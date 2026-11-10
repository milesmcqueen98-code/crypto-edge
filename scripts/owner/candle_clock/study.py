#!/usr/bin/env python3
"""Candle clock study (plan: reports/owner/candle_clock_prereg.md). Runs on a GitHub runner; public endpoints only,
no keys, no orders. Raw trades stay in memory and are never written to a file.

For each coin (BTC and the 17 traded coins):
  1. page the public trades back from the present until past 2 minutes before the window start (at most 5 requests a
     second for the whole job, at most 2,500 pages a coin);
  2. fetch the final candles of the window plus 2 minutes either side, in requests of up to 300 minutes, and keep an
     answer only if it was generated (Date minus Age) at or after the window's last minute closed plus 180 s;
  3. chain the candles through the trades (trade_id order) to bound where each candle was cut, and score the bars a
     trades-built bar would give with offset zero, a fitted offset and the previous boundary's offset.
Refusal policy: 401, 403, 429, 451 or a non-JSON body stops that source (trades or candles) for the whole job at once;
network errors and 5xx are retried twice.

Usage: python scripts/owner/candle_clock/study.py [--minutes 360] [--lead 15] [--coins BTC,DOGE]
"""
import argparse
import bisect
import datetime as dt
import gzip
import json
import math
import os
import sys
import time
from decimal import Decimal

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

US = 1_000_000
MIN = 60 * US
EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
OUT = os.path.join(ROOT, "reports", "owner", "candle_clock")
ANCHOR_SPAN = 20 * US          # anchor start within 20 s either side of the minute mark
CONFIRM = 5                    # the next 5 candles must chain too
B_LATEST = 12.0                # class B: the candle ends no later than 12 s after the mark


# ----------------------------------------------------------------------------------------------- fetching

class Refused(RuntimeError):
    """The venue said no (401, 403, 429, 451 or a non-JSON body). Never worked around."""


RATE = 5.0
_last = [0.0]


def get(url, params, parse_float=None):
    """One paced GET (all requests of the job share the pace). Returns (json, headers). 5xx and network errors are
    retried twice; a refusal raises Refused at once with no retry."""
    import requests
    from bot import market as M
    for a in range(3):
        wait = _last[0] + 1.0 / RATE - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = M._S.get(url, params=params, timeout=15)
        except requests.RequestException:
            if a == 2:
                raise
            time.sleep(0.5 + a)
            continue
        if r.status_code in (401, 403, 429, 451):
            raise Refused(f"HTTP {r.status_code} on {url} {params}: {r.text[:200]!r}")
        if r.status_code >= 500:
            if a == 2:
                r.raise_for_status()
            time.sleep(0.5 + a)
            continue
        r.raise_for_status()
        try:
            js = r.json(parse_float=parse_float) if parse_float else r.json()
        except ValueError:
            raise Refused(f"non-JSON reply on {url} {params}: {r.text[:200]!r}")
        return js, r.headers


def stamp_us(s):
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return (t - EPOCH) // dt.timedelta(microseconds=1)


def fetch_trades(coin, stop_us, max_pages=2500):
    """Trades of one coin from the present back past stop_us: list of (t_us, trade_id, price_str, size_str)."""
    from bot import market as M
    rows, pages, cur, info = [], 0, None, dict(capped=False, ended=False, error=None)
    params = {"limit": 1000}
    while True:
        if pages >= max_pages:
            info["capped"] = True
            break
        try:
            js, hd = get(f"{M.EXCHANGE}/products/{coin}-USD/trades", params)
        except Refused:
            info["pages"] = pages
            raise_info = dict(info, pages=pages, rows=rows)
            raise RefusedWith(raise_info)
        except Exception as err:  # noqa: BLE001  network or HTTP error after the retries
            info["error"] = repr(err)[:200]
            break
        pages += 1
        if not js:
            info["ended"] = True
            break
        if not isinstance(js, list):
            raise RefusedWith(dict(info, pages=pages, rows=rows, why=f"trades page is not a list: {str(js)[:200]}"))
        pg = [(stamp_us(r["time"]), int(r["trade_id"]), str(r["price"]), str(r["size"])) for r in js]
        rows += pg
        if min(x[0] for x in pg) < stop_us:
            break
        nxt = hd.get("CB-AFTER") or hd.get("cb-after")
        cur = int(nxt) if nxt not in (None, "") else min(x[1] for x in pg)
        params = {"limit": 1000, "after": cur}
    info["pages"] = pages
    return rows, info


class RefusedWith(RuntimeError):
    def __init__(self, info):
        super().__init__(info.get("why", "refused"))
        self.info = info


def fetch_candles(coin, m_first, m_last, w1_us, log):
    """Final candles for minutes m_first..m_last (inclusive, µs) in requests of up to 300 minutes. Returns
    (rows {minute_us: (o, h, l, c, v) as Decimal}, known set of minutes, answers list)."""
    from bot import market as M
    rows, known, answers = {}, set(), []
    s = m_first
    while s <= m_last:
        e = min(m_last, s + 299 * MIN)
        p = {"granularity": 60, "start": iso(s), "end": iso(e)}
        js, hd = get(f"{M.EXCHANGE}/products/{coin}-USD/candles", p, parse_float=Decimal)
        gen = M.generated_at(hd)
        gen_us = None if gen is None else int(gen.value // 1000)
        a = dict(coin=coin, start=iso(s), end=iso(e), cache=hd.get("cf-cache-status"), age=hd.get("Age"),
                 gen=None if gen is None else str(gen), dropped=False)
        if gen_us is None or gen_us < w1_us + 180 * US:
            a["dropped"] = True
            log.append(f"DROPPED candle answer {coin} {iso(s)}..{iso(e)}: generated {a['gen']} (cache {a['cache']}, "
                       f"Age {a['age']})")
        elif not isinstance(js, list):
            raise Refused(f"candles answer is not a list: {str(js)[:200]}")
        else:
            for r in js:
                t = int(r[0]) * US
                if s <= t <= e:
                    rows[t] = (Decimal(r[3]), Decimal(r[2]), Decimal(r[1]), Decimal(r[4]), Decimal(r[5]))
            known.update(range(s, e + 1, MIN))
        answers.append(a)
        s = e + MIN
    return rows, known, answers


def iso(us):
    return dt.datetime.fromtimestamp(us / US, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------------------------- integer units

def decimals(s):
    d = Decimal(s).normalize()
    e = d.as_tuple().exponent
    return max(0, -e) if isinstance(e, int) else 0


def to_units(x, d):
    """Decimal x in units of 10^-d; None when not a whole number of units."""
    v = Decimal(x).scaleb(d)
    return int(v) if v == v.to_integral_value() else None


def prepare(trades, candles):
    """Integer form. trades: list of (t_us, id, price_str, size_str); candles: {minute: (o, h, l, c, v) Decimal}.
    Returns dict with id-ordered lists t, p, cum (prefix sums of size units), the time-ordered arrays, and the
    candles in units: {minute: (o, h, l, c, vlo, vhi, v_units_float)} with vlo..vhi the size-unit totals within half a
    unit of the candle volume."""
    seen, tr = set(), []
    for x in sorted(trades, key=lambda r: r[1]):
        if x[1] not in seen:
            seen.add(x[1])
            tr.append(x)
    dp = max([decimals(x[2]) for x in tr] or [0])
    ds = max([decimals(x[3]) for x in tr] or [0])
    t = [x[0] for x in tr]
    ids = [x[1] for x in tr]
    p = [to_units(x[2], dp) for x in tr]
    sz = [to_units(x[3], ds) for x in tr]
    cum = [0]
    for v in sz:
        cum.append(cum[-1] + v)
    cu = {}
    for m, (o, h, lo, c, v) in candles.items():
        tv = Decimal(v).scaleb(ds)
        cu[m] = (to_units(o, dp), to_units(h, dp), to_units(lo, dp), to_units(c, dp),
                 math.ceil(tv - Decimal("0.5")), math.floor(tv + Decimal("0.5")), float(v))
    order = sorted(range(len(tr)), key=lambda i: (t[i], ids[i]))      # the bot's bar order: time, then trade_id
    ta = np.array([t[i] for i in order], dtype=np.int64)
    pa = [p[i] for i in order]
    cs = [0]
    for i in order:
        cs.append(cs[-1] + sz[i])
    gaps = sum(1 for a, b in zip(ids, ids[1:]) if b != a + 1)
    nonmono = sum(1 for a, b in zip(t, t[1:]) if b < a)
    t_np = np.array(t, dtype=np.int64)
    return dict(t=t, t_np=t_np, p=p, cum=cum, ta=ta, pa=pa, cs=cs, candles=cu, dp=dp, ds=ds, n=len(tr),
                id_gaps=gaps, nonmono=nonmono, scale_p=10 ** dp, scale_s=10 ** ds)


# ----------------------------------------------------------------------------------------------- the chain

def match_run(D, s, c):
    """End position e such that trades [s, e) (trade_id order) reproduce candle c; c None = no candle (zero trades,
    returns s). None when no run matches."""
    if c is None:
        return s
    o, h, lo, cl, vlo, vhi, _ = c
    t, p, cum = D["t"], D["p"], D["cum"]
    n = len(t)
    if s >= n or o is None or p[s] != o:
        return None
    base = cum[s]
    e = bisect.bisect_left(cum, base + vlo, lo=s + 1)
    while e <= n and cum[e] <= base + vhi:
        if p[e - 1] == cl:
            seg = p[s:e]
            if max(seg) == h and min(seg) == lo:
                return e
        e += 1
    return None


def chain(D, mins, known):
    """Chain the candles of minutes mins (µs, consecutive) through the trades. Returns start, end (position lists,
    None where the candle is not explained) and anchored (True where the chain was (re)anchored)."""
    cand = D["candles"]
    t_np = D["t_np"]
    k = len(mins)
    start, end, anch = [None] * k, [None] * k, [False] * k
    floor = 0
    pos = None
    i = 0
    while i < k:
        m = mins[i]
        if m not in known:
            pos = None
            i += 1
            continue
        c = cand.get(m)
        if pos is None:
            if c is None:                       # cannot anchor on a minute with no candle
                i += 1
                continue
            cands = np.nonzero((t_np >= m - ANCHOR_SPAN) & (t_np <= m + ANCHOR_SPAN))[0]
            got = None
            for s in cands:
                s = int(s)
                if s < floor:
                    continue
                e = match_run(D, s, c)
                if e is None:
                    continue
                q, ok = e, True
                for j in range(i + 1, min(k, i + 1 + CONFIRM)):
                    if mins[j] not in known:
                        ok = False
                        break
                    q = match_run(D, q, cand.get(mins[j]))
                    if q is None:
                        ok = False
                        break
                if ok:
                    got = (s, e)
                    break
            if got is None:
                i += 1
                continue
            start[i], end[i], anch[i] = got[0], got[1], True
            pos = floor = got[1]
            i += 1
            continue
        e = match_run(D, pos, c)
        if e is None:
            pos = None
            i += 1
            continue
        start[i], end[i] = pos, e
        pos = floor = e
        i += 1
    return start, end, anch


def boundaries(D, mins, start, end):
    """For minute i: (lo, hi) in seconds of the cut at its end, or None when unexplained."""
    t = D["t"]
    out = []
    for i, m in enumerate(mins):
        mark = m + MIN
        ok = (end[i] is not None and i + 1 < len(mins) and end[i + 1] is not None and start[i + 1] == end[i]
              and 0 < end[i] < len(t))
        out.append(((t[end[i] - 1] - mark) / US, (t[end[i]] - mark) / US) if ok else None)
    return out


# ----------------------------------------------------------------------------------------------- offsets

def best_offset(iv):
    """The offset x satisfying the most intervals lo < x <= hi. Returns dict(n, k, share, a, b, mid, runs): the best
    count k, the tied range (a, b] (the widest tied run; nearest zero on a tie of widths), its midpoint."""
    if not iv:
        return dict(n=0, k=0, share=np.nan, a=np.nan, b=np.nan, mid=np.nan, runs=0)
    lo = np.sort(np.array([x[0] for x in iv]))
    hi = np.sort(np.array([x[1] for x in iv]))
    pts = np.unique(np.concatenate([lo, hi]))
    cnt = np.searchsorted(lo, pts, "left") - np.searchsorted(hi, pts, "left")
    k = int(cnt.max())
    runs, j = [], 0
    while j < len(pts):
        if cnt[j] == k:
            j0 = j
            while j + 1 < len(pts) and cnt[j + 1] == k:
                j += 1
            runs.append((float(pts[j0 - 1]), float(pts[j])))
        j += 1
    a, b = sorted(runs, key=lambda r: (-(r[1] - r[0]), abs((r[0] + r[1]) / 2)))[0]
    return dict(n=len(iv), k=k, share=k / len(iv), a=a, b=b, mid=(a + b) / 2, runs=len(runs))


def satisfies(iv, x):
    return sum(1 for lo, hi in iv if lo < x <= hi)


# ----------------------------------------------------------------------------------------------- bars

def time_bar(D, a_us, b_us, incl_end=False):
    """Bar of trades stamped in [a, b) (or [a, b] with incl_end), in (time, trade_id) order; None when empty.
    (open, high, low, close, volume units)."""
    ta = D["ta"]
    i0 = int(np.searchsorted(ta, a_us, "left"))
    i1 = int(np.searchsorted(ta, b_us, "right" if incl_end else "left"))
    if i1 <= i0:
        return None
    seg = D["pa"][i0:i1]
    return (seg[0], max(seg), min(seg), seg[-1], D["cs"][i1] - D["cs"][i0])


def run_bar(D, s, cut_us, incl):
    """Bar of trades from id position s onward while the stamp is before the cut (or at it, with incl)."""
    t, p, cum = D["t"], D["p"], D["cum"]
    e = s
    while e < len(t) and (t[e] < cut_us or (incl and t[e] == cut_us)):
        e += 1
    if e <= s:
        return None
    seg = p[s:e]
    return (seg[0], max(seg), min(seg), seg[-1], cum[e] - cum[s])


def compare(D, bar, c, sigma):
    """(all five equal, exact, material) of bar against candle c (c exists)."""
    if bar is None:
        return False, False, True
    o, h, lo, cl, vlo, vhi, vf = c
    eq5 = bar[0] == o and bar[1] == h and bar[2] == lo and bar[3] == cl and vlo <= bar[4] <= vhi
    vb = bar[4] / D["scale_s"]
    exact = bar[1] == h and bar[2] == lo and bar[3] == cl and abs(vb - vf) <= 0.005 * max(vf, 1e-12)
    sp = D["scale_p"]
    mat = False
    if cl is None or lo is None:
        mat = True
    else:
        if abs(math.log((bar[3] / sp) / (cl / sp))) > 0.5 * sigma:
            mat = True
        if abs((bar[2] / sp) / (lo / sp) - 1) > 5e-4:
            mat = True
    return eq5, exact, mat


def shares(rows):
    if not rows:
        return dict(n=0, eq5=np.nan, exact=np.nan, material=np.nan)
    a = np.array(rows, dtype=float)
    return dict(n=len(rows), eq5=a[:, 0].mean(), exact=a[:, 1].mean(), material=a[:, 2].mean())


# ----------------------------------------------------------------------------------------------- per coin

def analyze_coin(coin, trades, candles, known, w0, w1, cover_from=None):
    """trades: (t_us, id, price_str, size_str); candles {minute: Decimal OHLCV}; known: minutes whose final candle
    answer was kept; window [w0, w1) in µs. cover_from: the earliest time the trades are complete from."""
    D = prepare(trades, candles)
    cand = D["candles"]
    first = w0 - MIN
    if cover_from is not None:
        first = max(first, ((cover_from + ANCHOR_SPAN) // MIN + 1) * MIN)
    mins = list(range(first, w1 + 2 * MIN, MIN))
    start, end, anch = chain(D, mins, known)
    bnd = boundaries(D, mins, start, end)
    idx = {m: i for i, m in enumerate(mins)}
    wmins = list(range(w0, w1, MIN))
    nmin = len(wmins)
    half = w0 + (nmin // 2) * MIN

    # sigma of one-minute log returns of the final closes in the window
    cl = [cand[m][3] for m in wmins if m in cand and cand[m][3]]
    lr = np.diff(np.log(np.array(cl, dtype=float))) if len(cl) > 2 else np.array([])
    sigma = float(np.std(lr, ddof=1)) if len(lr) > 2 else float("nan")

    brow, m1_all, m1_last, iv_all, iv_first, iv_hour = [], [], [], [], [], {}
    tpm, extra, unexpl_list = [], 0, []
    for m in wmins:
        i = idx.get(m)
        n_in = int(np.searchsorted(D["ta"], m + MIN, "left") - np.searchsorted(D["ta"], m, "left"))
        tpm.append(n_in)
        kn = m in known and (m + MIN) in known
        b = bnd[i] if i is not None and kn else None
        bar0 = time_bar(D, m, m + MIN)
        c = cand.get(m)
        if m in known:
            if c is not None:
                r = compare(D, bar0, c, sigma)
                m1_all.append(r)
                if m >= half:
                    m1_last.append(r)
            elif bar0 is not None:
                extra += 1
        matched = (m in known) and ((c is None and bar0 is None) or (c is not None and compare(D, bar0, c, sigma)[0]))
        brow.append(dict(coin=coin, minute=iso(m), lo=None if b is None else round(b[0], 6),
                         hi=None if b is None else round(b[1], 6), explained=b is not None, trades=n_in,
                         candle=c is not None, bar0_match=bool(matched) if m in known else None))
        if b is not None:
            iv_all.append(b)
            iv_hour.setdefault((m - w0) // (60 * MIN), []).append(b)
            if m < half:
                iv_first.append(b)
        elif m in known and (m + MIN) in known:
            unexpl_list.append(iso(m))

    nb = sum(1 for m in wmins if m in known and (m + MIN) in known)
    ne = len(iv_all)
    z = satisfies(iv_all, 0.0)
    los = np.array([b[0] for b in iv_all]) if iv_all else np.array([])
    his = np.array([b[1] for b in iv_all]) if iv_all else np.array([])
    lpos = los[los > 0] if len(los) else los
    bo = best_offset(iv_all)
    bf = best_offset(iv_first)
    hourly = {h: best_offset(v) for h, v in sorted(iv_hour.items())}
    h_a = max([v["a"] for v in hourly.values() if v["n"]] or [np.nan])
    h_b = min([v["b"] for v in hourly.values() if v["n"]] or [np.nan])

    # measure 5 on the last half
    fit = bf["mid"] if bf["n"] else 0.0
    fit_us = int(round(fit * US))
    r0, rf, rp, prev_fallback = [], [], [], 0
    for m in wmins:
        if m < half or m not in known or m not in cand:
            continue
        c = cand[m]
        r0.append(compare(D, time_bar(D, m, m + MIN), c, sigma))
        rf.append(compare(D, time_bar(D, m + fit_us, m + MIN + fit_us), c, sigma))
        i = idx.get(m)
        pe = end[i - 1] if i is not None and i > 0 else None
        if pe is not None and pe > 0:
            lo_prev = D["t"][pe - 1] - m
            x = max(0, lo_prev)
            bar = run_bar(D, pe, m + MIN + x, incl=x > 0)
        else:
            prev_fallback += 1
            bar = time_bar(D, m, m + MIN)
        rp.append(compare(D, bar, c, sigma))
    s0, sf, sp = shares(r0), shares(rf), shares(rp)
    m1a, m1l = shares(m1_all), shares(m1_last)
    zero_share = z / nb if nb else np.nan                # unexplained boundaries count as not satisfied
    if zero_share >= 0.995 and m1l["material"] <= 0.01:
        cls = "A"
    elif sf["material"] <= 0.01 and fit <= B_LATEST:
        cls = "B"
    else:
        cls = "C"
    row = dict(
        coin=coin, cls=cls, window_start=iso(w0), window_end=iso(w1), trades=D["n"], id_gaps=D["id_gaps"],
        stamps_out_of_id_order=D["nonmono"], trades_per_min_median=float(np.median(tpm)) if tpm else np.nan,
        sigma_1m=sigma, minutes_with_candle=m1a["n"], minutes_bar_but_no_candle=extra,
        m1_eq5=m1a["eq5"], m1_exact=m1a["exact"], m1_material=m1a["material"],
        m1_last_eq5=m1l["eq5"], m1_last_exact=m1l["exact"], m1_last_material=m1l["material"],
        boundaries=nb, explained=ne, explained_share=ne / nb if nb else np.nan,
        unexplained=nb - ne, reanchors=sum(anch),
        zero_share=zero_share, zero_share_of_explained=z / ne if ne else np.nan,
        lo_pos_share=float((los > 0).mean()) if ne else np.nan,
        hi_nonpos_share=float((his <= 0).mean()) if ne else np.nan,
        lo_pos_median=float(np.median(lpos)) if len(lpos) else np.nan,
        lo_pos_p90=float(np.percentile(lpos, 90)) if len(lpos) else np.nan,
        lo_max=float(los.max()) if ne else np.nan, hi_min=float(his.min()) if ne else np.nan,
        hi_nonpos_median=float(np.median(his[his <= 0])) if ne and (his <= 0).any() else np.nan,
        best_a=bo["a"], best_b=bo["b"], best_mid=bo["mid"], best_share=bo["k"] / nb if nb else np.nan,
        best_share_of_explained=bo["share"], best_tied_runs=bo["runs"],
        hourly_best_mid=";".join(f"{v['mid']:.3f}" for v in hourly.values()),
        hourly_best_share=";".join(f"{v['share']:.3f}" for v in hourly.values()),
        hourly_common_range=bool(h_a < h_b) if hourly else False,
        fit_first_a=bf["a"], fit_first_b=bf["b"], fit_offset=fit,
        oos_minutes=s0["n"],
        oos0_eq5=s0["eq5"], oos0_exact=s0["exact"], oos0_material=s0["material"],
        oosfit_eq5=sf["eq5"], oosfit_exact=sf["exact"], oosfit_material=sf["material"],
        oosprev_eq5=sp["eq5"], oosprev_exact=sp["exact"], oosprev_material=sp["material"],
        oosprev_fallback=prev_fallback,
    )
    return row, brow, unexpl_list


# ----------------------------------------------------------------------------------------------- main

def main(minutes, lead, coins):
    from bot import market as M  # noqa: F401  (session and helpers)
    t_start = time.time()
    now_min = int(t_start // 60) * MIN
    w1 = now_min - lead * MIN
    w0 = w1 - minutes * MIN
    print(f"job start {iso(int(t_start) * US)}; window {iso(w0)} .. {iso(w1)} ({minutes} minutes); coins {coins}",
          flush=True)
    log, trades, tinfo = [], {}, {}
    refused_trades = False
    for c in coins:
        if refused_trades:
            break
        a = time.time()
        try:
            rows, info = fetch_trades(c, w0 - 2 * MIN)
        except RefusedWith as r:
            refused_trades = True
            rows, info = r.info["rows"], r.info
            log.append(f"REFUSED trades at {c} after {info.get('pages')} pages: {r}")
            print(log[-1], flush=True)
        trades[c] = rows
        tinfo[c] = info
        old = min((x[0] for x in rows), default=None)
        print(f"{c}: {info.get('pages')} pages, {len(rows)} trades, oldest {iso(old) if old else None}, "
              f"capped {info.get('capped')}, error {info.get('error')}, {time.time() - a:.0f} s", flush=True)
        if info.get("capped"):
            log.append(f"PAGE CAP {c}: stopped at 2,500 pages, oldest trade {iso(old) if old else None}")
        if info.get("error"):
            log.append(f"ERROR trades {c}: {info['error']}")
    # candles: at least 10 minutes after the window's last minute closed
    wait = (w1 + 600 * US) / US - time.time()
    if wait > 0:
        time.sleep(wait)
    candles, known, answers = {}, {}, []
    refused_candles = False
    for c in coins:
        if c not in trades or refused_candles:
            continue
        try:
            rows, kn, ans = fetch_candles(c, w0 - 2 * MIN, w1 + MIN, w1, log)
        except Refused as r:
            refused_candles = True
            log.append(f"REFUSED candles at {c}: {r}")
            print(log[-1], flush=True)
            continue
        except Exception as err:  # noqa: BLE001
            log.append(f"ERROR candles {c}: {err!r}"[:300])
            continue
        candles[c], known[c] = rows, kn
        answers += ans
    print("candle answers: cache", count([a["cache"] for a in answers]), "Age", count([a["age"] for a in answers]),
          "dropped", sum(a["dropped"] for a in answers), flush=True)

    rows, brows = [], []
    for c in coins:
        if c not in candles or not trades.get(c):
            log.append(f"SKIPPED {c}: no trades or no candles")
            continue
        info = tinfo[c]
        old = min(x[0] for x in trades[c])
        cover = None if (old < w0 - 2 * MIN or info.get("ended")) else old
        a = time.time()
        row, br, un = analyze_coin(c, trades[c], candles[c], known[c], w0, w1, cover_from=cover)
        row["pages"] = info.get("pages")
        row["page_capped"] = bool(info.get("capped"))
        rows.append(row)
        brows += br
        if un:
            log.append(f"UNEXPLAINED {c}: {len(un)} boundaries, first {un[:8]}")
        print(f"analyzed {c} in {time.time() - a:.1f} s", flush=True)
        trades[c] = None
    write(rows, brows)
    report(rows, log)


def count(xs):
    out = {}
    for x in xs:
        out[str(x)] = out.get(str(x), 0) + 1
    return out


COLS_SHOW = [("cls", "cls", "{}"), ("tpm", "trades_per_min_median", "{:.0f}"), ("expl", "explained_share", "{:.3f}"),
             ("zero", "zero_share", "{:.3f}"), ("best", "best_mid", "{:.2f}"), ("best_sh", "best_share", "{:.3f}"),
             ("fit", "fit_offset", "{:.2f}"), ("m1_eq5", "m1_eq5", "{:.3f}"), ("m1_mat", "m1_material", "{:.3f}"),
             ("oos0", "oos0_material", "{:.3f}"), ("oosfit", "oosfit_material", "{:.3f}"),
             ("oosprev", "oosprev_material", "{:.3f}"), ("lo>0", "lo_pos_share", "{:.3f}"),
             ("hi<=0", "hi_nonpos_share", "{:.3f}"), ("lo>0_med", "lo_pos_median", "{:.2f}"),
             ("lo>0_p90", "lo_pos_p90", "{:.2f}"), ("lo_max", "lo_max", "{:.2f}"), ("unexpl", "unexplained", "{}"),
             ("gaps", "id_gaps", "{}"), ("hrs_same", "hourly_common_range", "{}")]


def fmt(v, f):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "-"
        return f.format(v)
    except (ValueError, TypeError):
        return str(v)


def write(rows, brows):
    import csv
    os.makedirs(OUT, exist_ok=True)
    if rows:
        keys = list(rows[0].keys())
        with open(os.path.join(OUT, "per_coin.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow({k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()})
    if brows:
        with gzip.open(os.path.join(OUT, "boundaries.csv.gz"), "wt", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(brows[0].keys()))
            w.writeheader()
            w.writerows(brows)


def report(rows, log):
    print("\nPER COIN")
    print("coin  " + " ".join(f"{h:>8}" for h, _, _ in COLS_SHOW))
    for r in rows:
        print(f"{r['coin']:<5} " + " ".join(f"{fmt(r[k], f):>8}" for _, k, f in COLS_SHOW))
    print("\nhourly best offsets (midpoints) and shares:")
    for r in rows:
        print(f"  {r['coin']}: mids {r['hourly_best_mid']} shares {r['hourly_best_share']}; "
              f"fitted first half ({fmt(r['fit_first_a'], '{:.3f}')}, {fmt(r['fit_first_b'], '{:.3f}')}]; "
              f"best all ({fmt(r['best_a'], '{:.3f}')}, {fmt(r['best_b'], '{:.3f}')}] runs {r['best_tied_runs']}; "
              f"eq5/exact oos: zero {fmt(r['oos0_eq5'], '{:.3f}')}/{fmt(r['oos0_exact'], '{:.3f}')} "
              f"fit {fmt(r['oosfit_eq5'], '{:.3f}')}/{fmt(r['oosfit_exact'], '{:.3f}')} "
              f"prev {fmt(r['oosprev_eq5'], '{:.3f}')}/{fmt(r['oosprev_exact'], '{:.3f}')}; "
              f"pages {r['pages']} capped {r['page_capped']}; bar-without-candle {r['minutes_bar_but_no_candle']}; "
              f"reanchors {r['reanchors']}; prev fallback {r['oosprev_fallback']}")
    cl = {}
    for r in rows:
        cl.setdefault(r["cls"], []).append(r["coin"])
    print("\nSUMMARY classes:", {k: v for k, v in sorted(cl.items())})
    b = [r for r in rows if r["coin"] == "BTC"]
    if b:
        b = b[0]
        print(f"BTC: class {b['cls']}; zero satisfies {fmt(b['zero_share'], '{:.4f}')} of boundaries; cut-at-minute "
              f"material share last half {fmt(b['m1_last_material'], '{:.4f}')}; largest lo {fmt(b['lo_max'], '{:.2f}')} s")
    tb = sum(r["boundaries"] for r in rows)
    te = sum(r["explained"] for r in rows)
    print(f"boundaries explained overall: {te}/{tb}")
    print("\nLOG (refusals, drops, caps, unexplained):")
    for x in log or ["(nothing)"]:
        print("  " + x)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=360)
    ap.add_argument("--lead", type=int, default=15)
    ap.add_argument("--coins", default="")
    a = ap.parse_args()
    allc = ["BTC"] + json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))["coins"]
    cs = [c.strip().upper() for c in a.coins.split(",") if c.strip()] or allc
    main(a.minutes, a.lead, cs)
