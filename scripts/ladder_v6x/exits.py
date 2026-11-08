#!/usr/bin/env python3
"""Ladder v6 (exits): exit dataset, exit layer, oracle bounds and the hold-or-sell rule family, on the frozen simulator
(scripts/ladder_v6x/lsim.py). Pre-registration: reports/ladder_v6x_prereg.md.

Minute m of a tranche is the candle that starts at fill_t + m. An exit "at m" sells the unsold part at that candle's
close, i.e. at fill_t + m + 1 min; m = 60 is the incumbent's exit. A rule deciding at m sees only that close and earlier.

exit dataset   per tranche: closes as log return from the entry (bp), USD traded above the take-profit per minute and
               the first take-profit touch (the frozen tick convention of scripts/wick1m/sim.py), minutes 0..120; BTC's
               move since the fill (bp); cascade breadth = coins with a research parent fill in minutes m-29..m
take-profit    the incumbent books its whole-window take-profit fill at the first touch. Here the fill accrues with the
               USD traded above the take-profit from the touch on and reaches the incumbent's fill at minute 60 (so an
               early exit keeps only what had traded). After 60 the order keeps resting and gets theta x the later USD
               above it (x the today's-volume factor in S*), shared pro rata among a parent's tranches still open.
exit costs     prereg "Exit costs at any minute": print-measured at 60 / 65 / 75 (PrintCost offsets 0 / 5 / 15),
               kappa(m) x the minute-60 cost before 60, linear in m between 60, 65 and 75, the 75-minute cost after 75.
               A tranche without event prints: the frozen model where the incumbent priced its exit by the model (keeps
               parity; dearer than prints), else the coin-era pooled print cost x kappa(m), else the model x kappa(m).
parity         exit at 60 everywhere reproduces lsim.rem_daily (the incumbent) to float precision (parity()).
usage: python scripts/ladder_v6x/exits.py build sel | parity sel
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lsim  # noqa: E402
from lsim import CONFIGS, OUT, ROOT, RL, fsim  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import wick_sim as ws  # noqa: E402

HMAX = 120
H0 = 60
W = HMAX + 1
EXD = os.path.join(OUT, "exitdata")
SRC = {"main": "minute", "early": "minute_early"}
FEATURES = ("mark", "rec", "k", "btc", "breadth", "m")


# ------------------------------------------------------------------------------------------------ exit dataset
def minute_arrays(coin, idx, src):
    path = os.path.join(ROOT, "data", src, f"{coin}.parquet")
    if not os.path.exists(path):
        return None
    m = pd.read_parquet(path).drop_duplicates("ts").set_index("ts").sort_index()
    m = m[m.volume > 0].reindex(idx)
    out = {k: m[k].to_numpy(np.float64) for k in ("high", "low", "close")}
    out["vol"] = m["volume"].fillna(0.0).to_numpy(np.float64)
    out["cf"] = m["close"].ffill(limit=30).to_numpy(np.float64)
    return out


def breadth_series(tag, idx):
    """Distinct coins with a research parent fill (4-sigma rung filled) in minutes t-29..t, for every t of idx."""
    P = RL.inputs(tag)["P"]
    par = P[(P.k == 4.0) & P.filled]
    pos = idx.get_indexer(par.ts)
    coins = sorted(par.coin.unique())
    pres = np.zeros((len(idx), len(coins)), np.int32)
    for j, c in enumerate(coins):
        p = pos[(par.coin == c).to_numpy() & (pos >= 0)]
        pres[p, j] = 1
    cs = np.cumsum(pres, axis=0)
    lag = np.vstack([np.zeros((30, len(coins)), cs.dtype), cs[:-30]])
    return ((cs - lag) > 0).sum(axis=1).astype(np.int16)


def era_idx(era):
    lo, hi = fsim.ERAS[era][1]
    return pd.date_range(pd.Timestamp(lo) - pd.Timedelta(days=2), pd.Timestamp(hi) + pd.Timedelta(days=3), freq="min",
                         inclusive="left")


def build(era, frames):
    """Exit dataset for every filled tranche of `frames` (cached tranche frames of that era)."""
    tag = fsim.ERAS[era][0]
    src = SRC[tag]
    idx = era_idx(era)
    K = pd.concat([Q.loc[Q.fill > 0, ["coin", "fill_t", "lvl", "g_tp"]] for Q in frames])
    K = K.drop_duplicates(["coin", "fill_t", "lvl"]).sort_values(["coin", "fill_t", "lvl"]).reset_index(drop=True)
    n = len(K)
    C = np.full((n, W), np.nan)
    AB = np.zeros((n, W))
    B = np.full((n, W), np.nan)
    BR = np.zeros((n, W), np.int16)
    touch = np.full(n, -1, np.int32)
    btc = minute_arrays("BTC", idx, src)
    br_all = breadth_series(tag, idx)
    t0 = time.time()
    for coin, g in K.groupby("coin"):
        S = minute_arrays(coin, idx, src)
        try:
            tick = ws.spot_tick(coin)
        except KeyError:
            tick = np.nan
        for r in g.itertuples():
            i_f = idx.get_loc(r.fill_t)
            sl = slice(i_f, i_f + W)
            path = pd.Series(S["cf"][sl]).ffill().bfill().to_numpy()
            C[r.Index] = 1e4 * np.log(path / r.lvl)
            tp = r.lvl * np.exp(r.g_tp / 1e4)
            tickf = (tick / r.lvl) if np.isfinite(tick) else 0.0
            hi_, lo_, v = S["high"][sl], S["low"][sl], S["vol"][sl]
            ok = np.isfinite(hi_) & (np.nan_to_num(hi_) > tp)
            rng = hi_ - lo_
            frac = np.where(rng <= 0, 1.0, np.minimum(1.0, (hi_ - tp) / np.where(rng > 0, rng, 1.0)))
            ab = np.where(ok, v * frac * 0.5 * (tp + hi_), 0.0)
            ab[0] = 0.0                                     # the incumbent counts minutes 1..60
            AB[r.Index] = np.cumsum(ab)
            th = np.nonzero(np.nan_to_num(hi_[1:]) >= tp * (1 + tickf))[0]
            touch[r.Index] = th[0] + 1 if len(th) else -1
            if btc is not None:
                bp = pd.Series(btc["cf"][sl]).ffill().bfill().to_numpy()
                B[r.Index] = 1e4 * np.log(bp / bp[0])
            BR[r.Index] = br_all[sl]
    os.makedirs(EXD, exist_ok=True)
    np.savez_compressed(os.path.join(EXD, f"paths_{era}.npz"), C=C.astype(np.float32), AB=AB, B=B.astype(np.float32),
                        BR=BR, touch=touch)
    K.to_parquet(os.path.join(EXD, f"keys_{era}.parquet"))
    print(f"exit dataset {era}: {n} tranches, {time.time() - t0:.0f}s", flush=True)


class Data:
    def __init__(self, era):
        z = np.load(os.path.join(EXD, f"paths_{era}.npz"))
        self.C, self.AB, self.B, self.BR, self.touch = (z[k] for k in ("C", "AB", "B", "BR", "touch"))
        self.K = pd.read_parquet(os.path.join(EXD, f"keys_{era}.parquet"))
        self.row = {(c, pd.Timestamp(t), round(float(lv), 12)): i
                    for i, (c, t, lv) in enumerate(zip(self.K.coin, self.K.fill_t, self.K.lvl))}

    def rows(self, Q):
        return np.array([self.row[(c, pd.Timestamp(t), round(float(lv), 12))]
                         for c, t, lv in zip(Q.coin, Q.fill_t, Q.lvl)])


# ------------------------------------------------------------------------------------------------ costs
_POOL = {}


def hs_pool():
    if "hs" not in _POOL:
        X = pd.read_csv(os.path.join(fsim.OUT, "prints_rt2_exit.csv"))
        _POOL["hs"] = X.groupby(["coin", "era_tag"]).hs_bp.median().to_dict()
    return _POOL["hs"]


def vcost(hs, s, xs, x, fb):
    """PrintCost.cost vectorised over sizes x (USD) with fallback fb (bp, same shape): fraction, NaN without data."""
    if not np.isfinite(hs):
        return np.full(len(x), np.nan)
    ok = np.isfinite(s)
    if not ok.any():
        return np.full(len(x), np.nan)
    xo = xs[ok]
    ss = np.maximum.accumulate(np.maximum(s[ok], 0.0))
    sl = np.where(x <= xo[0], ss[0] * x / xo[0],
                  np.where(x <= xo[-1], np.interp(x, xo, ss), np.maximum(ss[-1] * x / xo[-1], fb)))
    return (hs + sl) / 1e4


def kappa_vec(kappa):
    """kappa(m) for m = 0..HMAX: a number (bracket before measurement) or a dict {minute: ratio} (measured; linear
    between measured minutes, the first value before them); 1 from minute 60 on (60-75 use the frozen costs)."""
    m = np.arange(W, dtype=float)
    if isinstance(kappa, dict):
        ks = sorted(kappa)
        k = np.interp(m, ks, [kappa[x] for x in ks])
    else:
        k = np.full(W, float(kappa))
    k[H0:] = 1.0
    return k


# ------------------------------------------------------------------------------------------------ exit layer
class ExitBook:
    """One tranche frame (config, era, latency bound) with the value of exiting each tranche's unsold part at every
    minute 0..HMAX: VAL[i, m] (USD, the tranche's whole P&L), TPF / R (take-profit fill / unsold USD at m), COST."""

    def __init__(self, Q, info, cfg, era, D, kappa):
        kw = CONFIGS[cfg]
        self.cfg, self.era, self.kw = cfg, era, kw
        tag, (lo, hi) = fsim.ERAS[era]
        self.adv_med, self.vol_med = Q.adv.median(), Q.vol_d.median()     # rem_daily fills gaps over the whole frame
        Q = Q[Q.fill > 0].reset_index(drop=True)
        self.Q = Q
        n = len(Q)
        r = D.rows(Q)
        self.C, self.AB, self.B, self.BR = D.C[r].astype(np.float64), D.AB[r], D.B[r].astype(np.float64), D.BR[r]
        touch = D.touch[r]
        self.mk, self.tk = info["maker_bp"] / 1e4, info["taker_bp"] / 1e4
        sc = fsim.today_scale(RL.inputs(tag)["P"], lo, hi) if kw["today"] else {}
        self.fsc = Q.coin.map(sc).fillna(1.0).to_numpy() if sc else np.ones(n)
        fill, tpi, tp_off = Q.fill.to_numpy(), Q.tp_fill.to_numpy(), Q.tp_off.to_numpy()
        self.fill, self.tpi = fill, tpi
        self.g_tp, self.g60 = Q.g_tp.to_numpy(), Q.g60.to_numpy()
        self.k = Q.k.to_numpy()
        # parity: the incumbent's 60-minute close
        self.c60_gap = np.abs(self.C[:, H0] - self.g60)
        self.C[:, H0] = self.g60
        # take-profit fill by minute
        m = np.arange(W)
        A60 = self.AB[:, H0]
        frac = np.where(A60[:, None] > 0, self.AB[:, :H0 + 1] / np.where(A60 > 0, A60, 1.0)[:, None], 1.0)
        on = (tp_off[:, None] >= 0) & (m[None, :H0 + 1] >= tp_off[:, None])
        TPF = np.zeros((n, W))
        TPF[:, :H0 + 1] = np.where(on, tpi[:, None] * np.minimum(frac, 1.0), 0.0)
        TPF[:, H0] = tpi
        rem60 = np.maximum(fill - tpi, 0.0)
        start = np.where(tp_off >= 0, H0 + 1, np.where(touch > H0, touch, 10 ** 6))
        extra = (self.AB[:, H0 + 1:] - A60[:, None]) * self.fsc[:, None] * kw["theta"]
        extra = np.where(m[None, H0 + 1:] >= start[:, None], extra, 0.0)
        grp = Q.groupby(["ts", "coin"]).ngroup().to_numpy()
        tot = pd.Series(rem60).groupby(grp).transform("sum").to_numpy()
        share = np.where(tot > 0, rem60 / np.where(tot > 0, tot, 1.0), 0.0)
        TPF[:, H0 + 1:] = tpi[:, None] + np.minimum(rem60[:, None], extra * share[:, None])
        self.TPF = TPF
        self.R = np.maximum(fill[:, None] - TPF, 0.0)
        self.R[:, H0] = rem60
        self.touch2 = start
        # costs
        self.COST = self._costs(kappa, tag, rem60)
        self.entry = Q.entry_cost.to_numpy()
        gt = self.g_tp / 1e4 - self.mk
        self.VAL = TPF * gt[:, None] + self.R * (self.C / 1e4 - self.tk - self.COST) - self.entry[:, None]
        self.tp_day = Q.tp_t.dt.floor("D").to_numpy()
        self.fill_t = Q.fill_t.to_numpy()
        self.pnl_tp_inc = Q.pnl_tp.to_numpy()
        self.quarter = Q.fill_t.dt.to_period("Q").astype(str).to_numpy()

    def _costs(self, kappa, tag, rem60):
        Q, kw = self.Q, self.kw
        pc = lsim.pcost()
        hp = hs_pool()
        km = kappa_vec(kappa)
        hs_m = fsim.HS_BP * kw["cost_mult"] / 1e4
        y = fsim.IMPACT_Y * kw["cost_mult"]
        adv = Q.adv.fillna(self.adv_med).to_numpy()
        vol_d = Q.vol_d.fillna(self.vol_med).to_numpy()
        n = len(Q)
        COST = np.zeros((n, W))
        self.cost_src = np.empty(n, object)
        mm = np.arange(W)
        for i in range(n):
            R = self.R[i]
            X = R / self.fsc[i]
            fb = 1e4 * fsim.IMPACT_Y * vol_d[i] * np.sqrt(R / adv[i])
            model = hs_m + y * vol_d[i] * np.sqrt(R / adv[i])
            key = (Q.coin.iat[i], pd.Timestamp(Q.fill_t.iat[i]))
            v0 = pc.tab.get(key + (0,))
            c0 = vcost(v0[0], v0[1], pc.xs, X, fb) if v0 is not None else np.full(W, np.nan)
            if np.isfinite(c0).all():
                out = []
                for off in (5, 15):
                    v = pc.tab.get(key + (off,))
                    c = vcost(v[0], v[1], pc.xs, X, fb) if v is not None else np.full(W, np.nan)
                    out.append(np.where(np.isfinite(c), c, c0))
                c5, c15 = out
                cst = c0 * km
                a = (mm > H0) & (mm < 65)
                cst[a] = c0[a] + (c5[a] - c0[a]) * (mm[a] - H0) / 5.0
                cst[65] = c5[65]
                b = (mm > 65) & (mm < 75)
                cst[b] = c5[b] + (c15[b] - c5[b]) * (mm[b] - 65) / 10.0
                cst[75:] = c15[75:]
                self.cost_src[i] = "event"
            elif rem60[i] > 0:
                cst = model * km
                self.cost_src[i] = "model(inc)"
            else:
                pl = pc.pool.get((key[0], tag))
                c = vcost(hp.get((key[0], tag), np.nan), pl, pc.xs, X, fb) if pl is not None else np.full(W, np.nan)
                if np.isfinite(c).all():
                    cst = c * km
                    self.cost_src[i] = "pool"
                else:
                    cst = model * km
                    self.cost_src[i] = "model"
            COST[i] = cst
        return COST

    def daily(self, mx):
        """Daily P&L / C when tranche i sells its unsold part at minute mx[i]."""
        i = np.arange(len(self.Q))
        mx = np.asarray(mx, int)
        m60 = np.minimum(mx, H0)
        gt = self.g_tp / 1e4 - self.mk
        tp_part = self.TPF[i, m60] * gt - self.entry
        ex_part = (self.TPF[i, mx] - self.TPF[i, m60]) * gt + self.R[i, mx] * (
            self.C[i, mx] / 1e4 - self.tk - self.COST[i, mx])
        ex_day = (pd.to_datetime(self.fill_t) + pd.to_timedelta(mx, unit="m")).floor("D").to_numpy()
        lo, hi = fsim.ERAS[self.era][1]
        idx = pd.date_range(lo, hi, freq="D")
        s = pd.concat([pd.Series(tp_part, index=self.tp_day), pd.Series(ex_part, index=ex_day)]).groupby(level=0).sum()
        return s.reindex(idx, fill_value=0.0) / self.kw["C"]


# ------------------------------------------------------------------------------------------------ books and stats
def frames(cfg, era, ext=0):
    """Tranche frames: the incumbent's (cached) or, with ext > 0, the cash-rule bound with every remainder held ext
    more minutes (cached on first use)."""
    if ext == 0:
        return lsim.load_books(cfg, era)
    out = {}
    paths = {b: os.path.join(lsim.BOOKS, f"ext{ext}_{cfg}_{era}_{b}.parquet") for b in ("minute", "instant")}
    if all(os.path.exists(p) for p in paths.values()):
        info = pd.read_csv(os.path.join(lsim.BOOKS, "info.csv"))
        for b, p in paths.items():
            r = info[(info.cfg == cfg) & (info.era == era) & (info.bound == b)].iloc[0]
            out[b] = (pd.read_parquet(p), dict(maker_bp=r.maker_bp, taker_bp=r.taker_bp))
        return out
    lsim.ensure_frozen()
    bb = lsim.bound_books(cfg, era, rem_extra=ext)
    for b, (Qo, info) in bb.items():
        Qo[[c for c in Qo.columns if c != "path"]].to_parquet(paths[b])
        out[b] = (Qo, info)
    return out


def books(cfg, era, D, kappa, ext=0):
    return {b: ExitBook(Qo, info, cfg, era, D, kappa) for b, (Qo, info) in frames(cfg, era, ext).items()}


def blended(bk, rule):
    """Daily series of a rule (rule(book) -> exit minute per tranche) on both latency bounds, blended."""
    eb = next(iter(bk.values()))
    d = {b: x.daily(rule(x)) for b, x in bk.items()}
    return lsim.blend(eb.era, eb.kw["theta"], d["minute"], d["instant"])


def compare(inc, cand, cfg, era):
    C = CONFIGS[cfg]["C"]
    si, sc = fsim.stats(inc, C, era), fsim.stats(cand, C, era)
    d = cand - inc
    return dict(inc_ret=si["ret_yr"], inc_sharpe=si["sharpe"], ret=sc["ret_yr"], sharpe=sc["sharpe"],
                d_ret=sc["ret_yr"] - si["ret_yr"], d_sharpe=sc["sharpe"] - si["sharpe"],
                mean_bp=1e4 * float(d.mean()), t=float(fsim.nw_t(d)))


def at60(x):
    return np.full(len(x.Q), H0)


def parity(era="sel", cfgs=("S_0.5",)):
    D = Data(era)
    lines = []
    for cfg in cfgs:
        bk = books(cfg, era, D, 1.0)
        d = blended(bk, at60)
        ref = lsim.incumbent_daily(cfg, era)
        gap = max(float(x.c60_gap.max()) for x in bk.values())
        src = pd.Series(np.concatenate([x.cost_src for x in bk.values()])).value_counts().to_dict()
        lines.append(f"parity {cfg} {era}: max daily diff {float((d - ref).abs().max()):.1e}; max |close60 - g60| "
                     f"{gap:.2e} bp; cost sources {src}")
        print(lines[-1], flush=True)
    return lines


if __name__ == "__main__":
    cmd, era = sys.argv[1], sys.argv[2]
    if cmd == "build":
        fr = []
        for cfg in sys.argv[3:] or ["S_0.5"]:
            for ext in (0, 60):
                fr += [q for q, _ in frames(cfg, era, ext).values()]
        build(era, fr)
    elif cmd == "parity":
        parity(era, tuple(sys.argv[3:]) or ("S_0.5",))


def measured_kappa():
    """kappa(m) measured on the pre-registered sample (reports/ladder_v6x/kappa/kappa.csv, branch ladder/v6x-kappa):
    {minute: median ratio}, or 2 at a minute with fewer than 100 valid pairs (pre-registered)."""
    k = pd.read_csv(os.path.join(OUT, "kappa", "kappa.csv"))
    return {int(r.m): (float(r.kappa) if r.n_valid >= 100 else 2.0) for r in k.itertuples()}
