#!/usr/bin/env python3
"""Edge hunt: the incumbent at $100K (reports/hunt_prereg.md).

The spot bot as it trades (bot/spot): R2-08 signal, $1M rules (4/6/8-sigma ladder in thirds, each signal capped at
0.2% of the coin's trailing ADV, every AI signal, cash <= 100%), Coinbase spot only (perp volume removed from the
fill capacity), VIP tiers from the book's own volume. Two bounds of the live bot and the 1-second bot between them:
  minute  = deeper rungs filled in the parent's own minute dropped (the paper bot);
  instant = all kept (the research simulator);
  poll1s  = minute + s * (instant - minute), s = the measured share at $250K (reports/wick_v4/latency_value.csv).
Writes reports/hunt/incumbent_daily.parquet (daily return on capital, P&L booked on the exit day) and
reports/hunt/incumbent_summary.csv. The precompute pickles are regenerated if missing (not committed).

usage: python scripts/hunt/incumbent.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
import sim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt")
W0 = {4.0: 1, 6.0: 1, 8.0: 1}
CAPS = (50e3, 70e3, 100e3, 250e3)
THETAS = (0.5, 0.25)
ERAS = {"sel": ("main", sim.SEL), "chk": ("main", sim.CHK), "early": ("early", sim.EARLY)}


def load(tag):
    path = os.path.join(ROOT, "reports", "wick1m", f"pre_hunt_{tag}.pkl")
    if not os.path.exists(path):
        sim.precompute(tag, bitstamp=False, out_tag=f"hunt_{tag}")
    P = pd.read_pickle(path)
    for col in ("in_perp", "tp_perp"):          # the spot bot cannot fill on the perp venue
        if col in P:
            P[col] = 0.0
    return P


def run(P, lo, hi, theta, C, drop):
    W = P[(P.ts >= lo) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    Q, daily, info = sim.evaluate(W, kappa=0.002, trade_list="all", theta=theta, C=C, days=days, gross_cap=1.0,
                                  drop_same_minute=drop, weights=W0, use_bitstamp=False)
    idx = pd.date_range(lo, hi, freq="D")
    return daily.reindex(idx, fill_value=0.0) / C, int((Q.fill > 0).sum()), float(Q.fill.sum())


def main():
    lat = pd.read_csv(os.path.join(ROOT, "reports", "wick_v4", "latency_value.csv"))
    pre = {t: load(t) for t in ("main", "early")}
    cols, rows = {}, []
    for era, (tag, (lo, hi)) in ERAS.items():
        P = pre[tag]
        lat_era = {"sel": "selection", "chk": "check", "early": "fresh_2022_23"}[era]
        for theta in THETAS:
            ref = lat[(lat.era == lat_era) & (lat.capital == 250e3) & (lat.theta == theta)].iloc[0]
            share = (ref.poll1s_ret - ref.minute_bot_ret) / (ref.research_ret - ref.minute_bot_ret)
            for C in CAPS:
                d_m, n_m, f_m = run(P, lo, hi, theta, C, True)
                d_i, n_i, f_i = run(P, lo, hi, theta, C, False)
                d_1 = d_m + share * (d_i - d_m)
                for name, d, n, f in (("minute", d_m, n_m, f_m), ("instant", d_i, n_i, f_i), ("poll1s", d_1, n_i, f_i)):
                    key = f"{era}|{int(C)}|{theta}|{name}"
                    cols[key] = d
                    st = sim.period_stats(d * C, C, lo, hi)
                    rows.append(dict(era=era, capital=C, theta=theta, variant=name, fills=n, fill_musd=f / 1e6,
                                     share_1s=share, **{k: st.get(k) for k in ("ret_yr", "sharpe", "maxdd", "dollars_yr",
                                                                              "top3_share", "sharpe_p05", "sharpe_p95")}))
                print(era, theta, int(C), {r["variant"]: round(r["sharpe"], 2) for r in rows[-3:]}, flush=True)
    os.makedirs(OUT, exist_ok=True)
    D = pd.DataFrame(cols)
    D.index.name = "day"
    D.to_parquet(os.path.join(OUT, "incumbent_daily.parquet"))
    S = pd.DataFrame(rows)
    S.to_csv(os.path.join(OUT, "incumbent_summary.csv"), index=False)
    pd.set_option("display.width", 220)
    print(S.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
