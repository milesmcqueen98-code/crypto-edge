#!/usr/bin/env python3
"""Edge hunt 2, EXP: the single HOLD read (run only AFTER the freeze commit of reports/hunt2/exp/frozen.json).

The frozen variant (rule, event set, assets, DEV thresholds of |F|) is run unchanged by exp.py's own functions over
every scored day: DEV (sel) events from reports/hunt2/exp/derived/fridays_dev.csv, HOLD (early, chk) events from
reports/hunt2/exp/derived/fridays_hold.csv (copied unchanged from the pre-freeze derive run's artifact by
scripts/hunt2/gamma/copy_hold.py). Sleeve daily returns at 2x and 1x on $25K/$50K/$75K/$125K -> daily.parquet
(s25_2x, s50_2x, s75_2x, s125_2x, s25_1x, ...); h2gates.path_b at 2x (the gates) and at 1x (information) ->
gates.json, with the events per era (prereg: an era is gated only with >= 60 scored days and >= 10 events; h2gates
counts every era with scored days, so both B3 readings are written).

usage: python scripts/hunt2/exp/exp_hold.py
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp as X  # noqa: E402
import h2gates as G  # noqa: E402  (exp puts the main clone's scripts/hunt2 on the path)


def main():
    fz = json.load(open(os.path.join(X.OUT, "frozen.json")))
    rule, ev, assets, th = fz["rule"], fz["evset"], fz["assets"], fz["thresholds"]
    E = pd.concat([X.event_table("sel", os.path.join(X.OUT, "derived", "fridays_dev.csv")),
                   X.event_table("hold", os.path.join(X.OUT, "derived", "fridays_hold.csv"))], ignore_index=True)
    E = E.sort_values(["date", "coin"]).reset_index(drop=True)
    T = X.trades(E, rule, ev, assets, th)
    days = G.SCORED
    cols, logs = {}, {}
    for cap in X.CAPS:
        for mult in (2.0, 1.0):
            s, L = X.sleeve(T, cap, mult, days)
            cols[f"s{cap // 1000}_{int(mult)}x"] = s
            logs[(cap, mult)] = L
    D = pd.DataFrame(cols, index=days)
    D.to_parquet(os.path.join(X.OUT, "daily.parquet"))
    g2 = G.path_b({c: D[f"s{c // 1000}_2x"] for c in X.CAPS}, days)
    g1 = G.path_b({c: D[f"s{c // 1000}_1x"] for c in X.CAPS}, days)
    L = logs[(50000, 2.0)].merge(T[["date", "coin", "side", "venue", "p_in", "p_out", "F", "r"]], on=["date", "coin"])
    L["era"] = G.era_of(L.date)
    L.to_csv(os.path.join(X.OUT, "hold_read_trades.csv"), index=False)
    ev_era = {e: int(L[(L.era == e) & (L.contracts > 0)].date.nunique()) for e in ("early", "sel", "chk")}
    days_era = {e: int((G.era_of(days) == e).sum()) for e in ("early", "sel", "chk")}
    gated = [e for e in G.HOLD_ERAS if days_era[e] >= 60 and ev_era[e] >= 10]
    out = dict(g2)
    out["x1"] = g1
    out["frozen_variant"] = fz["variant"]
    out["events_per_era"] = ev_era
    out["scored_days_per_era"] = days_era
    out["gated_eras_prereg"] = gated
    out["B3_prereg"] = bool(len(gated) > 0 and all(g2[f"{e}_gain"] > 0 for e in gated)) if gated else None
    out["pass_prereg"] = bool(g2["B1"] and g2["B2"] and g2["B4"] and (out["B3_prereg"] in (True, None)))
    json.dump(out, open(os.path.join(X.OUT, "gates.json"), "w"), indent=1, default=str)
    keys = ["a", "B1", "B2", "B3", "B4", "pass", "hold_gain", "hold_t_alpha", "chk_gain", "early_gain", "dev_gain",
            "dev_t_alpha", "years", "hold_sleeve_sharpe", "hold_corr", "dsr"]
    print({k: g2.get(k) for k in keys})
    print("1x:", {k: g1.get(k) for k in keys})
    print("events per era", ev_era, "gated (prereg)", gated, "B3_prereg", out["B3_prereg"])


if __name__ == "__main__":
    main()
