#!/usr/bin/env python3
"""Explore v1: selection-era profile of the frozen finalists (information, before the holdout read).

  python scripts/explore/profile.py

For each finalist and the incumbent (blended, $250K, selection era): Sharpe and return; Sharpe with the top 1 / 3 / 5
/ 10 days removed; ΔSharpe by calendar quarter; the vol-matched paired difference's t (stationary bootstrap, mean
block 7 days); signals, fills and fill dollars (minute book). Writes reports/explore/profile.txt.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402
import holdout  # noqa: E402
import xsim  # noqa: E402

OUT = analyze.OUT
ERA, C = "selection", 250e3


def sharpe(e):
    return float(e.mean() / e.std(ddof=1) * math.sqrt(365))


def main():
    F = json.load(open(os.path.join(OUT, "finalists.json")))
    lo, hi = xsim.ERAS[ERA][1]
    idx = pd.date_range(lo, hi, freq="D")
    rf = xsim.edge_book.rf_daily(idx).to_numpy()
    rows = [("incumbent", F["incumbent"])] + [(f["name"], f) for f in F["finalists"]]
    ser = {n: holdout.series(f, ERA, C).reindex(idx, fill_value=0.0) for n, f in rows}
    e0 = ser["incumbent"].to_numpy() - rf
    rng = np.random.default_rng(3)
    lines = ["Selection-era profile (blended, $250K): Sharpe, return, Sharpe without the best k days, paired test",
             f"{'book':16s} {'Sharpe':>7s} {'ret/yr':>7s} {'-1d':>6s} {'-3d':>6s} {'-5d':>6s} {'-10d':>6s} "
             f"{'ΔSR':>6s} {'t(vm)':>6s}"]
    q_lines = []
    for n, _ in rows:
        r = ser[n].to_numpy()
        e = r - rf
        out = [sharpe(e), r.sum() / (len(r) / 365.25)]
        order = np.argsort(-r)
        for k in (1, 3, 5, 10):
            keep = np.ones(len(r), bool)
            keep[order[:k]] = False
            out.append(sharpe(e[keep]))
        d = e / e.std(ddof=1) - e0 / e0.std(ddof=1)
        bs = np.array([d[analyze.stationary_idx(len(d), rng)].mean() for _ in range(1000)])
        t = d.mean() / bs.std(ddof=1) if n != "incumbent" else float("nan")
        lines.append(f"{n:16s} {out[0]:7.3f} {out[1]:7.3f} " + " ".join(f"{x:6.2f}" for x in out[2:]) +
                     f" {out[0] - sharpe(e0):6.2f} {t:6.2f}")
        s = pd.Series(e, index=idx)
        s0 = pd.Series(e0, index=idx)
        qd = {str(p): sharpe(g.to_numpy()) - sharpe(s0[g.index].to_numpy()) for p, g in s.groupby(s.index.to_period("Q"))}
        q_lines.append(f"{n:16s} " + " ".join(f"{k}:{v:+.2f}" for k, v in qd.items()))
    lines += ["", "ΔSharpe vs the incumbent by calendar quarter (selection era):"] + q_lines
    info = ["", "Minute book at $250K: signals kept, fills, fill dollars (each member for the ensemble, averaged):"]
    for n, f in rows:
        specs = f["members"] if f.get("members") else [f["spec"]]
        st = [xsim.evaluate(dict(s, mode="minute"), ERA, C)[2] for s in specs]
        info.append(f"{n:16s} signals {np.mean([x['signals'] for x in st]):7.0f}  fills {np.mean([x['fills'] for x in st]):7.0f}"
                    f"  fill $ {np.mean([x['fill_usd'] for x in st]) / 1e6:6.1f}M  maker {st[0]['maker_bp']:.1f} bp")
    txt = "\n".join(lines + info) + "\n"
    open(os.path.join(OUT, "profile.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
