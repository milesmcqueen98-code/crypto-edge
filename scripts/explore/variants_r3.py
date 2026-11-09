#!/usr/bin/env python3
"""Explore v1: the round-3 variant list (reports/explore/prereg.md, 'Rounds 2-3' and the deviation log), written from
the selection era only (rounds 1-2 and a selection-era attribution of the incumbent), before round 3 runs.

Round 3 adds three dimensions to xsim (all off in rounds 1-2):
  sig_min   skip signals whose sigma is below 40 / 50 / 55 / 60 / 70 bp
  bid_to    deeper bids rest at most 2 / 5 / 10 / 20 minutes after the signal
  cancel_f  cancel deeper bids when the parent recovers 0.3 / 0.4 / 0.5 / 0.8 / 1.0 of its dislocation
and finer hold times (40, 50, 55 minutes).

Parts:
  A  1,500 random combinations over the pruned grid (levels whose round 1-2 OLS effect was <= -0.19 with |t| >= 3 are
     dropped: hold 30, trigger-only parent, alpha 2 and 3, 4 slots, take-profit 0.3 and 1.0, rungs 4-6), seed 20261110;
  B  family searches, every other dimension at the incumbent:
       geometry  all 252 combinations of rung set x alpha x parent weight;
       exits     600 random draws over take-profit x hold x cancel x cancel_f x bid_to (seed 20261111);
       filters   600 random draws over strictness x ADV floor x sigma floor x slots x ADV cap x size x cash (seed
                 20261112);
  C  the new dimensions one at a time around the incumbent and the 10 best no-harm variants of rounds 1-2.
De-duplicated against rounds 1-2. Writes reports/explore/round3_variants.json.
"""
import json
import os
import random
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import variants as V1  # noqa: E402

OUT = V1.OUT
NEW = dict(sig_min=[None, 40.0, 50.0, 55.0, 60.0, 70.0], bid_to=[None, 2, 5, 10, 20],
           cancel_f=[None, 0.3, 0.4, 0.5, 0.8, 1.0])
H_ALL = [60, 30, 45, 40, 50, 55]
DIMS3 = dict(V1.DIMS)
DIMS3["H"] = H_ALL
DIMS3.update(NEW)
BASE3 = {d: v[0] for d, v in DIMS3.items()}
PRUNED = dict(DIMS3)
PRUNED.update(H=[60, 45, 40, 50, 55], p4=[1.0, 0.5], alpha=[0.0, -1.0, 0.5, 1.0, 1.5], slots=[None, 6, 8],
              tp=[t for t in V1.DIMS["tp"] if t not in ("f30", "f100")],
              rungset=[r for r in V1.DIMS["rungset"] if r != "R46"])
FAMILIES = dict(geometry=("rungset", "alpha", "p4"),
                exits=("tp", "H", "cancel", "cancel_f", "bid_to"),
                filters=("r_min", "adv_floor", "sig_min", "slots", "kappa", "per_trade", "cash_cap"))


def spec3(p):
    s = V1.spec(p)
    for d in NEW:
        if p.get(d) is not None:
            s[d] = p[d]
    if s.get("cancel") == "none":
        s.pop("cancel_f", None)                                # cancel_f only acts on the parent_tp rule
    return s


def full(p):
    q = dict(BASE3)
    q.update({k: v for k, v in p.items() if k != "note"})
    return q


def main():
    seen = set()
    for r in (1, 2):
        for v in json.load(open(os.path.join(OUT, f"round{r}_variants.json"))):
            seen.add(V1.key(v["spec"]))
    out = []

    def add(vid, p, origin, parent=""):
        p = full(p)
        s = spec3(p)
        k = V1.key(s)
        if k in seen:
            return False
        seen.add(k)
        out.append(dict(id=vid, round=3, origin=origin, parent=parent, design=p, spec=s))
        return True

    rng = random.Random(20261110)                              # A: random over the pruned grid
    i = 0
    while i < 1500:
        p = {d: rng.choice(lv) for d, lv in PRUNED.items()}
        if add(f"r3a_{i:04d}", p, "random"):
            i += 1
    for rs in V1.DIMS["rungset"]:                              # B: geometry, exhaustive
        for a in V1.DIMS["alpha"]:
            for p4 in V1.DIMS["p4"]:
                add(f"r3g_{rs}_{a}_{p4}", dict(rungset=rs, alpha=a, p4=p4), "fam_geometry")
    for fam, seed in (("exits", 20261111), ("filters", 20261112)):
        rng = random.Random(seed)
        i, tries = 0, 0
        while i < 600 and tries < 100000:
            tries += 1
            p = {d: rng.choice(DIMS3[d]) for d in FAMILIES[fam]}
            if add(f"r3{fam[0]}_{i:04d}", p, f"fam_{fam}"):
                i += 1
    S = pd.read_csv(os.path.join(OUT, "scores.csv"))          # C: new dimensions around the incumbent and the top 10
    top = S[S.noharm & S.id.ne("base")].sort_values("sharpe_b250", ascending=False).head(10)
    centres = [("base", dict(BASE3))]
    for r in top.itertuples():
        d = json.loads(r.design)
        d.pop("note", None)
        if set(V1.DIMS) <= set(d):
            centres.append((r.id, full(d)))
    for cid, p0 in centres:
        for d in ("H",) + tuple(NEW):
            for v in DIMS3[d]:
                p = dict(p0)
                p[d] = v
                add(f"r3c_{cid}_{d}_{v}", p, "new_dims", cid)
    json.dump(out, open(os.path.join(OUT, "round3_variants.json"), "w"), indent=0, default=str)
    cnt = pd.Series([v["origin"] for v in out]).value_counts()
    print(len(out), "round-3 variants:", cnt.to_dict())


if __name__ == "__main__":
    main()
