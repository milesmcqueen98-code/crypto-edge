#!/usr/bin/env python3
"""Red team 3: independent re-derivation of C4_usdc (ladder v5; reports/ladder_v5_prereg.md, row C4).

Written without reading the builder's code or report. Uses only the frozen pieces: hsim.book (the incumbent with the
live bot's cash rule, taken as given), hsim.run (its per-minute trace, for scenario B), the panel, gates.CONFIGS and
fsim.ERAS, edge.book.rf_daily (the T-bill table) and the frozen Bitstamp USDC/USD candles. Everything C4 adds is
computed here: open positions by day, the reward, the USDC/USD mark, the holds of resting bids outside hsim's active
windows, the statistics (own Newey-West t, own return and Sharpe).

Candidate daily return on capital C (scenario A, the trial):
    cand_A(t) = inc(t) + (r(t) + m(t)) * (1 - pos(t) / C)
    r(t)  = max(0, T-bill(t) - 0.5%) / 365, x 0.5 when cost_mult = 2 (S* and $1M), x 1 in base
    m(t)  = Bitstamp usdcusd daily close(t) / close(t-1) - 1 (frozen file, daily candles, then the _ext file)
    pos(t) = time-average over day t of open positions at cost from hsim.book's instant-bound tranche frame:
             each fill's take-profit part from fill_t to tp_t, the rest from fill_t to ex_t
Scenario B (post hoc): the reward only on USDC not on hold for resting bids:
    cand_B(t) = inc(t) + r(t) * free(t) / C + m(t) * (1 - pos(t) / C)
    free = C - positions - 4-sigma holds - deeper-rung holds, minute by minute: hsim.run's own trace in its active
           minutes (parent fill to +60 min), and outside them the engine's 4-sigma allocation recomputed here for every
           minute (all coins free, no positions, budget C; same prediction order, sizes and half-or-nothing rule).

  python scripts/ladder_v5/rt3_c4.py [--configs S_0.5,S_0.25,base_0.5,cap_1M] [--eras sel,chk,early] [--no-holds]
Outputs in reports/ladder_v5/redteam3/.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUTD = os.path.join(ROOT, "reports", "ladder_v5", "redteam3")


def ensure_frozen():
    """fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl (gitignored): copy the frozen pickles there, sha256-checked."""
    sums = dict(reversed(line.split()) for line in open(os.path.join(ROOT, "reports/ladder_v5/frozen/SHA256SUMS")))
    for tag in ("main", "early"):
        src = os.path.join(ROOT, "reports/ladder_v5/frozen", f"pre_hunt_{tag}.pkl")
        dst = os.path.join(ROOT, "reports/wick1m", f"pre_hunt_{tag}.pkl")
        h = hashlib.sha256(open(src, "rb").read()).hexdigest()
        assert h == sums[f"frozen/pre_hunt_{tag}.pkl"], f"frozen pickle {tag} hash mismatch"
        if not os.path.exists(dst) or hashlib.sha256(open(dst, "rb").read()).hexdigest() != h:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)


ensure_frozen()
sys.path.insert(0, HERE)
import gates  # noqa: E402  (before fsim: scripts/hunt has its own gates.py on the path fsim adds)
import fsim  # noqa: E402
import hsim  # noqa: E402

sys.path.insert(0, ROOT)
from edge import book as ebook  # noqa: E402

LOGGED = os.path.join(ROOT, "reports", "ladder_v5", "trials", "C4_usdc.json")


# ----------------------------------------------------------------------------------------------- inputs C4 adds
def usdc_close():
    """Daily UTC close of Bitstamp usdcusd: frozen file (daily candles only), then the _ext file for later days."""
    a = pd.read_csv(os.path.join(ROOT, "data/ladder_v5/usdc_usd_bitstamp.csv"))
    b = pd.read_csv(os.path.join(ROOT, "data/ladder_v5/usdc_usd_bitstamp_ext.csv"))
    a, b = a[a.step == 86400], b[b.step == 86400]
    sa = pd.Series(a.close.to_numpy(float), index=pd.to_datetime(a.ts, unit="s"))
    sb = pd.Series(b.close.to_numpy(float), index=pd.to_datetime(b.ts, unit="s"))
    s = pd.concat([sa, sb[~sb.index.isin(sa.index)]]).sort_index()
    return s[~s.index.duplicated()]


def usdc_mark(days, close=None):
    """m(t) = close(t) / close(t-1) - 1; a day without a candle (or without the previous day's) counts 1.0."""
    s = usdc_close() if close is None else close
    full = pd.date_range(min(s.index.min(), days[0] - pd.Timedelta(days=1)), max(s.index.max(), days[-1]), freq="D")
    c = s.reindex(full)
    ratio = (c / c.shift(1)).fillna(1.0)
    return (ratio - 1.0).reindex(days).fillna(0.0)


def reward_daily(days, cost_mult, spread=0.005, rate=None):
    """r(t) = max(0, T-bill(t) - spread) / 365 (edge.book.rf_daily is the T-bill / 365), halved when cost_mult = 2.
    rate: optional annual rate series (index days) used instead of the T-bill proxy (sensitivity)."""
    if rate is None:
        tb_daily = ebook.rf_daily(days).to_numpy()
        r = np.maximum(0.0, tb_daily - spread / 365.0)
    else:
        r = rate.reindex(days).ffill().bfill().to_numpy() / 365.0
    h = 0.5 if cost_mult >= 2.0 else 1.0
    return pd.Series(r * h, index=days)


def positions_by_day(Q, days):
    """Time-average over each UTC day of open positions at cost (USD): take-profit part fill_t -> tp_t, the rest
    fill_t -> ex_t. Returns a Series on days."""
    d0 = np.datetime64(days[0])
    acc = np.zeros(len(days))
    segs = ((Q.fill_t.to_numpy(), Q.tp_t.to_numpy(), Q.tp_fill.to_numpy(float)),
            (Q.fill_t.to_numpy(), Q.ex_t.to_numpy(), (Q.fill - Q.tp_fill).to_numpy(float)))
    for st, en, amt in segs:
        s = (st - d0) / np.timedelta64(1, "s") / 60.0
        e = (en - d0) / np.timedelta64(1, "s") / 60.0
        for si, ei, a in zip(s, e, amt):
            if not a > 0 or ei <= si:
                continue
            k0, k1 = int(si // 1440), int(np.ceil(ei / 1440) - 1)
            for k in range(k0, k1 + 1):
                lo_, hi_ = max(si, k * 1440.0), min(ei, (k + 1) * 1440.0)
                if 0 <= k < len(days) and hi_ > lo_:
                    acc[k] += a * (hi_ - lo_) / 1440.0
    return pd.Series(acc, index=days)


def alloc4_vec(Mx, th, need, C):
    """The engine's 4-sigma allocation for many minutes at once: armed coins (prediction > threshold) in prediction
    order get their need from the budget C; a coin that cannot get it gets 0.999 x what is left if that is at least
    half its need, else nothing (and later coins may still fit). All coins free, no positions or deeper holds."""
    n, J = Mx.shape
    order = np.argsort(-Mx, axis=1)
    rows = np.arange(n)
    left = np.full(n, float(C))
    hold = np.zeros(n)
    for k in range(J):
        j = order[:, k]
        p = Mx[rows, j]
        armed = p > th
        nd = need[rows, j]
        full = armed & (nd <= left)
        part = armed & ~full & (left >= 0.5 * nd)
        amt = np.where(full, nd, np.where(part, 0.999 * left, 0.0))
        left = left - amt
        hold = hold + amt
    return hold


def alloc4_scalar(p, th, need, C):
    """Reference (one minute), written from the engine rule, to check alloc4_vec."""
    left, tot = float(C), 0.0
    for j in np.argsort(-p):
        if not p[j] > th:
            continue
        nd = need[j]
        if nd <= left:
            left -= nd
            tot += nd
        elif left >= 0.5 * nd:
            a = 0.999 * left
            left -= a
            tot += a
    return tot


def holds_by_day(P, era, pan, adv, cfg, check_n=3000):
    """Scenario B's reward base per day: time-average of (C - positions - 4-sigma holds - deeper holds) / C over all
    minutes; hsim.run's trace in its active minutes, alloc4_vec elsewhere. Also the hold and position fractions."""
    tag, (lo, hi) = fsim.ERAS[era]
    C, theta, today = cfg["C"], cfg["theta"], cfg["today"]
    W = fsim.window(P, lo, hi)
    adv_ = adv.copy()
    sc = None
    if today:                                   # exactly as hsim.book prepares its run() call
        sc = fsim.today_scale(P, lo, hi)
        W = fsim.apply_scale(W, sc)
        for c in adv_.columns:
            adv_[c] = adv_[c] * sc.get(c, 1.0)
    trace = []
    _, st, _ = hsim.run(W, era, C=C, theta=theta, policy="engine", drop_same_minute=False, adv=adv_, pan=pan,
                        scale=sc, trace=trace)
    T = pd.DataFrame(trace).set_index("t")
    idx, M, thr, coins = pan
    i_lo, i_hi = idx.searchsorted(pd.Timestamp(lo)), idx.searchsorted(pd.Timestamp(hi) + pd.Timedelta(days=1))
    mins = idx[i_lo:i_hi]
    Mx, th = M[i_lo:i_hi], thr[i_lo:i_hi]
    days = adv_.index
    A_ = adv_.reindex(columns=coins).to_numpy(np.float64)
    S_day = np.full(A_.shape, 0.25 * C)
    S_day = np.where(np.isfinite(A_), np.minimum(S_day, 0.002 * A_), S_day)
    day_of = ((mins.normalize() - days[0]) // pd.Timedelta(days=1)).to_numpy()
    need = S_day[day_of] * (1.0 / 3.0) * (1 + hsim.FEE_M)
    hold4 = alloc4_vec(Mx, th, need, C)
    # check the vectorised allocation against the scalar reference on random minutes
    rng = np.random.default_rng(7)
    pick = rng.choice(len(mins), size=min(check_n, len(mins)), replace=False)
    err = max(abs(alloc4_scalar(Mx[i], th[i], need[i], C) - hold4[i]) for i in pick)
    pos = np.zeros(len(mins))
    deep = np.zeros(len(mins))
    act = mins.get_indexer(T.index)
    ok = act >= 0
    # compare the recomputed allocation with hsim's trace where hsim had nothing open (positions 0, no deep holds)
    Tz = T[ok]
    z = (Tz.positions.to_numpy() == 0) & (Tz.deep.to_numpy() == 0) & (Tz.pending.to_numpy() == 0)
    trace_gap = float(np.median(np.abs(Tz.hold4.to_numpy()[z] - hold4[act[ok]][z]))) if z.any() else np.nan
    hold4_trace_minus_vec = float(np.mean(Tz.hold4.to_numpy()[z] - hold4[act[ok]][z])) if z.any() else np.nan
    hold4[act[ok]] = Tz.hold4.to_numpy()
    pos[act[ok]] = Tz.positions.to_numpy()
    deep[act[ok]] = Tz.deep.to_numpy()
    free = np.maximum(0.0, C - pos - hold4 - deep)
    D = pd.DataFrame({"free": free / C, "hold4": hold4 / C, "deep": deep / C, "pos_trace": pos / C,
                      "armed": (Mx > th[:, None]).sum(axis=1)}, index=mins)
    out = D.groupby(D.index.normalize()).mean().reindex(days)
    info = dict(active_minutes=int(ok.sum()), minutes=len(mins), alloc4_check_max_abs=float(err),
                trace_vs_vec_median_abs_when_idle=trace_gap, trace_minus_vec_mean_when_idle=hold4_trace_minus_vec,
                idle_trace_minutes=int(z.sum()), hsim_stats=st,
                mean_free=float(out.free.mean()), mean_hold4=float(out.hold4.mean()), mean_deep=float(out.deep.mean()),
                mean_pos_trace=float(out.pos_trace.mean()), mean_armed=float(out.armed.mean()),
                share_minutes_hold_ge_90pct=float(((hold4 + deep) / C >= 0.9).mean()))
    return out, info


# ------------------------------------------------------------------------------------------------ statistics (own)
def nw_t(x, lags=5):
    x = np.asarray(x, float)
    n = len(x)
    mu = x.mean()
    e = x - mu
    s = e @ e / n
    for k in range(1, lags + 1):
        s += 2.0 * (1.0 - k / (lags + 1.0)) * (e[k:] @ e[:-k]) / n
    return mu / np.sqrt(s / n) if s > 0 else np.nan


def ret_sharpe(r, lo, hi):
    idx = pd.date_range(lo, hi, freq="D")
    r = r.reindex(idx, fill_value=0.0)
    ex = r.to_numpy() - ebook.rf_daily(idx).to_numpy()
    yrs = len(idx) / 365.25
    return float(r.sum() / yrs), float(ex.mean() / ex.std(ddof=1) * np.sqrt(365))


# ------------------------------------------------------------------------------------------------------- main run
def run(configs, eras, do_holds=True):
    os.makedirs(OUTD, exist_ok=True)
    logged = json.load(open(LOGGED)) if os.path.exists(LOGGED) else None
    res = {"configs": {}, "notes": {}}
    for cfg in configs:
        kw = gates.CONFIGS[cfg]
        C = kw["C"]
        rows, per = [], {}
        for era in eras:
            tag, (lo, hi) = fsim.ERAS[era]
            P, pan = gates.data(tag)
            adv = gates.adv(tag, era)
            t0 = time.time()
            d_inc, out = hsim.book(P, era, pan=pan, adv=adv, **kw)
            days = pd.date_range(lo, hi, freq="D")
            d_inc = d_inc.reindex(days, fill_value=0.0)
            cache = os.path.join(gates.CACHE, f"inc_{era}_{cfg}.parquet")
            cache_gap = (float((pd.read_parquet(cache).iloc[:, 0].reindex(days) - d_inc).abs().max())
                         if os.path.exists(cache) else None)
            Q = out["instant"][0]
            pos = positions_by_day(Q, days)
            Qm = out["minute"][0]
            pos_m = positions_by_day(Qm, days)
            r = reward_daily(days, kw["cost_mult"])
            m = usdc_mark(days)
            f_usdc = 1.0 - pos / C
            add_r, add_m = r * f_usdc, m * f_usdc
            candA = d_inc + add_r + add_m
            df = pd.DataFrame({"era": era, "inc": d_inc, "pos_frac": pos / C, "pos_frac_minute": pos_m / C,
                               "reward": r, "mark": m, "add_reward": add_r, "add_mark": add_m, "candA": candA})
            if do_holds:
                H, hinfo = holds_by_day(P, era, pan, adv, kw)
                df["free_frac"] = H.free
                df["hold4_frac"] = H.hold4
                df["deep_frac"] = H.deep
                df["pos_frac_trace"] = H.pos_trace
                df["armed"] = H.armed
                df["add_reward_B"] = r * H.free
                df["candB"] = d_inc + df.add_reward_B + add_m
            else:
                hinfo = {}
            rows.append(df)
            ri, si = ret_sharpe(d_inc, lo, hi)
            rc, scd = ret_sharpe(candA, lo, hi)
            dA = candA - d_inc
            e = dict(inc_ret=ri, inc_sharpe=si, cand_ret=rc, cand_sharpe=scd, d_ret=rc - ri, d_sharpe=scd - si,
                     mean_diff=float(dA.mean()), t=float(nw_t(dA)), reward_yr=float(add_r.sum() / (len(days) / 365.25)),
                     mark_yr=float(add_m.sum() / (len(days) / 365.25)), mean_pos_frac=float(pos.mean() / C),
                     max_pos_frac=float(pos.max() / C), cache_gap=cache_gap, seconds=round(time.time() - t0),
                     frozen_stats_check=dict(fsim_nw_t=float(fsim.nw_t(dA)),
                                             fsim_cand=fsim.stats(candA, C, era), fsim_inc=fsim.stats(d_inc, C, era)))
            if do_holds:
                rb, sb = ret_sharpe(df.candB, lo, hi)
                dB = df.candB - d_inc
                e.update(B_cand_ret=rb, B_cand_sharpe=sb, B_d_ret=rb - ri, B_d_sharpe=sb - si,
                         B_mean_diff=float(dB.mean()), B_t=float(nw_t(dB)),
                         B_reward_yr=float(df.add_reward_B.sum() / (len(days) / 365.25)), holds=hinfo)
            if logged and cfg in logged["configs"] and era in logged["configs"][cfg]["eras"]:
                L = logged["configs"][cfg]["eras"][era]
                e["logged"] = {k: L[k] for k in ("inc_ret", "inc_sharpe", "cand_ret", "cand_sharpe", "t")}
                e["gap_vs_logged"] = {k: e[k] - L[k] for k in ("inc_ret", "inc_sharpe", "cand_ret", "cand_sharpe", "t")}
            per[era] = e
            print(f"{cfg} {era}: inc {ri:.4f}/{si:.3f} candA {rc:.4f}/{scd:.3f} t {e['t']:+.2f} cache_gap {cache_gap}"
                  + (f"  B {e['B_cand_ret']:.4f}/{e['B_cand_sharpe']:.3f} t {e['B_t']:+.2f} free {hinfo['mean_free']:.3f}"
                     if do_holds else "") + f"  [{e['seconds']}s]", flush=True)
        D = pd.concat(rows)
        D.index.name = "date"
        D.to_csv(os.path.join(OUTD, f"c4_daily_{cfg}.csv"))
        dA = (D.candA - D.inc).to_numpy()
        c = dict(eras=per, pooled_t=float(nw_t(dA)), pooled_mean=float(dA.mean()))
        # what carries the variance: the two depeg days
        dev = dA - dA.mean()
        dep = D.index.isin(pd.to_datetime(["2023-03-11", "2023-03-12"]))
        c["var_share_mar11_12_2023"] = float((dev[dep] ** 2).sum() / (dev ** 2).sum()) if len(dev) else None
        wk = (D.index >= "2023-03-09") & (D.index <= "2023-03-15")
        c["pooled_t_ex_mar9_15_2023"] = float(nw_t(dA[~wk]))
        c["pooled_t_mark_only"] = float(nw_t((D.add_mark).to_numpy()))
        c["pooled_mean_mark_only"] = float(D.add_mark.mean())
        if logged and cfg in logged["configs"]:
            c["logged_pooled_t"] = logged["configs"][cfg]["pooled_t"]
        if do_holds:
            dB = (D.candB - D.inc).to_numpy()
            c["B_pooled_t"] = float(nw_t(dB))
            c["B_pooled_mean"] = float(dB.mean())
        # cross-check of the own NW t with statsmodels' HAC (Bartlett, 5 lags, no small-sample correction)
        try:
            import statsmodels.api as sm
            fit = sm.OLS(dA, np.ones(len(dA))).fit(cov_type="HAC", cov_kwds={"maxlags": 5, "use_correction": False})
            c["statsmodels_hac_t"] = float(fit.tvalues[0])
        except Exception as ex:  # noqa: BLE001
            c["statsmodels_hac_t"] = f"n/a ({ex})"
        res["configs"][cfg] = c
        print(f"{cfg}: pooled t A {c['pooled_t']:+.3f} (logged {c.get('logged_pooled_t')})"
              + (f"  B {c['B_pooled_t']:+.3f}" if do_holds else "")
              + f"  var share Mar 11-12 2023 {c['var_share_mar11_12_2023']:.2f}  t ex Mar 9-15 2023 "
                f"{c['pooled_t_ex_mar9_15_2023']:+.1f}", flush=True)
    json.dump(res, open(os.path.join(OUTD, "c4_summary.json"), "w"), indent=1, default=float)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="S_0.5,S_0.25,base_0.5,cap_1M")
    ap.add_argument("--eras", default="sel,chk,early")
    ap.add_argument("--no-holds", action="store_true")
    a = ap.parse_args()
    run(a.configs.split(","), a.eras.split(","), do_holds=not a.no_holds)
