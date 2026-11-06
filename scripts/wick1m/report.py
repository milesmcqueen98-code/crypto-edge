#!/usr/bin/env python3
"""Final report for the wick catcher at $1M (reports/wick1m_prereg.md). Opens the check period (WICK1M_CHECK=1).

The fixed Phase 1 rule (20 bp size cap, 4/6/8 sigma ladder, market exit at 60 minutes, every AI-approved signal,
gross <= 100%) and the current rules, on: Phase 1 (17 coins, Coinbase spot + perp), + Bitstamp, and Phase 1 + 2
(wider spot universe + Bitstamp). Selection and check periods, theta 0.5 and 0.25, capacity curve, months,
correlation with C3. Writes reports/wick1m/report.csv, curve.csv, monthly.csv, daily_final.parquet.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402

RULE = dict(kappa=0.002, ladder=True, exit_rule="E0", trade_list="all")
BASE = dict(kappa=None, ladder=False, exit_rule="E0", trade_list="bot")
BOOKS = {"Phase 1: 17 coins": "main", "Phase 1 + Bitstamp": "main_bs", "Phase 1 + 2: wide universe + Bitstamp": "wide"}
CAPS = [100e3, 250e3, 500e3, 1e6, 2e6, 5e6]


def window(P, lo, hi):
    return P[(P.ts >= lo) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]


def run(P, cfg, lo, hi, theta, C, mtm=True, **kw):
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    Q, daily, info = sim.evaluate(window(P, lo, hi), theta=theta, C=C, days=days, gross_cap=1.0, mtm=mtm, **cfg, **kw)
    st = sim.period_stats(daily, C, lo, hi, equity=info.get("equity"))
    st.update(fills=int((Q.fill > 0).sum()), maker_bp=info["maker_bp"], taker_bp=info["taker_bp"],
              v30_musd=info["v30"] / 1e6, fill_usd=float(Q.fill.sum()))
    return st, daily


def main():
    if not sim.CHECK_OPEN:
        sys.exit("opens the check period: run with WICK1M_CHECK=1")
    rows, curve, dailies = [], [], {}
    for bname, tag in BOOKS.items():
        p = os.path.join(sim.OUT, f"pre_{tag}.pkl")
        if not os.path.exists(p):
            print("missing", p)
            continue
        P = pd.read_pickle(p)
        rule_sets = (("$1M rule", RULE),) if tag == "wide" else (("current rules", BASE), ("$1M rule", RULE))
        for cname, cfg in rule_sets:                       # the bot's 6-slot rule exists only for the 17 coins
            for pname, (lo, hi) in (("selection", sim.SEL), ("check", sim.CHK)):
                for th in (0.5, 0.25):
                    st, d = run(P, cfg, lo, hi, th, 1e6)
                    rows.append(dict(book=bname, rules=cname, period=pname, theta=th, **st))
                    if cname == "$1M rule" and th == 0.5:
                        dailies[(bname, pname)] = d
        for sname, kw in (("deeper fills in the parent's minute dropped", dict(drop_same_minute=True)),
                          ("VIP-page fee tiers", dict(tiers=sim.VIP_TIERS))):
            for pname, (lo, hi) in (("selection", sim.SEL), ("check", sim.CHK)):
                st, _ = run(P, RULE, lo, hi, 0.5, 1e6, mtm=False, **kw)
                rows.append(dict(book=bname, rules=f"$1M rule, {sname}", period=pname, theta=0.5, **st))
        for C in CAPS:
            for pname, (lo, hi) in (("selection", sim.SEL), ("check", sim.CHK)):
                st, _ = run(P, RULE, lo, hi, 0.5, C, mtm=False)
                curve.append(dict(book=bname, capital=C, period=pname, **st))
    R = pd.DataFrame(rows)
    K = pd.DataFrame(curve)
    R.to_csv(os.path.join(sim.OUT, "report.csv"), index=False)
    K.to_csv(os.path.join(sim.OUT, "curve.csv"), index=False)
    # monthly returns and correlation with C3 for the final book
    final = [b for b in BOOKS if (b, "check") in dailies][-1]
    d = pd.concat([dailies[(final, "selection")], dailies[(final, "check")]]).sort_index()
    idx = pd.date_range(sim.SEL[0], sim.CHK[1], freq="D")
    r = d.reindex(idx, fill_value=0.0) / 1e6
    r.to_frame("ret").to_parquet(os.path.join(sim.OUT, "daily_final.parquet"))
    (r.groupby(r.index.to_period("M")).sum()).to_frame("ret").to_csv(os.path.join(sim.OUT, "monthly.csv"))
    sys.path.insert(0, os.path.join(sim.ROOT, "scripts"))
    import multiasset as ma  # noqa: E402
    c3, _ = ma.c3_returns("b")
    j = pd.concat([r, c3], axis=1).dropna()
    corr = float(j.corr().iloc[0, 1])
    pd.set_option("display.width", 250)
    show = R.pivot_table(index=["book", "rules", "theta"], columns="period",
                         values=["ret_yr", "sharpe", "maxdd_mtm", "dollars_yr", "sharpe_p05", "sharpe_p95", "top3_share",
                                 "ret_ex_top3"])
    print(show.round(3).to_string())
    print("\ncapacity curve ($1M rule, theta 0.5):")
    print(K.pivot_table(index=["book", "capital"], columns="period", values=["ret_yr", "sharpe", "dollars_yr"]).round(3).to_string())
    print(f"\ndaily correlation with C3, Jan 2025 - Nov 2026 ({final}): {corr:.2f}")
    print("worst month %.1f%%, best month %.1f%%, losing months %d of %d" % (
        100 * r.groupby(r.index.to_period("M")).sum().min(), 100 * r.groupby(r.index.to_period("M")).sum().max(),
        int((r.groupby(r.index.to_period("M")).sum() < 0).sum()), r.index.to_period("M").nunique()))


if __name__ == "__main__":
    main()
