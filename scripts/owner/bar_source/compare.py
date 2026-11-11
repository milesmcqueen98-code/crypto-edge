"""The plan's Part 1 measures and its single-coin clause (reports/owner/bar_source_prereg.md) from build.py's table.
Offline, no network.

  python scripts/owner/bar_source/compare.py --dir reports/owner/bar_source_dev [--out DIR] \
      [--state paper_spot_tb/state.json] [--log paper_spot_tb/events.jsonl]

Inputs: --dir/minutes.parquet and --dir/run.json (build.py), bot/v2/model_meta.json (threshold), --state (only its
"specs": each coin's tick, as the engine's spec(c).tick returned it). --log is read only when given.

Rows: for coin c and way w the rows of build.canonical_pass(c, w) (the twelve: pass w; LTC and ZEC: LA, A (the
third book) and LC; way C18, all 17 traded coins: pass C18, every coin on way C, the fourth paper book), limited to
rows whose own inputs exist (inputs_ok). The research is pass R in the same rows.

Days: each 24-hour block of the period counted from its first decision minute (block 1 = start .. start + 24 h - 1
min, ...), not UTC days. For the registered window (Nov 11 02:00 to Nov 14 01:59 UTC) these are three full days.

Measures, per coin and way, per day and over the whole period, for the twelve together and, on C18, for the five
listed traded coins together (ETH SOL XRP LTC ZEC; pooled counts):
  1. Arming disagreement (primary). Armed = valid and score > threshold (the engine's test). Among the minutes where
     the way or the research is armed (den), the share where exactly one is (num). Split: way only, research only.
  2. Score error: median and 90th percentile (numpy linear interpolation) of |score - research score| over the
     minutes where both are valid.
  3. Level error: over the minutes where both are valid, each level is floored to the coin's tick (the engine's
     floor_to, as _arm_plan prices a bid); a difference within one tick (the reconciliation's same_px, 1e-9 relative
     slack) is 0 bp, otherwise err = 1e4 x (way price / research price - 1). The share with |err| > 5 bp.
  4. Score-miss share: among the minutes where both are valid, the share with |score - research score| strictly
     greater than 1.0 point (exactly 1.0 is not a miss), with the counts.
The single-coin clause (deviation log of the plan, Nov 11), for each of the twelve: "stays on candles" is true when
its score-miss share under C is strictly higher than under A over the whole period and strictly higher on at least
two of the day blocks, compared exactly on counts (c_miss x a_n > a_miss x c_n); a period or day with a zero
denominator on either side does not count as higher. It is reported as "not applied" (no value) unless the
emulation check on B passes, which needs --log.
Checks against the third book's own log (--log): its `arm` events (its new bids; `pred` is the score it logged,
rounded to 0.1) inside the period, against pass A (the third book's emulation): way B on ETH, SOL, XRP, LTC, ZEC
(they are on trades there) and way A on the twelve. Within = |pred - emulated score| <= 0.5. A bid without a valid
emulated score counts in n and not as within (listed apart). The B check passes when within x 10 >= 9 x n (under
90% fails).

Also counted per row group (not used by any measure): newest_fallback, rows whose row t-1 is a fall-back (no
verified trades bar: the candle path's row); newest_old_answer, rows whose row t-1 came from a candle answer made
before minute t-1 had closed or of unknown age (the third book's stale guard would place no new bid then).

Outputs in --out (default --dir): per_coin.csv, counts.json, summary.md.
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "owner", "reconcile"))

import numpy as np                    # noqa: E402
import pandas as pd                   # noqa: E402

import common                         # noqa: E402  (reconciliation: load_events)


def _reconcile_compare():
    """The reconciliation's compare.py (floor_to, same_px), loaded by path: this file has the same name."""
    spec = importlib.util.spec_from_file_location(
        "reconcile_compare", os.path.join(ROOT, "scripts", "owner", "reconcile", "compare.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rc = _reconcile_compare()

TWELVE = ["DOGE", "LINK", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE", "ENA", "PEPE", "ONDO"]
REPORTED = ["LTC", "ZEC"]
WAYS = ("A", "B", "C", "C18")
CHECK_B = ["ETH", "SOL", "XRP", "LTC", "ZEC"]
LISTED = ["ETH", "SOL", "XRP"]                  # on trades in every pass but C18 (their way C18 only is reported)
MISS = 1.0
DAY = pd.Timedelta(hours=24)
TOL = 0.5


def canonical_pass(coin, way):
    """Same as build.canonical_pass (kept here so compare.py needs no engine import)."""
    if way == "C18":
        return "C18"
    if coin in TWELVE:
        return way
    if coin in REPORTED:
        return {"A": "LA", "B": "A", "C": "LC"}[way]
    raise ValueError(coin)


def day_block(ts, start):
    """1-based 24-hour block of the period counted from its start."""
    return ((pd.DatetimeIndex(ts) - pd.Timestamp(start)) // DAY).astype(int) + 1


def arming(g, thr):
    """Counts of the arming disagreement on rows g (score, valid, res_score, res_valid)."""
    aw = g.valid.to_numpy(bool) & (g.score.to_numpy(float) > thr)
    ar = g.res_valid.to_numpy(bool) & (g.res_score.to_numpy(float) > thr)
    return dict(den=int((aw | ar).sum()), num=int((aw ^ ar).sum()), way_only=int((aw & ~ar).sum()),
                res_only=int((ar & ~aw).sum()), way_armed=int(aw.sum()), res_armed=int(ar.sum()), minutes=len(g))


def level_err_bp(level, res_level, tick):
    if not (np.isfinite(level) and np.isfinite(res_level)) or not np.isfinite(tick):
        return np.nan
    px, pr = rc.floor_to(level, tick), rc.floor_to(res_level, tick)
    return 0.0 if rc.same_px(px, pr, tick) else 1e4 * (px / pr - 1)


def errors(g, ticks):
    both = g.valid.to_numpy(bool) & g.res_valid.to_numpy(bool)
    b = g[both]
    d = (b.score - b.res_score).abs().to_numpy(float)
    lv = np.array([level_err_bp(x, y, ticks.get(c, np.nan)) for x, y, c in zip(b.level, b.res_level, b.coin)])
    lv = lv[np.isfinite(lv)]
    return dict(score_n=int(len(d)), score_med=float(np.median(d)) if len(d) else None,
                score_p90=float(np.percentile(d, 90)) if len(d) else None,
                level_n=int(len(lv)), level_gt5=int((np.abs(lv) > 5).sum()), miss=int((d > MISS).sum()))


def share(n, d):
    return n / d if d else None


def rows_for(T, coins, way):
    parts = [T[(T.coin == c) & (T["pass"] == canonical_pass(c, way))] for c in coins]
    g = pd.concat(parts) if parts else T.iloc[:0]
    return g[g.inputs_ok.astype(bool)]


def strictly_higher(b, a):
    """b's share > a's share, on counts ({"num", "den"}); None when a denominator is 0 (then not higher)."""
    if not a["den"] or not b["den"]:
        return None
    return b["num"] * a["den"] > a["num"] * b["den"]


def groups():
    """(group name, coins, ways) for the measures."""
    out = [(c, [c], WAYS) for c in TWELVE + REPORTED] + [(c, [c], ("C18",)) for c in LISTED]
    return out + [("twelve", TWELVE, WAYS), ("listed5", CHECK_B, ("C18",))]


def compute(T, thr, ticks, start):
    T = T.copy()
    T["day"] = day_block(T.ts, start)
    days = sorted(T.day.unique().tolist())
    per, counts = [], {}
    for group, coins, ways in groups():
        for w in ways:
            g = rows_for(T, coins, w)
            for d in ["all"] + days:
                gd = g if d == "all" else g[g.day == d]
                r = dict(coin=group, way=w, day=d, **arming(gd, thr), **errors(gd, ticks),
                         newest_fallback=int(gd.src.astype(str).str.startswith("fb_").sum()) if "src" in gd else 0,
                         newest_old_answer=int(gd.answer_old.fillna(False).astype(bool).sum())
                         if "answer_old" in gd else 0)
                r["share"] = share(r["num"], r["den"])
                r["level_share_gt5"] = share(r["level_gt5"], r["level_n"])
                r["miss_share"] = share(r["miss"], r["score_n"])
                per.append(r)
    P = pd.DataFrame(per)
    for r in per:
        counts.setdefault(r["coin"], {}).setdefault(r["way"], {})[str(r["day"])] = \
            {k: r[k] for k in ("minutes", "den", "num", "way_only", "res_only", "way_armed", "res_armed",
                               "score_n", "miss", "level_n", "level_gt5", "newest_fallback", "newest_old_answer")}
    days_n = {int(d): int((T[T["pass"] == "A"].drop_duplicates("ts").day == d).sum()) for d in days}
    return P, days_n, counts


def stays_on_candles(P, check_b):
    """The single-coin clause for each of the twelve. check_b: the B emulation check's result (dict with
    at_least_90pct) or None. Returns {"applied": bool, "why": str, "coins": {coin: {...}}}."""
    if check_b is None:
        status = (False, "not applied: the emulation check on B was not run (no --log)")
    elif check_b.get("at_least_90pct") is not True:
        status = (False, "not applied: the emulation check on B did not pass (under 90%, or no bids)")
    else:
        status = (True, "applied: the emulation check on B passed")
    out = {}
    days = sorted(d for d in P.day.unique() if d != "all")
    for c in TWELVE:
        def cnt(w, d):
            r = P[(P.coin == c) & (P.way == w) & (P.day == d)].iloc[0]
            return dict(num=int(r.miss), den=int(r.score_n))
        per = strictly_higher(cnt("C", "all"), cnt("A", "all"))
        by_day = {int(d): strictly_higher(cnt("C", d), cnt("A", d)) for d in days}
        higher_days = sum(1 for v in by_day.values() if v is True)
        value = bool(per is True and higher_days >= 2)
        out[c] = dict(value=value if status[0] else None, period_higher=per, days_higher=higher_days, by_day=by_day,
                      C={"all": cnt("C", "all")}, A={"all": cnt("A", "all")})
    return dict(applied=status[0], why=status[1], coins=out)


def log_check(events, T, coins, start, end, pass_="A"):
    """The book's arm events for `coins` with minute in [start, end] against pass `pass_` of the table."""
    idx = T[T["pass"] == pass_].set_index(["ts", "coin"])
    n = within = missing = 0
    rows = []
    for e in events:
        if e.get("kind") != "arm" or e.get("coin") not in coins:
            continue
        t = pd.Timestamp(e["ts"]).floor("min")
        if not (start <= t <= end):
            continue
        n += 1
        k = (t, e["coin"])
        sc = float(idx.at[k, "score"]) if k in idx.index and bool(idx.at[k, "valid"]) else np.nan
        if not np.isfinite(sc):
            missing += 1
            ok = False
        else:
            ok = abs(float(e["pred"]) - sc) <= TOL
        within += ok
        rows.append(dict(ts=t, coin=e["coin"], pred=e["pred"], emulated=sc, within=ok))
    return dict(n=n, within=within, no_valid_emulation=missing, share=share(within, n),
                at_least_90pct=(within * 10 >= 9 * n) if n else None), pd.DataFrame(rows)


def fmt(x, p=3):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else (f"{x:.{p}f}" if isinstance(x, float) else str(x))


def summary_md(P, days_n, clause, checks, run, thr):
    L = [f"# Newest-bar source, Part 1: {run.get('period_start')} to {run.get('period_end')} UTC", "",
         f"Threshold {thr:.6f}. Days are 24-hour blocks counted from the period's start "
         f"(decision minutes per block: {days_n}). Rows: each coin's own inputs exist (inputs_ok).",
         "Share = arming disagreement (num / den); way only and research only split num. Score error: |way - research|,"
         " both valid. Miss: share of minutes (both valid) with |score - research| > 1.0. Level: share of minutes"
         " (both valid) more than 5 bp from the research price (tick-floored, within one tick = 0).", ""]
    head = ["| coin | way | day | den | num | way only | research only | share | score med | score p90 | miss | level > 5 bp |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def line(r):
        return (f"| {r.coin} | {r.way} | {r.day} | {r.den} | {r.num} | {r.way_only} | {r.res_only} | {fmt(r.share)} | "
                f"{fmt(r.score_med, 2)} | {fmt(r.score_p90, 2)} | {fmt(r.miss_share)} ({r.miss}/{r.score_n}) | "
                f"{fmt(r.level_share_gt5)} ({r.level_gt5}/{r.level_n}) |")
    for title, sel in (("The twelve together", P.coin == "twelve"),
                       ("C18 (all 18 coins on way C, the fourth book): the five listed traded coins together",
                        P.coin == "listed5"),
                       ("Per coin, whole period", ~P.coin.isin(["twelve", "listed5"]) & (P.day == "all"))):
        L += [f"## {title}", ""] + head + [line(r) for _, r in P[sel].iterrows()] + [""]
    L += ["## Single-coin clause: stays on candles (score-miss share under C strictly higher than under A, over the "
          "period and on at least two day blocks; exact on counts)", "", clause["why"], ""]
    for c, v in clause["coins"].items():
        L.append(f"- {c}: {'not applied' if v['value'] is None else v['value']} (period higher: {v['period_higher']}; "
                 f"days higher: {v['days_higher']} of {len(v['by_day'])}; by day {v['by_day']}; "
                 f"C {v['C']['all']['num']}/{v['C']['all']['den']}, A {v['A']['all']['num']}/{v['A']['all']['den']})")
    L.append("")
    if checks:
        L += ["## Checks against the third book's log", ""]
        for k, v in checks.items():
            L.append(f"- {k}: {v['within']} of {v['n']} within {TOL} points (share {fmt(v['share'])}); "
                     f"{v['no_valid_emulation']} without a valid emulated score; at least 90%: {v['at_least_90pct']}")
        L.append("")
    else:
        L += ["Checks against the third book's log: not run (no --log).", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="build.py's output folder")
    ap.add_argument("--out", default=None)
    ap.add_argument("--state", default=os.path.join(ROOT, "paper_spot_tb", "state.json"),
                    help="a book state.json; only its specs (ticks) are read")
    ap.add_argument("--log", default=None, help="the third book's events.jsonl (the two checks); omitted: not run")
    a = ap.parse_args(argv)
    out = a.out or a.dir
    os.makedirs(out, exist_ok=True)
    T = pd.read_parquet(os.path.join(a.dir, "minutes.parquet"))
    run = json.load(open(os.path.join(a.dir, "run.json")))
    thr = float(json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))["threshold"])
    if abs(thr - float(run["threshold"])) > 0:
        raise SystemExit(f"threshold differs from the build's: {thr} vs {run['threshold']}")
    ticks = {c: float(v["tick"]) for c, v in json.load(open(a.state))["specs"].items()}
    start, end = pd.Timestamp(run["period_start"]), pd.Timestamp(run["period_end"])
    P, days_n, counts = compute(T, thr, ticks, start)
    checks = {}
    if a.log:
        ev = common.load_events(a.log)
        for name, coins in (("B on ETH SOL XRP LTC ZEC", CHECK_B), ("A on the twelve", TWELVE)):
            res, rows = log_check(ev, T, coins, start, end)
            checks[name] = res
            rows.to_csv(os.path.join(out, "check_" + name.split()[0] + ".csv"), index=False)
    clause = stays_on_candles(P, checks.get("B on ETH SOL XRP LTC ZEC"))
    P.to_csv(os.path.join(out, "per_coin.csv"), index=False, float_format="%.6g")
    json.dump(dict(period_start=str(start), period_end=str(end), threshold=thr, day_blocks=days_n,
                   stays_on_candles=clause, checks=checks, counts=counts), open(os.path.join(out, "counts.json"), "w"),
              indent=1, default=str)
    md = summary_md(P, days_n, clause, checks, run, thr)
    open(os.path.join(out, "summary.md"), "w").write(md + "\n")
    print(md)


if __name__ == "__main__":
    main()
