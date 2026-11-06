#!/usr/bin/env python3
"""Coinbase US futures (Coinbase Financial Markets / Coinbase Derivatives) market data from the public
Advanced Trade API -- no keys needed. This is the venue a New York resident can trade.

Modes:
  products            list every futures product -> reports/cfm_products.csv (+ raw json)
  candles ROOT START  1-minute candles of ROOT's perp-style future (e.g. BTC -> nano BTC perp)
                      -> data/cfm/<ROOT>.parquet  (ts, open, high, low, close, volume[contracts])
  book MINUTES        sample the order book of every perp + its spot pair every ~3s
                      -> reports/cfm_book_samples.parquet and reports/cfm_book_summary.csv
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.coinbase.com/api/v3/brokerage/market"
S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"


def get(path, **params):
    for attempt in range(6):
        try:
            r = S.get(f"{API}/{path}", params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(2 + 2 * attempt)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as err:
            if attempt == 5:
                raise
            time.sleep(1 + 2 * attempt)


def _page_all(**params):
    out, offset = [], 0
    while True:
        js = get("products", limit=100, offset=offset, **params)
        prods = js.get("products", [])
        out += prods
        total = js.get("num_products") or 0
        offset += len(prods)
        if not prods or (total and offset >= total) or len(prods) < 100 and not total:
            break
    return out


def futures_products():
    seen = {}
    for params in ({"product_type": "FUTURE", "contract_expiry_type": "PERPETUAL"},
                   {"product_type": "FUTURE"}):
        try:
            for p in _page_all(**params):
                seen[p["product_id"]] = p
        except Exception as err:
            print("listing failed", params, err, flush=True)
    return list(seen.values())


def is_perp(p):
    f = p.get("future_product_details") or {}
    pid = (p.get("product_id") or "").upper()
    disp = (p.get("display_name") or "").upper()
    return (f.get("contract_expiry_type") == "PERPETUAL" or bool((f.get("perpetual_details") or {}).get("funding_rate"))
            or "PERP" in disp or "20DEC30" in pid or "PERP" in pid)


def root_of(p):
    f = p.get("future_product_details") or {}
    r = f.get("contract_root_unit") or p.get("base_display_symbol") or p.get("base_currency_id") or ""
    return r.upper()


def flat(p):
    f = p.get("future_product_details") or {}
    perp = f.get("perpetual_details") or {}
    return dict(product_id=p.get("product_id"), display=p.get("display_name"), status=p.get("status"),
                trading_disabled=p.get("trading_disabled"), price=p.get("price"),
                price_increment=p.get("price_increment"), base_increment=p.get("base_increment"),
                volume_24h=p.get("volume_24h"), contract_code=f.get("contract_code"),
                contract_size=f.get("contract_size"), contract_root_unit=f.get("contract_root_unit"),
                expiry_type="PERPETUAL" if is_perp(p) else (f.get("contract_expiry_type") or "EXPIRING"),
                expiry=f.get("contract_expiry"), root=root_of(p),
                venue=f.get("venue"), max_leverage=perp.get("max_leverage"), funding_rate=perp.get("funding_rate"),
                open_interest=perp.get("open_interest"), twenty_four_by_seven=f.get("twenty_four_by_seven"),
                group=f.get("group_description"))


def perp_for(root, prods=None):
    prods = prods or futures_products()
    cands = [flat(p) for p in prods]
    cands = [c for c in cands if c["root"] == root and c["expiry_type"] == "PERPETUAL"]
    if not cands:
        return None
    cands.sort(key=lambda c: float(c["volume_24h"] or 0), reverse=True)
    return cands[0]


def mode_products():
    prods = futures_products()
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "reports", "cfm_products.json"), "w") as fh:
        json.dump(prods, fh, indent=1)
    df = pd.DataFrame([flat(p) for p in prods])
    df.to_csv(os.path.join(ROOT, "reports", "cfm_products.csv"), index=False)
    perps = df[df.expiry_type == "PERPETUAL"]
    print(f"{len(df)} futures products, {len(perps)} perp-style")
    pd.set_option("display.width", 250)
    print(df[["product_id", "display", "root", "expiry_type", "contract_size", "price", "price_increment",
              "volume_24h", "max_leverage"]].to_string(index=False))
    pp = [p for p in prods if is_perp(p)] or prods
    print("example product json:", json.dumps(pp[0])[:2500])


def mode_candles(root, start):
    p = perp_for(root)
    if p is None:
        print(f"{root}: no perp-style future listed")
        return
    pid = p["product_id"]
    print(f"{root}: {pid} ({p['display']}), contract size {p['contract_size']} {root}", flush=True)
    s = int(pd.Timestamp(start, tz="UTC").timestamp())
    e = int(time.time()) // 60 * 60
    rows, n, t0, empty_run = {}, 0, time.time(), 0
    # walk backwards from now so we stop once we pass the listing date
    hi = e
    while hi > s:
        lo = max(s, hi - 300 * 60)
        js = get(f"products/{pid}/candles", start=lo, end=hi, granularity="ONE_MINUTE", limit=350)
        cs = js.get("candles", [])
        for c in cs:
            rows[int(c["start"])] = (float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]),
                                     float(c["volume"]))
        empty_run = empty_run + 1 if not cs else 0
        if empty_run >= 60:                     # 60 empty windows (~12.5 days) -> before listing
            break
        hi = lo
        n += 1
        time.sleep(0.12)
        if n % 500 == 0:
            print(f"  {n} requests, {len(rows)} minutes, {time.time() - t0:.0f}s", flush=True)
    if not rows:
        print("no candles returned")
        return
    k = sorted(rows)
    df = pd.DataFrame([rows[i] for i in k], columns=["open", "high", "low", "close", "volume"])
    df.insert(0, "ts", pd.to_datetime(k, unit="s"))
    os.makedirs(os.path.join(ROOT, "data", "cfm"), exist_ok=True)
    df.astype({c: np.float64 for c in ["open", "high", "low", "close", "volume"]}).to_parquet(
        os.path.join(ROOT, "data", "cfm", f"{root}.parquet"), index=False, compression="zstd")
    print(f"{root}: {len(df)} minutes {df.ts.min()} -> {df.ts.max()} in {time.time() - t0:.0f}s")


def depth(levels, mid, side, bps):
    tot = 0.0
    for lv in levels:
        px, sz = float(lv["price"]), float(lv["size"])
        if side == "bid" and px < mid * (1 - bps / 1e4):
            break
        if side == "ask" and px > mid * (1 + bps / 1e4):
            break
        tot += px * sz
    return tot


def mode_book(minutes):
    prods = futures_products()
    perps = [flat(p) for p in prods]
    perps = [c for c in perps if c["expiry_type"] == "PERPETUAL" and str(c["status"] or "online").lower() == "online"]
    if not perps:
        print("no perps found; nothing to sample")
        return
    books = [(c["product_id"], c["root"], float(c["contract_size"] or 1)) for c in perps]
    books += [(f"{c['root']}-USD", c["root"], 1.0) for c in perps if not c["root"].startswith("CDE")]
    print("sampling", [b[0] for b in books], flush=True)
    rec, t_end = [], time.time() + 60 * float(minutes)
    while time.time() < t_end:
        t = pd.Timestamp.utcnow()
        for pid, root, csize in books:
            try:
                js = get("product_book", product_id=pid, limit=100)
            except Exception as err:
                print("err", pid, err)
                continue
            pb = js.get("pricebook", {})
            bids, asks = pb.get("bids", []), pb.get("asks", [])
            if not bids or not asks:
                continue
            bb, ba = float(bids[0]["price"]), float(asks[0]["price"])
            mid = (bb + ba) / 2
            # futures sizes are in contracts -> convert to coin via contract size
            mult = csize if not pid.endswith("-USD") else 1.0
            bl = [{"price": l["price"], "size": float(l["size"]) * mult} for l in bids]
            al = [{"price": l["price"], "size": float(l["size"]) * mult} for l in asks]
            rec.append(dict(ts=t, product=pid, root=root, kind="spot" if pid.endswith("-USD") else "perp",
                            bid=bb, ask=ba, spread_bp=(ba - bb) / mid * 1e4,
                            top_bid_usd=float(bids[0]["size"]) * mult * bb, top_ask_usd=float(asks[0]["size"]) * mult * ba,
                            bid_5bp_usd=depth(bl, mid, "bid", 5), ask_5bp_usd=depth(al, mid, "ask", 5),
                            bid_20bp_usd=depth(bl, mid, "bid", 20), ask_20bp_usd=depth(al, mid, "ask", 20)))
            time.sleep(0.1)
        time.sleep(1.0)
    df = pd.DataFrame(rec)
    df.to_parquet(os.path.join(ROOT, "reports", "cfm_book_samples.parquet"), index=False)
    summ = df.groupby(["root", "kind", "product"]).agg(
        samples=("spread_bp", "size"), spread_bp_median=("spread_bp", "median"), spread_bp_mean=("spread_bp", "mean"),
        spread_bp_p90=("spread_bp", lambda x: x.quantile(0.9)), top_bid_usd=("top_bid_usd", "median"),
        top_ask_usd=("top_ask_usd", "median"), bid_5bp_usd=("bid_5bp_usd", "median"),
        bid_20bp_usd=("bid_20bp_usd", "median")).reset_index()
    summ.to_csv(os.path.join(ROOT, "reports", "cfm_book_summary.csv"), index=False)
    print(summ.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))


if __name__ == "__main__":
    m = sys.argv[1]
    if m == "products":
        mode_products()
    elif m == "candles":
        mode_candles(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "2025-06-01")
    elif m == "book":
        mode_book(sys.argv[2] if len(sys.argv) > 2 else 30)
