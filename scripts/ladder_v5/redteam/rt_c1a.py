#!/usr/bin/env python3
"""Red team: C1a "deeper first" re-derived with my replay. Incumbent = policy engine, candidate = policy preempt
(a 6/8-sigma rung short of cash cancels the lowest-prediction 4-sigma bids and takes their holds; the 4-sigma bids
are re-allocated each minute from what is left), same machinery otherwise. Gates as pre-registered: G1 pooled paired
Newey-West t (5 lags) of daily candidate - incumbent over all three eras' days at S* theta 0.5 >= 2; G2 every era's
mean difference > 0 (S*, theta 0.5); G3 the same at theta 0.25; G4 base pooled mean > 0.
Worlds: "faithful" (my engine-faithful replay) and "hsim_like" (my emulation of hsim's modelling choices, which
reproduces the claim's incumbent), plus robustness variants of the faithful world.
usage: python scripts/ladder_v5/redteam/rt_c1a.py [world ...]
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rt_live as RL  # noqa: E402
import rt_matrix as MX  # noqa: E402
import fsim  # noqa: E402

CONFIGS = {"S_0.5": dict(theta=0.5, C=250e3, today=True, cost_mult=2.0),
           "S_0.25": dict(theta=0.25, C=250e3, today=True, cost_mult=2.0),
           "base_0.5": dict(theta=0.5, C=250e3, today=False, cost_mult=1.0),
           "cap_1M": dict(theta=0.5, C=1e6, today=True, cost_mult=2.0)}
WORLDS = {"faithful": (False, {}),
          "hsim_like": (True, dict(MX.HSIM, prio_mode=1)),
          "faithful_fill_order": (False, dict(prio_mode=1)),
          "faithful_no_market_check": (False, dict(mkt_check=False)),
          "faithful_newcoin_bids": ("newcoin", {})}


def stats_pair(inc, cand, C, era):
    si, sc = fsim.stats(inc, C, era), fsim.stats(cand, C, era)
    d = cand - inc
    return dict(inc_ret=si["ret_yr"], inc_sharpe=si["sharpe"], cand_ret=sc["ret_yr"], cand_sharpe=sc["sharpe"],
                d_ret=sc["ret_yr"] - si["ret_yr"], d_sharpe=sc["sharpe"] - si["sharpe"], mean_diff=float(d.mean()),
                t=float(fsim.nw_t(d)))


def run_world(world, configs=CONFIGS):
    MX.ensure_frozen()
    phantom, opts = WORLDS[world]
    out = {"world": world, "configs": {}}
    daily = {}
    t0 = time.time()
    arrs = {}
    for cfg, kw in configs.items():
        per, incs, cands = {}, [], []
        for era in fsim.ERAS:
            tag = fsim.ERAS[era][0]
            key = (era, kw["C"], kw["today"])
            if key not in arrs:
                arrs.clear()
                arrs[key] = RL.era_arrays(tag, era, kw["theta"], kw["C"], kw["today"], phantom=(phantom is True),
                                          newcoin=(phantom == "newcoin"))
            A = arrs[key]
            inc = RL.book(tag, era, theta=kw["theta"], C=kw["C"], cost_mult=kw["cost_mult"], policy="engine", A=A,
                          **opts)
            cand = RL.book(tag, era, theta=kw["theta"], C=kw["C"], cost_mult=kw["cost_mult"], policy="preempt", A=A,
                           **opts)
            per[era] = stats_pair(inc, cand, kw["C"], era)
            incs.append(inc)
            cands.append(cand)
            daily[f"{cfg}|{era}|inc"] = inc
            daily[f"{cfg}|{era}|cand"] = cand
            print(f"{world} {cfg} {era}: inc {per[era]['inc_ret']:.4f}/{per[era]['inc_sharpe']:.2f} cand "
                  f"{per[era]['cand_ret']:.4f}/{per[era]['cand_sharpe']:.2f} t {per[era]['t']:+.2f} "
                  f"({time.time() - t0:.0f}s)", flush=True)
        ai, ac = pd.concat(incs), pd.concat(cands)
        d = ac - ai
        out["configs"][cfg] = dict(eras=per, pooled_t=float(fsim.nw_t(d)), pooled_mean=float(d.mean()))
    c = out["configs"]
    g = {}
    if "S_0.5" in c:
        g["G1"] = c["S_0.5"]["pooled_t"] >= 2.0
        g["G2"] = all(e["mean_diff"] > 0 for e in c["S_0.5"]["eras"].values())
    if "S_0.25" in c:
        g["G3"] = c["S_0.25"]["pooled_t"] >= 2.0 and all(e["mean_diff"] > 0 for e in c["S_0.25"]["eras"].values())
    if "base_0.5" in c:
        g["G4"] = c["base_0.5"]["pooled_mean"] > 0
    g["pass"] = all(g.get(k, False) for k in ("G1", "G2", "G3", "G4"))
    out["gates"] = {k: bool(v) for k, v in g.items()}
    os.makedirs(RL.OUT, exist_ok=True)
    json.dump(out, open(os.path.join(RL.OUT, f"c1a_{world}.json"), "w"), indent=1, default=float)
    pd.DataFrame(daily).to_parquet(os.path.join(RL.OUT, f"c1a_daily_{world}.parquet"))
    print(json.dumps({cfg: dict(pooled_t=round(v["pooled_t"], 3)) for cfg, v in c.items()}), out["gates"], flush=True)
    return out


if __name__ == "__main__":
    for w in sys.argv[1:] or ["faithful", "hsim_like"]:
        run_world(w)
