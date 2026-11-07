#!/usr/bin/env python3
"""H9 (MC) Step 1: mechanism check on DEV days only (reports/hunt/h9mc/SPEC.md). Runs on GitHub Actions.

Definitions, fixed before any Step-1 number was computed (this file is committed before it first runs):
- Days: DEV trading days = weekdays with US holidays dropped (hcommon.US_HOLIDAYS), from each perp's first full day
  through 2026-05-31. Nothing dated 2026-06-01 or later enters any statistic here (asserted).
- Windows on the ET clock (America/New_York, DST-aware): 4 pm = [15:30, 16:30); control = [13:30, 14:30).
- Measure 1, aggressive-sell share = USD volume of prints whose maker side is BUY (an aggressive seller hit a bid)
  divided by all USD volume.
  T1 (primary): per day, pool the USD volume of every coin with prints in both windows into one share per window;
  d1 = share(4 pm) - share(control); paired t = mean(d1) / sd(d1) * sqrt(days). Pass if t >= 2.
- Measure 2, basis residual e (H1's definition): b = log(perp close / spot close) on minutes where both traded;
  bbar = trailing 24 h median of b known at t-1; e = b - bbar. Sub-windows [15:55, 16:05) and, shifted by the same
  two hours, [13:55, 14:05). Per coin-day: mean e over valid minutes in each sub-window (at least one in each).
  T2 (primary): per day, the mean across coins of (mean e at 4 pm - mean e in control) weighted by the coin's USD
  perp volume in the two Step-1 windows that day (1-minute candles); paired t across days. Pass if t <= -2.
- Measure 3 (information): return gap = perp log return - spot log return over [15:45, 16:05) minus the same over
  [13:45, 14:05); prices = the last 1-minute close before each boundary, at most 15 minutes stale; pooled as T2.
- Step 2 is built only if T1 and T2 both pass. Everything else below (equal-weighted and z versions, per coin, per
  month, per weekday, minute profiles, R1's 16:00-16:02 check, weekend/holiday placebo days) is information only.
Writes reports/hunt/h9mc/step1.json, step1_days.parquet, step1_coin.csv, step1_month.csv, step1_weekday.csv,
step1_profile.csv, step1_coverage.csv.
"""
import glob
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hcommon as H  # noqa: E402
import common  # noqa: E402

OUT = os.path.join(common.ROOT, "reports", "hunt", "h9mc")
DATA = os.path.join(common.ROOT, "data", "hunt", "h9mc")
HOLD0 = pd.Timestamp("2026-06-01")
CUT = H.et_to_utc(HOLD0, "00:00")            # ET midnight of the first HOLD day, in naive UTC
W4, WC = (930, 990), (810, 870)              # [15:30, 16:30) and [13:30, 14:30) in ET minutes of the day
S4, SC = (955, 965), (835, 845)              # [15:55, 16:05) and [13:55, 14:05)
G4, GC = (945, 965), (825, 845)              # return-gap windows [15:45, 16:05) and [13:45, 14:05)
R1_4, R1_C = (960, 962), (840, 842)          # R1's check: 16:00-16:02 vs 14:00-14:02
MIN_PRINTS_EW = 20                           # equal-weighted (information) versions: prints per window per coin


def et_parts(ts):
    et = pd.DatetimeIndex(ts).tz_localize("UTC").tz_convert(H.ET)
    return et.tz_localize(None).normalize(), et.hour * 60 + et.minute


def tstat(x):
    x = pd.Series(x).dropna()
    n = len(x)
    if n < 3 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / x.std(ddof=1) * math.sqrt(n))


def nw_t(x, lags=5):
    x = pd.Series(x).dropna().to_numpy(float)
    n = len(x)
    if n < 10:
        return float("nan")
    u = x - x.mean()
    v = u @ u / n
    for k in range(1, lags + 1):
        v += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / n
    return float(x.mean() / math.sqrt(v / n)) if v > 0 else float("nan")


def summ(x, scale=1.0):
    x = pd.Series(x).dropna()
    return dict(mean=float(x.mean() * scale) if len(x) else float("nan"), t=tstat(x), t_nw=nw_t(x), n=int(len(x)),
                share_pos=float((x > 0).mean()) if len(x) else float("nan"))


def wmean(df, val, w):
    d = df.dropna(subset=[val])
    d = d[d[w] > 0]
    return (d[val] * d[w]).groupby(level="day").sum() / d[w].groupby(level="day").sum()


# ------------------------------------------------------------------ measure 1: aggressive-sell share (prints)
def load_aggs():
    parts = []
    for f in sorted(glob.glob(os.path.join(DATA, "agg_*.parquet"))):
        x = pd.read_parquet(f)
        x["minute"] = pd.to_datetime(x["minute"])
        x = x[x.minute < CUT]
        if len(x):
            parts.append(x)
    a = pd.concat(parts, ignore_index=True)
    a["day"], a["hm"] = et_parts(a["minute"])
    assert a.day.max() < HOLD0
    a["trading"] = H.trading_mask(a.day)
    return a


def win_sum(a, w, win):
    x = a[(a.win == win) & (a.hm >= w[0]) & (a.hm < w[1])]
    return x.groupby(["coin", "day"])[["usd", "agg_usd", "n"]].sum()


def measure1(a):
    j = win_sum(a, W4, 1).join(win_sum(a, WC, 0), lsuffix="_4", rsuffix="_c", how="inner")
    j = j[(j.usd_4 > 0) & (j.usd_c > 0)].copy()
    j["share_4"], j["share_c"] = j.agg_usd_4 / j.usd_4, j.agg_usd_c / j.usd_c
    j["d1"] = j.share_4 - j.share_c
    g = j.groupby(level="day")[["agg_usd_4", "usd_4", "agg_usd_c", "usd_c"]].sum()
    pooled = g.agg_usd_4 / g.usd_4 - g.agg_usd_c / g.usd_c
    ok = j[(j.n_4 >= MIN_PRINTS_EW) & (j.n_c >= MIN_PRINTS_EW)]
    ew = ok.d1.groupby(level="day").mean()
    r1 = win_sum(a, R1_4, 1).join(win_sum(a, R1_C, 0), lsuffix="_4", rsuffix="_c", how="inner")
    r1 = r1[(r1.usd_4 > 0) & (r1.usd_c > 0)]
    g1 = r1.groupby(level="day")[["agg_usd_4", "usd_4", "agg_usd_c", "usd_c"]].sum()
    r1d = g1.agg_usd_4 / g1.usd_4 - g1.agg_usd_c / g1.usd_c
    vol_ratio = np.log(g.usd_4 / g.usd_c)
    return j, pooled, ew, r1d, vol_ratio, g


# ------------------------------------------------------------------ measures 2 and 3: basis residual, return gap
def coin_basis(coin):
    bf = H.basis_frame(coin, end=CUT)
    day, hm = et_parts(bf.index)
    bf["day"], bf["hm"] = day, hm
    assert bf.day.max() < HOLD0
    bf["z"] = bf.e / bf.sig
    p = common.load_perp(coin)
    p = p[p.index < CUT]
    pday, phm = et_parts(p.index)
    usd = p.volume * H.px_coin(coin, p.close)
    inwin = ((phm >= W4[0]) & (phm < W4[1])) | ((phm >= WC[0]) & (phm < WC[1]))
    w = usd[inwin].groupby(pday[inwin]).sum()
    s = common.load_minute(coin)
    s = s[s.index < CUT]
    rows = []
    for (lo, hi), tag in ((S4, "4"), (SC, "c")):
        m = (bf.hm >= lo) & (bf.hm < hi)
        g = bf[m].groupby("day")
        rows.append(pd.DataFrame({f"e_{tag}": g.e.mean(), f"z_{tag}": g.z.mean(), f"ne_{tag}": g.e.count()}))
    out = pd.concat(rows, axis=1)
    days = sorted(set(pday))
    gaps = {}
    for (lo, hi), tag in ((G4, "4"), (GC, "c")):
        gp = []
        for d in days:
            b0 = H.et_to_utc(d, f"{lo // 60:02d}:{lo % 60:02d}")
            b1 = H.et_to_utc(d, f"{hi // 60:02d}:{hi % 60:02d}")
            vals = []
            for ser in (p.close, s.close):
                v = []
                for B in (b0, b1):
                    i = ser.index.searchsorted(B, side="left") - 1
                    ok = i >= 0 and ser.index[i] >= B - pd.Timedelta(minutes=15)
                    v.append(float(ser.iloc[i]) if ok else np.nan)
                vals.append(math.log(v[1] / v[0]) if np.isfinite(v).all() else np.nan)
            gp.append(vals[0] - vals[1])
        gaps[f"gap_{tag}"] = pd.Series(gp, index=pd.DatetimeIndex(days))
    out = out.join(pd.DataFrame(gaps), how="outer")
    out["w"] = w.reindex(out.index).fillna(0.0)
    out["coin"] = coin
    out.index.name = "day"
    prof = bf[((bf.hm >= W4[0]) & (bf.hm < 1050)) | ((bf.hm >= WC[0]) & (bf.hm < WC[1]))]
    prof = prof[H.trading_mask(prof.day)]
    pr = prof.groupby("hm").e.agg(["mean", "count"])
    pr["coin"] = coin
    return out.reset_index().set_index(["coin", "day"]), pr.reset_index()


def main():
    os.makedirs(OUT, exist_ok=True)
    a = load_aggs()
    res = dict(definitions=__doc__.split("Definitions, fixed")[1].split("Writes")[0].strip())
    tr = a[a.trading]
    pl = a[~a.trading]
    j, d1, d1_ew, r1d, vr, g = measure1(tr)
    res["T1_aggsell_pooled"] = summ(d1)
    res["T1_aggsell_pooled"]["share_4pm"] = float((g.agg_usd_4.sum() / g.usd_4.sum()))
    res["T1_aggsell_pooled"]["share_ctrl"] = float((g.agg_usd_c.sum() / g.usd_c.sum()))
    res["T1_info_equal_weighted"] = summ(d1_ew)
    res["T1_info_R1_1600_1602"] = summ(r1d)
    res["info_log_volume_ratio_4pm_vs_ctrl"] = summ(vr)
    jp, d1p, _, _, _, _ = measure1(pl)
    res["placebo_weekend_holiday_T1"] = summ(d1p)

    B, P = [], []
    for coin in H.COINS:
        if not os.path.exists(os.path.join(common.DATA, "cfm", f"{coin}.parquet")) or H.launch_day(coin) >= HOLD0:
            continue
        b, pr = coin_basis(coin)
        B.append(b)
        P.append(pr)
        print("basis", coin, len(b), flush=True)
    B = pd.concat(B)
    B["trading"] = H.trading_mask(B.index.get_level_values("day"))
    B["d2"] = (B.e_4 - B.e_c) * 1e4
    B["dz"] = B.z_4 - B.z_c
    B["d3"] = (B.gap_4 - B.gap_c) * 1e4
    Bt, Bp = B[B.trading], B[~B.trading]
    d2 = wmean(Bt, "d2", "w")
    res["T2_basis_vw_bp"] = summ(d2)
    res["T2_basis_vw_bp"]["e_4pm_bp"] = float(wmean(Bt.assign(x=Bt.e_4 * 1e4), "x", "w").mean())
    res["T2_basis_vw_bp"]["e_ctrl_bp"] = float(wmean(Bt.assign(x=Bt.e_c * 1e4), "x", "w").mean())
    res["T2_info_equal_weighted_bp"] = summ(Bt.d2.groupby(level="day").mean())
    res["T2_info_z_equal_weighted"] = summ(Bt.dz.groupby(level="day").mean())
    d3 = wmean(Bt, "d3", "w")
    res["T3_info_return_gap_vw_bp"] = summ(d3)
    res["placebo_weekend_holiday_T2"] = summ(wmean(Bp, "d2", "w"))
    res["pass_T1"] = bool(res["T1_aggsell_pooled"]["t"] >= 2)
    res["pass_T2"] = bool(res["T2_basis_vw_bp"]["t"] <= -2)
    res["pass_step1"] = res["pass_T1"] and res["pass_T2"]

    days = pd.DataFrame({"d1_aggsell": d1, "d1_ew": d1_ew, "d2_basis_bp": d2, "d3_gap_bp": d3,
                         "log_vol_ratio": vr}).sort_index()
    assert days.index.max() < HOLD0
    days.to_parquet(os.path.join(OUT, "step1_days.parquet"))

    # per coin (information)
    rows = []
    for coin in H.COINS:
        r = dict(coin=coin)
        if coin in j.index.get_level_values("coin"):
            x = j.loc[coin]
            r.update(days_T1=len(x), share_4pm=float(x.agg_usd_4.sum() / x.usd_4.sum()),
                     share_ctrl=float(x.agg_usd_c.sum() / x.usd_c.sum()), d1_mean=float(x.d1.mean()), d1_t=tstat(x.d1),
                     usd_4pm_day=float(x.usd_4.mean()), usd_ctrl_day=float(x.usd_c.mean()))
        if coin in Bt.index.get_level_values("coin"):
            y = Bt.loc[coin]
            r.update(days_T2=int(y.d2.notna().sum()), d2_mean_bp=float(y.d2.mean()), d2_t=tstat(y.d2),
                     dz_mean=float(y.dz.mean()), dz_t=tstat(y.dz), d3_mean_bp=float(y.d3.mean()), d3_t=tstat(y.d3))
        rows.append(r)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "step1_coin.csv"), index=False, float_format="%.5g")

    # by month and by weekday (information; the SPEC asks whether the effect changes over time)
    for key, fn, name in (("month", lambda i: i.to_period("M").astype(str), "step1_month.csv"),
                          ("weekday", lambda i: i.day_name(), "step1_weekday.csv")):
        rows = []
        for k, grp in days.groupby(fn(days.index)):
            rows.append({key: k, "days": len(grp),
                         "d1_mean": grp.d1_aggsell.mean(), "d1_t": tstat(grp.d1_aggsell),
                         "d2_mean_bp": grp.d2_basis_bp.mean(), "d2_t": tstat(grp.d2_basis_bp),
                         "d3_mean_bp": grp.d3_gap_bp.mean(), "d3_t": tstat(grp.d3_gap_bp),
                         "log_vol_ratio": grp.log_vol_ratio.mean()})
        pd.DataFrame(rows).to_csv(os.path.join(OUT, name), index=False, float_format="%.5g")
        res[f"by_{key}"] = rows

    # minute profiles (information): pooled aggressive-sell share and volume by ET minute; mean e by group
    x = tr[((tr.win == 1) & (tr.hm >= W4[0]) & (tr.hm < 1050)) | ((tr.win == 0) & (tr.hm >= WC[0]) & (tr.hm < WC[1]))]
    pf = x.groupby("hm")[["agg_usd", "usd"]].sum()
    pf["aggsell_share"] = pf.agg_usd / pf.usd
    pf["usd_per_day"] = pf.usd / tr.day.nunique()
    P = pd.concat(P)
    P["grp"] = np.where(P.coin.isin(H.MAJORS), "e_bp_btc_eth", "e_bp_alts")
    pe = P.assign(s=P["mean"] * P["count"]).groupby(["grp", "hm"])[["s", "count"]].sum()
    pe = (pe.s / pe["count"] * 1e4).unstack("grp")
    prof = pf[["aggsell_share", "usd_per_day"]].join(pe, how="outer")
    prof.index = [f"{h // 60:02d}:{h % 60:02d}" for h in prof.index]
    prof.to_csv(os.path.join(OUT, "step1_profile.csv"), index_label="et_minute", float_format="%.5g")

    # print coverage against 1-minute candles (DEV days only)
    L = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(DATA, "log_*.parquet")))])
    L["day"] = pd.to_datetime(L["day"])
    L = L[(L.day < HOLD0) & H.trading_mask(L.day)]
    L["gap"] = (L.contracts - L.candle_contracts).abs() / L.candle_contracts.clip(lower=1e-9)
    cov = L.groupby("coin").agg(windows=("day", "size"), prints=("prints", "sum"), contracts=("contracts", "sum"),
                                candle_contracts=("candle_contracts", "sum"), errors=("err", lambda e: int((e != "").sum())),
                                lost_seconds=("lost_seconds", "sum"),
                                windows_off_1pct=("gap", lambda g: int((g > 0.01).sum())))
    cov["coverage"] = cov.contracts / cov.candle_contracts
    cov.to_csv(os.path.join(OUT, "step1_coverage.csv"), float_format="%.6g")
    res["coverage_total"] = float(cov.contracts.sum() / cov.candle_contracts.sum())
    res["n_dev_trading_days"] = int(len(d1))

    json.dump(res, open(os.path.join(OUT, "step1.json"), "w"), indent=1, default=float)
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("by_") and k != "definitions"}, indent=1,
                     default=float))


if __name__ == "__main__":
    main()
