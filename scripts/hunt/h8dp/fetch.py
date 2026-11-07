#!/usr/bin/env python3
"""H8 (depeg bids) data fetch, run on GitHub Actions (reports/hunt/h8dp/SPEC.md).

  python scripts/hunt/h8dp/fetch.py discover
      Coinbase Exchange /products: every stablecoin-like or wrapped pair (any status, incl. delisted), with the
      fx_stablecoin / high_bid_limit_percentage / quote_increment fields -> data/hunt/h8dp/products.json
  python scripts/hunt/h8dp/fetch.py candles <PRODUCT> <start> <end> [tag]
      1-minute candles in fixed 300-minute windows (so no-trade gaps never stop the walk), after locating the first
      and last traded day inside [start, end) with daily candles -> data/hunt/h8dp/candles/<PRODUCT>[_tag].parquet
Exchange API: https://api.exchange.coinbase.com ; ~8 requests/second per runner (public limit 10).
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, "data", "hunt", "h8dp")
EX = "https://api.exchange.coinbase.com"
RATE = float(os.environ.get("RATE", "8"))
S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"
_last = [0.0]
N_REQ = [0]

STABLE_BASES = {"USDT", "DAI", "PYUSD", "GUSD", "USDS", "EURC", "USDC", "BUSD", "UST", "USDP", "PAX", "TUSD", "MUSD",
                "RAI", "GYEN", "FEI", "LUSD", "FRAX", "USDE", "RLUSD", "USD1", "FDUSD", "SUSD", "ALUSD", "MIM",
                "CUSD", "USDD", "XSGD", "EUROC", "AUSD", "USDG", "GHO", "CRVUSD", "SUSDE", "USDB", "USR"}
WRAPPED_BASES = {"CBETH", "CBBTC", "WBTC", "STETH", "WSTETH", "RETH", "LSETH", "WETH", "CBDOGE", "CBXRP", "CBSOL",
                 "CBADA", "CBLTC", "TBTC", "LBTC", "CBMETH"}


def get(path, params=None):
    for a in range(10):
        w = _last[0] + 1.0 / RATE - time.time()
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
        N_REQ[0] += 1
        try:
            r = S.get(EX + path, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(1.0 + a)
                continue
            if r.status_code == 404:
                return None
            if r.status_code == 400:
                print("400", path, params, r.text[:200], flush=True)
                return []
            r.raise_for_status()
            return r.json()
        except requests.RequestException as err:
            if a == 9:
                raise
            print("retry", path, repr(err)[:120], flush=True)
            time.sleep(1.0 + a)
    return []


def iso(t):
    return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%SZ")


def discover():
    js = get("/products") or []
    keep = []
    for p in js:
        b = str(p.get("base_currency", "")).upper()
        if b in STABLE_BASES or b in WRAPPED_BASES or p.get("fx_stablecoin") or b.startswith("CB"):
            keep.append(p)
    keep.sort(key=lambda p: p["id"])
    out = {"n_products": len(js), "pairs": keep,
           "fx_stablecoin_ids": sorted(p["id"] for p in js if p.get("fx_stablecoin")),
           "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    # first and last traded day of every USD (and USDC/ETH/BTC-quoted wrapped) pair found, from daily candles
    spans = {}
    for p in keep:
        if p["quote_currency"] not in ("USD", "USDC", "ETH", "BTC"):
            continue
        d = daily(p["id"], "2015-01-01", "2026-11-07")
        if len(d):
            spans[p["id"]] = dict(first=str(d.ts.min().date()), last=str(d.ts.max().date()), days=int(len(d)),
                                  min_low=float(d.low.min()), max_high=float(d.high.max()),
                                  usd_vol_median=float((d.volume * d.close).median()))
        else:
            spans[p["id"]] = None
    out["spans"] = spans
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "products.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    for p in keep:
        print(p["id"], p.get("status"), "fx" if p.get("fx_stablecoin") else "", p.get("quote_increment"),
              p.get("high_bid_limit_percentage"), spans.get(p["id"]), flush=True)
    print("requests", N_REQ[0])


def daily(pid, start, end):
    rows = {}
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    while s < e:
        t1 = min(s + pd.Timedelta(days=299), e)
        js = get(f"/products/{pid}/candles", {"granularity": 86400, "start": iso(s), "end": iso(t1)})
        if js is None:
            return pd.DataFrame(columns=["ts", "low", "high", "open", "close", "volume"])
        for r in js or []:
            rows[r[0]] = r
        s = s + pd.Timedelta(days=300)
    d = pd.DataFrame([rows[k] for k in sorted(rows)], columns=["ts", "low", "high", "open", "close", "volume"])
    d["ts"] = pd.to_datetime(d["ts"], unit="s")
    return d


def candles(pid, start, end, tag=""):
    t0 = time.time()
    d = daily(pid, start, end)
    d = d[d.volume > 0]
    if d.empty:
        print(f"{pid}: no daily candles in {start} .. {end}")
        return
    s = max(pd.Timestamp(start), d.ts.min())
    e = min(pd.Timestamp(end), d.ts.max() + pd.Timedelta(days=1))
    print(f"{pid}: traded days {d.ts.min().date()} .. {d.ts.max().date()} ({len(d)} days); fetching {s} .. {e}",
          flush=True)
    rows = {}
    while s < e:
        t1 = s + pd.Timedelta(minutes=299)
        js = get(f"/products/{pid}/candles", {"granularity": 60, "start": iso(s), "end": iso(t1)})
        for r in js or []:
            rows[r[0]] = r
        s = s + pd.Timedelta(minutes=300)
        if N_REQ[0] % 1000 == 0:
            print(f"{pid}: {N_REQ[0]} requests, {len(rows)} minutes, at {s}, {time.time() - t0:.0f}s", flush=True)
    df = pd.DataFrame([rows[k] for k in sorted(rows)], columns=["ts", "low", "high", "open", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="s")
    df = df[(df.ts >= pd.Timestamp(start)) & (df.ts < pd.Timestamp(end))]
    df = df[["ts", "open", "high", "low", "close", "volume"]].astype(
        {"open": np.float64, "high": np.float64, "low": np.float64, "close": np.float64, "volume": np.float32})
    d_out = os.path.join(OUT, "candles", pid)
    os.makedirs(d_out, exist_ok=True)
    for y, g in df.groupby(df.ts.dt.year):                       # one file per year keeps every file well under 50 MB
        g.to_parquet(os.path.join(d_out, f"{y}{('_' + tag) if tag else ''}.parquet"), index=False, compression="zstd")
    print(f"{pid}: {len(df)} minutes {df.ts.min()} .. {df.ts.max()}, {N_REQ[0]} requests, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    if sys.argv[1] == "discover":
        discover()
    elif sys.argv[1] == "candles":
        candles(*sys.argv[2:6])
