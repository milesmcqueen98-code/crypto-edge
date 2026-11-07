#!/usr/bin/env python3
"""Red team h1pb (runs on Actions): independent fetch of ALL Coinbase perp prints 4:50 pm ET .. >= 7:08 pm ET on every
day for the given coins, spot prints around candidate minutes (own superset, k = 5), and an independent re-simulation
of the frozen variant for latency lam in {1, 2, 6} s, theta in {0.5, 0.25}, size from all prints or maker-BUY prints
only. Also per-minute venue statistics of the perp prints.

  python scripts/redteam_h1pb/rt_job.py --coins BTC,ETH --tag a [--mock]
Outputs: reports/hunt/h1pb/redteam/{trig,vmin}_<coin>.parquet, fetchlog_<tag>.csv; raw prints in out_rt/ (artifact).
"""
import argparse
import concurrent.futures as cf
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402  (product specs and the shared, paging-fixed TradeFetcher)
import rt_lib as R  # noqa: E402

NS, MIN_NS = R.NS, R.MIN_NS
OUT = os.path.join(ROOT, "reports", "hunt", "h1pb", "redteam")
RAW = os.path.join(ROOT, "out_rt")
ET = "America/New_York"
WIN = (16 * 60 + 55, 18 * 60 + 5)
LAMS = (1, 2, 6)
THETAS = (0.5, 0.25)
LAST_DAY = pd.Timestamp("2026-11-05")


def fetch_many(pid, wins, threads=3, rate=8.4):
    """All prints of pid in the union of [a, b) windows (pd.Timestamp, naive UTC)."""
    fs = [common.TradeFetcher(rate / threads) for _ in range(threads)]
    parts = [None] * len(wins)

    def work(w):
        for i in range(w, len(wins), threads):
            for att in range(3):
                try:
                    d = fs[w].window(pid, wins[i][0], wins[i][1])
                    break
                except Exception as e:  # noqa: BLE001
                    print("retry", pid, wins[i], repr(e)[:120], flush=True)
                    time.sleep(5 * (att + 1))
            else:
                raise RuntimeError(f"fetch failed {pid} {wins[i]}")
            parts[i] = d
    with cf.ThreadPoolExecutor(threads) as ex:
        list(ex.map(work, range(threads)))
    d = [x for x in parts if x is not None and len(x)]
    if not d:
        return pd.DataFrame({"trade_id": pd.Series(dtype="int64"), "time": pd.Series(dtype="datetime64[ns]"),
                             "price": pd.Series(dtype=float), "size": pd.Series(dtype=float),
                             "side": pd.Series(dtype=str)}), sum(f.n_req for f in fs), sum(getattr(f, "lost_seconds", 0) for f in fs)
    D = pd.concat(d, ignore_index=True)
    D["trade_id"] = D["trade_id"].astype(np.int64)
    D = D.drop_duplicates("trade_id").sort_values(["time", "trade_id"]).reset_index(drop=True)
    return D, sum(f.n_req for f in fs), sum(getattr(f, "lost_seconds", 0) for f in fs)


def day_windows(st):
    """Per ET date: [16:50 ET, end) in naive UTC, end = first traded perp minute >= 19:07 ET, + 1 min (>= 19:12 ET)."""
    idx = st["idx"]
    traded = np.isfinite(st["p_close"])
    nxt = np.full(len(idx) + 1, len(idx), np.int64)
    for i in range(len(idx) - 1, -1, -1):
        nxt[i] = i if traded[i] else nxt[i + 1]
    first_et = idx[0].tz_localize("UTC").tz_convert(ET).normalize().tz_localize(None)
    out = []
    for d in pd.date_range(first_et, LAST_DAY, freq="D"):
        a = (d + pd.Timedelta(minutes=16 * 60 + 50)).tz_localize(ET).tz_convert("UTC").tz_localize(None)
        e0 = (d + pd.Timedelta(minutes=19 * 60 + 7)).tz_localize(ET).tz_convert("UTC").tz_localize(None)
        i0 = int((e0.value - st["t0"]) // MIN_NS)
        if i0 >= len(idx):
            e = R.GRID_END
        else:
            j = nxt[max(i0, 0)]
            e = idx[j] + pd.Timedelta(minutes=1) if j < len(idx) else R.GRID_END
        e = max(e, (d + pd.Timedelta(minutes=19 * 60 + 12)).tz_localize(ET).tz_convert("UTC").tz_localize(None))
        e = min(e, a + pd.Timedelta(hours=9), R.GRID_END)
        if a < idx[0]:
            a = idx[0]
        if e > a:
            out.append((a, e))
    return out


def et_minute(t_ns):
    t = pd.to_datetime(t_ns).tz_localize("UTC").tz_convert(ET)
    return np.asarray(t.hour * 60 + t.minute)


def candidate_minutes(st, kc=5.0):
    """Own superset: grid minutes m with ET minute in [16:54, 18:06) whose perp candle low is below
    max(A_m, A_{m-1}), A_x = max(s_prev_x, spot high_x) x exp(bbar_x - kc sigma_x)."""
    with np.errstate(invalid="ignore"):
        A = np.fmax(st["s_prev"], st["s_hi"]) * np.exp(st["bbar"] - kc * st["sig"])
        A = np.where(st["sig"] > 0, A, np.nan)
        A2 = np.fmax(A, np.concatenate([[np.nan], A[:-1]]))
        c = st["p_low"] < A2
    m = et_minute(st["idx"].asi8)
    c &= (m >= WIN[0] - 1) & (m < WIN[1] + 1)
    return np.nonzero(c)[0]


def segments(minutes, n):
    """Merged [m-1, m+1) minute windows as (start, end) index pairs."""
    mk = np.zeros(n + 2, bool)
    for m in minutes:
        mk[max(m - 1, 0):min(m + 1, n)] = True
    d = np.diff(np.r_[False, mk, False].astype(np.int8))
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]))


def spot_ref(Tq, sp_t, sp_p, ssegs, st):
    """Last spot print <= Tq inside the spot segment containing Tq; else the spot close before the segment; NaN if
    Tq is in no fetched spot segment."""
    t0 = st["t0"]
    starts = np.array([t0 + a * MIN_NS for a, _ in ssegs], np.int64)
    ends = np.array([t0 + b * MIN_NS for _, b in ssegs], np.int64)
    out = np.full(len(Tq), np.nan)
    if not len(starts):
        return out
    k = np.searchsorted(starts, Tq, "right") - 1
    inside = (k >= 0) & (Tq < ends[np.maximum(k, 0)])
    j = np.searchsorted(sp_t, Tq, "right") - 1
    has = inside & (j >= 0) & (sp_t[np.maximum(j, 0)] >= starts[np.maximum(k, 0)])
    out[has] = sp_p[j[has]]
    fb = inside & ~has
    smin = np.array([a for a, _ in ssegs], np.int64)[np.maximum(k, 0)]
    out[fb] = np.where(smin[fb] >= 1, st["s_cf"][np.maximum(smin[fb] - 1, 0)], np.nan)
    return out


def venue_minutes(coin, st, D):
    """Per (ET date, ET minute) statistics of perp prints, with the depth of the minute's lowest print below the
    candle fair value in sigma units."""
    t = D["time"].to_numpy("datetime64[ns]").astype(np.int64)
    if not len(t):
        return pd.DataFrame()
    et = pd.to_datetime(t).tz_localize("UTC").tz_convert(ET)
    g = pd.DataFrame({"date": et.normalize().tz_localize(None), "etmin": et.hour * 60 + et.minute,
                      "p": D["price"].to_numpy(float) / R.PX_SCALE.get(coin, 1.0), "q": D["size"].to_numpy(float),
                      "buy": (D["side"].to_numpy() == "BUY").astype(np.int8), "t": t})
    g["qbuy"] = g.q * g.buy
    row = (t - st["t0"]) // MIN_NS
    r = np.clip(row, 0, st["n"] - 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        F = st["s_prev"][r] * np.exp(st["bbar"][r])
        g["z"] = np.log(g.p.to_numpy() / F) / st["sig"][r]
    a = g.groupby(["date", "etmin"]).agg(n=("q", "size"), q=("q", "sum"), nbuy=("buy", "sum"), qbuy=("qbuy", "sum"),
                                          pmin=("p", "min"), pmax=("p", "max"), zmin=("z", "min"), zmax=("z", "max"),
                                          nts=("t", "nunique"))
    a = a.reset_index()
    a["coin"] = coin
    return a


def run_coin(coin, mock=False):
    pid, cs, tick = common.PERP[coin]
    st = R.my_stats(coin, common.DATA, cs)
    log = dict(coin=coin)
    wins = day_windows(st)
    t1 = time.time()
    if mock:
        D = mock_prints(st, wins, "perp")
        nreq = lost = 0
    else:
        D, nreq, lost = fetch_many(pid, wins)
    log.update(perp_windows=len(wins), perp_prints=len(D), perp_req=nreq, perp_lost=lost, perp_secs=round(time.time() - t1))
    # completeness vs candles (contracts) over the fetched windows
    P = pd.read_parquet(os.path.join(common.DATA, "cfm", f"{coin}.parquet")).drop_duplicates("ts").set_index("ts")
    cv = 0.0
    for a, b in wins:
        cv += P.loc[(P.index >= a) & (P.index < b), "volume"].sum()
    log.update(print_contracts=float(D["size"].sum()), candle_contracts=float(cv))
    cand = candidate_minutes(st)
    ssegs = segments(cand, st["n"])
    sw = [(st["idx"][0] + pd.Timedelta(minutes=int(a)), st["idx"][0] + pd.Timedelta(minutes=int(b))) for a, b in ssegs]
    t1 = time.time()
    if mock:
        SP = mock_prints(st, sw, "spot")
        sreq = slost = 0
    else:
        SP, sreq, slost = fetch_many(f"{coin}-USD", sw)
    log.update(cand_minutes=len(cand), spot_segments=len(ssegs), spot_prints=len(SP), spot_req=sreq, spot_lost=slost,
               spot_secs=round(time.time() - t1))
    os.makedirs(RAW, exist_ok=True)
    D.to_parquet(os.path.join(RAW, f"perp_{coin}.parquet"), index=False, compression="zstd")
    SP.to_parquet(os.path.join(RAW, f"spot_{coin}.parquet"), index=False, compression="zstd")
    V = venue_minutes(coin, st, D)
    V.to_parquet(os.path.join(OUT, f"vmin_{coin}.parquet"), index=False, compression="zstd")
    # tape with one synthetic print per day window (the last perp candle close before it)
    sc = R.PX_SCALE.get(coin, 1.0)
    t = D["time"].to_numpy("datetime64[ns]").astype(np.int64)
    p = D["price"].to_numpy(float) / sc
    q = D["size"].to_numpy(float)
    sd = (D["side"].to_numpy() == "BUY").astype(np.int8)
    tid = D["trade_id"].to_numpy(np.int64)
    Ts, Ps, Qs, Ss, Gs, Ys, Is = [], [], [], [], [], [], []
    for g, (a, b) in enumerate(wins):
        i0, i1 = np.searchsorted(t, a.value, "left"), np.searchsorted(t, b.value, "left")
        ia = int((a.value - st["t0"]) // MIN_NS)
        prev = st["p_cf"][ia - 1] if ia >= 1 else np.nan
        Ts.append(np.r_[a.value - 1, t[i0:i1]])
        Ps.append(np.r_[prev, p[i0:i1]])
        Qs.append(np.r_[0.0, q[i0:i1]])
        Ss.append(np.r_[-1, sd[i0:i1]].astype(np.int8))
        Gs.append(np.full(i1 - i0 + 1, g, np.int32))
        Ys.append(np.r_[True, np.zeros(i1 - i0, bool)])
        Is.append(np.r_[-1, tid[i0:i1]])
    T = np.concatenate(Ts)
    Pp, Q, SD, SEG, SYN, TID = (np.concatenate(x) for x in (Ps, Qs, Ss, Gs, Ys, Is))
    em = et_minute(T)
    inwin = (em >= WIN[0]) & (em < WIN[1]) & ~SYN
    sp_t = SP["time"].to_numpy("datetime64[ns]").astype(np.int64)
    sp_p = SP["price"].to_numpy(float)
    o = np.argsort(sp_t, kind="stable")
    sp_t, sp_p = sp_t[o], sp_p[o]
    out = []
    for lam in LAMS:
        Sref = spot_ref(T - lam * NS, sp_t, sp_p, ssegs, st)
        Sref[SYN] = np.nan
        L, F, row = R.levels(st, T, Sref, lam * NS, tick, cs)
        L[~inwin] = np.nan
        for th in THETAS:
            for sb in (False, True):
                if sb and not (lam == 1 and th == 0.5):
                    continue
                oi, of = R.sim(T, Pp, Q, SD, SEG, SYN, L, F, inwin, tick, cs, th, sb, 10_000.0, 3600 * NS, NS, 2 * NS)
                E = pd.DataFrame(of, columns=R.COLS)
                E.insert(0, "t_fill", T[oi])
                E.insert(1, "coin", coin)
                E["lam"], E["theta"], E["size_buy_only"] = lam, th, sb
                E["S"] = Sref[oi]
                E["row"] = row[oi]
                E["p_trig"] = Pp[oi]
                E["p_prev"] = Pp[oi - 1]
                E["t_prev"] = T[oi - 1]
                E["side_trig"] = SD[oi]
                E["tid_trig"] = TID[oi]
                # spot path around the trigger (fetched spot prints only): min in [t-60s, t] and [t, t+60s]
                lo1 = np.searchsorted(sp_t, T[oi] - 60 * NS, "left")
                hi1 = np.searchsorted(sp_t, T[oi], "right")
                hi2 = np.searchsorted(sp_t, T[oi] + 60 * NS, "right")
                E["spot_min_before"] = [sp_p[x:y].min() if y > x else np.nan for x, y in zip(lo1, hi1)]
                E["spot_min_after"] = [sp_p[x:y].min() if y > x else np.nan for x, y in zip(hi1, hi2)]
                E["spot_last_after"] = [sp_p[y - 1] if y > x else np.nan for x, y in zip(hi1, hi2)]
                E = E[E.n >= 1]
                out.append(E)
    E = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    E.to_parquet(os.path.join(OUT, f"trig_{coin}.parquet"), index=False, compression="zstd")
    log.update(triggers=len(E), triggers_base=int(((E.lam == 1) & (E.theta == 0.5) & ~E.size_buy_only).sum()) if len(E) else 0)
    print(log, flush=True)
    return log


def mock_prints(st, wins, kind):
    """Local plumbing test only: synthetic prints from candles."""
    rows = []
    idx = st["idx"]
    for a, b in wins:
        i0 = max(int((a.value - st["t0"]) // MIN_NS), 0)
        i1 = min(int((b.value - st["t0"]) // MIN_NS), st["n"])
        for i in range(i0, i1):
            if kind == "perp":
                c, lo = st["p_close"][i], st["p_low"][i]
            else:
                c, lo = st["s_close"][i], st["s_lo"][i]
            if not np.isfinite(c):
                continue
            base = idx[i]
            rows.append((len(rows), base + pd.Timedelta(seconds=10), c, 3.0, "SELL"))
            rows.append((len(rows), base + pd.Timedelta(seconds=20), lo, 3.0, "BUY"))
            rows.append((len(rows), base + pd.Timedelta(seconds=40), c, 3.0, "SELL"))
    sc = R.PX_SCALE.get(st["coin"], 1.0) if kind == "perp" else 1.0
    d = pd.DataFrame(rows, columns=["trade_id", "time", "price", "size", "side"])
    d["price"] = d["price"] * sc
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", required=True)
    ap.add_argument("--tag", default="x")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    logs = []
    for c in a.coins.split(","):
        t1 = time.time()
        lg = run_coin(c, a.mock)
        lg["secs"] = round(time.time() - t1)
        logs.append(lg)
        pd.DataFrame(logs).to_csv(os.path.join(OUT, f"fetchlog_{a.tag}.csv"), index=False)


if __name__ == "__main__":
    main()
