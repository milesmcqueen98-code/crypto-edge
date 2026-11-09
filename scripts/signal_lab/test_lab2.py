#!/usr/bin/env python3
"""Unit tests of scripts/signal_lab/lab2.py on small synthetic arrays (no lab, no data):
the every-minute panel rule of deviation 1, the all-armed sensitivity flag, the print-feature join and the seed sets.

  python scripts/signal_lab/test_lab2.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab2  # noqa: E402


def approve(M, th):
    """rt_live.era_arrays' approval, verbatim: a float32 panel against float64 per-minute thresholds."""
    return np.asarray(M, np.float32) > np.asarray(th, np.float64)


def quarters(n, thr_by_q, cut):
    """Per-minute thresholds: quarter 0 before `cut`, quarter 1 after (NaN = no model in that quarter)."""
    t = np.empty(n)
    t[:cut], t[cut:] = thr_by_q
    return t


def test_mixed_rule():
    rng = np.random.default_rng(0)
    n, cut = 400, 250
    thr_t = quarters(n, (30.0, 28.5), cut)                      # twin's thresholds
    thr_s = quarters(n, (26.123456789, 33.987654321), cut)      # spec's (different) thresholds
    px_t = (thr_t + rng.normal(0, 4, n)).astype(np.float32)
    px_t[7] = np.float32(np.nan)                                # a twin minute without a prediction
    cand = np.array([3, 10, 120, 251, 399])
    cand_pred = thr_s[cand] + np.array([1.5, -2.0, 0.0, 1e-9, -1e-9])   # incl. predictions at and around the threshold
    v, info = lab2.mixed_panel(px_t, thr_t, thr_s, cand, cand_pred)
    assert v.dtype == np.float32 and len(v) == n
    is_c = np.zeros(n, bool)
    is_c[cand] = True
    # candidate minutes: the spec's own prediction, with the trade list's armed state (pred > thr)
    assert np.abs(v[cand].astype(np.float64) - cand_pred).max() < 1e-5
    assert (approve(v[cand], thr_s[cand]) == (cand_pred > thr_s[cand])).all()
    # every other minute: the twin's armed state under the spec's threshold, and the twin's value shifted
    assert (approve(v, thr_s) == approve(px_t, thr_t))[~is_c].all()
    ok = ~is_c & np.isfinite(px_t)
    assert np.abs(v[ok].astype(np.float64) - (px_t[ok].astype(np.float64) + thr_s[ok] - thr_t[ok])).max() < 1e-5
    assert np.isnan(v[7])
    # the built-in check agrees
    chk = lab2.check_panel(v, thr_s, cand, cand_pred, want_other=approve(px_t, thr_t))
    assert chk["cand_armed_mismatch"] == 0 and chk["other_armed_mismatch"] == 0 and chk["cand_max_abs"] < 1e-5
    assert info["cand"] == len(cand)


def test_margin_rounding():
    """float32 rounding at the threshold must not flip an armed state (rt_live compares float32 with float64)."""
    one = 1.0
    up = np.nextafter(np.float32(1.0), np.float32(2.0))          # the twin just above its threshold: armed
    px_t = np.array([up, np.float32(1.0), up, np.float32(1.0)], np.float32)
    thr_t = np.full(4, one)
    thr_s = np.full(4, 1000.0000001)                             # float32 ulp at 1000 is 6e-5: px + shift rounds to 1000
    v, info = lab2.mixed_panel(px_t, thr_t, thr_s, np.array([], np.int64), np.array([]))
    assert (approve(v, thr_s) == approve(px_t, thr_t)).all()     # [True, False, True, False]
    assert approve(v, thr_s).tolist() == [True, False, True, False]
    assert info["moved_other"] >= 2                              # the naive shift would have disarmed them
    naive = (px_t.astype(np.float64) + (thr_s - thr_t)).astype(np.float32)
    assert not approve(naive, thr_s)[0]                          # (so the case does exercise the correction)
    # a candidate prediction a hair above / at its threshold keeps the trade list's decision
    thr_c = np.full(3, 0.1)
    pred = np.array([0.1 + 1e-12, 0.1, 0.1 - 1e-12])
    assert approve(pred.astype(np.float32), thr_c).tolist() == [True, True, True]   # naive float32: all armed
    vc, info = lab2.mixed_panel(np.zeros(3, np.float32), thr_c, thr_c, np.arange(3), pred)
    assert approve(vc, thr_c).tolist() == [True, False, False] and info["moved_cand"] == 2


def test_no_model_quarter():
    n = 10
    thr_t = np.r_[np.full(5, np.nan), np.full(5, 2.0)]
    thr_s = np.r_[np.full(5, np.nan), np.full(5, 3.0)]
    px_t = np.r_[np.full(5, np.nan), np.array([1, 2.5, 2.0, 3, 1.9])].astype(np.float32)
    v, _ = lab2.mixed_panel(px_t, thr_t, thr_s, np.array([1, 6]), np.array([np.nan, 3.5]))
    assert not approve(v, thr_s)[:5].any()
    assert approve(v, thr_s)[5:].tolist() == [False, True, False, True, False]   # minute 6 is the candidate (3.5 > 3)
    bad = np.r_[np.full(5, np.nan), np.full(5, 3.0)]
    try:
        lab2.mixed_panel(px_t, np.full(n, 2.0), bad, np.array([1]), np.array([0.0]))
        raise AssertionError("expected a quarter mismatch error")
    except ValueError:
        pass
    try:
        lab2.mixed_panel(px_t, thr_t, thr_s, np.array([1, 1]), np.array([0.0, 0.0]))
        raise AssertionError("expected a duplicate-candidate error")
    except ValueError:
        pass


def test_all_armed_flag():
    rng = np.random.default_rng(1)
    n, cut = 300, 120
    thr = quarters(n, (5.0, 7.25), cut)
    thr[:20] = np.nan                                            # no model yet: stays unarmed
    v0 = (thr + rng.normal(0, 3, n)).astype(np.float32)
    v0[50] = np.float32(np.nan)                                  # a minute without a prediction is armed too
    cand = np.array([25, 60, 130, 200])
    v0[cand] = (thr[cand] - 1.0).astype(np.float32)              # unarmed candidates must stay unarmed
    v1, n_raised = lab2.arm_others(v0, thr, cand)
    is_c = np.zeros(n, bool)
    is_c[cand] = True
    a0, a1 = approve(v0, thr), approve(v1, thr)
    assert a1[~is_c & np.isfinite(thr)].all()
    assert not a1[:20].any()
    assert (v1[cand] == v0[cand]).all() and not a1[cand].any()
    keep = a0 & ~is_c
    assert (v1[keep] == v0[keep]).all()                          # already armed: unchanged (priority kept)
    raised = ~is_c & np.isfinite(thr) & ~a0
    assert n_raised == int(raised.sum()) > 0
    above = lab2.just_above(thr[raised])
    assert (v1[raised] == above).all()
    assert (np.nextafter(above, np.float32(-np.inf)).astype(np.float64) <= thr[raised]).all()   # the smallest such value


def test_join_f6():
    ts = pd.to_datetime(["2025-01-01 00:01", "2025-01-01 00:02", "2025-03-01 12:00"]).astype("datetime64[us]")
    X = pd.DataFrame({"coin": ["ETH", "SOL", "ETH"], "ts": ts}, index=[10, 11, 12])
    T = pd.DataFrame({"coin": ["SOL", "ETH", "ETH", "XRP"],
                      "ts": pd.to_datetime(["2025-01-01 00:02", "2025-03-01 12:00", "2025-01-01 00:01",
                                            "2025-01-01 00:05"]).astype("datetime64[ns]")})
    for i, f in enumerate(lab2.F6):
        T[f] = np.array([1.0, 2.0, np.nan, 4.0]) + 10 * i
    T.attrs["path"] = "synthetic"
    out, extra = lab2.join_f6(X, T)
    assert list(out.columns) == lab2.F6 and (out.index == X.index).all()
    assert out.dtypes.eq(np.float32).all() and extra == 1
    assert np.isnan(out.loc[10, "csv_30"]) and out.loc[11, "csv_30"] == 1.0 and out.loc[12, "csv_5"] == 12.0
    try:
        lab2.join_f6(pd.concat([X, pd.DataFrame({"coin": ["ETH"], "ts": [pd.Timestamp("2025-06-01")]}, index=[13])]), T)
        raise AssertionError("expected a missing-row error")
    except ValueError as e:
        assert "1 of 4" in str(e)


def test_replay_thresholds():
    """thr.csv is read by rt_live with pd.read_csv, whose default parser is one ulp off for some values: the rule
    must use the thresholds as parsed, and still give the trade list's decision at candidate minutes."""
    import io
    thr_q = {"2025Q1": 28.545640303477633, "2025Q2": 30.022654494664074}
    back = lab2.replay_thresholds(thr_q)
    path = pd.read_csv(io.StringIO(pd.DataFrame({"thr": list(thr_q.values()), "quarter": list(thr_q)})
                                   .to_csv(index=False)))          # what rt_live.inputs does with the file
    assert back == dict(zip(path.quarter, path.thr))
    model_t = thr_q["2025Q1"]
    assert back["2025Q1"] != model_t                                # this value does not survive the parser
    n = 4
    thr_model = np.full(n, model_t)
    thr_replay = np.full(n, back["2025Q1"])
    pred = np.array([model_t + 2e-15, model_t, model_t + 5.0, model_t - 5.0])   # a hair above the model threshold
    want = pred > thr_model                                          # the trade list: [True, False, True, False]
    v, info = lab2.mixed_panel(np.zeros(n, np.float32), thr_replay, thr_replay, np.arange(n), pred, cand_want=want)
    assert (approve(v, thr_replay) == want).all()
    chk = lab2.check_panel(v, thr_replay, np.arange(n), pred, cand_want=want)
    assert chk["cand_armed_mismatch"] == 0


def test_seeds_and_twins():
    assert lab2.seed_sets("t1") == [(7, 11, 23)] and lab2.seed_sets("t5") == [(12, 13, 14)]
    assert lab2.seed_sets("u15") == [(7, 11, 23, 1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 13, 14)]
    assert len(lab2.seed_sets("triples")) == 5 and lab2.seed_sets("42,101") == [(42, 101)]
    assert lab2.seed_name((1, 2, 3)) == "t2" and lab2.seed_name(lab2.U15) == "u15" and lab2.seed_name((42,)) == "42"
    assert lab2.twin_of("RF6") == "RF0" and lab2.twin_of("RF6H") == "RF0H" and lab2.twin_of("RF2H") is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
