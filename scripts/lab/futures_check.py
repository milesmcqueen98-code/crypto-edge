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


def stats(x):
    sd = x.std()
    eq = x.cumsum()
    return dict(sharpe=x.mean() / sd * np.sqrt(365) if sd > 0 else np.nan, ann=x.mean() * 365,
                maxdd=(eq - eq.cummax()).min())


def main():
    t0 = time.time()
    sl = json.load(open(os.path.join(OUT, "shortlist.json")))
    names = list(dict.fromkeys(sl["variants"] + sl.get("ens10", []) + [BASE] + sys.argv[1:]))
    allv = {v["name"]: v for v in VV.VARIANTS + getattr(VV, "ROUND2", [])}
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
        ls = core.LevelSet(data, ls_d["coins"], L=ls_d["L"], k=ls_d["k"], wsig=ls_d["wsig"], wbeta=ls_d["wbeta"],
                           ref=ls_d["ref"], side=ls_d["side"])
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
    rows, daily = [], {}
    for v in variants:
        for venue in ("spot", "perp", "perp_strict"):
            parts = [cache[(RUN.key(ls), RUN.key((ex, ai)))][venue] for ls, ex, ai in RUN.expand(v)]
            parts = [p for p in parts if len(p)]
            tr = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
            if len(tr):
                st = tr.coin.map(starts)
                tr = tr[st.notna() & (tr.ts >= st)]
            d, k = RUN.run_portfolio(v, tr, data)
            row = dict(variant=v["name"], venue=venue)
            for model in ("real", "base"):
                x = d[model][d[model].index >= first]
                for lab, lo, hi in (("all", first, core.HOLD[1]), ("val_part", first, core.VAL[1]),
                                    ("hold_part", core.HOLD[0], core.HOLD[1])):
                    s = stats(x[(x.index >= lo) & (x.index < hi)])
                    for kk, vv in s.items():
                        row[f"{lab}_{model}_{kk}"] = vv
            row["trades"] = len(k)
            row["net_real_bp"] = k.netx_real.mean() if len(k) else np.nan
            row["hit"] = (k.netx_real > 0).mean() if len(k) else np.nan
            rows.append(row)
            daily[f"{v['name']}|{venue}"] = d["real"]
    R = pd.DataFrame(rows)
    D = pd.DataFrame(daily)
    if sl.get("ens10"):
        for venue in ("spot", "perp", "perp_strict"):
            e = D[[f"{n}|{venue}" for n in sl["ens10"]]].mean(axis=1)
            x = e[e.index >= first]
            row = dict(variant="ENS10 (equal-weight top 10)", venue=venue)
            for lab, lo, hi in (("all", first, core.HOLD[1]), ("val_part", first, core.VAL[1]),
                                ("hold_part", core.HOLD[0], core.HOLD[1])):
                for kk, vv in stats(x[(x.index >= lo) & (x.index < hi)]).items():
                    row[f"{lab}_real_{kk}"] = vv
            rows.append(row)
        R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, "futures_check.csv"), index=False)
    D.to_parquet(os.path.join(OUT, "futures_daily.parquet"))
    pd.set_option("display.width", 250)
    cols = ["variant", "venue", "trades", "net_real_bp", "hit", "all_real_sharpe", "val_part_real_sharpe",
            "hold_part_real_sharpe", "all_real_ann", "all_real_maxdd", "all_base_sharpe"]
    print(f"\nFutures-priced check from {first.date()} (coins join as their perps list), realistic costs:")
    print(R[cols].round(3).to_string(index=False))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
