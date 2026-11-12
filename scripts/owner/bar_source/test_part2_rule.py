"""Offline tests of the Part 2 decision rule (part2_rule.py) on small made-up folders and on a copy of the real interim
folder. Run: python scripts/owner/bar_source/test_part2_rule.py (prints ok / FAIL per check, last line "N checks
passed", non-zero exit on any failure)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pandas as pd         # noqa: E402

import part2_rule as p2     # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REAL = os.path.join(REPO, "reports", "owner", "reconcile_tb", "i2_t18")
TWELVE = ["AAVE", "BCH", "DOGE", "ENA", "HBAR", "HYPE", "LINK", "NEAR", "ONDO", "PEPE", "SUI", "XLM"]
OUTSIDE = ["ETH", "LTC", "SOL", "XRP", "ZEC", "ZZZ"]
FAILS = []
COUNT = [0]


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


def raises(fn, text):
    try:
        fn()
    except ValueError as exc:
        return text in str(exc)
    return False


def spec(n=300, kw=0, nsc=None, kl=0, nlv=None, m=None, r=None, extra_outside=0):
    """One book: n bids on the twelve; nsc of them have a score (kw on the wrong side); nlv have a level (kl of them
    more than 5 bp away, alternating sign); research matched m of r."""
    return dict(n=n, kw=kw, nsc=n if nsc is None else nsc, kl=kl, nlv=n if nlv is None else nlv,
                m=n if m is None else m, r=n if r is None else r, extra_outside=extra_outside)


def book_rows(label, s):
    rows = []
    for i in range(s["n"]):
        has_sc = i < s["nsc"]
        j = i - (s["n"] - s["nlv"])             # position among the rows that have a level
        err = float("nan")
        if j >= 0:
            err = (6.0 if j % 2 == 0 else -6.0) if j < s["kl"] else (5.0 if j % 2 == 0 else -4.0)
        rows.append(dict(book=label, ts="2026-11-12 00:00:00", coin=TWELVE[i % 12], err_bp=err,
                         res_score=1.0 if has_sc else float("nan"), res_other_side=bool(has_sc and i < s["kw"])))
    for i in range(s["extra_outside"]):         # outside the twelve: wrong side and far from the level, ignored
        rows.append(dict(book=label, ts="2026-11-12 00:00:00", coin=OUTSIDE[i % 6], err_bp=50.0, res_score=1.0,
                         res_other_side=True))
    return rows


def side_rows(label, s, over):
    vals = {("m2_score_error", "n"): s["nsc"], ("m2_score_error", "n_other_side"): s["kw"],
            ("m1_level_error", "n"): s["nlv"], ("m3_bids", "research_matched"): s["m"],
            ("m3_bids", "research_new_bids_ex_blocked"): s["r"]}
    out = []
    for (me, st), v in vals.items():
        v = over.get((label, me, st), v)
        out.append(dict(measure=me, statistic=st, group="candle path", book=label, value=float(v)))
        out.append(dict(measure=me, statistic=st, group="all", book=label, value=999.0))   # other group: ignored
    return out


def make(tmp, third, fourth, minutes=4320, books=("paper_spot_tb", "paper_spot_t18"), over=None):
    """Write a folder like two_books.py's. minutes = period length, both ends included."""
    over = over or {}
    os.makedirs(tmp, exist_ok=True)
    start = pd.Timestamp("2026-11-11 22:25:00")
    end = start + pd.Timedelta(minutes=minutes - 1)
    meta = dict(period=dict(start=str(start), end=str(end)), books=dict(main=books[0], tb=books[1]),
                minutes=dict(main=minutes, tb=minutes, common=minutes),
                groups={"all": TWELVE + OUTSIDE[:5], "candle path": TWELVE})
    json.dump(meta, open(os.path.join(tmp, "two_books.json"), "w"))
    pd.DataFrame(book_rows("main", third) + book_rows("tb", fourth)).to_csv(os.path.join(tmp, "item7_bids.csv"),
                                                                           index=False)
    pd.DataFrame(side_rows("main", third, over) + side_rows("tb", fourth, over)).to_csv(
        os.path.join(tmp, "side_by_side.csv"), index=False)
    return tmp


def run(third, fourth, items="pass", minutes=4320, over=None, books=("paper_spot_tb", "paper_spot_t18"), **kw):
    with tempfile.TemporaryDirectory() as tmp:
        make(tmp, third, fourth, minutes, books, over)
        meta = json.load(open(os.path.join(tmp, "two_books.json")))
        return p2.evaluate(meta, pd.read_csv(os.path.join(tmp, "item7_bids.csv")),
                           pd.read_csv(os.path.join(tmp, "side_by_side.csv")), items, **kw)


def vs(res):
    m = res["measures"]
    return m["wrong_side"]["verdict"], m["matched"]["verdict"], m["level"]["verdict"]


def good3():
    return spec(n=300, kw=6)


def good4():
    return spec(n=300, kw=3)


def test_conditions():
    r = run(spec(299, kw=6), good4())
    check("third book with 299 bids waits", r["overall"] == "WAIT" and vs(r) == ("WAIT",) * 3, r["overall"])
    check("counts still shown when waiting", r["measures"]["wrong_side"]["third_n"] == 299
          and r["measures"]["wrong_side"]["fourth_k"] == 3)
    r = run(good3(), spec(299, kw=3))
    check("fourth book with 299 bids waits", r["overall"] == "WAIT"
          and not r["conditions"]["c2_bids_on_the_twelve"]["met"])
    r = run(good3(), good4(), minutes=4319)
    check("one minute short of 4320 waits", r["overall"] == "WAIT" and vs(r) == ("WAIT",) * 3
          and r["conditions"]["c1_minutes_together"]["value"] == 4319)
    r = run(good3(), good4(), minutes=4320)
    check("exactly 4320 minutes is not WAIT", r["overall"] == "PASS" and r["conditions"]["c1_minutes_together"]["met"])
    check("a failing measure still shows WAIT when c1 is not met",
          run(spec(300, kw=0), good4(), minutes=4319)["measures"]["wrong_side"]["verdict"] == "WAIT")
    r = run(spec(10, kw=1), spec(10, kw=0), min_bids=10, min_minutes=100, minutes=100)
    check("thresholds are parameters and recorded", r["overall"] == "PASS" and r["min_bids"] == 10
          and r["min_minutes"] == 100)
    r = run(good3(), good4())
    check("default thresholds are the rule", r["min_bids"] == 300 and r["min_minutes"] == 4320)


def test_overall():
    r = run(good3(), good4(), items="pass")
    check("full PASS", r["overall"] == "PASS" and vs(r) == ("PASS",) * 3, (r["overall"], vs(r)))
    r = run(good3(), good4(), items="unread")
    check("unread items give overall WAIT", r["overall"] == "WAIT" and r["items_1_5"]["verdict"] == "WAIT"
          and r["items_1_5"]["text"] == "read reports/owner/PAPER_STATUS.md")
    r = run(good3(), good4(), items="fail")
    check("failed items give overall FAIL", r["overall"] == "FAIL")
    r = run(spec(300, kw=6, m=100, r=0), good4(), items="fail")
    check("FAIL beats WAIT", r["overall"] == "FAIL" and r["measures"]["matched"]["verdict"] == "WAIT")
    r = run(spec(300, kw=6, m=100, r=0), good4(), items="pass")
    check("a waiting measure makes overall WAIT", r["overall"] == "WAIT")
    r = run(spec(300, kw=6), spec(300, kw=3, kl=15), items="pass")
    check("a failing measure makes overall FAIL", r["overall"] == "FAIL" and vs(r)[2] == "FAIL")
    check("items 1 to 5 default is unread", subprocess.run(
        [sys.executable, os.path.join(HERE, "part2_rule.py"), "--help"], capture_output=True, text=True
    ).stdout.count("unread") >= 1)


def test_measure1():
    r = run(spec(300, kw=6), spec(350, kw=7))
    check("equal shares (6/300, 7/350) fail", vs(r)[0] == "FAIL")
    r = run(spec(300, kw=0), spec(350, kw=0))
    check("third book with no wrong-side bid fails", vs(r)[0] == "FAIL")
    r = run(spec(300, kw=6), spec(350, kw=6))
    check("fourth strictly lower passes (6/300 vs 6/350)", vs(r)[0] == "PASS")
    r = run(spec(300, kw=6), spec(300, kw=7))
    check("fourth higher fails", vs(r)[0] == "FAIL")
    s = r["measures"]["wrong_side"]
    check("shares reported", abs(s["third_share"] - 0.02) < 1e-12 and s["fourth_k"] == 7)


def test_measure2():
    r = run(spec(300, m=200, r=300), spec(600, m=400, r=600))
    check("equal matched shares with different denominators pass", vs(r)[1] == "PASS")
    r = run(spec(300, m=200, r=300), spec(600, m=399, r=600))
    check("fourth lower by one bid fails", vs(r)[1] == "FAIL")
    r = run(spec(300, m=200, r=300), spec(600, m=401, r=600))
    check("fourth higher passes", vs(r)[1] == "PASS")
    r = run(spec(300, m=0, r=0), good4())
    check("r = 0 for the third book waits", vs(r)[1] == "WAIT")
    r = run(good3(), spec(300, kw=3, m=0, r=0))
    check("r = 0 for the fourth book waits", vs(r)[1] == "WAIT")


def test_measure3():
    check("exactly 5% (15 of 300) fails", vs(run(good3(), spec(300, kw=3, kl=15)))[2] == "FAIL")
    check("just under (14 of 300) passes", vs(run(good3(), spec(300, kw=3, kl=14)))[2] == "PASS")
    r = run(good3(), spec(300, kw=3, kl=0))
    check("abs(err_bp) exactly 5 is not above 5", r["measures"]["level"]["fourth_k"] == 0 and vs(r)[2] == "PASS")
    r = run(good3(), spec(300, kw=3, kl=1))
    check("negative errors count by absolute value", r["measures"]["level"]["fourth_k"] == 1)
    rows = pd.DataFrame(book_rows("tb", spec(300, kl=2)))
    check("both signs among the counted errors", (rows["err_bp"] == -6.0).sum() == 1
          and (rows["err_bp"] == 6.0).sum() == 1)
    r = run(spec(300, kw=6, kl=299), spec(300, kw=3, kl=14))
    check("third book's level carries no verdict", vs(r)[2] == "PASS" and r["measures"]["level"]["third_k"] == 299)


def test_missing_and_outside():
    r = run(spec(300, kw=6, nsc=250), spec(300, kw=3, nsc=260))
    check("missing scores are left out of measure 1 but count as bids", r["measures"]["wrong_side"]["third_n"] == 250
          and r["measures"]["wrong_side"]["fourth_n"] == 260 and r["conditions"]["c2_bids_on_the_twelve"]["met"]
          and r["overall"] == "PASS")
    r = run(good3(), spec(300, kw=3, nlv=280, kl=13))
    check("missing levels are left out of measure 3 but count as bids", r["measures"]["level"]["fourth_n"] == 280
          and r["conditions"]["c2_bids_on_the_twelve"]["met"] and vs(r)[2] == "PASS")
    r = run(spec(300, kw=6, extra_outside=40), spec(300, kw=3, extra_outside=40))
    check("coins outside the twelve are ignored", r["measures"]["wrong_side"]["third_n"] == 300
          and r["measures"]["level"]["fourth_k"] == 0 and r["conditions"]["c2_bids_on_the_twelve"]["fourth"] == 300)
    r = run(spec(290, kw=6, extra_outside=40), good4())
    check("outside coins do not help c2", r["overall"] == "WAIT")


def test_errors():
    check("guard: wrong third book name raises", raises(
        lambda: run(good3(), good4(), books=("paper_spot_t18", "paper_spot_t18")), "not a third-book"))
    check("guard: wrong fourth book name raises", raises(
        lambda: run(good3(), good4(), books=("paper_spot_tb", "paper_spot")), "not a third-book"))
    check("guard: swapped names raise", raises(
        lambda: run(good3(), good4(), books=("paper_spot_t18", "paper_spot_tb")), "not a third-book"))
    for b in ("main", "tb"):
        check(f"wrong-side n disagrees ({b})", raises(
            lambda: run(good3(), good4(), over={(b, "m2_score_error", "n"): 299}), "wrong-side counts"))
        check(f"wrong-side k disagrees ({b})", raises(
            lambda: run(good3(), good4(), over={(b, "m2_score_error", "n_other_side"): 9}), "wrong-side counts"))
        check(f"level n disagrees ({b})", raises(
            lambda: run(good3(), good4(), over={(b, "m1_level_error", "n"): 299}), "level count"))
    check("a non-whole count raises", raises(
        lambda: run(good3(), good4(), over={("tb", "m3_bids", "research_matched"): 299.5}), "not a whole number"))
    check("a non-whole consistency count raises", raises(
        lambda: run(good3(), good4(), over={("main", "m2_score_error", "n"): 300.25}), "not a whole number"))
    check("a missing side_by_side row raises", raises(
        lambda: p2.side_value(pd.DataFrame(columns=["measure", "statistic", "group", "book", "value"]),
                              "m3_bids", "research_matched", "main"), "expected one row"))
    check("a bad items value raises", raises(lambda: run(good3(), good4(), items="maybe"), "pass, fail or unread"))
    with tempfile.TemporaryDirectory() as tmp:
        make(tmp, good3(), good4(), books=("paper_spot_t18", "paper_spot_tb"))
        r = subprocess.run([sys.executable, os.path.join(HERE, "part2_rule.py"), "--dir", tmp],
                           capture_output=True, text=True)
        check("guard on the command line: error and no verdict written", r.returncode != 0
              and not os.path.exists(os.path.join(tmp, "part2_rule.json"))
              and not os.path.exists(os.path.join(tmp, "part2_rule.md")), r.stderr[-200:])


def test_exact_arithmetic():
    big = 10 ** 9
    r = run(spec(300, kw=6), spec(300, kw=6), min_bids=1)
    check("integer comparison: equal shares fail", vs(r)[0] == "FAIL")
    check("cross-multiplication on large counts", p2.v_wrong_side(1, big, 1, big + 1) == "PASS"
          and p2.v_wrong_side(1, big + 1, 1, big) == "FAIL" and p2.v_matched(big, big + 1, big - 1, big) == "FAIL")
    check("level uses 20 k < n", p2.v_level(1, 21) == "PASS" and p2.v_level(1, 20) == "FAIL")


def test_cli_and_real():
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "folder")
        make(d, good3(), good4())
        r = subprocess.run([sys.executable, os.path.join(HERE, "part2_rule.py"), "--dir", d, "--items-1-5", "pass"],
                           capture_output=True, text=True)
        js = json.load(open(os.path.join(d, "part2_rule.json")))
        md = open(os.path.join(d, "part2_rule.md")).read()
        check("command line writes json and md and prints the markdown", r.returncode == 0 and r.stdout.strip() ==
              md.strip() and js["overall"] == "PASS" and "**Part 2: PASS**" in md, r.stderr[-200:])
        check("markdown never says main book or tb", "main book" not in md and " tb " not in md
              and "third book" in md and "fourth book" in md)
        check("markdown title", md.startswith("# Part 2: fourth paper book against the third (the twelve coins, "
                                              "common minutes)"))
    check("real interim folder exists", os.path.isdir(REAL), REAL)
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "i2_t18")
        shutil.copytree(REAL, d)
        r = subprocess.run([sys.executable, os.path.join(HERE, "part2_rule.py"), "--dir", d],
                           capture_output=True, text=True)
        check("real folder runs", r.returncode == 0, r.stderr[-300:])
        js = json.load(open(os.path.join(d, "part2_rule.json")))
        md = open(os.path.join(d, "part2_rule.md")).read()
        c2, ms = js["conditions"]["c2_bids_on_the_twelve"], js["measures"]
        check("real folder: overall WAIT", js["overall"] == "WAIT")
        check("real folder: 59 and 70 bids", c2["third"] == 59 and c2["fourth"] == 70)
        check("real folder: no wrong-side bids", (ms["wrong_side"]["third_k"], ms["wrong_side"]["fourth_k"]) == (0, 0)
              and (ms["wrong_side"]["third_n"], ms["wrong_side"]["fourth_n"]) == (59, 70))
        check("real folder: matched 55 of 59 and 66 of 70", (ms["matched"]["third_k"], ms["matched"]["third_n"],
                                                             ms["matched"]["fourth_k"], ms["matched"]["fourth_n"])
              == (55, 59, 66, 70))
        check("real folder: level 0 of 59 and 0 of 70", (ms["level"]["third_k"], ms["level"]["third_n"],
                                                         ms["level"]["fourth_k"], ms["level"]["fourth_n"])
              == (0, 59, 0, 70))
        check("real folder: markdown has no main book or tb label", "main book" not in md and " tb " not in md)


def main():
    for t in (test_conditions, test_overall, test_measure1, test_measure2, test_measure3, test_missing_and_outside,
              test_errors, test_exact_arithmetic, test_cli_and_real):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
