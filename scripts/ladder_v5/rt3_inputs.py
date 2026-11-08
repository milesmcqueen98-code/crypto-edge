#!/usr/bin/env python3
"""Red team 3 (C4_usdc): input checks and post hoc sensitivities (not trials).

Reads the independent sources fetched by rt3_fetch.py (reports/ladder_v5/redteam3/fetch/) and the daily frames written by
rt3_c4.py (reports/ladder_v5/redteam3/c4_daily_<cfg>.csv), and writes reports/ladder_v5/redteam3/:
  tbill_check.csv          edge/book.py's monthly T-bill table vs U.S. Treasury daily bill rates (13-week, bank
                           discount and coupon equivalent, monthly averages) and FRED TB3MS
  usdc_check_daily.csv     Bitstamp vs Kraken USDC/USD daily closes and daily marks (Kraken OHLC 2024-11-18 on; Kraken
                           trades for the 2022-23 days where Bitstamp moved > 0.2%)
  usdc_mar2023_hourly.csv  Mar 9-15 2023 hourly: Bitstamp, Kraken (from trades), Coinbase USDT-USD / USDT-USDC implied
  inputs_summary.json      the comparisons, the depeg re-marks (4a) and the C4 sensitivities below
Sensitivities (post hoc; same incumbent, positions and holds as rt3_c4.py):
  tb_official   reward and the Sharpe's T-bill from Treasury's daily 13-week rate (bank discount) instead of the table
  mark_kraken   Kraken's daily close wherever Kraken has the day (else Bitstamp)
  cb_actual     Coinbase's published USDC rewards rate history (step series, sources in the report), full and halved
  forced_sale   the bot sells its USDC at the worst hourly close on Mar 11 2023 and buys it back at the Mar 13 close
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from edge import book as ebook  # noqa: E402

OUTD = os.path.join(ROOT, "reports", "ladder_v5", "redteam3")
FD = os.path.join(OUTD, "fetch")
ERAS = {"sel": ("2025-01-01", "2026-03-31"), "chk": ("2026-04-01", "2026-11-05"), "early": ("2022-01-01", "2023-12-31")}
CFG_C = {"S_0.5": 250e3, "S_0.25": 250e3, "base_0.5": 250e3, "cap_1M": 1e6}
CFG_HALF = {"S_0.5": 0.5, "S_0.25": 0.5, "base_0.5": 1.0, "cap_1M": 0.5}

# Coinbase's published US USDC rewards rate (annual %), step changes, as found (sources in REPORT.md):
#   0.15% until the late-Oct/Nov 2022 raise to 1.5% (Coinbase blog, updated 2022-11-30; The Defiant 2022-11-02);
#   2% by June 9 2023 (date of the 1.5 -> 2 step not found: assumed 2023-01-01); 4% from 2023-06-15 (The Block,
#   2023-06-16); 5% from 2023-09-10 (CryptoSlate / crypto.news, 2023-09-10, from user screenshots);
#   2024 not needed; 4.1% through Sep 2025 ("up to 4.1%" in Jul 2025, Decrypt 2025-12-11; 4.10% still on
#   coinbase.com/usdc; Jan-Jun 2025 assumed equal); 4% from Oct 2025 (DL News 2025-12-11); 3.5% from 2025-12-15,
#   Coinbase One members only (DL News; MEXC/livebitcoinnews 2026-02-22); 3.75% from 2026-09-15 (Eco, rate as of
#   2026-10-06); 3.60% from 2026-10-23 (stablecoininsider, 2026-10-28).
CB_RATE = [("2021-01-01", 0.15), ("2022-11-01", 1.5), ("2023-01-01", 2.0), ("2023-06-15", 4.0), ("2023-09-10", 5.0),
           ("2025-01-01", 4.1), ("2025-10-01", 4.0), ("2025-12-15", 3.5), ("2026-09-15", 3.75), ("2026-10-23", 3.6)]


def nw_t(x, lags=5):
    x = np.asarray(x, float)
    n, mu = len(x), x.mean()
    e = x - mu
    s = e @ e / n
    for k in range(1, lags + 1):
        s += 2.0 * (1.0 - k / (lags + 1.0)) * (e[k:] @ e[:-k]) / n
    return mu / np.sqrt(s / n) if s > 0 else np.nan


def ret_sharpe(r, rf):
    ex = r.to_numpy() - rf.reindex(r.index).to_numpy()
    yrs = len(r) / 365.25
    return float(r.sum() / yrs), float(ex.mean() / ex.std(ddof=1) * np.sqrt(365))


# ------------------------------------------------------------------------------------------------------ T-bills
def treasury_daily():
    fr = []
    for y in range(2022, 2027):
        p = os.path.join(FD, f"treasury_bills_{y}.csv")
        if os.path.exists(p):
            d = pd.read_csv(p)
            d["Date"] = pd.to_datetime(d["Date"], format="%m/%d/%Y")
            fr.append(d.set_index("Date")[["13 WEEKS BANK DISCOUNT", "13 WEEKS COUPON EQUIVALENT"]])
    t = pd.concat(fr).sort_index()
    t.columns = ["disc", "cey"]
    return t


def tbill_check():
    t = treasury_daily()
    m = t.groupby(t.index.to_period("M")).mean()
    fred = pd.read_csv(os.path.join(FD, "fred_tb3ms.csv"))
    fred["m"] = pd.to_datetime(fred.observation_date).dt.to_period("M")
    fred = fred.set_index("m").TB3MS
    rows = []
    for y, vals in ebook._TB.items():
        if y < 2022:
            continue
        for k, v in enumerate(vals):
            per = pd.Period(f"{y}-{k + 1:02d}", "M")
            rows.append(dict(month=str(per), table=v, treasury_13w_disc=m.disc.get(per, np.nan),
                             treasury_13w_cey=m.cey.get(per, np.nan), fred_tb3ms=fred.get(per, np.nan)))
    df = pd.DataFrame(rows)
    df["table_minus_treasury_bp"] = (df.table - df.treasury_13w_disc) * 100
    df["table_minus_fred_bp"] = (df.table - df.fred_tb3ms) * 100
    df["flag_gt_10bp"] = df.table_minus_treasury_bp.abs() > 10
    df.to_csv(os.path.join(OUTD, "tbill_check.csv"), index=False, float_format="%.4f")
    # daily official T-bill (bank discount), forward-filled over non-business days; Nov 6 2026 carried to the end
    idx = pd.date_range("2021-12-01", "2026-11-30", freq="D")
    tb = t.disc.reindex(idx).ffill().bfill()
    return df, tb


# ---------------------------------------------------------------------------------------------------- USDC/USD
def bitstamp_daily():
    a = pd.read_csv(os.path.join(ROOT, "data/ladder_v5/usdc_usd_bitstamp.csv"))
    b = pd.read_csv(os.path.join(ROOT, "data/ladder_v5/usdc_usd_bitstamp_ext.csv"))
    a, b = a[a.step == 86400], b[b.step == 86400]
    sa = pd.Series(a.close.to_numpy(float), index=pd.to_datetime(a.ts, unit="s"))
    sb = pd.Series(b.close.to_numpy(float), index=pd.to_datetime(b.ts, unit="s"))
    s = pd.concat([sa, sb[~sb.index.isin(sa.index)]]).sort_index()
    return s[~s.index.duplicated()]


def bitstamp_hourly():
    a = pd.read_csv(os.path.join(ROOT, "data/ladder_v5/usdc_usd_bitstamp.csv"))
    a = a[a.step == 3600]
    a.index = pd.to_datetime(a.ts, unit="s")
    return a[["open", "high", "low", "close", "volume"]]


def kraken_daily():
    o = pd.read_csv(os.path.join(FD, "kraken_usdcusd_daily.csv"))
    so = pd.Series(o.close.to_numpy(float), index=pd.to_datetime(o.date))
    t = pd.read_csv(os.path.join(FD, "kraken_daily_from_trades.csv"), parse_dates=["t"])
    st = pd.Series(t.close.to_numpy(float), index=t.t)
    st = st[~st.index.duplicated()]
    return pd.concat([st, so[~so.index.isin(st.index)]]).sort_index(), so, st


def usdc_check():
    bs = bitstamp_daily()
    kr, ko, kt = kraken_daily()
    mb = bs / bs.shift(1) - 1
    rows = []
    # Kraken OHLC days (contiguous): marks comparable on every day
    kom = ko / ko.shift(1) - 1
    common = ko.index.intersection(bs.index)
    common = common[common <= "2026-11-05"]
    for d in common:
        rows.append(dict(date=d, src="kraken_ohlc", bitstamp=bs[d], kraken=ko[d], m_bitstamp=mb.get(d, np.nan),
                         m_kraken=kom.get(d, np.nan)))
    # Kraken trade windows: a mark needs both days in the window
    ktm = kt / kt.shift(1) - 1
    ktm[(kt.index.to_series().diff() != pd.Timedelta(days=1)).to_numpy()] = np.nan
    for d in kt.index:
        if d in bs.index:
            rows.append(dict(date=d, src="kraken_trades", bitstamp=bs[d], kraken=kt[d], m_bitstamp=mb.get(d, np.nan),
                             m_kraken=ktm.get(d, np.nan)))
    df = pd.DataFrame(rows).sort_values(["date", "src"])
    df["close_diff_bp"] = (df.bitstamp - df.kraken) * 1e4
    df["m_diff_bp"] = (df.m_bitstamp - df.m_kraken) * 1e4
    df.to_csv(os.path.join(OUTD, "usdc_check_daily.csv"), index=False, float_format="%.6f")
    o = df[df.src == "kraken_ohlc"].dropna(subset=["m_kraken", "m_bitstamp"])
    t = df[df.src == "kraken_trades"].dropna(subset=["m_kraken"])
    summ = dict(
        ohlc_days=int(len(o)), ohlc_range=[str(o.date.min().date()), str(o.date.max().date())],
        ohlc_close_diff_bp_max_abs=float(o.close_diff_bp.abs().max()),
        ohlc_m_diff_bp_max_abs=float(o.m_diff_bp.abs().max()), ohlc_m_corr=float(o.m_bitstamp.corr(o.m_kraken)),
        ohlc_std_m_bitstamp_bp=float(o.m_bitstamp.std() * 1e4), ohlc_std_m_kraken_bp=float(o.m_kraken.std() * 1e4),
        ohlc_days_absm_gt_10bp_bitstamp=int((o.m_bitstamp.abs() > 1e-3).sum()),
        ohlc_days_absm_gt_10bp_kraken=int((o.m_kraken.abs() > 1e-3).sum()),
        window_days=[dict(date=str(r.date.date()), bitstamp=r.bitstamp, kraken=r.kraken,
                          m_bitstamp_bp=round(r.m_bitstamp * 1e4, 1),
                          m_kraken_bp=None if pd.isna(r.m_kraken) else round(r.m_kraken * 1e4, 1))
                     for r in df[df.src == "kraken_trades"].itertuples()],
        window_m_diff_bp_max_abs=float(t.m_diff_bp.abs().max()) if len(t) else None)
    return df, summ


def mar2023_hourly():
    bh = bitstamp_hourly()
    kh = pd.read_csv(os.path.join(FD, "kraken_hourly_2023-03-09.csv"), parse_dates=["t"]).set_index("t")
    km = pd.read_csv(os.path.join(FD, "kraken_minute_20230310.csv"), parse_dates=["t"]).set_index("t")
    cb = pd.read_csv(os.path.join(FD, "coinbase_candles_20230309.csv"), parse_dates=["t"])
    p = cb.pivot_table(index="t", columns="product", values="close")
    lo = cb.pivot_table(index="t", columns="product", values="low")
    hi = cb.pivot_table(index="t", columns="product", values="high")
    impl = (p["USDT-USD"] / p["USDT-USDC"]).rename("cb_implied_close")
    impl_lo = (lo["USDT-USD"] / hi["USDT-USDC"]).rename("cb_implied_low")
    idx = pd.date_range("2023-03-09", "2023-03-15 23:00", freq="h")
    H = pd.DataFrame({"bitstamp_close": bh.close, "bitstamp_low": bh.low, "kraken_close": kh.close,
                      "kraken_low": kh.low, "kraken_volume": kh.volume, "cb_implied_close": impl,
                      "cb_implied_low": impl_lo}).reindex(idx)
    H.to_csv(os.path.join(OUTD, "usdc_mar2023_hourly.csv"), float_format="%.5f")
    w = H.loc["2023-03-10":"2023-03-13 23:00"]
    kmw = km.loc["2023-03-10":"2023-03-13 23:59"]
    out = dict(
        bitstamp_min_hourly_close=[float(w.bitstamp_close.min()), str(w.bitstamp_close.idxmin())],
        bitstamp_min_low=[float(w.bitstamp_low.min()), str(w.bitstamp_low.idxmin())],
        kraken_min_hourly_close=[float(w.kraken_close.min()), str(w.kraken_close.idxmin())],
        kraken_min_trade=[float(kmw.low.min()), str(kmw.low.idxmin())],
        kraken_min_minute_close=[float(kmw.close.min()), str(kmw.close.idxmin())],
        coinbase_implied_min_hourly_close=[float(w.cb_implied_close.min()), str(w.cb_implied_close.idxmin())],
        coinbase_implied_min_low=[float(w.cb_implied_low.min()), str(w.cb_implied_low.idxmin())],
        kraken_volume_mar11_usd=float(kh.loc["2023-03-11"].volume.sum()),
        hours_below_0p99_bitstamp=int((w.bitstamp_close < 0.99).sum()),
        hours_below_0p99_kraken=int((w.kraken_close < 0.99).sum()),
        hours_below_0p95_bitstamp=int((w.bitstamp_close < 0.95).sum()),
        hours_below_0p95_kraken=int((w.kraken_close < 0.95).sum()))
    # minutes below 0.90 on Kraken (how long a forced seller would have faced a 10%+ discount)
    out["kraken_minutes_close_below_0p90"] = int((kmw.close < 0.90).sum())
    out["kraken_minutes_close_below_0p95"] = int((kmw.close < 0.95).sum())
    return H, out


# --------------------------------------------------------------------------------------------- C4 sensitivities
def load_daily(cfg):
    D = pd.read_csv(os.path.join(OUTD, f"c4_daily_{cfg}.csv"), parse_dates=["date"]).set_index("date")
    return D


def cb_rate_series(days):
    s = pd.Series({pd.Timestamp(d): v for d, v in CB_RATE}).sort_index()
    return (s.reindex(s.index.union(days)).ffill().reindex(days) / 100.0)


def evaluate(D, C, add, rf):
    """add: Series of the daily amount added to the incumbent (fraction of C). Per-era and pooled stats."""
    out, diffs = {}, []
    for era, (lo, hi) in ERAS.items():
        g = D[D.era == era]
        inc = g.inc
        cand = inc + add.reindex(g.index)
        ri, si = ret_sharpe(inc, rf)
        rc, sc = ret_sharpe(cand, rf)
        d = cand - inc
        out[era] = dict(inc_ret=ri, inc_sharpe=si, cand_ret=rc, cand_sharpe=sc, d_ret=rc - ri, d_sharpe=sc - si,
                        t=float(nw_t(d)), add_yr=float(d.sum() / (len(d) / 365.25)))
        diffs.append(d)
    out["pooled_t"] = float(nw_t(pd.concat(diffs)))
    return out


def sensitivities(tb_off, kr_daily, H):
    res = {}
    bs = bitstamp_daily()
    for cfg, C in CFG_C.items():
        D = load_daily(cfg)
        days = D.index
        half = CFG_HALF[cfg]
        rf_tab = ebook.rf_daily(days)
        rf_off = (tb_off.reindex(days) / 100.0 / 365.0)
        f = 1.0 - D.pos_frac
        r_tab = np.maximum(0.0, rf_tab - 0.005 / 365.0) * half
        r_off = np.maximum(0.0, rf_off - 0.005 / 365.0) * half
        base_A = (r_tab + D.mark) * f
        v = {}
        v["as_logged_A"] = evaluate(D, C, base_A, rf_tab)
        v["tb_official_A"] = evaluate(D, C, (r_off + D.mark) * f, rf_off)
        if "free_frac" in D:
            v["as_logged_B"] = evaluate(D, C, r_tab * D.free_frac + D.mark * f, rf_tab)
            v["tb_official_B"] = evaluate(D, C, r_off * D.free_frac + D.mark * f, rf_off)
        # Kraken mark wherever Kraken has both days, else Bitstamp
        cl = bs.copy()
        kk = kr_daily.reindex(cl.index)
        cl2 = cl.where(kk.isna(), kk)
        m_kr = (cl2 / cl2.shift(1) - 1).reindex(days).fillna(0.0)
        v["mark_kraken_A"] = evaluate(D, C, (r_tab + m_kr) * f, rf_tab)
        # Coinbase's published rate (full, and halved where the config halves unverified yields)
        cbr = cb_rate_series(days) / 365.0
        v["cb_actual_full_A"] = evaluate(D, C, (cbr + D.mark) * f, rf_tab)
        v["cb_actual_halfS_A"] = evaluate(D, C, (cbr * half + D.mark) * f, rf_tab)
        if "free_frac" in D:
            v["cb_actual_full_B"] = evaluate(D, C, cbr * D.free_frac + D.mark * f, rf_tab)
        # forced sale: sell all USDC at the worst hourly close on Mar 11 2023 (Bitstamp), buy back at the Mar 13 close;
        # mark days Mar 11-13 replaced so the cumulative loss is realised
        worst = float(H.loc["2023-03-11", "bitstamp_close"].min())
        m_fs = D.mark.copy()
        c10, c13 = float(bs["2023-03-10"]), float(bs["2023-03-13"])
        if pd.Timestamp("2023-03-11") in m_fs.index:
            # realised: from the Mar 10 close to the sale price, then flat in USD (no USDC held) until the buy-back
            m_fs[pd.Timestamp("2023-03-11")] = worst / c10 - 1.0
            m_fs[pd.Timestamp("2023-03-12")] = 0.0
            m_fs[pd.Timestamp("2023-03-13")] = 0.0
        v["forced_sale_A"] = evaluate(D, C, (r_tab + m_fs) * f, rf_tab)
        v["forced_sale_A"]["worst_hourly_close"] = worst
        v["forced_sale_A"]["loss_usd_mar11"] = float((worst / c10 - 1.0) * C * f[pd.Timestamp("2023-03-11")])
        v["forced_sale_A"]["rebuy_at_mar13_close"] = c13
        res[cfg] = v
    return res


def main():
    os.makedirs(OUTD, exist_ok=True)
    tbdf, tb_off = tbill_check()
    ud, usumm = usdc_check()
    H, hsumm = mar2023_hourly()
    kr, _, _ = kraken_daily()
    sens = sensitivities(tb_off, kr, H)
    # depeg re-marks (4a): USDC balance on Mar 11 2023 = C x (1 - positions) from the S* frame
    D = load_daily("S_0.5")
    f11 = float(1.0 - D.loc["2023-03-11", "pos_frac"])
    bs = bitstamp_daily()
    marks = {"daily_close_mar11_vs_mar10_close": float(bs["2023-03-11"] / bs["2023-03-10"] - 1),
             "daily_close_mar11_vs_par": float(bs["2023-03-11"] - 1),
             "worst_hourly_close_bitstamp_vs_par": hsumm["bitstamp_min_hourly_close"][0] - 1,
             "worst_hourly_close_kraken_vs_par": hsumm["kraken_min_hourly_close"][0] - 1,
             "worst_hourly_close_coinbase_implied_vs_par": hsumm["coinbase_implied_min_hourly_close"][0] - 1,
             "intraday_low_bitstamp_vs_par": hsumm["bitstamp_min_low"][0] - 1,
             "intraday_low_kraken_vs_par": hsumm["kraken_min_trade"][0] - 1}
    remark = {k: {"pct": v, "usd_250k": v * 250e3 * f11, "usd_1m": v * 1e6 * f11} for k, v in marks.items()}
    off = tbdf[tbdf.flag_gt_10bp]
    summary = dict(
        tbill=dict(months=int(len(tbdf)), flagged=off[["month", "table", "treasury_13w_disc", "fred_tb3ms",
                                                        "table_minus_treasury_bp"]].to_dict("records"),
                   max_abs_bp=float(tbdf.table_minus_treasury_bp.abs().max()),
                   mean_bp_by_year={str(y): float(g.table_minus_treasury_bp.mean())
                                    for y, g in tbdf.groupby(tbdf.month.str[:4])},
                   cey_minus_disc_bp_mean=float(((tbdf.treasury_13w_cey - tbdf.treasury_13w_disc) * 100).mean()),
                   treasury_last=[str(tb_off.dropna().index[-1].date()), float(tb_off.dropna().iloc[-1])]),
        usdc=usumm, mar2023=hsumm, remark_4a=remark, usdc_balance_frac_mar11=f11, sensitivities=sens)
    json.dump(summary, open(os.path.join(OUTD, "inputs_summary.json"), "w"), indent=1, default=str)
    # short print
    print("T-bill months flagged (>10 bp vs Treasury 13w discount):")
    print(off[["month", "table", "treasury_13w_disc", "fred_tb3ms", "table_minus_treasury_bp"]].to_string(index=False))
    print(json.dumps({k: v for k, v in usumm.items() if k != "window_days"}, indent=1))
    for r in usumm["window_days"]:
        print(r)
    print(json.dumps(hsumm, indent=1))
    print(json.dumps(remark, indent=1))
    for cfg, v in sens.items():
        print(cfg, {k: (round(x["pooled_t"], 2), {e: (round(x[e]["d_ret"] * 100, 2), round(x[e]["d_sharpe"], 3))
                                                   for e in ERAS}) for k, x in v.items()})


if __name__ == "__main__":
    main()
