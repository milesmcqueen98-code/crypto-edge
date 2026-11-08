#!/usr/bin/env python3
"""Gemini venue test (reports/gemini_prereg.md): trade-by-trade data for Gemini and Coinbase on the sample days.

Source: Tardis.dev free CSVs (first day of each month, no API key). Runs on GitHub Actions (the research workspace
cannot reach Tardis or Gemini). For each day given:
  - Gemini trades (all USD pairs of the 17 R2-08 coins that Tardis lists that day): every print is kept.
  - Gemini top of book (Tardis "quotes"): reduced to the last bid/ask of each second.
  - Coinbase trades of the same coins: reduced to per-second bars (last, low, high, USD volume, taker-sell USD,
    taker-buy USD), enough for a second-synchronous fair value and the shared/Gemini-only test.
Also saves Tardis's Gemini/Coinbase symbol availability and Gemini's current symbol details (tick, minimum size).

Writes out/gemini/<day>/{gem_trades,gem_quotes,cb_sec}.parquet and out/gemini/meta/*.json.
Usage: python scripts/gemini/fetch_tardis.py 2024-01-01 2024-02-01 ...
"""
import gzip
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

COINS17 = ["ETH", "SOL", "XRP", "DOGE", "LTC", "LINK", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE", "ENA",
           "PEPE", "ONDO", "ZEC"]
DS = "https://datasets.tardis.dev/v1"
API = "https://api.tardis.dev/v1"
OUT = os.path.join("out", "gemini")
UA = {"User-Agent": "crypto-edge-research/1.0"}


def get(url, tries=6, stream=False):
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=120, stream=stream)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None
            print(f"  {r.status_code} {url}", flush=True)
        except requests.RequestException as e:
            print(f"  error {e} {url}", flush=True)
        time.sleep(3 * (i + 1))
    return None


def csv(exchange, kind, day, symbol):
    y, m, d = day.split("-")
    r = get(f"{DS}/{exchange}/{kind}/{y}/{m}/{d}/{symbol}.csv.gz")
    if r is None:
        return None
    return pd.read_csv(io.BytesIO(gzip.decompress(r.content)))


def availability(exchange):
    r = get(f"{API}/exchanges/{exchange}")
    js = r.json() if r is not None else {}
    av = {}
    for s in js.get("availableSymbols", []):
        av[s["id"].upper()] = (s.get("availableSince"), s.get("availableTo"))
    return av, js


def available(av, sym, day):
    if sym not in av:
        return False
    a, b = av[sym]
    t = pd.Timestamp(day, tz="UTC")
    if a and pd.Timestamp(a) > t + pd.Timedelta(days=1):
        return False
    if b and pd.Timestamp(b) < t:
        return False
    return True


def gem_details():
    out = {}
    for c in COINS17:
        r = get(f"https://api.gemini.com/v1/symbols/details/{c.lower()}usd", tries=3)
        if r is not None:
            out[c] = r.json()
        time.sleep(0.3)
    return out


def per_second_cb(df):
    df = df.sort_values(["timestamp", "id"] if "id" in df else ["timestamp"])
    sec = (df.timestamp.to_numpy() // 1_000_000).astype(np.int64)
    usd = df.price.to_numpy() * df.amount.to_numpy()
    g = pd.DataFrame({"sec": sec, "price": df.price.to_numpy(), "usd": usd,
                      "sell": np.where(df.side.to_numpy() == "sell", usd, 0.0),
                      "buy": np.where(df.side.to_numpy() == "buy", usd, 0.0)}).groupby("sec")
    out = pd.DataFrame({"last": g.price.last(), "low": g.price.min(), "high": g.price.max(), "n": g.price.size(),
                        "usd": g.usd.sum(), "sell_usd": g.sell.sum(), "buy_usd": g.buy.sum()})
    return out.reset_index()


def main(days):
    os.makedirs(os.path.join(OUT, "meta"), exist_ok=True)
    gav, gjs = availability("gemini")
    cav, _ = availability("coinbase")
    with open(os.path.join(OUT, "meta", "tardis_gemini_symbols.json"), "w") as f:
        json.dump({k: v for k, v in gav.items() if k.endswith("USD")}, f, indent=0)
    with open(os.path.join(OUT, "meta", "gemini_details.json"), "w") as f:
        json.dump(gem_details(), f, indent=0)
    for day in days:
        t0 = time.time()
        od = os.path.join(OUT, day)
        os.makedirs(od, exist_ok=True)
        gt, gq, cs, log = [], [], [], []
        for c in COINS17:
            gs, cbs = f"{c}USD", f"{c}-USD"
            if not available(gav, gs, day):
                log.append(f"{c}: not on Gemini (Tardis) this day")
                continue
            t = csv("gemini", "trades", day, gs)
            if t is None or not len(t):
                log.append(f"{c}: no Gemini trades file")
                continue
            t = t[["timestamp", "local_timestamp", "id", "side", "price", "amount"]].copy()
            t["coin"] = c
            gt.append(t)
            q = csv("gemini", "quotes", day, gs)
            if q is not None and len(q):
                q["sec"] = (q.timestamp.to_numpy() // 1_000_000).astype(np.int64)
                q = q.groupby("sec")[["bid_price", "bid_amount", "ask_price", "ask_amount"]].last().reset_index()
                q["coin"] = c
                gq.append(q)
            if available(cav, cbs, day):
                cb = csv("coinbase", "trades", day, cbs)
                if cb is not None and len(cb):
                    s = per_second_cb(cb)
                    s["coin"] = c
                    cs.append(s)
                    log.append(f"{c}: Gemini {len(t)} trades ${(t.price * t.amount).sum() / 1e6:.2f}M; "
                               f"Coinbase {len(cb)} trades ${(cb.price * cb.amount).sum() / 1e6:.1f}M")
                    del cb
                    continue
            log.append(f"{c}: Gemini {len(t)} trades; no Coinbase file")
        if gt:
            pd.concat(gt, ignore_index=True).to_parquet(os.path.join(od, "gem_trades.parquet"), index=False)
        if gq:
            pd.concat(gq, ignore_index=True).to_parquet(os.path.join(od, "gem_quotes.parquet"), index=False)
        if cs:
            pd.concat(cs, ignore_index=True).to_parquet(os.path.join(od, "cb_sec.parquet"), index=False)
        with open(os.path.join(od, "log.txt"), "w") as f:
            f.write("\n".join(log) + "\n")
        print(f"{day} ({time.time() - t0:.0f}s):\n  " + "\n  ".join(log), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
