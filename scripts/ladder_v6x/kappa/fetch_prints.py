#!/usr/bin/env python3
"""Ladder v6 exits, kappa(m): fetch Coinbase Exchange trade prints for reports/ladder_v6x/kappa/windows.csv.

Red team 2's fetch (scripts/ladder_v5/redteam2/fetch_prints.py on ladder/redteam2), pointed at the kappa windows.
Shard i of n (windows with window_id % n == i). Uses the public trades endpoint and the interpolation-search locator
of scripts/ladder_v5/fetch_trades_early.py (same rate limit, same User-Agent; 429s are waited out, never worked
around). Raw prints go to out/trades_<shard>.parquet for the workflow artifact and are never committed.
Selection era only: refuses to run if any window lies outside 2025-01-01 .. 2026-03-31.
usage: python scripts/ladder_v6x/kappa/fetch_prints.py <shard> <n_shards>
"""
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v5"))
import fetch_trades_early as ft  # noqa: E402

WIN = os.path.join(ROOT, "reports", "ladder_v6x", "kappa", "windows.csv")
SEL = (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-04-01"))


def fetch_window(loc, start, end, max_pages=3000):
    """red team 2's fetch_window, unchanged: page backward from the trade id at `end` until a page reaches `start`."""
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
    assert (W.start >= SEL[0]).all() and (W.end <= SEL[1]).all(), "a window falls outside the selection era"
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
