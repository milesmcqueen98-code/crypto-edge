#!/usr/bin/env python3
"""Final check of the deployable configuration: AI-filtered resting bids on the 17-coin perp universe.

  * walk-forward exactly as before (quarterly, expanding window, first model trained on 2024 only),
    repeated with 5 LightGBM seeds to show how much of the result is model noise,
    plus the 5-seed average prediction (threshold = median of the averaged training predictions)
  * portfolio: $2,500 notional per trade on $10,000 (0.25x), uncapped and at most 6 open positions
  * exit-cost stress: market exits pay 3 ticks of spread instead of 1
Writes reports/wick_final.csv and reports/wick_final_trades.parquet (5-seed average, both strategies)
"""
import os
import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge import wick  # noqa: E402
import wick_breadth as wb  # noqa: E402
import wick_futures as wf  # noqa: E402
import wick_sim as ws  # noqa: E402

SEEDS = [7, 11, 23, 42, 101]


def models_for(X, seed):
    out = {}
    for q in pd.period_range("2025Q1", "2026Q4", freq="Q"):
        tr = X[X.ts < q.start_time - pd.Timedelta(days=1)]
        w = 1.0 / tr.groupby(["coin", "episode"]).ts.transform("size")
        m = lgb.train(wick.PARAMS | {"seed": seed}, lgb.Dataset(tr[wick.FEATS], tr.net_bp.clip(-400, 400), weight=w,
                                                               categorical_feature=["coin_id"]), num_boost_round=wick.ROUNDS)
        out[q] = (m, m.predict(tr[wick.FEATS]))
    return out


def main():
    t0 = time.time()
    coins = [c for c in wb.WIDE if os.path.exists(os.path.join(ROOT, "data", "minute", f"{c}.parquet"))]
    idx, D = ws.load_ohlc(coins=["BTC"] + coins)
    cf = {c: D[c]["cf"] for c in D}
    LV = wick.levels(cf, coins)
    cands = wf.spot_candidates(D, LV, coins)
    pn = wick.panel(cf, {c: D[c]["vol"] for c in D}, coins, idx, keep_rows=cands)
    X = wf.spot_training_set(D, pn, idx, coins, lv=LV, cands=cands)
    print(f"{len(coins)} coins, {len(X)} candidates ({time.time() - t0:.0f}s)", flush=True)
    test_rows = {c: cands[c][idx[cands[c]] >= ws.TEST_START] for c in coins}
    feats = {c: pn[c].loc[idx[test_rows[c]]][wick.FEATS] for c in coins}
    qs = {c: pd.PeriodIndex(idx[test_rows[c]], freq="Q") for c in coins}
    preds = {}                                                   # seed -> coin -> (pred, thr) arrays
    for seed in SEEDS:
        ms = models_for(X, seed)
        preds[seed] = {}
        for c in coins:
            p, th = np.full(len(test_rows[c]), np.nan), np.full(len(test_rows[c]), np.nan)
            for q in np.unique(qs[c]):
                m, ptr = ms[q]
                j = qs[c] == q
                p[j] = m.predict(feats[c][j])
                th[j] = np.median(ptr)
            preds[seed][c] = (p, th)
        # keep the training predictions for the seed-average threshold
        preds[seed]["_train"] = {q: ptr for q, (m, ptr) in ms.items()}
        print(f"  seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    avg = {}
    for c in coins:
        p = np.mean([preds[s][c][0] for s in SEEDS], axis=0)
        th = np.full(len(p), np.nan)
        for q in np.unique(qs[c]):
            th[qs[c] == q] = np.median(np.mean([preds[s]["_train"][q] for s in SEEDS], axis=0))
        avg[c] = (p, th)

    def simulate(keep_fn, exit_ticks=1.0):
        trs = []
        i_test = idx.get_indexer([pd.Timestamp(ws.TEST_START)])[0]
        for c in coins:
            o, hh, lo, cfc = (D[c][k] for k in ("open", "high", "low", "cf"))
            lvl, sig = LV[c][0].copy(), LV[c][1]
            lvl[:i_test] = np.nan
            if keep_fn is not None:
                k = keep_fn(c)
                lvl[test_rows[c][~k]] = np.nan
            tick = np.nan_to_num(ws.PERP[c][2] / cfc, nan=1.0)
            ei, xi, ep, xp, ty = ws.run_book(o, hh, lo, cfc, lvl, wick.THETA * wick.K * sig, np.full(len(idx), np.nan), 1,
                                             tick, wick.H, 0)
            gross = np.log(xp / ep) * 1e4
            hs = exit_ticks * ws.PERP[c][2] / ep * 1e4
            net = gross - 2.0 - np.where(ty == 1, 2.0, 2.0 + hs)
            trs.append(pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "net_bp": net, "gross_bp": gross, "type": ty}))
        return pd.concat(trs, ignore_index=True)

    rows, keep_trades = [], []
    runs = [("rule only", None, 1.0)] + [(f"rule + AI, seed {s}", (lambda c, s=s: preds[s][c][0] > preds[s][c][1]), 1.0) for s in SEEDS]
    runs += [("rule + AI, 5-seed average", lambda c: avg[c][0] > avg[c][1], 1.0),
             ("rule + AI, 5-seed average, exits pay 3 ticks", lambda c: avg[c][0] > avg[c][1], 3.0)]
    for name, fn, xt in runs:
        tr = simulate(fn, xt)
        for cap in (None, 6):
            s, d = wf.portfolio(tr, pd.Timestamp(ws.TEST_START), cap)
            yrs = {f"sharpe_{y}": d[d.index.year == y].mean() / d[d.index.year == y].std() * np.sqrt(365) for y in (2025, 2026)}
            rows.append(dict(strategy=name, cap=cap or "none", **s, **yrs))
        if name in ("rule only", "rule + AI, 5-seed average"):
            keep_trades.append(tr.assign(strategy=name))
        print(f"  {name} ({time.time() - t0:.0f}s)", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(ROOT, "reports", "wick_final.csv"), index=False)
    pd.concat(keep_trades).to_parquet(os.path.join(ROOT, "reports", "wick_final_trades.parquet"), index=False)
    pd.set_option("display.width", 250)
    print(R.round(3).to_string(index=False))
    ai = R[R.strategy.str.contains("seed ") & ~R.strategy.str.contains("average")]
    for cap in ("none", 6):
        x = ai[ai.cap == cap].sharpe
        print(f"single-seed models, cap {cap}: Sharpe mean {x.mean():.2f}, range {x.min():.2f} - {x.max():.2f}")


if __name__ == "__main__":
    main()
