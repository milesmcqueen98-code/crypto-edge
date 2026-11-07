#!/usr/bin/env python3
"""H10 (XQ): Coinbase Exchange public candles, paced (~8 requests/second per runner)."""
import time

import numpy as np
import pandas as pd
import requests

API = "https://api.exchange.coinbase.com/products"


class Candles:
    def __init__(self, rate=8.0):
        self.S = requests.Session()
        self.S.headers["User-Agent"] = "crypto-edge-research/1.0"
        self.rate, self._last, self.n_req, self.n_err = rate, 0.0, 0, 0

    def get(self, pid, start, end, gran):
        """Raw candles [time, low, high, open, close, volume] in [start, end] (unix seconds, inclusive)."""
        for a in range(10):
            w = self._last + 1.0 / self.rate - time.time()
            if w > 0:
                time.sleep(w)
            self._last = time.time()
            self.n_req += 1
            try:
                r = self.S.get(f"{API}/{pid}/candles", timeout=30,
                               params={"granularity": gran,
                                       "start": pd.Timestamp(start, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ"),
                                       "end": pd.Timestamp(end, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ")})
                if r.status_code == 429 or r.status_code >= 500:
                    self.n_err += 1
                    time.sleep(1 + a)
                    continue
                if r.status_code in (400, 404):
                    return []
                r.raise_for_status()
                js = r.json()
                return js if isinstance(js, list) else []
            except requests.RequestException:
                self.n_err += 1
                if a == 9:
                    raise
                time.sleep(1 + a)
        return []

    def range(self, pid, start, end, gran, n=300):
        """All candles of `pid` with start time in [start, end), as a DataFrame (ts, open, high, low, close, volume)."""
        s, e = int(pd.Timestamp(start).timestamp()), int(pd.Timestamp(end).timestamp())
        rows = {}
        while s < e:
            hi = min(s + (n - 1) * gran, e - gran)
            for c in self.get(pid, s, hi, gran):
                if s <= c[0] <= hi:
                    rows[c[0]] = c
            s += n * gran
        if not rows:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        a = np.array([rows[k] for k in sorted(rows)], dtype=np.float64)
        d = pd.DataFrame({"ts": pd.to_datetime(a[:, 0].astype(np.int64), unit="s"), "open": a[:, 3], "high": a[:, 2],
                          "low": a[:, 1], "close": a[:, 4], "volume": a[:, 5]})
        return d
