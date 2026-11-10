#!/usr/bin/env python3
"""Test of the minute bar built from trades (bot/market.py minute_trades_bar and trades_to_bar). No network.

A fake trades endpoint serves a list of trades newest first, 1000 a page, paged back with the CB-AFTER cursor, with
Date and Age headers. The test checks the bar and the proof of completeness:
  - one page; several pages; a minute with more than 1000 trades;
  - a trade at m belongs to the minute, a trade at m + 60 s does not;
  - trades with equal times are ordered by trade_id;
  - an empty minute that is verified;
  - a first page generated before the minute's end with no later trade (unverified);
  - paging that hits the page cap (unverified);
  - malformed rows (unverified), a page that breaks the cursor rule (error), the venue's list ending (verified).

Usage: python bot/spot/trades_bar_test.py
"""
import os
import sys
from email.utils import format_datetime

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from bot import market as M  # noqa: E402

M0 = pd.Timestamp("2026-11-10 15:04")
E0 = M0 + pd.Timedelta(minutes=1)
FAILS = []


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""))
    if not ok:
        FAILS.append(name)


def iso(t):
    return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def http_date(t):
    return format_datetime(pd.Timestamp(t).tz_localize("UTC").to_pydatetime(), usegmt=True)


class FakeVenue:
    """trades: list of (seconds from M0, price, size); trade ids rise with the list order from id0."""

    def __init__(self, trades, gen=None, age=0, id0=1000, malformed=(), bad_cursor=False):
        self.rows = [dict(time=iso(M0 + pd.Timedelta(seconds=s)), trade_id=id0 + i, price=str(p), size=str(q),
                          side="buy") for i, (s, p, q) in enumerate(trades)]
        for i in malformed:
            self.rows[i] = dict(self.rows[i], price="not a number")
        self.gen = gen if gen is not None else E0 + pd.Timedelta(seconds=6)
        self.age, self.bad_cursor, self.calls = age, bad_cursor, []

    def get(self, url, params):
        self.calls.append(dict(params))
        after = params.get("after")
        rows = sorted(self.rows, key=lambda r: -r["trade_id"])
        if after is not None:
            rows = [r for r in rows if r["trade_id"] < int(after)]
            if self.bad_cursor:
                rows = sorted(self.rows, key=lambda r: -r["trade_id"])
        page = rows[:int(params.get("limit", 1000))]
        hd = {"Date": http_date(self.gen + pd.Timedelta(seconds=self.age)), "Age": str(self.age)}
        if page:
            hd["CB-AFTER"] = str(page[-1]["trade_id"])
        return page, hd


def bar_of(v, **kw):
    return M.minute_trades_bar("BTC", M0, get=v.get, **kw)


# 1. one page: trades before, inside and after the minute
v = FakeVenue([(-5, 99, 1), (0, 100, 1), (10, 103, 2), (30, 98, 1), (59.999, 101, 0.5), (60, 200, 9), (62, 201, 1)])
r = bar_of(v)
check("one page: verified", r["verified"], str(r["reason"]))
check("one page: one request", r["pages"] == 1 and len(v.calls) == 1)
check("one page: bar", r["bar"] == dict(open=100.0, high=103.0, low=98.0, close=101.0, volume=4.5), str(r["bar"]))
check("one page: trade at m is in, trade at m + 60 s is out", r["bar"]["open"] == 100.0 and r["bar"]["high"] < 200)
check("one page: n trades in the minute", r["n"] == 4)
check("one page: newest trade time", r["newest"] == M0 + pd.Timedelta(seconds=62))
check("one page: generation time read from Date minus Age", r["gen"] == E0 + pd.Timedelta(seconds=6))

# 2. several pages; a minute with more than 1000 trades
tr = [(-1, 50, 1)] + [(i * 59.0 / 2500, 100 + (i % 7), 0.01) for i in range(2500)] + [(61, 300, 1)]
v = FakeVenue(tr, age=3)
r = bar_of(v)
check("2500 trades: verified", r["verified"], str(r["reason"]))
check("2500 trades: three pages, cursor from CB-AFTER", r["pages"] == 3 and v.calls[1].get("after") == v.calls[1]["after"]
      and all("after" in c for c in v.calls[1:]), str(v.calls))
check("2500 trades: n", r["n"] == 2500, str(r["n"]))
check("2500 trades: open, close, high, low", (r["bar"]["open"], r["bar"]["close"], r["bar"]["high"], r["bar"]["low"])
      == (100.0, 100.0 + 2499 % 7, 106.0, 100.0), str(r["bar"]))
check("2500 trades: volume", abs(r["bar"]["volume"] - 25.0) < 1e-9, str(r["bar"]["volume"]))

# 3. equal times: ordered by trade_id (the id order, not the list order on the page)
v = FakeVenue([(-1, 1, 1), (20, 111, 1), (20, 222, 1), (59, 333, 1), (59, 444, 1), (70, 5, 1)])
r = bar_of(v)
check("equal times: open is the lower trade id, close the higher", r["bar"]["open"] == 111 and r["bar"]["close"] == 444,
      str(r["bar"]))
rows = [(M0 + pd.Timedelta(seconds=59), 9, 444.0, 1.0), (M0 + pd.Timedelta(seconds=59), 8, 333.0, 1.0),
        (M0 + pd.Timedelta(seconds=1), 7, 1.0, 1.0), (M0 + pd.Timedelta(seconds=1), 7, 1.0, 1.0)]
b = M.trades_to_bar(rows, M0)
check("trades_to_bar: sorts by time then id, drops duplicate ids", b == dict(open=1.0, high=444.0, low=1.0, close=444.0,
                                                                          volume=3.0), str(b))

# 4. an empty minute, verified: a trade before m and one after m + 60 s, nothing inside
v = FakeVenue([(-30, 10, 1), (75, 11, 1)])
r = bar_of(v)
check("empty minute: verified with no bar", r["verified"] and r["bar"] is None and r["n"] == 0, str(r))

# 5. first page generated before the minute's end, no later trade: unverified
v = FakeVenue([(-30, 10, 1), (20, 11, 1)], gen=E0 - pd.Timedelta(seconds=2))
r = bar_of(v)
check("stale first page: unverified", not r["verified"] and r["reason"] == "stale_first_page", str(r["reason"]))
v = FakeVenue([(-30, 10, 1), (20, 11, 1)], gen=E0 - pd.Timedelta(seconds=3), age=4)   # served at E0 + 1 s, Age 4
r = bar_of(v)
check("Age pushes generation before the end: unverified", not r["verified"] and r["gen"] < E0, str(r["gen"]))
v = FakeVenue([(-30, 10, 1), (20, 11, 1)], gen=E0)
r = bar_of(v)
check("first page generated exactly at m + 60 s: verified", r["verified"], str(r["reason"]))
v = FakeVenue([(-30, 10, 1), (20, 11, 1), (60, 12, 1)], gen=E0 - pd.Timedelta(seconds=30))
r = bar_of(v)
check("old first page with a trade at m + 60 s: verified", r["verified"], str(r["reason"]))


def no_date(url, params):
    page, hd = FakeVenue([(-30, 10, 1), (20, 11, 1)]).get(url, params)
    return page, {k: x for k, x in hd.items() if k != "Date"}


r = M.minute_trades_bar("BTC", M0, get=no_date)
check("no Date header and no later trade: unverified", not r["verified"] and r["gen"] is None, str(r["reason"]))

# 6. page cap
v = FakeVenue([(-1, 50, 1)] + [(i * 0.02, 100, 0.01) for i in range(2500)] + [(61, 1, 1)])
r = bar_of(v, max_pages=2)
check("page cap: unverified", not r["verified"] and r["reason"] == "page_cap" and r["pages"] == 2, str(r["reason"]))
check("page cap: a partial bar is still returned", r["bar"] is not None and r["n"] < 2500)

# 7. deadline (time budget) between pages
clock = iter([100.0, 200.0])
r = M.minute_trades_bar("BTC", M0, get=FakeVenue([(-1, 50, 1)] + [(i * 0.02, 100, 0.01) for i in range(2500)]
                                                  + [(61, 1, 1)]).get, deadline=50.0, clock=lambda: next(clock))
check("deadline: unverified with reason deadline after one page", not r["verified"] and r["reason"] == "deadline"
      and r["pages"] == 1, f"{r['reason']} {r['pages']}")

# 8. malformed rows
v = FakeVenue([(-5, 99, 1), (10, 103, 2), (30, 98, 1), (65, 1, 1)], malformed=[2])
r = bar_of(v)
check("malformed row: unverified", not r["verified"] and r["reason"] == "malformed", str(r["reason"]))


def junk(url, params):
    return [{"foo": 1}, {"time": "x"}], {"Date": http_date(E0 + pd.Timedelta(seconds=5))}


r = M.minute_trades_bar("BTC", M0, get=junk)
check("page of junk rows: unverified", not r["verified"] and r["reason"] == "malformed", str(r["reason"]))
try:
    M.minute_trades_bar("BTC", M0, get=lambda u, p: ({"message": "x"}, {}))
    check("a page that is not a list raises", False)
except ValueError:
    check("a page that is not a list raises", True)
try:
    bar_of(FakeVenue([(-1, 50, 1)] + [(i * 0.02, 100, 0.01) for i in range(1500)] + [(61, 1, 1)], bad_cursor=True))
    check("a page with ids at or above the cursor raises", False)
except ValueError:
    check("a page with ids at or above the cursor raises", True)

# 9. the venue's list ends (no trade before m exists): verified
v = FakeVenue([(1, 10, 1), (2, 12, 1), (70, 13, 1)])
r = bar_of(v)
check("list ended: verified after an empty page", r["verified"] and r["pages"] == 2 and r["bar"]["close"] == 12,
      f"{r['reason']} {r['pages']}")

# 10. a refusal propagates (never retried around)
try:
    M.minute_trades_bar("BTC", M0, get=lambda u, p: (_ for _ in ()).throw(M.Refused("HTTP 403")))
    check("a refusal propagates", False)
except M.Refused:
    check("a refusal propagates", True)

print("TRADES BAR TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
sys.exit(1 if FAILS else 0)
