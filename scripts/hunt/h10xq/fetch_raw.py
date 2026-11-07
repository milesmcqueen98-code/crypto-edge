#!/usr/bin/env python3
"""H10 (XQ): raw 1-minute candles (download only, no statistics) for every product needed on the given days of the
universe: the secondary pairs ranked in data/hunt/h10xq/universe.parquet and their USD legs not on disk, with 4
warm-up days. Used for HOLD days (2026-06-01 .. 2026-11-05) so that the post-freeze run reads disk only.
Writes data/hunt/h10xq/raw/<PRODUCT>__<shard>.parquet.
usage: python scripts/hunt/h10xq/fetch_raw.py <first day> <last day> <shard> <nshards>"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
from cbx import Candles  # noqa: E402

DATA = os.path.join(ROOT, "data", "hunt", "h10xq")
LOCAL_MAIN = ("2024-01-01", "2026-11-06")


def main(d0, d1, shard, nsh):
    U = pd.read_parquet(os.path.join(DATA, "universe.parquet"))
    U = U[(U.day >= d0) & (U.day <= d1)]
    a, b = pd.Timestamp(d0) - pd.Timedelta(days=4), pd.Timestamp(d1) + pd.Timedelta(days=1)
    local = {f.split(".")[0] for f in os.listdir("/home/claude/crypto-edge/data/minute")} \
        if os.path.isdir("/home/claude/crypto-edge/data/minute") else \
        {f.split(".")[0] for f in os.listdir(os.path.join(ROOT, "data", "minute"))}
    prods = sorted(set(U.pair) | {p for p in set(U.base_usd) | set(U.quote_usd) if p[:-4] not in local})
    mine = prods[shard::nsh]
    print(f"shard {shard}/{nsh}: {len(mine)} of {len(prods)} products: {mine}", flush=True)
    C = Candles()
    os.makedirs(os.path.join(DATA, "raw"), exist_ok=True)
    for p in mine:
        d = C.range(p, a, b, 60)
        d = d[d.volume > 0]
        d.to_parquet(os.path.join(DATA, "raw", f"{p}__{shard}.parquet"), index=False, compression="zstd")
        print(p, len(d), "requests", C.n_req, "errors", C.n_err, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
