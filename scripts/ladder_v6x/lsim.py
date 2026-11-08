#!/usr/bin/env python3
"""Ladder v6 (exits): the frozen simulator that ladder v5 named for the next round.

  cash rule   red team 1's engine-faithful replay of bot/spot/engine.py: frozen/rt_live.py, unchanged from
              origin/ladder/redteam (75ecbd3); it feeds funded sizes to scripts/ladder_v5/fsim.py evaluate
  exit costs  red team 2's print-measured half-spread + first-X slippage for each remainder's 60-minute market exit:
              frozen/c3.py PrintCost on reports/ladder_v5/prints_rt2_{exit,coin}.csv, unchanged from
              origin/ladder/redteam2, applied exactly as red team 1's rt_prints.rem_daily (copied below, unchanged
              apart from its home); an exit with no prints keeps the model's cost x cost_mult
  the rest    scripts/ladder_v5/fsim.py, sim.py, the frozen dataset (reports/ladder_v5/frozen, SHA256SUMS)

Configurations as in ladder v5 (S* = today's volumes, unverified costs doubled). Incumbent's best estimate to
reproduce (red team 1's addendum, S* theta 0.5, $250K): 22.8% / 19.1% / 11.1% a year, Sharpe 2.94 / 2.66 / 1.91.
Tranche frames of the incumbent are cached in reports/ladder_v6x/books/ (the exit research works on them).
usage: python scripts/ladder_v6x/lsim.py reproduce [cfg ...]
"""
import hashlib
import os
import shutil
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LV5 = os.path.join(ROOT, "scripts", "ladder_v5")
sys.path.insert(0, LV5)
import gates  # noqa: E402,F401  (first: scripts/hunt has its own gates.py on the path fsim adds)
sys.path.insert(0, os.path.join(HERE, "frozen"))
import rt_live as RL  # noqa: E402
import c3 as RT2  # noqa: E402
import fsim  # noqa: E402

assert os.path.dirname(os.path.abspath(fsim.__file__)) == LV5
OUT = os.path.join(ROOT, "reports", "ladder_v6x")
BOOKS = os.path.join(OUT, "books")
CONFIGS = {"S_0.5": dict(theta=0.5, C=250e3, today=True, cost_mult=2.0),
           "S_0.25": dict(theta=0.25, C=250e3, today=True, cost_mult=2.0),
           "base_0.5": dict(theta=0.5, C=250e3, today=False, cost_mult=1.0),
           "cap_1M": dict(theta=0.5, C=1e6, today=True, cost_mult=2.0)}
ERAS = list(fsim.ERAS)                                   # sel, chk, early
_PC = {}


def ensure_frozen():
    """fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl (gitignored): copy the frozen pickles there, hash-checked."""
    fz = os.path.join(ROOT, "reports", "ladder_v5", "frozen")
    sums = {}
    for line in open(os.path.join(fz, "SHA256SUMS")):
        h, f = line.split()
        sums[os.path.basename(f)] = h
    for tag in ("main", "early"):
        name = f"pre_hunt_{tag}.pkl"
        src, dst = os.path.join(fz, name), os.path.join(ROOT, "reports", "wick1m", name)
        assert hashlib.sha256(open(src, "rb").read()).hexdigest() == sums[name], name
        if not os.path.exists(dst) or hashlib.sha256(open(dst, "rb").read()).hexdigest() != sums[name]:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)


def pcost():
    if "pc" not in _PC:
        _PC["pc"] = RT2.PrintCost()
    return _PC["pc"]


def rem_daily(Q, info, cfg, era, C, cost="print"):
    """red team 1's rt_prints.rem_daily: daily P&L / C of a tranche frame with the remainders' market exit at minute 60
    under `cost`, and the share of remainder dollars priced from prints."""
    kw = CONFIGS[cfg]
    tag, (lo, hi) = fsim.ERAS[era]
    tk_fee = info["taker_bp"] / 1e4
    hs = fsim.HS_BP * kw["cost_mult"] / 1e4
    y = fsim.IMPACT_Y * kw["cost_mult"]
    sc = fsim.today_scale(RL.inputs(tag)["P"], lo, hi) if kw["today"] else {}
    rem = np.maximum((Q.fill - Q.tp_fill).to_numpy(), 0.0)
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    fsc = Q.coin.map(sc).fillna(1.0).to_numpy() if sc else np.ones(len(Q))
    g60 = Q.g60.to_numpy() / 1e4
    coin, fill_t = Q.coin.to_numpy(), Q.fill_t.to_numpy()
    pc = pcost()
    pnl = np.zeros(len(Q))
    hit = 0.0
    for i in np.nonzero(rem > 0)[0]:
        R = rem[i]
        model = hs + y * vol_d[i] * np.sqrt(R / adv[i])
        if cost == "print":
            fb = 1e4 * fsim.IMPACT_Y * vol_d[i] * np.sqrt(R / adv[i])
            ci = pc.cost(coin[i], pd.Timestamp(fill_t[i]), 0, R / fsc[i], fb_bp=fb)
            if np.isfinite(ci):
                hit += R
            else:
                ci = model
        else:
            ci = model
        pnl[i] = R * (g60[i] - tk_fee - ci)
    idx = pd.date_range(lo, hi, freq="D")
    ex_day = (Q.fill_t + pd.Timedelta(minutes=60)).dt.floor("D").to_numpy()
    s = pd.concat([pd.Series((Q.pnl_tp - Q.entry_cost).to_numpy(), index=Q.tp_t.dt.floor("D").to_numpy()),
                   pd.Series(pnl[rem > 0], index=ex_day[rem > 0])]).groupby(level=0).sum()
    return s.reindex(idx, fill_value=0.0) / C, (hit / rem.sum() if rem.sum() > 0 else np.nan), rem.sum()


def bound_books(cfg, era, A=None, rem_extra=0):
    """The incumbent's two latency bounds on the engine-faithful replay: {bound: (Qo, info)}."""
    kw = CONFIGS[cfg]
    tag = fsim.ERAS[era][0]
    if A is None:
        A = RL.era_arrays(tag, era, kw["theta"], kw["C"], kw["today"])
    out = {}
    for bound in ("minute", "instant"):
        R = RL.replay(A, theta=kw["theta"], C=kw["C"], bound=bound, policy="engine", rem_extra=rem_extra)
        _, Qo, info = RL.evaluate_live(A, R, kw["theta"], kw["C"], era, kw["cost_mult"])
        out[bound] = (Qo, info)
    return out


def blend(era, theta, d_min, d_inst):
    s = fsim.lat_share(era, theta)
    return d_min + s * (d_inst - d_min)


def cache_path(cfg, era, bound):
    return os.path.join(BOOKS, f"inc_{cfg}_{era}_{bound}.parquet")


def load_books(cfg, era):
    """Cached tranche frames + info of the incumbent (built by `reproduce`)."""
    info = pd.read_csv(os.path.join(BOOKS, "info.csv"))
    out = {}
    for b in ("minute", "instant"):
        r = info[(info.cfg == cfg) & (info.era == era) & (info.bound == b)].iloc[0]
        out[b] = (pd.read_parquet(cache_path(cfg, era, b)), dict(maker_bp=r.maker_bp, taker_bp=r.taker_bp))
    return out


def incumbent_daily(cfg, era, out=None, cost="print"):
    kw = CONFIGS[cfg]
    out = out or load_books(cfg, era)
    d = {b: rem_daily(out[b][0], out[b][1], cfg, era, kw["C"], cost)[0] for b in ("minute", "instant")}
    return blend(era, kw["theta"], d["minute"], d["instant"])


def reproduce(cfgs):
    """Rebuild the incumbent on the frozen simulator, cache its tranche frames, and check it against red team 1's
    committed daily series (reports/ladder_v6x/ref/rt1_daily_<cfg>.parquet, column <cfg>|<era>|inc|print)."""
    ensure_frozen()
    os.makedirs(BOOKS, exist_ok=True)
    rows, lines = [], []
    t0 = time.time()
    for cfg in cfgs:
        kw = CONFIGS[cfg]
        ref = pd.read_parquet(os.path.join(OUT, "ref", f"rt1_daily_{cfg}.parquet"))
        for era in ERAS:
            out = bound_books(cfg, era)
            for b in ("minute", "instant"):
                Qo, info = out[b]
                keep = [c for c in Qo.columns if c != "path"]
                Qo[keep].to_parquet(cache_path(cfg, era, b))
                rows.append(dict(cfg=cfg, era=era, bound=b, maker_bp=info["maker_bp"], taker_bp=info["taker_bp"]))
            d = incumbent_daily(cfg, era, out)
            r = ref[f"{cfg}|{era}|inc|print"].dropna()
            diff = float((d.reindex(r.index, fill_value=0.0) - r).abs().max())
            st = fsim.stats(d, kw["C"], era)
            lines.append(f"{cfg} {era}: {100 * st['ret_yr']:.2f}% / Sharpe {st['sharpe']:.3f}; max daily diff vs red "
                         f"team 1 {diff:.1e} ({time.time() - t0:.0f}s)")
            print(lines[-1], flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(BOOKS, "info.csv"), index=False,
                              mode="a" if os.path.exists(os.path.join(BOOKS, "info.csv")) else "w",
                              header=not os.path.exists(os.path.join(BOOKS, "info.csv")))
    open(os.path.join(OUT, "reproduce.txt"), "a").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "reproduce":
        reproduce(sys.argv[2:] or list(CONFIGS))
