#!/usr/bin/env python3
"""Late-cut replay (reports/owner/late_cut_prereg.md): R2-08 rebuilt with coin c's newest row (minute t-1) taken from
trade prints at its candidate minutes t, priced on the frozen engine-faithful simulator at the best estimate's
configuration (cash rule + print exit costs, S*, theta 0.5, $250K). The harness is scripts/owner/late_btc/replay.py's
(Research, the gate, the simulator calls and the summary measures are copied from it unchanged).

  python scripts/owner/late_cut/replay.py <main|early> --job export
  python scripts/owner/late_cut/replay.py <main|early> --job partA [--exact 200]
  python scripts/owner/late_cut/replay.py <main|early> --job partB [--exact 200]

Jobs (every job builds R2-08, fits the models, runs S0 and the gate first, and stops if the gate fails):
  export  the candidate table: every S0 candidate minute with S0's level, sigma, score, armed state and the research's
          row t-1 (close and volume) -> reports/owner/late_cut/data/candidates_<base>.csv.gz
  partA   main: M0 in sel and chk, M5 M10 Q5 Q10 in sel; early: M0 in 2022-23.
  partB   main: M5 M10 Q5 Q10 in chk; early: M5 M10 Q5 Q10 in 2022-23. Refused unless the plan's deviation log holds
          the entry that names the late bar (step 5 of the brief).
In partA and partB, after the gate: the exactness check (--exact N candidates per era and bar), then the decisions at
the candidate minutes of every scenario and era of the job (measure 1; the placebo is the five under M0), then the
pricing of each scenario-era (measures 2 and 3; measure 4 from the daily series by summarize.py).
Scenario rows come from reports/owner/late_cut/prints/derived_*.parquet (one row per candidate, prints_job.py).
Outputs (derived tables only): reports/owner/late_cut/runs/<base>_<job>/.
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
OPT = {"job": "export", "exact": "200"}
_rest = sys.argv[2:]
for _i in range(0, len(_rest), 2):
    if not _rest[_i].startswith("--") or _rest[_i][2:] not in OPT or _i + 1 >= len(_rest):
        raise SystemExit(f"bad option {_rest[_i:]}")
    OPT[_rest[_i][2:]] = _rest[_i + 1]
JOB = OPT["job"]
PLAN = {("main", "partA"): [("M0", "sel"), ("M0", "chk"), ("M5", "sel"), ("M10", "sel"), ("Q5", "sel"), ("Q10", "sel")],
        ("early", "partA"): [("M0", "early")],
        ("main", "partB"): [("M5", "chk"), ("M10", "chk"), ("Q5", "chk"), ("Q10", "chk")],
        ("early", "partB"): [("M5", "early"), ("M10", "early"), ("Q5", "early"), ("Q10", "early")]}
if JOB not in ("export", "partA", "partB"):
    raise SystemExit(f"unknown job {JOB}")
PREREG = os.path.join(ROOT, "reports", "owner", "late_cut_prereg.md")
if JOB == "partB" and "Late bar named:" not in open(PREREG).read().split("## Deviation log", 1)[1]:
    raise SystemExit("partB refused: the deviation log does not name the late bar yet")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "signal_lab"))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import score  # noqa: E402  (first: lsim imports ladder v5's gates before fsim puts scripts/hunt on the path)
_argv, sys.argv = sys.argv, [sys.argv[0], BASE]
import model  # noqa: E402  (the signal lab's pipeline: deep paths, dataset registration)
sys.argv = _argv
sys.path.insert(0, HERE)
import cut  # noqa: E402

core, RUN, VV, lgb, wick, fsim, sim = model.core, model.RUN, model.VV, model.lgb, model.wick, model.fsim, model.sim
lsim, RL = score.lsim, score.RL
ws = core.ws
OUT = os.path.join(ROOT, "reports", "owner", "late_cut", "runs", f"{BASE}_{JOB}")
DATA = os.path.join(ROOT, "reports", "owner", "late_cut", "data")
PRINTS = os.path.join(ROOT, "reports", "owner", "late_cut", "prints")
os.makedirs(OUT, exist_ok=True)
CFG = "S_0.5"
KW = lsim.CONFIGS[CFG]
ERAS = model.ERA_OF[BASE]
TARGET = {"sel": (2.94, 22.8), "chk": (2.66, 19.1), "early": (1.91, 11.1)}     # findings: best estimate at $250K
WIN = 11 * 1440                                                                 # bot/spot/engine.py WINDOW_MIN
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:7.0f}s] {msg}", flush=True)


# ------------------------------------------------------------------------------------------------ the research
class Research:
    """R2-08 as the wick lab builds it: data, level set, candidates, features, labels, kept walk-forward models.
    (late_btc/replay.py, unchanged.)"""

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
S0P = {}          # S0's float64 predictions at every test minute, by coin
S0C = {}          # S0's candidate minutes (absolute rows), by coin


# ------------------------------------------------------------------------------------------------ one scenario
class LS2:
    """A level set whose levels, sigma, beta, candidates and candidate features are the scenario's (core.simulate and
    core.Exit read these attributes). (late_btc/replay.py, unchanged.)"""

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


def predict(c, j, F):
    """Mean of the quarter's three boosters on feature rows F (float32 [n, 23]) at test rows j (relative to i0)."""
    out = np.full(len(j), np.nan)
    qs = R.q_of[j]
    for q in np.unique(qs):
        m = qs == q
        ms, _ = R.models[q]
        fr = pd.DataFrame(F[m], columns=R.feats)
        out[m] = np.mean([mm.predict(fr) for mm in ms], axis=0)
    return out


def build(name, ch=None):
    """Levels, features, candidates, predictions and the trade list of one scenario. ch: None for S0, else {coin:
    dict(t=absolute rows, level, sig, beta, F, pred)} for the changed candidate rows (late_btc's build with its BTC
    transform replaced by these rows)."""
    d, ls, i0 = R.data, R.ls, R.i0
    feats = R.feats
    lvl_f, sig_f, beta_f, cands, rows_x = {}, {}, {}, {}, []
    pxs32, lvl_post = {}, {}
    for c in ls.coins:
        lv, sg, bt = ls.lvl[c][i0:], ls.sig[c][i0:], ls.beta[c][i0:]
        F = R.F0[c]
        x = ch.get(c) if ch is not None else None
        if ch is None:
            p64 = np.full(len(R.rows), np.nan)
            for q, (ms, _) in R.models.items():
                mq = R.q_of == q
                if mq.any():
                    fr = pd.DataFrame(F[mq], columns=feats)
                    p64[mq] = np.mean([m.predict(fr) for m in ms], axis=0)
            S0P[c] = p64
        else:
            p64 = S0P[c].copy()
            if x is not None and len(x["t"]):
                j = x["t"] - i0
                lv, sg, bt = lv.copy(), sg.copy(), bt.copy()
                lv[j], sg[j], bt[j] = tick_round(c, x["level"]), x["sig"], x["beta"]
                p64[j] = x["pred"]
        lvl_post[c] = lv
        D = d.D[c]
        tk = ls.tick(c)[i0:]
        with np.errstate(invalid="ignore"):
            fill = (D["open"][i0:] > lv) & (D["low"][i0:] <= lv * (1 - tk))
        cd = R.rows[fill]
        cd = cd[cd > 1500]
        if ch is None:
            ref = ls.cands[c][ls.cands[c] >= i0]
            assert np.array_equal(cd, ref), f"S0 candidates of {c} differ from the level set's"
            S0C[c] = cd
        else:
            assert np.isin(cd, S0C[c]).all(), f"{name}: a candidate of {c} that S0 does not have"
        cands[c] = cd
        L_, S_, B_ = ls.lvl[c].copy(), ls.sig[c].copy(), ls.beta[c].copy()
        L_[i0:], S_[i0:], B_[i0:] = lv, sg, bt
        lvl_f[c], sig_f[c], beta_f[c] = L_, S_, B_
        pxs32[c] = p64.astype(np.float32)
        if len(cd):
            Fc = F[cd - i0].copy()
            if x is not None and len(x["t"]):
                hit = np.isin(cd, x["t"])
                if hit.any():
                    k = np.searchsorted(x["t"], cd[hit])
                    Fc[hit] = x["F"][k]
            f = pd.DataFrame(Fc, columns=feats)
            f["coin"], f["pos"], f["ts"] = c, cd, d.idx[cd]
            f["episode"] = np.cumsum(np.r_[1, np.diff(cd) > 1])
            f["sig"] = S_[cd]
            f["px"] = L_[cd]
            f["pred"] = p64[cd - i0]
            rows_x.append(f)
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
    """score.cell at S_0.5, also returning each bound's tranche frame, info and print-priced daily series."""
    A = RL.era_arrays(tag2, era, KW["theta"], KW["C"], KW["today"])
    dd, Qs, infos = {}, {}, {}
    for bound in ("minute", "instant"):
        Rr = RL.replay(A, theta=KW["theta"], C=KW["C"], bound=bound, policy="engine")
        _, Qo, info = RL.evaluate_live(A, Rr, KW["theta"], KW["C"], era, KW["cost_mult"])
        for cost in ("model", "print"):
            dd[(bound, cost)], _, _ = lsim.rem_daily(Qo, info, CFG, era, KW["C"], cost=cost)
        Qs[bound] = Qo[[c for c in Qo.columns if c != "path"]].copy()
        infos[bound] = info
    out = pd.DataFrame({cost: lsim.blend(era, KW["theta"], dd[("minute", cost)], dd[("instant", cost)])
                        for cost in ("model", "print")})
    return out, Qs, infos, dd


def dataset(name, B):
    """Trade list -> tranche dataset -> every-minute panel -> deep paths -> ADV table, under tag <era>_LC<name>."""
    tag2 = f"{BASE}_LC{name}"
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


def era_of_ts(ts):
    out = np.full(len(ts), "", object)
    for era in ERAS:
        lo, hi = fsim.ERAS[era][1]
        out[(ts >= pd.Timestamp(lo)) & (ts < pd.Timestamp(hi) + pd.Timedelta(days=1))] = era
    return out


def armed_of(pxs32, tq):
    th = np.asarray(pd.Series(R.q_of).map(tq), dtype=np.float64)
    return {c: np.asarray(pxs32[c], np.float32).astype(np.float64) > th for c in R.ls.coins}


def first_fills(Qo):
    q = Qo[(Qo.k == 4.0) & (Qo.fill > 0)]
    return set(zip(pd.to_datetime(q.ts), q.coin))


# ------------------------------------------------------------------------------------------------ measure 2
def row_pnl(Q, info, era, daily_print):
    """lsim.rem_daily (print-priced) per tranche row: each row's P&L as it enters the era's daily series (a part
    booked outside the era's days is left out, as rem_daily leaves it out). Checked: rows sum to rem_daily's total."""
    kw = KW
    tag, (lo, hi) = fsim.ERAS[era]
    tk_fee = info["taker_bp"] / 1e4
    hs = fsim.HS_BP * kw["cost_mult"] / 1e4
    y = fsim.IMPACT_Y * kw["cost_mult"]
    sc = fsim.today_scale(RL.inputs(tag)["P"], lo, hi) if kw["today"] else {}
    rem = np.maximum((Q.fill - Q.tp_fill).to_numpy(), 0.0)
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    fsc = Q.coin.map(sc).fillna(1.0).to_numpy() if sc else np.ones(len(Q))
    g60 = Q.g60.to_numpy() / 1e4
    coin, fill_t = Q.coin.to_numpy(), Q.fill_t.to_numpy()
    pc = lsim.pcost()
    pnl = np.zeros(len(Q))
    for i in np.nonzero(rem > 0)[0]:
        Rr = rem[i]
        mdl = hs + y * vol_d[i] * np.sqrt(Rr / adv[i])
        fb = 1e4 * fsim.IMPACT_Y * vol_d[i] * np.sqrt(Rr / adv[i])
        ci = pc.cost(coin[i], pd.Timestamp(fill_t[i]), 0, Rr / fsc[i], fb_bp=fb)
        if not np.isfinite(ci):
            ci = mdl
        pnl[i] = Rr * (g60[i] - tk_fee - ci)
    idx = pd.date_range(lo, hi, freq="D")
    d1 = pd.DatetimeIndex(Q.tp_t.dt.floor("D"))
    d2 = pd.DatetimeIndex((Q.fill_t + pd.Timedelta(minutes=60)).dt.floor("D"))
    in1, in2 = d1.isin(idx), d2.isin(idx) & (rem > 0)
    out = np.where(in1, (Q.pnl_tp - Q.entry_cost).to_numpy(), 0.0) + np.where(in2, pnl, 0.0)
    tot = float(daily_print.sum() * KW["C"])
    assert abs(out.sum() - tot) <= 1e-9 * max(1.0, abs(tot)), f"row P&L {out.sum()} != daily {tot}"
    return out


def parent_book(Qs, infos, dd, era):
    """{bound: DataFrame(ts, coin, pnl, usd)} by parent (first bid and its rungs) and the minute bound's first-bid
    fill keys."""
    out = {}
    for b in ("minute", "instant"):
        Q = Qs[b]
        p = row_pnl(Q, infos[b], era, dd[(b, "print")])
        g = pd.DataFrame({"ts": pd.to_datetime(Q.ts).to_numpy(), "coin": Q.coin.to_numpy(), "pnl": p,
                          "usd": Q.fill.to_numpy(np.float64)}).groupby(["ts", "coin"]).sum()
        out[b] = g
    return out, first_fills(Qs["minute"])


def group_net(book, keys, era):
    s = fsim.lat_share(era, KW["theta"])
    vals = {}
    for b in ("minute", "instant"):
        g = book[b]
        ix = pd.MultiIndex.from_tuples(sorted(keys), names=["ts", "coin"]) if keys else None
        sub = g.reindex(ix).fillna(0.0) if keys else g.iloc[:0]
        vals[b] = (float(sub.pnl.sum()), float(sub.usd.sum()))
    pnl = vals["minute"][0] + s * (vals["instant"][0] - vals["minute"][0])
    usd = vals["minute"][1] + s * (vals["instant"][1] - vals["minute"][1])
    return dict(n=len(keys), usd=usd, pnl=pnl, net_bp=1e4 * pnl / usd if usd > 0 else np.nan)


def measure2(name, era, S0b, Sb):
    (b0, f0), (bs, fs) = S0b, Sb
    rows = []
    for grp, coins in (("twelve", cut.TWELVE), ("five", cut.FIVE), ("all", cut.TWELVE + cut.FIVE)):
        F0 = {k for k in f0 if k[1] in coins}
        Fs = {k for k in fs if k[1] in coins}
        for lab, book, keys in (("dropped", b0, F0 - Fs), ("added", bs, Fs - F0), ("kept_scen", bs, F0 & Fs),
                                ("kept_s0", b0, F0 & Fs), ("all_s0", b0, F0), ("all_scen", bs, Fs)):
            rows.append(dict(scen=name, era=era, group=grp, fills=lab, **group_net(book, keys, era)))
    return rows


# ------------------------------------------------------------------------------------------------ pricing
def price(name, B, eras, S0book=None):
    """Dataset, every-minute panel and the engine-faithful cells of `eras`; summary rows and daily series."""
    tag2, tq = dataset(name, B)
    rows, books = [], {}
    for era in eras:
        out, Qs, infos, dd = cell(tag2, era)
        out.rename_axis("date").to_csv(os.path.join(OUT, f"daily_{era}_{name}.csv"))
        C = KW["C"]
        st, sm = fsim.stats(out["print"], C, era), fsim.stats(out["model"], C, era)
        s = fsim.lat_share(era, KW["theta"])
        fu = {b: float(Qs[b].fill.sum()) for b in Qs}
        fill_blend = fu["minute"] + s * (fu["instant"] - fu["minute"])
        pnl = float(out["print"].sum() * C)
        lo, hi = fsim.ERAS[era][1]
        ntr = int(((B["tr"].ts >= lo) & (B["tr"].ts < pd.Timestamp(hi) + pd.Timedelta(days=1))).sum())
        row = dict(scen=name, era=era, sharpe=st["sharpe"], ret_yr=st["ret_yr"], maxdd=st["maxdd"],
                   worst_day=float(out["print"].min()), sharpe_model=sm["sharpe"], ret_yr_model=sm["ret_yr"],
                   first_fills_min=int(((Qs["minute"].k == 4.0) & (Qs["minute"].fill > 0)).sum()),
                   rung_fills_min=int(((Qs["minute"].k > 4.0) & (Qs["minute"].fill > 0)).sum()),
                   first_fills_inst=int(((Qs["instant"].k == 4.0) & (Qs["instant"].fill > 0)).sum()),
                   rung_fills_inst=int(((Qs["instant"].k > 4.0) & (Qs["instant"].fill > 0)).sum()),
                   fill_usd=fill_blend, pnl_usd=pnl, net_bp_per_usd=1e4 * pnl / fill_blend if fill_blend > 0 else np.nan,
                   trades=ntr)
        rows.append(row)
        books[era] = parent_book(Qs, infos, dd, era)
        log(f"{name} {era}: Sharpe {st['sharpe']:.3f}, {100 * st['ret_yr']:.2f}%/yr (model-priced {sm['sharpe']:.3f}); "
            f"{row['first_fills_min']} first-bid fills, {row['rung_fills_min']} rungs (minute bound)")
        RL._IN.pop(tag2, None)
    S = pd.DataFrame(rows)
    sp = os.path.join(OUT, "summary.csv")
    S.to_csv(sp, mode="a", header=not os.path.exists(sp), index=False)
    if S0book is not None:
        m2 = []
        for era in eras:
            m2 += measure2(name, era, S0book[era], books[era])
        p = os.path.join(OUT, "fills.csv")
        pd.DataFrame(m2).to_csv(p, mode="a", header=not os.path.exists(p), index=False)
    cleanup(tag2)
    return books, tq


# ------------------------------------------------------------------------------------------------ gate
def gate(S0tr, pxs32, armed, daily):
    """S0 against R2-08: trade list, every-minute panel, and the engine-faithful daily series / best estimate.
    (late_btc/replay.py's gate.)"""
    g = {}
    ref = pd.read_parquet(os.path.join(ROOT, "reports", "wick1m", f"trades_{BASE}.parquet"))
    tr = S0tr
    m = tr.merge(ref[["ts", "coin", "pred", "px", "sig"]], on=["ts", "coin"], how="outer", suffixes=("", "_ref"),
                 indicator=True)
    g["trades"], g["trades_ref"] = len(tr), len(ref)
    g["trades_identical"] = bool((m._merge == "both").all()) and float(np.abs(m.pred - m.pred_ref).max()) < 1e-9 \
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
        mine = pxs32[c]
        ok = np.isfinite(p0) & np.isfinite(mine)
        worst = max(worst, float(np.abs(p0[ok].astype(np.float64) - mine[ok]).max()) if ok.any() else 0.0)
        mism += int(((p0.astype(np.float64) > th0) != armed[c]).sum())
        n += len(p0)
    g.update(panel_max_pred_diff=worst, panel_armed_mismatch=mism, panel_minutes=n)
    ok_all = g["trades_identical"] and mism == 0
    for era in ERAS:
        d = daily[era]
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


def run_s0():
    """S0 (one build over the base's eras), priced; the gate. Returns (passed, S0 book by era)."""
    B = build("S0")
    tag2, tq = dataset("S0", B)
    armed = armed_of(B["pxs32"], tq)
    daily, books, rows = {}, {}, []
    for era in ERAS:
        out, Qs, infos, dd = cell(tag2, era)
        daily[era] = out
        out.rename_axis("date").to_csv(os.path.join(OUT, f"daily_{era}_S0.csv"))
        C = KW["C"]
        st, sm = fsim.stats(out["print"], C, era), fsim.stats(out["model"], C, era)
        s = fsim.lat_share(era, KW["theta"])
        fu = {b: float(Qs[b].fill.sum()) for b in Qs}
        fill_blend = fu["minute"] + s * (fu["instant"] - fu["minute"])
        pnl = float(out["print"].sum() * C)
        lo, hi = fsim.ERAS[era][1]
        ntr = int(((B["tr"].ts >= lo) & (B["tr"].ts < pd.Timestamp(hi) + pd.Timedelta(days=1))).sum())
        rows.append(dict(scen="S0", era=era, sharpe=st["sharpe"], ret_yr=st["ret_yr"], maxdd=st["maxdd"],
                         worst_day=float(out["print"].min()), sharpe_model=sm["sharpe"], ret_yr_model=sm["ret_yr"],
                         first_fills_min=int(((Qs["minute"].k == 4.0) & (Qs["minute"].fill > 0)).sum()),
                         rung_fills_min=int(((Qs["minute"].k > 4.0) & (Qs["minute"].fill > 0)).sum()),
                         first_fills_inst=int(((Qs["instant"].k == 4.0) & (Qs["instant"].fill > 0)).sum()),
                         rung_fills_inst=int(((Qs["instant"].k > 4.0) & (Qs["instant"].fill > 0)).sum()),
                         fill_usd=fill_blend, pnl_usd=pnl,
                         net_bp_per_usd=1e4 * pnl / fill_blend if fill_blend > 0 else np.nan, trades=ntr))
        if JOB == "export":                 # information here (measure 2 is computed in partA / partB)
            try:
                parent_book(Qs, infos, dd, era)
                log(f"S0 {era}: per-parent P&L sums to the daily series")
            except AssertionError as err:
                log(f"S0 {era}: per-parent P&L check FAILED (information): {err}")
        else:
            books[era] = parent_book(Qs, infos, dd, era)
        log(f"S0 {era}: Sharpe {st['sharpe']:.3f}, {100 * st['ret_yr']:.2f}%/yr; {rows[-1]['first_fills_min']} "
            f"first-bid fills (minute bound)")
        RL._IN.pop(tag2, None)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "summary.csv"), index=False)
    ok = gate(B["tr"], B["pxs32"], armed, daily)
    cleanup(tag2)
    return ok, books, B


# ------------------------------------------------------------------------------------------------ export
def export():
    """The candidate table: S0's candidate minutes with S0's level, sigma, score and armed state, and the research's
    row t-1 (close and volume; and minute t's, for the fetch cost estimate)."""
    d, i0 = R.data, R.i0
    tq = {q: t_ for q, (_, t_) in R.models.items()}
    parts = []
    for c in R.ls.coins:
        t = S0C[c]
        if not len(t):
            continue
        D = d.D[c]
        ts = d.idx[t]
        thr = np.asarray(pd.Series(R.q_of[t - i0]).map(tq), dtype=np.float64)
        pred = S0P[c][t - i0]
        parts.append(pd.DataFrame(dict(
            base=BASE, era=era_of_ts(ts), coin=c, ts=ts, pos=t, level=R.ls.lvl[c][t], sig=R.ls.sig[c][t], pred=pred,
            thr=thr, armed=pred > thr, close_prev=D["cf"][t - 1], vol_prev=D["vol"][t - 1],
            candle_prev=D["vol"][t - 1] > 0, close_t=D["cf"][t], vol_t=D["vol"][t])))
    E = pd.concat(parts, ignore_index=True).sort_values(["coin", "ts"]).reset_index(drop=True)
    assert (E.era != "").all()
    os.makedirs(DATA, exist_ok=True)
    E.to_csv(os.path.join(DATA, f"candidates_{BASE}.csv.gz"), index=False, float_format="%.17g",
             date_format="%Y-%m-%d %H:%M:%S")
    log(f"candidate table: {len(E):,} candidates; by era {E.era.value_counts().to_dict()}; armed "
        f"{int(E.armed.sum()):,}")


# ------------------------------------------------------------------------------------------------ scenario rows
def load_prints():
    """Derived print rows of this base's candidates and the window status."""
    fs = sorted(f for f in os.listdir(PRINTS) if f.startswith("derived_") and f.endswith(".parquet"))
    Dv = pd.concat([pd.read_parquet(os.path.join(PRINTS, f)) for f in fs], ignore_index=True)
    Dv["ts"] = pd.to_datetime(Dv.ts).astype("datetime64[ns]")
    Dv = Dv[Dv.base == BASE]
    assert not Dv.duplicated(["coin", "ts"]).any()
    return Dv


class Bars:
    """Per coin: the S0 candidates, their print bars, and the changed values of each bar s the job needs."""

    def __init__(self, Dv, need):
        """need: {s: set of eras}: the bars (seconds) and eras the job may compute."""
        d = R.data
        E = pd.read_csv(os.path.join(DATA, f"candidates_{BASE}.csv.gz"), parse_dates=["ts"],
                        float_precision="round_trip")
        self.cand = {}
        for c in R.ls.coins:
            t = S0C[c]
            e = E[E.coin == c]
            assert np.array_equal(e.pos.to_numpy(), t), f"{c}: candidates differ from the exported table"
            assert np.array_equal(e.level.to_numpy(), R.ls.lvl[c][t], equal_nan=True), f"{c}: levels differ"
            ts = pd.DatetimeIndex(d.idx[t]).astype("datetime64[ns]")
            k = pd.DataFrame({"coin": c, "ts": ts}).merge(Dv, on=["coin", "ts"], how="left")
            assert len(k) == len(t) and (k.ts.to_numpy() == ts.to_numpy()).all()
            ok = (k.status == "complete").to_numpy()
            D = d.D[c]
            u = t - 1
            carry = cut.carry_close(D["cf"], D["vol"], u)
            info = dict(t=t, ts=ts, era=era_of_ts(ts), complete=ok, n0=k["n_0"].fillna(-1).to_numpy(np.int64),
                        close_prev=D["cf"][u], vol_prev=D["vol"][u], bar={})
            for s in cut.SECONDS:                 # stored as the research stores its candles: float32
                n = k[f"n_{s}"].fillna(0).to_numpy(np.int64)
                cl = np.where(n > 0, cut.as_candle(k[f"close_{s}"].to_numpy(np.float64)), carry)
                vo = np.where(n > 0, cut.as_candle(k[f"vol_{s}"].to_numpy(np.float64)), 0.0)
                info["bar"][s] = (cl, vo, n)
            self.cand[c] = info
        self.val = {}
        for c in R.ls.coins:
            x = self.cand[c]
            if not len(x["t"]):
                continue
            C = cut.Coin(D_cf(c), D_vol(c), D_cf("BTC"), x["t"], k=R.ls.k, lookback=R.ls.L, wbeta=R.wbeta)
            self.selfcheck(c, C)
            for s, eras in need.items():
                cl, vo, _ = x["bar"][s]
                same = ((cl == x["close_prev"]) | (np.isnan(cl) & np.isnan(x["close_prev"]))) & (vo == x["vol_prev"])
                sel = np.nonzero(x["complete"] & ~same & np.isin(x["era"], list(eras)))[0]
                self.val[(c, s)] = self._values(c, C, sel, cl[sel], vo[sel])
            del C
            gc.collect()
        log(f"self-check (information): the candle's own row fed to the changed-value code reproduces S0's posted "
            f"level and changed features to relative {self.worst:.1e}")
        log("changed values: " + ", ".join(f"s={s}: {sum(len(v['sel']) for (c_, s_), v in self.val.items() if s_ == s):,}"
                                           for s in need))

    worst = 0.0

    def selfcheck(self, c, C):
        """Information: the changed-value code fed the candle's own row reproduces S0's level and features."""
        x = self.cand[c]
        v = C.values(x["close_prev"], x["vol_prev"])
        F0 = R.F0[c][x["t"] - R.i0]
        for f in cut.CHANGED:
            a, b = v[f].astype(np.float32).astype(np.float64), F0[:, R.feats.index(f)].astype(np.float64)
            ok = np.isfinite(a) & np.isfinite(b)
            if ok.any():
                self.worst = max(self.worst, float((np.abs(a[ok] - b[ok]) / np.maximum(np.abs(b[ok]), 1e-12)).max()))
        lv = R.ls.lvl[c][x["t"]]
        ok = np.isfinite(lv)
        if ok.any():
            self.worst = max(self.worst, float(np.abs(tick_round(c, v["level"][ok]) / lv[ok] - 1).max()))

    def _values(self, c, C, sel, cl, vo):
        i0 = R.i0
        t = self.cand[c]["t"][sel]
        assert ((vo > 0) | (np.isnan(cl) | (cl == cut.carry_close(D_cf(c), D_vol(c), t - 1)))).all()
        v = C.values(cl, vo, sel=sel)
        F = R.F0[c][t - i0].copy()
        for f in cut.CHANGED:
            F[:, R.feats.index(f)] = v[f].astype(np.float32)
        p0 = S0P[c][t - i0]
        pred = p0.copy()
        diff = ~np.all((F == R.F0[c][t - i0]) | (np.isnan(F) & np.isnan(R.F0[c][t - i0])), axis=1)
        if diff.any():
            pred[diff] = predict(c, t[diff] - i0, F[diff])
        return dict(sel=sel, t=t, level=v["level"], sig=v["sig"], beta=v["beta"], F=F, pred=pred, close=cl, vol=vo)


def D_cf(c):
    return R.data.D[c]["cf"]


def D_vol(c):
    return R.data.D[c]["vol"]


def scenario(BR, name, era):
    """Changes (for build) and per-candidate decisions of scenario `name` in `era`."""
    s_late, quiet = cut.SCEN[name]
    d, i0 = R.data, R.i0
    tq = {q: t_ for q, (_, t_) in R.models.items()}
    ch, rows = {}, []
    for c in R.ls.coins:
        x = BR.cand[c]
        if not len(x["t"]):
            continue
        em = x["era"] == era
        s_use = cut.pick_bar(x["n0"], s_late, quiet)
        n = len(x["t"])
        lvl_s = R.ls.lvl[c][x["t"]].copy()
        pred_s = S0P[c][x["t"] - i0].copy()
        changed = np.zeros(n, bool)
        parts = []
        for s in sorted(set(s_use[em].tolist())):
            v = BR.val[(c, s)]
            want = em & (s_use == s)
            hit = np.isin(v["sel"], np.nonzero(want)[0])
            if not hit.any():
                continue
            j = v["sel"][hit]
            changed[j] = True
            lvl_s[j] = tick_round(c, v["level"][hit])
            pred_s[j] = v["pred"][hit]
            parts.append(dict(j=j, t=v["t"][hit], level=v["level"][hit], sig=v["sig"][hit], beta=v["beta"][hit],
                              F=v["F"][hit], pred=v["pred"][hit]))
        if parts:
            j = np.concatenate([p["j"] for p in parts])
            o = np.argsort(j)
            ch[c] = {k: np.concatenate([p[k] for p in parts])[o] for k in ("t", "level", "sig", "beta", "F", "pred")}
        D = d.D[c]
        t = x["t"]
        tk = R.ls.tick(c)[t]
        with np.errstate(invalid="ignore"):
            touched = (D["open"][t] > lvl_s) & (D["low"][t] <= lvl_s * (1 - tk))
        thr = np.asarray(pd.Series(R.q_of[t - i0]).map(tq), dtype=np.float64)
        p0 = S0P[c][t - i0]
        cl = np.vstack([x["bar"][s][0] for s in cut.SECONDS])[s_use, np.arange(n)]
        vo = np.vstack([x["bar"][s][1] for s in cut.SECONDS])[s_use, np.arange(n)]
        with np.errstate(invalid="ignore", divide="ignore"):
            dv = np.where(x["vol_prev"] > 0, np.abs(vo / x["vol_prev"] - 1.0) > 0.01, vo > 0)
        dcl = ~((cl == x["close_prev"]) | (np.isnan(cl) & np.isnan(x["close_prev"])))
        rows.append(pd.DataFrame(dict(
            scen=name, era=era, coin=c, ts=x["ts"], complete=x["complete"], n0=x["n0"], s_used=s_use, changed=changed,
            differs_close=dcl & x["complete"], differs_vol=dv & x["complete"], pred0=p0, pred=pred_s, thr=thr,
            armed0=p0 > thr, armed_pred=pred_s > thr, touched=touched, armed=touched & (pred_s > thr)))[em])
    return ch, pd.concat(rows, ignore_index=True)


def decisions_table(Dc):
    out = []
    for (scen, era), G in Dc.groupby(["scen", "era"], sort=False):
        for grp, coins in (("twelve", cut.TWELVE), ("five", cut.FIVE), ("all", cut.TWELVE + cut.FIVE)):
            g = G[G.coin.isin(coins)]
            dp = (g.pred - g.pred0).abs()
            out.append(dict(scen=scen, era=era, group=grp, candidates=len(g), complete=int(g.complete.sum()),
                            row_changed=int(g.changed.sum()), differs_close=int(g.differs_close.sum()),
                            differs_vol_1pct=int(g.differs_vol.sum()), armed_s0=int(g.armed0.sum()),
                            armed_scen=int(g.armed.sum()), both=int((g.armed0 & g.armed).sum()),
                            s0_only=int((g.armed0 & ~g.armed).sum()), scen_only=int((~g.armed0 & g.armed).sum()),
                            changed_decisions=int((g.armed0 != g.armed).sum()),
                            changed_share=float((g.armed0 != g.armed).mean()) if len(g) else np.nan,
                            not_touched=int((~g.touched).sum()), armed_by_pred=int(g.armed_pred.sum()),
                            changed_by_pred=int((g.armed0 != g.armed_pred).sum()),
                            score_diff_med=float(dp.median()) if len(g) else np.nan,
                            score_diff_p90=float(dp.quantile(0.9)) if len(g) else np.nan,
                            score_diff_med_changed=float(dp[g.changed].median()) if g.changed.any() else np.nan,
                            score_diff_p90_changed=float(dp[g.changed].quantile(0.9)) if g.changed.any() else np.nan))
    return pd.DataFrame(out)


# ------------------------------------------------------------------------------------------------ exactness
def bot_arrays_rep(t, c, close_new, vol_new):
    """late_btc's bot_arrays(t) (bot/spot/engine.py arrays: the last WIN minutes up to t, candles with volume > 0, close
    filled forward with limit 30, volume 0 when missing; candle t not closed yet), with coin c's row t-1 replaced by
    (close_new, vol_new): volume 0 = no row."""
    d = R.data
    a = t - WIN + 1
    idx = d.idx[a:t + 1]
    cf, vol = {}, {}
    for cc in ["BTC"] + list(R.ls.coins):
        D = d.D[cc]
        cl = D["close"][a:t + 1].copy()
        v = D["vol"][a:t + 1].copy()
        have = v > 0
        have[-1] = False
        if cc == c:
            cl[-2], v[-2], have[-2] = close_new, vol_new, vol_new > 0
        cl[~have] = np.nan
        v[~have] = 0.0
        cf[cc] = pd.Series(cl).ffill(limit=30).to_numpy(np.float64)
        vol[cc] = v
    return idx, cf, vol


def exact(BR, plan_bars, N):
    """N candidates per era and bar among those whose bar differs from the candle's row: the unmodified wick.panel on
    the bot's arrays with that row replaced against the values the scenario uses. Returns (passed, aggregate)."""
    rng = np.random.default_rng(7)
    out = []
    for era in ERAS:
        for s in sorted(plan_bars):
            if era not in plan_bars[s]:
                continue
            pool = [(c, i) for c in R.ls.coins if (c, s) in BR.val for i in range(len(BR.val[(c, s)]["t"]))
                    if BR.cand[c]["era"][BR.val[(c, s)]["sel"][i]] == era]
            pick = rng.choice(len(pool), size=min(N, len(pool)), replace=False)
            for p in np.sort(pick):
                c, i = pool[p]
                v = BR.val[(c, s)]
                t = int(v["t"][i])
                idx, cf, vol = bot_arrays_rep(t, c, v["close"][i], v["vol"][i])
                pn = wick.panel(cf, vol, R.ls.coins, idx, k=R.ls.k, lookback=R.ls.L, keep_rows={c: [len(idx) - 1]},
                                wbeta=R.wbeta)[c].iloc[0]
                for f in ["level", "sig"] + R.feats:
                    mine = float(v[f][i]) if f in ("level", "sig") else float(v["F"][i, R.feats.index(f)])
                    out.append((era, s, t, c, f, mine, float(pn[f])))
                del pn
    E = pd.DataFrame(out, columns=["era", "bar", "t", "coin", "feat", "mine", "panel"])
    both_nan = E.mine.isna() & E.panel.isna()
    E["abs"] = np.where(both_nan, 0.0, (E.mine - E.panel).abs())
    E["rel"] = np.where(both_nan, 0.0, E["abs"] / np.maximum(E.panel.abs(), 1e-12))
    E["nan_mismatch"] = E.mine.isna() != E.panel.isna()
    bad = E.nan_mismatch | ((E["abs"] > 1e-9) & (E["rel"] > 1e-6))
    E["bad"] = bad
    agg = E.groupby(["era", "bar", "feat"]).agg(n=("abs", "size"), minutes=("t", "nunique"), max_abs=("abs", "max"),
                                                 max_rel=("rel", "max"), nan_mismatch=("nan_mismatch", "sum"),
                                                 over_tol=("bad", "sum")).reset_index()
    ok = not bool(bad.any())
    log(f"EXACTNESS {'PASSED' if ok else 'FAILED'}: {len(E):,} values at "
        f"{E.groupby(['era', 'bar']).t.nunique().to_dict()} candidates (era, bar); largest absolute {E['abs'].max():.2e}, "
        f"largest relative {E['rel'].max():.2e}; over tolerance {int(bad.sum())}")
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
    ok, S0book, B0 = run_s0()
    if not ok:
        log("STOP: the gate failed; no other scenario is computed")
        return
    if JOB == "export":
        export()
        log("done")
        return
    del B0
    gc.collect()
    plan = PLAN[(BASE, JOB)]
    need = {}
    for name, era in plan:
        s_late, quiet = cut.SCEN[name]
        for s in ({s_late, 0} if quiet else {s_late}):
            need.setdefault(s, set()).add(era)
    Dv = load_prints()
    BR = Bars(Dv, need)
    N = int(OPT["exact"])
    ok, agg = exact(BR, need, N)
    agg.to_csv(os.path.join(OUT, "exact.csv"), index=False)
    if not ok:
        log("STOP: the exactness check failed; no other scenario is computed")
        return
    # decisions at the candidate minutes (measure 1; the placebo first)
    Dc, CH = [], {}
    for name, era in plan:
        ch, rows = scenario(BR, name, era)
        CH[(name, era)] = ch
        Dc.append(rows)
    Dc = pd.concat(Dc, ignore_index=True)
    Dc.to_parquet(os.path.join(OUT, "decisions_rows.parquet"), index=False, compression="zstd")
    T1 = decisions_table(Dc)
    T1.to_csv(os.path.join(OUT, "decisions.csv"), index=False)
    pl = T1[(T1.scen == "M0") & (T1.group == "five")]
    if len(pl):
        log("PLACEBO (the five under M0): " + "; ".join(
            f"{r.era}: {r.changed_decisions} of {r.candidates} candidates change arming ({100 * r.changed_share:.2f}%)"
            for r in pl.itertuples()))
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(T1.round(4).to_string(index=False), flush=True)
    # pricing, one scenario-era at a time
    for name, era in plan:
        B = build(f"{name}_{era}", CH[(name, era)])
        price(f"{name}_{era}", B, (era,), S0book)
        del B
        gc.collect()
    log("done")


if __name__ == "__main__":
    main()
