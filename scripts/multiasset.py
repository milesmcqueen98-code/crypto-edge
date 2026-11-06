#!/usr/bin/env python3
"""Scale round 2 (pre-registered in reports/multiasset_prereg.md): highest Sharpe that holds at $5M.

C3 (crypto) + a multi-asset trend sleeve of contracts Coinbase Derivatives lists (H1), and + Treasuries/currencies via
CME (H2). Carver EWMAC book defaults on daily total-return proxies, equal instrument weights, IDM from development
correlations, risk parity with C3 by inverse development volatility. Writes reports/multiasset.csv,
reports/multiasset_returns.parquet, reports/multiasset_capacity.csv.
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge import book, intraday as ih  # noqa: E402
import c3_improve as c3i  # noqa: E402
import intraday_search as s1  # noqa: E402

COINBASE = ["SPY", "QQQ", "FXI", "GLD", "SLV", "USO", "UNG", "CPER", "PPLT"]
CME = ["TLT", "IEF", "UUP", "FXE", "FXY"]
COST = {t: 3e-4 for t in COINBASE + CME}
COST.update({"UNG": 6e-4, "CPER": 6e-4, "PPLT": 6e-4, "FXI": 6e-4})
SPEEDS = [(8, 32), (16, 64), (32, 128), (64, 256)]
TARGET = 0.25
PER = c3i.PER
CFM = {"SPY": "US5", "QQQ": "TEK", "FXI": "CHN", "GLD": "GOL", "SLV": "SLR", "USO": "NOL", "UNG": "NGS",
       "CPER": "CU", "PPLT": "PT", "BTC": "BIP", "ETH": "ETP"}
N_TRIALS = 484


def load_px(tickers):
    px = {}
    for t in tickers:
        d = pd.read_csv(os.path.join(ROOT, "data", "etf", f"{t}.csv"), parse_dates=[0], index_col=0)
        px[t] = d["close"].astype(float)
    return pd.DataFrame(px).sort_index()


def trend_sleeve(tickers, mult=1.0, idm=None):
    px = load_px(tickers)
    r = px.pct_change(fill_method=None)
    sig = r.ewm(span=35, min_periods=20).std()
    vann = (sig * np.sqrt(256)).clip(lower=0.05)
    fc = []
    for f, s in SPEEDS:
        raw = (px.ewm(span=f, min_periods=f).mean() - px.ewm(span=s, min_periods=s).mean()) / (px * sig)
        scal = 10.0 / raw.abs().stack().groupby(level=0).mean().expanding(min_periods=256).mean()
        fc.append(raw.mul(scal, axis=0).clip(-20, 20))
    F = (sum(fc) / len(fc) * 1.15).clip(-20, 20)
    active = F.notna() & vann.notna()
    n_act = active.sum(axis=1).replace(0, np.nan)
    # instrument sub-system returns (weight 1) for the IDM
    days = px.index.to_series().diff().dt.days.fillna(1)
    rf_d = book.rf_daily(pd.DatetimeIndex(px.index)).to_numpy()
    ex = r.sub(rf_d * days.to_numpy(), axis=0)
    sub = (F / 10 * TARGET / vann).shift(1) * ex
    if idm is None:
        dev = sub.loc[PER["dev"][0]:PER["dev"][1]]
        cols = [c for c in dev.columns if dev[c].notna().sum() > 250]
        C = dev[cols].corr().clip(lower=0).to_numpy()
        w = np.full(len(cols), 1 / len(cols))
        idm = float(min(2.5, 1 / np.sqrt(w @ C @ w)))
    unit = (1.0 / n_act).to_numpy()[:, None] * idm * TARGET / vann
    pos = book.buffer_positions((F / 10 * unit).fillna(0.0), 0.10 * unit.fillna(0.0))
    pos = book.cap_gross(pos.fillna(0.0), 4.0)
    held = pos.shift(1).fillna(0.0)
    tc = (pos.diff().abs().fillna(0.0) * pd.Series({t: COST[t] for t in tickers}) * mult).sum(axis=1)
    margin = ih.MARGIN_SHARE * (held.abs().sum(axis=1) > 0).astype(float) * rf_d * days.to_numpy()
    ret_td = (held * ex.fillna(0.0)).sum(axis=1) - tc - margin
    cal = pd.date_range(px.index.min(), px.index.max(), freq="D")
    ret = ret_td.reindex(cal, fill_value=0.0)
    return ret, pos, idm


def c3_returns(ck="b", rounding=False):
    live_P = s1.to_hourly(s1.live_daily())
    hls = c3i.ewmac()
    live_r, hls_r = ih.run(live_P, s1.close_h), ih.run(hls, s1.close_h)
    wl = 1 / live_r.loc[PER["dev"][0]:PER["dev"][1]].std()
    wh = 1 / hls_r.loc[PER["dev"][0]:PER["dev"][1]].std()
    W_L, W_H = wl / (wl + wh), wh / (wl + wh)
    P = W_L * live_P.reindex(hls.index).fillna(0.0) + W_H * hls
    cost = {k: v * (2 if ck == "c" else 1) for k, v in c3i.COSTS["b"].items()}
    x, _ = c3i.engine(P, cost, rounding)
    return x, P


def rp(a, b):
    wa = 1 / a.loc[PER["dev"][0]:PER["dev"][1]].std()
    wb = 1 / b.loc[PER["dev"][0]:PER["dev"][1]].std()
    return wa / (wa + wb), wb / (wa + wb)


def stats_row(name, x):
    row = dict(book=name)
    for p, (s_, e_) in PER.items():
        row[f"sharpe_{p}"] = book.sharpe(x, s_, e_)
    if x.loc[:"2017-07-01"].dropna().size > 365:
        row["sharpe_2010"] = book.sharpe(x, "2010-01-01")
    st = book.summary(x, "2017-07-01")
    row.update(cagr_full=st["cagr"], maxdd_full=st["maxdd"], vol_full=float(x.loc["2017-07-01":].std() * np.sqrt(365)))
    for y, v in c3i.yearly(x).items():
        row[f"y{y}"] = v
    return row


def lever_for(x, target):
    xx = x.loc["2017-07-01":]
    rf = book.rf_daily(xx.index)
    lo, hi = 0.0, 20.0
    for _ in range(60):
        mid = (lo + hi) / 2
        tot = (1 + mid * xx + rf).prod() ** (365.25 / len(xx)) - 1
        lo, hi = (mid, hi) if tot < target else (lo, mid)
    eq = (1 + lo * xx + rf).cumprod()
    return lo, float((eq / eq.cummax() - 1).min())


def main():
    c3, c3_pos = c3_returns("b")
    c3s, _ = c3_returns("c")
    ma, ma_pos, idm1 = trend_sleeve(COINBASE)
    ma_s, _, _ = trend_sleeve(COINBASE, 2.0, idm1)
    mx, mx_pos, idm2 = trend_sleeve(COINBASE + CME)
    mx_s, _, _ = trend_sleeve(COINBASE + CME, 2.0, idm2)
    idx = c3.index
    ma, ma_s, mx, mx_s = (s.reindex(idx).fillna(0.0) for s in (ma, ma_s, mx, mx_s))
    a1, b1 = rp(c3, ma)
    a2, b2 = rp(c3, mx)
    p1, p1s = a1 * c3 + b1 * ma, a1 * c3s + b1 * ma_s
    p2, p2s = a2 * c3 + b2 * mx, a2 * c3s + b2 * mx_s
    print(f"IDM Coinbase sleeve {idm1:.2f}, with CME {idm2:.2f}; P1 weights C3 {a1:.2f} / multi-asset {b1:.2f}; "
          f"P2 weights C3 {a2:.2f} / multi-asset {b2:.2f}")
    # long-history sleeves (from 2006+) for the 2010 check
    ma_long, _, _ = trend_sleeve(COINBASE, 1.0, idm1)
    mx_long, _, _ = trend_sleeve(COINBASE + CME, 1.0, idm2)
    rets = {"C3": c3, "Multi-asset (Coinbase)": ma, "Multi-asset (Coinbase+CME)": mx, "P1 C3 + Coinbase": p1,
            "P2 C3 + Coinbase + CME": p2, "C3 2x cost": c3s, "P1 2x cost": p1s, "P2 2x cost": p2s}
    rows = [stats_row(k, v) for k, v in rets.items()]
    rows += [stats_row("Multi-asset (Coinbase), from 2007", ma_long), stats_row("Multi-asset (+CME), from 2007", mx_long)]
    tab = pd.DataFrame(rows)
    for name, x in (("P1 C3 + Coinbase", p1), ("P2 C3 + Coinbase + CME", p2)):
        for p in ("dev", "recent", "early", "7y", "full"):
            z, _ = c3i.memmel(x, c3, *PER[p])
            tab.loc[tab.book == name, f"z_vs_C3_{p}"] = z
        tab.loc[tab.book == name, "dsr"] = c3i.dsr(x, N_TRIALS)
    tab.loc[tab.book == "C3", "dsr"] = c3i.dsr(c3, N_TRIALS)
    corr = pd.DataFrame({"C3": c3, "MA": ma, "MA+CME": mx}).loc["2017-07-01":]
    print("correlations (daily, Jul 2017+):\n", corr.corr().round(2).to_string())
    print("correlations (weekly):\n", corr.resample("W").sum().corr().round(2).to_string())
    # pre-registered rule
    t = tab.set_index("book")

    def beats(new, old):
        return (t.loc[new, "sharpe_dev"] > t.loc[old, "sharpe_dev"] and t.loc[new, "sharpe_recent"] >= t.loc[old, "sharpe_recent"]
                and t.loc[new, "sharpe_early"] >= t.loc[old, "sharpe_early"])
    p1_wins = beats("P1 C3 + Coinbase", "C3")
    p2_wins = beats("P2 C3 + Coinbase + CME", "P1 C3 + Coinbase") if p1_wins else beats("P2 C3 + Coinbase + CME", "C3")
    print(f"Rule: P1 replaces C3: {p1_wins}; P2 replaces {'P1' if p1_wins else 'C3'}: {p2_wins}")
    # leverage for 50% / 100% a year
    lev = []
    for name in ("C3", "P1 C3 + Coinbase", "P2 C3 + Coinbase + CME"):
        for tgt in (0.5, 1.0):
            L, dd = lever_for(rets[name], tgt)
            lev.append(dict(book=name, target=tgt, leverage=L, maxdd=dd))
    lev = pd.DataFrame(lev)
    tab.to_csv(os.path.join(ROOT, "reports", "multiasset.csv"), index=False)
    lev.to_csv(os.path.join(ROOT, "reports", "multiasset_leverage.csv"), index=False)
    pd.DataFrame(rets).to_parquet(os.path.join(ROOT, "reports", "multiasset_returns.parquet"))

    # capacity at $5M for the 100%-a-year leverage of P1 (Coinbase-only book)
    prods = pd.read_csv(os.path.join(ROOT, "reports", "cfm_products.csv"))
    prods["usd_vol"] = prods.volume_24h * prods.price * prods.contract_size
    prods["usd_oi"] = prods.open_interest * prods.price * prods.contract_size
    code = prods.product_id.str.split("-").str[0]
    best = prods.assign(code=code).sort_values("usd_vol", ascending=False).drop_duplicates("code").set_index("code")
    L100 = float(lev[(lev.book == "P1 C3 + Coinbase") & (lev.target == 1.0)].leverage.iloc[0])
    cap_rows = []
    last = slice("2025-11-01", None)
    c3p = c3_pos.loc[last]
    c3_daily_trade = c3p.diff().abs().resample("D").sum()
    for t_ in COINBASE + ["BTC", "ETH"]:
        if t_ in ("BTC", "ETH"):
            pos = a1 * c3p[t_].abs().resample("D").mean()
            trade = a1 * c3_daily_trade[t_]
        else:
            pp = ma_pos[t_].loc[last]
            pos, trade = b1 * pp.abs(), b1 * pp.diff().abs()
        cb = best.loc[CFM[t_]] if CFM[t_] in best.index else None
        avg_pos = float(pos.mean() * L100 * 5e6)
        max_pos = float(pos.max() * L100 * 5e6)
        avg_trade = float(trade.mean() * L100 * 5e6)
        cap_rows.append(dict(instrument=t_, coinbase_contract=CFM[t_], avg_position_usd=avg_pos, max_position_usd=max_pos,
                             avg_daily_trade_usd=avg_trade,
                             coinbase_24h_volume_usd=float(cb.usd_vol) if cb is not None else np.nan,
                             coinbase_open_interest_usd=float(cb.usd_oi) if cb is not None else np.nan))
    cap = pd.DataFrame(cap_rows)
    cap["trade_pct_of_volume"] = cap.avg_daily_trade_usd / cap.coinbase_24h_volume_usd
    cap["max_pos_pct_of_oi"] = cap.max_position_usd / cap.coinbase_open_interest_usd
    cap.to_csv(os.path.join(ROOT, "reports", "multiasset_capacity.csv"), index=False)

    pd.set_option("display.width", 250)
    cols = ["book", "sharpe_dev", "sharpe_recent", "sharpe_early", "sharpe_7y", "sharpe_full", "sharpe_2010", "cagr_full",
            "vol_full", "maxdd_full", "dsr"]
    print(tab[cols].round(2).to_string(index=False))
    print(tab[["book"] + [c for c in tab.columns if c.startswith("y20")]].round(2).to_string(index=False))
    print(tab[["book"] + [c for c in tab.columns if c.startswith("z_vs")]].dropna(how="all", subset=[c for c in tab.columns if c.startswith("z_vs")]).round(2).to_string(index=False))
    print(lev.round(2).to_string(index=False))
    print(f"Capacity at $5M, P1 at {L100:.2f}x (100% a year):")
    print(cap.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
