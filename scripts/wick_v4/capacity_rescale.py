#!/usr/bin/env python3
"""Wick v4 addendum C1, step 3 (local): the return / Sharpe tables with the simulator's entry capacity scaled by R.

usage: capacity_rescale.py R [label] [spot]
With "spot", the perp venue's capacity (in_perp, tp_perp) is removed: the spot bot can only fill on Coinbase spot.
Runs the $1M rules (W0 thirds, kappa 0.002, every signal, cash <= 100%) with in_spot * R for the two bounds of the
live bot: the minute bot (same-minute deeper fills dropped) and the instant bot (all kept). The 1-second bot sits
between them; its value is placed at the same share of the gap as measured at R = 1 (reports/wick_v4/latency_value.csv).
Writes reports/wick_v4/capacity_rescaled.csv.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
import sim  # noqa: E402
from rungs import W, run  # noqa: E402

OUT = os.path.join(ROOT, "reports", "wick_v4")


def main(R, label, spot_only=False):
    P = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", "pre_v4_main.pkl"))
    E = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", "pre_v4_early.pkl"))
    for D in (P, E):
        D["in_spot"] = D["in_spot"] * R
        if spot_only:
            for col in ("in_perp", "tp_perp"):
                if col in D:
                    D[col] = 0.0
    lat = pd.read_csv(os.path.join(OUT, "latency_value.csv"))
    eras = {"selection": (P, sim.SEL), "check": (P, sim.CHK), "fresh_2022_23": (E, sim.EARLY)}
    rows = []
    for era, (D, (lo, hi)) in eras.items():
        for C in (250e3, 500e3, 1e6):
            for theta in (0.5, 0.25):
                st_m, d_m = run(D, W["W0"], lo, hi, theta, C, drop=True)
                st_i, d_i = run(D, W["W0"], lo, hi, theta, C, drop=False)
                ref = lat[(lat.era == era) & (lat.capital == C) & (lat.theta == theta)]
                if len(ref):
                    r0 = ref.iloc[0]
                    share = (r0.poll1s_ret - r0.minute_bot_ret) / (r0.research_ret - r0.minute_bot_ret)
                else:
                    share = 0.85                      # $500K was not in the latency table: S1's P&L share at 1 s
                d_1 = d_m + share * (d_i - d_m)
                st_1 = sim.period_stats(d_1 * C, C, lo, hi)
                rows.append(dict(R=R, label=label, era=era, capital=C, theta=theta,
                                 minute_ret=st_m["ret_yr"], minute_sharpe=st_m["sharpe"],
                                 instant_ret=st_i["ret_yr"], instant_sharpe=st_i["sharpe"],
                                 s1_share=share, poll1s_ret=st_1["ret_yr"], poll1s_sharpe=st_1["sharpe"]))
    out = pd.DataFrame(rows)
    path = os.path.join(OUT, "capacity_rescaled.csv")
    if os.path.exists(path):
        old = pd.read_csv(path)
        out = pd.concat([old[old.label != label], out])
    out.to_csv(path, index=False)
    pd.set_option("display.width", 250)
    print(out[out.label == label].round(3).to_string(index=False))


if __name__ == "__main__":
    main(float(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else f"R={sys.argv[1]}",
         len(sys.argv) > 3 and sys.argv[3] == "spot")
