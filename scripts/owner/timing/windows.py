#!/usr/bin/env python3
"""Live order timing study (reports/owner/timing_prereg.md), step 2 input: the print windows to fetch.

Every studied (coin, q) of both tags (reports/owner/timing/data/studied_<tag>.csv.gz, export.py) gets [q, q + 70 s);
overlapping or touching windows of one product are merged (scripts/signal_lab/prints_windows.py's rule), so every
studied minute lies inside exactly one merged window and no print is fetched twice. Shards are balanced on the same
cost model as signal lab 2 (1.7 s per window plus 0.37 ms per print; $874 of candle volume per print).
Writes reports/owner/timing/data/windows.csv and rows.csv.gz (tag, coin, q, L_prev, L, tick, window_id).
usage: python scripts/owner/timing/windows.py <n_shards>
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "owner", "timing", "data")
WIN = pd.Timedelta(seconds=70)
USD_PER_PRINT, SEC_PER_WINDOW, SEC_PER_PRINT = 874.0, 1.7, 0.37e-3


def main(n_shards):
    parts = []
    for tag in ("main", "early"):
        s = pd.read_csv(os.path.join(OUT, f"studied_{tag}.csv.gz"), parse_dates=["q"])
        s.insert(0, "tag", tag)
        parts.append(s)
    S = pd.concat(parts, ignore_index=True).sort_values(["coin", "q"]).reset_index(drop=True)
    assert not S.duplicated(["coin", "q"]).any()
    wid = np.empty(len(S), np.int64)
    rows = []
    for coin, g in S.groupby("coin", sort=True):
        st, en, usd = g.q.to_numpy(), (g.q + WIN).to_numpy(), g.est_usd.to_numpy()
        cs, ce, members = st[0], en[0], [g.index[0]]
        for i in range(1, len(g)):
            if st[i] <= ce:
                ce = max(ce, en[i])
                members.append(g.index[i])
            else:
                rows.append((f"{coin}-USD", cs, ce, members))
                cs, ce, members = st[i], en[i], [g.index[i]]
        rows.append((f"{coin}-USD", cs, ce, members))
    W = []
    for k, (prod, cs, ce, mem) in enumerate(rows):
        wid[mem] = k
        W.append(dict(window_id=k, product=prod, start=pd.Timestamp(cs), end=pd.Timestamp(ce), n_rows=len(mem),
                      est_prints=int(round(S.loc[mem, "est_usd"].sum() / USD_PER_PRINT))))
    W = pd.DataFrame(W)
    cost = SEC_PER_WINDOW + SEC_PER_PRINT * W.est_prints.to_numpy()
    load = np.zeros(n_shards)
    sh = np.empty(len(W), np.int64)
    for i in np.argsort(-cost, kind="stable"):
        j = int(np.argmin(load))
        sh[i] = j
        load[j] += cost[i]
    W["shard"] = sh
    S["window_id"] = wid
    W.to_csv(os.path.join(OUT, "windows.csv"), index=False, date_format="%Y-%m-%d %H:%M:%S")
    S[["tag", "coin", "q", "L_prev", "L", "tick", "window_id"]].to_csv(
        os.path.join(OUT, "rows.csv.gz"), index=False, float_format="%.12g", date_format="%Y-%m-%d %H:%M:%S")
    print(f"{len(S)} studied minutes, {len(W)} merged windows, est prints {W.est_prints.sum() / 1e6:.2f} M; "
          f"est seconds per shard ({n_shards}): max {load.max():.0f}, min {load.min():.0f}")


if __name__ == "__main__":
    main(int(sys.argv[1]))
