#!/usr/bin/env python3
"""Test of the newest-minute switches in the spot engine: "newest_bar" (candles or trades) and "stale_guard".
No network, no keys.

Part 1, a small synthetic market (update_spot and trades_pass only):
  - newest_bar "candles" leaves the table exactly as the candle merge makes it, and never asks for trades;
  - a verified bar replaces the minute's row (or inserts it when the candle has none); a verified empty minute changes
    nothing;
  - an unverified bar, an error and a refusal keep the candle row and are counted;
  - the time budget stops the pass and the rest fall back (counted);
  - a refusal or a rate limit (the real bot/market.py classes) stops the pass; a rate limit counts as tb_fb_limited;
  - trades_coins: listed coins are rebuilt, unlisted ones are never asked, unknown names raise at start-up;
  - candle_old and btc_candle_old count candle answers made before the minute ended, and change nothing;
  - the next step's re-fetch replaces the trades-built row with the venue's candle, and a trades-built row does not
    move the re-fetch window.
Part 2, the engine stepping through stored Oct 10 2025 crash data (bot/spot/replay_test.py ReplayMarket), paper broker:
  - newest_bar "trades" with trades that match the candles gives exactly the decisions of newest_bar "candles";
  - a late trade missing from the first-seen candle (lower low, other close, less volume): with candles the paper fill
    in that minute is missed; with trades the row is the final one and the fill is booked as in the clean run;
  - BTC stale with stale_guard on: no new or re-priced bids, exits still run, one stale_input event per stale minute,
    no error; with the guard off: as today, only counted;
  - timing and data checks that raise: the step still settles, runs exits and writes last_minute (obs_error);
    with the guard on such a minute places no new bid;
  - the heartbeat carries the new counters and the step timing, and both reset after each heartbeat.

Usage: python bot/spot/newest_bar_test.py [--part1]
"""
import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot import market as BM  # noqa: E402
from bot.spot import engine as E  # noqa: E402

COLS = ["open", "high", "low", "close", "volume"]
FAILS = []
CFG = json.load(open(os.path.join(HERE, "config.json")))


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""), flush=True)
    if not ok:
        FAILS.append(name)


# ------------------------------------------------------------------------------------------------ part 1
T0 = pd.Timestamp("2026-11-10 12:00")


class SynthMarket:
    """Final candles for every coin; the first-seen copy of a minute can differ (first); trades bars per (coin, minute)
    from `tb` (dict, or an Exception to raise)."""

    def __init__(self, coins, n):
        self.final, self.first, self.tb, self.calls = {}, {}, {}, []
        idx = pd.date_range(T0, periods=n, freq="min")
        for j, c in enumerate(coins):
            x = 100.0 + j + np.arange(n) * 0.01
            self.final[c] = pd.DataFrame({"open": x, "high": x + 0.5, "low": x - 0.5, "close": x, "volume": 10.0},
                                         index=idx)
        self.slow = 0.0
        self.Refused, self.Limited = BM.Refused, BM.Limited   # as LiveMarket: the real classes
        self.lag = None          # set: answers carry cache facts, made `lag` (a Timedelta, or {coin: lag}) after end
        self.copy = {}           # (coin, end) -> a frame served instead (an old copy)
        self.starts = []

    def spot_candles(self, coin, start, end):
        self.starts.append((coin, start))
        if self.lag is not None:
            lag = self.lag.get(coin, pd.Timedelta(seconds=30)) if isinstance(self.lag, dict) else self.lag
            if not hasattr(self, "candle_meta"):
                self.candle_meta = {}
            self.candle_meta[coin] = {"gen": None if lag is None else end + lag, "start": start}
        if (coin, end) in self.copy:
            return self.copy[(coin, end)]
        d = self.final[coin]
        d = d[(d.index >= start) & (d.index < end)].copy()
        newest = end - pd.Timedelta(minutes=1)
        if (coin, newest) in self.first:
            v = self.first[(coin, newest)]
            if v is None:
                d = d[d.index != newest]
            else:
                d.loc[newest, COLS] = v
        return d

    def spec(self, coin):
        return E.Spec(f"{coin}-USD", 0.01, 1e-8, 1.0)

    def trades_bar(self, coin, m, deadline=None):
        self.calls.append((coin, m))
        if self.slow:
            CLOCK[0] += self.slow
        v = self.tb.get((coin, m), "final")
        if isinstance(v, Exception):
            raise v
        if isinstance(v, dict) and "verified" in v:
            return v
        if v == "final":
            d = self.final[coin]
            return dict(bar=d.loc[m].to_dict() if m in d.index else None, verified=True, reason=None, pages=1)
        return dict(bar=v, verified=True, reason=None, pages=1)


CLOCK = [0.0]


def synth_engine(newest_bar, coins=("ETH", "SOL"), **extra):
    sd = tempfile.mkdtemp(prefix="nb_part1_")
    cfg = dict(CFG, newest_bar=newest_bar, **extra)
    eng = E.Engine(mode="paper", cfg=cfg, state_dir=sd, market=None, broker=E.PaperBroker(0.5),
                   clock=lambda: T0, echo=False)
    eng.coins = list(coins)                       # a two-coin universe for the data tests (models are not used here)
    eng.market = SynthMarket(["BTC"] + eng.coins, 40)
    eng._timer = lambda: CLOCK[0]
    return eng, sd


def part1():
    E.WINDOW_MIN = 30                             # short window for the synthetic tables; restored below
    try:
        _part1()
    finally:
        E.WINDOW_MIN = 11 * 1440


def _part1():
    end = T0 + pd.Timedelta(minutes=20)
    m = end - pd.Timedelta(minutes=1)

    # candles mode: the table is what the merge gives; no trades asked
    eng, sd = synth_engine("candles")
    eng.market.first[("ETH", m)] = dict(open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)
    eng.update_spot(end)
    ref = eng.market.final["ETH"]
    want = ref[ref.index < end].copy()
    want.loc[m, COLS] = [1.0, 2.0, 0.5, 1.5, 1.0]
    check("candles: table is the candle merge", eng.spot["ETH"].equals(want.loc[end - pd.Timedelta(minutes=30):]))
    check("candles: no trades requested", not eng.market.calls)
    shutil.rmtree(sd)

    # trades mode: verified bar replaces the row; missing row inserted; verified empty changes nothing
    eng, sd = synth_engine("trades")
    eng.market.first[("ETH", m)] = dict(open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)   # first-seen differs
    eng.market.first[("SOL", m)] = None                                                      # first-seen missing
    eng.market.tb[("BTC", m)] = None                                                         # verified empty
    before_btc = None
    eng.update_spot(end)
    before_btc = eng.spot["BTC"].copy()
    eng.trades_pass(m)
    fin = eng.market.final
    check("trades: verified bar replaces the first-seen row", eng.spot["ETH"].loc[m].equals(fin["ETH"].loc[m]))
    check("trades: verified bar inserts a missing row", m in eng.spot["SOL"].index
          and eng.spot["SOL"].loc[m].equals(fin["SOL"].loc[m]) and eng.spot["SOL"].index.is_monotonic_increasing)
    check("trades: verified empty minute changes nothing", eng.spot["BTC"].equals(before_btc))
    check("trades: asked BTC first, then every coin", [c for c, _ in eng.market.calls] == ["BTC", "ETH", "SOL"])
    c = eng.counts
    check("trades: counts", c.get("tb_built") == 2 and c.get("tb_insert") == 1 and c.get("tb_close_diff") == 1
          and c.get("tb_empty") == 1, str(c))
    check("trades: re-fetch anchor stays at the newest candle", eng._cmax["SOL"] == m - pd.Timedelta(minutes=1)
          and eng._cmax["ETH"] == m, str(eng._cmax))

    # next step: the re-fetch brings the final candles and replaces the trades-built rows
    eng.market.tb[("ETH", end)] = dict(open=9.0, high=9.0, low=9.0, close=9.0, volume=9.0)   # a made-up bar for end
    eng.market.tb[("SOL", end)] = dict(bar=None, verified=False, reason="stale_first_page")
    eng.market.tb[("BTC", end)] = "final"
    seen = []
    orig = eng.market.spot_candles
    eng.market.spot_candles = lambda coin, s, e: (seen.append((coin, s)), orig(coin, s, e))[1]
    end2 = end + pd.Timedelta(minutes=1)
    eng.update_spot(end2)
    check("next step: SOL re-fetch starts 5 minutes before its newest candle (6 minutes), not the trades-built row",
          dict(seen)["SOL"] == m - pd.Timedelta(minutes=6), str(dict(seen)["SOL"]))
    check("next step: ETH re-fetch covers 6 minutes in trades mode", dict(seen)["ETH"] == m - pd.Timedelta(minutes=5))
    check("next step: ETH row for m stays the trades row (an answer of unknown age does not replace it)",
          eng.spot["ETH"].loc[m].equals(fin["ETH"].loc[m]))
    eng.market.final["ETH"].loc[end, "close"] += 0.0       # unchanged final
    eng.counts = {}
    eng.trades_pass(end)
    check("next step: the made-up trades bar for the new minute wins over its first-seen candle",
          eng.spot["ETH"].loc[end, "close"] == 9.0)
    check("next step: unverified bar keeps the candle row and is counted",
          eng.spot["SOL"].loc[end].equals(fin["SOL"].loc[end]) and eng.counts.get("tb_fb_unverified") == 1,
          str(eng.counts))
    eng.update_spot(end2 + pd.Timedelta(minutes=1))
    check("step after: an answer of unknown age does not replace the trades-built row", eng.spot["ETH"].loc[end, "close"]
          == 9.0)
    eng.market.lag = pd.Timedelta(seconds=30)               # answers now made 30 s after the step's minute starts
    eng.update_spot(end2 + pd.Timedelta(minutes=2))
    check("later: even a confirmed answer (made > 25 s after the minute closed) never replaces a trades-built row",
          eng.spot["ETH"].loc[end, "close"] == 9.0)
    shutil.rmtree(sd)

    # provenance with answers that report their age (old copies)
    def copy_of(coin, upto, delta=0.0):
        d = SM.final[coin]
        d = d[d.index < upto].copy()
        d["close"] += delta
        return d
    eng, sd = synth_engine("trades")
    SM = eng.market
    SM.lag = pd.Timedelta(seconds=10)
    eng.update_spot(end)
    eng.trades_pass(m)                                      # m: trades-built for BTC, ETH, SOL
    m1, end1 = end, end + pd.Timedelta(minutes=1)
    # an old copy (made 10 s before m ended, so missing m and with other values) at the next step
    SM.copy[("ETH", end1)] = copy_of("ETH", m, delta=5.0)
    SM.lag = {"ETH": -pd.Timedelta(minutes=1, seconds=10)}
    eng.update_spot(end1)
    check("old copy: never replaces a trades-built row", eng.spot["ETH"].loc[m].equals(fin["ETH"].loc[m]))
    mm = m - pd.Timedelta(minutes=1)                        # candle row from a fresher answer (made end + 10 s)
    check("old copy: never replaces a candle row from a newer answer", eng.spot["ETH"].loc[mm, "close"]
          == fin["ETH"].loc[mm, "close"])
    SM.copy.pop(("ETH", end1))
    SM.copy[("ETH", end1 + pd.Timedelta(minutes=1))] = copy_of("ETH", m, delta=7.0)
    SM.lag = {"ETH": pd.Timedelta(seconds=1)}              # newer than the stored answer, but not confirmed for m
    eng.update_spot(end1 + pd.Timedelta(minutes=1))
    check("newer answer: replaces an older candle row", eng.spot["ETH"].loc[mm, "close"]
          == fin["ETH"].loc[mm, "close"] + 7.0)
    check("newer answer: still does not replace m's trades row",
          eng.spot["ETH"].loc[m].equals(fin["ETH"].loc[m]))
    shutil.rmtree(sd)
    eng, sd = synth_engine("trades")
    eng.market.lag = -pd.Timedelta(minutes=6)               # an old copy, made before any of those rows closed
    eng.update_spot(end)
    eng.counts = {}
    eng.data_checks(m)
    check("rows_open counts rows 3 to 6 minutes old that are not confirmed (4 minutes x 3 coins)",
          eng.counts.get("rows_open") == 12, str(eng.counts))
    shutil.rmtree(sd)

    # the 6-minute window in trades mode for every coin, listed or not; 3 minutes in candles mode
    eng, sd = synth_engine("trades", trades_coins=["BTC", "ETH"])
    eng.update_spot(end)
    eng.trades_pass(m)
    eng.market.starts = []
    eng.update_spot(end + pd.Timedelta(minutes=1))
    st = dict(eng.market.starts)
    check("window: trades mode re-fetches 6 minutes for listed and unlisted coins",
          st["ETH"] == m - pd.Timedelta(minutes=5) and st["SOL"] == m - pd.Timedelta(minutes=5), str(st))
    check("window: the unlisted coin is never asked for trades", "SOL" not in [x[0] for x in eng.market.calls])
    shutil.rmtree(sd)

    # an unlisted coin: an old copy never replaces a newer candle row; a newer answer does; rows_open counts it
    eng, sd = synth_engine("trades", trades_coins=["BTC", "ETH"])
    SM = eng.market
    SM.lag = pd.Timedelta(seconds=10)
    eng.update_spot(end)
    eng.trades_pass(m)
    end1 = end + pd.Timedelta(minutes=1)
    SM.copy[("SOL", end1)] = copy_of("SOL", end, delta=5.0)
    SM.lag = {"SOL": -pd.Timedelta(minutes=1, seconds=10)}  # made before the stored answer
    eng.update_spot(end1)
    check("unlisted: an old copy does not replace a newer candle row", eng.spot["SOL"].loc[m].equals(fin["SOL"].loc[m]))
    SM.copy[("SOL", end1 + pd.Timedelta(minutes=1))] = copy_of("SOL", end, delta=7.0)
    SM.lag = {"SOL": pd.Timedelta(seconds=1)}
    eng.update_spot(end1 + pd.Timedelta(minutes=1))
    check("unlisted: a newer answer replaces it", eng.spot["SOL"].loc[m, "close"] == fin["SOL"].loc[m, "close"] + 7.0)
    shutil.rmtree(sd)
    eng, sd = synth_engine("trades", trades_coins=["BTC"])
    eng.market.lag = -pd.Timedelta(minutes=6)
    eng.update_spot(end)
    eng.counts = {}
    eng.data_checks(m)
    check("rows_open covers unlisted coins too (4 minutes x 3 coins)", eng.counts.get("rows_open") == 12,
          str(eng.counts))
    shutil.rmtree(sd)
    eng, sd = synth_engine("candles")
    eng.update_spot(end)
    eng.market.starts = []
    eng.update_spot(end + pd.Timedelta(minutes=1))
    check("window: candles mode re-fetches 3 minutes for every coin",
          all(v == m - pd.Timedelta(minutes=2) for v in dict(eng.market.starts).values()), str(eng.market.starts))
    shutil.rmtree(sd)

    # a hole left by a failed trades pass is repaired at the next step, in one paging pass
    class RepairMarket(SynthMarket):
        def trades_bars(self, coin, m0, m1, deadline=None):
            self.calls.append((coin, m0, m1))
            v = self.tb.get((coin, m1))
            if isinstance(v, Exception):
                raise v
            d = self.final[coin]
            mins = list(pd.date_range(m0, m1, freq="min"))
            return dict(bars={x: d.loc[x].to_dict() for x in mins}, verified=True, reason=None, pages=1)

    eng, sd = synth_engine("trades")
    eng.market = RM = RepairMarket(["BTC", "ETH", "SOL"], 40)
    RM.lag = {"ETH": -pd.Timedelta(minutes=2)}              # ETH's answers are old copies made before m ended
    RM.first[("ETH", m)] = None                             # and miss m
    eng.update_spot(end)
    eng._prov = {k: {x: v for x, v in P.items() if x != m} for k, P in eng._prov.items()}
    RM.tb[("ETH", m)] = RuntimeError("timeout")             # the trades pass fails for ETH at m
    eng.trades_pass(m)
    check("repair setup: ETH has a hole at m", m not in eng.spot["ETH"].index)
    RM.calls, eng.counts = [], {}
    eng.update_spot(end + pd.Timedelta(minutes=1))
    eng.trades_pass(end)
    eth = [x for x in RM.calls if x[0] == "ETH"]
    check("repair: the hole is rebuilt at the next step in one paging pass", m in eng.spot["ETH"].index
          and eng.spot["ETH"].loc[m].equals(fin["ETH"].loc[m]) and len(eth) == 1 and eth[0][1] <= m and eth[0][2] == end
          and eng.counts.get("tb_rebuilt", 0) >= 1, f"{eth} {eng.counts}")
    shutil.rmtree(sd)

    # guard: BTC stale unless trades-built or from an answer made after m closed; a coin with an old row is skipped
    eng, sd = synth_engine("trades", stale_guard=True)
    eng.tradable = list(eng.coins)
    eng.market.lag = {"BTC": -pd.Timedelta(seconds=20), "ETH": -pd.Timedelta(seconds=20), "SOL": pd.Timedelta(seconds=5)}
    eng.update_spot(end)
    eng._prov = {}                                          # forget the start-up rows: only this answer counts
    eng.update_spot(end)
    eng.market.tb[("BTC", m)] = RuntimeError("timeout")
    eng.market.tb[("ETH", m)] = RuntimeError("timeout")
    eng.market.tb[("SOL", m)] = RuntimeError("timeout")
    eng.trades_pass(m)
    eng.counts = {}
    st = eng.data_checks(m)
    check("guard: BTC row from an answer made before m closed is stale", st == (True, 0), str(st))
    check("guard: a coin whose row came from an old answer gets no new bid (skip_old); a fresh one does",
          eng._skip_old == {"ETH"} and eng.counts.get("skip_old") == 1, f"{eng._skip_old} {eng.counts}")
    eng.market.tb[("BTC", m)] = "final"
    eng.trades_pass(m)
    check("guard: BTC trades-built is not stale", eng.data_checks(m) == (False, 0))
    eng.counts = {}
    RU = eng.market.candle_meta
    eng.market.candle_meta = {k: dict(v, gen=None) if k == "ETH" else v for k, v in RU.items()}
    eng.data_checks(m)
    check("guard: an answer of unknown age also gets no new bid", "ETH" in eng._skip_old, str(eng._skip_old))
    eng.market.candle_meta = RU
    shutil.rmtree(sd)
    # quiet minute: a fresh answer with no row for m (no trades): the coin is decided as today, only newest_absent
    eng, sd = synth_engine("candles", stale_guard=True)
    eng.tradable = list(eng.coins)
    eng.market.lag = {"BTC": pd.Timedelta(seconds=5), "ETH": -pd.Timedelta(seconds=20), "SOL": pd.Timedelta(seconds=5)}
    eng.market.first[("SOL", m)] = None
    eng.update_spot(end)
    eng.counts = {}
    st = eng.data_checks(m)
    check("guard, quiet minute: fresh answer without a row is decided on; the old answer is skipped",
          eng._skip_old == {"ETH"} and eng.counts.get("skip_old") == 1 and eng.counts.get("newest_absent") == 1
          and st == (False, 0), f"{eng._skip_old} {eng.counts} {st}")
    eng.market.first[("BTC", end)] = None                   # BTC: a fresh answer without its row is a fault
    eng.update_spot(end + pd.Timedelta(minutes=1))
    check("guard: BTC with a fresh answer but no row is stale", eng.data_checks(end)[0])
    eng.cfg["stale_guard"] = False
    eng.counts = {}
    st = eng.data_checks(m)                                 # ETH's answer is still old
    check("guard off: nothing changes (no skip, BTC not stale)", st == (False, 0) and not eng._skip_old
          and "skip_old" not in eng.counts, f"{st} {eng.counts}")
    shutil.rmtree(sd)

    # errors and refusal
    eng, sd = synth_engine("trades", coins=("ETH", "SOL", "XRP"))
    eng.update_spot(end)
    eng.market.tb[("BTC", m)] = RuntimeError("timeout")
    eng.trades_pass(m)
    check("error: counted, others still built", eng.counts.get("tb_fb_error") == 1 and eng.counts.get("tb_built") == 3
          and "timeout" in (eng._tb_err or ""), str(eng.counts))

    eng.counts = {}
    eng.market.tb[("BTC", m)] = "final"
    eng.market.tb[("ETH", m)] = BM.Refused("HTTP 403")
    eng.market.calls = []
    keep = eng.spot["SOL"].copy()
    eng.trades_pass(m)
    check("refusal: the pass stops at once, the rest fall back as errors",
          [c for c, _ in eng.market.calls] == ["BTC", "ETH"] and eng.counts.get("tb_fb_error") == 3
          and eng.spot["SOL"].equals(keep), str(eng.counts))
    eng.counts = {}
    eng.market.tb[("ETH", m)] = BM.Limited("HTTP 429")
    eng.market.calls = []
    eng.trades_pass(m)
    check("rate limit: the pass stops at once, counted as tb_fb_limited (not as an error)",
          [c for c, _ in eng.market.calls] == ["BTC", "ETH"] and eng.counts.get("tb_fb_limited") == 3
          and "tb_fb_error" not in eng.counts and eng.spot["SOL"].equals(keep), str(eng.counts))
    eng.counts = {}
    eng.market.tb[("ETH", m)] = RuntimeError("Refused but not the class")       # name alone does not stop the pass
    eng.market.calls = []
    eng.trades_pass(m)
    check("a plain error named like a refusal does not stop the pass", len(eng.market.calls) == 4
          and eng.counts.get("tb_fb_error") == 1, str(eng.counts))
    shutil.rmtree(sd)

    # per-coin list: ETH listed, SOL not
    eng, sd = synth_engine("trades", trades_coins=["BTC", "ETH"])
    eng.market.first[("ETH", m)] = dict(open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)
    eng.market.first[("SOL", m)] = dict(open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)
    eng.update_spot(end)
    sol = eng.spot["SOL"].copy()
    eng.trades_pass(m)
    check("trades_coins: a listed coin is rebuilt from trades", eng.spot["ETH"].loc[m].equals(fin["ETH"].loc[m]))
    check("trades_coins: an unlisted coin is never asked and keeps its candle row",
          "SOL" not in [c for c, _ in eng.market.calls] and eng.spot["SOL"].equals(sol) and "SOL" not in eng._cmax)
    check("trades_coins: counters count listed coins only", eng.counts.get("tb_built") == 2
          and eng.counts.get("tb_close_diff") == 1, str(eng.counts))
    eng.market.first[("SOL", end)] = None                   # SOL's newest candle missing at the next step
    eng.update_spot(end + pd.Timedelta(minutes=1))
    eng.counts = {}
    eng.data_checks(end)
    check("trades_coins: newest_absent still covers every coin", eng.counts.get("newest_absent") == 1, str(eng.counts))
    shutil.rmtree(sd)
    try:
        synth_engine("trades", trades_coins=["BTC", "DOGEX"])
        check("trades_coins with an unknown coin raises at start-up", False)
    except ValueError:
        check("trades_coins with an unknown coin raises at start-up", True)

    # age of the candle answers (counted only): BTC and ETH answers made before the minute ended, SOL's after
    eng, sd = synth_engine("candles")
    eng.update_spot(end)
    tables = {c: eng.spot[c].copy() for c in eng.spot}
    eng.market.candle_meta = {"BTC": {"gen": m + pd.Timedelta(seconds=30)}, "ETH": {"gen": m - pd.Timedelta(minutes=2)},
                              "SOL": {"gen": end + pd.Timedelta(seconds=7)}}
    st = eng.data_checks(m)
    check("candle age: candle_old and btc_candle_old counted", eng.counts.get("candle_old") == 1
          and eng.counts.get("btc_candle_old") == 1, str(eng.counts))
    check("candle age: counting changes neither the tables nor the stale answer", st == (False, 0)
          and all(eng.spot[c].equals(tables[c]) for c in tables))
    eng.counts = {}
    del eng.market.candle_meta
    eng.data_checks(m)
    check("candle age: a market without meta is skipped", "candle_old" not in eng.counts
          and "btc_candle_old" not in eng.counts, str(eng.counts))
    shutil.rmtree(sd)

    # budget: each coin takes 3 s on an 8 s budget: BTC, ETH, SOL done (0, 3, 6 s), XRP not started (9 s > 8)
    eng, sd = synth_engine("trades", coins=("ETH", "SOL", "XRP"))
    eng.market.first[("XRP", m)] = dict(open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)
    eng.update_spot(end)
    keep = eng.spot["XRP"].copy()
    eng.market.slow = 3.0
    eng.trades_pass(m)
    check("budget: stops after 8 s, the rest fall back", [c for c, _ in eng.market.calls] == ["BTC", "ETH", "SOL"]
          and eng.counts.get("tb_fb_budget") == 1 and eng.counts.get("tb_built") == 3 and eng.spot["XRP"].equals(keep),
          str(eng.counts))
    eng.counts = {}
    eng.market.slow = 0.0
    eng.market.tb[("BTC", m)] = dict(bar=None, verified=False, reason="deadline")
    eng.trades_pass(m)
    check("budget: a bar cut by the deadline counts as budget", eng.counts.get("tb_fb_budget") == 1, str(eng.counts))
    shutil.rmtree(sd)

    # every market method the engine calls must exist on LiveMarket (checked on the class, no network)
    import re
    src = open(E.__file__).read()
    called = sorted(set(re.findall(r"self\.market\.(\w+)\(", src)))
    missing = [x for x in called if not callable(getattr(E.LiveMarket, x, None))]
    check("LiveMarket has every method the engine calls on the market", not missing and "trades_bars" in called,
          f"called {called}, missing {missing}")

    # bad switch value
    try:
        synth_engine("trade")
        check("newest_bar with a bad value raises", False)
    except ValueError:
        check("newest_bar with a bad value raises", True)


# ------------------------------------------------------------------------------------------------ part 2
START, END = pd.Timestamp("2025-10-10 20:30"), pd.Timestamp("2025-10-10 22:15")


def make_market():
    from bot.spot.replay_test import ReplayMarket

    class FirstSeen(ReplayMarket):
        """Stored candles; the first-seen copy of a minute can be altered (alter) or BTC's newest minute dropped
        (drop_btc); trades bars are the stored (final) candles."""
        alter, drop_btc, drop, tb_calls = {}, set(), set(), [0]

        def spot_candles(self, coin, start, end):
            d = super().spot_candles(coin, start, end)
            newest = pd.Timestamp(end) - pd.Timedelta(minutes=1)
            if (coin, newest) in self.alter and newest in d.index:
                d = d.copy()
                d.loc[newest, COLS] = self.alter[(coin, newest)]
            if getattr(self, "old", None) is not None:   # answer facts: fresh, or old for the listed steps
                e = pd.Timestamp(end)
                self.candle_meta[coin] = {"gen": e + pd.Timedelta(seconds=(-30 if (coin, e) in self.old else 8)),
                                          "start": pd.Timestamp(start)}
            if (coin == "BTC" and newest in self.drop_btc) or (coin, newest) in self.drop:
                d = d[d.index != newest]
            return d

        def trades_bars(self, coin, m0, m1, deadline=None):
            self.tb_calls[0] += 1
            d = self.D[coin]
            return dict(bars={x: (d.loc[x].to_dict() if x in d.index and d.loc[x, "volume"] > 0 else None)
                              for x in pd.date_range(m0, m1, freq="min")}, verified=True, reason=None, pages=1)

        def trades_bar(self, coin, m, deadline=None):
            self.tb_calls[0] += 1
            d = self.D[coin]
            bar = d.loc[m].to_dict() if m in d.index and d.loc[m, "volume"] > 0 else None
            return dict(bar=bar, verified=True, reason=None, pages=1)

    return FirstSeen(START, END)


def run(mkt, cfg_extra, tag, alter=None, drop_btc=(), patch=None, drop=(), old=None):
    mkt.alter, mkt.drop_btc, mkt.drop = dict(alter or {}), set(drop_btc), set(drop)
    mkt.old = old                                       # {(coin, step)}: answers that report being old copies
    if old is not None:
        mkt.candle_meta = {}
    elif "candle_meta" in vars(mkt):
        del mkt.candle_meta
    clock = {"t": START}
    sd = tempfile.mkdtemp(prefix=f"nb_{tag}_")
    cfg = dict(CFG, **cfg_extra)
    eng = E.Engine(mode="paper", cfg=cfg, state_dir=sd, market=mkt, broker=E.PaperBroker(cfg["paper_capture"]),
                   clock=lambda: clock["t"] + pd.Timedelta(seconds=6), echo=False)
    eng.start()
    if patch:
        patch(eng)
    after_hb = []
    eng.lm_ok = True
    for t in pd.date_range(START, END, freq="min", inclusive="left"):
        clock["t"] = t
        eng.step(t)
        eng.lm_ok = eng.lm_ok and json.load(open(os.path.join(sd, "state.json")))["last_minute"] == t.isoformat()
        if t.minute % 30 == 0:
            after_hb.append((dict(eng.counts), {k: list(v) for k, v in eng._tm.items()}))
    ev = [json.loads(x) for x in open(os.path.join(sd, "events.jsonl"))]
    print(f"  [{tag}] {len(ev)} events, kinds {pd.Series([e['kind'] for e in ev]).value_counts().to_dict()}", flush=True)
    shutil.rmtree(sd)
    return ev, after_hb, eng


def decisions(ev):
    return [e for e in ev if e["kind"] != "heartbeat"]


def part2():
    mkt = make_market()
    evA, hbA, engA = run(mkt, {}, "candles")
    fills = [e for e in evA if e["kind"] == "fill_entry" and e["rung"] == 4]
    check("setup: the clean run has 4-sigma fills", len(fills) > 0, str(len(fills)))
    if not fills:
        return
    f = fills[0]
    c, m, px = f["coin"], pd.Timestamp(f["ts"]), f["px"]
    tick = mkt.spec(c).tick
    fin = mkt.D[c].loc[m]
    alt_low = min(fin["open"], px + tick)
    alt = [fin["open"], max(fin["high"], fin["open"]), alt_low, fin["open"], fin["volume"] * 0.6]
    print(f"  first 4-sigma fill: {c} at {m} px {px}; final low {fin['low']}, first-seen low set to {alt_low}, "
          f"close {fin['close']} -> {alt[3]}, volume x0.6")
    check("setup: the altered row differs in close, low and volume",
          alt[3] != fin["close"] and alt[2] != fin["low"] and alt[4] != fin["volume"])

    # trades that match the candles: same decisions
    mkt.tb_calls[0] = 0
    evD, hbD, _ = run(mkt, {"newest_bar": "trades"}, "trades_match")
    check("trades matching the candles: identical decisions and log lines (heartbeats aside)",
          decisions(evD) == decisions(evA), f"{len(decisions(evD))} vs {len(decisions(evA))}")
    check("trades mode asked for trades every minute (and once at start-up)", mkt.tb_calls[0] == 18 * (1 + len(
        pd.date_range(START, END, freq="min", inclusive="left"))), str(mkt.tb_calls[0]))

    # late trade missing from the first-seen candle
    evB, _, _ = run(mkt, {}, "candles_late", alter={(c, m): alt})
    gotB = [e for e in evB if e["kind"] == "fill_entry" and e["coin"] == c and pd.Timestamp(e["ts"]) == m]
    check("candles, first-seen candle without the late trade: the fill in that minute is missed", not gotB, str(gotB[:1]))
    evC, hbC, _ = run(mkt, {"newest_bar": "trades"}, "trades_late", alter={(c, m): alt})
    gotC = [e for e in evC if e["kind"] == "fill_entry" and e["coin"] == c and pd.Timestamp(e["ts"]) == m]
    check("trades: the fill is booked in that minute", len(gotC) >= 1 and gotC[0]["px"] == px and gotC[0]["size"]
          == f["size"], str(gotC[:1]))
    check("trades: every decision as in the clean run", decisions(evC) == decisions(evA))
    hb = [e for e in evC if e["kind"] == "heartbeat"]
    cd = sum(h["counts"].get("tb_close_diff", 0) for h in hb)
    check("trades: heartbeat counts the built bars and the close that differed",
          all(h["counts"].get("tb_built", 0) > 0 for h in hb[1:]) and cd >= 1, f"close_diff {cd}")

    # BTC stale: BTC's newest candle missing at every step for 70 minutes, covering the fill's time exit
    ex = [e for e in evA if e["kind"] == "fill_exit" and e["coin"] == c and e["rung"] == 4]
    stale = set(pd.date_range(m + pd.Timedelta(minutes=1), m + pd.Timedelta(minutes=70), freq="min"))
    steps = {s + pd.Timedelta(minutes=1) for s in stale}        # the steps that see BTC stale
    evG, hbG, _ = run(mkt, {"stale_guard": True}, "guard_on", drop_btc=stale)
    si = [e for e in evG if e["kind"] == "stale_input"]
    check("guard on: one stale_input per stale minute, age 1", len(si) == len(stale)
          and all(e["age_min"] == 1 for e in si) and {pd.Timestamp(e["ts"]) for e in si} == steps, str(len(si)))
    bad = [e for e in evG if e["kind"] in ("arm", "rung") and pd.Timestamp(e["ts"]) in steps]
    check("guard on: no new bid while stale (no arm, no deeper rung)", not bad, str(bad[:2]))
    check("guard on: no error logged", not [e for e in evG if e["kind"] == "error"])
    exG = [e for e in evG if e["kind"] == "fill_exit" and e["coin"] == c and e["rung"] == 4]
    check("guard on: the open rung still exits while BTC is stale",
          len(exG) == 1 and pd.Timestamp(exG[0]["ts"]) in steps and ex and exG[0]["ts"] == ex[0]["ts"]
          and exG[0]["exit"] == ex[0]["exit"], f"{exG[:1]} vs {ex[:1]}")
    reprice = sum(h["counts"].get("reprice", 0) for h in [e for e in evG if e["kind"] == "heartbeat"])
    hbs = [e for e in evG if e["kind"] == "heartbeat" and pd.Timestamp(e["ts"]) in steps]
    check("guard on: heartbeats still run during the stale minutes and count btc_stale",
          bool(hbs) and all(h["counts"].get("btc_stale", 0) > 0 for h in hbs), str([h["counts"] for h in hbs]))
    evH, _, engH = run(mkt, {"stale_guard": False}, "guard_off", drop_btc=stale)
    evH0, _, _ = run(mkt, {}, "guard_absent", drop_btc=stale)
    check("guard off: no stale_input; decisions as with no guard key", not [e for e in evH if e["kind"] == "stale_input"]
          and decisions(evH) == decisions(evH0))
    hbH = [e for e in evH if e["kind"] == "heartbeat"]
    n_st = sum(h["counts"].get("btc_stale", 0) for h in hbH) + engH.counts.get("btc_stale", 0)   # + after the last
    check("guard off: btc_stale counted once per stale minute", n_st == len(stale),
          f"{[h['counts'].get('btc_stale') for h in hbH]} + {engH.counts.get('btc_stale')}")
    print(f"  (guard on: {reprice} re-prices in the whole run; guard off kept bidding: "
          f"{len([e for e in evH if e['kind'] == 'arm' and pd.Timestamp(e['ts']) in steps])} arms in the stale steps)")

    # guard, one coin: its newest row missing at the step where the clean run arms it: no arm for it, no stale_input
    arms = [e for e in evA if e["kind"] == "arm" and e["coin"] != c and pd.Timestamp(e["ts"]) > START + pd.Timedelta(minutes=5)]
    x, sx = arms[0]["coin"], pd.Timestamp(arms[0]["ts"])
    evS, _, _ = run(mkt, {"stale_guard": True}, "guard_one_coin", old={(x, sx)})
    armS = [e for e in evS if e["kind"] == "arm" and e["coin"] == x and pd.Timestamp(e["ts"]) == sx]
    hbS = sum(h["counts"].get("skip_old", 0) for h in evS if h["kind"] == "heartbeat")
    check(f"guard, one coin ({x} at {sx}, its candle answer made before the minute ended): no new bid for it then",
          not armS and not [e for e in evS if e["kind"] in ("stale_input", "error")] and hbS > 0, f"skip_old {hbS}")

    # monitoring that raises: _mark (step timing) and data_checks fail in every stale minute
    def broken(eng):
        real_since, real_checks = eng._since, eng.data_checks

        def since(t):
            if t in steps:
                raise RuntimeError("timing broke")
            return real_since(t)

        def checks(prev):
            if prev + pd.Timedelta(minutes=1) in steps:
                raise RuntimeError("check broke")
            return real_checks(prev)
        eng._since, eng.data_checks = since, checks

    evO, _, engO = run(mkt, {}, "obs_error_guard_off", patch=broken)
    nO = sum(e["counts"].get("obs_error", 0) for e in evO if e["kind"] == "heartbeat") + engO.counts.get("obs_error", 0)
    check("monitoring raises, guard off: every decision as in the clean run, last_minute written every step",
          decisions(evO) == decisions(evA) and engO.lm_ok)
    check("monitoring raises, guard off: counted as obs_error (data, cancel, place and check per stale step)",
          nO == 4 * len(steps), str(nO))
    evP, _, engP = run(mkt, {"stale_guard": True}, "obs_error_guard_on", patch=broken)
    siP = [e for e in evP if e["kind"] == "stale_input"]
    exP = [e for e in evP if e["kind"] == "fill_exit" and e["coin"] == c and e["rung"] == 4]
    check("monitoring raises, guard on: treated as stale (no new bid), exits still run, last_minute written",
          len(siP) == len(steps) and not [e for e in evP if e["kind"] in ("arm", "rung") and pd.Timestamp(e["ts"]) in steps]
          and len(exP) == 1 and exP[0]["ts"] == ex[0]["ts"] and engP.lm_ok
          and not [e for e in evP if e["kind"] == "error"], f"{len(siP)} stale_input, exits {exP[:1]}")

    # heartbeat: counters and timing appear, then reset
    hb = [e for e in evA if e["kind"] == "heartbeat"]
    check("heartbeat: step timing for data, cancel and place (median, max)", all(
        set(h["step_s"]) == {"data", "cancel", "place"} and all(len(v) == 2 for v in h["step_s"].values()) for h in hb)
        and hb[-1]["step_s"]["data"] == [6.0, 6.0], str(hb[-1].get("step_s")))
    check("heartbeat: newest_absent counted (minutes with no row for a coin)",
          any("newest_absent" in h["counts"] for h in hb), str([h["counts"].get("newest_absent") for h in hb]))
    check("heartbeat: counts and timing reset after each heartbeat",
          all(cnt == {} and all(not v for v in tm.values()) for cnt, tm in hbA + hbC), str(hbA[:1]))


if __name__ == "__main__":
    part1()
    if "--part1" not in sys.argv:
        part2()
    print("NEWEST BAR TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
