"""Practitioner-grade backtest helpers.

- Excess returns: idle cash earns the 3-month T-bill rate; leverage above 1x pays T-bill + 2%;
  Sharpe is computed on returns in excess of T-bills (Carver, Chan, AQR all report it this way).
- Volatility: Carver's blend of a 32-day EWMA with its own 2-year average (70/30).
- Buffering: Carver's no-trade zone; only trade when the position drifts outside +/-10% of
  the average position, and then only to the edge of the zone.
"""
import glob
import os

import numpy as np
import pandas as pd

from edge import ls

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Approximate monthly 3-month T-bill yields (%, secondary market, month average).
_TB = {
    2016: [.26, .31, .29, .23, .27, .27, .30, .30, .29, .33, .45, .51],
    2017: [.51, .52, .74, .80, .89, .98, 1.07, 1.01, 1.03, 1.07, 1.23, 1.32],
    2018: [1.41, 1.57, 1.70, 1.76, 1.86, 1.90, 1.96, 2.03, 2.13, 2.25, 2.33, 2.37],
    2019: [2.37, 2.39, 2.40, 2.38, 2.35, 2.17, 2.10, 1.95, 1.89, 1.65, 1.54, 1.54],
    2020: [1.52, 1.52, .29, .14, .13, .16, .13, .10, .11, .10, .09, .09],
    2021: [.08, .04, .03, .02, .02, .04, .05, .05, .04, .05, .05, .06],
    2022: [.15, .33, .44, .76, 1.05, 1.52, 2.23, 2.63, 3.13, 3.72, 4.15, 4.25],
    2023: [4.54, 4.65, 4.69, 5.00, 5.14, 5.16, 5.25, 5.30, 5.32, 5.34, 5.27, 5.24],
    2024: [5.22, 5.24, 5.24, 5.24, 5.25, 5.24, 5.20, 5.05, 4.72, 4.51, 4.42, 4.27],
    2025: [4.21, 4.22, 4.20, 4.21, 4.25, 4.23, 4.25, 4.15, 3.98, 3.90, 3.80, 3.62],
    2026: [3.65, 3.67, 3.70, 3.70, 3.68, 3.66, 3.65, 3.63, 3.62, 3.62, 3.60, 3.60],
}


def rf_daily(index):
    pts = {pd.Timestamp(y, m + 1, 15): v for y, vals in _TB.items() for m, v in enumerate(vals)}
    s = pd.Series(pts).sort_index()
    s = s.reindex(s.index.union(index)).interpolate().ffill().bfill()
    return (s.reindex(index) / 100.0 / 365.0)


def excess_returns(W, cost=ls.COST, alt_fee=ls.ALT_SHORT_FEE):
    """Daily returns in excess of T-bills for target weights W (decided at close t, earn t+1)."""
    r = ls.returns(W, cost=cost, alt_fee=alt_fee)
    held = W.fillna(0.0).shift(1).fillna(0.0)
    longs, shorts = held.clip(lower=0).sum(axis=1), (-held.clip(upper=0)).sum(axis=1)
    rf = rf_daily(W.index)
    idle = (1.0 - longs - shorts).clip(lower=0.0)
    borrowed = (longs - 1.0).clip(lower=0.0)
    return r + idle * rf - borrowed * (rf + 0.02 / 365) - rf


def sharpe(x, start=None, end=None):
    x = x.loc[start:end].dropna()
    if len(x) < 60 or x.std() == 0:
        return np.nan
    return x.mean() / x.std() * np.sqrt(365)


def summary(x, start=None, end=None):
    """Sharpe on excess returns; CAGR and drawdown on total returns (excess + T-bill)."""
    x = x.loc[start:end].dropna()
    if len(x) < 60:
        return dict(sharpe=np.nan, cagr=np.nan, maxdd=np.nan)
    tot = x + rf_daily(x.index)
    eq = (1 + tot).cumprod()
    yrs = (x.index[-1] - x.index[0]).days / 365.25
    return dict(sharpe=sharpe(x), cagr=eq.iloc[-1] ** (1 / yrs) - 1, maxdd=(eq / eq.cummax() - 1).min())


def carver_vol(ret, span=32, long_days=730):
    ew = ret.ewm(span=span, min_periods=20).std()
    lr = ew.rolling(long_days, min_periods=90).mean()
    v = (0.7 * ew + 0.3 * lr.fillna(ew)) * np.sqrt(365)
    return v.clip(lower=0.10)


def buffer_positions(ideal, width):
    """Carver buffering: hold the current position while inside ideal +/- width; else move to the edge."""
    out = pd.DataFrame(index=ideal.index, columns=ideal.columns, dtype=float)
    for c in ideal.columns:
        p, ia, wa = 0.0, ideal[c].to_numpy(), width[c].to_numpy()
        res = np.empty(len(ia))
        for i in range(len(ia)):
            tgt, w = ia[i], wa[i]
            if np.isnan(tgt):
                p = 0.0
            elif np.isnan(w):
                p = tgt
            elif p < tgt - w:
                p = tgt - w
            elif p > tgt + w:
                p = tgt + w
            if abs(p) < 1e-4 and abs(tgt) < 1e-9:
                p = 0.0
            res[i] = p
        out[c] = res
    return out


def cap_gross(W, cap):
    g = W.abs().sum(axis=1)
    scale = (cap / g).where(g > cap, 1.0)
    return W.mul(scale, axis=0)


def load_hlc(assets):
    out = {}
    for a in assets:
        p = os.path.join(ROOT, "data", "prices", f"{a}.csv")
        df = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
        out[a] = df[["high", "low", "close"]]
    return out


def load_perps():
    out = {}
    for p in glob.glob(os.path.join(ROOT, "data", "perps", "*.csv")):
        df = pd.read_csv(p, parse_dates=["date"]).set_index("date")
        out[os.path.basename(p)[:-4]] = df["close"]
    return pd.DataFrame(out).sort_index() if out else pd.DataFrame()
