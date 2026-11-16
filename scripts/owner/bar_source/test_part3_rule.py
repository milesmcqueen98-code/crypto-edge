"""Offline tests of the Part 3 rule (part3_rule.py) on small made-up folders and logs. Run:
python scripts/owner/bar_source/test_part3_rule.py (prints ok / FAIL per check, last line "N checks passed", non-zero
exit on any failure)."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

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
    meta, B, S = tables(fourth, fifth, over)
    r5 = r5 if r5 is not None else hrows([10.0] * 100)
    rmain = rmain if rmain is not None else hrows([10.0] * 100)
    rfourth = rfourth if rfourth is not None else hrows([10.0] * 100)
    rows = r5 if r5 and r5[0]["counts"] else r5
    return p3.evaluate(meta, B, S, rows, [], rmain, rfourth, items, start="2026-11-20 00:30", end="2026-11-23 00:29", **kw)


def with_counters(rows, **c):
    return [dict(r, counts=dict(c)) for r in rows]


def hbs(meds, counters=None, offset=1):
    return with_counters(hrows(meds, offset), **(GOOD4 if counters is None else counters)) if counters != {} else hrows(meds, offset)


def test_measure1():
    res = run(r5=hbs([10.3] * 100))
    s = res["measures"]["step"]
    check("m1 (a): median exactly 10.3 passes", s["a"]["met"], s)
    res = run(r5=hbs([10.31] * 100))
    check("m1 (a): 10.31 fails", not res["measures"]["step"]["a"]["met"] and not res["measures"]["step"]["met"])
    res = run(r5=hbs([10.2] * 50 + [10.4] * 50))
    check("m1 (a): even count, middle two average exactly 10.3, passes", res["measures"]["step"]["a"]["met"])
    res = run(r5=hbs([10.2] * 49 + [10.4] * 51))
    check("m1 (a): median 10.4 fails", not res["measures"]["step"]["a"]["met"])
    res = run(r5=hbs([10.0] * 99))
    check("m1: 99 fifth-book heartbeats is not met, 100 is", not res["measures"]["step"]["a"]["met"]
          and not res["measures"]["step"]["a"]["enough"] and run(r5=hbs([10.0] * 100))["measures"]["step"]["a"]["met"])
    res = run(r5=hbs([10.0] * 100), rmain=hrows([10.0] * 100))
    check("m1 (b): equal medians pass", res["measures"]["step"]["b"]["met"])
    res = run(r5=hbs([10.1] * 100), rmain=hrows([10.0] * 100))
    check("m1 (b): fifth just higher fails", not res["measures"]["step"]["b"]["met"] and not res["measures"]["step"]["met"])
    res = run(r5=hbs([10.0] * 100), rmain=hrows([10.1] * 100))
    check("m1 (b): fifth lower passes", res["measures"]["step"]["b"]["met"])
    # pairing by timestamp: only 99 shared timestamps
    res = run(r5=hbs([10.0] * 100), rmain=hrows([10.0] * 99, offset=2))
    b = res["measures"]["step"]["b"]
    check("m1 (b): 99 shared heartbeat times is not met", b["paired_half_hours"] == 99 and not b["met"], b)
    res = run(r5=hbs([10.0] * 100), rmain=hrows([10.0] * 100, offset=1))
    check("m1 (b): 100 shared times is enough", res["measures"]["step"]["b"]["paired_half_hours"] == 100)
    # a half hour in one book only is left out of the pairs: the main book's extra low values do not count
    res = run(r5=hbs([10.0] * 100), rmain=hrows([10.0] * 100 + [1.0] * 300, offset=1))
    b = res["measures"]["step"]["b"]
    check("m1 (b): main heartbeats at times the fifth lacks are left out", b["paired_half_hours"] == 100 and b["main_median_s"] == 10.0, b)
    res = run(r5=hbs([10.0] * 100), rmain=[])
    check("m1 (b): no main heartbeats is not met", not res["measures"]["step"]["b"]["met"])
    res = run(r5=hbs([10.0] * 100), rfourth=hrows([9.0] * 100))
    check("m1: the fourth book is for information only", res["measures"]["step"]["fourth_for_information"]["fourth_median_s"] == 9.0
          and res["measures"]["step"]["met"])


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
                      start="2026-11-20 00:30", end="2026-11-23 00:29")
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
        cmd = [sys.executable, os.path.join(HERE, "part3_rule.py"), "--dir", rec, "--start", "2026-11-20T00:30", "--end", "2026-11-23T00:29",
               "--fifth", d5, "--fourth", d4, "--main", dm, "--items-1-5", "pass", "--out", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        check("cli runs", r.returncode == 0, r.stderr[-400:])
        js = json.load(open(os.path.join(out, "part3_rule.json")))
        md = open(os.path.join(out, "part3_rule.md")).read()
        check("cli: prints the markdown it writes", r.stdout.strip() == md.strip())
        check("cli: 120 heartbeats counted, measure 1 met, two starts left out as the first step (1 each)",
              js["measures"]["step"]["a"]["heartbeats"] == 120 and js["measures"]["step"]["met"]
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
        check("shared: the status report prints the rule's in-step figure",
              f"{b['in_step']:,.0f} of {float(b['coin_minutes']):,.0f}" in sec and f"{b['left_out']:,.0f} left out" in sec, sec[-700:])
        m1 = ps.measure1(dq["rep"], ps.data_quality(ps.load_book(tmp, "paper_spot")["events"], rt)["rep"])
        check("shared: measure 1 medians agree", float(m1["median"]) == js["measures"]["step"]["a"]["median_s"])
        # the log is cut at the end: heartbeats after the period do not count
        r = subprocess.run(cmd[:-2] + ["--end", "2026-11-20T09:59", "--out", out], capture_output=True, text=True)
        check("cli: a period that differs from the folder's is refused", r.returncode != 0 and "differs" in r.stderr)
        # a period cut: only heartbeats inside the period
        rows, _ = p3.log_rows(d5, "2026-11-20T05:00", "2026-11-20T09:59")
        check("log_rows: only heartbeats inside [start, end]", len(rows) == 10 and rows[0]["t"] == T0 + timedelta(hours=5)
              and rows[-1]["t"] == T0 + timedelta(hours=9, minutes=30), [r["t"] for r in rows][:2])
        rows, _ = p3.log_rows(d5, "2026-11-20T05:00", "2026-11-20T10:00")
        check("log_rows: the end minute is included", rows[-1]["t"] == T0 + timedelta(hours=10), rows[-1]["t"])
        check("log_rows: a missing folder is an error", raises(lambda: p3.log_rows(os.path.join(tmp, "nope"), "2026-11-20T05:00", "2026-11-20T10:00"), "no events.jsonl"))


def main():
    for t in (test_measure1, test_measure2, test_measure4, test_verdict_and_period, test_labels_and_guards, test_cli_and_shared_numbers):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
