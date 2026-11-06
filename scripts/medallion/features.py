"""Signal library for the Medallion round: raw quantities per coin on the Coinbase daily calendar.

Row d holds what is known at the 00:00 UTC close that ends Coinbase day d. Implementation choices made before any
statistic was computed are listed in reports/medallion_prereg.md (deviation log, "implementation notes").
"""
import io
import os

import numpy as np
import pandas as pd

from common import ALT, binance_funding_raw, daily_close, rz

LUNAR_EPOCH = pd.Timestamp("2000-01-06 18:14")       # a new moon
SYNODIC = 29.530588853
FAMILIES = {"F0": "lunar placebo", "F1": "positioning and sentiment", "F4": "return sequences",
            "F8": "alternative data"}


def _pq(name):
    p = os.path.join(ALT, name)
    return pd.read_parquet(p) if os.path.exists(p) else None


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def fear_greed():
    fg = _pq("fear_greed.parquet")
    if fg is None:
        return None
    fg["date"] = pd.to_datetime(fg["date"]).dt.normalize()
    return fg.drop_duplicates("date").set_index("date")["value"].pipe(_num).sort_index()


def stablecoins():
    st = _pq("stablecoins.parquet")
    if st is None:
        return None
    st["date"] = pd.to_datetime(st["date"]).dt.normalize()
    return st.drop_duplicates("date").set_index("date")["usd"].pipe(_num).sort_index()


def dvol(coin):
    d = _pq(f"dvol_{coin}.parquet")
    if d is None:
        return None
    d = d.set_index("ts").sort_index()
    return d["close"].astype(float).groupby(d.index.floor("D")).last()


def onchain(coin):
    d = _pq(f"onchain_{coin.lower()}.parquet")
    if d is None:
        return None
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d.drop_duplicates("date").set_index("date").sort_index()
    return d.apply(_num)


def yf_close(nm):
    d = _pq(f"yf_{nm}.parquet")
    if d is None:
        return None
    d["date"] = pd.to_datetime(d["date"]).dt.tz_localize(None).dt.normalize()
    return d.drop_duplicates("date").set_index("date")["Close"].astype(float).dropna().sort_index()


def binance_metrics(coin):
    d = _pq(f"binance/metrics_{coin}.parquet")
    if d is None:
        return None
    d = d.set_index("ts").sort_index().apply(_num)
    return d


def binance_klines(coin, market="perp"):
    d = _pq(f"binance/{'perp' if market == 'perp' else 'spot'}1h_{coin}.parquet")
    if d is None:
        return None
    return d.set_index("ts").sort_index()


def coinbase_hourly(coin):
    d = pd.read_csv(os.path.join(os.path.dirname(ALT), "hourly", f"{coin}.csv.gz"), parse_dates=["ts"])
    return d.drop_duplicates("ts").set_index("ts").sort_index()["close"]


def etf_flows(coin):
    """Farside daily net flows (US$m), total column, indexed by US trading date. Descriptive only (2024+)."""
    t = _pq(f"etf_flows_{coin.lower()}.parquet")
    if t is None:
        return None
    dcol = t.columns[0]
    tot = [c for c in t.columns if "total" in c.lower()]
    if not tot:
        return None
    dates = pd.to_datetime(t[dcol], errors="coerce", dayfirst=True)
    v = t[tot[-1]].astype(str).str.replace(",", "").str.replace("(", "-").str.replace(")", "").str.strip()
    s = pd.Series(_num(v).to_numpy(), index=dates)
    return s[s.index.notna()].groupby(level=0).last().sort_index()


def last_friday(y, m):
    d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)
    return d - pd.Timedelta(days=(d.weekday() - 4) % 7)


def cme_dte(dates):
    out = []
    for d in dates:
        e = last_friday(d.year, d.month)
        if d > e:
            n = d + pd.offsets.MonthBegin(1)
            e = last_friday(n.year, n.month)
        out.append((e - d).days)
    return pd.Series(out, index=dates)


def cme_basis(coin, idx, ct_hour=15):
    """Annualized front-month CME basis: yfinance continuous future close (the 15:00 CT settlement, chosen by the
    measurement check) vs the Coinbase hourly close at that time on the same US date. Days within 5 days of expiry are
    left out (Yahoo rolls the continuous series a few days early and prints the final settlement on expiry day)."""
    fut = yf_close("cme_btc" if coin == "BTC" else "cme_eth")
    if fut is None:
        return None
    cb = coinbase_hourly(coin)
    cb_utc = cb.copy()
    cb_utc.index = cb_utc.index + pd.Timedelta(hours=1)               # close time of each bar
    stamps = [(pd.Timestamp(d) + pd.Timedelta(hours=ct_hour)).tz_localize("America/Chicago").tz_convert("UTC")
              .tz_localize(None) for d in fut.index]
    spot = cb_utc.reindex(stamps).to_numpy()
    raw = pd.Series(fut.to_numpy() / spot - 1.0, index=fut.index)
    dte = cme_dte(fut.index)
    return (raw * 365.0 / dte).where(dte >= 5).reindex(idx)


def raw_signals(coin):
    close = daily_close([coin])[coin]
    vol = daily_close([coin], "volume")[coin]
    idx = close.index
    r = close.pct_change(fill_method=None)
    S = {}
    # ---------------- F0 placebo
    days = ((idx + pd.Timedelta(days=1)) - LUNAR_EPOCH).total_seconds() / 86400.0
    S["F0_lunar"] = pd.Series(np.cos(2 * np.pi * ((days / SYNODIC) % 1.0)), index=idx)
    # ---------------- F1 positioning and sentiment
    fg = fear_greed()
    if fg is not None:
        fg = fg.reindex(idx)
        S["F1_fg"] = fg
        S["F1_fg_chg7"] = fg - fg.shift(7)
    fr = binance_funding_raw(coin)
    if fr is not None:
        fl = fr.groupby(fr.index.floor("D")).mean().reindex(idx)
        S["F1_fund"] = fl
        S["F1_fund_chg7"] = fl - fl.shift(7)
    m = binance_metrics(coin)
    if m is not None:
        day = m.index.floor("D")
        oi = m["sum_open_interest"].groupby(day).last().reindex(idx)
        S["F1_oi_chg1"] = np.log(oi / oi.shift(1))
        S["F1_oi_chg7"] = np.log(oi / oi.shift(7))
        S["F1_top_acct"] = m["count_toptrader_long_short_ratio"].groupby(day).mean().reindex(idx)
        S["F1_top_pos"] = m["sum_toptrader_long_short_ratio"].groupby(day).mean().reindex(idx)
    k = binance_klines(coin, "perp")
    if k is not None:
        day = k.index.floor("D")
        buy = k["taker_buy_quote_volume"].groupby(day).sum()
        tot = k["quote_volume"].groupby(day).sum()
        S["F1_taker"] = np.log(buy / (tot - buy)).replace([np.inf, -np.inf], np.nan).reindex(idx)
    # ---------------- F4 return sequences
    for n in (1, 2, 3, 5, 20):
        S[f"F4_ret{n}"] = close / close.shift(n) - 1
    S["F4_rv_ratio"] = r.rolling(5).std() / r.rolling(30).std()
    S["F4_volume"] = np.log((close * vol).where(vol > 0))
    S["F4_dist_high20"] = close / close.rolling(20).max() - 1
    # ---------------- F8 alternative data
    sp = binance_klines(coin, "spot")
    if sp is not None:
        cb = coinbase_hourly(coin)
        prem = (cb / sp["close"].reindex(cb.index) - 1).dropna()
        cbp = prem.groupby(prem.index.floor("D")).mean().reindex(idx)
        S["F8_cbp"] = cbp
        S["F8_cbp_chg7"] = cbp - cbp.shift(7)
    b = cme_basis(coin, idx)
    if b is not None:
        S["F8_cme_basis"] = b
    st = stablecoins()
    if st is not None:
        st = st.reindex(idx)
        S["F8_stable_g7"] = np.log(st / st.shift(7))
        S["F8_stable_g30"] = np.log(st / st.shift(30))
    dv = dvol(coin)
    if dv is not None:
        dv = dv.reindex(idx)
        S["F8_dvol"] = dv
        S["F8_dvol_rv"] = dv - 100 * r.rolling(30).std() * np.sqrt(365)
        S["F8_dvol_chg7"] = dv - dv.shift(7)
    oc = onchain(coin)
    if oc is not None:
        oc = oc.reindex(idx)
        for col, nm in (("AdrActCnt", "adr"), ("TxCnt", "tx"), ("FeeTotUSD", "fees"), ("HashRate", "hash")):
            if col in oc and oc[col].notna().sum() > 400 and (coin == "BTC" or nm != "hash"):
                x7 = oc[col].rolling(7, min_periods=5).mean()
                S[f"F8_{nm}_g30"] = np.log(x7 / x7.shift(30)).shift(1)
        if "CapMVRVCur" in oc:
            S["F8_mvrv"] = oc["CapMVRVCur"].shift(1)
        if "NVTAdj" in oc and oc["NVTAdj"].notna().sum() > 400:
            S["F8_nvt"] = oc["NVTAdj"].shift(1)
        elif "CapMrktCurUSD" in oc and "TxTfrValAdjUSD" in oc:
            S["F8_nvt"] = (oc["CapMrktCurUSD"] / oc["TxTfrValAdjUSD"]).shift(1)
    for nm, kind in (("vix", "diff"), ("dxy", "ret"), ("tnx", "diff"), ("es", "ret"), ("nq", "ret"), ("gold", "ret")):
        y = yf_close(nm)
        if y is None:
            continue
        ch = y.diff() if kind == "diff" else y.pct_change()
        S[f"F8_{nm}"] = ch.reindex(idx)                  # NaN on days without a US close
    return pd.DataFrame(S, index=idx), close


def z_signals(coin):
    raw, close = raw_signals(coin)
    return raw.apply(rz), raw, close


def describe_etf(coin):
    f = etf_flows(coin)
    return f
