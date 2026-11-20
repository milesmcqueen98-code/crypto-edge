"""Does an emulated book stand for a paper book? Checks build.py's emulation against the book's own logged scores.
Offline and read-only: it counts and prints, it changes no rule and no decision. The question is fixed in
reports/owner/bar_source_prereg.md, section "After Part 3: the cause".

  python scripts/owner/bar_source/book_check.py --dir DIR --log BOOK/events.jsonl --book NAME --pass PASS \
      [--start T0 --end T1] [--research-gap 2.0] [--within 0.5] [--out OUTDIR]

--dir: a folder with build.py's minutes.parquet and run.json. --pass: C18 (the fourth book; the fifth reads the same
rows) or A (the main book's inputs on the twelve; ETH SOL XRP ZEC are on its rule in that pass; LTC is not emulated
for the main book by any pass and is left out and counted). --book: a label for file names and headings. --start and
--end: UTC decision minutes, both included (default: the table's first and last ts). --out: default --dir.

Bids: the log's `arm` events (the book's new bids) with ts floored to the minute inside the period, on one of the 17
traded coins (the twelve and ETH SOL XRP LTC ZEC, as in build.py; the lists are copied here, as compare.py does, so
that this file needs no engine import, and the test checks them against build.py). `pred` is the book's score, one
decimal. Per bid the table's row of that pass, coin and minute gives emu (score), emu_valid, inputs_ok, src,
answer_old, res (res_score) and res_valid. A bid whose minute is not in the table is counted apart ("no row") and is
in no share.

Counts, for all coins, the twelve and the five (the five: ETH SOL XRP LTC ZEC; ETH SOL XRP ZEC with --pass A):
  1. n = bids with a row; emu valid; within = emu valid and |pred - emu| <= within. A bid without a valid emulated
     score counts in n and not as within (compare.py's convention). Share (i) = within / n.
  2. Among bids with res_valid: far = |pred - res| > research-gap (strictly), near = the rest. For far and near the
     number within of emu; for far also the number whose emu is within of the research instead (|emu - res| <=
     within, not within of the book) and the number with neither. Share (ii) = far-and-within / far.
  3. Wrong side: bids with res_valid and res <= threshold (bot/v2/model_meta.json, as compare.py reads it; the
     engine arms on score > threshold). Of those with a valid emu: emu <= threshold ("the emulated score is on the
     research's side") and emu > threshold ("on the book's side"); those without a valid emu are counted apart.
  4. For the far bids: counts by src and by answer_old.
Comparisons use the rounded pred: |pred - emu| <= within + 1e-9 and |pred - res| > research-gap + 1e-9.

Readings, compared exactly on counts. (i): "stands for the book" when 10 * within >= 9 * n, else "does not stand for
the book". (ii): "confirmed" when 5 * a >= 4 * b, "not explained" when 2 * a < b, else "explained in part"
(a = far-and-within, b = far). Nothing else is decided.

Outputs in --out: book_check_NAME_PASS.md, book_check_NAME_PASS.json (every count), book_check_NAME_PASS_bids.csv
(one row per bid with a row, in the traded coins and not left out: ts, coin, group, pred, emu, emu_valid, res,
res_valid, inputs_ok, src, answer_old, within, far, emu_side, res_side; sides are relative to the threshold,
below = score <= threshold). Exit code 0 on a completed run whatever the shares are; non-zero with a message if the
table, the pass, the log or the threshold is missing or the period holds no bid.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

TWELVE = ["DOGE", "LINK", "BCH", "SUI", "XLM", "HBAR", "NEAR", "AAVE", "HYPE", "ENA", "PEPE", "ONDO"]
FIVE = ["ETH", "SOL", "XRP", "LTC", "ZEC"]
LEFT_OUT = {"A": ["LTC"], "C18": []}
EPS = 1e-9
GROUPS = ("all", "twelve", "five")


def fail(msg):
    raise SystemExit("book_check: " + msg)


def read_bids(path):
    """The log's arm events as dicts with ts floored to the minute."""
    out = []
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("kind") == "arm":
                out.append(dict(ts=pd.Timestamp(e["ts"]).floor("min"), coin=e["coin"], pred=float(e["pred"])))
    return out


def pct(a, b):
    return "n/a" if b == 0 else f"{100.0 * a / b:.2f}%"


def of(a, b):
    return f"{a} of {b} ({pct(a, b)})"


def reading_i(within, n):
    if n == 0:
        return "no bids"
    return "stands for the book" if 10 * within >= 9 * n else "does not stand for the book"


def reading_ii(a, b):
    if b == 0:
        return "no far bids"
    if 5 * a >= 4 * b:
        return "confirmed"
    if 2 * a < b:
        return "not explained"
    return "explained in part"


def _valid(x, flag):
    return bool(flag) and bool(np.isfinite(x))


def bid_rows(bids, T, pass_, start, end, within, gap, thr):
    """Classify the bids. Returns (rows, apart): rows for bids with a row, apart = counts of the others."""
    idx = T[T["pass"] == pass_].drop_duplicates(["ts", "coin"]).set_index(["ts", "coin"])
    traded = set(TWELVE) | set(FIVE)
    left_out = set(LEFT_OUT[pass_])
    rows = []
    apart = dict(no_row=0, left_out=0, outside_period=0, not_traded=0)
    for b in bids:
        if b["coin"] not in traded:
            apart["not_traded"] += 1
            continue
        if not (start <= b["ts"] <= end):
            apart["outside_period"] += 1
            continue
        if b["coin"] in left_out:
            apart["left_out"] += 1
            continue
        k = (b["ts"], b["coin"])
        if k not in idx.index:
            apart["no_row"] += 1
            continue
        r = idx.loc[k]
        emu = float(r["score"])
        res = float(r["res_score"])
        ev, rv = _valid(emu, r["valid"]), _valid(res, r["res_valid"])
        pred = b["pred"]
        w = ev and abs(pred - emu) <= within + EPS
        far = (abs(pred - res) > gap + EPS) if rv else None
        rows.append(dict(
            ts=b["ts"], coin=b["coin"], group="twelve" if b["coin"] in TWELVE else "five", pred=pred,
            emu=emu if ev else np.nan, emu_valid=ev, res=res if rv else np.nan, res_valid=rv,
            inputs_ok=bool(r["inputs_ok"]), src=str(r["src"]),
            answer_old="NA" if pd.isna(r["answer_old"]) else str(bool(r["answer_old"])),
            within=bool(w), far=far,
            emu_side=("above" if emu > thr else "below") if ev else "",
            res_side=("above" if res > thr else "below") if rv else ""))
    return rows, apart


def counts_for(rows, within, gap):
    """All counts for one group of bid rows (a list of dicts from bid_rows)."""
    n = len(rows)
    ev = [r for r in rows if r["emu_valid"]]
    w = sum(1 for r in rows if r["within"])
    rv = [r for r in rows if r["res_valid"]]
    far = [r for r in rv if r["far"]]
    near = [r for r in rv if not r["far"]]

    def res_close(r):
        return r["emu_valid"] and abs(r["emu"] - r["res"]) <= within + EPS
    far_w = sum(1 for r in far if r["within"])
    far_res = sum(1 for r in far if res_close(r) and not r["within"])
    ws = [r for r in rv if r["res_side"] == "below"]
    ws_ev = [r for r in ws if r["emu_valid"]]
    by_src, by_old = {}, {}
    for r in far:
        by_src[r["src"]] = by_src.get(r["src"], 0) + 1
        by_old[r["answer_old"]] = by_old.get(r["answer_old"], 0) + 1
    return dict(
        n=n, emu_valid=len(ev), within=w, share_i=[w, n],
        res_valid=len(rv), far=len(far), near=len(near),
        far_within=far_w, far_res_within_not_book=far_res, far_neither=len(far) - far_w - far_res,
        near_within=sum(1 for r in near if r["within"]), near_not_within=sum(1 for r in near if not r["within"]),
        share_ii=[far_w, len(far)],
        wrong_side_n=len(ws), wrong_side_emu_valid=len(ws_ev),
        wrong_side_emu_research_side=sum(1 for r in ws_ev if r["emu_side"] == "below"),
        wrong_side_emu_book_side=sum(1 for r in ws_ev if r["emu_side"] == "above"),
        wrong_side_no_valid_emu=len(ws) - len(ws_ev),
        far_by_src=dict(sorted(by_src.items())), far_by_answer_old=dict(sorted(by_old.items())),
        reading_i=reading_i(w, n), reading_ii=reading_ii(far_w, len(far)))


def compute(bids, T, pass_, start, end, within=0.5, gap=2.0, thr=0.0):
    rows, apart = bid_rows(bids, T, pass_, start, end, within, gap, thr)
    sel = {"all": rows, "twelve": [r for r in rows if r["group"] == "twelve"],
           "five": [r for r in rows if r["group"] == "five"]}
    return rows, apart, {g: counts_for(sel[g], within, gap) for g in GROUPS}


def md_text(book, pass_, start, end, within, gap, thr, apart, C):
    L = [f"# Book check: {book} book against pass {pass_}", "",
         f"Period {start} to {end} UTC (both minutes included). Within = |book score - emulated score| <= {within}; "
         f"far = |book score - research score| > {gap}. Threshold {thr:.6f}.",
         f"Bids set apart, in no share: no row in the table {apart['no_row']}; coin left out for this pass "
         f"{apart['left_out']}; outside the period {apart['outside_period']}; not a traded coin "
         f"{apart['not_traded']}.", ""]
    for g in GROUPS:
        c = C[g]
        nm = {"all": "All coins", "twelve": "The twelve", "five": "The five"}[g]
        L += [f"## {nm}", "",
              "| measure | count |", "|---|---|",
              f"| (i) bids with a row (n) | {c['n']} |",
              f"| emulated score valid | {of(c['emu_valid'], c['n'])} |",
              f"| within of the book's score | {of(c['within'], c['n'])} |",
              f"| bids with a valid research score | {c['res_valid']} |",
              f"| far from the research | {c['far']} |",
              f"| far, emulated within of the book (ii) | {of(c['far_within'], c['far'])} |",
              f"| far, emulated within of the research instead | {c['far_res_within_not_book']} |",
              f"| far, neither | {c['far_neither']} |",
              f"| near the research, emulated within of the book | {of(c['near_within'], c['near'])} |",
              f"| research score at or below the threshold | {c['wrong_side_n']} |",
              f"| of those, emulated score valid | {c['wrong_side_emu_valid']} |",
              f"| of those, emulated score on the research's side (at or below) | "
              f"{c['wrong_side_emu_research_side']} |",
              f"| of those, emulated score on the book's side (above) | {c['wrong_side_emu_book_side']} |",
              f"| of those, no valid emulated score | {c['wrong_side_no_valid_emu']} |", ""]
        L += [f"Far bids by src: {c['far_by_src'] or 'none'}. By answer_old: {c['far_by_answer_old'] or 'none'}.", ""]
        L += [f"Reading (i): {of(c['within'], c['n'])} within, so the emulation {c['reading_i']}.",
              f"Reading (ii): {of(c['far_within'], c['far'])}, {c['reading_ii']}.", ""]
    return "\n".join(L)


def run(a):
    tpath, rpath = os.path.join(a.dir, "minutes.parquet"), os.path.join(a.dir, "run.json")
    if not os.path.isfile(tpath):
        fail(f"no table: {tpath}")
    if not os.path.isfile(rpath):
        fail(f"no run.json: {rpath}")
    if not os.path.isfile(a.log):
        fail(f"no log: {a.log}")
    T = pd.read_parquet(tpath)
    if a.pass_ not in set(T["pass"]):
        fail(f"pass {a.pass_} is not in the table (passes: {sorted(set(T['pass']))})")
    meta_path = os.path.join(ROOT, "bot", "v2", "model_meta.json")
    if not os.path.isfile(meta_path):
        fail(f"no threshold file: {meta_path}")
    thr = float(json.load(open(meta_path))["threshold"])
    run_thr = json.load(open(rpath)).get("threshold")
    if run_thr is not None and abs(thr - float(run_thr)) > 0:
        fail(f"threshold differs from the build's: {thr} vs {run_thr}")
    P = T[T["pass"] == a.pass_]
    start = pd.Timestamp(a.start) if a.start else P.ts.min()
    end = pd.Timestamp(a.end) if a.end else P.ts.max()
    bids = read_bids(a.log)
    traded = set(TWELVE) | set(FIVE)
    in_period = [b for b in bids if b["coin"] in traded and start <= b["ts"] <= end
                 and b["coin"] not in LEFT_OUT[a.pass_]]
    if not in_period:
        fail(f"the period {start} to {end} holds no bid of the traded coins in {a.log}")
    rows, apart, C = compute(bids, T, a.pass_, start, end, a.within, a.research_gap, thr)
    out = a.out or a.dir
    os.makedirs(out, exist_ok=True)
    stem = os.path.join(out, f"book_check_{a.book}_{a.pass_}")
    md = md_text(a.book, a.pass_, start, end, a.within, a.research_gap, thr, apart, C)
    open(stem + ".md", "w").write(md + "\n")
    json.dump(dict(book=a.book, pass_=a.pass_, period_start=str(start), period_end=str(end), within=a.within,
                   research_gap=a.research_gap, threshold=thr, set_apart=apart, groups=C),
              open(stem + ".json", "w"), indent=1)
    cols = ["ts", "coin", "group", "pred", "emu", "emu_valid", "res", "res_valid", "inputs_ok", "src", "answer_old",
            "within", "far", "emu_side", "res_side"]
    pd.DataFrame(rows, columns=cols).to_csv(stem + "_bids.csv", index=False)
    print(md)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--book", required=True)
    ap.add_argument("--pass", dest="pass_", required=True, choices=sorted(LEFT_OUT))
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--research-gap", type=float, default=2.0)
    ap.add_argument("--within", type=float, default=0.5)
    ap.add_argument("--out", default=None)
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
