#!/usr/bin/env python3
"""H4 (NL) after the freeze: run the FROZEN variant (reports/hunt/h4nl/frozen.json) once over all scored days and
apply the gates (reports/hunt_prereg.md). Refuses to run unless frozen.json is in the pushed branch.

  python scripts/hunt/h4nl/precompute.py full      (first; candidate fills over every minute fetched)
  python scripts/hunt/h4nl/hold.py
Writes reports/hunt/h4nl/gates.json, daily.parquet (s30_2x, s50_2x, s30_1x, s50_1x) and hold_extras.json.
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import gates  # noqa: E402
import sim  # noqa: E402

ROOT = sim.ROOT


def freeze_pushed():
    subprocess.run(["git", "-C", ROOT, "fetch", "-q", "origin", "hunt/h4nl"], check=False)
    out = subprocess.run(["git", "-C", ROOT, "log", "--format=%H", "FETCH_HEAD", "--", "reports/hunt/h4nl/frozen.json"],
                         capture_output=True, text=True).stdout.split()
    return out[-1] if out else None


def stats(r, ri=None):
    r = pd.Series(r)
    out = dict(sharpe=gates.sharpe(r), ret_yr=float(r.mean() * 365), total=float(r.sum()))
    if ri is not None:
        at = gates.alpha_test(r, ri)
        out.update(t_alpha=at["t_alpha"], beta=at["beta"], corr=float(np.corrcoef(r, ri)[0, 1]) if r.std() > 0 else None)
    return out


def main():
    fz_commit = freeze_pushed()
    if not fz_commit:
        raise SystemExit("frozen.json is not in the pushed branch: freeze first")
    F = json.load(open(os.path.join(sim.OUT, "frozen.json")))
    v = dict(F["params"])
    base = {k: v[k] for k in ("k", "win", "liq", "H")}
    C, L = sim.load("full")
    days = gates.ERA_DAYS
    hold = days >= gates.HOLD0
    drop = L.pid[L.t0.dt.year == 2024].tolist()
    q_all = sim.candidates(C, L, base)
    keep = None
    if v.get("ai"):
        keep, _ = sim.ai_keep(q_all, v["ai"])
    q = sim.candidates(C, L, base, keep=keep)
    S, TR = {}, {}
    for cap in (30000, 50000):
        for mult in (2.0, 1.0):
            T, d = sim.simulate(q, L, v, cap, theta=0.5, mult=mult, drop_pids=drop)
            S[f"s{cap // 1000}_{int(mult)}x"] = sim.daily_returns(d, cap, days)
            TR[(cap, mult)] = T
    daily = pd.DataFrame(S, index=days)
    daily.index.name = "day"
    daily.to_parquet(os.path.join(sim.OUT, "daily.parquet"))
    g2 = gates.path_b({30000: daily.s30_2x, 50000: daily.s50_2x}, days=days)
    g1 = gates.path_b({30000: daily.s30_1x, 50000: daily.s50_1x}, days=days)
    out = dict(idea="h4nl", variant=F["variant"], freeze_commit=fz_commit, path="B", theta=0.5,
               note="G4 provisional: recomputed centrally with the final ledger (coordinator)",
               path_b_2x=g2, path_b_1x_info=g1)
    json.dump(out, open(os.path.join(sim.OUT, "gates.json"), "w"), indent=1, default=float)

    # ------------------------------------------------------------ diagnostics of the frozen variant (information)
    X = {}
    T = TR[(30000, 2.0)].copy()
    T["day"] = pd.to_datetime(T.t_x).dt.floor("D")
    T = T[T.day.isin(days)]
    a = g2["a"]
    cap = int(round((1 - a) * 100e3))
    rs = daily[f"s{cap // 1000}_2x"]
    ri = gates.incumbent(a * 100e3, days=days)
    X["trades_scored"] = int(len(T))
    X["trades_by_year"] = T.groupby(T.day.dt.year).size().to_dict()
    X["trades_dev"], X["trades_hold"] = int((T.day < gates.HOLD0).sum()), int((T.day >= gates.HOLD0).sum())
    X["listings_traded"] = int(T.pid.nunique())
    X["filled_usd"], X["bid_usd"] = float(T.fill.sum()), float(T.bid.sum())
    X["fill_over_bid"] = float(T.fill.sum() / T.bid.sum())
    X["net_bp"] = float(1e4 * T.pnl.sum() / T.fill.sum())
    X["tp_share"] = float(T.tp_fill.sum() / T.fill.sum())
    X["hold_minutes_max"] = float(((pd.to_datetime(T.t_x) - T.ts).dt.total_seconds() / 60).max())
    X["sleeve_30k_2x"] = {"full": stats(daily.s30_2x, gates.incumbent(70e3, days=days)),
                          "dev": stats(daily.s30_2x[~hold], gates.incumbent(70e3, days=days[~hold])),
                          "hold": stats(daily.s30_2x[hold], gates.incumbent(70e3, days=days[hold]))}
    X["sleeve_30k_1x"] = {"full": stats(daily.s30_1x), "dev": stats(daily.s30_1x[~hold]), "hold": stats(daily.s30_1x[hold])}
    X["sleeve_years_30k_2x"] = {int(k): float(x) for k, x in gates.years(daily.s30_2x).items()}
    X["sleeve_years_30k_1x"] = {int(k): float(x) for k, x in gates.years(daily.s30_1x).items()}
    b = pd.cut(T.days, [0, 1, 2, 4, 8], right=False, labels=["day0", "day1", "days2-3", "days4-7"])
    X["net_bp_by_day"] = {str(k): dict(trades=int(len(g)), net_bp=float(1e4 * g.pnl.sum() / g.fill.sum()) if len(g) else None)
                          for k, g in T.groupby(b, observed=False)}
    pnl_day = T.groupby("day").pnl.sum()
    tot = T.pnl.sum()
    X["pnl_usd_30k_2x"] = float(tot)
    X["top3_days_share"] = float(pnl_day.sort_values(ascending=False).head(3).sum() / tot) if tot else None
    pl = T.groupby("pid").pnl.sum().sort_values(ascending=False)
    X["top3_listings"] = {k: float(x) for k, x in pl.head(3).items()}
    X["top3_listings_share"] = float(pl.head(3).sum() / tot) if tot else None
    X["worst3_listings"] = {k: float(x) for k, x in pl.tail(3).items()}
    inc100 = gates.incumbent(100e3, days=days)
    worst = inc100.sort_values().head(20).index
    X["sleeve_on_inc_worst20_days_usd"] = float(daily.s30_2x.reindex(worst).sum() * 30000)
    X["corr_full_book_a"] = float(np.corrcoef(rs, ri)[0, 1])
    # theta 0.25 (capacity), sleeve $30K at 2x
    T25, d25 = sim.simulate(q, L, v, 30000, theta=0.25, mult=2.0, drop_pids=drop)
    r25 = sim.daily_returns(d25, 30000, days)
    X["theta025_30k_2x"] = dict(stats(r25), filled_usd=float(T25.fill.sum()), trades=int(len(T25)))
    # survivorship: without products that are delisted now
    dl = L.pid[L.status == "delisted"].tolist()
    Td, dd = sim.simulate(q, L, v, 30000, theta=0.5, mult=2.0, drop_pids=drop + dl)
    rd = sim.daily_returns(dd, 30000, days)
    X["without_delisted_30k_2x"] = dict(stats(rd, gates.incumbent(70e3, days=days)), trades=int(len(Td)),
                                        delisted_trades_in_frozen=int(T.status.eq("delisted").sum()),
                                        delisted_pnl_usd=float(T.pnl[T.status == "delisted"].sum()))
    # fill realism on prints: the DEV trade sample intersected with the frozen variant's trades
    P = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(sim.DATA, "trade_check_*.csv")))],
                  ignore_index=True)
    P["ts"] = pd.to_datetime(P.ts)
    P = P[P.k == v["k"]]
    M = T.merge(P, on=["pid", "ts"], how="inner")
    if len(M):
        M["print_cap"] = np.minimum(M.bid, 0.5 * M.print_through_usd)
        X["print_check"] = dict(sampled_trades=int(len(M)), confirm_rate=float(M.confirm.mean()),
                                median_print_over_candle_through=float((M.print_through_usd / M.cand_through_usd).median()),
                                fill_usd_candle=float(M.fill.sum()), fill_usd_print_capped=float(np.where(M.confirm, np.minimum(M.fill, M.print_cap), 0).sum()),
                                pnl_usd_sampled=float(M.pnl.sum()),
                                pnl_usd_sampled_print_scaled=float((M.pnl * np.where(M.confirm, np.minimum(M.fill, M.print_cap) / M.fill, 0)).sum()),
                                half_spread_bp_median=float(M.half_spread_bp_med.median()))
    json.dump(X, open(os.path.join(sim.OUT, "hold_extras.json"), "w"), indent=1, default=float)
    print(json.dumps({k: g2[k] for k in ("a", "full_t_alpha", "hold_t_alpha", "full_gain", "hold_gain", "dev_gain", "dsr",
                                          "G1", "G2", "G3", "G4", "G5", "pass_G1_G5", "years")}, indent=1, default=float))


if __name__ == "__main__":
    main()
