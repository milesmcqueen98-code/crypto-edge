#!/usr/bin/env python3
"""H5 (AN) step 2: classify Binance catalog-48 titles and extract tickers. Titles only; no prices.

Written and committed before any Coinbase price around an event is fetched (reports/hunt/h5an/SPEC.md).

Classes (first match wins; fixed here before any price is seen):
  iv  HODLer Airdrops / Launchpool / Megadrop / Launchpad
  v   routine or non-token items: options, copy trading, quarterly/delivery futures, bStocks/tokenized securities,
      TradFi perps, trading bots, plain trading-pair additions, delistings, postponements, leverage updates
  i   spot listing: "Will List" (not Binance Futures/Options)
  ii  perp launch: "Binance Futures Will Launch|to Relaunch|Will List ... Perpetual", or
      "... Will Be Available on Binance Alpha and Binance Futures"
  iii margin / earn / convert additions: "Will Add|Adds ... (Margin|Earn|Convert)", "Binance Margin (Will )?Adds?"
  v   everything else

Tickers:
  - parentheses "(TICKER)" when the title has any (classes i, iii, iv, ii-Alpha);
  - perp titles: the contract list between the margin label and "Perpetual", suffixes USDT/USDC/BUSD stripped
    (and USD for COIN-M), e.g. "GRASSUSDT, DRIFTUSDT, and SWELLUSDT" -> GRASS, DRIFT, SWELL;
  - bare margin lists ("Binance Adds X, Y on Cross Margin and Z on Isolated Margin"): all-caps tokens before
    "More"/"Delisting"; "X/Y" pair mentions are pair additions, not new assets, and are skipped.
  - Binance multiplier tickers (1000PEPE, 1000000MOG, 1MBABYDOGE) map to the base token when only that exists on
    Coinbase.
Excluded tokens (no price-discovery mechanism): stablecoins, fiat-pegged, gold-pegged, wrapped/staked duplicates.
Ticker collisions (same ticker, different token on Coinbase): resolved with names, see COLLISIONS below.

usage: python scripts/hunt/h5an/events.py      -> data/hunt/h5an/events.csv, reports/hunt/h5an/event_counts.csv
"""
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
D = os.path.join(ROOT, "data", "hunt", "h5an")
R = os.path.join(ROOT, "reports", "hunt", "h5an")

# ------------------------------------------------------------------ fixed patterns (before any price)
RE_IV = re.compile(r"HODLer Airdrops?|Launchpool|Megadrop|Launchpad", re.I)
RE_V = re.compile(r"\bOptions\b|Copy Trading|Quarterly|Delivery Contract|bStocks|Tokeni[sz]ed|TradFi|Trading Bots"
                  r"|Trading Pairs?\b|Spot Trading Pair|Delist|Postpone|Will Cancel|Leverage & Margin Tiers"
                  r"|Will Convert|Removal|Fiat|Collateral", re.I)
RE_I = re.compile(r"^(?!Binance (Futures|Options)\b).*\bWill List\b")
RE_II = re.compile(r"^Binance Futures (Will Launch|to Relaunch|Will List)\b.*\bPerpetual|"
                   r"Will Be Available on Binance Alpha and Binance Futures")
RE_III = re.compile(r"\b(Will Add|Adds)\b.*\b(Margin|Earn|Convert)\b|^Binance Margin (Will )?Adds?\b")
# Trading-pair-only titles are routine (new quote currencies for listed tokens) unless they add a margin asset.
RE_PAIRS_ONLY = re.compile(r"Trading Pairs?\b", re.I)

RE_PAREN = re.compile(r"\(([^()]{1,24})\)")
RE_TOKEN = re.compile(r"^[A-Z0-9]{1,15}$")
RE_PERP_SEG = re.compile(r"(?:USD[ⓈT]?-M(?:argined)?|USDC-M(?:argined)?|BUSD-M(?:argined)?|Coin-M(?:argined)?|"
                         r"COIN-M(?:argined)?)\s+(.*?)\s+Perpetual|Will Launch\s+(.*?)\s+Perpetual", re.I)
STOP = {"USDⓈ", "M", "COIN", "AND", "USD", "NEW", "BINANCE", "ON", "THE"}

EXCLUDE = {  # stable / pegged / wrapped: an announcement cannot reprice them (fetch_data.EXCLUDE + Binance extras)
    "USDT", "USDC", "DAI", "PYUSD", "GUSD", "PAX", "USDP", "BUSD", "TUSD", "UST", "USTC", "FDUSD", "USDE", "USDS",
    "EURC", "EUROC", "EUR", "GBP", "AUD", "CAD", "JPY", "CHF", "USD1", "RLUSD", "USDG", "LUSD", "MUSD", "BFUSD",
    "XUSD", "AEUR", "EURI", "KGST", "RWUSD", "U", "BIDR", "IDRT", "TRY", "BRL", "ZUSD", "SUSD", "MIM", "GHO",
    "CRVUSD", "DOLA", "FRXUSD", "USDD", "GYEN", "XSGD",
    "WBTC", "CBBTC", "CBETH", "WETH", "STETH", "WSTETH", "RETH", "LSETH", "MSOL", "JITOSOL", "BETH", "WBETH",
    "BNSOL", "TBTC", "LBTC", "WAXL", "WAMPL", "WLUNA", "WCFG",
    "PAXG", "XAUT",
}
MULT = re.compile(r"^(1000000|100000|10000|1000|1M)(?=[A-Z])")

# Same ticker, different token (checked by name and listing date before any price; reports/hunt/h5an/name_check.csv).
# An event is dropped when its ticker is listed here.
COLLISIONS = {
    "AI": "Binance 'Sleepless AI (AI)' vs Coinbase AI = Gensyn",
    "EDGE": "Binance pre-market EDGE perp (2026-03, a not-yet-launched token) vs Coinbase EDGE = Definitive (since 2025-04)",
    "LIT": "Binance pre-market LIT perp (Lighter, 2025-12) vs Coinbase LIT = Litentry",
}
# Secondary-margin perps (USDC-, BUSD- or COIN-margined contracts, or XYZUSDC/XYZBUSD tickers) add a margin currency
# for a token Binance already lists as a perp: routine, no new eager buyers -> class v (fixed before any price).
RE_SECONDARY = re.compile(r"\b(USDC|BUSD|Coin|COIN)-M(argined)?\b")


def classify(t):
    if RE_IV.search(t):
        return "iv"
    if RE_V.search(t) and not (RE_III.search(t) and not RE_PAIRS_ONLY.search(t)):
        return "v"
    if RE_I.search(t):
        return "i"
    if RE_II.search(t):
        return "ii"
    if RE_III.search(t):
        return "iii"
    return "v"


def _paren(t):
    out = []
    for m in RE_PAREN.findall(t):
        m = m.strip()
        if re.fullmatch(r"[A-Za-z0-9]+", m) and re.search(r"[A-Z0-9]", m) and not re.fullmatch(r"[0-9-]+", m):
            out.append(m.upper())
    return out


def _strip_quote(tok, coin_m):
    for q in ("USDT", "USDC", "BUSD"):
        if tok.endswith(q) and len(tok) > len(q):
            return tok[: -len(q)]
    if coin_m and tok.endswith("USD") and len(tok) > 3:
        return tok[:-3]
    return tok


def _perp(t, with_quote=False):
    m = RE_PERP_SEG.search(t)
    if not m:
        return []
    seg = m.group(1) or m.group(2) or ""
    coin_m = bool(re.search(r"COIN-M|Coin-M", t))
    out = []
    for tok in re.split(r"[,&\s]+|\band\b", seg):
        tok = tok.strip()
        if not tok or not RE_TOKEN.match(tok) or tok in STOP:
            continue
        base = _strip_quote(tok, coin_m)
        secondary = bool(RE_SECONDARY.search(t)) or tok.endswith(("USDC", "BUSD")) and base != tok
        out.append((base, secondary) if with_quote else base)
    return out


RE_MLABEL = re.compile(r"\b(USD[ⓈT]?|USDC|BUSD|Coin|COIN)-M(?:argined)?\b")


def secondary_perp(title, ticker):
    """True when this ticker's perp in a class-ii title is a secondary-margin contract (see RE_SECONDARY): the
    nearest margin label before the ticker is USDC/BUSD/COIN-M, or the contract itself is quoted in USDC/BUSD."""
    if any(b == ticker and sec and not RE_SECONDARY.search(title) for b, sec in _perp(title, with_quote=True)):
        return True
    m = re.search(rf"\b(1000000|1000|1M)?{re.escape(ticker)}(USDT|USDC|BUSD|USD)?\b", title)
    pos = m.start() if m else len(title)
    labels = [x for x in RE_MLABEL.finditer(title) if x.start() < pos]
    if labels:
        lab = labels[-1].group(1)
        if lab in ("USDC", "BUSD", "Coin", "COIN"):
            return True
        return bool(m and m.group(2) in ("USDC", "BUSD"))
    return bool(RE_SECONDARY.search(title)) or bool(m and m.group(2) in ("USDC", "BUSD"))


def _bare(t):
    t = re.split(r"\b(?:&|and)?\s*More\b|Delisting|, Delist", t)[0]
    out = []
    for tok in re.split(r"[\s,&]+", t):
        if "/" in tok:
            continue
        if RE_TOKEN.match(tok) and tok not in STOP:
            out.append(tok)
    return out


def tickers(title, cls):
    p = _paren(title)
    if cls == "ii" and not p:
        return _perp(title)
    if p:
        return p
    if cls == "iii":
        return _bare(title)
    return []


def names(title):
    """Binance 'Name (TICKER)' pairs, for the collision check."""
    out = {}
    for m in re.finditer(r"([A-Z0-9][\w'.:\- ]{0,40}?)\s*\(([A-Za-z0-9]{1,15})\)", title):
        nm = re.sub(r"^(Binance Will List|Binance Will Add|Binance Adds|Introducing( the)?|and|,)\s+", "",
                    m.group(1).strip(), flags=re.I)
        nm = re.split(r"\b(Will List|Will Add|Adds|and)\b", nm)[-1].strip(" ,")
        out[m.group(2).upper()] = nm
    return out


def main():
    A = pd.read_csv(os.path.join(D, "articles.csv"))
    ex = pd.read_csv(os.path.join(D, "cb_products_exchange.csv"))
    usd = ex[ex.quote_currency == "USD"].set_index("base_currency")
    cur = pd.read_csv(os.path.join(D, "cb_currencies.csv")).set_index("id")
    rows, bn_names = [], {}
    for a in A.itertuples():
        cls = classify(a.title)
        bn_names.update(names(a.title))
        tk = list(dict.fromkeys(tickers(a.title, cls)))          # dedupe, keep order
        if not tk:
            rows.append(dict(article_id=a.id, code=a.code, title=a.title, release_ms=a.releaseDate, cls=cls,
                             ticker=None, base=None, product=None, cb_status=None, note="no ticker in title"))
            continue
        for t in tk:
            base, note, ecls = t, "", cls
            if cls == "ii" and secondary_perp(a.title, t):
                ecls, note = "v", "secondary-margin perp (routine)"
            if t in EXCLUDE:
                note = "excluded: stable/pegged/wrapped"
            elif t not in usd.index:
                m = MULT.match(t)
                if m and t[m.end():] in usd.index:
                    base, note = t[m.end():], f"multiplier {m.group(1)} stripped"
            prod = f"{base}-USD" if base in usd.index and not note.startswith("excluded") else None
            if base in COLLISIONS:
                prod, note = None, "collision: " + COLLISIONS[base]
            if ecls == "v":
                prod = None
            rows.append(dict(article_id=a.id, code=a.code, title=a.title, release_ms=a.releaseDate, cls=ecls, ticker=t,
                             base=base, product=prod, cb_status=usd.status.get(base) if prod else None, note=note))
    E = pd.DataFrame(rows)
    E["release_utc"] = pd.to_datetime(E.release_ms, unit="ms")
    E["year"] = E.release_utc.dt.year
    E["bn_name"] = E.base.map(lambda b: bn_names.get(b))
    E.loc[E.ticker.notna(), "bn_name"] = E.loc[E.ticker.notna()].apply(
        lambda r: bn_names.get(r.ticker) or bn_names.get(r.base), axis=1)
    E["cb_name"] = E.base.map(lambda b: cur.name.get(b) if isinstance(b, str) and b in cur.index else None)
    E.to_csv(os.path.join(D, "events.csv"), index=False)

    # name check table (for COLLISIONS): every distinct Coinbase-mapped ticker with both names
    nc = (E[E["product"].notna()].groupby("base").agg(bn_name=("bn_name", "first"), cb_name=("cb_name", "first"),
                                                       n=("article_id", "size"), first=("release_utc", "min"))
          .reset_index())
    nc.to_csv(os.path.join(R, "name_check.csv"), index=False)

    # counts by class and year (titles only)
    cand = E[E["product"].notna()]
    c1 = E.drop_duplicates("article_id").pivot_table(index="cls", columns="year", values="article_id",
                                                     aggfunc="count", fill_value=0)
    c2 = E[E.ticker.notna()].pivot_table(index="cls", columns="year", values="ticker", aggfunc="count", fill_value=0)
    c3 = cand.pivot_table(index="cls", columns="year", values="ticker", aggfunc="count", fill_value=0)
    out = pd.concat({"articles": c1, "article_tickers": c2, "on_coinbase_usd": c3})
    out.to_csv(os.path.join(R, "event_counts.csv"))
    print(out.to_string())
    print("events with a Coinbase USD product:", len(cand), "articles:", cand.article_id.nunique(),
          "products:", cand["product"].nunique())


if __name__ == "__main__":
    sys.exit(main())
