#!/usr/bin/env python3
"""Gemini venue test (reports/gemini_prereg.md), step 2: the frozen R2-08 ladder on Gemini prints.

Inputs: data/gemini/levels.parquet (scripts/gemini/levels.py) and the Tardis artifacts (scripts/gemini/fetch_tardis.py)
in ART/<day>/{gem_trades,gem_quotes,cb_sec}.parquet and ART/meta/gemini_details.json.

Outputs in reports/gemini/: rungs.csv (one row per simulated rung fill), parents.csv, dislocations.csv (pure
synchronous gap episodes), daily.csv, summary.json.
Usage: python scripts/gemini/analyze.py ART
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import wick_sim as ws  # noqa: E402

OUT = os.path.join(ROOT, "reports", "gemini")
K = (4.0, 6.0, 8.0)
TP_SHARE, HOLD_S, SCAN_S, SHARED_S, RATIO_MIN, RATIO_N = 0.6, 3600, 900, 60, 240, 3
MARKS = (1, 10, 60, 300, 3600)
OOS0 = pd.Timestamp("2025-01-01")


def load_day(art, day):
    d = os.path.join(art, day)
    if not os.path.exists(os.path.join(d, "gem_trades.parquet")):
        return None, None, None
    g = pd.read_parquet(os.path.join(d, "gem_trades.parquet"))
    q = pd.read_parquet(os.path.join(d, "gem_quotes.parquet")) if os.path.exists(os.path.join(d, "gem_quotes.parquet")) else None
    c = pd.read_parquet(os.path.join(d, "cb_sec.parquet")) if os.path.exists(os.path.join(d, "cb_sec.parquet")) else None
    return g, q, c


def asof(sec_arr, val_arr, t):
    """Last value at or before second t (vectorised); NaN before the first."""
    i = np.searchsorted(sec_arr, t, side="right") - 1
    out = np.where(i >= 0, val_arr[np.maximum(i, 0)], np.nan)
    return out, np.where(i >= 0, t - sec_arr[np.maximum(i, 0)], np.nan)


def ratios(tsec, gpx, cb_last, minute0):
    """r for each minute of the day: median Gemini/Coinbase ratio of Gemini prints in the 240 minutes before it."""
    ok = np.isfinite(cb_last) & (cb_last > 0)
    t, rr = tsec[ok], gpx[ok] / cb_last[ok]
    r = np.ones(1440)
    for m in range(1440):
        s = minute0 + 60 * m
        a, b = np.searchsorted(t, s - 60 * RATIO_MIN), np.searchsorted(t, s)
        if b - a >= RATIO_N:
            r[m] = float(np.median(rr[a:b]))
    return r


def through(tsec, px, usd, sell, i0, bid, tick):
    """USD of taker sells (and of all prints) at or below bid - tick from print i0 until a print at or above the bid,
    at most SCAN_S seconds; and the index of the last print in that window."""
    n = len(px)
    tot_s = tot_a = 0.0
    j, last = i0, tsec[i0]
    while j < n and tsec[j] - tsec[i0] <= SCAN_S:
        if px[j] >= bid:
            break
        if px[j] <= bid - tick + 1e-12:
            tot_a += usd[j]
            last = tsec[j]
            if sell[j]:
                tot_s += usd[j]
        j += 1
    return tot_s, tot_a, last


def tp_hit(tsec, px, usd, buy, t_fill, tp, tick):
    """First print at or above tp + tick within HOLD_S after the fill; taker-buy USD at or above it in that hour."""
    a = np.searchsorted(tsec, t_fill, side="right")
    b = np.searchsorted(tsec, t_fill + HOLD_S, side="right")
    seg = px[a:b]
    hit = np.nonzero(seg >= tp + tick - 1e-12)[0]
    cap = float(usd[a:b][(seg >= tp + tick - 1e-12) & buy[a:b]].sum())
    return (float(tsec[a + hit[0]]) if len(hit) else np.nan), cap


def run_coin(day, coin, G, Q, C, L, tick_g, ai):
    """Ladders on one coin-day. ai=True: parents only while armed (pred > thr)."""
    G = G.sort_values(["timestamp", "id"])
    tsec = G.timestamp.to_numpy() / 1e6
    px = G.price.to_numpy().astype(float)
    usd = px * G.amount.to_numpy().astype(float)
    sell = (G.side.to_numpy() == "sell")
    buy = (G.side.to_numpy() == "buy")
    minute0 = pd.Timestamp(day).timestamp()
    cs = C.sec.to_numpy().astype(float) if C is not None else np.array([])
    cb_last_t, cb_age = asof(cs, C["last"].to_numpy(), np.floor(tsec)) if C is not None and len(C) else (np.full(len(px), np.nan),) * 2
    r = ratios(tsec, px, cb_last_t, minute0)
    Lm = L.set_index("m")
    fair = Lm.fair_log.reindex(range(1440)).to_numpy()
    sig = Lm.sig.reindex(range(1440)).to_numpy()
    lvl4cb = Lm.lvl4.reindex(range(1440)).to_numpy()
    armed = (Lm.pred > Lm.thr).reindex(range(1440)).fillna(False).to_numpy() if ai else np.ones(1440, bool)
    bids = {k: np.floor(np.exp(fair - k * sig) * r / tick_g + 1e-9) * tick_g for k in K}
    mins = ((tsec - minute0) // 60).astype(int)
    qs = Q.sec.to_numpy().astype(float) if Q is not None and len(Q) else np.array([])
    cbtick = ws.spot_tick(coin)
    rungs, parents = [], []
    busy_until = -np.inf
    i = 0
    n = len(px)
    while i < n:
        m = mins[i]
        if m < 0 or m >= 1440 or tsec[i] < busy_until or not armed[m] or not np.isfinite(bids[4.0][m]):
            i += 1
            continue
        b4 = bids[4.0][m]
        if px[i] > b4 - tick_g + 1e-12:
            i += 1
            continue
        tau = tsec[i]
        s = sig[m]
        tp4 = b4 * np.exp(TP_SHARE * 4.0 * s)
        t_tp4, _ = tp_hit(tsec, px, usd, buy, tau, tp4, tick_g)
        close = t_tp4 if np.isfinite(t_tp4) else tau + HOLD_S
        # shared with Coinbase: Coinbase traded through its own 4-sigma level within tau +- 60 s
        shared = False
        if C is not None and len(C) and np.isfinite(lvl4cb[m]):
            a, b = np.searchsorted(cs, np.floor(tau) - SHARED_S), np.searchsorted(cs, np.floor(tau) + SHARED_S, side="right")
            lo = C["low"].to_numpy()[a:b]
            shared = bool(len(lo) and np.nanmin(lo) <= lvl4cb[m] * (1 - cbtick / lvl4cb[m]) + 1e-12)
        pid = f"{day}|{coin}|{int(tau)}"
        parent_pool_s, parent_pool_a, pool_end = through(tsec, px, usd, sell, i, b4, tick_g)
        parents.append(dict(pid=pid, day=day, coin=coin, ts=pd.Timestamp(tau, unit="s"), minute=m, shared=shared,
                            sig_bp=s * 1e4, bid=b4, ratio=r[m], cb_last=cb_last_t[i], cb_age=cb_age[i],
                            gap_sig=np.log(px[i] / (r[m] * cb_last_t[i])) / s if np.isfinite(cb_last_t[i]) else np.nan,
                            pool_sell=parent_pool_s, pool_all=parent_pool_a, pool_end=pool_end - tau, close=close - tau,
                            pred=float(Lm.pred.get(m, np.nan)), thr=float(Lm.thr.get(m, np.nan))))
        for k in K:
            bk = bids[k][m]
            if k == 4.0:
                j = i
            else:
                a = np.searchsorted(tsec, tau + 1.0, side="left")
                b = np.searchsorted(tsec, close, side="left")
                hit = np.nonzero(px[a:b] <= bk - tick_g + 1e-12)[0]
                if not len(hit):
                    continue
                j = a + hit[0]
            tf = tsec[j]
            cap_s, cap_a, _ = through(tsec, px, usd, sell, j, bk, tick_g)
            tpk = bk * np.exp(TP_SHARE * k * s)
            t_tp, tp_cap = tp_hit(tsec, px, usd, buy, tf, tpk, tick_g)
            row = dict(pid=pid, day=day, coin=coin, k=k, ts=pd.Timestamp(tf, unit="s"), f_off=tf - tau, shared=shared,
                       bid=bk, sig_bp=s * 1e4, cap_sell=cap_s, cap_all=cap_a, tp=tpk, tp_hit=bool(np.isfinite(t_tp)),
                       tp_secs=t_tp - tf if np.isfinite(t_tp) else np.nan, tp_cap=tp_cap,
                       g_tp=1e4 * np.log(tpk / bk))
            # exit at 60 minutes: Gemini's best bid then (half-spread included); markouts
            for h in MARKS:
                cb, _ = asof(cs, C["last"].to_numpy(), np.array([np.floor(tf + h)])) if C is not None and len(C) else (np.array([np.nan]), None)
                row[f"m_cb_{h}"] = 1e4 * np.log(cb[0] * r[m] / bk) if np.isfinite(cb[0]) else np.nan
                if len(qs):
                    bb, _ = asof(qs, Q.bid_price.to_numpy(), np.array([np.floor(tf + h)]))
                    aa, _ = asof(qs, Q.ask_price.to_numpy(), np.array([np.floor(tf + h)]))
                    row[f"m_gem_{h}"] = 1e4 * np.log(0.5 * (bb[0] + aa[0]) / bk) if bb[0] > 0 and aa[0] > 0 else np.nan
                    if h == HOLD_S:
                        row["g60"] = 1e4 * np.log(bb[0] / bk) if bb[0] > 0 else np.nan
                        row["hs60_bp"] = 1e4 * np.log(aa[0] / bb[0]) / 2 if bb[0] > 0 and aa[0] > 0 else np.nan
            if not np.isfinite(row.get("g60", np.nan)):
                b60 = np.searchsorted(tsec, tf + HOLD_S, side="right") - 1
                row["g60"] = 1e4 * np.log(px[b60] / bk) - 5.0       # last print less a 5 bp half-spread
            rungs.append(row)
        busy_until = close
        i = np.searchsorted(tsec, close, side="right")
    return rungs, parents


def dislocations(day, coin, G, C, L):
    """Pure synchronous gaps: Gemini prints at least k sigma below r x Coinbase's last price at that second."""
    if C is None or not len(C):
        return []
    G = G.sort_values(["timestamp", "id"])
    tsec = G.timestamp.to_numpy() / 1e6
    px = G.price.to_numpy().astype(float)
    usd = px * G.amount.to_numpy().astype(float)
    sell = G.side.to_numpy() == "sell"
    minute0 = pd.Timestamp(day).timestamp()
    cs = C.sec.to_numpy().astype(float)
    cbl, age = asof(cs, C["last"].to_numpy(), np.floor(tsec))
    r = ratios(tsec, px, cbl, minute0)
    mins = ((tsec - minute0) // 60).astype(int)
    sig = L.set_index("m").sig.reindex(range(1440)).to_numpy()
    ok = (mins >= 0) & (mins < 1440)
    gap = np.full(len(px), np.nan)
    gap[ok] = np.log(px[ok] / (r[mins[ok]] * cbl[ok])) / sig[mins[ok]]
    out = []
    hit = np.nonzero(np.nan_to_num(gap, nan=0.0) <= -4.0)[0]
    if not len(hit):
        return out
    ep = np.cumsum(np.r_[1, np.diff(tsec[hit]) > 60])
    for e in np.unique(ep):
        idx = hit[ep == e]
        j0 = idx[0]
        worst = idx[np.argmin(gap[idx])]
        a = np.searchsorted(tsec, tsec[j0])
        mk = {}
        for h in (60, 300):
            b = np.searchsorted(tsec, tsec[j0] + h, side="right") - 1
            cb_h, _ = asof(cs, C["last"].to_numpy(), np.array([np.floor(tsec[j0] + h)]))
            mk[f"gem_vs_entry_{h}"] = 1e4 * np.log(px[b] / px[j0]) if b >= a else np.nan
            mk[f"cb_vs_entry_{h}"] = 1e4 * np.log(cb_h[0] * r[mins[j0]] / px[j0])
        out.append(dict(day=day, coin=coin, ts=pd.Timestamp(tsec[j0], unit="s"), n_prints=len(idx),
                        worst_gap_sig=float(gap[worst]), first_gap_sig=float(gap[j0]), sig_bp=sig[mins[j0]] * 1e4,
                        usd=float(usd[idx].sum()), sell_usd=float(usd[idx][sell[idx]].sum()),
                        cb_age_s=float(age[j0]), max_k=4 if gap[worst] > -6 else (6 if gap[worst] > -8 else 8), **mk))
    return out


def main(art):
    lv = pd.read_parquet(os.path.join(ROOT, "data", "gemini", "levels.parquet"))
    lv["day"] = lv.ts.dt.floor("D")
    lv["m"] = (lv.ts - lv.day).dt.total_seconds().astype(int) // 60
    det = json.load(open(os.path.join(art, "meta", "gemini_details.json")))
    ticks = {c: float(v.get("quote_increment")) for c, v in det.items() if v.get("quote_increment")}
    days = sorted(d for d in os.listdir(art) if d[:2] == "20")
    R, P, Dz, Dv = [], [], [], []
    for day in days:
        g, q, c = load_day(art, day)
        if g is None:
            continue
        for coin in sorted(g.coin.unique()):
            G = g[g.coin == coin]
            Qc = q[q.coin == coin] if q is not None else None
            Cc = c[c.coin == coin].sort_values("sec") if c is not None else None
            L = lv[(lv.coin == coin) & (lv.day == pd.Timestamp(day))]
            gem_usd = float((G.price * G.amount).sum())
            cb_usd = float(Cc.usd.sum()) if Cc is not None else np.nan
            Dv.append(dict(day=day, coin=coin, gem_usd=gem_usd, cb_usd=cb_usd, gem_prints=len(G),
                           gem_sell_usd=float((G.price * G.amount)[G.side == "sell"].sum())))
            if not len(L) or coin not in ticks:
                continue
            Dz += dislocations(day, coin, G, Cc, L)
            for ai in (False, True):
                if ai and pd.Timestamp(day) < OOS0:
                    continue
                rr, pp = run_coin(day, coin, G, Qc, Cc, L, ticks[coin], ai)
                for x in rr + pp:
                    x["ai"] = ai
                R += rr
                P += pp
        print(f"{day}: {len(R)} rungs, {len(P)} parents, {len(Dz)} gap episodes so far", flush=True)
    os.makedirs(OUT, exist_ok=True)
    pd.DataFrame(R).to_csv(os.path.join(OUT, "rungs.csv"), index=False)
    pd.DataFrame(P).to_csv(os.path.join(OUT, "parents.csv"), index=False)
    pd.DataFrame(Dz).to_csv(os.path.join(OUT, "dislocations.csv"), index=False)
    pd.DataFrame(Dv).to_csv(os.path.join(OUT, "volumes.csv"), index=False)
    json.dump({"days": days, "ticks": ticks}, open(os.path.join(OUT, "inputs.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
