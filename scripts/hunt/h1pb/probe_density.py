#!/usr/bin/env python3
"""H1 fetch planning (runs on Actions): trade density of each perp on a few DEV hours, and a completeness check of
common.TradeFetcher paging (per-minute print volume vs the 1-minute candle volume, both in contracts).
DEV dates only. Prints counts only (no prices or P&L). Writes reports/hunt/h1pb/probe_density.csv."""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "hunt", "h1pb")
HOURS = ["2025-11-21 14:00", "2026-02-05 15:00", "2026-04-13 02:00"]   # a busy US day, a crash day, a quiet night


def main():
    f = common.TradeFetcher()
    rows = []
    t_all = time.time()
    for coin, (pid, cs, tick) in common.PERP.items():
        p = os.path.join(common.DATA, "cfm", f"{coin}.parquet")
        if not os.path.exists(p):
            continue
        C = pd.read_parquet(p).drop_duplicates("ts").set_index("ts").sort_index()
        for h in HOURS:
            s, e = pd.Timestamp(h), pd.Timestamp(h) + pd.Timedelta(hours=1)
            if C.index.min() > s:
                continue
            r0, t0 = f.n_req, time.time()
            d = f.window(pid, s, e)
            secs, nreq = time.time() - t0, f.n_req - r0
            cv = C.loc[(C.index >= s) & (C.index < e), "volume"]
            if len(d):
                pv = d.groupby(d.time.dt.floor("min"))["size"].sum()
            else:
                pv = pd.Series(dtype=float)
            j = pd.concat([cv.rename("candle"), pv.rename("prints")], axis=1).fillna(0.0)
            rows.append(dict(coin=coin, hour=h, trades=len(d), requests=nreq, secs=round(secs, 1),
                             candle_contracts=float(cv.sum()), print_contracts=float(pv.sum()),
                             minutes_candle=int((j.candle > 0).sum()), minutes_match=int((np.abs(j.candle - j.prints) < 1e-6).sum()),
                             minutes_any=len(j), max_trades_1s=int(d.groupby(d.time.dt.floor("s")).size().max()) if len(d) else 0,
                             dupes=int(d.trade_id.duplicated().sum()) if len(d) else 0,
                             contracts_per_trade=float(pv.sum() / max(1, len(d)))))
            print(rows[-1], flush=True)
    for coin in ("BTC", "ETH", "SOL", "XRP", "DOGE", "ZEC", "SUI", "NEAR"):
        C = common.load_minute(coin)
        for h in HOURS:
            s, e = pd.Timestamp(h), pd.Timestamp(h) + pd.Timedelta(hours=1)
            r0, t0 = f.n_req, time.time()
            d = f.window(f"{coin}-USD", s, e)
            secs, nreq = time.time() - t0, f.n_req - r0
            cv = C.loc[(C.index >= s) & (C.index < e), "volume"] if C is not None else pd.Series(dtype=float)
            pv = d.groupby(d.time.dt.floor("min"))["size"].sum() if len(d) else pd.Series(dtype=float)
            j = pd.concat([cv.rename("candle"), pv.rename("prints")], axis=1).fillna(0.0)
            rows.append(dict(coin=coin + "-USD", hour=h, trades=len(d), requests=nreq, secs=round(secs, 1),
                             candle_contracts=float(cv.sum()), print_contracts=float(pv.sum()),
                             minutes_candle=int((j.candle > 0).sum()),
                             minutes_match=int((np.abs(j.candle - j.prints) <= 1e-6 * np.maximum(1, j.candle)).sum()),
                             minutes_any=len(j), max_trades_1s=int(d.groupby(d.time.dt.floor("s")).size().max()) if len(d) else 0,
                             dupes=int(d.trade_id.duplicated().sum()) if len(d) else 0,
                             contracts_per_trade=float(pv.sum() / max(1, len(d)))))
            print(rows[-1], flush=True)
    R = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    R.to_csv(os.path.join(OUT, "probe_density.csv"), index=False)
    pd.set_option("display.width", 250)
    print(R.to_string(index=False))
    print(f"total requests {f.n_req}, {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main()
