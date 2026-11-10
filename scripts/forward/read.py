#!/usr/bin/env python3
"""Read the forward data (a checkout of the forward-data branch) into DataFrames, de-duplicated.

  python scripts/forward/read.py status --root <checkout> [--days 7]
  python scripts/forward/read.py show book --root <checkout> --start 2026-11-10 --end 2026-11-11

In Python:
  from read import load
  book = load("book", "2026-11-10", "2026-11-12", root="fwd")

Overlap between two collectors (a handover, a restart) is removed here: book, hl and cfm keep one row per key
(coin or product, minute), preferring a successful sample and then the earliest; candles merge the revision logs
of every run and keep a row only where the values differ from the previous sighting of that (coin, minute).
"""
import argparse
import glob
import json
import os
import sys

import pandas as pd

KEYS = {"book": ["coin", "minute"], "hl": ["coin", "minute"], "cfm": ["product_id", "minute"],
        "candles": ["coin", "minute"], "candle_fetch": ["coin", "minute"], "tbar": ["coin", "minute"]}
VALUES = ["open", "high", "low", "close", "volume"]


def files(stream, start, end, root="."):
    days = pd.date_range(pd.Timestamp(start).floor("D"), pd.Timestamp(end).floor("D"), freq="D")
    out = []
    for d in days:
        out += sorted(glob.glob(os.path.join(root, "forward", stream, f"{d:%Y-%m-%d}", "*.parquet")))
    return out


def dedupe(stream, df):
    if df.empty:
        return df
    if stream == "candle_fetch":                        # one row per answer; two overlapping runs keep both
        return df.drop_duplicates(["coin", "minute", "seen"]).sort_values(["coin", "minute", "seen"],
                                                                           kind="stable").reset_index(drop=True)
    if stream == "tbar":                                # overlap: a verified bar first, then the earliest
        df = df.sort_values(["verified", "t"], ascending=[False, True], kind="stable", na_position="last")
        return df.drop_duplicates(["coin", "minute"]).sort_values(["minute", "coin"], kind="stable").reset_index(drop=True)
    if stream == "candles":
        df = df.drop_duplicates(["coin", "minute", "seen"] + VALUES)
        df = df.sort_values(["coin", "minute", "seen"], kind="stable")
        same = (df[VALUES].eq(df[VALUES].shift()).all(axis=1)
                & df.coin.eq(df.coin.shift()) & df.minute.eq(df.minute.shift()))
        df = df[~same].copy()
        df["rev"] = df.groupby(["coin", "minute"], observed=True).cumcount().astype("int16")
        return df.reset_index(drop=True)
    key = KEYS[stream]
    df = df.sort_values(["ok", "t"], ascending=[False, True], kind="stable", na_position="last")
    return df.drop_duplicates(key).sort_values(key[::-1], kind="stable").reset_index(drop=True)


def load(stream, start, end=None, root=".", raw=False):
    """Rows of `stream` whose minute is in [start, end) (end defaults to start + 1 day), de-duplicated."""
    start = pd.Timestamp(start)
    end = pd.Timestamp(end) if end is not None else start + pd.Timedelta(days=1)
    fs = files(stream, start, end, root)
    if not fs:
        return pd.DataFrame()
    parts = []
    for f in fs:
        d = pd.read_parquet(f)
        d["file"] = os.path.basename(f)
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    for c in ("coin", "name", "product_id", "file", "cache", "reason"):
        if c in df:
            df[c] = df[c].astype("category")
    df = df[(df.minute >= start) & (df.minute < end)]
    return df.reset_index(drop=True) if raw else dedupe(stream, df)


def coverage(stream, df):
    """Per UTC day: minutes with data, gaps (runs of missing minutes between first and last), failed rows."""
    if df.empty:
        return []
    if stream == "tbar":                                # a failed row here is an unverified bar
        df = df.assign(ok=df.verified)
    if stream in ("candles", "candle_fetch"):
        m = df.seen.dt.floor("min")                     # the minute each fetch happened
        okm = m
        failed = 0
    else:
        okm = df.loc[df.ok, "minute"] if "ok" in df else df.minute
        failed = int((~df.ok).sum()) if "ok" in df else 0
    out = []
    for day, g in pd.Series(okm.unique()).groupby(pd.Series(okm.unique()).dt.floor("D")):
        mins = pd.DatetimeIndex(sorted(g))
        dd = mins.to_series().diff().dt.total_seconds().div(60).fillna(1)
        gaps = dd[dd > 1] - 1
        sub = df[(df.minute >= day) & (df.minute < day + pd.Timedelta(days=1))]
        out.append(dict(stream=stream, day=f"{day:%Y-%m-%d}", minutes=len(mins), first=f"{mins[0]:%H:%M}",
                        last=f"{mins[-1]:%H:%M}", gaps=len(gaps), gap_minutes=int(gaps.sum()),
                        longest_gap=int(gaps.max()) if len(gaps) else 0,
                        failed_rows=0 if "ok" not in sub else int((~sub.ok).sum()),
                        keys=int(sub[KEYS[stream][0]].nunique())))
    return out


def status(root=".", days=7):
    p = os.path.join(root, "forward", "status.json")
    if os.path.exists(p):
        with open(p) as fh:
            st = json.load(fh)
        print(f"status.json: run {st.get('run')} heartbeat {st.get('heartbeat')} planned end {st.get('planned_end')}")
        print(f"  rows last hour {st.get('rows_last_hour')}")
        print(f"  errors {st.get('errors')}")
        if st.get("refused"):
            print(f"  REFUSED {st['refused']}")
    else:
        print("no forward/status.json")
    stamps = []
    for s in KEYS:
        stamps += [os.path.basename(d) for d in glob.glob(os.path.join(root, "forward", s, "*"))]
    if not stamps:
        print("no data files")
        return []
    last = pd.Timestamp(max(stamps))
    start = max(pd.Timestamp(min(stamps)), last - pd.Timedelta(days=days - 1))
    rows = []
    for s in KEYS:
        rows += coverage(s, load(s, start, last + pd.Timedelta(days=1), root))
    if rows:
        print(pd.DataFrame(rows).to_string(index=False))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("status")
    a1.add_argument("--root", default=".")
    a1.add_argument("--days", type=int, default=7)
    a2 = sub.add_parser("show")
    a2.add_argument("stream", choices=list(KEYS))
    a2.add_argument("--root", default=".")
    a2.add_argument("--start", required=True)
    a2.add_argument("--end", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        status(a.root, a.days)
    else:
        df = load(a.stream, a.start, a.end, a.root)
        pd.set_option("display.width", 250)
        print(df.tail(40).to_string(index=False))
        print(f"{len(df)} rows")


if __name__ == "__main__":
    sys.exit(main())
