#!/usr/bin/env python3
"""Ladder v5: every minute a deeper rung could fill, not just the first (for the live cash rule, hsim).

The research precompute (scripts/wick1m/sim.py) records each 6/8-sigma rung's first trade-through after the parent's
fill. Live, a rung that is placed late (it waited for cash) still fills if the price trades through it again before
its window closes (the parent's take-profit or 60 minutes). For every deeper rung of the frozen dataset (filled or
not), this lists each minute of its window with a one-tick trade-through and the research quantities from that minute,
computed exactly as sim.precompute does: spot volume below the bid while the price stays below it (<= 15 min) and the
end of that scan, the take-profit's first touch and the volume above it over 60 minutes, and the 60-minute close.
Writes reports/ladder_v5/deep_paths_<tag>.pkl: {row index of fsim.load(tag): DataFrame(off, in_spot, scan_off,
tp_off, tp_spot, g60, g_tp)}.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fsim  # noqa: E402
import sim  # noqa: E402

sys.path.insert(0, os.path.join(fsim.ROOT, "scripts"))
import wick_sim as ws  # noqa: E402


def main(tag):
    P = fsim.load(tag)
    start, end, src = sim.PERIODS[tag]
    idx = pd.date_range(start, end, freq="min", inclusive="left")
    out = {}
    for c in sorted(P.coin.unique()):
        S = sim.load_venue(os.path.join(fsim.ROOT, "data", src, f"{c}.parquet"), idx)
        try:
            tick_abs = ws.spot_tick(c)
        except KeyError:
            tick_abs = np.nan
        G = P[P.coin == c]
        par = G[G.k == 4.0].set_index("ts")
        for i_row, r in G[G.k > 4.0].iterrows():
            if r.ts not in par.index:
                continue
            p = par.loc[r.ts]
            i0 = idx.get_indexer([r.ts])[0]
            close_par = i0 + (int(p.tp_off) if p.tp_off >= 0 else sim.H)     # parent's take-profit touch or 60 min
            lvl = float(r.lvl)
            tickf = (tick_abs / lvl) if np.isfinite(tick_abs) else 0.0
            sig = float(np.log(p.lvl / lvl) / (r.k - 4.0)) if r.k > 4 else np.nan     # lvl_k = fair - k sigma
            tp = lvl * np.exp(0.6 * r.k * sig)
            lows = np.nan_to_num(S["low"][i0:close_par], nan=np.inf)
            hits = np.nonzero(lows <= lvl * (1 - tickf))[0]
            rows = []
            for h in hits:
                i_f = i0 + int(h)
                if i_f + sim.H + 1 >= len(idx):
                    continue
                usd, last = sim.below_usd(S, i_f, lvl)
                i_tp = sim.first_touch(S["high"], i_f + 1, i_f + sim.H, tp * (1 + tickf))
                path = pd.Series(S["cf"][i_f:i_f + sim.H + 1]).ffill().bfill().to_numpy()
                rows.append(dict(off=int(h), in_spot=usd, scan_off=last - i0,
                                 tp_off=(i_tp - i_f) if i_tp >= 0 else -1,
                                 tp_spot=sim.above_usd(S, i_f + 1, i_f + sim.H, tp * 1.0),
                                 g60=1e4 * np.log(path[-1] / lvl), g_tp=1e4 * np.log(tp / lvl)))
            out[i_row] = pd.DataFrame(rows)
        print(c, flush=True)
    pd.to_pickle(out, os.path.join(fsim.OUT, f"deep_paths_{tag}.pkl"))
    # check: for filled rungs the first through-minute must equal the research's
    bad = 0
    for i_row, D in out.items():
        r = P.loc[i_row]
        if r.filled and (not len(D) or int(D.off.iloc[0]) != int(r.f_off)):
            bad += 1
        if r.filled and len(D):
            d0 = D.iloc[0]
            if abs(d0.in_spot - r.in_spot) > 1e-6 * max(1.0, r.in_spot) or int(d0.tp_off) != int(r.tp_off) \
                    or abs(d0.g60 - r.g60) > 1e-6:
                bad += 1
    print(f"{len(out)} deeper rungs; mismatches with the research first fill: {bad}")


if __name__ == "__main__":
    for t in sys.argv[1:] or ("main", "early"):
        main(t)
