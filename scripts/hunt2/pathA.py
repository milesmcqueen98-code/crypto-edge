#!/usr/bin/env python3
"""Edge hunt 2: helpers for Path A candidates (modifications of the live bot) on the frozen simulator.

A Path A filter decides, for each research parent (R2-08's 4-sigma fill: coin, fill minute), whether the bid would
have been live. Skipping a parent sets the multiplier of its (fill minute, coin) cell to frozen_sim.SKIP, so the
parent and its deeper rungs carry ~0 dollars and the cash it would have used stays free (the engine-faithful cash rule
decides the rest). Size changes use a multiplier m in (0, 1] on the same cell (and optionally on the minutes before
it, which only changes the cash held by resting bids).

    import pathA
    d_x2 = pathA.run_cells("sel", skip_cells, cost="X2")      # skip_cells: DataFrame with columns ts, coin
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frozen_sim as F  # noqa: E402


def parents(era):
    """Research parents of an era (the AI-approved 4-sigma fills): ts (fill minute), coin, lvl, g60, lab_gross."""
    tag, (lo, hi) = F.fsim.ERAS[era]
    P = F.RL.inputs(tag)["P"]
    par = P[(P.k == 4.0) & P.filled & (P.ts >= pd.Timestamp(lo)) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]
    return par[["ts", "coin", "lvl", "vol_d", "adv"]].reset_index(drop=True)


def mult_for(era, cells, value=F.SKIP, before=0, theta=0.5, C=250e3):
    """T x NC multiplier: `value` at each (ts, coin) in cells (and the `before` minutes before it), 1 elsewhere.
    cells may carry a column `m` to give each cell its own value."""
    A = F.arrays(era, theta, C)
    idx, coins = A["idx"], list(A["coins"])
    m = np.ones(A["want4"].shape)
    if cells is None or len(cells) == 0:
        return m
    pos = idx.get_indexer(pd.DatetimeIndex(cells["ts"]))
    col = np.array([coins.index(c) if c in coins else -1 for c in cells["coin"]])
    vals = cells["m"].to_numpy() if "m" in cells else np.full(len(cells), value)
    for p, c, v in zip(pos, col, vals):
        if p < 0 or c < 0:
            continue
        m[max(0, p - before):p + 1, c] = v
    return m


def run_cells(era, cells, cost="X2", value=F.SKIP, before=0, theta=0.5, C=250e3):
    """Daily returns on C of the live bot with the given cells skipped (or resized)."""
    return F.daily(era, theta, C, cost, mfac=mult_for(era, cells, value, before, theta, C))


# ------------------------------------------------------------------ the standard Path A workflow
def _gates():
    import h2gates as G  # noqa: E402  (imported lazily: frozen_sim puts ladder_v5's own `gates` module on the path)
    return G


def dev_trial(idea, variant, cells_dev, note="", value=F.SKIP, before=0, **extra):
    """Run one DEV configuration (sel era, X2, $250K), log it as a trial, and return its DEV screen."""
    G = _gates()
    d = run_cells("sel", cells_dev, cost="X2", value=value, before=before)
    d = d[G.is_dev(d.index)]
    scr = G.dev_screen_a(d)
    n_skip = int(len(cells_dev)) if cells_dev is not None else 0
    G.log_trial(idea, variant, d, "A", scr["t_diff"], note=note, n_skipped=n_skip, **extra)
    scr["n_skipped"] = n_skip
    return scr, d


def hold_read(idea, cells_by_era, out_dir, value=F.SKIP, before=0, eras=("sel", "chk", "early"), days=None):
    """AFTER the freeze commit only: run the frozen variant on every era at X2, X1 and S, write daily.parquet (columns
    x2, x1, s) and gates.json in out_dir, and return the gate dict."""
    import json
    G = _gates()
    cols = {"x2": [], "x1": [], "s": []}
    for era in eras:
        cells = cells_by_era.get(era)
        for cost, k in (("X2", "x2"), ("X1", "x1"), ("S", "s")):
            cols[k].append(run_cells(era, cells, cost=cost, value=value, before=before))
    D = pd.DataFrame({k: pd.concat(v).sort_index() for k, v in cols.items()})
    D = D[~D.index.duplicated()]
    if days is not None:
        D = D.reindex(pd.DatetimeIndex(days)).fillna(0.0)
    os.makedirs(out_dir, exist_ok=True)
    D.to_parquet(os.path.join(out_dir, "daily.parquet"))
    g = G.path_a(D["x2"], D["x1"], D.index)
    json.dump(g, open(os.path.join(out_dir, "gates.json"), "w"), indent=1, default=str)
    return g
