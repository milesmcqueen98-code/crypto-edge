#!/usr/bin/env python3
"""H5 (AN) simulation core (reports/hunt/h5an/SPEC.md). Imported by dev.py (DEV trials) and final.py (frozen variant).

Trade (fixed by the SPEC):
- Entry: taker buy at the first Coinbase print at least DELTA seconds after releaseDate, priced at that print x
  (1 + 1.5 x half-spread), plus the VIP-1 taker fee.
- Exit: market sale at the first print at least H after the entry, worse by the same half-spread, plus the taker fee.
- Half-spread: median |buyer-initiated - seller-initiated| / 2 of adjacent opposite-aggressor prints in the 10 minutes
  before releaseDate (fetch_trades.lookups).
- Size: min($5K, 1% of the coin's trailing 30-day median daily USD volume on Coinbase).
- One position per event; several tickers in one article are several trades.
Engineering choices (not in the SPEC; fixed here before any trial was scored):
- Half-spread fallbacks when the 10 minutes before hold < 3 opposite-aggressor pairs: the hour before (pairs <= 10 s
  apart, >= 3 pairs), then the hour before (any gap, >= 1 pair), then 50 bp.
- The half-spread charge per side is max(1.5 x measured, common.SPOT_HALF_SPREAD_BP), so it is never below the shared
  cost model's 2 bp.
- 30-day volume: median of up to 30 daily candles before the event day (volume x close); if there are none, 24 x the
  USD volume of the hour before.
- If no print exists after entry + H inside the fetched window (release + 150 min, extended to +8 h when needed), the
  exit is the last print fetched (counted and reported).
- Cash: open notional never exceeds the sleeve's capital; an entry that would exceed it is cut to the remaining cash
  (skipped if none).
- P&L is booked on the exit's calendar day (UTC). Daily return = P&L / sleeve capital; 0 on idle days.
"""
import glob
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402
import gates  # noqa: E402

D = os.path.join(ROOT, "data", "hunt", "h5an")
OUT = os.path.join(ROOT, "reports", "hunt", "h5an")
IDEA = "h5an"
DELTAS = (2, 10, 30)
HOLDS = (300, 1800, 7200)
SIZE_CAP = 5000.0
ADV_FRAC = 0.01
HS_FALLBACK_BP = 50.0
CLASSES_ALL = ("i", "ii", "iii", "iv")
CLASS_CODE = {"i": 0, "ii": 1, "iii": 2, "iv": 3}
SCORED = pd.DatetimeIndex(gates.ERA_DAYS)


# ------------------------------------------------------------------ events
def load_events():
    """Every candidate event (classes i-iv, Coinbase USD product) with its price lookups, the half-spread used, the
    30-day volume and the size. Keeps only events whose product traded in the hour before releaseDate."""
    E = pd.read_csv(os.path.join(D, "events.csv"))
    E = E[E["product"].notna() & E.cls.isin(CLASSES_ALL)].copy()
    E["key"] = E["product"].str.replace("-USD", "", regex=False) + "_" + E.release_ms.astype(str)
    E = E.drop_duplicates("key")
    P = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(D, "px_*.parquet")))])
    P = P.drop(columns=[c for c in ("product", "release_ms") if c in P.columns])
    M = E.merge(P, on="key", how="inner")
    M = M[M.n_pre60.fillna(0) > 0].copy()
    M["release"] = pd.to_datetime(M.release_ms, unit="ms")
    M["day"] = M.release.dt.normalize()
    # half-spread used (bp)
    hs = np.where(M.hs10_pairs >= 3, M.hs10, np.where(M.hs60_pairs >= 3, M.hs60,
                                                      np.where(M.hs60any_pairs >= 1, M.hs60any, np.nan)))
    M["hs_src"] = np.where(M.hs10_pairs >= 3, "hs10", np.where(M.hs60_pairs >= 3, "hs60",
                                                              np.where(M.hs60any_pairs >= 1, "hs60any", "default")))
    M["hs_bp"] = np.where(np.isnan(hs), HS_FALLBACK_BP, hs)
    M["hs_charge_bp"] = np.maximum(1.5 * M.hs_bp, common.SPOT_HALF_SPREAD_BP)
    # trailing 30-day median daily USD volume
    dly = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(D, "daily_*.parquet")))])
    dly = dly.rename(columns={"day": "cday"})
    dly["usd"] = dly.volume.astype(float) * dly.close.astype(float)
    dly = dly.merge(M[["key", "day"]], on="key")
    dly = dly[dly.cday < dly.day]                                        # candles strictly before the event day
    med = dly.sort_values("cday").groupby("key").usd.apply(lambda u: u.tail(30).median())
    M["adv30"] = M.key.map(med)
    M["adv_src"] = np.where(M.adv30.notna() & (M.adv30 > 0), "daily30", "hour_x24")
    M.loc[M.adv_src == "hour_x24", "adv30"] = 24 * M.loc[M.adv_src == "hour_x24", "usd_pre60"]
    M["size"] = np.minimum(SIZE_CAP, ADV_FRAC * M.adv30)
    M["ccode"] = M.cls.map(CLASS_CODE)
    return M.sort_values(["release_ms", "key"]).reset_index(drop=True)


def dev_events(M):
    """Events whose release is before HOLD0 (the DEV stage never sees a HOLD event)."""
    return M[M.release < gates.HOLD0].copy()


# ------------------------------------------------------------------ trades
def trades(M, delta, hold, mult, classes=CLASSES_ALL, capital=30000.0, take=None, size_mult=None):
    """One row per traded event: entry/exit times, gross and net return at `mult` x costs, $ size, $ P&L.
    take: optional boolean mask (AI filter) aligned with M. size_mult: optional per-event size multiplier."""
    m = M[M.cls.isin(classes)].copy()
    if take is not None:
        m = m[take.reindex(m.index).fillna(False).to_numpy()]
    if size_mult is not None:
        m["size"] = m["size"] * size_mult.reindex(m.index).fillna(0.0)
    e_ms, e_px = m[f"e{delta}_ms"], m[f"e{delta}_px"]
    x_ms, x_px = m[f"x{delta}_{hold}_ms"], m[f"x{delta}_{hold}_px"]
    m = m[e_ms.notna()].copy()
    m["e_ms"], m["e_px"] = m[f"e{delta}_ms"].astype(float), m[f"e{delta}_px"].astype(float)
    m["x_ms"], m["x_px"] = m[f"x{delta}_{hold}_ms"].astype(float), m[f"x{delta}_{hold}_px"].astype(float)
    # no print at least H after the entry inside the fetched window (release + 150 min, extended to +8 h): exit at the
    # last print up to release + 2 h if it is after the entry, else flat at the entry print (counted, reported)
    last = m.x_ms.isna()
    m["exit_fallback"] = last
    late = last & (m.e_ms >= 7.2e6)
    m.loc[last, "x_ms"] = np.maximum(m.loc[last, "e_ms"] + 1, m.loc[last, "last_ms"].astype(float))
    m.loc[last, "x_px"] = np.where(late[last], m.loc[last, "e_px"], m.loc[last, "p_7200"].astype(float))
    m = m[m.x_ms > m.e_ms].copy()
    m["entry"] = m.release + pd.to_timedelta(m.e_ms, unit="ms")
    m["exit"] = m.release + pd.to_timedelta(m.x_ms, unit="ms")
    hs = m.hs_charge_bp / 1e4 * mult
    fee = common.SPOT_TAKER * mult
    m["gross"] = m.x_px / m.e_px - 1
    m["net"] = (m.x_px * (1 - hs) * (1 - fee)) / (m.e_px * (1 + hs) * (1 + fee)) - 1
    # cash constraint
    m = m.sort_values(["entry", "key"])
    open_pos, sizes = [], []
    for r in m.itertuples():
        open_pos = [(x, s) for x, s in open_pos if x > r.entry]
        free = capital - sum(s for _, s in open_pos)
        s = max(0.0, min(r.size, free))
        sizes.append(s)
        if s > 0:
            open_pos.append((r.exit, s))
    m["usd"] = sizes
    m = m[m.usd > 0].copy()
    m["pnl"] = m.usd * m.net
    m["exit_day"] = m.exit.dt.normalize()
    return m


def daily(tr, capital, days=SCORED):
    s = tr.groupby("exit_day").pnl.sum() / capital
    return s.reindex(pd.DatetimeIndex(days)).fillna(0.0)


def dev_days():
    return SCORED[SCORED < gates.HOLD0]


# ------------------------------------------------------------------ AI (walk-forward by quarter)
FEATURES = ["ccode", "log_adv", "pre_move", "btc60", "hour"]


def btc_close():
    """BTC-USD 1-minute closes (Coinbase spot), minutes with trades only; two columns read to keep memory small."""
    parts = []
    for src in ("minute_early", "minute"):
        d = pd.read_parquet(os.path.join(common.DATA, src, "BTC.parquet"), columns=["ts", "close", "volume"])
        d = d[d.volume > 0]
        parts.append(pd.Series(d.close.to_numpy(), index=pd.DatetimeIndex(d.ts)))
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated()]


def features(M, delta, btc):
    """Decision-time features at the entry (release + delta)."""
    f = pd.DataFrame(index=M.index)
    f["ccode"] = M.ccode
    f["log_adv"] = np.log10(M.adv30.clip(lower=1.0))
    # -10 min to the last print known at the decision (decision = entry - 2 s; prints >= 1 s old):
    # release - 10 s / + 5 s / + 20 s for delta 2 / 10 / 30 s
    known = {2: "p_-10", 10: "p_5", 30: "p_20"}[delta]
    f["pre_move"] = np.log(M[known] / M["p_-600"])
    # BTC: the 1-minute candle that closed at least one minute before the decision
    dec = (M.release + pd.to_timedelta(delta, unit="s")).dt.floor("min") - pd.Timedelta(minutes=2)
    c1 = btc.reindex(dec, method="ffill").to_numpy()
    c0 = btc.reindex(dec - pd.Timedelta(minutes=60), method="ffill").to_numpy()
    f["btc60"] = np.log(c1 / c0)
    f["hour"] = M.release.dt.hour
    return f


def ai_take(M, delta, hold, kind, end=None):
    """Walk-forward LightGBM filter. kind: 'reg' (trade if predicted 2x net return > 0) or 'clf' (trade if
    P(2x net return > 0) > 0.5). Training uses every event whose exit is before the test quarter starts (2022 onward,
    2024 included); the first quarter scored is the first one with >= 6 months of history (2022Q3).
    end: events at or after `end` are never used or scored (the DEV stage passes HOLD0)."""
    import lightgbm as lgb
    btc = btc_close()
    m = M if end is None else M[M.release < end]
    F = features(m, delta, btc)
    tr = trades(m, delta, hold, 2.0, capital=1e12)                    # targets (cash cap off)
    y = tr.net.reindex(m.index)
    exit_t = tr.exit.reindex(m.index)
    q = m.release.dt.to_period("Q")
    warm = m.release.min() + pd.DateOffset(months=6)              # >= 6 months of history before the first quarter
    first_q = warm.to_period("Q") + (0 if warm == warm.to_period("Q").start_time else 1)
    take = pd.Series(False, index=m.index)
    for qq in sorted(q.unique()):
        if qq < first_q:
            continue
        q0 = qq.start_time
        trn = y.notna() & (exit_t < q0)                                  # LightGBM handles missing features
        tst = q == qq
        if trn.sum() < 30 or tst.sum() == 0:
            continue
        params = dict(n_estimators=200, learning_rate=0.03, num_leaves=4, min_child_samples=10, subsample=0.8,
                      subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=7, verbose=-1)
        if kind == "reg":
            mdl = lgb.LGBMRegressor(**params).fit(F[trn], y[trn])
            take[tst] = mdl.predict(F[tst]) > 0
        else:
            mdl = lgb.LGBMClassifier(**params).fit(F[trn], (y[trn] > 0).astype(int))
            take[tst] = mdl.predict_proba(F[tst])[:, 1] > 0.5
    return take


# ------------------------------------------------------------------ helpers
def alpha70(s, days):
    ri = gates.incumbent(70e3, 0.5, "instant", days)
    return gates.alpha_test(pd.Series(s).reindex(days).fillna(0.0), ri)


def git_head():
    import subprocess
    return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "HEAD"], text=True).strip()


def nan2none(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x
