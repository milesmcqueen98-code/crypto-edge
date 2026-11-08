#!/usr/bin/env python3
"""Red team 2 (ladder v5): the 60-minute exit's cost and the passive exit's fills, measured on Coinbase prints.

Runs on GitHub Actions (.github/workflows/ladder-prints.yml) over the trades-* artifacts of the ladder-fetch run on
branch ladder/redteam2 (windows reports/ladder_v5/redteam2/windows_exit.csv). Only derived numbers are written.
Conventions: prints sharing a timestamp (and maker side) are one taker order; `side` is the maker's side, so maker
side "buy" = an aggressive SELL order (the kind our market exit is). A candle stamped t covers [t, t+1 min).

Per event (reports/ladder_v5/redteam2/events_exit.csv: a tranche whose remainder is sold at the close of the candle
starting fill_t + 60 min, i.e. at T0 = fill_t + 61 min) and per m in (0, 5, 15) (the market sale at T_m = T0 + m min:
the incumbent's exit, and C3's leftover sale for N = 5 / 15):
  close_px, close_side   last print before T_m and its maker side
  hs_bp, hs_n            half the median quoted spread from clean bounces in [T_m - 5 min, T_m + 1 min): consecutive
                         taker orders of opposite sides within 1 s, both filled at a single price; |price gap| / mid
  roll_hs_bp             Roll's half-spread from successive order-VWAP changes in the same range
  slip_<X>, n_<X>        a market SELL of X USD walks the bids: the slippage below the best bid (bp) of the first
                         X USD of every aggressive sell order of at least X USD in [T_m - 5 min, T_m + 5 min) (exactly
                         what an order of X would have paid at that instant); median over those orders, and their count
  dlb_<d>                largest USD amount one aggressive sell order took within d bp of its first price in the same
                         range (a lower bound on the bid depth within d bp)
Per event and passive minute j = 1..15 (the candle starting fill_t + 60 + j, i.e. [T0 + (j-1) min, T0 + j min)):
  peg_ref                last print before the minute (the previous candle's close)
  for the model's tick (wick_sim.spot_tick, used by exit_paths_<tag>.pkl) and the real spot tick:
    v_ge_*   USD printed at or above peg = peg_ref + tick
    v_gt_*   USD printed at or above peg + tick (the model's one-tick trade-through)
    v_gtb_*  of v_gt, prints where the aggressor bought (maker side "sell")
    t_gt_*   seconds into the minute of the first print at or above peg + tick
    cap_u_*  the frozen model's capacity formula (candle volume spread evenly over the range above the peg) applied
             to the prints' own high, low and volume
  hi, lo, usd, n, first_px, first_side
Pooled per coin and era (prints_rt2_coin.csv): the first-X slippage of every distinct aggressive sell order within
5 minutes of any T0, by X.
usage: python scripts/ladder_v5/redteam2/prints_exit.py <artifact dir> rt2
"""
import glob
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LV5 = os.path.join(ROOT, "reports", "ladder_v5")
RT = os.path.join(LV5, "redteam2")
XS = (250, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000)
DS = (2, 5, 10, 25)
MS = (0, 5, 15)
NJ = 15
NS = 1_000_000_000


def orders(t, px, sz, mb):
    """Group prints (sorted by time, trade id) into taker orders. Returns per-print order id and per-order arrays."""
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


def first_x_slip(sel, X, O, px, cu_in, cs_in, oid):
    """Slippage (bp, vs the order's first price) of the first X USD of each selected order (all with usd >= X)."""
    if not len(sel):
        return np.array([])
    key = (oid.astype(np.int64) << 35) + np.minimum(np.round(cu_in * 100), 2 ** 35 - 1).astype(np.int64)
    j = np.searchsorted(key, (sel.astype(np.int64) << 35) + int(round(X * 100)), side="left")
    j = np.minimum(j, len(px) - 1)
    st = O["start"][sel]
    prev_u = np.where(j > st, cu_in[np.maximum(j - 1, 0)], 0.0)
    prev_s = np.where(j > st, cs_in[np.maximum(j - 1, 0)], 0.0)
    coins = prev_s + (X - prev_u) / px[j]
    vw = X / coins
    return 1e4 * np.log(O["first"][sel] / vw)


def main(art, tag="rt2"):
    t_start = time.time()
    W = pd.read_csv(os.path.join(RT, "windows_exit.csv"), parse_dates=["start", "end"])
    E = pd.read_csv(os.path.join(RT, "events_exit.csv"), parse_dates=["fill_t"])
    E["product"] = E.coin + "-USD"
    # each event's window
    wid = np.full(len(E), -1)
    for p, g in W.groupby(["product", "era_tag"]):
        e_ix = np.nonzero(((E["product"] == p[0]) & (E.era_tag == p[1])).to_numpy())[0]
        if not len(e_ix):
            continue
        a = (E.fill_t.iloc[e_ix] + pd.Timedelta(minutes=55)).to_numpy()
        b = (E.fill_t.iloc[e_ix] + pd.Timedelta(minutes=82)).to_numpy()
        gs, ge, gw = g.start.to_numpy(), g.end.to_numpy(), g.window_id.to_numpy()
        for n, (x, y) in zip(e_ix, zip(a, b)):
            k = np.nonzero((gs <= x) & (ge >= y))[0]
            if len(k):
                wid[n] = gw[k[0]]
    E["window_id"] = wid
    print(f"{len(E)} events, {np.mean(wid >= 0):.1%} inside a window", flush=True)
    ev_by_w = {w: g for w, g in E[E.window_id >= 0].groupby("window_id")}
    files = sorted(glob.glob(os.path.join(art, "**", "trades_*.parquet"), recursive=True))
    rows_x, rows_p, pool, n_prints, seen_w = [], [], {}, 0, set()
    for f in files:
        T = pd.read_parquet(f, columns=["window_id", "trade_id", "time", "price", "size", "side"])
        n_prints += len(T)
        T["mb"] = (T.side == "buy").to_numpy()
        T = T.drop(columns="side").sort_values(["window_id", "time", "trade_id"])
        for w, g in T.groupby("window_id", sort=False):
            if w not in ev_by_w:
                continue
            seen_w.add(w)
            t = g.time.to_numpy().astype("datetime64[ns]").astype(np.int64)
            px = g.price.to_numpy(np.float64)
            sz = g["size"].to_numpy(np.float64)
            mb = g.mb.to_numpy()
            usd = px * sz
            oid, O, cu_in, cs_in = orders(t, px, sz, mb)
            sell = O["mb"]                                   # aggressive sells
            dep = 1e4 * np.log(O["first"][oid] / px)          # per print: bp below its order's first price
            pool_ids = set()
            for e in ev_by_w[w].itertuples():
                T0 = int(pd.Timestamp(e.fill_t + pd.Timedelta(minutes=61)).value)
                rec0 = dict(event_id=e.event_id, coin=e.coin, era_tag=e.era_tag, fill_t=e.fill_t)
                for m in MS:
                    Tm = T0 + m * 60 * NS
                    r = dict(rec0, m=m)
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
                        sl = first_x_slip(q, X, O, px, cu_in, cs_in, oid)
                        r[f"n_{X}"] = int(len(sl))
                        r[f"slip_{X}"] = float(np.median(sl)) if len(sl) else np.nan
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
                    if m == 0:
                        pool_ids.update(idx.tolist())
                    rows_x.append(r)
                # passive minutes
                for j in range(1, NJ + 1):
                    a0 = T0 + (j - 1) * 60 * NS
                    a1 = a0 + 60 * NS
                    i0, i1 = np.searchsorted(t, a0), np.searchsorted(t, a1)
                    b = i0 - 1
                    r = dict(event_id=e.event_id, j=j, peg_ref=px[b] if b >= 0 else np.nan, n=int(i1 - i0))
                    seg_p, seg_u, seg_t, seg_mb = px[i0:i1], usd[i0:i1], (t[i0:i1] - a0) / NS, mb[i0:i1]
                    r["usd"] = float(seg_u.sum())
                    r["hi"] = float(seg_p.max()) if len(seg_p) else np.nan
                    r["lo"] = float(seg_p.min()) if len(seg_p) else np.nan
                    r["first_px"] = float(seg_p[0]) if len(seg_p) else np.nan
                    r["first_side"] = ("buy" if seg_mb[0] else "sell") if len(seg_p) else ""
                    vol = sz[i0:i1].sum()
                    for nm, tk in (("mod", e.tick_model), ("real", e.tick_real)):
                        peg = r["peg_ref"] + tk
                        ge = seg_p >= peg - 1e-9 * tk
                        gt = seg_p >= peg + tk * (1 - 1e-9)
                        r[f"v_ge_{nm}"] = float(seg_u[ge].sum())
                        r[f"v_gt_{nm}"] = float(seg_u[gt].sum())
                        r[f"v_gtb_{nm}"] = float(seg_u[gt & ~seg_mb].sum())
                        r[f"t_gt_{nm}"] = float(seg_t[gt][0]) if gt.any() else np.nan
                        h, lo_ = r["hi"], r["lo"]
                        if len(seg_p) and h >= peg + tk * (1 - 1e-9):
                            rng = h - lo_
                            frac = 1.0 if rng <= 0 else min(1.0, (h - peg) / rng)
                            r[f"cap_u_{nm}"] = float(vol * frac * 0.5 * (peg + h))
                        else:
                            r[f"cap_u_{nm}"] = 0.0
                    rows_p.append(r)
            # pooled slippage per coin-era (distinct orders)
            if pool_ids:
                e0 = ev_by_w[w].iloc[0]
                key = (e0.coin, e0.era_tag)
                ids = np.array(sorted(pool_ids))
                for X in XS:
                    q = ids[O["usd"][ids] >= X]
                    sl = first_x_slip(q, X, O, px, cu_in, cs_in, oid)
                    pool.setdefault((key, X), []).append(sl)
        print(f"{os.path.basename(f)}: {len(T):,} prints; {len(rows_x)} exit rows so far; "
              f"{time.time() - t_start:.0f}s", flush=True)
    X_ = pd.DataFrame(rows_x)
    P_ = pd.DataFrame(rows_p)
    C_ = []
    for ((coin, era), X), lst in pool.items():
        sl = np.concatenate(lst) if lst else np.array([])
        C_.append(dict(coin=coin, era_tag=era, X=X, n=len(sl),
                       med=float(np.median(sl)) if len(sl) else np.nan,
                       p75=float(np.percentile(sl, 75)) if len(sl) else np.nan,
                       p90=float(np.percentile(sl, 90)) if len(sl) else np.nan,
                       mean=float(np.mean(sl)) if len(sl) else np.nan))
    C_ = pd.DataFrame(C_).sort_values(["era_tag", "coin", "X"])
    X_.to_csv(os.path.join(LV5, "prints_rt2_exit.csv"), index=False)
    P_.to_csv(os.path.join(LV5, "prints_rt2_passive.csv"), index=False)
    C_.to_csv(os.path.join(LV5, "prints_rt2_coin.csv"), index=False)
    miss = E[(E.window_id < 0) | ~E.window_id.isin(list(seen_w))]
    print(f"{n_prints:,} prints in {len(files)} files; {X_.event_id.nunique()} events with prints; "
          f"{len(miss)} events without prints; {time.time() - t_start:.0f}s")
    if len(X_):
        x0 = X_[X_.m == 0]
        print(x0.groupby("era_tag")[["hs_bp", "roll_hs_bp", "n_sell_orders", "max_sell_usd", "slip_1000",
                                      "slip_5000", "slip_20000"]].median().round(3).to_string())
        print(P_[["v_gt_mod", "cap_u_mod", "v_gt_real", "cap_u_real"]].describe().round(1).to_string())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "rt2")
