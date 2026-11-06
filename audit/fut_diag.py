#!/usr/bin/env python3
"""Audit E4: where does the futures-over-spot P&L come from? Tags each base futures trade (from fut_trades.pkl,
identical to reports/wick_futures_trades.parquet) by what spot did in the fill minute, the futures minute
volume vs our order size, how far the futures low sat below the spot-implied price, and time to take-profit."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.argv = sys.argv[:1]
from edge import wick  # noqa: E402
import wick_futures as wf  # noqa: E402
import wick_sim as ws  # noqa: E402

OUT = os.path.join(ROOT, "audit")
with open(os.path.join(OUT, "fut_trades.pkl"), "rb") as fh:
    TR = pickle.load(fh)
COINS = sorted(TR["base (reproduces wick_futures)", True].coin.unique())
idx, D = ws.load_ohlc(coins=["BTC"] + COINS)
cf = {c: D[c]["cf"] for c in D}
LV = wick.levels(cf, COINS)
FS = wf.fut_specs()
fut = {c: wf.load_futures(c, idx) for c in COINS}

rows = []
for ai in (False, True):
    T = TR["base (reproduces wick_futures)", ai]
    T = T[T.ts >= "2025-12-13"].copy()
    out = []
    for c, g in T.groupby("coin"):
        F, S = fut[c], D[c]
        e = g.ei.to_numpy()
        lvl_s = LV[c][0][e]
        traded = np.isfinite(F["close"])
        b_last = pd.Series(np.where(traded, F["close"] / S["cf"], np.nan)).ffill().to_numpy()
        bclean = b_last[e - 1]
        size_f = FS[c][1]
        need = np.ceil(2500.0 / (size_f * g.ep.to_numpy()))
        g = g.assign(spot_low_vs_lvl_bp=np.log(S["low"][e] / lvl_s) * 1e4,
                     spot_reached=(S["low"][e] <= lvl_s),
                     fut_low_vs_spot_implied_bp=np.log(F["low"][e] / (S["low"][e] * bclean)) * 1e4,
                     fut_vol=F["vol"][e], need=need, vol_over_need=F["vol"][e] / need,
                     fut_traded_prev=np.isfinite(F["close"][e - 1]),
                     mins_since_fut_trade=[(e_ - np.flatnonzero(traded[:e_])[-1]) if traded[:e_].any() else 9999 for e_ in e],
                     hold=g.xi - g.ei)
        out.append(g)
    T = pd.concat(out)
    T["ai"] = ai
    rows.append(T)
T = pd.concat(rows)
T.to_parquet(os.path.join(OUT, "fut_trades_tagged.parquet"))
pd.set_option("display.width", 250)
for ai in (False, True):
    x = T[T.ai == ai]
    print(f"\n=== futures, {'rule + AI' if ai else 'rule only'}, all 17 perps from 2025-12-13: {len(x)} trades, "
          f"total net {x.net_bp.sum() / 1e4 * 0.25:.3f} (fraction of capital at 0.25x)")
    grp = x.groupby(np.where(x.spot_reached, "spot also reached its level", "futures-only wick"))
    print(grp.agg(trades=("net_bp", "size"), net_bp=("net_bp", "mean"), tp_share=("type", lambda s: (s == 1).mean()),
                  total_pnl=("net_bp", lambda s: s.sum() / 1e4 * 0.25),
                  med_fut_low_vs_spot_bp=("fut_low_vs_spot_implied_bp", "median"),
                  med_spot_low_vs_lvl_bp=("spot_low_vs_lvl_bp", "median"),
                  med_vol_over_need=("vol_over_need", "median"), share_vol_lt_need=("vol_over_need", lambda s: (s < 1).mean()),
                  med_tp_hold=("hold", lambda s: s[x.loc[s.index, "type"] == 1].median())).round(3).to_string())
    # by how far spot stayed above its level
    b = pd.cut(x.spot_low_vs_lvl_bp, [-1e9, 0, 25, 50, 100, 200, 1e9])
    print("by spot low minus spot level (bp) in the fill minute:")
    print(x.groupby(b, observed=True).agg(trades=("net_bp", "size"), net_bp=("net_bp", "mean"),
                                          total_pnl=("net_bp", lambda s: s.sum() / 1e4 * 0.25)).round(3).to_string())
    print("by minutes since previous futures trade (staleness of the basis):")
    b2 = pd.cut(x.mins_since_fut_trade, [0, 1, 2, 5, 10, 30, 1e9])
    print(x.groupby(b2, observed=True).agg(trades=("net_bp", "size"), net_bp=("net_bp", "mean"),
                                           total_pnl=("net_bp", lambda s: s.sum() / 1e4 * 0.25)).round(3).to_string())
    print("by futures volume in the fill minute / our order size (contracts):")
    b3 = pd.cut(x.vol_over_need, [0, 1, 3, 10, 30, 1e9])
    print(x.groupby(b3, observed=True).agg(trades=("net_bp", "size"), net_bp=("net_bp", "mean"),
                                           total_pnl=("net_bp", lambda s: s.sum() / 1e4 * 0.25)).round(3).to_string())
    print("by coin:")
    print(x.groupby(["coin", "spot_reached"]).agg(trades=("net_bp", "size"), net_bp=("net_bp", "mean")).unstack().round(1).to_string())
