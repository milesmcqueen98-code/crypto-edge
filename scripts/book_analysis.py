#!/usr/bin/env python3
"""Checks on the practitioner round:
1. Implementation check: Zarattini BTC-only from 2015 vs the paper's reported Sharpe 1.56.
2. Carry: decomposition (funding vs basis), time deployed, worst days, stress (lower funding,
   higher costs) - funding on US-regulated venues may be lower than on Hyperliquid.
3. Carver-style diversification: trend ensemble (Carver + Zarattini + Clenow, equal weight).
4. Trend + carry combinations (2023-05+): fixed capital splits, and idle trend cash in carry.
5. Probability of backtest overfitting (CSCV, 16 blocks) across the directional strategies.
6. Deflated Sharpe ratios given every strategy tried in this project.
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from edge import book, ls  # noqa: E402
import book_strategies as bs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = pd.read_parquet(os.path.join(ROOT, "reports", "book_results.csv").replace(".csv", ".csv")) if False else None
R = pd.read_parquet(os.path.join(ROOT, "reports", "book_returns.parquet"))
RES = pd.read_csv(os.path.join(ROOT, "reports", "book_results.csv"))


def line(name, x, periods=(("2023-05-16", None), ("2024-01-01", None))):
    parts = []
    for s, e in periods:
        st = book.summary(x, s, e)
        parts.append(f"{s[:7]}+ Sharpe {st['sharpe']:5.2f} CAGR {st['cagr']:6.1%} DD {st['maxdd']:5.0%}")
    print(f"  {name:48s} " + " | ".join(parts))


def main():
    # 1 ---------------------------------------------------------------
    print("== 1. Implementation check: Zarattini Donchian ensemble, BTC only, Jan 2015+, 0.10% costs ==")
    W = bs.W0(["BTC"])
    W["BTC"] = bs.donchian_ensemble(bs.px.BTC).fillna(0.0)
    raw = ls.returns(W, cost=0.001).loc["2015-01-01":]
    x = book.excess_returns(W, cost=0.001).loc["2015-01-01":]
    eq = (1 + raw).cumprod()
    print(f"  ours: Sharpe (raw) {raw.mean() / raw.std() * np.sqrt(365):.2f}, Sharpe (excess) {book.sharpe(x):.2f}, "
          f"CAGR {eq.iloc[-1] ** (365.25 / (eq.index[-1] - eq.index[0]).days) - 1:.0%}, "
          f"MaxDD {(eq / eq.cummax() - 1).min():.0%}   | paper: Sharpe 1.56, CAGR 30%, MaxDD 19% (to Mar 2025)")
    raw2 = raw.loc[:"2025-03-15"]
    print(f"  ours to Mar 2025: Sharpe (raw) {raw2.mean() / raw2.std() * np.sqrt(365):.2f}")

    # 2 ---------------------------------------------------------------
    print("\n== 2. Cash & carry diagnostics ==")
    perps = book.load_perps()
    fund = bs.fund
    for a in bs.A2:
        fa = fund[a].dropna()
        basis = (bs.r2[a] - perps[a].pct_change(fill_method=None)).reindex(fa.index)
        print(f"  {a}: funding {fa.mean() * 365:+.1%}/yr since {fa.index.min().date()}; "
              f"daily basis noise sd {basis.std():.3%}; corr(spot, perp) {bs.r2[a].reindex(fa.index).corr(perps[a].pct_change(fill_method=None).reindex(fa.index)):.4f}")
    cx = R["Cash & carry BTC+ETH (2023+)"].dropna()
    print(f"  carry stream: {len(cx)} days, worst day {cx.min():+.2%}, best {cx.max():+.2%}, "
          f"share of days with positive excess {(cx > 0).mean():.0%}")
    by_year = (1 + cx + book.rf_daily(cx.index)).groupby(cx.index.year).prod() - 1
    print("  total return by year:", {int(k): f"{v:+.1%}" for k, v in by_year.items()})
    orig = bs.fund.copy()
    for label, mult, shift, cost in [("funding x0.5", 0.5, 0.0, ls.COST), ("funding -5%/yr", 1.0, -0.05 / 365, ls.COST),
                                     ("costs 0.5%/leg", 1.0, 0.0, 0.005), ("funding x0.5 + costs 0.5%", 0.5, 0.0, 0.005)]:
        bs.fund = orig * mult + shift
        old = ls.COST
        ls.COST = cost
        sx, _ = bs.carry_returns()
        ls.COST = old
        st, st2 = book.summary(sx, "2023-05-16"), book.summary(sx, "2024-01-01")
        print(f"  stress {label:26s}: Sharpe {st['sharpe']:5.2f} (2024+ {st2['sharpe']:5.2f}), CAGR {st['cagr']:5.1%}, DD {st['maxdd']:4.0%}")
    bs.fund = orig

    # 3 ---------------------------------------------------------------
    print("\n== 3. Carver-style trend ensemble (equal weight of three book trend systems) ==")
    Wc, Wz, Wk = bs.carver_ewmac(True, 1.0), bs.zpb_btc_eth(1.0), bs.clenow(False, 1.0)
    ens = (Wc + Wz + Wk) / 3
    xe = book.excess_returns(ens)
    xe = xe.where(ens.abs().sum(axis=1).cumsum().shift(1).fillna(0) > 0)
    for nm, xx in [("Live rule", R["Live rule: BTC>SMA100, 50/50 BTC/ETH"]), ("Trend ensemble (Carver+Zarattini+Clenow)", xe)]:
        row = [f"{p} {book.sharpe(xx, *bs.PER[p]):.2f}" for p in ("dev", "recent", "early", "full")]
        st = book.summary(xx, *bs.PER["full"])
        print(f"  {nm:44s} Sharpe " + ", ".join(row) + f" | full CAGR {st['cagr']:.0%} DD {st['maxdd']:.0%}")
    # Sharpe is leverage-invariant: what the ensemble looks like scaled to the live rule's volatility
    k = R["Live rule: BTC>SMA100, 50/50 BTC/ETH"].loc["2017-07-01":].std() / xe.loc["2017-07-01":].std()
    lev = book.excess_returns(book.cap_gross(ens * k, 3.0))
    st = book.summary(lev, *bs.PER["full"])
    print(f"  ensemble scaled x{k:.1f} to the live rule's volatility (needs futures/margin): Sharpe {st['sharpe']:.2f}, "
          f"CAGR {st['cagr']:.0%}, DD {st['maxdd']:.0%}")
    R["Trend ensemble (Carver+Zarattini+Clenow)"] = xe

    # 4 ---------------------------------------------------------------
    print("\n== 4. Trend + carry (2023-05+) ==")
    live = R["Live rule: BTC>SMA100, 50/50 BTC/ETH"]
    for nm, tr in [("live rule", live), ("trend ensemble", xe)]:
        for wt in (1.0, 0.75, 0.5, 0.25, 0.0):
            comb = wt * tr + (1 - wt) * cx
            line(f"{int(wt * 100)}% {nm} / {int((1 - wt) * 100)}% carry", comb.dropna())
    # idle cash from the live rule goes into the carry trade instead of T-bills
    Wl = bs.live_rule()
    expo = Wl.abs().sum(axis=1).shift(1).fillna(0.0)
    idle_carry = live + (1 - expo).reindex(cx.index) * cx
    line("live rule, idle cash in carry", idle_carry.dropna())
    R["Live rule, idle cash in carry"] = idle_carry
    R["50% live rule / 50% carry"] = 0.5 * live + 0.5 * cx

    # 5 ---------------------------------------------------------------
    print("\n== 5. Probability of backtest overfitting (CSCV, 16 blocks, directional strategies, Jul 2017+) ==")
    excl = ("Cash & carry", "Meta-labeled", "50/50 BTC/ETH buy", "BTC buy & hold", "idle cash", "50% live")
    cols = [c for c in R.columns if not c.startswith(excl) and "Meta-labeled" not in c]
    M = R[cols].loc["2017-07-01":].dropna(axis=1, thresh=int(0.95 * len(R.loc["2017-07-01":]))).fillna(0.0)
    T, N = M.shape
    blocks = np.array_split(np.arange(T), 16)
    sums = np.array([M.values[b].sum(axis=0) for b in blocks])
    sq = np.array([(M.values[b] ** 2).sum(axis=0) for b in blocks])
    cnt = np.array([len(b) for b in blocks])
    logits = []
    for comb in itertools.combinations(range(16), 8):
        is_ = np.zeros(16, bool)
        is_[list(comb)] = True

        def sr(mask):
            n = cnt[mask].sum()
            mu = sums[mask].sum(axis=0) / n
            var = sq[mask].sum(axis=0) / n - mu ** 2
            return mu / np.sqrt(var)
        s_is, s_oos = sr(is_), sr(~is_)
        best = np.argmax(s_is)
        rank = (np.argsort(np.argsort(s_oos))[best] + 1) / (N + 1)
        logits.append(np.log(rank / (1 - rank)))
    logits = np.array(logits)
    print(f"  {N} strategies, {len(logits)} train/test splits: PBO = {(logits <= 0).mean():.0%} "
          f"(share of splits where the in-sample best lands in the bottom half out of sample)")
    full_sr = M.mean() / M.std() * np.sqrt(365)
    print("  best in-sample most often:", pd.Series([M.columns[np.argmax(
        (lambda m: sums[m].sum(0) / cnt[m].sum() / np.sqrt(sq[m].sum(0) / cnt[m].sum() - (sums[m].sum(0) / cnt[m].sum()) ** 2))(
            np.isin(np.arange(16), c)))] for c in itertools.islice(itertools.combinations(range(16), 8), 0, 12870, 13)]).value_counts().head(4).to_dict())

    # 6 ---------------------------------------------------------------
    print("\n== 6. Deflated Sharpe (all strategies tried in this project) ==")
    n_trials = 154 + 30 + len(RES) + 12   # ls_search + earlier rounds + this round + checks above
    srs_daily = (RES.full_sharpe.dropna().values / np.sqrt(365))
    emc = 0.5772
    sr0 = np.std(srs_daily, ddof=1) * ((1 - emc) * norm.ppf(1 - 1 / n_trials) + emc * norm.ppf(1 - 1 / (n_trials * np.e)))
    for nm in ["Cash & carry BTC+ETH (2023+)", "Live rule: BTC>SMA100, 50/50 BTC/ETH", "EWMAC 6-speed, long-only, spot (1x cap)",
               "Trend ensemble (Carver+Zarattini+Clenow)", "Live rule, idle cash in carry", "50% live rule / 50% carry"]:
        r = R[nm].dropna()
        sr = r.mean() / r.std()
        g3, g4 = skew(r), kurtosis(r, fisher=False)
        z = (sr - sr0) * np.sqrt(len(r) - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
        print(f"  {nm:44s} annual Sharpe {sr * np.sqrt(365):5.2f} over {len(r) / 365:.1f}y -> DSR {norm.cdf(z):.2f} "
              f"(benchmark Sharpe from {n_trials} trials: {sr0 * np.sqrt(365):.2f})")
    R.to_parquet(os.path.join(ROOT, "reports", "book_returns.parquet"))


if __name__ == "__main__":
    main()
