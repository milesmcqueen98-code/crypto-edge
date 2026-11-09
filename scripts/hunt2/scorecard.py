#!/usr/bin/env python3
"""Edge hunt 2: the 100-point scorecard (weights fixed in reports/hunt2_prereg.md). Automatic parts come from
central_gates.json; hand-scored parts (fill realism, mechanism, implementability, robustness neighbours) come from
reports/hunt2/scorecard_manual.json, one entry per idea with the reason for each score.
Writes reports/hunt2/scorecard.csv.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import h2gates as G  # noqa: E402

OUT = os.path.join(G.ROOT, "reports", "hunt2")


def oos_points(g):
    """Out-of-sample (HOLD, read once), 25 points."""
    if g.get("path") == "A":
        t, m = g.get("hold_t_x2", np.nan), g.get("hold_mean_bp_x2", np.nan)
        if t >= 2:
            return 25
        if t >= 1:
            return 15
        return 7 if m > 0 else 0
    gain, t = g.get("hold_gain", np.nan), g.get("hold_t_alpha", np.nan)
    if gain >= 0.5 and t >= 2:
        return 25
    if gain >= 0.25 and t >= 1:
        return 15
    return 7 if gain > 0 else 0


def sleeve_view(idea, g):
    """Path B: the sleeve itself at the capital the gate chose (a), 2x costs, over its scored days. The gate's own
    deflated Sharpe and calendar years are the book's, which is at least half incumbent, so they score the incumbent;
    the scorecard reads the sleeve's (deviation log, Nov 8 2026: scoring only, no gate changes)."""
    D = pd.read_parquet(os.path.join(OUT, idea, "daily.parquet"))
    D.index = pd.DatetimeIndex(D.index)
    cap = int(round((1 - g["a"]) * G.CAPITAL))
    rs = D[f"s{cap // 1000}_2x"]
    rs = rs[np.isin(G.era_of(rs.index), list(G.ERAS))]
    N, V = G.n_trials()
    return dict(dsr=G.deflated_sharpe(rs, N, V)[0], years={int(k): float(v) for k, v in G.years(rs).items()})


def stat_points(g):
    """Statistical strength, 15 points: DEV statistic (5), deflated Sharpe (5), every HOLD era positive (5)."""
    dev = g.get("dev_t_x2") if g.get("path") == "A" else g.get("dev_t_alpha")
    p = 5 if dev is not None and dev >= 3 else (3 if dev is not None and dev >= 2 else (1 if dev is not None and dev >= 1 else 0))
    d = g.get("dsr_sleeve", g.get("dsr", 0)) if g.get("path") == "B" else g.get("dsr", 0)
    d = d or 0
    p += 5 if d >= 0.95 else (3 if d >= 0.8 else (1 if d >= 0.5 else 0))
    p += 5 if g.get("A3", g.get("B3")) else 0
    return p


def main():
    gates = {r["idea"]: r for r in json.load(open(os.path.join(OUT, "central_gates.json"))) if "error" not in r}
    man = json.load(open(os.path.join(OUT, "scorecard_manual.json")))
    rows = []
    for idea, m in man.items():
        if idea.startswith("_"):
            continue
        g = gates.get(idea, {})
        if g.get("path") == "B":
            sv = sleeve_view(idea, g)
            g = dict(g, dsr_sleeve=sv["dsr"], years_sleeve=sv["years"])
        yrs = g.get("years_x2") or g.get("years_sleeve") or g.get("years") or {}
        r = dict(idea=idea, path=g.get("path", m.get("path")), status=m.get("status", "built"))
        r["oos"] = oos_points(g) if g else 0
        r["stat"] = stat_points(g) if g else 0
        top5 = g.get("hold_top5_share_x2", g.get("hold_top5_share", np.nan))
        r["robust"] = (5 if yrs and all(v > 0 for v in yrs.values()) else 0) + m.get("neighbours", 0) + \
            (5 if top5 == top5 and top5 < 0.5 else 0)
        r["realism"] = m.get("realism", 0)
        r["mechanism"] = m.get("mechanism", 0)
        r["implement"] = m.get("implement", 0)
        r["divers"] = m.get("divers", 0)
        r["capacity"] = m.get("capacity", 0)
        r["total"] = sum(r[k] for k in ("oos", "stat", "robust", "realism", "mechanism", "implement", "divers",
                                        "capacity"))
        r["pass"] = bool(g.get("pass", False))
        r["dsr_scored"] = g.get("dsr_sleeve", g.get("dsr"))
        r["years_scored"] = json.dumps({k: round(v, 4) for k, v in yrs.items()})
        r["note"] = m.get("note", "")
        rows.append(r)
    S = pd.DataFrame(rows).sort_values("total", ascending=False)
    S.to_csv(os.path.join(OUT, "scorecard.csv"), index=False)
    print(S.to_string(index=False))


if __name__ == "__main__":
    main()
