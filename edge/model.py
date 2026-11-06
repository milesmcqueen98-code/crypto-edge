"""LightGBM cross-sectional ranker. Hyperparameters were fixed before any test results were
seen and are frozen: changing them after looking at results is how backtests get overfit."""
import numpy as np
import pandas as pd
import lightgbm as lgb

PARAMS = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_data_in_leaf=300,
              feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10.0,
              n_estimators=300, verbose=-1, seed=7, num_threads=2)
NON_FEATURES = {"date", "asset", "fwd7", "fwd7_rank", "target"}
PURGE_DAYS = 8   # 7-day label + 1 day, so no training label overlaps the prediction period


def feature_cols(df):
    return [c for c in df.columns if c not in NON_FEATURES]


def fit(train):
    train = train[train["fwd7_rank"].notna() & (train["n_univ"] >= 10)]
    return lgb.LGBMRegressor(**PARAMS).fit(train[feature_cols(train)], train["fwd7_rank"] - 0.5)


def walk_forward(X, test_start, freq="QS"):
    starts = pd.date_range(test_start, X.date.max(), freq=freq)
    out = []
    for i, t0 in enumerate(starts):
        t1 = starts[i + 1] if i + 1 < len(starts) else X.date.max() + pd.Timedelta(days=1)
        test = X[(X.date >= t0) & (X.date < t1)]
        if test.empty:
            continue
        m = fit(X[X.date < t0 - pd.Timedelta(days=PURGE_DAYS)])
        out.append(test[["date", "asset", "fwd7", "fwd7_rank"]].assign(pred=m.predict(test[feature_cols(X)])))
    return pd.concat(out, ignore_index=True)


def weekly_ic(preds, col="pred"):
    d = preds.dropna(subset=["fwd7"])
    days = sorted(d.date.unique())[::7]
    ic = d[d.date.isin(days)].groupby("date").apply(
        lambda g: g[col].corr(g["fwd7"], method="spearman"), include_groups=False).dropna()
    return ic.mean(), ic.mean() / ic.std() * np.sqrt(len(ic)), len(ic)
