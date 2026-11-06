#!/usr/bin/env python3
"""Adoption bar 3 (reports/wick_v2_prereg.md): the futures-priced check for the shortlisted variants.

Each variant's spot pipeline (levels, features, walk-forward AI, bid mask) is re-run exactly as in run.py and
then executed on Coinbase perp 1-minute candles with core.futures_trades: perp bid = spot level x basis,
perp fill rule, counting only fills where spot also traded through its level (spot-confirmed), realistic
costs, whole contracts, same portfolio rules. Window: each perp from its first full day of data to
2026-11-05 (coins join as their perps list). Also reported on the same coins and window: the spot-priced
result (the haircut) and a strict perp fill (3-tick trade-through, >= 3x our size traded in the minute).
Writes reports/lab/futures_check.csv and futures_daily.parquet.
Usage: python futures_check.py [extra variant names...]"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import run as RUN  # noqa: E402
import variants as VV  # noqa: E402

OUT = RUN.OUT
BASE = "V000 base (v1)"
TAG = ""
if os.environ.get("QUIET") == "1":                   # as the bot trades: no new bids 16:55-18:05 ET
    core.QUIET = (1015, 1085)
    TAG = "_quiet"


def stats(x):
    sd = x.std()
    eq = x.cumsum()
    return dict(sharpe=x.mean() / sd * np.sqrt(365) if sd > 0 else np.nan, ann=x.mean() * 365,
                maxdd=(eq - eq.cummax()).min())


def main():
    t0 = time.time()
    sl = json.load(open(os.path.join(OUT, "shortlist.json")))
    names = list(dict.fromkeys(sl["variants"] + sl.get("ens10", []) + [BASE] + sys.argv[1:]))
    allv = {v["name"]: v for v in VV.VARIANTS + VV.ROUND1B + VV.make_round2()}
    variants = [allv[n] for n in names]
    coins_all = sorted({c for v in variants for b in RUN.expand(v) for c in b[0]["coins"]})
    data = core.Data(coins_all)
    print(f"{len(variants)} variants, data for {len(coins_all)} coins ({time.time() - t0:.0f}s)", flush=True)
    specs = {}
    for v in variants:
        for ls, ex, ai in RUN.expand(v):
            specs.setdefault(RUN.key(ls), (ls, {}))[1][RUN.key((ex, ai))] = (ex, ai)
    cache = {}
    state = {}
    starts = {}
    for lsk, (ls_d, items) in specs.items():
        t1 = time.time()
        ls = core.LevelSet(data, **ls_d)
        X = ls.features()
        lab_cache = {}
        for ik, (ex_d, ai_d) in items.items():
            ex, keep, pred, thr = RUN.build_spec(ls, X, ex_d, ai_d, lab_cache, state)
            spot = RUN.attach_thr(core.simulate(ls, ex, keep=keep, pred=pred), ls, X, thr)
            fut, st = core.futures_trades(ls, ex, keep=keep, pred=pred, thr=thr, confirm=True)
            strict, _ = core.futures_trades(ls, ex, keep=keep, pred=pred, thr=thr, confirm=True, strict=True)
            starts.update(st)
            cache[(lsk, ik)] = {"spot": spot, "perp": fut, "perp_strict": strict}
        print(f"  level set L={ls_d['L']} k={ls_d['k']} ref={ls_d['ref']} side={ls_d['side']}: {len(items)} specs "
              f"({time.time() - t1:.0f}s)", flush=True)
    first = min(starts.values())
    models = ("real", "adv", "base")
    windows = lambda lo0: (("all", lo0, core.HOLD[1]), ("val_part", lo0, core.VAL[1]),  # noqa: E731
                           ("hold_part", core.HOLD[0], core.HOLD[1]))
    rows, daily, trades = [], {}, []
    for v in variants:
        for venue in ("spot_full", "spot", "perp", "perp_strict"):
            src = "spot" if venue == "spot_full" else venue
            parts = [cache[(RUN.key(ls), RUN.key((ex, ai)))][src] for ls, ex, ai in RUN.expand(v)]
            parts = [p for p in parts if len(p)]
            tr = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
            lo0 = core.VAL[0] if venue == "spot_full" else first
            if len(tr) and venue != "spot_full":
                st = tr.coin.map(starts)
                tr = tr[st.notna() & (tr.ts >= st)]
            d, k = RUN.run_portfolio(v, tr, data)
            row = dict(variant=v["name"], venue=venue)
            for model in models:
                x = d[model][d[model].index >= lo0]
                for lab, lo, hi in windows(lo0):
                    for kk, vv in stats(x[(x.index >= lo) & (x.index < hi)]).items():
                        row[f"{lab}_{model}_{kk}"] = vv
                daily[f"{v['name']}|{venue}|{model}"] = d[model]
            row["trades"] = len(k)
            row["per_day"] = len(k) / max(1, (core.HOLD[1] - lo0).days)
            for model in models:
                row[f"net_{model}_bp"] = k[f"netx_{model}"].mean() if len(k) else np.nan
            row["gross_bp"] = k.gross.mean() if len(k) else np.nan
            row["hit"] = (k.netx_real > 0).mean() if len(k) else np.nan
            rows.append(row)
            if len(k):
                trades.append(k.assign(variant=v["name"], venue=venue))
    D = pd.DataFrame(daily)
    if sl.get("ens10"):
        for venue in ("spot_full", "spot", "perp", "perp_strict"):
            lo0 = core.VAL[0] if venue == "spot_full" else first
            row = dict(variant="ENS10 (equal-weight top 10)", venue=venue)
            for model in models:
                e = D[[f"{n}|{venue}|{model}" for n in sl["ens10"]]].mean(axis=1)
                x = e[e.index >= lo0]
                for lab, lo, hi in windows(lo0):
                    for kk, vv in stats(x[(x.index >= lo) & (x.index < hi)]).items():
                        row[f"{lab}_{model}_{kk}"] = vv
            rows.append(row)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, f"futures_check{TAG}.csv"), index=False)
    D.to_parquet(os.path.join(OUT, f"futures_daily{TAG}.parquet"))
    if trades:
        T = pd.concat(trades, ignore_index=True)
        keep_cols = [c for c in ("variant", "venue", "ts", "exit_ts", "coin", "side", "px", "gross", "net_real", "net_adv",
                                 "net_base", "notional", "pred", "thr", "tp", "sig") if c in T]
        T[keep_cols].to_parquet(os.path.join(OUT, f"futures_trades{TAG}.parquet"), index=False)
    pd.set_option("display.width", 260)
    cols = ["variant", "venue", "trades", "gross_bp", "net_real_bp", "net_adv_bp", "hit", "all_real_sharpe",
            "val_part_real_sharpe", "hold_part_real_sharpe", "all_adv_sharpe", "all_base_sharpe", "all_real_ann",
            "all_real_maxdd"]
    print(f"\nspot_full: spot-priced 2025-01-01..2026-11-05; others from {first.date()} (coins join as their perps list)."
          f"{' Quiet window on.' if TAG else ''}")
    print(R[cols].round(3).to_string(index=False))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
