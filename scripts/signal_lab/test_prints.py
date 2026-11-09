#!/usr/bin/env python3
"""Signal lab 2: synthetic tests of the F6 print features (scripts/signal_lab/prints_features.py). They run before
every feature run on the runner and stop it if any fails; QA.md records their output.

1. Timing: no print stamped at or after q reaches any quantity of candidate q. Huge prints added at q, q + 1 us and
   later leave every column unchanged; the same print 1 us before q moves the sums by exactly its USD (control).
2. Big-print threshold: only prints stamped before the window start w = q - 30 min. Changing every print at or after w
   (inside the window too) leaves the threshold unchanged; it equals a brute-force numpy.quantile(0.99) over
   [w - 30 days, w) when that holds >= 2,000 prints, the latest 2,000 before w when not, and NaN below 2,000 in all.
3. Sweep = the largest calendar-second taker-sell USD in [q - 30 min, q), against a pandas groupby.
4. De-duplication by trade_id; maker side BUY = taker sell; the NaN rules of finalize().
5. Margin (follow-up of Nov 9): with the windows ending at q - margin (5 s, 60 s), a print at q - margin or later
   leaves every column unchanged, one 1 us before q - margin is counted, the sums equal a brute force over
   [q - 30 min, q - margin) and [q - 5 min, q - margin), and the threshold is the margin-0 one.
usage: python scripts/signal_lab/test_prints.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prints_features as PF  # noqa: E402

NS = 10 ** 9
MIN = 60 * NS


def tape(seed=0, days=75, start="2024-03-01"):
    """Clustered synthetic prints: bursts around random centres, us-stamped, some shared stamps."""
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp(start).value
    centres = np.sort(rng.integers(t0, t0 + days * 86400 * NS, 120))
    ts = []
    for c in centres:
        k = int(rng.integers(50, 900))
        ts.append(c + np.sort(rng.integers(-40 * MIN, 5 * MIN, k)))
    t = np.concatenate(ts) // 1000 * 1000
    t.sort()
    dup = rng.random(len(t)) < 0.15
    t[1:][dup[1:]] = t[:-1][dup[1:]]                        # shared stamps
    t = np.maximum.accumulate(t)
    n = len(t)
    price = 50 + np.cumsum(rng.normal(0, 0.01, n))
    size = rng.lognormal(0, 1.5, n)
    sell = rng.random(n) < 0.5
    trade_id = np.arange(n, dtype=np.int64) + 10 ** 6
    return dict(trade_id=trade_id, t=t, price=price, size=size, sell=sell)


def feats(P, q):
    d, _ = PF.prep(P["trade_id"], P["t"], P["price"], P["size"], P["sell"])
    n, s, e, ab = PF.coin_features(d["t"], d["usd"], d["sell"], q)
    return n, s, d


def add(P, t_new, price, size, sell):
    m = len(P["t"])
    k = len(t_new)
    Q = {kk: np.concatenate([v, x]) for (kk, v), x in zip(P.items(), (
        np.arange(k, dtype=np.int64) + P["trade_id"].max() + 1 + m, np.asarray(t_new, np.int64),
        np.full(k, price), np.full(k, size), np.full(k, sell)))}
    o = np.argsort(Q["t"], kind="stable")
    return {kk: v[o] for kk, v in Q.items()}


def same(x, y):
    return np.array_equal(np.asarray(x), np.asarray(y), equal_nan=True)


def check_timing(P, q0):
    q = np.array([q0], dtype=np.int64)
    n0, s0, _ = feats(P, q)
    later = [q0, q0 + 1000, q0 + 1000 + NS, q0 + 7 * MIN]
    for tn in later:
        n1, s1, _ = feats(add(P, [tn], 1e6, 1e3, True), q)
        assert same(n0, n1), "n_prints moved by a print at or after q"
        for k in PF.SUMS:
            assert same(s0[k], s1[k]), f"{k} moved by a print at or after q"
    # control: 1 us before q is inside [q - 30 min, q) and [q - 5 min, q)
    usd = 1e6 * 1e3
    n2, s2, _ = feats(add(P, [q0 - 1000], 1e6, 1e3, True), q)
    assert (n2 == n0 + 1).all()
    assert np.allclose(s2["sell_usd_30"] - s0["sell_usd_30"], usd)
    assert np.allclose(s2["sell_usd_5"] - s0["sell_usd_5"], usd)
    assert (s2["sweep_max_usd_30"] >= usd).all() and (s0["sweep_max_usd_30"] < usd).all()
    # a print at exactly q - 30 min is inside the 30-minute window, at q - 30 min - 1 us it is not
    n3, s3, _ = feats(add(P, [q0 - 30 * MIN], 2.0, 3.0, False), q)
    n4, s4, _ = feats(add(P, [q0 - 30 * MIN - 1000], 2.0, 3.0, False), q)
    assert (n3 == n0 + 1).all() and np.allclose(s3["usd_30"] - s0["usd_30"], 6.0)
    assert (n4 == n0).all() and same(s4["usd_30"], s0["usd_30"])
    return True


def feats_m(P, q, margin):
    d, _ = PF.prep(P["trade_id"], P["t"], P["price"], P["size"], P["sell"])
    n, s, e, _ = PF.coin_features(d["t"], d["usd"], d["sell"], q, margin_s=margin)
    return n, s, e, d


def check_margin(P, q0, margin):
    """Windows end at q - margin: a print at q - margin (and anything later) is out, one 1 us earlier is in; the
    threshold does not move; reusing the margin-0 thresholds gives the same result as recomputing them."""
    q = np.array([q0], dtype=np.int64)
    end = q0 - margin * NS
    n0, s0, e0, d0 = feats_m(P, q, margin)
    for tn in (end, end + 1000, q0 - 1000, q0, q0 + 5 * MIN):
        n1, s1, _, _ = feats_m(add(P, [tn], 1e6, 1e3, True), q, margin)
        assert same(n0, n1), f"margin {margin}: n_prints moved by a print at {tn - q0} ns from q"
        for k in PF.SUMS:
            assert same(s0[k], s1[k]), f"margin {margin}: {k} moved by a print at {tn - q0} ns from q"
    usd = 1e6 * 1e3
    n2, s2, _, _ = feats_m(add(P, [end - 1000], 1e6, 1e3, True), q, margin)
    assert (n2 == n0 + 1).all()
    assert np.allclose(s2["sell_usd_30"] - s0["sell_usd_30"], usd)
    assert np.allclose(s2["sell_usd_5"] - s0["sell_usd_5"], usd)
    assert (s2["sweep_max_usd_30"] >= usd).all()
    # brute force against the definition
    t, u, sl = d0["t"], d0["usd"], d0["sell"]
    m30 = (t >= q0 - 30 * MIN) & (t < end)
    m5 = (t >= q0 - 5 * MIN) & (t < end)
    assert n0[0] == m30.sum() and np.isclose(s0["usd_30"][0], u[m30].sum())
    assert np.isclose(s0["sell_usd_30"][0], u[m30 & sl].sum()) and np.isclose(s0["sell_usd_5"][0], u[m5 & sl].sum())
    # threshold: identical to margin 0, and reusing it gives identical sums
    _, z, ez, _ = feats_m(P, q, 0)
    assert same(s0["big_thr_usd"], z["big_thr_usd"])
    _, s3, _, _ = PF.coin_features(d0["t"], d0["usd"], d0["sell"], q, margin_s=margin,
                                   thr=(z["big_thr_usd"], ez["thr_rule"]))
    for k in PF.SUMS:
        assert same(s0[k], s3[k]), f"margin {margin}: {k} differs with reused thresholds"
    return True


def brute_thr(t, usd, q):
    w = q - 30 * MIN
    pool = usd[(t >= w - 30 * 86400 * NS) & (t < w)]
    if len(pool) >= 2000:
        return float(np.quantile(pool, 0.99)), 1
    before = usd[t < w]
    if len(before) >= 2000:
        return float(np.quantile(before[-2000:], 0.99)), 2
    return np.nan, 0


def check_threshold(P, qs):
    _, s0, d = feats(P, qs)
    rules = set()
    for i, q in enumerate(qs):
        thr, rule = brute_thr(d["t"], d["usd"], q)
        rules.add(rule)
        assert same(s0["big_thr_usd"][i], thr), (i, s0["big_thr_usd"][i], thr)
        # every print at or after w = q - 30 min scaled by 1000: the threshold must not move
        w = q - 30 * MIN
        Q = {k: v.copy() for k, v in P.items()}
        Q["size"][Q["t"] >= w] *= 1000.0
        _, s1, _ = feats(Q, np.array([q]))
        assert same(s1["big_thr_usd"][0], s0["big_thr_usd"][i]), "threshold moved by a print at or after w"
        # big taker-sell USD in the window against brute force
        if rule:
            m = (d["t"] >= w) & (d["t"] < q) & d["sell"] & (d["usd"] >= thr)
            assert np.isclose(s0["big_sell_usd_30"][i], d["usd"][m].sum())
        else:
            assert np.isnan(s0["big_sell_usd_30"][i])
    return rules


def check_sweep(P, qs):
    _, s0, d = feats(P, qs)
    df = pd.DataFrame({"t": d["t"], "usd": np.where(d["sell"], d["usd"], 0.0)})
    for i, q in enumerate(qs):
        x = df[(df.t >= q - 30 * MIN) & (df.t < q)]
        want = x.groupby(x.t // NS).usd.sum().max() if len(x) else 0.0
        assert np.isclose(s0["sweep_max_usd_30"][i], want), (i, s0["sweep_max_usd_30"][i], want)


def check_dedup_side():
    t = np.array([0, 1, 1, 2], dtype=np.int64) * NS + pd.Timestamp("2024-01-01").value
    d, chk = PF.prep(np.array([5, 6, 6, 7]), t, np.array([10.0, 20.0, 20.0, 30.0]), np.ones(4),
                     np.array([True, False, False, True]))
    assert chk["n_dup"] == 1 and len(d["t"]) == 3
    q = np.array([pd.Timestamp("2024-01-01 00:01").value])
    n, s, e, _ = PF.coin_features(d["t"], d["usd"], d["sell"], q)
    assert n[0] == 3 and s["usd_30"][0] == 60.0 and s["sell_usd_30"][0] == 40.0     # sells: maker BUY rows


def check_finalize():
    sums = {k: np.array([10.0, 0.0, 0.0, 10.0]) for k in PF.SUMS}
    sums["sell_usd_30"] = np.array([4.0, 0.0, 0.0, 0.0])
    sums["usd_30"] = np.array([10.0, 0.0, 0.0, 10.0])
    f = PF.finalize(np.array([True, True, False, True]), np.array([5, 0, 3, 2]), sums,
                    np.array([100.0, 100.0, 100.0, np.nan]))
    assert np.isclose(f["csv_30"][0], 0.04) and np.isclose(f["sell_share_30"][0], 0.4)
    assert all(np.isnan(f[k][1]) for k in PF.F6)                       # no prints: F6 missing
    assert f["usd_30"][1] == 0.0                                        # ... sums stay 0
    assert all(np.isnan(f[k][2]) for k in PF.FLOATS)                    # not complete: every float missing
    assert np.isnan(f["csv_30"][3]) and f["sell_share_30"][3] == 0.0    # ADV missing; no taker sells
    assert np.isnan(f["big_sell_share_30"][3])                          # 0 / 0


def run():
    out, all_rules, n_margin = [], set(), 0
    for seed in (0, 1, 2, 3):
        P = tape(seed)
        if seed == 3:                                   # a 40-day gap: the 30-day pool runs dry after it (rule 2)
            mid = P["t"][len(P["t"]) // 2]
            P["t"] = np.where(P["t"] > mid, P["t"] + 40 * 86400 * NS, P["t"])
        d, _ = PF.prep(P["trade_id"], P["t"], P["price"], P["size"], P["sell"])
        rng = np.random.default_rng(100 + seed)
        # candidate minutes: inside bursts (whole minutes), the first burst (threshold missing) and after the gap
        picks = np.sort(rng.choice(len(d["t"]), 60, replace=False))
        qs = (d["t"][picks] // MIN + 1) * MIN
        extra = [(d["t"][0] // MIN + 2) * MIN, (d["t"][2500] // MIN + 1) * MIN]
        if seed == 3:
            j = int(np.searchsorted(d["t"], mid + 40 * 86400 * NS, "right"))
            extra += [(d["t"][j + k] // MIN + 1) * MIN for k in (0, 300, 1500)]
        qs = np.unique(np.concatenate([qs, extra]))
        for q in qs[::6]:
            check_timing(P, int(q))
        for q in qs[3::12]:
            for margin in (5, 60):
                check_margin(P, int(q), margin)
                n_margin += 1
        rules = check_threshold(P, qs)
        all_rules |= rules
        check_sweep(P, qs)
        out.append(f"seed {seed}: {len(d['t'])} prints, {len(qs)} candidate minutes, threshold rules hit {sorted(rules)}")
    assert all_rules == {0, 1, 2}, all_rules
    check_dedup_side()
    check_finalize()
    msg = ("test_prints: all checks passed (" + "; ".join(out) + f"; {n_margin} margin checks at 5 s and 60 s)")
    print(msg, flush=True)
    return msg


if __name__ == "__main__":
    run()
