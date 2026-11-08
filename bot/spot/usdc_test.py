#!/usr/bin/env python3
"""Test of the quote option (ladder v5, C4) in LiveBroker, against a recording fake of the Coinbase SDK client.

With quote "USD" (the default) every call must be exactly as before: orders on {coin}-USD, cash = available USD (plus
USDC only with count_usdc_as_cash). With quote "USDC" every order call (GTD and GTC post-only bids and sells, previews,
market sells, the client-id lookup after a timeout) must go to the {coin}-USDC alias, and cash must be the available
USDC alone. Market data and the bot's specs stay on the -USD book. No network.

Usage: python bot/spot/usdc_test.py
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from bot.spot import engine as E  # noqa: E402


class FakeClient:
    def __init__(self, fail_create=False):
        self.calls, self.fail_create = [], fail_create

    def _rec(self, name, **kw):
        self.calls.append((name, kw.get("product_id") or (kw.get("product_ids") or [None])[0]))

    def create_order(self, **kw):
        self._rec("create_order", **kw)
        if self.fail_create:
            raise TimeoutError("read timed out")
        return {"success": True, "success_response": {"order_id": "o1"}}

    def limit_order_gtc_buy(self, **kw):
        self._rec("limit_order_gtc_buy", **kw)
        return {"success": True, "success_response": {"order_id": "o2"}}

    def limit_order_gtc_sell(self, **kw):
        self._rec("limit_order_gtc_sell", **kw)
        return {"success": True, "success_response": {"order_id": "o3"}}

    def preview_order(self, **kw):
        self._rec("preview_order", **kw)
        return {"errs": []}

    def market_order_sell(self, **kw):
        self._rec("market_order_sell", **kw)
        return {"success": True, "success_response": {"order_id": "o4"}}

    def get_order(self, oid):
        return {"order": {"filled_size": "1", "average_filled_price": "100", "total_fees": "0.1", "status": "FILLED"}}

    def list_orders(self, **kw):
        self._rec("list_orders", **kw)
        return {"orders": [{"client_order_id": "none", "order_id": "x"}]}

    def get_accounts(self, limit=250):
        return {"accounts": [
            {"currency": "USD", "available_balance": {"value": "1000"}, "hold": {"value": "50"}},
            {"currency": "USDC", "available_balance": {"value": "250000"}, "hold": {"value": "20000"}}]}


def run():
    sp = E.Spec("SOL-USD", 0.01, 0.001)
    end = pd.Timestamp("2026-11-08 12:00")
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        print(f"{'ok  ' if good else 'FAIL'} {name}: {got}" + ("" if good else f" (want {want})"))

    for quote, prod in (("USD", "SOL-USD"), ("USDC", "SOL-USDC")):
        fc = FakeClient()
        br = E.LiveBroker(quote=quote, client=fc)
        br.place(sp, "BUY", 100.0, 1.0, end_time=end)              # good-til-date entry bid
        br.place(sp, "BUY", 100.0, 1.0)                            # good-til-cancelled bid
        br.place(sp, "SELL", 120.0, 1.0)                           # take-profit / passive sell
        br.preview_gtd(sp, 100.0, 1.0, end)
        import time as _t
        sleep, _t.sleep = _t.sleep, (lambda s: None)
        try:
            br.market_sell(sp, 1.0, 110.0, 0.1)
        finally:
            _t.sleep = sleep
        check(f"quote {quote}: products of every order call", sorted({p for _, p in fc.calls}), [prod])
        check(f"quote {quote}: the bot's spec stays on the -USD book", sp.product, "SOL-USD")
        fc2 = FakeClient(fail_create=True)
        br2 = E.LiveBroker(quote=quote, client=fc2)
        br2.place(sp, "BUY", 100.0, 1.0, end_time=end)
        check(f"quote {quote}: client-id lookup after a timeout", [p for n, p in fc2.calls if n == "list_orders"][:1],
              [prod])
    check("quote USD: cash = available USD", E.LiveBroker(quote="USD", client=FakeClient()).cash(), 1000.0)
    check("quote USD + count_usdc_as_cash: cash = USD + USDC",
          E.LiveBroker(count_usdc=True, quote="USD", client=FakeClient()).cash(), 251000.0)
    b = E.LiveBroker(quote="USDC", client=FakeClient())
    check("quote USDC: cash = available USDC only", b.cash(), 250000.0)
    check("quote USDC: USDC for the rewards check (available + on hold)", b.last_usdc, 270000.0)
    try:
        E.LiveBroker(quote="EUR", client=FakeClient())
        check("an unknown quote is refused", False, True)
    except ValueError:
        check("an unknown quote is refused", True, True)
    print("USDC QUOTE TEST", "PASSED" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
