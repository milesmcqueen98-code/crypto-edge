#!/usr/bin/env python3
"""Ladder v5 scorecard (rubric fixed in reports/ladder_v5_prereg.md). Automatic parts from reports/ladder_v5/trials/
<name>.json (Evidence, Robustness, Prize, Capacity); hand parts (Realism, Mechanism, Implementation and risk) from
reports/ladder_v5/scorecard_manual.json with a reason each. Writes reports/ladder_v5/scorecard.csv.

--adjusted: the same rubric after the red teams. Where a red team recomputed a candidate with better inputs
(reports/ladder_v5/redteam_records/<name>.json: C1a on red team 1's engine-faithful replay; C2a, C3a, C3b with red
team 2's print-measured exit costs and fills; C4 with red team 3's Kraken USDC marks), the automatic parts use that
record; hand parts from scorecard_manual_adjusted.json. Writes reports/ladder_v5/scorecard_adjusted.csv."""
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


def _md(v):
    """An era's mean difference; a record that rounded it to zero gives its sign through the era t."""
    m = v["mean_diff"]
    return m if abs(m) > 1e-12 or not np.isfinite(v.get("t", np.nan)) else 1e-12 * np.sign(v["t"])


def auto(o, allo):
    c, vm = o["configs"], o.get("path", "return") == "sharpe"
    key = "pooled_t_volmatched" if vm else "pooled_t"
    t = c["S_0.5"][key]
    ev = 25 if t >= 3 else 18 if t >= 2 else 8 if t >= 1 else 3 if t >= 0 else 0
    eras = c["S_0.5"]["era_means_volmatched"] if vm else {e: _md(v) for e, v in c["S_0.5"]["eras"].items()}
    npos = sum(1 for v in eras.values() if v > 0)
    r1 = 5 if npos == 3 else 3 if npos == 2 else 0
    t25 = c["S_0.25"][key]
    e25 = c["S_0.25"]["era_means_volmatched"] if vm else {e: _md(v) for e, v in c["S_0.25"]["eras"].items()}
    r2 = 5 if (t25 >= 2 and all(v > 0 for v in e25.values())) else 3 if t25 >= 1 else 0
    bm = c["base_0.5"]["pooled_mean_volmatched" if vm else "pooled_mean"]
    if abs(bm) < 1e-12 and np.isfinite(c["base_0.5"][key]):
        bm = 1e-12 * np.sign(c["base_0.5"][key])
    bt = c["base_0.5"][key]
    r3 = 5 if (bm > 0 and bt >= 1) else 3 if bm > 0 else 0
    other = allo.get(PAIRS.get(o["name"], ""))
    sgn = np.sign(t)
    if other is not None:
        so = np.sign(other["configs"]["S_0.5"]["pooled_t_volmatched" if other.get("path") == "sharpe" else "pooled_t"])
    else:
        so = np.sign(c["cap_1M"][key]) if "cap_1M" in c else 0
    r4 = 5 if so == sgn and sgn != 0 else 2 if so == 0 else 0
    ds = np.mean([v["d_sharpe"] for v in c["S_0.5"]["eras"].values()])
    pz = 15 if ds >= 0.5 else 10 if ds >= 0.25 else 5 if ds >= 0.1 else 2 if ds > 0 else 0
    cap = np.mean([v["d_sharpe"] for v in c["cap_1M"]["eras"].values()]) if "cap_1M" in c else 0.0
    cp = 5 if cap >= 0.25 else 2 if cap >= 0 else 0
    return dict(evidence=ev, robustness=r1 + r2 + r3 + r4, prize=pz, capacity=cp, t=t, mean_dsharpe=ds, cap_dsharpe=cap)


def main(adjusted=False):
    allo = {}
    for f in glob.glob(os.path.join(fsim.OUT, "trials", "*.json")):
        o = json.load(open(f))
        if o["name"].startswith(("dryrun", "J_")):            # joint re-tests are reported on their own
            continue
        allo[o["name"]] = o
    if adjusted:
        for f in glob.glob(os.path.join(fsim.OUT, "redteam_records", "*.json")):
            o = json.load(open(f))
            o.setdefault("gates", allo.get(o["name"], {}).get("gates", {}))
            allo[o["name"]] = o
    mf = os.path.join(fsim.OUT, "scorecard_manual_adjusted.json" if adjusted else "scorecard_manual.json")
    man = json.load(open(mf)) if os.path.exists(mf) else {}
    rows = []
    for n, o in sorted(allo.items()):
        a = auto(o, allo)
        m = man.get(n, {})
        tot = a["evidence"] + a["robustness"] + a["prize"] + a["capacity"] + sum(m.get(k, 0) for k in ("realism", "mechanism", "implement"))
        rows.append(dict(name=n, total=tot, **a, **{k: m.get(k) for k in ("realism", "mechanism", "implement")},
                         gates_pass=o["gates"].get("pass"), why=json.dumps(m.get("why", ""))))
    S = pd.DataFrame(rows).sort_values("total", ascending=False)
    S.to_csv(os.path.join(fsim.OUT, "scorecard_adjusted.csv" if adjusted else "scorecard.csv"), index=False)
    pd.set_option("display.width", 220)
    print(S.drop(columns=["why"]).round(2).to_string(index=False))


if __name__ == "__main__":
    main(adjusted="--adjusted" in sys.argv)
