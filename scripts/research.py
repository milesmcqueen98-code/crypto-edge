#!/usr/bin/env python3
"""Full research run: walk-forward ML + rule baselines on the Coinbase/Kraken universe.
Writes reports/results.json and reports/research.md."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import data, features, model, portfolio as pf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_START = "2021-07-01"   # first date with a full 50-coin universe plus >1 year of training data


def main():
    close, dvol, ret = data.load()
    X, univ, f = features.build(close, dvol, ret)
    print("universe size by year:", univ.sum(axis=1).groupby(univ.index.year).mean().round(1).to_dict())
    preds = model.walk_forward(X, TEST_START)
    ic = model.weekly_ic(preds)
    ic_mom = model.weekly_ic(preds.merge(X[["date", "asset", "ret_28_r"]]), "ret_28_r")
    ic_lv = model.weekly_ic(preds.merge(X[["date", "asset", "vol_90_r"]]).assign(lv=lambda d: -d.vol_90_r), "lv")

    risk_on = features.regime(close)
    P = preds.pivot(index="date", columns="asset", values="pred")
    rb = [d for d in close.loc[TEST_START:].index[:: pf.REBAL_EVERY] if d in P.index]
    mom = f["ret_28"].where(univ)
    lowvol = -f["vol_90"].where(univ)
    btc = features.REGIME_ASSET

    S = {
        "BTC buy & hold": {rb[0]: pd.Series({btc: 1.0})},
        "Equal-weight top 50": {d: pd.Series(1.0 / univ.loc[d].sum(), index=univ.columns[univ.loc[d]]) for d in rb},
        "BTC trend filter": {d: pd.Series({btc: 1.0}) if risk_on[d] else pd.Series(dtype=float) for d in rb},
        "Momentum top 10 + trend": pf.run_rule({d: mom.loc[d] for d in rb}, risk_on),
        "Low-vol top 10 + trend": pf.run_rule({d: lowvol.loc[d] for d in rb}, risk_on),
        "AI model top 10 + trend": pf.run_rule({d: P.loc[d] for d in rb}, risk_on),
        "AI model top 10 (no filter)": pf.run_rule({d: P.loc[d] for d in rb}),
    }
    res, curves = {}, {}
    for name, tg in S.items():
        eq, turn = pf.simulate(ret, tg, TEST_START)
        res[name] = pf.stats(eq) | {"weekly_turnover": turn,
                                    "cagr_at_0.5pct_cost": pf.stats(pf.simulate(ret, tg, TEST_START, 0.005)[0])["cagr"]}
        curves[name] = eq
    wk = pd.DataFrame(curves).resample("W").last().pct_change().dropna()
    diffs = {}
    for a, b in [("AI model top 10 + trend", "Low-vol top 10 + trend"),
                 ("AI model top 10 + trend", "BTC trend filter"),
                 ("Low-vol top 10 + trend", "BTC trend filter"),
                 ("AI model top 10 + trend", "Momentum top 10 + trend")]:
        d = wk[a] - wk[b]
        diffs[f"{a} vs {b}"] = {"weekly_mean": d.mean(), "t": d.mean() / d.std() * np.sqrt(len(d)), "weeks": len(d)}

    out = {"period": [str(wk.index[0].date()), str(close.index[-1].date())],
           "coins_in_data": int(close.shape[1]),
           "ic": {"ai_model": ic, "momentum_28d": ic_mom, "low_vol": ic_lv},
           "results": res, "diffs": diffs,
           "curves": {k: [[str(i.date()), round(float(v), 5)] for i, v in c.resample("W").last().items()]
                      for k, c in curves.items()}}
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "reports", "results.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)

    lines = [f"# Research results ({out['period'][0]} to {out['period'][1]})", "",
             f"Universe: point-in-time top {features.TOP_N} USD-tradable coins by 30-day volume "
             f"({out['coins_in_data']} coins in data). Costs: {pf.COST:.2%} per side.", "",
             "| Strategy | CAGR | Vol | Sharpe | Max DD | CAGR @0.5% cost |", "|---|---|---|---|---|---|"]
    for k, r in res.items():
        lines.append(f"| {k} | {r['cagr']:.1%} | {r['vol']:.0%} | {r['sharpe']:.2f} | {r['maxdd']:.0%} | "
                     f"{r['cagr_at_0.5pct_cost']:.1%} |")
    lines += ["", "Weekly IC (Spearman, non-overlapping): " +
              ", ".join(f"{k} {v[0]:+.3f} (t {v[1]:+.1f})" for k, v in out["ic"].items()), "",
              "Head-to-head (weekly return difference):"]
    lines += [f"- {k}: {v['weekly_mean']:+.3%}/wk, t {v['t']:+.2f}" for k, v in diffs.items()]
    with open(os.path.join(ROOT, "reports", "research.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
