#!/usr/bin/env python3
"""Live order timing study: one compact copy of the runners' derived rows for branch owner/timing.
The six running-minimum paths are replaced by their union cut to the prices that can matter (low_ms, low_px: every
path entry at or below max(L(q-1), L(q)) + one tick; every bid the evaluator rests is within half a tick of one of the
two levels and fills one tick below it). The first print at or after s at or below such a price is a record low from
s, so it is in the union, and no earlier union entry after s can be at or below it: every policy evaluates exactly as
on the full rows (evaluate.path_of rebuilds each path from the union).
usage: python scripts/owner/timing/compact.py <derived_dir> <out_dir>
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prints_derive as PDV  # noqa: E402


def main(src, out):
    rows = pd.read_csv(os.path.join(HERE, "..", "..", "..", "reports", "owner", "timing", "data", "rows.csv.gz"),
                       parse_dates=["q"])
    D = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(src, "derived_*.parquet")))],
                  ignore_index=True)
    D["q"] = pd.to_datetime(D.q)
    D = D.merge(rows[["coin", "q", "L_prev", "L", "tick"]], on=["coin", "q"], how="left", validate="1:1")
    cap = np.fmax(D.L_prev.to_numpy(), D.L.to_numpy()) + D.tick.to_numpy()
    lm, lp = [], []
    for i in range(len(D)):
        pts = set()
        for s in PDV.STARTS:
            for a, b in zip(D[f"rl_ms_{s}"].iat[i], D[f"rl_px_{s}"].iat[i]):
                if b <= cap[i]:
                    pts.add((float(a), float(b)))
        pts = sorted(pts)
        lm.append([a for a, _ in pts])
        lp.append([b for _, b in pts])
    D["low_ms"], D["low_px"] = lm, lp
    D = D.drop(columns=[f"rl_{x}_{s}" for x in ("ms", "px") for s in PDV.STARTS])
    D = D.drop(columns=["L_prev", "L", "tick"]).sort_values(["tag", "coin", "q"])
    os.makedirs(out, exist_ok=True)
    D.to_parquet(os.path.join(out, "derived_all.parquet"), index=False, compression="zstd")
    S = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(src, "status_*.csv")))], ignore_index=True)
    S.to_csv(os.path.join(out, "status_all.csv.gz"), index=False)
    print(len(D), "rows;", os.path.getsize(os.path.join(out, "derived_all.parquet")) / 1e6, "MB")


if __name__ == "__main__":
    main(*sys.argv[1:3])
