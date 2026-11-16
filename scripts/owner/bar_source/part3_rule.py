"""Part 3 of reports/owner/bar_source_prereg.md ("Part 3: the build as a paper book"), as code. Semantics fixed by the
plan and the owner's brief; do not improve on them. Modelled on part2_rule.py: same kind of inputs, outputs and exact
integer arithmetic (every comparison below is made on whole numbers or exact fractions, never on rounded shares).

Inputs
  --dir     a folder written by scripts/owner/reconcile/two_books.py run with --main paper_spot_t18 --third
            paper_spot_r5 over the period. In that folder's tables the label "main" means the FOURTH paper book
            (paper_spot_t18) and the label "tb" means the FIFTH paper book (paper_spot_r5). Everything is on the minutes
            both books were live and on the 17 traded coins: the folder's group "all" (two_books.json groups["all"]),
            which is every coin of the research file; the script stops with an error unless that group is exactly the
            17 coins of "trades list" plus "candle path" (5 plus 12), and unless two_books.json's period equals
            --start and --end and its books are the ones named by --fourth and --fifth.
  --start, --end  the period (UTC minutes, both included).
  --fifth, --fourth, --main  the three book folders (events.jsonl); --main is the main book (paper_spot).
  --pairs   the folder of pair files (default reports/owner/step_pairs).
  --items-1-5 pass|fail  items 1 to 5 of the fifth book, read from the status report on a copy of its log cut at the
            period's end (as in Part 2); the script does not compute them.

Where each count comes from (all for the 17 coins, on the common minutes; "fifth" is label tb, "fourth" is label main)
  n   new bids of a book: the number of rows of item7_bids.csv with that label and a coin of groups["all"]
      (checked against side_by_side.csv, measure m3_bids, statistic bot_new_bids, group all).
  ns, w  bids with a research score and, among them, the bids on the wrong side (the research would not have placed them):
      item7_bids.csv, rows with res_score present: ns is their number, w those with res_other_side true (checked against
      side_by_side.csv, measure m2_score_error, statistics n and n_other_side, group all).
  nl, l  bids with a research level and, among them, those more than 5 bp from it: item7_bids.csv, rows with err_bp
      present: nl is their number, l those with abs(err_bp) > 5 (nl checked against side_by_side.csv, measure
      m1_level_error, statistic n, group all).
  r, m  the research's new bids (not blocked by cash or a stale input) and, among them, those with a bot bid within a
      minute: side_by_side.csv, measure m3_bids, statistics research_new_bids_ex_blocked and research_matched, group all.
  A mismatch between a count from item7_bids.csv and its side_by_side.csv check is an error and no verdict.

Measure 1, the step (deviation log of Nov 16 2026, 12:04 ET):
  (a) same-machine pairs: the files pair_*.json of --pairs (written by scripts/owner/step_pairs/run_pair.py), those with
      "counts" true and a utc_start inside [start, end] (end minute included). The measure is the median of the build's
      median data-step end minus release 3's, computed exactly from the medians as printed (data_end_median_text of the
      two runs) with Fractions; it must be at or below zero, with at least 8 such pairs (fewer: not met). A pair that
      does not count, or starts outside the period, is left out. The even-count median is the mean of the two middle
      values.
  (b) over the heartbeat timestamps inside the period at which both the fifth and the main book have a heartbeat (the
      data step is the first number of step_s.data), the median of the fifth book's values is no higher than the main
      book's, with at least 100 such timestamps and at least 100 fifth-book heartbeats (fewer: not met).
  Both must hold. Reported, deciding nothing: the fifth book's own median of heartbeat data steps against 10.3 s, and
  the fifth book's median against the fourth book's over the paired half hours.
Measure 2, decisions (exact): wrong side w5/ns5 <= w4/ns4 + 0.02 and w5/ns5 <= 0.05; matched m5/r5 >= m4/r4 - 0.03;
  level l5/nl5 < 0.05 (strictly). A zero denominator means that clause is not met.
Measure 3: the --items-1-5 argument.
Measure 4, from the fifth book's heartbeats in the period, computed by scripts/owner/paper_status.py (measure4 and
  startup_steps, imported here, so the status report and this rule give the same numbers): failed share
  pre_error / (pre_fetched + pre_error) at most 1%; in-step share (pre_missing + pre_ondemand, less the first step after
  each start) over 18 times the minutes run, at most 2%. Counters absent from every heartbeat means not met.
Verdict: "Part 3: pass" only if all four measures hold, else "Part 3: fail". The period condition: each of the fifth and
  fourth books has at least 300 new bids (n above). Under 300 in either: "PERIOD NOT COMPLETE" and no verdict, unless
  --read-as-is is passed (the plan allows the read after the third extension), which is then stated in the output.

Command line:
  python scripts/owner/bar_source/part3_rule.py --dir DIR --start 2026-..T..:.. --end 2026-..T..:.. \\
      --fifth paper_spot_r5 --fourth paper_spot_t18 --main paper_spot --items-1-5 pass|fail [--pairs DIR] [--out DIR] \
      [--read-as-is]
  reads DIR/two_books.json, DIR/item7_bids.csv, DIR/side_by_side.csv and the three events.jsonl; writes part3_rule.json and
  part3_rule.md into --out (default DIR) and prints the markdown.
"""
import argparse
import json
import os
import sys
from datetime import timedelta
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
OWNER = os.path.dirname(HERE)
sys.path.insert(0, OWNER)

import pandas as pd             # noqa: E402

import paper_status as ps       # noqa: E402

MIN_BIDS = 300
MIN_HEARTBEATS = 100
MIN_PAIRS = ps.MIN_PAIRS
PAIRS_DEFAULT = ps.PAIRS_DIR
LIMIT_BP = 5.0
FOURTH, FIFTH = "main", "tb"        # the labels in the folder: main = fourth book, tb = fifth book
GROUP = "all"
STEP_BAR = Fraction("10.3")
WRONG_SIDE_TOLERANCE = Fraction(2, 100)
WRONG_SIDE_CAP = Fraction(5, 100)
MATCHED_TOLERANCE = Fraction(3, 100)
LEVEL_CAP = Fraction(5, 100)
N_COINS = 17


def guard(meta, fourth_folder, fifth_folder, start, end):
    books = meta.get("books", {})
    if books.get(FOURTH) != fourth_folder or books.get(FIFTH) != fifth_folder:
        raise ValueError("this folder is not a fourth-book / fifth-book reconciliation: books must be main = "
                         f"{fourth_folder} and tb = {fifth_folder}, found {books}")
    p = meta.get("period", {})
    if pd.Timestamp(p.get("start")) != pd.Timestamp(start) or pd.Timestamp(p.get("end")) != pd.Timestamp(end):
        raise ValueError(f"the folder's period {p} differs from --start {start} --end {end}")
    g = meta.get("groups", {})
    allc = set(g.get(GROUP, []))
    if len(allc) != N_COINS or allc != set(g.get("trades list", [])) | set(g.get("candle path", [])) \
            or set(g.get("trades list", [])) & set(g.get("candle path", [])):
        raise ValueError(f"the folder's group 'all' is not the {N_COINS} traded coins (trades list plus candle path): {g}")
    return sorted(allc)


def to_int(x, what):
    f = float(x)
    if f != int(f):
        raise ValueError(f"{what} is not a whole number: {x}")
    return int(f)


def side_value(S, measure, statistic, book):
    r = S[(S["measure"] == measure) & (S["statistic"] == statistic) & (S["group"] == GROUP) & (S["book"] == book)]
    if len(r) != 1:
        raise ValueError(f"side_by_side.csv: expected one row for {measure} / {statistic} / {GROUP} / {book}, "
                         f"found {len(r)}")
    return to_int(r["value"].iloc[0], f"side_by_side.csv {measure} / {statistic} / {book}")


def book_counts(B, S, label, coins):
    """n, (w, ns), (l, nl), (m, r) of one book; the counts from item7_bids.csv are checked against side_by_side.csv."""
    A = B[(B["book"] == label) & (B["coin"].isin(coins))]
    sc = A[A["res_score"].notna()]
    lv = A[A["err_bp"].notna()]
    other = sc["res_other_side"].astype(str).str.lower() == "true"
    n, ns, w = int(len(A)), int(len(sc)), int(other.sum())
    nl, lcount = int(len(lv)), int((lv["err_bp"].abs() > LIMIT_BP).sum())
    for what, mine, theirs in (("new bids", n, side_value(S, "m3_bids", "bot_new_bids", label)),
                               ("scored bids", ns, side_value(S, "m2_score_error", "n", label)),
                               ("wrong-side bids", w, side_value(S, "m2_score_error", "n_other_side", label)),
                               ("bids with a level", nl, side_value(S, "m1_level_error", "n", label))):
        if mine != theirs:
            raise ValueError(f"inconsistent folder: {what} of the {label} book from item7_bids.csv ({mine}) differ from "
                             f"side_by_side.csv ({theirs})")
    m = side_value(S, "m3_bids", "research_matched", label)
    r = side_value(S, "m3_bids", "research_new_bids_ex_blocked", label)
    return dict(n=n, ns=ns, w=w, nl=nl, l=lcount, m=m, r=r)


def share(k, n):
    return float(Fraction(k) / Fraction(n)) if n else None


# ---------------------------------------------------------------- the heartbeats
def log_rows(path, start, end):
    """(data-quality rows of the heartbeats inside [start, end + 1 minute), the first stepped minutes of the starts) of
    one book's log, with the log cut at the period's end first: the same figures the status report gives on a cut copy."""
    folder = os.path.normpath(path)
    book = ps.load_book(os.path.dirname(os.path.abspath(folder)), os.path.basename(folder))
    if book["status"] == "missing":
        raise ValueError(f"no events.jsonl in {path}")
    stop = pd.Timestamp(end).to_pydatetime().replace(tzinfo=ps.timezone.utc) + timedelta(minutes=1)
    t0 = pd.Timestamp(start).to_pydatetime().replace(tzinfo=ps.timezone.utc)
    ev = [e for e in book["events"] if e["_t"] is not None and e["_t"] < stop]
    times = [e["_t"] for e in ev]
    first, last = (min(times), max(times)) if times else (None, None)
    rt = ps.running_time(ev, first, last)
    dq = ps.data_quality(ev, rt)
    return [r for r in dq["rep"] if t0 <= r["t"] < stop], ps.startup_steps(ev)


# ---------------------------------------------------------------- the rule
def clause(met, **kw):
    return dict(met=bool(met), **kw)


def when(x):
    """A UTC datetime from a period bound (a string or Timestamp)."""
    return pd.Timestamp(x).to_pydatetime().replace(tzinfo=ps.timezone.utc)


def measure1(rows5, rows_main, rows_fourth, pairs, start, end, min_hb=MIN_HEARTBEATS, min_pairs=MIN_PAIRS):
    pm = ps.pairs_measure(pairs or [], when(start), when(end), None, min_pairs)
    mm = ps.measure1(rows5, rows_main)
    mf = ps.measure1(rows5, rows_fourth)
    enough_b = mm["pairs"] >= min_hb and mm["n"] >= min_hb
    a = clause(pm["met"], pairs=pm["n"], needed=min_pairs, enough=pm["enough"], median_s=_f(pm["median"]),
               median_exact=None if pm["median"] is None else str(pm["median"]),
               pair_files=[p["file"] for p in pm["used"]], rule="median of build minus release 3 at or below 0")
    b = clause(enough_b and mm["paired_fifth"] <= mm["paired_other"], paired_half_hours=mm["pairs"], fifth_heartbeats=mm["n"],
               needed=min_hb, fifth_median_s=_f(mm["paired_fifth"]), main_median_s=_f(mm["paired_other"]), enough=enough_b)
    reported = dict(fifth_own_median_s=_f(mm["median"]), fifth_heartbeats=mm["n"], bar_s=float(STEP_BAR),
                    at_or_below_bar=mm["median"] is not None and mm["median"] <= STEP_BAR, decides="nothing")
    info = dict(paired_half_hours=mf["pairs"], fifth_median_s=_f(mf["paired_fifth"]), fourth_median_s=_f(mf["paired_other"]))
    return dict(a=a, b=b, reported=reported, fourth_for_information=info, met=a["met"] and b["met"])


def _f(x):
    return None if x is None else float(x)


def measure2(c5, c4):
    n5, n4 = c5["ns"], c4["ns"]
    ws = bool(n5 and n4) and Fraction(c5["w"], n5) <= Fraction(c4["w"], n4) + WRONG_SIDE_TOLERANCE
    wc = bool(n5) and Fraction(c5["w"], n5) <= WRONG_SIDE_CAP
    mt = bool(c5["r"] and c4["r"]) and Fraction(c5["m"], c5["r"]) >= Fraction(c4["m"], c4["r"]) - MATCHED_TOLERANCE
    lv = bool(c5["nl"]) and Fraction(c5["l"], c5["nl"]) < LEVEL_CAP
    out = dict(
        wrong_side_vs_fourth=clause(ws, fifth=f"{c5['w']}/{n5}", fourth=f"{c4['w']}/{n4}", fifth_share=share(c5["w"], n5),
                                    fourth_share=share(c4["w"], n4), rule="fifth share <= fourth share + 2.0 points"),
        wrong_side_cap=clause(wc, fifth=f"{c5['w']}/{n5}", fifth_share=share(c5["w"], n5), rule="fifth share <= 5%"),
        matched=clause(mt, fifth=f"{c5['m']}/{c5['r']}", fourth=f"{c4['m']}/{c4['r']}", fifth_share=share(c5["m"], c5["r"]),
                       fourth_share=share(c4["m"], c4["r"]), rule="fifth share >= fourth share - 3.0 points"),
        level=clause(lv, fifth=f"{c5['l']}/{c5['nl']}", fifth_share=share(c5["l"], c5["nl"]),
                     rule="fifth share < 5% (strictly)"))
    out["met"] = ws and wc and mt and lv
    return out


def measure4(rows5, starts5):
    m = ps.measure4(rows5, starts5)
    c = {k: (int(v) if float(v).is_integer() else v) for k, v in m["counters"].items()}
    for k in ("requests", "failed", "in_step", "left_out"):
        if float(m[k]).is_integer():
            m[k] = int(m[k])
    out = dict(heartbeats=m["beats"], counters_present=m["present"], counters=c, requests=m["requests"], failed=m["failed"],
               failed_share=share(m["failed"], m["requests"]) if m["requests"] else None,
               in_step=m["in_step"], left_out_first_steps=m["left_out"], coin_minutes=float(m["coin_minutes"]),
               in_step_share=float(Fraction(m["in_step"]) / m["coin_minutes"]) if m["coin_minutes"] else None)
    out["failed_clause"] = clause(m["failed_ok"], rule="pre_error / (pre_fetched + pre_error) <= 1%")
    out["in_step_clause"] = clause(m["in_step_ok"], rule="(pre_missing + pre_ondemand, first step after each start left "
                                   "out) / (18 x minutes run) <= 2%")
    out["met"] = m["failed_ok"] and m["in_step_ok"]
    return out


def evaluate(meta, B, S, rows5, starts5, rows_main, rows_fourth, items, fourth_folder="paper_spot_t18",
             fifth_folder="paper_spot_r5", start=None, end=None, read_as_is=False, min_bids=MIN_BIDS,
             min_heartbeats=MIN_HEARTBEATS, pairs=None, min_pairs=MIN_PAIRS):
    """meta: two_books.json; B: item7_bids.csv; S: side_by_side.csv (data frames); rows5, rows_main, rows_fourth: data-quality
    rows of the heartbeats in the period (log_rows); starts5: the fifth book's first stepped minutes."""
    start = start if start is not None else meta["period"]["start"]
    end = end if end is not None else meta["period"]["end"]
    if items not in ("pass", "fail"):
        raise ValueError(f"items 1 to 5 must be pass or fail, not {items}")
    coins = guard(meta, fourth_folder, fifth_folder, start, end)
    c4, c5 = book_counts(B, S, FOURTH, coins), book_counts(B, S, FIFTH, coins)
    period_ok = c4["n"] >= min_bids and c5["n"] >= min_bids
    m1 = measure1(rows5, rows_main, rows_fourth, pairs, start, end, min_heartbeats, min_pairs)
    m2 = measure2(c5, c4)
    m3 = dict(value=items, met=items == "pass")
    m4 = measure4(rows5, starts5)
    holds = [m1["met"], m2["met"], m3["met"], m4["met"]]
    if not period_ok and not read_as_is:
        verdict = None
    else:
        verdict = "pass" if all(holds) else "fail"
    return dict(period=dict(start=str(pd.Timestamp(start)), end=str(pd.Timestamp(end))), books=meta["books"],
                label_mapping={"main": f"fourth book ({fourth_folder})", "tb": f"fifth book ({fifth_folder})"},
                minutes=meta.get("minutes"), coins=coins,
                condition=dict(new_bids_fifth=c5["n"], new_bids_fourth=c4["n"], needed=min_bids, met=period_ok,
                               read_as_is=bool(read_as_is)),
                counts=dict(fifth=c5, fourth=c4), measures=dict(step=m1, decisions=m2, items_1_5=m3, candle_requests=m4),
                holds=dict(zip(("1", "2", "3", "4"), holds)), verdict=verdict)


# ---------------------------------------------------------------- output
def pct(x):
    return "n/a" if x is None else f"{100 * x:.3f}%"


def sx(x):
    return "n/a" if x is None else f"{x:.3f} s"


def mk(ok):
    return "met" if ok else "not met"


def to_md(res):
    c, M = res["condition"], res["measures"]
    L = ["# Part 3: the fifth paper book (all 17 coins, common minutes)", "",
         f"Period: {res['period']['start']} to {res['period']['end']} UTC (both minutes included).",
         f"Labels in the reconciliation folder: main = {res['label_mapping']['main']}, tb = {res['label_mapping']['tb']}."]
    if res.get("minutes"):
        m = res["minutes"]
        L.append(f"Decision minutes: fourth book {m['main']}, fifth book {m['tb']}; common minutes {m['common']}.")
    L += ["", f"Period condition: {c['new_bids_fifth']} new bids in the fifth book and {c['new_bids_fourth']} in the "
              f"fourth, {c['needed']} needed in each: {mk(c['met'])}."]
    if not c["met"]:
        L += ["", "**PERIOD NOT COMPLETE**" + (" (read as is, as the plan allows after the third extension)"
                                                if c["read_as_is"] else "; no verdict")]
    s = M["step"]
    L += ["", "## Measure 1, the step", "",
          "| clause | value | rule | result |", "|---|---|---|---|",
          f"| (a) same-machine pairs, build minus release 3 | median {sx(s['a']['median_s'])} over {s['a']['pairs']} pairs | "
          f"at or below zero, at least {s['a']['needed']} pairs | {mk(s['a']['met'])} |",
          f"| (b) fifth against main, same heartbeat times | fifth {sx(s['b']['fifth_median_s'])}, main "
          f"{sx(s['b']['main_median_s'])}, {s['b']['paired_half_hours']} half hours, {s['b']['fifth_heartbeats']} fifth-book "
          f"heartbeats | fifth no higher, at least {s['b']['needed']} half hours and heartbeats | {mk(s['b']['met'])} |",
          f"| reported, decides nothing: the fifth book's own median | {sx(s['reported']['fifth_own_median_s'])} over "
          f"{s['reported']['fifth_heartbeats']} heartbeats, against {s['reported']['bar_s']:g} s | - | "
          f"{'at or below' if s['reported']['at_or_below_bar'] else 'above'} {s['reported']['bar_s']:g} s |",
          f"| for information: fifth against fourth | fifth {sx(s['fourth_for_information']['fifth_median_s'])}, fourth "
          f"{sx(s['fourth_for_information']['fourth_median_s'])}, {s['fourth_for_information']['paired_half_hours']} "
          "half hours | not part of the rule | - |", "", f"Measure 1: {mk(s['met'])}.", ""]
    d = M["decisions"]
    L += ["## Measure 2, decisions against the research", "",
          "| clause | fifth book | fourth book | rule | result |", "|---|---|---|---|---|"]
    for key, name in (("wrong_side_vs_fourth", "wrong side against the fourth book"), ("wrong_side_cap", "wrong side, cap"),
                      ("matched", "matched"), ("level", "level more than 5 bp")):
        x = d[key]
        L.append(f"| {name} | {x['fifth']} = {pct(x['fifth_share'])} | {x.get('fourth', '-')}"
                 + (f" = {pct(x['fourth_share'])}" if "fourth" in x else "") + f" | {x['rule']} | {mk(x['met'])} |")
    L += ["", f"Measure 2: {mk(d['met'])}.", "",
          "## Measure 3, items 1 to 5 of the fifth book", "",
          f"Read by the owner from the status report on the cut log: {M['items_1_5']['value']}. "
          f"Measure 3: {mk(M['items_1_5']['met'])}.", ""]
    q = M["candle_requests"]
    L += ["## Measure 4, the candle requests between steps", ""]
    if not q["counters_present"]:
        L += ["No heartbeat of the fifth book in the period carries the counters: not met.", ""]
    else:
        L += ["| clause | value | rule | result |", "|---|---|---|---|",
              f"| failed requests | {q['failed']} of {q['requests']} = {pct(q['failed_share'])} | "
              f"{q['failed_clause']['rule']} | {mk(q['failed_clause']['met'])} |",
              f"| requests inside a step | {q['in_step']} of {q['coin_minutes']:,.0f} coin-minutes = {pct(q['in_step_share'])} "
              f"({q['left_out_first_steps']} left out as the first step after a start) | {q['in_step_clause']['rule']} | "
              f"{mk(q['in_step_clause']['met'])} |", ""]
    L += [f"Measure 4: {mk(q['met'])}.", ""]
    L += ["| measure | holds |", "|---|---|"] + [f"| {k} | {'yes' if v else 'no'} |" for k, v in res["holds"].items()] + [""]
    if res["verdict"] is None:
        L += ["**Part 3: no verdict (period not complete)**", ""]
    else:
        L += [f"**Part 3: {res['verdict']}**", ""]
    L += ["Rule in plain words: all four measures must hold. 1: the median over at least 8 same-machine pairs of the build's "
          "data step minus release 3's at or below zero, and the fifth book's median no higher than the main book's over "
          "the same half hours. 2: against the research, wrong-side share at most the "
          "fourth book's plus 2.0 points and at most 5%, matched share at least the fourth's minus 3.0 points, under 5% of "
          "bids more than 5 bp from the level. 3: items 1 to 5. 4: failed candle requests at most 1% of requests, "
          "requests inside a step at most 2% of coin-minutes. Shares are compared exactly on the counts. A PASS makes "
          "the build's configuration release 5; it does not change `main` by itself.", ""]
    return "\n".join(L)


def write(out_dir, res):
    os.makedirs(out_dir, exist_ok=True)
    json.dump(res, open(os.path.join(out_dir, "part3_rule.json"), "w"), indent=1)
    open(os.path.join(out_dir, "part3_rule.md"), "w").write(to_md(res))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--fifth", required=True)
    ap.add_argument("--fourth", required=True)
    ap.add_argument("--main", required=True)
    ap.add_argument("--items-1-5", dest="items", choices=["pass", "fail"], required=True)
    ap.add_argument("--pairs", default=PAIRS_DEFAULT)
    ap.add_argument("--out")
    ap.add_argument("--read-as-is", action="store_true")
    ap.add_argument("--min-bids", type=int, default=MIN_BIDS)
    ap.add_argument("--min-heartbeats", type=int, default=MIN_HEARTBEATS)
    a = ap.parse_args(argv)
    meta = json.load(open(os.path.join(a.dir, "two_books.json")))
    B = pd.read_csv(os.path.join(a.dir, "item7_bids.csv"))
    S = pd.read_csv(os.path.join(a.dir, "side_by_side.csv"))
    rows5, starts5 = log_rows(a.fifth, a.start, a.end)
    rows_main, _ = log_rows(a.main, a.start, a.end)
    rows_fourth, _ = log_rows(a.fourth, a.start, a.end)
    res = evaluate(meta, B, S, rows5, starts5, rows_main, rows_fourth, a.items,
                   os.path.basename(os.path.normpath(a.fourth)), os.path.basename(os.path.normpath(a.fifth)),
                   a.start, a.end, a.read_as_is, a.min_bids, a.min_heartbeats, ps.load_pairs(a.pairs))
    write(a.out or a.dir, res)
    print(to_md(res))


if __name__ == "__main__":
    main()
