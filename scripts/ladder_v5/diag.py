#!/usr/bin/env python3
"""Ladder v5, step 1: where the incumbent loses P&L (reports/ladder_v5_prereg.md, written after this diagnosis).

  - P&L decomposition of the incumbent (gross price gain, maker fees, taker fees, half-spread, impact) by era;
  - oracle replays that bound each leak's prize (perfect exits, selection, sizing; zero costs; idle cash at the
    T-bill rate; front of the queue (theta 1); no size cap; instant deeper fills; the perp venue);
  - markouts by fill type from the 1-minute path (rung, BTC's move in the fill minute, sweep depth and volume,
    cascade breadth, AI prediction, hour, capacity-bound or not).
Writes reports/ladder_v5/diag_*.csv. Descriptive only: no candidate is tested here.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fsim  # noqa: E402

ROOT, OUT = fsim.ROOT, fsim.OUT
sys.path.insert(0, ROOT)
from edge import book as ebook  # noqa: E402


def era_rows(P, era, C, theta=0.5, label="incumbent", **kw):
    d1, out = fsim.book(P, era, theta=theta, C=C, **kw)
    st = fsim.stats(d1, C, era)
    Qi = out["instant"][0]
    return d1, dict(era=era, C=C, theta=theta, label=label, **st), Qi


def decomposition(pre):
    rows = []
    for era, (tag, _) in fsim.ERAS.items():
        for C in (250e3, 1e6):
            d1, out = fsim.book(pre[tag], era, C=C)
            lo, hi = fsim.ERAS[era][1]
            yrs = ((pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1) / 365.25
            Q = out["instant"][0]
            Q = Q[Q.fill > 0]
            s = lambda c: float(Q[c].sum()) / yrs  # noqa: E731
            rows.append(dict(era=era, C=C, fills=len(Q), fill_musd_yr=s("fill") / 1e6, tp_share=float(Q.tp_fill.sum() / Q.fill.sum()),
                             gross=s("gross"), fee_maker=s("fee_maker"), fee_taker=s("fee_taker"), half_spread=s("cost_hs"),
                             impact=s("cost_imp"), net=s("pnl"), net_bp=1e4 * Q.pnl.sum() / Q.fill.sum(),
                             gross_bp=1e4 * Q.gross.sum() / Q.fill.sum(), cap_bound=float((Q.fill < 0.999 * Q.want).mean())))
    return pd.DataFrame(rows)


def deployed_share(Q, lo, hi, C):
    """Mean share of capital in open positions (at cost), from fill to exit, by day (instant bound)."""
    idx = pd.date_range(lo, pd.Timestamp(hi) + pd.Timedelta(days=1), freq="min", inclusive="left")
    x = np.zeros(len(idx))
    t0 = idx[0]
    for r in Q[Q.fill > 0].itertuples():
        a = int((r.fill_t - t0) / pd.Timedelta(minutes=1))
        b_tp = int((r.tp_t - t0) / pd.Timedelta(minutes=1))
        b_ex = int((r.ex_t - t0) / pd.Timedelta(minutes=1))
        a = max(a, 0)
        if r.tp_fill > 0:
            x[a:max(a, b_tp)] += r.tp_fill
        x[a:max(a, b_ex)] += r.fill - r.tp_fill
    s = pd.Series(x / C, index=idx)
    return s.resample("D").mean()


def oracles(pre):
    rows = []
    for era, (tag, (lo, hi)) in fsim.ERAS.items():
        P = pre[tag]
        rf = ebook.rf_daily(pd.date_range(lo, hi, freq="D"))
        for C in (250e3, 1e6):
            base, r0, Qi = era_rows(P, era, C)
            rows.append(r0)
            # per-tranche sign of the incumbent's net (for the selection and sizing oracles)
            net = Qi.set_index(["ts", "coin", "k"]).pnl
            key = list(zip(P.ts, P.coin, P.k))
            sign = pd.Series([net.get(k, 0.0) for k in key], index=P.index)
            # 1. zero costs
            _, r, _ = era_rows(P, era, C, label="O1 zero fees and costs", tiers=[(0, 0.0, 0.0)], hs_bp=0.0, impact_y=0.0)
            rows.append(r)
            # 2. perfect exits: every tranche sells its whole fill at the best minute close within 60 min, as a maker
            Px = P.copy()
            best = np.array([1e4 * float(np.nanmax(p)) if isinstance(p, np.ndarray) else np.nan for p in Px.path])
            Px["g60"] = np.where(Px.filled, best, Px.g60)
            Px["tp_off"] = -1
            Px["rem_cost"] = 6e-4
            Px["rem_imp"] = 0.0
            _, r, _ = era_rows(Px, era, C, label="O2 perfect exits (best close in 60 min, maker)")
            rows.append(r)
            # 3. perfect selection: losing tranches skipped
            Ps = P.copy()
            Ps["mult"] = np.where(sign < 0, 0.0, 1.0)
            _, r, _ = era_rows(Ps, era, C, label="O3 perfect selection (losers skipped)")
            rows.append(r)
            # 4. perfect sizing: winners at twice the size, losers skipped
            Pz = P.copy()
            Pz["mult"] = np.where(sign < 0, 0.0, 2.0)
            _, r, _ = era_rows(Pz, era, C, label="O4 perfect sizing (winners 2x, losers 0)")
            rows.append(r)
            # 5. front of the queue: all the volume through the bid is ours (theta 1)
            _, r, _ = era_rows(P, era, C, theta=1.0, label="O5 front of queue (theta 1)")
            rows.append(r)
            # 6. no size cap (kappa off; 25% of capital and theta x through-volume still bind)
            _, r, _ = era_rows(P, era, C, label="O6 no ADV cap", kappa=None)
            rows.append(r)
            # 7. instant deeper fills (the latency gap)
            d1, out = fsim.book(P, era, C=C)
            di = out["instant"][1]
            rows.append(dict(era=era, C=C, theta=0.5, label="O7 instant deeper fills", **fsim.stats(di, C, era)))
            # 8. the perp venue at 1x costs
            Pp = P.copy()
            Pp["in_perp"], Pp["tp_perp"] = Pp.in_perp_raw, Pp.tp_perp_raw
            _, r, _ = era_rows(Pp, era, C, label="O8 + Coinbase US perp venue (1x costs)")
            rows.append(r)
            # 9. idle cash at the T-bill rate (positions only; resting-bid holds ignored)
            dep = deployed_share(Qi, lo, hi, C).reindex(rf.index).fillna(0.0)
            dy = base + rf.to_numpy() * (1 - dep.to_numpy())
            rows.append(dict(era=era, C=C, theta=0.5, label="O9 idle cash earns T-bills", mean_deployed=float(dep.mean()),
                             **fsim.stats(dy, C, era)))
            print(era, int(C), "done", flush=True)
    R = pd.DataFrame(rows)
    inc = R[R.label == "incumbent"].set_index(["era", "C"])
    R["d_sharpe"] = [r.sharpe - inc.loc[(r.era, r.C), "sharpe"] for r in R.itertuples()]
    R["d_ret"] = [r.ret_yr - inc.loc[(r.era, r.C), "ret_yr"] for r in R.itertuples()]
    return R


def main():
    pre = {t: fsim.load(t) for t in ("main", "early")}
    os.makedirs(OUT, exist_ok=True)
    pd.set_option("display.width", 250)
    D = decomposition(pre)
    D.to_csv(os.path.join(OUT, "diag_decomposition.csv"), index=False)
    print(D.round(3).to_string(index=False), flush=True)
    R = oracles(pre)
    R.to_csv(os.path.join(OUT, "diag_oracles.csv"), index=False)
    cols = ["era", "C", "label", "ret_yr", "sharpe", "d_ret", "d_sharpe", "mean_deployed"]
    print(R[[c for c in cols if c in R]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
