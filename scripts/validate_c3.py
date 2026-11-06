#!/usr/bin/env python3
"""Validate C3 (risk parity: live rule + hourly EWMAC long/short on BTC/ETH, Coinbase perps)."""
import os, sys, itertools
import numpy as np, pandas as pd
from scipy.stats import norm, skew, kurtosis
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from edge import book, intraday as ih
import intraday_search as s1
import intraday_search2 as s2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dev = slice("2019-11-06", "2023-12-31")

def build(cost=ih.PERP_COST, fmult=1.0, fshift=0.0, pre=ih.PRE_FUNDING):
    fund = ih.hourly_funding(s1.H, s1.A2, pre=pre, mult=fmult, shift=fshift)
    live = ih.run(s1.to_hourly(s1.live_daily()), s1.close_h, cost=cost, funding=fund)
    P = s1.hourly_ewmac(False)
    hls = ih.run(P, s1.close_h, cost=cost, funding=fund)
    return live, hls, P

live, hls, P = build()
wl, wh = 1 / live.loc[dev].std(), 1 / hls.loc[dev].std()
W_L, W_H = wl / (wl + wh), wh / (wl + wh)
c3 = W_L * live + W_H * hls
print(f"Weights (from development-period vol): live {W_L:.2f}, hourly L/S {W_H:.2f}")
turn = P.diff().abs().sum(axis=1).groupby(P.index.year).sum()
print("Hourly L/S book turnover (x capital per year):", {int(k): round(v, 1) for k, v in turn.loc[2017:].items()})

def yrs(x):
    xx = x.loc["2017-07-01":]
    return (1 + xx + book.rf_daily(xx.index)).groupby(xx.index.year).prod() - 1
for nm, x in [("live", live), ("hourly L/S", hls), ("C3", c3), ("C3 x1.5", 1.5 * c3)]:
    print(f"  {nm:12s}", {int(k): f"{v:+.0%}" for k, v in yrs(x).items()})

def memmel(a, b, start, end=None):
    d = pd.concat([a, b], axis=1).loc[start:end].dropna(); T = len(d)
    s_a, s_b = (d.mean() / d.std()).values; rho = d.corr().iloc[0, 1]
    z = (s_a - s_b) / np.sqrt((2 - 2 * rho + 0.5 * (s_a**2 + s_b**2 - 2 * s_a * s_b * rho**2)) / T)
    return z, 2 * (1 - norm.cdf(abs(z)))
for lab, (s_, e_) in [("7y", ("2019-11-06", None)), ("full Jul 2017+", ("2017-07-01", None)), ("2024+", ("2024-01-01", None))]:
    z, p = memmel(c3, live, s_, e_)
    print(f"Sharpe C3 {book.sharpe(c3, s_, e_):.2f} vs live {book.sharpe(live, s_, e_):.2f} ({lab}): z {z:+.2f}, p {p:.2f}")

print("\nStress tests (7y Sharpe, CAGR at 1.5x, worst down-year at 1.5x):")
for lab, kw in [("base", {}), ("perp cost 0.08%/side", dict(cost=0.0008)), ("perp cost 0.12%/side", dict(cost=0.0012)),
                ("funding x1.5", dict(fmult=1.5)), ("pre-2023 funding 15%/yr", dict(pre=0.15)),
                ("cost 0.08% + funding x1.5", dict(cost=0.0008, fmult=1.5))]:
    l, h, _ = build(**kw)
    c = W_L * l + W_H * h
    y = yrs(1.5 * c)
    st = book.summary(1.5 * c, "2019-11-06")
    print(f"  {lab:28s} Sharpe {book.sharpe(c, '2019-11-06'):.2f} | 2024+ {book.sharpe(c, '2024-01-01'):.2f} | x1.5 CAGR {st['cagr']:.0%} DD {st['maxdd']:.0%} | "
          f"2018 {y.get(2018, np.nan):+.0%} 2022 {y.get(2022, np.nan):+.0%} 2025 {y.get(2025, np.nan):+.0%} 2026 {y.get(2026, np.nan):+.0%}")

# robustness: leave one EWMAC speed out
print("\nLeave-one-speed-out (C3 7y Sharpe):")
import intraday_search2 as s2b
F2, v2 = s2b.ewmac_forecast(s1.close_h, s1.r_h)
speeds = [(4, 16), (8, 32), (16, 64), (32, 128), (64, 256), (128, 512)]
vh = s1.r_h.ewm(span=768, min_periods=240).std()
raws = []
for f, s in speeds:
    raw = (s1.close_h.ewm(span=f, min_periods=f).mean() - s1.close_h.ewm(span=s, min_periods=s).mean()) / (s1.close_h * vh)
    scal = 10.0 / raw.abs().mean(axis=1).expanding(min_periods=24 * 365).mean()
    raws.append(raw.mul(scal, axis=0).clip(-20, 20))
vann = (vh * np.sqrt(8760)).clip(lower=0.10)
out = []
for i, sp in enumerate(speeds):
    F = (sum(r for j, r in enumerate(raws) if j != i) / 5 * 1.19).clip(-20, 20)
    Pp = s2b.positions(F, vann, 0.5, 1.05)
    h = ih.run(Pp, s1.close_h)
    c = W_L * live + W_H * h
    out.append(f"drop {sp}: {book.sharpe(c, '2019-11-06'):.2f}")
print("  " + " | ".join(out))

# deflated Sharpe with all trials so far
n_trials = 154 + 30 + 28 + 12 + 14 + 10
srs = pd.read_csv(os.path.join(ROOT, "reports", "book_results.csv")).full_sharpe.dropna().values / np.sqrt(365)
emc = 0.5772
sr0 = np.std(srs, ddof=1) * ((1 - emc) * norm.ppf(1 - 1 / n_trials) + emc * norm.ppf(1 - 1 / (n_trials * np.e)))
r = c3.loc["2017-07-01":].dropna(); sr = r.mean() / r.std()
z = (sr - sr0) * np.sqrt(len(r) - 1) / np.sqrt(1 - skew(r) * sr + (kurtosis(r, fisher=False) - 1) / 4 * sr**2)
print(f"\nDeflated Sharpe (C3, Jul 2017+, {n_trials} trials): Sharpe {sr*np.sqrt(365):.2f}, DSR {norm.cdf(z):.2f}")
pd.DataFrame({"live": live, "hourly_ls": hls, "C3": c3}).to_parquet(os.path.join(ROOT, "reports", "c3_returns.parquet"))
