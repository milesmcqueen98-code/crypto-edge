#!/usr/bin/env python3
"""Red team (ladder v5): an independent minute-level replay of the live bot's cash rule (bot/spot/engine.py), written
from the engine's code. It does not import or copy scripts/ladder_v5/hsim.py or gates.py. Fills, costs and P&L come
from the frozen research simulator (scripts/ladder_v5/fsim.py evaluate), fed with each tranche's funded size.

Engine order per step t (the minute now starting), paper mode:
  settle(t-1): book the minute that just closed (parent 4-sigma fills, deeper fills, take-profit fills; a partly filled
               rung rests while the price stays below it, <= 15 more minutes)
  _manage(t):  deeper window closes (parent take-profit traded, or t >= parent minute + 60) -> cancel deeper bids;
               60-minute time exits (step fill + 61); then pending deeper rungs are placed in ladder-creation order if
               the last close is above the level and free cash = equity - positions at cost - ALL resting holds
               (including the 4-sigma bids placed at t-1) covers the rung (>= 50%: partial, else retried next minute)
  _allocate(t): approved, fresh, non-busy coins in prediction order; free = equity - positions - holds other than the
               armed 4-sigma bids; full want if it fits, a partial bid if >= 50% of the need, else nothing
Live (1-second poll) adds: the deeper rungs of a parent that fills during minute t are placed within a second, from the
cash then free (what the 4-sigma allocation at t left), so they can fill in the parent's own minute.
A coin is busy (no new 4-sigma bid) while its parent rung is open or its partly filled 4-sigma remainder rests.

Policies: engine (the claim's live book), nocash (same timing and busy rule, unlimited cash), research (unlimited
cash, no busy rule, the research's deeper timing: reproduces fsim.book exactly), preempt (C1a).
Bounds: minute (no reaction inside the parent's minute) and instant (deeper rungs placed at the parent's fill);
the live book is minute + s x (instant - minute) with fsim's s.
"""
import os
import sys
import time

import numba as nb
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v5"))
import fsim  # noqa: E402
import sim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "ladder_v5", "redteam")
FEE_M = 6.0 / 1e4                       # engine hold_usd: notional x (1 + maker fee), fee_bp_maker 6
POL = {"engine": 0, "nocash": 1, "research": 2, "preempt": 3}
MARGIN = 200                            # minutes after the last parent day (exits of late deeper fills)

_IN = {}


# ------------------------------------------------------------------------------------------------ inputs
def inputs(tag):
    """Frozen dataset, panel (pred, quarterly threshold), freshness, ADV table, deep paths, minute closes."""
    if tag in _IN:
        return _IN[tag]
    P = fsim.load(tag)
    coins = sorted(P.coin.unique())
    pdir = os.path.join(ROOT, "data", "ladder_v5", f"panel_{tag}")
    thr = pd.read_csv(os.path.join(pdir, "thr.csv"))
    tq = dict(zip(thr.quarter, thr.thr))
    first = None
    preds = {}
    for c in coins:
        p = pd.read_parquet(os.path.join(pdir, f"{c}.parquet"))
        preds[c] = p.set_index("ts").pred
    pidx = preds[coins[0]].index
    for c in coins:
        assert preds[c].index.equals(pidx)
    M = np.column_stack([preds[c].to_numpy(np.float32) for c in coins])
    q = pd.PeriodIndex(pidx, freq="Q").astype(str)
    th = np.asarray(q.map(tq), dtype=np.float64)
    src = sim.PERIODS[tag][2]
    has, close = {}, {}
    for c in coins:
        m = pd.read_parquet(os.path.join(ROOT, "data", src, f"{c}.parquet"), columns=["ts", "close", "volume"])
        m = m[m.volume > 0].drop_duplicates("ts").set_index("ts").sort_index()
        has[c] = m.index
        close[c] = m.close
    adv = pd.read_parquet(os.path.join(OUT, f"adv_{tag}.parquet"))
    D = pd.read_pickle(os.path.join(ROOT, "reports", "ladder_v5", f"deep_paths_{tag}.pkl"))
    _IN[tag] = dict(P=P, coins=coins, pidx=pidx, M=M, thr=th, has=has, close=close, adv=adv, D=D)
    return _IN[tag]


def era_arrays(tag, era, theta, C, today, notional=0.25, kappa=0.002, phantom=False, win=None, newcoin=False):
    """Per-minute candidate order and 4-sigma wants; parents and deeper rungs of the era (volumes scaled for today).
    phantom=True (artifact test): no freshness check, and a coin with unknown ADV bids notional x C / 3 (what hsim
    does); the engine skips a coin without recent candles and, here, a coin whose ADV is unknown gets no bid.
    newcoin=True (engine-faithful edge case): a fresh coin whose ADV is still unknown (first 10 days of trading) holds
    a notional x C / 3 bid, as the engine sizes it (no ADV cap); its trades are not priced (the dataset has size 0).
    win=(lo, hi): only bids and parents inside the window (engine check)."""
    I = inputs(tag)
    P, coins = I["P"], I["coins"]
    lo, hi = fsim.ERAS[era][1]
    W = fsim.window(P, lo, hi)
    scale = fsim.today_scale(P, lo, hi) if today else {}
    if today:
        W = fsim.apply_scale(W, scale)
    NC = len(coins)
    t0 = pd.Timestamp(lo)
    t_end = pd.Timestamp(hi) + pd.Timedelta(days=1)          # parents (and new bids) only before this
    idx = pd.date_range(t0, t_end + pd.Timedelta(minutes=MARGIN), freq="min", inclusive="left")
    T = len(idx)
    # prediction and approval
    pos = I["pidx"].get_indexer(idx)
    M = np.full((T, NC), np.nan, np.float32)
    ok = pos >= 0
    M[ok] = I["M"][pos[ok]]
    th = np.full(T, np.inf)
    th[ok] = I["thr"][pos[ok]]
    appr = M > th[:, None]
    appr[idx >= t_end] = False
    if win is not None:
        appr[(idx < pd.Timestamp(win[0])) | (idx >= pd.Timestamp(win[1]))] = False
    # fresh: a candle in [t-10, t-1]
    fresh = np.zeros((T, NC), bool)
    for j, c in enumerate(coins):
        h = np.zeros(T + 11, np.int32)
        ip = (I["has"][c] - (t0 - pd.Timedelta(minutes=11))) // pd.Timedelta(minutes=1)
        ip = ip[(ip >= 0) & (ip < T + 11)]
        h[np.asarray(ip, dtype=np.int64)] = 1
        cs = np.concatenate([[0], np.cumsum(h)])
        # minute t of idx is position t+11 in h; window positions t+1 .. t+10 (= minutes t-10 .. t-1)
        k = np.arange(T)
        fresh[:, j] = (cs[k + 11] - cs[k + 1]) > 0
    # wants (4-sigma rung: a third of min(notional x C, kappa x ADV x today's factor)); unknown ADV: no bid
    days = idx.floor("D")
    A = I["adv"].reindex(pd.DatetimeIndex(days.unique()))
    fac = np.array([scale.get(c, 1.0) for c in coins])
    S_day = np.minimum(notional * C, kappa * A[coins].to_numpy() * fac[None, :])
    di = pd.DatetimeIndex(days.unique()).get_indexer(days)
    want4 = S_day[di] / 3.0
    if phantom:
        want4 = np.where(np.isfinite(want4), want4, notional * C / 3.0)
        cand = appr & (want4 > 0)
    elif newcoin:
        want4 = np.where(np.isfinite(want4), want4, notional * C / 3.0)
        cand = appr & fresh & (want4 > 0)
    else:
        want4 = np.where(np.isfinite(want4), want4, 0.0)
        cand = appr & fresh & (want4 > 0)
    Pm = np.where(cand, M, -np.inf)
    order = np.argsort(-Pm, axis=1, kind="stable").astype(np.int8)
    ncand = cand.sum(axis=1).astype(np.int8)
    # parents and deeper rungs
    par = W[(W.k == 4.0) & W.filled].sort_values(["ts", "coin"])
    if win is not None:
        par = par[(par.ts >= pd.Timestamp(win[0])) & (par.ts < pd.Timestamp(win[1]))]
    cj = {c: j for j, c in enumerate(coins)}
    NP = len(par)
    p_t = ((par.ts - t0) // pd.Timedelta(minutes=1)).to_numpy(np.int64)
    p_c = par.coin.map(cj).to_numpy(np.int64)
    p_in = par.in_spot.to_numpy(np.float64)
    p_scan = par.scan_off.to_numpy(np.int64)
    p_tpoff = par.tp_off.to_numpy(np.int64)
    p_tp = par.tp_spot.to_numpy(np.float64)
    p_want = (np.minimum(notional * C, kappa * par.adv.fillna(0.0).to_numpy()) / 3.0)
    p_close = np.where(p_tpoff >= 0, p_t + p_tpoff + 1, p_t + 60)
    rows = {(t, c, k): i for i, t, c, k in zip(W.index, W.ts, W.coin, W.k)}
    p_row = np.zeros((NP, 3), np.int64)
    dp_start = np.zeros((NP, 2), np.int64)
    dp_len = np.zeros((NP, 2), np.int64)
    lvl_ok = np.ones((NP, 2, 62), bool)
    f_off, f_in, f_scan, f_tpoff, f_tp, f_g60, f_gtp = [], [], [], [], [], [], []
    n = 0
    D = I["D"]
    for i, r in enumerate(par.itertuples()):
        p_row[i, 0] = r.Index
        cl = I["close"][r.coin]
        for kk, k in enumerate((6.0, 8.0)):
            ri = rows[(r.ts, r.coin, k)]
            p_row[i, kk + 1] = ri
            d = D[ri]
            dp_start[i, kk], dp_len[i, kk] = n, len(d)
            if len(d):
                f_off += list(d.off.astype(np.int64))
                f_in += list(d.in_spot * scale.get(r.coin, 1.0))
                f_scan += list(d.scan_off.astype(np.int64))
                f_tpoff += list(d.tp_off.astype(np.int64))
                f_tp += list(d.tp_spot * scale.get(r.coin, 1.0))
                f_g60 += list(d.g60)
                f_gtp += list(d.g_tp)
                n += len(d)
                lvl = float(W.at[ri, "lvl"])
                # paper engine: placed at step ts+j only if the last close (minute ts+j-1) is above the level
                mins = pd.date_range(r.ts, periods=61, freq="min")
                cc = cl.reindex(cl.index.union(mins)).ffill(limit=30).reindex(mins).to_numpy()
                lvl_ok[i, kk, 1:62] = ~(cc <= lvl)          # NaN close: treated as above (rare)
    dp = dict(off=np.array(f_off, np.int64), inn=np.array(f_in, np.float64), scan=np.array(f_scan, np.int64),
              tpoff=np.array(f_tpoff, np.int64), tp=np.array(f_tp, np.float64), g60=np.array(f_g60),
              gtp=np.array(f_gtp))
    # research's first-fill index per rung (for the research policy) = path entry 0
    return dict(W=W, coins=coins, idx=idx, T=T, NC=NC, order=order, ncand=ncand, want4=want4, M=M, par=par,
                NP=NP, p_t=p_t, p_c=p_c, p_in=p_in, p_scan=p_scan, p_tpoff=p_tpoff, p_tp=p_tp, p_want=p_want,
                p_close=p_close, p_row=p_row, dp_start=dp_start, dp_len=dp_len, lvl_ok=lvl_ok, dp=dp, scale=scale,
                cand=cand, appr=appr, fresh=fresh, t_end=t_end)


# ------------------------------------------------------------------------------------------------ core
def _place(q, k, t, ts, usd, free, fee, dp_start, dp_len, f_off, late_fills, r_usd, r_place, r_state, r_fidx,
           r_ncash):
    """_place_pending for one rung: full if it fits, partial if >= 50% of the need, else deferred. Returns the
    dollars now held (notional x (1 + fee)), 0 if deferred."""
    need = usd * (1 + fee)
    if need <= free:
        pl = usd
    elif free >= 0.5 * need:
        pl = 0.999 * free / (1 + fee)
    else:
        r_ncash[q, k] += 1
        return 0.0
    r_usd[q, k] = pl
    r_place[q, k] = t
    r_state[q, k] = 1
    st, ln = dp_start[q, k], dp_len[q, k]
    for jj in range(st, st + ln):            # the first trade-through at or after the minute it starts resting
        if ts + f_off[jj] >= t:
            if late_fills or jj == st:
                r_fidx[q, k] = jj
            break
    return pl * (1 + fee)


_place = nb.njit(cache=True)(_place)


def _core(T, NC, order, ncand, want4, M, NP, p_t, p_c, p_in, p_scan, p_tpoff, p_tp, p_want, p_close, dp_start,
          dp_len, lvl_ok, f_off, f_in, f_scan, f_tpoff, f_tp, E, theta, fee, instant, policy, busy_on, rem_hold,
          tp_release, late_fills, inst_new_first, prio_mode, alloc_first, rel_shift, busy_mode, mkt_check,
          inst_retry_old, interleave):
    """One era, one bound. policy 0 engine, 1 nocash, 2 research, 3 preempt (C1a).
    prio_mode 0: ladders in creation order (engine dict order), 1: parent fill order.
    alloc_first: (artifact test) the 4-sigma allocation runs before the deeper rungs are placed.
    Artifact switches (hsim's choices): rel_shift 1 releases take-profit, exit and closed-window cash one minute
    earlier (at the take-profit minute / fill + 60 instead of the step after); busy_mode 1 frees the coin at the
    parent's take-profit touch + 1 or 61 whatever its fill; mkt_check False places a deeper rung below the market;
    inst_retry_old False retries older pending rungs only at minute steps; interleave False releases every closed
    window and time exit before any deeper rung is placed (the engine works ladder by ladder)."""
    INF = 1e300
    nocap = policy == 1 or policy == 2
    Ee = INF if nocap else E
    dN = np.zeros(T + 400)
    N = 0.0
    busy_until = np.zeros(NC, np.int64)
    alloc_prev = np.zeros(NC)
    alloc = np.zeros(NC)
    arm_key = np.zeros(NC, np.int64)
    # per parent
    a4 = np.zeros(NP)
    F4 = np.zeros(NP)
    tpF4 = np.zeros(NP)
    why4 = -np.ones(NP, np.int64)            # 0 funded, 1 busy, 2 cash, 3 not a candidate at its minute
    create = np.zeros(NP, np.int64)
    pool = np.zeros(NP)
    used = np.zeros(NP)
    usedtp = np.zeros(NP)
    win = np.zeros(NP, np.bool_)
    r_state = np.zeros((NP, 2), np.int64)    # 0 pending, 1 resting, 2 filled, 3 dead
    r_usd = np.zeros((NP, 2))
    r_fidx = -np.ones((NP, 2), np.int64)
    r_F = np.zeros((NP, 2))
    r_tpF = np.zeros((NP, 2))
    r_place = -np.ones((NP, 2), np.int64)
    r_ncash = np.zeros((NP, 2), np.int64)
    remc = np.zeros((NP, 2))                 # deeper remainder cancelled at the window close
    ex_step = -np.ones((NP, 3), np.int64)    # time exits (step fill + 61), released in _manage
    ex_amt = np.zeros((NP, 3))
    live = np.zeros(NP, np.bool_)
    live_ids = -np.ones(4096, np.int64)
    nlive = 0
    filled_prev = np.zeros(NC, np.bool_)
    filled_now = np.zeros(NC, np.bool_)
    fq_prev = -np.ones(NC, np.int64)
    fq_now = -np.ones(NC, np.int64)
    cash_short = 0
    qptr = 0
    for t in range(T):
        N += dN[t]
        # ================= settle minute t-1 (booked at step t)
        for c in range(NC):
            if not filled_prev[c]:
                continue
            q = fq_prev[c]
            a, F, tpF = a4[q], F4[q], tpF4[q]
            ts = p_t[q]
            if rem_hold and a - F > 0:
                N += F + (a - F) * (1 + fee)
                r_rem = min(ts + p_scan[q] + 2, ts + 16)
                dN[r_rem] -= (a - F) * (1 + fee)
            else:
                N += F
                r_rem = ts + 1
            if tp_release and tpF > 0:
                stp = ts + p_tpoff[q] + 1 - rel_shift
                if stp <= t:
                    N -= tpF                         # already due (switch rel_shift): release now
                else:
                    dN[stp] -= tpF
                ex_amt[q, 0] = F - tpF
            else:
                ex_amt[q, 0] = F
            ex_step[q, 0] = ts + 61 - rel_shift
            if busy_mode == 1:
                bu = ts + p_tpoff[q] + 1 if p_tpoff[q] >= 0 else ts + 61
            elif p_tpoff[q] >= 0 and tpF >= F - 1e-9 and tp_release:
                bu = ts + p_tpoff[q] + 1
            else:
                bu = ts + 61
            if busy_mode == 0 and a - F > 1e-9 and rem_hold and r_rem > bu:
                bu = r_rem
            if busy_on:
                busy_until[c] = bu
            if not instant and policy != 2:
                win[q] = True
            if not live[q]:
                live[q] = True
                live_ids[nlive] = q
                nlive += 1
        # deeper fills during minute t-1
        for ii in range(nlive):
            q = live_ids[ii]
            if q < 0 or not win[q]:
                continue
            ts = p_t[q]
            for k in range(2):
                if r_state[q, k] != 1 or r_fidx[q, k] < 0:
                    continue
                j = r_fidx[q, k]
                if ts + f_off[j] != t - 1:
                    continue
                usd = r_usd[q, k]
                cap = theta * f_in[j]
                if f_off[j] <= p_scan[q]:
                    cap = min(cap, max(0.0, pool[q] - used[q]))
                F = min(usd, cap)
                used[q] += F
                tpF = 0.0
                if f_tpoff[j] >= 0:
                    tpF = max(0.0, min(F, theta * f_tp[j] - usedtp[q]))
                    usedtp[q] += tpF
                r_F[q, k], r_tpF[q, k] = F, tpF
                r_state[q, k] = 2
                f = t - 1
                N -= F * fee                         # hold (notional + fee) -> position at cost + remainder hold
                rem = (usd - F) * (1 + fee)
                if rem_hold:
                    rr = min(ts + f_scan[j] + 2, f + 16)
                else:
                    rr = t
                pcq = p_close[q] - (rel_shift if p_tpoff[q] >= 0 else 0)
                if rr >= pcq:
                    remc[q, k] = rem                 # cancelled with the deeper window (in _manage)
                elif rr <= t:
                    N -= rem
                else:
                    dN[rr] -= rem
                if tp_release and tpF > 0:
                    stp = f + f_tpoff[j] + 1 - rel_shift
                    if stp <= t:
                        N -= tpF
                    else:
                        dN[stp] -= tpF
                    ex_amt[q, k + 1] = F - tpF
                else:
                    ex_amt[q, k + 1] = F
                ex_step[q, k + 1] = max(t, f + 61 - rel_shift)
        # ================= _manage (ladders in creation order) and _allocate
        H4 = 0.0
        live4 = np.zeros(NC)
        for c in range(NC):
            if alloc_prev[c] > 0 and not filled_prev[c]:
                H4 += alloc_prev[c] * (1 + fee)
                live4[c] = alloc_prev[c]
        for phase in range(2):
            do_manage = (phase == 0) != alloc_first
            if do_manage:
                # ladders in creation order; the engine releases and places ladder by ladder (interleave), the
                # artifact switch releases every ladder first
                for rnd in range(2):
                    if interleave and rnd == 1:
                        break
                    do_rel = interleave or rnd == 0
                    do_pl = interleave or rnd == 1
                    done = np.zeros(nlive, np.bool_)
                    for _ in range(nlive):
                        best, bi = 1 << 62, -1
                        for ii in range(nlive):
                            q = live_ids[ii]
                            if q < 0 or done[ii]:
                                continue
                            key = create[q] if prio_mode == 0 else p_t[q]
                            if key < best:
                                best, bi = key, ii
                        if bi < 0:
                            break
                        done[bi] = True
                        q = live_ids[bi]
                        ts = p_t[q]
                        pcq = p_close[q] - (rel_shift if p_tpoff[q] >= 0 else 0)
                        if do_rel:
                            if win[q] and pcq <= t:                 # window closes: cancel deeper bids
                                for k in range(2):
                                    if r_state[q, k] == 1:
                                        N -= r_usd[q, k] * (1 + fee)
                                        r_state[q, k] = 3
                                    elif r_state[q, k] == 0:
                                        r_state[q, k] = 3
                                    N -= remc[q, k]
                                    remc[q, k] = 0.0
                                win[q] = False
                            for j in range(3):                        # 60-minute time exits
                                if ex_step[q, j] == t:
                                    N -= ex_amt[q, j]
                        if do_pl and win[q] and policy != 2:          # place pending deeper rungs
                            for k in range(2):
                                if r_state[q, k] != 0:
                                    continue
                                if mkt_check and not lvl_ok[q, k, t - ts]:
                                    continue
                                usd = p_want[q]
                                free = Ee - N - H4
                                if policy == 3 and usd * (1 + fee) > free:
                                    while usd * (1 + fee) > free:   # C1a: cancel the lowest-prediction 4-sigma bids
                                        lo_c, lo_p = -1, 1e30
                                        for c2 in range(NC):
                                            if live4[c2] > 0 and M[t - 1, c2] < lo_p:
                                                lo_c, lo_p = c2, M[t - 1, c2]
                                        if lo_c < 0:
                                            break
                                        H4 -= live4[lo_c] * (1 + fee)
                                        free += live4[lo_c] * (1 + fee)
                                        live4[lo_c] = 0.0
                                held = _place(q, k, t, ts, usd, free, fee, dp_start, dp_len, f_off, late_fills,
                                              r_usd, r_place, r_state, r_fidx, r_ncash)
                                N += held
                # drop finished ladders
                for ii in range(nlive):
                    q = live_ids[ii]
                    if q < 0 or win[q]:
                        continue
                    fin = True
                    for j in range(3):
                        if ex_step[q, j] > t:
                            fin = False
                    if fin:
                        live[q] = False
                        live_ids[ii] = -1
                # compact
                m = 0
                for ii in range(nlive):
                    if live_ids[ii] >= 0:
                        live_ids[m] = live_ids[ii]
                        m += 1
                for ii in range(m, nlive):
                    live_ids[ii] = -1
                nlive = m
            else:
                # _allocate: free = equity - positions - holds other than the armed 4-sigma bids
                for c in range(NC):
                    alloc[c] = 0.0
                free = Ee - N
                rank = 0
                for i in range(ncand[t]):
                    c = order[t, i]
                    if t < busy_until[c]:
                        continue
                    want = want4[t, c]
                    need = want * (1 + fee)
                    if need <= free:
                        alloc[c] = want
                        free -= need
                    elif free >= 0.5 * need:
                        alloc[c] = 0.999 * free / (1 + fee)
                        free = 0.0
                    else:
                        cash_short += 1
                    if alloc[c] > 0 and alloc_prev[c] <= 0:
                        arm_key[c] = t * 64 + rank           # a new ladder: dict order = time, then plan order
                    rank += 1
                if alloc_first:
                    # deeper placement then sees these bids as held
                    H4 = 0.0
                    for c in range(NC):
                        H4 += alloc[c] * (1 + fee)
        # ================= parents filling during minute t
        for c in range(NC):
            filled_now[c] = False
            fq_now[c] = -1
        while qptr < NP and p_t[qptr] < t:
            qptr += 1
        q = qptr
        while q < NP and p_t[q] == t:
            c = p_c[q]
            if alloc[c] > 0 or policy == 2:
                a = alloc[c] if policy != 2 else p_want[q]
                a4[q] = a
                F = min(a, theta * p_in[q])
                tpF = 0.0
                if p_tpoff[q] >= 0:
                    tpF = max(0.0, min(F, theta * p_tp[q]))
                F4[q], tpF4[q] = F, tpF
                pool[q], used[q], usedtp[q] = theta * p_in[q], F, tpF
                create[q] = arm_key[c]
                why4[q] = 0
                filled_now[c] = True
                fq_now[c] = q
            elif busy_on and t < busy_until[c]:
                why4[q] = 1
            else:
                incand = False
                for i in range(ncand[t]):
                    if order[t, i] == c:
                        incand = True
                why4[q] = 2 if incand else 3
            q += 1
        if policy == 2:
            # research timing, unlimited cash: deeper rungs rest from the parent's minute (instant bound) or from the
            # next minute with a first trade-through in the parent's minute dropped (the research's minute bound)
            for c in range(NC):
                if not filled_now[c]:
                    continue
                q = fq_now[c]
                win[q] = True
                for k in range(2):
                    st, ln = dp_start[q, k], dp_len[q, k]
                    r_usd[q, k] = p_want[q]
                    r_state[q, k] = 1
                    r_place[q, k] = t
                    if ln > 0 and (instant or f_off[st] >= 1):
                        r_fidx[q, k] = st
        elif instant:
            # the live 1-second poll: rungs of parents filled in minute t go out within a second, from the cash the
            # 4-sigma allocation left (newly filled ladders first, then every pending rung, creation order)
            freei = Ee - N
            live4 = alloc.copy()
            for c in range(NC):
                freei -= alloc[c] * (1 + fee)
            newl = np.zeros(NP, np.bool_)
            for c in range(NC):
                if filled_now[c]:
                    q = fq_now[c]
                    live4[c] = 0.0
                    freei += F4[q] * fee
                    win[q] = True
                    newl[q] = True
                    if not live[q]:
                        live[q] = True
                        live_ids[nlive] = q
                        nlive += 1
            done = np.zeros(nlive, np.bool_)
            for passn in range(2):
                if passn == 1 and (not inst_new_first or not inst_retry_old):
                    break
                for _ in range(nlive):
                    best, bi = 1 << 62, -1
                    for ii in range(nlive):
                        q = live_ids[ii]
                        if q < 0 or done[ii] or not win[q]:
                            continue
                        if (inst_new_first or not inst_retry_old) and passn == 0 and not newl[q]:
                            continue
                        key = create[q] if prio_mode == 0 else p_t[q]
                        if key < best:
                            best, bi = key, ii
                    if bi < 0:
                        break
                    done[bi] = True
                    q = live_ids[bi]
                    ts = p_t[q]
                    if p_close[q] - (rel_shift if p_tpoff[q] >= 0 else 0) <= t:
                        continue
                    for k in range(2):
                        if r_state[q, k] != 0:
                            continue
                        if mkt_check and ts != t and not lvl_ok[q, k, t - ts]:
                            continue
                        usd = p_want[q]
                        if policy == 3 and usd * (1 + fee) > freei:
                            while usd * (1 + fee) > freei:
                                lo_c, lo_p = -1, 1e30
                                for c2 in range(NC):
                                    if live4[c2] > 0 and M[t, c2] < lo_p:
                                        lo_c, lo_p = c2, M[t, c2]
                                if lo_c < 0:
                                    break
                                freei += live4[lo_c] * (1 + fee)
                                live4[lo_c] = 0.0
                        held = _place(q, k, t, ts, usd, freei, fee, dp_start, dp_len, f_off, late_fills, r_usd,
                                      r_place, r_state, r_fidx, r_ncash)
                        freei -= held
                        N += held
        for c in range(NC):
            alloc_prev[c] = alloc[c]
            filled_prev[c] = filled_now[c]
            fq_prev[c] = fq_now[c]
    return a4, F4, tpF4, why4, r_state, r_usd, r_fidx, r_F, r_tpF, r_place, r_ncash, cash_short


_core = nb.njit(cache=True)(_core)


def replay(A, theta=0.5, C=250e3, bound="minute", policy="engine", busy_on=True, rem_hold=True, tp_release=True,
           late_fills=True, inst_new_first=True, prio_mode=0, alloc_first=False, rel_shift=0, busy_mode=0,
           mkt_check=True, inst_retry_old=True, interleave=True):
    dp = A["dp"]
    res = _core(A["T"], A["NC"], A["order"], A["ncand"], A["want4"], A["M"], A["NP"], A["p_t"], A["p_c"], A["p_in"],
                A["p_scan"], A["p_tpoff"], A["p_tp"], A["p_want"], A["p_close"], A["dp_start"], A["dp_len"],
                A["lvl_ok"], dp["off"], dp["inn"], dp["scan"], dp["tpoff"], dp["tp"], float(C), float(theta), FEE_M,
                bound == "instant", POL[policy], busy_on and policy != "research", rem_hold, tp_release, late_fills,
                inst_new_first, prio_mode, alloc_first, rel_shift, busy_mode, mkt_check, inst_retry_old, interleave)
    keys = ("a4", "F4", "tpF4", "why4", "r_state", "r_usd", "r_fidx", "r_F", "r_tpF", "r_place", "r_ncash",
            "cash_short")
    return dict(zip(keys, res))


def to_frame(A, R):
    """Tranche rows for fsim.evaluate: funded size as `mult`; a late deeper fill takes the quantities of the
    trade-through it fills on (deep paths)."""
    W = A["W"]
    Q = W.copy()
    Q["mult"] = 0.0
    pr = A["p_row"]
    dp = A["dp"]
    wf = A["p_want"]
    mult = np.zeros(len(Q))
    pos = {ix: i for i, ix in enumerate(Q.index)}
    cols = {c: Q[c].to_numpy().copy() for c in ("f_off", "in_spot", "scan_off", "tp_off", "tp_spot", "g60", "g_tp",
                                                 "tp_hit", "filled")}
    cols["filled"] = cols["filled"].astype(bool)
    cols["tp_hit"] = cols["tp_hit"].astype(object)
    for q in range(A["NP"]):
        i0 = pos[pr[q, 0]]
        mult[i0] = R["a4"][q] / wf[q] if wf[q] > 0 else 0.0
        for kk in range(2):
            i = pos[pr[q, kk + 1]]
            j = R["r_fidx"][q, kk]
            if R["r_state"][q, kk] == 2 and j >= 0 and R["r_usd"][q, kk] > 0:
                mult[i] = R["r_usd"][q, kk] / wf[q]
                cols["filled"][i] = True
                cols["f_off"][i] = dp["off"][j]
                cols["in_spot"][i] = dp["inn"][j]
                cols["scan_off"][i] = dp["scan"][j]
                cols["tp_off"][i] = dp["tpoff"][j]
                cols["tp_spot"][i] = dp["tp"][j]
                cols["g60"][i] = dp["g60"][j]
                cols["g_tp"][i] = dp["gtp"][j]
                cols["tp_hit"][i] = dp["tpoff"][j] >= 0
            else:
                mult[i] = 0.0
    for c, v in cols.items():
        Q[c] = v
    Q["filled"] = Q["filled"].astype(bool)
    Q["mult"] = mult
    return Q


def evaluate_live(A, R, theta, C, era, cost_mult=1.0):
    Q = to_frame(A, R)
    lo, hi = fsim.ERAS[era][1]
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    Qo, d, info = fsim.evaluate(Q, theta=theta, C=C, days=days, drop_same_minute=False,
                                hs_bp=fsim.HS_BP * cost_mult, impact_y=fsim.IMPACT_Y * cost_mult)
    idx = pd.date_range(lo, hi, freq="D")
    return d.reindex(idx, fill_value=0.0) / C, Qo, info


def check_fills(A, R, Qo, theta):
    """My replay's fill sizes must equal fsim's (fsim recomputes them from the funded sizes)."""
    pr = A["p_row"]
    m = dict(zip(zip(Qo.ts, Qo.coin, Qo.k), Qo.fill))
    par = A["par"]
    worst = 0.0
    for q, r in enumerate(par.itertuples()):
        f = m.get((r.ts, r.coin, 4.0), 0.0)
        worst = max(worst, abs(f - R["F4"][q]))
        for kk, k in enumerate((6.0, 8.0)):
            f = m.get((r.ts, r.coin, k), 0.0)
            mine = R["r_F"][q, kk] if R["r_state"][q, kk] == 2 else 0.0
            worst = max(worst, abs(f - mine))
    return worst


def book(tag, era, theta=0.5, C=250e3, today=False, cost_mult=1.0, policy="engine", A=None, detail=False, **kw):
    """Daily returns on capital, 1-second blend: minute + s x (instant - minute)."""
    if A is None:
        A = era_arrays(tag, era, theta, C, today)
    out = {}
    for bound in ("minute", "instant"):
        R = replay(A, theta=theta, C=C, bound=bound, policy=policy, **kw)
        d, Qo, info = evaluate_live(A, R, theta, C, era, cost_mult)
        out[bound] = (d, R, Qo, info)
    s = fsim.lat_share(era, theta)
    d1 = out["minute"][0] + s * (out["instant"][0] - out["minute"][0])
    return (d1, out, A) if detail else d1


if __name__ == "__main__":
    t0 = time.time()
    for era in ("chk",):
        tag = fsim.ERAS[era][0]
        A = era_arrays(tag, era, 0.5, 250e3, False)
        print("arrays", round(time.time() - t0, 1), "s")
        for pol in ("research", "engine"):
            d1, out, _ = book(tag, era, policy=pol, A=A, detail=True)
            st = fsim.stats(d1, 250e3, era)
            print(era, pol, round(st["ret_yr"], 4), round(st["sharpe"], 3), round(time.time() - t0, 1), "s")
