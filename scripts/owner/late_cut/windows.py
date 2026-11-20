#!/usr/bin/env python3
"""Late-cut replay (reports/owner/late_cut_prereg.md), the print windows to fetch.

Every candidate (reports/owner/late_cut/data/candidates_<base>.csv.gz, replay.py --job export) gets [t - 60 s,
t + 15 s), t the start of the candidate minute. Overlapping or touching windows of one product are merged (the rule of
scripts/owner/timing/windows.py), so every candidate lies inside exactly one merged window and no print is fetched
twice. Shards are balanced on the same cost model (1.7 s per window plus 0.37 ms per print; $874 of candle volume per
print, candle dollars = minute t-1's plus a quarter of minute t's).
Writes reports/owner/late_cut/prints/windows.csv and cands.csv.gz (base, coin, ts, window_id).
usage: python scripts/owner/late_cut/windows.py <n_shards>
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DATA = os.path.join(ROOT, "reports", "owner", "late_cut", "data")
OUT = os.path.join(ROOT, "reports", "owner", "late_cut", "prints")
BEFORE, AFTER = pd.Timedelta(seconds=60), pd.Timedelta(seconds=15)
USD_PER_PRINT, SEC_PER_WINDOW, SEC_PER_PRINT = 874.0, 1.7, 0.37e-3


def main(n_shards):
    parts = [pd.read_csv(os.path.join(DATA, f"candidates_{b}.csv.gz"), parse_dates=["ts"]) for b in ("main", "early")]
    S = pd.concat(parts, ignore_index=True).sort_values(["coin", "ts"]).reset_index(drop=True)
    assert not S.duplicated(["coin", "ts"]).any()
    S["est_usd"] = np.nan_to_num(S.vol_prev * S.close_prev) + 0.25 * np.nan_to_num(S.vol_t * S.close_t)
    wid = np.empty(len(S), np.int64)
    rows = []
    for coin, g in S.groupby("coin", sort=True):
        st, en = (g.ts - BEFORE).to_numpy(), (g.ts + AFTER).to_numpy()
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
    os.makedirs(OUT, exist_ok=True)
    W.to_csv(os.path.join(OUT, "windows.csv"), index=False, date_format="%Y-%m-%d %H:%M:%S")
    S[["base", "coin", "ts", "window_id"]].to_csv(os.path.join(OUT, "cands.csv.gz"), index=False,
                                                  date_format="%Y-%m-%d %H:%M:%S")
    print(f"{len(S)} candidates ({S.base.value_counts().to_dict()}), {len(W)} merged windows, est prints "
          f"{W.est_prints.sum() / 1e6:.2f} M; est seconds per shard ({n_shards}): max {load.max():.0f}, "
          f"min {load.min():.0f}")


if __name__ == "__main__":
    main(int(sys.argv[1]))
