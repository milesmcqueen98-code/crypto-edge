"""What `run.py status` and `run.py live` say about the batch order path (bot/spot/README.md, "Order path").

Pure functions, standard library only (Python 3.8 and later). summarize() reads event-log lines (text, one JSON event
per line; a malformed line is skipped) and the current time, and returns the numbers; latest_check() and
check_passed() read the order-check result files in a state folder; block() puts the lines together.
"""
import glob
import json
import os
import statistics
from datetime import datetime, timedelta

COUNTERS = ("reprice", "arm", "cancel_unconfirmed", "snap_miss", "snap_mismatch", "bbo_miss", "batch_fallback",
            "http_429")
FALLBACKS = ("snap_miss", "bbo_miss", "batch_fallback")
HB_MIN = 30                                            # minutes between heartbeats (Engine._heartbeat)
NOT_PASSED = "order check: not yet passed on this server (wickctl order-check)"


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "")[:26])
    except Exception:
        return None


def summarize(lines, now, hours=24):
    """Heartbeats of the last `hours` before `now` (a naive UTC datetime): how many; minutes covered (each heartbeat
    covers the minutes since the heartbeat before it, at most 30; the first one seen 30); the medians over heartbeats
    of the data mark's median and of the place mark's median minus the data mark's (with their largest values); the
    sums of COUNTERS; the newest rate_limit and library fields in the whole log (with their times)."""
    cut = now - timedelta(hours=hours)
    out = dict(heartbeats=0, minutes=0, first=None, last=None, data=None, data_max=None, gap=None, gap_max=None,
               counts={}, rate_limit=None, rate_limit_ts=None, library=None, library_ts=None, malformed=0)
    data, gap, prev = [], [], None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            if e.get("kind") != "heartbeat":
                continue
            t = _ts(e.get("ts"))
            if t is None:
                raise ValueError("no time")
        except Exception:
            out["malformed"] += 1
            continue
        if e.get("library"):
            out["library"], out["library_ts"] = e["library"], t
        if e.get("rate_limit"):
            out["rate_limit"], out["rate_limit_ts"] = e["rate_limit"], t
        p, prev = prev, t
        if t < cut or t > now:
            continue
        out["heartbeats"] += 1
        step = (t - p).total_seconds() / 60 if p is not None and t > p else HB_MIN
        out["minutes"] += int(round(min(HB_MIN, step)))
        out["first"] = out["first"] or t
        out["last"] = t
        for k, v in (e.get("counts") or {}).items():
            if k in COUNTERS and isinstance(v, (int, float)):
                out["counts"][k] = out["counts"].get(k, 0) + v
        s = e.get("step_s")
        try:
            d = float(s["data"][0])
            data.append(d)
            gap.append(float(s["place"][0]) - d)
        except Exception:
            pass                                       # a heartbeat without step_s (or without a place mark)
    if data:
        out["data"], out["data_max"] = statistics.median(data), max(data)
    if gap:
        out["gap"], out["gap_max"] = statistics.median(gap), max(gap)
    return out


def _checks(state_dir):
    out = []
    for p in sorted(glob.glob(os.path.join(state_dir, "order_check_*.json"))):
        try:
            with open(p) as fh:
                r = json.load(fh)
            out.append((p, r))
        except Exception:
            out.append((p, None))
    return out


def latest_check(state_dir):
    """(path, result dict or None if unreadable) of the newest order-check file (names sort by UTC time), or None."""
    c = _checks(state_dir)
    return c[-1] if c else None


def check_passed(state_dir):
    """True when some order-check file in the folder passed with test orders placed."""
    return any(r and r.get("passed") is True and r.get("place_test_orders") is True for _, r in _checks(state_dir))


def _r(x):
    return "-" if x is None else f"{x:.2f}"


def block(cfg, state_dir, lines, now, library):
    """The order-path lines of `status` for a config on the batch path."""
    out = [f"order path: batch ({cfg.get('orders_rate', 10)} requests a second, {cfg.get('place_workers', 1)} placing "
           "threads)", f"  library: coinbase-advanced-py {library or 'not found'}"]
    lc = latest_check(state_dir)
    if lc is None:
        out.append("  order check: none on this server yet (wickctl order-check)")
    elif lc[1] is None:
        out.append(f"  order check: {os.path.basename(lc[0])} cannot be read")
    else:
        r = lc[1]
        why = " ".join("; ".join(str(x) for x in r.get("reasons") or []).split())   # one line
        why = (": " + why[:150] + ("..." if len(why) > 150 else "")) if why else ""
        out.append(f"  order check: {r.get('started')} {'PASSED' if r.get('passed') else 'FAILED' + why}, "
                   f"{'test orders placed' if r.get('place_test_orders') else 'read-only'} "
                   f"({os.path.basename(lc[0])})")
    s = summarize(lines, now)
    if s["library"]:
        out.append(f"  library in the newest heartbeat that has it: {s['library']} ({s['library_ts']:%Y-%m-%d %H:%M})")
    if s["rate_limit"]:
        out.append(f"  rate limit headers, newest ({s['rate_limit_ts']:%Y-%m-%d %H:%M}): {s['rate_limit']}")
    if not s["heartbeats"]:
        out.append("  last 24 h: no heartbeat")
        return out
    out.append(f"  last 24 h: {s['heartbeats']} heartbeats, {s['minutes']} minutes covered "
               f"({s['first']:%Y-%m-%d %H:%M} .. {s['last']:%Y-%m-%d %H:%M} UTC)")
    out.append(f"  data step ended: median {_r(s['data'])} s after the minute (largest {_r(s['data_max'])})")
    out.append(f"  place minus data: median {_r(s['gap'])} s (largest {_r(s['gap_max'])})")
    out.append("  counters: " + ", ".join(f"{k} {s['counts'].get(k, 0):g}" for k in COUNTERS))
    n = sum(s["counts"].get(k, 0) for k in FALLBACKS)
    out.append(f"  place minus data: median {_r(s['gap'])} s (the plan's first-day figure is 3 s or less)")
    out.append(f"  single-request fallbacks: {n:g} in {s['minutes']} minutes (the plan's figure is fewer than 5% of "
               "minutes)")
    out.append("  (that count is snap_miss + bbo_miss + batch_fallback: orders and coins read singly, and pieces "
               "switched off; the heartbeats do not say in how many minutes a fallback happened)")
    return out
