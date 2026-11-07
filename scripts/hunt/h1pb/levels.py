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
MED_WIN, MED_MINP = "24h", 60                      # 24-hour median of the basis (>= 60 both-traded minutes)
SIG_WIN, SIG_MINP = "3D", 720                      # 3-day std of the residual (>= 720 both-traded minutes)
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


def load_pair(coin):
    """Perp and spot 1-minute candles on one full minute grid from the perp's first minute (USD per coin)."""
    P = common.load_perp(coin)
    S = common.load_minute(coin)
    if P is None or S is None:
        return None
    sc = PX_SCALE.get(coin, 1.0)
    for k in ("open", "high", "low", "close"):
        P[k] = P[k] / sc
    t0 = P.index.min().floor("min")
    idx = pd.date_range(t0, GRID_END, freq="min", inclusive="left")
    P = P.reindex(idx)
    S = S[(S.index >= t0 - pd.Timedelta(days=1)) & (S.index < GRID_END)].reindex(idx)
    return idx, P, S


def stats(coin):
    """Per-minute fair value and residual sigma (row t = known at t-1), plus the candle arrays."""
    out = load_pair(coin)
    if out is None:
        return None
    idx, P, S = out
    pc, sc = P["close"].to_numpy(), S["close"].to_numpy()
    both = np.isfinite(pc) & np.isfinite(sc)
    b = pd.Series(np.log(pc[both] / sc[both]), index=idx[both])
    med = b.rolling(MED_WIN, min_periods=MED_MINP).median()
    e = b - med.shift(1)
    sig = e.rolling(SIG_WIN, min_periods=SIG_MINP).std()
    med_g = med.reindex(idx).ffill().to_numpy()
    sig_g = sig.reindex(idx).ffill().to_numpy()
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


def coins():
    return [c for c in common.PERP if os.path.exists(os.path.join(common.DATA, "cfm", f"{c}.parquet"))]
