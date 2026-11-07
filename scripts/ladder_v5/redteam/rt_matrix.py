#!/usr/bin/env python3
"""Red team: the live book under my engine-faithful replay and under each modelling choice that differs from it
(hsim's choices and other artifact tests), one at a time and all together.
usage: python scripts/ladder_v5/redteam/rt_matrix.py <config> [era ...]   config: base | S_0.5 | S_0.25 | base_1M | cap_1M
Writes reports/ladder_v5/redteam/matrix_<config>.csv and daily returns to reports/ladder_v5/redteam/daily_<config>.parquet
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rt_live as RL  # noqa: E402
import fsim  # noqa: E402

CONFIGS = {"base": dict(theta=0.5, C=250e3, today=False, cost_mult=1.0),
           "base_1M": dict(theta=0.5, C=1e6, today=False, cost_mult=1.0),
           "S_0.5": dict(theta=0.5, C=250e3, today=True, cost_mult=2.0),
           "S_0.25": dict(theta=0.25, C=250e3, today=True, cost_mult=2.0),
           "cap_1M": dict(theta=0.5, C=1e6, today=True, cost_mult=2.0)}
HSIM = dict(rem_hold=False, rel_shift=1, busy_mode=1, mkt_check=False, inst_retry_old=False, interleave=False)
VARIANTS = [
    ("engine", "engine", False, {}),
    ("nocash", "nocash", False, {}),
    ("phantom_bids", "engine", True, {}),
    ("no_remainder_hold", "engine", False, dict(rem_hold=False)),
    ("release_1min_early", "engine", False, dict(rel_shift=1)),
    ("busy_at_touch", "engine", False, dict(busy_mode=1)),
    ("no_market_check", "engine", False, dict(mkt_check=False)),
    ("no_instant_retry_old", "engine", False, dict(inst_retry_old=False)),
    ("no_interleave", "engine", False, dict(interleave=False)),
    ("hsim_like_no_phantom", "engine", False, HSIM),
    ("hsim_like", "engine", True, HSIM),
    ("hsim_like_fill_order", "engine", True, dict(HSIM, prio_mode=1)),
    ("hsim_like_no_phantom_fill_order", "engine", False, dict(HSIM, prio_mode=1)),
    ("release_all_at_60", "engine", False, dict(tp_release=False)),
    ("alloc_before_deeper", "engine", False, dict(alloc_first=True)),
    ("priority_fill_time", "engine", False, dict(prio_mode=1)),
    ("no_late_fills", "engine", False, dict(late_fills=False)),
    ("no_busy_rule", "engine", False, dict(busy_on=False)),
]


def ensure_frozen():
    """fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl (gitignored): copy the frozen pickles there, hash-checked."""
    import hashlib
    import shutil
    fz = os.path.join(fsim.ROOT, "reports", "ladder_v5", "frozen")
    sums = {}
    for line in open(os.path.join(fz, "SHA256SUMS")):
        h, f = line.split()
        sums[os.path.basename(f)] = h
    for tag in ("main", "early"):
        name = f"pre_hunt_{tag}.pkl"
        src, dst = os.path.join(fz, name), os.path.join(fsim.ROOT, "reports", "wick1m", name)
        assert hashlib.sha256(open(src, "rb").read()).hexdigest() == sums[name], name
        if not os.path.exists(dst) or hashlib.sha256(open(dst, "rb").read()).hexdigest() != sums[name]:
            shutil.copyfile(src, dst)


def main(cfg, eras, variants=None):
    ensure_frozen()
    kw = CONFIGS[cfg]
    rows, daily = [], {}
    t0 = time.time()
    for era in eras:
        tag = fsim.ERAS[era][0]
        P = RL.inputs(tag)["P"]
        dres, _ = fsim.book(P, era, theta=kw["theta"], C=kw["C"], today=kw["today"], cost_mult=kw["cost_mult"])
        daily[(era, "research")] = dres
        sr = fsim.stats(dres, kw["C"], era)
        rows.append(dict(era=era, variant="research", ret=sr["ret_yr"], sharpe=sr["sharpe"], t_vs_research=np.nan,
                         t_vs_engine=np.nan))
        arrs = {}
        for name, pol, phantom, opts in VARIANTS:
            if variants and name not in variants:
                continue
            if phantom not in arrs:
                arrs[phantom] = RL.era_arrays(tag, era, kw["theta"], kw["C"], kw["today"], phantom=phantom)
            A = arrs[phantom]
            d, out, _ = RL.book(tag, era, theta=kw["theta"], C=kw["C"], cost_mult=kw["cost_mult"], policy=pol, A=A,
                                detail=True, **opts)
            daily[(era, name)] = d
            st = fsim.stats(d, kw["C"], era)
            Rm, Ri = out["minute"][1], out["instant"][1]
            row = dict(era=era, variant=name, ret=st["ret_yr"], sharpe=st["sharpe"],
                       t_vs_research=fsim.nw_t(d - dres),
                       t_vs_engine=fsim.nw_t(d - daily[(era, "engine")]) if (era, "engine") in daily else np.nan,
                       ret_minute=fsim.stats(out["minute"][0], kw["C"], era)["ret_yr"],
                       ret_instant=fsim.stats(out["instant"][0], kw["C"], era)["ret_yr"],
                       parents_unfunded=int((Rm["a4"] <= 0).sum()),
                       parents_partial=int(((Rm["a4"] > 0) & (Rm["a4"] < A["p_want"] * (1 - 1e-6))).sum()),
                       deeper_filled_minute=int((Rm["r_state"] == 2).sum()),
                       deeper_filled_instant=int((Ri["r_state"] == 2).sum()),
                       fillcheck=max(RL.check_fills(A, Rm, out["minute"][2], kw["theta"]),
                                     RL.check_fills(A, Ri, out["instant"][2], kw["theta"])))
            rows.append(row)
            print(f"{cfg} {era} {name:22s} {row['ret']:.4f} / {row['sharpe']:.3f}  t vs research "
                  f"{row['t_vs_research']:+.2f}  unfunded {row['parents_unfunded']}  ({time.time() - t0:.0f}s)",
                  flush=True)
        del arrs
    df = pd.DataFrame(rows)
    os.makedirs(RL.OUT, exist_ok=True)
    df.to_csv(os.path.join(RL.OUT, f"matrix_{cfg}.csv"), index=False)
    D = pd.DataFrame({f"{e}|{v}": s for (e, v), s in daily.items()})
    D.to_parquet(os.path.join(RL.OUT, f"daily_{cfg}.parquet"))
    return df


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "base"
    main(cfg, sys.argv[2:] or list(fsim.ERAS))
