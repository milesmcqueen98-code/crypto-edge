#!/usr/bin/env python3
"""Explore v1: round 3b, the literature scan's ideas that xsim can express (scratchpad notes summarised in
reports/explore/literature.md), written before round 3b runs and after round 3 (deviation log entry 2).

  A1 take-profit rising with depth (Lipton & Lopez de Prado; Duffie; impact reversion of uninformed metaorders)
  A3 a light 4-sigma parent (Brogaard et al.; Handa & Schwartz)
  A4 scale-out take-profit ladders per rung (Gueant, Lehalle & Fernandez-Tapia), and A1 + A4 combined
  A5 cancel deeper bids on 50% parent recovery or after 30 minutes; 30-minute timeout alone
Each on the incumbent, and on the round 1-3 Best and Robust no-harm variants (their other settings kept).
De-duplicated against rounds 1-3. Writes reports/explore/round3b_variants.json.
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import variants as V1  # noqa: E402

OUT = V1.OUT

TP_RISING = {"tpA1_50_80_100": {4: 0.5, 6: 0.8, 8: 1.0}, "tpA1_60_80_100": {4: 0.6, 6: 0.8, 8: 1.0},
             "tpA1_40_60_100": {4: 0.4, 6: 0.6, 8: 1.0}, "tpA1_50_70_100": {4: 0.5, 6: 0.7, 8: 1.0}}
TP_LADDER = {"tpA4_40_70_100": [(0.4, 1), (0.7, 1), (1.0, 1)], "tpA4_50_100": [(0.5, 1), (1.0, 1)]}
TP_COMBO = {"tpA14": {"4": [(0.4, 1), (0.6, 1), (0.8, 1)], "deep": [(0.6, 1), (0.8, 1), (1.0, 1)]}}


def tp_rising(depths, m):
    """Monotone take-profit by depth: the listed 4/6/8 fractions; other depths take the nearest listed depth's."""
    out = {}
    for k in depths:
        near = min(m, key=lambda d: (abs(d - k), -d))
        out[float(k)] = [(m[near], 1.0)]
    return out


def variants_on(vid, s0):
    depths = sorted(float(k) for k in s0["rungs"])
    out = []
    for name, m in TP_RISING.items():
        out.append((f"{vid}_{name}", dict(s0, tp=tp_rising(depths, m))))
    for name, lad in TP_LADDER.items():
        out.append((f"{vid}_{name}", dict(s0, tp=lad)))
    for name, d in TP_COMBO.items():
        out.append((f"{vid}_{name}", dict(s0, tp={k: (d["4"] if k == 4.0 else d["deep"]) for k in depths})))
    w = dict(s0["rungs"])
    tot = sum(w.values())
    light = {k: (0.1 * tot if k == 4.0 else v * 0.9 * tot / max(tot - w.get(4.0, 0.0), 1e-12)) for k, v in w.items()}
    out.append((f"{vid}_A3_light10", dict(s0, rungs=light)))
    out.append((f"{vid}_A5_c50_to30", dict(s0, cancel="parent_tp", cancel_f=0.5, bid_to=30)))
    out.append((f"{vid}_A5_to30", dict(s0, bid_to=30)))
    return out


def main():
    seen = set()
    for r in ("1", "2", "3"):
        for v in json.load(open(os.path.join(OUT, f"round{r}_variants.json"))):
            seen.add(V1.key(v["spec"]))
    S = pd.read_csv(os.path.join(OUT, "scores.csv"))
    nh = S[S.noharm & S.id.ne("base")]
    centres = [("base", {"rungs": {4.0: 1.0, 6.0: 1.0, 8.0: 1.0}, "tp": [(0.6, 1.0)], "H": 60, "cancel": "parent_tp",
                         "r_min": 1.0, "adv_floor": 0.0, "slots": None, "kappa": 0.002, "per_trade": 0.25,
                         "cash_cap": 1.0})]
    for col in ("sharpe_b250", "lcb"):
        r = nh.sort_values(col, ascending=False).iloc[0]
        centres.append((r.id, json.loads(r.spec)))
    out = []
    for cid, s0 in centres:
        s0 = dict(s0)
        s0["rungs"] = {float(k): float(v) for k, v in s0["rungs"].items()}
        for vid, s in variants_on(cid, s0):
            k = V1.key(s)
            if k in seen:
                continue
            seen.add(k)
            out.append(dict(id=f"r3b_{vid}", round=3, origin="literature", parent=cid, design={}, spec=s))
    json.dump(out, open(os.path.join(OUT, "round3b_variants.json"), "w"), indent=0, default=str)
    print(len(out), "round-3b variants from", [c for c, _ in centres])


if __name__ == "__main__":
    main()
