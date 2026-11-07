#!/usr/bin/env python3
"""H13 (PS) DEV trials (reports/hunt/h13ps/SPEC.md): the fixed grid on DEV events only, each logged to the shared
ledger with gates.log_trial(gates.dev_book(sleeve $30K at 2x)). Never opens a HOLD file (sim.load('dev')).

usage: python scripts/hunt/h13ps/dev.py base    9 trials: Mode I H in {5,30,120}; Mode II Delta in {2,60} x H
       python scripts/hunt/h13ps/dev.py ai      1 trial: walk-forward LightGBM filter on the best of the nine
       python scripts/hunt/h13ps/dev.py diag    DEV-only diagnostics (no trial): moves, leak, phases, spreads
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

END = pd.Timestamp("2026-05-31")          # fixed: the DEV stage ends here
TRIALS = os.path.join(sim.OUT, "trials_dev.csv")


def grid():
    g = [dict(variant=f"m1_H{h}", mode=1, H=h, delta=None) for h in sim.HOLDS]
    g += [dict(variant=f"m2_d{d}_H{h}", mode=2, H=h, delta=d) for d in sim.DELTAS for h in sim.HOLDS]
    return g


def score(M, S, v, take=None, log=True, note=""):
    days = sim.dev_days()
    t2 = sim.trades(M, S, v["mode"], v["H"], 2.0, 0.5, v["delta"] or 2, 30000.0, take=take)
    t2 = t2[t2.exit_day <= END] if len(t2) else t2
    s30 = sim.daily(t2, 30000.0, days)
    gates.assert_dev_only(s30)
    book = gates.dev_book(s30)
    scr = gates.dev_screen(s30)
    a70 = sim.alpha70(s30, days)
    ts = sim.scored(t2)
    row = dict(variant=v["variant"], mode=v["mode"], H=v["H"], delta=v["delta"], n_trades=int(len(ts)),
               n_events_bid=None, sleeve_sharpe_2x=scr["sleeve_sharpe"], t_alpha70=a70["t_alpha"],
               t_alpha100=scr["t_alpha"], corr=scr["corr"], dev_book_sharpe=gates.sharpe(book),
               inc_sharpe=gates.sharpe(gates.incumbent(100e3, 0.5, "instant", days)),
               mean_net_bp_2x=float(ts.net.mean() * 1e4) if len(ts) else np.nan,
               median_net_bp_2x=float(ts.net.median() * 1e4) if len(ts) else np.nan,
               mean_gross_bp=float(ts.gross.mean() * 1e4) if len(ts) else np.nan,
               pnl_2x=float(ts.pnl.sum()) if len(ts) else 0.0, usd_traded=float(ts.usd.sum()) if len(ts) else 0.0,
               active_days=scr["active_days"])
    if log:
        gates.log_trial(sim.IDEA, v["variant"], book, note=note or f"H13 PS {v['variant']} DEV, sleeve $30K 2x",
                        t_alpha70=row["t_alpha70"], n_trades=row["n_trades"], sleeve_sharpe=row["sleeve_sharpe_2x"])
    return row, t2, s30


def append(rows):
    T = pd.DataFrame(rows)
    if os.path.exists(TRIALS):
        T = pd.concat([pd.read_csv(TRIALS), T], ignore_index=True)
    T.to_csv(TRIALS, index=False)
    return T


def main():
    what = sys.argv[1]
    M, S = sim.load("dev")
    assert (M.T_ft + pd.Timedelta(hours=3) < gates.HOLD0).all()
    if what == "base":
        rows = []
        for v in grid():
            r, _, _ = score(M, S, v)
            rows.append(r)
            print({k: (round(x, 3) if isinstance(x, float) else x) for k, x in r.items()}, flush=True)
        append(rows)
    elif what == "ai":
        T = pd.read_csv(TRIALS)
        base = T[~T.variant.str.contains("_ai")]
        ok = base[base.n_trades >= 40]
        best = (ok if len(ok) else base).sort_values(["t_alpha70"], ascending=False).iloc[0]
        v = next(g for g in grid() if g["variant"] == best.variant)
        allE = pd.read_csv(sim.EVENTS, parse_dates=["T_lo"])
        allE = allE[allE.in_universe]
        take, qlog = sim.ai_take(M, S, v["mode"], v["H"], v["delta"] or 2, 0.5, allE, end=gates.HOLD0)
        qlog.to_csv(os.path.join(sim.OUT, "ai_quarters_dev.csv"), index=False)
        va = dict(v, variant=v["variant"] + "_ai")
        r, _, _ = score(M, S, va, take=take, note=f"H13 PS {va['variant']} DEV (walk-forward LightGBM on "
                                                   f"{v['variant']}), sleeve $30K 2x")
        print(qlog.to_string())
        print({k: (round(x, 3) if isinstance(x, float) else x) for k, x in r.items()}, flush=True)
        append([r])
    elif what == "diag":
        diag(M, S)


def diag(M, S):
    """DEV-only checks (no trial is scored): events by year, phase durations, gross moves, leak diagnostic, spreads."""
    out = {}
    D = M[M.T_ft + pd.Timedelta(hours=3) <= END + pd.Timedelta(days=1)].copy()
    D["year"] = D.T_lo.dt.year
    out["events_by_year_dev"] = D.groupby("year").size().to_dict()
    out["lo_dur_h_quantiles"] = (D.lo_dur_min / 60).quantile([.1, .25, .5, .75, .9]).round(2).to_dict()
    au = (D.T_lo - D.T_auction).dt.total_seconds() / 60
    out["auction_min_quantiles"] = au.dropna().quantile([.1, .25, .5, .75, .9]).round(1).to_dict()
    lg = lambda a, b: np.log(D[b] / D[a]) * 1e4  # noqa: E731
    mv = {"lo60_to_ft": lg("px_lo60", "px_ft"), "ftm10_to_ft": lg("px_ftm10", "px_ft"),
          "ft_to_ft5": lg("px_ft", "px_ft5"), "ft_to_ft30": lg("px_ft", "px_ft30"),
          "ft_to_ft120": lg("px_ft", "px_ft120")}
    out["moves_bp"] = {k: dict(mean=float(v.mean()), median=float(v.median()), n=int(v.notna().sum()))
                       for k, v in mv.items()}
    out["half_spread_bp"] = {k: dict(median=float(D[f"{k}_hs10any"].median()),
                                     mean=float(D[f"{k}_hs10any"].mean())) for k in ("pre_ft", "post_ft")}
    R = sim._read("rel", ("dev",))
    R = R[R.key.isin(D.key)]
    piv = R.groupby("bin").usd.median()
    out["median_usd_per_min_rel_ft"] = {int(k): float(v) for k, v in piv.items() if -15 <= k <= 15}
    sim.dumpj(out, os.path.join(sim.OUT, "diag_dev.json"))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
