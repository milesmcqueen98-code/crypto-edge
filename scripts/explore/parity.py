#!/usr/bin/env python3
"""Explore v1: xsim at its defaults reproduces rungs.run (spot-only capacity, W0 and W2, theta 0.5, bot-like) on all
three eras at $250K and $1M. Writes reports/explore/parity.txt."""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick_v4"))
import xsim  # noqa: E402
import rungs  # noqa: E402
import sim  # noqa: E402

lines, worst = [], 0.0
D = {}
for tag in ("main", "early"):
    X = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", f"pre_v4_{tag}.pkl"))
    X["in_perp"] = 0.0
    X["tp_perp"] = 0.0
    D[tag] = X
for era, (tag, (lo, hi)) in xsim.ERAS.items():
    for C in (250e3, 1e6):
        for nm, rw in (("W0", {4.0: 1, 6.0: 1, 8.0: 1}), ("W2", {4.0: 1, 6.0: 1, 8.0: 2})):
            st, d0 = rungs.run(D[tag], rungs.W[nm], lo, hi, 0.5, C, True)
            t = time.time()
            d1, Q, info = xsim.evaluate({"rungs": rw}, era, C)
            dt = time.time() - t
            diff = float(np.abs(d1.to_numpy() - d0.to_numpy()).max())
            worst = max(worst, diff)
            s1 = xsim.stats(d1, era)
            lines.append(f"{era:9s} ${C / 1e3:>5,.0f}K {nm}: rungs.py Sharpe {st['sharpe']:.4f}, xsim {s1['sharpe']:.4f}; "
                         f"max daily diff {diff:.1e} ({dt:.2f}s)")
            print(lines[-1], flush=True)
txt = "\n".join(lines + [f"largest daily difference: {worst:.1e}"]) + "\n"
os.makedirs(os.path.join(ROOT, "reports", "explore"), exist_ok=True)
open(os.path.join(ROOT, "reports", "explore", "parity.txt"), "w").write(txt)
