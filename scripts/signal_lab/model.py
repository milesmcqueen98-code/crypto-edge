#!/usr/bin/env python3
"""Signal lab (reports/signal_lab/prereg.md): R2-08's AI model with other labels and feature sets.

  python scripts/signal_lab/model.py <main|early> screen [SPEC ...]   development screen (selection era only)
  python scripts/signal_lab/model.py <main|early> chain SPEC          full walk-forward + every-minute panel + deep paths

The lab's own pipeline (scripts/lab: levels, candidates, features, walk-forward LightGBM by quarter, 60th-percentile
threshold, per-coin books) is imported, not modified. A spec is a label and a feature set:
  labels    R   R2-08's (one 4-sigma trade, perp per-contract costs)
            S4  the same trade at the spot bot's costs (maker 6 bp in, take-profit maker 6 bp, else taker 12.5 bp + 2 bp)
            LD  the spot ladder's net per dollar of the whole signal: the 4 / 6 / 8-sigma rungs in thirds, each with its
                take-profit at 0.6 of its dislocation, else sold at minute 60; an unfilled rung earns 0
            LS  LD in units of the signal's sigma
  features  F0  R2-08's 23
            F1  + cascade state (sell volume, close location, breadth of fills, time since / count of episodes)
            F2  + multi-horizon position and trend regime
            F3  + all of F1, F2 and calendar
            F4  + implied-volatility and macro regime (Deribit DVOL, variance premium, VIX, Nasdaq futures)
RF0 is the incumbent; its trades must equal reports/wick1m/trades_<era>.parquet.
The screen scores each spec on the frozen simulator (fsim.book, S*: today's volumes, costs x2, theta 0.5, $250K).
"""
import gc
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASE = sys.argv[1] if len(sys.argv) > 1 else "main"
os.environ["LAB_ERA"] = BASE                                 # the lab reads the era at import
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v5"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "lab"))
import core  # noqa: E402
import run as RUN  # noqa: E402
import variants as VV  # noqa: E402
import lightgbm as lgb  # noqa: E402
import numba  # noqa: E402
from edge import wick  # noqa: E402
import fsim  # noqa: E402
import sim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "signal_lab")
os.makedirs(OUT, exist_ok=True)
MAKER_BP, TAKER_BP, HS_BP = 6.0, 12.5, 2.0
MACRO = ["dvol_btc", "dvol_chg24", "vrp_btc", "vix", "nq_ret1d_bp", "nq_ret5d_bp"]
MEMORY = ["mkt_net_24h", "mkt_n_24h", "coin_prev_net", "coin_prev_age"]
FSETS = {"F0": [], "F1": list(core.EXTRA2), "F2": list(core.EXTRA1) + list(core.EXTRA4),
         "F3": list(core.EXTRA1) + list(core.EXTRA2) + list(core.EXTRA3) + list(core.EXTRA4), "F4": list(MACRO),
         "F5": list(MEMORY)}
LABELS = ("R", "S4", "LD", "LS")
SPECS = [f"{l}{f}" for l in LABELS for f in ("F0", "F1", "F2", "F3", "F4")]            # round 1
HIST = os.path.join(OUT, "cand_early.parquet")              # round 2: 2021-23 candidates as extra training rows
DEV_Q = {"main": ("2025Q1", "2026Q1")}                      # development: walk-forward through Mar 2026 only
ERA_OF = {"main": ("sel", "chk"), "early": ("early",)}
CFG = dict(theta=0.5, C=250e3, today=True, cost_mult=2.0)    # S* theta 0.5


def split(name):
    """SPEC = <label><feature set>[H]; H = the 2021-23 candidates are added to every training set (main era only)."""
    hist = name.endswith("H")
    core_name = name[:-1] if hist else name
    for l in sorted(LABELS, key=len, reverse=True):
        if core_name.startswith(l) and core_name[len(l):] in FSETS:
            return l, core_name[len(l):], hist
    raise ValueError(name)


# ------------------------------------------------------------------------------------------------ labels
@numba.njit(cache=True)
def _ladder(cand, hi, lo, cf, lvl4, sig, tickf, H, ks, theta):
    """Deeper rungs of the ladder for each candidate 4-sigma fill: (filled, gross log return, take-profit hit)."""
    n, nk, T = len(cand), len(ks), len(hi)
    g = np.full((n, nk), np.nan)
    filled = np.zeros((n, nk), np.int8)
    tp = np.zeros((n, nk), np.int8)
    for a in range(n):
        i0 = cand[a]
        s, p4 = sig[i0], lvl4[i0]
        if not (s > 0.0) or not (p4 > 0.0) or i0 + 2 * H + 1 >= T:
            continue
        tk = tickf[i0]
        tp4 = p4 * np.exp(theta * 4.0 * s)
        close_par = i0 + H
        for j in range(i0 + 1, i0 + H + 1):
            if hi[j] >= tp4 * (1.0 + tk):
                close_par = j
                break
        for b in range(nk):
            k = ks[b]
            L = p4 * np.exp(-(k - 4.0) * s)
            jf = -1
            for j in range(i0, close_par):
                if lo[j] <= L * (1.0 - tk):
                    jf = j
                    break
            g[a, b] = 0.0
            if jf < 0:
                continue
            filled[a, b] = 1
            tpk = L * np.exp(theta * k * s)
            x = -1
            for j in range(jf + 1, jf + H + 1):
                if hi[j] >= tpk * (1.0 + tk):
                    x = j
                    break
            if x >= 0:
                g[a, b] = theta * k * s
                tp[a, b] = 1
            else:
                g[a, b] = np.log(cf[jf + H] / L)
    return g, filled, tp


def spot_labels(ls, X, lab):
    """S4, LD and LS for every candidate (bp; LS in sigmas)."""
    d = ls.data
    out = pd.DataFrame(index=X.index, columns=["S4", "LD", "LS", "f6", "f8"], dtype=float)
    ks = np.array([6.0, 8.0])
    for c in ls.coins:
        rows = X.index[X.coin == c]
        cand = X.pos[rows].to_numpy().astype(np.int64)
        D = d.D[c]
        g, f, tp = _ladder(cand, D["high"], D["low"], D["cf"], ls.lvl[c], ls.sig[c], ls.tick(c), 60, ks, 0.6)
        tp4 = lab.tp_hit[rows].to_numpy() > 0
        s4 = lab.gross[rows].to_numpy() - MAKER_BP - np.where(tp4, MAKER_BP, TAKER_BP + HS_BP)
        net = 1e4 * g - f * (MAKER_BP + np.where(tp > 0, MAKER_BP, TAKER_BP + HS_BP))
        ld = (s4 + net[:, 0] + net[:, 1]) / 3.0
        out.loc[rows, "S4"] = s4
        out.loc[rows, "LD"] = ld
        out.loc[rows, "LS"] = ld / (X.sig[rows].to_numpy() * 1e4)
        out.loc[rows, "f6"], out.loc[rows, "f8"] = f[:, 0], f[:, 1]
    return out


def label_of(kind, lab, sp):
    if kind == "R":
        return lab["net_real"].clip(-400, 400)
    if kind == "LS":
        return sp["LS"].clip(-8, 8)
    return sp[kind].clip(-400, 400)


# ------------------------------------------------------------------------------------------------ macro features
def macro_arrays(d):
    """Per-minute arrays known at the end of minute t-1 (row t): Deribit BTC DVOL (hourly bars, usable one hour after
    the bar opens), its 24-hour change, DVOL minus BTC's 1-day realized volatility (annualized, %), the VIX close and
    Nasdaq-futures returns (daily bars, usable from the next UTC day)."""
    idx = pd.DataFrame({"t": d.idx - pd.Timedelta(minutes=1)})
    A = os.path.join(ROOT, "data", "alt")
    dv = pd.read_parquet(os.path.join(A, "dvol_BTC.parquet"))[["ts", "close"]].sort_values("ts")
    dv["avail"] = pd.to_datetime(dv.ts) + pd.Timedelta(hours=1)
    dv["chg24"] = dv.close - dv.close.shift(24)
    m = pd.merge_asof(idx, dv[["avail", "close", "chg24"]].astype({"avail": idx.t.dtype}), left_on="t", right_on="avail")
    out = {"dvol_btc": m.close.to_numpy(), "dvol_chg24": m.chg24.to_numpy()}
    r = np.diff(d.lp["BTC"], prepend=np.nan)
    rv = pd.Series(r).rolling(1440, min_periods=600).std().to_numpy() * np.sqrt(525600.0) * 100.0
    out["vrp_btc"] = out["dvol_btc"] - core.shift(rv, 1)
    for name, f in (("vix", "yf_vix"), ("nq", "yf_nq")):
        y = pd.read_parquet(os.path.join(A, f"{f}.parquet"))[["date", "Close"]].sort_values("date")
        y["avail"] = (pd.to_datetime(y.date) + pd.Timedelta(days=1)).astype(idx.t.dtype)
        y["r1"] = 1e4 * np.log(y.Close / y.Close.shift(1))
        y["r5"] = 1e4 * np.log(y.Close / y.Close.shift(5))
        m = pd.merge_asof(idx, y[["avail", "Close", "r1", "r5"]], left_on="t", right_on="avail")
        if name == "vix":
            out["vix"] = m.Close.to_numpy()
        else:
            out["nq_ret1d_bp"], out["nq_ret5d_bp"] = m.r1.to_numpy(), m.r5.to_numpy()
    return {k: v.astype(np.float32) for k, v in out.items()}


def memory_arrays(L):
    """Outcome memory, known at the end of minute t-1 (row t). A candidate fill at minute q has its R2-08 label (net bp
    of the 4-sigma trade, clipped) known by the end of minute q + 60, so row t may use it when q + 61 <= t.
      mkt_net_24h / mkt_n_24h   mean and count of all coins' candidate outcomes that became known in the last 24 hours
      coin_prev_net / _age      the coin's latest known candidate outcome, and minutes since that fill (<= 7 days)"""
    d, X = L.data, L.X
    T = d.T
    y = L.lab.net_real.clip(-400, 400).to_numpy()
    pos = X.pos.to_numpy().astype(np.int64)
    ok = np.isfinite(y) & (pos + 61 < T)
    a_s, a_n = np.zeros(T), np.zeros(T)
    np.add.at(a_s, pos[ok] + 61, y[ok])
    np.add.at(a_n, pos[ok] + 61, 1.0)
    cs, cn = np.cumsum(a_s), np.cumsum(a_n)
    lag = np.r_[np.zeros(1440), cs[:-1440]], np.r_[np.zeros(1440), cn[:-1440]]
    w_s, w_n = cs - lag[0], cn - lag[1]
    with np.errstate(invalid="ignore", divide="ignore"):
        out = {"mkt_net_24h": np.where(w_n > 0, w_s / w_n, np.nan).astype(np.float32), "mkt_n_24h": w_n.astype(np.float32)}
    coin = {}
    cc = X.coin.to_numpy()
    tt = np.arange(T)
    for c in L.ls.coins:
        m = ok & (cc == c)
        val = np.full(T, np.nan)
        src = np.full(T, -1, dtype=np.int64)
        o = np.argsort(pos[m])
        val[pos[m][o] + 61] = y[m][o]
        src[pos[m][o] + 61] = pos[m][o]
        last = np.maximum.accumulate(np.where(src >= 0, tt, -1))          # latest minute <= t with a new outcome
        has = last >= 0
        pv = np.where(has, val[np.maximum(last, 0)], np.nan)
        age = np.where(has, np.minimum(tt - src[np.maximum(last, 0)], 10080), 10080)
        coin[c] = (pv.astype(np.float32), age.astype(np.float32))
    out["coin"] = coin
    return out


# ------------------------------------------------------------------------------------------------ walk-forward
def wf(X, y, feats, periods, thr_q=0.6, seeds=(7, 11, 23), keep_models=False, hist=None):
    """core.walk_forward at R2-08's settings (episode weights, Huber, 250 rounds), also returning the models."""
    params = dict(wick.PARAMS)
    pred = pd.Series(np.nan, index=X.index)
    thr = pd.Series(np.nan, index=X.index)
    cat = ["coin_id"] if "coin_id" in feats else []
    ok = y.notna()
    models = {}
    for per in periods:
        tr_mask = (X.ts < per.start_time - pd.Timedelta(days=1)) & ok
        te_mask = (X.ts >= per.start_time) & (X.ts <= per.end_time)
        if not te_mask.any() or tr_mask.sum() < 200:
            continue
        tr, te = X[tr_mask], X[te_mask]
        ytr = y[tr_mask].to_numpy()
        if hist is not None:                                  # earlier-era candidates: extra training rows
            hx, hy = hist
            tr = pd.concat([hx[["coin", "episode", "ts"] + feats], tr[["coin", "episode", "ts"] + feats]], ignore_index=True)
            ytr = np.r_[hy, ytr]
        w = 1.0 / tr.groupby(["coin", "episode"]).ts.transform("size").to_numpy()
        ms = [lgb.train(params | {"seed": s}, lgb.Dataset(tr[feats], ytr, weight=w, categorical_feature=cat),
                        num_boost_round=wick.ROUNDS) for s in seeds]
        pred[te.index] = np.mean([m.predict(te[feats]) for m in ms], axis=0)
        t_ = float(np.quantile(np.mean([m.predict(tr[feats]) for m in ms], axis=0), thr_q))
        thr[te.index] = t_
        if keep_models:
            models[str(per)] = (ms, t_)
    return pred, thr, models


class Lab:
    def __init__(self):
        t0 = time.time()
        allv = {v["name"]: v for v in VV.VARIANTS + VV.ROUND1B + VV.make_round2()}
        self.v = allv["R2-08 C29+A11"]
        (ls_d, ex_d, ai_d), = RUN.expand(self.v)
        self.ai_d = ai_d
        self.data = core.Data(list(ls_d.get("coins") or core.COINS17))
        self.ls = core.LevelSet(self.data, **ls_d)
        self.X = self.ls.features()
        self.ex = core.Exit(**ex_d)
        self.lab = core.labels(self.ls, self.ex)
        self.sp = spot_labels(self.ls, self.X, self.lab)
        self.macro = macro_arrays(self.data)
        pos = self.X.pos.to_numpy()
        for k, a in self.macro.items():
            self.X[k] = a[pos]
        self.mem = memory_arrays(self)
        self.X["mkt_net_24h"], self.X["mkt_n_24h"] = self.mem["mkt_net_24h"][pos], self.mem["mkt_n_24h"][pos]
        pn_, pa_ = np.full(len(pos), np.nan, np.float32), np.full(len(pos), np.nan, np.float32)
        cc = self.X.coin.to_numpy()
        for c in self.ls.coins:
            m = cc == c
            pn_[m], pa_[m] = self.mem["coin"][c][0][pos[m]], self.mem["coin"][c][1][pos[m]]
        self.X["coin_prev_net"], self.X["coin_prev_age"] = pn_, pa_
        self.hist = None
        if BASE == "main" and os.path.exists(HIST):
            h = pd.read_parquet(HIST)
            codes = {c: float(i) for i, c in enumerate(sorted(self.ls.coins))}
            h = h[h.coin.isin(codes)].copy()
            h["coin_id"] = h.coin.map(codes).astype(np.float32)
            h["episode"] = h.episode + 10_000_000
            self.hist = h.reset_index(drop=True)
        print(f"lab ready: {len(self.X):,} candidates, {len(self.ls.coins)} coins ({time.time() - t0:.0f}s)", flush=True)

    def fit(self, name, periods, keep_models=False):
        l, f, use_hist = split(name)
        feats = list(wick.FEATS) + FSETS[f]
        y = label_of(l, self.lab, self.sp)
        hist = None
        if use_hist:
            hy = self.hist[f"y_{l}"]
            okh = hy.notna().to_numpy()
            hist = (self.hist[okh], hy.to_numpy()[okh])
        pred, thr, models = wf(self.X, y, feats, periods, thr_q=self.ai_d.get("thr_q", 0.5), keep_models=keep_models,
                               hist=hist)
        return feats, pred, thr, models

    def export(self):
        """Every candidate of this era with all features and labels (training rows for the later era's models)."""
        cols = ["coin", "ts", "episode"] + list(wick.FEATS) + sorted({x for v in FSETS.values() for x in v})
        E = self.X[cols].copy()
        for l in LABELS:
            E[f"y_{l}"] = label_of(l, self.lab, self.sp).to_numpy()
        E.to_parquet(os.path.join(OUT, f"cand_{BASE}.parquet"), index=False)
        print(f"exported {len(E):,} candidates, {E.coin.nunique()} coins, {E.ts.min()} .. {E.ts.max()}", flush=True)

    def trades(self, pred, thr):
        X, ls, ex = self.X, self.ls, self.ex
        keep = (pred > thr) | (X.ts < core.TEST0)
        tr = RUN.attach_thr(core.simulate(ls, ex, keep=keep, pred=pred), ls, X, thr)
        tr["k"] = ls.k
        tr["tp_log"] = ex.theta * ls.k * tr.sig
        tr["fair_log"] = np.log(tr.px) + ls.k * tr.sig
        tr = tr.sort_values(["ts", "coin"]).reset_index(drop=True)
        _, kept = RUN.run_portfolio(self.v, tr, self.data)
        key = set(zip(kept.ts, kept.coin))
        tr["bot"] = [(t, c) in key for t, c in zip(tr.ts, tr.coin)]
        return tr


def register(tag2):
    sim.PERIODS[tag2] = sim.PERIODS[BASE]
    if BASE == "early":
        sim.perp_mult = lambda: {}                           # no perp venue in 2021-23 (sim tests tag != "early")


_SCALE = {}


def fix_scale():
    """'Today's volumes' uses the incumbent's per-coin factors for every book (a challenger's own trade list would
    shift them slightly)."""
    orig = fsim.today_scale
    P_inc = fsim.load(BASE)

    def fixed(P, lo, hi):
        k = (str(lo), str(hi))
        if k not in _SCALE:
            _SCALE[k] = orig(P_inc, lo, hi)
        return _SCALE[k]

    fsim.today_scale = fixed
    return P_inc


def book_of(tr, tag2, eras):
    register(tag2)
    tr.to_parquet(os.path.join(sim.OUT, f"trades_{tag2}.parquet"), index=False)
    p = os.path.join(sim.OUT, f"pre_hunt_{tag2}.pkl")
    if os.path.exists(p):
        os.remove(p)
    P = fsim.load(tag2)
    return P, {e: fsim.book(P, e, **CFG)[0] for e in eras}


def screen(names):
    L = Lab()
    P_inc = fix_scale()
    periods = pd.period_range(*DEV_Q[BASE], freq="Q")
    inc = fsim.book(P_inc, "sel", **CFG)[0]
    s_inc = fsim.stats(inc, CFG["C"], "sel")
    print(f"incumbent (frozen dataset): Sharpe {s_inc['sharpe']:.3f}, {100 * s_inc['ret_yr']:.2f}%/yr", flush=True)
    ref = pd.read_parquet(os.path.join(sim.OUT, f"trades_{BASE}.parquet"))
    lo, hi = fsim.ERAS["sel"][1]
    ref = ref[ref.ts < pd.Timestamp(hi) + pd.Timedelta(days=1)]
    rows, daily = [], {}
    path = os.path.join(OUT, "screen.csv")
    for name in names:
        t0 = time.time()
        feats, pred, thr, _ = L.fit(name, periods)
        tr = L.trades(pred, thr)
        P, d = book_of(tr, f"{BASE}_dev_{name}", ("sel",))
        st = fsim.stats(d["sel"], CFG["C"], "sel")
        note = ""
        if name == "RF0":
            m = tr.merge(ref[["ts", "coin", "pred", "px"]], on=["ts", "coin"], how="outer", suffixes=("", "_ref"), indicator=True)
            same = bool((m._merge == "both").all()) and float(np.abs(m.pred - m.pred_ref).max()) < 1e-9
            diff = float(np.abs(d["sel"].reindex(inc.index, fill_value=0.0) - inc).max())
            note = f"parity: trades {'identical' if same else 'DIFFER'} ({len(tr)} vs {len(ref)}); max daily diff {diff:.1e}"
        te = (L.X.ts >= periods[0].start_time) & (L.X.ts <= periods[-1].end_time)
        rows.append(dict(spec=name, label=split(name)[0], fset=split(name)[1], hist=split(name)[2], n_feats=len(feats),
                         sharpe=st["sharpe"],
                         ret_yr=st["ret_yr"], maxdd=st["maxdd"], d_sharpe=st["sharpe"] - s_inc["sharpe"],
                         trades=len(tr), share_kept=float((pred[te] > thr[te]).mean()),
                         overlap=float(len(tr.merge(ref[["ts", "coin"]], on=["ts", "coin"])) / max(len(tr), 1)), note=note))
        daily[name] = d["sel"]
        print(f"{name}: Sharpe {st['sharpe']:.3f} ({st['sharpe'] - s_inc['sharpe']:+.3f}), {100 * st['ret_yr']:.2f}%/yr, "
              f"{len(tr)} trades, overlap {rows[-1]['overlap']:.2f} {note} ({time.time() - t0:.0f}s)", flush=True)
        R = pd.DataFrame(rows)
        if os.path.exists(path):
            old = pd.read_csv(path)
            R = pd.concat([old[~old.spec.isin(R.spec)], R], ignore_index=True)
        R.to_csv(path, index=False)
        D = pd.DataFrame(daily)
        dp = os.path.join(OUT, f"screen_daily_{'_'.join(names)[:40]}.parquet")
        D.to_parquet(dp)
    pd.DataFrame({"incumbent": inc}).to_parquet(os.path.join(OUT, "screen_daily_incumbent.parquet"))


# ------------------------------------------------------------------------------------------------ chain (finalists)
def extra_all(L, c, pos):
    """The F1-F4 extras for every listed minute of coin c (the same definitions as core.add_extra, written for
    arbitrary minutes; candidate-based ones use the coin's candidate fill minutes)."""
    d, ls = L.data, L.ls
    p = lambda a: core.shift(a, 1)  # noqa: E731
    D = d.D[c]
    s = pd.Series(D["cf"])
    lp = d.lp[c]
    btc = d.D["BTC"]
    f = {}
    f["dist_7d_high_bp"] = p(np.log(D["cf"] / s.rolling(10080, min_periods=2000).max().to_numpy()))[pos] * 1e4
    f["dist_3d_low_bp"] = p(np.log(D["cf"] / s.rolling(4320, min_periods=1440).min().to_numpy()))[pos] * 1e4
    lo1, hi1 = s.rolling(1440, min_periods=600).min().to_numpy(), s.rolling(1440, min_periods=600).max().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        f["range_pos_1d"] = p((D["cf"] - lo1) / (hi1 - lo1))[pos]
        f["ret15_bp"] = p(lp - core.shift(lp, 15))[pos] * 1e4
        f["ret60_bp"] = p(lp - core.shift(lp, 60))[pos] * 1e4
        b_cf = pd.Series(btc["cf"])
        f["btc_dist_1d_high_bp"] = (p(np.log(btc["cf"] / b_cf.rolling(1440, min_periods=600).max().to_numpy())) * 1e4)[pos]
        h, l_, cl = D["high"], D["low"], D["close"]
        clv = ((cl - l_) - (h - cl)) / (h - l_)
        f["clv5"] = p(pd.Series(clv).rolling(5, min_periods=1).mean().to_numpy())[pos]
        r = np.diff(lp, prepend=np.nan)
        v = pd.Series(D["vol"])
        f["sellvol5"] = p(((v * (r < 0)).rolling(5).sum() / (v.rolling(4320, min_periods=1440).mean() * 5)).to_numpy())[pos]
        b_r = np.diff(d.lp["BTC"], prepend=np.nan)
        bv = pd.Series(btc["vol"])
        f["btc_sellvol5"] = p(((bv * (b_r < 0)).rolling(5).sum() / (bv.rolling(4320, min_periods=1440).mean() * 5)).to_numpy())[pos]
    br = np.zeros(len(pos))
    for o in ls.coins:
        if o == c:
            continue
        ind = np.zeros(d.T, dtype=np.int32)
        ind[ls.cands[o]] = 1
        a = np.cumsum(ind)
        br += (a[np.maximum(pos - 1, 0)] - a[np.maximum(pos - 6, 0)]) > 0
    f["panic_breadth"] = br
    ind = np.zeros(d.T, dtype=bool)
    ind[ls.cands[c]] = True
    prev = np.r_[False, ind[:-1]]
    is_start = ind & ~prev                                    # first minute of each run of candidate minutes
    tt = np.arange(d.T)
    run_start = np.maximum.accumulate(np.where(is_start, tt, -1))        # start of the latest run beginning <= t
    start = np.where(prev, core.shift(run_start.astype(float), 1), tt)   # a fill at t continues t-1's run or starts one
    start = np.nan_to_num(start, nan=0.0).astype(np.int64)
    last_c = np.maximum.accumulate(np.where(ind, tt, -1))                # latest candidate minute <= t
    prev_end = np.where(start >= 1, last_c[np.maximum(start - 1, 0)], -1)
    msp = np.where(prev_end >= 0, np.minimum(start - prev_end, 10080), 10080)
    cs = np.cumsum(is_start)
    cs0 = np.r_[0, cs]                                        # cs0[i] = starts before minute i
    e24 = cs0[start] - cs0[np.maximum(start - 1440, 0)]
    f["mins_since_prev_ep"] = msp[pos]
    f["eps_24h"] = e24[pos]
    ts = d.idx[pos]
    f["hour_of_week"] = np.asarray(ts.dayofweek * 24 + ts.hour)
    f["mins_to_midnight"] = np.asarray(1440 - (ts.hour * 60 + ts.minute))
    mins = np.asarray(ts.hour * 60 + ts.minute)
    f["us_session"] = ((np.asarray(ts.dayofweek) < 5) & (mins >= 810) & (mins < 1200)).astype(int)
    bcf = pd.Series(btc["cf"])
    sma100 = bcf.rolling(144000, min_periods=100000).mean().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        f["btc_dist_sma100_bp"] = (p(np.log(btc["cf"] / sma100)) * 1e4)[pos]
        f["btc_ret30d_bp"] = (p(d.lp["BTC"] - core.shift(d.lp["BTC"], 43200)) * 1e4)[pos]
    for k, a in L.macro.items():
        f[k] = a[pos]
    f["mkt_net_24h"], f["mkt_n_24h"] = L.mem["mkt_net_24h"][pos], L.mem["mkt_n_24h"][pos]
    f["coin_prev_net"], f["coin_prev_age"] = L.mem["coin"][c][0][pos], L.mem["coin"][c][1][pos]
    return pd.DataFrame(f).astype(np.float32)


def deep_paths(tag2):
    """scripts/ladder_v5/deep_paths.py for a challenger's dataset (same code path, other tag)."""
    import wick_sim as ws
    P = fsim.load(tag2)
    start, end, src = sim.PERIODS[tag2]
    idx = pd.date_range(start, end, freq="min", inclusive="left")
    out = {}
    for c in sorted(P.coin.unique()):
        S = sim.load_venue(os.path.join(fsim.ROOT, "data", src, f"{c}.parquet"), idx)
        try:
            tick_abs = ws.spot_tick(c)
        except KeyError:
            tick_abs = np.nan
        G = P[P.coin == c]
        par = G[G.k == 4.0].set_index("ts")
        for i_row, r in G[G.k > 4.0].iterrows():
            if r.ts not in par.index:
                continue
            p = par.loc[r.ts]
            i0 = idx.get_indexer([r.ts])[0]
            close_par = i0 + (int(p.tp_off) if p.tp_off >= 0 else sim.H)
            lvl = float(r.lvl)
            tickf = (tick_abs / lvl) if np.isfinite(tick_abs) else 0.0
            sig = float(np.log(p.lvl / lvl) / (r.k - 4.0)) if r.k > 4 else np.nan
            tp = lvl * np.exp(0.6 * r.k * sig)
            lows = np.nan_to_num(S["low"][i0:close_par], nan=np.inf)
            hits = np.nonzero(lows <= lvl * (1 - tickf))[0]
            rows = []
            for h in hits:
                i_f = i0 + int(h)
                if i_f + sim.H + 1 >= len(idx):
                    continue
                usd, last = sim.below_usd(S, i_f, lvl)
                i_tp = sim.first_touch(S["high"], i_f + 1, i_f + sim.H, tp * (1 + tickf))
                path = pd.Series(S["cf"][i_f:i_f + sim.H + 1]).ffill().bfill().to_numpy()
                rows.append(dict(off=int(h), in_spot=usd, scan_off=last - i0,
                                 tp_off=(i_tp - i_f) if i_tp >= 0 else -1,
                                 tp_spot=sim.above_usd(S, i_f + 1, i_f + sim.H, tp * 1.0),
                                 g60=1e4 * np.log(path[-1] / lvl), g_tp=1e4 * np.log(tp / lvl)))
            out[i_row] = pd.DataFrame(rows)
    pd.to_pickle(out, os.path.join(fsim.OUT, f"deep_paths_{tag2}.pkl"))
    bad = 0
    for i_row, Dd in out.items():
        r = P.loc[i_row]
        if r.filled and (not len(Dd) or int(Dd.off.iloc[0]) != int(r.f_off)):
            bad += 1
    return len(out), bad


def chain(name):
    """Full walk-forward for one spec, its trade list and dataset, the every-minute panel and the deep paths, under
    the tag <era>_<spec> (read by scripts/signal_lab/score.py)."""
    t0 = time.time()
    L = Lab()
    fix_scale()
    tag2 = f"{BASE}_{name}"
    periods = pd.period_range(*core.WF_Q, freq="Q")
    feats, pred, thr, models = L.fit(name, periods, keep_models=True)
    tr = L.trades(pred, thr)
    P, _ = book_of(tr, tag2, ())
    print(f"{tag2}: {len(tr)} trades, {len(P)} tranche rows ({time.time() - t0:.0f}s)", flush=True)
    d, ls = L.data, L.ls
    i0 = d.i_test
    rows = {c: np.arange(i0, d.T, dtype=np.int64) for c in ls.coins}
    cf = {c: d.D[c]["cf"] for c in d.D}
    vol = {c: d.D[c]["vol"] for c in d.D}
    pn = wick.panel(cf, vol, ls.coins, d.idx, k=ls.k, lookback=ls.L, keep_rows=rows)
    print(f"every-minute features ({time.time() - t0:.0f}s)", flush=True)
    out = os.path.join(ROOT, "data", "ladder_v5", f"panel_{tag2}")
    os.makedirs(out, exist_ok=True)
    extra = [x for x in feats if x not in wick.FEATS]
    worst, n_chk, armed = 0.0, 0, {}
    q_of = pd.PeriodIndex(d.idx[i0:], freq="Q").astype(str)
    for c in ls.coins:
        f = pn.pop(c)[list(wick.FEATS)].copy().reset_index(drop=True)
        r = rows[c]
        f["bid_depth_bp"] = (ls.k * ls.sig[c][r] * 1e4).astype(np.float32)
        f["beta"] = ls.beta[c][r].astype(np.float32)
        if extra:
            E = extra_all(L, c, r)
            for x in extra:
                f[x] = E[x].to_numpy()
        px = np.full(len(r), np.nan, dtype=np.float32)
        th = np.full(len(r), np.nan, dtype=np.float32)
        for q, (ms, t_) in models.items():
            m = np.asarray(q_of == q)
            if m.any():
                px[m] = np.mean([mm.predict(f.loc[m, feats]) for mm in ms], axis=0)
                th[m] = t_
        pd.DataFrame({"ts": d.idx[r], "pred": px}).to_parquet(os.path.join(out, f"{c}.parquet"), index=False)
        # check: the every-minute prediction at candidate minutes = the candidate-row prediction
        sub = L.X[(L.X.coin == c) & (L.X.ts >= core.TEST0)]
        got = px[sub.pos.to_numpy() - i0]
        want = pred[sub.index].to_numpy()
        ok = np.isfinite(got) & np.isfinite(want)
        if ok.any():
            worst = max(worst, float(np.abs(got[ok] - want[ok]).max()))
            n_chk += int(ok.sum())
        armed[c] = float(np.nanmean(px > th))
        del f
        gc.collect()
    pd.DataFrame({"thr": [t_ for _, (_, t_) in models.items()], "quarter": list(models)}).to_csv(
        os.path.join(out, "thr.csv"), index=False)
    print(f"panel: {n_chk:,} candidate minutes checked, max |every-minute - candidate prediction| {worst:.2e}; "
          f"mean share of minutes armed {np.mean(list(armed.values())):.3f} ({time.time() - t0:.0f}s)", flush=True)
    n, bad = deep_paths(tag2)
    import shutil
    rt = os.path.join(ROOT, "reports", "ladder_v5", "redteam")
    shutil.copy(os.path.join(rt, f"adv_{BASE}.parquet"), os.path.join(rt, f"adv_{tag2}.parquet"))
    json.dump(dict(spec=name, base=BASE, trades=len(tr), panel_check=worst, panel_checked=n_chk, deep=n, deep_bad=bad,
                   armed=armed), open(os.path.join(OUT, f"chain_{tag2}.json"), "w"), indent=1)
    print(f"deep paths: {n} rungs, {bad} mismatches; done ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    mode = sys.argv[2]
    if mode == "screen":
        screen(sys.argv[3:] or SPECS)
    elif mode == "chain":
        chain(sys.argv[3])
    elif mode == "export":
        Lab().export()
