#!/usr/bin/env python3
"""Rows (minute index on each coin's grid) whose fair-value inputs (bbar, sigma) differ between the first DEV fetch's
statistics (levels v1) and the corrected v2, for the majors (BTC, ETH, SOL, XRP), whose first-fetch entries are kept on
all other rows. DEV grid only (end 2026-06-01). Writes reports/hunt/h1pb/delta_rows.parquet."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import levels as LV  # noqa: E402

HOLD0 = pd.Timestamp("2026-06-01")
MAJORS = ("BTC", "ETH", "SOL", "XRP")
out = []
for c in MAJORS:
    s1, s2 = LV.stats(c, end=HOLD0, version=1), LV.stats(c, end=HOLD0, version=2)
    a, b = np.c_[s1["bbar"], s1["sig"]], np.c_[s2["bbar"], s2["sig"]]
    same = ((np.isnan(a) & np.isnan(b)) | (np.abs(a - b) <= 1e-9 * np.abs(a))).all(axis=1)   # float noise ~1e-12 ignored
    rows = np.nonzero(~same)[0].astype(np.int32)
    out.append(pd.DataFrame({"coin": c, "row": rows}))
    print(c, len(rows), "rows", str(s1["idx"][0]))
D = pd.concat(out, ignore_index=True)
D.to_parquet(os.path.join(LV.common.ROOT if hasattr(LV.common, "ROOT") else ".", "reports", "hunt", "h1pb", "delta_rows.parquet"), index=False)
