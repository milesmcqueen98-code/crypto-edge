#!/usr/bin/env python3
"""Breadth: the AI-filtered resting-bid dip buyer on a wider universe of Coinbase-perp-listed coins.

Universe rule fixed before looking at results (implementability only): a Coinbase US perp exists, its
tick is <= 3 bp of price, one contract is >= $150, 24h perp volume >= $1M (product listing, 6 Nov 2026).
  -> ETH SOL XRP DOGE LTC LINK  + BCH SUI XLM HBAR NEAR AAVE HYPE ENA PEPE ONDO ZEC
Same walk-forward protocol as wick_ai (quarterly expanding-window LightGBM, first model on 2024 only,
bid off when prediction <= training median), simulated on spot 1-minute data with futures ticks.
Writes reports/wick_breadth.csv, reports/wick_breadth_trades.parquet
"""
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge import wick  # noqa: E402
import wick_futures as wf  # noqa: E402
import wick_robust as wr  # noqa: E402
import wick_sim as ws  # noqa: E402

CORE = ["ETH", "SOL", "XRP", "DOGE", "LTC", "LINK"]
WIDE16 = CORE + ["BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE", "ENA", "PEPE", "ONDO"]
WIDE = WIDE16 + ["ZEC"]          # ZEC also passes the rule; it was missed in the first pass


def evaluate(coins, tag):
    t0 = time.time()
    coins = [c for c in coins if os.path.exists(os.path.join(ROOT, "data", "minute", f"{c}.parquet"))]
    idx, D = ws.load_ohlc(coins=["BTC"] + coins)
    cf_ = {c: D[c]["cf"] for c in D}
    LV = wick.levels(cf_, coins)
    cands = wf.spot_candidates(D, LV, coins)
    pn = wick.panel(cf_, {c: D[c]["vol"] for c in D}, coins, idx, keep_rows=cands)
    X = wf.spot_training_set(D, pn, idx, coins, lv=LV, cands=cands)
    models = wf.quarterly_models(X)
    trs = []
    for c in coins:
        o, hh, lo, cf = (D[c][k] for k in ("open", "high", "low", "cf"))
        lvl, sig = LV[c][0].copy(), LV[c][1]
        tick = np.nan_to_num(ws.PERP[c][2] / cf, nan=1.0)
        cand = cands[c]
        keep_rule = np.ones(len(idx), dtype=bool)
        test_c = cand[idx[cand] >= ws.TEST_START]
        if len(test_c):
            qs = pd.PeriodIndex(idx[test_c], freq="Q")
            feats = pn[c].loc[idx[test_c]][wick.FEATS]
            for q in np.unique(qs):
                m, thr = models[q]
                keep_rule[test_c[qs == q]] = m.predict(feats[qs == q]) > thr
        for name, mask in [("rule only", None), ("rule + AI", keep_rule)]:
            lv = lvl.copy()
            lv[: idx.get_indexer([pd.Timestamp(ws.TEST_START)])[0]] = np.nan      # evaluate the test period only
            if mask is not None:
                lv[~mask] = np.nan
            ei, xi, ep, xp, ty = ws.run_book(o, hh, lo, cf, lv, wick.THETA * wick.K * sig, np.full(len(idx), np.nan),
                                             1, tick, wick.H, 0)
            gross = np.log(xp / ep) * 1e4
            hs = ws.PERP[c][2] / ep * 1e4
            net = gross - 2.0 - np.where(ty == 1, 2.0, 2.0 + hs)
            trs.append(pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "strategy": name, "net_bp": net,
                                     "gross_bp": gross, "type": ty}))
    T = pd.concat(trs, ignore_index=True)
    rows = []
    for name in ("rule only", "rule + AI"):
        tr = T[T.strategy == name]
        d = wr.daily(tr).loc[ws.TEST_START:]
        s = wr.sstats(d, wr.TST)
        yrs = {f"sharpe_{y}": d[d.index.year == y].mean() / d[d.index.year == y].std() * np.sqrt(365) for y in (2025, 2026)}
        rows.append(dict(universe=tag, n_coins=len(coins), strategy=name, trades=len(tr),
                         per_day=len(tr) / len(d), net_bp=tr.net_bp.mean(), hit=(tr.net_bp > 0).mean(),
                         worst_day=d.min(), **s, **yrs))
    per_coin = T[T.strategy == "rule + AI"].groupby("coin").agg(trades=("net_bp", "size"), net_bp=("net_bp", "mean"),
                                                                hit=("net_bp", lambda x: (x > 0).mean()))
    print(f"[{tag}] {len(coins)} coins, {len(X)} spot candidates, {time.time() - t0:.0f}s")
    print(per_coin.round(2).to_string())
    return rows, T.assign(universe=tag)


def main():
    rows, trades = [], []
    for coins, tag in [(CORE, "core 6"), (WIDE16, "wide 16"), (WIDE, "wide 17")]:
        r, T = evaluate(coins, tag)
        rows += r
        trades.append(T)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(ROOT, "reports", "wick_breadth.csv"), index=False)
    pd.concat(trades).to_parquet(os.path.join(ROOT, "reports", "wick_breadth_trades.parquet"), index=False)
    pd.set_option("display.width", 250)
    print(R.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
