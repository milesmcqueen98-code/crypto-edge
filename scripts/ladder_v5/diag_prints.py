#!/usr/bin/env python3
"""Ladder v5, step 1d (selection era only): who sold to us and who bid beside us, from the print statistics
(reports/ladder_v5/prints_parents.csv, made on Actions by prints.py), against each parent's outcome in the research
book ($250K, theta 0.5, instant bound). Writes reports/ladder_v5/diag_prints_sel.txt."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fsim  # noqa: E402


def main():
    D = pd.read_csv(os.path.join(fsim.OUT, "prints_parents.csv"), parse_dates=["ts"])
    lo, hi = fsim.ERAS["sel"][1]
    D = D[(D.ts >= lo) & (D.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]
    P = fsim.load("main")
    _, out = fsim.book(P, "sel", C=250e3)
    Q = out["instant"][0]
    q = Q[(Q.k == 4.0) & (Q.fill > 0)][["ts", "coin", "fill", "want", "pnl", "adv"]]
    q["net_bp"] = 1e4 * q.pnl / q.fill
    M = D.merge(q, on=["ts", "coin"], how="inner")
    M["at_pre_rel"] = M.at_lvl_pre_usd / M.want
    M["at_share"] = M.at_lvl_usd / (M.at_lvl_usd + M.below_usd)
    M["sweep_adv_bp"] = 1e4 * M.first_sweep_usd / M.adv
    lines = [f"{len(M)} selection-era parents with prints and research fills"]
    w = lambda g: pd.Series(dict(n=len(g), net_w=np.average(g.net_bp, weights=g.fill), mo5=g.mo_5s.mean(),  # noqa: E731
                                 mo60=g.mo_60s.mean(), min_after=g.min_after_bp.mean()))
    lines.append("\nWho bid beside us: USD printed at exactly our price before our trade-through, relative to our size")
    lines.append(f"  share of parents with any: {(M.at_lvl_pre_usd > 0).mean():.1%}; median when any: "
                 f"{M.loc[M.at_lvl_pre_usd > 0, 'at_pre_rel'].median():.2f}x our size; at-level share of the minute's "
                 f"volume at or below our price: median {M.at_share.median():.1%}")
    b = pd.cut(M.at_pre_rel, [-1, 0, 0.25, 1, 1e9], labels=["none", "<0.25x", "0.25-1x", ">1x"])
    lines.append(M.groupby(b, observed=True).apply(w).round(1).to_string())
    for v, lab in (("taker_sell_share", "share of the volume below us that was aggressive selling"),
                   ("n_sweeps", "number of aggressive orders at or below our price in the fill minute"),
                   ("sweep_adv_bp", "the order that reached us, bp of ADV"),
                   ("first_sweep_levels", "price levels that order swept"),
                   ("first_sweep_depth_bp", "how far below our price that order went, bp"),
                   ("approach1_s", "seconds from 1 sigma above our bid to our fill"),
                   ("through_s", "seconds into the minute of our fill"),
                   ("mo_5s", "markout 5 s after our fill, bp"),
                   ("mo_60s", "markout 60 s after our fill, bp")):
        x = M.dropna(subset=[v])
        qq = pd.qcut(x[v], 5, labels=False, duplicates="drop")
        t = x.groupby(qq).apply(w)
        t.insert(0, "hi", x.groupby(qq)[v].max())
        rho = x[[v, "net_bp"]].corr("spearman").iloc[0, 1]
        lines.append(f"\n{lab} ({v}; Spearman with net {rho:+.3f})\n" + t.round(1).to_string())
    txt = "\n".join(lines)
    open(os.path.join(fsim.OUT, "diag_prints_sel.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
