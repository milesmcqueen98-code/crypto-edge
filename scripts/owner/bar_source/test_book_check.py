"""Offline tests of book_check.py on a tiny made-up table and log.
Run: python scripts/owner/bar_source/test_book_check.py (a PASS or FAIL line per check, a count at the end,
non-zero exit on any failure)."""
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

import pandas as pd         # noqa: E402

spec = importlib.util.spec_from_file_location("book_check", os.path.join(HERE, "book_check.py"))
bk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bk)

THR = float(json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))["threshold"])
PASSED, FAILED = [], []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + str(detail)))


def ts(m):
    return pd.Timestamp("2026-11-12 00:00") + pd.Timedelta(minutes=m)


def row(m, coin, score, res, pass_="C18", valid=True, res_valid=True, src="candle", old=False, ok=True):
    return dict(ts=ts(m), coin=coin, **{"pass": pass_}, way="C", score=score, level=1.0, sig=0.01, valid=valid,
                src=src, inputs_ok=ok, answer_old=old, res_score=res, res_level=1.0, res_sig=0.01, res_valid=res_valid)


def bid(m, coin, pred):
    return dict(ts=ts(m), coin=coin, pred=pred)


def run_counts(rows, bids, pass_="C18", start=0, end=100, thr=50.0, within=0.5, gap=2.0):
    T = pd.DataFrame(rows)
    return bk.compute(bids, T, pass_, ts(start), ts(end), within, gap, thr)


def test_within_and_edges():
    rows = [row(0, "DOGE", 60.0, 60.0), row(1, "DOGE", 60.0, 60.0), row(2, "LINK", 60.0, 60.0),
            row(3, "LINK", 60.0, 60.0)]
    bids = [bid(0, "DOGE", 60.4), bid(1, "DOGE", 61.0), bid(2, "LINK", 60.5), bid(3, "LINK", 60.6)]
    _, _, C = run_counts(rows, bids)
    c = C["all"]
    check("a bid within and bids not within: 60.4 and 60.5 within, 61.0 and 60.6 not", c["within"] == 2 and c["n"] == 4, c)


def test_gap_edge():
    rows = [row(0, "DOGE", 60.0, 62.0), row(1, "DOGE", 60.0, 62.1), row(2, "DOGE", 60.0, 58.0)]
    bids = [bid(0, "DOGE", 60.0), bid(1, "DOGE", 60.0), bid(2, "DOGE", 60.0)]
    _, _, C = run_counts(rows, bids)
    c = C["all"]
    check("exactly 2.0 from the research is near, 2.1 is far", c["far"] == 1 and c["near"] == 2, c)
    check("exactly 2.0 below the research is near too", c["near"] == 2 and c["res_valid"] == 3, c)


def test_invalid_emulation():
    rows = [row(0, "DOGE", float("nan"), 60.0, valid=False), row(1, "DOGE", 60.0, 60.0)]
    bids = [bid(0, "DOGE", 60.0), bid(1, "DOGE", 60.0)]
    _, _, C = run_counts(rows, bids)
    c = C["all"]
    check("a bid with no valid emulated score is in n, not within", c["n"] == 2 and c["within"] == 1
          and c["emu_valid"] == 1, c)


def test_no_row_outside_untraded():
    rows = [row(0, "DOGE", 60.0, 60.0)]
    bids = [bid(0, "DOGE", 60.0), bid(1, "DOGE", 60.0), bid(500, "DOGE", 60.0), bid(-5, "DOGE", 60.0),
            bid(0, "BTC", 60.0)]
    _, apart, C = run_counts(rows, bids)
    check("a bid with no row is counted apart and is in no share", apart["no_row"] == 1 and C["all"]["n"] == 1, apart)
    check("bids outside the period are ignored", apart["outside_period"] == 2, apart)
    check("a bid on a coin that is not traded is ignored", apart["not_traded"] == 1, apart)


def test_pass_a_ltc():
    rows = [row(0, "LTC", 60.0, 60.0, "A"), row(0, "ETH", 60.0, 60.0, "A"), row(1, "ZEC", 60.0, 60.0, "A")]
    bids = [bid(0, "LTC", 60.0), bid(0, "ETH", 60.0), bid(1, "ZEC", 60.0)]
    _, apart, C = run_counts(rows, bids, "A")
    check("pass A leaves LTC out and counts it", apart["left_out"] == 1 and C["all"]["n"] == 2
          and C["five"]["n"] == 2, (apart, C["all"]))
    rows18 = [dict(r, **{"pass": "C18"}) for r in rows]
    _, apart, C = run_counts(rows18, bids, "C18")
    check("pass C18 keeps LTC", apart["left_out"] == 0 and C["five"]["n"] == 3, (apart, C["five"]))


def test_groups():
    rows = [row(0, "DOGE", 60.0, 60.0), row(1, "ETH", 60.0, 60.0)]
    bids = [bid(0, "DOGE", 60.0), bid(1, "ETH", 70.0)]
    _, _, C = run_counts(rows, bids)
    check("groups: the twelve and the five split the bids", C["twelve"]["n"] == 1 and C["twelve"]["within"] == 1
          and C["five"]["n"] == 1 and C["five"]["within"] == 0 and C["all"]["n"] == 2, C)


def test_readings():
    for a, b, want in ((80, 100, "confirmed"), (79, 100, "explained in part"), (50, 100, "explained in part"),
                       (49, 100, "not explained")):
        check(f"reading (ii) at {a} of {b} is {want}", bk.reading_ii(a, b) == want, bk.reading_ii(a, b))
    check("reading (ii) with no far bid", bk.reading_ii(0, 0) == "no far bids")
    check("reading (i) at 90 of 100 stands, at 89 does not",
          bk.reading_i(90, 100) == "stands for the book" and bk.reading_i(89, 100) == "does not stand for the book")
    rows, bids = [], []
    for i in range(100):
        rows.append(row(i, "DOGE", 60.0 if i < 79 else 70.0, 63.0))
        bids.append(bid(i, "DOGE", 60.0))
    _, _, C = run_counts(rows, bids)
    c = C["all"]
    check("made-up counts: 79 of 100 far bids within gives explained in part",
          (c["far_within"], c["far"], c["reading_ii"]) == (79, 100, "explained in part"), c)


def test_far_split_and_src():
    rows = [row(0, "DOGE", 60.0, 70.0, src="candle", old=False), row(1, "DOGE", 70.0, 70.0, src="fb_x", old=True),
            row(2, "DOGE", 80.0, 70.0, src="candle", old=False), row(3, "DOGE", 60.0, 60.0)]
    bids = [bid(0, "DOGE", 60.0), bid(1, "DOGE", 60.0), bid(2, "DOGE", 60.0), bid(3, "DOGE", 60.0)]
    _, _, C = run_counts(rows, bids)
    c = C["all"]
    check("far split: within of the book, within of the research instead, neither",
          (c["far"], c["far_within"], c["far_res_within_not_book"], c["far_neither"]) == (3, 1, 1, 1), c)
    check("far counts by src and by answer_old", c["far_by_src"] == {"candle": 2, "fb_x": 1}
          and c["far_by_answer_old"] == {"False": 2, "True": 1}, c)
    check("near within count", c["near"] == 1 and c["near_within"] == 1, c)


def test_wrong_side():
    rows = [row(0, "DOGE", 40.0, 40.0), row(1, "DOGE", 60.0, 40.0), row(2, "DOGE", float("nan"), 40.0, valid=False),
            row(3, "DOGE", 60.0, 60.0), row(4, "DOGE", 50.0, 50.0)]
    bids = [bid(i, "DOGE", 55.0) for i in range(5)]
    _, _, C = run_counts(rows, bids, thr=50.0)
    c = C["all"]
    check("wrong side: research at or below the threshold (50.0 itself counts)", c["wrong_side_n"] == 4, c)
    check("wrong side split: research's side, book's side, no valid emulated score",
          (c["wrong_side_emu_research_side"], c["wrong_side_emu_book_side"], c["wrong_side_no_valid_emu"])
          == (2, 1, 1), c)


def test_files():
    with tempfile.TemporaryDirectory() as d:
        rows = [row(i, "DOGE", 60.0, 60.0 if i % 2 else 66.0) for i in range(10)] + \
               [row(i, "ETH", 60.0, 60.0) for i in range(10)]
        pd.DataFrame(rows).to_parquet(os.path.join(d, "minutes.parquet"))
        json.dump(dict(threshold=THR), open(os.path.join(d, "run.json"), "w"))
        with open(os.path.join(d, "events.jsonl"), "w") as f:
            f.write(json.dumps(dict(ts="2026-11-12T00:00:00", kind="backfill")) + "\n")
            for i in range(10):
                f.write(json.dumps(dict(ts=str(ts(i)).replace(" ", "T"), kind="arm", coin="DOGE",
                                        pred=60.0 if i < 8 else 61.0)) + "\n")
                f.write(json.dumps(dict(ts=str(ts(i)).replace(" ", "T"), kind="arm", coin="ETH", pred=60.3)) + "\n")
        out = os.path.join(d, "out")
        rc = bk.main(["--dir", d, "--log", os.path.join(d, "events.jsonl"), "--book", "tst", "--pass", "C18",
                      "--out", out])
        stem = os.path.join(out, "book_check_tst_C18")
        have = all(os.path.isfile(stem + s) for s in (".md", ".json", "_bids.csv"))
        check("the run returns 0 and writes the md, json and csv files", rc == 0 and have)
        J = json.load(open(stem + ".json"))["groups"]["all"]
        md = open(stem + ".md").read()
        csv = pd.read_csv(stem + "_bids.csv")
        m_i = re.search(r"within of the book's score \| (\d+) of (\d+) \((\d+\.\d\d)%\)", md)
        m_ii = re.search(r"emulated within of the book \(ii\) \| (\d+) of (\d+) \((\d+\.\d\d)%\)", md)
        check("md and json agree on n and on share (i)", m_i and int(m_i.group(2)) == J["n"] == 20
              and int(m_i.group(1)) == J["within"] == 18 and m_i.group(3) == "90.00", (m_i, J))
        check("md and json agree on share (ii)", m_ii and (int(m_ii.group(1)), int(m_ii.group(2))) ==
              tuple(J["share_ii"]) and m_ii.group(3) == "80.00", (m_ii, J))
        check("csv agrees on n and on both shares", len(csv) == J["n"] and int(csv["within"].sum()) == J["within"]
              and int((csv["far"] == True).sum()) == J["far"]  # noqa: E712
              and int(((csv["far"] == True) & csv["within"]).sum()) == J["far_within"], J)  # noqa: E712
        check("the md prints the readings", "stands for the book" in md and "Reading (ii)" in md and "confirmed" in md)
        # errors
        for name, args in (("a missing log", ["--log", os.path.join(d, "none.jsonl")]),
                           ("an empty period", ["--start", "2030-01-01T00:00", "--end", "2030-01-02T00:00"])):
            base = ["--dir", d, "--log", os.path.join(d, "events.jsonl"), "--book", "tst", "--pass", "C18"]
            try:
                bk.main(base + args)
                ok = False
            except SystemExit as e:
                ok = isinstance(e.code, str) and e.code.startswith("book_check:")
            check(f"{name} stops with a clear message", ok)
        try:
            bk.main(["--dir", d, "--log", os.path.join(d, "events.jsonl"), "--book", "tst", "--pass", "A"])
            ok = False
        except SystemExit as e:
            ok = isinstance(e.code, str) and "not in the table" in e.code
        check("a pass that is not in the table stops with a clear message", ok)
        try:
            bk.main(["--dir", os.path.join(d, "nowhere"), "--log", os.path.join(d, "events.jsonl"), "--book", "t",
                     "--pass", "C18"])
            ok = False
        except SystemExit as e:
            ok = isinstance(e.code, str) and "no table" in e.code
        check("a missing table stops with a clear message", ok)


def test_lists_match_build():
    try:
        sys.path.insert(0, HERE)
        import build
    except Exception as e:      # the engine may be unavailable; the lists are then not compared
        print("SKIP lists against build.py (" + type(e).__name__ + ")")
        return
    check("coin lists equal build.py's", bk.TWELVE == build.TWELVE and bk.FIVE == ["ETH", "SOL", "XRP"] + ["LTC", "ZEC"]
          and set(bk.FIVE) == set(build.BOOK_TRADES[1:] + build.REPORTED))


def main():
    for t in (test_within_and_edges, test_gap_edge, test_invalid_emulation, test_no_row_outside_untraded,
              test_pass_a_ltc, test_groups, test_readings, test_far_split_and_src, test_wrong_side, test_files,
              test_lists_match_build):
        t()
    print(f"{len(PASSED)} PASS, {len(FAILED)} FAIL")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
