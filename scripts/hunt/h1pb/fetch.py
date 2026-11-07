#!/usr/bin/env python3
"""H1 trade fetching: common.TradeFetcher with two fixes (reported as shared-code problems, common.py untouched):
1. Paging completeness. common.TradeFetcher.window pages backward to floor(oldest second of the page), so trades in
   that boundary second that did not fit in the 1,000-trade page are skipped (BTC perp prints 2-5% short of candle
   volume in busy hours, BTC spot ~10%; reports/hunt/h1pb/probe_density.csv). Here the next page ends at
   floor(oldest second) + 1 and trades are de-duplicated by trade_id; only when one second holds more than 1,000
   trades is the rest of that second skipped (counted in `lost_seconds`).
2. Time parsing. pd.to_datetime without format fails on mixed ISO-8601 strings ("...:09Z" next to "...:09.123Z");
   format="ISO8601" is used.
Segments are fetched by `threads` fetchers in parallel, each paced at rate/threads requests per second.
"""
import concurrent.futures as cf
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402


class Fetcher(common.TradeFetcher):
    def __init__(self, rate=8.0):
        super().__init__(rate)
        self.lost_seconds = 0

    def window(self, pid, start, end):
        s = int(pd.Timestamp(start).timestamp())
        e = int(pd.Timestamp(end).timestamp())
        seen, rows = set(), []
        while e > s:
            tr = self._get(pid, s, e)
            new = [t for t in tr if t["trade_id"] not in seen]
            for t in new:
                seen.add(t["trade_id"])
                rows.append((t["trade_id"], t["time"], t["price"], t["size"], t["side"]))
            if len(tr) < 1000:
                break
            oldest = int(pd.Timestamp(min(t["time"][:19] for t in tr)).timestamp())     # floor second
            e_new = oldest + 1
            if not new or e_new >= e:                    # > 1,000 trades in one second: step past it
                e_new = oldest
                self.lost_seconds += 1
            e = e_new
        if not rows:
            return pd.DataFrame({"time": pd.Series(dtype="datetime64[ns]"), "price": pd.Series(dtype=float),
                                 "size": pd.Series(dtype=float), "side": pd.Series(dtype="int8")})
        d = pd.DataFrame(rows, columns=["trade_id", "time", "price", "size", "side"])
        d["trade_id"] = d["trade_id"].astype(np.int64)
        d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.tz_convert(None).astype("datetime64[ns]")
        d["price"] = d["price"].astype(float)
        d["size"] = d["size"].astype(float)
        d["side"] = (d["side"] == "BUY").astype("int8")       # 1 = maker bid hit by an aggressive seller
        d = d[(d.time >= pd.Timestamp(start)) & (d.time < pd.Timestamp(end))]
        return d.sort_values(["time", "trade_id"])[["trade_id", "time", "price", "size", "side"]]


def chunk_segments(segs, max_len=pd.Timedelta(hours=2)):
    out = []
    for a, b in segs:
        while a < b:
            c = min(b, a + max_len)
            out.append((a, c))
            a = c
    return out


def fetch_segments(pid, segs, threads=3, rate=8.4, log_every=200):
    """All trades of `pid` in the union of [start, end) segments. Returns (DataFrame, stats)."""
    segs = chunk_segments(segs)
    fetchers = [Fetcher(rate / threads) for _ in range(threads)]
    parts = [None] * len(segs)
    t0 = time.time()

    def work(i):
        f = fetchers[i % threads]
        parts[i] = f.window(pid, segs[i][0], segs[i][1])
        return i

    done = 0
    with cf.ThreadPoolExecutor(threads) as ex:
        # assign segment i to fetcher i % threads; one in flight per fetcher keeps each one's pacing valid
        futs = []
        for w in range(threads):
            futs.append(ex.submit(lambda w=w: [work(i) for i in range(w, len(segs), threads)]))
        for fu in cf.as_completed(futs):
            fu.result()
            done += 1
    d = [p for p in parts if p is not None and len(p)]
    D = pd.concat(d, ignore_index=True) if d else Fetcher().window(pid, "2000-01-01", "2000-01-01")
    D = D.drop_duplicates("trade_id").sort_values(["time", "trade_id"]).reset_index(drop=True)
    st = dict(pid=pid, segments=len(segs), trades=len(D), requests=sum(f.n_req for f in fetchers),
              lost_seconds=sum(f.lost_seconds for f in fetchers), secs=round(time.time() - t0, 1))
    print(f"  fetched {pid}: {st}", flush=True)
    return D, st
