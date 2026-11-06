"""Minute engine for the AI-filtered resting-bid dip buyer on Coinbase US perps.

Every minute, a few seconds after the minute closes:
  1. append the newest spot candles (BTC + universe) to an 11-day rolling window
  2. paper: settle the minute that just closed against the futures candle (trade-through rule);
     live: poll the exchange for fills
  3. compute edge.wick.panel -> level and features for the minute now starting; model -> keep bid or not
  4. manage orders: entry bid (post-only) when flat and the model says yes; take-profit (post-only) when
     long; market exit when the hold limit is reached; risk limits on top
State persists in a JSON file so a restart (or the next GitHub Actions job) picks up where it left off.
"""
import json
import math
import os
import time
import uuid
from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd

from edge import wick
from bot import market

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOW_MIN = 11 * 1440


def now_utc():
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


@dataclass
class Spec:
    product: str
    size: float        # coin per contract
    tick: float        # USD


def load_specs():
    df = pd.read_csv(os.path.join(ROOT, "reports", "cfm_products.csv"))
    df = df[df.expiry_type == "PERPETUAL"]
    out = {}
    for r in df.itertuples():
        # futures units throughout (1000PEPE is quoted per 1000 PEPE): order prices come from the spot level x the
        # futures/spot price ratio, so they land in futures units automatically
        out[r.root] = Spec(r.product_id, float(r.contract_size), float(r.price_increment))
    return out


class Log:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def __call__(self, kind, **kw):
        rec = {"ts": now_utc().isoformat(), "kind": kind, **kw}
        with open(self.path, "a") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        print(json.dumps(rec, default=str), flush=True)


class PaperBroker:
    """Fills post-only limits only when the futures minute trades through them by one tick."""

    def __init__(self, state, specs, fee_bp=2.0):
        self.s, self.specs, self.fee_bp = state, specs, fee_bp

    def place(self, coin, side, px, contracts, kind):
        oid = f"paper-{uuid.uuid4().hex[:10]}"
        self.s["orders"][coin] = dict(id=oid, side=side, px=px, contracts=contracts, kind=kind,
                                      active_from=(now_utc().floor("min")).isoformat())
        return oid

    def cancel(self, coin):
        self.s["orders"].pop(coin, None)
        return 0.0

    def settle(self, coin, bar, minute):
        """bar: futures candle (open, high, low, close) for `minute` (NaN when no futures trade)."""
        o = self.s["orders"].get(coin)
        if not o or pd.Timestamp(o["active_from"]) > minute or not np.isfinite(bar["low"]):
            return None
        tick = self.specs[coin].tick
        if o["side"] == "BUY" and bar["open"] > o["px"] and bar["low"] <= o["px"] - tick:
            self.s["orders"].pop(coin)
            return dict(side="BUY", px=o["px"], contracts=o["contracts"], kind=o["kind"], maker=True)
        if o["side"] == "SELL" and bar["high"] >= o["px"] + tick:
            self.s["orders"].pop(coin)
            return dict(side="SELL", px=o["px"], contracts=o["contracts"], kind=o["kind"], maker=True)
        return None

    def market_exit(self, coin, contracts, ref_px, half_spread):
        return dict(side="SELL", px=ref_px - half_spread, contracts=contracts, kind="time", maker=False)


class LiveBroker:
    """Coinbase Advanced Trade (Coinbase Financial Markets futures account) via the official SDK.
    Needs COINBASE_API_KEY / COINBASE_API_SECRET (CDP key with trade permission) in the environment."""

    def __init__(self, state, specs):
        from coinbase.rest import RESTClient  # pip install coinbase-advanced-py
        self.c = RESTClient(api_key=os.environ["COINBASE_API_KEY"], api_secret=os.environ["COINBASE_API_SECRET"])
        self.s, self.specs = state, specs

    def place(self, coin, side, px, contracts, kind):
        sp = self.specs[coin]
        dec = max(0, -int(math.floor(math.log10(sp.tick))))
        args = dict(client_order_id=uuid.uuid4().hex, product_id=sp.product, base_size=str(int(contracts)),
                    limit_price=f"{px:.{dec}f}", post_only=True)
        r = self.c.limit_order_gtc_buy(**args) if side == "BUY" else self.c.limit_order_gtc_sell(**args)
        r = r.to_dict() if hasattr(r, "to_dict") else r
        if not r.get("success"):
            raise RuntimeError(f"order rejected: {r}")
        oid = r["success_response"]["order_id"]
        self.s["orders"][coin] = dict(id=oid, side=side, px=px, contracts=contracts, kind=kind,
                                      active_from=now_utc().isoformat())
        return oid

    def cancel(self, coin):
        """Cancel and return how many contracts of it had already filled (partial fills)."""
        o = self.s["orders"].pop(coin, None)
        if not o:
            return 0.0
        self.c.cancel_orders(order_ids=[o["id"]])
        r = self.c.get_order(o["id"])
        r = r.to_dict() if hasattr(r, "to_dict") else r
        return float(r.get("order", {}).get("filled_size") or 0)

    def positions(self):
        r = self.c.list_futures_positions()
        r = r.to_dict() if hasattr(r, "to_dict") else r
        return {p.get("product_id"): float(p.get("number_of_contracts") or 0) for p in r.get("positions", [])}

    def settle(self, coin, bar, minute):
        o = self.s["orders"].get(coin)
        if not o:
            return None
        r = self.c.get_order(o["id"])
        r = r.to_dict() if hasattr(r, "to_dict") else r
        od = r.get("order", {})
        filled = float(od.get("filled_size") or 0)
        if od.get("status") == "FILLED" or (od.get("status") in ("CANCELLED", "EXPIRED") and filled > 0):
            self.s["orders"].pop(coin)
            return dict(side=o["side"], px=float(od.get("average_filled_price") or o["px"]), contracts=filled,
                        kind=o["kind"], maker=True, fee=float(od.get("total_fees") or 0))
        if od.get("status") in ("CANCELLED", "EXPIRED", "FAILED"):
            self.s["orders"].pop(coin)
        return None

    def market_exit(self, coin, contracts, ref_px, half_spread):
        r = self.c.market_order_sell(client_order_id=uuid.uuid4().hex, product_id=self.specs[coin].product,
                                     base_size=str(int(contracts)))
        r = r.to_dict() if hasattr(r, "to_dict") else r
        oid = r.get("success_response", {}).get("order_id")
        time.sleep(1.0)
        od = (self.c.get_order(oid).to_dict() if oid else {}).get("order", {})
        return dict(side="SELL", px=float(od.get("average_filled_price") or ref_px), contracts=contracts,
                    kind="time", maker=False, fee=float(od.get("total_fees") or 0))


@dataclass
class Engine:
    mode: str = "paper"
    cfg: dict = field(default_factory=dict)
    state_path: str = os.path.join(ROOT, "paper", "state.json")
    log_path: str = os.path.join(ROOT, "paper", "events.jsonl")

    def __post_init__(self):
        meta = json.load(open(os.path.join(ROOT, "bot", "model_meta.json")))
        self.meta = meta
        self.model = lgb.Booster(model_file=os.path.join(ROOT, "bot", "model.txt"))
        self.coins = meta["coins"]
        self.codes = {c: i for i, c in enumerate(sorted(self.coins))}
        self.thr = meta["threshold"]
        self.specs = load_specs()
        self.log = Log(self.log_path)
        self.state = self._load_state()
        self.broker = PaperBroker(self.state, self.specs) if self.mode == "paper" else LiveBroker(self.state, self.specs)
        self.spot = {}

    # ---------- state
    def _load_state(self):
        if os.path.exists(self.state_path):
            return json.load(open(self.state_path))
        return dict(positions={}, orders={}, equity=self.cfg.get("capital", 10000.0), day=None, day_start_equity=None,
                    halted_day=None, last_minute=None)

    def save(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        tmp = self.state_path + ".tmp"
        json.dump(self.state, open(tmp, "w"), indent=1, default=str)
        os.replace(tmp, self.state_path)

    # ---------- data
    def backfill(self):
        end = now_utc().floor("min")
        start = end - pd.Timedelta(minutes=WINDOW_MIN)
        for c in ["BTC"] + self.coins:
            self.spot[c] = market.spot_candles(c, start, end)
        self.log("backfill", minutes=WINDOW_MIN, coins=len(self.spot))

    def update_spot(self, end):
        for c in ["BTC"] + self.coins:
            df = self.spot[c]
            start = (df.index.max() + pd.Timedelta(minutes=1)) if len(df) else end - pd.Timedelta(minutes=WINDOW_MIN)
            new = market.spot_candles(c, start, end)
            df = pd.concat([df, new])
            self.spot[c] = df[~df.index.duplicated(keep="last")].loc[end - pd.Timedelta(minutes=WINDOW_MIN):]

    def arrays(self, upto):
        """Minute grid ending at `upto` (the minute now starting, with no data yet)."""
        idx = pd.date_range(upto - pd.Timedelta(minutes=WINDOW_MIN - 1), upto, freq="min")
        cf, vol, last = {}, {}, {}
        for c, df in self.spot.items():
            d = df[df.volume > 0].reindex(idx)
            cf[c] = d.close.ffill(limit=30).to_numpy(np.float64)
            vol[c] = d.volume.fillna(0.0).to_numpy(np.float64)
            last[c] = cf[c][-2] if len(d) > 1 else np.nan            # spot close at t-1 (forward-filled)
        return idx, cf, vol, last

    # ---------- one minute
    def step(self):
        t = now_utc().floor("min")                        # the minute now starting
        prev = t - pd.Timedelta(minutes=1)
        self.update_spot(t)
        self._new_day(t)
        # settle the minute that just closed
        fut = {}
        for c in self.coins:
            if c in self.state["orders"] or c in self.state["positions"]:
                bar = market.futures_candles(self.specs[c].product, prev, t)
                b = dict(open=np.nan, high=np.nan, low=np.nan, close=np.nan) if bar.empty else bar.iloc[-1].to_dict()
                fut[c] = b
                fill = self.broker.settle(c, b, prev)
                if fill:
                    self._on_fill(c, fill, prev)
        idx, cf, vol, last = self.arrays(t)
        pn = wick.panel(cf, vol, self.coins, idx, coin_codes=self.codes)
        cands = []
        for c in self.coins:
            row = pn[c].iloc[-1]
            pos = self.state["positions"].get(c)
            if pos:
                self._manage_position(c, pos, t)
                if c in self.state["positions"]:
                    continue
            ok = all(np.isfinite(row[k]) for k in ("level", "sig", "z_res60", "bid_depth_bp"))
            pred = float(self.model.predict(row[wick.FEATS].to_numpy(np.float64)[None, :])[0]) if ok else np.nan
            if ok and pred > self.thr:
                cands.append((pred, c, row))
            elif c in self.state["orders"]:
                self.broker.cancel(c)
                self.log("cancel", coin=c, pred=None if not ok else round(pred, 1))
        # never risk more positions than slots: bids only for the best-predicted coins
        slots = 0 if self._halted(t) else self.cfg.get("max_positions", 6) - len(self.state["positions"])
        cands.sort(key=lambda x: -x[0])
        for rank, (pred, c, row) in enumerate(cands):
            sp = self.specs[c]
            px = np.nan
            if rank < slots:
                bid, ask = market.book_top(sp.product)
                if np.isfinite(bid) and np.isfinite(ask) and np.isfinite(last[c]):
                    basis = ((bid + ask) / 2) / last[c]
                    px = float(wick.round_down(row.level * basis, sp.tick))
                    if px >= bid:                    # market already below the level: no order this minute
                        px = np.nan
            if not np.isfinite(px):
                if c in self.state["orders"]:
                    self.broker.cancel(c)
                    self.log("cancel", coin=c, pred=round(pred, 1), reason="no slot or market below level")
                continue
            notional = self.cfg.get("notional_frac", 0.25) * self.state["equity"]
            contracts = max(1, int(notional // (sp.size * px)))
            o = self.state["orders"].get(c)
            if o and abs(o["px"] - px) < sp.tick / 2 and o["contracts"] == contracts:
                continue
            if o:
                self.broker.cancel(c)
            oid = self.broker.place(c, "BUY", px, contracts, "entry")
            self.log("bid", coin=c, px=px, contracts=contracts, pred=round(pred, 1), thr=round(self.thr, 1),
                     sigma_bp=round(float(row.sig) * 1e4, 1), depth_bp=round(float(row.bid_depth_bp), 1), oid=oid)
            self.state.setdefault("pending_sig", {})[c] = float(row.sig)
        if t.minute % 30 == 0:
            self.log("heartbeat", equity=round(self.state["equity"], 2), positions=list(self.state["positions"]),
                     orders={k: v["kind"] for k, v in self.state["orders"].items()})
        self.state["last_minute"] = t.isoformat()
        self.save()

    def _on_fill(self, c, fill, minute):
        sp = self.specs[c]
        fee = fill.get("fee")
        if fee is None:                                   # paper: fee model from config (bp of notional)
            bp = self.cfg.get("fee_bp_maker", 2.0) if fill["maker"] else self.cfg.get("fee_bp_taker", 2.0)
            fee = fill["px"] * sp.size * fill["contracts"] * bp / 1e4
        if fill["side"] == "BUY":
            sig = self.state.get("pending_sig", {}).get(c, np.nan)
            tp = float(wick.round_down(fill["px"] * math.exp(wick.THETA * wick.K * sig), sp.tick))
            self.state["positions"][c] = dict(contracts=fill["contracts"], entry_px=fill["px"], entry_ts=minute.isoformat(),
                                              # research holds to the close of minute entry+H; the exit
                                              # order goes out at the start of the following minute
                                              exit_due=(minute + pd.Timedelta(minutes=wick.H + 1)).isoformat(), tp_px=tp,
                                              fees=fee)
            self.log("fill_entry", coin=c, px=fill["px"], contracts=fill["contracts"], tp=tp, fee=round(fee, 4))
            self.broker.place(c, "SELL", tp, fill["contracts"], "tp")
        else:
            pos = self.state["positions"].pop(c, None)
            if not pos:
                return
            pnl = (fill["px"] - pos["entry_px"]) * sp.size * fill["contracts"] - pos["fees"] - fee
            self.state["equity"] += pnl
            self.log("fill_exit", coin=c, kind=fill["kind"], px=fill["px"], entry_px=pos["entry_px"],
                     contracts=fill["contracts"], pnl=round(pnl, 2),
                     net_bp=round(pnl / (pos["entry_px"] * sp.size * fill["contracts"]) * 1e4, 1),
                     equity=round(self.state["equity"], 2))

    def _manage_position(self, c, pos, t):
        sp = self.specs[c]
        if t >= pd.Timestamp(pos["exit_due"]):
            partial = self.broker.cancel(c) if c in self.state["orders"] else 0.0
            if partial:                                     # part of the take-profit filled before the cancel
                pos["contracts"] -= partial
                pos["fees"] *= pos["contracts"] / (pos["contracts"] + partial)
                pnl = (pos["tp_px"] - pos["entry_px"]) * sp.size * partial
                self.state["equity"] += pnl
                self.log("fill_exit", coin=c, kind="tp_partial", px=pos["tp_px"], entry_px=pos["entry_px"],
                         contracts=partial, pnl=round(pnl, 2), equity=round(self.state["equity"], 2))
                if pos["contracts"] <= 0:
                    self.state["positions"].pop(c, None)
                    return
            bid, ask = market.book_top(sp.product)
            ref = (bid + ask) / 2 if np.isfinite(bid) and np.isfinite(ask) else pos["entry_px"]
            hs = (ask - bid) / 2 if np.isfinite(bid) and np.isfinite(ask) else sp.tick
            fill = self.broker.market_exit(c, pos["contracts"], ref, hs)
            self._on_fill(c, fill, t)
        elif c not in self.state["orders"]:
            self.broker.place(c, "SELL", pos["tp_px"], pos["contracts"], "tp")

    def _new_day(self, t):
        d = str(t.date())
        if self.state.get("day") != d:
            self.state["day"], self.state["day_start_equity"] = d, self.state["equity"]

    def _halted(self, t):
        if os.path.exists(os.path.join(ROOT, "STOP")):
            return True
        dd = self.state["equity"] / max(1e-9, self.state["day_start_equity"] or self.state["equity"]) - 1
        if dd <= -self.cfg.get("daily_loss_limit", 0.05):
            if self.state.get("halted_day") != self.state["day"]:
                self.state["halted_day"] = self.state["day"]
                self.log("halt", reason="daily loss limit", drawdown=round(dd, 4))
            return True
        return False

    def catch_up(self):
        """Paper only: settle open positions over any gap since the last run (entry bids did not exist then)."""
        last = self.state.get("last_minute")
        if self.mode != "paper" or not last:
            return
        start, end = pd.Timestamp(last), now_utc().floor("min")
        for c in [k for k, o in self.state["orders"].items() if o["kind"] == "entry"]:
            self.state["orders"].pop(c)
        for c, pos in list(self.state["positions"].items()):
            bars = market.futures_candles(self.specs[c].product, start, end)
            if c not in self.state["orders"]:
                self.broker.place(c, "SELL", pos["tp_px"], pos["contracts"], "tp")
                self.state["orders"][c]["active_from"] = start.isoformat()
            for minute, b in bars.iterrows():
                fill = self.broker.settle(c, b.to_dict(), minute)
                if fill:
                    self._on_fill(c, fill, minute)
                    break
                if minute >= pd.Timestamp(pos["exit_due"]):
                    self.state["orders"].pop(c, None)
                    self._on_fill(c, dict(side="SELL", px=float(b["close"]) - self.specs[c].tick,
                                          contracts=pos["contracts"], kind="time", maker=False), minute)
                    break
        self.log("catch_up", gap_minutes=int((end - start) / pd.Timedelta(minutes=1)),
                 open_positions=list(self.state["positions"]))

    def reconcile(self):
        """Live only: compare the exchange's futures positions with the bot's state and log any difference."""
        if self.mode != "live":
            return
        try:
            ex = self.broker.positions()
        except Exception as err:
            self.log("error", error=f"reconcile failed: {err!r}")
            return
        mine = {self.specs[c].product: p["contracts"] for c, p in self.state["positions"].items()}
        for pid in set(ex) | set(mine):
            if abs(ex.get(pid, 0) - mine.get(pid, 0)) > 1e-9:
                self.log("warning", msg="position mismatch: check manually before continuing", product=pid,
                         exchange=ex.get(pid, 0), bot=mine.get(pid, 0))

    def run(self, minutes):
        self.backfill()
        self.catch_up()
        self.reconcile()
        end = time.time() + 60 * minutes
        while time.time() < end:
            nxt = (math.floor(time.time() / 60) + 1) * 60 + 6        # 6 s after each minute closes
            time.sleep(max(0.0, nxt - time.time()))
            try:
                self.step()
            except Exception as err:                                  # keep running; log and retry next minute
                self.log("error", error=repr(err))
        self.save()
