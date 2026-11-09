#!/usr/bin/env python3
"""Explore v1: generalized fast evaluator for R2-08 spot-ladder variants (reports/explore/prereg.md).

It follows scripts/wick1m/sim.py evaluate (spot venue only, as the spot bot; rungs.py settings by default) and adds the
variant dimensions:
  rungs    {depth: weight}; depths from 4, 5, 6, 7, 8, 9, 10, 12 sigma; the 4-sigma parent may have weight 0
           ("trigger-only": deeper bids go out when the 4-sigma level trades, with no 4-sigma order)
  tp       take-profit ladder per rung: [(fraction of the rung's dislocation, share of the rung), ...], fractions from
           0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0; a dict {depth: ladder} or one ladder for every rung
  H        minutes to the market exit (<= 60); deeper bids rest at most H minutes after the parent
  cancel   "parent_tp" (deeper bids are cancelled when the parent's lowest take-profit trades) or "none"
  r_min    keep a signal only if pred / thr >= r_min (a stricter AI threshold)
  adv_floor  skip signals whose coin trades less than this ADV (USD)
  slots    at most this many open parents at once (None = no limit)
  kappa, per_trade, cash_cap, theta   size cap (share of ADV), size (share of capital), positions cap, capture share
Round 3 additions (None = off, the round 1-2 behaviour):
  cancel_f  cancel the deeper bids when the parent's price recovers this fraction of its dislocation (0.3-1.0),
           instead of at the parent's lowest take-profit (cancel "parent_tp" only)
  bid_to   deeper bids rest at most this many minutes after the signal (bid timeout)
  sig_min  skip signals whose sigma (the AI's volatility unit) is below this many basis points
With the defaults it reproduces rungs.run on spot-only capacity (W0 / W2), checked in reports/explore/parity.txt.
"""
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
import sim  # noqa: E402
from edge import book as edge_book  # noqa: E402

ERAS = {"selection": ("main", sim.SEL), "check": ("main", sim.CHK), "y2022_23": ("early", sim.EARLY)}
H_MAX = 60
BASE = dict(rungs={4.0: 1.0, 6.0: 1.0, 8.0: 1.0}, tp=[(0.6, 1.0)], H=60, cancel="parent_tp", r_min=1.0, adv_floor=0.0,
            slots=None, kappa=0.002, per_trade=0.25, cash_cap=1.0, theta=0.5, cancel_f=None, bid_to=None,
            sig_min=None)


def ftag(f):
    return f"{int(round(f * 100)):03d}"


_P = {}


def data(tag):
    if tag not in _P:
        P = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", f"pre_x_{tag}.pkl"))
        _P[tag] = P
    return _P[tag]


def norm_spec(spec):
    s = dict(BASE)
    s.update(spec or {})
    s["rungs"] = {float(k): float(v) for k, v in s["rungs"].items()}
    tp = s["tp"]
    if isinstance(tp, dict):
        s["tp"] = {float(k): [(float(f), float(w)) for f, w in v] for k, v in tp.items()}
    else:
        s["tp"] = {k: [(float(f), float(w)) for f, w in tp] for k in s["rungs"]}
    for k in s["rungs"]:
        s["tp"].setdefault(k, s["tp"].get(4.0, [(0.6, 1.0)]))
        tot = sum(w for _, w in s["tp"][k])
        s["tp"][k] = sorted([(f, w / tot) for f, w in s["tp"][k]])
    return s


def evaluate(spec, era, C, want_equity=False):
    """Daily returns (P&L / C on the era's days), the sub-tranche table and info."""
    s = norm_spec(spec)
    tag, (lo, hi) = ERAS[era]
    P = data(tag)
    P = P[(P.ts >= lo) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    H, theta = int(s["H"]), float(s["theta"])
    par = P[P.k == 4.0].set_index(["ts", "coin"])
    ok = (par.pred / par.thr >= s["r_min"] - 1e-12) & (par.adv.fillna(0.0) >= s["adv_floor"])
    if s.get("sig_min") is not None:
        ok &= par.sig * 1e4 >= s["sig_min"] - 1e-9
    keep = set(par.index[ok])
    ptp = s["tp"].get(4.0, [(0.6, 1.0)])
    f_tp = min(f for f, _ in ptp)

    def close_at(f):
        c = par[f"tpo_{ftag(f)}"].where(par[f"tpo_{ftag(f)}"] >= 1, H).clip(upper=H)
        return c.where(c <= H, H)

    pclose = close_at(f_tp)                                       # the parent's first take-profit (slots)
    pcancel = pclose if s.get("cancel_f") is None else close_at(float(s["cancel_f"]))
    wsum = sum(s["rungs"].values())
    rows = []
    for k, w in s["rungs"].items():
        R = P[(P.k == k) & P.filled]
        R = R[[key in keep for key in zip(R.ts, R.coin)]]
        if k != 4.0:
            if s.get("mode", "minute") == "minute":
                R = R[R.f_off >= 1]                               # bot-like: no deeper fill in the parent's minute
            if s["cancel"] == "parent_tp":
                pc = pcancel.reindex(pd.MultiIndex.from_arrays([R.ts, R.coin])).to_numpy()
                R = R[R.f_off.to_numpy() < pc]
            else:
                R = R[R.f_off < H]
            if s.get("bid_to") is not None:
                R = R[R.f_off < s["bid_to"]]
        if w <= 0 and k != 4.0:
            continue
        for f, sh in s["tp"][k]:
            x = R[["ts", "coin", "k", "f_off", "scan_off", "in_spot", "adv", "vol_d", "g60", "path"]].copy()
            x["tpf"], x["share"] = f, (w / wsum) * sh
            x["tp_off"] = R[f"tpo_{ftag(f)}"].to_numpy()
            x["g_tp"] = R[f"gtp_{ftag(f)}"].to_numpy()
            x["tp_cap"] = R[f"tpv_{ftag(f)}"].to_numpy()
            rows.append(x)
    Q = pd.concat(rows, ignore_index=True)
    Q["fill_t"] = Q.ts + pd.to_timedelta(Q.f_off, unit="m")
    Q = Q.sort_values(["fill_t", "coin", "k", "ts", "tpf"], kind="mergesort").reset_index(drop=True)
    want_tot = np.minimum(s["per_trade"] * C, s["kappa"] * Q.adv.fillna(0.0).to_numpy())
    want = want_tot * Q.share.to_numpy()
    cap_in = theta * Q.in_spot.to_numpy()
    cap_tp = theta * Q.tp_cap.to_numpy()
    tp_off = Q.tp_off.to_numpy().astype(int)
    tp_ok = (tp_off >= 1) & (tp_off <= H)
    f_off, scan_off = Q.f_off.to_numpy(), Q.scan_off.to_numpy()
    kk, ft = Q.k.to_numpy(), Q.fill_t.to_numpy()
    keys = list(zip(Q.ts, Q.coin))
    n = len(Q)
    fill, tpf_ = np.zeros(n), np.zeros(n)
    pool, used, used_tp, scan, skip = {}, {}, {}, {}, set()
    releases, open_amt, open_par = [], 0.0, []
    pclose_map = pclose.to_dict()
    i = 0
    while i < n:                                                  # one rung (all its take-profit sub-tranches) at a time
        j = i + 1
        while j < n and keys[j] == keys[i] and kk[j] == kk[i] and ft[j] == ft[i]:
            j += 1
        while releases and releases[0][0] <= ft[i]:
            open_amt -= releases.pop(0)[1]
        key = keys[i]
        if kk[i] == 4.0:
            if s["slots"] is not None:
                open_par = [t for t in open_par if t > ft[i]]
                if len(open_par) >= s["slots"]:
                    skip.add(key)
                else:
                    open_par.append(ft[i] + np.timedelta64(int(pclose_map.get(key, H)), "m"))
            pool[key], used[key], used_tp[key], scan[key] = cap_in[i], 0.0, 0.0, scan_off[i]
            cap = cap_in[i]
        elif key in pool and f_off[i] <= scan[key]:
            cap = min(cap_in[i], max(0.0, pool[key] - used[key]))
        else:
            cap = cap_in[i]
        if key in skip:
            i = j
            continue
        w_rung = want[i:j].sum()
        total = min(w_rung, cap)
        room = s["cash_cap"] * C - open_amt
        if total > room:
            total = room if room > 0.1 * w_rung else 0.0
        if total <= 0 or cap <= 0:
            i = j
            continue
        if key in used:
            used[key] += total
        for r in range(i, j):
            fr = total * want[r] / w_rung
            fill[r] = fr
            if tp_ok[r]:
                avail = cap_tp[r] - used_tp.get(key, 0.0)
                tpf_[r] = max(0.0, min(fr, avail))
                if key in used_tp:
                    used_tp[key] += tpf_[r]
                if tpf_[r] > 0:
                    releases.append((ft[r] + np.timedelta64(int(tp_off[r]), "m"), tpf_[r]))
            releases.append((ft[r] + np.timedelta64(H, "m"), fr - tpf_[r]))
        open_amt += total
        releases.sort(key=lambda z: z[0])
        i = j
    mk, tk = sim.tier(2 * fill.sum() / days * 30, sim.SPOT_TIERS)
    taker = tk + sim.SPOT_HS_BP / 1e4
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    rem = fill - tpf_
    grp = pd.Series(rem).groupby([Q.ts.to_numpy(), Q.coin.to_numpy(), kk]).transform("sum").to_numpy()
    imp = sim.IMPACT_Y * vol_d * np.sqrt(np.maximum(grp, 0.0) / adv)
    if H == H_MAX:
        gH = Q.g60.to_numpy() / 1e4
    else:
        gH = np.array([p[H] for p in Q.path], dtype=np.float64)
    pnl_tp = tpf_ * (Q.g_tp.to_numpy() / 1e4 - mk)
    pnl_rem = rem * (gH - taker - imp)
    entry = fill * mk
    Q["fill"], Q["tp_fill"], Q["pnl"] = fill, tpf_, pnl_tp + pnl_rem - entry
    Q["pnl_tp"], Q["pnl_rem"], Q["entry_cost"] = pnl_tp, pnl_rem, entry
    tp_t = Q.fill_t + pd.to_timedelta(np.where(tp_ok, tp_off, H), unit="m")
    ex_t = Q.fill_t + pd.Timedelta(minutes=H)
    daily = pd.concat([pd.Series(pnl_tp - entry, index=tp_t.dt.floor("D").to_numpy()),
                       pd.Series(pnl_rem, index=ex_t.dt.floor("D").to_numpy())]).groupby(level=0).sum()
    idx = pd.date_range(lo, hi, freq="D")
    d = daily.reindex(idx, fill_value=0.0) / C
    expo = float(np.sum(tpf_ * np.where(tp_ok, tp_off, H)) + np.sum(rem * H))
    info = dict(maker_bp=mk * 1e4, taker_bp=tk * 1e4, v30=2 * fill.sum() / days * 30, exposure=expo,
                fills=int((fill > 0).sum()), fill_usd=float(fill.sum()), signals=len(keep))
    if want_equity:
        info["equity"] = mtm_equity(Q, tp_t, ex_t, H)
    return d, Q, info


def mtm_equity(Q, tp_t, ex_t, H):
    """Minute-level cumulative P&L as sim.mtm_equity: realized at exits plus open positions marked to the close path."""
    q = Q[Q.fill > 0]
    recs = []
    for r in q.itertuples():
        path = np.exp(r.path.astype(np.float64)[:H + 1]) - 1.0
        m = np.arange(len(path))
        open_ = np.where((r.tp_off >= 1) & (r.tp_off <= H) & (m >= r.tp_off), r.fill - r.tp_fill, r.fill)
        u = open_ * path - r.entry_cost
        u[-1] = 0.0
        recs.append(pd.DataFrame({"t": r.fill_t + pd.to_timedelta(m, unit="m"), "u": u}))
    U = pd.concat(recs).groupby("t").u.sum() if recs else pd.Series(dtype=float)
    R = pd.concat([pd.Series(q.pnl_tp.to_numpy(), index=tp_t[q.index].to_numpy()),
                   pd.Series((q.pnl_rem - q.entry_cost).to_numpy(), index=ex_t[q.index].to_numpy())])
    R = R.groupby(level=0).sum()
    t_all = U.index.union(R.index)
    return R.reindex(t_all, fill_value=0.0).cumsum() + U.reindex(t_all, fill_value=0.0)


_LAT = {}


def lat_share(era, C):
    """Share of the minute-to-instant gap the live 1-second bot captures (reports/wick_v4/latency_value.csv, theta 0.5):
    (poll1s - minute) / (research - minute) return."""
    if not _LAT:
        L = pd.read_csv(os.path.join(ROOT, "reports", "wick_v4", "latency_value.csv"))
        for r in L[L.theta == 0.5].itertuples():
            e = {"selection": "selection", "check": "check", "fresh_2022_23": "y2022_23"}[r.era]
            _LAT[(e, float(r.capital))] = (r.poll1s_ret - r.minute_bot_ret) / (r.research_ret - r.minute_bot_ret)
    return _LAT[(era, float(C))]


def blended(spec, era, C):
    """Live-like daily returns: minute + s x (instant - minute); returns (blend, minute, instant, info_minute)."""
    dm, Qm, im = evaluate(dict(spec, mode="minute"), era, C)
    di, Qi, ii = evaluate(dict(spec, mode="instant"), era, C)
    s = lat_share(era, C)
    return dm + s * (di - dm), dm, di, im, ii


def stats(d, era):
    lo, hi = ERAS[era][1]
    idx = pd.date_range(lo, hi, freq="D")
    r = d.reindex(idx, fill_value=0.0).to_numpy()
    ex = r - edge_book.rf_daily(idx).to_numpy()
    yrs = len(idx) / 365.25
    sd = ex.std(ddof=1)
    eq = np.cumprod(1 + r)
    return dict(ret_yr=float(r.sum() / yrs), sharpe=float(ex.mean() / sd * math.sqrt(365)) if sd > 0 else float("nan"),
                maxdd=float(np.min(eq / np.maximum.accumulate(eq) - 1)), worst=float(r.min()))
