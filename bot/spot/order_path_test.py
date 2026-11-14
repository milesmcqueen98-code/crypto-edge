#!/usr/bin/env python3
"""Order path test: the live-path simulation three ways, which must agree exactly (bot/spot/README.md, "Order path").

  (i)   live_sim_test.py as it is: its FakeExchange stands in for the whole broker;
  (ii)  the real LiveBroker on the serial path, over FakeClient, a stand-in for the venue's library
        (coinbase-advanced-py 1.8.4) on top of the same FakeExchange: LiveBroker's own code runs end to end;
  (iii) the same on the batch path ("order_path": "batch", 10 requests a second, 3 placing threads, each on its own
        FakeClient made by a factory).

FakeClient implements every library method LiveBroker calls (create_order, limit_order_gtc_buy/sell, market_order_sell,
get_order, list_orders, cancel_orders, get_best_bid_ask, get_accounts, get_fills, get_transaction_summary), answers in
the library's shapes as dicts (what its to_dict() gives; LiveBroker._d accepts dicts), and delegates to FakeExchange's
state and fault injection so that the random draws come at the same logical operations in the same order as in (i):
- a cancel draws once per open order (FakeExchange.cancel), in the order the orders are named;
- a take-profit placement draws for the injected server error (FakeExchange.place), which FakeClient raises as an
  HTTPError, as the library does;
- a market sell draws for the half fill and the unreadable outcome (FakeExchange.market_sell). An unreadable sell
  stays unreadable for LiveBroker.market_sell's own 15 reads and then for the 2 reads (i) allows.
Prices and sizes arrive as the decimal strings LiveBroker sends; FakeClient puts them back on the tick and lot grid as
the engine computes them (integer x increment), so FakeExchange sees the engine's floats. Numbers go back as repr()
strings, which float() reads back exactly. Two things the venue would not be told are passed to the stand-in by the
test: the price a market sell executes at (FakeExchange takes the engine's own model of it, ref_px - cost_px, which
LiveBroker does not send; a subclass of LiveBroker in this file hands it over before calling the real market_sell),
and, in (iii), the order in which the three threads' placements reach FakeExchange (request order, by a turnstile,
so that the run is deterministic; the venue would take them in arrival order).
The engine module's sleeps (time.sleep in LiveBroker.cancel, market_sell, _find_by_client_id) are replaced by a fake
for the run, and the broker's injectable sleep and clock are the request model's.

Checks, (ii) and (iii) each against (i), on the window with and without the server's death:
- every entry and exit (minute, coin, ladder, rung, price, size, P&L), every ladder's P&L, the final equity, and the
  exchange's USD balance, all equal exactly;
- live_sim_test's own checks pass (no orphan order, coin balances zero after the last rung, equity equals the
  exchange's USD balance, no bid outlived the dead server);
- the injected faults drawn are the same (unconfirmed cancels, half sells, unreadable sells, take-profit errors);
- the whole event log equals (i)'s line for line, order ids masked, heartbeats and fee_tier lines aside (the fee tier
  goes through the library's decimal string: 1e4 x 0.0006 = 5.999999999999999, not 6.0).
Reported, not checked: requests per minute by kind and a modelled clock (MODEL: each request costs 0.1 s; requests of
one place_many on k threads overlap, bound by the pace; the waits of the code itself count), for (ii) and (iii).

Usage: python bot/spot/order_path_test.py "2025-10-10 20:00" "2025-10-11 02:00" ["--death=2025-10-10 21:10"]
       [--only=ii,iii]   (default: i, ii and iii)   [--keep]   keep the runs' state folders (else removed on a pass)
"""
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import types

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot.spot import engine as E  # noqa: E402
from bot.spot import live_sim_test as L  # noqa: E402

FAILS = []
HEX = re.compile(r"[0-9a-f]{12,}")
COST = 0.1                                             # MODEL: seconds per request
EPOCH = pd.Timestamp("2025-01-01")                    # MODEL: its clock is seconds since this


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""), flush=True)
    if not ok:
        FAILS.append(name)


class SimHTTPError(Exception):
    """The library's HTTPError, with the text FakeExchange gives its injected server error."""

    def __init__(self, msg, code=503):
        super().__init__(msg)
        self.response = types.SimpleNamespace(status_code=code, headers={})

    def __repr__(self):
        return 'HTTPError("%s")' % self.args[0]


# ------------------------------------------------------------------------------------------------ the request model
class Model:
    """MODEL clock, per thread: each request costs COST seconds on the calling thread's lane; a wait adds its length.
    A place_many on worker threads starts every worker's lane at the main lane's time and ends at the latest one."""

    def __init__(self):
        self.lock = threading.RLock()
        self.main = threading.get_ident()
        self.T = 0.0
        self.lanes = {}                                # thread -> (epoch, time)
        self.epoch, self.T0 = None, 0.0

    def now(self):
        with self.lock:
            tid = threading.get_ident()
            if tid == self.main or self.epoch is None:
                return self.T
            ep, t = self.lanes.get(tid, (None, 0.0))
            return t if ep == self.epoch else self.T0

    def add(self, s):
        with self.lock:
            tid = threading.get_ident()
            if tid == self.main or self.epoch is None:
                self.T += s
                return self.T
            t = self.now() + s
            self.lanes[tid] = (self.epoch, t)
            return t

    sleep = add

    def begin(self):
        with self.lock:
            self.epoch, self.T0 = object(), self.T

    def end(self):
        with self.lock:
            ts = [t for ep, t in self.lanes.values() if ep == self.epoch]
            self.T = max([self.T] + ts)
            self.epoch = None


class Shared:
    """State shared by every FakeClient of one run: the lock around FakeExchange, the request log, the model, the
    turnstile of the placing threads, the price of the next market sell."""

    def __init__(self, ex, mkt):
        self.ex, self.mkt = ex, mkt
        self.lock = threading.RLock()
        self.model = Model()
        self.log = []                                  # dicts: minute, phase, kind, client, start, end, ok
        self.minute, self.phase = "start", "start"
        self.sell_px = None
        self.turn = threading.Condition()
        self.expect = []                               # keys of the placements of the running place_many, in order
        self.n_clients = 0

    def rec(self, kind, client, ok=True):
        with self.lock:
            st = self.model.now()
            en = self.model.add(COST)
            self.log.append(dict(minute=self.minute, phase=self.phase, kind=kind, client=client, start=st, end=en,
                                 ok=ok, thread=threading.get_ident()))
            return self.log[-1]


def grid(s, inc):
    """A decimal string LiveBroker sent, back on the engine's grid: integer x increment, as floor_to and floor_size."""
    return int(round(float(s) / inc)) * inc


def num(x):
    return repr(float(x))


class FakeClient:
    """Stand-in for coinbase.rest.RESTClient over live_sim_test.FakeExchange (see the module docstring)."""

    def __init__(self, sh):
        self.sh, self.ex = sh, sh.ex
        with sh.lock:
            sh.n_clients += 1
            self.name = f"c{sh.n_clients}"
        self.threads = set()

    def _use(self):
        self.threads.add(threading.get_ident())

    def _spec(self, product):
        c = product.split("-")[0]
        sp = self.sh.mkt.spec(c)
        return c, E.Spec(product, sp.tick, sp.lot, sp.min_usd)

    def _od(self, oid, o, s):
        avg = o.get("avg_px", s["avg"])
        return dict(order_id=oid, product_id=o["coin"] + "-USD", side=o["side"], client_order_id=o["client_order_id"],
                    status=s["status"], filled_size=num(s["filled"]), average_filled_price=num(avg),
                    total_fees=num(s["fees"]), last_fill_time=None if o.get("last_fill") is None
                    else pd.Timestamp(o["last_fill"]).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    pending_cancel=False, order_type="MARKET" if o.get("market") else "LIMIT")

    def _wait_turn(self, key):
        sh = self.sh
        with sh.turn:
            if key not in sh.expect:
                return
            ok = sh.turn.wait_for(lambda: sh.expect and sh.expect[0] == key, timeout=60)
            if not ok:
                raise AssertionError(f"turnstile: {key} never came up")

    def _done_turn(self, key):
        sh = self.sh
        with sh.turn:
            if sh.expect and sh.expect[0] == key:
                sh.expect.pop(0)
                sh.turn.notify_all()

    # ---- orders
    def _create(self, kind, client_order_id, product_id, side, px_s, size_s, post_only, end_s):
        self._use()
        key = (product_id, side, px_s, size_s)
        self._wait_turn(key)
        try:
            c, sp = self._spec(product_id)
            px, size = grid(px_s, sp.tick), grid(size_s, sp.lot)
            end = None if end_s is None else pd.Timestamp(end_s.rstrip("Z"))
            with self.sh.lock:
                oid, err = self.ex.place(sp, side, px, size, post_only=post_only, end_time=end)
                if oid is not None:
                    self.ex.orders[oid]["client_order_id"] = client_order_id
                r = self.sh.rec(kind, self.name, ok=oid is not None)
                r.update(side=side, gtd=end is not None)
        finally:
            self._done_turn(key)
        if oid is not None:
            return {"success": True, "success_response": {"order_id": oid, "product_id": product_id, "side": side,
                                                          "client_order_id": client_order_id}}
        if str(err).startswith("HTTPError("):
            raise SimHTTPError(str(err)[len('HTTPError("'):-2])
        return {"success": False, "failure_reason": "UNKNOWN_FAILURE_REASON", "order_id": "",
                "error_response": json.loads(err)}

    def create_order(self, client_order_id, product_id, side, order_configuration, **kw):
        g = order_configuration["limit_limit_gtd"]
        return self._create("create_order", client_order_id, product_id, side, g["limit_price"], g["base_size"],
                            g.get("post_only", False), g["end_time"])

    def limit_order_gtc_buy(self, client_order_id, product_id, base_size, limit_price, post_only=False, **kw):
        return self._create("limit_order_gtc_buy", client_order_id, product_id, "BUY", limit_price, base_size,
                            post_only, None)

    def limit_order_gtc_sell(self, client_order_id, product_id, base_size, limit_price, post_only=False, **kw):
        return self._create("limit_order_gtc_sell", client_order_id, product_id, "SELL", limit_price, base_size,
                            post_only, None)

    def market_order_sell(self, client_order_id, product_id, base_size, **kw):
        self._use()
        c, sp = self._spec(product_id)
        size = grid(base_size, sp.lot)
        with self.sh.lock:
            ref_px, cost_px = self.sh.sell_px
            self.sh.sell_px = None
            px, fee, q, err = self.ex.market_sell(sp, size, ref_px, cost_px)
            self.sh.rec("market_order_sell", self.name)
            if isinstance(err, dict) and err.get("pending_order"):
                oid = err["pending_order"]
                self.ex.unreadable[oid] += 15              # LiveBroker.market_sell's own 15 reads cannot read it either
                self.ex.orders[oid]["client_order_id"] = client_order_id
                return {"success": True, "success_response": {"order_id": oid, "product_id": product_id}}
            if px is None:
                return {"success": False, "error_response": {"error": str(err)}}
            oid = "m" + E.uuid.uuid4().hex
            self.ex.orders[oid] = dict(coin=c, side="SELL", px=px, size=size, filled=q, value=q * px, fees=fee,
                                       status="FILLED" if q >= size * 0.999 else "CANCELLED",
                                       next=self.ex.clock().floor("min"), client_order_id=client_order_id,
                                       expires=None, market=True, avg_px=px)
            return {"success": True, "success_response": {"order_id": oid, "product_id": product_id}}

    def get_order(self, order_id, **kw):
        self._use()
        with self.sh.lock:
            self.sh.rec("get_order", self.name)
            if order_id not in self.ex.orders:
                raise SimHTTPError("400 Client Error: INVALID_ARGUMENT", 400)
            s = self.ex.status(order_id)                   # FakeExchange's read: advance, unreadable sells
            return {"order": self._od(order_id, self.ex.orders[order_id], s)}

    def list_orders(self, order_ids=None, product_ids=None, order_status=None, limit=None, cursor=None, **kw):
        self._use()
        with self.sh.lock:
            ex = self.ex
            if order_ids is not None:                      # the batch path's read of several orders
                self.sh.rec("list_orders(ids)", self.name)
                ex._advance()
                out = [self._od(i, ex.orders[i], self._read(i)) for i in order_ids
                       if i in ex.orders and not ex.unreadable.get(i, 0) > 0]
                return {"orders": out, "sequence": 0, "has_next": False, "cursor": ""}
            if product_ids is not None:                    # the search by client order id
                self.sh.rec("list_orders(product)", self.name)
                ids = [i for i, o in ex.orders.items() if o["coin"] + "-USD" in product_ids][::-1][:limit or 1000]
                return {"orders": [self._od(i, ex.orders[i], self._read(i)) for i in ids], "has_next": False,
                        "cursor": ""}
            self.sh.rec("list_orders(open)", self.name)    # reconcile: open orders (FakeExchange.open_orders)
            st = set(order_status or [])
            out = [dict(order_id=k, client_order_id=v["client_order_id"], product_id=v["coin"] + "-USD",
                        side=v["side"], status=v["status"]) for k, v in ex.orders.items() if v["status"] in st]
            return {"orders": out, "sequence": 0, "has_next": False, "cursor": ""}

    def _read(self, oid):
        o = self.ex.orders[oid]
        return dict(filled=o["filled"], avg=o["value"] / o["filled"] if o["filled"] else 0.0, fees=o["fees"],
                    status=o["status"])

    def cancel_orders(self, order_ids, **kw):
        self._use()
        res = []
        with self.sh.lock:
            self.sh.rec("cancel_orders", self.name)
            for i in order_ids:
                o = self.ex.orders.get(i)
                if o is None:
                    res.append(dict(success=False, failure_reason="UNKNOWN_CANCEL_ORDER", order_id=i))
                    continue
                was = o["status"]
                self.ex.cancel(dict(id=i, filled=0.0, value=0.0, fees=0.0, px=o["px"]))   # its draw, as in (i)
                if was == "OPEN":
                    res.append(dict(success=True, failure_reason="UNKNOWN_CANCEL_FAILURE_REASON", order_id=i))
                else:
                    res.append(dict(success=False, order_id=i, failure_reason="ORDER_IS_FULLY_FILLED"
                                    if o["status"] == "FILLED" else "UNKNOWN_CANCEL_FAILURE_REASON"))
        return {"results": res}

    def get_best_bid_ask(self, product_ids=None, **kw):
        self._use()
        with self.sh.lock:
            self.sh.rec("get_best_bid_ask", self.name)
            out = []
            for p in product_ids or []:
                bb = float(self.sh.best_bid(p))
                out.append(dict(product_id=p, bids=[dict(price=num(bb), size="1")] if np.isfinite(bb) else [],
                                asks=[], time="2025-10-10T00:00:00Z"))
            return {"pricebooks": out}

    def get_accounts(self, limit=None, **kw):
        self._use()
        with self.sh.lock:
            self.sh.rec("get_accounts", self.name)
            b = self.ex.balances()
            acc = [dict(currency=c, available_balance=dict(value=num(a), currency=c), hold=dict(value=num(h),
                                                                                                currency=c))
                   for c, (a, h) in b.items()]
            return {"accounts": acc, "has_next": False, "cursor": "", "size": len(acc)}

    def get_fills(self, start_sequence_timestamp=None, limit=None, cursor=None, **kw):
        self._use()
        with self.sh.lock:
            self.sh.rec("get_fills", self.name)
            ids = sorted(self.ex.filled_order_ids(pd.Timestamp(start_sequence_timestamp.rstrip("Z"))))
            i0, n = int(cursor or 0), int(limit or 100)
            page = ids[i0:i0 + n]
            return {"fills": [dict(order_id=i, trade_id=f"t{i}") for i in page],
                    "cursor": str(i0 + n) if i0 + n < len(ids) else ""}

    def get_transaction_summary(self, **kw):
        self._use()
        with self.sh.lock:
            self.sh.rec("get_transaction_summary", self.name)
        return {"fee_tier": {"pricing_tier": "fake VIP 1", "maker_fee_rate": "0.0006", "taker_fee_rate": "0.00125"},
                "advanced_trade_only_volume": None}


class SimBroker(E.LiveBroker):
    """The real LiveBroker. market_sell hands the engine's model price of the sell to the stand-in first (the venue
    would execute at its market; FakeExchange executes at ref_px - cost_px), then runs LiveBroker.market_sell."""

    def market_sell(self, spec, size, ref_px, cost_px):
        self.c.sh.sell_px = (ref_px, cost_px)
        return E.LiveBroker.market_sell(self, spec, size, ref_px, cost_px)


# ------------------------------------------------------------------------------------------------ one run
PUBLIC = ("best_bid", "bids_ahead")


def run(start, end, death, path, tag):
    """path None: (i), FakeExchange as the broker. "serial" / "batch": the real LiveBroker over FakeClient."""
    cfg = json.load(open(os.path.join(HERE, "config.json")))
    if path is not None:
        cfg.update(order_path=path, orders_rate=10, place_workers=3 if path == "batch" else 1)
    else:
        cfg.pop("order_path", None)
    tmp = tempfile.mkdtemp(prefix=f"order_path_{tag}_")
    cp = os.path.join(tmp, "config.json")
    json.dump(cfg, open(cp, "w"), indent=2)
    hold = {}
    real_time = E.time

    def make_broker(ex, mkt, now):
        hold["ex"] = ex
        if path is None:
            return ex
        if "sh" not in hold:
            hold["sh"] = Shared(ex, mkt)
            hold["sh"].best_bid = mkt.best_bid             # FakeClient's price answer reads the market unwrapped
            for name in PUBLIC:                            # public market data the engine asks for: counted, costed
                f = getattr(mkt, name)

                def g(*a, _f=f, _n=name):
                    hold["sh"].rec(f"public {_n}", "market")
                    return _f(*a)
                setattr(mkt, name, g)
        sh = hold["sh"]
        b = SimBroker(client=FakeClient(sh), client_factory=lambda: FakeClient(sh), order_path=path,
                      orders_rate=cfg["orders_rate"], place_workers=cfg["place_workers"])
        b.sleep, b.mono = sh.model.sleep, sh.model.now
        pm = b.place_many

        def place_many(reqs, _pm=pm, _b=b):                # the model's lanes and the turnstile around the real call
            with sh.turn:
                sh.expect = [(_b._p(q[0].product), q[1], E.fmt(q[2], q[0].tick), E.fmt(q[3], q[0].lot))
                             for q in reqs]
            sh.model.begin()
            try:
                return _pm(reqs)
            finally:
                sh.model.end()
                with sh.turn:
                    sh.expect = []
        b.place_many = place_many
        return b

    def on_engine(eng):
        if path is None:
            return
        sh = hold["sh"]

        def wrap(name, phase=None, step=False):
            f = getattr(eng, name)

            def g(*a, **k):
                prev, prev_m = sh.phase, sh.minute
                if phase == "start":
                    sh.minute = "start"                    # a process starting: not counted in any minute
                if step:                                   # the model's clock runs with the minutes (never back)
                    t = pd.Timestamp(a[0] if a else eng.clock()).floor("min")
                    sh.minute, sh.phase = t, "data"
                    sh.model.T = max(sh.model.T, (t - EPOCH).total_seconds() + 6)
                elif name == "fast_poll" and isinstance(sh.minute, pd.Timestamp):
                    sh.model.T = max(sh.model.T, (sh.minute - EPOCH).total_seconds() + 30)
                elif phase is not None:
                    if phase == "settle" and sh.phase == "data":
                        sh.data_end = sh.model.T          # the data step ended: cash read, settle begins
                        sh.log.append(dict(minute=sh.minute, phase="mark", kind="data_end", start=sh.model.T,
                                           end=sh.model.T, client="-", ok=True))
                    sh.phase = phase
                try:
                    return f(*a, **k)
                finally:
                    if phase is not None and not step:
                        sh.phase = prev
                    if phase == "start":
                        sh.minute = prev_m
            setattr(eng, name, g)
        wrap("step", step=True)
        for n, ph in (("_settle", "settle"), ("_manage", "manage"), ("_allocate", "allocate"),
                      ("_refresh_tps", "tps"), ("reconcile", "reconcile"), ("fast_poll", "fast_poll"),
                      ("start", "start")):
            wrap(n, ph)

    fake_time = types.SimpleNamespace(sleep=lambda s: hold["sh"].model.sleep(s) if "sh" in hold else None,
                                      time=real_time.time, monotonic=real_time.monotonic)
    E.time = fake_time
    try:
        sd, ok = L.main(start, end, death=death, config=cp, make_broker=make_broker, on_engine=on_engine)
    finally:
        E.time = real_time
        shutil.rmtree(tmp, ignore_errors=True)
    return dict(sd=sd, ok=ok, ex=hold["ex"], sh=hold.get("sh"), tag=tag)


# ------------------------------------------------------------------------------------------------ comparisons
def events(sd):
    return [json.loads(x) for x in open(os.path.join(sd, "events.jsonl"))]


def trades(ev):
    ent = [(e["ts"], e["coin"], e["ladder"], e["rung"], e["px"], e["size"], e["usd"], e["fee"]) for e in ev
           if e["kind"] == "fill_entry"]
    ext = [(e["ts"], e["coin"], e["ladder"], e["rung"], e["exit"], e["px"], e["size"], e["pnl"]) for e in ev
           if e["kind"] == "fill_exit"]
    lad = [(e["ladder"], e["pnl"]) for e in ev if e["kind"] == "ladder_close"]
    return ent, ext, lad


def lines(sd):
    out = []
    for x in open(os.path.join(sd, "events.jsonl")):
        k = json.loads(x)["kind"]
        if k not in ("heartbeat", "fee_tier"):
            out.append(HEX.sub("<id>", x.strip()))
    return out


INJECTED = ("cancel_unconfirmed", "partial_sell", "sell_unknown", "tp_error")


def compare(a, b):
    tag = f"{b['tag']} vs {a['tag']}"
    ea, eb = events(a["sd"]), events(b["sd"])
    ta, tb = trades(ea), trades(eb)
    check(f"{tag}: live-path checks pass on both", a["ok"] and b["ok"])
    check(f"{tag}: every entry equal (minute, coin, ladder, rung, price, size, USD, fee)", ta[0] == tb[0],
          f"{len(tb[0])} vs {len(ta[0])}")
    check(f"{tag}: every exit equal (minute, coin, ladder, rung, type, price, size, P&L)", ta[1] == tb[1],
          f"{len(tb[1])} vs {len(ta[1])}")
    check(f"{tag}: every ladder's P&L equal", ta[2] == tb[2], f"{len(tb[2])} ladders")
    sa = json.load(open(os.path.join(a["sd"], "state.json")))
    sb = json.load(open(os.path.join(b["sd"], "state.json")))
    check(f"{tag}: final equity equal", sa["equity"] == sb["equity"], f"{sb['equity']!r} vs {sa['equity']!r}")
    check(f"{tag}: the exchange's USD balance equal", a["ex"].usd == b["ex"].usd,
          f"{b['ex'].usd!r} vs {a['ex'].usd!r}")
    check(f"{tag}: no orphan order, coin balances zero", not b["ex"].open_orders()
          and not {c: v for c, v in b["ex"].coin.items() if abs(v) * b["ex"].mkt.last(c) > 0.01})
    na = {k: a["ex"].n[k] for k in INJECTED}
    nb = {k: b["ex"].n[k] for k in INJECTED}
    check(f"{tag}: the same injected faults drawn", na == nb, f"{nb} vs {na}")
    other = {k: (a["ex"].n[k], b["ex"].n[k]) for k in a["ex"].n if k not in INJECTED and a["ex"].n[k] != b["ex"].n[k]}
    print(f"  {tag}: the exchange's other counts that differ ({a['tag']}, {b['tag']}): {other or 'none'}", flush=True)
    la, lb = lines(a["sd"]), lines(b["sd"])
    d = next((i for i, (x, y) in enumerate(zip(la, lb)) if x != y), None)
    if d is None and len(la) != len(lb):
        d = min(len(la), len(lb))
    check(f"{tag}: every event line equal (order ids masked; heartbeats and fee_tier aside)", d is None,
          f"{len(lb)} vs {len(la)} lines")
    if d is not None:
        print(f"  first difference at line {d}:\n    {a['tag']}: {la[d] if d < len(la) else None}\n"
              f"    {b['tag']}: {lb[d] if d < len(lb) else None}", flush=True)
    ha = [{k: v for k, v in e.items() if k not in ("counts", "step_s", "rate_limit", "library")} for e in ea
          if e["kind"] == "heartbeat"]
    hb = [{k: v for k, v in e.items() if k not in ("counts", "step_s", "rate_limit", "library")} for e in eb
          if e["kind"] == "heartbeat"]
    check(f"{tag}: heartbeats equal apart from the counters, step timing, rate_limit and library", ha == hb)
    ca, cb = {}, {}
    for e in ea:
        for k, v in (e.get("counts") or {}).items():
            ca[k] = ca.get(k, 0) + v
    for e in eb:
        for k, v in (e.get("counts") or {}).items():
            cb[k] = cb.get(k, 0) + v
    new = ("snap_miss", "bbo_miss", "batch_fallback", "http_429")
    check(f"{tag}: the engine's counters equal, the batch path's own aside",
          {k: v for k, v in ca.items() if k not in new} == {k: v for k, v in cb.items() if k not in new},
          str({k: (ca.get(k), cb.get(k)) for k in set(ca) | set(cb) if ca.get(k) != cb.get(k)}))
    print(f"  {b['tag']}: batch path counters {({k: cb[k] for k in new if k in cb}) or 'none'}", flush=True)


# ------------------------------------------------------------------------------------------------ the model's report
def model_report(r):
    sh = r["sh"]
    log = [x for x in sh.log if isinstance(x["minute"], pd.Timestamp)]
    kinds = sorted({x["kind"] for x in log if x["kind"] != "data_end"})
    per = {}
    for x in log:
        if x["kind"] != "data_end":
            per.setdefault(x["minute"], {}).setdefault(x["kind"], 0)
            per[x["minute"]][x["kind"]] += 1
    mins = sorted(per)
    print(f"  [{r['tag']}] MODEL requests per minute by kind over {len(mins)} minutes with a request "
          f"(median, max; the minute's step and the fast poll after it):", flush=True)
    tot = [sum(per[m].values()) for m in mins]
    print(f"    all requests: median {np.median(tot):.0f}, max {max(tot)}", flush=True)
    for k in kinds:
        v = [per[m].get(k, 0) for m in mins]
        print(f"    {k}: median {np.median(v):.0f}, max {max(v)}, total {sum(v)}", flush=True)
    for k in ("get_order", "get_fills", "list_orders(ids)"):  # where the reads come from (settle, allocate, ...)
        ph = {}
        for x in log:
            if x["kind"] == k:
                ph[x["phase"]] = ph.get(x["phase"], 0) + 1
        if ph:
            print(f"    {k} by phase (total): " + ", ".join(f"{p} {n}" for p, n in sorted(ph.items())), flush=True)
    first, last = [], []
    for m in mins:
        ml = [x for x in log if x["minute"] == m]
        de = [x for x in ml if x["kind"] == "data_end"]
        bids = [x for x in ml if x["phase"] == "allocate" and x["kind"] == "create_order" and x["ok"]
                and x.get("side") == "BUY"]
        if de and bids:
            first.append(min(x["end"] for x in bids) - de[0]["start"])
            last.append(max(x["end"] for x in bids) - de[0]["start"])
    if first:
        q = lambda v: f"median {np.median(v):.2f}, p90 {np.percentile(v, 90):.2f}, max {max(v):.2f}"  # noqa: E731
        print(f"  [{r['tag']}] MODEL seconds from the data step's end to the first new bid resting ({len(first)} "
              f"minutes with a new bid): {q(first)}", flush=True)
        print(f"  [{r['tag']}] MODEL seconds from the data step's end to the last new bid resting: {q(last)}",
              flush=True)
    th = {}
    for x in sh.log:
        if "thread" in x and x["client"] != "market":
            th.setdefault(x["client"], set()).add(x["thread"])
    print(f"  [{r['tag']}] clients made {len(th)}; threads per client: {sorted({len(v) for v in th.values()})}",
          flush=True)
    return all(len(v) == 1 for v in th.values())


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    start, end = a[0], a[1]
    death = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--death=")), None)
    only = next((x.split("=", 1)[1].split(",") for x in sys.argv[1:] if x.startswith("--only=")), ["i", "ii", "iii"])
    t0 = time.time()
    res = {}
    for tag, path in (("i", None), ("ii", "serial"), ("iii", "batch")):
        if tag in only:
            what = "FakeExchange as the broker" if path is None else "LiveBroker over FakeClient, " + path
            print(f"=== ({tag}) {what}{', death ' + death if death else ''}", flush=True)
            res[tag] = run(start, end, death, path, tag)
    print(flush=True)
    for tag in ("ii", "iii"):
        if "i" in res and tag in res:
            compare(res["i"], res[tag])
    for tag in ("ii", "iii"):
        if tag in res:
            one = model_report(res[tag])
            if tag == "iii":
                check("(iii): each placing client was used by one thread only", one)
    print(f"{time.time() - t0:.0f} s", flush=True)
    for r in res.values():
        print(f"  ({r['tag']}) events {r['sd']}", flush=True)
    if not FAILS and "--keep" not in sys.argv:
        for r in res.values():
            shutil.rmtree(r["sd"], ignore_errors=True)


if __name__ == "__main__":
    main()
    print("ORDER PATH TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
