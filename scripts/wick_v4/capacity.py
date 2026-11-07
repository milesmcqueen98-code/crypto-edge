#!/usr/bin/env python3
"""Wick v4 addendum C1, step 2 (runs on GitHub Actions next to the trade artifacts): is the simulator's fill capacity right?

The simulator caps a fill at theta * V-hat, V-hat being the dollar volume below the bid estimated from minute candles
(volume spread evenly over each minute's range). Here V is measured from the trades themselves on the same minutes
(the fill minute and the next one, the next one only while its low is below the level, as the simulator counts it):
  V      all trades strictly below the bid (at least one tick below the level): sellers that would have reached a
         resting bid at our price before any bid below it, so our queue position at the price doesn't matter;
  V_tk   only taker sells among them (Coinbase's trade side is the maker's: side == "buy");
  V_2s   all trades below the bid from 2 s after the minute start (the live bot's bid goes in a second or two late).
V-hat comes from Coinbase's minute candles (capacity_events.csv, as the simulator used them) and, as a check, from
candles rebuilt from the same trades.

Pre-registered in reports/wick_v4_prereg.md (addendum C1). Writes reports/wick_v4/capacity_out.csv (per-event derived
numbers only) and prints the summary that the workflow saves to reports/wick_v4/capacity_log.txt.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "reports", "wick_v4")
THETA = 0.5
CAPITAL = (250e3, 500e3, 1e6)
SELECTION_END = pd.Timestamp("2026-04-01")
rng = np.random.default_rng(7)


def ticks():
    t = pd.read_csv(os.path.join(ROOT, "reports", "wick1m", "spot_ticks_wide.csv"))
    d = {r.coin: float(r.tick) for r in t.itertuples() if np.isfinite(r.tick)}
    d["PEPE"] = 1e-8
    return d


def vhat_minute(lo, hi, v, level):
    if not np.isfinite(lo) or lo >= level:
        return 0.0
    rng_ = hi - lo
    frac = 1.0 if rng_ <= 0 else min(1.0, (level - lo) / rng_)
    return v * frac * 0.5 * (level + lo)


def boot_ratio(num, den, n=2000):
    num, den = np.asarray(num, float), np.asarray(den, float)
    idx = rng.integers(0, len(num), size=(n, len(num)))
    r = num[idx].sum(1) / den[idx].sum(1)
    return num.sum() / den.sum(), np.percentile(r, 2.5), np.percentile(r, 97.5)


def main(art_dir):
    T = pd.concat([pd.read_parquet(f) for f in glob.glob(os.path.join(art_dir, "**", "trades_*.parquet"), recursive=True)])
    W = pd.read_csv(os.path.join(OUT, "windows.csv"), parse_dates=["start", "end"])
    alt_win = {(r.product.split("-")[0], r.start): r.window_id for r in W[W.kind == "alt"].itertuples()}
    by_win = {w: g.sort_values(["time", "trade_id"]) for w, g in T.groupby("window_id")}
    E = pd.read_csv(os.path.join(OUT, "capacity_events.csv"), parse_dates=["ts"])
    tk = ticks()
    rows = []
    for r in E.itertuples():
        g = by_win.get(alt_win.get((r.coin, r.ts)))
        if g is None or not len(g):
            continue
        tick = tk.get(r.coin, np.nan)
        tt = (g.time - r.ts).dt.total_seconds().to_numpy()
        px, sz = g["price"].to_numpy(), g["size"].to_numpy()
        usd = px * sz
        below = px <= r.lvl - tick * (1 - 1e-9)
        taker_sell = (g["side"] == "buy").to_numpy()
        rec = dict(ts=r.ts, coin=r.coin, k=r.k, bot=r.bot, adv=r.adv, in_spot=r.in_spot,
                   vhat=r.vhat_m0 + r.vhat_m1, n_trades=int((tt < 120).sum()))
        V = V_tk = V_2s = vh_rb = 0.0
        for j in (0, 1):
            m = (tt >= 60 * j) & (tt < 60 * (j + 1))
            if j == 1:                               # the simulator's rule: the next minute counts while its low is below
                if not (np.isfinite(r.low_m1) and r.low_m1 < r.lvl and r.vhat_m0 > 0):
                    continue
            V += usd[m & below].sum()
            V_tk += usd[m & below & taker_sell].sum()
            V_2s += usd[m & below & (tt >= 60 * j + (2 if j == 0 else 0))].sum()
            if m.any():
                vh_rb += vhat_minute(px[m].min(), px[m].max(), sz[m].sum(), r.lvl)
        rec.update(V=V, V_tk=V_tk, V_2s=V_2s, vhat_rebuilt=vh_rb)
        for C in CAPITAL:
            rec[f"want_{int(C / 1e3)}k"] = min(0.25 * C, 0.002 * r.adv) / 3.0
        rows.append(rec)
    D = pd.DataFrame(rows)
    D.to_csv(os.path.join(OUT, "capacity_out.csv"), index=False)
    D["period"] = np.where(D.ts < SELECTION_END, "selection", "check")
    print(f"C1: {len(D)} events with trades ({(D.k == 4).sum()} parents)\n")
    par = D[(D.k == 4) & D.bot]
    print(f"Parent fills the bot takes: {len(par)}. V-hat on these 2 minutes is "
          f"{par.vhat.sum() / par.in_spot.sum():.0%} of the simulator's full capacity (dollar-weighted).\n")
    print("R = trades volume below the bid / simulator estimate, same minutes (dollar-weighted, 95% bootstrap interval):")
    for name, sub in (("selection", par[par.period == "selection"]), ("check", par[par.period == "check"]),
                      ("both", par)):
        print(f"  {name}: {len(sub)} parent fills")
        for col, lab in (("V", "all trades"), ("V_tk", "taker sells"), ("V_2s", "from 2 s")):
            r_, lo, hi = boot_ratio(sub[col], sub.vhat)
            med = (sub[col] / sub.vhat.replace(0, np.nan)).median()
            print(f"  {name:9s} {lab:12s} R {r_:.2f} [{lo:.2f}, {hi:.2f}]  median per event {med:.2f}")
        r_, lo, hi = boot_ratio(sub.vhat_rebuilt, sub.vhat)
        print(f"  {name:9s} {'check: candles rebuilt from trades / Coinbase candles':s} {r_:.2f} [{lo:.2f}, {hi:.2f}]")
    print("\nF(C) = sum min(want, 0.5 V) / sum min(want, 0.5 V-hat): the simulator's 4-sigma fill dollars that trades support")
    for name, sub in (("selection", par[par.period == "selection"]), ("check", par[par.period == "check"]),
                      ("both", par)):
        for C in CAPITAL:
            w = sub[f"want_{int(C / 1e3)}k"]
            sim = np.minimum(w, THETA * sub.vhat)
            bound = (sim < w).mean()
            parts = []
            for col in ("V", "V_tk", "V_2s"):
                f, lo, hi = boot_ratio(np.minimum(w, THETA * sub[col]), sim)
                parts.append(f"{col} {f:.3f} [{lo:.3f}, {hi:.3f}]")
            print(f"  {name:9s} ${C / 1e3:,.0f}K: capacity-bound in the simulator {bound:.0%}; " + "; ".join(parts))
            # supplementary: the simulator's full capacity (up to 15 minutes) with the 2 covered minutes replaced by trades
            full_sim = np.minimum(w, THETA * sub.in_spot)
            full_tr = np.minimum(w, THETA * np.maximum(0.0, sub.in_spot - sub.vhat + sub.V))
            f, lo, hi = boot_ratio(full_tr, full_sim)
            print(f"  {'':9s} {'':6s} supplementary, full capacity with trades on the covered minutes: {f:.3f} [{lo:.3f}, {hi:.3f}]"
                  f"; capacity-bound in the simulator {(full_sim < w).mean():.0%}")
    deep = D[D.k > 4]
    if len(deep):
        print("\nSame-minute 6/8-sigma fills (they share the parent's capacity in the simulator):")
        for k, sub in deep.groupby("k"):
            r_, lo, hi = boot_ratio(sub.V, sub.vhat)
            print(f"  {k:.0f} sigma: {len(sub)} fills, R {r_:.2f} [{lo:.2f}, {hi:.2f}], "
                  f"median {(sub.V / sub.vhat.replace(0, np.nan)).median():.2f}")


if __name__ == "__main__":
    main(sys.argv[1])
