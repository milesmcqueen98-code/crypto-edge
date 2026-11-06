#!/usr/bin/env python3
"""Final, robust comparison. Two fixes over research.py:
1. The trend filter is checked DAILY (exit/enter the day BTC crosses its 100-day average);
   coin selection still refreshes weekly. Weekly-only checks made results swing 7%-26% CAGR
   depending on the weekday chosen.
2. Every weekly strategy is run on all 7 weekday phases and averaged, with the range shown.
Writes reports/final.json."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import data, features, model, portfolio as pf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOWS = {"B": "2021-07-01"}
PRED_CACHE = os.path.join(ROOT, "reports", "preds_cache.parquet")


def daily_regime_targets(scores, on, start, phase, k=pf.TOP_K, buffer=pf.BUFFER, fixed=None):
    """Hold top-k by score (or a fixed basket) while regime is on; cash the day it turns off.
    Selection refreshes on the weekly phase day or on re-entry."""
    idx = on.loc[start:].index
    weekly = set(idx[phase::7])
    targets, held, was_on = {}, frozenset(), False
    for d in idx:
        if not on[d]:
            if was_on:
                targets[d] = pd.Series(dtype=float)
            held, was_on = frozenset(), False
            continue
        if d in weekly or not was_on:
            if fixed is not None:
                targets[d] = fixed
            else:
                if d not in scores.index:
                    was_on = True
                    continue
                targets[d] = pf.top_k(scores.loc[d], held, k, buffer)
            held = frozenset(targets[d].index)
        was_on = True
    return targets


def weekly_targets(scores, start, phase, univ=None):
    idx = scores.loc[start:].index
    if univ is not None:  # equal weight universe
        return {d: pd.Series(1.0 / univ.loc[d].sum(), index=univ.columns[univ.loc[d]]) for d in idx[phase::7]}
    return pf.run_rule({d: scores.loc[d] for d in idx[phase::7]})


def summarize(runs):
    keys = ["cagr", "sharpe", "maxdd", "pct_months_up20", "worst_month"]
    out = {k: float(np.mean([r[k] for r in runs])) for k in keys}
    out |= {f"{k}_min": float(np.min([r[k] for r in runs])) for k in ["cagr", "sharpe", "maxdd"]}
    out |= {f"{k}_max": float(np.max([r[k] for r in runs])) for k in ["cagr", "sharpe", "maxdd"]}
    out["cagr_cost50"] = float(np.mean([r["cagr_cost50"] for r in runs]))
    return out


def main():
    close, dvol, ret = data.load()
    X, univ, f = features.build(close, dvol, ret)
    if os.path.exists(PRED_CACHE):
        preds = pd.read_parquet(PRED_CACHE)
    else:
        preds = model.walk_forward(X, "2021-07-01")
        preds.to_parquet(PRED_CACHE, index=False)
    P = preds.pivot(index="date", columns="asset", values="pred")
    on_btc = features.regime(close)
    lowvol = (-f["vol_90"]).where(univ)
    mom = f["ret_28"].where(univ)
    btc_only = pd.Series({"BTC": 1.0})
    btc_eth = pd.Series({"BTC": 0.5, "ETH": 0.5})

    res = {}
    for w, start in WINDOWS.items():
        strategies = {
            "BTC buy & hold": lambda ph: {close.loc[start:].index[0]: btc_only},
            "BTC trend filter": lambda ph: daily_regime_targets(None, on_btc, start, ph, fixed=btc_only),
            "BTC+ETH trend filter": lambda ph: daily_regime_targets(None, on_btc, start, ph, fixed=btc_eth),
            "Low-vol top 10 + trend": lambda ph: daily_regime_targets(lowvol, on_btc, start, ph),
            "AI model top 10 + trend": lambda ph: daily_regime_targets(P, on_btc, start, ph),
            "AI model top 3 + trend": lambda ph: daily_regime_targets(P, on_btc, start, ph, k=3, buffer=5),
            "Momentum top 10 + trend": lambda ph: daily_regime_targets(mom, on_btc, start, ph),
            "Equal-weight top 50": lambda ph: weekly_targets(close, start, ph, univ),
        }
        res[w] = {}
        curves = {}
        for name, make in strategies.items():
            runs = []
            for ph in range(7):
                tg = make(ph)
                eq, _ = pf.simulate(ret, tg, start)
                s = pf.stats(eq)
                s["cagr_cost50"] = pf.stats(pf.simulate(ret, tg, start, 0.005)[0])["cagr"]
                runs.append(s)
                if ph == 0:
                    curves[name] = eq
                if name == "BTC buy & hold":
                    break
            res[w][name] = summarize(runs)
            r = res[w][name]
            print(f"[{w}] {name:26s} CAGR {r['cagr']:+6.1%} ({r['cagr_min']:+.0%}..{r['cagr_max']:+.0%})  "
                  f"Sharpe {r['sharpe']:.2f} ({r['sharpe_min']:.2f}..{r['sharpe_max']:.2f})  "
                  f"MaxDD {r['maxdd']:.0%}  CAGR@0.5% {r['cagr_cost50']:+.1%}", flush=True)
        wk = pd.DataFrame(curves).resample("W").last().pct_change().dropna()
        res[w]["_curves"] = {k: [[str(i.date()), round(float(v), 5)] for i, v in c.resample("W").last().items()]
                             for k, c in curves.items()}
        res[w]["_diffs"] = {}
        for a, b in [("AI model top 10 + trend", "BTC trend filter"), ("Low-vol top 10 + trend", "BTC trend filter"),
                     ("AI model top 10 + trend", "Low-vol top 10 + trend"), ("BTC trend filter", "BTC buy & hold"),
                     ("BTC+ETH trend filter", "BTC trend filter")]:
            d = wk[a] - wk[b]
            res[w]["_diffs"][f"{a} vs {b}"] = {"weekly_mean": d.mean(), "t": d.mean() / d.std() * np.sqrt(len(d)),
                                               "weeks": len(d)}
            print(f"   {a} vs {b}: {d.mean():+.3%}/wk  t {d.mean() / d.std() * np.sqrt(len(d)):+.2f}")
    json.dump(res, open(os.path.join(ROOT, "reports", "final.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
