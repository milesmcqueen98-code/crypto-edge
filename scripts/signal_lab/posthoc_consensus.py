#!/usr/bin/env python3
"""Signal lab, POST HOC (information only; every era here has been read): what if the bot only took the signals
that R2-08 and a second, differently trained model both approve?

  python scripts/signal_lab/posthoc_consensus.py

R2-08's trade list is cut to the (minute, coin) pairs that the second model's list also holds, then run through the
frozen simulator at S* (today's volumes, costs x2, theta 0.5, $250K). Second models: history only (RF0H) and features +
history (RF2H) in the main eras; features (RF2) in 2022-23, where no earlier history exists. The cut is approximate:
per-coin books are sequential, so a dropped trade could have let a later one in.
Writes reports/signal_lab/posthoc_consensus.txt.
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v5"))
import fsim  # noqa: E402

sim = fsim.sim
OUT = os.path.join(ROOT, "reports", "signal_lab")
CFG = dict(theta=0.5, C=250e3, today=True, cost_mult=2.0)
PAIRS = {"main": ("RF0H", "RF2H"), "early": ("RF2",)}
ERAS = {"main": ("sel", "chk"), "early": ("early",)}


def main():
    orig = fsim.today_scale
    inc_P = {b: fsim.load(b) for b in PAIRS}
    fsim.today_scale = lambda P, lo, hi: orig(inc_P["early" if pd.Timestamp(lo).year < 2024 else "main"], lo, hi)
    pm = sim.perp_mult
    lines = ["POST HOC (information only): R2-08 cut to the signals a second model also approves; frozen simulator, S*", ""]
    for base, others in PAIRS.items():
        inc = pd.read_parquet(os.path.join(sim.OUT, f"trades_{base}.parquet"))
        ref = {e: fsim.stats(fsim.book(inc_P[base], e, **CFG)[0], CFG["C"], e) for e in ERAS[base]}
        for o in others:
            oth = pd.read_parquet(os.path.join(sim.OUT, f"trades_{base}_{o}.parquet"))[["ts", "coin"]]
            cut = inc.merge(oth, on=["ts", "coin"])
            tag = f"{base}_cons_{o}"
            sim.PERIODS[tag] = sim.PERIODS[base]
            sim.perp_mult = (lambda: {}) if base == "early" else pm
            cut.to_parquet(os.path.join(sim.OUT, f"trades_{tag}.parquet"), index=False)
            p = os.path.join(sim.OUT, f"pre_hunt_{tag}.pkl")
            if os.path.exists(p):
                os.remove(p)
            P = fsim.load(tag)
            for e in ERAS[base]:
                lo, hi = fsim.ERAS[e][1]
                w = lambda T: int(((T.ts >= lo) & (T.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))).sum())  # noqa: E731
                st = fsim.stats(fsim.book(P, e, **CFG)[0], CFG["C"], e)
                lines.append(f"R2-08 and {o:5s} {e:6s}: Sharpe {st['sharpe']:.3f} vs {ref[e]['sharpe']:.3f} "
                             f"({st['sharpe'] - ref[e]['sharpe']:+.3f}); return {100 * st['ret_yr']:.1f}% vs "
                             f"{100 * ref[e]['ret_yr']:.1f}%; trades {w(cut)} of {w(inc)}")
                print(lines[-1], flush=True)
    open(os.path.join(OUT, "posthoc_consensus.txt"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
