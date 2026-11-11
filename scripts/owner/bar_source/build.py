"""Where the twelve candle-path coins should take their newest bar from: Part 1 of reports/owner/bar_source_prereg.md.
Runs on a GitHub runner (hunt2.yml): it fetches the venue's final candles. The comparison itself is compare.py.

  python scripts/owner/bar_source/build.py --start 2026-11-10T21:50 --end 2026-11-11T01:59 \
      --out reports/owner/bar_source_dev [--min-age-min 60] [--max-minutes N] [--workers N] [--record DIR]

--start and --end are UTC decision minutes, both included. The decision at minute t reads bars through t-1.

1. The forward collector's record (branch forward-data: streams tbar, candles, candle_fetch) is read out of git
   into a temporary folder on the runner (--record: an existing folder with forward/<stream>/<day>/*.parquet instead).
   Only minutes the period needs are kept: tbar through end-1, candles through end-1, candle answers made in
   minutes through end. Raw files are never written to --out.
2. The venue's final candles for BTC and the 17 coins, from end - 1 back over the engine's whole look-back before
   start (WINDOW_MIN + 5 minutes), are fetched with the reconciliation's own fetch_coin (scripts/owner/reconcile/
   fetch_and_compute.py): pacing, refusal policy (a refusal stops all fetching, no retry), the rule that drops an
   answer generated before its newest minute closed plus 180 s, and its freshness guard (old_enough).
3. For every decision minute t the reconciliation's own compute_at runs the bot's engine code (Engine.arrays,
   edge.wick.panel, the mean of the five bot/v2 models) on a table assembled per pass. Pass R is the reconciliation
   itself (its table_at, unchanged). In the other passes each coin's rows follow one of these rules:
     R  every row the final candle.
     A  rows before t-1 final; row t-1 the collector's first-seen candle (the first revision of that candle, seen in
        the collector's fetch during minute t). If that answer did not hold minute t-1 the coin has no row for t-1
        (the engine then carries the close forward). If the collector has no candle answer in minute t at all, the
        coin also has no row and the row is flagged inputs_ok = False.
     B  trades kept: every minute m from the start of the collector's record (its first tbar minute) to t-1 from the
        verified trades bar; a verified empty minute (n = 0) has no row. A minute with no verified trades bar (absent
        or not verified) takes the candle path's row: the first-seen candle if m = t-1, the final candle otherwise
        (counted). Minutes before the record began are final candles.
     C  trades then candles: row t-1 as in B; every older row final.
   Passes (the coin's rule inside each; a coin not named is R):
     A, B, C   the twelve (DOGE LINK BCH SUI XLM HBAR NEAR AAVE HYPE ENA PEPE ONDO) on that rule; BTC, ETH, SOL, XRP,
               LTC, ZEC as the third book has them (rule B: trades from the record's start, final candles before).
               Pass A is the third book itself.
     LA, LC    for LTC and ZEC, reported only: the twelve as the third book has them (rule A), BTC ETH SOL XRP rule B,
               LTC and ZEC both on rule A (LA) or rule C (LC). Their rule B is pass A (the third book).
   A coin's score depends on the other traded coins' rows (edge/wick.py: alts_mean_z60 and alts_below_2sd are the
   mean and the count below -2 of every other coin's z_res60), so every pass is a book that could exist and LTC and
   ZEC get passes of their own.
4. Writes to --out:
     minutes.parquet     one row per pass other than R, coin and decision minute: ts, coin, pass, way (the coin's
                         rule in that pass), score, level, sig, valid, src (where row t-1 came from), inputs_ok,
                         answer_old (row t-1 from a candle answer made before minute t-1 had closed, or of unknown
                         age: the stale guard would skip the coin), and the research (pass R) beside it: res_score,
                         res_level, res_sig, res_valid
     record_sources.csv  per coin: the collector's minutes from the record's start to end-1 by kind (verified with
                         trades, verified empty, not verified, absent) and the first-seen candle at each decision
                         minute (held, answer without the minute, no answer)
     fetch_answers.csv   one row per final-candle answer (as the reconciliation writes it)
     run.json            fetch facts (answers, refused, dropped, errors, cache counts), threshold, counts, timings
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")     # one thread per worker process (results do not depend on it)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "owner", "reconcile"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "forward"))

import numpy as np                    # noqa: E402
import pandas as pd                   # noqa: E402

import fetch_and_compute as fac       # noqa: E402  (the reconciliation: fetch, freshness, engine driver)
import input_checks as ic             # noqa: E402  (the collector's first-seen candle)
import read as fread                  # noqa: E402  (the collector's loaders, de-duplicated)

MIN = pd.Timedelta(minutes=1)
COLS = ["open", "high", "low", "close", "volume"]
TWELVE = ["DOGE", "LINK", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE", "ENA", "PEPE", "ONDO"]
REPORTED = ["LTC", "ZEC"]
BOOK_TRADES = ["BTC", "ETH", "SOL", "XRP"]
STREAMS = ("tbar", "candles", "candle_fetch")
DATA_REF = "refs/remotes/origin/forward-data"
NO_INPUT = ("no_answer", "fb_no_answer")          # row t-1's source does not exist in the record


def passes():
    """{pass: {coin: rule}}; a coin not named is on rule R (final candles)."""
    tb = {c: "B" for c in BOOK_TRADES + REPORTED}                  # as the third book has them
    out = {"R": {}}
    for w in "ABC":
        out[w] = {**tb, **{c: w for c in TWELVE}}
    out["LA"] = {**tb, **{c: "A" for c in TWELVE}, **{c: "A" for c in REPORTED}}
    out["LC"] = {**tb, **{c: "A" for c in TWELVE}, **{c: "C" for c in REPORTED}}
    return out


def canonical_pass(coin, way):
    """The pass whose rows give coin `coin` under way `way` (A, B, C) in a book that could exist."""
    if coin in TWELVE:
        return way
    if coin in REPORTED:
        return {"A": "LA", "B": "A", "C": "LC"}[way]
    raise ValueError(f"{coin} is not a coin of interest")


# ------------------------------------------------------------------------------------------------ the record
def git(*args, **kw):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, **kw).stdout


def fetch_record(dest, days):
    """Read the collector's files for `days` ({stream: [YYYY-MM-DD]}) out of the fetched forward-data ref into dest.
    Returns {stream/day: files}."""
    got = {}
    for s, ds in days.items():
        for d in ds:
            p = f"forward/{s}/{d}"
            names = [x for x in git("ls-tree", "--name-only", f"{DATA_REF}:{p}").split() if x.endswith(".parquet")] \
                if git("ls-tree", DATA_REF, p).strip() else []
            if not names:
                continue
            os.makedirs(os.path.join(dest, p), exist_ok=True)
            for n in names:
                blob = subprocess.run(["git", "show", f"{DATA_REF}:{p}/{n}"], cwd=ROOT, check=True,
                                      capture_output=True).stdout
                with open(os.path.join(dest, p, n), "wb") as fh:
                    fh.write(blob)
            got[f"{s}/{d}"] = len(names)
    return got


def record_days(start, end, tbar_days):
    """Days to read: tbar from the record's first day (rule B reads every trades bar since the record began),
    candles and candle answers from the day of start - 1 minute to the day of end."""
    near = [f"{d:%Y-%m-%d}" for d in pd.date_range((start - MIN).floor("D"), end.floor("D"), freq="D")]
    tb = sorted(d for d in tbar_days if d <= f"{end:%Y-%m-%d}")
    return {"tbar": tb, "candles": near, "candle_fetch": near}


def load_record(root, start, end):
    """The record limited to what the period needs. Returns (tbar, first, answers):
    tbar     {coin: DataFrame indexed by minute: open..volume, n, verified} for minutes through end - 1
    first    {coin: DataFrame indexed by candle minute: open..volume} first-seen candles of minutes start-1..end-1
    answers  {coin: DataFrame indexed by fetch minute: gen (answer made; NaT when a cache copy has no Age)} for
             fetch minutes start..end"""
    days = sorted(os.listdir(os.path.join(root, "forward", "tbar")))
    t0 = pd.Timestamp(days[0]) if days else start
    tb = fread.load("tbar", t0, end, root=root)                         # minute in [t0, end): through end - 1
    cd = fread.load("candles", start - MIN, end, root=root)              # candle minutes start-1 .. end-1
    cf = fread.load("candle_fetch", start, end + MIN, root=root)         # fetch minutes start .. end
    return split_record(tb, cd, cf, start, end)


def split_record(tb, cd, cf, start, end):
    tbar, first, answers = {}, {}, {}
    if len(tb):
        tb = tb[tb.minute < end].copy()
        tb["coin"] = tb.coin.astype(str)
        for c, g in tb.groupby("coin"):
            tbar[c] = g.set_index("minute")[COLS + ["n", "verified"]].sort_index()
    if len(cd):
        cd = cd[(cd.minute >= start - MIN) & (cd.minute < end)]
        fs = ic.first_seen(cd)
        for c in fs.index.get_level_values(0).unique():
            first[c] = fs.loc[c][COLS].sort_index()
    if len(cf):
        cf = cf[(cf.minute >= start) & (cf.minute <= end)].copy()
        cf["coin"] = cf.coin.astype(str)
        hit = cf.cache.astype("string").eq("HIT").fillna(False).to_numpy(bool)
        known = cf.age.notna().to_numpy(bool)
        gen = cf.seen - pd.to_timedelta(cf.age.where(known, 0.0).astype(float), unit="s")
        cf["gen"] = gen.where(~hit | known)                              # a cache copy of unknown age: NaT
        cf = cf.sort_values("seen").drop_duplicates(["coin", "minute"], keep="first")   # the first answer
        for c, g in cf.groupby("coin"):
            answers[c] = g.set_index("minute")[["gen"]].sort_index()
    return tbar, first, answers


# ------------------------------------------------------------------------------------------------ row assembly
def first_src(c, m, first, answers):
    """Rule A for minute m as the newest row (decision m + 1): 'first' (the collector's answer in minute m + 1 held
    the candle), 'first_absent' (it did not: no row) or 'no_answer' (no answer in minute m + 1: input missing)."""
    a = answers.get(c)
    if a is None or (m + MIN) not in a.index:
        return "no_answer"
    f = first.get(c)
    return "first" if f is not None and m in f.index else "first_absent"


def trades_kind(c, m, tbar):
    """'trades' (verified, with trades), 'empty' (verified, none) or 'fallback' (not verified, or no row)."""
    t = tbar.get(c)
    if t is None or m not in t.index or not bool(t.at[m, "verified"]):
        return "fallback"
    return "trades" if t.at[m, "n"] > 0 else "empty"


def trades_src(c, m, tbar, first, answers):
    """Rules B and C for minute m as the newest row: 'trades', 'empty' (no row) or 'fb_' + the first-seen source."""
    k = trades_kind(c, m, tbar)
    return k if k != "fallback" else "fb_" + first_src(c, m, first, answers)


def row_of(src, c, m, tbar, first):
    """The row a source gives (a one-row DataFrame) or None."""
    if src == "trades":
        return tbar[c].loc[[m], COLS]
    if src in ("first", "fb_first"):
        return first[c].loc[[m], COLS]
    return None


def newest_frames(c, decisions, tbar, first, answers):
    """For coin c and decision minutes `decisions`: {rule: (rows DataFrame indexed by t-1, src Series by t-1)}
    for rule 'A' (first-seen) and 'T' (trades with fall-back; rules B and C)."""
    ms = [t - MIN for t in decisions]
    out = {}
    for key in ("A", "T"):
        src = pd.Series([first_src(c, m, first, answers) if key == "A" else trades_src(c, m, tbar, first, answers)
                         for m in ms], index=pd.DatetimeIndex(ms), dtype=object)
        parts = []
        tm = src.index[src.eq("trades")]
        fm = src.index[src.isin(["first", "fb_first"])]
        if len(tm):
            parts.append(tbar[c].loc[tm, COLS])
        if len(fm):
            parts.append(first[c].loc[fm, COLS])
        df = pd.concat(parts).sort_index() if parts else pd.DataFrame(columns=COLS, dtype=float)
        out[key] = (df.astype(float), src)
    return out


def old_b_frame(c, final, rec_start, last, tbar):
    """Rule B's rows for every minute up to `last` (the older rows; row t-1 comes from newest_frames): final
    candles before rec_start; from rec_start the verified trades bar, no row for a verified empty minute, the final
    candle for a minute with no verified trades bar. Returns (DataFrame, counts by kind)."""
    before = final[final.index < rec_start]
    t = tbar.get(c)
    mins = pd.date_range(rec_start, last, freq="min")
    kinds = pd.Series([trades_kind(c, m, tbar) for m in mins], index=mins, dtype=object)
    tr = t.loc[kinds.index[kinds.eq("trades")], COLS] if t is not None and kinds.eq("trades").any() else None
    fb = final.loc[final.index.isin(kinds.index[kinds.eq("fallback")])]
    parts = [x for x in (before, tr, fb) if x is not None and len(x)]
    df = pd.concat(parts).sort_index() if parts else final.iloc[:0]
    counts = kinds.value_counts().to_dict()
    return df[COLS].astype(float), {k: int(counts.get(k, 0)) for k in ("trades", "empty", "fallback")}


def as_unit_of(df, ref):
    """Same index resolution as the final candles (so concatenated tables index alike)."""
    if not len(df):
        return df.set_axis(pd.DatetimeIndex([], dtype=ref.index.dtype))
    return df.set_axis(pd.DatetimeIndex(df.index).as_unit(ref.index.unit))


# ------------------------------------------------------------------------------------------------ engine side
_W = {}
_TABLE_AT = fac.table_at                  # the reconciliation's own table (pass R)


def init_worker(candles, coins, tmp, frames, ways):
    fac.init_worker(candles, coins, tmp)
    _W["frames"] = frames
    _W["ways"] = ways


def table_for(p, t):
    """The engine's table at decision minute t in pass p: for each coin, rows of [t - WINDOW_MIN, t - 2] from its
    rule's older rows and row t - 1 from its rule's newest row (no row when the rule gives none)."""
    from bot.spot.engine import WINDOW_MIN
    lo = t - pd.Timedelta(minutes=WINDOW_MIN)
    out = {}
    for c, fin in fac._G["candles"].items():
        way = _W["ways"][p].get(c, "R")
        if way == "R":
            out[c] = fin.loc[lo:t - MIN]
            continue
        fr = _W["frames"][c]
        old = fr["oldB"] if way == "B" else fin
        new = fr["newA"] if way == "A" else fr["newT"]
        a = old.loc[lo:t - 2 * MIN]
        if (t - MIN) in new.index:
            a = pd.concat([a, new.loc[[t - MIN]]])
        out[c] = a
    return out


def work(job):
    p, t = job
    if p == "R":
        fac.table_at = _TABLE_AT
    else:
        fac.table_at = lambda tt, btc_lag=0: table_for(p, tt)
    try:
        rows = fac.compute_at(t)
    finally:
        fac.table_at = _TABLE_AT
    for r in rows:
        r["pass"] = p
    return rows


def run_steps(jobs, candles, coins, frames, ways, workers, log_every=500):
    import multiprocessing as mp
    tmp = tempfile.mkdtemp(prefix="bar_source_")
    rows = []
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers, initializer=init_worker, initargs=(candles, coins, tmp, frames, ways)) as pool:
        for i, r in enumerate(pool.imap(work, jobs, chunksize=4)):
            rows += r
            if i % log_every == 0:
                print(f"  {i}/{len(jobs)} {time.time() - t0:.0f} s", flush=True)
    return pd.DataFrame(rows), time.time() - t0


def sources_table(decisions, coins, frames, ways, answers):
    """Per pass (other than R), coin and decision minute: way, src of row t-1, inputs_ok, answer_old."""
    out = []
    for p, wmap in ways.items():
        if p == "R":
            continue
        for c in coins:
            w = wmap.get(c, "R")
            if w == "R":
                src = pd.Series("final", index=[t - MIN for t in decisions])
            else:
                src = frames[c]["srcA"] if w == "A" else frames[c]["srcT"]
            a = answers.get(c)
            for t in decisions:
                s = src.get(t - MIN, "final")
                old = None
                if s in ("first", "fb_first"):
                    g = a.at[t, "gen"] if a is not None and t in a.index else pd.NaT
                    old = bool(pd.isna(g) or g < t)         # made before minute t-1 closed, or of unknown age
                out.append(dict(ts=t, coin=c, **{"pass": p}, way=w, src=s, inputs_ok=s not in NO_INPUT,
                                answer_old=old))
    return pd.DataFrame(out)


# ------------------------------------------------------------------------------------------------ main
def parse_minute(x):
    return pd.Timestamp(x).floor("min")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="first UTC decision minute, e.g. 2026-11-11T02:00")
    ap.add_argument("--end", required=True, help="last UTC decision minute (included), e.g. 2026-11-14T01:59")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-age-min", type=float, default=60.0,
                    help="refuse to fetch unless the end minute is at least this many minutes before now (UTC)")
    ap.add_argument("--max-minutes", type=int, default=0, help="smoke: only the first N decision minutes")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--record", default=None, help="a folder holding forward/<stream>/<day>/ (default: read the "
                                                   "forward-data branch out of git into a temporary folder)")
    a = ap.parse_args(argv)
    t_start = time.time()
    start, end = parse_minute(a.start), parse_minute(a.end)
    decisions = pd.date_range(start, end, freq="min")
    if a.max_minutes:
        decisions = decisions[:a.max_minutes]
        end = decisions[-1]
    now = fac.utc_now()
    if not fac.old_enough(now, end, a.min_age_min):
        print(f"NOT FETCHING: end minute {end} UTC is less than {a.min_age_min:g} minutes before now {now} UTC "
              f"(candles may not be final); rerun later or lower --min-age-min explicitly", flush=True)
        sys.exit(2)
    os.makedirs(a.out, exist_ok=True)
    meta = json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))
    coins = list(meta["coins"])
    from bot.spot.engine import WINDOW_MIN

    # 1. the collector's record
    if a.record:
        root, got = a.record, "local folder"
    else:
        root = tempfile.mkdtemp(prefix="fwd_")
        git("fetch", "--depth", "1", "origin", f"+refs/heads/forward-data:{DATA_REF}")     # the branch tip only
        tdays = [x for x in git("ls-tree", "--name-only", f"{DATA_REF}:forward/tbar").split()]
        got = fetch_record(root, record_days(start, end, tdays))
    print("record files:", got, flush=True)
    tbar, first, answers = load_record(root, start, end)
    if not tbar:
        raise SystemExit("no trades bars in the record")
    rec_start = min(t.index.min() for t in tbar.values())
    print(f"record: trades bars from {rec_start}; coins {sorted(tbar)}", flush=True)
    if start - MIN < rec_start:
        raise SystemExit(f"the first decision's newest minute {start - MIN} is before the record began {rec_start}")

    # 2. the venue's final candles (the reconciliation's fetch)
    first_min = start - pd.Timedelta(minutes=WINDOW_MIN) - pd.Timedelta(minutes=5)
    last_min = end - MIN
    print(f"decision minutes {len(decisions)} ({len(decisions) / 60:.2f} h) {decisions[0]} .. {decisions[-1]}; "
          f"fetch {first_min} .. {last_min}", flush=True)
    answers_f, log, refused, candles = [], [], None, {}
    for c in ["BTC"] + coins:
        if refused:
            break
        try:
            candles[c] = fac.fetch_coin(c, first_min, last_min, answers_f, log)
        except fac.Refused as err:
            refused = f"{c}: {err}"
            print("REFUSED:", refused, flush=True)
        except Exception as err:                    # network or HTTP error after the retries: report, go on
            log.append(f"ERROR {c}: {err!r}"[:300])
            print("ERROR", c, repr(err)[:300], flush=True)
        if c in candles:
            print(f"{c}: {len(candles[c])} candles {candles[c].index.min()} .. {candles[c].index.max()}", flush=True)
    pd.DataFrame(answers_f).to_csv(os.path.join(a.out, "fetch_answers.csv"), index=False)
    for line in log:
        print(line, flush=True)
    have = [c for c in coins if c in candles]
    run = dict(utc_finished=None, period_start=str(start), period_end=str(end), decision_minutes=len(decisions),
               record_start=str(rec_start), record_files=got, threshold=float(meta["threshold"]),
               coins=coins, coins_fetched=(["BTC"] if "BTC" in candles else []) + have, refused=refused,
               dropped=[x for x in log if x.startswith("DROPPED")], errors=[x for x in log if x.startswith("ERROR")],
               answers=len(answers_f), min_age_min=a.min_age_min, checked_at_utc=str(now),
               fetch_from=str(first_min), fetch_to=str(last_min),
               cache_counts=pd.Series([x["cache"] for x in answers_f]).value_counts(dropna=False).to_dict(),
               passes={p: w for p, w in passes().items()})
    complete = "BTC" in candles and len(have) == len(coins) and not refused
    if not complete:
        run["utc_finished"] = dt.datetime.now(dt.timezone.utc).isoformat()
        run["note"] = "incomplete fetch: no pass computed (every pass needs every coin)"
        json.dump(run, open(os.path.join(a.out, "run.json"), "w"), indent=1, default=str)
        print("incomplete fetch; nothing computed", flush=True)
        sys.exit(3)
    t_fetch = time.time() - t_start

    # 3. per-coin frames and the passes
    ways = passes()
    frames, src_rows = {}, []
    for c in ["BTC"] + coins:
        fin = candles[c]
        nf = newest_frames(c, decisions, tbar, first, answers)
        oldB, kinds = old_b_frame(c, fin, rec_start, last_min, tbar)
        frames[c] = dict(oldB=as_unit_of(oldB, fin), newA=as_unit_of(nf["A"][0], fin), srcA=nf["A"][1],
                         newT=as_unit_of(nf["T"][0], fin), srcT=nf["T"][1])
        fa = nf["A"][1].value_counts().to_dict()
        src_rows.append(dict(coin=c, record_minutes=sum(kinds.values()), tbar_verified_trades=kinds["trades"],
                             tbar_verified_empty=kinds["empty"], tbar_fallback=kinds["fallback"],
                             first_held=int(fa.get("first", 0)), first_answer_without_minute=int(fa.get("first_absent", 0)),
                             first_no_answer=int(fa.get("no_answer", 0))))
    pd.DataFrame(src_rows).to_csv(os.path.join(a.out, "record_sources.csv"), index=False)
    jobs = [(p, t) for t in decisions for p in ways]
    nw = a.workers or max(1, (os.cpu_count() or 2))
    print(f"computing {len(jobs)} engine steps ({len(ways)} passes) with {nw} workers", flush=True)
    df, compute_s = run_steps(jobs, {c: candles[c] for c in ["BTC"] + coins}, coins, frames, ways, nw)

    # 4. the table
    keep = ["ts", "coin", "pass", "score", "level", "sig", "valid"]
    df = df[keep]
    res = df[df["pass"] == "R"].drop(columns="pass").rename(
        columns={"score": "res_score", "level": "res_level", "sig": "res_sig", "valid": "res_valid"})
    src = sources_table(decisions, coins, frames, ways, answers)
    out = df[df["pass"] != "R"].merge(src, on=["ts", "coin", "pass"], how="left", validate="one_to_one")
    out = out.merge(res, on=["ts", "coin"], how="left", validate="many_to_one")
    out = out[["ts", "coin", "pass", "way", "score", "level", "sig", "valid", "src", "inputs_ok", "answer_old",
               "res_score", "res_level", "res_sig", "res_valid"]].sort_values(["pass", "ts", "coin"])
    out["answer_old"] = out.answer_old.astype("boolean")
    out.reset_index(drop=True).to_parquet(os.path.join(a.out, "minutes.parquet"), index=False, compression="zstd")
    fb = src[src.way.isin(["B", "C"])].groupby(["pass", "way"]).src.value_counts().rename("n").reset_index()
    run.update(utc_finished=dt.datetime.now(dt.timezone.utc).isoformat(), fetch_s=round(t_fetch),
               compute_s=round(compute_s), steps=len(jobs), workers=nw,
               steps_per_s=round(len(jobs) / max(compute_s, 1e-9), 2), rows=len(out),
               inputs_missing=int((~out.inputs_ok).sum()),
               newest_src_counts={f"{r['pass']}/{r.way}/{r.src}": int(r.n) for _, r in fb.iterrows()},
               record_sources=src_rows)
    json.dump(run, open(os.path.join(a.out, "run.json"), "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in run.items() if k not in ("record_sources", "passes")}, default=str), flush=True)
    print(pd.DataFrame(src_rows).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
