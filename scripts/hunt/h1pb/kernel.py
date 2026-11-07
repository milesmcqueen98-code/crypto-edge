#!/usr/bin/env python3
"""H1 trade-print fill simulator core (reports/hunt/h1pb/SPEC.md "Trades"; reports/hunt_prereg.md "Fill and latency").

Inputs (one coin, one fetched chunk): perp prints in time order (t ns, p USD per coin, q contracts); every fetched
segment starts with a synthetic print (q = 0) carrying the last perp price before the segment (the close of the last
traded 1-minute candle), so the first real print has a predecessor. Per print: L = the order price live at that print
(NaN = no order) and F = the fair value behind it.

Entry (long; short mirrored): print i fills our resting bid at L_i when p_i <= L_i - 1 tick (strictly through) and the
previous print p_{i-1} >= L_i (the post-only bid could rest: the market was not already through it).
  Fill price = L_i. Size = min(target contracts, floor(theta x contracts of the consecutive prints strictly beyond L_i
  from print i on, while the price stays beyond it)). Every trigger is returned, also those with size 0.
Take-profit: post-only at TP = L + 0.6 (F - L) on the tick grid (rounded toward L, at least one tick from L), placed
  at fill + 1 s. It rests once the last print is at or inside TP; then each run of consecutive prints strictly beyond
  TP that starts from a print at or inside TP fills floor(theta x run contracts), accumulated, until the position is
  closed or the deadline.
Time exit: contracts still open at fill + H are sold at the first print at least 2 s after the deadline (same fetched
  segment; otherwise the entry is marked invalid for that H). Taker costs are added by the caller's cost model.
The slot rules (one position per coin and side, at most 6 open) are applied afterwards in time order.
"""
import numpy as np
from numba import njit

NS = 1_000_000_000
LAT_NS = 1 * NS            # take-profit placed >= 1 s after the fill
EXIT_LAG_NS = 2 * NS       # market exit: first print >= 2 s after the deadline


@njit(cache=True)
def _count(t, p, syn, seg, L, is_long, tick, cs, keep_lo, keep_hi):
    n = len(t)
    h = 0.5 * tick
    m = 0
    for i in range(1, n):
        if syn[i] or t[i] < keep_lo or t[i] >= keep_hi:
            continue
        Lv = L[i]
        if not (Lv > 0.0) or Lv * cs < 150.0 or seg[i - 1] != seg[i]:
            continue
        if is_long:
            if p[i] < Lv - h and p[i - 1] > Lv - h:
                m += 1
        else:
            if p[i] > Lv + h and p[i - 1] < Lv + h:
                m += 1
    return m


@njit(cache=True)
def entries(t, p, q, syn, seg, L, F, is_long, tick, cs, target_usd, thetas, hs_ns, keep_lo, keep_hi):
    """All trigger prints with their outcomes for every H in hs_ns and theta in thetas.
    Returns (idx, run, ntg, tp, n[m, a], tpn[m, b, a], gross[m, b, a], tclose[m, b, a], remnot[m, b, a],
    chours[m, b, a], valid[m, b])."""
    n_pr = len(t)
    h = 0.5 * tick
    nth, nh = len(thetas), len(hs_ns)
    m_tot = _count(t, p, syn, seg, L, is_long, tick, cs, keep_lo, keep_hi)
    o_i = np.empty(m_tot, np.int64)
    o_run = np.empty(m_tot, np.float64)
    o_ntg = np.empty(m_tot, np.int64)
    o_tp = np.empty(m_tot, np.float64)
    o_n = np.zeros((m_tot, nth), np.int64)
    o_tpn = np.zeros((m_tot, nh, nth), np.int64)
    o_gross = np.zeros((m_tot, nh, nth), np.float64)
    o_tclose = np.zeros((m_tot, nh, nth), np.int64)
    o_remnot = np.zeros((m_tot, nh, nth), np.float64)
    o_chours = np.zeros((m_tot, nh, nth), np.float64)
    o_valid = np.zeros((m_tot, nh), np.bool_)
    m = 0
    for i in range(1, n_pr):
        if syn[i] or t[i] < keep_lo or t[i] >= keep_hi:
            continue
        Lv = L[i]
        if not (Lv > 0.0) or Lv * cs < 150.0 or seg[i - 1] != seg[i]:
            continue
        if is_long:
            if not (p[i] < Lv - h and p[i - 1] > Lv - h):
                continue
        else:
            if not (p[i] > Lv + h and p[i - 1] < Lv + h):
                continue
        run = 0.0
        j = i
        while j < n_pr and seg[j] == seg[i] and not syn[j]:
            if is_long:
                if not (p[j] < Lv - h):
                    break
            else:
                if not (p[j] > Lv + h):
                    break
            run += q[j]
            j += 1
        ntg = int(np.floor(target_usd / (Lv * cs) + 1e-9))
        Fv = F[i]
        if is_long:
            tp = np.floor((Lv + 0.6 * (Fv - Lv)) / tick + 1e-9) * tick
            if tp < Lv + tick:
                tp = Lv + tick
        else:
            tp = np.ceil((Lv - 0.6 * (Lv - Fv)) / tick - 1e-9) * tick
            if tp > Lv - tick:
                tp = Lv - tick
        o_i[m] = i
        o_run[m] = run
        o_ntg[m] = ntg
        o_tp[m] = tp
        nmax = 0
        for a in range(nth):
            o_n[m, a] = min(ntg, int(np.floor(thetas[a] * run + 1e-9)))
            if o_n[m, a] > nmax:
                nmax = o_n[m, a]
        te = t[i]
        if nmax == 0:
            for b in range(nh):
                o_valid[m, b] = True
                for a in range(nth):
                    o_tclose[m, b, a] = te
            m += 1
            continue
        for b in range(nh):
            D = te + hs_ns[b]
            open_ = np.zeros(nth, np.int64)
            cum = np.zeros(nth, np.float64)
            n_open = 0
            for a in range(nth):
                open_[a] = o_n[m, a]
                o_tclose[m, b, a] = te
                if open_[a] > 0:
                    n_open += 1
            in_run = False
            j = i + 1
            while j < n_pr and seg[j] == seg[i] and not syn[j] and t[j] < D:
                beyond = (p[j] > tp + h) if is_long else (p[j] < tp - h)
                if beyond and t[j] >= te + LAT_NS:
                    if not in_run:
                        prev_in = (p[j - 1] < tp + h) if is_long else (p[j - 1] > tp - h)
                        if prev_in:
                            in_run = True
                            for a in range(nth):
                                cum[a] = 0.0
                    if in_run:
                        for a in range(nth):
                            if open_[a] > 0:
                                before = int(np.floor(thetas[a] * cum[a] + 1e-9))
                                cum[a] += q[j]
                                after = int(np.floor(thetas[a] * cum[a] + 1e-9))
                                f = min(open_[a], after - before)
                                if f > 0:
                                    open_[a] -= f
                                    o_tpn[m, b, a] += f
                                    o_gross[m, b, a] += f * cs * ((tp - Lv) if is_long else (Lv - tp))
                                    o_chours[m, b, a] += f * (t[j] - te) / 3.6e12
                                    o_tclose[m, b, a] = t[j]
                                    if open_[a] == 0:
                                        n_open -= 1
                else:
                    in_run = False
                if n_open == 0:
                    break
                j += 1
            if n_open == 0:
                o_valid[m, b] = True
                continue
            k = j
            while k < n_pr and seg[k] == seg[i] and not syn[k] and t[k] < D + EXIT_LAG_NS:
                k += 1
            if k < n_pr and seg[k] == seg[i] and not syn[k]:
                x = p[k]
                o_valid[m, b] = True
                for a in range(nth):
                    if open_[a] > 0:
                        o_gross[m, b, a] += open_[a] * cs * ((x - Lv) if is_long else (Lv - x))
                        o_remnot[m, b, a] = open_[a] * cs * x
                        o_chours[m, b, a] += open_[a] * (t[k] - te) / 3.6e12
                        o_tclose[m, b, a] = t[k]
            else:
                o_valid[m, b] = False
        m += 1
    return o_i, o_run, o_ntg, o_tp, o_n, o_tpn, o_gross, o_tclose, o_remnot, o_chours, o_valid
