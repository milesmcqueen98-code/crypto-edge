#!/usr/bin/env python3
"""Live order timing study (reports/owner/timing_prereg.md), step 2 on GitHub Actions: Coinbase spot trade prints for
the merged [q, q + 70 s) windows of one shard, reduced at once to one derived row per studied (coin, q)
(prints_derive.py). Raw prints never leave the runner unless an artifact path is given.

usage: python scripts/owner/timing/prints_runner.py <windows.csv> <rows.csv.gz> <shard> <out_dir> [<soft_limit_min>]
  windows.csv  window_id, product, start, end, n_rows, est_prints, shard   (scripts/owner/timing/windows.py)
  rows.csv.gz  tag, coin, q, L_prev, L, tick, window_id                   (one per studied minute)
Fetcher: signal lab 2's scripts/signal_lab/prints_fetch.py (copied below: strict_get and fetch, the same pacing of
scripts/wick_v4/fetch_trades.py, RATE 7 per second, its retries, a refusal stops the shard), with one addition of
bookkeeping: fetch also returns the newest print stamped before the window's start, read from the last page it
already fetched (no extra request); it is the "last print before q" of the window's first minute.
Output
  <out_dir>/derived_<shard>.parquet   tag, coin, q, window_id, status, and prints_derive.derive's columns
  <out_dir>/status_<shard>.csv        one row per window: status (complete | capped | history_start | failed |
                                      not_run), n_prints, n_pages, n_req, seconds, error
  <out_dir>/prints_<shard>.parquet    raw prints (artifact only, never committed)
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick_v4"))
sys.path.insert(0, HERE)
import fetch_trades as FT  # noqa: E402
import prints_derive as PD  # noqa: E402

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
        if r.status_code in (401, 403, 451):
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
        try:
            return r.json()
        except ValueError:                               # a bot-check page instead of JSON
            raise Refused(f"non-JSON reply on {path} {params}: {r.text[:300]!r}")
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
    """Every trade with start <= time < end, paging back from a cursor whose page starts at or after `end`; and the
    newest trade stamped before start among the pages read (the last page holds it when status is complete)."""
    cur = loc.cursor_at(end)
    cur0, parts, n_pages, status, oldest = int(cur), [], 0, "capped", pd.NaT
    pre = None
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
        b = d[d.time < start]
        if len(b):
            b = b.sort_values(["time", "trade_id"]).iloc[-1]
            if pre is None or (b.time, b.trade_id) > (pre.time, pre.trade_id):
                pre = b
        if oldest < start:
            status = "complete"
            break
    D = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLS)
    return D, pre, dict(status=status, n_pages=n_pages, cursor=cur0, last_cursor=cur, oldest=oldest)


def derive_window(D, pre, rows):
    """Derived rows of the studied minutes of one merged window."""
    D = D.drop_duplicates("trade_id").sort_values(["time", "trade_id"])
    t = D.time.to_numpy().astype("datetime64[ns]").astype(np.int64)
    px = D.price.to_numpy(np.float64)
    pre_t = np.int64(pd.Timestamp(pre.time).value) if pre is not None else None
    pre_p = float(pre.price) if pre is not None else np.nan
    out = []
    for r in rows.itertuples():
        q = np.int64(pd.Timestamp(r.q).value)
        a = int(np.searchsorted(t, q, "left"))
        b = int(np.searchsorted(t, q + int(PD.WIN_MS * 1e6), "left"))
        if a > 0:
            pm, pp = (t[a - 1] - q) / 1e6, px[a - 1]
        elif pre_t is not None:
            pm, pp = (pre_t - q) / 1e6, pre_p
        else:
            pm, pp = np.nan, np.nan
        d = PD.derive((t[a:b] - q) / 1e6, px[a:b], pm, pp, r.L_prev, r.L, r.tick)
        d.update(tag=r.tag, coin=r.coin, q=r.q, window_id=r.window_id)
        out.append(d)
    return out


def main(wpath, rpath, shard, out_dir, soft_limit_min=300.0):
    W = pd.read_csv(wpath, parse_dates=["start", "end"])
    W = W[W.shard == shard].sort_values(["product", "start"]).reset_index(drop=True)
    R = pd.read_csv(rpath, parse_dates=["q"])
    R = R[R.window_id.isin(W.window_id)]
    byw = dict(tuple(R.groupby("window_id")))
    os.makedirs(out_dir, exist_ok=True)
    locs, raw, derived, stat, t0 = {}, [], {}, {}, time.time()
    refused = None

    def run(w):
        t1, r0 = time.time(), FT.N_REQ[0]
        row = dict(window_id=w.window_id, product=w.product, start=w.start, end=w.end)
        try:
            if w.product not in locs:
                locs[w.product] = FT.Locator(w.product)
            d, pre, info = fetch(locs[w.product], w.start, w.end)
            dv = derive_window(d, pre, byw[w.window_id])
            for x in dv:
                x["status"] = info["status"]
            derived[w.window_id] = dv
            d.insert(0, "window_id", np.int32(w.window_id))
            raw.append(d)
            row.update(info, n_prints=len(d), pre_known=pre is not None, error="")
        except Refused:
            raise
        except Exception as err:  # noqa: BLE001
            derived.pop(w.window_id, None)
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
            if i % 100 == 0:
                print(f"{i}/{len(W)} windows, {sum(len(x) for x in raw)} prints, {FT.N_REQ[0]} requests, "
                      f"{time.time() - t0:.0f}s", flush=True)
        for w in [w for w in W.itertuples() if stat.get(w.window_id, {}).get("status") == "failed"]:
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
    dv = [x for k in W.window_id if k in derived for x in derived[k]]
    Dd = pd.DataFrame(dv)
    if len(Dd):
        front = ["tag", "coin", "q", "window_id", "status"]
        Dd = Dd[front + [c for c in Dd.columns if c not in front]]
    Dd.to_parquet(os.path.join(out_dir, f"derived_{shard}.parquet"), index=False, compression="zstd")
    Rw = pd.concat(raw, ignore_index=True) if raw else pd.DataFrame(columns=["window_id"] + COLS)
    Rw.to_parquet(os.path.join(out_dir, f"prints_{shard}.parquet"), index=False)
    print(f"done: {len(W)} windows, status {S.status.value_counts().to_dict()}, {len(Dd)} derived rows of "
          f"{len(R)}, {len(Rw)} prints, {FT.N_REQ[0]} requests, {time.time() - t0:.0f}s"
          + (f", REFUSED: {refused}" if refused else ""))
    if refused:
        sys.exit(3)


if __name__ == "__main__":
    import test_derive as TD                              # synthetic tests first; a failure stops the job
    TD.test_derive_random()
    TD.test_boundary()
    TD.test_window()
    print("prints_derive tests: all passed", flush=True)
    a = sys.argv[1:]
    main(a[0], a[1], int(a[2]), a[3], *([float(a[4])] if len(a) > 4 else []))
