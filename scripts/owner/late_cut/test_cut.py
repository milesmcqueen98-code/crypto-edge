#!/usr/bin/env python3
"""Offline tests of the late-cut pieces (made-up prints and candles; no data files, no lab imports beyond edge.wick).
Run here and on every print runner before its fetch (a failure stops the job).

  python scripts/owner/late_cut/test_cut.py

1. Bars: cut.bars on made-up prints (shared stamps, duplicates, unsorted input through cut.order) equals a brute-force
   loop over the prints written from the definition (stamp in [T - 60 s, T + s), last in (time, trade id) order).
2. Scenario bars: cut.pick_bar (M and Q forms, the five-print rule).
3. The carried close: cut.carry_close equals the bot's fill (forward fill, limit 30) of a row with no candle.
4. Changed values: cut.Coin.values on a made-up market (BTC and three coins, 16,000 minutes, some minutes without a
   candle) equals edge.wick.panel run on the arrays with that one row replaced (the bot's fill: no volume = no row),
   at 60 candidate minutes, for a random new close and volume, for no print (carried close), and for the candle's own
   row; and every value panel computes that the row should not move is unmoved.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import cut  # noqa: E402

NS = cut.NS


def brute_bar(prints, T, s):
    """prints: list of (trade_id, t_ns, px, sz), any order, duplicates allowed."""
    seen, keep = set(), []
    for p in prints:
        if p[0] not in seen:
            seen.add(p[0])
            keep.append(p)
    inside = [p for p in keep if T - 60 * NS <= p[1] < T + s * NS]
    if not inside:
        return 0, np.nan, 0.0
    last = max(inside, key=lambda p: (p[1], p[0]))
    return len(inside), last[2], float(np.sum([p[3] for p in sorted(inside, key=lambda p: (p[1], p[0]))]))


def test_bars():
    rng = np.random.default_rng(1)
    T = pd.Timestamp("2025-03-01 12:00:00").value
    checked = 0
    for _ in range(400):
        n = int(rng.integers(0, 60))
        ids = rng.permutation(np.arange(1000, 1000 + n))
        sec = rng.choice([-61.0, -60.0, -59.5, -1e-6, 0.0, 0.0, 3.0, 4.999999, 5.0, 9.0, 10.0, 14.9, 15.0], n) \
            if rng.random() < 0.5 else rng.uniform(-60, 15, n)
        tn = (T + np.round(sec * 1e6).astype(np.int64) * 1000)
        tn = np.where(rng.random(n) < 0.3, T - 30 * NS, tn)                 # shared stamps
        px = np.round(100 + rng.normal(0, 1, n), 2)
        sz = np.round(rng.uniform(0.001, 5, n), 6)
        prints = list(zip(ids.tolist(), tn.tolist(), px.tolist(), sz.tolist()))
        if n:
            prints += prints[: int(rng.integers(0, n + 1))]                   # duplicates
        D = pd.DataFrame(prints, columns=["trade_id", "t", "price", "size"])
        D["time"] = pd.to_datetime(D.t)
        D = D[(D.time >= pd.Timestamp(T - 60 * NS)) & (D.time < pd.Timestamp(T + 15 * NS))]   # the fetch window
        D = D.sample(frac=1.0, random_state=int(rng.integers(1e9)))
        t_ns, p_, s_ = cut.order(D)
        b = cut.bars(t_ns, p_, s_, T)
        for s in cut.SECONDS:
            n_, c_, v_ = brute_bar(prints, T, s)
            assert b[f"n_{s}"] == n_, (s, b[f"n_{s}"], n_)
            assert (np.isnan(c_) and np.isnan(b[f"close_{s}"])) or b[f"close_{s}"] == c_
            assert abs(b[f"vol_{s}"] - v_) <= 1e-12 * max(1.0, v_)
            checked += 1
    print(f"bars: {checked} (candidate, second) cases equal the brute-force cut")


def test_pick():
    n0 = np.array([0, 1, 5, 6, 40])
    assert (cut.pick_bar(n0, 0, False) == 0).all()
    assert (cut.pick_bar(n0, 5, False) == 5).all()
    assert cut.pick_bar(n0, 5, True).tolist() == [5, 5, 5, 0, 0]
    assert cut.pick_bar(n0, 10, True).tolist() == [10, 10, 10, 0, 0]
    assert cut.SCEN == {"M0": (0, False), "M5": (5, False), "M10": (10, False), "Q5": (5, True), "Q10": (10, True)}
    print("scenario bars: M and Q forms as the plan defines them")


def test_carry():
    rng = np.random.default_rng(2)
    n = 400
    raw = 100 + np.cumsum(rng.normal(0, 0.1, n))
    vol = rng.uniform(1, 2, n)
    gaps = [(50, 60), (100, 129), (200, 230), (300, 345)]
    for a, b in gaps:
        raw[a:b], vol[a:b] = np.nan, 0.0
    cf = pd.Series(raw).ffill(limit=30).to_numpy()
    u = np.arange(5, n)
    got = cut.carry_close(cf, vol, u)
    for i, uu in enumerate(u):
        r2 = raw.copy()
        r2[uu] = np.nan
        want = pd.Series(r2[: uu + 1]).ffill(limit=30).to_numpy()[uu]
        assert (np.isnan(want) and np.isnan(got[i])) or want == got[i], (uu, want, got[i])
    print(f"carried close: {len(u)} minutes equal the bot's fill (limit 30)")


def market(n, seed):
    rng = np.random.default_rng(seed)
    coins = ["AAA", "BBB", "CCC"]
    rb = rng.normal(0, 8e-4, n)
    lpb = np.log(30000) + np.cumsum(rb)
    raw, vol = {"BTC": np.exp(lpb)}, {"BTC": rng.uniform(5, 50, n)}
    for i, c in enumerate(coins):
        beta = 0.8 + 0.4 * i
        lp = np.log(10 + i) + np.cumsum(beta * rb + rng.normal(0, 1e-3, n))
        r, v = np.exp(lp), rng.uniform(1, 20, n) * (rng.random(n) < 0.8 + 0.1 * i)    # empty minutes
        r = np.where(v > 0, r, np.nan)
        raw[c], vol[c] = r, v
    return coins, raw, vol


def fill(raw):
    return pd.Series(raw).ffill(limit=30).to_numpy()


def test_values():
    from edge import wick
    n, wbeta = 16000, 10080
    coins, raw, vol = market(n, 4)
    idx = pd.date_range("2024-01-01", periods=n, freq="min")
    cf = {c: fill(raw[c]) for c in raw}
    base = wick.panel(cf, vol, coins, idx, k=4.0, lookback=60, keep_rows={c: np.arange(12000, n) for c in coins},
                      wbeta=wbeta)
    rng = np.random.default_rng(5)
    worst, nval = 0.0, 0
    for c in coins:
        t = np.sort(rng.choice(np.arange(12000, n), 60, replace=False))
        u = t - 1
        C = cut.Coin(cf[c], vol[c], cf["BTC"], t, k=4.0, lookback=60, wbeta=wbeta)
        carry = cut.carry_close(cf[c], vol[c], u)
        cases = {"random": (cf[c][u] * np.exp(rng.normal(0, 3e-3, len(t))), np.maximum(vol[c][u], 1.0) * rng.uniform(0.2, 3, len(t))),
                 "no print": (carry, np.zeros(len(t))),
                 "candle": (cf[c][u], vol[c][u])}
        for label, (cn, vn) in cases.items():
            vals = C.values(cn, vn)
            for i, tt in enumerate(t):
                r2, v2 = raw[c].copy(), vol[c].copy()
                r2[tt - 1] = cn[i] if vn[i] > 0 else np.nan
                v2[tt - 1] = vn[i]
                cf2, vol2 = dict(cf), dict(vol)
                cf2[c], vol2[c] = fill(r2), v2
                pn = wick.panel(cf2, vol2, coins, idx, k=4.0, lookback=60, keep_rows={c: [tt]}, wbeta=wbeta)[c].iloc[0]
                for name in ["level", "sig"] + cut.CHANGED:
                    mine = vals[name][i]
                    mine = float(np.float32(mine)) if name in cut.CHANGED else float(mine)
                    want = float(pn[name])
                    if np.isnan(mine) and np.isnan(want):
                        continue
                    assert np.isfinite(mine) == np.isfinite(want), (label, c, tt, name, mine, want)
                    d = abs(mine - want) / max(abs(want), 1e-12)
                    assert d < 2e-6 or abs(mine - want) < 1e-9, (label, c, tt, name, mine, want)
                    worst = max(worst, d)
                    nval += 1
                ref = base[c].loc[idx[tt]]
                for name in wick.FEATS:
                    if name not in cut.CHANGED:
                        a, b = float(pn[name]), float(ref[name])
                        assert (np.isnan(a) and np.isnan(b)) or a == b, (label, c, tt, name, a, b)
                if label == "candle":
                    for name in ["level", "sig"] + cut.CHANGED:
                        a, b = float(pn[name]), float(ref[name])
                        assert (np.isnan(a) and np.isnan(b)) or a == b
    print(f"changed values: {nval} values equal edge.wick.panel with the row replaced (largest relative "
          f"difference {worst:.1e}); unchanged features unmoved")


def main():
    test_bars()
    test_pick()
    test_carry()
    test_values()
    print("all late-cut tests passed")


if __name__ == "__main__":
    main()
