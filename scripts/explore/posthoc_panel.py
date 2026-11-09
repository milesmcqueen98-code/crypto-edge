#!/usr/bin/env python3
"""Explore v1, POST HOC (information only; runs only after the one holdout read): every variant of rounds 1-3 on the
check era and 2022-23 (blended, $250K), to see which design effects persist out of sample.

  python scripts/explore/posthoc_panel.py run      # simulate (about 35 minutes on 2 cores)
  python scripts/explore/posthoc_panel.py analyze  # effects and rank persistence

The verdict stays with the frozen finalists (holdout.txt). Nothing here selects anything.
Writes reports/explore/posthoc_panel.csv and posthoc_panel.txt.
"""
import json
import math
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402
import variants_r3  # noqa: E402
import xsim  # noqa: E402

OUT = analyze.OUT
ERAS = ("check", "y2022_23")


def one(v):
    s = json.loads(v["spec"])
    row = dict(id=v["id"])
    for era in ERAS:
        d = xsim.blended(s, era, 250e3)[0]
        st = xsim.stats(d, era)
        row[f"sharpe_{era}"], row[f"ret_{era}"], row[f"maxdd_{era}"] = st["sharpe"], st["ret_yr"], st["maxdd"]
    return row


def run():
    if not os.path.exists(os.path.join(OUT, "holdout_read.txt")):
        sys.exit("post hoc only: the holdout has not been read yet")
    V = pd.read_csv(os.path.join(OUT, "variants.csv"))
    with Pool(2) as pool:
        rows = pool.map(one, V[["id", "spec"]].to_dict("records"), chunksize=16)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "posthoc_panel.csv"), index=False)


def ols(V, ycol, rnd):
    des = []
    for x in V.loc[rnd, "design"]:
        d = dict(variants_r3.BASE3)
        d.update({k: v for k, v in json.loads(x).items() if k != "note"})
        des.append(d)
    X = pd.DataFrame([{f"{k}={d[k]}": 1.0 for k in variants_r3.BASE3} for d in des]).fillna(0.0)
    ref = [c for c in X.columns if any(c == f"{k}={variants_r3.BASE3[k]}" for k in variants_r3.BASE3)]
    X = X.drop(columns=ref)
    X.insert(0, "const", 1.0)
    y = V.loc[rnd, ycol].to_numpy()
    beta, *_ = np.linalg.lstsq(X.to_numpy(), y, rcond=None)
    return pd.Series(beta, index=X.columns)


def analyze_panel():
    V = pd.read_csv(os.path.join(OUT, "scores.csv"))
    H = pd.read_csv(os.path.join(OUT, "posthoc_panel.csv"))
    V = V.merge(H, on="id")
    base = V[V.id == "base"].iloc[0]
    lines = ["POST HOC (information only): all variants on the holdout eras, blended $250K", ""]
    for era in ERAS:
        c = V.sharpe_b250.corr(V[f"sharpe_{era}"], method="spearman")
        top = V.sort_values("sharpe_b250", ascending=False)
        lines.append(f"{era}: incumbent {base[f'sharpe_{era}']:.3f}; Spearman(selection, {era}) across {len(V)} variants "
                     f"{c:.3f}; share above the incumbent {np.mean(V[f'sharpe_{era}'] > base[f'sharpe_{era}']):.1%}")
        for k in (10, 50, 200, 1000):
            t = top.head(k)
            lines.append(f"   selection top {k:4d}: mean {era} ΔSharpe {t[f'sharpe_{era}'].mean() - base[f'sharpe_{era}']:+.3f}"
                         f", share > incumbent {np.mean(t[f'sharpe_{era}'] > base[f'sharpe_{era}']):.0%}")
    rnd = (V.origin == "random").to_numpy()
    eff = pd.DataFrame({"selection": ols(V, "sharpe_b250", rnd)})
    for era in ERAS:
        eff[era] = ols(V, f"sharpe_{era}", rnd)
    eff = eff.drop(index="const")
    eff["same_sign_all"] = (np.sign(eff.selection) == np.sign(eff.check)) & (np.sign(eff.selection) == np.sign(eff.y2022_23))
    lines += ["", "OLS partial effects on blended $250K Sharpe (random variants), selection vs holdout eras:",
              eff.round(3).sort_values("selection").to_string(),
              "", f"Correlation of effects, selection vs check {eff.selection.corr(eff.check):.2f}, "
                  f"vs 2022-23 {eff.selection.corr(eff.y2022_23):.2f}"]
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "posthoc_panel.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    {"run": run, "analyze": analyze_panel}[sys.argv[1]]()
