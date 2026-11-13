#!/usr/bin/env python3
"""Live-path simulation on the release-3 inputs, compared line for line with the candle run. No network, no keys.

Runs bot/spot/live_sim_test.py three times on the same window, in one process, against the same fake exchange set-up:
  A  candle mode, as release 2 tested it;
  B  the input settings of --inputs (default bot/spot/config.json, taken the way the live bot takes them) from the
     start, with a trades feed made from the same candles: every trades bar equals its candle, no answer is old;
  C  candle mode until --switch (default one hour after the start), then a fresh process on B's inputs on the same
     state folder (what wickctl update does on a VM).
Checks: every run passes live_sim_test's own checks; B and C asked the trades feed; the event logs of B and C equal
A's line for line, heartbeats aside, with order ids masked (they are random); C kept its open ladders across the
switch. On a difference it prints the first differing line of each log and does not adjust anything.

Usage: python bot/spot/live_sim_inputs_test.py "2025-10-10 20:00" "2025-10-11 02:00" "--death=2025-10-10 21:10"
       [--inputs=bot/spot/config.json] [--switch=2025-10-10 21:00]
"""
import json
import os
import re
import shutil
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot.spot import live_sim_test as L  # noqa: E402

FAILS = []
HEX = re.compile(r"[0-9a-f]{12,}")


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""), flush=True)
    if not ok:
        FAILS.append(name)


def lines(sd):
    """The event log without heartbeats, order ids masked."""
    out = []
    for x in open(os.path.join(sd, "events.jsonl")):
        e = json.loads(x)
        if e["kind"] != "heartbeat":
            out.append(HEX.sub("<id>", x.strip()))
    return out


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x, y
    return (min(len(a), len(b)), a[len(b)] if len(a) > len(b) else None, b[len(a)] if len(b) > len(a) else None) \
        if len(a) != len(b) else None


def compare(tag, a, b):
    d = first_diff(a, b)
    check(f"{tag}: every log line equals the candle run's (heartbeats aside, order ids masked)", d is None,
          f"{len(b)} vs {len(a)} lines")
    if d is not None:
        print(f"  first difference at line {d[0]}:\n    candle run: {d[1]}\n    {tag}:        {d[2]}", flush=True)


def heartbeats(sd):
    return [json.loads(x) for x in open(os.path.join(sd, "events.jsonl")) if '"kind": "heartbeat"' in x]


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    start, end = a[0], a[1]
    death = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--death=")), None)
    inputs = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--inputs=")),
                  os.path.join(HERE, "config.json"))
    switch = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--switch=")),
                  str(pd.Timestamp(start) + pd.Timedelta(hours=1)))
    src = json.load(open(inputs))
    if src.get("newest_bar") != "trades":
        check(f"{inputs} is on newest_bar trades (nothing to compare otherwise)", False, str(src.get("newest_bar")))
        return
    print(f"=== A: candle mode", flush=True)
    sdA, okA = L.main(start, end, death=death)
    print(f"\n=== B: inputs of {inputs} from the start", flush=True)
    sdB, okB = L.main(start, end, death=death, inputs=inputs)
    print(f"\n=== C: candle mode until {switch}, then the inputs of {inputs}", flush=True)
    sdC, okC = L.main(start, end, death=death, inputs=inputs, switch=switch)
    print(flush=True)
    check("A: live-path checks pass", okA)
    check("B: live-path checks pass", okB)
    check("C: live-path checks pass", okC)
    A, B, C = lines(sdA), lines(sdB), lines(sdC)
    compare("B", A, B)
    fills = lambda x: [y for y in x if '"kind": "fill_' in y]  # noqa: E731
    compare("C, entries and exits", fills(A), fills(C))
    d = first_diff(A, C)
    print(f"  C, whole log (the new process at the switch logs its own start-up): {len(C)} vs {len(A)} lines; "
          + ("identical" if d is None else f"first difference at line {d[0]}:\n    candle run: {d[1]}\n    C:"
                                            f"          {d[2]}"), flush=True)
    sw = L.SWITCH_SEEN
    check("C: the switch happened, with no exception, and the open ladders were kept", sw.get("t") is not None
          and sw.get("before") == sw.get("after"), str(sw))
    for tag, sd in (("B", sdB), ("C", sdC)):
        hb = heartbeats(sd)
        n = sum(h.get("counts", {}).get("tb_built", 0) for h in hb)
        fb = sum(v for h in hb for k, v in h.get("counts", {}).items() if k.startswith("tb_fb"))
        st = sum(h.get("counts", {}).get("btc_stale", 0) for h in hb)
        so = sum(h.get("counts", {}).get("skip_old", 0) for h in hb)
        print(f"  {tag}: heartbeats {len(hb)}; bars built from trades {n}, fallbacks {fb}, btc_stale {st}, "
              f"skip_old {so}", flush=True)
        check(f"{tag}: bars were built from trades", n > 0)
    hA = [{k: v for k, v in h.items() if k != "counts" and k != "step_s"} for h in heartbeats(sdA)]
    hB = [{k: v for k, v in h.items() if k != "counts" and k != "step_s"} for h in heartbeats(sdB)]
    check("B: heartbeats equal A's apart from the counters and step timing", hA == hB)
    if not FAILS:
        for sd in (sdA, sdB, sdC):
            shutil.rmtree(sd, ignore_errors=True)


if __name__ == "__main__":
    main()
    print("LIVE-PATH INPUTS TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
