#!/usr/bin/env python3
"""Long/short search with a development / hold-out split.

Benchmark: the live long-only rule (50/50 BTC/ETH while BTC > 100-day SMA, else cash).
Each round picks its best candidate by DEVELOPMENT Sharpe (Nov 2019 - Dec 2023) only.
A candidate counts as a winner only if it also beats the benchmark on the hold-outs it covers
(Jan 2024 - Nov 2026, and Jul 2016 - Nov 2019 for BTC/ETH-only rules).
All candidates are logged to reports/ls_search.csv so the number of trials is on record.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import features, ls  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def trend_signals(btc):
    """Each returns +1 (bull) / -1 (bear) per day, decided at the close."""
    sig = {}
    for n in (50, 100, 150, 200):
        sig[f"SMA{n}"] = np.sign(btc - btc.rolling(n).mean())
    for f, s in ((20, 100), (50, 200), (20, 50)):
        sig[f"MA{f}/{s}"] = np.sign(btc.rolling(f).mean() - btc.rolling(s).mean())
    for n in (30, 90, 180):
        sig[f"TSMOM{n}"] = np.sign(btc / btc.shift(n) - 1)
    for n in (20, 55):  # Donchian: flip on new N-day high / low, hold otherwise
        hi, lo = btc.rolling(n).max().shift(1), btc.rolling(n).min().shift(1)
        s = pd.Series(np.nan, index=btc.index)
        s[btc > hi], s[btc < lo] = 1.0, -1.0
        sig[f"Donchian{n}"] = s.ffill()
    return {k: v.fillna(0.0) for k, v in sig.items()}


def round_a(close):
    btc = close["BTC"]
    idx = close.index
    rows = []
    for sname, s in trend_signals(btc).items():
        up, dn = (s > 0).astype(float), (s < 0).astype(float)
        for long_leg in ("BTC+ETH", "BTC"):
            lb = {"BTC": 0.5, "ETH": 0.5} if long_leg == "BTC+ETH" else {"BTC": 1.0}
            for short in (0.0, 0.25, 0.5, 1.0):
                W = pd.DataFrame(0.0, index=idx, columns=["BTC", "ETH"])
                for a, w in lb.items():
                    W[a] += up * w
                W["BTC"] -= dn * short
                r = ls.returns(W)
                rows.append(ls.evaluate(f"{sname} | long {long_leg} | short BTC x{short}", r,
                                        "A trend" if short else "A trend (long-only)"))
    return rows


def round_b(close):
    btc, eth = close["BTC"], close["ETH"]
    idx = close.index
    rows = []
    live_up = (btc > btc.rolling(100).mean()).astype(float)
    sma50, sma200 = btc.rolling(50).mean(), btc.rolling(200).mean()
    ret20 = btc / btc.shift(20) - 1
    # B1 asymmetric: short only on confirmed bear (below 200d, 50<200, 20d momentum < 0)
    confirmed = ((btc < sma200) & (sma50 < sma200) & (ret20 < 0)).astype(float)
    # B2 confirmed bear with a stop: once stopped out (close above 20-day high), stay flat
    # until the bear condition resets (goes off, then on again)
    hi20 = btc.rolling(20).max().shift(1)
    stop_state, st, stopped = [], 0.0, False
    for d in idx:
        if not confirmed[d]:
            st, stopped = 0.0, False
        elif btc[d] > hi20[d]:
            st, stopped = 0.0, True
        elif not stopped:
            st = 1.0
        stop_state.append(st)
    confirmed_stop = pd.Series(stop_state, index=idx)
    # B3 short only in high-volatility down-trends (crash regime)
    vol30 = btc.pct_change().rolling(30).std() * np.sqrt(365)
    crash = ((btc < btc.rolling(100).mean()) & (vol30 > vol30.rolling(365, min_periods=180).median())).astype(float)
    for nm, bear in (("confirmed bear", confirmed), ("confirmed bear + stop", confirmed_stop), ("high-vol downtrend", crash)):
        for short in (0.25, 0.5, 1.0):
            W = pd.DataFrame({"BTC": 0.5 * live_up - short * bear, "ETH": 0.5 * live_up}, index=idx)
            rows.append(ls.evaluate(f"live long + short BTC x{short} on {nm}", ls.returns(W), "B asymmetric"))
    # B4 ETH/BTC relative trend (market-neutral pair), standalone and as overlay on live rule
    ratio = eth / btc
    for n in (30, 50, 100):
        rel = np.sign(ratio - ratio.rolling(n).mean()).fillna(0.0)
        for size in (0.25, 0.5, 1.0):
            pair = pd.DataFrame({"ETH": rel * size, "BTC": -rel * size}, index=idx)
            rows.append(ls.evaluate(f"ETH/BTC pair SMA{n} x{size} (standalone)", ls.returns(pair), "B pair"))
            live = pd.DataFrame({"BTC": 0.5 * live_up, "ETH": 0.5 * live_up}, index=idx)
            rows.append(ls.evaluate(f"live + ETH/BTC pair SMA{n} x{size}", ls.returns(live + pair), "B pair overlay"))
    # B5 rotation: in bull hold the stronger of BTC/ETH (by ratio trend), in bear short the weaker
    for n in (50, 100):
        rel = np.sign(ratio - ratio.rolling(n).mean()).fillna(0.0)
        strong_eth = (rel > 0).astype(float)
        for short in (0.0, 0.5, 1.0):
            # bull: hold the stronger coin; bear: short the weaker one (x0.0 = long-only rotation control)
            W = pd.DataFrame({"ETH": live_up * strong_eth, "BTC": live_up * (1 - strong_eth)}, index=idx)
            weak_short = (1 - live_up) * short
            W["ETH"] -= weak_short * (1 - strong_eth)
            W["BTC"] -= weak_short * strong_eth
            rows.append(ls.evaluate(f"rotate strong (ratio SMA{n}); short weak x{short} in bear", ls.returns(W), "B rotation"))
    return rows


def round_c(close, dvol):
    """Cross-sectional market-neutral baskets among the 30 most liquid coins (weekly refresh, Sunday)."""
    univ, v30 = features.universe(close, dvol)
    ret = close.pct_change(fill_method=None)
    vol90 = ret.rolling(90, min_periods=60).std()
    mom28 = close / close.shift(28) - 1
    P = pd.read_parquet(os.path.join(ROOT, "reports", "preds_cache.parquet")).pivot(index="date", columns="asset", values="pred")
    idx = close.index
    btc = close["BTC"]
    live_up = (btc > btc.rolling(100).mean()).astype(float)
    signals = {"low-vol": -vol90, "AI score": P.reindex(idx), "momentum": mom28}
    rows = []
    rebal = idx[idx.weekday == 6]
    for sname, score in signals.items():
        for k in (3, 5):
            W = pd.DataFrame(0.0, index=idx, columns=close.columns)
            cur = None
            for d in idx:
                if d in rebal:
                    top30 = v30.loc[d].where(univ.loc[d]).dropna().nlargest(30).index
                    s = score.loc[d, top30].dropna() if d in score.index else pd.Series(dtype=float)
                    if len(s) >= 2 * k + 4:
                        lo, hi = s.nsmallest(k).index, s.nlargest(k).index
                        cur = pd.Series(0.0, index=close.columns)
                        cur[hi] += 0.5 / k
                        cur[lo] -= 0.5 / k
                    else:
                        cur = None
                if cur is not None:
                    W.loc[d] = cur
            used = W.columns[(W != 0).any()]
            W = W[used]
            mn = ls.returns(W)
            rows.append(ls.evaluate(f"market-neutral {sname} top/bottom {k} of 30 (standalone)", mn, "C market-neutral"))
            live = pd.DataFrame({"BTC": 0.5 * live_up, "ETH": 0.5 * live_up}, index=idx)
            for w in (0.5, 1.0):
                comb = live.reindex(columns=sorted(set(live.columns) | set(W.columns)), fill_value=0.0).add(
                    (W * w).reindex(columns=sorted(set(live.columns) | set(W.columns)), fill_value=0.0), fill_value=0.0)
                rows.append(ls.evaluate(f"live + {w}x market-neutral {sname} {k}", ls.returns(comb), "C overlay"))
            # also: only run the neutral book when trend is down (shorts where they belong)
            Wd = W.mul(1 - live_up.reindex(W.index), axis=0)
            comb2 = live.reindex(columns=sorted(set(live.columns) | set(W.columns)), fill_value=0.0).add(
                Wd.reindex(columns=sorted(set(live.columns) | set(W.columns)), fill_value=0.0), fill_value=0.0)
            rows.append(ls.evaluate(f"live + market-neutral {sname} {k} in bear only", ls.returns(comb2), "C overlay"))
    return rows


def report(df, bench, label):
    fam = df[df.family.str.startswith(label)]
    fam = fam[~fam.family.str.contains("long-only")]
    best = fam.sort_values("dev_sharpe", ascending=False).head(5)
    print(f"\n=== Round {label}: {len(fam)} long/short candidates ===")
    print(f"benchmark (live long-only): dev {bench.dev_sharpe:.2f} | recent {bench.hold_recent_sharpe:.2f} | early {bench.hold_early_sharpe:.2f}")
    for _, r in best.iterrows():
        print(f"  {r['name'][:70]:70s} dev {r.dev_sharpe:5.2f} | recent {r.hold_recent_sharpe:5.2f} | "
              f"early {r.hold_early_sharpe:5.2f} | dev CAGR {r.dev_cagr:6.1%} DD {r.dev_maxdd:5.0%}")
    pick = best.iloc[0]
    beats_dev = pick.dev_sharpe > bench.dev_sharpe
    beats_recent = pick.hold_recent_sharpe > bench.hold_recent_sharpe
    beats_early = np.isnan(pick.hold_early_sharpe) or pick.hold_early_sharpe > bench.hold_early_sharpe
    verdict = "WINNER" if (beats_dev and beats_recent and beats_early) else "no winner"
    print(f"  -> dev pick: {pick['name']} | beats on dev {beats_dev}, recent {beats_recent}, early {beats_early}: {verdict}")
    n_beat_dev = (fam.dev_sharpe > bench.dev_sharpe).sum()
    n_beat_all = ((fam.dev_sharpe > bench.dev_sharpe) & (fam.hold_recent_sharpe > bench.hold_recent_sharpe) &
                  (fam.hold_early_sharpe.isna() | (fam.hold_early_sharpe > bench.hold_early_sharpe))).sum()
    print(f"  candidates beating benchmark on dev: {n_beat_dev}; on dev AND every hold-out: {n_beat_all}")
    return pick, verdict


def main():
    close, dvol, ret, fund = ls.load()
    idx = close.index
    btc = close["BTC"]
    up = (btc > btc.rolling(100).mean()).astype(float)
    bench_r = ls.returns(pd.DataFrame({"BTC": 0.5 * up, "ETH": 0.5 * up}, index=idx))
    bench = pd.Series(ls.evaluate("live long-only", bench_r, "benchmark"))
    which = sys.argv[1:] or ["A", "B", "C"]
    rows = [bench.to_dict()]
    if "A" in which:
        rows += round_a(close)
    if "B" in which:
        rows += round_b(close)
    if "C" in which:
        rows += round_c(close, dvol)
    df = pd.DataFrame(rows)
    out = os.path.join(ROOT, "reports", "ls_search.csv")
    if os.path.exists(out):
        old = pd.read_csv(out)
        df = pd.concat([old[~old.name.isin(df.name)], df], ignore_index=True)
    df.to_csv(out, index=False)
    for label in which:
        report(df, bench, label)
    lo = df[df.family == "A trend (long-only)"]
    if len(lo):
        b = lo.sort_values("dev_sharpe", ascending=False).iloc[0]
        print(f"\n(best long-only in the same grid, picked on dev: {b['name']} dev {b.dev_sharpe:.2f} | "
              f"recent {b.hold_recent_sharpe:.2f} | early {b.hold_early_sharpe:.2f})")


if __name__ == "__main__":
    main()
