#!/usr/bin/env python3
"""Edge hunt 2: the incumbent's daily series on the frozen simulator, for every capital and cost setting the gates use.
Writes reports/hunt2/incumbent_daily.parquet, columns "<cost>|<theta>|<capital>|<era>" (daily P&L / capital).
usage: python scripts/hunt2/incumbent.py [cost:theta:capital ...]
"""
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frozen_sim as F  # noqa: E402

ROOT = F.ROOT
OUT = os.path.join(ROOT, "reports", "hunt2", "incumbent_daily.parquet")
DEFAULT = ["S:0.5:250000", "S:0.5:225000", "S:0.5:200000", "S:0.5:175000", "S:0.5:125000", "X2:0.5:250000",
           "X1:0.5:250000", "S:0.25:250000"]


def main(specs):
    cols = {}
    if os.path.exists(OUT):
        old = pd.read_parquet(OUT)
        cols = {c: old[c].dropna() for c in old.columns}
    t0 = time.time()
    for spec in specs:
        cost, theta, C = spec.split(":")
        theta, C = float(theta), float(C)
        for era in ("sel", "chk", "early"):
            key = f"{cost}|{theta}|{int(C)}|{era}"
            if key in cols:
                continue
            d = F.daily(era, theta, C, cost)
            st = F.fsim.stats(d, C, era)
            cols[key] = d
            print(f"{key}: {100 * st['ret_yr']:.2f}%/yr Sharpe {st['sharpe']:.3f} ({time.time() - t0:.0f}s)", flush=True)
            pd.DataFrame(cols).to_parquet(OUT)
            F._A.clear()


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
