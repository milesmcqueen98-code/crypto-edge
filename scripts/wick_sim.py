#!/usr/bin/env python3
"""Limit-order (maker) execution of the short-horizon reversion trade on 1-minute OHLC.

Entry styles
  RB  resting order always working at fair value -/+ k*sigma_L, so it catches wicks inside the minute:
        level[t] = C[t-L] * exp(adj - side*k*sigma_L[t-1])
        adj = beta * BTC move over t-L..t-1 ("resid" reference) or 0 ("raw"); uses data through t-1 only.
  PS  post-signal limit: after the close-based residual z crosses -k (dips) at minute t0, a limit buy at
        C[t0]*exp(-delta) works for M minutes.
Fill rule (maker): the order rests from the start of minute t and fills only if that minute traded
THROUGH it by >= `tt` ticks (low <= level - tt*tick) and opened on the passive side of it (post-only;
an order that would cross is rejected). Fill price = the limit price.
Exit: take-profit limit at entry*exp(side*theta*k*sigma) resting from the next minute (maker, needs a
trade-through), else a market exit at the close H minutes after the fill (taker fee + half-spread).
Optional stop (market) at entry*exp(-side*s*k*sigma); a stop is checked in the fill minute too
(pessimistic: assumes the low came after the fill).
Costs per side: maker fee, or taker fee + half-spread. One position per coin per book.

Design: 2024. Test: 2025-01-01 .. 2026-11-05 (never used for any choice).
Writes reports/wick_grid_<tag>.csv
"""
import itertools
import os
import sys
import time

import numba
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
ALTS = ["ETH", "SOL", "XRP", "DOGE", "LTC", "AVAX", "LINK"]
ALL = ["BTC"] + ALTS
START, END = "2024-01-01", "2026-11-06"
TEST_START = "2025-01-01"
TICK_BP = {"BTC": 0.66, "ETH": 0.45, "SOL": 0.6, "XRP": 0.5, "DOGE": 1.0, "LTC": 1.2, "AVAX": 1.0, "LINK": 0.8}
# half-spread paid on a market order, bp (Coinbase futures book; replaced by measured values when available)
HALF_SPREAD_BP = {"BTC": 0.7, "ETH": 1.0, "SOL": 1.2, "XRP": 1.2, "DOGE": 2.0, "LTC": 3.0, "AVAX": 2.0, "LINK": 2.0}
W = 4320                      # 3-day trailing window for beta and sigma
PERP = {  # Coinbase Derivatives perp-style futures: (product, contract size in coin, tick in USD)
    "BTC": ("BIP-20DEC30-CDE", 0.01, 5.0), "ETH": ("ETP-20DEC30-CDE", 0.1, 0.5), "SOL": ("SLP-20DEC30-CDE", 5, 0.01),
    "XRP": ("XPP-20DEC30-CDE", 500, 0.0001), "DOGE": ("DOP-20DEC30-CDE", 5000, 0.00001),
    "LTC": ("LCP-20DEC30-CDE", 5, 0.01), "AVAX": ("AVP-20DEC30-CDE", 10, 0.01), "LINK": ("LNP-20DEC30-CDE", 50, 0.001),
    "ADA": ("ADP-20DEC30-CDE", 1000, 0.0001), "BCH": ("BCP-20DEC30-CDE", 1, 0.05), "SUI": ("SUP-20DEC30-CDE", 500, 0.0001),
    "XLM": ("XLP-20DEC30-CDE", 5000, 0.00001), "HBAR": ("HEP-20DEC30-CDE", 5000, 0.00001),
    "NEAR": ("NER-20DEC30-CDE", 500, 0.0001), "AAVE": ("AVE-20DEC30-CDE", 5, 0.01), "HYPE": ("HYP-20DEC30-CDE", 10, 0.01),
    "ENA": ("ENA-20DEC30-CDE", 5000, 0.00001), "PEPE": ("PEP-20DEC30-CDE", 1e8, 1e-9),           # 1000PEPE perp: 100k x 1000 PEPE
    "ONDO": ("OND-20DEC30-CDE", 1000, 0.0001),
}


def load_ohlc(src="minute", coins=ALL, start=START, end=END):
    idx = pd.date_range(start, end, freq="min", inclusive="left")
    out = {}
    for c in coins:
        p = os.path.join(ROOT, "data", src, f"{c}.parquet")
        if not os.path.exists(p):
            continue
        df = pd.read_parquet(p).drop_duplicates("ts").set_index("ts").sort_index()
        df = df[df.volume > 0].reindex(idx)
        out[c] = {k: df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close")}
        out[c]["cf"] = df["close"].ffill(limit=30).to_numpy(np.float64)
        out[c]["vol"] = df["volume"].fillna(0.0).to_numpy(np.float64)
    return idx, out


def roll_std(x, w=W, minp=1440):
    return pd.Series(x).rolling(w, min_periods=minp).std().to_numpy()


def roll_beta(ri, rb, w=W, minp=1440):
    a, b = pd.Series(ri), pd.Series(rb)
    cov = (a * b).rolling(w, min_periods=minp).mean() - a.rolling(w, min_periods=minp).mean() * b.rolling(w, min_periods=minp).mean()
    return (cov / b.rolling(w, min_periods=minp).var()).clip(0.0, 3.0).to_numpy()


def shift(x, n):
    out = np.full_like(x, np.nan)
    if n > 0:
        out[n:] = x[:-n]
    elif n < 0:
        out[:n] = x[-n:]
    else:
        out[:] = x
    return out


class Prep:
    """Per-coin log prices, betas and L-minute sigmas (raw and residual), all known at t-1."""

    def __init__(self, D, Ls):
        self.D = D
        self.lp = {c: np.log(D[c]["cf"]) for c in D}
        btc = self.lp["BTC"]
        r1b = np.diff(btc, prepend=np.nan)
        self.beta = {c: shift(roll_beta(np.diff(self.lp[c], prepend=np.nan), r1b), 1) for c in D if c != "BTC"}
        self.sig_raw, self.sig_res = {}, {}
        for L in Ls:
            rbL = btc - shift(btc, L)
            for c in D:
                rL = self.lp[c] - shift(self.lp[c], L)
                self.sig_raw[c, L] = shift(roll_std(rL), 1)                # sigma of L-minute moves, known at t-1
                if c != "BTC":
                    e = rL - shift(self.beta[c], -1) * rbL                  # residual L-minute move
                    self.sig_res[c, L] = shift(roll_std(e), 1)

    def level(self, c, L, k, side, ref):
        lp_ref = shift(self.lp[c], L)                             # log close at t-L (L>=1)
        if ref == "resid" and c != "BTC" and L > 1:
            # BTC move t-L .. t-1 (known), times beta (known at t-1)
            btc = self.lp["BTC"]
            mv = shift(btc, 1) - shift(btc, L)
            sig = self.sig_res[c, L]
            return np.exp(lp_ref + self.beta[c] * mv - side * k * sig), sig
        sig = self.sig_raw[c, L]
        return np.exp(lp_ref - side * k * sig), sig


@numba.njit(cache=True)
def run_book(O, Hh, Lo, Cf, lvl, tpd, stpd, side, tick, hmax, cooldown):
    """One coin, one side. Returns entry idx, exit idx, entry px, exit px, exit type (1 tp, 2 stop, 3 time)."""
    T = len(O)
    cap = T // 4 + 16
    ei = np.empty(cap, np.int64)
    xi = np.empty(cap, np.int64)
    ep = np.empty(cap, np.float64)
    xp = np.empty(cap, np.float64)
    ty = np.empty(cap, np.int8)
    n = 0
    pos = 0
    e_i = 0
    e_p = 0.0
    tp = 0.0
    st = 0.0
    nxt = 0
    for t in range(T):
        if n >= cap - 1:
            break
        if pos == 0:
            if t < nxt:
                continue
            b = lvl[t]
            if np.isnan(b) or np.isnan(Lo[t]) or np.isnan(O[t]):
                continue
            if side == 1:
                filled = (O[t] > b) and (Lo[t] <= b * (1.0 - tick[t]))
            else:
                filled = (O[t] < b) and (Hh[t] >= b * (1.0 + tick[t]))
            if not filled:
                continue
            pos = 1
            e_i = t
            e_p = b
            tp = b * np.exp(side * tpd[t]) if not np.isnan(tpd[t]) else (np.inf if side == 1 else 0.0)
            st = b * np.exp(-side * stpd[t]) if not np.isnan(stpd[t]) else (0.0 if side == 1 else np.inf)
            hit_stop = (Lo[t] <= st) if side == 1 else (Hh[t] >= st)
            if hit_stop:
                ei[n] = t
                xi[n] = t
                ep[n] = e_p
                xp[n] = st
                ty[n] = 2
                n += 1
                pos = 0
                nxt = t + 1 + cooldown
            continue
        # in a position
        if np.isnan(Lo[t]):
            if t - e_i >= hmax and not np.isnan(Cf[t]):
                ei[n] = e_i
                xi[n] = t
                ep[n] = e_p
                xp[n] = Cf[t]
                ty[n] = 3
                n += 1
                pos = 0
                nxt = t + 1 + cooldown
            continue
        if side == 1:
            if Lo[t] <= st:
                px = min(st, O[t])
                ty_ = 2
            elif Hh[t] >= tp * (1.0 + tick[t]):
                px = tp
                ty_ = 1
            elif t - e_i >= hmax:
                px = Cf[t]
                ty_ = 3
            else:
                continue
        else:
            if Hh[t] >= st:
                px = max(st, O[t])
                ty_ = 2
            elif Lo[t] <= tp * (1.0 - tick[t]):
                px = tp
                ty_ = 1
            elif t - e_i >= hmax:
                px = Cf[t]
                ty_ = 3
            else:
                continue
        ei[n] = e_i
        xi[n] = t
        ep[n] = e_p
        xp[n] = px
        ty[n] = ty_
        n += 1
        pos = 0
        nxt = t + 1 + cooldown
    return ei[:n], xi[:n], ep[:n], xp[:n], ty[:n]


def trades_df(idx, c, side, out, fee_m, fee_t, hs):
    ei, xi, ep, xp, ty = out
    gross = side * np.log(xp / ep) * 1e4
    exit_cost = np.where(ty == 1, fee_m, fee_t + hs)
    return pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": c, "side": side, "type": ty,
                         "hold_min": xi - ei, "gross_bp": gross, "cost_bp": fee_m + exit_cost,
                         "net_bp": gross - fee_m - exit_cost})


def daily_stats(tr, notional=0.25, start=START, end=END):
    days = pd.date_range(pd.Timestamp(start).floor("D"), pd.Timestamp(end).floor("D") - pd.Timedelta(days=1), freq="D")
    if tr.empty:
        return dict(trades=0, per_day=0.0, gross_bp=np.nan, net_bp=np.nan, hit=np.nan, sharpe=np.nan, ann_ret=np.nan,
                    maxdd=np.nan, worst_day=np.nan)
    d = (tr.set_index("exit_ts").net_bp * notional / 1e4).resample("D").sum().reindex(days, fill_value=0.0)
    eq = d.cumsum()
    sd = d.std()
    return dict(trades=len(tr), per_day=len(tr) / len(days), gross_bp=tr.gross_bp.mean(), net_bp=tr.net_bp.mean(),
                hit=(tr.net_bp > 0).mean(), sharpe=d.mean() / sd * np.sqrt(365) if sd > 0 else np.nan,
                ann_ret=d.mean() * 365, maxdd=(eq - eq.cummax()).min(), worst_day=d.min())


def split_stats(tr, notional=0.25):
    a = tr[tr.ts < TEST_START]
    b = tr[tr.ts >= TEST_START]
    out = {}
    for lab, x, s, e in [("design", a, START, TEST_START), ("test", b, TEST_START, END)]:
        out |= {f"{lab}_{k}": v for k, v in daily_stats(x, notional, s, e).items()}
    return out


def main():
    t0 = time.time()
    fee_m = float(os.environ.get("FEE_MAKER_BP", 2.0))
    fee_t = float(os.environ.get("FEE_TAKER_BP", 2.0))
    idx, D = load_ohlc()
    Ls = (1, 5, 15, 60)
    P = Prep(D, Ls)
    print(f"loaded + prepared in {time.time() - t0:.0f}s; fees maker {fee_m} / taker {fee_t} bp", flush=True)
    rows = []
    outer = [g for g in itertools.product(Ls, (3, 4, 5, 6, 8), (1, -1), ("raw", "resid")) if not (g[3] == "resid" and g[0] == 1)]
    for n_out, (L, k, side, ref) in enumerate(outer):
        coins = [c for c in D if not (ref == "resid" and c == "BTC")]
        lv = {c: P.level(c, L, k, side, ref) for c in coins}
        for theta, H in itertools.product((0.3, 0.6, 1.0, np.inf), (5, 15, 60, 240)):
            trs = []
            for c in coins:
                lvl, sig = lv[c]
                tpd = theta * k * sig if np.isfinite(theta) else np.full_like(sig, np.nan)
                stpd = np.full_like(sig, np.nan)
                out = run_book(D[c]["open"], D[c]["high"], D[c]["low"], D[c]["cf"], lvl, tpd, stpd, side,
                               np.full(len(lvl), TICK_BP[c] / 1e4), H, 0)
                trs.append(trades_df(idx, c, side, out, fee_m, fee_t, HALF_SPREAD_BP[c]))
            tr = pd.concat(trs, ignore_index=True)
            r = dict(L=L, k=k, theta=theta, H=H, side=side, ref=ref,
                     tp_share=(tr.type == 1).mean() if len(tr) else np.nan,
                     hold_min=tr.hold_min.mean() if len(tr) else np.nan)
            r |= split_stats(tr)
            rows.append(r)
        print(f"  {n_out + 1}/{len(outer)} level sets ({time.time() - t0:.0f}s)", flush=True)
    G = pd.DataFrame(rows)
    tag = os.environ.get("TAG", "base")
    G.to_csv(os.path.join(ROOT, "reports", f"wick_grid_{tag}.csv"), index=False)
    cols = ["L", "k", "theta", "H", "side", "ref", "tp_share", "design_trades", "design_net_bp", "design_sharpe",
            "test_trades", "test_per_day", "test_gross_bp", "test_net_bp", "test_hit", "test_sharpe", "test_ann_ret",
            "test_maxdd"]
    ok = G[G.design_trades >= 150]
    print("\nTop 25 by DESIGN Sharpe (>=150 design trades), with TEST results:")
    print(ok.sort_values("design_sharpe", ascending=False).head(25)[cols].round(2).to_string(index=False))
    print(f"\n{len(G)} configs; design Sharpe>0: {(G.design_sharpe > 0).sum()}, test>0: {(G.test_sharpe > 0).sum()}, "
          f"both: {((G.design_sharpe > 0) & (G.test_sharpe > 0)).sum()}; rank corr design/test "
          f"{G[['design_sharpe', 'test_sharpe']].corr(method='spearman').iloc[0, 1]:.2f}")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
