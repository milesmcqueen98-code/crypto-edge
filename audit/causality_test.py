#!/usr/bin/env python3
"""Audit E1: causality of edge.wick.levels / edge.wick.panel / wick_sim.Prep.level.

Row t must depend only on data at positions <= t-1. Test: perturb every input at positions >= t
(prices, volumes, all coins incl. BTC) and check that rows 0..t are bit-identical.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge import wick  # noqa: E402
import wick_sim as ws  # noqa: E402

COINS = ["ETH", "SOL", "DOGE", "PEPE"]
idx, D = ws.load_ohlc(coins=["BTC"] + COINS, start="2025-03-01", end="2025-03-22")
cf = {c: D[c]["cf"] for c in D}
vol = {c: D[c]["vol"] for c in D}
T = len(idx)
rng = np.random.default_rng(0)


def perturb(t):
    cf2 = {c: v.copy() for c, v in cf.items()}
    vol2 = {c: v.copy() for c, v in vol.items()}
    for c in cf2:
        cf2[c][t:] = cf2[c][t:] * np.exp(rng.normal(0, 0.02, T - t))
        vol2[c][t:] = rng.exponential(1000.0, T - t)
    return cf2, vol2


def same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return bool(np.all((a == b) | (np.isnan(a) & np.isnan(b))))


base_lv = wick.levels(cf, COINS)
base_pn = wick.panel(cf, vol, COINS, idx)
bad = []
for t in (16000, 22000, 29000):
    cf2, vol2 = perturb(t)
    lv2 = wick.levels(cf2, COINS)
    pn2 = wick.panel(cf2, vol2, COINS, idx)
    for c in COINS:
        for j, nm in enumerate(("level", "sig")):
            if not same(base_lv[c][j][: t + 1], lv2[c][j][: t + 1]):
                bad.append(("levels", c, nm, t))
            if same(base_lv[c][j][: t + 2], lv2[c][j][: t + 2]):
                pass  # row t+1 is allowed to change (and should)
        for col in base_pn[c].columns:
            if not same(base_pn[c][col].to_numpy()[: t + 1], pn2[c][col].to_numpy()[: t + 1]):
                bad.append(("panel", c, col, t))
        # sanity: row t+1 must react to the perturbation for the price-based columns
        changed = [col for col in base_pn[c].columns
                   if not same(base_pn[c][col].to_numpy()[t + 1: t + 2], pn2[c][col].to_numpy()[t + 1: t + 2])]
        print(f"t={t} {c}: columns that change at row t+1 (expected: price/volume features): {len(changed)}")
    # Prep (wick_sim / wick_ai path)
    D2 = {c: dict(D[c]) | {"cf": cf2[c]} for c in D}
    P1, P2 = ws.Prep(D, (60, 15)), ws.Prep(D2, (60, 15))
    for c in COINS:
        a, b = P1.level(c, 60, 4.0, 1, "resid"), P2.level(c, 60, 4.0, 1, "resid")
        if not (same(a[0][: t + 1], b[0][: t + 1]) and same(a[1][: t + 1], b[1][: t + 1])):
            bad.append(("Prep.level", c, "", t))
print("violations:", bad if bad else "none")

# levels() vs panel() level, and vs Prep.level (should be the same numbers)
P1 = ws.Prep(D, (60,))
for c in COINS:
    a = base_lv[c][0]
    b = base_pn[c].level.to_numpy()
    p = P1.level(c, 60, 4.0, 1, "resid")[0]
    m = np.isfinite(a)
    print(c, "levels==panel:", same(a, b), " max|levels/Prep-1|:", np.nanmax(np.abs(a[m] / p[m] - 1)))

# keep_rows panel == full panel at those rows
kr = {c: np.sort(rng.choice(np.arange(15000, T), 500, replace=False)) for c in COINS}
pk = wick.panel(cf, vol, COINS, idx, keep_rows=kr)
for c in COINS:
    full = base_pn[c].iloc[kr[c]]
    ok = all(same(full[col].to_numpy(), pk[c][col].to_numpy()) for col in full.columns)
    ok_loc = all(same(pk[c].loc[idx[kr[c]]][col].to_numpy(), full[col].to_numpy()) for col in full.columns)
    print(c, "keep_rows panel matches full panel:", ok, ok_loc, " pos column correct:", bool((pk[c].pos.to_numpy() == kr[c]).all()))
