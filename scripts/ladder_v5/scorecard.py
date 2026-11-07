#!/usr/bin/env python3
"""Ladder v5 scorecard (rubric fixed in reports/ladder_v5_prereg.md). Automatic parts from reports/ladder_v5/trials/
<name>.json (Evidence, Robustness, Prize, Capacity); hand parts (Realism, Mechanism, Implementation and risk) from
reports/ladder_v5/scorecard_manual.json with a reason each. Writes reports/ladder_v5/scorecard.csv."""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fsim  # noqa: E402

PAIRS = {"C1a_deeper_first": "C1b_reserve50", "C1b_reserve50": "C1a_deeper_first", "C2a_margin_terciles": "C2b_drop_bottom",
         "C2b_drop_bottom": "C2a_margin_terciles", "C3a_passive_5": "C3b_passive_15", "C3b_passive_15": "C3a_passive_5",
         "C7a_sweep_skip": "C7b_sweep_tilt", "C7b_sweep_tilt": "C7a_sweep_skip"}


def auto(o, allo):
    c, vm = o["configs"], o["path"] == "sharpe"
    key = "pooled_t_volmatched" if vm else "pooled_t"
    t = c["S_0.5"][key]
    ev = 25 if t >= 3 else 18 if t >= 2 else 8 if t >= 1 else 3 if t >= 0 else 0
    eras = c["S_0.5"]["era_means_volmatched"] if vm else {e: v["mean_diff"] for e, v in c["S_0.5"]["eras"].items()}
    npos = sum(1 for v in eras.values() if v > 0)
    r1 = 5 if npos == 3 else 3 if npos == 2 else 0
    t25 = c["S_0.25"][key]
    e25 = c["S_0.25"]["era_means_volmatched"] if vm else {e: v["mean_diff"] for e, v in c["S_0.25"]["eras"].items()}
    r2 = 5 if (t25 >= 2 and all(v > 0 for v in e25.values())) else 3 if t25 >= 1 else 0
    bm = c["base_0.5"]["pooled_mean_volmatched" if vm else "pooled_mean"]
    bt = c["base_0.5"][key]
    r3 = 5 if (bm > 0 and bt >= 1) else 3 if bm > 0 else 0
    other = allo.get(PAIRS.get(o["name"], ""))
    sgn = np.sign(t)
    if other is not None:
        so = np.sign(other["configs"]["S_0.5"]["pooled_t_volmatched" if other["path"] == "sharpe" else "pooled_t"])
    else:
        so = np.sign(c["cap_1M"][key]) if "cap_1M" in c else 0
    r4 = 5 if so == sgn and sgn != 0 else 2 if so == 0 else 0
    ds = np.mean([v["d_sharpe"] for v in c["S_0.5"]["eras"].values()])
    pz = 15 if ds >= 0.5 else 10 if ds >= 0.25 else 5 if ds >= 0.1 else 2 if ds > 0 else 0
    cap = np.mean([v["d_sharpe"] for v in c["cap_1M"]["eras"].values()]) if "cap_1M" in c else 0.0
    cp = 5 if cap >= 0.25 else 2 if cap >= 0 else 0
    return dict(evidence=ev, robustness=r1 + r2 + r3 + r4, prize=pz, capacity=cp, t=t, mean_dsharpe=ds, cap_dsharpe=cap)


def main():
    allo = {}
    for f in glob.glob(os.path.join(fsim.OUT, "trials", "*.json")):
        o = json.load(open(f))
        if o["name"].startswith("dryrun"):
            continue
        allo[o["name"]] = o
    man = json.load(open(os.path.join(fsim.OUT, "scorecard_manual.json"))) if os.path.exists(
        os.path.join(fsim.OUT, "scorecard_manual.json")) else {}
    rows = []
    for n, o in sorted(allo.items()):
        a = auto(o, allo)
        m = man.get(n, {})
        tot = a["evidence"] + a["robustness"] + a["prize"] + a["capacity"] + sum(m.get(k, 0) for k in ("realism", "mechanism", "implement"))
        rows.append(dict(name=n, total=tot, **a, **{k: m.get(k) for k in ("realism", "mechanism", "implement")},
                         gates_pass=o["gates"].get("pass"), why=m.get("why", "")))
    S = pd.DataFrame(rows).sort_values("total", ascending=False)
    S.to_csv(os.path.join(fsim.OUT, "scorecard.csv"), index=False)
    pd.set_option("display.width", 220)
    print(S.drop(columns=["why"]).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
