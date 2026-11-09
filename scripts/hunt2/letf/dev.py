#!/usr/bin/env python3
"""Edge hunt 2, LETF: the 12 DEV trials of the SPEC's frozen grid (k in {1, 2} x leg in {mom, rev, mkr} x universe in
{BTC, BTC+ETH+SOL+XRP}), each logged once in the shared ledger (h2gates.log_trial). DEV only (era fixed to sel).

usage: python scripts/hunt2/letf/dev.py sel
Writes reports/hunt2/letf/dev_trials.csv (one row per trial) and dev_daily.parquet (each variant's DEV sleeve on $50K
at 2x and 1x), both DEV-only.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import letf as L  # noqa: E402

G = L.G
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(WT, "reports", "hunt2", "letf")


def trade_stats(T):
    f = T[T.status == "filled"] if len(T) else T
    if len(f) == 0:
        return dict(trades=0)
    g_bp = 1e4 * f.gross / f.notional
    n_bp = 1e4 * f.pnl / f.notional
    return dict(trades=int(len(f)), mean_gross_bp=float(g_bp.mean()), mean_net_bp=float(n_bp.mean()),
                hit=float((f.pnl > 0).mean()), mean_notional=float(f.notional.mean()),
                fill_share=float(f.contracts.sum() / max(1, f.target.sum())),
                status=json.dumps(T.status.value_counts().to_dict()), by_asset=json.dumps(f.asset.value_counts().to_dict()))


def main(era):
    assert era == "sel", "DEV trials run on sel only"
    D = L.signals(era)
    rows, cols = [], {}
    for v in L.VARIANTS:
        name = L.vname(v)
        uni = L.UNIVERSE[v["uni"]]
        days = L.scored_days(uni, era)
        s2, T2 = L.sleeve(D, v["leg"], v["k"], uni, 50000, mult=2.0, theta=0.5, days=days)
        s1, T1 = L.sleeve(D, v["leg"], v["k"], uni, 50000, mult=1.0, theta=0.5, days=days)
        G.assert_dev_only(s2)
        scr2, scr1 = G.dev_screen_b(s2), G.dev_screen_b(s1)
        st2, st1 = trade_stats(T2), trade_stats(T1)
        G.log_trial("letf", name, G.dev_book(s2), "B", scr2["t_alpha"], note="DEV trial, sleeve $50K 2x, theta 0.5",
                    trades=st2.get("trades", 0), sleeve_sharpe=scr2["sleeve_sharpe"], book_gain=scr2["book_gain"])
        row = dict(variant=name, leg=v["leg"], k=v["k"], uni=v["uni"], scored_days=len(days),
                   t_alpha=scr2["t_alpha"], sleeve_sharpe_2x=scr2["sleeve_sharpe"], book_gain_2x=scr2["book_gain"],
                   corr=scr2["corr"], beta=scr2["beta"], active_days=scr2["active_days"],
                   t_alpha_1x=scr1["t_alpha"], sleeve_sharpe_1x=scr1["sleeve_sharpe"], book_gain_1x=scr1["book_gain"],
                   mean_net_bp_1x=st1.get("mean_net_bp", np.nan), pnl_2x=float(s2.sum() * 50000),
                   pnl_1x=float(s1.sum() * 50000))
        row.update(st2)
        rows.append(row)
        cols[f"{name}|2x"], cols[f"{name}|1x"] = s2, s1
        print(f"{name:14s} trades {row.get('trades', 0):4d}  t_alpha {row['t_alpha']:+.2f}  sleeve SR {row['sleeve_sharpe_2x']:+.2f}"
              f"  gross {row.get('mean_gross_bp', np.nan):+.1f} bp  net2x {row.get('mean_net_bp', np.nan):+.1f}"
              f"  net1x {row['mean_net_bp_1x']:+.1f}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "dev_trials.csv"), index=False)
    pd.DataFrame(cols).to_parquet(os.path.join(OUT, "dev_daily.parquet"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sel")
