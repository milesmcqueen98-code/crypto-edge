"""Research side of the paper reconciliation (reports/owner/paper_reconcile_plan.md). Runs on a GitHub runner.

Books and period (defaults reproduce the first reconciliation): --books, a comma list of paper book folders (default
paper_spot); --start and --end, UTC minutes, both included (default: each book's first event to common.END,
Nov 10 2026 13:30). The live set is the union over the books of the brief's live minutes inside the period
(common.live_minutes_brief), plus, per book, its decision minute just before the period when the period's first
decision minute keeps the bot's armed bids (common.prev_decision_minute: compare.py needs the research state there
to tell whether a research bid at the period's first minute is new). One research_minutes.csv.gz serves every book.

1. Fetch final one-minute candles of BTC and the 17 coins from the public Coinbase Exchange endpoint, far enough back
   that the engine's 11-day table (WINDOW_MIN = 15,840 minutes) is full at the first live minute, through the last
   live minute. At most 300 candles a request, at most 5 requests a second.
   - Every answer's cf-cache-status, Age and Date are recorded. An answer generated (Date minus Age) before its
     newest minute closed plus 180 s is dropped and reported; it is not asked again with an altered address.
   - Refusal policy: HTTP 401, 403, 429, 451 or a non-JSON body stops all fetching at once (no retry); the job
     finishes with what it has and reports it. Network errors and 5xx are retried twice.
2. For every live minute t (common.live_minutes_brief: the brief's set, a superset of the comparison's decision
   minutes) drive the engine's own code minute by minute: the engine's table holds the final candles of
   [t - WINDOW_MIN, t) (what update_spot keeps), then Engine.arrays(t), edge.wick.panel(...) with the engine's own
   arguments, and the engine's scoring (mean of the five bot/v2 models on the panel's last row). No vectorisation.
3. Supplementary (not one of the plan's measures): at every minute with a bot `arm` event inside the period, the same
   computation with BTC's newest one or two minutes missing from the table (what a late BTC answer gives the bot), for
   the armed coin. One engine computation per minute and lag serves every book armed then; with more than one book
   the file has a `book` column (the book folder's name) and one row per book, coin, minute and lag; with one book it
   has the first reconciliation's shape.

Writes derived tables only (no candles) to --out (default reports/owner/reconcile/):
  research_minutes.csv.gz  per live coin-minute: level, score, sigma, valid, final open/high/low of minute t,
                           BTC's one- and two-minute log returns to t-1 (bp), beta behind the level
  late_btc_at_arms.csv     supplementary late-BTC levels and scores at the bot's arm minutes
  fetch_answers.csv        one row per candle answer: coin, window, cache status, Age, Date, generated, dropped
  fetch_run.json           counts, refusals, dropped answers, timings
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")     # one thread per worker process (results do not depend on it)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np          # noqa: E402
import pandas as pd         # noqa: E402

import common               # noqa: E402

EXCHANGE = "https://api.exchange.coinbase.com"
RATE = 5.0
OUT = os.path.join(ROOT, "reports", "owner", "reconcile")


class Refused(RuntimeError):
    pass


_last = [0.0]
_S = None


def session():
    global _S
    if _S is None:
        from bot import market
        _S = market._S                          # the bot's own session and User-Agent, unchanged
    return _S


def get(url, params):
    """One paced GET. Returns (json, headers). Refusals raise Refused at once; 5xx and network errors retried twice."""
    import requests
    for a in range(3):
        wait = _last[0] + 1.0 / RATE - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = session().get(url, params=params, timeout=20)
        except requests.RequestException:
            if a == 2:
                raise
            time.sleep(1 + a)
            continue
        if r.status_code in (401, 403, 429, 451):
            raise Refused(f"HTTP {r.status_code} on {url} {params}: {r.text[:200]!r}")
        if r.status_code >= 500:
            if a == 2:
                r.raise_for_status()
            time.sleep(1 + a)
            continue
        r.raise_for_status()
        try:
            js = r.json()
        except ValueError:
            raise Refused(f"non-JSON reply on {url} {params}: {r.text[:200]!r}")
        return js, r.headers
    raise RuntimeError("unreachable")


def generated_at(hd):
    """When the answer was made: the Date header minus Age (0 when absent)."""
    d = hd.get("Date")
    if not d:
        return None
    from email.utils import parsedate_to_datetime
    t = pd.Timestamp(parsedate_to_datetime(d)).tz_convert("UTC").tz_localize(None)
    try:
        age = float(hd.get("Age") or 0)
    except ValueError:
        age = 0.0
    return t - pd.Timedelta(seconds=age)


def fetch_coin(coin, first, last, answers, log):
    """Final candles for minutes first..last (inclusive). Returns a DataFrame like bot.market.spot_candles."""
    rows = {}
    s = first
    while s <= last:
        e = min(last, s + 299 * common.MIN)
        p = {"granularity": 60, "start": s.isoformat() + "Z", "end": e.isoformat() + "Z"}
        js, hd = get(f"{EXCHANGE}/products/{coin}-USD/candles", p)
        gen = generated_at(hd)
        a = dict(coin=coin, start=str(s), end=str(e), cache=hd.get("cf-cache-status"), age=hd.get("Age"),
                 date=hd.get("Date"), generated=str(gen), n=len(js) if isinstance(js, list) else None, dropped=False)
        if not isinstance(js, list):
            answers.append(a)
            raise Refused(f"candles answer is not a list for {coin} {p}: {str(js)[:200]}")
        if gen is None or gen < e + common.MIN + pd.Timedelta(seconds=180):
            a["dropped"] = True
            log.append(f"DROPPED {coin} {s}..{e}: generated {gen} (cache {a['cache']}, Age {a['age']})")
        else:
            for r in js:
                t = pd.Timestamp(int(r[0]), unit="s")
                if s <= t <= e:
                    rows[t] = (float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5]))
        answers.append(a)
        s = e + common.MIN
    k = sorted(rows)
    df = pd.DataFrame([rows[i] for i in k], columns=["open", "high", "low", "close", "volume"], dtype=float)
    df.index = pd.DatetimeIndex(k)
    return df


# ------------------------------------------------------------------------------------------------ engine side
_G = {}


class NoMarket:
    """The engine never fetches here: its table is set from the final candles."""

    def spot_candles(self, *a, **k):
        raise RuntimeError("no network in the research computation")


def make_engine(tmp):
    from bot.spot.engine import Engine
    cfg = json.load(open(os.path.join(ROOT, "bot", "spot", "config.json")))
    return Engine(mode="paper", cfg=cfg, state_dir=tmp, market=NoMarket(), echo=False)


def init_worker(candles, coins, tmp):
    import warnings
    warnings.filterwarnings("ignore")
    _G["eng"] = make_engine(os.path.join(tmp, f"w{os.getpid()}"))
    _G["candles"] = candles
    _G["coins"] = coins


def table_at(t, btc_lag=0):
    """What the engine's update_spot holds at step t with final candles: minutes [t - WINDOW_MIN, t); with btc_lag > 0
    BTC's newest btc_lag minutes are missing (a late answer)."""
    from bot.spot.engine import WINDOW_MIN
    lo = t - pd.Timedelta(minutes=WINDOW_MIN)
    out = {}
    for c, df in _G["candles"].items():
        hi = t - pd.Timedelta(minutes=1 + (btc_lag if c == "BTC" else 0))
        out[c] = df.loc[lo:hi]
    return out


def compute_at(t, btc_lag=0, only=None):
    """The engine's levels and scores at decision minute t. Returns rows (dicts)."""
    from edge import wick
    eng, coins = _G["eng"], _G["coins"]
    eng.spot = table_at(t, btc_lag)
    idx, cf, vol = eng.arrays(t)
    pn = wick.panel(cf, vol, coins, idx, k=eng.k, lookback=eng.lookback, coin_codes=eng.codes, wbeta=eng.wbeta)
    lb = np.log(cf["BTC"])
    r1 = (lb[-2] - lb[-3]) * 1e4                # BTC log return over minute t-1 (close t-2 to close t-1), bp
    r2 = (lb[-2] - lb[-4]) * 1e4                # over the two minutes to t-1
    btc_fresh = bool(eng.fresh("BTC", t))
    rows = []
    for c in coins:
        if only is not None and c not in only:
            continue
        row = pn[c].iloc[-1]
        valid = btc_fresh and bool(eng.fresh(c, t)) and all(
            np.isfinite(row[f]) for f in ("level", "sig", "z_res60", "bid_depth_bp"))
        # the engine's scoring line in _allocate, verbatim
        pred = float(np.mean([m.predict(row[wick.FEATS].to_numpy(np.float64)[None, :])[0] for m in eng.models])) \
            if valid else np.nan
        rows.append(dict(ts=t, coin=c, level=float(row["level"]), sig=float(row["sig"]), score=pred, valid=valid,
                         beta=float(row["beta"]), btc_r1_bp=r1, btc_r2_bp=r2, btc_lag=btc_lag))
    return rows


def work(job):
    kind, t, only = job
    if kind == "main":
        return compute_at(t)
    return compute_at(t, btc_lag=kind, only=only)


# ------------------------------------------------------------------------------------------------ freshness
def utc_now():
    """The current time in UTC, as a naive Timestamp (the log's minutes are naive UTC)."""
    return pd.Timestamp(dt.datetime.now(dt.timezone.utc)).tz_convert("UTC").tz_localize(None)


def old_enough(now, newest, min_age_min):
    """The plan's rule: final candles are fetched at least min_age_min minutes after the newest live minute.
    now, newest: naive UTC. True when now - newest >= min_age_min minutes (exactly the margin passes)."""
    return pd.Timestamp(now) - pd.Timestamp(newest) >= pd.Timedelta(minutes=min_age_min)


# ------------------------------------------------------------------------------------------------ books, period
def live_set(evs, start, end):
    """The minutes the research is computed on: the union over books ({name: events}) of the brief's live minutes in
    the period, plus each book's decision minute just before the period when compare.py needs it."""
    live = pd.DatetimeIndex([])
    for name, ev in evs.items():
        lb = common.live_minutes_brief(ev, end, start)
        pm = common.prev_decision_minute(ev, end, start)
        print(f"book {name}: {len(lb)} live minutes in the period"
              + (f" {lb[0]} .. {lb[-1]}" if len(lb) else "") + (f"; previous decision minute {pm}" if pm else ""),
              flush=True)
        live = live.union(lb)
        if pm is not None:
            live = live.union(pd.DatetimeIndex([pm]))
    return live.sort_values()


def arms_in_period(evs, have, start, end):
    """{(minute, coin): set of books} for the `arm` events inside the period (coins with candles only)."""
    out = {}
    for name, ev in evs.items():
        p0 = common.period_start(ev, start)
        for e in ev:
            if e["kind"] == "arm" and e["coin"] in have and e["t"] <= end and e["t"].floor("min") >= p0:
                out.setdefault((e["t"].floor("min"), e["coin"]), set()).add(name)
    return out


def split_late(late, arm_book, names):
    """Late-BTC rows for several books: one row per book armed at that coin and minute, with a `book` column."""
    parts = [late[[n in arm_book.get((t, c), ()) for t, c in zip(late.ts, late.coin)]].assign(book=n) for n in names]
    out = pd.concat(parts, ignore_index=True)
    return out[["book", "ts", "coin", "btc_lag", "level", "score", "valid"]]


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="", help="comma list of coins (smoke); default: the 17 of bot/v2")
    ap.add_argument("--max-minutes", type=int, default=0, help="smoke: only the first N live minutes")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--books", default="paper_spot", help="comma list of paper book folders (repo-relative)")
    ap.add_argument("--start", default=None, help="first UTC minute (default: each book's first event)")
    ap.add_argument("--end", default=None, help=f"last UTC minute (default {common.END})")
    ap.add_argument("--min-age-min", type=float, default=60.0,
                    help="refuse to fetch unless the newest live minute is at least this many minutes before now (UTC)")
    a = ap.parse_args()
    t_start = time.time()
    os.makedirs(a.out, exist_ok=True)
    meta = json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))
    coins = [c for c in a.coins.split(",") if c] or list(meta["coins"])
    from bot.spot.engine import WINDOW_MIN

    books = [b for b in a.books.split(",") if b]
    start = pd.Timestamp(a.start) if a.start else None
    end = pd.Timestamp(a.end) if a.end else common.END
    evs = {os.path.basename(os.path.normpath(b)): common.load_events(os.path.join(ROOT, b, "events.jsonl"))
           for b in books}
    live = live_set(evs, start, end)
    if not len(live):
        print("no live minute in the period", flush=True)
        return
    if a.max_minutes:
        live = live[:a.max_minutes]
    now = utc_now()
    if not old_enough(now, live[-1], a.min_age_min):
        print(f"NOT FETCHING: newest live minute {live[-1]} UTC is less than {a.min_age_min:g} minutes before now "
              f"{now} UTC (candles may not be final); rerun later or lower --min-age-min explicitly", flush=True)
        sys.exit(2)
    first = live[0] - pd.Timedelta(minutes=WINDOW_MIN) - pd.Timedelta(minutes=5)
    last = live[-1]
    print(f"live minutes {len(live)} ({len(live) / 60:.2f} h), {live[0]} .. {live[-1]}; fetch {first} .. {last}",
          flush=True)

    answers, log, refused = [], [], None
    candles = {}
    for c in ["BTC"] + coins:
        if refused:
            break
        try:
            candles[c] = fetch_coin(c, first, last, answers, log)
        except Refused as err:
            refused = f"{c}: {err}"
            print("REFUSED:", refused, flush=True)
        except Exception as err:                    # network or HTTP error after the retries: report, go on
            log.append(f"ERROR {c}: {err!r}"[:300])
            print("ERROR", c, repr(err)[:300], flush=True)
        if c in candles:
            df = candles[c]
            newest = [x for x in answers if x["coin"] == c][-1]
            print(f"{c}: {len(df)} candles {df.index.min()} .. {df.index.max()}; newest window cache "
                  f"{newest['cache']} Age {newest['age']} generated {newest['generated']}", flush=True)
    pd.DataFrame(answers).to_csv(os.path.join(a.out, "fetch_answers.csv"), index=False)
    for line in log:
        print(line, flush=True)
    have = [c for c in coins if c in candles]
    run = dict(utc_finished=None, coins=coins, coins_fetched=["BTC"] + have if "BTC" in candles else have,
               refused=refused, dropped=[x for x in log if x.startswith("DROPPED")],
               errors=[x for x in log if x.startswith("ERROR")], answers=len(answers),
               books=books, period_start=str(start) if start is not None else "each book's first event",
               period_end=str(end), min_age_min=a.min_age_min, checked_at_utc=str(now), live_minutes=len(live), fetch_from=str(first), fetch_to=str(last),
               cache_counts=pd.Series([x["cache"] for x in answers]).value_counts(dropna=False).to_dict(),
               newest_window={c: {k: v for k, v in [x for x in answers if x["coin"] == c][-1].items()
                                  if k in ("cache", "age", "date", "generated", "end")}
                              for c in ["BTC"] + coins if any(x["coin"] == c for x in answers)})
    if "BTC" not in candles or not have:
        run["utc_finished"] = dt.datetime.now(dt.timezone.utc).isoformat()
        json.dump(run, open(os.path.join(a.out, "fetch_run.json"), "w"), indent=1, default=str)
        print("no data to compute with", flush=True)
        return
    missing = sorted(set(coins) - set(have))
    if missing:
        print("computing without", missing, "(their rows are absent)", flush=True)
    t_fetch = time.time() - t_start

    # minute-by-minute engine computation
    import multiprocessing as mp
    import tempfile
    tmp = tempfile.mkdtemp(prefix="reconcile_")
    jobs = [("main", t, None) for t in live]
    arm_book = arms_in_period(evs, have, start, end)
    arm_at = {}
    for t, c in arm_book:
        arm_at.setdefault(t, set()).add(c)
    if a.max_minutes:
        arm_at = {t: v for t, v in arm_at.items() if live[0] <= t <= live[-1]}
    for t, cs in sorted(arm_at.items()):
        jobs += [(1, t, cs), (2, t, cs)]
    nw = a.workers or max(1, (os.cpu_count() or 2))
    print(f"computing {len(jobs)} engine steps with {nw} workers", flush=True)
    t0 = time.time()
    rows = []
    ctx = mp.get_context("spawn")
    with ctx.Pool(nw, initializer=init_worker, initargs=({c: candles[c] for c in ["BTC"] + have}, have, tmp)) as pool:
        for i, r in enumerate(pool.imap(work, jobs, chunksize=8)):
            rows += r
            if i % 500 == 0:
                print(f"  {i}/{len(jobs)} {time.time() - t0:.0f} s", flush=True)
    df = pd.DataFrame(rows)
    main_df = df[df.btc_lag == 0].drop(columns="btc_lag").copy()
    # the final candle of minute t itself (for fills): open, high, low; NaN when the minute has no candle
    for k in ("open", "high", "low"):
        main_df[k] = [candles[c][k].get(t, np.nan) for t, c in zip(main_df.ts, main_df.coin)]
    main_df = main_df.sort_values(["ts", "coin"])
    main_df.to_csv(os.path.join(a.out, "research_minutes.csv.gz"), index=False, float_format="%.10g")
    late = df[df.btc_lag > 0][["ts", "coin", "btc_lag", "level", "score", "valid"]].sort_values(["ts", "coin", "btc_lag"])
    if len(books) > 1:
        late = split_late(late, arm_book, list(evs))
    late.to_csv(os.path.join(a.out, "late_btc_at_arms.csv"), index=False, float_format="%.10g")
    run.update(utc_finished=dt.datetime.now(dt.timezone.utc).isoformat(), fetch_s=round(t_fetch),
               compute_s=round(time.time() - t0), rows=len(main_df), late_rows=len(late),
               valid_share=float(main_df.valid.mean()), workers=nw,
               above_thr=int((main_df.score > float(meta["threshold"])).sum()))
    json.dump(run, open(os.path.join(a.out, "fetch_run.json"), "w"), indent=1, default=str)
    # compact echo to the log
    print(json.dumps({k: v for k, v in run.items() if k != "newest_window"}, default=str), flush=True)
    print(main_df.groupby("coin").agg(n=("score", "size"), valid=("valid", "mean"), score_med=("score", "median"),
                                      above=("score", lambda s: int((s > float(meta["threshold"])).sum()))), flush=True)


if __name__ == "__main__":
    main()
