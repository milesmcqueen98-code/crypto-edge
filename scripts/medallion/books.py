#!/usr/bin/env python3
"""Medallion round books F2, F3, F5, F6, F7, F9 (F10 is in onemodel.py). One fixed specification each, from
reports/medallion_prereg.md. Writes reports/medallion/books.csv and books_returns.parquet.

  python scripts/medallion/books.py            development period only
  MEDALLION_HOLDOUT=1 python ...               adds the hold-out (opened once)
"""
import sys
import warnings
from itertools import combinations

import numpy as np
import pandas as pd

from common import (COINS, DEV, DEV_H, HOLD, HOLDOUT_OPEN, HOURLY, TARGET, binance_funding_raw, cost_per_side,
                    daily_close, funding_daily, hourly_close, run_daily, run_hourly, save, stats, vol_unit)
from features import binance_metrics, dvol

warnings.filterwarnings("ignore")


# ------------------------------------------------------------------------------------------------ F2 HMM
def forward_filter(x, pi, A, mu, sd):
    T = len(x)
    out = np.empty((T, 2))
    a = None
    for t in range(T):
        b = np.exp(-0.5 * ((x[t] - mu) / sd) ** 2) / sd
        a = pi * b if a is None else (a @ A) * b
        s = a.sum()
        a = a / s if s > 0 else np.full(2, 0.5)
        out[t] = a
    return out


def hmm_prob(coin):
    """Filtered probability of the higher-mean state, refit monthly on all prior data (min 2 years)."""
    from hmmlearn.hmm import GaussianHMM
    close = daily_close([coin])[coin].dropna()
    x = (np.log(close).diff().dropna() * 100.0)
    prob = pd.Series(np.nan, index=x.index)
    first = x.index[0] + pd.Timedelta(days=730)
    for m in pd.date_range(first.to_period("M").to_timestamp() + pd.offsets.MonthBegin(1), x.index[-1], freq="MS"):
        train = x.loc[: m - pd.Timedelta(days=1)].to_numpy().reshape(-1, 1)
        hm = GaussianHMM(n_components=2, covariance_type="diag", n_iter=200, random_state=0)
        hm.fit(train)
        mu = hm.means_.ravel()
        sd = np.sqrt(hm.covars_.ravel())
        hi = int(np.argmax(mu))
        seq = x.loc[: m + pd.offsets.MonthEnd(0)]
        f = forward_filter(seq.to_numpy(), hm.startprob_, hm.transmat_, mu, sd)
        sel = seq.index >= m
        prob.loc[seq.index[sel]] = f[sel, hi]
    return prob


def f2_books():
    out = {}
    for coin in ("BTC", "ETH"):
        close = daily_close([coin])
        p = hmm_prob(coin).reindex(close.index)
        up = (p > 0.5).astype(float).where(p.notna(), 0.0)
        lf = pd.DataFrame({coin: up})
        ls = pd.DataFrame({coin: (2 * up - 1).where(p.notna(), 0.0)})
        out[f"F2_hmm_{coin}_longflat"] = run_daily(lf, close)
        out[f"F2_hmm_{coin}_longshort"] = run_daily(ls, close)
    return out


# ------------------------------------------------------------------------------------------------ F3 kNN
def knn_pred(coin, k=50, min_train=365):
    close = daily_close([coin])[coin].dropna()
    r = close.pct_change()
    F = pd.DataFrame({f"r{n}": close / close.shift(n) - 1 for n in (1, 2, 3, 5, 10, 20)})
    F["vol20"] = r.rolling(20).std()
    F = F.dropna()
    y = r.shift(-1).reindex(F.index)                      # next-day return of each feature row
    X = F.to_numpy()
    Y = y.to_numpy()
    pred = pd.Series(np.nan, index=F.index)
    for i in range(min_train + 1, len(F)):
        hist = X[: i + 1]
        m, s = hist.mean(axis=0), hist.std(axis=0)
        Zh = (X[:i] - m) / s                               # rows whose next-day return is known at row i
        zt = (X[i] - m) / s
        d = ((Zh - zt) ** 2).sum(axis=1)
        nn = np.argpartition(d, k)[:k]
        pred.iloc[i] = Y[:i][nn].mean()
    return pred


def f3_books():
    out = {}
    for coin in ("BTC", "ETH"):
        close = daily_close([coin])
        pred = knn_pred(coin).reindex(close.index)
        unit = vol_unit(close)[coin]
        W = pd.DataFrame({coin: (np.sign(pred) * unit).fillna(0.0).clip(-2, 2)})
        out[f"F3_knn_{coin}"] = run_daily(W, close)
    return out


# ------------------------------------------------------------------------------------------------ F5 seasonality
def f5_books():
    out = {}
    ch = hourly_close(HOURLY)
    r = ch.pct_change(fill_method=None)
    idx = ch.index
    cost = pd.Series({c: cost_per_side(c) for c in HOURLY})
    n_act = ch.notna().sum(axis=1).replace(0, np.nan)
    # (a) hour of week: trailing 52-week mean of the same hour-of-week, hold when |mean| > 2 x one-way cost
    how = pd.Series(idx.dayofweek * 24 + idx.hour, index=idx)
    m = r.groupby(how).transform(lambda s: s.shift(1).rolling(52, min_periods=52).mean())
    D = np.sign(m).where(m.abs().gt(2 * cost, axis=1), 0.0).fillna(0.0).div(n_act, axis=0).fillna(0.0)
    out["F5a_hour_of_week"] = run_hourly(D.shift(-1).fillna(0.0), ch)
    # (b) day of week: trailing 104-week mean by weekday, daily long/short
    cd = daily_close(HOURLY)
    rd = cd.pct_change(fill_method=None)
    dow = pd.Series(cd.index.dayofweek, index=cd.index)
    md = rd.groupby(dow).transform(lambda s: s.shift(1).rolling(104, min_periods=104).mean())
    nd = cd.notna().sum(axis=1).replace(0, np.nan)
    Dd = np.sign(md).fillna(0.0).div(nd, axis=0).fillna(0.0)
    out["F5b_day_of_week"] = run_daily(Dd.shift(-1).fillna(0.0), cd)
    # (c) weekend / CME gap: fade the Fri 21:00 -> Sun 23:00 UTC move from Sun 23:00 to Mon 21:00 UTC
    c2 = ch[["BTC", "ETH"]]
    Dc = pd.DataFrame(0.0, index=idx, columns=["BTC", "ETH"])
    fri = idx[(idx.dayofweek == 4) & (idx.hour == 20)]                # bar closing at Fri 21:00
    for t in fri:
        sun = t + pd.Timedelta(hours=50)                              # Sun 22:00 bar closes at 23:00
        if sun not in c2.index:
            continue
        move = c2.loc[sun] / c2.loc[t] - 1
        hold = pd.date_range(sun + pd.Timedelta(hours=1), sun + pd.Timedelta(hours=22), freq="h")
        hold = hold[hold.isin(idx)]
        Dc.loc[hold] = (-np.sign(move) * 0.5).fillna(0.0).to_numpy()
    out["F5c_weekend_gap"] = run_hourly(Dc.shift(-1).fillna(0.0), c2)
    # (d) funding hours: hour into 00/08/16 UTC = -sign(last funding print), the hour after = +sign
    Dfh = pd.DataFrame(0.0, index=idx, columns=HOURLY)
    for c in HOURLY:
        f = binance_funding_raw(c)
        if f is None:
            continue
        f = f.copy()
        f.index = f.index.floor("h")
        f = f.groupby(level=0).last()
        last = f.reindex(idx, method="ffill")                         # last print at or before each bar start
        into = idx.hour.isin([23, 7, 15])
        after = idx.hour.isin([0, 8, 16])
        sg = np.sign(last)
        sg_into = sg.to_numpy()
        # the 'after' bar uses the same print as the bar before it (the print that just settled is not used)
        sg_after = sg.shift(1).to_numpy()
        Dfh.loc[into, c] = -sg_into[into]
        Dfh.loc[after, c] = sg_after[after]
    Dfh = Dfh.where(ch.notna(), 0.0).div(n_act, axis=0).fillna(0.0)
    out["F5d_funding_hours"] = run_hourly(Dfh.shift(-1).fillna(0.0), ch)
    return out


# ------------------------------------------------------------------------------------------------ F6 pairs
def pair_positions(z, entry=2.0, exit_=0.5, max_days=20):
    pos = np.zeros(len(z))
    p, held = 0.0, 0
    for i, v in enumerate(z):
        if np.isnan(v):
            p, held = 0.0, 0
        elif p != 0:
            held += 1
            if abs(v) < exit_ or held >= max_days:
                p, held = 0.0, 0
        elif v > entry:
            p, held = -1.0, 0
        elif v < -entry:
            p, held = 1.0, 0
        pos[i] = p
    pos[-1] = 0.0                                                     # close at the end of the trading month
    return pos


def f6_book():
    from statsmodels.tsa.stattools import coint
    close = daily_close(COINS)
    lp = np.log(close)
    r = close.pct_change(fill_method=None)
    W = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    n_sel = {}
    for m in pd.date_range("2018-01-01", close.index[-1], freq="MS"):
        form = lp.loc[m - pd.Timedelta(days=365): m - pd.Timedelta(days=1)]
        tr = lp.loc[m: m + pd.offsets.MonthEnd(0)]
        if len(form) < 360 or len(tr) < 2:
            continue
        avail = sorted(c for c in close.columns if form[c].notna().sum() >= 360 and tr[c].notna().all())
        n_sel[m] = 0
        for a, b in combinations(avail, 2):
            f = form[[a, b]].dropna()
            p = coint(f[a], f[b])[1]
            if not p < 0.05:
                continue
            beta, alpha = np.polyfit(f[b], f[a], 1)
            s = f[a] - alpha - beta * f[b]
            mu, sd = s.mean(), s.std()
            ds = (r[a] - beta * r[b]).loc[f.index].std() * np.sqrt(365)
            if not (sd > 0 and ds > 0):
                continue
            k = 0.10 / ds
            z = ((tr[a] - alpha - beta * tr[b]) - mu) / sd
            pos = pair_positions(z.to_numpy())
            W.loc[tr.index, a] += pos * k
            W.loc[tr.index, b] += -pos * k * beta
            n_sel[m] += 1
    g = W.abs().sum(axis=1)
    W = W.mul((4.0 / g).where(g > 4.0, 1.0), axis=0)
    out = {"F6_pairs": run_daily(W, close)}
    return out, pd.Series(n_sel)


# ------------------------------------------------------------------------------------------------ F7 factor book
def xs_z(df, univ):
    x = df.where(univ)
    z = x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0).clip(-3, 3)
    return z.where(univ).fillna(0.0).where(univ)


def neutral_weights(score, beta, univ):
    W = pd.DataFrame(0.0, index=score.index, columns=score.columns)
    for t in score.index:
        u = univ.loc[t].to_numpy()
        if u.sum() < 5:
            continue
        s = score.loc[t].to_numpy()[u]
        X = np.column_stack([np.ones(u.sum()), beta.loc[t].to_numpy()[u]])
        w = s - X @ np.linalg.lstsq(X, s, rcond=None)[0]
        g = np.abs(w).sum()
        if g > 0:
            W.loc[t, score.columns[u]] = w / g
    return W


def xs_ic(sig, fwd, univ, start, end):
    a = sig.where(univ).loc[start:end]
    b = fwd.where(univ).loc[start:end]
    ics = a.rank(axis=1).corrwith(b.rank(axis=1), axis=1)
    return ics.dropna()


def f7_inputs():
    close = daily_close(COINS)
    r = close.pct_change(fill_method=None)
    rb = r["BTC"]
    cov = r.rolling(90, min_periods=60).cov(rb)
    beta = cov.div(rb.rolling(90, min_periods=60).var(), axis=0)
    beta["BTC"] = 1.0
    resid = r.sub(beta.mul(rb, axis=0))
    resid["BTC"] = 0.0
    fund = {}
    for c in COINS:
        f = binance_funding_raw(c)
        if f is not None:
            fund[c] = f.groupby(f.index.floor("D")).mean()
    fund = pd.DataFrame(fund).reindex(close.index)[[c for c in COINS if c in fund]]
    fund = fund.reindex(columns=close.columns)
    oi = {}
    for c in COINS:
        m = binance_metrics(c)
        if m is not None:
            o = m["sum_open_interest"].groupby(m.index.floor("D")).last()
            oi[c] = np.log(o / o.shift(7))
    oi = pd.DataFrame(oi).reindex(close.index).reindex(columns=close.columns)
    univ = close.notna() & close.shift(30).notna() & beta.notna() & fund.notna()
    sig = {"rev1": -resid, "mom7": close / close.shift(7) - 1, "mom30": close / close.shift(30) - 1,
           "carry": -fund, "oi7": oi}
    fwd = close.shift(-1) / close - 1
    return close, beta, univ, sig, fwd


def f7_books():
    close, beta, univ, sig, fwd = f7_inputs()
    ics = {}
    Z = {}
    for k, s in sig.items():
        ics[k] = xs_ic(s, fwd, univ & s.notna(), *DEV)
        Z[k] = xs_z(s, univ & s.notna()).reindex_like(close).where(univ, np.nan).fillna(0.0)
    signs = {k: float(np.sign(v.mean())) for k, v in ics.items()}
    score = sum(signs[k] * Z[k] for k in sig) / len(sig)
    W = neutral_weights(score.where(univ), beta, univ)
    Wc = neutral_weights(Z["carry"].where(univ), beta, univ)
    out = {"F7_factor": run_daily(W, close), "F7_carry": run_daily(Wc, close)}
    ic_tab = pd.DataFrame({k: dict(ic_dev=v.mean(), t_dev=v.mean() / v.std() * np.sqrt(len(v)), days=len(v),
                                   sign=signs[k]) for k, v in ics.items()}).T
    return out, ic_tab


# ------------------------------------------------------------------------------------------------ F9 short vol
def f9_books():
    out = {}
    for coin in ("BTC", "ETH"):
        close = daily_close([coin])[coin]
        dv = dvol(coin).reindex(close.index)
        r = np.log(close).diff()
        pnl = ((dv.shift(1) - 1.0) / 100.0) ** 2 / 365.0 - r ** 2
        pnl = pnl.dropna()
        k = 0.20 / (pnl.loc[DEV[0]:DEV[1]].std() * np.sqrt(365))
        x = k * pnl
        out[f"F9_short_vol_{coin}"] = (x, pd.Series(0.0, index=x.index))
    return out


def main():
    which = sys.argv[1:] or ["F2", "F3", "F5", "F6", "F7", "F9"]
    res, extra = {}, {}
    if "F2" in which:
        res.update(f2_books())
    if "F3" in which:
        res.update(f3_books())
    if "F5" in which:
        res.update(f5_books())
    if "F6" in which:
        o, nsel = f6_book()
        res.update(o)
        extra["F6_pairs"] = dict(pairs_per_month=float(nsel.mean()))
        save(nsel.rename("pairs").reset_index(), "f6_pairs_per_month.csv")
    if "F7" in which:
        o, ic_tab = f7_books()
        res.update(o)
        save(ic_tab.reset_index().rename(columns={"index": "signal"}), "f7_signal_ics.csv")
        print(ic_tab)
    if "F9" in which:
        res.update(f9_books())
    rows = []
    for name, (x, turn) in res.items():
        dev = DEV_H if name.startswith("F5") else DEV
        e = dict(turnover_per_year=float(turn.loc[dev[0]:dev[1]].mean() * 365))
        e.update(extra.get(name, {}))
        rows.append(stats(name, x, e, dev=dev))
    df = pd.DataFrame(rows)
    tag = "_".join(which)
    save(df, f"books_{tag}.csv")
    R = pd.DataFrame({k: v[0] for k, v in res.items()})
    if not HOLDOUT_OPEN:
        R = R.loc[:DEV[1]]
    save(R, f"books_{tag}_returns.parquet")
    pd.set_option("display.width", 250)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
