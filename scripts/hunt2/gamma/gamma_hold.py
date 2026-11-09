#!/usr/bin/env python3
"""Edge hunt 2, GAMMA: the single HOLD read (run only AFTER the freeze commit of reports/hunt2/gamma/frozen.json).

The frozen variant (signal column, threshold number) is applied unchanged: skipped hours are those whose hourly
signal is below the frozen threshold, from the DEV file for the sel era (exactly the logged DEV trial) and from
the DEV + HOLD files for chk and early (reports/hunt2/gamma/derived/gamma_hourly_hold.parquet, copied unchanged from
the pre-freeze derive run's artifact by scripts/hunt2/gamma/copy_hold.py; the DEV file only matters for any sim
warm-up minutes before an era's first day). pathA.hold_read runs X2/X1/S on every era at $250K and writes
daily.parquet (x2, x1, s) and gates.json (h2gates.path_a). Skip counts per era are added to gates.json.

usage: python scripts/hunt2/gamma/gamma_hold.py
"""
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
    m_by_era, info = {}, {}
    for era, h in hrs.items():
        m, n_min = GM.mult(era, h)
        m_by_era[era] = m
        n_skip, n_par = GM.n_skipped(era, h)
        info[era] = dict(skip_minutes=n_min, parents=n_par, parents_skipped=n_skip,
                         frac_parents=n_skip / n_par if n_par else None)
    for era, (lo, hi) in (("chk", ("2026-04-01", "2026-11-06")), ("early", ("2022-01-01", "2024-01-01"))):
        s = H_hold.loc[(H_hold.index >= lo) & (H_hold.index < hi), col]
        info[era].update(hours=len(s), frac_hours_skipped=float((s < thr).mean()))
    g = GM.pathA.hold_read("gamma", None, GM.OUT, m_by_era=m_by_era)
    g["skips"] = info
    g["frozen_variant"] = fz["variant"]
    json.dump(g, open(os.path.join(GM.OUT, "gates.json"), "w"), indent=1, default=str)
    keys = ["A1", "A2", "A3", "A4", "pass", "hold_t_x2", "hold_mean_bp_x2", "hold_mean_bp_x1", "chk_mean_bp_x2",
            "early_mean_bp_x2", "chk_t_x2", "early_t_x2", "dev_t_x2", "years_x2", "dsr", "hold_dsharpe_x2"]
    print({k: g.get(k) for k in keys})
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
