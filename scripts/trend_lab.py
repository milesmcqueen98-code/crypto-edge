#!/usr/bin/env python3
"""Trend rule v2 lab (rules: reports/trend_v2_prereg.md).

Engine: one step per UTC day (marks at 00:00 UTC). Each variant decides on its own schedule from its own signal
prices and trades at most once per step at its execution time:
  utc      : decide on the 00:00 UTC price, trade at that price
  et       : decide on BTC at 15:00 ET, trade at the 16:00 ET close (market-on-close), NYSE trading days only
  et_next  : decide at 00:00 UTC, trade at the next 16:00 ET close
  et_open  : decide at 00:00 UTC, trade at the next 10:00 ET price (first hour of the US session)
Holdings drift between trades. Costs are charged on traded notional:
  - Coinbase spot: fee tier from this strategy's own trailing-30-day volume at a fixed book size, plus slippage.
  - ETFs: flat bp per side plus an expense ratio accrued daily while held.
Idle cash earns T-bills. Sharpe is on daily returns above T-bills, x sqrt(365).
Writes reports/trend_lab/results.csv, daily.parquet, years.csv.
"""
import os
import sys

import numpy as np
import pandas as pd
from pandas.tseries.holiday import (AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay,
                                    USMartinLutherKingJr, USMemorialDay, USPresidentsDay, USThanksgivingDay,
                                    nearest_workday)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from edge.book import rf_daily  # noqa: E402

OUT = os.path.join(ROOT, "reports", "trend_lab")
SIM0, EVAL0, END = pd.Timestamp("2016-09-01"), pd.Timestamp("2017-07-01"), pd.Timestamp("2026-11-06")
SUBS = {"2017-19": ("2017-07-01", "2020-01-01"), "2020-21": ("2020-01-01", "2022-01-01"),
        "2022-23": ("2022-01-01", "2024-01-01"), "2024-26": ("2024-01-01", "2026-11-06")}
# Coinbase Advanced spot, after the Sep 16, 2026 change: (30-day volume floor $, maker, taker)
TIERS = [(0, 0.0050, 0.0090), (10e3, 0.0035, 0.0075), (50e3, 0.0015, 0.0030), (250e3, 0.0010, 0.0015),
         (500e3, 0.0006, 0.00125)]


class NYSE(AbstractHolidayCalendar):
    rules = [Holiday("NewYear", month=1, day=1, observance=nearest_workday), USMartinLutherKingJr, USPresidentsDay,
             GoodFriday, USMemorialDay,
             Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
             Holiday("July4", month=7, day=4, observance=nearest_workday), USLaborDay, USThanksgivingDay,
             Holiday("Christmas", month=12, day=25, observance=nearest_workday)]


# ---------------------------------------------------------------- data
def hourly(c):
    d = pd.read_csv(os.path.join(ROOT, "data", "hourly", f"{c}.csv.gz"), parse_dates=["ts"])
    s = d.drop_duplicates("ts").set_index("ts").close.astype(float).sort_index()
    grid = pd.date_range(s.index[0].floor("h"), END + pd.Timedelta(hours=12), freq="h")
    s = s.reindex(grid).ffill(limit=6)
    return s.shift(1)                          # price AT time T = close of the bar that ends at T


class Market:
    def __init__(self, assets=("BTC", "ETH", "SOL")):
        self.pa = {c: hourly(c) for c in assets}
        self.days = pd.date_range(SIM0, END - pd.Timedelta(days=1), freq="D")       # mark at 00:00 of each day
        hol = NYSE().holidays(start="2016-01-01", end="2027-01-01")
        self.trading = pd.DatetimeIndex([d for d in self.days if d.dayofweek < 5 and d not in hol])
        et = lambda d, h: (pd.Timestamp(d.year, d.month, d.day, h).tz_localize("America/New_York")  # noqa: E731
                           .tz_convert("UTC").tz_localize(None))
        self.t15 = pd.Series([et(d, 15) for d in self.days], index=self.days)
        self.t16 = pd.Series([et(d, 16) for d in self.days], index=self.days)
        self.t10 = pd.Series([et(d, 10) for d in self.days], index=self.days)
        self.rf = rf_daily(self.days)

    def px(self, c, times):
        s = self.pa[c]
        return s.reindex(pd.DatetimeIndex(times)).to_numpy()


# ---------------------------------------------------------------- signals (on a daily grid of signal prices)
def sma(p, n):
    return p.rolling(n, min_periods=n).mean()


def ema(p, n):
    return p.ewm(span=n, adjust=False, min_periods=n).mean()


def state_band(p, avg, band):
    on = np.zeros(len(p), dtype=bool)
    st = False
    for i, (x, a) in enumerate(zip(p.to_numpy(), avg.to_numpy())):
        if np.isnan(x) or np.isnan(a):
            on[i] = st
            continue
        if not st and x > a * (1 + band):
            st = True
        elif st and x < a * (1 - band):
            st = False
        on[i] = st
    return pd.Series(on, index=p.index)


def state_confirm(raw, n):
    on = np.zeros(len(raw), dtype=bool)
    st, run = False, 0
    for i, r in enumerate(raw.to_numpy()):
        if r != st:
            run += 1
            if run >= n:
                st, run = r, 0
        else:
            run = 0
        on[i] = st
    return pd.Series(on, index=raw.index)


def donchian(p, n_in=50, n_out=25):
    hi, lo = p.shift(1).rolling(n_in).max(), p.shift(1).rolling(n_out).min()
    on = np.zeros(len(p), dtype=bool)
    st = False
    for i, (x, h, l_) in enumerate(zip(p.to_numpy(), hi.to_numpy(), lo.to_numpy())):
        if not st and not np.isnan(h) and x > h:
            st = True
        elif st and not np.isnan(l_) and x < l_:
            st = False
        on[i] = st
    return pd.Series(on, index=p.index)


def targets(v, P):
    """Target weights (DataFrame BTC/ETH/SOL) on each decision day from daily signal prices P (DataFrame)."""
    b, e = P["BTC"], P["ETH"]
    kind, a = v.get("sig", "sma"), v.get("arg", 100)
    n = v.get("len", 100)
    if kind == "sma":
        on = b > sma(b, a if "arg" in v else n)
    elif kind == "ema":
        on = b > ema(b, a)
    elif kind == "band":
        on = state_band(b, sma(b, n), a)
    elif kind == "confirm":
        on = state_confirm(b > sma(b, n), a)
    elif kind == "golden":
        on = sma(b, 50) > sma(b, 200)
    elif kind == "donchian":
        on = donchian(b)
    elif kind == "tsmom":
        on = b > b.shift(a)
    elif kind in ("own", "and", "ensemble"):
        on = b > sma(b, 100)
    else:
        raise ValueError(kind)
    on = on.fillna(False).astype(bool)
    W = pd.DataFrame(0.0, index=P.index, columns=["BTC", "ETH", "SOL"])
    alloc = v.get("alloc", (0.5, 0.5))
    if kind == "own":
        W["BTC"] = 0.5 * (b > sma(b, 100))
        W["ETH"] = 0.5 * (e > sma(e, 100))
    elif kind == "and":
        both = (b > sma(b, 100)) & (e > sma(e, 100))
        W["BTC"], W["ETH"] = 0.5 * both, 0.5 * both
    elif kind == "ensemble":
        k = sum((b > sma(b, n)).astype(float) for n in (50, 100, 150, 200)) / 4
        W["BTC"], W["ETH"] = 0.5 * k, 0.5 * k
    elif alloc == "tilt":
        r = e / b
        lead = r > sma(r, 50)
        W["BTC"] = np.where(on, np.where(lead, 0.25, 0.75), 0.0)
        W["ETH"] = np.where(on, np.where(lead, 0.75, 0.25), 0.0)
    elif alloc == "invvol":
        rb, re = np.log(b).diff(), np.log(e).diff()
        ib, ie = 1 / rb.rolling(30).std(), 1 / re.rolling(30).std()
        W["BTC"] = np.where(on, ib / (ib + ie), 0.0)
        W["ETH"] = np.where(on, ie / (ib + ie), 0.0)
    elif alloc == "sol3":
        s = P["SOL"]
        has = s.notna() & (P.index >= pd.Timestamp("2021-06-20"))
        W["BTC"] = np.where(on, np.where(has, 1 / 3, 0.5), 0.0)
        W["ETH"] = np.where(on, np.where(has, 1 / 3, 0.5), 0.0)
        W["SOL"] = np.where(on & has, 1 / 3, 0.0)
    else:
        W["BTC"], W["ETH"] = on * alloc[0], on * alloc[1]
    if v.get("volcap"):
        rb = np.log(0.5 * b / b.shift(1) + 0.5 * e / e.shift(1))
        vol = rb.rolling(30).std() * np.sqrt(365)
        scale = np.minimum(1.0, v["volcap"] / vol).fillna(1.0)
        W = W.mul(scale, axis=0)
    return W.fillna(0.0)


# ---------------------------------------------------------------- simulation
def fee_coinbase(maker, vol30):
    tier = [t for t in TIERS if vol30 >= t[0]][-1]
    return (tier[1] + 0.0001) if maker else (tier[2] + 0.0002)


def simulate(v, M):
    impl = v["impl"]
    sched = impl["sched"]
    days = M.days
    # signal prices and decision days
    if sched == "et":
        sig_t = M.t15
        dec_days = M.trading
    else:
        sig_t = pd.Series(days, index=days)
        dec_days = days if sched == "utc" else M.trading
    P = pd.DataFrame({c: M.px(c, sig_t.to_numpy()) for c in ("BTC", "ETH", "SOL")}, index=days)
    W = targets(v, P)
    if v.get("weekly"):
        wd = 4 if sched in ("et", "et_next", "et_open") else 6          # Friday for ETFs, Sunday UTC
        keep = W.index.dayofweek == wd
        W = W.where(pd.Series(keep, index=W.index), np.nan).ffill().fillna(0.0)
    # crash guard (S22): basket 7-day drop > 20% while on -> flat for 7 days
    if v.get("guard"):
        bask = 0.5 * P["BTC"] / P["BTC"].shift(7) + 0.5 * P["ETH"] / P["ETH"].shift(7) - 1
        out_until = None
        Wv = W.copy()
        for i, d in enumerate(W.index):
            if out_until is not None and d < out_until:
                Wv.iloc[i] = 0.0
                continue
            out_until = None
            if W.iloc[i].sum() > 0 and bask.iloc[i] < -0.20:
                out_until = d + pd.Timedelta(days=7)
                Wv.iloc[i] = 0.0
        W = Wv
    # execution times (UTC) per day
    if sched == "utc":
        ex_t = pd.Series(days, index=days)
    elif sched in ("et", "et_next"):
        ex_t = M.t16
    else:
        ex_t = M.t10
    dec = pd.Series(False, index=days)
    dec[dec.index.isin(dec_days)] = True
    # et_next / et_open: a decision taken at 00:00 UTC executes in that day's US session; on non-trading days the
    # latest signal simply waits (decisions only exist on trading days)
    cols = ["BTC", "ETH", "SOL"]
    PX = {c: M.px(c, ex_t.to_numpy()) for c in cols}                 # execution prices on day d
    MK = {c: M.px(c, (days + pd.Timedelta(days=1)).to_numpy()) for c in cols}   # mark at next 00:00
    M0 = {c: M.px(c, days.to_numpy()) for c in cols}                 # mark at this day's 00:00
    units = np.zeros(3)
    cash = 1.0
    eq_prev = 1.0
    vol_hist = []                                                    # (day, notional $) for Coinbase tiers
    book = impl.get("book", 10000.0)
    rebal = v.get("rebal")
    buf = v.get("buffer", 0.0)
    er = impl.get("er", 0.0) / 365
    rets = np.zeros(len(days))
    trades = 0
    last_month = None
    wtarget_prev = np.zeros(3)
    minhold = v.get("minhold")
    last_trade = None
    for i, d in enumerate(days):
        rf = M.rf.iloc[i]
        cash *= (1 + rf)
        if dec.iloc[i]:
            wt = W.iloc[i].to_numpy()
            px = np.array([PX[c][i] for c in cols])
            px = np.where(np.isnan(px), np.array([M0[c][i] for c in cols]), px)
            val = cash + np.nansum(units * np.nan_to_num(px))
            cur_w = np.where(val > 0, np.nan_to_num(units * px) / val, 0.0)
            changed = np.abs(wt - wtarget_prev).max() > 1e-9
            month = (d.year, d.month)
            do = changed
            if rebal == "monthly" and wt.sum() > 0 and month != last_month:
                do = True
            if do and buf > 0 and np.abs(wt - cur_w).max() <= buf and not ((wt.sum() == 0) != (cur_w.sum() < 1e-9)):
                do = False
            if do and minhold and last_trade is not None and (d - last_trade).days < minhold:
                do = False
                changed = False                                      # retry on a later decision day
            if do:
                dw = wt - cur_w
                traded = np.abs(dw).sum() * val
                if impl["venue"] == "coinbase":
                    cutoff = d - pd.Timedelta(days=30)
                    vol_hist = [(t, n) for t, n in vol_hist if t > cutoff]
                    vol30 = sum(n for _, n in vol_hist)
                    rate = fee_coinbase(impl["maker"], vol30)
                    vol_hist.append((d, np.abs(dw).sum() * book))
                else:
                    rate = impl["bp"] / 1e4
                cost = traded * rate
                new_units = np.where(np.nan_to_num(px) > 0, wt * (val - cost) / np.where(px > 0, px, 1.0), 0.0)
                cash = val - cost - np.nansum(new_units * np.nan_to_num(px))
                units = new_units
                trades += 1
                wtarget_prev = wt
                last_month = month
                last_trade = d
            elif changed:
                wtarget_prev = wt
        mk = np.array([MK[c][i] for c in cols])
        hold_val = np.nansum(units * np.nan_to_num(mk))
        if er > 0 and hold_val > 0:                                  # ETF expense ratio
            cash -= hold_val * er
        eq = cash + hold_val
        rets[i] = eq / eq_prev - 1
        eq_prev = eq
    r = pd.Series(rets, index=days + pd.Timedelta(days=1))           # return earned during day d, marked at d+1
    return r, trades


def stats(r, rf, lo, hi):
    x = r[(r.index >= lo) & (r.index < hi)]
    f = rf.reindex(x.index).fillna(0.0)
    ex = x - f
    eq = (1 + x).cumprod()
    yrs = max((x.index[-1] - x.index[0]).days / 365.25, 1e-9)
    return dict(sharpe=ex.mean() / ex.std() * np.sqrt(365) if ex.std() > 0 else np.nan,
                cagr=eq.iloc[-1] ** (1 / yrs) - 1, maxdd=(eq / eq.cummax() - 1).min())


# ---------------------------------------------------------------- variants
IMPL = {
    "I0": dict(name="old assumption 0.25%/side, UTC close", venue="flat", bp=25, sched="utc"),
    "I1": dict(name="Coinbase taker, $10k book", venue="coinbase", maker=False, book=1e4, sched="utc"),
    "I2": dict(name="Coinbase maker, $10k book", venue="coinbase", maker=True, book=1e4, sched="utc"),
    "I3": dict(name="Coinbase taker, $100k book", venue="coinbase", maker=False, book=1e5, sched="utc"),
    "I4": dict(name="Coinbase maker, $100k book", venue="coinbase", maker=True, book=1e5, sched="utc"),
    "I5": dict(name="ETFs, 3pm signal, 4pm MOC, 0.25%/yr", venue="flat", bp=2, er=0.0025, sched="et"),
    "I6": dict(name="ETFs, 3pm signal, 4pm MOC, 0.15%/yr", venue="flat", bp=2, er=0.0015, sched="et"),
    "I7": dict(name="ETFs, UTC signal, next 4pm close", venue="flat", bp=2, er=0.0025, sched="et_next"),
    "I8": dict(name="ETFs, UTC signal, next 10am", venue="flat", bp=3, er=0.0025, sched="et_open"),
}
SIGS = {
    "S00": dict(name="live rule"),
    "S01": dict(name="SMA 75", arg=75), "S02": dict(name="SMA 90", arg=90),
    "S03": dict(name="SMA 110", arg=110), "S04": dict(name="SMA 125", arg=125),
    "S05": dict(name="EMA 100", sig="ema", arg=100),
    "S06": dict(name="band 1%", sig="band", arg=0.01), "S07": dict(name="band 2%", sig="band", arg=0.02),
    "S08": dict(name="band 3%", sig="band", arg=0.03),
    "S09": dict(name="confirm 2 closes", sig="confirm", arg=2), "S10": dict(name="confirm 3 closes", sig="confirm", arg=3),
    "S11": dict(name="weekly decisions", weekly=True),
    "S12": dict(name="each asset on its own SMA100", sig="own"),
    "S13": dict(name="both above own SMA100", sig="and"),
    "S14": dict(name="ETH/BTC tilt 75/25", alloc="tilt"),
    "S15": dict(name="100% BTC", alloc=(1.0, 0.0)), "S16": dict(name="100% ETH", alloc=(0.0, 1.0)),
    "S17": dict(name="60/40 BTC/ETH", alloc=(0.6, 0.4)),
    "S18": dict(name="inverse-vol weights", alloc="invvol", buffer=0.05),
    "S19": dict(name="monthly rebalance while on", rebal="monthly"),
    "S20": dict(name="vol cap 80%", volcap=0.80, rebal="monthly", buffer=0.05),
    "S21": dict(name="50/100/150/200 ensemble", sig="ensemble"),
    "S22": dict(name="crash guard (-20% in 7d)", guard=True),
    "S23": dict(name="golden cross 50/200", sig="golden"),
    "S24": dict(name="Donchian 50 in / 25 out", sig="donchian"),
    "S25": dict(name="add SOL third leg", alloc="sol3"),
    "S26": dict(name="90-day TSMOM", sig="tsmom", arg=90),
}


# round 2 (mechanical rule, reports/trend_v2_prereg.md): leads S03 (length), S08 (state filter), S25 (allocation);
# runners-up S04, S07, S14
COMBOS = {
    "C01": dict(name="SMA110 + band 3% + SOL leg", sig="band", arg=0.03, len=110, alloc="sol3"),
    "C02": dict(name="SMA110 + band 3%", sig="band", arg=0.03, len=110),
    "C03": dict(name="SMA110 + SOL leg", len=110, alloc="sol3"),
    "C04": dict(name="band 3% + SOL leg", sig="band", arg=0.03, alloc="sol3"),
    "C05": dict(name="SMA125 + band 3% + SOL leg", sig="band", arg=0.03, len=125, alloc="sol3"),
    "C06": dict(name="SMA110 + band 2% + SOL leg", sig="band", arg=0.02, len=110, alloc="sol3"),
    "C07": dict(name="SMA110 + band 3% + ETH/BTC tilt", sig="band", arg=0.03, len=110, alloc="tilt"),
}
HOLDS = {
    "H1": dict(name="ETFs next 4pm + 30-day minimum hold", minhold=30),
    "H2": dict(name="ETFs next 4pm + 60-day minimum hold", minhold=60),
}


def round2_variants():
    out = []
    for ck, cv in COMBOS.items():
        for ik in ("I2", "I5"):
            d = {k: v for k, v in cv.items() if k != "name"}
            out.append(dict(key=f"{ik}-{ck}", fam="C", impl=IMPL[ik], label=f"{ck} {cv['name']} [{ik}]", **d))
    for hk, hv in HOLDS.items():
        d = {k: v for k, v in hv.items() if k != "name"}
        out.append(dict(key=f"I7-{hk}", fam="H", impl=IMPL["I7"], label=f"{hk} {hv['name']}", **d))
    return out


def all_variants():
    out = []
    for ik, im in IMPL.items():
        out.append(dict(key=f"{ik}-S00", fam="I", impl=im, **{k: v for k, v in SIGS["S00"].items() if k != "name"},
                        label=f"{ik} {im['name']}"))
    for sk, sg in SIGS.items():
        if sk == "S00":
            continue
        for ik in ("I2", "I5"):
            d = {k: v for k, v in sg.items() if k != "name"}
            out.append(dict(key=f"{ik}-{sk}", fam="S", impl=IMPL[ik], label=f"{sk} {sg['name']} [{ik}]", **d))
    return out


def run(variants, M, tag):
    os.makedirs(OUT, exist_ok=True)
    rets, rows = {}, []
    for v in variants:
        r, n = simulate(v, M)
        r = r[(r.index >= EVAL0) & (r.index < END)]
        rets[v["key"]] = r
        row = dict(key=v["key"], fam=v["fam"], label=v["label"], trades=n)
        for lab, (lo, hi) in {"full": (EVAL0, END), **SUBS}.items():
            s = stats(r, M.rf, pd.Timestamp(lo), pd.Timestamp(hi))
            for kk, vv in s.items():
                row[f"{lab}_{kk}"] = vv
        rows.append(row)
        print(f"{v['key']:8s} {v['label'][:52]:52s} Sharpe {row['full_sharpe']:5.2f}  CAGR {row['full_cagr']:6.1%}  "
              f"DD {row['full_maxdd']:6.1%}  trades {n}", flush=True)
    R = pd.DataFrame(rows)
    D = pd.DataFrame(rets)
    R.to_csv(os.path.join(OUT, f"results_{tag}.csv"), index=False)
    D.to_parquet(os.path.join(OUT, f"daily_{tag}.parquet"))
    return R, D


if __name__ == "__main__":
    M = Market()
    which = sys.argv[1] if len(sys.argv) > 1 else "round1"
    if which == "round2":
        run(round2_variants(), M, "round2")
    else:
        vs = all_variants()
        if which != "round1":
            vs = [v for v in vs if which in v["key"]]
        run(vs, M, which)
