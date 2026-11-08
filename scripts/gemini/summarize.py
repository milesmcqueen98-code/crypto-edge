#!/usr/bin/env python3
"""Gemini venue test (reports/gemini_prereg.md), step 3: sizing, fees, P&L, the incumbent on the same days, and the
verdict. Reads reports/gemini/{rungs,parents,dislocations,volumes}.csv; writes summary.json, daily.csv,
incumbent_sample.csv and prints the tables used in README.md.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v5"))
OUT = os.path.join(ROOT, "reports", "gemini")
C, THETA, KAPPA, PER_TRADE = 250e3, 0.5, 0.002, 0.25
GEM_TIERS = [(0, .0060, .0120), (10e3, .0040, .0080), (25e3, .0025, .0050), (75e3, .00125, .0025),
             (250e3, .00075, .0015), (500e3, .0006, .00125), (1e6, .0005, .0010), (5e6, .0004, .00085),
             (10e6, .00025, .00065), (20e6, .0001, .0005), (50e6, 0.0, .00035), (100e6, 0.0, .00025),
             (250e6, 0.0, .0002)]
CB_VIP1 = (.0006, .00125)
OOS_DAYS = [d.strftime("%Y-%m-%d") for d in pd.date_range("2025-01-01", "2026-11-01", freq="MS")]


def tier(v30, table=GEM_TIERS):
    out = table[0]
    for t in table:
        if v30 >= t[0]:
            out = t
    return out[1], out[2]


def size(R, P, V, theta=THETA, kappa=KAPPA, cap_only=False):
    """Fill and take-profit USD per rung: want = min(25% C, kappa x the coin's Gemini USD volume that day) / 3, capped by
    theta x sellers (shared within the parent while inside the parent's seller window) and theta x take-profit buyers."""
    vol = V.set_index(["day", "coin"]).gem_usd
    P = P.set_index("pid")
    R = R.sort_values(["pid", "f_off"]).copy()
    fill, tpf = np.zeros(len(R)), np.zeros(len(R))
    used, used_tp = {}, {}
    for n, r in enumerate(R.itertuples()):
        p = P.loc[r.pid]
        want = np.inf if cap_only else min(PER_TRADE * C, kappa * vol.get((r.day, r.coin), 0.0)) / 3.0
        own = theta * r.cap_sell
        if r.k > 4.0 and r.f_off <= p.pool_end:
            own = min(own, max(0.0, theta * p.pool_sell - used.get(r.pid, 0.0)))
        f = min(want, own)
        used[r.pid] = used.get(r.pid, 0.0) + f
        if r.tp_hit:
            t = max(0.0, min(f, theta * r.tp_cap - used_tp.get(r.pid, 0.0)))
            used_tp[r.pid] = used_tp.get(r.pid, 0.0) + t
        else:
            t = 0.0
        fill[n], tpf[n] = f, t
    R["fill"], R["tp_fill"] = fill, tpf
    return R


def pnl(R, mk, tk):
    rem = R.fill - R.tp_fill
    return R.tp_fill * (R.g_tp / 1e4 - mk) + rem * (R.g60 / 1e4 - tk) - R.fill * mk


def boot(daily, n_days, reps=4000, seed=0):
    rng = np.random.default_rng(seed)
    x = daily.reindex(n_days, fill_value=0.0).to_numpy()
    sims = np.array([x[rng.integers(0, len(x), len(x))].mean() for _ in range(reps)]) * 365
    return float(np.percentile(sims, 5)), float(np.percentile(sims, 95))


def incumbent_sample():
    """The incumbent's Coinbase ladder (frozen simulator, research volumes, $250K, theta 0.5, instant deeper rungs)
    over the selection and check eras; returns its rows and the per-day P&L."""
    import fsim
    P = fsim.load("main")
    out = []
    for era in ("sel", "chk"):
        lo, hi = fsim.ERAS[era][1]
        W = fsim.window(P, lo, hi)
        days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
        Q, d, info = fsim.evaluate(W, theta=THETA, C=C, days=days, drop_same_minute=False)
        Q["era"] = era
        out.append(Q)
    Q = pd.concat(out, ignore_index=True)
    Q["day"] = Q.fill_t.dt.floor("D").dt.strftime("%Y-%m-%d")
    return Q


def main():
    R = pd.read_csv(os.path.join(OUT, "rungs.csv"))
    P = pd.read_csv(os.path.join(OUT, "parents.csv"))
    Dz = pd.read_csv(os.path.join(OUT, "dislocations.csv"))
    V = pd.read_csv(os.path.join(OUT, "volumes.csv"))
    inp = json.load(open(os.path.join(OUT, "inputs.json")))
    all_days = list(inp["days"])
    lv_days = list(inp.get("days_with_levels", all_days))
    oos = [d for d in OOS_DAYS if d in all_days]
    s = {"sample_days": len(all_days), "days_with_levels": len(lv_days), "oos_days": len(oos)}

    # volumes: Gemini vs Coinbase on the sample days
    vv = V[V.day.isin(oos)].groupby("coin")[["gem_usd", "cb_usd"]].mean()
    vv["gem_share"] = vv.gem_usd / vv.cb_usd
    s["volume_by_coin"] = vv.round(4).reset_index().to_dict("records")
    s["gem_alt_usd_day"] = float(V[V.day.isin(oos)].groupby("day").gem_usd.sum().mean())
    s["cb_alt_usd_day"] = float(V[V.day.isin(oos)].groupby("day").cb_usd.sum().mean())

    # pure synchronous dislocations (all sample days with levels)
    for k in (4, 6, 8):
        dk = Dz[Dz.worst_gap_sig <= -k] if len(Dz) else Dz
        fresh = dk[dk.cb_age_s <= 10] if len(dk) else dk
        s[f"gap{k}"] = dict(episodes=int(len(dk)), per_day=len(dk) / max(1, len(lv_days)),
                            fresh_cb_episodes=int(len(fresh)),
                            usd=float(dk.usd.sum()) if len(dk) else 0.0, sell_usd=float(dk.sell_usd.sum()) if len(dk) else 0.0,
                            gem_rebound_60=float(dk.gem_vs_entry_60.median()) if len(dk) else np.nan,
                            gem_rebound_300=float(dk.gem_vs_entry_300.median()) if len(dk) else np.nan,
                            cb_vs_entry_60=float(dk.cb_vs_entry_60.median()) if len(dk) else np.nan)

    res = {}
    for ai in (False, True):
        days = oos
        Ra = R[(R.ai == ai) & R.day.isin(days)].copy()
        Pa = P[(P.ai == ai) & P.day.isin(days)].copy()
        tag = "ai" if ai else "all"
        if not len(Ra):
            res[tag] = dict(parents=0)
            continue
        Rs = size(Ra, Pa, V)
        Rc = size(Ra, Pa, V, cap_only=True)
        v30 = 2 * Rs.fill.sum() / len(days) * 30
        mk, tk = tier(v30)
        Rs["net_gem"] = pnl(Rs, mk, tk)
        Rs["net_vip1"] = pnl(Rs, *CB_VIP1)
        Rs["gross"] = pnl(Rs, 0.0, 0.0)
        Rc["gross"] = pnl(Rc, 0.0, 0.0)
        Rc["net_vip1"] = pnl(Rc, *CB_VIP1)
        out = {}
        for grp, msk in (("all", Rs.k > 0), ("shared", Rs.shared), ("gemini_only", ~Rs.shared)):
            q = Rs[msk]
            qc = Rc[msk.to_numpy()]
            par = Pa[Pa.pid.isin(q.pid)] if grp != "all" else Pa
            par = par[par.shared] if grp == "shared" else (par[~par.shared] if grp == "gemini_only" else par)
            dly = q.groupby("day").net_gem.sum()
            out[grp] = dict(
                parents=int(len(par)), parents_per_day=len(par) / len(days), rungs=int(len(q)),
                rungs_by_k={str(k): int((q.k == k).sum()) for k in (4.0, 6.0, 8.0)},
                through_sell_usd_day=float(par.pool_sell.sum() / len(days)),
                through_all_usd_day=float(par.pool_all.sum() / len(days)),
                median_through_sell=float(par.pool_sell.median()) if len(par) else np.nan,
                fill_usd_day=float(q.fill.sum() / len(days)), cap_only_fill_usd_day=float(qc.fill.sum() / len(days)),
                tp_hit=float(q.tp_hit.mean()) if len(q) else np.nan,
                gross_bp_per_dollar=float(1e4 * q.gross.sum() / q.fill.sum()) if q.fill.sum() > 0 else np.nan,
                gross_bp_per_rung_median=float(np.nanmedian(np.where(q.tp_hit, q.g_tp, q.g60))) if len(q) else np.nan,
                net_gem_bp=float(1e4 * q.net_gem.sum() / q.fill.sum()) if q.fill.sum() > 0 else np.nan,
                net_vip1_bp=float(1e4 * q.net_vip1.sum() / q.fill.sum()) if q.fill.sum() > 0 else np.nan,
                net_gem_usd_yr=float(q.net_gem.sum() / len(days) * 365),
                net_vip1_usd_yr=float(q.net_vip1.sum() / len(days) * 365),
                gross_usd_yr=float(q.gross.sum() / len(days) * 365),
                cap_only_gross_usd_yr=float(qc.gross.sum() / len(days) * 365),
                cap_only_net_vip1_usd_yr=float(qc.net_vip1.sum() / len(days) * 365),
                net_gem_usd_yr_ci90=boot(dly, days),
                markouts_cb={h: float(q[f"m_cb_{h}"].median()) for h in (1, 10, 60, 300, 3600) if f"m_cb_{h}" in q},
                markouts_gem={h: float(q[f"m_gem_{h}"].median()) for h in (1, 10, 60, 300, 3600) if f"m_gem_{h}" in q},
                markouts_cb_mean={h: float(q[f"m_cb_{h}"].mean()) for h in (1, 10, 60, 300, 3600) if f"m_cb_{h}" in q},
                hs60_bp=float(q.hs60_bp.median()) if "hs60_bp" in q else np.nan)
        out["fee_tier"] = dict(v30=float(v30), maker_bp=mk * 1e4, taker_bp=tk * 1e4)
        res[tag] = out
        Rs.to_csv(os.path.join(OUT, f"rungs_sized_{tag}.csv"), index=False)
    s["ladder"] = res

    # the incumbent on the same days
    Q = incumbent_sample()
    full_days = (pd.Timestamp("2026-11-05") - pd.Timestamp("2025-01-01")).days + 1
    qs = Q[Q.day.isin(oos)]
    s["incumbent"] = dict(
        full_net_usd_yr=float(Q.pnl.sum() / full_days * 365), full_fill_usd_day=float(Q.fill.sum() / full_days),
        sample_net_usd_yr=float(qs.pnl.sum() / len(oos) * 365), sample_fill_usd_day=float(qs.fill.sum() / len(oos)),
        sample_parents=int(((qs.k == 4.0) & (qs.fill > 0)).sum()),
        sample_net_bp=float(1e4 * qs.pnl.sum() / qs.fill.sum()) if qs.fill.sum() > 0 else np.nan,
        sample_gross_bp=float(1e4 * qs.gross.sum() / qs.fill.sum()) if qs.fill.sum() > 0 else np.nan,
        full_net_bp=float(1e4 * Q.pnl.sum() / Q.fill.sum()),
        sample_net_usd_yr_ci90=boot(qs.groupby("day").pnl.sum(), oos))
    qs[["day", "coin", "k", "fill_t", "fill", "tp_fill", "gross", "pnl"]].to_csv(os.path.join(OUT, "incumbent_sample.csv"),
                                                                                index=False)
    ai = res.get("ai", {}).get("all", {})
    lo90 = ai.get("net_gem_usd_yr_ci90", (np.nan, np.nan))[0]
    s["verdict"] = dict(
        bar_5k=bool(ai.get("net_gem_usd_yr", -1) >= 5000 and ai.get("net_gem_bp", -1) > 0 and lo90 > 0),
        more_profitable_than_coinbase=bool(ai.get("net_gem_bp", -1e9) > s["incumbent"]["sample_net_bp"] and
                                           ai.get("net_gem_usd_yr", -1e9) > s["incumbent"]["sample_net_usd_yr"]))
    json.dump(s, open(os.path.join(OUT, "summary.json"), "w"), indent=1, default=float)
    print(json.dumps(s, indent=1, default=float))


if __name__ == "__main__":
    main()
