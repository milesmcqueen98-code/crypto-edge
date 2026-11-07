#!/usr/bin/env python3
"""H3 (LM): the SPEC's descriptive checks, DEV days only (no HOLD day is loaded; the idea stopped at the mechanism
test, so HOLD is never read). Writes reports/hunt/h3lm/dev/dev_checks.json and the DEV-only daily.parquet of the
density variant that the selection rule would have picked had the mechanism test passed.

  python scripts/hunt/h3lm/dev_checks.py
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HUNT = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(HUNT))
sys.path.insert(0, HUNT)
sys.path.insert(0, HERE)
import gates  # noqa: E402
import lm  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h3lm")
DEV = os.path.join(OUT, "dev")


def nw_t(x):
    return lm.nw_t(np.asarray(x, float))


def main():
    M = json.load(open(os.path.join(DEV, "dev_mech.json")))
    d = pd.read_parquet(os.path.join(DEV, "dev_daily.parquet"))
    T = pd.read_parquet(os.path.join(DEV, "dev_trades.parquet"))
    U = pd.read_parquet(os.path.join(DEV, "dev_unit_cross.parquet"))
    tab = pd.read_csv(os.path.join(DEV, "dev_table.csv"))
    assert d.index.max() < gates.HOLD0 and (U.ts < gates.HOLD0).all() and (T.fill_ts < gates.HOLD0).all()
    dens = tab[(tab.arm == "dens") & (tab.trades >= 40)].sort_values(["t_alpha"], ascending=False)
    best = dens.iloc[0].cfg                                  # what the selection rule would have picked
    out = dict(best_density_cfg=best, mechanism_pass_any=bool(any(v["pass"] for v in M["mech"].values())))
    inc = gates.incumbent(100e3, days=d.index)
    for cfg in M["configs"]:
        r = {}
        for arm in ("dens", "ctrl"):
            s = d[f"{arm}_{cfg}|30000|0.5|2x"]
            tr = T[T.variant == f"{arm}_{cfg}"]
            top = s.sort_values(ascending=False)
            u = U[(U.cfg == cfg) & (U.arm == arm) & U.filled]
            r[arm] = dict(trades=int(len(tr)),
                          fills_per_year={int(k): int(v) for k, v in tr.groupby(tr.fill_ts.dt.year).size().items()},
                          by_coin=tr.groupby("coin").size().to_dict(), venue=tr.groupby("venue").size().to_dict(),
                          top3_share=float(top.head(3).sum() / s.sum()) if s.sum() > 0 else None,
                          years_2x={int(k): round(float(v), 4) for k, v in s.groupby(s.index.year).sum().items()},
                          corr_inc=float(np.corrcoef(s, inc)[0, 1]),
                          unit_fill_above_low_bp_median=float(u.low_dist_bp.median()) if len(u) else None,
                          unit_fill_at_low_share=float((u.low_dist_bp <= 10).mean()) if len(u) else None,
                          unit_tp_share=float(u.tp.mean()) if len(u) else None,
                          notional_median=float(tr.notional.median()) if len(tr) else None,
                          full_size_share=float((tr.notional >= 0.95 * 30000).mean()) if len(tr) else None,
                          sleeve_ret_yr_2x_fee012=None, sleeve_ret_yr_2x_fee030=None)
            if len(tr):
                yrs = len(s) / 365.25
                for fee in (0.12, 0.30):
                    p = lm.pnl(tr, 2.0, fee).reindex(d.index).fillna(0.0) / 30000
                    r[arm][f"sleeve_ret_yr_2x_fee{int(round(fee * 100)):03d}"] = float(p.sum() / yrs)
                    r[arm][f"sleeve_sharpe_2x_fee{int(round(fee * 100)):03d}"] = gates.sharpe(p)
        out[cfg] = r
    # paired difference of the best config by era and coin (unit events: only fills/crossings are stored, and a
    # non-crossing event has net 0 in both arms, so sums over stored rows equal sums over all events)
    ev = pd.read_csv(os.path.join(DEV, "dev_event_counts.csv"))
    u = U[U.cfg == best].copy()
    u["era"] = np.where(u.ts < pd.Timestamp("2024-06-01"), "2022-23", "2025-26")
    u["netf"] = np.where(u.filled, u.net, 0.0)
    g = u.groupby(["era", "coin", "arm"]).netf.sum().unstack("arm").fillna(0.0)
    n_ev = ev[(ev.cfg == best) & (ev.arm == "dens")].set_index("coin").events
    out["best_sum_net_bp_by_era_coin"] = {f"{e}|{c}": dict(dens=round(float(r_.dens), 1), ctrl=round(float(r_.ctrl), 1))
                                          for (e, c), r_ in g.iterrows()}
    out["best_events_by_coin"] = n_ev.to_dict()
    json.dump(out, open(os.path.join(DEV, "dev_checks.json"), "w"), indent=1, default=str)
    # DEV-only daily series of the would-be selection (HOLD days are not computed: the idea stopped at the screen)
    daily = pd.DataFrame({"s30_2x": d[f"dens_{best}|30000|0.5|2x"], "s50_2x": d[f"dens_{best}|50000|0.5|2x"],
                          "s30_1x": d[f"dens_{best}|30000|0.5|1x"], "s50_1x": d[f"dens_{best}|50000|0.5|1x"]})
    gates.assert_dev_only(daily.s30_2x)
    daily.to_parquet(os.path.join(OUT, "daily.parquet"))
    b = out[best]
    print("best density cfg (selection rule, had the screen passed):", best)
    for arm in ("dens", "ctrl"):
        x = b[arm]
        print(arm, {k: x[k] for k in ("trades", "fills_per_year", "top3_share", "corr_inc", "years_2x",
                                      "unit_fill_above_low_bp_median", "unit_fill_at_low_share", "unit_tp_share",
                                      "notional_median", "full_size_share", "sleeve_ret_yr_2x_fee012",
                                      "sleeve_ret_yr_2x_fee030", "venue", "by_coin")})
    print("sum net bp by era/coin:", out["best_sum_net_bp_by_era_coin"])


if __name__ == "__main__":
    main()
