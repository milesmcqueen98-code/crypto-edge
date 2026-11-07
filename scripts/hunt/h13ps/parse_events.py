#!/usr/bin/env python3
"""H13 (PS) step 2 - local, no internet, no prices. Builds the event table reports/hunt/h13ps/events.csv from the raw
status-page incident history (data/hunt/h13ps/status/details.jsonl.gz) and product metadata (data/hunt/h13ps/meta/,
copied from builder h4nl's branch: Exchange /products, /currencies, Advanced products, and h4nl's per-product first
and last trading days from daily candles - no prices).

Phase statements: every incident update is split into sentences; a sentence that states a phase (transfers,
auction, post-only, limit-only, full trading, cancel-only/paused) in the present or past tense is attributed to the
product ids it names (XYZ-USD), or, if it names none, to the USD pair of each ticker it names, or, failing that, to
the tickers in the incident title. A future-tense sentence ("will move ... at 10:00 PT") is an announcement and is
kept only as a note. The time of a phase is the update's display time (display_at, else created_at).

Per USD pair, the listing episode is anchored on the first auction / post-only / limit-only statement within 3 days
of the pair's first trading day (h4nl's daily candles); T_lo = first limit-only statement of the episode, T_ft =
first full-trading statement after T_lo (within 30 days). Universe (SPEC): USD pairs with both, T_lo in
2022-01-01 .. 2026-11-05; excluded: stablecoins, fiat-backed and wrapped/staked assets (h4nl's lists and name
rules), relistings (base traded on Coinbase before 2022, ticker migrations, or the USD pair's first trade more than
3 days before T_lo).

usage: python scripts/hunt/h13ps/parse_events.py
"""
import gzip
import html
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ST = os.path.join(ROOT, "data", "hunt", "h13ps", "status")
META = os.path.join(ROOT, "data", "hunt", "h13ps", "meta")
OUT = os.path.join(ROOT, "reports", "hunt", "h13ps")
START, END = pd.Timestamp("2022-01-01"), pd.Timestamp("2026-11-05 23:59:59")

# ---------------------------------------------------------------- exclusion rules (copied from h4nl listings.py)
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
MIGRATIONS = {
    "POL": ["MATIC"], "RENDER": ["RNDR"], "SKY": ["MKR"], "A": ["EOS"], "S": ["FTM"], "T": ["NU", "KEEP"],
    "SYRUP": ["MPL"], "FET": ["AGIX", "OCEAN"], "ASI": ["FET", "AGIX", "OCEAN"], "CELO": ["CGLD"],
    "CFG": ["WCFG"], "AEVO": ["RBN"], "POLYX": ["POLY"], "XCN": ["CHAIN"], "LUNA": ["LUNC", "WLUNA"],
    "G": ["GAL"], "MANTLE": ["BIT"], "ZETACHAIN": ["ZETA"], "AXL": ["WAXL"],
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


# ---------------------------------------------------------------- phase statements
PHASES = [  # (phase, regex); a sentence may state several
    ("fulltrading", re.compile(r"full[\s-]*trading|limit,?\s+market,?\s+and\s+stop\s+orders\s+are\s+(all\s+)?now",
                               re.I)),
    ("limitonly", re.compile(r"limit[\s-]*only", re.I)),
    ("postonly", re.compile(r"post[\s-]*only", re.I)),
    ("auction", re.compile(r"\bauction", re.I)),
    ("cancelonly", re.compile(r"cancel[\s-]*only|have been paused|has been paused|failed to meet", re.I)),
    ("transfers", re.compile(r"(inbound\s+)?transfers?\b.*\b(available|enabled|open)|deposits?\b.*\b(available|"
                             r"enabled|open)", re.I)),
]
FUTURE = re.compile(r"\b(will(?!\s+now)|expect|expected|scheduled|anticipate|plan(ned)?|upcoming|later today|"
                    r"tomorrow|approximately|no earlier than|at the earliest|once|if|until|when)\b", re.I)
PID = re.compile(r"\b([A-Z0-9]{1,15})-(USD|USDT|USDC|EUR|GBP|BTC|ETH|DAI)\b")
TICK = re.compile(r"\b([A-Z][A-Z0-9]{1,14})\b")


def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sentences(body):
    return [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z@])", clean(body)) if x]


def incident_of(rec):
    d = rec.get("data") or {}
    if isinstance(d, dict) and "incident" in d and isinstance(d["incident"], dict):
        return d["incident"]
    return d if isinstance(d, dict) else {}


def statements(D, known_bases):
    """One row per (incident update sentence, phase, product)."""
    rows = []
    for rec in D:
        inc = incident_of(rec)
        name = clean(inc.get("name", ""))
        title_tickers = [t for t in TICK.findall(name) if t in known_bases]
        for u in inc.get("incident_updates", []) or []:
            ts = u.get("display_at") or u.get("created_at")
            if not ts:
                continue
            t = pd.Timestamp(ts).tz_convert(None) if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts)
            for snt in sentences(u.get("body", "")):
                ph = [p for p, rx in PHASES if rx.search(snt)]
                if not ph:
                    continue
                fut = bool(FUTURE.search(snt))
                pids = sorted(set("-".join(m) for m in PID.findall(snt)))
                src = "pid"
                if not pids:
                    tk = [x for x in TICK.findall(snt) if x in known_bases]
                    if tk:
                        pids, src = [f"{x}-USD" for x in sorted(set(tk))], "ticker"
                    elif title_tickers:
                        pids, src = [f"{x}-USD" for x in sorted(set(title_tickers))], "title"
                for p in ph:
                    for pid in pids:
                        rows.append(dict(code=rec["code"], incident=name, t=t, created=u.get("created_at"),
                                         display=u.get("display_at"), status=u.get("status"), phase=p,
                                         future=fut, pid=pid, src=src, sentence=snt[:300]))
    return pd.DataFrame(rows)


def load_details():
    D = []
    with gzip.open(os.path.join(ST, "details.jsonl.gz"), "rt") as f:
        for line in f:
            D.append(json.loads(line))
    return D


def main():
    D = load_details()
    ex = json.load(open(os.path.join(META, "products_exchange.json")))
    cur = json.load(open(os.path.join(META, "currencies_exchange.json")))
    adv = {p["product_id"]: p for p in json.load(open(os.path.join(META, "products_adv.json")))}
    names = {c["id"]: c.get("name") for c in cur}
    U = pd.read_csv(os.path.join(META, "h4_universe_all.csv"), parse_dates=["first_day", "last_day", "other_first"])
    P = pd.DataFrame(ex)
    P["base"] = P.base_currency.str.upper()
    known = set(P.base) | set(U.base)
    S = statements(D, known)
    os.makedirs(OUT, exist_ok=True)
    S.sort_values(["pid", "t"]).to_csv(os.path.join(OUT, "phase_statements.csv"), index=False)
    print(f"{len(D)} incidents; {len(S)} phase statements; by phase {S.phase.value_counts().to_dict()}")
    E = episodes(S, P, U, names, adv)
    E.to_csv(os.path.join(OUT, "events.csv"), index=False)
    print(f"USD pairs with a limit-only statement near their first trading day: {len(E)}; in universe "
          f"{int(E.in_universe.sum())}")
    print(E.reason.replace("", "IN").value_counts().to_string())
    print(E[E.in_universe].groupby(E.T_lo.dt.year).size().to_string())
    return E


def episodes(S, P, U, names, adv):
    """One row per USD pair: its opening episode (anchored on the pair's first trading day)."""
    S = S[~S.future & S.pid.str.endswith("-USD")].copy()
    Uk = U.set_index("pid")
    Pk = P.set_index("id")
    by_base = {b: g for b, g in P.groupby("base")}
    rows = []
    for pid, g in S.groupby("pid"):
        g = g.sort_values("t")
        base = pid[:-4]
        fd = Uk.first_day.get(pid) if pid in Uk.index else pd.NaT
        lo = g[g.phase == "limitonly"]
        if pd.notna(fd):
            lo = lo[(lo.t >= fd - pd.Timedelta(days=2)) & (lo.t < fd + pd.Timedelta(days=4))]
        else:                                   # no candle history: the first limit-only statement of an opening
            lo = lo[lo.incident.str.contains(r"open|listing|launch|new", case=False, regex=True)]
        if lo.empty:
            continue
        T_lo = lo.t.iloc[0]
        ftg = g[(g.phase == "fulltrading") & (g.t > T_lo) & (g.t <= T_lo + pd.Timedelta(days=30))]
        T_ft = ftg.t.iloc[0] if len(ftg) else pd.NaT
        pre = g[(g.t <= T_lo) & (g.t >= T_lo - pd.Timedelta(days=3))]
        def first(ph):
            x = pre[pre.phase == ph]
            return x.t.iloc[0] if len(x) else pd.NaT
        pend = g[(g.phase == "cancelonly") & (g.t > T_lo) & ((g.t < T_ft) if pd.notna(T_ft) else True)]
        name = names.get(base) or (adv.get(pid) or {}).get("base_name") or ""
        r = dict(key=f"{base}_{T_lo:%Y%m%d%H%M}", pid=pid, base=base, name=name, T_transfer=first("transfers"),
                 T_auction=first("auction"), T_postonly=first("postonly"), T_lo=T_lo, T_ft=T_ft,
                 lo_dur_h=(T_ft - T_lo).total_seconds() / 3600 if pd.notna(T_ft) else np.nan,
                 cancel_only_between=int(len(pend)), first_day=fd,
                 status_now=Pk.status.get(pid, ""), tick_now=float(Pk.quote_increment.get(pid, np.nan)),
                 code_lo=lo.code.iloc[0], code_ft=ftg.code.iloc[0] if len(ftg) else "",
                 src_lo=lo.src.iloc[0], src_ft=ftg.src.iloc[0] if len(ftg) else "",
                 sent_lo=lo.sentence.iloc[0][:200], sent_ft=ftg.sentence.iloc[0][:200] if len(ftg) else "")
        reason = rule_exclusion(base, name)
        h4 = Uk.loc[pid] if pid in Uk.index else None
        if not reason and h4 is not None and isinstance(h4.reason, str) and h4.reason:
            reason = h4.reason                  # h4nl: listed before 2022, relisting, migration, never traded
        if not reason and h4 is None:
            others = by_base.get(base)
            if others is not None and len(others) > 1:
                reason = ""                     # USD pair unknown to h4nl's table: kept, flagged below
        if not reason and pd.isna(T_ft):
            reason = "no full-trading statement"
        if not reason and not (START <= T_lo <= END):
            reason = "outside 2022-01-01 .. 2026-11-05"
        if not reason and T_ft <= T_lo:
            reason = "T_ft before T_lo"
        r["reason"] = reason
        r["in_h4_table"] = h4 is not None
        rows.append(r)
    E = pd.DataFrame(rows).sort_values("T_lo").reset_index(drop=True)
    E["in_universe"] = E.reason == ""
    return E


if __name__ == "__main__":
    main()
