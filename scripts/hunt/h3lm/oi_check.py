#!/usr/bin/env python3
"""H3 (LM): the SPEC's descriptive Binance open-interest cross-check (research only, never a model input).

Question: when the price trades through an estimated liquidation cluster (a density bid's cluster bucket is crossed:
the bid filled, or the cluster was consumed without filling us), does Binance USD-M open interest fall more in that
hour than when the price falls by a similar amount through a depth-matched random control bucket? A forced-selling
cluster should show up as an OI drop (positions closed), not just a price drop.

Uses DEV hours only (reports/hunt/h3lm/dev/dev_unit_cross.parquet) and data/alt/binance/metrics_<COIN>.parquet
(hourly OI). Prints a table; writes reports/hunt/h3lm/dev/oi_check.json.

  python scripts/hunt/h3lm/oi_check.py CFG
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
import common  # noqa: E402

DEV = os.path.join(ROOT, "reports", "hunt", "h3lm", "dev")
HOLD0 = pd.Timestamp("2026-06-01")


def oi(coin):
    p = os.path.join(common.DATA, "alt", "binance", f"metrics_{coin}.parquet")
    m = pd.read_parquet(p).drop_duplicates("ts").set_index("ts").sort_index()
    m = m[m.index < HOLD0]
    return m["sum_open_interest"]


def main(cfg):
    U = pd.read_parquet(os.path.join(DEV, "dev_unit_cross.parquet"))
    U = U[(U.cfg == cfg) & (U.ts < HOLD0)]
    rows = []
    for coin, g in U.groupby("coin"):
        s = oi(coin)
        # OI change over the bid's hour: value at the hour's end relative to the start (hourly records at :00)
        o0 = s.reindex(g.ts).to_numpy()
        o1 = s.reindex(g.ts + pd.Timedelta(hours=1)).to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            ch = (o1 / o0 - 1) * 1e4
        h = g.assign(oi_ch_bp=ch)
        rows.append(h)
    X = pd.concat(rows, ignore_index=True).dropna(subset=["oi_ch_bp", "hr_ret_bp"])
    out = {}
    for arm in ("dens", "ctrl"):
        a = X[X.arm == arm]
        out[arm] = dict(n=int(len(a)), oi_ch_bp_median=float(a.oi_ch_bp.median()), oi_ch_bp_mean=float(a.oi_ch_bp.mean()),
                        hr_ret_bp_median=float(a.hr_ret_bp.median()),
                        oi_per_100bp_drop=float(np.polyfit(-a.hr_ret_bp.clip(upper=0), a.oi_ch_bp, 1)[0] * 100)
                        if len(a) > 5 else None)
    # matched comparison: OI change minus what the hour's price move predicts (pooled fit on both arms)
    if len(X) > 10:
        b = np.polyfit(X.hr_ret_bp, X.oi_ch_bp, 1)
        X["oi_resid"] = X.oi_ch_bp - np.polyval(b, X.hr_ret_bp)
        d, c = X[X.arm == "dens"].oi_resid, X[X.arm == "ctrl"].oi_resid
        se = math.sqrt(d.var() / len(d) + c.var() / len(c)) if len(d) > 1 and len(c) > 1 else float("nan")
        out["resid_diff_bp"] = float(d.mean() - c.mean())
        out["resid_diff_t"] = float((d.mean() - c.mean()) / se) if se == se and se > 0 else None
    out["cfg"] = cfg
    out["note"] = ("Hours where the price crossed the estimated cluster (density arm) vs crossed a depth-matched random "
                   "bucket (control). OI = Binance USD-M sum_open_interest (coins), hourly; research context only.")
    print(json.dumps(out, indent=1))
    json.dump(out, open(os.path.join(DEV, "oi_check.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
