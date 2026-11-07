#!/usr/bin/env python3
"""H2 (FR): buy the end of forced deleveraging in BTC/ETH/SOL/XRP on Coinbase perps (reports/hunt/h2fr/SPEC.md).

Core library (no scoring here):
- data per coin: Coinbase spot 1-minute candles (signals; minute_early 2021-23 + minute 2024-26) and Coinbase perp
  1-minute candles (execution after each perp's launch, data/cfm);
- cascade events: D_t = log(close_t / max close over the last W minutes) <= -k * sigma_W (trailing 3-day std of W-minute
  log returns, known at t-1) AND W-minute volume >= 3 x its trailing 3-day median (known at t-1); one event per coin
  until it re-arms (close above pre-drop high - 0.5 x drop, or 6 hours);
- exhaustion entry: first minute after the event minute (within 30) that closes above its open and the previous close;
  entry at the next minute's open of the execution venue (candles), made worse by 1.5 x the half-spread (cost model);
- exits: post-only take-profit at trough + phi x (pre-drop high - trough), translated to the perp by the perp/spot
  basis at the decision minute; market time exit after H minutes; optional stop at trough - 1 sigma_W (a spot low at or
  below it decides; market exit at the next execution open);
- fills: the take-profit rests from the minute after entry; a minute fills it only if it opened below the level and
  traded at least one tick through it (perp tick, also for spot-priced trades, as wick_sim.spot_tick); size <= theta x
  volume beyond the level (each candle's volume spread evenly over its range); whole contracts; costs from
  scripts/hunt/common.py at 1x / 2x;
- venue rules (R3 memo, applied before any result): Friday 5-6 pm ET halt and 2-minute halts after a 10% move from the
  hourly reference (emulated before launch; real perp candles show them after), Fair Value Limit (+-5% from spot);
- portfolio: one position per coin, at most two coins, notional = 1 x sleeve capital per trade, P&L on the exit day.
"""
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402

COINS = ["BTC", "ETH", "SOL", "XRP"]
RANK = {c: i for i, c in enumerate(COINS)}
START = pd.Timestamp("2021-01-01")
DEV_END = pd.Timestamp("2026-06-01")          # exclusive; dev runs never load a HOLD minute
FULL_END = pd.Timestamp("2026-11-06")         # exclusive
W3D, MINP = 4320, 1440
VOL_MULT = 3.0
EXH_MAX = 30
REARM_MIN = 360
REARM_FRAC = 0.5
MAX_COINS = 2
CAPS = (30000.0, 50000.0, 100000.0)
THETAS = (0.5, 0.25)
FVL = 0.05
HALT_PCT, HALT_MIN = 0.10, 2
MAX_WAIT = 360                                # guard against data holes: no entry more than 6 h after the decision
FEES_SENS = (0.12, 0.30)                      # $/contract/side, descriptive only (R3 memo)


def rstd(x, w=W3D, minp=MINP):
    return pd.Series(x).rolling(w, min_periods=minp).std().to_numpy()


def shift1(x):
    out = np.full(len(x), np.nan)
    out[1:] = x[:-1]
    return out


class Coin:
    """All minute arrays of one coin on a full minute grid [START, end)."""

    def __init__(self, c, end):
        self.c = c
        end = pd.Timestamp(end)
        idx = pd.date_range(START, end, freq="min", inclusive="left")
        self.idx, self.T = idx, len(idx)
        T = self.T
        o, h, l, cl, v = (np.full(T, np.nan, np.float32) for _ in range(5))
        for src in ("minute_early", "minute"):
            d = common.load_minute(c, src, start=START, end=end)
            if d is None or d.empty:
                continue
            pos = ((d.index.values - np.datetime64(START)) // np.timedelta64(1, "m")).astype(np.int64)
            for arr, k in ((o, "open"), (h, "high"), (l, "low"), (cl, "close"), (v, "volume")):
                arr[pos] = d[k].to_numpy(np.float32)
            del d
        self.o, self.h, self.l, self.cl = o, h, l, cl
        self.v = np.nan_to_num(v, nan=0.0)
        self.cf = pd.Series(cl, dtype=np.float64).ffill(limit=60).to_numpy()   # gaps > 1 h stay NaN (XRP 2021-23)
        self.lf = np.where(np.isnan(l), self.cf, l).astype(np.float32)
        P = common.load_perp(c)
        self.perp_first = P.index[0]
        launch_ts = self.perp_first.normalize() + pd.Timedelta(days=1)      # first full UTC day of perp prints
        P = P[(P.index >= START) & (P.index < end)]
        pos = ((P.index.values - np.datetime64(START)) // np.timedelta64(1, "m")).astype(np.int64)
        po, ph, pl, pc, pv = (np.full(T, np.nan, np.float32) for _ in range(5))
        for arr, k in ((po, "open"), (ph, "high"), (pl, "low"), (pc, "close"), (pv, "volume")):
            arr[pos] = P[k].to_numpy(np.float32)
        del P
        self.po, self.ph, self.pl = po, ph, pl
        self.pv = np.nan_to_num(pv, nan=0.0)
        self.pcf = pd.Series(pc).ffill(limit=5).to_numpy(np.float32)
        del pc
        self.launch = int(np.searchsorted(idx.values, np.datetime64(launch_ts)))
        self.size, self.tick = common.PERP[c][1], common.PERP[c][2]
        # emulated perp halts for spot-priced (pre-launch) trades
        et = idx.tz_localize("UTC").tz_convert("America/New_York")
        fri = (np.asarray(et.dayofweek) == 4) & (np.asarray(et.hour) == 17)
        hs = (np.arange(self.T) // 60) * 60 - 1
        ref = np.where(hs >= 0, self.cf[np.clip(hs, 0, None)], np.nan)
        with np.errstate(invalid="ignore"):
            br = (self.lf <= (1 - HALT_PCT) * ref) | (np.nan_to_num(self.h) >= (1 + HALT_PCT) * ref)
        b = np.flatnonzero(br)
        pct = np.zeros(self.T, bool)
        if len(b):
            hb = b // 60
            first = b[np.r_[True, hb[1:] != hb[:-1]]]
            for k in range(HALT_MIN + 1):
                pct[np.clip(first + k, 0, self.T - 1)] = True
        self.halt_emul = fri | pct
        self.n_halt_emul = int(len(first)) if len(b) else 0
        self.ok_s = np.flatnonzero((self.v > 0) & ~self.halt_emul)     # spot-priced execution minutes
        self.ok_p = np.flatnonzero(self.pv > 0)                         # perp execution minutes
        self.sig, self.D, self.vr = {}, {}, {}

    # ------------------------------------------------------------------ signals
    def prep(self, W):
        if W in self.D:
            return
        hi = pd.Series(self.cf).rolling(W, min_periods=1).max().to_numpy()
        self.D[W] = np.log(self.cf / hi).astype(np.float32)
        del hi
        lc = np.log(self.cf)
        rW = lc - np.r_[np.full(W, np.nan), lc[:-W]]
        del lc
        self.sig[W] = shift1(rstd(rW)).astype(np.float32)
        del rW
        vW = pd.Series(np.where(np.isfinite(self.cf), self.v, np.nan)).rolling(W, min_periods=W).sum()
        med = shift1(vW.rolling(W3D, min_periods=MINP).median().to_numpy())
        with np.errstate(invalid="ignore", divide="ignore"):
            self.vr[W] = np.where(med > 0, vW.to_numpy() / med, np.nan).astype(np.float32)
        del vW, med

    def events(self, W, k):
        """Cascade events with the re-arm rule. Returns a list of dicts (t0, tH0, H0, rearm)."""
        self.prep(W)
        D, sig, vr = self.D[W], self.sig[W], self.vr[W]
        with np.errstate(invalid="ignore"):
            cond = (D <= -k * sig) & (vr >= VOL_MULT) & (self.v > 0) & np.isfinite(sig) & (sig > 0) & np.isfinite(D)
        cands = np.flatnonzero(cond)
        out, armed = [], 0
        for t0 in cands:
            if t0 < armed or t0 < W:
                continue
            lo = t0 - W + 1
            seg = self.cf[lo:t0 + 1]
            j = int(np.nanargmax(seg))
            tH0, H0 = lo + j, float(seg[j])
            endr = min(t0 + REARM_MIN, self.T)
            rmin = np.fmin.accumulate(self.lf[tH0:endr])
            off = t0 + 1 - tH0
            thr = H0 - REARM_FRAC * (H0 - rmin[off:])
            ok = np.flatnonzero(self.cf[t0 + 1:endr] >= thr)
            rearm = t0 + 1 + int(ok[0]) + 1 if len(ok) else t0 + REARM_MIN
            out.append(dict(t0=int(t0), tH0=int(tH0), H0=H0, rearm=int(rearm), sigW=float(sig[t0]),
                            vr=float(vr[t0]), D=float(D[t0])))
            armed = rearm
        return out

    def exhaustion(self, t0):
        a, b = t0 + 1, min(t0 + EXH_MAX + 1, self.T)
        with np.errstate(invalid="ignore"):
            up = (self.cl[a:b] > self.o[a:b]) & (self.cl[a:b] > self.cf[a - 1:b - 1]) & (self.v[a:b] > 0)
        j = np.flatnonzero(up)
        return a + int(j[0]) if len(j) else -1

    # ------------------------------------------------------------------ execution helpers
    @staticmethod
    def _nxt(arr, t):
        j = np.searchsorted(arr, t)
        return int(arr[j]) if j < len(arr) else -1

    def venue(self, t_dec):
        """Execution arrays for a decision at minute t_dec: perp after launch, spot-priced (emulated halts) before."""
        if t_dec >= self.launch:
            return "perp", self.ok_p, self.po, self.ph, self.pl, self.pv
        return "spot", self.ok_s, self.o, self.h, self.l, self.v

    # ------------------------------------------------------------------ one trade (standalone)
    def trade(self, ev, phi, H, entry="exh", stop=False):
        t0 = ev["t0"]
        t_dec = self.exhaustion(t0) if entry == "exh" else t0
        if t_dec < 0:
            return None
        H0, tH0 = ev["H0"], ev["tH0"]
        seg = self.lf[tH0:t_dec + 1]
        jt = int(np.nanargmin(seg))
        trough, t_tr = float(seg[jt]), tH0 + jt
        tp_spot = trough + phi * (H0 - trough)
        if self.cf[t_dec] >= tp_spot:                     # target already met at the decision: no trade
            return None
        mode, ok, O, Hh, L, V = self.venue(t_dec)
        e = self._nxt(ok, t_dec + 1)
        if e < 0 or e - t_dec > MAX_WAIT:
            return None
        px_e = float(O[e])
        if not common.contract_ok(self.c, px_e):
            return None
        spot_ref = float(self.cf[e - 1])
        ratio = 1.0
        if mode == "perp":                                 # perp/spot basis at the decision minute
            if np.isfinite(self.pcf[t_dec]) and np.isfinite(self.cf[t_dec]):
                ratio = float(self.pcf[t_dec]) / float(self.cf[t_dec])
            elif np.isfinite(spot_ref) and spot_ref > 0:   # no perp print in 5 min: the entry print vs spot
                ratio = px_e / spot_ref
        tp = math.ceil(tp_spot * ratio / self.tick - 1e-9) * self.tick
        if tp <= px_e:                                     # never a take-profit at or below the entry price
            tp = math.ceil(px_e / self.tick - 1e-9) * self.tick + self.tick
        # Fair Value Limit: a take-profit more than 5% above spot cannot be placed until spot comes within 5%
        end = e + H
        if tp_spot > (1 + FVL) * spot_ref:
            jj = np.flatnonzero(self.cf[e:min(end, self.T)] * (1 + FVL) >= tp_spot)
            tp_start = e + int(jj[0]) + 1 if len(jj) else end
        else:
            tp_start = e
        # stop (spot trigger at a minute close; market exit at the next execution open)
        stop_m = -1
        if stop:
            sl = trough * math.exp(-ev["sigW"])
            seg_l = self.l[e:min(end, self.T)]
            with np.errstate(invalid="ignore"):
                js = np.flatnonzero(seg_l <= sl)
            if len(js):
                stop_m = e + int(js[0])
        tp_end = stop_m if stop_m >= 0 else end
        # take-profit through-volume per execution minute in [max(e + 1, tp_start), tp_end): the minute opened below
        # the level and traded at least one tick through it; volume above the level, spread evenly over the range
        a = np.searchsorted(ok, max(e + 1, tp_start))
        b = np.searchsorted(ok, tp_end)
        mins = ok[a:b]
        oo, hh, ll, vv = (O[mins].astype(np.float64), Hh[mins].astype(np.float64), L[mins].astype(np.float64),
                          V[mins].astype(np.float64))
        grid = 0.5 if mode == "perp" else 0.0              # perp prices sit on the tick grid (float tolerance)
        sel = (oo < tp - grid * self.tick) & (hh >= tp + (1.0 - grid) * self.tick)
        mins, hh, ll, vv = mins[sel], hh[sel], ll[sel], vv[sel]
        rng = hh - ll
        frac = np.where(rng > 0, (hh - np.maximum(tp, ll)) / np.where(rng > 0, rng, 1.0), 0.0)
        cum = np.cumsum(vv * np.clip(frac, 0.0, 1.0))
        # market exit (time or stop)
        x = self._nxt(ok, stop_m + 1) if stop_m >= 0 else self._nxt(ok, end)
        px_x = float(O[x]) if x >= 0 else np.nan
        # mark-to-market low during the hold (execution venue) for the drawdown note
        last = x if x >= 0 else min(end, self.T)
        hold_l = L[e:last]
        mae = float(np.nanmin(hold_l) / px_e - 1) * 1e4 if np.isfinite(hold_l).any() else 0.0
        rec = dict(coin=self.c, mode=mode, t0=t0, t_dec=t_dec, e=e, x=x, tp_spot=tp_spot, tp=tp, px_e=px_e, px_x=px_x,
                   stop_m=stop_m, tp_start=tp_start, mae_bp=mae, trough=trough, H0=H0, ratio=ratio,
                   vol_e=float(V[e]), tp_mins=mins, tp_cum=cum)
        # AI features (all known at the decision minute t_dec)
        basis = np.nan
        if t_tr >= self.launch and np.isfinite(self.pcf[t_tr]):
            basis = (self.pcf[t_tr] / self.cf[t_tr] - 1) * 1e4
        c1 = self.cf[t_dec - 1440] if t_dec >= 1440 else np.nan
        c7 = self.cf[t_dec - 10080] if t_dec >= 10080 else np.nan
        rec.update(f_drop_sig=math.log(H0 / trough) / ev["sigW"],
                   f_speed=math.log(H0 / trough) * 1e4 / max(1, t_tr - tH0),
                   f_vr=ev["vr"], f_basis=basis,
                   f_tr1d=math.log(self.cf[t_dec] / c1) * 1e4 if np.isfinite(c1) else np.nan,
                   f_tr7d=math.log(self.cf[t_dec] / c7) * 1e4 if np.isfinite(c7) else np.nan,
                   f_hour=float(self.idx[t_dec].hour), f_coin=float(RANK[self.c]))
        return rec

    def settle(self, rec, C, theta):
        """Whole contracts, take-profit capacity at theta, P&L in USD at 1x / 2x and fee sensitivities."""
        c, size = self.c, self.size
        px_e, tp, px_x = rec["px_e"], rec["tp"], rec["px_x"]
        n = int(math.floor(C / (px_e * size)))
        if n <= 0:
            return None
        cum, mins = rec["tp_cum"], rec["tp_mins"]
        cap = theta * cum
        full = np.flatnonzero(cap >= n * size - 1e-12)
        if len(full):
            n_tp, m_tp = n, int(mins[full[0]])
        else:
            n_tp = int(math.floor((cap[-1] if len(cap) else 0.0) / size + 1e-9))
            n_tp = min(n_tp, n)
            m_tp = int(mins[-1]) if (n_tp > 0 and len(mins)) else -1
        n_x = n - n_tp
        if n_x > 0 and not np.isfinite(px_x):
            return None                                   # the position cannot be closed inside the data
        e, x = rec["e"], rec["x"]
        exit_i = m_tp if n_x == 0 else x
        exit_ts = self.idx[exit_i]
        h_tp = ((m_tp + 1 - e) / 60.0) if n_tp > 0 else 0.0
        h_x = ((x - e) / 60.0) if n_x > 0 else 0.0
        q_tp, q_x, q = n_tp * size, n_x * size, n * size
        gross = q_tp * (tp - px_e) + (q_x * (px_x - px_e) if n_x > 0 else 0.0)
        out = dict(n=n, n_tp=n_tp, notional=q * px_e, exit_i=int(exit_i), exit_ts=exit_ts,
                   exit_day=exit_ts.normalize(),
                   tp_frac=n_tp / n, hold_min=int(exit_i - e) + (1 if n_x == 0 else 0), gross=gross)
        for mult in (1.0, 2.0):
            ce = common.perp_cost_bp(c, px_e, True, mult) * q * px_e / 1e4
            ct = common.perp_cost_bp(c, tp, False, mult) * q_tp * tp / 1e4
            cx = common.perp_cost_bp(c, px_x, True, mult) * q_x * px_x / 1e4 if n_x > 0 else 0.0
            fu = (common.perp_funding_bp(h_tp, mult) * q_tp + common.perp_funding_bp(h_x, mult) * q_x) * px_e / 1e4
            pnl = gross - ce - ct - cx - fu
            k = int(mult)
            out[f"pnl_{k}x"] = pnl
            out[f"bp_{k}x"] = pnl / (q * px_e) * 1e4
            for fee in FEES_SENS:              # descriptive: all-in fee per contract per side other than $0.20
                out[f"pnl_{k}x_fee{fee:.2f}"] = pnl - mult * (fee - common.PERP_FEE_USD) * 2 * n
        out["gross_bp"] = gross / (q * px_e) * 1e4
        out["mae_usd"] = rec["mae_bp"] / 1e4 * q * px_e
        return out


# ---------------------------------------------------------------------- tables
def trade_table(coin, evs, phi, H, entry="exh", stop=False):
    """Standalone trades (no portfolio constraint) for one coin, with settlement for every capital and theta."""
    rows = []
    for ev in evs:
        rec = coin.trade(ev, phi, H, entry, stop)
        if rec is None:
            continue
        base = {k: v for k, v in rec.items() if k not in ("tp_mins", "tp_cum")}
        base.update(entry_ts=coin.idx[rec["e"]], dec_ts=coin.idx[rec["t_dec"]], t0_ts=coin.idx[rec["t0"]])
        okall = True
        for C in CAPS:
            for th in THETAS:
                s = coin.settle(rec, C, th)
                if s is None:
                    okall = False
                    break
                tag = f"{int(C / 1000)}k_{th}"
                for k_, v_ in s.items():
                    base[f"{k_}@{tag}"] = v_
            if not okall:
                break
        if okall:
            rows.append(base)
    return pd.DataFrame(rows)


def portfolio(T, C, theta):
    """One position per coin, at most MAX_COINS at once, first come first served (ties: BTC, ETH, SOL, XRP)."""
    if T.empty:
        return T
    tag = f"{int(C / 1000)}k_{theta}"
    X = T.assign(_r=T.coin.map(RANK)).sort_values(["entry_ts", "_r"])
    ex_end = np.where(X[f"n_tp@{tag}"] == X[f"n@{tag}"], X[f"exit_ts@{tag}"] + pd.Timedelta(minutes=1),
                      X[f"exit_ts@{tag}"])
    keep, open_ = [], []
    for i, (et, cn, xe) in enumerate(zip(X.entry_ts.to_numpy(), X.coin.to_numpy(), ex_end)):
        open_ = [o for o in open_ if o[0] > et]
        if any(o[1] == cn for o in open_) or len(open_) >= MAX_COINS:
            continue
        keep.append(i)
        open_.append((xe, cn))
    return X.iloc[keep].drop(columns="_r")


def daily(P, C, theta, days, col="pnl_2x"):
    tag = f"{int(C / 1000)}k_{theta}"
    if P.empty:
        return pd.Series(0.0, index=days)
    s = P.groupby(P[f"exit_day@{tag}"])[f"{col}@{tag}"].sum() / C
    s.index = pd.DatetimeIndex(s.index)
    return s.reindex(days).fillna(0.0)
