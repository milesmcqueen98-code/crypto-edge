#!/usr/bin/env python3
"""H10 (XQ): verify candidate fills on trade prints (common.TradeFetcher; delisted pairs fall back to the Exchange
trade-id cursor). Input data/hunt/h10xq/prints/req_<tag>.parquet: pair, k, ts (fill minute), lvl, tick, tp, tp_ts.
For each (pair, ts) the prints of [ts, ts + 16 min) are fetched once; for each request row:
  confirmed  a print at <= lvl - tick inside the fill minute, and the minute's first print above lvl (so a post-only
             bid resting at lvl was not crossed at the open)
  thru_q     quote volume of prints strictly below lvl, from the first such print, while the price stays below lvl
             (stops at the first print >= lvl; prints AT the level are ignored: queue position unknown)
  tp_ok      if tp_ts is set: a print >= tp + tick inside [tp_ts, tp_ts + 1 min)
  hs_bp      median |price change| / 2 over consecutive prints whose maker side flips, in bp (half-spread proxy)
Writes data/hunt/h10xq/prints/res_<tag>_<shard>.parquet (no P&L).
usage: python scripts/hunt/h10xq/prints.py <tag> <shard> <nshards>"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

DIR = os.path.join(ROOT, "data", "hunt", "h10xq", "prints")
SCAN = 16


def check(tr, ts, lvl, tick, tp, tp_ts, tr_tp):
    m0 = tr[(tr.time >= ts) & (tr.time < ts + pd.Timedelta(minutes=1))]
    out = dict(n_min=len(m0), confirmed=False, thru_q=0.0, first_px=np.nan, min_px=np.nan, tp_ok=np.nan)
    if len(m0):
        out["first_px"] = float(m0.price.iloc[0])
        out["min_px"] = float(m0.price.min())
        below = m0.price <= lvl - 0.5 * tick
        out["confirmed"] = bool(below.any()) and out["first_px"] > lvl + 0.5 * tick
        if below.any():
            i0 = int(np.flatnonzero(below.to_numpy())[0])
            seq = tr[tr.time >= m0.time.iloc[i0]]
            seq = seq[seq.time < ts + pd.Timedelta(minutes=SCAN)]
            px = seq.price.to_numpy()
            stop = np.flatnonzero(px >= lvl - 0.5 * tick)
            seg = seq.iloc[: stop[0]] if len(stop) else seq
            seg = seg[seg.price < lvl - 0.5 * tick]
            out["thru_q"] = float((seg.price * seg["size"]).sum())
    if pd.notna(tp_ts) and tr_tp is not None:
        w = tr_tp[(tr_tp.time >= tp_ts) & (tr_tp.time < tp_ts + pd.Timedelta(minutes=1))]
        out["tp_ok"] = float(bool((w.price >= tp + 0.5 * tick).any())) if len(w) else 0.0
    return out


def half_spread_bp(tr):
    if len(tr) < 3:
        return np.nan
    s = tr.side.to_numpy()
    p = tr.price.to_numpy()
    f = s[1:] != s[:-1]
    d = np.abs(np.diff(p))[f]
    d = d[d > 0]
    return float(np.median(d) / 2 / np.median(p) * 1e4) if len(d) else np.nan


def main(tag, shard, nsh):
    R = pd.read_parquet(os.path.join(DIR, f"req_{tag}.parquet"))
    keys = R[["pair", "ts"]].drop_duplicates().sort_values(["pair", "ts"]).reset_index(drop=True)
    keys = keys.iloc[shard::nsh]
    R = R.merge(keys, on=["pair", "ts"])
    print(f"{tag} shard {shard}/{nsh}: {len(keys)} windows, {len(R)} rows, {R.pair.nunique()} pairs", flush=True)
    F = common.TradeFetcher(rate=8.0)
    out, t0, nfail = [], time.time(), 0
    for n, ((pair, ts), g) in enumerate(R.groupby(["pair", "ts"], sort=True)):
        try:
            tr = F.window(pair, ts, ts + pd.Timedelta(minutes=SCAN))
        except Exception as err:  # noqa: BLE001
            nfail += 1
            for r in g.itertuples():
                out.append(dict(pair=pair, ts=ts, k=r.k, fetched=False, err=type(err).__name__))
            continue
        tp_cache = {}
        hs = half_spread_bp(tr)
        for r in g.itertuples():
            tr_tp = None
            if pd.notna(r.tp_ts):
                if r.tp_ts < ts + pd.Timedelta(minutes=SCAN):
                    tr_tp = tr
                else:
                    if r.tp_ts not in tp_cache:
                        try:
                            tp_cache[r.tp_ts] = F.window(pair, r.tp_ts, r.tp_ts + pd.Timedelta(minutes=1))
                        except Exception:  # noqa: BLE001
                            tp_cache[r.tp_ts] = None
                    tr_tp = tp_cache[r.tp_ts]
            o = check(tr, ts, r.lvl, r.tick, r.tp, r.tp_ts, tr_tp)
            o.update(pair=pair, ts=ts, k=r.k, fetched=True, n_win=len(tr), hs_bp=hs)
            out.append(o)
        if n % 200 == 0:
            print(n, pair, ts, len(tr), f"req {F.n_req} fail {nfail} {time.time() - t0:.0f}s", flush=True)
    os.makedirs(DIR, exist_ok=True)
    pd.DataFrame(out).to_parquet(os.path.join(DIR, f"res_{tag}_{shard}.parquet"), index=False)
    print("done", len(out), "rows", F.n_req, "requests", nfail, "failed windows", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
