#!/usr/bin/env python3
"""Red team h1pb (Actions): re-fetch raw perp prints [fill - 10 min, max(close, fill + 62 min) + 2 min] and spot prints
[fill - 3 min, fill + 3 min] for an audit sample of the builder's frozen trades (25 random DEV, 25 random HOLD, the 15
largest and 10 smallest net P&L), and commit them compactly for a print-level audit.
Writes reports/hunt/h1pb/redteam/audit_{sample.csv, perp.parquet, spot.parquet}."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h1pb", "redteam")


def sample(T):
    hold0 = pd.Timestamp("2026-06-01").value
    rng = np.random.default_rng(20261107)
    dev_i = T.index[T.t_fill < hold0]
    hold_i = T.index[T.t_fill >= hold0]
    pick = list(rng.choice(dev_i, 25, replace=False)) + list(rng.choice(hold_i, 25, replace=False))
    top = list(T.net.nlargest(15).index)
    worst = list(T.net.nsmallest(10).index)
    S = pd.DataFrame({"i": pick + top + worst, "why": ["rand_dev"] * 25 + ["rand_hold"] * 25 + ["top15"] * 15 + ["worst10"] * 10})
    return S.drop_duplicates("i").reset_index(drop=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    T = pd.read_parquet(os.path.join(ROOT, "reports", "hunt", "h1pb", "trades_frozen.parquet"))
    S = sample(T)
    S = S.join(T[["coin", "t_fill", "t_close"]], on="i")
    S.to_csv(os.path.join(OUT, "audit_sample.csv"), index=False)
    f = common.TradeFetcher(8.0)
    P, SP = [], []
    for r in S.itertuples():
        pid = common.PERP[r.coin][0]
        a = pd.Timestamp(r.t_fill).floor("s") - pd.Timedelta(minutes=10)
        b = max(pd.Timestamp(r.t_close), pd.Timestamp(r.t_fill) + pd.Timedelta(minutes=62)).ceil("s") + pd.Timedelta(minutes=2)
        d = f.window(pid, a, b)
        d["coin"], d["i"] = r.coin, r.i
        P.append(d)
        a2 = pd.Timestamp(r.t_fill).floor("s") - pd.Timedelta(minutes=3)
        d2 = f.window(f"{r.coin}-USD", a2, a2 + pd.Timedelta(minutes=6))
        d2["coin"], d2["i"] = r.coin, r.i
        SP.append(d2)
        print(r.i, r.coin, len(d), len(d2), f.n_req, flush=True)
    P = pd.concat(P, ignore_index=True)
    SP = pd.concat(SP, ignore_index=True)
    for X in (P, SP):
        X["time"] = X["time"].astype("datetime64[ns]")
    P.to_parquet(os.path.join(OUT, "audit_perp.parquet"), index=False, compression="zstd")
    SP.to_parquet(os.path.join(OUT, "audit_spot.parquet"), index=False, compression="zstd")
    print("perp prints", len(P), "spot prints", len(SP), "requests", f.n_req)


if __name__ == "__main__":
    main()
