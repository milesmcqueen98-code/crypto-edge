#!/usr/bin/env python3
"""H4 (NL) step 1: candidate fills of the resting bid for every listing (reports/hunt/h4nl/SPEC.md).

For each listing (data/hunt/h4nl/m1/*.parquet, 1-minute Exchange candles from the first trading day for 32 days):
- t0 = the first 1-minute candle with volume; minutes on a full grid (no-trade minutes: volume 0, close carried);
- F_t = VWAP of minutes t-60..t-1 (typical price (H+L+C)/3), sigma_t = std of 1-minute log returns over the trailing
  min(1440, minutes since t0) minutes up to t-1, x sqrt(60); both known at t-1;
- level_k = F exp(-k sigma) floored to the tick (quote_increment), k in (3, 4, 6);
- candidate fill at minute t: the minute traded, opened above the level and its low traded through it by >= 1 tick
  (prices sit on the tick grid; tolerances of 0.5 / 0.02 tick absorb float32 storage),
  t0 + 2 h <= t < t0 + 31 days;
- through-volume (USD): the candle volume spread evenly over each range, below the level, from the fill minute while
  the low stays below the level (<= 15 more minutes; a no-trade minute ends it);
- take-profit TP = level exp(0.6 ln(F / level)) ceiled to the tick; hit = first minute in t+1..t+H whose high is >= TP
  + 1 tick; TP capacity = USD volume above TP over t+1..t+H; time exit = the open of the first traded minute at or
  after t+H+1 (H in (30, 60));
- AI features known at t-1 (SPEC): days since listing, drawdown from the first-day VWAP (to date while in day 1),
  trailing-24h volume vs day 1 (to date), BTC 60-minute move, sigma, k-depth in bp.
Only minutes before END are read (dev: END = 2026-06-01, so no HOLD minute is ever touched before the freeze).

  python scripts/hunt/h4nl/precompute.py dev        -> data/hunt/h4nl/cand_dev.parquet, listings_dev.csv
  python scripts/hunt/h4nl/precompute.py full       -> cand_full.parquet, listings_full.csv (after the freeze only)
"""
import glob
import os
import sys

import numba as nb
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

DATA = os.path.join(ROOT, "data", "hunt", "h4nl")
END = {"dev": pd.Timestamp("2026-06-01"), "full": pd.Timestamp("2026-11-06")}
KS = (3.0, 4.0, 6.0)
HS = (30, 60)
WARM, WIN_MAX, L_F, L_SIG, SCAN = 120, 31 * 1440, 60, 1440, 15
LIQ_USD = 1e6


@nb.njit(cache=True)
def scans(cand, lvl, tp, o, h, lo, v, tick, H, n):
    """For each candidate minute: through-volume USD below lvl; TP first-hit offset, TP capacity USD over t+1..t+H;
    exit offset (first traded minute >= t+H+1) and its open."""
    m = len(cand)
    thr = np.zeros(m)
    tp_off = np.full(m, -1)
    tp_cap = np.zeros(m)
    x_off = np.full(m, -1)
    x_px = np.full(m, np.nan)
    for q in range(m):
        t = cand[q]
        L = lvl[q]
        for j in range(SCAN + 1):
            i = t + j
            if i >= n or not (lo[i] < L) or v[i] <= 0:      # NaN low (no trade) or low >= level ends the scan
                break
            rng = h[i] - lo[i]
            frac = 1.0 if rng <= 0 else min(1.0, (L - lo[i]) / rng)
            thr[q] += v[i] * frac * 0.5 * (L + lo[i])
        T = tp[q]
        for i in range(t + 1, min(t + H + 1, n)):
            if v[i] <= 0:
                continue
            if h[i] >= T + 0.98 * tick:                     # traded through the take-profit by >= 1 tick
                if tp_off[q] < 0:
                    tp_off[q] = i - t
                rng = h[i] - lo[i]
                frac = 1.0 if rng <= 0 else min(1.0, (h[i] - T) / rng)
                tp_cap[q] += v[i] * frac * 0.5 * (T + h[i])
        for i in range(t + H + 1, n):
            if v[i] > 0:
                x_off[q] = i - t
                x_px[q] = o[i]
                break
    return thr, tp_off, tp_cap, x_off, x_px


def btc_close():
    """BTC 1-minute close (minutes with trades, as common.load_minute), only the columns needed (memory)."""
    parts = []
    for src in ("minute_early", "minute"):
        d = pd.read_parquet(os.path.join(common.DATA, src, "BTC.parquet"), columns=["ts", "close", "volume"])
        d = d[(d.volume > 0) & (d.ts >= pd.Timestamp("2021-12-25"))].drop_duplicates("ts").set_index("ts")["close"]
        parts.append(d)
    c = pd.concat(parts).astype(np.float64)
    c = c[~c.index.duplicated()].sort_index()
    idx = pd.date_range(c.index.min(), c.index.max(), freq="min")
    return c.reindex(idx).ffill()


def one_listing(pid, d, tick, end, btc):
    d = d[(d.volume > 0) & (d.ts < end)]
    if d.empty:
        return None, None
    t0 = d.ts.iloc[0]
    g_end = min(end, t0 + pd.Timedelta(minutes=WIN_MAX + 3 * 1440))
    idx = pd.date_range(t0, g_end, freq="min", inclusive="left")
    n = len(idx)
    pos = ((d.ts - t0) // pd.Timedelta(minutes=1)).to_numpy()
    keep = pos < n
    pos = pos[keep]
    o = np.full(n, np.nan)
    h = o.copy()
    lo = o.copy()
    c = o.copy()
    v = np.zeros(n)
    o[pos], h[pos], lo[pos], c[pos] = (d[k].to_numpy(np.float64)[keep] for k in ("open", "high", "low", "close"))
    v[pos] = d.volume.to_numpy(np.float64)[keep]
    cf = pd.Series(c).ffill().to_numpy()
    tpx = np.where(v > 0, (h + lo + c) / 3.0, 0.0)
    pv = tpx * v
    # F_t: VWAP over t-60..t-1
    cpv, cv = np.concatenate([[0.0], np.cumsum(pv)]), np.concatenate([[0.0], np.cumsum(v)])
    t = np.arange(n)
    a = np.maximum(t - L_F, 0)
    sv = cv[t] - cv[a]
    with np.errstate(invalid="ignore", divide="ignore"):
        F = np.where(sv > 0, (cpv[t] - cpv[a]) / sv, np.nan)
    # sigma_t: std of r_j = ln(cf_j / cf_{j-1}), j in [max(1, t-1440), t-1], x sqrt(60)
    r = np.zeros(n)
    r[1:] = np.log(cf[1:] / cf[:-1])
    c1, c2 = np.concatenate([[0.0], np.cumsum(r)]), np.concatenate([[0.0], np.cumsum(r * r)])
    a2 = np.maximum(t - L_SIG, 1)
    k_n = (t - a2).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        s1, s2 = c1[t] - c1[a2], c2[t] - c2[a2]
        var = (s2 - s1 * s1 / k_n) / (k_n - 1)
        sig = np.where(k_n >= 2, np.sqrt(np.maximum(var, 0.0)) * np.sqrt(60.0), np.nan)
    # liquidity filter: cumulative USD volume of day 1 through t-1 reaches $1M (known at t-1); day-1 total
    cum = cpv                                                    # cum[m] = USD volume of minutes 0..m-1
    day1_usd = float(pv[:1440].sum())
    hit = np.nonzero(cum[1:1441] >= LIQ_USD)[0]                  # cum[m] = USD volume of minutes 0..m-1
    liq_from = int(hit[0] + 1) if len(hit) else -1
    # features known at t-1
    vw1_num = np.concatenate([[0.0], np.cumsum(pv[:1440])])
    vw1_den = np.concatenate([[0.0], np.cumsum(v[:1440])])
    m1 = np.minimum(t, 1440)
    with np.errstate(invalid="ignore", divide="ignore"):
        vwap_d1 = np.where(vw1_den[m1] > 0, vw1_num[m1] / vw1_den[m1], np.nan)
        usd24 = cpv[t] - cpv[np.maximum(t - 1440, 0)]
        vol_vs_d1 = usd24 / np.where(vw1_num[m1] > 0, vw1_num[m1], np.nan)
    cf_prev = np.concatenate([[np.nan], cf[:-1]])
    bt = btc.reindex(idx).to_numpy()
    bt1 = np.concatenate([[np.nan], bt[:-1]])
    bt61 = np.concatenate([np.full(61, np.nan), bt[:-61]])
    rows = []
    valid_t = (t >= WARM) & (t < WIN_MAX) & np.isfinite(F) & np.isfinite(sig) & (sig > 0)
    for k in KS:
        with np.errstate(invalid="ignore"):
            lvl = np.floor(F * np.exp(-k * sig) / tick + 1e-9) * tick
            fill = valid_t & (v > 0) & (o >= lvl + 0.5 * tick) & (lo <= lvl - 0.98 * tick) & (lvl > 0)
        cand = np.nonzero(fill)[0]
        if len(cand) == 0:
            continue
        L = lvl[cand]
        tp = np.ceil(L * np.exp(0.6 * np.log(F[cand] / L)) / tick - 1e-9) * tick
        rec = dict(pid=pid, ts=idx[cand], k=k, m=cand, lvl=L, F=F[cand], sig=sig[cand], tp=tp,
                   f_days=cand / 1440.0, f_dd_d1=np.log(cf_prev[cand] / vwap_d1[cand]), f_vol_d1=vol_vs_d1[cand],
                   f_btc60=np.log(bt1[cand] / bt61[cand]), f_depth_bp=1e4 * np.log(F[cand] / L))
        for H in HS:
            thr, tpo, tpc, xo, xp = scans(cand.astype(np.int64), L, tp, o, h, lo, v, float(tick), H, n)
            rec["thr_usd"] = thr
            rec[f"tp_off{H}"], rec[f"tp_cap{H}"], rec[f"x_off{H}"], rec[f"x_px{H}"] = tpo, tpc, xo, xp
        rows.append(pd.DataFrame(rec))
    info = dict(pid=pid, t0=t0, n_min=int((v > 0).sum()), grid_end=idx[-1], day1_usd=day1_usd,
                liq_from=(t0 + pd.Timedelta(minutes=liq_from)) if liq_from >= 0 else pd.NaT,
                px0=float(o[0]), med_tick_bp=float(np.nanmedian(1e4 * tick / cf[: min(n, WIN_MAX)])))
    return (pd.concat(rows, ignore_index=True) if rows else None), info


def main(mode):
    end = END[mode]
    L = pd.read_csv(os.path.join(DATA, "listings_pre.csv"), parse_dates=["first_day"])
    ticks = dict(zip(L.pid, L.tick))
    btc = btc_close()
    out, infos = [], []
    for f in sorted(glob.glob(os.path.join(DATA, "m1", "m1_*.parquet"))):
        M = pd.read_parquet(f)
        M["pid"] = M["pid"].astype(str)
        for pid, d in M.groupby("pid", sort=False):
            if pid not in ticks:
                continue
            cnd, info = one_listing(pid, d.sort_values("ts"), ticks[pid], end, btc)
            if info is not None:
                infos.append(info)
            if cnd is not None:
                out.append(cnd)
        print(f"{os.path.basename(f)}: {M.pid.nunique()} listings", flush=True)
        del M
    C = pd.concat(out, ignore_index=True)
    for col in C.columns:
        if C[col].dtype == np.float64 and col not in ("lvl", "F", "tp", "x_px30", "x_px60"):
            C[col] = C[col].astype(np.float32)
    C.to_parquet(os.path.join(DATA, f"cand_{mode}.parquet"), index=False, compression="zstd")
    I = pd.DataFrame(infos).merge(L[["pid", "base", "name", "status", "tick", "first_day", "new_at"]], on="pid")
    I.to_csv(os.path.join(DATA, f"listings_{mode}.csv"), index=False)
    print(f"{mode}: {len(I)} listings with trades before {end.date()}, {len(C)} candidate rows")


if __name__ == "__main__":
    main(sys.argv[1])
