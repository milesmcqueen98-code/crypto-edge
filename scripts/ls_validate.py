#!/usr/bin/env python3
"""Stress-test the round C candidate: live rule + 0.5x market-neutral low-vol book
(long the 3 lowest-volatility of the 30 most liquid coins, short the 3 highest, 0.25 gross each side).

Checks: significance of the improvement, all 7 rebalance weekdays, cost/fee stress,
what the legs hold, and an implementable version whose shorts are limited to coins with
US-listed perpetuals (Kraken Derivatives US list at launch, June 2026)."""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import features, ls  # noqa: E402

US_PERPS = {"BTC", "ETH", "SOL", "XRP", "ADA", "LINK", "DOGE", "LTC", "AVAX"}
N_TRIALS = 129 + 0   # candidates logged in reports/ls_search.csv (rounds A-C), updated below


def neutral_book(close, dvol, k=3, weekday=6, gross=0.5, short_pool=None, long_pool_n=30, short_pool_n=30):
    univ, v30 = features.universe(close, dvol)
    vol90 = close.pct_change(fill_method=None).rolling(90, min_periods=60).std()
    idx = close.index
    rows, cur, longs, shorts = {}, None, {}, {}
    for d in idx:
        if d.weekday() == weekday:
            liquid = v30.loc[d].where(univ.loc[d]).dropna()
            lp = liquid.nlargest(long_pool_n).index
            sp = liquid.nlargest(short_pool_n).index
            if short_pool is not None:
                sp = [a for a in sp if a in short_pool]
            lv, sv = vol90.loc[d, lp].dropna(), vol90.loc[d, sp].dropna()
            if len(lv) >= 2 * k + 4 and len(sv) >= k + 1:
                lo = lv.nsmallest(k).index
                hi = [a for a in sv.nlargest(k + 3).index if a not in lo][:k]
                cur = pd.Series(0.0, index=close.columns)
                cur[lo] += gross / 2 / k
                cur[hi] -= gross / 2 / k
                longs[d], shorts[d] = list(lo), list(hi)
            else:
                cur = None
        if cur is not None:
            rows[d] = cur
    W = pd.DataFrame(rows).T.reindex(idx).fillna(0.0)
    W = W.loc[:, (W != 0).any()]
    return W, longs, shorts


def combine(live, W):
    cols = sorted(set(live.columns) | set(W.columns))
    return live.reindex(columns=cols, fill_value=0.0).add(W.reindex(columns=cols, fill_value=0.0), fill_value=0.0)


def tstat(a, b, start, end=None):
    x = ((1 + a.loc[start:end]).resample("W").prod() - (1 + b.loc[start:end]).resample("W").prod())
    return x.mean() / x.std() * np.sqrt(len(x))


def dsr(r, sr_trials, n):
    """Deflated Sharpe ratio (Bailey & Lopez de Prado): P(true SR > best-of-n luck)."""
    r = r.dropna()
    sr = r.mean() / r.std()
    emc = 0.5772
    sr0 = np.std(sr_trials, ddof=1) / np.sqrt(365) * ((1 - emc) * norm.ppf(1 - 1 / n) + emc * norm.ppf(1 - 1 / (n * np.e)))
    g3, g4 = skew(r), kurtosis(r, fisher=False)
    return norm.cdf((sr - sr0) * np.sqrt(len(r) - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))


def main():
    close, dvol, ret, fund = ls.load()
    idx = close.index
    btc = close["BTC"]
    up = (btc > btc.rolling(100).mean()).astype(float)
    live = pd.DataFrame({"BTC": 0.5 * up, "ETH": 0.5 * up}, index=idx)
    r_live = ls.returns(live)
    P = {"dev": ("2019-11-06", "2023-12-31"), "recent": ("2024-01-01", None), "7y": ("2019-11-06", None)}

    def show(name, r):
        parts = []
        for p, (s, e) in P.items():
            st = ls.stats(r, s, e)
            parts.append(f"{p} Sharpe {st['sharpe']:.2f} CAGR {st['cagr']:6.1%} DD {st['maxdd']:4.0%}")
        print(f"  {name:52s} " + " | ".join(parts))

    print("== Baseline vs candidate ==")
    show("live long-only", r_live)
    W, longs, shorts = neutral_book(close, dvol)
    r_c = ls.returns(combine(live, W))
    show("candidate: live + 0.5x neutral low-vol 3", r_c)
    r_n = ls.returns(W)
    show("neutral book alone", r_n)
    print(f"  improvement t-stat (weekly): dev {tstat(r_c, r_live, *P['dev']):+.2f}, recent {tstat(r_c, r_live, *P['recent']):+.2f}, 7y {tstat(r_c, r_live, *P['7y']):+.2f}")
    print(f"  neutral book t-stat vs zero (7y): {r_n.loc['2019-11-06':].mean() / r_n.loc['2019-11-06':].std() * np.sqrt(len(r_n.loc['2019-11-06':])):+.2f}; "
          f"corr with live rule {r_n.loc['2019-11-06':].corr(r_live.loc['2019-11-06':]):+.2f}")

    print("\n== All 7 rebalance weekdays (candidate Sharpe) ==")
    out = []
    for wd in range(7):
        Wd, _, _ = neutral_book(close, dvol, weekday=wd)
        rr = ls.returns(combine(live, Wd))
        out.append((wd, ls.stats(rr, *P["dev"])["sharpe"], ls.stats(rr, *P["recent"])["sharpe"]))
    print("  " + ", ".join(f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][w]} {a:.2f}/{b:.2f}" for w, a, b in out) + "   (dev/recent; live 1.53/0.66)")

    print("\n== Cost and short-fee stress ==")
    for c, fee in [(0.0025, 0.05), (0.005, 0.05), (0.005, 0.15), (0.0075, 0.25)]:
        rr = ls.returns(combine(live, W), cost=c, alt_fee=fee)
        print(f"  trade cost {c:.2%}, alt short fee {fee:.0%}/yr: dev {ls.stats(rr, *P['dev'])['sharpe']:.2f}  recent {ls.stats(rr, *P['recent'])['sharpe']:.2f}  7y {ls.stats(rr, *P['7y'])['sharpe']:.2f}")

    print("\n== What the book holds (share of weeks each coin appears, since 2024) ==")
    lw = pd.Series([a for d, l in longs.items() if d >= pd.Timestamp("2024-01-01") for a in l]).value_counts(normalize=True).head(8)
    sw = pd.Series([a for d, l in shorts.items() if d >= pd.Timestamp("2024-01-01") for a in l]).value_counts(normalize=True).head(12)
    print("  longs: ", ", ".join(f"{a} {v:.0%}" for a, v in lw.items()))
    print("  shorts:", ", ".join(f"{a} {v:.0%}" for a, v in sw.items()))
    shortable = np.mean([a in US_PERPS for d, l in shorts.items() if d >= pd.Timestamp("2024-01-01") for a in l])
    print(f"  share of short positions in coins with US-listed perps: {shortable:.0%}")
    lr = ls.returns(W.clip(lower=0)); sr_ = ls.returns(W.clip(upper=0))
    print(f"  7y leg P&L: long leg {np.expm1(np.log1p(lr.loc['2019-11-06':]).sum()):+.0%}, short leg {np.expm1(np.log1p(sr_.loc['2019-11-06':]).sum()):+.0%}")

    print("\n== Implementable: shorts only in coins with US-listed perps ==")
    for k in (2, 3):
        Wi, _, si = neutral_book(close, dvol, k=k, short_pool=US_PERPS - {"BTC", "ETH"})
        ri = ls.returns(combine(live, Wi))
        show(f"live + 0.5x neutral low-vol {k}, US-perp shorts", ri)
        print(f"     improvement t: dev {tstat(ri, r_live, *P['dev']):+.2f}, recent {tstat(ri, r_live, *P['recent']):+.2f}")
    print("  (caveat: these perps only became available to US accounts in 2025-26; earlier periods assume offshore-equivalent access)")

    df = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports", "ls_search.csv"))
    n = len(df)
    p = dsr(r_c.loc[slice(*P["dev"])], df.dev_sharpe.dropna().values, n)
    print(f"\n== Multiple testing ==\n  {n} candidates tried; deflated-Sharpe probability the candidate's dev Sharpe is skill, not best-of-{n} luck: {p:.2f}")


if __name__ == "__main__":
    main()
