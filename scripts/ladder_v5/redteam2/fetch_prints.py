#!/usr/bin/env python3
"""Red team 2 (ladder v5): fetch Coinbase Exchange trade prints for reports/ladder_v5/redteam2/windows_exit.csv.

Shard i of n (windows with window_id % n == i). Uses the public trades endpoint and the interpolation-search locator
of scripts/ladder_v5/fetch_trades_early.py (same rate limit, same User-Agent; 429s are waited out, never worked
around). Raw prints go to out/trades_<shard>.parquet for the workflow artifact and are never committed.
usage: python scripts/ladder_v5/redteam2/fetch_prints.py <shard> <n_shards>
"""
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import fetch_trades_early as ft  # noqa: E402

WIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "reports", "ladder_v5", "redteam2",
                   "windows_exit.csv")


def fetch_window(loc, start, end, max_pages=3000):
    cur = loc.cursor_at(end)
    out = []
    for _ in range(max_pages):
        js = ft.get(f"/products/{loc.pid}/trades", {"limit": 1000, "after": int(cur)})
        if not js:
            break
        loc._add(js[-1:])
        for t in js:
            tt = ft.t_of(t["time"])
            if start <= tt < end:
                out.append((int(t["trade_id"]), tt, float(t["price"]), float(t["size"]), t["side"]))
        oldest = ft.t_of(js[-1]["time"])
        cur = int(js[-1]["trade_id"])
        if oldest < start:
            break
    return out


def main(shard, n):
    W = pd.read_csv(WIN, parse_dates=["start", "end"])
    W = W[W.window_id % n == shard].sort_values(["product", "start"])
    locs, rows, t0, failed = {}, [], time.time(), 0
    for i, w in enumerate(W.itertuples()):
        try:
            if w.product not in locs:
                locs[w.product] = ft.Locator(w.product)
            tr = fetch_window(locs[w.product], w.start, w.end)
        except Exception as err:                         # noqa: BLE001
            failed += 1
            print(f"window {w.window_id} {w.product} {w.start}: FAILED {err!r}", flush=True)
            continue
        rows += [(w.window_id, w.product) + t for t in tr]
        if i % 25 == 0:
            print(f"{i}/{len(W)} windows, {len(rows):,} prints, {ft.N_REQ[0]} requests, {time.time() - t0:.0f}s",
                  flush=True)
    os.makedirs("out", exist_ok=True)
    D = pd.DataFrame(rows, columns=["window_id", "product", "trade_id", "time", "price", "size", "side"])
    D.to_parquet(f"out/trades_{shard}.parquet", index=False)
    print(f"done: {len(W)} windows ({failed} failed), {len(D):,} prints, {ft.N_REQ[0]} requests, "
          f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
