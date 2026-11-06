#!/usr/bin/env python3
"""Daily total-return closes (yfinance, auto-adjusted) for the multi-asset trend sleeve. Writes data/etf/<TICKER>.csv.

Proxies for contracts listed on Coinbase Derivatives (US500, Tech100, China index, gold, silver, crude oil, natural gas,
copper, platinum) plus a CME extension (Treasuries, dollar, euro, yen). See reports/multiasset_prereg.md.
"""
import os
import time

import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKERS = ["SPY", "QQQ", "FXI", "GLD", "SLV", "USO", "UNG", "CPER", "PPLT", "TLT", "IEF", "UUP", "FXE", "FXY"]

os.makedirs(os.path.join(ROOT, "data", "etf"), exist_ok=True)
for t in TICKERS:
    for attempt in range(5):
        try:
            df = yf.download(t, start="2000-01-01", auto_adjust=True, progress=False)
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            if len(df) < 100:
                raise RuntimeError("too few rows")
            df[["Close"]].rename(columns={"Close": "close"}).to_csv(os.path.join(ROOT, "data", "etf", f"{t}.csv"))
            print(t, len(df), df.index.min().date(), df.index.max().date(), flush=True)
            break
        except Exception as err:  # noqa: BLE001
            print(f"retry {t}: {err}", flush=True)
            time.sleep(5 * (attempt + 1))
