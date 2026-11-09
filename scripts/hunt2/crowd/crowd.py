#!/usr/bin/env python3
"""Edge hunt 2, CROWD (Path A): skip a coin's 4-sigma bids on UTC day d when its perp-funding statistic for day d - 1
is below a threshold (reports/hunt2/crowd/SPEC.md). Leveraged longs crowded (funding > 0) means a selloff liquidates
them (forced flow the ladder is paid to absorb); shorts crowded means the sellers are voluntary.

Data: Hyperliquid daily funding, data/funding/<COIN>.csv (date, funding_daily), from 2023-05-12. The value for UTC day
d - 1 is known at 00:00 UTC of day d.

Grid (8 trials): source in {coin, btc} x statistic in {prev (day d - 1), m7 (mean of days d - 7 .. d - 1)} x threshold
in {0, q25 = the DEV 25th percentile of the statistic over the coin-days on which a research parent filled}.
Skip: every minute of day d for the coin (multiplier frozen_sim.SKIP in the T x NC array of frozen_sim.arrays(era)).

Pre-trial definitions (fixed before the first DEV trial; the SPEC leaves them to the builder):
  1. Coin series: the coin's own funding where it has a value for the day, else BTC's (the SPEC's PEPE rule: PEPE has
     no kPEPE file, so PEPE is BTC throughout; ZEC before 2025-10-02, XLM before 2024-11-23 and any coin before its
     Hyperliquid listing likewise). Source "btc" uses BTC's series for every coin.
  2. m7 = the mean of the values that exist in d - 7 .. d - 1 (at least one); prev = the value of d - 1. No value -> no
     skip (the filter is off).
  3. q25 = numpy's default (linear) 25th percentile of the statistic over the UNIQUE (coin, UTC day) pairs of the sel
     era's research parents (pathA.parents("sel"): 1,155 parents). Skip when statistic < threshold (strict).
  4. Parents skipped = research parents whose (coin, UTC day of the fill minute) is skipped; the SPEC's eligibility is
     10% <= skipped / 1,155 <= 50%.
  5. Skips are applied only on days inside the era (sel: 2025-01-01 .. 2026-03-31; chk: 2026-04-01 .. 2026-11-05;
     early: 2023-05-13 .. 2023-12-31, the first day with a d - 1 value); the arrays' tail minutes after the era (exits)
     keep multiplier 1. Funding is read only for the window an era needs (sel: 2024-12-20 .. 2026-03-30).
  6. Scored days for the HOLD read: every calendar day of sel and chk, and early from 2023-05-13 (pathA.hold_read
     days=...). The DEV trial scores the sel days (pathA.dev_trial).

HOLD protection: funding is read only inside the era's window; HOLD eras need allow_hold=True, which only
scripts/hunt2/crowd/hold.py passes, after the freeze commit.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/crypto-edge/scripts/hunt2")
import frozen_sim as F  # noqa: E402
import pathA  # noqa: E402

FUND = "/home/claude/crypto-edge/data/funding"
ERA_DAYS = {"sel": (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-03-31")),
            "chk": (pd.Timestamp("2026-04-01"), pd.Timestamp("2026-11-05")),
            "early": (pd.Timestamp("2023-05-13"), pd.Timestamp("2023-12-31"))}
HOLD = ("chk", "early")
ALIAS = {"PEPE": "kPEPE"}
VARIANTS = [dict(src=s, stat=t, thr=h) for s in ("coin", "btc") for t in ("prev", "m7") for h in ("0", "q25")]


def vname(v):
    return f"{v['src']}_{v['stat']}_{v['thr']}"


def check_era(era, allow_hold=False):
    if era not in ERA_DAYS:
        raise ValueError(era)
    if era in HOLD and not allow_hold:
        raise RuntimeError("HOLD era requested before the freeze (reports/hunt2_prereg.md)")


def _read(coin, lo, hi):
    name = ALIAS.get(coin, coin)
    p = os.path.join(FUND, f"{name}.csv")
    if not os.path.exists(p):
        return pd.Series(dtype=float)
    d = pd.read_csv(p, parse_dates=["date"])
    d = d[(d.date >= lo) & (d.date <= hi)]
    return d.set_index("date").funding_daily.astype(float)


def statistic(coins, era, src, stat, allow_hold=False):
    """DataFrame (day x coin) of the statistic for each day of the era (from d - 1 or d - 7 .. d - 1)."""
    check_era(era, allow_hold)
    lo, hi = ERA_DAYS[era]
    a, b = lo - pd.Timedelta(days=12), hi - pd.Timedelta(days=1)      # only the values an era's signals need
    days = pd.date_range(a, hi, freq="D")
    btc = _read("BTC", a, b).reindex(days)
    out = {}
    for c in coins:
        s = btc if src == "btc" else _read(c, a, b).reindex(days).combine_first(btc)
        s = s.where(s.index <= b)                                       # nothing from the era's last day
        if stat == "prev":
            v = s.shift(1)
        else:
            v = s.rolling(7, min_periods=1).mean().shift(1)
        out[c] = v
    X = pd.DataFrame(out)
    return X[(X.index >= lo) & (X.index <= hi)]


def threshold(v, coins_par_dev):
    """v: the variant; coins_par_dev: the sel parents. Returns the threshold value."""
    if v["thr"] == "0":
        return 0.0
    X = statistic(sorted(coins_par_dev.coin.unique()), "sel", v["src"], v["stat"])
    cd = coins_par_dev.assign(day=coins_par_dev.ts.dt.floor("D"))[["coin", "day"]].drop_duplicates()
    vals = np.array([X.at[d, c] for c, d in zip(cd.coin, cd.day)], float)
    vals = vals[np.isfinite(vals)]
    return float(np.percentile(vals, 25))


def skip_frame(era, v, thr, allow_hold=False):
    """Boolean DataFrame (day x coin of the era's arrays): True = skip that coin's bids all day."""
    A = F.arrays(era)
    coins = list(A["coins"])
    X = statistic(coins, era, v["src"], v["stat"], allow_hold)
    return (X < thr).fillna(False) & X.notna()


def mult(era, skip):
    """T x NC multiplier for frozen_sim: SKIP on every minute of a skipped (day, coin)."""
    A = F.arrays(era)
    idx, coins = A["idx"], list(A["coins"])
    m = np.ones(A["want4"].shape)
    day_of = idx.to_numpy().astype("datetime64[D]")
    for j, c in enumerate(coins):
        if c not in skip.columns:
            continue
        sk = skip[c]
        bad = sk.index[sk.to_numpy()].to_numpy().astype("datetime64[D]")
        if len(bad):
            m[np.isin(day_of, bad), j] = F.SKIP
    return m


def n_skipped(era, skip, allow_hold=False):
    check_era(era, allow_hold)
    par = pathA.parents(era)
    lo, hi = ERA_DAYS[era]
    par = par[(par.ts >= lo) & (par.ts < hi + pd.Timedelta(days=1))]
    day = par.ts.dt.floor("D")
    hit = np.array([bool(skip.at[d, c]) if (d in skip.index and c in skip.columns) else False
                    for c, d in zip(par.coin, day)])
    return int(hit.sum()), int(len(par))
