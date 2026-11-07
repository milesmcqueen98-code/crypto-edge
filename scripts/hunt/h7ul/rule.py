#!/usr/bin/env python3
"""H7 (UL): protocol-to-ticker mapping and the unlock-event extraction rule (reports/hunt/h7ul/SPEC.md).

Committed BEFORE any price was loaded. Inputs: DefiLlama's free dataset CDN (data/hunt/h7ul/emissions/*.json.gz,
fetched by fetch_unlocks.py on Actions). Output: reports/hunt/h7ul/events.csv (schedule-only; no prices).

RULE (fixed)
1. Series. For each section of documentedData, the cumulative `unlocked` tokens at 00:00 UTC each day (forward-filled
   onto a daily calendar). A step that appears at the series date t happened in (t-1 00:00, t 00:00] UTC.
2. Circulating supply C(t) = sum of `unlocked` over sections whose DefiLlama category is neither "noncirculating" nor
   "burned" (DefiLlama's own split; uncategorised sections count as circulating). Source: DefiLlama for every mapped
   coin (no CoinGecko/Coinbase fallback was needed).
3. Eligible increase dU(t) = sum over eligible sections of max(0, unlocked(t) - unlocked(t-1)). Eligible sections:
   every section except (a) "burned", (b) "noncirculating" (treasury tokens that stay out of circulation by DefiLlama's
   classification), (c) sections DefiLlama documents as REALISED TRANSFERS rather than a published schedule (their
   dates are known only after the fact, so trading d1 days ahead would be look-ahead):
       chainlink "Node Operators & Company", hyperliquid "Core Contributors", ethereum "Ethereum Foundation".
   Team/investor subset: eligible sections whose category is "insiders" or "privateSale".
4. A qualifying day t: dU(t) >= X * C(t - 30), with C(t - 30) > 0 (so a TGE is never an unlock event).
   Linear vesting whose daily step is below X never qualifies.
5. Events. Qualifying days of one coin no more than 7 days after the previous qualifying day form one event; the
   unlock date U is the first day of the run. size = dU(U) / C(U - 30); size_run = sum over the run.
   Category filter "ti" (team/investor) applies steps 3-5 to the team/investor subset only.
6. Thresholds X in {1%, 2.5%} (SPEC). events.csv lists every event at X = 1% with its size, so the 2.5% set is the
   subset with size >= 2.5% computed on the same per-day rule (a 2.5% run starts on its first >= 2.5% day).
Trade timing (sim.py): entry 16:00 UTC on U - d1, exit 16:00 UTC on U + d2 (d2 = 0 exits 16 h after the latest
possible unlock instant).
"""
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
EMI = os.path.join(ROOT, "data", "hunt", "h7ul", "emissions")
OUT = os.path.join(ROOT, "reports", "hunt", "h7ul")

# ---------------------------------------------------------------- the hand-made mapping (common.PERP coins)
MAP = {  # coin -> (DefiLlama protocol slug, DefiLlama gecko_id, note)
    "BTC": ("bitcoin", "bitcoin", "mining emission only"),
    "ETH": ("ethereum", None, "EF section = realised outflows (excluded); rest emission/linear"),
    "SOL": ("solana", "solana", ""),
    "DOGE": ("dogecoin", "dogecoin", "mining emission only"),
    "LTC": ("litecoin", "litecoin", "mining emission only"),
    "AVAX": ("avalanche", "avalanche-2", "quarterly schedule; seed/private dates = latest described (DefiLlama note)"),
    "LINK": ("chainlink", "chainlink", "only unlock section is realised transfers (excluded) -> no events"),
    "SUI": ("sui-foundation", "sui", "approximated from Sui's token schedule chart (DefiLlama note)"),
    "HBAR": ("hedera", "hedera-hashgraph", "quarterly treasury schedule"),
    "NEAR": ("near-protocol", "near", ""),
    "AAVE": ("aave", "aave", ""),
    "HYPE": ("hyperliquid", "hyperliquid", "Core Contributors = realised transfers from HyperLabs (excluded)"),
    "ENA": ("ethena", "ethena", "schedule from Ethena CSV (May 2024); cliffs linearised over a month"),
    "ONDO": ("ondo-finance", "ondo-finance", "annual Jan-18 cliffs"),
    "DOT": ("polkadot-treasury", "polkadot", ""),
    "BNB": ("binance-smart-chain", "binancecoin", ""),
}
UNMAPPED = {  # in common.PERP but no dataset on DefiLlama's free CDN (373 protocols, Nov 7 2026)
    "XRP": "no DefiLlama dataset (escrow releases not in the free CDN; not hand-added: SPEC fixes the data source)",
    "ADA": "no DefiLlama dataset", "BCH": "no DefiLlama dataset", "XLM": "no DefiLlama dataset",
    "PEPE": "no DefiLlama dataset", "ZEC": "no DefiLlama dataset", "SHIB": "no DefiLlama dataset",
}
REALISED = {("chainlink", "Node Operators & Company"), ("hyperliquid", "Core Contributors"),
            ("ethereum", "Ethereum Foundation")}
TI_CATS = {"insiders", "privateSale"}
OUT_OF_CIRC = {"noncirculating", "burned"}
LOOKBACK = 30
MERGE_GAP = 7
X_MIN = 0.01


def load_protocol(slug):
    js = json.loads(gzip.open(os.path.join(EMI, f"{slug}.json.gz")).read())
    cats = js.get("categories") or {}
    lab2cat = {lab: k for k, v in cats.items() for lab in v}
    cols = {}
    for sec in js["documentedData"]["data"]:
        idx = pd.to_datetime([q["timestamp"] for q in sec["data"]], unit="s").normalize()
        s = pd.Series([float(q["unlocked"]) for q in sec["data"]], index=idx)
        cols[sec["label"]] = s[~s.index.duplicated(keep="last")]
    df = pd.DataFrame(cols).sort_index()
    df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="D")).ffill().fillna(0.0)
    return js, df, lab2cat


def daily_terms(slug):
    """Circulating supply C(t), eligible increase dU(t) (all / team-investor) per day."""
    js, df, lab2cat = load_protocol(slug)
    circ_cols = [c for c in df if lab2cat.get(c) not in OUT_OF_CIRC]
    elig = [c for c in circ_cols if (slug, c) not in REALISED]
    ti = [c for c in elig if lab2cat.get(c) in TI_CATS]
    inc = df.diff().clip(lower=0).fillna(0.0)
    C = df[circ_cols].sum(axis=1)
    out = pd.DataFrame({"C": C, "C30": C.shift(LOOKBACK), "dU_all": inc[elig].sum(axis=1),
                        "dU_ti": inc[ti].sum(axis=1) if ti else 0.0})
    out["sections"] = ""
    return out, lab2cat, elig


def extract(slug, coin, X=X_MIN):
    T, lab2cat, elig = daily_terms(slug)
    rows = []
    for cat in ("all", "ti"):
        frac = (T[f"dU_{cat}"] / T["C30"]).where(T["C30"] > 0)
        q = frac[frac >= X].dropna()
        run, prev = [], None
        runs = []
        for t, v in q.items():
            if prev is not None and (t - prev).days > MERGE_GAP:
                runs.append(run)
                run = []
            run.append((t, v))
            prev = t
        if run:
            runs.append(run)
        for r in runs:
            U = r[0][0]
            rows.append(dict(coin=coin, protocol=slug, cat=cat, U=U.date(), size=round(float(r[0][1]), 6),
                             size_run=round(float(sum(v for _, v in r)), 6), run_days=len(r),
                             run_end=r[-1][0].date(), C30=float(T.loc[U, "C30"])))
    return rows


def build(X=X_MIN):
    rows = []
    for coin, (slug, _, _) in MAP.items():
        rows += extract(slug, coin, X)
    ev = pd.DataFrame(rows).sort_values(["U", "coin", "cat"]).reset_index(drop=True)
    return ev


def events_for(ev_all, X, cat):
    """The event set for threshold X and category filter cat ("all" or "ti"). For X above X_MIN the runs are
    re-extracted at X so that a run starts on its first day >= X."""
    if abs(X - X_MIN) < 1e-12:
        e = ev_all[ev_all.cat == cat]
    else:
        e = build(X)
        e = e[e.cat == cat]
    return e.reset_index(drop=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    ev = build(X_MIN)
    ev25 = build(0.025)
    ev["X"] = 0.01
    ev25["X"] = 0.025
    allv = pd.concat([ev, ev25], ignore_index=True)
    allv.to_csv(os.path.join(OUT, "events.csv"), index=False)
    m = pd.DataFrame([dict(coin=c, protocol=p, gecko_id=g, note=n) for c, (p, g, n) in MAP.items()] +
                     [dict(coin=c, protocol="", gecko_id="", note=n) for c, n in UNMAPPED.items()])
    m.to_csv(os.path.join(OUT, "mapping.csv"), index=False)
    print(allv.groupby(["X", "cat", "coin"]).size().unstack(0).fillna(0).astype(int).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
