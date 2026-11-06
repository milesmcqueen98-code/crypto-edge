#!/usr/bin/env python3
"""Train the live models for a wick v2 lab variant with the lab's own code (research == live).

Uses scripts/lab: the variant's level set (incl. the minimum contract value), its exit rule for the labels,
its AI settings (label, threshold quantile, parameters); 5 LightGBM seeds on every spot candidate from
2024-01-01 to the latest data. Writes model_s*.txt and model_meta.json to the output folder (default bot/v2); the engine reads the
threshold, hold limit, take-profit fraction, beta window and minimum contract value from the meta file.
Supported variants: those that change only minc / label / threshold / H / theta / coins (others raise).
Usage: python bot/train_v2.py "R2-08 C29+A11" bot/v2
"""
import json
import os
import sys

import lightgbm as lgb
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "lab"))
import core  # noqa: E402
import run as RUN  # noqa: E402
import variants as VV  # noqa: E402
from edge import wick  # noqa: E402

SEEDS = [7, 11, 23, 42, 101]
SUPPORTED = {("ls", "minc"), ("ls", "coins"), ("ls", "wbeta"), ("ai", "label"), ("ai", "thr_q"), ("exit", "H"),
             ("exit", "theta")}


def main(name, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    allv = {v["name"]: v for v in VV.VARIANTS + VV.ROUND1B + VV.make_round2()}
    v = allv[name]
    ch = VV.changes(v)
    bad = [k for k in ch if k not in SUPPORTED]
    if bad:
        raise SystemExit(f"{name}: the bot does not implement {bad} yet")
    ls_d, ex_d, ai_d = RUN.expand(v)[0]
    coins = list(ls_d["coins"])
    data = core.Data(coins)
    ls = core.LevelSet(data, **ls_d)
    X = ls.features()
    lab = core.labels(ls, core.Exit(**ex_d))
    y = RUN.make_label(lab, ai_d, ls).to_numpy()
    ok = np.isfinite(y)                                    # the newest candidates have no exit yet
    X, y = X[ok], y[ok]
    feats = list(ai_d.get("feats", tuple(wick.FEATS)))
    w = 1.0 / X.groupby(["coin", "episode"]).ts.transform("size").to_numpy()
    params = dict(wick.PARAMS) | (ai_d.get("params") or {})
    preds, files = [], []
    for seed in SEEDS:
        m = lgb.train(params | {"seed": seed}, lgb.Dataset(X[feats], y, weight=w, categorical_feature=["coin_id"]),
                      num_boost_round=ai_d.get("rounds") or wick.ROUNDS)
        f = f"model_s{seed}.txt"
        m.save_model(os.path.join(out_dir, f))
        files.append(f)
        preds.append(m.predict(X[feats]))
    q = ai_d.get("thr_q", 0.5)
    thr = float(np.quantile(np.mean(preds, axis=0), q))
    meta = dict(variant=name, coins=coins, threshold=thr, threshold_quantile=q, label=ai_d.get("label", "net_base"),
                models=files, trained_from=str(X.ts.min()), trained_through=str(X.ts.max()), n_candidates=int(len(X)),
                L=ls_d["L"], K=ls_d["k"], THETA=ex_d.get("theta", wick.THETA), H=ex_d.get("H", wick.H),
                min_contract_usd=ls_d.get("minc") or 0.0, wbeta=int(ls_d.get("wbeta", wick.W)), feats=feats,
                coin_codes={c: i for i, c in enumerate(sorted(coins))})
    json.dump(meta, open(os.path.join(out_dir, "model_meta.json"), "w"), indent=1)
    print(json.dumps({k: meta[k] for k in meta if k not in ("feats", "coin_codes")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "bot", "v2"))
