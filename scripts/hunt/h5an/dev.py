#!/usr/bin/env python3
"""H5 (AN) DEV stage: the SPEC's trial grid on DEV days only (before 2026-06-01), every trial logged to the shared
ledger, then the selection rule. Never reads a HOLD event: sim.dev_events() drops them before any computation and
every scored series passes gates.assert_dev_only.

Trials (SPEC):
  core  18: delta in {2, 10, 30} s x H in {5, 30, 120} min x event set in {spot listings only (i), all classes (i-iv)}
  fade  +1 only if >= 20 DEV events had a Coinbase perp at the time (counted below; not run otherwise)
  AI    +2: LightGBM walk-forward filter for the best core (delta, H, set): regression and classification
Selection: the highest DEV alpha t (sleeve at 2x costs on the incumbent at $70K) among trials with >= 20 trades;
ties to the simpler variant.

usage: python scripts/hunt/h5an/dev.py [--log]      (--log appends the trials to the shared ledger)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402
from sim import gates, common  # noqa: E402

END = pd.Timestamp("2026-05-31")          # last DEV day, fixed
CAP = 30000.0
SETS = {"spot": ("i",), "all": ("i", "ii", "iii", "iv")}


def run_variant(Mdev, delta, hold, eset, take=None):
    days = sim.dev_days()
    t2 = sim.trades(Mdev, delta, hold, 2.0, SETS[eset], CAP, take=take)
    t1 = sim.trades(Mdev, delta, hold, 1.0, SETS[eset], CAP, take=take)
    t2, t1 = t2[t2.exit_day.isin(days)], t1[t1.exit_day.isin(days)]      # 2024 trains only; never scored
    s2 = sim.daily(t2, CAP, days)
    s1 = sim.daily(t1, CAP, days)
    gates.assert_dev_only(s2)
    gates.assert_dev_only(s1)
    assert (t2.exit < gates.HOLD0).all()
    a = sim.alpha70(s2, days)
    scr = gates.dev_screen(s2)
    bk = gates.dev_book(s2)
    row = dict(delta=delta, hold_min=hold // 60, set=eset, trades=len(t2), events=int(t2.key.nunique()),
               sleeve_sharpe_2x=gates.sharpe(s2), sleeve_sharpe_1x=gates.sharpe(s1), t_alpha70=a["t_alpha"],
               t_alpha100=scr["t_alpha"], corr=scr["corr"], book_sharpe=gates.sharpe(bk),
               mean_net_2x_bp=float(t2.net.mean() * 1e4) if len(t2) else np.nan,
               mean_net_1x_bp=float(t1.net.mean() * 1e4) if len(t1) else np.nan,
               mean_gross_bp=float(t2.gross.mean() * 1e4) if len(t2) else np.nan,
               hit_2x=float((t2.net > 0).mean()) if len(t2) else np.nan, pnl_2x=float(t2.pnl.sum()),
               usd_mean=float(t2.usd.mean()) if len(t2) else np.nan, exit_fallback=int(t2.exit_fallback.sum()))
    return row, s2, s1, bk, t2


def checks(Mdev):
    """Descriptive DEV checks the SPEC asks for (no trials)."""
    out = {}
    grid = [-600, -300, -120, -60, -30, -10, 0, 2, 5, 10, 20, 30, 60, 120, 300, 600, 900, 1800, 3600, 5400, 7200]
    P = pd.DataFrame({g: np.log(Mdev[f"p_{g}"] / Mdev["p_-600"]) * 1e4 for g in grid})
    P["cls"] = Mdev.cls.to_numpy()
    path = P.groupby("cls")[grid].mean().round(1)
    path.loc["all"] = P[grid].mean().round(1)
    path.loc["all_median"] = P[grid].median().round(1)
    out["path_bp_from_-10min"] = {str(k): {str(g): float(v) for g, v in r.items()} for k, r in path.iterrows()}
    n_cls = P.groupby("cls").size()
    out["path_n"] = {str(k): int(v) for k, v in n_cls.items()}
    # leak diagnostic: share of the -10 min .. +2 h move already done at release (0) and at each delta
    mv = {}
    for k, g in list(P.groupby("cls")) + [("all", P)]:
        tot = g[7200].mean()
        d = {"move_-10m_to_0": float(g[0].mean()), "move_-10m_to_+2h": float(tot),
             "move_0_to_30s": float((g[30] - g[0]).mean()), "move_0_to_300s": float((g[300] - g[0]).mean())}
        for dl in sim.DELTAS:
            e = np.log(Mdev.loc[g.index, f"e{dl}_px"] / Mdev.loc[g.index, "p_-600"]) * 1e4
            d[f"entry{dl}_vs_-600"] = float(e.mean())
            d[f"peak_to_entry{dl}_share"] = float(e.mean() / g[[2, 5, 10, 20, 30, 60, 120, 300]].mean().max()) \
                if g[[2, 5, 10, 20, 30, 60, 120, 300]].mean().max() > 0 else None
        mv[str(k)] = d
    out["leak"] = mv
    byd = {}
    for dl in sim.DELTAS:
        for h in sim.HOLDS:
            g = np.log(Mdev[f"x{dl}_{h}_px"] / Mdev[f"e{dl}_px"]) * 1e4
            byd[f"d{dl}_h{h // 60}"] = {str(k): float(v) for k, v in g.groupby(Mdev.cls).mean().round(1).items()} | \
                {"all": float(round(g.mean(), 1)), "all_median": float(round(g.median(), 1))}
    out["gross_bp_entry_to_exit_by_cls"] = byd
    # absolute moves (direction-free) - is there a jump at all?
    out["abs_move_bp_median"] = {str(g): float(np.nanmedian(np.abs(P[g]))) for g in (0, 30, 300, 1800, 7200)}
    # spread at the event
    out["half_spread_bp"] = {"median": float(Mdev.hs_bp.median()), "p75": float(Mdev.hs_bp.quantile(0.75)),
                             "by_cls_median": {str(k): float(v) for k, v in Mdev.groupby("cls").hs_bp.median().items()},
                             "source": {str(k): int(v) for k, v in Mdev.hs_src.value_counts().items()}}
    # pre-release activity
    out["pre60_usd_median"] = float(Mdev.usd_pre60.median())
    out["entry_latency_s_median"] = {dl: float((Mdev[f"e{dl}_ms"] / 1000).median()) for dl in sim.DELTAS}
    out["buyer_usd_first60s_after_entry2_median"] = float(Mdev.e2_buyusd60.median())
    return out


def main():
    log = "--log" in sys.argv
    M = sim.load_events()
    Mdev = sim.dev_events(M)
    assert (Mdev.release < gates.HOLD0).all()
    res = {"n_dev_events": int(len(Mdev)),
           "dev_events_by_cls_year": {f"{k[0]}|{k[1]}": int(v) for k, v in
                                      Mdev.groupby(["cls", Mdev.release.dt.year]).size().items()}}
    res["checks"] = checks(Mdev)
    # fade variant feasibility: Coinbase perp live at release (data/cfm start dates)
    first = {}
    for c in common.PERP:
        d = common.load_perp(c)
        if d is not None and len(d):
            first[c] = d.index.min()
    pf = Mdev.base.map(first)
    res["fade_dev_events_with_perp"] = int((pf.notna() & (Mdev.release >= pf)).sum())

    rows, series, trd, pending = [], {}, {}, []
    for eset in ("spot", "all"):
        for delta in sim.DELTAS:
            for hold in sim.HOLDS:
                v = f"core_d{delta}_h{hold // 60}_{eset}"
                row, s2, s1, bk, t2 = run_variant(Mdev, delta, hold, eset)
                row["variant"] = v
                rows.append(row)
                series[v] = (s2, s1)
                trd[v] = t2
                pending.append((v, bk, "DEV book a=0.7, sleeve $30K at 2x costs", row))
                print(f"{v:24s} trades {row['trades']:4d}  sleeve SR2x {row['sleeve_sharpe_2x']:6.2f}  "
                      f"t70 {row['t_alpha70']:6.2f}  net2x {row['mean_net_2x_bp']:7.1f}bp  "
                      f"gross {row['mean_gross_bp']:7.1f}bp", flush=True)
    R = pd.DataFrame(rows)
    # AI variants on the best core (delta, H, set) with >= 20 trades
    ok = R[R.trades >= 20].sort_values(["t_alpha70"], ascending=False)
    best = ok.iloc[0]
    ai_rows = []
    for kind in ("reg", "clf"):
        take = sim.ai_take(Mdev, int(best.delta), int(best.hold_min) * 60, kind, end=gates.HOLD0)
        take = take & Mdev.cls.isin(SETS[best.set])
        v = f"ai_{kind}_d{int(best.delta)}_h{int(best.hold_min)}_{best.set}"
        row, s2, s1, bk, t2 = run_variant(Mdev, int(best.delta), int(best.hold_min) * 60, best.set, take=take)
        row["variant"] = v
        ai_rows.append(row)
        series[v] = (s2, s1)
        trd[v] = t2
        pending.append((v, bk, "DEV book a=0.7, sleeve $30K at 2x costs; walk-forward LightGBM", row))
        print(f"{v:24s} trades {row['trades']:4d}  sleeve SR2x {row['sleeve_sharpe_2x']:6.2f}  "
              f"t70 {row['t_alpha70']:6.2f}  net2x {row['mean_net_2x_bp']:7.1f}bp", flush=True)
    R = pd.concat([R, pd.DataFrame(ai_rows)], ignore_index=True)
    assert len(pending) <= 24
    if log:                                   # every configuration scored, logged once, after the grid completed
        for v, bk, note, row in pending:
            gates.log_trial(sim.IDEA, v, bk, note=note, sleeve_sharpe=row["sleeve_sharpe_2x"],
                            t_alpha70=row["t_alpha70"], trades=row["trades"])
        res["logged_trials"] = len(pending)
    R.to_csv(os.path.join(sim.OUT, "dev_trials.csv"), index=False)
    # selection: highest DEV alpha t with >= 20 trades; ties -> simpler (core before AI, spot before all,
    # shorter delta and H first)
    simp = {"core": 0, "ai": 1}
    R["simplicity"] = R.variant.str.split("_").str[0].map(simp) * 100 + (R.set == "all") * 10
    el = R[R.trades >= 20].copy()
    el["t_round"] = el.t_alpha70.round(6)
    sel = el.sort_values(["t_round", "simplicity", "delta", "hold_min"], ascending=[False, True, True, True]).iloc[0]
    res["selected"] = sel.drop(labels=["t_round"]).to_dict()
    # neighbours of the selection (robustness, information)
    t2 = trd[sel.variant]
    res["selected_top3_share"] = float(t2.pnl.nlargest(3).sum() / t2.pnl.sum()) if t2.pnl.sum() > 0 else None
    res["selected_years_pnl"] = {int(k): float(v) for k, v in t2.groupby(t2.exit.dt.year).pnl.sum().items()}
    with open(os.path.join(sim.OUT, "dev_summary.json"), "w") as f:
        json.dump(res, f, indent=1, default=lambda x: sim.nan2none(float(x)) if isinstance(x, (np.floating, float))
                  else (int(x) if isinstance(x, np.integer) else str(x)))
    S = pd.DataFrame({f"{k}|2x": v[0] for k, v in series.items()} | {f"{k}|1x": v[1] for k, v in series.items()})
    S.to_parquet(os.path.join(sim.OUT, "dev_series.parquet"))
    pd.concat([t.assign(variant=k) for k, t in trd.items()])[
        ["variant", "key", "cls", "release", "entry", "exit", "e_px", "x_px", "gross", "net", "usd", "pnl", "hs_bp",
         "exit_fallback"]].to_parquet(os.path.join(sim.OUT, "dev_trades.parquet"))
    print(json.dumps({"selected": res["selected"]["variant"], "t_alpha70": res["selected"]["t_alpha70"],
                      "trades": res["selected"]["trades"]}, default=str))


if __name__ == "__main__":
    main()
