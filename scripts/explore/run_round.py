#!/usr/bin/env python3
"""Explore v1: run one round's variants on the selection era only (reports/explore/prereg.md).

  python scripts/explore/run_round.py <round>

Reads reports/explore/round<round>_variants.json. For each variant, on Jan 2025 - Mar 2026 only:
  - blended (live-like), minute and instant books at $250K;
  - the blended book at $1M.
Appends one row per variant to reports/explore/variants.csv. Writes the blended $250K daily returns to
reports/explore/daily_sel_r<round>.parquet (one column per variant) for the overfitting diagnostics.
"""
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import xsim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "explore")
ERA = "selection"


def one(v):
    s = v["spec"]
    b250, m250, i250, im, ii = xsim.blended(s, ERA, 250e3)
    b1m, m1m, i1m, im1, _ = xsim.blended(s, ERA, 1e6)
    st_b, st_m, st_i, st_1 = (xsim.stats(x, ERA) for x in (b250, m250, i250, b1m))
    row = dict(id=v["id"], round=v["round"], origin=v["origin"], spec=json.dumps(s, default=str),
               design=json.dumps(v.get("design", {}), default=str),
               sharpe_b250=st_b["sharpe"], sharpe_m250=st_m["sharpe"], sharpe_i250=st_i["sharpe"], sharpe_b1m=st_1["sharpe"],
               ret_b250=st_b["ret_yr"], ret_b1m=st_1["ret_yr"], maxdd_b250=st_b["maxdd"], worst_b250=st_b["worst"],
               exposure_m250=im["exposure"], fills_m250=im["fills"], fill_usd_m250=im["fill_usd"], signals=im["signals"],
               maker_bp_m250=im["maker_bp"], exposure_m1m=im1["exposure"])
    return row, b250.rename(v["id"])


def main(rnd):
    V = json.load(open(os.path.join(OUT, f"round{rnd}_variants.json")))
    with Pool(2) as pool:
        res = pool.map(one, V, chunksize=8)
    rows = pd.DataFrame([r for r, _ in res])
    daily = pd.concat([d for _, d in res], axis=1)
    path = os.path.join(OUT, "variants.csv")
    if os.path.exists(path):
        old = pd.read_csv(path)
        old = old[old["round"] != rnd]
        rows = pd.concat([old, rows], ignore_index=True)
    rows.to_csv(path, index=False)
    daily.to_parquet(os.path.join(OUT, f"daily_sel_r{rnd}.parquet"))
    r = rows[rows["round"] == rnd]
    base = rows[rows.id == "base"].iloc[0]
    print(f"round {rnd}: {len(r)} variants; incumbent blended Sharpe at $250K {base.sharpe_b250:.3f}")
    print(r.sort_values("sharpe_b250", ascending=False)[["id", "sharpe_b250", "sharpe_m250", "sharpe_b1m", "ret_b250",
                                                         "maxdd_b250"]].head(15).round(3).to_string(index=False))


if __name__ == "__main__":
    main(int(sys.argv[1]))
