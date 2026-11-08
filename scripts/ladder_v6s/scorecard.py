#!/usr/bin/env python3
"""Ladder v6 (sizing) scorecard, the same rules as ladder v6 exits. Ladder v6 (exits) scorecard: ladder v5's 100-point rubric (scripts/ladder_v5/scorecard.py), with Evidence,
Robustness, Prize and Capacity on the out-of-sample eras (check + 2022-23), as the pre-registration says.

Automatic parts (fixed at the freeze, before the out-of-sample read):
  Evidence 25     pooled paired t at S* theta 0.5, declared path: >= 3: 25, >= 2: 18, >= 1: 8, >= 0: 3, else 0
  Robustness 20   r1 both out-of-sample eras positive 5, one 2, none 0; r2 theta 0.25 pooled t >= 2 and both eras
                  positive 5, t >= 1 3, else 0; r3 base pooled mean > 0 and t >= 1 5, mean > 0 3, else 0;
                  r4 the $1M pooled t has the sign of S*'s 5 (zero 2, else 0)
  Prize 15        mean of the two eras' Sharpe change at S*: >= 0.5: 15, >= 0.25: 10, >= 0.1: 5, > 0: 2
  Capacity 5      the same at $1M: >= 0.25: 5, >= 0: 2, else 0
Hand parts (reports/ladder_v6x/scorecard_manual.json, with reasons, written before the read): Realism 15,
Mechanism 10, Implementation and risk 10.
Levers dropped before the freeze have no out-of-sample read: they are scored the same way on the selection era with
their best in-sample rule (an upper bound), and marked so.
usage: python scripts/ladder_v6x/scorecard.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "reports", "ladder_v6s")


def auto(c, path="return"):
    """c: {cfg: {eras: {era: {mean_bp, d_sharpe}}, pooled_t, pooled_t_volmatched, pooled_mean_bp,
    era_means_volmatched_bp}}"""
    vm = path == "sharpe"
    key = "pooled_t_volmatched" if vm else "pooled_t"
    t = c["S_0.5"][key]
    ev = 25 if t >= 3 else 18 if t >= 2 else 8 if t >= 1 else 3 if t >= 0 else 0

    def eras(cfg):
        return c[cfg]["era_means_volmatched_bp"] if vm else {e: v["mean_bp"] for e, v in c[cfg]["eras"].items()}
    npos = sum(v > 0 for v in eras("S_0.5").values())
    r1 = 5 if npos == len(eras("S_0.5")) else 2 if npos >= 1 else 0
    r2 = 5 if (c["S_0.25"][key] >= 2 and all(v > 0 for v in eras("S_0.25").values())) else 3 if c["S_0.25"][key] >= 1 else 0
    bm = np.mean(list(eras("base_0.5").values())) if vm else c["base_0.5"]["pooled_mean_bp"]
    r3 = 5 if (bm > 0 and c["base_0.5"][key] >= 1) else 3 if bm > 0 else 0
    sc, s5 = np.sign(c["cap_1M"][key]), np.sign(t)
    r4 = 5 if (sc == s5 and s5 != 0) else 2 if sc == 0 else 0
    ds = float(np.mean([v["d_sharpe"] for v in c["S_0.5"]["eras"].values()]))
    pz = 15 if ds >= 0.5 else 10 if ds >= 0.25 else 5 if ds >= 0.1 else 2 if ds > 0 else 0
    cap = float(np.mean([v["d_sharpe"] for v in c["cap_1M"]["eras"].values()]))
    cp = 5 if cap >= 0.25 else 2 if cap >= 0 else 0
    return dict(evidence=ev, robustness=r1 + r2 + r3 + r4, prize=pz, capacity=cp, t=t, mean_dsharpe=ds,
                cap_dsharpe=cap)


def main():
    man = json.load(open(os.path.join(OUT, "scorecard_manual.json")))
    rows = []
    for name, m in man.items():
        rec = json.load(open(os.path.join(OUT, m["record"])))
        a = auto(rec["configs"], rec.get("spec", {}).get("path", "return"))
        hand = {k: m[k]["score"] for k in ("realism", "mechanism", "implementation")}
        total = a["evidence"] + a["robustness"] + a["prize"] + a["capacity"] + sum(hand.values())
        rows.append(dict(candidate=name, basis=m.get("basis", rec.get("basis", "")), total=total, **{k: a[k] for k in
                         ("evidence", "robustness", "prize", "capacity")}, **hand,
                         t=round(a["t"], 2), mean_dsharpe=round(a["mean_dsharpe"], 3),
                         cap_dsharpe=round(a["cap_dsharpe"], 3), verdict=m.get("verdict", "")))
    df = pd.DataFrame(rows).sort_values("total", ascending=False)
    df.to_csv(os.path.join(OUT, "scorecard.csv"), index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
