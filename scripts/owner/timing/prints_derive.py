#!/usr/bin/env python3
"""Live order timing study (reports/owner/timing_prereg.md), step 2: one compact derived row per studied (coin, q)
from the Coinbase trade prints of [q, q + 70 s), from which every policy of the plan is evaluated without refetching.

Pure functions (no I/O); the runner (prints_runner.py) feeds them de-duplicated prints ordered by (time, trade_id).
Times are milliseconds after q (float, microsecond resolution). Placement / start times of the plan, in ms:
  0 (P0, the stale bid), 1300 (P2), 7500 (P1a), 8000 (P3), 10000 (P1), 15000 (P1b).
Per row:
  n60, n70           prints in [q, q + 60 s) and [q, q + 70 s)
  min60, min70       lowest print price in those windows (NaN without prints)
  pre_px, pre_ms     the last print stamped before q (ms < 0), NaN when unknown
  last_px_<s>, last_ms_<s>   the last print stamped before q + s (for s = 0 this is pre_px), for every start s
  ft_prev_<s>, ft_cur_<s>    the first time >= s at which a print trades at or below L(q-1) - tick (prev) or
                             L(q) - tick (cur); NaN if none before q + 70 s
  rl_ms_<s>, rl_px_<s>       the running-minimum path from q + s: every print that sets a new low since q + s
                             (lists); the first time >= s at or below any price X is the first entry with px <= X
"""
import numpy as np

STARTS = (0, 1300, 7500, 8000, 10000, 15000)
WIN_MS = 70000.0
REL_TOL = 1e-9                      # float tolerance of the one-tick trade-through comparison (relative to price)


def through(px, level, tick):
    """A print at px trades through a bid at `level` (the research's rule: px <= level - one tick)."""
    return px <= level - tick + REL_TOL * abs(level)


def running_min(ms, px, s):
    """Record lows of the prints at or after s (ms): (times, prices), strictly decreasing prices."""
    m = ms >= s
    a, b = ms[m], px[m]
    if len(b) == 0:
        return np.zeros(0), np.zeros(0)
    cm = np.minimum.accumulate(b)
    new = np.r_[True, cm[1:] < cm[:-1]]
    return a[new], b[new]


def first_through(rl_ms, rl_px, level, tick):
    """First time on a running-minimum path at which the price trades through `level`; NaN if never."""
    if not np.isfinite(level):
        return np.nan
    hit = np.nonzero(through(rl_px, level, tick))[0]
    return float(rl_ms[hit[0]]) if len(hit) else np.nan


def derive(ms, px, pre_ms, pre_px, L_prev, L, tick):
    """One studied minute. ms, px: prints in [q, q + 70 s) ordered by (time, trade_id), ms after q.
    pre_ms, pre_px: the last print before q (NaN if unknown)."""
    ms = np.asarray(ms, dtype=np.float64)
    px = np.asarray(px, dtype=np.float64)
    assert (np.diff(ms) >= 0).all() and (len(ms) == 0 or (ms[0] >= 0 and ms[-1] < WIN_MS))
    m60 = ms < 60000.0
    out = dict(n60=int(m60.sum()), n70=int(len(ms)), min60=float(px[m60].min()) if m60.any() else np.nan,
               min70=float(px.min()) if len(px) else np.nan, pre_ms=float(pre_ms), pre_px=float(pre_px))
    for s in STARTS:
        k = int(np.searchsorted(ms, s, "left"))          # prints strictly before q + s
        if k > 0:
            out[f"last_px_{s}"], out[f"last_ms_{s}"] = float(px[k - 1]), float(ms[k - 1])
        else:
            out[f"last_px_{s}"], out[f"last_ms_{s}"] = float(pre_px), float(pre_ms)
        a, b = running_min(ms, px, s)
        out[f"rl_ms_{s}"], out[f"rl_px_{s}"] = a.tolist(), b.tolist()
        out[f"ft_prev_{s}"] = first_through(a, b, L_prev, tick)
        out[f"ft_cur_{s}"] = first_through(a, b, L, tick)
    return out
