#!/usr/bin/env python3
"""Ladder v5, cash_venue post hoc analyses (NOT trials; run after C4_usdc and C5_perp_venue were logged).

C4 scenario B (reports/ladder_v5/specs/cash_venue.md): USDC rewards only on USDC that is not on hold for resting bids;
the USDC/USD mark is still on the whole USDC balance. Rewards per day = r_usdc(t) (halved when cost_mult == 2) x the
day's average over its minutes of free(m) / C, free = C - positions - 4-sigma holds - deeper-rung holds:
  - minutes when hsim is stepping (a parent's window is open: hsim.run's "active" minutes): positions, 4-sigma holds
    and deeper holds exactly as hsim.run allocates them (its trace, instant bound);
  - other minutes: no rung is open and no coin is busy, so the 4-sigma holds are hsim's allocation rule applied to the
    panel (armed coins in prediction order, want/3 x (1 + maker fee) each, the rest if at least half, else none) from
    C minus the open positions of the instant-bound Q (deeper fills whose exits run past their parent's window).
Writes reports/ladder_v5/cashvenue/posthoc_c4b.json and posthoc_c4b_daily.csv.
usage: python scripts/ladder_v5/cashvenue_posthoc.py [cfg ...]     (default S_0.5 base_0.5)
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cand_cashvenue as cv  # noqa: E402  (copies and checks the frozen dataset on import)

fsim, gates, hsim = cv.fsim, cv.gates, cv.hsim


def holds_outside(M, thr, rows, budget, S_day, day_of, C, per_trade=0.25):
    """hsim's 4-sigma allocation (policy engine, nobody busy) at panel rows `rows`, vectorised over minutes."""
    Ms, th = M[rows], thr[rows]
    order = np.argsort(-Ms, axis=1)
    d = day_of[rows]
    ok = (d >= 0) & (d < S_day.shape[0])
    left, hold = budget.astype(float).copy(), np.zeros(len(rows))
    share = 1 / 3.0
    for r in range(Ms.shape[1]):
        j = order[:, r]
        p = Ms[np.arange(len(rows)), j]
        armed = p > th
        w = np.where(ok, S_day[np.clip(d, 0, S_day.shape[0] - 1), j], per_trade * C)
        need = w * share * (1 + hsim.FEE_M)
        full = armed & (need <= left)
        part = armed & ~full & (left >= 0.5 * need)
        x = np.where(full, need, np.where(part, 0.999 * left, 0.0))
        hold += x
        left -= x
    return hold


def scenario_b(era, cfg):
    tag, (lo, hi) = fsim.ERAS[era]
    P, pan = gates.data(tag)
    kw = gates.CONFIGS[cfg]
    theta, C, today, cost_mult = kw["theta"], kw["C"], kw["today"], kw["cost_mult"]
    idx, M, thr, coins = pan
    # hsim.book's set-up and its instant branch, with hsim.run's trace
    W = fsim.window(P, lo, hi)
    adv = gates.adv(tag, era)
    sc = None
    if today:
        sc = fsim.today_scale(P, lo, hi)
        W = fsim.apply_scale(W, sc)
        adv = adv.copy()
        for c in adv.columns:
            adv[c] = adv[c] * sc.get(c, 1.0)
    days = pd.date_range(lo, hi, freq="D")
    trace = []
    o, st, foff = hsim.run(W, era, C=C, theta=theta, drop_same_minute=False, adv=adv, pan=pan, trace=trace, scale=sc)
    Wm = hsim.with_live_fills(W, foff, tag, sc)
    want = np.minimum(0.25 * C, 0.002 * Wm.adv.fillna(0.0)) * Wm.k.map({4.0: 1 / 3, 6.0: 1 / 3, 8.0: 1 / 3})
    Wm["mult"] = np.where(want > 0, o.reindex(Wm.index).fillna(0.0) / want, 0.0)
    Q, d_inst, _ = fsim.evaluate(Wm, theta=theta, C=C, days=len(days), drop_same_minute=False,
                                 hs_bp=fsim.HS_BP * cost_mult, impact_y=fsim.IMPACT_Y * cost_mult)
    # minute grid of the era (the panel's index)
    i_lo, i_hi = idx.searchsorted(pd.Timestamp(lo)), idx.searchsorted(pd.Timestamp(hi) + pd.Timedelta(days=1))
    grid = idx[i_lo:i_hi]
    n = len(grid)
    # open positions of the instant-bound Q on the grid: [fill minute, release minute)
    a, s, e = cv._segments(Q)
    pos = np.zeros(n + 1)
    np.add.at(pos, np.clip(grid.searchsorted(s), 0, n), a)
    np.add.at(pos, np.clip(grid.searchsorted(e), 0, n), -a)
    posQ = np.cumsum(pos)[:n]
    T = pd.DataFrame(trace)
    act = np.zeros(n, bool)
    p_m, h4, dp = posQ.copy(), np.zeros(n), np.zeros(n)
    if len(T):
        k = grid.get_indexer(pd.DatetimeIndex(T.t))
        keep = k >= 0
        k = k[keep]
        act[k] = True
        p_m[k], h4[k], dp[k] = T.positions.to_numpy()[keep], T.hold4.to_numpy()[keep], T.deep.to_numpy()[keep]
    # outside hsim's active minutes: the 4-sigma allocation from C - open positions
    A_ = adv.reindex(columns=coins).to_numpy(np.float64)
    S_day = np.where(np.isfinite(A_), np.minimum(0.25 * C, 0.002 * A_), 0.25 * C)
    day_of = ((idx.normalize() - adv.index[0]) // pd.Timedelta(days=1)).to_numpy()
    out_rows = np.nonzero(~act)[0]
    h4[out_rows] = holds_outside(M, thr, i_lo + out_rows, C - posQ[out_rows], S_day, day_of, C)
    free = np.clip(C - p_m - h4 - dp, 0.0, None)
    g = pd.DataFrame(dict(day=grid.floor("D"), free=free / C, held=(h4 + dp) / C, act=act))
    by = g.groupby("day").agg(free=("free", "mean"), held=("held", "mean"), act=("act", "mean"), minutes=("free", "size"))
    by = by.reindex(days)
    pos_avg = cv.day_positions(Q, days).to_numpy(float)
    half = 0.5 if cost_mult == cv.UNVERIFIED else 1.0
    r = cv.usdc_reward(days) * half
    m = cv.usdc_mtm(days)
    extra_a = (r + m) * (1.0 - pos_avg / C)
    extra_b = r * by.free.fillna(1.0).to_numpy() + m * (1.0 - pos_avg / C)
    inc = gates.incumbent_cached(era, cfg)
    df = pd.DataFrame(dict(cfg=cfg, era=era, date=days, inc=inc.reindex(days).to_numpy(), reward_a=r * (1 - pos_avg / C),
                           reward_b=r * by.free.fillna(1.0).to_numpy(), mtm=m * (1 - pos_avg / C),
                           free_b=by.free.to_numpy(), held=by.held.to_numpy(), active_share=by.act.to_numpy(),
                           minutes=by.minutes.to_numpy()))
    df["cand_a"], df["cand_b"] = df.inc + extra_a, df.inc + extra_b
    info = dict(minutes=int(n), active_minutes=int(act.sum()), days_short=int((by.minutes < 1440).sum()),
                hsim_stats=st)
    return df, info


def stats(df, C):
    out, diffs = {}, {}
    for era, g in df.groupby("era", sort=False):
        inc = pd.Series(g.inc.to_numpy(), index=g.date)
        e = {"held_avg": float(g.held.mean()), "free_b_avg": float(g.free_b.mean()),
             "reward_a_usd_yr": float(g.reward_a.sum() * C / (len(g) / 365.25)),
             "reward_b_usd_yr": float(g.reward_b.sum() * C / (len(g) / 365.25))}
        si = fsim.stats(inc, C, era)
        e.update(inc_ret=si["ret_yr"], inc_sharpe=si["sharpe"])
        for v in ("a", "b"):
            c = pd.Series(g[f"cand_{v}"].to_numpy(), index=g.date)
            sc = fsim.stats(c, C, era)
            d = c - inc
            e.update({f"{v}_ret": sc["ret_yr"], f"{v}_sharpe": sc["sharpe"], f"{v}_mean_diff": float(d.mean()),
                      f"{v}_t": float(fsim.nw_t(d))})
            diffs.setdefault(v, []).append(d)
        out[era] = e
    pooled = {v: float(fsim.nw_t(pd.concat(x))) for v, x in diffs.items()}
    return out, pooled


def main():
    cfgs = sys.argv[1:] or ["S_0.5", "base_0.5"]
    res, frames = {}, []
    for cfg in cfgs:
        dfs, infos = [], {}
        for era in fsim.ERAS:
            t0 = time.time()
            df, info = scenario_b(era, cfg)
            info["seconds"] = round(time.time() - t0)
            dfs.append(df)
            infos[era] = info
            print(cfg, era, info, flush=True)
        df = pd.concat(dfs)
        frames.append(df)
        per, pooled = stats(df, gates.CONFIGS[cfg]["C"])
        res[cfg] = dict(eras=per, pooled_t=pooled, info=infos)
        print(cfg, json.dumps(per, indent=1, default=float), pooled, flush=True)
    os.makedirs(cv.OUTD, exist_ok=True)
    json.dump(res, open(os.path.join(cv.OUTD, "posthoc_c4b.json"), "w"), indent=1, default=float)
    pd.concat(frames).to_csv(os.path.join(cv.OUTD, "posthoc_c4b_daily.csv"), index=False, float_format="%.8g")


if __name__ == "__main__":
    main()
