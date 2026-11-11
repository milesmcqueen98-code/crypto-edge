#!/usr/bin/env python3
"""Test of the trades-mode key "trades_rows" (bot/spot/README.md, "Newest minute from trades"). No network, no keys.

Part 1, the synthetic market of newest_bar_test.py (update_spot, trades_pass and data_checks only):
  - "candle_after": the trades row is used at the decision for its own minute; an answer not confirmed for the
    minute leaves it; a confirmed answer replaces it; a confirmed answer without the row drops it (inside the answer's
    window only: a minute at or after the answer's newest row is left); a verified empty minute is filled by a
    confirmed candle row; an older answer does not undo a confirmed row; the repair path leaves confirmed rows alone;
    the stale guard gives the same answer as "keep" for the newest minute; the four counters;
  - a session: after the confirmations every row older than three minutes equals the venue's final candles, for
    every listed coin, including a minute the venue has no bar for;
  - the key absent and "keep" give identical tables, provenance and counts at every step, in trades and candles mode.
Part 2 (needs data/minute; skipped with a message when absent): the stored-crash replay of newest_bar_test.py gives the
same event log with the key absent and with "keep", in candles and in trades mode, and "candle_after" runs through.

Usage: python bot/spot/candle_after_test.py [--part1]
"""
import os
import shutil
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot.spot import engine as E  # noqa: E402
from bot.spot import newest_bar_test as NB  # noqa: E402

COLS = NB.COLS
MIN = pd.Timedelta(minutes=1)
S = pd.Timedelta(seconds=1)
T1 = NB.T0 + 20 * MIN
FAILS = NB.FAILS
check = NB.check


def made_up(x):
    return dict(open=x, high=x, low=x, close=x, volume=3.0)


def eng_of(rows="candle_after", coins=("ETH",), **extra):
    if rows is not None:
        extra["trades_rows"] = rows
    eng, sd = NB.synth_engine("trades", coins=coins, **extra)
    eng.market.lag = {c: 6 * S for c in ["BTC"] + list(coins)}      # answers made 6 s after the step's minute
    return eng, sd


def step(eng, t):
    eng.update_spot(t)
    eng.trades_pass(t - MIN)


def close(eng, c, mm):
    df = eng.spot[c]
    return float(df.loc[mm, "close"]) if mm in df.index else None


def fin(eng, c, mm):
    return float(eng.market.final[c].loc[mm, "close"])


def part1():
    E.WINDOW_MIN = 30
    try:
        _replace_and_counts()
        _drop()
        _empty_filled()
        _older_answer()
        _repair()
        _stale_guard()
        _pending()
        _session()
        _identity()
    finally:
        E.WINDOW_MIN = 11 * 1440


def _replace_and_counts():
    eng, sd = eng_of()
    m1 = T1 - MIN
    eng.market.tb[("ETH", m1)] = made_up(9.0)
    step(eng, T1)
    check("candle_after: the trades row is the row for its own decision (minute t-1 at t)", close(eng, "ETH", m1) == 9.0)
    eng.market.lag["ETH"] = -40 * S          # made t2 - 40 s = 20 s after m1 closed: not confirmed for m1
    eng.counts = {}
    step(eng, T1 + MIN)
    check("candle_after: an answer not confirmed for the minute leaves the trades row", close(eng, "ETH", m1) == 9.0
          and "tb_replaced_diff" not in eng.counts, str(eng.counts))
    eng.market.lag["ETH"] = 6 * S
    eng.counts = {}
    step(eng, T1 + 2 * MIN)
    check("candle_after: a confirmed answer replaces the trades row with the venue's candle",
          eng.spot["ETH"].loc[m1].equals(eng.market.final["ETH"].loc[m1]))
    p = eng._prov["ETH"][m1]
    check("candle_after: the minute is now a confirmed candle row", p[1] is False and eng._confirmed(m1, p[0]), str(p))
    # ETH m1 and T1 (both trades-built, confirmed now) and BTC's T1 (BTC's m1 was confirmed at the step before)
    check("counters: tb_replaced 3, tb_replaced_diff 1 (only the made-up close differs)",
          eng.counts.get("tb_replaced") == 3 and eng.counts.get("tb_replaced_diff") == 1, str(eng.counts))
    shutil.rmtree(sd)
    k, sd = eng_of("keep")
    k.market.tb[("ETH", m1)] = made_up(9.0)
    for j in range(3):
        step(k, T1 + j * MIN)
    check("keep: the same confirmed answers leave the trades row, and no new counter appears",
          close(k, "ETH", m1) == 9.0 and not {"tb_replaced", "tb_replaced_diff", "tb_dropped", "tb_pending"} & set(k.counts))
    shutil.rmtree(sd)


def _drop():
    eng, sd = eng_of()
    md = T1 - MIN
    eng.market.final["ETH"] = eng.market.final["ETH"].drop(md)       # the venue has no bar for md
    eng.market.tb[("ETH", md)] = made_up(9.0)                          # the trades list has trades in it
    step(eng, T1)
    check("drop: setup, the trades row is inserted at its own decision", close(eng, "ETH", md) == 9.0
          and eng.counts.get("tb_insert") == 1, str(eng.counts))
    eng.counts = {}
    step(eng, T1 + MIN)
    check("drop: a confirmed answer without a row for the minute (inside its window) drops the trades row",
          md not in eng.spot["ETH"].index and eng.counts.get("tb_dropped") == 1, str(eng.counts))
    check("drop: the minute is then a confirmed candle state with no row",
          eng._prov["ETH"][md][1] is False and eng._confirmed(md, eng._prov["ETH"][md][0]))
    check("drop: the table stays sorted and the other rows are the venue's",
          eng.spot["ETH"].index.is_monotonic_increasing and close(eng, "ETH", md - MIN) == fin(eng, "ETH", md - MIN))
    shutil.rmtree(sd)

    # edge: the answer's newest row is before md (the venue has written nothing at or after md yet): md stays
    eng, sd = eng_of()
    eng.market.final["ETH"] = eng.market.final["ETH"].drop([md, md + MIN])
    eng.market.tb[("ETH", md)] = made_up(9.0)
    step(eng, T1)                                        # md trades-built
    eng.counts = {}
    step(eng, T1 + MIN)                                  # answer ends at md - 1; trades say T1 had no trades (empty)
    check("drop edge: a minute at or after the answer's newest row is not dropped", close(eng, "ETH", md) == 9.0
          and "tb_dropped" not in eng.counts, str(eng.counts))
    eng.counts = {}
    step(eng, T1 + 2 * MIN)                              # the answer now holds T1 + 1: md and T1 lie inside it
    check("drop edge: once the venue's answer holds a later row, the minute is dropped (one count: T1 had no row)",
          md not in eng.spot["ETH"].index and eng.counts.get("tb_dropped") == 1
          and eng._prov["ETH"][md + MIN][1] is False, str(eng.counts))
    shutil.rmtree(sd)

    # edge: an unconfirmed answer without the row never drops it
    eng, sd = eng_of()
    eng.market.final["ETH"] = eng.market.final["ETH"].drop(md)
    eng.market.tb[("ETH", md)] = made_up(9.0)
    step(eng, T1)
    eng.market.lag["ETH"] = None                          # an answer of unknown age
    step(eng, T1 + MIN)
    step(eng, T1 + 2 * MIN)
    check("drop edge: answers of unknown age leave the trades row", close(eng, "ETH", md) == 9.0)
    shutil.rmtree(sd)


def _empty_filled():
    for rows in ("candle_after", "keep"):
        eng, sd = eng_of(rows)
        m1 = T1 - MIN
        eng.market.first[("ETH", m1)] = None             # the first-seen answer has no row for m1
        eng.market.tb[("ETH", m1)] = None                # and the trades say no trades (verified empty)
        step(eng, T1)
        ok0 = m1 not in eng.spot["ETH"].index and eng.counts.get("tb_empty") == 1
        step(eng, T1 + MIN)
        if rows == "candle_after":
            check("candle_after: a verified empty minute is filled by a confirmed candle row (not counted as replaced)",
                  ok0 and eng.spot["ETH"].loc[m1].equals(eng.market.final["ETH"].loc[m1])
                  and eng._prov["ETH"][m1][1] is False, str(eng.counts))
        else:
            check("keep: the verified empty minute stays without a row", ok0 and m1 not in eng.spot["ETH"].index)
        shutil.rmtree(sd)


def _older_answer():
    eng, sd = eng_of()
    m1 = T1 - MIN
    eng.market.tb[("ETH", m1)] = made_up(9.0)
    step(eng, T1)
    step(eng, T1 + MIN)                                   # confirmed: m1 is the venue's candle
    t3 = T1 + 2 * MIN
    old = eng.market.final["ETH"]
    old = old[(old.index >= m1 - 5 * MIN) & (old.index < t3)].copy()
    old.loc[m1, "close"] = 7.0
    eng.market.copy[("ETH", t3)] = old
    eng.market.lag["ETH"] = -200 * S                     # made before the answer that confirmed m1
    step(eng, t3)
    check("candle_after: an older answer does not undo a confirmed row", close(eng, "ETH", m1) == fin(eng, "ETH", m1))
    shutil.rmtree(sd)


class RepairMarket(NB.SynthMarket):
    """Adds trades_bars (the repair path): made-up bars, so a rebuilt row is visible."""

    def trades_bars(self, coin, m0, m1, deadline=None):
        self.asked = getattr(self, "asked", []) + [(coin, m0, m1)]
        bars = {x: made_up(50.0) for x in pd.date_range(m0, m1, freq="min")}
        return dict(bars=bars, verified=True, reason=None, pages=1)


def _repair():
    eng, sd = eng_of()
    mk = RepairMarket(["BTC", "ETH"], 40)
    mk.lag = dict(eng.market.lag)
    eng.market = mk
    for j in range(3):                                     # trades rows, then confirmed by the next answers
        step(eng, T1 + j * MIN)
    t = T1 + 3 * MIN
    eng.update_spot(t)
    m = t - MIN
    # minutes m-4 .. m-1: the first answer's candle row, then three trades rows each confirmed by a later answer
    open_before = [mm for mm in pd.date_range(m - 4 * MIN, m - MIN, freq="min") if eng._open("ETH", mm)]
    before = eng.spot["ETH"].copy()
    mk.asked = []
    eng.counts = {}
    eng.trades_pass(m)
    conf = [mm for mm in pd.date_range(m - 4 * MIN, m - MIN, freq="min")
            if eng._prov["ETH"].get(mm, (None, True))[1] is False]
    check("repair: confirmed minutes are not open", open_before == [] and len(conf) == 4, f"{open_before} {conf}")
    check("repair: the trades pass asks for no repair and rebuilds none of them (only minute m from trades)",
          all(before.loc[mm].equals(eng.spot["ETH"].loc[mm]) for mm in conf) and mk.asked == []
          and close(eng, "ETH", m) == fin(eng, "ETH", m) and not eng.counts.get("tb_rebuilt"), str(eng.counts))
    # an unconfirmed candle row (trades failed for it, the answer not late enough) is still repaired
    eng2, sd2 = eng_of()
    mk2 = RepairMarket(["BTC", "ETH"], 40)
    mk2.lag = dict(eng2.market.lag)
    eng2.market = mk2
    step(eng2, T1)
    mk2.tb[("ETH", T1)] = dict(bar=None, verified=False, reason="stale_first_page")
    mk2.trades_bars = lambda coin, m0, m1, deadline=None: dict(bars={x: None for x in pd.date_range(m0, m1, freq="min")},
                                                                verified=False, reason="stale_first_page", pages=1)
    eng2.update_spot(T1 + MIN)
    eng2.trades_pass(T1)                                  # T1 keeps its first-seen candle row (not confirmed)
    mk2.trades_bars = RepairMarket.trades_bars.__get__(mk2)
    mk2.lag["ETH"] = -40 * S                              # the next answer is not confirmed for T1 either
    eng2.update_spot(T1 + 2 * MIN)
    eng2.counts = {}
    eng2.trades_pass(T1 + MIN)
    check("repair: an unconfirmed candle row is still rebuilt from trades, as today",
          close(eng2, "ETH", T1) == 50.0 and eng2.counts.get("tb_rebuilt") == 1, str(eng2.counts))
    shutil.rmtree(sd)
    shutil.rmtree(sd2)


def _stale_guard():
    res = {}
    for rows in ("keep", "candle_after"):
        out = []
        for case in ("btc_trades", "btc_error_fresh", "btc_error_old"):
            eng, sd = eng_of(rows, coins=("ETH", "SOL"), stale_guard=True)
            eng.tradable = list(eng.coins)                       # the two-coin universe
            eng.market.candle_meta = {}
            m = T1 - MIN
            eng.market.first[("SOL", m)] = None
            if case != "btc_trades":
                eng.market.tb[("BTC", m)] = RuntimeError("network")
            if case == "btc_error_old":
                eng.market.lag["BTC"] = -40 * S                  # BTC's answer made before m closed
            step(eng, T1 - 2 * MIN)
            step(eng, T1 - MIN)
            step(eng, T1)
            stale = eng.data_checks(m)
            out.append((case, stale, sorted(eng._skip_old)))
            shutil.rmtree(sd)
        res[rows] = out
    check("stale guard: the newest minute gives the same answer in keep and candle_after", res["keep"] == res["candle_after"],
          str(res))
    check("stale guard: BTC trades-built fresh; BTC from an old answer stale", res["candle_after"][0][1][0] is False
          and res["candle_after"][2][1][0] is True, str(res["candle_after"]))


def _pending():
    for rows in ("candle_after", "keep"):
        eng, sd = eng_of(rows)
        eng.market.lag = {"BTC": None, "ETH": None}         # answers of unknown age: no row is ever confirmed
        for j in range(7):
            step(eng, T1 + j * MIN)
        m = T1 + 5 * MIN                                 # the minute that closed before the last step
        eng.counts = {}
        eng.data_checks(m)
        if rows == "candle_after":
            check("counter tb_pending: rows 3 to 6 minutes old still trades-built, 4 per coin",
                  eng.counts.get("tb_pending") == 8 and not eng.counts.get("rows_open"), str(eng.counts))
        else:
            check("keep: no tb_pending", "tb_pending" not in eng.counts, str(eng.counts))
        shutil.rmtree(sd)


def scenario(eng, seed, steps=14):
    """A random session: first-seen candles altered or missing, trades bars made up or failing, a minute the venue
    has no bar for, answers 6 s after the step (some of unknown age). Returns the steps."""
    rng = np.random.default_rng(seed)
    mk = eng.market
    coins = ["BTC"] + eng.coins
    ts = [T1 + j * MIN for j in range(steps)]
    gone = (eng.coins[0], T1 + 3 * MIN)
    mk.final[gone[0]] = mk.final[gone[0]].drop(gone[1])
    mk.tb[gone] = made_up(5.0)
    for t in ts:
        m = t - MIN
        for c in coins:
            u = rng.random()
            if u < 0.2:
                mk.first[(c, m)] = None
            elif u < 0.4:
                mk.first[(c, m)] = made_up(100.0 + rng.random())
            v = rng.random()
            if (c, m) == gone:
                continue
            if v < 0.3:
                mk.tb[(c, m)] = made_up(100.0 + rng.random())
            elif v < 0.4:
                mk.tb[(c, m)] = dict(bar=None, verified=False, reason="incomplete")
    return ts, gone


def _session():
    eng, sd = eng_of(coins=("ETH", "SOL"))
    ts, gone = scenario(eng, 5)
    for t in ts:
        step(eng, t)
    last = ts[-1]
    bad = []
    for c in ["BTC"] + eng.coins:
        have = eng.spot[c][eng.spot[c].index <= last - 4 * MIN]
        f = eng.market.final[c]
        want = f[(f.index >= have.index.min()) & (f.index <= last - 4 * MIN)]
        if not have[COLS].equals(want[COLS]):
            bad.append(c)
    check("session: every row older than three minutes equals the venue's final candles, every listed coin", not bad,
          str(bad))
    check("session: the minute the venue has no bar for has no row", gone[1] not in eng.spot[gone[0]].index)
    shutil.rmtree(sd)


def _identity():
    bad = []
    for mode in ("trades", "candles"):
        for seed in (1, 2, 3):
            runs = []
            for rows in (None, "keep"):
                extra = {} if rows is None else {"trades_rows": rows}
                eng, sd = NB.synth_engine(mode, coins=("ETH", "SOL"), **extra)
                eng.market.lag = {c: (None if c == "SOL" else 6 * S) for c in ["BTC", "ETH", "SOL"]}
                ts, _ = scenario(eng, seed)
                trace = []
                for t in ts:
                    eng.update_spot(t)
                    if mode == "trades":
                        eng.trades_pass(t - MIN)
                    eng.data_checks(t - MIN)
                    trace.append(({c: df.copy() for c, df in eng.spot.items()}, repr(sorted(
                        (c, sorted(p.items())) for c, p in eng._prov.items())), dict(eng.counts), dict(eng._cmax)))
                runs.append(trace)
                shutil.rmtree(sd)
            a, b = runs
            same = all(set(x[0]) == set(y[0]) and all(x[0][c].equals(y[0][c]) for c in x[0]) and x[1:] == y[1:]
                       for x, y in zip(a, b))
            if not same:
                bad.append((mode, seed))
    check("key absent and \"keep\": identical tables, provenance, counts and re-fetch anchors at every step "
          "(trades and candles mode, three random sessions each)", not bad, str(bad))


def part2():
    if not os.path.exists(os.path.join(ROOT, "data", "minute", "BTC.parquet")):
        print("SKIPPED part 2: data/minute is not here (runs on a runner with the whole repository)")
        return
    mkt = NB.make_market()
    for mode in ({}, {"newest_bar": "trades"}, {"newest_bar": "trades", "stale_guard": True}):
        e0, _, _ = NB.run(mkt, dict(mode), "absent")
        e1, _, _ = NB.run(mkt, dict(mode, trades_rows="keep"), "keep")
        check(f"replay {mode}: identical event log with the key absent and \"keep\" ({len(e0)} events)", e0 == e1)
    e2, _, eng = NB.run(mkt, {"newest_bar": "trades", "trades_rows": "candle_after"}, "candle_after")
    errs = [e for e in e2 if e["kind"] == "error"]
    hb = [e for e in e2 if e["kind"] == "heartbeat"]
    check("replay candle_after: runs through with no error event and heartbeats", not errs and hb and eng.lm_ok,
          str(errs[:2]))


def main():
    part1()
    if "--part1" not in sys.argv:
        part2()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {FAILS}")
        sys.exit(1)
    print("candle_after_test: all passed")


if __name__ == "__main__":
    main()
