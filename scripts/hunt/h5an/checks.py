#!/usr/bin/env python3
"""H5 (AN) post-freeze fill-realism checks on the frozen variant (information only; no parameter is chosen, nothing is
logged as a trial). Uses the committed 10-second bars (data/hunt/h5an/bars_*.parquet) and the per-event lookups.

1. Participation: our $ size vs the buyer-initiated USD printed in the 10 s / 60 s after our entry print, and vs the
   seller-initiated USD in the 60 s after our exit print.
2. Worst-print bound: entry at the highest print in the 10-second buckets holding the entry print and the next one
   (<= 20 s), exit at the lowest print in the bucket holding the exit print and the next one; taker fee only (the
   worst print stands in for the half-spread and impact). 1x and 2x fee.
3. Detection-latency sensitivity is read from the logged DEV grid (delta 2 / 10 / 30 s); not recomputed here.
usage: python scripts/hunt/h5an/checks.py  -> reports/hunt/h5an/checks.json
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402
from sim import gates, common  # noqa: E402

FZ = json.load(open(os.path.join(sim.OUT, "frozen.json")))
DELTA, HOLD = int(FZ["params"]["delta_s"]), int(FZ["params"]["hold_min"]) * 60


def main():
    M = sim.load_events()
    t = sim.trades(M, DELTA, HOLD, 2.0, tuple(FZ["params"]["classes"]), 30000.0)
    t = t[t.exit_day.isin(sim.SCORED)].copy()
    Mk = M.set_index("key")
    t["buy10"] = t.key.map(Mk[f"e{DELTA}_buyusd10"])
    t["buy60"] = t.key.map(Mk[f"e{DELTA}_buyusd60"])
    t["sell60x"] = t.key.map(Mk[f"x{DELTA}_{HOLD}_sellusd60"])
    hold = t.exit_day >= gates.HOLD0
    out = {}
    for nm, m in (("dev", ~hold), ("all", np.ones(len(t), bool))):
        s = t[m]
        out[f"participation_{nm}"] = {
            "median_size_over_buy10": float((s.usd / s.buy10.replace(0, np.nan)).median()),
            "median_size_over_buy60": float((s.usd / s.buy60.replace(0, np.nan)).median()),
            "share_size_gt_half_buy60": float((s.usd > 0.5 * s.buy60).mean()),
            "share_size_gt_quarter_buy60": float((s.usd > 0.25 * s.buy60).mean()),
            "median_size_over_sell60_at_exit": float((s.usd / s.sell60x.replace(0, np.nan)).median())}
        # P&L kept if size were capped at theta x buyer USD in the 60 s after entry (information only)
        for th in (0.5, 0.25):
            k = np.minimum(1.0, th * s.buy60 / s.usd)
            out[f"participation_{nm}"][f"pnl_share_kept_theta{th}"] = float((s.pnl * k).sum() / s.pnl.sum())
    B = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(sim.D, "bars_*.parquet")))])
    B = B.set_index(["key", "b"]).sort_index()
    worst = []
    for r in t.itertuples():
        eb, xb = int(r.e_ms // 10000), int(r.x_ms // 10000)
        try:
            be = B.loc[r.key]
        except KeyError:
            worst.append((np.nan, np.nan))
            continue
        hi = be.loc[be.index.isin([eb, eb + 1]), "high"].max()
        lo = be.loc[be.index.isin([xb, xb + 1]), "low"].min()
        worst.append((hi, lo))
    t["e_worst"], t["x_worst"] = [w[0] for w in worst], [w[1] for w in worst]
    for mult in (1.0, 2.0):
        fee = common.SPOT_TAKER * mult
        t[f"net_worst_{int(mult)}x"] = (t.x_worst * (1 - fee)) / (t.e_worst * (1 + fee)) - 1
    for nm, m in (("dev", ~hold), ("hold", hold), ("all", np.ones(len(t), bool))):
        s = t[m]
        out[f"worst_print_{nm}"] = {
            "n": int(s.e_worst.notna().sum()),
            "entry_worst_vs_print_bp_median": float(((s.e_worst / s.e_px - 1) * 1e4).median()),
            "exit_worst_vs_print_bp_median": float(((s.x_worst / s.x_px - 1) * 1e4).median()),
            "mean_net_model_2x_bp": float(s.net.mean() * 1e4),
            "mean_net_worst_1x_bp": float(s.net_worst_1x.mean() * 1e4),
            "mean_net_worst_2x_bp": float(s.net_worst_2x.mean() * 1e4),
            "pnl_model_2x": float(s.pnl.sum()),
            "pnl_worst_2x": float((s.usd * s.net_worst_2x).sum())}
    # sleeve Sharpe under the worst-print bound (information)
    tw = t.assign(pnl=t.usd * t.net_worst_2x)
    sw = sim.daily(tw, 30000.0, sim.SCORED)
    out["worst_print_sleeve_sharpe_2x_all"] = gates.sharpe(sw)
    out["worst_print_t_alpha70_dev"] = sim.alpha70(sw[sw.index < gates.HOLD0], sim.dev_days())["t_alpha"]
    out["model_sleeve_sharpe_2x_all"] = gates.sharpe(sim.daily(t, 30000.0, sim.SCORED))
    # how many trades entered late (first print >= delta came much later than delta)
    lat = (t.entry - t.release).dt.total_seconds()
    out["entry_latency_s"] = {"median": float(lat.median()), "p75": float(lat.quantile(.75)),
                              "share_gt_10s": float((lat > 10).mean()), "share_gt_60s": float((lat > 60).mean())}
    with open(os.path.join(sim.OUT, "checks.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
