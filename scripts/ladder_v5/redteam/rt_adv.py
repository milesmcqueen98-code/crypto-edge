#!/usr/bin/env python3
"""Red team: per-coin daily ADV table (trailing 30-day median daily USD volume, Coinbase spot + perp for main, spot
only for early, as of the previous day) for every coin and day, from scripts/wick1m/sim.py's daily_stats (the research
definition). Checked against the frozen dataset's adv on every trade row. Writes reports/ladder_v5/redteam/adv_<tag>.parquet
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v5"))
import fsim  # noqa: E402
import sim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "ladder_v5", "redteam")


def build(tag):
    P = fsim.load(tag)
    start, end, src = sim.PERIODS[tag]
    idx = pd.date_range(start, end, freq="min", inclusive="left")
    pm = sim.perp_mult()
    cols = {}
    for c in sorted(P.coin.unique()):
        V = {"spot": sim.load_venue(os.path.join(ROOT, "data", src, f"{c}.parquet"), idx)}
        if tag != "early" and c in pm:
            p = sim.load_venue(os.path.join(ROOT, "data", "cfm", f"{c}.parquet"), idx, pm[c])
            if p is not None:
                V["perp"] = p
        adv_cb, _, _ = sim.daily_stats(V, idx)
        cols[c] = adv_cb
        del V
    A = pd.DataFrame(cols)
    A.index.name = "day"
    # check against the frozen dataset
    day = P.ts.dt.floor("D")
    got = np.array([A.at[d, c] if d in A.index else np.nan for d, c in zip(day, P.coin)])
    ok = np.isfinite(got) & np.isfinite(P.adv.to_numpy())
    err = np.abs(got[ok] - P.adv.to_numpy()[ok]) / np.maximum(1.0, P.adv.to_numpy()[ok])
    nan_mismatch = int((np.isfinite(got) != np.isfinite(P.adv.to_numpy())).sum())
    print(f"{tag}: {ok.sum()} rows compared, max rel diff {err.max():.2e}, nan mismatches {nan_mismatch}")
    A.to_parquet(os.path.join(OUT, f"adv_{tag}.parquet"))
    return A


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for t in sys.argv[1:] or ("main", "early"):
        build(t)
