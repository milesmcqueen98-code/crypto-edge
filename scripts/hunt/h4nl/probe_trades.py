#!/usr/bin/env python3
"""Does Coinbase serve spot trade prints for old windows and for delisted products? (counts and timing only)"""
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import common  # noqa: E402
import fetch  # noqa: E402

F = common.TradeFetcher()
# (product, window start, end): listed and delisted products, 2022..2025 windows (metadata only: counts)
for pid, s, e in [("APE-USD", "2022-03-17 12:00", "2022-03-17 12:10"), ("ETH-USD", "2022-06-01 12:00", "2022-06-01 12:02"),
                  ("RAI-USD", "2023-01-10 12:00", "2023-01-10 14:00"), ("DAR-USD", "2022-06-01 12:00", "2022-06-01 13:00"),
                  ("ENJ-USD", "2023-06-01 12:00", "2023-06-01 12:30"), ("SUI-USD", "2023-05-03 16:00", "2023-05-03 16:10")]:
    t0 = time.time()
    try:
        d = F.window(pid, s, e)
        n, lo, hi = len(d), (d.time.min() if len(d) else None), (d.time.max() if len(d) else None)
    except Exception as ex:  # noqa: BLE001
        n, lo, hi = f"ERR {type(ex).__name__} {str(ex)[:120]}", None, None
    print("ADV", pid, s, e, "n", n, lo, hi, "secs", round(time.time() - t0, 1), "req", F.n_req, flush=True)
    t0 = time.time()
    try:
        d2 = fetch.exch_trades_window(pid, s, e)
        n2 = None if d2 is None else len(d2)
        extra = (d2.time.min(), d2.time.max(), d2.side.value_counts().to_dict()) if d2 is not None and len(d2) else None
    except Exception as ex:  # noqa: BLE001
        n2, extra = f"ERR {type(ex).__name__} {str(ex)[:120]}", None
    print("EXCH", pid, "n", n2, extra, "secs", round(time.time() - t0, 1), "req", fetch.N_REQ[0], flush=True)
