#!/usr/bin/env python3
"""Ladder v5: R2-08's walk-forward AI prediction for every test minute and coin (the live bot's 'armed' state).

The bot asks the AI every minute whether to keep a 4-sigma bid resting; the research trade lists only record the
minutes when a bid would have filled. This rebuilds R2-08 exactly as scripts/wick1m/trades.py does (scripts/lab
pipeline: levels, features, labels, walk-forward LightGBM by quarter, 60th-percentile threshold) and asks the same
quarterly models for every test minute (core.walk_forward's X_extra), with the features the bot computes
(edge.wick.panel with the 7-day beta behind bid depth and beta).
Check: on the candidate minutes the extra predictions must equal the lab's (trades_<era>.parquet pred).
Writes data/ladder_v5/panel_<era>/<COIN>.parquet (minute, pred) and data/ladder_v5/panel_<era>/thr.csv.

  python scripts/ladder_v5/panel.py main | early     (sets LAB_ERA before the lab is imported)
"""
import gc
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1:
    os.environ["LAB_ERA"] = sys.argv[1]                  # core reads the era at import
sys.path.insert(0, os.path.join(ROOT, "scripts", "lab"))
import core  # noqa: E402
import run as RUN  # noqa: E402
import variants as VV  # noqa: E402
from edge import wick  # noqa: E402


def main(tag):
    t0 = time.time()
    allv = {v["name"]: v for v in VV.VARIANTS + VV.ROUND1B + VV.make_round2()}
    v = allv["R2-08 C29+A11"]
    (ls_d, ex_d, ai_d), = RUN.expand(v)
    data = core.Data(list(ls_d.get("coins") or core.COINS17))
    ls = core.LevelSet(data, **ls_d)
    X = ls.features()
    ex = core.Exit(**ex_d)
    lab = core.labels(ls, ex)
    y = RUN.make_label(lab, ai_d, ls)
    feats = list(ai_d.get("feats", tuple(wick.FEATS)))
    print(f"level set, {len(X)} candidates, labels ({time.time() - t0:.0f}s)", flush=True)
    d = ls.data
    i0 = d.i_test
    rows = {c: np.arange(i0, d.T, dtype=np.int64) for c in ls.coins}
    cf = {c: d.D[c]["cf"] for c in d.D}
    vol = {c: d.D[c]["vol"] for c in d.D}
    pn = wick.panel(cf, vol, ls.coins, d.idx, k=ls.k, lookback=ls.L, keep_rows=rows)
    parts = []
    for c in ls.coins:
        f = pn.pop(c)[list(wick.FEATS)].copy()
        r = rows[c]
        f["bid_depth_bp"] = (ls.k * ls.sig[c][r] * 1e4).astype(np.float32)   # as LevelSet.features (7-day beta)
        f["beta"] = ls.beta[c][r].astype(np.float32)
        f["coin"], f["pos"], f["ts"] = c, r, d.idx[r]
        f = f.reset_index(drop=True)
        parts.append(f)
        gc.collect()
    Xe = pd.concat(parts, ignore_index=True)
    del parts, pn
    gc.collect()
    print(f"extra rows {len(Xe):,} ({time.time() - t0:.0f}s)", flush=True)
    pred, thr, px, tx = core.walk_forward(
        X, y, feats, params=ai_d.get("params"), seeds=ai_d.get("seeds", (7, 11, 23)), freq=ai_d.get("freq", "Q"),
        window_days=ai_d.get("window_days"), weight=ai_d.get("weight", "episode"), halflife=ai_d.get("halflife"),
        thr_q=ai_d.get("thr_q", 0.5), thr_abs=ai_d.get("thr_abs"), objective=ai_d.get("objective"),
        monotone=ai_d.get("monotone"), rounds=ai_d.get("rounds"), X_extra=Xe)
    print(f"walk-forward done ({time.time() - t0:.0f}s)", flush=True)
    # check: extra predictions at candidate minutes = the lab's candidate predictions
    cand = X[X.ts >= core.TEST0][["coin", "pos"]].copy()
    cand["pred"] = pred[cand.index].to_numpy()
    m = Xe[["coin", "pos"]].copy()
    m["px"] = px.to_numpy()
    j = cand.merge(m, on=["coin", "pos"], how="left").dropna()
    err = float(np.abs(j.pred - j.px).max()) if len(j) else np.nan
    print(f"check: {len(j):,} candidate minutes, max |pred - extra pred| = {err:.2e}", flush=True)
    tr = pd.read_parquet(os.path.join(ROOT, "reports", "wick1m", f"trades_{tag}.parquet"))
    out = os.path.join(ROOT, "data", "ladder_v5", f"panel_{tag}")
    os.makedirs(out, exist_ok=True)
    Xe["pred"] = px.to_numpy().astype(np.float32)
    Xe["thr"] = tx.to_numpy().astype(np.float32)
    q = Xe.groupby(pd.PeriodIndex(Xe.ts, freq="Q")).thr.first()
    q.rename("thr").to_frame().assign(quarter=lambda z: z.index.astype(str)).to_csv(os.path.join(out, "thr.csv"), index=False)
    for c, g in Xe.groupby("coin"):
        g[["ts", "pred"]].reset_index(drop=True).to_parquet(os.path.join(out, f"{c}.parquet"), index=False)
    # second check against the stored trade list: trades' pred vs extra pred at the trade minute
    pm = Xe.set_index(["coin", "ts"]).pred
    k = [(c, t) for c, t in zip(tr.coin, tr.ts)]
    got = np.array([pm.get(x, np.nan) for x in k])
    ok = np.isfinite(got) & np.isfinite(tr.pred.to_numpy())
    print(f"check vs trades_{tag}.parquet: {ok.sum()} trades, max |diff| = "
          f"{float(np.abs(got[ok] - tr.pred.to_numpy()[ok]).max()):.2e}", flush=True)
    armed = (Xe.pred > Xe.thr).groupby(Xe.coin).mean()
    print("share of minutes armed by coin:\n" + armed.round(3).to_string(), flush=True)
    print(f"done ({time.time() - t0:.0f}s) -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
