#!/usr/bin/env python3
"""Wick v4 addendum C1, step 1 (local): per-event inputs for the fill-capacity check on trade data.

For each research event with a trade window (reports/wick_v4/events_research.csv: the 4-sigma parent fills and the
same-minute 6/8-sigma fills), export what the simulator used:
  - the bid level, the coin's ADV (for the $1M-rule tranche size) and the simulator's full entry capacity in_spot;
  - V-hat on the two minutes the trade window covers (the fill minute and the next one), from Coinbase's minute candles
    with the simulator's own rule (sim.below_usd: each minute's volume spread evenly over its high-low range, counted
    while the minute's low is below the level).
Only derived numbers are written (reports/wick_v4/capacity_events.csv); candles and trades stay out of the repo.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))


def vhat_minute(lo, hi, v, level):
    if not np.isfinite(lo) or lo >= level or not np.isfinite(v):
        return 0.0
    rng = hi - lo
    frac = 1.0 if rng <= 0 else min(1.0, (level - lo) / rng)
    return v * frac * 0.5 * (level + lo)


def main():
    P = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", "pre_v4_main.pkl"))
    E = pd.read_csv(os.path.join(ROOT, "reports", "wick_v4", "events_research.csv"), parse_dates=["ts"])
    M = E[["ts", "coin", "k"]].merge(P[P.filled], on=["ts", "coin", "k"], how="left")
    assert M.lvl.notna().all()
    rows = []
    for c, g in M.groupby("coin"):
        d = pd.read_parquet(os.path.join(ROOT, "data", "minute", f"{c}.parquet")).drop_duplicates("ts").set_index("ts")
        d = d[d.volume > 0]
        for r in g.itertuples():
            t0 = r.ts + pd.Timedelta(minutes=int(r.f_off))
            v = []
            for j in (0, 1):
                t = t0 + pd.Timedelta(minutes=j)
                if t in d.index:
                    x = d.loc[t]
                    v.append((float(x.low), float(x.high), float(x.volume)))
                else:
                    v.append((np.nan, np.nan, 0.0))
            m0 = vhat_minute(*v[0], r.lvl)
            m1 = vhat_minute(*v[1], r.lvl) if (np.isfinite(v[1][0]) and v[1][0] < r.lvl and m0 > 0) else 0.0
            rows.append(dict(ts=r.ts, coin=c, k=r.k, bot=bool(r.bot), lvl=r.lvl, adv=r.adv, in_spot=r.in_spot,
                             scan_off=r.scan_off, low_m0=v[0][0], low_m1=v[1][0], vhat_m0=m0, vhat_m1=m1))
    out = pd.DataFrame(rows).sort_values(["ts", "coin", "k"])
    out.to_csv(os.path.join(ROOT, "reports", "wick_v4", "capacity_events.csv"), index=False)
    par = out[out.k == 4]
    print(f"{len(out)} rows ({len(par)} parents); V-hat on the 2 covered minutes / full simulator capacity: "
          f"{(par.vhat_m0 + par.vhat_m1).sum() / par.in_spot.sum():.3f} (dollar-weighted), "
          f"median {((par.vhat_m0 + par.vhat_m1) / par.in_spot).median():.3f}")


if __name__ == "__main__":
    main()
