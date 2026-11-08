#!/usr/bin/env python3
"""Cutoffs for the size_by_margin option (ladder v5, C2a): the 1/3 and 2/3 quantiles (numpy's default linear
interpolation) of the AI's margin (prediction minus the quarter's threshold) over every research parent fill before the
start of the quarter (reports/wick1m/trades_main.parquet, all rows), as in the backtest (scripts/ladder_v5/cand_sizing.py
on branch ladder/sizing). Fewer than 60 earlier fills: no cutoffs (x1.0).

  python bot/spot/margin_cutoffs.py                 the current quarter
  python bot/spot/margin_cutoffs.py 2027-01-01      the quarter that starts on that day

Paste the printed block into the config's size_by_margin. The trade list ends where the research data ends; refresh
the cutoffs each quarter only after the trade list has been rebuilt on newer data, otherwise keep the last ones.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIN_FILLS = 60


def cutoffs(day=None, path=os.path.join(ROOT, "reports", "wick1m", "trades_main.parquet")):
    q0 = pd.Timestamp(day or pd.Timestamp.now(tz="UTC").tz_localize(None)).to_period("Q").start_time
    t = pd.read_parquet(path, columns=["ts", "pred", "thr"])
    m = (t.pred - t.thr)[t.ts < q0].to_numpy(float)
    if len(m) < MIN_FILLS:
        return q0, len(m), None
    lo, hi = np.quantile(m, [1 / 3, 2 / 3])
    return q0, len(m), dict(lower=round(float(lo), 4), upper=round(float(hi), 4), mult=[0.5, 1.0, 1.5],
                            quarter=str(q0.to_period("Q")), fills=int(len(m)), last_fill=str(t.ts.max()))


if __name__ == "__main__":
    q0, n, rule = cutoffs(sys.argv[1] if len(sys.argv) > 1 else None)
    if rule is None:
        sys.exit(f"{n} research parent fills before {q0.date()}: fewer than {MIN_FILLS}, no cutoffs (x1.0)")
    print(json.dumps({"size_by_margin": rule}, indent=1))
