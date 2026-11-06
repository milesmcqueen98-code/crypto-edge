#!/usr/bin/env python3
"""Phase 2 trade list (reports/wick1m_prereg.md, lever E): R2-08's pipeline on the wider Coinbase spot universe.

Differences from Phase 1, all because the $1M book trades on Coinbase spot:
  - universe: the 17 coins + ADA, AVAX and the 19 new coins with 2024 median daily Coinbase volume >= $3M, keeping
    those whose spot tick is <= 3 bp of price on 2025-01-01;
  - fill tick: each coin's spot tick (estimated from its minute prices: the smallest price step seen);
  - the AI's cost label: Coinbase spot at the tier the $1M book reaches in Phase 1 (VIP 1: 6 bp maker, 12.5 bp
    taker) plus a 2 bp half-spread on market exits, no funding.
Everything else is R2-08 unchanged (levels, features, walk-forward LightGBM, 60th-percentile threshold, exits).
Writes reports/wick1m/trades_wide.parquet (+ spot_ticks_wide.csv). Needs ~10 GB of memory (run on GitHub Actions).
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "lab"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import core  # noqa: E402
import run as RUN  # noqa: E402
import variants as VV  # noqa: E402
import wick_sim as ws  # noqa: E402

NEW = ["ADA", "AVAX", "BONK", "SHIB", "FET", "JASMY", "INJ", "SEI", "TIA", "ICP", "STX", "AERO", "OP", "DOT", "ARB",
       "JTO", "UNI", "LDO", "APT", "FIL", "GRT"]
MAKER, TAKER, HS_BP = 6.0, 12.5, 2.0


def est_tick(c):
    d = pd.read_parquet(os.path.join(ROOT, "data", "minute", f"{c}.parquet"), columns=["ts", "close"])
    d = d[(d.ts >= "2024-07-01") & (d.ts < "2025-01-01")]
    px = np.unique(d.close.astype(np.float64).round(12))
    step = np.diff(px)
    step = step[step > 0]
    if len(step) == 0:
        return np.nan, np.nan
    t = float(10 ** np.floor(np.log10(step.min() * 1.0001)))
    last = float(d.close.iloc[-1])
    return t, t / last * 1e4


def patch_costs():
    def costs_bp(c, px, ty, model):
        if model == "real":
            return np.where((ty == 1) | (ty == 4), MAKER, TAKER + HS_BP) + 0.0 * px
        return ORIG_COSTS(c, px, ty, model)

    def entry_cost_bp(c, px, model):
        if model == "real":
            return MAKER + 0.0 * px
        return ORIG_ENTRY(c, px, model)

    core.costs_bp, core.entry_cost_bp = costs_bp, entry_cost_bp


ORIG_COSTS, ORIG_ENTRY = core.costs_bp, core.entry_cost_bp


def main():
    t0 = time.time()
    base = list(core.COINS17)
    rows = []
    for c in base + NEW:
        p = os.path.join(ROOT, "data", "minute", f"{c}.parquet")
        if not os.path.exists(p):
            rows.append(dict(coin=c, tick=np.nan, tick_bp=np.nan, keep=False, note="no data"))
            continue
        t, bp = est_tick(c)
        rows.append(dict(coin=c, tick=t, tick_bp=bp, keep=bool(np.isfinite(bp) and bp <= 3.0)))
    T = pd.DataFrame(rows)
    os.makedirs(os.path.join(ROOT, "reports", "wick1m"), exist_ok=True)
    T.to_csv(os.path.join(ROOT, "reports", "wick1m", "spot_ticks_wide.csv"), index=False)
    coins = [r.coin for r in T.itertuples() if r.keep or r.coin in base]
    print(T.to_string(index=False), flush=True)
    for r in T.itertuples():
        if np.isfinite(r.tick):
            ws.SPOT_TICK[r.coin] = r.tick
            if r.coin not in ws.PERP:
                ws.PERP[r.coin] = (None, 1.0, r.tick)
    ws.spot_tick = lambda c: ws.SPOT_TICK.get(c, ws.PERP[c][2])        # spot execution: spot tick for every coin
    patch_costs()
    allv = {v["name"]: v for v in VV.VARIANTS + VV.ROUND1B + VV.make_round2()}
    v = allv["R2-08 C29+A11"]
    data = core.Data(coins)
    print(f"data for {len(coins)} coins loaded ({time.time() - t0:.0f}s)", flush=True)
    state, lab_cache, parts = {}, {}, []
    for ls_d, ex_d, ai_d in RUN.expand(v):
        ls_d = dict(ls_d, coins=tuple(coins))
        ls = core.LevelSet(data, **ls_d)
        X = ls.features()
        ex, keep, pred, thr = RUN.build_spec(ls, X, ex_d, ai_d, lab_cache, state)
        tr = RUN.attach_thr(core.simulate(ls, ex, keep=keep, pred=pred), ls, X, thr)
        if len(tr):
            tr["k"] = ls.k
            tr["tp_log"] = ex.theta * ls.k * tr.sig
            tr["fair_log"] = np.log(tr.px) + ls.k * tr.sig
            parts.append(tr)
    tr = pd.concat(parts, ignore_index=True).sort_values(["ts", "coin"]).reset_index(drop=True)
    tr["bot"] = False
    out = os.path.join(ROOT, "reports", "wick1m", "trades_wide.parquet")
    tr.to_parquet(out, index=False)
    print(f"{len(tr)} AI-approved trades, {tr.coin.nunique()} coins, {tr.ts.min()} .. {tr.ts.max()} "
          f"({time.time() - t0:.0f}s) -> {out}")
    print(tr.coin.value_counts().to_string())


if __name__ == "__main__":
    main()
