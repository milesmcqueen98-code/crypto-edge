#!/usr/bin/env python3
"""Signal lab 2: a QA diagnostic of the fetched prints against the repo's minute candles, minute by minute, over every
minute of the merged F6 windows (all of them before their candidates' minutes q). Runs on the runner beside the fetch
artifacts; writes counts only (reports/signal_lab/prints/qa_diag.json).

Per minute: print base volume (sum of size) against candle volume (data/minute_early before 2024, data/minute after;
rows with volume > 0, as the simulator loads them). Categories: match (relative difference <= 1e-5; candle volume is
stored as float32), candle gap (prints but no candle row), print gap (a candle row but no print), mismatch (both, not
equal), with the mismatches that an adjacent minute's opposite difference offsets counted apart (trades bucketed into
the neighbouring minute). Also the size of every place where time decreases along trade id, and whether any such
inversion straddles a window edge (the fetcher's stop rule assumes ids rise with time); and gaps in trade id inside a
window (Coinbase numbers each product's trades 1, 2, 3, ..., so a gap is a print the API did not return).
usage: python scripts/signal_lab/prints_diag.py <art_dir> [<out_dir>]
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import prints_features as PFE  # noqa: E402

NS_MIN = 60 * 10 ** 9
SPLIT = pd.Timestamp("2024-01-01")
TOL = 1e-5


def candles(coin):
    parts = []
    for src, early in (("minute_early", True), ("minute", False)):
        p = os.path.join(ROOT, "data", src, f"{coin}.parquet")
        if os.path.exists(p):
            m = pd.read_parquet(p, columns=["ts", "volume"]).drop_duplicates("ts")
            parts.append(m[(m.ts < SPLIT) if early else (m.ts >= SPLIT)])
    m = pd.concat(parts).sort_values("ts")
    m = m[m.volume > 0]
    return m.ts.to_numpy().astype("datetime64[ns]").view(np.int64) // NS_MIN, m.volume.to_numpy().astype(np.float64)


def main(art_dir, out_dir=os.path.join(ROOT, "reports", "signal_lab", "prints")):
    files = sorted(glob.glob(os.path.join(art_dir, "**", "prints_*.parquet"), recursive=True))
    W = pd.read_csv(os.path.join(ROOT, "reports", "signal_lab", "prints", "windows.csv"), parse_dates=["start", "end"])
    w_lo = W.start.to_numpy().astype("datetime64[ns]").view(np.int64)
    w_hi = W.end.to_numpy().astype("datetime64[ns]").view(np.int64)
    rows, inv, id_gaps = [], [], []
    for product, g in W.groupby("product"):
        coin = product[:-4]
        raw, _ = PFE.load_coin(files, product)
        if raw is None:
            print(f"{coin}: no prints", flush=True)
            continue
        o = np.argsort(raw["trade_id"], kind="stable")
        t, size, wid = raw["t"][o], raw["size"][o], raw["window_id"][o].astype(np.int64)
        tid = raw["trade_id"][o]
        del raw
        # trade-id gaps inside a window (ids run 1, 2, 3, ... per product, so a gap is a print the API did not return)
        same_w = wid[1:] == wid[:-1]
        step = np.diff(tid)[same_w]
        gyear = pd.to_datetime(t[1:][same_w][step > 1]).year.to_numpy()
        idg = dict(coin=coin, pairs=int(same_w.sum()), gaps=int((step > 1).sum()),
                   missing_ids=int((step[step > 1] - 1).sum()), repeated_ids=int((step == 0).sum()),
                   windows_with_gap=int(len(np.unique(wid[1:][same_w][step > 1]))),
                   gaps_by_year={int(y): int(n) for y, n in zip(*np.unique(gyear, return_counts=True))})
        id_gaps.append(idg)
        # time inversions along trade id
        d = np.diff(t)
        k = np.flatnonzero(d < 0)
        for i in k:
            hi_t, lo_t = t[i], t[i + 1]
            edges = (w_lo[wid[i]], w_hi[wid[i]], w_lo[wid[i + 1]], w_hi[wid[i + 1]])
            straddle = any(lo_t < e <= hi_t for e in edges)
            inv.append(dict(coin=coin, ms=float(-d[i] / 1e6), straddle=bool(straddle),
                            same_second=bool(hi_t // 10 ** 9 == lo_t // 10 ** 9),
                            same_minute=bool(hi_t // NS_MIN == lo_t // NS_MIN)))
        # minute volumes
        pm = t // NS_MIN
        oo = np.argsort(pm, kind="stable")
        pm_s, sz_s = pm[oo], size[oo]
        u, first = np.unique(pm_s, return_index=True)
        pv_u = np.add.reduceat(sz_s, first) if len(first) else np.zeros(0)
        mins = np.concatenate([np.arange(a // NS_MIN, b // NS_MIN) for a, b in
                               zip(g.start.to_numpy().astype("datetime64[ns]").view(np.int64),
                                   g.end.to_numpy().astype("datetime64[ns]").view(np.int64))])
        cm, cv_all = candles(coin)
        j = np.searchsorted(u, mins)
        pv = np.where((j < len(u)) & (u[np.clip(j, 0, len(u) - 1)] == mins), pv_u[np.clip(j, 0, len(u) - 1)], 0.0)
        j = np.searchsorted(cm, mins)
        hit = (j < len(cm)) & (cm[np.clip(j, 0, len(cm) - 1)] == mins)
        cv = np.where(hit, cv_all[np.clip(j, 0, len(cm) - 1)], 0.0)
        diff = pv - cv
        scale = np.maximum(np.maximum(pv, cv), 1e-12)
        match = np.abs(diff) <= TOL * scale
        both = (pv > 0) & (cv > 0)
        mism = both & ~match
        # offset by a neighbour: the pair's summed difference is ~0 (minutes are consecutive inside a window)
        nxt = np.r_[diff[1:], np.nan]
        prv = np.r_[np.nan, diff[:-1]]
        contig_n = np.r_[mins[1:] == mins[:-1] + 1, False]
        contig_p = np.r_[False, mins[1:] == mins[:-1] + 1]
        pair_scale = np.maximum(scale, 1e-12)
        off_n = contig_n & (np.abs(diff + nxt) <= 1e-4 * (pair_scale + np.abs(np.nan_to_num(nxt))))
        off_p = contig_p & (np.abs(diff + prv) <= 1e-4 * (pair_scale + np.abs(np.nan_to_num(prv))))
        era = np.where(mins * NS_MIN < SPLIT.value, "early", "main")
        yr = pd.to_datetime(mins * NS_MIN).year.to_numpy()
        rows.append(pd.DataFrame(dict(coin=coin, era=era, year=yr, pv=pv, cv=cv, match=match & (pv + cv > 0),
                                      no_volume=(pv == 0) & (cv == 0), candle_gap=(pv > 0) & (cv == 0),
                                      print_gap=(pv == 0) & (cv > 0), mism=mism, mism_offset=mism & (off_n | off_p),
                                      pos=pv > cv, neg=pv < cv)))
        print(f"{coin}: {len(mins)} minutes, {int(mism.sum())} mismatched, {len(k)} inversions", flush=True)
    R = pd.concat(rows, ignore_index=True)
    out = {}
    for key, g in [("all", R)] + [(e, g) for e, g in R.groupby("era")] + [(str(y), g) for y, g in R.groupby("year")]:
        n = len(g)
        m = g[g.mism]
        out[key] = dict(
            minutes=int(n), match=int(g.match.sum()), no_volume=int(g["no_volume"].sum()), candle_gap=int(g.candle_gap.sum()),
            print_gap=int(g.print_gap.sum()), mismatch=int(g.mism.sum()), mismatch_offset_by_neighbour=int(g.mism_offset.sum()),
            mismatch_prints_above=int((g.mism & g.pos).sum()), mismatch_prints_below=int((g.mism & g.neg).sum()),
            print_vol_in_candle_gaps_share=float(g.pv[g.candle_gap].sum() / g.pv.sum()),
            candle_vol_in_print_gaps_share=float(g.cv[g.print_gap].sum() / g.cv.sum()),
            net_vol_ratio=float(g.pv.sum() / g.cv.sum()),
            net_vol_ratio_matched_rows_only=float(g.pv[g.cv > 0].sum() / g.cv[g.cv > 0].sum()),
            abs_diff_share_unexplained=float(np.abs(m.pv - m.cv)[~m.mism_offset].sum() / g.cv.sum()) if len(m) else 0.0)
    I = pd.DataFrame(inv)
    out["inversions"] = dict(n=int(len(I)), straddle_window_edge=int(I.straddle.sum()) if len(I) else 0,
                             same_second=int(I.same_second.sum()) if len(I) else 0,
                             same_minute=int(I.same_minute.sum()) if len(I) else 0,
                             ms_quantiles=[float(x) for x in np.quantile(I.ms, [0.5, 0.9, 0.99, 1.0])] if len(I) else [])
    G = pd.DataFrame(id_gaps)
    by_year = {}
    for d_ in id_gaps:
        for y, n_ in d_["gaps_by_year"].items():
            by_year[y] = by_year.get(y, 0) + n_
    out["trade_id_gaps"] = dict(consecutive_pairs=int(G.pairs.sum()), gaps=int(G.gaps.sum()),
                                missing_ids=int(G.missing_ids.sum()), repeated_ids=int(G.repeated_ids.sum()),
                                windows_with_gap=int(G.windows_with_gap.sum()), by_year=by_year,
                                by_coin={r.coin: [int(r.gaps), int(r.missing_ids), int(r.windows_with_gap)]
                                         for r in G.itertuples()})
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "qa_diag.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    for k_, v in out.items():
        print(k_, v, flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
