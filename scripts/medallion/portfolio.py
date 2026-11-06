#!/usr/bin/env python3
"""Portfolio step of the Medallion round (reports/medallion_prereg.md, "Pass bars and combination").

Passing books (development Sharpe >= 1.0, hold-out >= 0.5, same sign) are added to C3 by inverse development
volatility. The combination replaces C3 only if its development Sharpe is higher and neither out-of-sample period
(hold-out 2024+, and the pre-development period 2017-07 to 2019-12 where a book has data) is worse.
Also reports: every book's correlation with C3, deflated Sharpe (N = 484 + 17), leverage for 50% / 100% a year,
and $5M capacity of anything kept. Needs MEDALLION_HOLDOUT=1. Writes reports/medallion/portfolio.csv, .json.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

from common import DEV, HOLD, N_BOOKS, N_PRIOR, OUT, book, save, sharpe

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import c3_improve as c3i  # noqa: E402
import multiasset as ma  # noqa: E402

EARLY = ("2017-07-01", "2019-12-31")


def load_books():
    tabs = pd.concat([pd.read_csv(p) for p in sorted(glob.glob(os.path.join(OUT, "books_*.csv")))], ignore_index=True)
    R = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(os.path.join(OUT, "books_*_returns.parquet")))],
                  axis=1)
    return tabs.drop_duplicates("book", keep="last"), R.loc[:, ~R.columns.duplicated(keep="last")]


def combine(series, dev=DEV):
    w = {k: 1.0 / v.loc[dev[0]:dev[1]].std() for k, v in series.items()}
    s = sum(w.values())
    w = {k: v / s for k, v in w.items()}
    df = pd.DataFrame(series)
    W = pd.DataFrame({k: np.where(df[k].notna(), w[k], 0.0) for k in series}, index=df.index)
    W = W.div(W.sum(axis=1), axis=0)                  # weights renormalized over the books trading that day
    x = (W * df.fillna(0.0)).sum(axis=1)
    return x.loc[df.dropna(how="all").index.min():], w


def main():
    tabs, R = load_books()
    c3, _ = ma.c3_returns("b")
    rows = []
    for name in R.columns:
        x = R[name]
        d = pd.concat([x, c3], axis=1).loc[DEV[0]:HOLD[1]].dropna()
        rows.append(dict(book=name, corr_c3=float(d.corr().iloc[0, 1]),
                         sharpe_early=sharpe(x, *EARLY)))
    corr = pd.DataFrame(rows)
    tabs = tabs.merge(corr, on="book", how="left")
    passing = list(tabs.loc[tabs.passes.astype(bool), "book"])
    base = dict(sharpe_dev=sharpe(c3, *DEV), sharpe_hold=sharpe(c3, *HOLD), sharpe_early=sharpe(c3, *EARLY))
    res = dict(passing=passing, c3=base)
    if passing:
        series = {"C3": c3, **{k: R[k] for k in passing}}
        x, w = combine(series)
        cand = dict(sharpe_dev=sharpe(x, *DEV), sharpe_hold=sharpe(x, *HOLD), sharpe_early=sharpe(x, *EARLY),
                    weights=w)
        better = cand["sharpe_dev"] > base["sharpe_dev"] and cand["sharpe_hold"] >= base["sharpe_hold"] and (
            np.isnan(cand["sharpe_early"]) or cand["sharpe_early"] >= base["sharpe_early"] - 1e-9)
        res.update(candidate=cand, replaces_c3=bool(better))
        kept = x if better else c3
        save(pd.DataFrame({"C3": c3, "combined": x}), "portfolio_returns.parquet")
    else:
        res.update(replaces_c3=False)
        kept = c3
    res["kept"] = "combined" if res.get("replaces_c3") else "C3"
    res["dsr_kept"] = c3i.dsr(kept, N_PRIOR + N_BOOKS)
    for tgt in (0.5, 1.0):
        L, dd = ma.lever_for(kept, tgt)
        res[f"lev_{int(tgt * 100)}"] = dict(leverage=L, maxdd=dd)
    st = book.summary(kept, "2017-07-01")
    res["kept_full"] = dict(sharpe=st["sharpe"], cagr=st["cagr"], maxdd=st["maxdd"])
    save(tabs, "portfolio_books.csv")
    with open(os.path.join(OUT, "portfolio.json"), "w") as fh:
        json.dump(res, fh, indent=2, default=float)
    pd.set_option("display.width", 250)
    print(tabs[["book", "sharpe_dev", "sharpe_hold", "sharpe_early", "corr_c3", "passes"]].to_string(index=False))
    print(json.dumps(res, indent=2, default=float))


if __name__ == "__main__":
    main()
