#!/usr/bin/env python3
"""Test of the order check (bot/spot/order_check.py, `run.py order-check`) against the scripted venue of
bot/spot/order_path_unit_test.py. No network, no real wait.

Cases: every part with --place-test-orders (three bids at half the best bid, previewed, placed with one place_many,
read, cancelled, the JSON file); the read-only path without the flag (nothing previewed, placed or cancelled); a
product whose preview has errors (skipped, the other two placed); an order that stays open after cancel_many and is
cancelled singly in the clean-up (FAILED, nothing left open); an order the clean-up cannot cancel (FAILED, loudly);
the plan text and run.py's print-only and live-switch paths.

Usage: python bot/spot/order_check_test.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import pandas as pd  # noqa: E402

from bot.spot import engine as E  # noqa: E402
from bot.spot import order_check as OC  # noqa: E402
from bot.spot.order_path_unit_test import Client, Clock, NoSleep, Venue, methods  # noqa: E402

FAILS = []
COINS = ["ETH", "SOL", "XRP", "DOGE"]
BIDS = {"ETH-USD": 2500.0, "SOL-USD": 200.0, "XRP-USD": 2.5, "DOGE-USD": 0.25}
CFG = dict(orders_rate=10, place_workers=3, bid_ttl_s=600)
NOW = pd.Timestamp("2026-11-14 12:00:00")


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""), flush=True)
    if not ok:
        FAILS.append(name)


class Market:
    """The public market data: best bids 1 bp under the venue's batch answer, specs."""

    def best_bid(self, p):
        return BIDS[p] * (1 - 1e-4)

    def spec(self, c):
        return E.Spec(f"{c}-USD", 0.01 if c != "DOGE" else 1e-5, 1e-8, 1.0)


def setup():
    ck = Clock()
    v = Venue(ck)
    v.bids = dict(BIDS)
    b = E.LiveBroker(client=Client(v), client_factory=lambda: Client(v, name="w"), order_path="batch",
                     place_workers=3)
    b.sleep, b.mono = ck.sleep, ck.now
    return ck, v, b


def go(place, v, b, ck, d):
    lines = []
    with NoSleep(ck):
        r = OC.run(b, Market(), COINS, CFG, place, d, say=lines.append, clock=ck.now, now=lambda: NOW)
    return r, lines


def main():
    d = tempfile.mkdtemp(prefix="order_check_")
    try:
        # every part
        ck, v, b = setup()
        r, out = go(True, v, b, ck, d)
        k = methods(v)
        pl = r.get("placed", [])
        check("all parts: PASSED, then the closing line: the batch path from the next start",
              r["passed"] and out[-2] == "order check PASSED"
              and out[-1] == "The bot uses the batch order path from its next start (wickctl start).", str(out[-2:]))
        check("all parts: the plan printed first, naming the flag and the bot's tag",
              "ONLY WITH --place-test-orders" in out[0] and "wk1m-" in out[0])
        check("all parts: best_bids five times, every product with a bid; the public book 1 bp off for ETH, SOL, XRP",
              k.count("get_best_bid_ask") == 5 and [x["products"] for x in r["best_bids"]["runs"]] == [4] * 5
              and all(abs(x["diff_bp"] - 1.0) < 0.01 for x in r["best_bids"]["compare"].values())
              and list(r["best_bids"]["compare"]) == ["ETH-USD", "SOL-USD", "XRP-USD"], str(r["best_bids"]))
        low = [E.floor_to(0.5 * min(BIDS[p], Market().best_bid(p)), 0.01) for p in ("ETH-USD", "SOL-USD", "XRP-USD")]
        check("all parts: three bids, ETH, SOL, XRP, at half the lower of the batch and the public best bid (here the "
              "public one) floored to the tick, about $25 each, previewed first, sent with one place_many",
              [p["product"] for p in pl] == ["ETH-USD", "SOL-USD", "XRP-USD"]
              and [p["px"] for p in pl] == low and all(abs(x - y) < 1e-9 for x, y in zip(low, [1249.87, 99.99, 1.24]))
              and all(24.9 < p["px"] * p["size"] <= 25.0 + 1e-6 for p in pl) and k.count("preview_order") == 3
              and k.count("create_order") == 3 and k.index("preview_order") < k.index("create_order"), str(pl))
        check("all parts: lifetime bid_ttl_s (600 s)", all(p["end"] == str(NOW + pd.Timedelta(seconds=600)) for p in pl))
        check("all parts: the snapshot names all three and equals the single reads; cancel_many confirms each at the "
              "first read", r["read"]["missing"] == [] and r["read"]["differing_fields"] == {}
              and all(x["confirmed"] and x["seen_final_at_s"] == 0.0 for x in r["cancel"].values())
              and r["still_open"] == [], str(r.get("cancel")))
        check("all parts: nothing left open on the venue", not [o for o in v.orders.values() if o["status"] == "OPEN"])
        js = json.load(open(r["file"]))
        check("all parts: the JSON file next to the state, named in the output, with the result",
              os.path.dirname(r["file"]) == d and js["passed"] is True and any(r["file"] in x for x in out)
              and set(js["requests"]) >= {"get_best_bid_ask", "create_order", "cancel_orders", "list_orders"},
              str(js.get("requests")))

        # without the flag
        ck, v, b = setup()
        r, out = go(False, v, b, ck, d)
        k = methods(v)
        check("no flag: the plan and the read-only parts only (best bids), nothing previewed, placed or cancelled",
              r["passed"] and set(k) == {"get_best_bid_ask"} and "placed" not in r
              and any("skipped: no --place-test-orders" in x for x in out), str(set(k)))
        check("no flag: PASSED, then the closing line: read-only, the serial path stays",
              out[-2] == "order check PASSED" and out[-1] == "Read-only run: the bot keeps the serial path until a "
              "run with test orders passes.", str(out[-2:]))

        # a product whose preview has errors
        ck, v, b = setup()
        v.script["preview_order"] = [None, lambda kw: {"errs": [{"preview_failure_reason": "TEST"}]}, None]
        r, out = go(True, v, b, ck, d)
        check("preview errors: that product skipped (noted), the other two placed and cancelled, PASSED",
              r["passed"] and [p["product"] for p in r["placed"]] == ["ETH-USD", "XRP-USD"]
              and any("SOL-USD: skipped" in n for n in r["notes"]), str(r["notes"]))

        # the batch best bid disagrees with the public book, or is missing: that product skipped, the check FAILS
        ck, v, b = setup()
        v.bids["SOL-USD"] = 2 * BIDS["SOL-USD"]        # twice the public book's
        del v.bids["XRP-USD"]                          # no batch bid at all
        r, out = go(True, v, b, ck, d)
        made = [c[2]["product_id"] for c in v.calls if c[1] == "create_order"]
        check("bids that disagree (batch twice the public) or a missing batch bid: both skipped and named, nothing "
              "placed for them, ETH placed, FAILED", not r["passed"] and made == ["ETH-USD"]
              and any("SOL-USD: skipped" in x and "differ by more than 5%" in x for x in r["reasons"])
              and any("XRP-USD: skipped, no batch best bid" in x for x in r["reasons"])
              and [p["product"] for p in r["placed"]] == ["ETH-USD"], str(r["reasons"]))
        check("FAILED: the final line says so, then the closing line: the serial path stays",
              out[-2].startswith("order check FAILED: ") and out[-1] == "The bot keeps the serial path.",
              str(out[-2:]))

        # a placement reported as failed whose order rests at the venue: found by the sweep; a bot bid left alone
        ck, v, b = setup()
        v.add("botbid", product="SOL-USD", cid="wk1m-livebot")     # a running bot's bid, at its own level
        v.orders["botbid"]["order_configuration"] = {"limit_limit_gtd": {"limit_price": "180.00"}}
        orig = Client._new

        def lost(self, kw, m):                         # SOL: the venue keeps the order, the answer is lost
            if kw.get("product_id") == "SOL-USD" and m == "create_order":
                orig(self, dict(kw, client_order_id="wk1m-under-another-id"), m)
                raise RuntimeError("read timed out")
            return orig(self, kw, m)
        Client._new = lost
        try:
            r, out = go(True, v, b, ck, d)
        finally:
            Client._new = orig
        lost_ids = [i for i, o in v.orders.items() if o["client_order_id"] == "wk1m-under-another-id"]
        check("sweep: a placement reported as failed whose order rests at the venue -> found by the one open-orders "
              "read, cancelled singly, read again, reported; FAILED",
              not r["passed"] and r["sweep"]["found"] == lost_ids and v.orders[lost_ids[0]]["status"] == "CANCELLED"
              and any("d. sweep: a lost test order" in x for x in out), str(r.get("sweep")))
        check("sweep: a bot bid at another price on the same product is left alone",
              v.orders["botbid"]["status"] == "OPEN" and "botbid" not in r["sweep"]["found"])
        ck, v, b = setup()
        b.open_orders = lambda: (_ for _ in ()).throw(RuntimeError("503"))
        r, out = go(True, v, b, ck, d)
        check("sweep: the open-orders read fails -> said so (the sweep could not run)",
              str(r.get("sweep", "")).startswith("could not run") and any("sweep for lost test orders could not run"
                                                                          in x for x in out), str(r.get("sweep")))

        # an order that stays open after cancel_many: cancelled singly in the clean-up
        ck, v, b = setup()
        noop = lambda kw: {"results": [dict(success=True, order_id=i) for i in kw["order_ids"]]}  # noqa: E731
        v.script["cancel_orders"] = [noop]             # the batch cancel does nothing; the single ones work
        r, out = go(True, v, b, ck, d)
        check("open after cancel_many: FAILED for it, then each cancelled singly and read again; none left open",
              not r["passed"] and r["still_open"] == [] and all("did not confirm" in x for x in r["reasons"])
              and len(r["reasons"]) == 3 and sum("clean-up" in x for x in out) == 3
              and not [o for o in v.orders.values() if o["status"] == "OPEN"], str(r["reasons"]))

        # an order the clean-up cannot cancel either: said loudly
        ck, v, b = setup()
        v.script["cancel_orders"] = [noop] * 10
        r, out = go(True, v, b, ck, d)
        loud = [x for x in out if x.startswith("!!!!! TEST ORDER STILL OPEN")]
        check("clean-up fails: FAILED, every one named loudly with its end time", not r["passed"]
              and len(r["still_open"]) == 3 and len(loud) == 3 and all("expires by itself" in x for x in loud)
              and any("still open" in x for x in r["reasons"]), str(loud[:1]))

        # run.py: the plan only, and the live switch
        cfgp = os.path.join(d, "cfg.json")
        json.dump(dict(CFG, capital=1000), open(cfgp, "w"))
        env = {k: v_ for k, v_ in os.environ.items() if k not in ("I_UNDERSTAND_LIVE_TRADING",)}
        p = subprocess.run([sys.executable, os.path.join(HERE, "run.py"), "order-check", "--print-plan", "--config",
                            cfgp], cwd=ROOT, capture_output=True, text=True, env=env)
        check("run.py order-check --print-plan: the plan, exit 0, no keys needed",
              p.returncode == 0 and p.stdout.strip() == OC.plan(dict(CFG, capital=1000)), p.stderr[-300:])
        p = subprocess.run([sys.executable, os.path.join(HERE, "run.py"), "order-check", "--place-test-orders",
                            "--config", cfgp], cwd=ROOT, capture_output=True, text=True,
                           env=dict(env, COINBASE_API_KEY="k", COINBASE_API_SECRET="s"))
        check("run.py order-check --place-test-orders without I_UNDERSTAND_LIVE_TRADING=yes: stops before anything",
              p.returncode != 0 and "I_UNDERSTAND_LIVE_TRADING" in p.stderr, p.stderr[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
    print("ORDER CHECK TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
