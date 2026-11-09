#!/usr/bin/env python3
"""Explore v1: the round-1 variant list (reports/explore/prereg.md), written before any variant is run.

One-factor-at-a-time from the incumbent (every level of every dimension, plus the W2 book), then 1,000 random
combinations drawn uniformly over the grid (seed 20261109). Duplicates (same effective spec) are dropped.
Writes reports/explore/round1_variants.json.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "reports", "explore")

RUNGSETS = {"R468": (4, 6, 8), "R45678": (4, 5, 6, 7, 8), "R46810": (4, 6, 8, 10), "R46812": (4, 6, 8, 12),
            "R45710": (4, 5, 7, 10), "R4710": (4, 7, 10), "R46912": (4, 6, 9, 12), "R48": (4, 8), "R4610": (4, 6, 10),
            "R4568012": (4, 5, 6, 8, 10, 12), "R46": (4, 6), "R4812": (4, 8, 12)}
ALPHA = (0.0, -1.0, 0.5, 1.0, 1.5, 2.0, 3.0)                 # deeper weight w_k ~ (k / 4) ** alpha
P4 = (1.0, 0.5, 0.0)                                          # parent weight multiplier (0 = trigger-only)
TP = {"f60": [(0.6, 1)], "f30": [(0.3, 1)], "f40": [(0.4, 1)], "f50": [(0.5, 1)], "f70": [(0.7, 1)], "f80": [(0.8, 1)],
      "f100": [(1.0, 1)], "L3": [(0.4, 1), (0.6, 1), (0.8, 1)], "L2": [(0.5, 1), (0.8, 1)],
      "L3w": [(0.3, 1), (0.6, 2), (1.0, 1)], "L2lo": [(0.4, 1), (0.7, 1)]}
for f4 in (0.4, 0.6, 0.8):                                    # take-profit by depth: parent f4, deeper rungs fd
    for fd in (0.4, 0.6, 0.8, 1.0):
        if f4 != fd:
            TP[f"d{int(f4 * 100)}_{int(fd * 100)}"] = {"4": [(f4, 1)], "deep": [(fd, 1)]}
H = (60, 30, 45)
CANCEL = ("parent_tp", "none")
RMIN = (1.0, 1.05, 1.1, 1.2, 1.3, 1.5)
FLOOR = (0.0, 3e6, 10e6)
SLOTS = (None, 4, 6, 8)
KAPPA = (0.002, 0.0015, 0.003, 0.004)
PER = (0.25, 0.15, 0.2, 0.33)
CASH = (1.0, 0.8)
DIMS = dict(rungset=list(RUNGSETS), alpha=list(ALPHA), p4=list(P4), tp=list(TP), H=list(H), cancel=list(CANCEL),
            r_min=list(RMIN), adv_floor=list(FLOOR), slots=list(SLOTS), kappa=list(KAPPA), per_trade=list(PER),
            cash_cap=list(CASH))
BASE = {d: v[0] for d, v in DIMS.items()}


def spec(p):
    """Design point -> xsim spec."""
    ks = RUNGSETS[p["rungset"]]
    w = {float(k): (k / 4.0) ** p["alpha"] for k in ks}
    w[4.0] *= p["p4"]
    tp = TP[p["tp"]]
    if isinstance(tp, dict):
        tp = {float(k): (tp["4"] if k == 4 else tp["deep"]) for k in ks}
    return dict(rungs=w, tp=tp, H=p["H"], cancel=p["cancel"], r_min=p["r_min"], adv_floor=p["adv_floor"],
                slots=p["slots"], kappa=p["kappa"], per_trade=p["per_trade"], cash_cap=p["cash_cap"])


def key(s):
    return json.dumps(s, sort_keys=True, default=str)


def main():
    out, seen = [], set()

    def add(vid, p, origin):
        s = spec(p)
        k = key(s)
        if k in seen:
            return
        seen.add(k)
        out.append(dict(id=vid, round=1, origin=origin, design=p, spec=s))

    add("base", dict(BASE), "incumbent")
    w2 = dict(BASE)
    out.append(dict(id="W2", round=1, origin="named", design=dict(w2, note="rungs 1:1:2"),
                    spec=dict(spec(w2), rungs={4.0: 1.0, 6.0: 1.0, 8.0: 2.0})))
    seen.add(key(out[-1]["spec"]))
    for d, levels in DIMS.items():                            # one factor at a time
        for v in levels[1:]:
            p = dict(BASE)
            p[d] = v
            add(f"ofat_{d}_{v}", p, "ofat")
    rng = random.Random(20261109)
    i = 0
    while i < 1000:                                           # random combinations
        p = {d: rng.choice(levels) for d, levels in DIMS.items()}
        before = len(out)
        add(f"rnd_{i:04d}", p, "random")
        if len(out) > before:
            i += 1
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "round1_variants.json"), "w"), indent=0, default=str)
    print(len(out), "variants:", sum(v["origin"] == "ofat" for v in out), "OFAT,",
          sum(v["origin"] == "random" for v in out), "random, plus base and W2")


if __name__ == "__main__":
    main()
