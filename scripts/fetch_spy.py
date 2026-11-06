#!/usr/bin/env python3
"""SPY daily adjusted closes (total return) for comparison runs. Writes data/etf/SPY.csv."""
import os
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(ROOT, "data", "etf"), exist_ok=True)
for t in ["SPY", "QQQ"]:
    df = yf.download(t, start="1993-01-01", auto_adjust=True, progress=False)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df[["Close"]].rename(columns={"Close": "close"}).to_csv(os.path.join(ROOT, "data", "etf", f"{t}.csv"))
    print(t, len(df), df.index.min().date(), df.index.max().date())
