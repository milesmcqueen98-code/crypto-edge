#!/usr/bin/env python3
"""Ladder v5, C4 (reports/ladder_v5/specs/cash_venue.md): Bitstamp USDC/USD daily candles 2024-09-26 .. 2026-11-05.

The frozen data/ladder_v5/usdc_usd_bitstamp.csv has daily candles 2022-01-01 .. 2024-09-26 (and hourly Mar-Apr 2023).
This fetches the rest of the daily series from Bitstamp's public OHLC endpoint (no key), with a plain research
User-Agent and at least 1 s between requests, into a NEW file (the frozen CSV is not touched):
  data/ladder_v5/usdc_usd_bitstamp_ext.csv    same columns as the frozen CSV (step, ts, open, high, low, close, volume)
  reports/ladder_v5/cashvenue/fetch_usdc.json  every request with its HTTP status, rows kept, coverage and gaps
A refusal (HTTP 403 or any 4xx other than 429) is recorded and not worked around; the candidate then uses 1.0 for the
missing days. Transient errors (429, 5xx, network) are retried at most three times with a growing pause.
usage: python scripts/ladder_v5/fetch_usdc_ext.py
"""
import csv
import json
import os
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
URL = "https://www.bitstamp.net/api/v2/ohlc/usdcusd/"
UA = "crypto-edge-research/1.0"
START, END = "2024-09-26", "2026-11-05"
OUT_CSV = os.path.join(ROOT, "data", "ladder_v5", "usdc_usd_bitstamp_ext.csv")
OUT_LOG = os.path.join(ROOT, "reports", "ladder_v5", "cashvenue", "fetch_usdc.json")


def main():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    t0 = int(pd.Timestamp(START, tz="UTC").timestamp())
    t1 = int(pd.Timestamp(END, tz="UTC").timestamp())
    log = {"url": URL, "user_agent": UA, "range": [START, END], "requests": [], "refused": False}
    rows, cur, last = {}, t0, 0.0
    for _ in range(6):                                  # 771 days need one page of 1,000; a few spare pages
        params = {"step": 86400, "limit": 1000, "start": cur}
        ohlc = None
        for attempt in range(3):
            wait = max(1.1, 2.0 * attempt) - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            last = time.time()
            entry = {"params": dict(params), "attempt": attempt, "utc": pd.Timestamp.now(tz="UTC").isoformat()}
            try:
                r = s.get(URL, params=params, timeout=30)
                entry["http"] = r.status_code
                if r.status_code == 200:
                    ohlc = r.json()["data"]["ohlc"]
                    entry["n"] = len(ohlc)
                    log["requests"].append(entry)
                    break
                entry["body"] = r.text[:300]
                log["requests"].append(entry)
                if r.status_code != 429 and r.status_code < 500:
                    log["refused"] = True                 # a refusal: stop, do not work around it
                    break
            except Exception as err:                    # network error or malformed body
                entry["error"] = repr(err)[:300]
                log["requests"].append(entry)
        if ohlc is None:
            break
        new = 0
        for o in ohlc:
            ts = int(o["timestamp"])
            if t0 <= ts <= t1 and ts not in rows:
                rows[ts] = dict(step=86400, ts=ts, open=float(o["open"]), high=float(o["high"]), low=float(o["low"]),
                                close=float(o["close"]), volume=float(o["volume"]))
                new += 1
        log["requests"][-1]["kept"] = new
        if not rows or max(rows) >= t1 or new == 0:
            break
        cur = max(rows) + 86400
    want = pd.date_range(START, END, freq="D")
    have = pd.to_datetime(sorted(rows), unit="s")
    missing = want.difference(have)
    log.update(rows=len(rows), first=str(have.min().date()) if len(have) else None,
               last=str(have.max().date()) if len(have) else None, missing_days=len(missing),
               missing=[str(d.date()) for d in missing[:50]])
    os.makedirs(os.path.dirname(OUT_LOG), exist_ok=True)
    if rows:
        os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
        with open(OUT_CSV, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["step", "ts", "open", "high", "low", "close", "volume"])
            w.writeheader()
            w.writerows(rows[t] for t in sorted(rows))
    json.dump(log, open(OUT_LOG, "w"), indent=1)
    print(json.dumps({k: v for k, v in log.items() if k != "requests"}, indent=1))
    for e in log["requests"]:
        print(e)


if __name__ == "__main__":
    main()
