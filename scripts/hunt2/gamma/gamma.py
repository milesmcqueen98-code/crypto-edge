#!/usr/bin/env python3
"""Edge hunt 2, GAMMA (Path A; reports/hunt2/gamma/SPEC.md): skip every coin's 4-sigma bids while Deribit option
dealers are short gamma.

Definitions fixed before the first trial (this docstring is the record; git timestamps it):
- Signal: reports/hunt2/gamma/derived/gamma_hourly_<dev|hold>.parquet (scripts/hunt2/gamma/derive_deribit.py). For
  hour h the value uses every BTC option trade before h - 60 s, so it is >= 1 minute old at every minute of h.
  Dealer inventory per option = - cumulative signed taker contracts since listing (options listed before 2021-01-01
  excluded; none is live after 2021). G = sum inventory x BS gamma (last traded IV, index price, T to expiry) x S^2 x
  1%, the SPEC's formula, i.e. USD per 1% move (the SPEC's label "BTC per 1% move" is G / S; threshold 0 is the same
  in both units, the 25th-percentile cut is taken in the formula's units). Columns: G (all live options), Gb (strikes
  below the index), G30 / Gb30 (options expiring within 30 days of h).
- Threshold: 0, or the 25th percentile of the signal over the 10,920 DEV hours (2025-01-01 00:00 .. 2026-03-31 23:00)
  of the DEV file; the number is written to frozen.json and applied unchanged to HOLD.
- Rule: every minute of an hour whose signal is below the threshold gets m = frozen_sim.SKIP for every coin (the
  T x NC multiplier of frozen_sim.arrays(era): the 4-sigma bids, and so the parents and their deeper rungs, are off);
  m = 1 elsewhere, including minutes with no signal value (the sim's trailing minutes past an era's last day).
- n_skip = DEV research parents (pathA.parents('sel')) whose fill minute is in a skipped hour.
- Grid (8 trials): signal in {G, Gb} x threshold in {0, p25} x scope in {all, 30d}. Each trial: pathA.dev_trial(
  "gamma", variant, m=m, n_skip=n_skip) (X2, $250K, logged). Selection: the highest DEV paired HAC t among variants
  with 5-50% of DEV parents skipped; ties -> G, threshold 0, all options.

usage: python scripts/hunt2/gamma/gamma.py dev sel     (the 8 DEV trials; writes reports/hunt2/gamma/dev_trials.csv)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, "/home/claude/crypto-edge/scripts/hunt2")
import frozen_sim as F  # noqa: E402
import pathA  # noqa: E402

OUT = os.path.join(WT, "reports", "hunt2", "gamma")
COL = {("G", "all"): "G", ("G", "30d"): "G30", ("Gb", "all"): "Gb", ("Gb", "30d"): "Gb30"}
GRID = [(sig, thr, scope) for sig in ("G", "Gb") for thr in ("0", "p25") for scope in ("all", "30d")]


def signal(part):
    H = pd.read_parquet(os.path.join(OUT, "derived", f"gamma_hourly_{part}.parquet")).set_index("h").sort_index()
    return H


def threshold(H_dev, col, thr):
    return 0.0 if thr == "0" else float(np.percentile(H_dev[col].to_numpy(), 25))


def skip_hours(H, col, thr_value):
    s = H[col]
    return pd.DatetimeIndex(s.index[(s < thr_value).to_numpy()])


def mult(era, hours):
    """T x NC multiplier for an era: SKIP in every minute of the given hours, 1 elsewhere."""
    A = F.arrays(era)
    m = np.ones(A["want4"].shape)
    rows = A["idx"].floor("h").isin(hours)
    m[rows, :] = F.SKIP
    return m, int(rows.sum())


def n_skipped(era, hours):
    P = pathA.parents(era)
    return int(P.ts.dt.floor("h").isin(hours).sum()), len(P)


def dev(era):
    assert era == "sel", "dev runs are fixed to the sel era"
    H = signal("dev")
    assert H.index.min() >= pd.Timestamp("2025-01-01") and H.index.max() < pd.Timestamp("2026-04-01")
    res, series = [], {}
    for sig, thr, scope in GRID:
        col = COL[(sig, scope)]
        v = f"{sig}|{thr}|{scope}"
        tv = threshold(H, col, thr)
        hrs = skip_hours(H, col, tv)
        m, n_min = mult("sel", hrs)
        n_skip, n_par = n_skipped("sel", hrs)
        scr, d = pathA.dev_trial("gamma", v, m=m, n_skip=n_skip, note="GAMMA DEV trial (X2, $250K)", col=col,
                                 thr=tv, frac_hours=len(hrs) / len(H), frac_parents=n_skip / n_par)
        row = dict(variant=v, signal=sig, thr=thr, scope=scope, col=col, thr_value=tv, skip_hours=len(hrs),
                   frac_hours=len(hrs) / len(H), n_skip=n_skip, n_parents=n_par, frac_parents=n_skip / n_par,
                   eligible=0.05 <= n_skip / n_par <= 0.50, **{k: scr[k] for k in scr if k != "n_skipped"})
        res.append(row)
        print({k: (round(x, 4) if isinstance(x, float) else x) for k, x in row.items()}, flush=True)
        series[v] = d
    R = pd.DataFrame(res)
    R.to_csv(os.path.join(OUT, "dev_trials.csv"), index=False)
    pd.DataFrame(series).to_parquet(os.path.join(OUT, "dev_series_x2.parquet"))
    return R


if __name__ == "__main__":
    if sys.argv[1] == "dev":
        dev(sys.argv[2])
    else:
        raise SystemExit("hold: implemented after the freeze in gamma_hold.py")
