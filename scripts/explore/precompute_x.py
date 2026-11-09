#!/usr/bin/env python3
"""Explore v1: extended per-rung precompute for the R2-08 spot ladder (reports/explore/prereg.md).

Same rules as scripts/wick1m/sim.py precompute (spot venue only, as the spot bot), extended so one table serves many
ladder and exit variants:
  - rungs at 4, 5, 6, 7, 8, 9, 10 and 12 sigma below the frozen fair value (4 sigma = the R2-08 parent);
  - a deeper rung's first touch is searched over the parent's whole 60-minute window (minutes 0..59 after the parent);
    the evaluator applies the "cancel when the parent's take-profit trades" rule for whichever parent take-profit a
    variant uses;
  - take-profits at 0.3, 0.4, 0.5, 0.6, 0.7, 0.8 and 1.0 of each rung's own dislocation: first minute it trades and the
    USD volume above it in 60 minutes;
  - the 61-minute close path after each fill (for hold times up to 60 minutes), entry capacity below the bid (<= 15
    minutes) and the end of that window, trailing ADV (Coinbase spot + perp) and daily vol, as in sim.py.
Writes reports/wick1m/pre_x_<tag>.pkl (gitignored, regenerable): python scripts/explore/precompute_x.py main early
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
import sim  # noqa: E402

LADDER_X = (4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0)
TPF = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0)
H = sim.H


def ftag(f):
    return f"{int(round(f * 100)):03d}"


def precompute(tag):
    start, end, src = sim.PERIODS[tag]
    tr = pd.read_parquet(os.path.join(sim.OUT, f"trades_{tag}.parquet"))
    idx = pd.date_range(start, end, freq="min", inclusive="left")
    pm = sim.perp_mult()
    rows = []
    for c in sorted(tr.coin.unique()):
        V = {"spot": sim.load_venue(os.path.join(sim.ROOT, "data", src, f"{c}.parquet"), idx)}
        if tag != "early" and c in pm:
            p = sim.load_venue(os.path.join(sim.ROOT, "data", "cfm", f"{c}.parquet"), idx, pm[c])
            if p is not None:
                V["perp"] = p                                    # ADV only (spot + perp, as the bot)
        adv_cb, _, vol_d = sim.daily_stats(V, idx)
        S = V["spot"]
        try:
            tick_abs = sim.ws.spot_tick(c)
        except KeyError:
            tick_abs = np.nan
        n_idx = len(idx)
        for t in tr[tr.coin == c].itertuples():
            i0 = idx.get_indexer([t.ts])[0]
            if i0 < 1 or i0 + H + 1 >= n_idx:
                continue
            day = t.ts.floor("D")
            base = dict(ts=t.ts, coin=c, adv=float(adv_cb.get(day, np.nan)), vol_d=float(vol_d.get(day, np.nan)),
                        pred=float(t.pred), thr=float(t.thr), sig=float(t.sig))
            for k in LADDER_X:
                lvl = t.px if k == t.k else float(np.exp(t.fair_log - k * t.sig))
                tickf = (tick_abs / lvl) if np.isfinite(tick_abs) else 0.0
                if k == t.k:
                    i_f = i0
                else:
                    lows = np.nan_to_num(S["low"][i0:i0 + H], nan=np.inf)
                    hit = np.nonzero(lows <= lvl * (1 - tickf))[0]
                    i_f = int(i0 + hit[0]) if len(hit) else -1
                row = dict(base, k=k, filled=i_f >= 0, lvl=lvl)
                if i_f < 0:
                    rows.append(row)
                    continue
                usd, last = sim.below_usd(S, i_f, lvl)
                path = pd.Series(S["cf"][i_f:i_f + H + 1]).ffill().bfill().to_numpy()
                row.update(f_off=i_f - i0, scan_off=last - i0, in_spot=usd, g60=1e4 * np.log(path[-1] / lvl),
                           path=np.log(path / lvl).astype(np.float32))
                for f in TPF:
                    tp = lvl * np.exp(f * k * t.sig)
                    i_tp = sim.first_touch(S["high"], i_f + 1, i_f + H, tp * (1 + tickf))
                    row[f"tpo_{ftag(f)}"] = (i_tp - i_f) if i_tp >= 0 else -1
                    row[f"gtp_{ftag(f)}"] = 1e4 * np.log(tp / lvl)
                    row[f"tpv_{ftag(f)}"] = sim.above_usd(S, i_f + 1, i_f + H, tp)
                rows.append(row)
        print(f"  {c}: {int((tr.coin == c).sum())} trades", flush=True)
    P = pd.DataFrame(rows)
    P.to_pickle(os.path.join(sim.OUT, f"pre_x_{tag}.pkl"))
    print(f"precomputed {len(P)} rung rows for {P.ts.nunique()} signals -> pre_x_{tag}.pkl")
    return P


if __name__ == "__main__":
    for tag in sys.argv[1:]:
        precompute(tag)
