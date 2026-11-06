#!/usr/bin/env python3
"""Alternative data for the Medallion round (runs on CI; the research sandbox can't reach these hosts).

  python scripts/fetch_altdata.py probe        check which public sources answer from the runner
  python scripts/fetch_altdata.py fetch        download everything into data/alt/

Sources (all free, public, no keys):
  Binance USD-M futures archive (data.binance.vision): funding rates, 1h perp klines, daily open-interest/taker metrics
  Binance spot archive: 1h BTCUSDT/ETHUSDT (Coinbase premium = Coinbase USD price vs Binance USDT price)
  Deribit public API: DVOL implied-volatility index (BTC, ETH)
  alternative.me: Crypto Fear & Greed index
  DefiLlama: total stablecoin supply
  Coin Metrics community API: on-chain daily metrics (BTC, ETH)
  blockchain.com charts: BTC hash rate, transactions
  yfinance: CME bitcoin futures (BTC=F), VIX, dollar index, 10y yield, S&P futures, gold
Data from offshore exchanges is used for research signals only; nothing here trades there.
"""
import io
import json
import os
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "alt")
UA = {"User-Agent": "crypto-edge-research/1.0"}
BV = "https://data.binance.vision/data"
# coins with a Coinbase US perp (reports/cfm_products.csv) that also trade as Binance USD-M perps
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC", "BCH", "DOT", "XLM", "HBAR", "SUI", "NEAR",
         "AAVE", "ENA", "ONDO", "BNB", "ZEC"]
ONCHAIN = ["PriceUSD", "CapMrktCurUSD", "CapMVRVCur", "CapRealUSD", "AdrActCnt", "TxCnt", "TxTfrValAdjUSD", "HashRate",
           "FeeTotUSD", "SplyCur", "IssTotUSD", "NVTAdj", "SplyExNtv", "FlowInExNtv", "FlowOutExNtv"]


def get(url, tries=5, **kw):
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            if r.status_code in (429, 418) or r.status_code >= 500:
                time.sleep(3 * (i + 1))
                continue
            return r
        except requests.RequestException:
            time.sleep(3 * (i + 1))
    return None


def probe():
    tests = {
        "binance funding": f"{BV}/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2024-01.zip",
        "binance metrics": f"{BV}/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2024-01-01.zip",
        "binance perp klines": f"{BV}/futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2024-01.zip",
        "binance spot klines": f"{BV}/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2024-01.zip",
        "deribit dvol": "https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&start_timestamp="
                        "1704067200000&end_timestamp=1706745600000&resolution=1D",
        "fear greed": "https://api.alternative.me/fng/?limit=5&format=json",
        "defillama stables": "https://stablecoins.llama.fi/stablecoincharts/all",
        "coinmetrics": "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics="
                       + ",".join(ONCHAIN) + "&frequency=1d&page_size=3",
        "blockchain.com": "https://api.blockchain.info/charts/hash-rate?timespan=30days&format=json",
        "farside etf flows": "https://farside.co.uk/btc/",
    }
    for name, url in tests.items():
        r = get(url, tries=2)
        if r is None:
            print(f"{name:20s} NO RESPONSE")
            continue
        body = r.content[:300]
        print(f"{name:20s} {r.status_code} {len(r.content):>9,} bytes  {body[:160]!r}")
    try:
        import yfinance as yf
        for t in ["BTC=F", "^VIX", "DX-Y.NYB", "^TNX", "ES=F", "GC=F"]:
            d = yf.download(t, start="2024-01-01", end="2024-02-01", progress=False)
            print(f"yfinance {t:10s} rows {len(d)}")
    except Exception as err:  # noqa: BLE001
        print("yfinance error", err)


def months(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def read_zip_csv(content, header="infer", names=None):
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        with z.open(z.namelist()[0]) as fh:
            return pd.read_csv(fh, header=header, names=names)


def fetch_binance_funding(coin):
    sym = f"{coin}USDT"
    frames = []
    today = date.today()
    for y, m in months(date(2019, 9, 1), today):
        r = get(f"{BV}/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{y}-{m:02d}.zip", tries=3)
        if r is None or r.status_code != 200:
            continue
        df = read_zip_csv(r.content)
        df.columns = [c.lower() for c in df.columns]
        frames.append(df)
    if not frames:
        return None
    df = pd.concat(frames)
    tcol = "calc_time" if "calc_time" in df.columns else df.columns[0]
    df["ts"] = pd.to_datetime(df[tcol], unit="ms", utc=True).dt.tz_convert(None)
    rate = "last_funding_rate" if "last_funding_rate" in df.columns else df.columns[-1]
    return df[["ts", rate]].rename(columns={rate: "funding"}).drop_duplicates("ts").sort_values("ts")


KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
         "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def fetch_binance_klines(coin, market):
    sym = f"{coin}USDT"
    base = f"{BV}/futures/um" if market == "perp" else f"{BV}/spot"
    frames = []
    for y, m in months(date(2019, 9, 1) if market == "perp" else date(2017, 8, 1), date.today()):
        r = get(f"{base}/monthly/klines/{sym}/1h/{sym}-1h-{y}-{m:02d}.zip", tries=3)
        if r is None or r.status_code != 200:
            continue
        df = read_zip_csv(r.content, header=None, names=KCOLS)
        if not str(df.iloc[0, 0]).isdigit():
            df = df.iloc[1:]
        frames.append(df)
    # current month from daily files
    d = date.today().replace(day=1)
    while d < date.today():
        r = get(f"{base}/daily/klines/{sym}/1h/{sym}-1h-{d.isoformat()}.zip", tries=2)
        if r is not None and r.status_code == 200:
            df = read_zip_csv(r.content, header=None, names=KCOLS)
            if not str(df.iloc[0, 0]).isdigit():
                df = df.iloc[1:]
            frames.append(df)
        d += timedelta(days=1)
    if not frames:
        return None
    df = pd.concat(frames)
    ot = pd.to_numeric(df.open_time)
    ot = ot.where(ot < 1e14, ot // 1000)            # spot files switched to microseconds in 2025
    df["ts"] = pd.to_datetime(ot, unit="ms")
    for c in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_quote_volume"]:
        df[c] = pd.to_numeric(df[c])
    return df[["ts", "open", "high", "low", "close", "volume", "quote_volume", "taker_buy_quote_volume"]] \
        .drop_duplicates("ts").sort_values("ts")


def fetch_binance_metrics(coin, start=date(2021, 12, 1)):
    """Daily files of 5-minute open interest, top-trader and taker ratios; kept at the last row of each hour."""
    sym = f"{coin}USDT"
    frames = []
    d = start
    while d < date.today():
        r = get(f"{BV}/futures/um/daily/metrics/{sym}/{sym}-metrics-{d.isoformat()}.zip", tries=2)
        if r is not None and r.status_code == 200:
            df = read_zip_csv(r.content)
            df["ts"] = pd.to_datetime(df["create_time"])
            frames.append(df.set_index("ts").resample("1h").last().reset_index())
        d += timedelta(days=1)
    if not frames:
        return None
    df = pd.concat(frames).drop(columns=["create_time", "symbol"], errors="ignore")
    return df.dropna(how="all", subset=[c for c in df.columns if c != "ts"])


def fetch_dvol(cur):
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    start = int(datetime(2021, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)
    rows = []
    while start < end:
        stop = min(end, start + 900 * 3600 * 1000)
        r = get("https://www.deribit.com/api/v2/public/get_volatility_index_data", params=dict(
            currency=cur, start_timestamp=start, end_timestamp=stop, resolution="3600"))
        if r is None or r.status_code != 200:
            break
        data = r.json().get("result", {}).get("data", [])
        rows += data
        start = stop
        time.sleep(0.2)
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df.ts, unit="ms")
    return df.drop_duplicates("ts").sort_values("ts")


def fetch_coinmetrics(asset):
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    frames, token = [], None
    while True:
        params = dict(assets=asset, metrics=",".join(ONCHAIN), frequency="1d", page_size=10000, start_time="2010-01-01",
                      ignore_forbidden_errors="true", ignore_unsupported_errors="true")
        if token:
            params["next_page_token"] = token
        r = get(url, params=params)
        if r is None or r.status_code != 200:
            print("coinmetrics", asset, r.status_code if r is not None else None, r.text[:200] if r is not None else "")
            break
        js = r.json()
        frames.append(pd.DataFrame(js.get("data", [])))
        token = js.get("next_page_token")
        if not token:
            break
    if not frames:
        return None
    df = pd.concat(frames)
    df["date"] = pd.to_datetime(df.time).dt.tz_convert(None).dt.normalize()
    return df.drop(columns=["time", "asset"], errors="ignore")


def save(df, name):
    if df is None or len(df) == 0:
        print("EMPTY", name, flush=True)
        return
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False)
    print("saved", name, len(df), flush=True)


def fetch(parts):
    os.makedirs(OUT, exist_ok=True)
    if "small" in parts:
        r = get("https://api.alternative.me/fng/?limit=0&format=json")
        if r is not None and r.status_code == 200:
            fg = pd.DataFrame(r.json()["data"])
            fg["date"] = pd.to_datetime(fg.timestamp.astype(int), unit="s")
            save(fg[["date", "value", "value_classification"]], "fear_greed.parquet")
        r = get("https://stablecoins.llama.fi/stablecoincharts/all")
        if r is not None and r.status_code == 200:
            js = r.json()
            st = pd.DataFrame([{"date": pd.to_datetime(int(x["date"]), unit="s"),
                                "usd": (x.get("totalCirculatingUSD") or x.get("totalCirculating") or {}).get("peggedUSD")}
                               for x in js])
            save(st, "stablecoins.parquet")
        for cur in ["BTC", "ETH"]:
            save(fetch_dvol(cur), f"dvol_{cur}.parquet")
        for a in ["btc", "eth"]:
            save(fetch_coinmetrics(a), f"onchain_{a}.parquet")
        for chart in ["hash-rate", "n-transactions", "miners-revenue"]:
            r = get(f"https://api.blockchain.info/charts/{chart}?timespan=all&format=json&sampled=false")
            if r is not None and r.status_code == 200:
                v = pd.DataFrame(r.json()["values"])
                v["date"] = pd.to_datetime(v.x, unit="s")
                save(v[["date", "y"]].rename(columns={"y": chart}), f"bc_{chart}.parquet")
        import yfinance as yf
        for t, nm in [("BTC=F", "cme_btc"), ("ETH=F", "cme_eth"), ("^VIX", "vix"), ("DX-Y.NYB", "dxy"), ("^TNX", "tnx"),
                      ("ES=F", "es"), ("GC=F", "gold"), ("NQ=F", "nq")]:
            d = yf.download(t, start="2015-01-01", auto_adjust=False, progress=False)
            d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
            save(d.reset_index().rename(columns={"Date": "date"}), f"yf_{nm}.parquet")
    if "funding" in parts:
        for c in COINS:
            save(fetch_binance_funding(c), f"binance/funding_{c}.parquet")
    if "klines" in parts:
        for c in COINS:
            save(fetch_binance_klines(c, "perp"), f"binance/perp1h_{c}.parquet")
        for c in ["BTC", "ETH"]:
            save(fetch_binance_klines(c, "spot"), f"binance/spot1h_{c}.parquet")
    if "metrics" in parts:
        for c in [p for p in parts if p.isupper()] or ["BTC", "ETH"]:
            save(fetch_binance_metrics(c), f"binance/metrics_{c}.parquet")


if __name__ == "__main__":
    if sys.argv[1] == "probe":
        probe()
    else:
        fetch(sys.argv[2:] if len(sys.argv) > 2 else ["small", "funding", "klines", "metrics"])
