#!/usr/bin/env python3
"""H4 (NL) DEV trial grid (SPEC: 12 core + H=30 for the best + 2 AI = 15 trials). Reads only cand_dev (no minute on
or after 2026-06-01 exists in it), scores only DEV days, logs every trial with gates.log_trial (run locally: the shared
ledger is file-locked on this machine).

  python scripts/hunt/h4nl/dev_trials.py core | h30 | ai | table
"""
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

IDEA = "h4nl"
TAB = os.path.join(sim.OUT, "trials_dev.csv")
MIN_TRADES = 40


def core_grid():
    return [dict(k=k, win=w, liq=liq, H=60) for k in (3.0, 4.0, 6.0) for w in (7, 30) for liq in (False, True)]


def run(v, C, L, keep=None, log=True, note=""):
    days = sim.dev_days()
    drop = L.pid[L.t0.dt.year == 2024].tolist()                 # 2024 listings only train the AI
    q = sim.candidates(C, L, v, keep=keep)
    out = {}
    for cap in (30000, 50000):
        for mult in (2.0, 1.0):
            T, d = sim.simulate(q, L, v, cap, theta=0.5, mult=mult, drop_pids=drop)
            r = sim.daily_returns(d, cap, days)
            gates.assert_dev_only(r)
            out[(cap, mult)] = (T, r)
    T30, r30 = out[(30000, 2.0)]
    T30 = T30[T30.t_x.dt.floor("D").isin(days) | T30.ts.dt.floor("D").isin(days)] if len(T30) else T30
    ri70 = gates.incumbent(70e3, days=days)
    scr = gates.dev_screen(r30, ri=ri70)
    book = gates.dev_book(r30)
    row = dict(variant=sim.variant_name(v), **{k_: v[k_] for k_ in ("k", "win", "liq", "H")}, ai=v.get("ai", ""),
               trades=int(len(T30)), listings=int(T30.pid.nunique()) if len(T30) else 0,
               sleeve_sharpe=scr["sleeve_sharpe"], t_alpha=scr["t_alpha"], appraisal=scr["appraisal"],
               corr=scr["corr"], beta=scr["beta"], active_days=scr["active_days"],
               dev_book_sharpe=gates.sharpe(book), dev_inc_sharpe=gates.sharpe(gates.incumbent(100e3, days=days)),
               pnl30_2x=float(r30.sum() * 30000), pnl30_1x=float(out[(30000, 1.0)][1].sum() * 30000),
               sharpe30_1x=gates.sharpe(out[(30000, 1.0)][1]), pnl50_2x=float(out[(50000, 2.0)][1].sum() * 50000),
               filled_usd=float(T30.fill.sum()) if len(T30) else 0.0,
               net_bp=float(1e4 * T30.pnl.sum() / T30.fill.sum()) if len(T30) else np.nan,
               tp_share=float(T30.tp_fill.sum() / T30.fill.sum()) if len(T30) else np.nan)
    if log:
        lg = gates.log_trial(IDEA, row["variant"], book, note=note or "DEV a=0.7 book, sleeve $30K at 2x",
                             t_alpha=row["t_alpha"], trades=row["trades"], sleeve_sharpe=row["sleeve_sharpe"])
        row["logged"] = lg["time"]
    return row


def save(rows):
    old = pd.read_csv(TAB) if os.path.exists(TAB) else pd.DataFrame()
    new = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
    os.makedirs(sim.OUT, exist_ok=True)
    new.to_csv(TAB, index=False)
    return new


def best(tab):
    ok = tab[tab.trades >= MIN_TRADES].copy()
    if ok.empty:
        return None
    ok["simple"] = ok.ai.fillna("").eq("").astype(int) * 2 + (ok.H == 60).astype(int) + (~ok.liq.astype(bool)).astype(int)
    return ok.sort_values(["t_alpha", "simple"], ascending=[False, False]).iloc[0]


def show(tab):
    cols = ["variant", "trades", "listings", "sleeve_sharpe", "t_alpha", "corr", "dev_book_sharpe", "pnl30_2x",
            "pnl30_1x", "net_bp", "tp_share"]
    print(tab[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    step = sys.argv[1]
    C, L = sim.load("dev")
    if step == "core":
        rows = [run(v, C, L) for v in core_grid()]
        show(save(rows))
    elif step == "h30":
        tab = pd.read_csv(TAB)
        b = best(tab[tab.ai.fillna("") == ""])
        v = dict(k=float(b.k), win=int(b.win), liq=bool(b.liq), H=30)
        print("best core:", b.variant)
        show(save([run(v, C, L, note=f"H=30 for the best core variant {b.variant}")]))
    elif step == "ai":
        tab = pd.read_csv(TAB)
        b = best(tab[tab.ai.fillna("") == ""])
        base = dict(k=float(b.k), win=int(b.win), liq=bool(b.liq), H=int(b.H))
        q_all = sim.candidates(C, L, base)                       # all listings incl. 2024 (training)
        rows = []
        for rule in ("pos", "med"):
            keep, pred = sim.ai_keep(q_all, rule)
            v = dict(base, ai=rule)
            print(rule, "kept", len(keep), "of", len(q_all), "candidates")
            rows.append(run(v, C, L, keep=keep, note=f"walk-forward LightGBM filter ({rule}) on {b.variant}"))
        show(save(rows))
    elif step == "table":
        tab = pd.read_csv(TAB)
        show(tab)
        b = best(tab)
        print("SELECTED:", b.variant, "t_alpha", round(b.t_alpha, 3), "trades", b.trades)
