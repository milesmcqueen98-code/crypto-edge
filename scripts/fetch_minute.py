#!/usr/bin/env python3
"""1-minute Coinbase candles for one coin over a date range (fixed 300-minute windows, so gaps
with no trades never stop the walk). Writes data/minute/<COIN>.parquet (ts, open, high, low, close, volume; float32).
Usage: python scripts/fetch_minute.py BTC 2024-01-01 2026-11-06"""
import os
import sys
import time

import ccxt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_MS = 60_000


def main(coin, start, end):
    ex = ccxt.coinbaseexchange({"enableRateLimit": True, "timeout": 30_000})
    ex.load_markets()
    sym = f"{coin}/USD"
    if sym not in ex.markets:
        print(f"{coin}: {sym} not listed on Coinbase spot; skipping")
        return
    s = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    e = int(pd.Timestamp(end, tz="UTC").timestamp() * 1000)
    rows, n_req, t0 = {}, 0, time.time()
    while s < e:
        for attempt in range(6):
            try:
                batch = ex.fetch_ohlcv(sym, "1m", since=s, limit=300)
                break
            except ccxt.BaseError as err:
                time.sleep(1 + 2 * attempt)
                batch = []
        for r in batch:
            rows[r[0]] = r
        s += 300 * MIN_MS
        n_req += 1
        if n_req % 500 == 0:
            print(f"{coin}: {n_req} requests, {len(rows)} minutes, {time.time() - t0:.0f}s", flush=True)
    df = pd.DataFrame([rows[k] for k in sorted(rows)], columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    out = df[["ts", "open", "high", "low", "close", "volume"]].astype({c: np.float32 for c in ["open", "high", "low", "close", "volume"]})
    os.makedirs(os.path.join(ROOT, "data", "minute"), exist_ok=True)
    out.to_parquet(os.path.join(ROOT, "data", "minute", f"{coin}.parquet"), index=False, compression="zstd")
    print(f"{coin}: {len(out)} minutes {out.ts.min()} -> {out.ts.max()} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
