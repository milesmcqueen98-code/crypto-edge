#!/usr/bin/env python3
"""Edge hunt 2: recompute every idea's gates centrally, once, with the final trial ledger (reports/hunt2_prereg.md).

Reads reports/hunt2/<id>/daily.parquet and frozen.json for each idea:
  Path A: columns x2, x1 (the frozen candidate's daily returns on $250K at X2 / X1, indexed by its scored days)
  Path B: columns s25_2x, s50_2x, s75_2x, s125_2x (sleeve daily returns on that capital at 2x), plus *_1x
Writes reports/hunt2/central_gates.csv and central_gates.json.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import h2gates as G  # noqa: E402

OUT = os.path.join(G.ROOT, "reports", "hunt2")


def one(idea_dir):
    fz = json.load(open(os.path.join(idea_dir, "frozen.json")))
    D = pd.read_parquet(os.path.join(idea_dir, "daily.parquet"))
    D.index = pd.DatetimeIndex(D.index)
    days = D.index[np.isin(G.era_of(D.index), list(G.ERAS))]
    path = fz.get("path", "A" if "x2" in D.columns else "B")
    if path == "A":
        g = G.path_a(D["x2"], D["x1"], days)
    else:
        caps = {25000: "s25_2x", 50000: "s50_2x", 75000: "s75_2x", 125000: "s125_2x"}
        g = G.path_b({c: D[col] for c, col in caps.items()}, days)
        if "s50_1x" in D:
            g1 = G.path_b({c: D[col.replace("_2x", "_1x")] for c, col in caps.items()}, days)
            g["hold_gain_1x"], g["full_gain_1x"] = g1.get("hold_gain"), g1.get("full_gain")
    g["idea"] = os.path.basename(idea_dir)
    g["variant"] = fz.get("variant")
    g["scored_days"] = len(days)
    return g


def main():
    rows = []
    for d in sorted(glob.glob(os.path.join(OUT, "*", "frozen.json"))):
        idir = os.path.dirname(d)
        if not os.path.exists(os.path.join(idir, "daily.parquet")):
            continue
        try:
            rows.append(one(idir))
        except Exception as e:  # noqa: BLE001
            rows.append(dict(idea=os.path.basename(idir), error=repr(e)))
    json.dump(rows, open(os.path.join(OUT, "central_gates.json"), "w"), indent=1, default=str)
    flat = [{k: v for k, v in r.items() if not isinstance(v, (dict, list))} for r in rows]
    pd.DataFrame(flat).to_csv(os.path.join(OUT, "central_gates.csv"), index=False)
    for r in flat:
        print(r.get("idea"), r.get("path"), "PASS" if r.get("pass") else "fail",
              {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
               if k in ("hold_t_x2", "hold_mean_bp_x2", "hold_gain", "hold_t_alpha", "dsr", "a")})


if __name__ == "__main__":
    main()
