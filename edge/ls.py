"""Shared engine for the long/short search. Weights are targets set at close t (earn t+1).
Costs: COST per unit of weight traded. Short carry: Hyperliquid funding where available
(positive = shorts receive), else 0; alt (non-BTC/ETH) shorts also pay ALT_SHORT_FEE per year."""
import numpy as np
import pandas as pd

from edge import data

COST = 0.0025
ALT_SHORT_FEE = 0.05
PERIODS = {"dev": ("2019-11-06", "2023-12-31"), "hold_recent": ("2024-01-01", None),
           "hold_early": ("2016-07-01", "2019-11-05")}

_cache = {}


def load():
    if not _cache:
        close, dvol, ret = data.load()
        fund = data.load_funding().reindex(close.index)
        _cache.update(close=close, dvol=dvol, ret=ret.fillna(0.0), fund=fund)
    return _cache["close"], _cache["dvol"], _cache["ret"], _cache["fund"]


def returns(W, cost=COST, alt_fee=ALT_SHORT_FEE):
    """W: date x asset target weights (NaN = 0). Returns daily net return series."""
    close, _, ret, fund = load()
    W = W.fillna(0.0)
    cols = W.columns
    held = W.shift(1).fillna(0.0)
    R = ret.reindex(index=W.index, columns=cols).fillna(0.0)
    gross = (held * R).sum(axis=1)
    F = fund.reindex(index=W.index, columns=cols).fillna(0.0).shift(1).fillna(0.0)
    shorts = (-held.clip(upper=0))
    carry = (shorts * F).sum(axis=1)
    alt_cols = [c for c in cols if c not in ("BTC", "ETH")]
    fee = shorts[alt_cols].sum(axis=1) * alt_fee / 365 if alt_cols else 0.0
    tc = W.diff().abs().sum(axis=1)
    tc.iloc[0] = W.iloc[0].abs().sum()
    return gross + carry - fee - tc * cost


def stats(r, start, end=None):
    r = r.loc[start:end]
    if len(r) < 60 or r.std() == 0:
        return dict(sharpe=np.nan, cagr=np.nan, maxdd=np.nan)
    eq = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    return dict(sharpe=r.mean() / r.std() * np.sqrt(365), cagr=eq.iloc[-1] ** (1 / yrs) - 1,
                maxdd=(eq / eq.cummax() - 1).min())


def evaluate(name, r, family):
    row = {"family": family, "name": name}
    for p, (s, e) in PERIODS.items():
        st = stats(r, s, e)
        row |= {f"{p}_{k}": v for k, v in st.items()}
    return row


def weights(index, **cols):
    return pd.DataFrame(cols, index=index).astype(float)
