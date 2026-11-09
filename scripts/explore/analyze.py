#!/usr/bin/env python3
"""Explore v1: selection-era analysis of all variants run so far (reports/explore/prereg.md).

  python scripts/explore/analyze.py

- which assumptions matter: mean blended Sharpe by level (random variants) and an OLS on one-hot levels;
- overfitting: PBO by CSCV (16 blocks, all 12,870 half-splits), Hansen's SPA (consistent version) and Romano-Wolf
  StepM against the incumbent on the vol-matched daily difference, stationary bootstrap (mean block 7 days);
- a robust score per variant: Sharpe - 1 block-bootstrap standard error (7-day blocks).
Writes reports/explore/analysis.txt, effects.csv and scores.csv.
"""
import itertools
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import xsim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "explore")
SEED = 7


def load():
    V = pd.read_csv(os.path.join(OUT, "variants.csv"))
    D = [pd.read_parquet(os.path.join(OUT, f)) for f in sorted(os.listdir(OUT)) if f.startswith("daily_sel_r")]
    D = pd.concat(D, axis=1)
    D = D.loc[:, ~D.columns.duplicated()]
    lo, hi = xsim.ERAS["selection"][1]
    idx = pd.date_range(lo, hi, freq="D")
    rf = xsim.edge_book.rf_daily(idx).to_numpy()
    E = D.reindex(idx).fillna(0.0).to_numpy() - rf[:, None]          # excess daily returns
    return V, D.columns.tolist(), E


def sharpe_cols(E):
    return E.mean(0) / E.std(0, ddof=1) * math.sqrt(365)


def stationary_idx(n, rng, mean_block=7):
    out = np.empty(n, int)
    p = 1.0 / mean_block
    i = rng.integers(n)
    for t in range(n):
        out[t] = i
        i = rng.integers(n) if rng.random() < p else (i + 1) % n
    return out


def cscv(E, S=16):
    n, N = E.shape
    blocks = np.array_split(np.arange(n), S)
    s1 = np.array([E[b].sum(0) for b in blocks])
    s2 = np.array([(E[b] ** 2).sum(0) for b in blocks])
    nb = np.array([len(b) for b in blocks])
    lam, is_best_oos, oos_med = [], [], []
    for comb in itertools.combinations(range(S), S // 2):
        m = np.zeros(S, bool)
        m[list(comb)] = True

        def sh(mask):
            k = nb[mask].sum()
            a, b = s1[mask].sum(0), s2[mask].sum(0)
            v = (b - a ** 2 / k) / (k - 1)
            return a / k / np.sqrt(v)

        si, so = sh(m), sh(~m)
        best = int(np.argmax(si))
        w = (np.sum(so < so[best]) + 0.5) / N
        lam.append(math.log(w / (1 - w)))
        is_best_oos.append(so[best] * math.sqrt(365))
        oos_med.append(np.median(so) * math.sqrt(365))
    lam = np.array(lam)
    return dict(pbo=float(np.mean(lam <= 0)), splits=len(lam), best_oos_sharpe=float(np.mean(is_best_oos)),
                median_oos_sharpe=float(np.mean(oos_med)))


def spa_stepm(E, j0, B=2000, alpha=0.05):
    """Hansen SPA (consistent) and Romano-Wolf StepM on d_k = e_k / sd_k - e_0 / sd_0."""
    n, N = E.shape
    Z = E / E.std(0, ddof=1)
    d = Z - Z[:, [j0]]
    d = np.delete(d, j0, axis=1)
    dbar = d.mean(0)
    rng = np.random.default_rng(SEED)
    boots = np.empty((B, d.shape[1]))
    for b in range(B):
        boots[b] = d[stationary_idx(n, rng)].mean(0)
    om = boots.std(0, ddof=1)
    om = np.where(om > 0, om, np.nan)
    t = dbar / om
    T = max(np.nanmax(t), 0.0)
    thr = -math.sqrt(2 * math.log(math.log(n)))
    mu_c = np.where(t <= thr, dbar, 0.0)
    Tb = np.nanmax((boots - dbar + mu_c) / om, axis=1)
    p_spa = float(np.mean(np.maximum(Tb, 0) >= T))
    # StepM: reject while the largest remaining t exceeds the bootstrap (1-alpha) quantile of max over the rest
    active = np.ones(d.shape[1], bool)
    rejected = np.zeros(d.shape[1], bool)
    cen = (boots - dbar) / om
    while active.any():
        q = np.nanquantile(np.nanmax(cen[:, active], axis=1), 1 - alpha)
        new = active & (t > q)
        if not new.any():
            break
        rejected |= new
        active &= ~new
    return dict(T=float(T), p_spa=p_spa, n_stepm=int(rejected.sum()), t=t, rejected=rejected)


def boot_se(E, B=500):
    n, _ = E.shape
    rng = np.random.default_rng(SEED + 1)
    blocks = [np.arange(i, min(i + 7, n)) for i in range(0, n, 7)]
    out = []
    for _ in range(B):
        idx = np.concatenate([blocks[j] for j in rng.integers(0, len(blocks), len(blocks))])
        out.append(sharpe_cols(E[idx]))
    return np.std(np.array(out), axis=0, ddof=1)


def effects(V):
    R = V[V.origin == "random"].copy()
    base = V[V.id == "base"].iloc[0]
    rows = []
    des = [json.loads(x) for x in R.design]
    dims = [k for k in des[0] if k != "note"]
    for dname in dims:
        lv = pd.Series([str(d[dname]) for d in des], index=R.index)
        for level, g in R.groupby(lv):
            rows.append(dict(dim=dname, level=level, n=len(g), mean_d_b250=g.sharpe_b250.mean() - base.sharpe_b250,
                             se=g.sharpe_b250.std(ddof=1) / math.sqrt(len(g)), mean_d_b1m=g.sharpe_b1m.mean() - base.sharpe_b1m,
                             mean_d_m250=g.sharpe_m250.mean() - base.sharpe_m250))
    Eff = pd.DataFrame(rows)
    # OLS on one-hot levels (partial effects relative to each dimension's first listed level)
    X = []
    for d in des:
        X.append({f"{k}={d[k]}": 1.0 for k in dims})
    X = pd.DataFrame(X).fillna(0.0)
    ref = [c for c in X.columns if any(c == f"{k}={json.loads(V[V.id == 'base'].design.iloc[0])[k]}" for k in dims)]
    X = X.drop(columns=ref)
    X.insert(0, "const", 1.0)
    y = R.sharpe_b250.to_numpy()
    beta, *_ = np.linalg.lstsq(X.to_numpy(), y, rcond=None)
    resid = y - X.to_numpy() @ beta
    s2 = resid @ resid / (len(y) - X.shape[1])
    cov = s2 * np.linalg.pinv(X.to_numpy().T @ X.to_numpy())
    ols = pd.DataFrame({"term": X.columns, "coef": beta, "se": np.sqrt(np.diag(cov))})
    ols["t"] = ols.coef / ols.se
    r2 = 1 - resid @ resid / ((y - y.mean()) @ (y - y.mean()))
    return Eff, ols, r2


def main():
    V, cols, E = load()
    V = V.set_index("id").loc[cols].reset_index()
    base = V[V.id == "base"].iloc[0]
    j0 = cols.index("base")
    lines = [f"Variants analysed: {len(cols)} (selection era, blended $250K unless noted)",
             f"Incumbent: blended {base.sharpe_b250:.3f}, minute {base.sharpe_m250:.3f}, $1M blended {base.sharpe_b1m:.3f}"]
    se = boot_se(E)
    V["se_boot"] = se
    V["lcb"] = V.sharpe_b250 - V.se_boot
    V["noharm"] = (V.sharpe_m250 >= base.sharpe_m250 - 1e-12) & (V.sharpe_b1m >= base.sharpe_b1m - 0.05)
    V["d_b250"] = V.sharpe_b250 - base.sharpe_b250
    Eff, ols, r2 = effects(V)
    Eff.to_csv(os.path.join(OUT, "effects.csv"), index=False)
    ols.to_csv(os.path.join(OUT, "effects_ols.csv"), index=False)
    c = cscv(E)
    s = spa_stepm(E, j0)
    t_full = np.insert(s["t"], j0, np.nan)
    rej = np.insert(s["rejected"], j0, False)
    V["spa_t"], V["stepm"] = t_full, rej
    V.to_csv(os.path.join(OUT, "scores.csv"), index=False)
    lines += ["", f"Share of variants above the incumbent: {np.mean(V.d_b250 > 0):.1%}; no-harm: {V.noharm.mean():.1%}",
              f"Best blended Sharpe: {V.sharpe_b250.max():.3f} ({V.loc[V.sharpe_b250.idxmax(), 'id']})",
              f"PBO (CSCV, 16 blocks, {c['splits']} splits): {c['pbo']:.3f}; mean OOS Sharpe of the in-sample best "
              f"{c['best_oos_sharpe']:.2f} vs the median variant's {c['median_oos_sharpe']:.2f}",
              f"SPA (vol-matched daily difference vs incumbent): T {s['T']:.2f}, p {s['p_spa']:.3f}; "
              f"StepM rejections at 5%: {s['n_stepm']}",
              f"OLS of blended Sharpe on the design levels (random variants): R^2 {r2:.2f}", ""]
    lines.append("Top 20 no-harm variants (blended Sharpe at $250K):")
    top = V[V.noharm].sort_values("sharpe_b250", ascending=False).head(20)
    lines.append(top[["id", "sharpe_b250", "lcb", "sharpe_m250", "sharpe_b1m", "ret_b250", "maxdd_b250", "spa_t",
                      "stepm"]].round(3).to_string(index=False))
    lines += ["", "Largest partial effects (OLS, |t| >= 2):"]
    lines.append(ols[(ols.term != "const") & (ols.t.abs() >= 2)].sort_values("coef").round(3).to_string(index=False))
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "analysis.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
