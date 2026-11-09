#!/usr/bin/env python3
"""Edge hunt 2, GAMMA: the single HOLD read (run only AFTER the freeze commit of reports/hunt2/gamma/frozen.json).

The frozen variant (signal column, threshold number) is applied unchanged: skipped hours are those whose hourly
signal is below the frozen threshold, from the DEV file for the sel era (exactly the logged DEV trial) and from
the DEV + HOLD files for chk and early (reports/hunt2/gamma/derived/gamma_hourly_hold.parquet, copied unchanged from
the pre-freeze derive run's artifact by scripts/hunt2/gamma/copy_hold.py; the DEV file only matters for any sim
warm-up minutes before an era's first day). The steps of pathA.hold_read (X2/X1/S on every era at $250K through
pathA.run_mult, daily.parquet with x2, x1, s, and h2gates.path_a -> gates.json) are run one era at a time with the
simulator's caches released in between (memory on the shared machine); the numbers are those hold_read computes.
Skip counts per era are added to gates.json.

usage: python scripts/hunt2/gamma/gamma_hold.py
"""
import gc
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamma as GM  # noqa: E402


def main():
    fz = json.load(open(os.path.join(GM.OUT, "frozen.json")))
    col, thr = fz["col"], float(fz["thr_value"])
    H_dev, H_hold = GM.signal("dev"), GM.signal("hold")
    H_all = pd.concat([H_dev, H_hold]).sort_index()
    hrs = {"sel": GM.skip_hours(H_dev, col, thr), "chk": GM.skip_hours(H_all, col, thr),
           "early": GM.skip_hours(H_all, col, thr)}
    info = {}
    # pathA.hold_read's steps (X2/X1/S per era, concat, de-duplicate, daily.parquet, h2gates.path_a), run one era at a
    # time with the simulator's caches released in between (the shared 8 GB machine cannot hold all three eras).
    G = GM.pathA._gates()
    cols = {"x2": [], "x1": [], "s": []}
    for era in ("sel", "chk", "early"):
        m, n_min = GM.mult(era, hrs[era])
        n_skip, n_par = GM.n_skipped(era, hrs[era])
        info[era] = dict(skip_minutes=n_min, parents=n_par, parents_skipped=n_skip,
                         frac_parents=n_skip / n_par if n_par else None)
        for cost, k in (("X2", "x2"), ("X1", "x1"), ("S", "s")):
            cols[k].append(GM.pathA.run_mult(era, m, cost=cost))
            print(era, cost, "done", flush=True)
        del m
        GM.F._A.clear()
        if era == "chk":
            GM.F.RL._IN.clear()
        gc.collect()
    D = pd.DataFrame({k: pd.concat(v).sort_index() for k, v in cols.items()})
    D = D[~D.index.duplicated()]
    D.to_parquet(os.path.join(GM.OUT, "daily.parquet"))
    g = G.path_a(D["x2"], D["x1"], D.index)
    for era, (lo, hi) in (("chk", ("2026-04-01", "2026-11-06")), ("early", ("2022-01-01", "2024-01-01"))):
        sh = H_hold.loc[(H_hold.index >= lo) & (H_hold.index < hi), col]
        info[era].update(hours=len(sh), frac_hours_skipped=float((sh < thr).mean()))
    g["skips"] = info
    g["frozen_variant"] = fz["variant"]
    json.dump(g, open(os.path.join(GM.OUT, "gates.json"), "w"), indent=1, default=str)
    keys = ["A1", "A2", "A3", "A4", "pass", "hold_t_x2", "hold_mean_bp_x2", "hold_mean_bp_x1", "chk_mean_bp_x2",
            "early_mean_bp_x2", "chk_t_x2", "early_t_x2", "dev_t_x2", "years_x2", "dsr", "hold_dsharpe_x2"]
    print({k: g.get(k) for k in keys})
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
