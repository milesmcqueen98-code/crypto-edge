#!/usr/bin/env python3
"""BURN and MAC, after both freezes: descriptive only (no gate, no selection). The research gross of the ladders a rule
skips against the ones it keeps, from the frozen dataset's rung records:
  rung gross   g_tp if the rung's take-profit traded by +60 minutes, else g60 (bp, before costs)
  ladder gross the mean over the 4/6/8-sigma rungs (an unfilled rung counts 0), in bp of the signal's full size
DEV (sel): every grid variant of both ideas; HOLD eras (chk, early): the frozen variant of each idea only.
usage: python scripts/hunt2/burn/explain.py    -> reports/hunt2/burn/explain.csv, reports/hunt2/mac/explain.csv
"""
import gc
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "mac"))
import burn  # noqa: E402
import mac  # noqa: E402

F = burn.F


def gross_table(era):
    tag, (lo, hi) = F.fsim.ERAS[era]
    P = F.RL.inputs(tag)["P"]
    par = burn.pathA.parents(era)[["ts", "coin"]]
    R = P[P.filled & P.k.isin([4.0, 6.0, 8.0])].copy()
    R["gross"] = np.where(R.tp_hit.astype(bool), R.g_tp, R.g60)
    W = R.pivot_table(index=["ts", "coin"], columns="k", values="gross", aggfunc="first").reindex(
        columns=[4.0, 6.0, 8.0])
    out = par.merge(W.reset_index(), on=["ts", "coin"], how="left")
    out["g4"] = out[4.0]
    out["ladder"] = out[[4.0, 6.0, 8.0]].fillna(0.0).sum(axis=1) / 3.0
    T4 = R[R.k == 4.0][["ts", "coin", "tp_hit"]]
    out = out.merge(T4, on=["ts", "coin"], how="left")
    out["tp4"] = out.tp_hit.astype(bool)
    return out[["ts", "coin", "g4", "ladder", "tp4"]]


def row(idea, variant, era, G4, sk):
    key = set(zip(sk.ts, sk.coin))
    s = np.array([(t, c) in key for t, c in zip(G4.ts, G4.coin)])
    return dict(idea=idea, variant=variant, era=era, n_skip=int(s.sum()), n_keep=int((~s).sum()),
                g4_skip_bp=float(G4.g4[s].mean()) if s.any() else np.nan, g4_keep_bp=float(G4.g4[~s].mean()),
                ladder_skip_bp=float(G4.ladder[s].mean()) if s.any() else np.nan,
                ladder_keep_bp=float(G4.ladder[~s].mean()),
                tp_rate_skip=float(G4.tp4[s].mean()) if s.any() else np.nan, tp_rate_keep=float(G4.tp4[~s].mean()))


def main():
    fb, _ = burn.assert_frozen()
    fm, _ = mac.assert_frozen()
    rows_b, rows_m = [], []
    for era in ("sel", "chk", "early"):
        G4 = gross_table(era)
        if era == "sel":
            G4 = G4[burn.G.is_dev(G4.ts.dt.floor("D"))]
        gb = burn.GRID if era == "sel" else [(fb["params"]["m"], fb["params"]["C_hours"], fb["params"]["scope"])]
        for mthr, C, scope in gb:
            m, _, _ = burn.mult(era, mthr, C, scope)
            sk, _ = burn.skipped(era, m)
            rows_b.append(row("burn", burn.name(mthr, C, scope), era, G4, sk))
        gm = mac.GRID if era == "sel" else [(fm["params"]["a"], fm["params"]["b"], fm["params"]["events"])]
        for a, b, ev in gm:
            m = mac.mult(era, a, b, ev)
            sk, _ = mac.skipped(era, m)
            rows_m.append(row("mac", mac.name(a, b, ev), era, G4, sk))
        F._A.clear()
        if era == "chk":
            F.RL._IN.clear()          # the main tag's input cache is not needed for the early era
        gc.collect()
    for rows, idea in ((rows_b, "burn"), (rows_m, "mac")):
        D = pd.DataFrame(rows)
        D.round(3).to_csv(os.path.join(burn.WT, "reports", "hunt2", idea, "explain.csv"), index=False)
        print(D.round(2).to_string(index=False))
    print(json.dumps(dict(burn=fb["variant"], mac=fm["variant"])))


if __name__ == "__main__":
    main()
