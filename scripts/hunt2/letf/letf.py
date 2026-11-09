#!/usr/bin/env python3
"""Edge hunt 2, LETF (Path B): leveraged-ETF rebalancing flow into the US close (reports/hunt2/letf/SPEC.md).

The model. Everything is anchored on each NYSE trading day's close time Tc (16:00 ET, 13:00 ET on early closes; the
NYSE calendar from pandas_market_calendars, ET converted to UTC minutes). Candles are labelled by their start minute;
P(x) is the close of the candle labelled x (the last one at or before x, at most 30 minutes old).

  signal  r = ln(P(Tc - 16 min) / P(previous trading day's Tc))           [15:44 vs the previous 16:00]
          sigma = std of the last 30 trading-day close-to-close log returns, ending at the previous close
          signal when |r| >= k * sigma, the asset's 2x/-2x ETF complex has a trailing 20-trading-day mean dollar
          volume (to d-1) >= $50M, and one perp contract is worth >= $150 at P(Tc - 16 min). Spot candles.
  size    1.0 x sleeve capital / (number of assets signalling that day), whole contracts sized at P(Tc - 16 min)
  legs    mom   taker sign(r) at the open of Tc - 14 (15:46), exit at the open of Tc (16:00)
          rev   taker -sign(r) at the open of Tc + 1 (16:01), exit at the open of Tc + 60 (17:00)
          mkr   post-only order opposite the flow (a bid on down days, an offer on up days) 10 bp beyond P(Tc - 6)
                (the 15:54 close), working Tc - 5 .. Tc - 1 (15:55-15:59), cancelled at Tc; a post-only take-profit at
                P(Tc - 6) works from the minute after a fill to Tc + 59; the rest exits taker at the open of Tc + 60.
  fills   taker: the open of the first candle in [target, target + 5 min) (entries; none = no trade) or
          [target, target + 30 min) (exits; none = the last close before the target, counted); the cost of a taker
          side (costs.perp_cost_bp, taker=True) includes 1.5x the measured half-spread.
          resting: a candle fills only beyond the level by at least one tick (the perp's tick); size <= theta x the
          candle's volume beyond the level, the volume spread evenly over the candle's range; post-only orders whose
          first candle (Tc - 5) opens at or beyond the level are rejected.
          Fills use CFM perp candles from the SPEC's launch dates (BTC/ETH 2025-07-19, SOL/XRP 2025-08-16) and Coinbase
          spot candles before (a synthetic perp at perp costs). Signals always use spot candles.
  costs   costs.perp_cost_bp per side at the fill price (x mult), funding costs.perp_funding_bp on the entry notional
          for the hours held. P&L booked on the trade day (the US close falls on the same UTC day).

Pre-trial definitions (fixed before the first DEV trial; the SPEC leaves them to the builder):
  1. P(x) = close of the candle labelled x; the previous close = the candle labelled at the previous trading day's close
     time (16:00, or 13:00 after an early close). Early closes shift every time by the close (12:44/12:46/13:00/...).
  2. sigma = sample std (ddof 1) of the 30 most recent NYSE-trading-day close-to-close log returns (spot), the last one
     ending at the previous close (so Monday's r, which spans the weekend, is compared with the same sigma).
  3. Gate: dollar volume = Yahoo close x volume summed over the SPEC's tickers (BTC: BITX BITU SBIT BTCL BTCZ; ETH:
     ETHU ETHT ETHD; SOL: SOLT SLON; XRP: XXRP UXRP XRPT), 0 before a fund launched; mean over the 20 NYSE trading days
     to d - 1; open when >= $50M.
  4. contract_ok (>= $150 per contract) and the contract count use P(15:44) spot; n = the assets that pass gate,
     contract_ok and |r| >= k sigma that day.
  5. Taker exits with no candle in [target, target + 30 min) take the last close before the target: in practice the
     Friday 17:00-18:00 ET CFM maintenance, when a live bot exits just before the halt.
  6. Maker: level 10 bp beyond the fill venue's 15:54 close, rounded away from the market to the perp tick; the
     take-profit at that close rounded to the tick on the far side; fractional fill capacity (< 1 contract) carries to
     the next minute; the take-profit works on contracts filled in earlier minutes only.
  7. Scored days: calendar days on which the most recent NYSE trading day (on or before the day) has an open gate for
     some asset of the variant's universe; idle days count as 0 (the guide's calendar-day convention). An era with
     < 60 scored days or < 10 trades is reported, not gated (prereg "Windows"): its days are left out of the days
     passed to h2gates.path_b for the gates, and reported separately.
  8. "Trades" for the SPEC's 40-trade minimum = asset-days with >= 1 contract filled on the $50K sleeve at 2x.
  9. Each DEV trial is logged once: h2gates.log_trial("letf", variant, h2gates.dev_book(s50_2x), "B",
     h2gates.dev_screen_b(s50_2x)["t_alpha"]), theta 0.5. 1x, other capitals and theta 0.25 are information only.
 10. After the freeze, the early era is also run with the gate off as a descriptive placebo (SPEC: "effectively a
     placebo ... reported, not gated"); it never enters a gate.

HOLD protection: every loader takes an era and reads only the data window it needs; `check_era` refuses the HOLD eras
(chk, early) unless the caller passes allow_hold=True, which only scripts/hunt2/letf/hold.py does, after the freeze
commit. The pseudo-era "t24" (2024-10-01 .. 2024-12-31; never scored, not HOLD) is for code tests only.
"""
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/crypto-edge/scripts/hunt2")
import costs  # noqa: E402
import h2gates as G  # noqa: E402

DATA = "/home/claude/crypto-edge/data"
ETF_PATH = os.path.join(DATA, "hunt2", "etf", "etf_daily.parquet")
ET = "America/New_York"
ASSETS = ("BTC", "ETH", "SOL", "XRP")
COMPLEX = {"BTC": ("BITX", "BITU", "SBIT", "BTCL", "BTCZ"), "ETH": ("ETHU", "ETHT", "ETHD"),
           "SOL": ("SOLT", "SLON"), "XRP": ("XXRP", "UXRP", "XRPT")}
PERP_FROM = {"BTC": pd.Timestamp("2025-07-19"), "ETH": pd.Timestamp("2025-07-19"),
             "SOL": pd.Timestamp("2025-08-16"), "XRP": pd.Timestamp("2025-08-16")}
GATE_USD, GATE_N, SIG_N = 50e6, 20, 30
MAKER_BP = 10.0
ENTRY_WAIT, EXIT_WAIT, ASOF_MAX = 5, 30, 30
LOOKBACK = pd.Timedelta(days=100)
CAPS = (25000, 50000, 75000, 125000)


TEST = {"t24": (pd.Timestamp("2024-10-01"), pd.Timestamp("2024-12-31"))}   # code tests only: never scored, not HOLD


def check_era(era, allow_hold=False):
    if era not in G.ERAS and era not in TEST:
        raise ValueError(era)
    if era in G.HOLD_ERAS and not allow_hold:
        raise RuntimeError("HOLD era requested before the freeze (reports/hunt2_prereg.md)")


def era_window(era):
    lo, hi = G.ERAS[era] if era in G.ERAS else TEST[era]
    return lo, hi


# ------------------------------------------------------------------ calendar and data
def nyse(lo, hi):
    """NYSE trading days in [lo, hi]: index = the day; close_utc = the close time as a naive UTC minute."""
    import pandas_market_calendars as mcal
    s = mcal.get_calendar("NYSE").schedule(start_date=lo.strftime("%Y-%m-%d"), end_date=hi.strftime("%Y-%m-%d"))
    out = pd.DataFrame(index=pd.DatetimeIndex(s.index).normalize())
    out.index.name = "day"
    out["close_utc"] = s["market_close"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy()
    out["close_et"] = s["market_close"].dt.tz_convert(ET).dt.strftime("%H:%M").to_numpy()
    return out


def _frame(d):
    if d is None or len(d) == 0:
        return None
    d = d[["open", "high", "low", "close", "volume"]].astype(float)
    return dict(t=d.index.to_numpy().astype("datetime64[m]").astype(np.int64), o=d.open.to_numpy(),
                h=d.high.to_numpy(), l=d.low.to_numpy(), c=d.close.to_numpy(), v=d.volume.to_numpy())


def load_spot(coin, era):
    lo, hi = era_window(era)
    src = "minute_early" if era == "early" else "minute"
    a, b = lo - LOOKBACK, hi + pd.Timedelta(days=1)
    d = costs.load_minute(coin, src, start=a, end=b)
    return _frame(d)


def load_perp(coin, era):
    lo, hi = era_window(era)
    d = costs.load_perp(coin)
    if d is None:
        return None
    d = d[(d.index >= lo) & (d.index < hi + pd.Timedelta(days=1))]
    return _frame(d)


def etf_dollar_volume(era):
    """Daily dollar volume (close x volume) of each asset's 2x/-2x complex on the NYSE trading days of the era's
    window (lookback included). Only rows dated before the era's last day are read (day d's gate uses data to d - 1);
    0 where a fund had not launched."""
    lo, hi = era_window(era)
    D = pd.read_parquet(ETF_PATH)
    D = D[(D.date >= lo - LOOKBACK) & (D.date < hi)]
    cal = nyse(lo - LOOKBACK, hi).index
    out = {}
    for a, tick in COMPLEX.items():
        x = D[D.ticker.isin(tick)].copy()
        x["dv"] = x.close.astype(float) * x.volume.astype(float)
        out[a] = x.groupby("date").dv.sum().reindex(cal).fillna(0.0)
    return pd.DataFrame(out)


def gate_table(era):
    """Trailing 20-trading-day mean dollar volume of each complex to d - 1, per NYSE trading day (lookback included);
    the gate is open when it is >= $50M."""
    dv = etf_dollar_volume(era)
    return dv.rolling(GATE_N, min_periods=GATE_N).mean().shift(1)


# ------------------------------------------------------------------ candle lookups (minutes as int64)
def asof_close(F, t, max_age=ASOF_MAX):
    i = np.searchsorted(F["t"], t, side="right") - 1
    if i < 0 or t - F["t"][i] > max_age:
        return np.nan
    return F["c"][i]


def first_open(F, t, wait):
    i = np.searchsorted(F["t"], t, side="left")
    if i >= len(F["t"]) or F["t"][i] >= t + wait:
        return np.nan, -1
    return F["o"][i], int(F["t"][i])


def window_rows(F, t0, t1):
    """Candle rows with t0 <= t < t1."""
    i, j = np.searchsorted(F["t"], t0, side="left"), np.searchsorted(F["t"], t1, side="left")
    return np.arange(i, j)


def mins(ts):
    return int(np.datetime64(pd.Timestamp(ts).to_datetime64(), "m").astype(np.int64))


# ------------------------------------------------------------------ signals
def signals(era, allow_hold=False):
    """One row per (NYSE trading day in the era, asset): r, sigma, z = r / sigma, gate, contract_ok and the prices the
    legs need. Nothing outside the era's window (plus lookback) is read."""
    check_era(era, allow_hold)
    lo, hi = era_window(era)
    cal = nyse(lo - LOOKBACK, hi)
    gate_avg = gate_table(era)
    rows = []
    for a in ASSETS:
        S = load_spot(a, era)
        P = load_perp(a, era)
        csize, tick = costs.PERP[a][1], costs.PERP[a][2]
        closes = pd.Series([asof_close(S, mins(t)) for t in cal.close_utc], index=cal.index)
        lr = np.log(closes / closes.shift(1))
        sig = lr.rolling(SIG_N, min_periods=SIG_N).std().shift(1)       # 30 returns ending at the previous close
        prev_close = closes.shift(1)
        for i, day in enumerate(cal.index):
            if day < lo or day > hi:
                continue
            Tc = mins(cal.close_utc.iloc[i])
            p_sig = asof_close(S, Tc - 16)
            r = math.log(p_sig / prev_close.iloc[i]) if (p_sig == p_sig and prev_close.iloc[i] == prev_close.iloc[i]) \
                else np.nan
            use_perp = day >= PERP_FROM[a]
            Fx = P if use_perp else S
            g = gate_avg[a].get(day, np.nan)
            row = dict(day=day, asset=a, close_et=cal.close_et.iloc[i], Tc=Tc, p_sig=p_sig, prev_close=prev_close.iloc[i],
                       r=r, sigma=sig.iloc[i], gate_avg=g, gate=bool(g >= GATE_USD) if g == g else False,
                       cok=bool(costs.contract_ok(a, p_sig)) if p_sig == p_sig else False, venue="perp" if use_perp else "spot",
                       csize=csize, tick=tick)
            # taker legs
            for leg, (t_in, t_out) in (("mom", (Tc - 14, Tc)), ("rev", (Tc + 1, Tc + 60))):
                pin, tin = first_open(Fx, t_in, ENTRY_WAIT) if Fx is not None else (np.nan, -1)
                pout, tout = first_open(Fx, t_out, EXIT_WAIT) if Fx is not None else (np.nan, -1)
                stale = False
                if pout != pout and Fx is not None:
                    pout, tout, stale = asof_close(Fx, t_out, 24 * 60), t_out, True
                row.update({f"{leg}_in": pin, f"{leg}_tin": tin, f"{leg}_out": pout, f"{leg}_tout": tout,
                            f"{leg}_stale": stale})
            # maker leg: reference, rejection test, per-minute candles Tc-5 .. Tc+59, taker exit at Tc+60
            p54 = asof_close(Fx, Tc - 6) if Fx is not None else np.nan
            row["p54"] = p54
            if Fx is not None:
                w = window_rows(Fx, Tc - 5, Tc + 60)
                row["mk_rows"] = (Fx["t"][w] - Tc, Fx["o"][w], Fx["h"][w], Fx["l"][w], Fx["v"][w])
                pout, tout = first_open(Fx, Tc + 60, EXIT_WAIT)
                stale = False
                if pout != pout:
                    pout, tout, stale = asof_close(Fx, Tc + 60, 24 * 60), Tc + 60, True
                row.update(mk_out=pout, mk_tout=tout, mk_stale=stale)
            rows.append(row)
    D = pd.DataFrame(rows)
    D["z"] = D.r / D.sigma
    return D


# ------------------------------------------------------------------ the sleeve
def _beyond(h, l, v, level, tick, side):
    """Coin volume strictly beyond `level` by >= 1 tick in a candle (side +1: a bid, the price must trade at or below
    level - tick; side -1: an offer, at or above level + tick), the candle's volume spread evenly over its range."""
    if side > 0:
        edge = level - tick
        if l > edge:
            return 0.0
        frac = 1.0 if h <= l else min(1.0, (edge - l) / (h - l))
    else:
        edge = level + tick
        if h < edge:
            return 0.0
        frac = 1.0 if h <= l else min(1.0, (h - edge) / (h - l))
    return v * frac


def maker_trade(row, side, n_target, theta):
    """Simulate the maker leg for one asset-day. side +1 = a bid (down day), -1 = an offer (up day). Returns a list of
    (contracts, entry_px, exit_px, exit_kind, entry_min, exit_min) blocks (minutes relative to Tc) and a flag."""
    p54, tick, csize = row["p54"], row["tick"], row["csize"]
    if not (p54 == p54) or n_target <= 0 or not isinstance(row.get("mk_rows"), tuple):
        return [], "nodata"
    if side > 0:
        L = math.floor(p54 * (1 - MAKER_BP / 1e4) / tick) * tick
        TP = math.ceil(p54 / tick - 1e-9) * tick
    else:
        L = math.ceil(p54 * (1 + MAKER_BP / 1e4) / tick) * tick
        TP = math.floor(p54 / tick + 1e-9) * tick
    rel, o, h, lo, v = row["mk_rows"]
    if len(rel) and rel[0] == -5 and ((side > 0 and o[0] <= L) or (side < 0 and o[0] >= L)):
        return [], "rejected"
    filled, carry_in = [], 0.0          # filled: list of [contracts, entry minute]
    pos_open, carry_tp, out = 0, 0.0, []
    remaining_in = n_target
    pending = []                         # entry fills of the current minute (become TP-eligible next minute)
    for k in range(len(rel)):
        m = int(rel[k])
        # TP on the position held at the start of this minute
        if pos_open > 0:
            cap = theta * _beyond(h[k], lo[k], v[k], TP, tick, -side) + carry_tp
            q = min(pos_open, int(cap // csize + 1e-12))
            if q > 0:
                # close the oldest blocks first
                left = q
                for blk in filled:
                    if left <= 0:
                        break
                    take = min(blk[0], left)
                    if take > 0:
                        out.append((take, L, TP, "tp", blk[1], m))
                        blk[0] -= take
                        left -= take
                pos_open -= q
            carry_tp = cap - q * csize if pos_open > 0 else 0.0
        # entry order works Tc-5 .. Tc-1
        if -5 <= m <= -1 and remaining_in > 0:
            cap = theta * _beyond(h[k], lo[k], v[k], L, tick, side) + carry_in
            q = min(remaining_in, int(cap // csize + 1e-12))
            if q > 0:
                pending.append([q, m])
                remaining_in -= q
            carry_in = cap - q * csize if remaining_in > 0 else 0.0
        # fills of this minute join the position at the end of the minute
        for blk in pending:
            filled.append(blk)
            pos_open += blk[0]
        pending = []
    if pos_open > 0:
        pout = row.get("mk_out", np.nan)
        for blk in filled:
            if blk[0] > 0:
                out.append((blk[0], L, pout, "taker", blk[1], 60))
    if not out:
        return [], "nofill"
    return out, "filled"


def sleeve(D, leg, k, universe, cap, mult=1.0, theta=0.5, days=None):
    """Daily returns (P&L / cap) of one variant over `days` (calendar days; 0 when idle), plus a trade list."""
    X = D[D.asset.isin(universe)].copy()
    X["sig"] = X.gate & X.cok & (X.z.abs() >= k) & X.z.notna()
    nsig = X[X.sig].groupby("day").size()
    trades = []
    for row in X[X.sig].to_dict("records"):
        a, csize = row["asset"], row["csize"]
        n = nsig[row["day"]]
        notional = cap / n
        n_c = int(math.floor(notional / (row["p_sig"] * csize) + 1e-9))
        s_flow = 1 if row["r"] > 0 else -1
        base = dict(day=row["day"], asset=a, z=row["z"], r=row["r"], venue=row["venue"], n_sig=int(n), target=n_c)
        if leg in ("mom", "rev"):
            side = s_flow if leg == "mom" else -s_flow
            pin, pout = row[f"{leg}_in"], row[f"{leg}_out"]
            if n_c <= 0 or not (pin == pin) or not (pout == pout):
                trades.append(dict(base, contracts=0, status="nodata" if n_c > 0 else "small"))
                continue
            qty = n_c * csize
            gross = side * qty * (pout - pin)
            c_in = costs.perp_cost_bp(a, pin, taker=True, mult=mult) / 1e4 * qty * pin
            c_out = costs.perp_cost_bp(a, pout, taker=True, mult=mult) / 1e4 * qty * pout
            hours = max(0, row[f"{leg}_tout"] - row[f"{leg}_tin"]) / 60.0
            fund = costs.perp_funding_bp(hours, mult) / 1e4 * qty * pin
            trades.append(dict(base, contracts=n_c, side=side, entry=pin, exit=pout, notional=qty * pin,
                               gross=gross, cost=c_in + c_out + fund, pnl=gross - c_in - c_out - fund,
                               stale=bool(row[f"{leg}_stale"]), status="filled"))
        else:
            side = -s_flow                       # liquidity to the flow: a bid on down days, an offer on up days
            blocks, status = maker_trade(row, side, n_c, theta)
            if status != "filled":
                trades.append(dict(base, contracts=0, status=status))
                continue
            gross = cost = 0.0
            qty_tot = 0.0
            n_tp = 0
            for (q, pin, pout, kind, m_in, m_out) in blocks:
                qty = q * csize
                gross += side * qty * (pout - pin)
                cost += costs.perp_cost_bp(a, pin, taker=False, mult=mult) / 1e4 * qty * pin
                cost += costs.perp_cost_bp(a, pout, taker=(kind == "taker"), mult=mult) / 1e4 * qty * pout
                cost += costs.perp_funding_bp(max(0, m_out - m_in) / 60.0, mult) / 1e4 * qty * pin
                qty_tot += qty
                n_tp += q if kind == "tp" else 0
            n_f = int(round(qty_tot / csize))
            trades.append(dict(base, contracts=n_f, side=side, entry=blocks[0][1], exit=np.nan,
                               notional=qty_tot * blocks[0][1], gross=gross, cost=cost, pnl=gross - cost,
                               tp_share=n_tp / n_f if n_f else np.nan, stale=bool(row.get("mk_stale", False)),
                               status="filled"))
    T = pd.DataFrame(trades)
    if days is None:
        days = pd.DatetimeIndex(sorted(D.day.unique()))
    if len(T) and "pnl" in T:
        pnl = T[T.status == "filled"].groupby("day").pnl.sum()
    else:
        pnl = pd.Series(dtype=float)
    r = (pnl / cap).reindex(pd.DatetimeIndex(days)).fillna(0.0)
    return r, T


def scored_days(universe, era, allow_hold=False):
    """Calendar days of the era on which the sleeve is live: the most recent NYSE trading day on or before the day has
    an open gate for some asset of the universe (SPEC: each asset's gated days; idle days inside count as 0)."""
    check_era(era, allow_hold)
    lo, hi = era_window(era)
    avg = gate_table(era)
    anyg = (avg[list(universe)] >= GATE_USD).any(axis=1)
    cal = pd.date_range(lo, hi, freq="D")
    live = anyg.reindex(anyg.index.union(cal)).ffill().reindex(cal).fillna(False).astype(bool)
    return cal[live.to_numpy()]


VARIANTS = [dict(k=k, leg=leg, uni=uni) for leg in ("mom", "rev", "mkr") for uni in ("btc", "all") for k in (1, 2)]
UNIVERSE = {"btc": ("BTC",), "all": ASSETS}


def vname(v):
    return f"{v['leg']}_k{v['k']}_{v['uni']}"
