#!/usr/bin/env python3
"""Signal lab, POST HOC (information only; after the one holdout read): which signals each finalist added and dropped
against R2-08, and what the ladder earned on them.

  python scripts/signal_lab/posthoc.py

For each finalist and era, the filled 4-sigma signals are split into: kept by both models, only R2-08, only the
finalist. For each set: the count and the ladder's gross per dollar of the whole signal (thirds; a rung that did not
fill earns 0; take-profit or the 60-minute close; before costs and capacity). Per-coin books are sequential, so a
changed decision can also shift a later fill; the split is by (minute, coin).
Writes reports/signal_lab/posthoc_sets.csv and posthoc_sets.txt.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
import lsim  # noqa: E402

fsim = lsim.fsim
OUT = os.path.join(ROOT, "reports", "signal_lab")


def signals(tag):
    P = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", f"pre_hunt_{tag}.pkl"))
    g = np.where(P.filled.to_numpy(bool), np.where(P.tp_hit.to_numpy(bool), P.g_tp.to_numpy(), P.g60.to_numpy()), 0.0)
    P = P.assign(g=g)
    S = P.groupby(["ts", "coin"]).agg(ladder_bp=("g", "sum"), deep=("filled", "sum")).reset_index()
    S["ladder_bp"] /= 3.0
    S["deep"] -= 1                                              # deeper rungs filled
    return S


def main():
    F = json.load(open(os.path.join(OUT, "finalists.json")))
    rows = []
    for f in [x["spec"] for x in F["finalists"]]:
        for era in ("sel", "chk", "early"):
            base, (lo, hi) = fsim.ERAS[era]
            name = f
            if base == "early" and f.endswith("H"):
                name = f[:-1]
                if name == "RF0":
                    continue                                    # the incumbent itself in 2022-23
            A = signals(base)
            B = signals(f"{base}_{name}")
            w = lambda S: S[(S.ts >= lo) & (S.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]  # noqa: E731
            m = w(A).merge(w(B), on=["ts", "coin"], how="outer", suffixes=("_inc", "_new"), indicator=True)
            for lab, sel, col in (("both", m._merge == "both", "ladder_bp_inc"), ("only R2-08", m._merge == "left_only", "ladder_bp_inc"),
                                  ("only finalist", m._merge == "right_only", "ladder_bp_new")):
                x = m.loc[sel, col]
                dcol = "deep_inc" if col.endswith("inc") else "deep_new"
                rows.append(dict(spec=f, era=era, set=lab, n=int(sel.sum()), ladder_bp=float(x.mean()) if len(x) else np.nan,
                                 sum_bp=float(x.sum()), deep_per_signal=float(m.loc[sel, dcol].mean()) if sel.any() else np.nan))
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, "posthoc_sets.csv"), index=False)
    lines = ["POST HOC (information only): signals kept by both models, only R2-08, only the finalist",
             "ladder_bp = gross per dollar of the whole signal (thirds), before costs and capacity", ""]
    for f, g in T.groupby("spec", sort=False):
        lines += [f"== {f}", g.drop(columns="spec").round(2).to_string(index=False), ""]
    txt = "\n".join(lines)
    open(os.path.join(OUT, "posthoc_sets.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
