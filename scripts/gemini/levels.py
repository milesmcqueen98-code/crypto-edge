#!/usr/bin/env python3
"""Gemini venue test (reports/gemini_prereg.md), step 1: the frozen R2-08 bid levels and AI decisions at every
minute of the sample days, from Coinbase 1-minute data.

- R2-08 = lab base + A11 (7-day beta) + C29 (label net_real, threshold at the 60th percentile), seeds 7/11/23.
- The walk-forward models are trained on Coinbase candidates only, exactly as in the lab; the same models score every
  minute of the out-of-sample sample days (X_extra), with the features the lab builds (known at t-1).
- Parity: the reproduced predictions on R2-08's stored trades (reports/wick1m/trades_main.parquet) are printed.

Writes data/gemini/levels.parquet: ts, coin, fair_log, sig, lvl4 (Coinbase tick-floored, as the bot), pred, thr.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "lab"))
import core  # noqa: E402
from edge import wick  # noqa: E402

DAYS = pd.date_range("2024-01-01", "2026-11-01", freq="MS")
OUT = os.path.join(ROOT, "data", "gemini")


def main():
    data = core.Data(core.COINS17)
    ls = core.LevelSet(data, core.COINS17, L=60, k=4.0, wsig=4320, wbeta=10080, ref="btc", side=1)
    X = ls.features()
    ex = core.Exit(theta=0.6, H=60)
    lab = core.labels(ls, ex)
    y = lab["net_real"].clip(-400, 400)
    print(f"candidates: {len(X)}", flush=True)

    # every minute of the sample days, per coin: features as in LevelSet.features (wick.panel, 3-day beta for the
    # z-scores; bid_depth_bp and beta from the level set's 7-day beta)
    idx = data.idx
    pos_day = {}
    for d in DAYS:
        i0 = idx.get_indexer([d])[0]
        if i0 >= 0:
            pos_day[d] = np.arange(i0, min(i0 + 1440, len(idx)))
    keep = np.concatenate(list(pos_day.values()))
    cf = {c: data.D[c]["cf"] for c in data.D}
    vol = {c: data.D[c]["vol"] for c in data.D}
    pn = wick.panel(cf, vol, ls.coins, idx, k=4.0, lookback=60, keep_rows={c: keep for c in ls.coins})
    f_btc = data.lp["BTC"]
    rows = []
    for c in ls.coins:
        f = pn[c][wick.FEATS].copy()
        p = pn[c]["pos"].to_numpy()
        f["bid_depth_bp"] = (4.0 * ls.sig[c][p] * 1e4).astype(np.float32)
        f["beta"] = ls.beta[c][p].astype(np.float32)
        x = data.lp[c]
        fair = core.shift(x, 60) + ls.beta[c] * (core.shift(f_btc, 1) - core.shift(f_btc, 60))
        f["fair_log"] = fair[p]
        f["sig"] = ls.sig[c][p]
        f["lvl4"] = ls.lvl[c][p]
        f["cb_close"] = data.D[c]["close"][p]
        f["cb_low"] = data.D[c]["low"][p]
        f["coin"], f["ts"], f["pos"] = c, idx[p], p
        rows.append(f)
    Xe = pd.concat(rows, ignore_index=True)
    Xe = Xe[np.isfinite(Xe.sig)]
    print(f"sample-day minutes with a level: {len(Xe)}", flush=True)

    pred, thr, pred_x, thr_x = core.walk_forward(X, y, list(wick.FEATS), seeds=(7, 11, 23), thr_q=0.6, X_extra=Xe)
    Xe["pred"], Xe["thr"] = pred_x, thr_x

    # parity with the stored R2-08 trades
    tm = pd.read_parquet(os.path.join(ROOT, "reports", "wick1m", "trades_main.parquet"))
    key = pd.Series(pred.to_numpy(), index=pd.MultiIndex.from_arrays([X.coin, X.pos]))
    tkey = pd.Series(thr.to_numpy(), index=pd.MultiIndex.from_arrays([X.coin, X.pos]))
    got = key.reindex(pd.MultiIndex.from_arrays([tm.coin, tm.ei])).to_numpy()
    gthr = tkey.reindex(pd.MultiIndex.from_arrays([tm.coin, tm.ei])).to_numpy()
    ok = np.isfinite(got) & np.isfinite(tm.pred)
    print(f"parity on {ok.sum()} of {len(tm)} stored trades: max |pred diff| {np.nanmax(np.abs(got[ok] - tm.pred[ok])):.2e},"
          f" max |thr diff| {np.nanmax(np.abs(gthr[ok] - tm.thr[ok])):.2e}", flush=True)
    # the same model scores a stored candidate minute identically whether it comes from X or X_extra
    both = Xe.merge(X[["coin", "pos"]].assign(px_=pred.to_numpy()), on=["coin", "pos"])
    if len(both):
        print(f"X vs X_extra consistency on {len(both)} shared minutes: "
              f"max |diff| {np.nanmax(np.abs(both.pred - both.px_)):.2e}", flush=True)

    os.makedirs(OUT, exist_ok=True)
    cols = ["ts", "coin", "fair_log", "sig", "lvl4", "cb_close", "cb_low", "pred", "thr"] + list(wick.FEATS)
    Xe[cols].to_parquet(os.path.join(OUT, "levels.parquet"), index=False)
    # the R2-08 candidates (Coinbase fills of the 4-sigma bid) on the sample days, with the AI decision
    Xc = X.assign(pred=pred.to_numpy(), thr=thr.to_numpy(), net_real=lab.net_real.to_numpy(), gross=lab.gross.to_numpy())
    Xc = Xc[Xc.ts.dt.floor("D").isin(DAYS)]
    Xc[["ts", "coin", "pos", "pred", "thr", "net_real", "gross", "sig", "px"]].to_parquet(
        os.path.join(OUT, "cb_candidates.parquet"), index=False)
    print(f"saved {len(Xe)} minute rows and {len(Xc)} Coinbase candidates on sample days", flush=True)


if __name__ == "__main__":
    main()
