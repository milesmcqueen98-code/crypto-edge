#!/usr/bin/env python3
"""Live-path test: the engine in live mode against a fake Coinbase exchange driven by historical candles.

The fake exchange keeps real balances and holds:
- It rejects post-only orders that would cross, and orders the cash can't cover.
- It fills resting orders from the candles (one-tick trade-through, half the volume beyond the price).
- It injects faults: 5% of cancels go unconfirmed, 15% of market sells fill only half, 10% of market sells execute
  with an outcome that cannot be read for two minutes, and 5% of take-profit placements fail with a server error.
- Entry bids are good-til-date; the fake exchange expires them and demands at least 400 s (the bot must adapt).
- The server "dies" for 20 minutes in the middle of the crash (--death): every bid must have expired by itself, and a
  fresh process must pick up the state, book what filled meanwhile and run the overdue exits.

Checks:
- nothing crashes;
- no orphan orders;
- once every rung has closed, the coin balances are back to zero;
- the bot's equity equals the exchange's USD balance (every fill booked exactly once).

Usage: python bot/spot/live_sim_test.py "2025-10-10 20:00" "2025-10-11 02:00" "--death=2025-10-10 21:10"
       [--config=path/to/config.json]   (default bot/spot/config.json; its input settings are not used: history has
                                         no trades list, so the run is on final candles)
"""
import os
import random
import sys
import tempfile
import time
import uuid

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot.spot import engine as E  # noqa: E402
from bot.spot.replay_test import H, ReplayMarket  # noqa: E402


class LiveReplayMarket(ReplayMarket):
    def __init__(self, start, end, clock):
        super().__init__(start, end)
        self.clock = clock

    def last(self, coin):
        d = self.D[coin]
        i = d.index.searchsorted(self.clock().floor("min")) - 1
        return float(d.close.iloc[i]) if i >= 0 else np.nan

    def best_bid(self, product):
        c = product.split("-")[0]
        return self.last(c) - self.ticks[c] / 2

    def bids_ahead(self, product, px):
        return 0.0, True


class FakeExchange:
    live = True
    TERMINAL = E.LiveBroker.TERMINAL
    increment = staticmethod(E.LiveBroker.increment)

    def __init__(self, mkt, clock, usd, capture=0.5, p_cancel_fail=0.05, p_partial=0.15, seed=7, min_gtd_s=400,
                 p_sell_unknown=0.10, p_tp_error=0.05):
        self.mkt, self.clock, self.usd, self.coin, self.orders = mkt, clock, usd, {}, {}
        self.capture, self.pcf, self.pp = capture, p_cancel_fail, p_partial
        self.fm, self.ft = 6e-4, 12.5e-4
        self.rng = random.Random(seed)
        self.min_gtd = pd.Timedelta(seconds=min_gtd_s)
        self.p_sell_unknown, self.p_tp_error, self.unreadable = p_sell_unknown, p_tp_error, {}
        self.n = dict(cancel_unconfirmed=0, partial_sell=0, post_only_reject=0, funds_reject=0, fills=0, expired=0,
                      duration_reject=0, sell_unknown=0, tp_error=0)

    # ---- matching
    def _advance(self):
        now = self.clock()
        for o in self.orders.values():
            while o["status"] == "OPEN" and o["next"] < now.floor("min"):
                if o["expires"] is not None and o["next"] >= o["expires"]:
                    break
                self._fill_minute(o, o["next"])
                o["next"] += pd.Timedelta(minutes=1)
            if o["status"] == "OPEN" and o["expires"] is not None and now >= o["expires"]:
                o["status"] = "EXPIRED"
                self.n["expired"] += 1

    def _fill_minute(self, o, m):
        c, d = o["coin"], self.mkt.D[o["coin"]]
        if m not in d.index:
            return
        b = d.loc[m]
        if not b.volume > 0:
            return
        tick, rng, px = self.mkt.ticks[c], b.high - b.low, o["px"]
        if o["side"] == "BUY":
            if b.low > px - tick * (1 - 1e-9):
                return
            frac = 1.0 if rng <= 0 else min(1.0, (px - b.low) / rng)
        else:
            if b.high < px + tick * (1 - 1e-9):
                return
            frac = 1.0 if rng <= 0 else min(1.0, (b.high - px) / rng)
        q = min(o["size"] - o["filled"], self.capture * b.volume * frac)
        if q <= 0:
            return
        fee = q * px * self.fm
        o["filled"] += q
        o["value"] += q * px
        o["fees"] += fee
        self.n["fills"] += 1
        if o["side"] == "BUY":
            self.usd -= q * px + fee
            self.coin[c] = self.coin.get(c, 0.0) + q
        else:
            self.usd += q * px - fee
            self.coin[c] -= q
        o["last_fill"] = m
        if o["filled"] >= o["size"] - 1e-12:
            o["status"] = "FILLED"

    def _avail_usd(self):
        return self.usd - sum((o["size"] - o["filled"]) * o["px"] * (1 + self.fm) for o in self.orders.values()
                              if o["status"] == "OPEN" and o["side"] == "BUY")

    def _avail_coin(self, c):
        return self.coin.get(c, 0.0) - sum(o["size"] - o["filled"] for o in self.orders.values()
                                           if o["status"] == "OPEN" and o["side"] == "SELL" and o["coin"] == c)

    # ---- the LiveBroker interface
    def place(self, spec, side, px, size, post_only=True, end_time=None):
        self._advance()
        if end_time is not None and pd.Timestamp(end_time) - self.clock() < self.min_gtd:
            self.n["duration_reject"] += 1
            return None, '{"error": "INVALID_END_TIME", "preview_failure_reason": "DURATION_TOO_SMALL"}'
        c = spec.product.split("-")[0]
        if side == "SELL" and self.rng.random() < self.p_tp_error:          # a transient server error, nothing placed
            self.n["tp_error"] += 1
            return None, 'HTTPError("503 Server Error: Service Unavailable")'
        last = self.mkt.last(c)
        if post_only and ((side == "BUY" and px >= last) or (side == "SELL" and px <= last)):
            self.n["post_only_reject"] += 1
            return None, '{"error": "INVALID_LIMIT_PRICE_POST_ONLY"}'
        if (side == "BUY" and size * px * (1 + self.fm) > self._avail_usd() + 1e-6) or \
                (side == "SELL" and size > self._avail_coin(c) + 1e-9):
            self.n["funds_reject"] += 1
            return None, '{"error": "INSUFFICIENT_FUND"}'
        oid = uuid.uuid4().hex
        self.orders[oid] = dict(coin=c, side=side, px=px, size=size, filled=0.0, value=0.0, fees=0.0, status="OPEN",
                                next=self.clock().floor("min"), client_order_id=f"{E.ORDER_TAG}-{oid[:8]}",
                                expires=None if end_time is None else pd.Timestamp(end_time))
        return oid, None

    def status(self, oid):
        self._advance()
        if self.unreadable.get(oid, 0) > 0:                 # a market sell whose status can't be read yet
            self.unreadable[oid] -= 1
            raise RuntimeError("HTTP 503 get_order")
        o = self.orders[oid]
        return dict(filled=o["filled"], avg=o["value"] / o["filled"] if o["filled"] else 0.0, fees=o["fees"],
                    status=o["status"], last_fill=None)

    def fills(self, coin, orders, bar, minute, tick):
        out = []
        for r, o in orders:
            s = self.status(o["id"])
            inc, done = self.increment(o, s), s["status"] in self.TERMINAL
            if inc:
                out.append((r, inc[0], inc[1], inc[2], done))
            elif done:
                out.append((r, 0.0, o["px"], 0.0, True))
        return out

    def cancel(self, order):
        self._advance()
        o = self.orders[order["id"]]
        if o["status"] == "OPEN":
            if self.rng.random() < self.pcf:
                self.n["cancel_unconfirmed"] += 1
                return self.increment(order, self.status(order["id"])), False
            o["status"] = "CANCELLED"
        return self.increment(order, self.status(order["id"])), True

    def filled_order_ids(self, since):
        self._advance()
        cut = pd.Timestamp(since).floor("min") - pd.Timedelta(minutes=1)
        return {k for k, o in self.orders.items() if o.get("last_fill") is not None and o["last_fill"] >= cut}

    def cancel_ids(self, ids):
        for i in ids:
            if self.orders.get(i, {}).get("status") == "OPEN":
                self.orders[i]["status"] = "CANCELLED"

    def market_sell(self, spec, size, ref_px, cost_px):
        self._advance()
        c = spec.product.split("-")[0]
        if size > self._avail_coin(c) + 1e-9:
            return None, None, 0.0, "INSUFFICIENT_FUND"
        q = size * (0.5 if self.rng.random() < self.pp else 1.0)
        self.n["partial_sell"] += int(q < size)
        px = ref_px - cost_px
        fee = q * px * self.ft
        self.usd += q * px - fee
        self.coin[c] -= q
        if self.rng.random() < self.p_sell_unknown:        # executed, but the outcome can't be read for ~2 minutes
            self.n["sell_unknown"] += 1
            oid = uuid.uuid4().hex
            self.orders[oid] = dict(coin=c, side="SELL", px=px, size=size, filled=q, value=q * px, fees=fee,
                                    status="FILLED" if q >= size * 0.999 else "CANCELLED", next=self.clock().floor("min"),
                                    client_order_id=f"{E.ORDER_TAG}-{oid[:8]}", expires=None, market=True)
            self.unreadable[oid] = 2
            return None, None, 0.0, {"pending_order": oid, "status": None}
        return px, fee, q, (None if q >= size * 0.999 else f"partial: {q} of {size}")

    def cash(self):
        self._advance()
        return self._avail_usd()

    def balances(self):
        self._advance()
        out = {"USD": (self._avail_usd(), self.usd - self._avail_usd())}
        for c, b in self.coin.items():
            out[c] = (self._avail_coin(c), b - self._avail_coin(c))
        return out

    def open_orders(self):
        return [dict(order_id=k, client_order_id=v["client_order_id"], product_id=v["coin"] + "-USD", side=v["side"])
                for k, v in self.orders.items() if v["status"] == "OPEN"]

    def fee_tier(self):
        return dict(tier="fake VIP 1", maker_bp=6.0, taker_bp=12.5, volume_30d=None)


def main(start, end, death=None, death_min=20, config=None):
    clock = {"t": pd.Timestamp(start)}
    now = lambda: clock["t"] + pd.Timedelta(seconds=6)  # noqa: E731
    mkt = LiveReplayMarket(start, end, now)
    cap = 250000.0
    ex = FakeExchange(mkt, now, cap)
    import json
    cfg = json.load(open(config or os.path.join(HERE, "config.json")))
    cfg.update(capital=cap, usd_reserve=0.0)
    # stored history has no trades list: this replay runs on final candles, whatever the config's inputs are
    cfg.update(newest_bar="candles", stale_guard=False)
    cfg.pop("trades_coins", None)
    sd = tempfile.mkdtemp(prefix="spot_live_")
    eng = E.Engine(mode="live", cfg=cfg, state_dir=sd, market=mkt, broker=ex, clock=now, echo=False)
    t0 = time.time()
    eng.start()
    steps = pd.date_range(start, pd.Timestamp(end) + pd.Timedelta(minutes=3 * H), freq="min", inclusive="left")
    dead_until, death_ok = None, None
    for t in steps:
        if death is not None and t == pd.Timestamp(death):
            dead_until = t + pd.Timedelta(minutes=death_min)
            open_buys = sum(1 for o in ex.orders.values() if o["status"] == "OPEN" and o["side"] == "BUY")
            print(f"server dies at {t} with {open_buys} resting bids and {len(eng.ladders())} ladders")
        if dead_until is not None:
            if t < dead_until:
                continue                                   # no process running: the exchange keeps going
            clock["t"] = t
            ex._advance()
            left = [o for o in ex.orders.values() if o["status"] == "OPEN" and o["side"] == "BUY"]
            death_ok = not left
            print(f"back at {t}: {len(left)} bids still resting on the exchange (should be 0); "
                  f"{sum(1 for o in ex.orders.values() if o['status'] == 'OPEN')} take-profits resting")
            eng = E.Engine(mode="live", cfg=cfg, state_dir=sd, market=mkt, broker=ex, clock=now, echo=False)
            if t >= pd.Timestamp(end):
                eng.tradable = []
            eng.start()                                    # a fresh process: reconcile, book fills, overdue exits
            dead_until = None
        if t == pd.Timestamp(end):
            eng.tradable = []
        clock["t"] = t
        eng.step(t)
        clock["t"] = t + pd.Timedelta(seconds=30)
        eng.fast_poll()
        if t > pd.Timestamp(end) + pd.Timedelta(minutes=2 * H + 5) and not eng.ladders():
            break
    ev = pd.read_json(os.path.join(sd, "events.jsonl"), lines=True)
    ent, ext = ev[ev.kind == "fill_entry"], ev[ev.kind == "fill_exit"]
    print(f"{len(steps)} minutes in {time.time() - t0:.0f}s; events {sd}")
    print(f"entries {len(ent)} (${ent.usd.sum():,.0f}), exits {len(ext)}, P&L ${ext.pnl.sum():,.2f}; exchange: {ex.n}")
    print("event kinds:", ev.kind.value_counts().to_dict())
    open_ex = ex.open_orders()
    coins_left = {c: b for c, b in ex.coin.items() if abs(b) * mkt.last(c) > 0.01}
    ok = True
    if eng.ladders():
        ok = False
        print("FAIL: ladders still open:", [l["id"] for l in eng.ladders()])
    if open_ex:
        ok = False
        print("FAIL: orders still open on the exchange:", open_ex[:5])
    if coins_left:
        ok = False
        print("FAIL: coin balances left:", coins_left)
    diff = eng.state["equity"] - ex.usd
    print(f"bot equity ${eng.state['equity']:,.4f} vs exchange USD ${ex.usd:,.4f} (difference ${diff:,.6f})")
    if abs(diff) > 0.01:
        ok = False
        print("FAIL: the bot's books and the exchange disagree")
    if death is not None and not death_ok:
        ok = False
        print("FAIL: bids outlived the dead server")
    print(f"good-til-date duration the bot settled on: {eng.ttl} s (fake exchange minimum 400 s)")
    errs = ev[ev.kind == "error"]
    if len(errs):
        print("errors logged (expected only from injected faults):")
        print(errs.error.astype(str).str[:120].value_counts().head(10).to_string())
    print("LIVE-PATH TEST", "PASSED" if ok else "FAILED")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    d = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--death=")), None)
    cf = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--config=")), None)
    main(a[0], a[1], death=d, config=cf)
