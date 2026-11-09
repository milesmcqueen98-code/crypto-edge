#!/usr/bin/env python3
"""Explore v1, POST HOC (information only): does the W2 paper book (rungs 4 / 6 / 8 sigma at 1:1:2) still beat the
incumbent (thirds) on the engine-faithful simulator, which charges resting bids for the cash they hold?

  python scripts/explore_ef/w_check.py

Ladder v6's frozen simulator (scripts/ladder_v6x/lsim.py): the engine-faithful cash rule (red team 1's replay), print-
priced remainder exits (red team 2), the 1-second blend. Rung weights enter through scripts/explore_ef/rt_live_w.py, a
copy of the frozen replay whose only change is the weights; with thirds it must reproduce the frozen replay exactly
(checked first, every era). Configurations as in ladder v5: S* (today's volumes, unverified costs doubled) at theta 0.5
and 0.25, $1M, and base (research volumes, 1x costs).
Writes reports/explore_ef/w_check.txt and w_check.csv.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
sys.path.insert(0, HERE)
import lsim  # noqa: E402
import rt_live_w as RW  # noqa: E402

OUT = os.path.join(ROOT, "reports", "explore_ef")
BOOKS = {"incumbent": (1 / 3, 1 / 3, 1 / 3), "W2": (0.25, 0.25, 0.5)}
CFGS = ("S_0.5", "S_0.25", "cap_1M", "base_0.5")


def daily(cfg, era, w):
    kw = lsim.CONFIGS[cfg]
    tag = lsim.fsim.ERAS[era][0]
    A = RW.era_arrays(tag, era, kw["theta"], kw["C"], kw["today"], w=w)
    d = {}
    for bound in ("minute", "instant"):
        R = RW.replay(A, theta=kw["theta"], C=kw["C"], bound=bound, policy="engine")
        _, Qo, info = RW.evaluate_live(A, R, kw["theta"], kw["C"], era, kw["cost_mult"])
        d[bound] = lsim.rem_daily(Qo, info, cfg, era, kw["C"], cost="print")[0]
    return lsim.blend(era, kw["theta"], d["minute"], d["instant"])


def main():
    lsim.ensure_frozen()
    os.makedirs(OUT, exist_ok=True)
    lines = ["POST HOC (information only): W2 vs the incumbent on ladder v6's frozen engine-faithful simulator", ""]
    worst = 0.0
    for era in lsim.ERAS:                                   # parity: thirds through the weighted copy = frozen replay
        ref = lsim.incumbent_daily("S_0.5", era, out=lsim.bound_books("S_0.5", era))
        mine = daily("S_0.5", era, BOOKS["incumbent"])
        worst = max(worst, float(np.abs(ref.to_numpy() - mine.to_numpy()).max()))
    lines.append(f"parity (S* theta 0.5, all eras): thirds through rt_live_w vs the frozen replay, max daily diff {worst:.1e}")
    assert worst < 1e-12, worst
    rows = []
    for cfg in CFGS:
        kw = lsim.CONFIGS[cfg]
        for era in lsim.ERAS:
            rec = dict(cfg=cfg, era=era)
            ser = {}
            for name, w in BOOKS.items():
                ser[name] = daily(cfg, era, w)
                st = lsim.fsim.stats(ser[name], kw["C"], era)
                rec[f"sharpe_{name}"], rec[f"ret_{name}"], rec[f"maxdd_{name}"] = st["sharpe"], st["ret_yr"], st["maxdd"]
                rec[f"worst_{name}"] = float(ser[name].min())
            rec["d_sharpe"] = rec["sharpe_W2"] - rec["sharpe_incumbent"]
            rows.append(rec)
            print(cfg, era, round(rec["sharpe_incumbent"], 3), round(rec["sharpe_W2"], 3), flush=True)
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, "w_check.csv"), index=False)
    pd.set_option("display.width", 220)
    lines += ["", "Sharpe, return a year, daily max drawdown and worst day (blended, print-priced exits):",
              T.round(4).to_string(index=False)]
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "w_check.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
