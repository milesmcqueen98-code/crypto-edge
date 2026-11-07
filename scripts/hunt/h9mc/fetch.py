#!/usr/bin/env python3
"""H9 (MC) fetch, run on GitHub Actions: Coinbase perp prints for every day since each perp's launch, in two ET
windows. Trading days are weekdays with US holidays dropped; weekends and US holidays are fetched as aggregates only,
as a descriptive placebo (no intraday margin, so no 4 pm step; R1 memo), never as trials:
  - control 13:30-14:30 ET  -> per-minute aggregates only (Step 1)
  - 4 pm    15:30-17:30 ET  -> raw prints (fills, entries, exits through the 17:00 exit) + per-minute aggregates
    (a superset of the SPEC's 15:30-16:45 ET, because V-after exits at 17:00)
Usage: python scripts/hunt/h9mc/fetch.py SHARD NSHARDS
Writes data/hunt/h9mc/prints_<coin>_<YYYY-MM>.parquet, agg_<coin>_<YYYY-MM>.parquet and log_<shard>.parquet.
Shards are coin/month blocks balanced by an estimated request count. No statistics are computed here beyond a
per-window completeness check against 1-minute candle volume (written to the log, not printed)."""
import os
import sys
import time
import traceback

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hcommon as H  # noqa: E402
import common  # noqa: E402

OUT = os.path.join(common.ROOT, "data", "hunt", "h9mc")
CTRL, FOUR = H.CTRL, H.FOUR
WEIGHT = {"BTC": 10, "ETH": 9, "SOL": 6, "XRP": 6}      # rough requests per coin-day (others: 2)


def tasks():
    out = []
    for coin in H.COINS:
        days = H.all_days(H.launch_day(coin), H.LAST_DAY)
        for m, dd in pd.Series(days, index=days).groupby(days.to_period("M")):
            out.append((coin, str(m), list(dd.index), WEIGHT.get(coin, 2) * len(dd)))
    return out


def shard_of(all_tasks, n):
    load = [0.0] * n
    assign = {}
    for t in sorted(all_tasks, key=lambda x: -x[3]):
        i = int(np.argmin(load))
        assign[(t[0], t[1])] = i
        load[i] += t[3]
    return assign, load


def minute_agg(d, coin, win):
    if d.empty:
        return pd.DataFrame()
    cs = common.PERP[coin][1]
    x = d.assign(minute=d.time.dt.floor("min"), agg=(d.side == "BUY").astype(np.int8))
    x["usd"] = x.price * H.PX_PER_COIN.get(coin, 1.0) * x["size"] * cs
    x["agg_contracts"] = x["size"] * x["agg"]
    x["agg_usd"] = x["usd"] * x["agg"]
    g = x.groupby("minute")
    a = pd.DataFrame({
        "n": g.size(),
        "contracts": g["size"].sum(),
        "agg_contracts": g["agg_contracts"].sum(),
        "n_agg": g["agg"].sum(),
        "usd": g["usd"].sum(),
        "agg_usd": g["agg_usd"].sum(),
        "first_px": g["price"].first(),
        "last_px": g["price"].last(),
        "lo": g["price"].min(),
        "hi": g["price"].max(),
    }).reset_index()
    a.insert(0, "win", win)
    a.insert(0, "coin", coin)
    return a


def main():
    shard, n = int(sys.argv[1]), int(sys.argv[2])
    T = tasks()
    assign, load = shard_of(T, n)
    mine = [t for t in T if assign[(t[0], t[1])] == shard]
    print(f"shard {shard}/{n}: {len(mine)} coin-months, est requests {load[shard]:.0f}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    f = H.Fetcher()
    logs = []
    t_start = time.time()
    for coin, month, days, _ in mine:
        pid = common.PERP[coin][0]
        cand = common.load_perp(coin)
        cand_contracts = cand.volume / common.PERP[coin][1]
        raws, aggs = [], []
        for day in days:
            for win, (w0, w1) in ((0, CTRL), (1, FOUR)):
                s, e = H.et_to_utc(day, w0), H.et_to_utc(day, w1)
                r0 = f.n_req
                try:
                    d = f.window(pid, s, e)
                    err = ""
                except Exception as ex:  # noqa: BLE001
                    d = pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
                    err = f"{type(ex).__name__}: {ex}"[:200]
                cc = cand_contracts[(cand_contracts.index >= s) & (cand_contracts.index < e)]
                trading = H.is_trading_day(day)
                logs.append(dict(coin=coin, day=day, win=win, trading=trading, prints=len(d),
                                 contracts=float(d["size"].sum()) if len(d) else 0.0,
                                 candle_contracts=float(cc.sum()), candle_minutes=int((cc > 0).sum()),
                                 req=f.n_req - r0, lost_seconds=getattr(f, "lost", 0), err=err))
                if len(d):
                    aggs.append(minute_agg(d, coin, win))
                    if win == 1 and trading:
                        raws.append(pd.DataFrame({
                            "coin": coin,
                            "t_us": d.time.to_numpy().astype("datetime64[us]").astype(np.int64),
                            "price": d.price.to_numpy(np.float64),
                            "size": d["size"].to_numpy(np.float32),
                            "aggsell": (d.side == "BUY").to_numpy(np.int8),
                        }))
        if raws:
            pd.concat(raws, ignore_index=True).to_parquet(os.path.join(OUT, f"prints_{coin}_{month}.parquet"),
                                                          index=False, compression="zstd")
        if aggs:
            pd.concat(aggs, ignore_index=True).to_parquet(os.path.join(OUT, f"agg_{coin}_{month}.parquet"),
                                                          index=False, compression="zstd")
        print(f"{coin} {month}: {len(days)} days, requests so far {f.n_req}, {time.time() - t_start:.0f}s", flush=True)
    pd.DataFrame(logs).to_parquet(os.path.join(OUT, f"log_{shard}.parquet"), index=False)
    print("done", f.n_req, "requests", round(time.time() - t_start), "s")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
