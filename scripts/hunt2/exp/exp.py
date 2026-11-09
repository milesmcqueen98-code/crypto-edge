#!/usr/bin/env python3
"""Edge hunt 2, EXP (Path B sleeve; reports/hunt2/exp/SPEC.md): the Deribit Friday 08:00 UTC expiry unwind.

Definitions fixed before the first trial (this docstring is the record; git timestamps it):
- Events: every Friday of the era (Deribit expires options every Friday 08:00 UTC, settled on a 07:30-08:00 TWAP of
  its index). "monthly + quarterly" = the last Friday of each month (quarterlies are a subset).
- D (coins): dealer net delta at 07:29:00 UTC of the options expiring that Friday (scripts/hunt2/gamma/
  derive_deribit.py: inventory = - cumulative signed taker contracts since listing; BS delta at the last traded IV).
- F = +D / V30, V30 = the coin's average 30-minute Coinbase SPOT volume (coins) over the 30 days before 07:29 that day
  (sum of 1-minute volume / 1,440). Spot volume in every era (CFM volume exists only from Jul 2025).
- Threshold: |F| >= the DEV median of |F| over the events of the variant's event set, per coin (BTC and ETH
  separately); stored in frozen.json and applied unchanged to HOLD.
- Prices: P(t) = the close of the last Coinbase spot 1-minute candle before t. Window return r = P(08:00)/P(07:30) - 1;
  sigma = std of the 1,440 non-overlapping 30-minute log returns of P on the :00/:30 grid in the 30 days before
  07:30 that day (trailing, so no look-ahead). Window fade fires when |log(1 + r)| >= 1 sigma (decided at 08:01;
  P(08:00) is then >= 1 minute old).
- Orders: taker at the open of the named minute (the candle model's "next minute's open"): with = enter sign(F) at
  07:30, exit at 08:00; fade = enter -sign(F) at 08:01, exit at 09:00; window fade = enter -sign(r) at 08:01, exit at
  09:00. D is measured at 07:29 from trades before 07:29:00, so it is >= 1 minute old at 07:30.
- Venue: events before the CFM perps existed (dates before 2025-07-25, the first Friday after the 2025-07-18 launch)
  are priced on spot candles; later a trade is priced on CFM perp candles when both its entry and exit minutes have a
  CFM candle (the open of that exact minute), otherwise on spot candles (CFM had no trade in ~13% of DEV window
  minutes; counted in the output). A spot price is the open of the first spot candle at or after the order minute
  and within 5 minutes of it (the first print after the decision); with none (a data gap, e.g. ETH 2025-04-25
  07:29-08:08) the coin does not trade that event.
- Costs (scripts/hunt2/costs.py, perps, every term x mult; 2x for selection and gates): per side
  perp_cost_bp(coin, price, taker=True) on the entry and the exit notional, plus funding perp_funding_bp(hours held)
  on the entry notional. A coin trades only if costs.contract_ok at the entry price (contract worth >= $150).
- Size: per event, 1.0 x sleeve capital split equally across the variant's assets (BTC: 100%; BTC+ETH: 50% each,
  whether or not the other coin fires), whole contracts (floor). P&L booked on the Friday (entry and exit same day);
  daily returns on the sleeve capital over calendar days, 0 when idle.
- An "event" for the minimum-events rule is a Friday on which the variant traded at least one contract.
- Grid (12 trials): rule in {with, fade, wfade} x event set in {all, mq} x assets in {BTC, BTC+ETH}. Selection: the
  highest DEV alpha t (h2gates.dev_screen_b on the $50K sleeve at 2x) with >= 20 events (all) or >= 8 (mq); ties ->
  mq, BTC only.

usage: python scripts/hunt2/exp/exp.py dev sel        (the 12 DEV trials, logged; writes reports/hunt2/exp/dev_*.csv)
       python scripts/hunt2/exp/exp.py hold           (AFTER the freeze only: the frozen variant on every era)
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, "/home/claude/crypto-edge/scripts/hunt2")
import costs  # noqa: E402
import h2gates as G  # noqa: E402

DATA = "/home/claude/crypto-edge/data"
OUT = os.path.join(WT, "reports", "hunt2", "exp")
CFM_FIRST_EVENT = pd.Timestamp("2025-07-25")
RANGES = {"sel": [("2025-01-01", "2026-03-31")],
          "hold": [("2022-01-01", "2023-12-31"), ("2026-04-01", "2026-11-05")]}
RULES, EVSETS, ASSETS = ("with", "fade", "wfade"), ("all", "mq"), ("BTC", "BTC+ETH")
CAPS = (25000, 50000, 75000, 125000)
MIN_EVENTS = {"all": 20, "mq": 8}


def load(src, coin, lo, hi):
    """1-minute candles of data/<src>/<coin>.parquet with lo <= ts < hi only (rows outside are never read)."""
    p = os.path.join(DATA, src, f"{coin}.parquet")
    d = pd.read_parquet(p, filters=[("ts", ">=", pd.Timestamp(lo)), ("ts", "<", pd.Timestamp(hi))])
    d = d.drop_duplicates("ts").set_index("ts").sort_index()
    d = d[d.volume > 0]
    if src == "cfm":
        d = d.assign(volume=d.volume * costs.PERP[coin][1])
    return d


def spot(coin, lo, hi):
    parts = []
    if pd.Timestamp(lo) < pd.Timestamp("2024-01-01"):
        parts.append(load("minute_early", coin, lo, min(pd.Timestamp(hi), pd.Timestamp("2024-01-01"))))
    if pd.Timestamp(hi) > pd.Timestamp("2024-01-01"):
        parts.append(load("minute", coin, max(pd.Timestamp(lo), pd.Timestamp("2024-01-01")), hi))
    d = pd.concat(parts).sort_index()
    return d[~d.index.duplicated()]


def fridays(era):
    out = []
    for lo, hi in RANGES[era]:
        out.append(pd.date_range(lo, hi, freq="W-FRI"))
    f = out[0].append(out[1:]) if len(out) > 1 else out[0]
    return pd.DatetimeIndex(sorted(f))


def event_table(era, fr_file):
    """One row per (Friday, coin): D, V30, F, r, sigma, the trade prices of each rule and the venue."""
    FR = pd.read_csv(fr_file, parse_dates=["date"])
    days = fridays(era)
    rows = []
    for coin in ("BTC", "ETH"):
        for lo, hi in RANGES[era]:
            lo_l = pd.Timestamp(lo) - pd.Timedelta(days=31)          # lookback (2021 / 2024 / DEV: never HOLD for sel)
            hi_l = pd.Timestamp(hi) + pd.Timedelta(days=1)
            sp = spot(coin, lo_l, hi_l)
            cf = load("cfm", coin, max(lo_l, pd.Timestamp("2025-07-18")), hi_l) if hi_l > CFM_FIRST_EVENT else None
            cv = sp.volume.cumsum()
            for day in days[(days >= pd.Timestamp(lo)) & (days <= pd.Timestamp(hi))]:
                t729, t730, t800 = (day + pd.Timedelta(hours=7, minutes=29), day + pd.Timedelta(hours=7, minutes=30),
                                    day + pd.Timedelta(hours=8))
                t801, t900 = day + pd.Timedelta(hours=8, minutes=1), day + pd.Timedelta(hours=9)
                # V30: spot volume of candles in [t729 - 30d, t729)
                a = cv[cv.index < t729 - pd.Timedelta(days=30)]
                b = cv[cv.index < t729]
                v30 = (float(b.iloc[-1]) - (float(a.iloc[-1]) if len(a) else 0.0)) / 1440.0
                # P(t) = last close before t; sigma of 30-minute log returns over the 30 days before 07:30
                grid = pd.date_range(t730 - pd.Timedelta(days=30), t730, freq="30min")
                px = sp.close[(sp.index >= grid[0] - pd.Timedelta(hours=1)) & (sp.index < t800)]
                pos = np.searchsorted(px.index.values, grid.values, side="left") - 1   # last candle with ts < t
                pg = np.where(pos >= 0, px.to_numpy()[np.maximum(pos, 0)], np.nan)
                sig = float(np.nanstd(np.diff(np.log(pg)), ddof=1))
                p730 = float(px[px.index < t730].iloc[-1])
                p800 = float(px[px.index < t800].iloc[-1])
                r = p800 / p730 - 1.0

                def op_spot(t):
                    w = sp.open[(sp.index >= t) & (sp.index < t + pd.Timedelta(minutes=5))]
                    return float(w.iloc[0]) if len(w) else np.nan

                def op_cfm(t):
                    return float(cf.open.at[t]) if (cf is not None and t in cf.index) else np.nan

                row = dict(date=day, coin=coin, v30=v30, r=r, sig=sig, lr=math.log(1 + r),
                           sp730=op_spot(t730), sp800=op_spot(t800), sp801=op_spot(t801), sp900=op_spot(t900),
                           cf730=op_cfm(t730), cf800=op_cfm(t800), cf801=op_cfm(t801), cf900=op_cfm(t900))
                f = FR[(FR.date == day) & (FR.cur == coin)]
                row["D"] = float(f.D.iloc[0]) if len(f) else np.nan
                row["n_exp"] = float(f.n_exp.iloc[0]) if len(f) else np.nan
                rows.append(row)
    E = pd.DataFrame(rows)
    E["F"] = E.D / E.v30
    E["mq"] = (E.date + pd.Timedelta(days=7)).dt.month != E.date.dt.month
    return E


def thresholds(E_dev):
    """DEV median of |F| per coin and event set."""
    th = {}
    for ev in EVSETS:
        for coin in ("BTC", "ETH"):
            e = E_dev[(E_dev.coin == coin) & (E_dev.mq if ev == "mq" else True)]
            th[f"{ev}|{coin}"] = float(e.F.abs().median())
    return th


def trades(E, rule, ev, assets, th):
    """The variant's trades: one row per (Friday, coin) that fires, with side and the venue's entry/exit prices."""
    coins = ["BTC"] if assets == "BTC" else ["BTC", "ETH"]
    e = E[E.coin.isin(coins)].copy()
    if ev == "mq":
        e = e[e.mq]
    if rule in ("with", "fade"):
        thr = e.coin.map(lambda c: th[f"{ev}|{c}"])
        fire = e.F.notna() & (e.F.abs() >= thr) & (e.F != 0)
        side = np.sign(e.F) * (1 if rule == "with" else -1)
    else:
        fire = e.sig.notna() & (e.lr.abs() >= e.sig)
        side = -np.sign(e.r)
    e = e[fire].assign(side=side[fire])
    t_in, t_out = ("730", "800") if rule == "with" else ("801", "900")
    use_cf = (e.date >= CFM_FIRST_EVENT) & e[f"cf{t_in}"].notna() & e[f"cf{t_out}"].notna()
    e["venue"] = np.where(use_cf, "cfm", "spot")
    e["p_in"] = np.where(use_cf, e[f"cf{t_in}"], e[f"sp{t_in}"])
    e["p_out"] = np.where(use_cf, e[f"cf{t_out}"], e[f"sp{t_out}"])
    e["hours"] = 0.5 if rule == "with" else 59 / 60
    e["n_assets"] = len(coins)
    return e[e.side != 0]


def sleeve(T, capital, mult, days):
    """Daily returns on `capital` of a trade list at cost multiplier `mult` (whole contracts, perp costs)."""
    pnl = pd.Series(0.0, index=pd.DatetimeIndex(days))
    rows = []
    for t in T.itertuples():
        size = costs.PERP[t.coin][1]
        if not (np.isfinite(t.p_in) and np.isfinite(t.p_out)) or not costs.contract_ok(t.coin, t.p_in):
            rows.append((t.date, t.coin, 0, 0.0))
            continue
        n = math.floor(capital / t.n_assets / (t.p_in * size))
        if n <= 0:
            rows.append((t.date, t.coin, 0, 0.0))
            continue
        q = n * size
        gross = t.side * q * (t.p_out - t.p_in)
        c_in = costs.perp_cost_bp(t.coin, t.p_in, taker=True, mult=mult) / 1e4 * q * t.p_in
        c_out = costs.perp_cost_bp(t.coin, t.p_out, taker=True, mult=mult) / 1e4 * q * t.p_out
        fund = costs.perp_funding_bp(t.hours, mult=mult) / 1e4 * q * t.p_in
        p = gross - c_in - c_out - fund
        pnl.loc[t.date] += p
        rows.append((t.date, t.coin, n, p))
    L = pd.DataFrame(rows, columns=["date", "coin", "contracts", "pnl"])
    return pnl / capital, L


def dev(era):
    assert era == "sel", "dev runs are fixed to the sel era"
    E = event_table("sel", os.path.join(OUT, "derived", "fridays_dev.csv"))
    assert E.date.max() <= pd.Timestamp("2026-03-31") and E.date.min() >= pd.Timestamp("2025-01-01")
    th = thresholds(E)
    days = pd.date_range("2025-01-01", "2026-03-31", freq="D")
    res = []
    for rule in RULES:
        for ev in EVSETS:
            for assets in ASSETS:
                v = f"{rule}|{ev}|{assets}"
                T = trades(E, rule, ev, assets, th)
                s50, L = sleeve(T, 50000, 2.0, days)
                G.assert_dev_only(s50)
                scr = G.dev_screen_b(s50)
                n_ev = int(L[L.contracts > 0].date.nunique())
                G.log_trial("exp", v, G.dev_book(s50), "B", scr["t_alpha"], note="EXP DEV trial (sleeve $50K, 2x)",
                            events=n_ev, n_trades=int((L.contracts > 0).sum()),
                            n_cfm=int((T.venue == "cfm").sum()), sleeve_sharpe=scr["sleeve_sharpe"],
                            book_gain=scr["book_gain"], corr=scr["corr"])
                s50_1x, _ = sleeve(T, 50000, 1.0, days)
                res.append(dict(variant=v, rule=rule, evset=ev, assets=assets, events=n_ev,
                                trades=int((L.contracts > 0).sum()), n_cfm=int((T.venue == "cfm").sum()),
                                t_alpha=scr["t_alpha"], sleeve_sharpe=scr["sleeve_sharpe"], book_gain=scr["book_gain"],
                                corr=scr["corr"], total_ret_2x=float(s50.sum()), total_ret_1x=float(s50_1x.sum()),
                                eligible=n_ev >= MIN_EVENTS[ev]))
                print(res[-1], flush=True)
    R = pd.DataFrame(res)
    R.to_csv(os.path.join(OUT, "dev_trials.csv"), index=False)
    E.to_csv(os.path.join(OUT, "dev_events.csv"), index=False)
    json.dump(th, open(os.path.join(OUT, "dev_thresholds.json"), "w"), indent=1)
    return R, th


if __name__ == "__main__":
    if sys.argv[1] == "dev":
        dev(sys.argv[2])
    else:
        raise SystemExit("hold: implemented after the freeze in exp_hold.py")
