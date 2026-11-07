#!/usr/bin/env python3
"""Ladder v5, C7 (reports/ladder_v5/specs/sweep.md): is "the prints sharing a timestamp" one aggressive order?

Properties of the raw prints only (no outcomes, no markouts). Each Coinbase print is one match between a taker and a
resting maker order; `side` is the maker's side (buy = a seller hit a bid). If the prints sharing the timestamp of
the first print through our bid are one taker order, they are all on one maker side, their prices never rise in
trade-id order (one order walking down the book), and their trade ids are consecutive. Two orders merged by a shared
timestamp would show mixed sides or a price that rises again; one order split across timestamps would show the next
print, microseconds later, continuing down on the same side.
Runs on Actions through ladder-prints.yml (it downloads the raw trade artifacts):
  gh workflow run ladder-prints.yml --ref ladder/sweep -f run_id=<fetch run> -f era=<main|early>_grouping \
     -f script=scripts/ladder_v5/prints_grouping.py
Writes reports/ladder_v5/prints_grouping_<main|early>.csv (one row per parent) and prints a summary.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "reports", "ladder_v5")
sys.path.insert(0, HERE)
from prints import ticks  # noqa: E402


def mono(p):
    d = np.diff(p)
    return "flat" if not len(d) or np.all(d == 0) else "down" if np.all(d <= 0) else "up" if np.all(d >= 0) else "mixed"


def main(art, era):
    tag = era.split("_")[0]
    files = glob.glob(os.path.join(art, "**", "trades_*.parquet"), recursive=True)
    T = pd.concat([pd.read_parquet(f, columns=["window_id", "time", "trade_id", "price", "size", "side"])
                   for f in files])
    T = T.sort_values(["window_id", "time", "trade_id"])           # prints.py's order
    us = T.time.astype("datetime64[us]").astype("int64").to_numpy()
    print(f"{len(T):,} prints in {T.window_id.nunique():,} windows")
    print(f"timestamps with a non-zero sub-millisecond part: {np.mean(us % 1000 != 0):.1%} (microsecond resolution)")
    tid_order_ok = T.groupby("window_id").trade_id.apply(lambda s: bool(np.all(np.diff(s.to_numpy()) > 0)))
    print(f"windows where (time, trade id) order equals trade-id order: {tid_order_ok.mean():.2%}")
    wpath = os.path.join(ROOT, "reports", "wick_v4", "windows.csv") if tag == "main" else \
        os.path.join(OUT, "windows_early.csv")
    W = pd.read_csv(wpath, parse_dates=["start", "end"])
    alt = {(r.product.split("-")[0], r.start): r.window_id for r in W[W.kind == "alt"].itertuples()}
    by = {w: g for w, g in T.groupby("window_id")}
    P = pd.read_pickle(os.path.join(OUT, "frozen", f"pre_hunt_{tag}.pkl"))
    par = P[(P.k == 4.0) & P.filled]
    tk = ticks()
    rows, allg = [], []
    for r in par.itertuples():
        g = by.get(alt.get((r.coin, r.ts)))
        if g is None or not len(g):
            continue
        tick = tk.get(r.coin, np.nan)
        lvl = float(r.lvl)
        t = ((g.time - r.ts).dt.total_seconds()).to_numpy()
        px = g.price.to_numpy(np.float64)
        side = g.side.to_numpy()
        tid = g.trade_id.to_numpy()
        tu = g.time.astype("datetime64[us]").astype("int64").to_numpy()
        m0 = t < 60
        hit = np.nonzero(m0 & (px <= lvl - tick * (1 - 1e-9)))[0]
        if not len(hit):
            continue
        i4 = hit[0]
        ft = tu[i4]
        G = np.nonzero(tu == ft)[0]
        o = G[np.argsort(tid[G])]
        before, after = np.nonzero(tu < ft)[0], np.nonzero(tu > ft)[0]
        nxt = after[0] if len(after) else None
        rec = dict(ts=r.ts, coin=r.coin, n=len(G), sides="".join(sorted(set(side[G]))),
                   price_path=mono(px[o]), contiguous_ids=bool(tid[o][-1] - tid[o][0] + 1 == len(G)),
                   gap_prev_us=float(ft - tu[before[-1]]) if len(before) else np.nan,
                   gap_next_us=float(tu[nxt] - ft) if nxt is not None else np.nan,
                   next_same_side_lower=bool(nxt is not None and side[nxt] == "buy" and px[nxt] <= px[G].min()))
        rows.append(rec)
        # every same-timestamp group in the fill minute that printed at or below our price (sorted by time then
        # trade id, so each group is a contiguous slice in trade-id order)
        sub = np.nonzero(m0 & (px <= lvl + 0.5 * tick))[0]
        uq, st, cnt = np.unique(tu, return_index=True, return_counts=True)
        for p_ in np.searchsorted(uq, np.unique(tu[sub])):
            a, n_ = int(st[p_]), int(cnt[p_])
            allg.append((n_, len(set(side[a:a + n_])) > 1, mono(px[a:a + n_]), bool(tid[a + n_ - 1] - tid[a] + 1 == n_)))
    D = pd.DataFrame(rows)
    A = pd.DataFrame(allg, columns=["n", "mixed_sides", "price_path", "contiguous_ids"])
    D.to_csv(os.path.join(OUT, f"prints_grouping_{tag}.csv"), index=False)
    multi = D[D.n > 1]
    print(f"\nfirst order through our bid ({len(D)} parents; {len(multi)} with more than one print at that time)")
    print(f"  maker side: {D.sides.value_counts().to_dict()}")
    print(f"  price path in trade-id order (multi-print groups): {multi.price_path.value_counts().to_dict()}")
    print(f"  consecutive trade ids: {D.contiguous_ids.mean():.2%}")
    print(f"  microseconds to the next print: median {D.gap_next_us.median():.0f}; share < 1 ms "
          f"{(D.gap_next_us < 1000).mean():.1%}; share < 100 us {(D.gap_next_us < 100).mean():.1%}")
    print(f"  next print within 1 ms, same side, at or below the group's low (a possible split order): "
          f"{(D.next_same_side_lower & (D.gap_next_us < 1000)).mean():.1%}")
    am = A[A.n > 1]
    print(f"\nall same-timestamp groups at or below our price in the fill minute: {len(A):,} ({len(am):,} multi-print)")
    print(f"  mixed maker sides: {A.mixed_sides.mean():.3%}; consecutive trade ids: {A.contiguous_ids.mean():.2%}")
    print(f"  price path (multi-print): {am.price_path.value_counts(normalize=True).round(4).to_dict()}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "main")
