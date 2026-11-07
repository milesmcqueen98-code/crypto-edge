#!/usr/bin/env python3
"""H5 (AN) after the freeze (commit 1c05af4): run the frozen variant (reports/hunt/h5an/frozen.json) once over every
scored day (gates.ERA_DAYS), read HOLD once, apply gates.path_b at 2x costs, write gates.json and daily.parquet.
No parameter is chosen here.

usage: python scripts/hunt/h5an/final.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402
from sim import gates  # noqa: E402

FZ = json.load(open(os.path.join(sim.OUT, "frozen.json")))
DELTA, HOLD = int(FZ["params"]["delta_s"]), int(FZ["params"]["hold_min"]) * 60
CLASSES = tuple(FZ["params"]["classes"])


def run(M, mult, cap):
    t = sim.trades(M, DELTA, HOLD, mult, CLASSES, cap)
    t = t[t.exit_day.isin(sim.SCORED)]
    return t, sim.daily(t, cap, sim.SCORED)


def main():
    M = sim.load_events()
    out, tr = {}, {}
    S = {}
    for cap in (30000, 50000):
        for mult in (2.0, 1.0):
            t, s = run(M, mult, float(cap))
            S[f"s{cap // 1000}_{int(mult)}x"] = s
            tr[(cap, mult)] = t
    daily = pd.DataFrame(S).reindex(sim.SCORED).fillna(0.0)
    daily.index.name = "day"
    daily.to_parquet(os.path.join(sim.OUT, "daily.parquet"))
    g2 = gates.path_b({30000: daily.s30_2x, 50000: daily.s50_2x}, days=sim.SCORED)
    g1 = gates.path_b({30000: daily.s30_1x, 50000: daily.s50_1x}, days=sim.SCORED)
    out["path_b_2x"] = g2
    out["path_b_1x_info"] = g1
    # Path A only if the sleeve alone beats the incumbent (prereg); report the check
    inc = gates.incumbent(100e3, 0.5, "instant", sim.SCORED)
    out["sleeve_alone_sharpe_2x_full"] = gates.sharpe(daily.s30_2x)
    out["incumbent_sharpe_full"] = gates.sharpe(inc)
    if out["sleeve_alone_sharpe_2x_full"] > out["incumbent_sharpe_full"]:
        out["path_a_2x"] = gates.path_a(daily.s30_2x * (100e3 / 30e3), days=sim.SCORED)   # on $100K
    # descriptive
    t30 = tr[(30000, 2.0)]
    hold = t30.exit_day >= gates.HOLD0
    out["trades"] = {"all": int(len(t30)), "dev": int((~hold).sum()), "hold": int(hold.sum()),
                     "by_cls_dev": {k: int(v) for k, v in t30[~hold].cls.value_counts().items()},
                     "by_cls_hold": {k: int(v) for k, v in t30[hold].cls.value_counts().items()},
                     "by_year": {int(k): int(v) for k, v in t30.groupby(t30.exit.dt.year).size().items()}}
    out["hold_trades"] = t30[hold][["key", "cls", "release", "gross", "net", "usd", "pnl", "hs_bp"]].assign(
        release=lambda x: x.release.astype(str)).round(5).to_dict("records")
    out["mean_net_bp_2x"] = {"dev": float(t30[~hold].net.mean() * 1e4),
                             "hold": float(t30[hold].net.mean() * 1e4) if hold.any() else None}
    out["pnl_by_year_30k_2x"] = {int(k): float(v) for k, v in t30.groupby(t30.exit.dt.year).pnl.sum().items()}
    out["sleeve_years_30k_2x"] = {int(k): float(v) for k, v in gates.years(daily.s30_2x).items()}
    pos = t30.pnl.sum()
    out["top3_share_all"] = float(t30.pnl.nlargest(3).sum() / pos) if pos > 0 else None
    out["corr_incumbent_full"] = float(np.corrcoef(daily.s30_2x, gates.incumbent(70e3, 0.5, "instant",
                                                                                sim.SCORED))[0, 1])
    w = inc.nsmallest(20).index
    out["sleeve_on_incumbent_worst20_days_bp"] = float(daily.s30_2x.reindex(w).mean() * 1e4)
    out["capacity"] = {"mean_usd_30k": float(t30.usd.mean()), "share_at_5k": float((t30.usd >= 4999).mean()),
                       "mean_usd_50k": float(tr[(50000, 2.0)].usd.mean())}
    out["frozen"] = {"variant": FZ["variant"], "freeze_commit": "1c05af4", "code_commit_in_frozen": FZ["code_commit"]}
    out["hold_read_utc"] = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(sim.OUT, "gates.json"), "w") as f:
        json.dump(out, f, indent=1, default=lambda x: sim.nan2none(float(x)) if isinstance(x, (np.floating, float))
                  else (int(x) if isinstance(x, (np.integer,)) else (bool(x) if isinstance(x, np.bool_) else str(x))))
    keys = ["a", "full_t_alpha", "dev_t_alpha", "hold_t_alpha", "full_gain", "dev_gain", "hold_gain", "full_book_sharpe",
            "full_inc_sharpe", "hold_book_sharpe", "hold_inc_sharpe", "full_sleeve_sharpe", "hold_sleeve_sharpe", "dsr",
            "n_trials", "years", "G1", "G2", "G3", "G4", "G5", "pass_G1_G5"]
    print("2x:", json.dumps({k: g2[k] for k in keys}, default=str))
    print("1x:", json.dumps({k: g1[k] for k in keys}, default=str))
    print(json.dumps({k: out[k] for k in ("trades", "mean_net_bp_2x", "pnl_by_year_30k_2x", "top3_share_all",
                                          "corr_incumbent_full", "sleeve_on_incumbent_worst20_days_bp", "capacity")},
                     default=str))


if __name__ == "__main__":
    main()
