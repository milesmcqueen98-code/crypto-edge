#!/usr/bin/env python3
"""Edge hunt 2: can a GitHub Actions runner reach Deribit's public history and Coinbase-hosted Deribit endpoints?
Writes reports/hunt2/probe/deribit_probe.json (status codes, first/last trade times, counts). No statistic computed."""
import json
import os
import time

import requests

out = {}
S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"
tests = {
    "history_options_2021": ("https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time",
                             dict(currency="BTC", kind="option", start_timestamp=1609459200000,
                                  end_timestamp=1609545600000, count=1000, sorting="asc")),
    "history_options_2025": ("https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time",
                             dict(currency="BTC", kind="option", start_timestamp=1735689600000,
                                  end_timestamp=1735776000000, count=1000, sorting="asc")),
    "drb_book_summary": ("https://drb.coinbase.com/api/v2/public/get_book_summary_by_currency",
                         dict(currency="BTC", kind="option")),
    "deribit_book_summary": ("https://www.deribit.com/api/v2/public/get_book_summary_by_currency",
                             dict(currency="BTC", kind="option")),
    "deribit_instruments_expired": ("https://history.deribit.com/api/v2/public/get_instruments",
                                    dict(currency="BTC", kind="option", expired="true")),
}
for name, (url, params) in tests.items():
    t0 = time.time()
    try:
        r = S.get(url, params=params, timeout=30)
        row = dict(status=r.status_code, secs=round(time.time() - t0, 2))
        js = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        res = js.get("result")
        if isinstance(res, dict) and "trades" in res:
            tr = res["trades"]
            row.update(n=len(tr), has_more=res.get("has_more"), keys=sorted(tr[0].keys()) if tr else [],
                       first=tr[0]["timestamp"] if tr else None, last=tr[-1]["timestamp"] if tr else None)
        elif isinstance(res, list):
            row.update(n=len(res), keys=sorted(res[0].keys())[:30] if res else [])
        else:
            row.update(body=r.text[:300])
    except Exception as e:  # noqa: BLE001
        row = dict(error=repr(e)[:300])
    out[name] = row
    print(name, row, flush=True)
os.makedirs("reports/hunt2/probe", exist_ok=True)
json.dump(out, open("reports/hunt2/probe/deribit_probe.json", "w"), indent=1, default=str)
