#!/usr/bin/env python3
"""Gemini venue test: fetch the sample days from Tardis (scripts/gemini/fetch_tardis.py) and attach to every Gemini
print what the analysis needs from Coinbase and from Gemini's book, so that only the prints are committed:
  cb_last, cb_age        Coinbase's last price at or before the print's second, and its age (s)
  cb_low_pm60            Coinbase's lowest print in the print's second +- 60 s
  cb_last_<h>            Coinbase's last price at the print's second + h (h = 1, 10, 60, 300, 3600 s)
  gbid_<h>, gask_<h>     Gemini's best bid and ask at the print's second + h (h = 0 and the above)
Also writes per coin-day USD volumes on both venues. Runs on Actions (the workspace cannot reach Tardis).
Usage: python scripts/gemini/enrich.py DAY [DAY ...]
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_tardis  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
MARKS = (1, 10, 60, 300, 3600)
DST = os.path.join(ROOT, "data", "gemini", "prints")


def asof(sec, val, t):
    i = np.searchsorted(sec, t, side="right") - 1
    return np.where(i >= 0, val[np.maximum(i, 0)], np.nan), np.where(i >= 0, t - sec[np.maximum(i, 0)], np.nan)


def window_min(sec, val, t, w):
    """Minimum of val over sec in [t - w, t + w] for each t (sec sorted)."""
    a = np.searchsorted(sec, t - w, side="left")
    b = np.searchsorted(sec, t + w, side="right")
    out = np.full(len(t), np.nan)
    for n in range(len(t)):
        if b[n] > a[n]:
            out[n] = val[a[n]:b[n]].min()
    return out


def enrich_day(day):
    src = os.path.join("out", "gemini", day)
    g = pd.read_parquet(os.path.join(src, "gem_trades.parquet"))
    q = pd.read_parquet(os.path.join(src, "gem_quotes.parquet")) if os.path.exists(os.path.join(src, "gem_quotes.parquet")) else None
    c = pd.read_parquet(os.path.join(src, "cb_sec.parquet")) if os.path.exists(os.path.join(src, "cb_sec.parquet")) else None
    out, vols = [], []
    for coin in sorted(g.coin.unique()):
        G = g[g.coin == coin].sort_values(["timestamp", "id"]).reset_index(drop=True)
        t = np.floor(G.timestamp.to_numpy() / 1e6)
        E = pd.DataFrame({"coin": coin, "ts_us": G.timestamp.to_numpy(), "id": G.id.to_numpy(),
                          "side": G.side.to_numpy(), "price": G.price.to_numpy().astype(float),
                          "amount": G.amount.to_numpy().astype(float)})
        C = c[c.coin == coin].sort_values("sec") if c is not None else None
        if C is not None and len(C):
            cs, cl, clo = C.sec.to_numpy().astype(float), C["last"].to_numpy(), C["low"].to_numpy()
            E["cb_last"], E["cb_age"] = asof(cs, cl, t)
            E["cb_low_pm60"] = window_min(cs, clo, t, 60)
            for h in MARKS:
                E[f"cb_last_{h}"] = asof(cs, cl, t + h)[0]
        Qc = q[q.coin == coin].sort_values("sec") if q is not None else None
        if Qc is not None and len(Qc):
            qs = Qc.sec.to_numpy().astype(float)
            for h in (0,) + MARKS:
                E[f"gbid_{h}"] = asof(qs, Qc.bid_price.to_numpy(), t + h)[0]
                E[f"gask_{h}"] = asof(qs, Qc.ask_price.to_numpy(), t + h)[0]
        for col in E.columns:
            if col not in ("coin", "ts_us", "id", "side", "price", "amount") and E[col].dtype == np.float64:
                E[col] = E[col].astype(np.float64)
        out.append(E)
        usd = G.price.to_numpy() * G.amount.to_numpy()
        vols.append(dict(day=day, coin=coin, gem_usd=float(usd.sum()), gem_sell_usd=float(usd[G.side == "sell"].sum()),
                         gem_prints=len(G), cb_usd=float(C.usd.sum()) if C is not None and len(C) else np.nan,
                         cb_sell_usd=float(C.sell_usd.sum()) if C is not None and len(C) else np.nan))
    os.makedirs(DST, exist_ok=True)
    pd.concat(out, ignore_index=True).to_parquet(os.path.join(DST, f"{day}.parquet"), index=False, compression="zstd")
    return vols


def main(days):
    fetch_tardis.main(days)
    vols = []
    for d in days:
        if os.path.exists(os.path.join("out", "gemini", d, "gem_trades.parquet")):
            vols += enrich_day(d)
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    tag = f"{days[0]}_{days[-1]}"
    pd.DataFrame(vols).to_csv(os.path.join(os.path.dirname(DST), f"volumes_{tag}.csv"), index=False)
    for f in ("gemini_details.json", "tardis_gemini_symbols.json"):
        src = os.path.join("out", "gemini", "meta", f)
        if os.path.exists(src):
            os.replace(src, os.path.join(os.path.dirname(DST), f"meta_{tag}_{f}"))
    print(f"enriched {len(days)} days -> {DST}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
