#!/usr/bin/env python3
"""Apply the trend v2 bars (reports/trend_v2_prereg.md) to scripts/trend_lab.py output.
Usage: python scripts/trend_analyze.py [tag ...]   (default: round1)"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge.book import rf_daily  # noqa: E402
import trend_lab as TL  # noqa: E402

OUT = TL.OUT


def load(tags):
    R = pd.concat([pd.read_csv(os.path.join(OUT, f"results_{t}.csv")) for t in tags]).drop_duplicates("key", keep="last")
    D = pd.concat([pd.read_parquet(os.path.join(OUT, f"daily_{t}.parquet")) for t in tags], axis=1)
    D = D.loc[:, ~D.columns.duplicated(keep="last")]
    return R.set_index("key"), D


def excess(D):
    rf = rf_daily(D.index).reindex(D.index).fillna(0.0)
    return D.sub(rf, axis=0)


def sharpe(x):
    return x.mean() / x.std() * np.sqrt(365) if x.std() > 0 else np.nan


def paired_t_weekly(a, b):
    d = (a - b).resample("W").sum()
    return d.mean() / d.std() * np.sqrt(len(d))


def years(D, cols):
    Y = (1 + D[cols]).groupby(D.index.year).prod() - 1
    return Y


# ---------------------------------------------------------------- cross-market check (single asset, daily UTC closes)
def daily_close(sym):
    p = os.path.join(ROOT, "data", "prices", f"{sym}.csv")
    if os.path.exists(p):
        d = pd.read_csv(p, parse_dates=["date"]).set_index("date").close.astype(float)
        return d, 0.0010
    d = pd.read_csv(os.path.join(ROOT, "data", "etf", f"{sym}.csv"))
    d.columns = [c.lower() for c in d.columns]
    d = d.set_index(pd.to_datetime(d["date"])).close.astype(float)
    return d, 0.0002


def single_asset(close, cost, rule):
    """rule: 'live' (close > SMA100) or a signal dict like the lab's. Long 100% / cash. Excess daily returns."""
    v = dict(rule)
    P = pd.DataFrame({"BTC": close, "ETH": close, "SOL": np.nan})
    W = TL.targets(v, P)["BTC"] * 2 if v.get("alloc") is None else TL.targets(v, P)["BTC"]
    W = W.clip(0, 1)
    if v.get("weekly"):
        W = W.where(W.index.dayofweek == 6).ffill().fillna(0.0)
    r = close.pct_change().fillna(0.0)
    held = W.shift(1).fillna(0.0)
    rf = rf_daily(close.index).reindex(close.index).fillna(0.0)
    net = held * r + (1 - held) * rf - W.diff().abs().fillna(0.0) * cost
    return (net - rf).loc["2017-07-01":]


MARKETS = ["SOL", "LTC", "XRP", "LINK", "DOGE", "ADA", "AVAX", "SPY", "QQQ"]


def cross_market(sig):
    wins, rows = 0, []
    for m in MARKETS:
        try:
            c, cost = daily_close(m)
        except Exception as e:  # noqa: BLE001
            rows.append((m, np.nan, np.nan))
            continue
        c = c[~c.index.duplicated()].sort_index()
        base = single_asset(c, cost, {})
        alt = single_asset(c, cost, sig)
        sb, sa = sharpe(base), sharpe(alt)
        rows.append((m, sb, sa))
        wins += int(sa > sb)
    return wins, rows


def main():
    tags = sys.argv[1:] or ["round1"]
    R, D = load(tags)
    X = excess(D)
    inc = {"I2": "I2-S00", "I5": "I5-S00"}
    pd.set_option("display.width", 250)
    print("Implementation family (live rule signal):")
    imp = R[R.fam == "I"][["label", "full_sharpe", "full_cagr", "full_maxdd", "trades"] +
                          [f"{k}_sharpe" for k in TL.SUBS]]
    imp["t_vs_I0"] = [paired_t_weekly(X[k], X["I0-S00"]) for k in imp.index]
    imp["t_vs_I5"] = [paired_t_weekly(X[k], X["I5-S00"]) for k in imp.index]
    print(imp.round(2).to_string())
    print("\nSignal family vs the incumbent under each implementation:")
    rows = []
    for k, r in R[R.fam != "I"].iterrows():
        ik = k.split("-")[0]
        b = R.loc[inc[ik]]
        row = dict(key=k, label=r.label, sharpe=r.full_sharpe, d_sharpe=r.full_sharpe - b.full_sharpe,
                   t_weekly=paired_t_weekly(X[k], X[inc[ik]]), cagr=r.full_cagr, maxdd=r.full_maxdd, trades=r.trades)
        row["worst_sub_d"] = min(r[f"{s}_sharpe"] - b[f"{s}_sharpe"] for s in TL.SUBS)
        rows.append(row)
    S = pd.DataFrame(rows).set_index("key")
    S["bar1"] = S.d_sharpe >= 0.10
    S["bar2"] = S.t_weekly > 3.0
    S["bar3"] = S.worst_sub_d > -0.10
    print(S.sort_values("d_sharpe", ascending=False).round(2).to_string())
    # bars must hold under BOTH implementations
    sig = S.index.str.split("-").str[1]
    both = S.assign(sig=sig).groupby("sig")[["bar1", "bar2", "bar3"]].all()
    both["all3"] = both.all(axis=1)
    print("\nBars 1-3 under both I2 and I5:")
    print(both[both.bar1 | both.all3].to_string())
    # cross-market check for every signal change that passes bar 1 under both
    cands = both.index[both.bar1].tolist()
    print("\nCross-market check (Sharpe above T-bills, single asset long/cash, Jul 2017+):")
    xm = {}
    for s in cands:
        spec = {k: v for k, v in TL.SIGS[s].items() if k != "name"}
        if spec.get("alloc") or spec.get("sig") in ("own", "and", "tilt"):
            print(f"  {s} {TL.SIGS[s]['name']}: allocation change, no single-asset analogue")
            continue
        w, rows_ = cross_market(spec)
        xm[s] = w
        print(f"  {s} {TL.SIGS[s]['name']}: improves {w}/{len(MARKETS)}  " +
              ", ".join(f"{m} {a:.2f}->{b:.2f}" for m, a, b in rows_ if not np.isnan(a)))
    both["cross_market_wins"] = pd.Series(xm)
    both.to_csv(os.path.join(OUT, f"bars_{'_'.join(tags)}.csv"))
    S.to_csv(os.path.join(OUT, f"signal_vs_incumbent_{'_'.join(tags)}.csv"))
    Y = years(D, ["I0-S00", "I1-S00", "I2-S00", "I4-S00", "I5-S00", "I7-S00"] + [f"I5-{s}" for s in cands if f"I5-{s}" in D])
    print("\nCalendar-year returns:")
    print((Y * 100).round(1).to_string())


if __name__ == "__main__":
    main()
