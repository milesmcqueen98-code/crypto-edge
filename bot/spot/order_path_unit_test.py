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
Part 2, the engine's batch path (Engine._allocate_batch, _settle), on a small scripted venue:
  added in the engine step (see part2 below).

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
        with self.v.lock:
            self.v.n += 1
            oid = f"o{self.v.n}"
        self.v.add(oid, product=kw["product_id"], cid=kw["client_order_id"], side=kw.get("side", "BUY"))
        return {"success": True, "success_response": {"order_id": oid}}

    def create_order(self, **kw):
        return self._new(kw, "create_order")

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
def t_cancel_many():
    # the batch cancel raises: the reads decide (here the venue did cancel)
    ck = Clock()
    v = Venue(ck)
    v.add("a")
    v.add("b")
    v.script["cancel_orders"] = [lambda kw: (v.orders["a"].update(status="CANCELLED"),
                                             v.orders["b"].update(status="CANCELLED"), raises("timeout")(kw))[2]]
    b = broker(v, ck)
    r = b.cancel_many([order("a"), order("b")])
    check("cancel_many: the batch cancel raises -> the reads decide (both cancelled: confirmed, no fill)",
          r == {"a": (None, True), "b": (None, True)} and methods(v) == ["cancel_orders", "list_orders"], str(r))
    b2 = broker(Venue(ck), ck)
    b2.c.v.add("c")
    b2.c.v.script["cancel_orders"] = [raises("timeout")]
    b2.c.v.reads["c"] = ["OPEN"]
    r2 = b2.cancel_many([order("c")])
    check("cancel_many: the batch cancel raises and the order stays open -> not confirmed after seven reads",
          r2 == {"c": (None, False)} and methods(b2.c.v).count("list_orders") == 7, str(r2))

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
    v.script["cancel_orders"] = [raises("x"), lambda kw: {"oops": 1}, raises("x")]
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
    t_breaker()
    t_pace()
    t_headers()
    t_fills()
    t_defaults()


if __name__ == "__main__":
    part1()
    print("ORDER PATH UNIT TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
