#!/usr/bin/env python3
"""H7 (UL): compact daily price tables from Coinbase bars (no statistics are computed here).

Sources (read-only, /home/claude/crypto-edge/data via common.DATA):
  spot  1-minute: data/minute_early (2021-2023), data/minute (2024-2026); hourly data/hourly where a coin lacks minutes
  perp  1-minute: data/cfm (from each perp's launch); volume converted from contracts to coin units
  daily closes:   data/prices/<COIN>.csv (Coinbase daily candles; used for betas and the event study)

For each UTC day D in [start, end]:
  m00 = last trade before D 00:00 (close of the last bar starting before D 00:00; NaN if > 48 h stale)
  p16 = first trade at or after D 16:00 (open of the first bar starting at/after D 16:00; NaN if > 120 min late)
  v16 = coin volume traded in [D 16:00, D 17:00)
Only bars starting before `end` 00:00 are read, so a DEV build (end = 2026-06-01) never sees a HOLD price.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402

H48, M120, M60 = np.timedelta64(48, "h"), np.timedelta64(120, "m"), np.timedelta64(60, "m")


def _daily(ts, op, cl, vol, days):
    D = days.values.astype("datetime64[ns]")
    n = len(D)
    m00, p16 = np.full(n, np.nan), np.full(n, np.nan)
    i = np.searchsorted(ts, D, side="left") - 1
    ok = i >= 0
    m00[ok] = cl[i[ok]]
    stale = np.zeros(n, bool)
    stale[ok] = (D[ok] - ts[i[ok]]) > H48
    m00[stale] = np.nan
    t16 = D + np.timedelta64(16, "h")
    j = np.searchsorted(ts, t16, side="left")
    okj = j < len(ts)
    p16[okj] = op[j[okj]]
    late = np.ones(n, bool)
    late[okj] = (ts[j[okj]] - t16[okj]) > M120
    p16[late] = np.nan
    cv = np.concatenate([[0.0], np.cumsum(vol)])
    v16 = cv[np.searchsorted(ts, t16 + M60, side="left")] - cv[np.searchsorted(ts, t16, side="left")]
    return pd.DataFrame({"m00": m00, "p16": p16, "v16": v16}, index=days)


def _bars(path, start, end, mult=1.0):
    if not os.path.exists(path):
        return None
    cols = ["ts", "open", "close", "volume"]
    if path.endswith(".parquet"):
        lo = (start - pd.Timedelta(days=3)).to_pydatetime()
        d = pd.read_parquet(path, columns=cols, filters=[("ts", ">=", lo), ("ts", "<", end.to_pydatetime())])
    else:
        d = pd.read_csv(path, usecols=cols, parse_dates=["ts"])
    d = d[(d.volume > 0) & (d.ts >= start - pd.Timedelta(days=3)) & (d.ts < end)]
    if d.empty:
        return None
    d = d.drop_duplicates("ts").sort_values("ts")
    return (d.ts.values.astype("datetime64[ns]"), d.open.to_numpy(float), d.close.to_numpy(float),
            d.volume.to_numpy(float) * mult)


def spot_table(coin, start, end):
    days = pd.date_range(start, end, freq="D")
    parts = []
    for src in ("minute_early", "minute"):
        b = _bars(os.path.join(common.DATA, src, f"{coin}.parquet"), start, end)
        if b is not None:
            parts.append(b)
    out = pd.DataFrame(np.nan, index=days, columns=["m00", "p16", "v16"])
    out["src"] = ""
    if parts:
        ts, op, cl, vol = (np.concatenate(x) for x in zip(*parts))
        o = np.argsort(ts, kind="stable")
        t = _daily(ts[o], op[o], cl[o], vol[o], days)
        for c in ("m00", "p16", "v16"):
            out[c] = t[c]
        out.loc[t.m00.notna() | t.p16.notna(), "src"] = "minute"
        del parts, ts, op, cl, vol
    hb = _bars(os.path.join(common.DATA, "hourly", f"{coin}.csv.gz"), start, end)
    if hb is not None:
        th = _daily(*hb, days)
        fill = out.m00.isna() & out.p16.isna()
        for c in ("m00", "p16", "v16"):
            out.loc[fill, c] = th.loc[fill, c]
        out.loc[fill & (th.m00.notna() | th.p16.notna()), "src"] = "hourly"
    return out


def perp_table(coin, start, end):
    if coin not in common.PERP:
        return None, None
    b = _bars(os.path.join(common.DATA, "cfm", f"{coin}.parquet"), start, end, mult=common.PERP[coin][1])
    if b is None:
        return None, None
    days = pd.date_range(start, end, freq="D")
    first = pd.Timestamp(b[0][0])
    live = first.normalize() + pd.Timedelta(days=1)          # first full UTC day of perp trading
    t = _daily(*b, days)
    t.loc[t.index < live, ["m00", "p16", "v16"]] = np.nan
    t["src"] = "perp"
    return t, live


def daily_closes(coin, end):
    """Price at D 00:00 for each day D (= close of Coinbase's daily candle dated D - 1), D <= end."""
    p = os.path.join(common.DATA, "prices", f"{coin}.csv")
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, usecols=["date", "close"], parse_dates=["date"])
    s = pd.Series(d.close.to_numpy(float), index=d.date + pd.Timedelta(days=1))
    s = s[~s.index.duplicated()].sort_index()
    return s[s.index <= end]


def build(coins, start, end):
    P = {}
    for c in coins:
        sp = spot_table(c, start, end)
        pp, live = perp_table(c, start, end)
        P[c] = dict(spot=sp, perp=pp, live=live, close=daily_closes(c, end))
    return P
