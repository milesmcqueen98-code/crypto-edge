#!/usr/bin/env python3
"""Creative search: hourly-data strategies, AI risk models and portfolio insurance, run as
they would trade on Coinbase (spot at the new small-account fees, or nano BTC/ETH perps).

Pre-registered candidates (rules fixed before results):
  H1  Carver EWMAC on hourly bars, 6 speeds (4/16 ... 128/512 h), 25% vol target, buffered.
      Long-only and long/short (perps).
  H2  Bitcoin time-of-day seasonality (Padysak & Vojtko 2021): long BTC 22:00-24:00 UTC.
  H3  Intraday momentum/reversal (Shen, Urquhart & Wang 2022), ET clock: trade 16-17h ET,
      long if overnight-to-10am return > 0 and 15-16h return < 0, short if the reverse.
  H4  AI hourly model: LightGBM classifier on next-4h direction (hour, lags, vol, volume, trend
      features), purged quarterly walk-forward, trade only when p > 0.55 / < 0.45.
  H5  AI risk overlay on the live rule: volatility forecast (HAR and LightGBM on hourly
      realized variance) sets position size; plus an AI crash guard that halves exposure.
  H6  Live rule checked hourly with a +/-0.5% band (faster exits), on perps.
Baselines: live rule on spot at 0.25% (earlier assumption), at Coinbase's 0.50% maker fee, and on perps.
"""
import os
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import book, intraday as ih  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PER = {"dev": ("2019-11-06", "2023-12-31"), "recent": ("2024-01-01", None),
       "early": ("2017-07-01", "2019-11-05"), "7y": ("2019-11-06", None)}
A2 = ["BTC", "ETH"]
TARGET = 0.25

close_h, vol_h = ih.load_hourly(A2)
H = close_h.index
r_h = close_h.pct_change(fill_method=None)
close_d = ih.daily_from_hourly(close_h)
D = close_d.index
FUND = ih.hourly_funding(H, A2)
et = H.tz_localize("UTC").tz_convert("America/New_York")
ET_HOUR = pd.Series(et.hour, index=H)


def to_hourly(Wd):
    """Daily target weights (decided at the UTC close) -> hourly positions held the next day."""
    Wd = Wd.reindex(D).fillna(0.0)
    Ph = Wd.reindex(H.floor("D")).set_axis(H)                       # value of day d on all hours of d
    last_hour = H.hour == 23
    Ph[~last_hour] = np.nan                                         # change only at the daily close
    return Ph.ffill().fillna(0.0)


def live_daily():
    btc = close_d.BTC
    up = (btc > btc.rolling(100).mean()).astype(float)
    return pd.DataFrame({"BTC": 0.5 * up, "ETH": 0.5 * up}, index=D)


# ---------------------------------------------------------------- H1 hourly EWMAC
def hourly_ewmac(long_only, cap=2.0):
    speeds = [(4, 16), (8, 32), (16, 64), (32, 128), (64, 256), (128, 512)]
    vh = r_h.ewm(span=768, min_periods=240).std()
    vann = (vh * np.sqrt(8760)).clip(lower=0.10)
    comb = []
    for f, s in speeds:
        raw = (close_h.ewm(span=f, min_periods=f).mean() - close_h.ewm(span=s, min_periods=s).mean()) / (close_h * vh)
        scal = 10.0 / raw.abs().mean(axis=1).expanding(min_periods=24 * 365).mean()
        comb.append(raw.mul(scal, axis=0).clip(-20, 20))
    F = (sum(comb) / len(comb) * 1.26).clip(-20, 20)
    if long_only:
        F = F.clip(lower=0)
    unit = 1.05 * 0.5 * TARGET / vann
    pos = book.buffer_positions((F / 10 * unit).fillna(0.0), 0.1 * unit)
    return book.cap_gross(pos.fillna(0.0), cap)


# ---------------------------------------------------------------- H2 seasonality
def seasonality():
    P = pd.DataFrame(0.0, index=H, columns=A2)
    P.loc[H.hour.isin([21, 22]), "BTC"] = 1.0      # held during the 22:00 and 23:00 UTC bars
    return P


# ---------------------------------------------------------------- H3 Shen-Urquhart-Wang
def suw_intraday():
    P = pd.DataFrame(0.0, index=H, columns=A2)
    c = close_h
    eth_hour = ET_HOUR.to_numpy()
    # bar starting 16:00 ET closes at the 17:00 ET "day close"
    is16, is15, is9 = eth_hour == 16, eth_hour == 15, eth_hour == 9
    for a in A2:
        ca = c[a]
        close17 = ca.where(is16).ffill().shift(1)          # last completed 17:00 ET close before now
        close10 = ca.where(is9).ffill()                     # close of the 9:00-10:00 ET bar
        r_onfh = close10 / close17 - 1
        r_slh = ca / ca.shift(1) - 1                       # return of the current bar
        sig = np.where((r_onfh > 0) & (r_slh < 0), 1.0, np.where((r_onfh <= 0) & (r_slh >= 0), -1.0, 0.0))
        s = pd.Series(sig, index=H).where(is15, 0.0)        # decide at the end of the 15:00 ET bar
        P[a] = 0.5 * s.fillna(0.0)
    return P


# ---------------------------------------------------------------- H4 AI hourly model
def ai_hourly_features():
    rows = []
    btc_up = (close_d.BTC > close_d.BTC.rolling(100).mean()).astype(float)
    up_h = btc_up.shift(1).reindex(H.floor("D")).set_axis(H)   # yesterday's daily state, known now
    rel24 = (close_h.ETH / close_h.ETH.shift(24)) / (close_h.BTC / close_h.BTC.shift(24)) - 1
    for a in A2:
        p, r = close_h[a], r_h[a]
        vh = r.ewm(span=768, min_periods=240).std()
        f = pd.DataFrame(index=H)
        f["hour_et"] = ET_HOUR.to_numpy()
        f["dow"] = et.dayofweek
        for k in (1, 2, 3, 4, 6, 8, 12, 24, 48, 72, 168, 336):
            f[f"r{k}"] = (p / p.shift(k) - 1) / (vh * np.sqrt(k))
        rv6 = r.rolling(6).std()
        f["rv6_168"] = rv6 / r.rolling(168).std()
        f["rv24_720"] = r.rolling(24).std() / r.rolling(720).std()
        f["vol_z"] = np.log((vol_h[a].rolling(24).sum() + 1) / (vol_h[a].rolling(720).mean() * 24 + 1))
        for n in (24, 168, 720):
            f[f"ema{n}"] = (p / p.ewm(span=n).mean() - 1) / vh
        f["trend_up"] = up_h.to_numpy()
        f["rel24"] = rel24.to_numpy() * (1 if a == "ETH" else -1)
        f["is_eth"] = float(a == "ETH")
        fwd = p.shift(-4) / p - 1
        f["y"] = (fwd > 0).astype(float).where(fwd.notna())
        f["asset"] = a
        f["vann"] = (vh * np.sqrt(8760)).clip(lower=0.10)
        rows.append(f)
    X = pd.concat(rows)
    X = X[(X.index.hour + 1) % 4 == 0]                     # decisions at 00/04/08/12/16/20 UTC
    return X


def ai_hourly(long_only=False):
    X = ai_hourly_features()
    feats = [c for c in X.columns if c not in ("y", "asset", "vann")]
    params = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=500,
                  feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10.0,
                  n_estimators=300, verbose=-1, seed=7, num_threads=2)
    preds = []
    for t0 in pd.date_range("2019-01-01", H[-1], freq="QS"):
        t1 = t0 + pd.offsets.QuarterBegin(1)
        tr = X[(X.index < t0 - pd.Timedelta(hours=28)) & X.y.notna() & (X.index >= "2016-07-01")]
        te = X[(X.index >= t0) & (X.index < t1)]
        if len(tr) < 5000 or te.empty:
            continue
        m = lgb.LGBMClassifier(**params).fit(tr[feats], tr.y.astype(int))
        preds.append(te[["asset", "vann", "y"]].assign(p=m.predict_proba(te[feats])[:, 1]))
    Pr = pd.concat(preds)
    P = pd.DataFrame(0.0, index=H, columns=A2)
    for a in A2:
        pa = Pr[Pr.asset == a]
        sig = np.where(pa.p > 0.55, 1.0, np.where(pa.p < 0.45, 0.0 if long_only else -1.0, 0.0))
        size = 0.5 * TARGET / pa.vann
        s = pd.Series(sig * size.to_numpy(), index=pa.index).reindex(H)
        # hold for the next 4 hours: carry the decision forward until the next decision point
        dec = pd.Series(np.nan, index=H)
        dec.loc[pa.index] = s.loc[pa.index]
        P[a] = dec.ffill(limit=3).fillna(0.0)
    hit = ((Pr.p > 0.5) == (Pr.y > 0)).mean()
    active = Pr[(Pr.p > 0.55) | (Pr.p < 0.45)]
    hit_active = ((active.p > 0.5) == (active.y > 0)).mean()
    return book.cap_gross(P, 2.0), dict(hit=hit, hit_active=hit_active, share_active=len(active) / len(Pr))


# ---------------------------------------------------------------- H5 AI risk overlay
def daily_rv():
    rv = (r_h ** 2).groupby(H.floor("D")).sum(min_count=12)
    return rv.reindex(D)


def vol_forecasts():
    """Forecast next-7-day average daily variance per asset: HAR-OLS and LightGBM, walk-forward."""
    rv = daily_rv()
    out_har, out_ml = {}, {}
    for a in A2:
        x = rv[a]
        df = pd.DataFrame({"l1": np.log(x), "l7": np.log(x.rolling(7).mean()), "l30": np.log(x.rolling(30).mean()),
                           "ret1": close_d[a].pct_change(), "ret7": close_d[a].pct_change(7),
                           "ret30": close_d[a].pct_change(30), "dd30": close_d[a] / close_d[a].rolling(30).max() - 1})
        df["y"] = np.log(x.shift(-1).rolling(7).mean().shift(-6))
        har, ml = pd.Series(np.nan, index=D), pd.Series(np.nan, index=D)
        for t0 in pd.date_range("2017-01-01", D[-1], freq="QS"):
            t1 = t0 + pd.offsets.QuarterBegin(1)
            tr = df[(df.index < t0 - pd.Timedelta(days=8))].dropna()
            te = df[(df.index >= t0) & (df.index < t1)].dropna(subset=["l1", "l7", "l30"])
            if len(tr) < 365 or te.empty:
                continue
            Xh = np.c_[np.ones(len(tr)), tr[["l1", "l7", "l30"]].to_numpy()]
            beta = np.linalg.lstsq(Xh, tr.y.to_numpy(), rcond=None)[0]
            har.loc[te.index] = np.c_[np.ones(len(te)), te[["l1", "l7", "l30"]].to_numpy()] @ beta
            m = lgb.LGBMRegressor(objective="regression", learning_rate=0.03, num_leaves=7, min_data_in_leaf=60,
                                  n_estimators=300, lambda_l2=5.0, verbose=-1, seed=7, num_threads=2)
            fcols = ["l1", "l7", "l30", "ret1", "ret7", "ret30", "dd30"]
            m.fit(tr[fcols], tr.y)
            ml.loc[te.index] = m.predict(te[fcols].fillna(0.0))
        out_har[a], out_ml[a] = np.sqrt(np.exp(har) * 365), np.sqrt(np.exp(ml) * 365)
        # forecast accuracy (log variance), Jul 2017+
    return pd.DataFrame(out_har), pd.DataFrame(out_ml), rv


def crash_guard():
    """AI crash classifier: P(next-3-day return < -2 x forecast 3-day vol) per asset, walk-forward."""
    rv = daily_rv()
    probs = {}
    for a in A2:
        c = close_d[a]
        sd = np.sqrt(rv[a].rolling(30).mean())
        df = pd.DataFrame({"l1": np.log(rv[a]), "l7": np.log(rv[a].rolling(7).mean()),
                           "l30": np.log(rv[a].rolling(30).mean()), "ret1": c.pct_change(), "ret3": c.pct_change(3),
                           "ret7": c.pct_change(7), "ret30": c.pct_change(30), "dd20": c / c.rolling(20).max() - 1,
                           "sma100": c / c.rolling(100).mean() - 1,
                           "maxdrop24": r_h[a].groupby(H.floor("D")).min().reindex(D),
                           "downshare": ((r_h[a].clip(upper=0) ** 2).groupby(H.floor("D")).sum() /
                                         (r_h[a] ** 2).groupby(H.floor("D")).sum()).reindex(D)})
        fwd3 = c.shift(-3) / c - 1
        df["y"] = (fwd3 < -2 * sd * np.sqrt(3)).astype(float).where(fwd3.notna())
        p = pd.Series(np.nan, index=D)
        thr = pd.Series(np.nan, index=D)
        fcols = [k for k in df.columns if k != "y"]
        for t0 in pd.date_range("2018-01-01", D[-1], freq="QS"):
            t1 = t0 + pd.offsets.QuarterBegin(1)
            tr = df[df.index < t0 - pd.Timedelta(days=4)].dropna()
            te = df[(df.index >= t0) & (df.index < t1)]
            if len(tr) < 365 or tr.y.sum() < 10 or te.empty:
                continue
            m = lgb.LGBMClassifier(objective="binary", learning_rate=0.03, num_leaves=7, min_data_in_leaf=50,
                                   n_estimators=200, lambda_l2=5.0, verbose=-1, seed=7, num_threads=2,
                                   is_unbalance=True)
            m.fit(tr[fcols], tr.y.astype(int))
            p.loc[te.index] = m.predict_proba(te[fcols].fillna(0.0))[:, 1]
            thr.loc[te.index] = np.quantile(m.predict_proba(tr[fcols])[:, 1], 0.9)
        probs[a] = (p > thr).astype(float).where(p.notna())
    return pd.DataFrame(probs)


def risk_overlay(vol, guard=None, target=0.5, cap=2.0):
    Wl = live_daily()
    W = pd.DataFrame(index=D, columns=A2, dtype=float)
    for a in A2:
        size = (target / vol[a]).clip(upper=cap)
        w = Wl[a] * 2 * 0.5 * size
        if guard is not None:
            w = w * np.where(guard[a].reindex(D).fillna(0.0) > 0, 0.5, 1.0)
        W[a] = w
    return book.cap_gross(W.fillna(0.0), cap)


# ---------------------------------------------------------------- H6 live rule checked hourly
def live_hourly(band=0.005):
    sma = close_d.BTC.rolling(100).mean().shift(1)               # 100-day SMA of completed days
    s_h = sma.reindex(H.floor("D")).set_axis(H)
    px = close_h.BTC
    state, out = 0.0, np.zeros(len(H))
    pa, sa = px.to_numpy(), s_h.to_numpy()
    for i in range(len(H)):
        if np.isnan(pa[i]) or np.isnan(sa[i]):
            state = 0.0
        elif pa[i] > sa[i] * (1 + band):
            state = 1.0
        elif pa[i] < sa[i] * (1 - band):
            state = 0.0
        out[i] = state
    on = pd.Series(out, index=H)
    return pd.DataFrame({"BTC": 0.5 * on, "ETH": 0.5 * on}, index=H)


# ---------------------------------------------------------------- evaluation
def evaluate(name, x, kind, note=""):
    row = {"strategy": name, "kind": kind, "note": note}
    for p, (s, e) in PER.items():
        st = book.summary(x, s, e)
        row |= {f"{p}_{k}": v for k, v in st.items()}
    xx = x.loc["2017-07-01":]
    yearly = ((1 + xx + book.rf_daily(xx.index)).groupby(xx.index.year).prod() - 1)
    row["worst_year"] = yearly.min()
    row["losing_years"] = int((yearly < 0).sum())
    row["yearly"] = "; ".join(f"{y}: {v:+.0%}" for y, v in yearly.items())
    return row


def main():
    rows, streams = [], {}

    def add(name, x, kind, note=""):
        streams[name] = x
        rows.append(evaluate(name, x, kind, note))
        print(f"  {name:55s} dev {rows[-1]['dev_sharpe']:5.2f} | recent {rows[-1]['recent_sharpe']:5.2f} | "
              f"early {rows[-1]['early_sharpe']:5.2f} | 7y {rows[-1]['7y_sharpe']:5.2f} CAGR {rows[-1]['7y_cagr']:6.1%} "
              f"DD {rows[-1]['7y_maxdd']:5.0%} | losing yrs {rows[-1]['losing_years']}", flush=True)

    Wl = live_daily()
    add("Live rule, spot at 0.25% (earlier assumption)", book.excess_returns(Wl.reindex(book.ls.load()[0].index).fillna(0.0)), "baseline")
    add("Live rule, Coinbase spot at 0.50% maker", book.excess_returns(Wl.reindex(book.ls.load()[0].index).fillna(0.0), cost=0.005), "baseline")
    add("Live rule, Coinbase perps", ih.run(to_hourly(Wl), close_h), "baseline")

    print("H1 hourly EWMAC", flush=True)
    add("H1 Hourly EWMAC, long-only (perps)", ih.run(hourly_ewmac(True), close_h), "candidate")
    add("H1 Hourly EWMAC, long/short (perps)", ih.run(hourly_ewmac(False), close_h), "candidate")
    print("H2/H3 intraday effects", flush=True)
    add("H2 BTC 22-24h UTC seasonality (perps)", ih.run(seasonality(), close_h), "candidate")
    add("H3 Intraday momentum/reversal, ET clock (perps)", ih.run(suw_intraday(), close_h), "candidate")
    print("H4 AI hourly model", flush=True)
    Pai, info = ai_hourly(False)
    add("H4 AI hourly model, long/short (perps)", ih.run(Pai, close_h), "candidate",
        f"hit {info['hit']:.3f}, hit when trading {info['hit_active']:.3f}, active {info['share_active']:.0%}")
    Pai_lo, _ = ai_hourly(True)
    add("H4 AI hourly model, long-only (perps)", ih.run(Pai_lo, close_h), "candidate")
    print("H5 AI risk overlay", flush=True)
    vh, vm, rv = vol_forecasts()
    realized = np.sqrt(rv.shift(-1).rolling(7).mean().shift(-6) * 365)
    for nm, v in [("HAR", vh), ("LightGBM", vm)]:
        err = (np.log(v) - np.log(realized)).loc["2017-07-01":].stack()
        print(f"     vol forecast {nm}: RMSE (log vol) {np.sqrt((err ** 2).mean()):.3f}", flush=True)
    naive = np.sqrt(rv.rolling(30).mean() * 365)
    err = (np.log(naive) - np.log(realized)).loc["2017-07-01":].stack()
    print(f"     vol forecast naive 30d: RMSE (log vol) {np.sqrt((err ** 2).mean()):.3f}", flush=True)
    add("H5 Live rule + HAR vol sizing (perps)", ih.run(to_hourly(risk_overlay(vh)), close_h), "candidate")
    add("H5 Live rule + AI vol sizing (perps)", ih.run(to_hourly(risk_overlay(vm)), close_h), "candidate")
    g = crash_guard()
    add("H5 Live rule + AI vol sizing + AI crash guard (perps)", ih.run(to_hourly(risk_overlay(vm, g)), close_h), "candidate")
    print("H6 hourly-checked live rule", flush=True)
    add("H6 Live rule checked hourly, 0.5% band (perps)", ih.run(live_hourly(), close_h), "candidate")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(ROOT, "reports", "intraday_results.csv"), index=False)
    pd.DataFrame(streams).to_parquet(os.path.join(ROOT, "reports", "intraday_returns.parquet"))
    print("\nYear by year (total return):")
    for _, r in df.iterrows():
        print(f"  {r.strategy[:55]:55s} {r.yearly}")


if __name__ == "__main__":
    main()
