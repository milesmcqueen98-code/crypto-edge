#!/usr/bin/env python3
"""Explore v1: the round-2 variant list (reports/explore/prereg.md 'Rounds 2-3'), from round 1's selection-era
scores only.

Neighbours of the top 20 no-harm round-1 variants: one level either side on each ordered dimension, and every level of
the categorical dimensions (rung set, take-profit, cancel) for the top 5. Extra mechanism-led variants (from the
literature scan) are appended from reports/explore/round2_extra.json if it exists. De-duplicated against round 1.
Writes reports/explore/round2_variants.json.
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import variants as V1  # noqa: E402

OUT = V1.OUT
ORDERED = ("alpha", "p4", "H", "r_min", "adv_floor", "slots", "kappa", "per_trade", "cash_cap")
CATEG = ("rungset", "tp", "cancel")


def sort_levels(d):
    lv = list(V1.DIMS[d])
    if d == "slots":
        return [None] + sorted(x for x in lv if x is not None)
    return sorted(lv)


def main():
    S = pd.read_csv(os.path.join(OUT, "scores.csv"))
    S = S[S["round"] == 1]
    top = S[S.noharm].sort_values("sharpe_b250", ascending=False)
    seen = set()
    for v in json.load(open(os.path.join(OUT, "round1_variants.json"))):
        seen.add(V1.key(v["spec"]))
    out = []

    def add(vid, p, origin, parent):
        s = V1.spec(p)
        k = V1.key(s)
        if k in seen:
            return
        seen.add(k)
        out.append(dict(id=vid, round=2, origin=origin, parent=parent, design=p, spec=s))

    for rank, r in enumerate(top.head(20).itertuples()):
        p0 = json.loads(r.design)
        p0.pop("note", None)
        if set(p0) != set(V1.DIMS):
            continue
        for d in ORDERED:
            lv = sort_levels(d)
            i = lv.index(p0[d])
            for j in (i - 1, i + 1):
                if 0 <= j < len(lv):
                    p = dict(p0)
                    p[d] = lv[j]
                    add(f"r2_{r.id}_{d}_{lv[j]}", p, "neighbour", r.id)
        if rank < 5:
            for d in CATEG:
                for v in V1.DIMS[d]:
                    p = dict(p0)
                    p[d] = v
                    add(f"r2_{r.id}_{d}_{v}", p, "neighbour", r.id)
    extra = os.path.join(OUT, "round2_extra.json")
    if os.path.exists(extra):
        for e in json.load(open(extra)):
            k = V1.key(e["spec"])
            if k not in seen:
                seen.add(k)
                out.append(dict(id=e["id"], round=2, origin=e.get("origin", "literature"), parent=e.get("parent", ""),
                                design=e.get("design", {}), spec=e["spec"], note=e.get("note", "")))
    json.dump(out, open(os.path.join(OUT, "round2_variants.json"), "w"), indent=0, default=str)
    print(len(out), "round-2 variants:", sum(v["origin"] == "neighbour" for v in out), "neighbours,",
          sum(v["origin"] != "neighbour" for v in out), "added (main effects / literature)")


if __name__ == "__main__":
    main()
