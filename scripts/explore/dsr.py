#!/usr/bin/env python3
"""Explore v1: deflated Sharpe ratios of the frozen finalists on the selection era (Bailey and Lopez de Prado 2014).

  python scripts/explore/dsr.py

N = every variant of this search; also N + 5,000 (earlier setups that touched these data); also the effective number
of independent trials from the variants' daily-return correlations (participation ratio of the eigenvalues, and
rho-bar: N_eff = rho + (1 - rho) N). The trial Sharpe variance is the cross-variant variance of the per-day Sharpe.
Writes reports/explore/dsr.txt.
"""
import json
import math
import os
import sys

import numpy as np
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402
import holdout  # noqa: E402

OUT = analyze.OUT
EULER = 0.5772156649


def sr0(var_sr, n):
    return math.sqrt(var_sr) * ((1 - EULER) * norm.ppf(1 - 1 / n) + EULER * norm.ppf(1 - 1 / (n * math.e)))


def dsr(e, sr_star):
    T = len(e)
    sr = e.mean() / e.std(ddof=1)
    z = (e - e.mean()) / e.std(ddof=0)
    g3, g4 = float((z ** 3).mean()), float((z ** 4).mean())
    den = math.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-12))
    return float(norm.cdf((sr - sr_star) * math.sqrt(T - 1) / den)), sr, g3, g4


def main():
    V, cols, E = analyze.load()
    n_var = E.shape[1]
    srs = E.mean(0) / E.std(0, ddof=1)
    var_sr = float(np.var(srs, ddof=1))
    Z = (E - E.mean(0)) / E.std(0, ddof=1)
    s = np.linalg.svd(Z / math.sqrt(len(Z) - 1), compute_uv=False)
    lam = s ** 2
    n_pr = float(lam.sum() ** 2 / (lam ** 2).sum())
    C = np.corrcoef(E, rowvar=False)
    rho = float((C.sum() - n_var) / (n_var * (n_var - 1)))
    n_rho = rho + (1 - rho) * n_var
    F = json.load(open(os.path.join(OUT, "finalists.json")))
    lines = [f"Deflated Sharpe (selection era, blended $250K, daily excess returns), {n_var} variants",
             f"cross-variant variance of the daily Sharpe {var_sr:.3e} (annualized SD {math.sqrt(var_sr * 365):.3f})",
             f"effective N: participation ratio {n_pr:.1f}; mean pairwise correlation {rho:.3f} -> {n_rho:.0f}", ""]
    Ns = {"N": n_var, "N+5000": n_var + 5000, "N_eff(PR)": max(n_pr, 2.0), "N_eff(rho)": max(n_rho, 2.0)}
    lines.append(f"{'finalist':16s} {'SR(ann)':>8s} {'skew':>6s} {'kurt':>6s} " + " ".join(f"{k + ' SR0':>14s} {'DSR':>6s}" for k in Ns))
    rows = [("incumbent", {"spec": {}})] + [(f["name"], f) for f in F["finalists"]]
    for name, f in rows:
        d = holdout.series(f, "selection", 250e3)
        e = holdout.excess(d, "selection")
        parts = []
        for k, n in Ns.items():
            s0 = sr0(var_sr, n)
            p, sr, g3, g4 = dsr(e, s0)
            parts.append(f"{s0 * math.sqrt(365):14.2f} {p:6.3f}")
        lines.append(f"{name:16s} {sr * math.sqrt(365):8.3f} {g3:6.2f} {g4:6.1f} " + " ".join(parts))
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "dsr.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
