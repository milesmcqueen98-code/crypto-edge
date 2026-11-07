#!/usr/bin/env python3
"""H11 (MJ): DEV table, trial logging (local only: the shared ledger is file-locked) and the selection.
Reads reports/hunt/h11mj/dev/ (DEV days only; produced by `mj.py dev` on Actions).

  python scripts/hunt/h11mj/dev_log.py show        print the DEV table and the selection (no logging)
  python scripts/hunt/h11mj/dev_log.py log         log all 12 trials once (gates.log_trial, idea "h11mj")
  python scripts/hunt/h11mj/dev_log.py freeze      write reports/hunt/h11mj/frozen.json for the selected trial
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HUNT = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(HUNT))
sys.path.insert(0, HUNT)
import gates  # noqa: E402

IDEA = "h11mj"
OUT = os.path.join(ROOT, "reports", "hunt", IDEA)
DEV = os.path.join(OUT, "dev")


def load():
    M = json.load(open(os.path.join(DEV, "dev_meta.json")))
    d = pd.read_parquet(os.path.join(DEV, "dev_daily.parquet"))
    T = pd.read_parquet(os.path.join(DEV, "dev_trades.parquet"))
    assert d.index.max() < gates.HOLD0 and (T.fill_ts < gates.HOLD0).all()
    assert (T.x_ts.fillna(T.tp_ts) < gates.HOLD0).all()
    return M, d, T


def parse(v):
    p = v.split("_")
    return dict(k=float(p[0][1:]), H=int(p[1][1:]), universe=p[2], ai=p[3][2:] if len(p) > 3 else "")


def table(M, d, T):
    inc70 = gates.incumbent(70e3, days=d.index)
    rows = []
    for v in M["trials"]:
        s30 = d[f"{v}|30000|0.5|2x"]
        gates.assert_dev_only(s30)
        scr = gates.dev_screen(s30)
        bk = gates.dev_book(s30)
        tr = T[T.variant == v]
        yrs = len(s30) / 365.25
        rows.append(dict(variant=v, **parse(v), trades=len(tr), sleeve_sharpe_2x=scr["sleeve_sharpe"],
                         t_alpha_inc70=gates.alpha_test(s30, inc70)["t_alpha"], t_alpha_inc100=scr["t_alpha"],
                         corr=scr["corr"], active_days=scr["active_days"], book_sharpe=gates.sharpe(bk),
                         ret_yr_2x=float(s30.sum() / yrs), ret_yr_1x=float(d[f"{v}|30000|0.5|1x"].sum() / yrs),
                         sleeve_sharpe_th025=gates.sharpe(d[f"{v}|30000|0.25|2x"]),
                         perp_trades=int((tr.venue == "perp").sum()),
                         mean_notional=float(tr.notional.mean()) if len(tr) else np.nan))
    return pd.DataFrame(rows)


def select(tab):
    e = tab[tab.trades >= 40].copy()
    e["simple"] = (e.ai != "").astype(int) * 2 + (e.k == 9).astype(int)         # ties go to the simpler variant
    e = e.sort_values(["t_alpha_inc70", "simple"], ascending=[False, True])
    return e.iloc[0]


def main():
    M, d, T = load()
    tab = table(M, d, T)
    pd.set_option("display.width", 250)
    print(tab.drop(columns=["k", "H", "universe", "ai"]).round(3).to_string(index=False))
    best = select(tab)
    print("best core (stage 2 base, chosen on the runner):", M["best_core"])
    print("selection:", best.variant, "t_alpha_inc70", round(best.t_alpha_inc70, 3), "trades", int(best.trades))
    tab.to_csv(os.path.join(DEV, "dev_table.csv"), index=False)
    mode = sys.argv[1] if len(sys.argv) > 1 else "show"
    if mode == "log":
        flag = os.path.join(DEV, "logged.json")
        if os.path.exists(flag):
            raise SystemExit("already logged: " + open(flag).read())
        out = []
        for r in tab.itertuples():
            bk = gates.dev_book(d[f"{r.variant}|30000|0.5|2x"])
            note = (f"deep hourly bid P*exp(-{r.k:g} sigma_1h), H{r.H}, {r.universe}"
                    + (f", AI filter ({'book' if r.ai == 'a' else 'unit'} fills)" if r.ai else ""))
            out.append(gates.log_trial(IDEA, r.variant, bk, note=note, trades=int(r.trades),
                                       sleeve_sharpe_2x=round(float(r.sleeve_sharpe_2x), 4),
                                       t_alpha_inc70=round(float(r.t_alpha_inc70), 4)))
        pd.DataFrame(out).to_csv(os.path.join(DEV, "dev_trials.csv"), index=False)
        json.dump(dict(n=len(out), ledger=gates.LEDGER, time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                  open(flag, "w"))
        print(f"logged {len(out)} trials to {gates.LEDGER}")
    if mode == "freeze":
        if not os.path.exists(os.path.join(DEV, "logged.json")):
            raise SystemExit("log the trials first")
        commit = subprocess.run(["git", "-C", ROOT, "log", "--format=%H", "-1", "--", "scripts/hunt/h11mj/mj.py"],
                                capture_output=True, text=True).stdout.strip()
        F = dict(idea=IDEA, variant=best.variant,
                 params=dict(k=float(best.k), H=int(best.H), universe=best.universe, ai=best.ai),
                 rule="highest DEV alpha t (sleeve $30K at 2x on the incumbent at $70K) among trials with >= 40 trades",
                 code_commit=commit, dev=dict(t_alpha_inc70=float(best.t_alpha_inc70),
                                              t_alpha_inc100=float(best.t_alpha_inc100), trades=int(best.trades),
                                              sleeve_sharpe_2x=float(best.sleeve_sharpe_2x),
                                              book_sharpe_a07=float(best.book_sharpe), corr=float(best.corr),
                                              ret_yr_2x=float(best.ret_yr_2x), ret_yr_1x=float(best.ret_yr_1x)),
                 best_core=M["best_core"], n_trials_logged=int(len(tab)),
                 gate_series="candle fills before each perp launch; perp prints for every post-launch trade "
                             "(mj.py docstring, fixed before the DEV run)",
                 written=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        json.dump(F, open(os.path.join(OUT, "frozen.json"), "w"), indent=1)
        print(json.dumps(F, indent=1))


if __name__ == "__main__":
    main()
