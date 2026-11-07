#!/usr/bin/env python3
"""H11 (MJ): deep hourly bids on BTC, ETH, SOL and XRP perps (reports/hunt/h11mj/SPEC.md under
reports/hunt_prereg.md). Fill, cost and halt code copied from the H3 build (branch hunt/h3lm, scripts/hunt/h3lm/lm.py).

Modes (run from the repo root on GitHub Actions; local runs only for small tests):
  python scripts/hunt/h11mj/mj.py dev            DEV trials (<= 12). Loads no minute at or after 2026-06-01, so it
                                                 cannot touch HOLD. Stage 1: the 8 core trials. Stage 2 (same job, by
                                                 the fixed rule): the best core trial's variants k = 9 and BTC only,
                                                 and its two AI-filter trials.
  python scripts/hunt/h11mj/mj.py full           the frozen variant (reports/hunt/h11mj/frozen.json) on all scored
                                                 days with candle fills; refuses to run without frozen.json.
  python scripts/hunt/h11mj/mj.py prints COIN    perp prints for COIN's post-launch trades of the full run (needs
                                                 internet): print-checked fills, sizes, take-profits, market exits.
  python scripts/hunt/h11mj/mj.py smoke OUTDIR   the dev code path on 2024 data (never scored); counts only.

Bids (SPEC, fixed): at the top of every hour, using data to t-1:
  sigma = std of the last 72 one-hour spot log returns (closes at the minute before each top of hour; >= 48 needed);
  P = spot close of the previous minute; bid = P exp(-k sigma) rounded down to the perp tick, raised to the lowest tick
  at or above 0.95 P when deeper (Fair Value Limit: a perp order must sit within 5% of spot; the clamp share is
  reported); take-profit = bid + 50% of (P - bid), rounded down to the tick; replaced every hour; no bid in the
  Friday 5-6 PM ET hour; contract worth >= $150 at P; no bid in the 5 hours before the spot -> perp venue switch.
Venue: Coinbase perp 1-minute candles from the day after each launch (BTC/ETH 2025-07-19, SOL/XRP 2025-08-16);
  before that, spot candles on the perp tick grid with the perp cost model.
Fills (candles): the minute opens above the bid and its low is at or below bid - 1 tick; no matching during the
  Friday 5-6 PM ET halt or for 2 minutes after a +-10% move from the hour's first open (R3, all eras). Size <=
  theta x through-volume (candle volume spread over its range, while the price stays below the bid, <= 15 minutes),
  whole contracts, target notional 1x sleeve capital. Take-profit post-only (one-tick trade-through; volume above it
  spread over the range, <= theta); else a market exit at the open of the first tradable minute H minutes after the
  fill. No stop. One position per coin; gross <= 2x across coins (later fills trimmed, whole contracts).
Prints (fixed before any run; units fixed after the first HOLD read, logged deviation: Coinbase perp print sizes are
  contracts, converted to coins with the contract size): the gate series of the frozen variant uses perp prints for
  every post-launch trade:
  a fill needs a print at or below bid - 1 tick in the candle fill minute; size <= theta x the volume of prints
  strictly below the bid from that print while the price stays below it (<= 15 minutes), never above the candle size;
  take-profit volume = prints strictly above it after the fill, <= theta; the market exit is priced at the first print
  at least 2 s after the exit decision (plus 1.5x half-spread in the costs). Trades the prints do not confirm are
  dropped. DEV trials use candles.
Costs: scripts/hunt/common.py (perp $0.20 per contract per side, 1.5x half-spread on market exits, 1 bp per 8 h
  funding); 2x for every gate, 1x for information; $0.12 and $0.30 per contract for information (R3).
AI trials (fixed before any run; the SPEC's two AI slots): walk-forward LightGBM (huber, the wick lab's parameters,
  3 seeds averaged) by quarter from 2022Q3; features known at placement (sigma, the coin's 24-hour and 7-day spot
  moves, BTC's 4-hour spot move, UTC hour, coin); label = net bp at 2x costs of fills at least 1 day before the
  quarter starts (2024 fills train but are never scored); keep a bid if its prediction exceeds the median of the
  training predictions; a quarter with fewer than 200 training fills (too few to split at min_data_in_leaf 60), or a
  model whose training predictions are constant, keeps every bid (fixed after a 2024 smoke test showed a constant
  model drops every bid, before any DEV run). AIa trains on the best core
  trial's own book fills; AIb trains on its unit fills (every hour's bid simulated alone at unit size), the SPEC's
  "fills" read both ways.
Selection (prereg): the highest DEV alpha t (sleeve $30K at 2x on the incumbent at $70K) among trials with >= 40
  trades; the same rule picks the best core trial for stage 2.
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

OUT = os.path.join(ROOT, "reports", "hunt", "h11mj")
COINS = ["BTC", "ETH", "SOL", "XRP"]
UNIV = {"BE": ("BTC", "ETH"), "ALL": tuple(COINS), "BTC": ("BTC",)}
CORE = [(k, H, u) for k in (5.0, 7.0) for H in (60, 240) for u in ("BE", "ALL")]
K_VAR = 9.0
FVL = 0.05
HALT_PCT = 0.10
SIG_N, SIG_MIN = 72, 48
ERAS = {"early": ("2021-12-01", "2024-01-01", "minute_early"), "main": ("2024-01-01", "2026-11-06", "minute")}
SCORED = (("2022-01-01", "2023-12-31"), ("2025-01-01", "2026-11-05"))
TRAIN = ("2024-01-08", "2024-12-31")             # AI training rows only, never scored
HOLD0 = pd.Timestamp("2026-06-01")
SWITCH_GAP = 300
CAPS = ((30000, 0.5), (50000, 0.5), (30000, 0.25), (50000, 0.25))
AI_MIN_ROWS = 200                                   # enough rows to split at min_data_in_leaf 60, bagging 0.8
AI_Q0 = "2022Q3"
AI_QEND = "2026Q2"                                  # DEV: the last quarter with DEV hours
FEATS = ["sigma", "ret24_bp", "ret7d_bp", "btc4h_bp", "hour", "coin_id"]
LGB_PARAMS = dict(objective="huber", alpha=60.0, learning_rate=0.03, num_leaves=7, min_data_in_leaf=60,
                  feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1)
LGB_ROUNDS, LGB_SEEDS = 250, (7, 11, 23)


def tname(k, H, u, ai=""):
    return f"k{int(k)}_H{H}_{u}" + (f"_AI{ai}" if ai else "")


# ------------------------------------------------------------------------------------------------ kernels (from H3)
@numba.njit(cache=True)
def fill_scan(o, lo, halt, h, bid, tick, n):
    """First minute in h .. h+59 that opens above the bid and trades through it by one tick (-1 if none)."""
    for t in range(h, min(n, h + 60)):
        if halt[t] or not (lo[t] == lo[t]):
            continue
        if o[t] > bid and lo[t] <= bid - tick:
            return t
    return -1


@numba.njit(cache=True)
def through_usd(hi, lo, vol, halt, tf, bid, n):
    """USD volume below the bid from the fill minute while the price stays below it (<= 15 more minutes)."""
    tot = 0.0
    for j in range(tf, min(n, tf + 16)):
        lj = lo[j]
        if halt[j] or not (lj == lj) or lj >= bid:
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
def unit_events(o, hi, lo, halt, hs, bids, tps, tick, H):
    """Each bid alone at unit size: fill minute (-1 none, -2 exit not observable), exit minute, exit px, type (1 TP,
    2 market), cascade low (min low over the fill minute and the next 60)."""
    n = len(o)
    m = len(hs)
    tf = np.full(m, -1, np.int64)
    xt = np.full(m, -1, np.int64)
    xp = np.full(m, np.nan)
    typ = np.zeros(m, np.int8)
    clow = np.full(m, np.nan)
    for j in range(m):
        f = fill_scan(o, lo, halt, hs[j], bids[j], tick, n)
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
    return tf, xt, xp, typ, clow


@numba.njit(cache=True)
def book(o, hi, lo, vol, halt, hs, bids, tps, tick, H, C, theta, csize):
    """One coin, one position at a time. Per trade: bid index, fill minute, coins, coins closed by the take-profit,
    TP completion (or last TP) minute, market-exit minute, exit px, through-volume USD, cascade low."""
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
        f = fill_scan(o, lo, halt, h, bid, tick, n)
        if f < 0:
            continue
        usd = through_usd(hi, lo, vol, halt, f, bid, n)
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
    """Minute grid with spot, perp (main era) and the trading venue (spot before the perp's first full day, perp after).
    end: exclusive cap (DEV passes HOLD0, so no HOLD minute is ever loaded)."""
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
    halt, fri = halt_mask(idx, V)
    return dict(idx=idx, S=S, V=V, sw=sw, coin=coin, era=era, halt=halt, fri=fri)


def halt_mask(idx, V):
    """R3: Friday 5-6 PM ET maintenance and 2-minute halts after a +-10% move from the hour's first open."""
    et = idx.tz_localize("UTC").tz_convert("America/New_York")
    fri = np.asarray((et.weekday == 4) & (et.hour == 17))
    hour_key = np.asarray(idx.floor("h").asi8)
    ref = pd.Series(V["open"]).groupby(hour_key).transform("first").to_numpy()
    with np.errstate(invalid="ignore"):
        trig = (V["low"] <= (1 - HALT_PCT) * ref) | (V["high"] >= (1 + HALT_PCT) * ref)
    halt = fri.copy()
    tr = np.nonzero(trig)[0]
    for d in (1, 2):
        j = tr + d
        halt[j[j < len(halt)]] = True
    return halt, fri


def day_set(spans):
    return set().union(*[set(pd.date_range(a, b, freq="D")) for a, b in spans])


SCORED_DAYS = day_set(SCORED)
TRAIN_DAYS = day_set((TRAIN,))


def hours_table(D, btc_cf):
    """Decision hours (top of hour h, data to h-1) on scored or training days, with sigma, P and the AI features."""
    idx, S = D["idx"], D["S"]
    cf = S["cf"]
    tops = np.nonzero(np.asarray(idx.minute == 0))[0]
    tops = tops[tops >= 1]
    c = cf[tops - 1]
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.diff(np.log(c), prepend=np.nan)
    sig = pd.Series(r).rolling(SIG_N, min_periods=SIG_MIN).std().to_numpy()

    def lag(a, m):
        x = np.full(len(tops), np.nan)
        ok = tops - 1 - m >= 0
        x[ok] = a[tops[ok] - 1 - m]
        return x

    with np.errstate(invalid="ignore", divide="ignore"):
        ret24 = np.log(c / lag(cf, 1440)) * 1e4
        ret7d = np.log(c / lag(cf, 10080)) * 1e4
        btc4h = np.log(btc_cf[tops - 1] / lag(btc_cf, 240)) * 1e4
    ts = idx[tops]
    day = ts.floor("D")
    scored = np.asarray(day.isin(SCORED_DAYS))
    train = np.asarray(day.isin(TRAIN_DAYS))
    coin = D["coin"]
    size = common.PERP[coin][1]
    with np.errstate(invalid="ignore"):
        valid = np.isfinite(c) & np.isfinite(sig) & (sig > 0) & (np.nan_to_num(c) * size >= common.MIN_CONTRACT_USD)
    valid &= ~D["fri"][tops]
    valid &= ~((tops >= D["sw"] - SWITCH_GAP) & (tops < D["sw"]))
    valid &= scored | train
    T = pd.DataFrame(dict(coin=coin, era=D["era"], h=tops, ts=ts, P=c, sigma=sig, ret24_bp=ret24, ret7d_bp=ret7d,
                          btc4h_bp=btc4h, hour=np.asarray(ts.hour, float), coin_id=float(COINS.index(coin)),
                          valid=valid, scored=scored, train=train))
    return T[T.valid].reset_index(drop=True)


def make_bids(Ht, D, k, keep=None):
    coin = D["coin"]
    size, tick = common.PERP[coin][1], common.PERP[coin][2]
    P = Ht.P.to_numpy()
    raw = np.floor(P * np.exp(-k * Ht.sigma.to_numpy()) / tick + 1e-9) * tick
    lowest = np.ceil((1 - FVL) * P / tick - 1e-9) * tick                 # R3 Fair Value Limit (5% of spot)
    bid = np.maximum(raw, lowest)
    tp = np.floor((bid + 0.5 * (P - bid)) / tick + 1e-9) * tick
    ok = (bid > 0) & (tp > bid)
    if keep is not None:
        ok &= keep
    j = np.nonzero(ok)[0]
    B = dict(j=j, h=Ht.h.to_numpy()[j].astype(np.int64), bid=bid[j], tp=tp[j], P=P[j], sigma=Ht.sigma.to_numpy()[j],
             capped=(raw < lowest)[j], ts=Ht.ts.to_numpy()[j])
    return B, dict(size=size, tick=tick)


def _ts(idx, a):
    a = np.asarray(a, np.int64)
    if not len(a):
        return pd.DatetimeIndex([], dtype="datetime64[ns]")
    v = idx.values.astype("datetime64[ns]")[np.maximum(a, 0)].copy()
    v[a < 0] = np.datetime64("NaT", "ns")
    return pd.DatetimeIndex(v)


def unit_table(D, B, spec, H, mult=2.0):
    V, coin = D["V"], D["coin"]
    tf, xt, xp, typ, clow = unit_events(V["open"], V["high"], V["low"], D["halt"], B["h"], B["bid"], B["tp"],
                                        spec["tick"], H)
    filled = tf >= 0
    e = B["bid"]
    g = np.where(filled, (xp / e - 1.0) * 1e4, 0.0)
    hrs = np.where(filled, (xt - tf) / 60.0, 0.0)
    xpf = np.where(filled, xp, e)
    c_in = common.perp_cost_bp(coin, e, taker=False, mult=mult)
    c_out = np.where(typ == 1, common.perp_cost_bp(coin, xpf, taker=False, mult=mult),
                     common.perp_cost_bp(coin, xpf, taker=True, mult=mult))
    net = np.where(filled, g - c_in - c_out - common.perp_funding_bp(hrs, mult), 0.0)
    U = pd.DataFrame(dict(coin=coin, era=D["era"], h=B["h"], ts=B["ts"], fill_ts=_ts(D["idx"], np.where(filled, tf, -1)),
                          filled=filled, incomplete=tf == -2, tp=typ == 1, gross=g, net=net, capped=B["capped"],
                          depth_bp=np.log(B["P"] / e) * 1e4, low_dist_bp=np.where(filled, (e / clow - 1) * 1e4, np.nan),
                          venue=np.where(np.where(filled, tf, B["h"]) >= D["sw"], "perp", "spot")))
    return U[~U.incomplete & U.filled].drop(columns=["incomplete"]).reset_index(drop=True)


def trades_table(D, B, spec, H, C, theta):
    V = D["V"]
    ev, tf, q, qtp, ttp, tx, xpx, inu, clw = book(V["open"], V["high"], V["low"], V["vol"], D["halt"], B["h"], B["bid"],
                                                  B["tp"], spec["tick"], H, float(C), theta, spec["size"])
    idx = D["idx"]
    T = pd.DataFrame(dict(coin=D["coin"], era=D["era"], h=B["h"][ev], h_ts=_ts(idx, B["h"][ev]), fill_ts=_ts(idx, tf),
                          bid=B["bid"][ev], tp=B["tp"][ev], P=B["P"][ev], sigma=B["sigma"][ev], capped=B["capped"][ev],
                          qty=q, q_tp=qtp, tp_ts=_ts(idx, ttp), x_ts=_ts(idx, tx), x_px=xpx, in_usd=inu, low=clw,
                          venue=np.where(tf >= D["sw"], "perp", "spot"), H=H))
    T["tp_ts"] = T.tp_ts.where(T.q_tp > 0)
    T["notional"] = T.qty * T.bid
    return T


def gross_cap(T, C, cap=2.0):
    """Gross <= cap x C across coins (positions open from fill to final exit), in fill-time order; whole contracts."""
    if len(T) == 0:
        return T
    T = T.sort_values(["fill_ts", "coin"]).reset_index(drop=True)
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
    T["q_tp"] = np.minimum(T.q_tp.to_numpy(), q_new)
    T["qty"] = q_new
    T["notional"] = T.qty * T.bid
    return T[T.qty > 0].reset_index(drop=True)


def trade_pnl(T, mult=2.0, fee=None):
    """Per trade: USD P&L of the take-profit part and of the rest (entry cost booked with the rest), booking days."""
    if len(T) == 0:
        return pd.DataFrame(columns=["pnl_tp", "day_tp", "pnl_rem", "day_rem", "pnl", "net_bp"])
    old = common.PERP_FEE_USD
    if fee is not None:
        common.PERP_FEE_USD = fee
    try:
        parts = []
        for coin, g in T.groupby("coin", sort=False):
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
            p_r = np.where(qr > 0, p_r, 0.0) - c_in
            d_tp = g.tp_ts.dt.floor("D")
            d_r = g.x_ts.dt.floor("D").where(qr > 0, d_tp)
            parts.append(pd.DataFrame(dict(pnl_tp=np.where(qtp > 0, p_tp, 0.0), day_tp=d_tp.fillna(d_r).to_numpy(),
                                           pnl_rem=p_r, day_rem=d_r.to_numpy()), index=g.index))
        P = pd.concat(parts).loc[T.index]
        P["pnl"] = P.pnl_tp + P.pnl_rem
        P["net_bp"] = P.pnl / T.notional * 1e4
        return P
    finally:
        common.PERP_FEE_USD = old


def daily(T, C, days, mult=2.0, fee=None):
    if len(T) == 0:
        return pd.Series(0.0, index=days)
    P = trade_pnl(T, mult, fee)
    s = pd.concat([pd.Series(P.pnl_tp.to_numpy(), index=pd.DatetimeIndex(P.day_tp)),
                   pd.Series(P.pnl_rem.to_numpy(), index=pd.DatetimeIndex(P.day_rem))])
    s = s[s.index.notna()].groupby(level=0).sum()
    return s.reindex(days).fillna(0.0) / C


def scored_days(end=None):
    d = pd.DatetimeIndex(sorted(SCORED_DAYS))
    return d if end is None else d[d < pd.Timestamp(end)]


def in_days(T, days, end=None):
    """Trades filled on the given days whose final exit is before `end`."""
    if len(T) == 0:
        return T
    m = T.fill_ts.dt.floor("D").isin(days)
    if end is not None:
        m &= T.x_ts.fillna(T.tp_ts) < pd.Timestamp(end)
    return T[m].reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ AI
def walk_forward(Ht, L, q_end):
    """Ht: hour rows (ts, FEATS); L: label rows (ts = fill time, FEATS, y). Returns the keep mask over Ht and info."""
    import lightgbm as lgb
    keep = np.ones(len(Ht), bool)
    info = []
    tsH = Ht.ts.to_numpy()
    for per in pd.period_range(AI_Q0, q_end, freq="Q"):
        q0, q1 = per.start_time, per.end_time
        te = (tsH >= np.datetime64(q0)) & (tsH <= np.datetime64(q1))
        if not te.any():
            continue
        tr = L[L.ts < q0 - pd.Timedelta(days=1)]
        if len(tr) < AI_MIN_ROWS:
            info.append(dict(q=str(per), n_train=int(len(tr)), model=False, keep_rate=1.0))
            continue
        ptr, pte = [], []
        Xte = Ht.loc[te, FEATS]
        for s in LGB_SEEDS:
            m = lgb.train(LGB_PARAMS | {"seed": s}, lgb.Dataset(tr[FEATS], tr.y.to_numpy(), categorical_feature=["coin_id"]),
                          num_boost_round=LGB_ROUNDS)
            ptr.append(m.predict(tr[FEATS]))
            pte.append(m.predict(Xte))
        ptr_m = np.mean(ptr, axis=0)
        thr = float(np.median(ptr_m))
        if np.ptp(ptr_m) <= 1e-9:                    # no split was possible: a constant model keeps every bid
            info.append(dict(q=str(per), n_train=int(len(tr)), model=False, keep_rate=1.0, constant=True))
            continue
        kk = np.mean(pte, axis=0) > thr
        keep[te] = kk
        info.append(dict(q=str(per), n_train=int(len(tr)), model=True, thr_bp=round(thr, 2),
                         keep_rate=round(float(kk.mean()), 3)))
    return keep, info


def ai_labels(kind, trades, units, Hall):
    """Training rows: fills with their placement-hour features and net bp at 2x."""
    if kind == "a":
        T = trades
        P = trade_pnl(T, 2.0)
        L = T[["coin", "era", "h", "fill_ts"]].copy()
        L["y"] = P.net_bp.to_numpy()
    else:
        L = units[["coin", "era", "h", "fill_ts", "net"]].rename(columns={"net": "y"}).copy()
    L = L.merge(Hall[["coin", "era", "h"] + FEATS], on=["coin", "era", "h"], how="left")
    L["ts"] = L.fill_ts
    return L.dropna(subset=["y"]).sort_values("ts").reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ runs
def coin_eras(coins, end):
    """Yield (coin, era, D, hours) one at a time (keeps memory small)."""
    for era in ERAS:
        btc = load_coin("BTC", era, end)
        btc_cf = btc["S"]["cf"] if btc is not None else None
        for coin in coins:
            D = btc if coin == "BTC" else load_coin(coin, era, end)
            if D is None:
                continue
            Ht = hours_table(D, btc_cf)
            yield coin, era, D, Ht
            if coin != "BTC":
                del D
        del btc


def universe_trades(store, coins, cap):
    lst = [t for c in coins for t in store.get(c, {}).get(cap, [])]
    T = pd.concat(lst, ignore_index=True) if lst else pd.DataFrame()
    return gross_cap(T, cap[0]) if len(T) else T


def series_block(name, store, coins, days, end, cols, trades_out, n_trades):
    for cap in CAPS:
        T = in_days(universe_trades(store, coins, cap), days, end)
        for mult in (1.0, 2.0):
            cols[f"{name}|{cap[0]}|{cap[1]}|{int(mult)}x"] = daily(T, cap[0], days, mult)
        if cap == (30000, 0.5):
            t = T.copy()
            t["variant"] = name
            trades_out.append(t)
            n_trades[name] = int(len(T))


def run_dev(outdir=None, coins=COINS, select=True):
    import gates
    outdir = outdir or os.path.join(OUT, "dev")
    os.makedirs(outdir, exist_ok=True)
    days = scored_days(HOLD0)
    t0 = time.time()
    st1 = {}                          # (k, H) -> coin -> cap -> [trades]
    units = {}                        # (k, H) -> coin -> [unit fills]
    hours = []
    meta = dict(coin_era={}, clamp_share={})
    for coin, era, D, Ht in coin_eras(coins, HOLD0):
        assert D["idx"][-1] < HOLD0
        hours.append(Ht)
        meta["coin_era"][f"{coin}|{era}"] = dict(minutes=len(D["idx"]), hours=int(len(Ht)), scored_hours=int(Ht.scored.sum()),
                                                 switch=str(D["idx"][D["sw"]]) if D["sw"] < len(D["idx"]) else None)
        for k in (5.0, 7.0):
            for H in (60, 240):
                B, spec = make_bids(Ht, D, k)
                meta["clamp_share"][f"k{int(k)}|{coin}|{era}"] = float(B["capped"].mean()) if len(B["h"]) else None
                for cap in CAPS:
                    st1.setdefault((k, H), {}).setdefault(coin, {}).setdefault(cap, []).append(
                        trades_table(D, B, spec, H, *cap))
                units.setdefault((k, H), {}).setdefault(coin, []).append(unit_table(D, B, spec, H))
        print(f"{coin} {era}: {len(Ht)} hours, {time.time() - t0:.0f}s", flush=True)
    Hall = pd.concat(hours, ignore_index=True)
    cols, trades_out, n_tr = {}, [], {}
    for k, H, u in CORE:
        series_block(tname(k, H, u), st1[(k, H)], UNIV[u], days, HOLD0, cols, trades_out, n_tr)
    # ---- stage 2: the best core trial (prereg statistic: alpha t of the $30K sleeve at 2x on the incumbent at $70K)
    tstat = {}
    if select:
        inc70 = gates.incumbent(70e3, days=days)
        for k, H, u in CORE:
            nm = tname(k, H, u)
            tstat[nm] = gates.alpha_test(cols[f"{nm}|30000|0.5|2x"], inc70)["t_alpha"]
        elig = [c for c in CORE if n_tr[tname(*c)] >= 40]
        key = lambda c: tstat[tname(*c)] if np.isfinite(tstat[tname(*c)]) else -np.inf  # noqa: E731
        best = max(elig, key=key) if elig else CORE[0]
    else:
        best = CORE[0]
    kb, Hb, ub = best
    meta["best_core"] = tname(*best)
    meta["core_t_alpha_inc70"] = tstat
    print("best core:", tname(*best), {k_: round(v, 2) for k_, v in tstat.items()}, flush=True)
    # BTC only: the stage-1 BTC book of the best (k, H)
    series_block(tname(kb, Hb, "BTC"), st1[(kb, Hb)], UNIV["BTC"], days, HOLD0, cols, trades_out, n_tr)
    # AI masks from labels on the best core trial
    Hb_rows = Hall[Hall.coin.isin(UNIV[ub])].reset_index(drop=True)
    best_trades = universe_trades(st1[(kb, Hb)], UNIV[ub], (30000, 0.5))
    best_trades = best_trades[best_trades.fill_ts.dt.floor("D").isin(SCORED_DAYS | TRAIN_DAYS)]
    best_trades = best_trades[best_trades.x_ts.fillna(best_trades.tp_ts) < HOLD0].reset_index(drop=True)
    U = pd.concat([x for c in UNIV[ub] for x in units[(kb, Hb)][c]], ignore_index=True)
    U = U[U.fill_ts.dt.floor("D").isin(SCORED_DAYS | TRAIN_DAYS)]
    masks, ai_info = {}, {}
    for kind, src in (("a", best_trades), ("b", U)):
        L = ai_labels(kind, best_trades if kind == "a" else None, U if kind == "b" else None, Hall)
        keep, info = walk_forward(Hb_rows, L, AI_QEND)
        masks[kind] = Hb_rows.assign(keep=keep).set_index(["coin", "era", "h"]).keep
        ai_info[kind] = dict(n_labels=int(len(L)), quarters=info)
    meta["ai"] = ai_info
    st2 = {"k9": {}, "a": {}, "b": {}}
    for coin, era, D, Ht in coin_eras(list(UNIV[ub]), HOLD0):
        B, spec = make_bids(Ht, D, K_VAR)
        meta["clamp_share"][f"k{int(K_VAR)}|{coin}|{era}"] = float(B["capped"].mean()) if len(B["h"]) else None
        for cap in CAPS:
            st2["k9"].setdefault(coin, {}).setdefault(cap, []).append(trades_table(D, B, spec, Hb, *cap))
        for kind in ("a", "b"):
            kp = masks[kind].reindex(pd.MultiIndex.from_arrays([Ht.coin, Ht.era, Ht.h])).fillna(True).to_numpy(bool)
            B, spec = make_bids(Ht, D, kb, keep=kp)
            for cap in CAPS:
                st2[kind].setdefault(coin, {}).setdefault(cap, []).append(trades_table(D, B, spec, Hb, *cap))
    series_block(tname(K_VAR, Hb, ub), st2["k9"], UNIV[ub], days, HOLD0, cols, trades_out, n_tr)
    for kind in ("a", "b"):
        series_block(tname(kb, Hb, ub, kind), st2[kind], UNIV[ub], days, HOLD0, cols, trades_out, n_tr)
    meta["n_trades"] = n_tr
    meta["trials"] = list(n_tr)
    d = pd.DataFrame(cols)
    assert d.index.max() < HOLD0
    d.to_parquet(os.path.join(outdir, "dev_daily.parquet"))
    pd.concat(trades_out, ignore_index=True).to_parquet(os.path.join(outdir, "dev_trades.parquet"))
    Uall = []
    for (k, H), byc in units.items():
        for c, lst in byc.items():
            x = pd.concat(lst, ignore_index=True)
            x = x[x.fill_ts.dt.floor("D").isin(set(days))]
            x["k"], x["H"] = k, H
            Uall.append(x)
    pd.concat(Uall, ignore_index=True).to_parquet(os.path.join(outdir, "dev_units.parquet"))
    meta["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    meta["end"] = str(HOLD0)
    json.dump(meta, open(os.path.join(outdir, "dev_meta.json"), "w"), indent=1, default=str)
    print("done", round(time.time() - t0), "s", flush=True)


def run_full():
    fz = os.path.join(OUT, "frozen.json")
    if not os.path.exists(fz):
        raise SystemExit("full mode needs reports/hunt/h11mj/frozen.json (the freeze commit) first")
    F = json.load(open(fz))
    k, H, u, ai = float(F["params"]["k"]), int(F["params"]["H"]), F["params"]["universe"], F["params"].get("ai", "")
    coins = list(UNIV[u])
    days = scored_days()
    caps = CAPS + ((100000, 0.5),)
    os.makedirs(os.path.join(OUT, "full"), exist_ok=True)
    store = {}
    hours = []
    units = {}
    keep = None
    if ai:
        # walk-forward labels from the core book (or units) of the same k, H, universe, through 2026Q4
        st0 = {}
        for coin, era, D, Ht in coin_eras(coins, None):
            hours.append(Ht)
            B, spec = make_bids(Ht, D, k)
            st0.setdefault(coin, {}).setdefault((30000, 0.5), []).append(trades_table(D, B, spec, H, 30000, 0.5))
            units.setdefault(coin, []).append(unit_table(D, B, spec, H))
        Hall = pd.concat(hours, ignore_index=True)
        bt = universe_trades(st0, coins, (30000, 0.5))
        bt = bt[bt.fill_ts.dt.floor("D").isin(SCORED_DAYS | TRAIN_DAYS)].reset_index(drop=True)
        U = pd.concat([x for c in coins for x in units[c]], ignore_index=True)
        U = U[U.fill_ts.dt.floor("D").isin(SCORED_DAYS | TRAIN_DAYS)]
        L = ai_labels(ai, bt if ai == "a" else None, U if ai == "b" else None, Hall)
        kp, info = walk_forward(Hall, L, "2026Q4")
        keep = Hall.assign(keep=kp).set_index(["coin", "era", "h"]).keep
        json.dump(info, open(os.path.join(OUT, "full", "ai_quarters.json"), "w"), indent=1)
    os.makedirs(os.path.join(OUT, "full"), exist_ok=True)
    clamp = {}
    for coin, era, D, Ht in coin_eras(coins, None):
        kp = None
        if keep is not None:
            kp = keep.reindex(pd.MultiIndex.from_arrays([Ht.coin, Ht.era, Ht.h])).fillna(True).to_numpy(bool)
        B, spec = make_bids(Ht, D, k, keep=kp)
        clamp[f"{coin}|{era}"] = float(B["capped"].mean()) if len(B["h"]) else None
        for cap in caps:
            store.setdefault(coin, {}).setdefault(cap, []).append(trades_table(D, B, spec, H, *cap))
        U = unit_table(D, B, spec, H)
        U = U[U.fill_ts.dt.floor("D").isin(set(days))]
        units.setdefault("frozen", []).append(U)
        print(f"{coin} {era} done", flush=True)
    cols = {}
    for cap in caps:
        T = in_days(universe_trades(store, coins, cap), days)
        T.to_parquet(os.path.join(OUT, "full", f"trades_{cap[0]}_{cap[1]}.parquet"))
        for mult in (1.0, 2.0):
            cols[f"s{cap[0] // 1000}_{int(mult)}x" + ("" if cap[1] == 0.5 else f"_th{cap[1]}")] = daily(T, cap[0], days, mult)
    pd.DataFrame(cols).to_parquet(os.path.join(OUT, "full", "candle_daily.parquet"))
    pd.concat(units["frozen"], ignore_index=True).to_parquet(os.path.join(OUT, "full", "unit_fills.parquet"))
    json.dump(dict(clamp=clamp, frozen=F), open(os.path.join(OUT, "full", "full_meta.json"), "w"), indent=1, default=str)
    print("done", flush=True)


# ------------------------------------------------------------------------------------------------ prints
def print_check(pr, t, tick, theta):
    """Re-evaluate one trade on perp prints (sorted by time). Returns the print-based fill, size, take-profit and
    market exit. pr: DataFrame time, price, size."""
    out = dict(p_fill=False, p_qty=0.0, p_q_tp=0.0, p_tp_ts=pd.NaT, p_x_ts=pd.NaT, p_x_px=np.nan, p_through=0.0,
               p_n=int(len(pr)), p_vol_fill_min_contracts=0.0)
    if len(pr) == 0:
        return out
    csize = common.PERP[t.coin][1]
    tm = pr.time.to_numpy()
    px = pr.price.to_numpy()
    sz = pr["size"].to_numpy() * csize                 # perp print sizes are contracts: convert to coins
    f0 = np.datetime64(t.fill_ts)
    f1 = f0 + np.timedelta64(60, "s")
    inmin = (tm >= f0) & (tm < f1)
    out["p_vol_fill_min_contracts"] = float(pr["size"].to_numpy()[inmin].sum())
    hit = np.nonzero(inmin & (px <= t.bid - tick + 1e-12))[0]
    if not len(hit):
        return out
    i0 = hit[0]
    lim = tm[i0] + np.timedelta64(15 * 60, "s")
    vol = 0.0
    i = i0
    while i < len(tm) and tm[i] <= lim:
        if px[i] >= t.bid:
            break
        vol += sz[i]
        i += 1
    q = min(t.qty, math.floor(theta * vol / csize + 1e-9) * csize)
    out.update(p_fill=q > 0, p_qty=q, p_through=vol)
    if q <= 0:
        return out
    t_end = np.datetime64(t.fill_ts) + np.timedelta64(int(t.H) * 60, "s")
    after = (tm > tm[i0]) & (tm < t_end)
    j = np.nonzero(after & (px >= t.tp + tick - 1e-12))[0]
    q_tp = 0.0
    if len(j):
        cum = 0.0
        for jj in range(j[0], len(tm)):
            if tm[jj] >= t_end:
                break
            if px[jj] > t.tp:
                cum += sz[jj]
                out["p_tp_ts"] = pd.Timestamp(tm[jj])
                if theta * cum >= q:
                    break
        q_tp = min(q, theta * cum)
    out["p_q_tp"] = q_tp
    if q_tp < q:
        dec = t_end + np.timedelta64(2, "s")
        k = np.nonzero(tm >= dec)[0]
        if len(k):
            out["p_x_ts"], out["p_x_px"] = pd.Timestamp(tm[k[0]]), float(px[k[0]])
    return out


def run_prints(coin):
    files = sorted(f for f in os.listdir(os.path.join(OUT, "full")) if f.startswith("trades_"))
    allt = []
    for f in files:
        T = pd.read_parquet(os.path.join(OUT, "full", f))
        T = T[(T.coin == coin) & (T.venue == "perp")].copy()
        T["file"] = f
        T["row"] = T.index
        allt.append(T)
    T = pd.concat(allt, ignore_index=True)
    pid, _, tick = common.PERP[coin]
    tick = float(tick)
    w0 = T.fill_ts.dt.floor("min")
    w1 = pd.concat([T.x_ts.fillna(T.tp_ts), T.fill_ts + pd.to_timedelta(T.H, unit="m")], axis=1).max(axis=1) \
        + pd.Timedelta(minutes=20)                      # slack so the market exit always has a print to land on
    W = pd.DataFrame(dict(s=w0, e=w1)).sort_values("s").reset_index(drop=True)
    merged = []
    for r in W.itertuples():
        if merged and r.s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], r.e)
        else:
            merged.append([r.s, r.e])
    fe = common.TradeFetcher()
    prints = []
    t0 = time.time()
    for i, (s, e) in enumerate(merged):
        try:
            d = fe.window(pid, s, e)
            d["ok"] = True
        except Exception as ex:  # noqa: BLE001
            print("fetch failed", s, e, repr(ex)[:200], flush=True)
            d = pd.DataFrame(dict(time=[pd.Timestamp(s)], price=[np.nan], size=[0.0], ok=[False]))
        d["w"] = i
        prints.append(d)
        if i % 20 == 0:
            print(f"{coin}: window {i + 1}/{len(merged)}, requests {fe.n_req}, {time.time() - t0:.0f}s", flush=True)
    P = pd.concat(prints, ignore_index=True)
    ok_w = P.groupby("w").ok.all()
    P = P[P.ok & P.price.notna()].sort_values("time").reset_index(drop=True)
    starts = np.array([np.datetime64(m[0]) for m in merged])
    raw = pd.read_parquet(os.path.join(common.DATA, "cfm", f"{coin}.parquet")).drop_duplicates("ts").set_index("ts")
    cvol = raw["volume"]                                # candle volume in contracts (completeness check)
    rows = []
    for t in T.itertuples():
        w = int(np.searchsorted(starts, np.datetime64(t.fill_ts.floor("min")), side="right") - 1)
        s, e = merged[w]
        pr = P[(P.time >= s) & (P.time < e)][["time", "price", "size"]]
        theta = 0.25 if "_0.25" in t.file else 0.5
        r = print_check(pr, t, tick, theta)
        r.update(file=t.file, row=t.row, fetch_ok=bool(ok_w.get(w, False)),
                 c_vol_fill_min_contracts=float(cvol.get(t.fill_ts, np.nan)))
        rows.append(r)
    R = pd.DataFrame(rows)
    R.to_parquet(os.path.join(OUT, "full", f"prints_{coin}.parquet"))
    P.to_parquet(os.path.join(OUT, "full", f"rawprints_{coin}.parquet"))
    print(f"{coin}: {len(T)} trade rows, {len(merged)} windows, {len(P)} prints, {fe.n_req} requests", flush=True)


def run_smoke(outdir):
    """2024 only (never scored, not DEV): exercises the dev code path; prints counts only."""
    global SCORED_DAYS, TRAIN_DAYS, ERAS, AI_MIN_ROWS, AI_Q0, AI_QEND
    ERAS = {"main": ("2024-01-01", "2024-07-01", "minute")}
    SCORED_DAYS = day_set((("2024-04-01", "2024-06-30"),))
    TRAIN_DAYS = day_set((("2024-01-08", "2024-03-31"),))
    AI_MIN_ROWS, AI_Q0, AI_QEND = 20, "2024Q2", "2024Q2"
    LGB_PARAMS["min_data_in_leaf"] = 5
    import gates
    gates.incumbent = lambda cap, theta=0.5, variant="instant", days=None: pd.Series(0.0, index=days)
    run_dev(outdir=outdir, coins=["BTC", "ETH"], select=False)
    d = pd.read_parquet(os.path.join(outdir, "dev_daily.parquet"))
    t = pd.read_parquet(os.path.join(outdir, "dev_trades.parquet"))
    m = json.load(open(os.path.join(outdir, "dev_meta.json")))
    print("daily", d.shape, "trades", t.shape, "trials", m["trials"])
    print("trades per trial", m["n_trades"])
    print("clamp", m["clamp_share"])
    print("ai", {k: (v["n_labels"], v["quarters"]) for k, v in m["ai"].items()})


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "dev":
        run_dev()
    elif mode == "full":
        run_full()
    elif mode == "prints":
        run_prints(sys.argv[2])
    elif mode == "smoke":
        run_smoke(sys.argv[2])
