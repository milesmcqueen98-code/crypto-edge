#!/usr/bin/env python3
"""Sizing lab: the flat books reproduce through the sizing hook (reports/sizing_lab/prereg.md).

1. rungs.run with mult=None reproduces reports/wick_v4/rungs.csv (W0, W2; theta 0.5, bot-like; $250K, $1M; 3 eras).
2. mult = 1 everywhere (ADV-capped and uncapped) gives the same daily P&L as mult=None.
3. Spot-only capacity (in_perp = tp_perp = 0) reproduces reports/wick_v4/spot_only.csv (W0, minute bot).
4. The lab's flat baselines: spot-only, main (W0) and W2 books. Writes reports/sizing_lab/reproduce.txt.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick_v4"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
import sim  # noqa: E402
import rungs  # noqa: E402

OUT = os.path.join(ROOT, "reports", "sizing_lab")


def main():
    P = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", "pre_v4_main.pkl"))
    E = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", "pre_v4_early.pkl"))
    R = pd.read_csv(os.path.join(ROOT, "reports", "wick_v4", "rungs.csv"))
    S = pd.read_csv(os.path.join(ROOT, "reports", "wick_v4", "spot_only.csv"))
    eras = {"selection": (P, sim.SEL), "check": (P, sim.CHK), "fresh_2022_23": (E, sim.EARLY)}
    lines, worst_csv, worst_one = [], 0.0, 0.0
    ones = lambda Q: np.ones(len(Q))  # noqa: E731
    for era, (D, (lo, hi)) in eras.items():
        Ds = D.copy()
        Ds["in_perp"] = 0.0
        Ds["tp_perp"] = 0.0
        for C in (250e3, 1e6):
            for nm in ("W0", "W2"):
                st, d = rungs.run(D, rungs.W[nm], lo, hi, 0.5, C, True)
                ref = R[(R.era == era) & (R.capital == C) & (R.theta == 0.5) & R.bot_like & (R.cand == nm)].iloc[0]
                worst_csv = max(worst_csv, abs(st["ret_yr"] - ref.ret_yr), abs(st["sharpe"] - ref.sharpe))
                for cap in (True, False):
                    _, d1 = rungs.run(D, rungs.W[nm], lo, hi, 0.5, C, True, mult=ones, mult_cap=cap)
                    worst_one = max(worst_one, float(np.abs(d1 - d).max()))
            st, _ = rungs.run(Ds, rungs.W["W0"], lo, hi, 0.5, C, True)
            ref = S[(S.era == era) & (S.capital == C) & (S.theta == 0.5)].iloc[0]
            worst_csv = max(worst_csv, abs(st["ret_yr"] - ref.minute_ret), abs(st["sharpe"] - ref.minute_sharpe))
            for nm in ("W0", "W2"):
                st, _ = rungs.run(Ds, rungs.W[nm], lo, hi, 0.5, C, True)
                book = "main" if nm == "W0" else "W2"
                lines.append(f"{era:14s} ${C / 1e3:>5,.0f}K {book:4s}  return {st['ret_yr']:6.2%}  Sharpe {st['sharpe']:.3f}  "
                             f"max DD {st['maxdd']:.2%}  fills {st['fills']}")
    head = [f"rungs.csv (W0, W2) and spot_only.csv (W0) through rungs.run, mult=None: largest difference {worst_csv:.1e}",
            f"mult = 1 (ADV-capped and uncapped) vs mult=None, daily returns: largest difference {worst_one:.1e}",
            "", "Flat baselines of the lab (spot-only capacity, theta 0.5, bot-like):"]
    txt = "\n".join(head + lines) + "\n"
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "reproduce.txt"), "w") as f:
        f.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
