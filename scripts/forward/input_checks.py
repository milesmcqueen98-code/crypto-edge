#!/usr/bin/env python3
"""Daily input check from the stored forward streams: how good is each newest-bar input against the final candle.

  python scripts/forward/input_checks.py --root fwd --start 2026-11-10 --end 2026-11-12 [--out dir]

Per coin and UTC day:
  trades bar (stream tbar): minutes, share verified, and against the final candle: share exact and share in material
      error (the candle probe's measures 2 and 3), overall and split by trades in the minute;
  first-seen candle (the first revision in `candles`, if seen at the 6 s fetch): missing, exact, material, same split;
  candle answers (`candle_fetch`): share made before the minute they end on had closed, share whose newest minute
      was behind;
  gaps: minutes where the final candle's volume is below the verified trades bar's by more than 0.5%.

Final candle: the last revision in `candles` of a (coin, minute), provided the collector fetched that coin again at
least 180 s after the minute closed (its fetch in minute m + 4 or m + 5, still in the 5-minute window) and that answer
was made at least 180 s after the close (seen minus Age; a cache copy with no Age does not qualify). With no
candle_fetch rows (data before that stream), the fetch at m + 4 only has to exist.

Measures (reports/owner/candle_probe_prereg.md): exact = high, low and close equal and volume within 0.5%; material =
missing, or the close off by more than half that coin's one-minute sigma (the standard deviation of one-minute log
returns of that day's final closes, consecutive minutes only), or the low off by more than 5 bp.
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import read as R  # noqa: E402

BUCKETS = [(0, 5, "0-5"), (6, 20, "6-20"), (21, 50, "21-50"), (51, 100, "51-100"), (101, 10 ** 12, ">100")]
FINAL_AFTER = 180                 # seconds after the minute closed
VOL_TOL = 0.005
LOW_BP = 5.0


def bucket(n):
    if n is None or not np.isfinite(n):
        return "unknown"
    for lo, hi, name in BUCKETS:
        if lo <= n <= hi:
            return name
    return "unknown"


def final_candles(cd, cf):
    """(coin, minute) -> final OHLCV and `present` (False: the final answer holds no candle, a minute without
    trades). Only coin-minutes with a qualifying late fetch are returned."""
    cd = cd.sort_values("seen")
    last = cd.groupby(["coin", "minute"], observed=True)[["open", "high", "low", "close", "volume"]].last()
    if cf is not None and len(cf):
        f = cf.copy()
        f["coin"] = f.coin.astype(str)
        hit = f.cache.astype("string").eq("HIT").fillna(False).to_numpy(bool)
        known = f.age.notna().to_numpy(bool)
        f["gen"] = f.seen - pd.to_timedelta(f.age.where(known, 0.0), unit="s")
        f = f[~hit | known]                                   # a copy of unknown age never qualifies
        out = []
        for k in (4, 5):                                      # candle m is in the window of the fetch in minute m + k
            g = f.assign(m=f.minute - pd.Timedelta(minutes=k))
            g = g[(g.gen >= g.m + pd.Timedelta(seconds=60 + FINAL_AFTER)) & (g.newest >= g.m)]
            out.append(g[["coin", "m"]])
        ok = pd.concat(out).drop_duplicates().rename(columns={"m": "minute"})
    else:                                                     # before candle_fetch: the fetch at m + 4 must exist
        fetched = set(cd.seen.dt.floor("min"))
        ms = sorted(set(cd.minute))
        ok_m = [m for m in ms if m + pd.Timedelta(minutes=4) in fetched]
        coins = sorted(set(cd.coin.astype(str)))
        ok = pd.DataFrame([(c, m) for c in coins for m in ok_m], columns=["coin", "minute"])
    idx = pd.MultiIndex.from_frame(ok[["coin", "minute"]])
    last.index = last.index.set_levels(last.index.levels[0].astype(str), level=0)
    fin = last.reindex(idx)
    fin["present"] = fin.close.notna()
    fin.loc[~fin.present, "volume"] = 0.0
    return fin.sort_index()


def first_seen(cd):
    """The first revision of each (coin, minute) if it was seen at the 6 s fetch (within 60 s of the close)."""
    cd = cd.sort_values("seen")
    first = cd.groupby(["coin", "minute"], observed=True)[["open", "high", "low", "close", "volume", "seen"]].first()
    first.index = first.index.set_levels(first.index.levels[0].astype(str), level=0)
    age = (first.seen - first.index.get_level_values(1)).dt.total_seconds() - 60
    return first[age < 60]


def sigmas(fin):
    """(coin, day) -> one-minute sigma of log returns of that day's final closes (consecutive minutes only)."""
    f = fin[fin.present].reset_index()
    f["day"] = f.minute.dt.floor("D")
    out = {}
    for (c, d), g in f.groupby(["coin", "day"]):
        g = g.sort_values("minute")
        cons = g.minute.diff().eq(pd.Timedelta(minutes=1))
        out[(c, d)] = float(np.log(g.close).diff()[cons].std())
    return out


def compare(x, fin, sig):
    """Per coin-minute with a present final candle: missing, exact, material for candidate rows x (indexed like fin;
    a missing candidate is NaN)."""
    f = fin[fin.present]
    j = f.join(x[["open", "high", "low", "close", "volume"]], rsuffix="_x", how="left")
    day = j.index.get_level_values(1).floor("D")
    s = np.array([sig.get((c, d), np.nan) for c, d in zip(j.index.get_level_values(0), day)])
    present = j.close_x.notna().to_numpy()
    cerr = np.abs(np.log(j.close_x / j.close)).to_numpy()
    lerr = np.abs(np.log(j.low_x / j.low)).to_numpy() * 1e4
    exact = present & (j.high_x == j.high).to_numpy() & (j.low_x == j.low).to_numpy() \
        & (j.close_x == j.close).to_numpy() & (np.abs(j.volume_x / j.volume - 1) <= VOL_TOL).to_numpy()
    with np.errstate(invalid="ignore"):
        material = ~present | (cerr > 0.5 * s) | (lerr > LOW_BP)
    return pd.DataFrame(dict(missing=~present, exact=exact, material=material), index=j.index)


def pct(x):
    return round(float(np.mean(x)) * 100, 2) if len(x) else np.nan


def daily(root, start, end):
    """Returns (daily table, split by trades in the minute, gaps list)."""
    cd = R.load("candles", start, end, root=root)
    if cd.empty:
        raise SystemExit("no candles in the range")
    cf = R.load("candle_fetch", start, end, root=root)
    tb = R.load("tbar", start, end, root=root)
    fin = final_candles(cd, cf)
    sig = sigmas(fin)
    first = first_seen(cd)
    if len(tb):
        tb = tb.copy()
        tb["coin"] = tb.coin.astype(str)
        tbi = tb.set_index(["coin", "minute"])
        ver = tbi[tbi.verified]
        vx = ver[["open", "high", "low", "close", "volume"]]
        n = tbi.n.reindex(fin.index)
    else:
        tbi = ver = vx = None
        n = pd.Series(np.nan, index=fin.index)
    cmp_first = compare(first, fin, sig)
    cmp_tb = compare(vx, fin.loc[fin.index.intersection(ver.index)], sig) if vx is not None else None
    rows, split, gaps = [], [], []
    keys = sorted({(c, m.floor("D")) for c, m in fin.index})
    for c, d in keys:
        sel = lambda df: df[(df.index.get_level_values(0) == c) & (df.index.get_level_values(1).floor("D") == d)]
        fcd = sel(fin)
        r = dict(coin=c, day=f"{d:%Y-%m-%d}", final_minutes=len(fcd), final_with_trades=int(fcd.present.sum()))
        if tbi is not None:
            t = sel(tbi)
            r.update(tbar_minutes=len(t), tbar_verified=pct(t.verified))
            m = sel(cmp_tb)
            r.update(tbar_compared=len(m), tbar_exact=pct(m.exact), tbar_material=pct(m.material))
        f1 = sel(cmp_first)
        r.update(first_compared=len(f1), first_missing=pct(f1.missing), first_exact=pct(f1.exact),
                 first_material=pct(f1.material))
        if len(cf):
            a = cf[(cf.coin.astype(str) == c) & (cf.minute.dt.floor("D") == d)]
            hit = a.cache.astype("string").eq("HIT").fillna(False).to_numpy(bool)
            known = a.age.notna().to_numpy(bool)
            gen = a.seen - pd.to_timedelta(a.age.where(known, 0.0), unit="s")
            unknown = hit & ~known
            r.update(answers=len(a), made_before_close=pct((gen < a.minute).to_numpy() & ~unknown),
                     age_unknown=pct(unknown),
                     newest_behind=pct((a.newest.isna() | (a.newest < a.minute - pd.Timedelta(minutes=1))).to_numpy()))
        # venue-wide gaps: verified trades bar with trades, final candle short of its volume (or absent)
        if ver is not None:
            v = sel(ver[ver.n > 0])
            fj = fcd.reindex(v.index)
            short = fj.volume.notna() & (fj.volume < v.volume * (1 - VOL_TOL))
            for (cc, mm), row in v[short].iterrows():
                gaps.append(dict(day=f"{d:%Y-%m-%d}", coin=cc, minute=mm, trades=int(row.n), tbar_volume=row.volume,
                                 final_volume=float(fj.loc[(cc, mm), "volume"]),
                                 final_candle=bool(fj.loc[(cc, mm), "present"])))
            r["gaps"] = int(short.sum())
        rows.append(r)
        for name, m in (("tbar", sel(cmp_tb) if cmp_tb is not None else None), ("first_seen", f1)):
            if m is None or not len(m):
                continue
            b = n.reindex(m.index).map(bucket)
            for bk, g in m.groupby(b.to_numpy()):
                split.append(dict(coin=c, day=f"{d:%Y-%m-%d}", input=name, trades=bk, minutes=len(g),
                                  exact=pct(g.exact), material=pct(g.material)))
    return pd.DataFrame(rows), pd.DataFrame(split), pd.DataFrame(gaps)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", default=None, help="exclusive; default start + 1 day")
    ap.add_argument("--out", default=None, help="folder for input_checks_daily.csv, _by_trades.csv, _gaps.csv")
    a = ap.parse_args(argv)
    start = pd.Timestamp(a.start)
    end = pd.Timestamp(a.end) if a.end else start + pd.Timedelta(days=1)
    d, s, g = daily(a.root, start, end)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(d.to_string(index=False))
    print()
    print(s.to_string(index=False) if len(s) else "no split")
    print()
    print(g.to_string(index=False) if len(g) else "no gaps")
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        d.to_csv(os.path.join(a.out, "input_checks_daily.csv"), index=False)
        s.to_csv(os.path.join(a.out, "input_checks_by_trades.csv"), index=False)
        g.to_csv(os.path.join(a.out, "input_checks_gaps.csv"), index=False)


if __name__ == "__main__":
    sys.exit(main())
