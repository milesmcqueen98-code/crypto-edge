#!/usr/bin/env python3
"""Edge hunt 2, IMP (reports/hunt2/imp/SPEC.md): was the drop paid for by selling? A square-root-law impact residual as
a filter on R2-08's ladder (Path A, frozen simulator).

usage (from the worktree):
  python scripts/hunt2/imp/imp.py features sel     DEV features (parents' print features + BTC candles), era fixed
  python scripts/hunt2/imp/imp.py dev              the 8 DEV trials (logged), dev_trials.csv
  python scripts/hunt2/imp/imp.py freeze           the fixed selection rule -> frozen.json (commit = the freeze)
  python scripts/hunt2/imp/imp.py hold             AFTER the freeze commit and the post-freeze features_hold.csv run

Formulas (REPORT, "Formulas"), for a parent (coin c, fill minute t, first trade-through t_fill) and W in {5, 15, 30}:
  inputs   usd_W, sell_share_W, ret_bp_W: prints in [t_fill - W min - 1 s, t_fill - 1 s) (reports/hunt2/parents/
           features_*.csv; sell share = aggressive sellers' notional share, Coinbase side = maker side);
           vol_d (sigma_D, daily) and adv (V_D, USD/day) of the frozen dataset (reports/hunt2/parents/windows.csv)
  Q_W      = usd_W (2 sell_share_W - 1)                      net aggressive selling, USD
  r_W      = -ln(1 + ret_bp_W / 1e4)                         the coin's log return, first to last print of the window
           SHARED-CODE BUG, corrected here (DEVIATION, decided before any trial, no outcomes seen): the prints are
           stored newest-first (scripts/wick_v4/fetch_trades.py fetch_window walks backward) and parent_features.py
           takes px[-1] / px[0] - 1 on that order, so ln(1 + ret_bp_W / 1e4) is exactly minus the true log return
           (DEV check: corr with the candle return over the same minutes -0.84 / -0.95 / -0.96 for W = 5 / 15 / 30).
           The same code produced features_dev.csv and features_hold.csv, so the same correction applies to both.
           Logged centrally in reports/hunt2_prereg.md's deviation log (commit d0eb624 on branch hunt2), before any
           IMP trial. dist_lvl_bp_W (also order-dependent) is not used anywhere in this build.
  rb_W     = lf_BTC[t-1] - lf_BTC[t-1-W]                     BTC's log return over the W minutes before the fill
           minute (1-minute candle closes, forward-filled <= 30 minutes; known at the start of minute t)
  beta     = R2-08's 7-day beta through minute t-1 (the SHAPE helper; reproduces the frozen levels exactly)
  D_W      = -(r_W - beta rb_W)                              residual drop (positive for a drop)
  I_W      = sigma_D sqrt(max(Q_W, 0) / V_D)                 flow-implied impact (Y omitted)
  f_W      = D_W / I_W if Q_W > 0; +inf if Q_W <= 0 and D_W > 0; NaN (kept) if Q_W <= 0 and D_W <= 0   skip HIGH
  rate_15  = (Q_15 / 15) / (V_D / 1440)                      selling rate vs an average minute's volume  skip LOW
  A missing input -> NaN (kept).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "shape"))
sys.path.insert(0, "/home/claude/crypto-edge/scripts/hunt2")
import shp_common as C  # noqa: E402
import shp_rules as rules  # noqa: E402

IDEA = "imp"
OUT = os.path.join(rules.WT, "reports", "hunt2", IDEA)
PAR = os.path.join(rules.WT, "reports", "hunt2", "parents")
WINS = (5, 15, 30)
FEATS = {"f_5": "high", "f_15": "high", "f_30": "high", "rate_15": "low"}
WOF = {"f_5": 5, "f_15": 15, "f_30": 30, "rate_15": 15}
SHARES = (0.15, 0.30)
GRID = [(f, s) for f in FEATS for s in SHARES]          # 8 trials, in this order


def variant_name(f, s):
    return f"{f}_{int(round(100 * s))}"


def parent_list(era):
    import pathA
    return pathA.parents(era)[["ts", "coin", "lvl", "vol_d", "adv"]].copy()


def print_features(era):
    rules.require_frozen(IDEA, era)
    name = "features_dev.csv" if era == "sel" else "features_hold.csv"
    cols = ["window_id", "coin", "ts", "era", "flag", "t_fill"] + [f"{k}_{W}" for W in WINS
                                                                    for k in ("usd", "sell_share", "ret_bp")]
    X = pd.read_csv(os.path.join(PAR, name), usecols=cols, parse_dates=["ts", "t_fill"])
    X = X[X.era == era].reset_index(drop=True)
    return X


def features(era):
    rules.require_frozen(IDEA, era)
    tag = C.ERA_TAG[era]
    par = parent_list(era)
    X = print_features(era)
    Wn = pd.read_csv(os.path.join(PAR, "windows.csv"), usecols=["window_id", "coin", "ts", "vol_d", "adv"],
                     parse_dates=["ts"])
    X = X.merge(Wn, on="window_id", how="left", suffixes=("", "_w"))
    assert (X.ts == X.ts_w).all() and (X.coin == X.coin_w).all()
    key = lambda d: sorted(zip(pd.to_datetime(d.ts), d.coin))  # noqa: E731
    assert key(X) == key(par), f"{era}: print features do not cover exactly the research parents"
    if era == "sel":
        import h2gates as G
        assert G.is_dev(X.ts.dt.floor("D")).all()
    lb = C.load_cf(tag, "BTC")
    rbt = C.returns(lb)
    out = []
    for coin, g in X.groupby("coin", sort=True):
        b = C.rbeta(C.returns(C.load_cf(tag, coin)), rbt, C.WBETA)
        pos = C.positions(tag, g.ts)
        assert (pos >= 0).all()
        g = g.copy()
        g["beta"] = b[pos - 1]
        for W in WINS:
            g[f"rb_{W}"] = lb[pos - 1] - lb[pos - 1 - W]
        out.append(g)
    X = pd.concat(out).sort_values(["ts", "coin"]).reset_index(drop=True)
    sd, vd = X.vol_d.to_numpy(float), X.adv.to_numpy(float)
    for W in WINS:
        Q = X[f"usd_{W}"].to_numpy(float) * (2 * X[f"sell_share_{W}"].to_numpy(float) - 1)
        r = -np.log1p(X[f"ret_bp_{W}"].to_numpy(float) / 1e4)        # sign: see the docstring (shared-code bug)
        D = -(r - X.beta.to_numpy(float) * X[f"rb_{W}"].to_numpy(float))
        with np.errstate(invalid="ignore", divide="ignore"):
            I = sd * np.sqrt(np.maximum(Q, 0.0) / vd)
            f = np.where(Q > 0, D / I, np.where((Q <= 0) & (D > 0), np.inf, np.nan))
        f[~(np.isfinite(Q) & np.isfinite(D) & np.isfinite(sd) & np.isfinite(vd))] = np.nan
        X[f"Q_{W}"], X[f"r_{W}"], X[f"D_{W}"], X[f"I_{W}"], X[f"f_{W}"] = Q, r, D, I, f
    X["rate_15"] = (X["Q_15"] / 15.0) / (X.adv / 1440.0)
    keep = ["ts", "coin", "t_fill", "flag", "vol_d", "adv", "beta"] + [f"{k}_{W}" for W in WINS for k in
                                                                       ("Q", "r", "rb", "D", "I", "f")] + ["rate_15"]
    X = X[keep]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"features_{era}.csv")
    X.to_csv(path, index=False)
    print(f"{era}: {len(X)} parents, missing: " + ", ".join(f"{k} {int(X[k].isna().sum())}" for k in FEATS)
          + f" -> {path}")
    return X


def load_features(era):
    rules.require_frozen(IDEA, era)
    return pd.read_csv(os.path.join(OUT, f"features_{era}.csv"), parse_dates=["ts", "t_fill"])


def dev():
    import pathA
    F = load_features("sel")
    par = parent_list("sel")
    key = lambda d: sorted(zip(pd.to_datetime(d.ts), d.coin))  # noqa: E731
    assert key(F) == key(par), "features do not cover exactly the DEV parents"
    rows, daily = [], {}
    for f, s in GRID:
        side = FEATS[f]
        thr = rules.threshold(F[f], side, s)
        m = rules.skip_mask(F[f], side, thr)
        cells = F.loc[m, ["ts", "coin"]].reset_index(drop=True)
        rules.check_cells("sel", cells)
        v = variant_name(f, s)
        scr, d = pathA.dev_trial(IDEA, v, cells, note=f"skip {side} {f}, share {s}",
                                 feature=f, side=side, share=s, thr=thr, realised_share=float(m.mean()))
        row = dict(variant=v, feature=f, W=WOF[f], side=side, share=s, thr=thr, n_skipped=int(m.sum()),
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
    >= 15% of 1,155 DEV parents); ties -> share 15%, then W = 15."""
    T = pd.read_csv(os.path.join(OUT, "dev_trials.csv"))
    assert len(T) == len(GRID)
    T["tie1"] = (T.share != 0.15).astype(int)
    T["tie2"] = (T.W != 15).astype(int)
    best = T.sort_values(["t_diff", "tie1", "tie2"], ascending=[False, True, True]).iloc[0]
    fz = dict(idea=IDEA, variant=best.variant, feature=best.feature, W=int(best.W), side=best.side,
              share=float(best.share), thr=float(best.thr),
              rule=f"skip the 4-sigma parent when {best.feature} {'>=' if best.side == 'high' else '<='} "
                   f"{best.thr!r} (missing -> keep)",
              code_commit=rules.git_head(), selection="highest DEV paired HAC t at X2; ties -> 15%, then W = 15",
              dev=dict(t_diff=float(best.t_diff), mean_diff_bp=float(best.mean_diff_bp),
                       d_sharpe=float(best.d_sharpe), cand_sharpe=float(best.cand_sharpe),
                       inc_sharpe=float(best.inc_sharpe), n_skipped=int(best.n_skipped),
                       realised_share=float(best.realised_share), top5_share=float(best.top5_share)),
              all_trials=T.drop(columns=["tie1", "tie2"]).to_dict(orient="records"))
    json.dump(fz, open(os.path.join(OUT, "frozen.json"), "w"), indent=1, default=float)
    print(json.dumps({k: fz[k] for k in ("variant", "rule", "code_commit", "dev")}, indent=1, default=float))


def hold():
    """After the freeze commit and the post-freeze HOLD print-feature run only."""
    import pathA
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    for era in ("chk", "early"):
        rules.require_frozen(IDEA, era)
        if not os.path.exists(os.path.join(OUT, f"features_{era}.csv")):
            features(era)
    cells = {}
    for era in ("sel", "chk", "early"):
        F = load_features(era)
        m = rules.skip_mask(F[fz["feature"]], fz["side"], fz["thr"])
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
