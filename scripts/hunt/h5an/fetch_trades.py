#!/usr/bin/env python3
"""H5 (AN) step 3 - runs on GitHub Actions. Coinbase spot trades around every candidate event, reduced to the lookups
the simulation needs. Prints fetch progress only (no prices, no returns): HOLD events are fetched but never summarised.

For each event in data/hunt/h5an/events.csv (classes i-iv, ticker mapped to a Coinbase XYZ-USD product):
  - trades in [release - 60 min, release + 150 min]
      online products:  common.TradeFetcher (Advanced Trade public ticker window)
      delisted products: Exchange API /products/<id>/trades, trade-id binary search + backward paging
    (if no trade lands in [release + 120 min, +150 min], the window is extended to +8 h for the exit lookups);
  - 31 daily candles before the event day (Exchange API) for the 30-day median daily USD volume (sizing, AI feature).
Outputs per shard (committed):
  data/hunt/h5an/px_<shard>.parquet     one row per event: hour-before activity, half-spread estimates, price path on a
                                         fixed offset grid, entry lookups for each delta, exit lookups for each delta x H
  data/hunt/h5an/bars_<shard>.parquet   10-second bars from -10 min to +150 min (path checks)
  data/hunt/h5an/daily_<shard>.parquet  the daily candles
  data/hunt/h5an/fetchlog_<shard>.csv   method, requests, status per event
Raw trades go to raw_h5an/ (uploaded as a workflow artifact, never committed).

usage: python scripts/hunt/h5an/fetch_trades.py SHARD NSHARDS
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402

D = os.path.join(ROOT, "data", "hunt", "h5an")
RAW = os.path.join(ROOT, "raw_h5an")                 # artifact only, outside every committed path
EX = "https://api.exchange.coinbase.com"
PRE_S, POST_S, EXT_S = 3600, 9000, 8 * 3600
DELTAS = (2, 10, 30)                    # seconds after releaseDate
HOLDS = (300, 1800, 7200)               # seconds after entry
GRID = (-3600, -1800, -600, -300, -120, -60, -30, -10, 0, 2, 5, 10, 20, 30, 60, 120, 300, 600, 900, 1800, 3600,
        5400, 7200)
CLASSES = ("i", "ii", "iii", "iv")


class ExchangeTrades:
    """Exchange API trades by trade-id cursor (serves delisted products). ~4 requests/second."""

    def __init__(self, rate=4.0):
        self.S = requests.Session()
        self.S.headers["User-Agent"] = "crypto-edge-research/1.0"
        self.rate, self._last, self.n_req = rate, 0.0, 0

    def get(self, path, params):
        for a in range(8):
            w = self._last + 1.0 / self.rate - time.time()
            if w > 0:
                time.sleep(w)
            self._last = time.time()
            self.n_req += 1
            try:
                r = self.S.get(f"{EX}{path}", params=params, timeout=30)
                if r.status_code == 429:
                    time.sleep(1 + a)
                    continue
                r.raise_for_status()
                return r.json()
            except Exception:  # noqa: BLE001
                if a == 7:
                    raise
                time.sleep(1 + a)
        return []

    def _time_of(self, pid, tid):
        js = self.get(f"/products/{pid}/trades", {"after": int(tid) + 1, "limit": 1})
        return (pd.Timestamp(js[0]["time"]).tz_convert(None), int(js[0]["trade_id"])) if js else (None, None)

    def id_at(self, pid, ts, hi):
        """Smallest trade id whose time is >= ts (hi = latest id)."""
        lo = 1
        while lo < hi:
            mid = (lo + hi) // 2
            t, _ = self._time_of(pid, mid)
            if t is None or t < ts:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def window(self, pid, start, end):
        js = self.get(f"/products/{pid}/trades", {"limit": 1})
        if not js:
            return pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
        top = int(js[0]["trade_id"])
        i0 = self.id_at(pid, pd.Timestamp(start), top)
        i1 = self.id_at(pid, pd.Timestamp(end), top)
        rows, cur = [], i1
        while cur > i0:
            page = self.get(f"/products/{pid}/trades", {"after": cur, "limit": 1000})
            if not page:
                break
            rows.extend(page)
            mn = min(int(t["trade_id"]) for t in page)
            if mn >= cur:
                break
            cur = mn
        if not rows:
            return pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
        d = pd.DataFrame(rows)
        d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.tz_convert(None)
        d["price"] = d["price"].astype(float)
        d["size"] = d["size"].astype(float)
        d["side"] = d["side"].str.upper()                      # maker side, as on Advanced Trade
        d = d[(d.time >= pd.Timestamp(start)) & (d.time < pd.Timestamp(end))].drop_duplicates("trade_id")
        return d[["trade_id", "time", "price", "size", "side"]].sort_values(["time", "trade_id"]).reset_index(drop=True)

    def daily(self, pid, day):
        s = (pd.Timestamp(day) - pd.Timedelta(days=31)).strftime("%Y-%m-%dT00:00:00Z")
        e = pd.Timestamp(day).strftime("%Y-%m-%dT00:00:00Z")
        js = self.get(f"/products/{pid}/candles", {"granularity": 86400, "start": s, "end": e})
        if not isinstance(js, list) or not js:
            return pd.DataFrame(columns=["day", "low", "high", "open", "close", "volume"])
        d = pd.DataFrame(js, columns=["t", "low", "high", "open", "close", "volume"])
        d["day"] = pd.to_datetime(d.t, unit="s")
        return d.drop(columns="t")


# ------------------------------------------------------------------ per-event lookups
def _half_spread(tr, a, b, max_gap):
    """Median |p_buyer-initiated - p_seller-initiated| / 2 over adjacent opposite-aggressor prints in [a, b), in bp of
    their mid. Coinbase side is the maker side: 'SELL' = aggressive buyer, 'BUY' = aggressive seller."""
    w = tr[(tr.t >= a) & (tr.t < b)]
    if len(w) < 2:
        return np.nan, 0
    p, s, t = w.price.to_numpy(), w.side.to_numpy(), w.t.to_numpy()
    k = (s[1:] != s[:-1]) & (t[1:] - t[:-1] <= max_gap)
    if not k.any():
        return np.nan, 0
    p0, p1 = p[:-1][k], p[1:][k]
    hs = np.abs(p1 - p0) / ((p0 + p1) / 2) / 2 * 1e4
    return float(np.median(hs)), int(k.sum())


def lookups(tr, r_ms):
    """tr: trades with t = ms offset from the release (int64), price, size, side, usd. One dict of lookups."""
    out = {}
    t, p = tr.t.to_numpy(), tr.price.to_numpy()
    usd = tr.usd.to_numpy()
    buyer = (tr.side.to_numpy() == "SELL")
    pre = t < 0
    out["n_pre60"] = int(pre.sum())
    out["usd_pre60"] = float(usd[pre].sum())
    out["n_pre10"] = int(((t >= -600_000) & pre).sum())
    out["last_pre_ms"] = int(t[pre].max()) if pre.any() else None
    out["n_post"] = int((~pre).sum())
    out["first_post_ms"] = int(t[~pre].min()) if (~pre).any() else None
    out["last_ms"] = int(t.max()) if len(t) else None
    for nm, (a, b, g) in {"hs10": (-600_000, 0, 10_000), "hs60": (-3_600_000, 0, 10_000),
                          "hs60any": (-3_600_000, 0, 3_600_000)}.items():
        out[nm], out[f"{nm}_pairs"] = _half_spread(tr, a, b, g)
    # last-price path on the grid: the last print at or before release + offset (seconds)
    for g in GRID:
        i = np.searchsorted(t, g * 1000, side="right") - 1
        out[f"p_{g}"] = float(p[i]) if i >= 0 else np.nan
    for dl in DELTAS:
        i = np.searchsorted(t, dl * 1000, side="left")              # first print at least delta after the release
        if i >= len(t):
            out[f"e{dl}_ms"] = None
            continue
        te = int(t[i])
        out[f"e{dl}_ms"], out[f"e{dl}_px"], out[f"e{dl}_buyer"] = te, float(p[i]), bool(buyer[i])
        m10 = (t >= te) & (t < te + 10_000)
        m60 = (t >= te) & (t < te + 60_000)
        out[f"e{dl}_buyusd10"] = float(usd[m10 & buyer].sum())
        out[f"e{dl}_buyusd60"] = float(usd[m60 & buyer].sum())
        out[f"e{dl}_usd60"] = float(usd[m60].sum())
        for h in HOLDS:
            j = np.searchsorted(t, te + h * 1000, side="left")      # first print at least H after the entry
            if j >= len(t):
                out[f"x{dl}_{h}_ms"] = None
                continue
            tx = int(t[j])
            out[f"x{dl}_{h}_ms"], out[f"x{dl}_{h}_px"] = tx, float(p[j])
            mx = (t >= tx) & (t < tx + 60_000)
            out[f"x{dl}_{h}_sellusd60"] = float(usd[mx & ~buyer].sum())
            out[f"x{dl}_{h}_usd60"] = float(usd[mx].sum())
    # tick-direction check of the side convention: share of up-ticks among buyer-initiated prints (should be high)
    dp = np.diff(p)
    nz = dp != 0
    if nz.sum() > 20:
        out["side_check_up_given_buyer"] = float(((dp > 0) & buyer[1:])[nz].sum() / max(1, (buyer[1:] & nz).sum()))
    return out


def bars10(tr):
    w = tr[(tr.t >= -600_000) & (tr.t < POST_S * 1000)].copy()
    if w.empty:
        return pd.DataFrame()
    w["b"] = (w.t // 10_000).astype(int)
    w["buyusd"] = np.where(w.side == "SELL", w.usd, 0.0)
    g = w.groupby("b")
    return pd.DataFrame({"first": g.price.first(), "last": g.price.last(), "high": g.price.max(), "low": g.price.min(),
                         "usd": g.usd.sum(), "buyusd": g.buyusd.sum(), "n": g.price.size()}).reset_index()


def needs_extension(tr, r):
    """True when some entry (first print >= release + delta) or exit (first print >= entry + H) is not inside the
    fetched window."""
    t = ((tr.time - r) / pd.Timedelta(milliseconds=1)).to_numpy()
    t = np.sort(t)
    for dl in DELTAS:
        i = np.searchsorted(t, dl * 1000, side="left")
        if i >= len(t):
            return True
        if np.searchsorted(t, t[i] + max(HOLDS) * 1000, side="left") >= len(t):
            return True
    return False


def main():
    shard, nsh = int(sys.argv[1]), int(sys.argv[2])
    os.makedirs(RAW, exist_ok=True)
    E = pd.read_csv(os.path.join(D, "events.csv"))
    E = E[E["product"].notna() & E.cls.isin(CLASSES)].copy()
    E["key"] = E["product"].str.replace("-USD", "", regex=False) + "_" + E.release_ms.astype(str)
    E = E.drop_duplicates("key").sort_values("release_ms").reset_index(drop=True)
    E = E[E.index % nsh == shard]
    adv = pd.read_csv(os.path.join(D, "cb_products_adv.csv")).set_index("product_id")
    exd = pd.read_csv(os.path.join(D, "cb_products_exchange.csv")).set_index("id")
    tf, xt = common.TradeFetcher(), ExchangeTrades()
    px, bars, daily, log = [], [], [], []
    t0 = time.time()
    for k, ev in enumerate(E.itertuples()):
        r = pd.Timestamp(int(ev.release_ms), unit="ms")
        pid = ev.product
        rec = dict(key=ev.key, product=pid, release_ms=int(ev.release_ms))
        online = (exd.status.get(pid) == "online") and pid in adv.index
        start, end = r - pd.Timedelta(seconds=PRE_S), r + pd.Timedelta(seconds=POST_S)
        n0, x0 = tf.n_req, xt.n_req
        try:
            if online:
                try:
                    tr = tf.window(pid, start, end)
                    rec["method"] = "advanced"
                except Exception as e:  # noqa: BLE001
                    rec["adv_error"] = f"{type(e).__name__}"[:80]
                    tr = xt.window(pid, start, end)
                    rec["method"] = "exchange_fallback"
                new_at = adv.new_at.get(pid)            # 2023-01-01 is a placeholder for older listings
                listed_before = isinstance(new_at, str) and (new_at.startswith("2023-01-01T00:00:00")
                                                             or pd.Timestamp(new_at).tz_convert(None) < r)
                if rec["method"] == "advanced" and not (tr.time < r).any() and listed_before:
                    tr = xt.window(pid, start, end)          # Advanced served nothing for an older product
                    rec["method"] = "exchange_empty_fallback"
            else:
                tr = xt.window(pid, start, end)
                rec["method"] = "exchange"
            if len(tr) and (tr.time < r).any() and needs_extension(tr, r):
                ext = (tf.window(pid, end, end + pd.Timedelta(seconds=EXT_S)) if rec["method"] == "advanced"
                       else xt.window(pid, end, end + pd.Timedelta(seconds=EXT_S)))
                rec["extended"] = int(len(ext))
                tr = pd.concat([tr, ext]).drop_duplicates("trade_id").sort_values(["time", "trade_id"])
            rec["status"] = "ok"
        except Exception as e:  # noqa: BLE001
            rec.update(status=f"error {type(e).__name__}: {e}"[:200])
            tr = pd.DataFrame(columns=["trade_id", "time", "price", "size", "side"])
        try:
            dd = xt.daily(pid, r.normalize())
            dd["key"] = ev.key
            daily.append(dd)
        except Exception as e:  # noqa: BLE001
            rec["daily_error"] = f"{type(e).__name__}"[:80]
        rec["n_trades"] = int(len(tr))
        rec["req_adv"], rec["req_ex"] = tf.n_req - n0, xt.n_req - x0
        log.append(rec)
        if len(tr):
            tr = tr.reset_index(drop=True)
            tr.to_parquet(os.path.join(RAW, f"{ev.key}.parquet"), index=False)
            q = pd.DataFrame({"t": ((tr.time - r) / pd.Timedelta(milliseconds=1)).round().astype("int64"),
                              "price": tr.price.astype(float), "size": tr["size"].astype(float),
                              "side": tr.side.astype(str)})
            q["usd"] = q.price * q["size"]
            q = q.sort_values("t", kind="stable").reset_index(drop=True)
            lk = lookups(q, int(ev.release_ms))
            lk.update(key=ev.key, product=pid, release_ms=int(ev.release_ms))
            px.append(lk)
            b = bars10(q)
            if len(b):
                b["key"] = ev.key
                bars.append(b)
        if (k + 1) % 20 == 0:
            print(f"shard {shard}: {k + 1}/{len(E)} events, requests adv {tf.n_req} ex {xt.n_req}, "
                  f"{time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(px).to_parquet(os.path.join(D, f"px_{shard}.parquet"), index=False)
    if bars:
        pd.concat(bars).to_parquet(os.path.join(D, f"bars_{shard}.parquet"), index=False)
    if daily:
        pd.concat(daily).to_parquet(os.path.join(D, f"daily_{shard}.parquet"), index=False)
    L = pd.DataFrame(log)
    L.to_csv(os.path.join(D, f"fetchlog_{shard}.csv"), index=False)
    print(f"shard {shard} done: {len(E)} events, status {L.status.value_counts().to_dict()}, "
          f"methods {L.method.value_counts().to_dict()}, requests adv {tf.n_req} ex {xt.n_req}, "
          f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
