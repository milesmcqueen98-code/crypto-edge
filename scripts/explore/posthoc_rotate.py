#!/usr/bin/env python3
"""Explore v1, POST HOC (information only): would tuning across eras have worked better than tuning within one?

For each rotation, pick variants on two eras and score the pick on the third (blended $250K Sharpe, from
variants.csv and posthoc_panel.csv). Rules: best mean Sharpe over the two tuning eras; best worst-era Sharpe;
the top 1 and the mean of the top 10 / 50 by each rule. Scores are ΔSharpe against the incumbent in the test era.
Writes reports/explore/posthoc_rotate.txt.
"""
import os

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports", "explore")


def main():
    S = pd.read_csv(os.path.join(OUT, "scores.csv")).merge(pd.read_csv(os.path.join(OUT, "posthoc_panel.csv")), on="id")
    S = S.rename(columns={"sharpe_b250": "sel", "sharpe_check": "chk", "sharpe_y2022_23": "y23"})
    base = S[S.id == "base"].iloc[0]
    V = S[S.id != "base"]
    eras = ("sel", "chk", "y23")
    names = {"sel": "selection", "chk": "check", "y23": "2022-23"}
    lines = ["POST HOC (information only): tune on two eras, score on the third (ΔSharpe vs the incumbent, blended $250K)",
             "", f"{'test era':10s} {'rule':12s} {'top 1':>7s} {'top 10':>7s} {'top 50':>7s}  pick"]
    for test in eras:
        tune = [e for e in eras if e != test]
        d = {e: V[e] - base[e] for e in eras}
        for rule, score in (("mean", (d[tune[0]] + d[tune[1]]) / 2), ("worst era", np.minimum(d[tune[0]], d[tune[1]])),
                            ("one era", d[tune[0]] if tune[0] == "sel" else d[tune[1]])):
            order = score.sort_values(ascending=False).index
            t = d[test].loc[order]
            lines.append(f"{names[test]:10s} {rule:12s} {t.iloc[0]:+7.3f} {t.iloc[:10].mean():+7.3f} {t.iloc[:50].mean():+7.3f}  "
                         f"{V.loc[order[0], 'id']}")
    lines += ["", "('one era' tunes on the selection era alone where it is a tuning era, else on the first tuning era.)"]
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "posthoc_rotate.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
