#!/usr/bin/env python3
"""Fetch Coinbase Exchange trade-by-trade data for the windows in reports/wick_v4/windows.csv (shard i of n).

Used by the wick v4 sub-minute tests (reports/wick_v4_prereg.md, S1 and S2). Raw trades are written to
out/trades_<shard>.parquet and uploaded as a workflow artifact. They are never committed to the repo.

Coinbase's public trades endpoint pages backward by trade id (`after` = return trades with a smaller id). To find a
point in time, trade ids are located by interpolation search, reusing every probe as an anchor.
Usage: python scripts/wick_v4/fetch_trades.py <shard> <n_shards>
"""
import bisect
import os
import sys
import time

import pandas as pd
import requests

EX = "https://api.exchange.coinbase.com"
RATE = float(os.environ.get("RATE", "7"))          # requests per second (public limit is 10)
S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"
_last = [0.0]
N_REQ = [0]


def get(path, params):
    for a in range(10):
        wait = _last[0] + 1.0 / RATE - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        N_REQ[0] += 1
        try:
            r = S.get(EX + path, params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(1.0 + a)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as err:
            if a == 9:
                raise
            time.sleep(1.0 + a)


def t_of(x):
    return pd.Timestamp(x).tz_convert(None)


class Locator:
    """Sorted (trade_id, time) anchors for one product."""

    def __init__(self, pid):
        self.pid, self.pts = pid, []
        self._add(get(f"/products/{pid}/trades", {"limit": 1}))

    def _add(self, js):
        for t in js or []:
            p = (int(t["trade_id"]), t_of(t["time"]))
            i = bisect.bisect_left(self.pts, p)
            if i == len(self.pts) or self.pts[i] != p:
                self.pts.insert(i, p)

    def probe(self, tid):
        js = get(f"/products/{self.pid}/trades", {"limit": 1, "after": int(tid)})
        self._add(js)
        return js

    def seed_low(self):
        """A lower anchor: the earliest trade id that exists (trade ids start near 1)."""
        for x in (2, 10, 1000, 100000, 1000000, 10000000, 100000000):
            if self.probe(x):
                return

    def cursor_at(self, T, tol=500):
        """A trade id whose page (trades with smaller ids) starts at or after time T: interpolation search on
        (trade id, time), falling back to bisection whenever a step fails to halve the bracket."""
        if not any(p[1] < T for p in self.pts):
            self.seed_low()
        if not any(p[1] >= T for p in self.pts):
            self._add(get(f"/products/{self.pid}/trades", {"limit": 1}))
        last_span, step = None, 0
        while True:
            lo = [p for p in self.pts if p[1] < T]
            hi = [p for p in self.pts if p[1] >= T]
            if not hi:
                return self.pts[-1][0] + 1             # T is after the newest trade
            if not lo:
                return hi[0][0]                        # T is before the first trade
            l, h = lo[-1], hi[0]
            span = h[0] - l[0]
            if span <= tol or step > 80:
                return h[0]
            if last_span is not None and span > last_span / 2:
                guess = (l[0] + h[0]) // 2             # interpolation stalled: bisect
            else:
                dt = (h[1] - l[1]).total_seconds()
                frac = (T - l[1]).total_seconds() / dt if dt > 0 else 0.5
                guess = int(l[0] + min(0.99, max(0.01, frac)) * span)
            guess = min(max(guess, l[0] + 2), h[0] - 1)
            last_span, step = span, step + 1
            if not self.probe(guess):
                return h[0]


def fetch_window(loc, start, end):
    cur = loc.cursor_at(end)
    out = []
    for _ in range(400):
        js = get(f"/products/{loc.pid}/trades", {"limit": 1000, "after": int(cur)})
        if not js:
            break
        loc._add(js[-1:])
        for t in js:
            tt = t_of(t["time"])
            if start <= tt < end:
                out.append((int(t["trade_id"]), tt, float(t["price"]), float(t["size"]), t["side"]))
        oldest = t_of(js[-1]["time"])
        cur = int(js[-1]["trade_id"])
        if oldest < start:
            break
    return out


def main(shard, n):
    W = pd.read_csv("reports/wick_v4/windows.csv", parse_dates=["start", "end"])
    W = W[W.window_id % n == shard].sort_values(["product", "start"])
    locs, rows, t0 = {}, [], time.time()
    for i, w in enumerate(W.itertuples()):
        if w.product not in locs:
            locs[w.product] = Locator(w.product)
        try:
            tr = fetch_window(locs[w.product], w.start, w.end)
        except Exception as err:
            print(f"window {w.window_id} {w.product} {w.start}: FAILED {err!r}", flush=True)
            continue
        rows += [(w.window_id, w.product) + t for t in tr]
        if i % 25 == 0:
            print(f"{i}/{len(W)} windows, {len(rows)} trades, {N_REQ[0]} requests, {time.time() - t0:.0f}s", flush=True)
    os.makedirs("out", exist_ok=True)
    D = pd.DataFrame(rows, columns=["window_id", "product", "trade_id", "time", "price", "size", "side"])
    D.to_parquet(f"out/trades_{shard}.parquet", index=False)
    print(f"done: {len(W)} windows, {len(D)} trades, {N_REQ[0]} requests, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
