#!/usr/bin/env python3
"""Explore v1: selection-era attribution of the incumbent's fills (the evidence behind the round-3 dimensions).

  python scripts/explore/attribution.py

Net P&L per dollar filled (bp) by rung, AI ratio (pred / thr), sigma, ADV, daily vol, deeper-fill timing, hour, and
take-profit hit, for the minute and instant books at $250K (selection era only). Writes reports/explore/attribution.txt.
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xsim  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "reports", "explore")


def table(q, by, label):
    g = q.groupby(by, observed=True).agg(n=("pnl", "size"), usd=("fill", "sum"), pnl=("pnl", "sum"))
    g["bp"] = g.pnl / g.usd * 1e4
    g["pnl_share"] = g.pnl / q.pnl.sum()
    return f"-- by {label}\n" + g.round(3).to_string()


def main():
    pd.set_option("display.width", 200)
    par = xsim.data("main")
    par = par[par.k == 4.0].set_index(["ts", "coin"])
    lines = []
    for mode in ("minute", "instant"):
        _, Q, info = xsim.evaluate(dict(mode=mode), "selection", 250e3)
        q = Q[Q.fill > 0].copy()
        key = pd.MultiIndex.from_arrays([q.ts, q.coin])
        q["ratio"] = (par.pred / par.thr).reindex(key).to_numpy()
        q["sig_bp"] = par.sig.reindex(key).to_numpy() * 1e4
        deep = q[q.k > 4]
        lines += [f"== incumbent, {mode} book, $250K, selection era: {len(q)} fills, P&L ${q.pnl.sum():,.0f}",
                  table(q, "k", "rung (sigma)"), table(q, pd.qcut(q.ratio, 6), "AI ratio pred / thr (sextiles)"),
                  table(q, pd.qcut(q.sig_bp, 6), "sigma in bp (sextiles)"),
                  table(q, [q.ts.dt.to_period("Q"), q.sig_bp >= 57.6], "quarter x (sigma >= 57.6 bp)"),
                  table(q, [pd.qcut(q.adv, 3, labels=["adv_lo", "adv_mid", "adv_hi"]), q.sig_bp >= 57.6],
                        "ADV tercile x (sigma >= 57.6 bp)"),
                  table(q, [pd.qcut(q.ratio, 3, labels=["r_lo", "r_mid", "r_hi"]),
                            pd.qcut(q.sig_bp, 3, labels=["s_lo", "s_mid", "s_hi"])], "AI ratio tercile x sigma tercile"),
                  table(q, pd.qcut(q.adv, 6), "ADV (sextiles)"), table(q, pd.qcut(q.vol_d, 6), "daily vol (sextiles)"),
                  table(deep, pd.cut(deep.f_off, [-1, 0, 1, 2, 5, 10, 20, 30, 45, 60]),
                        "deeper fills: minutes after the signal"),
                  table(q, pd.cut(q.ts.dt.hour, [-1, 3, 7, 11, 15, 19, 23]), "hour (UTC)"),
                  table(q, q.tp_fill > 0, "take-profit hit"), ""]
    txt = "\n".join(lines)
    open(os.path.join(OUT, "attribution.txt"), "w").write(txt)
    print(txt[:3000])


if __name__ == "__main__":
    main()
