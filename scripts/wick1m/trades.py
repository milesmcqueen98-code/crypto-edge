#!/usr/bin/env python3
"""R2-08 trade lists for the $1M round (reports/wick1m_prereg.md), from the wick lab's own pipeline (scripts/lab,
imported, not modified): levels, features, walk-forward AI, bid mask, sequential per-coin books.

Writes reports/wick1m/trades_<tag>.parquet with every AI-approved trade (no slot cap) plus a 'bot' flag for the trades
the bot's portfolio rule keeps (6 slots x $2,500, gross $15,000 on $10K), and the ladder inputs (fair value, sigma).

  python scripts/wick1m/trades.py main            2024-26 data (selection + check periods), 17 coins
  LAB_ERA=early python scripts/wick1m/trades.py early     2021-23 data (fresh era), coins that existed
Set QUIET=1 for the bot's quiet window (no new bids 16:55-18:05 ET).
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "lab"))
import core  # noqa: E402
import run as RUN  # noqa: E402
import variants as VV  # noqa: E402

NAME = "R2-08 C29+A11"


def build(coins=None):
    allv = {v["name"]: v for v in VV.VARIANTS + VV.ROUND1B + VV.make_round2()}
    v = allv[NAME]
    parts = []
    exp = RUN.expand(v)
    need = sorted({c for ls_d, _, _ in exp for c in (coins or ls_d["coins"])})
    data = core.Data(need)
    state, lab_cache = {}, {}
    for ls_d, ex_d, ai_d in exp:
        ls_d = dict(ls_d)
        if coins:
            ls_d["coins"] = tuple(coins)
        ls = core.LevelSet(data, **ls_d)
        X = ls.features()
        ex, keep, pred, thr = RUN.build_spec(ls, X, ex_d, ai_d, lab_cache, state)
        if os.environ.get("QUIET") == "1":
            core.QUIET = (1015, 1085)
        tr = RUN.attach_thr(core.simulate(ls, ex, keep=keep, pred=pred), ls, X, thr)
        core.QUIET = None
        if len(tr):
            tr["k"] = ls.k
            tr["tp_log"] = ex.theta * ls.k * tr.sig            # take-profit distance from entry (log)
            tr["fair_log"] = np.log(tr.px) + ls.k * tr.sig     # fair value at the fill (log)
            parts.append(tr)
    tr = pd.concat(parts, ignore_index=True).sort_values(["ts", "coin"]).reset_index(drop=True)
    _, kept = RUN.run_portfolio(v, tr, data)
    key = set(zip(kept.ts, kept.coin))
    tr["bot"] = [(t, c) in key for t, c in zip(tr.ts, tr.coin)]
    return tr


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "main"
    t0 = time.time()
    tr = build()
    os.makedirs(os.path.join(ROOT, "reports", "wick1m"), exist_ok=True)
    q = "_quiet" if os.environ.get("QUIET") == "1" else ""
    out = os.path.join(ROOT, "reports", "wick1m", f"trades_{tag}{q}.parquet")
    tr.to_parquet(out, index=False)
    print(f"{len(tr)} AI-approved trades ({tr.bot.sum()} kept by the bot's rule), {tr.coin.nunique()} coins, "
          f"{tr.ts.min()} .. {tr.ts.max()}  ({time.time() - t0:.0f}s) -> {out}")


if __name__ == "__main__":
    main()
