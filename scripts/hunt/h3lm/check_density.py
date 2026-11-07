#!/usr/bin/env python3
"""H3 (LM): brute-force check of the vectorised density, survival and fill kernels on 2024 data (never scored).

For random decision hours, recompute the liquidation density directly (every entry minute in the trailing N days,
its decayed volume, survival per tier from the minimum low since entry) and compare with lm.density; re-derive fills
of a few bids minute by minute. Prints max relative errors only (no P&L, no statistics).

  python scripts/hunt/h3lm/check_density.py SOL
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lm  # noqa: E402


def main(coin):
    lm.SCORED = {"main": ("2024-03-01", "2024-03-31")}
    lm.ERAS = {"main": ("2024-02-01", "2024-04-01", "minute")}
    N = 7
    D = lm.prepare(coin, "main", None, (N,))
    hist, bmin = D["H"][N]
    S = D["S"]
    lo = np.where(np.isfinite(S["low"]), S["low"], np.inf)
    tp = (S["high"] + S["low"] + S["close"]) / 3.0
    rng = np.random.default_rng(1)
    errs = []
    for j in rng.choice(len(D["hrs"]), 12, replace=False):
        h = D["hrs"][j]
        lp0 = D["lp0"][j]
        b0 = int(math.ceil((lp0 - lm.D_UNION[1]) / lm.DELTA - 0.5))
        b1 = int(math.floor((lp0 - lm.D_UNION[0]) / lm.DELTA - 0.5))
        ref = np.zeros(lm.NB)
        for s in range(max(0, h - N * 1440), h):
            if not (np.isfinite(tp[s]) and S["vol"][s] > 0):
                continue
            w = S["vol"][s] * 0.5 ** ((h - s) / lm.HL_MIN)
            mn = lo[s + 1:h].min() if h > s + 1 else np.inf
            for (L, wt) in lm.TIERS:
                x = tp[s] * (1 - 1 / L + lm.MAINT)
                if mn > x:
                    b = int(math.floor(math.log(x) / lm.DELTA))
                    if b0 <= b <= b1:
                        ref[b - b0] += w * wt
        assert bmin[j] == b0, (bmin[j], b0)
        e = np.abs(hist[j] - ref).max() / max(ref.max(), 1e-12)
        errs.append(e)
        print(f"hour {D['idx'][h]}: buckets {b1 - b0 + 1}, max D {ref.max():.1f}, argmax ref {ref.argmax()} "
              f"vec {hist[j].argmax()}, max rel err {e:.2e}")
    print("density max rel err over hours:", max(errs))
    # fills: brute force vs kernel for the density bids of one R
    B, spec = lm.bids_for(D, N, lm.GRID_R[0], 0, 0, 0)
    V = D["V"]
    bad = 0
    n_fill = 0
    for arm in ("dens", "ctrl"):
        b = B[arm]
        for k in range(len(b["h"])):
            h, bid, edge = b["h"][k], b["bid"][k], b["edge"][k]
            f_ref, c_ref = -1, 0
            for t in range(h, min(len(V["open"]), h + 60)):
                if D["halt"][t] or not np.isfinite(V["low"][t]):
                    continue
                if V["open"][t] > bid and V["low"][t] <= bid - spec["tick"]:
                    f_ref = t
                    break
                if V["low"][t] < edge:
                    c_ref = 1
                    break
            f, c = lm.fill_scan(V["open"], V["high"], V["low"], D["halt"], h, bid, edge, spec["tick"], len(V["open"]))
            bad += int(f != f_ref or c != c_ref)
            n_fill += int(f_ref >= 0)
    print(f"fill kernel mismatches: {bad} of {len(B['dens']['h']) * 2} bids ({n_fill} fills)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "SOL")
