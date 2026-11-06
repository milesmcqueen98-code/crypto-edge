#!/usr/bin/env python3
"""Audit E3/E4: recompute futures trades by hand from the raw parquet files (no shared code except loading),
and print the candle sequence around futures-only fills."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "audit")
T = pd.read_parquet(os.path.join(OUT, "fut_trades_tagged.parquet"))
T = T[T.ai]
specs = pd.read_csv(os.path.join(ROOT, "reports", "cfm_products.csv"))
specs = specs[specs.expiry_type == "PERPETUAL"].set_index("root")
hsm = pd.read_csv(os.path.join(ROOT, "reports", "cfm_book_summary.csv"))
hsm = hsm[hsm.kind == "perp"].set_index("root").spread_bp_median / 2


def raw(src, c):
    df = pd.read_parquet(os.path.join(ROOT, "data", src, f"{c}.parquet")).set_index("ts").sort_index()
    return df[df.volume > 0].astype(float)


def hand_level(sp, btc, t):
    """Level for minute t from spot closes strictly before t (independent re-implementation)."""
    i = pd.date_range(t - pd.Timedelta(minutes=3 * 4320 + 120), t - pd.Timedelta(minutes=1), freq="min")
    x = np.log(sp.close.reindex(i).ffill(limit=30))
    b = np.log(btc.close.reindex(i).ffill(limit=30))
    rx, rb = x.diff(), b.diff()
    # rolling (3-day) beta at each minute of the last 3 days, using only returns up to that minute
    W = 4320
    mab = (rx * rb).rolling(W, min_periods=1440).mean()
    beta = ((mab - rx.rolling(W, min_periods=1440).mean() * rb.rolling(W, min_periods=1440).mean())
            / rb.rolling(W, min_periods=1440).var()).clip(0, 3)
    e = (x - x.shift(60)) - beta * (b - b.shift(60))
    sig = e.rolling(W, min_periods=1440).std().iloc[-1]
    lvl = np.exp(x.iloc[-60] + beta.iloc[-1] * (b.iloc[-1] - b.iloc[-60]) - 4.0 * sig)
    return lvl, sig


rng = np.random.default_rng(1)
pick = pd.concat([T[~T.spot_reached].sample(4, random_state=3), T[T.spot_reached].sample(2, random_state=3)])
btc = raw("minute", "BTC")
for r in pick.itertuples():
    c = r.coin
    sp, fu = raw("minute", c), raw("cfm", c)
    t = r.ts
    lvl_s, sig = hand_level(sp, btc, t)
    # basis: last futures trade at or before t-1 (ffill limit 30) over spot close at t-1 (ffill)
    fprev = fu.close[:t - pd.Timedelta(minutes=1)]
    fprev = fprev[fprev.index >= t - pd.Timedelta(minutes=31)]
    sprev = sp.close[:t - pd.Timedelta(minutes=1)].iloc[-1]
    basis = fprev.iloc[-1] / sprev
    tick = specs.loc[c, "price_increment"]
    lvl_f = np.floor(lvl_s * basis / tick + 1e-9) * tick
    o, lo = fu.open.get(t, np.nan), fu.low.get(t, np.nan)
    filled = (o > lvl_f) and (lo <= lvl_f * (1 - tick / fu.close[:t].iloc[-1]))
    tp = lvl_f * np.exp(0.6 * 4.0 * sig)
    # walk forward: TP needs high >= tp*(1+tick/close); else exit after 60 min at futures close (or spot x basis)
    ex_t, ex_px, ty = None, None, None
    for k in range(1, 400):
        u = t + pd.Timedelta(minutes=k)
        if u in fu.index:
            h = fu.high[u]
            if h >= tp * (1 + tick / fu.close[u]):
                ex_t, ex_px, ty = u, np.floor(tp / tick + 1e-9) * tick, 1
                break
            if k >= 60:
                ex_t, ex_px, ty = u, fu.close[u], 3
                break
        elif k >= 60:
            fl = fu.close[:u]
            fl = fl[fl.index >= u - pd.Timedelta(minutes=30)]
            last_f = fu.close[:u].index[-1]
            b_last = fu.close[last_f] / sp.close[:last_f].iloc[-1]
            cand = [sp.close[:u].iloc[-1] * b_last] + ([fl.iloc[-1]] if len(fl) else [])
            ex_t, ex_px, ty = u, min(cand), 3
            break
    gross = np.log(ex_px / lvl_f) * 1e4
    net = gross - 2 - (2 if ty == 1 else 2 + hsm[c])
    print(f"\n{c} {t}  spot_reached={r.spot_reached}  sim: ep={r.ep:.6g} xp={r.xp:.6g} type={r.type} exit={r.exit_ts} net={r.net_bp:.1f}")
    print(f"   by hand: spot level {lvl_s:.6g} (sigma {sig * 1e4:.0f} bp, depth {4 * sig * 1e4:.0f} bp), basis {basis:.5f}, "
          f"fut bid {lvl_f:.6g}, fut open {o:.6g}, low {lo:.6g} -> filled={filled}; exit {ex_t} at {ex_px:.6g} type {ty}; "
          f"gross {gross:.1f} net {net:.1f}")
    w = pd.date_range(t - pd.Timedelta(minutes=3), t + pd.Timedelta(minutes=4), freq="min")
    tab = pd.DataFrame({"spot_o": sp.open.reindex(w), "spot_l": sp.low.reindex(w), "spot_c": sp.close.reindex(w),
                        "fut_o": fu.open.reindex(w) / basis, "fut_l": fu.low.reindex(w) / basis,
                        "fut_h": fu.high.reindex(w) / basis, "fut_c": fu.close.reindex(w) / basis,
                        "fut_vol": fu.volume.reindex(w)})
    print("   (futures prices divided by the basis, i.e. in spot units; spot level", f"{lvl_s:.6g})")
    print(tab.to_string(float_format=lambda v: f"{v:.6g}"))
