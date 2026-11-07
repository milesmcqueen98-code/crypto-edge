#!/usr/bin/env python3
"""Ladder v5, C1: who gets the cash when resting bids compete for it (reports/ladder_v5_prereg.md).

C1a "deeper first": a 6/8-sigma rung that is short of cash takes the holds of the lowest-prediction 4-sigma bids
(they are cancelled); the 4-sigma bids are re-allocated each minute from what is left.
C1b "reserve": the 4-sigma bids may hold at most 50% of equity in total.
Both are policies of the frozen hold-aware simulator (hsim); everything else is the incumbent.
usage: python scripts/ladder_v5/cand_cash.py [check]
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gates  # noqa: E402
import hsim  # noqa: E402


def make(policy, reserve=0.0):
    def book_fn(P, era, pan=None, adv_=None, theta=0.5, C=250e3, today=False, cost_mult=1.0):
        d, _ = hsim.book(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, pan=pan, adv=adv_,
                         policy=policy, reserve=reserve)
        return d
    return book_fn


def check():
    """Off switch: policy 'engine' must reproduce the cached incumbent exactly."""
    P, pan = gates.data("main")
    d = make("engine")(P, "chk", pan=pan, adv_=gates.adv("main", "chk"), **gates.CONFIGS["S_0.5"])
    inc = gates.incumbent_cached("chk", "S_0.5")
    print("off-switch max daily difference:", float(np.abs(d.reindex(inc.index, fill_value=0.0) - inc).max()))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check()
    else:
        for name, pol, res in (("C1a_deeper_first", "preempt", 0.0), ("C1b_reserve50", "reserve", 0.5)):
            out = gates.run(name, make(pol, res), path="return")
            print(gates.summary(out), flush=True)
