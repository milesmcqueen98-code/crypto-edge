#!/usr/bin/env python3
"""Edge hunt shared helpers (reports/hunt_prereg.md): data loaders, the cost model at 1x/2x, and a trade fetcher for
Coinbase's public market-trades endpoint (perps and spot). Builders import this instead of re-deriving costs.

Trade-side convention on Coinbase (checked in reports/hunt/probe2.json): `side` is the MAKER's side. side == "BUY"
means a resting bid was hit by an aggressive seller (the price ticks down); side == "SELL" means an aggressive buyer
lifted a resting offer.
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

def _data_root():
    d = os.path.join(ROOT, "data")
    if os.path.isdir(os.path.join(d, "minute")) or os.path.isdir(os.path.join(d, "cfm")):
        return d
    alt = "/home/claude/crypto-edge/data"               # builders' sparse worktrees read the main clone's data
    return alt if os.path.isdir(alt) else d


DATA = os.environ.get("HUNT_DATA") or _data_root()

# ------------------------------------------------------------------ products
# Coinbase Derivatives perp-style futures: (product id, contract size in coin units, tick in USD)
PERP = {
    "BTC": ("BIP-20DEC30-CDE", 0.01, 5.0), "ETH": ("ETP-20DEC30-CDE", 0.1, 0.5), "SOL": ("SLP-20DEC30-CDE", 5, 0.01),
    "XRP": ("XPP-20DEC30-CDE", 500, 0.0001), "DOGE": ("DOP-20DEC30-CDE", 5000, 0.00001),
    "LTC": ("LCP-20DEC30-CDE", 5, 0.01), "AVAX": ("AVP-20DEC30-CDE", 10, 0.01), "LINK": ("LNP-20DEC30-CDE", 50, 0.001),
    "ADA": ("ADP-20DEC30-CDE", 1000, 0.0001), "BCH": ("BCP-20DEC30-CDE", 1, 0.05), "SUI": ("SUP-20DEC30-CDE", 500, 0.0001),
    "XLM": ("XLP-20DEC30-CDE", 5000, 0.00001), "HBAR": ("HEP-20DEC30-CDE", 5000, 0.00001),
    "NEAR": ("NER-20DEC30-CDE", 500, 0.0001), "AAVE": ("AVE-20DEC30-CDE", 5, 0.01), "HYPE": ("HYP-20DEC30-CDE", 10, 0.01),
    "ENA": ("ENA-20DEC30-CDE", 5000, 0.00001), "PEPE": ("PEP-20DEC30-CDE", 1e8, 1e-9),
    "ONDO": ("OND-20DEC30-CDE", 1000, 0.0001), "ZEC": ("ZEC-20DEC30-CDE", 1, 0.05),
    "DOT": ("POP-20DEC30-CDE", 100, 0.001), "SHIB": ("SHP-20DEC30-CDE", 1e7, 1e-9), "BNB": ("BNB-20DEC30-CDE", 1, 0.05),
}
# Universe rule for anything that trades perps (fixed in the pre-registration): a contract worth >= $150 at the time
# of the trade (per-contract fees above ~13 bp otherwise) and the coin's 1-minute perp data in data/cfm.
MIN_CONTRACT_USD = 150.0

# ------------------------------------------------------------------ cost model (1x = realistic; 2x = stress)
SPOT_MAKER, SPOT_TAKER = 0.0006, 0.00125      # Coinbase Advanced VIP 1 (the $100K book reaches it in ~2 weeks)
SPOT_HALF_SPREAD_BP = 2.0                      # market exits on spot (as scripts/wick1m/sim.py)
PERP_FEE_USD = 0.20                            # per contract per side, maker or taker (exchange + FCM estimate)
PERP_HS_MULT = 1.5                             # market orders on perps pay 1.5x the measured median half-spread
PERP_FUND_BP_PER_8H = 1.0                      # funding charged to every perp position, either side, pro rata


def perp_half_spread_bp():
    """Measured median half-spread (bp) of each perp (reports/cfm_book_summary.csv, 82 samples)."""
    s = pd.read_csv(os.path.join(ROOT, "reports", "cfm_book_summary.csv"))
    s = s[s.kind == "perp"]
    return {r.root: r.spread_bp_median / 2 for r in s.itertuples()}


_HS = None


def perp_cost_bp(coin, price, taker=False, mult=1.0):
    """One side of a perp trade in bp of notional: the per-contract fee, plus the half-spread for market orders."""
    global _HS
    if _HS is None:
        _HS = perp_half_spread_bp()
    size = PERP[coin][1]
    fee = PERP_FEE_USD / (price * size) * 1e4
    hs = PERP_HS_MULT * _HS.get(coin, 5.0) if taker else 0.0
    return mult * (fee + hs)


def perp_funding_bp(hours, mult=1.0):
    return mult * PERP_FUND_BP_PER_8H * hours / 8.0


def spot_cost_bp(taker=False, mult=1.0):
    """One side of a spot trade in bp: VIP-1 maker or taker fee, plus the half-spread for market orders."""
    return mult * ((SPOT_TAKER * 1e4 + SPOT_HALF_SPREAD_BP) if taker else SPOT_MAKER * 1e4)


def contract_ok(coin, price):
    return coin in PERP and price * PERP[coin][1] >= MIN_CONTRACT_USD


# ------------------------------------------------------------------ data
def load_minute(coin, src="minute", start=None, end=None):
    """1-minute Coinbase spot OHLCV (minutes with trades only), indexed by ts. src: minute (2024-01 .. 2026-11),
    minute_early (2021-01 .. 2023-12), bitstamp."""
    p = os.path.join(DATA, src, f"{coin}.parquet")
    if not os.path.exists(p):
        return None
    d = pd.read_parquet(p).drop_duplicates("ts").set_index("ts").sort_index()
    d = d[d.volume > 0]
    if start is not None:
        d = d[d.index >= pd.Timestamp(start)]
    if end is not None:
        d = d[d.index < pd.Timestamp(end)]
    return d


def load_perp(coin):
    """1-minute Coinbase perp OHLCV in USD per coin (volume converted to coin units), minutes with trades only."""
    p = os.path.join(DATA, "cfm", f"{coin}.parquet")
    if not os.path.exists(p):
        return None
    d = pd.read_parquet(p).drop_duplicates("ts").set_index("ts").sort_index()
    d = d[d.volume > 0].copy()
    d["volume"] = d["volume"] * PERP[coin][1]
    return d


# ------------------------------------------------------------------ trades (run on GitHub Actions; needs internet)
ADV = "https://api.coinbase.com/api/v3/brokerage/market/products"


class TradeFetcher:
    """All trades of one product in [start, end) from Coinbase's public market-trades endpoint, paging backward in
    time (the endpoint returns the most recent `limit` trades of the window). ~8 requests/second."""

    def __init__(self, rate=8.0):
        import requests
        self.S = requests.Session()
        self.S.headers["User-Agent"] = "crypto-edge-research/1.0"
        self.rate, self._last, self.n_req = rate, 0.0, 0
        self._ex = None

    def _get(self, pid, s, e):
        for a in range(8):
            w = self._last + 1.0 / self.rate - time.time()
            if w > 0:
                time.sleep(w)
            self._last = time.time()
            self.n_req += 1
            try:
                r = self.S.get(f"{ADV}/{pid}/ticker", params={"limit": 1000, "start": int(s), "end": int(e)}, timeout=30)
                if r.status_code == 429:
                    time.sleep(1 + a)
                    continue
                if r.status_code == 404:                  # delisted or unknown on Advanced Trade
                    raise LookupError(pid)
                r.raise_for_status()
                return r.json().get("trades", [])
            except LookupError:
                raise
            except Exception:  # noqa: BLE001
                if a == 7:
                    raise
                time.sleep(1 + a)
        return []

    def window(self, pid, start, end):
        """All trades in [start, end). Products Advanced Trade no longer serves (delisted spot pairs) fall back to the
        Exchange API's trade-id cursor (ExchangeTrades), which still serves them."""
        try:
            return self._window_adv(pid, start, end)
        except LookupError:
            if self._ex is None:
                self._ex = ExchangeTrades(rate=min(self.rate, 6.0))
            return self._ex.window(pid, start, end)

    def _window_adv(self, pid, start, end):
        s = int(pd.Timestamp(start).timestamp())
        e = int(pd.Timestamp(end).timestamp())
        seen, rows = set(), []
        while e > s:
            tr = self._get(pid, s, e)
            new = [t for t in tr if t["trade_id"] not in seen]
            for t in new:
                seen.add(t["trade_id"])
                rows.append(t)
            if len(tr) < 1000 or not new:
                break
            e_new = int(min(pd.Timestamp(t["time"]).timestamp() for t in tr))
            e = e_new if e_new < e else e - 1           # >1000 trades inside one second: step past it
        if not rows:
            return pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
        d = pd.DataFrame(rows)
        d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.tz_convert(None)
        d["price"] = d["price"].astype(float)
        d["size"] = d["size"].astype(float)
        d = d[(d.time >= pd.Timestamp(start)) & (d.time < pd.Timestamp(end))]
        return d[["trade_id", "time", "price", "size", "side"]].sort_values(["time", "trade_id"]).reset_index(drop=True)


EXCH = "https://api.exchange.coinbase.com"


class ExchangeTrades:
    """Exchange API trades by trade-id cursor; serves delisted spot products (from builder h5an). `side` is the maker
    side, upper-cased to match Advanced Trade. ~4-6 requests/second."""

    def __init__(self, rate=4.0):
        import requests
        self.S = requests.Session()
        self.S.headers["User-Agent"] = "crypto-edge-research/1.0"
        self.rate, self._last, self.n_req = rate, 0.0, 0

    def get(self, path, params):
        for a in range(8):
            w = self._last + 1.0 / self.rate - time.time()
            if w > 0:
                time.sleep(w)
            self._last = time.time()
            self.n_req += 1
            try:
                r = self.S.get(f"{EXCH}{path}", params=params, timeout=30)
                if r.status_code == 429:
                    time.sleep(1 + a)
                    continue
                r.raise_for_status()
                return r.json()
            except Exception:  # noqa: BLE001
                if a == 7:
                    raise
                time.sleep(1 + a)
        return []

    def _time_of(self, pid, tid):
        js = self.get(f"/products/{pid}/trades", {"after": int(tid) + 1, "limit": 1})
        return (pd.Timestamp(js[0]["time"]).tz_convert(None), int(js[0]["trade_id"])) if js else (None, None)

    def id_at(self, pid, ts, hi):
        """Smallest trade id whose time is >= ts (hi = latest id), by bisection."""
        lo = 1
        while lo < hi:
            mid = (lo + hi) // 2
            t, _ = self._time_of(pid, mid)
            if t is None or t < ts:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def window(self, pid, start, end):
        js = self.get(f"/products/{pid}/trades", {"limit": 1})
        empty = pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
        if not js:
            return empty
        top = int(js[0]["trade_id"])
        i0 = self.id_at(pid, pd.Timestamp(start), top)
        i1 = self.id_at(pid, pd.Timestamp(end), top)
        rows, cur = [], i1
        while cur > i0:
            page = self.get(f"/products/{pid}/trades", {"after": cur, "limit": 1000})
            if not page:
                break
            rows.extend(page)
            mn = min(int(t["trade_id"]) for t in page)
            if mn >= cur:
                break
            cur = mn
        if not rows:
            return empty
        d = pd.DataFrame(rows)
        d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.tz_convert(None)
        d["price"] = d["price"].astype(float)
        d["size"] = d["size"].astype(float)
        d["side"] = d["side"].str.upper()
        d = d[(d.time >= pd.Timestamp(start)) & (d.time < pd.Timestamp(end))].drop_duplicates("trade_id")
        return d[["trade_id", "time", "price", "size", "side"]].sort_values(["time", "trade_id"]).reset_index(drop=True)
