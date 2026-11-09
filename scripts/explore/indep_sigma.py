#!/usr/bin/env python3
"""Explore v1: a semi-independent check of xsim's sigma floor against the legacy path (wick_v4 rungs.run on the
pre_v4 precompute), selection era only unless an era is given.

  python scripts/explore/indep_sigma.py [sig_min_bp ...] [--era selection]

Sigma comes from the AI pipeline's trade list (reports/wick1m/trades_<tag>.parquet, column sig; the legacy precompute
keeps no sigma and no unfilled deeper rungs), signals below the floor are dropped from the legacy input, and rungs.run (W0, theta 0.5, bot-like minute book) is compared with
xsim's minute book for {"sig_min": floor}. Writes reports/explore/indep_sigma_<era>.txt.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick_v4"))
import xsim  # noqa: E402
import rungs  # noqa: E402


def main(floors, era):
    tag, (lo, hi) = xsim.ERAS[era]
    X = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", f"pre_v4_{tag}.pkl"))
    X["in_perp"] = 0.0
    X["tp_perp"] = 0.0
    tr = pd.read_parquet(os.path.join(ROOT, "reports", "wick1m", f"trades_{tag}.parquet"))
    sig = tr.drop_duplicates(["ts", "coin"]).set_index(["ts", "coin"]).sig
    lines = [f"era {era}: legacy rungs.run on pre_v4 with signals dropped below the floor vs xsim sig_min (minute book)"]
    for C in (250e3, 1e6):
        for f in floors:
            keep = set(sig.index[(sig * 1e4 >= f - 1e-9).to_numpy()])
            Xf = X[[k in keep for k in zip(X.ts, X.coin)]]
            st, d0 = rungs.run(Xf, rungs.W["W0"], lo, hi, 0.5, C, True)
            d1, _, info = xsim.evaluate({"sig_min": f}, era, C)
            diff = float(np.abs(d1.to_numpy() - d0.to_numpy()).max())
            lines.append(f"${C / 1e3:,.0f}K floor {f:5.1f} bp: signals kept {len(keep)} (xsim {info['signals']}); "
                         f"legacy Sharpe {st['sharpe']:.4f}, xsim {xsim.stats(d1, era)['sharpe']:.4f}; max daily diff {diff:.1e}")
            print(lines[-1], flush=True)
    open(os.path.join(ROOT, "reports", "explore", f"indep_sigma_{era}.txt"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    era = "selection"
    if "--era" in args:
        i = args.index("--era")
        era = args[i + 1]
        args = args[:i] + args[i + 2:]
    main([float(a) for a in args] or [0.0, 50.0, 57.6, 70.0], era)
