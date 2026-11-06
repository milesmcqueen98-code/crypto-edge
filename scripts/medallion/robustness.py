#!/usr/bin/env python3
"""Checks on any book that passes (run after the hold-out is opened; nothing here selects a book).

For each named book: Sharpe at 2x costs, yearly returns, and $5M capacity (daily dollars traded at the leverage
that gives 50% and 100% a year, vs Coinbase Derivatives volume from reports/cfm_products.csv).

  MEDALLION_HOLDOUT=1 python scripts/medallion/robustness.py F3_knn_BTC [...]
"""
import os
import sys

import numpy as np
import pandas as pd

import books as B
import common as C

sys.path.insert(0, os.path.join(C.ROOT, "scripts"))
import multiasset as ma  # noqa: E402


def rerun(name, mult):
    orig = C.cost_per_side
    scaled = lambda c: mult * orig(c)  # noqa: E731
    B.cost_per_side = scaled
    C_run_daily, C_run_hourly = C.run_daily, C.run_hourly
    B.run_daily = lambda W, close, funding=None, cost=None: C_run_daily(W, close, funding,
                                                                         {c: scaled(c) for c in W.columns})
    B.run_hourly = lambda P, ch, funding_d=None, cost=None: C_run_hourly(P, ch, funding_d,
                                                                          {c: scaled(c) for c in P.columns})
    fam = name.split("_")[0]
    fn = {"F2": B.f2_books, "F3": B.f3_books, "F5a": B.f5_books, "F5b": B.f5_books, "F5c": B.f5_books,
          "F5d": B.f5_books, "F7": lambda: B.f7_books()[0], "F9": B.f9_books, "F6": lambda: B.f6_book()[0]}[fam]
    out = fn()[name]
    B.cost_per_side, B.run_daily, B.run_hourly = orig, C_run_daily, C_run_hourly
    return out


def f9_ladder(coin, haircut=1.0, tenor=30):
    """Stricter short-vol proxy: a ladder of 30-day short variance swaps, one sold each day at (DVOL - haircut)^2,
    marked to market daily at the current DVOL (adds the vega losses of implied-vol spikes that the one-day proxy
    leaves out). Same constant scale rule (20% development vol)."""
    close = C.daily_close([coin])[coin]
    dv = B.dvol(coin).reindex(close.index)
    r2 = (np.log(close).diff() ** 2).to_numpy()
    K = (((dv - haircut) / 100.0) ** 2).to_numpy()          # annualized variance strike sold each day
    T = len(close)
    pnl = np.full(T, np.nan)
    n = 1.0 / tenor                                          # each swap: 1/tenor of the book
    for t in range(tenor + 1, T):
        if np.isnan(K[t]) or np.isnan(K[t - 1]) or np.isnan(r2[t]):
            continue
        tot = 0.0
        for s in range(t - tenor, t):                        # swaps alive over day t (sold at the close of s)
            if np.isnan(K[s]):
                continue
            accrual = K[s] / 365.0 - r2[t]
            left_before = s + tenor - (t - 1)                # days left at the close of t-1
            left_after = left_before - 1
            mtm_before = left_before * (K[s] - K[t - 1]) / 365.0 if s < t - 1 else 0.0
            mtm_after = left_after * (K[s] - K[t]) / 365.0
            tot += n * (accrual + mtm_after - mtm_before)
        pnl[t] = tot
    x = pd.Series(pnl, index=close.index).dropna()
    k = 0.20 / (x.loc[C.DEV[0]:C.DEV[1]].std() * np.sqrt(365))
    return k * x


def knn_variants(coin="BTC"):
    """Neighbour-count sensitivity for F3 (k = 25, 100 vs the registered 50). Diagnostic only."""
    close = C.daily_close([coin])
    unit = C.vol_unit(close)[coin]
    out = {}
    for k in (25, 50, 100):
        pred = B.knn_pred(coin, k=k).reindex(close.index)
        W = pd.DataFrame({coin: (np.sign(pred) * unit).fillna(0.0).clip(-2, 2)})
        out[k] = C.run_daily(W, close)[0]
    return out


def cde_volume_usd():
    p = pd.read_csv(os.path.join(C.ROOT, "reports", "cfm_products.csv"))
    p = p[p.expiry_type == "PERPETUAL"]
    p["usd"] = p.volume_24h * p.contract_size * p.price
    p["oi_usd"] = p.open_interest * p.contract_size * p.price
    return p.groupby("contract_root_unit")[["usd", "oi_usd"]].sum()


def main():
    vol = cde_volume_usd()
    rows = []
    for name in sys.argv[1:]:
        x1, turn = rerun(name, 1.0)
        x2, _ = rerun(name, 2.0)
        row = dict(book=name, sharpe_dev=C.sharpe(x1, *C.DEV), sharpe_hold=C.sharpe(x1, *C.HOLD),
                   sharpe_dev_2x=C.sharpe(x2, *C.DEV), sharpe_hold_2x=C.sharpe(x2, *C.HOLD))
        yr = (1 + x1.loc["2017-07-01":] + C.book.rf_daily(x1.loc["2017-07-01":].index)).groupby(
            x1.loc["2017-07-01":].index.year).prod() - 1
        row.update({f"y{y}": v for y, v in yr.items()})
        for tgt in (0.5, 1.0):
            L, dd = ma.lever_for(x1, tgt)
            row[f"lev_{int(tgt * 100)}"], row[f"maxdd_{int(tgt * 100)}"] = L, dd
            traded = float(turn.loc[C.HOLD[0]:].mean()) * 5e6 * (L if np.isfinite(L) else 1.0)
            row[f"usd_traded_day_{int(tgt * 100)}"] = traded
        coins = [c for c in C.COINS if c in name] or ["BTC", "ETH"]
        v = vol.reindex(coins).usd.sum()
        row["cde_perp_usd_volume_day"] = float(v)
        row["share_of_volume_100"] = row["usd_traded_day_100"] / v if v else np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    C.save(df, "robustness.csv")
    pd.set_option("display.width", 250)
    print(df.T.to_string())


if __name__ == "__main__":
    main()
