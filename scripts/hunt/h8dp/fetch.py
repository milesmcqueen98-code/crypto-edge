#!/usr/bin/env python3
"""H8 (depeg bids) data fetch, run on GitHub Actions (reports/hunt/h8dp/SPEC.md).

  python scripts/hunt/h8dp/fetch.py discover
      Coinbase Exchange /products: every stablecoin-like or wrapped pair (any status, incl. delisted), with the
      fx_stablecoin / high_bid_limit_percentage / quote_increment fields -> data/hunt/h8dp/products.json
  python scripts/hunt/h8dp/fetch.py candles <PRODUCT,start,end> [<PRODUCT,start,end> ...]
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
        s = s + pd.Timedelta(days=299)                          # step 299 with end = start + 299: no gap either way
    d = pd.DataFrame([rows[k] for k in sorted(rows)], columns=["ts", "low", "high", "open", "close", "volume"])
    d["ts"] = pd.to_datetime(d["ts"], unit="s")
    return d


def candles(pid, start, end, tag=""):
    tag = tag or pd.Timestamp(start).strftime("%Y%m%d")
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
        s = s + pd.Timedelta(minutes=299)                       # end inclusive or exclusive: no minute is skipped
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


def trades_probe():
    """Which trade source serves old and delisted stable-pair prints: Advanced market-trades (common.TradeFetcher)
    vs the Exchange trade-id cursor. Prints counts only."""
    sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
    import common
    tf = common.TradeFetcher()
    res = {}
    for pid, s, e in [("USDT-USD", "2022-05-12 01:00", "2022-05-12 01:10"), ("DAI-USD", "2023-03-11 06:00", "2023-03-11 06:10"),
                      ("GUSD-USD", "2023-03-11 06:00", "2023-03-11 07:00"), ("PYUSD-USD", "2024-06-01 00:00", "2024-06-01 06:00"),
                      ("USDS-USD", "2025-10-10 21:00", "2025-10-10 22:00"), ("CBETH-USD", "2022-11-09 00:00", "2022-11-09 00:30"),
                      ("UST-USD", "2022-05-09 20:00", "2022-05-09 20:10"), ("USDT-USD", "2026-05-01 00:00", "2026-05-01 00:05")]:
        t0 = time.time()
        try:
            d = tf.window(pid, s, e)
            adv = dict(n=len(d), first=str(d.time.min()) if len(d) else None, last=str(d.time.max()) if len(d) else None,
                       sides=d.side.value_counts().to_dict() if len(d) else {}, secs=round(time.time() - t0, 1))
        except Exception as err:  # noqa: BLE001
            adv = dict(error=repr(err)[:200])
        t0 = time.time()
        try:
            newest = get(f"/products/{pid}/trades", {"limit": 1})
            exch = dict(newest=newest[:1] if newest else newest, secs=round(time.time() - t0, 1))
            if newest:
                old = get(f"/products/{pid}/trades", {"limit": 5, "after": 1000})
                exch["after_1000"] = old[:2] if old else old
        except Exception as err:  # noqa: BLE001
            exch = dict(error=repr(err)[:200])
        res[f"{pid} {s}"] = dict(advanced=adv, exchange=exch)
        print(pid, s, json.dumps(res[f"{pid} {s}"], default=str)[:600], flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "trades_probe.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)


def exchange_all(pid):
    """Every trade of a (small, delisted) product via the Exchange trade-id cursor (newest -> oldest). Used where the
    Advanced market-trades endpoint (common.TradeFetcher) returns 404: products delisted before ~mid-2025."""
    t0, rows, cur = time.time(), [], None
    while True:
        js = get(f"/products/{pid}/trades", {"limit": 1000, **({"after": cur} if cur else {})})
        if not js:
            break
        rows += [(int(t["trade_id"]), t["time"], float(t["price"]), float(t["size"]), t["side"]) for t in js]
        cur = min(int(t["trade_id"]) for t in js)
        if cur <= 1 or len(js) < 1000:
            break
        if N_REQ[0] % 200 == 0:
            print(pid, N_REQ[0], len(rows), js[-1]["time"], flush=True)
    d = pd.DataFrame(rows, columns=["trade_id", "time", "price", "size", "side"]).drop_duplicates("trade_id")
    d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.tz_convert(None)
    # Exchange /trades `side` is the MAKER side, as on the Advanced endpoint (checked by tick test on GUSD/PYUSD:
    # "buy" prints are down-ticks). Upper-case it to the common convention ("BUY" = resting bid hit by a seller).
    d["side"] = d["side"].str.upper()
    d = d.sort_values(["time", "trade_id"]).reset_index(drop=True)
    os.makedirs(os.path.join(OUT, "trades_all"), exist_ok=True)
    d.to_parquet(os.path.join(OUT, "trades_all", f"{pid}.parquet"), index=False, compression="zstd")
    print(f"{pid}: {len(d)} trades {d.time.min()} .. {d.time.max()}, {N_REQ[0]} requests, {time.time() - t0:.0f}s")


def advlist():
    """Advanced Trade public product list: any cbBTC / cbETH / wrapped product ids (spot and futures)."""
    r = S.get("https://api.coinbase.com/api/v3/brokerage/market/products", params={"limit": 5000}, timeout=60)
    js = r.json().get("products", [])
    hits = [p for p in js if any(k in (p.get("product_id", "") + p.get("base_display_symbol", "")).upper()
                                 for k in ("CBBTC", "CBETH", "WBTC", "LSETH"))]
    out = {"status": r.status_code, "n_products": len(js),
           "hits": [{k: p.get(k) for k in ("product_id", "status", "product_type", "quote_currency_id",
                                             "trading_disabled", "is_disabled", "new_at", "volume_24h")} for p in hits]}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "advanced_wrapped.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, default=str)[:3000])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "advlist":
        advlist()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "xall":
        for pid in sys.argv[2:]:
            exchange_all(pid)
        sys.exit(0)
    if sys.argv[1] == "discover":
        discover()
    elif sys.argv[1] == "candles":
        for spec in sys.argv[2:]:                               # PRODUCT:START:END ...
            pid, s, e = spec.split(",")
            candles(pid, s, e)
    elif sys.argv[1] == "tprobe":
        trades_probe()
