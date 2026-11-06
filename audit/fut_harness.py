#!/usr/bin/env python3
"""Audit harness: re-implements scripts/wick_futures.py main() (17 perps, FEES=pct2, STRICT=0) so that
execution assumptions can be varied one at a time. Writes only under audit/.

Usage: python audit/fut_harness.py            (all variants)
"""
import os
import pickle
import sys
import time

import numba
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.argv = sys.argv[:1]                       # wick_futures reads COINS from argv at import
from edge import wick  # noqa: E402
import wick_ai as wa  # noqa: E402
import wick_futures as wf  # noqa: E402
import wick_robust as wr  # noqa: E402
import wick_sim as ws  # noqa: E402

OUT = os.path.join(ROOT, "audit")
COINS = ["ETH", "SOL", "XRP", "DOGE", "LTC", "LINK", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE", "ENA",
         "PEPE", "ONDO", "ZEC"]
ORDER_USD = 2500.0


@numba.njit(cache=True)
def run_book_v(O, Hh, Lo, Cf, lvl, tpd, tick, hmax, tp_ok):
    """wick_sim.run_book (long, no stop, cooldown 0) plus: a take-profit can only fill in a minute where tp_ok."""
    T = len(O)
    cap = T // 4 + 16
    ei = np.empty(cap, np.int64)
    xi = np.empty(cap, np.int64)
    ep = np.empty(cap, np.float64)
    xp = np.empty(cap, np.float64)
    ty = np.empty(cap, np.int8)
    n = 0
    pos = 0
    e_i = 0
    e_p = 0.0
    tp = 0.0
    for t in range(T):
        if n >= cap - 1:
            break
        if pos == 0:
            b = lvl[t]
            if np.isnan(b) or np.isnan(Lo[t]) or np.isnan(O[t]):
                continue
            if (O[t] > b) and (Lo[t] <= b * (1.0 - tick[t])):
                pos = 1
                e_i = t
                e_p = b
                tp = b * np.exp(tpd[t]) if not np.isnan(tpd[t]) else np.inf
            continue
        if np.isnan(Lo[t]):
            if t - e_i >= hmax and not np.isnan(Cf[t]):
                ei[n] = e_i; xi[n] = t; ep[n] = e_p; xp[n] = Cf[t]; ty[n] = 3
                n += 1
                pos = 0
            continue
        if Hh[t] >= tp * (1.0 + tick[t]) and tp_ok[t]:
            px = tp
            ty_ = 1
        elif t - e_i >= hmax:
            px = Cf[t]
            ty_ = 3
        else:
            continue
        ei[n] = e_i; xi[n] = t; ep[n] = e_p; xp[n] = px; ty[n] = ty_
        n += 1
        pos = 0
    return ei[:n], xi[:n], ep[:n], xp[:n], ty[:n]


def setup():
    t0 = time.time()
    idx, D = ws.load_ohlc(coins=["BTC"] + COINS)
    cf = {c: D[c]["cf"] for c in D}
    vol = {c: D[c]["vol"] for c in D}
    LV = wick.levels(cf, COINS)
    spot_c = wf.spot_candidates(D, LV, COINS)
    FS = wf.fut_specs()
    fut = {c: wf.load_futures(c, idx) for c in COINS}
    # all rows any variant may need the AI decision for: every minute where a futures or spot bid could fill,
    # under the original level and the 1-minute-delayed level; panel rows r (decision for minute r) and r-1
    need = {}
    for c in COINS:
        F = fut[c]
        r = [spot_c[c]]
        tick_f = np.nan_to_num(FS[c][2] / F["cf"], nan=1.0)
        tick_s = np.nan_to_num(ws.PERP[c][2] / D[c]["cf"], nan=1.0)
        for lag in (0, 1):
            for basis in ("orig", "clean", "fresh"):
                lf = fut_level(D, LV, FS, fut, c, basis, lag)[0]
                r.append(wf.candidates(F["open"], F["low"], lf, tick_f))
            r.append(wf.candidates(D[c]["open"], D[c]["low"], wick.shift(LV[c][0], lag), tick_s))
        rr = np.unique(np.concatenate(r))
        rr = np.unique(np.concatenate([rr, rr - 1]))
        need[c] = rr[rr > 0]
    pn = wick.panel(cf, vol, COINS, idx, keep_rows=need)
    print(f"panel rows: {sum(len(v) for v in need.values())} ({time.time() - t0:.0f}s)", flush=True)
    X = wf.spot_training_set(D, pn, idx, COINS, lv=LV, cands=spot_c)
    models = wf.quarterly_models(X)
    print(f"spot candidates {len(X)}, models trained ({time.time() - t0:.0f}s)", flush=True)
    # AI decision per panel row (row r = features known at end of r-1); test period only
    keep = {}
    for c in COINS:
        p = pn[c]
        ok = np.zeros(len(idx), dtype=bool)
        sel = p.index >= pd.Timestamp("2025-01-01")
        rows = p.pos.to_numpy()[sel]
        qs = pd.PeriodIndex(p.index[sel], freq="Q")
        feats = p.loc[sel, wick.FEATS]
        for q in np.unique(qs):
            m, thr = models[q]
            ok[rows[qs == q]] = m.predict(feats[qs == q]) > thr
        keep[c] = ok
    return idx, D, LV, spot_c, FS, fut, keep, X


def fut_level(D, LV, FS, fut, c, basis, lag):
    F, S = fut[c], D[c]
    lvl_s, sig = LV[c]
    if lag:
        lvl_s, sig = wick.shift(lvl_s, lag), wick.shift(sig, lag)
    traded = np.isfinite(F["close"])
    if basis == "orig":
        bas = wick.shift(F["cf"] / S["cf"], 1 + lag)
    elif basis == "clean":     # ratio at the last futures trade, against the spot price of that same minute
        b_last = pd.Series(np.where(traded, F["close"] / S["cf"], np.nan)).ffill(limit=30).to_numpy()
        bas = wick.shift(b_last, 1 + lag)
    elif basis == "fresh":     # orig, but only when the futures traded in the previous minute
        bas = wick.shift(np.where(traded, F["close"] / S["cf"], np.nan), 1 + lag)
    return wick.round_down(lvl_s * bas, FS[c][2]), lvl_s, sig


def fut_run(idx, D, LV, FS, fut, keep, c, ai, basis="orig", lag=0, vol_entry=0.0, vol_tp=0.0, spot_confirm=False,
            fees="pct2", exit_mode="orig", hs_mult=1.0, hs_meas=None):
    F = fut[c]
    S = D[c]
    start = (F["first"] + pd.Timedelta(days=1)).normalize()
    i0 = idx.get_indexer([start])[0]
    pid, size_f, tick_usd = FS[c]
    traded = np.isfinite(F["close"])
    lv, lvl_s, sig = fut_level(D, LV, FS, fut, c, basis, lag)
    tick_f = np.nan_to_num(tick_usd / F["cf"], nan=1.0)
    need = np.ceil(ORDER_USD / (size_f * lv))
    with np.errstate(invalid="ignore"):
        if vol_entry > 0:
            lv = np.where(F["vol"] >= vol_entry * need, lv, np.nan)
        if spot_confirm:       # spot itself traded down to the spot level in the same minute
            lv = np.where(S["low"] <= lvl_s, lv, np.nan)
    lv[:i0] = np.nan
    if ai:
        cand = wf.candidates(F["open"], F["low"], lv, tick_f)
        k_ = keep[c] if not lag else np.r_[False, keep[c][:-1]]        # lag: decision of the previous minute
        off = np.zeros(len(idx), dtype=bool)
        off[cand] = True
        lv[off & ~k_] = np.nan
    b_last = pd.Series(np.where(traded, F["close"] / S["cf"], np.nan)).ffill().to_numpy()
    if exit_mode == "orig":
        exit_px = np.fmin(F["cf"], S["cf"] * b_last)
    elif exit_mode == "spot":    # time exit at spot close x last basis (no stale futures print)
        exit_px = np.where(traded, F["close"], S["cf"] * b_last)
    tpd = wick.THETA * wick.K * sig
    nf = np.ceil(ORDER_USD / (size_f * np.nan_to_num(F["cf"], nan=np.inf)))
    tp_ok = F["vol"] >= vol_tp * nf if vol_tp > 0 else np.ones(len(idx), dtype=bool)
    ei, xi, ep, xp, ty = run_book_v(F["open"], F["high"], F["low"], exit_px, lv, tpd, tick_f, wick.H, tp_ok)
    xp = np.where(ty == 1, wick.round_down(xp, tick_usd), xp)
    gross = np.log(xp / ep) * 1e4
    hs = (hs_meas or {}).get(c, np.nan)
    hs_bp = hs_mult * np.where(np.isfinite(hs), hs, tick_usd / ep * 1e4)

    def fee(px, maker):
        if fees == "contract":
            return wr.FEE_CONTRACT_USD / (size_f * px) * 1e4
        return np.full_like(px, 2.0)
    net = gross - fee(ep, True) - np.where(ty == 1, fee(xp, True), fee(xp, False) + hs_bp)
    return pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "type": ty, "gross_bp": gross, "net_bp": net,
                         "ei": ei, "xi": xi, "ep": ep, "xp": xp, "start": start})


def spot_run(idx, D, LV, spot_c, keep, c, ai, start, lag=0, fees="pct2"):
    S = D[c]
    i0 = idx.get_indexer([start])[0]
    lv, sig = LV[c][0].copy(), LV[c][1]
    if lag:
        lv, sig = wick.shift(lv, lag), wick.shift(sig, lag)
    lv[:i0] = np.nan
    tick_s = np.nan_to_num(ws.PERP[c][2] / S["cf"], nan=1.0)
    if ai:
        cand = wf.candidates(S["open"], S["low"], lv, tick_s)
        k_ = keep[c] if not lag else np.r_[False, keep[c][:-1]]
        off = np.zeros(len(idx), dtype=bool)
        off[cand] = True
        lv[off & ~k_] = np.nan
    ei, xi, ep, xp, ty = ws.run_book(S["open"], S["high"], S["low"], S["cf"], lv, wick.THETA * wick.K * sig,
                                     np.full(len(idx), np.nan), 1, tick_s, wick.H, 0)
    g2 = np.log(xp / ep) * 1e4
    n2 = g2 - 2.0 - np.where(ty == 1, 2.0, 2.0 + ws.PERP[c][2] / ep * 1e4)
    return pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "type": ty, "gross_bp": g2, "net_bp": n2,
                         "ei": ei, "xi": xi, "ep": ep, "xp": xp})


def port(T, coins, st):
    out = {}
    for cap in (None, 6):
        tr = T[T.coin.isin(coins) & (T.ts >= st)]
        s, _ = wf.portfolio(tr, st, cap)
        out[cap or "none"] = s
    return out


def main():
    t0 = time.time()
    cache = os.path.join(OUT, "fut_setup.pkl")
    idx, D, LV, spot_c, FS, fut, keep, X = setup()
    hs_meas = wf.half_spread_bp()
    variants = [
        ("base (reproduces wick_futures)", dict()),
        ("clean basis (last fut trade / same-minute spot)", dict(basis="clean")),
        ("fresh basis (fut traded at t-1, else no bid)", dict(basis="fresh")),
        ("entry minute fut volume >= 1x order", dict(vol_entry=1.0)),
        ("entry + TP minute fut volume >= 1x order", dict(vol_entry=1.0, vol_tp=1.0)),
        ("entry + TP minute fut volume >= 3x order", dict(vol_entry=3.0, vol_tp=3.0)),
        ("spot also reached the spot level in the fill minute", dict(spot_confirm=True)),
        ("fees $0.20/contract/side", dict(fees="contract")),
        ("time-exit price: spot x last basis when no fut trade", dict(exit_mode="spot")),
        ("market exits pay 2x measured half-spread", dict(hs_mult=2.0)),
        ("1-minute extra latency (level, basis, AI all 1 min older)", dict(lag=1)),
        ("combined: clean basis + vol>=1x entry/TP + $0.20/contract", dict(basis="clean", vol_entry=1.0, vol_tp=1.0, fees="contract")),
    ]
    rows = []
    starts = {c: (fut[c]["first"] + pd.Timedelta(days=1)).normalize() for c in COINS}
    old3 = ["ETH", "SOL", "XRP"]
    w_all, w_old = pd.Timestamp("2025-12-13"), max(starts[c] for c in old3)
    keep_tr = {}
    for name, kw in variants:
        for ai in (False, True):
            T = pd.concat([fut_run(idx, D, LV, FS, fut, keep, c, ai, hs_meas=hs_meas, **kw) for c in COINS], ignore_index=True)
            keep_tr[name, ai] = T
            for wlab, coins, st in (("all17 from 2025-12-13", COINS, w_all), ("ETH/SOL/XRP from 2025-08-16", old3, w_old)):
                for cap, s in port(T, coins, st).items():
                    rows.append(dict(variant=name, strategy="rule + AI" if ai else "rule only", venue="futures",
                                     window=wlab, cap=cap, **s))
        print(f"  {name} ({time.time() - t0:.0f}s)", flush=True)
    for name, kw in [("spot, same windows (reproduces)", dict()), ("spot, 1-minute extra latency", dict(lag=1))]:
        for ai in (False, True):
            T = pd.concat([spot_run(idx, D, LV, spot_c, keep, c, ai, starts[c], **kw) for c in COINS], ignore_index=True)
            keep_tr[name, ai] = T
            for wlab, coins, st in (("all17 from 2025-12-13", COINS, w_all), ("ETH/SOL/XRP from 2025-08-16", old3, w_old)):
                for cap, s in port(T, coins, st).items():
                    rows.append(dict(variant=name, strategy="rule + AI" if ai else "rule only", venue="spot",
                                     window=wlab, cap=cap, **s))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, "fut_variants.csv"), index=False)
    with open(os.path.join(OUT, "fut_trades.pkl"), "wb") as fh:
        pickle.dump(keep_tr, fh)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    cols = ["variant", "strategy", "venue", "window", "cap", "trades", "net_bp", "hit", "sharpe", "ann_ret", "maxdd"]
    print(R[cols].round(3).to_string(index=False))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
