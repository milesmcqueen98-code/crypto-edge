#!/usr/bin/env python3
"""H1 fetch planning (Actions): (1) does the public market-trades endpoint accept limit > 1000; (2) completeness of the
fixed fetcher (fetch.Fetcher) vs 1-minute candle volume on busy DEV hours. Counts only. Writes probe_limit.csv."""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402
import fetch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "hunt", "h1pb")


def main():
    rows = []
    f = fetch.Fetcher(8.0)
    s, e = int(pd.Timestamp("2026-02-05 15:00").timestamp()), int(pd.Timestamp("2026-02-05 15:30").timestamp())
    for pid in ("BTC-USD", "BIP-20DEC30-CDE"):
        for lim in (1000, 2000, 5000, 10000, 30000):
            r = f.S.get(f"{common.ADV}/{pid}/ticker", params={"limit": lim, "start": s, "end": e}, timeout=60)
            n = len(r.json().get("trades", [])) if r.status_code == 200 else -1
            rows.append(dict(test="limit", pid=pid, limit=lim, status=r.status_code, n=n))
            print(rows[-1], flush=True)
            time.sleep(0.3)
    for pid, coin, src, h in [("BIP-20DEC30-CDE", "BTC", "cfm", "2026-02-05 15:00"), ("BIP-20DEC30-CDE", "BTC", "cfm", "2025-11-21 14:00"),
                              ("ETP-20DEC30-CDE", "ETH", "cfm", "2026-02-05 15:00"), ("BTC-USD", "BTC", "minute", "2026-02-05 15:00"),
                              ("ETH-USD", "ETH", "minute", "2026-02-05 15:00")]:
        a, b = pd.Timestamp(h), pd.Timestamp(h) + pd.Timedelta(hours=1)
        f2 = fetch.Fetcher(8.0)
        t0 = time.time()
        d = f2.window(pid, a, b)
        C = pd.read_parquet(os.path.join(common.DATA, src, f"{coin}.parquet")).drop_duplicates("ts").set_index("ts").sort_index()
        cv = C.loc[(C.index >= a) & (C.index < b), "volume"]
        pv = d.groupby(d.time.dt.floor("min"))["size"].sum()
        j = pd.concat([cv.rename("c"), pv.rename("p")], axis=1).fillna(0.0)
        rows.append(dict(test="complete", pid=pid, hour=h, trades=len(d), requests=f2.n_req, lost_seconds=f2.lost_seconds,
                         secs=round(time.time() - t0, 1), candle_vol=float(cv.sum()), print_vol=float(pv.sum()),
                         minutes_match=int((np.abs(j.c - j.p) <= 1e-6 * np.maximum(1.0, j.c)).sum()), minutes=len(j),
                         dupes=int(d.trade_id.duplicated().sum())))
        print(rows[-1], flush=True)
    os.makedirs(OUT, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "probe_limit.csv"), index=False)


if __name__ == "__main__":
    main()
