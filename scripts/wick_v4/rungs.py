#!/usr/bin/env python3
"""Wick v4 rung-weight candidates W0-W4 (reports/wick_v4_prereg.md) on the wick1m simulator (v2), bot-like by default
(deeper fills in the parent's own minute dropped). Writes reports/wick_v4/rungs.csv and rungs_daily.parquet."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
import sim  # noqa: E402

W = {"W0": {4.0: 1, 6.0: 1, 8.0: 1}, "W1": {4.0: 2, 6.0: 3, 8.0: 4}, "W2": {4.0: 1, 6.0: 1, 8.0: 2},
     "W3": {4.0: 1, 6.0: 1, 8.0: 1, 10.0: 1}, "W4": {4.0: 4, 6.0: 6, 8.0: 8, 10.0: 10}}
OUT = os.path.join(ROOT, "reports", "wick_v4")


def window(P, lo, hi):
    return P[(P.ts >= lo) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]


def run(P, w, lo, hi, theta, C, drop=True, mtm=False, mult=None, mult_cap=True, out=None):
    """mult / mult_cap: the sizing lab's optional per-row size multiplier (scripts/wick1m/sim.py evaluate); None keeps
    the original sizing. out: a dict that receives the tranche table Q and info, if given."""
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    Q, daily, info = sim.evaluate(window(P, lo, hi), kappa=0.002, trade_list="all", theta=theta, C=C, days=days,
                                  gross_cap=1.0, drop_same_minute=drop, weights=w, mtm=mtm, mult=mult,
                                  mult_cap=mult_cap)
    if out is not None:
        out.update(Q=Q, info=info)
    st = sim.period_stats(daily, C, lo, hi, equity=info.get("equity"))
    st.update(fills=int((Q.fill > 0).sum()), fill_musd=float(Q.fill.sum()) / 1e6, v30_musd=info["v30"] / 1e6)
    idx = pd.date_range(lo, hi, freq="D")
    return st, daily.reindex(idx, fill_value=0.0) / C


def paired_t(a, b, lags=5):
    d = (a - b).to_numpy()
    n = len(d)
    m = d.mean()
    x = d - m
    g = [np.dot(x[k:], x[:n - k]) / n for k in range(lags + 1)]
    var = g[0] + 2 * sum((1 - k / (lags + 1)) * g[k] for k in range(1, lags + 1))
    return m / np.sqrt(var / n) if var > 0 else np.nan


def main():
    P = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", "pre_v4_main.pkl"))
    E = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", "pre_v4_early.pkl"))
    eras = {"selection": (P, sim.SEL), "check": (P, sim.CHK), "fresh_2022_23": (E, sim.EARLY)}
    rows, dailies = [], {}
    for era, (D, (lo, hi)) in eras.items():
        for C in (250e3, 1e6):
            for theta in (0.5, 0.25):
                for drop in ((True, False) if (C == 250e3 and theta == 0.5) else (True,)):
                    for name, w in W.items():
                        st, d = run(D, w, lo, hi, theta, C, drop)
                        rows.append(dict(era=era, capital=C, theta=theta, bot_like=drop, cand=name, **st))
                        dailies[(era, C, theta, drop, name)] = d
    R = pd.DataFrame(rows)
    R["paired_t_vs_W0"] = [paired_t(dailies[(r.era, r.capital, r.theta, r.bot_like, r.cand)],
                                    dailies[(r.era, r.capital, r.theta, r.bot_like, "W0")]) if r.cand != "W0" else np.nan
                           for r in R.itertuples()]
    os.makedirs(OUT, exist_ok=True)
    R.to_csv(os.path.join(OUT, "rungs.csv"), index=False)
    pd.DataFrame({"|".join(map(str, k)): v for k, v in dailies.items()}).to_parquet(os.path.join(OUT, "rungs_daily.parquet"))
    pd.set_option("display.width", 250)
    cols = ["ret_yr", "sharpe", "dollars_yr", "fills", "paired_t_vs_W0"]
    for (C, th, drop), g in R.groupby(["capital", "theta", "bot_like"]):
        print(f"\n=== capital {C:,.0f}  theta {th}  {'bot-like' if drop else 'with same-minute deeper fills'} ===")
        print(g.pivot_table(index="cand", columns="era", values=cols).round(3).to_string())


if __name__ == "__main__":
    main()
