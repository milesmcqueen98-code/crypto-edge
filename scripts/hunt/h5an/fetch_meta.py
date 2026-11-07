#!/usr/bin/env python3
"""H5 (AN) metadata, runs on Actions. No prices.
- Coinbase currency names (Exchange API /currencies) for a ticker-collision check against Binance titles.
- Feasibility probe (status codes and counts only) of the Exchange API trades endpoint for delisted USD products,
  paginated by trade id, since Advanced Trade's ticker window returns 404 for them.
usage: python scripts/hunt/h5an/fetch_meta.py
"""
import json
import os
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_D = os.path.join(ROOT, "data", "hunt", "h5an")
OUT_R = os.path.join(ROOT, "reports", "hunt", "h5an")
S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"
EX = "https://api.exchange.coinbase.com"


def main():
    os.makedirs(OUT_D, exist_ok=True)
    log = {}
    r = S.get(f"{EX}/currencies", timeout=60)
    cur = pd.DataFrame(r.json())
    keep = [c for c in ("id", "name", "status", "message", "convertible_to") if c in cur.columns]
    cur[keep].to_csv(os.path.join(OUT_D, "cb_currencies.csv"), index=False)
    log["currencies"] = {"status": r.status_code, "n": len(cur)}
    probe = {}
    for pid in ("RNDR-USD", "MATIC-USD", "GAL-USD", "LRC-USD"):
        out = {}
        r = S.get(f"{EX}/products/{pid}/trades", params={"limit": 5}, timeout=30)
        out["latest_status"] = r.status_code
        try:
            js = r.json()
            out["latest_n"] = len(js) if isinstance(js, list) else str(js)[:200]
            if isinstance(js, list) and js:
                top = int(js[0]["trade_id"])
                out["latest_time"] = js[0]["time"][:10]
                mid = top // 2
                time.sleep(0.2)
                r2 = S.get(f"{EX}/products/{pid}/trades", params={"limit": 5, "after": mid}, timeout=30)
                js2 = r2.json()
                out["mid_status"] = r2.status_code
                out["mid_day"] = js2[0]["time"][:10] if isinstance(js2, list) and js2 else str(js2)[:200]
                out["cb_after_header"] = r2.headers.get("cb-after") is not None
        except Exception as e:  # noqa: BLE001
            out["error"] = f"{type(e).__name__}: {e}"[:300]
        probe[pid] = out
        time.sleep(0.3)
    log["exchange_trades_probe"] = probe
    print(json.dumps(log, indent=1))
    with open(os.path.join(OUT_R, "fetch_meta.json"), "w") as f:
        json.dump(log, f, indent=1)


if __name__ == "__main__":
    main()
