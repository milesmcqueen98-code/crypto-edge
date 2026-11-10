#!/usr/bin/env python3
"""Test of the candle merge in Engine.update_spot. No network, no keys.

Each minute the bot re-fetches the last three minutes and merges them into its stored table. If the re-fetch leaves out
a minute that the stored table has, the merged index used to be out of order, and cutting the window then raised
KeyError when the left edge label was not in the index. The fix sorts the index before the cut.

This test checks that:
  1. the old three lines raise on such a merge and the real update_spot does not;
  2. the merged table is the sorted, de-duplicated union cut to the window, and re-fetched values win;
  3. a normal merge (nothing omitted) gives exactly the table the old lines gave.

Usage: python bot/spot/merge_test.py
"""
import os
import sys
import types

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from bot.spot import engine as E  # noqa: E402

T0 = pd.Timestamp("2026-11-07 21:00")
COLS = ["open", "high", "low", "close", "volume"]
WINDOW = 7                      # a short window for the test; the engine value is patched in below
FAILS = []


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""))
    if not ok:
        FAILS.append(name)


def candles(minutes, base):
    """Candles at T0 + each minute; close = base + minute so every value tells where it came from."""
    idx = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=m) for m in minutes])
    c = np.array([base + m for m in minutes], dtype=float)
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 10.0}, index=idx)


def old_merge(df, new, end, window):
    """The three old lines of update_spot, copied as they were."""
    df = pd.concat([df, new])
    df = df[~df.index.duplicated(keep="last")]
    if len(df):
        df = df.loc[end - pd.Timedelta(minutes=window):]
    return df


class FakeMarket:
    def __init__(self, frames):
        self.frames = frames

    def spot_candles(self, coin, start, end):
        d = self.frames[coin]
        return d[(d.index >= start) & (d.index < end)]


def run_update(stored, fetched, end, coins):
    """Run the real Engine.update_spot on a stand-in object that has only what the method uses."""
    me = types.SimpleNamespace(spot={c: stored[c].copy() for c in stored}, coins=coins, market=FakeMarket(fetched))
    E.Engine.update_spot(me, end)
    return me.spot


E.WINDOW_MIN = WINDOW
END = T0 + pd.Timedelta(minutes=11)
EDGE = END - pd.Timedelta(minutes=WINDOW)          # T0 + 4

# ---- gap case: stored has minutes 0..9 without minute 4 (the window edge); the re-fetch omits minute 8
stored_gap = candles([m for m in range(10) if m != 4], base=100.0)
fetch_gap = candles([7, 9, 10], base=500.0)        # re-fetch of 7, 9 and the new minute 10; minute 8 is left out
check("setup: left edge label is not in the stored index", EDGE not in stored_gap.index)
check("setup: stored table has minute 8, the re-fetch does not",
      (T0 + pd.Timedelta(minutes=8)) in stored_gap.index and (T0 + pd.Timedelta(minutes=8)) not in fetch_gap.index)

# 1. old lines raise
try:
    old_merge(stored_gap, fetch_gap, END, WINDOW)
    check("old lines raise KeyError on the gap case", False, "no error")
except KeyError as err:
    check("old lines raise KeyError on the gap case", "non-monotonic" in str(err), str(err)[:70])

# real code does not raise
try:
    got = run_update({"BTC": stored_gap, "ETH": stored_gap}, {"BTC": fetch_gap, "ETH": fetch_gap}, END, ["ETH"])
    check("update_spot does not raise on the gap case", True)
except Exception as err:  # noqa: BLE001
    got = None
    check("update_spot does not raise on the gap case", False, repr(err)[:100])

# 2. result is the sorted, de-duplicated union cut to the window, re-fetched values winning
if got is not None:
    union = pd.concat([stored_gap, fetch_gap])
    union = union[~union.index.duplicated(keep="last")].sort_index()
    want = union.loc[EDGE:]
    for c in ("BTC", "ETH"):
        check(f"{c}: index is sorted and unique", got[c].index.is_monotonic_increasing and got[c].index.is_unique)
        check(f"{c}: table equals sorted union cut to the window", got[c].equals(want),
              f"{len(got[c])} rows vs {len(want)}")
        check(f"{c}: first row is at or after the window edge", got[c].index.min() >= EDGE)
        both = [T0 + pd.Timedelta(minutes=m) for m in (7, 9)]
        check(f"{c}: re-fetched values win for minutes in both", (got[c].loc[both, "close"] == [507.0, 509.0]).all())
        check(f"{c}: minute only in stored keeps its stored value",
              got[c].loc[T0 + pd.Timedelta(minutes=8), "close"] == 108.0)
        check(f"{c}: new minute 10 is there", got[c].loc[T0 + pd.Timedelta(minutes=10), "close"] == 510.0)

# ---- normal case: nothing omitted, the re-fetch overlaps the tail of the stored table in order
stored_ok = candles(range(10), base=100.0)
fetch_ok = candles([7, 8, 9, 10], base=500.0)
want_old = old_merge(stored_ok, fetch_ok, END, WINDOW)
got_ok = run_update({"BTC": stored_ok, "ETH": stored_ok}, {"BTC": fetch_ok, "ETH": fetch_ok}, END, ["ETH"])
for c in ("BTC", "ETH"):
    check(f"{c}: normal case equals the old result (values, index, order)", got_ok[c].equals(want_old))
    pd.testing.assert_frame_equal(got_ok[c], want_old)
check("normal case: old result was already sorted", want_old.index.is_monotonic_increasing)

# ---- other branches stay as they were: empty re-fetch, first fill
got_empty = run_update({"BTC": stored_ok}, {"BTC": candles([], 0.0)}, END, [])
check("empty re-fetch: table is only cut to the window", got_empty["BTC"].equals(stored_ok.loc[EDGE:]))
first = run_update({"BTC": pd.DataFrame(columns=COLS)}, {"BTC": candles(range(10), 100.0)}, END, [])
check("first fill: table is the fetch cut to the window", first["BTC"].equals(candles(range(10), 100.0).loc[EDGE:]))

print("MERGE TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
sys.exit(1 if FAILS else 0)
