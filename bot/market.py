"""Public Coinbase market data (no keys): spot 1-minute candles (Coinbase Exchange, the research source)
and Coinbase US futures candles / order books (Advanced Trade public endpoints)."""
import time
from email.utils import parsedate_to_datetime

import numpy as np
import pandas as pd
import requests

EXCHANGE = "https://api.exchange.coinbase.com"
ADV = "https://api.coinbase.com/api/v3/brokerage/market"
_S = requests.Session()
_S.headers["User-Agent"] = "crypto-edge-bot/1.0"


def _get(url, params=None, tries=5):
    for a in range(tries):
        try:
            r = _S.get(url, params=params, timeout=15)
            if r.status_code == 429:
                time.sleep(1 + a)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if a == tries - 1:
                raise
            time.sleep(0.5 + a)


class Refused(RuntimeError):
    """The venue refused a request (401, 403, 451 or a page that is not JSON). Never worked around."""


TRADES_RATE = 7.0               # trades requests per second at most (the research fetcher's pace; public limit 10)
_last_req = [0.0]


def _get_h(url, params=None, tries=2):
    """Like _get, but returns (json, headers) and gives up sooner (the trades pass runs on a time budget).
    Paced to TRADES_RATE requests per second. A refusal raises Refused at once."""
    for a in range(tries):
        wait = _last_req[0] + 1.0 / TRADES_RATE - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_req[0] = time.time()
        try:
            r = _S.get(url, params=params, timeout=3)
            if r.status_code in (401, 403, 451):
                raise Refused(f"HTTP {r.status_code} on {url}: {r.text[:200]!r}")
            if r.status_code == 429:
                if a == tries - 1:
                    r.raise_for_status()
                time.sleep(0.5)
                continue
            r.raise_for_status()
            try:
                return r.json(), r.headers
            except ValueError:
                raise Refused(f"non-JSON reply on {url}: {r.text[:200]!r}")
        except requests.RequestException:
            if a == tries - 1:
                raise
            time.sleep(0.3)


def _http_time(s):
    try:
        return pd.Timestamp(parsedate_to_datetime(s)).tz_convert(None)
    except (TypeError, ValueError, IndexError):
        return None


def generated_at(headers):
    """When the venue (or its cache) generated this answer: the Date header minus the Age header (Age absent = 0).
    None when there is no readable Date."""
    d = _http_time((headers or {}).get("Date"))
    if d is None:
        return None
    try:
        age = float((headers or {}).get("Age") or 0)
    except ValueError:
        return None
    return d - pd.Timedelta(seconds=age)


def _page(js):
    """Rows of one trades page as (time, trade_id, price, size); bad is the number of rows that could not be read."""
    out, bad = [], 0
    for r in js:
        try:
            t = pd.Timestamp(r["time"])
            t = t.tz_convert(None) if t.tzinfo is not None else t
            tid, px, sz = int(r["trade_id"]), float(r["price"]), float(r["size"])
            if not (np.isfinite(px) and np.isfinite(sz) and px > 0 and sz >= 0):
                raise ValueError
            out.append((t, tid, px, sz))
        except (KeyError, TypeError, ValueError):
            bad += 1
    return out, bad


def trades_to_bar(rows, m):
    """Bar of the minute [m, m + 60 s) from trade rows (time, trade_id, price, size), in trade order (time, then
    trade_id); duplicates by trade_id are dropped. None when no trade falls in the minute."""
    m = pd.Timestamp(m)
    e = m + pd.Timedelta(minutes=1)
    seen, sel = set(), []
    for t, tid, px, sz in rows:
        if m <= t < e and tid not in seen:
            seen.add(tid)
            sel.append((t, tid, px, sz))
    if not sel:
        return None
    sel.sort(key=lambda x: (x[0], x[1]))
    px = [x[2] for x in sel]
    return dict(open=px[0], high=max(px), low=min(px), close=px[-1], volume=float(sum(x[3] for x in sel)))


def minute_trades_bar(coin, m, max_pages=20, deadline=None, get=None, clock=time.monotonic):
    """The trades of one coin for the minute [m, m + 60 s), from Coinbase Exchange's public trades list (newest first,
    1000 a page, paged back with the CB-AFTER cursor), reduced to a bar, with proof of completeness.

    verified is True only if both hold:
      (i) paging reached a trade stamped before m, or the venue's list ended (an empty page);
      (ii) the first page was generated at or after m + 60 s (Date minus Age), or it holds a trade stamped at or
           after m + 60 s.
    Also unverified: the page cap, the deadline (a time.monotonic value), or any row that could not be read.
    Returns dict(bar (None = no trades in the minute), verified, reason (None when verified), pages, gen (first page's
    generation time), newest (newest trade time seen), n (trades in the minute)). `get` is _get_h (tests pass a fake)."""
    get = get or _get_h
    m = pd.Timestamp(m)
    e = m + pd.Timedelta(minutes=1)
    rows, pages, bad, gen, newest, reason = [], 0, 0, None, None, None
    reached = ended = first_late = False
    params, cur = {"limit": 1000}, None
    while True:
        if pages >= max_pages:
            reason = "page_cap"
            break
        if deadline is not None and pages and clock() > deadline:
            reason = "deadline"
            break
        js, hd = get(f"{EXCHANGE}/products/{coin}-USD/trades", params)
        hd = hd or {}
        pages += 1
        if pages == 1:
            gen = generated_at(hd)
        if not js:
            ended = True                                   # the venue's list ended: nothing older
            break
        if not isinstance(js, list):
            raise ValueError(f"trades page is not a list: {str(js)[:200]}")
        pg, b = _page(js)
        bad += b
        if not pg:
            reason = "malformed"
            break
        if cur is not None and max(x[1] for x in pg) >= cur:
            raise ValueError(f"trades page after {cur} holds ids at or above the cursor")
        rows += pg
        top = max(x[0] for x in pg)
        newest = top if newest is None else max(newest, top)
        if pages == 1:
            first_late = top >= e                          # a trade after the minute: the page saw its end
        if min(x[0] for x in pg) < m:
            reached = True
            break
        nxt = hd.get("CB-AFTER") or hd.get("cb-after")
        try:
            cur = int(nxt) if nxt not in (None, "") else min(x[1] for x in pg)
        except ValueError:
            cur = min(x[1] for x in pg)
        params = {"limit": 1000, "after": cur}
    fresh = (gen is not None and gen >= e) or first_late
    bar = trades_to_bar(rows, m)
    if reason is None and bad:
        reason = "malformed"
    if reason is None and not (reached or ended):
        reason = "incomplete"
    if reason is None and not fresh:
        reason = "stale_first_page"
    n = len({r[1] for r in rows if m <= r[0] < e})
    return dict(bar=bar, verified=reason is None, reason=reason, pages=pages, gen=gen, newest=newest, n=n)


def spot_candles(coin, start, end):
    """1-minute candles [start, end) as a DataFrame indexed by minute (UTC, naive)."""
    rows = {}
    s = pd.Timestamp(start).floor("min")
    end = pd.Timestamp(end).floor("min")
    while s < end:
        e = min(end, s + pd.Timedelta(minutes=300))
        js = _get(f"{EXCHANGE}/products/{coin}-USD/candles",
                  {"granularity": 60, "start": s.isoformat() + "Z", "end": (e - pd.Timedelta(minutes=1)).isoformat() + "Z"})
        for t, lo, hi, op, cl, vo in js or []:
            rows[t] = (op, hi, lo, cl, vo)
        s = e
        time.sleep(0.12)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    k = sorted(rows)
    df = pd.DataFrame([rows[i] for i in k], columns=["open", "high", "low", "close", "volume"], dtype=float)
    df.index = pd.to_datetime(k, unit="s")
    return df[(df.index >= pd.Timestamp(start)) & (df.index < end)]


def futures_candles(product_id, start, end):
    rows = {}
    s = int(pd.Timestamp(start).timestamp())
    e = int(pd.Timestamp(end).timestamp())
    while s < e:
        hi = min(e, s + 300 * 60)
        js = _get(f"{ADV}/products/{product_id}/candles", {"start": s, "end": hi, "granularity": "ONE_MINUTE", "limit": 350})
        for c in js.get("candles", []):
            rows[int(c["start"])] = (float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c["volume"]))
        s = hi
        time.sleep(0.12)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    k = sorted(rows)
    df = pd.DataFrame([rows[i] for i in k], columns=["open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(k, unit="s")
    return df[(df.index >= pd.Timestamp(start)) & (df.index < pd.Timestamp(end))]


def book(product_id, limit=50):
    """Bids and asks as lists of (price, size in contracts), best first."""
    js = _get(f"{ADV}/product_book", {"product_id": product_id, "limit": limit})
    pb = js.get("pricebook", {})
    return ([(float(b["price"]), float(b["size"])) for b in pb.get("bids", [])],
            [(float(a["price"]), float(a["size"])) for a in pb.get("asks", [])])


def book_top(product_id):
    js = _get(f"{ADV}/product_book", {"product_id": product_id, "limit": 5})
    pb = js.get("pricebook", {})
    bids, asks = pb.get("bids", []), pb.get("asks", [])
    if not bids or not asks:
        return np.nan, np.nan
    return float(bids[0]["price"]), float(asks[0]["price"])
