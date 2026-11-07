#!/usr/bin/env python3
"""H10 (XQ) step 3 (GitHub Actions, sharded by pair): 1-minute Exchange candles for each secondary pair on its universe
days (data/hunt/h10xq/universe.parquet: the top-10 books of each quote set by trailing ADV; plus 4 warm-up days and 1
day after) and for every USD leg not on disk; the SPEC's cross residual, fair value and sigma; and every POTENTIAL FILL
EVENT of the resting bid for k in {3, 4, 6}, with candle-based outcome fields. The sequencing (one position per pair,
<= 6 open, slots by capital) and all P&L are done later by sim.py.

SPEC (reports/hunt/h10xq/SPEC.md):
  c = log(X-Q close) - log(X-USD close / Q-USD close) on minutes where all three traded
  c_bar = trailing 24 h median of c; sigma_c = trailing 3-day std of c (both known at t-1)
  F = (X-USD / Q-USD at t-1) * exp(c_bar); bid = F * exp(-k sigma_c), floored to the pair's quote_increment
  candle fill: the minute opened above the bid and traded through it by >= 1 tick
Engineering (REPORT): >= 30 joint minutes for c_bar and >= 120 for sigma_c; leg closes forward-filled <= 30 min;
statistics carried <= 6 h past the last joint minute.

Mode `dev` writes events for DEV days only (< 2026-06-01). Mode `hold` (run only after the freeze commit) writes
events for HOLD days only, for the quote set given.
Outputs: data/hunt/h10xq/ev/<mode>_ev_<shard>.parquet, <mode>_diag_<shard>.parquet, <mode>_pairs_<shard>.csv
usage: python scripts/hunt/h10xq/events.py <mode> <shard> <nshards> [qset]
"""
import os
import sys
import time

import numba
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from cbx import Candles  # noqa: E402
import common  # noqa: E402

DATA = os.path.join(ROOT, "data", "hunt", "h10xq")
HOLD0 = pd.Timestamp("2026-06-01")
END = pd.Timestamp("2026-11-05")
DEV = (pd.date_range("2022-01-01", "2023-12-31"), pd.date_range("2025-01-01", "2026-05-31"))
HOLD = (pd.date_range("2026-06-01", END),)
KS = (3.0, 4.0, 6.0)
HS = (30, 60)
TP_FRAC = 0.6
SCAN = 15
MIN_MED, MIN_SIG = 30, 120
FFILL, STALE = 30, 360
WARM, AFTER = 4, 1
LOCAL = {"minute": (pd.Timestamp("2024-01-01"), pd.Timestamp("2026-11-06")),
         "minute_early": (pd.Timestamp("2021-01-01"), pd.Timestamp("2024-01-01"))}


def day_ranges(days):
    days = sorted(days)
    out, s, prev = [], days[0], days[0]
    for d in days[1:] + [None]:
        if d is None or (d - prev).days > 1:
            out.append((s, prev + pd.Timedelta(days=1)))
            s = d
        prev = d if d is not None else prev
    return out


_LEG = {}


def local_leg(coin):
    if coin not in _LEG:
        parts = [common.load_minute(coin, src) for src in ("minute_early", "minute")]
        parts = [p.astype(np.float64) for p in parts if p is not None]
        L = pd.concat(parts).sort_index() if parts else None
        _LEG[coin] = L[~L.index.duplicated()] if L is not None else None
    return _LEG[coin]


def local_cover(coin, d):
    return any(a <= d < b and os.path.exists(os.path.join(common.DATA, src, f"{coin}.parquet"))
               for src, (a, b) in LOCAL.items())


class Store:
    def __init__(self, C):
        self.C, self.have = C, {}

    def get(self, prod, days):
        h = self.have.setdefault(prod, {"days": set(), "df": []})
        new = sorted(set(days) - h["days"])
        for a, b in (day_ranges(new) if new else []):
            d = self.C.range(prod, a, b, 60)
            if len(d):
                h["df"].append(d)
        h["days"] |= set(new)
        if not h["df"]:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], dtype=float)
        if len(h["df"]) > 1:
            h["df"] = [pd.concat(h["df"], ignore_index=True).drop_duplicates("ts").sort_values("ts")]
        d = h["df"][0]
        return d[d.volume > 0].set_index("ts")


_PRE = {}


def prefetched(prod):
    if prod not in _PRE:
        import glob
        fs = sorted(glob.glob(os.path.join(DATA, "legs", f"{prod}__*.parquet")))
        if fs:
            d = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates("ts").sort_values("ts")
            d = d[d.volume > 0].set_index("ts")
            _PRE[prod] = (d, set(d.index.floor("D")))
        else:
            _PRE[prod] = None
    return _PRE[prod]


def leg_frame(store, prod, days):
    coin = prod[:-4]
    pre = prefetched(prod)
    parts = []
    if pre is not None:
        d0, have = pre
        got = [d for d in days if d in have]
        if got:
            parts.append(d0[d0.index.floor("D").isin(got)])
        days = [d for d in days if d not in have]
    loc = [d for d in days if local_cover(coin, d)]
    rem = [d for d in days if not local_cover(coin, d)]
    if loc:
        L = local_leg(coin)
        if L is not None:
            parts.append(L[L.index.floor("D").isin(loc)])
    if rem:
        parts.append(store.get(prod, rem))
    parts = [p for p in parts if len(p)]
    if not parts:
        return None
    d = pd.concat(parts).sort_index()
    return d[~d.index.duplicated()]


def btc_z15(idx):
    """BTC-USD 15-minute log move to t-1 over the trailing 3-day std of 15-minute moves known at t-1."""
    B = local_leg("BTC")
    b = B.close.reindex(idx).ffill(limit=FFILL)
    lb = np.log(b)
    m15 = lb - lb.shift(15)
    sd = m15.rolling(3 * 1440, min_periods=1440).std()
    return (m15 / sd).shift(1).to_numpy()


@numba.njit(cache=True)
def outcomes(mn, o, h, l, v, lvl, tp, xo, qo, qc, ev, tick, scan, hs):
    """For each potential fill minute ev[e] (index): candle through-volume below the level (quote units, at the
    mid of the level and the low) while the price stays below it (<= scan minutes after the fill minute, contiguous
    minutes); exit (a) per H: first TP trade-through minute, quote volume above TP until the exit, market-exit minute
    (first traded minute >= i+H+1); exit (b): first traded minute >= i+1 of each USD leg."""
    n = len(ev)
    nh = len(hs)
    thru = np.zeros(n)
    nb = np.zeros(n, np.int64)
    tp_i = np.full((n, nh), -1, np.int64)
    tp_vol = np.zeros((n, nh))
    mx_i = np.full((n, nh), -1, np.int64)
    hx_i = np.full(n, -1, np.int64)
    hq_i = np.full(n, -1, np.int64)
    T = len(o)
    for e in range(n):
        i = ev[e]
        b = lvl[i]
        tot = 0.0
        for j in range(i, min(T, i + scan + 1)):
            if mn[j] - mn[i] != j - i:
                break
            if np.isnan(l[j]) or l[j] >= b:
                if j == i:
                    continue
                break
            rng = h[j] - l[j]
            frac = 1.0 if rng <= 0 else min(1.0, (b - l[j]) / rng)
            tot += v[j] * frac * 0.5 * (b + l[j])
            nb[e] = j - i + 1
        thru[e] = tot
        for k in range(nh):
            H = hs[k]
            t = tp[e]
            for j in range(i + 1, min(T, i + H + 1)):
                if mn[j] - mn[i] > H:
                    break
                if not np.isnan(h[j]) and h[j] >= t + 0.5 * tick:
                    if tp_i[e, k] < 0:
                        tp_i[e, k] = j
                    rng = h[j] - l[j]
                    frac = 1.0 if rng <= 0 else min(1.0, (h[j] - t) / rng)
                    tp_vol[e, k] += v[j] * frac * 0.5 * (t + h[j])
            for j in range(i + 1, min(T, i + H + 1 + 24 * 60)):
                if mn[j] - mn[i] >= H + 1 and not np.isnan(o[j]):
                    mx_i[e, k] = j
                    break
        for j in range(i + 1, min(T, i + 24 * 60)):
            if not np.isnan(xo[j]):
                hx_i[e] = j
                break
        for j in range(i + 1, min(T, i + 24 * 60)):
            if not np.isnan(qo[j]):
                hq_i[e] = j
                break
    return thru, nb, tp_i, tp_vol, mx_i, hx_i, hq_i


def pair_events(pair, r, U, store, mode):
    live_days = sorted(set(U[U.pair == pair].day))
    allow = set().union(*[set(x) for x in (DEV if mode == "dev" else HOLD)])
    live_days = [d for d in live_days if d in allow]
    if not live_days:
        return None, None, None
    days = set()
    for d in live_days:
        days.update(pd.date_range(d - pd.Timedelta(days=WARM), d + pd.Timedelta(days=AFTER)))
    if mode == "dev":
        days = {d for d in days if d < HOLD0}
    days = sorted(days)
    P = store.get(pair, days)
    X = leg_frame(store, r.base_usd, days)
    Q = leg_frame(store, r.quote_usd, days)
    if P is None or len(P) == 0 or X is None or Q is None:
        return None, None, dict(pair=pair, note="missing data", days=len(days))
    idx = pd.DatetimeIndex(np.concatenate([pd.date_range(a, b, freq="min", inclusive="left").to_numpy()
                                           for a, b in day_ranges(days)]))
    tick = float(r.quote_increment)
    p, x, q = P.reindex(idx), X.reindex(idx), Q.reindex(idx)
    valid = p.close.notna() & x.close.notna() & q.close.notna()
    c = (np.log(p.close) - np.log(x.close) + np.log(q.close))[valid]
    med = c.rolling("24h", min_periods=MIN_MED).median().reindex(idx).ffill(limit=STALE).shift(1)
    sd = c.rolling("3D", min_periods=MIN_SIG).std().reindex(idx).ffill(limit=STALE).shift(1)
    lx = np.log(x.close.ffill(limit=FFILL)).shift(1)
    lq = np.log(q.close.ffill(limit=FFILL)).shift(1)
    logF = (lx - lq + med).to_numpy()
    sig = sd.to_numpy()
    o, h, l, cl, v = (p[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "volume"))
    v = np.nan_to_num(v)
    mn = (idx.as_unit("s").asi8 // 60).astype(np.int64)
    day = idx.floor("D")
    live = day.isin(live_days)
    if mode == "dev":
        live &= idx < HOLD0
    else:
        live &= (idx >= HOLD0) & (idx < END + pd.Timedelta(days=1))
    z15 = btc_z15(idx)
    qprev = np.exp(lq.to_numpy())
    xprev = np.exp(lx.to_numpy())
    rows = []
    for k in KS:
        lvl = np.floor(np.exp(logF - k * sig) / tick + 1e-9) * tick
        F = np.exp(logF)
        ok = live & np.isfinite(lvl) & (lvl > 0) & np.isfinite(o) & (o >= lvl + 0.5 * tick) & (l <= lvl - 0.5 * tick)
        ev = np.flatnonzero(ok)
        if len(ev) == 0:
            continue
        tp = np.ceil((lvl[ev] + TP_FRAC * (F[ev] - lvl[ev])) / tick - 1e-9) * tick
        thru, nb, tp_i, tp_vol, mx_i, hx_i, hq_i = outcomes(mn, o, h, l, v, lvl, tp, x.open.to_numpy(np.float64),
                                                        q.open.to_numpy(np.float64), q.close.to_numpy(np.float64),
                                                        ev, tick, SCAN, np.array(HS, np.int64))
        E = pd.DataFrame({"pair": pair, "k": k, "ts": idx[ev], "lvl": lvl[ev], "F": F[ev], "sig": sig[ev],
                          "tick": tick, "open": o[ev], "low": l[ev], "close": cl[ev], "vol": v[ev], "tp": tp,
                          "thru_q": thru, "n_below": nb, "q_prev": qprev[ev], "x_prev": xprev[ev], "btc_z15": z15[ev]})
        for j, H in enumerate(HS):
            ti, mi = tp_i[:, j], mx_i[:, j]
            E[f"tp_ts_{H}"] = np.where(ti >= 0, idx[np.maximum(ti, 0)], pd.NaT)
            E[f"tp_vol_q_{H}"] = tp_vol[:, j]
            E[f"mx_ts_{H}"] = np.where(mi >= 0, idx[np.maximum(mi, 0)], pd.NaT)
            E[f"mx_px_{H}"] = np.where(mi >= 0, o[np.maximum(mi, 0)], np.nan)
            E[f"mx_q_{H}"] = np.where(mi >= 0, q.open.to_numpy()[np.maximum(mi, 0)], np.nan)
            E[f"q_at_tp_{H}"] = np.where(ti >= 0, q.close.ffill(limit=FFILL).to_numpy()[np.maximum(ti, 0)], np.nan)
        E["hx_ts"] = np.where(hx_i >= 0, idx[np.maximum(hx_i, 0)], pd.NaT)
        E["hx_px"] = np.where(hx_i >= 0, x.open.to_numpy()[np.maximum(hx_i, 0)], np.nan)
        E["hq_ts"] = np.where(hq_i >= 0, idx[np.maximum(hq_i, 0)], pd.NaT)
        E["hq_px"] = np.where(hq_i >= 0, q.open.to_numpy()[np.maximum(hq_i, 0)], np.nan)
        rows.append(E)
    Ev = pd.concat(rows, ignore_index=True) if rows else None
    m = live & np.isfinite(l) & np.isfinite(logF) & np.isfinite(sig) & (sig > 0)
    dev = np.log(l[m]) - logF[m]
    Dg = pd.DataFrame({"day": day[m], "dev": dev, "z": dev / sig[m], "ts": idx[m],
                       "usd": v[m] * cl[m] * qprev[m]})
    g = Dg.groupby("day")
    D = pd.DataFrame({"min_dev": g.dev.min(), "min_z": g.z.min(), "usd": g.usd.sum(),
                      "ts_min": Dg.loc[g.dev.idxmin(), "ts"].to_numpy()})
    D["pair"] = pair
    jm = valid & pd.Series(live, index=idx)
    stats = dict(pair=pair, days=len(live_days), minutes_pair=int(p.close.notna()[live].sum()),
                 minutes_joint=int(jm.sum()), sig_med_bp=float(np.nanmedian(sig[live]) * 1e4) if live.any() else None,
                 n_ev_k3=int((Ev.k == 3).sum()) if Ev is not None else 0)
    return Ev, D.reset_index(), stats


def main(mode, shard, nsh, qset=None):
    U = pd.read_parquet(os.path.join(DATA, "universe.parquet"))
    if qset:
        U = U[U.qset == qset]
    PR = pd.read_csv(os.path.join(ROOT, "reports", "hunt", "h10xq", "pairs.csv")).set_index("id")
    wt = U.groupby("pair").size().sort_values(ascending=False)
    base = U.groupby("pair").base.first()
    wb = wt.groupby(base).sum().sort_values(ascending=False)
    load, assign_b = [0] * nsh, {}
    for b, w in wb.items():
        i = min(range(nsh), key=lambda j: load[j])
        assign_b[b] = i
        load[i] += w
    mine = [p for p in wt.index if assign_b[base[p]] == shard]
    print(f"{mode} shard {shard}/{nsh}: {len(mine)} pairs, {load[shard]} pair-days: {mine}", flush=True)
    store, t0 = Store(Candles(rate=8.0)), time.time()
    out = os.path.join(DATA, "ev")
    os.makedirs(out, exist_ok=True)
    evs, dgs, sts = [], [], []
    for pair in mine:
        try:
            Ev, D, st = pair_events(pair, PR.loc[pair], U, store, mode)
        except Exception as err:  # noqa: BLE001
            print(pair, "FAILED", type(err).__name__, err, flush=True)
            sts.append(dict(pair=pair, note=f"failed {type(err).__name__}"))
            continue
        if Ev is not None:
            evs.append(Ev)
        if D is not None:
            dgs.append(D)
        if st:
            sts.append(st)
        print(pair, st, f"req {store.C.n_req} err {store.C.n_err} {time.time() - t0:.0f}s", flush=True)
    if evs:
        A = pd.concat(evs, ignore_index=True)
        for j, s0 in enumerate(range(0, len(A), 300_000)):
            A.iloc[s0:s0 + 300_000].to_parquet(os.path.join(out, f"{mode}_ev_{shard}_{j}.parquet"), index=False,
                                                compression="zstd")
    if dgs:
        pd.concat(dgs, ignore_index=True).to_parquet(os.path.join(out, f"{mode}_diag_{shard}.parquet"), index=False,
                                                     compression="zstd")
    pd.DataFrame(sts).to_csv(os.path.join(out, f"{mode}_pairs_{shard}.csv"), index=False)
    print("done", store.C.n_req, "requests", store.C.n_err, "errors", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else None)
