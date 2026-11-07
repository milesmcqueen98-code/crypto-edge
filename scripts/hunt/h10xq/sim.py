#!/usr/bin/env python3
"""H10 (XQ) simulator: resting bids in Coinbase's BTC-, ETH- and USDT-quoted books (reports/hunt/h10xq/SPEC.md).

Inputs: potential fill events from events.py (each minute whose candle opened above the bid and traded through it by
>= 1 tick, for k = 3, 4, 6, with candle outcomes); print results from prints.py where fetched; the daily universe
(universe.py); daily USD closes (daily.parquet).

Sequencing (independent of costs):
- Bids rest at full size ($5K). Cash in the quote asset incl. resting bids <= C, so floor((C - cash in open positions)
  / $5K) bids rest; they go to the best-ranked books of the quote set (trailing 30-day median USD volume) holding no
  position. One position per pair; at most 6 open. A position blocks its pair until the minute after its exit.
  Cascade variant: bids live only while BTC-USD's 15-minute move to t-1 is below -2 sigma (3-day sigma, known at t-1).
- Fill: candles: the minute opened above the bid and its low is >= 1 tick through it; size = min($5K, theta x USD
  volume below the level while the price stays below it, each candle's volume spread evenly over its range, <= 15
  contiguous minutes). Where prints were fetched they replace both: the last print before t + 1 s above the bid and a
  print <= bid - 1 tick after t + 1 s; size cap from the prints strictly below the bid while the price stays below it.
  Fills under $100 are ignored (the bid keeps resting).
Exits:
- (a) post-only take-profit at 60% of the way back to F (next minute on, >= 1 tick through, size <= theta x volume
  above it over the holding window); the rest sold at market in the same book at the first traded minute >= H + 1
  minutes after the fill (its open), made worse by max(2 bp, 1.5 x the book's half-spread measured on prints).
- (b) market-sell X on X-USD and market-buy Q on Q-USD at the first print >= 2 s after the fill (prints), or at the
  next minute's opens (candles, where no prints were fetched).
Costs (common.py, mult = 2 for gates, 1 for information): spot maker on the bid and the take-profit; spot taker + the
2 bp half-spread on every market leg (exit (a) uses the book's measured half-spread when wider); USDT set: monthly
USD<->USDT conversion at maker both ways and USDT/USD marked daily; BTC/ETH set: perp short on the inventory with
perp maker fees on every change and funding (common.perp_funding_bp) daily; before Jul 2025 the perp is priced on spot.
Daily returns on C, P&L booked on the exit day, calendar days.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

DATA = os.path.join(ROOT, "data", "hunt", "h10xq")
HOLD0 = pd.Timestamp("2026-06-01")
BID_USD = 5000.0
MAX_OPEN = 6
MIN_FILL = 100.0
QSETS = ("USDT", "BTCETH")
EV_COLS = ["pair", "k", "ts", "lvl", "F", "sig", "tick", "thru_q", "n_below", "q_prev", "x_prev", "btc_z15", "tp",
           "hx_ts", "hx_px", "hq_ts", "hq_px"]


def universe(qset):
    U = pd.read_parquet(os.path.join(DATA, "universe.parquet"))
    return U[U.qset == qset].sort_values(["day", "rank"])


def load_events(mode, qset, k, H):
    hc = [f"tp_ts_{H}", f"tp_vol_q_{H}", f"mx_ts_{H}", f"mx_px_{H}", f"mx_q_{H}", f"q_at_tp_{H}"]
    pairs = set(universe(qset).pair)
    parts = []
    for f in sorted(glob.glob(os.path.join(DATA, "ev", f"{mode}_ev_*.parquet"))):
        d = pd.read_parquet(f, columns=EV_COLS + hc, filters=[("k", "==", float(k))])
        d = d[d.pair.isin(pairs)]
        if len(d):
            parts.append(d)
    E = pd.concat(parts, ignore_index=True)
    E.columns = EV_COLS + ["tp_ts", "tp_vol_q", "mx_ts", "mx_px", "mx_q", "q_at_tp"]
    if mode == "dev":
        E = E[E.ts < HOLD0]
    else:
        E = E[E.ts >= HOLD0]
    return E.sort_values(["ts", "pair"]).reset_index(drop=True)


def load_prints():
    fs = sorted(glob.glob(os.path.join(DATA, "prints", "res_*.parquet")))
    if not fs:
        return None
    P = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    P = P[P.fetched.astype(bool)].drop_duplicates(["pair", "ts", "k"], keep="last")
    return P.set_index(["pair", "k", "ts"])


class _Rows:
    """Column-oriented row store (a list of dicts per fill costs ~10x the memory)."""

    def __init__(self):
        self.cols, self.n = {}, 0

    def add(self, **kw):
        for k, v in kw.items():
            if k not in self.cols:
                self.cols[k] = [None] * self.n
            self.cols[k].append(v)
        self.n += 1
        for k, c in self.cols.items():
            if len(c) < self.n:
                c.append(None)

    def frame(self):
        return pd.DataFrame(self.cols) if self.n else pd.DataFrame()


def run(E, qset, C, theta=0.5, exit_="a", cascade=False, prints=None):
    """Sequence the bids. Returns the trade list (no costs applied)."""
    ranked = {d: list(g.pair) for d, g in universe(qset).groupby("day")}
    pkeys = set(prints.index) if prints is not None else set()
    opened, rel = {}, {}
    rows = _Rows()
    nmax = int(C // BID_USD)
    for e in E.itertuples(index=False):
        t = e.ts
        for p in [p for p, x in opened.items() if x < t]:
            del opened[p]
            rel.pop(p, None)
        if e.pair in opened or len(opened) >= MAX_OPEN:
            continue
        if cascade and not (e.btc_z15 < -2.0):
            continue
        used = sum(u for rl in rel.values() for tr, u in rl if tr >= t)
        nb = min(nmax, int((C - used + 1e-6) // BID_USD))
        avail = [p for p in ranked.get(t.floor("D"), []) if p not in opened]
        if e.pair not in avail[:nb]:
            continue
        key = (e.pair, float(e.k), t)
        src, thru_usd, fill_time = "candle", e.thru_q * e.q_prev, t
        pr = None
        if key in pkeys:
            pr = prints.loc[key]
            src = "print"
            if not bool(pr.confirmed):
                rows.add(pair=e.pair, ts=t, k=e.k, fill=0.0, src="print_reject")
                continue
            thru_usd = float(pr.thru_q) * e.q_prev
            fill_time = pr.fill_time
        size = min(BID_USD, theta * thru_usd)
        if not np.isfinite(size) or size < MIN_FILL:
            rows.add(pair=e.pair, ts=t, k=e.k, fill=0.0, src=src + "_small")
            continue
        r = dict(pair=e.pair, ts=t, k=e.k, lvl=e.lvl, F=e.F, sig=e.sig, tick=e.tick, fill=size, src=src,
                 q_prev=e.q_prev, disloc=float(np.log(e.lvl / e.F)), fill_time=fill_time)
        if exit_ == "a":
            tp_ok = pd.notna(e.tp_ts) and np.isfinite(e.q_at_tp)
            if pr is not None and tp_ok and pd.notna(pr.get("tp_ok", np.nan)):
                tp_ok = bool(pr.tp_ok)
            tp_usd = min(size, theta * e.tp_vol_q * e.q_at_tp) if tp_ok else 0.0
            rem = size - tp_usd
            if rem > 1e-9 and (pd.isna(e.mx_ts) or not np.isfinite(e.mx_px)):
                rows.add(pair=e.pair, ts=t, k=e.k, fill=0.0, src="no_exit")
                continue
            r.update(tp=e.tp, tp_usd=tp_usd, tp_ts=e.tp_ts if tp_usd > 0 else pd.NaT, q_tp=e.q_at_tp,
                     rem=rem, mx_ts=e.mx_ts if rem > 1e-9 else pd.NaT, mx_px=e.mx_px,
                     mx_q=e.mx_q if np.isfinite(e.mx_q) else e.q_prev)
            parts = [(r["tp_ts"], tp_usd)] if tp_usd > 0 else []
            if rem > 1e-9:
                parts.append((e.mx_ts, rem))
            x_final = max(x for x, _ in parts)
        else:
            if pr is not None and pd.notna(pr.get("hx_px", np.nan)) and pd.notna(pr.get("hq_px", np.nan)):
                hx_px, hq_px, hsrc = float(pr.hx_px), float(pr.hq_px), "print"
                x_final = max(pr.hx_time, pr.hq_time).floor("min")
            else:
                if pd.isna(e.hx_ts) or pd.isna(e.hq_ts) or not (np.isfinite(e.hx_px) and np.isfinite(e.hq_px)):
                    rows.add(pair=e.pair, ts=t, k=e.k, fill=0.0, src="no_hedge")
                    continue
                hx_px, hq_px, hsrc = e.hx_px, e.hq_px, "candle"
                x_final = max(e.hx_ts, e.hq_ts)
            r.update(hx_px=hx_px, hq_px=hq_px, hedge_src=hsrc, locked=float(np.log(hx_px / (e.lvl * hq_px))))
            parts = [(x_final, size)]
        r["exit_ts"] = x_final
        opened[e.pair] = x_final
        rel[e.pair] = parts
        rows.add(**r)
    return rows.frame()


def half_spreads(prints):
    """Per-pair median half-spread (bp) from print windows; pairs without prints get their quote set's median."""
    if prints is None or "hs_bp" not in prints:
        return {}
    h = prints.reset_index().groupby("pair").hs_bp.median()
    return h.dropna().to_dict()


def trade_pnl(T, exit_, mult, hs):
    """USD P&L per trade and the (day, amount) bookings."""
    T = T[T.fill > 0].copy()
    if not len(T):
        return T, pd.Series(dtype=float)
    mk = common.spot_cost_bp(False, mult) / 1e4
    tk = common.spot_cost_bp(True, mult) / 1e4
    if exit_ == "a":
        # scoring basis: common.py (2 bp half-spread on every spot market order); `hs` (measured half-spreads of the
        # secondary books, bp) adds max(0, 1.5 x hs - 2 bp) where given (realism check, not the scoring basis)
        hsp = T.pair.map(hs or {}).to_numpy(dtype=float)
        extra = np.nan_to_num(mult * np.maximum(0.0, 1.5 * hsp - common.SPOT_HALF_SPREAD_BP) / 1e4)
        tp_pnl = np.where(T.tp_usd > 0, T.tp_usd * ((T.tp / T.lvl) * (1 - mk) - 1) * (T.q_tp / T.q_prev), 0.0)
        mx_pnl = np.where(T.rem > 1e-9, T.rem * ((T.mx_px / T.lvl) * (1 - tk - extra) - 1) * (T.mx_q / T.q_prev), 0.0)
        entry = T.fill * mk
        T["pnl"] = tp_pnl + mx_pnl - entry
        T["exit_kind"] = np.where(T.rem <= 1e-9, "tp", np.where(T.tp_usd > 0, "tp+mkt", "mkt"))
        b1 = pd.Series(tp_pnl - entry, index=pd.DatetimeIndex(T.tp_ts.fillna(T.mx_ts)).floor("D"))
        b2 = pd.Series(mx_pnl, index=pd.DatetimeIndex(T.mx_ts.fillna(T.tp_ts)).floor("D"))
        book = pd.concat([b1, b2])
    else:
        qty = T.fill / (T.lvl * T.q_prev)
        T["pnl"] = qty * T.hx_px * (1 - tk) - qty * T.lvl * T.hq_px * (1 + tk) - T.fill * mk
        book = pd.Series(T.pnl.to_numpy(), index=pd.DatetimeIndex(T.exit_ts).floor("D"))
    return T, book.groupby(level=0).sum()


_PX = None


def usd_close():
    global _PX
    if _PX is None:
        D = pd.read_parquet(os.path.join(DATA, "daily.parquet"), columns=["ts", "product", "close"])
        D = D[D["product"].isin(["USDT-USD", "BTC-USD", "ETH-USD"])]
        _PX = D.pivot_table(index="ts", columns="product", values="close")
    return _PX


def inventory(qset, C, mult, days):
    """Daily USD P&L of holding the quote-asset inventory (costs and USDT/USD marks)."""
    days = pd.DatetimeIndex(days)
    P = usd_close()
    out = pd.Series(0.0, index=days)
    mk = common.spot_cost_bp(False, mult) / 1e4
    if qset == "USDT":
        u = P["USDT-USD"].reindex(pd.date_range(days.min() - pd.Timedelta(days=1), days.max())).ffill()
        out += C * (u / u.shift(1) - 1).reindex(days).fillna(0.0)
        for _, g in pd.Series(days, index=days).groupby([days.year, days.month]):
            out[g.iloc[0]] -= C * mk
            out[g.iloc[-1]] -= C * mk
        return out
    U = universe(qset)
    U = U[U["rank"] <= int(C // BID_USD)]
    eth = U.groupby("day").quote.apply(lambda q: float((q == "ETH").mean())).reindex(days).ffill().fillna(0.0)
    out -= C * common.perp_funding_bp(24, mult) / 1e4
    prev = None
    for i, d in enumerate(days):
        if prev is None or (d - days[i - 1]).days > 1:
            prev = np.zeros(2)
        cur = np.array([1 - eth[d], eth[d]])
        for j, coin in enumerate(("BTC", "ETH")):
            dl = abs(cur[j] - prev[j]) * C
            if dl > 0:
                out[d] -= dl * (mk + common.perp_cost_bp(coin, float(P[f"{coin}-USD"].asof(d)), False, mult) / 1e4)
        prev = cur
        if i == len(days) - 1 or (days[i + 1] - d).days > 1:
            for j, coin in enumerate(("BTC", "ETH")):
                out[d] -= prev[j] * C * (mk + common.perp_cost_bp(coin, float(P[f"{coin}-USD"].asof(d)), False,
                                                                     mult) / 1e4)
            prev = None
    return out


def daily_returns(T, qset, C, exit_, mult, days, hs):
    T2, book = trade_pnl(T, exit_, mult, hs)
    days = pd.DatetimeIndex(days)
    inv = inventory(qset, C, mult, days)
    r = (book.reindex(days).fillna(0.0) + inv) / C
    return r, T2, dict(trade_usd=float(book.reindex(days).fillna(0).sum()), inv_usd=float(inv.sum()))
