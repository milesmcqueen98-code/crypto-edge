#!/usr/bin/env python3
"""H8 (depeg bids): descriptive checks for the REPORT (reports/hunt/h8dp/SPEC.md "Checks to report").

  python scripts/hunt/h8dp/analyze.py dev     DEV-only: UST stress (described, not traded), power calculation
  python scripts/hunt/h8dp/analyze.py full    after the freeze and the HOLD read: fills per year, P&L per episode,
                                              concentration, MTM drawdown, incumbent worst days (all scored days)
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
sys.path.insert(0, HERE)
import gates  # noqa: E402
import levels as LV  # noqa: E402
import sim  # noqa: E402

OUT = sim.OUT


def episodes_of(R, gap_h=24):
    """Group lots into depeg episodes: same pair, fills less than gap_h apart."""
    R = R.sort_values(["pid", "t_fill"]).copy()
    new = (R.pid != R.pid.shift()) | ((R.t_fill - R.t_fill.shift()).dt.total_seconds() > gap_h * 3600)
    R["ep"] = new.cumsum()
    R["cost"] = R.qty * R.px_in
    g = R.groupby("ep").agg(pid=("pid", "first"), first_fill=("t_fill", "min"), last_exit=("t_exit", "max"),
                            lots=("pnl", "size"), usd_bought=("cost", "sum"), min_px=("px_in", "min"),
                            pnl=("pnl", "sum"))
    g["pnl_bp_of_bought"] = (g.pnl / g.usd_bought * 1e4).round(1)
    g["days_held_max"] = ((g.last_exit - g.first_fill).dt.total_seconds() / 86400).round(2)
    return g.reset_index(drop=True)


def power(s, rf_days, label):
    """Power of the alpha test for a rare-event sleeve. s: daily sleeve returns (0 idle) over the scored days.
    t ~ sqrt(N) * mean(excess) / sd(excess) (iid approximation of the HAC t)."""
    x = gates.excess(s)
    n = len(x)
    sd = float(x.std())
    mu_need = 3.0 * sd / math.sqrt(n)
    rf_yr = float((s - x).mean() * 365)
    ev = s[s != 0]
    k_yr = len(ev) / (n / 365)
    out = dict(label=label, n_days=n, active_days=int((s != 0).sum()), sleeve_ret_yr=float(s.mean() * 365),
               rf_yr=rf_yr, excess_yr=float(x.mean() * 365), sd_daily=sd, t_iid=float(x.mean() / sd * math.sqrt(n)),
               excess_needed_yr_for_t3=mu_need * 365, sleeve_ret_needed_yr_for_t3=mu_need * 365 + rf_yr,
               active_days_per_yr=k_yr,
               mean_active_day_ret=float(ev.mean()) if len(ev) else 0.0)
    # same per-active-day payoff distribution, how many active days a year would t = 3 need?
    if len(ev) and ev.mean() > 0:
        g, v = float(ev.mean()), float((ev ** 2).mean())
        for k in range(1, 2000):
            p = k / 365.0
            m = p * g - rf_yr / 365
            var = p * v - (p * g) ** 2
            if var > 0 and m / math.sqrt(var) * math.sqrt(n) >= 3:
                out["active_days_per_yr_needed_for_t3"] = k
                break
    return out


def ust_stress():
    """UST-USD on Coinbase (2021-08-12 .. 2022-05-27; delisted after the collapse): the SPEC's deep ladder with
    $10K a rung (the whole $30K sleeve), both exits, 2x costs. Described, not traded: UST is not in the SPEC
    universe; no variant can select it. Shows the loss a depeg bidder takes when par never returns."""
    rows = []
    for ex in ("tp", "tp7"):
        for ladder in ("deep", "shallow"):
            P = sim.build("UST-USD", sim.HOLD0)
            P["final"], P["delisted"] = True, True
            rec, ol, _ = sim.simulate([P], sim.LADDERS[ladder], 0.5, sim.EXITS[ex], 2.0, lambda t: 10e3, 30e3)
            R = pd.DataFrame(rec, columns=sim.REC_COLS)
            R["t_exit"] = pd.to_datetime(R.t_exit)
            may = R[R.t_exit >= "2022-05-07"]
            rows.append(dict(ladder=ladder, exit=ex, lots=len(R), pnl_before_collapse=float(R[R.t_exit < "2022-05-07"].pnl.sum()),
                             pnl_collapse=float(may.pnl.sum()), pnl_pct_of_sleeve=float(R.pnl.sum() / 30e3 * 100),
                             collapse_exit_kinds=may.groupby("kind").size().to_dict()))
    return rows


def mtm_curve(R, capital, end):
    """Daily marked-to-market equity of the sleeve: realised P&L to date plus open lots at each day's last close."""
    days = pd.date_range("2021-01-01", end, freq="D")
    eq = pd.Series(0.0, index=days)
    real = R.groupby(R.t_exit.dt.floor("D")).pnl.sum().reindex(days).fillna(0.0).cumsum()
    unreal = pd.Series(0.0, index=days)
    for pid, g in R.groupby("pid"):
        C = LV.load_candles(pid, end=end + pd.Timedelta(days=1))
        close = C["close"].resample("D").last().ffill().reindex(days).ffill()
        maker = LV.fees(pid)[0]
        for lot in g.itertuples():
            d0, d1 = lot.t_fill.floor("D"), lot.t_exit.floor("D")
            if d1 <= d0:
                continue
            dd = pd.date_range(d0, d1 - pd.Timedelta(days=1), freq="D")
            unreal.loc[dd] += lot.qty * (close.loc[dd].to_numpy() - lot.px_in * (1 + 2 * maker))
    eq = capital + real + unreal
    dd = eq / eq.cummax() - 1
    return eq, float(dd.min()), dd.idxmin()


def mode_dev():
    out = {"ust_stress": ust_stress()}
    T = pd.read_csv(os.path.join(OUT, "dev_trials.csv"))
    pw = []
    for r in T.itertuples():
        u, ld, ex = r.universe, r.ladder, r.exit
        R, daily, _, _ = sim.run(u, ld, ex, theta=0.5, mult=2.0, capital=30e3, end=sim.HOLD0)
        s = sim.scored(daily)
        gates.assert_dev_only(s)
        pw.append(power(s, None, r.variant))
    out["power_dev"] = pw
    with open(os.path.join(OUT, "dev_checks.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


def mode_full():
    F = json.load(open(os.path.join(OUT, "frozen.json")))
    D = pd.read_parquet(os.path.join(OUT, "daily.parquet"))
    R = pd.read_csv(os.path.join(OUT, "lots_s30_2x.csv"), parse_dates=["t_fill", "t_exit"])
    days = gates.ERA_DAYS
    Rs = R[R.t_exit.dt.floor("D").isin(days)]
    E = episodes_of(R)
    E["scored"] = E.last_exit.dt.floor("D").isin(days)
    E.to_csv(os.path.join(OUT, "episodes_traded.csv"), index=False)
    s = D["s30_2x"]
    inc = gates.incumbent(70e3, days=days)
    worst = inc.nsmallest(10)
    pnl_day = Rs.groupby(Rs.t_exit.dt.floor("D")).pnl.sum()
    top3 = pnl_day.nlargest(3).sum() / pnl_day.sum() if pnl_day.sum() > 0 else float("nan")
    eq, mdd, mdd_day = mtm_curve(R, 30e3, gates.END)
    yr = Rs.groupby(Rs.t_exit.dt.year).agg(lots=("pnl", "size"), pnl=("pnl", "sum"))
    yr["fills"] = Rs.groupby(Rs.t_exit.dt.year).apply(lambda g: g.groupby(["pid", "slot", "episode"]).ngroups)
    out = dict(frozen=F["variant"], fills_per_year=yr.reset_index().to_dict("records"),
               top3_days_share_of_pnl=float(top3),
               corr_with_incumbent=float(np.corrcoef(s, inc)[0, 1]) if s.std() > 0 else None,
               sleeve_on_incumbent_10_worst_days=float(s.reindex(worst.index).sum()),
               incumbent_10_worst_days=[str(d.date()) for d in worst.index],
               mtm_max_drawdown=mdd, mtm_max_drawdown_day=str(mdd_day.date()),
               power_all=power(s, None, F["variant"] + " all scored days"),
               power_hold=power(s[s.index >= gates.HOLD0], None, F["variant"] + " HOLD"),
               years_2x=D["s30_2x"].groupby(D.index.year).sum().round(4).to_dict(),
               years_1x=D["s30_1x"].groupby(D.index.year).sum().round(4).to_dict())
    with open(os.path.join(OUT, "full_checks.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    pd.set_option("display.width", 220)
    print(E.to_string())
    print(json.dumps(out, indent=1, default=str))


def mode_compare():
    """Pre-fix (old TradeFetcher paging) vs fixed prints: the frozen variant's gate numbers side by side."""
    keys = ["a", "full_t_alpha", "dev_t_alpha", "hold_t_alpha", "full_gain", "dev_gain", "hold_gain",
            "full_sleeve_sharpe", "hold_sleeve_sharpe", "dsr", "G1", "G2", "G3", "G4", "G5"]
    rows = {}
    for tag, f in (("pre_fix", "gates_prefix.json"), ("fixed", "gates.json")):
        g = json.load(open(os.path.join(OUT, f)))
        r = {k: g["path_b_2x"][k] for k in keys}
        r.update({"1x_full_t": g["path_b_1x_info"]["full_t_alpha"], "1x_hold_t": g["path_b_1x_info"]["hold_t_alpha"],
                  "th025_full_t": g["path_b_2x_theta025_info"]["full_t_alpha"], "fills_scored": g["fills_scored"],
                  "fills_hold": g["fills_hold"], "lots_scored": g["lots_scored"],
                  "pnl_dev": g["pnl_usd_30k_2x"]["dev"], "pnl_hold": g["pnl_usd_30k_2x"]["hold"]})
        r.update({f"book_{y}": v for y, v in g["path_b_2x"]["years"].items()})
        rows[tag] = r
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, "fetchfix_compare.csv"))
    print(T.to_string())


if __name__ == "__main__":
    {"dev": mode_dev, "full": mode_full, "compare": mode_compare}[sys.argv[1]]()
