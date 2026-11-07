#!/usr/bin/env python3
"""H12 (LT) universe (reports/hunt/h12lt/SPEC.md), fixed from 2024 data before any P&L.

  screen    2024 volume screen from Exchange daily candles of every USD pair (delisted ones included):
            median daily USD volume (close x base volume) over the pair's 2024 days with a candle (days it traded),
            kept if $0.5M <= median < $3M, not one of the wide set's 31 coins, not a stablecoin / fiat-backed / wrapped
            / staked / pegged asset. -> data/hunt/h12lt/candidates.csv and reports/hunt/h12lt/screen.csv (every pair,
            with its reason).
  finalize  adds each candidate's est_tick (scripts/wick1m/trades_wide.py rule, computed on the fetched 1-minute
            candles by fetch.py) and keeps tick <= 3 bp; at most 80 coins by 2024 volume.
            -> reports/hunt/h12lt/universe.csv
usage: python scripts/hunt/h12lt/universe.py screen|finalize [data_dir]
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
OUT = os.path.join(ROOT, "reports", "hunt", "h12lt")
VOL_LO, VOL_HI, TICK_BP_MAX, MAX_COINS = 0.5e6, 3e6, 3.0, 80

# Fixed exclusion lists (taken over from builder h4nl's listings.py; ticker/name rules, no prices consulted)
STABLE = {
    "USDT", "USDC", "DAI", "PYUSD", "USDS", "GUSD", "EURC", "EUROC", "USDP", "PAX", "BUSD", "TUSD", "UST", "USTC",
    "USDD", "FDUSD", "RLUSD", "USD1", "USDE", "SUSDE", "USDG", "AUSD", "USDY", "USDM", "GYEN", "ZUSD", "LUSD", "FRAX",
    "GHO", "CRVUSD", "MUSD", "SUSD", "XSGD", "EURT", "AGEUR", "EURA", "EURCV", "PAXG", "XAUT", "CADC", "OUSG", "BUIDL",
    "USYC", "USR", "DOLA", "MIM", "FEI", "HUSD", "USDK", "USDX", "SAI", "RAI",
}
WRAPPED = {
    "CBBTC", "CBETH", "WBTC", "WETH", "LSETH", "MSOL", "JITOSOL", "RETH", "STETH", "WSTETH", "CBDOGE", "CBXRP",
    "CBADA", "CBLTC", "CBSOL", "CBDOT", "WAMPL", "WAXL", "WCFG", "WLUNA", "BSOL", "JUPSOL", "WEETH", "EZETH", "TBTC",
    "LBTC", "SOLVBTC", "CBXLM",
}
NOT_STABLE = {"CHIP"}
RE_STABLE_NAME = re.compile(r"\b(usd|us dollar|dollar|euro|yen|gold|treasury|treasuries|stablecoin)\b", re.I)
RE_WRAPPED_NAME = re.compile(r"\b(wrapped|staked|bridged|restaked)\b", re.I)


def rule_exclusion(base, name):
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


def wide31():
    p = os.path.join(ROOT, "reports", "wick1m", "spot_ticks_wide.csv")
    if not os.path.exists(p):                       # sparse worktree: the main clone's copy (read-only)
        p = "/home/claude/crypto-edge/reports/wick1m/spot_ticks_wide.csv"
    T = pd.read_csv(p)
    return set(T.coin[T.used.astype(bool)])


def screen(ddir):
    ex = json.load(open(os.path.join(ddir, "products_exchange.json")))
    cur = json.load(open(os.path.join(ddir, "currencies_exchange.json")))
    names = {c["id"]: c.get("name") for c in cur}
    d = pd.read_csv(os.path.join(ddir, "daily2024.csv"), parse_dates=["day"])
    d = d[(d.volume > 0) & (d.day >= "2024-01-01") & (d.day < "2025-01-01")]
    d["usd"] = d.close * d.volume
    g = d.groupby("pid").agg(vol2024=("usd", "median"), n_days=("usd", "size"), first_day=("day", "min"),
                             last_day=("day", "max"))
    W = wide31()
    rows = []
    for p in ex:
        if p["quote_currency"] != "USD":
            continue
        base = p["base_currency"].upper()
        r = dict(pid=p["id"], coin=base, name=names.get(p["base_currency"]) or "", status=p["status"],
                 quote_increment=float(p["quote_increment"]))
        if p["id"] in g.index:
            r.update(g.loc[p["id"]].to_dict())
        else:
            r.update(vol2024=np.nan, n_days=0)
        reason = ""
        if r["n_days"] == 0:
            reason = "no 2024 trading"
        elif base in W:
            reason = "wide-set coin"
        elif base == "BTC":
            reason = "BTC"
        else:
            reason = rule_exclusion(base, r["name"])
            if not reason and r["vol2024"] < VOL_LO:
                reason = "2024 median volume < $0.5M"
            elif not reason and r["vol2024"] >= VOL_HI:
                reason = "2024 median volume >= $3M"
        r["reason"] = reason
        rows.append(r)
    S = pd.DataFrame(rows).sort_values("vol2024", ascending=False)
    os.makedirs(OUT, exist_ok=True)
    S.to_csv(os.path.join(OUT, "screen.csv"), index=False)
    C = S[S.reason == ""].copy()
    assert C.coin.is_unique
    C[["pid", "coin", "name", "status", "vol2024", "n_days", "first_day", "last_day", "quote_increment"]].to_csv(
        os.path.join(ddir, "candidates.csv"), index=False)
    print(S.reason.replace("", "CANDIDATE").value_counts().to_string())
    print(f"{len(C)} candidates ({(C.status == 'delisted').sum()} delisted now)")


def finalize(ddir):
    C = pd.read_csv(os.path.join(ddir, "candidates.csv"))
    T = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(ddir, "ticks_*.csv")))], ignore_index=True)
    U = C.merge(T[["coin", "tick", "tick_bp", "n_tick_rows", "n_min"]], on="coin", how="left")
    U["reason"] = np.where(U.n_min.fillna(0) <= 0, "no 1-minute candles",
                           np.where(~(U.tick_bp <= TICK_BP_MAX), "tick > 3 bp", ""))
    ok = U[U.reason == ""].sort_values("vol2024", ascending=False)
    dropped = max(0, len(ok) - MAX_COINS)
    keep = set(ok.coin.head(MAX_COINS))
    U.loc[(U.reason == "") & ~U.coin.isin(keep), "reason"] = "beyond the 80 largest"
    U.sort_values("vol2024", ascending=False).to_csv(os.path.join(OUT, "universe_screen.csv"), index=False)
    out = U[U.coin.isin(keep)].sort_values("coin")
    out[["coin", "pid", "name", "status", "vol2024", "n_days", "tick", "tick_bp", "quote_increment", "n_min"]].to_csv(
        os.path.join(OUT, "universe.csv"), index=False)
    print(U.reason.replace("", "UNIVERSE").value_counts().to_string())
    print(f"universe: {len(out)} coins ({(out.status == 'delisted').sum()} delisted); dropped beyond 80: {dropped}")


if __name__ == "__main__":
    ddir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "data", "hunt", "h12lt")
    {"screen": screen, "finalize": finalize}[sys.argv[1]](ddir)
