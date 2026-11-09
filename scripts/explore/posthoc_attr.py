#!/usr/bin/env python3
"""Explore v1, POST HOC (information only, after the one holdout read): did the selection-era patterns behind the
finalists hold in the check era and 2022-23? The incumbent's minute book at $250K, per era: net bp per dollar and
P&L share by sigma (the 55 bp floor and the selection-era median 57.6 bp), by AI ratio (pred / thr, the 1.1 / 1.2
strictness cuts), by deeper-fill timing, and the knock-out of each of Best's knobs (revert one knob to the incumbent's,
blended $250K Sharpe). Writes reports/explore/posthoc_attr.txt.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xsim  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "reports", "explore")
ERAS = ("selection", "check", "y2022_23")


def fills(era):
    _, Q, _ = xsim.evaluate(dict(mode="minute"), era, 250e3)
    q = Q[Q.fill > 0].copy()
    par = xsim.data(xsim.ERAS[era][0])
    par = par[par.k == 4.0].set_index(["ts", "coin"])
    key = pd.MultiIndex.from_arrays([q.ts, q.coin])
    q["ratio"] = (par.pred / par.thr).reindex(key).to_numpy()
    q["sig_bp"] = par.sig.reindex(key).to_numpy() * 1e4
    return q


def by(q, groups):
    g = q.groupby(groups, observed=True).agg(n=("pnl", "size"), usd=("fill", "sum"), pnl=("pnl", "sum"))
    g["bp"] = g.pnl / g.usd * 1e4
    g["share"] = g.pnl / q.pnl.sum()
    return g[["n", "bp", "share"]]


def main():
    pd.set_option("display.width", 200)
    lines = ["POST HOC (information only): the incumbent's minute book at $250K, net bp per dollar and P&L share", ""]
    Fq = {e: fills(e) for e in ERAS}
    cuts = {"sigma vs 55 bp": lambda q: np.where(q.sig_bp >= 55, ">=55", "<55"),
            "sigma vs 57.6 bp": lambda q: np.where(q.sig_bp >= 57.6, ">=57.6", "<57.6"),
            "AI ratio": lambda q: pd.cut(q.ratio, [0, 1.1, 1.2, 1.5, 2.0, 99], right=False).astype(str),
            "rung": lambda q: q.k.astype(str),
            "deeper fill minute": lambda q: np.where(q.k > 4, pd.cut(q.f_off, [-1, 1, 5, 20, 60]).astype(str), "parent"),
            "take-profit hit": lambda q: np.where(q.tp_fill > 0, "hit", "not hit")}
    for name, f in cuts.items():
        tabs = []
        for e in ERAS:
            q = Fq[e]
            t = by(q, f(q))
            t.columns = [f"{c}_{e}" for c in t.columns]
            tabs.append(t)
        lines += [f"-- by {name}", pd.concat(tabs, axis=1).round(3).to_string(), ""]
    for e in ERAS:
        q = Fq[e]
        lines.append(f"{e}: fills {len(q)}, median sigma {q.sig_bp.median():.1f} bp, share of fills with sigma >= 55: "
                     f"{np.mean(q.sig_bp >= 55):.0%}, median AI ratio {q.ratio.median():.2f}")
    F = json.load(open(os.path.join(OUT, "finalists.json")))
    best = next(f for f in F["finalists"] if f["name"] == "Best")["spec"]
    inc = dict(xsim.BASE)
    lines += ["", "Knock-out of Best's knobs (revert one to the incumbent's), blended $250K Sharpe:"]
    rows = []
    variants = {"Best": best}
    for k in best:
        if k in inc and json.dumps(best[k], sort_keys=True, default=str) != json.dumps(inc[k], sort_keys=True, default=str):
            s = dict(best)
            s[k] = inc[k]
            if k == "rungs":
                s["tp"] = {"4.0": best["tp"]["4.0"], "6.0": best["tp"]["6.0"], "8.0": best["tp"]["6.0"]}
            variants[f"Best, {k} as incumbent"] = s
    variants["incumbent"] = {}
    for n, s in variants.items():
        r = {"book": n}
        for e in ERAS:
            r[e] = xsim.stats(xsim.blended(s, e, 250e3)[0], e)["sharpe"]
        rows.append(r)
    lines.append(pd.DataFrame(rows).round(3).to_string(index=False))
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "posthoc_attr.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
