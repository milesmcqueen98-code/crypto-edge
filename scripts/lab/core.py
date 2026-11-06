"""Wick v2 lab core: fast, realistic-cost evaluation of many variants of the AI-filtered resting-bid
dip buyer. Rules are in reports/wick_v2_prereg.md.

Pipeline per variant:
  level set (L, k, sigma/beta windows, reference, side, universe) -> spot candidate fill minutes
  -> features at those minutes (edge.wick.panel + optional extra sets, all known at t-1)
  -> single-trade labels for the exit rule -> walk-forward LightGBM (seed-averaged) -> bid mask
  -> sequential per-coin simulation (one position per coin per book) -> portfolio with whole contracts,
     gross cap, sizing rule -> daily returns under the realistic and the base cost model.
"""
import os
import sys
import time

import lightgbm as lgb
import numba
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge import wick  # noqa: E402
import wick_futures as wf  # noqa: E402
import wick_sim as ws  # noqa: E402

COINS17 = ["ETH", "SOL", "XRP", "DOGE", "LTC", "LINK", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE", "ENA",
           "PEPE", "ONDO", "ZEC"]
# Era: "main" = 2024-01 .. 2026-11 (lab rounds 1-2); "early" = 2021-01 .. 2023-12, never used by any wick research
# before reports/wick_v3_prereg.md (first model trained on 2021, test 2022-2023, fees held at today's bp per coin)
ERA = os.environ.get("LAB_ERA", "main")
if ERA == "early":
    SRC, START, END = "minute_early", "2021-01-01", "2024-01-01"
    TEST0 = pd.Timestamp("2022-01-01")
    VAL = (pd.Timestamp("2022-01-01"), pd.Timestamp("2024-01-01"))
    HOLD = (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01"))
    DAYS = pd.date_range("2022-01-01", "2023-12-31", freq="D")
    WF_Q, WF_M = ("2022Q1", "2023Q4"), ("2022-01", "2023-12")
else:
    SRC, START, END = "minute", "2024-01-01", "2026-11-06"
    TEST0 = pd.Timestamp("2025-01-01")
    VAL = (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-04-01"))
    HOLD = (pd.Timestamp("2026-04-01"), pd.Timestamp("2026-11-06"))
    DAYS = pd.date_range("2025-01-01", "2026-11-05", freq="D")
    WF_Q, WF_M = ("2025Q1", "2026Q4"), ("2025-01", "2026-11")
FEE_USD, FUND_BP, HS_MULT = 0.20, 1.0, 1.5
CAPITAL, TARGET, GROSS_CAP = 10000.0, 2500.0, 15000.0
HS = wf.half_spread_bp()                                   # measured perp half-spread (bp) by coin
_CT = os.path.join(ROOT, "reports", "lab", "cost_table.csv")
_ct = pd.read_csv(_CT).set_index("coin") if os.path.exists(_CT) else None
FEE_BP_NOW = _ct.fee_bp_side.to_dict() if _ct is not None else {}      # today's $0.20/contract in bp, per coin
CONTRACT_USD_NOW = _ct.contract_usd.to_dict() if _ct is not None else {}
BTC_HEDGE_BP = {"real": None, "base": 2.0 + 0.66}          # per side; real computed from price


# ---------------------------------------------------------------- helpers
def shift(x, n):
    return wick.shift(x, n)


def rstd(x, w):
    return pd.Series(x).rolling(w, min_periods=min(1440, w)).std().to_numpy()


def rbeta(ri, rf, w):
    a, b = pd.Series(ri), pd.Series(rf)
    mp = min(1440, w)
    m = lambda s: s.rolling(w, min_periods=mp).mean()  # noqa: E731
    cov = m(a * b) - m(a) * m(b)
    return (cov / b.rolling(w, min_periods=mp).var()).clip(0.0, 3.0).to_numpy()


class Data:
    def __init__(self, coins):
        need = sorted(set(["BTC", "ETH"] + list(coins)))
        self.idx, self.D = ws.load_ohlc(src=SRC, coins=need, start=START, end=END)
        self.lp = {c: np.log(self.D[c]["cf"]) for c in self.D}
        self.T = len(self.idx)
        self.i_test = int(self.idx.get_indexer([TEST0])[0])
        r = np.vstack([np.diff(self.lp[c], prepend=np.nan) for c in need if c in self.lp])
        self.basket_lp = np.nancumsum(np.nanmean(r, axis=0))          # equal-weight market factor (log level)
        b1 = np.diff(self.lp["BTC"], prepend=np.nan)
        rv = pd.Series(b1).rolling(1440, min_periods=600).std()
        self.btc_rv_ratio = shift((rv / rv.rolling(43200, min_periods=10080).median()).to_numpy(), 1)
        self._quiet = {}

    def quiet_mask(self, win):
        if win not in self._quiet:
            et = self.idx.tz_localize("UTC").tz_convert("America/New_York")
            mins = np.asarray(et.hour * 60 + et.minute)
            self._quiet[win] = (mins >= win[0]) & (mins < win[1])
        return self._quiet[win]


def factor(data, ref):
    if ref == "btc":
        return data.lp["BTC"]
    if ref == "btceth":
        return 0.5 * (data.lp["BTC"] + data.lp["ETH"])
    if ref == "basket":
        return data.basket_lp
    raise ValueError(ref)


def hod_factor(e, idx, days=30):
    """Hour-of-day volatility factor of a residual series through minute t: trailing mean of e^2 in this UTC
    hour over `days` days relative to the trailing mean over all hours, square-rooted, clipped to [0.5, 2]."""
    e2 = pd.Series(e * e)
    allm = e2.rolling(days * 1440, min_periods=7 * 1440).mean()
    byh = e2.groupby(np.asarray(idx.hour)).transform(lambda z: z.rolling(days * 60, min_periods=7 * 60).mean())
    return np.clip(np.sqrt(byh / allm).to_numpy(), 0.5, 2.0)


class LevelSet:
    """Order levels, sigma, beta and spot candidate fill minutes for one (L, k, windows, reference, side)."""

    def __init__(self, data, coins, L=60, k=4.0, wsig=4320, wbeta=4320, ref="btc", side=1, minc=None, hod=False):
        """minc: no bid while one contract is worth less than this many dollars (per-contract fees too large);
        hod: scale sigma by the coin's hour-of-day volatility factor (trailing 30 days)."""
        self.data, self.L, self.k, self.side, self.ref = data, L, k, side, ref
        self.coins = [c for c in coins if c in data.D]          # coins without data in this era are skipped
        self.lvl, self.sig, self.beta, self.cands = {}, {}, {}, {}
        D = data.D
        for c in self.coins:
            x = data.lp[c]
            rr = "raw" if (c == "BTC" or ref == "raw") else ref
            if rr == "raw":
                e = x - shift(x, L)
                sig_now = rstd(e, wsig)
                b_lag = np.zeros_like(x)
                if hod:
                    sig_now = sig_now * hod_factor(e, data.idx)
                lvl = np.exp(shift(x, L) - side * k * shift(sig_now, 1))
            else:
                f = factor(data, rr)
                b = rbeta(np.diff(x, prepend=np.nan), np.diff(f, prepend=np.nan), wbeta)
                e = (x - shift(x, L)) - b * (f - shift(f, L))
                sig_now = rstd(e, wsig)
                if hod:
                    sig_now = sig_now * hod_factor(e, data.idx)
                b_lag = shift(b, 1)
                lvl = np.exp(shift(x, L) + b_lag * (shift(f, 1) - shift(f, L)) - side * k * shift(sig_now, 1))
            t = ws.SPOT_TICK.get(c)
            if t:
                lvl = np.floor(lvl / t + 1e-9) * t if side == 1 else np.ceil(lvl / t - 1e-9) * t
            if minc:
                if ERA == "early":                   # today's contract values decide (fees are today's)
                    if CONTRACT_USD_NOW.get(c, 0) < minc:
                        lvl = np.full_like(lvl, np.nan)
                else:
                    with np.errstate(invalid="ignore"):
                        lvl = np.where(ws.PERP[c][1] * shift(D[c]["cf"], 1) >= minc, lvl, np.nan)
            tick = np.nan_to_num(ws.spot_tick(c) / D[c]["cf"], nan=1.0)
            with np.errstate(invalid="ignore"):
                if side == 1:
                    fill = (D[c]["open"] > lvl) & (D[c]["low"] <= lvl * (1 - tick))
                else:
                    fill = (D[c]["open"] < lvl) & (D[c]["high"] >= lvl * (1 + tick))
            cand = np.where(fill)[0]
            self.cands[c] = cand[cand > 1500]
            self.lvl[c], self.sig[c], self.beta[c] = lvl, shift(sig_now, 1), b_lag
        self._feat = None

    def tick(self, c):
        return np.nan_to_num(ws.spot_tick(c) / self.data.D[c]["cf"], nan=1.0)

    # ------------------------------------------------------------ features
    def features(self, extra=()):
        if self._feat is None:
            d = self.data
            cf = {c: d.D[c]["cf"] for c in d.D}
            vol = {c: d.D[c]["vol"] for c in d.D}
            pn = wick.panel(cf, vol, self.coins, d.idx, k=self.k, lookback=self.L, keep_rows=self.cands)
            rows = []
            for c in self.coins:
                cand = self.cands[c]
                if len(cand) == 0:
                    continue
                f = pn[c].loc[d.idx[cand]][wick.FEATS].copy()
                f["bid_depth_bp"] = (self.k * self.sig[c][cand] * 1e4).astype(np.float32)
                f["beta"] = self.beta[c][cand].astype(np.float32)
                f["coin"], f["pos"], f["ts"] = c, cand, d.idx[cand]
                f["episode"] = np.cumsum(np.r_[1, np.diff(cand) > 1])
                f["sig"] = self.sig[c][cand]
                f["px"] = self.lvl[c][cand]
                rows.append(f)
            X = pd.concat(rows, ignore_index=True)
            self._feat = add_extra(d, self, X)
        return self._feat


EXTRA1 = ["dist_7d_high_bp", "dist_3d_low_bp", "range_pos_1d", "ret15_bp", "ret60_bp", "btc_dist_1d_high_bp"]
EXTRA2 = ["clv5", "sellvol5", "btc_sellvol5", "panic_breadth", "mins_since_prev_ep", "eps_24h"]
EXTRA3 = ["hour_of_week", "mins_to_midnight", "us_session"]
EXTRA4 = ["btc_dist_sma100_bp", "btc_ret30d_bp"]


def add_extra(d, ls, X):
    """Extra feature sets, all from data through minute t-1 (candidate-based ones from earlier candidates)."""
    p = lambda a: shift(a, 1)  # noqa: E731
    btc = d.D["BTC"]
    b_cf = pd.Series(btc["cf"])
    btc_dist = p(np.log(btc["cf"] / b_cf.rolling(1440, min_periods=600).max().to_numpy())) * 1e4
    b_r = np.diff(d.lp["BTC"], prepend=np.nan)
    bv = pd.Series(btc["vol"])
    btc_sell = p(((bv * (b_r < 0)).rolling(5).sum() / (bv.rolling(4320, min_periods=1440).mean() * 5)).to_numpy())
    ind = {c: np.zeros(d.T, dtype=np.int32) for c in ls.coins}
    for c in ls.coins:
        ind[c][ls.cands[c]] = 1
    cs = {c: np.cumsum(ind[c]) for c in ls.coins}
    out = []
    for c in ls.coins:
        sub = X[X.coin == c]
        cand = sub.pos.to_numpy()
        D = d.D[c]
        s = pd.Series(D["cf"])
        f = pd.DataFrame(index=sub.index)
        f["dist_7d_high_bp"] = p(np.log(D["cf"] / s.rolling(10080, min_periods=2000).max().to_numpy()))[cand] * 1e4
        f["dist_3d_low_bp"] = p(np.log(D["cf"] / s.rolling(4320, min_periods=1440).min().to_numpy()))[cand] * 1e4
        lo1, hi1 = s.rolling(1440, min_periods=600).min().to_numpy(), s.rolling(1440, min_periods=600).max().to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            f["range_pos_1d"] = p((D["cf"] - lo1) / (hi1 - lo1))[cand]
            lp = d.lp[c]
            f["ret15_bp"] = p(lp - shift(lp, 15))[cand] * 1e4
            f["ret60_bp"] = p(lp - shift(lp, 60))[cand] * 1e4
            f["btc_dist_1d_high_bp"] = btc_dist[cand]
            h, l_, cl = D["high"], D["low"], D["close"]
            clv = ((cl - l_) - (h - cl)) / (h - l_)
            f["clv5"] = p(pd.Series(clv).rolling(5, min_periods=1).mean().to_numpy())[cand]
            r = np.diff(lp, prepend=np.nan)
            v = pd.Series(D["vol"])
            f["sellvol5"] = p(((v * (r < 0)).rolling(5).sum() / (v.rolling(4320, min_periods=1440).mean() * 5)).to_numpy())[cand]
        f["btc_sellvol5"] = btc_sell[cand]
        others = [o for o in ls.coins if o != c]
        br = np.zeros(len(cand))
        for o in others:
            a = cs[o]
            hi_ = a[np.maximum(cand - 1, 0)]
            lo_ = a[np.maximum(cand - 6, 0)]
            br += (hi_ - lo_) > 0
        f["panic_breadth"] = br
        ep = sub.episode.to_numpy()
        starts = pd.Series(cand).groupby(ep).transform("min").to_numpy()
        ends = pd.Series(cand).groupby(ep).max()
        prev_end = ends.shift(1).reindex(ep).to_numpy()
        f["mins_since_prev_ep"] = np.minimum(np.where(np.isnan(prev_end), 10080, starts - prev_end), 10080)
        st_sorted = np.sort(pd.Series(cand).groupby(ep).min().to_numpy())
        f["eps_24h"] = (np.searchsorted(st_sorted, starts) - np.searchsorted(st_sorted, starts - 1440))
        ts = d.idx[cand]
        f["hour_of_week"] = ts.dayofweek * 24 + ts.hour
        f["mins_to_midnight"] = 1440 - (ts.hour * 60 + ts.minute)
        mins = ts.hour * 60 + ts.minute
        f["us_session"] = ((ts.dayofweek < 5) & (mins >= 810) & (mins < 1200)).astype(int)
        out.append(f)
    E = pd.concat(out).loc[X.index]
    # trend regime (BTC vs its 100-day average, BTC 30-day return), known at t-1
    bcf = pd.Series(btc["cf"])
    sma100 = bcf.rolling(144000, min_periods=100000).mean().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        dist = p(np.log(btc["cf"] / sma100)) * 1e4
        r30 = p(d.lp["BTC"] - shift(d.lp["BTC"], 43200)) * 1e4
    pos = X.pos.to_numpy()
    E["btc_dist_sma100_bp"] = dist[pos]
    E["btc_ret30d_bp"] = r30[pos]
    return pd.concat([X, E.astype(np.float32)], axis=1)


# ---------------------------------------------------------------- exits: kernels
@numba.njit(cache=True)
def _leg_step(side, hh, lo, tp, tick_u):
    if side == 1:
        return hh >= tp * (1.0 + tick_u)
    return lo <= tp * (1.0 - tick_u)


@numba.njit(cache=True)
def single_x(cand, O, Hh, Lo, Cf, lvl, tp1d, tp2d, w1, dyn, stop_t, stop_d, tick, hmax, side, pw=0, phs=0.0):
    """Outcome of one trade entered at lvl[t] for each candidate t. Returns exit px of both legs, their
    types (1 tp, 2 early stop, 3 time/market, 4 passive time exit) and the last exit index. With pw > 0 the time
    exit first rests a limit at the hold-cap minute's price shifted half a spread our way (phs, a fraction)
    for pw minutes (filled on a one-tick trade-through), then sells at market."""
    n = len(cand)
    x1 = np.full(n, np.nan)
    x2 = np.full(n, np.nan)
    t1 = np.zeros(n, np.int8)
    t2 = np.zeros(n, np.int8)
    xl = np.full(n, -1, np.int64)
    T = len(O)
    for j in range(n):
        t = cand[j]
        e = lvl[t]
        two = w1 < 1.0
        tpa = e * np.exp(side * tp1d[t]) if not np.isnan(tp1d[t]) else (np.inf if side == 1 else 0.0)
        tpb = e * np.exp(side * tp2d[t]) if (two and not np.isnan(tp2d[t])) else tpa
        o1, o2 = True, two
        passive, pp, u_dead = False, 0.0, 0
        for u in range(t + 1, min(T, t + hmax + 1 + pw)):
            if passive:
                if not np.isnan(Hh[u]) and _leg_step(side, Hh[u], Lo[u], pp, tick[u]):
                    if o1:
                        x1[j], t1[j], o1 = pp, 4, False
                    if o2:
                        x2[j], t2[j], o2 = pp, 4, False
                    xl[j] = u
                    break
                if u >= u_dead and not np.isnan(Cf[u]):
                    if o1:
                        x1[j], t1[j], o1 = Cf[u], 3, False
                    if o2:
                        x2[j], t2[j], o2 = Cf[u], 3, False
                    xl[j] = u
                    break
                continue
            if not np.isnan(Hh[u]):
                a, b = tpa, tpb
                if not np.isnan(dyn[u]):
                    a = max(dyn[u], e) if side == 1 else min(dyn[u], e)
                    b = a
                if o1 and _leg_step(side, Hh[u], Lo[u], a, tick[u]):
                    x1[j], t1[j], o1 = a, 1, False
                if o2 and _leg_step(side, Hh[u], Lo[u], b, tick[u]):
                    x2[j], t2[j], o2 = b, 1, False
            if not o1 and not o2:
                xl[j] = u
                break
            if stop_t > 0 and u - t == stop_t and not np.isnan(Cf[u]):
                if side * (np.log(Cf[u] / e)) < -stop_d[t]:
                    if o1:
                        x1[j], t1[j], o1 = Cf[u], 2, False
                    if o2:
                        x2[j], t2[j], o2 = Cf[u], 2, False
                    xl[j] = u
                    break
            if u - t >= hmax and not np.isnan(Cf[u]):
                if pw > 0:
                    passive, pp, u_dead = True, Cf[u] * (1.0 + side * phs), u + pw
                    continue
                if o1:
                    x1[j], t1[j], o1 = Cf[u], 3, False
                if o2:
                    x2[j], t2[j], o2 = Cf[u], 3, False
                xl[j] = u
                break
        if not two:
            x2[j], t2[j] = x1[j], t1[j]
    return x1, x2, t1, t2, xl


@numba.njit(cache=True)
def book_x(O, Hh, Lo, Cf, lvl, tp1d, tp2d, w1, dyn, stop_t, stop_d, tick, hmax, side, pw=0, phs=0.0):
    """Sequential book for one coin: one position at a time, same exit logic as single_x."""
    T = len(O)
    cap = T // 4 + 16
    ei = np.empty(cap, np.int64)
    xi = np.empty(cap, np.int64)
    ep = np.empty(cap, np.float64)
    x1 = np.empty(cap, np.float64)
    x2 = np.empty(cap, np.float64)
    ty1 = np.empty(cap, np.int8)
    ty2 = np.empty(cap, np.int8)
    n = 0
    t = 0
    two = w1 < 1.0
    while t < T and n < cap - 1:
        b = lvl[t]
        if np.isnan(b) or np.isnan(Lo[t]) or np.isnan(O[t]):
            t += 1
            continue
        filled = (O[t] > b and Lo[t] <= b * (1.0 - tick[t])) if side == 1 else (O[t] < b and Hh[t] >= b * (1.0 + tick[t]))
        if not filled:
            t += 1
            continue
        e = b
        tpa = e * np.exp(side * tp1d[t]) if not np.isnan(tp1d[t]) else (np.inf if side == 1 else 0.0)
        tpb = e * np.exp(side * tp2d[t]) if (two and not np.isnan(tp2d[t])) else tpa
        o1, o2 = True, two
        r1, r2, k1, k2 = np.nan, np.nan, 0, 0
        last = -1
        passive, pp, u_dead = False, 0.0, 0
        for u in range(t + 1, T):
            if passive:
                if not np.isnan(Hh[u]) and _leg_step(side, Hh[u], Lo[u], pp, tick[u]):
                    if o1:
                        r1, k1, o1 = pp, 4, False
                    if o2:
                        r2, k2, o2 = pp, 4, False
                    last = u
                    break
                if u >= u_dead and not np.isnan(Cf[u]):
                    if o1:
                        r1, k1, o1 = Cf[u], 3, False
                    if o2:
                        r2, k2, o2 = Cf[u], 3, False
                    last = u
                    break
                continue
            if not np.isnan(Hh[u]):
                a, bb = tpa, tpb
                if not np.isnan(dyn[u]):
                    a = max(dyn[u], e) if side == 1 else min(dyn[u], e)
                    bb = a
                if o1 and _leg_step(side, Hh[u], Lo[u], a, tick[u]):
                    r1, k1, o1 = a, 1, False
                if o2 and _leg_step(side, Hh[u], Lo[u], bb, tick[u]):
                    r2, k2, o2 = bb, 1, False
            if not o1 and not o2:
                last = u
                break
            if stop_t > 0 and u - t == stop_t and not np.isnan(Cf[u]):
                if side * (np.log(Cf[u] / e)) < -stop_d[t]:
                    if o1:
                        r1, k1, o1 = Cf[u], 2, False
                    if o2:
                        r2, k2, o2 = Cf[u], 2, False
                    last = u
                    break
            if u - t >= hmax and not np.isnan(Cf[u]):
                if pw > 0:
                    passive, pp, u_dead = True, Cf[u] * (1.0 + side * phs), u + pw
                    continue
                if o1:
                    r1, k1, o1 = Cf[u], 3, False
                if o2:
                    r2, k2, o2 = Cf[u], 3, False
                last = u
                break
        if last < 0:
            break
        if not two:
            r2, k2 = r1, k1
        ei[n], xi[n], ep[n], x1[n], x2[n], ty1[n], ty2[n] = t, last, e, r1, r2, k1, k2
        n += 1
        t = last + 1
    return ei[:n], xi[:n], ep[:n], x1[:n], x2[:n], ty1[:n], ty2[:n]


class Exit:
    def __init__(self, theta=0.6, H=60, theta2=None, w1=1.0, dyn_z=None, stop_t=0, stop_k=None, pw=0):
        self.theta, self.H, self.theta2, self.w1 = theta, H, theta2, w1
        self.dyn_z, self.stop_t, self.stop_k, self.pw = dyn_z, stop_t, stop_k, int(pw)

    def phs(self, c):
        """Half the measured perp spread as a fraction (the passive time exit rests this far from the last price)."""
        return HS.get(c, 2.0) / 1e4 if self.pw > 0 else 0.0

    def arrays(self, ls, c):
        sig, k = ls.sig[c], ls.k
        tp1 = self.theta * k * sig if self.theta is not None else np.full_like(sig, np.nan)
        tp2 = (self.theta2 * k * sig) if self.theta2 is not None else np.full_like(sig, np.nan)
        if self.dyn_z is not None:                     # fair value now, minus dyn_z sigma
            dyn = ls.lvl[c] * np.exp(ls.side * (k - self.dyn_z) * sig)
        else:
            dyn = np.full_like(sig, np.nan)
        stop_d = (self.stop_k * sig) if self.stop_k is not None else np.full_like(sig, np.inf)
        return tp1, tp2, dyn, stop_d


ADV_TAKER_BP = 3.0                                         # advertised US perp schedule: 0% maker, 0.03% taker
QUIET = None                                               # (lo, hi) ET minutes: no new bids (as the bot does)


def costs_bp(c, px, ty, model):
    """Exit-leg cost in bp for exit types (1 tp and 4 passive exit are maker, else taker) under a cost model
    ("real": $0.20/contract + 1.5x half-spread on taker exits; "adv": advertised 0%/0.03% + 1.5x half-spread on
    taker exits; "base": 2 bp + one perp tick on taker exits); px in spot units."""
    if model == "adv":
        hs = HS_MULT * HS.get(c, ws.PERP[c][2] / px * 1e4)
        return np.where((ty == 1) | (ty == 4), 0.0, ADV_TAKER_BP + hs)
    if model == "real":
        fee = FEE_BP_NOW[c] if ERA == "early" else FEE_USD / (ws.PERP[c][1] * px) * 1e4
        hs = HS_MULT * HS.get(c, ws.PERP[c][2] / px * 1e4)
        return fee + np.where((ty == 1) | (ty == 4), 0.0, hs)
    tick_bp = ws.PERP[c][2] / px * 1e4
    return 2.0 + np.where((ty == 1) | (ty == 4), 0.0, tick_bp)


def entry_cost_bp(c, px, model):
    if model == "adv":
        return FUND_BP + 0.0 * px
    if model == "real":
        if ERA == "early":
            return FEE_BP_NOW[c] + FUND_BP + 0.0 * px
        return FEE_USD / (ws.PERP[c][1] * px) * 1e4 + FUND_BP
    return 2.0 + 0.0 * px


def net_bp(c, side, e, x1, x2, t1, t2, w1, model):
    g = side * 1e4 * (w1 * np.log(x1 / e) + (1 - w1) * np.log(x2 / e))
    cost = entry_cost_bp(c, e, model) + w1 * costs_bp(c, x1, t1, model) + (1 - w1) * costs_bp(c, x2, t2, model)
    return g, g - cost


def labels(ls, ex):
    """Single-trade outcomes for every candidate (training labels), under both cost models."""
    X = ls.features()
    d = ls.data
    out = []
    for c in ls.coins:
        D = d.D[c]
        cand = ls.cands[c]
        tp1, tp2, dyn, stop_d = ex.arrays(ls, c)
        x1, x2, t1, t2, xl = single_x(cand, D["open"], D["high"], D["low"], D["cf"], ls.lvl[c], tp1, tp2, ex.w1, dyn,
                                      ex.stop_t, stop_d, ls.tick(c), ex.H, ls.side, ex.pw, ex.phs(c))
        e = ls.lvl[c][cand]
        g, nr = net_bp(c, ls.side, e, x1, x2, t1, t2, ex.w1, "real")
        _, nb = net_bp(c, ls.side, e, x1, x2, t1, t2, ex.w1, "base")
        out.append(pd.DataFrame({"gross": g, "net_real": nr, "net_base": nb, "tp_hit": ((t1 == 1) & (t2 == 1)).astype(int)},
                                index=X.index[X.coin == c]))
    return pd.concat(out).loc[X.index]


# ---------------------------------------------------------------- AI
def walk_forward(X, y, feats, params=None, seeds=(7, 11, 23), freq="Q", window_days=None, weight="episode",
                 halflife=None, thr_q=0.5, thr_abs=None, objective=None, monotone=None, rounds=None, logit_ens=False,
                 X_extra=None):
    """Returns (pred, thr) for X's test rows; with X_extra also (pred_extra, thr_extra) from the same models."""
    params = dict(wick.PARAMS) | (params or {})
    if objective:
        params["objective"] = objective
        params.pop("alpha", None)
    if monotone:
        params["monotone_constraints"] = [monotone.get(f, 0) for f in feats]
        params["monotone_constraints_method"] = "advanced"
    rounds = rounds or wick.ROUNDS
    periods = pd.period_range(*WF_Q, freq="Q") if freq == "Q" else pd.period_range(*WF_M, freq="M")
    pred = pd.Series(np.nan, index=X.index)
    thr = pd.Series(np.nan, index=X.index)
    if X_extra is not None:
        pred_x = pd.Series(np.nan, index=X_extra.index)
        thr_x = pd.Series(np.nan, index=X_extra.index)
    cat = ["coin_id"] if "coin_id" in feats else []
    for per in periods:
        tr_mask = X.ts < per.start_time - pd.Timedelta(days=1)
        if window_days:
            tr_mask &= X.ts >= per.start_time - pd.Timedelta(days=window_days)
        te_mask = (X.ts >= per.start_time) & (X.ts <= per.end_time)
        if not te_mask.any() or tr_mask.sum() < 200:
            continue
        tr, te = X[tr_mask], X[te_mask]
        if weight == "episode":
            w = 1.0 / tr.groupby(["coin", "episode"]).ts.transform("size").to_numpy()
        else:
            w = np.ones(len(tr))
        if halflife:
            age = (per.start_time - tr.ts).dt.total_seconds().to_numpy() / 86400
            w = w * 0.5 ** (age / halflife)
        ytr = y[tr_mask].to_numpy()
        pte, ptr, pxx = [], [], []
        xe = None
        if X_extra is not None:
            xe = X_extra[(X_extra.ts >= per.start_time) & (X_extra.ts <= per.end_time)]
        for s in seeds:
            m = lgb.train(params | {"seed": s}, lgb.Dataset(tr[feats], ytr, weight=w, categorical_feature=cat),
                          num_boost_round=rounds)
            pte.append(m.predict(te[feats]))
            ptr.append(m.predict(tr[feats]))
            if xe is not None and len(xe):
                pxx.append(m.predict(xe[feats]))
        pte, ptr = np.mean(pte, axis=0), np.mean(ptr, axis=0)
        if logit_ens:
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.impute import SimpleImputer
            num = [f for f in feats if f != "coin_id"]
            lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=0.1, max_iter=500))
            lr.fit(tr[num], (ytr > 0).astype(int), logisticregression__sample_weight=w)
            q_te, q_tr = lr.predict_proba(te[num])[:, 1], lr.predict_proba(tr[num])[:, 1]
            rank = lambda a, ref: np.searchsorted(np.sort(ref), a) / len(ref)  # noqa: E731
            pte = 0.5 * rank(pte, ptr) + 0.5 * rank(q_te, q_tr)
            ptr = 0.5 * rank(ptr, ptr) + 0.5 * rank(q_tr, q_tr)
        pred[te.index] = pte
        t_ = thr_abs if thr_abs is not None else np.quantile(ptr, thr_q)
        thr[te.index] = t_
        if xe is not None and len(xe):
            if logit_ens:
                raise NotImplementedError("logit ensemble not supported with X_extra")
            pred_x[xe.index] = np.mean(pxx, axis=0)
            thr_x[xe.index] = t_
    if X_extra is not None:
        return pred, thr, pred_x, thr_x
    return pred, thr


# ---------------------------------------------------------------- simulation and portfolio
def simulate(ls, ex, keep=None, pred=None, start=TEST0):
    """Sequential per-coin books over the test period; keep/pred indexed like ls.features()."""
    X = ls.features()
    d = ls.data
    i0 = d.idx.get_indexer([start])[0]
    trs = []
    for c in ls.coins:
        D = d.D[c]
        lvl = ls.lvl[c].copy()
        lvl[:i0] = np.nan
        if QUIET is not None:
            lvl[d.quiet_mask(QUIET)] = np.nan
        rows = X.index[X.coin == c]
        cand = X.pos[rows].to_numpy()
        if keep is not None:
            k = keep[rows].to_numpy()
            off = cand[(cand >= i0) & ~k]
            lvl[off] = np.nan
        tp1, tp2, dyn, stop_d = ex.arrays(ls, c)
        ei, xi, ep, x1, x2, t1, t2 = book_x(D["open"], D["high"], D["low"], D["cf"], lvl, tp1, tp2, ex.w1, dyn,
                                            ex.stop_t, stop_d, ls.tick(c), ex.H, ls.side, ex.pw, ex.phs(c))
        if len(ei) == 0:
            continue
        g, nr = net_bp(c, ls.side, ep, x1, x2, t1, t2, ex.w1, "real")
        _, nb = net_bp(c, ls.side, ep, x1, x2, t1, t2, ex.w1, "base")
        _, na = net_bp(c, ls.side, ep, x1, x2, t1, t2, ex.w1, "adv")
        pmap = pd.Series(pred[rows].to_numpy(), index=cand) if pred is not None else None
        tr = pd.DataFrame({"ts": d.idx[ei], "exit_ts": d.idx[xi], "coin": c, "side": ls.side, "ei": ei, "xi": xi,
                           "px": ep, "gross": g, "net_real": nr, "net_base": nb, "net_adv": na, "sig": ls.sig[c][ei],
                           "beta": ls.beta[c][ei], "tp": (t1 == 1)})
        tr["pred"] = pmap.reindex(ei).to_numpy() if pmap is not None else np.nan
        trs.append(tr)
    return pd.concat(trs, ignore_index=True) if trs else pd.DataFrame()


_FUT = {}


def fut_data(c, idx):
    if c not in _FUT:
        _FUT[c] = wf.load_futures(c, idx)
    return _FUT[c]


def futures_trades(ls, ex, keep=None, pred=None, thr=None, confirm=True, strict=False, order_usd=TARGET):
    """Execute one book on Coinbase perp 1-minute candles (adoption bar 3). Signals and AI decisions come from the
    spot pipeline. Perp bid = spot level x basis (last perp trade / spot close, at t-1), rounded to the perp tick
    (down for bids, up for offers). A perp fill needs the perp minute to open beyond the bid and trade through it
    by one perp tick (strict: 3 ticks and >= 3x our contracts traded that minute) and, with confirm, the spot
    minute to trade through the spot level too. Take-profits on perp highs/lows (price rounded against us); time
    exits and stops at the worse of the last perp trade and spot x last basis. Costs are computed on
    spot-equivalent prices (perp price / entry basis) so that units match ws.PERP. Returns trades like simulate()
    and each coin's first full day of perp data."""
    X = ls.features()
    d = ls.data
    FS = wf.fut_specs()
    trs, starts = [], {}
    for c in ls.coins:
        F = fut_data(c, d.idx) if c in FS else None
        if F is None:
            continue
        start = (F["first"] + pd.Timedelta(days=1)).normalize()
        starts[c] = start
        i0 = max(int(d.idx.get_indexer([start])[0]), d.i_test)
        _, size_f, tick_usd = FS[c]
        D = d.D[c]
        basis = shift(F["cf"] / D["cf"], 1)
        raw = ls.lvl[c] * basis
        lvl = wick.round_down(raw, tick_usd) if ls.side == 1 else wick.round_up(raw, tick_usd)
        lvl[:i0] = np.nan
        if QUIET is not None:
            lvl[d.quiet_mask(QUIET)] = np.nan
        rows = X.index[X.coin == c]
        cand = X.pos[rows].to_numpy()
        if keep is not None:
            lvl[cand[~keep[rows].to_numpy()]] = np.nan
        if confirm:
            ok = np.zeros(d.T, dtype=bool)
            ok[ls.cands[c]] = True
            lvl[~ok] = np.nan
        tick = np.nan_to_num((3 if strict else 1) * tick_usd / F["cf"], nan=1.0)
        if strict:
            with np.errstate(invalid="ignore", divide="ignore"):
                need = np.ceil(order_usd / (size_f * lvl))
                lvl = np.where(F["vol"] >= 3 * need, lvl, np.nan)
        traded = np.isfinite(F["close"])
        b_last = pd.Series(np.where(traded, F["close"] / D["cf"], np.nan)).ffill().to_numpy()
        alt = D["cf"] * b_last
        exit_px = np.fmin(F["cf"], alt) if ls.side == 1 else np.fmax(F["cf"], alt)
        tp1, tp2, dyn, stop_d = ex.arrays(ls, c)
        dyn = dyn * basis
        ei, xi, ep, x1, x2, t1, t2 = book_x(F["open"], F["high"], F["low"], exit_px, lvl, tp1, tp2, ex.w1, dyn,
                                            ex.stop_t, stop_d, tick, ex.H, ls.side, ex.pw, ex.phs(c))
        if len(ei) == 0:
            continue
        rnd = wick.round_down if ls.side == 1 else wick.round_up
        x1 = np.where((t1 == 1) | (t1 == 4), rnd(x1, tick_usd), x1)
        x2 = np.where((t2 == 1) | (t2 == 4), rnd(x2, tick_usd), x2)
        b0 = basis[ei]
        e_s, x1_s, x2_s = ep / b0, x1 / b0, x2 / b0
        g, nr = net_bp(c, ls.side, e_s, x1_s, x2_s, t1, t2, ex.w1, "real")
        _, nb = net_bp(c, ls.side, e_s, x1_s, x2_s, t1, t2, ex.w1, "base")
        _, na = net_bp(c, ls.side, e_s, x1_s, x2_s, t1, t2, ex.w1, "adv")
        tr = pd.DataFrame({"ts": d.idx[ei], "exit_ts": d.idx[xi], "coin": c, "side": ls.side, "ei": ei, "xi": xi,
                           "px": e_s, "gross": g, "net_real": nr, "net_base": nb, "net_adv": na, "sig": ls.sig[c][ei],
                           "beta": ls.beta[c][ei], "tp": (t1 == 1)})
        if pred is not None:
            pmap = pd.Series(pred[rows].to_numpy(), index=cand)
            tmap = pd.Series(thr[rows].to_numpy(), index=cand)
            tr["pred"] = pmap.reindex(ei).to_numpy()
            tr["thr"] = tmap.reindex(ei).to_numpy()
        else:
            tr["pred"] = tr["thr"] = np.nan
        trs.append(tr)
    return (pd.concat(trs, ignore_index=True) if trs else pd.DataFrame()), starts


def hedge(tr, data, model):
    """BTC-perp beta hedge from the fill minute's close to the exit minute's close (taker both ways)."""
    lpb = data.lp["BTC"]
    btc_ret = (lpb[tr.xi.to_numpy()] - lpb[tr.ei.to_numpy()]) * 1e4
    b = np.nan_to_num(tr.beta.to_numpy())
    if model == "real":
        btc_px = data.D["BTC"]["cf"][tr.ei.to_numpy()]
        per_side = FEE_USD / (0.01 * btc_px) * 1e4 + HS_MULT * HS.get("BTC", 0.66)
    else:
        per_side = BTC_HEDGE_BP["base"]
    return -tr.side.to_numpy() * b * btc_ret - 2 * b * per_side


def portfolio(tr, cap=6, target=TARGET, gross_cap=GROSS_CAP, size=None, priority="coin", max_new_per_min=None,
              regime=None, throttle=None, fractional=None, hedged=False, data=None, size_scale=None):
    """Daily returns (fraction of $10k) under both cost models + trade stats."""
    if fractional is None:
        fractional = ERA == "early"
    if tr.empty:
        z = pd.Series(0.0, index=DAYS)
        return {"real": z, "base": z, "adv": z}, tr
    tr = tr.copy()
    m = np.ones(len(tr))
    if size == "pred":
        m = np.clip(tr.pred.to_numpy() / tr.thr.to_numpy(), 0.5, 2.0)
    elif size == "pred2":
        m = np.clip((tr.pred.to_numpy() / tr.thr.to_numpy()) ** 2, 0.25, 3.0)
    elif size == "invsig":
        m = np.clip(np.nanmedian(tr.sig) / tr.sig.to_numpy(), 0.5, 2.0)
    elif size == "pred_sig":
        r = (tr.pred.to_numpy() / tr.thr.to_numpy()) * (np.nanmedian(tr.sig) / tr.sig.to_numpy())
        m = np.clip(r, 0.5, 2.0)
    if size_scale is not None:
        m = m * size_scale(tr)
    if regime is not None and data is not None:
        m = m * np.clip(np.nan_to_num(data.btc_rv_ratio[tr.ei.to_numpy()], nan=1.0), 0.5, 2.0)
    tr["mult"] = m
    if priority == "pred":
        tr["_p"] = -tr.pred.fillna(-1e9)
        tr = tr.sort_values(["ts", "_p", "coin"], kind="mergesort").reset_index(drop=True)
    else:
        tr = tr.sort_values(["ts", "coin"], kind="mergesort").reset_index(drop=True)
    size_coin = np.array([ws.PERP[c][1] for c in tr.coin])
    px = tr.px.to_numpy()
    want = target * tr.mult.to_numpy()
    if fractional:
        notional = want
    else:
        cv = size_coin * px
        notional = np.maximum(1, np.floor(want / cv)) * cv
    keep, open_, new_in_min = [], [], {}
    real_pnl = []
    eq, peak = 0.0, 0.0
    closed = []
    for i, r in enumerate(tr.itertuples()):
        open_ = [(e, n_) for e, n_ in open_ if e >= r.ts]
        if len(open_) >= cap or sum(n_ for _, n_ in open_) + notional[i] > gross_cap * (1 + 1e-9) + (0 if not fractional else 0):
            continue
        if max_new_per_min and new_in_min.get(r.ts, 0) >= max_new_per_min:
            continue
        nt = notional[i]
        if throttle is not None:
            eq_now = sum(p for x, p in closed if x < r.ts)
            peak = max(peak, eq_now)
            if (eq_now - peak) / CAPITAL < -throttle:
                nt = nt * 0.5
        keep.append(i)
        open_.append((r.exit_ts, nt))
        new_in_min[r.ts] = new_in_min.get(r.ts, 0) + 1
        notional[i] = nt
        if throttle is not None:
            closed.append((r.exit_ts, nt * r.net_real / 1e4))
    k = tr.loc[keep].copy()
    k["notional"] = notional[keep]
    out = {}
    for model in [m for m in ("real", "base", "adv") if f"net_{m}" in k]:
        net = k[f"net_{model}"].to_numpy()
        if hedged:
            net = net + hedge(k, data, model)
        pnl = k.notional.to_numpy() * net / 1e4
        out[model] = pd.Series(pnl, index=k.exit_ts).resample("D").sum().reindex(DAYS, fill_value=0.0) / CAPITAL
        k[f"pnl_{model}"] = pnl
        k[f"netx_{model}"] = net
    return out, k


def stats(d, lo=None, hi=None):
    x = d if lo is None else d[(d.index >= lo) & (d.index < hi)]
    sd = x.std()
    eq = x.cumsum()
    return dict(sharpe=x.mean() / sd * np.sqrt(365) if sd > 0 else np.nan,
                t=x.mean() / sd * np.sqrt(len(x)) if sd > 0 else np.nan,
                ann=x.mean() * 365, maxdd=(eq - eq.cummax()).min(), worst=x.min())


def summarize(name, family, daily, k):
    """Validation metrics (selection) and holdout metrics (written separately)."""
    val, hold = {"variant": name, "family": family}, {"variant": name, "family": family}
    for model in [m for m in ("real", "base", "adv") if m in daily]:
        for lab, (lo, hi), dst in [("val", VAL, val), ("hold", HOLD, hold)]:
            s = stats(daily[model], lo, hi)
            for kk, v in s.items():
                dst[f"{lab}_{model}_{kk}"] = v
    for lab, (lo, hi), dst in [("val", VAL, val), ("hold", HOLD, hold)]:
        kk = k[(k.ts >= lo) & (k.ts < hi)] if len(k) else k
        dst[f"{lab}_trades"] = len(kk)
        dst[f"{lab}_net_real_bp"] = kk.netx_real.mean() if len(kk) else np.nan
        dst[f"{lab}_hit"] = (kk.netx_real > 0).mean() if len(kk) else np.nan
    return val, hold
