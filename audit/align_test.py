#!/usr/bin/env python3
"""Audit E2: are spot and futures 1-minute candles on the same clock (ts = minute start for both)?
Cross-correlation of 1-minute close-to-close log returns at lags -2..+2 (futures shifted vs spot).
Also: does the futures close at t track the spot close at t (level), or at t-1 / t+1?"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import wick_sim as ws  # noqa: E402

for c in ["BTC", "ETH", "SOL", "XRP", "DOGE", "PEPE"]:
    idx, D = ws.load_ohlc(coins=[c], start="2025-12-15", end="2026-11-06")
    _, F = ws.load_ohlc(src="cfm", coins=[c], start="2025-12-15", end="2026-11-06")
    s = np.log(D[c]["close"])
    f = np.log(F[c]["close"])
    rs = np.diff(s, prepend=np.nan)
    rf = np.diff(f, prepend=np.nan)
    out = {}
    for lag in (-2, -1, 0, 1, 2):
        a = rs
        b = ws.shift(rf, lag)          # b[t] = rf[t-lag]
        m = np.isfinite(a) & np.isfinite(b)
        out[lag] = np.corrcoef(a[m], b[m])[0, 1]
    # level tracking: |log f[t] - log s[t+lag]| median (basis noise), smaller = better aligned
    lv = {}
    for lag in (-1, 0, 1):
        b = ws.shift(s, -lag)          # s[t+lag]
        m = np.isfinite(f) & np.isfinite(b)
        d = f[m] - b[m]
        d = d - np.median(d)
        lv[lag] = np.median(np.abs(d)) * 1e4
    print(f"{c}: corr(spot ret[t], fut ret[t-lag]) {{lag: corr}} = { {k: round(v, 3) for k, v in out.items()} };"
          f" median |fut[t]-spot[t+lag]| bp = { {k: round(v, 2) for k, v in lv.items()} }")
