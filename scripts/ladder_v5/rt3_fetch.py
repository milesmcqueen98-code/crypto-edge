#!/usr/bin/env python3
"""Red team 3 (C4_usdc): independent inputs, fetched on GitHub Actions (the research machine's proxy refuses these hosts).

Writes reports/ladder_v5/redteam3/fetch/:
  kraken_usdcusd_daily.csv       Kraken public OHLC, USDCUSD, 1440-minute candles (the last 720 days the API serves)
  kraken_trades_<window>.csv     Kraken public trades for USDCUSD, aggregated to 1-hour OHLCV, for each window around a
                                 day where Bitstamp's daily close moved more than 0.2% (and Mar 9-16 2023)
  kraken_minute_20230310.csv     the same trades at 1-minute resolution for Mar 10-13 2023 (depeg weekend)
  kraken_daily_from_trades.csv   UTC daily close (last trade before 00:00 UTC) per window day
  fred_tb3ms.csv, fred_dtb3.csv  FRED 3-month T-bill (monthly average; daily), secondary market, discount basis
  treasury_bills_<year>.csv      U.S. Treasury daily bill rates (official), 2022-2026
  coinbase_*.json / *.csv        Coinbase public product records (alias fields) and hourly candles for Mar 10-14 2023
                                 on BTC-USD vs BTC-USDC and USDT-USD vs USDT-USDC (were the books aliases then?)
  status.json                    what each source returned
Plain research User-Agent; no header spoofing; a refusal is recorded, not worked around.
"""
import json
import os
import sys
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "reports", "ladder_v5", "redteam3", "fetch")
UA = {"User-Agent": "crypto-edge research (redteam3; github.com/milesmcqueen98-code/crypto-edge)"}
STATUS = {}


def get(url, params=None, tries=4):
    for k in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=30)
            if r.status_code == 429:
                time.sleep(5 * (k + 1))
                continue
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (k + 1))
    raise RuntimeError(f"failed {url}: {last}")


def kraken_ohlc():
    r = get("https://api.kraken.com/0/public/OHLC", {"pair": "USDCUSD", "interval": 1440})
    STATUS["kraken_ohlc"] = r.status_code
    js = r.json()
    if js.get("error"):
        STATUS["kraken_ohlc_error"] = js["error"]
        return
    key = [k for k in js["result"] if k != "last"][0]
    df = pd.DataFrame(js["result"][key], columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"])
    df["date"] = pd.to_datetime(df.time, unit="s").dt.strftime("%Y-%m-%d")
    df.to_csv(os.path.join(OUT, "kraken_usdcusd_daily.csv"), index=False)
    STATUS["kraken_ohlc_rows"] = len(df)
    STATUS["kraken_ohlc_range"] = [df.date.iloc[0], df.date.iloc[-1]]


def kraken_trades(start, end, max_calls=900):
    """All Kraken USDCUSD trades in [start, end) (UTC), paging by the `last` cursor."""
    since = int(pd.Timestamp(start).value)          # nanoseconds
    stop = pd.Timestamp(end).value / 1e9
    rows, calls = [], 0
    while calls < max_calls:
        r = get("https://api.kraken.com/0/public/Trades", {"pair": "USDCUSD", "since": since, "count": 1000})
        calls += 1
        js = r.json()
        if js.get("error"):
            STATUS.setdefault("kraken_trades_errors", []).append(str(js["error"]))
            time.sleep(10)
            continue
        key = [k for k in js["result"] if k != "last"][0]
        tr = js["result"][key]
        if not tr:
            break
        rows.extend((float(t[0]), float(t[1]), float(t[2])) for t in tr)
        nxt = int(js["result"]["last"])
        if nxt <= since or float(tr[-1][2]) >= stop:
            break
        since = nxt
        time.sleep(1.1)
    df = pd.DataFrame(rows, columns=["price", "volume", "time"]).drop_duplicates()
    df = df[(df.time >= pd.Timestamp(start).value / 1e9) & (df.time < stop)].sort_values("time")
    df["t"] = pd.to_datetime(df.time, unit="s")
    return df, calls


def ohlc(df, freq):
    g = df.set_index("t").groupby(pd.Grouper(freq=freq))
    o = pd.DataFrame({"open": g.price.first(), "high": g.price.max(), "low": g.price.min(), "close": g.price.last(),
                      "volume": g.volume.sum(), "n": g.price.count()})
    return o


def kraken_windows():
    # days where Bitstamp's daily close moved > 0.2% (2022-2026), each with the day before; Mar 2023 in full
    wins = [("2022-04-16", "2022-04-19"), ("2022-05-11", "2022-05-13"), ("2022-11-24", "2022-11-26"),
            ("2023-01-18", "2023-01-21"), ("2023-03-09", "2023-03-16"), ("2025-06-02", "2025-06-04")]
    daily = []
    for lo, hi in wins:
        try:
            df, calls = kraken_trades(lo, hi)
        except Exception as e:  # noqa: BLE001
            STATUS[f"kraken_trades_{lo}"] = f"error {e}"
            continue
        STATUS[f"kraken_trades_{lo}"] = dict(trades=len(df), calls=calls,
                                             first=str(df.t.min()) if len(df) else None,
                                             last=str(df.t.max()) if len(df) else None)
        if not len(df):
            continue
        h = ohlc(df, "1h")
        h.to_csv(os.path.join(OUT, f"kraken_hourly_{lo}.csv"))
        if lo == "2023-03-09":
            m = ohlc(df[(df.t >= "2023-03-10") & (df.t < "2023-03-14")], "1min")
            m.to_csv(os.path.join(OUT, "kraken_minute_20230310.csv"))
        d = ohlc(df, "1D")
        d["window"] = lo
        daily.append(d)
    if daily:
        pd.concat(daily).to_csv(os.path.join(OUT, "kraken_daily_from_trades.csv"))


def fred():
    for sid in ("TB3MS", "DTB3"):
        try:
            r = get("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": sid})
            STATUS[f"fred_{sid}"] = r.status_code
            if r.status_code == 200 and r.text.lower().startswith(("observation_date", "date")):
                open(os.path.join(OUT, f"fred_{sid.lower()}.csv"), "w").write(r.text)
            else:
                STATUS[f"fred_{sid}_head"] = r.text[:200]
        except Exception as e:  # noqa: BLE001
            STATUS[f"fred_{sid}"] = f"error {e}"


def treasury():
    for y in range(2022, 2027):
        url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
               f"{y}/all")
        try:
            r = get(url, {"type": "daily_treasury_bill_rates", "field_tdr_date_value": y, "page": "", "_format": "csv"})
            STATUS[f"treasury_{y}"] = r.status_code
            if r.status_code == 200 and "Date" in r.text[:200]:
                open(os.path.join(OUT, f"treasury_bills_{y}.csv"), "w").write(r.text)
            else:
                STATUS[f"treasury_{y}_head"] = r.text[:200]
        except Exception as e:  # noqa: BLE001
            STATUS[f"treasury_{y}"] = f"error {e}"


def coinbase():
    recs = {}
    for p in ("BTC-USDC", "SOL-USDC", "ETH-USDC", "BTC-USD", "USDT-USDC", "USDT-USD", "USDC-USD", "USDC-EUR"):
        for name, url in (("advanced", f"https://api.coinbase.com/api/v3/brokerage/market/products/{p}"),
                          ("exchange", f"https://api.exchange.coinbase.com/products/{p}")):
            try:
                r = get(url)
                recs[f"{name}:{p}"] = dict(status=r.status_code, body=r.json() if r.headers.get(
                    "content-type", "").startswith("application/json") else r.text[:300])
            except Exception as e:  # noqa: BLE001
                recs[f"{name}:{p}"] = dict(status=f"error {e}")
            time.sleep(0.4)
    recs["fetched_utc"] = pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(recs, open(os.path.join(OUT, "coinbase_products.json"), "w"), indent=1)
    # hourly candles over the depeg weekend: if the -USDC books were separate, BTC-USDC / BTC-USD moves with 1/USDC
    rows = []
    for p in ("BTC-USD", "BTC-USDC", "ETH-USD", "ETH-USDC", "USDT-USD", "USDT-USDC"):
        try:
            r = get(f"https://api.exchange.coinbase.com/products/{p}/candles",
                    {"granularity": 3600, "start": "2023-03-09T00:00:00Z", "end": "2023-03-15T00:00:00Z"})
            STATUS[f"coinbase_candles_{p}"] = r.status_code
            if r.status_code == 200:
                for c in r.json():
                    rows.append(dict(product=p, time=c[0], low=c[1], high=c[2], open=c[3], close=c[4], volume=c[5]))
            else:
                STATUS[f"coinbase_candles_{p}_body"] = r.text[:300]
        except Exception as e:  # noqa: BLE001
            STATUS[f"coinbase_candles_{p}"] = f"error {e}"
        time.sleep(0.4)
    if rows:
        df = pd.DataFrame(rows)
        df["t"] = pd.to_datetime(df.time, unit="s")
        df.sort_values(["product", "t"]).to_csv(os.path.join(OUT, "coinbase_candles_20230309.csv"), index=False)


def main():
    os.makedirs(OUT, exist_ok=True)
    which = sys.argv[1:] or ["kraken_ohlc", "fred", "treasury", "coinbase", "kraken_windows"]
    for w in which:
        t0 = time.time()
        try:
            globals()[w]()
        except Exception as e:  # noqa: BLE001
            STATUS[w] = f"error {e}"
        STATUS[f"{w}_seconds"] = round(time.time() - t0)
        json.dump(STATUS, open(os.path.join(OUT, "status.json"), "w"), indent=1)
    print(json.dumps(STATUS, indent=1))


if __name__ == "__main__":
    main()
