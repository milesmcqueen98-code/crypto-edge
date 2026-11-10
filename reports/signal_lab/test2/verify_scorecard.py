#!/usr/bin/env python3
"""Orchestrator's independent check of signal lab 2's gates and scorecard (reports/signal_lab/test2_m60), recomputed
from the cell series and holdout_cells.csv with prereg.md's formulas. Does not import the lab or score.py.
usage: python verify_scorecard.py /home/claude/wt/v6x/reports/signal_lab/test2_m60
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

OUT = sys.argv[1]
CELLS = os.path.join(OUT, "cells")
CFG = json.load(open(os.path.join(os.path.dirname(OUT), "test2", "config.json")))
ERAS = ("sel", "chk", "early")
CFGS = ("S_0.5", "S_0.25", "cap_1M", "base_0.5")
INC = CFG["incumbent"]
T = pd.read_csv(os.path.join(OUT, "holdout_cells.csv"))
TT = pd.read_csv(os.path.join(OUT, "holdout_tests.csv")).set_index("spec")
SC = pd.read_csv(os.path.join(OUT, "holdout_scorecard.csv")).set_index("spec")
M = T[T.cost == "model"]


def cell(b, cfg, era):
    return pd.read_parquet(os.path.join(CELLS, f"{b}__{cfg}__{era}.parquet"))["model"]


def stationary_idx(n, rng, mean_block=7):
    out = np.empty(n, int)
    i = rng.integers(n)
    for t in range(n):
        out[t] = i
        i = rng.integers(n) if rng.random() < 1.0 / mean_block else (i + 1) % n
    return out


clip = lambda x: float(np.clip(x, 0, 1))  # noqa: E731
pv = {}
for f in [x["spec"] for x in CFG["finalists"]]:
    m = M[M.spec == f]
    prim = m[m.cfg == "S_0.5"].set_index("era")
    g1 = bool((prim.d_sharpe >= 0.20).all())
    g2 = bool((m[m.cfg != "S_0.5"].d_sharpe >= 0).all())
    risk = [(prim.loc[e, "maxdd"] >= 1.1 * prim.loc[e, "maxdd_inc"], prim.loc[e, "worst"] >= 1.1 * prim.loc[e, "worst_inc"])
            for e in ERAS]
    g3 = all(a and b for a, b in risk)
    ser = pd.concat([cell(f, "S_0.5", e) for e in ERAS]).sort_index()
    yrs = ser.groupby(ser.index.year).sum()
    g4 = bool((yrs > 0).all())
    # pooled holdout, raw gain and top-5-day share (no risk-free adjustment needed for a difference of two books)
    g = np.concatenate([(cell(f, "S_0.5", e) - cell(INC, "S_0.5", e)).to_numpy() for e in ("early", "chk")])
    top5 = float(np.sort(g)[-5:].sum())
    share = top5 / g.sum() if g.sum() > 0 else float("nan")
    # own bootstrap on the vol-matched difference without the risk-free term (a check of magnitude, not of the digits)
    parts = []
    for e in ("early", "chk"):
        a, b = cell(f, "S_0.5", e).to_numpy(), cell(INC, "S_0.5", e).to_numpy()
        parts.append(a / a.std(ddof=1) - b / b.std(ddof=1))
    d = np.concatenate(parts)
    rng = np.random.default_rng(123)
    bs = np.array([d[stationary_idx(len(d), rng)].mean() for _ in range(3000)])
    p_own = float(np.mean((bs - d.mean()) >= d.mean()))
    pv[f] = float(TT.loc[f, "p_raw"])
    hand = next(x for x in CFG["finalists"] if x["spec"] == f)["hand"]
    hold = prim.loc[["chk", "early"]]
    cap = m[(m.cfg == "cap_1M") & m.era.isin(["chk", "early"])]
    print(f"== {f}")
    print("  d_sharpe (S_0.5):", {e: round(float(prim.loc[e, 'd_sharpe']), 3) for e in ERAS})
    print("  cells > 0:", int((m.d_sharpe > 0).sum()), "of", len(m), "| gates g1..g4:", g1, g2, g3, g4,
          "| risk checks passed:", int(sum(x for pair in risk for x in pair)), "of 6")
    print("  years:", {int(k): round(float(v), 4) for k, v in yrs.items()})
    print(f"  pooled gain {g.sum():+.4f}, top-5 share {share:.3f}; p_raw (report) {pv[f]:.3f}, own bootstrap p {p_own:.3f}, "
          f"annualized vol-matched mean {d.mean() * math.sqrt(365):+.3f} (SE {bs.std(ddof=1) * math.sqrt(365):.3f})")
    globals().setdefault("ROWS", {})[f] = dict(prim=prim, m=m, risk=risk, g4=g4, share=share, gain=g.sum(), hand=hand, hold=hold, cap=cap)

order = sorted(pv, key=lambda x: pv[x])
holm, run = {}, 0.0
for i, f in enumerate(order):
    run = max(run, min(1.0, (len(order) - i) * pv[f]))
    holm[f] = run
for f, r in ROWS.items():  # noqa: F821
    pts = dict(sharpe=25 * clip(r["hold"].d_sharpe.mean() / 0.40), capacity=10 * clip(r["cap"].d_sharpe.mean() / 0.40),
               consistency=15 * float((r["m"].d_sharpe > 0).mean()), evidence=15 * clip((0.20 - holm[f]) / 0.15),
               spread=(10 * clip((1 - r["share"]) / 0.5) if r["gain"] > 0 else 0.0),
               risk=8 * float(np.mean([x for pair in r["risk"] for x in pair])) + (2 if r["g4"] else 0),
               mechanism=float(r["hand"][0]), implementation=float(r["hand"][1]))
    pts["total"] = sum(pts.values())
    rep = SC.loc[f].to_dict()
    diff = max(abs(pts[k] - rep[k]) for k in pts)
    print(f"== {f}: Holm {holm[f]:.3f}; points " + ", ".join(f"{k} {v:.2f}" for k, v in pts.items()) +
          f" | max difference from the report's scorecard {diff:.2e}")
