#!/usr/bin/env python3
"""Ladder v5 probe (public data, no keys): do the 17 coins have -USDC spot products on Coinbase Advanced Trade, and are
they aliases of the -USD books? Also USDC/USD history on Bitstamp around the March 2023 depeg (for the cash candidate).
Writes reports/ladder_v5/probe_usdc.json and data/ladder_v5/usdc_usd_bitstamp.csv."""
import json
import os
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COINS = ["ETH", "SOL", "XRP", "DOGE", "LTC", "LINK", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE", "ENA", "PEPE",
         "ONDO", "ZEC", "BTC"]
S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"
KEEP = ("product_id", "status", "trading_disabled", "is_disabled", "cancel_only", "limit_only", "post_only",
        "quote_increment", "base_increment", "quote_min_size", "alias", "alias_to", "product_venue", "view_only",
        "quote_currency_id", "base_currency_id", "fcm_trading_session_details", "new")


def get(url, params=None):
    for a in range(4):
        try:
            r = S.get(url, params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(1 + a)
                continue
            return r.status_code, r.json()
        except Exception as err:
            last = repr(err)
            time.sleep(1 + a)
    return None, last


def main():
    out = {"advanced": {}, "exchange": {}}
    for c in COINS:
        for q in ("USD", "USDC"):
            pid = f"{c}-{q}"
            code, js = get(f"https://api.coinbase.com/api/v3/brokerage/market/products/{pid}")
            out["advanced"][pid] = {"http": code, **({k: js.get(k) for k in KEEP if k in js} if isinstance(js, dict) else {"err": str(js)[:200]})}
            code, js = get(f"https://api.exchange.coinbase.com/products/{pid}")
            out["exchange"][pid] = {"http": code, **({k: js.get(k) for k in ("id", "status", "trading_disabled", "quote_increment", "cancel_only", "limit_only", "post_only") if k in js} if isinstance(js, dict) else {"err": str(js)[:200]})}
            time.sleep(0.25)
    # Bitstamp USDC/USD hourly, Mar 1 - Mar 31 2023, and daily 2022-2023
    rows = []
    for step, start, n in ((3600, 1677628800, 1000), (86400, 1640995200, 1000)):
        code, js = get("https://www.bitstamp.net/api/v2/ohlc/usdcusd/", {"step": step, "start": start, "limit": n})
        try:
            for r in js["data"]["ohlc"]:
                rows.append(dict(step=step, ts=int(r["timestamp"]), open=float(r["open"]), high=float(r["high"]),
                                 low=float(r["low"]), close=float(r["close"]), volume=float(r["volume"])))
        except Exception as err:
            out[f"bitstamp_{step}"] = f"{code} {str(js)[:300]} {err!r}"
    os.makedirs(os.path.join(ROOT, "reports", "ladder_v5"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "data", "ladder_v5"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "reports", "ladder_v5", "probe_usdc.json"), "w"), indent=1, default=str)
    if rows:
        import csv
        with open(os.path.join(ROOT, "data", "ladder_v5", "usdc_usd_bitstamp.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    for pid, v in out["advanced"].items():
        print(pid, {k: v.get(k) for k in ("http", "status", "alias", "alias_to", "trading_disabled", "view_only")})
    print(len(rows), "bitstamp rows")


if __name__ == "__main__":
    main()
