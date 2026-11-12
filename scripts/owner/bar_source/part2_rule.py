"""Part 2 of reports/owner/bar_source_prereg.md ("Part 2: forward, a fourth paper book" and "Decision rule"), as code.
Semantics fixed by the owner's brief; do not improve on them.

Input: a folder written by scripts/owner/reconcile/two_books.py run with --main paper_spot_tb --third paper_spot_t18.
In such a folder the label "main" means the THIRD paper book and the label "tb" means the FOURTH paper book.
Everything is on the minutes both books were live (what the files already hold), for the twelve coins
(groups["candle path"] in two_books.json).

  Guard: books must be main == paper_spot_tb and tb == paper_spot_t18, else an error and no verdict.
  c1: the period's end minus start plus one minute is at least 4,320 minutes (three full days together).
  c2: each book has at least 300 rows in item7_bids.csv on the twelve (rows with a missing score or level count).
  Measure 1, wrong-side share: among a book's bids with res_score present, k = res_other_side true, n = the count.
    PASS if the fourth book's share is strictly lower than the third's: k4 * n3 < k3 * n4. Else FAIL.
  Measure 2, matched share: m = research_matched, r = research_new_bids_ex_blocked (side_by_side.csv, candle path).
    PASS if m4 * r3 >= m3 * r4. Else FAIL. WAIT if r is 0 for either book.
  Measure 3, level (fourth book): among its bids with err_bp present, k = abs(err_bp) > 5, n = the count.
    PASS if 20 * k < n. Else FAIL. The third book's k / n is shown for the record and carries no verdict.
  Items 1 to 5 of the fourth book are read from the status report by the owner: --items-1-5 pass, fail or unread.
  If c1 or c2 is not met every measure is WAIT and so is the overall verdict. Otherwise overall: FAIL if any measure
  is FAIL or items 1 to 5 is fail; else WAIT if any measure is WAIT or items 1 to 5 is unread; else PASS.
  Consistency checks (an error if violated): per book, measure 1's k and n equal side_by_side.csv's m2_score_error
  n_other_side and n; measure 3's n equals m1_level_error n.

Command line: python scripts/owner/bar_source/part2_rule.py --dir reports/owner/reconcile_tb/DIR
  [--items-1-5 pass|fail|unread] [--min-bids 300] [--min-minutes 4320]
  reads <dir>/two_books.json, <dir>/item7_bids.csv, <dir>/side_by_side.csv; writes <dir>/part2_rule.json and
  <dir>/part2_rule.md and prints the markdown.
"""
import argparse
import json
import os

import pandas as pd

MIN_BIDS = 300
MIN_MINUTES = 4320
LIMIT_BP = 5.0
THIRD, FOURTH = "main", "tb"            # the labels in the folder: main = third book, tb = fourth book
GROUP = "candle path"
UNREAD_TEXT = "read reports/owner/PAPER_STATUS.md"


def guard(meta):
    books = meta.get("books", {})
    if books.get("main") != "paper_spot_tb" or books.get("tb") != "paper_spot_t18":
        raise ValueError("this folder is not a third-book / fourth-book reconciliation: books must be "
                         f"main = paper_spot_tb and tb = paper_spot_t18, found {books}")


def minutes_together(period):
    """Minutes from start to end, both included."""
    d = pd.Timestamp(period["end"]) - pd.Timestamp(period["start"])
    return int(d / pd.Timedelta(minutes=1)) + 1


def to_int(x, what):
    """An integer written as a float; anything else is an error."""
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


def twelve_rows(B, book, twelve):
    return B[(B["book"] == book) & (B["coin"].isin(twelve))]


def counts(A):
    """bids, (k1, n1) wrong-side, (k3, n3) level on one book's rows on the twelve."""
    sc = A[A["res_score"].notna()]
    lv = A[A["err_bp"].notna()]
    other = sc["res_other_side"].astype(str).str.lower() == "true"
    return (int(len(A)), (int(other.sum()), int(len(sc))),
            (int((lv["err_bp"].abs() > LIMIT_BP).sum()), int(len(lv))))


def v_wrong_side(k3, n3, k4, n4):
    if n3 == 0 or n4 == 0:
        return "WAIT"
    return "PASS" if k4 * n3 < k3 * n4 else "FAIL"


def v_matched(m3, r3, m4, r4):
    if r3 == 0 or r4 == 0:
        return "WAIT"
    return "PASS" if m4 * r3 >= m3 * r4 else "FAIL"


def v_level(k4, n4):
    if n4 == 0:
        return "WAIT"
    return "PASS" if 20 * k4 < n4 else "FAIL"


def overall(verdicts, items):
    if "FAIL" in verdicts or items == "fail":
        return "FAIL"
    if "WAIT" in verdicts or items == "unread":
        return "WAIT"
    return "PASS"


def share(k, n):
    return (k / n) if n else None


def evaluate(meta, B, S, items="unread", min_bids=MIN_BIDS, min_minutes=MIN_MINUTES):
    """meta: two_books.json; B: item7_bids.csv; S: side_by_side.csv (as data frames)."""
    guard(meta)
    if items not in ("pass", "fail", "unread"):
        raise ValueError(f"items 1 to 5 must be pass, fail or unread, not {items}")
    twelve = meta["groups"][GROUP]
    bids, m1, m3 = {}, {}, {}
    for b in (THIRD, FOURTH):
        bids[b], m1[b], m3[b] = counts(twelve_rows(B, b, twelve))
        if m1[b][0] != side_value(S, "m2_score_error", "n_other_side", b) \
                or m1[b][1] != side_value(S, "m2_score_error", "n", b):
            raise ValueError(f"inconsistent folder: wrong-side counts of the {b} book from item7_bids.csv "
                             f"({m1[b][0]} of {m1[b][1]}) differ from side_by_side.csv")
        if m3[b][1] != side_value(S, "m1_level_error", "n", b):
            raise ValueError(f"inconsistent folder: level count of the {b} book from item7_bids.csv "
                             f"({m3[b][1]}) differs from side_by_side.csv")
    mr = {b: (side_value(S, "m3_bids", "research_matched", b),
              side_value(S, "m3_bids", "research_new_bids_ex_blocked", b)) for b in (THIRD, FOURTH)}
    minutes = minutes_together(meta["period"])
    c1 = minutes >= min_minutes
    c2 = bids[THIRD] >= min_bids and bids[FOURTH] >= min_bids
    raw = (v_wrong_side(m1[THIRD][0], m1[THIRD][1], m1[FOURTH][0], m1[FOURTH][1]),
           v_matched(mr[THIRD][0], mr[THIRD][1], mr[FOURTH][0], mr[FOURTH][1]),
           v_level(m3[FOURTH][0], m3[FOURTH][1]))
    ok = c1 and c2
    v = tuple(x if ok else "WAIT" for x in raw)
    items_v = {"pass": "PASS", "fail": "FAIL", "unread": "WAIT"}[items]
    res = dict(period=meta["period"], minutes=meta.get("minutes"), books=meta["books"],
               min_bids=min_bids, min_minutes=min_minutes,
               conditions=dict(
                   c1_minutes_together=dict(value=minutes, needed=min_minutes, met=c1),
                   c2_bids_on_the_twelve=dict(third=bids[THIRD], fourth=bids[FOURTH], needed=min_bids, met=c2)))
    res["measures"] = dict(
        wrong_side=dict(label="wrong-side share (new bids whose research score is at or below the threshold)",
                        third_k=m1[THIRD][0], third_n=m1[THIRD][1], third_share=share(*m1[THIRD]),
                        fourth_k=m1[FOURTH][0], fourth_n=m1[FOURTH][1], fourth_share=share(*m1[FOURTH]),
                        verdict=v[0]),
        matched=dict(label="matched share (research's new bids with a bot bid within a minute)",
                     third_k=mr[THIRD][0], third_n=mr[THIRD][1], third_share=share(*mr[THIRD]),
                     fourth_k=mr[FOURTH][0], fourth_n=mr[FOURTH][1], fourth_share=share(*mr[FOURTH]),
                     verdict=v[1]),
        level=dict(label="level (new bids more than 5 bp from the research level)",
                   third_k=m3[THIRD][0], third_n=m3[THIRD][1], third_share=share(*m3[THIRD]),
                   fourth_k=m3[FOURTH][0], fourth_n=m3[FOURTH][1], fourth_share=share(*m3[FOURTH]),
                   verdict=v[2], note="the third book's figures carry no verdict"))
    res["items_1_5"] = dict(value=items, verdict=items_v, text=UNREAD_TEXT if items == "unread" else items)
    res["overall"] = overall(v, items) if ok else "WAIT"
    return res


def pct(x):
    return "n/a" if x is None else f"{100 * x:.2f}%"


def to_md(res):
    L = ["# Part 2: fourth paper book against the third (the twelve coins, common minutes)", "",
         f"Period: {res['period']['start']} to {res['period']['end']} UTC (both minutes included)."]
    if res.get("minutes"):
        m = res["minutes"]
        L.append(f"Decision minutes in the period: third book {m['main']}, fourth book {m['tb']}; common minutes "
                 f"{m['common']}.")
    c = res["conditions"]
    c1, c2 = c["c1_minutes_together"], c["c2_bids_on_the_twelve"]
    L += ["", f"- Three full days together: {c1['value']} minutes, {c1['needed']} needed: "
              f"{'met' if c1['met'] else 'not met'}.",
          f"- Enough bids: third book {c2['third']}, fourth book {c2['fourth']} new bids on the twelve, "
          f"{c2['needed']} needed in each: {'met' if c2['met'] else 'not met'}.", "",
          "| measure | third book | fourth book | verdict |", "|---|---|---|---|"]
    for i, m in enumerate(res["measures"].values(), 1):
        L.append(f"| ({i}) {m['label']} | {m['third_k']} / {m['third_n']} = {pct(m['third_share'])} | "
                 f"{m['fourth_k']} / {m['fourth_n']} = {pct(m['fourth_share'])} | {m['verdict']} |")
    it = res["items_1_5"]
    L += ["", "Level (3): the third book's figures are for the record and carry no verdict.", "",
          f"Items 1 to 5 for the fourth book: {it['verdict']}" + (f" ({it['text']})" if it["value"] == "unread" else "")
          + ".", "", f"**Part 2: {res['overall']}**", "",
          f"Rule in plain words: the read waits until the third and fourth books have run three full days together "
          f"({res['min_minutes']} minutes) and each has at least {res['min_bids']} new bids on the twelve coins. Then "
          "the fourth book must have a strictly lower wrong-side share than the third (equal shares fail), a matched "
          "share not lower than the third's, and fewer than 5% of its bids more than 5 bp from the research level, "
          "and items 1 to 5 must hold for it. Shares are compared exactly on the counts. Any failure gives FAIL; "
          "otherwise anything still waiting gives WAIT; otherwise PASS.", "",
          "A PASS means the new way (trades for the newest minute, the venue's candle afterwards) for all 18 coins is "
          "proposed for the next release; it does not change `main` by itself.", ""]
    return "\n".join(L)


def write(out_dir, res):
    json.dump(res, open(os.path.join(out_dir, "part2_rule.json"), "w"), indent=1)
    open(os.path.join(out_dir, "part2_rule.md"), "w").write(to_md(res))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--items-1-5", dest="items", choices=["pass", "fail", "unread"], default="unread")
    ap.add_argument("--min-bids", type=int, default=MIN_BIDS)
    ap.add_argument("--min-minutes", type=int, default=MIN_MINUTES)
    a = ap.parse_args()
    meta = json.load(open(os.path.join(a.dir, "two_books.json")))
    B = pd.read_csv(os.path.join(a.dir, "item7_bids.csv"))
    S = pd.read_csv(os.path.join(a.dir, "side_by_side.csv"))
    res = evaluate(meta, B, S, a.items, a.min_bids, a.min_minutes)
    write(a.dir, res)
    print(to_md(res))


if __name__ == "__main__":
    main()
