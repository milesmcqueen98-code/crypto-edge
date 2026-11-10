#!/usr/bin/env python3
"""Follow-up check of the candle clock study (an addition to the plan, logged in reports/owner/candle_clock/README.md
before it ran). In the main run the unexplained boundaries fell on the same minutes for nearly every coin. For a few
coins and those minutes (and one minute either side), this prints the final candle next to the bar of trades stamped
in the minute, and the two-minute and five-minute totals of both. Derived values only; raw trades stay in memory.
Same pace and refusal policy as study.py.

Usage: python scripts/owner/candle_clock/diag.py --coins BTC,ETH,SOL,DOGE --minutes 2026-11-10T12:55,2026-11-10T14:05
"""
import argparse
import os
import sys
import time
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import study as S  # noqa: E402

MIN, US = S.MIN, S.US


def tot(D, a, b):
    """Volume (coin units) of trades stamped in [a, b) and of the candles of those minutes."""
    bar = S.time_bar(D, a, b)
    v_tr = 0 if bar is None else bar[4] / D["scale_s"]
    v_c = sum(D["candles"][m][6] for m in range(a, b, MIN) if m in D["candles"])
    return v_tr, v_c


def main(coins, mins):
    ms = sorted({S.stamp_us(x + ":00Z") for x in mins})
    first, last = ms[0] - 3 * MIN, ms[-1] + 3 * MIN
    for c in coins:
        try:
            tr, info = S.fetch_trades(c, first - 2 * MIN)
        except S.RefusedWith as r:
            print(f"REFUSED trades {c}: {r}")
            return
        try:
            rows, known, ans = S.fetch_candles(c, first, last, last + MIN, [])
        except S.Refused as r:
            print(f"REFUSED candles {c}: {r}")
            return
        D = S.prepare(tr, rows)
        sp, ss = D["scale_p"], D["scale_s"]
        print(f"\n{c}: {info['pages']} pages, id gaps {D['id_gaps']}, stamps out of id order {D['nonmono']}; "
              f"candle answers {[(a['cache'], a['age']) for a in ans]}")
        print("  minute            candle o/h/l/c/v                                  trades-in-minute o/h/l/c/v"
              "                          2-min vol trades/candle   5-min vol trades/candle")
        for m in sorted({x + k * MIN for x in ms for k in (-1, 0, 1)}):
            cd = D["candles"].get(m)
            b = S.time_bar(D, m, m + MIN)
            fc = "-" if cd is None else "/".join(str(x / sp) for x in cd[:4]) + f"/{cd[6]:.6g}"
            fb = "-" if b is None else "/".join(str(x / sp) for x in b[:4]) + f"/{b[4] / ss:.6g}"
            t2 = tot(D, m, m + 2 * MIN)
            t5 = tot(D, m - 2 * MIN, m + 3 * MIN)
            flag = " <" if m in ms else ""
            print(f"  {S.iso(m)[11:16]}  {fc:<50} {fb:<50} {t2[0]:.6g}/{t2[1]:.6g}  {t5[0]:.6g}/{t5[1]:.6g}{flag}")
        del tr, D
        time.sleep(0.2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="BTC,ETH,SOL,DOGE")
    ap.add_argument("--minutes", default="")
    a = ap.parse_args()
    main([x.strip() for x in a.coins.split(",") if x.strip()], [x.strip() for x in a.minutes.split(",") if x.strip()])
