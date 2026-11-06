"""Shared core of the resting-bid dip buyer ("wick catcher"): order levels and AI features.

Research (scripts/wick_*.py) and the live bot (bot/) both call `panel`, so the numbers a model is trained
on are the numbers it sees live. Row t of every output holds only what is known at the end of minute t-1:
it is the decision for minute t (keep a post-only bid at `level` working during minute t, or not).

Inputs are 1-minute Coinbase spot closes (forward-filled up to 30 minutes) and volumes (0 when no trade).
"""
import numpy as np
import pandas as pd

W, MINP = 4320, 1440                 # 3-day trailing window (minutes), 1 day minimum
L, K, THETA, H = 60, 4.0, 0.6, 60     # lookback, bid depth in sigmas, take-profit share of depth, max hold
FEATS = ["z_res60", "z_res15", "z_1min", "bid_depth_bp", "btc_z5", "btc_z15", "btc_z60", "btc_ret240_bp",
         "btc_ret1d_bp", "coin_ret1d_bp", "coin_ret7d_bp", "dist_1d_high_bp", "range_pos240", "vol_ratio_60m_3d",
         "btc_vol_ratio", "volume_ratio_15m", "btc_volume_ratio_15m", "alts_mean_z60", "alts_below_2sd", "beta",
         "hour_utc", "weekend", "coin_id"]
PARAMS = dict(objective="huber", alpha=60.0, learning_rate=0.03, num_leaves=7, min_data_in_leaf=60,
              feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, seed=7)
ROUNDS = 250


def shift(x, n):
    out = np.full(len(x), np.nan)
    if n > 0:
        out[n:] = x[:-n]
    elif n < 0:
        out[:n] = x[-n:]
    else:
        out[:] = x
    return out


def _rstd(x, w=W, minp=MINP):
    return pd.Series(x).rolling(w, min_periods=minp).std().to_numpy()


def _rz(x):
    return x / _rstd(x)


def _rbeta(ri, rb, w=W):
    a, b = pd.Series(ri), pd.Series(rb)
    mp = min(MINP, w)
    m = lambda s: s.rolling(w, min_periods=mp).mean()  # noqa: E731
    cov = m(a * b) - m(a) * m(b)
    return (cov / b.rolling(w, min_periods=mp).var()).clip(0.0, 3.0).to_numpy()


def levels(cf, coins, k=K, lookback=L, wbeta=W):
    """Just the order level and sigma per coin (cheap; used to find candidate fill minutes). wbeta: window
    (minutes) of the BTC beta behind the level (the z-score features keep the 3-day beta)."""
    lpb = np.log(cf["BTC"])
    r1b = np.diff(lpb, prepend=np.nan)
    rb = lpb - shift(lpb, lookback)
    out = {}
    for c in coins:
        x = np.log(cf[c])
        b = _rbeta(np.diff(x, prepend=np.nan), r1b, wbeta)
        sig_now = _rstd((x - shift(x, lookback)) - b * rb)
        out[c] = (np.exp(shift(x, lookback) + shift(b, 1) * (shift(lpb, 1) - shift(lpb, lookback)) - k * shift(sig_now, 1)),
                  shift(sig_now, 1))
    return out


def panel(cf, vol, coins, idx, k=K, lookback=L, coin_codes=None, keep_rows=None, wbeta=W):
    """cf, vol: {coin: np.ndarray} aligned to idx, including "BTC". coins: the alts to trade.
    Returns {coin: DataFrame(index=idx)} with level, sig (residual sigma of `lookback`-minute moves) and FEATS.
    keep_rows: optional {coin: integer positions}; then each frame holds only those rows (saves memory).
    wbeta: window (minutes) of the BTC beta behind level, sig, bid_depth_bp and the beta feature (default 3 days)."""
    lpb = np.log(cf["BTC"])
    r1b = np.diff(lpb, prepend=np.nan)
    btc_r = {h: lpb - shift(lpb, h) for h in sorted({5, 15, 60, 240, 1440, lookback})}
    btc_z = {h: _rz(btc_r[h]) for h in (5, 15, 60)}
    btc_vr = (pd.Series(r1b).rolling(60).std() / pd.Series(r1b).rolling(W, min_periods=MINP).std()).to_numpy()
    vb = pd.Series(vol["BTC"])
    btc_volr = (vb.rolling(15).sum() / (vb.rolling(W, min_periods=MINP).mean() * 15)).to_numpy()
    p = lambda x: shift(x, 1)  # noqa: E731  (value at t-1, placed on row t)
    lp, beta, zres = {}, {}, {}
    for c in coins:
        lp[c] = np.log(cf[c])
        beta[c] = _rbeta(np.diff(lp[c], prepend=np.nan), r1b)          # through t
        for h in (15, 60):
            zres[c, h] = _rz((lp[c] - shift(lp[c], h)) - beta[c] * btc_r[h])
    codes = coin_codes or {c: i for i, c in enumerate(sorted(coins))}
    out = {}
    for c in coins:
        x, b = lp[c], beta[c]
        if wbeta != W:                       # level, sigma and the beta feature from a beta over wbeta minutes
            b = _rbeta(np.diff(x, prepend=np.nan), r1b, wbeta)
        e = (x - shift(x, lookback)) - b * btc_r[lookback]
        sig_now = _rstd(e)
        level = np.exp(shift(x, lookback) + p(b) * (p(lpb) - shift(lpb, lookback)) - k * p(sig_now))
        r1 = np.diff(x, prepend=np.nan)
        v = pd.Series(vol[c])
        s_cf = pd.Series(cf[c])
        hi240, lo240 = s_cf.rolling(240, min_periods=60).max().to_numpy(), s_cf.rolling(240, min_periods=60).min().to_numpy()
        hi1d = s_cf.rolling(1440, min_periods=600).max().to_numpy()
        others = [o for o in coins if o != c]
        oz = np.vstack([zres[o, 60] for o in others]) if others else np.full((1, len(x)), np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            f = {
                "level": level, "sig": p(sig_now),
                "z_res60": p(zres[c, 60]), "z_res15": p(zres[c, 15]), "z_1min": p(_rz(r1)),
                "bid_depth_bp": k * p(sig_now) * 1e4,
                "btc_z5": p(btc_z[5]), "btc_z15": p(btc_z[15]), "btc_z60": p(btc_z[60]),
                "btc_ret240_bp": p(btc_r[240]) * 1e4, "btc_ret1d_bp": p(btc_r[1440]) * 1e4,
                "coin_ret1d_bp": p(x - shift(x, 1440)) * 1e4, "coin_ret7d_bp": p(x - shift(x, 10080)) * 1e4,
                "dist_1d_high_bp": p(np.log(cf[c] / hi1d)) * 1e4,
                "range_pos240": p((cf[c] - lo240) / (hi240 - lo240)),
                "vol_ratio_60m_3d": p((pd.Series(r1).rolling(60).std() / pd.Series(r1).rolling(W, min_periods=MINP).std()).to_numpy()),
                "btc_vol_ratio": p(btc_vr),
                "volume_ratio_15m": p((v.rolling(15).sum() / (v.rolling(W, min_periods=MINP).mean() * 15)).to_numpy()),
                "btc_volume_ratio_15m": p(btc_volr),
                "alts_mean_z60": p(np.nanmean(oz, axis=0)) if others else np.full(len(x), np.nan),
                "alts_below_2sd": p(np.nansum(oz < -2, axis=0).astype(float)) if others else np.zeros(len(x)),
                "beta": p(b),
                "hour_utc": idx.hour.to_numpy().astype(float), "weekend": (idx.dayofweek.to_numpy() >= 5).astype(float),
                "coin_id": np.full(len(x), float(codes[c])),
            }
        if keep_rows is not None:
            r = np.asarray(keep_rows.get(c, []), dtype=np.int64)
            f = {k_: v[r] for k_, v in f.items()}
            df = pd.DataFrame(f, index=idx[r])
            df["pos"] = r
        else:
            df = pd.DataFrame(f, index=idx)
        out[c] = df.astype({k_: np.float32 for k_ in FEATS})          # level and sig stay float64
    return out


def round_down(px, tick):
    return np.floor(px / tick + 1e-9) * tick


def round_up(px, tick):
    return np.ceil(px / tick - 1e-9) * tick
