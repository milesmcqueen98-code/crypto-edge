#!/usr/bin/env python3
"""Run wick v2 lab variants. Validation metrics -> reports/lab/results_val.csv (read during selection);
holdout metrics -> reports/lab/results_hold.csv (not read until the shortlist is fixed);
daily returns of every variant -> reports/lab/daily_real.parquet, daily_base.parquet.
Usage: python scripts/lab/run.py [round1|round2] [name-filter]"""
import gc
import json
import os
import sys
import time
from copy import deepcopy

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
from edge import wick  # noqa: E402

OUT = os.path.join(core.ROOT, "reports", "lab")
os.makedirs(OUT, exist_ok=True)


def key(d):
    return json.dumps(d, sort_keys=True, default=str)


def expand(var):
    """A variant -> list of (ls, exit, ai) book specs."""
    books = var.get("books") or [{}]
    out = []
    for b in books:
        ls = {**var["ls"], **b.get("ls", {})}
        ex = {**var["exit"], **b.get("exit", {})}
        ai = {**var["ai"], **b.get("ai", {})}
        out.append((ls, ex, ai))
    return out


def make_label(lab, ai, ls):
    kind = ai.get("label", "net_base")
    if kind == "tp_hit":
        return lab.tp_hit
    if kind == "net_per_sig":
        return (lab.net_base / (ls.features()["sig"] * 1e4)).clip(-8, 8)
    clip = ai.get("clip", 400)
    return lab[kind].clip(-clip, clip)


def top12(ls, lab):
    """Top-12 base features by gain in a model trained on 2024 candidates only (no test data)."""
    import lightgbm as lgb
    X = ls.features()
    tr = X.ts < core.TEST0 - pd.Timedelta(days=1)
    w = 1.0 / X[tr].groupby(["coin", "episode"]).ts.transform("size").to_numpy()
    m = lgb.train(wick.PARAMS, lgb.Dataset(X.loc[tr, list(wick.FEATS)], lab.net_base[tr].clip(-400, 400), weight=w,
                                           categorical_feature=["coin_id"]), num_boost_round=wick.ROUNDS)
    imp = pd.Series(m.feature_importance("gain"), index=list(wick.FEATS)).sort_values(ascending=False)
    feats = list(imp.index[:12])
    if "coin_id" not in feats:
        feats.append("coin_id")
    return tuple(feats)


def build_spec(ls, X, ex_d, ai_d, lab_cache, state):
    """Labels, walk-forward AI and bid mask for one (exit, AI) spec on a level set."""
    ex = core.Exit(**ex_d)
    ek = key(ex_d)
    if ek not in lab_cache:
        lab_cache[ek] = core.labels(ls, ex)
    lab = lab_cache[ek]
    if ai_d.get("off"):
        return ex, None, None, None
    feats = ai_d.get("feats", tuple(wick.FEATS))
    if feats == "TOP12":
        if state.get("top") is None:
            state["top"] = top12(ls, lab)
            print("  TOP12:", state["top"], flush=True)
        feats = state["top"]
    y = make_label(lab, ai_d, ls)
    pred, thr = core.walk_forward(
        X, y, list(feats), params=ai_d.get("params"), seeds=ai_d.get("seeds", (7, 11, 23)),
        freq=ai_d.get("freq", "Q"), window_days=ai_d.get("window_days"), weight=ai_d.get("weight", "episode"),
        halflife=ai_d.get("halflife"), thr_q=ai_d.get("thr_q", 0.5), thr_abs=ai_d.get("thr_abs"),
        objective=ai_d.get("objective"), monotone=ai_d.get("monotone"), rounds=ai_d.get("rounds"),
        logit_ens=ai_d.get("logit_ens", False))
    keep = (pred > thr) | (X.ts < core.TEST0)
    return ex, keep, pred, thr


def attach_thr(tr, ls, X, thr):
    """Each trade's AI threshold (for prediction-scaled sizing)."""
    if thr is not None and len(tr):
        tmap = {}
        for c in ls.coins:
            rows = X.index[X.coin == c]
            tmap[c] = pd.Series(thr[rows].to_numpy(), index=X.pos[rows].to_numpy())
        tr["thr"] = [tmap[c].get(e, np.nan) for c, e in zip(tr.coin, tr.ei)]
    elif len(tr):
        tr["thr"] = np.nan
    return tr


def liquidity_scale():
    pr = pd.read_csv(os.path.join(core.ROOT, "reports", "cfm_products.csv"))
    pr = pr[pr.expiry_type == "PERPETUAL"]
    usd = (pr.volume_24h.astype(float) * pr.contract_size.astype(float) * pr.price.astype(float))
    liq = pd.Series(usd.to_numpy(), index=pr.root)
    med = liq.reindex(list(core.COINS17)).median()
    return lambda t: np.clip(np.sqrt(liq.reindex(t.coin).to_numpy() / med), 0.5, 1.5)  # noqa: E731


def run_portfolio(v, tr, data):
    if v.get("filt") == "weekend":
        tr = tr[tr.ts.dt.dayofweek >= 5]
    elif v.get("filt") == "weekday":
        tr = tr[tr.ts.dt.dayofweek < 5]
    port = dict(v["port"])
    size_scale = liquidity_scale() if port.pop("size_liq", False) else None
    return core.portfolio(tr, data=data, size_scale=size_scale, **port)


def run(variants, tag):
    t0 = time.time()
    coins_all = sorted({c for v in variants for b in expand(v) for c in b[0]["coins"]})
    data = core.Data(coins_all)
    print(f"data for {len(coins_all)} coins loaded ({time.time() - t0:.0f}s)", flush=True)
    # group book specs by level-set key
    specs = {}
    for v in variants:
        for ls, ex, ai in expand(v):
            specs.setdefault(key(ls), (ls, {}))[1][key((ex, ai))] = (ex, ai)
    trade_cache = {}
    state = {}
    for n_ls, (lsk, (ls_d, items)) in enumerate(specs.items()):
        t1 = time.time()
        ls = core.LevelSet(data, **ls_d)
        X = ls.features()
        lab_cache = {}
        for ik, (ex_d, ai_d) in items.items():
            ex, keep, pred, thr = build_spec(ls, X, ex_d, ai_d, lab_cache, state)
            trade_cache[(lsk, ik)] = attach_thr(core.simulate(ls, ex, keep=keep, pred=pred), ls, X, thr)
        print(f"[{n_ls + 1}/{len(specs)}] level set {ls_d['L']}m k={ls_d['k']} ref={ls_d['ref']} side={ls_d['side']} "
              f"coins={len(ls_d['coins'])}: {len(X)} candidates, {len(items)} specs ({time.time() - t1:.0f}s)", flush=True)
        del ls, X, lab_cache
        gc.collect()
    # ---- portfolios
    rows_v, rows_h, dr, db, da = [], [], {}, {}, {}
    for v in variants:
        parts = [trade_cache[(key(ls), key((ex, ai)))] for ls, ex, ai in expand(v)]
        tr = pd.concat([p for p in parts if len(p)], ignore_index=True) if any(len(p) for p in parts) else parts[0]
        daily, k = run_portfolio(v, tr, data)
        val, hold = core.summarize(v["name"], v["family"], daily, k)
        rows_v.append(val)
        rows_h.append(hold)
        dr[v["name"]], db[v["name"]] = daily["real"], daily["base"]
        if "adv" in daily:
            da[v["name"]] = daily["adv"]
        print(f"  {v['name']:<44s} val real Sharpe {val['val_real_sharpe']:5.2f}  base {val['val_base_sharpe']:5.2f}  "
              f"trades {val['val_trades']:4d}  net {val['val_net_real_bp']:6.1f} bp", flush=True)
    V = pd.DataFrame(rows_v)
    Hh = pd.DataFrame(rows_h)
    V.to_csv(os.path.join(OUT, f"results_val_{tag}.csv"), index=False)
    Hh.to_csv(os.path.join(OUT, f"results_hold_{tag}.csv"), index=False)
    pd.DataFrame(dr).to_parquet(os.path.join(OUT, f"daily_real_{tag}.parquet"))
    pd.DataFrame(db).to_parquet(os.path.join(OUT, f"daily_base_{tag}.parquet"))
    if da:
        pd.DataFrame(da).to_parquet(os.path.join(OUT, f"daily_adv_{tag}.parquet"))
    print(f"done: {len(variants)} variants in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    import variants as VV
    which = sys.argv[1] if len(sys.argv) > 1 else "round1"
    flt = sys.argv[2] if len(sys.argv) > 2 else None
    vs = {"round1": VV.VARIANTS, "round1b": VV.ROUND1B}.get(which) or VV.make_round2()
    if flt:
        vs = [v for v in vs if flt in v["name"]]
    run(vs, which if not flt else f"{which}_{flt.replace(' ', '_')}")
