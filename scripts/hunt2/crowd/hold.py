#!/usr/bin/env python3
"""Edge hunt 2, CROWD: the single HOLD read of the frozen variant (AFTER the freeze commit only).

pathA.hold_read runs the frozen skip rule on every era at X2, X1 and S ($250K, theta 0.5) and writes daily.parquet
(x2, x1, s) and gates.json (h2gates.path_a) for the scored days: sel, chk, and early from 2023-05-13. The threshold is
frozen.json's DEV number (never recomputed). The multiplier arrays are built per era on demand, and the arrays of the
other eras are dropped from frozen_sim's cache first (as scripts/hunt2/incumbent.py does), so one era is in memory at a
time; nothing else in hold_read changes.
usage: python scripts/hunt2/crowd/hold.py
Also writes reports/hunt2/crowd/hold_info.json (parents skipped per era, coin-days skipped, years, top days).
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crowd as CW  # noqa: E402

F, pathA = CW.F, CW.pathA
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(WT, "reports", "hunt2", "crowd")


def committed(path):
    rel = os.path.relpath(path, WT)
    st = subprocess.run(["git", "-C", WT, "status", "--porcelain", rel], capture_output=True, text=True).stdout.strip()
    log = subprocess.run(["git", "-C", WT, "log", "--format=%H", "-1", "--", rel], capture_output=True, text=True).stdout
    return st == "" and log.strip() != ""


class LazyM(dict):
    """m_by_era for pathA.hold_read: builds an era's multiplier array when first asked, after dropping the other eras'
    arrays from frozen_sim's cache."""

    def __init__(self, v, thr, info):
        super().__init__()
        self.v, self.thr, self.info, self.cur = v, thr, info, (None, None)

    def get(self, era, default=None):
        if self.cur[0] == era:
            return self.cur[1]
        self.cur = (None, None)
        for key in list(F._A):
            if key[0] != era:
                del F._A[key]
        with pathA.cpu_slot():
            F.arrays(era)
        sk = CW.skip_frame(era, self.v, self.thr, allow_hold=True)
        ns, npar = CW.n_skipped(era, sk, allow_hold=True)
        self.info[era] = dict(n_skipped=ns, n_parents=npar, skip_share=ns / npar if npar else np.nan,
                              coin_days_skipped=int(sk.to_numpy().sum()), days_skipped=int(sk.any(axis=1).sum()),
                              era_days=int(len(sk)))
        m = CW.mult(era, sk)
        self.cur = (era, m)
        return m


def main():
    fzp = os.path.join(OUT, "frozen.json")
    assert committed(fzp), "frozen.json is not committed: no HOLD read before the freeze"
    fz = json.load(open(fzp))
    p = fz["params"]
    v = dict(src=p["source"], stat=p["statistic"], thr=p["threshold_kind"])
    thr = float(p["threshold"])
    info = {}
    days = pd.DatetimeIndex(sorted(set().union(*[set(pd.date_range(*CW.ERA_DAYS[e], freq="D")) for e in CW.ERA_DAYS])))
    g = pathA.hold_read("crowd", None, OUT, days=days, m_by_era=LazyM(v, thr, info))
    D = pd.read_parquet(os.path.join(OUT, "daily.parquet"))
    G = pathA._gates()
    inc2 = G.incumbent("X2", days=D.index)
    d = G.excess(D["x2"]) - G.excess(inc2)
    info["years_diff_x2_pct"] = {int(y): float(100 * x) for y, x in d.groupby(d.index.year).sum().items()}
    info["era_diff_sum_x2_pct"] = {e: float(100 * d[G.era_of(d.index) == e].sum()) for e in ("sel", "chk", "early")}
    info["top5_days_x2"] = {str(k.date()): float(1e4 * x) for k, x in d.nlargest(5).items()}
    info["bottom5_days_x2"] = {str(k.date()): float(1e4 * x) for k, x in d.nsmallest(5).items()}
    info["threshold"] = thr
    json.dump(info, open(os.path.join(OUT, "hold_info.json"), "w"), indent=1, default=str)
    keys = ("hold_t_x2", "hold_mean_bp_x2", "hold_mean_bp_x1", "chk_mean_bp_x2", "early_mean_bp_x2", "chk_t_x2",
            "early_t_x2", "dev_t_x2", "full_t_x2", "dsr", "years_x2", "A1", "A2", "A3", "A4", "pass")
    print(json.dumps({k: g.get(k) for k in keys}, indent=1, default=str))
    print(json.dumps(info, indent=1, default=str))


if __name__ == "__main__":
    main()
