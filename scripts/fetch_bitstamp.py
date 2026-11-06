#!/usr/bin/env python3
"""1-minute Bitstamp candles (New York BitLicense venue) for one coin over a date range.
Writes data/bitstamp/<COIN>.parquet (ts, open, high, low, close, volume; float32). Skips coins Bitstamp doesn't list.
Usage: python scripts/fetch_bitstamp.py SOL 2024-01-01 2026-11-06
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://www.bitstamp.net/api/v2"
UA = {"User-Agent": "crypto-edge-research/1.0"}


def get(url, params=None, tries=6):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (i + 1))
                continue
            return None
        except requests.RequestException:
            time.sleep(2 * (i + 1))
    return None


def main(coin, start, end):
    pair = f"{coin.lower()}usd"
    info = get(f"{API}/trading-pairs-info/") or []
    pairs = {p.get("url_symbol") for p in info}
    if pair not in pairs:
        print(f"{coin}: {pair} not listed on Bitstamp; skipping")
        return
    s = int(pd.Timestamp(start, tz="UTC").timestamp())
    e = int(pd.Timestamp(end, tz="UTC").timestamp())
    rows, n = {}, 0
    while s < e:
        js = get(f"{API}/ohlc/{pair}/", params=dict(step=60, limit=1000, start=s))
        data = (js or {}).get("data", {}).get("ohlc", [])
        for r in data:
            rows[int(r["timestamp"])] = r
        s += 1000 * 60
        n += 1
        if n % 200 == 0:
            print(f"{coin}: {n} requests, {len(rows)} minutes", flush=True)
        time.sleep(0.08)
    if not rows:
        print(f"{coin}: no data")
        return
    df = pd.DataFrame(rows.values())
    df["ts"] = pd.to_datetime(df.timestamp.astype(int), unit="s")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float).astype(np.float32)
    df = df[["ts", "open", "high", "low", "close", "volume"]].drop_duplicates("ts").sort_values("ts")
    df = df[(df.ts >= pd.Timestamp(start)) & (df.ts < pd.Timestamp(end))]
    os.makedirs(os.path.join(ROOT, "data", "bitstamp"), exist_ok=True)
    df.to_parquet(os.path.join(ROOT, "data", "bitstamp", f"{coin}.parquet"), index=False)
    print(f"{coin}: saved {len(df)} minutes {df.ts.min()} .. {df.ts.max()}, volume>0 in {(df.volume > 0).mean():.0%}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
