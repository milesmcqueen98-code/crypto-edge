#!/usr/bin/env python3
"""Sensitivity of the AI-filtered resting-bid dip buyer (walk-forward, test 2025-01-01 .. 2026-11-05).
The pre-registered setup is L=60, k=4, theta=0.6, H=60, fills need 1 tick, 2 bp fees, filter = prediction
above the training median. Every row below changes one thing; all rows are reported.
Writes reports/wick_ai_robust.csv and reports/wick_ai_trades_base.parquet"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wick_ai as wa  # noqa: E402
import wick_robust as wr  # noqa: E402
import wick_sim as ws  # noqa: E402

VARIANTS = [
    ("pre-registered", {}),
    ("fill needs 3 ticks", dict(TT=3)),
    ("fees $0.20/contract", dict(FEES="contract")),
    ("3 ticks + $0.20/contract", dict(TT=3, FEES="contract")),
    ("fees 0 maker / 2 taker", dict(FEES="maker0")),
    ("primary k=3", dict(K=3.0)),
    ("primary k=5", dict(K=5.0)),
    ("take-profit 0.3", dict(THETA=0.3)),
    ("take-profit 1.0", dict(THETA=1.0)),
    ("no take-profit", dict(THETA=np.inf)),
    ("hold 30 min", dict(H=30)),
    ("hold 120 min", dict(H=120)),
    ("lookback 30 min", dict(L=30)),
    ("lookback 120 min", dict(L=120)),
]
DEFAULT = dict(L=60, K=4.0, THETA=0.6, H=60, TT=1, FEES="pct2")


def one(D, idx, name, kw):
    for k, v in (DEFAULT | kw).items():
        setattr(wa, k, v)
    P = ws.Prep(D, tuple(sorted({wa.L, 15, 60})))
    X = wa.build(D, P, idx)
    X, imp, shap = wa.walk_forward(X)
    out = []
    for fname, rule in [("rule only", None), ("rule + AI", lambda xc: (xc.ts < ws.TEST_START) | (xc.pred > xc.thr))]:
        tr = wa.simulate_masked(D, P, idx, X, rule)
        tt = tr[tr.ts >= ws.TEST_START]
        d = wr.daily(tr)
        s = wr.sstats(d, wr.TST)
        yrs = {f"sharpe_{y}": (lambda x: x.mean() / x.std() * np.sqrt(365))(d[d.index.year == y]) for y in (2025, 2026)}
        out.append(dict(variant=name, strategy=fname, test_trades=len(tt), test_net_bp=tt.net_bp.mean(),
                        test_hit=(tt.net_bp > 0).mean(), **{f"test_{k}": v for k, v in s.items()}, **yrs))
        if name == "pre-registered" and fname == "rule + AI":
            tr.to_parquet(os.path.join(ws.ROOT, "reports", "wick_ai_trades_base.parquet"), index=False)
    return out


def main():
    t0 = time.time()
    idx, D = ws.load_ohlc(coins=["BTC"] + wa.COINS)
    rows = []
    for name, kw in VARIANTS:
        rows += one(D, idx, name, kw)
        print(f"{name} done ({time.time() - t0:.0f}s)", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(ws.ROOT, "reports", "wick_ai_robust.csv"), index=False)
    pd.set_option("display.width", 250)
    print(R.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
