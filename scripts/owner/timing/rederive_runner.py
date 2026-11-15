#!/usr/bin/env python3
"""Live order timing study, part 3 (reports/owner/timing_prereg.md, "Part 3, deviation 1"), on GitHub Actions: the
reduced print paths of every studied minute for fifteen start times (the six of parts 1 and 2 and the nine new-bid
times of part 3), from the raw prints of the first fetch (the eight shard artifacts, downloaded into art/). No request
is made. Modelled on deep_runner.py.

usage: python scripts/owner/timing/rederive_runner.py <art_dir> <rows.csv.gz> <derived_dir> <out_dir>
  art_dir      the first fetch's artifacts: **/prints_*.parquet (window_id, trade_id, time, price, size, side)
  rows.csv.gz  tag, coin, q, L_prev, L, tick, window_id (one per studied minute)
  derived_dir  the reduced rows on file: derived_<shard>.parquet and status_<shard>.csv (prints_runner.py)
Per studied minute, prints_derive.derive is called with the fifteen starts on the window's prints (per window_id,
de-duplicated by trade_id, ordered by (time, trade_id), as prints_runner.derive_window); the last print before q
(pre_px, pre_ms) is the row on file's (the artifacts hold the window [start, end) only).
Cross-check (decisive): for the six old starts, every column the two derivations share must equal the row on file
(lists element by element, floats exactly, NaN equal to NaN); the status (status_<shard>.csv of the row's window) and
the set of rows must match.
Storage: the fifteen running-minimum paths of a row are stored as one union (un_ms, un_px: every point of any of
the paths, ordered by time and, within one time, by falling price); prints_derive.running_min(un_ms, un_px, s)
returns the path from s exactly. This is checked on every row before writing (union_recovery in the check), and in
test_rederive.py.
Outputs (the only files written; nothing raw):
  <out_dir>/derived3_<shard>.parquet  tag, coin, q, window_id, status, n60, n70, min60, min70, pre_ms, pre_px, and
                                      per start s: last_px_s, last_ms_s, ft_prev_s, ft_cur_s; un_ms, un_px
  <out_dir>/rederive_check.csv        per shard: rows compared, rows missing on either side, rows differing, and per
                                      column the count of differing rows
  <out_dir>/rederive_run.json         counts, starts, artifact files seen, timings, reproduced true/false (and the
                                      traceback text if an exception stopped the run)
The script exits 0 in every case (the workflow commits only the outputs of a job that succeeds).
"""
import glob
import json
import os
import sys
import time
import traceback

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prints_derive as PD  # noqa: E402

OLD = tuple(PD.STARTS)
NEW = (2000, 5200, 10200, 11080, 11700, 12150, 13900, 17250, 24000)
STARTS = tuple(sorted(set(OLD) | set(NEW)))
SCALAR = ("last_px", "last_ms", "ft_prev", "ft_cur")
BASE = ("n60", "n70", "min60", "min70", "pre_ms", "pre_px")


def union_path(d, starts):
    """One union of the running-minimum paths of derive's output d: (ms, px) ordered by time, then falling price."""
    pts = set()
    for s in starts:
        pts.update(zip(map(float, d[f"rl_ms_{s}"]), map(float, d[f"rl_px_{s}"])))
    pts = sorted(pts, key=lambda x: (x[0], -x[1]))
    return [a for a, _ in pts], [b for _, b in pts]


def paths_from_union(un_ms, un_px, starts):
    """{s: (times, prices)}: the running-minimum path from each start, rebuilt from the union."""
    a, b = np.asarray(un_ms, float), np.asarray(un_px, float)
    return {s: PD.running_min(a, b, s) for s in starts}


def same_scalar(a, b):
    a, b = float(a), float(b)
    return a == b or (np.isnan(a) and np.isnan(b))


def same_list(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a.shape == b.shape and bool(np.all((a == b) | (np.isnan(a) & np.isnan(b))))


def compact(d, starts):
    """The stored row: base columns, the per-start scalars and the union path (no per-start lists)."""
    out = {k: d[k] for k in BASE}
    for s in starts:
        for k in SCALAR:
            out[f"{k}_{s}"] = d[f"{k}_{s}"]
    out["un_ms"], out["un_px"] = union_path(d, starts)
    return out


def window_prints(fs, log):
    """{window_id: (t ns int64, px)} from the artifact files: per window_id, de-duplicated by trade_id, ordered by
    (time, trade_id); a window met in an earlier file is kept from that file (deep_runner.py)."""
    W = {}
    for f in fs:
        P = pd.read_parquet(f, columns=["window_id", "trade_id", "time", "price"])
        n = 0
        for wid, D in P.groupby("window_id"):
            wid = int(wid)
            if wid in W:
                continue
            D = D.drop_duplicates("trade_id").sort_values(["time", "trade_id"])
            W[wid] = (D.time.to_numpy().astype("datetime64[ns]").astype(np.int64), D.price.to_numpy(np.float64))
            n += 1
        log.append(dict(file=os.path.relpath(f), rows=int(len(P)), windows_new=n))
        print(f, len(P), "prints,", n, "new windows", flush=True)
        del P
    return W


def run(art, rpath, ddir, out, info):
    t0 = time.time()
    R = pd.read_csv(rpath, parse_dates=["q"])
    fs = sorted(glob.glob(os.path.join(art, "**", "prints_*.parquet"), recursive=True))
    info["artifact_files"] = []
    info["starts"] = list(STARTS)
    info["old_starts"] = list(OLD)
    W = window_prints(fs, info["artifact_files"])
    info["windows_in_artifacts"] = len(W)
    info["t_read_s"] = round(time.time() - t0, 1)
    shard_files = sorted(glob.glob(os.path.join(ddir, "derived_*.parquet")))
    info["shards"] = [os.path.basename(f) for f in shard_files]
    checks, all_ok, recov_bad = [], True, 0
    for f in shard_files:
        shard = os.path.basename(f)[len("derived_"):-len(".parquet")]
        F = pd.read_parquet(f)
        F["q"] = pd.to_datetime(F.q)
        st = pd.read_csv(os.path.join(ddir, f"status_{shard}.csv"))
        wstat = dict(zip(st.window_id.astype(int), st.status))
        Rs = R[R.window_id.isin(st.window_id)]
        keyF = dict(zip(zip(F.coin, F.q), range(len(F))))
        keyR = set(zip(Rs.coin, Rs.q))
        shared_cols = [c for c in F.columns if c not in ("tag", "coin", "q", "window_id", "status")]
        diff = {c: 0 for c in shared_cols}
        ck = dict(shard=shard, rows_file=len(F), rows_studied=len(Rs), rows_compared=0, rows_rederived=0,
                  missing_on_file=0, missing_rederived=0, missing_window_prints=0, rows_differing=0,
                  status_differing=0, union_recovery_bad=0, pre_in_window_differs=0)
        ck["missing_on_file"] = len(keyR - set(keyF))
        ck["file_not_studied"] = len(set(keyF) - keyR)
        out_rows = []
        for r in Rs.itertuples():
            i = keyF.get((r.coin, r.q))
            if r.window_id not in W:
                ck["missing_window_prints"] += 1
                if i is not None:
                    ck["missing_rederived"] += 1
                continue
            t, px = W[r.window_id]
            q = np.int64(pd.Timestamp(r.q).value)
            a = int(np.searchsorted(t, q, "left"))
            b = int(np.searchsorted(t, q + int(PD.WIN_MS * 1e6), "left"))
            if i is None:
                continue
            x = F.iloc[i]
            d = PD.derive((t[a:b] - q) / 1e6, px[a:b], x.pre_ms, x.pre_px, r.L_prev, r.L, r.tick, starts=STARTS)
            ck["rows_rederived"] += 1
            ck["rows_compared"] += 1
            if a > 0 and not (same_scalar((t[a - 1] - q) / 1e6, x.pre_ms) and same_scalar(px[a - 1], x.pre_px)):
                ck["pre_in_window_differs"] += 1             # informational: the row on file's pre is used
            bad = False
            for c in shared_cols:
                if c not in d:
                    diff[c] += 1
                    bad = True
                    continue
                v, w = d[c], x[c]
                ok = same_list(v, w) if c.startswith("rl_") else same_scalar(v, w)
                if not ok:
                    diff[c] += 1
                    bad = True
            stt = wstat.get(int(r.window_id))
            if stt != x.status:
                ck["status_differing"] += 1
                bad = True
            ck["rows_differing"] += int(bad)
            row = compact(d, STARTS)
            rec = paths_from_union(row["un_ms"], row["un_px"], STARTS)
            if not all(same_list(rec[s][0], d[f"rl_ms_{s}"]) and same_list(rec[s][1], d[f"rl_px_{s}"])
                       for s in STARTS):
                ck["union_recovery_bad"] += 1
            row.update(tag=x.tag, coin=x.coin, q=x.q, window_id=int(x.window_id), status=stt)
            out_rows.append(row)
        ck.update({f"diff_{c}": n for c, n in diff.items()})
        ok = (ck["rows_differing"] == 0 and ck["missing_on_file"] == 0 and ck["missing_rederived"] == 0
              and ck["file_not_studied"] == 0 and ck["union_recovery_bad"] == 0
              and ck["rows_compared"] == ck["rows_file"])
        ck["identical"] = bool(ok)
        all_ok &= ok
        recov_bad += ck["union_recovery_bad"]
        checks.append(ck)
        O = pd.DataFrame(out_rows)
        if len(O):
            front = ["tag", "coin", "q", "window_id", "status"]
            O = O[front + [c for c in O.columns if c not in front]]
        O.to_parquet(os.path.join(out, f"derived3_{shard}.parquet"), index=False, compression="zstd")
        pd.DataFrame(checks).to_csv(os.path.join(out, "rederive_check.csv"), index=False)
        print(f"shard {shard}: {ck['rows_compared']} rows compared, {ck['rows_differing']} differing, "
              f"{ck['missing_on_file']} / {ck['missing_rederived']} missing (file / rederived), "
              f"union recovery bad {ck['union_recovery_bad']} ({time.time() - t0:.0f}s)", flush=True)
    if not shard_files:
        all_ok = False
    info["rows_compared"] = int(sum(c["rows_compared"] for c in checks))
    info["rows_differing"] = int(sum(c["rows_differing"] for c in checks))
    info["rows_missing"] = int(sum(c["missing_on_file"] + c["missing_rederived"] + c["file_not_studied"]
                                   for c in checks))
    info["union_recovery_bad"] = int(recov_bad)
    info["out_mb"] = round(sum(os.path.getsize(p) for p in glob.glob(os.path.join(out, "derived3_*.parquet"))) / 1e6, 2)
    info["reproduced"] = bool(all_ok)
    info["t_total_s"] = round(time.time() - t0, 1)


def main(art, rpath, ddir, out):
    info = dict(script="scripts/owner/timing/rederive_runner.py", reproduced=False)
    try:
        os.makedirs(out, exist_ok=True)
        run(art, rpath, ddir, out, info)
    except BaseException:  # noqa: BLE001  (the report must survive any failure)
        info["reproduced"] = False
        info["error"] = traceback.format_exc()
        print(info["error"], flush=True)
    try:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "rederive_run.json"), "w") as fh:
            json.dump(info, fh, indent=1, default=str)
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
    print(f"reproduced: {str(info.get('reproduced')).lower()}; rows compared {info.get('rows_compared')}, "
          f"differing {info.get('rows_differing')}, missing {info.get('rows_missing')}, "
          f"union recovery bad {info.get('union_recovery_bad')}, out {info.get('out_mb')} MB", flush=True)
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) != 4:
        print(__doc__)
        sys.exit(0)
    sys.exit(main(*a))
