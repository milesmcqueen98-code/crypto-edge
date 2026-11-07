#!/usr/bin/env python3
"""H4 (NL) data fetcher, run on GitHub Actions (reports/hunt/h4nl/SPEC.md).

  days  <shard> <nshards>   product lists (Exchange /products incl. delisted, /currencies, Advanced Trade `new_at`)
                            and, for every product whose base has a USD pair, the first/last trading day and the
                            number of trading days from daily candles (granularity 86400). Only dates are stored.
  minute <shard> <nshards>  1-minute candles for [first_day, first_day + 32 d) of every listing in
                            data/hunt/h4nl/listings_pre.csv (Exchange candles, granularity 60, 300 per call).
  trades <shard> <nshards>  trade prints around the sampled candidate fills in data/hunt/h4nl/trade_sample.csv
                            (common.TradeFetcher; Exchange trade-id paging as a fallback), aggregated on the runner.
Shards are assigned by crc32(product id) so every shard agrees whatever product list it sees.
"""
import json
import os
import sys
import time
import zlib

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data", "hunt", "h4nl")
EXCH = "https://api.exchange.coinbase.com"
ADV = "https://api.coinbase.com/api/v3/brokerage/market/products"
RATE = 8.0

S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"
_last = [0.0]
N_REQ = [0]


def get(url, params=None):
    for a in range(10):
        w = _last[0] + 1.0 / RATE - time.time()
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
        N_REQ[0] += 1
        try:
            r = S.get(url, params=params, timeout=30)
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


def shard_of(pid, n):
    return zlib.crc32(pid.encode()) % n


# ------------------------------------------------------------------ universe: product lists and trading days
def meta(write):
    ex = get(f"{EXCH}/products")
    cur = get(f"{EXCH}/currencies")
    adv = get(ADV, {"product_type": "SPOT", "limit": 5000}).get("products", [])
    if write:
        os.makedirs(DATA, exist_ok=True)
        json.dump(ex, open(os.path.join(DATA, "products_exchange.json"), "w"), indent=0)
        json.dump(cur, open(os.path.join(DATA, "currencies_exchange.json"), "w"), indent=0)
        keep = ("product_id", "base_currency_id", "quote_currency_id", "base_name", "status", "new_at",
                "trading_disabled", "is_disabled", "cancel_only", "limit_only", "post_only", "auction_mode",
                "quote_increment", "base_increment", "product_venue", "view_only")
        json.dump([{k: p.get(k) for k in keep} for p in adv], open(os.path.join(DATA, "products_adv.json"), "w"),
                  indent=0)
    return ex


def trading_days(pid, lo="2015-01-01", hi=None, step=290):
    """First/last day with a daily candle with volume > 0, and the count of such days (dates only)."""
    hi = pd.Timestamp(hi or pd.Timestamp.utcnow().tz_localize(None).normalize() + pd.Timedelta(days=1))
    s = pd.Timestamp(lo)
    days = []
    while s < hi:
        e = min(s + pd.Timedelta(days=step - 1), hi)
        js = get(f"{EXCH}/products/{pid}/candles", {"granularity": 86400, "start": s.isoformat(), "end": e.isoformat()})
        if isinstance(js, list):
            days += [pd.Timestamp(c[0], unit="s") for c in js if float(c[5]) > 0]
        s = s + pd.Timedelta(days=step)
    if not days:
        return None, None, 0
    days = sorted(set(days))
    return days[0].date(), days[-1].date(), len(days)


def days_job(shard, n):
    shard, n = int(shard), int(n)
    ex = meta(write=(shard == 0))
    usd_bases = {p["base_currency"].upper() for p in ex if p["quote_currency"] == "USD"}
    todo = sorted(p["id"] for p in ex if p["base_currency"].upper() in usd_bases and shard_of(p["id"], n) == shard)
    print(f"shard {shard}/{n}: {len(todo)} products (of {len(ex)})", flush=True)
    rows, t0 = [], time.time()
    for i, pid in enumerate(todo):
        f, l, k = trading_days(pid)
        rows.append(dict(pid=pid, first_day=f, last_day=l, n_days=k))
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} {pid} {f} {l} {k}  req={N_REQ[0]} {time.time() - t0:.0f}s", flush=True)
    os.makedirs(DATA, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(DATA, f"universe_days_{shard}.csv"), index=False)
    print(f"done: {len(rows)} products, {N_REQ[0]} requests, {time.time() - t0:.0f}s")


# ------------------------------------------------------------------ 1-minute candles for days 0..31 of each listing
def minutes(pid, start, end):
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    rows = {}
    while s < e:
        js = get(f"{EXCH}/products/{pid}/candles",
                 {"granularity": 60, "start": s.isoformat(), "end": (s + pd.Timedelta(minutes=299)).isoformat()})
        if isinstance(js, list):
            for c in js:
                rows[int(c[0])] = c
        s += pd.Timedelta(minutes=300)
    if not rows:
        return None
    d = pd.DataFrame([rows[k] for k in sorted(rows)], columns=["t", "low", "high", "open", "close", "volume"])
    d.insert(0, "ts", pd.to_datetime(d.pop("t"), unit="s"))
    d = d[d.ts < e]
    out = d[["ts", "open", "high", "low", "close"]].astype({c: np.float32 for c in ("open", "high", "low", "close")})
    out["volume"] = d["volume"].astype(np.float32)
    out.insert(0, "pid", pid)
    return out


def minute_job(shard, n, days=32):
    shard, n = int(shard), int(n)
    L = pd.read_csv(os.path.join(DATA, "listings_pre.csv"), parse_dates=["first_day"])
    L = L[[shard_of(p, n) == shard for p in L.pid]]
    print(f"shard {shard}/{n}: {len(L)} listings", flush=True)
    parts, t0 = [], time.time()
    for i, r in enumerate(L.itertuples()):
        d = minutes(r.pid, r.first_day, r.first_day + pd.Timedelta(days=days))
        if d is not None:
            parts.append(d)
        print(f"  {i + 1}/{len(L)} {r.pid} {r.first_day.date()} rows={0 if d is None else len(d)} "
              f"req={N_REQ[0]} {time.time() - t0:.0f}s", flush=True)
    os.makedirs(os.path.join(DATA, "m1"), exist_ok=True)
    out = pd.concat(parts, ignore_index=True)
    out["pid"] = out["pid"].astype("category")
    out.to_parquet(os.path.join(DATA, "m1", f"m1_{shard}.parquet"), index=False, compression="zstd",
                   compression_level=9)
    print(f"done: {len(out)} rows, {out.pid.nunique()} listings, {N_REQ[0]} requests, {time.time() - t0:.0f}s")


# ------------------------------------------------------------------ trade prints around sampled candidate fills
def exch_trades_window(pid, start, end, max_req=60):
    """Exchange trade-id paging fallback: binary-search the trade id at `end`, then page backward to `start`."""
    s_ts, e_ts = pd.Timestamp(start), pd.Timestamp(end)
    top = get(f"{EXCH}/products/{pid}/trades", {"limit": 1})
    if not top:
        return None
    hi = int(top[0]["trade_id"]) + 1
    lo_id, hi_id = 1, hi
    n = 0
    while hi_id - lo_id > 1000 and n < 40:            # find an id whose trades sit just after `end`
        mid = (lo_id + hi_id) // 2
        js = get(f"{EXCH}/products/{pid}/trades", {"limit": 1, "after": mid + 1})
        n += 1
        if not js:
            hi_id = mid
            continue
        t = pd.Timestamp(js[0]["time"]).tz_convert(None)
        if t >= e_ts:
            hi_id = mid
        else:
            lo_id = mid
    rows, cur = [], hi_id + 1
    for _ in range(max_req):
        js = get(f"{EXCH}/products/{pid}/trades", {"limit": 1000, "after": cur})
        if not js:
            break
        rows += js
        cur = min(int(t["trade_id"]) for t in js)
        if pd.Timestamp(js[-1]["time"]).tz_convert(None) < s_ts or cur <= 1:
            break
    if not rows:
        return pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
    d = pd.DataFrame(rows)
    d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.tz_convert(None)
    d["price"] = d["price"].astype(float)
    d["size"] = d["size"].astype(float)
    # Exchange `side` is the MAKER side too (docs: "buy side indicates a down-tick"), as in common.py; checked on the
    # runner with the uptick/downtick split printed in trade_stats
    d["side"] = d["side"].str.upper()
    d = d[(d.time >= s_ts) & (d.time < e_ts)].drop_duplicates("trade_id")
    return d[["trade_id", "time", "price", "size", "side"]].sort_values(["time", "trade_id"]).reset_index(drop=True)


def trade_job(shard, n):
    import common
    shard, n = int(shard), int(n)
    Q = pd.read_csv(os.path.join(DATA, "trade_sample.csv"), parse_dates=["ts"])
    Q = Q[[shard_of(f"{p}|{t}", n) == shard for p, t in zip(Q.pid, Q.ts.astype(str))]]
    print(f"shard {shard}/{n}: {len(Q)} sampled fills", flush=True)
    F = common.TradeFetcher(rate=RATE)
    out, t0 = [], time.time()
    for i, q in enumerate(Q.itertuples()):
        w0, w1 = q.ts - pd.Timedelta(minutes=2), q.ts + pd.Timedelta(minutes=17)
        src = "adv"
        try:
            d = F.window(q.pid, w0, w1)
        except Exception as e:  # noqa: BLE001
            print("adv fail", q.pid, q.ts, type(e).__name__, str(e)[:100], flush=True)
            d = pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
        if len(d) == 0:
            src = "exch"
            try:
                d = exch_trades_window(q.pid, w0, w1)
            except Exception as e:  # noqa: BLE001
                print("exch fail", q.pid, q.ts, type(e).__name__, str(e)[:100], flush=True)
                d = None
        rec = dict(pid=q.pid, ts=q.ts, k=q.k, lvl=q.lvl, tick=q.tick, cand_through_usd=q.through_usd, src=src)
        rec.update(trade_stats(d, q.ts, q.lvl, q.tick))
        out.append(rec)
        if i % 20 == 0:
            print(f"  {i}/{len(Q)} {q.pid} {q.ts} n={rec.get('n_trades')} {src} req={F.n_req + N_REQ[0]} "
                  f"{time.time() - t0:.0f}s", flush=True)
    os.makedirs(DATA, exist_ok=True)
    pd.DataFrame(out).to_csv(os.path.join(DATA, f"trade_check_{shard}.csv"), index=False)
    print(f"done {len(out)} in {time.time() - t0:.0f}s")


def trade_stats(d, ts, lvl, tick):
    """Fill check on prints for a resting bid at `lvl` during minute `ts` (prints are aggregated, never stored):
    - confirm: a print at or below lvl - tick inside the fill minute;
    - through-volume: USD of prints strictly below lvl from the first print below it while the price stays below
      (the first print at or above lvl ends it; 15-minute cap), as the pre-registration's trade rule;
    - spread: half the price gap between adjacent opposite-side prints within 2 s, in bp, over the window;
    - seller sweep: USD of prints that hit bids (maker side BUY) in the fill minute."""
    if d is None:
        return dict(n_trades=-1)
    if len(d) == 0:
        return dict(n_trades=0)
    t1 = ts + pd.Timedelta(minutes=1)
    m = d[(d.time >= ts) & (d.time < t1)]
    out = dict(n_trades=len(d), n_min=len(m), confirm=bool((m.price <= lvl - tick + 1e-12).any()),
               touch=bool((m.price <= lvl + 1e-12).any()), min_px_rel=float(m.price.min() / lvl - 1) if len(m) else np.nan)
    after = d[d.time >= ts].reset_index(drop=True)
    below = np.nonzero((after.price < lvl - 1e-12).to_numpy())[0]
    thr = 0.0
    if len(below):
        j0 = below[0]
        stop = after.time.iloc[j0] + pd.Timedelta(minutes=15)
        for j in range(j0, len(after)):
            p = after.price.iloc[j]
            if p >= lvl - 1e-12 or after.time.iloc[j] > stop:
                break
            thr += p * after["size"].iloc[j]
    out["print_through_usd"] = thr
    out["sweep_usd"] = float((m.price * m["size"])[m.side == "BUY"].sum()) if len(m) else 0.0
    out["vol_usd_min"] = float((m.price * m["size"]).sum()) if len(m) else 0.0
    s = d.sort_values(["time", "trade_id"]).reset_index(drop=True)
    p, sd, tt = s.price.to_numpy(), s.side.to_numpy(), s.time.to_numpy()
    gaps = []
    for j in range(1, len(s)):
        if sd[j] != sd[j - 1] and (tt[j] - tt[j - 1]) <= np.timedelta64(2, "s"):
            ask = p[j] if sd[j] == "SELL" else p[j - 1]     # maker SELL = a lifted offer
            bid = p[j] if sd[j] == "BUY" else p[j - 1]
            mid = 0.5 * (ask + bid)
            if ask >= bid and mid > 0:
                gaps.append(1e4 * (ask - bid) / mid / 2)
    out["half_spread_bp_med"] = float(np.median(gaps)) if gaps else np.nan
    out["n_spread_pairs"] = len(gaps)
    out["tick_bp"] = float(1e4 * tick / lvl)
    return out


if __name__ == "__main__":
    job = sys.argv[1]
    if job == "days":
        days_job(*sys.argv[2:4])
    elif job == "minute":
        minute_job(*sys.argv[2:4])
    elif job == "trades":
        trade_job(*sys.argv[2:4])
    elif job == "probe":
        ex = meta(write=False)
        print(len(ex), ex[0])
