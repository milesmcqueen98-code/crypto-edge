#!/usr/bin/env python3
"""H10 (XQ) step 3 (GitHub Actions, sharded by pair): fetch 1-minute Exchange candles for each pair on its universe
days (data/hunt/h10xq/universe.parquet: top-10 books of each quote set by trailing ADV, + 4 warm-up days) and any USD
leg not on disk; compute the SPEC's cross residual, fair value and sigma; write

  data/hunt/h10xq/win/win_<shard>.parquet   DEV-day candidate windows: every minute t whose bid at the loosest grid
                                            level (k = 3) traded through (open > bid, low <= bid - 1 tick), minutes
                                            t-1 .. t+90 of the pair and both legs, with F and sigma known at t-1
  data/hunt/h10xq/win/diag_<shard>.parquet  DEV days only: per pair-day, the deepest low vs F (log and sigma units)
  data/hunt/h10xq/hold_raw/<prod>__<shard>.parquet   raw candles from 2026-05-27 (HOLD + warm-up), NOT processed
                                            here: HOLD is computed only after the freeze commit.

SPEC (reports/hunt/h10xq/SPEC.md): c = log(X-Q close) - log(X-USD close / Q-USD close) on minutes where all three
traded; c_bar = trailing 24 h median of c; sigma_c = trailing 3-day std of c, both known at t-1;
F = (X-USD / Q-USD at t-1) * exp(c_bar); bid = F * exp(-k sigma_c) floored to the pair's quote_increment.
Engineering choices (REPORT): at least 30 joint minutes for c_bar and 120 for sigma_c; leg closes forward-filled at
most 30 minutes; statistics carried at most 6 h past the last joint minute.
usage: python scripts/hunt/h10xq/features.py <shard> <nshards>
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from cbx import Candles  # noqa: E402
import common  # noqa: E402

DATA = os.path.join(ROOT, "data", "hunt", "h10xq")
HOLD0 = pd.Timestamp("2026-06-01")
RAW0 = pd.Timestamp("2026-05-27")
DEV_DAYS = set(list(pd.date_range("2022-01-01", "2023-12-31")) + list(pd.date_range("2025-01-01", "2026-05-31")))
K_MIN = 3.0
W_BEFORE, W_AFTER = 1, 90
MIN_MED, MIN_SIG = 30, 120
FFILL, STALE = 30, 360
WARM = 4
LOCAL = {"minute": (pd.Timestamp("2024-01-01"), pd.Timestamp("2026-11-06")),
         "minute_early": (pd.Timestamp("2021-01-01"), pd.Timestamp("2024-01-01"))}


def day_ranges(days):
    days = sorted(days)
    out, s, prev = [], days[0], days[0]
    for d in days[1:] + [None]:
        if d is None or (d - prev).days > 1:
            out.append((s, prev + pd.Timedelta(days=1)))
            s = d
        prev = d if d is not None else prev
    return out


def local_leg(coin, cache={}):
    if coin not in cache:
        parts = [common.load_minute(coin, src) for src in ("minute_early", "minute")]
        parts = [p for p in parts if p is not None]
        cache[coin] = pd.concat(parts).sort_index() if parts else None
        if cache[coin] is not None:
            cache[coin] = cache[coin][~cache[coin].index.duplicated()]
    return cache[coin]


def local_cover(coin, d):
    for src, (a, b) in LOCAL.items():
        if a <= d < b and os.path.exists(os.path.join(common.DATA, src, f"{coin}.parquet")):
            return True
    return False


class Store:
    """Fetched candles per product, fetched once per (product, day)."""

    def __init__(self, C):
        self.C, self.have = C, {}

    def get(self, prod, days):
        h = self.have.setdefault(prod, {"days": set(), "df": []})
        new = sorted(set(days) - h["days"])
        for a, b in (day_ranges(new) if new else []):
            d = self.C.range(prod, a, b, 60)
            if len(d):
                h["df"].append(d)
        h["days"] |= set(new)
        if not h["df"]:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        if len(h["df"]) > 1:
            h["df"] = [pd.concat(h["df"], ignore_index=True).drop_duplicates("ts").sort_values("ts")]
        d = h["df"][0]
        d = d[d.volume > 0]
        return d.set_index("ts")


def leg_frame(store, prod, days):
    coin = prod[:-4]
    loc = [d for d in days if local_cover(coin, d)]
    rem = [d for d in days if not local_cover(coin, d)]
    parts = []
    if loc:
        L = local_leg(coin)
        if L is not None:
            parts.append(L[L.index.floor("D").isin(loc)])
    if rem:
        parts.append(store.get(prod, rem))
    parts = [p for p in parts if len(p)]
    if not parts:
        return None
    d = pd.concat(parts).sort_index()
    return d[~d.index.duplicated()]


def features(P, X, Q, idx, tick):
    p, x, q = (F_.reindex(idx) for F_ in (P, X, Q))
    valid = p.close.notna() & x.close.notna() & q.close.notna()
    c = (np.log(p.close) - np.log(x.close) + np.log(q.close))[valid]
    med = c.rolling("24h", min_periods=MIN_MED).median()
    sd = c.rolling("3D", min_periods=MIN_SIG).std()
    med_t = med.reindex(idx).ffill(limit=STALE).shift(1)
    sd_t = sd.reindex(idx).ffill(limit=STALE).shift(1)
    lx = np.log(x.close.ffill(limit=FFILL)).shift(1)
    lq = np.log(q.close.ffill(limit=FFILL)).shift(1)
    logF = lx - lq + med_t
    out = pd.DataFrame({"o": p.open, "h": p.high, "l": p.low, "c": p.close, "v": p.volume,
                        "logF": logF, "sig": sd_t, "cres": c.reindex(idx),
                        "ox": x.open, "cx": x.close, "oq": q.open, "cq": q.close}, index=idx)
    lvl = np.floor(np.exp(out.logF - K_MIN * out.sig) / tick + 1e-9) * tick
    out["cand"] = (out.o > lvl + 0.5 * tick) & (out.l <= lvl - 0.5 * tick)
    return out


def main(shard, nsh):
    U = pd.read_parquet(os.path.join(DATA, "universe.parquet"))
    PR = pd.read_csv(os.path.join(ROOT, "reports", "hunt", "h10xq", "pairs.csv")).set_index("id")
    need = {}
    for pair, g in U.groupby("pair"):
        ds = set()
        for d in g.day:
            ds.update(pd.date_range(d - pd.Timedelta(days=WARM), d))
        need[pair] = sorted(ds)
    load, assign = [0] * nsh, {}
    for pair in sorted(need, key=lambda k: -len(need[k])):
        i = min(range(nsh), key=lambda j: load[j])
        assign[pair] = i
        load[i] += len(need[pair])
    mine = [p for p in need if assign[p] == shard]
    print(f"shard {shard}/{nsh}: pairs {mine} pair-days {load[shard]}", flush=True)
    store, t0 = Store(Candles(rate=8.0)), time.time()
    os.makedirs(os.path.join(DATA, "win"), exist_ok=True)
    os.makedirs(os.path.join(DATA, "hold_raw"), exist_ok=True)
    wins, diags, raw_prods = [], [], set()
    for pair in mine:
        r = PR.loc[pair]
        days = need[pair]
        P = store.get(pair, days)
        X = leg_frame(store, r.base_usd, days)
        Q = leg_frame(store, r.quote_usd, days)
        if P is None or len(P) == 0 or X is None or Q is None:
            print(pair, "missing data", len(P) if P is not None else None, X is None, Q is None, flush=True)
            continue
        idx = pd.DatetimeIndex(np.concatenate([pd.date_range(a, b, freq="min", inclusive="left").to_numpy()
                                               for a, b in day_ranges(days)]))
        Fe = features(P, X, Q, idx, float(r.quote_increment))
        day = Fe.index.floor("D")
        top = set(U[U.pair == pair].day)
        live = day.isin(sorted(top)) & day.isin(sorted(DEV_DAYS)) & (Fe.index < HOLD0)
        cand = Fe.cand.to_numpy() & live
        ci = np.flatnonzero(cand)
        keep = np.zeros(len(Fe), bool)
        for i in ci:
            keep[max(0, i - W_BEFORE): i + W_AFTER + 1] = True
        W = Fe[keep].copy()
        W["cand"] = cand[keep]
        W["pair"] = pair
        wins.append(W.reset_index(names="ts"))
        dv = Fe[live & Fe.l.notna() & Fe.logF.notna()]
        if len(dv):
            dev = np.log(dv.l) - dv.logF
            dg = pd.DataFrame({"dev": dev, "z": dev / dv.sig, "cand": dv.cand,
                               "usd": dv.v * dv.c * np.exp(dv.cq.fillna(np.nan))}).groupby(dv.index.floor("D"))
            D = pd.DataFrame({"min_dev": dg.dev.min(), "min_z": dg.z.min(), "n_cand": dg.cand.sum(),
                              "ts_min": dv.assign(dev=dev).groupby(dv.index.floor("D")).dev.idxmin()})
            D["pair"] = pair
            diags.append(D.reset_index(names="day"))
        for prod, F_ in ((pair, P), (r.base_usd, X), (r.quote_usd, Q)):
            if prod in raw_prods:
                continue
            coin = prod[:-4] if prod.endswith("-USD") else None
            if coin is not None and local_cover(coin, RAW0):
                continue
            hr = F_[F_.index >= RAW0]
            if len(hr):
                hr.reset_index(names="ts").to_parquet(os.path.join(DATA, "hold_raw", f"{prod}__{shard}.parquet"),
                                                      index=False, compression="zstd")
                raw_prods.add(prod)
        print(f"{pair}: days {len(days)} minutes {int(Fe.c.notna().sum())} cand(DEV,top) {len(ci)} "
              f"win rows {int(keep.sum())} | req {store.C.n_req} err {store.C.n_err} {time.time() - t0:.0f}s",
              flush=True)
    if wins:
        pd.concat(wins, ignore_index=True).to_parquet(os.path.join(DATA, "win", f"win_{shard}.parquet"), index=False,
                                                      compression="zstd")
    if diags:
        pd.concat(diags, ignore_index=True).to_parquet(os.path.join(DATA, "win", f"diag_{shard}.parquet"),
                                                       index=False, compression="zstd")
    print("done", store.C.n_req, "requests", store.C.n_err, "errors", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
