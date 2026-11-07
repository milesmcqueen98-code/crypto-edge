#!/usr/bin/env python3
"""H3 (LM): bids beyond estimated liquidation clusters (reports/hunt/h3lm/SPEC.md, reports/hunt_prereg.md).

Modes (run from the repo root; heavy modes run on GitHub Actions):
  python scripts/hunt/h3lm/lm.py dev               DEV grid: 8 density configs + their 8 depth-matched controls.
                                                   Loads no minute at or after 2026-06-01 (HOLD0): it cannot touch HOLD.
  python scripts/hunt/h3lm/lm.py full              the frozen variant (reports/hunt/h3lm/frozen.json) on all scored days.
                                                   Refuses to run without frozen.json.
  python scripts/hunt/h3lm/lm.py smoke COIN        mechanics check on 2024 data (never scored); prints counts only.

The estimate (fixed by the SPEC), hourly at the top of hour h with minutes <= h-1:
  - entries: every minute's (typical price, volume) on Coinbase spot, plus Coinbase perp volume (coins) from launch,
    over the trailing N days, decayed with a 3-day half-life;
  - survival per leverage tier L in {10, 20, 50} (weights 0.5/0.3/0.2, maintenance m = 0.5%): an entry at e survives
    while no later spot minute (up to h-1) traded at or below e * (1 - 1/L + m);
  - density D(b) = sum of surviving entries x tier weight, in 0.25% log-price buckets of the liquidation price;
  - cluster = the max-D bucket whose centre lies inside the depth range R below the current spot price; bid at the
    centre of the next bucket down (0.25% below), rounded down to the tick grid; replaced every hour; cancelled for
    the rest of the hour once a minute trades below the cluster bucket without filling us.
Venue facts from research memo R3 (coordinator deviation, applied before any result was seen):
  - Fair Value Limit: a perp order more than 5% from spot is rejected, so the bid must sit within 5% of the spot
    price at placement: cluster centres deeper than -ln(0.95) - 0.25% are not eligible (same cap in every era);
  - a +-10% move from the hourly reference price (the hour's first open) halts matching for 2 minutes;
  - perps halt Friday 5-6 PM ET: no bid in that hour, no fills or exits in it (every era);
  - fee sensitivity at $0.12 and $0.30 per contract (descriptive; the gates keep $0.20).
Trades: post-only bid fills if the minute opened above it and traded through it by one tick (perp tick grid; the
pre-launch era is spot-priced with perp costs and perp ticks); size <= theta x through-volume (candle volume spread
over its range, while the price stays below the bid, <= 15 minutes); whole contracts; take-profit post-only at 50% of
the way back to the venue price at placement (one-tick trade-through, size <= theta x volume above it); otherwise a
market exit at the open of the first tradable minute H minutes after the fill. No stop. One position per coin, target
notional 1x sleeve capital, gross <= 2x. Costs from scripts/hunt/common.py (1x / 2x).

Mechanism test (pre-committed before any run): for each config, every (coin, hour) with a density bid is an event;
the control bid in the same hour sits at a depth drawn by a fixed-seed permutation of the density bids' depths in
sigma units (sigma = 1-hour spot sigma from 1-minute returns over the trailing 3 days), permuted within blocks of 25
events of adjacent sigma rank (coin x era x config), i.e. the same depth distribution in sigma units (and in percent)
at a random bucket inside R (clipped to R; the clip rate is reported). Each event is simulated alone (unit notional, no capacity cap, 2x costs); net bp = 0
when the bid does not fill. Statistics: (a) the SPEC's paired t of (density - control) per-event net bp over all
events; (b) the same mean with errors clustered by UTC day (daily sums of the paired differences, Newey-West 5 lags,
over DEV days with events), because hourly events on one cascade day are not independent. A config passes the
mechanism test only if both (a) and (b) are >= 2. Only configs that pass may be selected; if none passes, the idea
stops at the screen and HOLD is never read.
"""
import json
import math
import os
import sys
import time

import numba
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HUNT = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(HUNT))
sys.path.insert(0, HUNT)
import common  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h3lm")
COINS = ["BTC", "ETH", "SOL", "XRP"]
DELTA = 0.0025                                   # bucket width, log price
HL_MIN = 3 * 1440                                # decay half-life (minutes)
TIERS = ((10, 0.5), (20, 0.3), (50, 0.2))
MAINT = 0.005
LOGK = np.log(np.array([1.0 - 1.0 / L + MAINT for L, _ in TIERS]))
WT = np.array([w for _, w in TIERS])
FVL_D = -math.log(1 - 0.05)                      # bid depth cap (R3 Fair Value Limit)
CL_CAP = FVL_D - DELTA                           # deepest eligible cluster centre
D_UNION = (-math.log(1 - 0.015), CL_CAP)          # histogram range covering every R after the cap
NB = 24
GRID_N = (7, 14)
GRID_R = ((0.015, 0.05), (0.03, 0.10))
GRID_H = (60, 240)
THETA = 0.5
SIG_W = 4320
HALT_PCT = 0.10
ERAS = {"early": ("2021-12-01", "2024-01-01", "minute_early"), "main": ("2024-12-01", "2026-11-06", "minute")}
SCORED = {"early": ("2022-01-01", "2023-12-31"), "main": ("2025-01-01", "2026-11-05")}
HOLD0 = pd.Timestamp("2026-06-01")
SEED = 20261107
PERM_BLOCK = 25
SWITCH_GAP = 300                                 # no bids in the 5 hours before the spot -> perp venue switch


def cfg_name(N, R, H):
    return f"N{N}_R{int(round(R[0] * 1000)):02d}-{int(round(R[1] * 100)):02d}_H{H}"


def grid():
    return [(N, R, H) for N in GRID_N for R in GRID_R for H in GRID_H]


# ------------------------------------------------------------------------------------------------ kernels
@numba.njit(cache=True)
def next_lower(lo):
    """nl[i] = first j > i with lo[j] < lo[i] (n if none). lo uses +inf for minutes without trades."""
    n = len(lo)
    nl = np.full(n, n, np.int64)
    st = np.empty(n, np.int64)
    top = 0
    for i in range(n - 1, -1, -1):
        while top > 0 and lo[st[top - 1]] >= lo[i]:
            top -= 1
        nl[i] = st[top - 1] if top > 0 else n
        st[top] = i
        top += 1
    return nl


@numba.njit(cache=True)
def death_times(lo, nl, es, ee, logk, maxwin):
    """First minute u > s at which the spot low reached the tier's liquidation price e * k (n = alive)."""
    n = len(lo)
    m = len(es)
    K = len(logk)
    tau = np.full((K, m), n, np.int64)
    for i in range(m):
        s = es[i]
        lim = min(n, s + maxwin)
        for k in range(K):
            x = ee[i] * math.exp(logk[k])
            u = s + 1
            while u < lim:
                if lo[u] <= x:
                    tau[k, i] = u
                    break
                u = nl[u]
    return tau


@numba.njit(cache=True)
def density(hours, lp0, es, lee, ev, tau, logk, wt, nwin, hl, delta, d_lo, d_hi, nb):
    """Liquidation density per hour over the candidate buckets (cluster-centre depth in [d_lo, d_hi] below lp0).
    Uses entries with es <= h - 1 (minutes before the hour) and death times >= h (not yet liquidated at h - 1)."""
    nh = len(hours)
    m = len(es)
    hist = np.zeros((nh, nb))
    bmin = np.zeros(nh, np.int64)
    lo_p = 0
    hi_p = 0
    ln2 = math.log(2.0)
    K = len(logk)
    for j in range(nh):
        h = hours[j]
        while hi_p < m and es[hi_p] < h:
            hi_p += 1
        while lo_p < m and es[lo_p] < h - nwin:
            lo_p += 1
        if not np.isfinite(lp0[j]):
            continue
        b0 = int(math.ceil((lp0[j] - d_hi) / delta - 0.5))
        b1 = int(math.floor((lp0[j] - d_lo) / delta - 0.5))
        bmin[j] = b0
        for i in range(lo_p, hi_p):
            w = ev[i] * math.exp(-ln2 * (h - es[i]) / hl)
            for k in range(K):
                if tau[k, i] >= h:
                    b = int(math.floor((lee[i] + logk[k]) / delta))
                    if b >= b0 and b <= b1 and b - b0 < nb:
                        hist[j, b - b0] += w * wt[k]
    return hist, bmin


@numba.njit(cache=True)
def fill_scan(o, hi, lo, halt, h, bid, edge, tick, n):
    """(fill minute or -1, cancelled flag) for a bid working in minutes h .. h+59."""
    for t in range(h, min(n, h + 60)):
        if halt[t] or not (lo[t] == lo[t]):
            continue
        if o[t] > bid and lo[t] <= bid - tick:
            return t, 0
        if lo[t] < edge:
            return -1, 1
    return -1, 0


@numba.njit(cache=True)
def through_usd(hi, lo, vol, tf, bid, n):
    tot = 0.0
    for j in range(tf, min(n, tf + 16)):
        lj = lo[j]
        if not (lj == lj) or lj >= bid:
            break
        rng = hi[j] - lj
        frac = 1.0 if rng <= 0 else min(1.0, (bid - lj) / rng)
        tot += vol[j] * frac * 0.5 * (bid + lj)
    return tot


@numba.njit(cache=True)
def time_exit(o, halt, t0, n):
    for u in range(t0, n):
        if (not halt[u]) and o[u] == o[u]:
            return u
    return -1


@numba.njit(cache=True)
def cascade_low(lo, tf, n):
    m = np.inf
    for u in range(tf, min(n, tf + 61)):
        if lo[u] == lo[u] and lo[u] < m:
            m = lo[u]
    return m


@numba.njit(cache=True)
def unit_events(o, hi, lo, halt, hs, bids, edges, tps, tick, H):
    """Each event alone, unit notional: fill minute (-1 none, -2 incomplete), exit minute, exit px, type (1 TP,
    2 market), cancelled flag, cascade low (min low over the fill minute and the next 60)."""
    n = len(o)
    m = len(hs)
    tf = np.full(m, -1, np.int64)
    xt = np.full(m, -1, np.int64)
    xp = np.full(m, np.nan)
    typ = np.zeros(m, np.int8)
    canc = np.zeros(m, np.int8)
    clow = np.full(m, np.nan)
    for j in range(m):
        f, c = fill_scan(o, hi, lo, halt, hs[j], bids[j], edges[j], tick, n)
        canc[j] = c
        if f < 0:
            continue
        clow[j] = cascade_low(lo, f, n)
        u_tp = -1
        for u in range(f + 1, min(n, f + H)):
            if halt[u] or not (hi[u] == hi[u]):
                continue
            if hi[u] >= tps[j] + tick:
                u_tp = u
                break
        if u_tp >= 0:
            tf[j], xt[j], xp[j], typ[j] = f, u_tp, tps[j], 1
        else:
            u = time_exit(o, halt, f + H, n)
            if u < 0:
                tf[j] = -2
            else:
                tf[j], xt[j], xp[j], typ[j] = f, u, o[u], 2
    return tf, xt, xp, typ, canc, clow


@numba.njit(cache=True)
def book(o, hi, lo, vol, halt, hs, bids, edges, tps, tick, H, C, theta, csize):
    """One coin, one position at a time. Returns per trade: event idx, fill minute, contracts' coins, coins closed by
    the take-profit, TP completion minute, market-exit minute, exit px, through-volume USD, cascade low."""
    n = len(o)
    m = len(hs)
    ev = np.full(m, -1, np.int64)
    tf_ = np.full(m, -1, np.int64)
    qty = np.zeros(m)
    qtp = np.zeros(m)
    ttp = np.full(m, -1, np.int64)
    txx = np.full(m, -1, np.int64)
    xpx = np.full(m, np.nan)
    inu = np.zeros(m)
    clw = np.full(m, np.nan)
    k = 0
    free_at = -1
    for j in range(m):
        h = hs[j]
        if h <= free_at:
            continue
        bid = bids[j]
        f, c = fill_scan(o, hi, lo, halt, h, bid, edges[j], tick, n)
        if f < 0:
            continue
        usd = through_usd(hi, lo, vol, f, bid, n)
        target = min(C, theta * usd)
        ncon = math.floor(target / (bid * csize) + 1e-9)
        if ncon < 1:
            continue
        q = ncon * csize
        tp = tps[j]
        cum = 0.0
        u_tp = -1
        done = -1
        last_tp = -1
        for u in range(f + 1, min(n, f + H)):
            if halt[u] or not (hi[u] == hi[u]):
                continue
            if u_tp < 0 and hi[u] >= tp + tick:
                u_tp = u
            if u_tp >= 0 and hi[u] > tp:
                rng = hi[u] - lo[u]
                frac = 1.0 if rng <= 0 else min(1.0, (hi[u] - tp) / rng)
                cum += vol[u] * frac
                last_tp = u
                if theta * cum >= q:
                    done = u
                    break
        q_tp = min(q, theta * cum) if u_tp >= 0 else 0.0
        if q_tp < q:
            u = time_exit(o, halt, f + H, n)
            if u < 0:
                break                                  # exit not observable in the loaded data: stop the book
            txx[k], xpx[k] = u, o[u]
            close = u
        else:
            close = done
        ev[k], tf_[k], qty[k], qtp[k] = j, f, q, q_tp
        ttp[k] = done if done >= 0 else last_tp
        inu[k] = usd
        clw[k] = cascade_low(lo, f, n)
        k += 1
        free_at = close
    return ev[:k], tf_[:k], qty[:k], qtp[:k], ttp[:k], txx[:k], xpx[:k], inu[:k], clw[:k]


# ------------------------------------------------------------------------------------------------ data
def _arr(df, col, idx):
    return df[col].reindex(idx).to_numpy(np.float64)


def load_coin(coin, era, end=None):
    """Minute grid with spot, perp (main era) and the merged trading venue (spot before the perp's first full day,
    perp after). end: exclusive cap (DEV passes HOLD0, so no HOLD minute is ever loaded)."""
    start, stop, src = ERAS[era]
    stop = pd.Timestamp(stop)
    if end is not None:
        stop = min(stop, pd.Timestamp(end))
    idx = pd.date_range(start, stop, freq="min", inclusive="left")
    s = common.load_minute(coin, src, start, stop)
    if s is None or len(s) == 0:
        return None
    S = {k: _arr(s, k, idx) for k in ("open", "high", "low", "close")}
    S["vol"] = s["volume"].reindex(idx).fillna(0.0).to_numpy(np.float64)
    S["cf"] = pd.Series(S["close"]).ffill(limit=30).to_numpy()
    P, sw = None, len(idx)
    if era == "main":
        p = common.load_perp(coin)
        if p is not None:
            first = p.index.min()
            p = p[(p.index >= pd.Timestamp(start)) & (p.index < stop)]
            if len(p):
                P = {k: _arr(p, k, idx) for k in ("open", "high", "low", "close")}
                P["vol"] = p["volume"].reindex(idx).fillna(0.0).to_numpy(np.float64)
                P["cf"] = pd.Series(P["close"]).ffill(limit=60).to_numpy()
                swt = (first + pd.Timedelta(days=1)).normalize()
                sw = int(np.searchsorted(idx.values, np.datetime64(swt)))
    V = {}
    for k in ("open", "high", "low", "vol", "cf"):
        a = S[k].copy()
        if P is not None and sw < len(idx):
            a[sw:] = P[k][sw:]
        V[k] = a
    return dict(idx=idx, S=S, P=P, V=V, sw=sw, coin=coin, era=era)


def halt_mask(idx, V):
    """R3: Friday 5-6 PM ET maintenance and 2-minute halts after a +-10% move from the hour's first open."""
    et = idx.tz_localize("UTC").tz_convert("America/New_York")
    fri = np.asarray((et.dayofweek == 4) & (et.hour == 17))
    hour_key = np.asarray(idx.floor("h").asi8)
    ref = pd.Series(V["open"]).groupby(hour_key).transform("first").to_numpy()      # first traded open of the hour
    with np.errstate(invalid="ignore"):
        trig = (V["low"] <= (1 - HALT_PCT) * ref) | (V["high"] >= (1 + HALT_PCT) * ref)
    halt = fri.copy()
    tr = np.nonzero(trig)[0]
    for d in (1, 2):
        j = tr + d
        halt[j[j < len(halt)]] = True
    return halt, fri


def entries(D):
    """(minute, price, volume) of every spot minute and every perp minute (perp volume in coins), time-sorted."""
    S, P = D["S"], D["P"]
    tp = (S["high"] + S["low"] + S["close"]) / 3.0
    ok = np.isfinite(tp) & (S["vol"] > 0)
    es = [np.nonzero(ok)[0]]
    ee = [tp[ok]]
    ev = [S["vol"][ok]]
    if P is not None:
        tpp = (P["high"] + P["low"] + P["close"]) / 3.0
        okp = np.isfinite(tpp) & (P["vol"] > 0)
        es.append(np.nonzero(okp)[0])
        ee.append(tpp[okp])
        ev.append(P["vol"][okp])
    es, ee, ev = np.concatenate(es), np.concatenate(ee), np.concatenate(ev)
    o = np.argsort(es, kind="stable")
    return es[o].astype(np.int64), ee[o], ev[o]


def hour_events(D, scored, nmax):
    """Decision hours on scored days: minute index h (top of hour) with the spot price, sigma and venue price at h-1."""
    idx = D["idx"]
    lo_d, hi_d = pd.Timestamp(scored[0]), pd.Timestamp(scored[1]) + pd.Timedelta(days=1)
    hrs = np.nonzero((idx.minute == 0) & (idx >= lo_d) & (idx < hi_d))[0]
    hrs = hrs[(hrs >= 1) & (hrs < nmax)]
    S, V = D["S"], D["V"]
    p0 = S["cf"][hrs - 1]
    r1 = np.diff(np.log(S["cf"]), prepend=np.nan)
    sig = pd.Series(r1).rolling(SIG_W, min_periods=1440).std().to_numpy() * math.sqrt(60.0)
    return hrs, p0, sig[hrs - 1], V["cf"][hrs - 1]


# ------------------------------------------------------------------------------------------------ per coin-era
def prepare(coin, era, end, Ns):
    """Density histograms per N for every decision hour (the expensive part)."""
    t0 = time.time()
    D = load_coin(coin, era, end)
    if D is None:
        return None
    n = len(D["idx"])
    lo_k = np.where(np.isfinite(D["S"]["low"]), D["S"]["low"], np.inf)
    nl = next_lower(lo_k)
    es, ee, ev = entries(D)
    maxwin = max(Ns) * 1440 + 120
    tau = death_times(lo_k, nl, es, ee, LOGK, maxwin)
    del nl, lo_k
    hrs, p0, sig, vpx = hour_events(D, SCORED[era], n)
    lp0 = np.log(p0)
    lee = np.log(ee)
    H = {}
    for N in Ns:
        hist, bmin = density(hrs, lp0, es, lee, ev, tau, LOGK, WT, N * 1440, float(HL_MIN), DELTA,
                             D_UNION[0], D_UNION[1], NB)
        H[N] = (hist, bmin)
    halt, fri = halt_mask(D["idx"], D["V"])
    cnt = np.concatenate([[0], np.cumsum(np.isfinite(D["S"]["close"]))])
    D.update(hrs=hrs, p0=p0, lp0=lp0, sig=sig, vpx=vpx, H=H, halt=halt, fri=fri, n_entries=len(es), cnt=cnt)
    D["secs_prep"] = time.time() - t0
    return D


def pick_cluster(hist, bmin, lp0, R):
    d_lo = -math.log(1 - R[0])
    d_hi = min(-math.log(1 - R[1]), CL_CAP)
    k = np.arange(hist.shape[1])
    depth = lp0[:, None] - (bmin[:, None] + k[None, :] + 0.5) * DELTA
    ok = (depth >= d_lo - 1e-12) & (depth <= d_hi + 1e-12)
    Hm = np.where(ok, hist, -1.0)
    kb = Hm.argmax(axis=1)
    mx = Hm.max(axis=1)
    return bmin + kb, mx > 0, d_lo, d_hi


def bids_for(D, N, R, coin_i, era_i, cfg_i):
    """Density and control bids (venue prices) for every valid decision hour of one config."""
    hist, bmin = D["H"][N]
    lp0, sig, hrs = D["lp0"], D["sig"], D["hrs"]
    b, has, d_lo, d_hi = pick_cluster(hist, bmin, lp0, R)
    coin = D["coin"]
    size, tick = common.PERP[coin][1], common.PERP[coin][2]
    sw = D["sw"]
    vpx = D["vpx"]
    basis = vpx / D["p0"]
    with np.errstate(invalid="ignore"):
        okc = np.nan_to_num(vpx * size) >= common.MIN_CONTRACT_USD          # perp universe rule (>= $150 contract)
    valid = has & np.isfinite(lp0) & np.isfinite(sig) & (sig > 0) & np.isfinite(basis) & okc
    cnt = D["cnt"]                                                          # a full N-day history (XRP relisting):
    a0 = np.clip(hrs - N * 1440, 0, len(cnt) - 1)                           # spot trades in the first day of the
    a1 = np.clip(hrs - N * 1440 + 1440, 0, len(cnt) - 1)                    # trailing window
    valid &= (hrs - N * 1440 >= 0) & (cnt[a1] - cnt[a0] > 0)
    valid &= ~D["fri"][hrs]
    valid &= ~((hrs >= sw - SWITCH_GAP) & (hrs < sw))
    j = np.nonzero(valid)[0]
    lbid_d = (b[j] - 0.5) * DELTA                      # log spot price of the density bid (centre of bucket b-1)
    ledge_d = b[j] * DELTA                              # lower edge of the cluster bucket
    dep_d = lp0[j] - lbid_d
    z = dep_d / sig[j]
    rng = np.random.default_rng([SEED, coin_i, era_i, cfg_i])
    zc = np.empty_like(z)
    order = np.argsort(sig[j], kind="stable")                   # permute within blocks of PERM_BLOCK events of
    for a in range(0, len(order), PERM_BLOCK):                  # adjacent sigma rank: the control matches the
        ii = order[a:a + PERM_BLOCK]                            # density depths in sigma units and in percent
        zc[ii] = z[ii[rng.permutation(len(ii))]]
    raw_c = zc * sig[j]
    dep_c = np.clip(raw_c, d_lo + DELTA, d_hi + DELTA)
    clip_rate = float(np.mean((raw_c < d_lo + DELTA) | (raw_c > d_hi + DELTA))) if len(z) else float("nan")
    bb = np.round((lp0[j] - dep_c) / DELTA - 0.5)
    bb = np.where(lp0[j] - (bb + 0.5) * DELTA > d_hi + DELTA + 1e-12, bb + 1, bb)
    bb = np.where(lp0[j] - (bb + 0.5) * DELTA < d_lo + DELTA - 1e-12, bb - 1, bb)
    lbid_c = (bb + 0.5) * DELTA
    ledge_c = (bb + 1) * DELTA
    out = {}
    for name, lb, le in (("dens", lbid_d, ledge_d), ("ctrl", lbid_c, ledge_c)):
        bs = np.exp(lb) * basis[j]
        bid = np.floor(bs / tick + 1e-9) * tick
        bid = np.maximum(bid, np.ceil(0.95 * D["p0"][j] / tick - 1e-9) * tick)     # R3 Fair Value Limit (5%)
        edge = np.exp(le) * basis[j]
        tp = bid + 0.5 * (vpx[j] - bid)
        tp = np.floor(tp / tick + 1e-9) * tick
        ok = (bid > 0) & (tp > bid)
        out[name] = dict(j=j[ok], h=hrs[j][ok], bid=bid[ok], edge=edge[ok], tp=tp[ok], depth=(lp0[j] - lb)[ok],
                         sig=sig[j][ok], vpx=vpx[j][ok])
    # same hours for both arms
    common_h = np.intersect1d(out["dens"]["h"], out["ctrl"]["h"])
    for name in out:
        m = np.isin(out[name]["h"], common_h)
        out[name] = {k: v[m] for k, v in out[name].items()}
    return out, dict(size=size, tick=tick, clip_rate=clip_rate)


def _ts(idx, a):
    """Timestamps for minute positions a (NaT where a < 0)."""
    a = np.asarray(a, np.int64)
    v = idx.values.astype("datetime64[ns]")[np.maximum(a, 0)].copy() if len(a) else np.array([], "datetime64[ns]")
    if len(a):
        v[a < 0] = np.datetime64("NaT", "ns")
    return pd.DatetimeIndex(v)


def unit_table(D, B, spec, H, mult=2.0):
    V, halt = D["V"], D["halt"]
    coin = D["coin"]
    tf, xt, xp, typ, canc, clow = unit_events(V["open"], V["high"], V["low"], halt, B["h"], B["bid"], B["edge"],
                                              B["tp"], spec["tick"], H)
    filled = tf >= 0
    e = B["bid"]
    g = np.where(filled, (xp / e - 1.0) * 1e4, 0.0)
    hours = np.where(filled, (xt - tf) / 60.0, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        c_in = common.perp_cost_bp(coin, e, taker=False, mult=mult)
        c_out = np.where(typ == 1, common.perp_cost_bp(coin, np.where(filled, xp, e), taker=False, mult=mult),
                         common.perp_cost_bp(coin, np.where(filled, xp, e), taker=True, mult=mult))
    net = np.where(filled, g - c_in - c_out - common.perp_funding_bp(hours, mult), 0.0)
    cf = D["S"]["cf"]
    h = B["h"]
    h_end = np.minimum(h + 59, len(cf) - 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        hr_ret = np.log(cf[h_end] / cf[h - 1]) * 1e4                     # spot return over the bid's hour (bp)
    T = pd.DataFrame(dict(h=h, ts=D["idx"][h], filled=filled, incomplete=tf == -2, tp=typ == 1,
                          cancel=canc.astype(bool), gross=g, net=net, depth=B["depth"], sig=B["sig"],
                          hr_ret_bp=hr_ret, low_dist_bp=np.where(filled, (e / clow - 1) * 1e4, np.nan)))
    return T[~T.incomplete]


def trades_table(D, B, spec, H, C, theta):
    V, halt = D["V"], D["halt"]
    ev, tf, q, qtp, ttp, tx, xpx, inu, clw = book(V["open"], V["high"], V["low"], V["vol"], halt, B["h"], B["bid"],
                                                  B["edge"], B["tp"], spec["tick"], H, float(C), theta, spec["size"])
    idx = D["idx"]
    T = pd.DataFrame(dict(coin=D["coin"], h_ts=_ts(idx, B["h"][ev]), fill_ts=_ts(idx, tf), bid=B["bid"][ev],
                          tp=B["tp"][ev], vpx=B["vpx"][ev], depth=B["depth"][ev], sig=B["sig"][ev], qty=q, q_tp=qtp,
                          tp_ts=_ts(idx, ttp), x_ts=_ts(idx, tx), x_px=xpx, in_usd=inu, low=clw,
                          venue=np.where(tf >= D["sw"], "perp", "spot")))
    T["tp_ts"] = T.tp_ts.where(T.q_tp > 0)
    T["notional"] = T.qty * T.bid
    return T


def pnl(T, mult=2.0, fee=None):
    """USD P&L per trade part, booked on each part's exit day. Returns a Series by day."""
    if len(T) == 0:
        return pd.Series(dtype=float)
    old = common.PERP_FEE_USD
    if fee is not None:
        common.PERP_FEE_USD = fee
    try:
        out = []
        for coin, g in T.groupby("coin"):
            e = g.bid.to_numpy()
            n = g.notional.to_numpy()
            qtp = g.q_tp.to_numpy()
            qr = g.qty.to_numpy() - qtp
            tp = g.tp.to_numpy()
            xp = g.x_px.to_numpy()
            c_in = n * common.perp_cost_bp(coin, e, taker=False, mult=mult) / 1e4
            h_tp = ((g.tp_ts - g.fill_ts).dt.total_seconds() / 3600).fillna(0).to_numpy()
            h_r = ((g.x_ts - g.fill_ts).dt.total_seconds() / 3600).fillna(0).to_numpy()
            fund = common.perp_funding_bp(1.0, mult) / 1e4
            p_tp = qtp * (tp - e) - qtp * tp * common.perp_cost_bp(coin, tp, taker=False, mult=mult) / 1e4 \
                - qtp * e * fund * h_tp
            xpf = np.where(qr > 0, xp, e)
            p_r = qr * (xpf - e) - qr * xpf * common.perp_cost_bp(coin, xpf, taker=True, mult=mult) / 1e4 \
                - qr * e * fund * h_r
            p_r = np.where(qr > 0, p_r, 0.0)
            d_tp = g.tp_ts.dt.floor("D")
            d_r = g.x_ts.dt.floor("D").where(qr > 0, d_tp)
            out.append(pd.Series(np.where(qtp > 0, p_tp, 0.0), index=d_tp.fillna(d_r).to_numpy()))
            out.append(pd.Series(p_r - c_in, index=d_r.to_numpy()))
        s = pd.concat(out)
        s = s[s.index.notna()]
        return s.groupby(level=0).sum()
    finally:
        common.PERP_FEE_USD = old


def gross_cap(T, C, cap=2.0):
    """Portfolio gross <= cap x C across coins (positions open from fill to final exit), in fill-time order."""
    if len(T) == 0:
        return T
    T = T.sort_values("fill_ts").reset_index(drop=True)
    close = T.x_ts.fillna(T.tp_ts).to_numpy()
    fills = T.fill_ts.to_numpy()
    scale = np.ones(len(T))
    open_ = []
    for i in range(len(T)):
        open_ = [(c, a) for c, a in open_ if c > fills[i]]
        used = sum(a for _, a in open_)
        room = cap * C - used
        want = T.notional.iat[i]
        if want > room:
            scale[i] = room / want if room > 0.1 * want else 0.0
        open_.append((close[i], want * scale[i]))
    csize = T.coin.map({c: common.PERP[c][1] for c in T.coin.unique()}).to_numpy()
    q_new = np.floor(T.qty.to_numpy() * scale / csize + 1e-9) * csize
    T["q_tp"] = np.minimum(T.q_tp.to_numpy() * scale, q_new)
    T["qty"] = q_new
    T["notional"] = T.qty * T.bid
    return T[T.qty > 0].reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ modes
def scored_days(end=None):
    d = pd.DatetimeIndex(sorted(set().union(*[set(pd.date_range(a, b, freq="D")) for a, b in SCORED.values()])))
    return d if end is None else d[d < pd.Timestamp(end)]


def nw_t(x, lags=5):
    x = np.asarray(x, float)
    n = len(x)
    if n < 3:
        return float("nan")
    xc = x - x.mean()
    v = np.dot(xc, xc) / n
    for k in range(1, lags + 1):
        v += 2 * (1 - k / (lags + 1)) * np.dot(xc[k:], xc[:-k]) / n
    return float(x.mean() / math.sqrt(v / n)) if v > 0 else float("nan")


def run_dev(outdir=None, coins=COINS, quiet=False):
    outdir = outdir or os.path.join(OUT, "dev")
    os.makedirs(outdir, exist_ok=True)
    days = scored_days(HOLD0)
    cfgs = grid()
    caps = ((30000, 0.5), (50000, 0.5), (30000, 0.25))
    trades = {(ci, arm, C, th): [] for ci in range(len(cfgs)) for arm in ("dens", "ctrl") for C, th in caps}
    units = []
    meta = {}
    clips = {}
    for ci_coin, coin in enumerate(coins):
        for ei, era in enumerate(ERAS):
            D = prepare(coin, era, HOLD0, GRID_N)
            if D is None:
                continue
            assert D["idx"][-1] < HOLD0
            meta[f"{coin}|{era}"] = dict(minutes=len(D["idx"]), entries=int(D["n_entries"]), hours=len(D["hrs"]),
                                         switch=str(D["idx"][D["sw"]]) if D["sw"] < len(D["idx"]) else None,
                                         secs=round(D["secs_prep"], 1))
            print(f"{coin} {era}: prep {D['secs_prep']:.1f}s, {len(D['hrs'])} hours, {D['n_entries']} entries", flush=True)
            for ci, (N, R, H) in enumerate(cfgs):
                B, spec = bids_for(D, N, R, ci_coin, ei, ci)
                clips.setdefault(cfg_name(N, R, H), []).append((len(B["dens"]["h"]), spec["clip_rate"]))
                for arm in ("dens", "ctrl"):
                    U = unit_table(D, B[arm], spec, H)
                    U["coin"], U["cfg"], U["arm"] = coin, cfg_name(N, R, H), arm
                    units.append(U)
                    for C, th in caps:
                        trades[(ci, arm, C, th)].append(trades_table(D, B[arm], spec, H, C, th))
            del D
    # ---- per-config outputs (DEV days only)
    U = pd.concat(units, ignore_index=True)
    assert (U.ts < HOLD0).all()
    cols = {}
    T_all = []
    mech = {}
    pooled = {}
    for ci, (N, R, H) in enumerate(cfgs):
        name = cfg_name(N, R, H)
        for arm in ("dens", "ctrl"):
            for C, th in caps:
                T = pd.concat(trades[(ci, arm, C, th)], ignore_index=True)
                T = T[T.x_ts.fillna(T.tp_ts) < HOLD0]
                T = gross_cap(T, C)
                for mult in ((1.0, 2.0) if th == 0.5 else (2.0,)):
                    d = pnl(T, mult).reindex(days).fillna(0.0) / C
                    cols[f"{arm}_{name}|{C}|{th}|{int(mult)}x"] = d
                if C == 30000 and th == 0.5:
                    T = T.copy()
                    T["variant"] = f"{arm}_{name}"
                    T_all.append(T)
        # mechanism test: paired per-event net bp (2x), density vs control, same events
        a = U[(U.cfg == name) & (U.arm == "dens")].set_index(["coin", "h"])
        b = U[(U.cfg == name) & (U.arm == "ctrl")].set_index(["coin", "h"])
        k = a.index.intersection(b.index)
        a, b = a.loc[k], b.loc[k]
        dif = (a.net - b.net).to_numpy()
        day = a.ts.dt.floor("D").to_numpy()
        daily = pd.Series(dif).groupby(day).sum()
        pooled[name] = daily
        naive = float(dif.mean() / (dif.std(ddof=1) / math.sqrt(len(dif)))) if dif.std() > 0 else float("nan")
        mech[name] = dict(n_events=int(len(dif)), n_days=int(len(daily)), dens_fills=int(a.filled.sum()),
                          ctrl_fills=int(b.filled.sum()), dens_net_mean_bp=float(a.net.mean()),
                          ctrl_net_mean_bp=float(b.net.mean()),
                          dens_net_per_fill_bp=float(a.net[a.filled].mean()) if a.filled.any() else None,
                          ctrl_net_per_fill_bp=float(b.net[b.filled].mean()) if b.filled.any() else None,
                          dens_gross_per_fill_bp=float(a.gross[a.filled].mean()) if a.filled.any() else None,
                          ctrl_gross_per_fill_bp=float(b.gross[b.filled].mean()) if b.filled.any() else None,
                          diff_mean_bp=float(dif.mean()), t_naive=naive, t_day_cluster=nw_t(daily.to_numpy()),
                          dens_depth_sig_median=float((a.depth / a.sig).median()),
                          ctrl_depth_sig_median=float((b.depth / b.sig).median()),
                          dens_depth_bp_median=float(a.depth.median() * 1e4),
                          ctrl_depth_bp_median=float(b.depth.median() * 1e4),
                          dens_cancel=int(a.cancel.sum()), ctrl_cancel=int(b.cancel.sum()))
        cr = clips.get(name, [])
        mech[name]["ctrl_clip_rate"] = float(sum(n_ * r_ for n_, r_ in cr if r_ == r_) / max(1, sum(n_ for n_, _ in cr)))
        mech[name]["pass"] = bool(mech[name]["t_naive"] >= 2.0 and mech[name]["t_day_cluster"] >= 2.0)
        if not quiet:
            print(name, json.dumps({k_: (round(v, 3) if isinstance(v, float) else v) for k_, v in mech[name].items()}),
                  flush=True)
    # descriptive only: the 8 configs' daily paired differences averaged, Newey-West t
    pool = pd.concat([v for v in pooled.values()], axis=1).fillna(0.0).mean(axis=1)
    mech_pooled = dict(n_days=int(len(pool)), mean_daily_diff_bp=float(pool.mean()), t_day_cluster=nw_t(pool.to_numpy()))
    pd.DataFrame(cols).to_parquet(os.path.join(outdir, "dev_daily.parquet"))
    pd.concat(T_all, ignore_index=True).to_parquet(os.path.join(outdir, "dev_trades.parquet"))
    Uf = U[U.filled | U.cancel].drop(columns=["incomplete"])            # fills and cluster crossings (OI check)
    Uf.to_parquet(os.path.join(outdir, "dev_unit_cross.parquet"))
    cnt = U.groupby(["cfg", "arm", "coin"]).agg(events=("h", "size"), fills=("filled", "sum"),
                                                cancels=("cancel", "sum")).reset_index()
    cnt.to_csv(os.path.join(outdir, "dev_event_counts.csv"), index=False)
    json.dump(dict(mech=mech, pooled=mech_pooled, meta=meta, configs=[cfg_name(*c) for c in cfgs], end=str(HOLD0),
                   generated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
              open(os.path.join(outdir, "dev_mech.json"), "w"), indent=1)
    print("done", flush=True)


def run_full():
    fz = os.path.join(OUT, "frozen.json")
    if not os.path.exists(fz):
        raise SystemExit("full mode needs reports/hunt/h3lm/frozen.json (the freeze commit) first")
    F = json.load(open(fz))
    if not F.get("variant") or not F.get("params"):
        raise SystemExit("frozen.json names no variant (the idea stopped at the mechanism test): HOLD is not read")
    N, R, H = int(F["params"]["N"]), tuple(F["params"]["R"]), int(F["params"]["H"])
    ci = [cfg_name(*c) for c in grid()].index(cfg_name(N, R, H))
    days = scored_days()
    caps = ((30000, 0.5), (50000, 0.5), (30000, 0.25), (50000, 0.25))
    trades = {c: [] for c in caps}
    units = []
    for ci_coin, coin in enumerate(COINS):
        for ei, era in enumerate(("early", "main")):
            D = prepare(coin, era, None, (N,))
            if D is None:
                continue
            B, spec = bids_for(D, N, R, ci_coin, ei, ci)
            U = unit_table(D, B["dens"], spec, H)
            U["coin"] = coin
            units.append(U)
            for C, th in caps:
                trades[(C, th)].append(trades_table(D, B["dens"], spec, H, C, th))
            print(f"{coin} {era}: prep {D['secs_prep']:.1f}s", flush=True)
            del D
    os.makedirs(os.path.join(OUT, "full"), exist_ok=True)
    cols = {}
    for (C, th), lst in trades.items():
        T = gross_cap(pd.concat(lst, ignore_index=True), C)
        T.to_parquet(os.path.join(OUT, "full", f"trades_{C}_{th}.parquet"))
        for mult in (1.0, 2.0):
            cols[f"s{C // 1000}_{int(mult)}x" + ("" if th == 0.5 else f"_th{th}")] = \
                pnl(T, mult).reindex(days).fillna(0.0) / C
        if th == 0.5:
            for fee in (0.12, 0.30):
                for mult in (1.0, 2.0):
                    cols[f"s{C // 1000}_{int(mult)}x_fee{fee:.2f}"] = pnl(T, mult, fee).reindex(days).fillna(0.0) / C
    pd.DataFrame(cols).to_parquet(os.path.join(OUT, "full", "full_daily.parquet"))
    pd.concat(units, ignore_index=True).query("filled").to_parquet(os.path.join(OUT, "full", "unit_fills.parquet"))
    print("done", flush=True)


def run_smoke(outdir):
    """2024 only (never scored, not DEV): exercises the dev code path; prints shapes and counts, no statistics."""
    global SCORED, ERAS
    SCORED = {"main": ("2024-03-01", "2024-03-31")}
    ERAS = {"main": ("2024-02-01", "2024-04-01", "minute")}
    t0 = time.time()
    run_dev(outdir=outdir, coins=["SOL", "XRP"], quiet=True)
    d = pd.read_parquet(os.path.join(outdir, "dev_daily.parquet"))
    t = pd.read_parquet(os.path.join(outdir, "dev_trades.parquet"))
    c = pd.read_csv(os.path.join(outdir, "dev_event_counts.csv"))
    print("secs", round(time.time() - t0, 1), "daily", d.shape, "trades", t.shape, "nonzero cols",
          int((d != 0).any().sum()))
    print(c.groupby("arm")[["events", "fills", "cancels"]].sum().to_string())
    print(t.groupby("variant").size().head(4).to_string())


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "dev":
        run_dev()
    elif mode == "full":
        run_full()
    elif mode == "smoke":
        run_smoke(sys.argv[2])
