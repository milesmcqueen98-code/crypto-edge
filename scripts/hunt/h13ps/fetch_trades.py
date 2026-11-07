#!/usr/bin/env python3
"""H13 (PS) step 3 - runs on GitHub Actions. Coinbase spot prints for every in-universe event of
reports/hunt/h13ps/events.csv, from T_lo - 10 min to T_ft + 3 h (SPEC), reduced on the runner to what the simulation
and the checks need. Prints fetch progress only: no prices, no returns, no fill counts.

Hold-out hygiene: an event is a HOLD event when T_ft + 3 h >= 2026-06-01 (some exit could fall on a HOLD day). Its
reduced rows go to *_hold_<shard>.parquet, which no DEV-stage script opens (sim.py refuses to before the freeze).

Fetch: common.TradeFetcher (Advanced Trade public ticker; falls back to the Exchange API trade-id cursor for products
Advanced no longer serves). If Advanced returns no print at all for a product that exists, the Exchange API is tried
too (as builder h5an did). If T_ft - T_lo > 48 h, two windows are fetched: [T_lo - 10 min, T_lo + 48 h + 10 min] and
[T_ft - 70 min, T_ft + 3 h].

Outputs per shard (data/hunt/h13ps/prints/):
  ev_{dev|hold}_<s>.parquet     one row per event: lookups at fixed decision and fill times (see `lookups`)
  slot_{dev|hold}_<s>.parquet   Mode I bid slots: one per minute from T_lo + 60 min until min(T_ft, T_lo + 48 h);
                                bid L = (last print >= 1 s old) - 1 tick; through-volume = size of later prints in the
                                slot strictly below L (price <= L - tick); only slots with through-volume are kept
  m1_{dev|hold}_<s>.parquet     clock-minute bars of the whole window (checks, marked-to-market)
  rel_{dev|hold}_<s>.parquet    1-minute bins relative to T_ft, -30 .. +29 (leak diagnostic, volume jump)
  fetchlog_<s>.csv              method, requests, status, n prints per event (no prices)

usage: python scripts/hunt/h13ps/fetch_trades.py SHARD NSHARDS
"""
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402

EVENTS = os.path.join(ROOT, "reports", "hunt", "h13ps", "events.csv")
OUT = os.path.join(ROOT, "data", "hunt", "h13ps", "prints")
HOLD0 = pd.Timestamp("2026-06-01")
MS = 1000
MIN = 60 * MS
DELTAS = (2, 60)                     # s after T_ft (Mode II entry)
HS = (5, 30, 120)                    # min after T_ft (exits)
LAT = 2 * MS                         # taker legs fill at the first print >= 2 s after the decision
OLD = 1 * MS                         # decisions use prints >= 1 s old
CAP48 = 48 * 60 * MIN


def ms(ts):
    return int(pd.Timestamp(ts).value // 1_000_000)


def half_spread(t, p, s, a, b, max_gap):
    """Median |p_i - p_j| / mid / 2 (bp) over adjacent opposite-aggressor prints in [a, b) at most max_gap apart
    (builder h5an's estimator). side is the maker side, so adjacent prints of opposite side are opposite aggressors."""
    i0, i1 = np.searchsorted(t, a, "left"), np.searchsorted(t, b, "left")
    if i1 - i0 < 2:
        return np.nan, 0
    pp, ss, tt = p[i0:i1], s[i0:i1], t[i0:i1]
    k = (ss[1:] != ss[:-1]) & (tt[1:] - tt[:-1] <= max_gap)
    if not k.any():
        return np.nan, 0
    p0, p1 = pp[:-1][k], pp[1:][k]
    return float(np.median(np.abs(p1 - p0) / ((p0 + p1) / 2) / 2 * 1e4)), int(k.sum())


def obs_tick(p):
    u = np.unique(np.round(p, 12))
    if len(u) < 3:
        return np.nan
    d = np.diff(u)
    d = d[d > 0]
    return float(d.min()) if len(d) else np.nan


def lookups(ev, t, p, q, s, tick):
    """All per-event lookups. t: int64 ms (sorted), p price, q size (base), s maker side ('BUY'/'SELL')."""
    usd = p * q
    buyer = s == "SELL"                       # maker SELL = an aggressive buyer lifted an offer
    lo, ft = ms(ev.T_lo), ms(ev.T_ft)
    out = dict(key=ev.key, n=len(t), first_ms=int(t[0]), first_px=float(p[0]), tick=tick,
               n_before_lo=int((t < lo).sum()), last_ms=int(t[-1]))
    cs_usd = np.concatenate([[0.0], np.cumsum(usd)])

    def usd_between(a, b):
        return float(cs_usd[np.searchsorted(t, b, "left")] - cs_usd[np.searchsorted(t, a, "left")])

    def last_before(x):                       # last print strictly before x
        i = np.searchsorted(t, x, "left") - 1
        return (float(p[i]), int(t[i])) if i >= 0 else (np.nan, None)

    def first_from(x):                        # first print at or after x
        i = np.searchsorted(t, x, "left")
        return (float(p[i]), int(t[i]), i) if i < len(t) else (np.nan, None, None)

    # decision points: (name, decision time)
    dec = {"mI": lo + 60 * MIN, "x48": lo + CAP48}
    for dl in DELTAS:
        dec[f"e{dl}"] = ft + dl * MS - LAT
    for h in HS:
        dec[f"x{h}"] = ft + h * MIN
    for nm, d in dec.items():
        out[f"{nm}_dec_ms"] = d
        out[f"{nm}_last_px"], out[f"{nm}_last_ms"] = last_before(d - OLD)
        out[f"{nm}_usd60"] = usd_between(d - OLD - 60 * MIN, d - OLD)
        out[f"{nm}_lo_usd"] = usd_between(lo, d - OLD)
        for hn, (a, g) in {"hs10": (10 * MIN, 10 * MS), "hs60": (60 * MIN, 10 * MS),
                           "hs60any": (60 * MIN, 60 * MIN)}.items():
            out[f"{nm}_{hn}"], out[f"{nm}_{hn}_pairs"] = half_spread(t, p, s, d - a, d, g)
    # taker fills: first print >= decision + 2 s
    for nm in list(dec):
        px, tm, i = first_from(dec[nm] + LAT)
        out[f"{nm}_fill_px"], out[f"{nm}_fill_ms"] = px, tm
        if i is not None:
            j = np.searchsorted(t, tm + MIN, "left")
            out[f"{nm}_fill_buyusd60"] = float(usd[i:j][buyer[i:j]].sum())
            out[f"{nm}_fill_sellusd60"] = float(usd[i:j][~buyer[i:j]].sum())
            out[f"{nm}_fill_usd60"] = float(usd[i:j].sum())
    # check points: last print at or before x
    for nm, x in {"lo60": lo + 60 * MIN, "ftm10": ft - 10 * MIN, "ft": ft, "ft5": ft + 5 * MIN,
                  "ft30": ft + 30 * MIN, "ft120": ft + 120 * MIN}.items():
        out[f"px_{nm}"], _ = last_before(x + 1)
    i0, i1 = np.searchsorted(t, ft, "left"), np.searchsorted(t, ft + MIN, "left")
    out["buyusd_ft_60s"] = float(usd[i0:i1][buyer[i0:i1]].sum())
    out["usd_ft_60s"] = usd_between(ft, ft + MIN)
    for nm, (a, b) in {"pre_ft": (ft - 10 * MIN, ft), "post_ft": (ft, ft + 10 * MIN)}.items():
        out[f"{nm}_hs10"], out[f"{nm}_hs10_pairs"] = half_spread(t, p, s, a, b, 10 * MS)
        out[f"{nm}_hs10any"], out[f"{nm}_hs10any_pairs"] = half_spread(t, p, s, a, b, 10 * MIN)
    return out


def slots(ev, t, p, q, tick):
    """Mode I bid slots (see module doc). Returns rows only for slots with through-volume > 0."""
    lo, ft = ms(ev.T_lo), ms(ev.T_ft)
    a0 = lo + 60 * MIN
    stop = min(ft, lo + CAP48)
    rows = []
    if not np.isfinite(tick) or stop <= a0:
        return rows
    k = 0
    while True:
        a = a0 + k * MIN
        if a >= stop:
            break
        b = min(a + MIN, stop)
        i = np.searchsorted(t, a - OLD, "left") - 1
        if i >= 0:
            L = p[i] - tick
            j0, j1 = np.searchsorted(t, a, "left"), np.searchsorted(t, b, "left")
            if j1 > j0:
                m = p[j0:j1] < L - 0.5 * tick
                if m.any():
                    rows.append(dict(key=ev.key, k=k, a_ms=a, L=float(L), ref_px=float(p[i]),
                                     thru_base=float(q[j0:j1][m].sum()), min_px=float(p[j0:j1].min()),
                                     n_thru=int(m.sum())))
        k += 1
    return rows


def m1(ev, d):
    w = d.copy()
    w["minute"] = w.time.dt.floor("min")
    w["usd"] = w.price * w["size"]
    w["buyusd"] = np.where(w.side == "SELL", w.usd, 0.0)
    g = w.groupby("minute")
    o = pd.DataFrame({"first": g.price.first(), "last": g.price.last(), "high": g.price.max(), "low": g.price.min(),
                      "usd": g.usd.sum(), "buyusd": g.buyusd.sum(), "n": g.price.size()}).reset_index()
    o["key"] = ev.key
    return o


def rel(ev, t, p, q, s):
    ft = ms(ev.T_ft)
    usd = p * q
    buyer = s == "SELL"
    rows = []
    for b in range(-30, 30):
        a, e = ft + b * MIN, ft + (b + 1) * MIN
        i0, i1 = np.searchsorted(t, a, "left"), np.searchsorted(t, e, "left")
        rows.append(dict(key=ev.key, bin=b, usd=float(usd[i0:i1].sum()), buyusd=float(usd[i0:i1][buyer[i0:i1]].sum()),
                         n=int(i1 - i0), last=float(p[i1 - 1]) if i1 > 0 and i1 - 1 >= 0 and t[i1 - 1] < e else np.nan))
    return rows


def _ex(tf):
    if tf._ex is None:
        tf._ex = common.ExchangeTrades(rate=6.0)
    return tf._ex


def fetch(tf, pid, a, b):
    """Prints in [a, b); returns (frame, method)."""
    x0 = _ex(tf).n_req
    try:
        d = tf.window(pid, a, b)
        method = "advanced" if _ex(tf).n_req == x0 else "exchange_404_fallback"
    except Exception as e:  # noqa: BLE001
        d = _ex(tf).window(pid, a, b)
        method = f"exchange_after_{type(e).__name__}"
    if len(d) == 0 and method == "advanced":
        d = _ex(tf).window(pid, a, b)
        method = "exchange_empty_fallback"
    return d, method


def main():
    shard, nsh = int(sys.argv[1]), int(sys.argv[2])
    os.makedirs(OUT, exist_ok=True)
    E = pd.read_csv(EVENTS, parse_dates=["T_lo", "T_ft"])
    E = E[E.in_universe].sort_values("T_lo").reset_index(drop=True)
    E = E[E.index % nsh == shard]
    tf = common.TradeFetcher()
    res = {"dev": dict(ev=[], slot=[], m1=[], rel=[]), "hold": dict(ev=[], slot=[], m1=[], rel=[])}
    log = []
    t0 = time.time()
    for k, ev in enumerate(E.itertuples()):
        part = "hold" if ev.T_ft + pd.Timedelta(hours=3) >= HOLD0 else "dev"
        rec = dict(key=ev.key, pid=ev.pid, part=part)
        n0 = tf.n_req + _ex(tf).n_req
        try:
            lo0, ft1 = ev.T_lo - pd.Timedelta(minutes=10), ev.T_ft + pd.Timedelta(hours=3)
            if (ev.T_ft - ev.T_lo) > pd.Timedelta(hours=48):
                d1, m_1 = fetch(tf, ev.pid, lo0, ev.T_lo + pd.Timedelta(hours=48, minutes=10))
                d2, m_2 = fetch(tf, ev.pid, ev.T_ft - pd.Timedelta(minutes=70), ft1)
                d = pd.concat([d1, d2]).drop_duplicates("trade_id")
                rec["method"] = f"{m_1}+{m_2}"
            else:
                d, rec["method"] = fetch(tf, ev.pid, lo0, ft1)
            rec["status"] = "ok"
        except Exception as e:  # noqa: BLE001
            d = pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
            rec["status"] = f"error {type(e).__name__}: {e}"[:200]
        rec["n_prints"] = int(len(d))
        rec["requests"] = tf.n_req + _ex(tf).n_req - n0
        log.append(rec)
        if len(d) >= 2:
            d = d.sort_values(["time", "trade_id"]).reset_index(drop=True)
            d["side"] = d.side.astype(str).str.upper()
            d["time"] = pd.to_datetime(d.time)
            t = d.time.to_numpy().astype("datetime64[ms]").astype("int64")
            p, q, s = d.price.to_numpy(float), d["size"].to_numpy(float), d.side.to_numpy()
            tk = obs_tick(p)
            tick = tk if np.isfinite(tk) else float(ev.tick_now)
            lk = lookups(ev, t, p, q, s, tick)
            lk["tick_now"] = float(ev.tick_now)
            lk["tick_obs"] = tk
            R = res[part]
            R["ev"].append(lk)
            R["slot"] += slots(ev, t, p, q, tick)
            R["m1"].append(m1(ev, d))
            R["rel"] += rel(ev, t, p, q, s)
        if (k + 1) % 10 == 0:
            print(f"shard {shard}: {k + 1}/{len(E)} events, requests {tf.n_req}"
                  f"+{_ex(tf).n_req}, {time.time() - t0:.0f}s", flush=True)
    for part, R in res.items():
        if R["ev"]:
            pd.DataFrame(R["ev"]).to_parquet(os.path.join(OUT, f"ev_{part}_{shard}.parquet"), index=False)
        if R["slot"]:
            pd.DataFrame(R["slot"]).to_parquet(os.path.join(OUT, f"slot_{part}_{shard}.parquet"), index=False)
        if R["m1"]:
            pd.concat(R["m1"]).to_parquet(os.path.join(OUT, f"m1_{part}_{shard}.parquet"), index=False)
        if R["rel"]:
            pd.DataFrame(R["rel"]).to_parquet(os.path.join(OUT, f"rel_{part}_{shard}.parquet"), index=False)
    L = pd.DataFrame(log)
    L.to_csv(os.path.join(OUT, f"fetchlog_{shard}.csv"), index=False)
    print(f"shard {shard} done: {len(E)} events; status {L.status.str[:5].value_counts().to_dict()}; "
          f"methods {L.method.value_counts().to_dict() if 'method' in L else {}}; {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
