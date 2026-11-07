#!/usr/bin/env python3
"""Wick v4 sub-minute tests on Coinbase trade-by-trade data (reports/wick_v4_prereg.md).

S1 (latency): for each deeper rung (6/8 sigma) that the minute simulator fills inside the parent's own minute, find when
the parent (4 sigma) bid is traded through, then ask whether the deeper bid, placed L seconds later, is still
traded through afterwards. Two placement rules:
  rest  - post-only: the deeper bid can rest only if the last trade at placement is above it;
  cross - if the market is already through the deeper level at placement, buy at once (taker) at the level.
S3 (fast take-profit): whether the parent's take-profit price trades within the fill minute after the fill plus L
seconds; the minute research only allows it from the next minute.
Also descriptive: BTC's move from the start of the fill minute to the parent fill, against the fill's outcome
(the post-hoc 'BTC flat' lead).

Inputs: trades_*.parquet from the fetch-trades workflow artifacts (a directory given as argv[1]) and
reports/wick_v4/events_research.csv (levels and minute-simulator outcomes per event). Writes reports/wick_v4/subminute_*.csv.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "reports", "wick_v4")
LAT = (0.5, 1, 2, 5, 15, 30, 60)
THETA = 0.6


def ticks():
    t = pd.read_csv(os.path.join(ROOT, "reports", "wick1m", "spot_ticks_wide.csv"))
    d = {r.coin: float(r.tick) for r in t.itertuples() if np.isfinite(r.tick)}
    d["PEPE"] = 1e-8
    return d


def main(art_dir):
    T = pd.concat([pd.read_parquet(f) for f in glob.glob(os.path.join(art_dir, "**", "trades_*.parquet"), recursive=True)])
    T = T.sort_values(["window_id", "time", "trade_id"])
    W = pd.read_csv(os.path.join(ROOT, "reports", "wick_v4", "windows.csv"), parse_dates=["start", "end"])
    got = T.groupby("window_id").size()
    W["n_trades"] = W.window_id.map(got).fillna(0).astype(int)
    print(f"{len(T):,} trades in {int((W.n_trades > 0).sum())} of {len(W)} windows")
    by_win = {w: g for w, g in T.groupby("window_id")}
    alt_win = {(r.product.split("-")[0], r.start): r.window_id for r in W[W.kind == "alt"].itertuples()}
    btc_win = {r.start: r.window_id for r in W[W.kind == "btc"].itertuples()}
    # per-event research inputs (levels and minute-simulator outcomes), exported from pre_main + trades_main
    P = pd.read_csv(os.path.join(ROOT, "reports", "wick_v4", "events_research.csv"), parse_dates=["ts"])
    tk = ticks()
    par = P[(P.k == 4.0) & P.filled]
    rows, deep_rows = [], []
    for r in par.itertuples():
        wid = alt_win.get((r.coin, r.ts))
        g = by_win.get(wid)
        if g is None or not len(g):
            continue
        tick = tk.get(r.coin, np.nan)
        t0 = r.ts
        tt = ((g.time - t0).dt.total_seconds()).to_numpy()
        px = g.price.to_numpy()
        in_min = tt < 60
        hit4 = np.nonzero(in_min & (px <= r.px - tick * (1 - 1e-9)))[0]
        rec = dict(ts=r.ts, coin=r.coin, trades_in_minute=int(in_min.sum()), through4=len(hit4) > 0)
        if len(hit4):
            i4 = hit4[0]
            s4 = tt[i4]
            rec["t4_s"] = s4
            tp = r.px * np.exp(THETA * 4.0 * r.sig)
            outcome = r.g_tp if r.tp_hit else r.g60
            rec.update(outcome_bp=outcome, research_tp=bool(r.tp_hit), gain_if_tp_bp=1e4 * np.log(tp / r.px) - outcome)
            for L in LAT:                                      # S3: take-profit live L seconds after the fill
                m = (tt >= s4 + L) & in_min & (px >= tp + tick * (1 - 1e-9))
                rec[f"tp_same_min_{L}s"] = bool(m.any())
            bw = btc_win.get(r.ts)                             # BTC's move from the minute start to our fill
            bg = by_win.get(bw)
            if bg is not None and len(bg):
                bt = (bg.time - t0).dt.total_seconds().to_numpy()
                bp = bg.price.to_numpy()
                if (bt <= s4).any():
                    rec["btc_to_fill_bp"] = 1e4 * np.log(bp[bt <= s4][-1] / bp[0])
            # S1: deeper rungs of this parent that the minute simulator filled in the parent's own minute
            for d in P[(P.ts == r.ts) & (P.coin == r.coin) & (P.k > 4)].itertuples():
                lvl = d.lvl
                thr = lvl - tick * (1 - 1e-9)
                drec = dict(ts=r.ts, coin=r.coin, k=d.k, t4_s=s4)
                deep_hits = np.nonzero(in_min & (px <= thr))[0]
                drec["first_deep_s"] = tt[deep_hits[0]] if len(deep_hits) else np.nan
                drec["research_pnl_bp"] = d.g_tp if d.tp_hit else d.g60
                for L in LAT:
                    tl_ = s4 + L
                    before = np.nonzero(tt <= tl_)[0]
                    last_px = px[before[-1]] if len(before) else px[0]
                    later = (tt > tl_) & in_min & (px <= thr)
                    drec[f"rest_{L}s"] = bool(last_px > lvl and later.any())
                    drec[f"cross_{L}s"] = bool(last_px <= lvl or later.any()) and tl_ < 60
                deep_rows.append(drec)
        rows.append(rec)
    E = pd.DataFrame(rows)
    D = pd.DataFrame(deep_rows)
    os.makedirs(OUT, exist_ok=True)
    E.to_csv(os.path.join(OUT, "subminute_parents.csv"), index=False)
    D.to_csv(os.path.join(OUT, "subminute_deeper.csv"), index=False)
    pd.set_option("display.width", 220)
    print(f"\nparents with trades: {len(E)}; trade-through of the 4-sigma bid seen in the trades: {E.through4.mean():.1%}")
    if len(D):
        print(f"\nS1: {len(D)} same-minute deeper fills (simulator). Share still caught when reacting L s after the 4σ fill:")
        tab = pd.DataFrame({f"{L}s": [D[f"rest_{L}s"].mean(), D[f"cross_{L}s"].mean(),
                                      (D[f"rest_{L}s"] * D.research_pnl_bp).sum() / D.research_pnl_bp.sum(),
                                      (D[f"cross_{L}s"] * D.research_pnl_bp).sum() / D.research_pnl_bp.sum()]
                            for L in LAT}, index=["rest: share of fills", "cross: share of fills",
                                                  "rest: share of their P&L", "cross: share of their P&L"])
        print(tab.round(3).to_string())
        gap = (D.first_deep_s - D.t4_s)
        print("seconds from the 4σ trade-through to the deeper trade-through: median %.1f, 25%% %.1f, 75%% %.1f" %
              (gap.median(), gap.quantile(0.25), gap.quantile(0.75)))
    f = E[E.through4 == True]  # noqa: E712
    if len(f):
        print(f"\nS3: {len(f)} parent fills; take-profit price traded inside the fill minute after L seconds:")
        s3 = pd.DataFrame({f"{L}s": [f[f"tp_same_min_{L}s"].mean(),
                                     (f[f"tp_same_min_{L}s"] & ~f.research_tp).mean(),
                                     (f.gain_if_tp_bp * (f[f"tp_same_min_{L}s"] & ~f.research_tp)).mean()]
                           for L in LAT}, index=["share with a same-minute TP", "same-minute TP where research had none",
                                                 "mean gain per parent fill, bp"])
        print(s3.round(3).to_string())
        if "btc_to_fill_bp" in f:
            b = f.dropna(subset=["btc_to_fill_bp"])
            b = b.assign(q=pd.qcut(b.btc_to_fill_bp, 5, labels=False, duplicates="drop"))
            print("\nBTC move from minute start to our fill (quintiles) vs outcome (descriptive):")
            print(b.groupby("q").agg(n=("outcome_bp", "size"), btc_bp=("btc_to_fill_bp", "mean"),
                                     outcome_bp=("outcome_bp", "mean")).round(1).to_string())


if __name__ == "__main__":
    main(sys.argv[1])
