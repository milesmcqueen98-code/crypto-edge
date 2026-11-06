#!/usr/bin/env python3
"""Creative round 2 (exploratory, built on round 1's one useful finding: fast hourly trend
makes money in bear markets, and its returns are only 0.27 correlated with the live rule).

  H7a  Hybrid: live daily rule for longs + hourly-EWMAC shorts only in bear regimes (BTC < SMA100).
  H7b  Regime-filtered hourly EWMAC: longs only in bull regimes, shorts only in bear regimes.
  H8   Hourly EWMAC long/short across 9 coins with US-listed perps (BTC ETH SOL XRP DOGE LTC ADA AVAX LINK),
       equal risk, IDM 1.25.
  C1   50/50 capital: live rule (perps) + hourly EWMAC long/short BTC/ETH (perps).
  C2   Risk parity (weights from development-period volatility): live rule + H8.
  H9   AI allocator: LightGBM picks the book (live rule vs H8) more likely to win next week;
       75/25 tilt, walk-forward from 2019.
Each combo is also shown levered to the live rule's development-period volatility ("similar upside").
"""
import os
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from edge import book, intraday as ih  # noqa: E402
import intraday_search as s1  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COINS9 = ["BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "ADA", "AVAX", "LINK"]
PER = s1.PER
TARGET = 0.25
DOWN_YEARS = None


def ewmac_forecast(close, r):
    speeds = [(4, 16), (8, 32), (16, 64), (32, 128), (64, 256), (128, 512)]
    vh = r.ewm(span=768, min_periods=240).std()
    comb = []
    for f, s in speeds:
        raw = (close.ewm(span=f, min_periods=f).mean() - close.ewm(span=s, min_periods=s).mean()) / (close * vh)
        scal = 10.0 / raw.abs().mean(axis=1).expanding(min_periods=24 * 365).mean()
        comb.append(raw.mul(scal, axis=0).clip(-20, 20))
    F = (sum(comb) / len(comb) * 1.26).clip(-20, 20)
    return F, (vh * np.sqrt(8760)).clip(lower=0.10)


def positions(F, vann, weight, idm, cap=2.0):
    unit = idm * weight * TARGET / vann
    pos = book.buffer_positions((F / 10 * unit).fillna(0.0), 0.1 * unit)
    return book.cap_gross(pos.fillna(0.0), cap)


def regime_hourly():
    up_d = (s1.close_d.BTC > s1.close_d.BTC.rolling(100).mean()).astype(float)
    return s1.to_hourly(pd.DataFrame({"x": up_d}))["x"]           # yesterday's daily state, held next day


def yearly(x):
    xx = x.loc["2017-07-01":]
    return (1 + xx + book.rf_daily(xx.index)).groupby(xx.index.year).prod() - 1


def report(name, x, down):
    st = {p: book.summary(x, *PER[p]) for p in PER}
    y = yearly(x)
    dy = {int(k): v for k, v in y.items() if k in down}
    print(f"  {name:58s} dev {st['dev']['sharpe']:5.2f} | recent {st['recent']['sharpe']:5.2f} | early {st['early']['sharpe']:5.2f} | "
          f"7y {st['7y']['sharpe']:5.2f} CAGR {st['7y']['cagr']:6.1%} DD {st['7y']['maxdd']:5.0%} | down years: "
          + ", ".join(f"{k} {v:+.0%}" for k, v in dy.items()), flush=True)
    return dict(strategy=name, **{f"{p}_{k}": v for p, d in st.items() for k, v in d.items()},
                **{f"y{k}": v for k, v in y.items()})


def main():
    btc_y = s1.close_d.BTC.groupby(s1.close_d.index.year).last().pct_change()
    down = [int(y) for y, v in btc_y.items() if v < 0 and y >= 2017]
    print("BTC down years:", {y: f"{btc_y[y]:+.0%}" for y in down})
    rows, streams = [], {}
    R1 = pd.read_parquet(os.path.join(ROOT, "reports", "intraday_returns.parquet"))
    live = R1["Live rule, Coinbase perps"]
    hls = R1["H1 Hourly EWMAC, long/short (perps)"]
    rows.append(report("Live rule (perps) [benchmark]", live, down))
    rows.append(report("H1 Hourly EWMAC long/short BTC/ETH", hls, down))

    # H7a / H7b on BTC/ETH
    close2, r2 = s1.close_h, s1.r_h
    F2, v2 = ewmac_forecast(close2, r2)
    reg = regime_hourly().reindex(close2.index).fillna(0.0)
    Wl_h = s1.to_hourly(s1.live_daily())
    shorts = positions(F2.clip(upper=0).mul(1 - reg, axis=0), v2, 0.5, 1.05)
    x = ih.run(book.cap_gross(Wl_h + shorts, 2.0), close2)
    streams["H7a"] = x
    rows.append(report("H7a Live longs + hourly shorts in bear regime", x, down))
    Fb = F2.clip(lower=0).mul(reg, axis=0) + F2.clip(upper=0).mul(1 - reg, axis=0)
    x = ih.run(positions(Fb, v2, 0.5, 1.05), close2)
    streams["H7b"] = x
    rows.append(report("H7b Regime-filtered hourly EWMAC", x, down))

    # H8 multi-coin hourly EWMAC long/short
    close9, vol9 = ih.load_hourly(COINS9)
    close9 = close9.reindex(close2.index)
    r9 = close9.pct_change(fill_method=None)
    F9, v9 = ewmac_forecast(close9, r9)
    n_live = close9.notna().sum(axis=1).clip(lower=1)
    w9 = (1.0 / n_live)
    P9 = positions(F9, v9.mul(1, axis=0), 1.0, 1.25)
    P9 = P9.mul(w9, axis=0)                                       # equal weight across listed coins
    x8 = ih.run(P9, close9)
    streams["H8"] = x8
    rows.append(report("H8 Hourly EWMAC long/short, 9 coins", x8, down))

    # combos
    dev = slice(*PER["dev"])
    c1 = 0.5 * live + 0.5 * hls
    rows.append(report("C1 50% live + 50% hourly L/S BTC/ETH", c1, down))
    wl, w8 = 1 / live.loc[dev].std(), 1 / x8.loc[dev].std()
    c2 = (wl * live + w8 * x8) / (wl + w8)
    rows.append(report("C2 Risk parity: live + H8", c2, down))
    wl2, wh2 = 1 / live.loc[dev].std(), 1 / hls.loc[dev].std()
    c3 = (wl2 * live + wh2 * hls) / (wl2 + wh2)
    rows.append(report("C3 Risk parity: live + hourly L/S BTC/ETH", c3, down))

    # H9 AI allocator between live rule and H8
    books = pd.DataFrame({"live": live, "h8": x8}).dropna()
    wk = books.resample("W-SUN").sum()
    feat = pd.DataFrame(index=wk.index)
    for k in (1, 4, 12):
        feat[f"live_{k}"] = wk.live.rolling(k).sum()
        feat[f"h8_{k}"] = wk.h8.rolling(k).sum()
    bd = s1.close_d.BTC.resample("W-SUN").last()
    feat["btc_4w"] = bd.pct_change(4)
    feat["btc_vs_sma"] = (s1.close_d.BTC / s1.close_d.BTC.rolling(100).mean() - 1).resample("W-SUN").last()
    feat["btc_vol"] = s1.close_d.BTC.pct_change().rolling(30).std().resample("W-SUN").last()
    y = (wk.h8.shift(-1) > wk.live.shift(-1)).astype(float).where(wk.live.shift(-1).notna())
    tilt = pd.Series(np.nan, index=wk.index)
    for t0 in pd.date_range("2019-01-01", wk.index[-1], freq="QS"):
        t1 = t0 + pd.offsets.QuarterBegin(1)
        tr = feat[(feat.index < t0 - pd.Timedelta(days=8))].join(y.rename("y")).dropna()
        te = feat[(feat.index >= t0) & (feat.index < t1)].dropna()
        if len(tr) < 80 or te.empty:
            continue
        m = lgb.LGBMClassifier(objective="binary", learning_rate=0.03, num_leaves=5, min_data_in_leaf=20,
                               n_estimators=150, lambda_l2=5.0, verbose=-1, seed=7, num_threads=2)
        m.fit(tr.drop(columns="y"), tr.y.astype(int))
        tilt.loc[te.index] = m.predict_proba(te)[:, 1]
    a8 = np.where(tilt > 0.5, 0.75, 0.25)
    a8 = pd.Series(a8, index=wk.index).where(tilt.notna())
    a8d = a8.shift(1).reindex(books.index, method="ffill")           # decided at week end, applied next week
    nl, n8 = live / live.loc[dev].std(), x8 / x8.loc[dev].std()       # equal-risk units
    scale = 1 / (1 / live.loc[dev].std() + 1 / x8.loc[dev].std()) * 2
    h9 = ((1 - a8d) * nl + a8d * n8) * scale / 2
    h9 = h9.where(a8d.notna(), c2.reindex(h9.index))
    rows.append(report("H9 AI allocator (live vs H8)", h9, down))
    hit = ((tilt > 0.5) == (y > 0)).where(tilt.notna() & y.notna()).dropna().mean()
    print(f"     AI allocator hit rate {hit:.1%}")

    # levered to the live rule's development-period volatility ("similar upside")
    print("\nLevered to the live rule's development-period volatility:")
    target = live.loc[dev].std()
    for nm, x in [("C1 levered", c1), ("C2 levered", c2), ("C3 levered", c3), ("H7a levered", streams["H7a"]),
                  ("H9 levered", h9)]:
        k = target / x.loc[dev].std()
        rows.append(report(f"{nm} (x{k:.1f})", x * k, down))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(ROOT, "reports", "intraday_results2.csv"), index=False)
    out = pd.DataFrame({"C1": c1, "C2": c2, "C3": c3, "H7a": streams["H7a"], "H7b": streams["H7b"], "H8": x8, "H9": h9})
    out.to_parquet(os.path.join(ROOT, "reports", "intraday_returns2.parquet"))


if __name__ == "__main__":
    main()
