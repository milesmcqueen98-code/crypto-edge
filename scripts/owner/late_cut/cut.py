"""Late cut (reports/owner/late_cut_prereg.md): the print bars of one candidate, and coin c's level, sigma and features
at minute t when only its row t-1 (close and volume) is replaced, vectorised over candidates.

Pure numpy / pandas (no lab imports), so the offline test (test_cut.py) runs on made-up data.

Bars. For a candidate minute t (start T, in ns) the bar of second s (0 .. 15) holds the prints stamped
T - 60 s <= time < T + s seconds: close = the price of the last print in (time, trade id) order, volume = the sum of
sizes, n = the number of prints. s = 0 is minute t-1 itself (M0), s = 5 and 10 are M5 and M10.

Changed row. edge.wick.panel's row t reads values through minute t-1 only. Replacing coin c's close and volume of
minute u = t-1 changes, for coin c at t: the 3-day and 7-day betas at u (their newest return), the residual z-scores,
sigma and level (their newest residual), z_1min, the 1-day and 7-day returns, the 1-day high and 240-minute range,
the 60-minute / 3-day volatility ratio and the 15-minute volume ratio. BTC's and the other coins' values are not
touched (alts_mean_z60 and alts_below_2sd of coin c read the other coins only). Every rolling statistic is taken as
pandas' statistic of the window's unchanged part (window minus one, ending at u-1) merged with the one changed value,
so it equals panel's to floating-point rounding (checked against panel itself on the bot's own arrays:
replay.py `exact`).
"""
import numpy as np
import pandas as pd

W, MINP = 4320, 1440
SECONDS = tuple(range(16))
CHANGED = ["z_res60", "z_res15", "z_1min", "bid_depth_bp", "coin_ret1d_bp", "coin_ret7d_bp", "dist_1d_high_bp",
           "range_pos240", "vol_ratio_60m_3d", "volume_ratio_15m", "beta"]
TWELVE = ["DOGE", "LINK", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE", "ENA", "PEPE", "ONDO"]
FIVE = ["ETH", "SOL", "XRP", "LTC", "ZEC"]
NS = 1_000_000_000


# ------------------------------------------------------------------------------------------------ the print bars
def bars(t_ns, px, sz, T):
    """Bars of one candidate. t_ns, px, sz: prints de-duplicated and ordered by (time, trade id); T: start of minute t
    (ns). Returns {close_s, vol_s, n_s for s in SECONDS}."""
    a = int(np.searchsorted(t_ns, T - 60 * NS, "left"))
    out = {}
    for s in SECONDS:
        b = int(np.searchsorted(t_ns, T + s * NS, "left"))
        n = b - a
        out[f"n_{s}"] = n
        out[f"close_{s}"] = float(px[b - 1]) if n > 0 else np.nan
        out[f"vol_{s}"] = float(sz[a:b].sum()) if n > 0 else 0.0
    return out


def order(D):
    """Prints frame (trade_id, time, price, size) -> de-duplicated, ordered (t_ns, px, sz)."""
    D = D.drop_duplicates("trade_id").sort_values(["time", "trade_id"], kind="stable")
    return (D.time.to_numpy().astype("datetime64[ns]").astype(np.int64), D.price.to_numpy(np.float64),
            D["size"].to_numpy(np.float64))


def pick_bar(n0, s_late, quiet_only):
    """The second whose bar a scenario uses: M<s> always s; Q<s> s when minute t-1 holds at most 5 prints, else 0."""
    n0 = np.asarray(n0)
    if not quiet_only:
        return np.full(len(n0), s_late, np.int64)
    return np.where(n0 <= 5, s_late, 0).astype(np.int64)


SCEN = {"M0": (0, False), "M5": (5, False), "M10": (10, False), "Q5": (5, True), "Q10": (10, True)}


def carry_close(cf, vol, u):
    """The close the bot holds for minute u when it has no row there: its last close, if the gap stays within the
    30-minute fill limit (research cf of u-1 with fewer than 30 empty minutes ending at u-1), else NaN."""
    ar = np.arange(len(vol))
    last = np.maximum.accumulate(np.where(np.asarray(vol) > 0, ar, -1))
    run = ar - last                             # empty minutes in a row ending at i
    u = np.asarray(u, np.int64)
    return np.where(run[u - 1] < 30, cf[u - 1], np.nan)


# ------------------------------------------------------------------------------------------------ rolling pieces
def piece(x, w, pos):
    """Count, mean and M2 of pandas' rolling window of w - 1 values ending at pos (min_periods 1)."""
    r = pd.Series(np.asarray(x, np.float64)).rolling(w - 1, min_periods=1)
    cnt, mean, var = r.count().to_numpy()[pos], r.mean().to_numpy()[pos], r.var().to_numpy()[pos]
    m2 = np.where(cnt >= 2, var * (cnt - 1), 0.0)
    return cnt.astype(np.float64), np.where(cnt > 0, mean, 0.0), np.nan_to_num(m2)


def merge1(st, v):
    """Add one value (NaN skipped, as pandas does) to (count, mean, M2)."""
    cnt, mean, m2 = st
    ok = np.isfinite(v)
    c1 = cnt + ok
    d = np.where(ok, v - mean, 0.0)
    mean2 = np.where(ok, mean + d / np.where(c1 > 0, c1, 1.0), mean)
    m22 = np.where(ok, m2 + d * (np.where(ok, v, 0.0) - mean2), m2)
    return c1, mean2, m22


def r_mean(st, minp):
    cnt, mean, _ = st
    return np.where(cnt >= max(minp, 1), mean, np.nan)


def r_var(st, minp):
    cnt, _, m2 = st
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cnt >= max(minp, 2), m2 / (cnt - 1), np.nan)


def r_std(st, minp):
    return np.sqrt(np.maximum(r_var(st, minp), 0.0))


def shift(x, n):
    out = np.full(len(x), np.nan)
    out[n:] = x[:-n]
    return out


def rbeta(ri, rb, w):
    """edge.wick._rbeta."""
    a, b = pd.Series(ri), pd.Series(rb)
    mp = min(MINP, w)
    m = lambda s: s.rolling(w, min_periods=mp).mean()  # noqa: E731
    cov = m(a * b) - m(a) * m(b)
    return (cov / b.rolling(w, min_periods=mp).var()).clip(0.0, 3.0).to_numpy()


class Coin:
    """The unchanged pieces of coin c's window at its candidate minutes t (array): rolling statistics of every series
    whose newest value the replaced row moves, over the window minus one ending at t-2."""

    def __init__(self, cf, vol, btc_cf, t, k=4.0, lookback=60, wbeta=10080):
        self.t = np.asarray(t, np.int64)
        self.k, self.L, self.wbeta = k, lookback, wbeta
        u = self.t - 1
        P = u - 1
        cf = np.asarray(cf, np.float64)
        vol = np.asarray(vol, np.float64)
        x = np.log(cf)
        lpb = np.log(np.asarray(btc_cf, np.float64))
        r1b = np.diff(lpb, prepend=np.nan)
        r1c = np.diff(x, prepend=np.nan)
        self.x_prev = x[u - 1]                                   # log close of t-2 (research)
        self.x_ref = {h: x[u - h] for h in (15, 60, 1440, 10080, lookback)}
        self.x_tL = x[self.t - lookback]
        self.br = {h: (lpb - shift(lpb, h))[u] for h in sorted({15, 60, lookback})}
        self.lpb_u, self.lpb_tL = lpb[u], lpb[self.t - lookback]
        self.r1b_u = r1b[u]
        ws = sorted({W, wbeta})
        self.A = {w: piece(r1c, w, P) for w in ws}               # coin's 1-minute returns
        self.AB = {w: piece(r1c * r1b, w, P) for w in ws}        # product with BTC's
        self.Bm, self.Bv = {}, {}
        for w in ws:                                             # BTC's own (unchanged) at u
            r = pd.Series(r1b).rolling(w, min_periods=min(MINP, w))
            self.Bm[w], self.Bv[w] = r.mean().to_numpy()[u], r.var().to_numpy()[u]
        self.R60 = piece(r1c, 60, P)
        b3 = rbeta(r1c, r1b, W)
        b7 = rbeta(r1c, r1b, wbeta) if wbeta != W else b3
        self.Z = {}
        for h in (15, 60):
            self.Z[h] = piece((x - shift(x, h)) - b3 * (lpb - shift(lpb, h)), W, P)
        self.E = piece((x - shift(x, lookback)) - b7 * (lpb - shift(lpb, lookback)), W, P)
        self.V15, self.VW = piece(vol, 15, P), piece(vol, W, P)
        s_cf = pd.Series(cf)
        self.hi240 = s_cf.rolling(239, min_periods=1).max().to_numpy()[P]
        self.lo240 = s_cf.rolling(239, min_periods=1).min().to_numpy()[P]
        self.n240 = s_cf.rolling(239, min_periods=1).count().to_numpy()[P]
        self.hi1d = s_cf.rolling(1439, min_periods=1).max().to_numpy()[P]
        self.n1d = s_cf.rolling(1439, min_periods=1).count().to_numpy()[P]

    def values(self, cf_new, vol_new, sel=None):
        """Level (before tick rounding), sig, beta (7-day) and the changed features of coin c at its candidates (or at
        the subset `sel`, an index array) with row t-1 replaced by (cf_new, vol_new). Returns {name: float64 array}."""
        g = (lambda a: a) if sel is None else (lambda a: a[sel])
        cfn = np.asarray(cf_new, np.float64)
        vn = np.asarray(vol_new, np.float64)
        with np.errstate(invalid="ignore", divide="ignore"):
            xn = np.log(cfn)
        r1n = xn - g(self.x_prev)

        def sub(st):
            return tuple(g(a) for a in st)

        def beta(w):
            mp = min(MINP, w)
            m_a = r_mean(merge1(sub(self.A[w]), r1n), mp)
            m_ab = r_mean(merge1(sub(self.AB[w]), r1n * g(self.r1b_u)), mp)
            with np.errstate(invalid="ignore", divide="ignore"):
                return np.clip((m_ab - m_a * g(self.Bm[w])) / g(self.Bv[w]), 0.0, 3.0)

        b3 = beta(W)
        b7 = beta(self.wbeta) if self.wbeta != W else b3
        f = {}
        with np.errstate(invalid="ignore", divide="ignore"):
            for h in (15, 60):
                zn = (xn - g(self.x_ref[h])) - b3 * g(self.br[h])
                f[f"z_res{h}"] = zn / r_std(merge1(sub(self.Z[h]), zn), MINP)
            en = (xn - g(self.x_ref[self.L])) - b7 * g(self.br[self.L])
            sig = r_std(merge1(sub(self.E), en), MINP)
            f["level"] = np.exp(g(self.x_tL) + b7 * (g(self.lpb_u) - g(self.lpb_tL)) - self.k * sig)
            f["sig"], f["beta"], f["bid_depth_bp"] = sig, b7, self.k * sig * 1e4
            sA = merge1(sub(self.A[W]), r1n)
            f["z_1min"] = r1n / r_std(sA, MINP)
            f["vol_ratio_60m_3d"] = r_std(merge1(sub(self.R60), r1n), 60) / r_std(sA, MINP)
            f["coin_ret1d_bp"] = (xn - g(self.x_ref[1440])) * 1e4
            f["coin_ret7d_bp"] = (xn - g(self.x_ref[10080])) * 1e4
            ok = np.isfinite(cfn)
            hi = np.fmax(g(self.hi240), cfn)
            lo = np.fmin(g(self.lo240), cfn)
            n240 = g(self.n240) + ok
            hi, lo = np.where(n240 >= 60, hi, np.nan), np.where(n240 >= 60, lo, np.nan)
            f["range_pos240"] = (cfn - lo) / (hi - lo)
            h1 = np.fmax(g(self.hi1d), cfn)
            h1 = np.where(g(self.n1d) + ok >= 600, h1, np.nan)
            f["dist_1d_high_bp"] = np.log(cfn / h1) * 1e4
            s15 = merge1(sub(self.V15), vn)
            sum15 = np.where(s15[0] >= 15, s15[1] * s15[0], np.nan)
            f["volume_ratio_15m"] = sum15 / (r_mean(merge1(sub(self.VW), vn), MINP) * 15)
        return f
