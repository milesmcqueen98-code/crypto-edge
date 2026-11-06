#!/usr/bin/env python3
"""Practitioner strategies on BTC/ETH (and a top-20 coin rotation), using each author's
published default parameters, not parameters fitted to this data.

  1  Carver EWMAC (Systematic Trading): 6 speeds, vol-normalised forecasts, expanding
     forecast scalars, FDM, 25% vol target, 10% buffering.  Long-only and long/short.
  2  Zarattini-Pagani-Barbon "Catching Crypto Trends" (2025): Donchian ensemble over
     5..360-day lookbacks, midpoint trailing stop, 25% vol target on 90-day vol, 200% cap.
     BTC+ETH, and top-20 coin rotation (monthly universe, >=1y listed, >=$2M volume).
  3  AQR time-series momentum (Moskowitz-Ooi-Pedersen; Hurst-Ooi-Pedersen): 1/3/12-month
     excess-return signs, equal weight, vol-scaled, monthly.  Long-only and long/short.
  4  Clenow core trend (Following the Trend): EMA50/100 filter, 50-day breakout, 3x ATR(100)
     trailing stop, inverse-ATR sizing.  Long-only and long/short.
  5  Antonacci dual momentum: monthly, 12-month relative (BTC vs ETH) + absolute (vs T-bills).
  6  Kaufman adaptive moving average (KAMA 10/2/30) with 0.1-sigma filter.
  7  Moreira-Muir volatility-managed buy & hold (inverse variance, monthly).
  8  Carry (He-Manela-Ross-von Wachter; Carver's carry): long spot / short perp when funding
     beats T-bills; 2023+ only (Hyperliquid data).
  9  Lopez de Prado meta-labeling on the live trend rule: triple-barrier labels, purged
     walk-forward LightGBM, uniqueness weights, AFML bet sizing (and a 0/1 filter version).
 10  Chan mean reversion on ETH/BTC: Kalman-filter hedge ratio (delta 1e-4, Ve 1e-3, +/-sqrt(Q)
     bands), and Bollinger z-score (20 days, enter 1, exit 0).  Standalone and as overlays.
 11  Connors RSI(2) (Short Term Trading Strategies That Work): buy RSI2<10 above SMA200, exit
     above SMA5.  Long-only and long/short.
 12  Liu-Tsyvinski crypto time-series momentum: past-week return, weekly, all 7 weekday phases.
Benchmarks: live rule (BTC>SMA100 -> 50/50 BTC/ETH), BTC buy & hold, 50/50 buy & hold.

Usage: python scripts/book_strategies.py   -> reports/book_results.csv, reports/book_returns.parquet
"""
import os
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import book, ls  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PER = {"dev": ("2019-11-06", "2023-12-31"), "recent": ("2024-01-01", None),
       "early": ("2017-07-01", "2019-11-05"), "full": ("2017-07-01", None)}
A2 = ["BTC", "ETH"]
TARGET = 0.25

close, dvol, ret_all, fund = ls.load()
idx = close.index
px = close[A2].copy()
r2 = px.pct_change(fill_method=None)
rf = book.rf_daily(idx)


def W0(cols=A2):
    return pd.DataFrame(0.0, index=idx, columns=cols)


def monthly_mask(index):
    m = pd.Series(index.month, index=index)
    return (m != m.shift(1)).to_numpy()


def hold_monthly(W):
    """Rebalance only on the first day of each month (carry weights forward)."""
    mask = monthly_mask(W.index)
    out = W.copy()
    out[~mask] = np.nan
    return out.ffill().fillna(0.0)


# ---------------------------------------------------------------- benchmarks
def live_rule():
    up = (px.BTC > px.BTC.rolling(100).mean()).astype(float)
    W = W0()
    W["BTC"], W["ETH"] = 0.5 * up, 0.5 * up
    return W


def buy_hold(weights):
    W = W0()
    for a, w in weights.items():
        W[a] = w * px[a].notna()
    return hold_monthly(W)


# ---------------------------------------------------------------- 1 Carver EWMAC
SPEEDS = [(2, 8), (4, 16), (8, 32), (16, 64), (32, 128), (64, 256)]
FDM6, IDM2 = 1.26, 1.05


def carver_ewmac(long_only=True, cap=1.0):
    vol = pd.DataFrame({a: book.carver_vol(r2[a]) for a in A2})
    raw = {}
    for f, s in SPEEDS:
        d = {}
        for a in A2:
            p = px[a]
            sig_price = p * vol[a] / np.sqrt(365)
            d[a] = (p.ewm(span=f, min_periods=f).mean() - p.ewm(span=s, min_periods=s).mean()) / sig_price
        raw[(f, s)] = pd.DataFrame(d)
    comb = []
    for k, df in raw.items():
        pooled = df.abs().mean(axis=1)
        scal = 10.0 / pooled.expanding(min_periods=365).mean()        # Carver: expanding, pooled
        comb.append(df.mul(scal, axis=0).clip(-20, 20))
    F = (sum(comb) / len(comb) * FDM6).clip(-20, 20)
    if long_only:
        F = F.clip(lower=0)
    unit = IDM2 * 0.5 * TARGET / vol
    ideal = F / 10.0 * unit
    pos = book.buffer_positions(ideal, 0.1 * unit)
    return book.cap_gross(pos.fillna(0.0), cap)


# ---------------------------------------------------------------- 2 Zarattini Donchian ensemble
LOOKS = [5, 10, 20, 30, 60, 90, 150, 250, 360]


def donchian_sub(p, n):
    a = p.to_numpy()
    hi = p.rolling(n).max().shift(1).to_numpy()
    mid = ((p.rolling(n).max() + p.rolling(n).min()) / 2).to_numpy()
    out, inpos, stop = np.zeros(len(a)), False, np.nan
    for i in range(len(a)):
        if np.isnan(a[i]):
            inpos = False
        elif not inpos:
            if not np.isnan(hi[i]) and a[i] > hi[i]:
                inpos, stop = True, mid[i]
        else:
            stop = max(stop, mid[i])
            if a[i] < stop:
                inpos = False
        out[i] = 1.0 if inpos else 0.0
    return pd.Series(out, index=p.index)


def donchian_ensemble(p):
    v90 = p.pct_change(fill_method=None).rolling(90, min_periods=60).std() * np.sqrt(365)
    size = (TARGET / v90).clip(upper=2.0)
    return sum(donchian_sub(p, n) * size for n in LOOKS) / len(LOOKS)


def zpb_btc_eth(cap=1.0):
    W = W0()
    for a in A2:
        W[a] = 0.5 * donchian_ensemble(px[a]).fillna(0.0)
    return book.cap_gross(W, cap)


def zpb_top20(cap=1.0):
    v30 = dvol.rolling(30, min_periods=20).median()
    hist = close.notna().cumsum()
    elig = (hist >= 365) & close.notna() & (v30 >= 2e6)
    rank = v30.where(elig).rank(axis=1, ascending=False)
    member = (rank <= 20)
    mm = monthly_mask(idx)
    memb = member.copy().astype(float)
    memb[~mm] = np.nan
    memb = memb.ffill().fillna(0.0).astype(bool)
    coins = memb.columns[memb.any()]
    W = pd.DataFrame(0.0, index=idx, columns=coins)
    for c in coins:
        W[c] = donchian_ensemble(close[c]).fillna(0.0) / 20.0
    W = W.where(memb[coins], 0.0)
    return book.cap_gross(W, cap)


# ---------------------------------------------------------------- 3 AQR TSMOM
def aqr_tsmom(long_only=True, cap=1.0):
    vol = r2.ewm(com=60, min_periods=60).std() * np.sqrt(365)
    sig = []
    for k in (30, 90, 365):
        ex = px / px.shift(k) - 1 - rf.rolling(k).sum().to_numpy()[:, None]
        sig.append(np.sign(ex))
    S = sum(sig) / 3.0
    if long_only:
        S = S.clip(lower=0)
    W = hold_monthly((S * 0.5 * IDM2 * TARGET / vol).fillna(0.0))
    return book.cap_gross(W, cap)


# ---------------------------------------------------------------- 4 Clenow
def clenow(long_short=False, cap=1.0):
    hlc = book.load_hlc(A2)
    W = W0()
    for a in A2:
        d = hlc[a].reindex(idx)
        c, h, l = d.close, d.high, d.low
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(100, min_periods=60).mean()
        e50, e100 = c.ewm(span=50).mean(), c.ewm(span=100).mean()
        hi50, lo50 = c.rolling(50).max().shift(1), c.rolling(50).min().shift(1)
        sig_ann = (atr / c) / 1.6 * np.sqrt(365)
        pos, state, ext, size = np.zeros(len(idx)), 0, np.nan, 0.0
        ca, aa = c.to_numpy(), atr.to_numpy()
        for i in range(len(idx)):
            if np.isnan(ca[i]) or np.isnan(aa[i]):
                state = 0
            elif state == 0:
                if e50.iat[i] > e100.iat[i] and ca[i] >= hi50.iat[i]:
                    state, ext, size = 1, ca[i], 0.5 * TARGET / sig_ann.iat[i]
                elif long_short and e50.iat[i] < e100.iat[i] and ca[i] <= lo50.iat[i]:
                    state, ext, size = -1, ca[i], 0.5 * TARGET / sig_ann.iat[i]
            elif state == 1:
                ext = max(ext, ca[i])
                if ca[i] < ext - 3 * aa[i]:
                    state = 0
            elif state == -1:
                ext = min(ext, ca[i])
                if ca[i] > ext + 3 * aa[i]:
                    state = 0
            pos[i] = state * size
        W[a] = pos
    return book.cap_gross(W, cap)


# ---------------------------------------------------------------- 5 Antonacci dual momentum
def antonacci():
    r12 = px / px.shift(365) - 1
    rf12 = rf.rolling(365).sum()
    W = W0()
    best = r12.dropna(how="all").idxmax(axis=1).reindex(idx)
    for d in idx[monthly_mask(idx)]:
        b = best.get(d)
        if isinstance(b, str) and r12.at[d, b] > rf12.get(d, 0):
            W.loc[d, b] = 1.0
    mask = monthly_mask(idx)
    W[~mask] = np.nan
    return W.ffill().fillna(0.0)


# ---------------------------------------------------------------- 6 Kaufman KAMA
def kaufman_kama():
    W = W0()
    for a in A2:
        p = px[a]
        er = (p - p.shift(10)).abs() / p.diff().abs().rolling(10).sum()
        sc = (er * (2 / 3 - 2 / 31) + 2 / 31) ** 2
        k = np.full(len(p), np.nan)
        pa, sa = p.to_numpy(), sc.to_numpy()
        for i in range(len(p)):
            if np.isnan(pa[i]):
                continue
            if np.isnan(k[i - 1]) if i else True:
                k[i] = pa[i]
            elif np.isnan(sa[i]):
                k[i] = k[i - 1]
            else:
                k[i] = k[i - 1] + sa[i] * (pa[i] - k[i - 1])
        kama = pd.Series(k, index=p.index)
        dk = kama.diff()
        filt = 0.1 * dk.rolling(20).std()
        state, out = 0.0, np.zeros(len(p))
        for i in range(len(p)):
            if np.isnan(dk.iat[i]) or np.isnan(filt.iat[i]):
                state = 0.0
            elif dk.iat[i] > filt.iat[i]:
                state = 1.0
            elif dk.iat[i] < -filt.iat[i]:
                state = 0.0
            out[i] = state
        W[a] = 0.5 * out
    return W


# ---------------------------------------------------------------- 7 Moreira-Muir
def moreira_muir(cap=1.0):
    rv = r2.rolling(30, min_periods=20).var() * 365
    med = rv.expanding(min_periods=180).median()
    w = (med / rv).clip(upper=cap) * 0.5
    return book.cap_gross(hold_monthly(w.fillna(0.0)), cap)


# ---------------------------------------------------------------- 8 Carry (cash & carry)
def carry_returns():
    """Daily excess return of long spot / short perp on BTC+ETH, sized to 1/1.3 of capital
    (30% kept as perp margin). Enter when the 7-day average funding (annualised) exceeds
    T-bills + 2%, exit when it falls below T-bills. Basis P&L from Hyperliquid perp closes."""
    perps = book.load_perps()
    f = fund[A2].dropna(how="all")
    if f.empty:
        return None, None
    start = f.index.min() + pd.Timedelta(days=8)
    out, info = [], {}
    for a in A2:
        fa = fund[a].reindex(idx)
        f7 = fa.rolling(7, min_periods=5).mean() * 365
        st, state = np.zeros(len(idx)), 0.0
        for i in range(len(idx)):
            if np.isnan(f7.iat[i]):
                state = 0.0
            elif f7.iat[i] > rf.iat[i] * 365 + 0.02:
                state = 1.0
            elif f7.iat[i] < rf.iat[i] * 365:
                state = 0.0
            st[i] = state
        held = pd.Series(st, index=idx).shift(1).fillna(0.0)
        spot = r2[a].fillna(0.0)
        if a in perps:
            perp = perps[a].reindex(idx).pct_change(fill_method=None)
            basis = (spot - perp).where(perp.notna(), 0.0)
            info[a] = f"basis from perp closes ({perps[a].dropna().index.min().date()}+)"
        else:
            basis = 0.0 * spot
            info[a] = "no perp prices: basis P&L ignored (Sharpe overstated)"
        tc = pd.Series(st, index=idx).diff().abs().fillna(0.0) * 2 * ls.COST
        gross = held * (basis + fa.fillna(0.0)) - tc
        out.append(gross / 1.3 * 0.5)
    r = sum(out)
    deployed = sum(pd.Series(0.5, index=idx) * 0 for _ in A2)
    # undeployed capital earns T-bills; deployed capital does not (spot + margin)
    used = sum((pd.Series(np.where(o != 0, 0.5, 0.0), index=idx)) for o in out)
    exc = r + (1 - used).clip(lower=0) * rf - rf
    return exc.loc[start:], info


# ---------------------------------------------------------------- 9 Lopez de Prado meta-labeling
def meta_labeling(filter_only=False, h=20, pt_sl=1.0, embargo=5):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from research_timing import timing_features  # noqa: E402
    from edge import data as edata  # noqa: E402
    c_, d_, r_ = edata.load()
    X = timing_features(c_, d_, r_).drop(columns=["fwd7"])
    up = (px.BTC > px.BTC.rolling(100).mean())
    flips = (up != up.shift()).cumsum()
    days_in = up.groupby(flips).cumcount()
    sma100 = px.BTC.rolling(100).mean()
    rows = []
    for a in A2:
        p = px[a]
        dv = p.pct_change(fill_method=None).ewm(span=100, min_periods=50).std()
        barrier = pt_sl * dv * np.sqrt(h)
        pa, ba = p.to_numpy(), barrier.to_numpy()
        lab, end = np.full(len(p), np.nan), np.full(len(p), np.nan)
        for i in range(len(p) - 1):
            if np.isnan(pa[i]) or np.isnan(ba[i]):
                continue
            j_end = min(i + h, len(p) - 1)
            path = pa[i + 1:j_end + 1] / pa[i] - 1
            if len(path) == 0:
                continue
            hit_u = np.where(path >= ba[i])[0]
            hit_d = np.where(path <= -ba[i])[0]
            tu = hit_u[0] if len(hit_u) else 10**9
            td = hit_d[0] if len(hit_d) else 10**9
            if tu == td == 10**9:
                if i + h > len(p) - 1:
                    continue  # vertical barrier not reached yet
                lab[i], end[i] = float(path[-1] > 0), i + h
            elif tu < td:
                lab[i], end[i] = 1.0, i + 1 + tu
            else:
                lab[i], end[i] = 0.0, i + 1 + td
        df = pd.DataFrame({"date": idx, "asset": a, "label": lab, "end_i": end, "i": np.arange(len(idx)),
                           "primary": up.to_numpy(), "days_in": days_in.to_numpy(),
                           "z_sma100": ((px.BTC - sma100) / (px.BTC * dv)).to_numpy()})
        rows.append(df)
    L = pd.concat(rows).merge(X, on=["date", "asset"], how="left")
    L = L[L.primary]
    # uniqueness weights (AFML ch.4): average 1/concurrency over each label's span
    conc = np.zeros(len(idx) + h + 2)
    for a in A2:
        la = L[(L.asset == a) & L.label.notna()]
        for s, e in zip(la.i.astype(int), la.end_i.astype(int)):
            conc[s:e + 1] += 1
    L["w"] = [np.mean(1.0 / np.maximum(conc[int(s):int(e) + 1], 1)) if not np.isnan(e) else np.nan
              for s, e in zip(L.i, L.end_i)]
    feats = [c for c in L.columns if c not in ("date", "asset", "label", "end_i", "i", "primary", "w")]
    params = dict(objective="binary", learning_rate=0.03, num_leaves=7, min_data_in_leaf=100,
                  feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10.0,
                  n_estimators=200, verbose=-1, seed=7, num_threads=2)
    preds = []
    for t0 in pd.date_range("2019-01-01", idx[-1], freq="QS"):
        t1 = t0 + pd.offsets.QuarterBegin(1)
        i0 = idx.get_indexer([t0], method="bfill")[0]
        tr = L[L.label.notna() & (L.end_i < i0 - embargo)]          # purge: label must end before test
        te = L[(L.date >= t0) & (L.date < t1)]
        if len(tr) < 300 or te.empty:
            continue
        m = lgb.LGBMClassifier(**params).fit(tr[feats], tr.label.astype(int), sample_weight=tr.w)
        preds.append(te[["date", "asset"]].assign(p=m.predict_proba(te[feats])[:, 1]))
    P = pd.concat(preds).pivot(index="date", columns="asset", values="p").reindex(idx)
    if filter_only:
        size = (P > 0.5).astype(float)
    else:
        z = (P - 0.5) / np.sqrt(P * (1 - P))
        size = pd.DataFrame(2 * norm.cdf(z) - 1, index=P.index, columns=P.columns).clip(lower=0)
        size = (size / 0.1).round() * 0.1                            # AFML: discretise bet sizes
    W = W0()
    for a in A2:
        W[a] = 0.5 * size[a].fillna(0.0) * up.astype(float)
    W.loc[:"2018-12-31"] = 0.0
    return W


# ---------------------------------------------------------------- 10 Chan mean reversion on ETH/BTC
def chan_kalman():
    y, x = np.log(px.ETH), np.log(px.BTC)
    delta, Ve = 1e-4, 1e-3
    Vw = delta / (1 - delta) * np.eye(2)
    theta, P = np.zeros(2), np.zeros((2, 2))
    e_, q_, b_ = (np.full(len(idx), np.nan) for _ in range(3))
    started = False
    for i in range(len(idx)):
        if np.isnan(y.iat[i]) or np.isnan(x.iat[i]):
            continue
        F = np.array([x.iat[i], 1.0])
        if not started:
            started = True
        R = P + Vw
        yhat = F @ theta
        Q = F @ R @ F + Ve
        e = y.iat[i] - yhat
        K = R @ F / Q
        theta = theta + K * e
        P = R - np.outer(K, F) @ R
        e_[i], q_[i], b_[i] = e, np.sqrt(Q), theta[0]
    e, sq, beta = pd.Series(e_, index=idx), pd.Series(q_, index=idx), pd.Series(b_, index=idx)
    state, pos = 0, np.zeros(len(idx))
    for i in range(len(idx)):
        if np.isnan(e.iat[i]) or i < 365:          # one year burn-in for the filter
            state = 0
        elif state == 0:
            state = 1 if e.iat[i] < -sq.iat[i] else (-1 if e.iat[i] > sq.iat[i] else 0)
        elif state == 1 and e.iat[i] > -sq.iat[i]:
            state = 0
        elif state == -1 and e.iat[i] < sq.iat[i]:
            state = 0
        pos[i] = state
    pos = pd.Series(pos, index=idx)
    bb = beta.clip(0.2, 3.0)
    W = W0()
    W["ETH"], W["BTC"] = pos / (1 + bb), -pos * bb / (1 + bb)
    return W.fillna(0.0)


def chan_bollinger():
    x = np.log(px.ETH / px.BTC)
    z = (x - x.rolling(20).mean()) / x.rolling(20).std()
    state, pos = 0, np.zeros(len(idx))
    for i in range(len(idx)):
        zi = z.iat[i]
        if np.isnan(zi):
            state = 0
        elif state == 0:
            state = 1 if zi < -1 else (-1 if zi > 1 else 0)
        elif state == 1 and zi >= 0:
            state = 0
        elif state == -1 and zi <= 0:
            state = 0
        pos[i] = state
    W = W0()
    W["ETH"], W["BTC"] = 0.5 * pos, -0.5 * pos
    return W


# ---------------------------------------------------------------- 11 Connors RSI(2)
def rsi(p, n=2):
    d = p.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    ru = up.ewm(alpha=1 / n, adjust=False).mean()
    rd = dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + ru / rd)


def connors(long_short=False):
    W = W0()
    for a in A2:
        p = px[a]
        r_, s200, s5 = rsi(p), p.rolling(200).mean(), p.rolling(5).mean()
        state, out = 0, np.zeros(len(p))
        for i in range(len(p)):
            if np.isnan(s200.iat[i]):
                state = 0
            elif state == 0:
                if p.iat[i] > s200.iat[i] and r_.iat[i] < 10:
                    state = 1
                elif long_short and p.iat[i] < s200.iat[i] and r_.iat[i] > 90:
                    state = -1
            elif state == 1 and p.iat[i] > s5.iat[i]:
                state = 0
            elif state == -1 and p.iat[i] < s5.iat[i]:
                state = 0
            out[i] = state
        W[a] = 0.5 * out
    return W


# ---------------------------------------------------------------- 12 Liu-Tsyvinski weekly TSMOM
def liu_tsyvinski(long_short=False):
    r7 = px / px.shift(7) - 1
    sig = np.sign(r7)
    if not long_short:
        sig = sig.clip(lower=0)
    phases = []
    for ph in range(7):
        Wp = (0.5 * sig).copy()
        keep = np.zeros(len(idx), dtype=bool)
        keep[ph::7] = True
        Wp[~keep] = np.nan
        phases.append(Wp.ffill().fillna(0.0))
    return sum(phases) / 7.0


# ---------------------------------------------------------------- evaluation
def evaluate(name, x, group, note=""):
    row = {"strategy": name, "group": group, "note": note}
    for p, (s, e) in PER.items():
        st = book.summary(x, s, e)
        row |= {f"{p}_{k}": v for k, v in st.items()}
    return row


def main():
    strategies = {
        ("Benchmark", "Live rule: BTC>SMA100, 50/50 BTC/ETH"): live_rule,
        ("Benchmark", "BTC buy & hold"): lambda: buy_hold({"BTC": 1.0}),
        ("Benchmark", "50/50 BTC/ETH buy & hold"): lambda: buy_hold({"BTC": 0.5, "ETH": 0.5}),
        ("1 Carver", "EWMAC 6-speed, long-only, spot (1x cap)"): lambda: carver_ewmac(True, 1.0),
        ("1 Carver", "EWMAC 6-speed, long/short, futures (2x cap)"): lambda: carver_ewmac(False, 2.0),
        ("2 Zarattini", "Donchian ensemble BTC+ETH, spot (1x)"): lambda: zpb_btc_eth(1.0),
        ("2 Zarattini", "Donchian ensemble BTC+ETH, 2x cap"): lambda: zpb_btc_eth(2.0),
        ("2 Zarattini", "Donchian ensemble top-20 coins, spot (1x)"): lambda: zpb_top20(1.0),
        ("3 AQR", "TSMOM 1/3/12m, long-only (1x)"): lambda: aqr_tsmom(True, 1.0),
        ("3 AQR", "TSMOM 1/3/12m, long/short (2x)"): lambda: aqr_tsmom(False, 2.0),
        ("4 Clenow", "Core trend, long-only (1x)"): lambda: clenow(False, 1.0),
        ("4 Clenow", "Core trend, long/short (2x)"): lambda: clenow(True, 2.0),
        ("5 Antonacci", "Dual momentum BTC/ETH/T-bills"): antonacci,
        ("6 Kaufman", "KAMA 10/2/30 with filter"): kaufman_kama,
        ("7 Moreira-Muir", "Vol-managed buy & hold (1x)"): lambda: moreira_muir(1.0),
        ("7 Moreira-Muir", "Vol-managed buy & hold (2x)"): lambda: moreira_muir(2.0),
        ("9 Lopez de Prado", "Meta-labeled live rule, AFML bet sizing"): lambda: meta_labeling(False),
        ("9 Lopez de Prado", "Meta-labeled live rule, 0/1 filter"): lambda: meta_labeling(True),
        ("10 Chan", "Kalman ETH/BTC pair (market-neutral)"): chan_kalman,
        ("10 Chan", "Bollinger ETH/BTC pair (market-neutral)"): chan_bollinger,
        ("11 Connors", "RSI(2) long-only"): lambda: connors(False),
        ("11 Connors", "RSI(2) long/short"): lambda: connors(True),
        ("12 Liu-Tsyvinski", "Weekly TSMOM long-only"): lambda: liu_tsyvinski(False),
        ("12 Liu-Tsyvinski", "Weekly TSMOM long/short"): lambda: liu_tsyvinski(True),
    }
    rows, streams, weights = [], {}, {}
    for (group, name), fn in strategies.items():
        W = fn()
        x = book.excess_returns(W)
        x = x.where(W.abs().sum(axis=1).cumsum().shift(1).fillna(0) > 0)  # start when it first trades
        if name.startswith("BTC buy") or name.startswith("50/50"):
            x = book.excess_returns(W)
        streams[name] = x
        weights[name] = W
        turnover = W.diff().abs().sum(axis=1).loc["2019-11-06":].mean() * 365
        rows.append(evaluate(name, x, group, f"turnover {turnover:.1f}x/yr"))
        print(f"done: {name}", flush=True)
    cx, info = carry_returns()
    if cx is not None:
        streams["Cash & carry BTC+ETH (2023+)"] = cx
        rows.append(evaluate("Cash & carry BTC+ETH (2023+)", cx, "8 Carry", "; ".join(f"{k}: {v}" for k, v in info.items())))
    # overlays (Chan pair at half size on top of the live rule)
    live = weights["Live rule: BTC>SMA100, 50/50 BTC/ETH"]
    for nm in ("Kalman ETH/BTC pair (market-neutral)", "Bollinger ETH/BTC pair (market-neutral)"):
        x = book.excess_returns(live + 0.5 * weights[nm])
        nm2 = f"Live rule + 0.5x {nm.split(' (')[0]}"
        streams[nm2] = x
        rows.append(evaluate(nm2, x, "10 Chan"))
    df = pd.DataFrame(rows)
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    df.to_csv(os.path.join(ROOT, "reports", "book_results.csv"), index=False)
    pd.DataFrame(streams).to_parquet(os.path.join(ROOT, "reports", "book_returns.parquet"))
    pd.set_option("display.width", 250)
    show = df[["group", "strategy", "dev_sharpe", "recent_sharpe", "early_sharpe", "full_sharpe",
               "full_cagr", "full_maxdd", "note"]].copy()
    for c in ["dev_sharpe", "recent_sharpe", "early_sharpe", "full_sharpe"]:
        show[c] = show[c].map(lambda v: f"{v:.2f}" if v == v else "—")
    show["full_cagr"] = show["full_cagr"].map(lambda v: f"{v:.0%}" if v == v else "—")
    show["full_maxdd"] = show["full_maxdd"].map(lambda v: f"{v:.0%}" if v == v else "—")
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
