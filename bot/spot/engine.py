"""Wick catcher with the $1M rules, on Coinbase spot: minute engine, paper broker, live broker.

The rule (reports/wick1m_prereg.md; findings doc, section "Wick catcher at $1M"):
  - Signal: R2-08 unchanged (edge.wick levels and features, the five R2-08 models in bot/v2, 60th-percentile threshold).
  - Size per signal S = min(notional_frac x equity, adv_frac x the coin's trailing 30-day median daily USD volume on
    Coinbase spot + perp); defaults 25% and 0.2%.
  - A ladder in thirds. While the AI approves, a post-only bid of S/3 rests 4 sigma below fair value (the R2-08 level,
    re-priced every minute). When it fills, bids of S/3 go out 6 and 8 sigma below the fair value frozen at that fill;
    they are cancelled when the 4-sigma take-profit first trades or 60 minutes after the fill.
  - Every filled rung gets its own post-only take-profit at 60% of its dislocation and is sold at market 60 minutes
    after its fill. A partly filled rung keeps resting while the price stays below it, for at most 15 more minutes.
  - Option size_by_margin (ladder v5, C2a; null = off): the whole ladder of a signal is sized x0.5 / x1.0 / x1.5 by
    the AI's margin (prediction minus the threshold) below `lower`, between, or at or above `upper` (the margin's
    terciles over all earlier research parent fills; scripts/ladder_v5/margin_cutoffs.py, refreshed each quarter).
  - Option passive_exit_min = N (ladder v5, C3; 0 = off): at the 60-minute mark the unsold part instead rests as a
    post-only sell at the last minute's close plus one tick, re-pegged every minute, for N minutes; whatever is left is
    then sold at market. While it rests the coin may bid again (its 4-sigma rung counts as closed, as in the research).
  - Every AI-approved coin may bid (no slot cap); one parent per coin at a time (a coin may bid again once its 4-sigma
    rung has closed, even while deeper rungs are still open, as in the research).
  - Cash: positions at cost + resting bids <= cash_cap x equity, because Coinbase holds cash for every resting spot
    bid; when cash is short the highest predictions get it.
Known differences from the research simulation (scripts/wick1m/sim.py): the 6/8-sigma bids go out once the 4-sigma
fill is seen (the next minute; within seconds in live mode with fast polling), so deeper fills inside the parent's own
minute are mostly missed (research sensitivity: 10.0% -> 8.5% a year at $1M); entry capacity is Coinbase spot only
(97% of the research's capacity); cash held by resting bids counts against the cash cap.

Each minute, ~6 s after it closes: refresh candles; settle the minute that just closed (paper: trade-through rule with
a capacity limit; live: order status); manage rungs (time exits, deeper-rung window); run the AI; allocate cash; place
or re-price 4-sigma bids. State: <state_dir>/state.json. Events: <state_dir>/events.jsonl.
"""
import json
import math
import os
import time
import uuid
import warnings
from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd

from edge import wick

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WINDOW_MIN = 11 * 1440          # candles kept for the features (7-day beta + warm-up)
DEEP = ("6", "8")               # deeper rungs, sigmas below fair value (lever B)
SCAN_MIN = 15                   # a partly filled rung rests at most this many more minutes (research capacity window)
ADV_DAYS = 30
ORDER_TAG = "wk1m"              # client_order_id prefix: lets reconcile() find the bot's own orders
REFRESH_S = 150                 # re-place a good-til-date bid this many seconds before it would expire
warnings.filterwarnings("ignore", message="Mean of empty slice")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="edge.wick")


def now_utc():
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


def floor_to(x, inc):
    return math.floor(x / inc + 1e-9) * inc


def floor_size(x, lot):
    """Round a quantity down to the lot, never above x (float noise on very large quantities, e.g. PEPE)."""
    return math.floor(x / lot * (1 - 1e-12) + 1e-9) * lot


def fmt(x, inc):
    dec = max(0, -int(math.floor(math.log10(inc) + 1e-12)))
    return f"{x:.{dec}f}"


@dataclass
class Spec:
    product: str
    tick: float          # quote increment, USD
    lot: float           # base increment, coin
    min_usd: float = 1.0


def fallback_ticks():
    """Spot ticks estimated from the research data (reports/wick1m/spot_ticks_wide.csv), PEPE from the audit."""
    p = os.path.join(ROOT, "reports", "wick1m", "spot_ticks_wide.csv")
    out = {}
    if os.path.exists(p):
        t = pd.read_csv(p)
        out = {r.coin: float(r.tick) for r in t.itertuples() if np.isfinite(r.tick)}
    out["PEPE"] = 1e-8
    return out


class Log:
    def __init__(self, path, clock, echo=True):
        self.path, self.clock, self.echo = path, clock, echo
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def __call__(self, kind, t=None, **kw):
        rec = {"ts": pd.Timestamp(t if t is not None else self.clock()).isoformat(), "kind": kind, **kw}
        line = json.dumps(rec, default=str)
        with open(self.path, "a") as fh:
            fh.write(line + "\n")
        if self.echo:
            print(line, flush=True)


# ------------------------------------------------------------------------------------------------ market data
class LiveMarket:
    """Public Coinbase market data, no keys (bot/market.py)."""

    def __init__(self):
        from bot import market
        self.m = market
        self.fb = fallback_ticks()
        p = pd.read_csv(os.path.join(ROOT, "reports", "cfm_products.csv"))
        p = p[p.expiry_type == "PERPETUAL"]
        self.perp = {r.contract_root_unit: (r.product_id, float(r.contract_size)) for r in p.itertuples()}

    def spot_candles(self, coin, start, end):
        return self.m.spot_candles(coin, start, end)

    def best_bid(self, product):
        bids, _ = self.m.book(product, limit=1)
        return bids[0][0] if bids else np.nan

    def bids_ahead(self, product, px):
        """USD resting at or above `px` (filled before us) and whether the fetched book reached `px`."""
        bids, _ = self.m.book(product, limit=1000)
        return sum(p * q for p, q in bids if p >= px), bool(bids) and bids[-1][0] <= px

    def spec(self, coin):
        try:
            js = self.m._get(f"{self.m.ADV}/products/{coin}-USD")
            return Spec(f"{coin}-USD", float(js["quote_increment"]), float(js["base_increment"]),
                        float(js.get("quote_min_size") or 1.0))
        except Exception:
            return Spec(f"{coin}-USD", self.fb.get(coin, 0.01), 1e-8, 1.0)

    def daily_usd(self, coin, end):
        """Daily USD volume (Coinbase spot + perp) and daily closes, for the days before `end`."""
        start = end - pd.Timedelta(days=ADV_DAYS + 5)
        js = self.m._get(f"{self.m.EXCHANGE}/products/{coin}-USD/candles",
                         {"granularity": 86400, "start": start.isoformat() + "Z", "end": end.isoformat() + "Z"})
        rows = {pd.Timestamp(r[0], unit="s"): (float(r[4]), float(r[4]) * float(r[5])) for r in js or []}
        d = pd.DataFrame.from_dict(rows, orient="index", columns=["close", "usd"]).sort_index()
        if coin in self.perp:
            pid, cs = self.perp[coin]
            js = self.m._get(f"{self.m.ADV}/products/{pid}/candles",
                             {"start": int(start.timestamp()), "end": int(end.timestamp()), "granularity": "ONE_DAY"})
            v = pd.Series({pd.Timestamp(int(c["start"]), unit="s"): float(c["close"]) * float(c["volume"]) * cs
                           for c in js.get("candles", [])}, dtype=float)
            d["usd"] = d["usd"].add(v, fill_value=0.0).reindex(d.index)
        return d[d.index < end]


# ------------------------------------------------------------------------------------------------ brokers
class PaperBroker:
    """Post-only limits fill when the spot minute trades through them by one tick, up to `capture` x the volume traded
    beyond the price in that minute (each candle's volume spread evenly over its range; the bot's own orders on one
    coin and side share that pool). An unfilled 4-sigma bid also needs the minute to open above it, as in the research
    (a post-only bid cannot rest above the market). capture=None: unlimited (parity tests)."""

    live = False

    def __init__(self, capture=0.5):
        self.capture = capture

    def place(self, spec, side, px, size, post_only=True, end_time=None):
        return f"paper-{uuid.uuid4().hex[:12]}", None      # expiry not simulated: the bot refreshes bids before it

    def cancel(self, order):
        return None, True                              # no late fills in paper; always confirmed

    def fills(self, coin, orders, bar, minute, tick):
        """orders: [(ref, order)] resting during `minute`. Returns [(ref, qty, px, fee=None, done)]."""
        lo, hi, op, vol = (float(bar.get(k, np.nan)) for k in ("low", "high", "open", "volume"))
        if not (np.isfinite(lo) and np.isfinite(hi)) or not vol > 0:
            return []
        rng, out = hi - lo, []
        for side in ("SELL", "BUY"):
            sel = [(r, o) for r, o in orders if o["side"] == side and pd.Timestamp(o["active_from"]) <= minute]
            sel.sort(key=lambda x: -x[1]["px"] if side == "SELL" else x[1]["px"])  # shared pool, best-placed first
            used = 0.0
            for r, o in sel:
                px = o["px"]
                if side == "BUY":
                    if lo > px - tick * (1 - 1e-9) or (o.get("open_rule") and o["filled"] <= 0 and not op > px):
                        continue
                    frac = 1.0 if rng <= 0 else min(1.0, (px - lo) / rng)
                else:
                    if hi < px + tick * (1 - 1e-9):
                        continue
                    frac = 1.0 if rng <= 0 else min(1.0, (hi - px) / rng)
                rem = o["size"] - o["filled"]
                q = rem if self.capture is None else min(rem, self.capture * vol * frac - used)
                if q <= 1e-15:
                    continue
                used += q
                out.append((r, q, px, None, q >= rem - 1e-12))
        return out

    def market_sell(self, spec, size, ref_px, cost_px):
        return ref_px - cost_px, None, size, None

    def cash(self):
        return np.inf


class LiveBroker:
    """Coinbase Advanced Trade spot via the official SDK (pip install coinbase-advanced-py). Needs a CDP API key with
    trade permission (no transfer permission), created for the portfolio the bot trades in: COINBASE_API_KEY and
    COINBASE_API_SECRET in the environment."""

    live = True
    TERMINAL = ("FILLED", "CANCELLED", "EXPIRED", "FAILED")

    def __init__(self, count_usdc=False):
        from coinbase.rest import RESTClient
        secret = os.environ["COINBASE_API_SECRET"].replace("\\n", "\n")     # accept the one-line (\\n) form
        self.c = RESTClient(api_key=os.environ["COINBASE_API_KEY"], api_secret=secret, timeout=10)   # no hung loop
        self.count_usdc = count_usdc

    @staticmethod
    def _d(r):
        return r.to_dict() if hasattr(r, "to_dict") else r

    @staticmethod
    def _gtd(spec, px, size, end_time, post_only=True):
        return {"limit_limit_gtd": {"base_size": fmt(size, spec.lot), "limit_price": fmt(px, spec.tick),
                                    "end_time": pd.Timestamp(end_time).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "post_only": post_only}}

    def place(self, spec, side, px, size, post_only=True, end_time=None):
        """Post-only limit order: good-til-date when end_time is given (entry bids), else good-til-cancelled."""
        cid = f"{ORDER_TAG}-{uuid.uuid4().hex[:20]}"
        try:
            if end_time is not None:
                r = self._d(self.c.create_order(client_order_id=cid, product_id=spec.product, side=side,
                                                order_configuration=self._gtd(spec, px, size, end_time, post_only)))
            else:
                args = dict(client_order_id=cid, product_id=spec.product, base_size=fmt(size, spec.lot),
                            limit_price=fmt(px, spec.tick), post_only=post_only)
                r = self._d(self.c.limit_order_gtc_buy(**args) if side == "BUY" else self.c.limit_order_gtc_sell(**args))
        except Exception as err:
            oid = self._find_by_client_id(spec.product, cid)  # a timed-out call may still have placed the order
            return (oid, None) if oid else (None, repr(err)[:300])
        if r.get("success"):
            return r["success_response"]["order_id"], None
        return None, json.dumps(r.get("error_response") or r, default=str)[:300]

    def _find_by_client_id(self, product, cid, tries=2):
        for i in range(tries):
            try:
                r = self._d(self.c.list_orders(product_ids=[product], limit=50))
                for od in r.get("orders", []) or []:
                    if od.get("client_order_id") == cid:
                        return od.get("order_id")
            except Exception:
                pass
            if i + 1 < tries:
                time.sleep(0.5)
        return None

    def preview_gtd(self, spec, px, size, end_time):
        """Errors Coinbase would give a good-til-date bid (nothing is placed)."""
        r = self._d(self.c.preview_order(product_id=spec.product, side="BUY",
                                         order_configuration=self._gtd(spec, px, size, end_time)))
        return r.get("errs") or []

    def status(self, oid):
        od = self._d(self.c.get_order(oid)).get("order", {})
        return dict(filled=float(od.get("filled_size") or 0), avg=float(od.get("average_filled_price") or 0),
                    fees=float(od.get("total_fees") or 0), status=od.get("status", ""),
                    last_fill=od.get("last_fill_time"))

    @staticmethod
    def increment(o, s):
        """New fill since the bot last booked this order: (qty, avg px of the new part, fee of the new part)."""
        q = s["filled"] - o["filled"]
        if q <= 1e-12:
            return None
        value = s["filled"] * s["avg"] - o["value"]
        return q, (value / q if value > 0 else o["px"]), max(0.0, s["fees"] - o["fees"])

    def fills(self, coin, orders, bar, minute, tick):
        out = []
        for r, o in orders:
            try:
                s = self.status(o["id"])
            except Exception:
                continue
            inc = self.increment(o, s)
            done = s["status"] in self.TERMINAL
            if inc:
                out.append((r, inc[0], inc[1], inc[2], done))
            elif done:
                out.append((r, 0.0, o["px"], 0.0, True))
        return out

    def cancel(self, order):
        """Cancel and wait for the exchange to confirm. Returns (fill not yet booked as (qty, px, fee) or None,
        confirmed). Unconfirmed: the order may still rest, so the engine keeps it and retries next minute."""
        try:
            self.c.cancel_orders(order_ids=[order["id"]])
        except Exception:
            pass
        s = None
        for _ in range(6):
            try:
                s = self.status(order["id"])
            except Exception:
                s = None
            if s and s["status"] in self.TERMINAL:
                break
            time.sleep(0.4)
        return (self.increment(order, s) if s else None), bool(s and s["status"] in self.TERMINAL)

    def market_sell(self, spec, size, ref_px, cost_px):
        try:
            r = self._d(self.c.market_order_sell(client_order_id=f"{ORDER_TAG}-{uuid.uuid4().hex[:20]}",
                                                 product_id=spec.product, base_size=fmt(size, spec.lot)))
        except Exception as err:
            return None, None, 0.0, repr(err)[:300]
        if not r.get("success"):
            return None, None, 0.0, json.dumps(r.get("error_response") or r, default=str)[:300]
        oid = r["success_response"]["order_id"]
        s = None
        for _ in range(15):
            time.sleep(0.4)
            try:
                s = self.status(oid)
            except Exception:
                continue
            if s["status"] in self.TERMINAL:
                break
        if not s or s["status"] not in self.TERMINAL:     # accepted, outcome unknown: resolve it before selling again
            return None, None, 0.0, {"pending_order": oid, "status": s}
        if s["filled"] <= 0:
            return None, None, 0.0, f"market sell {oid} not filled: {s}"
        return s["avg"], s["fees"], s["filled"], (None if s["filled"] >= size * 0.999 else f"partial: {s['filled']} of {size}")

    def balances(self):
        r = self._d(self.c.get_accounts(limit=250))
        out = {}
        for a in r.get("accounts", []):
            avail = float((a.get("available_balance") or {}).get("value") or 0)
            hold = float((a.get("hold") or {}).get("value") or 0)
            out[a["currency"]] = (avail, hold)
        return out

    def cash(self):
        b = self.balances()
        usd = b.get("USD", (0.0, 0.0))[0]
        return usd + (b.get("USDC", (0.0, 0.0))[0] if self.count_usdc else 0.0)

    def open_orders(self):
        r = self._d(self.c.list_orders(order_status=["OPEN"], limit=1000))
        return r.get("orders", [])

    def cancel_ids(self, ids):
        self.c.cancel_orders(order_ids=list(ids))

    def filled_order_ids(self, since, max_pages=5):
        """Order ids with a fill at or after `since` (usually one request for the whole account; for 1-second
        detection). Follows the cursor for at most max_pages pages of 100 fills (a crash can bring many partial fills)."""
        fn = getattr(self.c, "get_fills", None) or getattr(self.c, "list_fills")
        start = pd.Timestamp(since).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        ids, cursor = set(), None
        for _ in range(max_pages):
            kw = dict(start_sequence_timestamp=start, limit=100)
            if cursor:
                kw["cursor"] = cursor
            r = self._d(fn(**kw))
            fills = r.get("fills", []) or []
            ids |= {f.get("order_id") for f in fills}
            nxt = r.get("cursor")
            if len(fills) < 100 or not nxt or nxt == cursor:
                break
            cursor = nxt
        return ids

    def fee_tier(self):
        r = self._d(self.c.get_transaction_summary())
        ft = r.get("fee_tier") or {}
        return dict(tier=ft.get("pricing_tier"), maker_bp=1e4 * float(ft.get("maker_fee_rate") or 0),
                    taker_bp=1e4 * float(ft.get("taker_fee_rate") or 0), volume_30d=r.get("advanced_trade_only_volume"))


# ------------------------------------------------------------------------------------------------ engine
@dataclass
class Engine:
    mode: str = "paper"
    cfg: dict = field(default_factory=dict)
    state_dir: str = os.path.join(ROOT, "paper_spot")
    model_dir: str = os.path.join(ROOT, "bot", "v2")
    market: object = None
    broker: object = None
    clock: object = None
    echo: bool = True

    def __post_init__(self):
        meta = json.load(open(os.path.join(self.model_dir, "model_meta.json")))
        self.models = [lgb.Booster(model_file=os.path.join(self.model_dir, f)) for f in meta["models"]]
        self.coins = list(meta["coins"])
        self.codes = {c: i for i, c in enumerate(sorted(self.coins))}
        self.thr = float(meta["threshold"])
        self.theta, self.k = float(meta.get("THETA", wick.THETA)), float(meta.get("K", wick.K))
        self.hold, self.lookback = int(meta.get("H", wick.H)), int(meta.get("L", wick.L))
        self.wbeta = int(meta.get("wbeta") or wick.W)
        self.market = self.market or LiveMarket()
        self.clock = self.clock or now_utc
        self.state_path = os.path.join(self.state_dir, "state.json")
        self.log = Log(os.path.join(self.state_dir, "events.jsonl"), self.clock, echo=self.echo)
        self.state = self._load_state()
        if self.broker is None:
            self.broker = (LiveBroker(self.cfg.get("count_usdc_as_cash", False)) if self.mode == "live"
                           else PaperBroker(self.cfg.get("paper_capture", 0.5)))
        off = set(self.cfg.get("coins_disabled", []))
        self.tradable = [c for c in self.coins if c not in off]
        self.specs = {c: Spec(**v) for c, v in self.state.get("specs", {}).items()}
        self.spot = {}
        self.cash_live = np.inf
        self.counts = {}
        self._tp_dirty = set()
        self._no_buys = False                              # set while market data or cash is unavailable
        # entry bids expire on their own after ttl seconds (0: good-til-cancelled); the bot re-places them while alive
        self.ttl = int(self.state.get("gtd_ttl_s") or self.cfg.get("bid_ttl_s", 300) or 0)
        # share of each signal per rung (default: thirds); e.g. {"4": 1, "6": 1, "8": 2} is the wick v4 W2 challenger
        w = {str(k): float(v) for k, v in (self.cfg.get("rung_weights") or {"4": 1, "6": 1, "8": 1}).items()}
        self.rung_w = {k: w.get(k, 0.0) / sum(w.values()) for k in ("4",) + DEEP}
        self.passive_n = int(self.cfg.get("passive_exit_min") or 0)    # ladder v5 C3: passive time exit (0 = off)
        self.margin_rule = self.cfg.get("size_by_margin") or None      # ladder v5 C2a: size by the AI's margin

    # ---------- state
    def _load_state(self):
        if os.path.exists(self.state_path):
            return json.load(open(self.state_path))
        cap = float(self.cfg.get("capital", 250000.0))
        return dict(version=1, equity=cap, peak=cap, ladders={}, seq=0, day=None, day_start_equity=cap,
                    halted_day=None, dd_halt=False, last_minute=None, adv={}, vol_d={}, adv_day=None, specs={})

    def save(self):
        self.state["specs"] = {c: vars(s) for c, s in self.specs.items()}
        os.makedirs(self.state_dir, exist_ok=True)
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(self.state, fh, indent=1, default=str)
        os.replace(tmp, self.state_path)

    def ladders(self, coin=None):
        return [lad for lad in list(self.state["ladders"].values()) if coin is None or lad["coin"] == coin]

    def count(self, k, n=1):
        self.counts[k] = self.counts.get(k, 0) + n

    # ---------- data
    def spec(self, c):
        if c not in self.specs:
            self.specs[c] = self.market.spec(c)
        return self.specs[c]

    def refresh_adv(self, t):
        d = str(t.date())
        if self.state.get("adv_day") == d:
            return
        for c in self.coins:
            try:
                u = self.market.daily_usd(c, t.floor("D")).tail(ADV_DAYS + 1)
                usd = u.usd[u.usd > 0].tail(ADV_DAYS)
                r = np.log(u.close).diff().dropna().tail(ADV_DAYS)
                self.state["adv"][c] = float(usd.median()) if len(usd) >= 10 else None
                self.state["vol_d"][c] = float(r.std()) if len(r) >= 10 else None
            except Exception as err:                        # keep the last value
                self.log("error", t=t, error=f"adv {c}: {err!r}"[:300])
        self.state["adv_day"] = d
        self.log("adv", t=t, adv_musd={c: round(v / 1e6, 1) for c, v in self.state["adv"].items() if v})

    def update_spot(self, end):
        for c in ["BTC"] + self.coins:
            df = self.spot.get(c)
            # re-fetch the last 3 minutes too: the newest candle can still be filling in when first fetched
            start = (df.index.max() - pd.Timedelta(minutes=2)) if df is not None and len(df) else end - pd.Timedelta(minutes=WINDOW_MIN)
            if start >= end:
                continue
            new = self.market.spot_candles(c, start, end)
            if df is None or not len(df):
                df = new
            elif len(new):
                df = pd.concat([df, new])
                df = df[~df.index.duplicated(keep="last")]
            if len(df):
                df = df.loc[end - pd.Timedelta(minutes=WINDOW_MIN):]
            self.spot[c] = df

    def arrays(self, upto):
        idx = pd.date_range(upto - pd.Timedelta(minutes=WINDOW_MIN - 1), upto, freq="min")
        cf, vol = {}, {}
        for c, df in self.spot.items():
            d = df[df.volume > 0].reindex(idx)
            cf[c] = d.close.ffill(limit=30).to_numpy(np.float64)
            vol[c] = d.volume.fillna(0.0).to_numpy(np.float64)
        return idx, cf, vol

    def bar(self, c, minute):
        df = self.spot.get(c)
        if df is None or minute not in df.index:
            return {}
        return df.loc[minute].to_dict()

    def last_close(self, c, before):
        df = self.spot.get(c)
        if df is None or not len(df):
            return np.nan
        s = df.close[(df.index < before) & (df.volume > 0)]
        return float(s.iloc[-1]) if len(s) and s.index[-1] >= before - pd.Timedelta(minutes=30) else np.nan

    def fresh(self, c, before, minutes=10):
        df = self.spot.get(c)
        return df is not None and len(df) and df.index.max() >= before - pd.Timedelta(minutes=minutes)

    # ---------- money
    def hold_usd(self, o):
        return (o["size"] - o["filled"]) * o["px"] * (1 + self.fee_m())

    def committed(self):
        tot = 0.0
        for lad in self.ladders():
            tot += sum(tr["cost"] for tr in lad["tranches"].values())
            tot += sum(self.hold_usd(o) for o in lad["orders"].values() if o["side"] == "BUY")
        return tot

    def free_cash(self):
        """Dollars available for new holds. A resting buy holds its notional plus the maker fee."""
        return min(self.cfg.get("cash_cap", 1.0) * self.state["equity"] - self.committed(), self.cash_live)

    def fee_m(self):
        return self.cfg.get("fee_bp_maker", 6.0) / 1e4

    def signal_usd(self, c):
        S = self.cfg.get("notional_frac", 0.25) * self.state["equity"]
        a = self.state["adv"].get(c)
        if self.cfg.get("adv_frac"):
            if not a:
                return 0.0           # volume cap set but the coin's volume unknown (< 10 days of data): no bid (ladder v5
                                     # red team: it used to bid the uncapped 25%, which the research never priced)
            S = min(S, self.cfg["adv_frac"] * a)
        return S

    def size_mult(self, pred):
        """Ladder v5 C2a: multiplier of the signal's whole ladder from the AI's margin (1.0 when the option is off)."""
        r = self.margin_rule
        if not r:
            return 1.0
        lo, mid, hi = (float(x) for x in r.get("mult", (0.5, 1.0, 1.5)))
        m = pred - self.thr
        return lo if m < float(r["lower"]) else hi if m >= float(r["upper"]) else mid

    def mtm(self, before):
        u = 0.0
        for lad in self.ladders():
            px = self.last_close(lad["coin"], before)
            for tr in lad["tranches"].values():
                if np.isfinite(px):
                    u += tr["size"] * px - tr["cost"]
        return self.state["equity"] + u

    # ---------- orders
    def _place(self, lad, key, side, px, size, t, open_rule=False, first_fill=None):
        sp = self.spec(lad["coin"])
        if side == "BUY" and self._no_buys:
            return False, "no new bids while market data or cash is unavailable"
        size = floor_size(size, sp.lot)
        if size <= 0 or size * px < sp.min_usd:
            return False, "below minimum size"
        while True:
            end = self.clock() + pd.Timedelta(seconds=self.ttl) if side == "BUY" and self.ttl else None
            oid, err = self.broker.place(sp, side, px, size, end_time=end)
            if oid is None and err and any(x in str(err).upper() for x in ("DURATION", "END_TIME", "EXPIR")) \
                    and 0 < self.ttl < 3600:
                self.ttl = min(3600, 2 * self.ttl)          # Coinbase wants longer-lived bids: use its minimum
                self.state["gtd_ttl_s"] = self.ttl
                self.log("warning", t=t, msg=f"good-til-date bids now last {self.ttl} s (Coinbase minimum)")
                continue
            break
        if oid is None:
            self.log("reject", t=t, coin=lad["coin"], ladder=lad["id"], key=key, px=px, size=size, error=err)
            return False, err or "rejected"
        lad["orders"][key] = dict(id=oid, side=side, px=px, size=size, filled=0.0, value=0.0, fees=0.0,
                                  active_from=t.isoformat(), first_fill=first_fill, open_rule=open_rule,
                                  expires=None if end is None else end.isoformat())
        if side == "BUY" and np.isfinite(self.cash_live):
            self.cash_live -= self.hold_usd(lad["orders"][key])
        return True, None

    def _cancel(self, lad, key, t, minute=None):
        """Cancel one order. Returns True when it is gone; False when the exchange has not confirmed (live), in which
        case the order stays in the state and the caller retries next minute."""
        o = lad["orders"].pop(key, None)
        if o is None:
            return True
        o["cancel_req"] = True
        inc, ok = self.broker.cancel(o)
        if inc:                                            # live: it filled before the cancel took effect
            q, px, fee = inc
            o["filled"] += q
            o["value"] += q * px
            o["fees"] += fee
            self._apply_fill(lad, key, o, q, px, fee, minute or t.floor("min"))
        if not ok:
            lad["orders"][key] = o
            self.count("cancel_unconfirmed")
            self.log("warning", t=t, coin=lad["coin"], ladder=lad["id"], key=key, msg="cancel not confirmed; retrying")
            return False
        if o["side"] == "BUY" and np.isfinite(self.cash_live):
            self.cash_live += self.hold_usd(o)
        return True

    def _apply_fill(self, lad, key, o, q, px, fee, minute, beyond_usd=None):
        c, sp = lad["coin"], self.spec(lad["coin"])
        if fee is None:                                    # paper: resting limit orders pay the maker fee
            fee = q * px * self.cfg.get("fee_bp_maker", 6.0) / 1e4
        if key.startswith("e"):
            k = key[1:]
            if k == "4" and lad["status"] == "armed":
                lad.update(status="open", parent_ts=minute.isoformat(), fair_log=math.log(o["px"]) + self.k * lad["sig"],
                           cancel_at=(minute + pd.Timedelta(minutes=self.hold)).isoformat(), tp4_touched=False,
                           pending=list(DEEP))
            tr = lad["tranches"].get(k)
            if tr is None:
                tp = floor_to(o["px"] * math.exp(self.theta * float(k) * lad["sig"]), sp.tick)
                tr = lad["tranches"][k] = dict(size=0.0, cost=0.0, fees=0.0, entry_ts=minute.isoformat(), tp_px=tp,
                                               exit_due=(minute + pd.Timedelta(minutes=self.hold + 1)).isoformat())
            tr["size"] += q
            tr["cost"] += q * px
            tr["fees"] += fee
            lad.setdefault("bought", {})[k] = lad.get("bought", {}).get(k, 0.0) + q * px
            if o.get("first_fill") is None:
                o["first_fill"] = minute.isoformat()
            self.log("fill_entry", t=minute, coin=c, ladder=lad["id"], rung=int(k), px=px, size=q,
                     usd=round(q * px, 2), fee=round(fee, 4), tp_px=tr["tp_px"], left=max(0.0, o["size"] - o["filled"]),
                     beyond_usd=None if beyond_usd is None else round(beyond_usd))
            self._tp_dirty.add((lad["id"], k))
        else:
            k = key[2:]
            kind = "passive" if key.startswith("px") else "tp"
            tr = lad["tranches"].get(k)
            if tr is None or tr["size"] <= 0:
                self.log("warning", t=minute, coin=c, msg=f"{kind} sell fill without an open rung", key=key, qty=q)
                return
            share = min(1.0, q / tr["size"])
            cost, efee = tr["cost"] * share, tr["fees"] * share
            pnl = q * px - cost - efee - fee
            tr["size"] -= q
            tr["cost"] -= cost
            tr["fees"] -= efee
            self.state["equity"] += pnl
            lad["pnl"] = lad.get("pnl", 0.0) + pnl
            if k == "4" and kind == "tp":
                lad["tp4_touched"] = True
            self.log("fill_exit", t=minute, coin=c, ladder=lad["id"], rung=int(k), exit=kind, px=px,
                     entry_px=round(cost / q, 10) if q else None, size=q, pnl=round(pnl, 2),
                     net_bp=round(1e4 * pnl / cost, 1) if cost else None, equity=round(self.state["equity"], 2))
            if self._dust(tr, px, sp):
                lad["tranches"].pop(k, None)               # an unfilled take-profit remainder is cancelled by _manage

    @staticmethod
    def _dust(tr, px, sp):
        """A rung whose remainder is worth less than the exchange's minimum order is closed (the dust stays put)."""
        return tr["size"] < sp.lot / 2 or tr["size"] * px < sp.min_usd

    def _refresh_tps(self, t):
        """(Re)place the take-profit of every rung that filled this pass, for its full open size."""
        keep = set()
        for lid, k in sorted(self._tp_dirty):
            lad = self.state["ladders"].get(lid)
            if not lad or k not in lad["tranches"]:
                continue
            if f"tp{k}" in lad["orders"] and not self._cancel(lad, f"tp{k}", t):
                keep.add((lid, k))
                continue
            tr = lad["tranches"].get(k)
            if not tr or tr.get("sell_order"):
                continue
            if self.passive_n and t >= pd.Timestamp(tr["exit_due"]):
                continue                                    # past its 60 minutes: the exit owns the rung
            ok, err = self._place(lad, f"tp{k}", "SELL", tr["tp_px"], tr["size"], t)
            if not ok and err and "POST_ONLY" in str(err).upper():   # market already above the target: sell now
                self._exit_market(lad, k, t, "tp_cross")
            elif not ok and "minimum" not in str(err):
                keep.add((lid, k))                          # transient error: try again next pass
        self._tp_dirty = keep

    def _exit_market(self, lad, k, t, reason):
        c, sp = lad["coin"], self.spec(lad["coin"])
        for key in (f"tp{k}", f"px{k}"):                   # live: books the resting sell's fills first
            if key in lad["orders"] and not self._cancel(lad, key, t):
                return                                     # a sell is still live: retry next minute
        tr = lad["tranches"].get(k)
        if tr is None:
            return
        if tr.get("sell_order") and not self._resolve_sell(lad, k, t):
            return                                         # an earlier sell's outcome is still unknown: never sell twice
        tr = lad["tranches"].get(k)
        if tr is None:
            return
        last = self.last_close(c, t)
        if not np.isfinite(last):
            last = tr["cost"] / tr["size"]
        size = floor_size(tr["size"], sp.lot)
        if self._dust(tr, last, sp) or size <= 0:
            lad["tranches"].pop(k, None)                   # less than the exchange's minimum order: nothing to sell
            return
        a, vd = self.state["adv"].get(c), self.state["vol_d"].get(c)
        imp = self.cfg.get("impact_y", 0.7) * vd * math.sqrt(size * last / a) if a and vd else 0.0
        cost_px = last * (self.cfg.get("half_spread_bp", 2.0) / 1e4 + imp)
        px, fee, sold, err = self.broker.market_sell(sp, size, last, cost_px)
        if px is None or not sold:
            if isinstance(err, dict) and err.get("pending_order"):
                tr.update(sell_order=err["pending_order"], sell_reason=reason, sell_ref=last)
                self.log("warning", t=t, coin=c, ladder=lad["id"], rung=int(k),
                         msg=f"market sell {err['pending_order']} sent, outcome unknown: resolving before any new sell")
                return
            self.log("error", t=t, coin=c, ladder=lad["id"], rung=int(k), error=f"exit failed, retry next minute: {err}")
            return
        if err:
            self.log("warning", t=t, coin=c, ladder=lad["id"], msg=err)
        self._book_sell(lad, k, tr, sold, px, fee, last, reason, imp, t)

    def _in_passive(self, tr, t):
        """The rung is in its passive exit window: from its 60-minute mark for passive_exit_min minutes."""
        if not self.passive_n or tr.get("sell_order"):
            return False
        due = pd.Timestamp(tr["exit_due"])
        return due <= t < due + pd.Timedelta(minutes=self.passive_n)

    def _exit_passive(self, lad, k, t):
        """Ladder v5 C3: the rung's unsold part rests as a post-only sell at the last minute's close plus one tick,
        re-pegged every minute (kept, with its queue place, while the peg is unchanged)."""
        c, sp = lad["coin"], self.spec(lad["coin"])
        if f"tp{k}" in lad["orders"] and not self._cancel(lad, f"tp{k}", t):
            return                                         # take-profit still live: retry next minute
        tr = lad["tranches"].get(k)
        if tr is None:
            return
        last = self.last_close(c, t)
        if not np.isfinite(last):
            return                                         # no price: keep what rests; the market exit still comes
        peg = floor_to(last, sp.tick) + sp.tick
        size = floor_size(tr["size"], sp.lot)
        if self._dust(tr, last, sp) or size <= 0:
            if f"px{k}" not in lad["orders"]:
                lad["tranches"].pop(k, None)               # less than the exchange's minimum: nothing to sell
            return
        key = f"px{k}"
        o = lad["orders"].get(key)
        if o is not None:
            if abs(o["px"] - peg) < sp.tick / 2 and abs((o["size"] - o["filled"]) - size) < sp.lot / 2:
                return                                     # unchanged: keep the queue place
            if not self._cancel(lad, key, t):
                return                                     # still resting: retry next minute
            tr = lad["tranches"].get(k)
            if tr is None:
                return                                     # it sold out before the cancel took effect
            size = floor_size(tr["size"], sp.lot)
            if self._dust(tr, last, sp) or size <= 0:
                lad["tranches"].pop(k, None)
                return
        ok, err = self._place(lad, key, "SELL", peg, size, t)
        if not ok and err and "POST_ONLY" in str(err).upper():   # the market is already above the peg: sell now
            self._exit_market(lad, k, t, "passive_cross")
        elif ok and o is None:
            self.log("passive_exit", t=t, coin=c, ladder=lad["id"], rung=int(k), px=peg, size=size,
                     until=(pd.Timestamp(tr["exit_due"]) + pd.Timedelta(minutes=self.passive_n)).isoformat())

    def _resolve_sell(self, lad, k, t):
        """Book a market sell whose outcome was unknown when it was sent. True once resolved."""
        tr = lad["tranches"].get(k)
        if tr is None or not tr.get("sell_order"):
            return True
        try:
            s = self.broker.status(tr["sell_order"])
        except Exception:
            return False
        if s["status"] not in self.broker.TERMINAL:
            return False
        oid, tr["sell_order"] = tr["sell_order"], None
        if s["filled"] > 0:
            self.log("warning", t=t, coin=lad["coin"], ladder=lad["id"], msg=f"resolved market sell {oid}: {s['filled']} sold")
            self._book_sell(lad, k, tr, s["filled"], s["avg"], s["fees"], tr.get("sell_ref") or s["avg"],
                            tr.get("sell_reason") or "time", 0.0, t)
        return True

    def _book_sell(self, lad, k, tr, sold, px, fee, last, reason, imp, t):
        c, sp = lad["coin"], self.spec(lad["coin"])
        if fee is None:
            fee = sold * px * self.cfg.get("fee_bp_taker", 12.5) / 1e4
        share = min(1.0, sold / tr["size"])
        cost, efee = tr["cost"] * share, tr["fees"] * share
        pnl = sold * px - cost - efee - fee
        tr["size"] -= sold
        tr["cost"] -= cost
        tr["fees"] -= efee
        self.state["equity"] += pnl
        lad["pnl"] = lad.get("pnl", 0.0) + pnl
        self.log("fill_exit", t=t, coin=c, ladder=lad["id"], rung=int(k), exit=reason, px=px, ref_px=last,
                 entry_px=round(cost / sold, 10), size=sold, pnl=round(pnl, 2), net_bp=round(1e4 * pnl / cost, 1),
                 impact_bp=round(imp * 1e4, 1), equity=round(self.state["equity"], 2))
        if self._dust(tr, px, sp):                         # a partial market fill leaves the rest for next minute
            lad["tranches"].pop(k, None)

    # ---------- one minute
    def step(self, t=None):
        t = pd.Timestamp(t if t is not None else self.clock()).floor("min")    # the minute now starting
        prev = t - pd.Timedelta(minutes=1)
        try:
            self.update_spot(t)
            self.refresh_adv(t)
            if self.broker.live:
                self.cash_live = self.broker.cash() - self.cfg.get("usd_reserve", 500.0)
        except Exception:
            self._orders_only(prev, t)                     # exits and take-profits still run; no new bids
            raise
        self._new_day(t)
        self._settle(prev, t)
        idx, cf, vol = self.arrays(t)
        pn = wick.panel(cf, vol, self.coins, idx, k=self.k, lookback=self.lookback, coin_codes=self.codes, wbeta=self.wbeta)
        self._manage(t)
        self._risk(t)
        self._allocate(pn, t)
        self._refresh_tps(t)                               # rungs that filled while their bids were being cancelled
        if self.broker.live and t.minute % 15 == 7:
            self.reconcile(t)                              # orphan orders, balance drift, fee tier
        if t.minute % 30 == 0:
            free = self.free_cash()
            self.log("heartbeat", t=t, equity=round(self.state["equity"], 2), mtm=round(self.mtm(t), 2),
                     committed=round(self.committed()), free=round(free) if np.isfinite(free) else None,
                     armed=sorted(l["coin"] for l in self.ladders() if l["status"] == "armed"),
                     open=sorted(f"{l['coin']}:{'/'.join(sorted(l['tranches']))}" for l in self.ladders() if l["tranches"]),
                     counts=self.counts)
            self.counts = {}
        self.state["last_minute"] = t.isoformat()
        self.save()

    def _orders_only(self, prev, t):
        """Market data or cash unavailable this minute: book fills, run exits and keep take-profits, place no bids."""
        self._no_buys = True
        try:
            self._new_day(t)
            self._settle(prev, t)
            self._manage(t)
            self._refresh_tps(t)
        except Exception as err:
            self.log("error", t=t, error=f"order handling without market data failed: {err!r}"[:300])
        finally:
            self._no_buys = False
            self.save()

    def _settle(self, m, t):
        """Book fills for minute m (the one that just closed)."""
        for c in self.coins:
            if not any(lad["orders"] for lad in self.ladders(c)):
                continue
            bar, tick = self.bar(c, m), self.spec(c).tick
            # take-profits first: the parent's take-profit trade closes the deeper rungs' window (no deeper fill in
            # that minute, as in the research)
            for side in ("SELL", "BUY"):
                sel = [((lad["id"], key), o) for lad in self.ladders(c) for key, o in lad["orders"].items()
                       if o["side"] == side
                       and not (side == "BUY" and key != "e4" and lad.get("tp4_touched") and not self.broker.live)]
                if not sel:
                    continue
                for (lid, key), q, px, fee, done in self.broker.fills(c, sel, bar, m, tick):
                    lad = self.state["ladders"].get(lid)
                    o = lad["orders"].get(key) if lad else None
                    if o is None:
                        continue
                    if q > 0:
                        o["filled"] += q
                        o["value"] += q * px
                        o["fees"] += fee or 0.0
                        self._apply_fill(lad, key, o, q, px, fee, m, beyond_usd=self._beyond_usd(bar, o))
                    if done and key in lad["orders"]:
                        gone = lad["orders"].pop(key)
                        left = gone["size"] - gone["filled"]
                        if (key[1:] in DEEP and not gone.get("cancel_req") and gone["filled"] <= 0
                                and left * gone["px"] >= self.spec(c).min_usd and lad["status"] == "open"
                                and not lad.get("tp4_touched") and t < pd.Timestamp(lad["cancel_at"])
                                and key[1:] not in lad["pending"]):
                            lad["pending"].append(key[1:])        # it expired (bot down): place it again
                            self.count("deep_requeue")
            # a partly filled rung keeps resting while the price stays below it, at most SCAN_MIN more minutes
            lo = float(bar.get("low", np.nan))
            for lad in self.ladders(c):
                for key in [k for k in lad["orders"] if k.startswith("e")]:
                    o = lad["orders"][key]
                    ff = o.get("first_fill")
                    if ff is None or m <= pd.Timestamp(ff):
                        continue
                    if not (lo < o["px"]) or m >= pd.Timestamp(ff) + pd.Timedelta(minutes=SCAN_MIN):
                        self._cancel(lad, key, t, minute=m)
                        self.count("remainder_cancel")
        self._refresh_tps(t)

    @staticmethod
    def _beyond_usd(bar, o):
        """USD volume traded beyond the order's price in the fill minute (the paper capacity base, at capture 1)."""
        lo, hi, vol = (float(bar.get(k, np.nan)) for k in ("low", "high", "volume"))
        if not (np.isfinite(lo) and np.isfinite(hi) and vol > 0):
            return None
        rng = hi - lo
        if o["side"] == "BUY":
            frac = 1.0 if rng <= 0 else max(0.0, min(1.0, (o["px"] - lo) / rng))
        else:
            frac = 1.0 if rng <= 0 else max(0.0, min(1.0, (hi - o["px"]) / rng))
        return vol * frac * o["px"]

    def _manage(self, t):
        for lad in self.ladders():
            if lad["status"] != "open":
                continue
            closed = lad["tp4_touched"] or t >= pd.Timestamp(lad["cancel_at"])
            if closed:
                for k in DEEP:
                    if f"e{k}" in lad["orders"]:
                        self._cancel(lad, f"e{k}", t)
                        self.count("deep_cancel")
                lad["pending"] = []
            for k, tr in list(lad["tranches"].items()):
                if tr.get("sell_order"):
                    self._resolve_sell(lad, k, t)          # a sell sent earlier with an unknown outcome
                elif self._in_passive(tr, t):
                    self._exit_passive(lad, k, t)          # option passive_exit_min (ladder v5 C3)
                elif t >= pd.Timestamp(tr["exit_due"]):
                    self._exit_market(lad, k, t, "time")
            for key in [k for k, o in lad["orders"].items()
                        if k.startswith(("tp", "px")) and k[2:] not in lad["tranches"]]:
                self._cancel(lad, key, t)                  # a sell left over a closed rung (dust remainder)
            for k, tr in lad["tranches"].items():
                if f"tp{k}" not in lad["orders"] and not tr.get("sell_order") and t < pd.Timestamp(tr["exit_due"]):
                    self._tp_dirty.add((lad["id"], k))     # a take-profit lost to an error or cancelled by the exchange
            self._refresh_bids(lad, t)
            if lad["pending"] and not self._halted(t):
                self._place_pending(lad, t)
            if not lad["tranches"] and not lad["orders"] and not lad["pending"]:
                self.log("ladder_close", t=t, coin=lad["coin"], ladder=lad["id"], pnl=round(lad.get("pnl", 0.0), 2))
                self.state["ladders"].pop(lad["id"], None)

    def _refresh_bids(self, lad, t):
        """Good-til-date bids expire on their own, so a dead server leaves no bids behind. While the bot is alive it
        re-places the ones still wanted (a partly filled 4-sigma rung in its remainder window, deeper rungs) first."""
        if self._no_buys:
            return                                         # no data: let the bids expire rather than re-place blind
        now = self.clock()
        closed = lad.get("tp4_touched") or t >= pd.Timestamp(lad["cancel_at"])
        halted = self._halted(t)
        for key in [k for k, o in lad["orders"].items() if o["side"] == "BUY"]:
            o = lad["orders"][key]
            if not o.get("expires") or pd.Timestamp(o["expires"]) - now > pd.Timedelta(seconds=REFRESH_S):
                continue
            if not self._cancel(lad, key, t):
                continue
            deep = key[1:] in DEEP
            if halted or (deep and closed):
                continue                                   # halted, or the deeper rungs' window closed: let it go
            left = o["size"] - o["filled"]
            if lad["id"] in self.state["ladders"] and left * o["px"] >= self.spec(lad["coin"]).min_usd:
                ok, _ = self._place(lad, key, "BUY", o["px"], left, t, first_fill=o.get("first_fill"))
                self.count("refresh")
                if not ok and deep and o["filled"] <= 0 and key[1:] not in lad["pending"]:
                    lad["pending"].append(key[1:])         # retried while the window is open (e.g. post-only reject)

    def _place_pending(self, lad, t):
        """Deeper rungs at fair value (frozen at the 4-sigma fill) minus 6 / 8 sigma, if the market is above them and
        cash allows; otherwise retried next minute while the window is open."""
        if self._no_buys:
            return
        c, sp = lad["coin"], self.spec(lad["coin"])
        mkt = self._market_px(c, t)
        keep = []
        for k in lad["pending"]:
            if f"e{k}" in lad["orders"]:
                continue
            ra = lad.get("retry_at", {}).get(k)
            if ra and self.clock() < pd.Timestamp(ra):
                keep.append(k)
                continue
            lvl = floor_to(math.exp(lad["fair_log"] - float(k) * lad["sig"]), sp.tick)
            if not (np.isfinite(mkt) and mkt > lvl):
                keep.append(k)
                self.count("deep_deferred_market")
                continue
            bought = lad.get("bought", {}).get(k, lad["tranches"].get(k, {}).get("cost", 0.0))
            usd, free = lad["S"] * self.rung_w[k] - bought, self.free_cash()
            if usd < sp.min_usd:
                continue
            if usd * (1 + self.fee_m()) > free:
                if free >= 0.5 * usd * (1 + self.fee_m()):
                    usd = 0.999 * free / (1 + self.fee_m())
                else:
                    keep.append(k)
                    self.count("deep_deferred_cash")
                    continue
            ok, err = self._place(lad, f"e{k}", "BUY", lvl, usd / lvl, t)
            if ok:
                self.log("rung", t=t, coin=c, ladder=lad["id"], rung=int(k), px=lvl, usd=round(usd))
            elif err and "POST_ONLY" in str(err).upper():
                keep.append(k)
            elif "minimum" not in str(err):                # transient error: retry in a minute while the window is open
                keep.append(k)
                lad.setdefault("retry_at", {})[k] = (self.clock() + pd.Timedelta(seconds=60)).isoformat()
        lad["pending"] = keep

    def _market_px(self, c, t):
        if self.broker.live:
            try:
                return float(self.market.best_bid(self.spec(c).product))
            except Exception:
                return np.nan
        return self.last_close(c, t)

    def _allocate(self, pn, t):
        busy, armed = set(), {}
        for lad in self.ladders():
            if lad["status"] == "armed":
                armed[lad["coin"]] = lad
            elif "e4" in lad["orders"] or ("4" in lad["tranches"] and not self._in_passive(lad["tranches"]["4"], t)):
                busy.add(lad["coin"])
        halted = self._halted(t)
        prev = t - pd.Timedelta(minutes=1)
        cands, rows = [], {}
        if not halted and self.fresh("BTC", t):
            for c in self.tradable:
                if c in busy or not self.fresh(c, t):
                    continue
                row = pn[c].iloc[-1]
                if not all(np.isfinite(row[f]) for f in ("level", "sig", "z_res60", "bid_depth_bp")):
                    continue
                pred = float(np.mean([m.predict(row[wick.FEATS].to_numpy(np.float64)[None, :])[0] for m in self.models]))
                if pred > self.thr:
                    cands.append((pred, c))
                    rows[c] = row
        cands.sort(reverse=True)
        free = self.free_cash() + sum(self.hold_usd(l["orders"]["e4"]) for l in armed.values() if "e4" in l["orders"])
        alloc = {}
        for pred, c in cands:
            want = self.signal_usd(c) * self.rung_w["4"] * self.size_mult(pred)   # order notional (+ maker fee held)
            if want <= 0:
                self.count("no_adv")
                continue
            need = want * (1 + self.fee_m())
            if need <= free:
                alloc[c], free = want, free - need
            elif free >= 0.5 * need:
                alloc[c], free = 0.999 * free / (1 + self.fee_m()), 0.0
            else:
                self.count("cash_short")
                self.log("cash_short", t=t, coin=c, pred=round(pred, 1), want=round(want), free=round(max(free, 0)))
        for c, lad in armed.items():                       # lost approval or cash: cancel first, freeing its hold
            if c not in alloc:
                if self._cancel(lad, "e4", t, minute=prev) and lad["status"] == "armed":
                    self.state["ladders"].pop(lad["id"], None)
                    self.count("disarm")
        # two passes, so cash released by re-priced bids is free before any new bid needs it
        plans = [p for p in (self._arm_plan(c, pred, rows[c], alloc[c], t, armed.get(c)) for pred, c in cands
                             if c in alloc) if p]
        for p in plans:
            self._arm(*p)

    def _arm_plan(self, c, pred, row, usd, t, lad):
        """Decide the 4-sigma bid for coin c; cancel a stale one. Returns the arguments for _arm, or None."""
        sp = self.spec(c)
        px = floor_to(float(row["level"]), sp.tick)
        size = floor_size(usd / px, sp.lot)
        if lad is not None:
            o = lad["orders"].get("e4")
            fresh = not o or not o.get("expires") or \
                pd.Timestamp(o["expires"]) - self.clock() > pd.Timedelta(seconds=REFRESH_S)
            if o and fresh and abs(o["px"] - px) < sp.tick / 2 and abs(o["size"] - size) <= 0.02 * size:
                lad.update(sig=float(row["sig"]), pred=pred)
                return None                                # unchanged: keep the queue position
            if o:
                if not self._cancel(lad, "e4", t, minute=t - pd.Timedelta(minutes=1)):
                    return None                            # still resting: retry next minute
                if lad["status"] != "armed":               # it filled before the cancel: that ladder is now open
                    return None
                self.count("reprice")
            lad.update(sig=float(row["sig"]), pred=pred)
        if self.broker.live:
            bb = self._market_px(c, t)
            if not (np.isfinite(bb) and px < bb):         # market already at or below the level
                if lad is not None and not lad["orders"]:
                    self.state["ladders"].pop(lad["id"], None)
                self.count("skip_market_below")
                return None
        return c, pred, row, px, size, t, lad

    def _arm(self, c, pred, row, px, size, t, lad):
        sp = self.spec(c)
        if lad is not None and lad["id"] not in self.state["ladders"]:
            lad = None
        new = lad is None
        if new:
            self.state["seq"] += 1
            lad = dict(id=f"{c}-{self.state['seq']}", coin=c, status="armed", sig=float(row["sig"]), pred=pred,
                       S=self.signal_usd(c) * self.size_mult(pred), orders={}, tranches={}, pending=[], pnl=0.0)
            self.state["ladders"][lad["id"]] = lad
        lad["S"] = self.signal_usd(c) * self.size_mult(pred)     # the deeper rungs use the multiplier at the fill
        ok, err = self._place(lad, "e4", "BUY", px, size, t, open_rule=True)
        if not ok:
            if not lad["orders"]:
                self.state["ladders"].pop(lad["id"], None)
            return
        if new:
            ahead = None
            if self.broker.live and self.cfg.get("log_book", True):
                try:
                    a, reached = self.market.bids_ahead(sp.product, px)
                    ahead = round(a) if reached else f">{round(a)}"
                except Exception:
                    pass
            self.count("arm")
            self.log("arm", t=t, coin=c, ladder=lad["id"], px=px, usd=round(size * px), pred=round(pred, 1),
                     sigma_bp=round(float(row["sig"]) * 1e4, 1), usd_bids_ahead=ahead,
                     **({"mult": self.size_mult(pred)} if self.margin_rule else {}))

    # ---------- risk
    def _new_day(self, t):
        d = str(t.date())
        if self.state.get("day") != d:
            self.state["day"], self.state["day_start_equity"] = d, self.state["equity"]

    def _risk(self, t):
        m = self.mtm(t)
        self.state["peak"] = max(self.state.get("peak", m), m)
        if not self.state.get("dd_halt") and m < self.state["peak"] * (1 - self.cfg.get("max_drawdown", 0.25)):
            self.state["dd_halt"] = True
            self.log("halt", t=t, reason="drawdown stop: no new bids until reset (python bot/spot/run.py reset-halt)",
                     mtm=round(m, 2), peak=round(self.state["peak"], 2))

    def _halted(self, t):
        if any(os.path.exists(p) for p in (os.path.join(ROOT, "STOP"), os.path.join(self.state_dir, "STOP"))):
            return "stop file"
        if self.state.get("dd_halt"):
            return "drawdown stop"
        dd = self.state["equity"] / max(1e-9, self.state["day_start_equity"]) - 1
        if dd <= -self.cfg.get("daily_loss_limit", 0.08):
            if self.state.get("halted_day") != self.state["day"]:
                self.state["halted_day"] = self.state["day"]
                self.log("halt", t=t, reason="daily loss limit: no new bids until 00:00 UTC", drawdown=round(dd, 4))
            return "daily loss limit"
        return None

    # ---------- start-up, catch-up, shutdown
    def start(self):
        end = self.clock().floor("min")
        self.update_spot(end)
        self.log("backfill", t=end, minutes=WINDOW_MIN, coins=len(self.spot))
        for c in self.coins:
            self.spec(c)
        if self.broker.live:
            self.reconcile(end)
        self.catch_up(end)
        self.save()

    def catch_up(self, end):
        """After a gap (restart, or between paper jobs): no new bids were live, so cancel armed 4-sigma bids at the gap's
        start; then settle the gap minute by minute (paper) and run the exits that fell due."""
        last = self.state.get("last_minute")
        if not last:
            return
        start = pd.Timestamp(last)
        gap = int((end - start) / pd.Timedelta(minutes=1))
        if gap <= 1:
            return
        for lad in self.ladders():
            if lad["status"] == "armed":
                if self._cancel(lad, "e4", start) and lad["status"] == "armed":
                    self.state["ladders"].pop(lad["id"], None)
        if not self.broker.live:
            for m in pd.date_range(start, end - pd.Timedelta(minutes=2), freq="min"):
                self._settle(m, m + pd.Timedelta(minutes=1))
                self._manage(m + pd.Timedelta(minutes=1))
                self._refresh_tps(m + pd.Timedelta(minutes=1))
        else:
            self._settle(end - pd.Timedelta(minutes=1), end)
            self._manage(end)
            self._refresh_tps(end)
        self.log("catch_up", t=end, gap_minutes=gap,
                 open=[f"{l['coin']}:{'/'.join(sorted(l['tranches']))}" for l in self.ladders()])

    def reconcile(self, t):
        """Live: cancel the bot's own orders that the state lost track of, compare coin balances with the bot's open
        rungs, and log the account's fee tier. (Fills on known orders are booked by catch_up.)"""
        known = {o["id"] for lad in self.ladders() for o in lad["orders"].values()}
        try:
            for od in self.broker.open_orders():
                if str(od.get("client_order_id", "")).startswith(ORDER_TAG) and od.get("order_id") not in known:
                    self.broker.cancel_ids([od["order_id"]])
                    self.log("warning", t=t, msg="cancelled a bot order missing from state", order=od.get("order_id"),
                             product=od.get("product_id"), side=od.get("side"))
            bal = self.broker.balances()
            for c in self.coins:
                mine = sum(tr["size"] for lad in self.ladders(c) for tr in lad["tranches"].values())
                ex = sum(bal.get(c, (0.0, 0.0)))
                px = self.last_close(c, t)
                if np.isfinite(px) and abs(ex - mine) * px > self.cfg.get("reconcile_tol_usd", 25.0):
                    self.log("warning", t=t, msg="coin balance differs from the bot's open rungs: check before trading",
                             coin=c, exchange=ex, bot=mine)
            self.log("fee_tier", t=t, **self.broker.fee_tier())
        except Exception as err:
            self.log("error", t=t, error=f"reconcile failed: {err!r}"[:300])

    def fast_poll(self):
        """Live, between minute steps (every fast_poll_s seconds): find 4-sigma fills and place the deeper rungs and the
        take-profit at once, and retry deeper rungs the market had already passed. Trade-by-trade data (wick v4, S1):
        reacting within 1 s catches 87% of the deeper fills that come in the parent's own minute, 74% at 5 s, 0% at a
        minute."""
        t = self.clock()
        armed = [lad for lad in self.ladders() if lad["status"] == "armed" and "e4" in lad["orders"]]
        since = getattr(self, "_fills_since", None) or (t - pd.Timedelta(seconds=90))
        ids = None
        if armed and hasattr(self.broker, "filled_order_ids"):
            try:
                ids = self.broker.filled_order_ids(since - pd.Timedelta(seconds=30))
                self._fills_since = t
            except Exception:
                ids = None                                 # fall back to checking each bid (slower)
        for lad in armed:
            o = lad["orders"]["e4"]
            if ids is not None and o["id"] not in ids:
                continue
            for _, q, px, fee, done in self.broker.fills(lad["coin"], [("e4", o)], {}, t, 0.0):
                if q > 0:
                    o["filled"] += q
                    o["value"] += q * px
                    o["fees"] += fee or 0.0
                    self._apply_fill(lad, "e4", o, q, px, fee, t.floor("min"))
                if done:
                    lad["orders"].pop("e4", None)
            if lad["status"] == "open":
                self._refresh_tps(t.floor("min"))
                if not self._halted(t):
                    self._place_pending(lad, t.floor("min"))
                self.save()
        for lad in self.ladders():                         # deeper rungs waiting for the market to come back above them
            if lad["status"] == "open" and lad["pending"] and not lad.get("tp4_touched") \
                    and t < pd.Timestamp(lad["cancel_at"]) and not self._halted(t):
                before = list(lad["pending"])
                self._place_pending(lad, t.floor("min"))
                if lad["pending"] != before:
                    self.save()

    def cancel_all(self, flatten=False):
        """Cancel every bot order; with flatten=True also sell every open rung at market."""
        t = self.clock().floor("min")
        for lad in self.ladders():
            for key in list(lad["orders"]):
                self._cancel(lad, key, t)
            lad["pending"] = []
            if flatten:
                for k in list(lad["tranches"]):
                    self._exit_market(lad, k, t, "flatten")
            if not lad["orders"] and (lad["status"] == "armed" or not lad["tranches"]):
                self.state["ladders"].pop(lad["id"], None)
        self.save()
        left = [f"{l['coin']}:{k}" for l in self.ladders() for k in l["orders"]]
        self.log("cancel_all", t=t, flatten=flatten, open=[l["coin"] for l in self.ladders() if l["tranches"]],
                 unconfirmed_orders=left)
        return left

    @staticmethod
    def _hc(suffix=""):
        """Outside heartbeat (healthchecks.io URL in HEALTHCHECK_URL): alerts your phone if the pings stop."""
        url = os.environ.get("HEALTHCHECK_URL")
        if url:
            try:
                import requests
                requests.get(url.rstrip("/") + suffix, timeout=3)
            except Exception:
                pass

    def run(self, minutes):
        self._hc("/start")
        self.start()
        stop = time.time() + 60 * minutes
        poll = float(self.cfg.get("fast_poll_s", 1)) if self.broker.live else 0.0
        errors = 0
        while time.time() < stop:
            nxt = (math.floor(time.time() / 60) + 1) * 60 + 6       # 6 s after each minute closes
            while poll and time.time() < nxt - poll - 1:
                time.sleep(poll)
                try:
                    self.fast_poll()
                except Exception as err:
                    self.log("error", error=f"fast poll: {err!r}"[:300])
            time.sleep(max(0.0, nxt - time.time()))
            try:
                self.step()
                errors = 0
                self._hc()
            except Exception as err:
                errors += 1
                self.log("error", error=repr(err)[:500], consecutive=errors)
                self._hc("/fail")
                if errors >= self.cfg.get("max_consecutive_errors", 5) and self.broker.live:
                    try:                                    # blind for 5 minutes: pull the resting bids
                        for lad in self.ladders():
                            for key in [k for k, o in lad["orders"].items() if o["side"] == "BUY"]:
                                self._cancel(lad, key, self.clock().floor("min"))
                        self.log("warning", msg="resting bids cancelled after repeated errors")
                    except Exception:
                        pass
        self.save()
