#!/usr/bin/env python3
"""AI layer for the resting-bid dip buyer: which signals matter, and does a learned filter help?

Primary rule: 60-minute residual resting bid at k = 4 (loose, many candidate fills).
For every minute t where that bid would fill (opened above it, traded through it by one futures tick),
features are taken at t-1 (everything known when the order is placed) and the label is the net bp of a
single trade entered at the bid (take-profit theta*k*sigma as maker, else market exit after H minutes).

Model: LightGBM regression, walk-forward by calendar quarter (expanding window, 1-day embargo), first
model trained on 2024 only. Filter rule fixed in advance: keep the order live only if the predicted net
edge is above the median prediction on that model's own training data. The filtered strategy is then
re-simulated exactly (bid masked where the model says no). Also reports quintile tables per feature
and feature importance (gain and mean |SHAP|).
Writes reports/wick_ai_importance.csv, reports/wick_ai_quintiles.csv, reports/wick_ai_results.csv
"""
import os
import sys
import time

import lightgbm as lgb
import numba
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wick_sim as ws  # noqa: E402
import wick_robust as wr  # noqa: E402

ROOT = ws.ROOT
L, K, THETA, H = 60, 4.0, 0.6, 60
COINS = [c for c in ws.ALTS if c != "AVAX"]
TT, FEES = 1, "pct2"          # fill needs TT futures ticks of trade-through; fee model (see wick_robust.fee_bp)


def net_of_costs(c, ep, xp, ty):
    gross = np.log(xp / ep) * 1e4
    hs = ws.PERP[c][2] / ep * 1e4                                  # half-spread = one futures tick
    f_in = wr.fee_bp(FEES, c, ep, True)
    f_out = np.where(ty == 1, wr.fee_bp(FEES, c, xp, True), wr.fee_bp(FEES, c, xp, False) + hs)
    return gross, gross - f_in - f_out


@numba.njit(cache=True)
def single_trades(cand, O, Hh, Lo, Cf, lvl, tpd, tick, hmax):
    """Outcome of one long trade entered at lvl[t] for each candidate fill minute t."""
    n = len(cand)
    xp = np.full(n, np.nan)
    ty = np.zeros(n, np.int8)
    T = len(O)
    for j in range(n):
        t = cand[j]
        e = lvl[t]
        tp = e * np.exp(tpd[t]) if not np.isnan(tpd[t]) else np.inf
        for u in range(t + 1, min(T, t + hmax + 1)):
            if not np.isnan(Hh[u]) and Hh[u] >= tp * (1.0 + tick[u]):
                xp[j] = tp
                ty[j] = 1
                break
            if u - t >= hmax:
                xp[j] = Cf[u]
                ty[j] = 3
                break
    return xp, ty


def rolling_z(x, w=ws.W):
    s = pd.Series(x)
    return (s / s.rolling(w, min_periods=1440).std()).to_numpy()


def build(D, P, idx):
    lpb = P.lp["BTC"]
    btc_r = {h: lpb - ws.shift(lpb, h) for h in (5, 15, 60, 240, 1440)}
    btc_z = {h: rolling_z(btc_r[h]) for h in (5, 15, 60)}
    r1b = np.diff(lpb, prepend=np.nan)
    btc_vr = (pd.Series(r1b).rolling(60).std() / pd.Series(r1b).rolling(ws.W, min_periods=1440).std()).to_numpy()
    vb = D["BTC"]["vol"]
    btc_volr = (pd.Series(vb).rolling(15).sum() / (pd.Series(vb).rolling(ws.W, min_periods=1440).mean() * 15)).to_numpy()
    # residual z per coin for several horizons (for breadth features)
    zres = {}
    for c in COINS:
        lp = P.lp[c]
        b = ws.shift(P.beta[c], -1)
        for h in (15, 60):
            zres[c, h] = rolling_z((lp - ws.shift(lp, h)) - b * btc_r[h])
    rows = []
    for c in COINS:
        o, hh, lo, cf, vol = (D[c][k] for k in ("open", "high", "low", "cf", "vol"))
        lvl, sig = P.level(c, L, K, 1, "resid")
        tick = np.nan_to_num(TT * ws.PERP[c][2] / cf, nan=1.0)
        with np.errstate(invalid="ignore"):
            fill = (o > lvl) & (lo <= lvl * (1 - tick))
        cand = np.where(fill)[0]
        cand = cand[cand > 1500]
        tpd = THETA * K * sig if np.isfinite(THETA) else np.full_like(sig, np.nan)
        xp, ty = single_trades(cand, o, hh, lo, cf, lvl, tpd, tick, H)
        ep = lvl[cand]
        gross, net = net_of_costs(c, ep, xp, ty)
        lp = P.lp[c]
        r1 = np.diff(lp, prepend=np.nan)
        vr = (pd.Series(r1).rolling(60).std() / pd.Series(r1).rolling(ws.W, min_periods=1440).std()).to_numpy()
        volr = (pd.Series(vol).rolling(15).sum() / (pd.Series(vol).rolling(ws.W, min_periods=1440).mean() * 15)).to_numpy()
        hi240 = pd.Series(cf).rolling(240, min_periods=60).max().to_numpy()
        lo240 = pd.Series(cf).rolling(240, min_periods=60).min().to_numpy()
        hi1d = pd.Series(cf).rolling(1440, min_periods=600).max().to_numpy()
        z1 = rolling_z(r1)
        p = cand - 1                                               # features at t-1
        others = [x for x in COINS if x != c]
        br60 = np.nanmean(np.vstack([zres[x, 60][p] for x in others]), axis=0)
        brn = np.nansum(np.vstack([zres[x, 60][p] < -2 for x in others]), axis=0)
        f = pd.DataFrame({
            "ts": idx[cand], "coin": c, "episode": np.cumsum(np.r_[1, np.diff(cand) > 1]), "net_bp": net,
            "gross_bp": gross, "exit_type": ty,
            "z_res60": zres[c, 60][p], "z_res15": zres[c, 15][p], "z_1min": z1[p],
            "bid_depth_bp": K * sig[cand] * 1e4,
            "btc_z5": btc_z[5][p], "btc_z15": btc_z[15][p], "btc_z60": btc_z[60][p],
            "btc_ret240_bp": btc_r[240][p] * 1e4, "btc_ret1d_bp": btc_r[1440][p] * 1e4,
            "coin_ret1d_bp": (lp - ws.shift(lp, 1440))[p] * 1e4, "coin_ret7d_bp": (lp - ws.shift(lp, 10080))[p] * 1e4,
            "dist_1d_high_bp": (np.log(cf / hi1d))[p] * 1e4,
            "range_pos240": ((cf - lo240) / (hi240 - lo240))[p],
            "vol_ratio_60m_3d": vr[p], "btc_vol_ratio": btc_vr[p],
            "volume_ratio_15m": volr[p], "btc_volume_ratio_15m": btc_volr[p],
            "alts_mean_z60": br60, "alts_below_2sd": brn,
            "beta": P.beta[c][cand],
            "hour_utc": idx[cand].hour, "weekend": (idx[cand].dayofweek >= 5).astype(int),
        })
        rows.append(f)
        print(f"  {c}: {len(cand)} candidate fill minutes", flush=True)
    X = pd.concat(rows, ignore_index=True).dropna(subset=["net_bp"])
    X["coin_id"] = X.coin.astype("category").cat.codes
    return X


FEATS = ["z_res60", "z_res15", "z_1min", "bid_depth_bp", "btc_z5", "btc_z15", "btc_z60", "btc_ret240_bp",
         "btc_ret1d_bp", "coin_ret1d_bp", "coin_ret7d_bp", "dist_1d_high_bp", "range_pos240", "vol_ratio_60m_3d",
         "btc_vol_ratio", "volume_ratio_15m", "btc_volume_ratio_15m", "alts_mean_z60", "alts_below_2sd", "beta",
         "hour_utc", "weekend", "coin_id"]
PARAMS = dict(objective="huber", alpha=60.0, learning_rate=0.03, num_leaves=7, min_data_in_leaf=60,
              feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, seed=7)


def walk_forward(X):
    X = X.sort_values("ts").reset_index(drop=True)
    X["pred"] = np.nan
    X["thr"] = np.nan
    quarters = pd.period_range("2025Q1", "2026Q4", freq="Q")
    imps, shaps = [], []
    for q in quarters:
        qs, qe = q.start_time, q.end_time
        tr = X[X.ts < qs - pd.Timedelta(days=1)]
        te = X[(X.ts >= qs) & (X.ts <= qe)]
        if te.empty:
            continue
        # one episode = consecutive candidate minutes; weight each episode equally in training
        w = 1.0 / tr.groupby(["coin", "episode"]).ts.transform("size")
        m = lgb.train(PARAMS, lgb.Dataset(tr[FEATS], tr.net_bp.clip(-400, 400), weight=w,
                                          categorical_feature=["coin_id"]), num_boost_round=250)
        ptr = m.predict(tr[FEATS])
        X.loc[te.index, "pred"] = m.predict(te[FEATS])
        X.loc[te.index, "thr"] = np.median(ptr)
        imps.append(pd.Series(m.feature_importance("gain"), index=FEATS, name=str(q)))
        sh = m.predict(te[FEATS], pred_contrib=True)[:, :-1]
        shaps.append(pd.Series(np.abs(sh).mean(axis=0), index=FEATS, name=str(q)))
        print(f"  {q}: trained on {len(tr)} candidates, predicting {len(te)}", flush=True)
    return X, pd.concat(imps, axis=1), pd.concat(shaps, axis=1)


def simulate_masked(D, P, idx, X, rule):
    """Re-run the sequential book with the bid switched off where the model says no."""
    trs = []
    for c in COINS:
        lvl, sig = P.level(c, L, K, 1, "resid")
        if rule is not None:
            xc = X[X.coin == c]
            bad = xc.loc[~rule(xc), "ts"]
            pos = idx.get_indexer(bad)
            lvl = lvl.copy()
            lvl[pos[pos >= 0]] = np.nan
        cf = D[c]["cf"]
        tick = np.nan_to_num(TT * ws.PERP[c][2] / cf, nan=1.0)
        tpd = THETA * K * sig if np.isfinite(THETA) else np.full_like(sig, np.nan)
        ei, xi, ep, xp, ty = ws.run_book(D[c]["open"], D[c]["high"], D[c]["low"], cf, lvl, tpd,
                                         np.full_like(sig, np.nan), 1, tick, H, 0)
        gross, net = net_of_costs(c, ep, xp, ty)
        trs.append(pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "net_bp": net, "gross_bp": gross,
                                 "type": ty, "hold_min": xi - ei, "entry_px": ep}))
    return pd.concat(trs, ignore_index=True)


def main():
    t0 = time.time()
    idx, D = ws.load_ohlc(coins=["BTC"] + COINS)
    P = ws.Prep(D, (L, 15))
    X = build(D, P, idx)
    print(f"{len(X)} candidate fills with features ({time.time() - t0:.0f}s)", flush=True)

    # ---- which signals matter: quintile tables on the design year and the test period, episode-first fills
    first = X.drop_duplicates(["coin", "episode"])
    qrows = []
    for f in FEATS:
        if f in ("coin_id", "weekend"):
            continue
        for lab, m in [("design", first.ts < ws.TEST_START), ("test", first.ts >= ws.TEST_START)]:
            x = first[m]
            try:
                b = pd.qcut(x[f], 5, labels=False, duplicates="drop")
            except ValueError:
                continue
            g = x.groupby(b).net_bp.agg(["mean", "size"])
            for qi, r in g.iterrows():
                qrows.append(dict(feature=f, period=lab, quintile=int(qi) + 1, net_bp=r["mean"], n=int(r["size"])))
    Q = pd.DataFrame(qrows)
    Q.to_csv(os.path.join(ROOT, "reports", "wick_ai_quintiles.csv"), index=False)
    spread = Q.pivot_table(index=["feature"], columns=["period", "quintile"], values="net_bp")
    spread[("design", "Q5-Q1")] = spread[("design", 5)] - spread[("design", 1)]
    spread[("test", "Q5-Q1")] = spread[("test", 5)] - spread[("test", 1)]
    print("\nNet bp per trade by feature quintile (episode-first fills; Q1 = lowest value):")
    print(spread.round(1).sort_values(("design", "Q5-Q1")).to_string())

    # ---- walk-forward model
    X, imp, shap = walk_forward(X)
    I = pd.DataFrame({"gain_share": imp.sum(axis=1) / imp.sum().sum(), "mean_abs_shap_bp": shap.mean(axis=1)})
    I = I.sort_values("mean_abs_shap_bp", ascending=False)
    I.to_csv(os.path.join(ROOT, "reports", "wick_ai_importance.csv"))
    print("\nFeature importance (walk-forward models, 2025-26):")
    print(I.round(3).to_string())

    te = X[X.ts >= ws.TEST_START]
    print(f"\nTest candidates: {len(te)}; corr(pred, net) = {te[['pred', 'net_bp']].corr().iloc[0, 1]:.3f}")
    te_b = pd.qcut(te.pred, 5, labels=False, duplicates="drop")
    print("Test net bp by prediction quintile:", te.groupby(te_b).net_bp.mean().round(1).to_dict())

    res = []
    base = simulate_masked(D, P, idx, X, None)
    filt = simulate_masked(D, P, idx, X, lambda xc: (xc.ts < ws.TEST_START) | (xc.pred > xc.thr))
    strict = simulate_masked(D, P, idx, X, lambda xc: (xc.ts < ws.TEST_START) | (xc.pred > 25.0))
    for name, tr in [("rule only (k=4)", base), ("rule + AI filter (pred > train median)", filt),
                     ("rule + AI filter (pred > 25 bp)", strict)]:
        tt = tr[tr.ts >= ws.TEST_START]
        d = wr.daily(tr)
        s = wr.sstats(d, wr.TST)
        ndays = (pd.Timestamp(ws.END) - pd.Timestamp(ws.TEST_START)).days
        res.append(dict(strategy=name, test_trades=len(tt), test_per_day=len(tt) / ndays, test_net_bp=tt.net_bp.mean(),
                        test_hit=(tt.net_bp > 0).mean(), **{f"test_{k}": v for k, v in s.items()}))
    R = pd.DataFrame(res)
    R.to_csv(os.path.join(ROOT, "reports", "wick_ai_results.csv"), index=False)
    print("\nTest period 2025-01-01 .. 2026-11-05 (models never saw it):")
    print(R.round(3).to_string(index=False))
    X.to_parquet(os.path.join(ROOT, "reports", "wick_ai_candidates.parquet"), index=False)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
