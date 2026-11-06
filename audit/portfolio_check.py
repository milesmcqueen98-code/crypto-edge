#!/usr/bin/env python3
"""Audit E10: independent recomputation of the headline portfolio statistics from the trade files, and checks of
the position-cap logic in scripts/wick_futures.portfolio."""
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = pd.read_parquet(os.path.join(ROOT, "reports", "wick_final_trades.parquet"))
tr = T[T.strategy == "rule + AI, 5-seed average"].copy()


def stats(tr, start, end):
    days = pd.date_range(start, end, freq="D")
    pnl = tr.groupby(tr.exit_ts.dt.normalize()).net_bp.sum() * 0.25 / 1e4
    d = pnl.reindex(days, fill_value=0.0)
    assert abs(pnl.sum() - d.sum()) < 1e-12, "P&L outside the day range"
    return dict(days=len(d), sharpe=d.mean() / d.std(ddof=1) * np.sqrt(365), ann=d.mean() * 365,
                maxdd=(d.cumsum() - d.cumsum().cummax()).min(), zero_day_share=(d == 0).mean())


def cap_fifo(tr, cap):
    """Independent cap: walk minute by minute; a trade is taken if fewer than `cap` taken trades are open at its
    entry minute (a trade is open on [ts, exit_ts])."""
    tr = tr.sort_values("ts", kind="stable").reset_index(drop=True)
    taken, open_exits = [], []
    for r in tr.itertuples():
        open_exits = [e for e in open_exits if e >= r.ts]        # still open during the entry minute
        if len(open_exits) < cap:
            taken.append(r.Index)
            open_exits.append(r.exit_ts)
    return tr.loc[taken]


def cap_code(tr, cap):                                           # copy of wick_futures.portfolio's cap
    tr = tr.sort_values("ts").reset_index(drop=True)
    keep, open_ = [], []
    for r in tr.itertuples():
        open_ = [e for e in open_ if e > r.ts]
        if len(open_) < cap:
            keep.append(r.Index)
            open_.append(r.exit_ts)
    return tr.loc[keep]


def max_conc(tr):
    ev = pd.concat([pd.Series(1, index=tr.ts), pd.Series(-1, index=tr.exit_ts + pd.Timedelta(minutes=1))]).sort_index()
    ev = ev.groupby(level=0).sum()
    return int(ev.cumsum().max())


print("uncapped:", {k: round(v, 3) for k, v in stats(tr, "2025-01-01", "2026-11-05").items()},
      "max concurrent (counting the exit minute):", max_conc(tr))
c6 = cap_code(tr, 6)
print("cap 6 as coded:", len(c6), {k: round(v, 3) for k, v in stats(c6, "2025-01-01", "2026-11-05").items()},
      "max concurrent incl. exit minute:", max_conc(c6))
c6b = cap_fifo(tr, 6)
print("cap 6, strict (exit minute still occupies the slot):", len(c6b),
      {k: round(v, 3) for k, v in stats(c6b, "2025-01-01", "2026-11-05").items()}, "max concurrent:", max_conc(c6b))
# tie order sensitivity: sort_values default is not stable; shuffle ties
rng = np.random.default_rng(0)
sh = []
for i in range(20):
    x = tr.sample(frac=1.0, random_state=i)
    x = x.sort_values("ts", kind="stable")
    sh.append(stats(cap_code(x, 6), "2025-01-01", "2026-11-05")["sharpe"])
print(f"cap 6 Sharpe over 20 random tie orders: {np.min(sh):.3f} .. {np.max(sh):.3f}")
# same-minute entries on several coins (correlated fills)
g = tr.groupby("ts").size()
print(f"entry minutes with >=3 coins filling at once: {(g >= 3).sum()} ({g[g >= 3].sum()} trades of {len(tr)})")
# P&L concentration
d = (tr.groupby(tr.exit_ts.dt.normalize()).net_bp.sum() * 0.25 / 1e4).sort_values(ascending=False)
print(f"best 10 days = {d.head(10).sum() / d.sum():.1%} of uncapped P&L: {[(str(k.date()), round(v, 3)) for k, v in d.head(5).items()]}")
sh = np.array(sh)
print(f"cap 6 Sharpe over random tie orders: mean {sh.mean():.3f}, median {np.median(sh):.3f}; headline as coded 3.220")
sh2 = []
for i in range(20):
    x = tr.sample(frac=1.0, random_state=100 + i).sort_values("ts", kind="stable")
    sh2.append(stats(cap_fifo(x, 6), "2025-01-01", "2026-11-05")["sharpe"])
print(f"strict cap 6 (exit minute occupies slot), random tie orders: mean {np.mean(sh2):.3f}, range {np.min(sh2):.3f}..{np.max(sh2):.3f}")
