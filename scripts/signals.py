#!/usr/bin/env python3
"""Daily signal: today's target portfolio for each strategy, using the same features and rules
as the backtest. Rebalances weekly (on the Sunday close); every other day reports status only.

Writes signals/latest.md (human-readable), signals/latest.json, signals/state.json (holdings
carried between weeks for the keep-until-rank-20 rule) and appends signals/history.csv.
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import data, features, model, portfolio as pf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "signals")
CAPITAL = 1000
REBAL_WEEKDAY = 6   # Sunday close -> act Monday


def main():
    os.makedirs(OUT, exist_ok=True)
    close, dvol, ret = data.load()
    X, univ, f = features.build(close, dvol, ret)
    asof = close.index[-1]
    m = model.fit(X[X.date < asof - pd.Timedelta(days=model.PURGE_DAYS)])
    today = X[X.date == asof].set_index("asset")
    ai = pd.Series(m.predict(today[model.feature_cols(X)]), index=today.index)
    lowvol = -f["vol_90"].where(univ).loc[asof]

    btc = close[features.REGIME_ASSET]
    sma = btc.rolling(features.REGIME_SMA).mean()
    risk_on = bool(btc.iloc[-1] > sma.iloc[-1])
    was_on = bool(btc.iloc[-2] > sma.iloc[-2])

    state_path = os.path.join(OUT, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    rebalance = asof.weekday() == REBAL_WEEKDAY or not state

    strategies = {
        "lowvol": ("Low-vol top 10 + trend", lowvol),
        "ai": ("AI model top 10 + trend", ai),
    }
    out = {"asof": str(asof.date()), "rebalance_day": rebalance, "risk_on": risk_on,
           "regime_flipped": risk_on != was_on,
           "btc_close": float(btc.iloc[-1]), "btc_sma100": float(sma.iloc[-1]), "strategies": {}}
    for key, (name, score) in strategies.items():
        prev = state.get(key, [])
        if rebalance:
            tgt = pf.top_k(score, frozenset(prev)) if risk_on else pd.Series(dtype=float)
            holds = list(tgt.index)
        else:
            holds = prev
        out["strategies"][key] = {"name": name, "holdings": holds,
                                  "buys": sorted(set(holds) - set(prev)), "sells": sorted(set(prev) - set(holds)),
                                  "top15": [[a, round(float(s), 4)] for a, s in score.dropna().sort_values(ascending=False).head(15).items()]}
        if rebalance:
            state[key] = holds
    out["strategies"]["btc_trend"] = {"name": "BTC trend filter", "holdings": ["BTC"] if risk_on else [],
                                      "buys": [], "sells": []}
    if rebalance:
        state["last_rebalance"] = out["asof"]
        json.dump(state, open(state_path, "w"), indent=1)
    json.dump(out, open(os.path.join(OUT, "latest.json"), "w"), indent=1)

    gap = btc.iloc[-1] / sma.iloc[-1] - 1
    md = [f"# Signal for {out['asof']} (daily close, UTC)", "",
          f"**Market regime: {'RISK ON' if risk_on else 'RISK OFF (hold cash)'}** — BTC ${btc.iloc[-1]:,.0f} is "
          f"{abs(gap):.1%} {'above' if gap > 0 else 'below'} its 100-day average (${sma.iloc[-1]:,.0f})."]
    if out["regime_flipped"]:
        md.append(f"\n> Regime flipped today. The tested rule acts at the weekly rebalance, not mid-week.")
    md.append("")
    md.append("**Rebalance day — act on this.**" if rebalance else
              f"Not a rebalance day (next: Sunday close). Holdings below are unchanged since {state.get('last_rebalance')}.")
    for key, s in out["strategies"].items():
        md += ["", f"## {s['name']}"]
        if not s["holdings"]:
            md.append("- Hold cash")
        else:
            w = CAPITAL / len(s["holdings"])
            md.append("- Hold: " + ", ".join(s["holdings"]) + f" (equal weight, ${w:,.0f} each on ${CAPITAL:,})")
        if s.get("buys"):
            md.append("- Buy: " + ", ".join(s["buys"]))
        if s.get("sells"):
            md.append("- Sell: " + ", ".join(s["sells"]))
    with open(os.path.join(OUT, "latest.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")

    hist = os.path.join(OUT, "history.csv")
    row = pd.DataFrame([{"date": out["asof"], "risk_on": risk_on, "rebalance": rebalance,
                         **{k: " ".join(v["holdings"]) for k, v in out["strategies"].items()}}])
    if os.path.exists(hist):
        h = pd.read_csv(hist)
        row = pd.concat([h[h["date"] != out["asof"]], row])
    row.to_csv(hist, index=False)
    print("\n".join(md))


if __name__ == "__main__":
    main()
