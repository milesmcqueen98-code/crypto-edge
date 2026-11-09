#!/usr/bin/env python3
"""Signal lab 2 (reports/signal_lab/prospective_prereg.md): Coinbase spot trade prints for the merged F6 windows of one
shard, with a completeness record per window. Runs on GitHub Actions (exchange APIs are unreachable from the research
machine); raw prints go to the workflow artifact only and are never committed.

usage: python scripts/signal_lab/prints_fetch.py <windows.csv> <shard> [<out_dir>] [<soft_limit_minutes>]
  windows.csv: window_id, product, start, end, ..., shard (scripts/signal_lab/prints_windows.py)

Same fetcher as scripts/hunt2/prints.py: the Exchange API's trade-id cursor located by interpolation search
(scripts/wick_v4/fetch_trades.py Locator, its pacing of RATE = 7 requests per second and its retry rule). Two changes
of bookkeeping, none of rate:
  - a refusal stops the shard at once: HTTP 401 or 403, or 429 that persists through all ten retries (fetch_trades.get
    would return None there, which fetch_window reads as "no older trades");
  - every window gets a status: complete (a page reached a trade stamped before the window's start, so every trade in
    [start, end) was read), capped (page limit), history_start (the API returned no older trades), failed, not_run.
Output
  <out_dir>/prints_<shard>.parquet  window_id, product, trade_id, time, price, size, side (the MAKER's side, upper
                                    case: BUY = a resting bid was hit by a seller); only trades in [start, end)
  <out_dir>/status_<shard>.csv      one row per window of the shard
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick_v4"))
import fetch_trades as FT  # noqa: E402

MAX_PAGES = 20000
COLS = ["trade_id", "time", "price", "size", "side"]


class Refused(RuntimeError):
    pass


def strict_get(path, params):
    """fetch_trades.get with the same pacing, session, header and retries; a refusal raises Refused."""
    for a in range(10):
        wait = FT._last[0] + 1.0 / FT.RATE - time.time()
        if wait > 0:
            time.sleep(wait)
        FT._last[0] = time.time()
        FT.N_REQ[0] += 1
        try:
            r = FT.S.get(FT.EX + path, params=params, timeout=20)
        except requests.RequestException:
            if a == 9:
                raise
            time.sleep(1.0 + a)
            continue
        if r.status_code in (401, 403):
            raise Refused(f"HTTP {r.status_code} on {path} {params}: {r.text[:300]!r}")
        if r.status_code == 429:
            time.sleep(1.0 + a)
            continue
        try:
            r.raise_for_status()
        except requests.RequestException:
            if a == 9:
                raise
            time.sleep(1.0 + a)
            continue
        return r.json()
    raise Refused(f"HTTP 429 through 10 retries on {path} {params}")


FT.get = strict_get           # Locator's probes go through the same rule


def page_frame(js):
    d = pd.DataFrame.from_records(js, columns=COLS)
    d["trade_id"] = d["trade_id"].astype(np.int64)
    d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.tz_convert(None).astype("datetime64[ns]")
    d["price"] = d["price"].astype(np.float64)
    d["size"] = d["size"].astype(np.float64)
    d["side"] = d["side"].astype(str).str.upper()
    return d


def fetch(loc, start, end):
    """Every trade with start <= time < end, paging back from a cursor whose page starts at or after `end`."""
    cur = loc.cursor_at(end)
    cur0, parts, n_pages, status, oldest = int(cur), [], 0, "capped", pd.NaT
    while n_pages < MAX_PAGES:
        js = FT.get(f"/products/{loc.pid}/trades", {"limit": 1000, "after": int(cur)})
        n_pages += 1
        if not js:
            status = "history_start"
            break
        d = page_frame(js)
        if (d.trade_id >= cur).any():
            raise RuntimeError(f"page after {cur} holds ids >= the cursor")
        i = int(d.trade_id.to_numpy().argmin())
        loc._add([js[i]])
        cur, oldest = int(d.trade_id.iloc[i]), d.time.iloc[i]
        parts.append(d[(d.time >= start) & (d.time < end)])
        if oldest < start:
            status = "complete"
            break
    D = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLS)
    return D, dict(status=status, n_pages=n_pages, cursor=cur0, last_cursor=cur, oldest=oldest)


def main(path, shard, out_dir="out", soft_limit_min=300.0):
    W = pd.read_csv(path, parse_dates=["start", "end"])
    W = W[W.shard == shard].sort_values(["product", "start"]).reset_index(drop=True)
    os.makedirs(out_dir, exist_ok=True)
    locs, parts, stat, t0 = {}, {}, {}, time.time()
    refused = None

    def run(w):
        t1, r0 = time.time(), FT.N_REQ[0]
        row = dict(window_id=w.window_id, product=w.product, start=w.start, end=w.end)
        try:
            if w.product not in locs:
                locs[w.product] = FT.Locator(w.product)
            d, info = fetch(locs[w.product], w.start, w.end)
            d.insert(0, "product", w.product)
            d.insert(0, "window_id", np.int32(w.window_id))
            parts[w.window_id] = d
            row.update(info, n_prints=len(d), error="")
        except Refused:
            raise
        except Exception as err:  # noqa: BLE001
            parts.pop(w.window_id, None)
            row.update(status="failed", n_prints=0, error=repr(err)[:300])
            print(f"window {w.window_id} {w.product} {w.start}: FAILED {err!r}", flush=True)
        row.update(n_req=FT.N_REQ[0] - r0, seconds=round(time.time() - t1, 2))
        stat[w.window_id] = row

    try:
        for i, w in enumerate(W.itertuples()):
            if time.time() - t0 > 60 * soft_limit_min:
                print(f"soft time limit reached after {i} windows", flush=True)
                break
            run(w)
            if i % 25 == 0:
                n_tr = sum(len(p) for p in parts.values())
                print(f"{i}/{len(W)} windows, {n_tr} prints, {FT.N_REQ[0]} requests, {time.time() - t0:.0f}s",
                      flush=True)
        retry = [w for w in W.itertuples() if stat.get(w.window_id, {}).get("status") == "failed"]
        for w in retry:                                   # one more try for failed windows
            if time.time() - t0 > 60 * soft_limit_min:
                break
            run(w)
    except Refused as err:
        refused = str(err)
        print(f"REFUSED, shard stopped: {err}", flush=True)
    rows = [stat.get(w.window_id, dict(window_id=w.window_id, product=w.product, start=w.start, end=w.end,
                                        status="not_run", n_prints=0, error=refused or "time limit"))
            for w in W.itertuples()]
    S = pd.DataFrame(rows)
    S.to_csv(os.path.join(out_dir, f"status_{shard}.csv"), index=False)
    keep = [parts[k] for k in W.window_id if k in parts]
    D = pd.concat(keep, ignore_index=True) if keep else pd.DataFrame(columns=["window_id", "product"] + COLS)
    D.to_parquet(os.path.join(out_dir, f"prints_{shard}.parquet"), index=False, row_group_size=1_000_000)
    print(f"done: {len(W)} windows, status {S.status.value_counts().to_dict()}, {len(D)} prints, "
          f"{FT.N_REQ[0]} requests, {time.time() - t0:.0f}s" + (f", REFUSED: {refused}" if refused else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], int(a[1]), *(a[2:3] or ["out"]), *([float(a[3])] if len(a) > 3 else []))
