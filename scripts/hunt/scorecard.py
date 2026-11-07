#!/usr/bin/env python3
"""Edge hunt: the weighted 100-point scorecard (weights fixed in reports/hunt_prereg.md).

Computed from each idea's gates.json and daily.parquet:
- out-of-sample (20)
- statistical strength (20)
- 2x-cost years (5 of robustness)
- concentration (5 of robustness)
- diversification (5)

Judged by hand, with written reasons, in reports/hunt/scorecard_manual.json:
- neighbouring settings (5 of robustness)
- fill and cost realism (15)
- mechanism (10)
- implementability (10)
- capacity (5)

The gates decide pass or fail; the score ranks and explains.

usage: python scripts/hunt/scorecard.py [ideas ...]   (default: every idea with a SPEC)
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
MANUAL = os.path.join(ROOT, "reports", "hunt", "scorecard_manual.json")


def idea_dir(i):
    for base in (os.path.join(WT, i, "reports", "hunt", i), os.path.join(ROOT, "reports", "hunt", i)):
        if os.path.exists(os.path.join(base, "SPEC.md")):
            return base
    return None


def auto_scores(i):
    d = idea_dir(i)
    out = dict(idea=i, oos=0.0, stats=0.0, rob_years=0.0, rob_conc=0.0, divers=0.0, notes=[])
    gj = os.path.join(d, "gates.json") if d else None
    dp = os.path.join(d, "daily.parquet") if d else None
    G = json.load(open(gj)) if gj and os.path.exists(gj) else None
    if G is None:
        out["notes"].append("no gates.json (stopped before HOLD)")
    else:
        hg, ht = G.get("hold_gain", np.nan), G.get("hold_t_alpha", np.nan)
        out["oos"] = 20 if (hg >= 0.5 and ht >= 2) else 14 if (hg >= 0.25 and ht >= 1.5) else 7 if hg > 0 else 0
        t, dsr = G.get("full_t_alpha", np.nan), G.get("dsr", np.nan)
        out["stats"] = (10 if t >= 3 else 6 if t >= 2 else 3 if t >= 1 else 0) + \
                       (10 if dsr >= 0.95 else 6 if dsr >= 0.8 else 3 if dsr >= 0.5 else 0)
        out.update({k: G.get(k) for k in ("a", "full_t_alpha", "hold_t_alpha", "full_gain", "hold_gain", "dsr",
                                          "full_book_sharpe", "full_sleeve_sharpe", "G1", "G2", "G3", "G4", "G5")})
    if dp and os.path.exists(dp):
        D = pd.read_parquet(dp)
        D.index = pd.to_datetime(D.index)
        s = D["s30_2x"].astype(float)
        s = s[s.index.isin(gates.ERA_DAYS)]
        yrs = s.groupby(s.index.year).sum()
        out["sleeve_years_2x"] = {int(k): round(float(v), 4) for k, v in yrs.items()}
        out["rob_years"] = 5 if len(yrs) and (yrs > 0).all() else 0
        tot = s.sum()
        top3 = s.sort_values(ascending=False).head(3).sum() / tot if tot > 0 else np.nan
        out["top3_share"] = float(top3) if np.isfinite(top3) else None
        out["rob_conc"] = 5 if (np.isfinite(top3) and top3 < 0.5) else 0
        ri = gates.incumbent(70e3, days=s.index)
        c = float(np.corrcoef(s, ri)[0, 1]) if s.std() > 0 else np.nan
        worst = ri.sort_values().head(10).index
        on_worst = float(s.reindex(worst).mean())
        out["corr_incumbent"], out["mean_on_inc_worst10"] = c, on_worst
        out["divers"] = (3 if c < 0.2 else 1.5 if c < 0.4 else 0) + (2 if on_worst > 0 else 0)
    return out


def main(ideas):
    man = json.load(open(MANUAL)) if os.path.exists(MANUAL) else {}
    rows = []
    for i in ideas:
        a = auto_scores(i)
        m = man.get(i, {})
        a["rob_neigh"] = m.get("rob_neigh", 0)
        a["realism"] = m.get("realism", 0)
        a["mechanism"] = m.get("mechanism", 0)
        a["implement"] = m.get("implement", 0)
        a["capacity"] = m.get("capacity", 0)
        a["total"] = sum(a[k] for k in ("oos", "stats", "rob_years", "rob_neigh", "rob_conc", "realism", "mechanism",
                                        "implement", "divers", "capacity"))
        a["manual_reasons"] = m.get("why", "")
        rows.append(a)
    S = pd.DataFrame(rows).sort_values("total", ascending=False)
    S.to_csv(os.path.join(ROOT, "reports", "hunt", "scorecard.csv"), index=False)
    cols = ["idea", "total", "oos", "stats", "rob_years", "rob_neigh", "rob_conc", "realism", "mechanism", "implement",
            "divers", "capacity", "full_t_alpha", "dsr", "full_gain", "hold_gain"]
    print(S[[c for c in cols if c in S]].round(2).to_string(index=False))
    return S


if __name__ == "__main__":
    ids = sys.argv[1:] or sorted({os.path.basename(os.path.dirname(p)) for p in
                                  glob.glob(os.path.join(WT, "*", "reports", "hunt", "h*", "SPEC.md"))})
    main(ids)
