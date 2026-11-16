"""One alternating-minute run for Part 3 of reports/owner/trades_workers_plan.md (deviation log of Nov 16 2026, 18:35 ET):
ONE paper run of --minutes minutes on one machine and on the pinned code, with the sixth book's config
(CODE_DIR/bot/spot/config.tw.json). The trades pass uses one worker in one minute and three in the next, turn by turn. No
orders, public data only (paper mode). The tool itself uses the standard library only; the engine it loads brings pandas.

Usage: python scripts/owner/workers_alt/run_alt.py --code CODE_DIR --first one|three --minutes 60 --out reports/owner/workers_alt

What it does (ported from in_process, instrument and parity of the candidate's bot/spot/tb_smoke.py, which cannot be
imported because it parses arguments at import): CODE_DIR goes first on sys.path, bot.spot.engine.Engine is built in paper
mode (echo off) on a fresh temporary state folder and eng.run(minutes) is called, with methods wrapped on the instance.
The job does not run (counts false, why) if config.tw.json is missing, the engine has no trades_workers attribute or its
market has no trades_many.

The arms: eng.step is wrapped. At each call m = int(clock() // 60) (the UTC minute now); the arm of an even m is --first
("one" is 1 worker, "three" is 3), of an odd m the other one; eng.trades_workers is set to 1 or 3 before the real step runs.
The start-up pass inside eng.run is not a step and is not recorded.

Per step (eng.trades_pass and eng._mark are wrapped): minute (YYYY-MM-DDTHH:MM, UTC, the minute the step runs in), workers,
pass_s (the pass's duration by eng._timer, rounded to 3 decimals, and pass_text, the same as text), data_end_s (seconds
after the minute at which the data part was marked, null if not marked), the increases over the pass of the counters
tb_fb_budget, tb_fb_limited, tb_fb_error, tb_fb_unverified, peak (trades_peak(reset=True) just before the pass, read just
after: the most trades requests in any one second during that pass), limited (tb_fb_limited rose), refused (tb_fb_error
rose AND the engine's _tb_err text matches Refused( or HTTP 401, HTTP 403, HTTP 451; the text, cut to 200 characters, is
kept as err), and the bars of the pass: for each coin of the pass (BTC and every coin, restricted to eng.trades_coins when
it is set) and the minute the pass built (its argument), the row the engine holds if its provenance says trades-built and
the minute is in eng.spot[coin] (open, high, low, close, volume as floats); a trades-built minute with no row is a verified
empty minute; a coin that fell back has no entry. The result file keeps only bars_built and bars_empty per step.

After the run, the rows: for each coin one request for the venue's candles over the recorded minutes
(eng.market.spot_candles(coin, start, end, tries=1, need_answer=True): ONE try per coin, no retry, one coin after another), made at least three minutes after the last recorded
minute (it waits if needed). The newest three recorded minutes are left out, as tb_smoke's parity leaves out the newest
three minutes. EQUALITY, as in tb_smoke's parity: a recorded bar and the venue's candle of its minute are "identical" when
all five values open, high, low, close and volume are equal as floats (==, no tolerance). A recorded bar whose minute has no
candle differs. A recorded empty minute is equal when the venue has no candle for that minute and differs when it has one.
Counted by the arm that built the bar: rows_compared, rows_differ. One try per coin, no retry: a request that is refused,
rate-limited (no answer) or fails raises, and the comparison stops at once and is reported, rows_complete is false with the reason (rows_reason), and nothing is counted for the coins not
compared (a coin counts only when all its bars were compared). The refusal is the comparison's, not an arm's.

Result: <out>/alt_<UTC start YYYYMMDDTHHMM>Z.json with utc_start, utc_end, minutes, code_commit (git rev-parse HEAD in
CODE_DIR, or null), first, steps, arms (keys "1" and "3": steps_timed (steps with a pass), pass_median_text (exact decimal
of the median of the rounded pass_s), pass_mean_s, pass_longest_s, slow_over_6s (pass_s strictly above 6.0), fb_budget,
fb_limited, fb_error, fb_unverified (sums), peak_max, limited_steps, refused_steps, rows_compared, rows_differ), rows_complete,
rows_reason, events (the engine's error, warning and halt events from events.jsonl: ts, kind, message cut to 200 characters),
counts (true when the run ended without an exception and each arm has at least 20 timed steps) and why_not. It never
raises: any failure gives a result file with counts false and the reason, and the exit code is 0.

The engine and the market come from a factory (make_env), so the tests pass a fake one.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from decimal import Decimal

MIN_STEPS = 20
SLOW_S = 6.0
CONFIG = os.path.join("bot", "spot", "config.tw.json")
COUNTERS = ("tb_fb_budget", "tb_fb_limited", "tb_fb_error", "tb_fb_unverified")
REFUSAL_RX = re.compile(r"Refused\(|HTTP 401|HTTP 403|HTTP 451")
COLS = ("open", "high", "low", "close", "volume")


class NoJob(Exception):
    """The job cannot run; the message is the reason written to the result file."""


def now_utc():
    return datetime.now(timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def minute_key(m):
    """YYYY-MM-DDTHH:MM of a minute (a datetime, a pandas Timestamp or a key already)."""
    return m if isinstance(m, str) else m.strftime("%Y-%m-%dT%H:%M")


def key_epoch(key):
    return datetime.strptime(key, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc).timestamp()


def epoch_key(sec):
    return datetime.fromtimestamp(sec, timezone.utc).strftime("%Y-%m-%dT%H:%M")


class Env:
    """What the tool needs of the engine and the market. eng: the engine; peak(reset): the most trades requests in one second;
    row(coin, minute): (o, h, l, c, v) floats the engine holds or None; trusted(coin, minute): provenance says trades-built;
    candles(coin, start_key, end_key): {minute key: (o, h, l, c, v)} of the venue, [start, end); state_dir."""
    def __init__(self, eng, peak, row, trusted, candles, state_dir):
        self.eng, self.peak, self.row, self.trusted, self.candles, self.state_dir = eng, peak, row, trusted, candles, state_dir


def make_env(code_dir, state_dir):
    """The real engine on CODE_DIR (paper mode). Raises NoJob when the job cannot run."""
    cpath = os.path.join(code_dir, CONFIG)
    if not os.path.isfile(cpath):
        raise NoJob(f"{CONFIG} not found in {code_dir}")
    cfg = json.load(open(cpath))
    sys.path.insert(0, code_dir)
    from bot import market
    from bot.spot.engine import Engine
    import pandas as pd
    eng = Engine(mode="paper", cfg=cfg, state_dir=state_dir, echo=False)
    if not hasattr(eng, "trades_workers"):
        raise NoJob("the engine has no trades_workers attribute")
    if not hasattr(eng.market, "trades_many"):
        raise NoJob("the engine's market has no trades_many")

    def row(c, m):
        e = eng.spot.get(c)
        t = pd.Timestamp(m)
        if e is None or t not in e.index:
            return None
        return tuple(float(e.loc[t, k]) for k in COLS)

    def trusted(c, m):
        return bool(eng._prov.get(c, {}).get(pd.Timestamp(m), (None, False))[1])

    def candles(c, start, end):
        return fetch_candles(eng.market, c, start, end)
    return Env(eng, lambda reset=False: market.trades_peak(reset=reset), row, trusted, candles, state_dir)


def fetch_candles(market, c, start, end):
    """One request for the venue's candles of one coin: one try, no retry, and a request that got no answer (every try a
    429) raises RuntimeError, as does a connection error on the one try (bot/market.py spot_candles with tries=1 and
    need_answer=True). {minute key: (open, high, low, close, volume)}."""
    import pandas as pd
    v = market.spot_candles(c, pd.Timestamp(start), pd.Timestamp(end), tries=1, need_answer=True)
    return {minute_key(t): tuple(float(v.loc[t, k]) for k in COLS) for t in v.index}


def git_commit(code_dir):
    try:
        r = subprocess.run(["git", "-C", code_dir, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)
        c = r.stdout.strip()
        return c if r.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", c) else None
    except Exception:
        return None


# ---------------------------------------------------------------- the run
def instrument(env, first, clock=time.time):
    """Wrap eng.step, eng._mark and eng.trades_pass on the instance; returns the list of step records (each with the private
    keys _bars: {coin: tuple, or None for a verified empty minute} and _pass_minute)."""
    eng = env.eng
    recs, cur = [], {}
    step, mark, tpass = eng.step, eng._mark, eng.trades_pass
    other = "three" if first == "one" else "one"

    def w_step(t=None):
        now = clock()
        m = int(now // 60)
        arm = first if m % 2 == 0 else other
        workers = 1 if arm == "one" else 3
        eng.trades_workers = workers
        cur.clear()
        cur.update(on=True, minute=epoch_key(m * 60), workers=workers, m0=m * 60, data=None, rec=None)
        try:
            return step(t) if t is not None else step()
        finally:
            r = cur.get("rec")
            if r is None:
                r = dict(minute=cur["minute"], workers=workers, pass_s=None, pass_text=None)
                r.update({k: 0 for k in COUNTERS})
                r.update(peak=None, limited=False, refused=False, err=None, _bars={}, _pass_minute=None)
            r["data_end_s"] = None if cur["data"] is None else round(cur["data"] - cur["m0"], 2)
            recs.append(r)
            cur["on"] = False

    def w_mark(k, t):
        if k == "data" and cur.get("on"):
            cur["data"] = clock()
        return mark(k, t)

    def w_pass(m):
        before = {k: eng.counts.get(k, 0) for k in COUNTERS}
        env.peak(True)
        t0 = eng._timer()
        try:
            return tpass(m)
        finally:
            dt = round(eng._timer() - t0, 3)
            peak = env.peak(False)
            if cur.get("on"):
                inc = {k: eng.counts.get(k, 0) - before[k] for k in COUNTERS}
                err = getattr(eng, "_tb_err", None)
                text = str(err)[:200] if err and inc["tb_fb_error"] > 0 else None
                bars = {}
                tc = getattr(eng, "trades_coins", None)
                for c in ["BTC"] + list(eng.coins):
                    if tc is not None and c not in tc:
                        continue
                    if env.trusted(c, m):
                        bars[c] = env.row(c, m)
                r = dict(minute=cur["minute"], workers=cur["workers"], pass_s=dt, pass_text=f"{dt:.3f}")
                r.update(inc)
                r.update(peak=peak, limited=inc["tb_fb_limited"] > 0,
                         refused=inc["tb_fb_error"] > 0 and bool(text and REFUSAL_RX.search(text)), err=text,
                         _bars=bars, _pass_minute=minute_key(m))
                cur["rec"] = r
    eng.step, eng._mark, eng.trades_pass = w_step, w_mark, w_pass
    return recs


def median_text(texts):
    v = sorted(Decimal(t) for t in texts)
    n = len(v)
    if not n:
        return None
    return format(v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2, "f")


def arm_stats(steps):
    out = {}
    for w in (1, 3):
        timed = [s for s in steps if s["workers"] == w and s["pass_s"] is not None]
        xs = [s["pass_s"] for s in timed]
        out[str(w)] = dict(
            steps_timed=len(timed), pass_median_text=median_text([s["pass_text"] for s in timed]),
            pass_mean_s=(sum(xs) / len(xs)) if xs else None, pass_longest_s=max(xs) if xs else None,
            slow_over_6s=sum(1 for x in xs if x > SLOW_S), fb_budget=sum(s["tb_fb_budget"] for s in timed),
            fb_limited=sum(s["tb_fb_limited"] for s in timed), fb_error=sum(s["tb_fb_error"] for s in timed),
            fb_unverified=sum(s["tb_fb_unverified"] for s in timed),
            peak_max=max((s["peak"] for s in timed if s["peak"] is not None), default=None),
            limited_steps=sum(1 for s in timed if s["limited"]), refused_steps=sum(1 for s in timed if s["refused"]),
            rows_compared=0, rows_differ=0)
    return out


def compare_rows(env, recs, arms, clock=time.time, sleep=time.sleep):
    """Compare the recorded bars with the venue's candles; adds to arms[...]['rows_compared'/'rows_differ'].
    Returns (rows_complete, reason or None)."""
    minutes = sorted({s["_pass_minute"] for s in recs if s["_pass_minute"]})
    if not minutes:
        return True, None
    wait_until = key_epoch(minutes[-1]) + 180
    while clock() < wait_until:
        sleep(min(5.0, max(0.0, wait_until - clock())) or 0.01)
    keep = set(minutes[:-3])
    if not keep:
        return True, None
    lo, hi = min(keep), max(keep)
    end = epoch_key(key_epoch(hi) + 60)
    coins = []
    for s in recs:
        for c in s["_bars"]:
            if c not in coins:
                coins.append(c)
    for c in coins:
        mine = [(s["_pass_minute"], s["workers"], s["_bars"][c]) for s in recs if c in s["_bars"] and s["_pass_minute"] in keep]
        if not mine:
            continue
        try:
            cd = env.candles(c, lo, end)
        except Exception as err:
            return False, f"{c}: {type(err).__name__}: {err}"[:200]
        for k, w, bar in mine:
            a = arms[str(w)]
            a["rows_compared"] += 1
            v = cd.get(k)
            if bar is None:
                a["rows_differ"] += 1 if v is not None else 0
            elif v is None or any(float(x) != float(y) for x, y in zip(bar, v)):
                a["rows_differ"] += 1
    return True, None


def read_events(state_dir):
    out = []
    try:
        for line in open(os.path.join(state_dir, "events.jsonl"), encoding="utf-8", errors="replace"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e, dict) and e.get("kind") in ("error", "warning", "halt"):
                msg = e.get("msg") or e.get("message") or e.get("error") or ""
                out.append(dict(ts=e.get("ts"), kind=e["kind"], message=str(msg)[:200]))
    except OSError:
        pass
    return out


def job(code_dir, first, minutes, out, factory=make_env, start=None, clock=time.time, sleep=time.sleep):
    """Run one job and write its result file; returns the result dict. Never raises."""
    start = start or now_utc()
    res = dict(utc_start=iso(start), utc_end=None, minutes=minutes, code_commit=None, first=first, steps=[], arms={},
               rows_complete=False, rows_reason=None, events=[], counts=False, why_not=None)
    try:
        res["code_commit"] = git_commit(code_dir)
        if first not in ("one", "three"):
            raise NoJob(f"first must be one or three, not {first!r}")
        state = os.path.join(tempfile.mkdtemp(prefix="workers_alt_"), "s")
        env = factory(code_dir, state)
        recs = instrument(env, first, clock)
        env.eng.run(minutes)
        res["events"] = read_events(env.state_dir)
        arms = arm_stats(recs)
        res["arms"] = arms
        res["steps"] = [dict({k: v for k, v in s.items() if not k.startswith("_")}, bars_built=sum(1 for b in s["_bars"].values() if b is not None),
                             bars_empty=sum(1 for b in s["_bars"].values() if b is None)) for s in recs]
        try:
            res["rows_complete"], res["rows_reason"] = compare_rows(env, recs, arms, clock, sleep)
        except Exception as err:
            res["rows_complete"], res["rows_reason"] = False, f"comparison failed: {type(err).__name__}: {err}"[:200]
        short = [w for w in ("1", "3") if arms[w]["steps_timed"] < MIN_STEPS]
        if short:
            res["why_not"] = "; ".join(f"the {w}-worker arm has {arms[w]['steps_timed']} timed steps, {MIN_STEPS} needed" for w in short)
        else:
            res["counts"] = True
    except NoJob as exc:
        res["why_not"] = str(exc)
    except Exception as exc:
        res["why_not"] = f"failed: {type(exc).__name__}: {exc}"[:300]
    res["counts"] = bool(res["counts"]) and res["why_not"] is None
    res["utc_end"] = iso(now_utc())
    try:
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, "alt_" + start.strftime("%Y%m%dT%H%M") + "Z.json")
        with open(path, "w") as f:
            json.dump(res, f, indent=1)
            f.write("\n")
        print(f"alt result: {path}: counts {res['counts']}" + ("" if res["counts"] else f", {res['why_not']}"))
    except Exception as exc:
        print("could not write the result file:", repr(exc))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--first", required=True)
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--out", default=os.path.join("reports", "owner", "workers_alt"))
    a = ap.parse_args(argv)
    try:
        job(a.code, a.first, a.minutes, a.out)
    except Exception as exc:                       # never fails the job
        print("run_alt failed:", repr(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
