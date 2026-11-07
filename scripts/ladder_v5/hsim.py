#!/usr/bin/env python3
"""Ladder v5: the live bot's cash rule on top of the frozen simulator ("hold-aware" book).

Coinbase holds cash for every resting spot bid, so the bot (bot/spot/engine.py) keeps positions at cost plus all
resting bids within equity. The research simulator (fsim) counts positions only. This replays the bot's allocation
at minute resolution and returns each tranche's funded order size; fsim then computes fills, costs and P&L with
those sizes (mult = order / research want), so everything else is the frozen model.

The rules, as the engine applies them:
  - Each minute the AI's prediction for every coin (data/ladder_v5/panel_<era>, the walk-forward R2-08 models the
    trade lists come from) arms the coins above the quarter's threshold. A coin is busy (no new 4-sigma bid) while
    its 4-sigma rung is open (fill to take-profit or 60 minutes).
  - 4-sigma bids: armed coins in prediction order get want x (1 + maker fee) from equity minus positions minus
    deeper-rung holds; a coin that cannot get it gets what is left if that is at least half, else nothing.
  - Deeper rungs (6 and 8 sigma) go out when the parent fills (1-second detection), from the cash not held by 4-sigma
    bids or positions; if short, they retry every minute while the parent's window is open (take-profit or 60 min).
    They hold their cash until they fill or the window closes.
  - A parent fill in the trade list needs its coin's bid to be funded that minute; a deeper fill needs its rung to
    be resting by its fill minute.
Policies (for the cash-allocation candidate) change only who gets cash: policy "engine" is the bot today.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fsim  # noqa: E402
import sim  # noqa: E402

PANEL = os.path.join(fsim.ROOT, "data", "ladder_v5")
FEE_M = 6e-4
_DEEP = {}


def deep_paths(tag):
    """Every trade-through minute of each deeper rung's window (scripts/ladder_v5/deep_paths.py)."""
    if tag not in _DEEP:
        _DEEP[tag] = pd.read_pickle(os.path.join(fsim.OUT, f"deep_paths_{tag}.pkl"))
    return _DEEP[tag]


def panel(tag, coins):
    th = pd.read_csv(os.path.join(PANEL, f"panel_{tag}", "thr.csv"))
    tq = dict(zip(th.quarter, th.thr))
    frames = {}
    for c in coins:
        p = os.path.join(PANEL, f"panel_{tag}", f"{c}.parquet")
        if os.path.exists(p):
            frames[c] = pd.read_parquet(p).set_index("ts").pred
    idx = frames[next(iter(frames))].index
    M = np.full((len(idx), len(coins)), -np.inf, dtype=np.float32)
    for j, c in enumerate(coins):
        if c in frames:
            M[:, j] = frames[c].reindex(idx).fillna(-np.inf).to_numpy(np.float32)
    thr = pd.PeriodIndex(idx, freq="Q").astype(str).map(tq).to_numpy(np.float32)
    return idx, M, thr


def adv_table(tag, coins, lo, hi):
    """Trailing 30-day median daily Coinbase USD volume (spot + perp), as of the previous day (sim.daily_stats)."""
    start, end, src = sim.PERIODS[tag]
    idx = pd.date_range(start, end, freq="min", inclusive="left")
    pm = sim.perp_mult()
    out = {}
    for c in coins:
        V = {"spot": sim.load_venue(os.path.join(fsim.ROOT, "data", src, f"{c}.parquet"), idx)}
        if V["spot"] is None:
            continue
        if tag != "early" and c in pm:
            p = sim.load_venue(os.path.join(fsim.ROOT, "data", "cfm", f"{c}.parquet"), idx, pm[c])
            if p is not None:
                V["perp"] = p
        adv, _, _ = sim.daily_stats(V, idx)
        out[c] = adv
    days = pd.date_range(lo, hi, freq="D")
    return pd.DataFrame({c: s.reindex(days) for c, s in out.items()})


def run(P, era, C=250e3, theta=0.5, kappa=0.002, per_trade=0.25, weights=fsim.W0, policy="engine", reserve=0.0,
        size_fn=None, drop_same_minute=False, adv=None, pan=None, trace=None, scale=None, deep_mult=None):
    """Funded order size per tranche row of P (index of P) under the live cash rule; and counters.
    policy: "engine" (deeper rungs only get cash 4-sigma bids leave), "preempt" (a deeper rung may take the hold of
    the lowest-prediction 4-sigma bids), "reserve" (4-sigma bids may hold at most (1 - reserve) of equity).
    size_fn: optional sizing rule m = size_fn(margin, minute index), margin = prediction - threshold; it scales the
    whole ladder of a signal (the 4-sigma hold every minute, and the deeper rungs from the margin at the fill).
    deep_mult: optional {(parent ts, coin): multiplier} for that parent's 6/8-sigma rungs only (0 = not placed)."""
    tag, (lo, hi) = fsim.ERAS[era]
    W = fsim.window(P, lo, hi)
    coins = sorted(W.coin.unique()) if pan is None else pan[3]
    if pan is None:
        idx, M, thr = panel(tag, coins)
    else:
        idx, M, thr, coins = pan
    if adv is None:
        adv = adv_table(tag, coins, lo, hi)
    cj = {c: j for j, c in enumerate(coins)}
    t_lo, t_hi = pd.Timestamp(lo), pd.Timestamp(hi) + pd.Timedelta(days=1)
    i_lo, i_hi = idx.searchsorted(t_lo), idx.searchsorted(t_hi)
    days = adv.index
    wsum = float(sum(weights.values()))
    share = {k: w / wsum for k, w in weights.items()}

    # signal size per (day, coin): min(per_trade x C, kappa x ADV), looked up by minute index
    A_ = adv.reindex(columns=coins).to_numpy(np.float64)
    S_day = np.full(A_.shape, per_trade * C)
    if kappa is not None:
        S_day = np.where(np.isfinite(A_), np.minimum(S_day, kappa * A_), S_day)
    day_of = ((idx.normalize() - days[0]) // pd.Timedelta(days=1)).to_numpy()

    def want_sig(c, t):
        d = int((t.normalize() - days[0]) // pd.Timedelta(days=1))
        return float(S_day[d, cj[c]]) if 0 <= d < len(days) else per_trade * C

    def want_i(j, i):
        d = day_of[i]
        return float(S_day[d, j]) if 0 <= d < len(days) else per_trade * C

    F = W[W.filled].copy()
    par = W[W.k == 4.0]
    F["fill_t"] = F.ts + pd.to_timedelta(F.f_off, unit="m")
    rows_by_parent = {key: g for key, g in W.groupby(["ts", "coin"])}
    order = pd.Series(0.0, index=W.index)
    fill_off = {}                                       # deeper row -> minute offset of its fill (from the parent)
    DP = deep_paths(tag)
    stats = dict(parents=0, parent_unfunded=0, parent_partial=0, deep_placed=0, deep_late=0, deep_never=0,
                 cash_short_minutes=0)
    pos = []            # (release_minute_index, amount)
    deep = {}           # (parent key, k) -> dict(amount, end, fill_i, row)
    pending = []        # (parent key, k, need, end, fill_i or None, row)
    busy = np.zeros(len(coins), dtype=np.int64)      # minute index until which the coin is busy
    pools = {}

    def t2i(t):
        return int(idx.searchsorted(t))

    # parent events in time order
    events = []
    for r in par.itertuples():
        if not r.filled:
            continue
        events.append((t2i(r.ts), r))
    events.sort(key=lambda e: e[0])
    # active minutes: from each parent fill to its window end (deeper rungs) and its 4-sigma exit (busy)
    active = set()
    for i, r in events:
        end = i + (int(r.tp_off) if r.tp_off >= 0 else sim.H)
        active.update(range(i, min(i + sim.H + 1, len(idx))))
    act = sorted(active)
    ev_at = {}
    for i, r in events:
        ev_at.setdefault(i, []).append(r)

    def add_position(i, f, r):
        """A filled tranche holds cash until its take-profit trades (the part the take-profit buyers absorb) and
        otherwise until the 60-minute exit (fsim's release rule)."""
        if r.tp_off >= 0:
            tp = min(f, theta * r.tp_spot)
            if tp > 0:
                pos.append((i + int(r.tp_off), tp))
            f -= tp
        if f > 0:
            pos.append((i + sim.H, f))

    def positions(i):
        return sum(a for (e, a) in pos if e > i)

    def deep_held(i):
        return sum(d["amount"] for d in deep.values() if d["end"] > i and d.get("filled_at") is None)

    def alloc4(i, budget, exclude=None):
        """4-sigma holds at minute i, prediction order. Returns {coin: hold incl. fee}."""
        p = M[i]
        th = thr[i]
        out, left = {}, budget
        cand = [j for j in np.argsort(-p) if p[j] > th and busy[j] <= i and (exclude is None or j != exclude)]
        for j in cand:
            c = coins[j]
            need = want_i(j, i) * share[4.0] * (1 + FEE_M)
            if size_fn is not None:
                need *= size_fn(float(p[j] - th), i)
                if need <= 0:
                    out[c] = 0.0
                    continue
            if policy == "reserve":
                cap4 = (1 - reserve) * C - sum(out.values())
                need_ok = min(need, max(cap4, 0.0))
            else:
                need_ok = need
            if need_ok >= need - 1e-9 and need <= left:
                out[c], left = need, left - need
            elif min(left, need_ok) >= 0.5 * need:
                out[c], left = 0.999 * min(left, need_ok), left - 0.999 * min(left, need_ok)
            else:
                out[c] = 0.0
        return out

    def place(i, items, free, A):
        """Place deeper rungs in order from `free`; returns (free, the rungs still waiting). With policy "preempt" a
        rung short of cash takes the holds of the lowest-prediction 4-sigma bids in A (they are cancelled)."""
        keep = []
        for (key, k, need, end, fi, rix) in items:
            if (key, k) in deep:
                continue
            if policy == "preempt" and free < need:
                for c_ in sorted(A, key=lambda x: M[i][cj[x]]):
                    if free >= need:
                        break
                    if A[c_] > 0:
                        free += A[c_]
                        A[c_] = 0.0
            if free >= need:
                amt = need
            elif free >= 0.5 * need:
                amt = 0.999 * free
            else:
                stats["cash_short_minutes"] += 1
                keep.append((key, k, need, end, fi, rix))
                continue
            free -= amt
            # it fills at the first trade-through of its level at or after this minute, within its window
            D = DP.get(rix)
            i0 = fi
            fill_i = None
            if D is not None and len(D):
                later = D.off.to_numpy()[i0 + D.off.to_numpy() >= i]
                if len(later) and i0 + int(later[0]) < end:
                    fill_i = i0 + int(later[0])
            deep[(key, k)] = dict(amount=amt, end=end, fill_i=fill_i, row=rix, placed=i)
            stats["deep_placed"] += 1
            if D is not None and len(D) and i0 + int(D.off.iloc[0]) < i:
                stats["deep_late"] += 1                 # placed after its first trade-through
            order[rix] = amt / (1 + FEE_M)
            if fill_i is not None:
                fill_off[rix] = fill_i - i0
        return free, keep

    A_prev, last_i = {}, None
    for i in act:
        # 1. exits, take-profits and closed deeper-rung windows release cash
        pos[:] = [(e, a) for (e, a) in pos if e > i]
        for key in [k for k, d in deep.items() if d["end"] <= i and d.get("filled_at") is None]:
            deep.pop(key)
        pending[:] = [x for x in pending if x[3] > i]
        # 2. deeper rungs waiting for cash, before the 4-sigma bids are re-allocated (engine: _manage, then _allocate);
        #    the 4-sigma bids resting into this minute still hold their cash
        if last_i != i - 1:
            A_prev = alloc4(i - 1, C - positions(i) - deep_held(i))
        free = C - positions(i) - deep_held(i) - sum(A_prev.values())
        free, rest = place(i, pending, free, A_prev)
        pending[:] = rest
        # 3. 4-sigma bids for this minute, prediction order, from what positions and deeper rungs leave
        A = alloc4(i, C - positions(i) - deep_held(i))
        # 4. parent fills this minute
        new_rungs = []
        for r in ev_at.get(i, []):
            c = r.coin
            j = cj[c]
            stats["parents"] += 1
            S = want_sig(c, r.ts)
            m = 1.0 if size_fn is None else float(size_fn(float(M[i, j] - thr[i]), i))
            want4 = S * share[4.0] * m
            held = A.get(c, 0.0)
            if busy[j] > i or held <= 0:
                stats["parent_unfunded"] += 1
                continue
            o = min(want4, held / (1 + FEE_M))
            if o < 0.999 * want4:
                stats["parent_partial"] += 1
            order[r.Index] = o
            f = min(o, theta * r.in_spot)
            key = (r.ts, c)
            add_position(i, f, r)
            busy[j] = i + (int(r.tp_off) if r.tp_off >= 0 else sim.H) + 1
            A.pop(c, None)                              # its hold became the position
            end = i + (int(r.tp_off) if r.tp_off >= 0 else sim.H)
            for k in (6.0, 8.0):
                if k not in share:
                    continue
                g = rows_by_parent[key]
                rr = g[g.k == k]
                if not len(rr):
                    continue
                row = rr.iloc[0]
                md = 1.0 if deep_mult is None else float(deep_mult.get(key, 1.0))
                if md <= 0:
                    continue
                need = S * share[k] * m * md * (1 + FEE_M)
                new_rungs.append((key, k, need, end, i, row.name))     # i: the parent's fill minute
        if new_rungs:
            if drop_same_minute:
                pending.extend(new_rungs)               # minute bot: placed at the next minute's step
            else:                                       # 1-second detection: placed at once from what is free
                free = C - positions(i) - deep_held(i) - sum(A.values())
                free, rest = place(i, new_rungs, free, A)
                pending.extend(rest)
        # 5. deeper fills this minute: the hold becomes a position
        for (key, k), d in list(deep.items()):
            if d.get("filled_at") is None and d["fill_i"] is not None and d["fill_i"] == i and order[d["row"]] > 0:
                rr = DP[d["row"]]
                rr = rr[rr.off == fill_off[d["row"]]].iloc[0]
                sc = 1.0 if scale is None else scale.get(W.at[d["row"], "coin"], 1.0)
                rr = rr.copy()
                rr["in_spot"], rr["tp_spot"] = rr.in_spot * sc, rr.tp_spot * sc
                f = min(order[d["row"]], theta * rr.in_spot)
                add_position(i, f, rr)
                d["filled_at"] = i
        A_prev, last_i = A, i
        if trace is not None:
            trace.append(dict(t=idx[i], positions=positions(i), deep=deep_held(i), hold4=sum(A.values()),
                              n4=sum(1 for v in A.values() if v > 0), pending=len(pending)))
    stats["deep_never"] = int(len([1 for r in W[(W.k > 4) & W.filled].itertuples() if r.Index not in fill_off]))
    stats["deep_filled"] = len(fill_off)
    return order, stats, fill_off


def with_live_fills(W, foff, tag, scale=None):
    """The deeper rungs as the live book fills them: at the first trade-through after the rung was placed (foff), with
    the research quantities from that minute; a rung with no such minute does not fill."""
    W = W.copy()
    DP = deep_paths(tag)
    deep = W.index[W.k > 4.0]
    W.loc[deep, "filled"] = False
    cols = ["f_off", "in_spot", "scan_off", "tp_off", "tp_spot", "g60", "g_tp"]
    for rix, off in foff.items():
        D = DP[rix]
        d = D[D.off == off].iloc[0]
        f = 1.0 if scale is None else scale.get(W.at[rix, "coin"], 1.0)
        W.loc[rix, cols] = [off, d.in_spot * f, d.scan_off, d.tp_off, d.tp_spot * f, d.g60, d.g_tp]
        W.at[rix, "filled"] = True
        W.at[rix, "tp_hit"] = bool(d.tp_off >= 0)
    W["filled"] = W["filled"].astype(bool)
    return W


def book(P, era, theta=0.5, C=250e3, policy="engine", reserve=0.0, size_fn=None, today=False, cost_mult=1.0,
         adv=None, pan=None, deep_mult=None, **kw):
    """Daily returns (poll1s blend) of the hold-aware book. Sizes from run(); fills, costs, P&L from fsim."""
    tag, (lo, hi) = fsim.ERAS[era]
    W = fsim.window(P, lo, hi)
    if adv is None:
        adv = adv_table(tag, sorted(W.coin.unique()), lo, hi)
    sc = None
    if today:
        sc = fsim.today_scale(P, lo, hi)
        W = fsim.apply_scale(W, sc)
        adv = adv.copy()
        for c in adv.columns:
            adv[c] = adv[c] * sc.get(c, 1.0)
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    kw.setdefault("hs_bp", fsim.HS_BP * cost_mult)
    kw.setdefault("impact_y", fsim.IMPACT_Y * cost_mult)
    idx_d = pd.date_range(lo, hi, freq="D")
    out = {}
    for name, drop in (("minute", True), ("instant", False)):
        o, st, foff = run(W, era, C=C, theta=theta, policy=policy, reserve=reserve, size_fn=size_fn,
                          drop_same_minute=drop, adv=adv, pan=pan, scale=sc, deep_mult=deep_mult)
        Wm = with_live_fills(W, foff, tag, sc)
        want = np.minimum(0.25 * C, 0.002 * Wm.adv.fillna(0.0)) * Wm.k.map({4.0: 1 / 3, 6.0: 1 / 3, 8.0: 1 / 3})
        Wm["mult"] = np.where(want > 0, o.reindex(Wm.index).fillna(0.0) / want, 0.0)
        Q, d, info = fsim.evaluate(Wm, theta=theta, C=C, days=days, drop_same_minute=drop, **kw)
        out[name] = (Q, d.reindex(idx_d, fill_value=0.0) / C, info, st)
    s = fsim.lat_share(era, theta)
    d1 = out["minute"][1] + s * (out["instant"][1] - out["minute"][1])
    return d1, out
