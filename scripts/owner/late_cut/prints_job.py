#!/usr/bin/env python3
"""Late-cut replay (reports/owner/late_cut_prereg.md) on GitHub Actions: Coinbase spot trade prints for the merged
windows of one shard, reduced at once to one derived row per candidate (cut.bars). Raw prints are never written.

usage: python scripts/owner/late_cut/prints_job.py <windows.csv> <cands.csv.gz> <shard> <out_dir> [<soft_limit_min>]
Fetcher: scripts/owner/timing/prints_runner.py's strict_get and fetch, imported and used unchanged (signal lab 2's
fetcher: the pacing of scripts/wick_v4/fetch_trades.py, RATE 7 per second, its retries; a refusal raises and stops
the shard). Bookkeeping only: every HTTP 429 answer is counted (the session's get is wrapped to count, nothing else).
Before any fetch the reduction is tested against brute force on made-up prints (test_cut.py); a failure stops the job.
Output
  <out_dir>/derived_<shard>.parquet  base, coin, ts, window_id, status, n_s, close_s, vol_s (s = 0 .. 15)
  <out_dir>/status_<shard>.csv       one row per window: status (complete | capped | history_start | failed |
                                     not_run), n_prints, n_pages, n_req, seconds, error
  <out_dir>/job_<shard>.json         requests, prints, 429 answers, refusal
A refusal stops the shard; what was derived before it is written and committed, and the refusal is in job_<shard>.json.
"""
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "owner", "timing"))
import cut  # noqa: E402
import prints_runner as PR  # noqa: E402

FT = PR.FT
N429 = [0]
_get = FT.S.get


def counted_get(*a, **k):
    r = _get(*a, **k)
    if getattr(r, "status_code", None) == 429:
        N429[0] += 1
    return r


FT.S.get = counted_get


def main(wpath, cpath, shard, out_dir, soft_limit_min=300.0):
    W = pd.read_csv(wpath, parse_dates=["start", "end"])
    W = W[W.shard == shard].sort_values(["product", "start"]).reset_index(drop=True)
    Cd = pd.read_csv(cpath, parse_dates=["ts"])
    Cd = Cd[Cd.window_id.isin(W.window_id)]
    byw = dict(tuple(Cd.groupby("window_id")))
    os.makedirs(out_dir, exist_ok=True)
    locs, derived, stat, t0 = {}, {}, {}, time.time()
    n_prints = [0]
    refused = None

    def run(w):
        t1, r0 = time.time(), FT.N_REQ[0]
        row = dict(window_id=w.window_id, product=w.product, start=w.start, end=w.end)
        try:
            if w.product not in locs:
                locs[w.product] = FT.Locator(w.product)
            d, _, info = PR.fetch(locs[w.product], w.start, w.end)
            t_ns, px, sz = cut.order(d)
            out = []
            for r in byw[w.window_id].itertuples():
                b = cut.bars(t_ns, px, sz, pd.Timestamp(r.ts).value)
                b.update(base=r.base, coin=r.coin, ts=r.ts, window_id=r.window_id, status=info["status"])
                out.append(b)
            derived[w.window_id] = out
            n_prints[0] += len(d)
            row.update(status=info["status"], n_pages=info["n_pages"], n_prints=len(d), error="")
            del d, t_ns, px, sz
        except PR.Refused:
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
                print(f"{i}/{len(W)} windows, {n_prints[0]} prints, {FT.N_REQ[0]} requests, {N429[0]} answers 429, "
                      f"{time.time() - t0:.0f}s", flush=True)
        for w in [w for w in W.itertuples() if stat.get(w.window_id, {}).get("status") == "failed"]:
            if time.time() - t0 > 60 * soft_limit_min:
                break
            run(w)
    except PR.Refused as err:
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
        front = ["base", "coin", "ts", "window_id", "status"]
        Dd = Dd[front + [c for c in Dd.columns if c not in front]]
    Dd.to_parquet(os.path.join(out_dir, f"derived_{shard}.parquet"), index=False, compression="zstd")
    job = dict(shard=shard, windows=len(W), status=S.status.value_counts().to_dict(), derived_rows=len(Dd),
               candidates=len(Cd), prints=n_prints[0], requests=FT.N_REQ[0], answers_429=N429[0], refused=refused,
               seconds=round(time.time() - t0))
    json.dump(job, open(os.path.join(out_dir, f"job_{shard}.json"), "w"), indent=1, default=str)
    print(f"done: {json.dumps(job, default=str)}", flush=True)


if __name__ == "__main__":
    import test_cut as TC                                 # synthetic tests of the reduction first; a failure stops
    TC.test_bars()
    TC.test_pick()
    TC.test_carry()
    print("late-cut reduction tests: all passed", flush=True)
    a = sys.argv[1:]
    main(a[0], a[1], int(a[2]), a[3], *([float(a[4])] if len(a) > 4 else []))
