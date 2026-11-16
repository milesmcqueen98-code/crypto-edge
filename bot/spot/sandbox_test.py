#!/usr/bin/env python3
"""Live-broker smoke test against Coinbase's Advanced Trade sandbox (https://api-sandbox.coinbase.com).

The sandbox returns static, production-format responses for the Accounts and Orders endpoints, with no auth and no
money. Every LiveBroker call the engine makes is sent through the official SDK exactly as live: create_order (good-til-
date bid), limit GTC sell, get_order, batch cancel, list orders, list fills, accounts, preview and market sell. The test
checks the requests are accepted and the responses parse into what the engine expects. The X-Sandbox header simulates
the documented errors (insufficient funds on create and preview, failed cancel).

The batch order path's requests (README, "Order path") are checked the same way on a second broker whose clients are
built as the batch path builds them (rate_limit_headers=True, a client factory, three placing threads): snapshot (list
orders by ids), cancel_many (batch cancel, then reads), best_bids (best bid/ask), place_many on one and on three
threads, the venue's limit headers. The sandbox's answers are static, so some of these checks may fail there for
reasons that are not the bot's: see the comments at each one.

Run where the sandbox is reachable (the sandbox-test workflow on GitHub Actions): python bot/spot/sandbox_test.py
Exit code 0 = every check passed.
"""
import os
import sys
import traceback

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))      # repo root, for `from edge import wick`
sys.path.insert(0, HERE)
from engine import LiveBroker, Spec  # noqa: E402

HEADER = {}
_orig = requests.sessions.Session.request


def _request(self, method, url, **kw):                 # add the X-Sandbox header (error simulation) to SDK requests
    h = dict(kw.pop("headers", None) or {})
    h.update(HEADER)
    return _orig(self, method, url, headers=h, **kw)


requests.sessions.Session.request = _request


def broker():
    from coinbase.rest import RESTClient
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())         # throwaway key: the sandbox needs no auth, the SDK signs anyway
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                            serialization.NoEncryption()).decode()
    b = LiveBroker.__new__(LiveBroker)
    b.c = RESTClient(api_key="organizations/sandbox/apiKeys/sandbox", api_secret=pem,
                     base_url="api-sandbox.coinbase.com", timeout=10)                # as LiveBroker builds it
    b.count_usdc = False
    return b


def batch_broker():
    """A broker with clients built as the batch path builds them: limit headers on, a factory, three threads."""
    from coinbase.rest import RESTClient
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                            serialization.NoEncryption()).decode()

    def make():
        return RESTClient(api_key="organizations/sandbox/apiKeys/sandbox", api_secret=pem,
                          base_url="api-sandbox.coinbase.com", timeout=10, rate_limit_headers=True)
    return LiveBroker(client=make(), client_factory=make, order_path="batch", orders_rate=10, place_workers=3)


RESULTS = []


def check(name, fn, ok):
    try:
        out = fn()
        good = bool(ok(out))
        RESULTS.append((name, good))
        print(f"{'PASS' if good else 'FAIL'}  {name}: {str(out)[:300]}")
        return out
    except Exception:
        RESULTS.append((name, False))
        print(f"FAIL  {name}: exception\n{traceback.format_exc()[-1500:]}")
        return None


STATUS_KEYS = {"filled", "avg", "fees", "status", "last_fill"}


def batch_checks(sp, end, order, known):
    """The batch path's requests and the shapes of their answers (README, "Order path")."""
    b = batch_broker()
    # snapshot: one list request filtered by order ids. Its shape is the dict status() returns. The static sandbox
    # may ignore the order_ids filter (any order it names but the bot did not ask for is dropped by the broker).
    check("batch: snapshot (list orders by ids) -> {id: the dict status() returns}", lambda: b.snapshot([known]),
          lambda o: isinstance(o, dict) and all(set(v) == STATUS_KEYS and isinstance(v["filled"], float)
                                                and isinstance(v["status"], str) for v in o.values()))
    # may fail on the sandbox if its static list answer does not name this static order
    check("batch: snapshot names the order it was asked for", lambda: b.snapshot([known]), lambda o: known in o)
    # cancel_many: one batch cancel, then reads until final or 2 s; the static order may never show a final status,
    # so only the shape is checked
    check("batch: cancel_many (batch cancel + reads) -> a (fill or None, confirmed) pair for the order",
          lambda: b.cancel_many([order(known)]),
          lambda o: isinstance(o, dict) and set(o) == {known} and isinstance(o[known], tuple) and len(o[known]) == 2
          and isinstance(o[known][1], bool))
    # best_bids: GET /best_bid_ask. The sandbox is documented for the Accounts and Orders endpoints only, so it may
    # answer 404 here: the broker then returns {} (never raises), which the first check accepts
    check("batch: best_bids (best bid/ask) -> {product: float}, never raises", lambda: b.best_bids(["BTC-USD"]),
          lambda o: isinstance(o, dict) and all(isinstance(v, float) and v > 0 for v in o.values()))
    check("batch: best_bids gives a bid for BTC-USD (may fail: the sandbox may not serve this endpoint)",
          lambda: b.best_bids(["BTC-USD"]), lambda o: "BTC-USD" in o)
    check("batch: place_many, one request -> [(order id, None)] as place() answers",
          lambda: b.place_many([(sp, "BUY", 50000.0, 0.001, True, end)]),
          lambda o: isinstance(o, list) and len(o) == 1 and o[0][0] is not None and o[0][1] is None)
    check("batch: place_many on three threads, each on its own client -> three answers in request order",
          lambda: b.place_many([(sp, "BUY", 50000.0 - k, 0.001, True, end) for k in range(3)]),
          lambda o: isinstance(o, list) and len(o) == 3 and all(x[0] is not None and x[1] is None for x in o))
    # may fail on the sandbox if it does not send the x-ratelimit headers (the production venue's documentation
    # says its answers carry them; the library copies them when rate_limit_headers=True)
    check("batch: the venue's rate-limit headers were seen", b.rate_limit,
          lambda o: isinstance(o, dict) and any(v is not None for v in o.values()))
    # the counters and any piece switched off are printed; a piece may switch off on the sandbox when its static
    # answers name none of the orders asked for (three such reads in a row)
    check("batch: no 429 from the sandbox (counters and switched-off pieces printed)",
          lambda: (b.take_counts(), b.take_trips()), lambda o: "http_429" not in o[0])


def main():
    b = broker()
    sp = Spec("BTC-USD", 0.01, 1e-8, 1.0)
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    end = now + pd.Timedelta(minutes=10)
    order = lambda oid: dict(id=oid, filled=0.0, value=0.0, fees=0.0, px=50000.0)   # noqa: E731

    check("balances (accounts)", b.balances, lambda o: isinstance(o, dict) and len(o) > 0 and
          all(isinstance(v, tuple) and len(v) == 2 for v in o.values()))
    check("cash", b.cash, lambda o: isinstance(o, float))
    check("open orders (list orders)", b.open_orders, lambda o: isinstance(o, list))
    oid_gtd = check("place: post-only good-til-date bid", lambda: b.place(sp, "BUY", 50000.0, 0.001, end_time=end),
                    lambda o: o[0] is not None and o[1] is None)
    check("place: post-only GTC take-profit sell", lambda: b.place(sp, "SELL", 60000.0, 0.001),
          lambda o: o[0] is not None and o[1] is None)
    oid = oid_gtd[0] if oid_gtd and oid_gtd[0] else "sandbox-order"
    # the sandbox's get-order mock answers only for its own static order ids (any other id -> 400 INVALID_ARGUMENT)
    known = check("a static order id from the sandbox (list orders)", lambda: b.open_orders()[0]["order_id"],
                  lambda o: isinstance(o, str) and len(o) > 0)
    check("status (get order)", lambda: b.status(known or oid),
          lambda o: isinstance(o["filled"], float) and isinstance(o["avg"], float) and isinstance(o["status"], str))
    check("increment from a status", lambda: b.increment(order(known or oid), b.status(known or oid)),
          lambda o: o is None or (len(o) == 3 and all(isinstance(x, float) for x in o)))
    check("fills (status per order)", lambda: b.fills("BTC", [("4", order(oid))], None, None, 0.01),
          lambda o: isinstance(o, list))
    check("cancel (batch cancel + status)", lambda: b.cancel(order(oid)),
          lambda o: isinstance(o, tuple) and len(o) == 2 and isinstance(o[1], bool))
    check("cancel_ids", lambda: b.cancel_ids([oid]) or True, lambda o: o is True)
    check("filled_order_ids (list fills, 1-second detection)", lambda: b.filled_order_ids(now - pd.Timedelta(hours=1)),
          lambda o: isinstance(o, set))
    check("preview good-til-date bid", lambda: b.preview_gtd(sp, 50000.0, 0.001, end), lambda o: isinstance(o, list))
    # the sandbox can't report the new order's status, so the sell comes back as pending (outcome unknown), with its
    # order id: the engine resolves it before any new sell instead of selling twice
    check("market sell with unreadable status -> pending with its order id", lambda: b.market_sell(sp, 0.001, 5e4, 5e4),
          lambda o: isinstance(o, tuple) and len(o) == 4 and o[0] is None and isinstance(o[3], dict)
          and bool(o[3].get("pending_order")))
    listed = b.open_orders()[0]
    check("find an order by its client id (a timed-out create may still have placed it)",
          lambda: b._find_by_client_id(listed["product_id"], listed.get("client_order_id"), tries=1),
          lambda o: o == listed["order_id"])

    batch_checks(sp, end, order, known or oid)

    HEADER["X-Sandbox"] = "PostOrder_insufficient_fund"
    check("place with insufficient funds -> rejected with the error text",
          lambda: b.place(sp, "BUY", 50000.0, 0.001, end_time=end),
          lambda o: o[0] is None and "INSUFFICIENT_FUND" in str(o[1]).upper())
    HEADER["X-Sandbox"] = "PreviewOrder_insufficient_fund"
    check("preview with insufficient funds -> error list", lambda: b.preview_gtd(sp, 50000.0, 0.001, end),
          lambda o: isinstance(o, list))
    HEADER["X-Sandbox"] = "CancelOrders_failure"
    check("cancel that fails -> no crash, unconfirmed unless the order is terminal", lambda: b.cancel(order(oid)),
          lambda o: isinstance(o, tuple) and len(o) == 2)
    bb = batch_broker()
    check("batch: cancel_many when the batch cancel fails -> no crash, a (fill, confirmed) pair per order",
          lambda: bb.cancel_many([order(known or oid)]),
          lambda o: isinstance(o, dict) and len(o) == 1 and all(isinstance(v, tuple) and len(v) == 2
                                                                and isinstance(v[1], bool) for v in o.values()))
    HEADER.pop("X-Sandbox")

    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)} of {len(RESULTS)} checks passed" + (f"; failed: {bad}" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
