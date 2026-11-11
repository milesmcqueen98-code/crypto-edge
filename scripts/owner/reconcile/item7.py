"""Item 7 of the third paper book's rule (reports/owner/FORWARD_TESTS.md, row "Verified inputs (release 2), third
paper book"), as code. Semantics fixed by the owner's brief; do not improve on them.

  "(7) on the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from
  the research level, and the share of new bids whose research score is on the other side of the threshold, are each
  lower in the third book than in the main book, or below 5% in both. At least 200 new bids in each book are needed,
  and item 7 waits for them if there are fewer."

Inputs: each book's per-bid table (compare.py's m1_m2_bot_arms rows, columns err_bp, res_score, res_other_side),
already restricted by the caller to the common minutes (two_books.py: the minutes that are decision minutes of both
books in the period).
  (a) among the book's new bids with a research level (err_bp not missing: measure 1's set; err_bp is 0 when the bot
      price is within one tick of the research price), the share with abs(err_bp) > 5.
  (b) among the book's new bids with a research score (res_score not missing: measure 2's set), the share whose
      research score is at or below the threshold (res_other_side, computed by compare.py at full precision).
  Per measure: WAIT if either book has fewer than 200 counted bids; else PASS if the third book's share is strictly
  lower than the main book's, or both shares are strictly below 5%; else FAIL. Shares are compared exactly, by integer
  cross-multiplication of the counts.
  Overall: FAIL if any measure is FAIL; else WAIT if any is WAIT; else PASS.

Command line: python scripts/owner/reconcile/item7.py --dir reports/owner/reconcile_tb
  reads <dir>/item7_bids.csv (written by two_books.py at full precision: book, ts, coin, err_bp, res_score,
  res_other_side, restricted to the common minutes) and <dir>/two_books.json (period and minute counts), and writes
  <dir>/item7.json and <dir>/item7.md.
"""
import argparse
import json
import os

import pandas as pd

MIN_BIDS = 200
LIMIT_BP = 5.0
BOTH_BELOW = (1, 20)            # 5% as a fraction: share < 1/20  <=>  20 * k < n


def counts(A):
    """(k, n) for measure (a) and (b) on one book's per-bid rows."""
    lv = A[A["err_bp"].notna()]
    sc = A[A["res_score"].notna()]
    a = (int((lv["err_bp"].abs() > LIMIT_BP).sum()), int(len(lv)))
    b = (int(sc["res_other_side"].astype(bool).sum()), int(len(sc)))
    return a, b


def below(k, n):
    """k / n strictly below 5%, exactly."""
    return BOTH_BELOW[1] * k < BOTH_BELOW[0] * n


def verdict(k_main, n_main, k_tb, n_tb, min_n=MIN_BIDS):
    if n_main < min_n or n_tb < min_n:
        return "WAIT"
    if k_tb * n_main < k_main * n_tb:              # k_tb / n_tb < k_main / n_main
        return "PASS"
    if below(k_main, n_main) and below(k_tb, n_tb):
        return "PASS"
    return "FAIL"


def overall(verdicts):
    if "FAIL" in verdicts:
        return "FAIL"
    if "WAIT" in verdicts:
        return "WAIT"
    return "PASS"


def evaluate(main, tb, meta=None):
    """main, tb: per-bid tables restricted to the common minutes. meta: dict copied into the result."""
    (ka1, na1), (kb1, nb1) = counts(main)
    (ka3, na3), (kb3, nb3) = counts(tb)
    res = dict(meta or {})
    ms = {}
    for key, label, k1, n1, k3, n3 in (
            ("a_level_gt5bp", "new bids more than 5 bp from the research level", ka1, na1, ka3, na3),
            ("b_score_other_side", "new bids whose research score is at or below the threshold", kb1, nb1, kb3, nb3)):
        ms[key] = dict(label=label, main_k=k1, main_n=n1, main_share=(k1 / n1) if n1 else None,
                       tb_k=k3, tb_n=n3, tb_share=(k3 / n3) if n3 else None,
                       verdict=verdict(k1, n1, k3, n3))
    res["measures"] = ms
    res["min_bids"] = MIN_BIDS
    res["overall"] = overall([m["verdict"] for m in ms.values()])
    return res


def pct(x):
    return "n/a" if x is None else f"{100 * x:.2f}%"


def to_md(res):
    L = ["# Item 7: third book against main book, on the minutes both were live", ""]
    if "period" in res:
        L.append(f"Period: {res['period']['start']} to {res['period']['end']} UTC (both included).")
    if "minutes" in res:
        m = res["minutes"]
        L.append(f"Decision minutes in the period: main book {m['main']}, third book {m['tb']}; common minutes "
                 f"{m['common']}.")
    L += ["", "| measure | main book | third book | verdict |", "|---|---|---|---|"]
    for k, m in res["measures"].items():
        L.append(f"| ({k[0]}) {m['label']} | {m['main_k']} / {m['main_n']} = {pct(m['main_share'])} | "
                 f"{m['tb_k']} / {m['tb_n']} = {pct(m['tb_share'])} | {m['verdict']} |")
    L += ["", f"**Item 7: {res['overall']}**", "",
          f"Rule: per measure, WAIT if either book has fewer than {res['min_bids']} counted bids; PASS if the third "
          "book's share is strictly lower than the main book's, or both are strictly below 5%; else FAIL. Shares are "
          "compared exactly on the counts. Overall: FAIL if any measure fails, else WAIT if any waits, else PASS.", ""]
    return "\n".join(L)


def write(out_dir, res):
    json.dump(res, open(os.path.join(out_dir, "item7.json"), "w"), indent=1)
    open(os.path.join(out_dir, "item7.md"), "w").write(to_md(res))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                                  "reports", "owner", "reconcile_tb"))
    a = ap.parse_args()
    B = pd.read_csv(os.path.join(a.dir, "item7_bids.csv"))
    meta = json.load(open(os.path.join(a.dir, "two_books.json")))
    res = evaluate(B[B.book == "main"], B[B.book == "tb"],
                   dict(period=meta["period"], minutes=meta["minutes"]))
    write(a.dir, res)
    print(to_md(res))


if __name__ == "__main__":
    main()
