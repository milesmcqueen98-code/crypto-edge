#!/usr/bin/env python3
"""BURN, DEV only: pin down the definitions of the parent records' take-profit flag and 60-minute price (structural
checks on the research parents whose 60-minute mark is known before the end of DEV; no HOLD row is read).
usage: python scripts/hunt2/burn/inspect_dev.py sel
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/crypto-edge/scripts/hunt2")
import frozen_sim as F  # noqa: E402

assert sys.argv[1:] == ["sel"], "DEV only: the era argument is fixed to sel"
lo, hi = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-04-01")
P = F.RL.inputs("main")["P"]
P4 = P[(P.k == 4.0) & P.filled]
P4 = P4[(P4.ts >= lo) & (P4.ts + pd.Timedelta(minutes=61) <= hi)].copy()       # outcome known inside DEV
print("DEV research parents (60-minute mark known in DEV):", len(P4))
print("f_off == 0 for every parent:", bool((P4.f_off == 0).all()))
tph = P4.tp_hit.astype(bool)
print("tp_hit == (tp_off >= 0):", bool((tph == (P4.tp_off >= 0)).all()))
print("tp_off range when hit:", int(P4.tp_off[tph].min()), "..", int(P4.tp_off[tph].max()))
L = P4.path.map(len)
print("path lengths:", sorted(L.unique()))
last = P4.path.map(lambda p: float(p[-1]))
print("max |g60 - 1e4 * path[-1]| (bp):", float((P4.g60 - 1e4 * last).abs().max()))
first = P4.path.map(lambda p: float(p[0]))
print("path[0] (close of the fill minute vs level), bp: min", round(1e4 * first.min(), 1), "(the fill minute closes"
      " above or below the level)")
mx = P4.path.map(lambda p: float(np.max(p[1:])))
print("not hit: every close after the fill minute below the take-profit:", bool((1e4 * mx[~tph] < P4.g_tp[~tph]).all()))
# dislocation: lvl4 = fair * exp(-4 sig), lvl6 = fair * exp(-6 sig)  ->  ln(lvl4 / lvl6) = 2 sig; g_tp = 1e4 * 0.6 * 4 sig
P6 = P[(P.k == 6.0) & P.filled][["ts", "coin", "lvl"]].rename(columns={"lvl": "lvl6"})
J = P4.merge(P6, on=["ts", "coin"], how="inner")
D_from_tp = J.g_tp / 0.6
D_from_lvl = 1e4 * 2.0 * np.log(J.lvl / J.lvl6)
print(f"dislocation check on {len(J)} parents with a filled 6-sigma rung: max |g_tp/0.6 - 2 ln(lvl4/lvl6)| = "
      f"{float((D_from_tp - D_from_lvl).abs().max()):.2e} bp")
gap = P4.sort_values(["coin", "ts"]).groupby("coin").ts.diff().dropna()
print("smallest gap between consecutive parents of one coin (min):", float(gap.min() / pd.Timedelta(minutes=1)))
print("parents of one coin within 61 minutes of the previous one:", int((gap < pd.Timedelta(minutes=61)).sum()))
