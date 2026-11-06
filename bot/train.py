#!/usr/bin/env python3
"""Train the live model on every spot candidate fill from 2024-01-01 to the latest data for the chosen
universe. Writes bot/model.txt and bot/model_meta.json (coins, threshold = median in-sample prediction).
Usage: python bot/train.py ETH,SOL,XRP,..."""
import json
import os
import sys

import lightgbm as lgb
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge import wick  # noqa: E402
import wick_futures as wf  # noqa: E402
import wick_sim as ws  # noqa: E402

SEEDS = [7, 11, 23, 42, 101]


def main(coins):
    idx, D = ws.load_ohlc(coins=["BTC"] + coins)
    cf = {c: D[c]["cf"] for c in D}
    vol = {c: D[c]["vol"] for c in D}
    LV = wick.levels(cf, coins)
    cands = wf.spot_candidates(D, LV, coins)
    pn = wick.panel(cf, vol, coins, idx, keep_rows=cands)
    X = wf.spot_training_set(D, pn, idx, coins, lv=LV, cands=cands)
    w = 1.0 / X.groupby(["coin", "episode"]).ts.transform("size")
    preds, files = [], []
    for seed in SEEDS:                                  # 5-seed average: same design, less model noise
        m = lgb.train(wick.PARAMS | {"seed": seed}, lgb.Dataset(X[wick.FEATS], X.net_bp.clip(-400, 400), weight=w,
                                                               categorical_feature=["coin_id"]), num_boost_round=wick.ROUNDS)
        f = f"model_s{seed}.txt"
        m.save_model(os.path.join(ROOT, "bot", f))
        files.append(f)
        preds.append(m.predict(X[wick.FEATS]))
    thr = float(np.median(np.mean(preds, axis=0)))
    meta = dict(coins=coins, threshold=thr, models=files, trained_from=str(X.ts.min()), trained_through=str(X.ts.max()),
                n_candidates=int(len(X)), L=wick.L, K=wick.K, THETA=wick.THETA, H=wick.H, feats=wick.FEATS,
                coin_codes={c: i for i, c in enumerate(sorted(coins))})
    json.dump(meta, open(os.path.join(ROOT, "bot", "model_meta.json"), "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main(sys.argv[1].split(","))
