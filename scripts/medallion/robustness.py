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
