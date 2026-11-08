#!/usr/bin/env python3
"""Red team 2 (ladder v5): the tranche exits to measure on prints: every (coin, live fill time) whose remainder is
sold at the 60-minute mark in any gate configuration or latency bound of the live incumbent (qdump.py tables).
Writes reports/ladder_v5/redteam2/events_exit.csv (event_id, coin, fill_t, era_tag, tick_model, tick_real)."""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import c3  # noqa: E402

rows = []
for f in sorted(glob.glob(os.path.join(c3.QD, "inc_*.parquet"))):
    cfg_era = os.path.basename(f)[4:].rsplit("_", 1)[0]
    era = cfg_era.rsplit("_", 1)[1]
    Q = pd.read_parquet(f, columns=["coin", "fill_t", "fill", "tp_fill"])
    Q = Q[(Q.fill - Q.tp_fill) > 0]
    rows.append(Q[["coin", "fill_t"]].assign(era_tag="early" if era == "early" else "main"))
E = pd.concat(rows).drop_duplicates().sort_values(["fill_t", "coin"]).reset_index(drop=True)
E["event_id"] = np.arange(len(E))
E["tick_model"] = E.coin.map(c3.TICK_MODEL)
E["tick_real"] = E.coin.map(c3.TICK_REAL)
W = pd.read_csv(os.path.join(c3.RT, "windows_exit.csv"), parse_dates=["start", "end"])
cov = []
for r in E.itertuples():
    w = W[(W["product"] == r.coin + "-USD") & (W.start <= r.fill_t + pd.Timedelta(minutes=55)) &
          (W.end >= r.fill_t + pd.Timedelta(minutes=82))]
    cov.append(len(w) > 0)
print(f"{len(E)} events ({E.era_tag.value_counts().to_dict()}), inside a fetched window: {np.mean(cov):.1%}")
E[["event_id", "coin", "fill_t", "era_tag", "tick_model", "tick_real"]].to_csv(
    os.path.join(c3.RT, "events_exit.csv"), index=False)
