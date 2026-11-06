#!/usr/bin/env python3
"""Execution-level test of the cross-sectional reversal on 1-minute Coinbase data, Jan 2024 - Nov 2026
(the period the hourly signal was never selected on).

For lookback/holding L minutes (5, 15, 30, 60) and entry delays d (0, 1, 2, 5, 10 minutes):
  signal_i  = P_i[t] / P_i[t-L] - 1                  (P = minute close)
  weights   = dollar-neutral, minus cross-sectional rank (long losers, short winners), gross 1
  return    = sum_i w_i * (P_i[t+d+L] / P_i[t+d] - 1)
Reports gross Sharpe, turnover and break-even cost per side, plus Roll (1984) effective-spread
estimates per coin, to compare the edge per trade with what crossing the spread costs.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "ADA", "AVAX", "LINK"]
START, END = "2024-01-01", "2026-11-06"


def load():
    px, vol = {}, {}
    for c in COINS:
        df = pd.read_parquet(os.path.join(ROOT, "data", "minute", f"{c}.parquet")).drop_duplicates("ts").set_index("ts")
        px[c], vol[c] = df["close"].astype(float), df["volume"].astype(float)
    idx = pd.date_range(START, END, freq="min", inclusive="left")
    P = pd.DataFrame({c: s.reindex(idx) for c, s in px.items()})
    V = pd.DataFrame({c: s.reindex(idx) for c, s in vol.items()}).fillna(0.0)
    traded = V > 0
    P = P.ffill(limit=10)
    return P, V, traded


def roll_spread_bp(P):
    out = {}
    for c in P:
        dp = np.log(P[c]).diff().dropna()
        cov = dp.autocorr(1) * dp.var()
        out[c] = 2 * np.sqrt(-cov) * 1e4 if cov < 0 else 0.0
    return pd.Series(out)


def test(P, traded, L, d):
    A = P.to_numpy()
    T = A.shape[0]
    tt = np.arange(L, T - L - d - 1, L)                  # decision points every L minutes
    sig = A[tt] / A[tt - L] - 1
    ok = traded.to_numpy()[tt] & ~np.isnan(sig)
    ent, ext = A[tt + d], A[tt + d + L]
    fwd = ext / ent - 1
    ok &= ~np.isnan(fwd)
    sig = np.where(ok, sig, np.nan)
    rk = pd.DataFrame(sig).rank(axis=1).to_numpy()
    n = np.sum(~np.isnan(rk), axis=1, keepdims=True)
    w = -(rk - np.nanmean(rk, axis=1, keepdims=True))
    g = np.nansum(np.abs(w), axis=1, keepdims=True)
    w = np.where((n >= 6) & (g > 0), w / np.where(g > 0, g, 1), 0.0)
    w = np.nan_to_num(w)
    ret = np.nansum(w * np.nan_to_num(fwd), axis=1)
    turn = np.r_[np.abs(w[0]).sum(), np.abs(np.diff(w, axis=0)).sum(axis=1)]
    per_year = 525_600 / L
    mu, sd = ret.mean(), ret.std()
    return dict(L=L, delay=d, gross_sharpe=mu / sd * np.sqrt(per_year), gross_ret_yr=mu * per_year,
                turnover_yr=turn.mean() * per_year, breakeven_bp=mu / turn.mean() * 1e4,
                edge_per_trade_bp=mu * 1e4)


def main():
    P, V, traded = load()
    print(f"minutes {len(P):,}; coverage (share of minutes with trades):",
          {c: f"{traded[c].mean():.0%}" for c in COINS})
    rs = roll_spread_bp(P)
    print("Roll effective-spread estimate (bp, round trip):", {c: round(v, 2) for c, v in rs.items()})
    dv = (V * P).resample("h").sum().mean()
    print("Average hourly $ volume on Coinbase (millions):", {c: round(v / 1e6, 1) for c, v in dv.items()})
    rows = []
    for L in (5, 15, 30, 60):
        for d in (0, 1, 2, 5, 10):
            r = test(P, traded, L, d)
            rows.append(r)
            print(f"  L={L:2d}m delay={d:2d}m: gross Sharpe {r['gross_sharpe']:6.2f}  gross {r['gross_ret_yr']:+8.1%}/yr  "
                  f"turnover {r['turnover_yr']:9,.0f}x  break-even {r['breakeven_bp']:5.2f} bp/side", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(ROOT, "reports", "minute_reversal.csv"), index=False)
    rs.to_csv(os.path.join(ROOT, "reports", "roll_spreads_bp.csv"))


if __name__ == "__main__":
    main()
