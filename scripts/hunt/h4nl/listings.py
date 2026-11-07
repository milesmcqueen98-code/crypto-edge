#!/usr/bin/env python3
"""H4 (NL) universe rules: which Coinbase USD spot products count as NEW LISTINGS (reports/hunt/h4nl/SPEC.md).

Written and committed BEFORE any price was fetched or looked at. The rules use product metadata only (ticker, name,
status, first/last trading day from daily candles; no prices):

1. Quote currency USD, any status (delisted products are KEPT: survivorship-free).
2. Excluded as stablecoins / fiat-, commodity- or asset-backed: a fixed ticker list (SPEC's examples plus the ones we
   know), any ticker containing "USD" or starting "EUR", and names matching USD/Dollar/Euro/Yen/Gold/Treasury.
3. Excluded as wrapped or staked assets: a fixed ticker list, and any name containing Wrapped/Staked/Bridged/Restaked
   (literal SPEC rule: this also drops wrapped tokens whose underlying was never on Coinbase, e.g. WAXL, WCFG).
4. Excluded as relistings or older listings: the USD product's first trade is before 2022-01-01, or ANY Coinbase
   product of the same base (any quote) first traded before 2022-01-01, or the base is a ticker migration/rename of
   a token that already traded on Coinbase (fixed list below, checked against the product list). A USD pair added
   later to a 2022+ listing on another quote is KEPT (SPEC: every USD product first traded 2022+) and flagged.
5. No first trade at all (never traded) -> dropped.
Listing time t0 = first 1-minute candle with volume (set after the minute fetch; cross-checked against Advanced
Trade's `new_at`, which is a 2023-01-01 placeholder for older products).

  python scripts/hunt/h4nl/listings.py merge      (local, no internet: merges the universe shards into the table)
"""
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DATA = os.path.join(ROOT, "data", "hunt", "h4nl")
OUT = os.path.join(ROOT, "reports", "hunt", "h4nl")
CUTOFF = pd.Timestamp("2022-01-01")

# ---------------------------------------------------------------- fixed exclusion lists (no prices consulted)
STABLE = {  # stablecoins, fiat-, commodity- and asset-backed tokens
    "USDT", "USDC", "DAI", "PYUSD", "USDS", "GUSD", "EURC", "EUROC", "USDP", "PAX", "BUSD", "TUSD", "UST", "USTC",
    "USDD", "FDUSD", "RLUSD", "USD1", "USDE", "SUSDE", "USDG", "AUSD", "USDY", "USDM", "GYEN", "ZUSD", "LUSD", "FRAX",
    "GHO", "CRVUSD", "MUSD", "SUSD", "XSGD", "EURT", "AGEUR", "EURA", "EURCV", "PAXG", "XAUT", "CADC", "OUSG", "BUIDL",
    "USYC", "USR", "DOLA", "MIM", "FEI", "HUSD", "USDK", "USDX", "SAI", "RAI",
}
WRAPPED = {  # wrapped, bridged and liquid-staking tokens
    "CBBTC", "CBETH", "WBTC", "WETH", "LSETH", "MSOL", "JITOSOL", "RETH", "STETH", "WSTETH", "CBDOGE", "CBXRP",
    "CBADA", "CBLTC", "CBSOL", "CBDOT", "WAMPL", "WAXL", "WCFG", "WLUNA", "BSOL", "JUPSOL", "WEETH", "EZETH", "TBTC",
    "LBTC", "SOLVBTC", "CBXLM",
}
# ticker migrations / renames: new ticker -> predecessor tickers; excluded if a predecessor has any Coinbase product
MIGRATIONS = {
    "POL": ["MATIC"], "RENDER": ["RNDR"], "SKY": ["MKR"], "A": ["EOS"], "S": ["FTM"], "T": ["NU", "KEEP"],
    "SYRUP": ["MPL"], "FET": ["AGIX", "OCEAN"], "ASI": ["FET", "AGIX", "OCEAN"], "CELO": ["CGLD"],
    "CFG": ["WCFG"], "AEVO": ["RBN"], "POLYX": ["POLY"], "XCN": ["CHAIN"], "LUNA": ["LUNC", "WLUNA"],
    # added after reading the product/currency metadata (names and first trading days only; no prices seen):
    # the same asset already had a Coinbase market under another ticker, so the book was not new
    "G": ["GAL"],                  # Galxe: GAL -> G (Gravity)
    "MANTLE": ["BIT"],             # BitDAO BIT -> Mantle MNT
    "ZETACHAIN": ["ZETA"],         # ZetaChain: ERC-20 ZETA-USD (2024-02) then native ZETACHAIN-USD (2024-09)
    "AXL": ["WAXL"],               # Axelar traded as Wrapped Axelar (2022-10) before the native AXL pair (2023-02)
}
NOT_STABLE = {"CHIP"}              # CHIP: USD.AI's governance token (the currency name is the protocol's, "USD.AI")
RE_STABLE_NAME = re.compile(r"\b(usd|us dollar|dollar|euro|yen|gold|treasury|treasuries|stablecoin)\b", re.I)
RE_WRAPPED_NAME = re.compile(r"\b(wrapped|staked|bridged|restaked)\b", re.I)


def rule_exclusion(base, name):
    """Ticker/name rules (2) and (3). Returns a reason string or ''."""
    b = (base or "").upper()
    n = name or ""
    if b in NOT_STABLE:
        return ""
    if b in STABLE:
        return "stable/fiat/asset-backed (list)"
    if "USD" in b or b.startswith("EUR"):
        return "stable/fiat-backed (ticker)"
    if RE_STABLE_NAME.search(n):
        return "stable/fiat/asset-backed (name)"
    if b in WRAPPED:
        return "wrapped/staked (list)"
    if RE_WRAPPED_NAME.search(n):
        return "wrapped/staked (name)"
    return ""


def load_meta():
    ex = json.load(open(os.path.join(DATA, "products_exchange.json")))
    cur = json.load(open(os.path.join(DATA, "currencies_exchange.json")))
    adv = json.load(open(os.path.join(DATA, "products_adv.json")))
    names = {c["id"]: c.get("name") for c in cur}
    adv_map = {p["product_id"]: p for p in adv}
    return ex, names, adv_map


def merge():
    """Build the listing table from the universe shards (first/last trading day of every product of every candidate
    base, from daily candles; no prices are stored)."""
    ex, names, adv = load_meta()
    days = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(DATA, "universe_days_*.csv")))])
    days["first_day"] = pd.to_datetime(days.first_day)
    days["last_day"] = pd.to_datetime(days.last_day)
    fd = days.set_index("pid")
    P = pd.DataFrame(ex)
    P["base"] = P.base_currency.str.upper()
    by_base = {b: g for b, g in P.groupby("base")}
    rows = []
    for p in P[P.quote_currency == "USD"].itertuples():
        b = p.base
        name = names.get(p.base_currency) or adv.get(p.id, {}).get("base_name") or ""
        a = adv.get(p.id, {})
        r = dict(pid=p.id, base=b, name=name, status=p.status, tick=float(p.quote_increment),
                 base_increment=float(p.base_increment), new_at=a.get("new_at"), adv_status=a.get("status"),
                 first_day=pd.NaT, last_day=pd.NaT, n_days=0, other_first=pd.NaT, reason="")
        if p.id in fd.index:
            q = fd.loc[p.id]
            r.update(first_day=q.first_day, last_day=q.last_day, n_days=int(q.n_days))
        others = by_base[b][by_base[b].id != p.id]
        of = [fd.loc[o, "first_day"] for o in others.id if o in fd.index and pd.notna(fd.loc[o, "first_day"])]
        r["other_first"] = min(of) if of else pd.NaT
        reason = rule_exclusion(b, name)
        if not reason and pd.isna(r["first_day"]):
            reason = "never traded"
        if not reason and r["first_day"] < CUTOFF:
            reason = "listed before 2022"
        if not reason and pd.notna(r["other_first"]) and r["other_first"] < CUTOFF:
            reason = "base traded on Coinbase before 2022 (relisting)"
        # kept (the SPEC's universe is every USD product first traded in 2022+), but flagged
        r["usd_after_other"] = bool(pd.notna(r["other_first"]) and r["other_first"] < r["first_day"] - pd.Timedelta(days=1))
        if not reason and b in MIGRATIONS:
            pred = [o for o in MIGRATIONS[b] if o in by_base]
            if pred:
                reason = f"ticker migration from {'/'.join(pred)}"
        r["reason"] = reason
        rows.append(r)
    T = pd.DataFrame(rows).sort_values(["first_day", "pid"]).reset_index(drop=True)
    T["in_universe"] = T.reason == ""
    os.makedirs(OUT, exist_ok=True)
    T.to_csv(os.path.join(OUT, "universe_all.csv"), index=False)
    U = T[T.in_universe].copy()
    U["delisted_now"] = U.status.eq("delisted")
    U.to_csv(os.path.join(DATA, "listings_pre.csv"), index=False)
    print(f"USD products {len(T)}; universe (first trade >= 2022, rules passed) {len(U)}; "
          f"delisted now {int(U.delisted_now.sum())}")
    print(T.reason.replace("", "IN").value_counts().to_string())
    print(U.groupby(U.first_day.dt.year).size().to_string())
    return T


if __name__ == "__main__":
    if sys.argv[1] == "merge":
        merge()
