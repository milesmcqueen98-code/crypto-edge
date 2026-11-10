#!/usr/bin/env python3
"""Test of the newest-minute switches in the spot engine: "newest_bar" (candles or trades) and "stale_guard".
No network, no keys.

Part 1, a small synthetic market (update_spot and trades_pass only):
  - newest_bar "candles" leaves the table exactly as the candle merge makes it, and never asks for trades;
  - a verified bar replaces the minute's row (or inserts it when the candle has none); a verified empty minute changes
    nothing;
  - an unverified bar, an error and a refusal keep the candle row and are counted;
  - the time budget stops the pass and the rest fall back (counted);
  - the next step's re-fetch replaces the trades-built row with the venue's candle, and a trades-built row does not
    move the re-fetch window.
Part 2, the engine stepping through stored Oct 10 2025 crash data (bot/spot/replay_test.py ReplayMarket), paper broker:
  - newest_bar "trades" with trades that match the candles gives exactly the decisions of newest_bar "candles";
  - a late trade missing from the first-seen candle (lower low, other close, less volume): with candles the paper fill
    in that minute is missed; with trades the row is the final one and the fill is booked as in the clean run;
  - BTC stale with stale_guard on: no new or re-priced bids, exits still run, one stale_input event per stale minute,
    no error; with the guard off: as today, only counted;
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

    def spot_candles(self, coin, start, end):
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


def synth_engine(newest_bar, coins=("ETH", "SOL")):
    sd = tempfile.mkdtemp(prefix="nb_part1_")
    cfg = dict(CFG, newest_bar=newest_bar)
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
    check("next step: SOL re-fetch starts 2 minutes before its newest candle, not the trades-built row",
          dict(seen)["SOL"] == m - pd.Timedelta(minutes=3), str(dict(seen)["SOL"]))
    check("next step: ETH re-fetch window as in candles mode", dict(seen)["ETH"] == m - pd.Timedelta(minutes=2))
    check("next step: ETH row for m is the venue's candle", eng.spot["ETH"].loc[m].equals(fin["ETH"].loc[m]))
    eng.market.final["ETH"].loc[end, "close"] += 0.0       # unchanged final
    eng.counts = {}
    eng.trades_pass(end)
    check("next step: the made-up trades bar for the new minute wins over its first-seen candle",
          eng.spot["ETH"].loc[end, "close"] == 9.0)
    check("next step: unverified bar keeps the candle row and is counted",
          eng.spot["SOL"].loc[end].equals(fin["SOL"].loc[end]) and eng.counts.get("tb_fb_unverified") == 1,
          str(eng.counts))
    eng.update_spot(end2 + pd.Timedelta(minutes=1))
    check("step after: the re-fetch replaces the made-up row with the candle",
          eng.spot["ETH"].loc[end].equals(fin["ETH"].loc[end]))
    shutil.rmtree(sd)

    # errors and refusal
    eng, sd = synth_engine("trades", coins=("ETH", "SOL", "XRP"))
    eng.update_spot(end)
    eng.market.tb[("BTC", m)] = RuntimeError("timeout")
    eng.trades_pass(m)
    check("error: counted, others still built", eng.counts.get("tb_fb_error") == 1 and eng.counts.get("tb_built") == 3
          and "timeout" in (eng._tb_err or ""), str(eng.counts))

    class Refused(RuntimeError):
        pass

    eng.counts = {}
    eng.market.tb[("BTC", m)] = "final"
    eng.market.tb[("ETH", m)] = Refused("HTTP 403")
    eng.market.calls = []
    keep = eng.spot["SOL"].copy()
    eng.trades_pass(m)
    check("refusal: the pass stops at once, the rest fall back as errors",
          [c for c, _ in eng.market.calls] == ["BTC", "ETH"] and eng.counts.get("tb_fb_error") == 3
          and eng.spot["SOL"].equals(keep), str(eng.counts))
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
        alter, drop_btc, tb_calls = {}, set(), [0]

        def spot_candles(self, coin, start, end):
            d = super().spot_candles(coin, start, end)
            newest = pd.Timestamp(end) - pd.Timedelta(minutes=1)
            if (coin, newest) in self.alter and newest in d.index:
                d = d.copy()
                d.loc[newest, COLS] = self.alter[(coin, newest)]
            if coin == "BTC" and newest in self.drop_btc:
                d = d[d.index != newest]
            return d

        def trades_bar(self, coin, m, deadline=None):
            self.tb_calls[0] += 1
            d = self.D[coin]
            bar = d.loc[m].to_dict() if m in d.index and d.loc[m, "volume"] > 0 else None
            return dict(bar=bar, verified=True, reason=None, pages=1)

    return FirstSeen(START, END)


def run(mkt, cfg_extra, tag, alter=None, drop_btc=()):
    mkt.alter, mkt.drop_btc = dict(alter or {}), set(drop_btc)
    clock = {"t": START}
    sd = tempfile.mkdtemp(prefix=f"nb_{tag}_")
    cfg = dict(CFG, **cfg_extra)
    eng = E.Engine(mode="paper", cfg=cfg, state_dir=sd, market=mkt, broker=E.PaperBroker(cfg["paper_capture"]),
                   clock=lambda: clock["t"] + pd.Timedelta(seconds=6), echo=False)
    eng.start()
    after_hb = []
    for t in pd.date_range(START, END, freq="min", inclusive="left"):
        clock["t"] = t
        eng.step(t)
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
    check("trades mode asked for trades every minute", mkt.tb_calls[0] == 18 * len(pd.date_range(START, END, freq="min",
                                                                                                  inclusive="left")))

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
