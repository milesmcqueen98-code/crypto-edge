#!/usr/bin/env python3
"""Ladder v5, C2 and C6: size the spot ladder by the AI's margin or by BTC stress (reports/ladder_v5/specs/sizing.md).

All three candidates use hsim's size_fn hook, m = size_fn(margin, i), margin = prediction - the quarter's threshold,
i = the panel's minute index. m scales the whole ladder of a signal: the 4-sigma hold every minute (that minute's m)
and the 6/8-sigma rungs (m at the parent's fill minute). It multiplies the capped size (0.2% of ADV, 25% of capital).
Everything else is the incumbent (hsim engine policy on fsim).

  C2a_margin_terciles (path "return"): cutoffs = the 1/3 and 2/3 quantiles (numpy's default linear interpolation) of
      the margins (pred - thr) of all parent fills in the era's trade list (reports/wick1m/trades_<main|early>.parquet,
      every row, not only the 'bot' rows) whose ts is before the start of the current calendar quarter; fewer than 60
      such fills: x1.0. Recomputed each quarter. x0.5 below the lower cutoff, x1.0 between, x1.5 at or above the upper.
  C2b_drop_bottom (path "sharpe"): same cutoffs; x0 (no bid) below the lower cutoff, x1.0 otherwise.
  C6_stress (path "return"): x1.5 when BTC stress >= 2.0, else x1.0. Stress at minute t = edge/wick.py's btc_vol_ratio
      placed on row t (known at t-1): 60-minute std of BTC's 1-minute log returns / its 4,320-minute std (at least
      1,440 minutes), from the lab's closes (wick_sim.load_ohlc: Coinbase spot, ffill <= 30 minutes) of
      data/minute/BTC.parquet (main) and data/minute_early/BTC.parquet (early), aligned to the panel's minutes.
      A minute without a stress value (NaN) gets x1.0.

usage: python scripts/ladder_v5/cand_sizing.py check [era] [cfg]  off switch (size_fn = 1.0) vs the cached incumbent
       python scripts/ladder_v5/cand_sizing.py inputs               cutoffs, bucket and stress shares (no P&L)
       python scripts/ladder_v5/cand_sizing.py run                  inputs, off switch in every era and configuration,
                                                                    the three gated trials in order, then diagnostics
       python scripts/ladder_v5/cand_sizing.py diag                 diagnostics only (no trial is logged)
Outputs: reports/ladder_v5/trials.csv and trials/<name>.json (gates.run), reports/ladder_v5/sizing/*.
"""
import hashlib
import os
import shutil
import sys
import time
import traceback

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gates  # noqa: E402  (first: fsim puts scripts/hunt, which has its own gates.py, ahead of this folder)
import fsim  # noqa: E402
import hsim  # noqa: E402
import sim  # noqa: E402
import wick_sim as ws  # noqa: E402
from edge import wick  # noqa: E402

for _m in (gates, fsim, hsim):
    assert os.path.dirname(os.path.abspath(_m.__file__)) == HERE, _m.__file__

OUTD = os.path.join(fsim.OUT, "sizing")
TRIALS = (("C2a_margin_terciles", "c2a", "return"), ("C2b_drop_bottom", "c2b", "sharpe"), ("C6_stress", "c6", "return"))
MIN_FILLS = 60
STRESS_AT = 2.0
DIAG_CFG = "S_0.5"
_C2, _ST, _SF, STASH = {}, {}, {}, {}


# ------------------------------------------------------------------------------------------------ frozen dataset
def ensure_frozen():
    """fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl (gitignored; absent in a fresh checkout, where fsim would
    rebuild it). Put the frozen copies there (reports/ladder_v5/frozen, sha256 in SHA256SUMS) so every run uses the
    frozen dataset byte for byte. No frozen file is changed."""
    sums = {}
    for line in open(os.path.join(fsim.OUT, "frozen", "SHA256SUMS")):
        h, p = line.split()
        sums[p] = h

    def sha(p):
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    for tag in ("main", "early"):
        src = os.path.join(fsim.OUT, "frozen", f"pre_hunt_{tag}.pkl")
        dst = os.path.join(fsim.ROOT, "reports", "wick1m", f"pre_hunt_{tag}.pkl")
        want = sums[f"frozen/pre_hunt_{tag}.pkl"]
        if sha(src) != want:
            raise RuntimeError(f"frozen {src} does not match SHA256SUMS")
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
        if sha(dst) != want:
            raise RuntimeError(f"{dst} exists and differs from the frozen dataset")


# ------------------------------------------------------------------------------------------------ the rules' inputs
def qcode(ts):
    ts = pd.DatetimeIndex(ts)
    return ts.year.to_numpy() * 4 + (ts.month.to_numpy() - 1) // 3


def c2_cutoffs(tag, idx):
    """Per calendar quarter of the panel: the 1/3 and 2/3 quantiles of the margins of all earlier parent fills."""
    T = pd.read_parquet(os.path.join(fsim.ROOT, "reports", "wick1m", f"trades_{tag}.parquet"))
    mg = (T.pred - T.thr).to_numpy(np.float64)
    ts = T.ts.to_numpy()
    rows = []
    for q in pd.PeriodIndex(idx, freq="Q").unique():
        start = q.start_time
        prior = mg[ts < np.datetime64(start)]
        n = int(len(prior))
        lo, hi = (np.nan, np.nan) if n < MIN_FILLS else (float(v) for v in np.quantile(prior, [1 / 3, 2 / 3]))
        rows.append(dict(tag=tag, quarter=str(q), start=start, n_prior_fills=n, lo=lo, hi=hi,
                         code=int(q.year * 4 + q.quarter - 1)))
    return pd.DataFrame(rows)


def c2_arrays(tag, idx):
    """(cutoff table, LO, HI as Python lists by panel minute index; NaN = fewer than 60 earlier fills)."""
    if tag not in _C2:
        cut = c2_cutoffs(tag, idx)
        qc = qcode(idx)
        LO, HI = np.full(len(idx), np.nan), np.full(len(idx), np.nan)
        for r in cut.itertuples():
            m = qc == r.code
            LO[m], HI[m] = r.lo, r.hi
        _C2[tag] = (cut, LO, HI)
    return _C2[tag]


def btc_stress(tag, idx):
    """edge/wick.py's btc_vol_ratio on row t (value at t-1), from the lab's BTC closes, at the panel's minutes."""
    if tag not in _ST:
        start, end, src = sim.PERIODS[tag]
        gidx, D = ws.load_ohlc(src=src, coins=["BTC"], start=start, end=end)
        lpb = np.log(D["BTC"]["cf"])
        r1b = np.diff(lpb, prepend=np.nan)
        btc_vr = (pd.Series(r1b).rolling(60).std() / pd.Series(r1b).rolling(wick.W, min_periods=wick.MINP).std()).to_numpy()
        s = wick.shift(btc_vr, 1)
        pidx = pd.DatetimeIndex(idx)
        i0 = int(gidx.searchsorted(pidx[0]))
        g = gidx[i0:i0 + len(pidx)]
        if len(g) != len(pidx) or not np.array_equal(g.as_unit("s").asi8, pidx.as_unit("s").asi8):
            raise RuntimeError("BTC minute grid does not align with the panel's minutes")
        _ST[tag] = s[i0:i0 + len(pidx)].copy()
    return _ST[tag]


def build(kind, tag, idx):
    if kind == "off":
        return lambda margin, i: 1.0
    if kind in ("c2a", "c2b"):
        _, LO_, HI_ = c2_arrays(tag, idx)
        LO, HI = LO_.tolist(), HI_.tolist()
        if kind == "c2a":
            def f(margin, i):
                lo = LO[i]
                if lo != lo:                    # fewer than 60 earlier fills
                    return 1.0
                if margin < lo:
                    return 0.5
                if margin >= HI[i]:
                    return 1.5
                return 1.0
        else:
            def f(margin, i):
                lo = LO[i]
                if lo != lo:
                    return 1.0
                return 0.0 if margin < lo else 1.0
        return f
    if kind == "c6":
        ST = btc_stress(tag, idx).tolist()

        def f(margin, i):
            return 1.5 if ST[i] >= STRESS_AT else 1.0     # NaN compares False: x1.0
        return f
    raise ValueError(kind)


def size_fn_for(kind, tag, idx):
    if (kind, tag) not in _SF:
        _SF[(kind, tag)] = build(kind, tag, idx)
    return _SF[(kind, tag)]


def cfg_name(theta, C, today, cost_mult):
    for k, v in gates.CONFIGS.items():
        if (v["theta"], v["C"], v["today"], v["cost_mult"]) == (theta, C, today, cost_mult):
            return k
    return None


LEAN = ["ts", "coin", "k", "f_off", "fill_t", "fill", "tp_fill", "pnl", "gross", "fee_maker", "fee_taker", "cost_hs",
        "cost_imp", "want"]


def make(kind):
    def book_fn(P, era, pan=None, adv_=None, theta=0.5, C=250e3, today=False, cost_mult=1.0):
        tag = fsim.ERAS[era][0]
        if pan is None:
            pan = gates.data(tag)[1]
        f = size_fn_for(kind, tag, pan[0])
        d, out = hsim.book(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, pan=pan, adv=adv_, size_fn=f)
        cfg = cfg_name(theta, C, today, cost_mult)
        if cfg == DIAG_CFG and kind != "off":
            STASH[(kind, era)] = dict(d=d, **{b: dict(Q=out[b][0][LEAN].copy(), st=dict(out[b][3]), info=out[b][2])
                                             for b in ("minute", "instant")})
        return d
    return book_fn


# ------------------------------------------------------------------------------------------------ off switch
def offswitch(pairs):
    worst, lines = 0.0, []
    for era, cfg in pairs:
        tag = fsim.ERAS[era][0]
        P, pan = gates.data(tag)
        d = make("off")(P, era, pan=pan, adv_=gates.adv(tag, era), **gates.CONFIGS[cfg])
        inc = gates.incumbent_cached(era, cfg)
        same_idx = bool(d.index.equals(inc.index))
        diff = float(np.abs(d.reindex(inc.index, fill_value=0.0) - inc).max())
        worst = max(worst, diff)
        lines.append(f"  {era:5s} {cfg:8s} max |daily diff| = {diff:.3e}  (same day index: {same_idx}, days {len(inc)})")
    return worst, lines


# ------------------------------------------------------------------------------------------------ inputs (no P&L)
def era_slice(era, idx):
    lo, hi = fsim.ERAS[era][1]
    t0, t1 = pd.Timestamp(lo), pd.Timestamp(hi) + pd.Timedelta(days=1)
    return int(idx.searchsorted(t0)), int(idx.searchsorted(t1))


def parent_buckets(era):
    """Every parent fill of the era (frozen dataset, = the trade list's rows in the era): margin at the fill minute as
    hsim computes it (float32 panel), its C2 bucket and its BTC stress."""
    tag, (lo, hi) = fsim.ERAS[era]
    P, pan = gates.data(tag)
    idx, M, thr, coins = pan
    cut, LO, HI = c2_arrays(tag, idx)
    ST = btc_stress(tag, idx)
    W = fsim.window(P, lo, hi)
    par = W[(W.k == 4.0) & W.filled][["ts", "coin"]].copy()
    cj = {c: j for j, c in enumerate(coins)}
    i = idx.searchsorted(par.ts.to_numpy())
    j = par.coin.map(cj).to_numpy().astype(int)
    mg = (M[i, j] - thr[i]).astype(np.float64)
    lo_, hi_ = LO[i], HI[i]
    b2 = np.where(np.isnan(lo_), "x1_lt60", np.where(mg < lo_, "bottom", np.where(mg >= hi_, "top", "middle")))
    par["i"], par["margin"], par["c2"], par["stress"] = i, mg, b2, ST[i]
    par["c6"] = np.where(ST[i] >= STRESS_AT, "stress", "calm")
    # the same margins from the trade list (float64): bucket agreement
    T = pd.read_parquet(os.path.join(fsim.ROOT, "reports", "wick1m", f"trades_{tag}.parquet"))[["ts", "coin", "pred", "thr"]]
    m = par.merge(T, on=["ts", "coin"], how="left")
    mt = (m.pred - m.thr).to_numpy()
    bt = np.where(np.isnan(lo_), "x1_lt60", np.where(mt < lo_, "bottom", np.where(mt >= hi_, "top", "middle")))
    par["margin_tradelist"], par["c2_tradelist"] = mt, bt
    return par


def inputs():
    os.makedirs(OUTD, exist_ok=True)
    lines, cuts = [], []
    for tag in ("main", "early"):
        P, pan = gates.data(tag)
        idx, M, thr, coins = pan
        cut, LO, HI = c2_arrays(tag, idx)
        ST = btc_stress(tag, idx)
        cuts.append(cut.drop(columns="code"))
        lines.append(f"[{tag}] BTC stress: {np.isnan(ST).sum()} of {len(ST)} panel minutes have no value (x1.0)")
    cut = pd.concat(cuts, ignore_index=True)
    cut.to_csv(os.path.join(OUTD, "cutoffs.csv"), index=False)
    lines.append("C2 cutoffs per quarter (margin = pred - thr; NaN = fewer than 60 earlier fills, x1.0):")
    lines.append(cut.drop(columns="start").to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    rows = []
    for era in fsim.ERAS:
        tag = fsim.ERAS[era][0]
        P, pan = gates.data(tag)
        idx, M, thr, coins = pan
        cut, LO, HI = c2_arrays(tag, idx)
        ST = btc_stress(tag, idx)
        a, b = era_slice(era, idx)
        mg = M[a:b] - thr[a:b, None]
        armed = mg > 0
        lo_, hi_ = LO[a:b, None], HI[a:b, None]
        nan = np.isnan(lo_) & np.ones_like(armed)
        n_arm = int(armed.sum())
        sh = lambda z: float((z & armed).sum()) / n_arm if n_arm else np.nan  # noqa: E731
        st_ = ST[a:b, None]
        par = parent_buckets(era)
        r = dict(era=era, minutes=b - a, armed_coin_minutes=n_arm,
                 arm_x1_lt60=sh(nan), arm_bottom=sh(~nan & (mg < lo_)), arm_middle=sh(~nan & (mg >= lo_) & (mg < hi_)),
                 arm_top=sh(~nan & (mg >= hi_)),
                 minutes_stress=float(np.nanmean(ST[a:b] >= STRESS_AT)), minutes_stress_nan=int(np.isnan(ST[a:b]).sum()),
                 arm_stress=sh(np.broadcast_to(st_ >= STRESS_AT, armed.shape)),
                 parents=len(par))
        for k in ("x1_lt60", "bottom", "middle", "top"):
            r[f"par_{k}"] = float((par.c2 == k).mean())
        r["par_stress"] = float((par.c6 == "stress").mean())
        r["par_stress_nan"] = int(np.isnan(par.stress).sum())
        r["par_margin_maxdiff_tradelist"] = float(np.nanmax(np.abs(par.margin - par.margin_tradelist)))
        r["par_bucket_disagree_tradelist"] = int((par.c2 != par.c2_tradelist).sum())
        rows.append(r)
    S = pd.DataFrame(rows)
    S.to_csv(os.path.join(OUTD, "bucket_shares.csv"), index=False)
    lines.append("\nShares by era (arm_* = share of armed coin-minutes; par_* = share of parent fills; stress = BTC "
                 "stress >= 2):")
    lines.append(S.T.to_string(float_format=lambda v: f"{v:.4f}"))
    txt = "\n".join(lines)
    open(os.path.join(OUTD, "inputs.txt"), "w").write(txt + "\n")
    print(txt, flush=True)
    return S


# ------------------------------------------------------------------------------------------------ diagnostics
def _agg(Q, keys, buck=None):
    Q = Q.copy()
    Q["n"] = (Q.fill > 0).astype(float)
    if buck is not None:
        Q = Q.merge(buck, on=["ts", "coin"], how="left")
    return Q.groupby(keys)[["n", "fill", "pnl"]].sum()


def _blend(a, b, s):
    a, b = a.align(b, fill_value=0.0)
    return a + s * (b - a)


def diagnostics():
    """Decomposition of the logged runs at S*, theta 0.5 (not trials): hsim's cash counters, rungs, size buckets,
    the largest daily differences. Uses the gated runs' outputs when present (same process), else recomputes."""
    os.makedirs(OUTD, exist_ok=True)
    kw = gates.CONFIGS[DIAG_CFG]
    st_rows, rung_rows, b_rows, day_rows, lines = [], [], [], [], []
    for era in fsim.ERAS:
        tag = fsim.ERAS[era][0]
        P, pan = gates.data(tag)
        adv = gates.adv(tag, era)
        s = fsim.lat_share(era, kw["theta"])
        par = parent_buckets(era)
        buck = par[["ts", "coin", "c2", "c6"]]
        res = {}
        d, out = hsim.book(P, era, pan=pan, adv=adv, **kw)
        inc_c = gates.incumbent_cached(era, DIAG_CFG)
        lines.append(f"{era}: incumbent recomputed vs cache, max |daily diff| = "
                     f"{float(np.abs(d.reindex(inc_c.index, fill_value=0.0) - inc_c).max()):.3e}")
        res["inc"] = dict(d=d, **{b: dict(Q=out[b][0][LEAN].copy(), st=dict(out[b][3]), info=out[b][2])
                                  for b in ("minute", "instant")})
        for name, kind, path in TRIALS:
            if (kind, era) not in STASH:
                make(kind)(P, era, pan=pan, adv_=adv, **kw)
            res[kind] = STASH[(kind, era)]
        dropped = int((par.c2 == "bottom").sum())
        for kind, r in res.items():
            for b in ("minute", "instant"):
                row = dict(era=era, kind=kind, bound=b, **r[b]["st"], v30=r[b]["info"]["v30"],
                           maker_bp=r[b]["info"]["maker_bp"], taker_bp=r[b]["info"]["taker_bp"],
                           bought=float(r[b]["Q"].fill.sum()), pnl=float(r[b]["Q"].pnl.sum()))
                row["dropped_by_rule"] = dropped if kind == "c2b" else 0
                st_rows.append(row)
            g = _blend(_agg(r["minute"]["Q"], ["k"]), _agg(r["instant"]["Q"], ["k"]), s)
            for k, v in g.iterrows():
                rung_rows.append(dict(era=era, kind=kind, k=k, fills=v.n, bought=v.fill, pnl=v.pnl,
                                      bp_per_usd=1e4 * v.pnl / v.fill if v.fill > 0 else np.nan))
            for scheme in ("c2", "c6"):
                g = _blend(_agg(r["minute"]["Q"], [scheme, "k"], buck), _agg(r["instant"]["Q"], [scheme, "k"], buck), s)
                for (bk, k), v in g.iterrows():
                    b_rows.append(dict(era=era, kind=kind, scheme=scheme, bucket=bk, k=k, parents=int((par[scheme] == bk).sum()),
                                       fills=v.n, bought=v.fill, pnl=v.pnl,
                                       bp_per_usd=1e4 * v.pnl / v.fill if v.fill > 0 else np.nan))
        # largest daily differences per candidate (the day's parents, funded parents and deeper fills, instant bound)
        pday = par.groupby(par.ts.dt.floor("D")).size()

        def per_day(Q):
            q = Q[Q.fill > 0]
            dd = q.ts.dt.floor("D")
            return (q[q.k == 4.0].groupby(dd[q.k == 4.0]).size(), q[q.k > 4.0].groupby(dd[q.k > 4.0]).size(),
                    q.groupby(dd).fill.sum())
        pi, di, bi = per_day(res["inc"]["instant"]["Q"])
        for name, kind, path in TRIALS:
            diff = (res[kind]["d"] - res["inc"]["d"])
            pc, dc, bc = per_day(res[kind]["instant"]["Q"])
            for day in diff.abs().sort_values(ascending=False).index[:5]:
                day_rows.append(dict(era=era, trial=name, day=day.date(), diff_bp=1e4 * diff[day],
                                     inc_bp=1e4 * res["inc"]["d"][day], cand_bp=1e4 * res[kind]["d"][day],
                                     parents=int(pday.get(day, 0)), inc_parents_funded=int(pi.get(day, 0)),
                                     cand_parents_funded=int(pc.get(day, 0)), inc_deep_fills=int(di.get(day, 0)),
                                     cand_deep_fills=int(dc.get(day, 0)), inc_bought=float(bi.get(day, 0.0)),
                                     cand_bought=float(bc.get(day, 0.0))))
            # share of the era's total difference from its 5 / 10 largest days
            tot = diff.sum()
            top = diff.loc[diff.abs().sort_values(ascending=False).index[:10]]
            lines.append(f"{era} {name}: total diff {1e4 * tot:+.1f} bp of capital over the era; 5 largest days "
                         f"{1e4 * top.iloc[:5].sum():+.1f} bp, 10 largest {1e4 * top.sum():+.1f} bp; "
                         f"days up / down {(diff > 1e-12).sum()} / {(diff < -1e-12).sum()}")
    pd.DataFrame(st_rows).to_csv(os.path.join(OUTD, "diag_cash.csv"), index=False)
    pd.DataFrame(rung_rows).to_csv(os.path.join(OUTD, "diag_rung.csv"), index=False)
    pd.DataFrame(b_rows).to_csv(os.path.join(OUTD, "diag_bucket.csv"), index=False)
    pd.DataFrame(day_rows).to_csv(os.path.join(OUTD, "diag_days.csv"), index=False)
    open(os.path.join(OUTD, "diag.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


# ------------------------------------------------------------------------------------------------ main
def main():
    ensure_frozen()
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "check":
        era = sys.argv[2] if len(sys.argv) > 2 else "chk"
        cfg = sys.argv[3] if len(sys.argv) > 3 else "S_0.5"
        worst, lines = offswitch([(era, cfg)])
        print("off switch (size_fn = 1.0) vs cached incumbent:\n" + "\n".join(lines), flush=True)
        return
    if mode == "inputs":
        inputs()
        return
    if mode == "diag":
        diagnostics()
        return
    if mode != "run":
        raise SystemExit(__doc__)
    t0 = time.time()
    log = []
    inputs()
    worst, lines = offswitch([(e, c) for c in gates.CONFIGS for e in fsim.ERAS])
    log.append(f"off switch (size_fn = 1.0) vs cached incumbent, every era and configuration ({time.time() - t0:.0f}s):")
    log += lines
    log.append(f"  worst {worst:.3e}")
    print("\n".join(log), flush=True)
    if not worst <= 1e-12:
        open(os.path.join(OUTD, "run_summary.txt"), "w").write("\n".join(log) + "\nABORTED before any trial\n")
        raise SystemExit("off switch does not reproduce the incumbent: no trial run")
    for name, kind, path in TRIALS:
        out = gates.run(name, make(kind), path=path)
        log.append(gates.summary(out) + f"\n  ({out['seconds']}s)")
        print(log[-1], flush=True)
        open(os.path.join(OUTD, "run_summary.txt"), "w").write("\n".join(log) + "\n")
    try:
        diagnostics()
    except Exception:                                   # the trials are logged; never lose them to a diagnostic
        traceback.print_exc()
        log.append("diagnostics failed:\n" + traceback.format_exc())
    log.append(f"total {time.time() - t0:.0f}s")
    open(os.path.join(OUTD, "run_summary.txt"), "w").write("\n".join(log) + "\n")


if __name__ == "__main__":
    main()
