#!/usr/bin/env python3
"""Explore v1: build the frozen short list from the selection-era scores (reports/explore/prereg.md 'Short list').

  python scripts/explore/freeze.py            # print the picks (no file written)
  python scripts/explore/freeze.py --write hand.json
      hand.json: {"<finalist name>": [mechanism 0-10, implementation 0-5, "reason"], ...}, assigned before the read

Rules (no-harm = minute Sharpe at $250K >= the incumbent's and blended $1M Sharpe >= the incumbent's - 0.05):
  Best      highest blended $250K Sharpe among no-harm variants
  Robust    highest lower bound (Sharpe - 1 block-bootstrap SE) among no-harm variants
  Ensemble  the 10 best no-harm variants, daily returns averaged (each at full capital)
  Family bests (geometry, exits, filters): the best no-harm variant that changes only that family's dimensions, not
  already listed.
  Best single change (deviation log entry 3): the best no-harm variant that changes exactly one dimension from the
  incumbent, not already listed.
Writes reports/explore/finalists.json.
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import select_rules  # noqa: E402

OUT = select_rules.OUT


def picks():
    S = pd.read_csv(os.path.join(OUT, "scores.csv"))
    S["family"] = select_rules.family_of(S)
    nh = S[S.noharm & S.id.ne("base")].copy()
    out = []
    best = nh.sort_values("sharpe_b250", ascending=False).iloc[0]
    out.append(("Best", best))
    rob = nh.sort_values("lcb", ascending=False).iloc[0]
    out.append(("Robust", rob))
    ens = nh.sort_values("sharpe_b250", ascending=False).head(10)
    listed = {best.id, rob.id}
    fam = []
    for f in select_rules.FAM_DIMS:
        g = nh[(nh.family == f) & ~nh.id.isin(listed)].sort_values("sharpe_b250", ascending=False)
        if len(g):
            fam.append((f"Best {f}", g.iloc[0]))
            listed.add(g.iloc[0].id)
    nch = n_changed(S)
    g = nh[(nch[nh.index] == 1) & ~nh.id.isin(listed)].sort_values("sharpe_b250", ascending=False)
    if len(g):
        fam.append(("Best single change", g.iloc[0]))
    return S, out, ens, fam


def n_changed(S):
    """Number of design dimensions changed from the incumbent (-1 if the design is not a full one)."""
    out = []
    for x in S.design:
        d = json.loads(x) if isinstance(x, str) else {}
        d.pop("note", None)
        if not set(select_rules.variants_r3.V1.DIMS) <= set(d):
            out.append(-1)
            continue
        f = dict(select_rules.variants_r3.BASE3)
        f.update(d)
        out.append(sum(f[k] != select_rules.variants_r3.BASE3[k] for k in f))
    return pd.Series(out, index=S.index)


def main():
    S, out, ens, fam = picks()
    base = S[S.id == "base"].iloc[0]
    cols = ["id", "family", "sharpe_b250", "lcb", "sharpe_m250", "sharpe_b1m", "ret_b250", "maxdd_b250", "spa_t", "stepm"]
    print(f"incumbent: {base.sharpe_b250:.3f} / minute {base.sharpe_m250:.3f} / $1M {base.sharpe_b1m:.3f}")
    for name, r in out + fam:
        print(f"{name:14s}", r[cols].to_dict())
        print("   spec:", r.spec)
    print("Ensemble members:")
    print(ens[cols].round(3).to_string(index=False))
    if len(sys.argv) > 2 and sys.argv[1] == "--write":
        hand = json.load(open(sys.argv[2]))
        fins = []
        for name, r in out + fam:
            h = hand[name]
            fins.append(dict(name=name, id=r.id, spec=json.loads(r.spec), hand=[h[0], h[1]], why=h[2],
                             sel=dict(sharpe_b250=r.sharpe_b250, lcb=r.lcb, sharpe_m250=r.sharpe_m250,
                                      sharpe_b1m=r.sharpe_b1m)))
        h = hand["Ensemble"]
        fins.insert(2, dict(name="Ensemble", ids=ens.id.tolist(), members=[json.loads(x) for x in ens.spec],
                            hand=[h[0], h[1]], why=h[2]))
        F = dict(incumbent=dict(spec={}), finalists=fins,
                 note="Frozen from the selection era only (rounds 1-3) by scripts/explore/freeze.py; hand scores "
                      "(mechanism /10, implementation /5) assigned before the holdout read.")
        json.dump(F, open(os.path.join(OUT, "finalists.json"), "w"), indent=1)
        print("wrote finalists.json with", len(fins), "finalists")


if __name__ == "__main__":
    main()
