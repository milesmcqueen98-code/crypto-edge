#!/usr/bin/env python3
"""Ladder v5: the frozen simulator, cost model and dataset for every candidate (reports/ladder_v5_prereg.md).

It is scripts/wick1m/sim.py's evaluate (the research simulator behind R2-08's $1M rules), copied with hooks that
default to the incumbent, plus the incumbent's book definition from scripts/hunt/incumbent.py:
  - Coinbase spot only (perp and Bitstamp fill capacity removed), the 4/6/8-sigma ladder in thirds, kappa 0.2% of the
    trailing 30-day median daily USD volume, 25% of capital per signal, every AI signal, positions <= 100% of capital;
  - fills: one-tick trade-through, size <= theta x the USD volume traded below the bid (sellers shared within a parent);
  - exits: post-only take-profit at 60% of each rung's dislocation (maker fee), else market at 60 minutes (taker fee,
    half-spread, square-root impact);
  - fees: Coinbase's US spot tiers from the book's own 30-day volume;
  - the live bot reads its fills every second: poll1s = minute bound + s x (instant bound - minute bound), with s the
    share measured at $250K in wick v4 (reports/wick_v4/latency_value.csv), per era and theta.
Hooks (all default to the incumbent): per-row size multiplier `mult`; per-row overrides of the remainder's exit gain
and cost (`g60`, `rem_cost`, `rem_imp`); the take-profit leg's fee (`tp_cost`); half-spread and impact constants;
per-coin volume scaling (today's volumes); the fee table. Parity with sim.evaluate: python scripts/ladder_v5/fsim.py.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import sim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "ladder_v5")
W0 = {4.0: 1, 6.0: 1, 8.0: 1}
ERAS = {"sel": ("main", sim.SEL), "chk": ("main", sim.CHK), "early": ("early", sim.EARLY)}
ERA_LAT = {"sel": "selection", "chk": "check", "early": "fresh_2022_23"}
HS_BP, IMPACT_Y = sim.SPOT_HS_BP, sim.IMPACT_Y
# today's trailing 30-day median daily Coinbase USD volume (spot + perp), $M, logged by the paper bot on 2026-11-07
LIVE_ADV_MUSD = {"ETH": 286.8, "SOL": 75.1, "XRP": 103.8, "DOGE": 7.7, "LTC": 7.3, "LINK": 9.2, "BCH": 3.5, "SUI": 17.0,
                 "XLM": 10.4, "HBAR": 7.8, "NEAR": 83.8, "AAVE": 4.2, "HYPE": 28.0, "ENA": 10.5, "PEPE": 5.9,
                 "ONDO": 7.3, "ZEC": 144.8}


def load(tag):
    """The frozen dataset: R2-08's out-of-sample trades and ladder tranches (scripts/wick1m/sim.py precompute, no
    Bitstamp), with the perp venue's capacity removed (the spot bot cannot fill there)."""
    path = os.path.join(ROOT, "reports", "wick1m", f"pre_hunt_{tag}.pkl")
    if not os.path.exists(path):
        sim.precompute(tag, bitstamp=False, out_tag=f"hunt_{tag}")
    P = pd.read_pickle(path)
    P["in_perp_raw"], P["tp_perp_raw"] = P["in_perp"], P["tp_perp"]
    P["in_perp"], P["tp_perp"] = 0.0, 0.0
    return P


def window(P, lo, hi):
    return P[(P.ts >= lo) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]


def today_scale(P, lo, hi):
    """Per-coin volume factor for 'today's volumes': today's ADV / the era's median ADV, capped at 1 (stress only
    downward). Scales the size base (adv) and the fill and take-profit capacity (in_*, tp_*)."""
    W = window(P, lo, hi)
    med = W[W.k == 4.0].groupby("coin").adv.median() / 1e6
    return {c: float(min(1.0, LIVE_ADV_MUSD.get(c, np.inf) / m)) for c, m in med.items() if m > 0}


def apply_scale(P, scale):
    Q = P.copy()
    f = Q.coin.map(scale).fillna(1.0).to_numpy()
    for col in ("adv", "in_spot", "tp_spot", "in_perp", "tp_perp", "in_bitstamp", "tp_bitstamp"):
        if col in Q:
            Q[col] = Q[col].to_numpy() * f
    return Q


def evaluate(P, kappa=0.002, theta=0.5, C=250e3, gross_cap=1.0, per_trade=0.25, days=None, tiers=sim.SPOT_TIERS,
             drop_same_minute=False, weights=W0, hs_bp=HS_BP, impact_y=IMPACT_Y, venues=("spot", "perp")):
    """sim.evaluate (exit E0, trade_list 'all', ladder by weights) with hooks. Optional columns of P:
    mult (size multiplier, default 1), g60 override is just the g60 column, rem_cost (fraction charged on the
    remainder instead of taker + half-spread), rem_imp (0/1: square-root impact on the remainder), tp_cost (fraction
    charged on the take-profit leg instead of the maker fee). Returns (Q, daily P&L by exit day, info)."""
    Q = P[P.filled].copy()
    Q = Q[Q.k.isin(list(weights))]
    if drop_same_minute:
        Q = Q[(Q.k == sim.LADDER[0]) | (Q.f_off > 0)]
    venues = list(venues)
    Q["fill_t"] = Q.ts + pd.to_timedelta(Q.f_off, unit="m")
    Q = Q.sort_values(["fill_t", "coin", "k"]).reset_index(drop=True)
    want_tot = np.full(len(Q), per_trade * C)
    if kappa is not None:
        want_tot = np.minimum(want_tot, kappa * Q.adv.fillna(0.0).to_numpy())
    wsum = float(sum(weights.values()))
    want = want_tot * Q.k.map({k: w / wsum for k, w in weights.items()}).to_numpy()
    if "mult" in Q:
        want = want * Q["mult"].fillna(1.0).to_numpy()
    cap_in = {v: theta * Q[f"in_{v}"].to_numpy() for v in venues}
    cap_tp = {v: theta * Q[f"tp_{v}"].to_numpy() for v in venues}
    fill_v = {v: np.zeros(len(Q)) for v in venues}
    tp_v = {v: np.zeros(len(Q)) for v in venues}
    pool, used, used_tp, scan = {}, {}, {}, {}
    ft = Q.fill_t.to_numpy()
    tp_off, f_off, scan_off = Q.tp_off.to_numpy(), Q.f_off.to_numpy(), Q.scan_off.to_numpy()
    releases, open_amt = [], 0.0
    keys = list(zip(Q.ts, Q.coin))
    kk = Q.k.to_numpy()
    for i in range(len(Q)):
        while releases and releases[0][0] <= ft[i]:
            open_amt -= releases.pop(0)[1]
        key = keys[i]
        caps = np.array([cap_in[v][i] for v in venues])
        if kk[i] == sim.LADDER[0]:
            pool[key] = {v: cap_in[v][i] for v in venues}
            used[key] = {v: 0.0 for v in venues}
            used_tp[key] = {v: 0.0 for v in venues}
            scan[key] = scan_off[i]
        elif key in pool and f_off[i] <= scan[key]:
            caps = np.array([min(cap_in[v][i], max(0.0, pool[key][v] - used[key][v])) for v in venues])
        tot_cap = caps.sum()
        total = min(want[i], tot_cap)
        room = gross_cap * C - open_amt if gross_cap is not None else np.inf
        if total > room:
            total = room if room > 0.1 * want[i] else 0.0
        if total <= 0 or tot_cap <= 0:
            continue
        tpa = 0.0
        for j, v in enumerate(venues):
            f = total * caps[j] / tot_cap
            fill_v[v][i] = f
            if key in used:
                used[key][v] += f
            if tp_off[i] >= 0:
                avail = cap_tp[v][i] - (used_tp[key][v] if key in used_tp else 0.0)
                tp_v[v][i] = max(0.0, min(f, avail))
                if key in used_tp:
                    used_tp[key][v] += tp_v[v][i]
                tpa += tp_v[v][i]
        open_amt += total
        if tpa > 0:
            releases.append((ft[i] + np.timedelta64(int(tp_off[i]), "m"), tpa))
        releases.append((ft[i] + np.timedelta64(sim.H, "m"), total - tpa))
        releases.sort(key=lambda r: r[0])
    fill = sum(fill_v.values())
    tpf = sum(tp_v.values())
    rem_v = {v: fill_v[v] - tp_v[v] for v in venues}
    span = days or max(1.0, (Q.ts.max() - Q.ts.min()).days)
    mk, tk = sim.tier(2 * fill_v["spot"].sum() / span * 30, tiers)
    fee_perp, hs_perp = sim.perp_cost()
    fp = Q.coin.map(fee_perp).fillna(5.0).to_numpy() / 1e4
    hp = Q.coin.map(hs_perp).fillna(5.0).to_numpy() / 1e4
    maker = {"spot": np.full(len(Q), mk), "perp": fp + 1e-4}
    maker_x = {"spot": np.full(len(Q), mk), "perp": fp}
    taker = {"spot": np.full(len(Q), tk + hs_bp / 1e4), "perp": fp + hp}
    if "tp_cost" in Q:
        maker_x["spot"] = Q.tp_cost.fillna(mk).to_numpy()
    if "rem_cost" in Q:
        taker["spot"] = Q.rem_cost.fillna(tk + hs_bp / 1e4).to_numpy()
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    rem = fill - tpf
    imp = impact_y * vol_d * np.sqrt(np.maximum(rem, 0.0) / adv)
    if "rem_imp" in Q:
        imp = imp * Q.rem_imp.fillna(1.0).to_numpy()
    g_tp, g60 = Q.g_tp.to_numpy() / 1e4, Q.g60.to_numpy() / 1e4
    pnl_tp = sum(tp_v[v] * (g_tp - maker_x[v]) for v in venues)
    pnl_rem = sum(rem_v[v] * (g60 - taker[v] - imp) for v in venues)
    entry = sum(fill_v[v] * maker[v] for v in venues)
    Q["fill"], Q["tp_fill"], Q["pnl_tp"], Q["pnl_rem"], Q["entry_cost"] = fill, tpf, pnl_tp, pnl_rem, entry
    Q["pnl"] = pnl_tp + pnl_rem - entry
    Q["want"] = want
    # decomposition (USD): gross price gain, maker fees (entry + take-profit), taker fee, half-spread, impact
    Q["gross"] = tpf * g_tp + rem * g60
    Q["fee_maker"] = entry + sum(tp_v[v] * maker_x[v] for v in venues)
    Q["fee_taker"] = sum(rem_v[v] * (taker[v] - (hs_bp / 1e4 if v == "spot" else hp)) for v in venues)
    Q["cost_hs"] = rem_v["spot"] * (hs_bp / 1e4) + (rem_v["perp"] * hp if "perp" in rem_v else 0.0)
    Q["cost_imp"] = rem * imp
    tp_t = Q.fill_t + pd.to_timedelta(np.where(tp_off >= 0, tp_off, sim.H), unit="m")
    ex_t = Q.fill_t + pd.Timedelta(minutes=sim.H)
    Q["tp_t"], Q["ex_t"] = tp_t, ex_t
    daily = pd.concat([pd.Series(pnl_tp - entry, index=tp_t.dt.floor("D").to_numpy()),
                       pd.Series(pnl_rem, index=ex_t.dt.floor("D").to_numpy())]).groupby(level=0).sum()
    info = dict(v30=2 * fill.sum() / span * 30, maker_bp=mk * 1e4, taker_bp=tk * 1e4)
    return Q, daily, info


def lat_share(era, theta):
    lat = pd.read_csv(os.path.join(ROOT, "reports", "wick_v4", "latency_value.csv"))
    th = theta if theta in (0.5, 0.25) else 0.5                 # other capture shares use theta 0.5's share
    r = lat[(lat.era == ERA_LAT[era]) & (lat.capital == 250e3) & (lat.theta == th)].iloc[0]
    return float((r.poll1s_ret - r.minute_bot_ret) / (r.research_ret - r.minute_bot_ret))


def book(P, era, theta=0.5, C=250e3, today=False, cost_mult=1.0, **kw):
    """Daily returns on capital of the live bot (poll1s blend) for one era. today=True: today's volumes;
    cost_mult: multiplies the unverified costs (half-spread and impact). Returns (daily poll1s, detail dict)."""
    lo, hi = ERAS[era][1]
    W = window(P, lo, hi)
    if today:
        W = apply_scale(W, today_scale(P, lo, hi))
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    kw.setdefault("hs_bp", HS_BP * cost_mult)
    kw.setdefault("impact_y", IMPACT_Y * cost_mult)
    idx = pd.date_range(lo, hi, freq="D")
    out = {}
    for name, drop in (("minute", True), ("instant", False)):
        Q, d, info = evaluate(W, theta=theta, C=C, days=days, drop_same_minute=drop, **kw)
        out[name] = (Q, d.reindex(idx, fill_value=0.0) / C, info)
    s = lat_share(era, theta)
    d1 = out["minute"][1] + s * (out["instant"][1] - out["minute"][1])
    return d1, out


def nw_t(d, lags=5):
    d = np.asarray(d, float)
    n = len(d)
    m = d.mean()
    x = d - m
    g = [np.dot(x[k:], x[:n - k]) / n for k in range(lags + 1)]
    var = g[0] + 2 * sum((1 - k / (lags + 1)) * g[k] for k in range(1, lags + 1))
    return m / np.sqrt(var / n) if var > 0 else np.nan


def stats(d, C, era):
    lo, hi = ERAS[era][1]
    st = sim.period_stats(d * C, C, lo, hi)
    return {k: st.get(k) for k in ("ret_yr", "sharpe", "sharpe_raw", "maxdd", "dollars_yr", "top3_share")}


def _parity():
    """The hooks at their defaults reproduce sim.evaluate exactly (incumbent definition of scripts/hunt)."""
    import incumbent as inc
    worst = 0.0
    for era, (tag, (lo, hi)) in ERAS.items():
        P0 = inc.load(tag)
        P1 = load(tag)
        for theta in (0.5, 0.25):
            for C in (250e3, 1e6):
                for drop in (True, False):
                    a, _, _ = inc.run(P0, lo, hi, theta, C, drop)
                    W = window(P1, lo, hi)
                    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
                    _, d, _ = evaluate(W, theta=theta, C=C, days=days, drop_same_minute=drop)
                    b = d.reindex(a.index, fill_value=0.0) / C
                    worst = max(worst, float(np.abs(a - b).max()))
    print(f"parity with sim.evaluate (scripts/hunt/incumbent.py): max daily difference {worst:.2e}")
    return worst


if __name__ == "__main__":
    _parity()
