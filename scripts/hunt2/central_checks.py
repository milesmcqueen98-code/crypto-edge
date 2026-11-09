#!/usr/bin/env python3
"""Edge hunt 2: central checks of every build after its single HOLD read (descriptive; the gates are central_gates.py).

1. Path A, the skip cells reached the simulator in every era: days where the candidate differs from the incumbent
   (pathA.mult_for silently drops cells it cannot place, so a dtype slip would turn a filter into a no-op).
2. Path A, the HOLD run used the frozen rule: the DEV part of daily.parquet reproduces the DEV statistic the ledger
   logged for the frozen variant.
3. Path B, the alpha t with idle capital earning T-bills instead of 0% (descriptive): h2gates' convention books idle
   days at 0, so a sparse sleeve's excess return is -rf on most days and its residual variance is tiny, which pushes
   the gate B2 t far below zero whatever the trades did. Reported next to the gate value; it decides nothing.
4. Timing: each idea's DEV ledger rows were logged before its freeze commit, and its HOLD outputs came after it.
Writes reports/hunt2/central_checks.json.
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import h2gates as G  # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(ROOT, "reports", "hunt2")
IDEAS = ["who", "exh", "mac", "burn", "shape", "imp", "crowd", "gamma", "letf", "exp"]


def git(*a):
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True).stdout.strip()


def first_commit_time(path):
    """Author time (UTC) of the first commit that added `path` on the current branch."""
    out = git("log", "--diff-filter=A", "--format=%H %aI", "--", path).splitlines()
    if not out:
        return None, None
    h, t = out[-1].split(" ", 1)
    return h, pd.Timestamp(t).tz_convert("UTC")


def check_a(idea, D, L):
    days = pd.DatetimeIndex(D.index)
    era = G.era_of(days)
    inc = G.incumbent("X2", days=days)
    diff = D["x2"].reindex(days).fillna(0.0).to_numpy() - inc.to_numpy()
    out = {}
    for e in ("sel", "chk", "early"):
        m = era == e
        if m.any():
            out[f"{e}_days"] = int(m.sum())
            out[f"{e}_days_differ"] = int((np.abs(diff[m]) > 1e-12).sum())
            out[f"{e}_sum_diff_bp"] = float(1e4 * diff[m].sum())
    fz = json.load(open(os.path.join(OUT, idea, "frozen.json")))
    v = fz.get("variant")
    dev = G.dev_screen_a(D["x2"][G.is_dev(D.index)])
    out["dev_t_from_daily"] = dev["t_diff"]
    row = L[(L.idea == idea) & (L.variant.astype(str) == str(v)) & (L.stage == "dev")]
    out["dev_t_ledger"] = float(row.stat.iloc[-1]) if len(row) else None
    out["dev_t_match"] = bool(len(row) and abs(out["dev_t_ledger"] - dev["t_diff"]) < 1e-6)
    return out


def check_b(idea, D):
    days = pd.DatetimeIndex(D.index)
    g = json.load(open(os.path.join(OUT, idea, "gates.json")))
    if isinstance(g, list):
        g = g[0]
    a = g.get("a", 0.9)
    cap = int(round((1 - a) * G.CAPITAL))
    col = {25000: "s25_2x", 50000: "s50_2x", 75000: "s75_2x", 125000: "s125_2x"}[cap]
    rs = D[col].reindex(days).fillna(0.0)
    ri = G.incumbent("S", C=a * G.CAPITAL, days=days)
    rf = G.book.rf_daily(days).to_numpy()
    idle = (rs == 0).to_numpy()
    rs_rf = rs + np.where(idle, rf, 0.0)          # idle sleeve capital earns T-bills
    hold = G.is_hold(days)
    out = dict(a=a, sleeve_col=col, active_days=int((~idle).sum()), active_days_hold=int((~idle & hold).sum()))
    for name, m in (("dev", G.is_dev(days)), ("hold", hold)):
        out[f"{name}_t_alpha_gate"] = G.alpha_test(rs[m], ri[m])["t_alpha"]
        out[f"{name}_t_alpha_idle_rf"] = G.alpha_test(rs_rf[m], ri[m])["t_alpha"]
        x = rs[m & ~idle]
        out[f"{name}_trade_days"] = int(len(x))
        out[f"{name}_mean_trade_day_bp"] = float(1e4 * x.mean()) if len(x) else None
        out[f"{name}_t_trade_days"] = G.hac_t(x.to_numpy()) if len(x) > 2 else None
    return out


def main():
    L = pd.read_csv(G.LEDGER)
    L["time"] = pd.to_datetime(L["time"], utc=True)
    res = {}
    for idea in IDEAS:
        d = os.path.join(OUT, idea)
        if not os.path.exists(os.path.join(d, "daily.parquet")):
            res[idea] = dict(missing=True)
            continue
        D = pd.read_parquet(os.path.join(d, "daily.parquet"))
        D.index = pd.DatetimeIndex(D.index)
        r = check_a(idea, D, L) if "x2" in D.columns else check_b(idea, D)
        hf, tf = first_commit_time(f"reports/hunt2/{idea}/frozen.json")
        hg, tg = first_commit_time(f"reports/hunt2/{idea}/gates.json")
        rows = L[(L.idea == idea) & (L.stage == "dev")]
        r.update(freeze_commit=hf, freeze_time=str(tf), gates_commit=hg, gates_time=str(tg),
                 n_dev_trials=int(len(rows)), last_dev_trial=str(rows.time.max()) if len(rows) else None,
                 dev_trials_before_freeze=bool(tf is not None and len(rows) and rows.time.max() <= tf),
                 gates_after_freeze=bool(tf is not None and tg is not None and tg >= tf))
        res[idea] = r
    hf, tf = first_commit_time("reports/hunt2/parents/features_hold.csv")
    res["_features_hold"] = dict(commit=hf, time=str(tf))
    json.dump(res, open(os.path.join(OUT, "central_checks.json"), "w"), indent=1, default=str)
    for k, v in res.items():
        print(k, json.dumps({kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()}, default=str))


if __name__ == "__main__":
    main()
