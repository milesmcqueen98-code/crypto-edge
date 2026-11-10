#!/usr/bin/env python3
"""Late BTC replay (reports/owner/late_btc_prereg.md): R2-08 rebuilt with BTC as the bot saw it, priced on the frozen
engine-faithful simulator at the best estimate's configuration (cash rule + print exit costs, S*, theta 0.5, $250K).

  python scripts/owner/late_btc/replay.py <main|early> [--scen S0,S1,...] [--exact N] [--exact4 N] [--job NAME]

Scenarios (BTC only; every coin's own candles stay true):
  S0 true BTC; S1 BTC's newest minute missing at every decision, filled forward (one minute late); S2 the newest two
  missing; S3s<k> each decision minute one or two minutes late (probability 0.7 / 0.3, seed k); S4s<k> S3s<k> plus 30%
  of BTC's older minutes missing and filled forward (drawn once per seed). Default: all, S3 and S4 with seeds 1-5.

What changes and what does not:
  - The models are R2-08's walk-forward LightGBM by quarter, fitted on true candles exactly as scripts/lab/core.py
    walk_forward fits them (kept), with their 60th-percentile thresholds. They are never refitted on late features.
  - At every decision minute of the test period the bot's level, sigma and 23 features are rebuilt from the late BTC
    (late.py; level and the BTC-dependent features, coin-only features unchanged). The candidate fill minutes are then
    found again against TRUE lows (open above the level, low a tick below it), and the model scores the late features
    there and at every minute (the every-minute armed panel).
  - The trade list, tranche dataset, deep paths and the engine-faithful replay run on true prices (model.py's
    deep_paths, sim.precompute through fsim.load, frozen/rt_live.py, lsim.rem_daily print costs), as for R2-08.
Gate: S0 must reproduce R2-08 (trade list, every-minute panel, and the best estimate 2.94 / 2.66 / 1.91 Sharpe and
22.8% / 19.1% / 11.1% a year). Exactness: --exact N draws N decision minutes per era and runs the unmodified
edge.wick.panel on the bot's own arrays (bot/spot/engine.py `arrays`: 11 days, close filled forward, volume 0 when
missing) with BTC's tail dropped (S1, S2); level and all 23 features must equal the vectorised values. --exact4 N does
the same for S4 seed 1. If the gate or a check fails, the job stops before any other scenario is computed.
Outputs (derived tables only): reports/owner/late_btc/runs/<era>_<job>/ (gate.json, exact.csv, summary.csv,
daily_<era>_<scenario>.csv).
"""
import gc
import json
import os
import shutil
import sys
import time

BASE = sys.argv[1]
os.environ["LAB_ERA"] = BASE                                  # the lab reads the era at import
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OPT = {"scen": None, "exact": "0", "exact4": "0", "job": "run"}
_rest = sys.argv[2:]
for _i in range(0, len(_rest), 2):
    if not _rest[_i].startswith("--") or _rest[_i][2:] not in OPT or _i + 1 >= len(_rest):
        raise SystemExit(f"bad option {_rest[_i:]}")
    OPT[_rest[_i][2:]] = _rest[_i + 1]
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "signal_lab"))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import score  # noqa: E402  (first: lsim imports ladder v5's gates before fsim puts scripts/hunt on the path)
_argv, sys.argv = sys.argv, [sys.argv[0], BASE]
import model  # noqa: E402  (the signal lab's pipeline: deep paths, dataset registration)
sys.argv = _argv
sys.path.insert(0, HERE)
import late  # noqa: E402

core, RUN, VV, lgb, wick, fsim, sim = model.core, model.RUN, model.VV, model.lgb, model.wick, model.fsim, model.sim
lsim, RL = score.lsim, score.RL
ws = core.ws
OUT = os.path.join(ROOT, "reports", "owner", "late_btc", "runs", f"{BASE}_{OPT['job']}")
os.makedirs(OUT, exist_ok=True)
CFG = "S_0.5"
KW = lsim.CONFIGS[CFG]
ERAS = model.ERA_OF[BASE]
TARGET = {"sel": (2.94, 22.8), "chk": (2.66, 19.1), "early": (1.91, 11.1)}     # findings: best estimate at $250K
WIN = 11 * 1440                                                                 # bot/spot/engine.py WINDOW_MIN
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:7.0f}s] {msg}", flush=True)


def scenarios():
    if OPT["scen"]:
        return OPT["scen"].split(",")
    return ["S0", "S1", "S2"] + [f"S3s{k}" for k in range(1, 6)] + [f"S4s{k}" for k in range(1, 6)]


# ------------------------------------------------------------------------------------------------ the research
class Research:
    """R2-08 as the wick lab builds it: data, level set, candidates, features, labels, kept walk-forward models."""

    def __init__(self):
        allv = {v["name"]: v for v in VV.VARIANTS + VV.ROUND1B + VV.make_round2()}
        self.v = allv["R2-08 C29+A11"]
        (ls_d, ex_d, ai_d), = RUN.expand(self.v)
        extra = set(ai_d) - {"label", "thr_q", "feats"}
        assert not extra, f"R2-08's AI settings have keys this fit does not copy: {extra}"
        self.ls_d, self.ai_d = ls_d, ai_d
        self.data = core.Data(list(ls_d.get("coins") or core.COINS17))
        self.ls = core.LevelSet(self.data, **ls_d)
        self.X = self.ls.features()
        self.ex = core.Exit(**ex_d)
        lab = core.labels(self.ls, self.ex)
        self.y = RUN.make_label(lab, ai_d, self.ls)
        self.feats = list(ai_d.get("feats", tuple(wick.FEATS)))
        assert self.feats == list(wick.FEATS)
        d = self.data
        self.i0, self.T = d.i_test, d.T
        self.rows = np.arange(self.i0, self.T, dtype=np.int64)
        self.q_of = np.asarray(pd.PeriodIndex(d.idx[self.i0:], freq="Q").astype(str))
        self.wbeta = ls_d.get("wbeta", 4320)
        log(f"research ready: {len(self.X):,} candidates, {len(self.ls.coins)} coins, wbeta {self.wbeta}")

    def fit(self):
        """core.walk_forward at R2-08's settings, with the boosters kept (same training rows, weights, seeds)."""
        X, y, feats, ai = self.X, self.y, self.feats, self.ai_d
        params = dict(wick.PARAMS)
        seeds = ai.get("seeds", (7, 11, 23))
        cat = ["coin_id"]
        self.models, self.pred, self.thr = {}, pd.Series(np.nan, index=X.index), pd.Series(np.nan, index=X.index)
        for per in pd.period_range(*core.WF_Q, freq="Q"):
            tr_mask = X.ts < per.start_time - pd.Timedelta(days=1)
            te_mask = (X.ts >= per.start_time) & (X.ts <= per.end_time)
            if not te_mask.any() or tr_mask.sum() < 200:
                continue
            tr, te = X[tr_mask], X[te_mask]
            w = 1.0 / tr.groupby(["coin", "episode"]).ts.transform("size").to_numpy()
            ytr = y[tr_mask].to_numpy()
            ms = [lgb.train(params | {"seed": s}, lgb.Dataset(tr[feats], ytr, weight=w, categorical_feature=cat),
                            num_boost_round=wick.ROUNDS) for s in seeds]
            self.pred[te.index] = np.mean([m.predict(te[feats]) for m in ms], axis=0)
            t_ = np.quantile(np.mean([m.predict(tr[feats]) for m in ms], axis=0), ai.get("thr_q", 0.5))
            self.thr[te.index] = t_
            self.models[str(per)] = (ms, float(t_))
        log(f"walk-forward: {len(self.models)} quarters fitted")

    def true_panel(self):
        """Every test minute's 23 features as the research computes them (wick.panel, 7-day beta behind bid depth and
        beta), one quarter at a time, as float32 matrices [rows, 23]."""
        d, ls = self.data, self.ls
        cf = {c: d.D[c]["cf"] for c in d.D}
        vol = {c: d.D[c]["vol"] for c in d.D}
        n = len(self.rows)
        self.F0 = {c: np.full((n, len(self.feats)), np.nan, np.float32) for c in ls.coins}
        for q in list(dict.fromkeys(self.q_of)):
            m = self.q_of == q
            r = self.rows[m]
            pn = wick.panel(cf, vol, ls.coins, d.idx, k=ls.k, lookback=ls.L, keep_rows={c: r for c in ls.coins})
            for c in ls.coins:
                f = pn.pop(c)[self.feats].copy()
                f["bid_depth_bp"] = (ls.k * ls.sig[c][r] * 1e4).astype(np.float32)
                f["beta"] = ls.beta[c][r].astype(np.float32)
                self.F0[c][m] = f.to_numpy(np.float32)
            del pn
            gc.collect()
        log("true every-minute features built")


R = None


# ------------------------------------------------------------------------------------------------ one scenario
class LS2:
    """A level set whose levels, sigma, beta, candidates and candidate features are the scenario's (core.simulate and
    core.Exit read these attributes)."""

    def __init__(self, ls, lvl, sig, beta, cands, X):
        self.data, self.L, self.k, self.side, self.ref = ls.data, ls.L, ls.k, ls.side, ls.ref
        self.coins = ls.coins
        self.lvl, self.sig, self.beta, self.cands, self._X = lvl, sig, beta, cands, X

    def tick(self, c):
        return np.nan_to_num(ws.spot_tick(c) / self.data.D[c]["cf"], nan=1.0)

    def features(self, extra=()):
        return self._X


def tick_round(c, lvl):
    t = ws.SPOT_TICK.get(c)
    return np.floor(lvl / t + 1e-9) * t if t else lvl


def build(name, lag, late_vals):
    """Levels, features, candidates, predictions and the trade list of one scenario. lag: per test row 1 or 2 (None for
    S0); late_vals: {m: (btc, per)} from late.late_multi on the scenario's base (None for S0)."""
    d, ls, i0 = R.data, R.ls, R.i0
    feats = R.feats
    col = {f: i for i, f in enumerate(feats)}
    lvl_f, sig_f, beta_f, cands, rows_x = {}, {}, {}, {}, []
    pxs64, pxs32, lvl_post = {}, {}, {}

    def pick(c, name_):
        if name_ in late_vals[1][0]:
            a1, a2 = late_vals[1][0][name_], late_vals[2][0][name_]
        else:
            a1, a2 = late_vals[1][1][c][name_], late_vals[2][1][c][name_]
        return np.where(lag == 1, a1, a2)

    for c in ls.coins:
        if lag is None:
            lv, sg, bt = ls.lvl[c][i0:], ls.sig[c][i0:], ls.beta[c][i0:]
            F = R.F0[c]
        else:
            lv = tick_round(c, pick(c, "level"))
            sg, bt = pick(c, "sig"), pick(c, "beta")
            F = R.F0[c].copy()
            for f in late.BTC_FEATS:
                F[:, col[f]] = pick(c, f).astype(np.float32)
        lvl_post[c] = lv
        D = d.D[c]
        tk = ls.tick(c)[i0:]
        with np.errstate(invalid="ignore"):
            fill = (D["open"][i0:] > lv) & (D["low"][i0:] <= lv * (1 - tk))
        cd = R.rows[fill]
        cd = cd[cd > 1500]
        if lag is None:
            ref = ls.cands[c][ls.cands[c] >= i0]
            assert np.array_equal(cd, ref), f"S0 candidates of {c} differ from the level set's"
        cands[c] = cd
        L_, S_, B_ = ls.lvl[c].copy(), ls.sig[c].copy(), ls.beta[c].copy()
        L_[i0:], S_[i0:], B_[i0:] = lv, sg, bt
        lvl_f[c], sig_f[c], beta_f[c] = L_, S_, B_
        p64 = np.full(len(R.rows), np.nan)
        for q, (ms, _) in R.models.items():
            mq = R.q_of == q
            if mq.any():
                fr = pd.DataFrame(F[mq], columns=feats)
                p64[mq] = np.mean([m.predict(fr) for m in ms], axis=0)
        pxs64[c], pxs32[c] = p64, p64.astype(np.float32)
        if len(cd):
            f = pd.DataFrame(F[cd - i0], columns=feats)
            f["coin"], f["pos"], f["ts"] = c, cd, d.idx[cd]
            f["episode"] = np.cumsum(np.r_[1, np.diff(cd) > 1])
            f["sig"] = S_[cd]
            f["px"] = L_[cd]
            f["pred"] = p64[cd - i0]
            rows_x.append(f)
        del F
    X2 = pd.concat(rows_x, ignore_index=True)
    pred2 = X2.pop("pred")
    tq = {q: t_ for q, (_, t_) in R.models.items()}
    thr2 = pd.Series(np.asarray(pd.PeriodIndex(X2.ts, freq="Q").astype(str).map(tq), dtype=np.float64), index=X2.index)
    ls2 = LS2(ls, lvl_f, sig_f, beta_f, cands, X2)
    keep = (pred2 > thr2) | (X2.ts < core.TEST0)
    tr = RUN.attach_thr(core.simulate(ls2, R.ex, keep=keep, pred=pred2), ls2, X2, thr2)
    tr["k"] = ls2.k
    tr["tp_log"] = R.ex.theta * ls2.k * tr.sig
    tr["fair_log"] = np.log(tr.px) + ls2.k * tr.sig
    tr = tr.sort_values(["ts", "coin"]).reset_index(drop=True)
    _, kept = RUN.run_portfolio(R.v, tr, d)
    key = set(zip(kept.ts, kept.coin))
    tr["bot"] = [(t, c) in key for t, c in zip(tr.ts, tr.coin)]
    log(f"{name}: {len(X2):,} candidate minutes, {int(keep.sum()):,} armed there, {len(tr)} trades")
    return dict(tr=tr, pxs32=pxs32, lvl=lvl_post, ncand=len(X2))


def write_panel(tag2, pxs32):
    """data/ladder_v5/panel_<tag>: as scripts/ladder_v5/panel.py writes R2-08's (float32 predictions and float32
    quarterly thresholds), so S0 is byte-for-byte the incumbent's rule."""
    d = R.data
    out = os.path.join(ROOT, "data", "ladder_v5", f"panel_{tag2}")
    os.makedirs(out, exist_ok=True)
    ts = d.idx[R.rows]
    for c in R.ls.coins:
        pd.DataFrame({"ts": ts, "pred": pxs32[c]}).to_parquet(os.path.join(out, f"{c}.parquet"), index=False)
    q = list(R.models)
    pd.DataFrame({"thr": np.array([R.models[k][1] for k in q], np.float32), "quarter": q}).to_csv(
        os.path.join(out, "thr.csv"), index=False)
    back = pd.read_csv(os.path.join(out, "thr.csv"))
    return dict(zip(back.quarter, back.thr))


def cell(tag2, era):
    """score.cell at S_0.5, also returning each bound's tranche frame."""
    A = RL.era_arrays(tag2, era, KW["theta"], KW["C"], KW["today"])
    dd, Qs = {}, {}
    for bound in ("minute", "instant"):
        Rr = RL.replay(A, theta=KW["theta"], C=KW["C"], bound=bound, policy="engine")
        _, Qo, info = RL.evaluate_live(A, Rr, KW["theta"], KW["C"], era, KW["cost_mult"])
        for cost in ("model", "print"):
            dd[(bound, cost)], _, _ = lsim.rem_daily(Qo, info, CFG, era, KW["C"], cost=cost)
        Qs[bound] = Qo[[c for c in Qo.columns if c != "path"]].copy()
    out = pd.DataFrame({cost: lsim.blend(era, KW["theta"], dd[("minute", cost)], dd[("instant", cost)])
                        for cost in ("model", "print")})
    return out, Qs


def dataset(name, B):
    """Trade list -> tranche dataset -> every-minute panel -> deep paths -> ADV table, under tag <era>_LB<name>."""
    tag2 = f"{BASE}_LB{name}"
    P, _ = model.book_of(B["tr"], tag2, ())
    tq = write_panel(tag2, B["pxs32"])
    n, bad = model.deep_paths(tag2)
    rt = os.path.join(ROOT, "reports", "ladder_v5", "redteam")
    shutil.copy(os.path.join(rt, f"adv_{BASE}.parquet"), os.path.join(rt, f"adv_{tag2}.parquet"))
    log(f"{tag2}: {len(P)} tranche rows, deep paths {n} rungs ({bad} mismatches)")
    if bad:
        raise AssertionError(f"{tag2}: {bad} deep-path mismatches")
    return tag2, tq


def cleanup(tag2):
    RL._IN.pop(tag2, None)
    shutil.rmtree(os.path.join(ROOT, "data", "ladder_v5", f"panel_{tag2}"), ignore_errors=True)
    gc.collect()


def era_mask(era):
    lo, hi = fsim.ERAS[era][1]
    ts = R.data.idx[R.rows]
    return (ts >= pd.Timestamp(lo)) & (ts < pd.Timestamp(hi) + pd.Timedelta(days=1))


def armed_of(pxs32, tq):
    th = np.asarray(pd.Series(R.q_of).map(tq), dtype=np.float64)
    return {c: np.asarray(pxs32[c], np.float32).astype(np.float64) > th for c in R.ls.coins}


def first_fills(Qo):
    q = Qo[(Qo.k == 4.0) & (Qo.fill > 0)]
    return set(zip(pd.to_datetime(q.ts), q.coin))


def run_scenario(name, lag, late_vals, S0=None):
    B = build(name, lag, late_vals)
    tag2, tq = dataset(name, B)
    armed = armed_of(B["pxs32"], tq)
    rows, daily, fills = [], {}, {}
    for era in ERAS:
        out, Qs = cell(tag2, era)
        daily[era] = out
        fills[era] = first_fills(Qs["minute"])
        out.rename_axis("date").to_csv(os.path.join(OUT, f"daily_{era}_{name}.csv"))
        C = KW["C"]
        st, sm = fsim.stats(out["print"], C, era), fsim.stats(out["model"], C, era)
        s = fsim.lat_share(era, KW["theta"])
        fu = {b: float(Qs[b].fill.sum()) for b in Qs}
        fill_blend = fu["minute"] + s * (fu["instant"] - fu["minute"])
        pnl = float(out["print"].sum() * C)
        em = era_mask(era)
        lo, hi = fsim.ERAS[era][1]
        ntr = int(((B["tr"].ts >= lo) & (B["tr"].ts < pd.Timestamp(hi) + pd.Timedelta(days=1))).sum())
        row = dict(scen=name, era=era, sharpe=st["sharpe"], ret_yr=st["ret_yr"], maxdd=st["maxdd"],
                   worst_day=float(out["print"].min()), sharpe_model=sm["sharpe"], ret_yr_model=sm["ret_yr"],
                   first_fills_min=int(((Qs["minute"].k == 4.0) & (Qs["minute"].fill > 0)).sum()),
                   rung_fills_min=int(((Qs["minute"].k > 4.0) & (Qs["minute"].fill > 0)).sum()),
                   first_fills_inst=int(((Qs["instant"].k == 4.0) & (Qs["instant"].fill > 0)).sum()),
                   rung_fills_inst=int(((Qs["instant"].k > 4.0) & (Qs["instant"].fill > 0)).sum()),
                   fill_usd=fill_blend, pnl_usd=pnl, net_bp_per_usd=1e4 * pnl / fill_blend if fill_blend > 0 else np.nan,
                   trades=ntr, armed_minutes=int(sum(int(armed[c][em].sum()) for c in R.ls.coins)))
        if S0 is not None:
            a0, l0 = S0["armed"], S0["lvl"]
            both = sum(int((a0[c][em] & armed[c][em]).sum()) for c in R.ls.coins)
            n0 = sum(int(a0[c][em].sum()) for c in R.ls.coins)
            ns = row["armed_minutes"]
            diffs = []
            for c in R.ls.coins:
                m = em & armed[c] & np.isfinite(B["lvl"][c]) & np.isfinite(l0[c])
                with np.errstate(invalid="ignore", divide="ignore"):
                    diffs.append(1e4 * np.abs(B["lvl"][c][m] / l0[c][m] - 1.0))
            dl = np.concatenate(diffs) if diffs else np.zeros(0)
            f0, fs = S0["fills"][era], fills[era]
            pos = {t: i for i, t in enumerate(R.data.idx[R.rows])}
            arm_at_f0 = sum(1 for (t, c) in f0 if t in pos and armed[c][pos[t]])
            row.update(armed_kept=both / n0 if n0 else np.nan, armed_new=(ns - both) / ns if ns else np.nan,
                       lvl_bp_med=float(np.median(dl)) if len(dl) else np.nan,
                       lvl_bp_p95=float(np.quantile(dl, 0.95)) if len(dl) else np.nan,
                       fills_s0_armed=arm_at_f0 / len(f0) if f0 else np.nan,
                       fills_s0_kept=len(f0 & fs) / len(f0) if f0 else np.nan,
                       fills_new=len(fs - f0) / len(fs) if fs else np.nan)
        rows.append(row)
        log(f"{name} {era}: Sharpe {st['sharpe']:.3f}, {100 * st['ret_yr']:.2f}%/yr (model-priced {sm['sharpe']:.3f}); "
            f"{row['first_fills_min']} first-bid fills, {row['rung_fills_min']} rungs (minute bound)")
        RL._IN.pop(tag2, None)
    S = pd.DataFrame(rows)
    sp = os.path.join(OUT, "summary.csv")
    S.to_csv(sp, mode="a", header=not os.path.exists(sp), index=False)
    res = dict(daily=daily, armed=armed, lvl=B["lvl"], tr=B["tr"], pxs32=B["pxs32"], tag=tag2, fills=fills)
    cleanup(tag2)
    return res, rows


# ------------------------------------------------------------------------------------------------ gate
def gate(S0res):
    """S0 against R2-08: trade list, every-minute panel, and the engine-faithful daily series / best estimate."""
    g = {}
    ref = pd.read_parquet(os.path.join(ROOT, "reports", "wick1m", f"trades_{BASE}.parquet"))
    tr = S0res["tr"]
    m = tr.merge(ref[["ts", "coin", "pred", "px", "sig"]], on=["ts", "coin"], how="outer", suffixes=("", "_ref"),
                 indicator=True)
    g["trades"], g["trades_ref"] = len(tr), len(ref)
    g["trades_identical"] = bool((m._merge == "both").all()) and float(np.abs(m.pred - m.pred_ref).max()) == 0.0 \
        and float(np.abs(m.px - m.px_ref).max()) == 0.0
    g["trades_max_pred_diff"] = float(np.abs(m.pred - m.pred_ref).max())
    worst, mism, n = 0.0, 0, 0
    pdir = os.path.join(ROOT, "data", "ladder_v5", f"panel_{BASE}")
    tq0 = pd.read_csv(os.path.join(pdir, "thr.csv"))
    tq0 = dict(zip(tq0.quarter, tq0.thr))
    th0 = np.asarray(pd.Series(R.q_of).map(tq0), dtype=np.float64)
    for c in R.ls.coins:
        p0 = pd.read_parquet(os.path.join(pdir, f"{c}.parquet")).set_index("ts").pred
        p0 = p0.reindex(R.data.idx[R.rows]).to_numpy(np.float32)
        mine = S0res["pxs32"][c]
        ok = np.isfinite(p0) & np.isfinite(mine)
        worst = max(worst, float(np.abs(p0[ok].astype(np.float64) - mine[ok]).max()) if ok.any() else 0.0)
        mism += int(((p0.astype(np.float64) > th0) != S0res["armed"][c]).sum())
        n += len(p0)
    g.update(panel_max_pred_diff=worst, panel_armed_mismatch=mism, panel_minutes=n)
    ok_all = g["trades_identical"] and mism == 0
    for era in ERAS:
        d = S0res["daily"][era]
        refc = pd.read_parquet(os.path.join(ROOT, "reports", "signal_lab", "cells", f"R2-08__{CFG}__{era}.parquet"))
        diff = float((d["print"] - refc["print"].reindex(d.index)).abs().max())
        st = fsim.stats(d["print"], KW["C"], era)
        tgt = TARGET[era]
        hit = round(st["sharpe"], 2) == tgt[0] and round(100 * st["ret_yr"], 1) == tgt[1]
        g[era] = dict(sharpe=st["sharpe"], ret_pct=100 * st["ret_yr"], target_sharpe=tgt[0], target_ret_pct=tgt[1],
                      max_daily_diff_vs_R2_08_cell=diff, reproduces=bool(hit))
        ok_all = ok_all and hit
    g["passed"] = bool(ok_all)
    json.dump(g, open(os.path.join(OUT, "gate.json"), "w"), indent=1, default=float)
    log(f"GATE {'PASSED' if ok_all else 'FAILED'}: {json.dumps(g, default=float)}")
    return ok_all


# ------------------------------------------------------------------------------------------------ exactness
def bot_arrays(t, drop_btc, mask=None):
    """bot/spot/engine.py arrays(t): the last WIN minutes up to t, each coin's candles with volume > 0, close filled
    forward (limit 30), volume 0 when missing. Candle t itself is not closed yet. BTC also lacks the minutes in
    drop_btc (and those in mask, S4)."""
    d = R.data
    a = t - WIN + 1
    idx = d.idx[a:t + 1]
    cf, vol = {}, {}
    for c in ["BTC"] + list(R.ls.coins):
        D = d.D[c]
        cl = D["close"][a:t + 1].copy()
        v = D["vol"][a:t + 1].copy()
        have = v > 0
        have[-1] = False
        if c == "BTC":
            for s in drop_btc:
                have[s - a] = False
            if mask is not None:
                have &= ~mask[a:t + 1]
        cl[~have] = np.nan
        v[~have] = 0.0
        cf[c] = pd.Series(cl).ffill(limit=30).to_numpy(np.float64)
        vol[c] = v
    return idx, cf, vol


def exact(N, res_by_m, mask=None, lag_full=None, label="S1/S2"):
    """N random decision minutes per era: the unmodified wick.panel on the bot's arrays against the vectorised values
    (lags 1 and 2; with lag_full the scenario's own lag at each minute). Returns (passed, frame of differences)."""
    rng = np.random.default_rng(7)
    rows_out = []
    ms = sorted(res_by_m)
    for era in ERAS:
        em = era_mask(era)
        cand = R.rows[em]
        pick = np.sort(rng.choice(cand, size=min(N, len(cand)), replace=False))
        for t in pick:
            j = t - R.i0
            lags = [int(lag_full[t])] if lag_full is not None else ms
            for m in lags:
                idx, cf, vol = bot_arrays(t, list(range(t - m, t)), mask)
                pn = wick.panel(cf, vol, R.ls.coins, idx, k=R.ls.k, lookback=R.ls.L,
                                keep_rows={c: [len(idx) - 1] for c in R.ls.coins}, wbeta=R.wbeta)
                btc, per = res_by_m[m]
                for c in R.ls.coins:
                    r = pn[c].iloc[0]
                    for f in ["level", "sig"] + R.feats:
                        if f in ("level", "sig"):
                            mine = float(per[c][f][j])
                        elif f in late.BTC_FEATS:
                            mine = float(np.float32(btc[f][j] if f in btc else per[c][f][j]))
                        else:
                            mine = float(R.F0[c][j, R.feats.index(f)])
                        want = float(r[f])
                        rows_out.append((era, int(t), m, c, f, mine, want))
                del pn
    E = pd.DataFrame(rows_out, columns=["era", "t", "lag", "coin", "feat", "mine", "panel"])
    both_nan = E.mine.isna() & E.panel.isna()
    E["abs"] = np.where(both_nan, 0.0, (E.mine - E.panel).abs())
    E["rel"] = np.where(both_nan, 0.0, E["abs"] / np.maximum(E.panel.abs(), 1e-12))
    E["nan_mismatch"] = E.mine.isna() != E.panel.isna()
    bad = E.nan_mismatch | ((E["abs"] > 1e-9) & (E["rel"] > 1e-6))
    agg = E.groupby(["lag", "feat"]).agg(n=("abs", "size"), max_abs=("abs", "max"), max_rel=("rel", "max"),
                                          nan_mismatch=("nan_mismatch", "sum")).reset_index()
    agg["over_tol"] = E[bad].groupby(["lag", "feat"]).size().reindex(pd.MultiIndex.from_frame(agg[["lag", "feat"]])) \
        .fillna(0).astype(int).to_numpy()
    agg.insert(0, "check", label)
    ok = not bool(bad.any())
    log(f"EXACTNESS {label} {'PASSED' if ok else 'FAILED'}: {len(E):,} values at {E.t.nunique()} minutes; largest "
        f"absolute {E['abs'].max():.2e}, largest relative {E['rel'].max():.2e}; over tolerance {int(bad.sum())}")
    if not ok:
        print(E[bad].head(40).to_string(), flush=True)
    return ok, agg


# ------------------------------------------------------------------------------------------------ main
def main():
    global R
    lsim.ensure_frozen()
    score.fix_scale()
    R = Research()
    R.fit()
    R.true_panel()
    names = scenarios()
    # S0 and the gate (always first)
    S0res, _ = run_scenario("S0", None, None)
    if not gate(S0res):
        log("STOP: the gate failed; no other scenario is computed")
        return
    S0 = dict(armed=S0res["armed"], lvl=S0res["lvl"], fills=S0res["fills"])
    del S0res
    gc.collect()
    d = R.data
    T = R.T
    lp = {c: d.lp[c] for c in R.ls.coins}
    need_true = [n for n in names if n in ("S1", "S2") or n.startswith("S3")]
    if need_true or int(OPT["exact"]):
        Bt = late.Base(d.D["BTC"]["cf"], d.D["BTC"]["vol"], lp, R.ls.coins, wbeta=R.wbeta, lookback=R.ls.L)
        LT = late.late_multi(Bt, R.rows, (1, 2), k=R.ls.k, coin_hook=shrink)
        del Bt
        gc.collect()
        log("late values on the true base: lags 1 and 2")
        if int(OPT["exact"]):
            ok, agg = exact(int(OPT["exact"]), LT, label="S1/S2")
            agg.to_csv(os.path.join(OUT, "exact.csv"), index=False)
            if not ok:
                log("STOP: the exactness check failed; no other scenario is computed")
                return
        for n in names:
            if n == "S0" or n.startswith("S4"):
                continue
            if n == "S1":
                lag = np.ones(len(R.rows), np.int8)
            elif n == "S2":
                lag = np.full(len(R.rows), 2, np.int8)
            else:
                lag = late.draw_lags(T, 100 + int(n[3:]))[R.rows]
            run_scenario(n, lag, LT, S0)
        del LT
        gc.collect()
    for n in names:
        if not n.startswith("S4"):
            continue
        k = int(n[3:])
        mask = late.draw_mask(T, 200 + k)
        lag_full = late.draw_lags(T, 100 + k)
        b4, v4 = late.base_s4(d.D["BTC"]["close"], d.D["BTC"]["vol"], mask)
        B4 = late.Base(b4, v4, lp, R.ls.coins, wbeta=R.wbeta, lookback=R.ls.L)
        L4 = late.late_multi(B4, R.rows, (1, 2), k=R.ls.k, coin_hook=shrink)
        del B4
        gc.collect()
        log(f"late values on S4 seed {k}'s base ({int(mask.sum()):,} of {T:,} BTC minutes dropped)")
        if k == 1 and int(OPT["exact4"]):
            ok, agg = exact(int(OPT["exact4"]), L4, mask=mask, lag_full=lag_full, label="S4s1")
            p = os.path.join(OUT, "exact.csv")
            agg.to_csv(p, mode="a", header=not os.path.exists(p), index=False)
            if not ok:
                log("STOP: the S4 exactness check failed")
                return
        run_scenario(n, lag_full[R.rows], L4, S0)
        del L4
        gc.collect()
    log("done")


def shrink(c, fs):
    """Keep level, sig and z_res60 in float64 (z_res60 feeds the alts features), the rest as float32."""
    for m, f in fs.items():
        for k in list(f):
            if k not in ("level", "sig", "z_res60"):
                f[k] = f[k].astype(np.float32)
    return fs


if __name__ == "__main__":
    main()
