#!/usr/bin/env python3
"""Ladder v5: the minutes after each rung's 60-minute time exit (for the passive-exit candidate, C2).

For every filled tranche of the frozen dataset (fsim.load), the coin's spot candles at fill+60 .. fill+60+N
(N = 15): close, high and the USD volume traded above each minute's peg price (candle volume spread evenly over the
range, as the simulator's take-profit capacity). The peg for minute j (j >= 1) is the previous minute's close plus
one tick (a post-only sell resting at the ask, re-pegged every minute); it fills on a one-tick trade-through.
Writes reports/ladder_v5/exit_paths_<tag>.pkl (index aligned to fsim.load(tag)).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fsim  # noqa: E402

N = 15


def tick_abs(c):
    sys.path.insert(0, os.path.join(fsim.ROOT, "scripts"))
    import wick_sim as ws
    try:
        return float(ws.spot_tick(c))
    except KeyError:
        return np.nan


def main(tag):
    P = fsim.load(tag)
    src = "minute" if tag == "main" else "minute_early"
    out = {}
    for c, g in P[P.filled].groupby("coin"):
        m = pd.read_parquet(os.path.join(fsim.ROOT, "data", src, f"{c}.parquet")).drop_duplicates("ts").set_index("ts").sort_index()
        m = m[m.volume > 0]
        tk = tick_abs(c)
        full = pd.date_range(m.index.min(), m.index.max(), freq="min")
        cl = m.close.reindex(full).ffill().to_numpy(np.float64)
        hi = m.high.reindex(full).to_numpy(np.float64)
        lo = m.low.reindex(full).to_numpy(np.float64)
        vo = m.volume.reindex(full).fillna(0.0).to_numpy(np.float64)
        t0 = full[0]
        for i, r in g.iterrows():
            ft = r.ts + pd.Timedelta(minutes=int(r.f_off))
            a = int((ft - t0) / pd.Timedelta(minutes=1)) + 60
            if a + N >= len(cl) or a < 0:
                continue
            lvl = r.lvl
            c60 = cl[a]
            gain = np.full(N + 1, np.nan)             # gross (log, vs the entry level) of a passive sale in minute j
            cap = np.zeros(N + 1)                      # USD volume above the peg in minute j
            close_g = np.log(cl[a:a + N + 1] / lvl)    # market exit at the close of minute 60+j
            for j in range(1, N + 1):
                peg = cl[a + j - 1] + (tk if np.isfinite(tk) else 0.0)
                h, l_, v = hi[a + j], lo[a + j], vo[a + j]
                gain[j] = np.log(peg / lvl)
                if np.isfinite(h) and h >= peg + (tk if np.isfinite(tk) else 0.0) * (1 - 1e-9):
                    rng = h - l_
                    frac = 1.0 if rng <= 0 else min(1.0, (h - peg) / rng)
                    cap[j] = v * frac * 0.5 * (peg + h)
            out[i] = dict(c60=np.log(c60 / lvl), close_g=close_g.astype(np.float32), pas_g=gain.astype(np.float32),
                          pas_cap=cap.astype(np.float32))
        print(c, len(g), flush=True)
    E = pd.DataFrame.from_dict(out, orient="index")
    E.to_pickle(os.path.join(fsim.OUT, f"exit_paths_{tag}.pkl"))
    print(f"{len(E)} tranches -> exit_paths_{tag}.pkl")


if __name__ == "__main__":
    for t in sys.argv[1:] or ("main", "early"):
        main(t)
