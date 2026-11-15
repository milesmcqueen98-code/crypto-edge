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
N1, N3, B1 = EV.POLICIES3["N1"], EV.POLICIES3["N3"], EV.POLICIES3["B1"]
ALL_STARTS = tuple(sorted(set(PD.STARTS) | {v[1] for v in EV.POLICIES3.values()}))


def path(prints, pre=100.5):
    """prints: list of (seconds after q, price)."""
    ms = np.array([1000.0 * s for s, _ in prints])
    px = np.array([p for _, p in prints], float)
    d = PD.derive(ms, px, -1000.0, pre, np.nan, np.nan, TICK, starts=ALL_STARTS)
    return EV.path_of(d, ALL_STARTS)


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


# ------------------------------------------------------------------------------------------------ part 3
def test_policies3_table():
    # the plan's table (seconds) in ms; N1 to N3 carry no bid; the six policies of parts 1 and 2 are unchanged
    want = {"B0": (14.25, 17.25), "B0f": (12.4, 13.9), "B0s": (18.0, 24.0), "B1": (10.8, 11.7), "B2": (9.3, 10.2),
            "B3": (4.3, 5.2), "B4": (1.1, 2.0), "B1r": (10.7, 12.15), "B2r": (9.63, 11.08), "N1": (0, 11.7),
            "N2": (0, 10.2), "N3": (0, 5.2)}
    assert list(EV.POLICIES3) == list(want)
    for k, (c, p) in want.items():
        v = EV.POLICIES3[k]
        assert v[0] == round(1000 * c, 6) and v[1] == round(1000 * p) and EV.carries(v) == (k[0] == "B"), k
    assert EV.POLICIES == {"P0": (0.0, 0), "P1": (8000.0, 10000), "P1a": (6500.0, 7500), "P1b": (12000.0, 15000),
                           "P2": (1000.0, 1300), "P3": (8000.0, 8000)}


def test_no_carry_no_stale():
    # a bid carried in at 100 would fill at 3 s (B1: stale until 10.8 s); with no carried bid it does not exist
    pt = path([(1, 100.2), (3, 99.98), (5, 100.3), (30, 99.5)])
    r = EV.step(100.0, 99.0, True, TICK, pt, B1)
    assert r["fill"] and r["src"] == "stale"
    r = EV.step(100.0, 99.0, True, TICK, pt, N1)
    assert not r["fill"] and not r["skip"] and r["rest"] is None       # the new bid at 99 rests to 60 s only
    r = EV.step(100.0, 99.6, True, TICK, pt, N1)                        # new bid at 99.6 from 11.7 s: hit at 30 s
    assert r["fill"] and r["src"] == "new" and r["px"] == 99.6 and r["ms"] == 30000.0


def test_no_carry_no_kept():
    # L within half a tick of the carried bid: B1 keeps it (the dip at 9 s fills it); N1 places a new bid at 11.7 s
    pt = path([(1, 100.5), (9, 99.99), (12, 99.5)])
    r = EV.step(100.0, 100.004, True, TICK, pt, B1)
    assert r["fill"] and r["src"] == "kept" and r["ms"] == 9000.0
    r = EV.step(100.0, 100.004, True, TICK, pt, N1)                     # last print before 11.7 s is 99.99 <= L
    assert not r["fill"] and r["skip"] and r["rest"] is None
    r = EV.step(100.0, 100.004, True, TICK, path([(1, 100.5), (9, 100.2), (12, 99.5)]), N1)
    assert r["fill"] and r["src"] == "new" and r["px"] == 100.004 and r["ms"] == 12000.0
    r = EV.step(100.0, 100.004, True, TICK, path([(1, 100.5), (9, 100.2)]), N1)
    assert not r["fill"] and not r["skip"] and r["rest"] is None       # not filled: nothing carried out


def test_no_carry_placement_time_and_skip():
    # placed at exactly p: a print at p belongs to the new bid's path; the skip test reads the last print before p
    pt = path([(1, 100.5), (5.2, 99.98), (6, 100.4)])
    r = EV.step(None, 100.0, True, TICK, pt, N3)
    assert r["fill"] and r["ms"] == 5200.0
    r = EV.step(None, 100.0, True, TICK, path([(1, 100.5), (5.1, 100.0), (20, 99.5)]), N3)
    assert r["skip"] and not r["fill"]
    r = EV.step(None, 100.0, True, TICK, path([(1, 100.5), (5.1, 100.0), (20, 99.5)]), N1)   # 11.7 s: last 100.0
    assert r["skip"] and not r["fill"]
    r = EV.step(None, 100.0, False, TICK, path([(20, 99.0)]), N1)       # not approved: nothing
    assert not r["fill"] and not r["skip"] and r["rest"] is None
    # carry=True as a third field is the same as two fields
    for pt in (path([(3, 99.0)]), path([(1, 100.5), (9, 99.99), (12, 99.5)]), path([(20, 99.97)])):
        for rest in (None, 100.0):
            a = EV.step(rest, 100.0, True, TICK, pt, P1)
            b = EV.step(rest, 100.0, True, TICK, pt, (8000.0, 10000, True))
            assert {k: v for k, v in a.items() if k not in ("px", "ms")} == \
                {k: v for k, v in b.items() if k not in ("px", "ms")}


def test_run_coin_no_carry():
    # P1 fills minute 10 on the stale bid placed at 9 (not studied); N1 never does, and fills minute 11 on its new
    # bid; the fill makes the coin busy until its exit; an unapproved minute places nothing
    T = 20
    L = np.full(T, 100.0) + np.arange(T) * 0.1
    appr = np.ones(T, bool)
    appr[14] = False
    st = {10: path([(3, L[9] - 0.05)], pre=200),
          11: path([(20, L[11] - 0.05)], pre=200),
          12: path([(20, L[12] - 0.05)], pre=200),                  # busy (N1 filled at 11, exit 11 + 2)
          14: path([(20, L[14] - 0.05)], pre=200),                  # not approved
          15: path([(3, L[14] - 0.05), (5, L[13] - 0.05)], pre=200)}  # nothing carried in: no fill before 11.7 s, none after
    pars, _ = EV.run_coin(L, appr, TICK, st, P1, lambda i, px, src: i + 2)
    assert [(p[0], p[3]) for p in pars] == [(10, "stale")], pars
    pars, flags = EV.run_coin(L, appr, TICK, st, N1, lambda i, px, src: i + 2)
    assert [(p[0], p[3], p[2]) for p in pars] == [(11, "new", 20000.0)], pars
    # 10 and 15: the last print before 11.7 s is below L (skip); 12 busy; 14 not approved
    assert flags[10] == (True, False) and 12 not in flags and flags[14] == (False, False) and flags[15] == (True, False)
    # with every minute studied and no fill, each approved minute places a new bid at 11.7 s
    st2 = {i: path([(1, L[i] + 0.5), (11.7, L[i] + 0.3)] + ([(30, L[i] - 0.05)] if i == 7 else []), pre=200)
           for i in range(1, T)}
    pars, flags = EV.run_coin(L, appr, TICK, st2, N1, lambda i, px, src: i + 2)
    assert [(p[0], p[3], p[2]) for p in pars] == [(7, "new", 30000.0)] and not any(f[0] for f in flags.values())
    assert sorted(flags) == [i for i in range(1, T) if i not in (8, 9)]


def test_union_layout():
    # part 3's rows store one union of the paths (time, then falling price); path_of rebuilds every start exactly
    rng = np.random.default_rng(5)
    for _ in range(200):
        n = int(rng.integers(0, 90))
        ms = np.sort(rng.choice(np.arange(0, 70000, 100.0), n))
        px = np.round(100 + np.cumsum(rng.normal(0, 0.03, n)), 2)
        d = PD.derive(ms, px, -10.0, 100.1, 99.9, 99.8, TICK, starts=ALL_STARTS)
        pts = sorted({(a, b) for s in ALL_STARTS for a, b in zip(d[f"rl_ms_{s}"], d[f"rl_px_{s}"])},
                     key=lambda x: (x[0], -x[1]))
        u = {k: v for k, v in d.items() if not k.startswith("rl_")}
        u["un_ms"], u["un_px"] = [a for a, _ in pts], [b for _, b in pts]
        a, b = EV.path_of(d, ALL_STARTS), EV.path_of(u, ALL_STARTS)
        for s in ALL_STARTS:
            assert np.array_equal(a["rl"][s][0], b["rl"][s][0]) and np.array_equal(a["rl"][s][1], b["rl"][s][1])
            assert a["last"][s] == b["last"][s] or (np.isnan(a["last"][s]) and np.isnan(b["last"][s]))
        for pol in list(EV.POLICIES.values()) + list(EV.POLICIES3.values()):
            for rest in (None, 99.9):
                ra, rb = EV.step(rest, 99.8, True, TICK, a, pol), EV.step(rest, 99.8, True, TICK, b, pol)
                assert str(ra) == str(rb)


if __name__ == "__main__":
    n = 0
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            n += 1
    print(f"evaluator tests: all {n} passed")
