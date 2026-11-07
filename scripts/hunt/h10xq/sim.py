#!/usr/bin/env python3
"""H10 (XQ) simulator: resting bids in Coinbase's BTC-, ETH- and USDT-quoted books (reports/hunt/h10xq/SPEC.md).

Inputs: potential fill events from events.py (every minute whose candle traded through the bid by >= 1 tick after
opening above it, for k = 3, 4, 6, with candle outcomes), optional print overrides (prints.py), the daily universe
(universe.py) and daily USD closes (daily.parquet).

Rules (SPEC + pre-registration):
- Bids rest at full size ($5K each). Cash in the quote asset incl. resting bids <= sleeve capital C, so the number of
  resting bids is floor((C - cash in open positions) / $5K); they go to the best-ranked books of the quote set (rank =
  trailing 30-day median USD volume, universe.py) that hold no position. One position per pair; at most 6 open (no
  bids while 6 are open). Cascade variant: bids live only while BTC-USD's 15-minute move (to t-1) is below -2 sigma.
- Fill size = min($5K, theta x USD volume traded beyond the level while the price stays beyond it): candles spread
  volume evenly over each minute's range (<= 15 contiguous minutes); prints, where fetched, replace the candle fill:
  a fill needs a print >= 1 tick below the level, and the size cap uses the prints strictly below the level while the
  price stays below it. A fill under $100 is ignored (the bid keeps resting).
- Exit (a): post-only take-profit at 60% of the way back to F (from the next minute, trade-through by one tick, size
  <= theta x the volume above it), the rest at market after H minutes (next traded minute's open). Same book.
- Exit (b): at the next minute's open, market-sell X on X-USD and market-buy Q on Q-USD (candles; deep books).
- Costs: common.spot_cost_bp (VIP 1 maker, taker + 2 bp half-spread) on every spot leg; mult = 2 for the gates.
- Quote inventory: USDT set holds C in USDT (USD->USDT on the first and USDT->USD on the last day of each month at VIP-1
  maker; daily USDT/USD mark-to-market). BTC/ETH set holds BTC/ETH worth C (split by the day's bid slots) and shorts
  the same notional of the BTC/ETH perp: spot maker and perp maker (common.perp_cost_bp) on every change of the hedge,
  funding common.perp_funding_bp(24) a day on the notional (before Jul 2025: priced on spot prices, flagged).
- Daily returns on C, P&L booked on the exit day; calendar days; 0 when idle (inventory costs apply every day).
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
TP_FRAC = 0.6
SETS = {"USDT": ("USDT",), "BTCETH": ("BTC", "ETH")}
EV_COLS = ["pair", "k", "ts", "lvl", "F", "sig", "tick", "thru_q", "n_below", "q_prev", "x_prev", "btc_z15", "tp",
           "hx_ts", "hx_px", "hq_ts", "hq_px"]


def era_days(mode):
    import gates
    d = gates.ERA_DAYS
    return d[d < HOLD0] if mode == "dev" else d


def load_events(mode, qset, k, H):
    cols = EV_COLS + [f"tp_ts_{H}", f"tp_vol_q_{H}", f"mx_ts_{H}", f"mx_px_{H}", f"mx_q_{H}", f"q_at_tp_{H}"]
    U = pd.read_parquet(os.path.join(DATA, "universe.parquet"))
    pairs = set(U[U.qset == qset].pair)
    parts = []
    for f in sorted(glob.glob(os.path.join(DATA, "ev", f"{mode}_ev_*.parquet"))):
        d = pd.read_parquet(f, columns=cols, filters=[("k", "==", float(k))])
        d = d[d.pair.isin(pairs)]
        if len(d):
            parts.append(d)
    E = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)
    E = E.rename(columns={f"tp_ts_{H}": "tp_ts", f"tp_vol_q_{H}": "tp_vol_q", f"mx_ts_{H}": "mx_ts",
                          f"mx_px_{H}": "mx_px", f"mx_q_{H}": "mx_q", f"q_at_tp_{H}": "q_at_tp"})
    if mode == "dev":
        E = E[E.ts < HOLD0]
    return E.sort_values(["ts", "pair"]).reset_index(drop=True)


def daily_close():
    D = pd.read_parquet(os.path.join(DATA, "daily.parquet"), columns=["ts", "product", "close", "open"])
    return D.pivot_table(index="ts", columns="product", values="close")


def simulate(E, qset, C, theta=0.5, mult=2.0, exit_="a", cascade=False, prints=None, days=None):
    """Returns (trades, daily P&L in USD over `days`, info)."""
    U = pd.read_parquet(os.path.join(DATA, "universe.parquet"))
    U = U[U.qset == qset].sort_values(["day", "rank"])
    ranked = {d: list(g.pair) for d, g in U.groupby("day")}
    mk = common.spot_cost_bp(False, mult) / 1e4
    tk = common.spot_cost_bp(True, mult) / 1e4
    if prints is not None:
        prints = prints.set_index(["pair", "k", "ts"])
    opened, cash_pos = {}, {}           # pair -> final exit time ; pair -> [(release time, usd)]
    rows = []
    n_bids_max = int(C // BID_USD)
    for e in E.itertuples(index=False):
        t = e.ts
        for p in [p for p, x in opened.items() if x <= t]:
            del opened[p]
            cash_pos.pop(p, None)
        used = 0.0
        for p, rel in cash_pos.items():
            used += sum(u for tr, u in rel if tr > t)
        if e.pair in opened or len(opened) >= MAX_OPEN:
            continue
        if cascade and not (e.btc_z15 < -2.0):
            continue
        day = t.floor("D")
        avail = [p for p in ranked.get(day, []) if p not in opened]
        nb = min(n_bids_max, int((C - used + 1e-6) // BID_USD))
        if e.pair not in avail[:nb]:
            continue
        thru_usd = e.thru_q * e.q_prev
        src = "candle"
        if prints is not None:
            key = (e.pair, float(e.k), t)
            if key in prints.index:
                pr = prints.loc[key]
                src = "print"
                if not bool(pr.confirmed):
                    rows.append(dict(pair=e.pair, ts=t, fill=0.0, src="print_reject"))
                    continue
                thru_usd = float(pr.thru_q) * e.q_prev
        size = min(BID_USD, theta * thru_usd)
        if not np.isfinite(size) or size < MIN_FILL:
            continue
        r = dict(pair=e.pair, ts=t, k=e.k, lvl=e.lvl, F=e.F, sig=e.sig, fill=size, src=src,
                 disloc=np.log(e.lvl / e.F))
        if exit_ == "a":
            tp_usd = 0.0
            if pd.notna(e.tp_ts) and np.isfinite(e.q_at_tp):
                tp_usd = min(size, theta * e.tp_vol_q * e.q_at_tp)
            rem = size - tp_usd
            pnl_tp = tp_usd * ((e.tp / e.lvl) * (1 - mk) - 1) * (e.q_at_tp / e.q_prev) if tp_usd > 0 else 0.0
            if rem > 0:
                if pd.isna(e.mx_ts) or not np.isfinite(e.mx_px):
                    continue                                  # no exit price within a day: drop (rare, reported)
                pnl_mx = rem * ((e.mx_px / e.lvl) * (1 - tk) - 1) * (e.mx_q / e.q_prev if np.isfinite(e.mx_q) else 1)
            else:
                pnl_mx = 0.0
            entry = size * mk
            x_final = max([x for x, a in ((e.tp_ts, tp_usd), (e.mx_ts, rem)) if a > 0])
            rel = []
            if tp_usd > 0:
                rel.append((e.tp_ts, tp_usd))
            if rem > 0:
                rel.append((e.mx_ts, rem))
            r.update(tp_usd=tp_usd, pnl_tp=pnl_tp, pnl_mx=pnl_mx, entry=entry, tp_ts=e.tp_ts, mx_ts=e.mx_ts,
                     pnl=pnl_tp + pnl_mx - entry, exit_ts=x_final)
            book = [(e.tp_ts if tp_usd > 0 else e.mx_ts, pnl_tp - entry)]
            if rem > 0:
                book.append((e.mx_ts, pnl_mx))
        else:
            if pd.isna(e.hx_ts) or pd.isna(e.hq_ts) or not (np.isfinite(e.hx_px) and np.isfinite(e.hq_px)):
                continue
            qty = size / (e.lvl * e.q_prev)
            sell = qty * e.hx_px
            buy = qty * e.lvl * e.hq_px
            pnl = sell * (1 - tk) - buy * (1 + tk) - size * mk
            x_final = max(e.hx_ts, e.hq_ts)
            rel = [(x_final, size)]
            r.update(pnl=pnl, exit_ts=x_final, locked=np.log(e.hx_px / (e.lvl * e.hq_px)))
            book = [(x_final, pnl)]
        opened[e.pair] = x_final
        cash_pos[e.pair] = rel
        r["book"] = book
        rows.append(r)
    T = pd.DataFrame(rows)
    if len(T) and "book" in T:
        T = T[T.fill > 0].copy() if "fill" in T else T
    bk = [(ts.floor("D"), v) for b in (T.book if len(T) else []) for ts, v in b]
    daily = pd.Series([v for _, v in bk], index=pd.DatetimeIndex([d for d, _ in bk]), dtype=float).groupby(level=0).sum()
    inv = inventory(qset, C, mult, days)
    days = pd.DatetimeIndex(days)
    pnl = daily.reindex(days).fillna(0.0) + inv.reindex(days).fillna(0.0)
    info = dict(trades=int(len(T)), fill_usd=float(T.fill.sum()) if len(T) else 0.0,
                trade_pnl=float(T.pnl.sum()) if len(T) else 0.0, inv_pnl=float(inv.reindex(days).sum()))
    return T, pnl, info


def slot_split(qset, C):
    """BTC/ETH set: share of the day's bid slots (top floor(C/5K) books) quoted in ETH."""
    U = pd.read_parquet(os.path.join(DATA, "universe.parquet"))
    U = U[(U.qset == qset) & (U["rank"] <= int(C // BID_USD))]
    return U.groupby("day").apply(lambda g: float((g.quote == "ETH").mean()), include_groups=False)


def inventory(qset, C, mult, days):
    """Daily USD P&L of holding the quote inventory (costs, USDT/USD mark-to-market)."""
    days = pd.DatetimeIndex(days)
    P = daily_close()
    out = pd.Series(0.0, index=days)
    mk = common.spot_cost_bp(False, mult) / 1e4
    if qset == "USDT":
        u = P["USDT-USD"].reindex(pd.date_range(days.min() - pd.Timedelta(days=1), days.max())).ffill()
        ret = (u / u.shift(1) - 1).reindex(days).fillna(0.0)
        out += C * ret
        mon = pd.Series(days, index=days).groupby([days.year, days.month])
        for _, g in mon:
            out[g.iloc[0]] -= C * mk
            out[g.iloc[-1]] -= C * mk
        return out
    share_eth = slot_split(qset, C).reindex(days).ffill().fillna(0.0)
    fund = C * common.perp_funding_bp(24, mult) / 1e4
    out -= fund
    prev = None
    for i, d in enumerate(days):
        cur = np.array([1 - share_eth[d], share_eth[d]])
        start = prev is None or (d - days[i - 1]).days > 1
        if start:
            prev = np.zeros(2)
        dlt = np.abs(cur - prev) * C
        for j, coin in enumerate(("BTC", "ETH")):
            if dlt[j] > 0:
                px = P[f"{coin}-USD"].asof(d)
                out[d] -= dlt[j] * (mk + common.perp_cost_bp(coin, px, False, mult) / 1e4)
        prev = cur
        end = i == len(days) - 1 or (days[i + 1] - d).days > 1
        if end:
            for j, coin in enumerate(("BTC", "ETH")):
                if prev[j] > 0:
                    px = P[f"{coin}-USD"].asof(d)
                    out[d] -= prev[j] * C * (mk + common.perp_cost_bp(coin, px, False, mult) / 1e4)
            prev = None
    return out
