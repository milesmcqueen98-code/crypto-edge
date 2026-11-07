#!/usr/bin/env python3
"""Ladder v5: the joint re-test of the candidates that passed the gates (reports/ladder_v5_prereg.md, step 4).

Components, each exactly as its builder implemented and logged it (code copied unchanged from its branch):
  c2a  meta-label sizing by the AI margin's tercile (scripts/ladder_v5/cand_sizing.py, branch ladder/sizing)
  c3a  passive time exit, 5 minutes   (scripts/ladder_v5/cand_exits.py, branch ladder/exits)
  c3b  passive time exit, 15 minutes  (same)
The joint book: hsim.book with C2a's size_fn (the live cash rule sees the C2a sizes), then each latency bound's tranche
frame goes through C3's passive exit (cand_exits.exit_rem), blended as hsim.book blends.
Checks before any logged trial: (1) both components off reproduce the cached incumbent exactly; (2) C2a alone and
C3b alone reproduce their logged trials' per-era return and Sharpe (reports/ladder_v5/trials/<name>.json from the
builder branches, copied into reports/ladder_v5/joint/ref/).
usage: python scripts/ladder_v5/cand_joint.py check | run <combo> [<combo> ...]     combo e.g. c2a+c3b
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gates  # noqa: E402  (first: fsim puts scripts/hunt, which has its own gates.py, ahead of this folder)
import fsim  # noqa: E402
import hsim  # noqa: E402
import cand_sizing as CS  # noqa: E402
import cand_exits as CE  # noqa: E402

for _m in (gates, fsim, hsim, CS, CE):
    assert os.path.dirname(os.path.abspath(_m.__file__)) == HERE, _m.__file__

OUTD = os.path.join(fsim.OUT, "joint")


def make(sizing="off", N=0):
    """Joint book: sizing in {"off", "c2a"}; N = passive minutes (0 = the market exit at minute 60)."""
    def book_fn(P, era, pan=None, adv_=None, theta=0.5, C=250e3, today=False, cost_mult=1.0):
        tag, (lo, hi) = fsim.ERAS[era]
        if pan is None:
            pan = gates.data(tag)[1]
        f = None if sizing == "off" else CS.size_fn_for(sizing, tag, pan[0])
        d, out = hsim.book(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, pan=pan, adv=adv_, size_fn=f)
        if N == 0:
            return d
        sc = fsim.today_scale(P, lo, hi) if today else None
        hs_bp, impact_y = fsim.HS_BP * cost_mult, fsim.IMPACT_Y * cost_mult
        idx_d = pd.date_range(lo, hi, freq="D")
        res = {}
        for name in ("minute", "instant"):
            Q, _, info, _ = out[name]
            daily, det, chk = CE.exit_rem(Q, info, tag, P, N, theta, hs_bp, impact_y, sc)
            assert chk < 1e-9, f"market-exit replication failed: {chk}"
            res[name] = daily.reindex(idx_d, fill_value=0.0) / C
        s = fsim.lat_share(era, theta)
        return res["minute"] + s * (res["instant"] - res["minute"])
    return book_fn


def parse(combo):
    parts = set(combo.split("+"))
    sizing = "c2a" if "c2a" in parts else "off"
    N = 15 if "c3b" in parts else 5 if "c3a" in parts else 0
    unknown = parts - {"c2a", "c3a", "c3b"}
    assert not unknown, unknown
    return sizing, N


def check():
    CE.ensure_frozen()
    lines = []
    for era in fsim.ERAS:
        tag = fsim.ERAS[era][0]
        P, pan = gates.data(tag)
        inc = gates.incumbent_cached(era, "S_0.5")
        d = make("off", 0)(P, era, pan=pan, adv_=gates.adv(tag, era), **gates.CONFIGS["S_0.5"])
        lines.append(f"off/off vs cached incumbent, {era}: max daily difference "
                     f"{float(np.abs(d.reindex(inc.index, fill_value=0.0) - inc).max()):.2e}")
    for name, sizing, N in (("C2a_margin_terciles", "c2a", 0), ("C3b_passive_15", "off", 15)):
        ref = json.load(open(os.path.join(OUTD, "ref", f"{name}.json")))["configs"]["S_0.5"]["eras"]
        for era in fsim.ERAS:
            tag = fsim.ERAS[era][0]
            P, pan = gates.data(tag)
            d = make(sizing, N)(P, era, pan=pan, adv_=gates.adv(tag, era), **gates.CONFIGS["S_0.5"])
            st = fsim.stats(d, 250e3, era)
            lines.append(f"{name} alone, {era}: return {st['ret_yr']:.6f} vs logged {ref[era]['cand_ret']:.6f}; "
                         f"Sharpe {st['sharpe']:.6f} vs {ref[era]['cand_sharpe']:.6f}")
    txt = "\n".join(lines)
    os.makedirs(OUTD, exist_ok=True)
    open(os.path.join(OUTD, "check.txt"), "w").write(txt + "\n")
    print(txt, flush=True)


def run(combos):
    CE.ensure_frozen()
    for combo in combos:
        sizing, N = parse(combo)
        name = "J_" + combo.replace("+", "_")
        out = gates.run(name, make(sizing, N), path="return", note=f"joint re-test: {combo}")
        print(gates.summary(out), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "check":
        check()
    elif sys.argv[1] == "run":
        check()
        run(sys.argv[2:])
