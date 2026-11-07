#!/usr/bin/env python3
"""H10 (XQ) step 1: the secondary-book pair list, built from the Coinbase Exchange /products endpoint (online AND
delisted) before any price is read (reports/hunt/h10xq/SPEC.md).

Universe rule (SPEC): every Coinbase spot pair quoted in BTC, ETH or USDT whose base and quote both have USD books
(any status, so delisted books count), so the USD-implied cross exists. X-USDC pairs are not separate books (USDC
books were merged into USD in 2023) and are not quoted in BTC/ETH/USDT anyway.
The endpoint carries no prices or volumes; nothing here reads a price.

Writes reports/hunt/h10xq/pairs.csv (one row per secondary pair) and reports/hunt/h10xq/products_all.csv (the raw
listing, for audit).
usage: python scripts/hunt/h10xq/pairs.py
"""
import json
import os
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, "reports", "hunt", "h10xq")
QUOTES = ("BTC", "ETH", "USDT")


def main():
    S = requests.Session()
    S.headers["User-Agent"] = "crypto-edge-research/1.0"
    for a in range(6):
        r = S.get("https://api.exchange.coinbase.com/products", timeout=30)
        if r.status_code == 200:
            break
        time.sleep(2 + 2 * a)
    r.raise_for_status()
    js = r.json()
    P = pd.DataFrame(js)
    os.makedirs(OUT, exist_ok=True)
    P.sort_values("id").to_csv(os.path.join(OUT, "products_all.csv"), index=False)
    usd = P[P.quote_currency == "USD"].set_index("base_currency")
    sec = P[P.quote_currency.isin(QUOTES)].copy()
    sec["base_usd"] = sec.base_currency.map(lambda b: f"{b}-USD" if b in usd.index else None)
    sec["quote_usd"] = sec.quote_currency.map(lambda q: f"{q}-USD" if q in usd.index else None)
    sec["base_usd_status"] = sec.base_currency.map(lambda b: usd.status.get(b))
    sec["quote_usd_status"] = sec.quote_currency.map(lambda q: usd.status.get(q))
    sec["eligible"] = sec.base_usd.notna() & sec.quote_usd.notna()
    cols = ["id", "base_currency", "quote_currency", "status", "trading_disabled", "cancel_only", "limit_only",
            "post_only", "auction_mode", "fx_stablecoin", "quote_increment", "base_increment", "min_market_funds",
            "base_usd", "base_usd_status", "quote_usd", "quote_usd_status", "eligible"]
    cols = [c for c in cols if c in sec.columns]
    sec = sec[cols].sort_values(["quote_currency", "id"])
    sec.to_csv(os.path.join(OUT, "pairs.csv"), index=False)
    meta = dict(fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), n_products=len(P),
                n_usd=int((P.quote_currency == "USD").sum()), status_counts=P.status.value_counts().to_dict(),
                n_secondary=len(sec), n_eligible=int(sec.eligible.sum()),
                eligible_by_quote=sec[sec.eligible].quote_currency.value_counts().to_dict(),
                eligible_by_status=sec[sec.eligible].status.value_counts().to_dict(),
                ineligible=sec[~sec.eligible].id.tolist())
    with open(os.path.join(OUT, "pairs_meta.json"), "w") as f:
        json.dump(meta, f, indent=1, default=str)
    print(json.dumps(meta, indent=1, default=str))
    print(sec[sec.eligible].to_string(index=False))


if __name__ == "__main__":
    main()
