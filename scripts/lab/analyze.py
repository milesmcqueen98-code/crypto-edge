#!/usr/bin/env python3
"""Wick v2 lab analysis: shortlist (validation only), walk-forward variant selection, probability of
backtest overfitting (CSCV) and deflated Sharpe. Holdout numbers are printed only with --holdout, after
the shortlist file exists (reports/lab/shortlist.json)."""
import itertools
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

OUT = os.path.join(core.ROOT, "reports", "lab")


def load(tags):
    V = pd.concat([pd.read_csv(os.path.join(OUT, f"results_val_{t}.csv")) for t in tags], ignore_index=True)
    R = pd.concat([pd.read_parquet(os.path.join(OUT, f"daily_real_{t}.parquet")) for t in tags], axis=1)
    B = pd.concat([pd.read_parquet(os.path.join(OUT, f"daily_base_{t}.parquet")) for t in tags], axis=1)
    V = V.drop_duplicates("variant", keep="last")
    R = R.loc[:, ~R.columns.duplicated(keep="last")]
    B = B.loc[:, ~B.columns.duplicated(keep="last")]
    return V, R, B


def sharpe(x):
    sd = x.std()
    return x.mean() / sd * np.sqrt(365) if sd > 0 else np.nan


def pbo_cscv(M, S=16):
    """Bailey et al. (2017): share of in-sample/out-of-sample splits where the in-sample best variant ranks
    below the out-of-sample median."""
    M = M.to_numpy()
    T, N = M.shape
    edges = np.linspace(0, T, S + 1).astype(int)
    s1 = np.array([M[edges[i]:edges[i + 1]].sum(0) for i in range(S)])
    s2 = np.array([(M[edges[i]:edges[i + 1]] ** 2).sum(0) for i in range(S)])
    n = np.array([edges[i + 1] - edges[i] for i in range(S)])
    lam = []
    for comb in itertools.combinations(range(S), S // 2):
        ins = np.zeros(S, dtype=bool)
        ins[list(comb)] = True
        def sr(mask):
            nn = n[mask].sum()
            mu = s1[mask].sum(0) / nn
            var = s2[mask].sum(0) / nn - mu ** 2
            return mu / np.sqrt(np.maximum(var, 1e-18))
        a, b = sr(ins), sr(~ins)
        best = np.nanargmax(a)
        omega = (np.argsort(np.argsort(b))[best] + 1) / (N + 1)
        lam.append(math.log(omega / (1 - omega)))
    lam = np.array(lam)
    return float((lam <= 0).mean()), lam


def deflated_sharpe(x, trial_srs, n_trials):
    """Bailey & López de Prado (2014). x: daily returns of the chosen variant; trial_srs: daily Sharpe of the
    trials (to estimate their dispersion); n_trials: number of independent-ish trials."""
    x = np.asarray(x)
    T = len(x)
    sr = x.mean() / x.std()
    g3 = pd.Series(x).skew()
    g4 = pd.Series(x).kurt() + 3
    v = np.var(trial_srs, ddof=1)
    em = 0.5772156649
    sr0 = math.sqrt(v) * ((1 - em) * norm.ppf(1 - 1 / n_trials) + em * norm.ppf(1 - 1 / (n_trials * math.e)))
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    return float(norm.cdf(z)), sr0 * math.sqrt(365)


def walk_forward_selection(R, base="V000 base (v1)"):
    q = R.index.to_period("Q")
    quarters = sorted(set(q))
    picks, parts = [], []
    for i, qq in enumerate(quarters):
        if i < 2:
            continue
        past = R[q < qq]
        best = past.apply(sharpe).idxmax()
        picks.append((str(qq), best))
        parts.append(R.loc[q == qq, best])
    meta = pd.concat(parts)
    b = R.loc[meta.index, base]
    return meta, b, picks


def main():
    tags = [t for t in ("round1", "round1b", "round2") if os.path.exists(os.path.join(OUT, f"results_val_{t}.csv"))]
    V, R, B = load(tags)
    base = "V000 base (v1)"
    elig = V[V.val_trades >= 150].copy()
    elig = elig.sort_values("val_real_sharpe", ascending=False)
    b0 = V.set_index("variant").loc[base]
    pd.set_option("display.width", 250)
    cols = ["variant", "family", "val_real_sharpe", "val_real_t", "val_real_ann", "val_real_maxdd", "val_base_sharpe",
            "val_trades", "val_net_real_bp", "val_hit"]
    print(f"{len(V)} variants ({', '.join(tags)}); base validation realistic Sharpe {b0.val_real_sharpe:.2f} "
          f"(base-cost {b0.val_base_sharpe:.2f}), trades {b0.val_trades}")
    print("\nTop 25 by validation realistic Sharpe:")
    print(elig[cols].head(25).round(2).to_string(index=False))
    print("\nBy family (best / median / share beating base):")
    fam = V.groupby("family").val_real_sharpe.agg(["count", "max", "median"])
    fam["beat_base"] = V.groupby("family").val_real_sharpe.apply(lambda s: (s > b0.val_real_sharpe).mean())
    print(fam.round(2).to_string())
    print("\nWorst 10:")
    print(V.sort_values("val_real_sharpe")[cols].head(10).round(2).to_string(index=False))
    # paired comparison with the base on validation days (is the improvement distinguishable from noise?)
    Rv = R[(R.index >= core.VAL[0]) & (R.index < core.VAL[1])]
    top = elig.head(25).copy()
    dif = Rv[top.variant].sub(Rv[base], axis=0)
    top["d_sharpe"] = top.val_real_sharpe - b0.val_real_sharpe
    top["paired_t"] = (dif.mean() / dif.std() * np.sqrt(len(dif))).reindex(top.variant).to_numpy()
    top["corr_base"] = Rv[top.variant].corrwith(Rv[base]).reindex(top.variant).to_numpy()
    print("\nTop 25 vs base on validation days (paired t of daily differences, correlation with base):")
    print(top[["variant", "val_real_sharpe", "d_sharpe", "paired_t", "corr_base"]].round(2).to_string(index=False))
    if "--holdout" not in sys.argv:
        # selection phase: validation window only (the pre-registered full-window statistics need the holdout)
        M = Rv.loc[:, V.variant]
        pbo, lam = pbo_cscv(M)
        print(f"\nPBO (CSCV, 16 blocks, {M.shape[1]} variants, VALIDATION window only): {pbo:.3f}; "
              f"median logit {np.median(lam):.2f}")
        meta, b, picks = walk_forward_selection(M)
        print(f"Walk-forward variant selection within validation (2025Q3-2026Q1): Sharpe {sharpe(meta):.2f} vs base "
              f"{sharpe(b):.2f}")
        print("  picks:", picks)
        return
    # pre-registered diagnostics on the full 2025-01 .. 2026-11 realistic daily returns (uses the holdout)
    M = R.loc[:, V.variant]
    pbo, lam = pbo_cscv(M)
    print(f"\nPBO (CSCV, 16 blocks, {M.shape[1]} variants, full window): {pbo:.3f}; median logit {np.median(lam):.2f}")
    meta, b, picks = walk_forward_selection(M)
    print(f"Walk-forward variant selection 2025Q3-2026Q4: Sharpe {sharpe(meta):.2f} vs base {sharpe(b):.2f} "
          f"(return {meta.sum():.1%} vs {b.sum():.1%})")
    print("  picks:", picks)
    hq = meta.index >= core.HOLD[0]
    print(f"  of which holdout quarters: Sharpe {sharpe(meta[hq]):.2f} vs base {sharpe(b[hq]):.2f}")
    json.dump({"pbo": pbo, "wf_sharpe": sharpe(meta), "wf_base_sharpe": sharpe(b), "picks": picks,
               "wf_hold_sharpe": sharpe(meta[hq]), "wf_hold_base_sharpe": sharpe(b[hq])},
              open(os.path.join(OUT, "overfit_stats.json"), "w"), indent=1)
    if "--holdout" in sys.argv:
        sl = json.load(open(os.path.join(OUT, "shortlist.json")))
        Hh = pd.concat([pd.read_csv(os.path.join(OUT, f"results_hold_{t}.csv")) for t in tags]).drop_duplicates("variant", keep="last")
        Hh = Hh.set_index("variant")
        rows = []
        n_trials = len(V)
        trial_srs = M.loc[M.index < core.VAL[1]].apply(lambda s: s.mean() / s.std()).dropna().to_numpy()
        for name in sl["variants"] + [base]:
            h = Hh.loc[name]
            x = M[name]
            dsr_v2, sr0 = deflated_sharpe(x, trial_srs, n_trials)
            dsr_all, _ = deflated_sharpe(x, trial_srs, n_trials + 2000)
            rows.append(dict(variant=name, val_real=V.set_index("variant").loc[name, "val_real_sharpe"],
                             hold_real=h.hold_real_sharpe, hold_base=h.hold_base_sharpe, hold_trades=h.hold_trades,
                             hold_net_bp=h.hold_net_real_bp, full_real=sharpe(x), dsr_v2=dsr_v2, dsr_with_2000=dsr_all))
        ens = M[sl["ens10"]].mean(axis=1)
        hold_mask = ens.index >= core.HOLD[0]
        rows.append(dict(variant="ENS10 (equal-weight top 10)", val_real=sharpe(ens[~hold_mask]), hold_real=sharpe(ens[hold_mask]),
                         full_real=sharpe(ens)))
        H = pd.DataFrame(rows)
        print("\nHOLDOUT (2026-04-01 .. 2026-11-05), realistic costs unless noted:")
        print(H.round(3).to_string(index=False))
        H.to_csv(os.path.join(OUT, "holdout_report.csv"), index=False)


if __name__ == "__main__":
    main()
