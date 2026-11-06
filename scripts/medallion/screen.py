#!/usr/bin/env python3
"""Signal screen (F0 placebo, F1 positioning/sentiment, F4 return sequences, F8 alternative data).

Each signal: rolling z-score (365 days, 90 minimum) vs the forward Coinbase return over 1 and 7 days, BTC and ETH.
Rank IC with a Newey-West t-stat (lags = horizon). Pass: development |t| >= 3, then hold-out same sign, |t| >= 2.
Hold-out columns are filled only with MEDALLION_HOLDOUT=1. Writes reports/medallion/screen.csv.
"""
import numpy as np
import pandas as pd

from common import DEV, HOLD, HOLDOUT_OPEN, ic_nw, save
from features import etf_flows, z_signals


def main():
    rows = []
    for coin in ("BTC", "ETH"):
        Z, raw, close = z_signals(coin)
        for h in (1, 7):
            fwd = close.shift(-h) / close - 1
            for s in Z.columns:
                d = ic_nw(Z[s], fwd, *DEV, lags=h)
                row = dict(coin=coin, signal=s, family=s[:2], h=h, ic_dev=d["ic"], t_dev=d["t"], n_dev=d["n"],
                           first=str(raw[s].first_valid_index().date()) if raw[s].notna().any() else "")
                if HOLDOUT_OPEN:
                    o = ic_nw(Z[s], fwd, *HOLD, lags=h)
                    row.update(ic_hold=o["ic"], t_hold=o["t"], n_hold=o["n"])
                rows.append(row)
        if HOLDOUT_OPEN:                                    # ETF flows start inside the hold-out: described only
            f = etf_flows(coin)
            if f is not None and f.notna().sum() > 60:
                f = f.copy()
                f.index = f.index + pd.Timedelta(days=1)    # one-day publication lag
                sig = f.reindex(close.index)
                for h in (1, 7):
                    fwd = close.shift(-h) / close - 1
                    o = ic_nw(sig, fwd, *HOLD, lags=h)
                    rows.append(dict(coin=coin, signal="F8_etf_flow (descriptive)", family="F8", h=h,
                                     ic_hold=o["ic"], t_hold=o["t"], n_hold=o["n"],
                                     first=str(f.index.min().date())))
    df = pd.DataFrame(rows)
    df["dev_pass"] = df.t_dev.abs() >= 3
    if HOLDOUT_OPEN:
        df["pass"] = df.dev_pass & (np.sign(df.t_hold) == np.sign(df.t_dev)) & (df.t_hold.abs() >= 2)
    save(df, "screen.csv")
    pd.set_option("display.width", 220)
    print(df.sort_values("t_dev", key=abs, ascending=False).head(40).to_string(index=False))
    print("\nsignals:", df.signal.nunique(), "tests:", df.t_dev.notna().sum(), "dev passes:", int(df.dev_pass.sum()))
    if HOLDOUT_OPEN:
        print("full passes:", int(df["pass"].sum()))


if __name__ == "__main__":
    main()
