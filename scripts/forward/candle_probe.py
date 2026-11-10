#!/usr/bin/env python3
"""Candle probe (one-off): when is the newest one-minute candle final, and from which source?

Plan: reports/owner/candle_probe_prereg.md (branch owner/charter). Results: reports/owner/candle_probe/README.md.

At each minute boundary q, for each of nine coins (the plan's eight plus BTC, by its amendment) and the minute that just closed (q-1):
  ex_candles   Coinbase Exchange candles (the bot's own request) at about 1, 3, 6, 10, 15, 25 and 40 s after q
  adv_candles  Coinbase Advanced public candles at about 6 s
  ex_trades    Coinbase Exchange trades at about 1 s and 3 s, paged back to the start of q-1, reduced to OHLCV
  ref          Exchange candles for q-1 requested at q + 230 s (the reference)
Every call's planned, request and response times are stored. Raw trades never leave the process.

  python scripts/forward/candle_probe.py collect --minutes 125 --out probe_out      # on a runner
  python scripts/forward/candle_probe.py analyze probe_out/obs.parquet --collector <forward checkout>

Reuses the collector's Http (refusal detection, user agent), RateLimiter and candle parser; changes nothing in it.
"""
import argparse
import itertools
import json
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collector as C  # noqa: E402

COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "HYPE", "ZEC", "PEPE", "ONDO"]   # BTC added by the plan's amendment
CANDLE_DELAYS = (1, 3, 6, 10, 15, 25, 40)
ADV_DELAY = 6
TRADE_DELAYS = (1, 3, 6)
REF_AT = 230                  # seconds after q; the plan asks for 180 s or more
BOT_URL_AT = 9.5              # the paper bot's steady-state URL, requested after the bots made their own request
EX_INTERVAL = 0.125           # 8 a second on the Exchange host (public limit 10 a second, burst 15)
ADV_INTERVAL = 0.125          # 8 a second on the Advanced host
TIMEOUT = (2, 5)
MAX_PAGES = 20
PRIO = {"page": 0, "ex_trades": 1, "ex_candles": 2, "adv_candles": 2, "bot_url": 2, "ref": 3}
SOURCES = ("ex_candles", "adv_candles", "ex_trades", "bot_url", "ref")
WINDOW_MINUTES = {1: 6, 3: 7, 6: 5, 10: 8, 15: 9, 25: 10, 40: 11, REF_AT: 15}   # 6 s = the bot's own window
REF_MIN_GEN = 180            # a reference answer must have been generated at least this long after q


# ------------------------------------------------------------------------------------------------ parsers
def adv_candle(js, minute):
    """Advanced {'candles': [{'start': unix, 'low', 'high', 'open', 'close', 'volume'}]} -> (o, h, l, c, v) or None."""
    t = int(pd.Timestamp(minute).timestamp())
    for k in (js or {}).get("candles") or []:
        if int(k["start"]) == t:
            return tuple(float(k[f]) for f in ("open", "high", "low", "close", "volume"))
    return None


def reduce_trades(trades, minute):
    """Exchange trades [{'time', 'trade_id', 'price', 'size'}] -> (o, h, l, c, v, n) for [minute, minute + 1 min)."""
    lo, hi = pd.Timestamp(minute), pd.Timestamp(minute) + pd.Timedelta(minutes=1)
    sel = []
    for x in trades:
        t = pd.Timestamp(x["time"])
        t = t.tz_convert(None) if t.tzinfo else t
        if lo <= t < hi:
            sel.append((int(x["trade_id"]), float(x["price"]), float(x["size"])))
    if not sel:
        return None
    sel.sort()
    px = [p for _, p, _ in sel]
    return px[0], max(px), min(px), px[-1], sum(s for _, _, s in sel), len(sel)


def oldest(trades):
    """(time, trade_id) of the oldest trade in a page."""
    i = min(range(len(trades)), key=lambda k: int(trades[k]["trade_id"]))
    t = pd.Timestamp(trades[i]["time"])
    return (t.tz_convert(None) if t.tzinfo else t), int(trades[i]["trade_id"])


# ------------------------------------------------------------------------------------------------ http
class ProbeHttp(C.Http):
    """The collector's Http (same session, user agent and refusal checks) that also returns the cache headers:
    the venue answers from a URL-keyed Cloudflare cache (candles max-age 300 s, trades 5 s)."""

    def fetch(self, url, params):
        r = self.s.get(url, timeout=TIMEOUT, params=params)
        body = r.text[:400].lower() if r.status_code != 200 else ""
        if r.status_code in (403, 451) or "captcha" in body or "just a moment" in body or "cf-chl" in body:
            raise C.Refused(f"{r.status_code} {url.split('?')[0]} {r.text[:120]!r}")
        if r.status_code == 429:
            raise requests.HTTPError("429 rate limited")
        r.raise_for_status()
        d = r.headers.get("date")
        try:
            date = pd.Timestamp(d).timestamp() if d else math.nan
        except (TypeError, ValueError):
            date = math.nan
        return r.json(), dict(cache=r.headers.get("cf-cache-status"), age=C.fnum(r.headers.get("age")), date=date)


def bot_window(q):
    """The paper bot's steady-state request at boundary q: start = q - 4 min, end = q - 1 min (bot/spot/engine.py
    update_spot asks from its newest stored minute, normally q - 2, minus 2 minutes; bot/market.py spot_candles
    sends end - 1 min)."""
    q = pd.Timestamp(q).floor("min")
    return {"granularity": 60, "start": (q - pd.Timedelta(minutes=4)).isoformat() + "Z",
            "end": (q - pd.Timedelta(minutes=1)).isoformat() + "Z"}


def window(q, delay):
    """Exchange candle params for the window ending at the minute just closed (q-1). The bot's 6 s request is its
    exact 5-minute window; every other delay and the reference start further back, so no request in the run repeats
    another's URL (a repeated URL is answered from the cache)."""
    p = C.candle_params(q)
    back = WINDOW_MINUTES[delay]
    if back != C.CANDLE_MINUTES:
        p["start"] = (pd.Timestamp(q).floor("min") - pd.Timedelta(minutes=back)).isoformat() + "Z"
    return p


# ------------------------------------------------------------------------------------------------ scheduling
class Lane:
    """One host: among the jobs already due, the lowest (priority, slot time) goes next, each start paced by the
    collector's RateLimiter, the request itself on a worker thread. So trades never wait behind candles that are
    still queued from an earlier slot."""

    def __init__(self, interval, pool):
        self.limiter = C.RateLimiter(interval)
        self.pool, self.jobs, self.cv, self.seq = pool, [], threading.Condition(), itertools.count()
        threading.Thread(target=self.loop, daemon=True).start()

    def push(self, when, prio, fn):
        with self.cv:
            self.jobs.append((when, prio, next(self.seq), fn))
            self.cv.notify()

    def pending(self):
        with self.cv:
            return len(self.jobs)

    def _due(self):
        now = time.time()
        due = [j for j in self.jobs if j[0] <= now]
        return min(due, key=lambda j: (j[1], j[0], j[2])) if due else None

    def loop(self):
        while True:
            with self.cv:
                while not self.jobs:
                    self.cv.wait()
                if self._due() is None:
                    self.cv.wait(timeout=max(0.0, min(j[0] for j in self.jobs) - time.time()))
                    continue
            self.limiter.acquire()
            with self.cv:
                job = self._due()
                self.jobs.remove(job)
            self.pool.submit(job[3])


class Probe:
    def __init__(self, coins=COINS, http=None, log=None, ex_interval=EX_INTERVAL, adv_interval=ADV_INTERVAL):
        self.coins, self.http = coins, http or ProbeHttp()
        self.pool = ThreadPoolExecutor(max_workers=32)
        self.ex, self.adv = Lane(ex_interval, self.pool), Lane(adv_interval, self.pool)
        self.rows, self.lock = [], threading.Lock()
        self.stopped = {}                  # source -> reason (refusal or rate limit)
        self.errors = {}
        self.log = log or (lambda m: print(m, flush=True))

    def record(self, **r):
        with self.lock:
            self.rows.append(r)

    def fail(self, source, err):
        kind = ("refused" if isinstance(err, C.Refused) else "http429" if "429" in str(err)
                else "timeout" if isinstance(err, requests.Timeout)
                else "http" if isinstance(err, requests.HTTPError)
                else "net" if isinstance(err, requests.RequestException) else "parse")
        with self.lock:
            self.errors[f"{source}:{kind}"] = self.errors.get(f"{source}:{kind}", 0) + 1
            if kind in ("refused", "http429") and source not in self.stopped:
                self.stopped[source] = f"{kind}: {str(err)[:200]}"
                self.log(f"STOPPED {source}: {kind} {str(err)[:200]} -- source stopped for the rest of the run")
        return kind

    def base(self, source, coin, q, delay, plan):
        return dict(source=source, coin=coin, minute=q - pd.Timedelta(minutes=1), q=q, delay=delay, t_plan=plan)

    # ---- jobs
    def ex_candles(self, coin, q, delay, plan, source="ex_candles", tries=1):
        def run():
            b = self.base(source, coin, q, delay, plan)
            if source in self.stopped:
                return self.record(**b, status="stopped")
            t_req = time.time()
            try:
                js, hd = self.http.fetch(f"{C.EXCHANGE}/products/{coin}-USD/candles",
                                         bot_window(q) if source == "bot_url" else window(q, delay))
                t_resp = time.time()
                cs = C.parse_candles(js, q)
                v = cs.get(b["minute"])
                newest = max(pd.Timestamp(int(x[0]), unit="s") for x in js) if js else pd.NaT
            except Exception as err:                    # noqa: BLE001
                kind = self.fail(source, err)
                if source == "ref" and tries < 3 and kind not in ("refused", "http429"):
                    self.ex.push(time.time() + 15, PRIO["ref"], self.ex_candles(coin, q, delay, plan, source, tries + 1))
                    return None
                return self.record(**b, status=kind, t_req=t_req, t_resp=time.time())
            self.record(**b, status="ok", t_req=t_req, t_resp=t_resp, present=v is not None, newest=newest, **hd,
                        **dict(zip(("open", "high", "low", "close", "volume"), v or (math.nan,) * 5)))
        return run

    def adv_candles(self, coin, q, delay, plan):
        def run():
            b = self.base("adv_candles", coin, q, delay, plan)
            if "adv_candles" in self.stopped:
                return self.record(**b, status="stopped")
            t_req = time.time()
            s = q - pd.Timedelta(minutes=C.CANDLE_MINUTES)
            try:
                js, hd = self.http.fetch(f"{C.ADV}/products/{coin}-USD/candles",
                                         {"start": str(int(s.timestamp())), "end": str(int(q.timestamp())),
                                          "granularity": "ONE_MINUTE"})
                t_resp = time.time()
                v = adv_candle(js, b["minute"])
                ks = (js or {}).get("candles") or []
                newest = max(pd.Timestamp(int(k["start"]), unit="s") for k in ks) if ks else pd.NaT
            except Exception as err:                    # noqa: BLE001
                return self.record(**b, status=self.fail("adv_candles", err), t_req=t_req, t_resp=time.time())
            self.record(**b, status="ok", t_req=t_req, t_resp=t_resp, present=v is not None, newest=newest, **hd,
                        **dict(zip(("open", "high", "low", "close", "volume"), v or (math.nan,) * 5)))
        return run

    def ex_trades(self, coin, q, delay, plan):
        st = dict(trades=[], pages=0, t_req=None, hd={}, newest=pd.NaT)
        b = self.base("ex_trades", coin, q, delay, plan)

        def page(after=None):
            def run():
                if "ex_trades" in self.stopped:
                    return self.record(**b, status="stopped", pages=st["pages"], t_req=st["t_req"])
                t = time.time()
                st["t_req"] = st["t_req"] or t
                params = {"limit": 1000} | ({"after": after} if after else {})
                try:
                    js, hd = self.http.fetch(f"{C.EXCHANGE}/products/{coin}-USD/trades", params)
                    t_resp = time.time()
                    if not st["pages"]:                 # the first page: its cache headers and newest trade
                        st["hd"] = hd
                        st["newest"] = max((pd.Timestamp(x["time"]).tz_convert(None) for x in js), default=pd.NaT)
                    st["pages"] += 1
                    st["trades"] += js
                    old_t, old_id = oldest(js) if js else (None, None)
                except Exception as err:                # noqa: BLE001
                    return self.record(**b, status=self.fail("ex_trades", err), pages=st["pages"],
                                       t_req=st["t_req"], t_resp=time.time())
                if js and old_t >= b["minute"] and st["pages"] < MAX_PAGES:
                    return self.ex.push(plan, PRIO["page"], page(old_id))
                v = reduce_trades(st["trades"], b["minute"])
                st["trades"] = None                     # raw trades are dropped here
                self.record(**b, status="ok", t_req=st["t_req"], t_resp=t_resp, pages=st["pages"], **st["hd"],
                            newest=st["newest"],
                            capped=bool(js and old_t >= b["minute"]), present=v is not None,
                            **dict(zip(("open", "high", "low", "close", "volume", "n_trades"),
                                       v or (math.nan,) * 6)))
            return run
        return page()

    # ---- the minute
    def schedule(self, q):
        T = q.timestamp()
        for d in TRADE_DELAYS:
            for c in self.coins:
                self.ex.push(T + d, PRIO["ex_trades"], self.ex_trades(c, q, d, T + d))
        for d in CANDLE_DELAYS:
            for c in self.coins:
                self.ex.push(T + d, PRIO["ex_candles"], self.ex_candles(c, q, d, T + d))
        for c in self.coins:
            self.adv.push(T + ADV_DELAY, PRIO["adv_candles"], self.adv_candles(c, q, ADV_DELAY, T + ADV_DELAY))
            self.ex.push(T + REF_AT, PRIO["ref"], self.ex_candles(c, q, REF_AT, T + REF_AT, source="ref"))
            self.ex.push(T + BOT_URL_AT, PRIO["bot_url"],
                         self.ex_candles(c, q, BOT_URL_AT, T + BOT_URL_AT, source="bot_url"))

    def minute_line(self, q):
        with self.lock:
            rs = [r for r in self.rows if r["q"] == q]
        out = {}
        for s in SOURCES:
            g = [r for r in rs if r["source"] == s and r.get("t_req")]
            if g:
                lag = [r["t_req"] - r["t_plan"] for r in g]
                out[s] = [len(g), sum(1 for r in g if r.get("present")), round(max(lag), 2)]
        return out

    def run(self, minutes, out):
        os.makedirs(out, exist_ok=True)
        q0 = pd.Timestamp(math.ceil(time.time() / 60 + 0.02) * 60, unit="s")
        qs = [q0 + pd.Timedelta(minutes=i) for i in range(minutes)]
        self.log(f"candle probe: {len(self.coins)} coins {self.coins}, boundaries {qs[0]} to {qs[-1]}, out {out}")
        started = time.time()
        for i, q in enumerate(qs):
            while time.time() < q.timestamp() - 1:
                time.sleep(0.2)
            self.schedule(q)
            if i >= 1:                                   # the previous minute's timed requests are done by now
                self.log(json.dumps({"q": f"{qs[i - 1]:%H:%M}", "src": self.minute_line(qs[i - 1]),
                                     "stopped": list(self.stopped)}))
        end = qs[-1].timestamp() + REF_AT + 60
        while time.time() < end or self.ex.pending() or self.adv.pending():
            time.sleep(1)
            if time.time() > end + 120:
                break
        self.pool.shutdown(wait=True)
        df = to_frame(self.rows)
        df.to_parquet(os.path.join(out, "obs.parquet"), index=False)
        meta = dict(coins=self.coins, first_q=str(qs[0]), last_q=str(qs[-1]), minutes=minutes,
                    started=pd.Timestamp(started, unit="s").isoformat(), ended=pd.Timestamp.now().isoformat(),
                    stopped=self.stopped, errors=self.errors, ex_interval=EX_INTERVAL, adv_interval=ADV_INTERVAL,
                    candle_delays=CANDLE_DELAYS, trade_delays=TRADE_DELAYS, adv_delay=ADV_DELAY, ref_at=REF_AT,
                    bot_url_at=BOT_URL_AT, windows={str(k): v for k, v in WINDOW_MINUTES.items()},
                    rows=len(df))
        with open(os.path.join(out, "run.json"), "w") as fh:
            json.dump(meta, fh, indent=1)
        self.log(f"done: {len(df)} rows; stopped {self.stopped}; errors {self.errors}")
        self.log(spread(df).to_string(index=False))
        return df


def to_frame(rows):
    df = pd.DataFrame(rows)
    for c in ("t_plan", "t_req", "t_resp", "pages", "n_trades"):
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
    for c in ("present", "capped"):
        df[c] = df[c].astype("boolean").fillna(False).astype(bool) if c in df else False
    for c in ("age",):
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
    if "cache" not in df:
        df["cache"] = None
    q = df.q.map(lambda x: x.timestamp())
    df["plan_s"], df["req_s"], df["resp_s"] = df.t_plan - q, df.t_req - q, df.t_resp - q
    df["gen_s"] = df.resp_s - df.age.fillna(0)          # when the venue made the answer (Age is whole seconds)
    df["gen_date_s"] = (pd.to_numeric(df["date"], errors="coerce") if "date" in df else np.nan) - df.age.fillna(0) - q
    for c in ("t_plan", "t_req", "t_resp"):
        df[c] = pd.to_datetime(df[c], unit="s").astype("datetime64[ms]")
    return df.sort_values(["source", "coin", "minute", "delay"]).reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ analysis
def spread(df):
    """Actual request time minus planned, per source and delay (seconds)."""
    d = df[df.req_s.notna()].copy()
    d["lag"] = d.req_s - d.plan_s
    g = d.groupby(["source", "delay"])
    return g.lag.describe(percentiles=[.5, .95, .99])[["count", "min", "50%", "95%", "99%", "max"]].round(3) \
        .join(g.resp_s.median().round(2).rename("resp_s_median")).reset_index()


def reference(df):
    r = df[(df.source == "ref") & (df.status == "ok") & df.present & (df.gen_s >= REF_MIN_GEN)]
    r = r.sort_values("t_req").drop_duplicates(["coin", "minute"], keep="last")
    return r.set_index(["coin", "minute"])[["open", "high", "low", "close", "volume", "req_s"]]


def sigma(ref):
    out = {}
    for c, g in ref.reset_index().groupby("coin"):
        g = g.sort_values("minute")
        cons = g.minute.diff().eq(pd.Timedelta(minutes=1))
        out[c] = float(np.log(g.close).diff()[cons].std())
    return out


def compare(obs, ref, sig):
    """One row per counted coin-minute for one source at one delay: missing, exact, material, errors in bp."""
    o = obs.drop_duplicates(["coin", "minute"]).set_index(["coin", "minute"])
    j = ref.join(o[["status", "present", "open", "high", "low", "close", "volume", "req_s", "resp_s", "age"]],
                 rsuffix="_o", how="left")
    present = (j.status == "ok") & j.present.astype("boolean").fillna(False).astype(bool)
    s = j.index.get_level_values(0).map(sig).astype(float)
    cerr = (np.log(j.close_o / j.close) * 1e4).abs()
    lerr = (np.log(j.low_o / j.low) * 1e4)
    exact = present & (j.high_o == j.high) & (j.low_o == j.low) & (j.close_o == j.close) \
        & ((j.volume_o / j.volume - 1).abs() <= 0.005)
    material = ~present | (cerr > 0.5 * s * 1e4) | (lerr.abs() > 5)
    return pd.DataFrame(dict(missing=~present, failed=j.status.ne("ok") & j.status.notna(),
                             exact=exact, material=material, cerr=cerr.where(present), lerr=lerr.where(present),
                             vshare=(j.volume_o / j.volume).where(present), age=j.age), index=j.index)


def measures(df, fresh_only=False):
    """The plan's measures 1 to 4 per source and delay. fresh_only (descriptive, not the plan's): only coin-minutes
    whose answer was made fresh for the request (Age at most 1 s)."""
    ref = reference(df)
    sig = sigma(ref)
    rows, per = [], {}
    for (src, d), g in df[df.source != "ref"].groupby(["source", "delay"]):
        m = compare(g, ref, sig)
        if fresh_only:
            m = m[m.age.fillna(0) <= 1]
        per[(src, d)] = m
        lag = (g.req_s - g.plan_s)
        rows.append(dict(source=src, delay=d, req_s_median=round(g.req_s.median(), 2),
                         req_lag_p95=round(lag.quantile(.95), 2), coin_minutes=len(m),
                         missing=round(m.missing.mean() * 100, 2), failed=int(m.failed.sum()),
                         exact=round(m.exact.mean() * 100, 2), material=round(m.material.mean() * 100, 2),
                         close_bp_med=round(m.cerr.median(), 2), close_bp_p95=round(m.cerr.quantile(.95), 2),
                         close_bp_max=round(m.cerr.max(), 2),
                         low_bp_med=round(m.lerr.abs().median(), 2), low_bp_p95=round(m.lerr.abs().quantile(.95), 2),
                         low_bp_max=round(m.lerr.abs().max(), 2),
                         vol_share_med=round(m.vshare.median(), 3), vol_share_p5=round(m.vshare.quantile(.05), 3)))
    return pd.DataFrame(rows), per, ref, sig


def trades_timing(df):
    """Measure 5: pages per coin-minute, and per minute the time from the first request to the last response over
    all coins (only minutes where every coin's trades call finished)."""
    t = df[df.source == "ex_trades"]
    out = []
    for d, g in t.groupby("delay"):
        ok = g[g.status == "ok"]
        span = ok.groupby("q").agg(n=("coin", "size"), first=("req_s", "min"), last=("resp_s", "max"))
        full = span[span.n == len(df.coin.unique())]
        w = full["last"] - full["first"]
        out.append(dict(delay=d, minutes=len(span), minutes_all_coins=len(full),
                        pages_mean=round(ok.pages.mean(), 3), pages_max=int(ok.pages.max()),
                        pages_gt1_share=round((ok.pages > 1).mean() * 100, 2), capped=int(ok.capped.sum()),
                        span_s_median=round(w.median(), 2), span_s_p99=round(w.quantile(.99), 2),
                        span_s_max=round(w.max(), 2), within_2s=round((w <= 2).mean() * 100, 2),
                        last_resp_s_median=round(full["last"].median(), 2), last_resp_s_p99=round(full["last"].quantile(.99), 2)))
    return pd.DataFrame(out)


def decide(tab, tt):
    use = tab[tab.material <= 1.0]
    tr = use[(use.source == "ex_trades") & use.delay.isin(TRADE_DELAYS)]
    fast = [int(d) for d in tr.delay if float(tt.loc[tt.delay == d, "within_2s"].iloc[0]) >= 99]
    if fast:
        return "A", f"trades usable at {fast} s with all coins within 2 s in at least 99% of minutes"
    cd = use[(use.source.isin(["ex_candles", "adv_candles"])) & (use.delay <= 25)]
    if len(cd):
        best = cd.sort_values("delay").iloc[0]
        return "B", f"candles usable at {int(best.delay)} s ({best.source}); smallest usable delay of 25 s or less"
    return "C", "no source usable at a delay of 25 s or less: no change now; a live trade feed is its own project"


def by_coin(per, keys):
    cols = {}
    for k in keys:
        if k in per:
            cols[f"{k[0]} {k[1]}s"] = (per[k].material.groupby(level=0).mean() * 100).round(1)
    return pd.DataFrame(cols)


def collector_check(root, coins):
    """Material-error share of the bot's 6 s candle in the forward collector's revision log, for the probe's coins.
    Reference: the candle's values at the collector's fetch 186 s after the minute closed (its last change). A minute counts
    if the collector made the decision fetch for it (minute m is fetched first at m + 1 min + 6 s); a first sighting
    later than that means it was missing at the decision."""
    import glob
    import read as R
    days = sorted({os.path.basename(p) for p in glob.glob(os.path.join(root, "forward", "candles", "*"))})
    cd = pd.concat([R.load("candles", d, root=root) for d in days], ignore_index=True)
    cd = cd[cd.coin.astype(str).isin(coins)].copy()
    cd["coin"] = cd.coin.astype(str)
    cd["age"] = (cd.seen - cd.minute).dt.total_seconds() - 60      # seconds after the minute closed
    cd = cd.sort_values("seen")
    first = cd.groupby(["coin", "minute"]).first()
    last = cd.groupby(["coin", "minute"]).last()
    fetched = set(cd.seen.dt.floor("min"))
    ms = last.index.get_level_values(1)
    dec = np.array([m + pd.Timedelta(minutes=1) in fetched for m in ms], dtype=bool)
    # the log keeps a row only on change, so the last row holds the values of every later fetch; the candle is
    # still in the bot's 5-minute window at the fetch in minute m + 4 (186 s after it closed)
    late = np.array([m + pd.Timedelta(minutes=4) in fetched for m in ms], dtype=bool)
    ref = last[dec & late]
    sig = sigma(ref)
    f = first.loc[ref.index]
    present = f.age < 60
    cerr = (np.log(f.close / ref.close) * 1e4).abs()
    lerr = (np.log(f.low / ref.low) * 1e4).abs()
    s = ref.index.get_level_values(0).map(sig).astype(float)
    material = ~present | (cerr > 0.5 * s * 1e4) | (lerr > 5)
    exact = present & (f.high == ref.high) & (f.low == ref.low) & (f.close == ref.close) \
        & ((f.volume / ref.volume - 1).abs() <= 0.005)
    return dict(coin_minutes=int(len(ref)), material=round(float(material.mean() * 100), 2),
                missing=round(float((~present).mean() * 100), 2), exact=round(float(exact.mean() * 100), 2),
                first=str(ref.index.get_level_values(1).min()), last=str(ref.index.get_level_values(1).max()))


def cache_table(df, by_coin=False):
    """Descriptive: how often each source and delay was answered from the cache, how old the answer was (Age), and
    how often the answer was made before the boundary (generation time = response time minus Age, and Date minus
    Age as a check)."""
    d = df[df.status == "ok"]
    keys = ["source", "delay"] + (["coin"] if by_coin else [])
    g = d.groupby(keys)
    gd = d.get("gen_date_s", pd.Series(np.nan, index=d.index))
    return pd.DataFrame(dict(n=g.size(), hit_share=g.cache.apply(lambda x: round((x == "HIT").mean() * 100, 1)),
                             age_gt1_share=g.age.apply(lambda x: round((x.fillna(0) > 1).mean() * 100, 1)),
                             age_gt10_share=g.age.apply(lambda x: round((x.fillna(0) > 10).mean() * 100, 1)),
                             age_med=g.age.median(), age_p95=g.age.quantile(.95), age_max=g.age.max(),
                             gen_s_med=g.gen_s.median().round(2),
                             made_before_q=g.gen_s.apply(lambda x: int((x < 0).sum())),
                             made_before_q_by_date=gd.groupby([d[k] for k in keys]).apply(lambda x: int((x < 0).sum()))
                             )).reset_index()


def bot_url_table(df):
    """The paper bot's own URL at 9.5 s, by coin: served from cache, a copy older than 10 s, newest minute stale."""
    b = df[(df.source == "bot_url") & (df.status == "ok")]
    g = b.groupby("coin")
    stale = (b.newest.isna() | (b.newest < b.minute))
    return pd.DataFrame(dict(n=g.size(), hit_share=g.cache.apply(lambda x: round((x == "HIT").mean() * 100, 1)),
                             age_gt10_share=g.age.apply(lambda x: round((x.fillna(0) > 10).mean() * 100, 1)),
                             age_max=g.age.max(),
                             newest_stale_share=stale.groupby(b.coin).mean().mul(100).round(1),
                             asked_minute_missing=g.present.apply(lambda x: round((~x).mean() * 100, 1)))).reset_index()


def staleness(df):
    """Descriptive (not a plan measure): age in minutes of the newest candle a response returned, against the minute
    asked for (q-1). 0 = current; 1 = one minute behind; NaN = an empty or failed response."""
    c = df[(df.status == "ok")].copy()
    c["age_min"] = (c.minute - c.newest.dt.floor("min")).dt.total_seconds() / 60   # trades: newest trade's minute
    g = c.groupby(["source", "delay", "coin"])
    return pd.DataFrame(dict(n=g.size(), empty=g.newest.apply(lambda x: int(x.isna().sum())),
                             current=(g.age_min.apply(lambda x: (x <= 0).mean() * 100)).round(1),
                             age_med=g.age_min.median(), age_p95=g.age_min.quantile(.95), age_max=g.age_min.max(),
                             asked_missing=g.present.apply(lambda x: (~x).mean() * 100).round(1))).reset_index()


def btc_cross(df):
    """Per BTC minute: is the Exchange candle at 6 s stale (newest older than the minute asked), and were the
    Exchange trades for that minute present at 1 s and 3 s?"""
    b = df[df.coin == "BTC"]
    ex = b[(b.source == "ex_candles") & (b.delay == 6)].set_index("minute")
    stale = (ex.newest < ex.index.to_series()) | ex.newest.isna()
    out = {}
    for d in TRADE_DELAYS:
        t = b[(b.source == "ex_trades") & (b.delay == d)].set_index("minute").present.reindex(ex.index)
        out[f"trades_{d}s_present"] = t
    x = pd.DataFrame(dict(candle_6s_stale=stale, **out))
    return x.groupby("candle_6s_stale").agg(minutes=("candle_6s_stale", "size"),
                                             **{k: (k, "mean") for k in out}).round(3).reset_index()


def analyze(path, collector_root=None, out=None):
    df = pd.read_parquet(path)
    for c in ("age", "cache"):
        if c not in df:
            df[c] = np.nan if c == "age" else None
    if "gen_s" not in df:
        df["gen_s"] = df.resp_s - df.age.fillna(0)
    tab, per, ref, sig = measures(df)
    tt = trades_timing(df)
    verdict = decide(tab, tt)
    keys = [("ex_candles", 6), ("ex_candles", 25), ("ex_candles", 40), ("adv_candles", 6), ("ex_trades", 1),
            ("ex_trades", 3)]
    bc = by_coin(per, keys)
    res = dict(tab=tab, trades=tt, verdict=verdict, by_coin=bc, spread=spread(df), sigma_bp={k: round(v * 1e4, 2)
               for k, v in sig.items()}, ref_minutes=int(len(ref)))
    res["fresh_only"] = measures(df, fresh_only=True)[0]
    res["cache"] = cache_table(df)
    res["cache_by_coin"] = cache_table(df, by_coin=True)
    if "bot_url" in set(df.source):
        res["bot_url"] = bot_url_table(df)
    if "newest" in df:
        res["staleness"] = staleness(df)
        if "BTC" in set(df.coin):
            res["btc_cross"] = btc_cross(df)
    if "BTC" in set(df.coin):                           # the plan's amendment: BTC is also reported on its own
        b = df[df.coin == "BTC"]
        res["btc"] = measures(b)[0]
        res["btc_trades"] = trades_timing(b)
    if collector_root:
        res["collector"] = collector_check(collector_root, list(df.coin.unique()))
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    for k, v in res.items():
        print(f"== {k}")
        print(v.to_string(index=not isinstance(v.index, pd.RangeIndex)) if isinstance(v, pd.DataFrame) else v)
    if out:
        os.makedirs(out, exist_ok=True)
        tab.to_csv(os.path.join(out, "measures.csv"), index=False)
        tt.to_csv(os.path.join(out, "trades_timing.csv"), index=False)
        bc.to_csv(os.path.join(out, "by_coin_material.csv"))
        res["spread"].to_csv(os.path.join(out, "request_spread.csv"), index=False)
        res["fresh_only"].to_csv(os.path.join(out, "measures_fresh_only.csv"), index=False)
        res["cache"].to_csv(os.path.join(out, "cache.csv"), index=False)
        res["cache_by_coin"].to_csv(os.path.join(out, "cache_by_coin.csv"), index=False)
        if "bot_url" in res:
            res["bot_url"].to_csv(os.path.join(out, "bot_url.csv"), index=False)
        if "staleness" in res:
            res["staleness"].to_csv(os.path.join(out, "staleness.csv"), index=False)
        if "btc_cross" in res:
            res["btc_cross"].to_csv(os.path.join(out, "btc_candle_vs_trades.csv"), index=False)
        if "btc" in res:
            res["btc"].to_csv(os.path.join(out, "btc_measures.csv"), index=False)
            res["btc_trades"].to_csv(os.path.join(out, "btc_trades_timing.csv"), index=False)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("collect")
    a1.add_argument("--minutes", type=int, required=True)
    a1.add_argument("--out", default="probe_out")
    a1.add_argument("--coins", default=",".join(COINS))
    a2 = sub.add_parser("analyze")
    a2.add_argument("obs")
    a2.add_argument("--collector", default=None, help="a checkout of the forward data branch, for the consistency check")
    a2.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "collect":
        Probe(a.coins.split(",")).run(a.minutes, a.out)
    else:
        analyze(a.obs, a.collector, a.out)


if __name__ == "__main__":
    sys.exit(main())
