#!/usr/bin/env python3
"""Test of the setting "trades_workers" (bot/spot/README.md, "Trades side by side"): the trades pass asks several coins
side by side. No network, no keys.

Part 1, the market (bot/market.py minute_trades_many and _get_h), with a fake venue behind fake sessions, controlled
by events and short real sleeps:
  - pacing: 3 workers and 40 requests: no two sends closer than 1/7 s (2 ms allowed for timer noise at the fake), never
    more than 7 in any one-second window; the sequential path's send times are those of today's formula;
  - a stalled request delays only its own job: the other 17 jobs finish while it is blocked;
  - outcomes come back in the input order whatever the completion order;
  - stop: a 429 (Limited), then separately a 403 (Refused), at one job: zero requests sent after that moment (not even
    the next page of a job in the middle of paging); the job finished before keeps its result; the rest report the stop;
  - deadline: jobs not started by the deadline are not asked; a job in flight at the deadline is reported as not
    finished and its late result is not delivered; no request starts after the deadline; the call returns by the
    deadline; a worker still blocked does not disturb the next pass and sends nothing more;
  - an exception in one job (a connection error after its retry) is that job's outcome only;
  - one session per thread; worker threads are daemon threads and a blocked one does not hold up the process's exit.
Part 2, the engine, with a fake market whose many-method has no threads (a model of the workers' timing on the
engine's timer, deterministic):
  - parity: the same scripted data through trades_workers 1 and 3 gives identical spot tables, provenance, counters,
    _fb, _fb_stop, tb_err, _cmax and log events (heartbeat step_s included) over 34 minutes with repairs, an empty
    minute, an unverified answer, budget fallbacks, an error for one coin, and (in separate runs) a rate limit and a
    refusal at a coin in the middle of the order; once more with candle_after, candles_at_s and the candle pass;
  - the differences, each shown: after a stop the workers path applies whatever had arrived (sequential: the coins
    before the refused one, none after); a coin the sequential path would not reach within the budget is reached by
    the workers; a result that arrives after the deadline is thrown away (sequential: applied);
  - the plan worked out up front (_cmax default, open minutes) equals what the sequential loop works out coin by coin;
  - validation: 0, -1, 1.5, "3", 7 and true refuse to start; 1 and absent take the sequential path (the many-method is
    never called); 3 with a market that lacks the method takes the sequential path;
  - outside trades mode the key is ignored with one warning event;
  - step_s has the "trades" entry in both paths (and none in candle mode);
  - config.tw.json is config.json with "trades_workers": 3 and nothing else changed.

Usage: python bot/spot/trades_workers_test.py
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from email.utils import format_datetime

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot import market as M  # noqa: E402
from bot.spot import engine as E  # noqa: E402
from bot.spot import newest_bar_test as NB  # noqa: E402

FAILS = NB.FAILS
check = NB.check
GAP = 1.0 / M.TRADES_RATE
M0 = pd.Timestamp("2026-11-10 15:04")
E0 = M0 + pd.Timedelta(minutes=1)
BASE_THREADS = threading.active_count()


# ------------------------------------------------------------------------------------------------ part 1: the market
def iso(t):
    return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def http_date(t):
    return format_datetime(pd.Timestamp(t).tz_localize("UTC").to_pydatetime(), usegmt=True)


def px(coin):
    return 100.0 + int(coin[1:])


def page_done(coin):
    """One page that proves the minute complete: a trade after it, one in it (the coin's price), one before it."""
    rows = [dict(time=iso(M0 + pd.Timedelta(seconds=s)), trade_id=i, price=str(p), size="1")
            for s, i, p in ((70, 30, px(coin) + 5), (30, 20, px(coin)), (-5, 10, px(coin) - 5))]
    return 200, rows, {"Date": http_date(E0 + pd.Timedelta(seconds=6))}


def page_first(coin):
    """A first page with trades of the minute only: paging must go on (CB-AFTER 50)."""
    rows = [dict(time=iso(M0 + pd.Timedelta(seconds=s)), trade_id=i, price=str(px(coin)), size="1")
            for s, i in ((70, 60), (40, 55), (20, 51))]
    return 200, rows, {"Date": http_date(E0 + pd.Timedelta(seconds=6)), "CB-AFTER": "51"}


class Resp(object):
    def __init__(self, code, js, headers):
        self.status_code, self._js, self.headers, self.text = code, js, headers, "x"

    def json(self):
        return self._js

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("HTTP %s" % self.status_code)


class Venue(object):
    """Serves the trades list per coin through handlers (coin -> f(params) -> (code, json, headers), may block or
    raise); default: page_done. Records every request: coin, cursor, time.time(), time.monotonic(), thread, session."""

    def __init__(self, handlers=None):
        self.h, self.calls, self.answered, self.lock = dict(handlers or {}), [], [], threading.Lock()
        self.stamp = None                                  # a clock read at each request (tests of the deadline)

    def serve(self, sess, url, params):
        coin = url.split("/products/")[1].split("-USD")[0]
        with self.lock:
            self.calls.append(dict(coin=coin, after=(params or {}).get("after"), t=time.time(),
                                   mono=time.monotonic(), thread=threading.get_ident(), sess=id(sess),
                                   clk=self.stamp() if self.stamp else None))
        f = self.h.get(coin)
        out = f(params or {}) if f else page_done(coin)
        with self.lock:
            self.answered.append((coin, time.monotonic()))
        return Resp(*out)


class Sess(object):
    def __init__(self, venue):
        self.v, self.threads = venue, set()

    def get(self, url, params=None, timeout=None):
        self.threads.add(threading.get_ident())
        return self.v.serve(self, url, params)


def sessions_of(venue, made):
    def f():
        s = Sess(venue)
        made.append(s)
        return s
    return f


def settle(timeout=10.0):
    """Wait until every worker thread of earlier calls has ended."""
    end = time.monotonic() + timeout
    while threading.active_count() > BASE_THREADS and time.monotonic() < end:
        time.sleep(0.02)
    return threading.active_count() <= BASE_THREADS


def many(venue, coins, workers=3, deadline_s=30.0, clock=time.monotonic, deadline=None, trace=None, made=None,
         repair=()):
    jobs = [(c, (M0 - pd.Timedelta(minutes=2)) if c in repair else None, M0) for c in coins]
    made = [] if made is None else made
    dl = deadline if deadline is not None else clock() + deadline_s
    return M.minute_trades_many(jobs, workers, dl, clock=clock, sessions=sessions_of(venue, made), trace=trace)


def most_in_a_second(ts):
    ts = sorted(ts)
    return max((sum(1 for x in ts[i:] if x < t + 1.0 - 1e-9) for i, t in enumerate(ts)), default=0)


def pacing():
    settle()
    v, trace = Venue(), []

    def slow(coin):
        def f(params):
            time.sleep(0.05)
            return page_done(coin)
        return f
    coins = ["C%d" % i for i in range(40)]
    v.h = {c: slow(c) for c in coins}
    M.trades_peak(reset=True)
    t0 = time.monotonic()
    out = many(v, coins, workers=3, trace=trace)
    took = time.monotonic() - t0
    ts = sorted(c["t"] for c in v.calls)
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    sends = [x[2] for x in trace if x[0] == "send"]
    check("pacing: 3 workers, 40 requests: every job answered and verified, one request each",
          len(out) == 40 and all(o["status"] == "ok" and o["result"]["verified"] for o in out) and len(v.calls) == 40,
          str([o["status"] for o in out][:5]))
    check("pacing: no two sends closer than 1/7 s (2 ms allowed for timer noise at the fake venue)",
          min(gaps) >= GAP - 0.002, "smallest gap %.4f s" % min(gaps))
    check("pacing: never more than 7 sends in any one-second window (the sends as recorded under the lock, and at the "
          "fake venue with 2 ms per gap allowed)", most_in_a_second(sends) <= 7 and len(sends) == 40
          and max((sum(1 for x in ts[i:] if x < t + 1.0 - 0.014) for i, t in enumerate(ts))) <= 7,
          "%d in one second" % most_in_a_second(sends))
    check("pacing: the requests of 3 workers went out at the pace (40 in about 39/7 s, not slower)",
          39 * GAP - 0.01 <= took <= 39 * GAP + 1.0, "%.2f s" % took)
    pk = M.trades_peak(reset=True)
    check("pacing: trades_peak (monitoring) records the most sends in one second: 7", pk == 7, str(pk))

    # the sequential path: today's formula, unchanged, on a fake clock
    real_t, real_s = M.time, M._S
    now = [1000.0]

    class FT(object):
        time = staticmethod(lambda: now[0])
        sleep = staticmethod(lambda x: now.__setitem__(0, now[0] + x))
        monotonic = staticmethod(lambda: now[0])
    durs = [0.05, 0.3, 0.01, 0.0, 0.2, 0.14, 0.15, 0.02, 0.5, 0.0]
    got = []

    class S(object):
        headers = {}

        def get(self, url, params=None, timeout=None):
            got.append(now[0])
            now[0] += durs[len(got) - 1]
            return Resp(*page_done("C1"))
    try:
        M.time, M._S = FT, S()
        M._last_req[0] = 999.9
        for _ in durs:
            M._get_h(M.EXCHANGE + "/products/C1-USD/trades", {"limit": 1000})
    finally:
        M.time, M._S = real_t, real_s
    ref, last, t = [], 999.9, 1000.0                       # today's code, written out: wait, sleep, mark, send
    for d in durs:
        wait = last + 1.0 / M.TRADES_RATE - t
        if wait > 0:
            t = t + wait
        last = t
        ref.append(t)
        t += d
    check("pacing: the sequential path's send times are today's formula's, to the last bit", got == ref,
          str([round(x - 1000, 4) for x in got]))
    M._last_req[0] = M._last_sent[0] = 0.0


def stalled():
    settle()
    v = Venue()
    coins = ["C%d" % i for i in range(18)]
    seen = {}

    def block(params):
        end = time.monotonic() + 15
        while time.monotonic() < end:
            with v.lock:
                n = len([a for a in v.answered if a[0] != "C5"])
            if n >= 17:
                seen["others"] = n
                break
            time.sleep(0.01)
        return page_done("C5")
    v.h = {"C5": block}
    out = many(v, coins, workers=3)
    ok = [o["status"] for o in out] == ["ok"] * 18
    check("stalled: one request blocked until the 17 other jobs had their answers; all 18 jobs answered",
          ok and seen.get("others") == 17, str(seen))
    last_other = max(t for c, t in v.answered if c != "C5")
    c5 = [t for c, t in v.answered if c == "C5"][0]
    check("stalled: the other 17 finished while it was blocked", last_other <= c5)


def order():
    settle()
    v = Venue()
    coins = ["C%d" % i for i in range(6)]

    def wait(coin, s):
        def f(params):
            time.sleep(s)
            return page_done(coin)
        return f
    v.h = {c: wait(c, 0.9 - 0.18 * i) for i, c in enumerate(coins)}
    out = many(v, coins, workers=3)
    done = [c for c, _ in v.answered]
    check("order: completion order differs from the input order", done != coins, str(done))
    check("order: outcomes in the input order (each job's own bar)", [o["result"]["bar"]["close"] for o in out]
          == [px(c) for c in coins], str([o["result"]["bar"]["close"] for o in out]))


def stop(code, cls, name):
    settle()
    v, trace = Venue(), []
    release, blocked = threading.Event(), []

    def hold(coin, first):
        def f(params):
            with v.lock:
                blocked.append(coin)
            release.wait(10)
            return first(coin) if params.get("after") is None else page_done(coin)
        return f

    def refuse(params):
        end = time.monotonic() + 10
        while len(blocked) < 2 and time.monotonic() < end:       # C1 and C3 are in flight when the refusal comes
            time.sleep(0.005)
        return code, {"message": "no"}, {}
    v.h = {"C1": hold("C1", page_first), "C2": refuse, "C3": hold("C3", page_done)}
    coins = ["C%d" % i for i in range(6)]
    out = many(v, coins, workers=3, trace=trace, repair=("C1",))
    returned_blocked = len(blocked) == 2 and not release.is_set()
    n_at_stop = len(v.calls)
    release.set()
    settled = settle()
    st = [o["status"] for o in out]
    check(f"stop ({name}): the call returned at the stop, with two requests still in flight", returned_blocked)
    check(f"stop ({name}): the job finished before keeps its result; every other job reports the stop",
          st == ["ok", "stop", "stop", "stop", "stop", "stop"] and out[0]["result"]["verified"]
          and out[0]["result"]["bar"]["close"] == px("C0"), str(st))
    check(f"stop ({name}): the stop names the job that saw it and the error is {cls.__name__}",
          [o.get("cause") for o in out[1:]] == [False, True, False, False, False]
          and all(isinstance(o["error"], cls) for o in out[1:])
          and (cls is M.Limited or not isinstance(out[2]["error"], M.Limited)), str([o.get("error") for o in out]))
    check(f"stop ({name}): jobs not taken by then are not started", [o["started"] for o in out]
          == [True, True, True, True, False, False])
    stop_at = [i for i, x in enumerate(trace) if x[0] == "stop"]
    after = [x for x in trace[stop_at[0] + 1:] if x[0] == "send"] if stop_at else None
    check(f"stop ({name}): zero requests sent after the stop: none in the send record after it, and the venue saw "
          "4 requests in all (C0, C1's first page, C2, C3), no next page of C1 though its first page asked for one",
          settled and len(stop_at) == 1 and after == [] and len(v.calls) == 4 == n_at_stop
          and [c["coin"] for c in v.calls] == ["C0", "C1", "C2", "C3"] and all(c["after"] is None for c in v.calls),
          str([(c["coin"], c["after"]) for c in v.calls]))


def deadline():
    settle()
    # a controlled clock: the deadline passes while C1 is in flight (after at least one other job was answered)
    C, release = [0.0], threading.Event()
    v = Venue()
    v.stamp = lambda: C[0]

    def stall(params):
        end = time.monotonic() + 10
        while not [a for a in v.answered if a[0] != "C1"] and time.monotonic() < end:
            time.sleep(0.002)
        C[0] = 101.0                                      # the deadline (100) passes during this request
        release.wait(10)
        return page_first("C1")                            # it would need a next page
    v.h = {"C1": stall}
    coins = ["C%d" % i for i in range(8)]
    out = many(v, coins, workers=3, clock=lambda: C[0], deadline=100.0, repair=("C1",))
    asked = [c["coin"] for c in v.calls]
    st = [o["status"] for o in out]
    check("deadline: the jobs answered before it keep their results; the job in flight and every other one are budget",
          "C1" in asked and st[1] == "budget" and out[1]["started"] and len(asked) >= 2
          and all((o["status"] == "ok" and o["result"]["verified"]) == (c in asked and c != "C1")
                  for c, o in zip(coins, out)) and set(st) == {"ok", "budget"}, str(list(zip(asked, st))))
    check("deadline: no request started after the deadline; the jobs not started by then were not asked "
          "(a job taken whose send slot came after the deadline was not sent either)",
          all(c["clk"] <= 100.0 for c in v.calls) and len(asked) == len(set(asked))
          and sum(not o["started"] for o in out) >= 8 - 4 and all(c in asked for c, o in zip(coins, out)
                                                               if o["status"] == "ok"),
          str([(c, o["started"]) for c, o in zip(coins, out)]))
    # the next pass, while C1's worker is still blocked: undisturbed
    v2 = Venue()
    out2 = many(v2, ["D%d" % i for i in range(5)], workers=3)
    check("deadline: a worker still blocked does not disturb the next pass", [o["status"] for o in out2]
          == ["ok"] * 5 and len(v2.calls) == 5)
    release.set()
    settled = settle()
    check("deadline: the late answer is thrown away (the outcome stays budget) and no request starts after the deadline "
          "(no next page for C1, nothing else)", settled and out[1] == dict(status="budget", started=True)
          and [c["coin"] for c in v.calls] == asked and all(c["after"] is None for c in v.calls),
          str([(c["coin"], c["after"]) for c in v.calls]))

    # real time: the call returns by the deadline; nothing is sent after it
    rel2 = threading.Event()

    def long(params):
        rel2.wait(10)
        return page_done("C0")
    v3 = Venue({"C0": long})
    t0 = time.monotonic()
    dl = t0 + 0.5
    out3 = many(v3, ["C%d" % i for i in range(12)], workers=3, deadline=dl)
    back = time.monotonic()
    rel2.set()
    settle()
    check("deadline (real time): the call returns by the deadline (within 60 ms after it)", back - dl <= 0.06,
          "%.3f s after" % (back - dl))
    asked3 = set(c["coin"] for c in v3.calls)
    check("deadline (real time): no request started after the deadline (5 ms allowed between the check and the fake); "
          "the jobs asked by then answered, the rest and the stalled one are budget",
          all(c["mono"] <= dl + 0.005 for c in v3.calls) and out3[0]["status"] == "budget"
          and all((o["status"] == "ok") == (("C%d" % i) in asked3 and i > 0) for i, o in enumerate(out3))
          and len(asked3) < 12, str([o["status"] for o in out3]))


def error():
    settle()
    v = Venue()
    n = []

    def broken(params):
        n.append(1)
        raise requests.ConnectionError("connection reset")
    v.h = {"C2": broken}
    out = many(v, ["C%d" % i for i in range(5)], workers=3)
    check("error: a connection error after the retry is that job's outcome only (2 requests: the try and its retry)",
          [o["status"] for o in out] == ["ok", "ok", "error", "ok", "ok"]
          and isinstance(out[2]["error"], requests.ConnectionError) and len(n) == 2, str([o["status"] for o in out]))


def threads():
    settle()
    v, made = Venue(), []
    hold, inside = threading.Event(), []

    def wait(coin):
        def f(params):
            inside.append(coin)
            hold.wait(10)
            return page_done(coin)
        return f
    v.h = {c: wait(c) for c in ("C0", "C1", "C2")}
    daemon = {}

    def look():
        end = time.monotonic() + 10
        while len(inside) < 3 and time.monotonic() < end:
            time.sleep(0.01)
        daemon["all"] = all(t.daemon for t in threading.enumerate() if t is not threading.main_thread()
                            and t is not threading.current_thread())
        daemon["n"] = threading.active_count()
        hold.set()
    lk = threading.Thread(target=look, daemon=True)
    lk.start()
    out = many(v, ["C%d" % i for i in range(6)], workers=3, made=made)
    lk.join()
    settle()
    check("threads: one session per worker, each used by one thread only, three threads",
          len(made) == 3 and all(len(s.threads) == 1 for s in made)
          and len(set(t for s in made for t in s.threads)) == 3 and [o["status"] for o in out] == ["ok"] * 6,
          str([len(s.threads) for s in made]))
    check("threads: the workers are daemon threads", daemon.get("all") is True, str(daemon))
    # the default sessions: a small pool of idle sessions, never two threads on one at a time
    real = M._new_session
    built = []

    def fake_new():
        s = Sess(v2)
        built.append(s)
        return s
    v2 = Venue()
    hold2, inside2 = threading.Event(), []

    def wait2(coin):
        def f(params):
            inside2.append(coin)
            if len(inside2) >= 3:
                hold2.set()
            hold2.wait(10)
            return page_done(coin)
        return f
    v2.h = {c: wait2(c) for c in ("C0", "C1", "C2")}
    del M._free[:]
    try:
        M._new_session = fake_new
        jobs = [("C%d" % i, None, M0) for i in range(3)]
        M.minute_trades_many(jobs, 3, time.monotonic() + 10)
        settle()
        n1 = len(built)
        M.minute_trades_many(jobs, 3, time.monotonic() + 10)
        settle()
    finally:
        M._new_session = real
        del M._free[:]
    calls1 = v2.calls[:3]
    check("threads: default sessions: three distinct sessions while three requests were in flight together, "
          "reused by the next pass (no new session built)", n1 == 3 and len(built) == 3
          and len({c["sess"] for c in calls1}) == 3, str((n1, len(built))))
    # a worker blocked in a request does not hold up the process's normal exit
    code = ("import sys, time, threading; sys.path.insert(0, %r)\n"
            "from bot import market as M\n"
            "import pandas as pd\n"
            "class S(object):\n"
            "    def get(self, url, params=None, timeout=None):\n"
            "        time.sleep(60)\n"
            "out = M.minute_trades_many([('BTC', None, pd.Timestamp('2026-11-10 15:04'))], 2, time.monotonic() + 0.3,"
            " sessions=S)\n"
            "print(out[0]['status'], threading.active_count())\n" % ROOT)
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    took = time.monotonic() - t0
    check("threads: a worker blocked in a request does not hold up the process's exit (the call returns at its "
          "deadline as budget, the process ends at once)", r.returncode == 0 and r.stdout.split()[:1] == ["budget"]
          and took < 15, "%.1f s, %r %r" % (took, r.stdout.strip(), r.stderr[-200:]))


# ------------------------------------------------------------------------------------------------ part 2: the engine
MIN = pd.Timedelta(minutes=1)
COINS = ("ETH", "SOL", "XRP", "DOGE")
ORDER = ["BTC"] + list(COINS)
START = NB.T0 + 30 * MIN                                  # 12:30; the steps run to 13:04 (a heartbeat at 13:00)
STEPS = 34


def mk(k):
    """The minute rebuilt by step k (k = 1 .. STEPS): the one before the step's minute."""
    return START + (k - 1) * MIN


class ScriptMarket(NB.SynthMarket):
    """SynthMarket (final candles) with scripted trades answers on the engine's timer (NB.CLOCK). script: (coin,
    minute) -> "final" (default: a verified bar from the final candles), "empty" (verified, no trades), "unverified",
    "deadline" (unverified, reason deadline) or an Exception to raise. dur: (coin, minute) -> seconds one request
    takes on the engine's timer (default 0.125)."""

    def __init__(self, coins, script=None, dur=None, vw=1):
        NB.SynthMarket.__init__(self, coins, 100)
        self.script, self.dur, self.vw, self.asked, self.many_calls = dict(script or {}), dict(dur or {}), vw, [], []

    def _d(self, c, m):
        return self.dur.get((c, m), 0.125)

    def _answer(self, c, m0, m1):
        self.asked.append((c, m0, m1))
        v = self.script.get((c, m1), "final")
        if isinstance(v, Exception):
            raise v
        d = self.final[c]
        mins = [m1] if m0 is None else list(pd.date_range(m0, m1, freq="min"))
        bars = {x: (d.loc[x].to_dict() if x in d.index else None) for x in mins}
        if v == "empty":
            bars[m1] = None
        ver, why = {"unverified": (False, "stale_first_page"), "deadline": (False, "deadline")}.get(v, (True, None))
        if m0 is None:
            return dict(bar=bars[m1], verified=ver, reason=why, pages=1)
        return dict(bars=bars, verified=ver, reason=why, pages=1)

    def trades_bar(self, coin, m, deadline=None):
        try:
            return self._answer(coin, None, m)
        finally:
            NB.CLOCK[0] += self._d(coin, m)

    def trades_bars(self, coin, m0, m1, deadline=None):
        try:
            return self._answer(coin, m0, m1)
        finally:
            NB.CLOCK[0] += self._d(coin, m1)


class ManyMarket(ScriptMarket):
    """ScriptMarket with the many-method, without threads: a model of vw workers on the engine's timer. Jobs are
    taken in order by the first free worker; a job is started only if its start is not after the deadline and not
    after a stop; its result arrives at start + duration and counts only if that is not after the deadline (else
    budget) and before the stop; the stop is the first refusal (Refused, Limited) to arrive by the deadline. The timer
    ends at the stop, or at the last started job's end. With vw 1 this is exactly what the sequential loop sees, except
    that a result arriving after the deadline is budget (the sequential loop applies it)."""

    def trades_many(self, jobs, workers, deadline, clock):
        self.many_calls.append((len(jobs), workers))
        free = [clock()] * self.vw
        rec = []
        for c, m0, m1 in jobs:
            w = min(range(self.vw), key=lambda i: free[i])
            st = free[w]
            if st > deadline:
                rec.append(None)
                continue
            en = st + self._d(c, m1)
            free[w] = en
            try:
                rec.append((st, en, self._answer(c, m0, m1), None))
            except Exception as err:
                rec.append((st, en, None, err))
        stops = [(r[1], j) for j, r in enumerate(rec) if r and isinstance(r[3], BM_REFUSED) and r[1] <= deadline]
        ts, sj = min(stops) if stops else (None, None)
        out = []
        for j, r in enumerate(rec):
            if r is None or (ts is not None and j != sj and r[0] >= ts):
                out.append(dict(status="stop", started=False, error=rec[sj][3], cause=False) if ts is not None
                           else dict(status="budget", started=False))
                continue
            st, en, res, err = r
            if ts is not None and (j == sj or en >= ts):
                out.append(dict(status="stop", started=True, error=rec[sj][3], cause=j == sj))
            elif en > deadline:
                out.append(dict(status="budget", started=True))
            elif err is not None:
                out.append(dict(status="error", started=True, error=err))
            else:
                out.append(dict(status="ok", started=True, result=res))
        ends = [r[1] for j, r in enumerate(rec) if r is not None and (ts is None or j == sj or r[0] < ts)]
        NB.CLOCK[0] = ts if ts is not None else max(ends + [clock()])
        return out


BM_REFUSED = M.Refused


def script(stop=None):
    """The scripted minutes (step k rebuilds mk(k)); stop: an Exception for SOL (the middle coin) at step 20."""
    s, d = {}, {}
    s[("ETH", mk(3))] = "unverified"                       # ETH repaired at step 4
    s[("SOL", mk(5))] = "empty"
    s[("XRP", mk(7))] = RuntimeError("connection reset")    # XRP repaired at step 8
    for c in ("BTC", "ETH", "SOL"):                         # step 9: the budget; SOL's request crosses it
        d[(c, mk(9))] = 3.0
    s[("SOL", mk(9))] = "deadline"                         # XRP and DOGE not reached; three coins repaired at step 10
    s[("DOGE", mk(12))] = "unverified"
    s[("BTC", mk(12))] = "empty"
    s[("ETH", mk(15))] = ValueError("trades page after 5 holds ids at or above the cursor")
    s[("SOL", mk(15))] = "unverified"
    if stop is not None:
        s[("SOL", mk(20))] = stop                          # XRP and DOGE: the rest; repaired at step 21
    for c in ORDER:                                        # step 25: the budget again, BTC's request crossing it
        d[(c, mk(25))] = 2.5
    d[("BTC", mk(25))] = 9.0
    s[("BTC", mk(25))] = "deadline"
    s[("XRP", mk(28))] = "empty"
    return s, d


def run_engine(tw, scr, dur, vw=1, many=True, between=False, steps=STEPS, upto=None, **cfg):
    """The engine through `steps` steps on the scripted market; snapshots after start-up and each step."""
    NB.CLOCK[0] = 0.0
    if tw is not None:
        cfg["trades_workers"] = tw
    cfg.setdefault("trades_budget_s", 8.0)
    eng, sd = NB.synth_engine("trades", coins=COINS, **cfg)
    eng.market = (ManyMarket if many else ScriptMarket)(ORDER, scr, dur, vw)
    now = [START]
    eng.clock = lambda: now[0] + pd.Timedelta(seconds=6)
    eng.refresh_adv = lambda t: None
    eng.update_spot(START)                                  # start-up: backfill and the trades pass of START - 1
    eng.trades_pass(START - MIN)
    snaps = [snap(eng)]
    for k in range(1, steps + 1):
        t = START + k * MIN
        now[0] = t
        if upto is not None and k == upto:
            return eng, sd
        eng.step(t)
        if between:
            eng.candle_pass(t)                              # candles_at_s: the pass of the minute open after the step
        snaps.append(snap(eng))
    p = os.path.join(sd, "events.jsonl")
    ev = [json.loads(x) for x in open(p)] if os.path.exists(p) else []
    shutil.rmtree(sd)
    return eng, snaps, ev


def snap(eng):
    return dict(spot={c: df.copy() for c, df in eng.spot.items()}, prov=copy.deepcopy(eng._prov),
                counts=dict(eng.counts), fb=list(eng._fb), fb_stop=eng._fb_stop, tb_err=eng._tb_err,
                cmax=dict(eng._cmax))


def diff(a, b):
    """Where two snapshot lists differ: [(snapshot index, field, coin or None)]."""
    out = []
    for i, (x, y) in enumerate(zip(a, b)):
        for k in x:
            if k == "spot":
                for c in set(x[k]) | set(y[k]):
                    if c not in x[k] or c not in y[k] or not x[k][c].equals(y[k][c]):
                        out.append((i, k, c))
            elif x[k] != y[k]:
                out.append((i, k, None))
    if len(a) != len(b):
        out.append((None, "length", None))
    return out


def total(snaps, key):
    """A counter summed over the run (the counts reset at each heartbeat: take each step's increase)."""
    n, prev = 0, {}
    for s in snaps:
        c = s["counts"]
        n += c.get(key, 0) - (prev.get(key, 0) if all(c.get(k, 0) >= v for k, v in prev.items()) else 0)
        prev = c
    return n


def parity():
    for tag, stop_err, extra in (("no stop", None, {}),
                                 ("rate limit", M.Limited("HTTP 429 on trades"), {}),
                                 ("refusal", M.Refused("HTTP 403 on trades"), {})):
        scr, dur = script(stop_err)
        e1, s1, ev1 = run_engine(1, scr, dur, **extra)
        e3, s3, ev3 = run_engine(3, scr, dur, **extra)
        d = diff(s1, s3)
        check(f"parity ({tag}): trades_workers 1 and 3 give identical spot tables, provenance, counters, _fb, "
              f"_fb_stop, tb_err and _cmax after start-up and each of {STEPS} steps", not d and len(s1) == STEPS + 1,
              str(d[:5]))
        check(f"parity ({tag}): identical log events (heartbeats with counts and step_s included)",
              ev1 == ev3 and any(e["kind"] == "heartbeat" for e in ev1), str(len(ev1)))
        check(f"parity ({tag}): the many-method took every pass with 3 workers, never with 1",
              len(e3.market.many_calls) == STEPS + 1 and all(w == 3 for _, w in e3.market.many_calls)
              and not e1.market.many_calls)
        want = {"tb_rebuilt": 1, "tb_empty": 1, "tb_fb_unverified": 1, "tb_fb_budget": 1, "tb_fb_error": 1}
        if stop_err is not None:
            want["tb_fb_limited" if isinstance(stop_err, M.Limited) else "tb_fb_error"] = 3
        got = {k: total(s1, k) for k in want}
        check(f"parity ({tag}): the script holds repairs, empty minutes, unverified answers, budget fallbacks and "
              "errors" + (", and the stop" if stop_err is not None else ""),
              all(got[k] >= v for k, v in want.items()) and total(s1, "tb_fb_budget") == 8, str(got))
        if stop_err is not None:
            k20 = s1[20]
            check(f"parity ({tag}): the stop at SOL: BTC and ETH applied, SOL, XRP and DOGE counted as the rest, "
                  "_fb_stop set, in both", k20["fb_stop"] and s3[20]["fb_stop"] and k20["tb_err"].startswith("SOL: ")
                  and all(k20["prov"][c].get(mk(20), (None, False))[1] for c in ("BTC", "ETH"))
                  and not any(k20["prov"][c].get(mk(20), (None, False))[1] for c in ("SOL", "XRP", "DOGE")),
                  str(k20["counts"]))
        hb1 = [e["step_s"] for e in ev1 if e["kind"] == "heartbeat"]
        hb3 = [e["step_s"] for e in ev3 if e["kind"] == "heartbeat"]
        check(f"parity ({tag}): step_s has the trades entry [median, max] in both paths",
              hb1 and all("trades" in h and len(h["trades"]) == 2 for h in hb1 + hb3) and hb1 == hb3,
              str(hb3[-1:]))
    # the release's inputs: candle_after, candles_at_s and the candle pass between steps (on-demand candles)
    scr, dur = script(M.Limited("HTTP 429 on trades"))
    extra = dict(trades_rows="candle_after", candles_at_s=45)
    e1, s1, ev1 = run_engine(1, scr, dur, between=True, **extra)
    e3, s3, ev3 = run_engine(3, scr, dur, between=True, **extra)
    d = diff(s1, s3)
    check("parity (candle_after, candles_at_s 45, the candle pass between steps, a rate limit): identical tables, "
          "provenance, counters, fallbacks, events", not d and ev1 == ev3 and total(s1, "pre_ondemand") > 0,
          str(d[:5]) + " pre_ondemand %d" % total(s1, "pre_ondemand"))


def differences():
    """Each place where the two paths legitimately differ, shown on one minute (step 2: rebuilds mk(2))."""
    k = 2
    # 1. after a stop: whatever had arrived (workers) vs. the coins before the refused one (sequential)
    scr = {("SOL", mk(k)): M.Limited("HTTP 429 on trades")}
    dur = {("ETH", mk(k)): 2.0, ("SOL", mk(k)): 1.0}
    _, s1, _ = run_engine(1, scr, dur, steps=3)
    _, s3, _ = run_engine(3, scr, dur, vw=3, steps=3)
    built = [lambda s, c=c: s[k]["prov"][c].get(mk(k), (None, False))[1] for c in ORDER]
    b1 = [c for c, f in zip(ORDER, built) if f(s1)]
    b3 = [c for c, f in zip(ORDER, built) if f(s3)]
    check("difference, stop: sequential applies the coins before the refused one (BTC, ETH) and none after",
          b1 == ["BTC", "ETH"] and s1[k]["counts"].get("tb_fb_limited") == 3, str((b1, s1[k]["counts"])))
    check("difference, stop: workers apply whatever had arrived (BTC, XRP, DOGE: their requests ended before SOL's "
          "429; ETH's had not); ETH and SOL counted as the rest", b3 == ["BTC", "XRP", "DOGE"]
          and s3[k]["counts"].get("tb_fb_limited") == 2 and s3[k]["fb_stop"], str((b3, s3[k]["counts"])))
    check("difference, stop: the next minute repairs the coins not applied in either path; that minute is then "
          "trades-built for every coin in both", all(s[k + 1]["prov"][c].get(mk(k), (None, False))[1]
                                                     for s in (s1, s3) for c in ORDER))
    # 2. the budget: a coin the sequential path would not reach is reached by the workers
    dur = {("BTC", mk(k)): 5.0, ("ETH", mk(k)): 5.0}
    _, s1, _ = run_engine(1, {}, dur, steps=3)
    _, s3, _ = run_engine(3, {}, dur, vw=3, steps=3)
    b1 = [c for c, f in zip(ORDER, built) if f(s1)]
    b3 = [c for c, f in zip(ORDER, built) if f(s3)]
    check("difference, budget: sequential reaches BTC and ETH (ETH's answer arriving after the budget is still "
          "applied); SOL, XRP and DOGE fall back", b1 == ["BTC", "ETH"] and s1[k]["counts"].get("tb_fb_budget") == 3,
          str((b1, s1[k]["counts"])))
    check("difference, budget: 3 workers reach every coin within the budget",
          b3 == ORDER and not s3[k]["counts"].get("tb_fb_budget"), str((b3, s3[k]["counts"])))
    # 3. a result that arrives after the deadline: applied by the sequential loop, thrown away by the workers
    dur = {("BTC", mk(k)): 7.5, ("ETH", mk(k)): 1.0}
    _, s1, _ = run_engine(1, {}, dur, steps=3)
    _, s3, _ = run_engine(3, {}, dur, vw=1, steps=3)
    b1 = [c for c, f in zip(ORDER, built) if f(s1)]
    b3 = [c for c, f in zip(ORDER, built) if f(s3)]
    check("difference, late result: ETH's request starts before the deadline and ends after it: the sequential loop "
          "applies it, the workers path counts it as a budget fallback (with one worker, to show only this)",
          b1 == ["BTC", "ETH"] and b3 == ["BTC"] and s1[k]["counts"].get("tb_fb_budget") == 3
          and s3[k]["counts"].get("tb_fb_budget") == 4, str((b1, b3)))


def plan_upfront():
    """The plan worked out for every coin before any request equals what the sequential loop works out coin by coin."""
    scr, dur = script()
    for upto, drop in ((10, "XRP"), (16, None), (4, "BTC")):
        eng, sd = run_engine(1, scr, dur, upto=upto)
        t = START + upto * MIN
        if drop:
            eng._cmax.pop(drop, None)                       # a coin with no _cmax yet
        eng.update_spot(t)                                  # the step's candles, then the plan
        m = t - MIN
        up = [(c,) + eng._tb_plan(c, m) for c in ORDER]
        seen, real = [], eng._tb_plan

        def rec(c, mm):
            r = real(c, mm)
            seen.append((c,) + r)
            return r
        eng._tb_plan = rec
        eng.trades_pass(m)
        shutil.rmtree(sd)
        opened = sum(len(x[2]) for x in up)
        check(f"plan up front (step {upto}{', ' + drop + ' without _cmax' if drop else ''}): equals the sequential "
              f"loop's, coin by coin ({opened} open minutes, {sum(x[1] is not None for x in up)} _cmax defaults)",
              seen == up and len(seen) == len(ORDER) and (opened > 0 or upto == 16)
              and (drop is None or [x for x in up if x[0] == drop][0][1] is not None), str(up))


def validation():
    for v in (0, -1, 1.5, "3", 7, True):
        sd = tempfile.mkdtemp(prefix="tw_cfg_")
        try:
            E.Engine(mode="paper", cfg=dict(NB.CFG, newest_bar="trades", trades_workers=v), state_dir=sd,
                     broker=E.PaperBroker(0.5), clock=lambda: NB.T0, echo=False)
            msg = None
        except ValueError as err:
            msg = str(err)
        finally:
            shutil.rmtree(sd)
        check(f"validation: trades_workers {v!r} refuses to start, with a clear message", msg is not None
              and "trades_workers must be a whole number from 1 to 6" in msg and repr(v) in msg, str(msg))
    scr, dur = script()
    ref = None
    for tw in (1, None, 6, 2):
        eng, s, ev = run_engine(tw, scr, dur, steps=12)
        if tw == 1:
            ref = s
        if tw in (1, None):
            check(f"validation: trades_workers {tw!r}: the sequential path (the many-method is never called)",
                  not eng.market.many_calls and eng.trades_workers == 1 and not diff(s, ref))
        else:
            check(f"validation: trades_workers {tw}: accepted, the many-method takes the pass", eng.trades_workers == tw
                  and len(eng.market.many_calls) == 13 and not diff(s, ref))
    eng, s, ev = run_engine(3, scr, dur, many=False, steps=12)
    check("validation: trades_workers 3 with a market that lacks the many-method: the sequential path, same result",
          eng.trades_workers == 3 and not hasattr(eng.market, "trades_many") and not diff(s, ref)
          and len(eng.market.asked) > 0)


def ignored():
    def warnings(sd):
        return [e for e in map(json.loads, open(os.path.join(sd, "events.jsonl"))) if e.get("kind") == "warning"]
    for nb in ("candles", None):
        for v in (3, "x", 7):
            sd = tempfile.mkdtemp(prefix="tw_ign_")
            cfg = dict(NB.CFG, trades_workers=v)
            if nb is not None:
                cfg["newest_bar"] = nb
            eng = E.Engine(mode="paper", cfg=cfg, state_dir=sd, market=None, broker=E.PaperBroker(0.5),
                           clock=lambda: START, echo=False)
            eng.coins = list(COINS)
            eng.market = ManyMarket(ORDER)
            eng.refresh_adv = lambda t: None
            eng.start()
            w = warnings(sd)
            check(f"ignored (newest_bar {nb!r}, trades_workers {v!r}): the engine starts, one warning event in plain "
                  "words", eng.trades_workers == 1 and len(w) == 1 and w[0]["msg"].startswith(
                      'trades_workers is set but newest_bar is not "trades": the setting is ignored'), str(w))
            if v == 3:
                now = [START]
                eng.clock = lambda: now[0] + pd.Timedelta(seconds=6)
                for t in pd.date_range(START + MIN, START + 30 * MIN, freq="min"):
                    now[0] = t
                    eng.step(t)
                hb = [e for e in map(json.loads, open(os.path.join(sd, "events.jsonl"))) if e["kind"] == "heartbeat"]
                check(f"ignored (newest_bar {nb!r}): no trades asked, and step_s has no trades entry in candle mode",
                      not eng.market.many_calls and not eng.market.asked and hb
                      and set(hb[-1]["step_s"]) == {"data", "cancel", "place"}, str(hb[-1:]))
            shutil.rmtree(sd)


def config_tw():
    a = json.load(open(os.path.join(HERE, "config.json")))
    b = json.load(open(os.path.join(HERE, "config.tw.json")))
    check("config.tw.json: config.json with trades_workers 3 added, no other key different",
          [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k) or (k in a) != (k in b)] == ["trades_workers"]
          and "trades_workers" not in a and b["trades_workers"] == 3)
    sd = tempfile.mkdtemp(prefix="tw_cfg_")
    try:
        eng = E.Engine(mode="paper", cfg=b, state_dir=sd, broker=E.PaperBroker(0.5), clock=lambda: NB.T0, echo=False)
        check("config.tw.json: the engine starts with it, 3 workers, in trades mode", eng.trades_workers == 3
              and eng.newest_bar == "trades" and hasattr(eng.market, "trades_many"))
    finally:
        shutil.rmtree(sd)


def main():
    t0 = time.time()
    config_tw()
    pacing()
    stalled()
    order()
    stop(429, M.Limited, "rate limit")
    stop(403, M.Refused, "refusal")
    deadline()
    error()
    threads()
    E.WINDOW_MIN = 30                                       # short window for the synthetic tables; restored below
    try:
        parity()
        differences()
        plan_upfront()
        validation()
        ignored()
    finally:
        E.WINDOW_MIN = 11 * 1440
    print("%.0f s" % (time.time() - t0))
    print("TRADES WORKERS TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
