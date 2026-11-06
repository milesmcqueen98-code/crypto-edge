#!/usr/bin/env python3
"""AI market timing: should we hold BTC / ETH this week, or cash?

Design fixed before looking at results (one model, no tuning):
- Assets: BTC and ETH (longest clean Coinbase histories). Rows pooled across both.
- Features at close t: the asset's own trend/volatility features plus market-wide state
  (breadth and dispersion across the top-50 universe, BTC-vs-alts relative strength).
- Label: next-7-day return > 0. LightGBM classifier, same regularisation style as the ranker.
- Walk-forward: retrain quarterly from 2019-01-01 on an expanding window, 8-day purge.
- Rule: hold the asset for the week if P(up) > 0.5, else cash. Weekly (Sunday close) decisions.
Compared against the 100-day moving-average rule on the same assets and dates.
"""
import json
import os
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import data, features, portfolio as pf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = ["BTC", "ETH"]
WF_START = "2019-01-01"
PARAMS = dict(objective="binary", learning_rate=0.03, num_leaves=7, min_data_in_leaf=150,
              feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10.0,
              n_estimators=300, verbose=-1, seed=7, num_threads=2)


def timing_features(close, dvol, ret):
    univ, _ = features.universe(close, dvol)
    r28 = close / close.shift(28) - 1
    above50 = (close > close.rolling(50, min_periods=40).mean()).astype(float).where(univ)
    mkt = pd.DataFrame(index=close.index)
    mkt["breadth_50"] = above50.sum(axis=1) / univ.sum(axis=1).astype(float).replace(0, np.nan)
    mkt["dispersion_28"] = r28.where(univ).std(axis=1)
    mkt["btc_vs_alts_28"] = r28["BTC"] - r28.where(univ).median(axis=1)
    rows = []
    for a in ASSETS:
        c, r = close[a], ret[a]
        f = pd.DataFrame(index=close.index)
        for h in [1, 3, 7, 14, 28, 56, 90, 180]:
            f[f"ret_{h}"] = c / c.shift(h) - 1
        for h in [7, 28, 90]:
            f[f"vol_{h}"] = r.rolling(h).std()
        for h in [20, 50, 100, 200]:
            f[f"dist_sma{h}"] = c / c.rolling(h).mean() - 1
        f["dd_90"] = c / c.rolling(90).max() - 1
        f["up_90"] = c / c.rolling(90).min() - 1
        f["skew_28"] = r.rolling(28).skew()
        f["v7_v30"] = dvol[a].rolling(7).median() / dvol[a].rolling(30).median()
        f = f.join(mkt)
        f["is_eth"] = float(a == "ETH")
        f["fwd7"] = c.shift(-7) / c - 1
        f["asset"] = a
        rows.append(f.reset_index(names="date"))
    X = pd.concat(rows, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    return X[X.date >= "2016-07-01"]


def walk_forward(X):
    cols = [c for c in X.columns if c not in ("date", "asset", "fwd7")]
    starts = pd.date_range(WF_START, X.date.max(), freq="QS")
    out = []
    for i, t0 in enumerate(starts):
        t1 = starts[i + 1] if i + 1 < len(starts) else X.date.max() + pd.Timedelta(days=1)
        tr = X[(X.date < t0 - pd.Timedelta(days=8)) & X.fwd7.notna()]
        te = X[(X.date >= t0) & (X.date < t1)]
        m = lgb.LGBMClassifier(**PARAMS).fit(tr[cols], (tr.fwd7 > 0).astype(int))
        out.append(te[["date", "asset", "fwd7"]].assign(p_up=m.predict_proba(te[cols])[:, 1]))
    return pd.concat(out, ignore_index=True)


def main(eval_start="2021-07-11"):
    close, dvol, ret = data.load()
    X = timing_features(close, dvol, ret)
    P = walk_forward(X).pivot(index="date", columns="asset", values="p_up")
    sma_on = {a: close[a] > close[a].rolling(100).mean() for a in ASSETS}
    results, curves = {}, {}
    for start in ["2019-01-06", eval_start]:
        rb = [d for d in close.loc[start:].index[:: pf.REBAL_EVERY] if d in P.index]
        S = {
            "BTC buy & hold": {rb[0]: pd.Series({"BTC": 1.0})},
            "BTC trend filter": {d: pd.Series({"BTC": 1.0}) if sma_on["BTC"][d] else pd.Series(dtype=float) for d in rb},
            "BTC AI timing": {d: pd.Series({"BTC": 1.0}) if P.loc[d, "BTC"] > 0.5 else pd.Series(dtype=float) for d in rb},
            "BTC+ETH trend filter": {d: pd.Series({a: 0.5 for a in ASSETS if sma_on[a][d]}, dtype=float) for d in rb},
            "BTC+ETH AI timing": {d: pd.Series({a: 0.5 for a in ASSETS if P.loc[d, a] > 0.5}, dtype=float) for d in rb},
        }
        res = {}
        for name, tg in S.items():
            eq, turn = pf.simulate(ret, tg, start)
            res[name] = pf.stats(eq) | {"weekly_turnover": turn,
                                        "cagr_at_0.5pct_cost": pf.stats(pf.simulate(ret, tg, start, 0.005)[0])["cagr"]}
            if start == eval_start:
                curves[name] = eq
        wk = pd.DataFrame({n: pf.simulate(ret, tg, start)[0] for n, tg in S.items()}).resample("W").last().pct_change().dropna()
        diffs = {}
        for a, b in [("BTC AI timing", "BTC trend filter"), ("BTC+ETH AI timing", "BTC+ETH trend filter"),
                     ("BTC+ETH AI timing", "BTC trend filter")]:
            d = wk[a] - wk[b]
            diffs[f"{a} vs {b}"] = {"weekly_mean": d.mean(), "t": d.mean() / d.std() * np.sqrt(len(d)), "weeks": len(d)}
        results[start] = {"results": res, "diffs": diffs}
    # hit rate of the classifier on non-overlapping weeks
    Pl = walk_forward(X)
    wkd = Pl[Pl.date.isin(sorted(Pl.date.unique())[::7])].dropna(subset=["fwd7"])
    hit = ((wkd.p_up > 0.5) == (wkd.fwd7 > 0)).mean()
    out = {"hit_rate": hit, "base_rate_up": (wkd.fwd7 > 0).mean(), "weeks": len(wkd), "periods": results,
           "curves": {k: [[str(i.date()), round(float(v), 5)] for i, v in c.resample("W").last().items()]
                      for k, c in curves.items()}}
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "reports", "timing_results.json"), "w"), indent=1, default=float)
    print(f"AI timing hit rate {hit:.1%} vs base rate of up weeks {out['base_rate_up']:.1%} (n={len(wkd)} asset-weeks)")
    for start, r in results.items():
        print(f"\n== from {start} ==")
        for k, v in r["results"].items():
            print(f"{k:24s} CAGR {v['cagr']:7.1%}  Sharpe {v['sharpe']:5.2f}  MaxDD {v['maxdd']:6.1%}  "
                  f"turn/wk {v['weekly_turnover'] or 0:5.1%}  CAGR@0.5% {v['cagr_at_0.5pct_cost']:6.1%}")
        for k, v in r["diffs"].items():
            print(f"  {k}: {v['weekly_mean']:+.3%}/wk  t {v['t']:+.2f}")


if __name__ == "__main__":
    main()
