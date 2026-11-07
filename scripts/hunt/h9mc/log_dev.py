#!/usr/bin/env python3
"""H9 (MC): log DEV trials to the shared ledger (gates.log_trial; run locally, it file-locks the ledger) and build
the DEV selection table. Idempotent: a (idea, variant) already in the ledger is not logged again.
  log_dev.py step1             the two Step-1 comparisons (one trial each)
  log_dev.py grid              the 18 Step-2 DEV trials (reports/hunt/h9mc/step2_dev_daily.parquet)
  log_dev.py mirror            the short-mirror trial (reports/hunt/h9mc/step2_dev_mirror_daily.parquet)
  log_dev.py table             write reports/hunt/h9mc/dev_trials.csv (no logging)
Step-1 trials: there is no sleeve, so the logged series is the DEV book with an idle sleeve
(gates.dev_book of zeros over the sleeve's scored DEV days). That adds the two looks to N without putting a test
statistic (not a return) into the ledger's z dispersion; the Step-1 t-stats go in `extra`.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import gates  # noqa: E402

ROOT = gates.ROOT
OUT = os.path.join(ROOT, "reports", "hunt", "h9mc")
IDEA = "h9mc"
DAY0 = pd.Timestamp("2025-07-18")
DEV_DAYS = pd.date_range(DAY0, gates.HOLD0 - pd.Timedelta(days=1), freq="D")


def logged():
    if not os.path.exists(gates.LEDGER):
        return set()
    L = pd.read_csv(gates.LEDGER)
    return set(L.loc[L.idea == IDEA, "variant"])


def sleeve(D, name, cap=30000, mult=2):
    s = D[f"{name}|{cap}|{mult}"].reindex(DEV_DAYS).fillna(0.0)
    gates.assert_dev_only(s)
    return s[s.index < gates.HOLD0]


def stats(s30_2x, trades):
    days = s30_2x.index
    inc70 = gates.incumbent(70e3, 0.5, "instant", days)
    at = gates.alpha_test(s30_2x, inc70)
    scr = gates.dev_screen(s30_2x)
    book = gates.dev_book(s30_2x)
    inc100 = gates.incumbent(100e3, 0.5, "instant", days)
    return dict(dev_sleeve_sharpe=gates.sharpe(s30_2x), dev_alpha_t_inc70=at["t_alpha"],
                dev_alpha_yr_inc70=at["alpha_yr"], dev_beta=at["beta"], screen_t_alpha_inc100=scr["t_alpha"],
                corr_inc=scr["corr"], active_days=scr["active_days"], trades=int(trades),
                dev_book_sharpe=gates.sharpe(book), dev_inc100_sharpe=gates.sharpe(inc100),
                dev_book_gain=gates.sharpe(book) - gates.sharpe(inc100), sleeve_ret_dev=float(s30_2x.sum()))


def log_step1():
    done = logged()
    r = json.load(open(os.path.join(OUT, "step1.json")))
    idle = pd.Series(0.0, index=DEV_DAYS)
    book = gates.dev_book(idle)
    for name, key in (("step1_aggsell_share", "T1_aggsell_pooled"), ("step1_basis_residual", "T2_basis_vw_bp")):
        if name in done:
            print("already logged", name)
            continue
        x = r[key]
        gates.log_trial(IDEA, name, book, note=f"Step-1 mechanism check (no sleeve; idle-sleeve DEV book): 4 pm vs "
                        f"13:30-14:30 control, paired t {x['t']:.2f} (NW {x['t_nw']:.2f}), {x['n']} DEV days",
                        t=x["t"], t_nw=x["t_nw"], mean=x["mean"], n=x["n"], passed=r["pass_step1"])
        print("logged", name)


def log_daily(fname, summ_name):
    done = logged()
    D = pd.read_parquet(os.path.join(OUT, fname))
    S = pd.read_csv(os.path.join(OUT, summ_name))
    for row in S.itertuples():
        name = row.variant
        s = sleeve(D, name)
        st = stats(s, row.trades)
        if name in done:
            print("already logged", name)
            continue
        gates.log_trial(IDEA, name, gates.dev_book(s), note=f"DEV book a=0.7, sleeve $30K at 2x costs; "
                        f"alpha t (inc $70K) {st['dev_alpha_t_inc70']:.2f}, trades {st['trades']}",
                        **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items()},
                        mean_bp_2x=row.mean_bp_2x)
        print("logged", name, round(st["dev_alpha_t_inc70"], 2), st["trades"])


def table():
    rows = []
    for fname, summ in (("step2_dev_daily.parquet", "step2_dev_summary.csv"),
                        ("step2_dev_mirror_daily.parquet", "step2_dev_mirror_summary.csv")):
        if not os.path.exists(os.path.join(OUT, fname)):
            continue
        D = pd.read_parquet(os.path.join(OUT, fname))
        S = pd.read_csv(os.path.join(OUT, summ))
        for row in S.itertuples():
            st = stats(sleeve(D, row.variant), row.trades)
            st1 = gates.sharpe(sleeve(D, row.variant, 30000, 1))
            rows.append(dict(variant=row.variant, **st, dev_sleeve_sharpe_1x=st1, mean_bp_2x=row.mean_bp_2x,
                             mean_bp_1x=row.mean_bp_1x, net2_usd=row.net2_usd,
                             fill_share_of_15k=row.fill_share_of_15k))
    T = pd.DataFrame(rows)
    T["eligible"] = T.trades >= 40
    T.to_csv(os.path.join(OUT, "dev_trials.csv"), index=False, float_format="%.5g")
    pd.set_option("display.width", 250)
    print(T[["variant", "trades", "dev_sleeve_sharpe", "dev_sleeve_sharpe_1x", "dev_alpha_t_inc70",
             "screen_t_alpha_inc100", "dev_book_gain", "mean_bp_2x", "mean_bp_1x", "corr_inc", "eligible"]]
          .round(3).to_string(index=False))
    return T


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "step1":
        log_step1()
    elif mode == "grid":
        log_daily("step2_dev_daily.parquet", "step2_dev_summary.csv")
    elif mode == "mirror":
        log_daily("step2_dev_mirror_daily.parquet", "step2_dev_mirror_summary.csv")
    elif mode == "table":
        table()
