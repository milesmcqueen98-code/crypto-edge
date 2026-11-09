#!/usr/bin/env python3
"""Signal lab 2 (reports/signal_lab/prospective_prereg.md and its deviation 1): helpers shared by model.py, score.py
and test2.py. Free of the lab's imports, so its unit test (test_lab2.py) runs without loading anything.

  F6          the five print features, one row per candidate in reports/signal_lab/prints/f6_<era>.parquet
              (contract with the data job: coin, ts = candidate minute, complete, n_prints, usd_30, sell_usd_30,
              sell_usd_5, big_sell_usd_30, sweep_max_usd_30, big_thr_usd, adv_usd and the five features below)
  seed sets   t1 .. t5 = the five registered triples, u15 = their union (one 15-seed model), triples = all five
  panel rule  the every-minute panel of a print spec for the engine-faithful replay (deviation 1)
  lock        holdout readings of this test run only after the look-ahead audit: reports/signal_lab/test2/AUDIT_PASSED,
              created by the orchestrator, never by these scripts
"""
import io
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
T2 = os.path.join(ROOT, "reports", "signal_lab", "test2")
LOCK = os.path.join(T2, "AUDIT_PASSED")
F6_DIR = os.path.join(ROOT, "reports", "signal_lab", "prints")
F6 = ["csv_30", "csv_5", "sell_share_30", "big_sell_share_30", "sweep_max_30"]
TRIPLES = {"t1": (7, 11, 23), "t2": (1, 2, 3), "t3": (4, 5, 6), "t4": (8, 9, 10), "t5": (12, 13, 14)}
U15 = tuple(s for t in TRIPLES.values() for s in t)            # the order of the signal lab's 15-seed runs
TWIN = {"F6": "F0"}                                            # a print spec's no-prints twin: RF6 -> RF0, RF6H -> RF0H


# ------------------------------------------------------------------------------------------------ seeds
def seed_sets(name):
    """'t1' .. 't5' (one triple), 'u15' (the 15-seed union), 'triples' (the five triples in turn) or an explicit
    comma-separated list -> list of seed tuples."""
    if name in TRIPLES:
        return [TRIPLES[name]]
    if name == "u15":
        return [U15]
    if name == "triples":
        return list(TRIPLES.values())
    try:
        s = tuple(int(x) for x in name.split(","))
    except ValueError:
        raise ValueError(f"unknown seed set {name!r} (t1..t5, u15, triples or a comma-separated list)") from None
    if not s:
        raise ValueError("empty seed set")
    return [s]


def seed_name(seeds):
    """The short name of a seed tuple (t1 .. t5, u15), else the seeds joined by '-'."""
    seeds = tuple(seeds)
    for k, v in TRIPLES.items():
        if v == seeds:
            return k
    if seeds == U15:
        return "u15"
    return "-".join(str(s) for s in seeds)


# ------------------------------------------------------------------------------------------------ lock
def locked():
    return not os.path.exists(LOCK)


def check_lock(what):
    """Stop unless the look-ahead audit has passed (the orchestrator creates the lock file after it)."""
    if locked():
        raise SystemExit(f"LOCKED: {what} reads the holdout (Apr 2026 on, or 2022-23) for this test. It runs only after "
                         f"the independent look-ahead audit, when {os.path.relpath(LOCK, ROOT)} exists (created by "
                         f"the orchestrator).")


# ------------------------------------------------------------------------------------------------ print features
def load_f6(era, f6_dir=None):
    """The print-feature table of an era, validated against the contract."""
    path = os.path.join(f6_dir or F6_DIR, f"f6_{era}.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(f"print-feature table not found: {path}")
    T = pd.read_parquet(path)
    miss = [c for c in ["coin", "ts"] + F6 if c not in T.columns]
    if miss:
        raise ValueError(f"{path}: columns missing {miss}")
    T = T.copy()
    T["coin"] = T.coin.astype(str)
    T["ts"] = pd.to_datetime(T.ts).astype("datetime64[ns]")
    if T.ts.isna().any() or T.coin.isna().any():
        raise ValueError(f"{path}: rows without coin or ts")
    dup = T.duplicated(["coin", "ts"])
    if dup.any():
        raise ValueError(f"{path}: {int(dup.sum())} duplicate (coin, ts) rows, e.g. "
                         f"{T[dup][['coin', 'ts']].head(3).to_dict('records')}")
    T.attrs["path"] = path
    return T


def _key(coin, ts):
    return pd.MultiIndex.from_arrays([pd.Index(np.asarray(coin).astype(str)),
                                      pd.Index(pd.to_datetime(ts).astype("datetime64[ns]").astype("int64"))])


def join_f6(rows, T, what="candidates"):
    """F6 for each (coin, ts) row of `rows` as float32 (NaN kept where a feature is undefined). Raises if any row has no
    feature row. Returns (frame indexed like rows, number of table rows not used)."""
    k = _key(T.coin.to_numpy(), T.ts)
    pos = k.get_indexer(_key(rows.coin.to_numpy(), rows.ts))
    if (pos < 0).any():
        bad = rows.loc[pos < 0, ["coin", "ts"]]
        raise ValueError(f"{what}: {len(bad):,} of {len(rows):,} rows have no print-feature row in "
                         f"{T.attrs.get('path', 'the table')}, e.g. {bad.head(5).to_dict('records')}")
    out = pd.DataFrame({f: T[f].to_numpy(np.float32)[pos] for f in F6}, index=rows.index)
    return out, int(len(T) - len(np.unique(pos)))


def twin_of(spec):
    """RF6 -> RF0, RF6H -> RF0H; None for a spec without print features."""
    for f, g in TWIN.items():
        if f in spec:
            return spec.replace(f, g)
    return None


# ------------------------------------------------------------------------------------------------ panel rule
def replay_thresholds(thr_q):
    """{quarter: threshold} as the replay will read it: model.py writes thr.csv with DataFrame.to_csv (exact) and
    rt_live reads it with pd.read_csv, whose default float parser can be one ulp off (about 1 value in 6)."""
    s = pd.DataFrame({"thr": list(thr_q.values()), "quarter": list(thr_q)}).to_csv(index=False)
    back = pd.read_csv(io.StringIO(s))
    return dict(zip(back.quarter, back.thr))


def armed_state(v, thr):
    """rt_live's approval: the float32 panel value against the float64 quarterly threshold (NaN: never armed)."""
    return np.asarray(v, np.float32).astype(np.float64) > np.asarray(thr, np.float64)


def nudge(v, thr, want, max_steps=4):
    """Move float32 values by whole ulps until armed_state(v, thr) == want where both are finite. Returns (v, mask of
    the values moved)."""
    v = np.array(v, np.float32, copy=True)
    want = np.asarray(want, bool)
    fin = np.isfinite(v) & np.isfinite(thr)
    moved = np.zeros(len(v), bool)
    for _ in range(max_steps):
        bad = fin & (armed_state(v, thr) != want)
        if not bad.any():
            break
        up, dn = bad & want, bad & ~want
        v[up] = np.nextafter(v[up], np.float32(np.inf))
        v[dn] = np.nextafter(v[dn], np.float32(-np.inf))
        moved |= bad
    if (fin & (armed_state(v, thr) != want)).any():
        raise AssertionError("panel values could not be placed on the right side of the threshold")
    if (~np.isfinite(v) & want).any():
        raise AssertionError("a minute that must be armed has no prediction")
    return v, moved


def just_above(thr):
    """The smallest float32 values strictly above the float64 thresholds."""
    thr = np.asarray(thr, np.float64)
    v = thr.astype(np.float32)
    lo = v.astype(np.float64) <= thr
    v[lo] = np.nextafter(v[lo], np.float32(np.inf))
    assert (v.astype(np.float64) > thr).all()
    return v


def mixed_panel(px_twin, thr_twin, thr_spec, cand_pos, cand_pred, cand_want=None):
    """One coin's every-minute panel for a print spec (deviation 1 of prospective_prereg.md).
      px_twin    float32 [n]  the no-prints twin's every-minute prediction (its own exact panel)
      thr_twin   float64 [n]  each minute's quarterly threshold of the twin as the replay reads it; thr_spec: of the
                              spec (NaN: no model)
      cand_pos   int [m]      panel positions of the coin's candidate minutes (the only minutes a bid can fill)
      cand_pred  float64 [m]  the spec's own candidate-row prediction there (with its print features)
      cand_want  bool [m]     the trade list's decision there (pred > the model's threshold); default cand_pred > thr_spec
    Candidate minutes hold the spec's own prediction; every other minute the twin's, shifted by (spec threshold - twin
    threshold), so it is above the spec's threshold exactly when the twin's prediction is above the twin's threshold
    (rt_live compares float32 values with float64 thresholds: values at the margin are moved by one float32 ulp so the
    armed states hold exactly; at candidate minutes the armed state is the trade list's decision).
    Returns (float32 [n], info)."""
    px_twin = np.asarray(px_twin, np.float32)
    thr_twin, thr_spec = np.asarray(thr_twin, np.float64), np.asarray(thr_spec, np.float64)
    cand_pos, cand_pred = np.asarray(cand_pos, np.int64), np.asarray(cand_pred, np.float64)
    n = len(px_twin)
    if not (len(thr_twin) == len(thr_spec) == n) or len(cand_pos) != len(cand_pred):
        raise ValueError("length mismatch")
    if (np.isfinite(thr_twin) != np.isfinite(thr_spec)).any():
        raise ValueError("the spec and its twin must have models in the same quarters")
    if len(np.unique(cand_pos)) != len(cand_pos) or (len(cand_pos) and (cand_pos.min() < 0 or cand_pos.max() >= n)):
        raise ValueError("candidate positions must be distinct and inside the panel")
    is_c = np.zeros(n, bool)
    is_c[cand_pos] = True
    want = armed_state(px_twin, thr_twin)                     # the twin's own armed state
    with np.errstate(invalid="ignore"):
        v = (px_twin.astype(np.float64) + (thr_spec - thr_twin)).astype(np.float32)
    v, moved = nudge(v, thr_spec, want)
    if cand_want is None:
        cand_want = cand_pred > thr_spec[cand_pos]
    vc, moved_c = nudge(cand_pred.astype(np.float32), thr_spec[cand_pos], np.asarray(cand_want, bool))
    v[cand_pos] = vc
    info = dict(minutes=n, cand=int(len(cand_pos)), moved_other=int((moved & ~is_c).sum()),
                moved_cand=int(moved_c.sum()))
    return v, info


def arm_others(v, thr, cand_pos):
    """Sensitivity (deviation 1): every non-candidate minute armed. A non-candidate value not above its threshold is
    raised to the smallest float32 above it (the lowest priority among armed bids); every other value is kept.
    Minutes without a model (NaN threshold) stay unarmed."""
    v = np.array(v, np.float32, copy=True)
    thr = np.asarray(thr, np.float64)
    is_c = np.zeros(len(v), bool)
    is_c[np.asarray(cand_pos, np.int64)] = True
    low = ~is_c & np.isfinite(thr) & ~armed_state(v, thr)
    v[low] = just_above(thr[low])
    return v, int(low.sum())


def check_panel(v, thr, cand_pos, cand_pred, want_other=None, cand_want=None):
    """The built-in check of a written panel: max |panel - candidate-row prediction| at candidate minutes, armed-state
    mismatches there (against cand_want, default pred > thr), and, given want_other, armed-state mismatches at the
    other minutes."""
    v = np.asarray(v, np.float32)
    thr = np.asarray(thr, np.float64)
    cand_pos = np.asarray(cand_pos, np.int64)
    cand_pred = np.asarray(cand_pred, np.float64)
    if cand_want is None:
        cand_want = cand_pred > thr[cand_pos]
    got = v[cand_pos].astype(np.float64)
    ok = np.isfinite(got) & np.isfinite(cand_pred)
    out = dict(cand_checked=int(ok.sum()),
               cand_max_abs=float(np.abs(got[ok] - cand_pred[ok]).max()) if ok.any() else 0.0,
               cand_nan_mismatch=int((np.isfinite(got) != np.isfinite(cand_pred)).sum()),
               cand_armed_mismatch=int((armed_state(v[cand_pos], thr[cand_pos]) != np.asarray(cand_want, bool)).sum()))
    if want_other is not None:
        is_c = np.zeros(len(v), bool)
        is_c[cand_pos] = True
        out["other_armed_mismatch"] = int((armed_state(v, thr) != np.asarray(want_other, bool))[~is_c].sum())
    return out
