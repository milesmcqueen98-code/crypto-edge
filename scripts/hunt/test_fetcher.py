#!/usr/bin/env python3
"""Smoke test of common.TradeFetcher on a GitHub runner (prints counts only)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

f = common.TradeFetcher()
for pid, s, e in [("DOP-20DEC30-CDE", "2026-02-05 12:00", "2026-02-05 14:00"),
                  ("ETP-20DEC30-CDE", "2025-10-10 21:00", "2025-10-10 21:30"),
                  ("ETH-USD", "2025-10-10 21:15", "2025-10-10 21:17")]:
    t0 = time.time()
    d = f.window(pid, s, e)
    print(pid, s, e, "trades", len(d), "first", d.time.min() if len(d) else None, "last", d.time.max() if len(d) else None,
          "dupes", int(d.trade_id.duplicated().sum()), "secs", round(time.time() - t0, 1), "req", f.n_req)
    if len(d):
        print(d.head(3).to_string(), "\n", d.side.value_counts().to_dict())
