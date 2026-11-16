#!/usr/bin/env python3
"""Test of the setting "candles_at_s" (bot/spot/README.md, "Candle requests between steps"). No network, no keys, no
real clock and no real sleep: a fake clock (epoch seconds) drives the engine's wait, the candle pass and the market.

The market is the synthetic one of newest_bar_test.py on that fake clock: a candle request takes a set time and is
answered as the venue would answer it then (made at the request's own time, no row for the minute open then).
Checks:
  - configuration: only with "newest_bar": "trades", only from confirm_s + 5 to 50 seconds, a number;
  - paper: the pass runs once per minute, at the set second, in one go, each request exactly update_spot's with end
    = the open minute, and never gives the open minute a row; a second call for the same minute asks nothing;
  - live: fast polls every poll seconds before and during the pass; the pass's requests sit between them, a few per
    turn (the times of the fake's calls); the pass ends before the step;
  - the pass starts no request that would end within 3 s of the step; the coins it did not reach are fetched by the
    step and counted as pre_missing; a failed request (pre_error) is left to the step too;
  - the step asks no candles for the coins the pass covered and fetches the others (coins not on the trades list
    always); pre_missing when the pass did not run for this minute;
  - on demand: after an unverified trades bar, a trades error or the budget, that coin's candle is fetched in the
    step (end = the step's minute) and the row is the candle's, with today's counters; after a rate limit or a
    refusal, no candle request in that step, the coins have no new row and the stale guard skips them;
  - candle_old and btc_candle_old: not counted for a trades-built row (or a verified empty minute) with the setting;
    still counted otherwise, and counted as before without the setting;
  - without the setting the step asks every coin's candles with end = its minute, and no new counter appears;
  - the pass's requests have one try of 4 s (the step's and the on-demand requests are today's); a request that
    raises or gives no rows counts pre_error, is not marked fetched and is left to the step; no request starts
    unless a whole 4 s timeout would end before the stop; the live turn rule is judged by the last request.

Usage: python bot/spot/candle_pass_test.py
"""
import os
import shutil
import sys
import tempfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot import market as BM  # noqa: E402
from bot.spot import engine as E  # noqa: E402
from bot.spot import newest_bar_test as NB  # noqa: E402

MIN = pd.Timedelta(minutes=1)
T = NB.T0 + 20 * MIN                     # a step minute of the synthetic market (40 minutes from NB.T0)
FAILS = NB.FAILS
check = NB.check
NEW = ("pre_missing", "pre_fetched", "pre_error", "pre_ondemand", "step_candles")


def ep(ts):
    return pd.Timestamp(ts).timestamp()


class ClockMarket(NB.SynthMarket):
    """SynthMarket on a fake clock F (a one-element list, epoch seconds). A candle request takes `dur` seconds of the
    fake clock; its answer was made at the request's time minus `age` seconds and holds no row for the minute open
    at the request's time. `fail` holds coins whose next candle request raises; `empty` holds coins whose next
    candle request gives no rows (a 429 on the pass's one try). `req` records every request, with the keywords it
    was given (tries and timeout; None when not given)."""

    def __init__(self, coins, F, dur=0.31, age=0.0):
        super().__init__(coins, 40)
        self.F, self.dur, self.age, self.req, self.fail, self.candle_meta = F, dur, age, [], set(), {}
        self.empty = set()

    def spot_candles(self, coin, start, end, tries=None, timeout=None):
        at = self.F[0]
        self.req.append(dict(coin=coin, start=start, end=end, at=at, tries=tries, timeout=timeout))
        self.F[0] += self.dur
        if coin in self.fail:
            self.fail.discard(coin)
            raise RuntimeError("timeout")
        if coin in self.empty:
            self.empty.discard(coin)
            return super().spot_candles(coin, start, end).iloc[:0]
        now = pd.Timestamp(at, unit="s")
        self.candle_meta[coin] = {"gen": now - pd.Timedelta(seconds=self.age), "start": start}
        d = super().spot_candles(coin, start, end)
        return d[d.index < now.floor("min")]


def engine(coins=("ETH", "SOL"), at=45, **cfg):
    if at is not None:
        cfg["candles_at_s"] = at
    cfg.setdefault("trades_rows", "candle_after")          # the release's inputs
    eng, sd = NB.synth_engine("trades", coins=coins, **cfg)
    F = [ep(T) + 6.0]
    eng.market = ClockMarket(["BTC"] + eng.coins, F)
    eng.clock = lambda: pd.Timestamp(F[0], unit="s")
    eng.refresh_adv = lambda t: None                       # the synthetic market has no daily candles
    eng.update_spot(T)                                      # start-up: backfill and the trades pass of T - 1
    eng.trades_pass(T - MIN)
    eng.counts = {}
    return eng, sd, F


def sleeper(F, log):
    def sleep(x):
        log.append((F[0], x))
        F[0] += max(0.0, x)
    return sleep


def step(eng, F, t):
    """The step of minute t, at t + 6 s on the fake clock; returns the candle requests it made."""
    F[0] = ep(t) + 6.0
    n = len(eng.market.req)
    eng.step(t)
    return eng.market.req[n:]


def config_errors():
    def err(**cfg):
        sd = tempfile.mkdtemp(prefix="cp_cfg_")
        try:
            E.Engine(mode="paper", cfg=dict(NB.CFG, newest_bar=cfg.pop("newest_bar", "trades"), **cfg), state_dir=sd,
                     broker=E.PaperBroker(0.5), clock=lambda: NB.T0, echo=False)
            return None
        except ValueError as e:
            return str(e)
        finally:
            shutil.rmtree(sd)
    check("config: candles_at_s needs newest_bar trades", err(newest_bar="candles", candles_at_s=45) is not None)
    check("config: candles_at_s 29.9 refused (confirm_s 25: from 30)", err(candles_at_s=29.9) is not None)
    check("config: candles_at_s 50.5 refused", err(candles_at_s=50.5) is not None)
    check("config: candles_at_s as text refused", err(candles_at_s="45") is not None)
    check("config: candles_at_s true refused", err(candles_at_s=True) is not None)
    check("config: candles_at_s 30, 45 and 50 accepted", err(candles_at_s=30) is None and err(candles_at_s=45) is None
          and err(candles_at_s=50) is None)
    check("config: with confirm_s 30, 34 refused and 35 accepted",
          err(candles_at_s=34, confirm_s=30) is not None and err(candles_at_s=35, confirm_s=30) is None)
    eng, sd = NB.synth_engine("trades")
    check("config: absent means None (no candle pass)", eng.candles_at_s is None)
    shutil.rmtree(sd)


def paper():
    eng, sd, F = engine()
    F[0] = ep(T) + 10.0                                     # after the step of T; the minute T is open
    sl = []
    nxt = ep(T + MIN) + 6.0
    n = len(eng.market.req)
    eng.fast_poll = lambda: sl.append(("poll", F[0]))
    eng._wait_step(nxt, 0.0, now=lambda: F[0], sleep=sleeper(F, sl))
    rq = eng.market.req[n:]
    check("paper: one request per coin built from trades (BTC, ETH, SOL)",
          [r["coin"] for r in rq] == ["BTC", "ETH", "SOL"], str([r["coin"] for r in rq]))
    gap = all(abs(rq[i + 1]["at"] - rq[i]["at"] - 0.31) < 1e-6 for i in range(len(rq) - 1))
    check("paper: the pass starts at the set second (T + 45 s) and runs in one go",
          abs(rq[0]["at"] - (ep(T) + 45)) < 1e-6 and gap, str([r["at"] - ep(T) for r in rq]))
    check("paper: every request ends at the open minute T (as update_spot(T))", all(r["end"] == T for r in rq))
    check("paper: no row for the open minute", all(T not in eng.spot[c].index for c in ["BTC", "ETH", "SOL"]))
    check("paper: then sleeps to the step (6 s after the minute); no fast poll in paper",
          abs(F[0] - nxt) < 1e-6 and not [x for x in sl if x[0] == "poll"])
    m1 = T - MIN
    check("paper: the answer (made at T + 45 s) confirms T - 1: its trades row is now the venue's candle",
          eng.spot["ETH"].loc[m1].equals(eng.market.final["ETH"].loc[m1]) and eng._prov["ETH"][m1][1] is False
          and eng._confirmed(m1, eng._prov["ETH"][m1][0]))
    n = len(eng.market.req)
    eng.candle_pass(T)
    check("paper: once per minute (a second call for the same minute asks nothing)", len(eng.market.req) == n)
    check("paper: counted pre_fetched 3", eng.counts.get("pre_fetched") == 3, str(eng.counts))
    eng.counts = {}
    rq = step(eng, F, T + MIN)
    check("step after the pass: no candle request for the coins it covered", rq == [], str(rq))
    check("step after the pass: step_candles 0, no pre_missing", eng.counts.get("step_candles") == 0
          and "pre_missing" not in eng.counts, str(eng.counts))
    check("step after the pass: the minute T is trades-built", eng._prov["ETH"][T][1] and T in eng.spot["ETH"].index)
    check("step after the pass: candle_old not counted for trades-built rows (answers made at T + 45 s)",
          "candle_old" not in eng.counts and "btc_candle_old" not in eng.counts, str(eng.counts))
    shutil.rmtree(sd)


def live():
    coins = ("ETH", "SOL", "XRP", "DOGE", "LTC")
    eng, sd = engine(coins=coins)[:2]
    F = eng.market.F
    F[0] = ep(T) + 10.0
    polls, sl = [], []
    eng.fast_poll = lambda: polls.append(F[0])
    nxt = ep(T + MIN) + 6.0
    n = len(eng.market.req)
    eng._wait_step(nxt, 1.0, now=lambda: F[0], sleep=sleeper(F, sl))
    rq = eng.market.req[n:]
    gaps = [b - a for a, b in zip(polls, polls[1:])]
    check("live: fast polls keep their 1 s cadence before and during the pass", polls and
          all(abs(g - 1.0) < 1e-6 for g in gaps), f"{len(polls)} polls, gaps {sorted(set(round(g, 3) for g in gaps))}")
    check("live: the last fast poll comes before nxt - poll - 1, as without the setting", polls[-1] < nxt - 1.0 + 1e-6)
    check("live: all six coins fetched, none before the set second",
          sorted(r["coin"] for r in rq) == sorted(["BTC"] + list(coins)) and min(r["at"] for r in rq) >= ep(T) + 45)
    per = {}
    for r in rq:
        k = sum(1 for p in polls if p <= r["at"])          # the turn: fast polls before the request
        per[k] = per.get(k, 0) + 1
    check("live: the pass's requests come in slices between fast polls (3 per 1 s turn with 0.31 s requests)",
          sorted(per.values()) == [3, 3], str(per))
    check("live: no request overlaps a fast poll", all(not (r["at"] < p < r["at"] + 0.31) for r in rq for p in polls))
    check("live: the pass ended before the step", max(r["at"] for r in rq) + 0.31 <= nxt - 3)
    check("live: every request ends at the open minute T, no row for T",
          all(r["end"] == T for r in rq) and all(T not in eng.spot[c].index for c in ["BTC"] + list(coins)))
    check("live: then sleeps to the step", abs(F[0] - nxt) < 1e-6)
    eng.counts = {}
    rq = step(eng, F, T + MIN)
    check("live: the step then asks no candles", rq == [] and "pre_missing" not in eng.counts, str(eng.counts))
    shutil.rmtree(sd)


def stop_before_step():
    coins = ("ETH", "SOL", "XRP", "DOGE", "LTC")
    for poll in (1.0, 0.0):
        eng, sd = engine(coins=coins, at=50)[:2]
        F = eng.market.F
        eng.market.dur = 4.0                                # slow requests
        F[0] = ep(T) + 10.0
        eng.fast_poll = lambda: None
        nxt = ep(T + MIN) + 6.0
        n = len(eng.market.req)
        eng._wait_step(nxt, poll, now=lambda: F[0], sleep=sleeper(F, []))
        rq = eng.market.req[n:]
        tag = "live" if poll else "paper"
        check(f"stop ({tag}): no pass request ends within 3 s of the step (4 s requests from T + 50 s: 3 done)",
              len(rq) == 3 and max(r["at"] for r in rq) + 4.0 <= nxt - 3, str([r["at"] - ep(T) for r in rq]))
        eng.market.dur = 0.31
        eng.counts = {}
        rq2 = step(eng, F, T + MIN)
        left = [c for c in ["BTC"] + list(coins) if c not in [r["coin"] for r in rq]]
        check(f"stop ({tag}): the step fetches the coins left, counted as pre_missing",
              [r["coin"] for r in rq2] == left and eng.counts.get("pre_missing") == len(left) == 3
              and all(r["end"] == T + MIN for r in rq2), f"{[r['coin'] for r in rq2]} {eng.counts}")
        shutil.rmtree(sd)


def step_coins():
    eng, sd, F = engine(trades_coins=["BTC", "ETH"])
    F[0] = ep(T) + 45
    eng.candle_pass(T)
    check("listed: the pass asks only the coins built from trades (BTC, ETH)",
          [r["coin"] for r in eng.market.req if r["end"] == T and r["at"] >= ep(T) + 45] == ["BTC", "ETH"])
    eng.counts = {}
    rq = step(eng, F, T + MIN)
    check("listed: the step fetches only the coin not on the trades list (SOL), no pre_missing",
          [r["coin"] for r in rq] == ["SOL"] and "pre_missing" not in eng.counts
          and eng.counts.get("step_candles") == 1, f"{[r['coin'] for r in rq]} {eng.counts}")
    eng.counts = {}
    rq = step(eng, F, T + 2 * MIN)                          # no pass for the minute T + 1
    check("no pass this minute: the step fetches every coin, pre_missing for the two built from trades",
          [r["coin"] for r in rq] == ["BTC", "ETH", "SOL"] and eng.counts.get("pre_missing") == 2,
          f"{[r['coin'] for r in rq]} {eng.counts}")
    shutil.rmtree(sd)
    eng, sd, F = engine()
    F[0] = ep(T) + 45
    eng.market.fail.add("ETH")
    left = eng.candle_pass(T)
    check("failed request: the pass goes on (pre_error 1), nothing left, never raises",
          left == 0 and eng.counts.get("pre_error") == 1 and eng.counts.get("pre_fetched") == 2, str(eng.counts))
    eng.counts = {}
    rq = step(eng, F, T + MIN)
    check("failed request: the step fetches that coin, counted as pre_missing",
          [r["coin"] for r in rq] == ["ETH"] and eng.counts.get("pre_missing") == 1, f"{rq} {eng.counts}")
    shutil.rmtree(sd)


def on_demand():
    cases = (("unverified", dict(bar=None, verified=False, reason="incomplete", pages=1), "tb_fb_unverified"),
             ("error", RuntimeError("timeout"), "tb_fb_error"))
    for tag, v, k in cases:
        eng, sd, F = engine()
        F[0] = ep(T) + 45
        eng.candle_pass(T)
        eng.market.tb[("ETH", T)] = v
        eng.market.first[("ETH", T)] = dict(open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)   # first-seen candle
        eng.counts = {}
        rq = step(eng, F, T + MIN)
        check(f"on demand ({tag}): one candle request in the step, for ETH, end = the step's minute",
              [(r["coin"], r["end"]) for r in rq] == [("ETH", T + MIN)], str(rq))
        check(f"on demand ({tag}): ETH's row for T is the candle's, as without the setting",
              eng.spot["ETH"].loc[T, "close"] == 1.5 and not eng._prov["ETH"].get(T, (None, False))[1])
        check(f"on demand ({tag}): counters {k} 1, pre_ondemand 1, step_candles 1, tb_built 2",
              eng.counts.get(k) == 1 and eng.counts.get("pre_ondemand") == 1 and eng.counts.get("step_candles") == 1
              and eng.counts.get("tb_built") == 2, str(eng.counts))
        shutil.rmtree(sd)
    eng, sd, F = engine(trades_budget_s=8.0)
    F[0] = ep(T) + 45
    eng.candle_pass(T)
    NB.CLOCK[0] = 0.0
    eng.market.slow = 5.0                                   # each trades request takes 5 s of the pass's timer
    eng.counts = {}
    rq = step(eng, F, T + MIN)
    eng.market.slow = 0.0
    check("on demand (budget): the coin the budget left out (SOL) gets its candle in the step",
          [r["coin"] for r in rq] == ["SOL"] and eng.counts.get("tb_fb_budget") == 1
          and eng.counts.get("pre_ondemand") == 1 and T in eng.spot["SOL"].index, f"{rq} {eng.counts}")
    shutil.rmtree(sd)
    for tag, exc, k in (("rate limit", BM.Limited("HTTP 429"), "tb_fb_limited"),
                        ("refusal", BM.Refused("HTTP 403"), "tb_fb_error")):
        eng, sd, F = engine(stale_guard=True)
        eng.tradable = list(eng.coins)
        F[0] = ep(T) + 45
        eng.candle_pass(T)
        eng.market.tb[("ETH", T)] = exc
        eng.counts = {}
        rq = step(eng, F, T + MIN)
        check(f"no on demand ({tag}): no candle request in the step", rq == [], str(rq))
        check(f"no on demand ({tag}): ETH and SOL have no row for T; {k} 2",
              T not in eng.spot["ETH"].index and T not in eng.spot["SOL"].index and eng.counts.get(k) == 2,
              str(eng.counts))
        check(f"no on demand ({tag}): the stale guard skips them (no new bid)", eng._skip_old == {"ETH", "SOL"}
              and eng.counts.get("skip_old") == 2, str(eng._skip_old))
        check(f"no on demand ({tag}): candle_old counted for them (their answers were made before T ended), "
              "not for BTC's trades-built row",
              eng.counts.get("candle_old") == 2 and "btc_candle_old" not in eng.counts, str(eng.counts))
        shutil.rmtree(sd)


def candle_old():
    eng, sd, F = engine()
    eng.market.tb[("ETH", T)] = None                        # ETH: a verified empty minute
    F[0] = ep(T) + 45
    eng.candle_pass(T)
    eng.counts = {}
    step(eng, F, T + MIN)
    check("candle_old: not counted for a verified empty minute nor for trades-built rows",
          "candle_old" not in eng.counts and "btc_candle_old" not in eng.counts and eng.counts.get("tb_empty") == 1,
          str(eng.counts))
    shutil.rmtree(sd)
    for at in (45, None):
        eng, sd, F = engine(at=at)
        eng.market.age = 30.0                               # old copies: made 30 s before the request
        eng.counts = {}
        step(eng, F, T + MIN)                               # no pass ran: the step fetches every coin
        tag = "with the setting" if at else "without the setting"
        want = {} if at else {"candle_old": 2, "btc_candle_old": 1}
        got = {k: eng.counts[k] for k in ("candle_old", "btc_candle_old") if k in eng.counts}
        check(f"candle_old ({tag}): answers made before the minute ended, rows trades-built: counted {want}",
              got == want, str(eng.counts))
        shutil.rmtree(sd)


def absent():
    eng, sd, F = engine(at=None)
    eng.counts = {}
    rq = step(eng, F, T + MIN)
    check("absent: the step asks every coin's candles, end = its minute",
          [(r["coin"], r["end"]) for r in rq] == [("BTC", T + MIN), ("ETH", T + MIN), ("SOL", T + MIN)], str(rq))
    check("absent: no new counter", not set(NEW) & set(eng.counts), str(eng.counts))
    shutil.rmtree(sd)


def pass_timeout():
    """The pass's requests: one try of E.PASS_TIMEOUT_S (4 s); a failed one or one without rows leaves the coin to
    the step; the stop rule counts a whole timeout."""
    check("pass: PASS_TRIES 1 and PASS_TIMEOUT_S 4.0", E.PASS_TRIES == 1 and E.PASS_TIMEOUT_S == 4.0)
    # a. keywords; a request that raises (a timeout)
    eng, sd, F = engine()
    F[0] = ep(T) + 45
    eng.market.fail.add("ETH")
    n = len(eng.market.req)
    eng.candle_pass(T)
    rq = eng.market.req[n:]
    check("pass: every request with tries 1 and timeout 4.0",
          [(r["coin"], r["tries"], r["timeout"]) for r in rq] == [(c, 1, 4.0) for c in ("BTC", "ETH", "SOL")], str(rq))
    check("pass, a request that raises: pre_error 1, the pass goes on (BTC and SOL fetched), ETH not marked fetched",
          eng.counts.get("pre_error") == 1 and eng.counts.get("pre_fetched") == 2 and "ETH" not in eng._cpass
          and eng._cpass.get("BTC") == T and eng._cpass.get("SOL") == T, f"{eng.counts} {eng._cpass}")
    eng.market.tb[("SOL", T)] = RuntimeError("timeout")    # SOL: its trades bar fails, so it is fetched on demand
    eng.counts = {}
    rq = step(eng, F, T + MIN)
    check("pass, a request that raises: the step fetches ETH (pre_missing 1); SOL on demand (pre_ondemand 1)",
          [(r["coin"], r["end"]) for r in rq] == [("ETH", T + MIN), ("SOL", T + MIN)]
          and eng.counts.get("pre_missing") == 1 and eng.counts.get("pre_ondemand") == 1, f"{rq} {eng.counts}")
    check("step and on-demand requests: called without tries and timeout (today's request)",
          [(r["tries"], r["timeout"]) for r in rq] == [(None, None)] * 2, str(rq))
    shutil.rmtree(sd)
    # b. a request that gives no rows (a 429 on the one try: bot/market.py returns an empty table)
    eng, sd, F = engine()
    F[0] = ep(T) + 45
    before = eng.spot["ETH"].copy()
    eng.market.empty.add("ETH")
    left = eng.candle_pass(T)
    check("pass, an answer without rows: pre_error 1, the pass goes on, ETH not marked fetched, its table unchanged",
          left == 0 and eng.counts.get("pre_error") == 1 and eng.counts.get("pre_fetched") == 2
          and "ETH" not in eng._cpass and eng.spot["ETH"].equals(before), f"{eng.counts} {eng._cpass}")
    eng.counts = {}
    rq = step(eng, F, T + MIN)
    check("pass, an answer without rows: the step fetches ETH, counted pre_missing",
          [r["coin"] for r in rq] == ["ETH"] and eng.counts.get("pre_missing") == 1
          and T in eng.spot["ETH"].index, f"{rq} {eng.counts}")
    shutil.rmtree(sd)
    # c. the stop rule: a whole timeout must fit before stop, whatever the last request took
    S = ep(T) + 63.0
    for off, want in ((-0.01, 1), (+0.01, 0)):
        eng, sd, F = engine(coins=("ETH", "SOL", "XRP"))
        eng.market.dur = 0.1
        F[0] = S - 20.0
        eng.candle_pass(T, stop=S, turn_end=F[0] + 0.05, now=lambda: F[0])    # one 0.1 s request: the last one
        F[0] = S - 4.0 + off
        n = len(eng.market.req)
        eng.candle_pass(T, stop=S, now=lambda: F[0])
        rq = eng.market.req[n:]
        check(f"stop: last request 0.1 s; at stop - 4.0 {off:+.2f} s, {want} request starts",
              len(rq) == want and (not rq or abs(rq[0]["at"] - (S - 4.01)) < 1e-6), str([r["at"] - S for r in rq]))
        shutil.rmtree(sd)
    eng, sd, F = engine(coins=("ETH", "SOL", "XRP"))
    eng.market.dur = 4.0
    F[0] = S - 4.0 - 0.01
    n = len(eng.market.req)
    eng.candle_pass(T, stop=S, now=lambda: F[0])
    rq = eng.market.req[n:]
    check("stop: a request that takes the whole 4.0 s from the last allowed start ends before stop; no other starts",
          len(rq) == 1 and rq[0]["at"] + 4.0 < S and F[0] < S, str([r["at"] - S for r in rq]))
    shutil.rmtree(sd)
    # d. the live turn rule is still judged by the last request's length (not the timeout)
    eng, sd, F = engine(coins=("ETH", "SOL", "XRP", "DOGE"))
    eng.market.dur = 0.1
    F[0] = ep(T) + 45.0
    n = len(eng.market.req)
    eng.candle_pass(T, stop=ep(T) + 63.0, turn_end=F[0] + 0.35, now=lambda: F[0])
    rq = eng.market.req[n:]
    check("turn: 0.1 s requests in a 0.35 s turn: three requests (turn_end judged by the last request)",
          len(rq) == 3, str([round(r["at"] - ep(T), 2) for r in rq]))
    shutil.rmtree(sd)


def main():
    E.WINDOW_MIN = 30
    try:
        config_errors()
        paper()
        live()
        stop_before_step()
        step_coins()
        on_demand()
        candle_old()
        absent()
        pass_timeout()
    finally:
        E.WINDOW_MIN = 11 * 1440
    print(f"candle_pass_test: {'all passed' if not FAILS else 'FAILED: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
