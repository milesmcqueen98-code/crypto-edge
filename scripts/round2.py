#!/usr/bin/env python3
"""Round 2: can anything, AI or not, beat the live rule? Fixed before running:

A  Live: 50/50 BTC/ETH while BTC closes above its 100-day SMA, else cash (checked daily).
B  Ensemble trend: exposure = share of BTC's {50,100,150,200}-day SMAs it closes above (0-100%).
C  Vol-targeted trend: A, but exposure = min(1, 60% / basket's 30-day annualised vol), resized weekly.
D  AI picks within the majors: when A is on, hold the AI ranker's top 2 of the 5 most liquid
   coins that day (refreshed weekly) instead of fixed BTC/ETH. Window: Jul 2021+ (AI preds).
E  Funding overlay: A, but half exposure when avg BTC/ETH 7-day perp funding is above its
   trailing 80th percentile (expanding window, >=180 days of history). Window: 2024+.

Pass bar: higher Sharpe than A AND weekly-return-difference t-stat > 2.5 (Bonferroni for 4 tries).
Weekly-refresh rules are averaged over all 7 weekday phases.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import data, features, portfolio as pf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B5050 = pd.Series({"BTC": 0.5, "ETH": 0.5})


def to_targets(weights_by_day):
    """Only emit a rebalance when target weights actually change."""
    out, prev = {}, None
    for d, w in weights_by_day.items():
        w = w[w > 1e-9]
        if prev is None or set(w.index) != set(prev.index) or (w - prev).abs().max() > 1e-6:
            out[d] = w
            prev = w
    return out


def main():
    close, dvol, ret = data.load()
    btc = close["BTC"]
    sma = {n: btc.rolling(n).mean() for n in (50, 100, 150, 200)}
    on = btc > sma[100]
    ens = sum((btc > sma[n]).astype(float) for n in sma) / len(sma)
    basket_ret = ret[["BTC", "ETH"]].mean(axis=1)
    bvol = basket_ret.rolling(30).std() * np.sqrt(365)

    univ, v30 = features.universe(close, dvol)
    P = pd.read_parquet(os.path.join(ROOT, "reports", "preds_cache.parquet")).pivot(
        index="date", columns="asset", values="pred")

    fund = data.load_funding()
    f7 = fund[["BTC", "ETH"]].mean(axis=1).rolling(7, min_periods=5).sum() if len(fund) else pd.Series(dtype=float)
    f_thr = f7.expanding(min_periods=180).quantile(0.8)
    crowded = (f7 > f_thr).reindex(close.index).fillna(False)

    def A(idx, ph):
        return to_targets({d: B5050 if on[d] else pd.Series(dtype=float) for d in idx})

    def Bf(idx, ph):
        return to_targets({d: B5050 * ens[d] for d in idx})

    def C(idx, ph):
        weekly, out, size = set(idx[ph::7]), {}, None
        for d in idx:
            if not on[d]:
                out[d], size = pd.Series(dtype=float), None
                continue
            if size is None or d in weekly:
                size = float(min(1.0, 0.60 / bvol[d])) if bvol[d] > 0 else 1.0
            out[d] = B5050 * size
        return to_targets(out)

    def D(idx, ph):
        weekly, out, held = set(idx[ph::7]), {}, None
        for d in idx:
            if not on[d] or d not in P.index:
                out[d], held = pd.Series(dtype=float), None
                continue
            if held is None or d in weekly:
                majors = v30.loc[d].where(univ.loc[d]).dropna().nlargest(5).index
                s = P.loc[d, [m for m in majors if m in P.columns]].dropna().nlargest(2)
                held = pd.Series(1.0 / len(s), index=s.index) if len(s) else B5050
            out[d] = held
        return to_targets(out)

    def E(idx, ph):
        return to_targets({d: (B5050 * (0.5 if crowded[d] else 1.0)) if on[d] else pd.Series(dtype=float) for d in idx})

    tests = [("A Live rule", A, False), ("B Ensemble trend", Bf, False), ("C Vol-targeted trend", C, True),
             ("D AI picks top 2 of 5 majors", D, True), ("E Funding-crowding overlay", E, False)]
    windows = {"7 years (Nov 2019+)": "2019-11-06", "Out-of-sample AI window (Jul 2021+)": "2021-07-01",
               "Funding window (Jan 2024+)": "2024-01-01"}
    rows = []
    for wname, start in windows.items():
        idx = close.loc[start:].index
        base_wk = None
        for name, fn, phased in tests:
            if name.startswith("D") and start < "2021-07-01":
                continue
            if name.startswith("E") and start < "2024-01-01":
                continue
            runs, curves = [], []
            for ph in (range(7) if phased else [0]):
                eq, _ = pf.simulate(ret, fn(idx, ph), start)
                runs.append(pf.stats(eq))
                curves.append(eq)
            eq = pd.concat(curves, axis=1).mean(axis=1)
            wk = eq.resample("W").last().pct_change().dropna()
            if name.startswith("A"):
                base_wk = wk
                t = np.nan
            else:
                dlt = (wk - base_wk).dropna()
                t = dlt.mean() / dlt.std() * np.sqrt(len(dlt))
            rows.append(dict(window=wname, test=name, cagr=np.mean([r["cagr"] for r in runs]),
                             sharpe=np.mean([r["sharpe"] for r in runs]), maxdd=np.mean([r["maxdd"] for r in runs]),
                             t_vs_A=t))
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    for w, g in df.groupby("window", sort=False):
        print(f"\n== {w} ==")
        a = g.iloc[0]
        for _, r in g.iterrows():
            verdict = "" if r.test.startswith("A") else (
                "PASS" if (r.sharpe > a.sharpe and r.t_vs_A > 2.5) else "fail")
            print(f"  {r.test:32s} CAGR {r.cagr:6.1%}  Sharpe {r.sharpe:.2f}  MaxDD {r.maxdd:5.0%}  "
                  f"t vs A {'' if np.isnan(r.t_vs_A) else f'{r.t_vs_A:+.2f}':>6s}  {verdict}")
    df.to_csv(os.path.join(ROOT, "reports", "round2.csv"), index=False)
    print(f"\nfunding coverage: {f7.dropna().index.min().date() if len(f7.dropna()) else None} -> "
          f"{f7.dropna().index.max().date() if len(f7.dropna()) else None}; crowded share since 2024: "
          f"{crowded.loc['2024':].mean():.0%}")


if __name__ == "__main__":
    main()
