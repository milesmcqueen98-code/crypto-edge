#!/usr/bin/env python3
"""Signal lab 2 follow-up (coordinator, Nov 9): where the repo's minute candles put each minute boundary relative to
the print timestamps. The model decides fills from the candles and F6 uses prints stamped before q, so a candle q that
held trades the prints stamp before q would let "prints before q" see the start of the fill minute.

For every pair of adjacent minutes (m, m+1) inside a merged window where print base volume and candle volume disagree
(relative difference > 1e-5) in at least one of the two, find whether one boundary move reconciles both minutes:
  A: the prints stamped in [m+1-d, m+1) belong to candle m+1 (candle time lags print time; the direction that could
     leak into features at the boundary q);
  B: the prints stamped in [m+1, m+1+d) belong to candle m (the harmless direction).
Prints move by whole timestamps. d is the smallest shift in seconds that reconciles both minutes within 1e-5
(relative, on each minute); the same is reported at 1e-7, the float32 precision of the candle files. For A, d = m+1
minus the earliest moved print's time; for B, d = the latest moved print's offset after m+1 plus 1 us (so that
[m+1, m+1+d) holds it). A whole-minute shift moves every print of the source minute. A pair no single move reconciles
is "not reconciled by a boundary move up to 60 s".

The boundary before each candidate (m+1 = q) is classified the same way when minute q lies inside a merged window
(a later candidate of the coin within 30 minutes). Otherwise minute q's prints were never fetched (windows end at q)
and direction A is tested one-sided: candle q-1 = prints of q-1 less a suffix of them, with candle q holding at least
that volume. The USD of the moved prints is reported against the candidate's usd_30.

Reads the fetch artifacts, windows.csv, the candidate lists, f6_<era>.parquet (usd_30) and the minute candles
(prints_diag.candles). Writes <out_dir>/qa_boundary.json and qa_boundary_cand.parquet. A synthetic self-test with known
lags, leads, whole-minute shifts and lost volume runs first.
usage: python scripts/signal_lab/prints_boundary.py <art_dir> [<out_dir>]
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import prints_features as PFE  # noqa: E402

NS_S = 10 ** 9
NS_MIN = 60 * NS_S
TOL, STRICT = 1e-5, 1e-7
QS = (0.5, 0.9, 0.99, 1.0)


def _match(c_from, p_from, c_to, p_to, cs, one_sided=False):
    """Moving cs[j] (cumulative volume of the movable timestamps, in moving order) out of the source minute and into
    the target. Returns the smallest j reconciling within TOL and within STRICT (-1 if none)."""
    e = np.abs(c_from - (p_from - cs)) / max(c_from, p_from, 1e-300)
    if one_sided:
        e = np.where(cs <= c_to * (1 + TOL), e, np.inf)         # candle q must hold at least the moved volume
    else:
        got = p_to + cs
        e = np.maximum(e, np.abs(c_to - got) / np.maximum(np.maximum(c_to, got), 1e-300))
    ok, oks = np.flatnonzero(e <= TOL), np.flatnonzero(e <= STRICT)
    return (int(ok[0]) if len(ok) else -1), (int(oks[0]) if len(oks) else -1)


def coin_boundaries(t, size, usd, w_start, w_end, q, cand_min, cand_vol):
    """t (int64 ns, ascending), size, usd: one coin's prints; w_start, w_end: its merged windows (ns); q: candidate
    minute starts (ns); cand_min, cand_vol: candle minute index (ascending) and volume (rows with volume > 0).
    Returns (pair rows, candidate rows) as DataFrames."""
    ut, first = np.unique(t, return_index=True)
    vs = np.add.reduceat(size, first) if len(first) else np.zeros(0)
    vu = np.add.reduceat(usd, first) if len(first) else np.zeros(0)
    um = ut // NS_MIN
    pm, pf = np.unique(um, return_index=True)
    pl = np.r_[pf[1:], len(um)].astype(np.int64)
    pmv = np.add.reduceat(vs, pf) if len(pf) else np.zeros(0)
    mins = np.concatenate([np.arange(a // NS_MIN, b // NS_MIN) for a, b in zip(w_start, w_end)])
    k = np.searchsorted(pm, mins)
    kc = np.clip(k, 0, max(len(pm) - 1, 0))
    has = (k < len(pm)) & (pm[kc] == mins) if len(pm) else np.zeros(len(mins), bool)
    lo = np.where(has, pf[kc] if len(pf) else 0, 0)
    hi = np.where(has, pl[kc] if len(pl) else 0, 0)
    P = np.where(has, pmv[kc] if len(pmv) else 0.0, 0.0)

    def candle(mm):
        j = np.searchsorted(cand_min, mm)
        jc = np.clip(j, 0, max(len(cand_min) - 1, 0))
        hit = (j < len(cand_min)) & (cand_min[jc] == mm) if len(cand_min) else np.zeros(len(mm), bool)
        return np.where(hit, cand_vol[jc] if len(cand_vol) else 0.0, 0.0)

    C = candle(mins)
    scale = np.maximum(C, P)
    uneq = np.abs(C - P) > TOL * scale
    pair = np.flatnonzero(mins[1:] == mins[:-1] + 1)
    upair = pair[uneq[pair] | uneq[pair + 1]]
    rows, at = [], {}
    for i in upair:
        b = int(mins[i] + 1) * NS_MIN
        ml, mh, nl, nh = int(lo[i]), int(hi[i]), int(lo[i + 1]), int(hi[i + 1])
        Cm, Pm, Cn, Pn = float(C[i]), float(P[i]), float(C[i + 1]), float(P[i + 1])
        r = dict(minute=int(mins[i]), kind="none", d_s=np.nan, whole=False, strict=False, usd_moved=np.nan,
                 em=Cm - Pm, en=Cn - Pn)
        jA = jAs = jB = jBs = -1
        if mh > ml:
            jA, jAs = _match(Cm, Pm, Cn, Pn, np.cumsum(vs[ml:mh][::-1]))
        if nh > nl:
            jB, jBs = _match(Cn, Pn, Cm, Pm, np.cumsum(vs[nl:nh]))
        if jA >= 0:
            r.update(kind="A", d_s=(b - int(ut[mh - 1 - jA])) / NS_S, whole=jA == mh - ml - 1, strict=jAs >= 0,
                     usd_moved=float(np.cumsum(vu[ml:mh][::-1])[jA]), both=jB >= 0)
            if jAs > jA:
                r["d_strict_s"] = (b - int(ut[mh - 1 - jAs])) / NS_S
        elif jB >= 0:
            r.update(kind="B", d_s=(int(ut[nl + jB]) - b) / NS_S + 1e-6, whole=jB == nh - nl - 1, strict=jBs >= 0,
                     usd_moved=float(np.cumsum(vu[nl:nh])[jB]))
        at[int(i)] = len(rows)
        rows.append(r)
    # an unreconciled pair whose unequal minutes a reconciled move at the next boundary explains is a "neighbour";
    # one whose remaining unequal minute touches a window edge (a boundary the pair test cannot see) is "edge"
    expl = np.zeros(len(mins), dtype=bool)
    for i, r in zip(upair, rows):
        if r["kind"] in ("A", "B"):
            expl[i] = expl[i + 1] = True
    first = np.r_[True, mins[1:] != mins[:-1] + 1]
    last = np.r_[mins[1:] != mins[:-1] + 1, True]
    for i, r in zip(upair, rows):
        if r["kind"] != "none":
            continue
        need = [x for x in (i, i + 1) if uneq[x]]
        if all(expl[x] for x in need):
            r["kind"] = "neighbour"
        elif all(expl[x] or first[x] or last[x] for x in need):
            r["kind"] = "edge"
    # chain check: a transfer at every boundary of a window at once. With x the print volume stamped before the
    # boundary that the candles put after it (A > 0; B < 0), candle m = prints of m + x(before m) - x(after m), so
    # x(after m) = x(before m) - (candle m - prints m), starting from 0 at the window start. x must be 0, a suffix of
    # the left minute's prints (A) or a prefix of the right minute's (B); where it is none of these the boundary is
    # "unexplained" (e.g. candle volume lost) and x restarts at 0. A move is confirmed when neither neighbouring
    # boundary is unexplained.
    e_all = C - P

    def classify(x, kl, kr, tol):
        if abs(x) <= tol:
            return ("zero", np.nan, False, 0.0)
        if x > 0:
            ml, mh = int(lo[kl]), int(hi[kl])
            if mh > ml:
                cs = np.cumsum(vs[ml:mh][::-1])
                j = int(np.searchsorted(cs, x - tol))
                if j < len(cs) and abs(cs[j] - x) <= tol:
                    b = int(mins[kl] + 1) * NS_MIN
                    return ("A", (b - int(ut[mh - 1 - j])) / NS_S, j == mh - ml - 1,
                            float(np.cumsum(vu[ml:mh][::-1])[j]))
            return ("unexplained", np.nan, False, np.nan)
        if kr < 0:
            return ("B_unverified", np.nan, False, np.nan)          # the right minute was never fetched
        nl, nh = int(lo[kr]), int(hi[kr])
        if nh > nl:
            cs = np.cumsum(vs[nl:nh])
            j = int(np.searchsorted(cs, -x - tol))
            if j < len(cs) and abs(cs[j] + x) <= tol:
                b = int(mins[kr]) * NS_MIN
                return ("B", (int(ut[nl + j]) - b) / NS_S + 1e-6, j == nh - nl - 1, float(np.cumsum(vu[nl:nh])[j]))
        return ("unexplained", np.nan, False, np.nan)

    starts = np.flatnonzero(first)
    ends = np.r_[starts[1:], len(mins)]
    chain, chain_end = {}, {}
    for r_, (s0, s1) in enumerate(zip(starts, ends)):
        x, acc, res = 0.0, 0.0, []
        for k in range(s0 + 1, s1 + 1):                    # boundary before window position k (k = s1: window end)
            x -= e_all[k - 1]
            acc += C[k - 1]
            internal = k < s1
            loc = max(P[k - 1], C[k - 1], P[k] if internal else 0.0, C[k] if internal else 0.0)
            out = classify(x, k - 1, k if internal else -1, TOL * loc + 1e-7 * acc)
            if out[0] == "unexplained":
                x, acc = 0.0, 0.0
            res.append((k, out))
        kinds = [o[0] for _, o in res]
        for j_, (k, out) in enumerate(res):
            bad = (j_ > 0 and kinds[j_ - 1] == "unexplained") or (j_ + 1 < len(res) and kinds[j_ + 1] == "unexplained")
            rec = out + (out[0] in ("A", "B") and not bad,)
            if k < s1:
                chain[k] = rec
            else:
                chain_end[r_] = rec
    for i, r in zip(upair, rows):
        c_ = chain[int(i) + 1]
        r.update(chain_kind=c_[0], chain_d_s=c_[1], chain_whole=c_[2], chain_confirmed=c_[4])
    # the boundary before each candidate
    qm = np.asarray(q, dtype=np.int64) // NS_MIN
    ip = np.searchsorted(mins, qm - 1)
    assert (mins[ip] == qm - 1).all(), "minute q-1 of a candidate is outside its window"
    cq = candle(qm)
    crow = []
    for i, m_, c_q in zip(ip, qm, cq):
        i = int(i)
        two = i + 1 < len(mins) and mins[i + 1] == m_
        r = dict(two_sided=bool(two), kind="equal", d_s=np.nan, whole=False, strict=False, usd_moved=np.nan)
        if two:
            if i in at:
                pr = rows[at[i]]
                r.update(kind=pr["kind"], d_s=pr["d_s"], whole=pr["whole"], strict=pr["strict"],
                         usd_moved=pr["usd_moved"])
        elif uneq[i] and expl[i]:
            r["kind"] = "neighbour"
        elif uneq[i]:
            ml, mh = int(lo[i]), int(hi[i])
            Cm, Pm = float(C[i]), float(P[i])
            jA, jAs = (_match(Cm, Pm, float(c_q), 0.0, np.cumsum(vs[ml:mh][::-1]), one_sided=True)
                       if mh > ml else (-1, -1))
            if jA >= 0:
                r.update(kind="A", d_s=(int(m_) * NS_MIN - int(ut[mh - 1 - jA])) / NS_S, whole=jA == mh - ml - 1,
                         strict=jAs >= 0, usd_moved=float(np.cumsum(vu[ml:mh][::-1])[jA]))
            else:
                r["kind"] = "deficit_unexplained" if Cm < Pm else "surplus"
        c_ = chain[i + 1] if two else chain_end[int(np.searchsorted(starts, i, "right") - 1)]
        r.update(chain_kind=c_[0], chain_d_s=c_[1], chain_whole=c_[2], chain_usd_moved=c_[3], chain_confirmed=c_[4])
        crow.append(r)
    cols = ["minute", "kind", "d_s", "whole", "strict", "usd_moved", "em", "en", "both", "d_strict_s", "chain_kind",
            "chain_d_s", "chain_whole", "chain_confirmed"]
    CH = pd.DataFrame([dict(minute=int(mins[k] - 1), kind=v[0], d_s=v[1], whole=v[2], usd_moved=v[3], confirmed=v[4])
                       for k, v in chain.items()], columns=["minute", "kind", "d_s", "whole", "usd_moved", "confirmed"])
    return (pd.DataFrame(rows, columns=cols), pd.DataFrame(crow),
            dict(minutes=int(len(mins)), pairs=int(len(pair)), unequal_pairs=int(len(upair)),
                 unequal_minutes=int(uneq.sum())), CH)


# ------------------------------------------------------------------------------------------------ self-test
def selftest():
    """Synthetic tape; candles built from it with known boundary moves at isolated boundaries."""
    rng = np.random.default_rng(5)
    t0 = pd.Timestamp("2025-03-03").value
    w_start = np.array([t0, t0 + 3 * 3600 * NS_S])
    w_end = w_start + 40 * NS_MIN
    t = np.sort(np.concatenate([rng.integers(a, b, 40000) for a, b in zip(w_start, w_end)])) // 1000 * 1000
    t = np.concatenate([t, t[::7]])                            # shared stamps
    t.sort()
    size = rng.lognormal(0, 1, len(t))
    usd = size * 100.0
    m = t // NS_MIN
    cm = m.copy()
    b0 = w_start[0] // NS_MIN
    plan = {}
    # A, sub-minute: prints in [b - 0.35 s, b) go to the next candle, at boundary b0+5 (pair (b0+4, b0+5))
    bA = (b0 + 5) * NS_MIN
    sel = (t >= bA - 350_000_000) & (t < bA)
    cm[sel] = b0 + 5
    plan[b0 + 4] = ("A", (bA - t[sel].min()) / NS_S, False)
    # B, sub-minute: prints in [b, b + 2 s) go to the previous candle, at boundary b0+12
    bB = (b0 + 12) * NS_MIN
    sel = (t >= bB) & (t < bB + 2 * NS_S)
    cm[sel] = b0 + 11
    plan[b0 + 11] = ("B", (t[sel].max() - bB) / NS_S + 1e-6, False)
    # A, whole minute: minute b0+20 goes entirely to candle b0+21
    sel = m == b0 + 20
    cm[sel] = b0 + 21
    plan[b0 + 20] = ("A", ((b0 + 21) * NS_MIN - t[sel].min()) / NS_S, True)
    for mm in (b0 + 3, b0 + 5, b0 + 10, b0 + 12, b0 + 19, b0 + 21):
        plan[mm] = ("neighbour", np.nan, False)
    # a chain of B moves in window 2: the first 1, 2, 3 s of minutes b1+10, +11, +12 go to the previous candle
    b1 = w_start[1] // NS_MIN
    chain_plan = {}
    for mm, sec in ((b1 + 10, 1), (b1 + 11, 2), (b1 + 12, 3)):
        sel = (t >= mm * NS_MIN) & (t < mm * NS_MIN + sec * NS_S)
        cm[sel] = mm - 1
        chain_plan[mm - 1] = ("B", (t[sel].max() - mm * NS_MIN) / NS_S + 1e-6)
    for mm in (b1 + 8, b1 + 9, b1 + 10, b1 + 11, b1 + 12):
        plan[mm] = ("none", np.nan, False)                       # no single move reconciles a chain
    # lost: minute b0+30 has no candle and its volume is nowhere
    lost = m == b0 + 30
    plan[b0 + 29] = ("none", np.nan, False)
    plan[b0 + 30] = ("none", np.nan, False)
    keep = ~lost
    cmin, cinv = np.unique(cm[keep], return_inverse=True)
    cvol = np.bincount(cinv, weights=size[keep]).astype(np.float32).astype(np.float64)
    # candidates: q at b0+5 (two-sided, A), at window end (one-sided) with an A lag at that boundary
    qe = int(w_end[1])
    sel = (t >= qe - 200_000_000) & (t < qe)
    # the window-end candle q holds the moved prints plus prints of q (unfetched): add a candle row at q
    cmin = np.r_[cmin, qe // NS_MIN]
    cvol = np.r_[cvol, size[sel].sum() + 5.0]
    o = np.argsort(cmin)
    cmin, cvol = cmin[o], cvol[o]
    i_last = np.searchsorted(cmin, qe // NS_MIN - 1)
    cvol[i_last] -= size[sel].sum()
    plan[qe // NS_MIN - 2] = ("edge", np.nan, False)            # minute qe-1 lost prints to the unfetched minute qe
    q = np.array([bA, int(w_end[1])])
    pairs, cands, info, CH = coin_boundaries(t, size, usd, w_start, w_end, q, cmin, cvol)
    got = pairs.set_index("minute")
    ch = CH.set_index("minute")                                  # chain result per boundary (indexed by left minute)
    for mm, (kind, d, whole) in plan.items():
        if kind in ("A", "B"):                                   # isolated moves: the chain check agrees and confirms
            assert ch.loc[mm].kind == kind and abs(ch.loc[mm].d_s - d) < 1e-9 and bool(ch.loc[mm].confirmed), mm - b0
    for mm, (kind, d) in chain_plan.items():
        g = ch.loc[mm]
        assert g.kind == kind and abs(g.d_s - d) < 1e-9 and bool(g.confirmed), (mm - b1, g.kind, g.d_s, d)
    assert ch.loc[b1 + 8].kind == "zero" and ch.loc[b1 + 12].kind == "zero"
    assert ch.loc[b0 + 29].kind == "zero"
    assert ch.loc[b0 + 30].kind == "A" and bool(ch.loc[b0 + 30].whole) and not bool(ch.loc[b0 + 30].confirmed)
    assert ch.loc[b0 + 31].kind == "unexplained"                 # the lost minute is caught, not taken as a shift
    for mm, (kind, d, whole) in plan.items():
        assert mm in got.index, f"boundary after minute {mm - b0} not found unequal"
        g = got.loc[mm]
        assert g.kind == kind, (mm - b0, g.kind, kind)
        if kind in ("A", "B"):
            assert abs(g.d_s - d) < 1e-9 and bool(g.whole) == whole and bool(g.strict), (mm - b0, g.d_s, d, g.whole)
    assert set(got.index) == set(plan), (sorted(set(got.index) - set(plan)), sorted(set(plan) - set(got.index)))
    c0, c1 = cands.iloc[0], cands.iloc[1]
    assert c0.two_sided and c0.kind == "A" and abs(c0.d_s - plan[b0 + 4][1]) < 1e-9
    assert (not c1.two_sided) and c1.kind == "A" and abs(c1.d_s - (qe - t[sel].min()) / NS_S) < 1e-9
    assert np.isclose(c1.usd_moved, usd[sel].sum())
    assert c0.chain_kind == "A" and bool(c0.chain_confirmed) and c1.chain_kind == "A" and bool(c1.chain_confirmed)
    assert abs(c1.chain_d_s - c1.d_s) < 1e-9
    msg = (f"prints_boundary self-test passed ({info['unequal_pairs']} unequal pairs; A 0.35 s lag, B 2 s lead, "
           "whole-minute A, their neighbours, a lost minute, a window edge, a one-sided window-end A and, by the "
           "chain check, a three-boundary B chain all recovered)")
    print(msg, flush=True)
    return msg


# ------------------------------------------------------------------------------------------------ summaries
def qv(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return [round(float(v), 6) for v in np.quantile(x, QS)] if len(x) else None


def pair_summary(R, n_pairs):
    out = dict(pairs=int(n_pairs), unequal=int(len(R)))
    for kind in ("A", "B"):
        g = R[R.kind == kind]
        sub = g[~g.whole.astype(bool)]
        out[kind] = dict(n=int(len(g)), strict=int(g.strict.astype(bool).sum()), whole_minute=int(g.whole.astype(bool).sum()),
                         d_q=qv(g.d_s), d_sub_minute_q=qv(sub.d_s),
                         d_strict_sub_minute_q=qv(sub[sub.strict.astype(bool)].d_s))
    out["neighbour"] = int((R.kind == "neighbour").sum())
    out["edge"] = int((R.kind == "edge").sum())
    out["A_and_B_both_reconcile"] = int((R.both == True).sum())  # noqa: E712
    nr = R[R.kind == "none"]
    out["not_reconciled"] = dict(n=int(len(nr)), a_like=int(((nr.em < 0) & (nr.en > 0)).sum()),
                                 b_like=int(((nr.em > 0) & (nr.en < 0)).sum()),
                                 same_sign=int(((nr.em * nr.en) >= 0).sum()))
    out["share_whole_minute_of_unequal"] = (float(R.whole.astype(bool).sum() / len(R)) if len(R) else None)
    return out


def chain_summary(CH, R):
    """Chain check over every internal boundary, and what it says about the pairs the single-move test left open."""
    out = dict(boundaries=int(len(CH)), kinds={k: int(v) for k, v in CH.kind.value_counts().items()})
    for kind in ("A", "B"):
        g = CH[(CH.kind == kind) & CH.confirmed.astype(bool)]
        sub = g[~g.whole.astype(bool)]
        out[kind] = dict(confirmed=int(len(g)), unconfirmed=int(((CH.kind == kind) & ~CH.confirmed.astype(bool)).sum()),
                         whole_minute=int(g.whole.astype(bool).sum()), d_q=qv(g.d_s), d_sub_minute_q=qv(sub.d_s))
    open_ = R[R.kind.isin(["none", "edge"])]
    lab = np.where(open_.chain_kind.isin(["A", "B"]) & open_.chain_confirmed.astype(bool),
                   open_.chain_kind + "_confirmed", open_.chain_kind)
    out["single_move_open_pairs_by_chain"] = {k: int(v) for k, v in pd.Series(lab).value_counts().items()}
    return out


def cand_summary(Q):
    n = len(Q)
    A = Q[Q.kind == "A"]
    two, one = Q[Q.two_sided], Q[~Q.two_sided]
    ratio = (A.usd_moved / A.usd_30).to_numpy()
    QC = Q[(Q.chain_kind == "A") & Q.chain_confirmed.astype(bool)]
    allr = np.where(Q.kind == "A", Q.usd_moved / Q.usd_30, 0.0)
    return dict(
        n=int(n), two_sided=int(len(two)), one_sided=int(len(one)),
        two_sided_kinds={k: int(v) for k, v in two.kind.value_counts().items()},
        one_sided_kinds={k: int(v) for k, v in one.kind.value_counts().items()},
        A=int(len(A)), A_share=float(len(A) / n) if n else None, A_strict=int(A.strict.astype(bool).sum()),
        A_whole_minute=int(A.whole.astype(bool).sum()), A_d_q=qv(A.d_s), A_d_sub_minute_q=qv(A[~A.whole.astype(bool)].d_s),
        A_usd_over_usd30_q=qv(ratio), usd_over_usd30_mean_all=float(np.nanmean(allr)) if n else None,
        B=int((Q.kind == "B").sum()),
        chain_kinds={k: int(v) for k, v in Q.chain_kind.value_counts().items()},
        chain_A_confirmed=int(len(QC)), chain_A_confirmed_share=float(len(QC) / n) if n else None,
        chain_A_unconfirmed=int(((Q.chain_kind == "A") & ~Q.chain_confirmed.astype(bool)).sum()),
        chain_A_whole_minute=int(QC.chain_whole.astype(bool).sum()), chain_A_d_q=qv(QC.chain_d_s),
        chain_A_d_sub_minute_q=qv(QC[~QC.chain_whole.astype(bool)].chain_d_s),
        chain_A_usd_over_usd30_q=qv((QC.chain_usd_moved / QC.usd_30).to_numpy()),
        chain_usd_over_usd30_mean_all=float(np.nanmean(np.where((Q.chain_kind == "A") & Q.chain_confirmed.astype(bool),
                                                                Q.chain_usd_moved / Q.usd_30, 0.0))) if n else None,
        chain_B_confirmed=int(((Q.chain_kind == "B") & Q.chain_confirmed.astype(bool)).sum()))


def main(art_dir, out_dir=os.path.join(ROOT, "reports", "signal_lab", "prints")):
    import prints_diag as PD                                   # candles loader
    test_msg = selftest()
    files = sorted(glob.glob(os.path.join(art_dir, "**", "prints_*.parquet"), recursive=True))
    W = pd.read_csv(os.path.join(ROOT, "reports", "signal_lab", "prints", "windows.csv"), parse_dates=["start", "end"])
    C = PFE.candidates()
    U = pd.concat([pd.read_parquet(os.path.join(ROOT, "reports", "signal_lab", "prints", f"f6_{e}.parquet"))
                   .assign(era=e) for e in ("main", "early")], ignore_index=True)
    assert (U.coin.astype(str).to_numpy() == C.coin.to_numpy()).all() and (U.ts.to_numpy() == C.ts.to_numpy()).all()
    pairs, cands, info, chains = [], [], {}, []
    for product, g in W.groupby("product"):
        coin = product[:-4]
        raw, _ = PFE.load_coin(files, product)
        if raw is None:
            print(f"{coin}: no prints", flush=True)
            continue
        d, _ = PFE.prep(raw["trade_id"], raw["t"], raw["price"], raw["size"], raw["sell"])
        del raw
        g = g.sort_values("start")
        idx = np.flatnonzero((C.coin == coin).to_numpy())
        q = C.ts.to_numpy()[idx].astype("datetime64[ns]").view(np.int64)
        cmin, cvol = PD.candles(coin)
        R, Q, inf, CH = coin_boundaries(d["t"], d["size"], d["usd"],
                                    g.start.to_numpy().astype("datetime64[ns]").view(np.int64),
                                    g.end.to_numpy().astype("datetime64[ns]").view(np.int64), q, cmin, cvol)
        del d
        R["coin"] = coin
        CH["coin"] = coin
        chains.append(CH)
        Q["era"], Q["coin"], Q["ts"] = C.era.to_numpy()[idx], coin, C.ts.to_numpy()[idx]
        Q["usd_30"] = U.usd_30.to_numpy()[idx]
        Q["row"] = idx
        pairs.append(R)
        cands.append(Q)
        info[coin] = inf
        print(f"{coin}: {inf}; A {int((R.kind == 'A').sum())}, B {int((R.kind == 'B').sum())}, "
              f"none {int((R.kind == 'none').sum())}; candidates A {int((Q.kind == 'A').sum())} of {len(Q)}", flush=True)
    R = pd.concat(pairs, ignore_index=True)
    Q = pd.concat(cands, ignore_index=True).sort_values("row").reset_index(drop=True)
    R["year"] = pd.to_datetime(R.minute * NS_MIN).dt.year
    Q["year"] = pd.to_datetime(Q.ts).dt.year
    n_pairs_year = {}
    for product, g in W.groupby("product"):                   # all adjacent pairs inside windows, by year
        for s_, e_ in zip(g.start, g.end):
            n = int((e_ - s_).total_seconds() // 60) - 1
            n_pairs_year[s_.year] = n_pairs_year.get(s_.year, 0) + n
    out = dict(self_test=test_msg, tol=TOL, strict=STRICT, coins=info,
               pairs={"all": pair_summary(R, sum(n_pairs_year.values()))})
    for y, g in R.groupby("year"):
        out["pairs"][str(y)] = pair_summary(g, n_pairs_year.get(int(y), 0))
    CH = pd.concat(chains, ignore_index=True)
    CH["year"] = pd.to_datetime(CH.minute * NS_MIN).dt.year
    out["chain"] = {"all": chain_summary(CH, R)}
    for y, g in CH.groupby("year"):
        out["chain"][str(y)] = chain_summary(g, R[R.year == y])
    out["candidates"] = {e: cand_summary(g) for e, g in Q.groupby("era")}
    out["candidates_by_year"] = {str(y): cand_summary(g) for y, g in Q.groupby("year")}
    A = R[R.kind == "A"]
    QA_ = Q[Q.kind == "A"]
    CA = CH[(CH.kind == "A") & CH.confirmed.astype(bool)]
    QC = Q[(Q.chain_kind == "A") & Q.chain_confirmed.astype(bool)]
    out["largest_A_chain_confirmed"] = dict(
        boundaries_d_max=float(CA.d_s.max()) if len(CA) else None,
        boundaries_sub_minute_d_max=float(CA[~CA.whole.astype(bool)].d_s.max()) if (~CA.whole.astype(bool)).any() else None,
        boundaries_whole_minute=int(CA.whole.astype(bool).sum()),
        at_q_d_max=float(QC.chain_d_s.max()) if len(QC) else None,
        at_q_sub_minute_d_max=(float(QC[~QC.chain_whole.astype(bool)].chain_d_s.max())
                               if (~QC.chain_whole.astype(bool)).any() else None),
        at_q_whole_minute=int(QC.chain_whole.astype(bool).sum()))
    out["largest_A"] = dict(
        pairs_d_max=float(A.d_s.max()) if len(A) else None,
        pairs_sub_minute_d_max=float(A[~A.whole.astype(bool)].d_s.max()) if (~A.whole.astype(bool)).any() else None,
        pairs_whole_minute=int(A.whole.astype(bool).sum()),
        at_q_d_max=float(QA_.d_s.max()) if len(QA_) else None,
        at_q_sub_minute_d_max=float(QA_[~QA_.whole.astype(bool)].d_s.max()) if (~QA_.whole.astype(bool)).any() else None,
        at_q_whole_minute=int(QA_.whole.astype(bool).sum()))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "qa_boundary.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    Q[["era", "coin", "ts", "two_sided", "kind", "d_s", "whole", "strict", "usd_moved", "chain_kind", "chain_d_s",
       "chain_whole", "chain_usd_moved", "chain_confirmed", "usd_30"]].to_parquet(
        os.path.join(out_dir, "qa_boundary_cand.parquet"), index=False)
    print(json.dumps({k: out[k] for k in ("largest_A", "largest_A_chain_confirmed", "candidates")}, indent=1,
                     default=str), flush=True)
    print(json.dumps(out["pairs"]["all"], indent=1, default=str), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    else:
        main(*sys.argv[1:3])
