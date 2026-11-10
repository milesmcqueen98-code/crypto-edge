#!/usr/bin/env python3
"""Offline tests for the forward collector (no network). Run: python scripts/forward/test_collector.py"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collector as C  # noqa: E402
import handover as H  # noqa: E402
import read as R  # noqa: E402

T = pd.Timestamp("2026-11-10 13:55:00")

EXCHANGE_BOOK = {"bids": [["100.00", "1.0", 3], ["99.50", "2.0", 1], ["98.00", "10", 2], ["90.00", "100", 1]],
                 "asks": [["100.10", "1.5", 1], ["100.50", "3", 2], ["102.00", "4", 1]], "sequence": 1}
ADV_BOOK = {"pricebook": {"product_id": "X-USD", "bids": [{"price": "100", "size": "1"}, {"price": "99", "size": "2"}],
                          "asks": [{"price": "101", "size": "5"}], "time": "2026-11-10T13:55:04Z"}}
CANDLES = [[int(pd.Timestamp("2026-11-10 13:54").timestamp()), 99, 101, 100, 100.5, 7.0],
           [int(pd.Timestamp("2026-11-10 13:53").timestamp()), 98, 100, 99, 99.5, 3.0],
           [int(pd.Timestamp("2026-11-10 13:55").timestamp()), 1, 1, 1, 1, 1.0]]    # outside the window: dropped
HL = [{"universe": [{"name": "BTC", "szDecimals": 5}, {"name": "kPEPE", "szDecimals": 0}, {"name": "OLD", "isDelisted": True},
                    {"name": "ETH"}, {"name": "kBONK"}]},
      [{"funding": "0.0000125", "openInterest": "42114.7", "prevDayPx": "74569.0", "dayNtlVlm": "2571963236.49",
        "premium": "-0.000549", "oraclePx": "73951.6", "markPx": "73921.0", "midPx": "73910.5",
        "impactPxs": ["73910.0", "73911.0"]},
       {"funding": "0.00001", "openInterest": "5e9", "markPx": "0.0061", "oraclePx": "0.0061", "midPx": None,
        "impactPxs": None, "dayNtlVlm": "1", "premium": None, "prevDayPx": "0.006"},
       {"funding": "0", "openInterest": "0"}, {"funding": "0.00002", "markPx": "2200"}, {"funding": "0", "markPx": "0.02"}]]
CFM = {"num_products": 3, "products": [
    {"product_id": "BIP-20DEC30-CDE", "price": "75740", "volume_24h": "874769", "approximate_quote_24h_volume": "6.6e8",
     "display_name": "BTC PERP", "best_bid_price": "", "mid_market_price": "75741", "trading_disabled": False,
     "future_product_details": {"contract_root_unit": "BTC", "contract_size": "0.01", "contract_expiry_type": "EXPIRING",
                                "funding_interval": "3600s", "open_interest": "210620", "funding_rate": "0.000006",
                                "funding_time": "2026-11-06T13:00:00Z", "index_price": "75732.59",
                                "intraday_margin_rate": {"long_margin_rate": "0.1", "short_margin_rate": "0.0999"},
                                "overnight_margin_rate": {"long_margin_rate": "0.21", "short_margin_rate": "0.25"},
                                "perpetual_details": {"open_interest": "210620", "funding_rate": ""}}},
    {"product_id": "BIT-27NOV26-CDE", "price": "75975", "display_name": "BTC 27 NOV 26",
     "future_product_details": {"contract_root_unit": "BTC", "contract_expiry_type": "EXPIRING"}},
    {"product_id": "SHP-20DEC30-CDE", "price": "0.00001", "display_name": "SHIB PERP",
     "future_product_details": {"contract_root_unit": "SHIB", "funding_interval": "3600s"}}]}


class FakeHttp:
    """URL substring -> response (dict/list) or an exception instance, or a callable."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []
        self.lock = threading.Lock()

    def request(self, method, url, timeout, **kw):
        with self.lock:
            self.calls.append((time.time(), url, kw.get("params")))
        if kw.get("meta") is not None:                  # what the venue's cache headers would say
            kw["meta"].update(cache="MISS", age=0.0)
        for k, v in self.routes.items():
            if k in url:
                if callable(v):
                    v = v(url, kw)
                if isinstance(v, Exception):
                    raise v
                return json.loads(json.dumps(v))
        raise requests.ConnectionError("no route")


class Parsers(unittest.TestCase):
    def test_exchange_book(self):
        b, a = C.parse_exchange_book(EXCHANGE_BOOK)
        self.assertEqual(b[0], (100.0, 1.0))
        self.assertEqual(len(b), 4)
        self.assertEqual(a[-1], (102.0, 4.0))

    def test_adv_book(self):
        b, a = C.parse_adv_book(ADV_BOOK)
        self.assertEqual(b, [(100.0, 1.0), (99.0, 2.0)])
        self.assertEqual(a, [(101.0, 5.0)])
        self.assertEqual(C.parse_adv_book({}), ([], []))

    def test_candles(self):
        p = C.candle_params(T + pd.Timedelta(seconds=6))
        self.assertEqual(p, {"granularity": 60, "start": "2026-11-10T13:50:00Z", "end": "2026-11-10T13:54:00Z"})
        c = C.parse_candles(CANDLES, T)
        self.assertEqual(sorted(c), [pd.Timestamp("2026-11-10 13:53"), pd.Timestamp("2026-11-10 13:54")])
        self.assertEqual(c[pd.Timestamp("2026-11-10 13:54")], (100.0, 101.0, 99.0, 100.5, 7.0))   # o h l c v

    def test_hl_universe(self):
        rows = C.parse_hl(HL, ["BTC", "PEPE", "OLD", "SOL"], T, T)
        by = {r["coin"]: r for r in rows}
        self.assertEqual(sorted(by), ["BTC", "PEPE"])                       # delisted and unlisted are absent
        self.assertEqual((by["PEPE"]["name"], by["PEPE"]["px_mult"]), ("kPEPE", 1000))
        self.assertTrue(math.isnan(by["PEPE"]["mid"]) and math.isnan(by["PEPE"]["impact_bid"]))
        self.assertAlmostEqual(by["BTC"]["open_interest"], 42114.7)
        self.assertEqual(by["BTC"]["impact_ask"], 73911.0)

    def test_hl_all(self):
        rows = C.parse_hl(HL, None, T, T)
        self.assertEqual(sorted(r["coin"] for r in rows), ["BONK", "BTC", "ETH", "PEPE"])

    def test_cfm(self):
        rows = C.parse_cfm(CFM, None, T, T)
        self.assertEqual([r["product_id"] for r in rows], ["BIP-20DEC30-CDE", "SHP-20DEC30-CDE"])  # no dated future
        r = rows[0]
        self.assertEqual((r["coin"], r["open_interest"], r["funding_rate"], r["funding_interval_s"]),
                         ("BTC", 210620.0, 0.000006, 3600.0))
        self.assertEqual(r["funding_time"], pd.Timestamp("2026-11-06 13:00"))
        self.assertEqual((r["im_long"], r["om_short"]), (0.1, 0.25))
        self.assertTrue(math.isnan(r["best_bid"]) and math.isnan(r["mark_price"]))     # '' and absent -> missing
        self.assertTrue(math.isnan(rows[1]["open_interest"]))
        self.assertEqual(len(C.parse_cfm(CFM, ["BTC"], T, T)), 1)
        df = C.frame("cfm", rows)
        self.assertEqual(str(df.funding_time.dtype), "datetime64[ms]")


class Depth(unittest.TestCase):
    def test_buckets(self):
        bids = [(100.0, 1.0), (99.5, 2.0), (98.0, 10.0), (90.0, 100.0)]
        v = C.depth_buckets(bids, 100.0, "bid", (5, 50, 200, 1000))
        # 5bp: >= 99.95 -> 100; 50bp: >= 99.5 -> 100 + 199 (boundary inclusive); 200bp: + 980; 1000bp: + 9000
        np.testing.assert_allclose(v, [100, 299, 1279, 10279])

    def test_not_reached(self):
        bids = [(100.0, 1.0), (99.0, 1.0)]                 # book ends 100 bp below
        v = C.depth_buckets(bids, 100.0, "bid", (50, 100, 150, 800))
        self.assertEqual(v[0], 100.0)
        self.assertEqual(v[1], 199.0)                       # exactly reached
        self.assertTrue(np.isnan(v[2]) and np.isnan(v[3]))  # not reached: missing, not zero

    def test_zero_but_reached(self):
        # a gap in the book: nothing within 5 bp, but the book goes deeper, so 0 is a real zero
        v = C.depth_buckets([(99.0, 1.0)], 100.0, "bid", (5, 100))
        self.assertEqual(list(v), [0.0, 99.0])

    def test_ask_side(self):
        asks = [(100.5, 2.0), (100.0, 1.0)]                # unsorted on purpose
        v = C.depth_buckets(asks, 100.0, "ask", (5, 50, 100))
        self.assertEqual(v[0], 100.0)
        self.assertEqual(v[1], 301.0)
        self.assertTrue(np.isnan(v[2]))

    def test_empty_side(self):
        r = C.book_row("X", T, [], [(101.0, 1.0)], T, T)
        self.assertEqual((r["n_bid"], r["n_ask"]), (0, 1))
        self.assertTrue(math.isnan(r["mid"]) and math.isnan(r["bid"]))
        self.assertEqual(r["ask"], 101.0)
        self.assertTrue(all(math.isnan(r[f"bid_usd_{b}"]) for b in C.BID_BPS))
        self.assertTrue(all(math.isnan(r[f"ask_usd_{b}"]) for b in C.ASK_BPS))

    def test_one_sided_and_empty_book(self):
        r = C.book_row("X", T, [(100.0, 1.0)], [], T, T)
        self.assertEqual(r["bid"], 100.0)
        self.assertTrue(math.isnan(r["bid_usd_5"]) and math.isnan(r["ask_usd_5"]))
        r = C.book_row("X", T, [], [], T, T)
        self.assertTrue(r["ok"] and r["n_bid"] == 0 and math.isnan(r["mid"]))

    def test_book_row_full(self):
        b, a = C.parse_exchange_book(EXCHANGE_BOOK)
        r = C.book_row("X", T, b, a, T, T)
        self.assertAlmostEqual(r["mid"], 100.05)
        self.assertAlmostEqual(r["bid_reach_bp"], (1 - 90 / 100.05) * 1e4, places=6)
        self.assertAlmostEqual(r["bid_usd_5"], 100.0)
        self.assertAlmostEqual(r["bid_usd_800"], 100 + 199 + 980)  # 90 is 1004 bp below: not inside 800
        self.assertTrue(np.isfinite(r["bid_usd_800"]))
        self.assertAlmostEqual(r["ask_usd_100"], 100.1 * 1.5 + 100.5 * 3)
        df = C.frame("book", [r, C.missing_book_row("Y", T, pd.NaT)])
        self.assertEqual(str(df.bid_usd_5.dtype), "float32")
        self.assertEqual(list(df.ok), [True, False])


class Candles(unittest.TestCase):
    def test_revision_log(self):
        log = C.CandleLog(keep_minutes=10)
        m1, m2 = pd.Timestamp("2026-11-10 13:53"), pd.Timestamp("2026-11-10 13:54")
        s = [pd.Timestamp("2026-11-10 13:55:06") + pd.Timedelta(minutes=i) for i in range(4)]
        r = log.update("BTC", {m1: (1, 2, 0.5, 1.5, 10.0), m2: (1.5, 1.6, 1.4, 1.5, 3.0)}, s[0], s[0])
        self.assertEqual([(x["minute"], x["rev"]) for x in r], [(m1, 0), (m2, 0)])
        r = log.update("BTC", {m1: (1, 2, 0.5, 1.5, 10.0), m2: (1.5, 1.6, 1.4, 1.5, 3.0)}, s[1], s[1])
        self.assertEqual(r, [])                                        # unchanged: no rows
        r = log.update("BTC", {m1: (1, 2, 0.5, 1.5, 10.0), m2: (1.5, 1.6, 1.3, 1.45, 4.5)}, s[2], s[2])
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["minute"], r[0]["rev"], r[0]["low"], r[0]["volume"], r[0]["seen"]), (m2, 1, 1.3, 4.5, s[2]))
        r = log.update("ETH", {m2: (1, 1, 1, 1, 1.0)}, s[2], s[2])        # coins are separate
        self.assertEqual(r[0]["rev"], 0)
        log.prune(m1 + pd.Timedelta(minutes=10.5))
        self.assertNotIn(("BTC", m1), log.last)
        self.assertIn(("BTC", m2), log.last)


class Files(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def rows(self, minute):
        return [C.book_row("BTC", minute, [(100.0, 1.0)], [(101.0, 1.0)], minute, minute + pd.Timedelta(seconds=4))]

    def test_rotation_and_immutability(self):
        c = C.Collector(self.d, "r1", ["BTC"], http=FakeHttp({}), log=lambda m: None)
        for m in ("2026-11-10 10:58", "2026-11-10 10:59", "2026-11-10 11:00"):
            c.emit("book", pd.Timestamp(m), self.rows(pd.Timestamp(m)))
        paths = c.flush(before=pd.Timestamp("2026-11-10 11:00"))      # what the loop does at 11:00:56
        self.assertEqual([os.path.relpath(p, self.d) for p in paths], ["forward/book/2026-11-10/10-r1.parquet"])
        self.assertEqual(len(pd.read_parquet(paths[0])), 2)
        self.assertEqual(c.flush(before=pd.Timestamp("2026-11-10 11:00")), [])   # nothing more for 10:xx
        c.emit("book", pd.Timestamp("2026-11-10 10:59"), self.rows(pd.Timestamp("2026-11-10 10:59")))  # a late row
        p2 = c.flush(before=pd.Timestamp("2026-11-10 11:00"))
        self.assertTrue(p2[0].endswith("10-r1-2.parquet"))            # the first file is never rewritten
        p3 = c.flush()                                                 # exit: the partial 11:00 hour
        self.assertTrue(p3[0].endswith("2026-11-10/11-r1.parquet"))
        df = R.load("book", "2026-11-10", root=self.d)
        self.assertEqual(len(df), 3)                                   # 10:58, 10:59 (deduped), 11:00

    def test_dedupe_overlap(self):
        a = C.Collector(self.d, "runA", ["BTC"], http=FakeHttp({}), log=lambda m: None)
        b = C.Collector(self.d, "runB", ["BTC"], http=FakeHttp({}), log=lambda m: None)
        m = pd.Timestamp("2026-11-10 12:00")
        for i in range(5):
            a.emit("book", m + pd.Timedelta(minutes=i), self.rows(m + pd.Timedelta(minutes=i)))
        for i in range(3, 8):
            rr = self.rows(m + pd.Timedelta(minutes=i))
            rr[0]["t"] += pd.Timedelta(seconds=0.5)
            b.emit("book", m + pd.Timedelta(minutes=i), rr if i != 4 else [C.missing_book_row("BTC", rr[0]["minute"], pd.NaT)])
        # candles: both runs saw 12:03 the same, then B saw a revision; A logged it again a second later
        k = dict(coin="BTC", minute=m + pd.Timedelta(minutes=3), t_req=m, open=1, high=2, low=0.5, close=1.5, rev=0)
        a.emit("candles", m, [dict(k, seen=m + pd.Timedelta(seconds=66), volume=5.0),
                              dict(k, seen=m + pd.Timedelta(seconds=126), volume=6.0, rev=1)])
        b.emit("candles", m, [dict(k, seen=m + pd.Timedelta(seconds=66.4), volume=5.0),
                              dict(k, seen=m + pd.Timedelta(seconds=125), volume=6.0, rev=1)])
        a.flush()
        b.flush()
        df = R.load("book", m, m + pd.Timedelta(hours=1), root=self.d)
        self.assertEqual(len(df), 8)
        self.assertFalse(df.duplicated(["coin", "minute"]).any())
        self.assertTrue(df.ok.all())                                   # 12:04 from A (B's sample failed)
        self.assertEqual(set(df.file), {"12-runA.parquet", "12-runB.parquet"})
        raw = R.load("book", m, m + pd.Timedelta(hours=1), root=self.d, raw=True)
        self.assertEqual(len(raw), 10)
        cd = R.load("candles", m, m + pd.Timedelta(hours=1), root=self.d)
        self.assertEqual(list(cd.volume), [5.0, 6.0])                  # merged revision log
        self.assertEqual(list(cd.rev), [0, 1])
        cov = R.coverage("book", df)
        self.assertEqual((cov[0]["minutes"], cov[0]["gaps"]), (8, 0))

    def test_storage_round_trip(self):
        """The compact writer is lossless: every stream reads back exactly as frame() built it (values, NaN, dtypes
        including categories, datetime64[ms], bool and float32), and t_req is not stored."""
        m = pd.Timestamp("2026-11-10 12:00")
        hl = C.parse_hl(HL, ["BTC", "PEPE"], m, m + pd.Timedelta(seconds=5.3))
        cfm = C.parse_cfm(CFM, None, m, m + pd.Timedelta(seconds=12.1))
        book = self.rows(m) + [C.missing_book_row("ETH", m, m)]
        cl = C.CandleLog().update("BTC", C.parse_candles(CANDLES, T), m, m + pd.Timedelta(seconds=6.7))
        for stream, rows in (("book", book), ("hl", hl), ("cfm", cfm), ("candles", cl)):
            p = C.write_hour(self.d, stream, m, "rt", rows)
            exp = C.frame(stream, rows).sort_values(C.KEYS[stream], kind="stable").reset_index(drop=True)
            back = pd.read_parquet(p)
            empty = [c for c in exp if exp[c].isna().all() and str(exp[c].dtype) == "category"]
            for c in empty:                                            # an all-missing category column (e.g. the
                self.assertTrue(back[c].isna().all())                  # cache status of a fake venue) has no type
            pd.testing.assert_frame_equal(back.drop(columns=empty), exp.drop(columns=empty))
            self.assertNotIn("t_req", exp)
            self.assertEqual(len(R.load(stream, m, root=self.d)), len(exp))


class Streams(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def routes(self, hl):
        def candles(url, kw):                          # two candles inside whatever window was asked for
            e = int(pd.Timestamp(kw["params"]["end"].rstrip("Z")).timestamp())
            return [[e, 99, 101, 100, 100.5, 7.0], [e - 60, 98, 100, 99, 99.5, 3.0]]
        return {"/book": EXCHANGE_BOOK, "/candles": candles, "hyperliquid": hl, "/products": CFM}

    def run_minute(self, c, T0):
        ths = c.launch_minute(T0)
        for th in ths:
            th.join(timeout=60)
        self.assertFalse(any(th.is_alive() for th in ths))

    def offsets(self, wide=True):
        # compress the minute so the test runs in a few seconds
        C.BOOK_DONE, C.BOOK_LATENCY, C.BOOK_LAST_START = 1.5, 0.1, 1.9
        C.HL_AT, C.CANDLE_AT, C.CFM_AT = 1.5, 1.6, 2.0
        C.RETRY_UNTIL.update(hl=3.0, candles=4.0, cfm=4.0)

    def test_failing_stream_does_not_stop_others(self):
        saved = (C.BOOK_DONE, C.BOOK_LATENCY, C.BOOK_LAST_START, C.HL_AT, C.CANDLE_AT, C.CFM_AT, dict(C.RETRY_UNTIL),
                 C.CB_INTERVAL)
        try:
            self.offsets()
            C.CB_INTERVAL = 0.02
            http = FakeHttp(self.routes(requests.ConnectionError("down")))
            coins = ["BTC", "PEPE"]
            c = C.Collector(self.d, "t", coins, http=http, log=lambda m: None)
            c.cb = C.RateLimiter(0.02)
            c.last_names["hl"] = [("BTC", "BTC"), ("PEPE", "kPEPE")]
            T0 = time.time()
            self.run_minute(c, T0)
            m = pd.Timestamp(T0, unit="s")
            buf = {k[0]: v for k, v in c.buf.items()}
            self.assertEqual(sum(r["ok"] for r in buf["book"]), 2)
            self.assertEqual(len(buf["candles"]), 4)                   # 2 coins x 2 candles, first sightings
            cf = buf["candle_fetch"]                                   # one row per candle answer
            self.assertEqual([r["coin"] for r in cf], coins)
            self.assertTrue(all(r["cache"] == "MISS" and r["age"] == 0 and r["newest"] is not pd.NaT for r in cf))
            self.assertTrue(all(r["cache"] == "MISS" for r in buf["book"] if r["ok"]))
            self.assertEqual(len(buf["cfm"]), 2)
            self.assertEqual([r["ok"] for r in buf["hl"]], [False, False])   # missing rows, not stale ones
            self.assertGreaterEqual(c.err["hl:net"], 2)                # retried within the minute
            self.assertEqual(c.err["hl:missing"], 1)
            # timing, as the code guarantees it: no book request starts after BOOK_LAST_START, and candles are
            # requested at or after CANDLE_AT (a tighter bound on the book fails when a busy machine wakes a thread late)
            bt = [t - T0 for t, u, _ in http.calls if "/book" in u]
            ct = [t - T0 for t, u, _ in http.calls if "/candles" in u]
            self.assertTrue(max(bt) <= C.BOOK_LAST_START + 0.3 and min(ct) >= C.CANDLE_AT, (bt, ct))
            # a second minute: candles unchanged -> no rows; a stream that raises a non-HTTP error is contained
            http.routes["/products"] = lambda url, kw: (_ for _ in ()).throw(ValueError("boom"))
            c.buf.clear()
            self.run_minute(c, time.time())
            buf = {k[0]: v for k, v in c.buf.items()}
            self.assertNotIn("candles", buf)
            self.assertEqual(sum(r["ok"] for r in buf["book"]), 2)
            self.assertGreater(c.err["cfm:parse"], 0)
            self.assertEqual([r["ok"] for r in buf["cfm"]], [False, False])
            st = c.status()
            self.assertIn("hl:net", st["errors"])
            self.assertTrue(os.path.exists(os.path.join(self.d, "forward", "status.json")))
            self.assertIn(m.floor("h"), {k[1] for k in c.buf} | {m.floor("h")})
        finally:
            (C.BOOK_DONE, C.BOOK_LATENCY, C.BOOK_LAST_START, C.HL_AT, C.CANDLE_AT, C.CFM_AT, ru, C.CB_INTERVAL) = saved
            C.RETRY_UNTIL.clear()
            C.RETRY_UNTIL.update(ru)

    def test_refused_stops_stream(self):
        http = FakeHttp({"hyperliquid": C.Refused("403 bot check")})
        c = C.Collector(self.d, "t", ["BTC"], http=http, log=lambda m: None)
        c.stop.clear()
        saved = C.HL_AT
        try:
            C.HL_AT = 0
            th = threading.Thread(target=c._guard, args=("hl", c.s_hl, time.time(), pd.Timestamp.now()))
            th.start()
            th.join(10)
        finally:
            C.HL_AT = saved
        self.assertIn("hl", c.refused)
        self.assertEqual(len([1 for _, u, _ in http.calls if "hyperliquid" in u]), 1)   # no retry after a refusal
        self.assertNotIn("hl", [t.name for t in c.launch_minute(time.time() + 3600)])
        c.stop.set()

    def test_rate_limiter(self):
        # grant times as the limiter set them (rl.next - interval, under its lock), not the caller's clock after
        # return: a busy machine can wake a caller late, which shortens the next measured gap but not the grant gap
        rl = C.RateLimiter(0.05)
        grants = []
        for _ in range(6):
            rl.acquire()
            grants.append(rl.next - rl.interval)
        self.assertGreaterEqual(min(np.diff(grants)), 0.05 - 1e-9)
        self.assertFalse(rl.acquire(deadline=time.time() - 1))


class Git(unittest.TestCase):
    """Two publishers on one branch, from stale bases, never conflict and never lose a file."""

    def test_concurrent_publish(self):
        d = tempfile.mkdtemp()
        try:
            bare = os.path.join(d, "remote.git")
            g = lambda *a, cwd=d: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)
            g("init", "-q", "--bare", bare)
            g("config", "uploadpack.allowFilter", "true", cwd=bare)
            seed = os.path.join(d, "seed")
            g("init", "-q", seed)
            g("checkout", "-q", "--orphan", "forward-data", cwd=seed)
            with open(os.path.join(seed, "README.md"), "w") as fh:
                fh.write("data\n")
            g("add", "README.md", cwd=seed)
            g("-c", "user.name=t", "-c", "user.email=t", "commit", "-qm", "init", cwd=seed)
            g("remote", "add", "origin", "file://" + bare, cwd=seed)
            g("push", "-q", "origin", "forward-data", cwd=seed)
            pubs = []
            for name in ("a", "b"):
                wd = os.path.join(d, name)
                C.GitPublisher.setup(wd, "forward-data", repo=seed)
                pubs.append(C.GitPublisher(wd, "forward-data", log=lambda m: None))
            for i, p in enumerate(pubs * 2):                          # a, b, a, b: each starts from a stale tip
                f = os.path.join(p.dir, "forward", "book", f"{i}.parquet")
                os.makedirs(os.path.dirname(f), exist_ok=True)
                with open(f, "w") as fh:
                    fh.write(str(i))
                st = os.path.join(p.dir, "forward", "status.json")
                with open(st, "w") as fh:
                    fh.write(json.dumps({"i": i}))
                p.add([f, st])
                self.assertTrue(p.publish(f"commit {i}"))
            g("fetch", "-q", "origin", cwd=seed)
            tree = g("ls-tree", "-r", "--name-only", "origin/forward-data", cwd=seed).stdout.split()
            self.assertEqual(sorted(tree), ["README.md"] + [f"forward/book/{i}.parquet" for i in range(4)]
                             + ["forward/status.json"])
            st = g("show", "origin/forward-data:forward/status.json", cwd=seed).stdout
            self.assertEqual(json.loads(st), {"i": 3})
            self.assertTrue(pubs[0].publish("nothing new"))            # idempotent
        finally:
            shutil.rmtree(d)


class Handover(unittest.TestCase):
    def test_rule(self):
        self.assertEqual(H.decide(100, []), ("collect", None))
        self.assertEqual(H.decide(100, [100]), ("collect", None))
        self.assertEqual(H.decide(100, [50], predecessor="50"), ("collect", None))   # successor keeps its predecessor
        self.assertEqual(H.decide(50, [50, 100]), ("collect", None))                 # predecessor ignores successor
        self.assertEqual(H.decide(120, [50, 100], predecessor="50"), ("exit", 100))  # a duplicate yields to the older
        self.assertEqual(H.decide(100, [50, 120]), ("exit", 50))                     # scheduled run during normal ops


class FakeVenue:
    """Exchange candles, Exchange trades (3 a page, newest first, paged by `after`) and Advanced candles for a few
    coins. Coin 'GONE' has no trades and no candles."""

    def __init__(self, minutes):
        self.urls = []
        self.bars = {}
        self.trades = {}
        for c in ("AAA", "BBB", "GONE"):
            tl = []
            tid = 1
            for i, m in enumerate(minutes):
                if c == "GONE":
                    continue
                px = [100 + i, 101 + i, 99 + i, 100.5 + i]          # open, high, low, close
                for k, p_ in enumerate(px):
                    tl.append(dict(time=(m + pd.Timedelta(seconds=10 * k + 1)).isoformat() + "Z", trade_id=tid,
                                   price=str(p_), size="0.5", side="buy"))
                    tid += 1
                self.bars[(c, m)] = (px[0], px[1], px[2], px[3], 2.0)
            self.trades[c] = tl[::-1]

    def fetch(self, url, params):
        self.urls.append((url, tuple(sorted(params.items()))))
        return self.request("GET", url, None, params=params), dict(cache="MISS", age=0.0)

    def request(self, method, url, timeout, params=None, **kw):
        coin = url.split("/products/")[1].split("-")[0]
        if url.endswith("/trades"):
            tl = self.trades[coin]
            if params.get("after"):
                tl = [t for t in tl if t["trade_id"] < params["after"]]
            return tl[:3]
        if url.startswith(C.ADV):
            s, e = int(params["start"]), int(params["end"])
            return {"candles": [dict(start=str(int(m.timestamp())), open=v[0], high=v[1], low=v[2], close=v[3],
                                     volume=v[4]) for (c, m), v in self.bars.items()
                                if c == coin and s <= m.timestamp() <= e]}
        s, e = pd.Timestamp(params["start"][:-1]), pd.Timestamp(params["end"][:-1])
        return [[int(m.timestamp()), v[2], v[1], v[0], v[3], v[4]] for (c, m), v in self.bars.items()
                if c == coin and s <= m <= e]


class CandleProbe(unittest.TestCase):
    def test_probe_end_to_end(self):
        import candle_probe as P
        q0 = pd.Timestamp.now().floor("min") - pd.Timedelta(minutes=20)
        qs = [q0 + pd.Timedelta(minutes=i) for i in range(4)]
        venue = FakeVenue([q - pd.Timedelta(minutes=k) for q in qs[:1] for k in range(6, 0, -1)] + qs[:3])
        pr = P.Probe(["AAA", "BBB", "GONE"], http=venue, log=lambda m: None, ex_interval=0.001, adv_interval=0.001)
        for q in qs:
            pr.schedule(q)
        n = 3 * 4 * (len(P.CANDLE_DELAYS) + 1 + len(P.TRADE_DELAYS) + 1 + 1)     # + adv, ref, bot_url
        deadline = time.time() + 120                                   # wait for the rows, not for a fixed time
        while len(pr.rows) < n and time.time() < deadline:
            time.sleep(0.05)
        time.sleep(0.2)                                                # no extra row may follow
        df = P.to_frame(pr.rows)
        self.assertEqual(len(df), n)                                    # one row per coin, boundary, source, delay
        tr = df[(df.source == "ex_trades") & (df.coin == "AAA") & df.present]
        self.assertTrue((tr.pages >= 2).all())                          # 3 a page, 4 trades a minute: paging used
        self.assertEqual(set(tr.n_trades), {4})
        cu = [u for u in venue.urls if u[0].endswith("/candles") and u[0].startswith(C.EXCHANGE)]
        self.assertEqual(len(cu), len(set(cu)))                         # no candle URL is asked twice
        self.assertEqual(dict(P.window(qs[0], 6)), C.candle_params(qs[0]))   # 6 s keeps the collector's window
        bw = P.bot_window(pd.Timestamp("2026-11-10 12:00"))                   # the paper bot's steady-state request
        self.assertEqual((bw["start"], bw["end"]), ("2026-11-10T11:56:00Z", "2026-11-10T11:59:00Z"))
        tab, per, ref, sig = P.measures(df)
        self.assertEqual(len(ref), 2 * 4)                               # AAA, BBB; GONE never traded
        self.assertTrue((tab.exact == 100).all() and (tab.material == 0).all())
        tt = P.trades_timing(df[df.coin != "GONE"])
        self.assertTrue((tt.pages_mean >= 2).all())
        self.assertEqual(P.decide(tab, tt)[0], "A")
        late = tab.copy()
        late.loc[late.source == "ex_trades", "material"] = 5.0
        self.assertEqual(P.decide(late, tt)[0], "B")
        late.loc[late.source != "ex_trades", "material"] = 5.0
        self.assertEqual(P.decide(late, tt)[0], "C")
        self.assertEqual(P.reduce_trades(venue.trades["AAA"], qs[0] - pd.Timedelta(minutes=1))[:5],
                         venue.bars[("AAA", qs[0] - pd.Timedelta(minutes=1))])


if __name__ == "__main__":
    unittest.main(verbosity=1)
