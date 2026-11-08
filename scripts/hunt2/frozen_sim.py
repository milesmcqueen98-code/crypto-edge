#!/usr/bin/env python3
"""Edge hunt 2: thin wrapper over ladder v6's frozen simulator (scripts/ladder_v6x/lsim.py, unchanged).

Cost settings (reports/hunt2_prereg.md):
  S   the incumbent's best estimate (ladder v5/v6): today's volumes, unverified model costs x2 (half-spread, impact),
      published fees x1, print-measured exit costs x1.
  X1  "1x": today's volumes, every cost term at its realistic value (model x1, fees x1, prints x1).
  X2  "2x": today's volumes, every cost term doubled (model x2, fee tiers x2, print-measured exit costs x2).
Frozen files are never edited: fees are doubled by passing a doubled tier table to fsim.evaluate, and print costs by
scaling PrintCost.cost, both at call time.

Path A candidates enter through the multiplier hook m(t, coin) (ladder v6 sizing's semantics, scripts/ladder_v6s):
every minute's 4-sigma bid is scaled by m; a parent fill's deeper rungs take m at the fill minute. A filter that skips
a signal uses m = SKIP (1e-9: the bid is effectively zero; the hook requires m > 0).
"""
import functools
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
import lsim  # noqa: E402
from lsim import RL, fsim  # noqa: E402

SKIP = 1e-9
COST = {"S": dict(cost_mult=2.0, fee_mult=1.0, print_mult=1.0),
        "X1": dict(cost_mult=1.0, fee_mult=1.0, print_mult=1.0),
        "X2": dict(cost_mult=2.0, fee_mult=2.0, print_mult=2.0)}
_ORIG_EVAL = fsim.evaluate
_ORIG_PC = lsim.pcost
_A = {}


class _ScaledPC:
    def __init__(self, pc, k):
        self.pc, self.k = pc, k

    def cost(self, *a, **kw):
        c = self.pc.cost(*a, **kw)
        return c * self.k if np.isfinite(c) else c


def _set_costs(cost):
    kw = COST[cost]
    tiers = [(v, mk * kw["fee_mult"], tk * kw["fee_mult"]) for v, mk, tk in fsim.sim.SPOT_TIERS]
    fsim.evaluate = functools.partial(_ORIG_EVAL, tiers=tiers) if kw["fee_mult"] != 1.0 else _ORIG_EVAL
    pm = kw["print_mult"]
    lsim.pcost = (lambda: _ScaledPC(_ORIG_PC(), pm)) if pm != 1.0 else _ORIG_PC


def cfg_name(theta, C, cost):
    name = f"h2_{cost}_{theta}_{int(C)}"
    lsim.CONFIGS[name] = dict(theta=theta, C=C, today=True, cost_mult=COST[cost]["cost_mult"])
    return name


def arrays(era, theta=0.5, C=250e3):
    key = (era, theta, C)
    if key not in _A:
        lsim.ensure_frozen()
        _A[key] = RL.era_arrays(fsim.ERAS[era][0], era, theta, C, True)
    return _A[key]


def with_mult(A, mfac):
    """Arrays with the 4-sigma wants scaled by mfac (T x NC, all > 0): ladder v6 sizing's with_mult, unchanged."""
    assert mfac.shape == A["want4"].shape and np.all(mfac > 0)
    A2 = dict(A)
    A2["mfac"] = mfac
    A2["want4"] = A["want4"] * mfac
    pm = mfac[A["p_t"], A["p_c"]] if A["NP"] else np.ones(0)
    A2["p_mult"] = pm
    A2["p_want"] = A["p_wbase"] * pm
    return A2


def daily(era, theta=0.5, C=250e3, cost="S", mfac=None, detail=False):
    """Daily P&L / C of the live bot (1-second blend of the two latency bounds, print-measured exit costs) on the frozen
    simulator, under cost setting `cost`, optionally with a multiplier array mfac (T x NC)."""
    _set_costs(cost)
    try:
        name = cfg_name(theta, C, cost)
        A = arrays(era, theta, C)
        A2 = A if mfac is None else with_mult(A, mfac)
        d, Q = {}, {}
        for bound in ("minute", "instant"):
            R = RL.replay(A2, theta=theta, C=C, bound=bound, policy="engine")
            _, Qo, info = RL.evaluate_live(A2, R, theta, C, era, COST[cost]["cost_mult"])
            d[bound] = lsim.rem_daily(Qo, info, name, era, C, "print")[0]
            Q[bound] = (Qo, info)
        out = lsim.blend(era, theta, d["minute"], d["instant"])
    finally:
        _set_costs("S") if cost != "S" else None
        fsim.evaluate, lsim.pcost = _ORIG_EVAL, _ORIG_PC
    return (out, Q) if detail else out


if __name__ == "__main__":
    # parity: S at $250K, theta 0.5 must reproduce the cached incumbent exactly
    for era in fsim.ERAS:
        a = daily(era)
        b = lsim.incumbent_daily("S_0.5", era)
        print(era, "max |diff| vs cached incumbent:", float((a - b).abs().max()))
