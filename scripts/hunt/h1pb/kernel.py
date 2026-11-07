#!/usr/bin/env python3
"""H1 trade-print simulator core (reports/hunt/h1pb/SPEC.md "Trades"; reports/hunt_prereg.md "Fill and latency rules").

Inputs per coin are perp prints in time order (USD per coin, size in contracts) with a synthetic print at the start of
every fetched segment carrying the last price before it (the close of the last traded 1-minute candle), and, per print,
the order price L that is live when the print happens (NaN = no order) and the fair value F behind it.

Entry (long; short mirrored): print i fills our resting bid at L_i when p_i < L_i (strictly, i.e. at least one tick
through) and the previous print p_{i-1} >= L_i (the bid could rest: post-only, market not already through it).
  Fill price = L_i. Size = min(target contracts, floor(theta * contracts of the consecutive prints strictly below L_i
  from print i on)). No fill if that is 0 contracts.
Take-profit: post-only at TP = L + 0.6 (F - L), rounded to the tick toward L, live from fill + 1 s. Each run of
  consecutive prints strictly above TP that starts from a print at or below TP fills min(open, floor(theta * run
  contracts)), accumulated print by print.
Time exit: whatever is open at fill + H is sold at the first print at least 2 s after the deadline (fallback: the
  open of the first traded candle minute after the fetched segment; the exact first print there). The taker cost
  (fee + 1.5x half-spread) is added by the caller's cost model.
Every trigger print is returned as a potential entry with its own outcome; the slot rules (one position per coin and
side, at most 6 open) are applied afterwards in time order (book.py), which is exact because an entry's outcome does
not depend on other positions.
"""
import numpy as np
from numba import njit

NS = 1_000_000_000
LAT_NS = 1 * NS            # orders and take-profits act on information >= 1 s old
EXIT_LAG_NS = 2 * NS       # market exits: first print >= 2 s after the deadline


@njit(cache=True)
def potential_entries(t, p, q, syn, seg, L, F, is_long, tick, cs, target_usd, thetas, hs_ns, seg_fb_t, seg_fb_p):
    """Returns arrays describing every potential entry (trigger print with >= 1 contract at thetas[0])."""
    n = len(t)
    h = 0.5 * tick
    nth, nh = len(thetas), len(hs_ns)
    cap = 1024
    o_i = np.empty(cap, np.int64)
    o_run = np.empty(cap, np.float64)
    o_ntg = np.empty(cap, np.int64)
    o_tp = np.empty(cap, np.float64)
    o_n = np.empty((cap, nth), np.int64)
    o_tclose = np.empty((cap, nh), np.int64)            # final exit time at thetas[0]
    o_gross = np.empty((cap, nh, nth), np.float64)      # USD
    o_tpn = np.empty((cap, nh, nth), np.int64)          # contracts closed by the take-profit
    o_rem_notional = np.empty((cap, nh, nth), np.float64)   # USD notional sold at market (exit price x contracts x cs)
    o_chours = np.empty((cap, nh, nth), np.float64)     # contract-hours held
    o_x = np.empty((cap, nh), np.float64)               # time-exit price
    o_tx = np.empty((cap, nh), np.int64)                # time-exit print time (-1 if fully closed by TP)
    o_tp_first = np.empty((cap, nh), np.int64)          # first take-profit fill time (-1 if none)
    m = 0
    for i in range(1, n):
        if syn[i]:
            continue
        Lv = L[i]
        if not (Lv > 0.0):
            continue
        if is_long:
            if not (p[i] < Lv - h and p[i - 1] > Lv - h):
                continue
        else:
            if not (p[i] > Lv + h and p[i - 1] < Lv + h):
                continue
        if Lv * cs < 150.0:
            continue
        # through-volume of the run that starts at i
        run = 0.0
        j = i
        while j < n and seg[j] == seg[i] and not syn[j]:
            if is_long:
                if not (p[j] < Lv - h):
                    break
            else:
                if not (p[j] > Lv + h):
                    break
            run += q[j]
            j += 1
        ntg = int(np.floor(target_usd / (Lv * cs) + 1e-9))
        n0 = min(ntg, int(np.floor(thetas[0] * run + 1e-9)))
        if n0 < 1:
            continue
        if m == cap:
            cap2 = cap * 2
            o_i = _grow1(o_i, cap2)
            o_run = _grow1f(o_run, cap2)
            o_ntg = _grow1(o_ntg, cap2)
            o_tp = _grow1f(o_tp, cap2)
            o_n = _grow2(o_n, cap2)
            o_tclose = _grow2(o_tclose, cap2)
            o_gross = _grow3f(o_gross, cap2)
            o_tpn = _grow3(o_tpn, cap2)
            o_rem_notional = _grow3f(o_rem_notional, cap2)
            o_chours = _grow3f(o_chours, cap2)
            o_x = _grow2f(o_x, cap2)
            o_tx = _grow2(o_tx, cap2)
            o_tp_first = _grow2(o_tp_first, cap2)
            cap = cap2
        te = t[i]
        Fv = F[i]
        if is_long:
            tp = np.floor((Lv + 0.6 * (Fv - Lv)) / tick + 1e-9) * tick
            if tp < Lv:
                tp = Lv
        else:
            tp = np.ceil((Lv - 0.6 * (Lv - Fv)) / tick - 1e-9) * tick
            if tp > Lv:
                tp = Lv
        o_i[m] = i
        o_run[m] = run
        o_ntg[m] = ntg
        o_tp[m] = tp
        for a in range(nth):
            o_n[m, a] = min(ntg, int(np.floor(thetas[a] * run + 1e-9)))
        for b in range(nh):
            D = te + hs_ns[b]
            open_ = np.empty(nth, np.int64)
            tpn = np.zeros(nth, np.int64)
            gross = np.zeros(nth, np.float64)
            chours = np.zeros(nth, np.float64)
            cum = np.zeros(nth, np.float64)
            for a in range(nth):
                open_[a] = o_n[m, a]
            t_close0 = -1
            t_tp_first = -1
            j = i + 1
            in_run = False
            while j < n and seg[j] == seg[i] and t[j] < D:
                if syn[j]:
                    break
                beyond = (p[j] > tp + h) if is_long else (p[j] < tp - h)
                if beyond and t[j] >= te + LAT_NS:
                    if not in_run:
                        prev_ok = (p[j - 1] < tp + h) if is_long else (p[j - 1] > tp - h)
                        if prev_ok or j == i + 1:
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
                                    tpn[a] += f
                                    gross[a] += f * cs * ((tp - Lv) if is_long else (Lv - tp))
                                    chours[a] += f * (t[j] - te) / 3.6e12
                                    if a == 0:
                                        if t_tp_first < 0:
                                            t_tp_first = t[j]
                                        if open_[0] == 0:
                                            t_close0 = t[j]
                else:
                    in_run = False
                if open_[0] == 0 and (nth == 1 or open_[nth - 1] == 0):
                    break
                j += 1
            # time exit for whatever is open
            x = np.nan
            tx = -1
            need = False
            for a in range(nth):
                if open_[a] > 0:
                    need = True
            if need:
                k = j
                while k < n and seg[k] == seg[i] and not syn[k] and t[k] < D + EXIT_LAG_NS:
                    k += 1
                if k < n and seg[k] == seg[i] and not syn[k]:
                    x = p[k]
                    tx = t[k]
                else:
                    x = seg_fb_p[seg[i]]
                    tx = seg_fb_t[seg[i]]
                for a in range(nth):
                    if open_[a] > 0:
                        gross[a] += open_[a] * cs * ((x - Lv) if is_long else (Lv - x))
                        o_rem_notional[m, b, a] = open_[a] * cs * x
                        chours[a] += open_[a] * (tx - te) / 3.6e12
                    else:
                        o_rem_notional[m, b, a] = 0.0
                if open_[0] > 0:
                    t_close0 = tx
            else:
                for a in range(nth):
                    o_rem_notional[m, b, a] = 0.0
            o_tclose[m, b] = t_close0
            o_x[m, b] = x
            o_tx[m, b] = tx
            o_tp_first[m, b] = t_tp_first
            for a in range(nth):
                o_gross[m, b, a] = gross[a]
                o_tpn[m, b, a] = tpn[a]
                o_chours[m, b, a] = chours[a]
        m += 1
    return (o_i[:m], o_run[:m], o_ntg[:m], o_tp[:m], o_n[:m], o_tclose[:m], o_gross[:m], o_tpn[:m],
            o_rem_notional[:m], o_chours[:m], o_x[:m], o_tx[:m], o_tp_first[:m])


@njit(cache=True)
def _grow1(a, c):
    b = np.empty(c, a.dtype)
    b[:len(a)] = a
    return b


@njit(cache=True)
def _grow1f(a, c):
    b = np.empty(c, a.dtype)
    b[:len(a)] = a
    return b


@njit(cache=True)
def _grow2(a, c):
    b = np.empty((c, a.shape[1]), a.dtype)
    b[:a.shape[0]] = a
    return b


@njit(cache=True)
def _grow2f(a, c):
    b = np.empty((c, a.shape[1]), a.dtype)
    b[:a.shape[0]] = a
    return b


@njit(cache=True)
def _grow3(a, c):
    b = np.empty((c, a.shape[1], a.shape[2]), a.dtype)
    b[:a.shape[0]] = a
    return b


@njit(cache=True)
def _grow3f(a, c):
    b = np.empty((c, a.shape[1], a.shape[2]), a.dtype)
    b[:a.shape[0]] = a
    return b


@njit(cache=True)
def row_triggers(t, p, syn, row, L, is_long, tick, nrows):
    """Per candle row: 1 if some print in the row's live window triggers at that row's level (minute mode)."""
    out = np.zeros(nrows, np.int8)
    h = 0.5 * tick
    for i in range(1, len(t)):
        if syn[i]:
            continue
        r = row[i]
        if r < 0 or r >= nrows:
            continue
        Lv = L[i]
        if not (Lv > 0.0):
            continue
        if is_long:
            if p[i] < Lv - h and p[i - 1] > Lv - h:
                out[r] = 1
        else:
            if p[i] > Lv + h and p[i - 1] < Lv + h:
                out[r] = 1
    return out
