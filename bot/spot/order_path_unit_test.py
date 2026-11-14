#!/usr/bin/env python3
"""Unit tests of the batch order path (bot/spot/README.md, "Order path"), against scripted fakes of the venue's library.
No network, no real sleep: every wait goes through the broker's injectable sleep on a fake clock.

Part 1, LiveBroker's new methods, one check per case:
  - cancel_many: the batch cancel raises; it answers for some orders only; it reports failure reasons (one of them
    ORDER_IS_FULLY_FILLED); the read misses an order (read singly); the order stays open until the patience ends (not
    confirmed, seven reads at 0 .. 2.0 s); CANCEL_QUEUED then CANCELLED; a fill before the cancel (returned once);
    groups of 50;
  - snapshot: the same dict as status(); a cursor followed while has_next (at most 5 pages); groups of 50; never raises;
  - best_bids: a coin missing from the answer, an empty book, an unreadable price; never raises;
  - place_many: the same answers as place() (success, venue error, a raise with the order found under its client
    order id, a raise with no order); a 429 counted; three threads, each on its own client from a thread-safe
    factory, results in request order;
  - the breaker: three failed calls in a row switch a piece off once, a success in between resets the count;
  - the pace: no two sends closer than 1 / rate, on one thread and on several;
  - rate-limit headers: the last ones seen are kept (library names and raw header names);
  - fills() without snap makes exactly today's requests; with snap it reads only the orders the snapshot lacks;
  - a broker built with the defaults has today's attributes and no client factory.
Part 2, the engine's batch path (Engine._allocate_batch, _settle) on a small live engine over the same scripted venue
(two coins, stub models, hand-made levels):
  - new bids: one best-bid request, one place_many, arm events; an unchanged bid is kept with no request;
  - a fill before the cancel of a re-priced bid: booked once (and not again by the next settle), no new bid for that
    coin, the ladder open;
  - an unconfirmed cancel: the order kept with today's warning, no new bid, the cancel retried next minute;
  - a duration error on every bid of one place_many: the lifetime doubled once with one warning, every bid sent again
    singly at the new lifetime and placed;
  - best_bids failing three minutes in a row: one warning event and batch_fallback, then today's single request;
  - cancel_many raising: one warning, today's single cancel for each order, the same outcome;
  - _settle reads every resting order with one request (fills from the snapshot; a missed order read singly);
  - the setting: "serial" and absent never touch the batch methods; a paper engine ignores "batch"; any other value
    is refused at start; the heartbeat gets rate_limit only once headers were seen.

Usage: python bot/spot/order_path_unit_test.py
"""
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot.spot import engine as E  # noqa: E402

FAILS = []


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""), flush=True)
    if not ok:
        FAILS.append(name)


class Clock:
    """Fake clock: sleep advances it (single-threaded tests)."""

    def __init__(self, t=1000.0):
        self.t, self.sleeps = t, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class Resp:
    def __init__(self, code, headers=None):
        self.status_code, self.headers = code, headers or {}


class HTTPError(Exception):
    """As the library raises it: the response attached."""

    def __init__(self, msg, response=None):
        super().__init__(msg)
        self.response = response


class Venue:
    """A scripted venue shared by the clients: orders, best bids, and per-method scripts."""

    def __init__(self, clock=None, cost=0.0):
        self.orders, self.bids, self.calls = {}, {}, []
        self.cost = cost           # seconds each request takes on the fake clock
        self.reads = {}            # order id -> statuses returned at successive reads (the last one sticks)
        self.script = {}           # method -> list of callables(kw) used once each, in order; then the default
        self.page = 1000           # list_orders page size
        self.clock = clock
        self.lock = threading.Lock()
        self.n = 0

    def add(self, oid, status="OPEN", filled=0.0, avg=0.0, fees=0.0, product="ETH-USD", cid=None, side="BUY"):
        self.orders[oid] = dict(order_id=oid, product_id=product, side=side, status=status, filled_size=repr(filled),
                                average_filled_price=repr(avg), total_fees=repr(fees), client_order_id=cid or "x",
                                last_fill_time=None)

    def view(self, oid):
        o = dict(self.orders[oid])
        seq = self.reads.get(oid)
        if seq:
            o["status"] = seq.pop(0) if len(seq) > 1 else seq[0]
        return o


class Client:
    """Implements the library methods LiveBroker calls; records (client name, method, kwargs, clock)."""

    def __init__(self, venue, name="main"):
        self.v, self.name = venue, name

    def _rec(self, m, kw):
        with self.v.lock:
            self.v.calls.append((self.name, m, kw, self.v.clock.now() if self.v.clock else None,
                                 threading.get_ident()))
            s = self.v.script.get(m)
            if self.v.cost and self.v.clock:
                self.v.clock.t += self.v.cost
            return s.pop(0) if s else None

    def get_order(self, order_id):
        f = self._rec("get_order", dict(order_id=order_id))
        if f:
            return f(dict(order_id=order_id))
        if order_id not in self.v.orders:
            raise HTTPError("404 Client Error: NOT_FOUND", Resp(404))
        return {"order": self.v.view(order_id)}

    def list_orders(self, **kw):
        f = self._rec("list_orders", kw)
        if f:
            return f(kw)
        if kw.get("order_ids") is not None:
            sel = [i for i in kw["order_ids"] if i in self.v.orders]
        elif kw.get("product_ids") is not None:
            sel = [i for i, o in self.v.orders.items() if o["product_id"] in kw["product_ids"]]
        else:
            sel = [i for i, o in self.v.orders.items() if o["status"] in (kw.get("order_status") or [o["status"]])]
        i0 = int(kw.get("cursor") or 0)
        page = sel[i0:i0 + self.v.page]
        more = i0 + self.v.page < len(sel)
        return {"orders": [self.v.view(i) for i in page], "has_next": more,
                "cursor": str(i0 + self.v.page) if more else "", "sequence": 0}

    def cancel_orders(self, order_ids):
        f = self._rec("cancel_orders", dict(order_ids=list(order_ids)))
        if f:
            return f(dict(order_ids=list(order_ids)))
        res = []
        for i in order_ids:
            o = self.v.orders.get(i)
            if o is None:
                res.append(dict(success=False, failure_reason="UNKNOWN_CANCEL_ORDER", order_id=i))
            elif o["status"] == "FILLED":
                res.append(dict(success=False, failure_reason="ORDER_IS_FULLY_FILLED", order_id=i))
            else:
                if o["status"] == "OPEN":
                    o["status"] = "CANCELLED"
                res.append(dict(success=True, failure_reason="UNKNOWN_CANCEL_FAILURE_REASON", order_id=i))
        return {"results": res}

    def get_best_bid_ask(self, product_ids=None):
        f = self._rec("get_best_bid_ask", dict(product_ids=list(product_ids or [])))
        if f:
            return f(dict(product_ids=product_ids))
        return {"pricebooks": [dict(product_id=p, bids=[dict(price=repr(self.v.bids[p]), size="1")] if self.v.bids[p]
                                    else [], asks=[]) for p in product_ids if p in self.v.bids]}

    def _new(self, kw, m):
        f = self._rec(m, kw)
        if f:
            return f(kw)
        g = (kw.get("order_configuration") or {}).get("limit_limit_gtd")
        if g and getattr(self.v, "min_end", None) is not None and \
                E.pd.Timestamp(g["end_time"].rstrip("Z")) < self.v.min_end:
            return {"success": False, "error_response": {"error": "INVALID_END_TIME",
                                                         "preview_failure_reason": "DURATION_TOO_SMALL"}}
        with self.v.lock:
            self.v.n += 1
            oid = f"o{self.v.n}"
        self.v.add(oid, product=kw["product_id"], cid=kw["client_order_id"], side=kw.get("side", "BUY"))
        return {"success": True, "success_response": {"order_id": oid}}

    def create_order(self, **kw):
        return self._new(kw, "create_order")

    def get_accounts(self, **kw):
        self._rec("get_accounts", kw)
        return {"accounts": [dict(currency="USD", available_balance=dict(value="1000000"), hold=dict(value="0"))]}

    def get_transaction_summary(self, **kw):
        self._rec("get_transaction_summary", kw)
        return {"fee_tier": {"pricing_tier": "test", "maker_fee_rate": "0.0006", "taker_fee_rate": "0.00125"}}

    def get_fills(self, **kw):
        f = self._rec("get_fills", kw)
        if f:
            return f(kw)
        return {"fills": [dict(order_id=i) for i in getattr(self.v, "filled_ids", [])], "cursor": ""}

    def preview_order(self, **kw):
        f = self._rec("preview_order", kw)
        if f:
            return f(kw)
        return {"errs": []}

    def limit_order_gtc_buy(self, **kw):
        return self._new(dict(kw, side="BUY"), "limit_order_gtc_buy")

    def limit_order_gtc_sell(self, **kw):
        return self._new(dict(kw, side="SELL"), "limit_order_gtc_sell")


def broker(venue, clock, **kw):
    b = E.LiveBroker(client=Client(venue), **kw)
    b.sleep, b.mono = clock.sleep, clock.now
    return b


def order(oid, px=100.0, size=1.0, filled=0.0, value=0.0, fees=0.0):
    return dict(id=oid, px=px, size=size, filled=filled, value=value, fees=fees, side="BUY")


def raises(msg):
    def f(kw):
        raise RuntimeError(msg)
    return f


def methods(v, name=None):
    return [c[1] for c in v.calls if name is None or c[0] == name]


SP = E.Spec("ETH-USD", 0.01, 1e-8, 1.0)


# ------------------------------------------------------------------------------------------------ part 1
class NoSleep:
    """time.sleep replaced while today's cancel() runs (it waits 0.4 s between its reads)."""

    def __init__(self, ck):
        self.ck = ck

    def __enter__(self):
        self.old, E.time.sleep = E.time.sleep, self.ck.sleep

    def __exit__(self, *a):
        E.time.sleep = self.old


def t_cancel_many():
    # the batch cancel raises: today's cancel for each order at once, its answers used (here the venue did cancel)
    ck = Clock()
    v = Venue(ck)
    v.add("a")
    v.add("b")
    v.script["cancel_orders"] = [lambda kw: (v.orders["a"].update(status="CANCELLED"),
                                             v.orders["b"].update(status="CANCELLED"), raises("timeout")(kw))[2]]
    b = broker(v, ck)
    with NoSleep(ck):
        r = b.cancel_many([order("a"), order("b")])
    check("cancel_many: the batch cancel raises -> today's cancel for each order at once (cancel of one id, then "
          "its read), its answers used; no read schedule", r == {"a": (None, True), "b": (None, True)}
          and methods(v) == ["cancel_orders", "cancel_orders", "get_order", "cancel_orders", "get_order"]
          and b.last_cancel_rounds == {"a": "single", "b": "single"}, str((r, methods(v))))
    b2 = broker(Venue(ck), ck)
    b2.c.v.add("c")
    b2.c.v.script["cancel_orders"] = [raises("timeout")]
    b2.c.v.reads["c"] = ["OPEN"]
    with NoSleep(ck):
        r2 = b2.cancel_many([order("c")])
    check("cancel_many: the batch cancel raises and the order stays open -> today's cancel: six reads, not "
          "confirmed, no list read", r2 == {"c": (None, False)} and methods(b2.c.v).count("get_order") == 6
          and "list_orders" not in methods(b2.c.v), str(r2))
    v3 = Venue(ck)
    v3.add("d")
    v3.script["cancel_orders"] = [lambda kw: {"oops": 1}]
    with NoSleep(ck):
        r3 = broker(v3, ck).cancel_many([order("d")])
    check("cancel_many: an answer without a results list -> today's cancel for its orders, confirmed",
          r3 == {"d": (None, True)} and methods(v3) == ["cancel_orders", "cancel_orders", "get_order"], str(r3))

    # the second of two groups raises: the first group by the read schedule, the second by today's cancel
    ck = Clock()
    v = Venue(ck)
    ids = [f"g{k}" for k in range(60)]
    for i in ids:
        v.add(i)
    v.script["cancel_orders"] = [None, raises("503")]
    with NoSleep(ck):
        r = broker(v, ck).cancel_many([order(i) for i in ids])
    k = [(c[1], len(c[2].get("order_ids") or [c[2].get("order_id")])) for c in v.calls]
    want = [("cancel_orders", 50), ("cancel_orders", 10)] + [("cancel_orders", 1), ("get_order", 1)] * 10 + \
        [("list_orders", 50)]
    check("cancel_many: the batch request raises for the second of two groups -> that group by today's cancel at "
          "once, in order, then the first group by the reads; all confirmed",
          k == want and all(x == (None, True) for x in r.values()), str(k[:4]))

    # the list keeps showing OPEN while the single read says CANCELLED: confirmed at the 0.6 s round
    ck = Clock()
    v = Venue(ck)
    v.add("a", status="CANCELLED")
    v.add("b", status="CANCELLED")
    v.script["cancel_orders"] = [lambda kw: {"results": [dict(success=True, order_id=i) for i in kw["order_ids"]]}]
    v.script["list_orders"] = [lambda kw: {"orders": [dict(v.view(i), status="OPEN") for i in kw["order_ids"]]}] * 7
    b = broker(v, ck)
    r = b.cancel_many([order("a"), order("b")])
    check("cancel_many: the list stays OPEN, the single read says CANCELLED -> confirmed at the 0.6 s round by "
          "single reads", r == {"a": (None, True), "b": (None, True)}
          and methods(v) == ["cancel_orders"] + ["list_orders"] * 4 + ["get_order"] * 2
          and b.last_cancel_rounds == {"a": 3, "b": 3}, str((r, methods(v))))
    v = Venue(ck)
    v.add("a")
    v.reads["a"] = ["OPEN"]
    v.script["cancel_orders"] = [lambda kw: {"results": [dict(success=True, order_id="a")]}]
    v.script["get_order"] = [raises("503")] * 4
    r = broker(v, ck).cancel_many([order("a")])
    check("cancel_many: the single read raises from 0.6 s on -> the snapshot's view stands (open): not confirmed, "
          "a single read tried at each of the last four rounds", r == {"a": (None, False)}
          and methods(v).count("get_order") == 4 and methods(v).count("list_orders") == 7, str(methods(v)))

    # the answer covers some orders only
    ck = Clock()
    v = Venue(ck)
    for i in "abc":
        v.add(i)
    v.script["cancel_orders"] = [lambda kw: (v.orders["a"].update(status="CANCELLED"),
                                             v.orders["c"].update(status="CANCELLED"),
                                             {"results": [dict(success=True, order_id="a")]})[2]]
    r = broker(v, ck).cancel_many([order("a"), order("b"), order("c")])
    check("cancel_many: an answer for some orders only -> each order as its read shows (b still open: not confirmed)",
          r == {"a": (None, True), "b": (None, False), "c": (None, True)}, str(r))

    # failure reasons, ORDER_IS_FULLY_FILLED among them: the fill is returned, confirmed
    ck = Clock()
    v = Venue(ck)
    v.add("f", status="FILLED", filled=1.0, avg=99.5, fees=0.06)
    v.add("g")
    o = order("f", px=100.0)
    r = broker(v, ck).cancel_many([o, order("g")])
    ans = [c for c in v.calls if c[1] == "cancel_orders"]
    check("cancel_many: a failure reason ORDER_IS_FULLY_FILLED -> the fill returned once, confirmed",
          r["f"][1] is True and r["f"][0] is not None and abs(r["f"][0][0] - 1.0) < 1e-12
          and abs(r["f"][0][1] - 99.5) < 1e-9 and abs(r["f"][0][2] - 0.06) < 1e-12 and r["g"] == (None, True)
          and len(ans) == 1, str(r))
    check("cancel_many: the fill computed with increment() exactly as cancel() would",
          r["f"][0] == E.LiveBroker.increment(o, E.LiveBroker._sd(v.orders["f"])))

    # the read misses an order: read singly with status()
    ck = Clock()
    v = Venue(ck)
    v.add("a")
    v.add("b")
    v.script["list_orders"] = [lambda kw: {"orders": [v.view("a")], "has_next": False}]
    b = broker(v, ck)
    r = b.cancel_many([order("a"), order("b")])
    check("cancel_many: the read misses an order -> that order read singly (get_order), confirmed",
          r == {"a": (None, True), "b": (None, True)} and methods(v) == ["cancel_orders", "list_orders", "get_order"]
          and b.take_counts().get("snap_miss") == 1, str(methods(v)))
    # ... and the single read raises: unknown this round, read again next round
    ck = Clock()
    v = Venue(ck)
    v.add("a")
    v.script["list_orders"] = [lambda kw: {"orders": [], "has_next": False}]
    v.script["get_order"] = [raises("503")]
    r = broker(v, ck).cancel_many([order("a")])
    check("cancel_many: the single read raises -> unknown that round, confirmed at the next read",
          r == {"a": (None, True)} and methods(v) == ["cancel_orders", "list_orders", "get_order", "list_orders"],
          str(methods(v)))

    # still open until the patience ends: seven reads at 0, 0.15, 0.3, 0.6, 1.0, 1.5, 2.0 s after the cancel returned
    # (each request takes 0.1 s on the fake clock, as in the request model; recorded times are when each was sent)
    ck = Clock()
    v = Venue(ck, cost=0.1)
    v.add("a", filled=0.25, avg=100.0, fees=0.015)
    v.reads["a"] = ["OPEN"]
    v.script["cancel_orders"] = [lambda kw: {"results": [dict(success=True, order_id="a")]}]
    r = broker(v, ck).cancel_many([order("a")])
    t0 = v.calls[0][3] + 0.1                       # the cancel returned
    at = [round(c[3] - t0, 6) for c in v.calls if c[1] == "list_orders"]
    check("cancel_many: open until the patience ends -> not confirmed, the partial fill returned, reads at "
          "0, 0.15, 0.3, 0.6, 1.0, 1.5, 2.0 s", r["a"][1] is False and r["a"][0] is not None
          and abs(r["a"][0][0] - 0.25) < 1e-12 and at == [0.0, 0.15, 0.3, 0.6, 1.0, 1.5, 2.0], str((r, at)))

    # CANCEL_QUEUED then CANCELLED
    ck = Clock()
    v = Venue(ck)
    v.add("a")
    v.reads["a"] = ["CANCEL_QUEUED", "CANCEL_QUEUED", "CANCELLED"]
    v.script["cancel_orders"] = [lambda kw: {"results": [dict(success=True, order_id="a")]}]
    r = broker(v, ck).cancel_many([order("a")])
    check("cancel_many: CANCEL_QUEUED, CANCEL_QUEUED, CANCELLED -> confirmed at the third read",
          r == {"a": (None, True)} and methods(v).count("list_orders") == 3, str(r))

    # a fill before the cancel: returned once (the engine books it once and gives the coin no new bid: part 2)
    ck = Clock()
    v = Venue(ck)
    v.add("a", status="OPEN", filled=0.4, avg=100.0, fees=0.024)
    v.script["cancel_orders"] = [lambda kw: (v.orders["a"].update(status="CANCELLED"),
                                             {"results": [dict(success=True, order_id="a")]})[1]]
    o = order("a")
    r = broker(v, ck).cancel_many([o])
    check("cancel_many: a part fill before the cancel -> returned with the confirmation",
          r["a"][1] is True and r["a"][0] is not None and abs(r["a"][0][0] - 0.4) < 1e-12, str(r))

    # groups of 50
    ck = Clock()
    v = Venue(ck)
    ids = [f"i{k}" for k in range(120)]
    for i in ids:
        v.add(i)
    r = broker(v, ck).cancel_many([order(i) for i in ids])
    cn = [len(c[2]["order_ids"]) for c in v.calls if c[1] == "cancel_orders"]
    ln = [len(c[2]["order_ids"]) for c in v.calls if c[1] == "list_orders"]
    check("cancel_many: 120 orders -> batch cancels of 50, 50, 20 and reads of 50, 50, 20; all confirmed",
          cn == [50, 50, 20] and ln == [50, 50, 20] and all(x == (None, True) for x in r.values()), str((cn, ln)))


def t_snapshot():
    ck = Clock()
    v = Venue(ck)
    v.add("a", status="OPEN", filled=0.5, avg=101.25, fees=0.03)
    v.orders["a"]["last_fill_time"] = "2025-10-10T20:01:02Z"
    b = broker(v, ck)
    s = b.snapshot(["a"])
    check("snapshot: the dict status() returns for the same order", s == {"a": b.status("a")}, str(s))

    v.page = 2
    for k in range(9):
        v.add(f"p{k}")
    s = b.snapshot([f"p{k}" for k in range(9)])
    pages = [c for c in v.calls if c[1] == "list_orders"][1:]
    check("snapshot: a cursor followed while has_next (9 orders in pages of 2: 5 pages, all 9 read)",
          len(pages) == 5 and len(s) == 9, f"pages {len(pages)}, got {len(s)}")
    v2 = Venue(ck)
    v2.page = 2
    for k in range(12):
        v2.add(f"p{k}")
    b2 = broker(v2, ck)
    s2 = b2.snapshot([f"p{k}" for k in range(12)])
    curs = [c[2].get("cursor") for c in v2.calls if c[1] == "list_orders"]
    check("snapshot: at most 5 pages per group (12 orders in pages of 2: 10 read, 2 absent and counted as snap_miss)",
          len(curs) == 5 and curs[0] is None and curs[1:] == ["2", "4", "6", "8"] and len(s2) == 10
          and b2.take_counts().get("snap_miss") == 2, str((curs, len(s2))))

    ck = Clock()
    v = Venue(ck)
    ids = [f"i{k}" for k in range(75)]
    for i in ids:
        v.add(i)
    b = broker(v, ck)
    s = b.snapshot(ids)
    check("snapshot: groups of 50 (75 ids: 50 + 25)", [len(c[2]["order_ids"]) for c in v.calls] == [50, 25]
          and len(s) == 75)
    v.calls = []
    v.script["list_orders"] = [lambda kw: {"orders": [v.view(i) for i in kw["order_ids"]], "has_next": False},
                               raises("503")]
    s = b.snapshot(ids)
    check("snapshot: an exception in the second group -> what it has so far (50), never raises", len(s) == 50)
    v.script["list_orders"] = [lambda kw: {"orders": [dict(v.view("i0"), filled_size="bad")] + [v.view("i1")]}]
    s = b.snapshot(["i0", "i1"])
    check("snapshot: an order with an unreadable field is absent, the others kept", list(s) == ["i1"], str(s))
    v.script["list_orders"] = [lambda kw: {"orders": [v.view("i0"), v.view("i5")]}]
    s = b.snapshot(["i0"])
    check("snapshot: an order the bot did not ask for is not taken", list(s) == ["i0"], str(s))


def t_best_bids():
    ck = Clock()
    v = Venue(ck)
    v.bids = {"ETH-USD": 2500.5, "SOL-USD": 0}
    b = broker(v, ck)
    r = b.best_bids(["ETH-USD", "SOL-USD", "XRP-USD"])
    check("best_bids: one request; a coin missing from the answer and an empty book are absent (bbo_miss 2)",
          r == {"ETH-USD": 2500.5} and methods(v) == ["get_best_bid_ask"] and b.take_counts() == {"bbo_miss": 2},
          str(r))
    v.script["get_best_bid_ask"] = [lambda kw: {"pricebooks": [dict(product_id="ETH-USD", bids=[dict(price="x")]),
                                                                  dict(product_id="SOL-USD",
                                                                       bids=[dict(price="24.5")])]}]
    r = b.best_bids(["ETH-USD", "SOL-USD"])
    check("best_bids: an unreadable price is absent, the rest kept", r == {"SOL-USD": 24.5}, str(r))
    v.script["get_best_bid_ask"] = [raises("timeout")]
    check("best_bids: an exception -> empty, never raises", b.best_bids(["ETH-USD"]) == {})


def t_place_many():
    ck = Clock()
    end = E.pd.Timestamp("2025-10-10 20:10:06")
    # success, venue error, raise + found by client id, raise + not found: place_many equals place() each time
    cases = [
        ("success", [], {}),
        ("venue error", [lambda kw: {"success": False, "error_response": {"error": "INSUFFICIENT_FUND"}}], {}),
        ("raises, placed under its client order id", "found", {}),
        ("raises, nothing placed", [raises("read timed out")], {}),
    ]
    for label, scr, _ in cases:
        out = []
        for how in ("place", "place_many"):
            v = Venue(ck)
            if scr == "found":
                def f(kw, v=v):
                    v.add("late", cid=kw["client_order_id"])
                    raise RuntimeError("read timed out")
                v.script["create_order"] = [f]
            else:
                v.script["create_order"] = list(scr)
            b = broker(v, ck)
            old = E.time.sleep                     # place() waits with time.sleep: no real wait in a test
            E.time.sleep = ck.sleep
            try:
                r = b.place(SP, "BUY", 2500.0, 0.01, end_time=end) if how == "place" else \
                    b.place_many([(SP, "BUY", 2500.0, 0.01, True, end)])[0]
            finally:
                E.time.sleep = old
            out.append((r if r[0] is None or r[0] == "late" else ("<new>", r[1]), methods(v)))
        check(f"place_many = place(): {label}", out[0] == out[1], str(out))
    ck = Clock()
    v = Venue(ck)
    v.script["create_order"] = [raises("x")]
    v.script["list_orders"] = [lambda kw: {"orders": []}]
    b = broker(v, ck)
    r = b.place_many([(SP, "BUY", 2500.0, 0.01, True, end)])[0]
    check("place_many: the client-id search waits 0.5 s between its two tries through the injectable sleep (after "
          "the pace's 0.1 s before the first try; none before the second)",
          r[0] is None and methods(v) == ["create_order", "list_orders", "list_orders"]
          and [round(x, 9) for x in ck.sleeps] == [0.1, 0.5], str(ck.sleeps))

    # a 429 on a placement: counted; treated as any failed request (search by client id, then the error)
    v = Venue(ck)

    def r429(kw):
        raise HTTPError("429 Client Error: Too Many Requests", Resp(429, {"x-ratelimit-limit": "30",
                                                                          "x-ratelimit-remaining": "0",
                                                                          "x-ratelimit-reset": "1"}))
    v.script["create_order"] = [r429]
    b = broker(v, ck)
    r = b.place_many([(SP, "BUY", 2500.0, 0.01, True, end)])[0]
    check("place_many: a 429 -> http_429 counted, the order searched by client id, the error returned",
          r[0] is None and "429" in r[1] and b.take_counts() == {"http_429": 1}
          and methods(v) == ["create_order", "list_orders", "list_orders"]
          and b.rate_limit() == {"limit": "30", "remaining": "0", "reset": "1"}, str((r, b.rate_limit())))

    # three threads, each on its own client from a thread-safe factory; results in request order
    v = Venue(None)
    made, lock = [], threading.Lock()

    def factory():
        with lock:
            c = Client(v, name=f"w{len(made)}")
            made.append(c)
        return c
    gate = threading.Barrier(3, timeout=10)        # the first three requests meet: three threads at once
    b = E.LiveBroker(client=Client(v), client_factory=factory, place_workers=3)
    b.sleep = lambda s: None
    reqs = [(E.Spec(f"C{k}-USD", 0.01, 1e-8, 1.0), "BUY", 10.0 + k, 1.0, True, end) for k in range(9)]
    orig = Client._new

    def new(self, kw, m):
        if kw["product_id"] in ("C0-USD", "C1-USD", "C2-USD"):
            gate.wait()
        return orig(self, kw, m)
    Client._new = new
    try:
        r = b.place_many(reqs)
    finally:
        Client._new = orig
    byname = {}
    for name, m, kw, _, tid in v.calls:
        byname.setdefault(name, set()).add(tid)
    prod = {v.orders[oid]["product_id"]: oid for oid in v.orders}
    check("place_many: three threads (the first three requests in flight together), three clients from the factory, "
          "the main client unused", len(made) == 3 and "main" not in byname and len(byname) == 3, str(byname.keys()))
    check("place_many: each thread used only its own client (one thread per client)",
          all(len(t) == 1 for t in byname.values()) and len(set().union(*byname.values())) == 3)
    check("place_many: results in request order", [x[0] for x in r] == [prod[f"C{k}-USD"] for k in range(9)]
          and all(x[1] is None for x in r), str(r))
    r2 = b.place_many(reqs[:4])
    check("place_many: the same three clients on the next call (no new client)", len(made) == 3 and len(r2) == 4)


def t_place_never_loses():
    end = E.pd.Timestamp("2025-10-10 20:10:06")
    v = Venue(None)
    made, lock = [], threading.Lock()

    def factory():
        with lock:
            c = Client(v, name=f"w{len(made)}")
            made.append(c)
        return c
    b = E.LiveBroker(client=Client(v), client_factory=factory, place_workers=3)
    b.sleep = lambda s: None
    reqs = [(E.Spec(f"C{k}-USD", 0.01, 1e-8, 1.0), "BUY", 10.0 + k, 1.0, True, end) for k in range(3)]
    orig = Client._new

    def new(self, kw, m):                              # C1: the venue says success but gives no order id
        if kw["product_id"] == "C1-USD":
            self._rec(m, kw)
            return {"success": True, "success_response": {}}
        return orig(self, kw, m)
    Client._new = new
    try:
        r = b.place_many(reqs)
    finally:
        Client._new = orig
    srch = [c for c in v.calls if c[1] == "list_orders"]
    check("place_many: a success answer without an id while two others succeed -> the two recorded, the third "
          "searched by client order id and reported", r[0][0] and r[2][0] and r[0][1] is None and r[2][1] is None
          and r[1][0] is None and r[1][1].startswith("unreadable answer: ") and len(srch) == 2
          and all(c[2]["product_ids"] == ["C1-USD"] for c in srch), str(r))

    def new2(self, kw, m):                             # ... and the order did rest: found under its client id
        if kw["product_id"] == "C1-USD":
            orig(self, kw, m)
            return "not a dict"
        return orig(self, kw, m)
    Client._new = new2
    try:
        r = b.place_many(reqs)
    finally:
        Client._new = orig
    check("place_many: an answer that is not a dict, the order placed -> found under its client order id",
          r[1][0] is not None and r[1][1] is None and all(x[0] for x in r), str(r))
    real = b._place_thread

    def boom(q):
        if q[0].product == "C2-USD":
            raise RuntimeError("worker broke outside _place_on")
        return real(q)
    b._place_thread = boom
    r = b.place_many(reqs)
    check("place_many: a worker that raises outside _place_on -> that request's (None, error), the others placed, "
          "no raise", r[0][0] and r[1][0] and r[2][0] is None and "worker broke" in r[2][1], str(r))
    b1 = E.LiveBroker(client=Client(Venue(None)))
    b1.sleep = lambda s: None
    b1._place_on = lambda c, *q: (_ for _ in ()).throw(RuntimeError("loop broke"))
    r = b1.place_many(reqs)
    check("place_many, one worker: an exception becomes each request's (None, error), no raise",
          len(r) == 3 and all(x[0] is None and "loop broke" in x[1] for x in r), str(r))


def t_breaker():
    ck = Clock()
    v = Venue(ck)
    v.bids = {"ETH-USD": 1.0}
    b = broker(v, ck)
    v.script["get_best_bid_ask"] = [raises("x"), raises("x"), lambda kw: {"pricebooks": []}, raises("x")]
    b.best_bids(["ETH-USD"])
    b.best_bids(["ETH-USD"])
    check("breaker: two failures -> still on", b.batch_on("best_bids") and b.take_trips() == [])
    b.best_bids(["ETH-USD"])
    check("breaker: a third failure in a row (an answer with nothing usable) -> off, reported once",
          not b.batch_on("best_bids") and b.take_trips() == ["best_bids"] and b.take_trips() == [])
    n = len(v.calls)
    check("breaker: off -> no request, empty answer", b.best_bids(["ETH-USD"]) == {} and len(v.calls) == n)
    check("breaker: the other pieces stay on", b.batch_on("snapshot") and b.batch_on("cancel_many"))
    v.add("a")
    v.script["list_orders"] = [raises("x"), raises("x"), None, raises("x"), raises("x")]
    for _ in range(5):
        b.snapshot(["a"])
    check("breaker: a success in between resets the count (fail, fail, ok, fail, fail -> on)", b.batch_on("snapshot"))
    v.script["cancel_orders"] = [raises("x"), None, lambda kw: {"oops": 1}, None, raises("x"), None]
    with NoSleep(ck):
        for _ in range(3):
            b.cancel_many([order("a")])
    check("breaker: cancel_many's batch request -> off after three failures; cancel_many then raises (the engine "
          "falls back to today's cancel)", not b.batch_on("cancel_many") and b.take_trips() == ["cancel_many"])
    try:
        b.cancel_many([order("a")])
        ok = False
    except RuntimeError:
        ok = True
    check("breaker: cancel_many switched off raises", ok)


def t_pace():
    ck = Clock()
    v = Venue(ck)
    for i in range(5):
        v.add(f"a{i}")
    b = broker(v, ck)
    for i in range(5):
        b.snapshot([f"a{i}"])
    ts = [c[3] for c in v.calls]
    check("pace, one thread: sends 0.1 s apart at 10 a second", all(abs((y - x) - 0.1) < 1e-9
                                                                     for x, y in zip(ts, ts[1:])), str(ts))
    ck2 = Clock()
    b2 = broker(Venue(ck2), ck2, orders_rate=4)
    ats = [b2._pace() for _ in range(3)]
    check("pace: orders_rate 4 -> 0.25 s apart", all(abs((y - x) - 0.25) < 1e-9 for x, y in zip(ats, ats[1:])))

    class Still:                                   # the clock stands still; sleeps only recorded: slots must spread
        t = 50.0

        def now(self):
            return self.t
    st = Still()
    b3 = E.LiveBroker(client=Client(Venue(None)))
    b3.mono, b3.sleep = st.now, lambda s: None
    got, lock = [], threading.Lock()

    def run():
        for _ in range(20):
            a = b3._pace()
            with lock:
                got.append(a)
    th = [threading.Thread(target=run) for _ in range(4)]
    for x in th:
        x.start()
    for x in th:
        x.join()
    got.sort()
    check("pace, four threads x 20 sends: no two slots closer than 1 / rate",
          len(got) == 80 and all((y - x) >= 0.1 - 1e-9 for x, y in zip(got, got[1:])))


def t_headers():
    ck = Clock()
    v = Venue(ck)
    v.add("a")
    b = broker(v, ck)
    check("rate limit: none seen -> None", b.snapshot(["a"]) and b.rate_limit() is None)
    v.script["list_orders"] = [lambda kw: {"orders": [v.view("a")], "rate_limit_limit": "30",
                                           "rate_limit_remaining": "29", "rate_limit_reset": "0.5"}]
    b.snapshot(["a"])
    check("rate limit: the library's names (to_dict of an answer) kept",
          b.rate_limit() == {"limit": "30", "remaining": "29", "reset": "0.5"}, str(b.rate_limit()))
    v.script["get_best_bid_ask"] = [lambda kw: {"pricebooks": [], "x-ratelimit-limit": "30",
                                                "x-ratelimit-remaining": "12", "x-ratelimit-reset": "0.2"}]
    b.best_bids(["ETH-USD"])
    check("rate limit: raw header names kept too; the last seen wins", b.rate_limit()["remaining"] == "12")


def t_fills():
    ck = Clock()
    v = Venue(ck)
    v.add("a", filled=0.5, avg=100.0)
    v.add("b")
    v.add("c", status="FILLED", filled=1.0, avg=100.0)
    b = broker(v, ck)
    orders = [("x", order("a")), ("y", order("b")), ("z", order("c"))]
    r0 = b.fills("ETH", orders, None, None, 0.01)
    calls0 = [(c[1], c[2]) for c in v.calls]
    check("fills() without snap: today's requests (one get_order per order, in order)",
          calls0 == [("get_order", {"order_id": i}) for i in "abc"], str(calls0))
    v.calls = []
    snap = {"a": b.status("a"), "c": b.status("c")}
    v.calls = []
    r1 = b.fills("ETH", orders, None, None, 0.01, snap=snap)
    check("fills(snap): reads only the order the snapshot lacks, same result",
          [(c[1], c[2]) for c in v.calls] == [("get_order", {"order_id": "b"})] and r0 == r1, str(r1))
    v.calls = []
    r2 = b.fills("ETH", orders, None, None, 0.01, snap={})
    check("fills(snap={}): every order read singly, as today", r2 == r0 and len(v.calls) == 3)


def t_defaults():
    b = E.LiveBroker(client=Client(Venue(None)))
    check("defaults: serial, 10 a second, one worker, no client factory, no batch state yet",
          b.order_path == "serial" and b.orders_rate == 10.0 and b.place_workers == 1 and b.client_factory is None
          and getattr(b, "_batch_state", None) is None)
    bad = []
    for kw in (dict(order_path="fast"), dict(orders_rate=0), dict(place_workers=0), dict(place_workers=3)):
        try:
            E.LiveBroker(client=Client(Venue(None)), **kw)
            bad.append(kw)
        except ValueError:
            pass
    check("defaults: a bad order_path, rate or worker count (or threads without a factory) is refused", not bad,
          str(bad))
    n = E.LiveBroker.__new__(E.LiveBroker)          # as the sandbox test builds it: class defaults only
    n.c = Client(Venue(None))
    check("defaults: a broker built without __init__ has the class defaults and works (snapshot of nothing)",
          n.order_path == "serial" and n.snapshot([]) == {} and n.place_workers == 1)


def part1():
    t_cancel_many()
    t_snapshot()
    t_best_bids()
    t_place_many()
    t_place_never_loses()
    t_breaker()
    t_pace()
    t_headers()
    t_fills()
    t_defaults()


# ------------------------------------------------------------------------------------------------ part 2
import json  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from edge import wick  # noqa: E402

T0 = pd.Timestamp("2025-10-10 20:00")


class StubModel:
    def __init__(self, pred):
        self.pred = pred

    def predict(self, x):
        return np.array([self.pred])


class StubMarket:
    """The market object of a live engine: specs, the public best bid (counted), the book depth."""

    def __init__(self, bids):
        self.bids, self.calls = bids, []

    def spec(self, c):
        return E.Spec(f"{c}-USD", 0.01, 1e-8, 1.0)

    def best_bid(self, product):
        self.calls.append(("best_bid", product))
        return self.bids.get(product, np.nan)

    def bids_ahead(self, product, px):
        self.calls.append(("bids_ahead", product))
        return 0.0, True


class Mini:
    """A live engine on the batch path over the scripted venue; levels set by hand each minute."""

    def __init__(self, path="batch", mode="live", bids=None):
        self.ck = Clock()
        self.v = Venue(self.ck)
        self.v.bids = dict(bids or {"ETH-USD": 101.0, "SOL-USD": 21.0})
        self.mkt = StubMarket(self.v.bids)
        self.t = T0
        self.sd = tempfile.mkdtemp(prefix="order_path_unit_")
        cfg = dict(capital=250000.0, bid_ttl_s=300, adv_frac=None, usd_reserve=0.0, log_book=True)
        if path is not None:
            cfg["order_path"] = path
        self.b = E.LiveBroker(client=Client(self.v), order_path="batch")
        self.b.sleep, self.b.mono = self.ck.sleep, self.ck.now
        try:
            self.e = E.Engine(mode=mode, cfg=cfg, state_dir=self.sd, market=self.mkt, echo=False,
                              broker=self.b if mode == "live" else None,
                              clock=lambda: self.t + pd.Timedelta(seconds=6))
        except Exception:
            self.close()
            raise
        self.e.models, self.e.thr = [StubModel(5.0)], 1.0
        self.e.tradable = ["ETH", "SOL"]
        self.e.coins = ["ETH", "SOL"]
        self.e.specs = {c: self.mkt.spec(c) for c in ("ETH", "SOL")}
        self.level = {"ETH": 100.0, "SOL": 20.0}

    def bars(self):
        idx = pd.date_range(self.t - pd.Timedelta(minutes=5), self.t - pd.Timedelta(minutes=1), freq="min")
        for c, px in (("BTC", 60000.0), ("ETH", 102.0), ("SOL", 22.0)):
            self.e.spot[c] = pd.DataFrame({"open": px, "high": px, "low": px, "close": px, "volume": 1.0}, index=idx)

    def pn(self):
        out = {}
        for c in ("ETH", "SOL"):
            row = {f: 0.0 for f in wick.FEATS}
            row.update(level=self.level[c], sig=0.01, z_res60=0.0, bid_depth_bp=1.0)
            out[c] = pd.DataFrame([row])
        return out

    def allocate(self):
        self.bars()
        self.v.calls, self.mkt.calls = [], []
        self.e._allocate(self.pn(), self.t)

    def settle(self):
        self.bars()
        self.v.calls = []
        self.e._settle(self.t - pd.Timedelta(minutes=1), self.t)

    def next(self):
        self.t += pd.Timedelta(minutes=1)

    def ev(self, kind=None):
        p = os.path.join(self.sd, "events.jsonl")
        out = [json.loads(x) for x in open(p)] if os.path.exists(p) else []
        return [x for x in out if kind is None or x["kind"] == kind]

    def e4(self, c):
        lad = [l for l in self.e.ladders(c)]
        return lad[0]["orders"].get("e4") if lad else None

    def close(self):
        shutil.rmtree(self.sd, ignore_errors=True)


def t_engine_new_keep():
    m = Mini()
    try:
        check("engine: the setting is read and the batch path is on (live broker with the methods)",
              m.e.order_path == "batch" and m.e._batch_on())
        m.allocate()
        k = methods(m.v)
        check("engine, new bids: one best-bid request, then the two bids (one place_many, plain loop), no cancel",
              k == ["get_best_bid_ask", "create_order", "create_order"]
              and not any(x[0] == "best_bid" for x in m.mkt.calls)
              and len(m.ev("arm")) == 2 and [x[0] for x in m.mkt.calls] == ["bids_ahead", "bids_ahead"], str(k))
        sol = m.e4("SOL")
        m.next()
        m.allocate()
        check("engine, an unchanged bid: kept, no request at all", methods(m.v) == [] and m.e4("SOL") is sol
              and len(m.ev("arm")) == 2, str(methods(m.v)))
    finally:
        m.close()


def t_engine_fill_before_cancel():
    m = Mini()
    try:
        m.allocate()
        o = m.e4("ETH")
        m.v.orders[o["id"]].update(status="FILLED", filled_size=repr(o["size"]), average_filled_price=repr(o["px"]),
                                   total_fees=repr(o["size"] * o["px"] * 6e-4))
        m.next()
        m.level["ETH"] = 99.0                          # ETH re-prices; it filled before the cancel
        m.allocate()
        k = methods(m.v)
        eth = m.e.ladders("ETH")[0]
        ent = m.ev("fill_entry")
        check("engine, a fill before the cancel: booked once, the ladder open, no new ETH bid",
              len(ent) == 1 and ent[0]["coin"] == "ETH" and eth["status"] == "open" and "e4" not in eth["orders"]
              and not any(c[1] == "create_order" and c[2]["product_id"] == "ETH-USD" for c in m.v.calls)
              and k[:2] == ["get_best_bid_ask", "cancel_orders"], str(k))
        check("engine, a fill before the cancel: no reprice counted", m.e.counts.get("reprice") is None)
        m.next()
        m.settle()
        check("engine, a fill before the cancel: the next settle does not book it again",
              len(m.ev("fill_entry")) == 1)
    finally:
        m.close()


def t_engine_unconfirmed():
    m = Mini()
    try:
        m.allocate()
        o = m.e4("ETH")
        m.v.reads[o["id"]] = ["OPEN"]                  # the venue keeps showing it open
        m.v.script["cancel_orders"] = [lambda kw: {"results": [dict(success=True, order_id=i)
                                                               for i in kw["order_ids"]]}]
        m.next()
        m.level["ETH"] = 99.0
        m.allocate()
        w = [x for x in m.ev("warning") if x.get("msg") == "cancel not confirmed; retrying"]
        check("engine, an unconfirmed cancel: the order kept, today's warning, no new ETH bid",
              m.e4("ETH") is o and len(w) == 1 and m.e.counts.get("cancel_unconfirmed") == 1
              and not any(c[1] == "create_order" for c in m.v.calls))
        del m.v.reads[o["id"]]
        m.next()
        m.allocate()
        k = methods(m.v)
        check("engine, an unconfirmed cancel: retried next minute, then the new bid",
              k[:2] == ["get_best_bid_ask", "cancel_orders"] and "create_order" in k and m.e4("ETH")["px"] == 99.0
              and m.e.counts.get("reprice") == 1, str(k))
    finally:
        m.close()


def t_engine_duration():
    m = Mini()
    try:
        m.v.min_end = m.t + pd.Timedelta(seconds=6 + 400)    # the venue wants bids living at least 400 s
        m.allocate()
        k = methods(m.v)
        w = [x for x in m.ev("warning") if "good-til-date bids now last" in x.get("msg", "")]
        ends = sorted(m.e4(c)["expires"] for c in ("ETH", "SOL"))
        check("engine, a duration error on both bids of one place_many: lifetime doubled once (one warning), both "
              "sent again singly at 600 s and placed", m.e.ttl == 600 and len(w) == 1 and m.e.state["gtd_ttl_s"] == 600
              and k == ["get_best_bid_ask"] + ["create_order"] * 4 and len(m.ev("arm")) == 2
              and ends == [(m.t + pd.Timedelta(seconds=606)).isoformat()] * 2 and not m.ev("reject"), str(k))
        ev = [x["kind"] for x in m.ev()]
        check("engine, duration: the events in today's order (warning, arm, arm)", ev == ["warning", "arm", "arm"],
              str(ev))
    finally:
        m.close()


def t_engine_breaker():
    m = Mini()
    try:
        m.v.script["get_best_bid_ask"] = [raises("x")] * 3
        for i in range(3):
            for c in ("ETH", "SOL"):                   # a new level each minute: every coin asks for its bid again
                m.level[c] += 0.5
            m.allocate()
            if i < 2:
                m.next()
        w = [x for x in m.ev("warning") if "best_bids switched off" in x.get("msg", "")]
        check("engine, best_bids failing three minutes in a row: one warning event, batch_fallback counted",
              len(w) == 1 and m.e.counts.get("batch_fallback") == 1, str(w))
        m.next()
        m.level["ETH"] += 0.5
        m.allocate()
        check("engine, best_bids off: no best-bid request; today's single request (public book) instead",
              "get_best_bid_ask" not in methods(m.v) and ("best_bid", "ETH-USD") in m.mkt.calls, str(m.mkt.calls))
    finally:
        m.close()


def t_engine_cancel_raises():
    m = Mini()
    try:
        m.allocate()

        def boom(orders):
            raise RuntimeError("cancel_many broke")
        m.b.cancel_many = boom
        m.next()
        m.level["ETH"] = 99.0
        old = E.time.sleep
        E.time.sleep = m.ck.sleep                      # today's cancel waits with time.sleep
        try:
            m.allocate()
        finally:
            E.time.sleep = old
        k = methods(m.v)
        w = [x for x in m.ev("warning") if "batch cancel failed" in x.get("msg", "")]
        check("engine, cancel_many raises: one warning, today's single cancel (cancel_orders of one id, then "
              "get_order), then the new bid", len(w) == 1 and k == ["get_best_bid_ask", "cancel_orders", "get_order",
                                                                    "create_order"]
              and m.e4("ETH")["px"] == 99.0 and m.e.counts.get("reprice") == 1, str(k))
    finally:
        m.close()


def t_engine_settle():
    m = Mini()
    try:
        m.allocate()
        o = m.e4("ETH")
        m.v.orders[o["id"]].update(filled_size=repr(o["size"] / 2), average_filled_price=repr(o["px"]))
        m.next()
        m.v.script["list_orders"] = [lambda kw: {"orders": [m.v.view(i) for i in kw["order_ids"]
                                                            if m.v.orders[i]["product_id"] == "ETH-USD"]}]
        m.settle()
        k = methods(m.v)
        check("engine, settle: the fills request, one read of every resting order; the order it missed read singly; "
              "the part fill booked", k[:3] == ["get_fills", "list_orders", "get_order"]
              and len(m.ev("fill_entry")) == 1 and m.e.counts.get("snap_miss") == 1, str(k))
    finally:
        m.close()


def t_engine_settle_recent_fill():
    m = Mini()
    try:
        m.allocate()
        o = m.e4("ETH")
        m.v.orders[o["id"]].update(filled_size=repr(o["size"] / 2), average_filled_price=repr(o["px"]))
        m.v.filled_ids = [o["id"]]                     # the fills list names it ...
        stale = lambda kw: {"orders": [dict(m.v.view(i), filled_size="0.0", average_filled_price="0.0")  # noqa: E731
                                       for i in kw["order_ids"]]}       # ... the order list still shows it unfilled
        m.v.script["list_orders"] = [stale, stale]
        m.next()
        m.settle()
        k = [(c[1], c[2].get("order_ids") or c[2].get("order_id")) for c in m.v.calls]
        ent = m.ev("fill_entry")
        check("engine, settle: an order the list shows unfilled while the fills list names it -> left out of the "
              "list request, read singly, its fill booked this minute",
              k[0][0] == "get_fills" and k[1] == ("list_orders", [m.e4("SOL")["id"]]) and ("get_order", o["id"]) in k
              and len(ent) == 1 and ent[0]["coin"] == "ETH", str(k))
        fl = [c[2]["start_sequence_timestamp"] for c in m.v.calls if c[1] == "get_fills"]
        m.next()
        m.settle()
        fl2 = [c[2]["start_sequence_timestamp"] for c in m.v.calls if c[1] == "get_fills"]
        check("engine, settle: booked once (the next minute's settle books nothing more); the fills request goes "
              "back 3 minutes the first time, then to the previous settle minus 10 s",
              len(m.ev("fill_entry")) == 1 and fl == [(T0 + pd.Timedelta(seconds=66) - pd.Timedelta(minutes=3))
                                                      .strftime("%Y-%m-%dT%H:%M:%S.%fZ")]
              and fl2 == [(T0 + pd.Timedelta(seconds=56)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")], str((fl, fl2)))
    finally:
        m.close()
    m = Mini()
    try:
        m.allocate()
        m.v.script["get_fills"] = [raises("503")]
        m.next()
        m.settle()
        k = methods(m.v)
        check("engine, settle: the fills request raising -> no list request this minute, every order read singly, "
              "snap_miss for each", k == ["get_fills", "get_order", "get_order"] and m.e.counts.get("snap_miss") == 2,
              str(k))
    finally:
        m.close()


def t_engine_snap_check():
    m = Mini()
    try:
        m.allocate()
        m.next()
        m.settle()
        k = methods(m.v)
        check("engine, running check: equal dicts -> nothing counted; one covered order read singly after the list",
              k == ["get_fills", "list_orders", "get_order"] and "snap_mismatch" not in m.e.counts
              and not m.ev("warning"), str(k))
        for oid in m.v.orders:                         # both bids fill a part; the list does not show it yet
            m.v.orders[oid].update(filled_size=repr(30.0), average_filled_price=repr(1.0))
        lag = lambda kw: {"orders": [dict(m.v.view(i), filled_size="0.0", average_filled_price="0.0")  # noqa: E731
                                     for i in kw["order_ids"]]}
        m.v.script["list_orders"] = [lag]
        m.next()
        m.settle()
        check("engine, running check: a fill landing between the two reads (the single read shows more) -> not a "
              "mismatch; the single read used for that order (its fill booked)", "snap_mismatch" not in m.e.counts
              and len(m.ev("fill_entry")) == 1, str(m.e.counts))
    finally:
        m.close()
    m = Mini()
    try:
        m.allocate()
        for oid in m.v.orders:
            m.v.orders[oid]["status"] = "QUEUED"
        other = lambda kw: {"orders": [dict(m.v.view(i), status="OPEN") for i in kw["order_ids"]]}  # noqa: E731
        m.v.script["list_orders"] = [other, other]
        m.next()
        m.settle()
        w = [x for x in m.ev("warning") if "differs from the single read" in x.get("msg", "")]
        check("engine, running check: a different status with equal fills -> a mismatch, counted and logged with both "
              "dicts", m.e.counts.get("snap_mismatch") == 1 and len(w) == 1 and w[0]["snapshot"]["status"] == "OPEN"
              and w[0]["single"]["status"] == "QUEUED", str(w))
        m.next()
        m.settle()
        off = [x for x in m.ev("warning") if "snapshot switched off" in x.get("msg", "")]
        check("engine, running check: the second mismatch switches the snapshot off (reported once, batch_fallback)",
              m.e.counts.get("snap_mismatch") == 2 and len(off) == 1 and m.e.counts.get("batch_fallback") == 1
              and not m.b.batch_on("snapshot"), str(off))
        m.next()
        m.settle()
        check("engine, running check: snapshot off -> settle reads every order singly (no fills or list request)",
              methods(m.v) == ["get_order", "get_order"], str(methods(m.v)))
    finally:
        m.close()


def t_engine_setting():
    for path in (None, "serial"):
        m = Mini(path=path)
        try:
            called = []
            for n in ("snapshot", "cancel_many", "best_bids", "place_many"):
                setattr(m.b, n, (lambda n: lambda *a, **k: called.append(n))(n))
            m.allocate()
            m.next()
            m.level["ETH"] = 99.0
            old = E.time.sleep
            E.time.sleep = m.ck.sleep
            try:
                m.allocate()
                m.settle()
            finally:
                E.time.sleep = old
            check(f"engine, order_path {path!r}: the serial path, no batch method called",
                  not m.e._batch_on() and not called and len(m.ev("arm")) == 2, str(called))
        finally:
            m.close()
    m = Mini(mode="paper")
    try:
        check("engine: a paper engine with order_path batch stays on the paper path",
              m.e.order_path == "batch" and isinstance(m.e.broker, E.PaperBroker) and not m.e._batch_on())
    finally:
        m.close()
    try:
        Mini(path="fast")
        ok = False
    except ValueError:
        ok = True
    check("engine: any other order_path is refused at start", ok)
    m = Mini()
    try:
        check("engine, heartbeat: no rate_limit field before any header was seen", m.e._hb_rate_limit() == {})
        m.v.script["get_best_bid_ask"] = [lambda kw: {"pricebooks": [], "rate_limit_limit": "30",
                                                      "rate_limit_remaining": "28", "rate_limit_reset": "1"}]
        m.allocate()
        m.t = T0.floor("h") + pd.Timedelta(hours=1)
        m.e._heartbeat(m.t)
        hb = m.ev("heartbeat")
        check("engine, heartbeat: rate_limit once seen, and the batch counters in counts",
              hb and hb[-1].get("rate_limit") == {"limit": "30", "remaining": "28", "reset": "1"}
              and hb[-1]["counts"].get("bbo_miss") == 2, str(hb[-1] if hb else None))
    finally:
        m.close()


def t_engine_place_guard():
    m = Mini()
    try:
        def broken(reqs):                              # one bid reaches the venue, then the call raises
            sp, side, px, size, po, end = reqs[0]
            m.b._place_on(m.b.c, sp, side, px, size, po, end)
            raise RuntimeError("place_many broke")
        real = m.b.place_many
        m.b.place_many = broken
        m.allocate()
        k = methods(m.v)
        err = [x for x in m.ev("error") if "place_many failed" in x.get("error", "")]
        swept = [x for x in m.ev("warning") if x.get("msg") == "cancelled a bot order missing from state"]
        check("engine, place_many raises: an error event, the sweep ran at once (the orphan bid cancelled), no "
              "ladder left without an order", len(err) == 1 and len(swept) == 1 and "list_orders" in k
              and k.count("cancel_orders") == 1 and not m.e.ladders(), str(k))
        m.b.place_many = real
        m.next()
        m.allocate()
        ids = [o["id"] for l in m.e.ladders() for o in l["orders"].values()]
        live = [i for i, o in m.v.orders.items() if o["status"] == "OPEN"]
        check("engine, place_many raises: next minute one bid per coin, each recorded once, the venue's open orders "
              "exactly the recorded ones", len(m.e.ladders()) == 2 and len(ids) == 2 and sorted(ids) == sorted(live),
              str((ids, live)))
    finally:
        m.close()


def part2():
    t_engine_new_keep()
    t_engine_fill_before_cancel()
    t_engine_unconfirmed()
    t_engine_duration()
    t_engine_breaker()
    t_engine_cancel_raises()
    t_engine_settle()
    t_engine_settle_recent_fill()
    t_engine_snap_check()
    t_engine_setting()
    t_engine_place_guard()


if __name__ == "__main__":
    part1()
    part2()
    print("ORDER PATH UNIT TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
