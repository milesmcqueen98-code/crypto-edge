#!/usr/bin/env python3
"""H10 (XQ): does common.TradeFetcher (Advanced public trades) serve old and delisted secondary books? Also tests the
Exchange /trades endpoint and 1-minute candles of a delisted pair. Prints counts only (no statistics)."""
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import common  # noqa: E402
from cbx import Candles  # noqa: E402

f = common.TradeFetcher()
for pid, s, e in [("BTC-USDT", "2022-05-12 06:00", "2022-05-12 06:05"), ("ETH-BTC", "2022-06-13 03:00", "2022-06-13 03:05"),
                  ("UST-USDT", "2022-05-11 12:00", "2022-05-11 12:05"), ("GALA-USDT", "2022-11-09 12:00", "2022-11-09 13:00"),
                  ("WBTC-BTC", "2023-03-11 12:00", "2023-03-11 14:00"), ("USDT-USD", "2022-05-12 06:00", "2022-05-12 06:05"),
                  ("SOL-USDT", "2025-10-10 21:10", "2025-10-10 21:20"), ("ETH-BTC", "2025-10-10 21:10", "2025-10-10 21:20"),
                  ("LTC-BTC", "2023-08-17 21:00", "2023-08-17 22:00"), ("ICP-USDT", "2025-03-01 12:00", "2025-03-01 14:00"),
                  ("BTC-USD", "2022-05-12 06:00", "2022-05-12 06:01")]:
    t0 = time.time()
    try:
        d = f.window(pid, s, e)
        print(pid, s, e, "trades", len(d), "first", d.time.min() if len(d) else None, "last",
              d.time.max() if len(d) else None, "sides", d.side.value_counts().to_dict() if len(d) else {},
              "secs", round(time.time() - t0, 1), flush=True)
    except Exception as err:  # noqa: BLE001
        print(pid, s, e, "ERROR", type(err).__name__, str(err)[:200], flush=True)
S = requests.Session()
for pid in ("GALA-USDT", "ETH-BTC"):
    r = S.get(f"https://api.exchange.coinbase.com/products/{pid}/trades", params={"limit": 5}, timeout=30)
    print("exchange trades", pid, r.status_code, r.text[:300], r.headers.get("cb-after"), flush=True)
C = Candles()
for pid, s, e in [("GALA-USDT", "2022-11-09", "2022-11-10"), ("UST-USDT", "2022-05-10", "2022-05-11"),
                  ("ETH-BTC", "2022-01-01", "2022-01-02")]:
    d = C.range(pid, s, e, 60)
    print("candles", pid, s, len(d), d.ts.min() if len(d) else None, d.ts.max() if len(d) else None, flush=True)
