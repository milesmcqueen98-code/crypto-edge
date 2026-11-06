"""Point-in-time universe and features. Everything at date t uses data through close t only.
Shared by the research backtest and the live daily signal so they can't drift apart."""
import numpy as np
import pandas as pd

TOP_N = 50            # universe: top 50 by trailing 30-day median USD volume
MIN_VOL = 1e6         # $1M/day median volume floor on the source venue
MIN_HISTORY = 90      # days listed before a coin can enter
REGIME_ASSET, REGIME_SMA = "BTC", 100


def universe(close, dvol):
    v30 = dvol.rolling(30, min_periods=20).median()
    hist = close.notna().cumsum()
    elig = (hist >= MIN_HISTORY) & close.notna() & (v30 >= MIN_VOL)
    rank = v30.where(elig).rank(axis=1, ascending=False)
    return rank <= TOP_N, v30


def regime(close):
    b = close[REGIME_ASSET]
    return b > b.rolling(REGIME_SMA).mean()


def build(close, dvol, ret, with_label=True):
    univ, v30 = universe(close, dvol)
    btc, btc_ret = close[REGIME_ASSET], ret[REGIME_ASSET]
    f = {}
    for h in [1, 3, 7, 14, 28, 56, 90, 180]:
        f[f"ret_{h}"] = close / close.shift(h) - 1
    for h in [7, 28, 90]:
        f[f"vol_{h}"] = ret.rolling(h, min_periods=int(h * 0.7)).std()
    for h in [20, 50, 100, 200]:
        f[f"dist_sma{h}"] = close / close.rolling(h, min_periods=int(h * 0.8)).mean() - 1
    f["dd_90"] = close / close.rolling(90, min_periods=60).max() - 1
    f["up_90"] = close / close.rolling(90, min_periods=60).min() - 1
    f["logv30"] = np.log(v30)
    f["v7_v30"] = dvol.rolling(7, min_periods=5).median() / v30
    f["mom_risk_adj"] = f["ret_28"] / (f["vol_28"] * np.sqrt(28))
    cov = ret.rolling(90, min_periods=60).cov(btc_ret)
    f["beta_btc"] = cov.div(btc_ret.rolling(90, min_periods=60).var(), axis=0)
    f["rel_btc_28"] = f["ret_28"].sub(f["ret_28"][REGIME_ASSET], axis=0)
    f["skew_28"] = ret.rolling(28, min_periods=20).skew()
    f["max_ret_28"] = ret.rolling(28, min_periods=20).max()

    long = pd.concat({k: v.where(univ).stack() for k, v in f.items()}, axis=1)
    long.index.names = ["date", "asset"]
    long = long.replace([np.inf, -np.inf], np.nan)
    cols = list(f.keys())
    ranked = long.groupby(level="date")[cols].rank(pct=True)
    ranked.columns = [c + "_r" for c in cols]

    mkt = pd.DataFrame(index=close.index)
    mkt["btc_ret_28"] = btc / btc.shift(28) - 1
    mkt["btc_vol_28"] = btc_ret.rolling(28).std()
    mkt["btc_dist_sma100"] = btc / btc.rolling(100).mean() - 1
    above50 = (close > close.rolling(50, min_periods=40).mean()).astype(float).where(univ)
    mkt["breadth_50"] = above50.sum(axis=1) / univ.sum(axis=1).astype(float).replace(0, np.nan)
    mkt["dispersion_28"] = f["ret_28"].where(univ).std(axis=1)
    mkt["n_univ"] = univ.sum(axis=1)

    X = ranked.join(long[["vol_28", "logv30", "beta_btc"]]).join(mkt, on="date")
    if with_label:
        fwd7 = (close.shift(-7) / close - 1).clip(-0.95, 5.0).where(univ).stack()
        fwd7.index.names = ["date", "asset"]
        X["fwd7"] = fwd7
        X["fwd7_rank"] = X.groupby(level="date")["fwd7"].rank(pct=True)
    return X.reset_index(), univ, f
