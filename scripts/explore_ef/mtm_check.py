#!/usr/bin/env python3
"""Explore v1, POST HOC (information only): marked-to-market drawdown of W2 vs the incumbent on the engine-faithful
simulator (S*, theta 0.5, $250K), minute and instant bounds. The remainder's exit is marked at the model's cost here
(the print-priced exit applies to realized P&L only), the same for both books.

  python scripts/explore_ef/mtm_check.py

Writes reports/explore_ef/mtm_check.txt.
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
sys.path.insert(0, HERE)
import lsim  # noqa: E402
import rt_live_w as RW  # noqa: E402
import w_check  # noqa: E402

OUT = w_check.OUT


def mtm_dd(Qo, C):
    tp_t = Qo.fill_t + pd.to_timedelta(Qo.tp_off.where(Qo.tp_off >= 0, 60), unit="m")
    ex_t = Qo.fill_t + pd.Timedelta(minutes=60)
    eq = lsim.fsim.sim.mtm_equity(Qo, tp_t, ex_t)
    if not len(eq):
        return 0.0, None
    lvl = C + eq
    dd = lvl / lvl.cummax() - 1
    return float(dd.min()), dd.idxmin()


def main():
    lsim.ensure_frozen()
    cfg = "S_0.5"
    kw = lsim.CONFIGS[cfg]
    lines = ["POST HOC: marked-to-market max drawdown, engine-faithful simulator, S* theta 0.5, $250K", ""]
    for era in lsim.ERAS:
        tag = lsim.fsim.ERAS[era][0]
        for name, w in w_check.BOOKS.items():
            A = RW.era_arrays(tag, era, kw["theta"], kw["C"], kw["today"], w=w)
            parts = []
            for bound in ("minute", "instant"):
                R = RW.replay(A, theta=kw["theta"], C=kw["C"], bound=bound, policy="engine")
                _, Qo, _ = RW.evaluate_live(A, R, kw["theta"], kw["C"], era, kw["cost_mult"])
                dd, at = mtm_dd(Qo, kw["C"])
                parts.append(f"{bound} {dd:+.2%} at {at}")
            lines.append(f"{era:6s} {name:10s} " + "; ".join(parts))
            print(lines[-1], flush=True)
    open(os.path.join(OUT, "mtm_check.txt"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
