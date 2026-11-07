#!/usr/bin/env python3
"""Red team h1pb (Actions): Coinbase Derivatives top-of-book on the one free Tardis day with CDE data (2026-11-01,
a Sunday, EST): per-minute quoted spread and top-of-book size 3:00-8:00 pm ET for a few perps, plus the trades file.
Writes reports/hunt/h1pb/redteam/tardis_quotes_min.csv and tardis_status.csv (counts only)."""
import gzip
import io
import os
import sys

import numpy as np
import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "reports", "hunt", "h1pb", "redteam")
SYMS = ["XLP-20DEC30-CDE", "NER-20DEC30-CDE", "ZEC-20DEC30-CDE", "DOP-20DEC30-CDE", "BIP-20DEC30-CDE", "XPP-20DEC30-CDE",
        "ETP-20DEC30-CDE", "ADP-20DEC30-CDE"]
DAY = "2026/11/01"


def get(path):
    r = requests.get("https://datasets.tardis.dev/v1/" + path, timeout=120, headers={"User-Agent": "crypto-edge-research/1.0"})
    return r.status_code, r.content


def main():
    os.makedirs(OUT, exist_ok=True)
    stat, rows = [], []
    for s in SYMS:
        for typ in ("quotes", "book_snapshot_25"):
            code, body = get(f"coinbase-derivatives/{typ}/{DAY}/{s}.csv.gz")
            stat.append(dict(sym=s, type=typ, status=code, nbytes=len(body)))
            print(stat[-1], flush=True)
            if code != 200 or typ != "quotes":
                continue
            d = pd.read_csv(io.BytesIO(gzip.decompress(body)))
            t = pd.to_datetime(d["timestamp"], unit="us")
            et = t.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
            d["etmin"] = et.dt.hour * 60 + et.dt.minute
            d = d[(d.etmin >= 15 * 60) & (d.etmin < 20 * 60)]
            mid = (d.ask_price + d.bid_price) / 2
            d["spr_bp"] = (d.ask_price - d.bid_price) / mid * 1e4
            d["no_bid"] = d.bid_price.isna() | (d.bid_amount.fillna(0) <= 0)
            d["no_ask"] = d.ask_price.isna() | (d.ask_amount.fillna(0) <= 0)
            g = d.groupby("etmin").agg(n=("spr_bp", "size"), spr_med=("spr_bp", "median"), spr_p90=("spr_bp", lambda x: x.quantile(0.9)),
                                       spr_max=("spr_bp", "max"), no_bid=("no_bid", "mean"), no_ask=("no_ask", "mean"),
                                       bid_sz_med=("bid_amount", "median"), ask_sz_med=("ask_amount", "median"))
            g = g.reset_index()
            g["sym"] = s
            rows.append(g)
    pd.DataFrame(stat).to_csv(os.path.join(OUT, "tardis_status.csv"), index=False)
    if rows:
        pd.concat(rows).to_csv(os.path.join(OUT, "tardis_quotes_min.csv"), index=False)


if __name__ == "__main__":
    main()
