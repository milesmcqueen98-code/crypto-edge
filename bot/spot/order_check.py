"""The batch order path's requests against the real venue, run by the account owner before the bot relies on them
(bot/spot/README.md, "Order path"): python bot/spot/run.py order-check [--place-test-orders], or wickctl order-check.

Without --place-test-orders it prints the plan and runs only the read-only parts (a, b, e). With it, it also places
three tiny post-only bids far below the market and cancels them (c, d). The result is printed and written as one JSON
file next to the live state. Standard library only, besides the engine (Python 3.8 and later).
"""
import json
import math
import os
import statistics
import time

import pandas as pd

from bot.spot import engine as E

PREFER = ("ETH", "SOL", "XRP")
TEST_USD = 25.0
AGREE = 0.05                                           # the batch and the public best bid must agree this closely
PLAN = """order check: the batch order path's requests against Coinbase (bot/spot/README.md, "Order path")
  a. build the broker as the bot's batch path does (orders_rate {rate}, place_workers {workers}); print the library
     version
  b. best bids of every coin's product, five times: how many came back, how long each request took, and for three
     products the difference to the public book's best bid (read-only)
  c. ONLY WITH --place-test-orders: three real post-only good-til-date bids (ETH, SOL, XRP when tradable, else the
     first three tradable coins), each about ${usd:.0f} at half the lower of the batch and the public best bid (far
     below the market: they should not fill; a product whose two bids are missing or differ by more than 5% is
     skipped and fails the check), each previewed first (a product whose preview has errors is skipped), lifetime
     bid_ttl_s ({ttl} s), sent with one place_many
  d. ONLY WITH --place-test-orders: read them with one snapshot and singly, compare; cancel them with cancel_many
     and record when each was seen cancelled; then cancel singly any test order not confirmed cancelled and read it
     again; then one read of the open orders, to cancel a test bid whose placement came back as an error (the bot's
     tag, a test product, the test bid's price; an order still open expires by itself at its end time)
  e. the rate-limit headers seen, the median time by kind of request, and a final line PASSED or FAILED; the whole
     result as one JSON file next to the live state
  The test orders carry the bot's client order id tag ({tag}-): a running bot's reconcile sweep would cancel them
  too, and its requests share the account's rate limit. wickctl order-check refuses to start while the bot's
  service runs (stop it with wickctl stop); run.py order-check run by hand does not check that."""


def plan(cfg):
    return PLAN.format(rate=cfg.get("orders_rate", 10), workers=cfg.get("place_workers", 1), usd=TEST_USD,
                       ttl=int(cfg.get("bid_ttl_s", 300) or 300), tag=E.ORDER_TAG)


class Timed:
    """A client whose every call is timed and recorded as (method, seconds)."""

    def __init__(self, c, log, clock):
        self._c, self._log, self._clock = c, log, clock

    def __getattr__(self, name):
        f = getattr(self._c, name)
        if not callable(f):
            return f

        def g(*a, **k):
            t0 = self._clock()
            try:
                return f(*a, **k)
            finally:
                self._log.append((name, self._clock() - t0))
        return g


def _eq(a, b):
    """Two status() dicts equal field by field (numbers to 1e-9 relative)."""
    diff = []
    for k in ("filled", "avg", "fees", "status", "last_fill"):
        x, y = a.get(k), b.get(k)
        if isinstance(x, float) and isinstance(y, float):
            if abs(x - y) > 1e-9 * max(abs(x), abs(y)):
                diff.append(k)
        elif x != y:
            diff.append(k)
    return diff


def run(broker, market, coins, cfg, place, out_dir, say=print, clock=time.monotonic, now=None):
    """The check. broker: a LiveBroker built for the batch path; market: the public market data (best_bid, spec);
    coins: the coins the bot may trade. Returns the result dict (also written as JSON in out_dir)."""
    now = now or (lambda: pd.Timestamp.now(tz="UTC").tz_localize(None))
    reqs = []
    broker.c = Timed(broker.c, reqs, clock)
    if broker.client_factory is not None:
        f = broker.client_factory
        broker.client_factory = lambda: Timed(f(), reqs, clock)
    res = dict(started=str(now()), place_test_orders=bool(place), reasons=[], notes=[])
    reasons = res["reasons"]
    say(plan(cfg))
    say("")
    # a.
    res["library"] = E.library_version()
    res["orders_rate"], res["place_workers"] = broker.orders_rate, broker.place_workers
    res["rate_headers_off"] = bool(getattr(broker, "rate_headers_off", False))
    say(f"a. library coinbase-advanced-py {res['library']}; orders_rate {broker.orders_rate}, place_workers "
        f"{broker.place_workers}" + ("; this library does not know rate_limit_headers" if res["rate_headers_off"]
                                     else ""))
    # b.
    prods = [f"{c}-USD" for c in coins]
    pick = [c for c in PREFER if c in coins]
    pick += [c for c in coins if c not in pick][:3 - len(pick)]
    runs, last = [], {}
    for _ in range(5):
        t0 = clock()
        last = broker.best_bids(prods)
        runs.append(dict(products=len(last), seconds=round(clock() - t0, 4)))
    cmp_ = {}
    for c in pick:
        p = f"{c}-USD"
        try:
            pub = float(market.best_bid(p))
        except Exception as err:
            pub = float("nan")
            res["notes"].append(f"public best bid of {p}: {err!r}"[:200])
        bb = last.get(p)
        cmp_[p] = dict(best_bids=bb, public=pub if math.isfinite(pub) else None,
                       diff_bp=round(1e4 * (bb / pub - 1), 2) if bb and math.isfinite(pub) and pub > 0 else None)
    res["best_bids"] = dict(asked=len(prods), runs=runs, median_s=statistics.median(r["seconds"] for r in runs),
                            compare=cmp_)
    say(f"b. best_bids for {len(prods)} products, five times: came back with a bid {[r['products'] for r in runs]}; "
        f"median request {res['best_bids']['median_s']:.3f} s")
    for p, x in cmp_.items():
        say(f"   {p}: best_bids {x['best_bids']}, public book {x['public']}, difference {x['diff_bp']} bp")
    if any(r["products"] == 0 for r in runs):
        reasons.append("best_bids came back without any bid")
    if any(cmp_[p]["best_bids"] is None for p in cmp_):
        reasons.append("best_bids had no bid for " + ", ".join(p for p in cmp_ if cmp_[p]["best_bids"] is None))
    # c. and d.
    placed = []
    if place:
        try:
            placed = _place(broker, market, pick, last, cfg, res, say, now)
            if placed:
                _read_and_cancel(broker, placed, res, say)
        except Exception as err:
            reasons.append(f"the check stopped: {err!r}"[:300])
            say(f"!! the check stopped: {err!r}"[:300])
        finally:
            _clean(broker, placed, res, say)
    else:
        say("c., d. skipped: no --place-test-orders (nothing placed)")
    # e.
    res["rate_limit"] = broker.rate_limit()
    kinds = {}
    for k, s in reqs:
        kinds.setdefault(k, []).append(s)
    res["requests"] = {k: dict(n=len(v), median_s=round(statistics.median(v), 4)) for k, v in sorted(kinds.items())}
    res["counts"], res["switched_off"] = broker.take_counts(), broker.take_trips()
    say(f"e. rate-limit headers seen: {res['rate_limit']}")
    for k, v in res["requests"].items():
        say(f"   {k}: {v['n']} requests, median {v['median_s']:.3f} s")
    if res["counts"] or res["switched_off"]:
        say(f"   counters {res['counts']}; switched off {res['switched_off']}")
    if res["switched_off"]:
        reasons.append("pieces switched off: " + ", ".join(res["switched_off"]))
    res["passed"] = not reasons
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "order_check_" + pd.Timestamp(now()).strftime("%Y%m%dT%H%M%SZ") + ".json")
    res["file"] = path
    with open(path, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    say(f"result written to {path}")
    say("order check PASSED" if not reasons else "order check FAILED: " + "; ".join(reasons))
    if reasons:
        say("The bot keeps the serial path.")
    elif place:
        say("The bot uses the batch order path from its next start (wickctl start).")
    else:
        say("Read-only run: the bot keeps the serial path until a run with test orders passes.")
    return res


def _place(broker, market, pick, bids, cfg, res, say, now):
    ttl = int(cfg.get("bid_ttl_s", 300) or 300)
    reqs, meta = [], []
    for c in pick:
        p = f"{c}-USD"
        bb = bids.get(p)                                   # the batch answer under test ...
        try:
            pub = float(market.best_bid(p))                # ... and the public book: never price from the first alone
        except Exception:
            pub = float("nan")
        ok_b = isinstance(bb, float) and math.isfinite(bb) and bb > 0
        ok_p = math.isfinite(pub) and pub > 0
        if not (ok_b and ok_p) or max(bb, pub) / min(bb, pub) - 1 > AGREE:
            why = ("no batch best bid" if not ok_b else "no public best bid" if not ok_p else
                   f"the batch best bid {bb} and the public one {pub} differ by more than {AGREE:.0%}")
            res["reasons"].append(f"{p}: skipped, {why}")
            say(f"c. {p}: skipped, {why}")
            continue
        try:
            sp = market.spec(c)
            px = E.floor_to(0.5 * min(bb, pub), sp.tick)   # half the lower of the two
            size = E.floor_size(TEST_USD / px, sp.lot)
            if size * px < sp.min_usd:                     # not below the product's minimum order
                size = math.ceil(sp.min_usd / px / sp.lot - 1e-9) * sp.lot
            end = now() + pd.Timedelta(seconds=ttl)
            errs = broker.preview_gtd(sp, px, size, end)
        except Exception as err:
            res["notes"].append(f"{p}: skipped, preview or price failed: {err!r}"[:200])
            say(f"c. {p}: skipped (preview or price failed: {err!r})"[:200])
            continue
        if errs:
            res["notes"].append(f"{p}: skipped, preview errors {errs}"[:300])
            say(f"c. {p}: skipped, preview errors {errs}"[:300])
            continue
        reqs.append((sp, "BUY", px, size, True, end))
        meta.append(dict(product=p, px=px, size=size, end=str(end), tick=sp.tick))
    out = broker.place_many(reqs) if reqs else []
    placed = []
    for m, (oid, err) in zip(meta, out):
        m.update(order_id=oid, error=err)
        say(f"c. {m['product']}: bid {m['size']} at {m['px']} until {m['end']}: " + (f"placed {oid}" if oid
                                                                                     else f"REJECTED {err}"))
        if oid:
            placed.append(dict(id=oid, px=m["px"], size=m["size"], filled=0.0, value=0.0, fees=0.0, side="BUY",
                               product=m["product"], end=m["end"]))
        else:
            res["reasons"].append(f"{m['product']}: placement rejected")
    res["placed"] = meta
    if not placed:
        res["reasons"].append("no test order was placed")
    return placed


def _read_and_cancel(broker, placed, res, say):
    ids = [o["id"] for o in placed]
    snap = broker.snapshot(ids)
    one = {}
    for i in ids:
        try:
            one[i] = broker.status(i)
        except Exception as err:
            one[i] = None
            res["reasons"].append(f"status({i}) failed: {err!r}"[:200])
    diffs = {i: _eq(snap[i], one[i]) for i in ids if i in snap and one.get(i)}
    res["read"] = dict(named=sorted(snap), missing=[i for i in ids if i not in snap], snapshot=snap, single=one,
                       differing_fields={i: d for i, d in diffs.items() if d})
    say(f"d. snapshot named {len(snap)} of {len(ids)}; fields differing from the single read: "
        f"{res['read']['differing_fields'] or 'none'}")
    if res["read"]["missing"]:
        res["reasons"].append("the snapshot did not name " + ", ".join(res["read"]["missing"]))
    if res["read"]["differing_fields"]:
        res["reasons"].append("the snapshot differs from the single read")
    ans = broker.cancel_many(placed)
    rounds = broker.last_cancel_rounds or {}
    res["cancel"] = {}
    for o in placed:
        inc, ok = ans.get(o["id"], (None, False))
        k = rounds.get(o["id"])
        at = k if k == "single" or k is None else broker.CANCEL_READS[k]
        res["cancel"][o["id"]] = dict(confirmed=ok, fill=inc, seen_final_at_s=at)
        o["confirmed"] = ok
        say(f"d. cancel_many {o['id']}: confirmed {ok}, fill {inc}, seen final at "
            + (f"{at} s after the cancel" if isinstance(at, float) else str(at)))
        if not ok:
            res["reasons"].append(f"cancel_many did not confirm {o['id']}")
        if inc:
            res["reasons"].append(f"test order {o['id']} filled: {inc}")


def _clean(broker, placed, res, say):
    """Whatever happened before: every test order not confirmed cancelled is cancelled singly and read again."""
    left = []
    for o in placed:
        if o.get("confirmed"):
            continue
        try:
            inc, ok = broker.cancel(o)
        except Exception as err:
            inc, ok = None, False
            res["notes"].append(f"single cancel of {o['id']}: {err!r}"[:200])
        try:
            st = broker.status(o["id"])["status"]
        except Exception as err:
            st = f"unreadable ({err!r})"[:100]
        say(f"d. clean-up: {o['id']} cancelled singly: confirmed {ok}; status now {st}")
        if st not in broker.TERMINAL:
            left.append(o)
            say(f"!!!!! TEST ORDER STILL OPEN: {o['id']} on {o['product']}, {o['size']} at {o['px']}. It expires "
                f"by itself at {o['end']} UTC; cancel it in the Coinbase app to be sure.")
    left += _sweep(broker, placed, res, say)
    res["still_open"] = [o["id"] for o in left]
    if left:
        res["reasons"].append("test orders still open: " + ", ".join(res["still_open"]))


def _limit_price(od):
    """The limit price of an order in a list answer (any order configuration with a limit_price), or None."""
    for v in (od.get("order_configuration") or {}).values():
        if isinstance(v, dict) and v.get("limit_price") is not None:
            return float(v["limit_price"])
    return None


def _sweep(broker, placed, res, say):
    """A test bid whose placement came back as an error may still rest at the venue: one read of the open orders, and
    any open order with the bot's tag, on a product a test bid was sent for, at that test bid's price (within one
    tick), that is not one of the placed ones, is cancelled singly and read again. The price condition keeps a
    running bot's own bids out of the sweep: they rest at their levels, never at half the best bid."""
    sent = res.get("placed") or []
    if not sent:
        return []
    known = {o["id"] for o in placed}
    try:
        opened = broker.open_orders()
    except Exception as err:
        res["sweep"] = f"could not run: {err!r}"[:200]
        say(f"!! the sweep for lost test orders could not run (the open orders could not be read: {err!r})"[:300])
        if any(not m.get("order_id") for m in sent):
            res["reasons"].append("a placement failed and the sweep for lost test orders could not run")
        return []
    found, left = [], []
    for od in opened:
        oid, px = od.get("order_id"), _limit_price(od)
        if oid in known or not str(od.get("client_order_id", "")).startswith(E.ORDER_TAG) or px is None:
            continue
        m = next((m for m in sent if broker._p(m["product"]) == od.get("product_id")
                  and abs(px - m["px"]) <= m["tick"] * (1 + 1e-9)), None)
        if m is None:
            continue
        o = dict(id=oid, px=m["px"], size=m["size"], filled=0.0, value=0.0, fees=0.0, side="BUY",
                 product=m["product"], end=m["end"])
        found.append(oid)
        try:
            inc, ok = broker.cancel(o)
        except Exception as err:
            inc, ok = None, False
            res["notes"].append(f"single cancel of lost {oid}: {err!r}"[:200])
        try:
            st = broker.status(oid)["status"]
        except Exception as err:
            st = f"unreadable ({err!r})"[:100]
        say(f"d. sweep: a lost test order {oid} on {m['product']} at {px} (its placement came back as an error): "
            f"cancelled singly: confirmed {ok}; status now {st}")
        if inc:
            res["reasons"].append(f"lost test order {oid} filled: {inc}")
        if st not in broker.TERMINAL:
            left.append(o)
            say(f"!!!!! TEST ORDER STILL OPEN: {oid} on {m['product']} at {px}. It expires by itself at {m['end']} "
                "UTC; cancel it in the Coinbase app to be sure.")
    res["sweep"] = dict(found=found)
    if found:
        res["reasons"].append("a test order lost by its placement was found resting: " + ", ".join(found))
    return left
