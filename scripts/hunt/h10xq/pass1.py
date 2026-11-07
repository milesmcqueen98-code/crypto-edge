#!/usr/bin/env python3
"""H10 (XQ): print-request list (no P&L is computed or printed; fill counts only).
Sequences each configuration (sim.run, $30K, theta 0.5, candles + any print results already fetched) and requests
prints for (i) a seeded random sample of N fills per configuration and (ii) the TOP fills by dislocation depth
(lvl vs F) per configuration. Configurations: the 12 core trials (k 3/4/6 x exit a/b x quote set, H 60) and, so that a
second fetch round is not needed after the core grid is scored, their H = 30 and cascade versions (data only).
Writes data/hunt/h10xq/prints/req_<tag>.parquet and data/hunt/h10xq/prints/fills_<tag>.csv (counts).
usage: python scripts/hunt/h10xq/pass1.py <tag> <mode dev|hold> <N> <TOP> [k:exit:qset:H:cascade,...]"""
import os
import sys
import time
import zlib

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402


def grid(spec=None):
    if spec:
        out = []
        for g in spec.split(","):
            k, ex, q, H, c = g.split(":")
            out.append((float(k), ex, q, int(H), c == "1"))
        return out
    core = [(k, ex, q, 60, False) for q in sim.QSETS for ex in ("a", "b") for k in (3.0, 4.0, 6.0)]
    return core + [(k, ex, q, 30, False) for k, ex, q, _, _ in core if ex == "a"] + \
        [(k, ex, q, 60, True) for k, ex, q, _, _ in core]


def main(tag, mode, N, TOP, spec=None):
    P = sim.load_prints()
    req, cnt, t0 = [], [], time.time()
    cache = {}
    for k, ex, q, H, casc in grid(spec):
        if (mode, q, k, H) not in cache:
            cache.clear()
            cache[(mode, q, k, H)] = sim.load_events(mode, q, k, H)
        E = cache[(mode, q, k, H)]
        T = sim.run(E, q, 30000.0, 0.5, ex, casc, P)
        F = T[T.src == "candle"] if len(T) else T
        cnt.append(dict(k=k, exit=ex, qset=q, H=H, cascade=casc, fills=int((T.fill > 0).sum()) if len(T) else 0,
                        candle_only=len(F), print_rows=int(T.src.str.startswith("print").sum()) if len(T) else 0))
        print(cnt[-1], f"{time.time() - t0:.0f}s", flush=True)
        if not len(F):
            continue
        rng = np.random.default_rng(zlib.crc32(f"{k}|{ex}|{q}|{H}|{casc}".encode()))
        pick = set(rng.choice(len(F), size=min(N, len(F)), replace=False)) if N > 0 else set()
        pick |= set(np.argsort(F.disloc.to_numpy())[:TOP])
        S = F.iloc[sorted(pick)][["pair", "ts", "k"]]
        m = S.merge(E[["pair", "ts", "lvl", "tick", "tp", "tp_ts"]], on=["pair", "ts"])
        m["hedge"] = ex == "b"
        req.append(m)
    R = pd.concat(req, ignore_index=True)
    R = R.groupby(["pair", "ts", "k"], as_index=False).agg(lvl=("lvl", "first"), tick=("tick", "first"),
                                                             tp=("tp", "first"), tp_ts=("tp_ts", "first"),
                                                             hedge=("hedge", "max"))
    os.makedirs(os.path.join(sim.DATA, "prints"), exist_ok=True)
    R.to_parquet(os.path.join(sim.DATA, "prints", f"req_{tag}.parquet"), index=False)
    pd.DataFrame(cnt).to_csv(os.path.join(sim.DATA, "prints", f"fills_{tag}.csv"), index=False)
    print("requests", len(R), "windows", len(R[["pair", "ts"]].drop_duplicates()), "pairs", R.pair.nunique(),
          "hedge rows", int(R.hedge.sum()))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] if len(sys.argv) > 5 else None)
