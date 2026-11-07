#!/usr/bin/env python3
"""H12 (LT): R2-08 "C29+A11" exactly as scripts/wick1m/trades_wide.py runs it, on a pool of the wide set's 31 coins
plus the long-tail universe (reports/hunt/h12lt/SPEC.md), then sim.py's precompute for the sleeve's trades.

Why a coin-by-coin driver: core.Data / LevelSet / wick.panel hold every coin's full minute arrays at once (~0.3 GB per
coin; the 31-coin run needed ~10 GB), so ~110 coins do not fit in a 16 GB runner. This driver calls the lab's own code
for one coin at a time (core.LevelSet for levels and candidates, wick.panel for the per-coin features, core.labels,
core.walk_forward's training rule, core.simulate, run.attach_thr) and fills in the only pool-wide pieces itself:
  - alts_mean_z60 / alts_below_2sd (wick.panel: mean and count of the OTHER pool coins' z_res60 at t-1), from each
    coin's stored z_res60 with wick.panel's own formula;
  - coin_id = position in the sorted pool (wick.panel's default codes);
  - row order = pool order, candidates ascending (as LevelSet.features concatenates), so LightGBM sees the same data.
Unused work is skipped: add_extra's columns (not in R2-08's feature set) and the basket factor (R2-08 uses BTC).
Mode `check` runs the wide 31 alone and compares with reports/wick1m/trades_wide.parquet (DEV trades only).

usage: python scripts/hunt/h12lt/pipeline.py check
       python scripts/hunt/h12lt/pipeline.py run
"""
import gc
import json
import os
import sys
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "lab"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
import core  # noqa: E402
import run as RUN  # noqa: E402
import variants as VV  # noqa: E402
import wick_sim as ws  # noqa: E402
import trades_wide as TW  # noqa: E402
from edge import wick  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h12lt")
DATA_DIRS = [os.path.join(ROOT, "data", "minute"), os.path.join(ROOT, "data", "hunt", "h12lt", "minute")]
HOLD0 = pd.Timestamp("2026-06-01")
WIDE_TICKS = os.path.join(ROOT, "reports", "wick1m", "spot_ticks_wide.csv")


def load_coin(c, idx):
    """ws.load_ohlc for one coin (same reads, same float64 arrays)."""
    for d in DATA_DIRS:
        p = os.path.join(d, f"{c}.parquet")
        if os.path.exists(p):
            break
    else:
        return None
    df = pd.read_parquet(p).drop_duplicates("ts").set_index("ts").sort_index()
    df = df[df.volume > 0].reindex(idx)
    out = {k: df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close")}
    out["cf"] = df["close"].ffill(limit=30).to_numpy(np.float64)
    out["vol"] = df["volume"].fillna(0.0).to_numpy(np.float64)
    return out


def setup(universe):
    """trades_wide.main's patches: spot ticks, PERP stubs for coins without a perp, spot_tick, the VIP1 cost label."""
    T = pd.read_csv(WIDE_TICKS)
    pool = [r.coin for r in T.itertuples() if bool(r.used)]
    rows = [(r.coin, r.tick) for r in T.itertuples()]
    if universe is not None:
        rows += [(r.coin, r.tick) for r in universe.itertuples()]
        pool += [c for c in universe.coin if c not in pool]
    for c, t in rows:
        if np.isfinite(t) and c not in ws.SPOT_TICK:
            ws.SPOT_TICK[c] = t
        if c not in ws.PERP:
            ws.PERP[c] = (None, 1.0, ws.SPOT_TICK.get(c, t))
    ws.spot_tick = lambda c: ws.SPOT_TICK.get(c, ws.PERP[c][2])
    TW.patch_costs()
    allv = {v["name"]: v for v in VV.VARIANTS + VV.ROUND1B + VV.make_round2()}
    v = allv["R2-08 C29+A11"]
    specs = RUN.expand(v)
    assert len(specs) == 1
    print("R2-08 spec:", json.dumps(specs[0], default=str), flush=True)
    return pool, specs[0]


def make_ls(data, c, ls_d):
    d = dict(ls_d)
    d["coins"] = [c]
    return core.LevelSet(data, **d)


def coin_features(ls, c, data, code):
    """LevelSet.features for one coin, without add_extra (its columns are not R2-08 features). wick.panel with this
    coin alone gives every per-coin feature; coin_id and the two cross-coin features are set by the caller."""
    cand = ls.cands[c]
    if len(cand) == 0:
        return None
    cf = {k: data.D[k]["cf"] for k in data.D}
    vol = {k: data.D[k]["vol"] for k in data.D}
    pn = wick.panel(cf, vol, [c], data.idx, k=ls.k, lookback=ls.L, keep_rows=ls.cands)
    f = pn[c].loc[data.idx[cand]][wick.FEATS].copy()
    f["bid_depth_bp"] = (ls.k * ls.sig[c][cand] * 1e4).astype(np.float32)
    f["beta"] = ls.beta[c][cand].astype(np.float32)
    f["coin"], f["pos"], f["ts"] = c, cand, data.idx[cand]
    f["episode"] = np.cumsum(np.r_[1, np.diff(cand) > 1])
    f["sig"] = ls.sig[c][cand]
    f["px"] = ls.lvl[c][cand]
    f["coin_id"] = np.float32(code)
    return f.reset_index(drop=True)


def zres60(cf_c, r1b, btc_r60):
    """wick.panel's zres[c, 60] (3-day beta, 3-day std), through minute t."""
    lp = np.log(cf_c)
    beta = wick._rbeta(np.diff(lp, prepend=np.nan), r1b)
    return wick._rz((lp - wick.shift(lp, 60)) - beta * btc_r60)


def walk_forward(X, y, feats, seeds=(7, 11, 23), thr_q=0.6, extra_q=(0.7,)):
    """core.walk_forward with R2-08's settings (Huber LightGBM, quarterly, episode weights, no window), unchanged, also
    recording other quantiles of each quarter's training predictions (for the stricter-filter trial)."""
    import lightgbm as lgb
    params = dict(wick.PARAMS)
    rounds = wick.ROUNDS
    periods = pd.period_range(*core.WF_Q, freq="Q")
    pred = pd.Series(np.nan, index=X.index)
    thr = pd.Series(np.nan, index=X.index)
    thx = {q: pd.Series(np.nan, index=X.index) for q in extra_q}
    cat = ["coin_id"] if "coin_id" in feats else []
    qrows = []
    for per in periods:
        tr_mask = X.ts < per.start_time - pd.Timedelta(days=1)
        te_mask = (X.ts >= per.start_time) & (X.ts <= per.end_time)
        if not te_mask.any() or tr_mask.sum() < 200:
            continue
        tr, te = X[tr_mask], X[te_mask]
        w = 1.0 / tr.groupby(["coin", "episode"]).ts.transform("size").to_numpy()
        ytr = y[tr_mask].to_numpy()
        pte, ptr = [], []
        for s in seeds:
            m = lgb.train(params | {"seed": s}, lgb.Dataset(tr[feats], ytr, weight=w, categorical_feature=cat),
                          num_boost_round=rounds)
            pte.append(m.predict(te[feats]))
            ptr.append(m.predict(tr[feats]))
        pte, ptr = np.mean(pte, axis=0), np.mean(ptr, axis=0)
        pred[te.index] = pte
        thr[te.index] = np.quantile(ptr, thr_q)
        rec = dict(quarter=str(per), n_train=int(tr_mask.sum()), thr=float(np.quantile(ptr, thr_q)))
        for q in extra_q:
            thx[q][te.index] = np.quantile(ptr, q)
            rec[f"thr_{int(q * 100)}"] = float(np.quantile(ptr, q))
        if per.start_time < HOLD0:                    # quarters trained on HOLD data are neither printed nor kept
            qrows.append(rec)
            print(f"  {per}: train {tr_mask.sum()}, thr {rec['thr']:.2f}", flush=True)
    return pred, thr, thx, pd.DataFrame(qrows)


def main(mode):
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    universe = None
    if mode == "run":
        universe = pd.read_csv(os.path.join(OUT, "universe.csv"))
    pool, (ls_d, ex_d, ai_d) = setup(universe)
    assert ai_d.get("label") == "net_real" and ai_d.get("thr_q") == 0.6 and ls_d["ref"] == "btc" and ls_d["wbeta"] == 10080
    idx = pd.date_range(core.START, core.END, freq="min", inclusive="left")
    i_test = int(idx.get_indexer([core.TEST0])[0])
    btc = load_coin("BTC", idx)
    lpb = np.log(btc["cf"])
    r1b = np.diff(lpb, prepend=np.nan)
    btc_r60 = lpb - wick.shift(lpb, 60)
    pool = [c for c in pool if any(os.path.exists(os.path.join(d, f"{c}.parquet")) for d in DATA_DIRS)]
    codes = {c: i for i, c in enumerate(sorted(pool))}
    trade_coins = pool if mode == "check" else [c for c in pool if c in set(universe.coin)]
    print(f"pool {len(pool)} coins; trading {len(trade_coins)}", flush=True)
    ex = core.Exit(**ex_d)
    Z, LV, feats_parts, labs = {}, {}, [], []
    for c in pool:
        D = load_coin(c, idx)
        data = SimpleNamespace(D={"BTC": btc, c: D}, lp={"BTC": lpb, c: np.log(D["cf"])}, idx=idx, T=len(idx),
                               i_test=i_test)
        ls = make_ls(data, c, ls_d)
        f = coin_features(ls, c, data, codes[c])
        Z[c] = zres60(D["cf"], r1b, btc_r60)
        if f is not None:
            ls._feat = f
            lab = core.labels(ls, ex)
            feats_parts.append(f)
            labs.append(lab.reset_index(drop=True))
        if c in trade_coins:
            LV[c] = (ls.lvl[c], ls.sig[c], ls.beta[c], ls.cands[c])
        del D, data, ls
        gc.collect()
        print(f"  {c}: {0 if f is None else len(f)} candidates ({time.time() - t0:.0f}s)", flush=True)
    X = pd.concat(feats_parts, ignore_index=True)
    lab = pd.concat(labs, ignore_index=True)
    lab.index = X.index
    # the two cross-coin features, wick.panel's formula over the OTHER pool coins, value at t-1
    for c in pool:
        rows = X.index[X.coin == c]
        if len(rows) == 0:
            continue
        pos = X.pos[rows].to_numpy() - 1
        others = [o for o in pool if o != c]
        oz = np.vstack([Z[o][pos] for o in others])
        with np.errstate(invalid="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                X.loc[rows, "alts_mean_z60"] = np.nanmean(oz, axis=0).astype(np.float32)
            X.loc[rows, "alts_below_2sd"] = np.nansum(oz < -2, axis=0).astype(float).astype(np.float32)
    for col in wick.FEATS:
        X[col] = X[col].astype(np.float32)
    del Z
    gc.collect()
    print(f"features: {len(X)} candidates ({time.time() - t0:.0f}s)", flush=True)
    y = RUN.make_label(lab, ai_d, SimpleNamespace(features=lambda: X))
    feats = list(ai_d.get("feats", tuple(wick.FEATS)))
    pred, thr, thx, qtab = walk_forward(X, y, feats, seeds=ai_d.get("seeds", (7, 11, 23)), thr_q=ai_d["thr_q"])
    qtab.to_csv(os.path.join(OUT, f"quarters_{mode}.csv"), index=False)
    print(f"walk-forward done ({time.time() - t0:.0f}s)", flush=True)
    keeps = {"base": (pred > thr) | (X.ts < core.TEST0), "ai70": (pred >= thx[0.7]) | (X.ts < core.TEST0)}
    out = {}
    for name, keep in keeps.items():
        parts = []
        for c in trade_coins:
            lvl, sig, beta, cands = LV[c]
            D = load_coin(c, idx)
            data = SimpleNamespace(D={c: D}, idx=idx, T=len(idx), i_test=i_test)
            ls = core.LevelSet.__new__(core.LevelSet)
            ls.data, ls.L, ls.k, ls.side, ls.ref = data, ls_d["L"], ls_d["k"], ls_d["side"], ls_d["ref"]
            ls.coins, ls.lvl, ls.sig, ls.beta, ls.cands = [c], {c: lvl}, {c: sig}, {c: beta}, {c: cands}
            Xc = X[X.coin == c]
            ls._feat = Xc
            tr = core.simulate(ls, ex, keep=keep, pred=pred)
            tr = RUN.attach_thr(tr, ls, Xc, thx[0.7])
            if len(tr):
                tr["thr70"] = tr.pop("thr")
            tr = RUN.attach_thr(tr, ls, Xc, thr)
            if len(tr):
                tr["k"] = ls.k
                tr["tp_log"] = ex.theta * ls.k * tr.sig
                tr["fair_log"] = np.log(tr.px) + ls.k * tr.sig
                parts.append(tr)
            del D, data, ls
        tr = pd.concat(parts, ignore_index=True).sort_values(["ts", "coin"]).reset_index(drop=True)
        tr["bot"] = False
        out[name] = tr
        dev = tr[tr.ts < HOLD0]
        print(f"{name}: {dev.coin.nunique()} coins traded on DEV, {len(dev)} DEV trades ({time.time() - t0:.0f}s)",
              flush=True)
    if mode == "check":
        compare(out["base"])
        return
    for name, tr in out.items():
        tr.to_parquet(os.path.join(OUT, f"trades_{name}.parquet"), index=False)
    precompute(out, universe)
    print(f"done ({time.time() - t0:.0f}s)")


def compare(tr):
    """DEV-only comparison with the original 31-coin run."""
    W = pd.read_parquet(os.path.join(ROOT, "reports", "wick1m", "trades_wide.parquet"))
    a = W[W.ts < HOLD0].set_index(["ts", "coin"]).sort_index()
    b = tr[tr.ts < HOLD0].set_index(["ts", "coin"]).sort_index()
    both = a.index.intersection(b.index)
    res = dict(orig=len(a), mine=len(b), common=len(both), only_orig=len(a.index.difference(b.index)),
               only_mine=len(b.index.difference(a.index)))
    if len(both):
        for col in ("px", "gross", "net_real", "pred", "thr", "sig", "beta"):
            res[f"maxdiff_{col}"] = float(np.nanmax(np.abs(a.loc[both, col].to_numpy() - b.loc[both, col].to_numpy())))
        res["exit_same"] = float((a.loc[both, "exit_ts"].to_numpy() == b.loc[both, "exit_ts"].to_numpy()).mean())
    print("CHECK vs trades_wide (DEV):", json.dumps(res, indent=1), flush=True)
    json.dump(res, open(os.path.join(OUT, "check_vs_wide.json"), "w"), indent=1)


def precompute(out, universe):
    """sim.precompute ('wide' tag: spot ticks from a ticks table, Coinbase spot + perp ADV, no Bitstamp) on the sleeve's
    trade lists. sim.py reads data/minute/<coin>.parquet: the universe files are linked there on the runner."""
    import sim
    mdir = os.path.join(ROOT, "data", "minute")
    for c in universe.coin:
        src = os.path.join(ROOT, "data", "hunt", "h12lt", "minute", f"{c}.parquet")
        dst = os.path.join(mdir, f"{c}.parquet")
        if os.path.exists(src) and not os.path.exists(dst):
            os.symlink(src, dst)
    tmp = os.path.join(ROOT, "reports", "hunt", "h12lt", "_sim")
    os.makedirs(tmp, exist_ok=True)
    universe[["coin", "tick"]].to_csv(os.path.join(tmp, "spot_ticks_wide.csv"), index=False)
    sim.OUT = tmp
    import contextlib
    for name, tr in out.items():
        tr.to_parquet(os.path.join(tmp, "trades_wide.parquet"), index=False)
        with open(os.devnull, "w") as dn, contextlib.redirect_stdout(dn):     # its log counts trades incl. HOLD
            P = sim.precompute("wide", bitstamp=False, out_tag=f"h12lt_{name}")
        P.to_pickle(os.path.join(OUT, f"pre_{name}.pkl"))
        print(f"precomputed {name}: {int((P.ts < HOLD0).sum())} DEV tranche rows", flush=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)


if __name__ == "__main__":
    main(sys.argv[1])
