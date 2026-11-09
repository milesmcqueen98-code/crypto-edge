#!/usr/bin/env python3
"""MAC and BURN, after their HOLD reads: the reported-only diagnostics of mac.py / burn.py `post` (theta 0.25 at S, S and
X1 differences, calendar years, the incumbent's ten worst DEV days, the busy-rule side effect of the SKIP hook), run one
era per process so the shared machine's memory is not exhausted (two HOLD runs were OOM-killed). Same frozen rules
(mac.mult, burn.mult) and the same statistics as their `post`.
usage: python scripts/hunt2/burn/post_lowmem.py <mac|burn> <sel|chk|early>   (one era: theta 0.25 series, busy count)
       python scripts/hunt2/burn/post_lowmem.py <mac|burn> assemble         (post.json, years.csv, daily_theta025)
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "mac"))


def frozen_mult(X, fz, era):
    p = fz["params"]
    if X.__name__ == "mac":
        return X.mult(era, p["a"], p["b"], p["events"])
    return X.mult(era, p["m"], p["C_hours"], p["scope"])[0]


def one_era(X, era):
    fz, _ = X.assert_frozen()
    F = X.F
    m = frozen_mult(X, fz, era)
    sk = pd.read_csv(os.path.join(X.OUT, f"skipped_{era}.csv"), parse_dates=["ts"])
    nb = X.busy_blocked(era, sk)
    F._A.clear()
    with X.pathA.cpu_slot():
        c25 = F.daily(era, 0.25, 250e3, "S", mfac=m)
    d = os.path.join(X.OUT, "post_parts")
    os.makedirs(d, exist_ok=True)
    c25.to_frame("s_theta025").to_parquet(os.path.join(d, f"theta025_{era}.parquet"))
    json.dump(dict(era=era, busy_blocked=nb), open(os.path.join(d, f"busy_{era}.json"), "w"))
    print(era, "busy_blocked", nb, "theta 0.25 days", len(c25))


def assemble(X):
    fz, _ = X.assert_frozen()
    G = X.G
    D = pd.read_parquet(os.path.join(X.OUT, "daily.parquet"))
    days = pd.DatetimeIndex(D.index)
    era = G.era_of(days)
    res = dict(variant=fz["variant"])
    d = os.path.join(X.OUT, "post_parts")
    c25 = pd.concat([pd.read_parquet(os.path.join(d, f"theta025_{e}.parquet")).s_theta025
                     for e in ("sel", "chk", "early")]).sort_index()
    for e in ("sel", "chk", "early"):
        res[f"busy_blocked_{e}"] = json.load(open(os.path.join(d, f"busy_{e}.json")))["busy_blocked"]
    c25 = c25[~c25.index.duplicated()].reindex(days).fillna(0.0)
    D["s_theta025"] = c25
    i25 = G.incumbent("S", theta=0.25, days=days)
    iS, i2, i1 = (G.incumbent(c, days=days) for c in ("S", "X2", "X1"))
    diffs = {"theta025_S": G.excess(c25) - G.excess(i25), "S": G.excess(D.s) - G.excess(iS),
             "X2": G.excess(D.x2) - G.excess(i2), "X1": G.excess(D.x1) - G.excess(i1)}
    for k, dd in diffs.items():
        for e, mk in (("hold", G.is_hold(days)), ("sel", era == "sel"), ("chk", era == "chk"),
                      ("early", era == "early")):
            res[f"{k}_{e}_mean_bp"] = 1e4 * float(dd[mk].mean())
            res[f"{k}_{e}_t"] = G.hac_t(dd[mk])
    Y = pd.DataFrame({"cand_x2": G.years(D.x2), "inc_x2": G.years(i2), "cand_x1": G.years(D.x1),
                      "inc_x1": G.years(i1), "cand_s": G.years(D.s), "inc_s": G.years(iS)})
    Y["diff_x2"] = Y.cand_x2 - Y.inc_x2
    Y.round(5).to_csv(os.path.join(X.OUT, "years.csv"))
    dev_m = G.is_dev(days)
    w = iS[dev_m].nsmallest(10).index
    res["worst10_dev_days"] = [str(x.date()) for x in w]
    res["worst10_dev_diff_S_bp"] = 1e4 * float((D.s - iS)[w].sum())
    res["worst10_dev_diff_X2_bp"] = 1e4 * float((D.x2 - i2)[w].sum())
    D[["s_theta025"]].to_parquet(os.path.join(X.OUT, "daily_theta025.parquet"))
    json.dump(res, open(os.path.join(X.OUT, "post.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))
    print(Y.round(4).to_string())


if __name__ == "__main__":
    idea, what = sys.argv[1], sys.argv[2]
    X = __import__(idea)
    assemble(X) if what == "assemble" else one_era(X, what)
