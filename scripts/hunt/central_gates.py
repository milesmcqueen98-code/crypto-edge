#!/usr/bin/env python3
"""Edge hunt: central recomputation of every idea's gates from its daily series and the FINAL trial ledger.

Why: each builder computed G4 (deflated Sharpe) with the ledger as it stood when it ran, so early ideas saw a
smaller N. This script recomputes G1-G5 for every idea that reached the gates, from its committed daily.parquet
(s30_2x, s50_2x), with:
- N = 3000 prior trials + every trial in reports/hunt/trials.csv at the time this runs;
- vz robust (binding, deviation log 2026-11-07 06:00 UTC) and vz plain (the pre-registered variance), both shown.
It also checks the builder's own numbers: any gap above 0.01 in a t or Sharpe is flagged.

usage: python scripts/hunt/central_gates.py [ideas ...]   (default: every idea with a gates.json that has G1)
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import gates  # noqa: E402

WT = "/home/claude/wt"


def idea_dir(i):
    for base in (os.path.join(WT, i, "reports", "hunt", i), os.path.join(ROOT, "reports", "hunt", i)):
        if os.path.exists(os.path.join(base, "gates.json")):
            return base
    return None


def gates2x(G):
    """The 2x-cost Path B gate dict, wherever the builder put it (top level, gates_2x or path_b_2x)."""
    for k in ("gates_2x", "path_b_2x", "2x"):
        if isinstance(G.get(k), dict) and "full_t_alpha" in G[k]:
            return G[k]
    return G


def recompute(i):
    d = idea_dir(i)
    G = gates2x(json.load(open(os.path.join(d, "gates.json"))))
    if G.get("G1") is None or not os.path.exists(os.path.join(d, "daily.parquet")):
        return dict(idea=i, evaluated=False, note=G.get("result", "no full-window gates"))
    D = pd.read_parquet(os.path.join(d, "daily.parquet"))
    D.index = pd.to_datetime(D.index)
    sl = {30000: D["s30_2x"].astype(float), 50000: D["s50_2x"].astype(float)}
    days = pd.DatetimeIndex(sorted(set(D.index) & set(pd.DatetimeIndex(gates.ERA_DAYS))))   # the idea's scored days
    R = gates.path_b(sl, days=days)
    # plain-variance DSR on the same book
    a = R["a"]
    ri = gates.incumbent(a * 100e3, days=days)
    rs = sl[int(round((1 - a) * 100e3))].reindex(days).fillna(0.0)
    bk = a * ri + (1 - a) * rs
    N, v_plain = gates.n_trials(robust=False)
    dsr_plain, sr0_plain = gates.deflated_sharpe(bk, N, v_plain)
    _, v_pool = gates.n_trials(robust="pooled")
    dsr_pooled, sr0_pooled = gates.deflated_sharpe(bk, N, v_pool)
    N2, v_rob = gates.n_trials(robust=True)
    out = dict(idea=i, evaluated=True, n_days=len(days), first_day=str(days[0].date()), a=a, a_builder=G.get("a"),
               full_t_alpha=R["full_t_alpha"], full_t_alpha_builder=G.get("full_t_alpha"),
               hold_t_alpha=R["hold_t_alpha"], hold_t_alpha_builder=G.get("hold_t_alpha"),
               hold_gain=R["hold_gain"], hold_gain_builder=G.get("hold_gain"),
               full_gain=R["full_gain"], full_gain_builder=G.get("full_gain"),
               full_book_sharpe=R["full_book_sharpe"], full_inc_sharpe=R["full_inc_sharpe"],
               full_sleeve_sharpe=R["full_sleeve_sharpe"],
               dsr_robust=R["dsr"], sr0_robust_ann=R["sr0_ann"], vz_robust=v_rob,
               dsr_plain=dsr_plain, sr0_plain_ann=sr0_plain, vz_plain=v_plain,
               dsr_pooled=dsr_pooled, sr0_pooled_ann=sr0_pooled, vz_pooled=v_pool,
               dsr_builder=G.get("dsr"), n_trials=N,
               G1=R["G1"], G2=R["G2"], G3=R["G3"], G4_robust=R["G4"], G4_pooled=dsr_pooled >= 0.95,
               G4_plain=dsr_plain >= 0.95, G5=R["G5"],
               years=R["years"])
    out["pass_robust"] = all(out[g] for g in ("G1", "G2", "G3", "G4_robust", "G5"))
    out["pass_plain"] = all(out[g] for g in ("G1", "G2", "G3", "G4_plain", "G5"))
    flags = []
    for k in ("full_t_alpha", "hold_t_alpha", "hold_gain", "full_gain"):
        b = out.get(f"{k}_builder")
        if b is not None and np.isfinite(b) and abs(out[k] - b) > 0.01:
            flags.append(f"{k}: central {out[k]:.3f} vs builder {b:.3f}")
    if out["a_builder"] is not None and abs(out["a"] - out["a_builder"]) > 1e-9:
        flags.append(f"a: central {out['a']} vs builder {out['a_builder']}")
    out["mismatch"] = "; ".join(flags)
    return out


def main(ideas):
    rows = [recompute(i) for i in ideas]
    S = pd.DataFrame(rows)
    os.makedirs(os.path.join(ROOT, "reports", "hunt"), exist_ok=True)
    S.to_csv(os.path.join(ROOT, "reports", "hunt", "central_gates.csv"), index=False)
    with open(os.path.join(ROOT, "reports", "hunt", "central_gates.json"), "w") as f:
        json.dump(rows, f, indent=1, default=float)
    cols = ["idea", "n_days", "a", "full_t_alpha", "hold_t_alpha", "hold_gain", "full_gain", "full_book_sharpe",
            "dsr_robust", "sr0_robust_ann", "dsr_pooled", "dsr_plain", "G1", "G2", "G3", "G4_robust", "G4_pooled",
            "G4_plain", "G5", "pass_robust", "pass_plain", "mismatch"]
    with pd.option_context("display.width", 250, "display.max_colwidth", 80):
        print(S[[c for c in cols if c in S]].round(3).to_string(index=False))
    N, vr = gates.n_trials(True)
    _, vq = gates.n_trials("pooled")
    _, vp = gates.n_trials(False)
    print(f"N = {N}; vz within-idea robust (binding) {vr:.3f}, pooled robust {vq:.3f}, plain {vp:.3f}")
    return S


if __name__ == "__main__":
    ids = sys.argv[1:] or sorted({os.path.basename(os.path.dirname(p)) for p in
                                  glob.glob(os.path.join(WT, "*", "reports", "hunt", "h*", "gates.json"))})
    main(ids)
