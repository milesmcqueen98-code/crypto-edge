#!/usr/bin/env python3
"""H11 (MJ): after the freeze commit, build the gate series of the frozen variant (candle fills before each perp
launch, perp prints for every post-launch trade; mj.py docstring) and score it once on all scored days.

Inputs: reports/hunt/h11mj/full/ (mj.py full and mj.py prints COIN on Actions, run after frozen.json was pushed).
Writes reports/hunt/h11mj/daily.parquet (s30_2x, s50_2x, s30_1x, s50_1x + sensitivities) and gates.json.

  python scripts/hunt/h11mj/finalize.py
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HUNT = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(HUNT))
sys.path.insert(0, HUNT)
sys.path.insert(0, HERE)
import gates  # noqa: E402
import mj  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h11mj")
FULL = os.path.join(OUT, "full")


def frozen_pushed():
    F = json.load(open(os.path.join(OUT, "frozen.json")))
    c = subprocess.run(["git", "-C", ROOT, "log", "--format=%H", "-1", "--", "reports/hunt/h11mj/frozen.json"],
                       capture_output=True, text=True).stdout.strip()
    remote = subprocess.run(["git", "-C", ROOT, "ls-remote", "origin", "hunt/h11mj"], capture_output=True,
                            text=True).stdout.split()
    anc = subprocess.run(["git", "-C", ROOT, "merge-base", "--is-ancestor", c, remote[0] if remote else "HEAD"])
    if not c or not remote or anc.returncode != 0:
        raise SystemExit("frozen.json is not committed and pushed: no HOLD statistics before the freeze")
    return F, c


def apply_prints(T, fname, P):
    """Gate trades: spot-era trades as simulated on candles; post-launch trades re-evaluated on perp prints
    (dropped when the prints do not confirm the fill or the fetch failed). Returns trades and a confirmation table."""
    T = T.copy()
    T["row"] = T.index
    perp = T.venue == "perp"
    R = P[P.file == fname].set_index("row") if len(P) else pd.DataFrame()
    conf = []
    keep = np.ones(len(T), bool)
    for i in np.nonzero(perp.to_numpy())[0]:
        t = T.iloc[i]
        if t.row not in R.index:
            keep[i] = False
            conf.append(dict(coin=t.coin, fill_ts=t.fill_ts, status="no_print_row", cand_qty=t.qty, p_qty=0.0))
            continue
        r = R.loc[t.row]
        if not bool(r.fetch_ok):
            keep[i] = False
            conf.append(dict(coin=t.coin, fill_ts=t.fill_ts, status="fetch_failed", cand_qty=t.qty, p_qty=0.0))
            continue
        if not bool(r.p_fill):
            keep[i] = False
            conf.append(dict(coin=t.coin, fill_ts=t.fill_ts, status="not_confirmed", cand_qty=t.qty, p_qty=0.0,
                             n_prints=int(r.p_n)))
            continue
        q = float(r.p_qty)
        qtp = min(float(r.p_q_tp), q)
        cand_tp = t.q_tp / t.qty if t.qty > 0 else 0.0
        T.iat[i, T.columns.get_loc("qty")] = q
        T.iat[i, T.columns.get_loc("q_tp")] = qtp
        T.iat[i, T.columns.get_loc("tp_ts")] = r.p_tp_ts if qtp > 0 else pd.NaT
        if qtp < q:
            if pd.notna(r.p_x_px):
                T.iat[i, T.columns.get_loc("x_ts")] = r.p_x_ts
                T.iat[i, T.columns.get_loc("x_px")] = float(r.p_x_px)
            status = "confirmed" if pd.notna(r.p_x_px) else "confirmed_candle_exit"
        else:
            T.iat[i, T.columns.get_loc("x_ts")] = pd.NaT
            T.iat[i, T.columns.get_loc("x_px")] = np.nan
            status = "confirmed"
        conf.append(dict(coin=t.coin, fill_ts=t.fill_ts, status=status, cand_qty=t.qty, p_qty=q,
                         cand_tp_share=cand_tp, p_tp_share=qtp / q if q > 0 else 0.0,
                         cand_x_px=t.x_px, p_x_px=float(r.p_x_px) if pd.notna(r.p_x_px) else np.nan))
    T = T[keep].copy()
    T["notional"] = T.qty * T.bid
    return T[T.qty > 0].drop(columns=["row"]).reset_index(drop=True), pd.DataFrame(conf)


def years(s):
    s = pd.Series(s)
    return {int(k): round(float(v), 4) for k, v in s.groupby(s.index.year).sum().items()}


def main():
    F, fz = frozen_pushed()
    days = gates.ERA_DAYS
    P = pd.concat([pd.read_parquet(os.path.join(FULL, f)) for f in os.listdir(FULL) if f.startswith("prints_")],
                  ignore_index=True) if any(f.startswith("prints_") for f in os.listdir(FULL)) else pd.DataFrame()
    caps = {(30000, 0.5): "s30", (50000, 0.5): "s50", (30000, 0.25): "s30_th0.25", (50000, 0.25): "s50_th0.25",
            (100000, 0.5): "s100"}
    cols, gate_T, confs, cand_cols = {}, {}, {}, {}
    for (C, th), nm in caps.items():
        fname = f"trades_{C}_{th}.parquet"
        Tc = pd.read_parquet(os.path.join(FULL, fname))
        Tg, cf = apply_prints(Tc, fname, P)
        gate_T[(C, th)], confs[(C, th)] = Tg, cf
        for mult in (1.0, 2.0):
            cols[f"{nm}_{int(mult)}x"] = mj.daily(Tg, C, days, mult)
            cand_cols[f"{nm}_{int(mult)}x"] = mj.daily(Tc, C, days, mult)
        if th == 0.5 and C in (30000, 50000):
            for fee in (0.12, 0.30):
                cols[f"{nm}_2x_fee{fee:.2f}"] = mj.daily(Tg, C, days, 2.0, fee)
    D = pd.DataFrame(cols).reindex(days).fillna(0.0)
    Dc = pd.DataFrame(cand_cols).reindex(days).fillna(0.0)
    daily = D[["s30_2x", "s50_2x", "s30_1x", "s50_1x"]].copy()
    for c in D.columns:
        if c not in daily:
            daily[c] = D[c]
    for c in ("s30_2x", "s50_2x"):
        daily[f"{c}_candle"] = Dc[c]
    daily.to_parquet(os.path.join(OUT, "daily.parquet"))
    # ---- gates (2x binding; the rest for information)
    g2 = gates.path_b({30000: D.s30_2x, 50000: D.s50_2x}, days=days)
    N, v_plain = gates.n_trials(robust=False)
    g2["dsr_plain_variance"], g2["sr0_plain_variance"] = gates.deflated_sharpe(
        0 * D.s30_2x + (g2["a"] * gates.incumbent(g2["a"] * 100e3, days=days)
                        + (1 - g2["a"]) * (D.s30_2x if g2["a"] == 0.7 else D.s50_2x)), N, v_plain)
    g2["vz_robust"], g2["vz_plain"] = gates.n_trials()[1], v_plain
    g1 = gates.path_b({30000: D.s30_1x, 50000: D.s50_1x}, days=days)
    gth = gates.path_b({30000: D["s30_th0.25_2x"], 50000: D["s50_th0.25_2x"]}, days=days)
    gc = gates.path_b({30000: Dc.s30_2x, 50000: Dc.s50_2x}, days=days)
    sens = {}
    for fee in ("0.12", "0.30"):
        r = gates.path_b({30000: D[f"s30_2x_fee{fee}"], 50000: D[f"s50_2x_fee{fee}"]}, days=days)
        sens[fee] = {k: r[k] for k in ("full_t_alpha", "hold_t_alpha", "full_gain", "hold_gain", "dsr", "G1", "G2",
                                       "G3", "G4", "G5")}
    inc = gates.incumbent(100e3, days=days)
    pa = None
    if gates.sharpe(D.s100_2x) > gates.sharpe(inc):
        pa = gates.path_a(D.s100_2x, days=days)
    # ---- checks
    T = gate_T[(30000, 0.5)]
    Pn = mj.trade_pnl(T, 2.0)
    T = T.assign(net_bp=Pn.net_bp.to_numpy(), pnl=Pn.pnl.to_numpy(), year=T.fill_ts.dt.year,
                 period=np.where(T.fill_ts >= gates.HOLD0, "HOLD", "DEV"))
    s = D.s30_2x
    top = s.sort_values(ascending=False)
    worst10 = inc.sort_values().head(10).index
    act_s, act_i = s != 0, inc != 0
    cf = confs[(30000, 0.5)]
    U = pd.read_parquet(os.path.join(FULL, "unit_fills.parquet"))
    chk = dict(
        fills_by_year_coin={f"{y}|{c}": int(n) for (y, c), n in T.groupby(["year", "coin"]).size().items()},
        net_bp_by_year_coin={f"{y}|{c}": round(float(v), 1) for (y, c), v in T.groupby(["year", "coin"]).net_bp.mean().items()},
        pnl_by_year_coin_usd={f"{y}|{c}": round(float(v), 0) for (y, c), v in T.groupby(["year", "coin"]).pnl.sum().items()},
        venue={v: dict(trades=int((T.venue == v).sum()), net_bp_mean=float(T[T.venue == v].net_bp.mean()))
               for v in ("spot", "perp")},
        period={p: dict(trades=int((T.period == p).sum()), net_bp_mean=float(T[T.period == p].net_bp.mean()))
                for p in ("DEV", "HOLD")},
        print_confirmation=dict(rows=int(len(cf)), status=cf.status.value_counts().to_dict() if len(cf) else {},
                                size_ratio_median=float((cf.p_qty / cf.cand_qty)[cf.p_qty > 0].median()) if len(cf) else None,
                                exit_px_diff_bp_median=float(((cf.p_x_px / cf.cand_x_px - 1) * 1e4).median())
                                if len(cf) and "p_x_px" in cf else None,
                                tp_share_candle=float(cf.cand_tp_share.mean()) if len(cf) and "cand_tp_share" in cf else None,
                                tp_share_prints=float(cf.p_tp_share.mean()) if len(cf) and "p_tp_share" in cf else None),
        cascade_low=dict(fill_above_low_bp_median=float(((T.bid / T.low - 1) * 1e4).median()),
                         within_10bp_share=float(((T.bid / T.low - 1) * 1e4 <= 10).mean()),
                         unit_fill_above_low_bp_median=float(U.low_dist_bp.median())),
        top3_share=float(top.head(3).sum() / s.sum()) if s.sum() != 0 else None,
        corr_incumbent=float(np.corrcoef(s, inc)[0, 1]),
        same_day_overlap=dict(sleeve_active_days=int(act_s.sum()),
                              share_with_incumbent_active=float((act_s & act_i).sum() / max(1, act_s.sum()))),
        on_incumbent_worst10=dict(days=[str(x.date()) for x in worst10], sleeve_sum=float(s.reindex(worst10).sum()),
                                  incumbent_sum=float(inc.reindex(worst10).sum())),
        capacity=dict(median_notional=float(T.notional.median()), mean_notional=float(T.notional.mean()),
                      full_size_share=float((T.notional >= 0.95 * 30000).mean()),
                      theta025_trades=int(len(gate_T[(30000, 0.25)])),
                      theta025_mean_notional=float(gate_T[(30000, 0.25)].notional.mean())),
        sleeve_years_2x=years(D.s30_2x), sleeve_years_1x=years(D.s30_1x),
        clamp_share=json.load(open(os.path.join(FULL, "full_meta.json")))["clamp"])
    out = dict(idea="h11mj", frozen=F, freeze_commit=fz, path_b_2x=g2, path_b_1x_info=g1, path_b_2x_theta025_info=gth,
               path_b_2x_candle_only_info=gc, fee_sensitivity_2x=sens, path_a=pa, checks=chk,
               g4_note="provisional: G4 is recomputed centrally with the final ledger (robust MAD v_z); the "
                       "pre-registered plain-variance DSR is reported alongside")
    json.dump(out, open(os.path.join(OUT, "gates.json"), "w"), indent=1, default=str)
    keys = ("a", "full_t_alpha", "dev_t_alpha", "hold_t_alpha", "full_gain", "dev_gain", "hold_gain",
            "full_sleeve_sharpe", "hold_sleeve_sharpe", "full_book_sharpe", "full_inc_sharpe", "hold_book_sharpe",
            "hold_inc_sharpe", "dsr", "dsr_plain_variance", "n_trials", "vz_robust", "vz_plain", "years", "G1", "G2",
            "G3", "G4", "G5", "pass_G1_G5")
    print(json.dumps({k: g2[k] for k in keys}, indent=1, default=str))
    print("1x:", {k: round(g1[k], 3) for k in ("full_t_alpha", "hold_t_alpha", "full_gain", "hold_gain")})
    print("theta 0.25:", {k: round(gth[k], 3) for k in ("full_t_alpha", "hold_t_alpha", "full_gain", "hold_gain")})
    print("candle only:", {k: round(gc[k], 3) for k in ("full_t_alpha", "hold_t_alpha", "full_gain", "hold_gain")})
    print("fees:", json.dumps(sens, default=str))
    print("path A:", None if pa is None else {k: pa[k] for k in ("full_t_diff", "hold_t_diff", "G1", "G2", "G3")})
    print(json.dumps(chk, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
