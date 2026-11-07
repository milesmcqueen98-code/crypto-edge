#!/usr/bin/env python3
"""H10 (XQ): which secondary books get resting bids on each day (uses daily VOLUMES only, never a cross residual).

The SPEC caps cash in the quote asset, resting bids included at full size ($5K), at the sleeve's capital, so a sleeve
of C dollars can rest at most floor(C / 5000) bids at once. The bot gives those slots to the most liquid eligible
books of its quote set: rank by the trailing 30-day median daily USD volume of the X-Q book (calendar days, zeros
included, as of the previous day); eligible on day d if the X-Q book and both USD legs traded on day d-1.
Output: data/hunt/h10xq/universe.parquet (day, quote set, rank, pair, base/quote legs, adv) for ranks <= 10, and
data/hunt/h10xq/fetch_plan.csv (product, start, end) for the 1-minute fetch (top-10 days + 4 warm-up days).
usage: python scripts/hunt/h10xq/universe.py
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DATA = os.path.join(ROOT, "data", "hunt", "h10xq")
MAIN = "/home/claude/crypto-edge/data"
NMAX = 10
WARM = 4
SETS = {"USDT": ("USDT",), "BTCETH": ("BTC", "ETH")}


def windows():
    return ((pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31")),
            (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-11-05")))


def build():
    D = pd.read_parquet(os.path.join(DATA, "daily.parquet"))
    P = pd.read_csv(os.path.join(ROOT, "reports", "hunt", "h10xq", "pairs.csv"))
    P = P[P.eligible]
    days = pd.date_range("2021-12-01", "2026-11-06", freq="D")
    vol = D.pivot_table(index="ts", columns="product", values="volume").reindex(days)
    px = D.pivot_table(index="ts", columns="product", values="close").reindex(days)
    rows = []
    for r in P.itertuples():
        if r.id not in vol:
            continue
        usd = (vol[r.id] * px[r.id] * px.get(r.quote_usd)).fillna(0.0)
        adv = usd.rolling(30, min_periods=30).median().shift(1)
        traded = (vol[r.id].fillna(0) > 0) & (vol.get(r.base_usd, pd.Series(0, index=days)).fillna(0) > 0) & \
                 (vol.get(r.quote_usd, pd.Series(0, index=days)).fillna(0) > 0)
        ok = traded.shift(1, fill_value=False) & (adv > 0)
        qs = "USDT" if r.quote_currency == "USDT" else "BTCETH"
        for d in days[ok.to_numpy()]:
            rows.append((d, qs, r.id, r.base_currency, r.quote_currency, r.base_usd, r.quote_usd, float(adv[d])))
    U = pd.DataFrame(rows, columns=["day", "qset", "pair", "base", "quote", "base_usd", "quote_usd", "adv_usd"])
    U["rank"] = U.groupby(["day", "qset"]).adv_usd.rank(ascending=False, method="first").astype(int)
    U = U[U["rank"] <= NMAX]
    m = np.zeros(len(U), bool)
    for a, b in windows():
        m |= (U.day >= a) & (U.day <= b)
    U = U[m].sort_values(["day", "qset", "rank"]).reset_index(drop=True)
    U.to_parquet(os.path.join(DATA, "universe.parquet"), index=False)
    return U


def plan(U):
    """Contiguous [start, end) ranges per product (pairs and USD legs not on disk), with WARM warm-up days."""
    local = {}
    for src, (a, b) in (("minute", ("2024-01-01", "2026-11-06")), ("minute_early", ("2021-01-01", "2024-01-01"))):
        for f in os.listdir(os.path.join(MAIN, src)):
            local.setdefault(f.split(".")[0], []).append((pd.Timestamp(a), pd.Timestamp(b)))
    need = {}
    for r in U.itertuples():
        for prod in (r.pair, r.base_usd, r.quote_usd):
            need.setdefault(prod, set()).update(pd.date_range(r.day - pd.Timedelta(days=WARM), r.day))
    out = []
    for prod, ds in need.items():
        ds = sorted(ds)
        if prod.endswith("-USD"):
            coin = prod[:-4]
            ds = [d for d in ds if not any(a <= d < b for a, b in local.get(coin, []))]
        if not ds:
            continue
        s = prev = ds[0]
        for d in ds[1:] + [None]:
            if d is None or (d - prev).days > 7:
                out.append((prod, s, prev + pd.Timedelta(days=1)))
                s = d
            prev = d if d is not None else prev
    F = pd.DataFrame(out, columns=["product", "start", "end"])
    F["days"] = (F.end - F.start).dt.days
    F.to_csv(os.path.join(DATA, "fetch_plan.csv"), index=False)
    return F


if __name__ == "__main__":
    U = build()
    F = plan(U)
    print(U.groupby(["qset"]).pair.nunique())
    for qs in SETS:
        u = U[U.qset == qs]
        print(qs, "pairs ever in top-6:", u[u["rank"] <= 6].pair.nunique(), "top-10:", u.pair.nunique())
        print(u[u["rank"] <= 6].groupby("pair").size().sort_values(ascending=False).head(25).to_dict())
    print("fetch:", len(F), "ranges,", F["product"].nunique(), "products,", int(F.days.sum()), "product-days, ~",
          int(F.days.sum() * 4.8), "requests")
    print(F.groupby(F["product"].str.endswith("-USD")).days.sum())
