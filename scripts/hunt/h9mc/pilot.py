#!/usr/bin/env python3
"""H9 (MC) pilot: calibrate request counts, print counts and print-size units for the 4 pm ET fetch.
Counts only (no side shares, no returns). DEV days only. Writes reports/hunt/h9mc/pilot.json."""
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

ET = "America/New_York"
OUT = os.path.join(common.ROOT, "reports", "hunt", "h9mc", "pilot.json")


def et_utc(day, hhmm):
    t = pd.Timestamp(f"{day} {hhmm}").tz_localize(ET).tz_convert("UTC").tz_localize(None)
    return t


f = common.TradeFetcher()
res = []
for coin in ["BTC", "ETH", "SOL", "DOGE", "AAVE"]:
    pid = common.PERP[coin][0]
    cand = common.load_perp(coin)
    for day in ["2025-10-15", "2026-03-11"]:
        for w0, w1 in [("13:30", "14:30"), ("15:30", "17:10")]:
            s, e = et_utc(day, w0), et_utc(day, w1)
            r0, t0 = f.n_req, time.time()
            d = f.window(pid, s, e)
            row = dict(coin=coin, day=day, win=f"{w0}-{w1}", prints=len(d), req=f.n_req - r0,
                       secs=round(time.time() - t0, 1))
            if len(d):
                row["sum_size"] = float(d["size"].sum())
                row["median_size"] = float(d["size"].median())
                row["sides"] = d.side.value_counts().to_dict()
                row["dupes"] = int(d.trade_id.duplicated().sum())
                row["first"], row["last"] = str(d.time.min()), str(d.time.max())
            if cand is not None:
                c = cand[(cand.index >= s) & (cand.index < e)]
                row["candle_vol_coin"] = float(c.volume.sum())
                row["candle_vol_contracts"] = float(c.volume.sum() / common.PERP[coin][1])
                row["candle_minutes"] = int(len(c))
            print(json.dumps(row, default=str), flush=True)
            res.append(row)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(res, open(OUT, "w"), indent=1, default=str)
print("total requests", f.n_req)
