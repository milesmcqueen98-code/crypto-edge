#!/usr/bin/env python3
"""Explore v1: which selection rule generalizes best inside the selection era? (CSCV tournament)

  python scripts/explore/select_rules.py [rounds, e.g. 1 or 1,2,3]

For every half-split of 16 contiguous selection-era blocks (all 12,870; blended $250K excess daily returns), each rule
picks a variant on the in-sample half; we record the out-of-sample half Sharpe of its pick minus the incumbent's
out-of-sample half Sharpe. Rules:
  max_all   highest in-sample Sharpe, any variant
  max_nh    highest in-sample Sharpe among no-harm variants (no-harm flag from the full selection era: a mild leak)
  lcb_nh    highest in-sample Sharpe - 1 standard error (Mertens: skew and kurtosis of the in-sample half), no-harm
  ols_nh    highest fitted value of an OLS of in-sample Sharpe on the design levels (random variants), no-harm
  shr50_nh  0.5 x fitted + 0.5 x raw in-sample Sharpe, no-harm
  ens10_nh  equal-weight average of the 10 best in-sample no-harm variants' daily returns
  ens10_ols same, the 10 best by OLS fitted value
  fam_<f>   highest in-sample Sharpe among the variants that change only family f (geometry / exits / filters)
  single_nh highest in-sample Sharpe among no-harm variants that change exactly one dimension
Information for choosing and describing the short list; the binding test stays the single holdout read.
Writes reports/explore/select_rules_r<rounds>.txt.
"""
import itertools
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402
import variants_r3  # noqa: E402

OUT = analyze.OUT
FAM_DIMS = variants_r3.FAMILIES


def design_matrix(V):
    """One-hot design for variants with a full design (None for others)."""
    rows, ok = [], []
    for x in V.design:
        d = json.loads(x) if isinstance(x, str) else {}
        d.pop("note", None)
        if not set(variants_r3.V1.DIMS) <= set(d):
            rows.append({})
            ok.append(False)
            continue
        f = dict(variants_r3.BASE3)
        f.update(d)
        rows.append({f"{k}={f[k]}": 1.0 for k in variants_r3.BASE3})
        ok.append(True)
    X = pd.DataFrame(rows).fillna(0.0)
    ref = [c for c in X.columns if any(c == f"{k}={variants_r3.BASE3[k]}" for k in variants_r3.BASE3)]
    X = X.drop(columns=ref)
    X.insert(0, "const", 1.0)
    return X.to_numpy(), np.array(ok)


def family_of(V):
    """Family whose dimensions alone differ from the incumbent ('' if none or several)."""
    out = []
    for x in V.design:
        d = json.loads(x) if isinstance(x, str) else {}
        d.pop("note", None)
        if not set(variants_r3.V1.DIMS) <= set(d):
            out.append("")
            continue
        f = dict(variants_r3.BASE3)
        f.update(d)
        changed = {k for k in f if f[k] != variants_r3.BASE3[k]}
        fams = [n for n, dims in FAM_DIMS.items() if changed and changed <= set(dims)]
        out.append(fams[0] if fams else "")
    return np.array(out)


def n_changed(V):
    out = []
    for x in V.design:
        d = json.loads(x) if isinstance(x, str) else {}
        d.pop("note", None)
        if not set(variants_r3.V1.DIMS) <= set(d):
            out.append(-1)
            continue
        f = dict(variants_r3.BASE3)
        f.update(d)
        out.append(sum(f[k] != variants_r3.BASE3[k] for k in f))
    return np.array(out)


def main(rounds):
    V, cols, E = analyze.load()
    V = V.set_index("id").loc[cols].reset_index()
    keep = V["round"].isin(rounds).to_numpy()
    V, E = V[keep].reset_index(drop=True), E[:, keep]
    base = V[V.id == "base"].iloc[0]
    j0 = int(np.nonzero(V.id.to_numpy() == "base")[0][0])
    nh = ((V.sharpe_m250 >= base.sharpe_m250 - 1e-12) & (V.sharpe_b1m >= base.sharpe_b1m - 0.05)).to_numpy()
    X, has_d = design_matrix(V)
    rnd = (V.origin.to_numpy() == "random") & has_d
    Xr_pinv = np.linalg.pinv(X[rnd])
    fam = family_of(V)
    nch = n_changed(V)
    n, N = E.shape
    S = 16
    blocks = np.array_split(np.arange(n), S)
    b1 = np.array([E[b].sum(0) for b in blocks])
    b2 = np.array([(E[b] ** 2).sum(0) for b in blocks])
    b3 = np.array([(E[b] ** 3).sum(0) for b in blocks])
    b4 = np.array([(E[b] ** 4).sum(0) for b in blocks])
    nb = np.array([len(b) for b in blocks])
    blk_of = np.concatenate([[i] * len(b) for i, b in enumerate(blocks)])
    ann = math.sqrt(365)

    def moments(mask):
        k = nb[mask].sum()
        m1 = b1[mask].sum(0) / k
        m2 = b2[mask].sum(0) / k
        m3 = b3[mask].sum(0) / k
        m4 = b4[mask].sum(0) / k
        var = m2 - m1 ** 2
        sd = np.sqrt(var * k / (k - 1))
        sr = m1 / sd
        mu3 = m3 - 3 * m1 * m2 + 2 * m1 ** 3
        mu4 = m4 - 4 * m1 * m3 + 6 * m1 ** 2 * m2 - 3 * m1 ** 4
        g3 = mu3 / var ** 1.5
        g4 = mu4 / var ** 2
        se = np.sqrt(np.maximum(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-9) / k)
        return sr * ann, se * ann, k

    def sharpe_series(x):
        return x.mean() / x.std(ddof=1) * ann

    rules = (["max_all", "max_nh", "lcb_nh", "ols_nh", "shr50_nh", "ens10_nh", "ens10_ols"] + [f"fam_{f}" for f in FAM_DIMS]
             + ["single_nh"])
    res = {r: [] for r in rules}
    is_gain = {r: [] for r in rules}
    picks = {r: {} for r in rules}
    for comb in itertools.combinations(range(S), S // 2):
        m = np.zeros(S, bool)
        m[list(comb)] = True
        si, sei, _ = moments(m)
        so, _, _ = moments(~m)
        oos_rows = ~m[blk_of]
        is_rows = m[blk_of]
        beta = Xr_pinv @ si[rnd]
        fit = np.where(has_d, X @ beta, -np.inf)

        def arg(score, mask):
            sc = np.where(mask, score, -np.inf)
            return int(np.argmax(sc))

        def top(score, mask, k=10):
            sc = np.where(mask, score, -np.inf)
            return np.argsort(-sc)[:k]

        choice = {"max_all": arg(si, np.ones(N, bool)), "max_nh": arg(si, nh), "lcb_nh": arg(si - sei, nh),
                  "ols_nh": arg(fit, nh & has_d), "shr50_nh": arg(np.where(has_d, 0.5 * fit + 0.5 * si, si), nh)}
        for f in FAM_DIMS:
            mk = (fam == f) | (np.arange(N) == j0)
            choice[f"fam_{f}"] = arg(si, mk)
        choice["single_nh"] = arg(si, (nch == 1) & nh)
        for r, j in choice.items():
            res[r].append(so[j] - so[j0])
            is_gain[r].append(si[j] - si[j0])
            picks[r][V.id[j]] = picks[r].get(V.id[j], 0) + 1
        for r, idx in (("ens10_nh", top(si, nh)), ("ens10_ols", top(fit, nh & has_d))):
            avg = E[:, idx].mean(1)
            res[r].append(sharpe_series(avg[oos_rows]) - so[j0])
            is_gain[r].append(sharpe_series(avg[is_rows]) - si[j0])
    lines = [f"Selection-rule tournament (CSCV, 16 blocks, 12,870 half-splits); rounds {rounds}; {N} variants",
             "Mean out-of-sample half ΔSharpe vs the incumbent (blended $250K), and the in-sample Δ it came from", "",
             f"{'rule':12s} {'IS Δ':>7s} {'OOS Δ':>7s} {'OOS/IS':>7s} {'P(OOS Δ>0)':>11s} {'p10':>7s} {'p90':>7s}  most picked"]
    for r in rules:
        a, b = np.array(res[r]), np.array(is_gain[r])
        top3 = sorted(picks[r].items(), key=lambda z: -z[1])[:3] if picks[r] else []
        lines.append(f"{r:12s} {b.mean():7.3f} {a.mean():7.3f} {a.mean() / b.mean() if b.mean() else float('nan'):7.2f} "
                     f"{np.mean(a > 0):11.2f} {np.quantile(a, 0.1):7.3f} {np.quantile(a, 0.9):7.3f}  "
                     + ", ".join(f"{k} ({v / len(a):.0%})" for k, v in top3))
    txt = "\n".join(lines) + "\n"
    tag = "".join(str(r) for r in rounds)
    open(os.path.join(OUT, f"select_rules_r{tag}.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    rr = [int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "1,2,3").split(",")]
    main(rr)
