"""Queue-aware maker simulator on top-of-book quotes + trades (rules in reports/maker_prereg.md).

One call simulates one coin for one day and one configuration. Our orders are post-only limits that
join the best bid / ask we observe (after market-data latency); they reach the book after order
latency; they fill from trades at our price once the queue ahead of us is gone, from trades through
our price, or in full when the opposite best reaches our price. Our orders never move the market.

Inventory target by mode (E = expected 15-minute relative return in bp, q = position in USD):
  0  symmetric       bid while q < Q, ask while q > -Q
  1  skewed          q* = Q clip(E/E_ref); bid while q < q* + Q/2; ask while q > q* - Q/2
  2  passive track   same q*; bid only while q < q* - Q/10; ask only while q > q* + Q/10
Queue model: 0 risk-averse (only trades move us up, plus a cap at the displayed size);
             1 proportional (unexplained size drops are cancels spread evenly through the queue).
"""
import numpy as np
from numba import njit

INF = np.int64(4_000_000_000_000_000_000)
NSLOT = 4
MIN_USD = 50.0


@njit(cache=True)
def _fill(nf, f_t, f_side, f_px, f_qty, f_kind, t, side, px, qty, kind):
    if nf < f_t.shape[0]:
        f_t[nf] = t
        f_side[nf] = side
        f_px[nf] = px
        f_qty[nf] = qty
        f_kind[nf] = kind
    return nf + 1


@njit(cache=True)
def simulate(qt, qbp, qbs, qap, qas, tt, tside, tpx, tsz, st, sE,
             lat_md, lat_ord, throttle, quote_usd, qmax, mode, eref, qmodel, day_start, max_fills):
    nq, nt, ns = qt.shape[0], tt.shape[0], st.shape[0]
    act = np.zeros((2, NSLOT), np.bool_)
    live = np.zeros((2, NSLOT), np.bool_)
    cxl = np.zeros((2, NSLOT), np.bool_)
    spx = np.zeros((2, NSLOT))
    rem = np.zeros((2, NSLOT))
    A = np.zeros((2, NSLOT))
    tlive = np.full((2, NSLOT), INF, np.int64)
    tcxl = np.full((2, NSLOT), INF, np.int64)
    hint = np.zeros((2, NSLOT))
    lastL = np.full((2, NSLOT), -1.0)
    tsince = np.zeros((2, NSLOT))
    last_send = np.full(2, -INF, np.int64)

    f_t = np.zeros(max_fills, np.int64)
    f_side = np.zeros(max_fills, np.int8)
    f_px = np.zeros(max_fills)
    f_qty = np.zeros(max_fills)
    f_kind = np.zeros(max_fills, np.int8)
    nf = 0
    msgs = np.zeros(86_401, np.int32)
    n_new = 0
    n_cxl = 0
    n_rej = 0
    q = 0.0

    bb, bbs, ba, bas = np.nan, 0.0, np.nan, 0.0     # true book
    i = 0
    j = 0
    d1 = 0
    d2 = 0
    obs = -1
    sig = -1
    while True:
        t_t = tt[j] if j < nt else INF
        t_q = qt[i] if i < nq else INF
        t_o = qt[d1] + lat_md if d1 < nq else INF
        t_s = st[d2] + lat_md if d2 < ns else INF
        t_a = INF
        for s in range(2):
            for k in range(NSLOT):
                if act[s, k]:
                    if not live[s, k]:
                        if tlive[s, k] < t_a:
                            t_a = tlive[s, k]
                    elif cxl[s, k] and tcxl[s, k] < t_a:
                        t_a = tcxl[s, k]
        tmin = min(t_t, t_q, t_a, t_o, t_s)
        if tmin == INF:
            break

        if t_t == tmin:                                    # ---- market trade
            sd = tside[j]
            p = tpx[j]
            x = tsz[j]
            j += 1
            if sd == 0:
                continue
            ms = 0 if sd < 0 else 1                        # taker sell hits our bid (0), buy hits our ask (1)
            for k in range(NSLOT):
                if not (act[ms, k] and live[ms, k]):
                    continue
                b = spx[ms, k]
                at = p == b
                through = (p < b) if ms == 0 else (p > b)
                fq = 0.0
                kind = 0
                if at:
                    tsince[ms, k] += x
                    if A[ms, k] >= x:
                        A[ms, k] -= x
                    else:
                        fq = min(rem[ms, k], x - A[ms, k])
                        A[ms, k] = 0.0
                elif through:
                    fq = min(rem[ms, k], x)
                    A[ms, k] = 0.0
                    kind = 1
                if fq > 0.0:
                    nf = _fill(nf, f_t, f_side, f_px, f_qty, f_kind, tmin, ms, b, fq, kind)
                    rem[ms, k] -= fq
                    q += fq if ms == 0 else -fq
                    if rem[ms, k] <= 1e-12:
                        act[ms, k] = False
            continue

        if t_q == tmin:                                    # ---- true top-of-book change
            bb, bbs, ba, bas = qbp[i], qbs[i], qap[i], qas[i]
            i += 1
            for ms in range(2):
                for k in range(NSLOT):
                    if not (act[ms, k] and live[ms, k]):
                        continue
                    b = spx[ms, k]
                    same = bb if ms == 0 else ba
                    ssz = bbs if ms == 0 else bas
                    opp = ba if ms == 0 else bb
                    crossed = (opp <= b) if ms == 0 else (opp >= b)
                    if crossed:
                        fq = rem[ms, k]
                        nf = _fill(nf, f_t, f_side, f_px, f_qty, f_kind, tmin, ms, b, fq, 2)
                        q += fq if ms == 0 else -fq
                        rem[ms, k] = 0.0
                        act[ms, k] = False
                        continue
                    if same == b:
                        if qmodel == 1 and lastL[ms, k] >= 0.0:
                            base = lastL[ms, k] - tsince[ms, k]
                            dec = base - ssz
                            if dec > 0.0 and base > 0.0:
                                A[ms, k] -= dec * A[ms, k] / base
                                if A[ms, k] < 0.0:
                                    A[ms, k] = 0.0
                        if A[ms, k] > ssz:
                            A[ms, k] = ssz
                        lastL[ms, k] = ssz
                        tsince[ms, k] = 0.0
                    elif (same < b) if ms == 0 else (same > b):
                        A[ms, k] = 0.0                     # our level emptied: we are alone at the front
                        lastL[ms, k] = 0.0
                        tsince[ms, k] = 0.0
                    else:
                        lastL[ms, k] = -1.0                # behind the touch: size at our price unknown
            continue

        if t_a == tmin:                                    # ---- our order or cancel reaches the book
            for ms in range(2):
                for k in range(NSLOT):
                    if not act[ms, k]:
                        continue
                    if (not live[ms, k]) and tlive[ms, k] == tmin:
                        b = spx[ms, k]
                        opp = ba if ms == 0 else bb
                        same = bb if ms == 0 else ba
                        ssz = bbs if ms == 0 else bas
                        if np.isnan(opp) or ((b >= opp) if ms == 0 else (b <= opp)):
                            act[ms, k] = False             # post-only reject
                            n_rej += 1
                            continue
                        live[ms, k] = True
                        tsince[ms, k] = 0.0
                        if same == b:
                            A[ms, k] = ssz
                            lastL[ms, k] = ssz
                        elif (b > same) if ms == 0 else (b < same):
                            A[ms, k] = 0.0
                            lastL[ms, k] = 0.0
                        else:
                            A[ms, k] = hint[ms, k]
                            lastL[ms, k] = -1.0
                    elif live[ms, k] and cxl[ms, k] and tcxl[ms, k] == tmin:
                        act[ms, k] = False
            continue

        # ---- decision (observed book change or signal tick)
        if t_o == tmin:
            obs = d1
            d1 += 1
        else:
            sig = d2
            d2 += 1
        if obs < 0:
            continue
        ob, obs_b, oa, obs_a = qbp[obs], qbs[obs], qap[obs], qas[obs]
        if not (oa > ob):
            continue
        mid = 0.5 * (ob + oa)
        E = sE[sig] if sig >= 0 else 0.0
        qn = q * mid
        if mode == 0:
            tgt = 0.0
        else:
            z = E / eref
            if z > 1.0:
                z = 1.0
            elif z < -1.0:
                z = -1.0
            tgt = qmax * z
        for ms in range(2):
            if ms == 0:
                room = qmax - qn
                if mode == 0:
                    ok = qn < qmax
                elif mode == 1:
                    ok = qn < tgt + 0.5 * qmax
                else:
                    ok = qn < tgt - 0.1 * qmax
                px = ob
                hsz = obs_b
            else:
                room = qmax + qn
                if mode == 0:
                    ok = qn > -qmax
                elif mode == 1:
                    ok = qn > tgt - 0.5 * qmax
                else:
                    ok = qn > tgt + 0.1 * qmax
                px = oa
                hsz = obs_a
            size_usd = min(quote_usd, room)
            if size_usd < MIN_USD:
                ok = False
            keep = False
            for k in range(NSLOT):
                if act[ms, k] and not cxl[ms, k]:
                    if ok and (not keep) and spx[ms, k] == px and rem[ms, k] * px <= size_usd + 1.0:
                        keep = True
                    else:
                        cxl[ms, k] = True                   # cancels are never throttled
                        tcxl[ms, k] = tmin + lat_ord
                        n_cxl += 1
                        sec = (tmin - day_start) // 1_000_000
                        if 0 <= sec < 86_401:
                            msgs[sec] += 1
            if ok and not keep and tmin - last_send[ms] >= throttle:
                for k in range(NSLOT):
                    if not act[ms, k]:
                        act[ms, k] = True
                        live[ms, k] = False
                        cxl[ms, k] = False
                        spx[ms, k] = px
                        rem[ms, k] = size_usd / px
                        A[ms, k] = 0.0
                        tlive[ms, k] = tmin + lat_ord
                        tcxl[ms, k] = INF
                        hint[ms, k] = hsz
                        lastL[ms, k] = -1.0
                        tsince[ms, k] = 0.0
                        last_send[ms] = tmin
                        n_new += 1
                        sec = (tmin - day_start) // 1_000_000
                        if 0 <= sec < 86_401:
                            msgs[sec] += 1
                        break
    m = min(nf, max_fills)
    return (f_t[:m], f_side[:m], f_px[:m], f_qty[:m], f_kind[:m], nf, q, n_new, n_cxl, n_rej, msgs)
