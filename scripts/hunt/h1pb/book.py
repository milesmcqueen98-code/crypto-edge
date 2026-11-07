#!/usr/bin/env python3
"""H1 book: trigger entries (run_shard.py) -> sleeve trades and daily returns.

Variant = (mode, k, side, H, theta, time-of-day filter). Rules (SPEC "Trades", "Sleeve capital"):
- an entry is an order fill of n = min(target, floor(theta x through-volume)) >= 1 contracts;
- slots: one position per coin and side, at most 6 open, gross notional <= 3 x sleeve capital, in fill-time order; a
  position holds its slot until its last contract is closed (take-profit or time exit);
- costs: common.perp_cost_bp (maker on entries and take-profits, taker incl. 1.5x half-spread on time exits) and
  common.perp_funding_bp on the contract-hours held; mult = 2 for every gate, 1 for information;
- P&L in USD booked on the UTC day of the final close; daily return = P&L / sleeve capital; calendar days, 0 idle.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
from numba import njit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
REP = os.environ.get("H1_REP") or os.path.join(ROOT, "reports", "hunt", "h1pb")
HOLD0 = pd.Timestamp("2026-06-01")
MAINT = (16 * 60 + 55, 18 * 60 + 5)           # 4:55-6:05 pm ET (minutes after midnight, America/New_York)
CORE_COLS = ["coin", "mode", "k", "side", "t_fill", "row", "L", "TP", "ntg"]


def load(stage, H=60, theta=0.5, mode=None, files=None):
    hh, th = str(int(H)), "50" if theta == 0.5 else "25"
    cols = CORE_COLS + [f"n{th}", f"tpn{hh}_{th}", f"gross{hh}_{th}", f"tclose{hh}_{th}", f"remnot{hh}_{th}",
                        f"chours{hh}_{th}", f"valid{hh}"]
    out = []
    for f in sorted(files or glob.glob(os.path.join(REP, stage, "entries_*.parquet"))):
        d = pd.read_parquet(f, columns=cols, filters=[("mode", "==", mode)] if mode else None)
        out.append(d)
    E = pd.concat(out, ignore_index=True)
    E = E.rename(columns={f"n{th}": "n", f"tpn{hh}_{th}": "tpn", f"gross{hh}_{th}": "gross", f"tclose{hh}_{th}": "t_close",
                          f"remnot{hh}_{th}": "remnot", f"chours{hh}_{th}": "chours", f"valid{hh}": "valid"})
    E = E[(E.n >= 1) & E.valid].drop(columns="valid")
    E["L"] = E["L"].astype(np.float64)
    E["TP"] = E["TP"].astype(np.float64)
    # chunks overlap by design only in fetched prints, not in kept triggers; drop exact duplicates defensively
    return E.drop_duplicates(["coin", "mode", "k", "side", "t_fill"]).reset_index(drop=True)


MAJORS = ("BTC", "ETH", "SOL", "XRP")


def load_devc(H=60, theta=0.5, mode=None):
    """DEV entries with the corrected statistics (levels v2): every alt from the dev2 rerun; the majors from the first
    DEV fetch on all rows whose inputs did not change, plus the dev2 delta run on the rows that did."""
    D1 = load("dev", H, theta, mode)
    D2 = load("dev2", H, theta, mode)
    dr = pd.read_parquet(os.path.join(REP, "delta_rows.parquet"))
    key = set(zip(dr.coin, dr.row.astype(np.int64)))
    m1 = D1.coin.isin(MAJORS).to_numpy()
    if key:
        m1 &= ~np.array([(c, int(r)) in key for c, r in zip(D1.coin, D1.row)])
    out = pd.concat([D1[m1], D2], ignore_index=True)
    return out.drop_duplicates(["coin", "mode", "k", "side", "t_fill"]).reset_index(drop=True)


def et_minute(t_ns):
    t = pd.to_datetime(t_ns).tz_localize("UTC").tz_convert("America/New_York")
    return t.hour * 60 + t.minute


def select(E, mode, k, side, tod=None):
    s = (E["mode"] == mode) & (E.k == k)
    if side != "both":
        s &= E.side == (1 if side == "long" else -1)
    X = E[s]
    if tod is not None:
        m = et_minute(X.t_fill.to_numpy())
        inside = (m >= MAINT[0]) & (m < MAINT[1])
        X = X[~inside] if tod == "no_maint" else X[inside]
    return X.sort_values(["t_fill", "coin", "side"], kind="mergesort").reset_index(drop=True)


@njit(cache=True)
def _slots(t_fill, t_close, cside, notional, max_open, gross_cap):
    n = len(t_fill)
    take = np.zeros(n, np.bool_)
    op_close = np.empty(64, np.int64)
    op_cs = np.empty(64, np.int64)
    op_not = np.empty(64, np.float64)
    m = 0
    for i in range(n):
        j = 0
        while j < m:                                   # release positions closed at or before this fill
            if op_close[j] <= t_fill[i]:
                op_close[j] = op_close[m - 1]
                op_cs[j] = op_cs[m - 1]
                op_not[j] = op_not[m - 1]
                m -= 1
            else:
                j += 1
        if m >= max_open:
            continue
        busy = False
        g = 0.0
        for j in range(m):
            if op_cs[j] == cside[i]:
                busy = True
            g += op_not[j]
        if busy or g + notional[i] > gross_cap:
            continue
        take[i] = True
        op_close[m] = t_close[i]
        op_cs[m] = cside[i]
        op_not[m] = notional[i]
        m += 1
    return take


def trades(X, capital, max_open=6):
    if not len(X):
        return X.assign(notional=[])
    cs = X.coin.map({c: v[1] for c, v in common.PERP.items()}).to_numpy(np.float64)
    notional = X.n.to_numpy(np.float64) * cs * X.L.to_numpy()
    codes = {c: i for i, c in enumerate(sorted(common.PERP))}
    cside = X.coin.map(codes).to_numpy(np.int64) * 2 + (X.side.to_numpy() > 0)
    take = _slots(X.t_fill.to_numpy(np.int64), X.t_close.to_numpy(np.int64), cside, notional, max_open, 3.0 * capital)
    T = X[take].copy()
    T["notional"] = notional[take]
    T["cs"] = cs[take]
    return T.reset_index(drop=True)


def costs(T, mult, fee_usd=None):
    """USD cost per trade: entry and take-profit (maker), time exit (taker, 1.5x half-spread), funding. fee_usd
    overrides the per-contract fee (descriptive sensitivity only; the gates use common.PERP_FEE_USD)."""
    if not len(T):
        return np.zeros(0)
    out = np.zeros(len(T))
    for coin, g in T.groupby("coin"):
        ix = g.index.to_numpy()
        L, TP, n, tpn = g.L.to_numpy(), g.TP.to_numpy(), g.n.to_numpy(), g.tpn.to_numpy()
        cs = common.PERP[coin][1]
        rem = n - tpn
        x = np.where(rem > 0, g.remnot.to_numpy() / np.maximum(rem, 1) / cs, L)
        c_in = n * cs * L * np.array([common.perp_cost_bp(coin, v, False, mult) for v in L]) / 1e4
        c_tp = tpn * cs * TP * np.array([common.perp_cost_bp(coin, v, False, mult) for v in TP]) / 1e4
        c_x = g.remnot.to_numpy() * np.array([common.perp_cost_bp(coin, v, True, mult) for v in x]) / 1e4
        c_f = g.chours.to_numpy() * cs * L * common.perp_funding_bp(1.0, mult) / 1e4
        tot = c_in + c_tp + c_x + c_f
        if fee_usd is not None:                       # swap the per-contract fee part only
            fee_part = (n + tpn + rem) * common.PERP_FEE_USD * mult
            tot = tot - fee_part + (n + tpn + rem) * fee_usd * mult
        out[ix] = tot
    return out


def daily(T, net, days, capital):
    s = pd.Series(net, index=pd.to_datetime(T.t_close.to_numpy()).floor("D")).groupby(level=0).sum()
    return (s.reindex(days).fillna(0.0) / capital).rename("r")


def sleeve(E, mode, k, side, days, capital=30_000.0, mult=2.0, tod=None, fee_usd=None):
    X = select(E, mode, k, side, tod)
    T = trades(X, capital)
    c = costs(T, mult, fee_usd)
    net = T.gross.to_numpy() - c if len(T) else np.zeros(0)
    T = T.assign(cost=c, net=net)
    T = T[pd.to_datetime(T.t_close.to_numpy()).floor("D").isin(days)] if len(T) else T
    return daily(T, T.net.to_numpy(), days, capital), T
