#!/usr/bin/env python3
"""H8 (depeg bids): universe, ticks, fees, candle loaders and rung levels (reports/hunt/h8dp/SPEC.md).

Par: 1.0 USD for the stablecoins. cbETH: trailing 30-day median of the daily median cbETH-USD / ETH-USD ratio
(known the day before), times ETH-USD's previous-minute close (candle-level information at least 1 minute old).
Bids sit on the product's tick grid, rounded DOWN (never shallower than the SPEC depth); the take-profit sell
(par - 5 bp) is rounded UP to the grid.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
CANDLES = os.path.join(ROOT, "data", "hunt", "h8dp", "candles")

DEPTHS = (0.0010, 0.0025, 0.0050, 0.0100, 0.0200)       # union of the SPEC ladders: shallow 10/25/50, deep 50/100/200
TP_BP = 5.0                                              # exit: sell at par - 5 bp (post-only)
STABLES = ("USDT-USD", "DAI-USD", "PYUSD-USD", "GUSD-USD", "USDS-USD")
WRAPPED = ("CBETH-USD",)                                 # cbBTC has no Coinbase Exchange pair (products.json)
UNIVERSE_ALL = STABLES + WRAPPED
TICK = {"USDT-USD": 1e-5, "DAI-USD": 1e-4, "PYUSD-USD": 1e-5, "GUSD-USD": 1e-3, "USDS-USD": 1e-4,
        "CBETH-USD": 0.01, "UST-USD": 1e-5, "BUSD-USD": 1e-3}
# Fees (fraction, one side, 1x). fx_stablecoin pairs (DAI, PYUSD, GUSD, USDS; products.json flag): 0% maker,
# 0.10-0.45 bp taker by liquidity tier, the worst (0.45 bp) used; source reports/hunt/research/R3_plumbing.md
# (third-party table, Aug 2026, unverified against Coinbase's sign-in fee page). USDT-USD and CBETH-USD are not
# fx_stablecoin pairs: standard VIP 1 (common.py, 0.06% maker / 0.125% taker).
FX_STABLE = ("DAI-USD", "PYUSD-USD", "GUSD-USD", "USDS-USD", "UST-USD", "BUSD-USD")


def fees(pid):
    """(maker, taker, half_spread) as fractions, 1x. Market orders pay 1.5x the half-spread (pre-registration)."""
    import common
    hs = max(common.SPOT_HALF_SPREAD_BP * 1e-4, 0.5 * TICK.get(pid, 0.0))   # GUSD's 10 bp tick: >= 5 bp
    if pid in FX_STABLE:
        return 0.0, 0.45e-4, hs
    return common.SPOT_MAKER, common.SPOT_TAKER, hs


def load_candles(pid, end=None):
    fs = sorted(glob.glob(os.path.join(CANDLES, pid, "*.parquet")))
    d = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates("ts").sort_values("ts").set_index("ts")
    d = d[d.volume > 0]
    if end is not None:
        d = d[d.index < pd.Timestamp(end)]
    return d


def load_eth(end=None):
    import common
    parts = [common.load_minute("ETH", "minute_early"), common.load_minute("ETH", "minute")]
    e = pd.concat([p for p in parts if p is not None])
    e = e[~e.index.duplicated()].sort_index()
    if end is not None:
        e = e[e.index < pd.Timestamp(end)]
    return e


def cbeth_par(C, E):
    """Per cbETH minute: par (USD) = ratio30 (days < today) x ETH close of the previous minute."""
    eth_prev = E["close"].astype(float).shift(1)                        # ETH close at t-1 (on ETH's own index)
    eth_prev = eth_prev.reindex(E.index.union(C.index)).ffill().reindex(C.index)
    eth_now = E["close"].astype(float).reindex(C.index)
    r = (C["close"] / eth_now).dropna()
    daily = r.groupby(r.index.floor("D")).median()
    r30 = daily.rolling(30, min_periods=10).median().shift(1)          # only days strictly before
    r30 = r30.reindex(C.index.floor("D")).to_numpy()
    return pd.Series(r30 * eth_prev.to_numpy(), index=C.index)


def floor_tick(x, t):
    return np.floor(np.asarray(x, float) / t + 1e-9) * t


def ceil_tick(x, t):
    return np.ceil(np.asarray(x, float) / t - 1e-9) * t


def rung_levels(pid, C, par=None):
    """DataFrame (index = C.index) of bid levels, one column per depth in DEPTHS, plus 'tp' (par - 5 bp)."""
    t = TICK[pid]
    if par is None:
        par = pd.Series(1.0, index=C.index)
    out = {d: floor_tick(par.to_numpy() * (1 - d), t) for d in DEPTHS}
    out["tp"] = ceil_tick(par.to_numpy() * (1 - TP_BP * 1e-4), t)
    return pd.DataFrame(out, index=C.index)


def levels_for(pid, C, end=None):
    if pid == "CBETH-USD":
        return rung_levels(pid, C, cbeth_par(C, load_eth(end)))
    return rung_levels(pid, C)
