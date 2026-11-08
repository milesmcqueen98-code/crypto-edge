#!/usr/bin/env python3
"""Ladder v6 (sizing): diagnostics, oracle, family runs and the variants log (selection era only before the freeze).
usage: python scripts/ladder_v6s/rounds.py diag | round1
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ssim  # noqa: E402
from ssim import CONFIGS, OUT, RL, fsim, lsim  # noqa: E402

VAR = os.path.join(OUT, "variants.csv")
FAMILIES = ("kelly", "invvar", "edge", "breadth")
_INC = {}


def incumbent(cfg, era):
    if (cfg, era) not in _INC:
        _INC[(cfg, era)] = lsim.incumbent_daily(cfg, era)
    return _INC[(cfg, era)]


def log(row):
    row = dict(time_utc=pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), **row)
    df = pd.DataFrame([row])
    if os.path.exists(VAR):
        old = pd.read_csv(VAR)
        if [c for c in df.columns if c not in old.columns]:
            pd.concat([old, df], ignore_index=True).to_csv(VAR, index=False)
            return
        df = df.reindex(columns=old.columns)
    df.to_csv(VAR, mode="a", header=not os.path.exists(VAR), index=False)


def line(name, s):
    return (f"{name:34s} Sharpe-path t {s['t_vm']:+5.2f} (best 5 out {s['t_vm_ex5']:+5.2f})  return-path t {s['t']:+5.2f} "
            f"(best 5 out {s['t_ex5']:+5.2f})  dSharpe {s['d_sharpe']:+.3f}  dret {100 * s['d_ret']:+5.2f}pp  "
            f"top-5 share {s['top5_share']:.2f}")


def run(name, mfac, rnd, cfg="S_0.5", era="sel", note="", **meta):
    cand = ssim.daily(cfg, era, mfac)
    s = ssim.score(incumbent(cfg, era), cand, cfg, era)
    X = ssim.inputs(cfg, era)
    A = ssim.base(cfg, era)
    pm = mfac[A["p_t"], A["p_c"]]
    log(dict(round=rnd, name=name, cfg=cfg, era=era, **meta, **{f"sel_{k}": v for k, v in s.items()},
             par_mult_mean=float(pm.mean()), par_mult_p10=float(np.quantile(pm, 0.1)),
             par_mult_p90=float(np.quantile(pm, 0.9)), note=note))
    return s, cand


# ------------------------------------------------------------------------------------------------ diagnostics
def signal_frame(cfg="S_0.5", era="sel", bound="instant"):
    """Per research parent signal of the incumbent's frame: dollars filled and net P&L over its rungs (print costs)."""
    out = lsim.load_books(cfg, era)[bound]
    Q, info = out
    kw = CONFIGS[cfg]
    tag, (lo, hi) = fsim.ERAS[era]
    tk = info["taker_bp"] / 1e4
    hs = fsim.HS_BP * kw["cost_mult"] / 1e4
    y = fsim.IMPACT_Y * kw["cost_mult"]
    sc = fsim.today_scale(RL.inputs(tag)["P"], lo, hi) if kw["today"] else {}
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    rem = np.maximum((Q.fill - Q.tp_fill).to_numpy(), 0.0)
    fsc = Q.coin.map(sc).fillna(1.0).to_numpy() if sc else np.ones(len(Q))
    pc = lsim.pcost()
    net = (Q.pnl_tp - Q.entry_cost).to_numpy().copy()
    for i in np.nonzero(rem > 0)[0]:
        R = rem[i]
        fb = 1e4 * fsim.IMPACT_Y * vol_d[i] * np.sqrt(R / adv[i])
        ci = pc.cost(Q.coin.iat[i], pd.Timestamp(Q.fill_t.iat[i]), 0, R / fsc[i], fb_bp=fb)
        if not np.isfinite(ci):
            ci = hs + y * vol_d[i] * np.sqrt(R / adv[i])
        net[i] += R * (Q.g60.iat[i] / 1e4 - tk - ci)
    Q = Q.assign(net=net)
    S = Q[Q.fill > 0].groupby(["ts", "coin"]).agg(fill=("fill", "sum"), net=("net", "sum"),
                                                   vol_d=("vol_d", "first")).reset_index()
    S["r_bp"] = 1e4 * S.net / S.fill
    return S


def diag(cfg="S_0.5", era="sel"):
    S = signal_frame(cfg, era)
    X = ssim.inputs(cfg, era)
    I = RL.inputs(fsim.ERAS[era][0])
    cj = {c: j for j, c in enumerate(I["coins"])}
    ip = I["pidx"].get_indexer(S.ts)
    S["mu"] = [I["M"][i, cj[c]] if i >= 0 else np.nan for i, c in zip(ip, S.coin)]
    vt = ssim.vol_d_table(fsim.ERAS[era][0], sorted(S.coin.unique()))
    S["sig"] = [vt.at[d, c] for d, c in zip(S.ts.dt.floor("D"), S.coin)]
    tmin = X["idx"][0]
    pos = ((S.ts - tmin) // pd.Timedelta(minutes=1)).to_numpy()
    S["breadth"] = X["breadth"][pos]
    S["kelly"] = S.mu / S.sig ** 2
    S["invvar"] = 1 / S.sig ** 2
    S["edge"] = S.mu
    S["breadth_f"] = 1 / np.sqrt(np.maximum(S.breadth, 1))
    lines = [f"{cfg} {era}: {len(S)} funded signals, ${S.fill.sum() / 1e6:.1f}M; vol_d check vs frame: "
             f"max |diff| {np.nanmax(np.abs(S.sig - S.vol_d)):.2e}"]
    for col in ("mu", "sig", "kelly", "breadth"):
        q = pd.qcut(S[col].rank(method="first"), 5, labels=False)
        g = S.groupby(q)
        rows = []
        for k, gg in g:
            w = gg.fill
            m = np.average(gg.r_bp, weights=w)
            sd = np.sqrt(np.average((gg.r_bp - m) ** 2, weights=w))
            rows.append(f"Q{k + 1}: {gg[col].median():9.4g} | r {m:+6.1f} bp, sd {sd:5.0f}, mean/var x1e4 "
                        f"{1e4 * m / sd ** 2:+6.2f}, n {len(gg)}")
        lines.append(f"by {col} quintile (dollar-weighted net per dollar of the signal):")
        lines += ["   " + r for r in rows]
    for col in ("mu", "sig", "kelly", "breadth"):
        lines.append(f"Spearman({col}, r) = {S[col].corr(S.r_bp, method='spearman'):+.3f}; "
                     f"Spearman({col}, |r - mean|) = {S[col].corr((S.r_bp - S.r_bp.mean()).abs(), method='spearman'):+.3f}")
    # day concentration of the incumbent
    inc = incumbent(cfg, era)
    tot = inc.sum()
    lines.append(f"incumbent: best 5 days carry {100 * inc.nlargest(5).sum() / tot:.0f}% of the era's P&L; "
                 f"worst 5 days {100 * inc.nsmallest(5).sum() / tot:.0f}%")
    open(os.path.join(OUT, f"diag_{era}.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return S


# ------------------------------------------------------------------------------------------------ round 1
def oracle_mult(cfg, era, capped=True, up=2.0, down=0.5):
    """Hindsight: each research parent's whole ladder x up if the incumbent's realized net on it is > 0, else x down."""
    A = ssim.base(cfg, era)
    X = ssim.inputs(cfg, era)
    S = signal_frame(cfg, era)
    win = {(pd.Timestamp(t), c): (r > 0) for t, c, r in zip(S.ts, S.coin, S.net)}
    m = np.ones_like(X["M"])
    par = A["par"]
    for q, (t, c) in enumerate(zip(par.ts, par.coin)):
        w = win.get((pd.Timestamp(t), c))
        if w is None:
            continue
        m[A["p_t"][q], A["p_c"][q]] = up if w else down
    if capped:
        m = np.minimum(m, X["room"])
    return m


def round1():
    t0 = time.time()
    lines = []
    for capped in (True, False):
        s, _ = run(f"oracle x2/x0.5 {'capped' if capped else 'uncapped'}", oracle_mult("S_0.5", "sel", capped), 1,
                   family="oracle", lam=np.nan, capped=capped, note="hindsight bound in [0.5, 2]")
        lines.append(line(f"oracle {'capped' if capped else 'uncapped'}", s) + f" ({time.time() - t0:.0f}s)")
        print(lines[-1], flush=True)
    X = ssim.inputs("S_0.5", "sel")
    for fam in ssim_families():
        for lam in (0.25, 0.5, 1.0):
            for capped in (True, False):
                m = ssim.rule_mult(X, fam, lam, capped=capped)
                s, _ = run(f"{fam} lam{lam:g} {'capped' if capped else 'uncapped'}", m, 1, family=fam, lam=lam,
                           capped=capped)
                lines.append(line(f"{fam} lam{lam:g} {'capped' if capped else 'uncapped'}", s))
                print(lines[-1], flush=True)
    open(os.path.join(OUT, "round1.txt"), "w").write("\n".join(lines) + "\n")


def ssim_families():
    return FAMILIES


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "diag":
        diag()
    elif cmd == "round1":
        round1()


# ------------------------------------------------------------------------------------------------ round 2 (Z5)
def signals_with_mu(cfg="S_0.5", era="sel"):
    S = signal_frame(cfg, era)
    I = RL.inputs(fsim.ERAS[era][0])
    cj = {c: j for j, c in enumerate(I["coins"])}
    ip = I["pidx"].get_indexer(S.ts)
    S["mu"] = [float(I["M"][i, cj[c]]) if i >= 0 else np.nan for i, c in zip(ip, S.coin)]
    return S[np.isfinite(S.mu)].reset_index(drop=True)


def z5_coefs(S):
    A = np.column_stack([np.ones(len(S)), S.mu.to_numpy()])
    ab = np.linalg.lstsq(A, S.r_bp.to_numpy(), rcond=None)[0]
    res = np.abs(S.r_bp.to_numpy() - A @ ab)
    cd = np.linalg.lstsq(A, res, rcond=None)[0]
    return ab, cd


def z5_f(mu, ab, cd, kind="kelly", floor=50.0):
    rhat = ab[0] + ab[1] * mu
    s = np.maximum(cd[0] + cd[1] * mu, floor)
    if kind == "kelly":
        return np.maximum(rhat, 0.0) / s ** 2
    return 1.0 / s ** 2


def z5_mult(cfg, era, lam, mode, kind="kelly", capped=True, train=None, lo=0.5, hi=2.0, min_train=150,
            window_days=90, min_n=30):
    """Monthly coefficients (in-sample: one fit on `train`; walk-forward: all signals of `train` that exited before
    the month); f per minute from mu; fbar = trailing 90-day median of f over research parents (same coefficients)."""
    X = ssim.inputs(cfg, era)
    T, NC = X["M"].shape
    m = np.ones((T, NC))
    months = X["days"].to_period("M")
    mo_codes = np.asarray(months.astype(str))
    pts = pd.to_datetime(X["par_ts"])
    coef_log = {}
    for mo in sorted(set(mo_codes)):
        start = pd.Period(mo, "M").start_time
        if mode == "insample":
            tr = train
        else:
            tr = train[train.ts + pd.Timedelta(minutes=121) <= start]
        if len(tr) < min_train:
            continue
        ab, cd = z5_coefs(tr)
        coef_log[mo] = (ab.round(4).tolist(), cd.round(4).tolist(), len(tr))
        rows = np.nonzero(mo_codes == mo)[0]
        f = z5_f(X["M"][rows], ab, cd, kind)
        fp = z5_f(X["par_M"], ab, cd, kind)
        okp = np.isfinite(fp) & (fp > 0)
        s = pd.Series(fp[okp], index=pts[okp]).sort_index()
        tv, vals = s.index.to_numpy(), s.to_numpy()
        dsub = X["di"][rows]
        fb_day = {}
        for d in np.unique(dsub):
            day = X["du"][d]
            a_ = np.searchsorted(tv, (day - pd.Timedelta(days=window_days)).to_datetime64(), "left")
            b_ = np.searchsorted(tv, day.to_datetime64(), "left")
            fb_day[d] = np.median(vals[a_:b_]) if b_ - a_ >= min_n else np.nan
        fb = np.array([fb_day[d] for d in dsub])[:, None]
        with np.errstate(invalid="ignore", divide="ignore"):
            mm = np.clip((f / fb) ** lam, lo, hi)
        mm = np.where(np.isfinite(mm), mm, 1.0)
        m[rows] = mm
    if capped:
        m = np.minimum(m, X["room"])
    return m, coef_log


def round2():
    S = signals_with_mu("S_0.5", "sel")
    lines = []
    for kind in ("kelly", "invdisp"):
        for mode in ("insample", "wf"):
            for lam in (0.5, 1.0):
                for capped in ((True, False) if kind == "kelly" else (True,)):
                    m, cl = z5_mult("S_0.5", "sel", lam, mode, kind, capped, train=S)
                    name = f"Z5 {kind} {mode} lam{lam:g} {'capped' if capped else 'uncapped'}"
                    s, _ = run(name, m, 2, family=f"z5_{kind}", lam=lam, capped=capped, fit=mode,
                               note=f"coefs first/last month: {list(cl.items())[:1]} {list(cl.items())[-1:]}")
                    lines.append(line(name, s))
                    print(lines[-1], flush=True)
    ab, cd = z5_coefs(S)
    lines.append(f"in-sample coefficients: mean a, b = {ab.round(3).tolist()}, dispersion c, d = {cd.round(3).tolist()}"
                 f" over {len(S)} signals")
    print(lines[-1])
    open(os.path.join(OUT, "round2.txt"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__" and sys.argv[1] == "round2":
    round2()
