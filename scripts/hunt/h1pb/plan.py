#!/usr/bin/env python3
"""H1 fetch plan: candidate minutes from 1-minute candles (k = 3, both sides, spot-synchronous superset, which contains
the minute-mode candidates), the perp-print windows and spot-print windows they need, and a deterministic split into
chunks and shards balanced by estimated requests.

Perp window of candidate minute t: [t - 1 min, e_t + 1 min), e_t = the first minute >= t + 62 with a perp trade, so the
first print at least 2 s after any 60-minute deadline is inside the window.
Spot window of candidate minute t: [t - 1 min, t + 1 min): a print at tau uses row r = minute(tau - 1 s), r in {t-1, t};
the last spot trade <= tau - 1 s is in the fetched minutes, or else it is the close of the last traded minute before
the window (from candles).
Chunks: each coin's candidate minutes are cut into consecutive trigger ranges [a, b) of about `target` estimated
requests; a chunk fetches the windows of its own candidates (adjacent chunks may overlap by up to ~1 hour of perp
prints). Only triggers whose print falls in a candle minute of [a, b) are kept by that chunk.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402
import levels as LV  # noqa: E402

CPT = {"BTC": 8.0, "ETH": 29.0, "SOL": 3.5, "XRP": 2.0}            # contracts per perp print (probe_density.csv)
SPOT_TRADE_USD = {"BTC": 1500.0, "ETH": 1400.0, "SOL": 1100.0, "XRP": 1100.0}
SEG_MAX_MIN = 120                                                 # fetch requests are issued per <= 2-hour piece


def _segments(mask):
    """[start, end) index pairs of the True runs of a boolean array."""
    m = np.r_[False, mask, False].astype(np.int8)
    d = np.diff(m)
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]))


def et_window_mask(idx, lo_min, hi_min):
    """Minutes whose America/New_York clock time (minutes after midnight) is in [lo_min, hi_min)."""
    t = idx.tz_localize("UTC").tz_convert("America/New_York")
    m = t.hour * 60 + t.minute
    return np.asarray((m >= lo_min) & (m < hi_min))


def coin_plan(coin, d0, d1, modes=("minute", "sync"), delta=None, cand_k=3.0, cand_sides=("long", "short"), window=None):
    """delta: optional sorted array of rows; then only candle minutes t with row t or t-1 in delta are candidates."""
    st = LV.stats(coin, end=d1)
    if st is None:
        return None
    idx = st["idx"]
    n = len(idx)
    lo, hi = LV.candidates(st, cand_k, sync=("sync" in modes))
    cand = ((lo if "long" in cand_sides else False) | (hi if "short" in cand_sides else False)) & (idx >= d0) & (idx < d1)
    if window is not None:                         # frozen time-of-day filter: fill minutes inside the ET window only
        cand &= et_window_mask(idx, *window)
    dm = None
    if delta is not None:
        dm = np.zeros(n, bool)
        dm[np.asarray(delta, np.int64)[np.asarray(delta) < n]] = True
        cand &= dm | np.r_[False, dm[:-1]]
    ci = np.nonzero(cand)[0]
    traded = np.isfinite(st["p_close"])
    nxt = np.full(n + 1, n, np.int64)                           # next traded minute index (n = none)
    for i in range(n - 1, -1, -1):
        nxt[i] = i if traded[i] else nxt[i + 1]
    e = nxt[np.minimum(ci + 62, n)]
    w_end = np.minimum(e + 1, n)
    pw = np.zeros(n + 1, np.int32)
    np.add.at(pw, np.maximum(ci - 1, 0), 1)
    np.add.at(pw, w_end, -1)
    perp_need = np.cumsum(pw)[:n] > 0
    sw = np.zeros(n + 1, np.int32)
    if "sync" in modes:
        np.add.at(sw, np.maximum(ci - 1, 0), 1)
        np.add.at(sw, np.minimum(ci + 1, n), -1)
    spot_need = np.cumsum(sw)[:n] > 0
    # cost estimates (requests)
    cpt = CPT.get(coin, 3.0)
    p_prints = np.where(traded, np.maximum(1.0, np.nan_to_num(st["p_vol"]) / cpt), 0.0)
    s_usd = np.nan_to_num(st["s_close"]) * 0.0
    S = common.load_minute(coin)
    S = S[(S.index >= idx[0]) & (S.index < d1)].reindex(idx)
    s_usd = (S["volume"].fillna(0.0) * S["close"].fillna(0.0)).to_numpy()
    s_prints = s_usd / SPOT_TRADE_USD.get(coin, 600.0)
    return dict(coin=coin, st=st, idx=idx, cand=ci, w_end=w_end, perp_need=perp_need, spot_need=spot_need,
                p_prints=p_prints, s_prints=s_prints, delta_mask=dm)


def _cost(pl, a, b):
    """Estimated requests for the candidates in minute range [a, b)."""
    ci = pl["cand"]
    sel = ci[(ci >= a) & (ci < b)]
    if not len(sel):
        return 0.0, [], []
    n = len(pl["idx"])
    pw = np.zeros(n + 1, np.int32)
    np.add.at(pw, np.maximum(sel - 1, 0), 1)
    np.add.at(pw, pl["w_end"][np.searchsorted(ci, sel)], -1)
    pm = np.cumsum(pw)[:n] > 0
    sw = np.zeros(n + 1, np.int32)
    if pl["spot_need"].any():
        np.add.at(sw, np.maximum(sel - 1, 0), 1)
        np.add.at(sw, np.minimum(sel + 1, n), -1)
    sm = np.cumsum(sw)[:n] > 0
    psegs, ssegs = _segments(pm), _segments(sm)
    c = pl["p_prints"][pm].sum() / 1000 + sum(1 + (e - s) // SEG_MAX_MIN for s, e in psegs)
    c += pl["s_prints"][sm].sum() / 1000 + sum(1 + (e - s) // SEG_MAX_MIN for s, e in ssegs)
    return float(c), psegs, ssegs


def chunks(pl, target):
    """Cut a coin's candidates into trigger ranges of about `target` requests."""
    ci = pl["cand"]
    if not len(ci):
        return []
    # cumulative cost proxy per candidate: its own minute's perp + spot prints and window length
    proxy = (pl["p_prints"][ci] * 3 + pl["s_prints"][ci] * 2) / 1000 + 0.2
    cum = np.cumsum(proxy)
    out, a_i = [], 0
    total = cum[-1]
    nb = max(1, int(np.ceil(total / max(target, 1e-9))))
    cuts = np.searchsorted(cum, np.linspace(0, total, nb + 1)[1:-1])
    bounds = [0] + sorted(set(int(c) for c in cuts if 0 < c < len(ci))) + [len(ci)]
    for x, y in zip(bounds[:-1], bounds[1:]):
        a = int(ci[x])
        b = int(ci[y]) if y < len(ci) else int(ci[-1]) + 1
        cost, psegs, ssegs = _cost(pl, a, b)
        out.append(dict(coin=pl["coin"], a=a, b=b, cost=cost, psegs=psegs, ssegs=ssegs))
    return out


def make(coins, d0, d1, n_shards, modes=("minute", "sync"), per_shard_chunks=4, verbose=False, deltas=None, **kw):
    """Deterministic plan: list of chunk dicts with a 'shard' field."""
    plans, all_chunks = {}, []
    rough = {}
    for c in coins:
        pl = coin_plan(c, d0, d1, modes, None if deltas is None else deltas.get(c, np.zeros(0, np.int64)), **kw)
        if pl is None or not len(pl["cand"]):
            continue
        rough[c] = float((pl["p_prints"][pl["perp_need"]].sum() + pl["s_prints"][pl["spot_need"]].sum()) / 1000)
        plans[c] = pl
    total = sum(rough.values())
    target = max(50.0, total / (n_shards * per_shard_chunks))
    for c, pl in plans.items():
        for ch in chunks(pl, target):
            ch["t0"] = pl["idx"][0]
            all_chunks.append(ch)
        if verbose:
            print(f"  plan {c}: {len(pl['cand'])} candidate minutes, ~{rough[c]:.0f} requests", flush=True)
    order = sorted(range(len(all_chunks)), key=lambda i: -all_chunks[i]["cost"])
    load = np.zeros(n_shards)
    for i in order:
        s = int(np.argmin(load))
        all_chunks[i]["shard"] = s
        load[s] += all_chunks[i]["cost"]
    return all_chunks, plans, load
