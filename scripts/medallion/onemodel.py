#!/usr/bin/env python3
"""F10 one model: every F0/F1/F4/F8 signal (rolling z-scores) for BTC and ETH, pooled; ridge (alpha 10 on
standardized features) and LightGBM (library defaults, 200 trees, depth 3), retrained monthly from 2021 on all prior
data; predicts next-day return; position = prediction / its trailing 1-year std, capped +/-1, vol-targeted.
Writes reports/medallion/books_F10.csv and books_F10_returns.parquet.
"""
import warnings

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from common import DEV, HOLDOUT_OPEN, TARGET, active_from, daily_close, run_daily, save, stats, vol_unit
from features import z_signals

warnings.filterwarnings("ignore")


def panel():
    frames, closes = [], {}
    for coin in ("BTC", "ETH"):
        Z, _, close = z_signals(coin)
        Z = Z.copy()
        Z["y"] = close.shift(-1) / close - 1
        Z["coin"] = coin
        frames.append(Z)
        closes[coin] = close
    P = pd.concat(frames)
    P.index.name = "date"
    return P.reset_index(), pd.DataFrame(closes)


def predict(P, kind):
    feats = [c for c in P.columns if c[:2] in ("F0", "F1", "F4", "F8")]
    pred = pd.Series(np.nan, index=P.index)
    for m in pd.date_range("2021-01-01", P.date.max(), freq="MS"):
        tr = P[(P.date <= m - pd.Timedelta(days=2)) & P.y.notna()]
        te = P[(P.date >= m) & (P.date <= m + pd.offsets.MonthEnd(0))]
        if len(te) == 0:
            continue
        cols = [c for c in feats if tr[c].notna().sum() > 0]
        if kind == "ridge":
            sc = StandardScaler().fit(tr[cols].fillna(0.0))
            mdl = Ridge(alpha=10.0).fit(sc.transform(tr[cols].fillna(0.0)), tr.y)
            pred.loc[te.index] = mdl.predict(sc.transform(te[cols].fillna(0.0)))
        else:
            mdl = LGBMRegressor(n_estimators=200, max_depth=3, random_state=0, verbose=-1)
            mdl.fit(tr[cols], tr.y)
            pred.loc[te.index] = mdl.predict(te[cols])
    return pred


def main():
    P, close = panel()
    rows, R = [], {}
    full = daily_close(["BTC", "ETH"])
    unit = vol_unit(full)
    for kind in ("ridge", "lgbm"):
        P[f"pred_{kind}"] = predict(P, kind)
        pr = P.pivot(index="date", columns="coin", values=f"pred_{kind}").reindex(full.index)
        sd = pr.rolling(365, min_periods=60).std()
        W = (pr / sd).clip(-1, 1) * 0.5 * unit
        W = W.fillna(0.0)
        x, turn = run_daily(W, full)
        name = f"F10_{kind}"
        R[name] = x
        e = dict(turnover_per_year=float(turn.loc[DEV[0]:DEV[1]].mean() * 365))
        for coin in ("BTC", "ETH"):
            d = pd.concat([pr[coin], (full[coin].shift(-1) / full[coin] - 1)], axis=1).loc[DEV[0]:DEV[1]].dropna()
            e[f"ic_dev_{coin}"] = float(d.corr(method="spearman").iloc[0, 1])
        rows.append(stats(name, x, e, active_from=active_from(turn, x)))
    df = pd.DataFrame(rows)
    save(df, "books_F10.csv")
    R = pd.DataFrame(R)
    if not HOLDOUT_OPEN:
        R = R.loc[:DEV[1]]
    save(R, "books_F10_returns.parquet")
    keep = P[["date", "coin", "y", "pred_ridge", "pred_lgbm"]]
    if not HOLDOUT_OPEN:
        keep = keep[keep.date <= DEV[1]]
    save(keep.set_index("date"), "f10_predictions.parquet")
    pd.set_option("display.width", 250)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
