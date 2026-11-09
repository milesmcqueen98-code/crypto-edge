#!/usr/bin/env python3
"""Explore v1, POST HOC (information only): paired comparison of W2 and the incumbent on the engine-faithful
simulator (S*, theta 0.5, $250K): the vol-matched daily difference d_t = r_W2 / sd_W2 - r_inc / sd_inc in each era,
its stationary-bootstrap t (mean block 7 days), the share of positive months, and the result without each book's
best 5 days. W2 was chosen post hoc in wick v4 and its check / 2022-23 rungs.py readings were already known, so none
of this is out-of-sample evidence.

  python scripts/explore_ef/w_paired.py

Writes reports/explore_ef/w_paired.txt.
"""
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
sys.path.insert(0, HERE)
import lsim  # noqa: E402
import w_check  # noqa: E402
from edge import book as edge_book  # noqa: E402


def stationary_idx(n, rng, mean_block=7):
    out = np.empty(n, int)
    i = rng.integers(n)
    for t in range(n):
        out[t] = i
        i = rng.integers(n) if rng.random() < 1.0 / mean_block else (i + 1) % n
    return out


def sharpe(e):
    return float(e.mean() / e.std(ddof=1) * math.sqrt(365))


def main():
    lsim.ensure_frozen()
    rng = np.random.default_rng(11)
    lines = ["POST HOC: W2 vs the incumbent, engine-faithful simulator, S* theta 0.5, $250K (blended, print exits)", ""]
    for era in lsim.ERAS:
        lo, hi = lsim.fsim.ERAS[era][1]
        idx = pd.date_range(lo, hi, freq="D")
        rf = edge_book.rf_daily(idx).to_numpy()
        r0 = w_check.daily("S_0.5", era, w_check.BOOKS["incumbent"]).reindex(idx, fill_value=0.0)
        r1 = w_check.daily("S_0.5", era, w_check.BOOKS["W2"]).reindex(idx, fill_value=0.0)
        e0, e1 = r0.to_numpy() - rf, r1.to_numpy() - rf
        d = e1 / e1.std(ddof=1) - e0 / e0.std(ddof=1)
        bs = np.array([d[stationary_idx(len(d), rng)].mean() for _ in range(2000)])
        t = d.mean() / bs.std(ddof=1)
        mon = (r1 - r0).groupby(idx.to_period("M")).sum()
        keep0 = np.ones(len(e0), bool)
        keep0[np.argsort(-r0.to_numpy())[:5]] = False
        keep1 = np.ones(len(e1), bool)
        keep1[np.argsort(-r1.to_numpy())[:5]] = False
        lines.append(f"{era:6s} ΔSharpe {sharpe(e1) - sharpe(e0):+.3f} (t {t:+.2f}); corr {np.corrcoef(e0, e1)[0, 1]:.3f}; "
                     f"months W2 ahead {int((mon > 0).sum())}/{len(mon)}; without each book's best 5 days "
                     f"{sharpe(e1[keep1]) - sharpe(e0[keep0]):+.3f}")
        print(lines[-1], flush=True)
    open(os.path.join(w_check.OUT, "w_paired.txt"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
