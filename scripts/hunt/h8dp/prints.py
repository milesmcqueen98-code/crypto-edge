#!/usr/bin/env python3
"""H8 (depeg bids): trade prints -> per-minute through-volumes at every rung level (reports/hunt/h8dp/SPEC.md).

  python scripts/hunt/h8dp/prints.py win  <PRODUCT> <shard> <n_shards>   candidate windows via common.TradeFetcher
  python scripts/hunt/h8dp/prints.py full <PRODUCT>                      every print via the Exchange trade-id cursor
  python scripts/hunt/h8dp/prints.py local <PRODUCT>                     from data/hunt/h8dp/trades_all/<PRODUCT>.parquet

Candidate minutes (win): the 1-minute candle's low is at least one tick below the shallowest rung (par x (1 - 10 bp)).
They are merged into windows when <= 2 minutes apart and padded by one minute before and two after.
Per minute with prints: n, open, high, low, vol (coin), vb_<bp> = coin volume of prints at least one tick BELOW the
rung level for each depth (through-volume that can fill a resting bid there), va_tp = coin volume at least one tick
ABOVE the take-profit level (par - 5 bp), ids_missing (trade-id gaps inside fetched windows).
Outputs are split at the hold-out start (gates.HOLD0) into tagg/<PRODUCT>_<part>_dev.parquet and ..._hold.parquet so
nothing on HOLD days is read before the freeze. Logs print request counts and timings only.
"""
import glob
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
sys.path.insert(0, HERE)
import levels as LV  # noqa: E402

OUT = os.path.join(ROOT, "data", "hunt", "h8dp", "tagg")
HOLD0 = pd.Timestamp("2026-06-01")


def aggregate(d, pid, L):
    """d: prints (time, price, size); L: rung levels per candle minute (levels.levels_for). Per-minute table."""
    tick = LV.TICK[pid]
    d = d.sort_values(["time", "trade_id"]) if "trade_id" in d else d.sort_values("time")
    m = d["time"].dt.floor("min")
    Lm = L.reindex(L.index.union(pd.DatetimeIndex(m.unique()))).ffill().reindex(m.to_numpy()).to_numpy()
    px, sz = d["price"].to_numpy(float), d["size"].to_numpy(float)
    g = pd.DataFrame({"m": m.to_numpy(), "px": px, "sz": sz})
    cols = {}
    for j, dep in enumerate(LV.DEPTHS):
        cols[f"vb_{int(round(dep * 1e4))}"] = np.where(px <= Lm[:, j] - 0.5 * tick, sz, 0.0)
    cols["va_tp"] = np.where(px >= Lm[:, len(LV.DEPTHS)] + 0.5 * tick, sz, 0.0)
    for k, v in cols.items():
        g[k] = v
    gb = g.groupby("m", sort=True)
    A = pd.DataFrame({"n": gb.size(), "open": gb.px.first(), "high": gb.px.max(), "low": gb.px.min(),
                      "vol": gb.sz.sum()})
    for k in cols:
        A[k] = gb[k].sum()
    A.index.name = "ts"
    return A


def save(A, pid, part):
    os.makedirs(OUT, exist_ok=True)
    A = A.reset_index()
    A[A.ts < HOLD0].to_parquet(os.path.join(OUT, f"{pid}_{part}_dev.parquet"), index=False, compression="zstd")
    A[A.ts >= HOLD0].to_parquet(os.path.join(OUT, f"{pid}_{part}_hold.parquet"), index=False, compression="zstd")


def windows(pid, C, L):
    tick = LV.TICK[pid]
    cand = np.nonzero(C["low"].to_numpy() <= L[LV.DEPTHS[0]].to_numpy() - 0.5 * tick)[0]
    ts = C.index[cand]
    if len(ts) == 0:
        return []
    gaps = np.diff(ts.values).astype("timedelta64[m]").astype(int)
    brk = np.r_[0, np.nonzero(gaps > 2)[0] + 1, len(ts)]
    return [(ts[a] - pd.Timedelta(minutes=1), ts[b - 1] + pd.Timedelta(minutes=2)) for a, b in zip(brk[:-1], brk[1:])]


def run_win(pid, shard, n):
    import common
    shard, n = int(shard), int(n)
    C = LV.load_candles(pid)
    L = LV.levels_for(pid, C)
    W = [w for i, w in enumerate(windows(pid, C, L)) if i % n == shard]
    tf = common.TradeFetcher()
    parts, miss, t0 = [], [], time.time()
    for k, (a, b) in enumerate(W):
        try:
            d = tf.window(pid, a, b)
        except Exception as err:  # noqa: BLE001
            print("FAILED", pid, repr(err)[:200], flush=True)
            miss.append((a, b, -1))
            continue
        if len(d):
            ids = d.trade_id.astype(np.int64)
            miss.append((a, b, int(ids.max() - ids.min() + 1 - ids.nunique())))
            parts.append(aggregate(d, pid, L.loc[a - pd.Timedelta(minutes=5):b]))
        if k % 200 == 0:                                   # progress only: no HOLD counts are printed before the freeze
            print(f"{pid} shard {shard}: {tf.n_req} requests, {time.time() - t0:.0f}s", flush=True)
    A = pd.concat(parts) if parts else pd.DataFrame()
    A = A[~A.index.duplicated()].sort_index()
    save(A, pid, f"w{shard}")
    M = pd.DataFrame(miss, columns=["start", "end", "ids_missing"])
    M[M.start < HOLD0].to_parquet(os.path.join(OUT, f"{pid}_w{shard}_win_dev.parquet"), index=False)
    M[M.start >= HOLD0].to_parquet(os.path.join(OUT, f"{pid}_w{shard}_win_hold.parquet"), index=False)
    print(f"{pid} shard {shard}: done, {tf.n_req} requests, {time.time() - t0:.0f}s", flush=True)


def run_refetch(pid, shard, n):
    """Re-fetch, with the fixed common.TradeFetcher (paging fix 06b7052), every window whose first fetch had trade-id
    gaps (ids_missing > 0: prints lost by the old paging). Writes parts r<shard>; sim.prints_for prefers them."""
    import common
    shard, n = int(shard), int(n)
    W = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(OUT, f"{pid}_w*_win_*.parquet")))])
    W = W[W.ids_missing > 0].sort_values("start").reset_index(drop=True)
    W = W[W.index % n == shard]
    C = LV.load_candles(pid)
    L = LV.levels_for(pid, C)
    del C
    tf = common.TradeFetcher()
    parts, miss, t0 = [], [], time.time()
    for k, w in enumerate(W.itertuples()):
        a, b = w.start, w.end
        try:
            d = tf.window(pid, a, b)
        except Exception as err:  # noqa: BLE001
            print("FAILED", pid, repr(err)[:200], flush=True)
            miss.append((a, b, -1))
            continue
        if len(d):
            ids = d.trade_id.astype(np.int64)
            miss.append((a, b, int(ids.max() - ids.min() + 1 - ids.nunique())))
            parts.append(aggregate(d, pid, L.loc[a - pd.Timedelta(minutes=5):b]))
        else:
            miss.append((a, b, 0))
        if k % 50 == 0:
            print(f"{pid} refetch shard {shard}: {k}/{len(W)}, {tf.n_req} requests, {time.time() - t0:.0f}s", flush=True)
    A = pd.concat(parts) if parts else pd.DataFrame()
    A = A[~A.index.duplicated()].sort_index()
    save(A, pid, f"r{shard}")
    M = pd.DataFrame(miss, columns=["start", "end", "ids_missing"])
    M[M.start < HOLD0].to_parquet(os.path.join(OUT, f"{pid}_r{shard}_win_dev.parquet"), index=False)
    M[M.start >= HOLD0].to_parquet(os.path.join(OUT, f"{pid}_r{shard}_win_hold.parquet"), index=False)
    print(f"{pid} refetch shard {shard}: done, {len(W)} windows, ids still missing {int(M.ids_missing.clip(lower=0).sum())}, "
          f"{tf.n_req} requests, {time.time() - t0:.0f}s", flush=True)


def run_full(pid):
    import fetch
    t0, rows, cur = time.time(), [], None
    while True:
        js = fetch.get(f"/products/{pid}/trades", {"limit": 1000, **({"after": cur} if cur else {})})
        if not js:
            break
        rows += [(int(t["trade_id"]), t["time"], float(t["price"]), float(t["size"])) for t in js]
        cur = min(int(t["trade_id"]) for t in js)
        if cur <= 1 or len(js) < 1000:
            break
        if fetch.N_REQ[0] % 500 == 0:
            print(pid, fetch.N_REQ[0], "requests", f"{time.time() - t0:.0f}s", flush=True)
    d = pd.DataFrame(rows, columns=["trade_id", "time", "price", "size"]).drop_duplicates("trade_id")
    d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.tz_convert(None)
    ids = d.trade_id.to_numpy()
    print(pid, "ids span", int(ids.max() - ids.min() + 1), "unique", len(ids), flush=True)
    C = LV.load_candles(pid)
    L = LV.levels_for(pid, C)
    save(aggregate(d, pid, L), pid, "full")
    print(f"{pid}: done, {fetch.N_REQ[0]} requests, {time.time() - t0:.0f}s", flush=True)


def run_local(pid):
    d = pd.read_parquet(os.path.join(ROOT, "data", "hunt", "h8dp", "trades_all", f"{pid}.parquet"))
    C = LV.load_candles(pid)
    L = LV.levels_for(pid, C)
    save(aggregate(d, pid, L), pid, "full")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "win":
        run_win(*sys.argv[2:5])
    elif mode == "full":
        for p in sys.argv[2:]:
            run_full(p)
    elif mode == "refetch":
        run_refetch(*sys.argv[2:5])
    elif mode == "local":
        for p in sys.argv[2:]:
            run_local(p)
