#!/usr/bin/env python3
"""Live order timing study, part 2 (reports/owner/timing_prereg.md, deviation 3), on GitHub Actions: from the raw
prints of the first fetch (the shard artifacts, downloaded into art/), every print of each studied minute's
[q, q + 70 s) at or below the row's cut (max of the two minutes' 6-sigma levels + one tick). No request is made.
usage: python scripts/owner/timing/deep_runner.py <art_dir> <rows_deep.csv.gz> <out.parquet>
  out: tag, coin, q, n70, deep_ms (ms after q), deep_px (lists, ordered by time, trade_id)
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

WIN_MS = 70000.0


def main(art, rpath, out):
    R = pd.read_csv(rpath, parse_dates=["q"])
    fs = sorted(glob.glob(os.path.join(art, "**", "prints_*.parquet"), recursive=True))
    print(len(fs), "artifact files", flush=True)
    rows = []
    seen = set()
    for f in fs:
        P = pd.read_parquet(f)
        for wid, D in P.groupby("window_id"):
            wid = int(wid)
            if wid in seen:
                continue
            seen.add(wid)
            D = D.drop_duplicates("trade_id").sort_values(["time", "trade_id"])
            t = D.time.to_numpy().astype("datetime64[ns]").astype(np.int64)
            px = D.price.to_numpy(np.float64)
            for r in R[R.window_id == wid].itertuples():
                q = np.int64(pd.Timestamp(r.q).value)
                a = int(np.searchsorted(t, q, "left"))
                b = int(np.searchsorted(t, q + int(WIN_MS * 1e6), "left"))
                ms, p = (t[a:b] - q) / 1e6, px[a:b]
                k = p <= r.cut
                rows.append(dict(tag=r.tag, coin=r.coin, q=r.q, n70=int(b - a), deep_ms=ms[k].tolist(),
                                 deep_px=p[k].tolist()))
        print(f, len(rows), flush=True)
    O = pd.DataFrame(rows)
    miss = set(R.window_id) - seen
    print(f"rows {len(O)} of {len(R)}; windows missing {len(miss)}; deep prints {int(O.deep_px.map(len).sum())}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    O.to_parquet(out, index=False, compression="zstd")
    if miss:
        sys.exit(2)


if __name__ == "__main__":
    main(*sys.argv[1:4])
