#!/usr/bin/env python3
"""Synthetic tests of the timing evaluator's core (evaluate.step, evaluate.run_coin).
usage: python scripts/owner/timing/test_evaluate.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluate as EV  # noqa: E402
import prints_derive as PD  # noqa: E402

TICK = 0.01
P0, P1, P3 = EV.POLICIES["P0"], EV.POLICIES["P1"], EV.POLICIES["P3"]


def path(prints, pre=100.5):
    """prints: list of (seconds after q, price)."""
    ms = np.array([1000.0 * s for s, _ in prints])
    px = np.array([p for _, p in prints], float)
    d = PD.derive(ms, px, -1000.0, pre, np.nan, np.nan, TICK)
    return EV.path_of(d)


def test_stale_only():
    # carried bid at 100 is hit at 3 s; the new bid at 99 (placed at 10 s) is never reached
    pt = path([(1, 100.2), (3, 99.98), (5, 100.3), (30, 99.5)])
    r = EV.step(100.0, 99.0, True, TICK, pt, P1)
    assert r["fill"] and r["src"] == "stale" and r["px"] == 100.0 and r["ms"] == 3000.0
    r0 = EV.step(100.0, 99.0, True, TICK, pt, P0)          # P0: no stale bid, 99 never traded through
    assert not r0["fill"] and r0["rest"] == 99.0


def test_after_placement():
    pt = path([(1, 100.5), (20, 99.97), (40, 100.4)])
    r = EV.step(99.0, 99.98 + 0.0, True, TICK, pt, P1)      # stale at 99 untouched, new at 99.98 placed at 10 s
    assert r["fill"] and r["src"] == "new" and r["ms"] == 20000.0 and r["px"] == 99.98


def test_gap_no_fill():
    # the dip at 9 s falls between the stale bid's cancel (8 s) and the new bid's placement (10 s)
    pt = path([(1, 100.5), (9, 99.0), (9.5, 100.6), (30, 100.4)])
    r = EV.step(100.0, 100.3, True, TICK, pt, P1)
    assert not r["fill"] and not r["skip"] and r["rest"] == 100.3
    r3 = EV.step(100.0, 100.3, True, TICK, pt, P3)          # no gap: the new bid rests from 8 s and is hit at 9 s
    assert r3["fill"] and r3["src"] == "new" and r3["ms"] == 9000.0
    r0 = EV.step(100.0, 100.3, True, TICK, pt, P0)
    assert r0["fill"] and r0["ms"] == 9000.0


def test_skip():
    # the last print before 10 s is at or below L: the new bid is skipped although the price trades through later
    pt = path([(1, 100.5), (9, 100.0), (20, 99.5)])
    r = EV.step(None, 100.0, True, TICK, pt, P1)
    assert r["skip"] and not r["fill"] and r["rest"] is None
    r0 = EV.step(None, 100.0, True, TICK, pt, P0)           # placed at q (last print before q is 100.5 > L)
    assert r0["fill"] and r0["ms"] == 20000.0                             # 100.0 is not one tick through 100.0; 99.5 at 20 s is


def test_half_tick_keeps_bid():
    # L(q) within half a tick of the carried bid: it rests the whole minute (the dip in the gap fills it, no skip)
    pt = path([(1, 100.5), (9, 99.99), (12, 99.5)])
    for pol in (P0, P1, P3):
        r = EV.step(100.0, 100.004, True, TICK, pt, pol)
        assert r["fill"] and r["src"] == "kept" and r["px"] == 100.0 and r["ms"] == 9000.0
    r = EV.step(100.0, 100.006, True, TICK, pt, P1)        # more than half a tick: cancelled, re-placed, skipped
    assert not r["fill"] and r["skip"]


def test_one_tick_rule():
    r = EV.step(None, 100.0, True, TICK, path([(20, 99.99)]), P1)
    assert r["fill"] and r["ms"] == 20000.0
    r = EV.step(None, 100.0, True, TICK, path([(20, 99.9901)]), P1)
    assert not r["fill"]


def test_not_approved():
    pt = path([(3, 99.0)])
    r = EV.step(100.0, 99.5, False, TICK, pt, P1)          # the stale bid still rests until its cancel
    assert r["fill"] and r["src"] == "stale"
    r = EV.step(100.0, 99.5, False, TICK, path([(20, 99.0)]), P1)
    assert not r["fill"] and r["rest"] is None


def test_run_coin():
    # minute 1 skipped (no bid carried into 2), minute 3 fills, busy until its exit at 3 + 5, a bid again from 9
    T = 12
    L = np.full(T, 100.0) + np.arange(T) * 0.1
    appr = np.ones(T, bool)
    st = {1: path([(5, 99.0)], pre=99.0),                 # P1: last before 10 s = 99 <= L: skip
          2: path([(2, L[1] - 0.05)]),                     # would hit a stale bid at L(1) if one existed
          3: path([(20, L[3] - 0.05)]),
          5: path([(20, L[5] - 0.05)]),                    # busy: ignored
          10: path([(3, L[9] - 0.05)])}                    # stale bid at L(9) (placed at 9, not studied) is hit
    pars, flags = EV.run_coin(L, appr, TICK, st, P1, lambda i, px, src: i + 5)
    assert [(p[0], p[3]) for p in pars] == [(3, "new"), (10, "stale")], pars
    assert flags[1] == (True, False)
    assert abs(pars[1][1] - L[9]) < 1e-12


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
    print("evaluator tests: all passed")
