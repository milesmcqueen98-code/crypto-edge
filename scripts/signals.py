#!/usr/bin/env python3
"""Daily signal for the live strategy, plus shadow tracking of the AI coin-picker.

LIVE  - BTC+ETH trend filter: when BTC closes above its 100-day average, hold 50% BTC / 50% ETH;
        when it closes below, hold cash. Checked every daily close (UTC). Only a flip is a trade.
SHADOW - AI model top 10 + trend and Low-vol top 10 + trend: logged every day, never traded,
        so their live out-of-sample record builds up and can be judged later.

Writes signals/latest.md, signals/latest.json, signals/state.json; appends signals/history.csv.
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
LIVE = {"BTC": 0.5, "ETH": 0.5}


def main():
    os.makedirs(OUT, exist_ok=True)
    close, dvol, ret = data.load()
    asof = close.index[-1]
    btc = close[features.REGIME_ASSET]
    sma = btc.rolling(features.REGIME_SMA).mean()
    risk_on, was_on = bool(btc.iloc[-1] > sma.iloc[-1]), bool(btc.iloc[-2] > sma.iloc[-2])
    gap = btc.iloc[-1] / sma.iloc[-1] - 1

    state_path = os.path.join(OUT, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    first_run = "live_position" not in state
    target = "BTC+ETH" if risk_on else "CASH"
    action = first_run or state.get("live_position") != target

    # shadow: AI ranker (trained on all labelled history) and the low-vol rule
    X, univ, f = features.build(close, dvol, ret)
    m = model.fit(X[X.date < asof - pd.Timedelta(days=model.PURGE_DAYS)])
    today = X[X.date == asof].set_index("asset")
    ai = pd.Series(m.predict(today[model.feature_cols(X)]), index=today.index)
    lowvol = (-f["vol_90"]).where(univ).loc[asof]
    shadow = {}
    for key, score in [("ai_top10", ai), ("lowvol_top10", lowvol)]:
        held = frozenset(state.get(key, []))
        picks = list(pf.top_k(score, held).index)   # logged regardless of regime
        shadow[key] = picks
        state[key] = picks

    state["live_position"] = target
    if action:
        state["last_trade"] = str(asof.date())
    json.dump(state, open(state_path, "w"), indent=1)

    out = {"asof": str(asof.date()), "risk_on": risk_on, "flipped_today": risk_on != was_on,
           "action_needed": action, "live_target": target, "btc_close": float(btc.iloc[-1]),
           "btc_sma100": float(sma.iloc[-1]), "gap_pct": float(gap),
           "eth_close": float(close["ETH"].iloc[-1]), "shadow": shadow,
           "ai_top15": [[a, round(float(s), 4)] for a, s in ai.sort_values(ascending=False).head(15).items()]}
    json.dump(out, open(os.path.join(OUT, "latest.json"), "w"), indent=1)

    if first_run and target == "CASH":
        trade_line = "**Starting position: cash.** Don't buy yet; the first buy comes when BTC closes above its 100-day average."
        hold_line = ""
    elif target == "BTC+ETH":
        hold_line = f"Hold **50% BTC / 50% ETH** (${CAPITAL * 0.5:,.0f} each on ${CAPITAL:,})."
        trade_line = "**ACTION: Buy BTC and ETH, 50/50, with your cash.**"
    else:
        hold_line = "Hold **cash** (USD or USDC)."
        trade_line = "**ACTION: Sell your BTC and ETH to cash.**"
    if first_run and target == "CASH":
        hold_line = ""
    md = [f"# Signal for {out['asof']} (daily close, UTC)", "",
          f"BTC ${btc.iloc[-1]:,.0f} is {abs(gap):.1%} {'above' if gap > 0 else 'below'} its 100-day average "
          f"(${sma.iloc[-1]:,.0f}) → **{'RISK ON' if risk_on else 'RISK OFF'}**.", ""]
    md.append(trade_line if action else f"No trade today. {hold_line} (unchanged since {state.get('last_trade', 'start')})")
    if action and hold_line:
        md += ["", hold_line]
    md += ["", "## Shadow tracking (logged daily, never traded)",
           f"- AI model top 10{'' if risk_on else ' (would hold if risk on)'}: {', '.join(shadow['ai_top10'])}",
           f"- Low-vol top 10{'' if risk_on else ' (would hold if risk on)'}: {', '.join(shadow['lowvol_top10'])}"]
    with open(os.path.join(OUT, "latest.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")

    hist = os.path.join(OUT, "history.csv")
    row = pd.DataFrame([{"date": out["asof"], "btc_close": round(float(btc.iloc[-1]), 2),
                         "btc_sma100": round(float(sma.iloc[-1]), 2), "risk_on": risk_on,
                         "live_target": target, "action": action,
                         "ai_top10": " ".join(shadow["ai_top10"]), "lowvol_top10": " ".join(shadow["lowvol_top10"])}])
    if os.path.exists(hist):
        h = pd.read_csv(hist)
        row = pd.concat([h[h["date"] != out["asof"]], row])
    row.to_csv(hist, index=False)
    print("\n".join(md))


if __name__ == "__main__":
    main()
