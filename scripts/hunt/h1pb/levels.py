#!/usr/bin/env python3
"""H1 (PB): perp-only wicks and rips - fixed levels from 1-minute candles (reports/hunt/h1pb/SPEC.md, "Levels").

Row t of every array is the decision for minute t and uses only what is known at the end of minute t-1:
  b_s   = log(perp close / spot close) on minutes s where both traded
  bbar_t = trailing 24-hour median of b over both-traded minutes up to t-1
  e_s   = b_s - bbar_s                      (the basis residual against the median known before s)
  sig_t = trailing 3-day std of e over both-traded minutes up to t-1
  F_t   = spot close at t-1 x exp(bbar_t)
  long bid  = F_t exp(-k sig_t) rounded down to the perp tick; short offer = F_t exp(+k sig_t) rounded up.
Prices are USD per coin: PEPE perp candles (and prints) are quoted per 1000 PEPE and are divided by PX_SCALE here, so
common.PERP's per-coin contract size and tick apply.

The candidate superset used to plan trade fetches (k = 3, both sides, minute and spot-synchronous modes):
  long  candidate in minute t if perp low_t  < max(A_t, A_{t-1}), A_t = round_down(max(spot close_{t-1}, spot high_t) x exp(bbar_t - 3 sig_t))
  short candidate in minute t if perp high_t > min(Z_t, Z_{t-1}), Z_t = round_up(min(spot close_{t-1}, spot low_t) x exp(bbar_t + 3 sig_t))
Every minute-mode fill (any k >= 3) and every spot-synchronous fill (the last spot trade >= 1 s before a print lies
between spot close_{t-1} and the minute's spot high/low; the first second of minute t still uses minute t-1's
statistics, hence the A_{t-1} term) is inside this superset.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

PX_SCALE = {"PEPE": 1000.0, "SHIB": 1000.0}        # perp quoted per 1000 coins
KS = (3.0, 4.0, 6.0)
MED_WIN, SIG_WIN = "24h", "3D"
# Minimum both-traded minutes in each trailing window. v1 (first DEV fetch): 60 / 720, with statistics forward-filled
# over windows that were too thin (a stale value; bug). v2 (deviation, fixed before any DEV P&L was computed): 20 / 100,
# and a statistic is that of the last both-traded minute's own trailing window, NaN when that window is too thin.
STATS_VERSION = int(os.environ.get("H1_STATS", "2"))
MINP = {1: (60, 720), 2: (20, 100)}
SPOT_FFILL = 10                                    # spot close carried at most 10 minutes
FVL = 0.05                                         # Coinbase Derivatives Fair Value Limit: orders > 5% from spot rejected
GRID_END = pd.Timestamp("2026-11-06 02:00")


def round_down(px, tick):
    return np.floor(px / tick + 1e-9) * tick


def round_up(px, tick):
    return np.ceil(px / tick - 1e-9) * tick


def shift1(x):
    out = np.full(len(x), np.nan)
    out[1:] = x[:-1]
    return out


def load_pair(coin, end=GRID_END):
    """Perp and spot 1-minute candles on one full minute grid from the perp's first minute to `end` (exclusive),
    prices in USD per coin. Perp volume stays in contracts here."""
    P = pd.read_parquet(os.path.join(common.DATA, "cfm", f"{coin}.parquet")) if coin in common.PERP else None
    S = common.load_minute(coin)
    if P is None or S is None:
        return None
    P = P.drop_duplicates("ts").set_index("ts").sort_index()
    P = P[(P.volume > 0) & (P.index < end)]
    if not len(P):
        return None
    sc = PX_SCALE.get(coin, 1.0)
    for k in ("open", "high", "low", "close"):
        P[k] = P[k] / sc
    t0 = P.index.min().floor("min")
    idx = pd.date_range(t0, end, freq="min", inclusive="left")
    P = P.reindex(idx)
    S = S[(S.index >= t0 - pd.Timedelta(days=1)) & (S.index < end)].reindex(idx)
    return idx, P, S


def stats(coin, end=GRID_END, version=None):
    """Per-minute fair value and residual sigma (row t = known at t-1), plus the candle arrays (perp volume in
    contracts)."""
    version = version or STATS_VERSION
    MED_MINP, SIG_MINP = MINP[version]
    out = load_pair(coin, end)
    if out is None:
        return None
    idx, P, S = out
    pc, sc = P["close"].to_numpy(), S["close"].to_numpy()
    both = np.isfinite(pc) & np.isfinite(sc)
    b = pd.Series(np.log(pc[both] / sc[both]), index=idx[both])
    med = b.rolling(MED_WIN, min_periods=MED_MINP).median()
    e = b - med.shift(1)
    sig = e.rolling(SIG_WIN, min_periods=SIG_MINP).std()
    if version == 1:
        med_g = med.reindex(idx).ffill().to_numpy()
        sig_g = sig.reindex(idx).ffill().to_numpy()
    else:                                          # value at the last both-traded minute <= t (NaN stays NaN)
        last = pd.Series(np.where(both, np.arange(len(idx)), np.nan)).ffill().to_numpy()
        okl = np.isfinite(last)
        li = np.where(okl, last, 0).astype(np.int64)
        med_b = np.full(len(idx), np.nan)
        sig_b = np.full(len(idx), np.nan)
        med_b[both] = med.to_numpy()
        sig_b[both] = sig.to_numpy()
        med_g = np.where(okl, med_b[li], np.nan)
        sig_g = np.where(okl, sig_b[li], np.nan)
    s_cf = S["close"].ffill(limit=SPOT_FFILL).to_numpy()
    st = dict(idx=idx, coin=coin,
              bbar=shift1(med_g), sig=shift1(sig_g), s_prev=shift1(s_cf),
              p_open=P["open"].to_numpy(), p_high=P["high"].to_numpy(), p_low=P["low"].to_numpy(),
              p_close=pc, p_vol=P["volume"].fillna(0.0).to_numpy(),
              s_open=S["open"].to_numpy(), s_high=S["high"].to_numpy(), s_low=S["low"].to_numpy(), s_close=sc,
              p_cf=pd.Series(pc).ffill().to_numpy(), s_cf=s_cf)
    st["F"] = st["s_prev"] * np.exp(st["bbar"])
    return st


def level(st, k, side):
    """Minute-mode order price for minute t (NaN where no order: missing inputs or Fair Value Limit)."""
    tick = common.PERP[st["coin"]][2]
    with np.errstate(invalid="ignore"):
        if side == "long":
            lv = round_down(st["F"] * np.exp(-k * st["sig"]), tick)
            ok = lv >= (1 - FVL) * st["s_prev"]
        else:
            lv = round_up(st["F"] * np.exp(k * st["sig"]), tick)
            ok = lv <= (1 + FVL) * st["s_prev"]
        ok &= np.isfinite(lv) & (st["sig"] > 0)
    return np.where(ok, lv, np.nan)


def candidates(st, k=3.0, sync=True):
    """Boolean arrays (long, short): minutes in the fetch superset (see module doc). A print at time tau is judged
    with the statistics of row t = floor(tau - 1 s), so prints in [t + 1 s, t + 61 s) use row t: a candle minute m is
    a candidate when its low (high) crosses the row-m or the row-(m-1) level. sync=True widens the spot reference to
    every spot price the last-trade-1-s-before rule can return (spot close at t-1 and every trade of minute t)."""
    tick = common.PERP[st["coin"]][2]
    with np.errstate(invalid="ignore"):
        hi_ref = np.fmax(st["s_prev"], st["s_high"]) if sync else st["s_prev"]
        lo_ref = np.fmin(st["s_prev"], st["s_low"]) if sync else st["s_prev"]
        A = round_down(hi_ref * np.exp(st["bbar"] - k * st["sig"]), tick)
        Z = round_up(lo_ref * np.exp(st["bbar"] + k * st["sig"]), tick)
        A2, Z2 = np.fmax(A, shift1(A)), np.fmin(Z, shift1(Z))
        cs = common.PERP[st["coin"]][1]
        val_ok = np.nan_to_num(st["s_prev"]) * cs >= 0.9 * common.MIN_CONTRACT_USD
        lo_c = (st["p_low"] < A2 - 0.5 * tick) & val_ok
        hi_c = (st["p_high"] > Z2 + 0.5 * tick) & val_ok
    return lo_c, hi_c


def prefilter(st, rows, p, pprev, k_lo=3.0, k_hi=6.0):
    """Print-level superset of trigger prints over the whole grid (k in [k_lo, k_hi], both sides, both modes): the
    level a print can face lies between the levels implied by the lowest and highest spot price the 1-second rule
    can return (spot close of row-1 and every trade of the row's minute). Long: the print is below the highest
    k_lo level and the previous print is above the lowest k_hi level. Short mirrored."""
    tick = common.PERP[st["coin"]][2]
    b, s = st["bbar"][rows], st["sig"][rows]
    sp, lo_s, hi_s = st["s_prev"][rows], st["s_low"][rows], st["s_high"][rows]
    with np.errstate(invalid="ignore"):
        lo_ref, hi_ref = np.fmin(sp, lo_s), np.fmax(sp, hi_s)
        hiL = round_down(hi_ref * np.exp(b - k_lo * s), tick)
        loL = round_down(lo_ref * np.exp(b - k_hi * s), tick)
        loZ = round_up(lo_ref * np.exp(b + k_lo * s), tick)
        hiZ = round_up(hi_ref * np.exp(b + k_hi * s), tick)
        lng = (p < hiL - 0.5 * tick) & (pprev > loL - 0.5 * tick)
        sht = (p > loZ + 0.5 * tick) & (pprev < hiZ + 0.5 * tick)
        ok = (s > 0) & np.isfinite(b) & (np.nan_to_num(lo_ref) * common.PERP[st["coin"]][1] >= 0.9 * common.MIN_CONTRACT_USD)
    return (lng | sht) & ok


def coins():
    return [c for c in common.PERP if os.path.exists(os.path.join(common.DATA, "cfm", f"{c}.parquet"))]
