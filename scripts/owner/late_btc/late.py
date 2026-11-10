"""Late BTC (reports/owner/late_btc_prereg.md): what the bot's BTC input looks like when its newest candle is missing,
and R2-08's BTC-dependent levels and features computed from it, vectorised over every decision minute.

Pure numpy / pandas (no lab imports), so the offline test (test_late.py) runs on made-up closes.

The bot (bot/spot/engine.py `arrays`) keeps the candles it has, reindexes them to every minute, fills a missing close
forward (ffill, limit 30) and sets a missing minute's volume to 0. At decision minute t (row t of edge.wick.panel, which
uses only values through minute t-1) a BTC answer that is m minutes late lacks rows t-m .. t-1, so:
  close[s] = B[s] for s <= t-1-m and B[t-1-m] for t-m <= s <= t-1;   volume[s] = 0 for t-m <= s <= t-1.
B is BTC's close as the bot holds it before the tail is lost: the true close (S0 to S3), or (S4) the true close with a
fixed 30% of older minutes dropped and filled forward the same way (`base_s4`).

`late_rows` gives, for decision rows t and a lag m >= 1, every value of edge.wick.panel that depends on BTC (level,
sig and the 13 BTC-dependent features), as panel would compute them on that array with wbeta (7-day beta behind level,
sig, bid depth and the beta feature; 3-day beta in the residual z-scores). Rolling statistics are taken as pandas'
rolling statistic of the unchanged part of the window (window minus the m changed minutes, ending at t-1-m) merged
with the m changed values (Welford updates), so they equal panel's to floating-point rounding (checked against
panel itself on the bot's own array: replay.py `exact`).
"""
import warnings

import numpy as np
import pandas as pd

W, MINP = 4320, 1440                 # edge.wick: 3-day window, 1-day minimum
BTC_FEATS = ["z_res60", "z_res15", "bid_depth_bp", "btc_z5", "btc_z15", "btc_z60", "btc_ret240_bp", "btc_ret1d_bp",
             "btc_vol_ratio", "btc_volume_ratio_15m", "alts_mean_z60", "alts_below_2sd", "beta"]


# ------------------------------------------------------------------------------------------------ the transform
def late_array(close, vol, t, m):
    """Brute force: the BTC (close, volume) arrays the bot holds at decision minute t when its newest m minutes are
    missing (close filled forward from t-1-m, volume 0). close / vol: arrays as the bot holds them with nothing
    missing. Only rows <= t-1 matter to row t; row t itself is left as is."""
    c, v = np.array(close, np.float64, copy=True), np.array(vol, np.float64, copy=True)
    if m > 0:
        c[t - m:t] = np.nan
        v[t - m:t] = 0.0
        c[:t] = pd.Series(c[:t]).ffill(limit=30).to_numpy()
    return c, v


def late_array_fast(close, vol, t, m):
    """The same transform without a fill pass: the tail takes the last close the bot still has."""
    c, v = np.array(close, np.float64, copy=True), np.array(vol, np.float64, copy=True)
    if m > 0:
        c[t - m:t] = c[t - 1 - m]
        v[t - m:t] = 0.0
    return c, v


def base_s4(raw_close, vol, mask):
    """S4's base: the minutes in `mask` are missing from the bot's table and filled forward from the minute before
    (as the bot fills: from the candles it has, limit 30); their volume is 0. raw_close: closes with NaN where no
    candle exists (before any fill)."""
    rc = np.where(mask, np.nan, np.asarray(raw_close, np.float64))
    return pd.Series(rc).ffill(limit=30).to_numpy(), np.where(mask, 0.0, np.asarray(vol, np.float64))


def draw_lags(n, seed, p2=0.3):
    """S3's per-minute lag: 1 with probability 0.7, 2 with probability 0.3, independently (one draw per minute)."""
    return np.where(np.random.default_rng(seed).random(n) < p2, 2, 1).astype(np.int8)


def draw_mask(n, seed, p=0.3):
    """S4's older missing minutes: each minute missing with probability 0.3, drawn once per seed."""
    return np.random.default_rng(seed).random(n) < p


# ------------------------------------------------------------------------------------------------ rolling pieces
def shift(x, n):
    out = np.full(len(x), np.nan)
    if n > 0:
        out[n:] = x[:-n]
    else:
        out[:] = x
    return out


class Part:
    """Rolling count / mean / M2 of a series over windows of w - n minutes (n = 0 .. nmax), each read at any index."""

    def __init__(self, x, w, nmax):
        s = pd.Series(np.asarray(x, np.float64))
        self.p = {}
        for n in range(nmax + 1):
            r = s.rolling(w - n, min_periods=1)
            cnt = r.count().to_numpy()
            mean = r.mean().to_numpy()
            var = r.var().to_numpy()
            m2 = np.where(cnt >= 2, var * (cnt - 1), 0.0)
            self.p[n] = (cnt, np.where(cnt > 0, mean, 0.0), m2)

    def at(self, n, i):
        cnt, mean, m2 = self.p[n]
        ok = i >= 0
        j = np.where(ok, i, 0)
        return np.where(ok, cnt[j], 0.0), np.where(ok, mean[j], 0.0), np.where(ok, m2[j], 0.0)


def merge(cnt, mean, m2, mods):
    """Add the changed values (list of arrays; NaN skipped, as pandas does) to the unchanged part's statistics."""
    cnt, mean, m2 = cnt.astype(np.float64).copy(), mean.copy(), m2.copy()
    for v in mods:
        ok = np.isfinite(v)
        c1 = cnt + ok
        d = np.where(ok, v - mean, 0.0)
        mean = np.where(ok, mean + d / np.where(c1 > 0, c1, 1.0), mean)
        m2 = np.where(ok, m2 + d * (np.where(ok, v, 0.0) - mean), m2)
        cnt = c1
    return cnt, mean, m2


def r_mean(st, minp):
    cnt, mean, _ = st
    return np.where(cnt >= max(minp, 1), mean, np.nan)


def r_std(st, minp):
    cnt, _, m2 = st
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where((cnt >= max(minp, 2)), np.sqrt(np.maximum(m2, 0.0) / (cnt - 1)), np.nan)


def r_var(st, minp):
    cnt, _, m2 = st
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where((cnt >= max(minp, 2)), m2 / (cnt - 1), np.nan)


# ------------------------------------------------------------------------------------------------ true pieces
def rbeta(ri, rb, w):
    """edge.wick._rbeta."""
    a, b = pd.Series(ri), pd.Series(rb)
    mp = min(MINP, w)
    m = lambda s: s.rolling(w, min_periods=mp).mean()  # noqa: E731
    cov = m(a * b) - m(a) * m(b)
    return (cov / b.rolling(w, min_periods=mp).var()).clip(0.0, 3.0).to_numpy()


def rz(x):
    return x / pd.Series(x).rolling(W, min_periods=MINP).std().to_numpy()


class Base:
    """The unchanged part of the window for one BTC base (true or S4): BTC's pieces now, each coin's pieces built on
    demand (`coin_parts`, one coin at a time to bound memory). nmax: the largest lag (2)."""

    def __init__(self, btc_close, btc_vol, coin_lp, coins, wbeta=10080, lookback=60, nmax=2):
        self.coins, self.wbeta, self.L, self.nmax = list(coins), wbeta, lookback, nmax
        self.coin_lp = coin_lp
        lb = np.log(np.asarray(btc_close, np.float64))
        self.lb = lb
        self.r1b = np.diff(lb, prepend=np.nan)
        self.br = {h: lb - shift(lb, h) for h in sorted({5, 15, 60, 240, 1440, lookback})}
        self.P_br = {h: Part(self.br[h], W, nmax) for h in (5, 15, 60)}
        self.P_r1b = {w: Part(self.r1b, w, nmax) for w in sorted({60, W, wbeta})}
        self.P_vb = {w: Part(btc_vol, w, nmax) for w in (15, W)}

    def coin_parts(self, c):
        x = np.asarray(self.coin_lp[c], np.float64)
        r1c = np.diff(x, prepend=np.nan)
        b3 = rbeta(r1c, self.r1b, W)
        b7 = rbeta(r1c, self.r1b, self.wbeta) if self.wbeta != W else b3
        q = dict(x=x, r1c=r1c, P_a={w: Part(r1c, w, 0) for w in sorted({W, self.wbeta})},
                 P_ab={w: Part(r1c * self.r1b, w, self.nmax) for w in sorted({W, self.wbeta})}, zraw={}, P_z={})
        for h in (15, 60):
            z = (x - shift(x, h)) - b3 * self.br[h]
            q["zraw"][h] = z
            q["P_z"][h] = Part(z, W, self.nmax)
        e = (x - shift(x, self.L)) - b7 * self.br[self.L]
        q["P_e"] = Part(e, W, self.nmax)
        return q


def _alts(per, coins, n):
    zs = np.vstack([per[c]["z_res60"] for c in coins])
    for i, c in enumerate(coins):
        oz = np.delete(zs, i, axis=0)
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            per[c]["alts_mean_z60"] = np.nanmean(oz, axis=0) if len(oz) else np.full(n, np.nan)
            per[c]["alts_below_2sd"] = np.nansum(oz < -2, axis=0).astype(float) if len(oz) else np.zeros(n)


def _btc_late(B, t, m):
    u = t - 1
    um = u - m
    lb, lb_um = B.lb, B.lb[um]
    tail = [um + j for j in range(1, m + 1)]
    out = {}
    for h in (5, 15, 60):
        st = merge(*B.P_br[h].at(m, um), [lb_um - lb[p - h] for p in tail])
        with np.errstate(invalid="ignore", divide="ignore"):
            out[f"btc_z{h}"] = (lb_um - lb[u - h]) / r_std(st, MINP)
    out["btc_ret240_bp"] = (lb_um - lb[u - 240]) * 1e4
    out["btc_ret1d_bp"] = (lb_um - lb[u - 1440]) * 1e4
    zeros = [np.zeros(len(t)) for _ in tail]
    with np.errstate(invalid="ignore", divide="ignore"):
        out["btc_vol_ratio"] = (r_std(merge(*B.P_r1b[60].at(m, um), zeros), 60)
                                / r_std(merge(*B.P_r1b[W].at(m, um), zeros), MINP))
        st15 = merge(*B.P_vb[15].at(m, um), zeros)
        sum15 = np.where(st15[0] >= 15, st15[1] * st15[0], np.nan)
        out["btc_volume_ratio_15m"] = sum15 / (r_mean(merge(*B.P_vb[W].at(m, um), zeros), MINP) * 15)
    return out


def _coin_late(B, q, t, m, k):
    u = t - 1
    um = u - m
    lb, lb_um = B.lb, B.lb[um]
    tail = [um + j for j in range(1, m + 1)]
    x, r1c = q["x"], q["r1c"]

    def beta_at(w, n):                    # rolling beta over w minutes ending at um + n (r1b = 0 at the n changed)
        mp = min(MINP, w)
        mod_ab = [np.where(np.isfinite(r1c[um + j]), 0.0, np.nan) for j in range(1, n + 1)]
        m_ab = r_mean(merge(*q["P_ab"][w].at(n, um), mod_ab), mp)
        m_a = r_mean(q["P_a"][w].at(0, um + n), mp)        # the coin's own returns are unchanged
        stb = merge(*B.P_r1b[w].at(n, um), [np.zeros(len(t))] * n)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.clip((m_ab - m_a * r_mean(stb, mp)) / r_var(stb, mp), 0.0, 3.0)

    b3 = [beta_at(W, j + 1) for j in range(m)]
    b7 = [beta_at(B.wbeta, j + 1) for j in range(m)] if B.wbeta != W else b3
    f = {}
    for h in (15, 60):
        mods = [(x[p] - x[p - h]) - b3[j] * (lb_um - lb[p - h]) for j, p in enumerate(tail)]
        st = merge(*q["P_z"][h].at(m, um), mods)
        with np.errstate(invalid="ignore", divide="ignore"):
            f[f"z_res{h}"] = mods[-1] / r_std(st, MINP)
    L = B.L
    mods = [(x[p] - x[p - L]) - b7[j] * (lb_um - lb[p - L]) for j, p in enumerate(tail)]
    sig = r_std(merge(*q["P_e"].at(m, um), mods), MINP)
    beta = b7[-1]
    with np.errstate(invalid="ignore", over="ignore"):
        f["level"] = np.exp(x[t - L] + beta * (lb_um - lb[t - L]) - k * sig)
    f["sig"], f["bid_depth_bp"], f["beta"] = sig, k * sig * 1e4, beta
    return f


def _coin_true(B, q, t, k):
    u = t - 1
    x = q["x"]
    f = {}
    for h in (15, 60):
        with np.errstate(invalid="ignore", divide="ignore"):
            f[f"z_res{h}"] = q["zraw"][h][u] / r_std(q["P_z"][h].at(0, u), MINP)
    sig = r_std(q["P_e"].at(0, u), MINP)
    w = B.wbeta
    mp = min(MINP, w)
    stb = B.P_r1b[w].at(0, u)
    with np.errstate(invalid="ignore", divide="ignore"):
        beta = np.clip((r_mean(q["P_ab"][w].at(0, u), mp) - r_mean(q["P_a"][w].at(0, u), mp) * r_mean(stb, mp))
                       / r_var(stb, mp), 0.0, 3.0)
        f["level"] = np.exp(x[t - B.L] + beta * (B.lb[u] - B.lb[t - B.L]) - k * sig)
    f["sig"], f["bid_depth_bp"], f["beta"] = sig, k * sig * 1e4, beta
    return f


def late_multi(B, rows, ms, k=4.0, coin_hook=None):
    """BTC-dependent values of edge.wick.panel at decision rows t (array) when BTC is m minutes late, for each m in ms
    (0 = nothing late, from the same pieces), on base B. Returns {m: (btc, per)}: btc = {name: array} for the
    BTC-only features; per = {coin: {name: array}} with level (not tick-rounded), sig, beta (7-day) and the coin's
    BTC-dependent features. coin_hook(c, {m: f}) may shrink a coin's arrays as they are made (memory)."""
    t = np.asarray(rows, np.int64)
    res = {}
    for m in ms:
        res[m] = ({}, {})
        if m == 0:
            u = t - 1
            b = res[m][0]
            for h in (5, 15, 60):
                with np.errstate(invalid="ignore", divide="ignore"):
                    b[f"btc_z{h}"] = B.br[h][u] / r_std(B.P_br[h].at(0, u), MINP)
            b["btc_ret240_bp"], b["btc_ret1d_bp"] = B.br[240][u] * 1e4, B.br[1440][u] * 1e4
            with np.errstate(invalid="ignore", divide="ignore"):
                b["btc_vol_ratio"] = r_std(B.P_r1b[60].at(0, u), 60) / r_std(B.P_r1b[W].at(0, u), MINP)
                st15 = B.P_vb[15].at(0, u)
                b["btc_volume_ratio_15m"] = np.where(st15[0] >= 15, st15[1] * st15[0], np.nan) / (
                    r_mean(B.P_vb[W].at(0, u), MINP) * 15)
        else:
            res[m][0].update(_btc_late(B, t, m))
    for c in B.coins:
        q = B.coin_parts(c)
        fs = {m: (_coin_true(B, q, t, k) if m == 0 else _coin_late(B, q, t, m, k)) for m in ms}
        del q
        if coin_hook is not None:
            fs = coin_hook(c, fs)
        for m in ms:
            res[m][1][c] = fs[m]
    for m in ms:
        _alts(res[m][1], B.coins, len(t))
    return res


def late_rows(B, rows, m, k=4.0):
    """late_multi for one lag m >= 1: (btc, per)."""
    return late_multi(B, rows, (m,), k)[m]


def true_rows(B, rows, k=4.0):
    """late_multi with nothing late (m = 0)."""
    return late_multi(B, rows, (0,), k)[0]
