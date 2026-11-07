#!/usr/bin/env python3
"""H12 (LT) data fetcher, run on GitHub Actions (reports/hunt/h12lt/SPEC.md). Plain research User-Agent, <= 8 req/s.

  universe                  Exchange /products (every status, so delisted pairs are kept), /currencies, Advanced
                            Trade product metadata, and 2024 daily candles (granularity 86400) for every USD pair.
                            Writes data/hunt/h12lt/daily2024.csv and the product metadata json.
  minute <shard> <nshards>  1-minute candles 2024-01-01 -> 2026-11-06 (exclusive) for every coin in
                            data/hunt/h12lt/candidates.csv (shard i takes rows i, i+n, ...), in the format of
                            scripts/fetch_minute.py (ts, open, high, low, close, volume; float32; minutes with trades
                            only) -> data/hunt/h12lt/minute/<COIN>.parquet. Exchange candles also serve delisted pairs.
                            Also writes each coin's est_tick (scripts/wick1m/trades_wide.py rule) to ticks_<shard>.csv.
  trades <shard> <nshards>  trade prints around the sampled DEV fills in data/hunt/h12lt/print_sample.csv
                            (common.TradeFetcher, Exchange trade-id paging for delisted pairs), aggregated here.
"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data", "hunt", "h12lt")
EXCH = "https://api.exchange.coinbase.com"
ADV = "https://api.coinbase.com/api/v3/brokerage/market/products"
RATE = 8.0
START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-11-06")

_tl = threading.local()
_lock = threading.Lock()
_next = [0.0]
N_REQ = [0]


def _session():
    if not hasattr(_tl, "S"):
        _tl.S = requests.Session()
        _tl.S.headers["User-Agent"] = "crypto-edge-research/1.0"
    return _tl.S


def _pace():
    with _lock:
        now = time.time()
        t = max(now, _next[0])
        _next[0] = t + 1.0 / RATE
        N_REQ[0] += 1
    w = t - time.time()
    if w > 0:
        time.sleep(w)


def get(url, params=None):
    for a in range(10):
        _pace()
        try:
            r = _session().get(url, params=params, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(1 + a)
                continue
            if r.status_code == 404:
                return None
            if r.status_code == 400:
                print("400", url, params, r.text[:200], flush=True)
                return None
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:  # noqa: PERF203
            if a == 9:
                raise
            print("retry", url, type(e).__name__, flush=True)
            time.sleep(1 + a)
    return None


# ------------------------------------------------------------------ universe screen inputs
def universe_job():
    os.makedirs(DATA, exist_ok=True)
    ex = get(f"{EXCH}/products")
    cur = get(f"{EXCH}/currencies")
    adv = (get(ADV, {"product_type": "SPOT", "limit": 5000}) or {}).get("products", [])
    json.dump(ex, open(os.path.join(DATA, "products_exchange.json"), "w"), indent=0)
    json.dump(cur, open(os.path.join(DATA, "currencies_exchange.json"), "w"), indent=0)
    keep = ("product_id", "base_currency_id", "quote_currency_id", "base_name", "status", "new_at",
            "trading_disabled", "is_disabled", "cancel_only", "limit_only", "post_only", "auction_mode",
            "quote_increment", "base_increment", "product_venue", "view_only")
    json.dump([{k: p.get(k) for k in keep} for p in adv], open(os.path.join(DATA, "products_adv.json"), "w"), indent=0)
    usd = sorted(p["id"] for p in ex if p["quote_currency"] == "USD")
    print(f"{len(ex)} products, {len(usd)} USD pairs", flush=True)
    wins = [(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-10-16")), (pd.Timestamp("2024-10-17"), pd.Timestamp("2024-12-31"))]

    def one(pid):
        rows = []
        for s, e in wins:
            js = get(f"{EXCH}/products/{pid}/candles", {"granularity": 86400, "start": s.isoformat(), "end": e.isoformat()})
            if isinstance(js, list):
                rows += [(pid, int(c[0]), *map(float, c[1:6])) for c in js]
        return rows

    t0 = time.time()
    with ThreadPoolExecutor(4) as pool:
        res = list(pool.map(one, usd))
    rows = [r for rr in res for r in rr]
    d = pd.DataFrame(rows, columns=["pid", "t", "low", "high", "open", "close", "volume"])
    d.insert(1, "day", pd.to_datetime(d.pop("t"), unit="s"))
    d = d.drop_duplicates(["pid", "day"]).sort_values(["pid", "day"])
    d = d[(d.day >= "2024-01-01") & (d.day < "2025-01-01")]
    d.to_csv(os.path.join(DATA, "daily2024.csv"), index=False)
    print(f"daily2024: {len(d)} rows, {d.pid.nunique()} pairs with 2024 candles, {N_REQ[0]} requests, "
          f"{time.time() - t0:.0f}s")


# ------------------------------------------------------------------ 1-minute candles
def est_tick_df(d):
    """scripts/wick1m/trades_wide.py est_tick, unchanged, on a frame with ts and close (float32 as stored)."""
    w = d[(d.ts >= "2024-07-01") & (d.ts < "2025-01-01")]
    if len(w) < 10000:
        w = d[d.ts < d.ts.min() + pd.Timedelta(days=183)]
    px = w.close.to_numpy(np.float64)
    px = px[px > 0]
    if len(px) == 0:
        return np.nan, np.nan, len(w)
    best = np.nan
    for k in range(-10, 3):
        t = 10.0 ** k
        if t > 0.01 * np.median(px):
            break
        tol = np.maximum(0.02, 2.0 * px * 6e-8 / t)
        on = np.abs(px / t - np.round(px / t)) <= tol
        if on.mean() >= 0.95:
            best = t
    last = float(w.close.iloc[-1])
    return best, best / last * 1e4, len(w)


def minutes(pid, start=START, end=END, threads=4):
    wins = []
    s = start
    while s < end:
        wins.append(s)
        s += pd.Timedelta(minutes=300)

    def one(s):
        js = get(f"{EXCH}/products/{pid}/candles",
                 {"granularity": 60, "start": s.isoformat(), "end": (s + pd.Timedelta(minutes=299)).isoformat()})
        return js if isinstance(js, list) else []

    rows = {}
    with ThreadPoolExecutor(threads) as pool:
        for js in pool.map(one, wins):
            for c in js:
                rows[int(c[0])] = c
    if not rows:
        return None
    d = pd.DataFrame([rows[k] for k in sorted(rows)], columns=["t", "low", "high", "open", "close", "volume"])
    d.insert(0, "ts", pd.to_datetime(d.pop("t"), unit="s"))
    d = d[(d.ts >= start) & (d.ts < end)]
    return d[["ts", "open", "high", "low", "close", "volume"]].astype(
        {c: np.float32 for c in ("open", "high", "low", "close", "volume")}).reset_index(drop=True)


def minute_job(shard, n):
    """For each candidate: H2-2024 candles first. est_tick looks only at H2 2024 when it has >= 10,000 minutes, so a
    coin whose H2 tick is above 3 bp cannot enter the universe and the rest of its history is not fetched. Otherwise
    (passing, or too few H2 minutes) the full 2024-01-01 -> 2026-11-06 history is fetched and est_tick is computed on
    the full file, exactly as scripts/wick1m/trades_wide.py does."""
    shard, n = int(shard), int(n)
    C = pd.read_csv(os.path.join(DATA, "candidates.csv"))
    C = C.sort_values("coin").reset_index(drop=True)
    C = C.iloc[shard::n]
    print(f"shard {shard}/{n}: {list(C.coin)}", flush=True)
    out = os.path.join(DATA, "minute")
    os.makedirs(out, exist_ok=True)
    h0, h1 = pd.Timestamp("2024-07-01"), pd.Timestamp("2025-01-01")
    ticks, t0 = [], time.time()
    for r in C.itertuples():
        h2 = minutes(r.pid, h0, h1)
        n_h2 = 0 if h2 is None else len(h2)
        if n_h2 >= 10000:
            t, bp, nw = est_tick_df(h2)
            if not (bp <= 3.0):
                ticks.append(dict(coin=r.coin, pid=r.pid, tick=t, tick_bp=bp, n_tick_rows=nw, n_min=0, fetched="h2"))
                print(f"  {r.coin}: H2 tick {t} ({bp:.2f} bp) > 3 bp, not fetched further ({time.time() - t0:.0f}s)",
                      flush=True)
                continue
        parts = [x for x in (minutes(r.pid, START, h0), h2, minutes(r.pid, h1, END)) if x is not None and len(x)]
        if not parts:
            ticks.append(dict(coin=r.coin, pid=r.pid, tick=np.nan, tick_bp=np.nan, n_tick_rows=0, n_min=0,
                              fetched="none"))
            print(f"  {r.coin}: no candles", flush=True)
            continue
        d = pd.concat(parts, ignore_index=True).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
        d.to_parquet(os.path.join(out, f"{r.coin}.parquet"), index=False, compression="zstd")
        t, bp, nw = est_tick_df(d)
        ticks.append(dict(coin=r.coin, pid=r.pid, tick=t, tick_bp=bp, n_tick_rows=nw, n_min=len(d), fetched="full",
                          first=str(d.ts.min()), last=str(d.ts.max())))
        print(f"  {r.coin}: {len(d)} minutes {d.ts.min()} -> {d.ts.max()}, tick {t} ({bp:.2f} bp), "
              f"req={N_REQ[0]} {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(ticks).to_csv(os.path.join(DATA, f"ticks_{shard}.csv"), index=False)
    print(f"done in {time.time() - t0:.0f}s, {N_REQ[0]} requests")


# ------------------------------------------------------------------ trade prints around sampled fills
def trade_stats(d, ts, lvl, tick):
    """Fill check on prints for a resting bid at `lvl` during minute `ts` (prints aggregated, never stored):
    confirm = a print at or below lvl - tick in the fill minute; print-through = USD of prints strictly below lvl
    from the first such print while the price stays below (15-minute cap); half-spread = half the gap between
    adjacent opposite-maker-side prints within 2 s (bp); sweep = USD of prints that hit bids (maker side BUY)."""
    if d is None:
        return dict(n_trades=-1)
    if len(d) == 0:
        return dict(n_trades=0)
    t1 = ts + pd.Timedelta(minutes=1)
    m = d[(d.time >= ts) & (d.time < t1)]
    out = dict(n_trades=len(d), n_min=len(m), confirm=bool((m.price <= lvl - tick + 1e-12).any()),
               touch=bool((m.price <= lvl + 1e-12).any()),
               min_px_rel=float(m.price.min() / lvl - 1) if len(m) else np.nan,
               open_above=bool(m.price.iloc[0] > lvl) if len(m) else False)
    after = d[d.time >= ts].reset_index(drop=True)
    below = np.nonzero((after.price < lvl - 1e-12).to_numpy())[0]
    thr = 0.0
    if len(below):
        j0 = below[0]
        stop = after.time.iloc[j0] + pd.Timedelta(minutes=15)
        pr, sz, tm = after.price.to_numpy(), after["size"].to_numpy(), after.time.to_numpy()
        for j in range(j0, len(after)):
            if pr[j] >= lvl - 1e-12 or tm[j] > np.datetime64(stop):
                break
            thr += pr[j] * sz[j]
    out["print_through_usd"] = thr
    out["sweep_usd"] = float((m.price * m["size"])[m.side == "BUY"].sum()) if len(m) else 0.0
    out["vol_usd_min"] = float((m.price * m["size"]).sum()) if len(m) else 0.0
    s = d.sort_values(["time", "trade_id"]).reset_index(drop=True)
    p, sd, tt = s.price.to_numpy(), s.side.to_numpy(), s.time.to_numpy()
    gaps = []
    for j in range(1, len(s)):
        if sd[j] != sd[j - 1] and (tt[j] - tt[j - 1]) <= np.timedelta64(2, "s"):
            ask = p[j] if sd[j] == "SELL" else p[j - 1]          # maker SELL = a lifted offer
            bid = p[j] if sd[j] == "BUY" else p[j - 1]
            mid = 0.5 * (ask + bid)
            if ask >= bid and mid > 0:
                gaps.append(1e4 * (ask - bid) / mid / 2)
    out["half_spread_bp_med"] = float(np.median(gaps)) if gaps else np.nan
    out["n_spread_pairs"] = len(gaps)
    out["tick_bp"] = float(1e4 * tick / lvl)
    return out


def trade_job(shard, n):
    import common
    shard, n = int(shard), int(n)
    Q = pd.read_csv(os.path.join(DATA, "print_sample.csv"), parse_dates=["ts", "fill_t"])
    keys = sorted(set(zip(Q.pid, Q.fill_t)))
    mine = set(keys[shard::n])
    Q = Q[[(p, t) in mine for p, t in zip(Q.pid, Q.fill_t)]]
    W = Q.groupby(["pid", "fill_t"], sort=True)
    print(f"shard {shard}/{n}: {len(Q)} tranches in {W.ngroups} fill minutes", flush=True)
    F = common.TradeFetcher(rate=RATE)
    out, t0 = [], time.time()
    for i, ((pid, ft), g) in enumerate(W):
        w0, w1 = ft - pd.Timedelta(minutes=2), ft + pd.Timedelta(minutes=17)
        d, src = None, "adv"
        try:
            d = F.window(pid, w0, w1)
        except Exception as e:  # noqa: BLE001
            print("fetch fail", pid, ft, type(e).__name__, str(e)[:100], flush=True)
            d, src = None, "fail"
        for q in g.itertuples():
            rec = dict(pid=pid, coin=q.coin, ts=q.ts, fill_t=ft, k=q.k, lvl=q.lvl, tick=q.tick,
                       cand_through_usd=q.in_spot, fill_usd=q.fill, src=src)
            rec.update(trade_stats(d, ft, q.lvl, q.tick))
            out.append(rec)
        if i % 20 == 0:
            print(f"  {i}/{W.ngroups} {pid} {ft} n={out[-1].get('n_trades')} req={F.n_req} {time.time() - t0:.0f}s",
                  flush=True)
    os.makedirs(DATA, exist_ok=True)
    pd.DataFrame(out).to_csv(os.path.join(DATA, f"print_check_{shard}.csv"), index=False)
    print(f"done {len(out)} tranches in {time.time() - t0:.0f}s, requests {F.n_req}")


if __name__ == "__main__":
    job = sys.argv[1]
    if job == "universe":
        universe_job()
    elif job == "minute":
        minute_job(*sys.argv[2:4])
    elif job == "trades":
        trade_job(*sys.argv[2:4])
