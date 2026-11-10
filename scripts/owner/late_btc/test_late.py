#!/usr/bin/env python3
"""Offline test of the late-BTC transform (made-up closes; no data files, no lab imports beyond edge.wick).

  python scripts/owner/late_btc/test_late.py

1. The transform: for lags 1 and 2 and every decision minute of a short made-up series, late.late_array (the bot's
   fill: drop the newest minutes, fill forward with limit 30, volume 0) equals a brute-force fill written here from
   its definition, and equals late.late_array_fast.
2. S4's base: base_s4 equals a brute-force minute-by-minute fill of the dropped minutes.
3. The vectorised values: late.late_rows on a made-up market (BTC and three coins, 16,000 minutes) equals
   edge.wick.panel run on the brute-force late arrays, at 40 decision minutes, for lags 0 (true_rows), 1 and 2, and
   for an S4-style base.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import late  # noqa: E402
from edge import wick  # noqa: E402


def brute_fill(close, vol, t, m):
    c, v = list(close), list(vol)
    for s in range(t - m, t):
        v[s] = 0.0
        c[s] = c[t - 1 - m]                  # the last close the bot still has (no gap longer than 30 here)
    return np.array(c), np.array(v)


def test_transform():
    rng = np.random.default_rng(1)
    n = 300
    close = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, n)))
    vol = rng.uniform(1, 5, n)
    worst = 0
    for m in (1, 2):
        for t in range(5, n):
            a, va = late.late_array(close, vol, t, m)
            b, vb = brute_fill(close, vol, t, m)
            f, vf = late.late_array_fast(close, vol, t, m)
            assert np.array_equal(a[:t], b[:t]) and np.array_equal(va[:t], vb[:t]), (m, t)
            assert np.array_equal(f[:t], b[:t]) and np.array_equal(vf[:t], vb[:t]), (m, t)
            assert np.array_equal(a[:t - m], close[:t - m])           # older minutes untouched
            assert (a[t - m:t] == close[t - 1 - m]).all() and (va[t - m:t] == 0).all()
            worst += 1
    a0, _ = late.late_array(close, vol, 50, 0)
    assert np.array_equal(a0, close)
    print(f"transform: {worst} (minute, lag) cases equal the brute-force fill")


def test_s4():
    rng = np.random.default_rng(2)
    n = 500
    raw = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, n)))
    raw[[10, 11, 200]] = np.nan                      # minutes without a candle
    vol = rng.uniform(1, 5, n)
    vol[[10, 11, 200]] = 0.0
    mask = late.draw_mask(n, 3)
    b, vb = late.base_s4(raw, vol, mask)
    want, wv = [], []
    last, gap = np.nan, 0
    for s in range(n):
        have = (not mask[s]) and np.isfinite(raw[s])
        if have:
            last, gap = raw[s], 0
            want.append(raw[s])
        else:
            gap += 1
            want.append(last if gap <= 30 else np.nan)
        wv.append(0.0 if mask[s] else vol[s])
    assert np.allclose(b, want, equal_nan=True, rtol=0, atol=0) and np.array_equal(vb, wv)
    print(f"S4 base: {int(mask.sum())} of {n} minutes dropped; equals the brute-force fill")


def market(n, seed):
    rng = np.random.default_rng(seed)
    coins = ["AAA", "BBB", "CCC"]
    rb = rng.normal(0, 8e-4, n)
    lpb = np.log(30000) + np.cumsum(rb)
    cf, vol = {"BTC": np.exp(lpb)}, {"BTC": rng.uniform(5, 50, n)}
    for i, c in enumerate(coins):
        beta = 0.8 + 0.4 * i
        lp = np.log(10 + i) + np.cumsum(beta * rb + rng.normal(0, 1e-3, n))
        cf[c], vol[c] = np.exp(lp), rng.uniform(1, 20, n)
    return coins, cf, vol


def panel_row(cf, vol, coins, idx, t, wbeta):
    pn = wick.panel(cf, vol, coins, idx, k=4.0, lookback=60, keep_rows={c: [t] for c in coins}, wbeta=wbeta)
    return {c: pn[c].iloc[0] for c in coins}


def compare(B, coins, cf_btc, v_btc, cf, vol, idx, rows, m, wbeta, label):
    if m == 0:
        out, per = late.true_rows(B, rows)
    else:
        out, per = late.late_rows(B, rows, m)
    worst_rel, worst_abs = 0.0, 0.0
    for i, t in enumerate(rows):
        a, va = late.late_array(cf_btc, v_btc, t, m)
        cf2, vol2 = dict(cf), dict(vol)
        cf2["BTC"], vol2["BTC"] = a, va
        ref = panel_row(cf2, vol2, coins, idx, t, wbeta)
        for c in coins:
            for name in ["level", "sig"] + late.BTC_FEATS:
                mine = out[name][i] if name in out else per[c][name][i]
                want = float(ref[c][name])
                if not (np.isfinite(mine) or np.isfinite(want)):
                    continue
                mine_c = float(np.float32(mine)) if name in late.BTC_FEATS else float(mine)
                d = abs(mine_c - want)
                worst_abs = max(worst_abs, d)
                worst_rel = max(worst_rel, d / max(abs(want), 1e-12))
    # float32 features: 1 ulp is about 6e-8 relative
    assert worst_rel < 2e-6, (label, worst_rel)
    print(f"{label}: {len(rows)} minutes x {len(coins)} coins, largest relative difference {worst_rel:.1e} "
          f"(absolute {worst_abs:.1e})")


def test_vectorised():
    n = 16000
    coins, cf, vol = market(n, 4)
    idx = pd.date_range("2024-01-01", periods=n, freq="min")
    rows = np.sort(np.random.default_rng(5).choice(np.arange(12000, n), 40, replace=False))
    wbeta = 10080
    lp = {c: np.log(cf[c]) for c in coins}
    B = late.Base(cf["BTC"], vol["BTC"], lp, coins, wbeta=wbeta)
    for m in (0, 1, 2):
        compare(B, coins, cf["BTC"], vol["BTC"], cf, vol, idx, rows, m, wbeta, f"lag {m}")
    mask = late.draw_mask(n, 6)
    b4, v4 = late.base_s4(cf["BTC"], vol["BTC"], mask)
    B4 = late.Base(b4, v4, lp, coins, wbeta=wbeta)
    for m in (1, 2):
        compare(B4, coins, b4, v4, cf, vol, idx, rows, m, wbeta, f"S4 base, lag {m}")


if __name__ == "__main__":
    test_transform()
    test_s4()
    test_vectorised()
    print("all late-BTC tests passed")
