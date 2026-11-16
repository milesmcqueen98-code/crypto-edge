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


# ---------------------------------------------------------------- pair files (loaded through paper_status, as the rule does)
def wrun(median="10.00", longest="6.00", pass_median="4.00", fb=0, peak=7, compared=100, differ=1, refused=False, limited=False):
    return dict(data_end_median_text=median, trades_pass_longest_text=longest, trades_pass_median_text=pass_median, fb_budget=fb,
                peak_per_second=peak, rows_compared=compared, rows_differ=differ, refused=refused, limited=limited, steps_timed=31)


def write_pair(folder, name, start, one=None, three=None, counts=True, why=None, order="ab"):
    os.makedirs(folder, exist_ok=True)
    runs = [dict(workers=1, label="one", **(one or wrun())), dict(workers=3, label="three", **(three or wrun()))]
    if order == "ba":
        runs.reverse()
    with open(os.path.join(folder, name), "w") as f:
        json.dump(dict(mode="workers", utc_start=start, order=order, counts=counts, why_not=why, runs=runs), f)


def stamp(hours):
    return (PERIOD_START + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def fill_pairs(folder, specs, first_hour=1, **kw):
    """Pair files hour by hour from first_hour; a spec is None, or (one, three) run dicts, or a dict of write_pair keywords."""
    for i, sp in enumerate(specs):
        h = first_hour + i
        args = dict(kw)
        if isinstance(sp, dict):
            args.update(sp)
        elif sp:
            args.update(one=sp[0], three=sp[1])
        write_pair(folder, "pair_%s.json" % (PERIOD_START + timedelta(hours=h)).strftime("%Y%m%dT%H%MZ"), stamp(h), **args)


def pairs_of(specs, first_hour=1, extra=(), **kw):
    """ps.load_workers_pairs on a folder holding these pairs (extra: raw (name, text) files)."""
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "pairs")
        fill_pairs(d, specs, first_hour, **kw)
        for n, text in extra:
            open(os.path.join(d, n), "w").write(text)
        return ps.load_workers_pairs(d)


def steps(diffs):
    """Specs whose three-minus-one data steps are these decimals (texts)."""
    return [(wrun(median="10.00"), wrun(median=str(F("10.00") + F(d)))) for d in diffs]


GOOD_PAIRS = pairs_of([(wrun(median="10.00", differ=2), wrun(median="9.50", differ=1))] * 8)


def run(fifth=None, sixth=None, items="pass", r6=None, r5=None, s6=None, s5=None, trades=None, pairs=None, **kw):
    fifth = fifth or spec(300, w=9, l=3, m=280, r=300)
    sixth = sixth or spec(300, w=9, l=3, m=280, r=300)
    over = kw.pop("over", None)
    meta, B, S = tables(fifth, sixth, over)
    r6 = r6 if r6 is not None else good_rows()
    r5 = r5 if r5 is not None else good_rows()
    trades = trades or dict(n=0, median=None, max=None)
    return rule.evaluate(meta, B, S, r6, s6 or [], r5, s5 or [], trades, items, GOOD_PAIRS if pairs is None else pairs,
                         start=START, end=END, **kw)


# ---------------------------------------------------------------- tests
def test_baseline_and_labels():
    res = run()
    check("baseline: every clause holds and the verdict is pass", res["verdict"] == "pass" and all(res["holds"].values()), res["holds"])
    check("baseline: eight keys in holds (four of Part 3, four of Part 4)", len(res["holds"]) == 8)
    md = rule.to_md(res)
    check("markdown: verdict line and label mapping", "**Trades workers: pass**" in md and "main = fifth book (paper_spot_r5)" in md
          and "tb = sixth book (paper_spot_tw)" in md)
    check("json round trip", json.loads(json.dumps(rule.public(res)))["verdict"] == "pass" and "_pairs" not in rule.public(res))
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
        return run(pairs=pairs_of(specs), **kw)["part3"]
    # 1 the step
    r = p3res(steps(["-0.20"] * 8))
    check("part 3.1: eight pairs with the median exactly -0.20 s meet", r["step"]["met"] and r["step"]["median_exact"] == "-1/5" and r["step"]["pairs"] == 8, r["step"])
    check("part 3.1: -0.19 s does not meet", not p3res(steps(["-0.19"] * 8))["step"]["met"])
    check("part 3.1: -0.21 s meets", p3res(steps(["-0.21"] * 8))["step"]["met"])
    r = p3res(steps(["-1.00"] * 7))
    check("part 3.1: seven pairs do not meet even at -1.00 s, and the read is not complete", not r["step"]["met"] and not r["complete"])
    check("part 3.1: even count, the mean of the middle two (-0.30 and -0.10) is exactly -0.20 and meets",
          p3res(steps(["-0.50"] * 2 + ["-0.30"] * 2 + ["-0.10"] * 2 + ["0.50"] * 2))["step"]["met"])
    check("part 3.1: even count, the mean of the middle two (-0.30 and -0.09) is not enough",
          not p3res(steps(["-0.50"] * 2 + ["-0.30"] * 2 + ["-0.09"] * 2 + ["0.50"] * 2))["step"]["met"])
    check("part 3.1: the exact decimals, not floats (10.10 minus 9.90 style): -0.2 from 9.90 and 10.10 meets",
          p3res([(wrun(median="10.10"), wrun(median="9.90"))] * 8)["step"]["met"])
    # 2 the slow minutes
    def slow(fb1, fb3, l1="6.00", l3="6.00", n=8):
        return [(wrun(fb=fb1, longest=l1), wrun(fb=fb3, longest=l3))] * n
    r = p3res(slow(1, 1))
    check("part 3.2: equal fallbacks and equal longest passes meet", r["slow"]["met"] and r["slow"]["longest_median_exact"] == "0", r["slow"])
    check("part 3.2: one more fallback with three does not meet", not p3res(slow(1, 1)[:7] + [(wrun(fb=1), wrun(fb=2))])["slow"]["met"])
    check("part 3.2: fewer fallbacks with three meet", p3res(slow(2, 0))["slow"]["met"])
    check("part 3.2: median of the longest pass above zero (+0.01 s) does not meet", not p3res(slow(1, 1, "6.00", "6.01"))["slow"]["met"])
    check("part 3.2: a longest pass shorter with three meets", p3res(slow(1, 1, "6.00", "5.00"))["slow"]["met"])
    half = slow(1, 1, "6.00", "5.00", n=4) + slow(1, 1, "6.00", "6.01", n=4)
    check("part 3.2: the median of the longest differences (even count) is the mean of the middle two (-1 and 0.01 give -0.495)",
          p3res(half)["slow"]["longest_median_exact"] == "-99/200" and p3res(half)["slow"]["met"])
    check("part 3.2: seven pairs do not meet", not p3res(slow(1, 1, n=7))["slow"]["met"])
    # 3 the pace, over every file of the period
    base = [None] * 8
    check("part 3.3: eight clean pairs meet", p3res(base)["pace"]["met"] and p3res(base)["pace"]["peak_max"] == 7)
    check("part 3.3: a three-worker peak of exactly 8 meets", p3res([(None, wrun(peak=8))] * 8)["pace"]["met"])
    check("part 3.3: a peak of 9 in one three-worker run does not", not p3res([(None, wrun(peak=9))] + base[1:])["pace"]["met"])
    check("part 3.3: a peak of 9 in a ONE-worker run does not matter", p3res([(wrun(peak=9), None)] * 8)["pace"]["met"])
    r = p3res(base + [dict(three=wrun(refused=True), counts=False, why="refused")])
    check("part 3.3: a refused three-worker run in a pair that does not count still fails it, and the file is named",
          not r["pace"]["met"] and len(r["pace"]["refused_or_limited"]) == 1 and r["step"]["pairs"] == 8, r["pace"])
    check("part 3.3: a limited three-worker run fails it", not p3res(base + [dict(three=wrun(limited=True), counts=False)])["pace"]["met"])
    check("part 3.3: a refusal in the one-worker run only does not", p3res(base + [dict(one=wrun(refused=True), counts=False)])["pace"]["met"])
    check("part 3.3: a peak of 9 in a pair that does not count still fails it", not p3res(base + [dict(three=wrun(peak=9), counts=False)])["pace"]["met"])
    r = run(pairs=pairs_of(base, extra=[("pair_20261120T0405Z.json", "{not json")]))["part3"]
    check("part 3.3: a file that cannot be read is listed and makes it not met", not r["pace"]["met"] and r["pace"]["unreadable"] == ["pair_20261120T0405Z.json"], r["pace"])
    r = run(pairs=pairs_of(base, extra=[("pair_20261201T0405Z.json", "{not json")]))["part3"]
    check("part 3.3: an unreadable file that started after the period (by its name) is not in the clause", r["pace"]["met"], r["pace"])
    r = run(pairs=pairs_of(base, extra=[("odd.json", "{not json")]))["part3"]
    check("part 3.3: an unreadable file with no start at all is taken as inside the period", not r["pace"]["met"])
    r = run(pairs=pairs_of(base, extra=[("pair_20261125T0305Z.json", json.dumps(dict(utc_start="2026-11-25T03:05:00Z", counts=True, runs=[dict(workers=3, label="three", **wrun(peak=12))])))]))["part3"]
    check("part 3.3: a three-worker peak of 12 in a file after the period is not in the clause", r["pace"]["met"])
    check("part 3.3: no files at all: the clause itself is met, the read is not complete", run(pairs=[])["part3"]["pace"]["met"] and not run(pairs=[])["part3"]["complete"])
    # 4 the rows
    def rows(c1, d1, c3, d3, n=8):
        return [(wrun(compared=c1, differ=d1), wrun(compared=c3, differ=d3))] * n
    check("part 3.4: equal shares meet (3 of 100 and 3 of 100; 3 of 100 and 6 of 200)", p3res(rows(100, 3, 100, 3))["rows"]["met"] and p3res(rows(100, 3, 200, 6))["rows"]["met"])
    check("part 3.4: a higher share with three does not (3 of 100 and 4 of 100; 3 of 100 and 7 of 200)",
          not p3res(rows(100, 3, 100, 4))["rows"]["met"] and not p3res(rows(100, 3, 200, 7))["rows"]["met"])
    check("part 3.4: a lower share with three meets", p3res(rows(100, 3, 100, 0))["rows"]["met"])
    check("part 3.4: a zero denominator on either side is not met", not p3res(rows(0, 0, 100, 0))["rows"]["met"] and not p3res(rows(100, 0, 0, 0))["rows"]["met"])
    check("part 3.4: summed over the pairs, not averaged (10 of 100 against 0 of 100, then seven pairs 0 of 100 against 1 of 100)",
          p3res([(wrun(compared=100, differ=10), wrun(compared=100, differ=0))] + rows(100, 0, 100, 1, n=7))["rows"]["met"])
    check("part 3.4: seven pairs do not meet", not p3res(rows(100, 3, 100, 0, n=7))["rows"]["met"])
    # a pair that does not count is left out of 1, 2 and 4 (and in 3 only through its three-worker run)
    r = p3res([(wrun(median="10.00"), wrun(median="1.00"))] * 7 + [dict(one=wrun(median="10.00"), three=wrun(median="99.00"), counts=False, why="x")])
    check("part 3: a pair that does not count is left out of the median (7 pairs, not 8)", r["step"]["pairs"] == 7 and not r["complete"])
    # a pair that says counts but has a figure missing does not count
    r = run(pairs=pairs_of([None] * 7 + [dict(three=dict(wrun(), fb_budget=None))]))["part3"]
    check("part 3: counts true with a figure missing does not count", r["step"]["pairs"] == 7)


def test_pairs_extension():
    # five in the period, then later ones: three are added, oldest first
    specs = steps(["-1.00"] * 5) + steps(["0.00"] * 5)                 # hours 1..5 inside, 6..10 after
    pairs = pairs_of(specs[:5], first_hour=1) + pairs_of(specs[5:], first_hour=24 * 3 + 2)     # after the period
    pairs.sort(key=lambda p: p["start"])
    meta, B, S = tables(spec(), spec(), start=START, end=END)
    res = run(pairs=pairs)
    P = res["part3"]
    check("pairs: five in the period and three added oldest first make eight", P["complete"] and P["in_period"] == 5 and P["added"] == 3
          and P["step"]["pairs"] == 8 and P["pair_files"][5:] == [p["file"] for p in pairs[5:8]], P)
    check("pairs: the median is over the eight used (5 x -1.00 and 3 x 0.00: -1.00)", P["step"]["median_exact"] == "-1" and P["step"]["met"])
    check("pairs: the last used start is stated, in the output", P["last_used_start"] == pairs[7]["start"].strftime("%Y-%m-%dT%H:%M:%SZ")
          and "5 started in the period and 3 were added from after it" in rule.to_md(res) and f"started {P['last_used_start']} UTC" in rule.to_md(res))
    # the later pairs after the eighth are not used, and a pair after the period does not rescue the pace clause or break it
    check("pairs: pairs after the eighth are left out of the median", len(P["pair_files"]) == 8 and pairs[8]["file"] not in P["pair_files"])
    # eight in the period: nothing is added
    res = run(pairs=pairs_of(steps(["-1.00"] * 8)) + pairs_of(steps(["5.00"] * 2), first_hour=24 * 3 + 2))
    check("pairs: eight in the period, nothing is added", res["part3"]["added"] == 0 and res["part3"]["step"]["pairs"] == 8 and res["part3"]["step"]["met"])
    # seven even with the later ones: not complete, no verdict, the exact line
    res = run(pairs=pairs_of(steps(["-1.00"] * 5)) + pairs_of(steps(["-1.00"] * 2), first_hour=24 * 3 + 2))
    md = rule.to_md(res)
    check("pairs: seven count even with the later ones: no verdict and the exact line",
          res["verdict"] is None and not res["part3"]["complete"]
          and "PART 3 NOT COMPLETE: 7 of 8 pairs count; the pair jobs go on and the read waits" in md.splitlines()
          and "no verdict (part 3 not complete)" in md and "Trades workers: pass" not in md and "Trades workers: fail" not in md, md[:700])
    res = run(pairs=pairs_of(steps(["-1.00"] * 7)), read_as_is=True)
    check("pairs: --read-as-is gives a verdict with the clauses that need 8 pairs not met", res["verdict"] == "fail" and not res["part3"]["step"]["met"]
          and "Read as is" in rule.to_md(res) and "**Trades workers: fail**" in rule.to_md(res))
    # the pairs used are the status report's: the same files, whatever the arrangement
    agree = True
    for k_in, k_after in ((0, 0), (3, 2), (7, 4), (8, 3), (5, 9)):
        ps_ = pairs_of(steps(["-0.30"] * k_in)) + pairs_of(steps(["-0.10"] * k_after), first_hour=24 * 3 + 2) + pairs_of([dict(counts=False, why="x")], first_hour=50)
        ps_.sort(key=lambda p: p["start"])
        mine = ps.workers_pairs_measure(ps_, p3.when(START), p3.when(END), None, 8, extend=True)
        ref = ps.pairs_measure(ps_, p3.when(START), p3.when(END), None, 8, extend=True)
        agree = agree and [p["file"] for p in mine["used"]] == [p["file"] for p in ref["used"]] and mine["median"] == ref["median"] \
            and mine["in_period"] == ref["in_period"] and mine["added"] == ref["added"]
    check("pairs: the pairs used are exactly paper_status.pairs_measure's (extension logic shared) on five arrangements", agree)
    # the same logic as the fifth book's loader and rule: pairs of the fifth book's files, same selection
    agree = True
    for k_in, k_after in ((3, 2), (8, 3)):
        old = []
        for i in range(k_in + k_after):
            h = i + 1 if i < k_in else 24 * 3 + 2 + (i - k_in)
            old.append(dict(file=f"o{i}", start=PERIOD_START + timedelta(hours=h), counts=True, diff=F(-1)))
        new = pairs_of(steps(["-1.00"] * k_in)) + pairs_of(steps(["-1.00"] * k_after), first_hour=24 * 3 + 2)
        a = ps.pairs_measure(old, p3.when(START), p3.when(END), None, 8, extend=True)
        b = ps.workers_pairs_measure(new, p3.when(START), p3.when(END), None, 8, extend=True)
        agree = agree and (a["n"], a["in_period"], a["added"], a["complete"]) == (b["n"], b["in_period"], b["added"], b["complete"])
    check("pairs: counts, in-period and added numbers agree with the fifth book's pairs on the same arrangement", agree)
    # the boundary: a pair at the end minute is in the period, one a minute later is after it
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "p")
        for i, st in enumerate(["2026-11-23T00:29:59Z", "2026-11-23T00:30:00Z"]):
            write_pair(d, f"pair_b{i}.json", st)
        ld = ps.load_workers_pairs(d)
        m = ps.workers_pairs_measure(ld, p3.when(START), p3.when(END))
        check("pairs: a start inside the end minute is in the period, the next minute is not", m["n"] == 1 and m["used"][0]["file"] == "pair_b0.json")


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
    def good(**three):
        return (wrun(median="10.00", differ=2), wrun(**dict(dict(median="9.50", differ=1), **three)))
    cases = {"part3.1_step": dict(pairs=pairs_of([(wrun(median="10.00", differ=2), wrun(median="9.81", differ=1))] * 8)),
             "part3.2_slow_minutes": dict(pairs=pairs_of([good(fb=1)] * 8)),
             "part3.3_pace": dict(pairs=pairs_of([good(peak=9)] + [good()] * 7)),
             "part3.4_rows": dict(pairs=pairs_of([good(differ=3)] * 8)),
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
    res = run(sixth=spec(299, w=9, l=3, m=280, r=299), pairs=pairs_of(steps(["-1.00"] * 7)))
    check("period and pairs both incomplete: both reasons in the no-verdict line", "period not complete and part 3 not complete" in rule.to_md(res))
    # the reported items, deciding nothing
    r6 = good_rows(10)
    res = run(r6=r6, trades=dict(n=10, median=F(4), max=F("9.5")), pairs=pairs_of([(wrun(pass_median="5.00", median="10.00"), wrun(pass_median="3.00", median="9.50"))] * 8))
    rep = res["reported"]
    check("reported: step_s.trades, the pairs' trades-pass medians and the data-step medians over the common times",
          rep["step_s_trades"]["median_of_medians_s"] == 4.0 and rep["step_s_trades"]["largest_max_s"] == 9.5 and rep["step_s_trades"]["heartbeats"] == 10
          and rep["trades_pass_medians_of_the_pairs"]["median_one_s"] == 5.0 and rep["trades_pass_medians_of_the_pairs"]["median_three_s"] == 3.0
          and len(rep["trades_pass_medians_of_the_pairs"]["pairs"]) == 8 and rep["data_step"]["common_heartbeat_times"] == 10
          and rep["data_step"]["sixth_median_s"] == 10.0 and rep["data_step"]["fifth_median_s"] == 10.0 and rep["data_step"]["decides"] == "nothing", rep)
    md = rule.to_md(res)
    check("reported: in the markdown, and they decide nothing", "step_s.trades" in md and "median of the half-hour medians 4.000 s, largest maximum 9.500 s" in md
          and "three 3.000 s, one 5.000 s" in md and res["verdict"] == "pass")
    bad = run(r6=beats(range(1, 11), data=99.0, **GOOD4))
    check("reported: a data step of 99 s in the sixth decides nothing", bad["verdict"] == "pass")
    # the unreadable file and the listing in the markdown
    res = run(pairs=pairs_of([None] * 8, extra=[("pair_20261120T0405Z.json", "{not json")]))
    md = rule.to_md(res)
    check("markdown: an unreadable pair file is listed and the pace clause is not met", "Files that could not be read: pair_20261120T0405Z.json" in md
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
        pdir = os.path.join(tmp, "reports", "owner", "step_pairs_tw")
        for i in range(9):                               # eight that count (both orders), one that does not
            write_pair(pdir, f"pair_{i}.json", f"2026-11-2{i // 4}T{(i % 4) * 6:02d}:35:00Z", order="ab" if i % 3 else "ba",
                       one=wrun(median="10.00", fb=1), three=wrun(median="9.50", fb=1), counts=i != 8, why=None if i != 8 else "x")
        cmd = [sys.executable, os.path.join(HERE, "rule.py"), "--dir", rec, "--pairs", pdir, "--start", "2026-11-20T00:30", "--end", "2026-11-23T00:29",
               "--sixth", d6, "--fifth", d5, "--items-1-5", "pass", "--out", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        check("cli runs", r.returncode == 0, r.stderr[-500:])
        js = json.load(open(os.path.join(out, "trades_workers_rule.json")))
        md = open(os.path.join(out, "trades_workers_rule.md")).read()
        check("cli: prints the markdown it writes", r.stdout.strip() == md.strip())
        check("cli: verdict pass, eight pairs, 120 heartbeats counted, two starts left out as first steps (1 each)",
              js["verdict"] == "pass" and js["part3"]["step"]["pairs"] == 8 and js["part3"]["step"]["median_s"] == -0.5
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
        row1 = [l for l in sec.splitlines() if l.startswith("| 1. The step")][0]
        check("shared: the status report reads the same pairs and the same median", "8 pairs (8 needed); median -0.50 s" in row1 and row1.endswith("| meets |"), row1)
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
        # seven pairs count: the line, no verdict; read as is: fail
        os.remove(os.path.join(pdir, "pair_0.json"))
        r = subprocess.run(cmd, capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "trades_workers_rule.json")))
        check("cli: 7 pairs count: the line is printed, no verdict",
              r.returncode == 0 and "PART 3 NOT COMPLETE: 7 of 8 pairs count; the pair jobs go on and the read waits" in r.stdout.splitlines()
              and js["verdict"] is None and "Trades workers: pass" not in r.stdout, r.stdout[:500])
        r = subprocess.run(cmd + ["--read-as-is"], capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "trades_workers_rule.json")))
        check("cli: --read-as-is gives a verdict (fail: the pair clauses need 8)", js["verdict"] == "fail" and not js["part3"]["step"]["met"], r.stdout[:300])
        # a later pair is added
        write_pair(pdir, "pair_late.json", "2026-11-23T03:05:00Z", one=wrun(median="10.00", fb=1), three=wrun(median="9.50", fb=1), order="ba")
        r = subprocess.run(cmd, capture_output=True, text=True)
        js = json.load(open(os.path.join(out, "trades_workers_rule.json")))
        check("cli: a pair after the period is added: pass, with the numbers in the output",
              js["verdict"] == "pass" and js["part3"]["in_period"] == 7 and js["part3"]["added"] == 1 and js["part3"]["last_used_start"] == "2026-11-23T03:05:00Z"
              and "pair_late.json" in js["part3"]["pair_files"] and "7 started in the period and 1 were added from after it" in r.stdout, r.stdout[:900])
        # default --pairs and --out
        check("defaults: the pairs folder is the status report's and the out folder is --dir", rule.PAIRS_DEFAULT == os.path.join("reports", "owner", "step_pairs_tw"))
        r = subprocess.run([c for c in cmd if c not in ("--out", out)], capture_output=True, text=True)
        check("cli: --out defaults to --dir", r.returncode == 0 and os.path.isfile(os.path.join(rec, "trades_workers_rule.json")) and os.path.isfile(os.path.join(rec, "trades_workers_rule.md")))
        # a stop in the sixth log alone through the command line
        d6b = write_log(tmp, "paper_spot_tw_b", n, dict(counts, tb_fb_limited=1), trades=(4.0, 9.5))
        r = subprocess.run(cmd[:cmd.index("--sixth") + 1] + [d6b] + cmd[cmd.index("--sixth") + 2:], capture_output=True, text=True)
        check("cli: a book folder that is not the one in two_books.json is refused", r.returncode != 0 and "not a fifth-book / sixth-book" in r.stderr, r.stderr[-300:])


def test_pairs_in_paper_status_are_the_same_numbers():
    # the status report's section and the rule use one function for the pair clauses: spot-check a mixed set
    pairs = pairs_of(steps(["-0.50"] * 6) + [dict(three=wrun(peak=9), counts=False, why="x")] + steps(["-0.20", "0.10"]))
    m = ps.workers_pairs_measure(pairs, p3.when(START), p3.when(END), None, 8, extend=True)
    P = run(pairs=pairs)["part3"]
    check("shared: rule and status measure agree on a mixed set",
          m["n"] == P["step"]["pairs"] and str(m["median"]) == P["step"]["median_exact"] and m["pace_met"] == P["pace"]["met"] and m["rows_met"] == P["rows"]["met"]
          and m["slow_met"] == P["slow"]["met"] and m["step_met"] == P["step"]["met"] and not m["pace_met"], (m["n"], P["step"]))


def main():
    for t in (test_baseline_and_labels, test_decisions, test_part3_clauses, test_pairs_extension, test_requests_and_stops,
              test_verdict_and_period, test_cli_and_shared_numbers, test_pairs_in_paper_status_are_the_same_numbers):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
