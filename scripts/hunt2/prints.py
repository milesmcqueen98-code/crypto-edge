#!/usr/bin/env python3
"""Edge hunt 2: Coinbase trade prints for a list of windows (runs on GitHub Actions; exchange APIs are unreachable
from the research machine).

usage: python scripts/hunt2/prints.py <windows.csv> <shard> <n_shards> [<out_dir>]
  windows.csv columns: window_id, product, start, end   (UTC; spot products like SOL-USD, perps like SLP-20DEC30-CDE)
Spot products use the Exchange API's trade-id cursor (interpolation search, as scripts/wick_v4/fetch_trades.py);
perp-style futures use Advanced Trade's public market-trades endpoint by time window (scripts/hunt/common.py
TradeFetcher, with its page-boundary fix). Output: <out_dir>/prints_<shard>.parquet with columns
window_id, product, trade_id, time, price, size, side (side = the MAKER's side, upper case: BUY = a resting bid was
hit by a seller). Raw prints are uploaded as a workflow artifact, never committed.
"""
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick_v4"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import fetch_trades as FT  # noqa: E402  (Exchange API, interpolation search)


def fetch_spot(locs, product, start, end):
    if product not in locs:
        locs[product] = FT.Locator(product)
    tr = FT.fetch_window(locs[product], start, end)
    d = pd.DataFrame(tr, columns=["trade_id", "time", "price", "size", "side"])
    d["side"] = d["side"].str.upper()
    return d


def fetch_perp(tf, product, start, end):
    return tf.window(product, start, end)


def main(path, shard, n, out_dir="out"):
    W = pd.read_csv(path, parse_dates=["start", "end"])
    W = W[W.window_id % n == shard].sort_values(["product", "start"])
    locs, parts, t0, bad = {}, [], time.time(), 0
    tf = None
    for i, w in enumerate(W.itertuples()):
        try:
            if w.product.endswith("-CDE"):
                if tf is None:
                    import common  # noqa: E402
                    tf = common.TradeFetcher(rate=7.0)
                d = fetch_perp(tf, w.product, w.start, w.end)
            else:
                d = fetch_spot(locs, w.product, w.start, w.end)
        except Exception as err:  # noqa: BLE001
            bad += 1
            print(f"window {w.window_id} {w.product} {w.start}: FAILED {err!r}", flush=True)
            continue
        d.insert(0, "product", w.product)
        d.insert(0, "window_id", w.window_id)
        parts.append(d)
        if i % 50 == 0:
            n_tr = sum(len(p) for p in parts)
            print(f"{i}/{len(W)} windows, {n_tr} prints, {time.time() - t0:.0f}s", flush=True)
    os.makedirs(out_dir, exist_ok=True)
    D = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["window_id", "product", "trade_id", "time", "price", "size", "side"])
    D.to_parquet(os.path.join(out_dir, f"prints_{shard}.parquet"), index=False)
    print(f"done: {len(W)} windows ({bad} failed), {len(D)} prints, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), *(sys.argv[4:5] or ["out"]))
