#!/usr/bin/env python3
"""Edge hunt 2, SHAPE (reports/hunt2/shape/SPEC.md): air pocket or grind? The drop's shape as a filter on R2-08's
ladder (Path A, frozen simulator).

usage (from the worktree):
  python scripts/hunt2/shape/shape.py features sel      DEV features of every research parent (era fixed to sel)
  python scripts/hunt2/shape/shape.py dev               the 8 DEV trials (logged), dev_trials.csv
  python scripts/hunt2/shape/shape.py freeze            the fixed selection rule -> frozen.json (commit = the freeze)
  python scripts/hunt2/shape/shape.py hold              AFTER the freeze commit: HOLD features, the HOLD read, gates

Features of a parent (coin c, fill minute t), computed from 1-minute candles known at t-1 (REPORT, "Formulas"):
  r_k  = log cf_c[k] - log cf_c[k-1] (cf: close forward-filled <= 30 minutes, R2-08's grid); rb_k the same for BTC
  beta = R2-08's 7-day beta through minute t-1 (b[t-1]; verified: it reproduces the frozen levels exactly)
  e_k  = r_k - beta rb_k, one beta per parent
  PE60    = |sum e| / sum |e|, k in [t-60, t-1]                                        skip HIGH
  JS1_60  = max_k(-e_k) / (-sum e) if sum e < 0, else +inf (the whole drop is still to come)   skip LOW
  JR60    = max(0, 1 - BV / RV), RV = sum e^2, BV = pi/2 sum |e_k||e_{k-1}| (pairs inside the window)  skip LOW
            DEVIATION (decided on the DEV feature distribution, before any trial, no outcomes seen): JR60 is exactly 0
            for 406 of 1,155 DEV parents (35%), so its lowest 15% and 30% are all tied; the JR60 variants therefore rank
            and threshold the untruncated ratio RJ60 = 1 - BV / RV (equal to JR60 wherever JR60 > 0; Huang-Tauchen's
            relative jump measure; more negative = smoother |e|, a grind).
  DRIFT6h = sum e over [t-360, t-1] / (sd(e over [t-43200, t-1]) sqrt(360))              skip LOW
  Missing inputs (fewer than 30 of 60, 180 of 360 or 1,440 of 43,200 valid minutes, RV or sum|e| = 0) -> NaN (kept).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/home/claude/crypto-edge/scripts/hunt2")
import shp_common as C  # noqa: E402
import shp_rules as rules  # noqa: E402

IDEA = "shape"
OUT = os.path.join(rules.WT, "reports", "hunt2", IDEA)
FEATS = {"PE60": "high", "JS1_60": "low", "JR60": "low", "DRIFT6h": "low"}
COL = {"PE60": "PE60", "JS1_60": "JS1_60", "JR60": "RJ60", "DRIFT6h": "DRIFT6h"}   # the column each variant ranks
SHARES = (0.15, 0.30)
GRID = [(f, s) for f in FEATS for s in SHARES]          # 8 trials, in this order


def variant_name(f, s):
    return f"{f}_{int(round(100 * s))}"


def parent_list(era):
    import pathA
    P = pathA.parents(era)
    return P[["ts", "coin", "lvl", "vol_d", "adv"]].copy()


def feats_one(r, rb, p, beta):
    """Features for the parent at grid position p (the fill minute); only minutes <= p-1 are read."""
    out = dict(PE60=np.nan, JS1_60=np.nan, JR60=np.nan, RJ60=np.nan, DRIFT6h=np.nan, beta=beta)
    if not np.isfinite(beta) or p < 43201:
        return out
    e60 = r[p - 60:p] - beta * rb[p - 60:p]
    ok = np.isfinite(e60)
    out["n60"] = int(ok.sum())
    if ok.sum() >= 30:
        tot = float(np.nansum(e60))
        sab = float(np.nansum(np.abs(e60)))
        if sab > 0:
            out["PE60"] = abs(tot) / sab
        out["JS1_60"] = float(np.nanmax(-e60) / (-tot)) if tot < 0 else np.inf
        rv = float(np.nansum(e60 ** 2))
        pr = np.abs(e60[1:]) * np.abs(e60[:-1])
        bv = float(np.pi / 2 * np.nansum(pr))
        if rv > 0:
            out["RJ60"] = 1.0 - bv / rv
            out["JR60"] = max(0.0, out["RJ60"])
        out["ret60_bp"] = 1e4 * tot
    e360 = r[p - 360:p] - beta * rb[p - 360:p]
    e30 = r[p - 43200:p] - beta * rb[p - 43200:p]
    n30 = int(np.isfinite(e30).sum())
    if np.isfinite(e360).sum() >= 180 and n30 >= 1440:
        sd = float(np.nanstd(e30, ddof=1))
        if sd > 0:
            out["DRIFT6h"] = float(np.nansum(e360)) / (sd * np.sqrt(360))
    return out


def features(era):
    rules.require_frozen(IDEA, era)
    tag = C.ERA_TAG[era]
    par = parent_list(era)
    if era == "sel":
        import h2gates as G
        assert G.is_dev(par.ts.dt.floor("D")).all()
    rb = C.returns(C.load_cf(tag, "BTC"))
    rows = []
    for coin, g in par.groupby("coin", sort=True):
        lp = C.load_cf(tag, coin)
        r = C.returns(lp)
        b = C.rbeta(r, rb, C.WBETA)
        pos = C.positions(tag, g.ts)
        assert (pos >= 0).all()
        for (i, row), p in zip(g.iterrows(), pos):
            f = feats_one(r, rb, int(p), float(b[p - 1]))
            rows.append(dict(ts=row.ts, coin=coin, **f))
    F = pd.DataFrame(rows).sort_values(["ts", "coin"]).reset_index(drop=True)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"features_{era}.csv")
    F.to_csv(path, index=False)
    print(f"{era}: {len(F)} parents, missing: " + ", ".join(f"{k} {int(F[k].isna().sum())}" for k in FEATS)
          + f" -> {path}")
    return F


def load_features(era):
    rules.require_frozen(IDEA, era)
    F = pd.read_csv(os.path.join(OUT, f"features_{era}.csv"), parse_dates=["ts"])
    return F


def dev():
    import pathA
    F = load_features("sel")
    par = parent_list("sel")
    key = lambda d: list(zip(pd.to_datetime(d.ts), d.coin))  # noqa: E731
    assert sorted(key(F)) == sorted(key(par)), "features do not cover exactly the DEV parents"
    rows, daily = [], {}
    for f, s in GRID:
        side, col = FEATS[f], COL[f]
        thr = rules.threshold(F[col], side, s)
        m = rules.skip_mask(F[col], side, thr)
        cells = F.loc[m, ["ts", "coin"]].reset_index(drop=True)
        rules.check_cells("sel", cells)
        v = variant_name(f, s)
        scr, d = pathA.dev_trial(IDEA, v, cells, note=f"skip {side} {col}, share {s}",
                                 feature=f, col=col, side=side, share=s, thr=thr, realised_share=float(m.mean()))
        row = dict(variant=v, feature=f, col=col, side=side, share=s, thr=thr, n_skipped=int(m.sum()),
                   realised_share=float(m.mean()), **{k: scr[k] for k in ("t_diff", "mean_diff_bp", "d_sharpe",
                                                                         "cand_sharpe", "inc_sharpe", "top5_share",
                                                                         "n_days")})
        rows.append(row)
        daily[v] = d
        print(json.dumps(row), flush=True)
        pd.DataFrame(rows).to_csv(os.path.join(OUT, "dev_trials.csv"), index=False)
        pd.DataFrame(daily).to_parquet(os.path.join(OUT, "dev_daily.parquet"))
    return pd.DataFrame(rows)


def freeze():
    """Fixed selection: the highest DEV paired HAC t at X2 (the SPEC sets no minimum event count; every variant skips
    >= 15% of 1,155 DEV parents); ties -> share 15%."""
    T = pd.read_csv(os.path.join(OUT, "dev_trials.csv"))
    assert len(T) == len(GRID)
    T["tie"] = (T.share != 0.15).astype(int)
    best = T.sort_values(["t_diff", "tie"], ascending=[False, True]).iloc[0]
    fz = dict(idea=IDEA, variant=best.variant, feature=best.feature, col=best.col, side=best.side,
              share=float(best.share), thr=float(best.thr), rule=f"skip the 4-sigma parent when {best.col} "
              f"{'>=' if best.side == 'high' else '<='} {best.thr!r} (missing -> keep)",
              code_commit=rules.git_head(), selection="highest DEV paired HAC t at X2; ties -> 15%",
              dev=dict(t_diff=float(best.t_diff), mean_diff_bp=float(best.mean_diff_bp),
                       d_sharpe=float(best.d_sharpe), cand_sharpe=float(best.cand_sharpe),
                       inc_sharpe=float(best.inc_sharpe), n_skipped=int(best.n_skipped),
                       realised_share=float(best.realised_share), top5_share=float(best.top5_share)),
              all_trials=T.drop(columns="tie").to_dict(orient="records"))
    json.dump(fz, open(os.path.join(OUT, "frozen.json"), "w"), indent=1, default=float)
    print(json.dumps({k: fz[k] for k in ("variant", "rule", "code_commit", "dev")}, indent=1, default=float))


def hold():
    """After the freeze commit only: HOLD features from candles, then the frozen variant on every era."""
    import pathA
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    for era in ("chk", "early"):
        rules.require_frozen(IDEA, era)
        if not os.path.exists(os.path.join(OUT, f"features_{era}.csv")):
            features(era)
    cells = {}
    for era in ("sel", "chk", "early"):
        F = load_features(era)
        m = rules.skip_mask(F[fz["col"]], fz["side"], fz["thr"])
        cells[era] = F.loc[m, ["ts", "coin"]].reset_index(drop=True)
        rules.check_cells(era, cells[era])
        print(f"{era}: {len(F)} parents, {int(m.sum())} skipped ({m.mean():.3f})", flush=True)
    g = pathA.hold_read(IDEA, cells, OUT)
    g["n_skipped"] = {e: int(len(c)) for e, c in cells.items()}
    json.dump(g, open(os.path.join(OUT, "gates.json"), "w"), indent=1, default=str)
    print(json.dumps(g, indent=1, default=str))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "features":
        features(sys.argv[2])
    elif cmd == "dev":
        dev()
    elif cmd == "freeze":
        freeze()
    elif cmd == "hold":
        hold()
