"""Offline tests of the Part 3 rule (part3_rule.py) on small made-up folders and logs. Run:
python scripts/owner/bar_source/test_part3_rule.py (prints ok / FAIL per check, last line "N checks passed", non-zero
exit on any failure)."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pandas as pd         # noqa: E402

import part3_rule as p3     # noqa: E402

TRADES = ["ETH", "LTC", "SOL", "XRP", "ZEC"]
CANDLE = ["AAVE", "BCH", "DOGE", "ENA", "HBAR", "HYPE", "LINK", "NEAR", "ONDO", "PEPE", "SUI", "XLM"]
ALL = TRADES + CANDLE
FAILS = []
COUNT = [0]
T0 = datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)


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


def spec(n=300, w=0, ns=None, l=0, nl=None, m=None, r=None):
    """One book: n bids, ns with a score (w on the wrong side), nl with a level (l of them more than 5 bp away),
    research matched m of r."""
    return dict(n=n, w=w, ns=n if ns is None else ns, l=l, nl=n if nl is None else nl, m=n if m is None else m,
                r=n if r is None else r)


def rows_for(label, s):
    out = []
    for i in range(s["n"]):
        has_sc, has_lv = i < s["ns"], i < s["nl"]
        err = float("nan")
        if has_lv:
            err = (6.0 if i % 2 == 0 else -6.0) if i < s["l"] else (5.0 if i % 2 == 0 else -4.0)
        out.append(dict(book=label, ts="2026-11-21 00:00:00", coin=ALL[i % 17], err_bp=err,
                        res_score=1.0 if has_sc else float("nan"), res_other_side=bool(has_sc and i < s["w"])))
    return out


def side(label, s, over):
    vals = {("m3_bids", "bot_new_bids"): s["n"], ("m2_score_error", "n"): s["ns"], ("m2_score_error", "n_other_side"): s["w"],
            ("m1_level_error", "n"): s["nl"], ("m3_bids", "research_matched"): s["m"],
            ("m3_bids", "research_new_bids_ex_blocked"): s["r"]}
    out = []
    for (me, st), v in vals.items():
        v = over.get((label, me, st), v)
        out.append(dict(measure=me, statistic=st, group="all", book=label, value=float(v)))
        out.append(dict(measure=me, statistic=st, group="candle path", book=label, value=999.0))
    return out


def tables(fourth, fifth, over=None, groups=None, books=("paper_spot_t18", "paper_spot_r5"), start="2026-11-20 00:30",
             end="2026-11-23 00:29"):
    over = over or {}
    meta = dict(period=dict(start=start, end=end), books=dict(main=books[0], tb=books[1]),
                minutes=dict(main=4300, tb=4310, common=4290),
                groups=groups or {"all": ALL, "trades list": TRADES, "candle path": CANDLE})
    B = pd.DataFrame(rows_for("main", fourth) + rows_for("tb", fifth))
    S = pd.DataFrame(side("main", fourth, over) + side("tb", fifth, over))
    return meta, B, S


def hrows(meds, offset=1):
    """Data-quality-like rows of heartbeats k = offset.. with these data-step medians (None: no data step)."""
    return [dict(t=T0 + timedelta(minutes=30 * (offset + i)), data=None if m is None else (m, m + 1.0), counts={}, minutes=30.0)
            for i, m in enumerate(meds)]


def crow(k, minutes=30.0, **counts):
    return dict(t=T0 + timedelta(minutes=30 * k), data=None, counts=counts, minutes=minutes)


GOOD4 = dict(pre_fetched=1000, pre_error=0, pre_missing=1, pre_ondemand=0, step_candles=300)


def run(fourth=None, fifth=None, items="pass", r5=None, rmain=None, rfourth=None, c4=None, **kw):
    fourth = fourth or spec(300, w=9, l=3, m=280, r=300)
    fifth = fifth or spec(300, w=9, l=3, m=280, r=300)
    over = kw.pop("over", None)
    pairs = kw.pop("pairs", GOOD_PAIRS)
    meta, B, S = tables(fourth, fifth, over)
    r5 = r5 if r5 is not None else hrows([10.0] * 100)
    rmain = rmain if rmain is not None else hrows([10.0] * 100)
    rfourth = rfourth if rfourth is not None else hrows([10.0] * 100)
    rows = r5 if r5 and r5[0]["counts"] else r5
    return p3.evaluate(meta, B, S, rows, [], rmain, rfourth, items, start="2026-11-20 00:30", end="2026-11-23 00:29",
                       pairs=pairs, **kw)


def with_counters(rows, **c):
    return [dict(r, counts=dict(c)) for r in rows]


def hbs(meds, counters=None, offset=1):
    return with_counters(hrows(meds, offset), **(GOOD4 if counters is None else counters)) if counters != {} else hrows(meds, offset)


PERIOD_START = datetime(2026, 11, 20, 0, 30, tzinfo=timezone.utc)


def pr(diff, hours=1, counts=True, order="ab"):
    """A pair as ps.load_pairs gives it: starts `hours` hours after the period's start; diff is build minus release 3 (text)."""
    return dict(file=f"pair_{hours}_{diff}.json", start=PERIOD_START + timedelta(hours=hours), order=order, counts=counts,
                why=None if counts else "x", release3="10.00", build="10.00", diff=Fraction(diff))


def prs(diffs, **kw):
    return [pr(d, hours=i + 1, **kw) for i, d in enumerate(diffs)]


GOOD_PAIRS = prs(["0"] * 8)


def test_measure1():
    def a_of(pairs, **kw):
        return run(pairs=pairs, **kw)["measures"]["step"]["a"]
    a = a_of(prs(["0"] * 8))
    check("m1 (a): eight pairs with median exactly zero is met", a["met"] and a["pairs"] == 8 and a["median_s"] == 0.0, a)
    a = a_of(prs(["-0.01"] * 4 + ["0.01"] * 4))
    check("m1 (a): even count, mean of the two middle values (-0.01 and 0.01) is exactly zero: met", a["met"] and a["median_exact"] == "0", a)
    a = a_of(prs(["-0.02"] * 3 + ["0", "0.01"] + ["0.01"] * 3))
    check("m1 (a): even count, middle values 0 and 0.01 give 0.005: not met", not a["met"] and a["median_exact"] == "1/200", a)
    a = a_of(prs(["0.01"] * 8))
    check("m1 (a): the smallest positive step (0.01 s) is not met", not a["met"] and a["median_s"] == 0.01, a)
    a = a_of(prs(["-5.18"] * 8))
    check("m1 (a): a faster build is met", a["met"] and a["median_s"] == -5.18)
    a = a_of(prs(["-1"] * 3 + ["0"] * 3 + ["1"] * 2))
    check("m1 (a): median is -1, 0 or +1 by position, not the mean (middle values 0 and 0 here)", a["met"] and a["median_exact"] == "0")
    a = a_of(prs(["-9"] * 7))
    check("m1 (a): 7 pairs against 8: seven is not met however good", not a["met"] and not a["enough"] and a["pairs"] == 7, a)
    check("m1 (a): eight is enough", a_of(prs(["-9"] * 8))["enough"])
    a = a_of(prs(["-9"] * 7) + [pr("-9", hours=9, counts=False)])
    check("m1 (a): a pair that does not count is left out (7 count)", a["pairs"] == 7 and not a["met"], a)
    outside = [pr("5", hours=-2), pr("5", hours=24 * 3 + 1)]
    a = a_of(prs(["0"] * 8) + outside)
    check("m1 (a): pairs starting before or after the period are left out of the median", a["pairs"] == 8 and a["met"] and a["median_s"] == 0.0, a)
    a = a_of(prs(["-1"] * 7) + [pr("-1", hours=72 - 1)])
    check("m1 (a): a pair starting inside the last hour of the period counts", a["pairs"] == 8, a)
    end_in = datetime(2026, 11, 23, 0, 29, 30, tzinfo=timezone.utc)
    p_end = dict(pr("0"), start=end_in)
    p_after = dict(pr("0"), start=datetime(2026, 11, 23, 0, 30, 0, tzinfo=timezone.utc))
    # edited: with the pairs-after-the-period rule a pair starting a minute after the end is not in the period but is added
    # when fewer than 8 count in it, so the check now reads in_period and added instead of the count alone
    a_end, a_next = a_of(prs(["0"] * 7) + [p_end]), a_of(prs(["0"] * 7) + [p_after])
    check("m1 (a): the period's end minute is included, the next minute is not (it is added, not in the period)",
          a_end["pairs"] == 8 and a_end["in_period"] == 8 and a_end["added"] == 0
          and a_next["in_period"] == 7 and a_next["added"] == 1 and a_next["pairs"] == 8)
    a = a_of([])
    check("m1 (a): no pairs is not met", not a["met"] and a["pairs"] == 0 and a["median_s"] is None)
    a = a_of(prs(["-1", "1"] * 4, order="ba"))
    check("m1 (a): both orders mixed give one median", a["met"] and a["pairs"] == 8)
    # (a) alone does not decide: (b) must hold too
    res = run(pairs=prs(["-9"] * 8), r5=hbs([10.1] * 100), rmain=hrows([10.0] * 100))
    check("m1: (a) met and (b) failed: measure 1 not met", res["measures"]["step"]["a"]["met"] and not res["measures"]["step"]["b"]["met"]
          and not res["measures"]["step"]["met"])
    res = run(pairs=prs(["0.01"] * 8), r5=hbs([10.0] * 100), rmain=hrows([10.1] * 100))
    check("m1: (b) met and (a) failed: measure 1 not met", not res["measures"]["step"]["a"]["met"] and res["measures"]["step"]["b"]["met"]
          and not res["measures"]["step"]["met"])
    # the 10.3 s comparison is reported and decides nothing
    res = run(pairs=prs(["0"] * 8), r5=hbs([12.0] * 100), rmain=hrows([13.0] * 100))
    rep = res["measures"]["step"]["reported"]
    check("m1: a fifth-book median of 12 s (above 10.3) is reported and does not fail the measure", res["measures"]["step"]["met"]
          and rep["fifth_own_median_s"] == 12.0 and rep["at_or_below_bar"] is False and rep["decides"] == "nothing", rep)
    check("m1: the report names it as reported only", "reported, decides nothing" in p3.to_md(res) and "above 10.3 s" in p3.to_md(res))
    # (b) as before
    res = run(r5=hbs([10.0] * 100), rmain=hrows([10.0] * 100))
    check("m1 (b): equal medians pass", res["measures"]["step"]["b"]["met"])
    res = run(r5=hbs([10.1] * 100), rmain=hrows([10.0] * 100))
    check("m1 (b): fifth just higher fails", not res["measures"]["step"]["b"]["met"] and not res["measures"]["step"]["met"])
    res = run(r5=hbs([10.0] * 100), rmain=hrows([10.1] * 100))
    check("m1 (b): fifth lower passes", res["measures"]["step"]["b"]["met"])
    res = run(r5=hbs([10.0] * 99))
    check("m1 (b): 99 fifth-book heartbeats is not met, 100 is", not res["measures"]["step"]["b"]["met"]
          and not res["measures"]["step"]["b"]["enough"] and run(r5=hbs([10.0] * 100))["measures"]["step"]["b"]["met"])
    res = run(r5=hbs([10.0] * 100), rmain=hrows([10.0] * 99, offset=2))
    b = res["measures"]["step"]["b"]
    check("m1 (b): 99 shared heartbeat times is not met", b["paired_half_hours"] == 99 and not b["met"], b)
    res = run(r5=hbs([10.0] * 100), rmain=hrows([10.0] * 100 + [1.0] * 300, offset=1))
    b = res["measures"]["step"]["b"]
    check("m1 (b): main heartbeats at times the fifth lacks are left out", b["paired_half_hours"] == 100 and b["main_median_s"] == 10.0, b)
    res = run(r5=hbs([10.0] * 100), rmain=[])
    check("m1 (b): no main heartbeats is not met", not res["measures"]["step"]["b"]["met"])
    res = run(r5=hbs([10.0] * 100), rfourth=hrows([9.0] * 100))
    check("m1: the fourth book is for information only", res["measures"]["step"]["fourth_for_information"]["fourth_median_s"] == 9.0
          and res["measures"]["step"]["met"])
    # pairs read from files, both orders: the difference is always build minus release 3
    with tempfile.TemporaryDirectory() as tmp:
        for i, (order, r3, bd) in enumerate((("ab", "14.88", "9.70"), ("ba", "11.37", "11.37"), ("ab", "10.00", "10.01"), ("ba", "10.01", "10.00"))):
            runs = [dict(inputs="release3", data_end_median_text=r3), dict(inputs="build", data_end_median_text=bd)]
            if order == "ba":
                runs.reverse()
            json.dump(dict(utc_start=f"2026-11-20T0{i + 1}:05:00Z", order=order, counts=True, runs=runs),
                      open(os.path.join(tmp, f"pair_{i}.json"), "w"))
        got = p3.ps.load_pairs(tmp)
        check("pair files: differences are build minus release 3 for both orders, exact",
              [str(p["diff"]) for p in got] == ["-259/50", "0", "1/100", "-1/100"] and [p["order"] for p in got] == ["ab", "ba", "ab", "ba"], got)


def test_pairs_after_the_period():
    def later(diffs, first=73):
        return [pr(d, hours=first + i) for i, d in enumerate(diffs)]       # the period ends 72 hours less a minute after PERIOD_START
    r5 = hbs([10.0] * 100)
    # not complete: 5 in the period and 2 after
    pairs = prs(["-1"] * 5) + later(["-1"] * 2)
    res = run(r5=r5, pairs=pairs)
    md = p3.to_md(res)
    a = res["measures"]["step"]["a"]
    line = "PART (a) NOT COMPLETE: 7 of 8 pairs count; the pair jobs go on and the read waits"
    check("part (a) not complete: 7 of 8 count: the line is printed and there is no verdict",
          res["verdict"] is None and line in md.splitlines() and "Part 3: pass" not in md and "Part 3: fail" not in md
          and "no verdict (part (a) not complete)" in md and not a["met"] and not a["complete"] and a["pairs"] == 7, md[:900])
    check("part (a) not complete: the period condition itself is met and the other measures are read on the period",
          res["condition"]["met"] and not res["condition"]["part_a_complete"] and res["measures"]["step"]["b"]["met"]
          and res["measures"]["decisions"]["met"] and "PERIOD NOT COMPLETE" not in md)
    res = run(r5=r5, pairs=pairs, read_as_is=True)
    md = p3.to_md(res)
    check("part (a) not complete with --read-as-is: a verdict, part (a) not met", res["verdict"] == "fail" and not res["holds"]["1"]
          and not res["measures"]["step"]["a"]["met"] and "Part 3: fail" in md and "Read as is: part (a) is not met." in md, md[:900])
    # both incomplete: both reasons named
    res = run(r5=r5, pairs=pairs, fifth=spec(299))
    check("period and part (a) both not complete: no verdict, both stated", res["verdict"] is None
          and "no verdict (period not complete and part (a) not complete)" in p3.to_md(res))
    # no pairs at all
    res = run(r5=r5, pairs=[])
    check("no pairs: part (a) not complete, no verdict", res["verdict"] is None and "PART (a) NOT COMPLETE: 0 of 8 pairs count" in p3.to_md(res))
    # complete in the period: nothing added, the line is not printed
    res = run(r5=r5, pairs=prs(["0"] * 8) + later(["9"] * 3))
    a, md = res["measures"]["step"]["a"], p3.to_md(res)
    check("8 in the period: nothing added, later pairs unused, no part (a) line",
          res["verdict"] == "pass" and a["pairs"] == 8 and a["in_period"] == 8 and a["added"] == 0 and a["last_used_start"] is None
          and "NOT COMPLETE" not in md and "were added" not in md and len(a["pair_files"]) == 8)
    # a pass only through an added pair
    pairs = prs(["-1"] * 7) + later(["-1", "9", "9"])
    res = run(r5=r5, pairs=pairs)
    a, md = res["measures"]["step"]["a"], p3.to_md(res)
    last = pairs[7]["start"].strftime("%Y-%m-%dT%H:%M:%SZ")
    check("pass only through an added pair: 7 in the period and one added give a pass",
          res["verdict"] == "pass" and a["met"] and a["pairs"] == 8 and a["in_period"] == 7 and a["added"] == 1 and a["complete"]
          and a["last_used_start"] == last and a["pair_files"] == [p["file"] for p in pairs[:8]], a)
    check("pass only through an added pair: the markdown says how many started in the period, how many were added, the last start",
          f"7 started in the period and 1 were added from after it" in md and f"started {last} UTC" in md, md[:1200])
    check("the same case read as is without the later pairs is not met", run(r5=r5, pairs=pairs[:7], read_as_is=True)["verdict"] == "fail")
    check("the json keeps in_period, added, last_used_start and the files used",
          json.loads(json.dumps(res))["measures"]["step"]["a"]["added"] == 1)
    # a fail only through an added pair: the added pair moves the median above zero
    base = ["-1", "0", "0", "0", "1", "1", "1"]
    pairs = prs(base) + later(["1", "-9", "-9"])
    res = run(r5=r5, pairs=pairs)
    a = res["measures"]["step"]["a"]
    check("fail only through an added pair: the median of seven is 0, the added pair makes it 1/2 above zero",
          res["verdict"] == "fail" and a["pairs"] == 8 and a["added"] == 1 and a["median_exact"] == "1/2" and not a["met"] and a["complete"]
          and "NOT COMPLETE" not in p3.to_md(res) and run(r5=r5, pairs=prs(base) + later(["-1"]))["measures"]["step"]["a"]["median_exact"] == "0", a)
    # part (b) and measures 2 to 4 are read on the period: later pairs change nothing else
    res2 = run(r5=r5, pairs=prs(["-1"] * 7) + later(["-1"]))
    res1 = run(r5=r5, pairs=prs(["-1"] * 8))
    check("later pairs change only part (a): (b), measures 2 to 4 and the counts are the same",
          all(res1["measures"][k] == res2["measures"][k] for k in ("decisions", "items_1_5", "candle_requests"))
          and res1["measures"]["step"]["b"] == res2["measures"]["step"]["b"] and res1["counts"] == res2["counts"])


def test_measure2():
    def m2(f4, f5):
        return run(fourth=f4, fifth=f5)["measures"]["decisions"]
    # wrong side: fifth <= fourth + 2 points, and <= 5%. n = 300: 2 points = 6 bids
    d = m2(spec(300, w=0), spec(300, w=6))
    check("m2 wrong side: exactly fourth + 2.0 points passes", d["wrong_side_vs_fourth"]["met"], d)
    d = m2(spec(300, w=0), spec(300, w=7))
    check("m2 wrong side: just beyond fails", not d["wrong_side_vs_fourth"]["met"] and not d["met"])
    d = m2(spec(300, w=30), spec(300, w=15))
    check("m2 wrong side cap: exactly 5% passes", d["wrong_side_cap"]["met"] and d["wrong_side_vs_fourth"]["met"], d)
    d = m2(spec(300, w=30), spec(300, w=16))
    check("m2 wrong side cap: just over 5% fails though under the fourth plus 2 points",
          not d["wrong_side_cap"]["met"] and d["wrong_side_vs_fourth"]["met"] and not d["met"], d)
    d = m2(spec(300, w=1, ns=250), spec(400, w=2, ns=400, m=400, r=400))
    check("m2 wrong side: shares use the scored bids as denominators", d["wrong_side_vs_fourth"]["fifth"] == "2/400"
          and d["wrong_side_vs_fourth"]["fourth"] == "1/250", d)
    # matched: fifth >= fourth - 3 points
    d = m2(spec(300, m=300, r=300), spec(300, m=291, r=300))
    check("m2 matched: exactly fourth - 3.0 points passes", d["matched"]["met"], d)
    d = m2(spec(300, m=300, r=300), spec(300, m=290, r=300))
    check("m2 matched: just beyond fails", not d["matched"]["met"] and not d["met"])
    d = m2(spec(300, m=270, r=300), spec(300, m=270, r=300))
    check("m2 matched: equal shares pass", d["matched"]["met"])
    # level: strictly under 5%
    d = m2(spec(300), spec(300, l=14))
    check("m2 level: 14 of 300 passes", d["level"]["met"], d)
    d = m2(spec(300), spec(300, l=15))
    check("m2 level: exactly 5% fails (strict)", not d["level"]["met"] and not d["met"], d)
    d = m2(spec(300), spec(400, l=19))
    check("m2 level: 19 of 400 passes, 20 of 400 fails", d["level"]["met"] and not m2(spec(300), spec(400, l=20))["level"]["met"])
    # zero denominators
    d = m2(spec(300, ns=0, w=0), spec(300, w=0))
    check("m2: zero scored bids in the fourth book: wrong-side comparison not met", not d["wrong_side_vs_fourth"]["met"] and not d["met"])
    d = m2(spec(300), spec(300, ns=0, w=0))
    check("m2: zero scored bids in the fifth book: both wrong-side clauses not met", not d["wrong_side_vs_fourth"]["met"]
          and not d["wrong_side_cap"]["met"])
    d = m2(spec(300, r=0, m=0), spec(300))
    check("m2: zero research bids in the fourth book: matched not met", not d["matched"]["met"])
    d = m2(spec(300), spec(300, r=0, m=0))
    check("m2: zero research bids in the fifth book: matched not met", not d["matched"]["met"])
    d = m2(spec(300), spec(300, nl=0))
    check("m2: zero bids with a level in the fifth book: level not met", not d["level"]["met"])
    check("m2: all good passes", run()["measures"]["decisions"]["met"])
    # exact arithmetic: a share that float arithmetic would misjudge (3/100 + 0.02 style)
    d = m2(spec(100, w=3, ns=100), spec(100, w=5, ns=100, m=100, r=100))
    check("m2: 5/100 against 3/100 plus 2 points is exactly at the bar and passes", d["wrong_side_vs_fourth"]["met"], d)


def test_measure4():
    base = hrows([10.0] * 100)
    def m4(**c):
        return run(r5=with_counters(base, **c))["measures"]["candle_requests"]
    q = m4(pre_fetched=99, pre_error=1, pre_missing=0, pre_ondemand=0, step_candles=1)
    check("m4 failed: 100 failed of 10,000 (exactly 1%) passes", q["failed_clause"]["met"] and q["requests"] == 10000, q)
    # 100 heartbeats x (99 + 1) = 10,000 requests; 101 failures would be just over
    rows = with_counters(base, pre_fetched=99, pre_error=1, pre_missing=0, pre_ondemand=0, step_candles=1)
    rows[0]["counts"]["pre_error"] = 2
    q = run(r5=rows)["measures"]["candle_requests"]
    check("m4 failed: 101 of 10,001 is just over 1%: fails", not q["failed_clause"]["met"] and not q["met"], q)
    # in-step: 100 heartbeats x 30 minutes x 18 = 54,000 coin-minutes; 2% = 1,080
    rows = with_counters(base, pre_fetched=100, pre_error=0, pre_missing=10, pre_ondemand=0, step_candles=0)
    rows[0]["counts"]["pre_missing"] = 90
    q = run(r5=rows)["measures"]["candle_requests"]
    check("m4 in-step: 1,080 of 54,000 (exactly 2%) passes", q["in_step"] == 1080 and q["coin_minutes"] == 54000 and q["in_step_clause"]["met"], q)
    rows[0]["counts"]["pre_ondemand"] = 1
    q = run(r5=rows)["measures"]["candle_requests"]
    check("m4 in-step: 1,081 just over fails, pre_ondemand counts", not q["in_step_clause"]["met"] and q["failed_clause"]["met"])
    # first step after each start
    rows = with_counters(base, pre_fetched=100, pre_error=0, pre_missing=0, pre_ondemand=0, step_candles=0)
    rows[1]["counts"]["pre_missing"] = 1080 + 18
    meta, B, S = tables(spec(), spec())
    res = p3.evaluate(meta, B, S, rows, [rows[1]["t"] - timedelta(minutes=10)], hrows([10.0] * 100), hrows([10.0] * 100), "pass",
                      start="2026-11-20 00:30", end="2026-11-23 00:29")
    q = res["measures"]["candle_requests"]
    check("m4: one start in the half hour leaves out 18, so 1,098 becomes exactly 2%", q["left_out_first_steps"] == 18
          and q["in_step"] == 1080 and q["in_step_clause"]["met"], q)
    res = p3.evaluate(meta, B, S, rows, [], hrows([10.0] * 100), hrows([10.0] * 100), "pass", start="2026-11-20 00:30", end="2026-11-23 00:29")
    check("m4: without the start 1,098 fails", not res["measures"]["candle_requests"]["in_step_clause"]["met"])
    rows[1]["counts"]["pre_missing"] = 40
    res = p3.evaluate(meta, B, S, rows, [rows[1]["t"] - timedelta(minutes=10), rows[1]["t"] - timedelta(minutes=5)], hrows([10.0] * 100),
                      hrows([10.0] * 100), "pass", start="2026-11-20 00:30", end="2026-11-23 00:29")
    q = res["measures"]["candle_requests"]
    check("m4: two starts leave out 36 of 40", q["left_out_first_steps"] == 36 and q["in_step"] == 4, q)
    rows[1]["counts"]["pre_missing"] = 5
    res = p3.evaluate(meta, B, S, rows, [rows[1]["t"] - timedelta(minutes=10)] * 2, hrows([10.0] * 100), hrows([10.0] * 100), "pass",
                      start="2026-11-20 00:30", end="2026-11-23 00:29")
    check("m4: never below zero", res["measures"]["candle_requests"]["in_step"] == 0
          and res["measures"]["candle_requests"]["left_out_first_steps"] == 5)
    # counters absent from every heartbeat
    q = run(r5=hrows([10.0] * 100))["measures"]["candle_requests"]
    check("m4: counters absent from every heartbeat: not met", not q["met"] and q["counters_present"] == [], q)
    check("m4: absent counters make the verdict fail", run(r5=hrows([10.0] * 100))["verdict"] == "fail")
    q = run(r5=with_counters(base, pre_fetched=100))["measures"]["candle_requests"]
    check("m4: one counter present, the others read 0", q["met"] and q["counters_present"] == ["pre_fetched"], q)
    q = run(r5=with_counters(base, pre_fetched=0, pre_error=0))["measures"]["candle_requests"]
    check("m4: no requests at all is not met", not q["failed_clause"]["met"])


def test_verdict_and_period():
    r5 = hbs([10.0] * 100)
    res = run(r5=r5)
    check("all four hold: Part 3 pass", res["verdict"] == "pass" and all(res["holds"].values()), res["holds"])
    check("items fail: Part 3 fail", run(r5=r5, items="fail")["verdict"] == "fail")
    check("measure 1 fails: Part 3 fail", run(r5=hbs([11.0] * 100))["verdict"] == "fail")
    check("measure 2 fails: Part 3 fail", run(r5=r5, fifth=spec(300, w=40))["verdict"] == "fail")
    check("measure 4 fails: Part 3 fail", run(r5=hbs([10.0] * 100, dict(pre_fetched=1, pre_error=1)))["verdict"] == "fail")
    check("bad items value is an error", raises(lambda: run(r5=r5, items="unread"), "pass or fail"))
    # the period condition: 300 new bids in each book
    res = run(r5=r5, fifth=spec(299, w=0))
    check("period: 299 bids in the fifth book: not complete, no verdict", not res["condition"]["met"] and res["verdict"] is None)
    res = run(r5=r5, fourth=spec(299, w=0))
    check("period: 299 bids in the fourth book: not complete, no verdict", not res["condition"]["met"] and res["verdict"] is None)
    check("period: 300 in each is complete", run(r5=r5, fourth=spec(300), fifth=spec(300))["condition"]["met"])
    res = run(r5=r5, fifth=spec(299, w=0), read_as_is=True)
    check("period: --read-as-is gives the verdict and says so", res["verdict"] == "pass" and res["condition"]["read_as_is"]
          and "read as is" in p3.to_md(res), p3.to_md(res)[:600])
    md = p3.to_md(run(r5=r5, fifth=spec(299)))
    check("period: PERIOD NOT COMPLETE is printed", "PERIOD NOT COMPLETE" in md and "no verdict" in md and "Part 3: pass" not in md)
    md = p3.to_md(res_ok := run(r5=r5))
    check("markdown: verdict line and label mapping", "**Part 3: pass**" in md and "main = fourth book (paper_spot_t18)" in md
          and "tb = fifth book (paper_spot_r5)" in md)
    check("json round trip", json.loads(json.dumps(res_ok))["verdict"] == "pass")
    # a fifth book that is at the minimum is fine with a lower --min-heartbeats
    meta, B, S = tables(spec(), spec())
    res = p3.evaluate(meta, B, S, hbs([10.0] * 10), [], hrows([10.0] * 10), hrows([10.0] * 10), "pass", min_heartbeats=10,
                      start="2026-11-20 00:30", end="2026-11-23 00:29", pairs=GOOD_PAIRS)
    check("min heartbeats can be set", res["measures"]["step"]["met"])


def test_labels_and_guards():
    # the fifth book's numbers sit in the "tb" rows, the fourth's in the "main" rows
    fourth, fifth = spec(300, w=0, l=0), spec(310, w=31, l=0)
    res = run(r5=hbs([10.0] * 100), fourth=fourth, fifth=fifth)
    c = res["counts"]
    check("labels: fifth = tb rows, fourth = main rows", c["fifth"]["n"] == 310 and c["fourth"]["n"] == 300
          and c["fifth"]["w"] == 31 and c["fourth"]["w"] == 0, c)
    check("labels: the fifth's wrong-side excess is judged (10% is over the cap)", not res["measures"]["decisions"]["wrong_side_cap"]["met"])
    meta, B, S = tables(spec(), spec(), books=("paper_spot_r5", "paper_spot_t18"))
    check("guard: swapped books are an error", raises(lambda: p3.guard(meta, "paper_spot_t18", "paper_spot_r5", "2026-11-20 00:30", "2026-11-23 00:29"), "not a fourth-book"))
    meta, B, S = tables(spec(), spec())
    check("guard: period must equal --start and --end", raises(lambda: p3.guard(meta, "paper_spot_t18", "paper_spot_r5", "2026-11-20 00:30", "2026-11-23 00:35"), "differs"))
    meta, B, S = tables(spec(), spec(), groups={"all": ALL[:16], "trades list": TRADES, "candle path": CANDLE})
    check("guard: group all must be the 17 coins", raises(lambda: p3.guard(meta, "paper_spot_t18", "paper_spot_r5", "2026-11-20 00:30", "2026-11-23 00:29"), "17 traded coins"))
    meta, B, S = tables(spec(), spec(), groups={"all": ALL + ["BTC"], "trades list": TRADES, "candle path": CANDLE})
    check("guard: eighteen coins in group all is an error", raises(lambda: p3.guard(meta, "paper_spot_t18", "paper_spot_r5", "2026-11-20 00:30", "2026-11-23 00:29"), "17 traded coins"))
    check("guard: the real label order passes", len(p3.guard(*tables(spec(), spec())[:1], "paper_spot_t18", "paper_spot_r5", "2026-11-20 00:30", "2026-11-23 00:29")) == 17)
    # consistency with side_by_side.csv
    meta, B, S = tables(spec(), spec(), over={("tb", "m2_score_error", "n_other_side"): 5})
    check("consistency: wrong-side count differs from side_by_side.csv", raises(lambda: p3.book_counts(B, S, "tb", ALL), "wrong-side"))
    meta, B, S = tables(spec(), spec(), over={("main", "m3_bids", "bot_new_bids"): 301})
    check("consistency: bid count differs from side_by_side.csv", raises(lambda: p3.book_counts(B, S, "main", ALL), "new bids"))
    meta, B, S = tables(spec(), spec(), over={("main", "m1_level_error", "n"): 299})
    check("consistency: level count differs", raises(lambda: p3.book_counts(B, S, "main", ALL), "with a level"))
    # coins outside the 17 are ignored
    meta, B, S = tables(spec(), spec())
    extra = pd.DataFrame([dict(book="tb", ts="x", coin="BTC", err_bp=50.0, res_score=1.0, res_other_side=True)] * 5)
    c = p3.book_counts(pd.concat([B, extra], ignore_index=True), S, "tb", ALL)
    check("coins outside the 17 are ignored", c["n"] == 300 and c["w"] == 0)
    S2 = S[~((S.book == "tb") & (S.statistic == "research_matched"))]
    check("a missing side_by_side row is an error", raises(lambda: p3.book_counts(B, S2, "tb", ALL), "expected one row"))


# ---------------------------------------------------------------- logs and the command line
def iso(t):
    return t.replace(tzinfo=None).isoformat()


def write_log(root, folder, beats, counts=None, extra=()):
    """beats: list of data-step medians (None: no heartbeat) at 30-minute marks from 00:30 on Nov 20; a backfill at the start."""
    d = os.path.join(root, folder)
    os.makedirs(d, exist_ok=True)
    ev = [dict(ts=iso(T0 + timedelta(minutes=1)), kind="backfill")]
    for i, m in enumerate(beats, 1):
        if m is None:
            continue
        ev.append(dict(ts=iso(T0 + timedelta(minutes=30 * i)), kind="heartbeat", equity=250000, committed=1000,
                       counts=dict(counts or {}), step_s={"data": [m, m + 1.0]}))
    ev += list(extra)
    ev.sort(key=lambda e: e["ts"])
    with open(os.path.join(d, "events.jsonl"), "w") as f:
        for e in ev:
            f.write(json.dumps(e) + "\n")
    return d


def test_cli_and_shared_numbers():
    import paper_status as ps
    with tempfile.TemporaryDirectory() as tmp:
        n = 120
        counts = dict(GOOD4, tb_built=540)
        d5 = write_log(tmp, "paper_spot_r5", [10.0] * n, counts, extra=[dict(ts=iso(T0 + timedelta(minutes=95)), kind="backfill"),
                                                                       dict(ts=iso(T0 + timedelta(minutes=98)), kind="arm")])
        d4 = write_log(tmp, "paper_spot_t18", [10.5] * n)
        dm = write_log(tmp, "paper_spot", [10.2] * n)
        rec = os.path.join(tmp, "rec")
        os.makedirs(rec)
        meta, B, S = tables(spec(), spec())
        json.dump(meta, open(os.path.join(rec, "two_books.json"), "w"))
        B.to_csv(os.path.join(rec, "item7_bids.csv"), index=False)
        S.to_csv(os.path.join(rec, "side_by_side.csv"), index=False)
        out = os.path.join(tmp, "out")
        pdir = os.path.join(tmp, "reports", "owner", "step_pairs")
        os.makedirs(pdir)
        for i in range(9):                                      # eight that count (both orders), one that does not
            r3, bd = "10.00", ("9.90" if i % 2 else "10.10")    # build minus release 3: -0.10 and +0.10, four each
            runs = [dict(inputs="release3", data_end_median_text=r3), dict(inputs="build", data_end_median_text=bd)]
            if i % 3 == 0:
                runs.reverse()
            json.dump(dict(utc_start=f"2026-11-2{i // 4}T{(i % 4) * 6:02d}:35:00Z", order="ab" if i % 3 else "ba", counts=i != 8, why_not=None if i != 8 else "x", runs=runs),
                      open(os.path.join(pdir, f"pair_{i}.json"), "w"))
        cmd = [sys.executable, os.path.join(HERE, "part3_rule.py"), "--dir", rec, "--pairs", pdir, "--start", "2026-11-20T00:30", "--end", "2026-11-23T00:29",
               "--fifth", d5, "--fourth", d4, "--main", dm, "--items-1-5", "pass", "--out", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        check("cli runs", r.returncode == 0, r.stderr[-400:])
        js = json.load(open(os.path.join(out, "part3_rule.json")))
        md = open(os.path.join(out, "part3_rule.md")).read()
        check("cli: prints the markdown it writes", r.stdout.strip() == md.strip())
        check("cli: 120 heartbeats counted, measure 1 met, two starts left out as the first step (1 each)",
              js["measures"]["step"]["b"]["fifth_heartbeats"] == 120 and js["measures"]["step"]["a"]["pairs"] == 8
              and js["measures"]["step"]["a"]["median_s"] == 0.0 and js["measures"]["step"]["met"]
              and js["measures"]["candle_requests"]["left_out_first_steps"] == 2, js["measures"]["step"])
        check("cli: verdict pass", js["verdict"] == "pass" and "**Part 3: pass**" in md, js["holds"])
        # the same numbers as the status report on the same log
        rows5, starts = p3.log_rows(d5, "2026-11-20T00:30", "2026-11-23T00:29")
        text_book = ps.load_book(tmp, "paper_spot_r5")
        ev = text_book["events"]
        s = ps.stats(text_book, 250000.0, True)
        rt = ps.running_time(ev, s["first"], s["newest"])
        dq = ps.data_quality(ev, rt)
        a = ps.measure4(dq["rep"], ps.startup_steps(ev))
        b = ps.measure4(rows5, starts)
        check("shared: the rule and the status report give the same measure 4 on the same log",
              a["failed"] == b["failed"] and a["requests"] == b["requests"] and a["in_step"] == b["in_step"]
              and a["coin_minutes"] == b["coin_minutes"] and a["left_out"] == b["left_out"] and b["beats"] == 120, (a, b))
        text = ps.build_report(tmp, T0 + timedelta(days=4))
        sec = text.split("## Rule progress for the fifth book")[1].split("\n## ")[0]
        arow = [l for l in sec.splitlines() if l.startswith("| (a) Pairs that count")][0]
        check("shared: the status report and the rule read the same pairs and the same median",
              "8 pairs (8 needed); median 0.00 s" in arow and arow.endswith("| meets |") and js["measures"]["step"]["a"]["pairs"] == 8, arow)
        check("shared: the status report prints the rule's in-step figure",
              f"{b['in_step']:,.0f} of {float(b['coin_minutes']):,.0f}" in sec and f"{b['left_out']:,.0f} left out" in sec, sec[-700:])
        m1 = ps.measure1(dq["rep"], ps.data_quality(ps.load_book(tmp, "paper_spot")["events"], rt)["rep"])
        check("shared: measure 1 medians agree", float(m1["median"]) == js["measures"]["step"]["reported"]["fifth_own_median_s"])
        # the log is cut at the end: heartbeats after the period do not count
        r = subprocess.run(cmd[:-2] + ["--end", "2026-11-20T09:59", "--out", out], capture_output=True, text=True)
        check("cli: a period that differs from the folder's is refused", r.returncode != 0 and "differs" in r.stderr)
        # a period cut: only heartbeats inside the period
        rows, _ = p3.log_rows(d5, "2026-11-20T05:00", "2026-11-20T09:59")
        check("log_rows: only heartbeats inside [start, end]", len(rows) == 10 and rows[0]["t"] == T0 + timedelta(hours=5)
              and rows[-1]["t"] == T0 + timedelta(hours=9, minutes=30), [r["t"] for r in rows][:2])
        rows, _ = p3.log_rows(d5, "2026-11-20T05:00", "2026-11-20T10:00")
        check("log_rows: the end minute is included", rows[-1]["t"] == T0 + timedelta(hours=10), rows[-1]["t"])
        # pairs after the period, through the command line: 7 count in the period, then a later one is added
        os.remove(os.path.join(pdir, "pair_0.json"))
        r = subprocess.run(cmd, capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "part3_rule.json")))
        check("cli: 7 pairs count: the line is printed, no verdict, no verdict line in the file",
              r.returncode == 0 and "PART (a) NOT COMPLETE: 7 of 8 pairs count; the pair jobs go on and the read waits" in r.stdout.splitlines()
              and js["verdict"] is None and "Part 3: pass" not in r.stdout, r.stdout[:500])
        r = subprocess.run(cmd + ["--read-as-is"], capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "part3_rule.json")))
        check("cli: --read-as-is gives a verdict with part (a) not met", js["verdict"] == "fail" and not js["measures"]["step"]["a"]["met"], r.stdout[:300])
        json.dump(dict(utc_start="2026-11-23T03:05:00Z", order="ba", counts=True,
                       runs=[dict(inputs="build", data_end_median_text="9.90"), dict(inputs="release3", data_end_median_text="10.00")]),
                  open(os.path.join(pdir, "pair_late.json"), "w"))
        r = subprocess.run(cmd, capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "part3_rule.json")))
        a = js["measures"]["step"]["a"]
        check("cli: a pair after the period is added: pass, with the counts and the last start in the markdown and the json",
              js["verdict"] == "pass" and a["in_period"] == 7 and a["added"] == 1 and a["last_used_start"] == "2026-11-23T03:05:00Z"
              and "pair_late.json" in a["pair_files"] and "7 started in the period and 1 were added from after it" in r.stdout
              and "started 2026-11-23T03:05:00Z UTC" in r.stdout, r.stdout[:900])
        check("log_rows: a missing folder is an error", raises(lambda: p3.log_rows(os.path.join(tmp, "nope"), "2026-11-20T05:00", "2026-11-20T10:00"), "no events.jsonl"))


def main():
    for t in (test_measure1, test_pairs_after_the_period, test_measure2, test_measure4, test_verdict_and_period, test_labels_and_guards, test_cli_and_shared_numbers):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
