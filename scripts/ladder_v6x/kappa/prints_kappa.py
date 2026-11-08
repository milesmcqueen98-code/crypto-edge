#!/usr/bin/env python3
"""Ladder v6 exits, kappa(m): the market-sell cost at minute m after a fill, measured on Coinbase prints.

Red team 2's measurement (scripts/ladder_v5/redteam2/prints_exit.py on ladder/redteam2; same conventions, same
functions) at the event minutes of reports/ladder_v6x_prereg.md "Exit costs at any minute". Runs on GitHub Actions
(.github/workflows/ladder-prints.yml on branch ladder/v6x-kappa) over the trades-* artifacts of the ladder-fetch run
(windows reports/ladder_v6x/kappa/windows.csv). Only derived per-event numbers are written; raw prints stay in the
artifacts.
Conventions: prints sharing a timestamp (and maker side) are one taker order; `side` is the maker's side, so maker
side "buy" = an aggressive SELL order (the kind a market exit is). A candle stamped t covers [t, t+1 min).

Per event (reports/ladder_v6x/kappa/sample.csv) and event minute m in (2, 5, 10, 20, 30, 45, 60): the market sale at
T_m = fill_t + (m + 1) min, the close of the candle that starts fill_t + m (m = 60 is red team 2's T0, the incumbent's
exit):
  close_px, close_side, close_age_s   last print before T_m, its maker side and age
  hs_bp, hs_n            half the median quoted spread from clean bounces in [T_m - 5 min, T_m + 1 min): consecutive
                         taker orders of opposite sides within 1 s, both filled at a single price; |price gap| / mid
  hs_mean_bp             the same, mean
  roll_hs_bp             Roll's half-spread from successive order-VWAP changes in the same range
  n_sell_orders, max_sell_usd   aggressive sell orders in [T_m - 5 min, T_m + 5 min) and the largest in USD
  slip_<X>, n_<X>        a market SELL of X USD walks the bids: the slippage (bp) of the first X USD below the first
                         price of every aggressive sell order of at least X USD in [T_m - 5 min, T_m + 5 min); median
                         over those orders, and their count (X on red team 2's grid)
  slip_at_X, n_at_X      the same at the event's own size X (sample.csv: fill / fsc)
  dlb_<d>                largest USD one aggressive sell order took within d bp of its first price in the same range
  prints_in_window       prints in the event's fetch window (0: the window failed or returned nothing)
Sensitivity (never used as kappa), prints_kappa_clip.csv: m = 2 and 5 with every print before fill_t + 1 min dropped
(the fill minute and the move before it excluded), same measures.
Also windows_cover.csv: per window, prints and the first and last print time.
usage: python scripts/ladder_v6x/kappa/prints_kappa.py <artifact dir>
"""
import glob
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
KD = os.path.join(ROOT, "reports", "ladder_v6x", "kappa")
XS = (250, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000)
DS = (2, 5, 10, 25)
MS = (2, 5, 10, 20, 30, 45, 60)
MS_CLIP = (2, 5)
PRE, POST = 3, 67                     # each event's window: [fill_t - PRE min, fill_t + POST min)
CLIP = 1                              # sensitivity: prints from fill_t + CLIP min on
NS = 1_000_000_000


def orders(t, px, sz, mb):
    """Group prints (sorted by time, trade id) into taker orders. Returns per-print order id and per-order arrays.
    (red team 2's prints_exit.orders, unchanged)"""
    new = np.ones(len(t), bool)
    new[1:] = (t[1:] != t[:-1]) | (mb[1:] != mb[:-1])
    oid = np.cumsum(new) - 1
    starts = np.nonzero(new)[0]
    ends = np.append(starts[1:], len(t)) - 1
    usd = px * sz
    o_usd = np.add.reduceat(usd, starts)
    o_sz = np.add.reduceat(sz, starts)
    O = dict(t=t[starts], mb=mb[starts], first=px[starts], last=px[ends], usd=o_usd, vwap=o_usd / o_sz,
             single=(px[starts] == px[ends]), start=starts, end=ends)
    # within-order cumulative usd / size (inclusive), for first-X VWAPs
    cu = np.cumsum(usd)
    cs = np.cumsum(sz)
    base_u = np.repeat(np.append(0.0, cu[ends[:-1]]), ends - starts + 1)
    base_s = np.repeat(np.append(0.0, cs[ends[:-1]]), ends - starts + 1)
    return oid, O, cu - base_u, cs - base_s


def order_key(oid, cu_in):
    """first_x_slip's search key, computed once per window (red team 2 recomputed it in every call; same values)."""
    return (oid.astype(np.int64) << 35) + np.minimum(np.round(cu_in * 100), 2 ** 35 - 1).astype(np.int64)


def first_x_slip(sel, X, O, px, cu_in, cs_in, oid, key=None):
    """Slippage (bp, vs the order's first price) of the first X USD of each selected order (all with usd >= X).
    (red team 2's prints_exit.first_x_slip, unchanged but for the optional precomputed key)"""
    if not len(sel):
        return np.array([])
    if key is None:
        key = order_key(oid, cu_in)
    j = np.searchsorted(key, (sel.astype(np.int64) << 35) + int(round(X * 100)), side="left")
    j = np.minimum(j, len(px) - 1)
    st = O["start"][sel]
    prev_u = np.where(j > st, cu_in[np.maximum(j - 1, 0)], 0.0)
    prev_s = np.where(j > st, cs_in[np.maximum(j - 1, 0)], 0.0)
    coins = prev_s + (X - prev_u) / px[j]
    vw = X / coins
    return 1e4 * np.log(O["first"][sel] / vw)


def prep(t, px, sz, mb):
    """Per-window arrays shared by every event and minute."""
    oid, O, cu_in, cs_in = orders(t, px, sz, mb)
    return dict(t=t, px=px, sz=sz, mb=mb, usd=px * sz, oid=oid, O=O, cu_in=cu_in, cs_in=cs_in, sell=O["mb"],
                dep=1e4 * np.log(O["first"][oid] / px), key=order_key(oid, cu_in))


def measure(P, Tm, x_own):
    """red team 2's per-(event, m) block of prints_exit.main, unchanged, plus the first-X slippage at x_own."""
    t, px, mb, usd = P["t"], P["px"], P["mb"], P["usd"]
    oid, O, cu_in, cs_in, sell, dep, key = P["oid"], P["O"], P["cu_in"], P["cs_in"], P["sell"], P["dep"], P["key"]
    r = {}
    b = np.searchsorted(t, Tm) - 1
    r["close_px"] = px[b] if b >= 0 else np.nan
    r["close_side"] = ("buy" if mb[b] else "sell") if b >= 0 else ""
    r["close_age_s"] = (Tm - t[b]) / NS if b >= 0 else np.nan
    # spread: clean bounces
    o_lo, o_hi = np.searchsorted(O["t"], Tm - 300 * NS), np.searchsorted(O["t"], Tm + 60 * NS)
    ii = np.arange(max(o_lo, 1), max(o_hi, 1))
    ok = (O["mb"][ii] != O["mb"][ii - 1]) & ((O["t"][ii] - O["t"][ii - 1]) <= NS) & \
        O["single"][ii] & O["single"][ii - 1]
    gap = np.abs(O["first"][ii] - O["first"][ii - 1]) / (0.5 * (O["first"][ii] + O["first"][ii - 1]))
    gap = gap[ok]
    r["hs_n"] = int(len(gap))
    r["hs_bp"] = float(0.5e4 * np.median(gap)) if len(gap) else np.nan
    r["hs_mean_bp"] = float(0.5e4 * np.mean(gap)) if len(gap) else np.nan
    vw = O["vwap"][o_lo:o_hi]
    if len(vw) > 10:
        dp = np.diff(np.log(vw))
        cv = np.cov(dp[1:], dp[:-1])[0, 1] if len(dp) > 2 else 0.0
        r["roll_hs_bp"] = float(1e4 * np.sqrt(-cv)) if cv < 0 else 0.0
    else:
        r["roll_hs_bp"] = np.nan
    # depth: aggressive sells within +-5 minutes
    a_lo, a_hi = np.searchsorted(O["t"], Tm - 300 * NS), np.searchsorted(O["t"], Tm + 300 * NS)
    idx = np.arange(a_lo, a_hi)
    idx = idx[sell[idx]]
    r["n_sell_orders"] = int(len(idx))
    r["max_sell_usd"] = float(O["usd"][idx].max()) if len(idx) else 0.0
    for X in XS:
        q = idx[O["usd"][idx] >= X]
        sl = first_x_slip(q, X, O, px, cu_in, cs_in, oid, key)
        r[f"n_{X}"] = int(len(sl))
        r[f"slip_{X}"] = float(np.median(sl)) if len(sl) else np.nan
    q = idx[O["usd"][idx] >= x_own]
    sl = first_x_slip(q, x_own, O, px, cu_in, cs_in, oid, key)
    r["n_at_X"] = int(len(sl))
    r["slip_at_X"] = float(np.median(sl)) if len(sl) else np.nan
    if len(idx):
        p_lo, p_hi = O["start"][idx[0]], O["end"][idx[-1]] + 1
        pp = np.arange(p_lo, p_hi)
        pp = pp[sell[oid[pp]]]
        for d in DS:
            msk = dep[pp] <= d + 1e-9
            v = np.bincount(oid[pp][msk] - oid[pp][0], weights=usd[pp][msk]) if msk.any() else [0.0]
            r[f"dlb_{d}"] = float(np.max(v))
    else:
        for d in DS:
            r[f"dlb_{d}"] = 0.0
    return r


def assign_windows(E, W):
    """Each event's window: the window of its product and era that contains [fill_t - PRE, fill_t + POST)."""
    wid = np.full(len(E), -1)
    for p, g in W.groupby(["product", "era_tag"]):
        e_ix = np.nonzero(((E["product"] == p[0]) & (E.era_tag == p[1])).to_numpy())[0]
        if not len(e_ix):
            continue
        a = (E.fill_t.iloc[e_ix] - pd.Timedelta(minutes=PRE)).to_numpy()
        b = (E.fill_t.iloc[e_ix] + pd.Timedelta(minutes=POST)).to_numpy()
        gs, ge, gw = g.start.to_numpy(), g.end.to_numpy(), g.window_id.to_numpy()
        for n, (x, y) in zip(e_ix, zip(a, b)):
            k = np.nonzero((gs <= x) & (ge >= y))[0]
            if len(k):
                wid[n] = gw[k[0]]
    return wid


def main(art):
    t_start = time.time()
    W = pd.read_csv(os.path.join(KD, "windows.csv"), parse_dates=["start", "end"])
    E = pd.read_csv(os.path.join(KD, "sample.csv"), parse_dates=["fill_t"])
    E["product"] = E.coin + "-USD"
    E["window_id"] = assign_windows(E, W)
    print(f"{len(E)} events, {np.mean(E.window_id >= 0):.1%} inside a window; {len(W)} windows", flush=True)
    ev_by_w = {w: g for w, g in E[E.window_id >= 0].groupby("window_id")}
    files = sorted(glob.glob(os.path.join(art, "**", "trades_*.parquet"), recursive=True))
    rows, rows_c, cover, n_prints, n_dup = {}, [], [], 0, 0
    for f in files:
        T = pd.read_parquet(f, columns=["window_id", "trade_id", "time", "price", "size", "side"])
        n_prints += len(T)
        T["mb"] = (T.side == "buy").to_numpy()
        T = T.drop(columns="side").sort_values(["window_id", "time", "trade_id"])
        d = T.duplicated(["window_id", "trade_id"])
        n_dup += int(d.sum())
        T = T[~d.to_numpy()]
        for w, g in T.groupby("window_id", sort=False):
            if w not in ev_by_w:
                continue
            t = g.time.to_numpy().astype("datetime64[ns]").astype(np.int64)
            px = g.price.to_numpy(np.float64)
            sz = g["size"].to_numpy(np.float64)
            mb = g.mb.to_numpy()
            cover.append(dict(window_id=w, n_prints=len(g), first_t=g.time.iloc[0], last_t=g.time.iloc[-1],
                              n_events=len(ev_by_w[w])))
            P = prep(t, px, sz, mb)
            for e in ev_by_w[w].itertuples():
                f0 = int(pd.Timestamp(e.fill_t).value)
                rec0 = dict(event_id=e.event_id, coin=e.coin, era_tag=e.era_tag, fill_t=e.fill_t, k=e.k, X=e.X,
                            prints_in_window=len(g))
                for m in MS:
                    rows[(e.event_id, m)] = dict(rec0, m=m, **measure(P, f0 + (m + 1) * 60 * NS, e.X))
                c0 = np.searchsorted(t, f0 + CLIP * 60 * NS)
                if c0 < len(t):
                    Pc = prep(t[c0:], px[c0:], sz[c0:], mb[c0:])
                    for m in MS_CLIP:
                        rows_c.append(dict(rec0, m=m, clip_from=e.fill_t + pd.Timedelta(minutes=CLIP),
                                           **measure(Pc, f0 + (m + 1) * 60 * NS, e.X)))
        print(f"{os.path.basename(f)}: {len(T):,} prints; {len(rows)} event-minutes so far; "
              f"{time.time() - t_start:.0f}s", flush=True)
    # one row per event and m, events without prints included (no measurements)
    out = []
    for e in E.itertuples():
        for m in MS:
            r = rows.get((e.event_id, m))
            if r is None:
                r = dict(event_id=e.event_id, coin=e.coin, era_tag=e.era_tag, fill_t=e.fill_t, k=e.k, X=e.X,
                         prints_in_window=0, m=m, hs_n=0, n_sell_orders=0, n_at_X=0,
                         **{f"n_{x}": 0 for x in XS})
            out.append(r)
    cols = (["event_id", "coin", "era_tag", "fill_t", "k", "X", "m", "close_px", "close_side", "close_age_s", "hs_n",
             "hs_bp", "hs_mean_bp", "roll_hs_bp", "n_sell_orders", "max_sell_usd"]
            + [c for x in XS for c in (f"n_{x}", f"slip_{x}")] + ["n_at_X", "slip_at_X"]
            + [f"dlb_{d}" for d in DS] + ["prints_in_window"])
    X_ = pd.DataFrame(out).reindex(columns=cols)
    C_ = pd.DataFrame(rows_c).reindex(columns=cols + ["clip_from"])
    V_ = W.merge(pd.DataFrame(cover, columns=["window_id", "n_prints", "first_t", "last_t", "n_events"]),
                 on="window_id", how="left")
    V_["n_prints"] = V_.n_prints.fillna(0).astype(int)
    V_["first_gap_min"] = (pd.to_datetime(V_.first_t) - V_.start).dt.total_seconds() / 60
    V_["last_gap_min"] = (V_.end - pd.to_datetime(V_.last_t)).dt.total_seconds() / 60
    X_.to_csv(os.path.join(KD, "prints_kappa.csv"), index=False)
    C_.to_csv(os.path.join(KD, "prints_kappa_clip.csv"), index=False)
    V_.to_csv(os.path.join(KD, "windows_cover.csv"), index=False)
    has = X_[X_.prints_in_window > 0].event_id.nunique()
    print(f"{n_prints:,} prints in {len(files)} files ({n_dup} duplicate trade ids dropped); "
          f"{has} of {len(E)} events with prints; windows with prints {int((V_.n_prints > 0).sum())} of {len(V_)}; "
          f"{time.time() - t_start:.0f}s")
    print("windows without prints:", V_[V_.n_prints == 0][["window_id", "product", "start"]].to_dict("records"))
    print("windows whose first print is > 2 min after the start or last print > 2 min before the end:",
          V_[(V_.first_gap_min > 2) | (V_.last_gap_min > 2)][["window_id", "product", "start", "n_prints",
                                                                "first_gap_min", "last_gap_min"]].to_dict("records"))
    if len(X_):
        print(X_.groupby("m")[["hs_n", "hs_bp", "roll_hs_bp", "n_sell_orders", "max_sell_usd", "slip_1000",
                               "slip_5000", "slip_20000", "n_at_X", "slip_at_X"]].median().round(3).to_string())


if __name__ == "__main__":
    main(sys.argv[1])
