#!/usr/bin/env python3
"""Edge hunt 2, SHAPE and IMP: descriptive diagnostics of the frozen variants, AFTER their HOLD reads (reported in
the REPORTs, never used to change anything).

usage: python scripts/hunt2/shape/diag.py all <tmp_dir>
Writes reports/hunt2/<idea>/diag.json with, per era:
  - the mean daily difference (bp of $250K) and HAC t at cost setting S (candidate S - incumbent S; X2/X1 are in
    gates.json);
  - the frozen dataset's research gross outcome (lab_gross, bp) of the skipped vs the kept parents (did the filter pick
    the worse fills?);
  - theta 0.25 at S (the prereg's reported-only setting; the incumbent exists at S for theta 0.25), one subprocess per
    era (memory).
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/home/claude/crypto-edge/scripts/hunt2")
import shp_rules as rules  # noqa: E402

ERAS = ("sel", "chk", "early")
BOUNDS = {"sel": ("2025-01-01", "2026-03-31"), "chk": ("2026-04-01", "2026-11-05"), "early": ("2022-01-01", "2023-12-31")}
TAG = {"sel": "main", "chk": "main", "early": "early"}


def out_dir(idea):
    return os.path.join(rules.WT, "reports", "hunt2", idea)


def frozen_cells(idea, era):
    rules.require_frozen(idea, era)
    fz = json.load(open(os.path.join(out_dir(idea), "frozen.json")))
    F = pd.read_csv(os.path.join(out_dir(idea), f"features_{era}.csv"), parse_dates=["ts"])
    m = rules.skip_mask(F[fz.get("col", fz["feature"])], fz["side"], fz["thr"])
    return F, m


def theta25_era(idea, era, out):
    import pathA
    F, m = frozen_cells(idea, era)
    cells = F.loc[m, ["ts", "coin"]].reset_index(drop=True)
    d = pathA.run_cells(era, cells, cost="S", theta=0.25)
    d.rename("s25").to_frame().to_parquet(out)


def lab_outcomes(idea, era):
    F, m = frozen_cells(idea, era)
    P = pd.read_pickle(f"/home/claude/crypto-edge/reports/ladder_v5/frozen/pre_hunt_{TAG[era]}.pkl")
    lo, hi = BOUNDS[era]
    P = P[(P.k == 4.0) & P.filled & (P.ts >= lo) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]
    J = F[["ts", "coin"]].assign(skip=m).merge(P[["ts", "coin", "lab_gross"]], on=["ts", "coin"], how="left")
    assert J.lab_gross.notna().all()
    s, k = J[J.skip].lab_gross, J[~J.skip].lab_gross
    return dict(n_skip=int(len(s)), n_keep=int(len(k)), gross_skip_bp=float(s.mean()), gross_keep_bp=float(k.mean()),
                hit_skip=float((s > 0).mean()), hit_keep=float((k > 0).mean()))


def all_(tmp):
    import h2gates as G
    os.makedirs(tmp, exist_ok=True)
    for idea in ("shape", "imp"):
        D = pd.read_parquet(os.path.join(out_dir(idea), "daily.parquet"))
        D.index = pd.DatetimeIndex(D.index)
        res = {}
        for era in ERAS:
            days = D.index[G.era_of(D.index) == era]
            dS = G.excess(D.s.reindex(days)) - G.excess(G.incumbent("S", days=days))
            p = os.path.join(tmp, f"{idea}_{era}_t25.parquet")
            if not os.path.exists(p):
                subprocess.run([sys.executable, "-u", os.path.abspath(__file__), "theta25-era", idea, era, p],
                               check=True)
            s25 = pd.read_parquet(p)["s25"]
            s25.index = pd.DatetimeIndex(s25.index)
            s25 = s25.reindex(days).fillna(0.0)
            d25 = G.excess(s25) - G.excess(G.incumbent("S", theta=0.25, days=days))
            res[era] = dict(S_mean_bp=1e4 * float(dS.mean()), S_t=G.hac_t(dS), theta25_S_mean_bp=1e4 * float(d25.mean()),
                            theta25_S_t=G.hac_t(d25), cand_theta25_S_sharpe=G.sharpe(s25),
                            inc_theta25_S_sharpe=G.sharpe(G.incumbent("S", theta=0.25, days=days)),
                            **lab_outcomes(idea, era))
        hold = D.index[G.is_hold(D.index)]
        dS = G.excess(D.s.reindex(hold)) - G.excess(G.incumbent("S", days=hold))
        res["hold"] = dict(S_mean_bp=1e4 * float(dS.mean()), S_t=G.hac_t(dS))
        json.dump(res, open(os.path.join(out_dir(idea), "diag.json"), "w"), indent=1)
        print(idea, json.dumps(res, indent=1), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "theta25-era":
        theta25_era(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "all":
        all_(sys.argv[2])
