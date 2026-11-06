#!/usr/bin/env python3
"""Daily Hyperliquid perpetual-futures closes (for basis P&L in carry backtests).
Writes data/perps/<BASE>.csv with date,close for every coin that has a funding file."""
import os
import time

import ccxt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "perps")
DAY_MS = 86_400_000


def main():
    os.makedirs(OUT, exist_ok=True)
    hl = ccxt.hyperliquid({"enableRateLimit": True, "timeout": 30_000})
    hl.load_markets()
    bases = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "data", "funding")))
    for base in ["BTC", "ETH"] + [b for b in bases if b not in ("BTC", "ETH")]:
        sym = f"{base}/USDC:USDC"
        if sym not in hl.markets:
            continue
        rows, since = {}, int(pd.Timestamp("2023-05-01", tz="UTC").timestamp() * 1000)
        for _ in range(20):
            try:
                batch = hl.fetch_ohlcv(sym, "1d", since=since, limit=500)
            except ccxt.BaseError as e:
                print(f"{base}: {type(e).__name__}", flush=True)
                time.sleep(3)
                continue
            if not batch:
                break
            for r in batch:
                rows[r[0]] = r
            last = batch[-1][0]
            if last + DAY_MS >= time.time() * 1000 or len(batch) < 2:
                break
            since = last + 1
        if not rows:
            continue
        df = pd.DataFrame([rows[k] for k in sorted(rows)], columns=["ts", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.normalize()
        df = df[df["date"] < pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()]
        df[["date", "close"]].to_csv(os.path.join(OUT, f"{base}.csv"), index=False, date_format="%Y-%m-%d")
        print(f"{base}: {len(df)} days {df.date.min().date()} -> {df.date.max().date()}", flush=True)


if __name__ == "__main__":
    main()
