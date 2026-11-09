#!/usr/bin/env python3
"""Signal lab 2 (reports/signal_lab/prospective_prereg.md, "Data"): the print windows to fetch for F6.

For every candidate (coin, q) of both eras the window [q - 30 min, q); overlapping or touching windows of one product
are merged, so every candidate's window lies inside exactly one merged window and no print is fetched twice.

Writes
  reports/signal_lab/prints/windows.csv   window_id, product, start, end, n_cand, est_prints, shard
  reports/signal_lab/prints/adv_daily.csv.gz   coin, day, adv_usd (the ADV table the runner joins on)
  reports/signal_lab/prints/candle_usd.csv.gz  era, coin, ts, candle_usd_30, candle_vol_30, ret_30 (QA only)

ADV (prereg deviation 1; the spot part of daily_stats in scripts/wick1m/sim.py): per minute USD = close x volume over
minutes with volume > 0 (load_venue drops the others; close is ffilled but multiplies a zero volume there), summed per
UTC day; days without volume are missing; ADV on day D = the median of the positive daily totals over the 30 calendar
days D-30 .. D-1 (rolling 30 rows, at least 10 values, shifted one day). Days before 2024-01-01 come from
data/minute_early, later days from data/minute, as one continuous series per coin.

The print-count estimate (est_prints) is candle USD in the window / USD_PER_PRINT, calibrated on edge hunt 2's parent
fetch (8 shard logs: 21,445,897 prints over 18.74 bn candle USD, about $874 a print). It only sizes and balances shards.
Coin by coin; nothing loads all minute data at once.

usage: python scripts/signal_lab/prints_windows.py <n_shards>
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SL = os.path.join(ROOT, "reports", "signal_lab")
OUT = os.path.join(SL, "prints")
PRE = pd.Timedelta(minutes=30)
USD_PER_PRINT = 874.0
SPLIT = pd.Timestamp("2024-01-01")
# fetch cost model, from the same 8 logs: about 1.7 s of cursor search per window plus 0.37 s per page of 1,000 prints
SEC_PER_WINDOW, SEC_PER_PRINT = 1.7, 0.37e-3


def candidates():
    parts = []
    for era in ("main", "early"):
        c = pd.read_csv(os.path.join(SL, f"candidates_{era}.csv.gz"), parse_dates=["ts"])
        c["era"] = era
        parts.append(c)
    C = pd.concat(parts, ignore_index=True)
    C["ts"] = C.ts.astype("datetime64[ns]")
    assert not C.duplicated(["coin", "ts"]).any()
    return C


def merge(C):
    rows = []
    for coin, g in C.sort_values(["coin", "ts"]).groupby("coin"):
        st = (g.ts - PRE).to_numpy()
        en = g.ts.to_numpy()
        cs, ce, n = st[0], en[0], 1
        for s, e in zip(st[1:], en[1:]):
            if s <= ce:                                   # overlapping or touching: extend
                ce, n = max(ce, e), n + 1
            else:
                rows.append((f"{coin}-USD", coin, cs, ce, n))
                cs, ce, n = s, e, 1
        rows.append((f"{coin}-USD", coin, cs, ce, n))
    W = pd.DataFrame(rows, columns=["product", "coin", "start", "end", "n_cand"])
    return W


def minutes(coin):
    """One continuous minute series per coin: minute_early before 2024-01-01, minute from then on."""
    parts = []
    for src, keep in (("minute_early", lambda t: t < SPLIT), ("minute", lambda t: t >= SPLIT)):
        p = os.path.join(ROOT, "data", src, f"{coin}.parquet")
        if os.path.exists(p):
            m = pd.read_parquet(p, columns=["ts", "open", "close", "volume"])
            m = m.drop_duplicates("ts")
            parts.append(m[keep(m.ts)])
    m = pd.concat(parts, ignore_index=True).sort_values("ts")
    m["ts"] = m.ts.astype("datetime64[ns]")
    m = m[m.volume > 0]                                   # load_venue: m[m.volume > 0]
    m = m.set_index("ts")
    return m


def adv_daily(m):
    """daily_stats' spot part on a continuous daily index."""
    usd = (m.close.astype(np.float64).fillna(0.0) * m.volume.astype(np.float64))
    day = usd.resample("D").sum()
    return day.where(day > 0).rolling(30, min_periods=10).median().shift(1)


def adv_daily_bounded(m, lo, hi):
    """The same, on the simulator's era-bounded minute index (PERIODS in sim.py), for the QA comparison only."""
    mm = m[(m.index >= lo) & (m.index < hi)]
    idx = pd.date_range(lo, hi, freq="min", inclusive="left")
    usd = pd.Series(0.0, index=idx)
    usd.loc[mm.index] = (mm.close.astype(np.float64).fillna(0.0) * mm.volume.astype(np.float64)).to_numpy()
    day = usd.resample("D").sum()
    return day.where(day > 0).rolling(30, min_periods=10).median().shift(1)


def window_sums(m, start, end):
    t = m.index.values
    usd = np.concatenate([[0.0], np.cumsum((m.close.astype(np.float64) * m.volume.astype(np.float64)).to_numpy())])
    vol = np.concatenate([[0.0], np.cumsum(m.volume.astype(np.float64).to_numpy())])
    a = np.searchsorted(t, np.asarray(start, dtype="datetime64[ns]"), "left")
    b = np.searchsorted(t, np.asarray(end, dtype="datetime64[ns]"), "left")
    return usd[b] - usd[a], vol[b] - vol[a]


def shards(W, n):
    """Greedy longest-processing-time assignment on the estimated seconds."""
    cost = SEC_PER_WINDOW + SEC_PER_PRINT * W.est_prints.to_numpy()
    load = np.zeros(n)
    out = np.empty(len(W), dtype=np.int64)
    for i in np.argsort(-cost, kind="stable"):
        j = int(np.argmin(load))
        out[i] = j
        load[j] += cost[i]
    return out, load


def main(n_shards=16):
    C = candidates()
    W = merge(C)
    W = W.sort_values(["product", "start"]).reset_index(drop=True)
    W.insert(0, "window_id", np.arange(len(W)))
    W["est_usd"] = np.nan
    adv_rows, cu_rows = [], []
    bounded = {"main": ("2024-01-01", "2026-11-06"), "early": ("2021-01-01", "2024-01-01")}
    for coin in sorted(C.coin.unique()):
        m = minutes(coin)
        g = W[W.coin == coin]
        W.loc[g.index, "est_usd"] = window_sums(m, g.start.to_numpy(), g.end.to_numpy())[0]
        a = adv_daily(m)
        adv_rows.append(pd.DataFrame({"coin": coin, "day": a.index, "adv_usd": a.to_numpy()}).dropna())
        cc = C[C.coin == coin]
        usd30, vol30 = window_sums(m, (cc.ts - PRE).to_numpy(), cc.ts.to_numpy())
        # price change over the window from candles: last close before q against the first open at or after q-30m
        t = m.index.values
        i0 = np.searchsorted(t, (cc.ts - PRE).to_numpy().astype("datetime64[ns]"), "left")
        i1 = np.searchsorted(t, cc.ts.to_numpy().astype("datetime64[ns]"), "left") - 1
        op = m.open.astype(np.float64).to_numpy()
        cl = m.close.astype(np.float64).to_numpy()
        ok = (i1 >= i0) & (i0 < len(t))
        ret = np.full(len(cc), np.nan)
        ret[ok] = np.log(cl[i1[ok]] / op[i0[ok]])
        day = cc.ts.dt.floor("D")
        adv_c = a.reindex(day).to_numpy()
        adv_b = np.full(len(cc), np.nan)
        for era in ("main", "early"):
            e = (cc.era == era).to_numpy()
            if e.any():
                ab = adv_daily_bounded(m, *bounded[era])
                adv_b[e] = ab.reindex(day[e]).to_numpy()
        cu_rows.append(pd.DataFrame({"era": cc.era.to_numpy(), "coin": coin, "ts": cc.ts.to_numpy(),
                                     "candle_usd_30": usd30, "candle_vol_30": vol30, "ret_30": ret,
                                     "adv_usd": adv_c, "adv_usd_era_bounded": adv_b}))
        print(f"{coin}: {len(g)} windows, {len(cc)} candidates, {W.loc[g.index, 'est_usd'].sum() / 1e9:.2f} bn USD",
              flush=True)
    W["est_prints"] = np.round(W.est_usd / USD_PER_PRINT).astype(np.int64)
    W["shard"], load = shards(W, n_shards)
    os.makedirs(OUT, exist_ok=True)
    cols = ["window_id", "product", "start", "end", "n_cand", "est_prints", "shard"]
    W[cols].to_csv(os.path.join(OUT, "windows.csv"), index=False, date_format="%Y-%m-%d %H:%M:%S")
    A = pd.concat(adv_rows, ignore_index=True)
    A.to_csv(os.path.join(OUT, "adv_daily.csv.gz"), index=False, date_format="%Y-%m-%d")
    CU = pd.concat(cu_rows, ignore_index=True)
    CU.to_csv(os.path.join(OUT, "candle_usd.csv.gz"), index=False, date_format="%Y-%m-%d %H:%M:%S")
    dur = (W.end - W.start).dt.total_seconds() / 60
    print(f"candidates {len(C)}, merged windows {len(W)}, minutes {dur.sum():.0f} (median {dur.median():.0f}, "
          f"max {dur.max():.0f}), est prints {W.est_prints.sum() / 1e6:.1f} M")
    print(f"est seconds single-threaded {SEC_PER_WINDOW * len(W) + SEC_PER_PRINT * W.est_prints.sum():.0f}; "
          f"per shard ({n_shards}): max {load.max():.0f}, min {load.min():.0f}")


if __name__ == "__main__":
    main(*[int(x) for x in sys.argv[1:2]])
