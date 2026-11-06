#!/usr/bin/env python3
"""Renaissance/Citadel-style search on the 9 coins with US-listed perps (Kraken Derivatives US list):
many weak cross-sectional signals -> screened on development data only -> combined into one
dollar- and beta-neutral book -> tested on 2024-26 after perps costs.

Protocol (fixed before looking at results):
  * Development: 2021-07-01 .. 2023-12-31 (>= 7 coins). Hold-out: 2024-01-01 .. now.
  * Stale-price guard: a coin-hour counts only if it traded that hour (volume > 0).
  * Screen: rank IC of each signal vs forward h-hour returns, non-overlapping samples,
    keep |t| >= 3 (Harvey-Liu-Zhu multiple-testing hurdle). Greedy de-duplication: skip a
    signal whose average cross-sectional correlation with an already-kept one exceeds 0.7.
  * Composite: equal-weight sum of direction-adjusted cross-sectional rank z-scores.
  * Book: weights = composite, demeaned and beta-neutralised vs BTC, gross 1.0, rebalanced
    every h hours. Costs 0.04%/side + funding (Hyperliquid 2023+, symmetric 8%/yr before).
  * Checks: one-hour execution delay, 0.08%/side costs.
Writes reports/xs_ic.csv, reports/xs_books.csv, reports/xs_returns.parquet
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import book, intraday as ih  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COINS9 = ["BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "ADA", "AVAX", "LINK"]
DEV = ("2021-07-01", "2023-12-31")
HOLD = ("2024-01-01", None)
HORIZONS = [1, 4, 12, 24]
MIN_COINS = 6

t0 = time.time()
close, volu = ih.load_hourly(COINS9)
close, volu = close.loc["2019-01-01":], volu.loc["2019-01-01":]
H = close.index
valid = (volu > 0) & close.notna()
r1 = close.pct_change(fill_method=None)
btc = r1["BTC"]


def roll_beta(n=720):
    cov = r1.rolling(n, min_periods=240).cov(btc)
    return cov.div(btc.rolling(n, min_periods=240).var(), axis=0)


BETA = roll_beta()


def build_signals():
    s = {}
    for L in (1, 2, 3, 4, 6, 8, 12, 24, 48, 72, 168, 336, 720):
        s[f"mom_{L}h"] = close / close.shift(L) - 1
    for L in (6, 12, 24, 72, 168, 720):
        s[f"momskip_{L}h"] = close.shift(1) / close.shift(L) - 1
    for L in (1, 4, 24, 168):
        rb = close["BTC"] / close["BTC"].shift(L) - 1
        ri = close / close.shift(L) - 1
        s[f"resid_{L}h"] = ri - BETA.mul(rb, axis=0)
    for L in (1, 2, 4):
        rb = close["BTC"] / close["BTC"].shift(L) - 1
        ri = close / close.shift(L) - 1
        s[f"leadlag_{L}h"] = BETA.mul(rb, axis=0) - ri
    for L in (24, 168, 720):
        s[f"vol_{L}h"] = r1.rolling(L, min_periods=L // 2).std()
        s[f"maxret_{L}h"] = r1.rolling(L, min_periods=L // 2).max()
        s[f"skew_{L}h"] = r1.rolling(L, min_periods=L // 2).skew()
        lo, hi = close.rolling(L).min(), close.rolling(L).max()
        s[f"donch_{L}h"] = (close - lo) / (hi - lo)
    base = volu.rolling(720, min_periods=240).mean()
    for L in (1, 4, 24):
        av = np.log((volu.rolling(L).sum() + 1e-9) / (base * L + 1e-9))
        s[f"abvol_{L}h"] = av
        s[f"retxvol_{L}h"] = (close / close.shift(L) - 1) * av
    for D in (7, 14, 28):                      # same hour-of-day on previous days -> predicts next hour
        acc = sum(r1.shift(24 * k - 1) for k in range(1, D + 1)) / D
        s[f"season_{D}d"] = acc
    return s


def cs_z(df, mask):
    """Cross-sectional rank z-score among valid coins."""
    rk = df.where(mask).rank(axis=1)
    mu, sd = rk.mean(axis=1), rk.std(axis=1)
    return rk.sub(mu, axis=0).div(sd.replace(0, np.nan), axis=0)


def ic_series(sig, fwd, mask):
    a = sig.where(mask).rank(axis=1)
    b = fwd.where(mask).rank(axis=1)
    both = a.notna() & b.notna()
    a, b = a.where(both), b.where(both)
    a = a.sub(a.mean(axis=1), axis=0)
    b = b.sub(b.mean(axis=1), axis=0)
    ic = (a * b).sum(axis=1) / np.sqrt((a ** 2).sum(axis=1) * (b ** 2).sum(axis=1))
    return ic.where(both.sum(axis=1) >= MIN_COINS)


def tstat(x):
    x = x.dropna()
    return x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 30 else np.nan


def neutral_weights(score, mask):
    """Dollar- and beta-neutral, gross 1."""
    z = score.where(mask)
    out = np.full(z.shape, np.nan)
    Z, B = z.to_numpy(), BETA.reindex_like(z).to_numpy()
    for i in range(len(Z)):
        m = ~np.isnan(Z[i]) & ~np.isnan(B[i])
        if m.sum() < MIN_COINS:
            continue
        w = Z[i, m] - Z[i, m].mean()
        X = np.c_[np.ones(m.sum()), B[i, m]]
        w = w - X @ np.linalg.lstsq(X, w, rcond=None)[0]       # remove dollar and beta exposure
        g = np.abs(w).sum()
        if g > 0:
            out[i, m] = w / g
    return pd.DataFrame(out, index=z.index, columns=z.columns)


def book_positions(score, mask, h, delay=0):
    W = neutral_weights(score, mask)
    keep = np.zeros(len(W), dtype=bool)
    keep[::h] = True
    W[~keep] = np.nan
    W = (W.ffill(limit=h - 1) if h > 1 else W).fillna(0.0)
    if delay:
        W = W.shift(delay).fillna(0.0)
    return W


def main():
    sigs = build_signals()
    print(f"{len(sigs)} signals built in {time.time() - t0:.0f}s", flush=True)
    dev_mask = (H >= DEV[0]) & (H <= pd.Timestamp(DEV[1]) + pd.Timedelta(hours=23))
    hold_mask = H >= HOLD[0]
    rows = []
    fwds = {}
    for h in HORIZONS:
        fwd = close.shift(-h) / close - 1
        fwd = fwd.where(valid.shift(-h, fill_value=False))
        fwds[h] = fwd
        for name, s in sigs.items():
            if name.startswith("season") and h != 1:
                continue
            ic = ic_series(s, fwd, valid)
            samp = ic.iloc[::h]
            d, ho = samp[dev_mask[::h]], samp[hold_mask[::h]]
            rows.append(dict(signal=name, h=h, ic_dev=d.mean(), t_dev=tstat(d), ic_hold=ho.mean(), t_hold=tstat(ho),
                             n_dev=d.notna().sum()))
        print(f"  horizon {h}h screened", flush=True)
    IC = pd.DataFrame(rows)
    IC.to_csv(os.path.join(ROOT, "reports", "xs_ic.csv"), index=False)
    print(f"\n{len(IC)} signal-horizon tests. Passing |t_dev| >= 3: {(IC.t_dev.abs() >= 3).sum()}")
    same_sign = IC[IC.t_dev.abs() >= 3]
    print(f"  of those, same sign on hold-out: {(np.sign(same_sign.ic_dev) == np.sign(same_sign.ic_hold)).sum()}, "
          f"hold-out |t| >= 2 same sign: {((np.sign(same_sign.ic_dev) == np.sign(same_sign.ic_hold)) & (same_sign.t_hold.abs() >= 2)).sum()}")
    print(IC.reindex(IC.t_dev.abs().sort_values(ascending=False).index).head(25).to_string(index=False, float_format=lambda v: f"{v:+.3f}"))

    # composites per horizon
    results, streams = [], {}
    sub = np.zeros(len(H), dtype=bool)
    sub[::24] = True
    sub &= dev_mask
    for h in HORIZONS:
        cand = IC[(IC.h == h) & (IC.t_dev.abs() >= 3)].sort_values("t_dev", key=np.abs, ascending=False)
        kept = []
        for _, c in cand.iterrows():
            z = cs_z(sigs[c.signal], valid)[sub]
            dup = False
            for k, _d in kept:
                zk = cs_z(sigs[k], valid)[sub]
                corr = (z * zk).sum(axis=1) / np.sqrt((z ** 2).sum(axis=1) * (zk ** 2).sum(axis=1))
                if corr.abs().mean() > 0.7:
                    dup = True
                    break
            if not dup:
                kept.append((c.signal, np.sign(c.ic_dev)))
        if not kept:
            print(f"h={h}: no signals pass")
            continue
        comp = sum(d * cs_z(sigs[k], valid).fillna(0.0) for k, d in kept) / len(kept)
        comp = comp.where(valid)
        for delay, cost, tag in [(0, ih.PERP_COST, "base"), (1, ih.PERP_COST, "1h delay"), (0, 0.0008, "cost 0.08%"),
                                 (0, 0.0, "gross")]:
            P = book_positions(comp, valid, h, delay)
            x = ih.run(P, close, cost=cost) if cost > 0 else ih.run(P, close, cost=0.0,
                                                                      funding=ih.hourly_funding(close.index, COINS9) * 0)
            turn = P.diff().abs().sum(axis=1).loc["2021-07-01":].groupby(P.loc["2021-07-01":].index.year).sum().mean()
            res = dict(h=h, variant=tag, signals=", ".join(f"{'+' if d > 0 else '-'}{k}" for k, d in kept),
                       n_signals=len(kept), turnover_per_yr=turn,
                       sharpe_dev=book.sharpe(x, *DEV), sharpe_hold=book.sharpe(x, *HOLD),
                       cagr_hold=book.summary(x, *HOLD)["cagr"], vol_hold=x.loc[HOLD[0]:].std() * np.sqrt(365))
            results.append(res)
            streams[f"xs_h{h}_{tag}"] = x
            print(f"h={h:2d} {tag:10s} signals={len(kept)} turnover {turn:6.0f}x/yr | Sharpe dev {res['sharpe_dev']:5.2f} | "
                  f"hold-out {res['sharpe_hold']:5.2f} | vol {res['vol_hold']:.1%}", flush=True)
        print(f"     kept: {res['signals']}")
    pd.DataFrame(results).to_csv(os.path.join(ROOT, "reports", "xs_books.csv"), index=False)
    pd.DataFrame(streams).to_parquet(os.path.join(ROOT, "reports", "xs_returns.parquet"))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
