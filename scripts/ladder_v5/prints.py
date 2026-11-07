#!/usr/bin/env python3
"""Ladder v5, step 1d: who sold to us and who bid beside us, from Coinbase trade-by-trade prints.

Runs on GitHub Actions (.github/workflows/ladder-prints.yml) over the wick v4 trade artifacts: every print in the
fill minute and the next minute of each 4-sigma parent fill in Jan 2025 - Nov 2026 (reports/wick_v4/windows.csv).
Per parent (only derived numbers are written; raw prints stay in the artifacts):
  through_s        seconds from the minute start to the first print one tick below our bid (our fill)
  at_lvl_pre_usd   USD printed exactly at our price before that (other bids at our price: who bid beside us)
  at_lvl_usd       USD printed exactly at our price in the fill minute
  below_usd        USD printed below our price in the fill minute; taker_sell_share of it (maker side = buy)
  n_sweeps, max_sweep_usd, first_sweep_usd, first_sweep_levels, first_sweep_depth_bp: prints grouped by timestamp
                   (one aggressive order) at or below our price; the first one is the order that reached us
  approach1_s, approach2_s  seconds from the first print within 1 (2) sigma above our bid to our fill
  mo_<L>s          last print L seconds after our fill vs our price, bp (L = 1, 2, 5, 10, 30, 60)
  min_after_bp, min_after_s  lowest print in the 2 minutes after our fill, and when
Writes reports/ladder_v5/prints_parents.csv.  usage: python scripts/ladder_v5/prints.py <artifact dir>
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "reports", "ladder_v5")
LAGS = (1, 2, 5, 10, 30, 60)


def ticks():
    t = pd.read_csv(os.path.join(ROOT, "reports", "wick1m", "spot_ticks_wide.csv"))
    d = {r.coin: float(r.tick) for r in t.itertuples() if np.isfinite(r.tick)}
    d["PEPE"] = 1e-8
    return d


def main(art):
    T = pd.concat([pd.read_parquet(f) for f in glob.glob(os.path.join(art, "**", "trades_*.parquet"), recursive=True)])
    T = T.sort_values(["window_id", "time", "trade_id"])
    W = pd.read_csv(os.path.join(ROOT, "reports", "wick_v4", "windows.csv"), parse_dates=["start", "end"])
    alt = {(r.product.split("-")[0], r.start): r.window_id for r in W[W.kind == "alt"].itertuples()}
    by = {w: g for w, g in T.groupby("window_id")}
    P = pd.read_pickle(os.path.join(OUT, "frozen", "pre_hunt_main.pkl"))
    par = P[(P.k == 4.0) & P.filled]
    tk = ticks()
    rows = []
    for r in par.itertuples():
        g = by.get(alt.get((r.coin, r.ts)))
        if g is None or not len(g):
            continue
        tick = tk.get(r.coin, np.nan)
        lvl = float(r.lvl)
        t = ((g.time - r.ts).dt.total_seconds()).to_numpy()
        px = g.price.to_numpy(np.float64)
        sz = g.size.to_numpy(np.float64)
        usd = px * sz
        side = g.side.to_numpy()
        m0 = t < 60
        thr = lvl - tick * (1 - 1e-9)
        hit = np.nonzero(m0 & (px <= thr))[0]
        rec = dict(ts=r.ts, coin=r.coin, lvl=lvl, n_prints_min0=int(m0.sum()))
        at = np.abs(px - lvl) <= 0.5 * tick
        below = m0 & (px <= thr)
        rec["at_lvl_usd"] = float(usd[m0 & at].sum())
        rec["below_usd"] = float(usd[below].sum())
        rec["taker_sell_share"] = float(usd[below & (side == "buy")].sum() / usd[below].sum()) if below.any() else np.nan
        if len(hit):
            i4 = hit[0]
            s4 = t[i4]
            rec["through_s"] = float(s4)
            rec["at_lvl_pre_usd"] = float(usd[(t <= s4) & at].sum())
            # sweeps: prints with the same timestamp at or below our price in the fill minute
            sub = g[m0 & (px <= lvl + 0.5 * tick)]
            sw = sub.assign(usd=sub.price * sub["size"]).groupby("time").agg(usd=("usd", "sum"), lo=("price", "min"),
                                                                             n=("price", "nunique"))
            rec["n_sweeps"] = int(len(sw))
            rec["max_sweep_usd"] = float(sw.usd.max()) if len(sw) else np.nan
            first_t = g.time.iloc[i4]
            if first_t in sw.index:
                f = sw.loc[first_t]
                rec.update(first_sweep_usd=float(f.usd), first_sweep_levels=int(f.n),
                           first_sweep_depth_bp=float(1e4 * np.log(lvl / f.lo)))
            sig = float(np.exp(r.lvl) * 0 + 1)  # placeholder (sigma from the trade list below)
            for L in LAGS:
                b = np.nonzero(t <= s4 + L)[0]
                rec[f"mo_{L}s"] = float(1e4 * np.log(px[b[-1]] / lvl)) if len(b) else np.nan
            after = t > s4
            if after.any():
                j = np.argmin(np.where(after, px, np.inf))
                rec["min_after_bp"] = float(1e4 * np.log(px[j] / lvl))
                rec["min_after_s"] = float(t[j] - s4)
        rows.append(rec)
    D = pd.DataFrame(rows)
    # approach speed needs sigma: from the trade list
    tr = pd.read_parquet(os.path.join(ROOT, "reports", "wick1m", "trades_main.parquet"))[["ts", "coin", "sig"]]
    D = D.merge(tr, on=["ts", "coin"], how="left")
    ap1, ap2 = [], []
    for r in D.itertuples():
        g = by.get(alt.get((r.coin, r.ts)))
        if g is None or not np.isfinite(getattr(r, "through_s", np.nan)) or not np.isfinite(r.sig):
            ap1.append(np.nan)
            ap2.append(np.nan)
            continue
        t = ((g.time - r.ts).dt.total_seconds()).to_numpy()
        px = g.price.to_numpy(np.float64)
        out = []
        for m in (1.0, 2.0):
            near = np.nonzero((t <= r.through_s) & (px <= r.lvl * np.exp(m * r.sig)))[0]
            out.append(float(r.through_s - t[near[0]]) if len(near) else np.nan)
        ap1.append(out[0])
        ap2.append(out[1])
    D["approach1_s"], D["approach2_s"] = ap1, ap2
    os.makedirs(OUT, exist_ok=True)
    D.to_csv(os.path.join(OUT, "prints_parents.csv"), index=False)
    print(f"{len(T):,} prints; {len(D)} parents with prints; through seen {D.through_s.notna().mean():.1%}")
    print(D.describe().T.round(2).to_string())


if __name__ == "__main__":
    main(sys.argv[1])
