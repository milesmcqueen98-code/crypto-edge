#!/usr/bin/env python3
"""Hourly Coinbase candles for the majors (full history, walked backward from now).
Writes data/hourly/<BASE>.csv.gz with ts (UTC hour start), open, high, low, close, volume."""
import os
import sys
import time

import ccxt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "hourly")
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "ADA", "AVAX", "LINK"]
HOUR_MS = 3_600_000
START = pd.Timestamp("2015-07-20", tz="UTC")


def fetch(ex, sym):
    rows = {}
    end = int(time.time() * 1000) // HOUR_MS * HOUR_MS
    window = 300 * HOUR_MS
    since = end - window
    empty = 0
    while since > START.timestamp() * 1000 - window:
        batch = None
        for attempt in range(4):
            try:
                batch = ex.fetch_ohlcv(sym, "1h", since=since, limit=300)
                break
            except ccxt.BaseError as e:
                time.sleep(2 + 3 * attempt)
        if batch:
            empty = 0
            for r in batch:
                rows[r[0]] = r
        else:
            empty += 1
            if empty >= 3:          # three empty windows in a row: before listing
                break
        since -= window
    return [rows[k] for k in sorted(rows)]


def main():
    os.makedirs(OUT, exist_ok=True)
    coins = sys.argv[1:] or COINS
    ex = ccxt.coinbaseexchange({"enableRateLimit": True, "timeout": 30_000})
    ex.load_markets()
    for c in coins:
        sym = f"{c}/USD"
        if sym not in ex.markets:
            print(f"{c}: not listed", flush=True)
            continue
        t0 = time.time()
        rows = fetch(ex, sym)
        if not rows:
            continue
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        df = df[df.ts < pd.Timestamp.now(tz="UTC").tz_localize(None).floor("h")]
        df.to_csv(os.path.join(OUT, f"{c}.csv.gz"), index=False, compression="gzip")
        print(f"{c}: {len(df)} hours {df.ts.min()} -> {df.ts.max()} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
