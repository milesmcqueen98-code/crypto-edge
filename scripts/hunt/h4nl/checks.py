#!/usr/bin/env python3
"""H4 (NL) report checks (after the freeze; reproduces the REPORT's universe, trade-print, spread/depth and
drawdown numbers). Writes reports/hunt/h4nl/checks.json.  python scripts/hunt/h4nl/checks.py"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import gates  # noqa: E402
import sim  # noqa: E402

R = {}
U = pd.read_csv(os.path.join(sim.OUT, "universe_all.csv"))
R["usd_products"] = int(len(U))
R["exclusions"] = U.reason.fillna("IN").value_counts().to_dict()
Lf = pd.read_csv(os.path.join(sim.DATA, "listings_full.csv"), parse_dates=["t0"])
R["listings_table"] = int(U.reason.isna().sum())
R["listings_with_minutes"] = int(len(Lf))
R["by_year_status"] = {int(y): g.status.value_counts().to_dict() for y, g in Lf.groupby(Lf.t0.dt.year)}
na = Lf.new_at.notna() & ~Lf.new_at.astype(str).str.startswith("2023-01-01")
dh = (Lf.t0 - pd.to_datetime(Lf.new_at.where(na), utc=True).dt.tz_convert(None)).dt.total_seconds() / 3600
R["t0_minus_new_at_hours"] = dict(n=int(na.sum()), median=float(dh.median()),
                                  within_0_72h=int(((dh >= 0) & (dh <= 72)).sum()))
# trade-print sample (DEV candidate fill minutes, drawn before the freeze)
P = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(sim.DATA, "trade_check_*.csv")))], ignore_index=True)
P["ts"] = pd.to_datetime(P.ts)
W = P.drop_duplicates(["pid", "ts"])
ratio = P.print_through_usd / P.cand_through_usd.replace(0, np.nan)
R["trade_sample"] = dict(
    windows=int(len(W)), levels=int(len(P)), src=P.src.value_counts().to_dict(),
    confirm=float(P.confirm.mean()), confirm_by_k=P.groupby("k").confirm.mean().round(3).to_dict(),
    confirm_by_year=P.groupby(P.ts.dt.year).confirm.mean().round(3).to_dict(),
    print_over_candle_through_median=float(ratio.median()),
    print_over_candle_through_q25_q75=ratio.quantile([.25, .75]).round(3).tolist(),
    half_spread_bp=dict(median=float(W.half_spread_bp_med.median()), mean=float(W.half_spread_bp_med.mean()),
                        q75=float(W.half_spread_bp_med.quantile(.75)), q90=float(W.half_spread_bp_med.quantile(.9))),
    tick_bp_median=float(P.tick_bp.median()),
    sweep_usd_median=float(W.sweep_usd.median()), drop_bp_median=float(W.drop_bp.median()),
    usd_per_bp_drop_median=float((W.sweep_usd / W.drop_bp.replace(0, np.nan)).median()))
# print coverage: prints' USD volume vs the candle's in the fill minute; coverage in [0.9, 1.1] = complete
Wk = P[["pid", "ts"]].drop_duplicates()
parts = []
for f in sorted(glob.glob(os.path.join(sim.DATA, "m1", "m1_*.parquet"))):
    M = pd.read_parquet(f, columns=["pid", "ts", "high", "low", "close", "volume"])
    M["pid"] = M.pid.astype(str)
    parts.append(M.merge(Wk, on=["pid", "ts"]))
    del M
X = P.merge(pd.concat(parts), on=["pid", "ts"])
X["coverage"] = X.vol_usd_min / (X.volume * (X.high + X.low + X.close) / 3)
full = X["coverage"].between(0.9, 1.1)
rr = X.print_through_usd / X.cand_through_usd.replace(0, np.nan)
R["print_coverage"] = dict(levels_complete=int(full.sum()), levels=int(len(X)),
                           confirm_complete=float(X[full].confirm.mean()), confirm_incomplete=float(X[~full].confirm.mean()),
                           through_ratio_median_complete_confirmed=float(rr[full & X.confirm].median()),
                           through_ratio_iqr_complete_confirmed=rr[full & X.confirm].quantile([.25, .75]).round(3).tolist(),
                           through_ratio_aggregate_complete_confirmed=float(
                               X.print_through_usd[full & X.confirm].sum() / X.cand_through_usd[full & X.confirm].sum()))
# frozen variant's trades in the sample, print-capped (complete-coverage windows only)
F = json.load(open(os.path.join(sim.OUT, "frozen.json")))
v = F["params"]
C, L = sim.load("full")
base = {k: v[k] for k in ("k", "win", "liq", "H")}
keep, _ = sim.ai_keep(sim.candidates(C, L, base), v["ai"])
T, _ = sim.simulate(sim.candidates(C, L, base, keep=keep), L, v, 30000, mult=2.0,
                    drop_pids=L.pid[L.t0.dt.year == 2024].tolist())
Mx = T.merge(X[X.k == v["k"]][["pid", "ts", "confirm", "coverage", "print_through_usd", "half_spread_bp_med"]],
             on=["pid", "ts"])
Mc = Mx[Mx["coverage"].between(0.9, 1.1)]
cap = np.where(Mc.confirm, np.minimum(Mc.fill, 0.5 * Mc.print_through_usd), 0.0)
R["frozen_sample"] = dict(trades=int(len(Mx)), complete=int(len(Mc)), confirmed_complete=int(Mc.confirm.sum()),
                          fill_candle=float(Mc.fill.sum()), fill_print_capped=float(cap.sum()),
                          pnl_candle=float(Mc.pnl.sum()), pnl_print_scaled=float((Mc.pnl * cap / Mc.fill).sum()),
                          half_spread_bp_median=float(Mx.half_spread_bp_med.median()),
                          half_spread_bp_mean=float(Mx.half_spread_bp_med.mean()))
# frozen variant: drawdowns, DSR at the v_z floor (information; G4 is recomputed centrally)
D = pd.read_parquet(os.path.join(sim.OUT, "daily.parquet"))
R["max_drawdown_daily"] = {c: float(((1 + D[c]).cumprod() / (1 + D[c]).cumprod().cummax() - 1).min()) for c in D}
R["sleeve_totals"] = {c: dict(sharpe=gates.sharpe(D[c]), ret_yr=float(D[c].mean() * 365)) for c in D}
bk = 0.7 * gates.incumbent(70e3) + 0.3 * D.s30_2x
N, V = gates.n_trials()
R["dsr_gates_py"] = gates.deflated_sharpe(bk, N, V)
R["dsr_at_vz_floor"] = gates.deflated_sharpe(bk, N, gates.VZ_FLOOR)
R["n_trials_vz"] = [N, V]
json.dump(R, open(os.path.join(sim.OUT, "checks.json"), "w"), indent=1, default=float)
print(json.dumps(R, indent=1, default=float))
