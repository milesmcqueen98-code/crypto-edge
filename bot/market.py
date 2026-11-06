"""Public Coinbase market data (no keys): spot 1-minute candles (Coinbase Exchange, the research source)
and Coinbase US futures candles / order books (Advanced Trade public endpoints)."""
import time

import numpy as np
import pandas as pd
import requests

EXCHANGE = "https://api.exchange.coinbase.com"
ADV = "https://api.coinbase.com/api/v3/brokerage/market"
_S = requests.Session()
_S.headers["User-Agent"] = "crypto-edge-bot/1.0"


def _get(url, params=None, tries=5):
    for a in range(tries):
        try:
            r = _S.get(url, params=params, timeout=15)
            if r.status_code == 429:
                time.sleep(1 + a)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if a == tries - 1:
                raise
            time.sleep(0.5 + a)


def spot_candles(coin, start, end):
    """1-minute candles [start, end) as a DataFrame indexed by minute (UTC, naive)."""
    rows = {}
    s = pd.Timestamp(start).floor("min")
    end = pd.Timestamp(end).floor("min")
    while s < end:
        e = min(end, s + pd.Timedelta(minutes=300))
        js = _get(f"{EXCHANGE}/products/{coin}-USD/candles",
                  {"granularity": 60, "start": s.isoformat() + "Z", "end": (e - pd.Timedelta(minutes=1)).isoformat() + "Z"})
        for t, lo, hi, op, cl, vo in js or []:
            rows[t] = (op, hi, lo, cl, vo)
        s = e
        time.sleep(0.12)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    k = sorted(rows)
    df = pd.DataFrame([rows[i] for i in k], columns=["open", "high", "low", "close", "volume"], dtype=float)
    df.index = pd.to_datetime(k, unit="s")
    return df[(df.index >= pd.Timestamp(start)) & (df.index < end)]


def futures_candles(product_id, start, end):
    rows = {}
    s = int(pd.Timestamp(start).timestamp())
    e = int(pd.Timestamp(end).timestamp())
    while s < e:
        hi = min(e, s + 300 * 60)
        js = _get(f"{ADV}/products/{product_id}/candles", {"start": s, "end": hi, "granularity": "ONE_MINUTE", "limit": 350})
        for c in js.get("candles", []):
            rows[int(c["start"])] = (float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c["volume"]))
        s = hi
        time.sleep(0.12)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    k = sorted(rows)
    df = pd.DataFrame([rows[i] for i in k], columns=["open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(k, unit="s")
    return df[(df.index >= pd.Timestamp(start)) & (df.index < pd.Timestamp(end))]


def book(product_id, limit=50):
    """Bids and asks as lists of (price, size in contracts), best first."""
    js = _get(f"{ADV}/product_book", {"product_id": product_id, "limit": limit})
    pb = js.get("pricebook", {})
    return ([(float(b["price"]), float(b["size"])) for b in pb.get("bids", [])],
            [(float(a["price"]), float(a["size"])) for a in pb.get("asks", [])])


def book_top(product_id):
    js = _get(f"{ADV}/product_book", {"product_id": product_id, "limit": 5})
    pb = js.get("pricebook", {})
    bids, asks = pb.get("bids", []), pb.get("asks", [])
    if not bids or not asks:
        return np.nan, np.nan
    return float(bids[0]["price"]), float(asks[0]["price"])
