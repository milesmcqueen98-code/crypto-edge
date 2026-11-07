#!/usr/bin/env python3
"""H6 (VD): Coinbase-specific dislocation bids against an outside fair value.

Fixed spec: reports/hunt/h6vd/SPEC.md; rules: reports/hunt_prereg.md and reports/hunt/BUILDER_GUIDE.md.

  python scripts/hunt/h6vd/vd.py dev           DEV grid on data before 2026-06-01 (12 core + 1 quiet + 2 AI); Actions
  python scripts/hunt/h6vd/vd.py log           log the DEV trials in the shared ledger (LOCAL, file-locked; once)
  python scripts/hunt/h6vd/vd.py select        selection rule -> frozen.json (LOCAL; commit + push = the freeze)
  python scripts/hunt/h6vd/vd.py final         the frozen variant (frozen.json) over every scored day; Actions
  python scripts/hunt/h6vd/vd.py prints I N    trade-print check of a 25% sample of the frozen fills (shard I of N)
  python scripts/hunt/h6vd/vd.py gates         gates.path_b on daily.parquet (LOCAL: needs the shared ledger)

Bid (coin c, minute t, information through t-1):
  g = log(Coinbase close / reference close) on minutes where both traded
  gbar_t = trailing 24-hour median of g through t-1; e = g - gbar; sig_t = trailing 3-day std of e through t-1
  the reference must have traded in t-1 (freshness guard)
  bid L_t = ref_close(t-1) * exp(gbar_t - k * sig_t), floored to the spot tick
Fill: minute t opened above L_t and traded at least one tick below it (Coinbase candles). Size
  min($5K, theta * through-volume); through-volume = USD volume below L from t while each minute trades below L
  (at most 15 more minutes), each candle's volume spread evenly over its range (as scripts/wick1m/sim.py).
Take-profit: post-only at 60% of the way back to the fair value F = ref_close(t-1) * exp(gbar_t), ceiled to the tick;
  fills in minutes t+1 .. t+H that trade a tick above it; capacity theta * USD volume above it from the first touch.
Time exit: market at the open of the first traded minute >= t+H+1 (taker fee + half-spread, common.spot_cost_bp).
Book: one position per coin, at most 6 open. Coinbase holds cash for every resting bid at full size ($5K), so at
  most 6 - open coins can carry a bid in a minute; cash <= capital then holds for $30K and $50K. The SPEC does not say
  which coins get the bids: they go to the eligible coins with the most negative gap z at t-1
  (z = (last g within 5 minutes - gbar_t) / sig_t), an engineering choice fixed before any result.
Spot ticks: inferred per coin and month from Coinbase's own prices (largest power of ten holding >= 99% of
  open/high/low/close), because Coinbase changed some ticks (APT, SEI in 2025Q4).
"""
import json
import os
import subprocess
import sys
import time

import numba
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
sys.path.insert(0, ROOT)
import common  # noqa: E402
import gates  # noqa: E402

IDEA = "h6vd"
OUT = os.path.join(ROOT, "reports", "hunt", "h6vd")
SMOKE = os.environ.get("H6_SMOKE") == "1"            # mechanics test: writes elsewhere, prints no performance
DEV_OUT = os.environ.get("H6_DEV_OUT") if SMOKE else os.path.join(OUT, "dev")
START = pd.Timestamp(os.environ.get("H6_START", "2024-01-01"))
DEV_LAST = pd.Timestamp("2026-05-31")                 # dev runs load data through this day only
FULL_END = pd.Timestamp("2026-11-06")                 # exclusive
SCORE0 = {"bitstamp": pd.Timestamp("2025-01-01"),     # scored days start (2024 = warm-up and AI training only)
          "perp": pd.Timestamp("2025-07-19")}         # first full day after the first alt perp launch (ETH)
ORDER_USD, MAX_OPEN, TP_SHARE, SCAN_MIN = 5000.0, 6, 0.6, 15
MIN_MED, MIN_SD = 30, 100                             # observations in the 24h median / 3-day std windows
KS, HS, REFS = (3.0, 4.0, 6.0), (30, 60), ("bitstamp", "perp")
TICKS = 10.0 ** np.arange(-10, 1)
MIN_TRADES = 40
AI_FEATS = ["zgap", "depth_bp", "z_res15", "z_res60", "btc_z5", "btc_z15", "btc_z60", "vol_cb15", "vol_ref15",
            "hour_utc", "weekend", "coin_id"]


def inc_trades():
    """Incumbent parent fills (ts, coin): the worktree's copy, else the main clone's (sparse worktrees)."""
    for base in (ROOT, "/home/claude/crypto-edge"):
        p = os.path.join(base, "reports", "wick1m", "trades_main.parquet")
        if os.path.exists(p):
            return pd.read_parquet(p, columns=["ts", "coin"])
    raise FileNotFoundError("reports/wick1m/trades_main.parquet")


def cost(mult):
    """(maker, taker incl. half-spread) per side as fractions (common.spot_cost_bp)."""
    return common.spot_cost_bp(False, mult) / 1e4, common.spot_cost_bp(True, mult) / 1e4


def shift(x, n):
    x = np.asarray(x, np.float64)
    out = np.full(len(x), np.nan)
    if n > 0:
        out[n:] = x[:-n]
    elif n < 0:
        out[:n] = x[-n:]
    else:
        out[:] = x
    return out


def rstd(x, w=4320, minp=1440):
    return pd.Series(x).rolling(w, min_periods=minp).std().to_numpy()


def rbeta(ri, rb, w=4320, minp=1440):
    a, b = pd.Series(ri), pd.Series(rb)
    m = lambda s: s.rolling(w, min_periods=minp).mean()  # noqa: E731
    cov = m(a * b) - m(a) * m(b)
    return (cov / b.rolling(w, min_periods=minp).var()).clip(0.0, 3.0).to_numpy()


def universe(ref):
    cb = {f[:-8] for f in os.listdir(os.path.join(common.DATA, "minute")) if f.endswith(".parquet")}
    bs = {f[:-8] for f in os.listdir(os.path.join(common.DATA, "bitstamp")) if f.endswith(".parquet")}
    u = sorted((cb & bs) - {"BTC"})
    if ref == "perp":
        u = [c for c in u if os.path.exists(os.path.join(common.DATA, "cfm", f"{c}.parquet"))]
    only = os.environ.get("H6_COINS")
    return [c for c in u if c in only.split(",")] if only else u


def all_coins():
    return universe("bitstamp")


def infer_ticks(d, idx):
    mc = (d.index.year * 12 + d.index.month).to_numpy()
    px = d[["open", "high", "low", "close"]].to_numpy(np.float64)
    out = {}
    for m in np.unique(mc):
        p = px[mc == m].ravel()
        best = TICKS[0]
        for t in TICKS:
            q = p / t
            if np.mean(np.abs(q - np.round(q)) < 0.05) >= 0.99:
                best = t
        out[int(m)] = float(best)
    mi = pd.Series((idx.year * 12 + idx.month).to_numpy())
    return mi.map(out).ffill().bfill().to_numpy(np.float64), out


# ------------------------------------------------------------------------------------------------ levels
class Lev:
    """Gap, fair value, sigma, eligibility and ranking key of one coin against one reference on the minute grid."""

    def __init__(self, c, ref, idx, end):
        self.c, self.ref, self.ok = c, ref, False
        cb = common.load_minute(c, "minute", START, end)
        if ref == "bitstamp":
            r = common.load_minute(c, "bitstamp", START, end)
        else:
            r = common.load_perp(c)
            if r is not None:
                r = r[(r.index >= START) & (r.index < end)]
        if cb is None or r is None or len(cb) < 5000 or len(r) < 2000:
            return
        self.ok = True
        self.tick, self.tick_map = infer_ticks(cb, idx)
        g_ = cb.reindex(idx)
        rnd = lambda x: np.round(x / self.tick) * self.tick  # noqa: E731
        self.O, self.Hh = rnd(g_.open.to_numpy(np.float64)), rnd(g_.high.to_numpy(np.float64))
        self.Lo, self.Cl = rnd(g_.low.to_numpy(np.float64)), rnd(g_.close.to_numpy(np.float64))
        self.V = g_.volume.fillna(0.0).to_numpy(np.float64)
        rg = r.reindex(idx)
        self.rc = rg.close.to_numpy(np.float64)
        self.rv = rg.volume.fillna(0.0).to_numpy(np.float64)
        del cb, r, g_, rg
        with np.errstate(invalid="ignore", divide="ignore"):
            g = np.log(self.Cl) - np.log(self.rc)                    # NaN unless both venues traded
        gs = pd.Series(g, idx).dropna()
        med = gs.rolling("1440min", min_periods=MIN_MED).median()
        self.gbar = shift(med.reindex(idx).ffill(limit=1440).to_numpy(), 1)
        e = g - self.gbar
        es = pd.Series(e, idx).dropna()
        sd = es.rolling("4320min", min_periods=MIN_SD).std()
        self.sig = shift(sd.reindex(idx).ffill(limit=1440).to_numpy(), 1)
        fresh = shift(np.isfinite(self.rc).astype(np.float64), 1) == 1.0
        with np.errstate(invalid="ignore", divide="ignore"):
            self.lfair = np.log(shift(self.rc, 1)) + self.gbar        # log fair value for minute t
            glast = shift(pd.Series(g).ffill(limit=4).to_numpy(), 1)
            self.z = (glast - self.gbar) / self.sig
        self.elig = fresh & np.isfinite(self.gbar) & np.isfinite(self.sig) & (self.sig > 0) & np.isfinite(self.lfair)
        self.key = np.where(self.elig, np.where(np.isfinite(self.z), self.z, 1e9), np.nan).astype(np.float32)
        self.g = g

    def cands(self, k, idx):
        """Candidate fills of the k-sigma bid (every minute the bid would fill if it rested), with exits."""
        t = self.tick
        with np.errstate(invalid="ignore", over="ignore"):
            L = np.floor(np.exp(self.lfair - k * self.sig) / t + 1e-9) * t
            fill = self.elig & np.isfinite(self.O) & (L > 0) & ((self.O - L) / t >= 0.5) & ((L - self.Lo) / t >= 0.5)
        cand = np.nonzero(fill)[0].astype(np.int64)
        cand = cand[cand >= 20]
        if len(cand) == 0:
            return None
        Lc, tc = L[cand], t[cand]
        F = np.exp(self.lfair[cand])
        TP = np.ceil(np.exp(np.log(Lc) + TP_SHARE * (np.log(F) - np.log(Lc))) / tc - 1e-9) * tc
        TP = np.maximum(TP, Lc + tc)
        thr, thr0, i_tp, tp_usd, i_x, px_x, mae = scan(cand, Lc, TP, self.O, self.Hh, self.Lo, self.V, self.tick,
                                                 np.array(HS, np.int64), SCAN_MIN)
        T = len(idx)
        lc = np.log(pd.Series(self.Cl).ffill().to_numpy())
        lr = np.log(pd.Series(self.rc).ffill().to_numpy())
        at = lambda a, off: a[np.clip(cand + off, 0, T - 1)]  # noqa: E731
        D = pd.DataFrame(dict(coin=self.c, i0=cand, ts=idx[cand], k=k, L=Lc, F=F, TP=TP, tick=tc,
                              sig_bp=self.sig[cand] * 1e4, z=self.z[cand], thr_usd=thr, thr_m0=thr0, V0=self.V[cand],
                              cb_m1=at(lc, -1) - np.log(Lc), cb_m6=at(lc, -6) - np.log(Lc),
                              cb_m16=at(lc, -16) - np.log(Lc), rf_m1=at(lr, -1), rf_m6=at(lr, -6), rf_m16=at(lr, -16)))
        for h, H in enumerate(HS):
            D[f"i_tp{H}"] = i_tp[:, h]
            D[f"tp_usd{H}"] = tp_usd[:, h]
            D[f"i_x{H}"] = i_x[:, h]
            D[f"ret_tp{H}"] = TP / Lc - 1.0
            D[f"ret_x{H}"] = px_x[:, h] / Lc - 1.0
            D[f"mae{H}"] = mae[:, h]
            ix = np.where(i_x[:, h] >= 0, i_x[:, h], np.clip(cand + H + 1, 0, T - 1))
            D[f"rf_x{H}"] = lr[np.maximum(ix - 1, 0)]                # reference (ffilled) just before the exit
        return D


@numba.njit(cache=True)
def scan(cand, L, TP, O, Hh, Lo, V, tick, Hs, scan_min):
    n, nh, T = len(cand), len(Hs), len(O)
    thr = np.zeros(n)
    thr0 = np.zeros(n)
    i_tp = np.full((n, nh), -1, np.int64)
    tp_usd = np.zeros((n, nh))
    i_x = np.full((n, nh), -1, np.int64)
    px_x = np.full((n, nh), np.nan)
    mae = np.zeros((n, nh))
    for a in range(n):
        i0, lv, tp = cand[a], L[a], TP[a]
        tot = 0.0
        for j in range(scan_min + 1):
            i = i0 + j
            if i >= T:
                break
            lo, hi = Lo[i], Hh[i]
            if not (lo == lo) or lo > lv - 0.5 * tick[i]:
                if j == 0:
                    continue
                break
            rng = hi - lo
            frac = 1.0 if rng <= 0 else min(1.0, (lv - lo) / rng)
            tot += V[i] * frac * 0.5 * (lv + lo)
            if j == 0:
                thr0[a] = tot
        thr[a] = tot
        for h in range(nh):
            H = Hs[h]
            first, usd, mn = -1, 0.0, Lo[i0]
            for i in range(i0 + 1, min(i0 + H + 1, T)):
                hi = Hh[i]
                if not (hi == hi):
                    continue
                if first < 0:
                    if Lo[i] < mn:
                        mn = Lo[i]
                    if hi >= tp + 0.5 * tick[i]:
                        first = i
                if first >= 0 and hi > tp:
                    lo = Lo[i]
                    rng = hi - lo
                    frac = 1.0 if rng <= 0 else min(1.0, (hi - tp) / rng)
                    usd += V[i] * frac * 0.5 * (tp + hi)
            i_tp[a, h] = first
            tp_usd[a, h] = usd
            mae[a, h] = mn / lv - 1.0
            for i in range(i0 + H + 1, min(i0 + H + 241, T)):
                if O[i] == O[i]:
                    i_x[a, h] = i
                    px_x[a, h] = O[i]
                    break
    return thr, thr0, i_tp, tp_usd, i_x, px_x, mae


def btc_series(idx, end):
    b = common.load_minute("BTC", "minute", START, end).reindex(idx)
    lb = np.log(b.close.ffill(limit=30).to_numpy(np.float64))
    out = {"lb": lb}
    for L in (5, 15, 60):
        r = lb - shift(lb, L)
        out[f"btc_z{L}"] = shift(r / rstd(r), 1)
    r15 = lb - shift(lb, 15)
    s15 = rstd(r15)
    with np.errstate(invalid="ignore"):
        out["quiet_bad"] = np.nan_to_num(np.abs(shift(r15, 1)) > 2.0 * shift(s15, 1), nan=0.0).astype(bool)
    return out


# ------------------------------------------------------------------------------------------------ the book
def run_book(C, Z, lo, hi, theta, H, quiet=None, allow=None):
    """Sequential book over candidate minutes in [lo, hi). C: candidates of one (ref, k), Z: (T, n_coins) ranking key
    (NaN = no bid possible). allow: optional (U minutes, bool[T_U, n_coins]) AI permission. Returns the fills."""
    sub = C[(C.i0 >= lo) & (C.i0 < hi)].sort_values(["i0", "coin_id"])
    i0 = sub.i0.to_numpy()
    coin = sub.coin_id.to_numpy()
    thr = sub.thr_usd.to_numpy()
    itp, tpu, ix = sub[f"i_tp{H}"].to_numpy(), sub[f"tp_usd{H}"].to_numpy(), sub[f"i_x{H}"].to_numpy()
    busy = np.full(Z.shape[1], -1, np.int64)
    keep, sizes, tpss, ends, nslot, nelig = [], [], [], [], [], []
    if len(i0) == 0:
        return sub.iloc[:0].assign(size=[], tp_size=[], end=[])
    starts = np.r_[0, np.nonzero(np.diff(i0))[0] + 1]
    stops = np.r_[starts[1:], len(i0)]
    n_noslot = 0
    for s, e in zip(starts, stops):
        t = i0[s]
        if quiet is not None and quiet[t]:
            continue
        free = busy < t
        slots = MAX_OPEN - int((~free).sum())
        if slots <= 0:
            n_noslot += e - s
            continue
        z = Z[t]
        ok = free & ~np.isnan(z)
        if allow is not None:
            U, A = allow
            p = np.searchsorted(U, t)
            ok &= A[p] if (p < len(U) and U[p] == t) else False
        ids = np.nonzero(ok)[0]
        if len(ids) > slots:
            ids = ids[np.argsort(z[ids], kind="stable")[:slots]]
        bid = set(ids.tolist())
        for r in range(s, e):
            c = coin[r]
            if c not in bid:
                if busy[c] < t and (allow is None or ok[c]):
                    n_noslot += 1
                continue
            size = min(ORDER_USD, theta * thr[r])
            if size <= 1.0:
                continue
            tps = min(size, theta * tpu[r]) if itp[r] >= 0 else 0.0
            rem = size - tps
            if rem > 1e-9 and ix[r] < 0:
                continue                                         # no exit candle (end of data)
            end = ix[r] if rem > 1e-9 else itp[r]
            busy[c] = end                                        # free again from the minute after the exit
            keep.append(r)
            sizes.append(size)
            tpss.append(tps)
            ends.append(end)
            nslot.append(slots)
            nelig.append(int(ok.sum()))
    F = sub.iloc[keep].copy()
    F["size"], F["tp_size"], F["end"] = sizes, tpss, ends
    F["slots"], F["n_elig"] = nslot, nelig
    F.attrs["n_noslot"] = n_noslot
    return F


def pnl(F, H, mult):
    cm, ct = cost(mult)
    rem = F["size"] - F["tp_size"]
    return F["tp_size"] * (F[f"ret_tp{H}"] - cm) + rem * (F[f"ret_x{H}"] - ct) - F["size"] * cm


def daily(F, H, mult, capital, idx, days):
    if len(F) == 0:
        return pd.Series(0.0, index=days)
    p = pnl(F, H, mult).to_numpy()
    d = pd.Series(p, index=idx[F["end"].to_numpy()].floor("D")).groupby(level=0).sum()
    return d.reindex(days, fill_value=0.0) / capital


# ------------------------------------------------------------------------------------------------ diagnostics
def venue_led(F, H):
    """Who opened the gap in the 5 minutes before the fill: Coinbase falling to the bid, or the reference rising."""
    d_cb = -F["cb_m6"]                                            # log(L) - log(CB close at t-6)
    d_rf = F["rf_m1"] - F["rf_m6"]
    down, up = np.maximum(0.0, -d_cb), np.maximum(0.0, d_rf)
    tot = down + up
    share = np.where(tot > 0, down / tot.where(tot > 0, 1.0), 0.5)
    cl_cb = np.log1p(F[f"ret_x{H}"].fillna(0.0))                  # Coinbase from the bid to the time exit
    cl_rf = F[f"rf_x{H}"] - F["rf_m1"]                            # reference over the same hold
    return pd.DataFrame(dict(cb_share_open=share, cb_led=share > 0.5, cb_after_bp=cl_cb * 1e4,
                             ref_after_bp=cl_rf * 1e4), index=F.index)


def overlap(F, inc):
    """Share of fills in the same coin and minute (or within 5 minutes) as an incumbent parent fill."""
    if len(F) == 0:
        return dict(same_minute=np.nan, within5=np.nan)
    s = {(c, t) for c, t in zip(inc.coin, inc.ts)}
    same = np.array([(c, t) in s for c, t in zip(F.coin, F.ts)])
    near = np.zeros(len(F), bool)
    for j, (c, t) in enumerate(zip(F.coin, F.ts)):
        for dm in range(-5, 6):
            if (c, t + pd.Timedelta(minutes=dm)) in s:
                near[j] = True
                break
    return dict(same_minute=float(same.mean()), within5=float(near.mean()), n=int(len(F)))


def trade_stats(F, H):
    if len(F) == 0:
        return dict(trades=0)
    w = F["size"]
    out = dict(trades=int(len(F)), fill_musd=float(w.sum() / 1e6), avg_size=float(w.mean()),
               tp_share=float((F["tp_size"] / w).mean()), full_size_share=float((w >= ORDER_USD - 1).mean()))
    for m in (1.0, 2.0):
        out[f"net_bp_{int(m)}x"] = float(pnl(F, H, m).sum() / w.sum() * 1e4)
    out["gross_bp"] = float(pnl(F, H, 0.0).sum() / w.sum() * 1e4)
    out["sig_bp_med"] = float(F.sig_bp.median())
    out["depth_bp_med"] = float((np.log(F.F / F.L) * 1e4).median())
    return out


# ------------------------------------------------------------------------------------------------ AI filter
def ai_frame(levs_fn, coins, idx, end, btc, k, U, cand_keys):
    """Features (t-1) for every eligible coin at the minutes U; rows that are candidate fills carry their key."""
    rows = []
    for ci, c in enumerate(coins):
        lv = levs_fn(c)
        if not lv.ok:
            continue
        el = lv.elig[U]
        u = U[el]
        if len(u) == 0:
            continue
        lc = np.log(pd.Series(lv.Cl).ffill(limit=30).to_numpy())
        lb = btc["lb"]
        beta = rbeta(np.diff(lc, prepend=np.nan), np.diff(lb, prepend=np.nan))
        f = {}
        for L in (15, 60):
            res = (lc - shift(lc, L)) - beta * (lb - shift(lb, L))
            f[f"z_res{L}"] = shift(res / rstd(res), 1)[u]
        for nm, v in (("vol_cb15", lv.V), ("vol_ref15", lv.rv)):
            v15 = pd.Series(v).rolling(15, min_periods=1).sum()
            avg = v15.rolling(4320, min_periods=1440).mean()
            f[nm] = shift((v15 / avg.where(avg > 0)).to_numpy(), 1)[u]
        D = pd.DataFrame(f)
        D["zgap"] = lv.z[u]
        D["depth_bp"] = k * lv.sig[u] * 1e4
        for L in (5, 15, 60):
            D[f"btc_z{L}"] = btc[f"btc_z{L}"][u]
        ts = idx[u]
        D["hour_utc"] = ts.hour
        D["weekend"] = (ts.dayofweek >= 5).astype(int)
        D["coin_id"] = ci
        D["t"] = u
        D["ts"] = ts
        rows.append(D.astype({x: np.float32 for x in AI_FEATS if x not in ("coin_id", "hour_utc", "weekend")}))
        del lv
    X = pd.concat(rows, ignore_index=True)
    key = pd.Series(np.arange(len(cand_keys)), index=pd.MultiIndex.from_tuples(cand_keys))
    X["cand_row"] = key.reindex(pd.MultiIndex.from_arrays([X.t.to_numpy(), X.coin_id.to_numpy()])).to_numpy()
    return X


def ai_labels(C, H, theta=0.5, mult=2.0):
    """Single-trade net bp at 2x costs at the sleeve's sizing (no book constraint)."""
    size = np.minimum(ORDER_USD, theta * C.thr_usd)
    tps = np.where(C[f"i_tp{H}"] >= 0, np.minimum(size, theta * C[f"tp_usd{H}"]), 0.0)
    F = C.assign(size=size, tp_size=tps)
    y = pnl(F, H, mult) / size * 1e4
    y[(size - tps > 1e-9) & (C[f"i_x{H}"] < 0)] = np.nan
    return y.to_numpy()


def ai_walk_forward(X, y_c, q_last):
    """LightGBM (edge.wick.PARAMS, 3 seeds), trained on candidate rows before each test quarter (expanding window,
    1-day embargo), from 2025Q2. Returns predictions and the in-sample median threshold per row (NaN = no model)."""
    import lightgbm as lgb
    from edge import wick
    pred = np.full(len(X), np.nan)
    thr50 = np.full(len(X), np.nan)
    has = X.cand_row.notna().to_numpy()
    y = np.full(len(X), np.nan)
    y[has] = y_c[X.cand_row[has].astype(int).to_numpy()]
    feats = AI_FEATS
    t_first = X.ts[has].min() if has.any() else pd.Timestamp("2100-01-01")
    for per in pd.period_range("2025Q2", q_last, freq="Q"):
        tr = has & np.isfinite(y) & (X.ts < per.start_time - pd.Timedelta(days=1)).to_numpy()
        te = ((X.ts >= per.start_time) & (X.ts <= per.end_time)).to_numpy()
        if tr.sum() < 200 or not te.any() or t_first > per.start_time - pd.Timedelta(days=182):
            continue
        T_ = X.loc[tr]
        ep = T_.groupby("coin_id").t.transform(lambda s: np.cumsum(np.r_[1, np.diff(s.to_numpy()) > 1]))
        w = 1.0 / T_.assign(ep=ep).groupby(["coin_id", "ep"]).t.transform("size").to_numpy()
        pt, pi = [], []
        for s in (7, 11, 23):
            m = lgb.train(wick.PARAMS | {"seed": s}, lgb.Dataset(T_[feats], y[tr], weight=w, categorical_feature=["coin_id"]),
                          num_boost_round=wick.ROUNDS)
            pt.append(m.predict(X.loc[te, feats]))
            pi.append(m.predict(T_[feats]))
        pred[te] = np.mean(pt, axis=0)
        thr50[te] = float(np.median(np.mean(pi, axis=0)))
        print(f"    AI {per}: train {int(tr.sum())} test rows {int(te.sum())}", flush=True)
    return pred, thr50


# ------------------------------------------------------------------------------------------------ runs
class Run:
    def __init__(self, end):
        self.end = end
        self.idx = pd.date_range(START, end, freq="min", inclusive="left")
        self.coins = all_coins()
        self.cid = {c: i for i, c in enumerate(self.coins)}
        self.btc = btc_series(self.idx, end)
        self.C, self.Z, self.ticks = {}, {}, {}

    def lev(self, c, ref):
        return Lev(c, ref, self.idx, self.end)

    def build(self, ref, ks):
        T, n = len(self.idx), len(self.coins)
        Z = np.full((T, n), np.nan, np.float32)
        parts = {k: [] for k in ks}
        for c in universe(ref):
            t0 = time.time()
            lv = self.lev(c, ref)
            if not lv.ok:
                print(f"  {ref} {c}: no data", flush=True)
                continue
            Z[:, self.cid[c]] = lv.key
            self.ticks[(ref, c)] = lv.tick_map
            for k in ks:
                D = lv.cands(k, self.idx)
                if D is not None:
                    D["coin_id"] = self.cid[c]
                    parts[k].append(D)
            print(f"  {ref} {c}: elig {lv.elig.mean():.2f}, cands {[len(p[-1]) if p and p[-1].coin.iloc[0] == c else 0 for p in parts.values()]}, "
                  f"{time.time() - t0:.1f}s", flush=True)
            del lv
        self.Z[ref] = Z
        for k in ks:
            self.C[(ref, k)] = pd.concat(parts[k], ignore_index=True) if parts[k] else None

    def days(self, ref, last):
        return pd.date_range(SCORE0[ref], last, freq="D")

    def book(self, v, theta=0.5, allow=None, last=None):
        C = self.C.get((v["ref"], v["k"]))
        if C is None or len(C) == 0:
            F = pd.DataFrame(columns=["coin", "i0", "ts", "size", "tp_size", "end"])
            F.attrs["n_noslot"] = 0
            return F
        lo = int(self.idx.get_indexer([SCORE0[v["ref"]]])[0])
        return run_book(C, self.Z[v["ref"]], lo, len(self.idx), theta, v["H"],
                        quiet=self.btc["quiet_bad"] if v.get("quiet") else None, allow=allow)

    def ai_allow(self, v, q_last):
        """Permission matrix at the candidate minutes of variant v (AI threshold mode v['ai'])."""
        C = self.C[(v["ref"], v["k"])]
        U = np.unique(C.i0.to_numpy())
        keys = list(zip(C.i0.to_numpy(), C.coin_id.to_numpy()))
        X = ai_frame(lambda c: self.lev(c, v["ref"]), self.coins, self.idx, self.end, self.btc, v["k"], U, keys)
        y = ai_labels(C, v["H"])
        pred, thr50 = ai_walk_forward(X, y, q_last)
        out = {}
        for mode in ("pos", "q50"):
            okr = np.ones(len(X), bool)
            m = np.isfinite(pred)
            okr[m] = pred[m] > 0.0 if mode == "pos" else pred[m] >= thr50[m]
            A = np.zeros((len(U), len(self.coins)), bool)
            A[np.searchsorted(U, X.t.to_numpy()), X.coin_id.to_numpy()] = okr
            out[mode] = (U, A)
        P = X[["t", "coin_id", "ts"]].assign(pred=pred, thr50=thr50, cand_row=X.cand_row)
        return out, P


def complexity(v):
    """Ties go to the simpler variant: no AI, no quiet filter, the Bitstamp reference, H = 60."""
    return (bool(v.get("ai")), bool(v.get("quiet")), v["ref"] != "bitstamp", v["H"] != 60)


def pick(pairs):
    """Selection rule (pre-registration): highest DEV alpha t (sleeve 2x on the incumbent at $70K) among variants
    with at least MIN_TRADES trades; ties to the simpler variant. pairs: [(variant dict, stats dict)]."""
    ok = [(v, s) for v, s in pairs if s.get("trades", 0) >= MIN_TRADES and np.isfinite(s["t_alpha70"])]
    if not ok:
        ok = [(v, s) for v, s in pairs if np.isfinite(s["t_alpha70"])]
    return min(ok, key=lambda vs: (-round(vs[1]["t_alpha70"], 6), complexity(vs[0])))[0]


def vname(v):
    s = f"{v['ref'][:2]}_k{int(v['k'])}_H{v['H']}"
    if v.get("quiet"):
        s += "_quiet"
    if v.get("ai"):
        s += f"_ai{v['ai']}"
    return s


def evaluate(R, v, F, last, inc_tr):
    days = R.days(v["ref"], last)
    s2 = daily(F, v["H"], 2.0, 30e3, R.idx, days)
    s1 = daily(F, v["H"], 1.0, 30e3, R.idx, days)
    gates.assert_dev_only(s2)
    ri70 = gates.incumbent(70e3, 0.5, "instant", days)
    at = gates.alpha_test(s2, ri70)
    scr = gates.dev_screen(s2)
    st = dict(variant=vname(v), **{k_: v.get(k_) for k_ in ("ref", "k", "H", "quiet", "ai")}, n_days=len(days),
              t_alpha70=at["t_alpha"], alpha70_yr=at["alpha_yr"], **{f"scr_{a}": b for a, b in scr.items()},
              sleeve_sharpe_1x=gates.sharpe(s1), ret_yr_2x=float(s2.sum() / len(days) * 365),
              ret_yr_1x=float(s1.sum() / len(days) * 365), n_noslot=F.attrs.get("n_noslot", 0), **trade_stats(F, v["H"]))
    if len(F):
        vl = venue_led(F, v["H"])
        st["cb_led_share"] = float(vl.cb_led.mean())
        p2 = pnl(F, v["H"], 2.0)
        st["net_bp_2x_cbled"] = float(p2[vl.cb_led].sum() / F["size"][vl.cb_led].sum() * 1e4) if vl.cb_led.any() else np.nan
        st["net_bp_2x_refled"] = float(p2[~vl.cb_led].sum() / F["size"][~vl.cb_led].sum() * 1e4) if (~vl.cb_led).any() else np.nan
        st.update({f"overlap_{a}": b for a, b in overlap(F, inc_tr).items()})
        d = s2 * 30e3
        top = d.sort_values(ascending=False)
        st["top3_share_2x"] = float(top.head(3).sum() / d.sum()) if d.sum() != 0 else np.nan
    return st, s2, s1


def dev():
    end = DEV_LAST + pd.Timedelta(days=1)
    if os.environ.get("H6_END"):                                  # smoke tests only: can only shorten DEV
        end = min(end, pd.Timestamp(os.environ["H6_END"]))
    assert end <= gates.HOLD0
    last = end - pd.Timedelta(days=1)
    os.makedirs(DEV_OUT, exist_ok=True)
    R = Run(end)
    inc_tr = inc_trades()
    inc_tr = inc_tr[inc_tr.ts < gates.HOLD0]
    for ref in REFS:
        R.build(ref, KS)
    stats, cols, fills = [], {}, []

    def do(v, allow=None):
        F = R.book(v, allow=allow)
        st, s2, s1 = evaluate(R, v, F, last, inc_tr)
        stats.append(st)
        cols[(st["variant"], "s30_2x")] = s2
        cols[(st["variant"], "s30_1x")] = s1
        if len(F):
            fills.append(F.assign(variant=st["variant"], pnl2=pnl(F, v["H"], 2.0), pnl1=pnl(F, v["H"], 1.0)))
        if SMOKE:
            print(f"  {st['variant']}: trades {st.get('trades')}, fill $M {st.get('fill_musd', 0):.3f}, "
                  f"cb-led {st.get('cb_led_share', float('nan')):.2f}, overlap5 {st.get('overlap_within5', float('nan')):.2f}",
                  flush=True)
        else:
            print(f"  {st['variant']}: trades {st.get('trades')}, t70 {st['t_alpha70']:.2f}", flush=True)
        return st

    core = []
    for ref in REFS:
        for k in KS:
            for H in HS:
                v = dict(ref=ref, k=k, H=H)
                core.append((v, do(v)))
    best = pick(core)
    vq = dict(best, quiet=True)
    sq = do(vq)
    sb = [s for v, s in core if v == best][0]
    base = vq if (sq.get("trades", 0) >= MIN_TRADES and sq["t_alpha70"] > sb["t_alpha70"]) else best
    allows, P = R.ai_allow(base, "2026Q2")
    P[(P.ts < gates.HOLD0) & P.cand_row.notna()].to_parquet(os.path.join(DEV_OUT, "ai_pred_dev.parquet"))
    for mode in ("pos", "q50"):
        do(dict(base, ai=mode), allow=allows[mode])
    S = pd.DataFrame(stats)
    S.to_csv(os.path.join(DEV_OUT, "summary_dev.csv"), index=False)
    D = pd.DataFrame({f"{a}|{b}": s for (a, b), s in cols.items()})
    D.index.name = "day"
    D.to_parquet(os.path.join(DEV_OUT, "daily_dev.parquet"))
    if fills:
        Fa = pd.concat(fills, ignore_index=True)
        keep = ["variant", "coin", "ts", "k", "L", "F", "TP", "sig_bp", "z", "thr_usd", "thr_m0", "size", "tp_size",
                "pnl2", "pnl1", "slots", "n_elig"]
        Fa[keep].to_parquet(os.path.join(DEV_OUT, "fills_dev.parquet"))
    # net bp by k over every candidate (no book), DEV scored days, H = 60 and 30, 2x costs
    rows = []
    for (ref, k), C in R.C.items():
        if C is None:
            continue
        C = C[C.ts >= SCORE0[ref]]
        for H in HS:
            y = ai_labels(C, H)
            rows.append(dict(ref=ref, k=k, H=H, cands=int(len(C)), cand_net_bp_2x_mean=float(np.nanmean(y)),
                             cand_net_bp_2x_med=float(np.nanmedian(y))))
    pd.DataFrame(rows).to_csv(os.path.join(DEV_OUT, "cands_by_k_dev.csv"), index=False)
    tk = {f"{r}|{c}": {str(m): t for m, t in v.items()} for (r, c), v in R.ticks.items() if r == "bitstamp"}
    json.dump(dict(best_core=vname(best), quiet=vname(vq), ai_base=vname(base), ticks=tk),
              open(os.path.join(DEV_OUT, "selection_dev.json"), "w"), indent=1, default=str)
    pd.set_option("display.width", 250)
    if SMOKE:
        print(S[["variant", "trades", "fill_musd", "tp_share", "full_size_share", "n_noslot"]].round(3).to_string(index=False))
        return
    print(S[["variant", "trades", "t_alpha70", "scr_sleeve_sharpe", "net_bp_2x", "net_bp_1x", "gross_bp",
             "tp_share", "cb_led_share"]].round(3).to_string(index=False))


def log_trials():
    """LOCAL: append every DEV configuration to the shared ledger (once)."""
    mark = os.path.join(DEV_OUT, "logged.json")
    if os.path.exists(mark):
        print("already logged:", open(mark).read())
        return
    S = pd.read_csv(os.path.join(DEV_OUT, "summary_dev.csv"))
    D = pd.read_parquet(os.path.join(DEV_OUT, "daily_dev.parquet"))
    done = []
    for r in S.itertuples():
        s2 = D[f"{r.variant}|s30_2x"].dropna()
        gates.assert_dev_only(s2)
        bk = gates.dev_book(s2)
        gates.log_trial(IDEA, r.variant, bk, note="DEV book a=0.7, sleeve $30K at 2x (vd.py dev)",
                        trades=int(r.trades) if np.isfinite(r.trades) else 0, t_alpha70=round(float(r.t_alpha70), 4),
                        sleeve_sharpe=round(float(r.scr_sleeve_sharpe), 4))
        done.append(r.variant)
    json.dump(dict(time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), variants=done), open(mark, "w"), indent=1)
    print("logged", len(done), "trials")


def final():
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    v = fz["params"]
    R = Run(FULL_END)
    R.build(v["ref"], (v["k"],))
    allow = None
    if v.get("ai"):
        allows, P = R.ai_allow(v, "2026Q4")
        allow = allows[v["ai"]]
        P.to_parquet(os.path.join(OUT, "ai_pred.parquet"))
    last = gates.END
    days = pd.date_range(SCORE0[v["ref"]], last, freq="D")
    cols, out = {}, {}
    inc_tr = inc_trades()
    for theta, sfx in ((0.5, ""), (0.25, "_t25")):
        F = R.book(v, theta=theta, allow=allow)
        F = F[F.ts < last + pd.Timedelta(days=1)]
        for C in (30e3, 50e3):
            for m in (2.0, 1.0):
                cols[f"s{int(C / 1e3)}_{int(m)}x{sfx}"] = daily(F, v["H"], m, C, R.idx, days)
        st = trade_stats(F, v["H"])
        st["n_noslot"] = F.attrs.get("n_noslot", 0)
        if len(F):
            vl = venue_led(F, v["H"])
            F = pd.concat([F, vl], axis=1)
            F["pnl2"], F["pnl1"] = pnl(F, v["H"], 2.0), pnl(F, v["H"], 1.0)
            st["overlap"] = overlap(F, inc_tr)
            for nm, msk in (("dev", F.ts < gates.HOLD0), ("hold", F.ts >= gates.HOLD0)):
                st[f"{nm}_trades"] = int(msk.sum())
                st[f"{nm}_overlap"] = overlap(F[msk], inc_tr)
                st[f"{nm}_net_bp_2x"] = float(F.pnl2[msk].sum() / F["size"][msk].sum() * 1e4) if msk.any() else np.nan
            for nm, msk in (("cb_led", F.cb_led), ("ref_led", ~F.cb_led)):
                st[f"{nm}_trades"] = int(msk.sum())
                st[f"{nm}_net_bp_2x"] = float(F.pnl2[msk].sum() / F["size"][msk].sum() * 1e4) if msk.any() else np.nan
                st[f"{nm}_cb_after_bp"] = float(F.cb_after_bp[msk].median()) if msk.any() else np.nan
                st[f"{nm}_ref_after_bp"] = float(F.ref_after_bp[msk].median()) if msk.any() else np.nan
            st["by_coin"] = F.groupby("coin").agg(n=("size", "size"), usd=("size", "sum"), pnl2=("pnl2", "sum")).round(1).to_dict("index")
            st["by_year_trades"] = F.groupby(F.ts.dt.year).size().to_dict()
            st["mae_bp_p05"] = float(np.percentile(F[f"mae{v['H']}"], 5) * 1e4)
        out[f"theta{theta}"] = st
        if theta == 0.5:
            F.to_parquet(os.path.join(OUT, "fills.parquet"))
    D = pd.DataFrame(cols)
    D.index.name = "day"
    D.to_parquet(os.path.join(OUT, "daily.parquet"))
    out["ticks"] = {c: {str(m): t for m, t in tm.items()} for (r, c), tm in R.ticks.items()}
    json.dump(out, open(os.path.join(OUT, "final_stats.json"), "w"), indent=1, default=str)
    print(json.dumps({k_: v_ for k_, v_ in out["theta0.5"].items() if k_ not in ("by_coin",)}, indent=1, default=str))


def prints(shard, n_shards):
    """Trade-print check (GitHub Actions): for a 25% sample of the frozen variant's fills, fetch Coinbase spot trades
    around the fill, the take-profit and the time exit, and compare with the candle-based fill and capacity."""
    F = pd.read_parquet(os.path.join(OUT, "fills.parquet"))
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    H = fz["params"]["H"]
    S = F.sample(frac=0.25, random_state=0).sort_values("ts")
    S = S.iloc[shard::n_shards]
    f = common.TradeFetcher()
    rows = []
    t_start = time.time()
    for r in S.itertuples():
        pid = f"{r.coin}-USD"
        t0 = r.ts
        rec = dict(coin=r.coin, ts=t0, L=r.L, TP=r.TP, size=r.size, thr_usd=r.thr_usd, tp_size=r.tp_size)
        try:
            w = f.window(pid, t0 - pd.Timedelta(seconds=5), t0 + pd.Timedelta(minutes=SCAN_MIN + 1))
            live = w[w.time >= t0 + pd.Timedelta(seconds=1)]                # the bid is live 1 s into the minute
            in_min = live[live.time < t0 + pd.Timedelta(minutes=1)]
            rec["n_trades_min"] = int(len(in_min))
            rec["first_px_gt_L"] = bool(len(in_min) and in_min.price.iloc[0] > r.L)
            below = in_min.price < r.L - 0.5 * r.tick
            rec["traded_through"] = bool(below.any())
            # trade-based through-volume: trades strictly below L from the first one while the price stays below
            usd_strict = 0.0
            usd_scan = 0.0
            if below.any():
                j0 = int(np.argmax(below.to_numpy()))
                seg = live.iloc[live.index.get_loc(in_min.index[j0]):]
                bl = (seg.price < r.L - 0.5 * r.tick).to_numpy()
                stop = np.argmin(bl) if (~bl).any() else len(bl)
                usd_strict = float((seg.price * seg["size"]).iloc[:stop].sum())
                mins = seg.time.dt.floor("min")
                for m_, g_ in seg.groupby(mins):
                    b_ = g_.price < r.L - 0.5 * r.tick
                    if not b_.any():
                        break
                    usd_scan += float((g_.price * g_["size"])[b_].sum())
            rec["thr_usd_trades_strict"] = usd_strict
            rec["thr_usd_trades_scan"] = usd_scan
            rec["maker_buy_share"] = float((in_min.side[below] == "BUY").mean()) if below.any() else np.nan
            if r.tp_size > 0:
                ttp = r.ts + pd.Timedelta(minutes=int(getattr(r, f"i_tp{H}") - r.i0))
                wt = f.window(pid, ttp, ttp + pd.Timedelta(minutes=1))
                rec["tp_through"] = bool((wt.price > r.TP + 0.5 * r.tick).any())
                rec["tp_usd_trades"] = float((wt.price * wt["size"])[wt.price > r.TP + 0.5 * r.tick].sum())
            if r.size - r.tp_size > 1e-9:
                ix = int(getattr(r, f"i_x{H}"))
                tx = r.ts + pd.Timedelta(minutes=ix - int(r.i0))
                wx = f.window(pid, tx - pd.Timedelta(seconds=2), tx + pd.Timedelta(seconds=30))
                wx2 = wx[wx.time >= tx + pd.Timedelta(seconds=2)]
                cand_open = (1.0 + float(getattr(r, f"ret_x{H}"))) * r.L
                rec["exit_open_candle"] = cand_open
                rec["exit_first_trade_2s"] = float(wx2.price.iloc[0]) if len(wx2) else np.nan
        except Exception as err:  # noqa: BLE001
            rec["error"] = str(err)[:200]
        rows.append(rec)
        if len(rows) % 25 == 0:
            print(f"  {len(rows)}/{len(S)} fills, {f.n_req} requests, {time.time() - t_start:.0f}s", flush=True)
    os.makedirs(os.path.join(OUT, "prints"), exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "prints", f"prints_{shard}.csv"), index=False)
    print("done", len(rows), "requests", f.n_req)


def select():
    """LOCAL, after `log`: apply the selection rule to every DEV trial and write frozen.json (the freeze)."""
    S = pd.read_csv(os.path.join(DEV_OUT, "summary_dev.csv"))
    pairs = []
    for r in S.to_dict("records"):
        v = dict(ref=r["ref"], k=float(r["k"]), H=int(r["H"]))
        if r.get("quiet") is True or str(r.get("quiet")) == "True":
            v["quiet"] = True
        if isinstance(r.get("ai"), str) and r["ai"] in ("pos", "q50"):
            v["ai"] = r["ai"]
        pairs.append((v, r))
    v = pick(pairs)
    st = [s_ for v_, s_ in pairs if v_ == v][0]
    code = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    fz = dict(idea=IDEA, variant=vname(v), params=v, rule="highest DEV alpha t (sleeve $30K at 2x on incumbent $70K), "
              ">= 40 trades, ties to the simpler", code_commit=code, n_dev_trials=len(S),
              dev={k_: (None if (isinstance(x, float) and not np.isfinite(x)) else x) for k_, x in st.items()},
              frozen_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(fz, open(os.path.join(OUT, "frozen.json"), "w"), indent=1, default=str)
    print(json.dumps(fz, indent=1, default=str))


def gate_run():
    """LOCAL: the pre-registered gates on daily.parquet (2x costs; 1x and theta 0.25 for information)."""
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    D = pd.read_parquet(os.path.join(OUT, "daily.parquet"))
    days = gates.ERA_DAYS[gates.ERA_DAYS >= SCORE0[fz["params"]["ref"]]]
    res = {}
    for nm, sfx in (("2x", "_2x"), ("1x_info", "_1x"), ("2x_theta0.25_info", "_2x_t25")):
        s30, s50 = D[f"s30{sfx}"].reindex(days).fillna(0.0), D[f"s50{sfx}"].reindex(days).fillna(0.0)
        res[nm] = gates.path_b({30000: s30, 50000: s50}, days=days)
    s30 = D["s30_2x"].reindex(days).fillna(0.0)
    inc = gates.incumbent(100e3, 0.5, "instant", days)
    res["corr_inc100"] = float(np.corrcoef(s30, inc)[0, 1])
    worst = inc.nsmallest(20).index
    res["sleeve_on_inc_worst20_days"] = float(s30.reindex(worst).sum())
    res["sleeve_years_2x"] = {int(k): round(float(v), 4) for k, v in gates.years(s30).items()}
    d = s30 * 30e3
    res["top3_share"] = float(d.nlargest(3).sum() / d.sum()) if d.sum() != 0 else None
    res["days"] = [str(days[0].date()), str(days[-1].date())]
    json.dump(res, open(os.path.join(OUT, "gates.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "dev":
        dev()
    elif mode == "log":
        log_trials()
    elif mode == "final":
        final()
    elif mode == "prints":
        prints(int(sys.argv[2]), int(sys.argv[3]))
    elif mode == "select":
        select()
    elif mode == "gates":
        gate_run()
    else:
        raise SystemExit(__doc__)
