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
  --alt     the folder of the alternating-minute job files alt_*.json (default reports/owner/workers_alt, written by
            scripts/owner/workers_alt/run_alt.py).
  --now     the time the read is made (UTC, default the clock); only the 14 days of Part 3 are judged against it.
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

Part 3, alternating minutes (the files alt_*.json of --alt; a job counts when its file says "counts" true and its steps give at
  least 20 timed steps per arm). This is paper_status.alt_select and alt_measure themselves, so the status report and this rule
  choose the same jobs. Selection: the counting jobs sorted by start; all those started from the first job up to --end (the
  end minute included) are taken; then, while fewer than 8 jobs are used OR the one-worker steps of the used jobs hold fewer
  than 30 slow passes (pass above 6.0 s), the next counting job is added if it started no later than 14 days after the first
  job's start; adding stops when both hold. The script says how many jobs started in the period and how many were added.
  Both hold: Part 3 is complete. They do not hold and the 14 days (from the first job's start) have not passed at --now: it
  prints
      PART 3 NOT COMPLETE: <jobs> of 8 jobs, <slow> of 30 slow one-worker passes; the jobs go on and the read waits
  and gives no verdict unless --read-as-is is passed, which then counts clauses 1, 2 and 4 as not met. They do not hold and the
  14 days have passed: Part 3 is complete, clause 2 is not met ("the gain is not shown"). Over all steps of the used jobs:
  1. no harm: the median pass_s with three is at most the median with one plus 0.05 s (exact from the printed texts; an even
     count: the mean of the middle two);
  2. a gain in slow minutes: the one-worker steps hold at least 30 slow passes, slow3 / steps3 is at most (slow1 / steps1) / 2
     (cross-multiplied), and budget fallbacks with three are no more than with one;
  3. the pace, over ALL alt files that started from the first job on up to the last used job's start, counting or not: no
     three-worker step with a peak above 8, none limited, none refused; a file that cannot be read is listed and makes the
     clause not met (a file with no known start is taken as inside the range);
  4. the rows, over the used jobs whose row comparison is complete: differ3 / compared3 is at most differ1 / compared1 + 1/100
     (cross-multiplied on integers; a zero denominator on either side means not met).
  Reported, deciding nothing: both arms' median and mean pass, their difference, and "first version of the plan asked for a 0.2 s
  gain at the median over half-hour pairs"; the steps and slow passes of each arm per job.
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
Reported, not ruled on: both books' data-step medians over the common heartbeat times, the sixth book's own heartbeat entry
  step_s.trades, and the Part 3 figures above.

Command line:
  python scripts/owner/trades_workers/rule.py --dir DIR --start 2026-..T..:.. --end 2026-..T..:.. \\
      --sixth paper_spot_tw --fifth paper_spot_r5 --items-1-5 pass|fail [--alt DIR] [--now TIME] [--out DIR] [--read-as-is]
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
MIN_JOBS = ps.ALT_MIN_JOBS
MIN_SLOW = ps.ALT_MIN_SLOW
ALT_DEFAULT = ps.TW_ALT_DIR
FIFTH, SIXTH = "main", "tb"         # the labels in the folder: main = fifth book (control), tb = sixth book
GROUP = p3.GROUP
N_COINS = p3.N_COINS
GAIN_MARGIN = ps.ALT_GAIN_MARGIN    # 1/20 s
ROWS_MARGIN = ps.ALT_ROWS_MARGIN    # 1/100
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
def _x(f):
    return None if f is None else str(f)


def part3(jobs, start, end, now=None):
    sel = ps.alt_select(jobs or [], p3.when(end), now)
    wm = ps.alt_measure(jobs or [], sel)
    d3, c3 = wm["rows3"]
    d1, c1 = wm["rows1"]
    n1, n3 = wm["steps"][1], wm["steps"][3]
    step = clause(wm["step_met"], steps_three=n3, steps_one=n1, median_three_s=_f(wm["median"][3]), median_one_s=_f(wm["median"][1]),
                  median_three_exact=_x(wm["median"][3]), median_one_exact=_x(wm["median"][1]), margin_s=float(GAIN_MARGIN),
                  rule="median pass with three at most the median with one plus 0.05 s")
    gain = clause(wm["gain_met"], slow_one=wm["slow"][1], steps_one=n1, slow_three=wm["slow"][3], steps_three=n3,
                  share_one=share(wm["slow"][1], n1), share_three=share(wm["slow"][3], n3), fallbacks_three=wm["fb"][3],
                  fallbacks_one=wm["fb"][1], slow_needed=MIN_SLOW, gain_not_shown=sel["gain_not_shown"],
                  rule="at least 30 slow one-worker passes (above 6.0 s); three's slow share at most half of one's; "
                       "budget fallbacks with three no more than with one")
    pace = clause(wm["pace_met"], files=len(wm["files"]), peak_max=wm["peak_max"], over_peak=list(wm["peak_over"]),
                  refused_or_limited=list(wm["stopped"]), unreadable=list(wm["unreadable"]),
                  rule="no three-worker step above 8 trades requests in one second, none limited or refused, every file readable")
    rows = clause(wm["rows_met"], differ_three=d3, compared_three=c3, differ_one=d1, compared_one=c1, jobs=wm["rows_jobs"],
                  share_three=share(d3, c3), share_one=share(d1, c1),
                  rule="rows differing from the venue: three's share at most one's plus 1 point (cross-multiplied)")
    per_job = []
    for j in sel["used"]:
        st = {w: [x for x in j["steps"] if x["workers"] == w and x["pass"] is not None] for w in (1, 3)}
        per_job.append(dict(file=j["file"], start=j["start"].strftime("%Y-%m-%dT%H:%M:%SZ") if j["start"] else None,
                            first=j["first"], steps_one=len(st[1]), steps_three=len(st[3]),
                            slow_one=ps.slow_count(j, 1), slow_three=ps.slow_count(j, 3)))
    reported = dict(median_one_s=_f(wm["median"][1]), median_three_s=_f(wm["median"][3]), mean_one_s=_f(wm["mean"][1]),
                    mean_three_s=_f(wm["mean"][3]), diff_median_s=_f(wm["diff_median"]), diff_mean_s=_f(wm["diff_mean"]),
                    note="first version of the plan asked for a 0.2 s gain at the median over half-hour pairs",
                    jobs=per_job, decides="nothing")
    fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None      # noqa: E731
    return dict(step=step, gain=gain, pace=pace, rows=rows, reported=reported, complete=sel["complete"], holds=sel["holds"],
                wait=sel["wait"], gain_not_shown=sel["gain_not_shown"], jobs=len(sel["used"]), jobs_needed=MIN_JOBS,
                slow_one=wm["slow"][1], slow_needed=MIN_SLOW, in_period=sel["in_period"], added=sel["added"],
                job_files=[j["file"] for j in sel["used"]], first_job_start=fmt(sel["first_start"]),
                days_end=fmt(sel["deadline"]), last_used_start=fmt(sel["last_start"]),
                met=step["met"] and gain["met"] and pace["met"] and rows["met"], _sel=sel, _wm=wm)


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


def evaluate(meta, B, S, rows6, starts6, rows5, starts5, trades6, items, jobs=None, fifth_folder="paper_spot_r5",
             sixth_folder="paper_spot_tw", start=None, end=None, read_as_is=False, min_bids=MIN_BIDS, now=None):
    """meta: two_books.json; B: item7_bids.csv; S: side_by_side.csv (data frames); rows6, rows5: data-quality rows of the
    heartbeats of the sixth and the fifth book in the period (log_data); starts6, starts5: their first stepped minutes;
    trades6: the sixth book's step_s.trades statistics (log_data); jobs: ps.load_alt_jobs of --alt; now: the time of the read."""
    start = start if start is not None else meta["period"]["start"]
    end = end if end is not None else meta["period"]["end"]
    if items not in ("pass", "fail"):
        raise ValueError(f"items 1 to 5 must be pass or fail, not {items}")
    coins = guard(meta, fifth_folder, sixth_folder, start, end)
    c5, c6 = p3.book_counts(B, S, FIFTH, coins), p3.book_counts(B, S, SIXTH, coins)
    period_ok = c5["n"] >= min_bids and c6["n"] >= min_bids
    P3 = part3(jobs, start, end, now)
    sel, wm = P3.pop("_sel"), P3.pop("_wm")
    if not P3["complete"] and read_as_is:
        for k in ("step", "gain", "rows"):
            P3[k]["met"] = False
        P3["met"] = False
    P4 = dict(decisions=decisions(c6, c5), items_1_5=dict(value=items, met=items == "pass"),
              requests=requests(rows6, starts6, rows5, starts5), stops=stops(rows6, rows5))
    m1 = ps.measure1(rows6, rows5)
    reported = dict(
        part3=P3["reported"],
        data_step=dict(common_heartbeat_times=m1["pairs"], sixth_median_s=_f(m1["paired_fifth"]),
                       fifth_median_s=_f(m1["paired_other"]), sixth_own_median_s=_f(m1["median"]),
                       sixth_heartbeats=m1["n"], decides="nothing"),
        step_s_trades=dict(heartbeats=trades6["n"], median_of_medians_s=_f(trades6["median"]),
                           largest_max_s=_f(trades6["max"]), decides="nothing"))
    holds = {"part3.1_no_harm": P3["step"]["met"], "part3.2_gain": P3["gain"]["met"], "part3.3_pace": P3["pace"]["met"],
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
    return res


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
        L += ["", f"PART 3 NOT COMPLETE: {P3['jobs']} of {P3['jobs_needed']} jobs, {P3['slow_one']} of {P3['slow_needed']} slow "
                  "one-worker passes; the jobs go on and the read waits"]
        if c["read_as_is"]:
            L += ["", "Read as is: clauses 1, 2 and 4 of Part 3 need 8 jobs and 30 slow one-worker passes and are not met."]
    if P3["gain_not_shown"]:
        L += ["", f"Part 3: the 14 days from the first job ({P3['first_job_start']}) are over and there are {P3['jobs']} jobs and "
                  f"{P3['slow_one']} slow one-worker passes: Part 3 is complete, clause 2 is not met, the gain is not shown."]
    if P3["added"]:
        L += ["", f"Part 3 jobs: {P3['in_period']} started in the period and {P3['added']} were added from after it; the last job "
                  f"used started {P3['last_used_start']} UTC. Part 4 is read on the period itself."]
    L += ["", "## Part 3, alternating minutes (one worker against three)", ""]
    if R["part3"]["jobs"]:
        L += ["| job | start | first arm | steps one | steps three | slow passes one | slow passes three |", "|---|---|---|---|---|---|---|"]
        L += [f"| {j['file']} | {j['start']} | {j['first'] or 'n/a'} | {j['steps_one']} | {j['steps_three']} | {j['slow_one']} | "
              f"{j['slow_three']} |" for j in R["part3"]["jobs"]] + [""]
    s, g, pc, rw = P3["step"], P3["gain"], P3["pace"], P3["rows"]
    L += ["| clause | value | rule | result |", "|---|---|---|---|",
          f"| 1. no harm | median pass three {sx(s['median_three_s'])} ({s['steps_three']} steps), one {sx(s['median_one_s'])} "
          f"({s['steps_one']} steps) | three at most one plus 0.050 s | {mk(s['met'])} |",
          f"| 2. a gain in slow minutes | slow passes (above 6.0 s) one {g['slow_one']} of {g['steps_one']} = {pct(g['share_one'])}, "
          f"three {g['slow_three']} of {g['steps_three']} = {pct(g['share_three'])}; fallbacks three {g['fallbacks_three']}, one "
          f"{g['fallbacks_one']}" + ("; the gain is not shown" if g["gain_not_shown"] else "")
          + f" | at least 30 slow one-worker passes; three's share at most half of one's; fallbacks no more with three | "
          f"{mk(g['met'])} |",
          f"| 3. the pace | {pc['files']} files; most trades requests in one second "
          f"{pc['peak_max'] if pc['peak_max'] is not None else 'n/a'}; above 8: {len(pc['over_peak'])}; limited or refused: "
          f"{len(pc['refused_or_limited'])}; unreadable: {len(pc['unreadable'])} | no three-worker step above 8 in any file, none "
          f"limited or refused, every file readable | {mk(pc['met'])} |",
          f"| 4. the rows | three {rw['differ_three']} of {rw['compared_three']} = {pct(rw['share_three'])}, one "
          f"{rw['differ_one']} of {rw['compared_one']} = {pct(rw['share_one'])}, over {rw['jobs']} jobs with a complete comparison "
          f"| three's share at most one's plus 1 point | {mk(rw['met'])} |", ""]
    for key, what in (("over_peak", "A file with a three-worker step above 8 trades requests in one second"),
                      ("refused_or_limited", "A file with a three-worker step limited or refused"),
                      ("unreadable", "A file that could not be read")):
        if pc[key]:
            L += [what + ": " + ", ".join(pc[key]), ""]
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
    ds, ts, tp = R["data_step"], R["step_s_trades"], R["part3"]
    L += ["## Reported, deciding nothing", "",
          f"- Data-step medians over the {ds['common_heartbeat_times']} heartbeat times at which both books have a heartbeat: sixth "
          f"{sx(ds['sixth_median_s'])}, fifth {sx(ds['fifth_median_s'])} (the runners differ; Part 3 decides the step).",
          f"- The sixth book's own heartbeat entry step_s.trades (the trades pass's duration), over {ts['heartbeats']} heartbeats: "
          f"median of the half-hour medians {sx(ts['median_of_medians_s'])}, largest maximum {sx(ts['largest_max_s'])}.",
          f"- Part 3, pass duration over all steps of the jobs used: median one {sx(tp['median_one_s'])}, three "
          f"{sx(tp['median_three_s'])}, difference {sx(tp['diff_median_s'])}; mean one {sx(tp['mean_one_s'])}, three "
          f"{sx(tp['mean_three_s'])}, difference {sx(tp['diff_mean_s'])}.",
          f"- {tp['note']}."]
    L += ["", "| measure | holds |", "|---|---|"] + [f"| {k} | {'yes' if v else 'no'} |" for k, v in res["holds"].items()] + [""]
    if res["verdict"] is None:
        why = " and ".join(([] if c["met"] else ["period not complete"]) + ([] if c["part3_complete"] else ["part 3 not complete"]))
        L += [f"**Trades workers: no verdict ({why})**", ""]
    else:
        L += [f"**Trades workers: {res['verdict']}**", ""]
    L += ["Rule in plain words: every clause of Parts 3 and 4 must hold. Part 3, alternating minutes, over the jobs started in "
          "the period (if there are fewer than 8 jobs or fewer than 30 slow one-worker passes, the next jobs are added oldest "
          "first, up to 14 days from the first job, and the verdict waits for them): the median pass with three at most the "
          "median with one plus 0.05 s; at least 30 slow one-worker passes, three's share of slow passes at most half of one's, "
          "budget fallbacks with three no more than with one; in every alt file from the first job to the last one used no "
          "three-worker step above 8 trades requests in a second and none limited or refused; the share of rows that differ from "
          "the venue at most one point higher with three. Part 4: against the research, wrong-side share at most the fifth "
          "book's plus 2.0 points and at most 5%, matched share at least the fifth's minus 3.0 points, under 5% of bids more than "
          "5 bp from the level; items 1 to 5; failed requests at most 1% and in-step requests at most 2% of coin-minutes and no "
          "higher a share than the fifth book's; no rate-limit stop in the sixth book unless the fifth has one at the same "
          "heartbeat, and its error half hours at most the fifth's plus 2. Shares are compared exactly on the counts. A PASS puts "
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
    ap.add_argument("--alt", default=ALT_DEFAULT)
    ap.add_argument("--now")
    ap.add_argument("--out")
    ap.add_argument("--read-as-is", action="store_true")
    ap.add_argument("--min-bids", type=int, default=MIN_BIDS)
    a = ap.parse_args(argv)
    meta = json.load(open(os.path.join(a.dir, "two_books.json")))
    B = pd.read_csv(os.path.join(a.dir, "item7_bids.csv"))
    S = pd.read_csv(os.path.join(a.dir, "side_by_side.csv"))
    rows6, starts6, trades6 = log_data(a.sixth, a.start, a.end)
    rows5, starts5, _ = log_data(a.fifth, a.start, a.end)
    res = evaluate(meta, B, S, rows6, starts6, rows5, starts5, trades6, a.items, ps.load_alt_jobs(a.alt),
                   os.path.basename(os.path.normpath(a.fifth)), os.path.basename(os.path.normpath(a.sixth)),
                   a.start, a.end, a.read_as_is, a.min_bids, p3.when(a.now) if a.now else None)
    write(a.out or a.dir, res)
    print(to_md(res))


if __name__ == "__main__":
    main()
