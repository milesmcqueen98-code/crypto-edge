#!/usr/bin/env python3
"""Edge hunt 2: daily data for US-listed crypto ETFs (leveraged, inverse and spot) from Yahoo Finance, run on Actions.

usage: python scripts/hunt2/fetch_etf.py <out_dir> TICKER [TICKER ...]
Writes <out_dir>/etf_daily.parquet (date, ticker, open, high, low, close, volume) and <out_dir>/etf_shares.parquet
(date, ticker, shares) when Yahoo serves a shares-outstanding history, plus <out_dir>/etf_info.csv (first trading
day, rows, whether shares history exists). Inputs only: no strategy statistic is computed here.
"""
import os
import sys

import pandas as pd


def main(out_dir, tickers):
    import yfinance as yf
    os.makedirs(out_dir, exist_ok=True)
    px, sh, info = [], [], []
    for t in tickers:
        row = dict(ticker=t)
        try:
            d = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=False)
            d = d.reset_index()
            d = pd.DataFrame(dict(date=pd.to_datetime(d["Date"]).dt.tz_localize(None).dt.normalize(),
                                  open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"], volume=d["Volume"]))
            d["ticker"] = t
            px.append(d)
            row.update(first=str(d.date.min().date()) if len(d) else "", rows=len(d))
        except Exception as e:  # noqa: BLE001
            row.update(error=repr(e)[:200])
        try:
            s = yf.Ticker(t).get_shares_full(start="2020-01-01")
            if s is not None and len(s):
                s = s.reset_index()
                s.columns = ["time", "shares"]
                s["date"] = pd.to_datetime(s["time"]).dt.tz_localize(None).dt.normalize()
                s = s.groupby("date", as_index=False).shares.last()
                s["ticker"] = t
                sh.append(s)
                row.update(shares_rows=len(s), shares_first=str(s.date.min().date()))
        except Exception as e:  # noqa: BLE001
            row.update(shares_error=repr(e)[:200])
        info.append(row)
        print(row, flush=True)
    if px:
        pd.concat(px, ignore_index=True).to_parquet(os.path.join(out_dir, "etf_daily.parquet"), index=False)
    if sh:
        pd.concat(sh, ignore_index=True).to_parquet(os.path.join(out_dir, "etf_shares.parquet"), index=False)
    pd.DataFrame(info).to_csv(os.path.join(out_dir, "etf_info.csv"), index=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
