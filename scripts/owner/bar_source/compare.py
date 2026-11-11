"""The plan's Part 1 measures and decision helpers (reports/owner/bar_source_prereg.md) from build.py's table.
Offline, no network.

  python scripts/owner/bar_source/compare.py --dir reports/owner/bar_source_dev [--out DIR] \
      [--state paper_spot_tb/state.json] [--log paper_spot_tb/events.jsonl]

Inputs: --dir/minutes.parquet and --dir/run.json (build.py), bot/v2/model_meta.json (threshold), --state (only its
"specs": each coin's tick, as the engine's spec(c).tick returned it). --log is read only when given.

Rows: for coin c and way w the rows of build.canonical_pass(c, w) (the twelve: pass w; LTC and ZEC: LA, A (the
third book) and LC), limited to rows whose own inputs exist (inputs_ok). The research is pass R in the same rows.

Days: each 24-hour block of the period counted from its first decision minute (block 1 = start .. start + 24 h - 1
min, ...), not UTC days. For the registered window (Nov 11 02:00 to Nov 14 01:59 UTC) these are three full days.

Measures, per coin and way, per day and over the whole period, and for the twelve together (pooled counts):
  1. Arming disagreement (primary). Armed = valid and score > threshold (the engine's test). Among the minutes where
     the way or the research is armed (den), the share where exactly one is (num). Split: way only, research only.
  2. Score error: median and 90th percentile (numpy linear interpolation) of |score - research score| over the
     minutes where both are valid.
  3. Level error: over the minutes where both are valid, each level is floored to the coin's tick (the engine's
     floor_to, as _arm_plan prices a bid); a difference within one tick (the reconciliation's same_px, 1e-9 relative
     slack) is 0 bp, otherwise err = 1e4 x (way price / research price - 1). The share with |err| > 5 bp.
Decision helpers, exactly on counts (cross-multiplication; a day with a zero denominator makes a helper undefined,
reported as such, and then it is not true):
  - per coin, "worse on trades on each day": on every day, B's disagreement share is strictly higher than A's,
    b_num x a_den > a_num x b_den;
  - the twelve together, "C a fifth better than both": on every day, 5 x c_num x a_den <= 4 x a_num x c_den and the
    same against B (C's share at most four fifths of each; exactly four fifths counts).
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
WAYS = ("A", "B", "C")
CHECK_B = ["ETH", "SOL", "XRP", "LTC", "ZEC"]
DAY = pd.Timedelta(hours=24)
TOL = 0.5


def canonical_pass(coin, way):
    """Same as build.canonical_pass (kept here so compare.py needs no engine import)."""
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
                level_n=int(len(lv)), level_gt5=int((np.abs(lv) > 5).sum()))


def share(n, d):
    return n / d if d else None


def rows_for(T, coins, way):
    parts = [T[(T.coin == c) & (T["pass"] == canonical_pass(c, way))] for c in coins]
    g = pd.concat(parts) if parts else T.iloc[:0]
    return g[g.inputs_ok.astype(bool)]


def strictly_higher(b, a):
    """b's share > a's share, on counts; None when a denominator is 0."""
    if not a["den"] or not b["den"]:
        return None
    return b["num"] * a["den"] > a["num"] * b["den"]


def at_most_four_fifths(c, x):
    """c's share <= 4/5 of x's share, on counts; None when a denominator is 0."""
    if not c["den"] or not x["den"]:
        return None
    return 5 * c["num"] * x["den"] <= 4 * x["num"] * c["den"]


def every_day(vals):
    """(true on every day, undefined days). An undefined day makes it not true."""
    und = [d for d, v in vals.items() if v is None]
    return (bool(vals) and not und and all(vals.values())), und


def compute(T, thr, ticks, start):
    T = T.copy()
    T["day"] = day_block(T.ts, start)
    days = sorted(T.day.unique().tolist())
    per, counts = [], {"per_coin": {}, "twelve": {}}
    for group, coins in [(c, [c]) for c in TWELVE + REPORTED] + [("twelve", TWELVE)]:
        for w in WAYS:
            g = rows_for(T, coins, w)
            for d in ["all"] + days:
                gd = g if d == "all" else g[g.day == d]
                r = dict(coin=group, way=w, day=d, **arming(gd, thr), **errors(gd, ticks),
                         newest_fallback=int(gd.src.astype(str).str.startswith("fb_").sum()) if "src" in gd else 0,
                         newest_old_answer=int(gd.answer_old.fillna(False).astype(bool).sum())
                         if "answer_old" in gd else 0)
                r["share"] = share(r["num"], r["den"])
                r["level_share_gt5"] = share(r["level_gt5"], r["level_n"])
                per.append(r)
    P = pd.DataFrame(per)

    def cnt(coin, w, d):
        r = P[(P.coin == coin) & (P.way == w) & (P.day == d)].iloc[0]
        return dict(num=int(r.num), den=int(r.den))

    helpers = {"days": {int(d): int((T[T["pass"] == "A"].drop_duplicates("ts").day == d).sum()) for d in days},
               "worse_on_trades_each_day": {}, "c_fifth_better_than_both": None}
    for c in TWELVE + REPORTED:
        vals = {int(d): strictly_higher(cnt(c, "B", d), cnt(c, "A", d)) for d in days}
        ok, und = every_day(vals)
        helpers["worse_on_trades_each_day"][c] = dict(value=ok, by_day=vals, undefined_days=und)
    vals = {}
    for d in days:
        ca, cb, cc = cnt("twelve", "A", d), cnt("twelve", "B", d), cnt("twelve", "C", d)
        x, y = at_most_four_fifths(cc, ca), at_most_four_fifths(cc, cb)
        vals[int(d)] = None if x is None or y is None else (x and y)
    ok, und = every_day(vals)
    helpers["c_fifth_better_than_both"] = dict(value=ok, by_day=vals, undefined_days=und)
    for r in per:
        key = "twelve" if r["coin"] == "twelve" else "per_coin"
        counts[key].setdefault(r["coin"], {}).setdefault(r["way"], {})[str(r["day"])] = \
            {k: r[k] for k in ("minutes", "den", "num", "way_only", "res_only", "way_armed", "res_armed",
                               "score_n", "level_n", "level_gt5", "newest_fallback", "newest_old_answer")}
    counts["twelve"] = counts["twelve"].get("twelve", {})
    return P, helpers, counts


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


def summary_md(P, helpers, checks, run, thr):
    L = [f"# Newest-bar source, Part 1: {run.get('period_start')} to {run.get('period_end')} UTC", "",
         f"Threshold {thr:.6f}. Days are 24-hour blocks counted from the period's start "
         f"(decision minutes per block: {helpers['days']}). Rows: each coin's own inputs exist (inputs_ok).",
         "Share = arming disagreement (num / den); way only and research only split num. Score error: |way - research|,"
         " both valid. Level: share of minutes (both valid) more than 5 bp from the research price (tick-floored,"
         " within one tick = 0).", ""]
    for title, sel in (("The twelve together", P.coin == "twelve"), ("Per coin, whole period", (P.coin != "twelve") & (P.day == "all"))):
        L += [f"## {title}", "", "| coin | way | day | den | num | way only | research only | share | score med | score p90 | level > 5 bp |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for _, r in P[sel].iterrows():
            L.append(f"| {r.coin} | {r.way} | {r.day} | {r.den} | {r.num} | {r.way_only} | {r.res_only} | {fmt(r.share)} | "
                     f"{fmt(r.score_med, 2)} | {fmt(r.score_p90, 2)} | {fmt(r.level_share_gt5)} ({r.level_gt5}/{r.level_n}) |")
        L.append("")
    L += ["## Decision helpers (exact on counts)", ""]
    w = helpers["worse_on_trades_each_day"]
    L.append("Worse on trades on each day (B's share strictly higher than A's on every day): "
             + ", ".join(f"{c} {v['value']}" + (f" (undefined days {v['undefined_days']})" if v["undefined_days"] else "")
                         for c, v in w.items()))
    c = helpers["c_fifth_better_than_both"]
    L += ["", f"C a fifth better than both, the twelve together, on every day: {c['value']} (by day {c['by_day']}"
          + (f"; undefined days {c['undefined_days']}" if c["undefined_days"] else "") + ")", ""]
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
    P, helpers, counts = compute(T, thr, ticks, start)
    checks = {}
    if a.log:
        ev = common.load_events(a.log)
        for name, coins in (("B on ETH SOL XRP LTC ZEC", CHECK_B), ("A on the twelve", TWELVE)):
            res, rows = log_check(ev, T, coins, start, end)
            checks[name] = res
            rows.to_csv(os.path.join(out, "check_" + name.split()[0] + ".csv"), index=False)
    P.to_csv(os.path.join(out, "per_coin.csv"), index=False, float_format="%.6g")
    json.dump(dict(period_start=str(start), period_end=str(end), threshold=thr, day_blocks=helpers["days"],
                   helpers=helpers, checks=checks, counts=counts), open(os.path.join(out, "counts.json"), "w"),
              indent=1, default=str)
    md = summary_md(P, helpers, checks, run, thr)
    open(os.path.join(out, "summary.md"), "w").write(md + "\n")
    print(md)


if __name__ == "__main__":
    main()
