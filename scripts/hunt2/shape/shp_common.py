#!/usr/bin/env python3
"""Edge hunt 2, builds SHAPE and IMP (builder `shape`): shared candle helpers.

R2-08's conventions (scripts/lab/core.py, scripts/wick_sim.py load_ohlc, variants.R208):
- the minute grid is every minute from the era's lab START to END; candles with volume 0 are dropped, then the close is
  forward-filled up to 30 minutes (`cf`); log returns are diffs of log(cf) (NaN across longer gaps);
- R2-08's beta is the trailing 7-day (10,080-minute, >= 1,440 observations) OLS beta of the coin's 1-minute log
  returns on BTC's, clipped to [0, 3]; `b` at minute t uses returns through t, so the beta "as of t-1" is b[t-1];
- its level for minute t: exp(x[t-60] + b[t-1] (f[t-1] - f[t-60]) - 4 sig[t-1]), sig = the 3-day rolling std of the
  60-minute residual move (used here only to verify the beta reproduction on DEV parents).
Data are read from the main clone (read-only).
"""
import os

import numpy as np
import pandas as pd

MAIN = "/home/claude/crypto-edge"
SRC = {"main": ("minute", "2024-01-01", "2026-11-06"), "early": ("minute_early", "2021-01-01", "2024-01-01")}
ERA_TAG = {"sel": "main", "chk": "main", "early": "early"}
WBETA, MINP, WSIG = 10080, 1440, 4320


def shift(x, n):
    out = np.full(len(x), np.nan)
    if n > 0:
        out[n:] = x[:-n]
    elif n < 0:
        out[:n] = x[-n:]
    else:
        out[:] = x
    return out


def rbeta(ri, rf, w=WBETA):
    """scripts/lab/core.py rbeta, unchanged."""
    a, b = pd.Series(ri), pd.Series(rf)
    mp = min(MINP, w)
    m = lambda s: s.rolling(w, min_periods=mp).mean()  # noqa: E731
    cov = m(a * b) - m(a) * m(b)
    return (cov / b.rolling(w, min_periods=mp).var()).clip(0.0, 3.0).to_numpy()


_GRID = {}


def grid(tag):
    src, start, end = SRC[tag]
    return pd.date_range(start, end, freq="min", inclusive="left")


def load_cf(tag, coin):
    """Forward-filled log close on the lab's minute grid (as scripts/wick_sim.py load_ohlc), or None."""
    key = (tag, coin)
    if key in _GRID:
        return _GRID[key]
    src = SRC[tag][0]
    p = os.path.join(MAIN, "data", src, f"{coin}.parquet")
    if not os.path.exists(p):
        return None
    idx = grid(tag)
    df = pd.read_parquet(p, columns=["ts", "close", "volume"]).drop_duplicates("ts").set_index("ts").sort_index()
    df = df[df.volume > 0].reindex(idx)
    cf = df["close"].astype(np.float64).ffill(limit=30).to_numpy(np.float64)
    out = np.log(cf)
    _GRID[key] = out
    return out


def returns(lp):
    return np.diff(lp, prepend=np.nan)


def beta_series(tag, coin):
    """R2-08's beta through minute t (b[t]) on the grid; use b[t-1] for a decision at minute t."""
    x, f = load_cf(tag, coin), load_cf(tag, "BTC")
    return rbeta(returns(x), returns(f), WBETA)


def level_check(tag, coin, pos, k=4.0, L=60):
    """R2-08's 4-sigma level for minute positions `pos` (to verify the beta reproduction against the frozen lvl)."""
    x, f = load_cf(tag, coin), load_cf(tag, "BTC")
    b = beta_series(tag, coin)
    e = (x - shift(x, L)) - b * (f - shift(f, L))
    sig_now = pd.Series(e).rolling(WSIG, min_periods=min(1440, WSIG)).std().to_numpy()
    pos = np.asarray(pos)
    return np.exp(x[pos - L] + b[pos - 1] * (f[pos - 1] - f[pos - L]) - k * sig_now[pos - 1])


def positions(tag, ts):
    return grid(tag).get_indexer(pd.DatetimeIndex(ts))
