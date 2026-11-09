#!/usr/bin/env python3
"""Edge hunt 2, SHAPE and IMP: the frozen threshold rule and HOLD guards (shared by both builds).

Threshold rule (fixed before any trial, written in both REPORTs):
- n = all DEV parents (pathA.parents("sel")), including those whose feature is missing; n_skip = floor(s n + 0.5) for
  the removal share s.
- A missing feature (NaN) is never skipped: it sorts to the keep end.
- skip when HIGH: thr = the n_skip-th largest DEV value; a parent is skipped when x >= thr.
  skip when LOW:  thr = the n_skip-th smallest DEV value; a parent is skipped when x <= thr.
  +inf / -inf are ordinary values (e.g. f_W = +inf, "a drop with no net selling", is the most extreme HIGH value).
- Ties at thr are all skipped, so the realised DEV share can exceed s; it is reported with every trial.
- HOLD uses the same absolute thr and the same comparison.
"""
import os
import subprocess

import numpy as np
import pandas as pd

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def n_skip(n, s):
    return int(np.floor(s * n + 0.5))


def threshold(x_dev, side, s):
    """x_dev: feature values of every DEV parent (NaN allowed). side: 'high' or 'low'."""
    x = np.asarray(x_dev, float)
    k = n_skip(len(x), s)
    if side == "high":
        v = np.sort(np.where(np.isnan(x), -np.inf, x))[::-1]
    else:
        v = np.sort(np.where(np.isnan(x), np.inf, x))
    thr = float(v[k - 1])
    return thr


def skip_mask(x, side, thr):
    x = np.asarray(x, float)
    with np.errstate(invalid="ignore"):
        m = (x >= thr) if side == "high" else (x <= thr)
    return m & ~np.isnan(x)


def check_cells(era, cells):
    """Integrity check before a run: pathA.mult_for silently ignores cells it cannot place, so assert that every skip
    cell is a research parent of the simulator's arrays for this era (fill minute, coin)."""
    import frozen_sim as F
    A = F.arrays(era)
    par = set(zip(pd.DatetimeIndex(A["par"].ts), A["par"].coin))
    pos = A["idx"].get_indexer(pd.DatetimeIndex(cells["ts"]))
    assert (pos >= 0).all(), f"{era}: {(pos < 0).sum()} skip cells outside the simulator's minute index"
    assert all(c in list(A["coins"]) for c in cells["coin"]), f"{era}: unknown coin in skip cells"
    miss = [k for k in zip(pd.DatetimeIndex(cells["ts"]), cells["coin"]) if k not in par]
    assert not miss, f"{era}: {len(miss)} skip cells are not research parents, e.g. {miss[:3]}"
    return len(cells)


def git_head(path=WT):
    return subprocess.check_output(["git", "-C", path, "rev-parse", "HEAD"], text=True).strip()


def frozen_committed(idea):
    """True only if reports/hunt2/<idea>/frozen.json exists and is committed (the freeze commit)."""
    rel = f"reports/hunt2/{idea}/frozen.json"
    if not os.path.exists(os.path.join(WT, rel)):
        return False
    out = subprocess.run(["git", "-C", WT, "log", "-1", "--format=%H", "--", rel], text=True, capture_output=True)
    dirty = subprocess.run(["git", "-C", WT, "status", "--porcelain", "--", rel], text=True, capture_output=True)
    return bool(out.stdout.strip()) and not dirty.stdout.strip()


def require_frozen(idea, era):
    if era != "sel" and not frozen_committed(idea):
        raise RuntimeError(f"{idea}: era {era} is HOLD; it may be computed only after the freeze commit")
