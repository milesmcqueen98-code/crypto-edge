"""Step probe: how early after a minute closes does the venue's trades list hold that minute completely?

Plan: reports/owner/step_probe_prereg.md (fixed before any data). This script only records; it reads no P&L.

Run: python scripts/owner/step_probe/probe.py --minutes 300 --out reports/owner/step_probe/run1
         [--early-at 1.0] [--standard-at 6.0] [--ref-at 35.0]

For each whole UTC minute boundary q (m = q - 60 s is the minute that closed at q) three passes of one request after
another over the symbols, all through bot.market.minute_trades_bar (the engine's own check) and bot.market._get_h
(the engine's own pace, at most TRADES_RATE a second):
  early      starts at q + early-at, minute m, BTC first then the other 17 rotated by one place per minute
  standard   starts at q + standard-at (or when the early pass ends if later), minute m, same order
  reference  starts at q + ref-at, minute m - 60 s, list order
and after the last q one more reference pass for the last m. A pass that has not started by q + 55 s is skipped
and counted. A refusal or a rate-limit answer ends the run at once (exit code 0, rows kept).

Raw trades never leave the runner: only the derived bar and the facts of each call are written.
"""
import argparse
import csv
import json
import math
import os
import sys
import time
import traceback
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd     # noqa: E402

SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "LINK", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE",
           "ENA", "PEPE", "ONDO", "ZEC"]
COLUMNS = ["q", "minute", "pass", "place", "coin", "sent_s", "dur_s", "verified", "reason", "pages", "gen_s", "age",
           "n", "open", "high", "low", "close", "volume", "error"]
LATEST_START_S = 55.0           # a pass that has not started by q + 55 s is skipped
MAX_ERRORS_IN_A_ROW = 40
ERROR_TEXT_CHARS = 200


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp(t):
    """The naive UTC pandas timestamp of an epoch second, the form bot.market works in."""
    return pd.Timestamp(int(t), unit="s")


def fix3(x):
    return f"{x:.3f}"


def max_in_window(times, width=1.0):
    """The largest number of send times inside any window (t - width, t]."""
    ts = sorted(times)
    best, j = 0, 0
    for i, t in enumerate(ts):
        while ts[j] <= t - width:
            j += 1
        best = max(best, i - j + 1)
    return best


def make_get(market, info, sends):
    """A thin wrapper around market._get_h for one call. It returns _get_h's result unchanged. On the first page of
    the call it notes the send time (market._last_req[0], which _get_h sets just before sending) and the Date and
    Age headers of the reply. Every page's send time goes to sends (for the pace record)."""
    def get(url, params=None):
        first = info["pages"] == 0
        info["pages"] += 1
        try:
            out = market._get_h(url, params)
        finally:
            sent = market._last_req[0]
            sends.append(sent)
            if first:
                info["sent"] = sent
        if first:
            hd = out[1] or {}
            info["date"] = hd.get("Date")
            age = hd.get("Age")
            info["age"] = None if age is None else str(age)
        return out
    return get


def do_call(st, coin, q, minute, pname, place):
    """One call (one coin, one minute, one pass). Returns (row, error). error is None or the exception raised."""
    mk = st["market"]
    info = {"pages": 0, "sent": None, "date": None, "age": None}
    get = make_get(mk, info, st["sends"])
    row = {c: "" for c in COLUMNS}
    row.update({"q": iso(q), "minute": iso(minute), "pass": pname, "place": place, "coin": coin})
    t_before = st["clock"]()
    err = None
    try:
        res = mk.minute_trades_bar(coin, stamp(minute), get=get)
        verified = bool(res["verified"])
        row["verified"] = 1 if verified else 0
        row["reason"] = "" if verified else (res["reason"] or "unspecified")
        row["pages"] = res["pages"]
        if res["gen"] is not None:
            row["gen_s"] = fix3((pd.Timestamp(res["gen"]) - stamp(q)).total_seconds())
        row["n"] = res["n"]
        bar = res["bar"]
        if bar is not None:
            for k in ("open", "high", "low", "close", "volume"):
                row[k] = repr(float(bar[k]))
    except Exception as exc:
        err = exc
        row["verified"] = 0
        row["reason"] = "error"
        row["pages"] = info["pages"]
        row["error"] = (str(exc) or type(exc).__name__)[:ERROR_TEXT_CHARS]
    row["dur_s"] = fix3(st["clock"]() - t_before)
    if info["sent"] is not None:
        row["sent_s"] = fix3(info["sent"] - q)
    if info["age"] is not None:
        row["age"] = info["age"]
    return row, err


def append_rows(path, rows):
    """Open, append, close: a killed run keeps every finished pass."""
    if not rows:
        return
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        for r in rows:
            w.writerow(r)


def write_run_json(st):
    doc = {
        "args": st["args"],
        "started": iso(st["t0"]),
        "q_done": st["q_done"],
        "final_reference_done": st["final_done"],
        "calls_by_pass": st["calls"],
        "skipped_passes": st["skipped"],
        "stopped": st["stopped"],
        "stopped_message": st["stopped_msg"],
        "trades_rate": st["market"].TRADES_RATE,
        "python": sys.version,
        "requests_sent": len(st["sends"]),
        "max_requests_in_one_second": max_in_window(st["sends"]),
    }
    path = os.path.join(st["out"], "run.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def wait_until(clock, sleep, t):
    while True:
        now = clock()
        if now >= t:
            return
        sleep(t - now)


def run_pass(st, pname, q, minute, coins, start_at):
    """One pass. Returns "done", "skipped" or "stopped". A pass whose start cannot be met by q + 55 s is skipped."""
    limit = q + LATEST_START_S
    if start_at > limit:
        st["skipped"][pname] += 1
        return "skipped"
    wait_until(st["clock"], st["sleep"], start_at)
    if st["clock"]() > limit:
        st["skipped"][pname] += 1
        return "skipped"
    rows = []
    mk = st["market"]
    try:
        for place, coin in enumerate(coins):
            row, err = do_call(st, coin, q, minute, pname, place)
            rows.append(row)
            st["calls"][pname] += 1
            if err is None:
                st["consec"] = 0
                continue
            if isinstance(err, mk.Refused):
                st["stopped"] = "limited" if isinstance(err, mk.Limited) else "refused"
                st["stopped_msg"] = row["error"]
                return "stopped"
            st["consec"] += 1
            if st["consec"] >= MAX_ERRORS_IN_A_ROW:
                st["stopped"] = "errors"
                st["stopped_msg"] = f"{st['consec']} calls in a row ended in an error; last: {row['error']}"
                return "stopped"
    finally:
        append_rows(st["calls_path"], rows)
    return "done"


def run(args, market, clock, sleep, out_dir):
    """The whole probe. market is bot.market (or a fake with minute_trades_bar, _get_h, _last_req, TRADES_RATE,
    Refused, Limited); clock() is the UTC time as a float epoch; sleep(seconds) waits. Returns the exit code."""
    os.makedirs(out_dir, exist_ok=True)
    calls_path = os.path.join(out_dir, "calls.csv")
    if os.path.exists(calls_path) and os.path.getsize(calls_path) > 0:
        raise FileExistsError(f"{calls_path} already exists: a run never overwrites another run's rows")
    with open(calls_path, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=COLUMNS).writeheader()
    t0 = clock()
    q0 = int(math.ceil((t0 + 5.0) / 60.0)) * 60            # first boundary at least 5 s after the start
    qs = [q0 + 60 * i for i in range(args.minutes)]
    st = {"market": market, "clock": clock, "sleep": sleep, "out": out_dir, "calls_path": calls_path, "t0": t0,
          "args": dict(vars(args)), "q_done": [], "final_done": False, "sends": [], "consec": 0,
          "calls": {"early": 0, "standard": 0, "reference": 0},
          "skipped": {"early": 0, "standard": 0, "reference": 0}, "stopped": None, "stopped_msg": None}
    write_run_json(st)
    others = SYMBOLS[1:]
    for i, q in enumerate(qs):
        m = q - 60
        k = i % len(others)
        order = [SYMBOLS[0]] + others[k:] + others[:k]      # BTC first, the other 17 moved on by one place each minute
        plan = (("early", q + args.early_at, m, order),
                ("standard", q + args.standard_at, m, order),
                ("reference", q + args.ref_at, m - 60, SYMBOLS))
        for pname, start_at, minute, coins in plan:
            if run_pass(st, pname, q, minute, coins, start_at) == "stopped":
                write_run_json(st)
                return 0
        st["q_done"].append(iso(q))
        write_run_json(st)
    if qs:
        q = qs[-1] + 60                                     # one more reference pass, for the last m
        if run_pass(st, "reference", q, qs[-1] - 60, SYMBOLS, q + args.ref_at) == "stopped":
            write_run_json(st)
            return 0
        st["final_done"] = True
    write_run_json(st)
    return 0


def guarded_run(args, market, clock, sleep, out_dir):
    """run() with a guard: an exception that escapes run() must not lose the rows already written (hunt2.yml skips
    its commit step on a non-zero exit). It writes OUT/crash.json (type, text, the last 2000 characters of the
    traceback, the UTC time), prints the traceback to stderr and returns 0. KeyboardInterrupt and SystemExit are not
    caught. An existing calls.csv is refused before the guard: that raises FileExistsError (non-zero exit), so a run
    that never started cannot look successful."""
    calls_path = os.path.join(out_dir, "calls.csv")
    if os.path.exists(calls_path) and os.path.getsize(calls_path) > 0:
        raise FileExistsError(f"{calls_path} already exists: a run never overwrites another run's rows")
    try:
        return run(args, market, clock, sleep, out_dir)
    except Exception as exc:
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        doc = {"type": type(exc).__name__, "text": str(exc), "traceback_tail": tb[-2000:],
               "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "crash.json"), "w") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")
        return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--minutes", type=int, default=300)
    ap.add_argument("--out", required=True)
    ap.add_argument("--early-at", dest="early_at", type=float, default=1.0)
    ap.add_argument("--standard-at", dest="standard_at", type=float, default=6.0)
    ap.add_argument("--ref-at", dest="ref_at", type=float, default=35.0)
    args = ap.parse_args(argv)
    if args.minutes < 1:
        ap.error("--minutes must be at least 1")
    for name in ("early_at", "standard_at", "ref_at"):
        if not 0.0 <= getattr(args, name) <= LATEST_START_S:
            ap.error(f"--{name.replace('_', '-')} must be between 0 and {LATEST_START_S:g}")
    import bot.market as market
    return guarded_run(args, market, time.time, time.sleep, args.out)


if __name__ == "__main__":
    sys.exit(main())
