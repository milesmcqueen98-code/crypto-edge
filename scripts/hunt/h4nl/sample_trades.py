#!/usr/bin/env python3
"""Draw the trade-print sample (SPEC: a random 25% of candidate fill minutes) from the DEV candidates only.
Fixed seed; every k level filled in a sampled minute is checked on the same prints."""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DATA = os.path.join(ROOT, "data", "hunt", "h4nl")

C = pd.read_parquet(os.path.join(DATA, "cand_dev.parquet"), columns=["pid", "ts", "k", "lvl", "thr_usd"])
assert C.ts.max() < pd.Timestamp("2026-06-01")
L = pd.read_csv(os.path.join(DATA, "listings_dev.csv"))[["pid", "tick", "status"]]
u = C[["pid", "ts"]].drop_duplicates().sort_values(["ts", "pid"]).reset_index(drop=True)
rng = np.random.default_rng(20261107)
pick = u.iloc[np.sort(rng.choice(len(u), size=int(round(0.25 * len(u))), replace=False))]
S = C.merge(pick, on=["pid", "ts"]).merge(L, on="pid").sort_values(["ts", "pid", "k"])
S.to_csv(os.path.join(DATA, "trade_sample.csv"), index=False)
print(f"{len(pick)} of {len(u)} fill minutes sampled ({len(S)} levels); delisted products {int((S.status == 'delisted').sum())}")
