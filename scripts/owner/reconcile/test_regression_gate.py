"""Regression gate: compare.py with default arguments must reproduce, byte for byte, every committed file in
reports/owner/reconcile/ that it writes (the m1 to m4 CSVs and summary.json). Writes into a temporary folder; never
touches the committed files. Skipped, with a message, when an input is absent.
Run: python scripts/owner/reconcile/test_regression_gate.py (prints ok / FAIL per file, ends with "all passed")."""
import filecmp
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)

import common               # noqa: E402
import compare              # noqa: E402

COMMITTED = os.path.join(ROOT, "reports", "owner", "reconcile")
BOOK = os.path.join(ROOT, "paper_spot")
FILES = ["m1_m2_bot_arms.csv", "m1_level_error.csv", "m1_explained_by_late_btc.csv", "m1_closest_input.csv",
         "m1_by_coin.csv", "m1_by_btc_move.csv", "m2_score_error.csv", "m3_bids.csv", "m3_research_new_bids.csv",
         "m3_cash_short.csv", "m4_fills.csv", "m4_summary.csv", "m4_unsettled_minutes.csv", "summary.json"]
NEEDED = [os.path.join(COMMITTED, "research_minutes.csv.gz"), os.path.join(COMMITTED, "late_btc_at_arms.csv"),
          os.path.join(BOOK, "events.jsonl"), os.path.join(BOOK, "state.json"),
          os.path.join(ROOT, "bot", "v2", "model_meta.json")] + [os.path.join(COMMITTED, f) for f in FILES]


def main():
    missing = [p for p in NEEDED if not os.path.exists(p)]
    if missing:
        print("SKIPPED: regression gate needs these inputs, absent here:", *missing, sep="\n  ")
        print("test_regression_gate: skipped (not passed, not failed)")
        return
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        ev, R, late, ticks, thr = compare.load_inputs(BOOK, COMMITTED)
        o = compare.compute(ev, R, late, ticks, thr)            # the defaults: first event to common.END
        compare.write_outputs(o, tmp)
        written = set(os.listdir(tmp))
        for f in FILES:
            ok = f in written and filecmp.cmp(os.path.join(COMMITTED, f), os.path.join(tmp, f), shallow=False)
            print(("ok   " if ok else "FAIL ") + f"{f} byte-identical to the committed file")
            if not ok:
                fails.append(f)
        extra = written - set(FILES)
        print(("ok   " if not extra else "FAIL ") + "no file beyond the committed set", sorted(extra) or "")
        if extra:
            fails.append("extra files")
    print(f"(period: {ev[0]['ts']} to {common.END})")
    if fails:
        print(f"{len(fails)} FAILED: {fails}")
        sys.exit(1)
    print("test_regression_gate: all passed")


if __name__ == "__main__":
    main()
