#!/usr/bin/env python3
"""Red team 2 (ladder v5): an independent implementation of C2a (margin-tercile sizing) and post-hoc placebos.

C2a, from reports/ladder_v5/specs/sizing.md and the pre-registration: the whole ladder of a signal is sized
x0.5 / x1.0 / x1.5 by the tercile of the AI's margin (prediction minus the quarter's threshold). Cutoffs per
calendar quarter: the 1/3 and 2/3 quantiles of (pred - thr) over every parent fill in the era's trade list
(reports/wick1m/trades_<tag>.parquet) with ts before the quarter's start; x1.0 while fewer than 60 such fills.
Applied through hsim.book's size_fn hook (4-sigma hold each minute from that minute's margin; the deeper rungs
from the margin at the parent's fill). Written from the spec only (the builder's cand_sizing.py was not read).

Variants (all but c2a are post hoc diagnostics, not trials):
  c2a       0.5 / 1.0 / 1.5 (the claim)
  inverse   1.5 / 1.0 / 0.5 (margin order reversed: an informative margin should make this lose)
  const     a constant multiplier equal to C2a's mean multiplier over the era's parent fills in the quarters where
            C2a is active (same extra size, no information)
  random    the buckets drawn at random (deterministic hash of minute and margin) with each quarter's C2a bucket shares
            among its parent fills (same size distribution, no information)
  top_only  1.0 / 1.0 / 1.5
  bot_only  0.5 / 1.0 / 1.0
usage: python scripts/ladder_v5/redteam2/c2a.py <variant> [configs comma-separated]
Writes reports/ladder_v5/redteam2/c2a/<variant>.json (gates.run output, not logged as a trial) and
<variant>_daily.parquet (candidate and incumbent daily returns per era and configuration) and <variant>_stats.csv
(hsim counters).
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LV5 = os.path.dirname(HERE)
sys.path.insert(0, LV5)
import gates  # noqa: E402  (before fsim: scripts/hunt has its own gates.py)
import fsim  # noqa: E402
import hsim  # noqa: E402

OUT = os.path.join(fsim.OUT, "redteam2", "c2a")
MULTS = {"c2a": (0.5, 1.0, 1.5), "inverse": (1.5, 1.0, 0.5), "top_only": (1.0, 1.0, 1.5), "bot_only": (0.5, 1.0, 1.0)}


def cutoffs(tag, min_n=60):
    """{quarter (Period): (lo, hi) or None} from the era's trade list; and the trade list with margins."""
    T = pd.read_parquet(os.path.join(fsim.ROOT, "reports", "wick1m", f"trades_{tag}.parquet"))
    T = T.assign(m=(T.pred - T.thr).astype(float)).sort_values("ts")
    lo_t, hi_t = (pd.Timestamp("2021-01-01"), pd.Timestamp("2024-01-01")) if tag == "early" else \
        (pd.Timestamp("2024-01-01"), pd.Timestamp("2026-12-31"))
    out = {}
    for q in pd.period_range(lo_t, hi_t, freq="Q"):
        prev = T.m[T.ts < q.start_time].to_numpy()
        out[q] = (float(np.quantile(prev, 1 / 3)), float(np.quantile(prev, 2 / 3)), len(prev)) \
            if len(prev) >= min_n else None
    return out, T


def bucket(m, c):
    if c is None:
        return 1
    return 0 if m < c[0] else (2 if m >= c[1] else 1)


def make_fn(tag, pan, variant):
    cut, T = cutoffs(tag)
    idx = pan[0]
    q_of = pd.PeriodIndex(idx, freq="Q")
    lo = np.full(len(idx), np.nan)
    hi = np.full(len(idx), np.nan)
    for q, c in cut.items():
        if c is None:
            continue
        msk = np.asarray(q_of == q)
        lo[msk], hi[msk] = c[0], c[1]
    if variant == "const":
        T["b"] = [bucket(m, cut.get(pd.Period(t, freq="Q"))) for m, t in zip(T.m, T.ts)]
        T["act"] = [cut.get(pd.Period(t, freq="Q")) is not None for t in T.ts]
        mm = np.array(MULTS["c2a"])
        mbar = {}
        for era, (tg, (a, b)) in fsim.ERAS.items():
            if tg != tag:
                continue
            w = T[(T.ts >= a) & (T.ts < pd.Timestamp(b) + pd.Timedelta(days=1)) & T.act]
            mbar[era] = float(mm[w.b.to_numpy()].mean()) if len(w) else 1.0
        # one constant per era, applied where C2a is active
        era_of = np.full(len(idx), "", dtype=object)
        for era, (tg, (a, b)) in fsim.ERAS.items():
            if tg == tag:
                era_of[(idx >= pd.Timestamp(a)) & (idx < pd.Timestamp(b) + pd.Timedelta(days=1))] = era
        cm = np.array([mbar.get(e, 1.0) for e in era_of])

        def f(m, i):
            return 1.0 if lo[i] != lo[i] else cm[i]
        f.info = {"mbar": mbar}
        return f
    if variant == "random":
        sh = {}
        for q, c in cut.items():
            w = T[(T.ts >= q.start_time) & (T.ts <= q.end_time)]
            if c is None or not len(w):
                continue
            b = np.array([bucket(m, c) for m in w.m])
            sh[q] = (float(np.mean(b == 0)), float(np.mean(b == 2)))
        s_lo = np.full(len(idx), np.nan)
        s_hi = np.full(len(idx), np.nan)
        for q, (a, b) in sh.items():
            msk = np.asarray(q_of == q)
            s_lo[msk], s_hi[msk] = a, 1.0 - b

        def f(m, i):
            if lo[i] != lo[i] or s_lo[i] != s_lo[i]:
                return 1.0
            u = (np.sin(i * 12.9898 + m * 78.233) * 43758.5453) % 1.0
            return 0.5 if u < s_lo[i] else (1.5 if u >= s_hi[i] else 1.0)
        f.info = {"shares": {str(q): v for q, v in sh.items()}}
        return f
    a0, a1, a2 = MULTS[variant]

    def f(m, i):
        x = lo[i]
        if x != x:
            return 1.0
        if m < x:
            return a0
        if m >= hi[i]:
            return a2
        return a1
    f.info = {}
    return f


def main(variant, configs):
    os.makedirs(OUT, exist_ok=True)
    fns = {}
    for tag in ("main", "early"):
        P, pan = gates.data(tag)
        fns[tag] = make_fn(tag, pan, variant)
    store, st_rows = {}, []

    def book_fn(P, era, pan=None, adv_=None, theta=0.5, C=250e3, today=False, cost_mult=1.0):
        tag = fsim.ERAS[era][0]
        d, out = hsim.book(P, era, theta=theta, C=C, size_fn=fns[tag], today=today, cost_mult=cost_mult, pan=pan,
                           adv=adv_)
        cfg = [k for k, v in gates.CONFIGS.items() if v == dict(theta=theta, C=C, today=today, cost_mult=cost_mult)][0]
        store[(cfg, era)] = d
        for name in ("minute", "instant"):
            Q, _, info, st = out[name]
            st_rows.append(dict(variant=variant, cfg=cfg, era=era, bound=name, bought=float(Q.fill.sum()),
                                n_fill=int((Q.fill > 0).sum()), maker_bp=info["maker_bp"], taker_bp=info["taker_bp"],
                                **st))
        return d

    t0 = time.time()
    res = gates.run(f"RT2_{variant}", book_fn, path="return", configs=tuple(configs), log=False)
    res["info"] = {k: v for k, v in fns["main"].info.items()} | {f"early_{k}": v for k, v in fns["early"].info.items()}
    json.dump(res, open(os.path.join(OUT, f"{variant}.json"), "w"), indent=1, default=float)
    rows = []
    for (cfg, era), d in store.items():
        inc = gates.incumbent_cached(era, cfg)
        rows.append(pd.DataFrame({"day": inc.index, "cfg": cfg, "era": era, "inc": inc.to_numpy(),
                                  "cand": d.reindex(inc.index, fill_value=0.0).to_numpy()}))
    pd.concat(rows).to_parquet(os.path.join(OUT, f"{variant}_daily.parquet"), index=False)
    pd.DataFrame(st_rows).to_csv(os.path.join(OUT, f"{variant}_stats.csv"), index=False)
    print(gates.summary(res))
    print(f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else "c2a"
    cf = sys.argv[2].split(",") if len(sys.argv) > 2 else ["S_0.5", "S_0.25", "base_0.5", "cap_1M"]
    main(v, cf)
