#!/usr/bin/env python3
"""Signal lab 2 (reports/signal_lab/prospective_prereg.md, "Features (F6; fixed now)" and deviation 1): the F6 print
features of every candidate of both eras, from the artifacts of the fetch runs (scripts/signal_lab/prints_fetch.py).
Runs on GitHub Actions; raw prints stay on the runner and only derived rows leave it.

usage: python scripts/signal_lab/prints_features.py <art_dir> [<out_dir>]
  art_dir: art/<run_id>/<artifact>/prints_<shard>.parquet and status_<shard>.csv of the fetch runs
Writes <out_dir>/f6_main.parquet and f6_early.parquet (schema below), qa_cand.parquet (QA side table: window,
status, base volume, first and last print price, taker-sell count) and qa_runner.json (print-level checks).

Definitions (binding: the prereg and its deviation 1)
- q = the candidate minute start (UTC, naive). Only prints stamped strictly before q are used: the 30-minute window
  [q - 30 min, q) and the 5-minute window [q - 5 min, q).
- Taker sell = a print whose maker side is BUY (a resting bid was hit). USD = price x size. Prints are de-duplicated
  by trade_id and ordered by (time, trade_id).
- sweep = the largest taker-sell USD summed within one calendar second (time floored to the second) in [q - 30 min, q).
  q - 30 min and q are whole seconds, so no second straddles an edge of the window.
- Big-print threshold: the 99th percentile (numpy.quantile, linear interpolation) of print USD over the coin's
  fetched prints stamped in [w - 30 days, w), w = q - 30 min (the start of the candidate's own window); if that holds
  fewer than 2,000 prints, the 2,000 most recent fetched prints stamped before w; if fewer than 2,000 exist at all,
  missing. Fetched prints = every de-duplicated print of the coin in any merged window of either era (the union of
  the candidates' windows), whatever the window's status. A taker sell is big if its USD >= the threshold.
- ADV = reports/signal_lab/prints/adv_daily.csv.gz on the candidate's UTC day (that day's value uses days D-30..D-1).
- complete = the candidate's merged window has fetch status "complete" (a page reached a print stamped before the
  merged window's start, so every print of [start, end) was read).

Schema: one row per candidate, in the candidate list's order
  coin str, ts datetime64[ns], complete bool, n_prints int64 (prints in [q - 30 min, q)),
  usd_30, sell_usd_30, sell_usd_5, big_sell_usd_30, sweep_max_usd_30, big_thr_usd, adv_usd,
  csv_30 = sell_usd_30 / adv_usd, csv_5 = sell_usd_5 / adv_usd, sell_share_30 = sell_usd_30 / usd_30,
  big_sell_share_30 = big_sell_usd_30 / sell_usd_30, sweep_max_30 = sweep_max_usd_30 / adv_usd     (float64)
NaN rules: every float is NaN when complete is False. When complete: a ratio is NaN when its denominator is missing or
zero; big_* are NaN when the threshold is missing; a candidate with no print in its 30-minute window gets NaN for the
five F6 features (csv_30, csv_5, sell_share_30, big_sell_share_30, sweep_max_30; prereg: "A candidate with no prints
in its window gets missing values") while its USD sums are 0.
"""
import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SL = os.path.join(ROOT, "reports", "signal_lab")
PR = os.path.join(SL, "prints")
NS_S = 10 ** 9
W30, W5 = 30 * 60 * NS_S, 5 * 60 * NS_S
LOOKBACK = 30 * 86400 * NS_S
MIN_POOL, QTL = 2000, 0.99
SUMS = ["usd_30", "sell_usd_30", "sell_usd_5", "big_sell_usd_30", "sweep_max_usd_30", "big_thr_usd"]
F6 = ["csv_30", "csv_5", "sell_share_30", "big_sell_share_30", "sweep_max_30"]
FLOATS = SUMS + ["adv_usd"] + F6
SCHEMA = ["coin", "ts", "complete", "n_prints", "usd_30", "sell_usd_30", "sell_usd_5", "big_sell_usd_30",
          "sweep_max_usd_30", "big_thr_usd", "adv_usd"] + F6


# ------------------------------------------------------------------------------------------------ core
def prep(trade_id, t, price, size, sell, window_id=None):
    """De-duplicate by trade_id, then order by (time, trade_id). t: int64 ns. Returns (dict of arrays, checks)."""
    trade_id = np.asarray(trade_id, dtype=np.int64)
    _, first = np.unique(trade_id, return_index=True)            # sorted by trade_id
    d = dict(trade_id=trade_id[first], t=np.asarray(t, dtype=np.int64)[first],
             price=np.asarray(price, dtype=np.float64)[first], size=np.asarray(size, dtype=np.float64)[first],
             sell=np.asarray(sell, dtype=bool)[first])
    if window_id is not None:
        d["window_id"] = np.asarray(window_id)[first]
    checks = dict(n_in=int(len(trade_id)), n_dup=int(len(trade_id) - len(first)),
                  time_decreasing_along_id=int((np.diff(d["t"]) < 0).sum()))
    o = np.lexsort((d["trade_id"], d["t"]))
    d = {k: v[o] for k, v in d.items()}
    d["usd"] = d["price"] * d["size"]
    return d, checks


def coin_features(t, usd, sell, q):
    """F6 sums for one coin. t (int64 ns), usd, sell: the coin's prints from prep (ordered by time); q: int64 ns
    candidate minute starts. Every quantity of candidate i is read from slices that end before q[i]:
    [a, b) = [q - 30 min, q), [a5, b) = [q - 5 min, q), threshold pool [c, a) = [w - 30 days, w) with w = q - 30 min,
    or the 2,000 prints before index a."""
    t = np.asarray(t, dtype=np.int64)
    q = np.asarray(q, dtype=np.int64)
    sell_usd = np.where(sell, usd, 0.0)
    w = q - W30
    a = np.searchsorted(t, w, "left")
    b = np.searchsorted(t, q, "left")
    a5 = np.searchsorted(t, q - W5, "left")
    c = np.searchsorted(t, w - LOOKBACK, "left")
    n = len(q)
    out = {k: np.full(n, np.nan) for k in SUMS}
    extra = {k: np.full(n, np.nan) for k in ("vol_30", "px_first", "px_last")}
    extra["n_sell"] = np.zeros(n, dtype=np.int64)
    extra["thr_rule"] = np.zeros(n, dtype=np.int8)      # 1 = 30-day pool, 2 = latest 2,000, 0 = missing
    for i in range(n):
        ai, bi = int(a[i]), int(b[i])
        u, s = usd[ai:bi], sell_usd[ai:bi]
        out["usd_30"][i] = u.sum()
        out["sell_usd_30"][i] = s.sum()
        out["sell_usd_5"][i] = sell_usd[int(a5[i]):bi].sum()
        if ai - int(c[i]) >= MIN_POOL:
            thr, rule = float(np.quantile(usd[int(c[i]):ai], QTL)), 1
        elif ai >= MIN_POOL:
            thr, rule = float(np.quantile(usd[ai - MIN_POOL:ai], QTL)), 2
        else:
            thr, rule = np.nan, 0
        out["big_thr_usd"][i], extra["thr_rule"][i] = thr, rule
        if rule:
            out["big_sell_usd_30"][i] = s[u >= thr].sum()
        if bi > ai:
            sec = t[ai:bi] // NS_S
            starts = np.flatnonzero(np.r_[True, sec[1:] != sec[:-1]])
            out["sweep_max_usd_30"][i] = float(np.add.reduceat(s, starts).max())
        else:
            out["sweep_max_usd_30"][i] = 0.0
    return (b - a).astype(np.int64), out, extra, dict(a=a, b=b)


def finalize(complete, n_prints, sums, adv):
    """Ratios and NaN rules (module docstring). Returns a dict of float columns."""
    complete = np.asarray(complete, dtype=bool)
    n_prints = np.asarray(n_prints)
    f = {k: np.asarray(sums[k], dtype=np.float64).copy() for k in SUMS}
    f["adv_usd"] = np.asarray(adv, dtype=np.float64).copy()

    def ratio(x, y):
        x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
        ok = np.isfinite(x) & np.isfinite(y) & (y > 0)
        r = np.full(len(x), np.nan)
        r[ok] = x[ok] / y[ok]
        return r

    f["csv_30"] = ratio(f["sell_usd_30"], f["adv_usd"])
    f["csv_5"] = ratio(f["sell_usd_5"], f["adv_usd"])
    f["sell_share_30"] = ratio(f["sell_usd_30"], f["usd_30"])
    f["big_sell_share_30"] = ratio(f["big_sell_usd_30"], f["sell_usd_30"])
    f["sweep_max_30"] = ratio(f["sweep_max_usd_30"], f["adv_usd"])
    for k in F6:
        f[k][n_prints == 0] = np.nan
    for k in FLOATS:
        f[k][~complete] = np.nan
    return f


# ------------------------------------------------------------------------------------------------ io
def candidates():
    parts = []
    for era in ("main", "early"):
        c = pd.read_csv(os.path.join(SL, f"candidates_{era}.csv.gz"), parse_dates=["ts"])
        parts.append(pd.DataFrame({"coin": c.coin.astype(str).to_numpy(), "ts": c.ts.astype("datetime64[ns]").to_numpy(),
                                   "era": era}))
    return pd.concat(parts, ignore_index=True)


def window_of(C, W):
    wid = np.full(len(C), -1, dtype=np.int64)
    q_all = C.ts.to_numpy().astype("datetime64[ns]").view(np.int64)
    for p, g in W.groupby("product"):
        g = g.sort_values("start")
        idx = np.flatnonzero((C.coin == p[:-4]).to_numpy())
        st = g.start.to_numpy().astype("datetime64[ns]").view(np.int64)
        en = g.end.to_numpy().astype("datetime64[ns]").view(np.int64)
        q = q_all[idx]
        k = np.searchsorted(st, q - W30, "right") - 1
        kk = np.clip(k, 0, None)
        ok = (k >= 0) & (en[kk] >= q) & (st[kk] <= q - W30)
        wid[idx[ok]] = g.window_id.to_numpy()[kk[ok]]
    return wid


def load_coin(files, product):
    tabs = []
    for f in files:
        tb = pq.read_table(f, columns=["window_id", "trade_id", "time", "price", "size", "side"],
                           filters=[("product", "==", product)])
        if tb.num_rows:
            tabs.append(tb)
    if not tabs:
        return None, {}
    T = pa.concat_tables(tabs)
    side = T["side"]
    sides = {str(r["values"]): int(r["counts"]) for r in pc.value_counts(side).to_pylist()}
    t = T["time"].cast(pa.timestamp("ns")).to_numpy().astype("datetime64[ns]").view(np.int64)
    d = dict(trade_id=T["trade_id"].to_numpy(), t=t, price=T["price"].to_numpy(), size=T["size"].to_numpy(),
             sell=pc.equal(side, "BUY").to_numpy(zero_copy_only=False), window_id=T["window_id"].to_numpy())
    del T, tabs
    return d, sides


def statuses(art_dir):
    fs = sorted(glob.glob(os.path.join(art_dir, "**", "status_*.csv"), recursive=True))
    if not fs:
        return pd.Series(dtype=str), 0
    S = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
    rank = S.status.map({"complete": 0}).fillna(1)                  # a window fetched twice: keep a complete row
    S = S.assign(rank=rank).sort_values(["window_id", "rank"]).drop_duplicates("window_id")
    return S.set_index("window_id").status, len(fs)


def main(art_dir, out_dir=PR):
    t0 = time.time()
    sys.path.insert(0, HERE)
    import test_prints                                               # synthetic look-ahead tests first
    test_prints.run()
    files = sorted(glob.glob(os.path.join(art_dir, "**", "prints_*.parquet"), recursive=True))
    st, n_sfiles = statuses(art_dir)
    W = pd.read_csv(os.path.join(PR, "windows.csv"), parse_dates=["start", "end"])
    C = candidates()
    C["window_id"] = window_of(C, W)
    assert (C.window_id >= 0).all(), "a candidate window lies outside every merged window"
    C["status"] = C.window_id.map(st).fillna("missing").astype(str)
    C["complete"] = (C.status == "complete").to_numpy()
    A = pd.read_csv(os.path.join(PR, "adv_daily.csv.gz"), parse_dates=["day"])
    A["day"] = A.day.astype("datetime64[ns]")
    adv_map = A.set_index(["coin", "day"]).adv_usd
    C["adv_usd"] = adv_map.reindex(pd.MultiIndex.from_arrays([C.coin, C.ts.dt.floor("D")])).to_numpy()
    n = len(C)
    n_prints = np.zeros(n, dtype=np.int64)
    sums = {k: np.full(n, np.nan) for k in SUMS}
    ex = {k: np.full(n, np.nan) for k in ("vol_30", "px_first", "px_last")}
    ex["n_sell"] = np.zeros(n, dtype=np.int64)
    ex["thr_rule"] = np.zeros(n, dtype=np.int8)
    qa = dict(print_files=len(files), status_files=n_sfiles, coins={})
    assert (W.window_id.to_numpy() == np.arange(len(W))).all()
    w_lo = W.start.to_numpy().astype("datetime64[ns]").view(np.int64)
    w_hi = W.end.to_numpy().astype("datetime64[ns]").view(np.int64)
    for coin in sorted(C.coin.unique()):
        t1 = time.time()
        idx = np.flatnonzero((C.coin == coin).to_numpy())
        q = C.ts.to_numpy()[idx].astype("datetime64[ns]").view(np.int64)
        raw, sides = load_coin(files, f"{coin}-USD")
        if raw is None:
            nn, s, e = coin_features(np.zeros(0, np.int64), np.zeros(0), np.zeros(0, bool), q)[:3]
            qa["coins"][coin] = dict(prints=0)
        else:
            d, chk = prep(raw["trade_id"], raw["t"], raw["price"], raw["size"], raw["sell"], raw["window_id"])
            del raw
            wi = d["window_id"].astype(np.int64)
            chk["outside_own_window"] = int(((d["t"] < w_lo[wi]) | (d["t"] >= w_hi[wi])).sum())
            chk["windows_with_prints"] = int(len(np.unique(wi)))
            chk["prints"] = int(len(d["t"]))
            chk["sides"] = sides
            chk["usd_total"] = float(d["usd"].sum())
            nn, s, e, ab = coin_features(d["t"], d["usd"], d["sell"], q)
            vol_c = np.concatenate([[0.0], np.cumsum(d["size"])])
            e["vol_30"] = vol_c[ab["b"]] - vol_c[ab["a"]]
            has = ab["b"] > ab["a"]
            e["px_first"][has] = d["price"][ab["a"][has]]
            e["px_last"][has] = d["price"][ab["b"][has] - 1]
            sc = np.concatenate([[0], np.cumsum(d["sell"].astype(np.int64))])
            e["n_sell"] = sc[ab["b"]] - sc[ab["a"]]
            qa["coins"][coin] = chk
            del d
        n_prints[idx] = nn
        for k in SUMS:
            sums[k][idx] = s[k]
        for k in ex:
            ex[k][idx] = e[k]
        print(f"{coin}: {len(idx)} candidates, {qa['coins'][coin].get('prints', 0)} prints, "
              f"{time.time() - t1:.0f}s", flush=True)
    f = finalize(C.complete.to_numpy(), n_prints, sums, C.adv_usd.to_numpy())
    F = pd.DataFrame({"coin": C.coin.astype(str).to_numpy(), "ts": C.ts.to_numpy().astype("datetime64[ns]"),
                      "complete": C.complete.to_numpy().astype(bool), "n_prints": n_prints.astype(np.int64)})
    for k in SCHEMA[4:]:
        F[k] = f[k].astype(np.float64)
    F = F[SCHEMA]
    os.makedirs(out_dir, exist_ok=True)
    for era in ("main", "early"):
        m = (C.era == era).to_numpy()
        F[m].reset_index(drop=True).to_parquet(os.path.join(out_dir, f"f6_{era}.parquet"), index=False)
    Q = pd.DataFrame({"era": C.era.to_numpy(), "coin": C.coin.astype(str).to_numpy(), "ts": F.ts.to_numpy(),
                      "window_id": C.window_id.to_numpy(), "status": C.status.to_numpy()})
    for k in ex:
        Q[k] = ex[k]
    Q.to_parquet(os.path.join(out_dir, "qa_cand.parquet"), index=False)
    S2 = st.reindex(W.window_id).fillna("missing")
    qa["window_status"] = {era: S2[(W.start < "2024-01-01").to_numpy() == (era == "early")].value_counts().to_dict()
                           for era in ("main", "early")}
    qa["thr_rule_counts"] = {era: pd.Series(ex["thr_rule"][(C.era == era).to_numpy()]).value_counts().to_dict()
                             for era in ("main", "early")}
    qa["thr_rule_counts"] = {e_: {int(k): int(v) for k, v in d_.items()} for e_, d_ in qa["thr_rule_counts"].items()}
    qa["seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(out_dir, "qa_runner.json"), "w") as fh:
        json.dump(qa, fh, indent=1, default=str)
    print(f"done: {n} candidates, complete {int(C.complete.sum())}, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(*sys.argv[1:3])
