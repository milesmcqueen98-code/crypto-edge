#!/usr/bin/env python3
"""H9 (MC) helpers shared by the fetch and the analysis scripts: the ET calendar (weekdays, US holidays dropped),
the universe, perp-price units, and a print fetcher that pages without losing prints.

Why a fetcher subclass (logged as a deviation and reported as a shared-code problem): common.TradeFetcher.window
pages backward with end = int(oldest print time). The endpoint excludes prints at or after `end`, so every print in
[int(t_min), t_min) is lost at each page boundary. Pilot 2 (reports/hunt/h9mc/pilot2.json) showed ETH on 2026-03-11
losing 4,865 of the 5,709 contracts of the 16:00 ET minute. The subclass re-requests the boundary second
(end = floor(t_min) + 1) and de-duplicates by trade id; completeness is checked against 1-minute candle volume.
common.py itself is not edited.
"""
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

ET = "America/New_York"
FIRST_DAY = pd.Timestamp("2025-07-18")
LAST_DAY = pd.Timestamp("2026-11-05")
DEV_END = pd.Timestamp("2026-05-31")          # last DEV day (gates.HOLD0 = 2026-06-01)

# US market holidays (NYSE/CME full closures) in the perps' life: no intraday-margin window on these days.
US_HOLIDAYS = pd.DatetimeIndex([
    "2025-07-04",  # Independence Day (before the first perp day; listed for completeness)
    "2025-09-01",  # Labor Day
    "2025-11-27",  # Thanksgiving
    "2025-12-25",  # Christmas
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # Martin Luther King Jr. Day
    "2026-02-16",  # Presidents' Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
])

# Perps with 1-minute candles in data/cfm. AVAX is left out: its contract is worth < $150 on every day since launch
# (the pre-registered universe rule). BNB, DOT and SHIB have no data/cfm candles (and DOT/SHIB fail the $150 rule).
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "LINK", "ADA", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE",
         "HYPE", "ENA", "PEPE", "ONDO", "ZEC"]
MAJORS = ["BTC", "ETH"]

# data/cfm prices (and CDE prints) for PEPE are quoted per 1,000 PEPE, while common.PERP's contract size (1e8) is in
# PEPE units. Multiply perp prices by this factor to get USD per coin (the unit common.perp_cost_bp expects).
PX_PER_COIN = {"PEPE": 1e-3}

# Fetch windows (ET clock): the control hour (Step 1), and the 4 pm window through the latest exit (17:00) plus slack.
CTRL = ("13:30", "14:30")
FOUR = ("15:30", "17:30")


def px_coin(coin, perp_price):
    return perp_price * PX_PER_COIN.get(coin, 1.0)


def launch_day(coin):
    """First full ET weekday after the perp's first candle."""
    p = common.load_perp(coin)
    t0 = p.index.min().tz_localize("UTC").tz_convert(ET)
    return (t0.normalize() + pd.Timedelta(days=1)).tz_localize(None)


def weekdays(start, end):
    d = pd.date_range(start, end, freq="D")
    d = d[d.weekday < 5]
    return d[~d.isin(US_HOLIDAYS)]


def et_to_utc(day, hhmm):
    """Naive UTC timestamp of an ET wall-clock time on `day` (DST-aware)."""
    return pd.Timestamp(f"{pd.Timestamp(day).date()} {hhmm}").tz_localize(ET).tz_convert("UTC").tz_localize(None)


class Fetcher(common.TradeFetcher):
    """common.TradeFetcher with loss-free paging (see module docstring)."""

    def window(self, pid, start, end):
        s = int(pd.Timestamp(start).timestamp())
        e = int(pd.Timestamp(end).timestamp())
        seen, rows, lost = set(), [], 0
        while e > s:
            tr = self._get(pid, s, e)
            new = [t for t in tr if t["trade_id"] not in seen]
            for t in new:
                seen.add(t["trade_id"])
                rows.append(t)
            if len(tr) < 1000:
                break
            tmin = min(pd.Timestamp(t["time"]).timestamp() for t in tr)
            e_next = int(math.floor(tmin)) + 1          # re-request the boundary second; ids de-duplicate
            if e_next >= e or not new:                   # >= 1000 prints inside one second: step past it
                lost += 1
                e_next = int(math.floor(tmin)) if int(math.floor(tmin)) < e else e - 1
            e = e_next
        self.lost = lost
        if not rows:
            return pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
        d = pd.DataFrame(rows)
        d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.tz_convert(None)
        d["price"] = d["price"].astype(float)
        d["size"] = d["size"].astype(float)
        d = d[(d.time >= pd.Timestamp(start)) & (d.time < pd.Timestamp(end))]
        return d[["trade_id", "time", "price", "size", "side"]].sort_values(["time", "trade_id"]).reset_index(drop=True)


def all_days(start, end):
    """Every calendar day: trading weekdays plus the placebo days (weekends and US holidays: no intraday margin)."""
    return pd.date_range(start, end, freq="D")


def is_trading_day(day):
    day = pd.Timestamp(day)
    return day.weekday() < 5 and day not in US_HOLIDAYS


def load_prints(root=None):
    """All fetched prints (data/hunt/h9mc/prints_*.parquet): coin, t (naive UTC), price (as quoted), size
    (contracts), aggsell (1 = aggressive seller, i.e. maker side BUY), win (0 control, 1 4-pm window)."""
    import glob
    root = root or os.path.join(common.ROOT, "data", "hunt", "h9mc")
    parts = [pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(root, "prints_*.parquet")))]
    d = pd.concat(parts, ignore_index=True)
    d["t"] = pd.to_datetime(d["t_us"], unit="us")
    return d.drop(columns="t_us").sort_values(["coin", "t"]).reset_index(drop=True)


def basis_frame(coin):
    """Minute frame with perp and spot closes and H1's basis residual (SPEC: H1 definition):
    b = log(perp/spot) on minutes where both traded; bbar = trailing 24 h median of b known at t-1;
    e = b - bbar; sig = trailing 3-day std of e known at t-1; F = spot close at t-1 * exp(bbar)."""
    p = common.load_perp(coin)
    s = common.load_minute(coin)
    pc = px_coin(coin, p["close"].astype(float))
    j = pd.concat([pc.rename("pc"), s["close"].astype(float).rename("sc")], axis=1, join="inner").dropna()
    j = j[(j.pc > 0) & (j.sc > 0)]
    b = np.log(j.pc / j.sc)
    med = b.rolling("1440min", min_periods=60).median()
    bbar = med.shift(1)                                   # known at the previous observed minute (<= t-1)
    e = b - bbar
    sig = e.rolling("4320min", min_periods=600).std().shift(1)
    out = pd.DataFrame({"pc": j.pc, "sc": j.sc, "b": b, "bbar": bbar, "e": e, "sig": sig})
    return out
