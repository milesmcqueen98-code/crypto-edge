#!/usr/bin/env python3
"""Edge hunt 2 (GAMMA, EXP): every Deribit option trade for a currency over a range of months, from Deribit's public
history API (reachable from GitHub runners; reports/hunt2/probe/deribit_probe.json). Raw trades go to an artifact;
nothing is computed here.

usage: python scripts/hunt2/deribit/fetch_trades.py <currency> <first month YYYY-MM> <last month YYYY-MM> <out_dir>
Writes <out_dir>/<currency>_<YYYY-MM>.parquet (timestamp ms, trade_id, instrument_name, direction (taker side),
amount, contracts, price, iv, index_price, mark_price) and <out_dir>/<currency>_log.csv (rows per month, requests).
"""
import os
import sys
import time

import pandas as pd
import requests

URL = "https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time"
S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"
RATE = 6.0
_last = [0.0]
KEEP = ["timestamp", "trade_id", "instrument_name", "direction", "amount", "contracts", "price", "iv",
        "index_price", "mark_price"]


def get(params):
    for a in range(10):
        w = _last[0] + 1.0 / RATE - time.time()
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
        try:
            r = S.get(URL, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2 + 2 * a)
                continue
            r.raise_for_status()
            return r.json()["result"]
        except Exception:  # noqa: BLE001
            if a == 9:
                raise
            time.sleep(1 + a)


def month(cur, m0):
    t0 = int(pd.Timestamp(m0).timestamp() * 1000)
    t1 = int((pd.Timestamp(m0) + pd.offsets.MonthBegin(1)).timestamp() * 1000)
    rows, seen, start, n_req = [], set(), t0, 0
    while start < t1:
        res = get(dict(currency=cur, kind="option", start_timestamp=start, end_timestamp=t1, count=1000,
                       sorting="asc"))
        n_req += 1
        tr = res.get("trades", [])
        new = [t for t in tr if t["trade_id"] not in seen]
        for t in new:
            seen.add(t["trade_id"])
            rows.append({k: t.get(k) for k in KEEP})
        if not res.get("has_more") or not tr:
            break
        nxt = tr[-1]["timestamp"]
        start = nxt if new else nxt + 1          # re-request the boundary millisecond; step past it if stuck
    d = pd.DataFrame(rows, columns=KEEP)
    return d, n_req


def main(cur, m_first, m_last, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    log = []
    for m0 in pd.date_range(m_first, m_last, freq="MS"):
        tt = time.time()
        d, n_req = month(cur, m0)
        f = os.path.join(out_dir, f"{cur}_{m0:%Y-%m}.parquet")
        d.to_parquet(f, index=False)
        log.append(dict(month=f"{m0:%Y-%m}", rows=len(d), requests=n_req, secs=round(time.time() - tt)))
        print(log[-1], flush=True)
    pd.DataFrame(log).to_csv(os.path.join(out_dir, f"{cur}_log_{m_first}_{m_last}.csv"), index=False)


if __name__ == "__main__":
    main(*sys.argv[1:5])
