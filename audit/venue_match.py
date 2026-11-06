#!/usr/bin/env python3
"""Audit E4c: same coin, same fill minute on both venues -> what does moving the trade from spot to futures do?"""
import os
import pickle

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "audit", "fut_trades.pkl"), "rb") as fh:
    TR = pickle.load(fh)
for ai in (False, True):
    f = TR["base (reproduces wick_futures)", ai]
    s = TR["spot, same windows (reproduces)", ai]
    f, s = f[f.ts >= "2025-12-13"], s[s.ts >= "2025-12-13"]
    m = f.merge(s, on=["coin", "ts"], suffixes=("_fut", "_spot"))
    d = m.net_bp_fut - m.net_bp_spot
    only_f = f.merge(s[["coin", "ts"]], on=["coin", "ts"], how="left", indicator=True)
    only_f = only_f[only_f._merge == "left_only"]
    only_s = s.merge(f[["coin", "ts"]], on=["coin", "ts"], how="left", indicator=True)
    only_s = only_s[only_s._merge == "left_only"]
    print(f"{'rule + AI' if ai else 'rule only'}: matched fills {len(m)}: spot {m.net_bp_spot.mean():.1f} bp, futures "
          f"{m.net_bp_fut.mean():.1f} bp, diff {d.mean():.1f} +- {d.std() / np.sqrt(len(d)):.1f} bp (se); "
          f"futures-only-book fills {len(only_f)} at {only_f.net_bp.mean():.1f} bp; spot-only-book fills {len(only_s)} at "
          f"{only_s.net_bp.mean():.1f} bp")
