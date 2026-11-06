"""Hourly engine for strategies run on Coinbase's US perpetual-style futures (nano BTC / nano ETH).

Positions are fractions of capital decided at the close of hour t and held through hour t+1.
Costs: PERP_COST per unit traded (fee + slippage). Funding: longs pay and shorts receive the
funding rate each hour (Hyperliquid daily funding / 24 where available, PRE_FUNDING per year
before May 2023, as a stand-in for Coinbase's own funding). Collateral not posted as margin is
assumed to earn T-bills (USDC rewards or a T-bill ETF), so the excess return is the futures P&L
minus T-bills on the 20% of capital held as margin while a position is open.
Daily excess returns are the sum of hourly ones (UTC days), so Sharpe is comparable to the daily work.
"""
import os

import numpy as np
import pandas as pd

from edge import book, data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERP_COST = 0.0004
PRE_FUNDING = 0.08
MARGIN_SHARE = 0.20


def load_hourly(assets=("BTC", "ETH")):
    frames = {}
    for a in assets:
        p = os.path.join(ROOT, "data", "hourly", f"{a}.csv.gz")
        df = pd.read_csv(p, parse_dates=["ts"]).drop_duplicates("ts").set_index("ts").sort_index()
        frames[a] = df
    start = min(d.index.min() for d in frames.values())
    end = max(d.index.max() for d in frames.values())
    idx = pd.date_range(start, end, freq="h")
    close = pd.DataFrame({a: d["close"].reindex(idx) for a, d in frames.items()})
    close = close.ffill(limit=6)
    for a, d in frames.items():                       # blank out before listing
        close.loc[: d.index.min() - pd.Timedelta(hours=1), a] = np.nan
    volume = pd.DataFrame({a: d["volume"].reindex(idx).fillna(0.0) for a, d in frames.items()})
    return close, volume


def hourly_funding(idx, assets, pre=PRE_FUNDING, mult=1.0, shift=0.0):
    f = data.load_funding()
    day = idx.floor("D")
    out = {}
    for a in assets:
        per_hour = pd.Series(pre / 8760.0, index=idx)
        if a in f:
            fd = f[a].dropna()
            mapped = pd.Series(day.map(fd).to_numpy(), index=idx) / 24.0
            per_hour = mapped.where(mapped.notna(), per_hour)
        out[a] = per_hour * mult + shift / 8760.0
    return pd.DataFrame(out)


def run(P, close, cost=PERP_COST, funding=None):
    """P: hourly target positions (fractions of capital, +long/-short). Returns daily excess returns."""
    P = P.reindex(close.index).fillna(0.0)
    r = close.pct_change(fill_method=None).fillna(0.0)
    held = P.shift(1).fillna(0.0)
    if funding is None:
        funding = hourly_funding(close.index, list(P.columns))
    pnl = (held * r[P.columns]).sum(axis=1) - (held * funding[P.columns]).sum(axis=1)
    tc = P.diff().abs().sum(axis=1).fillna(0.0) * cost
    day = close.index.floor("D")
    rf_day = book.rf_daily(pd.DatetimeIndex(day.unique()))
    rf_h = pd.Series(day.map(rf_day).to_numpy(), index=close.index) / 24.0
    margin = MARGIN_SHARE * (held.abs().sum(axis=1) > 0).astype(float)
    ex = pnl - tc - margin * rf_h
    return ex.groupby(day).sum()


def daily_from_hourly(close):
    """UTC daily closes from hourly bars (close of the 23:00 bar)."""
    return close.groupby(close.index.floor("D")).last()
