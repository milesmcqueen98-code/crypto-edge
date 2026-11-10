#!/usr/bin/env python3
"""Offline test of study.py on made-up trades and candles cut at known offsets: zero, a steady +3.2 s, and a varying
one. Checks that every explained boundary's interval holds the true cut, that a corrupted candle is unexplained and the
chain re-anchors after it, and that the class logic gives A, B and C. No network.

Usage: python scripts/owner/candle_clock/test_study.py
"""
import os
import random
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import study as S  # noqa: E402

US, MIN = S.US, S.MIN
W0 = 1_793_000_000 // 60 * 60 * US           # a whole minute
NMIN = 120
W1 = W0 + NMIN * MIN


def make_trades(seed, rate=3.0, step="0.03", hole=None):
    """Trades from W0 - 3 min to W1 + 4 min, Poisson in time, random-walk price, ids in time order. hole = (a, b) µs
    with no trades."""
    rnd = random.Random(seed)
    t = W0 - 3 * MIN
    px = Decimal("100.00")
    st = Decimal(step)
    out, tid = [], 1000
    while t < W1 + 4 * MIN:
        t += max(1, int(rnd.expovariate(rate) * US))
        if hole and hole[0] <= t < hole[1]:
            continue
        px += st * rnd.choice((-1, 1))
        size = Decimal(rnd.randint(1, 5000)) / 1000
        out.append((t, tid, f"{px:.2f}", f"{size:.3f}"))
        tid += 1
    return out


def make_candles(trades, cut):
    """Candle of minute m holds the trades (id order) stamped in [m + cut(m), m + 60 s + cut(m + 1 min)) (cut in s)."""
    c = {}
    for m in range(W0 - 2 * MIN, W1 + 2 * MIN, MIN):
        a, b = m + int(round(cut(m) * US)), m + MIN + int(round(cut(m + MIN) * US))
        sel = [x for x in trades if a <= x[0] < b]
        if not sel:
            continue
        p = [Decimal(x[2]) for x in sel]
        c[m] = (p[0], max(p), min(p), p[-1], sum(Decimal(x[3]) for x in sel))
    return c


def check_truth(br, cut):
    bad, n = 0, 0
    for r in br:
        if not r["explained"]:
            continue
        n += 1
        m = S.stamp_us(r["minute"])
        x = cut(m + MIN)
        if not (r["lo"] < x <= r["hi"]):
            bad += 1
    return n, bad


def run(name, cut, hole=None, corrupt=None, seed=1):
    tr = make_trades(seed, hole=hole)
    cd = make_candles(tr, cut)
    if corrupt is not None:
        o, h, lo, c, v = cd[corrupt]
        cd[corrupt] = (o, h, lo, c, v + Decimal("0.001"))
    known = set(range(W0 - 2 * MIN, W1 + 2 * MIN, MIN))
    row, br, un = S.analyze_coin(name, tr, cd, known, W0, W1)
    n, bad = check_truth(br, cut)
    print(f"{name}: class {row['cls']}; explained {row['explained']}/{row['boundaries']}; truth outside interval {bad}; "
          f"zero share {row['zero_share']:.3f}; fit {row['fit_offset']:.3f}; best ({row['best_a']:.3f}, "
          f"{row['best_b']:.3f}]; oos material zero/fit/prev {row['oos0_material']:.3f}/{row['oosfit_material']:.3f}/"
          f"{row['oosprev_material']:.3f}; unexplained {un}")
    assert bad == 0, f"{name}: {bad} intervals miss the true cut"
    return row, br, un


def main():
    fails = 0
    row, br, un = run("ZERO", lambda m: 0.0)
    assert row["explained"] == row["boundaries"] == NMIN and row["cls"] == "A", row
    assert row["m1_eq5"] == 1.0 and row["zero_share"] == 1.0

    hole = (W0 + 50 * MIN + int(3.2 * US), W0 + 51 * MIN + int(3.2 * US))      # one minute with no candle
    row, br, un = run("STEADY", lambda m: 3.2, hole=hole, seed=2)
    assert row["explained"] == row["boundaries"] == NMIN and row["cls"] == "B", row
    assert row["fit_first_a"] < 3.2 <= row["fit_first_b"], row
    assert row["zero_share"] < 0.995 and row["oosfit_material"] <= 0.01
    assert not [r for r in br if r["minute"] == S.iso(W0 + 50 * MIN)][0]["candle"]

    rv = random.Random(7)
    xs = {}

    def vary(m):
        return xs.setdefault(m, rv.uniform(0.0, 20.0))
    row, br, un = run("VARYING", vary, seed=3)
    assert row["explained"] == row["boundaries"] and row["cls"] == "C", row
    assert row["oosprev_material"] > 0.01

    bad_m = W0 + 30 * MIN
    row, br, un = run("CORRUPT", lambda m: 0.0, corrupt=bad_m, seed=4)
    unexpl = sorted(r["minute"] for r in br if not r["explained"])
    assert unexpl == [S.iso(bad_m - MIN), S.iso(bad_m)], unexpl
    assert row["reanchors"] == 2, row["reanchors"]                     # the first anchor and the re-anchor
    after = [r for r in br if S.stamp_us(r["minute"]) > bad_m]
    assert all(r["explained"] for r in after)

    # best_offset: ties and the sweep
    bo = S.best_offset([(-1.0, 2.0), (0.5, 3.0), (1.0, 4.0)])
    assert bo["k"] == 3 and bo["a"] == 1.0 and bo["b"] == 2.0 and bo["mid"] == 1.5, bo
    print("all checks passed" if not fails else f"{fails} failures")


if __name__ == "__main__":
    main()
