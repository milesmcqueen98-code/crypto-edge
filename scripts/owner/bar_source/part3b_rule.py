"""Part 3, second run, of reports/owner/bar_source_prereg.md (section "Part 3, second run: the corrected build"), as code.
Written down exactly as the plan states it; do not improve on it. part3_rule.py stays as the record of the first run; this
script imports its functions (counts, guard, measures 1 and 4, the exact arithmetic) and changes only what the plan changed.
Every comparison is made on whole numbers or exact fractions, never on rounded shares.

Inputs
  --dir       a folder written by scripts/owner/reconcile/two_books.py run with --main paper_spot_t18 --third paper_spot_r5
              (labels there: main = the FOURTH book, tb = the FIFTH book; all 17 coins; the minutes both decided).
  --dir-main  a second folder written by two_books.py run with --main paper_spot --third paper_spot_r5 (labels there: main =
              the MAIN book, tb = the FIFTH book; all 17 coins; the minutes the fifth and the main book both decided).
  --start, --end  the period (UTC minutes, both included).
  --fifth, --fourth, --main  the three book folders (events.jsonl).
  --pair-commit  the full 40-character commit the same-machine pairs must have run (the pair file's code_commit).
  --items-1-5 pass|fail  items 1 to 5 of the fifth book, read by the owner from the status report on a cut copy of its log.
  --pairs, --out (default --dir), --read-as-is  as in part3_rule.py.

Guards (both folders): two_books.json's period equals --start and --end, its books are the ones named (--dir: --fourth and
  --fifth; --dir-main: --main and --fifth), its group "all" is the 17 coins (trades list plus candle path); in --dir the group
  "trades list" must be exactly ETH, LTC, SOL, XRP, ZEC. A count from item7_bids.csv that differs from its side_by_side.csv
  check (part3_rule.book_counts) is an error and no verdict, in both folders.

Measure 1, the step: as in part3_rule.py, but only pair files whose code_commit equals --pair-commit are passed on; the others
  are set aside and counted ("pairs of another commit: N").
Measure 2, decisions (exact; a zero denominator means the clause is not met):
  (2a) against the fourth book, --dir, all 17 coins:  w5/ns5 <= w4/ns4 + 0.02
  (2b) against the main book, --dir-main, all 17 coins:  w5b/ns5b <= wm/nsm + 0.02  (w5b/ns5b: the fifth book's counts there)
  (2c) the cap, restated: --dir, item7_bids.csv rows of label tb with a research score on the five coins ETH, LTC, SOL, XRP,
       ZEC:  w5(five)/ns5(five) <= 0.05
       (these two counts are cross-checked against side_by_side.csv, measure m2_score_error, group "trades list", book tb,
       statistics n_other_side and n; a mismatch or a missing row is an error and no verdict)
  (2d) matched, --dir:  m5/r5 >= m4/r4 - 0.03
  (2e) level, --dir:  l5/nl5 < 0.05 (strictly)
  There is no cap on all 17 coins. Reported, deciding nothing: w5/ns5 against 5% ("the first run's cap (reported only): would
  be met" or "would not be met"), the fifth and fourth books' shares on the twelve ("candle path") and on the five, and the
  main book's share.
Measure 3: --items-1-5.   Measure 4: part3_rule.measure4 on the fifth book's heartbeats in the period.
Period condition: each of the fifth and fourth books at least 300 new bids in --dir (--read-as-is as in part3_rule.py); the main
  book has no minimum, its counts are printed.
Verdict line: "Part 3, second run: pass" only if all four measures hold, else "Part 3, second run: fail" (no verdict when the
  period or part (a) is not complete and --read-as-is is not given, as in the first rule).

Command line:
  python scripts/owner/bar_source/part3b_rule.py --dir DIR --dir-main DIR2 --start 2026-..T..:.. --end 2026-..T..:.. \\
      --fifth paper_spot_r5 --fourth paper_spot_t18 --main paper_spot --items-1-5 pass|fail --pair-commit HASH \\
      [--pairs DIR] [--out DIR] [--read-as-is]
  writes part3b_rule.json and part3b_rule.md into --out (default --dir) and prints the markdown.
"""
import argparse
import json
import os
import re
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pandas as pd             # noqa: E402

import part3_rule as p3         # noqa: E402

ps = p3.ps
FIVE = ["ETH", "LTC", "SOL", "XRP", "ZEC"]
TOLERANCE = p3.WRONG_SIDE_TOLERANCE
CAP = p3.WRONG_SIDE_CAP
HASH = re.compile(r"^[0-9a-f]{40}$")
share, mk, pct = p3.share, p3.mk, p3.pct


def commit_arg(text):
    if not HASH.match(text):
        raise argparse.ArgumentTypeError("--pair-commit must be a full 40-character hash (lower-case hex)")
    return text


# ---------------------------------------------------------------- guards
def guard_main(meta, main_folder, fifth_folder, start, end):
    """The same guard as part3_rule.guard for --dir-main: labels main = the main book, tb = the fifth book."""
    books = meta.get("books", {})
    if books.get(p3.FOURTH) != main_folder or books.get(p3.FIFTH) != fifth_folder:
        raise ValueError("--dir-main is not a main-book / fifth-book reconciliation: books must be main = "
                         f"{main_folder} and tb = {fifth_folder}, found {books}")
    p = meta.get("period", {})
    if pd.Timestamp(p.get("start")) != pd.Timestamp(start) or pd.Timestamp(p.get("end")) != pd.Timestamp(end):
        raise ValueError(f"--dir-main's period {p} differs from --start {start} --end {end}")
    g = meta.get("groups", {})
    allc = set(g.get(p3.GROUP, []))
    if len(allc) != p3.N_COINS or allc != set(g.get("trades list", [])) | set(g.get("candle path", [])) \
            or set(g.get("trades list", [])) & set(g.get("candle path", [])):
        raise ValueError(f"--dir-main's group 'all' is not the {p3.N_COINS} traded coins (trades list plus candle path): {g}")
    return sorted(allc)


def five_coins(meta):
    got = meta.get("groups", {}).get("trades list", [])
    if sorted(got) != FIVE or len(got) != len(FIVE):
        raise ValueError(f"the group 'trades list' of --dir is not exactly {', '.join(FIVE)}: {got}")
    return list(FIVE)


# ---------------------------------------------------------------- counts on a group of coins
def scored(B, label, coins):
    """(w, ns): bids of the book on these coins with a research score, and those on the wrong side (item7_bids.csv)."""
    A = B[(B["book"] == label) & (B["coin"].isin(coins))]
    sc = A[A["res_score"].notna()]
    return int((sc["res_other_side"].astype(str).str.lower() == "true").sum()), int(len(sc))


def side_group_value(S, measure, statistic, group, book):
    """Like part3_rule.side_value but for a named coin group of side_by_side.csv (exactly one row, a whole number)."""
    r = S[(S["measure"] == measure) & (S["statistic"] == statistic) & (S["group"] == group) & (S["book"] == book)]
    if len(r) != 1:
        raise ValueError(f"side_by_side.csv: expected one row for {measure} / {statistic} / {group} / {book}, found {len(r)}")
    return p3.to_int(r["value"].iloc[0], f"side_by_side.csv {measure} / {statistic} / {group} / {book}")


def five_counts(B, S):
    """(w, ns) of the fifth book on the five coins from item7_bids.csv, checked against side_by_side.csv (measure
    m2_score_error, group "trades list", book tb, statistics n and n_other_side); a mismatch or a missing row is an error."""
    w, ns = scored(B, p3.FIFTH, FIVE)
    for what, mine, stat in (("scored bids on the five coins", ns, "n"), ("wrong-side bids on the five coins", w, "n_other_side")):
        theirs = side_group_value(S, "m2_score_error", stat, "trades list", p3.FIFTH)
        if mine != theirs:
            raise ValueError(f"inconsistent folder: {what} of the tb book from item7_bids.csv ({mine}) differ from "
                             f"side_by_side.csv ({theirs})")
    return w, ns


def frac_le(k, n, k2, n2, add):
    """k/n <= k2/n2 + add, exact; a zero denominator means not met."""
    return bool(n and n2) and Fraction(k, n) <= Fraction(k2, n2) + add


# ---------------------------------------------------------------- the rule
def measure2(c5, c4, c5b, cm, w5five, ns5five):
    """c5, c4: the fifth and fourth books' counts in --dir; c5b, cm: the fifth and the main books' counts in --dir-main;
    (w5five, ns5five): the fifth book's wrong-side and scored bids on the five coins in --dir."""
    a = frac_le(c5["w"], c5["ns"], c4["w"], c4["ns"], TOLERANCE)
    b = frac_le(c5b["w"], c5b["ns"], cm["w"], cm["ns"], TOLERANCE)
    c = bool(ns5five) and Fraction(w5five, ns5five) <= CAP
    d = bool(c5["r"] and c4["r"]) and Fraction(c5["m"], c5["r"]) >= Fraction(c4["m"], c4["r"]) - p3.MATCHED_TOLERANCE
    e = bool(c5["nl"]) and Fraction(c5["l"], c5["nl"]) < p3.LEVEL_CAP
    out = dict(
        wrong_side_vs_fourth=p3.clause(a, fifth=f"{c5['w']}/{c5['ns']}", fourth=f"{c4['w']}/{c4['ns']}",
                                       fifth_share=share(c5["w"], c5["ns"]), fourth_share=share(c4["w"], c4["ns"]),
                                       rule="fifth share <= fourth share + 2.0 points"),
        wrong_side_vs_main=p3.clause(b, fifth=f"{c5b['w']}/{c5b['ns']}", main=f"{cm['w']}/{cm['ns']}",
                                     fifth_share=share(c5b["w"], c5b["ns"]), main_share=share(cm["w"], cm["ns"]),
                                     rule="fifth share <= main book's share + 2.0 points"),
        wrong_side_cap_five=p3.clause(c, fifth=f"{w5five}/{ns5five}", fifth_share=share(w5five, ns5five), coins=list(FIVE),
                                      rule="fifth share on ETH, LTC, SOL, XRP, ZEC <= 5%"),
        matched=p3.clause(d, fifth=f"{c5['m']}/{c5['r']}", fourth=f"{c4['m']}/{c4['r']}", fifth_share=share(c5["m"], c5["r"]),
                          fourth_share=share(c4["m"], c4["r"]), rule="fifth share >= fourth share - 3.0 points"),
        level=p3.clause(e, fifth=f"{c5['l']}/{c5['nl']}", fifth_share=share(c5["l"], c5["nl"]),
                        rule="fifth share < 5% (strictly)"))
    out["met"] = a and b and c and d and e
    return out


def reported(B, c5, cm, twelve, five):
    """Reported, deciding nothing: all 17 coins against the first run's cap, the twelve and the five apart, the main book."""
    cap_met = bool(c5["ns"]) and Fraction(c5["w"], c5["ns"]) <= CAP
    rows = {}
    for name, coins in (("twelve", twelve), ("five", five)):
        w5, n5 = scored(B, p3.FIFTH, coins)
        w4, n4 = scored(B, p3.FOURTH, coins)
        rows[name] = dict(fifth=f"{w5}/{n5}", fifth_share=share(w5, n5), fourth=f"{w4}/{n4}", fourth_share=share(w4, n4))
    return dict(first_run_cap=dict(fifth=f"{c5['w']}/{c5['ns']}", fifth_share=share(c5["w"], c5["ns"]), would_be_met=cap_met,
                                   decides="nothing"),
                groups=rows, main_all=dict(wrong_side=f"{cm['w']}/{cm['ns']}", share=share(cm["w"], cm["ns"])),
                decides="nothing")


def split_pairs(directory, commit):
    """(pairs of --pair-commit as ps.load_pairs gives them, number of pair files of another commit): every *.json of the folder
    is read for its code_commit; a file without a readable code_commit equal to the given one is of another commit."""
    pairs = ps.load_pairs(directory)
    keep, other = [], 0
    for p in pairs:
        try:
            with open(os.path.join(directory, p["file"]), encoding="utf-8") as f:
                got = json.load(f).get("code_commit")
        except (OSError, ValueError, AttributeError):
            got = None
        if got == commit:
            keep.append(p)
        else:
            other += 1
    return keep, other


def evaluate(meta, B, S, meta_main, Bm, Sm, rows5, starts5, rows_main, rows_fourth, items, fourth_folder="paper_spot_t18",
             fifth_folder="paper_spot_r5", main_folder="paper_spot", start=None, end=None, read_as_is=False,
             min_bids=p3.MIN_BIDS, min_heartbeats=p3.MIN_HEARTBEATS, pairs=None, pairs_other=0, min_pairs=p3.MIN_PAIRS):
    """meta, B, S: --dir's two_books.json, item7_bids.csv, side_by_side.csv; meta_main, Bm, Sm: the same of --dir-main; rows5,
    rows_main, rows_fourth: data-quality rows of the heartbeats in the period (p3.log_rows); starts5: the fifth book's first
    stepped minutes; pairs: the pairs of the right commit; pairs_other: how many pair files were set aside."""
    start = start if start is not None else meta["period"]["start"]
    end = end if end is not None else meta["period"]["end"]
    if items not in ("pass", "fail"):
        raise ValueError(f"items 1 to 5 must be pass or fail, not {items}")
    coins = p3.guard(meta, fourth_folder, fifth_folder, start, end)
    coins_main = guard_main(meta_main, main_folder, fifth_folder, start, end)
    five = five_coins(meta)
    twelve = sorted(set(coins) - set(five))
    c4, c5 = p3.book_counts(B, S, p3.FOURTH, coins), p3.book_counts(B, S, p3.FIFTH, coins)
    cm, c5b = p3.book_counts(Bm, Sm, p3.FOURTH, coins_main), p3.book_counts(Bm, Sm, p3.FIFTH, coins_main)
    w5five, ns5five = five_counts(B, S)
    period_ok = c4["n"] >= min_bids and c5["n"] >= min_bids
    m1 = p3.measure1(rows5, rows_main, rows_fourth, pairs, start, end, min_heartbeats, min_pairs)
    m1["pairs_of_another_commit"] = int(pairs_other)
    m2 = measure2(c5, c4, c5b, cm, w5five, ns5five)
    m3 = dict(value=items, met=items == "pass")
    m4 = p3.measure4(rows5, starts5)
    holds = [m1["met"], m2["met"], m3["met"], m4["met"]]
    part_a_complete = m1["a"]["complete"]
    if (not period_ok or not part_a_complete) and not read_as_is:
        verdict = None
    else:
        verdict = "pass" if all(holds) else "fail"
    return dict(rule="part 3, second run",
                period=dict(start=str(pd.Timestamp(start)), end=str(pd.Timestamp(end))), books=meta["books"],
                books_main=meta_main["books"],
                label_mapping={"main": f"fourth book ({fourth_folder})", "tb": f"fifth book ({fifth_folder})"},
                label_mapping_main={"main": f"main book ({main_folder})", "tb": f"fifth book ({fifth_folder})"},
                minutes=meta.get("minutes"), minutes_main=meta_main.get("minutes"), coins=coins, five=five, twelve=twelve,
                condition=dict(new_bids_fifth=c5["n"], new_bids_fourth=c4["n"], new_bids_main=cm["n"],
                               new_bids_fifth_vs_main=c5b["n"], needed=min_bids, met=period_ok,
                               read_as_is=bool(read_as_is), part_a_complete=part_a_complete),
                counts=dict(fifth=c5, fourth=c4, main=cm, fifth_vs_main=c5b, fifth_five=dict(w=w5five, ns=ns5five)),
                measures=dict(step=m1, decisions=m2, items_1_5=m3, candle_requests=m4),
                reported=reported(B, c5, cm, twelve, five),
                holds=dict(zip(("1", "2", "3", "4"), holds)), verdict=verdict)


# ---------------------------------------------------------------- output
def to_md(res):
    c, M, R = res["condition"], res["measures"], res["reported"]
    L = ["# Part 3, second run: the fifth paper book on the corrected build (all 17 coins, common minutes)", "",
         f"Period: {res['period']['start']} to {res['period']['end']} UTC (both minutes included).",
         f"Labels in the folder against the fourth book: main = {res['label_mapping']['main']}, tb = {res['label_mapping']['tb']}.",
         f"Labels in the folder against the main book: main = {res['label_mapping_main']['main']}, "
         f"tb = {res['label_mapping_main']['tb']}."]
    if res.get("minutes"):
        m = res["minutes"]
        L.append(f"Decision minutes, fourth-book folder: fourth book {m['main']}, fifth book {m['tb']}; common minutes {m['common']}.")
    if res.get("minutes_main"):
        m = res["minutes_main"]
        L.append(f"Decision minutes, main-book folder: main book {m['main']}, fifth book {m['tb']}; common minutes {m['common']}.")
    L += ["", f"Period condition: {c['new_bids_fifth']} new bids in the fifth book and {c['new_bids_fourth']} in the "
              f"fourth, {c['needed']} needed in each: {mk(c['met'])}. The main book has no minimum: "
              f"{c['new_bids_main']} new bids (fifth book on the minutes it shares with the main book: {c['new_bids_fifth_vs_main']})."]
    if not c["met"]:
        L += ["", "**PERIOD NOT COMPLETE**" + (" (read as is, as the plan allows after the third extension)"
                                                if c["read_as_is"] else "; no verdict")]
    s = M["step"]
    if not c.get("part_a_complete", True):
        L += ["", f"PART (a) NOT COMPLETE: {s['a']['pairs']} of {s['a']['needed']} pairs count; the pair jobs go on and the "
                  "read waits"]
        if c["read_as_is"]:
            L += ["", "Read as is: part (a) is not met."]
    if s["a"].get("added"):
        L += ["", f"Part (a) pairs: {s['a']['in_period']} started in the period and {s['a']['added']} were added from after "
                  f"it (fewer than {s['a']['needed']} counted in the period); the last pair used started "
                  f"{s['a']['last_used_start']} UTC. Part (b) and measures 2 to 4 are read on the period itself."]
    L += ["", "## Measure 1, the step", "",
          f"Pairs of another commit: {s['pairs_of_another_commit']} (set aside; only pairs of the commit given by --pair-commit "
          "are used).", "",
          "| clause | value | rule | result |", "|---|---|---|---|",
          f"| (a) same-machine pairs, build minus release 3 | median {p3.sx(s['a']['median_s'])} over {s['a']['pairs']} pairs | "
          f"at or below zero, at least {s['a']['needed']} pairs | {mk(s['a']['met'])} |",
          f"| (b) fifth against main, same heartbeat times | fifth {p3.sx(s['b']['fifth_median_s'])}, main "
          f"{p3.sx(s['b']['main_median_s'])}, {s['b']['paired_half_hours']} half hours, {s['b']['fifth_heartbeats']} fifth-book "
          f"heartbeats | fifth no higher, at least {s['b']['needed']} half hours and heartbeats | {mk(s['b']['met'])} |",
          f"| reported, decides nothing: the fifth book's own median | {p3.sx(s['reported']['fifth_own_median_s'])} over "
          f"{s['reported']['fifth_heartbeats']} heartbeats, against {s['reported']['bar_s']:g} s | - | "
          f"{'at or below' if s['reported']['at_or_below_bar'] else 'above'} {s['reported']['bar_s']:g} s |",
          f"| for information: fifth against fourth | fifth {p3.sx(s['fourth_for_information']['fifth_median_s'])}, fourth "
          f"{p3.sx(s['fourth_for_information']['fourth_median_s'])}, {s['fourth_for_information']['paired_half_hours']} "
          "half hours | not part of the rule | - |", "", f"Measure 1: {mk(s['met'])}.", ""]
    d = M["decisions"]
    L += ["## Measure 2, decisions against the research", "",
          "| clause | fifth book | other book | rule | result |", "|---|---|---|---|---|"]
    for key, name, other in (("wrong_side_vs_fourth", "(2a) wrong side against the fourth book, 17 coins", "fourth"),
                             ("wrong_side_vs_main", "(2b) wrong side against the main book, 17 coins", "main"),
                             ("wrong_side_cap_five", "(2c) wrong side, cap on the five coins", None),
                             ("matched", "(2d) matched, 17 coins", "fourth"),
                             ("level", "(2e) level more than 5 bp, 17 coins", None)):
        x = d[key]
        L.append(f"| {name} | {x['fifth']} = {pct(x['fifth_share'])} | "
                 + (f"{x[other]} = {pct(x[other + '_share'])} ({other} book)" if other else "-")
                 + f" | {x['rule']} | {mk(x['met'])} |")
    L += ["", f"Measure 2: {mk(d['met'])}.", ""]
    fr = R["first_run_cap"]
    L += ["Reported, deciding nothing:", "",
          f"- All 17 coins, wrong side {fr['fifth']} = {pct(fr['fifth_share'])} of scored bids in the fifth book: the first run's "
          f"cap (reported only): {'would be met' if fr['would_be_met'] else 'would not be met'} (5%).",
          f"- Wrong-side share on the twelve (candle path): fifth book {R['groups']['twelve']['fifth']} = "
          f"{pct(R['groups']['twelve']['fifth_share'])}, fourth book {R['groups']['twelve']['fourth']} = "
          f"{pct(R['groups']['twelve']['fourth_share'])}.",
          f"- Wrong-side share on the five (trades list): fifth book {R['groups']['five']['fifth']} = "
          f"{pct(R['groups']['five']['fifth_share'])}, fourth book {R['groups']['five']['fourth']} = "
          f"{pct(R['groups']['five']['fourth_share'])}.",
          f"- Main book, all 17 coins: {R['main_all']['wrong_side']} = {pct(R['main_all']['share'])}.", "",
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
        why = " and ".join(([] if c["met"] else ["period not complete"])
                           + ([] if c.get("part_a_complete", True) else ["part (a) not complete"]))
        L += [f"**Part 3, second run: no verdict ({why})**", ""]
    else:
        L += [f"**Part 3, second run: {res['verdict']}**", ""]
    L += ["Rule in plain words: all four measures must hold. 1: the median over at least 8 same-machine pairs of the corrected "
          "build's data step minus release 3's at or below zero, using only pair files of the commit named for the second run "
          "(pairs that start in the period; if fewer than 8 count there, the later pairs of that commit are added oldest first "
          "up to the one that makes 8, and the verdict waits for them), and the fifth book's median no higher than the main "
          "book's over the same half hours. 2: against the research, on all 17 coins the fifth book's wrong-side share at most "
          "the fourth book's plus 2.0 points and at most the main book's plus 2.0 points (each on the minutes the two books "
          "both decided); on the five coins whose candles are cut at the minute (ETH, LTC, SOL, XRP, ZEC) its wrong-side share "
          "at most 5%; its matched share at least the fourth book's minus 3.0 points; under 5% of its bids more than 5 bp from "
          "the level. There is no cap on all 17 coins: that share is reported against the first run's 5% and decides nothing. "
          "3: items 1 to 5. 4: failed candle requests at most 1% of requests, requests inside a step at most 2% of "
          "coin-minutes. Shares are compared exactly on the counts. A PASS makes the corrected build's configuration release 5; "
          "it does not change `main` by itself.", ""]
    return "\n".join(L)


def write(out_dir, res):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "part3b_rule.json"), "w") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(out_dir, "part3b_rule.md"), "w") as f:
        f.write(to_md(res))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--dir-main", dest="dir_main", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--fifth", required=True)
    ap.add_argument("--fourth", required=True)
    ap.add_argument("--main", required=True)
    ap.add_argument("--items-1-5", dest="items", choices=["pass", "fail"], required=True)
    ap.add_argument("--pair-commit", dest="pair_commit", type=commit_arg, required=True)
    ap.add_argument("--pairs", default=p3.PAIRS_DEFAULT)
    ap.add_argument("--out")
    ap.add_argument("--read-as-is", action="store_true")
    ap.add_argument("--min-bids", type=int, default=p3.MIN_BIDS)
    ap.add_argument("--min-heartbeats", type=int, default=p3.MIN_HEARTBEATS)
    a = ap.parse_args(argv)

    def folder(d):
        with open(os.path.join(d, "two_books.json")) as f:
            meta = json.load(f)
        return meta, pd.read_csv(os.path.join(d, "item7_bids.csv")), pd.read_csv(os.path.join(d, "side_by_side.csv"))
    meta, B, S = folder(a.dir)
    meta_main, Bm, Sm = folder(a.dir_main)
    rows5, starts5 = p3.log_rows(a.fifth, a.start, a.end)
    rows_main, _ = p3.log_rows(a.main, a.start, a.end)
    rows_fourth, _ = p3.log_rows(a.fourth, a.start, a.end)
    pairs, other = split_pairs(a.pairs, a.pair_commit)
    base = lambda x: os.path.basename(os.path.normpath(x))      # noqa: E731
    res = evaluate(meta, B, S, meta_main, Bm, Sm, rows5, starts5, rows_main, rows_fourth, a.items, base(a.fourth), base(a.fifth),
                   base(a.main), a.start, a.end, a.read_as_is, a.min_bids, a.min_heartbeats, pairs, other)
    write(a.out or a.dir, res)
    print(to_md(res))


if __name__ == "__main__":
    main()
