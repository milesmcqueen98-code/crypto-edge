#!/usr/bin/env python3
"""H13 (PS) after the freeze (reports/hunt/h13ps/frozen.json committed and pushed): the frozen variant over every
scored day, 2x costs for the gates and 1x for information, on $30K and $50K; gates.path_b; daily.parquet; checks.
HOLD is read once, here. No parameter is chosen after this point.

usage: python scripts/hunt/h13ps/final.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402
from sim import gates  # noqa: E402

H4_BRANCH = "hunt/h4nl"


def run(M, S, fz, take, mult, cap, theta=0.5):
    p = fz["params"]
    t = sim.trades(M, S, p["mode"], p["H"], mult, theta, p.get("delta") or 2, cap, take=take)
    return sim.scored(t)


def main():
    fz = json.load(open(os.path.join(sim.OUT, "frozen.json")))
    p = fz["params"]
    M, S = sim.load("all")                       # raises unless the freeze commit is pushed
    allE = pd.read_csv(sim.EVENTS, parse_dates=["T_lo"])
    allE = allE[allE.in_universe]
    take = None
    if p.get("ai"):
        take, qlog = sim.ai_take(M, S, p["mode"], p["H"], p.get("delta") or 2, 0.5, allE, end=None)
        qlog.to_csv(os.path.join(sim.OUT, "ai_quarters_all.csv"), index=False)
    T = {}
    ser = {}
    for mult in (2.0, 1.0):
        for cap in (30000.0, 50000.0):
            t = run(M, S, fz, take, mult, cap)
            T[(mult, cap)] = t
            ser[f"s{int(cap / 1000)}_{int(mult)}x"] = sim.daily(t, cap)
    D = pd.DataFrame(ser)
    D.index.name = "day"
    D.to_parquet(os.path.join(sim.OUT, "daily.parquet"))
    g2 = gates.path_b({30000: D.s30_2x, 50000: D.s50_2x}, days=sim.SCORED)
    g1 = gates.path_b({30000: D.s30_1x, 50000: D.s50_1x}, days=sim.SCORED)
    # theta = 0.25 (information)
    t25 = run(M, S, fz, take, 2.0, 30000.0, theta=0.25)
    t25_50 = run(M, S, fz, take, 2.0, 50000.0, theta=0.25)
    s25 = sim.daily(t25, 30000.0)
    g25 = gates.path_b({30000: s25, 50000: sim.daily(t25_50, 50000.0)}, days=sim.SCORED)
    # G4 alternatives (information; the coordinator recomputes G4 centrally)
    bk = None
    a = g2["a"]
    ri = gates.incumbent(a * 100e3, 0.5, "instant", sim.SCORED)
    rs = D[f"s{int(round((1 - a) * 100))}_2x"]
    bk = a * ri + (1 - a) * rs
    g4 = {}
    for mode in ("within", "pooled", "plain"):
        N, V = gates.n_trials(robust=mode if mode != "plain" else False)
        g4[mode] = dict(N=N, vz=V, dsr=gates.deflated_sharpe(bk, N, V)[0])
    N, _ = gates.n_trials()
    g4["floor"] = dict(N=N, vz=gates.VZ_FLOOR, dsr=gates.deflated_sharpe(bk, N, gates.VZ_FLOOR)[0])
    t2 = T[(2.0, 30000.0)]
    hold = t2.exit_day >= gates.HOLD0 if len(t2) else pd.Series(dtype=bool)
    sl = D.s30_2x
    sl_y = sl.groupby(sl.index.year).sum()
    inc = gates.incumbent(100e3, 0.5, "instant", sim.SCORED)
    out = dict(idea=sim.IDEA, frozen=fz, gates_2x=g2, gates_1x_info=g1, gates_theta025_2x_info=g25, g4_variants=g4,
               n_trades=dict(all=int(len(t2)), dev=int((~hold).sum()), hold=int(hold.sum())),
               mean_net_bp_2x=dict(dev=float(t2[~hold].net.mean() * 1e4) if (~hold).any() else None,
                                   hold=float(t2[hold].net.mean() * 1e4) if hold.any() else None),
               sleeve_30k_2x=dict(sharpe_full=gates.sharpe(sl), sharpe_dev=gates.sharpe(sl[sl.index < gates.HOLD0]),
                                  sharpe_hold=gates.sharpe(sl[sl.index >= gates.HOLD0]),
                                  years={int(k): float(v) for k, v in sl_y.items()},
                                  ann_return=float(sl.mean() * 365)),
               corr_with_incumbent=float(np.corrcoef(sl, inc)[0, 1]),
               path_a_applies=bool(gates.sharpe(sl) > gates.sharpe(inc)))
    if out["path_a_applies"]:
        out["path_a"] = gates.path_a(sim.daily(run(M, S, fz, take, 2.0, 100000.0), 100000.0), days=sim.SCORED)
    sim.dumpj(out, os.path.join(sim.OUT, "gates.json"))
    t2.to_csv(os.path.join(sim.OUT, "trades_frozen_2x.csv"), index=False)
    checks(M, S, fz, take, T, D, inc)
    print(json.dumps({k: out[k] for k in ("n_trades", "mean_net_bp_2x", "sleeve_30k_2x", "corr_with_incumbent")},
                     indent=1, default=str))
    keys = ["a", "full_t_alpha", "hold_t_alpha", "dev_t_alpha", "full_gain", "hold_gain", "dev_gain",
            "full_book_sharpe", "full_inc_sharpe", "hold_book_sharpe", "hold_inc_sharpe", "dsr", "n_trials", "years",
            "G1", "G2", "G3", "G4", "G5", "pass_G1_G5"]
    print("2x:", {k: g2[k] for k in keys})
    print("1x:", {k: g1[k] for k in keys})
    print("theta 0.25 2x:", {k: g25[k] for k in ("full_t_alpha", "hold_t_alpha", "full_gain", "hold_gain")})
    print("G4 variants:", g4)


def checks(M, S, fz, take, T, D, inc):
    """SPEC checks on all scored events (information; nothing is chosen from them)."""
    import subprocess
    out = {}
    E = M.copy()
    E["year"] = E.T_lo.dt.year
    out["events_by_year"] = E.groupby("year").size().to_dict()
    out["lo_dur_h_quantiles"] = (E.lo_dur_min / 60).quantile([.1, .25, .5, .75, .9]).round(2).to_dict()
    au = (E.T_lo - E.T_auction).dt.total_seconds() / 60
    out["auction_min_quantiles"] = au.dropna().quantile([.1, .25, .5, .75, .9]).round(1).to_dict()
    lg = lambda a, b: np.log(E[b] / E[a]) * 1e4  # noqa: E731
    E["hold"] = E.T_ft >= gates.HOLD0
    for nm, (a, b) in {"lo60_to_ft": ("px_lo60", "px_ft"), "ftm10_to_ft": ("px_ftm10", "px_ft"),
                       "ft_to_ft5": ("px_ft", "px_ft5"), "ft_to_ft30": ("px_ft", "px_ft30"),
                       "ft_to_ft120": ("px_ft", "px_ft120")}.items():
        v = lg(a, b)
        out[f"move_bp_{nm}"] = {w: dict(mean=float(v[m].mean()), median=float(v[m].median()), n=int(v[m].notna().sum()))
                                for w, m in (("dev", ~E.hold), ("hold", E.hold), ("all", E.hold | ~E.hold))}
    out["half_spread_bp_pre_post_ft"] = {k: dict(median=float(E[f"{k}_hs10any"].median()),
                                                 mean=float(E[f"{k}_hs10any"].mean()))
                                         for k in ("pre_ft", "post_ft")}
    R = sim._read("rel", ("dev", "hold"))
    R = R[R.key.isin(E.key)]
    out["median_usd_per_min_rel_ft"] = {int(k): float(v) for k, v in R.groupby("bin").usd.median().items()
                                        if -15 <= k <= 15}
    out["mean_buy_share_rel_ft"] = {int(k): float(v) for k, v in
                                    (R.groupby("bin").buyusd.sum() / R.groupby("bin").usd.sum()).items()
                                    if -10 <= k <= 10}
    t2 = T[(2.0, 30000.0)]
    if len(t2):
        Mk = M.set_index("key")
        buy = t2.key.map(Mk.buyusd_ft_60s)
        out["participation"] = dict(median_size_over_buyusd_first_min_after_ft=float((t2.usd / buy.replace(0, np.nan)).median()),
                                    share_size_gt_half=float((t2.usd > 0.5 * buy).mean()))
        p = fz["params"]
        if p["mode"] == 2:
            e = f"e{p.get('delta') or 2}"
            b60 = t2.key.map(Mk[f"{e}_fill_buyusd60"])
            out["participation"]["median_size_over_buyusd_60s_after_entry"] = float((t2.usd / b60.replace(0, np.nan)).median())
        xl = t2.key.map(Mk[f"x{p['H']}_fill_sellusd60"])
        out["participation"]["median_size_over_sellusd_60s_after_exit"] = float((t2.usd / xl.replace(0, np.nan)).median())
        pnl_d = t2.groupby("exit_day").pnl.sum()
        out["top3_days_share_of_pnl"] = float(pnl_d.nlargest(3).sum() / pnl_d.sum()) if pnl_d.sum() > 0 else None
        out["top3_events_share_of_pnl"] = float(t2.pnl.nlargest(3).sum() / t2.pnl.sum()) if t2.pnl.sum() > 0 else None
        out["exit_fallbacks"] = int(t2.x_fallback.sum())
        out["capacity_30k_2x"] = dict(n=int(len(t2)), usd_traded=float(t2.usd.sum()), mean_usd=float(t2.usd.mean()),
                                      share_at_5k=float((t2.usd >= 4999).mean()))
        t25 = sim.scored(sim.trades(M, S, p["mode"], p["H"], 2.0, 0.25, p.get("delta") or 2, 30000.0, take=take))
        out["capacity_theta025"] = dict(n=int(len(t25)), usd_traded=float(t25.usd.sum()) if len(t25) else 0.0)
        worst = inc.nsmallest(20).index
        out["sleeve_on_incumbent_worst20_days_usd"] = float((D.s30_2x.reindex(worst) * 30000).sum())
        # overlap with H4 (same coin and UTC day as an H4 candidate fill)
        try:
            raw = subprocess.check_output(["git", "-C", sim.ROOT, "show",
                                           f"{H4_BRANCH}:data/hunt/h4nl/cand_full.parquet"])
            import io
            C4 = pd.read_parquet(io.BytesIO(raw))
            tcol = next(c for c in C4.columns if "time" in c.lower() or c in ("ts", "t", "entry"))
            pcol = next(c for c in C4.columns if c in ("pid", "product", "coin", "base"))
            C4["day"] = pd.to_datetime(C4[tcol]).dt.normalize()
            C4["b"] = C4[pcol].astype(str).str.replace("-USD", "", regex=False)
            k4 = set(zip(C4.b, C4.day))
            mine = list(zip(t2.base_ccy, pd.to_datetime(t2.x_ms, unit="ms").dt.normalize()))
            out["overlap_h4_same_coin_day"] = dict(n=int(sum(x in k4 for x in mine)), of=len(mine))
            raw = subprocess.check_output(["git", "-C", sim.ROOT, "show", f"{H4_BRANCH}:reports/hunt/h4nl/daily.parquet"])
            D4 = pd.read_parquet(io.BytesIO(raw))
            c4 = D4[D4.columns[0]].reindex(D.index).fillna(0.0)
            out["corr_with_h4_daily"] = float(np.corrcoef(D.s30_2x, c4)[0, 1])
        except Exception as e:  # noqa: BLE001
            out["overlap_h4_error"] = f"{type(e).__name__}: {e}"[:200]
        # marked-to-market drawdown of the sleeve (Mode I holds inventory for hours): daily MTM from minute bars
        if p["mode"] == 1:
            out["mtm"] = mtm(t2, 30000.0)
    sim.dumpj(out, os.path.join(sim.OUT, "checks.json"))
    print(json.dumps(out, indent=1, default=str))


def mtm(t, cap):
    """Worst intraday mark-to-market loss of open Mode I inventory (fills at the first fill slot; marked on minute
    lows), as a share of the sleeve."""
    B = sim._read("m1", ("dev", "hold"))
    worst = 0.0
    rows = []
    for r in t.itertuples():
        b = B[(B.key == r.key)]
        a = pd.to_datetime(r.entry_ms, unit="ms") if pd.notna(r.entry_ms) else None
        x = pd.to_datetime(r.x_ms, unit="ms")
        if a is None:
            continue
        w = b[(b.minute >= a.floor("min")) & (b.minute <= x)]
        if w.empty:
            continue
        units = r.usd / r.vwap
        dd = float((units * w.low.min() - r.usd) / cap)
        rows.append(dd)
        worst = min(worst, dd)
    return dict(worst_open_loss_share_of_sleeve=worst, median=float(np.median(rows)) if rows else None)


if __name__ == "__main__":
    main()
