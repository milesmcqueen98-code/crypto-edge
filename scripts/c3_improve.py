#!/usr/bin/env python3
"""C3 improvement round (pre-registered in reports/maker_prereg.md, "If nothing passes").

C3 = risk parity of the live rule (W_L) and the hourly EWMAC long/short (W_H) on Coinbase nano perps.
Variants (3 trials): B = EWMAC buffer 0.25 x unit (was 0.10); F = drop the 4/16 h speed (FDM 1.19 over 5);
BF = both. Weights stay at C3's development-period risk-parity values for every variant.

All books are run as ONE netted book (sleeve trades offset each other, as they would in one account).
Costs per unit traded: (a) 0.04% both coins; (b) realistic nano-perp cost BTC 2.5 bp, ETH 6.5 bp, positions
rounded to whole contracts (0.01 BTC, 0.1 ETH) at $10K; (c) 2 x (b). Funding and T-bill margin drag as in
edge/intraday.py. Writes reports/c3_improve.csv and reports/c3_improve_returns.parquet.
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge import book, intraday as ih  # noqa: E402
import intraday_search as s1  # noqa: E402

PER = {"dev": ("2019-11-06", "2023-12-31"), "recent": ("2024-01-01", None), "early": ("2017-07-01", "2019-11-05"),
       "7y": ("2019-11-06", None), "full": ("2017-07-01", None)}
SPEEDS = [(4, 16), (8, 32), (16, 64), (32, 128), (64, 256), (128, 512)]
CONTRACT = {"BTC": 0.01, "ETH": 0.1}
COSTS = {"a": {"BTC": 4e-4, "ETH": 4e-4}, "b": {"BTC": 2.5e-4, "ETH": 6.5e-4}, "c": {"BTC": 5e-4, "ETH": 13e-4}}
ROUND = {"a": False, "b": True, "c": True}
CAPITAL = 10_000.0
N_TRIALS = 476


def ewmac(drop_fast=False, buffer=0.10):
    close, r = s1.close_h, s1.r_h
    vh = r.ewm(span=768, min_periods=240).std()
    vann = (vh * np.sqrt(8760)).clip(lower=0.10)
    comb = []
    for f, s in (SPEEDS[1:] if drop_fast else SPEEDS):
        raw = (close.ewm(span=f, min_periods=f).mean() - close.ewm(span=s, min_periods=s).mean()) / (close * vh)
        scal = 10.0 / raw.abs().mean(axis=1).expanding(min_periods=24 * 365).mean()
        comb.append(raw.mul(scal, axis=0).clip(-20, 20))
    F = (sum(comb) / len(comb) * (1.19 if drop_fast else 1.26)).clip(-20, 20)
    unit = 1.05 * 0.5 * 0.25 / vann
    pos = book.buffer_positions((F / 10 * unit).fillna(0.0), buffer * unit)
    return book.cap_gross(pos.fillna(0.0), 2.0)


def engine(P, cost, rounding):
    close = s1.close_h
    P = P.reindex(close.index).fillna(0.0)
    r = close.pct_change(fill_method=None).fillna(0.0)
    if rounding:
        cu = pd.DataFrame({a: CONTRACT[a] * close[a] for a in P.columns})
        n = (P * CAPITAL / cu).round().fillna(0.0)
        held_frac = (n * cu / CAPITAL).fillna(0.0)
        traded = (n.diff().abs() * cu / CAPITAL).fillna(0.0)
    else:
        held_frac = P
        traded = P.diff().abs().fillna(0.0)
    held = held_frac.shift(1).fillna(0.0)
    pnl = (held * r[P.columns]).sum(axis=1) - (held * s1.FUND[P.columns]).sum(axis=1)
    tc = sum(traded[a] * cost[a] for a in P.columns)
    day = close.index.floor("D")
    rf_day = book.rf_daily(pd.DatetimeIndex(day.unique()))
    rf_h = pd.Series(day.map(rf_day).to_numpy(), index=close.index) / 24.0
    margin = ih.MARGIN_SHARE * (held.abs().sum(axis=1) > 0).astype(float)
    ex = pnl - tc - margin * rf_h
    turn = traded.sum(axis=1).groupby(close.index.year).sum()
    return ex.groupby(day).sum(), turn


def yearly(x, lev=1.0):
    xx = lev * x.loc["2017-07-01":]
    return (1 + xx + book.rf_daily(xx.index)).groupby(xx.index.year).prod() - 1


def memmel(a, b, start, end=None):
    d = pd.concat([a, b], axis=1).loc[start:end].dropna()
    T = len(d)
    s_a, s_b = (d.mean() / d.std()).values
    rho = d.corr().iloc[0, 1]
    z = (s_a - s_b) / np.sqrt((2 - 2 * rho + 0.5 * (s_a ** 2 + s_b ** 2 - 2 * s_a * s_b * rho ** 2)) / T)
    return float(z), float(2 * (1 - norm.cdf(abs(z))))


def dsr(x, n_trials):
    srs = pd.read_csv(os.path.join(ROOT, "reports", "book_results.csv")).full_sharpe.dropna().values / np.sqrt(365)
    emc = 0.5772156649
    sr0 = np.std(srs, ddof=1) * ((1 - emc) * norm.ppf(1 - 1 / n_trials) + emc * norm.ppf(1 - 1 / (n_trials * np.e)))
    r = x.loc["2017-07-01":].dropna()
    sr = r.mean() / r.std()
    z = (sr - sr0) * np.sqrt(len(r) - 1) / np.sqrt(1 - skew(r) * sr + (kurtosis(r, fisher=False) - 1) / 4 * sr ** 2)
    return float(norm.cdf(z))


def main():
    live_P = s1.to_hourly(s1.live_daily())
    base_hls = ewmac()
    # C3 weights exactly as before: inverse dev-period vol of each sleeve run on its own at 0.04%
    live_r = ih.run(live_P, s1.close_h)
    hls_r = ih.run(base_hls, s1.close_h)
    wl, wh = 1 / live_r.loc[PER["dev"][0]:PER["dev"][1]].std(), 1 / hls_r.loc[PER["dev"][0]:PER["dev"][1]].std()
    W_L, W_H = wl / (wl + wh), wh / (wl + wh)
    print(f"weights: live {W_L:.3f}, hourly L/S {W_H:.3f}")
    books = {"C3": base_hls, "C3-B": ewmac(buffer=0.25), "C3-F": ewmac(drop_fast=True),
             "C3-BF": ewmac(drop_fast=True, buffer=0.25)}
    rows, rets = [], {}
    for name, hls in books.items():
        P = W_L * live_P.reindex(hls.index).fillna(0.0) + W_H * hls
        for ck in ("a", "b", "c"):
            x, turn = engine(P, COSTS[ck], ROUND[ck])
            rets[f"{name}|{ck}"] = x
            row = dict(book=name, cost=ck, turnover_yr=float(turn.loc[2018:2025].mean()))
            for p, (s_, e_) in PER.items():
                row[f"sharpe_{p}"] = book.sharpe(x, s_, e_)
            for lev in (1.0, 1.5):
                st = book.summary(lev * x, "2019-11-06")
                row[f"cagr7y_x{lev}"], row[f"dd7y_x{lev}"] = st["cagr"], st["maxdd"]
                stf = book.summary(lev * x, "2017-07-01")
                row[f"ddfull_x{lev}"] = stf["maxdd"]
            for y, v in yearly(x).items():
                row[f"y{y}"] = v
            for y, v in yearly(x, 1.5).items():
                row[f"y{y}_x1.5"] = v
            rows.append(row)
    tab = pd.DataFrame(rows)
    for ck in ("a", "b", "c"):
        for name in books:
            if name == "C3":
                continue
            for p in ("dev", "recent", "early", "7y"):
                z, pv = memmel(rets[f"{name}|{ck}"], rets[f"C3|{ck}"], *PER[p])
                tab.loc[(tab.book == name) & (tab.cost == ck), f"z_vs_C3_{p}"] = z
    for k, x in rets.items():
        name, ck = k.split("|")
        tab.loc[(tab.book == name) & (tab.cost == ck), "dsr_full"] = dsr(x, N_TRIALS)
    tab.to_csv(os.path.join(ROOT, "reports", "c3_improve.csv"), index=False)
    pd.DataFrame(rets).to_parquet(os.path.join(ROOT, "reports", "c3_improve_returns.parquet"))

    # pre-registered replacement rule (cost b)
    b = tab[tab.cost == "b"].set_index("book")
    winners = [n for n in books if n != "C3" and b.loc[n, "sharpe_dev"] > b.loc["C3", "sharpe_dev"]
               and b.loc[n, "sharpe_recent"] >= b.loc["C3", "sharpe_recent"] and b.loc[n, "sharpe_early"] >= b.loc["C3", "sharpe_early"]]
    pick = max(winners, key=lambda n: b.loc[n, "sharpe_dev"]) if winners else "C3"
    pd.set_option("display.width", 250)
    cols = ["book", "cost", "turnover_yr", "sharpe_dev", "sharpe_recent", "sharpe_early", "sharpe_7y", "sharpe_full",
            "cagr7y_x1.0", "dd7y_x1.0", "cagr7y_x1.5", "dd7y_x1.5", "ddfull_x1.5", "dsr_full"]
    print(tab[cols].round(3).to_string(index=False))
    yc = [c for c in tab.columns if c.startswith("y") and not c.endswith("x1.5")]
    print(tab[["book", "cost"] + yc].round(3).to_string(index=False))
    print(tab[["book", "cost"] + [c for c in tab.columns if c.startswith("z_vs")]].round(2).to_string(index=False))
    print(f"\nReplacement rule (cost b): qualifying {winners or 'none'} -> book = {pick}")


if __name__ == "__main__":
    main()
