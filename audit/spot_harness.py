#!/usr/bin/env python3
"""Audit harness for the spot-executed headline (scripts/wick_final.py: 17 coins, test 2025-01-01..2026-11-05,
5-seed average AI, $2,500 per trade on $10K, cap none / 6). Reproduces it, then varies one assumption at a time.
Writes only under audit/."""
import os
import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.argv = sys.argv[:1]
from edge import wick  # noqa: E402
import wick_breadth as wb  # noqa: E402
import wick_futures as wf  # noqa: E402
import wick_robust as wr  # noqa: E402
import wick_sim as ws  # noqa: E402

OUT = os.path.join(ROOT, "audit")
SEEDS = [7, 11, 23, 42, 101]
EXTRA = [c for c in os.environ.get("EXTRA", "").split(",") if c]
SPOT_TICK = {"PEPE": 1e-8}


def main():
    t0 = time.time()
    coins = [c for c in wb.WIDE + EXTRA if os.path.exists(os.path.join(ROOT, "data", "minute", f"{c}.parquet"))]
    idx, D = ws.load_ohlc(coins=["BTC"] + coins)
    cf = {c: D[c]["cf"] for c in D}
    LV = wick.levels(cf, coins)
    cands = wf.spot_candidates(D, LV, coins)
    # rows needed: candidates for lag 0 and lag 1, and the row before each (lagged decision)
    need = {}
    for c in coins:
        tick = np.nan_to_num(ws.PERP[c][2] / D[c]["cf"], nan=1.0)
        c1 = wf.candidates(D[c]["open"], D[c]["low"], wick.shift(LV[c][0], 1), tick)
        extra = [np.array([], dtype=np.int64)]
        if c in SPOT_TICK:
            extra.append(wf.candidates(D[c]["open"], D[c]["low"], wick.round_down(LV[c][0], SPOT_TICK[c]),
                                       np.nan_to_num(SPOT_TICK[c] / D[c]["cf"], nan=1.0)))
        r = np.unique(np.concatenate([cands[c], c1, cands[c] - 1, c1 - 1] + extra))
        need[c] = r[r > 0]
    pn = wick.panel(cf, {c: D[c]["vol"] for c in D}, coins, idx, keep_rows=need)
    X = wf.spot_training_set(D, pn, idx, coins, lv=LV, cands=cands)
    print(f"{len(coins)} coins, {len(X)} candidates ({time.time() - t0:.0f}s)", flush=True)
    # 5-seed average prediction for every panel row in the test period; threshold per quarter as in wick_final
    keep = {c: np.zeros(len(idx), dtype=bool) for c in coins}
    rows = {c: pn[c].pos.to_numpy() for c in coins}
    qs = {c: pd.PeriodIndex(pn[c].index, freq="Q") for c in coins}
    pred = {c: np.zeros(len(rows[c])) for c in coins}
    thr = {c: np.full(len(rows[c]), np.nan) for c in coins}
    train_preds = {}
    seeds = SEEDS if os.environ.get("ONE_SEED", "0") != "1" else [7]
    for seed in seeds:
        for q in pd.period_range("2025Q1", "2026Q4", freq="Q"):
            tr = X[X.ts < q.start_time - pd.Timedelta(days=1)]
            w = 1.0 / tr.groupby(["coin", "episode"]).ts.transform("size")
            m = lgb.train(wick.PARAMS | {"seed": seed}, lgb.Dataset(tr[wick.FEATS], tr.net_bp.clip(-400, 400), weight=w,
                                                                   categorical_feature=["coin_id"]), num_boost_round=wick.ROUNDS)
            train_preds.setdefault(q, []).append(m.predict(tr[wick.FEATS]))
            for c in coins:
                j = qs[c] == q
                if j.any():
                    pred[c][j] += m.predict(pn[c].loc[j, wick.FEATS]) / len(seeds)
        print(f"  seed {seed} ({time.time() - t0:.0f}s)", flush=True)
    for q, lst in train_preds.items():
        th = np.median(np.mean(lst, axis=0))
        for c in coins:
            thr[c][qs[c] == q] = th
    for c in coins:
        ok = np.isfinite(thr[c])
        keep[c][rows[c][ok]] = pred[c][ok] > thr[c][ok]

    hs_meas = wf.half_spread_bp()
    i_test = idx.get_indexer([pd.Timestamp(ws.TEST_START)])[0]

    def simulate(ai, lag=0, hs_mode="tick", fees="pct2", pepe_spot_tick=False, drop=(), ai_lag=0):
        trs = []
        for c in coins:
            if c in drop:
                continue
            o, hh, lo, cfc = (D[c][k] for k in ("open", "high", "low", "cf"))
            lvl, sig = LV[c][0].copy(), LV[c][1]
            if lag:
                lvl, sig = wick.shift(lvl, lag), wick.shift(sig, lag)
            tick = np.nan_to_num(ws.PERP[c][2] / cfc, nan=1.0)
            if pepe_spot_tick and c in SPOT_TICK:
                lvl = wick.round_down(lvl, SPOT_TICK[c])
                tick = np.nan_to_num(SPOT_TICK[c] / cfc, nan=1.0)
            lvl[:i_test] = np.nan
            if ai:
                cand = wf.candidates(o, lo, lvl, tick)
                k_ = keep[c] if not (lag or ai_lag) else np.r_[False, keep[c][:-1]]
                off = np.zeros(len(idx), dtype=bool)
                off[cand] = True
                lvl[off & ~k_] = np.nan
            ei, xi, ep, xp, ty = ws.run_book(o, hh, lo, cfc, lvl, wick.THETA * wick.K * sig, np.full(len(idx), np.nan), 1,
                                             tick, wick.H, 0)
            if pepe_spot_tick and c in SPOT_TICK:
                xp = np.where(ty == 1, wick.round_down(xp, SPOT_TICK[c]), xp)
            gross = np.log(xp / ep) * 1e4
            if hs_mode == "tick":
                hs = ws.PERP[c][2] / ep * 1e4
            elif hs_mode == "perp_measured":
                hs = np.full_like(ep, hs_meas.get(c, np.nan))
            elif hs_mode == "spot_measured":
                hs = np.full_like(ep, SPOT_HS.get(c, np.nan))
            if fees == "pct2":
                f_in, f_tp, f_tk = 2.0, 2.0, 2.0
            else:
                size = ws.PERP[c][1]
                f_in = wr.FEE_CONTRACT_USD / (size * ep) * 1e4
                f_tp = f_tk = wr.FEE_CONTRACT_USD / (size * xp) * 1e4
            net = gross - f_in - np.where(ty == 1, f_tp, f_tk + hs)
            trs.append(pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "net_bp": net, "gross_bp": gross,
                                     "type": ty, "ep": ep}))
        return pd.concat(trs, ignore_index=True)

    s = pd.read_csv(os.path.join(ROOT, "reports", "cfm_book_summary.csv"))
    SPOT_HS = {r.root: r.spread_bp_median / 2 for r in s[s.kind == "spot"].itertuples()}
    variants = [("base (reproduces wick_final 5-seed avg)", dict()),
                ("1-minute extra latency (level + AI 1 min older)", dict(lag=1)),
                ("AI features 1 min older only (level unchanged)", dict(ai_lag=1)),
                ("market exits pay measured PERP half-spread", dict(hs_mode="perp_measured")),
                ("market exits pay measured SPOT half-spread", dict(hs_mode="spot_measured")),
                ("fees $0.20/contract/side (perp sizes)", dict(fees="contract")),
                ("PEPE on its real spot tick (1e-8)", dict(pepe_spot_tick=True)),
                ("without PEPE", dict(drop=("PEPE",))),
                ("measured perp half-spread + $0.20/contract", dict(hs_mode="perp_measured", fees="contract")),
                ]
    res, keep_tr = [], {}
    for name, kw in variants:
        for ai in (False, True):
            tr = simulate(ai, **kw)
            keep_tr[name, ai] = tr
            for cap in (None, 6):
                st, d = wf.portfolio(tr, pd.Timestamp(ws.TEST_START), cap)
                yrs = {f"sharpe_{y}": d[d.index.year == y].mean() / d[d.index.year == y].std() * np.sqrt(365) for y in (2025, 2026)}
                res.append(dict(variant=name, strategy="rule + AI (5-seed avg)" if ai else "rule only", cap=cap or "none", **st, **yrs))
        print(f"  {name} ({time.time() - t0:.0f}s)", flush=True)
    R = pd.DataFrame(res)
    tag = os.environ.get("TAG", "")
    R.to_csv(os.path.join(OUT, f"spot_variants{tag}.csv"), index=False)
    pd.concat([v.assign(variant=k[0], ai=k[1]) for k, v in keep_tr.items()]).to_parquet(os.path.join(OUT, f"spot_trades{tag}.parquet"))
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    print(R[["variant", "strategy", "cap", "trades", "net_bp", "hit", "sharpe", "t", "ann_ret", "maxdd", "sharpe_2025", "sharpe_2026"]]
          .round(3).to_string(index=False))
    pc = keep_tr["base (reproduces wick_final 5-seed avg)", True].groupby("coin").agg(
        trades=("net_bp", "size"), net_bp=("net_bp", "mean"), pnl=("net_bp", lambda x: x.sum() / 1e4 * 0.25))
    print(pc.round(3).sort_values("pnl").to_string())
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
