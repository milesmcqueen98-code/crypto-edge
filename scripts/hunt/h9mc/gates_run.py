#!/usr/bin/env python3
"""H9 (MC): the one HOLD read (run locally after the freeze commit is pushed; gates.path_b is cheap).
Refuses to run unless reports/hunt/h9mc/frozen.json is committed AND the commit that added it is on origin/hunt/h9mc.
Inputs: reports/hunt/h9mc/final_daily_theta0.5.parquet / _theta0.25 and final_trades_theta*.parquet (step2.py final).
Writes reports/hunt/h9mc/daily.parquet (s30_2x, s50_2x, s30_1x, s50_1x over the sleeve's scored days),
gates.json (path_b at 2x; 1x and theta 0.25 for information; checks)."""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import gates  # noqa: E402

ROOT = gates.ROOT
OUT = os.path.join(ROOT, "reports", "hunt", "h9mc")
DAY0 = pd.Timestamp("2025-07-18")


def freeze_pushed():
    rel = "reports/hunt/h9mc/frozen.json"
    sha = subprocess.run(["git", "-C", ROOT, "log", "-n1", "--format=%H", "--", rel], capture_output=True,
                         text=True).stdout.strip()
    if not sha:
        return None
    subprocess.run(["git", "-C", ROOT, "fetch", "-q", "origin", "hunt/h9mc"], check=False)
    ok = subprocess.run(["git", "-C", ROOT, "merge-base", "--is-ancestor", sha, "origin/hunt/h9mc"]).returncode == 0
    return sha if ok else None


def main():
    sha = freeze_pushed()
    if not sha:
        raise SystemExit("frozen.json is not committed and pushed: HOLD stays closed")
    F = json.load(open(os.path.join(OUT, "frozen.json")))
    name = F["variant"]
    days = pd.date_range(DAY0, gates.END, freq="D")
    days = days[days.isin(gates.ERA_DAYS)]
    res = dict(variant=name, freeze_commit=sha, scored_days=[str(days[0].date()), str(days[-1].date()), len(days)])
    D = {}
    for theta in (0.5, 0.25):
        X = pd.read_parquet(os.path.join(OUT, f"final_daily_theta{theta}.parquet")).reindex(days).fillna(0.0)
        D[theta] = {(cap, m): X[f"{name}|{cap}|{m}"] for cap in (30000, 50000) for m in (1, 2)}
    daily = pd.DataFrame({"s30_2x": D[0.5][(30000, 2)], "s50_2x": D[0.5][(50000, 2)],
                          "s30_1x": D[0.5][(30000, 1)], "s50_1x": D[0.5][(50000, 1)]})
    daily.index.name = "day"
    daily.to_parquet(os.path.join(OUT, "daily.parquet"))

    pb = gates.path_b({30000: daily.s30_2x, 50000: daily.s50_2x}, days=days)
    res["path_b_2x"] = pb
    res["info_path_b_1x"] = gates.path_b({30000: daily.s30_1x, 50000: daily.s50_1x}, days=days)
    res["info_path_b_2x_theta0.25"] = gates.path_b({30000: D[0.25][(30000, 2)], 50000: D[0.25][(50000, 2)]}, days=days)
    res["G4_note"] = ("provisional: G4 is recomputed centrally with the final ledger and a robust null dispersion "
                      "(coordinator note; deviation logged in reports/hunt_prereg.md)")
    # path A only if the sleeve alone beats the incumbent (prereg)
    inc100 = gates.incumbent(100e3, days=days)
    s_alone = gates.sharpe(daily.s30_2x)
    res["sleeve_alone_sharpe_2x_full"] = s_alone
    res["incumbent_sharpe_full"] = gates.sharpe(inc100)
    if s_alone > gates.sharpe(inc100):
        cand = daily.s30_2x  # returns on $30K capital scale with capital; path_a vol-scales anyway
        res["path_a_2x"] = gates.path_a(cand, days=days)

    # checks
    hold = days >= gates.HOLD0
    T = pd.read_parquet(os.path.join(OUT, "final_trades_theta0.5.parquet"))
    T["day"] = pd.to_datetime(T["day"])
    T["hold"] = T.day >= gates.HOLD0
    s = daily.s30_2x
    pnl = s * 30000
    pos = pnl[pnl != 0]
    top3 = pnl.sort_values(ascending=False).head(3).sum()
    res["checks"] = dict(
        trades_dev=int((~T.hold).sum()), trades_hold=int(T.hold.sum()), trades_total=int(len(T)),
        net_bp_2x_dev=float(T.loc[~T.hold, "bp2"].mean()), net_bp_2x_hold=float(T.loc[T.hold, "bp2"].mean()),
        net_bp_1x_dev=float(T.loc[~T.hold, "bp1"].mean()), net_bp_1x_hold=float(T.loc[T.hold, "bp1"].mean()),
        net_bp_2x_by_coin={c: [round(float(g.bp2.mean()), 2), int(len(g))] for c, g in T.groupby("coin")},
        top3_days_share_of_pnl=float(top3 / pnl.sum()) if pnl.sum() > 0 else None,
        total_pnl_usd_30k_2x=float(pnl.sum()), active_days=int(len(pos)),
        corr_incumbent_full=float(np.corrcoef(s, inc100)[0, 1]),
        mean_notional=float(T.notional.mean()), fill_share_of_15k=float((T.notional / 15000).mean()),
        sleeve_years_2x={int(k): round(float(v), 4) for k, v in gates.years(s).items()},
        sleeve_mtm_note="positions are flat by 17:00 ET each day (no overnight exposure)",
    )
    worst = inc100[inc100 < inc100.quantile(0.05)].index
    res["checks"]["sleeve_on_incumbent_worst5pct_days"] = float(s.reindex(worst).mean())
    # H1 overlap (if its daily.parquet exists on origin/hunt/h1pb)
    try:
        raw = subprocess.run(["git", "-C", ROOT, "show", "origin/hunt/h1pb:reports/hunt/h1pb/daily.parquet"],
                             capture_output=True, check=True).stdout
        import io
        h1 = pd.read_parquet(io.BytesIO(raw))
        h1.index = pd.to_datetime(h1.index)
        col = "s30_2x" if "s30_2x" in h1 else h1.columns[0]
        h = h1[col].reindex(days).fillna(0.0)
        res["checks"]["corr_h1pb_full"] = float(np.corrcoef(s, h)[0, 1]) if h.std() > 0 else None
    except Exception as ex:  # noqa: BLE001
        res["checks"]["corr_h1pb_full"] = f"unavailable: {type(ex).__name__}"
    json.dump(res, open(os.path.join(OUT, "gates.json"), "w"), indent=1, default=float)
    show = {k: pb[k] for k in ("a", "full_t_alpha", "hold_t_alpha", "dev_t_alpha", "full_gain", "hold_gain", "dev_gain",
                               "full_book_sharpe", "hold_book_sharpe", "full_sleeve_sharpe", "hold_sleeve_sharpe",
                               "dsr", "n_trials", "years", "G1", "G2", "G3", "G4", "G5", "pass_G1_G5")}
    print(json.dumps(show, indent=1, default=float))
    print(json.dumps(res["checks"], indent=1, default=float))


if __name__ == "__main__":
    main()
