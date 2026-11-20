"""Offline tests of the second run's rule (part3b_rule.py) on small made-up folders and logs. Run:
python scripts/owner/bar_source/test_part3b_rule.py (prints ok / FAIL per check, last line "N checks passed", non-zero exit
on any failure). The helpers for logs, pairs and heartbeats are those of test_part3_rule.py (imported, not copied)."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pandas as pd             # noqa: E402

import part3b_rule as p3b       # noqa: E402
import test_part3_rule as t3    # noqa: E402

FIVE, TWELVE = t3.TRADES, t3.CANDLE
ALL = FIVE + TWELVE
FAILS = []
COUNT = [0]
START, END = "2026-11-20 00:30", "2026-11-23 00:29"
COMMIT = "9e6f53b3aca8c15307f22a357f19431bff053e4c"
OTHER_COMMIT = "0123456789abcdef0123456789abcdef01234567"


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


def spec(five=(100, 100, 0), twelve=(200, 200, 0), l=0, nl=None, m=None, r=None):
    """One book: bids on the five coins as (bids, scored, wrong side) and on the twelve likewise; nl bids with a level (l of
    them more than 5 bp away); research matched m of r. Defaults: every bid has a level, m = r = all bids."""
    n = five[0] + twelve[0]
    return dict(five=five, twelve=twelve, n=n, l=l, nl=n if nl is None else nl, m=n if m is None else m, r=n if r is None else r)


def rows_for(label, s):
    out, i = [], 0
    for coins, (n, ns, w) in ((FIVE, s["five"]), (TWELVE, s["twelve"])):
        for k in range(n):
            out.append(dict(book=label, ts="2026-11-21 00:00:00", coin=coins[k % len(coins)], err_bp=float("nan"),
                            res_score=1.0 if k < ns else float("nan"), res_other_side=bool(k < ns and k < w)))
    for i, row in enumerate(out):
        if i < s["nl"]:
            row["err_bp"] = (6.0 if i % 2 == 0 else -6.0) if i < s["l"] else (5.0 if i % 2 == 0 else -4.0)
    return out


def side(label, s, over):
    ns, w = s["five"][1] + s["twelve"][1], s["five"][2] + s["twelve"][2]
    vals = {("m3_bids", "bot_new_bids"): s["n"], ("m2_score_error", "n"): ns, ("m2_score_error", "n_other_side"): w,
            ("m1_level_error", "n"): s["nl"], ("m3_bids", "research_matched"): s["m"],
            ("m3_bids", "research_new_bids_ex_blocked"): s["r"]}
    out = []
    for st, v in (("n", s["five"][1]), ("n_other_side", s["five"][2])):
        out.append(dict(measure="m2_score_error", statistic=st, group="trades list", book=label,
                        value=float(over.get((label, "trades list", st), v))))
    for (me, st), v in vals.items():
        v = over.get((label, me, st), v)
        out.append(dict(measure=me, statistic=st, group="all", book=label, value=float(v)))
        out.append(dict(measure=me, statistic=st, group="candle path", book=label, value=999.0))
    return out


def folder(first, second, books, over=None, groups=None, start=START, end=END):
    """A made-up two_books folder: label main = first, label tb = second."""
    meta = dict(period=dict(start=start, end=end), books=dict(main=books[0], tb=books[1]),
                minutes=dict(main=4300, tb=4310, common=4290),
                groups=groups or {"all": ALL, "trades list": FIVE, "candle path": TWELVE})
    over = over or {}
    B = pd.DataFrame(rows_for("main", first) + rows_for("tb", second))
    S = pd.DataFrame(side("main", first, over) + side("tb", second, over))
    return meta, B, S


BOOKS = ("paper_spot_t18", "paper_spot_r5")
BOOKS_MAIN = ("paper_spot", "paper_spot_r5")
GOOD = dict(five=(100, 100, 1), twelve=(200, 200, 8), m=280, r=300)


def run(fourth=None, fifth=None, main=None, fifth_b=None, items="pass", r5=None, rmain=None, rfourth=None, over=None,
        over_main=None, groups=None, groups_main=None, books=BOOKS, books_main=BOOKS_MAIN, start_main=START, end_main=END,
        pairs=None, pairs_other=0, **kw):
    fourth, fifth = fourth or spec(**GOOD), fifth or spec(**GOOD)
    main, fifth_b = main or spec(**GOOD), fifth_b or fifth
    meta, B, S = folder(fourth, fifth, books, over, groups)
    meta_m, Bm, Sm = folder(main, fifth_b, books_main, over_main, groups_main, start_main, end_main)
    r5 = r5 if r5 is not None else t3.hbs([10.0] * 100)
    rmain = rmain if rmain is not None else t3.hrows([10.0] * 100)
    rfourth = rfourth if rfourth is not None else t3.hrows([10.0] * 100)
    return p3b.evaluate(meta, B, S, meta_m, Bm, Sm, r5, [], rmain, rfourth, items, start=START, end=END,
                        pairs=t3.GOOD_PAIRS if pairs is None else pairs, pairs_other=pairs_other, **kw)


def d_of(**kw):
    return run(**kw)["measures"]["decisions"]


def test_measure2():
    # (2a) against the fourth book: 17 coins, 300 scored bids each, 2.0 points = 6 bids
    d = d_of(fourth=spec(five=(100, 100, 0), twelve=(200, 200, 0)), fifth=spec(five=(100, 100, 0), twelve=(200, 200, 6)))
    check("2a: exactly the fourth's share plus 2.0 points is met", d["wrong_side_vs_fourth"]["met"] and d["met"], d)
    d = d_of(fourth=spec(five=(100, 100, 0), twelve=(200, 200, 0)), fifth=spec(five=(100, 100, 0), twelve=(200, 200, 7)))
    check("2a: one more wrong bid is not met and measure 2 is not met", not d["wrong_side_vs_fourth"]["met"] and not d["met"]
          and d["wrong_side_vs_main"]["met"], d)
    d = d_of(fourth=spec(five=(100, 100, 0), twelve=(200, 200, 0)), fifth=spec(five=(100, 100, 0), twelve=(200, 200, 6)),
             fifth_b=spec(five=(100, 100, 0), twelve=(200, 200, 0)))
    check("2a: reads --dir, not --dir-main (the fifth book's counts differ between the folders)",
          d["wrong_side_vs_fourth"]["fifth"] == "6/300" and d["wrong_side_vs_main"]["fifth"] == "0/300", d)
    d = d_of(fourth=spec(five=(100, 100, 0), twelve=(200, 200, 1), m=280, r=300), fifth=spec(five=(100, 100, 0), twelve=(100, 100, 5)))
    check("2a: shares use the scored bids as denominators (5/200 against 1/300 plus 2 points)",
          d["wrong_side_vs_fourth"]["fifth"] == "5/200" and d["wrong_side_vs_fourth"]["fourth"] == "1/300"
          and not d["wrong_side_vs_fourth"]["met"], d)
    # (2b) against the main book, in --dir-main
    d = d_of(main=spec(five=(100, 100, 0), twelve=(200, 200, 0)), fifth_b=spec(five=(100, 100, 0), twelve=(200, 200, 6)))
    check("2b: exactly the main book's share plus 2.0 points is met", d["wrong_side_vs_main"]["met"] and d["met"], d)
    d = d_of(main=spec(five=(100, 100, 0), twelve=(200, 200, 0)), fifth_b=spec(five=(100, 100, 0), twelve=(200, 200, 7)))
    check("2b: one more wrong bid is not met though 2a, 2c, 2d, 2e are met", not d["wrong_side_vs_main"]["met"] and not d["met"]
          and d["wrong_side_vs_fourth"]["met"] and d["wrong_side_cap_five"]["met"] and d["matched"]["met"] and d["level"]["met"], d)
    d = d_of(main=spec(five=(100, 100, 5), twelve=(200, 200, 15)), fifth_b=spec(five=(100, 100, 0), twelve=(200, 200, 26)))
    check("2b: main 20/300 plus 2 points is 26/300: met (the main book's counts are its own)",
          d["wrong_side_vs_main"]["met"] and d["wrong_side_vs_main"]["main"] == "20/300", d)
    d = d_of(main=spec(five=(100, 100, 5), twelve=(200, 200, 15)), fifth_b=spec(five=(100, 100, 0), twelve=(200, 200, 27)))
    check("2b: 27/300 against 20/300 plus 2 points is not met", not d["wrong_side_vs_main"]["met"], d)
    # (2c) the cap on the five: n = 100 scored bids on the five
    hi = dict(twelve=(200, 200, 20))
    d = d_of(fourth=spec(five=(100, 100, 5), **hi), fifth=spec(five=(100, 100, 5), **hi), main=spec(five=(100, 100, 5), **hi))
    check("2c: the five at exactly 5% (5 of 100) is met", d["wrong_side_cap_five"]["met"] and d["wrong_side_cap_five"]["fifth"] == "5/100"
          and d["met"], d)
    d = d_of(fourth=spec(five=(100, 100, 5), **hi), fifth=spec(five=(100, 100, 6), **hi), main=spec(five=(100, 100, 5), **hi))
    check("2c: one more bid on the five is not met though 2a and 2b are met", not d["wrong_side_cap_five"]["met"]
          and d["wrong_side_vs_fourth"]["met"] and d["wrong_side_vs_main"]["met"] and not d["met"], d)
    d = d_of(fourth=spec(five=(100, 100, 5), **hi), fifth=spec(five=(40, 40, 2), twelve=(260, 260, 24)), main=spec(five=(100, 100, 5), **hi))
    check("2c: 2 of 40 on the five is exactly 5% (exact fractions): met", d["wrong_side_cap_five"]["met"], d)
    d = d_of(fourth=spec(five=(100, 100, 5), **hi), fifth=spec(five=(40, 40, 3), twelve=(260, 260, 23)), main=spec(five=(100, 100, 5), **hi))
    check("2c: 3 of 40 on the five is not met", not d["wrong_side_cap_five"]["met"], d)
    d = d_of(fifth=spec(five=(100, 100, 0), twelve=(200, 200, 30)), fourth=spec(five=(100, 100, 0), twelve=(200, 200, 30)),
             main=spec(five=(100, 100, 0), twelve=(200, 200, 30)))
    check("2c: wrong bids on the twelve do not count in the cap (30 of 300 overall, 0 of 100 on the five)",
          d["wrong_side_cap_five"]["met"] and d["wrong_side_cap_five"]["fifth"] == "0/100", d)
    # (2d) matched
    d = d_of(fourth=spec(**dict(GOOD, m=300, r=300)), fifth=spec(**dict(GOOD, m=291, r=300)))
    check("2d: exactly 3.0 points lower is met", d["matched"]["met"] and d["met"], d)
    d = d_of(fourth=spec(**dict(GOOD, m=300, r=300)), fifth=spec(**dict(GOOD, m=290, r=300)))
    check("2d: one fewer matched is not met", not d["matched"]["met"] and not d["met"], d)
    # (2e) level
    d = d_of(fifth=spec(**dict(GOOD, l=14)))
    check("2e: 14 of 300 (just under 5%) is met", d["level"]["met"] and d["met"], d)
    d = d_of(fifth=spec(**dict(GOOD, l=15)))
    check("2e: 15 of 300 (exactly 5%) is not met (strict)", not d["level"]["met"] and not d["met"], d)
    check("2e: 19 of 400 is met, 20 of 400 is not", d_of(fifth=spec(five=(100, 100, 1), twelve=(300, 300, 8), l=19, m=280, r=300))["level"]["met"]
          and not d_of(fifth=spec(five=(100, 100, 1), twelve=(300, 300, 8), l=20, m=280, r=300))["level"]["met"])
    # zero denominators, one clause at a time
    unscored = dict(five=(100, 0, 0), twelve=(200, 0, 0))
    d = d_of(fourth=spec(**dict(GOOD, **unscored)))
    check("zero scored bids in the fourth book: 2a not met", not d["wrong_side_vs_fourth"]["met"] and not d["met"], d)
    d = d_of(fifth=spec(**dict(GOOD, **unscored)))
    check("zero scored bids in the fifth book (--dir): 2a and 2c not met", not d["wrong_side_vs_fourth"]["met"]
          and not d["wrong_side_cap_five"]["met"], d)
    d = d_of(main=spec(**dict(GOOD, **unscored)))
    check("zero scored bids in the main book: 2b not met, 2a still met", not d["wrong_side_vs_main"]["met"]
          and d["wrong_side_vs_fourth"]["met"] and not d["met"], d)
    d = d_of(fifth_b=spec(**dict(GOOD, **unscored)))
    check("zero scored bids in the fifth book (--dir-main): 2b not met, 2a and 2c still met", not d["wrong_side_vs_main"]["met"]
          and d["wrong_side_vs_fourth"]["met"] and d["wrong_side_cap_five"]["met"], d)
    d = d_of(fifth=spec(**dict(GOOD, five=(100, 0, 0))))
    check("zero scored bids on the five only: 2c not met, 2a met", not d["wrong_side_cap_five"]["met"]
          and d["wrong_side_vs_fourth"]["met"] and not d["met"], d)
    d = d_of(fourth=spec(**dict(GOOD, m=0, r=0)))
    check("zero research bids in the fourth book: 2d not met", not d["matched"]["met"], d)
    d = d_of(fifth=spec(**dict(GOOD, m=0, r=0)))
    check("zero research bids in the fifth book: 2d not met", not d["matched"]["met"], d)
    d = d_of(fifth=spec(**dict(GOOD, nl=0)))
    check("zero bids with a level in the fifth book: 2e not met", not d["level"]["met"], d)
    check("all good: measure 2 met", d_of()["met"] and all(d_of()[k]["met"] for k in
                                                           ("wrong_side_vs_fourth", "wrong_side_vs_main", "wrong_side_cap_five", "matched", "level")))
    # the five must be exactly ETH, LTC, SOL, XRP, ZEC
    for name, five in (("four coins", FIVE[:4]), ("six coins", FIVE + ["BCH"]), ("another coin", FIVE[:4] + ["BCH"])):
        g = {"all": ALL, "trades list": five, "candle path": TWELVE}
        check(f"the group 'trades list' of --dir with {name} is an error", raises(lambda: run(groups=g), "trades list") or
              raises(lambda: run(groups=g), "17 traded coins"), name)
    g = {"all": ALL, "trades list": FIVE, "candle path": TWELVE}
    check("the group 'trades list' in the right order or not: only the set matters",
          run(groups={"all": ALL, "trades list": list(reversed(FIVE)), "candle path": TWELVE})["verdict"] == "pass")
    check("the check of the five is made on --dir: an error in the group names the five",
          raises(lambda: p3b.five_coins({"groups": {"trades list": FIVE[:4]}}), "exactly ETH, LTC, SOL, XRP, ZEC"))


def test_reported_and_verdict():
    hi = dict(twelve=(200, 200, 20))
    kw = dict(fourth=spec(five=(100, 100, 0), **hi), fifth=spec(five=(100, 100, 0), **hi), main=spec(five=(100, 100, 0), **hi))
    res = run(**kw)
    md = p3b.to_md(res)
    check("all 17 coins above 5% with every clause met: a pass", res["verdict"] == "pass" and all(res["holds"].values()), res["holds"])
    check("the all-17 share above 5%: the reported line says the first run's cap would not be met",
          "the first run's cap (reported only): would not be met" in md and "would be met (5%)" not in md
          and res["reported"]["first_run_cap"]["would_be_met"] is False and res["reported"]["first_run_cap"]["fifth"] == "20/300", md)
    check("the pass has the verdict line of the second run", "**Part 3, second run: pass**" in md and "Part 3: pass" not in md)
    res = run()
    check("all-17 share at or below 5%: the reported line says it would be met",
          "the first run's cap (reported only): would be met" in p3b.to_md(res) and res["reported"]["first_run_cap"]["would_be_met"])
    check("the cap of all 17 coins decides nothing: 15 of 300 is exactly 5% and 16 of 300 passes too when the controls agree",
          run(fourth=spec(five=(100, 100, 0), twelve=(200, 200, 16)), fifth=spec(five=(100, 100, 0), twelve=(200, 200, 16)),
              main=spec(five=(100, 100, 0), twelve=(200, 200, 16)))["verdict"] == "pass")
    R = run(fourth=spec(five=(100, 100, 3), twelve=(200, 200, 12)), fifth=spec(five=(100, 100, 4), twelve=(200, 200, 14)),
            main=spec(five=(100, 100, 2), twelve=(200, 200, 10)), fifth_b=spec(five=(100, 100, 4), twelve=(200, 200, 14)))["reported"]
    check("reported: the twelve and the five apart for the fifth and fourth books, and the main book's share",
          R["groups"]["twelve"]["fifth"] == "14/200" and R["groups"]["twelve"]["fourth"] == "12/200"
          and R["groups"]["five"]["fifth"] == "4/100" and R["groups"]["five"]["fourth"] == "3/100"
          and R["main_all"]["wrong_side"] == "12/300" and R["decides"] == "nothing", R)
    # each of measures 1, 3 and 4 failing alone gives a fail
    res = run(pairs=t3.prs(["0.01"] * 8))
    check("measure 1 fails alone: fail", res["verdict"] == "fail" and res["holds"] == {"1": False, "2": True, "3": True, "4": True}, res["holds"])
    res = run(r5=t3.hbs([10.1] * 100))
    check("measure 1 (b) fails alone: fail", res["verdict"] == "fail" and res["holds"] == {"1": False, "2": True, "3": True, "4": True}, res["holds"])
    res = run(items="fail")
    check("measure 3 fails alone: fail", res["verdict"] == "fail" and res["holds"] == {"1": True, "2": True, "3": False, "4": True}, res["holds"])
    res = run(r5=t3.hbs([10.0] * 100, dict(pre_fetched=1, pre_error=1)))
    check("measure 4 fails alone: fail", res["verdict"] == "fail" and res["holds"] == {"1": True, "2": True, "3": True, "4": False}, res["holds"])
    res = run(r5=t3.hrows([10.0] * 100))
    check("measure 4: counters absent from every heartbeat is not met", res["verdict"] == "fail" and not res["holds"]["4"])
    res = run(fifth=spec(**dict(GOOD, l=20)))
    check("measure 2 fails alone: fail", res["verdict"] == "fail" and res["holds"] == {"1": True, "2": False, "3": True, "4": True}, res["holds"])
    check("measures 1 and 4 use part3_rule's functions: same numbers as the first rule on the same rows",
          run()["measures"]["step"]["b"] == t3.p3.measure1(t3.hbs([10.0] * 100), t3.hrows([10.0] * 100), t3.hrows([10.0] * 100),
                                                          t3.GOOD_PAIRS, START, END)["b"])
    check("bad items value is an error", raises(lambda: run(items="unread"), "pass or fail"))
    # the period condition: 300 new bids in the fifth and in the fourth book (--dir), none for the main book
    res = run(fifth=spec(five=(100, 100, 0), twelve=(199, 199, 0)))
    check("period: 299 bids in the fifth book: not complete, no verdict", not res["condition"]["met"] and res["verdict"] is None)
    res = run(fourth=spec(five=(100, 100, 0), twelve=(199, 199, 0)))
    check("period: 299 bids in the fourth book: not complete, no verdict", not res["condition"]["met"] and res["verdict"] is None)
    res = run(main=spec(five=(1, 1, 0), twelve=(1, 1, 0)))
    check("period: the main book has no minimum (2 bids), its count is printed", res["condition"]["met"] and res["condition"]["new_bids_main"] == 2
          and "2 new bids" in p3b.to_md(res) and res["verdict"] in ("pass", "fail"))
    res = run(fifth=spec(five=(100, 100, 0), twelve=(199, 199, 0)), read_as_is=True)
    check("period: --read-as-is gives the verdict and says so", res["verdict"] in ("pass", "fail") and "read as is" in p3b.to_md(res))
    md = p3b.to_md(run(fifth=spec(five=(100, 100, 0), twelve=(199, 199, 0))))
    check("period: PERIOD NOT COMPLETE and the no-verdict line of the second run", "PERIOD NOT COMPLETE" in md
          and "**Part 3, second run: no verdict (period not complete)**" in md and "Part 3, second run: pass" not in md)
    check("period: 300 in each is complete", run()["condition"]["met"])


def test_guards():
    check("--dir-main with the wrong books (the fourth book where the main book belongs) is an error",
          raises(lambda: run(books_main=("paper_spot_t18", "paper_spot_r5")), "--dir-main is not a main-book"))
    check("--dir-main with the fifth book wrong is an error", raises(lambda: run(books_main=("paper_spot", "paper_spot_tb")), "--dir-main"))
    check("--dir-main with the books swapped is an error", raises(lambda: run(books_main=("paper_spot_r5", "paper_spot")), "--dir-main"))
    check("--dir-main with the wrong end of period is an error", raises(lambda: run(end_main="2026-11-23 00:35"), "--dir-main's period"))
    check("--dir-main with the wrong start of period is an error", raises(lambda: run(start_main="2026-11-20 00:31"), "--dir-main's period"))
    g16 = {"all": ALL[:16], "trades list": FIVE, "candle path": TWELVE}
    check("--dir-main whose group 'all' is not the 17 coins is an error", raises(lambda: run(groups_main=g16), "17 traded coins"))
    g18 = {"all": ALL + ["BTC"], "trades list": FIVE, "candle path": TWELVE}
    check("--dir-main with eighteen coins in group 'all' is an error", raises(lambda: run(groups_main=g18), "17 traded coins"))
    check("--dir with the wrong books is an error", raises(lambda: run(books=("paper_spot", "paper_spot_r5")), "not a fourth-book"))
    check("--dir with the wrong period is an error", raises(lambda: p3b.p3.guard(folder(spec(), spec(), BOOKS)[0], "paper_spot_t18", "paper_spot_r5", START,
                                                                                  "2026-11-23 00:35"), "differs"))
    # a count mismatch with side_by_side.csv is an error in both folders
    check("a count mismatch in --dir-main (wrong-side bids of the main book) is an error",
          raises(lambda: run(over_main={("main", "m2_score_error", "n_other_side"): 5}), "wrong-side"))
    check("a count mismatch in --dir-main (new bids of the fifth book) is an error",
          raises(lambda: run(over_main={("tb", "m3_bids", "bot_new_bids"): 301}), "new bids"))
    check("a count mismatch in --dir-main (bids with a level) is an error", raises(lambda: run(over_main={("main", "m1_level_error", "n"): 5}), "with a level"))
    check("a count mismatch in --dir-main (scored bids) is an error", raises(lambda: run(over_main={("tb", "m2_score_error", "n"): 5}), "scored bids"))
    check("a count mismatch in --dir (wrong-side bids of the fifth book) is an error",
          raises(lambda: run(over={("tb", "m2_score_error", "n_other_side"): 5}), "wrong-side"))
    check("a count mismatch in --dir (new bids of the fourth book) is an error", raises(lambda: run(over={("main", "m3_bids", "bot_new_bids"): 301}), "new bids"))
    check("the five-coin counts are cross-checked: a matching case passes", run()["verdict"] == "pass")
    check("a mismatch in the five's scored bids (n) against side_by_side.csv is an error",
          raises(lambda: run(over={("tb", "trades list", "n"): 99}), "scored bids on the five coins"))
    check("a mismatch in the five's wrong-side bids (n_other_side) against side_by_side.csv is an error",
          raises(lambda: run(over={("tb", "trades list", "n_other_side"): 3}), "wrong-side bids on the five coins"))
    meta, B, S = folder(spec(), spec(), BOOKS)
    S3 = S[S.group != "trades list"]
    check("a side_by_side.csv without the 'trades list' rows is an error", raises(lambda: p3b.five_counts(B, S3), "expected one row"))
    check("the five's counts equal side_by_side.csv when they match", p3b.five_counts(B, S) == (0, 100))
    meta, B, S = folder(spec(), spec(), BOOKS_MAIN)
    S2 = S[~((S.book == "main") & (S.statistic == "research_matched"))]
    check("a missing side_by_side row in --dir-main is an error",
          raises(lambda: p3b.p3.book_counts(B, S2, "main", ALL), "expected one row"))
    meta, B, S = folder(spec(), spec(), BOOKS)
    extra = pd.DataFrame([dict(book="tb", ts="x", coin="BTC", err_bp=50.0, res_score=1.0, res_other_side=True)] * 5)
    check("coins outside the 17 are ignored in the five's count",
          p3b.scored(pd.concat([B, extra], ignore_index=True), "tb", FIVE) == (0, 100))
    check("the commit argument must be 40 lower-case hex characters",
          all(not _ok(x) for x in ("9e6f53b", COMMIT.upper(), COMMIT + "0", "")) and _ok(COMMIT))


def _ok(text):
    try:
        p3b.commit_arg(text)
        return True
    except Exception:
        return False


def write_pairs(pdir, n_right, n_other, no_commit=0, bad_count=0):
    os.makedirs(pdir, exist_ok=True)
    k = 0
    for commit, n in ((COMMIT, n_right), (OTHER_COMMIT, n_other), (None, no_commit)):
        for _ in range(n):
            runs = [dict(inputs="release3", data_end_median_text="10.00"), dict(inputs="build", data_end_median_text="9.90")]
            o = dict(utc_start=f"2026-11-2{k // 4}T{(k % 4) * 6:02d}:35:00Z", order="ab", counts=True, runs=runs)
            if commit:
                o["code_commit"] = commit
            json.dump(o, open(os.path.join(pdir, f"pair_{k:02d}.json"), "w"))
            k += 1


def test_pairs():
    with tempfile.TemporaryDirectory() as tmp:
        pdir = os.path.join(tmp, "pairs")
        write_pairs(pdir, 8, 3, no_commit=1)
        keep, other = p3b.split_pairs(pdir, COMMIT)
        check("pair files: 8 of the right commit are passed on, 3 of another commit and 1 without a commit are set aside and counted",
              len(keep) == 8 and other == 4 and all(p["counts"] for p in keep), (len(keep), other))
        keep2, other2 = p3b.split_pairs(pdir, OTHER_COMMIT)
        check("pair files: another commit named gives its own pairs only", len(keep2) == 3 and other2 == 9)
        keep3, other3 = p3b.split_pairs(os.path.join(tmp, "none"), COMMIT)
        check("pair files: a missing folder is no pairs", keep3 == [] and other3 == 0)
        res = run(pairs=keep, pairs_other=other)
        md = p3b.to_md(res)
        check("pairs of another commit: the count is in the output (md and json)", res["measures"]["step"]["pairs_of_another_commit"] == 4
              and "Pairs of another commit: 4" in md and json.loads(json.dumps(res))["measures"]["step"]["pairs_of_another_commit"] == 4)
        check("8 pairs of the right commit: measure 1 (a) met with the median of the right pairs only",
              res["measures"]["step"]["a"]["pairs"] == 8 and res["measures"]["step"]["a"]["median_s"] == -0.1 and res["verdict"] == "pass")
        # the pairs of the other commit are not used even when they would make 8
        pdir2 = os.path.join(tmp, "pairs2")
        write_pairs(pdir2, 7, 5)
        keep, other = p3b.split_pairs(pdir2, COMMIT)
        res = run(pairs=keep, pairs_other=other)
        md = p3b.to_md(res)
        check("fewer than 8 of the right commit: the first rule's not-complete behaviour (line, no verdict), others counted",
              other == 5 and res["verdict"] is None and "PART (a) NOT COMPLETE: 7 of 8 pairs count; the pair jobs go on and the read waits"
              in md.splitlines() and "no verdict (part (a) not complete)" in md and "Pairs of another commit: 5" in md
              and "Part 3, second run: pass" not in md and "Part 3, second run: fail" not in md, md[:700])
        res = run(pairs=keep, pairs_other=other, read_as_is=True)
        check("fewer than 8 of the right commit with --read-as-is: fail, part (a) not met",
              res["verdict"] == "fail" and not res["measures"]["step"]["a"]["met"] and "Read as is: part (a) is not met." in p3b.to_md(res))
        # a pair of the right commit after the period is added as in the first rule
        later = t3.pr("-1", hours=73)
        res = run(pairs=t3.prs(["-1"] * 7) + [later], pairs_other=2)
        a = res["measures"]["step"]["a"]
        check("a later pair of the right commit is added as in the first rule", a["pairs"] == 8 and a["added"] == 1 and a["met"]
              and res["verdict"] == "pass")
        res = run(pairs=[], pairs_other=16)
        check("no pair of the right commit: not complete, no verdict, 16 counted", res["verdict"] is None
              and "PART (a) NOT COMPLETE: 0 of 8 pairs count" in p3b.to_md(res) and "Pairs of another commit: 16" in p3b.to_md(res))


def test_md_json_and_cli():
    res = run(fifth=spec(**dict(GOOD, l=20)), pairs_other=3)
    md = p3b.to_md(res)
    js = json.loads(json.dumps(res))
    d, c = js["measures"]["decisions"], js["counts"]
    check("md and json agree on the verdict (fail through measure 2)", js["verdict"] == "fail" and "**Part 3, second run: fail**" in md
          and "Measure 2: not met" in md)
    check("md and json agree on every count of measure 2",
          all(d[k][f] in md for k, f in (("wrong_side_vs_fourth", "fifth"), ("wrong_side_vs_fourth", "fourth"), ("wrong_side_vs_main", "fifth"),
                                         ("wrong_side_vs_main", "main"), ("wrong_side_cap_five", "fifth"), ("matched", "fifth"),
                                         ("matched", "fourth"), ("level", "fifth")))
          and d["level"]["fifth"] == f"{c['fifth']['l']}/{c['fifth']['nl']}" == "20/300"
          and d["wrong_side_vs_main"]["main"] == f"{c['main']['w']}/{c['main']['ns']}"
          and d["wrong_side_cap_five"]["fifth"] == f"{c['fifth_five']['w']}/{c['fifth_five']['ns']}")
    check("md has the heading of the second run and a closing paragraph 'Rule in plain words'",
          md.startswith("# Part 3, second run") and "Rule in plain words:" in md.splitlines()[-2] + md.splitlines()[-1] + md[-2500:])
    ok = p3b.to_md(run())
    check("md for a pass has one verdict line and a table per measure", ok.count("Part 3, second run: pass") == 1
          and all(h in ok for h in ("## Measure 1, the step", "## Measure 2, decisions against the research", "## Measure 3", "## Measure 4")))
    js = json.loads(json.dumps(run()))
    check("json holds the four measures and the holds", set(js["measures"]) == {"step", "decisions", "items_1_5", "candle_requests"}
          and js["holds"] == {"1": True, "2": True, "3": True, "4": True} and js["rule"] == "part 3, second run")
    with tempfile.TemporaryDirectory() as tmp:
        n = 120
        d5 = t3.write_log(tmp, "paper_spot_r5", [10.0] * n, dict(t3.GOOD4, tb_built=540))
        d4 = t3.write_log(tmp, "paper_spot_t18", [10.5] * n)
        dm = t3.write_log(tmp, "paper_spot", [10.2] * n)
        dirs = []
        for name, books, first, second in (("rec", BOOKS, spec(**GOOD), spec(**GOOD)), ("recm", BOOKS_MAIN, spec(**GOOD), spec(**GOOD))):
            meta, B, S = folder(first, second, books)
            os.makedirs(os.path.join(tmp, name))
            json.dump(meta, open(os.path.join(tmp, name, "two_books.json"), "w"))
            B.to_csv(os.path.join(tmp, name, "item7_bids.csv"), index=False)
            S.to_csv(os.path.join(tmp, name, "side_by_side.csv"), index=False)
            dirs.append(os.path.join(tmp, name))
        pdir = os.path.join(tmp, "pairs")
        write_pairs(pdir, 8, 2)
        out = os.path.join(tmp, "out")
        cmd = [sys.executable, os.path.join(HERE, "part3b_rule.py"), "--dir", dirs[0], "--dir-main", dirs[1], "--pairs", pdir,
               "--start", "2026-11-20T00:30", "--end", "2026-11-23T00:29", "--fifth", d5, "--fourth", d4, "--main", dm,
               "--items-1-5", "pass", "--pair-commit", COMMIT, "--out", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        check("cli runs", r.returncode == 0, r.stderr[-500:])
        js = json.load(open(os.path.join(out, "part3b_rule.json")))
        md = open(os.path.join(out, "part3b_rule.md")).read()
        check("cli: prints the markdown it writes", r.stdout.strip() == md.strip())
        check("cli: verdict pass, 8 pairs of the commit used, 2 of another commit set aside",
              js["verdict"] == "pass" and "**Part 3, second run: pass**" in md and js["measures"]["step"]["a"]["pairs"] == 8
              and js["measures"]["step"]["pairs_of_another_commit"] == 2 and "Pairs of another commit: 2" in md, js["holds"])
        check("cli: the output goes to --out and nothing is written into --dir",
              not os.path.exists(os.path.join(dirs[0], "part3b_rule.md")))
        r = subprocess.run(cmd[:-2], capture_output=True, text=True)
        check("cli: without --out the files go to --dir", r.returncode == 0 and os.path.exists(os.path.join(dirs[0], "part3b_rule.json")))
        r = subprocess.run([c if c != COMMIT else COMMIT[:7] for c in cmd], capture_output=True, text=True)
        check("cli: a short --pair-commit is refused", r.returncode != 0 and "40-character" in r.stderr)
        idx = cmd.index("--pair-commit")
        r = subprocess.run(cmd[:idx] + cmd[idx + 2:], capture_output=True, text=True)
        check("cli: --pair-commit is required", r.returncode != 0 and "--pair-commit" in r.stderr)
        idx = cmd.index("--dir-main")
        r = subprocess.run(cmd[:idx] + cmd[idx + 2:], capture_output=True, text=True)
        check("cli: --dir-main is required", r.returncode != 0 and "--dir-main" in r.stderr)
        r = subprocess.run(cmd[:cmd.index("--end") + 1] + ["2026-11-20T09:59"] + cmd[cmd.index("--end") + 2:], capture_output=True, text=True)
        check("cli: a period that differs from the folders' is refused", r.returncode != 0 and "differs" in r.stderr)
        r = subprocess.run([c if c != dirs[1] else dirs[0] for c in cmd], capture_output=True, text=True)
        check("cli: the fourth-book folder given as --dir-main is refused", r.returncode != 0 and "--dir-main is not a main-book" in r.stderr)


def main():
    for t in (test_measure2, test_reported_and_verdict, test_guards, test_pairs, test_md_json_and_cli):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
