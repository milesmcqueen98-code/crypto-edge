#!/usr/bin/env python3
"""Forward data collector: logs, once a minute, what cannot be backfilled later.

Four independent streams per minute (UTC), timed around the spot bot's decision at second 6:
  book     Coinbase spot order book per coin, sampled so it is complete by second 5
  hl       Hyperliquid perps (open interest, funding, mark/oracle/mid, impact prices), one POST at second 5
  candles  the bot's own candle request at second 6, kept as a revision log (a row when a candle is first seen and
           again whenever one of its five values changes)
  cfm      Coinbase US perp-style futures (price, open interest, funding), one request at second 12

Files are immutable: one parquet per stream per hour, forward/<stream>/<YYYY-MM-DD>/<HH>-<run>.parquet, written
when the hour closes (or at exit). Git mode commits them to the forward-data branch; --no-git just writes them.

  python scripts/forward/collector.py --out fwd --minutes 345            # git mode (GitHub Actions)
  python scripts/forward/collector.py --out /data/fwd --no-git --minutes 0   # plain server, forever
See scripts/forward/README.md.
"""
import argparse
import collections
import glob
import json
import math
import os
import random
import signal
import subprocess
import sys
import threading
import time

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
USER_AGENT = "crypto-edge-bot/1.0"
EXCHANGE = "https://api.exchange.coinbase.com"
ADV = "https://api.coinbase.com/api/v3/brokerage/market"
HL_URL = "https://api.hyperliquid.xyz/info"
BID_BPS = (5, 10, 25, 50, 100, 150, 200, 300, 400, 600, 800)
ASK_BPS = (5, 10, 25, 50, 100)
STREAMS = ("book", "hl", "candles", "cfm")
CB_INTERVAL = 0.2            # seconds between Coinbase request starts: 5 a second, under the 6/s budget
BOOK_DONE = 5.0              # the book burst should be complete by this second of the minute
BOOK_LATENCY = 0.6           # expected response time of the slowest book request (from the runner probe)
BOOK_LAST_START = 4.7        # no book request (or retry) starts after this second
CANDLE_AT, HL_AT, CFM_AT = 6.0, 5.0, 12.0
RETRY_UNTIL = {"book": BOOK_LAST_START, "hl": 40.0, "candles": 40.0, "cfm": 50.0}
CANDLE_MINUTES = 5           # the last 5 one-minute candles per request
EPS = 1e-10                  # bucket boundaries are inclusive despite float rounding (100 * 1.005 = 100.49999...)
GIT_NAME, GIT_EMAIL = "crypto-edge-bot", "crypto-edge-bot"


def universe(meta=None):
    meta = meta or os.path.join(REPO, "bot", "v2", "model_meta.json")
    with open(meta) as fh:
        coins = json.load(fh)["coins"]
    return ["BTC"] + [c for c in coins if c != "BTC"]


def now_utc():
    return pd.Timestamp(time.time(), unit="s")


def fnum(x):
    """float or NaN for '', None and junk."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return math.nan


class Refused(Exception):
    """The venue refused this client (403, 451, a bot check). The stream stops for the rest of the run."""


# ------------------------------------------------------------------------------------------------ parsers
def parse_exchange_book(js):
    """Coinbase Exchange /book?level=2: {"bids": [[price, size, n_orders], ...], "asks": ...} -> (bids, asks)."""
    b = [(float(p), float(s)) for p, s, *_ in js.get("bids") or []]
    a = [(float(p), float(s)) for p, s, *_ in js.get("asks") or []]
    return b, a


def parse_adv_book(js):
    pb = js.get("pricebook") or {}
    b = [(float(x["price"]), float(x["size"])) for x in pb.get("bids") or []]
    a = [(float(x["price"]), float(x["size"])) for x in pb.get("asks") or []]
    return b, a


def depth_buckets(levels, ref, side, bps):
    """Cumulative USD resting within each bp distance of `ref` (inclusive). NaN where the returned book does not reach
    that far (its last level is inside the bucket boundary), so a truncated book never reads as zero depth."""
    out = np.full(len(bps), np.nan)
    if not levels or not np.isfinite(ref):
        return out
    px = np.array([p for p, _ in levels], dtype=float)
    usd = px * np.array([s for _, s in levels], dtype=float)
    if side == "bid":
        order = np.argsort(-px, kind="stable")
        px, usd = px[order], usd[order]
        cum = np.cumsum(usd)
        for i, bp in enumerate(bps):
            thr = ref * (1 - bp / 1e4)
            if px[-1] > thr * (1 + EPS):
                continue                                       # not reached
            k = int(np.searchsorted(-px, -thr * (1 - EPS), side="right"))  # levels with price >= thr
            out[i] = cum[k - 1] if k else 0.0
    else:
        order = np.argsort(px, kind="stable")
        px, usd = px[order], usd[order]
        cum = np.cumsum(usd)
        for i, bp in enumerate(bps):
            thr = ref * (1 + bp / 1e4)
            if px[-1] < thr * (1 - EPS):
                continue
            k = int(np.searchsorted(px, thr * (1 + EPS), side="right"))    # levels with price <= thr
            out[i] = cum[k - 1] if k else 0.0
    return out


def book_row(coin, minute, bids, asks, t_req, t):
    bids = sorted(bids, key=lambda x: -x[0])
    asks = sorted(asks, key=lambda x: x[0])
    bb = bids[0] if bids else (math.nan, math.nan)
    ba = asks[0] if asks else (math.nan, math.nan)
    mid = (bb[0] + ba[0]) / 2 if bids and asks else math.nan
    r = dict(coin=coin, minute=minute, t_req=t_req, t=t, ok=True, bid=bb[0], bid_sz=bb[1], ask=ba[0], ask_sz=ba[1],
             mid=mid, n_bid=len(bids), n_ask=len(asks),
             bid_reach_bp=(1 - bids[-1][0] / mid) * 1e4 if bids and np.isfinite(mid) else math.nan,
             ask_reach_bp=(asks[-1][0] / mid - 1) * 1e4 if asks and np.isfinite(mid) else math.nan)
    for bp, v in zip(BID_BPS, depth_buckets(bids, mid, "bid", BID_BPS)):
        r[f"bid_usd_{bp}"] = v
    for bp, v in zip(ASK_BPS, depth_buckets(asks, mid, "ask", ASK_BPS)):
        r[f"ask_usd_{bp}"] = v
    return r


def missing_book_row(coin, minute, t_req):
    r = dict(coin=coin, minute=minute, t_req=t_req, t=pd.NaT, ok=False, n_bid=0, n_ask=0)
    for k in ("bid", "bid_sz", "ask", "ask_sz", "mid", "bid_reach_bp", "ask_reach_bp"):
        r[k] = math.nan
    for bp in BID_BPS:
        r[f"bid_usd_{bp}"] = math.nan
    for bp in ASK_BPS:
        r[f"ask_usd_{bp}"] = math.nan
    return r


def candle_params(T):
    """Exactly what bot/market.py spot_candles(coin, T - 5 min, T) sends for the window ending at minute T."""
    s = pd.Timestamp(T).floor("min") - pd.Timedelta(minutes=CANDLE_MINUTES)
    e = pd.Timestamp(T).floor("min")
    return {"granularity": 60, "start": s.isoformat() + "Z", "end": (e - pd.Timedelta(minutes=1)).isoformat() + "Z"}


def parse_candles(js, T):
    """Exchange candles [[time, low, high, open, close, volume], ...] -> {minute: (o, h, l, c, v)} inside the window,
    the same filter as spot_candles."""
    out = {}
    lo = pd.Timestamp(T).floor("min") - pd.Timedelta(minutes=CANDLE_MINUTES)
    hi = pd.Timestamp(T).floor("min")
    for t, low, high, op, cl, vo in js or []:
        m = pd.Timestamp(int(t), unit="s")
        if lo <= m < hi:
            out[m] = (float(op), float(high), float(low), float(cl), float(vo))
    return out


class CandleLog:
    """Revision log: a row the first time a (coin, minute) candle is seen and whenever any of its values changes."""

    def __init__(self, keep_minutes=30):
        self.last = {}
        self.keep = pd.Timedelta(minutes=keep_minutes)

    def update(self, coin, candles, t_req, seen):
        rows = []
        for m in sorted(candles):
            v = candles[m]
            old = self.last.get((coin, m))
            if old is not None and old[0] == v:
                continue
            rev = 0 if old is None else old[1] + 1
            self.last[(coin, m)] = (v, rev)
            o, h, l, c, vol = v
            rows.append(dict(coin=coin, minute=m, t_req=t_req, seen=seen, open=o, high=h, low=l, close=c, volume=vol,
                             rev=rev))
        return rows

    def prune(self, now):
        cut = now - self.keep
        for k in [k for k in self.last if k[1] < cut]:
            del self.last[k]


def hl_names(meta_universe, coins=None):
    """Hyperliquid perps to log -> {coin: (name, index, price multiplier)}. Universe coins map by name or k-prefix
    (kPEPE quotes 1000 PEPE); with coins=None every listed (not delisted) perp is kept, k-names under the bare coin."""
    idx = {u["name"]: (i, u) for i, u in enumerate(meta_universe)}
    out = {}
    if coins is None:
        for name, (i, u) in idx.items():
            if u.get("isDelisted", False):
                continue
            coin, mult = (name[1:], 1000) if name.startswith("k") and name[1:2].isupper() else (name, 1)
            out.setdefault(coin, (name, i, mult))
        return out
    for c in coins:
        for name, mult in ((c, 1), ("k" + c, 1000)):
            if name in idx and not idx[name][1].get("isDelisted", False):
                out[c] = (name, idx[name][0], mult)
                break
    return out


def parse_hl(js, coins, minute, t):
    meta, ctxs = js[0], js[1]
    rows = []
    for c, (name, i, mult) in hl_names(meta["universe"], coins).items():
        x = ctxs[i]
        imp = x.get("impactPxs") or [None, None]
        rows.append(dict(coin=c, minute=minute, t=t, ok=True, name=name, px_mult=mult,
                         open_interest=fnum(x.get("openInterest")), mark=fnum(x.get("markPx")),
                         oracle=fnum(x.get("oraclePx")), mid=fnum(x.get("midPx")), funding=fnum(x.get("funding")),
                         premium=fnum(x.get("premium")), impact_bid=fnum(imp[0]), impact_ask=fnum(imp[1]),
                         day_ntl_vlm=fnum(x.get("dayNtlVlm")), prev_day_px=fnum(x.get("prevDayPx"))))
    return rows


def is_cfm_perp(p):
    f = p.get("future_product_details") or {}
    pid = (p.get("product_id") or "").upper()
    return (f.get("contract_expiry_type") == "PERPETUAL" or bool(f.get("funding_interval"))
            or "PERP" in (p.get("display_name") or "").upper() or "20DEC30" in pid)


def _seconds(x):
    """'3600s' -> 3600.0"""
    if isinstance(x, str) and x.endswith("s"):
        x = x[:-1]
    return fnum(x)


def _ts(x):
    if not x:
        return pd.NaT
    try:
        t = pd.Timestamp(x)
        return t.tz_convert(None) if t.tzinfo else t
    except (TypeError, ValueError):
        return pd.NaT


def parse_cfm(js, coins=None, minute=None, t=None):
    """Every perpetual-style product the futures venue lists (coins=None), or only those on `coins`. Fields the
    response does not carry are stored as missing."""
    want = set(coins) if coins else None
    rows = []
    for p in js.get("products") or []:
        f = p.get("future_product_details") or {}
        if not is_cfm_perp(p):
            continue
        root = (f.get("contract_root_unit") or p.get("base_display_symbol") or "").upper()
        if want is not None and root not in want:
            continue
        perp = f.get("perpetual_details") or {}
        im, om = f.get("intraday_margin_rate") or {}, f.get("overnight_margin_rate") or {}
        rows.append(dict(coin=root, minute=minute, t=t, ok=True, product_id=p.get("product_id"),
                         price=fnum(p.get("price")), mid_market=fnum(p.get("mid_market_price")),
                         best_bid=fnum(p.get("best_bid_price")), best_ask=fnum(p.get("best_ask_price")),
                         mark_price=fnum(f.get("mark_price") or perp.get("mark_price")),
                         index_price=fnum(f.get("index_price")),
                         settlement_price=fnum(f.get("settlement_price")),
                         open_interest=fnum(f.get("open_interest") or perp.get("open_interest")),
                         contract_size=fnum(f.get("contract_size")),
                         funding_rate=fnum(f.get("funding_rate") or perp.get("funding_rate")),
                         funding_time=_ts(f.get("funding_time") or perp.get("funding_time")),
                         funding_interval_s=_seconds(f.get("funding_interval")),
                         volume_24h=fnum(p.get("volume_24h")),
                         quote_volume_24h=fnum(p.get("approximate_quote_24h_volume")),
                         im_long=fnum(im.get("long_margin_rate")), im_short=fnum(im.get("short_margin_rate")),
                         om_long=fnum(om.get("long_margin_rate")), om_short=fnum(om.get("short_margin_rate")),
                         trading_disabled=bool(p.get("trading_disabled"))))
    return rows


# ------------------------------------------------------------------------------------------------ storage
F32, F64, MS = "float32", "float64", "datetime64[ms]"
SCHEMA = {
    "book": dict(coin="category", minute=MS, t_req=MS, t=MS, ok="bool", bid=F64, bid_sz=F32, ask=F64, ask_sz=F32,
                 mid=F64, n_bid="int32", n_ask="int32", bid_reach_bp=F32, ask_reach_bp=F32,
                 **{f"bid_usd_{b}": F32 for b in BID_BPS}, **{f"ask_usd_{b}": F32 for b in ASK_BPS}),
    "candles": dict(coin="category", minute=MS, t_req=MS, seen=MS, open=F64, high=F64, low=F64, close=F64,
                    volume=F64, rev="int16"),
    "hl": dict(coin="category", minute=MS, t=MS, ok="bool", name="category", px_mult="int16", open_interest=F64,
               mark=F64, oracle=F64, mid=F64, funding=F64, premium=F32, impact_bid=F64, impact_ask=F64,
               day_ntl_vlm=F64, prev_day_px=F64),
    "cfm": dict(coin="category", minute=MS, t=MS, ok="bool", product_id="category", price=F64, mid_market=F64,
                best_bid=F64, best_ask=F64, mark_price=F64, index_price=F64, settlement_price=F64,
                open_interest=F64, contract_size=F32, funding_rate=F64, funding_time=MS, funding_interval_s=F32,
                volume_24h=F64, quote_volume_24h=F64, im_long=F32, im_short=F32, om_long=F32, om_short=F32,
                trading_disabled="bool"),
}
KEYS = {"book": ["coin", "minute"], "hl": ["coin", "minute"], "cfm": ["product_id", "minute"],
        "candles": ["coin", "minute", "seen"]}


def frame(stream, rows):
    sch = SCHEMA[stream]
    df = pd.DataFrame(rows)
    for c in sch:
        if c not in df:
            df[c] = pd.NaT if sch[c] == MS else (False if sch[c] == "bool" else np.nan)
    df = df[list(sch)]
    for c, dt in sch.items():
        if dt == MS:
            df[c] = pd.to_datetime(df[c]).astype(MS)
        elif dt == "bool":
            df[c] = df[c].fillna(False).astype(bool)
        elif dt.startswith("int"):
            df[c] = pd.to_numeric(df[c]).fillna(0).astype(dt)
        else:
            df[c] = df[c].astype(dt)
    return df


def hour_path(out, stream, hour, run):
    d = pd.Timestamp(hour)
    base = os.path.join(out, "forward", stream, d.strftime("%Y-%m-%d"), f"{d:%H}-{run}")
    p, n = base + ".parquet", 1
    while os.path.exists(p):                   # never overwrite: a restarted process gets a new name
        n += 1
        p = f"{base}-{n}.parquet"
    return p


def write_hour(out, stream, hour, run, rows):
    df = frame(stream, rows)
    p = hour_path(out, stream, hour, run)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    df.to_parquet(tmp, compression="zstd", index=False)
    os.replace(tmp, p)
    return p


# ------------------------------------------------------------------------------------------------ git publishing
class GitPublisher:
    """Publishes new files to a branch without ever needing its old blobs: fetch the tip (trees only), point the
    index at it, add our files, commit, push. A concurrent push just means doing it again on the new tip; our files
    are new paths, and status.json is simply ours on top, so there is never a merge conflict."""

    def __init__(self, workdir, branch, remote="origin", log=print):
        self.dir, self.branch, self.remote, self.log = workdir, branch, remote, log
        self.pending = set()
        self.lock = threading.Lock()

    def git(self, *args, check=True):
        cmd = ["git", "-c", f"user.name={GIT_NAME}", "-c", f"user.email={GIT_EMAIL}", "-C", self.dir, *args]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if check and r.returncode:
            raise RuntimeError(f"git {' '.join(args[:3])}: {r.stderr.strip()[-300:]}")
        return r

    @staticmethod
    def setup(workdir, branch, repo=REPO, remote="origin"):
        """Make `workdir` a no-checkout worktree of `repo` on the remote branch's tip (blobs not downloaded)."""
        if os.path.exists(os.path.join(workdir, ".git")):
            return
        def g(*a):
            r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, timeout=300)
            if r.returncode:
                raise RuntimeError(f"git {' '.join(a[:3])}: {r.stderr.strip()[-300:]}")
        if not subprocess.run(["git", "-C", repo, "config", f"remote.{remote}.promisor"], capture_output=True).stdout:
            g("config", f"remote.{remote}.promisor", "true")
            g("config", f"remote.{remote}.partialclonefilter", "blob:none")
        g("fetch", "--depth=1", "--filter=blob:none", remote, branch)
        g("worktree", "add", "--no-checkout", "--detach", os.path.abspath(workdir), "FETCH_HEAD")

    def add(self, paths):
        with self.lock:
            self.pending.update(os.path.relpath(p, self.dir) for p in paths)

    def publish(self, message, tries=8):
        with self.lock:
            todo = sorted(self.pending)
        if not todo:
            return True
        for a in range(tries):
            try:
                self.git("fetch", "--depth=1", "--filter=blob:none", self.remote, self.branch)
                self.git("reset", "-q", "--mixed", "FETCH_HEAD")
                self.git("add", "--sparse", "-f", "--", *[p for p in todo if os.path.exists(os.path.join(self.dir, p))])
                if self.git("diff", "--cached", "--quiet", check=False).returncode == 0:
                    break                               # everything is already on the branch
                self.git("commit", "-q", "-m", message)
                self.git("push", "-q", self.remote, f"HEAD:refs/heads/{self.branch}")
                break
            except Exception as err:
                self.log(f"publish attempt {a + 1} failed: {err}")
                time.sleep(min(60, 3 * 2 ** a) * (0.5 + random.random()))
        else:
            return False
        with self.lock:
            self.pending.difference_update(todo)
        return True


# ------------------------------------------------------------------------------------------------ collector
class RateLimiter:
    def __init__(self, interval):
        self.interval, self.next, self.lock = interval, 0.0, threading.Lock()

    def acquire(self, deadline=None, clock=time.time):
        with self.lock:
            slot = max(clock(), self.next)
            if deadline is not None and slot > deadline:
                return False
            self.next = slot + self.interval
        d = slot - clock()
        if d > 0:
            time.sleep(d)
        return True


class Http:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT

    def request(self, method, url, timeout, **kw):
        r = self.s.request(method, url, timeout=timeout, **kw)
        body = r.text[:400].lower() if r.status_code != 200 else ""
        if r.status_code in (403, 451) or "captcha" in body or "just a moment" in body or "cf-chl" in body:
            raise Refused(f"{r.status_code} {url.split('?')[0]} {r.text[:120]!r}")
        if r.status_code == 429:
            raise requests.HTTPError("429 rate limited")
        r.raise_for_status()
        return r.json()


class Collector:
    def __init__(self, out, run, coins, git=None, until=None, http=None, log=None, book_source="exchange",
                 hl_all=True, cfm_all=True):
        self.out, self.run, self.coins, self.git, self.until = out, run, coins, git, until
        self.http = http or Http()
        self.cb = RateLimiter(CB_INTERVAL)
        self.book_source = book_source
        self.hl_all, self.cfm_all = hl_all, cfm_all
        self.candles = CandleLog()
        self.buf = collections.defaultdict(list)          # (stream, hour) -> rows
        self.blk = threading.Lock()
        self.err = collections.Counter()                  # f"{stream}:{kind}" -> count since start
        self.rows_hist = {s: collections.deque() for s in STREAMS}   # (minute, n ok rows)
        self.refused = {}
        self.threads = {}
        self.last_names = {"hl": [], "cfm": []}
        self.minute_info = collections.defaultdict(dict)
        self.written = []
        self.started = now_utc()
        self.last_beat = None
        self.stop = threading.Event()
        self.log = log or (lambda m: print(m, flush=True))
        self.pub_thread = None
        if git:                                         # a restarted process re-offers files a dead one never pushed
            git.add(glob.glob(os.path.join(out, "forward", "*", "*", "*.parquet")))

    # ---- helpers
    def count(self, stream, kind, n=1):
        self.err[f"{stream}:{kind}"] += n

    def emit(self, stream, minute, rows):
        if not rows:
            return
        h = pd.Timestamp(minute).floor("h")
        with self.blk:
            self.buf[(stream, h)].extend(rows)
            self.rows_hist[stream].append((pd.Timestamp(minute), sum(1 for r in rows if r.get("ok", True))))

    def classify(self, err):
        if isinstance(err, Refused):
            return "refused"
        if isinstance(err, requests.Timeout):
            return "timeout"
        if isinstance(err, requests.HTTPError) and "429" in str(err):
            return "http429"
        if isinstance(err, requests.HTTPError):
            return "http"
        if isinstance(err, requests.RequestException):
            return "net"
        return "parse"

    def call(self, stream, T0, fn, coinbase, last_start):
        """Run `fn` with retries until `last_start` seconds into the minute. Returns (result, t_req) or (None, t_req)."""
        attempt, t_req = 0, None
        while not self.stop.is_set():
            if coinbase and not self.cb.acquire(deadline=T0 + last_start):
                self.count(stream, "deadline")
                return None, t_req
            if not coinbase and time.time() > T0 + last_start:
                self.count(stream, "deadline")
                return None, t_req
            t_req = time.time()
            try:
                return fn(), t_req
            except Exception as err:                    # noqa: BLE001 - every failure is counted, none escapes
                kind = self.classify(err)
                self.count(stream, kind)
                if kind == "refused":
                    self.refused[stream] = str(err)
                    self.log(f"REFUSED {stream}: {err} -- stream stopped for this run")
                    raise
                attempt += 1
                time.sleep(min(2.0, 0.3 * attempt) if stream != "book" else 0.05)
                if time.time() > T0 + last_start:
                    self.count(stream, "deadline")
                    return None, t_req
        return None, t_req

    # ---- streams
    def fetch_book(self, coin):
        if self.book_source == "exchange":
            js = self.http.request("GET", f"{EXCHANGE}/products/{coin}-USD/book", timeout=(1.5, 2.5),
                                   params={"level": 2})
            return parse_exchange_book(js)
        js = self.http.request("GET", f"{ADV}/product_book", timeout=(1.5, 2.5),
                               params={"product_id": f"{coin}-USD", "limit": 1000})
        return parse_adv_book(js)

    def s_book(self, T0, minute):
        start = T0 + BOOK_DONE - BOOK_LATENCY - (len(self.coins) - 1) * CB_INTERVAL
        self._sleep_until(start)
        q = collections.deque(self.coins)
        res = {}
        ql = threading.Lock()

        def worker():
            while True:
                with ql:
                    if not q:
                        return
                    coin = q.popleft()
                try:
                    r, t_req = self.call("book", T0, lambda: self.fetch_book(coin), True, BOOK_LAST_START)
                except Refused:
                    return
                t = time.time()
                res[coin] = (r, t_req, t)

        ws = [threading.Thread(target=worker, daemon=True) for _ in range(4)]
        for w in ws:
            w.start()
        for w in ws:
            w.join(timeout=30)
        rows, times = [], []
        for coin in self.coins:
            r, t_req, t = res.get(coin, (None, None, None))
            treq = pd.Timestamp(t_req, unit="s") if t_req else pd.NaT
            if r is None:
                rows.append(missing_book_row(coin, minute, treq))
                self.count("book", "missing")
            else:
                try:
                    rows.append(book_row(coin, minute, r[0], r[1], treq, pd.Timestamp(t, unit="s")))
                    times.append(t - T0)
                except Exception:                       # noqa: BLE001
                    self.count("book", "parse")
                    rows.append(missing_book_row(coin, minute, treq))
        self.emit("book", minute, rows)
        self.minute_info[minute]["book"] = (sum(r["ok"] for r in rows),
                                            round(min(times), 2) if times else None, round(max(times), 2) if times else None)

    def s_candles(self, T0, minute):
        self._sleep_until(T0 + CANDLE_AT)
        n, first, last = 0, None, None
        for coin in self.coins:
            try:
                js, t_req = self.call("candles", T0, lambda: self.http.request(
                    "GET", f"{EXCHANGE}/products/{coin}-USD/candles", timeout=(2, 4), params=candle_params(minute)),
                    True, RETRY_UNTIL["candles"])
            except Refused:
                return
            if js is None:
                self.count("candles", "missing")
                continue
            seen = time.time()
            first = first if first is not None else t_req - T0
            last = seen - T0
            try:
                rows = self.candles.update(coin, parse_candles(js, minute), pd.Timestamp(t_req, unit="s"),
                                           pd.Timestamp(seen, unit="s"))
            except Exception:                           # noqa: BLE001
                self.count("candles", "parse")
                continue
            n += 1
            self.emit("candles", minute, rows)
        self.candles.prune(minute)
        self.minute_info[minute]["candles"] = (n, round(first, 2) if first is not None else None,
                                               round(last, 2) if last is not None else None)

    def _missing_rows(self, stream, minute):
        return [dict(coin=c, minute=minute, t=pd.NaT, ok=False, **({"name": n} if stream == "hl" else
                                                                     {"product_id": n}))
                for c, n in self.last_names[stream]]

    def s_hl(self, T0, minute):
        self._sleep_until(T0 + HL_AT)
        js, t_req = self.call("hl", T0, lambda: self.http.request("POST", HL_URL, timeout=(2, 5),
                                                                 json={"type": "metaAndAssetCtxs"}),
                              False, RETRY_UNTIL["hl"])
        rows = None
        if js is not None:
            try:
                rows = parse_hl(js, None if self.hl_all else self.coins, minute, pd.Timestamp(time.time(), unit="s"))
                self.last_names["hl"] = [(r["coin"], r["name"]) for r in rows]
            except Exception:                           # noqa: BLE001
                self.count("hl", "parse")
        if rows is None:
            rows = self._missing_rows("hl", minute)
            self.count("hl", "missing")
        self.emit("hl", minute, rows)
        self.minute_info[minute]["hl"] = (sum(r["ok"] for r in rows), round(t_req - T0, 2) if t_req else None)

    def s_cfm(self, T0, minute):
        self._sleep_until(T0 + CFM_AT)
        js, t_req = self.call("cfm", T0, lambda: self.http.request(
            "GET", f"{ADV}/products", timeout=(2, 6),
            # product_type FUTURE lists the US venue (Coinbase Derivatives, *-CDE); its perps say EXPIRING in
            # contract_expiry_type, and filtering on PERPETUAL returns the international venue (*-PERP-INTX) instead
            params={"product_type": "FUTURE", "limit": 500}),
            True, RETRY_UNTIL["cfm"])
        rows = None
        if js is not None:
            try:
                rows = parse_cfm(js, None if self.cfm_all else self.coins, minute, pd.Timestamp(time.time(), unit="s"))
                if (js.get("num_products") or 0) > len(js.get("products") or []):
                    self.count("cfm", "truncated")
                if rows:
                    self.last_names["cfm"] = [(r["coin"], r["product_id"]) for r in rows]
                else:
                    self.count("cfm", "empty")
            except Exception:                           # noqa: BLE001
                self.count("cfm", "parse")
                rows = None
        if not rows:
            rows = self._missing_rows("cfm", minute)
            self.count("cfm", "missing")
        self.emit("cfm", minute, rows)
        self.minute_info[minute]["cfm"] = (sum(r["ok"] for r in rows), round(t_req - T0, 2) if t_req else None)

    def _sleep_until(self, t):
        d = t - time.time()
        if d > 0:
            self.stop.wait(d)

    def _guard(self, stream, fn, T0, minute):
        try:
            fn(T0, minute)
        except Refused:
            pass
        except Exception as err:                        # noqa: BLE001 - a stream must never kill the loop
            self.count(stream, "crash")
            self.log(f"{stream} crashed at {minute}: {err!r}"[:300])

    def launch_minute(self, T0):
        """Start the four streams for the minute that began at epoch second T0; each runs in its own thread."""
        minute = pd.Timestamp(T0, unit="s")
        fns = {"book": self.s_book, "hl": self.s_hl, "candles": self.s_candles, "cfm": self.s_cfm}
        started = []
        for s in STREAMS:
            if s in self.refused:
                continue
            th = self.threads.get(s)
            if th is not None and th.is_alive():        # last minute's burst is still hung: skip, never pile up
                self.count(s, "busy")
                continue
            th = threading.Thread(target=self._guard, args=(s, fns[s], T0, minute), daemon=True, name=s)
            th.start()
            self.threads[s] = th
            started.append(th)
        return started

    # ---- files, status, publishing
    def flush(self, before=None):
        """Write every buffered hour older than `before` (all hours if None). Returns the paths written."""
        with self.blk:
            keys = [k for k in self.buf if before is None or k[1] < before]
            items = [(k, self.buf.pop(k)) for k in sorted(keys, key=lambda k: (k[1], k[0]))]
        paths = []
        for (stream, hour), rows in items:
            try:
                paths.append(write_hour(self.out, stream, hour, self.run, rows))
            except Exception as err:                    # noqa: BLE001
                self.count(stream, "write")
                self.log(f"write {stream} {hour}: {err!r}")
        self.written += paths
        if paths and self.git:
            self.git.add(paths)
        return paths

    def status(self, now=None):
        now = now or now_utc()
        cut = now - pd.Timedelta(hours=1)
        with self.blk:
            for s in STREAMS:
                d = self.rows_hist[s]
                while d and d[0][0] < cut:
                    d.popleft()
            rows = {s: int(sum(n for _, n in self.rows_hist[s])) for s in STREAMS}
            minutes = {s: len(self.rows_hist[s]) for s in STREAMS}
        st = dict(run=self.run, heartbeat=now.isoformat() + "Z", started=self.started.isoformat() + "Z",
                  planned_end=(pd.Timestamp(self.until, unit="s").isoformat() + "Z") if self.until else None,
                  rows_last_hour=rows, bursts_last_hour=minutes, errors=dict(sorted(self.err.items())),
                  refused=self.refused, coins=self.coins, book_source=self.book_source)
        p = os.path.join(self.out, "forward", "status.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w") as fh:
            json.dump(st, fh, indent=1)
        os.replace(p + ".tmp", p)
        if self.git:
            self.git.add([p])
        return st

    def publish(self, why, wait=False):
        if not self.git:
            return
        if self.pub_thread is not None and self.pub_thread.is_alive():
            if not wait:
                return                                   # the next scheduled publish picks the files up
            self.pub_thread.join()
        msg = f"forward data {why} run {self.run} {now_utc():%Y-%m-%dT%H:%MZ}"
        if wait:
            ok = self.git.publish(msg)
            self.log(f"publish ({why}) {'ok' if ok else 'FAILED'}")
            return
        self.pub_thread = threading.Thread(target=lambda: self.log(
            f"publish ({why}) {'ok' if self.git.publish(msg) else 'FAILED'}"), daemon=True)
        self.pub_thread.start()

    def summary_line(self, minute):
        info = self.minute_info.pop(minute, {})
        return json.dumps({"m": f"{minute:%Y-%m-%d %H:%M}", **{k: v for k, v in info.items()},
                           "err": sum(self.err.values())})

    # ---- main loop
    def run_forever(self, minutes=0):
        if minutes:
            self.until = min(self.until or math.inf, time.time() + 60 * minutes)
        self.log(f"collector run {self.run}: {len(self.coins)} coins {self.coins}, book from {self.book_source}, "
                 f"until {pd.Timestamp(self.until, unit='s') if self.until else 'forever'}, out {self.out}, "
                 f"git {'on' if self.git else 'off'}")
        self.status()
        T0 = math.floor(time.time() / 60) * 60
        if time.time() - T0 > 1.0:                      # too late for this minute's book: start at the next one
            T0 += 60
        last_pub = time.time()
        while not self.stop.is_set() and (not self.until or T0 < self.until):
            self._sleep_until(T0)
            if self.stop.is_set():
                break
            self.launch_minute(T0)
            minute = pd.Timestamp(T0, unit="s")
            self._sleep_until(T0 + 56)
            # the previous minute's streams are done by now (deadlines at <= 50 s): log it, rotate hours, publish
            prev = minute - pd.Timedelta(minutes=1)
            if prev in self.minute_info:
                self.log(self.summary_line(prev))
            new = self.flush(before=minute.floor("h"))
            self.status()
            if new or time.time() - last_pub > 29 * 60:
                self.publish("hourly" if new else "status")
                last_pub = time.time()
            T0 += 60
        self.shutdown()

    def shutdown(self):
        self.stop.set()
        for th in list(self.threads.values()):
            th.join(timeout=15)
        last = max(self.minute_info) if self.minute_info else None
        if last is not None:
            self.log(self.summary_line(last))
        paths = self.flush()
        st = self.status()
        self.log(f"exit: wrote {len(paths)} files at exit, {len(self.written)} in total; errors {st['errors']}")
        self.publish("exit", wait=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="output folder (git mode: a worktree of --branch, created if missing)")
    ap.add_argument("--minutes", type=float, default=0, help="run this many minutes; 0 = forever")
    ap.add_argument("--until", type=float, default=None, help="stop at this epoch second (overrides --minutes if sooner)")
    ap.add_argument("--no-git", action="store_true", help="only write files, never commit")
    ap.add_argument("--branch", default="forward-data")
    ap.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID") or "local")
    ap.add_argument("--book-source", choices=["exchange", "advanced"], default="exchange")
    ap.add_argument("--hl-universe-only", action="store_true", help="hl: only the universe coins, not every perp")
    ap.add_argument("--cfm-universe-only", action="store_true", help="cfm: only the universe coins, not every perp")
    ap.add_argument("--meta", default=None, help="model_meta.json with the coin list (default bot/v2/model_meta.json)")
    a = ap.parse_args(argv)
    git = None
    if not a.no_git:
        GitPublisher.setup(a.out, a.branch)
        git = GitPublisher(a.out, a.branch)
    os.makedirs(a.out, exist_ok=True)
    c = Collector(a.out, a.run_id, universe(a.meta), git=git, until=a.until, book_source=a.book_source,
                  hl_all=not a.hl_universe_only, cfm_all=not a.cfm_universe_only)

    def stop(signum, _frame):
        c.log(f"signal {signum}: stopping after this minute's files are written")
        c.stop.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    c.run_forever(a.minutes)


if __name__ == "__main__":
    sys.exit(main())
