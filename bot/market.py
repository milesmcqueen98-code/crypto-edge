"""Public Coinbase market data (no keys): spot 1-minute candles (Coinbase Exchange, the research source)
and Coinbase US futures candles / order books (Advanced Trade public endpoints)."""
import collections
import threading
import time
from email.utils import parsedate_to_datetime

import numpy as np
import pandas as pd
import requests

EXCHANGE = "https://api.exchange.coinbase.com"
ADV = "https://api.coinbase.com/api/v3/brokerage/market"
_S = requests.Session()
_S.headers["User-Agent"] = "crypto-edge-bot/1.0"


def _get(url, params=None, tries=5):
    return _get_full(url, params, tries)[0]


def _get_full(url, params=None, tries=5, timeout=15):
    """_get's request, retries and timeout, returning (json, headers). (None, None) where _get returned None (every
    try answered 429). tries and timeout: the defaults are _get's; the engine's candle pass asks for one short try."""
    for a in range(tries):
        try:
            r = _S.get(url, params=params, timeout=timeout)
            if r.status_code == 429:
                time.sleep(1 + a)
                continue
            r.raise_for_status()
            return r.json(), r.headers
        except requests.RequestException:
            if a == tries - 1:
                raise
            time.sleep(0.5 + a)
    return None, None


class Refused(RuntimeError):
    """The venue refused a request (401, 403, 451 or a page that is not JSON). Never worked around."""


class Limited(Refused):
    """The venue answered 429 (rate limit) on the trades path. Not retried: the trades pass stops for that minute."""


TRADES_RATE = 7.0               # trades requests per second at most (the research fetcher's pace; public limit 10)
_last_req = [0.0]               # the last trades send (sequential path) or the last reserved send slot (workers)
_last_sent = [0.0]              # the last trades send, both paths (workers: the send gap is checked against it)
_pace_lock = threading.Lock()   # guards _last_req, _last_sent and the ring below (both paths, every thread)
_sends = collections.deque(maxlen=32)   # monitoring only: time of the last trades sends
_peak = [0]                     # monitoring only: most trades sends in any one second since the last reset


def _note_send(t):
    """Monitoring only (called under _pace_lock): remember a send time and the most sends in one second."""
    _sends.append(t)
    n = sum(1 for x in _sends if x > t - 1.0)
    if n > _peak[0]:
        _peak[0] = n


def trades_peak(reset=False):
    """Most trades requests sent in any one second (both paths) since the last reset. Monitoring only."""
    with _pace_lock:
        out = _peak[0]
        if reset:
            _peak[0] = 0
            _sends.clear()
        return out


def _get_h(url, params=None, tries=2, session=None, gate=None):
    """Like _get, but returns (json, headers) and gives up sooner (the trades pass runs on a time budget).
    Paced to TRADES_RATE requests per second. A refusal raises Refused at once; a 429 raises Limited at once.
    gate (minute_trades_many's workers only): called before every send, the retry too; it paces the send across
    workers and raises _Halt instead when the pass has stopped or its deadline has passed. session: the worker's own.
    Without gate: today's pacing and the module session, under the lock (so the shared pacing state stays whole)."""
    for a in range(tries):
        if gate is None:
            with _pace_lock:
                wait = _last_req[0] + 1.0 / TRADES_RATE - time.time()
                if wait > 0:
                    time.sleep(wait)
                _last_req[0] = time.time()
                _last_sent[0] = _last_req[0]
                _note_send(_last_req[0])
            s = _S
        else:
            gate()
            s = session
        try:
            r = s.get(url, params=params, timeout=3)
            if r.status_code in (401, 403, 451):
                raise Refused(f"HTTP {r.status_code} on {url}: {r.text[:200]!r}")
            if r.status_code == 429:
                raise Limited(f"HTTP 429 on {url}")
            r.raise_for_status()
            try:
                return r.json(), r.headers
            except ValueError:
                raise Refused(f"non-JSON reply on {url}: {r.text[:200]!r}")
        except requests.RequestException:
            if a == tries - 1:
                raise
            time.sleep(0.3)


def _http_time(s):
    try:
        return pd.Timestamp(parsedate_to_datetime(s)).tz_convert(None)
    except (TypeError, ValueError, IndexError):
        return None


def generated_at(headers):
    """When the venue (or its cache) generated this answer: the Date header minus the Age header (Age absent = 0).
    None when there is no readable Date."""
    d = _http_time((headers or {}).get("Date"))
    if d is None:
        return None
    try:
        age = float((headers or {}).get("Age") or 0)
    except ValueError:
        return None
    return d - pd.Timedelta(seconds=age)


def _page(js):
    """Rows of one trades page as (time, trade_id, price, size); bad is the number of rows that could not be read."""
    out, bad = [], 0
    for r in js:
        try:
            t = pd.Timestamp(r["time"])
            t = t.tz_convert(None) if t.tzinfo is not None else t
            tid, px, sz = int(r["trade_id"]), float(r["price"]), float(r["size"])
            if not (np.isfinite(px) and np.isfinite(sz) and px > 0 and sz >= 0):
                raise ValueError
            out.append((t, tid, px, sz))
        except (KeyError, TypeError, ValueError):
            bad += 1
    return out, bad


def trades_to_bar(rows, m):
    """Bar of the minute [m, m + 60 s) from trade rows (time, trade_id, price, size), in trade order (time, then
    trade_id); duplicates by trade_id are dropped. None when no trade falls in the minute."""
    m = pd.Timestamp(m)
    e = m + pd.Timedelta(minutes=1)
    seen, sel = set(), []
    for t, tid, px, sz in rows:
        if m <= t < e and tid not in seen:
            seen.add(tid)
            sel.append((t, tid, px, sz))
    if not sel:
        return None
    sel.sort(key=lambda x: (x[0], x[1]))
    px = [x[2] for x in sel]
    return dict(open=px[0], high=max(px), low=min(px), close=px[-1], volume=float(sum(x[3] for x in sel)))


def minute_trades_bar(coin, m, max_pages=20, deadline=None, get=None, clock=time.monotonic):
    """The trades of one coin for the minute [m, m + 60 s), reduced to a bar, with proof of completeness: the
    one-minute form of minute_trades_bars. Returns dict(bar (None = no trades in the minute), verified, reason (None
    when verified), pages, gen (first page's generation time), newest (newest trade time seen), n (trades in the
    minute))."""
    m = pd.Timestamp(m)
    r = minute_trades_bars(coin, m, m, max_pages=max_pages, deadline=deadline, get=get, clock=clock)
    return dict(bar=r["bars"][m], verified=r["verified"], reason=r["reason"], pages=r["pages"], gen=r["gen"],
                newest=r["newest"], n=r["n"][m])


def minute_trades_bars(coin, m0, m1, max_pages=20, deadline=None, get=None, clock=time.monotonic):
    """The trades of one coin for the minutes m0 .. m1 (inclusive), from Coinbase Exchange's public trades list (newest
    first, 1000 a page, paged back with the CB-AFTER cursor), reduced to one bar per minute, with proof of completeness.

    verified is True only if both hold:
      (i) paging reached a trade stamped before m0, or the venue's list ended (an empty page);
      (ii) the first page was generated at or after m1 + 60 s (Date minus Age), or it holds a trade stamped at or
           after m1 + 60 s.
    Also unverified: the page cap, the deadline (a time.monotonic value), or any row that could not be read.
    Returns dict(bars {minute: bar or None}, verified, reason, pages, gen, newest, n {minute: trades}).
    `get` is _get_h (tests pass a fake)."""
    get = get or _get_h
    m0, m1 = pd.Timestamp(m0), pd.Timestamp(m1)
    e = m1 + pd.Timedelta(minutes=1)
    rows, pages, bad, gen, newest, reason = [], 0, 0, None, None, None
    reached = ended = first_late = False
    params, cur = {"limit": 1000}, None
    while True:
        if pages >= max_pages:
            reason = "page_cap"
            break
        if deadline is not None and pages and clock() > deadline:
            reason = "deadline"
            break
        js, hd = get(f"{EXCHANGE}/products/{coin}-USD/trades", params)
        hd = hd or {}
        pages += 1
        if pages == 1:
            gen = generated_at(hd)
        if not js:
            ended = True                                   # the venue's list ended: nothing older
            break
        if not isinstance(js, list):
            raise ValueError(f"trades page is not a list: {str(js)[:200]}")
        pg, b = _page(js)
        bad += b
        if not pg:
            reason = "malformed"
            break
        if cur is not None and max(x[1] for x in pg) >= cur:
            raise ValueError(f"trades page after {cur} holds ids at or above the cursor")
        rows += pg
        top = max(x[0] for x in pg)
        newest = top if newest is None else max(newest, top)
        if pages == 1:
            first_late = top >= e                          # a trade after the newest minute: the page saw its end
        if min(x[0] for x in pg) < m0:
            reached = True
            break
        nxt = hd.get("CB-AFTER") or hd.get("cb-after")
        try:
            cur = int(nxt) if nxt not in (None, "") else min(x[1] for x in pg)
        except ValueError:
            cur = min(x[1] for x in pg)
        params = {"limit": 1000, "after": cur}
    fresh = (gen is not None and gen >= e) or first_late
    if reason is None and bad:
        reason = "malformed"
    if reason is None and not (reached or ended):
        reason = "incomplete"
    if reason is None and not fresh:
        reason = "stale_first_page"
    mins = list(pd.date_range(m0, m1, freq="min"))
    bars = {mm: trades_to_bar(rows, mm) for mm in mins}
    n = {mm: len({r[1] for r in rows if mm <= r[0] < mm + pd.Timedelta(minutes=1)}) for mm in mins}
    return dict(bars=bars, verified=reason is None, reason=reason, pages=pages, gen=gen, newest=newest, n=n)


# ------------------------------------------------------------------------------------------------ trades, side by side
class _Halt(Exception):
    """A worker's request was not sent: the pass stopped (a refusal or a rate limit) or its deadline passed."""


_free = []                       # idle worker sessions (each used by one thread at a time; kept for keep-alive)
_free_lock = threading.Lock()


def _new_session():
    s = requests.Session()
    s.headers["User-Agent"] = _S.headers.get("User-Agent", "crypto-edge-bot/1.0") if hasattr(_S, "headers") \
        else "crypto-edge-bot/1.0"
    return s


def _take_session():
    with _free_lock:
        if _free:
            return _free.pop()
    return _new_session()


def _give_session(s):
    with _free_lock:
        if len(_free) < 8:
            _free.append(s)


class _Pass(object):
    """The shared state of one minute_trades_many call. Every field is read and written under lock."""

    def __init__(self, n):
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.next, self.alive, self.done = 0, 0, 0
        self.out, self.started = [None] * n, [False] * n
        self.stopped, self.stop_err, self.stop_job, self.closed = False, None, None, False


def _gate(st, j, deadline, clock, trace):
    """Before each send of a worker (the retry too). Reserves the next send slot (at least 1 / TRADES_RATE after the
    one before, all workers and the sequential path together) under the pacing lock and sleeps to it outside the lock.
    Then, under the pass's lock, it either refuses (_Halt: the pass stopped, closed or is past its deadline) or records
    the send; the send time also keeps 1 / TRADES_RATE from the last actual send (a late wake-up of the worker before
    cannot bring two sends closer). The send and the stop are both recorded under the pass's lock, so no send can
    be recorded after the stop."""
    with _pace_lock:
        now = time.time()
        slot = max(now, _last_req[0] + 1.0 / TRADES_RATE)
        _last_req[0] = slot
    if slot > now:
        time.sleep(slot - now)
    while True:
        with st.lock:
            if st.stopped or st.closed or clock() > deadline:
                raise _Halt()
            with _pace_lock:
                t = time.time()
                gap = _last_sent[0] + 1.0 / TRADES_RATE - t
                if gap <= 0:
                    _last_sent[0] = t
                    _note_send(t)
                    if trace is not None:
                        trace.append(("send", j, t))
                    return
        time.sleep(gap)


def _work(st, jobs, deadline, clock, max_pages, sessions, trace):
    """One worker: takes the next job not yet started until none is left, the pass stops or closes, or the deadline
    has passed (a job is never started after the deadline). Touches nothing but the pass's state and its own session."""
    sess = sessions() if sessions is not None else _take_session()
    try:
        while True:
            with st.lock:
                if st.closed or st.stopped or st.next >= len(jobs) or clock() > deadline:
                    return
                j = st.next
                st.next += 1
                st.started[j] = True
            coin, m0, m1 = jobs[j]

            def get(url, params, j=j):
                return _get_h(url, params, session=sess, gate=lambda: _gate(st, j, deadline, clock, trace))
            kind, res = None, None
            try:
                if m0 is None:
                    res = minute_trades_bar(coin, m1, max_pages=max_pages, deadline=deadline, get=get, clock=clock)
                else:
                    res = minute_trades_bars(coin, m0, m1, max_pages=max_pages, deadline=deadline, get=get,
                                             clock=clock)
                kind = "ok"
            except _Halt:
                kind = None                                # not finished: the stop or the deadline decides
            except Refused as err:                         # a refusal or a rate limit: stop every worker
                kind, res = "stop", err
            except Exception as err:                       # this job's own error (after its retry)
                kind, res = "error", err
            with st.lock:
                late = st.closed or clock() > deadline     # arrived after the deadline: thrown away
                if not late and not st.stopped:
                    if kind == "stop":
                        st.stopped, st.stop_err, st.stop_job = True, res, j
                        if trace is not None:
                            trace.append(("stop", j, time.time()))
                    elif kind is not None:
                        st.out[j] = (kind, res)
                        st.done += 1
                st.cond.notify_all()
    finally:
        if sessions is None:
            _give_session(sess)
        with st.lock:
            st.alive -= 1
            st.cond.notify_all()


def minute_trades_many(jobs, workers, deadline, clock=time.monotonic, max_pages=20, sessions=None, trace=None):
    """The trades of several coins side by side: the engine's trades pass with trades_workers 2 or more.

    jobs: a list of (coin, m0, m1). m0 None: minute_trades_bar(coin, m1); else minute_trades_bars(coin, m0, m1) (the
    repair range), each with this deadline and clock, as the sequential pass asks them.
    workers: threads (daemon threads, started for this call; each with its own requests.Session, taken from a small
    pool of idle sessions so connections are reused across minutes, never used by two threads at once).
    deadline: a value of clock(); no job starts and no request is sent after it, and this call returns at the latest
    when clock() passes it (waiting in real time, a few tens of ms at a time).
    Pacing: all trades requests of all workers (and of the sequential path) together at most TRADES_RATE a second.
    A refusal or a rate limit (Refused, Limited) seen by any worker stops the pass: from then on no worker sends a
    request (not even the next page of a job in the middle of paging), and results that arrive later are thrown away.

    Returns one outcome per job, in the input order: dict(status, started, result or error).
      "ok": result (the minute_trades_bar(s) dict, verified or not); "error": error (that job's exception);
      "stop": error (the refusal or rate limit that stopped the pass; cause True for the job that saw it): the job had
        no result when the pass stopped;
      "budget": the job was not started by the deadline, or its result had not arrived by then (a late result is
        thrown away).
    started: the job was taken by a worker before the deadline and the stop. Workers still finishing a request after
    the return hold no state of the caller and send nothing more. sessions (tests): a callable making a session per
    worker; trace (tests): a list that receives ("send", job, time) and ("stop", job, time) in order."""
    n = len(jobs)
    if not n:
        return []
    st = _Pass(n)
    k = max(1, min(int(workers), n))
    st.alive = k
    for _ in range(k):
        threading.Thread(target=_work, args=(st, jobs, deadline, clock, max_pages, sessions, trace),
                         daemon=True).start()
    with st.lock:
        while not st.stopped and st.done < n and st.alive > 0:
            left = deadline - clock()
            if left < 0:
                break
            st.cond.wait(min(max(left, 0.001), 0.05))
        st.closed = True
        out = []
        for j in range(n):
            if st.out[j] is not None:
                kind, res = st.out[j]
                out.append(dict(status=kind, started=True, **({"result": res} if kind == "ok" else {"error": res})))
            elif st.stopped:
                out.append(dict(status="stop", started=st.started[j], error=st.stop_err, cause=j == st.stop_job))
            else:
                out.append(dict(status="budget", started=st.started[j]))
        return out


def spot_candles(coin, start, end, meta=None, tries=5, timeout=15, need_answer=False):
    """1-minute candles [start, end) as a DataFrame indexed by minute (UTC, naive). If a dict is passed as meta, it is
    filled with the cache facts of the last answer (the newest minutes): gen (Date minus Age), age, cache, date, and
    start (rows at or after it came from that answer). tries and timeout go to each request (_get_full); the defaults
    are today's. need_answer: a request that got no answer at all (every try answered 429) raises RuntimeError; an
    answer that is an empty list is an answer (an empty table, as without it)."""
    rows = {}
    s = pd.Timestamp(start).floor("min")
    end = pd.Timestamp(end).floor("min")
    while s < end:
        e = min(end, s + pd.Timedelta(minutes=300))
        js, hd = _get_full(f"{EXCHANGE}/products/{coin}-USD/candles",
                           {"granularity": 60, "start": s.isoformat() + "Z", "end": (e - pd.Timedelta(minutes=1)).isoformat() + "Z"},
                           tries=tries, timeout=timeout)
        if need_answer and js is None:
            raise RuntimeError(f"candles {coin}: no answer (every try answered 429)")
        if meta is not None:
            try:                                           # monitoring only: never raises into the data path
                meta.clear()
                hd = hd or {}
                meta.update(gen=generated_at(hd), age=hd.get("Age"), cache=hd.get("cf-cache-status"),
                            date=hd.get("Date"), start=s)  # rows at or after start came from this answer
            except Exception:
                try:
                    meta.clear()
                except Exception:
                    pass
        for t, lo, hi, op, cl, vo in js or []:
            rows[t] = (op, hi, lo, cl, vo)
        s = e
        time.sleep(0.12)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    k = sorted(rows)
    df = pd.DataFrame([rows[i] for i in k], columns=["open", "high", "low", "close", "volume"], dtype=float)
    df.index = pd.to_datetime(k, unit="s")
    return df[(df.index >= pd.Timestamp(start)) & (df.index < end)]


def futures_candles(product_id, start, end):
    rows = {}
    s = int(pd.Timestamp(start).timestamp())
    e = int(pd.Timestamp(end).timestamp())
    while s < e:
        hi = min(e, s + 300 * 60)
        js = _get(f"{ADV}/products/{product_id}/candles", {"start": s, "end": hi, "granularity": "ONE_MINUTE", "limit": 350})
        for c in js.get("candles", []):
            rows[int(c["start"])] = (float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c["volume"]))
        s = hi
        time.sleep(0.12)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    k = sorted(rows)
    df = pd.DataFrame([rows[i] for i in k], columns=["open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(k, unit="s")
    return df[(df.index >= pd.Timestamp(start)) & (df.index < pd.Timestamp(end))]


def book(product_id, limit=50):
    """Bids and asks as lists of (price, size in contracts), best first."""
    js = _get(f"{ADV}/product_book", {"product_id": product_id, "limit": limit})
    pb = js.get("pricebook", {})
    return ([(float(b["price"]), float(b["size"])) for b in pb.get("bids", [])],
            [(float(a["price"]), float(a["size"])) for a in pb.get("asks", [])])


def book_top(product_id):
    js = _get(f"{ADV}/product_book", {"product_id": product_id, "limit": 5})
    pb = js.get("pricebook", {})
    bids, asks = pb.get("bids", []), pb.get("asks", [])
    if not bids or not asks:
        return np.nan, np.nan
    return float(bids[0]["price"]), float(asks[0]["price"])
