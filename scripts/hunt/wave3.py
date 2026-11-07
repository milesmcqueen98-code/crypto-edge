#!/usr/bin/env python3
"""Edge hunt wave 3 (reports/hunt_prereg.md): combine the surviving sleeves with the incumbent.

Rule (fixed in the pre-registration):
- Incumbent share a in {0.5, 0.6, 0.7, 0.8}.
- The rest (1 - a) is split across sleeves in proportion to inverse DEV volatility.
- a is chosen on DEV by book Sharpe.
- The gates are re-applied to the combined book (alpha t of the sleeve portfolio on the incumbent, HOLD,
  all-day gain, DSR, years).

Approximations:
- Sleeve returns per dollar come from the closest simulated capital ($30K or $50K, 2x costs).
- The incumbent at a x $100K is interpolated linearly between the simulated capitals ($50K, $70K, $100K).

usage: python scripts/hunt/wave3.py h1pb [h9mc ...]
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import gates  # noqa: E402

A_GRID = (0.5, 0.6, 0.7, 0.8)
INC_CAPS = (50e3, 70e3, 100e3)


def inc_at(cap, days):
    """Incumbent per-dollar daily returns at `cap`, linear between the simulated capitals."""
    lo = max(c for c in INC_CAPS if c <= cap) if cap >= INC_CAPS[0] else INC_CAPS[0]
    hi = min(c for c in INC_CAPS if c >= cap) if cap <= INC_CAPS[-1] else INC_CAPS[-1]
    a, b = gates.incumbent(lo, days=days), gates.incumbent(hi, days=days)
    if hi == lo:
        return a
    w = (cap - lo) / (hi - lo)
    return (1 - w) * a + w * b


def load_sleeve(idea, branch_root="/home/claude/wt"):
    p = os.path.join(branch_root, idea, "reports", "hunt", idea, "daily.parquet")
    d = pd.read_parquet(p)
    d.index = pd.to_datetime(d.index)
    return d


def combine(ideas):
    S = {i: load_sleeve(i) for i in ideas}
    days = pd.DatetimeIndex(sorted(set().union(*[set(s.index) for s in S.values()]) & set(gates.ERA_DAYS)))
    dev = days < gates.HOLD0
    vol = {i: s["s30_2x"].reindex(days).fillna(0.0)[dev].std() for i, s in S.items()}
    w = {i: (1 / v) / sum(1 / x for x in vol.values()) for i, v in vol.items()}
    best, rows = None, []
    for a in A_GRID:
        ri = inc_at(a * 100e3, days)
        port = 0.0
        for i, s in S.items():
            cap = (1 - a) * w[i] * 100e3
            col = "s30_2x" if abs(cap - 30e3) <= abs(cap - 50e3) else "s50_2x"
            port = port + w[i] * s[col].reindex(days).fillna(0.0)
        bk = a * ri + (1 - a) * port
        sh = gates.sharpe(bk[dev])
        rows.append(dict(a=a, dev_sharpe=sh))
        if best is None or sh > best[1]:
            best = (a, sh, ri, port, bk)
    a, _, ri, port, bk = best
    inc = gates.incumbent(100e3, days=days)
    out = dict(ideas=ideas, weights=w, a=a, grid=rows)
    for name, m in (("full", np.ones(len(days), bool)), ("dev", dev), ("hold", ~dev)):
        at = gates.alpha_test(port[m], ri[m])
        out[f"{name}_t_alpha"] = at["t_alpha"]
        out[f"{name}_book_sharpe"] = gates.sharpe(bk[m])
        out[f"{name}_inc_sharpe"] = gates.sharpe(inc[m])
        out[f"{name}_gain"] = out[f"{name}_book_sharpe"] - out[f"{name}_inc_sharpe"]
    N, V = gates.n_trials()
    out["dsr"], out["sr0_ann"] = gates.deflated_sharpe(bk, N, V)
    out["n_trials"] = N
    yr = gates.years(bk)
    out["years"] = {int(k): round(float(v), 4) for k, v in yr.items()}
    out["G1"] = out["full_t_alpha"] >= 3
    out["G2"] = out["hold_t_alpha"] >= 1.5 and out["hold_gain"] >= 0.25
    out["G3"] = out["full_gain"] >= 0.5
    out["G4"] = out["dsr"] >= 0.95
    out["G5"] = bool((yr > 0).all())
    out["pass_G1_G5"] = all(out[g] for g in ("G1", "G2", "G3", "G4", "G5"))
    os.makedirs(os.path.join(ROOT, "reports", "hunt"), exist_ok=True)
    with open(os.path.join(ROOT, "reports", "hunt", "wave3.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    pd.DataFrame({"book": bk, "incumbent_100k": inc, "sleeves": port}).to_parquet(
        os.path.join(ROOT, "reports", "hunt", "wave3_daily.parquet"))
    return out


if __name__ == "__main__":
    print(json.dumps(combine(sys.argv[1:]), indent=1, default=float))
