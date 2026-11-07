#!/usr/bin/env python3
"""H10 (XQ): prefetch 1-minute Exchange candles of a USD leg used by many pairs (USDT-USD), part i of n of its
needed date range (both scored eras incl. warm-up; raw data only, no statistics). Writes
data/hunt/h10xq/legs/<PRODUCT>__<i>.parquet.   usage: python scripts/hunt/h10xq/legs.py USDT-USD <i> <n>"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
from cbx import Candles  # noqa: E402

RANGES = (("2021-12-27", "2024-01-02"), ("2024-12-27", "2026-11-07"))


def main(prod, i, n):
    days = [d for a, b in RANGES for d in pd.date_range(a, b, freq="D", inclusive="left")]
    mine = days[i::n] if False else days[len(days) * i // n: len(days) * (i + 1) // n]
    C = Candles()
    parts, s = [], mine[0]
    for k, d in enumerate(mine):
        nxt = mine[k + 1] if k + 1 < len(mine) else None
        if nxt is None or (nxt - d).days > 1:
            parts.append(C.range(prod, s, d + pd.Timedelta(days=1), 60))
            s = nxt
    D = pd.concat(parts, ignore_index=True).drop_duplicates("ts").sort_values("ts")
    out = os.path.join(ROOT, "data", "hunt", "h10xq", "legs")
    os.makedirs(out, exist_ok=True)
    D.to_parquet(os.path.join(out, f"{prod}__{i}.parquet"), index=False, compression="zstd")
    print(prod, i, n, len(D), D.ts.min(), D.ts.max(), "requests", C.n_req, "errors", C.n_err)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
