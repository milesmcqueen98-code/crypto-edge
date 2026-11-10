#!/usr/bin/env python3
"""Synthetic tests of the print reduction (prints_derive.derive, prints_runner.derive_window). Run before the fetch
on the runner (a failure stops the job) and here.
usage: python scripts/owner/timing/test_derive.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prints_derive as PD  # noqa: E402


def brute_first(ms, px, s, level, tick):
    for a, b in zip(ms, px):
        if a >= s and b <= level - tick + 1e-9 * level:
            return a
    return np.nan


def test_derive_random():
    rng = np.random.default_rng(1)
    for _ in range(300):
        n = int(rng.integers(0, 80))
        ms = np.sort(rng.uniform(0, 70000, n))
        px = 100 + np.cumsum(rng.normal(0, 0.05, n))
        Lp, L, tick = 100 - rng.uniform(0, 0.5), 100 - rng.uniform(0, 0.5), 0.01
        d = PD.derive(ms, px, -500.0, 100.2, Lp, L, tick)
        for s in PD.STARTS:
            for lev, key in ((Lp, "prev"), (L, "cur")):
                a, b = d[f"ft_{key}_{s}"], brute_first(ms, px, s, lev, tick)
                assert (np.isnan(a) and np.isnan(b)) or a == b, (s, key, a, b)
                # the running-minimum path answers the same query for any level
                rl = PD.first_through(np.array(d[f"rl_ms_{s}"]), np.array(d[f"rl_px_{s}"]), lev, tick)
                assert (np.isnan(rl) and np.isnan(b)) or rl == b
            k = np.nonzero(ms < s)[0]
            want = px[k[-1]] if len(k) else 100.2
            assert d[f"last_px_{s}"] == want
        assert d["n60"] == int((ms < 60000).sum()) and d["n70"] == n


def test_boundary():
    # exactly one tick through fills; a hair less does not
    d = PD.derive(np.array([100.0, 200.0]), np.array([99.99, 99.98]), -1.0, 100.0, 100.0, 100.0, 0.01)
    assert d["ft_cur_0"] == 100.0
    d = PD.derive(np.array([100.0]), np.array([99.9901]), -1.0, 100.0, 100.0, 100.0, 0.01)
    assert np.isnan(d["ft_cur_0"])


def test_window():
    import prints_runner as PR
    q = pd.Timestamp("2025-03-01 12:00:00")
    t = [q - pd.Timedelta(seconds=2), q + pd.Timedelta(seconds=3), q + pd.Timedelta(seconds=61),
         q + pd.Timedelta(seconds=75)]
    D = pd.DataFrame(dict(trade_id=[1, 2, 3, 4], time=t, price=[10.0, 9.0, 8.0, 7.0], size=1.0, side="BUY"))
    D = D[D.time >= q]                                     # the fetch keeps [start, end) only
    pre = pd.Series(dict(trade_id=1, time=t[0], price=10.0))
    rows = pd.DataFrame(dict(tag="main", coin="X", q=[q, q + pd.Timedelta(minutes=1)], L_prev=9.5, L=9.5,
                             tick=0.1, window_id=0))
    a, b = PR.derive_window(D, pre, rows)
    assert a["pre_px"] == 10.0 and a["pre_ms"] == -2000.0 and a["n70"] == 2 and a["ft_cur_0"] == 3000.0
    assert b["pre_px"] == 9.0 and b["pre_ms"] == -57000.0 and b["n70"] == 2 and b["ft_cur_0"] == 1000.0


if __name__ == "__main__":
    test_derive_random()
    test_boundary()
    test_window()
    print("prints_derive tests: all passed")
