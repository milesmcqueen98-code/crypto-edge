#!/usr/bin/env python3
"""Status report for the paper-trading logs (four books, five when paper_spot_tb exists).

Usage: python scripts/owner/paper_status.py [REPO_ROOT] [--now ISO_TIME]

Reads paper_spot/, paper_spot_w2/, paper/, paper_v2/ and, when its folder exists, paper_spot_tb/ (events.jsonl and state.json) under REPO_ROOT (default: the
repo this file lives in) and writes reports/owner/PAPER_STATUS.md. Reads reports/owner/explained_errors.json for errors the owner has explained (a missing or bad file means none are). Standard library only, no network. A missing
folder, an empty log, a truncated last line or an event kind it has not seen never stops the report.
"""
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

STALE_HOURS = 8.0
RULE_A = ("Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors "
          "and mean net per dollar is above 0.")
LAST_LINE = ("Paper fills assume the research's capture share; they check the machinery and the fill frequency, "
             "not whether real orders fill.")
RULE_A_RATE = "1-6 rung fills a day"   # rule A's rate text, as written in reports/owner/FORWARD_TESTS.md
ERR_CHARS = 160
EXPLAINED_FILE = os.path.join("reports", "owner", "explained_errors.json")

# key, folder, label, starting capital, spot-style book (rungs, ladders) or perp book
BOOKS = [
    ("spot", "paper_spot", "Spot (main)", 250000.0, True),
    ("w2", "paper_spot_w2", "Spot W2", 250000.0, True),
    ("v1", "paper", "Perp v1 (control)", 10000.0, False),
    ("r2", "paper_v2", "Perp R2-08", 10000.0, False),
]

TB_BOOK = ("tb", "paper_spot_tb", "Spot TB (trades input)", 250000.0, True)
TB_CONFIG = os.path.join("bot", "spot", "config.tb.json")
TB_DEFAULT_COINS = ["BTC", "ETH", "SOL", "XRP", "LTC", "ZEC"]   # the coins the forward rule names
TB_ALL_COINS = 18                                               # coins in the book (rule item 5)
TB_MIN_MINUTES = 4000                                           # real-time minutes the rule asks for
HEARTBEAT_MIN = 30                                              # the engine writes a heartbeat every 30 minutes
FIRST_RUNG = 4                                                  # the first (4-sigma) bid; deeper rungs are 6 and 8
MATCH_SECONDS = 120                                             # same coin within two minutes either side

# Data-quality counters the release-2 engine puts in the heartbeat's counts dict (any may be absent; every other key
# starting with tb_ is counted too). Old logs have none of them. See "Newest minute from trades" in bot/spot/README.md.
DQ_COUNTERS = (
    "newest_absent", "btc_stale", "candle_old", "btc_candle_old", "skip_old", "rows_open", "obs_error", "tb_built",
    "tb_empty", "tb_insert", "tb_rebuilt", "tb_close_diff", "tb_fb_unverified", "tb_fb_error", "tb_fb_budget",
    "tb_fb_limited",
)
NOT_REPORTED = "not reported by this book's code yet"
NOT_DERIVABLE = "not derivable from this log"

KNOWN_KINDS = {
    "backfill", "arm", "heartbeat", "fill_entry", "fill_exit", "ladder_close", "cash_short", "error", "catch_up",
    "bid", "cancel", "rung", "adv", "halt", "warning", "reject", "skip", "cancel_all", "fee_tier",
}


# ---------------------------------------------------------------- small helpers
def num(x):
    """A finite float, or None."""
    try:
        if isinstance(x, bool) or x is None:
            return None
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def parse_ts(s):
    """A timezone-aware UTC datetime from an ISO string (naive means UTC), or None."""
    if not isinstance(s, str) or not s:
        return None
    try:
        t = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def clean(s):
    """Text safe for a table cell: one line, no pipes, no at-sign."""
    s = " ".join(str(s).split())
    return s.replace("|", "/").replace(chr(64), " at ")


def money(x):
    if x is None:
        return "n/a"
    sign = "-" if x < 0 else ""
    a = abs(x)
    return f"{sign}${a:,.0f}" if a >= 1000 else f"{sign}${a:,.2f}"


def bp(x):
    return "n/a" if x is None else f"{x:,.1f} bp"


def pct(x, signed=True):
    if x is None:
        return "n/a"
    return f"{x:+.2f}%" if signed else f"{x:.2f}%"


def fmt_t(t):
    return "none" if t is None else t.strftime("%Y-%m-%d %H:%M UTC")


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(clean(c) for c in r) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------- explained errors
def load_explanations(root):
    """Returns (entries, note). A missing or malformed file gives no entries and a one-line note."""
    path = os.path.join(root, EXPLAINED_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return [], "No list of explained errors could be read, so every error counts as unexplained."
    if not isinstance(raw, list):
        return [], "The list of explained errors is not a list, so every error counts as unexplained."
    entries, skipped = [], 0
    for o in raw:
        ok = isinstance(o, dict) and isinstance(o.get("match"), str) and o["match"]
        t0 = parse_ts(o.get("from")) if ok else None
        t1 = parse_ts(o.get("to")) if ok else None
        books = o.get("books") if ok else None
        if not (ok and t0 and t1 and isinstance(books, list)):
            skipped += 1
            continue
        entries.append({"match": o["match"], "from": t0, "to": t1, "books": [str(b) for b in books],
                        "explained": str(o.get("explained", "")), "fix": str(o.get("fix", ""))})
    note = f"{skipped} entry(ies) in the list of explained errors could not be read and were ignored." if skipped else None
    return entries, note


def classify_errors(book_key, error_events, entries):
    """Splits error events (time, message) into explained [(time, message, entry)] and unexplained [(time, message)].
    Explained needs all three: the message contains the match text, the time is inside the window, the book is listed."""
    explained, unexplained = [], []
    for t, msg in error_events:
        hit = None
        for en in entries:
            if book_key in en["books"] and en["match"] in msg and t is not None and en["from"] <= t <= en["to"]:
                hit = en
                break
        if hit:
            explained.append((t, msg, hit))
        else:
            unexplained.append((t, msg))
    return explained, unexplained


# ---------------------------------------------------------------- loading
def load_book(root, folder):
    """Returns dict: status (ok, missing, empty), events (dicts with _t), bad (unreadable lines), state."""
    d = os.path.join(root, folder)
    res = {"status": "ok", "events": [], "bad": 0, "state": None, "note": None}
    if not os.path.isdir(d):
        res["status"] = "missing"
        return res
    path = os.path.join(d, "events.jsonl")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    res["bad"] += 1
                    continue
                if not isinstance(o, dict):
                    res["bad"] += 1
                    continue
                o["_t"] = parse_ts(o.get("ts"))
                res["events"].append(o)
    except OSError:
        res["status"] = "missing"
        return res
    if not res["events"]:
        res["status"] = "empty"
    try:
        with open(os.path.join(d, "state.json"), encoding="utf-8", errors="replace") as f:
            st = json.load(f)
        if isinstance(st, dict):
            res["state"] = st
    except (OSError, ValueError):
        pass
    return res


# ---------------------------------------------------------------- statistics
def stats(book, capital, spot_style):
    ev = book["events"]
    s = {"status": book["status"], "bad": book["bad"], "capital": capital, "n": len(ev)}
    times = [e["_t"] for e in ev if e["_t"] is not None]
    s["first"] = min(times) if times else None
    s["newest"] = max(times) if times else None
    s["days"] = (s["newest"] - s["first"]).total_seconds() / 86400 if times else None
    s["kinds"] = Counter(str(e.get("kind")) for e in ev)
    s["unknown"] = {k: n for k, n in s["kinds"].items() if k not in KNOWN_KINDS}

    entries = [e for e in ev if e.get("kind") == "fill_entry"]
    exits = [e for e in ev if e.get("kind") == "fill_exit"]
    closes = [e for e in ev if e.get("kind") == "ladder_close"]
    errors = [e for e in ev if e.get("kind") == "error"]
    beats = [e for e in ev if e.get("kind") == "heartbeat"]
    shorts = [e for e in ev if e.get("kind") == "cash_short"]

    s["fills"] = len(entries)
    usds = [num(e.get("usd")) for e in entries]
    known = [u for u in usds if u is not None]
    s["bought"] = sum(known) if (known or not entries) else None
    pnls = [num(e.get("pnl")) or 0.0 for e in exits]
    s["pnl"] = sum(pnls)
    s["net_bp"] = 1e4 * s["pnl"] / s["bought"] if s["bought"] else None
    s["exits"] = len(exits)
    s["tp"] = sum(1 for e in exits if e.get("exit") == "tp")
    s["time"] = sum(1 for e in exits if e.get("exit") == "time")
    s["other_exit"] = s["exits"] - s["tp"] - s["time"]
    nb = [num(e.get("net_bp")) for e in exits]
    nb = [v for v in nb if v is not None]
    s["mean_net_bp"] = sum(nb) / len(nb) if nb else None
    s["ladders"] = len(closes)
    s["ladders_win"] = sum(1 for e in closes if (num(e.get("pnl")) or 0.0) > 0)
    s["errors"] = len(errors)
    s["error_events"] = [(e["_t"], str(e.get("error", e.get("message", "(no message)")))) for e in errors]
    s["explained"] = []
    s["unexplained"] = len(errors)
    msgs = Counter()
    for e in errors:
        m = clean(e.get("error", e.get("message", "(no message)")))
        msgs[m[:ERR_CHARS]] += 1
    s["error_msgs"] = msgs
    s["unexplained_msgs"] = msgs
    s["bids"] = s["kinds"].get("bid", 0)
    s["cancels"] = s["kinds"].get("cancel", 0)
    s["halts"] = s["kinds"].get("halt", 0)
    s["warnings"] = s["kinds"].get("warning", 0)

    # equity: the book's own state when it has one, else the latest event that carries one
    eq = num((book["state"] or {}).get("equity"))
    if eq is None:
        for e in reversed(ev):
            v = num(e.get("equity"))
            if v is not None and e.get("kind") in ("heartbeat", "fill_exit"):
                eq = v
                break
    s["equity"] = eq
    s["change_pct"] = 100.0 * (eq / capital - 1.0) if eq is not None and capital else None

    if spot_style:
        by_rung = defaultdict(lambda: {"fills": 0, "bought": 0.0, "exits": 0, "pnl": 0.0})
        for rung in (4, 6, 8):
            by_rung[rung]
        for e in entries:
            r = num(e.get("rung"))
            r = int(r) if r is not None else -1
            by_rung[r]["fills"] += 1
            by_rung[r]["bought"] += num(e.get("usd")) or 0.0
        for e in exits:
            r = num(e.get("rung"))
            r = int(r) if r is not None else -1
            by_rung[r]["exits"] += 1
            by_rung[r]["pnl"] += num(e.get("pnl")) or 0.0
        s["by_rung"] = dict(sorted(by_rung.items()))

        daily = defaultdict(float)
        for e in exits:
            if e["_t"] is not None:
                daily[e["_t"].date()] += num(e.get("pnl")) or 0.0
        s["daily"] = dict(daily)
        losses = {d: v for d, v in daily.items() if v < 0}
        s["worst_day"] = min(losses.items(), key=lambda kv: kv[1]) if losses else None

        s["shorts"] = len(shorts)
        want = [num(e.get("want")) for e in shorts]
        free = [num(e.get("free")) for e in shorts]
        want = [v for v in want if v is not None]
        free = [v for v in free if v is not None]
        s["want_total"] = sum(want)
        s["want_avg"] = sum(want) / len(want) if want else None
        s["free_avg"] = sum(free) / len(free) if free else None

        shares = []
        for e in beats:
            c, q = num(e.get("committed")), num(e.get("equity"))
            if c is not None and q:
                shares.append(c / q)
        s["commit_share"] = 100.0 * sum(shares) / len(shares) if shares else None
        s["commit_n"] = len(shares)
    return s


def rule_a(s):
    days, rungs = s["days"] or 0.0, s["fills"]
    net = s["net_bp"]
    if s.get("unexplained", s["errors"]) > 0 or (net is not None and net <= 0):
        return "CHECK"
    if days >= 21 and rungs >= 60 and net is not None:
        return "ON TRACK"
    return "NOT YET (too early)"


# ---------------------------------------------------------------- running time
def active_books(root):
    """The four registered books, plus the third spot book when its folder exists."""
    books = list(BOOKS)
    if os.path.isdir(os.path.join(root, TB_BOOK[1])):
        books.insert(2, TB_BOOK)
    return books


def merge_intervals(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def running_time(events, first, last):
    """When the book was live, from its own log. Returns a dict: ok, first, last, cal_h, run_h, share, gaps (start,
    hours; longest first), down (merged intervals), note.

    Which events are used, and why:
    - Spot books and perp books both write a catch_up event when they start after a gap: its ts is the new start and
      gap_minutes is the time since the last minute the book had handled, so the book was not live from ts minus
      gap_minutes to ts. (Spot: bot/spot/engine.py, catch_up. Perp: same event name and field in the real logs; checked
      against heartbeat spacing, where a heartbeat gap of 480 minutes ends at a catch_up of 472 minutes, and a gap of
      180 ends at one of 145. Both books write a heartbeat every 30 minutes while live.) Real-time time is calendar
      time from the first to the last event minus the union of those gaps, clipped to that span.
    - A book with no catch_up events is taken as never gapped only if it has at least two heartbeats and no two
      consecutive heartbeats are more than 45 minutes apart. Otherwise the log cannot support it: not derivable.
    - A run whose log was never saved leaves no events, so it looks like a gap; the share can then be too low."""
    rt = {"ok": False, "first": first, "last": last, "cal_h": None, "run_h": None, "share": None, "gaps": [],
          "down": [], "note": NOT_DERIVABLE}
    if first is None or last is None or last <= first:
        return rt
    rt["cal_h"] = (last - first).total_seconds() / 3600
    gaps, n_cu = [], 0
    for e in events:
        if e.get("kind") != "catch_up":
            continue
        t, g = e.get("_t"), num(e.get("gap_minutes"))
        if t is None or g is None or g <= 0:
            continue
        n_cu += 1
        a, b = max(t - timedelta(minutes=g), first), min(t, last)
        if b > a:
            gaps.append((a, b))
    if n_cu == 0:
        hb = sorted(e["_t"] for e in events if e.get("kind") == "heartbeat" and e.get("_t") is not None)
        if len(hb) < 2 or any((y - x).total_seconds() > 45 * 60 for x, y in zip(hb, hb[1:])):
            return rt
    down = merge_intervals(gaps)
    lost = sum((b - a).total_seconds() for a, b in down) / 3600
    rt.update(ok=True, down=down, note="", run_h=rt["cal_h"] - lost, share=100.0 * (rt["cal_h"] - lost) / rt["cal_h"],
              gaps=sorted(((a, (b - a).total_seconds() / 3600) for a, b in gaps), key=lambda x: -x[1]))
    return rt


def up_hours(rt, a, b):
    """Hours in real time inside [a, b]. When the log cannot say, the whole span counts (calendar time)."""
    if rt is None:
        return 0.0
    if rt["first"] is not None:
        a = max(a, rt["first"])
    if rt["last"] is not None:
        b = min(b, rt["last"])
    if b <= a:
        return 0.0
    tot = (b - a).total_seconds()
    for d0, d1 in rt["down"]:
        tot -= max(0.0, (min(b, d1) - max(a, d0)).total_seconds())
    return max(0.0, tot) / 3600


def rate(n, hours):
    """n events over hours, as a per-day figure."""
    if hours is None or hours <= 0:
        return "n/a"
    return f"{n / (hours / 24.0):.2f}"


def both_rates(n, rt):
    """'x per calendar day; y per running day', labelled."""
    cal = rate(n, rt["cal_h"]) if rt and rt["cal_h"] else "n/a"
    run = rate(n, rt["run_h"]) if rt and rt["ok"] else NOT_DERIVABLE
    return f"{cal} per calendar day; {run} per running day"


def gaps_table(labels_rts):
    rows = []
    for label, rt in labels_rts:
        if rt["ok"]:
            for a, h in rt["gaps"][:5]:
                rows.append([label, fmt_t(a), f"{h:.1f}"])
    return table(["Book", "Gap start", "Hours"], rows) if rows else None


# ---------------------------------------------------------------- data quality (heartbeat counters)
def data_quality(events, rt):
    """Per spot book, from the heartbeats. A heartbeat reports when it carries step_s or any counter of the list (or any
    other key starting with tb_) or tb_err. Counters appear in counts only when they were counted, so a reporting
    heartbeat without a counter means 0. Minutes run for a heartbeat: the 30 minutes before it, less the gaps in them."""
    beats = sorted((e for e in events if e.get("kind") == "heartbeat" and e.get("_t") is not None),
                   key=lambda e: e["_t"])
    per_day = {}
    rep = []
    for e in beats:
        counts, step = e.get("counts"), e.get("step_s")
        found = {}
        if isinstance(counts, dict):
            for k, v in counts.items():
                x = num(v)
                if isinstance(k, str) and (k in DQ_COUNTERS or k.startswith("tb_")) and x is not None:
                    found[k] = x
        data = None
        if isinstance(step, dict) and isinstance(step.get("data"), (list, tuple)) and len(step["data"]) >= 2:
            m, mx = num(step["data"][0]), num(step["data"][1])
            if m is not None and mx is not None:
                data = (m, mx)
        reporting = bool(found) or isinstance(step, dict) or ("tb_err" in e)
        if not reporting:
            continue
        t = e["_t"]
        mins = 60.0 * up_hours(rt, t - timedelta(minutes=HEARTBEAT_MIN), t) if rt and rt["ok"] else float(HEARTBEAT_MIN)
        rep.append({"t": t, "counts": found, "data": data, "minutes": mins,
                    "err": clean(e.get("tb_err"))[:ERR_CHARS] if e.get("tb_err") else None})
    dq = {"all_beats": len(beats), "rep": rep, "days": {}, "total": None}

    def fold(rows):
        c = Counter()
        for r in rows:
            c.update(r["counts"])
        meds = [r["data"][0] for r in rows if r["data"]]
        maxs = [r["data"][1] for r in rows if r["data"]]
        return {"beats": len(rows), "minutes": sum(r["minutes"] for r in rows), "counts": c,
                "data_median": statistics.median(meds) if meds else None,
                "data_max": max(maxs) if maxs else None, "data_n": len(meds),
                "data_le20": sum(1 for v in maxs if v <= 20.0),
                "errs": [r for r in rows if r["err"]]}
    for d in sorted({r["t"].date() for r in rep}):
        per_day[d] = fold([r for r in rep if r["t"].date() == d])
    dq["days"] = per_day
    dq["total"] = fold(rep) if rep else None
    return dq


def count_text(c):
    items = [(k, v) for k, v in sorted(c.items()) if v]
    return ", ".join(f"{k} {v:,.0f}" if float(v).is_integer() else f"{k} {v:,.2f}" for k, v in items) or "all zero"


def num_s(x):
    return "n/a" if x is None else f"{x:.1f}"


def dq_section(label, dq):
    out = [f"### {label}", ""]
    if not dq or dq["total"] is None:
        return out + [NOT_REPORTED + ".", ""]
    rows = []
    for d, v in list(dq["days"].items()) + [("Total", dq["total"])]:
        rows.append([d.isoformat() if not isinstance(d, str) else d, f"{v['minutes']:,.0f}", str(v["beats"]),
                     num_s(v["data_median"]), num_s(v["data_max"]), count_text(v["counts"])])
    out += [table(["Day (UTC)", "Minutes run", "Heartbeats", "Data step median (s)", "Data step largest max (s)",
                   "Counters (sum)"], rows), ""]
    t = dq["total"]
    skipped = dq["all_beats"] - t["beats"]
    if skipped:
        out += [f"{skipped} earlier heartbeat(s) carry none of these fields and are not counted.", ""]
    if t["errs"]:
        out += [f"Heartbeats with a trades error (tb_err): {len(t['errs'])}. Last: {t['errs'][-1]['err']}", ""]
    return out


# ---------------------------------------------------------------- third book
def load_tb_coins(root):
    """(coins, source text). The list comes from bot/spot/config.tb.json (trades_coins) when it can be read."""
    try:
        with open(os.path.join(root, TB_CONFIG), encoding="utf-8") as f:
            cfg = json.load(f)
        lst = cfg.get("trades_coins") if isinstance(cfg, dict) else None
        if isinstance(lst, list) and lst and all(isinstance(c, str) and c for c in lst):
            return [str(c) for c in lst], "read from bot/spot/config.tb.json"
    except (OSError, ValueError):
        pass
    return list(TB_DEFAULT_COINS), "the six coins the rule names; no readable list in bot/spot/config.tb.json"


def mentions_refusal(events):
    """Events whose message text mentions a refusal or a rate limit (error, warning and similar message fields only)."""
    rx = re.compile(r"refus|rate.?limit|too many requests|\b429\b", re.I)
    n = 0
    for e in events:
        for k in ("error", "message", "msg", "reason", "tb_err"):
            v = e.get(k)
            if isinstance(v, str) and rx.search(v):
                n += 1
                break
    return n


def tb_rule_rows(dq, st, events, coins, rt):
    """Items 1 to 5 of the FORWARD_TESTS row. Returns (minutes_in_real_time, rows) with rows [item, value, verdict]."""
    t = dq["total"] if dq else None
    run_min = (rt["run_h"] * 60.0) if rt and rt["ok"] else None
    no = "does not meet yet"
    rows = []
    n = len(coins)
    if t is None or t["minutes"] <= 0:
        for i, txt in enumerate(["Verified trades bar share of listed coin-minutes (needs 99% or more)",
                                 "No rate-limit fallback (tb_fb_limited 0) and no refusal in any event",
                                 "Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats",
                                 "No error events and obs_error 0",
                                 "Unconfirmed rows (rows_open) 1% or less of coin-minutes"], 1):
            rows.append([f"{i}. {txt}", "no heartbeat reports the new fields yet", no])
        return run_min, rows
    c, mins = t["counts"], t["minutes"]
    # item 1
    verified = c.get("tb_built", 0) + c.get("tb_empty", 0)
    share = 100.0 * verified / (n * mins)
    v1 = f"{share:.2f}% ({verified:,.0f} verified of {n * mins:,.0f} coin-minutes, {n} coins: {', '.join(coins)})"
    if sorted(coins) != sorted(TB_DEFAULT_COINS):
        v1 += f"; against the rule's six coins: {100.0 * verified / (len(TB_DEFAULT_COINS) * mins):.2f}%"
    rows.append(["1. Verified trades bar share of listed coin-minutes (99% or more)", v1, "meets" if share >= 99.0 else no])
    # item 2
    lim = c.get("tb_fb_limited", 0)
    ref = mentions_refusal(events)
    rows.append(["2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event",
                 f"tb_fb_limited {lim:,.0f}; events mentioning a refusal or rate limit {ref}",
                 "meets" if lim == 0 and ref == 0 else no])
    # item 3
    if t["data_n"]:
        med = t["data_median"]
        sh = 100.0 * t["data_le20"] / t["data_n"]
        ok3 = med <= 13.0 and sh >= 95.0
        v3 = f"median {med:.1f} s of {t['data_n']} heartbeats; maximum 20 s or less in {sh:.1f}% (largest {t['data_max']:.1f} s)"
    else:
        ok3, v3 = False, "no heartbeat has a data step time yet"
    rows.append(["3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats", v3,
                 "meets" if ok3 else no])
    # item 4
    errs, obs = st["errors"], c.get("obs_error", 0)
    rows.append(["4. No error events and obs_error 0", f"error events {errs}; obs_error {obs:,.0f}",
                 "meets" if errs == 0 and obs == 0 else no])
    # item 5
    ro = c.get("rows_open", 0)
    sh5 = 100.0 * ro / (TB_ALL_COINS * mins)
    rows.append(["5. Unconfirmed rows (rows_open) 1% or less of coin-minutes",
                 f"{sh5:.3f}% ({ro:,.0f} of {TB_ALL_COINS * mins:,.0f} coin-minutes, {TB_ALL_COINS} coins)",
                 "meets" if sh5 <= 1.0 else no])
    return run_min, rows


def window_stats(events, a, b):
    """Entries, first-bid entries, dollars bought and exit P&L from events whose time is in [a, b]."""
    ent = [e for e in events if e.get("kind") == "fill_entry" and e.get("_t") is not None and a <= e["_t"] <= b]
    ext = [e for e in events if e.get("kind") == "fill_exit" and e.get("_t") is not None and a <= e["_t"] <= b]
    rungs = [e for e in events if e.get("kind") == "rung" and e.get("_t") is not None and a <= e["_t"] <= b]
    bought = sum(num(e.get("usd")) or 0.0 for e in ent)
    pnl = sum(num(e.get("pnl")) or 0.0 for e in ext)
    first = [e for e in ent if num(e.get("rung")) == FIRST_RUNG]
    return {"fills": len(ent), "first": first, "deeper_placed": len(rungs), "bought": bought, "pnl": pnl,
            "net_bp": 1e4 * pnl / bought if bought else None, "exits": len(ext)}


def match_first_bids(fa, fb):
    """One-to-one matching of fills of two books: same coin, times within MATCH_SECONDS either side, nearest pairs
    first. Returns (both, only_a, only_b)."""
    pairs = []
    for i, x in enumerate(fa):
        for j, y in enumerate(fb):
            if x.get("coin") == y.get("coin"):
                d = abs((x["_t"] - y["_t"]).total_seconds())
                if d <= MATCH_SECONDS:
                    pairs.append((d, i, j))
    pairs.sort()
    ua, ub, both = set(), set(), 0
    for d, i, j in pairs:
        if i not in ua and j not in ub:
            ua.add(i)
            ub.add(j)
            both += 1
    return both, len(fa) - both, len(fb) - both


# ---------------------------------------------------------------- report
def na(s, v):
    return "no data" if s["status"] != "ok" else v


def summary_row(label, s, spot_style):
    if s["status"] != "ok":
        return [label, s["status"] + " log"] + ["-"] * 8
    exits = f"{s['tp']} / {s['time']}" + (f" (+{s['other_exit']} other)" if s["other_exit"] else "")
    lad = f"{s['ladders']} ({s['ladders_win']} made money)" if spot_style else "-"
    return [label, f"{s['days']:.1f}" if s["days"] is not None else "n/a", money(s["equity"]), pct(s["change_pct"]),
            str(s["fills"]), money(s["bought"]) if s["bought"] is not None else "n/a (not logged)", bp(s["net_bp"]),
            exits, lad, str(s["errors"])]


def tb_sections(st, loaded, rts, dqs, labels, root):
    """The third spot book against the main book, and its progress on the three-day rule (items 1 to 5)."""
    L = []
    tb, sp = st["tb"], st["spot"]
    L += ["## Third book against the main book", ""]
    if tb["status"] != "ok" or sp["status"] != "ok":
        L += ["Both logs are needed for this comparison; one is missing or empty.", ""]
    else:
        a, b = max(tb["first"], sp["first"]), min(tb["newest"], sp["newest"])
        if b <= a:
            L += ["The two books have no period in common yet.", ""]
        else:
            ws, wt = window_stats(loaded["spot"]["events"], a, b), window_stats(loaded["tb"]["events"], a, b)
            cal = (b - a).total_seconds() / 3600
            hs, ht = up_hours(rts["spot"], a, b), up_hours(rts["tb"], a, b)
            both_h = None
            if rts["spot"]["ok"] and rts["tb"]["ok"]:
                dn = merge_intervals(list(rts["spot"]["down"]) + list(rts["tb"]["down"]))
                both_h = (b - a).total_seconds() / 3600 - sum(
                    max(0.0, (min(b, d1) - max(a, d0)).total_seconds()) for d0, d1 in dn) / 3600
            fb = match_first_bids(ws["first"], wt["first"])
            def rr(n, h, ok):
                return rate(n, h) if ok else NOT_DERIVABLE
            rows = [
                ["Rung fills", str(ws["fills"]), str(wt["fills"]), f"{wt['fills'] - ws['fills']:+d}"],
                ["Rung fills per calendar day", rate(ws["fills"], cal), rate(wt["fills"], cal), ""],
                ["Rung fills per running day", rr(ws["fills"], hs, rts["spot"]["ok"]), rr(wt["fills"], ht, rts["tb"]["ok"]), ""],
                ["First-bid fills (rung 4)", str(len(ws["first"])), str(len(wt["first"])), f"{len(wt['first']) - len(ws['first']):+d}"],
                ["Deeper rungs placed", str(ws["deeper_placed"]), str(wt["deeper_placed"]), ""],
                ["Dollars bought", money(ws["bought"]), money(wt["bought"]), money(wt["bought"] - ws["bought"])],
                ["Exit P&L", money(ws["pnl"]), money(wt["pnl"]), money(wt["pnl"] - ws["pnl"])],
                ["Net per dollar bought", bp(ws["net_bp"]), bp(wt["net_bp"]),
                 "n/a" if ws["net_bp"] is None or wt["net_bp"] is None else f"{wt['net_bp'] - ws['net_bp']:+.1f} bp"],
            ]
            L += [f"Period both ran: {fmt_t(a)} to {fmt_t(b)} ({cal:.1f} calendar hours; "
                  + (f"{both_h:.1f} hours with both live)." if both_h is not None else "hours with both live: " + NOT_DERIVABLE + ")"),
                  "", table(["Measure", "Spot (main)", "Spot TB", "TB minus main"], rows), ""]
            L += ["How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side "
                  "counts as the same fill, each fill used once):", "",
                  table(["Group", "Fills"], [["First-bid fills in both books", str(fb[0])],
                                            ["Only in the main book", str(fb[1])],
                                            ["Only in the third book", str(fb[2])]]), ""]
            L += ["This comparison is for the record. It is not the pass rule; the rule is below.", ""]
    coins, src = load_tb_coins(root)
    L += ["## Three-day rule progress for the third book", "",
          "> Verified inputs (release 2): after the first three full days of real-time running (at least 4,000 minutes), "
          "items 1 to 7 below must all hold. The rule is in reports/owner/FORWARD_TESTS.md. Items 1 to 5 are computed here "
          "from the heartbeats; the values are provisional until the minutes are reached.", ""]
    if tb["status"] != "ok":
        L += [f"No third-book log to judge ({tb['status']}).", ""]
        return L
    rt = rts["tb"]
    run_min, rows = tb_rule_rows(dqs.get("tb"), tb, loaded["tb"]["events"], coins, rt)
    L += [f"Real-time minutes run so far: "
          + (f"{run_min:,.0f} of {TB_MIN_MINUTES:,} ({100.0 * run_min / TB_MIN_MINUTES:.0f}%)." if run_min is not None
             else NOT_DERIVABLE + f" (needs {TB_MIN_MINUTES:,})."), "",
          f"Listed coins for item 1: {', '.join(coins)} ({src}).", ""]
    rows.append(["6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day",
                 "from the forward collector; computed at the read by scripts/owner/tb_rule6.py", "not computed here"])
    rows.append(["7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both",
                 "from the reconciliation (scripts/owner/reconcile); not computed here", "not computed here"])
    L += [table(["Item", "Current value", "Verdict"], rows), ""]
    return L


def build_report(root, now):
    loaded, st, rts, dqs = {}, {}, {}, {}
    notes = []
    books = active_books(root)
    for key, folder, label, cap, spot_style in books:
        try:
            loaded[key] = load_book(root, folder)
            st[key] = stats(loaded[key], cap, spot_style)
        except Exception as exc:  # never fail on odd data
            loaded[key] = {"status": "empty", "events": [], "bad": 0, "state": None}
            st[key] = stats(loaded[key], cap, spot_style)
            notes.append(f"{label}: could not be fully read ({clean(type(exc).__name__)}); shown as empty.")
    entries, expl_note = load_explanations(root)
    for key in st:
        ex, un = classify_errors(key, st[key]["error_events"], entries)
        st[key]["explained"] = ex
        st[key]["unexplained"] = len(un)
        m = Counter(clean(msg)[:ERR_CHARS] for _, msg in un)
        st[key]["unexplained_msgs"] = m
    labels = {k: lab for k, _, lab, _, _ in books}
    kinds_spot = {k: spot for k, _, _, _, spot in books}
    for key, _, label, _, spot_style in books:
        try:
            rts[key] = running_time(loaded[key]["events"], st[key]["first"], st[key]["newest"])
        except Exception as exc:
            rts[key] = running_time([], None, None)
            notes.append(f"{label}: running time could not be worked out ({clean(type(exc).__name__)}).")
        try:
            dqs[key] = data_quality(loaded[key]["events"], rts[key]) if spot_style else None
        except Exception as exc:
            dqs[key] = None
            notes.append(f"{label}: data quality could not be worked out ({clean(type(exc).__name__)}).")

    L = ["# Paper trading status", "", f"Report made {fmt_t(now)}.", ""]
    rows = []
    for key, folder, label, _, _ in books:
        s = st[key]
        if s["newest"] is None:
            rows.append([label, "none", "-", "NO DATA (" + ("folder missing" if s["status"] == "missing" else "empty log") + ")"])
            continue
        age = (now - s["newest"]).total_seconds() / 3600
        flag = "STALE" if age > STALE_HOURS else "ok"
        rows.append([label, fmt_t(s["newest"]), f"{age:.1f} h ago", flag])
    L += [table(["Book", "Newest event", "Age", "Flag"], rows), "",
          f"A book is flagged STALE when its newest event is more than {STALE_HOURS:g} hours old.", ""]

    # running time
    L += ["## Running time", "",
          "GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only "
          "settles what was already open. So the books were live in real time for only part of the calendar time, and "
          "every rate per calendar day below understates the rate while running. Rates are given both ways.", ""]
    rrows = []
    for key, _, label, _, _ in books:
        rt = rts[key]
        if st[key]["newest"] is None:
            rrows.append([label, "none", "none", "-", "-", "-"])
        elif rt["ok"]:
            rrows.append([label, fmt_t(rt["first"]), fmt_t(rt["last"]), f"{rt['cal_h']:.1f}", f"{rt['run_h']:.1f}",
                          f"{rt['share']:.1f}%"])
        else:
            rrows.append([label, fmt_t(rt["first"]), fmt_t(rt["last"]),
                          f"{rt['cal_h']:.1f}" if rt["cal_h"] is not None else "-", NOT_DERIVABLE, NOT_DERIVABLE])
    L += [table(["Book", "First event", "Last event", "Calendar hours", "Hours in real time", "Share"], rrows), ""]
    gt = gaps_table([(labels[k], rts[k]) for k in rts if st[k]["newest"] is not None])
    if gt:
        L += ["The five longest gaps of each book (a gap is the time the book was not running before a restart):", "", gt, ""]
    since = [f"{labels[k]} {(now - st[k]['newest']).total_seconds() / 3600:.1f} h" for k in st
             if st[k]["newest"] is not None]
    L += ["Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records "
          "(each restart logs a catch_up event with the minutes the book was not running). A run whose log was never "
          "saved would show as a gap, so the share can read too low. Time since the last event, not counted above: "
          + "; ".join(since) + ".", ""]

    # summary
    L += ["## Summary", ""]
    hdr = ["Book", "Days", "Equity", "Change", "Rung fills", "Dollars bought", "Net per dollar", "Exit events TP / time",
           "Ladders closed", "Errors"]
    L += [table(hdr, [summary_row(labels[k], st[k], kinds_spot[k]) for k in st]), "",
          "Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). "
          "Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought "
          "with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.", ""]

    # rule A
    sp = st["spot"]
    L += ["## Spot book against forward rule A", "", f"> {RULE_A}", ""]
    if sp["status"] != "ok":
        L += [f"No spot log to judge ({sp['status']}). Status: NOT YET (too early).", ""]
    else:
        L += [table(["Measure", "So far"], [
            ["Days (calendar)", f"{sp['days']:.1f} of 21"],
            ["Days in real time", f"{rts['spot']['run_h'] / 24:.1f}" if rts["spot"]["ok"] else NOT_DERIVABLE],
            ["Rungs", f"{sp['fills']} of 60"],
            [f"Rung fills a day (rule text: {RULE_A_RATE})", both_rates(sp["fills"], rts["spot"])],
            ["Mean net per dollar", bp(sp["net_bp"])],
            ["Errors (total)", str(sp["errors"])],
            ["Explained", str(len(sp["explained"]))],
            ["Unexplained", str(sp["unexplained"])]]), ""]
        if expl_note:
            L += [expl_note, ""]
        if sp["explained"]:
            L += ["Explained errors:", "",
                  table(["Time (UTC)", "Error (first 160 characters)", "Explanation", "Queued fix"],
                        [[fmt_t(t), clean(msg)[:ERR_CHARS], en["explained"], en["fix"]]
                         for t, msg, en in sp["explained"]]), ""]
        if sp["unexplained_msgs"] and sp["unexplained"]:
            L += ["Unexplained errors:", "",
                  table(["Error message (first 160 characters)", "Count"],
                        [[m, str(n)] for m, n in sp["unexplained_msgs"].most_common()]), ""]
        L += [f"Status: **{rule_a(sp)}**", "",
              "CHECK means unexplained errors are present or net is at or below 0. NOT YET means the 3 weeks and 60 rungs are not "
              "reached. ON TRACK means both are reached with no unexplained errors and net above 0. The owner declares any pass.", ""]

    # spot detail
    L += ["## Spot book detail", ""]
    if sp["status"] != "ok":
        L += ["No spot log.", ""]
    else:
        rr = []
        for r, v in sp["by_rung"].items():
            net = 1e4 * v["pnl"] / v["bought"] if v["bought"] else None
            rr.append(["unknown" if r < 0 else str(r), str(v["fills"]), money(v["bought"]), str(v["exits"]),
                       money(v["pnl"]), bp(net)])
        L += ["Fills and net per dollar by rung:", "",
              table(["Rung", "Fills", "Dollars bought", "Exit events", "Exit P&L", "Net per dollar"], rr), ""]
        end = (sp["newest"] or now).date()
        start = end - timedelta(days=13)
        if sp["first"] is not None and sp["first"].date() > start:
            start = sp["first"].date()
        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        L += ["P&L of exits by day, last 14 days:", "",
              table(["Day (UTC)", "Exit P&L", "Hours running"],
                    [[d.isoformat(), money(sp["daily"].get(d, 0.0)),
                      f"{up_hours(rts['spot'], datetime(d.year, d.month, d.day, tzinfo=timezone.utc), datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(days=1)):.1f}"
                      if rts["spot"]["ok"] else NOT_DERIVABLE] for d in days]), ""]
        if sp["shorts"]:
            L += [f"Cash shortfalls: {sp['shorts']}. Wanted {money(sp['want_total'])} in total "
                  f"(average {money(sp['want_avg'])}) against an average of {money(sp['free_avg'])} free.", ""]
        else:
            L += ["Cash shortfalls: 0.", ""]
        L += [("Share of capital held by resting bids (committed over equity, mean of "
               f"{sp['commit_n']} heartbeats): {pct(sp['commit_share'], False)}." if sp["commit_share"] is not None
               else "Share of capital held by resting bids: n/a (no heartbeats)."), ""]
        if sp["worst_day"]:
            d, v = sp["worst_day"]
            L += [f"Largest single-day loss so far: {money(v)} on {d.isoformat()}.", ""]
        else:
            L += ["Largest single-day loss so far: none (no losing day yet).", ""]

    # W2
    w2 = st["w2"]
    L += ["## W2 against the main spot book", ""]
    if sp["status"] != "ok" or w2["status"] != "ok":
        L += ["Both spot logs are needed for this comparison; one is missing or empty.", ""]
    else:
        def diff(a, b, f):
            return "n/a" if a is None or b is None else f(b - a)
        cmp_rows = [
            ["Days (calendar)", f"{sp['days']:.1f}", f"{w2['days']:.1f}", f"{w2['days'] - sp['days']:+.1f}"],
            ["Hours in real time", f"{rts['spot']['run_h']:.1f}" if rts["spot"]["ok"] else NOT_DERIVABLE,
             f"{rts['w2']['run_h']:.1f}" if rts["w2"]["ok"] else NOT_DERIVABLE, ""],
            ["Equity", money(sp["equity"]), money(w2["equity"]), diff(sp["equity"], w2["equity"], money)],
            ["Change", pct(sp["change_pct"]), pct(w2["change_pct"]),
             diff(sp["change_pct"], w2["change_pct"], lambda v: f"{v:+.2f} pp")],
            ["Rung fills", str(sp["fills"]), str(w2["fills"]), f"{w2['fills'] - sp['fills']:+d}"],
            ["Rung fills per calendar day", rate(sp["fills"], rts["spot"]["cal_h"]), rate(w2["fills"], rts["w2"]["cal_h"]), ""],
            ["Rung fills per running day", rate(sp["fills"], rts["spot"]["run_h"]) if rts["spot"]["ok"] else NOT_DERIVABLE,
             rate(w2["fills"], rts["w2"]["run_h"]) if rts["w2"]["ok"] else NOT_DERIVABLE, ""],
            ["Dollars bought", money(sp["bought"]), money(w2["bought"]), diff(sp["bought"], w2["bought"], money)],
            ["Net per dollar", bp(sp["net_bp"]), bp(w2["net_bp"]),
             diff(sp["net_bp"], w2["net_bp"], lambda v: f"{v:+.1f} bp")],
            ["Exit events TP / time", f"{sp['tp']} / {sp['time']}", f"{w2['tp']} / {w2['time']}", ""],
            ["Ladders closed (made money)", f"{sp['ladders']} ({sp['ladders_win']})",
             f"{w2['ladders']} ({w2['ladders_win']})", ""],
            ["Errors", str(sp["errors"]), str(w2["errors"]), f"{w2['errors'] - sp['errors']:+d}"],
        ]
        L += [table(["Measure", "Spot (main)", "W2", "W2 minus main"], cmp_rows), ""]
        if sp["first"] and w2["first"] and sp["first"] != w2["first"]:
            gap = abs((w2["first"] - sp["first"]).total_seconds()) / 3600
            L += [f"W2 started {gap:.1f} hours {'after' if w2['first'] > sp['first'] else 'before'} the main book, "
                  "so the windows are not identical.", ""]
        eqd = diff(sp["equity"], w2["equity"], money)
        L += [f"Difference in equity (W2 minus main): {eqd}.", "",
              "A few days and a few dozen fills cannot separate the two weightings; a gap this size is within "
              "what chance alone produces.", ""]

    # data quality
    L += ["## Data quality", "",
          "From the heartbeats of each spot book (one every 30 minutes while it runs). Counters are summed per UTC day; a "
          "counter that is not listed was 0 or is not reported. Minutes run are the 30 minutes before each heartbeat, "
          "less any gap. Data step is the seconds after the minute at which the data step finished: the median of the "
          "heartbeat medians, and the largest heartbeat maximum.", ""]
    for key, _, label, _, spot_style in books:
        if spot_style:
            L += dq_section(label, dqs.get(key))

    # third book
    if "tb" in st:
        L += tb_sections(st, loaded, rts, dqs, labels, root)

    # perps
    L += ["## Perp books", ""]
    prow = []
    for key in ("v1", "r2"):
        s = st[key]
        if s["status"] != "ok":
            prow.append([labels[key], s["status"] + " log", "-", "-", "-", "-", "-", "-"])
        else:
            rt = rts[key]
            fcal = rate(s["fills"], rt["cal_h"]) if rt["cal_h"] else "n/a"
            frun = rate(s["fills"], rt["run_h"]) if rt["ok"] else NOT_DERIVABLE
            prow.append([labels[key], str(s["fills"]), fcal, frun, bp(s["mean_net_bp"]), money(s["equity"]),
                         pct(s["change_pct"]), f"{s['bids']:,}"])
    L += [table(["Book", "Fills", "Fills per calendar day", "Fills per running day", "Net per trade", "Equity", "Change",
                 "Bids placed"], prow), "",
          "Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days "
          "from the first to the newest event; fills per running day divides by the days the book was live (see Running time).", ""]

    # data notes
    for key, _, label, _, _ in books:
        s = st[key]
        if s["status"] == "missing":
            notes.append(f"{label}: folder or events file not found.")
        elif s["status"] == "empty":
            notes.append(f"{label}: events log is empty.")
        if s["bad"]:
            notes.append(f"{label}: {s['bad']} unreadable line(s) skipped (a truncated last line is normal if the log was being written).")
        if s["unknown"]:
            notes.append(f"{label}: event kinds not seen before: " + ", ".join(f"{clean(k)} ({n})" for k, n in sorted(s["unknown"].items())) + ".")
        if s["halts"] or s["warnings"]:
            notes.append(f"{label}: {s['halts']} halt and {s['warnings']} warning events in the log.")
    if notes:
        L += ["## Data notes", ""] + [f"- {n}" for n in notes] + [""]

    L += [LAST_LINE, ""]
    return "\n".join(L)


def main(argv):
    args = list(argv)
    now = datetime.now(timezone.utc)
    if "--now" in args:
        i = args.index("--now")
        t = parse_ts(args[i + 1]) if i + 1 < len(args) else None
        if t is not None:
            now = t
        del args[i:i + 2]
    root = args[0] if args else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    text = build_report(root, now)
    out = os.path.join(root, "reports", "owner", "PAPER_STATUS.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
