#!/usr/bin/env python3
"""H10 (XQ) step 2: daily candles of every secondary pair in reports/hunt/h10xq/pairs.csv and of every USD leg
(2021-12-01 .. 2026-11-07), to find each book's active days and volumes and to plan the 1-minute fetch.
Writes data/hunt/h10xq/daily.parquet.  usage: python scripts/hunt/h10xq/fetch_daily.py"""
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
from cbx import Candles  # noqa: E402

OUT = os.path.join(ROOT, "data", "hunt", "h10xq")


def main():
    P = pd.read_csv(os.path.join(ROOT, "reports", "hunt", "h10xq", "pairs.csv"))
    P = P[P.eligible]
    prods = list(P.id) + sorted(set(P.base_usd) | set(P.quote_usd))
    C = Candles()
    parts, t0 = [], time.time()
    for i, pid in enumerate(prods):
        d = C.range(pid, "2021-12-01", "2026-11-07", 86400)
        d["product"] = pid
        parts.append(d)
        if i % 25 == 0:
            print(i, pid, len(d), C.n_req, f"{time.time() - t0:.0f}s", flush=True)
    D = pd.concat(parts, ignore_index=True)
    os.makedirs(OUT, exist_ok=True)
    D.to_parquet(os.path.join(OUT, "daily.parquet"), index=False, compression="zstd")
    print("products", len(prods), "rows", len(D), "requests", C.n_req, "errors", C.n_err, f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
