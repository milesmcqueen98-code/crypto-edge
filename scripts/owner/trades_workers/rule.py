"""Parts 3 and 4 of reports/owner/trades_workers_plan.md ("The trades pass side by side"), as code. Semantics fixed by the
plan and the owner's brief; do not improve on them. Modelled on scripts/owner/bar_source/part3_rule.py: same kind of
inputs, outputs and exact arithmetic (every comparison below is made on whole numbers or exact fractions, never on
rounded shares), and the same readings of the reconciliation folder (its functions are imported, not copied).

Inputs
  --dir     a folder written by scripts/owner/reconcile/two_books.py run with --main paper_spot_r5 --third paper_spot_tw
            over the period. In that folder's tables the label "main" means the FIFTH paper book (paper_spot_r5, the control)
            and the label "tb" means the SIXTH paper book (paper_spot_tw). Everything is on the minutes both books were live
            and on the 17 traded coins: the folder's group "all" (two_books.json groups["all"]); the script stops with an
            error unless that group is exactly the 17 coins of "trades list" plus "candle path" (5 plus 12), and unless
            two_books.json's period equals --start and --end and its books are the ones named by --fifth and --sixth.
  --start, --end  the period (UTC minutes, both included).
  --sixth, --fifth  the two book folders (events.jsonl).
  --pairs   the folder of the workers pair files (default reports/owner/step_pairs_tw, written by
            scripts/owner/step_pairs/run_pair_workers.py).
  --items-1-5 pass|fail  items 1 to 5 of the sixth book, read from the status report (scripts/owner/paper_status.py) on a copy
            of its log cut at the period's end; the script does not compute them.

Where each count of Part 4, measure 1 comes from (all for the 17 coins, on the common minutes; "sixth" is label tb, "fifth" is
label main). The reading is part3_rule.book_counts, unchanged:
  n   new bids of a book: the number of rows of item7_bids.csv with that label and a coin of groups["all"]
      (checked against side_by_side.csv, measure m3_bids, statistic bot_new_bids, group all).
  ns, w  bids with a research score and, among them, the bids on the wrong side (the research would not have placed them):
      item7_bids.csv, column res_score present gives ns, column res_other_side true gives w (checked against side_by_side.csv,
      measure m2_score_error, statistics n and n_other_side, group all).
  nl, l  bids with a research level and, among them, those more than 5 bp from it: item7_bids.csv, column err_bp present
      gives nl, abs(err_bp) above 5 gives l (nl checked against side_by_side.csv, measure m1_level_error, statistic n, group
      all).
  r, m  the research's new bids (not blocked by cash or a stale input) and, among them, those with a bot bid within a
      minute: side_by_side.csv, measure m3_bids, statistics research_new_bids_ex_blocked (r) and research_matched (m), group
      all. A mismatch between a count from item7_bids.csv and its side_by_side.csv check is an error and no verdict.

Part 3, the pairs (the files pair_*.json of --pairs, "counts" true; a pair belongs to the period by its start, the end minute
  included). If fewer than 8 count in the period, the pairs that count and start after the period's end are added, oldest first,
  one at a time, until the count reaches 8, and the script says so (how many started in the period, how many were added, the
  start of the last one used). This is paper_status.pairs_measure itself (workers_pairs_measure calls it), so the status
  report and this rule choose the same pairs. With fewer than 8 even then it prints
      PART 3 NOT COMPLETE: <n> of 8 pairs count; the pair jobs go on and the read waits
  and gives no verdict unless --read-as-is is passed, which then counts clauses 1, 2 and 4 as not met (they need 8 pairs).
  1. the median over the pairs used of (three's data-step median minus one's), exact from the printed texts, is at most -1/5 s;
  2. budget fallbacks summed over the three-worker runs of the pairs used are no more than over the one-worker runs, and the
     median of (longest pass with three minus longest pass with one) is at most 0;
  3. over ALL pair files that started in the period, counting or not: no three-worker run has peak_per_second above 8 and
     none is refused or limited; a file that cannot be read is listed and makes the clause not met (its start is the file's
     utc_start, else the one in its name; a file with neither is taken as inside the period). A null peak is not above 8;
  4. over the pairs used, rows_differ / rows_compared summed over the three-worker runs is no higher than over the one-worker
     runs (cross-multiplied on integers; a zero denominator on either side means not met).
Part 4, the books:
  1. decisions, exact on integers: wrong side w6/ns6 <= w5/ns5 + 2/100 and w6/ns6 <= 5/100; matched m6/r6 >= m5/r5 - 3/100;
     level l6/nl6 < 5/100 (strictly); a zero denominator means that clause is not met;
  2. --items-1-5;
  3. requests inside a step, the sixth book, heartbeats in the period (paper_status.measure4 and startup_steps, imported
     through paper_status): failed share at most 1% and in-step share at most 2%; and the sixth's in-step share no higher
     than the fifth's over the heartbeat times at which both books have a heartbeat (paper_status.tw_instep_paired,
     cross-multiplied; the number of such times is stated);
  4. stops, heartbeats in the period (paper_status.tw_stops): the sixth has no heartbeat with tb_fb_limited above zero unless the
     fifth's heartbeat at the same time has it too, and the number of the sixth's heartbeats with tb_fb_error above zero is at
     most the fifth's plus 2.
Period condition: each of the sixth and fifth books has at least 300 new bids (n above). Under 300 in either: "PERIOD NOT
  COMPLETE" and no verdict, unless --read-as-is is passed, which is then stated in the output.
Verdict: "Trades workers: pass" only if every clause of Parts 3 and 4 holds, else "Trades workers: fail"; none when the period or
  Part 3 is not complete (and no --read-as-is).
Reported, not ruled on: each pair's trades-pass medians (the pairs used), both books' data-step medians over the common
  heartbeat times, the sixth book's own heartbeat entry step_s.trades.

Command line:
  python scripts/owner/trades_workers/rule.py --dir DIR --start 2026-..T..:.. --end 2026-..T..:.. \\
      --sixth paper_spot_tw --fifth paper_spot_r5 --items-1-5 pass|fail [--pairs DIR] [--out DIR] [--read-as-is]
  reads DIR/two_books.json, DIR/item7_bids.csv, DIR/side_by_side.csv and the two events.jsonl; writes trades_workers_rule.json and
  trades_workers_rule.md into --out (default DIR) and prints the markdown.
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
sys.path.insert(0, os.path.join(OWNER, "bar_source"))

import pandas as pd             # noqa: E402

import paper_status as ps       # noqa: E402
import part3_rule as p3         # noqa: E402

MIN_BIDS = p3.MIN_BIDS
MIN_PAIRS = ps.MIN_PAIRS
PAIRS_DEFAULT = ps.TW_PAIRS_DIR
FIFTH, SIXTH = "main", "tb"         # the labels in the folder: main = fifth book (control), tb = sixth book
GROUP = p3.GROUP
N_COINS = p3.N_COINS
STEP_BAR = ps.TW_STEP_BAR           # -1/5 s
PEAK_MAX = ps.TW_PEAK_MAX           # 8
WRONG_SIDE_TOLERANCE = p3.WRONG_SIDE_TOLERANCE
WRONG_SIDE_CAP = p3.WRONG_SIDE_CAP
MATCHED_TOLERANCE = p3.MATCHED_TOLERANCE
LEVEL_CAP = p3.LEVEL_CAP
ERRORS_EXTRA = 2


def guard(meta, fifth_folder, sixth_folder, start, end):
    books = meta.get("books", {})
    if books.get(FIFTH) != fifth_folder or books.get(SIXTH) != sixth_folder:
        raise ValueError("this folder is not a fifth-book / sixth-book reconciliation: books must be main = "
                         f"{fifth_folder} and tb = {sixth_folder}, found {books}")
    p = meta.get("period", {})
    if pd.Timestamp(p.get("start")) != pd.Timestamp(start) or pd.Timestamp(p.get("end")) != pd.Timestamp(end):
        raise ValueError(f"the folder's period {p} differs from --start {start} --end {end}")
    g = meta.get("groups", {})
    allc = set(g.get(GROUP, []))
    if len(allc) != N_COINS or allc != set(g.get("trades list", [])) | set(g.get("candle path", [])) \
            or set(g.get("trades list", [])) & set(g.get("candle path", [])):
        raise ValueError(f"the folder's group 'all' is not the {N_COINS} traded coins (trades list plus candle path): {g}")
    return sorted(allc)


def _f(x):
    return None if x is None else float(x)


def clause(met, **kw):
    return dict(met=bool(met), **kw)


def share(k, n):
    return float(Fraction(k) / Fraction(n)) if n else None


# ---------------------------------------------------------------- the heartbeats
def log_data(path, start, end):
    """(data-quality rows of the heartbeats inside [start, end + 1 minute), the first stepped minutes of the starts, the
    step_s.trades statistics of those heartbeats) of one book's log, with the log cut at the period's end first (the same
    figures the status report gives on a cut copy; the first two are what part3_rule.log_rows gives)."""
    folder = os.path.normpath(path)
    book = ps.load_book(os.path.dirname(os.path.abspath(folder)), os.path.basename(folder))
    if book["status"] == "missing":
        raise ValueError(f"no events.jsonl in {path}")
    stop = p3.when(end) + timedelta(minutes=1)
    t0 = p3.when(start)
    ev = [e for e in book["events"] if e["_t"] is not None and e["_t"] < stop]
    times = [e["_t"] for e in ev]
    first, last = (min(times), max(times)) if times else (None, None)
    rt = ps.running_time(ev, first, last)
    dq = ps.data_quality(ev, rt)
    return [r for r in dq["rep"] if t0 <= r["t"] < stop], ps.startup_steps(ev), ps.trades_step_stats(ev, t0, stop)


# ---------------------------------------------------------------- Part 3
def part3(pairs, start, end, min_pairs=MIN_PAIRS):
    wm = ps.workers_pairs_measure(pairs or [], p3.when(start), p3.when(end), None, min_pairs, extend=True)
    used = wm["used"]
    d3, c3 = wm["rows3"]
    d1, c1 = wm["rows1"]
    step = clause(wm["step_met"], pairs=wm["n"], needed=min_pairs, enough=wm["enough"], median_s=_f(wm["median"]),
                  median_exact=None if wm["median"] is None else str(wm["median"]), bar_s=float(STEP_BAR),
                  rule="median of three minus one at most -0.2 s, at least 8 pairs")
    slow = clause(wm["slow_met"], fallbacks_three=wm["fb3"], fallbacks_one=wm["fb1"], longest_median_s=_f(wm["long_median"]),
                  longest_median_exact=None if wm["long_median"] is None else str(wm["long_median"]),
                  rule="fallbacks with three no more than with one; median of longest pass three minus one at most 0")
    pace = clause(wm["pace_met"], files_in_period=len(wm["files"]), peak_max=wm["peak_max"],
                  over_peak=[p["file"] for p in wm["peak_over"]], refused_or_limited=[p["file"] for p in wm["stopped"]],
                  unreadable=[p["file"] for p in wm["unreadable"]],
                  rule="no three-worker run above 8 trades requests in one second, none refused or limited, every file readable")
    rows = clause(wm["rows_met"], differ_three=d3, compared_three=c3, differ_one=d1, compared_one=c1,
                  share_three=share(d3, c3), share_one=share(d1, c1),
                  rule="rows differing from the venue: three's share no higher than one's (cross-multiplied)")
    reported = dict(pairs=[dict(file=p["file"], start=p["start"].strftime("%Y-%m-%dT%H:%M:%SZ") if p["start"] else None,
                                trades_pass_median_one=p["one"]["pass_median"], trades_pass_median_three=p["three"]["pass_median"])
                           for p in used],
                    median_one_s=_f(wm["pass_median_one"]), median_three_s=_f(wm["pass_median_three"]), decides="nothing")
    return dict(step=step, slow=slow, pace=pace, rows=rows, reported=reported, complete=wm["complete"], enough=wm["enough"],
                in_period=wm["in_period"], added=wm["added"], pair_files=[p["file"] for p in used],
                last_used_start=None if wm["last_start"] is None else wm["last_start"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                met=step["met"] and slow["met"] and pace["met"] and rows["met"], _wm=wm)


# ---------------------------------------------------------------- Part 4
def decisions(c6, c5):
    """Part 4, clause 1. c6, c5: the counts of the sixth and the fifth book (part3_rule.book_counts)."""
    n6, n5 = c6["ns"], c5["ns"]
    ws = bool(n6 and n5) and Fraction(c6["w"], n6) <= Fraction(c5["w"], n5) + WRONG_SIDE_TOLERANCE
    wc = bool(n6) and Fraction(c6["w"], n6) <= WRONG_SIDE_CAP
    mt = bool(c6["r"] and c5["r"]) and Fraction(c6["m"], c6["r"]) >= Fraction(c5["m"], c5["r"]) - MATCHED_TOLERANCE
    lv = bool(c6["nl"]) and Fraction(c6["l"], c6["nl"]) < LEVEL_CAP
    out = dict(
        wrong_side_vs_fifth=clause(ws, sixth=f"{c6['w']}/{n6}", fifth=f"{c5['w']}/{n5}", sixth_share=share(c6["w"], n6),
                                   fifth_share=share(c5["w"], n5), rule="sixth share <= fifth share + 2.0 points"),
        wrong_side_cap=clause(wc, sixth=f"{c6['w']}/{n6}", sixth_share=share(c6["w"], n6), rule="sixth share <= 5%"),
        matched=clause(mt, sixth=f"{c6['m']}/{c6['r']}", fifth=f"{c5['m']}/{c5['r']}", sixth_share=share(c6["m"], c6["r"]),
                       fifth_share=share(c5["m"], c5["r"]), rule="sixth share >= fifth share - 3.0 points"),
        level=clause(lv, sixth=f"{c6['l']}/{c6['nl']}", sixth_share=share(c6["l"], c6["nl"]),
                     rule="sixth share < 5% (strictly)"))
    out["met"] = ws and wc and mt and lv
    return out


def requests(rows6, starts6, rows5, starts5):
    """Part 4, clause 3: the sixth book's failed and in-step shares (paper_status.measure4) and its in-step share against
    the fifth's over the common heartbeat times (paper_status.tw_instep_paired)."""
    m = ps.measure4(rows6, starts6)
    c = {k: (int(v) if float(v).is_integer() else v) for k, v in m["counters"].items()}
    for k in ("requests", "failed", "in_step", "left_out"):
        if float(m[k]).is_integer():
            m[k] = int(m[k])
    pp = ps.tw_instep_paired(rows6, starts6, rows5, starts5)
    s6, s5 = pp["sixth"], pp["fifth"]
    out = dict(heartbeats=m["beats"], counters_present=m["present"], counters=c, requests=m["requests"], failed=m["failed"],
               failed_share=share(m["failed"], m["requests"]) if m["requests"] else None, in_step=m["in_step"],
               left_out_first_steps=m["left_out"], coin_minutes=float(m["coin_minutes"]),
               in_step_share=float(Fraction(m["in_step"]) / m["coin_minutes"]) if m["coin_minutes"] else None)
    out["failed_clause"] = clause(m["failed_ok"], rule="pre_error / (pre_fetched + pre_error) <= 1%")
    out["in_step_clause"] = clause(m["in_step_ok"], rule="(pre_missing + pre_ondemand, first step after each start left "
                                   "out) / (18 x minutes run) <= 2%")
    out["against_fifth"] = clause(
        pp["met"], common_heartbeat_times=pp["times"], sixth_in_step=_f(s6["in_step"]), sixth_coin_minutes=_f(s6["coin_minutes"]),
        fifth_in_step=_f(s5["in_step"]), fifth_coin_minutes=_f(s5["coin_minutes"]),
        sixth_share=share(s6["in_step"], s6["coin_minutes"]), fifth_share=share(s5["in_step"], s5["coin_minutes"]),
        rule="sixth in-step share no higher than the fifth's over the heartbeat times both books have (cross-multiplied)")
    out["met"] = m["failed_ok"] and m["in_step_ok"] and pp["met"]
    return out


def stops(rows6, rows5):
    s = ps.tw_stops(rows6, rows5)
    return dict(limited_sixth=s["limited6"], limited_fifth=s["limited5"],
                limited_sixth_alone=[t.strftime("%Y-%m-%dT%H:%MZ") for t in s["alone"]], errors_sixth=s["error6"],
                errors_fifth=s["error5"], allowed_errors=s["error5"] + ERRORS_EXTRA,
                limited_clause=clause(s["limited_ok"], rule="no sixth-book heartbeat with tb_fb_limited above 0 unless the "
                                      "fifth's heartbeat at the same time has it too"),
                error_clause=clause(s["error_ok"], rule="sixth heartbeats with tb_fb_error above 0 at most the fifth's plus 2"),
                met=s["met"])


def evaluate(meta, B, S, rows6, starts6, rows5, starts5, trades6, items, pairs=None, fifth_folder="paper_spot_r5",
             sixth_folder="paper_spot_tw", start=None, end=None, read_as_is=False, min_bids=MIN_BIDS, min_pairs=MIN_PAIRS):
    """meta: two_books.json; B: item7_bids.csv; S: side_by_side.csv (data frames); rows6, rows5: data-quality rows of the
    heartbeats of the sixth and the fifth book in the period (log_data); starts6, starts5: their first stepped minutes;
    trades6: the sixth book's step_s.trades statistics (log_data); pairs: ps.load_workers_pairs of --pairs."""
    start = start if start is not None else meta["period"]["start"]
    end = end if end is not None else meta["period"]["end"]
    if items not in ("pass", "fail"):
        raise ValueError(f"items 1 to 5 must be pass or fail, not {items}")
    coins = guard(meta, fifth_folder, sixth_folder, start, end)
    c5, c6 = p3.book_counts(B, S, FIFTH, coins), p3.book_counts(B, S, SIXTH, coins)
    period_ok = c5["n"] >= min_bids and c6["n"] >= min_bids
    P3 = part3(pairs, start, end, min_pairs)
    wm = P3.pop("_wm")
    P4 = dict(decisions=decisions(c6, c5), items_1_5=dict(value=items, met=items == "pass"),
              requests=requests(rows6, starts6, rows5, starts5), stops=stops(rows6, rows5))
    m1 = ps.measure1(rows6, rows5)
    reported = dict(
        trades_pass_medians_of_the_pairs=P3["reported"],
        data_step=dict(common_heartbeat_times=m1["pairs"], sixth_median_s=_f(m1["paired_fifth"]),
                       fifth_median_s=_f(m1["paired_other"]), sixth_own_median_s=_f(m1["median"]),
                       sixth_heartbeats=m1["n"], decides="nothing"),
        step_s_trades=dict(heartbeats=trades6["n"], median_of_medians_s=_f(trades6["median"]),
                           largest_max_s=_f(trades6["max"]), decides="nothing"))
    holds = {"part3.1_step": P3["step"]["met"], "part3.2_slow_minutes": P3["slow"]["met"], "part3.3_pace": P3["pace"]["met"],
             "part3.4_rows": P3["rows"]["met"], "part4.1_decisions": P4["decisions"]["met"],
             "part4.2_items_1_5": P4["items_1_5"]["met"], "part4.3_requests": P4["requests"]["met"],
             "part4.4_stops": P4["stops"]["met"]}
    if (not period_ok or not P3["complete"]) and not read_as_is:
        verdict = None
    else:
        verdict = "pass" if all(holds.values()) else "fail"
    res = dict(period=dict(start=str(pd.Timestamp(start)), end=str(pd.Timestamp(end))), books=meta["books"],
               label_mapping={"main": f"fifth book ({fifth_folder})", "tb": f"sixth book ({sixth_folder})"},
               minutes=meta.get("minutes"), coins=coins,
               condition=dict(new_bids_sixth=c6["n"], new_bids_fifth=c5["n"], needed=min_bids, met=period_ok,
                              read_as_is=bool(read_as_is), part3_complete=P3["complete"]),
               counts=dict(sixth=c6, fifth=c5), part3=P3, part4=P4, reported=reported, holds=holds, verdict=verdict)
    res["_pairs"] = pair_rows(pairs or [], wm)
    return res


def pair_rows(pairs, wm):
    """The pair files of the period (and the added ones) for the markdown: [(pair, in the period, used)]."""
    used = {p["file"] for p in wm["used"]}
    inside = {p["file"] for p in wm["files"]}
    return [(p, p["file"] in inside, p["file"] in used) for p in pairs if p["file"] in inside or p["file"] in used]


# ---------------------------------------------------------------- output
def pct(x):
    return "n/a" if x is None else f"{100 * x:.3f}%"


def sx(x):
    return "n/a" if x is None else f"{x:.3f} s"


def mk(ok):
    return "met" if ok else "not met"


def tx(r, k, unit=" s"):
    return "n/a" if not r or r.get(k) is None else f"{r[k]}{unit}"


def to_md(res):
    c = res["condition"]
    P3, P4, R = res["part3"], res["part4"], res["reported"]
    L = ["# Parts 3 and 4: the trades-workers test (sixth paper book against the fifth, all 17 coins, common minutes)", "",
         f"Period: {res['period']['start']} to {res['period']['end']} UTC (both minutes included).",
         f"Labels in the reconciliation folder: main = {res['label_mapping']['main']}, tb = {res['label_mapping']['tb']}."]
    if res.get("minutes"):
        m = res["minutes"]
        L.append(f"Decision minutes: fifth book {m['main']}, sixth book {m['tb']}; common minutes {m['common']}.")
    L += ["", f"Period condition: {c['new_bids_sixth']} new bids in the sixth book and {c['new_bids_fifth']} in the fifth, "
              f"{c['needed']} needed in each: {mk(c['met'])}."]
    if not c["met"]:
        L += ["", "**PERIOD NOT COMPLETE**" + (" (read as is, as the plan allows)" if c["read_as_is"] else "; no verdict")]
    if not c["part3_complete"]:
        L += ["", f"PART 3 NOT COMPLETE: {P3['step']['pairs']} of {P3['step']['needed']} pairs count; the pair jobs go on and the "
                  "read waits"]
        if c["read_as_is"]:
            L += ["", "Read as is: clauses 1, 2 and 4 of Part 3 need 8 pairs and are not met."]
    if P3["added"]:
        L += ["", f"Part 3 pairs: {P3['in_period']} started in the period and {P3['added']} were added from after it (fewer than "
                  f"{P3['step']['needed']} counted in the period); the last pair used started {P3['last_used_start']} UTC. The "
                  "pace clause and Part 4 are read on the period itself."]
    L += ["", "## Part 3, the same-machine pairs (one worker against three)", ""]
    pr = res.get("_pairs")
    if pr:
        rows = [[p["file"], p["order"] or "n/a", tx(p["one"], "median"), tx(p["three"], "median"),
                 "n/a" if p["diff"] is None else f"{float(p['diff']):.2f} s", tx(p["one"], "longest"), tx(p["three"], "longest"),
                 tx(p["one"], "fb", ""), tx(p["three"], "fb", ""), tx(p["three"], "peak", ""),
                 ("counts" if p["counts"] else "does not count: " + (p["why"] or "")) + ("; used" if used else "")
                 + ("" if inside else "; after the period")] for p, inside, used in pr]
        L += ["| file | order | step one | step three | three minus one | longest one | longest three | fallbacks one | "
              "fallbacks three | peak three | result |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        L += ["| " + " | ".join(r) + " |" for r in rows] + [""]
    s, sl, pc, rw = P3["step"], P3["slow"], P3["pace"], P3["rows"]
    L += ["| clause | value | rule | result |", "|---|---|---|---|",
          f"| 1. the step | median {sx(s['median_s'])} over {s['pairs']} pairs | at most -0.200 s, at least {s['needed']} pairs | "
          f"{mk(s['met'])} |",
          f"| 2. the slow minutes | fallbacks {sl['fallbacks_three']} with three, {sl['fallbacks_one']} with one; median of the "
          f"longest pass, three minus one, {sx(sl['longest_median_s'])} | fallbacks no more with three; median at most 0 | "
          f"{mk(sl['met'])} |",
          f"| 3. the pace | {pc['files_in_period']} files in the period; most trades requests in one second "
          f"{pc['peak_max'] if pc['peak_max'] is not None else 'n/a'}; refused or limited: {len(pc['refused_or_limited'])}; "
          f"above 8: {len(pc['over_peak'])}; unreadable: {len(pc['unreadable'])} | no three-worker run above 8 in any file, "
          f"none refused or limited, every file readable | {mk(pc['met'])} |",
          f"| 4. the rows | three {rw['differ_three']} of {rw['compared_three']} = {pct(rw['share_three'])}, one "
          f"{rw['differ_one']} of {rw['compared_one']} = {pct(rw['share_one'])} | three's share no higher than one's | "
          f"{mk(rw['met'])} |", ""]
    for key, what in (("over_peak", "above 8 trades requests in one second"), ("refused_or_limited", "refused or limited"),
                      ("unreadable", "could not be read")):
        if pc[key]:
            L += [f"Files with a three-worker run {what}: " + ", ".join(pc[key]) if key != "unreadable"
                  else "Files that could not be read: " + ", ".join(pc[key]), ""]
    L += [f"Part 3: {mk(P3['met'])}.", ""]
    d = P4["decisions"]
    L += ["## Part 4, measure 1: decisions against the research", "",
          "| clause | sixth book | fifth book | rule | result |", "|---|---|---|---|---|"]
    for key, name in (("wrong_side_vs_fifth", "wrong side against the fifth book"), ("wrong_side_cap", "wrong side, cap"),
                      ("matched", "matched"), ("level", "level more than 5 bp")):
        x = d[key]
        L.append(f"| {name} | {x['sixth']} = {pct(x['sixth_share'])} | {x.get('fifth', '-')}"
                 + (f" = {pct(x['fifth_share'])}" if "fifth" in x else "") + f" | {x['rule']} | {mk(x['met'])} |")
    L += ["", f"Part 4, measure 1: {mk(d['met'])}.", "",
          "## Part 4, measure 2: items 1 to 5 of the sixth book", "",
          f"Read by the owner from the status report on the cut log: {P4['items_1_5']['value']}. "
          f"Measure 2: {mk(P4['items_1_5']['met'])}.", ""]
    q = P4["requests"]
    L += ["## Part 4, measure 3: requests inside a step", ""]
    if not q["counters_present"]:
        L += ["No heartbeat of the sixth book in the period carries the counters: not met.", ""]
    else:
        L += ["| clause | value | rule | result |", "|---|---|---|---|",
              f"| failed requests | {q['failed']} of {q['requests']} = {pct(q['failed_share'])} | "
              f"{q['failed_clause']['rule']} | {mk(q['failed_clause']['met'])} |",
              f"| requests inside a step | {q['in_step']} of {q['coin_minutes']:,.0f} coin-minutes = {pct(q['in_step_share'])} "
              f"({q['left_out_first_steps']} left out as the first step after a start) | {q['in_step_clause']['rule']} | "
              f"{mk(q['in_step_clause']['met'])} |"]
    a = q["against_fifth"]
    L += [f"| in-step share against the fifth book's | sixth {pct(a['sixth_share'])}, fifth {pct(a['fifth_share'])}, over "
          f"{a['common_heartbeat_times']} heartbeat times at which both books have a heartbeat | {a['rule']} | "
          f"{mk(a['met'])} |" if q["counters_present"] else
          f"In-step share against the fifth book's, over {a['common_heartbeat_times']} common heartbeat times: {mk(a['met'])}.",
          "", f"Measure 3: {mk(q['met'])}.", ""]
    t = P4["stops"]
    L += ["## Part 4, measure 4: stops", "",
          "| clause | value | rule | result |", "|---|---|---|---|",
          f"| rate-limit stops (tb_fb_limited above 0) | sixth {t['limited_sixth']} heartbeats, fifth {t['limited_fifth']}; sixth "
          f"only: {len(t['limited_sixth_alone'])}" + (" (" + ", ".join(t['limited_sixth_alone']) + ")" if t['limited_sixth_alone'] else "")
          + f" | {t['limited_clause']['rule']} | {mk(t['limited_clause']['met'])} |",
          f"| request errors (tb_fb_error above 0) | sixth {t['errors_sixth']} heartbeats, fifth {t['errors_fifth']} (at most "
          f"{t['allowed_errors']}) | {t['error_clause']['rule']} | {mk(t['error_clause']['met'])} |", "",
          f"Measure 4: {mk(t['met'])}.", ""]
    ds, ts, tp = R["data_step"], R["step_s_trades"], R["trades_pass_medians_of_the_pairs"]
    L += ["## Reported, deciding nothing", "",
          f"- Data-step medians over the {ds['common_heartbeat_times']} heartbeat times at which both books have a heartbeat: sixth "
          f"{sx(ds['sixth_median_s'])}, fifth {sx(ds['fifth_median_s'])} (the runners differ, so the pairs decide the step).",
          f"- The sixth book's own heartbeat entry step_s.trades (the trades pass's duration), over {ts['heartbeats']} heartbeats: "
          f"median of the half-hour medians {sx(ts['median_of_medians_s'])}, largest maximum {sx(ts['largest_max_s'])}.",
          f"- The trades pass's median duration in the pairs used: three {sx(tp['median_three_s'])}, one {sx(tp['median_one_s'])} "
          "(median over the pairs)."]
    for p in tp["pairs"]:
        L.append(f"  - {p['file']} (started {p['start']}): one {p['trades_pass_median_one']} s, three {p['trades_pass_median_three']} s")
    L += ["", "| measure | holds |", "|---|---|"] + [f"| {k} | {'yes' if v else 'no'} |" for k, v in res["holds"].items()] + [""]
    if res["verdict"] is None:
        why = " and ".join(([] if c["met"] else ["period not complete"]) + ([] if c["part3_complete"] else ["part 3 not complete"]))
        L += [f"**Trades workers: no verdict ({why})**", ""]
    else:
        L += [f"**Trades workers: {res['verdict']}**", ""]
    L += ["Rule in plain words: every clause of Parts 3 and 4 must hold. Part 3, over at least 8 same-machine pairs (those that "
          "start in the period; if fewer than 8 count there, the later pairs are added oldest first up to the one that makes 8, "
          "and the verdict waits for them): the median of three's data step minus one's at most -0.2 s; budget fallbacks with "
          "three no more than with one and the median of the longest pass, three minus one, at most 0; in every pair file of the "
          "period no three-worker run above 8 trades requests in a second and none refused or limited; the share of rows that "
          "differ from the venue no higher with three. Part 4: against the research, wrong-side share at most the fifth book's "
          "plus 2.0 points and at most 5%, matched share at least the fifth's minus 3.0 points, under 5% of bids more than 5 bp "
          "from the level; items 1 to 5; failed requests at most 1% and in-step requests at most 2% of coin-minutes and no higher "
          "a share than the fifth book's; no rate-limit stop in the sixth book unless the fifth has one at the same heartbeat, "
          "and its error half hours at most the fifth's plus 2. Shares are compared exactly on the counts. A PASS puts "
          "trades_workers 3 into the release config; it does not change `main` by itself.", ""]
    return "\n".join(L)


def public(res):
    return {k: v for k, v in res.items() if not k.startswith("_")}


def write(out_dir, res):
    os.makedirs(out_dir, exist_ok=True)
    json.dump(public(res), open(os.path.join(out_dir, "trades_workers_rule.json"), "w"), indent=1)
    open(os.path.join(out_dir, "trades_workers_rule.md"), "w").write(to_md(res))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--sixth", required=True)
    ap.add_argument("--fifth", required=True)
    ap.add_argument("--items-1-5", dest="items", choices=["pass", "fail"], required=True)
    ap.add_argument("--pairs", default=PAIRS_DEFAULT)
    ap.add_argument("--out")
    ap.add_argument("--read-as-is", action="store_true")
    ap.add_argument("--min-bids", type=int, default=MIN_BIDS)
    a = ap.parse_args(argv)
    meta = json.load(open(os.path.join(a.dir, "two_books.json")))
    B = pd.read_csv(os.path.join(a.dir, "item7_bids.csv"))
    S = pd.read_csv(os.path.join(a.dir, "side_by_side.csv"))
    rows6, starts6, trades6 = log_data(a.sixth, a.start, a.end)
    rows5, starts5, _ = log_data(a.fifth, a.start, a.end)
    res = evaluate(meta, B, S, rows6, starts6, rows5, starts5, trades6, a.items, ps.load_workers_pairs(a.pairs),
                   os.path.basename(os.path.normpath(a.fifth)), os.path.basename(os.path.normpath(a.sixth)),
                   a.start, a.end, a.read_as_is, a.min_bids)
    write(a.out or a.dir, res)
    print(to_md(res))


if __name__ == "__main__":
    main()
