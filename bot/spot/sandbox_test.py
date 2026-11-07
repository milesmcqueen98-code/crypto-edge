#!/usr/bin/env python3
"""Live-broker smoke test against Coinbase's Advanced Trade sandbox (https://api-sandbox.coinbase.com).

The sandbox returns static, production-format responses for the Accounts and Orders endpoints, with no auth and no
money. Every LiveBroker call the engine makes is sent through the official SDK exactly as live: create_order (good-til-
date bid), limit GTC sell, get_order, batch cancel, list orders, list fills, accounts, preview and market sell. The test
checks the requests are accepted and the responses parse into what the engine expects. The X-Sandbox header simulates
the documented errors (insufficient funds on create and preview, failed cancel).

Run where the sandbox is reachable (the sandbox-test workflow on GitHub Actions): python bot/spot/sandbox_test.py
Exit code 0 = every check passed.
"""
import os
import sys
import traceback

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
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
                     base_url="api-sandbox.coinbase.com")
    b.count_usdc = False
    return b


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
    st = check("status (get order)", lambda: b.status(oid),
               lambda o: isinstance(o["filled"], float) and isinstance(o["avg"], float) and isinstance(o["status"], str))
    check("fills (status per order)", lambda: b.fills("BTC", [("4", order(oid))], None, None, 0.01),
          lambda o: isinstance(o, list))
    check("cancel (batch cancel + status)", lambda: b.cancel(order(oid)),
          lambda o: isinstance(o, tuple) and len(o) == 2 and isinstance(o[1], bool))
    check("cancel_ids", lambda: b.cancel_ids([oid]) or True, lambda o: o is True)
    check("filled_order_ids (list fills, 1-second detection)", lambda: b.filled_order_ids(now - pd.Timedelta(hours=1)),
          lambda o: isinstance(o, set))
    check("preview good-til-date bid", lambda: b.preview_gtd(sp, 50000.0, 0.001, end), lambda o: isinstance(o, list))
    check("market sell", lambda: b.market_sell(sp, 0.001, 50000.0, 50000.0),
          lambda o: isinstance(o, tuple) and len(o) == 4)

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
    HEADER.pop("X-Sandbox")

    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)} of {len(RESULTS)} checks passed" + (f"; failed: {bad}" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
