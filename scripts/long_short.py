#!/usr/bin/env python3
"""Long/short vs long/cash on the 100-day trend rule. Position set at close t earns t+1.
Short carry: Hyperliquid BTC funding where available (positive = shorts receive); before
May 2023 an assumed flat rate (scenario). Costs 0.25% per unit traded (a long->short flip trades 2 units)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import data

close, _, ret = data.load()
fund = data.load_funding()["BTC"].reindex(close.index)
on = close.BTC > close.BTC.rolling(100).mean()
r = ret[["BTC", "ETH"]].fillna(0)
COST = 0.0025


def run(long_w, short_w, start, pre_carry=0.0, cost=COST):
    """long_w / short_w: dicts asset->weight used when on / off."""
    idx = close.loc[start:].index
    carry = fund.loc[idx].fillna(pre_carry / 365)
    pos = pd.DataFrame(0.0, index=idx, columns=["BTC", "ETH"])
    for a, w in long_w.items():
        pos.loc[on.loc[idx], a] = w
    for a, w in short_w.items():
        pos.loc[~on.loc[idx], a] = w
    held = pos.shift(1).fillna(0)                      # decided at close t-1, earns day t
    gross = (held * r.loc[idx]).sum(axis=1)
    short_carry = (-held.clip(upper=0)).sum(axis=1) * carry.shift(1).fillna(0)
    tc = pos.diff().abs().sum(axis=1).fillna(pos.iloc[0].abs().sum()) * cost
    daily = gross + short_carry - tc
    eq = (1 + daily).cumprod()
    return eq, daily, held


def stats(eq, daily):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1, sharpe=daily.mean() / daily.std() * np.sqrt(365),
                maxdd=(eq / eq.cummax() - 1).min(), vol=daily.std() * np.sqrt(365))


S = {
    "BTC long / cash": ({"BTC": 1.0}, {}),
    "BTC long / short": ({"BTC": 1.0}, {"BTC": -1.0}),
    "BTC long / half short": ({"BTC": 1.0}, {"BTC": -0.5}),
    "BTC+ETH long / cash (live)": ({"BTC": 0.5, "ETH": 0.5}, {}),
    "BTC+ETH long / BTC short": ({"BTC": 0.5, "ETH": 0.5}, {"BTC": -1.0}),
}
for wname, start in [("7 years (Nov 2019+)", "2019-11-06"), ("Jul 2021+", "2021-07-01"), ("2024+ (real funding data)", "2024-01-01")]:
    print(f"\n== {wname} ==")
    base = None
    for name, (lw, sw) in S.items():
        eq, d, held = run(lw, sw, start)
        s = stats(eq, d)
        wk = (1 + d).resample("W").prod() - 1
        if name == "BTC long / cash":
            base = wk; t = ""
        else:
            x = wk - base; t = f"t vs BTC long/cash {x.mean() / x.std() * np.sqrt(len(x)):+.2f}"
        extra = ""
        if sw:
            sd = d[(held < 0).any(axis=1)]
            extra = f" | short days {len(sd)}, short-leg total {np.expm1(np.log1p(sd).sum()):+.0%}"
        print(f"  {name:28s} CAGR {s['cagr']:6.1%}  Sharpe {s['sharpe']:.2f}  MaxDD {s['maxdd']:5.0%}  vol {s['vol']:.0%}  {t}{extra}")

print("\nCarry sensitivity, BTC long / short, 7 years (pre-May-2023 funding assumption):")
for c in [-0.05, 0.0, 0.06]:
    eq, d, _ = run({"BTC": 1.0}, {"BTC": -1.0}, "2019-11-06", pre_carry=c); s = stats(eq, d)
    print(f"  shorts {'pay' if c < 0 else 'receive'} {abs(c):.0%}/yr: CAGR {s['cagr']:.1%} Sharpe {s['sharpe']:.2f} MaxDD {s['maxdd']:.0%}")
print("\nSMA length, BTC long / short vs long / cash (7 years, Sharpe):")
for n in [50, 100, 150, 200]:
    on = close.BTC > close.BTC.rolling(n).mean()
    a = stats(*run({"BTC": 1.0}, {}, "2019-11-06")[:2]); b = stats(*run({"BTC": 1.0}, {"BTC": -1.0}, "2019-11-06")[:2])
    print(f"  {n:3d}-day: long/cash {a['sharpe']:.2f} ({a['cagr']:.0%}) | long/short {b['sharpe']:.2f} ({b['cagr']:.0%}, DD {b['maxdd']:.0%})")
on = close.BTC > close.BTC.rolling(100).mean()
eq, d, held = run({"BTC": 1.0}, {"BTC": -1.0}, "2019-11-06")
yr = (1 + d).groupby(d.index.year).prod() - 1
eq2, d2, _ = run({"BTC": 1.0}, {}, "2019-11-06"); yr2 = (1 + d2).groupby(d2.index.year).prod() - 1
print("\nBy year (long/short vs long/cash):", {int(k): f"{v:+.0%} vs {yr2[k]:+.0%}" for k, v in yr.items()})
