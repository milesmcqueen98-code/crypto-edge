"""The plan's addition "candles after the bids" (reports/owner/bar_source_prereg.md) read from build.py's table with the
pass C2x18. Offline, no network.

  python scripts/owner/bar_source/c2_rule.py --dir reports/owner/bar_source_c2 --part1 reports/owner/bar_source \
      [--state paper_spot_tb/state.json] [--out DIR]

Inputs: --dir/minutes.parquet and --dir/run.json (a build.py run that has the pass C2x18), bot/v2/model_meta.json
(threshold; stop if it differs from the run's), --state (only its "specs": each coin's tick, as compare.py reads
it), and Part 1's published --part1/counts.json and --part1/minutes.parquet. compare.py's functions are used as they
are (compute, arming, errors, share, day_block).

a. Reproduction. The plan: the earlier passes must reproduce Part 1's published counts exactly; if they do not,
   nothing is read until the difference is explained. compare.compute runs on the new table (it ignores the new
   pass) and its counts, day blocks, period and threshold are compared with Part 1's counts.json as integers and
   strings. Beside it, a row check (it decides nothing): for the passes Part 1 has, the new table is joined to Part
   1's minutes.parquet on (ts, coin, pass); rows compared, rows only in one table, and per column the number of
   rows that differ (floats compared as printed with %.10g, two NaN are equal) and the largest absolute difference.
   If the counts are not reproduced: the outputs say reproduced false with the differences (at most 50), verdict
   null, no measure of the new pass is printed or written, the line "NOT READ:" is printed and the exit code is 4.
b. Measures by pass, for the passes A, C, C18, C2x18 and B: the rows of that pass itself (column pass; not the
   canonical pass: pass A for all 17 coins is the third book as it runs), limited to rows with inputs_ok, for the 17
   traded coins together (group all17) and each coin alone, over the whole period (day "all") and each 24-hour
   block. Counts as compare.compute makes them.
c. The plan's rule on the 17 coins together over the whole period, exact on integer counts:
     1. arming: C2x18.num x A.den <= A.num x C2x18.den
     2. score:  C2x18.miss x A.score_n <= A.miss x C2x18.score_n
     3. level:  1000 x C2x18.level_gt5 x C18.level_n <= 1000 x C18.level_gt5 x C2x18.level_n
                + 5 x C2x18.level_n x C18.level_n      (no more than 0.5 points above C18's share)
   A clause with a zero denominator on either side is not met. The verdict is true when all three are met.
Outputs in --out (default --dir): c2_per_coin.csv, c2_counts.json, c2_summary.md (and the summary is printed).
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

import numpy as np                    # noqa: E402
import pandas as pd                   # noqa: E402


def _load(name, path):
    """A module loaded by path (compare.py has the same file name as the reconciliation's)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bc = _load("bar_source_compare_c2", os.path.join(HERE, "compare.py"))

NEW = "C2x18"
PASSES = ("A", "C", "C18", NEW, "B")           # the passes measured, in the order of the tables
OLD_PASSES = ("A", "B", "C", "LA", "LC", "C18")  # the passes Part 1 published
FLOAT_COLS = ["score", "level", "sig", "res_score", "res_level", "res_sig"]
EXACT_COLS = ["valid", "res_valid", "src", "inputs_ok", "answer_old", "way"]
COUNT_KEYS = ("minutes", "den", "num", "way_only", "res_only", "way_armed", "res_armed", "score_n", "miss",
              "level_n", "level_gt5", "newest_fallback", "newest_old_answer")
EXIT_NOT_REPRODUCED = 4


# ------------------------------------------------------------------------------------------------ a. reproduction
def diff_counts(new, old, path=""):
    """Every place where two nested dicts of integers differ: list of (path, new value, old value)."""
    out = []
    if isinstance(new, dict) and isinstance(old, dict):
        for k in sorted(set(new) | set(old), key=str):
            p = f"{path}/{k}"
            if k not in new:
                out.append((p, "missing", old[k] if not isinstance(old[k], dict) else "group"))
            elif k not in old:
                out.append((p, new[k] if not isinstance(new[k], dict) else "group", "missing"))
            else:
                out += diff_counts(new[k], old[k], p)
    elif new != old:
        out.append((path, new, old))
    return out


def reproduction(T, thr, ticks, start, end, part1):
    """Compare compare.compute's counts on table T with Part 1's counts.json (dict). Returns a dict with
    reproduced (bool) and differences (list of strings, at most 50, plus the total in n_differences)."""
    _, days_n, counts = bc.compute(T, thr, ticks, start)
    new = dict(counts=json.loads(json.dumps(counts, default=int)),
               day_blocks={str(k): int(v) for k, v in days_n.items()},
               period_start=str(start), period_end=str(end), threshold=float(thr))
    old = dict(counts=part1["counts"], day_blocks={str(k): int(v) for k, v in part1["day_blocks"].items()},
               period_start=str(pd.Timestamp(part1["period_start"])), period_end=str(pd.Timestamp(part1["period_end"])),
               threshold=float(part1["threshold"]))
    diffs = diff_counts(new, old)
    return dict(reproduced=not diffs, n_differences=len(diffs),
                differences=[f"{p}: new {a}, Part 1 {b}" for p, a, b in diffs[:50]])


def _fmt10(x):
    return "nan" if pd.isna(x) else "%.10g" % x


def row_check(T, T1, passes=OLD_PASSES):
    """The new table against Part 1's rows on (ts, coin, pass) for the passes Part 1 has."""
    key = ["ts", "coin", "pass"]
    a = T[T["pass"].isin(passes)]
    b = T1[T1["pass"].isin(passes)]
    cols = key + FLOAT_COLS + EXACT_COLS
    j = a[cols].merge(b[cols], on=key, how="outer", suffixes=("_new", "_old"), indicator=True)
    both = j[j["_merge"] == "both"]
    out = dict(rows_compared=int(len(both)), rows_only_new=int((j["_merge"] == "left_only").sum()),
               rows_only_part1=int((j["_merge"] == "right_only").sum()), columns={})
    differing = np.zeros(len(both), bool)
    for c in FLOAT_COLS:
        x, y = both[c + "_new"].to_numpy(float), both[c + "_old"].to_numpy(float)
        sx = np.array([_fmt10(v) for v in x], dtype=object)
        sy = np.array([_fmt10(v) for v in y], dtype=object)
        d = sx != sy
        fin = np.isfinite(x) & np.isfinite(y)
        out["columns"][c] = dict(differ=int(d.sum()), max_abs_diff=float(np.abs(x[fin] - y[fin]).max())
                                 if fin.any() else None)
        differing |= d
    for c in EXACT_COLS:
        x, y = both[c + "_new"], both[c + "_old"]
        d = ~((x.isna() & y.isna()) | (x.astype(object) == y.astype(object)).fillna(False).to_numpy(bool))
        d = np.asarray(d, bool)
        out["columns"][c] = dict(differ=int(d.sum()), max_abs_diff=None)
        differing |= d
    out["rows_differing"] = int(differing.sum())
    return out


# ------------------------------------------------------------------------------------------------ b. measures
def pass_rows(T, coins, p):
    """The rows of pass p itself (not the canonical pass) for `coins`, with inputs_ok."""
    g = T[(T["pass"] == p) & T.coin.isin(coins)]
    return g[g.inputs_ok.astype(bool)]


def measure(g, thr, ticks):
    r = dict(**bc.arming(g, thr), **bc.errors(g, ticks),
             newest_fallback=int(g.src.astype(str).str.startswith("fb_").sum()),
             newest_old_answer=int(g.answer_old.fillna(False).astype(bool).sum()))
    r["share"] = bc.share(r["num"], r["den"])
    r["level_share_gt5"] = bc.share(r["level_gt5"], r["level_n"])
    r["miss_share"] = bc.share(r["miss"], r["score_n"])
    return r


def measures(T, coins, thr, ticks, start, passes=PASSES):
    """Rows (list of dicts) for each group (all17 and each coin), pass and day ("all" and each 24-hour block)."""
    T = T.copy()
    T["day"] = bc.day_block(T.ts, start)
    days = sorted(T.day.unique().tolist())
    out = []
    for p in passes:
        for name, cs in [("all17", coins)] + [(c, [c]) for c in coins]:
            g = pass_rows(T, cs, p)
            for d in ["all"] + days:
                gd = g if d == "all" else g[g.day == d]
                out.append(dict(coin=name, **{"pass": p}, day=d, **measure(gd, thr, ticks)))
    return out


# ------------------------------------------------------------------------------------------------ c. the rule
def clauses(a, c18, c2):
    """The three clauses on integer counts. a, c18, c2: the all17 / whole-period counts of passes A, C18 and
    C2x18 (dicts with the keys of COUNT_KEYS). Returns ({name: clause dict}, verdict)."""
    def clause(met_fn, dens, **kw):
        met = all(d > 0 for d in dens) and met_fn()
        return dict(met=bool(met), **kw)

    k1 = clause(lambda: c2["num"] * a["den"] <= a["num"] * c2["den"], [c2["den"], a["den"]],
                rule="C2x18's arming disagreement is no higher than pass A's",
                counts=dict(c2_num=c2["num"], c2_den=c2["den"], a_num=a["num"], a_den=a["den"]),
                c2_share=bc.share(c2["num"], c2["den"]), bar_share=bc.share(a["num"], a["den"]))
    k2 = clause(lambda: c2["miss"] * a["score_n"] <= a["miss"] * c2["score_n"], [c2["score_n"], a["score_n"]],
                rule="C2x18's share of scores more than 1.0 point off is no higher than pass A's",
                counts=dict(c2_miss=c2["miss"], c2_score_n=c2["score_n"], a_miss=a["miss"], a_score_n=a["score_n"]),
                c2_share=bc.share(c2["miss"], c2["score_n"]), bar_share=bc.share(a["miss"], a["score_n"]))
    k3 = clause(lambda: 1000 * c2["level_gt5"] * c18["level_n"]
                <= 1000 * c18["level_gt5"] * c2["level_n"] + 5 * c2["level_n"] * c18["level_n"],
                [c2["level_n"], c18["level_n"]],
                rule="C2x18's share of levels more than 5 bp off is no more than 0.5 points above C18's",
                counts=dict(c2_level_gt5=c2["level_gt5"], c2_level_n=c2["level_n"],
                            c18_level_gt5=c18["level_gt5"], c18_level_n=c18["level_n"]),
                c2_share=bc.share(c2["level_gt5"], c2["level_n"]), bar_share=bc.share(c18["level_gt5"], c18["level_n"]))
    named = {"1_arming": k1, "2_score": k2, "3_level": k3}
    return named, all(v["met"] for v in named.values())


# ------------------------------------------------------------------------------------------------ outputs
def fmt(x, p=4):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else (f"{x:.{p}f}" if isinstance(x, float) else str(x))


def _line(r, label):
    return (f"| {label} | {r['den']} | {r['num']} | {fmt(r['share'])} | {r['miss']}/{r['score_n']} = {fmt(r['miss_share'])} | "
            f"{r['level_gt5']}/{r['level_n']} = {fmt(r['level_share_gt5'])} | {fmt(r['score_med'], 2)} | "
            f"{fmt(r['score_p90'], 2)} |")


def summary_md(run, thr, repro, rc, rows, cl, verdict, second):
    L = [f"# Candles after the bids: {run.get('period_start')} to {run.get('period_end')} UTC", ""]
    L.append(f"Reproduction of Part 1's counts: {'yes, every count equal' if repro['reproduced'] else 'NO'}.")
    L.append(f"Row check beside it (decides nothing): {rc['rows_compared']} rows compared, {rc['rows_only_new']} only in "
             f"the new table, {rc['rows_only_part1']} only in Part 1's, {rc['rows_differing']} rows differ in at least "
             f"one column.")
    L += ["", f"Threshold {thr:.6f}. Days are 24-hour blocks from the period's start. Rows: each coin's own inputs "
          "exist. Share = arming disagreement num / den; miss = scores more than 1.0 point off, of the minutes where "
          "both are valid; level = levels more than 5 bp off, of the same minutes.", ""]
    head = ["| pass, day | den | num | arming share | score miss | level > 5 bp | score med | score p90 |",
            "|---|---|---|---|---|---|---|---|"]
    L += ["## The 17 traded coins together", ""] + head
    for r in rows:
        if r["coin"] == "all17":
            L.append(_line(r, f"{r['pass']}, {r['day']}"))
    L += ["", "## Per coin, whole period", ""]
    head2 = ["| coin, pass | den | num | arming share | score miss | level > 5 bp | score med | score p90 |",
             "|---|---|---|---|---|---|---|---|"]
    L += head2
    for r in rows:
        if r["coin"] != "all17" and r["day"] == "all" and r["pass"] in ("A", "C18", NEW):
            L.append(_line(r, f"{r['coin']}, {r['pass']}"))
    L += ["", "## The plan's rule (17 coins together, whole period, exact on counts)", ""]
    for k, v in cl.items():
        c = v["counts"]
        L.append(f"- Clause {k[0]}: {v['rule']}. Counts {c}. Shares {fmt(v['c2_share'])} against {fmt(v['bar_share'])}. "
                 f"Met: {'yes' if v['met'] else 'no'}.")
    L += ["", f"Under the plan's rule the candle requests move behind the bids: {'yes' if verdict else 'no'}", ""]
    if second:
        tot = {k: sum(v.get(k, 0) for v in second.values()) for k in ("trades", "empty", "fallback", "before_record")}
        L += ["## Where row t-2 came from (all coins, all decision minutes)", "",
              f"Verified trades bar {tot['trades']}, verified empty minute {tot['empty']}, no verified bar (final "
              f"candle) {tot['fallback']}, before the record began {tot['before_record']}.", ""]
    return "\n".join(L)


def not_read_md(run, repro):
    L = [f"# Candles after the bids: {run.get('period_start')} to {run.get('period_end')} UTC", "",
         "NOT READ: the earlier passes do not reproduce Part 1's published counts. Nothing is read until the "
         "difference is explained.", "", f"Differences: {repro['n_differences']} (first {len(repro['differences'])} listed).", ""]
    return "\n".join(L + [f"- {d}" for d in repro["differences"]] + [""])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="build.py's output folder with the pass C2x18")
    ap.add_argument("--part1", required=True, help="Part 1's published folder (counts.json, minutes.parquet)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--state", default=os.path.join(ROOT, "paper_spot_tb", "state.json"),
                    help="a book state.json; only its specs (ticks) are read")
    a = ap.parse_args(argv)
    out = a.out or a.dir
    os.makedirs(out, exist_ok=True)
    T = pd.read_parquet(os.path.join(a.dir, "minutes.parquet"))
    run = json.load(open(os.path.join(a.dir, "run.json")))
    thr = float(json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))["threshold"])
    if thr != float(run["threshold"]):
        raise SystemExit(f"threshold differs from the build's: {thr} vs {run['threshold']}")
    ticks = {c: float(v["tick"]) for c, v in json.load(open(a.state))["specs"].items()}
    start, end = pd.Timestamp(run["period_start"]), pd.Timestamp(run["period_end"])
    part1 = json.load(open(os.path.join(a.part1, "counts.json")))
    T1 = pd.read_parquet(os.path.join(a.part1, "minutes.parquet"))

    repro = reproduction(T, thr, ticks, start, end, part1)
    rc = row_check(T, T1)
    period = dict(start=str(start), end=str(end))
    if not repro["reproduced"]:
        json.dump(dict(period=period, threshold=thr, reproduced=False, differences=repro["differences"],
                       n_differences=repro["n_differences"], row_check=rc, verdict=None),
                  open(os.path.join(out, "c2_counts.json"), "w"), indent=1, default=str)
        md = not_read_md(run, repro)
        open(os.path.join(out, "c2_summary.md"), "w").write(md)
        print(md)
        print("NOT READ: the earlier passes do not reproduce Part 1's counts")
        sys.exit(EXIT_NOT_REPRODUCED)
    if NEW not in set(T["pass"]):
        raise SystemExit(f"the table has no pass {NEW}")

    coins = list(run["coins"])
    rows = measures(T, coins, thr, ticks, start)
    P = pd.DataFrame(rows)
    pick = lambda p: next(r for r in rows if r["coin"] == "all17" and r["pass"] == p and r["day"] == "all")  # noqa: E731
    cl, verdict = clauses(pick("A"), pick("C18"), pick(NEW))
    second = run.get("second_row_counts", {})
    counts = {}
    for r in rows:
        counts.setdefault(r["coin"], {}).setdefault(r["pass"], {})[str(r["day"])] = {k: r[k] for k in COUNT_KEYS}
    P.to_csv(os.path.join(out, "c2_per_coin.csv"), index=False, float_format="%.6g")
    days_n = {int(d): int((T[T["pass"] == "A"].drop_duplicates("ts").pipe(lambda x: bc.day_block(x.ts, start)) == d).sum())
              for d in sorted(set(bc.day_block(T.ts, start)))}
    json.dump(dict(period=period, threshold=thr, day_blocks=days_n,
                   reproduced=True, differences=[], row_check=rc, counts=counts, clauses=cl, verdict=verdict,
                   second_row_counts=second),
              open(os.path.join(out, "c2_counts.json"), "w"), indent=1, default=str)
    md = summary_md(run, thr, repro, rc, rows, cl, verdict, second)
    open(os.path.join(out, "c2_summary.md"), "w").write(md + "\n")
    print(md)


if __name__ == "__main__":
    main()
