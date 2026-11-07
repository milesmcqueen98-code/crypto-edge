#!/usr/bin/env python3
"""H5 (AN) step 1 - runs on GitHub Actions. No prices are fetched here.

1. Pages every article of Binance's announcement catalog 48 ("New Cryptocurrency Listing") back to 2022-01-01 through
   the public CMS list endpoint (the one probe.py used), with a plain research User-Agent and ~2 s between requests.
   If the endpoint refuses (non-200 or success=false) the refusal is recorded and the script stops; nothing is retried
   with other headers.
2. Saves Coinbase's spot product metadata (Exchange API /products incl. delisted, Advanced Trade /market/products) so
   tickers can be mapped to XYZ-USD products.
3. Checks (counts only, no prices printed or saved) whether Advanced Trade's public ticker window serves history for a
   few delisted USD products, which decides how delisted tokens are handled later.

usage: python scripts/hunt/h5an/fetch_articles.py
outputs: data/hunt/h5an/articles.csv, data/hunt/h5an/cb_products_exchange.csv, data/hunt/h5an/cb_products_adv.csv,
         reports/hunt/h5an/fetch_articles.json
"""
import json
import os
import sys
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_D = os.path.join(ROOT, "data", "hunt", "h5an")
OUT_R = os.path.join(ROOT, "reports", "hunt", "h5an")
URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
START_MS = int(pd.Timestamp("2022-01-01").timestamp() * 1000)
UA = "crypto-edge-research/1.0 (academic event study; contact via github milesmcqueen98-code)"
PAUSE = 2.0

S = requests.Session()
S.headers["User-Agent"] = UA
LOG = {"started_utc": pd.Timestamp.utcnow().isoformat(), "user_agent": UA, "pages": []}


def page(n, size=50):
    r = S.get(URL, params={"type": 1, "catalogId": 48, "pageNo": n, "pageSize": size}, timeout=30)
    info = {"page": n, "status": r.status_code}
    try:
        js = r.json()
    except Exception:  # noqa: BLE001
        info["body"] = r.text[:300]
        return info, None
    info["success"] = js.get("success")
    if r.status_code != 200 or not js.get("success", True) or not js.get("data"):
        info["body"] = json.dumps(js)[:300]
        return info, None
    cats = js["data"].get("catalogs") or []
    arts = cats[0].get("articles", []) if cats else []
    info["total"] = cats[0].get("total") if cats else None
    info["n"] = len(arts)
    return info, arts


def fetch_articles():
    rows, n = [], 1
    while True:
        info, arts = page(n)
        LOG["pages"].append(info)
        print(info, flush=True)
        if arts is None:
            LOG["refused_or_failed"] = info
            break
        if not arts:
            break
        for a in arts:
            rows.append(dict(id=a.get("id"), code=a.get("code"), title=a.get("title"), type=a.get("type"),
                             releaseDate=a.get("releaseDate")))
        oldest = min(int(a.get("releaseDate") or 0) for a in arts)
        if oldest < START_MS:
            break
        n += 1
        if n > 200:
            break
        time.sleep(PAUSE)
    d = pd.DataFrame(rows).drop_duplicates("id")
    d["release_utc"] = pd.to_datetime(d.releaseDate, unit="ms")
    d = d.sort_values("releaseDate").reset_index(drop=True)
    LOG["n_articles_all"] = len(d)
    d = d[d.releaseDate >= START_MS]
    LOG["n_articles_since_2022"] = len(d)
    LOG["first"], LOG["last"] = str(d.release_utc.min()), str(d.release_utc.max())
    d.to_csv(os.path.join(OUT_D, "articles.csv"), index=False)
    print("articles since 2022:", len(d), d.release_utc.min(), d.release_utc.max(), flush=True)


def fetch_products():
    js = S.get("https://api.exchange.coinbase.com/products", timeout=30).json()
    ex = pd.DataFrame(js)
    keep = [c for c in ("id", "base_currency", "quote_currency", "status", "trading_disabled", "cancel_only",
                        "limit_only", "post_only", "auction_mode", "status_message") if c in ex.columns]
    ex = ex[keep]
    ex.to_csv(os.path.join(OUT_D, "cb_products_exchange.csv"), index=False)
    LOG["cb_exchange"] = {"n": len(ex), "n_usd": int((ex.quote_currency == "USD").sum()),
                          "status_usd": ex[ex.quote_currency == "USD"].status.value_counts().to_dict()}
    time.sleep(0.5)
    r = S.get("https://api.coinbase.com/api/v3/brokerage/market/products",
              params={"product_type": "SPOT", "limit": 5000, "get_all_products": "true"}, timeout=60)
    pr = r.json().get("products", [])
    adv = pd.DataFrame(pr)
    keep = [c for c in ("product_id", "base_currency_id", "quote_currency_id", "base_display_symbol", "status",
                        "trading_disabled", "is_disabled", "new_at", "view_only", "cancel_only", "limit_only",
                        "post_only", "auction_mode", "approximate_quote_24h_volume", "product_venue") if c in adv.columns]
    adv = adv[keep]
    adv.to_csv(os.path.join(OUT_D, "cb_products_adv.csv"), index=False)
    LOG["cb_adv"] = {"status": r.status_code, "n": len(adv)}
    print("coinbase products: exchange", len(ex), "advanced", len(adv), flush=True)
    return ex


def probe_delisted(ex):
    """Counts only: does the Advanced Trade ticker window serve trades for delisted USD products?"""
    dl = ex[(ex.quote_currency == "USD") & (ex.status == "delisted")].id.tolist()[:6]
    out = {}
    for pid in dl:
        for when in ("2022-06-01 12:00", "2023-03-01 12:00"):
            s = int(pd.Timestamp(when).timestamp())
            r = S.get(f"https://api.coinbase.com/api/v3/brokerage/market/products/{pid}/ticker",
                      params={"limit": 1000, "start": s, "end": s + 6 * 3600}, timeout=30)
            try:
                n = len(r.json().get("trades", []))
            except Exception:  # noqa: BLE001
                n = None
            out[f"{pid}|{when}"] = {"status": r.status_code, "n_trades": n}
            time.sleep(0.25)
    LOG["delisted_ticker_probe"] = out
    print(json.dumps(out), flush=True)


def main():
    os.makedirs(OUT_D, exist_ok=True)
    os.makedirs(OUT_R, exist_ok=True)
    try:
        fetch_articles()
    finally:
        try:
            ex = fetch_products()
            probe_delisted(ex)
        except Exception as e:  # noqa: BLE001
            LOG["products_error"] = f"{type(e).__name__}: {e}"[:400]
        LOG["finished_utc"] = pd.Timestamp.utcnow().isoformat()
        with open(os.path.join(OUT_R, "fetch_articles.json"), "w") as f:
            json.dump(LOG, f, indent=1, default=str)


if __name__ == "__main__":
    sys.exit(main())
