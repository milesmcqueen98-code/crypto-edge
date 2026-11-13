#!/usr/bin/env python3
"""Weekly perp paper check (Nov 13 2026): final Coinbase spot and perp 1-minute candles for the coins the perp
paper books bid on, so each paper fill can be checked against spot. Writes data/pcheck/<COIN>.parquet (spot) and
data/pcheck/<COIN>_perp.parquet (perp, volume in contracts). Run on a GitHub runner (the research workspace cannot
reach the exchange). Usage: python scripts/pcheck/fetch.py COIN,COIN,... START END"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import fetch_cfm  # noqa: E402
import fetch_minute  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))


def main(coins, start, end):
    out = os.path.join(ROOT, "data", "pcheck")
    os.makedirs(out, exist_ok=True)
    for c in coins.split(","):
        fetch_minute.main(c, start, end, "pcheck")
        fetch_cfm.mode_candles(c, start)
        p = os.path.join(ROOT, "data", "cfm", f"{c}.parquet")
        if os.path.exists(p):
            os.replace(p, os.path.join(out, f"{c}_perp.parquet"))


if __name__ == "__main__":
    main(*sys.argv[1:4])
