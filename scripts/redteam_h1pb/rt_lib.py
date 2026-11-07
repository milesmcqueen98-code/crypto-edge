#!/usr/bin/env python3
"""Red team h1pb: an independent implementation of the frozen variant (sync, k = 6, long, H = 60, theta 0.5, orders
only 4:55-6:05 pm ET) from raw Coinbase prints. Written from the SPEC/pre-registration, not from the builder's kernel.

Levels (SPEC "Levels"): b = log(perp close / spot close) on both-traded minutes; bbar = trailing 24 h median of b
(min 20 obs, v2 floor), e = b - bbar(previous both-traded minute), sigma = trailing 3-day std of e (min 100 obs); the
statistics used for a print at time tau are those of the last both-traded minute <= the minute before
row = floor(tau - lam). Spot reference S = last spot print at or before tau - lam. F = S exp(bbar);
L = floor_tick(F exp(-6 sigma)); L >= 0.95 S (Fair Value Limit); L x contract >= $150.
Fill (long): print i with p_i <= L - 1 tick and p_{i-1} >= L. Size = min(floor($10K / (L cs)), floor(theta x contracts
of the consecutive prints from i strictly below L)). Take-profit TP = floor_tick(L + 0.6 (F - L)) (>= L + 1 tick),
live from fill + 1 s; fills floor(theta x cumulative contracts) on runs strictly above TP that start from a print at
or below TP. Time exit: first print >= fill + 60 min + 2 s.
"""
import math
import os
import sys

import numpy as np
import pandas as pd
from numba import njit

NS = 10**9
MIN_NS = 60 * NS
GRID_END = pd.Timestamp("2026-11-06 02:00")
PX_SCALE = {"PEPE": 1000.0, "SHIB": 1000.0}


def my_stats(coin, data_root, cs):
    """Minute-grid statistics. Returns dict with t0 (ns), bbar, sig (row t = known at end of t-1), s_cf (spot close
    ffill <= 10 min), s_prev, spot high/low, perp low/close (USD per coin), perp traded mask."""
    P = pd.read_parquet(os.path.join(data_root, "cfm", f"{coin}.parquet"))
    P = P.drop_duplicates("ts").set_index("ts").sort_index()
    P = P[(P.volume > 0) & (P.index < GRID_END)]
    P.index = pd.DatetimeIndex(P.index).as_unit("ns")
    S = pd.read_parquet(os.path.join(data_root, "minute", f"{coin}.parquet"))
    S = S.drop_duplicates("ts").set_index("ts").sort_index()
    S = S[S.volume > 0]
    S.index = pd.DatetimeIndex(S.index).as_unit("ns")
    sc = PX_SCALE.get(coin, 1.0)
    t0 = P.index.min().floor("min")
    idx = pd.date_range(t0, GRID_END, freq="min", inclusive="left").as_unit("ns")     # pandas 3 defaults to us
    pc = P["close"].reindex(idx).to_numpy(float) / sc
    plo = P["low"].reindex(idx).to_numpy(float) / sc
    S = S[(S.index >= t0 - pd.Timedelta(days=1)) & (S.index < GRID_END)].reindex(idx)
    s_close, s_hi, s_lo = (S[c].to_numpy(float) for c in ("close", "high", "low"))
    both = np.isfinite(pc) & np.isfinite(s_close)
    tb = idx[both]
    b = np.log(pc[both] / s_close[both])
    med = pd.Series(b, index=tb).rolling("24h", min_periods=20).median().to_numpy()
    e = b - np.concatenate([[np.nan], med[:-1]])
    sig = pd.Series(e, index=tb).rolling("3D", min_periods=100).std().to_numpy()
    # statistics for row t: last both-traded minute with time <= t - 1 min
    pos = np.searchsorted(tb.asi8, idx.asi8 - MIN_NS, "right") - 1
    okp = pos >= 0
    bbar = np.where(okp, med[np.maximum(pos, 0)], np.nan)
    sg = np.where(okp, sig[np.maximum(pos, 0)], np.nan)
    s_cf = pd.Series(s_close).ffill(limit=10).to_numpy()
    s_prev = np.concatenate([[np.nan], s_cf[:-1]])
    p_cf = pd.Series(pc).ffill().to_numpy()
    return dict(coin=coin, idx=idx, t0=int(idx[0].value), n=len(idx), bbar=bbar, sig=sg, s_cf=s_cf, s_prev=s_prev,
                s_hi=s_hi, s_lo=s_lo, s_close=s_close, p_low=plo, p_close=pc, p_cf=p_cf)


def floor_tick(x, tick):
    return np.floor(x / tick + 1e-9) * tick


def levels(st, T, S_ref, lam_ns, tick, cs, k=6.0, fvl=0.05):
    """Per print time T (ns) with spot reference S_ref (last spot print <= T - lam): L, F (NaN where no order)."""
    row = (T - lam_ns - st["t0"]) // MIN_NS
    okr = (row >= 0) & (row < st["n"])
    r = np.clip(row, 0, st["n"] - 1)
    bb, sg = st["bbar"][r], st["sig"][r]
    with np.errstate(invalid="ignore"):
        F = S_ref * np.exp(bb)
        L = floor_tick(F * np.exp(-k * sg), tick)
        ok = okr & np.isfinite(L) & (sg > 0) & (L >= (1 - fvl) * S_ref) & (L * cs >= 150.0)
    return np.where(ok, L, np.nan), np.where(ok, F, np.nan), row


@njit(cache=True)
def sim(t, p, q, side, seg, syn, L, F, inwin, tick, cs, theta, size_buy_only, target, H_ns, tp_lat_ns, exit_lag_ns):
    """All long triggers in time order with their outcomes (no slot rules). side: 1 = maker BUY (aggressive seller)."""
    n = len(t)
    h = 0.5 * tick
    cap = 0
    for i in range(1, n):
        if inwin[i] and not syn[i] and seg[i] == seg[i - 1] and L[i] > 0 and p[i] < L[i] - h and p[i - 1] > L[i] - h:
            cap += 1
    o_i = np.empty(cap, np.int64)
    o_f = np.zeros((cap, 17), np.float64)
    m = 0
    for i in range(1, n):
        if not (inwin[i] and not syn[i] and seg[i] == seg[i - 1]):
            continue
        Lv = L[i]
        if not (Lv > 0) or not (p[i] < Lv - h and p[i - 1] > Lv - h):
            continue
        run = 0.0
        run_buy = 0.0
        nb = 0
        nts = 0
        pmin = p[i]
        last_t = -1
        j = i
        while j < n and seg[j] == seg[i] and not syn[j] and p[j] < Lv - h:
            run += q[j]
            if side[j] == 1:
                run_buy += q[j]
            nb += 1
            if t[j] != last_t:
                nts += 1
                last_t = t[j]
            if p[j] < pmin:
                pmin = p[j]
            j += 1
        run_end = t[j - 1]
        ntg = int(math.floor(target / (Lv * cs) + 1e-9))
        base = run_buy if size_buy_only else run
        nf = min(ntg, int(math.floor(theta * base + 1e-9)))
        tp = math.floor((Lv + 0.6 * (F[i] - Lv)) / tick + 1e-9) * tick
        if tp < Lv + tick:
            tp = Lv + tick
        te = t[i]
        gross = 0.0
        tpn = 0
        chours = 0.0
        tclose = te
        remnot = 0.0
        valid = 1.0
        xpx = np.nan
        if nf > 0:
            left = nf
            D = te + H_ns
            in_run = False
            cum = 0.0
            j = i + 1
            while j < n and seg[j] == seg[i] and t[j] < D and left > 0:
                if syn[j]:
                    j += 1
                    continue
                if p[j] > tp + h and t[j] >= te + tp_lat_ns:
                    if not in_run:
                        if p[j - 1] < tp + h:
                            in_run = True
                            cum = 0.0
                    if in_run:
                        before = int(math.floor(theta * cum + 1e-9))
                        cum += q[j]
                        after = int(math.floor(theta * cum + 1e-9))
                        f = min(left, after - before)
                        if f > 0:
                            left -= f
                            tpn += f
                            gross += f * cs * (tp - Lv)
                            chours += f * (t[j] - te) / 3.6e12
                            tclose = t[j]
                else:
                    in_run = False
                j += 1
            if left > 0:
                k = j
                while k < n and seg[k] == seg[i] and (syn[k] or t[k] < D + exit_lag_ns):
                    k += 1
                if k < n and seg[k] == seg[i]:
                    xpx = p[k]
                    gross += left * cs * (xpx - Lv)
                    remnot = left * cs * xpx
                    chours += left * (t[k] - te) / 3.6e12
                    tclose = t[k]
                else:
                    valid = 0.0
        o_i[m] = i
        o_f[m, 0] = Lv
        o_f[m, 1] = F[i]
        o_f[m, 2] = tp
        o_f[m, 3] = run
        o_f[m, 4] = run_buy
        o_f[m, 5] = nb
        o_f[m, 6] = nts
        o_f[m, 7] = pmin
        o_f[m, 8] = ntg
        o_f[m, 9] = nf
        o_f[m, 10] = tpn
        o_f[m, 11] = gross
        o_f[m, 12] = tclose
        o_f[m, 13] = remnot
        o_f[m, 14] = chours
        o_f[m, 15] = valid
        o_f[m, 16] = (run_end - te) / NS
        m += 1
    return o_i, o_f


COLS = ["L", "F", "TP", "run", "run_buy", "nb", "nts", "pmin", "ntg", "n", "tpn", "gross", "t_close", "remnot",
        "chours", "valid", "run_secs"]
