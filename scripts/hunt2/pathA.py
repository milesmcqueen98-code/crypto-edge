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
