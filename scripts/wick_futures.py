#!/usr/bin/env python3
"""Validate the AI-filtered resting-bid dip buyer on the instrument actually traded: Coinbase US perps.

Signal side exactly as live: spot 1-minute data -> edge.wick.panel -> level and features for minute t.
Execution side on futures 1-minute candles (public Advanced Trade API, data/cfm/<COIN>.parquet):
  futures bid = level_spot * basis, rounded down to the futures tick, where basis = last futures trade
  price / spot close at t-1. Fill if the futures minute opened above the bid and traded through it by one
  tick. Take-profit on futures highs; time exit at the futures close (last trade) + half the spread.
AI filter: the walk-forward quarterly models trained on spot candidates (as in wick_ai); bid switched off
where the prediction is at or below the training median.
Periods: each perp from its first full day of futures data to 2026-11-05.
Writes reports/wick_futures.csv, reports/wick_futures_trades.parquet
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
import wick_ai as wa  # noqa: E402
import wick_robust as wr  # noqa: E402
import wick_sim as ws  # noqa: E402

COINS = [c for c in sys.argv[1].split(",")] if len(sys.argv) > 1 else ["ETH", "SOL", "XRP", "DOGE", "LTC", "LINK"]
FEES = os.environ.get("FEES", "pct2")


def half_spread_bp():
    p = os.path.join(ROOT, "reports", "cfm_book_summary.csv")
    if not os.path.exists(p):
        return {}
    s = pd.read_csv(p)
    s = s[s.kind == "perp"]
    return {r.root: r.spread_bp_median / 2 for r in s.itertuples()}


def candidates(o, lo, lvl, tick_frac):
    with np.errstate(invalid="ignore"):
        fill = (o > lvl) & (lo <= lvl * (1 - tick_frac))
    return np.where(fill)[0]


def spot_candidates(D, lv, coins):
    out = {}
    for c in coins:
        tick = np.nan_to_num(ws.PERP[c][2] / D[c]["cf"], nan=1.0)
        cand = candidates(D[c]["open"], D[c]["low"], lv[c][0], tick)
        out[c] = cand[cand > 1500]
    return out


def spot_training_set(D, pn, idx, coins, lv=None, cands=None):
    """pn: full panel, or a keep_rows panel that contains at least the spot candidate rows."""
    if lv is None:
        lv = {c: (pn[c].level.to_numpy(), pn[c].sig.to_numpy()) for c in coins}
    cands = cands or spot_candidates(D, lv, coins)
    rows = []
    for c in coins:
        o, hh, lo, cf = (D[c][k] for k in ("open", "high", "low", "cf"))
        lvl, sig = lv[c]
        tick = np.nan_to_num(ws.PERP[c][2] / cf, nan=1.0)
        cand = cands[c]
        xp, ty = wa.single_trades(cand, o, hh, lo, cf, lvl, wick.THETA * wick.K * sig, tick, wick.H)
        wa.FEES, wa.TT = FEES, 1
        gross, net = wa.net_of_costs(c, lvl[cand], xp, ty)
        f = (pn[c].loc[idx[cand]] if "pos" in pn[c] else pn[c].iloc[cand])[wick.FEATS].copy()
        f["ts"], f["coin"], f["net_bp"] = idx[cand], c, net
        f["episode"] = np.cumsum(np.r_[1, np.diff(cand) > 1])
        rows.append(f)
    return pd.concat(rows, ignore_index=True).dropna(subset=["net_bp"])


def quarterly_models(X, first_q="2025Q1", last_q="2026Q4"):
    models = {}
    for q in pd.period_range(first_q, last_q, freq="Q"):
        tr = X[X.ts < q.start_time - pd.Timedelta(days=1)]
        w = 1.0 / tr.groupby(["coin", "episode"]).ts.transform("size")
        m = lgb.train(wick.PARAMS, lgb.Dataset(tr[wick.FEATS], tr.net_bp.clip(-400, 400), weight=w,
                                               categorical_feature=["coin_id"]), num_boost_round=wick.ROUNDS)
        models[q] = (m, float(np.median(m.predict(tr[wick.FEATS]))))
    return models


def load_futures(c, idx):
    p = os.path.join(ROOT, "data", "cfm", f"{c}.parquet")
    if not os.path.exists(p):
        return None
    df = pd.read_parquet(p).drop_duplicates("ts").set_index("ts").sort_index()
    df = df[df.volume > 0].reindex(idx)
    return {k: df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close")} | {
        "cf": df["close"].ffill(limit=30).to_numpy(np.float64), "first": df["close"].first_valid_index()}


def main():
    t0 = time.time()
    idx, D = ws.load_ohlc(coins=["BTC"] + COINS)
    cf = {c: D[c]["cf"] for c in D}
    vol = {c: D[c]["vol"] for c in D}
    pn = wick.panel(cf, vol, COINS, idx)
    X = spot_training_set(D, pn, idx, COINS)
    models = quarterly_models(X)
    print(f"spot candidates {len(X)}; models for {len(models)} quarters ({time.time() - t0:.0f}s)", flush=True)
    hs_meas = half_spread_bp()
    print("measured futures half-spreads (bp):", {k: round(v, 2) for k, v in hs_meas.items()})
    rows, all_tr = [], []
    for c in COINS:
        F = load_futures(c, idx)
        if F is None:
            print(f"{c}: no futures data")
            continue
        start = (F["first"] + pd.Timedelta(days=1)).normalize()
        i0 = idx.get_indexer([start])[0]
        sl = slice(i0, len(idx))
        size, tick_usd = ws.PERP[c][1], ws.PERP[c][2]
        basis = wick.shift(F["cf"] / D[c]["cf"], 1)
        lvl_spot, sig = pn[c].level.to_numpy(), pn[c].sig.to_numpy()
        lvl_f = wick.round_down(lvl_spot * basis, tick_usd)
        tick_f = np.nan_to_num(tick_usd / F["cf"], nan=1.0)
        # AI decision at every futures-candidate minute (features are the spot features at t-1)
        cand = candidates(F["open"], F["low"], lvl_f, tick_f)
        cand = cand[cand >= i0]
        keep = np.zeros(len(idx), dtype=bool)
        if len(cand):
            feats = pn[c].iloc[cand][wick.FEATS]
            qs = pd.PeriodIndex(idx[cand], freq="Q")
            for q in np.unique(qs):
                m, thr = models[q]
                j = cand[qs == q]
                keep[j] = m.predict(feats[qs == q]) > thr
        hs = hs_meas.get(c, np.nan)
        for name, mask in [("rule only", None), ("rule + AI", keep)]:
            lv = lvl_f.copy()
            lv[:i0] = np.nan
            if mask is not None:
                lv[np.isin(np.arange(len(idx)), cand) & ~mask] = np.nan
            tpd = wick.THETA * wick.K * sig
            ei, xi, ep, xp, ty = ws.run_book(F["open"], F["high"], F["low"], F["cf"], lv, tpd,
                                             np.full(len(idx), np.nan), 1, tick_f, wick.H, 0)
            xp = np.where(ty == 1, wick.round_down(xp, tick_usd), xp)            # TP limit sits on the tick grid (conservative)
            gross = np.log(xp / ep) * 1e4
            hs_bp = np.where(np.isfinite(hs), hs, tick_usd / ep * 1e4)
            f_in = wr.fee_bp(FEES, c, ep, True)
            f_out = np.where(ty == 1, wr.fee_bp(FEES, c, xp, True), wr.fee_bp(FEES, c, xp, False) + hs_bp)
            tr = pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "strategy": name, "type": ty,
                               "gross_bp": gross, "net_bp": gross - f_in - f_out, "entry_px": ep,
                               "contracts_per_10k": 1e4 / (size * ep)})
            all_tr.append(tr)
            # the same strategy simulated on spot over the same window, for comparison
            lv_s = lvl_spot.copy()
            lv_s[:i0] = np.nan
            if mask is not None:
                sc = candidates(D[c]["open"], D[c]["low"], lvl_spot, np.nan_to_num(tick_usd / D[c]["cf"], nan=1.0))
                sc = sc[sc >= i0]
                ks = np.zeros(len(idx), dtype=bool)
                if len(sc):
                    fs = pn[c].iloc[sc][wick.FEATS]
                    qs = pd.PeriodIndex(idx[sc], freq="Q")
                    for q in np.unique(qs):
                        m, thr = models[q]
                        ks[sc[qs == q]] = m.predict(fs[qs == q]) > thr
                lv_s[np.isin(np.arange(len(idx)), sc) & ~ks] = np.nan
            ei2, xi2, ep2, xp2, ty2 = ws.run_book(D[c]["open"], D[c]["high"], D[c]["low"], D[c]["cf"], lv_s, tpd,
                                                  np.full(len(idx), np.nan), 1,
                                                  np.nan_to_num(tick_usd / D[c]["cf"], nan=1.0), wick.H, 0)
            g2 = np.log(xp2 / ep2) * 1e4
            n2 = g2 - wr.fee_bp(FEES, c, ep2, True) - np.where(ty2 == 1, wr.fee_bp(FEES, c, xp2, True),
                                                               wr.fee_bp(FEES, c, xp2, False) + tick_usd / ep2 * 1e4)
            days = (idx[-1] - idx[i0]).days
            rows.append(dict(coin=c, strategy=name, start=str(idx[i0].date()), futures_minutes_traded=
                             float(np.isfinite(F["close"][i0:]).mean()),
                             fut_trades=len(tr), fut_per_day=len(tr) / days, fut_net_bp=tr.net_bp.mean(),
                             fut_hit=(tr.net_bp > 0).mean(), spot_trades=len(ep2), spot_net_bp=np.nanmean(n2),
                             half_spread_bp=float(np.nanmean(hs_bp)) if len(hs_bp) else np.nan))
        print(f"  {c} done ({time.time() - t0:.0f}s)", flush=True)
    R = pd.DataFrame(rows)
    T = pd.concat(all_tr, ignore_index=True)
    T.to_parquet(os.path.join(ROOT, "reports", "wick_futures_trades.parquet"), index=False)
    pd.set_option("display.width", 250)
    print(R.round(2).to_string(index=False))
    for name in ("rule only", "rule + AI"):
        tr = T[T.strategy == name]
        start = tr.ts.min().normalize() if len(tr) else pd.Timestamp("2025-08-01")
        d = wr.daily(tr).loc[start:]
        s = wr.sstats(d, (start, ws.END))
        print(f"{name}: futures-executed portfolio from {start.date()}: Sharpe {s['sharpe']:.2f}, t {s['t']:.2f}, "
              f"ann return {s['ann_ret']:.1%} at 0.25x notional per trade, max DD {s['maxdd']:.1%}, "
              f"{len(tr)} trades, net {tr.net_bp.mean():.1f} bp/trade")
        R.loc[len(R)] = dict(coin="PORTFOLIO", strategy=name, start=str(start.date()), fut_trades=len(tr),
                             fut_net_bp=tr.net_bp.mean(), fut_hit=(tr.net_bp > 0).mean(), sharpe=s["sharpe"], t=s["t"],
                             ann_ret=s["ann_ret"], maxdd=s["maxdd"])
    R.to_csv(os.path.join(ROOT, "reports", "wick_futures.csv"), index=False)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
