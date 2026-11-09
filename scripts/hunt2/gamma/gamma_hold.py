#!/usr/bin/env python3
"""Edge hunt 2, GAMMA: the single HOLD read (run only AFTER the freeze commit of reports/hunt2/gamma/frozen.json).

The frozen variant (signal column, threshold number) is applied unchanged: skipped hours are those whose hourly
signal is below the frozen threshold, from the DEV file for the sel era (exactly the logged DEV trial) and from
the DEV + HOLD files for chk and early (reports/hunt2/gamma/derived/gamma_hourly_hold.parquet; the DEV file only
matters for any sim warm-up minutes before an era's first day).

The steps of pathA.hold_read are run in separate processes, one era each (the shared machine's memory cgroup cannot
hold the simulator's three eras at once; a first single-process attempt was OOM-killed in the sel era before any
series was computed): `era <name>` runs X2/X1/S through pathA.run_mult for that era and saves the three daily series
(nothing is printed); `assemble` concatenates the eras in hold_read's order (sel, chk, early), de-duplicates the
index as hold_read does, writes daily.parquet (x2, x1, s) and calls h2gates.path_a -> gates.json (+ skip counts).
Each era process first waits until the memory cgroup has room for it.

usage: python scripts/hunt2/gamma/gamma_hold.py era sel|chk|early ;  python scripts/hunt2/gamma/gamma_hold.py assemble
"""
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamma as GM  # noqa: E402

PARTS = os.path.join(GM.OUT, "hold_parts")
NEED_GB = {"sel": 2.4, "chk": 2.0, "early": 3.0}


def _cg():
    for line in open("/proc/self/cgroup"):
        f = line.strip().split(":")
        if len(f) == 3 and f[1] == "memory":
            p = "/sys/fs/cgroup/memory" + f[2]
            if os.path.exists(os.path.join(p, "memory.limit_in_bytes")):
                return p
    return None


def wait_mem(need_gb, max_wait=4 * 3600):
    p = _cg()
    if p is None:
        return
    t0 = time.time()
    while True:
        lim = int(open(os.path.join(p, "memory.limit_in_bytes")).read())
        use = int(open(os.path.join(p, "memory.usage_in_bytes")).read())
        st = dict(line.split() for line in open(os.path.join(p, "memory.stat")))
        ws = use - int(st.get("total_inactive_file", 0))
        free_gb = (lim - ws) / 1e9
        if free_gb >= need_gb or time.time() - t0 > max_wait:
            print(f"memory headroom {free_gb:.2f} GB (need {need_gb}) after {time.time() - t0:.0f}s", flush=True)
            return
        time.sleep(15)


def frozen_hours():
    fz = json.load(open(os.path.join(GM.OUT, "frozen.json")))
    col, thr = fz["col"], float(fz["thr_value"])
    H_dev, H_hold = GM.signal("dev"), GM.signal("hold")
    H_all = pd.concat([H_dev, H_hold]).sort_index()
    hrs = {"sel": GM.skip_hours(H_dev, col, thr), "chk": GM.skip_hours(H_all, col, thr),
           "early": GM.skip_hours(H_all, col, thr)}
    return fz, col, thr, H_hold, hrs


def run_era(era):
    wait_mem(NEED_GB[era])
    fz, col, thr, H_hold, hrs = frozen_hours()
    m, n_min = GM.mult(era, hrs[era])
    n_skip, n_par = GM.n_skipped(era, hrs[era])
    out = {}
    for cost, k in (("X2", "x2"), ("X1", "x1"), ("S", "s")):
        out[k] = GM.pathA.run_mult(era, m, cost=cost)
        print(era, cost, "done", flush=True)
    os.makedirs(PARTS, exist_ok=True)
    pd.DataFrame(out).to_parquet(os.path.join(PARTS, f"{era}.parquet"))
    json.dump(dict(skip_minutes=n_min, parents=n_par, parents_skipped=n_skip,
                   frac_parents=n_skip / n_par if n_par else None),
              open(os.path.join(PARTS, f"{era}_info.json"), "w"))


def assemble():
    G = GM.pathA._gates()
    fz, col, thr, H_hold, hrs = frozen_hours()
    cols = {"x2": [], "x1": [], "s": []}
    info = {}
    for era in ("sel", "chk", "early"):
        P = pd.read_parquet(os.path.join(PARTS, f"{era}.parquet"))
        for k in cols:
            cols[k].append(P[k])
        info[era] = json.load(open(os.path.join(PARTS, f"{era}_info.json")))
    D = pd.DataFrame({k: pd.concat(v).sort_index() for k, v in cols.items()})
    D = D[~D.index.duplicated()]
    D.to_parquet(os.path.join(GM.OUT, "daily.parquet"))
    g = G.path_a(D["x2"], D["x1"], D.index)
    for era, (lo, hi) in (("chk", ("2026-04-01", "2026-11-06")), ("early", ("2022-01-01", "2024-01-01"))):
        sh = H_hold.loc[(H_hold.index >= lo) & (H_hold.index < hi), col]
        info[era].update(hours=len(sh), frac_hours_skipped=float((sh < thr).mean()))
    g["skips"] = info
    g["frozen_variant"] = fz["variant"]
    json.dump(g, open(os.path.join(GM.OUT, "gates.json"), "w"), indent=1, default=str)
    keys = ["A1", "A2", "A3", "A4", "pass", "hold_t_x2", "hold_mean_bp_x2", "hold_mean_bp_x1", "chk_mean_bp_x2",
            "early_mean_bp_x2", "chk_t_x2", "early_t_x2", "dev_t_x2", "years_x2", "dsr", "hold_dsharpe_x2"]
    print({k: g.get(k) for k in keys})
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "era":
        run_era(sys.argv[2])
    elif sys.argv[1] == "assemble":
        assemble()
