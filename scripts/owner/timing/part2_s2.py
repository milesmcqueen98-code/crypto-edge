#!/usr/bin/env python3
"""Live order timing study, part 2, S2: the whole ladder for every parent of every policy (P0 included), like for
like (reports/owner/timing_prereg.md, deviation 3). Planned after the first reading was seen.

Rows (one per rung, as scripts/wick1m/sim.py precompute, Coinbase spot only):
  4 sigma  the parent: its own minute q, price px (L(q), or L(q-1) for a stale-bid fill); level and sigma of that bid
  6, 8     L x exp(-2 sigma), L x exp(-4 sigma); fill on the first print at or below rung - tick in
           [parent fill + 1 s, q + 70 s) (the deep prints, deviation 3; minute q, or q + 1 from 60 s), else on the
           first candle low <= rung - tick from minute q + 1 to the minute before the parent's take-profit minute
           (else q + 59); the parent's take-profit minute is the research's (first high >= tp x (1 + tick / px))
  each filled rung: capacity below it, take-profit minute and capacity, 60-minute close: precompute's rules from its
           own fill minute
Evaluation: scripts/ladder_v5/fsim.py evaluate (the research's sizes: kappa x ADV in thirds, theta x volume below,
sellers and take-profit buyers shared within a parent) at S* (today's volumes, costs x2, theta 0.5, $250K), cash cap
off, fee tier fixed to the research book's, one ordering (no same-minute drop: the rungs rest 1 s after the fill);
remainder exits priced from prints as lsim.rem_daily (part2.row_pnl).
Validation (before any policy difference): on the parents P0 shares with the research,
  A  the research ladder (engine-faithful replay with the cash rule, poll1s blend of the two bounds);
  B  the same evaluator on the research's own frozen rows (cash off, blend of the two bounds);
  C  the rows rebuilt here with candles only (the research's rule, cash off, blend): checks the row builder;
  D  P0 under S2.
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import part2 as P2  # noqa: E402
import evaluate as EV  # noqa: E402
import lsim  # noqa: E402
import fsim  # noqa: E402
import sim  # noqa: E402
import wick_sim as ws  # noqa: E402

ROOT, OUT, H = P2.ROOT, P2.OUT, 60
SRC = {"main": "minute", "early": "minute_early"}


def candles(tag):
    start, end, _ = sim.PERIODS[tag]
    idx = pd.date_range(start, end, freq="min", inclusive="left")
    return idx, {}


def coin_data(tag, c, cache, idx):
    if c not in cache:
        cache[c] = sim.load_venue(os.path.join(ROOT, "data", SRC[tag], f"{c}.parquet"), idx)
    return cache[c]


def build_rows(Pp, tag, deep, mode, cache, idx):
    """Rung rows of parents Pp (coin, q, px, ms, src, lev, sg, adv, vol_d). mode 'prints' (S2) or 'candles' (the
    research's rule: deeper rungs on candle lows from minute q)."""
    rows = []
    for r in Pp.itertuples():
        S = coin_data(tag, r.coin, cache, idx)
        tick = float(ws.spot_tick(r.coin))
        i0 = idx.get_indexer([r.q])[0]
        assert i0 > 0
        tickf0 = tick / r.px
        tp_par = r.px * np.exp(0.6 * 4.0 * r.sg)
        i_tp_par = sim.first_touch(S["high"], i0 + 1, i0 + H, tp_par * (1 + tickf0))
        close_par = i_tp_par if i_tp_par >= 0 else i0 + H
        base = dict(ts=r.q, coin=r.coin, adv=r.adv, vol_d=r.vol_d, policy_ms=r.ms)
        for k in sim.LADDER:
            lvl = r.px if k == 4.0 else float(r.lev * np.exp(-(k - 4.0) * r.sg))
            tickf = tick / lvl
            fms = np.nan
            if k == 4.0:
                i_f, fms = i0, r.ms
            elif mode == "candles":
                lows = np.nan_to_num(S["low"][i0:close_par], nan=np.inf)
                hit = np.nonzero(lows <= lvl * (1 - tickf))[0]
                i_f = int(i0 + hit[0]) if len(hit) else -1
            else:
                i_f = -1
                a, b = deep.get((r.coin, r.q), (np.zeros(0), np.zeros(0)))
                end_ms = 70000.0 if close_par > i0 + 1 else 60000.0
                m = (a >= r.ms + 1000.0) & (a < end_ms) & (b <= lvl - tick + 1e-9 * lvl)
                if m.any():
                    fms = float(a[m][0])
                    i_f = i0 + (1 if fms >= 60000.0 else 0)
                elif close_par > i0 + 1:
                    lows = np.nan_to_num(S["low"][i0 + 1:close_par], nan=np.inf)
                    hit = np.nonzero(lows <= lvl * (1 - tickf))[0]
                    if len(hit):
                        i_f = int(i0 + 1 + hit[0])
            row = dict(base, k=k, filled=i_f >= 0, lvl=lvl, fill_ms=fms)
            if i_f < 0:
                rows.append(row)
                continue
            tp = lvl * np.exp(0.6 * k * r.sg)
            i_tp = sim.first_touch(S["high"], i_f + 1, i_f + H, tp * (1 + tickf))
            usd, last = sim.below_usd(S, i_f, lvl)
            path = pd.Series(S["cf"][i_f:i_f + H + 1]).ffill().bfill().to_numpy()
            row.update(f_off=i_f - i0, tp_off=(i_tp - i_f) if i_tp >= 0 else -1, tp_hit=i_tp >= 0,
                       scan_off=last - i0, g_tp=1e4 * np.log(tp / lvl), g60=1e4 * np.log(path[-1] / lvl),
                       in_spot=usd, tp_spot=sim.above_usd(S, i_f + 1, i_f + H, tp))
            rows.append(row)
    F = pd.DataFrame(rows)
    for col in ("in_spot", "tp_spot"):
        F[col] = F[col].fillna(0.0)
    for v in ("perp", "bitstamp"):
        F[f"in_{v}"], F[f"tp_{v}"] = 0.0, 0.0
    return F


def ev(F, era, blend):
    """fsim.evaluate at S*, cash off, the research's fee tier; per parent (ts, coin): ladder P&L, 4-sigma P&L,
    daily P&L (tp leg on its day, remainder on its exit day)."""
    cfg = "S_0.5"
    kw = lsim.CONFIGS[cfg]
    tag, (lo, hi) = fsim.ERAS[era]
    info = lsim.load_books(cfg, era)["minute"][1]
    tiers = [(0, info["maker_bp"] / 1e4, info["taker_bp"] / 1e4)]
    W = fsim.apply_scale(F, fsim.today_scale(lsim.RL.inputs(tag)["P"], lo, hi))
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    idx = pd.date_range(lo, hi, freq="D")
    out = {}
    for name, drop in ((("minute", True), ("instant", False)) if blend else (("one", False),)):
        Q, _, inf = fsim.evaluate(W, theta=kw["theta"], C=kw["C"], gross_cap=None, days=days, tiers=tiers,
                                  drop_same_minute=drop, hs_bp=fsim.HS_BP * kw["cost_mult"],
                                  impact_y=fsim.IMPACT_Y * kw["cost_mult"])
        Q = Q.assign(rowpnl=P2.row_pnl(Q, inf, era, kw))
        tpart = (Q.pnl_tp - Q.entry_cost).to_numpy()
        g = Q.groupby(["ts", "coin"])
        par = pd.DataFrame(dict(ladder=g.rowpnl.sum(), r4=Q[Q.k == 4.0].groupby(["ts", "coin"]).rowpnl.sum(),
                                rungs=g.size(), bought=g.fill.sum()))
        d = pd.concat([pd.Series(tpart, index=Q.tp_t.dt.floor("D").to_numpy()),
                       pd.Series(Q.rowpnl.to_numpy() - tpart, index=Q.ex_t.dt.floor("D").to_numpy())])
        out[name] = (par, d.groupby(level=0).sum().reindex(idx, fill_value=0.0), Q)
    if not blend:
        return out["one"]
    s = fsim.lat_share(era, kw["theta"])
    m, x = out["minute"][0], out["instant"][0].reindex(out["minute"][0].index).fillna(0.0)
    par = m.copy()
    for col in ("ladder", "r4", "bought"):
        par[col] = m[col] + s * (x[col] - m[col])
    d = out["minute"][1] + s * (out["instant"][1] - out["minute"][1])
    return par, d, out["instant"][2]


def run(scr, deep_path):
    t0 = time.time()
    J, R, d0s, Cs = P2.base(scr)
    st = J.src.eq("stale")
    J["lev"] = np.where(st, J.L_prev, J.L)
    J["sg"] = np.where(st, J.sig_prev, J.sig)
    Dp = pd.read_parquet(deep_path)
    Dp["q"] = pd.to_datetime(Dp.q)
    deep = {(c, q): (np.asarray(a, float), np.asarray(b, float))
            for c, q, a, b in zip(Dp.coin, Dp.q, Dp.deep_ms, Dp.deep_px)}
    print(f"loaded ({time.time() - t0:.0f}s)", flush=True)
    V, val, rowchk, pars = {}, [], [], []
    for e in EV.ERAS:
        tag = EV.ERAS[e][0]
        idx, cache = candles(tag)
        E = J[J.era == e].copy()
        res = []
        for p in P2.POLS:
            F = build_rows(E[E.policy == p], tag, deep, "prints", cache, idx)
            par, d, Q = ev(F, e, blend=False)
            res.append((p, par, d))
            pp = par.reset_index().assign(era=e, policy=p)
            pars.append(pp)
        # per-parent S2 ladder into the table frame
        rows = []
        for p, par, d in res:
            rows.append(pd.DataFrame(dict(policy=p, s2=d.to_numpy(), day=d.index)))
        V[e] = pd.concat(rows, ignore_index=True)
        # validation on the parents P0 shares with the research
        Rr = R[e]
        b0 = E[E.policy == "P0"]
        shared = [k for k in zip(b0.q, b0.coin) if k in Rr.index]
        lo, hi = fsim.ERAS[e][1]
        Pf = fsim.window(fsim.load(tag), lo, hi)
        keyP = pd.MultiIndex.from_arrays([Pf.ts, Pf.coin])
        B, _, _ = ev(Pf[keyP.isin(shared)].copy(), e, blend=True)
        Cf = build_rows(b0[[k in set(shared) for k in zip(b0.q, b0.coin)]], tag, deep, "candles", cache, idx)
        Cp, _, Cq = ev(Cf, e, blend=True)
        D_ = res[0][1]
        # row builder against the frozen rows (candles, research parents)
        fz = Pf[keyP.isin(shared)].set_index(["ts", "coin", "k"])
        mine = Cf.set_index(["ts", "coin", "k"])
        jj = fz.join(mine, rsuffix="_m", how="inner")
        rowchk.append(dict(era=e, rows=len(jj), filled_same=float((jj.filled == jj.filled_m).mean()),
                           f_off_same=float((jj.f_off[jj.filled].fillna(-9) == jj.f_off_m[jj.filled].fillna(-9)).mean()),
                           tp_off_same=float((jj.tp_off[jj.filled] == jj.tp_off_m[jj.filled]).mean()),
                           in_spot_maxrel=float(np.nanmax(np.abs(jj.in_spot_m[jj.filled] / jj.in_spot[jj.filled] - 1))),
                           g60_maxdiff_bp=float(np.nanmax(np.abs(jj.g60_m[jj.filled] - jj.g60[jj.filled])))))
        sh = pd.MultiIndex.from_tuples(shared)
        A = Rr.loc[sh]
        val.append(dict(era=e, shared=len(shared),
                        A_research=float(A.ladder.sum()), B_frozen_rows_nocash=float(B.ladder.reindex(sh).sum()),
                        C_rebuilt_candles_nocash=float(Cp.ladder.reindex(sh).sum()),
                        D_p0_s2=float(D_.ladder.reindex(sh).fillna(0).sum()),
                        A_r4=float(A.r4.sum()), D_r4=float(D_.r4.reindex(sh).fillna(0).sum()),
                        A_rungs_deep=float((A.n_rungs - 1).sum()),
                        D_rungs_deep=float((D_.rungs.reindex(sh).fillna(1) - 1).sum()),
                        p0_s2_all=float(D_.ladder.sum())))
        val[-1]["D_vs_A_pct"] = 100 * (val[-1]["D_p0_s2"] / val[-1]["A_research"] - 1)
        val[-1]["B_vs_A_pct"] = 100 * (val[-1]["B_frozen_rows_nocash"] / val[-1]["A_research"] - 1)
        val[-1]["D_vs_C_pct"] = 100 * (val[-1]["D_p0_s2"] / val[-1]["C_rebuilt_candles_nocash"] - 1)
        print(f"{e}: S2 ({time.time() - t0:.0f}s)", flush=True)
    # table: per-day series per policy -> reuse part2.table on a frame with one row per (policy, day)
    T = P2.table(V, "s2", d0s, Cs, "S2")
    pd.set_option("display.width", 250)
    T.to_csv(os.path.join(OUT, "s2.csv"), index=False, float_format="%.6g")
    P2.rule(T).to_csv(os.path.join(OUT, "s2_rule.csv"), index=False)
    pd.DataFrame(val).to_csv(os.path.join(OUT, "s2_check.csv"), index=False, float_format="%.6g")
    pd.DataFrame(rowchk).to_csv(os.path.join(OUT, "s2_rowcheck.csv"), index=False, float_format="%.6g")
    pd.concat(pars, ignore_index=True).to_csv(os.path.join(OUT, "s2_parents.csv.gz"), index=False,
                                              float_format="%.8g")
    print(pd.DataFrame(rowchk).to_string(index=False))
    print(pd.DataFrame(val).round(1).to_string(index=False))
    print(T.round(3).to_string(index=False))
    print(P2.rule(T).to_string(index=False))
    print(f"done ({time.time() - t0:.0f}s)")
