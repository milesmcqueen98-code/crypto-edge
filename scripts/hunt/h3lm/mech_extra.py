#!/usr/bin/env python3
"""H3 (LM): descriptive extras for the mechanism screen (DEV only; not trials, no P&L, no HOLD day loaded).

1. The paired density-vs-control test at 1x costs and split by era (net_1x = (gross + net_2x) / 2: every cost term
   scales linearly with the multiplier).
2. Where the cluster sits: for BTC and SOL in the 2025-26 DEV era (N = 14), the share of hours whose max-density
   bucket is the deepest eligible bucket (the 5% Fair Value Limit binding) and the cluster depth quantiles.

  python scripts/hunt/h3lm/mech_extra.py
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lm  # noqa: E402

DEV = os.path.join(lm.OUT, "dev")


def paired(U, ev, cfg, era=None, mult=2):
    u = U[U.cfg == cfg].copy()
    if era is not None:
        u = u[(u.ts < pd.Timestamp("2024-06-01")) == (era == "2022-23")]
    u["v"] = np.where(u.filled, u.net if mult == 2 else (u.gross + u.net) / 2, 0.0)
    p = u.pivot_table(index=["coin", "h"], columns="arm", values="v", aggfunc="sum").fillna(0.0)
    day = u.groupby(["coin", "h"]).ts.first().dt.floor("D").reindex(p.index)
    dif = (p.get("dens", 0.0) - p.get("ctrl", 0.0)).to_numpy()
    n_all = int(ev[(ev.cfg == cfg) & (ev.arm == "dens")].events.sum()) if era is None else None
    if n_all is None:                                  # events per era: hours with a valid bid in that era
        n_all = int(len(dif)) + int(EV_ERA[(cfg, era)])
    z = np.concatenate([dif, np.zeros(max(0, n_all - len(dif)))])
    t = float(z.mean() / (z.std(ddof=1) / math.sqrt(len(z)))) if z.std() > 0 else float("nan")
    daily = pd.Series(dif).groupby(day.to_numpy()).sum()
    return dict(n=len(z), diff_mean_bp=float(z.mean()), t_event=t, t_day=lm.nw_t(daily.to_numpy()))


EV_ERA = {}


def main():
    U = pd.read_parquet(os.path.join(DEV, "dev_unit_cross.parquet"))
    ev = pd.read_csv(os.path.join(DEV, "dev_event_counts.csv"))
    M = json.load(open(os.path.join(DEV, "dev_mech.json")))
    out = {"paired_1x": {}, "paired_2x_by_era": {}}
    for cfg in M["configs"]:
        out["paired_1x"][cfg] = paired(U, ev, cfg, mult=1)
    # events by era are not stored separately: split the non-crossing events in proportion to decision hours
    hrs = {"2022-23": 0, "2025-26": 0}
    for k, v in M["meta"].items():
        hrs["2022-23" if k.endswith("early") else "2025-26"] += v["hours"]
    for cfg in M["configs"]:
        n_tot = int(ev[(ev.cfg == cfg) & (ev.arm == "dens")].events.sum())
        stored = U[U.cfg == cfg].groupby(["coin", "h"]).ts.first()
        for era in ("2022-23", "2025-26"):
            st = int(((stored < pd.Timestamp("2024-06-01")) == (era == "2022-23")).sum())
            share = hrs[era] / sum(hrs.values())
            EV_ERA[(cfg, era)] = max(0, int(round(n_tot * share)) - st)
        out["paired_2x_by_era"][cfg] = {era: paired(U, ev, cfg, era=era) for era in ("2022-23", "2025-26")}
    # cluster location (BTC, SOL; 2025-01 .. 2026-05; N = 14)
    loc = {}
    for coin in ("BTC", "SOL"):
        D = lm.prepare(coin, "main", lm.HOLD0, (14,))
        hist, bmin = D["H"][14]
        for R in lm.GRID_R:
            b, has, d_lo, d_hi = lm.pick_cluster(hist, bmin, D["lp0"], R)
            depth = D["lp0"] - (b + 0.5) * lm.DELTA
            ok = has & np.isfinite(depth)
            dep = depth[ok]
            loc[f"{coin}|R{R[0]}-{R[1]}"] = dict(hours=int(ok.sum()), cap_binding_share=float(np.mean(dep >= d_hi - lm.DELTA)),
                                                   cluster_depth_bp_q10_50_90=[round(float(x) * 1e4, 1) for x in
                                                                               np.quantile(dep, [0.1, 0.5, 0.9])],
                                                   eligible_range_bp=[round(d_lo * 1e4, 1), round(d_hi * 1e4, 1)])
        del D
    out["cluster_location"] = loc
    json.dump(out, open(os.path.join(DEV, "mech_extra.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
