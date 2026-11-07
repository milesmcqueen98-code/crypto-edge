#!/usr/bin/env python3
"""H4 (NL) step 2: the sleeve simulator (reports/hunt/h4nl/SPEC.md, reports/hunt_prereg.md).

Portfolio rules (SPEC "Sizing"; interpretation written down before any trial):
- every listing in its window (t0 + 2 h <= t < t0 + (N+1) days for "days 0-N"; with the liquidity filter, also after
  its cumulative day-1 USD volume reached $1M, known at t-1) and without an open position rests one bid;
- resting bids count at full size against capital: room = capital - cost of open positions; bids go to the most
  recent listings first (t0 descending), min($3K, what is left of the room) each;
- a fill takes min(bid, theta x through-volume); at most 6 positions at once (fills in one minute are taken in the
  same priority order; a fill beyond the cap is dropped, i.e. the bot cancels its other bids when the 6th opens);
- one position per coin: the coin's bid returns the minute after its position closes;
- take-profit (post-only, maker) fills min(position, theta x USD volume above it over t+1..t+H) at its price; the rest
  is sold at the open of the first traded minute after t+H (taker + half-spread);
- costs: spot maker on entries and take-profits, taker + half-spread on time exits (common.py fees; the SPEC's
  half-spread of 5 bp at 1x, 10 bp at 2x, replaces common's 2 bp for these wide books);
- P&L booked on the exit day (UTC); daily return = P&L / sleeve capital; idle days 0; only gates.ERA_DAYS are scored
  (2024 listings only train the AI variant).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402
import gates  # noqa: E402

DATA = os.path.join(ROOT, "data", "hunt", "h4nl")
OUT = os.path.join(ROOT, "reports", "hunt", "h4nl")
DEV_END = pd.Timestamp("2026-05-31")             # last DEV day; dev runs read cand_dev (no minute >= 2026-06-01)
ORDER_USD, MAX_POS, WARM_MIN = 3000.0, 6, 120
HS_BP = 5.0                                      # SPEC: half-spread for market exits on new listings, 1x (10 bp at 2x)
FEATS = ["f_days", "f_dd_d1", "f_vol_d1", "f_btc60", "sig", "f_depth_bp"]


def cost_frac(mult):
    maker = common.spot_cost_bp(taker=False, mult=mult) / 1e4
    taker = (common.spot_cost_bp(taker=True, mult=mult) - mult * common.SPOT_HALF_SPREAD_BP + mult * HS_BP) / 1e4
    return maker, taker


def load(mode):
    C = pd.read_parquet(os.path.join(DATA, f"cand_{mode}.parquet"))
    L = pd.read_csv(os.path.join(DATA, f"listings_{mode}.csv"), parse_dates=["t0", "liq_from", "first_day"])
    if mode == "dev":
        assert C.ts.max() < gates.HOLD0
    return C, L


def variant_name(v):
    s = f"k{v['k']:g}_d{v['win']}_{'liq1m' if v['liq'] else 'all'}_H{v['H']}"
    return s + (f"_ai{v['ai']}" if v.get("ai") else "")


def candidates(C, L, v, keep=None):
    """Candidate fills of variant v (no portfolio rules yet)."""
    q = C[C.k == v["k"]].merge(L[["pid", "t0", "liq_from", "status"]], on="pid")
    q = q[q.ts < q.t0 + pd.Timedelta(days=v["win"] + 1)]
    if v["liq"]:
        q = q[q.liq_from.notna() & (q.ts >= q.liq_from)]
    if keep is not None:                                # keep: set of (pid, ts) candidate keys
        q = q[[(p_, t_) in keep for p_, t_ in zip(q.pid, q.ts)]]
    H = v["H"]
    q = q.assign(tp_off=q[f"tp_off{H}"], tp_cap=q[f"tp_cap{H}"], x_off=q[f"x_off{H}"], x_px=q[f"x_px{H}"])
    return q[q.x_off > 0].sort_values(["ts", "t0", "pid"], ascending=[True, False, True])


def simulate(q, L, v, capital, theta=0.5, mult=2.0, drop_pids=()):
    """Run the portfolio over candidate fills q. Returns (trades DataFrame, daily P&L Series in USD)."""
    maker, taker = cost_frac(mult)
    Lw = L[~L.pid.isin(drop_pids)].copy()
    start = (Lw.t0 + pd.Timedelta(minutes=WARM_MIN)).to_numpy()
    if v["liq"]:
        start = np.maximum(start, Lw.liq_from.fillna(pd.Timestamp("2100-01-01")).to_numpy())
    stop = (Lw.t0 + pd.Timedelta(days=v["win"] + 1)).to_numpy()
    t0s = Lw.t0.to_numpy()
    pids = Lw.pid.to_numpy()
    open_pos = []                                       # dicts: pid, t_fill, t_close, cost
    rows = []
    q = q[~q.pid.isin(drop_pids)]
    for r in q.itertuples():
        t = r.ts.to_datetime64()
        open_pos = [p for p in open_pos if p["t_close"] >= t]   # closed before minute t: cash back, bid back
        if any(p["pid"] == r.pid for p in open_pos):
            continue                                    # one position per coin
        held = {p["pid"] for p in open_pos if p["t_fill"] < t}
        room = capital - sum(p["cost"] for p in open_pos if p["t_fill"] < t)
        elig = (start <= t) & (stop > t)
        higher = elig & ((t0s > r.t0.to_datetime64()) | ((t0s == r.t0.to_datetime64()) & (pids < r.pid)))
        n_hi = int(higher.sum()) - sum(1 for p in held if p in set(pids[higher]))
        bid = float(np.clip(room - ORDER_USD * n_hi, 0.0, ORDER_USD))
        if bid < 10.0:
            continue
        if sum(1 for p in open_pos if p["t_fill"] <= t) >= MAX_POS:
            continue
        f = min(bid, theta * float(r.thr_usd))
        if f < 1.0:
            continue
        g_tp, g_x = r.tp / r.lvl - 1.0, r.x_px / r.lvl - 1.0
        qtp = min(f, theta * float(r.tp_cap)) if r.tp_off > 0 else 0.0
        rem = f - qtp
        pnl_tp = qtp * g_tp - qtp * (1 + g_tp) * maker - qtp * maker
        pnl_x = rem * g_x - rem * (1 + g_x) * taker - rem * maker
        t_tp = t + np.timedelta64(int(r.tp_off), "m") if qtp > 0 else None
        t_x = t + np.timedelta64(int(r.x_off), "m")
        t_close = t_tp if (qtp > 0 and rem <= 1e-9) else t_x
        open_pos.append(dict(pid=r.pid, t_fill=t, t_close=t_close, cost=f))
        rows.append(dict(pid=r.pid, ts=r.ts, t0=r.t0, bid=bid, fill=f, tp_fill=qtp, pnl_tp=pnl_tp, pnl_x=pnl_x,
                         pnl=pnl_tp + pnl_x, t_tp=t_tp, t_x=t_x, g_tp=g_tp, g_x=g_x, thr_usd=float(r.thr_usd),
                         days=float(r.f_days), status=r.status, depth_bp=float(r.f_depth_bp)))
    T = pd.DataFrame(rows)
    if T.empty:
        return T, pd.Series(dtype=float)
    d = pd.concat([pd.Series(T.pnl_tp.to_numpy(), index=pd.to_datetime(T.t_tp.where(T.tp_fill > 0, T.t_x)).dt.floor("D")),
                   pd.Series(T.pnl_x.to_numpy(), index=pd.to_datetime(T.t_x).dt.floor("D"))]).groupby(level=0).sum()
    return T, d


def daily_returns(daily_usd, capital, days):
    return (pd.Series(daily_usd, dtype=float).reindex(days).fillna(0.0) / capital).rename(None)


def dev_days():
    d = gates.ERA_DAYS
    return d[d <= DEV_END]


# ------------------------------------------------------------------ AI (walk-forward LightGBM filter)
def labels(q, theta=0.5, mult=2.0):
    """Per-candidate net return at 2x costs for an unconstrained order of min($3K, theta x through-volume)."""
    maker, taker = cost_frac(mult)
    f = np.minimum(ORDER_USD, theta * q.thr_usd.to_numpy(float))
    g_tp, g_x = q.tp.to_numpy() / q.lvl.to_numpy() - 1, q.x_px.to_numpy() / q.lvl.to_numpy() - 1
    qtp = np.where(q.tp_off.to_numpy() > 0, np.minimum(f, theta * q.tp_cap.to_numpy(float)), 0.0)
    rem = f - qtp
    pnl = qtp * (g_tp - (1 + g_tp) * maker) + rem * (g_x - (1 + g_x) * taker) - f * maker
    return pd.Series(1e4 * pnl / np.maximum(f, 1e-9), index=q.index)


def ai_keep(q_all, rule, first_q="2022Q3", last_q=None):
    """Walk-forward by quarter: train on candidates before (quarter start - 1 day), keep test candidates with
    predicted net bp > 0 ("pos") or > the training-prediction median ("med"). Before the first test quarter there is
    no model, so candidates pass unfiltered. Resting bids of filtered coins still reserve cash (conservative)."""
    import lightgbm as lgb
    sys.path.insert(0, ROOT)
    from edge import wick
    y = labels(q_all)
    last_q = last_q or str(pd.Period(q_all.ts.max(), "Q"))
    keep, preds = [], {}
    for per in pd.period_range(first_q, last_q, freq="Q"):
        tr = q_all[q_all.ts < per.start_time - pd.Timedelta(days=1)]
        te = q_all[(q_all.ts >= per.start_time) & (q_all.ts <= per.end_time)]
        if te.empty:
            continue
        if len(tr) < 100:                               # too little history for a model: pass unfiltered
            keep += list(zip(te.pid, te.ts))
            continue
        p_te, p_tr = [], []
        for s in (7, 11, 23):
            m = lgb.train(dict(wick.PARAMS) | {"seed": s}, lgb.Dataset(tr[FEATS], y[tr.index]),
                          num_boost_round=wick.ROUNDS)
            p_te.append(m.predict(te[FEATS]))
            p_tr.append(m.predict(tr[FEATS]))
        p_te, p_tr = np.mean(p_te, axis=0), np.mean(p_tr, axis=0)
        thr = 0.0 if rule == "pos" else float(np.median(p_tr))
        keep += list(zip(te.pid[p_te > thr], te.ts[p_te > thr]))
        preds.update(dict(zip(zip(te.pid, te.ts), p_te)))
    keep += list(zip(q_all.pid[q_all.ts < pd.Period(first_q, "Q").start_time],
                     q_all.ts[q_all.ts < pd.Period(first_q, "Q").start_time]))   # no model yet: unfiltered
    return set(keep), pd.Series(preds)
