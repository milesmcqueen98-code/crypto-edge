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


def fut_specs():
    df = pd.read_csv(os.path.join(ROOT, "reports", "cfm_products.csv"))
    df = df[df.expiry_type == "PERPETUAL"]
    return {r.root: (r.product_id, float(r.contract_size), float(r.price_increment)) for r in df.itertuples()}


def fee_fut(c, px_fut, size_fut, maker):
    """Fee in bp for a futures fill (prices in futures units)."""
    if FEES == "contract":
        return wr.FEE_CONTRACT_USD / (size_fut * px_fut) * 1e4
    return wr.fee_bp(FEES, c, px_fut, maker)


def portfolio(tr, start, cap=None, notional=0.25):
    if cap:
        tr = tr.sort_values("ts").reset_index(drop=True)
        keep, open_ = [], []
        for r in tr.itertuples():
            open_ = [e for e in open_ if e > r.ts]
            if len(open_) < cap:
                keep.append(r.Index)
                open_.append(r.exit_ts)
        tr = tr.loc[keep]
    days = pd.date_range(start, pd.Timestamp(ws.END) - pd.Timedelta(days=1), freq="D")
    d = (tr.set_index("exit_ts").net_bp * notional / 1e4).resample("D").sum().reindex(days, fill_value=0.0)
    eq = d.cumsum()
    sd = d.std()
    return dict(trades=len(tr), per_day=len(tr) / len(days), net_bp=tr.net_bp.mean(), hit=(tr.net_bp > 0).mean(),
                sharpe=d.mean() / sd * np.sqrt(365) if sd > 0 else np.nan, t=d.mean() / sd * np.sqrt(len(d)) if sd > 0 else np.nan,
                ann_ret=d.mean() * 365, maxdd=(eq - eq.cummax()).min(), worst_day=d.min()), d


def main():
    t0 = time.time()
    idx, D = ws.load_ohlc(coins=["BTC"] + COINS)
    cf = {c: D[c]["cf"] for c in D}
    vol = {c: D[c]["vol"] for c in D}
    LV = wick.levels(cf, COINS)
    spot_c = spot_candidates(D, LV, COINS)
    FS = fut_specs()
    fut, fut_c, lvl_fut = {}, {}, {}
    for c in COINS:
        F = load_futures(c, idx)
        if F is None or c not in FS:
            continue
        fut[c] = F
        basis = wick.shift(F["cf"] / D[c]["cf"], 1)
        lvl_fut[c] = wick.round_down(LV[c][0] * basis, FS[c][2])
        tick_f = np.nan_to_num(FS[c][2] / F["cf"], nan=1.0)
        fut_c[c] = candidates(F["open"], F["low"], lvl_fut[c], tick_f)
    keep_rows = {c: np.union1d(spot_c[c], fut_c.get(c, np.array([], dtype=np.int64))) for c in COINS}
    pn = wick.panel(cf, vol, COINS, idx, keep_rows=keep_rows)
    X = spot_training_set(D, pn, idx, COINS, lv=LV, cands=spot_c)
    models = quarterly_models(X)
    print(f"spot candidates {len(X)}; models for {len(models)} quarters ({time.time() - t0:.0f}s)", flush=True)
    hs_meas = half_spread_bp()
    print("measured futures half-spreads (bp):", {k: round(v, 2) for k, v in hs_meas.items()})

    def ai_keep(c, cand):
        keep = np.zeros(len(idx), dtype=bool)
        cand = cand[idx[cand] >= pd.Timestamp("2025-01-01")]
        if len(cand):
            feats = pn[c].loc[idx[cand]][wick.FEATS]
            qs = pd.PeriodIndex(idx[cand], freq="Q")
            for q in np.unique(qs):
                m, thr = models[q]
                keep[cand[qs == q]] = m.predict(feats[qs == q]) > thr
        return keep

    rows, all_tr = [], []
    for c, F in fut.items():
        start = (F["first"] + pd.Timedelta(days=1)).normalize()
        i0 = idx.get_indexer([start])[0]
        pid, size_f, tick_f_usd = FS[c]
        sig = LV[c][1]
        tpd = wick.THETA * wick.K * sig
        hs = hs_meas.get(c, np.nan)
        tick_f = np.nan_to_num(tick_f_usd / F["cf"], nan=1.0)
        tick_s = np.nan_to_num(ws.PERP[c][2] / D[c]["cf"], nan=1.0)
        keep_f, keep_s = ai_keep(c, fut_c[c]), ai_keep(c, spot_c[c])
        for name in ("rule only", "rule + AI"):
            # futures execution
            lv = lvl_fut[c].copy()
            lv[:i0] = np.nan
            if name == "rule + AI":
                off = np.zeros(len(idx), dtype=bool)
                off[fut_c[c]] = True
                lv[off & ~keep_f] = np.nan
            ei, xi, ep, xp, ty = ws.run_book(F["open"], F["high"], F["low"], F["cf"], lv, tpd, np.full(len(idx), np.nan),
                                             1, tick_f, wick.H, 0)
            xp = np.where(ty == 1, wick.round_down(xp, tick_f_usd), xp)
            gross = np.log(xp / ep) * 1e4
            hs_bp = np.where(np.isfinite(hs), hs, tick_f_usd / ep * 1e4)
            net = gross - fee_fut(c, ep, size_f, True) - np.where(ty == 1, fee_fut(c, xp, size_f, True),
                                                                   fee_fut(c, xp, size_f, False) + hs_bp)
            trf = pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "strategy": name, "venue": "futures",
                                "type": ty, "gross_bp": gross, "net_bp": net})
            # spot execution of the same rule over the same window
            lv = LV[c][0].copy()
            lv[:i0] = np.nan
            if name == "rule + AI":
                off = np.zeros(len(idx), dtype=bool)
                off[spot_c[c]] = True
                lv[off & ~keep_s] = np.nan
            ei, xi, ep, xp, ty = ws.run_book(D[c]["open"], D[c]["high"], D[c]["low"], D[c]["cf"], lv, tpd,
                                             np.full(len(idx), np.nan), 1, tick_s, wick.H, 0)
            g2 = np.log(xp / ep) * 1e4
            n2 = g2 - wr.fee_bp(FEES, c, ep, True) - np.where(ty == 1, wr.fee_bp(FEES, c, xp, True),
                                                               wr.fee_bp(FEES, c, xp, False) + ws.PERP[c][2] / ep * 1e4)
            trs = pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "strategy": name, "venue": "spot",
                                "type": ty, "gross_bp": g2, "net_bp": n2})
            all_tr += [trf, trs]
            rows.append(dict(coin=c, strategy=name, start=str(start.date()),
                             fut_minutes_traded=float(np.isfinite(F["close"][i0:]).mean()),
                             fut_trades=len(trf), fut_net_bp=trf.net_bp.mean(), fut_hit=(trf.net_bp > 0).mean(),
                             spot_trades=len(trs), spot_net_bp=trs.net_bp.mean(), spot_hit=(trs.net_bp > 0).mean(),
                             half_spread_bp=float(np.nanmean(hs_bp)) if len(hs_bp) else np.nan))
        print(f"  {c} done ({time.time() - t0:.0f}s)", flush=True)
    R = pd.DataFrame(rows)
    T = pd.concat(all_tr, ignore_index=True)
    T.to_parquet(os.path.join(ROOT, "reports", "wick_futures_trades.parquet"), index=False)
    pd.set_option("display.width", 250)
    print(R.round(2).to_string(index=False))
    # portfolio over the window where every included perp has data (latest listing start), and the longer
    # window of the four oldest perps
    starts = {r.coin: pd.Timestamp(r.start) for r in R.itertuples()}
    old3 = [c for c in ("ETH", "SOL", "XRP") if c in starts]
    windows = [("all listed perps, from 2025-12-13 (coins join as their perps list)", list(starts), pd.Timestamp("2025-12-13"))]
    if old3:
        windows.append(("ETH/SOL/XRP perps, from " + str(max(starts[c] for c in old3).date()), old3,
                        max(starts[c] for c in old3)))
    port = []
    for label, coins_, st in windows:
        for name in ("rule only", "rule + AI"):
            for venue in ("futures", "spot"):
                for cap in (None, 6):
                    tr = T[(T.strategy == name) & (T.venue == venue) & T.coin.isin(coins_) & (T.ts >= st)]
                    s_, _ = portfolio(tr, st, cap)
                    port.append(dict(window=label, strategy=name, venue=venue, cap=cap or "none", **s_))
    P = pd.DataFrame(port)
    P.to_csv(os.path.join(ROOT, "reports", "wick_futures_portfolio.csv"), index=False)
    R.to_csv(os.path.join(ROOT, "reports", "wick_futures.csv"), index=False)
    print(P.round(3).to_string(index=False))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
