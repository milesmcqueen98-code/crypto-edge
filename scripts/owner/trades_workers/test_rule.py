"""Offline tests of the trades-workers rule (rule.py) on small made-up folders, logs and pair files. Run:
python scripts/owner/trades_workers/test_rule.py (prints ok / FAIL per check, last line "N checks passed", non-zero exit on any
failure)."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
OWNER = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, OWNER)
sys.path.insert(0, os.path.join(OWNER, "bar_source"))

import pandas as pd             # noqa: E402

import rule                     # noqa: E402
import paper_status as ps       # noqa: E402
import part3_rule as p3         # noqa: E402

TRADES = ["ETH", "LTC", "SOL", "XRP", "ZEC"]
CANDLE = ["AAVE", "BCH", "DOGE", "ENA", "HBAR", "HYPE", "LINK", "NEAR", "ONDO", "PEPE", "SUI", "XLM"]
ALL = TRADES + CANDLE
FAILS = []
COUNT = [0]
T0 = datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)
START, END = "2026-11-20 00:30", "2026-11-23 00:29"
PERIOD_START = datetime(2026, 11, 20, 0, 30, tzinfo=timezone.utc)
F = Fraction


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


# ---------------------------------------------------------------- the reconciliation folder (labels: main = fifth, tb = sixth)
def spec(n=300, w=0, ns=None, l=0, nl=None, m=None, r=None):
    """One book: n bids, ns with a score (w on the wrong side), nl with a level (l of them more than 5 bp away), research
    matched m of r."""
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


def tables(fifth, sixth, over=None, groups=None, books=("paper_spot_r5", "paper_spot_tw"), start=START, end=END):
    over = over or {}
    meta = dict(period=dict(start=start, end=end), books=dict(main=books[0], tb=books[1]),
                minutes=dict(main=4300, tb=4310, common=4290),
                groups=groups or {"all": ALL, "trades list": TRADES, "candle path": CANDLE})
    B = pd.DataFrame(rows_for("main", fifth) + rows_for("tb", sixth))
    S = pd.DataFrame(side("main", fifth, over) + side("tb", sixth, over))
    return meta, B, S


# ---------------------------------------------------------------- heartbeat rows
GOOD4 = dict(pre_fetched=1000, pre_error=0, pre_missing=1, pre_ondemand=0, step_candles=300)


def hb(k, minutes=30.0, data=10.0, **counts):
    """A data-quality row (ps.data_quality's dq['rep']) of the heartbeat at 30 minutes times k after T0."""
    return dict(t=T0 + timedelta(minutes=30 * k), data=(data, data + 1.0), counts=counts, minutes=minutes)


def beats(ks, **counts):
    return [hb(k, **counts) for k in ks]


def good_rows(n=100, **over):
    return beats(range(1, n + 1), **dict(GOOD4, **over))


# ---------------------------------------------------------------- alt job files (loaded through paper_status, as the rule does)
def asteps(n1=20, n3=20, p1="1.000", p3="1.000", slow1=0, slow3=0, fb1=0, fb3=0, peak3=7, limited3=0, refused3=0):
    """n1 one-worker and n3 three-worker steps; the first slow1 / slow3 of each arm have a slow pass of 7.000 s; fb1 / fb3
    budget fallbacks in the first step of an arm; peak3 is the three-worker peak."""
    out = []
    for w, n, p, slow, fb in ((1, n1, p1, slow1, fb1), (3, n3, p3, slow3, fb3)):
        for i in range(n):
            out.append(dict(workers=w, pass_s=float(p), pass_text="7.000" if i < slow else p, tb_fb_budget=fb if i == 0 else 0,
                            peak=peak3 if w == 3 else 5, limited=w == 3 and i < limited3, refused=w == 3 and i < refused3))
    return out


def texts(one, three):
    """Steps whose pass texts are exactly these lists (one-worker, three-worker)."""
    return [dict(workers=w, pass_s=float(t), pass_text=t, tb_fb_budget=0, peak=5, limited=False, refused=False)
            for w, ts in ((1, one), (3, three)) for t in ts]


def write_alt(folder, name, start, steps=None, first="one", counts=True, why=None, rows=((100, 1), (100, 1)), rows_complete=True):
    os.makedirs(folder, exist_ok=True)
    steps = asteps() if steps is None else steps
    arms = {w: dict(steps_timed=sum(1 for s in steps if s["workers"] == int(w)), rows_compared=rows[k][0], rows_differ=rows[k][1])
            for k, w in enumerate(("1", "3"))}
    with open(os.path.join(folder, name), "w") as f:
        json.dump(dict(utc_start=start, first=first, steps=steps, arms=arms, rows_complete=rows_complete, counts=counts, why_not=why), f)


def stamp(hours):
    return (PERIOD_START + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def fill_alt(folder, specs, first_hour=1):
    """One job per spec (a dict of write_alt keywords) hour by hour from first_hour."""
    for i, sp in enumerate(specs):
        h = first_hour + i
        write_alt(folder, "alt_%s.json" % (PERIOD_START + timedelta(hours=h)).strftime("%Y%m%dT%H%MZ"), stamp(h), **sp)


def jobs_of(specs, first_hour=1, extra=()):
    """ps.load_alt_jobs on a folder holding these jobs (extra: raw (name, text) files)."""
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "alt")
        fill_alt(d, specs, first_hour)
        for n, text in extra:
            open(os.path.join(d, n), "w").write(text)
        return ps.load_alt_jobs(d)


NOW0 = datetime(2026, 11, 24, tzinfo=timezone.utc)                 # a day after the period's end: far inside the 14 days
G = dict(steps=asteps(20, 20, "1.000", "1.000", slow1=4, slow3=1, fb1=1, fb3=1), rows=((100, 2), (100, 2)))
GOOD_JOBS = jobs_of([G] * 8)


def run(fifth=None, sixth=None, items="pass", r6=None, r5=None, s6=None, s5=None, trades=None, jobs=None, now=None, **kw):
    fifth = fifth or spec(300, w=9, l=3, m=280, r=300)
    sixth = sixth or spec(300, w=9, l=3, m=280, r=300)
    over = kw.pop("over", None)
    meta, B, S = tables(fifth, sixth, over)
    r6 = r6 if r6 is not None else good_rows()
    r5 = r5 if r5 is not None else good_rows()
    trades = trades or dict(n=0, median=None, max=None)
    return rule.evaluate(meta, B, S, r6, s6 or [], r5, s5 or [], trades, items, GOOD_JOBS if jobs is None else jobs,
                         start=START, end=END, now=NOW0 if now is None else now, **kw)


# ---------------------------------------------------------------- tests
def test_baseline_and_labels():
    res = run()
    check("baseline: every clause holds and the verdict is pass", res["verdict"] == "pass" and all(res["holds"].values()), res["holds"])
    check("baseline: eight keys in holds (four of Part 3, four of Part 4)", len(res["holds"]) == 8)
    md = rule.to_md(res)
    check("markdown: verdict line and label mapping", "**Trades workers: pass**" in md and "main = fifth book (paper_spot_r5)" in md
          and "tb = sixth book (paper_spot_tw)" in md)
    check("json round trip", json.loads(json.dumps(rule.public(res)))["verdict"] == "pass" and "_sel" not in rule.public(res)["part3"])
    # the sixth book's numbers sit in the "tb" rows, the fifth's in the "main" rows
    res = run(fifth=spec(300, w=0), sixth=spec(310, w=31))
    c = res["counts"]
    check("labels: sixth = tb rows, fifth = main rows", c["sixth"]["n"] == 310 and c["fifth"]["n"] == 300 and c["sixth"]["w"] == 31
          and c["fifth"]["w"] == 0, c)
    check("labels: the sixth's wrong-side excess is judged (10% is over the cap)", not res["part4"]["decisions"]["wrong_side_cap"]["met"])
    res = run(fifth=spec(310, w=31), sixth=spec(300, w=0))
    check("labels: the fifth's own wrong-side share only sets the comparison (a high control share loosens it)",
          res["part4"]["decisions"]["wrong_side_vs_fifth"]["met"] and res["part4"]["decisions"]["wrong_side_cap"]["met"])
    meta, B, S = tables(spec(), spec(), books=("paper_spot_tw", "paper_spot_r5"))
    check("guard: swapped books are an error", raises(lambda: rule.guard(meta, "paper_spot_r5", "paper_spot_tw", START, END), "not a fifth-book"))
    meta, B, S = tables(spec(), spec())
    check("guard: period must equal --start and --end", raises(lambda: rule.guard(meta, "paper_spot_r5", "paper_spot_tw", START, "2026-11-23 00:35"), "differs"))
    meta, B, S = tables(spec(), spec(), groups={"all": ALL[:16], "trades list": TRADES, "candle path": CANDLE})
    check("guard: group all must be the 17 coins", raises(lambda: rule.guard(meta, "paper_spot_r5", "paper_spot_tw", START, END), "17 traded coins"))
    meta, B, S = tables(spec(), spec(), groups={"all": ALL + ["BTC"], "trades list": TRADES, "candle path": CANDLE})
    check("guard: eighteen coins in group all is an error", raises(lambda: rule.guard(meta, "paper_spot_r5", "paper_spot_tw", START, END), "17 traded coins"))
    check("guard: the real label order passes", len(rule.guard(tables(spec(), spec())[0], "paper_spot_r5", "paper_spot_tw", START, END)) == 17)
    meta, B, S = tables(spec(), spec(), over={("tb", "m2_score_error", "n_other_side"): 5})
    check("consistency: a count that differs from side_by_side.csv is an error (the reading is part3_rule.book_counts)",
          raises(lambda: p3.book_counts(B, S, "tb", ALL), "wrong-side"))
    meta, B, S = tables(spec(), spec(), over={("tb", "m3_bids", "bot_new_bids"): 301})
    check("consistency: through evaluate too", raises(lambda: rule.evaluate(meta, B, S, [], [], [], [], dict(n=0, median=None, max=None), "pass", []), "new bids"))
    check("items must be pass or fail", raises(lambda: run(items="maybe"), "pass or fail"))


def test_decisions():
    def d(fifth, sixth):
        return run(fifth=fifth, sixth=sixth)["part4"]["decisions"]
    # wrong side: sixth <= fifth + 2 points and <= 5%
    x = d(spec(300, w=9), spec(300, w=15))
    check("wrong side: sixth exactly the fifth's share plus 2.0 points (and exactly 5%) is met", x["wrong_side_vs_fifth"]["met"] and x["wrong_side_cap"]["met"] and x["met"], x)
    x = d(spec(300, w=9), spec(300, w=16))
    check("wrong side: one bid more fails both clauses", not x["wrong_side_vs_fifth"]["met"] and not x["wrong_side_cap"]["met"] and not x["met"])
    x = d(spec(300, w=30), spec(300, w=15))
    check("wrong side: a fifth book far above still leaves the 5% cap", x["wrong_side_vs_fifth"]["met"] and x["wrong_side_cap"]["met"])
    x = d(spec(300, w=0), spec(300, w=7))
    check("wrong side: 7 of 300 against 0 of 300 is 2.33 points, over the tolerance, under the cap", not x["wrong_side_vs_fifth"]["met"] and x["wrong_side_cap"]["met"])
    x = d(spec(300, w=0), spec(300, w=6))
    check("wrong side: 6 of 300 against 0 of 300 is exactly 2.0 points, met", x["wrong_side_vs_fifth"]["met"])
    x = d(spec(300, w=0, ns=0), spec(300, w=0, ns=0))
    check("wrong side: zero scored bids in both is not met", not x["wrong_side_vs_fifth"]["met"] and not x["wrong_side_cap"]["met"])
    x = d(spec(300, w=0, ns=0), spec(300, w=0))
    check("wrong side: zero scored bids in the fifth alone fails the comparison, not the cap", not x["wrong_side_vs_fifth"]["met"] and x["wrong_side_cap"]["met"])
    x = d(spec(300, w=0), spec(300, w=0, ns=0))
    check("wrong side: zero scored bids in the sixth fails both", not x["wrong_side_vs_fifth"]["met"] and not x["wrong_side_cap"]["met"])
    # matched: sixth >= fifth - 3 points (280/300 - 0.03 = 271/300 exactly)
    x = d(spec(300, m=280), spec(300, m=271))
    check("matched: exactly the fifth's share minus 3.0 points is met", x["matched"]["met"], x["matched"])
    x = d(spec(300, m=280), spec(300, m=270))
    check("matched: one less is not met", not x["matched"]["met"] and not x["met"])
    check("matched: zero research bids in either book is not met", not d(spec(300, r=0, m=0), spec(300))["matched"]["met"]
          and not d(spec(300), spec(300, r=0, m=0))["matched"]["met"])
    # level: strictly under 5%
    x = d(spec(300), spec(300, l=14))
    check("level: 14 of 300 (4.67%) is met", x["level"]["met"])
    x = d(spec(300), spec(300, l=15))
    check("level: exactly 5% (15 of 300) is NOT met (strict)", not x["level"]["met"] and not x["met"])
    check("level: zero bids with a level is not met", not d(spec(300), spec(300, nl=0, l=0))["level"]["met"])
    # the same readings as part3_rule.measure2 (new = the first argument): the formulas agree on a grid
    agree = True
    for w6 in (0, 6, 9, 15, 16):
        for m6 in (270, 271, 290):
            for l6 in (0, 14, 15):
                a, b = spec(300, w=w6, m=m6, l=l6), spec(300, w=9, m=280, l=3)
                mine = rule.decisions(p3.book_counts(*tables(b, a)[1:], "tb", ALL), p3.book_counts(*tables(b, a)[1:], "main", ALL))
                ref = p3.measure2(p3.book_counts(*tables(b, a)[1:], "tb", ALL), p3.book_counts(*tables(b, a)[1:], "main", ALL))
                agree = agree and mine["met"] == ref["met"] and mine["level"]["met"] == ref["level"]["met"] \
                    and mine["matched"]["met"] == ref["matched"]["met"]
    check("decisions: the same results as part3_rule.measure2 on a grid of counts", agree)


def test_part3_clauses():
    def p3res(specs, **kw):
        return run(jobs=jobs_of(specs), **kw)["part3"]
    ok = lambda **kw: dict(G, steps=asteps(20, 20, slow1=4, **kw))                                      # noqa: E731
    # eight good jobs: all four clauses
    r = p3res([G] * 8)
    check("part 3: eight good jobs meet clauses 1 to 4 and are complete", r["step"]["met"] and r["gain"]["met"] and r["pace"]["met"] and r["rows"]["met"]
          and r["complete"] and r["met"] and r["jobs"] == 8 and r["slow_one"] == 32, r)
    # 1 no harm
    one3 = lambda a, b: [dict(steps=asteps(20, 20, a, b, slow1=4))] * 8                                 # noqa: E731
    r = p3res(one3("1.000", "1.050"))
    check("part 3.1: three exactly 0.05 s above one meets", r["step"]["met"] and r["step"]["median_three_exact"] == "21/20", r["step"])
    check("part 3.1: 0.051 s above does not", not p3res(one3("1.000", "1.051"))["step"]["met"])
    check("part 3.1: three faster than one meets", p3res(one3("1.000", "0.500"))["step"]["met"])
    check("part 3.1: even count: the mean of the middle two (1.000 and 2.000, so 1.500) plus 0.05 is the bar",
          p3res([dict(steps=texts(["1.000"] * 10 + ["2.000"] * 10, ["1.550"] * 20))] * 2)["step"]["met"]
          and not p3res([dict(steps=texts(["1.000"] * 10 + ["2.000"] * 10, ["1.551"] * 20))] * 2)["step"]["met"])
    r = p3res([dict(steps=texts(["1.000"] * 10 + ["2.000"] * 10, ["1.550"] * 20))] * 2)
    check("part 3.1: the exact medians are in the result", r["step"]["median_one_exact"] == "3/2" and r["step"]["median_three_exact"] == "31/20", r["step"])
    check("part 3.1: seven jobs can still meet clause 1 (the read waits, the clause is computed)", p3res([G] * 7)["step"]["met"] and not p3res([G] * 7)["complete"])
    # 2 a gain in slow minutes
    sl = lambda s1, s3, **kw: [dict(steps=asteps(20, 20, slow1=s1, slow3=s3, **kw))] * 8                # noqa: E731
    r = p3res(sl(4, 2))
    check("part 3.2: 32 slow one-worker passes and exactly half the share with three meet", r["gain"]["met"] and r["gain"]["slow_one"] == 32 and r["gain"]["slow_three"] == 16, r["gain"])
    check("part 3.2: one more slow pass with three (17 of 160 against 32 of 160) does not", not p3res(sl(4, 2)[:7] + [dict(steps=asteps(20, 20, slow1=4, slow3=3))])["gain"]["met"])
    check("part 3.2: exactly 30 slow one-worker passes meet", p3res([dict(steps=asteps(20, 20, slow1=4))] * 7 + [dict(steps=asteps(20, 20, slow1=2))])["gain"]["met"])
    r = p3res([dict(steps=asteps(20, 20, slow1=4))] * 7 + [dict(steps=asteps(20, 20, slow1=1))])
    check("part 3.2: 29 slow one-worker passes do not (the read waits)", not r["gain"]["met"] and not r["complete"] and r["slow_one"] == 29)
    check("part 3.2: slow is strictly above 6.0 s", p3res([dict(steps=asteps(20, 20, "6.000", "6.000"))] * 8)["gain"]["slow_one"] == 0
          and p3res([dict(steps=asteps(20, 20, "6.001", "6.001"))] * 8)["gain"]["slow_one"] == 160)
    # fallbacks in PASSES: met if s3 <= s1, or (s3 - s1) squared <= 4 * (s1 + s3). One job with 20 steps per arm; the slow
    # passes needed for the gain come from 8 jobs, the fallback passes sit in the first job.
    def fbp(s1, s3, coins=1):
        st = asteps(20, 20, slow1=4)
        for w, n in ((1, s1), (3, s3)):
            for x in [x for x in st if x["workers"] == w][:n]:
                x["tb_fb_budget"] = coins
        return p3res([dict(steps=st)] + [dict(steps=asteps(20, 20, slow1=4))] * 7)["gain"]
    for s1, s3, met in ((2, 2, True), (3, 1, True), (1, 5, True), (0, 4, True), (0, 5, False), (4, 10, True), (2, 11, False)):
        g = fbp(s1, s3)
        check(f"part 3.2: fallback passes one {s1}, three {s3}: {'meets' if met else 'does not meet'}", g["met"] == met and g["fallback_passes_one"] == s1
              and g["fallback_passes_three"] == s3, g)       # (1,5): 16 <= 24; (0,4): 16 <= 16; (0,5): 25 > 20; (2,11): 81 > 52
    check("part 3.2: a step with several coins fallen back is one pass (1 against 5 passes of 3 coins each still 16 <= 24)",
          fbp(1, 5, coins=3)["met"] and fbp(1, 5, coins=3)["fallbacks_three"] == 15 and fbp(1, 5, coins=3)["fallbacks_one"] == 3)
    check("part 3.2: the branch is in the result", fbp(0, 0)["fallbacks_branch"] == "no more" and fbp(0, 4)["fallbacks_branch"] == "chance" and fbp(0, 5)["fallbacks_branch"] == "more")
    check("part 3.2: summed over the jobs, not averaged (three 12 of 160 against one's 32 of 160 halved, 16: meets; 17 does not)",
          p3res([dict(steps=asteps(20, 20, slow1=4, slow3=3))] * 4 + [dict(steps=asteps(20, 20, slow1=4, slow3=0))] * 4)["gain"]["met"]
          and not p3res([dict(steps=asteps(20, 20, slow1=4, slow3=3))] * 4 + [dict(steps=asteps(20, 20, slow1=4, slow3=0))] * 3
                        + [dict(steps=asteps(20, 20, slow1=4, slow3=5))])["gain"]["met"])
    # 3 the pace
    base = [G] * 8
    check("part 3.3: eight clean jobs meet, the peak is stated", p3res(base)["pace"]["met"] and p3res(base)["pace"]["peak_max"] == 7)
    check("part 3.3: a three-worker peak of exactly 8 meets", p3res([dict(G, steps=asteps(20, 20, slow1=4, peak3=8))] * 8)["pace"]["met"])
    r = p3res([dict(G, steps=asteps(20, 20, slow1=4, peak3=9))] + base[1:])
    check("part 3.3: a peak of 9 does not meet, the file is named", not r["pace"]["met"] and r["pace"]["over_peak"] == ["alt_20261120T0130Z.json"], r["pace"])
    check("part 3.3: a limited three-worker step does not meet", not p3res(base[:7] + [dict(G, steps=asteps(20, 20, slow1=4, limited3=1))])["pace"]["met"])
    check("part 3.3: a refused three-worker step does not meet", not p3res(base[:7] + [dict(G, steps=asteps(20, 20, slow1=4, refused3=1))])["pace"]["met"])
    bad = dict(steps=asteps(20, 20, peak3=9), counts=False, why="x")
    r = p3res(base[:4] + [bad] + base[4:])
    check("part 3.3: a file that does not count, between the first and the last job used, still fails it", not r["pace"]["met"] and r["jobs"] == 8
          and r["pace"]["over_peak"] == ["alt_20261120T0530Z.json"], r["pace"])
    r = p3res([bad] + base)
    check("part 3.3: a file that does not count and started before the first job is outside the range", r["pace"]["met"] and r["jobs"] == 8)
    r = p3res(base + [bad])
    check("part 3.3: a file that does not count and started after the last job used is outside the range", r["pace"]["met"] and r["jobs"] == 8)
    r = p3res(base[:4] + [dict(steps=asteps(20, 20, refused3=1), counts=False, why="refused")] + base[4:])
    check("part 3.3: a refused step in a file that does not count fails it", not r["pace"]["met"] and r["pace"]["refused_or_limited"] == ["alt_20261120T0530Z.json"])
    r = run(jobs=jobs_of(base, extra=[("alt_20261120T0405Z.json", "{not json")]))["part3"]
    check("part 3.3: an unreadable file in the range is listed and does not meet", not r["pace"]["met"] and r["pace"]["unreadable"] == ["alt_20261120T0405Z.json"], r["pace"])
    r = run(jobs=jobs_of(base, extra=[("alt_20261201T0405Z.json", "{not json")]))["part3"]
    check("part 3.3: an unreadable file after the last job used is outside the range", r["pace"]["met"] and r["pace"]["unreadable"] == [])
    r = run(jobs=jobs_of(base, extra=[("odd.json", "{not json")]))["part3"]
    check("part 3.3: an unreadable file with no start at all is taken as inside the range", not r["pace"]["met"] and r["pace"]["unreadable"] == ["odd.json"])
    check("part 3.3: no files at all: the clause itself is met, the read is not complete", run(jobs=[])["part3"]["pace"]["met"] and not run(jobs=[])["part3"]["complete"])
    # 4 the rows
    rw = lambda c1, d1, c3, d3, n=8, complete=True: [dict(steps=asteps(20, 20, slow1=4), rows=((c1, d1), (c3, d3)), rows_complete=complete)] * n    # noqa: E731
    one = lambda c1, d1, c3, d3: p3res(rw(c1, d1, c3, d3, n=1))["rows"]                                   # noqa: E731
    check("part 3.4: d exactly 1/100 (2 of 100 and 3 of 100) meets, no more", one(100, 2, 100, 3)["met"] and one(100, 2, 100, 3)["branch"] == "no more"
          and one(100, 2, 100, 3)["difference"] == "1/100")
    # d just above 1/100, small samples: 10 of 50 and 11 of 50, d = 22/100 - 20/100 = 1/50; p = 21/100;
    # 4 * 0.21 * 0.79 * (1/50 + 1/50) = 0.026544 and d squared = 0.0004 <= 0.026544: within chance, met
    check("part 3.4: d = 1/50 with 50 and 50 rows meets by the chance branch", one(50, 10, 50, 11)["met"] and one(50, 10, 50, 11)["branch"] == "chance")
    # 4000 of 10000 and 4300 of 10000: d = 0.03; p = 0.415; 4 * 0.415 * 0.585 * 0.0002 = 0.00019422 < d squared = 0.0009: not met
    check("part 3.4: d = 3 points with 10000 and 10000 rows is more than chance allows, not met", not one(10000, 4000, 10000, 4300)["met"]
          and one(10000, 4000, 10000, 4300)["branch"] == "more")
    check("part 3.4: equal shares meet", one(100, 30, 200, 60)["met"] and one(100, 30, 200, 60)["branch"] == "no more")
    check("part 3.4: different sizes, exactly a point (1 of 100, 4 of 200) meets", one(100, 1, 200, 4)["met"])
    check("part 3.4: a zero denominator on either side does not meet", not p3res(rw(0, 0, 100, 0))["rows"]["met"] and not p3res(rw(100, 0, 0, 0))["rows"]["met"])
    r = p3res(rw(100, 0, 100, 0, n=7) + rw(100, 0, 100, 50, n=1, complete=False))
    check("part 3.4: a job with an incomplete comparison is left out", r["rows"]["met"] and r["rows"]["jobs"] == 7 and r["rows"]["compared_three"] == 700, r["rows"])
    check("part 3.4: no job with a complete comparison does not meet", not p3res(rw(100, 0, 100, 0, complete=False))["rows"]["met"])
    # the reported figures
    r = p3res(one3("1.000", "0.900"))["reported"]
    check("part 3 reported: medians, means, difference, the note and the per-job steps and slow passes",
          r["median_one_s"] == 1.0 and r["median_three_s"] == 0.9 and abs(r["diff_median_s"] + 0.1) < 1e-9 and abs(r["mean_one_s"] - 2.2) < 1e-9
          and r["note"] == "first version of the plan asked for a 0.2 s gain at the median over half-hour pairs" and len(r["jobs"]) == 8
          and r["jobs"][0]["steps_one"] == 20 and r["jobs"][0]["slow_one"] == 4 and r["decides"] == "nothing", r)


def test_chance_branch_texts():
    res = run(jobs=jobs_of([dict(G, steps=asteps(20, 20, slow1=20, fb3=1), rows=((50, 10), (50, 11)))] * 2 + [dict(G, steps=asteps(20, 20, slow1=20), rows=((50, 10), (50, 11)))] * 6))
    md = rule.to_md(res)
    check("markdown: the branch that decided is said plainly (fallbacks 0 against 2 passes, rows 1/50 apart)",
          "more, but within chance (two standard deviations of the difference)" in md and res["part3"]["gain"]["fallbacks_branch"] == "chance"
          and res["part3"]["rows"]["branch"] == "chance" and res["verdict"] == "pass", md[md.index("## Part 3"):][:1800])
    res = run(jobs=jobs_of([dict(G, steps=asteps(20, 20, slow1=20, fb3=1), rows=((10000, 4000), (10000, 4300)))] * 5 + [dict(G, steps=asteps(20, 20, slow1=20), rows=((10000, 4000), (10000, 4300)))] * 3))
    check("markdown: more than chance allows", rule.to_md(res).count("more than chance allows") == 2 and res["verdict"] == "fail")


def test_job_selection():
    first = 1
    sel = lambda specs_a, specs_b=(), b_hour=24 * 3 + 2, **kw: run(jobs=jobs_of(specs_a, first) + (jobs_of(list(specs_b), b_hour) if specs_b else []), **kw)["part3"]   # noqa: E731
    S6 = dict(G, steps=asteps(20, 20, slow1=6))
    S0 = dict(G, steps=asteps(20, 20, slow1=0))
    # in the period
    P = sel([S6] * 8)
    check("selection: eight in the period with 48 slow passes: all used, nothing added", P["complete"] and P["in_period"] == 8 and P["added"] == 0 and P["jobs"] == 8)
    P = sel([S6] * 5, [S0] * 4)
    check("selection: five in the period, later ones added for the eighth job, oldest first (30 slow already)",
          P["complete"] and P["in_period"] == 5 and P["added"] == 3 and P["jobs"] == 8 and P["slow_one"] == 30
          and P["job_files"][5:] == ["alt_20261123T0230Z.json", "alt_20261123T0330Z.json", "alt_20261123T0430Z.json"], P)
    check("selection: the last job used is stated", P["last_used_start"] == "2026-11-23T04:30:00Z" and P["first_job_start"] == "2026-11-20T01:30:00Z", P)
    S3 = dict(G, steps=asteps(20, 20, slow1=3))
    P = sel([S3] * 8, [S3] * 3)
    check("selection: eight jobs in the period but 24 slow passes: later jobs added for the 30th slow pass, one at a time (two)",
          P["complete"] and P["in_period"] == 8 and P["added"] == 2 and P["jobs"] == 10 and P["slow_one"] == 30, P)
    P = sel([S3] * 8, [S3] * 3, b_hour=24 * 3 + 2)
    check("selection: adding stops as soon as both hold (the third later job is not used)", "alt_20261123T0430Z.json" not in P["job_files"])
    # 14 days: first job at hour 1, so the days end at hour 24 * 14 + 1
    D = 24 * 14
    S15 = dict(G, steps=asteps(20, 20, slow1=15))
    P = sel([S0] * 8, [S15] * 2, b_hour=D)
    check("selection: a job exactly 14 days after the first job's start is still added", P["complete"] and P["added"] == 2 and P["jobs"] == 10
          and P["last_used_start"] == stamp(D + 1) and P["gain"]["met"], P)
    P = sel([S0] * 8, [S15] * 2, b_hour=D + 1, now=PERIOD_START + timedelta(days=30))
    check("selection: the second later job one hour past the 14 days is not added (the gain is not shown)",
          P["jobs"] == 9 and P["gain_not_shown"] and P["complete"] and not P["gain"]["met"] and P["added"] == 1, P)
    check("selection: the days are stated", P["days_end"] == stamp(D + 1), P["days_end"])
    # --now
    seven = [S6] * 7
    P = sel(seven, now=PERIOD_START + timedelta(days=14, hours=1))
    check("selection: seven jobs, now exactly at the end of the 14 days: not complete, waiting", not P["complete"] and P["wait"] and not P["gain_not_shown"], P)
    P = sel(seven, now=PERIOD_START + timedelta(days=14, hours=1, minutes=1))
    check("selection: seven jobs, one minute after the 14 days: complete, the gain is not shown, clause 2 not met",
          P["complete"] and P["gain_not_shown"] and not P["gain"]["met"], P)
    P = sel([S3] * 8, now=PERIOD_START + timedelta(days=30))
    check("selection: eight jobs but 24 slow passes after the days: complete, gain not shown, clauses 1, 3 and 4 still computed",
          P["complete"] and P["gain_not_shown"] and not P["gain"]["met"] and P["step"]["met"] and P["rows"]["met"], P)
    P = sel([S6] * 8, now=PERIOD_START + timedelta(days=30))
    check("selection: both hold: the days passing does not matter", P["complete"] and not P["gain_not_shown"] and P["gain"]["met"])
    # not counting jobs are skipped when adding
    P = sel([S6] * 5, [dict(G, counts=False, why="x")] + [S0] * 4)
    check("selection: a job that does not count is skipped when adding", P["added"] == 3 and all("alt_20261123T0230Z" not in f for f in P["job_files"]), P)
    # it is paper_status.alt_select
    jobs = jobs_of([S6] * 5) + jobs_of([S0] * 4, 24 * 3 + 2)
    s = ps.alt_select(jobs, p3.when(END), NOW0)
    P = run(jobs=jobs)["part3"]
    check("selection: the files used are exactly paper_status.alt_select's", [j["file"] for j in s["used"]] == P["job_files"] and s["in_period"] == P["in_period"])
    # not complete, and read as is
    res = run(jobs=jobs_of([S6] * 7))
    md = rule.to_md(res)
    check("not complete: the exact line, no verdict", res["verdict"] is None and "PART 3 NOT COMPLETE: 7 of 8 jobs, 42 of 30 slow one-worker passes; the jobs go on and the read waits" in md.splitlines()
          and "Trades workers: pass" not in md and "no verdict (part 3 not complete)" in md, md[:700])
    res = run(jobs=jobs_of([S3] * 8))
    check("not complete: eight jobs, 24 slow: the line names both counts", "PART 3 NOT COMPLETE: 8 of 8 jobs, 24 of 30 slow one-worker passes; the jobs go on and the read waits" in rule.to_md(res).splitlines())
    res = run(jobs=jobs_of([S6] * 7), read_as_is=True)
    check("not complete: --read-as-is gives a verdict, fail, clauses 1, 2 and 4 not met", res["verdict"] == "fail" and not res["part3"]["step"]["met"]
          and not res["part3"]["gain"]["met"] and not res["part3"]["rows"]["met"] and res["part3"]["pace"]["met"] and "Read as is" in rule.to_md(res))
    res = run(jobs=[], read_as_is=True)
    check("not complete: no jobs at all, read as is, fails without breaking", res["verdict"] == "fail" and "PART 3 NOT COMPLETE: 0 of 8 jobs, 0 of 30" in rule.to_md(res))
    res = run(jobs=jobs_of([S3] * 8), now=PERIOD_START + timedelta(days=30))
    md = rule.to_md(res)
    check("gain not shown: Part 3 complete, the verdict fails with the words, no NOT COMPLETE line",
          res["verdict"] == "fail" and not res["holds"]["part3.2_gain"] and "the gain is not shown" in md and "PART 3 NOT COMPLETE" not in md, md[:900])


def test_requests_and_stops():
    # requests inside a step: failed share at most 1%, in-step share at most 2%, exact
    def req(**over):
        return run(r6=good_rows(10, **over), r5=good_rows(10, **over))["part4"]["requests"]
    q = req(pre_fetched=990, pre_error=10)
    check("requests: failed exactly 1% (10 of 1000 in each heartbeat) is met", q["failed_clause"]["met"] and q["failed"] == 100 and q["requests"] == 10000, q)
    check("requests: failed 11 of 1000 is not met", not req(pre_fetched=989, pre_error=11)["failed_clause"]["met"])
    def odd(n_od):
        r6 = beats(range(1, 11), **dict(GOOD4, pre_missing=0))
        r6[0]["counts"]["pre_ondemand"] = n_od
        return run(r6=r6, r5=good_rows(10, pre_missing=0))["part4"]["requests"]
    check("requests: in-step exactly 2% of coin-minutes (108 of 5,400) is met", odd(108)["in_step_clause"]["met"] and odd(108)["in_step"] == 108)
    check("requests: 109 of 5,400 is not met", not odd(109)["in_step_clause"]["met"])
    check("requests: counters absent from every heartbeat is not met (and is stated)", not run(r6=beats(range(1, 11)))["part4"]["requests"]["met"]
          and "No heartbeat of the sixth book in the period carries the counters: not met." in rule.to_md(run(r6=beats(range(1, 11)))))
    # the first step after each start is left out
    r6 = beats(range(1, 11), **dict(GOOD4, pre_missing=0))
    r6[2]["counts"]["pre_missing"] = 18
    starts = [r6[2]["t"] - timedelta(minutes=10)]
    q = run(r6=r6, s6=starts)["part4"]["requests"]
    check("requests: pre_missing of the first step after a start (18) is left out", q["in_step"] == 0 and q["left_out_first_steps"] == 18, q)
    # against the fifth book, over the common heartbeat times only
    def inst(six, five):
        r6 = [dict(r, counts=dict(r["counts"], pre_ondemand=six if r["t"] == T0 + timedelta(minutes=30) else 0)) for r in good_rows(10, pre_missing=0)]
        r5 = [dict(r, counts=dict(r["counts"], pre_ondemand=five if r["t"] == T0 + timedelta(minutes=30) else 0)) for r in good_rows(10, pre_missing=0)]
        return run(r6=r6, r5=r5)["part4"]["requests"]
    q = inst(50, 50)
    check("requests: the sixth's in-step share equal to the fifth's is met, over 10 common times", q["against_fifth"]["met"] and q["against_fifth"]["common_heartbeat_times"] == 10, q["against_fifth"])
    check("requests: one more in-step request in the sixth than in the fifth is not met", not inst(51, 50)["against_fifth"]["met"] and not inst(51, 50)["met"])
    check("requests: fewer in the sixth is met", inst(49, 50)["against_fifth"]["met"])
    # the heartbeat pairing: heartbeats of one book only are left out
    r6 = good_rows(10, pre_missing=0)
    r6[8]["counts"]["pre_ondemand"] = 20                       # the sixth's bad half hours at times 9 and 10...
    r6[9]["counts"]["pre_ondemand"] = 20
    q = run(r6=r6, r5=good_rows(8, pre_missing=0))["part4"]["requests"]
    check("requests: heartbeats the fifth book does not have are left out of the pairing (8 common), though not of the 2% clause",
          q["against_fifth"]["met"] and q["against_fifth"]["common_heartbeat_times"] == 8 and q["in_step"] == 40 and q["in_step_clause"]["met"], q)
    q = run(r6=good_rows(10), r5=beats(range(50, 60), **GOOD4))["part4"]["requests"]
    check("requests: no common heartbeat time is not met, with zero times stated", not q["against_fifth"]["met"] and q["against_fifth"]["common_heartbeat_times"] == 0 and not q["met"])
    check("requests: the markdown says how many common times", "over 100 heartbeat times at which both books have a heartbeat" in rule.to_md(run()))
    # stops
    def stp(r6, r5):
        return run(r6=r6, r5=r5)["part4"]["stops"]
    def lim(base, ks, v=1, key="tb_fb_limited"):
        return [dict(r, counts=dict(r["counts"], **{key: v})) if (r["t"] - T0) // timedelta(minutes=30) in ks else r for r in base]
    base = good_rows(20)
    s = stp(lim(base, [5, 9]), lim(base, [5, 9]))
    check("stops: a limit in both books at the same heartbeat time is allowed", s["limited_clause"]["met"] and s["limited_sixth"] == 2 and s["limited_fifth"] == 2 and s["met"], s)
    s = stp(lim(base, [5, 9]), lim(base, [5]))
    check("stops: a limit in the sixth alone is not allowed, and its time is named", not s["limited_clause"]["met"] and s["limited_sixth_alone"] == ["2026-11-20T04:30Z"] and not s["met"], s)
    s = stp(lim(base, [5]), lim(base, [6]))
    check("stops: a limit in each at different times fails (the sixth's is alone)", not s["limited_clause"]["met"])
    s = stp(lim(base, [5]), [r for r in base if r["t"] != T0 + timedelta(minutes=150)])
    check("stops: a limit in the sixth at a time the fifth has no heartbeat is not allowed", not s["limited_clause"]["met"])
    check("stops: a limit in the fifth alone does not matter", stp(base, lim(base, [3, 4, 5]))["met"])
    check("stops: a counter of 0 is not a stop", stp(lim(base, [5], 0), base)["met"])
    five = lim(base, [1, 2, 3], key="tb_fb_error")
    check("stops: errors at the fifth's count plus 2 (5 against 3) are met, allowed 5", stp(lim(base, [1, 2, 3, 4, 5], key="tb_fb_error"), five)["error_clause"]["met"]
          and stp(lim(base, [1, 2, 3, 4, 5], key="tb_fb_error"), five)["allowed_errors"] == 5)
    s = stp(lim(base, [1, 2, 3, 4, 5, 6], key="tb_fb_error"), five)
    check("stops: errors at the fifth's count plus 3 (6 against 3) fail", not s["error_clause"]["met"] and not s["met"] and s["errors_sixth"] == 6 and s["errors_fifth"] == 3)
    check("stops: no errors anywhere is met", stp(base, base)["error_clause"]["met"])
    check("stops: zero in the fifth, two in the sixth is met; three is not", stp(lim(base, [1, 2], key="tb_fb_error"), base)["error_clause"]["met"]
          and not stp(lim(base, [1, 2, 3], key="tb_fb_error"), base)["error_clause"]["met"])
    res = run(r6=lim(base, [5]), r5=base)
    check("stops: a stop alone makes the verdict fail", res["verdict"] == "fail" and not res["holds"]["part4.4_stops"] and res["holds"]["part4.3_requests"])


def test_verdict_and_period():
    # items fail -> fail
    res = run(items="fail")
    check("items 1 to 5: fail makes the verdict fail, alone", res["verdict"] == "fail" and [k for k, v in res["holds"].items() if not v] == ["part4.2_items_1_5"])
    # each clause alone fails the verdict (the other seven hold)
    def gj(**kw):
        return dict(G, **kw)
    cases = {"part3.1_no_harm": dict(jobs=jobs_of([gj(steps=asteps(20, 20, "1.000", "1.060", slow1=4, slow3=1, fb1=1, fb3=1))] * 8)),
             "part3.2_gain": dict(jobs=jobs_of([gj(steps=asteps(20, 20, slow1=4, slow3=4, fb1=1, fb3=1))] * 8)),
             "part3.3_pace": dict(jobs=jobs_of([gj(steps=asteps(20, 20, slow1=4, slow3=1, fb1=1, fb3=1, peak3=9))] + [G] * 7)),
             "part3.4_rows": dict(jobs=jobs_of([gj(rows=((100, 2), (100, 4)))] * 8)),
             "part4.1_decisions": dict(sixth=spec(300, w=9, l=15, m=280, r=300))}
    for k, kw in cases.items():
        res = run(**kw)
        bad = [x for x, v in res["holds"].items() if not v]
        check(f"verdict: {k} alone fails it", bad == [k] and res["verdict"] == "fail", bad)
    # the period condition
    res = run(fifth=spec(300, w=9, l=3, m=280, r=300), sixth=spec(299, w=9, l=3, m=280, r=299))
    md = rule.to_md(res)
    check("period: 299 new bids in the sixth: PERIOD NOT COMPLETE, no verdict", res["verdict"] is None and not res["condition"]["met"]
          and "**PERIOD NOT COMPLETE**; no verdict" in md and "Trades workers: pass" not in md and "no verdict (period not complete)" in md, md[:500])
    res = run(fifth=spec(299), sixth=spec(300))
    check("period: 299 in the fifth: not complete too", res["verdict"] is None)
    res = run(fifth=spec(300), sixth=spec(300))
    check("period: exactly 300 in each is complete", res["condition"]["met"] and res["verdict"] == "pass")
    res = run(sixth=spec(299, w=9, l=3, m=280, r=299), read_as_is=True)
    check("period: --read-as-is gives the verdict, stated in the output", res["verdict"] == "pass" and "read as is" in rule.to_md(res), rule.to_md(res)[:600])
    res = run(sixth=spec(299, w=9, l=3, m=280, r=299), items="fail", read_as_is=True)
    check("period: --read-as-is still fails when a clause fails", res["verdict"] == "fail")
    res = run(sixth=spec(299, w=9, l=3, m=280, r=299), jobs=jobs_of([G] * 7, first_hour=1)[:6])
    check("period and jobs both incomplete: both reasons in the no-verdict line", "period not complete and part 3 not complete" in rule.to_md(res))
    # the reported items, deciding nothing
    r6 = good_rows(10)
    res = run(r6=r6, trades=dict(n=10, median=F(4), max=F("9.5")), jobs=jobs_of([dict(G, steps=asteps(20, 20, "5.000", "3.000", slow1=0))] * 8), now=NOW0 + timedelta(days=30))
    rep = res["reported"]
    check("reported: step_s.trades, the Part 3 pass medians and the data-step medians over the common times",
          rep["step_s_trades"]["median_of_medians_s"] == 4.0 and rep["step_s_trades"]["largest_max_s"] == 9.5 and rep["step_s_trades"]["heartbeats"] == 10
          and rep["part3"]["median_one_s"] == 5.0 and rep["part3"]["median_three_s"] == 3.0 and rep["part3"]["diff_median_s"] == -2.0
          and len(rep["part3"]["jobs"]) == 8 and rep["data_step"]["common_heartbeat_times"] == 10
          and rep["data_step"]["sixth_median_s"] == 10.0 and rep["data_step"]["fifth_median_s"] == 10.0 and rep["data_step"]["decides"] == "nothing", rep)
    md = rule.to_md(res)
    check("reported: in the markdown, and they decide nothing", "step_s.trades" in md and "median of the half-hour medians 4.000 s, largest maximum 9.500 s" in md
          and "median one 5.000 s, three 3.000 s, difference -2.000 s" in md
          and "first version of the plan asked for a 0.2 s gain at the median over half-hour pairs" in md and res["verdict"] == "fail")
    bad = run(r6=beats(range(1, 11), data=99.0, **GOOD4))
    check("reported: a data step of 99 s in the sixth decides nothing", bad["verdict"] == "pass")
    # the unreadable file and the listing in the markdown
    res = run(jobs=jobs_of([G] * 8, extra=[("alt_20261120T0405Z.json", "{not json")]))
    md = rule.to_md(res)
    check("markdown: an unreadable pair file is listed and the pace clause is not met", "A file that could not be read: alt_20261120T0405Z.json" in md
          and "| 3. the pace |" in md and res["verdict"] == "fail")
    check("markdown: no at-sign", chr(64) not in md)


def write_log(root, folder, n, counts=None, trades=None, extra=(), data=10.0):
    """n heartbeats at 30-minute marks from 00:30 on Nov 20 (data-step medians `data`), a backfill at the start."""
    d = os.path.join(root, folder)
    os.makedirs(d, exist_ok=True)
    ev = [dict(ts=(T0 + timedelta(minutes=1)).replace(tzinfo=None).isoformat(), kind="backfill")]
    for i in range(1, n + 1):
        step = {"data": [data, data + 1.0]}
        if trades:
            step["trades"] = list(trades)
        ev.append(dict(ts=(T0 + timedelta(minutes=30 * i)).replace(tzinfo=None).isoformat(), kind="heartbeat", equity=250000,
                       committed=1000, counts=dict(counts or {}), step_s=step))
    ev += list(extra)
    ev.sort(key=lambda e: e["ts"])
    with open(os.path.join(d, "events.jsonl"), "w") as f:
        for e in ev:
            f.write(json.dumps(e) + "\n")
    return d


def test_cli_and_shared_numbers():
    with tempfile.TemporaryDirectory() as tmp:
        n = 120
        counts = dict(GOOD4, tb_built=540)
        stamp_ = lambda m: (T0 + timedelta(minutes=m)).replace(tzinfo=None).isoformat()      # noqa: E731
        d6 = write_log(tmp, "paper_spot_tw", n, counts, trades=(4.0, 9.5),
                       extra=[dict(ts=stamp_(95), kind="backfill"), dict(ts=stamp_(98), kind="arm")])
        d5 = write_log(tmp, "paper_spot_r5", n, counts, extra=[dict(ts=stamp_(95), kind="backfill"), dict(ts=stamp_(98), kind="arm")])
        rec = os.path.join(tmp, "rec")
        os.makedirs(rec)
        meta, B, S = tables(spec(300, w=9, l=3, m=280, r=300), spec(300, w=9, l=3, m=280, r=300))
        json.dump(meta, open(os.path.join(rec, "two_books.json"), "w"))
        B.to_csv(os.path.join(rec, "item7_bids.csv"), index=False)
        S.to_csv(os.path.join(rec, "side_by_side.csv"), index=False)
        out = os.path.join(tmp, "out")
        pdir = os.path.join(tmp, "reports", "owner", "workers_alt")
        for i in range(9):                               # eight that count (both first arms), one that does not
            st = f"2026-11-2{i // 4}T{(i % 4) * 6:02d}:35:00Z"
            write_alt(pdir, f"alt_{st[:4]}{st[5:7]}{st[8:10]}T{st[11:13]}{st[14:16]}Z.json", st, asteps(20, 20, "1.000", "0.900", slow1=4, slow3=1, fb1=1, fb3=1),
                      first="one" if i % 3 else "three", rows=((100, 2), (100, 2)), counts=i != 8, why=None if i != 8 else "x")
        cmd = [sys.executable, os.path.join(HERE, "rule.py"), "--dir", rec, "--alt", pdir, "--now", "2026-11-24T00:00:00Z", "--start", "2026-11-20T00:30", "--end", "2026-11-23T00:29",
               "--sixth", d6, "--fifth", d5, "--items-1-5", "pass", "--out", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        check("cli runs", r.returncode == 0, r.stderr[-500:])
        js = json.load(open(os.path.join(out, "trades_workers_rule.json")))
        md = open(os.path.join(out, "trades_workers_rule.md")).read()
        check("cli: prints the markdown it writes", r.stdout.strip() == md.strip())
        check("cli: verdict pass, eight jobs, 120 heartbeats counted, two starts left out as first steps (1 each)",
              js["verdict"] == "pass" and js["part3"]["jobs"] == 8 and js["part3"]["step"]["median_three_s"] == 0.9 and js["part3"]["step"]["median_one_s"] == 1.0
              and js["part4"]["requests"]["heartbeats"] == 120 and js["part4"]["requests"]["left_out_first_steps"] == 2
              and "**Trades workers: pass**" in md, js["holds"])
        check("cli: step_s.trades read from the log", js["reported"]["step_s_trades"]["heartbeats"] == 120
              and js["reported"]["step_s_trades"]["median_of_medians_s"] == 4.0 and js["reported"]["step_s_trades"]["largest_max_s"] == 9.5)
        # the same numbers as the status report on the same log
        rows6, starts6, trades6 = rule.log_data(d6, "2026-11-20T00:30", "2026-11-23T00:29")
        rows_ref, starts_ref = p3.log_rows(d6, "2026-11-20T00:30", "2026-11-23T00:29")
        check("shared: log_data gives what part3_rule.log_rows gives", [(r["t"], r["counts"], r["minutes"]) for r in rows6] == [(r["t"], r["counts"], r["minutes"]) for r in rows_ref]
              and starts6 == starts_ref and trades6["n"] == 120)
        book = ps.load_book(tmp, "paper_spot_tw")
        ev = book["events"]
        s = ps.stats(book, 250000.0, True)
        rt = ps.running_time(ev, s["first"], s["newest"])
        dq = ps.data_quality(ev, rt)
        a = ps.measure4(dq["rep"], ps.startup_steps(ev))
        check("shared: the rule and the status report give the same measure 4 for the sixth book on the same log",
              a["failed"] == js["part4"]["requests"]["failed"] and a["in_step"] == js["part4"]["requests"]["in_step"]
              and float(a["coin_minutes"]) == js["part4"]["requests"]["coin_minutes"] and a["left_out"] == js["part4"]["requests"]["left_out_first_steps"], a)
        text = ps.build_report(tmp, T0 + timedelta(days=4))
        sec = text.split("## Rule progress for the sixth book")[1].split("\n## ")[0]
        row1 = [l for l in sec.splitlines() if l.startswith("| 1. No harm")][0]
        check("shared: the status report reads the same jobs and the same medians", "three 0.90 s, one 1.00 s, over 160 and 160 steps" in row1 and row1.endswith("| meets |"), row1)
        check("shared: the status report has the same job count", "8 jobs (8 needed); 32 slow one-worker passes (30 needed)" in sec, sec[:1500])
        check("shared: the status report prints the same in-step figure",
              f"{a['in_step']:,.0f} of {float(a['coin_minutes']):,.0f}" in sec, sec[-900:])
        check("shared: the status report has the same step_s.trades", "median of the half-hour medians 4.00 s, largest maximum 9.50 s, over 120 heartbeats" in sec)
        # a period that differs from the folder's is refused
        r = subprocess.run(cmd[:-2] + ["--end", "2026-11-20T09:59", "--out", out], capture_output=True, text=True)
        check("cli: a period that differs from the folder's is refused", r.returncode != 0 and "differs" in r.stderr)
        # the log is cut at the period's end
        rows, _, _ = rule.log_data(d6, "2026-11-20T05:00", "2026-11-20T09:59")
        check("log_data: only heartbeats inside [start, end]", len(rows) == 10 and rows[0]["t"] == T0 + timedelta(hours=5)
              and rows[-1]["t"] == T0 + timedelta(hours=9, minutes=30))
        rows, _, _ = rule.log_data(d6, "2026-11-20T05:00", "2026-11-20T10:00")
        check("log_data: the end minute is included", rows[-1]["t"] == T0 + timedelta(hours=10))
        check("log_data: a missing folder is an error", raises(lambda: rule.log_data(os.path.join(tmp, "nope"), "2026-11-20T05:00", "2026-11-20T10:00"), "no events.jsonl"))
        # seven jobs count: the line, no verdict; read as is: fail
        os.remove(os.path.join(pdir, "alt_20261120T0035Z.json"))
        r = subprocess.run(cmd, capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "trades_workers_rule.json")))
        check("cli: 7 jobs count: the line is printed, no verdict",
              r.returncode == 0 and "PART 3 NOT COMPLETE: 7 of 8 jobs, 28 of 30 slow one-worker passes; the jobs go on and the read waits" in r.stdout.splitlines()
              and js["verdict"] is None and "Trades workers: pass" not in r.stdout, r.stdout[:500])
        r = subprocess.run(cmd + ["--read-as-is"], capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "trades_workers_rule.json")))
        check("cli: --read-as-is gives a verdict (fail: clauses 1, 2 and 4 need 8 jobs)", js["verdict"] == "fail" and not js["part3"]["step"]["met"], r.stdout[:300])
        r = subprocess.run(cmd[:cmd.index("--now") + 1] + ["2026-12-30T00:00:00Z"] + cmd[cmd.index("--now") + 2:], capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "trades_workers_rule.json")))
        check("cli: --now after the 14 days: complete, the gain is not shown, fail", js["verdict"] == "fail" and js["part3"]["gain_not_shown"] and "the gain is not shown" in r.stdout, r.stdout[:300])
        # a later job is added
        write_alt(pdir, "alt_20261123T0305Z.json", "2026-11-23T03:05:00Z", asteps(20, 20, "1.000", "0.900", slow1=4, slow3=1, fb1=1, fb3=1), first="three", rows=((100, 2), (100, 2)))
        r = subprocess.run(cmd, capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "trades_workers_rule.json")))
        check("cli: a job after the period is added: pass, with the numbers in the output",
              js["verdict"] == "pass" and js["part3"]["in_period"] == 7 and js["part3"]["added"] == 1 and js["part3"]["last_used_start"] == "2026-11-23T03:05:00Z"
              and "alt_20261123T0305Z.json" in js["part3"]["job_files"] and "7 started in the period and 1 were added from after it" in r.stdout, r.stdout[:900])
        # default --alt and --out
        check("defaults: the alt folder is the status report's and the out folder is --dir", rule.ALT_DEFAULT == os.path.join("reports", "owner", "workers_alt"))
        r = subprocess.run([c for c in cmd if c not in ("--out", out)], capture_output=True, text=True)
        check("cli: --out defaults to --dir", r.returncode == 0 and os.path.isfile(os.path.join(rec, "trades_workers_rule.json")) and os.path.isfile(os.path.join(rec, "trades_workers_rule.md")))
        # a stop in the sixth log alone through the command line
        d6b = write_log(tmp, "paper_spot_tw_b", n, dict(counts, tb_fb_limited=1), trades=(4.0, 9.5))
        r = subprocess.run(cmd[:cmd.index("--sixth") + 1] + [d6b] + cmd[cmd.index("--sixth") + 2:], capture_output=True, text=True)
        check("cli: a book folder that is not the one in two_books.json is refused", r.returncode != 0 and "not a fifth-book / sixth-book" in r.stderr, r.stderr[-300:])


def test_jobs_in_paper_status_are_the_same_numbers():
    # the status report's section and the rule use one pair of functions for the Part 3 clauses: spot-check a mixed set
    bad = dict(steps=asteps(20, 20, peak3=9), counts=False, why="x")
    specs = [dict(G, steps=asteps(20, 20, "1.000", "1.040", slow1=4, slow3=1))] * 4 + [bad] + [dict(G, steps=asteps(20, 20, "1.000", "1.080", slow1=4, slow3=1))] * 4
    jobs = jobs_of(specs)
    m = ps.alt_measure(jobs, ps.alt_select(jobs, p3.when(END), NOW0))
    P = run(jobs=jobs)["part3"]
    check("shared: rule and status measure agree on a mixed set",
          m["jobs"] == P["jobs"] and str(m["median"][3]) == P["step"]["median_three_exact"] and m["pace_met"] == P["pace"]["met"] and m["rows_met"] == P["rows"]["met"]
          and m["gain_met"] == P["gain"]["met"] and m["step_met"] == P["step"]["met"] and not m["pace_met"], (m["jobs"], P["step"]))


def main():
    for t in (test_baseline_and_labels, test_decisions, test_part3_clauses, test_chance_branch_texts, test_job_selection, test_requests_and_stops,
              test_verdict_and_period, test_cli_and_shared_numbers, test_jobs_in_paper_status_are_the_same_numbers):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
