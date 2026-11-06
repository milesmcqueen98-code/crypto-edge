#!/usr/bin/env python3
"""Maker round analysis (pre-registered in reports/maker_prereg.md).

  python scripts/maker_analyze.py select     dev days only -> reports/maker/selection.json
  python scripts/maker_analyze.py final      dev + hold-out -> reports/maker/summary.md, summary.json

Daily P&L per config = sum over coins of marked-to-mid P&L minus the half spread to flatten end-of-day
inventory, minus fees (maker fee x traded notional, taker fee x end-of-day inventory). Daily excess
return = P&L / capital - T-bill. Sharpe = mean/sd x sqrt(365); t = mean/sd x sqrt(N days).
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from edge import book  # noqa: E402

OUT = os.path.join(ROOT, "reports", "maker")
DEV_END = "2025-06-30"
CAP = {"10k": 10_000.0, "100k": 100_000.0}
# (30-day volume threshold USD, maker, taker): US schedule after 16 Sep 2026; unlisted tiers at the next-lower listed one
TIERS = [(0, .0050, .0090), (10e3, .0035, .0075), (50e3, .0015, .0030), (250e3, .0010, .0015),
         (500e3, .0006, .00125), (20e6, .0001, .0005), (50e6, 0.0, .00035), (250e6, 0.0, .0002)]
N_PRIOR = 470
MODES = {0: "S0 symmetric", 1: "S1 skewed", 2: "S2 passive tracker"}
HORIZONS = [1, 10, 60, 300, 900]


def tier(vol30):
    out = TIERS[0]
    for t in TIERS:
        if vol30 >= t[0]:
            out = t
    return out


def load():
    files = [f for f in glob.glob(os.path.join(OUT, "raw", "*.csv")) if not f.endswith("_paths.csv.gz")]
    df = pd.concat([pd.read_csv(f) for f in sorted(files)], ignore_index=True)
    df["day"] = pd.to_datetime(df["day"])
    df["period"] = np.where(df["day"] <= DEV_END, "dev", "holdout")
    df["notional"] = df.buy_usd + df.sell_usd
    return df


def daily(df, key):
    """One row per (config..., day): gross P&L after flattening, traded notional, end-of-day inventory."""
    g = df.groupby(key + ["day", "period"]).agg(gross=("gross_pnl", "sum"), hs=("eod_halfspread_cost", "sum"),
                                                 V=("notional", "sum"), eod=("eod_inv_usd", lambda s: s.abs().sum()),
                                                 n=("n_fills", "sum")).reset_index()
    g["gross_flat"] = g.gross - g.hs
    return g


def net(g, maker, taker, mult=1.0):
    return g.gross_flat - mult * (maker * g.V + taker * g.eod)


def stats(pnl, days, cap):
    r = pnl / cap - book.rf_daily(pd.DatetimeIndex(days)).to_numpy()
    n = len(r)
    mu, sd = r.mean(), r.std(ddof=1)
    yrs = pd.Series(pnl.to_numpy(), index=pd.DatetimeIndex(days)).groupby(pd.DatetimeIndex(days).year).sum()
    return dict(n=n, mean_pnl=float(pnl.mean()), sharpe=float(mu / sd * np.sqrt(365)) if sd > 0 else np.nan,
                t=float(mu / sd * np.sqrt(n)) if sd > 0 else np.nan, worst_day=float(pnl.min()),
                win_days=float((pnl > 0).mean()), years={int(k): float(v) for k, v in yrs.items()})


def dsr(r, sr_trials, n_trials):
    r = np.asarray(r)
    sr = r.mean() / r.std(ddof=1)
    emc = 0.5772156649
    sr0 = np.std(sr_trials, ddof=1) * ((1 - emc) * norm.ppf(1 - 1 / n_trials) + emc * norm.ppf(1 - 1 / (n_trials * np.e)))
    den = np.sqrt(1 - skew(r) * sr + (kurtosis(r, fisher=False) - 1) / 4 * sr ** 2)
    return float(norm.cdf((sr - sr0) * np.sqrt(len(r) - 1) / den)), float(sr0 * np.sqrt(365))


def markouts(df):
    k = ["size", "lat", "qmodel", "mode", "period"]
    s = df.groupby(k).sum(numeric_only=True)
    out = pd.DataFrame(index=s.index)
    out["fills_per_day"] = s.n_fills / df.groupby(k).day.nunique()
    out["notional_per_day"] = s.notional / df.groupby(k).day.nunique()
    out["spread_bp"] = s.spread_usd / s.notional * 1e4
    for h in HORIZONS:
        out[f"rs_{h}s_bp"] = s[f"rs_{h}s_usd"] / s.notional * 1e4
    out["aligned_share"] = s.aligned_usd / s.notional
    out["aligned_rs900_bp"] = s.aligned_rs900_usd / s.aligned_usd * 1e4
    out["opposed_rs900_bp"] = s.opposed_rs900_usd / (s.notional - s.aligned_usd) * 1e4
    out["through_share"] = s.n_through / s.n_fills
    out["cross_share"] = s.n_cross / s.n_fills
    out["rejects_per_new"] = s.n_rej / s.n_new
    return out.reset_index()


def per_day_markout_t(df, cfg, h=60):
    """t-stat of the daily realized spread (bp) across days, one config, coins pooled."""
    d = df[(df["size"] == cfg["size"]) & (df.lat == cfg["lat"]) & (df.qmodel == cfg["qmodel"]) & (df["mode"] == cfg["mode"])]
    g = d.groupby("day").agg(u=(f"rs_{h}s_usd", "sum"), n=("notional", "sum"))
    x = (g.u / g.n * 1e4).dropna()
    return float(x.mean()), float(x.mean() / x.std(ddof=1) * np.sqrt(len(x)))


def select():
    df = load()
    df = df[df.period == "dev"]
    g = daily(df, ["size", "lat", "qmodel", "mode"])
    rows = []
    for (size, lat, qm, mode), x in g.groupby(["size", "lat", "qmodel", "mode"]):
        st0 = stats(net(x, 0.0, TIERS[6][2]), x.day, CAP[size])
        vol30 = 30 * x.V.mean()
        tr = tier(vol30)
        stt = stats(net(x, tr[1], tr[2]), x.day, CAP[size])
        rows.append(dict(size=size, lat=lat, qmodel=qm, mode=mode, days=len(x), V_day=x.V.mean(),
                         gross_day=x.gross_flat.mean(), breakeven_maker_bp=x.gross_flat.sum() / x.V.sum() * 1e4,
                         sharpe_fee0=st0["sharpe"], t_fee0=st0["t"], tier_maker_bp=tr[1] * 1e4,
                         sharpe_tier=stt["sharpe"], t_tier=stt["t"]))
    tab = pd.DataFrame(rows)
    tab.to_csv(os.path.join(OUT, "dev_table.csv"), index=False)
    base = tab[(tab["size"] == "10k") & (tab.lat == "base") & (tab.qmodel == 0)].sort_values("sharpe_fee0", ascending=False)
    pick = int(base.iloc[0]["mode"])
    sel = dict(selected_mode=pick, selected_name=MODES[pick], rule="highest dev Sharpe at base latency, risk-averse queue, "
               "0% maker fee, $10K book", dev_candidates=base[["mode", "sharpe_fee0", "t_fee0", "breakeven_maker_bp",
                                                                  "V_day", "gross_day"]].to_dict("records"))
    with open(os.path.join(OUT, "selection.json"), "w") as fh:
        json.dump(sel, fh, indent=2, default=float)
    print(tab.round(3).to_string())
    print(json.dumps(sel, indent=2, default=float))
    print(markouts(df).round(3).to_string())


def climb(V, gross, cap, days=90):
    """Equity path from the Intro tier when the strategy trades V per day with gross P&L `gross` per day."""
    hist, eq, out, reached = [], cap, [], None
    for d in range(days):
        vol30 = sum(hist[-30:])
        _, mk, tk = tier(vol30)
        eq += gross - mk * V
        hist.append(V)
        out.append(dict(day=d + 1, vol30=vol30, maker_bp=mk * 1e4, equity=eq))
        if reached is None and vol30 >= 50e6:
            reached = d + 1
    return pd.DataFrame(out), reached


def final():
    df = load()
    sel = json.load(open(os.path.join(OUT, "selection.json")))
    mode = sel["selected_mode"]
    g = daily(df, ["size", "lat", "qmodel", "mode"])
    res = {"selected": sel["selected_name"]}
    lines = [f"# Maker round results\n", f"Selected on dev: **{sel['selected_name']}** ({sel['rule']}).\n"]

    def cfg_rows(size, lat, qm, md, period=None):
        x = g[(g["size"] == size) & (g.lat == lat) & (g.qmodel == qm) & (g["mode"] == md)]
        return x if period is None else x[x.period == period]

    # main table: every config, both periods, fee 0 and attainable tier
    rows = []
    for (size, lat, qm, md), x in g.groupby(["size", "lat", "qmodel", "mode"]):
        for per in ("dev", "holdout"):
            xp = x[x.period == per]
            if xp.empty:
                continue
            tr = tier(30 * xp.V.mean())
            s0 = stats(net(xp, 0.0, TIERS[6][2]), xp.day, CAP[size])
            st = stats(net(xp, tr[1], tr[2]), xp.day, CAP[size])
            rows.append(dict(size=size, lat=lat, qmodel=qm, mode=md, period=per, V_day=xp.V.mean(),
                             gross_bp=xp.gross_flat.sum() / xp.V.sum() * 1e4, sharpe_fee0=s0["sharpe"], t_fee0=s0["t"],
                             tier_maker_bp=tr[1] * 1e4, sharpe_tier=st["sharpe"], t_tier=st["t"],
                             mean_pnl_tier=st["mean_pnl"]))
    tab = pd.DataFrame(rows)
    tab.to_csv(os.path.join(OUT, "all_configs.csv"), index=False)
    mk = markouts(df)
    mk.to_csv(os.path.join(OUT, "markouts.csv"), index=False)

    # selected strategy: hold-out at base latency, risk-averse queue
    x = cfg_rows("10k", "base", 0, mode)
    ho, dv = x[x.period == "holdout"], x[x.period == "dev"]
    tr = tier(30 * ho.V.mean())
    s_fee0 = stats(net(ho, 0.0, TIERS[6][2]), ho.day, 1e4)
    s_tier = stats(net(ho, tr[1], tr[2]), ho.day, 1e4)
    s_all0 = stats(net(x, 0.0, TIERS[6][2]), x.day, 1e4)
    # deflated Sharpe on all 35 days at 0% maker (most generous), trial variance from the 18 $10K runs
    sr_trials = []
    for (lat, qm, md), xx in g[g["size"] == "10k"].groupby(["lat", "qmodel", "mode"]):
        r = net(xx, 0.0, TIERS[6][2]) / 1e4 - book.rf_daily(pd.DatetimeIndex(xx.day)).to_numpy()
        sr_trials.append(r.mean() / r.std(ddof=1))
    r_sel = net(x, 0.0, TIERS[6][2]) / 1e4 - book.rf_daily(pd.DatetimeIndex(x.day)).to_numpy()
    d_sr, sr0 = dsr(r_sel, sr_trials, N_PRIOR + 3)
    # capacity, stress
    x100 = cfg_rows("100k", "base", 0, mode, "holdout")
    tr100 = tier(30 * x100.V.mean())
    s_100 = stats(net(x100, tr100[1], tr100[2]), x100.day, 1e5)
    s_100_0 = stats(net(x100, 0.0, TIERS[6][2]), x100.day, 1e5)
    xs = cfg_rows("10k", "stress", 0, mode, "holdout")
    trs = tier(30 * xs.V.mean())
    s_stress = stats(net(xs, trs[1], trs[2], mult=2.0), xs.day, 1e4)
    s_stress0 = stats(net(xs, 0.0, TIERS[6][2], mult=2.0), xs.day, 1e4)
    mo, mo_t = per_day_markout_t(df[df.period == "holdout"], dict(size="10k", lat="base", qmodel=0, mode=mode), 60)
    cl, reached = climb(ho.V.mean(), ho.gross_flat.mean(), 1e4)
    cl.to_csv(os.path.join(OUT, "fee_climb.csv"), index=False)
    # message rate: sum of per-coin peaks (upper bound) and of per-coin means
    m = df[(df["size"] == "10k") & (df.lat == "base") & (df.qmodel == 0) & (df["mode"] == mode)]
    msg = m.groupby("day").agg(peak=("msg_peak", "sum"), mean=("msg_mean", "sum"))
    # intraday drawdown from 5-minute paths (selected, $10K)
    paths = pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(OUT, "raw", "*_paths.csv.gz"))])
    pp = paths[(paths["size"] == "10k") & (paths["mode"] == mode)].groupby(["day", "minute"]).pnl.sum().reset_index()
    intraday_dd = pp.groupby("day").pnl.apply(lambda s: float((s - s.cummax()).min())).min()

    passes = {
        "holdout gross (0% maker) t >= 3": s_fee0["t"] >= 3,
        "holdout t >= 3 at attainable tier": s_tier["t"] >= 3,
        "deflated Sharpe >= 0.95": d_sr >= 0.95,
        "net Sharpe >= 2.4 at attainable tier": s_tier["sharpe"] >= 2.4,
        "no losing year (attainable tier)": all(v > 0 for v in s_tier["years"].values()),
        "Sharpe >= 2.4 at $100K": s_100["sharpe"] >= 2.4,
        "profitable at 2x fees and 2x latency": s_stress["mean_pnl"] > 0,
    }
    if all(passes.values()):
        verdict = "ADOPT"
    elif passes["holdout t >= 3 at attainable tier"] and passes["no losing year (attainable tier)"]:
        verdict = "PAPER-TRADE"
    else:
        verdict = "REJECT"
    res.update(verdict=verdict, passes=passes, holdout_fee0=s_fee0, holdout_tier=s_tier, tier_maker_bp=tr[1] * 1e4,
               all35_fee0=s_all0, dsr=d_sr, dsr_sr0_ann=sr0, cap100k_tier=s_100, cap100k_fee0=s_100_0,
               stress2x_tier=s_stress, stress2x_fee0=s_stress0, holdout_V_day=ho.V.mean(),
               holdout_gross_day=ho.gross_flat.mean(), breakeven_maker_bp=ho.gross_flat.sum() / ho.V.sum() * 1e4,
               rs60_bp=mo, rs60_t=mo_t, vip6_reached_day=reached, climb_equity_day90=float(cl.equity.iloc[-1]),
               climb_min_equity=float(cl.equity.min()), msg_peak_sum_max=float(msg.peak.max()),
               msg_mean_sum=float(msg["mean"].mean()), intraday_dd_worst=float(intraday_dd))
    with open(os.path.join(OUT, "summary.json"), "w") as fh:
        json.dump(res, fh, indent=2, default=float)

    lines.append(f"Verdict: **{verdict}**\n")
    lines.append("| Check | Result |\n|---|---|")
    lines += [f"| {k} | {'pass' if v else 'FAIL'} |" for k, v in passes.items()]
    lines.append("\nAll configs (Sharpe above T-bills, daily; gross_bp = P&L per $ traded before fees):\n")
    lines.append(tab.round(2).to_markdown(index=False))
    lines.append("\nMarkouts (bp of notional; rs = realized spread vs mid h seconds after the fill):\n")
    lines.append(mk.round(2).to_markdown(index=False))
    with open(os.path.join(OUT, "summary.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(json.dumps(res, indent=2, default=float))


if __name__ == "__main__":
    select() if sys.argv[1] == "select" else final()
