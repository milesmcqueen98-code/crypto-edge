#!/usr/bin/env python3
"""Gemini venue test (reports/gemini_prereg.md), step 2: the frozen R2-08 ladder on Gemini prints.

Inputs: data/gemini/levels.parquet (scripts/gemini/levels.py) and the enriched Gemini prints
data/gemini/prints/<day>.parquet (scripts/gemini/enrich.py: each print carries Coinbase's synchronous last price,
Coinbase's low within +-60 s, Coinbase and Gemini-book marks at +h seconds).

Outputs in reports/gemini/: rungs.csv (one row per simulated rung fill), parents.csv, dislocations.csv (pure
synchronous gap episodes), volumes.csv, inputs.json.
Usage: python scripts/gemini/analyze.py
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import wick_sim as ws  # noqa: E402

DATA = os.path.join(ROOT, "data", "gemini")
OUT = os.path.join(ROOT, "reports", "gemini")
K = (4.0, 6.0, 8.0)
TP_SHARE, HOLD_S, SCAN_S, RATIO_MIN, RATIO_N = 0.6, 3600, 900, 240, 3
MARKS = (1, 10, 60, 300, 3600)
OOS0 = pd.Timestamp("2025-01-01")


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
    at most SCAN_S seconds; and the time of the last such print."""
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
    above = seg >= tp + tick - 1e-12
    hit = np.nonzero(above)[0]
    cap = float(usd[a:b][above & buy[a:b]].sum())
    return (float(tsec[a + hit[0]]) if len(hit) else np.nan), cap


def mark(G, j, col):
    return float(G[col].iat[j]) if col in G else np.nan


def run_coin(day, coin, G, L, tick_g, ai):
    """Ladders on one coin-day. ai=True: parents only while armed (pred > thr)."""
    tsec = G.ts_us.to_numpy() / 1e6
    px = G.price.to_numpy()
    usd = px * G.amount.to_numpy()
    sell = G.side.to_numpy() == "sell"
    buy = G.side.to_numpy() == "buy"
    cbl = G.cb_last.to_numpy() if "cb_last" in G else np.full(len(px), np.nan)
    minute0 = pd.Timestamp(day).timestamp()
    r = ratios(tsec, px, cbl, minute0)
    Lm = L.set_index("m")
    fair = Lm.fair_log.reindex(range(1440)).to_numpy()
    sig = Lm.sig.reindex(range(1440)).to_numpy()
    lvl4cb = Lm.lvl4.reindex(range(1440)).to_numpy()
    pred = Lm.pred.reindex(range(1440)).to_numpy()
    thr = Lm.thr.reindex(range(1440)).to_numpy()
    armed = (pred > thr) if ai else np.ones(1440, bool)
    bids = {k: np.floor(np.exp(fair - k * sig) * r / tick_g + 1e-9) * tick_g for k in K}
    mins = ((tsec - minute0) // 60).astype(int)
    cbtick = ws.spot_tick(coin)
    rungs, parents = [], []
    busy_until = -np.inf
    i, n = 0, len(px)
    while i < n:
        m = mins[i]
        if m < 0 or m >= 1440 or tsec[i] < busy_until or not armed[m] or not np.isfinite(bids[4.0][m]):
            i += 1
            continue
        b4 = bids[4.0][m]
        if px[i] > b4 - tick_g + 1e-12:
            i += 1
            continue
        tau, s = tsec[i], sig[m]
        tp4 = b4 * np.exp(TP_SHARE * 4.0 * s)
        t_tp4, _ = tp_hit(tsec, px, usd, buy, tau, tp4, tick_g)
        close = t_tp4 if np.isfinite(t_tp4) else tau + HOLD_S
        lo60 = mark(G, i, "cb_low_pm60")
        shared = bool(np.isfinite(lo60) and np.isfinite(lvl4cb[m]) and lo60 <= lvl4cb[m] - cbtick + 1e-12)
        pid = f"{day}|{coin}|{int(tau)}"
        pool_s, pool_a, pool_end = through(tsec, px, usd, sell, i, b4, tick_g)
        parents.append(dict(pid=pid, day=day, coin=coin, ts=pd.Timestamp(tau, unit="s"), minute=m, shared=shared,
                            sig_bp=s * 1e4, bid=b4, ratio=r[m], cb_last=cbl[i], cb_age=mark(G, i, "cb_age"),
                            cb_low_pm60=lo60, cb_lvl4=lvl4cb[m],
                            gap_sig=np.log(px[i] / (r[m] * cbl[i])) / s if np.isfinite(cbl[i]) else np.nan,
                            pool_sell=pool_s, pool_all=pool_a, pool_end=pool_end - tau, close=close - tau,
                            pred=pred[m], thr=thr[m]))
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
                       tp_secs=t_tp - tf if np.isfinite(t_tp) else np.nan, tp_cap=tp_cap, g_tp=1e4 * np.log(tpk / bk))
            for h in MARKS:
                cb = mark(G, j, f"cb_last_{h}")
                row[f"m_cb_{h}"] = 1e4 * np.log(cb * r[m] / bk) if np.isfinite(cb) and cb > 0 else np.nan
                bb, aa = mark(G, j, f"gbid_{h}"), mark(G, j, f"gask_{h}")
                row[f"m_gem_{h}"] = 1e4 * np.log(0.5 * (bb + aa) / bk) if bb > 0 and aa > 0 else np.nan
            bb, aa = mark(G, j, f"gbid_{HOLD_S}"), mark(G, j, f"gask_{HOLD_S}")
            row["hs60_bp"] = 1e4 * np.log(aa / bb) / 2 if bb > 0 and aa > bb else np.nan
            if bb > 0:
                row["g60"] = 1e4 * np.log(bb / bk)                     # sold at Gemini's best bid at minute 60
            else:
                b60 = np.searchsorted(tsec, tf + HOLD_S, side="right") - 1
                row["g60"] = 1e4 * np.log(px[b60] / bk) - 5.0         # last print less a 5 bp half-spread
            rungs.append(row)
        busy_until = close
        i = int(np.searchsorted(tsec, close, side="right"))
    return rungs, parents


def dislocations(day, coin, G, L):
    """Pure synchronous gaps: Gemini prints at least 4 sigma below r x Coinbase's last price at that second."""
    if "cb_last" not in G:
        return []
    tsec = G.ts_us.to_numpy() / 1e6
    px = G.price.to_numpy()
    usd = px * G.amount.to_numpy()
    sell = G.side.to_numpy() == "sell"
    cbl, age = G.cb_last.to_numpy(), G.cb_age.to_numpy()
    minute0 = pd.Timestamp(day).timestamp()
    r = ratios(tsec, px, cbl, minute0)
    mins = ((tsec - minute0) // 60).astype(int)
    sig = L.set_index("m").sig.reindex(range(1440)).to_numpy()
    ok = (mins >= 0) & (mins < 1440)
    gap = np.full(len(px), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        gap[ok] = np.log(px[ok] / (r[mins[ok]] * cbl[ok])) / sig[mins[ok]]
    hit = np.nonzero(np.nan_to_num(gap, nan=0.0) <= -4.0)[0]
    out = []
    if not len(hit):
        return out
    ep = np.cumsum(np.r_[1, np.diff(tsec[hit]) > 60])
    for e in np.unique(ep):
        idx = hit[ep == e]
        j0, worst = idx[0], idx[np.argmin(gap[idx])]
        mk = {}
        for h in (60, 300):
            b = np.searchsorted(tsec, tsec[j0] + h, side="right") - 1
            cb_h = mark(G, j0, f"cb_last_{h}")
            mk[f"gem_vs_entry_{h}"] = 1e4 * np.log(px[b] / px[j0])
            mk[f"cb_vs_entry_{h}"] = 1e4 * np.log(cb_h * r[mins[j0]] / px[j0]) if np.isfinite(cb_h) else np.nan
            bb, aa = mark(G, j0, f"gbid_{h}"), mark(G, j0, f"gask_{h}")
            mk[f"gem_mid_vs_entry_{h}"] = 1e4 * np.log(0.5 * (bb + aa) / px[j0]) if bb > 0 and aa > 0 else np.nan
        bb0, aa0 = mark(G, j0, "gbid_0"), mark(G, j0, "gask_0")
        out.append(dict(day=day, coin=coin, ts=pd.Timestamp(tsec[j0], unit="s"), n_prints=len(idx),
                        worst_gap_sig=float(gap[worst]), first_gap_sig=float(gap[j0]), sig_bp=sig[mins[j0]] * 1e4,
                        usd=float(usd[idx].sum()), sell_usd=float(usd[idx][sell[idx]].sum()), cb_age_s=float(age[j0]),
                        gem_spread_bp=1e4 * np.log(aa0 / bb0) if bb0 > 0 and aa0 > 0 else np.nan, **mk))
    return out


def main():
    lv = pd.read_parquet(os.path.join(DATA, "levels.parquet"))
    lv["day"] = lv.ts.dt.floor("D")
    lv["m"] = (lv.ts - lv.day).dt.total_seconds().astype(int) // 60
    metas = sorted(glob.glob(os.path.join(DATA, "meta_*_gemini_details.json")))
    det = json.load(open(metas[-1]))
    ticks = {c: float(v["quote_increment"]) for c, v in det.items() if v.get("quote_increment")}
    files = sorted(glob.glob(os.path.join(DATA, "prints", "20*.parquet")))
    R, P, Dz = [], [], []
    for f in files:
        day = os.path.basename(f)[:10]
        g = pd.read_parquet(f)
        for coin in sorted(g.coin.unique()):
            G = g[g.coin == coin].sort_values(["ts_us", "id"]).reset_index(drop=True)
            L = lv[(lv.coin == coin) & (lv.day == pd.Timestamp(day))]
            if not len(L) or coin not in ticks:
                continue
            Dz += dislocations(day, coin, G, L)
            for ai in (False, True):
                if ai and pd.Timestamp(day) < OOS0:
                    continue
                rr, pp = run_coin(day, coin, G, L, ticks[coin], ai)
                for x in rr + pp:
                    x["ai"] = ai
                R += rr
                P += pp
        print(f"{day}: {len(R)} rungs, {len(P)} parents, {len(Dz)} gap episodes so far", flush=True)
    os.makedirs(OUT, exist_ok=True)
    pd.DataFrame(R).to_csv(os.path.join(OUT, "rungs.csv"), index=False)
    pd.DataFrame(P).to_csv(os.path.join(OUT, "parents.csv"), index=False)
    pd.DataFrame(Dz).to_csv(os.path.join(OUT, "dislocations.csv"), index=False)
    V = pd.concat([pd.read_csv(v) for v in sorted(glob.glob(os.path.join(DATA, "volumes_*.csv")))], ignore_index=True)
    V.sort_values(["day", "coin"]).to_csv(os.path.join(OUT, "volumes.csv"), index=False)
    days_lv = sorted({os.path.basename(f)[:10] for f in files} & {d.strftime("%Y-%m-%d") for d in lv.day.unique()})
    json.dump({"days": [os.path.basename(f)[:10] for f in files], "days_with_levels": days_lv, "ticks": ticks},
              open(os.path.join(OUT, "inputs.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
