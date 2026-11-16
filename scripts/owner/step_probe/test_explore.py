"""Offline test of explore.py on small synthetic calls.csv files written to a temporary folder.
Run: python scripts/owner/step_probe/test_explore.py (one line per check, last line "N checks, F failed",
non-zero exit on a failure)."""
import csv
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import explore as ex  # noqa: E402

COLS = ["q", "minute", "pass", "place", "coin", "sent_s", "dur_s", "verified", "reason", "pages", "gen_s", "age", "n",
        "open", "high", "low", "close", "volume", "error"]
FAILS = []
COUNT = [0]
BAR = (10, 12, 9, 11, 5.0)
OTHER = (10, 12, 9, 11.5, 5.0)  # close differs


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


def row(p, coin, minute, sent="", gen="", age="", ver=1, bar=BAR, n="3", error=""):
    r = {c: "" for c in COLS}
    r.update(q="Q", minute=minute, coin=coin, sent_s=str(sent), gen_s=str(gen), age=str(age), verified=str(ver),
             error=error, dur_s="0.2", n=n)
    r["pass"] = p
    if bar is not None:
        r["open"], r["high"], r["low"], r["close"], r["volume"] = (repr(float(x)) for x in bar)
    return r


def write(d, rows):
    os.makedirs(d)
    with open(os.path.join(d, "calls.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def ref(coin, minute, bar=BAR, ver=1):
    return row("reference", coin, minute, sent=95, ver=ver, bar=bar)


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def get(rows, runs, table, p, group, key):
    for r in rows:
        if r["runs"] == runs and r["table"] == str(table) and r["pass"] == p and r["group"] == group and r["key"] == key:
            return r
    return None


def counts(r):
    return None if r is None else tuple(int(r[k]) for k in ("rows", "verified", "equal_all", "equal_verified"))


# Run A: table 1 and 2 material. Every row has its own minute and a verified reference unless said otherwise.
def run_a():
    rows = []

    def add(r, refbar=BAR, ref_ver=1):
        rows.append(r)
        if refbar != "none":
            rows.append(ref(r["coin"], r["minute"], refbar, ref_ver))
    add(row("early", "ETH", "a1", sent=1.0, gen=-0.5))                       # sent 1, gen before, verified, equal
    add(row("early", "ETH", "a2", sent=1.999, gen=0.0, ver=0))               # sent 1, gen 0, NOT verified, equal bar
    add(row("early", "ETH", "a3", sent=2.0, gen=2.999, bar=OTHER))           # sent 2, gen 2, verified, not equal
    add(row("early", "ETH", "a4", sent=11.999, gen=7.5))                     # sent 11, gen 7
    add(row("early", "ETH", "a5", sent=12.0, gen=8.0))                       # sent 12+, gen 8+
    add(row("early", "ETH", "a6", sent=40, gen=""))                          # sent 12+, gen unknown
    add(row("early", "BTC", "a7", sent=1.0, gen=0.4, bar=OTHER))             # BTC apart, not equal
    add(row("early", "SOL", "a8", sent=3.2, gen=3.0, bar=None, n="0"), refbar=None)  # no trades in both: equal
    add(row("early", "XRP", "a9", sent=1.5, gen=1.0), ref_ver=0)             # reference unverified: left out
    rows.append(row("early", "ADA", "a10", sent=1.5, gen=1.0))               # no reference row at all: left out
    add(row("standard", "ETH", "a11", sent=6.0, gen=3.0))                    # standard, sent 6
    add(row("standard", "BTC", "a12", sent=6.5, gen=3.0))
    add(row("early", "ETH", "a13", sent="", gen=1.0, ver=0, bar=None), refbar=BAR)  # empty sent_s, no bar vs bar: not equal
    return rows


# Run B: one row each in a few cells, for the totals.
def run_b():
    rows = []
    for coin, m, kw in (("ETH", "b1", dict(sent=1.2, gen=0.1)), ("ETH", "b2", dict(sent=2.2, gen=0.1, bar=OTHER)),
                        ("BTC", "b3", dict(sent=1.1, gen=0.2))):
        rows += [row("early", coin, m, **kw), ref(coin, m)]
    rows += [row("standard", "ETH", "b4", sent=6.1, gen=2.5), ref("ETH", "b4")]
    return rows


# Table 4. Each case: ETH, own minute, early + standard + reference.
def run_t4():
    rows = []

    def case(m, early, std, refbar=BAR):
        for r in (early, std):
            if r is not None:
                rows.append(r)
        rows.append(ref(early["coin"], m, refbar))
    case("t1", row("early", "ETH", "t1", sent=2), row("standard", "ETH", "t1", sent=7))                    # fresh, fresh, same
    case("t2", row("early", "ETH", "t2", sent=2, bar=OTHER), row("standard", "ETH", "t2", sent=7, age=4))  # not equal, Age 4, different
    case("t3", row("early", "ETH", "t3", sent=2), row("standard", "ETH", "t3", sent=7, age=4))             # equal, Age 4, same
    case("t4", row("early", "ETH", "t4", sent=2), row("standard", "ETH", "t4", sent=7, age=4, bar=(10, 12, 9, 11, 5.5)))  # volume differs
    case("t5", row("early", "ETH", "t5", sent=2, age=2), row("standard", "ETH", "t5", sent=7))             # early has Age: out
    case("t6", row("early", "ETH", "t6", sent=2), None)                                                     # no standard row: out
    case("t7", row("early", "ETH", "t7", sent=2, bar=OTHER), row("standard", "ETH", "t7", sent=7))          # not equal, fresh, different
    case("t8", row("early", "BTC", "t8", sent=1), row("standard", "BTC", "t8", sent=6, age=7))              # BTC equal, Age 5+, same
    case("t9", row("early", "ETH", "t9", sent=2), row("standard", "ETH", "t9", sent=7, n="4"))              # n differs only: different
    return rows


def main():
    # labels and edges
    check("sent_s: 1.0 -> 1, 1.999 -> 1, 2.0 -> 2, 11.999 -> 11, 12.0 -> 12+, 40 -> 12+, empty -> unknown, -0.5 -> below 0",
          [ex.sent_label(x) for x in ("1.0", "1.999", "2.0", "11.999", "12.0", "40", "", "-0.5")]
          == ["1", "1", "2", "11", "12+", "12+", "unknown", "below 0"])
    check("gen_s: -0.5 and -1 -> before, 0 -> 0, 0.999 -> 0, 7.5 -> 7, 8.0 -> 8+, 30 -> 8+, empty -> unknown",
          [ex.gen_label(x) for x in ("-0.5", "-1", "0", "0.999", "7.5", "8.0", "30", "")]
          == ["before the minute's end"] * 2 + ["0", "0", "7", "8+", "8+", "unknown"])
    check("age: empty -> fresh, 0..4 as is, 5 and 9 -> 5+",
          [ex.age_label(x) for x in ("", "0", "1", "4", "5", "9")] == ["fresh", "0", "1", "4", "5+", "5+"])

    # equality on all four prices, as numbers; no bar in both
    b = row("early", "ETH", "x")
    check("equal: identical bars", ex.bars_equal(b, row("early", "ETH", "x")))
    for i, k in enumerate(("open", "high", "low", "close")):
        o = row("early", "ETH", "x")
        o[k] = repr(float(o[k]) + 0.01)
        check(f"not equal when only {k} differs", not ex.bars_equal(o, b))
    o = row("early", "ETH", "x")
    o["open"] = "10.000"
    check("equal compares numbers (10.000 vs 10.0)", ex.bars_equal(o, b))
    check("equal: volume is not compared", ex.bars_equal(row("early", "ETH", "x", bar=(10, 12, 9, 11, 99.0)), b))
    check("no bar in both is equal, a bar against none is not",
          ex.bars_equal(row("early", "ETH", "x", bar=None), row("early", "ETH", "x", bar=None))
          and not ex.bars_equal(row("early", "ETH", "x", bar=None), b))

    tmp = tempfile.mkdtemp()
    try:
        a, bd, t = (os.path.join(tmp, n) for n in ("runA", "runB", "runT"))
        write(a, run_a())
        write(bd, run_b())
        write(t, run_t4())
        out = os.path.join(tmp, "out")
        ex.explore([a, bd], out)
        rows = read_csv(os.path.join(out, "explore.csv"))
        R = "all runs together"

        # reference definition
        used = ex.used_rows("runA", ex.read_calls(a))
        mins = {r["minute"] for _, r, _ in used}
        check("unverified reference gives no reference; a missing one too: a9 and a10 are left out",
              "a9" not in mins and "a10" not in mins, sorted(mins))
        check("13 rows of run A, two left out, 11 used (a1..a8, a11, a12, a13)", len(used) == 11, len(used))

        # table 1, run A alone, ETH-like "other" group
        A = "run runA"
        t1 = lambda p, g, k: counts(get(rows, A, 1, p, g, k))  # noqa: E731
        check("sent 1, early other: a1 + a2 -> rows 2, verified 1, equal all 2, equal verified 1", t1("early", "other", "1") == (2, 1, 2, 1), t1("early", "other", "1"))
        check("sent 2, early other: a3 not equal -> (1, 1, 0, 0)", t1("early", "other", "2") == (1, 1, 0, 0), t1("early", "other", "2"))
        check("sent 3, early other: a8 no trades in both -> (1, 1, 1, 1)", t1("early", "other", "3") == (1, 1, 1, 1))
        check("sent 11 holds 11.999", t1("early", "other", "11") == (1, 1, 1, 1))
        check("sent 12+ holds 12.0 and 40: (2, 2, 2, 2)", t1("early", "other", "12+") == (2, 2, 2, 2))
        check("empty sent_s is its own line: a13 no bar vs bar -> (1, 0, 0, 0)", t1("early", "other", "unknown") == (1, 0, 0, 0), t1("early", "other", "unknown"))
        check("BTC apart: early BTC sent 1 -> (1, 1, 0, 0), and not in the other group", t1("early", "BTC", "1") == (1, 1, 0, 0))
        check("standard: other sent 6 -> (1, 1, 1, 1); BTC sent 6 -> (1, 1, 1, 1)",
              t1("standard", "other", "6") == (1, 1, 1, 1) and t1("standard", "BTC", "6") == (1, 1, 1, 1))
        check("a value of 6.5 is second 6, not 7", t1("standard", "BTC", "7") == (0, 0, 0, 0))

        # table 2
        t2 = lambda p, g, k: counts(get(rows, A, 2, p, g, k))  # noqa: E731
        check("gen below zero: one line 'before the minute's end' (a1)", t2("early", "other", "before the minute's end") == (1, 1, 1, 1))
        check("gen 0.0 -> second 0 (a2, unverified, equal bar): (1, 0, 1, 0)", t2("early", "other", "0") == (1, 0, 1, 0), t2("early", "other", "0"))
        check("gen 2.999 -> second 2 (a3)", t2("early", "other", "2") == (1, 1, 0, 0))
        check("gen 7.5 -> second 7 (a4)", t2("early", "other", "7") == (1, 1, 1, 1))
        check("gen 8.0 -> 8+ (a5)", t2("early", "other", "8+") == (1, 1, 1, 1))
        check("empty gen_s -> unknown (a6)", t2("early", "other", "unknown") == (1, 1, 1, 1))
        check("early BTC gen 0.4 -> second 0, apart", t2("early", "BTC", "0") == (1, 1, 0, 0))

        # table 3
        t3 = {(r["pass"], r["group"]): r for r in rows if r["runs"] == "run runB" and r["table"] == "3"}
        check("table 3 rows exist for each pass and group, all fresh in run B",
              len(t3) == 4 and t3[("early", "other")]["age_fresh"] == "2" and t3[("early", "BTC")]["age_fresh"] == "1")

        # totals add up
        ok = True
        for tno in (1, 2):
            for p in ex.PASSES:
                for g in ex.GROUPS:
                    for r in rows:
                        if r["runs"] == R and r["table"] == str(tno) and r["pass"] == p and r["group"] == g:
                            for f in ("rows", "verified", "equal_all", "equal_verified"):
                                s = sum(int(x[f]) for x in rows if x["runs"] in ("run runA", "run runB") and x["table"] == str(tno)
                                        and x["pass"] == p and x["group"] == g and x["key"] == r["key"])
                                if s != int(r[f]):
                                    ok = False
        check("per-run counts add up to the all-runs counts (tables 1 and 2, every line)", ok)
        tot = sum(int(r["rows"]) for r in rows if r["runs"] == R and r["table"] == "1")
        check("all rows of table 1 sum to the used rows: 11 + 4 = 15", tot == 15, tot)
        check("all runs, early other, sent 1: run A 2 + run B 1 = 3", counts(get(rows, R, 1, "early", "other", "1"))[0] == 3)

        # table 4
        ex.explore([t], os.path.join(tmp, "out4"))
        rows4 = read_csv(os.path.join(tmp, "out4", "explore.csv"))
        t4 = ex.tally_after_fresh(ex.used_rows("runT", ex.read_calls(t)))
        cell = lambda g, eq, age, same: t4.get((g, eq, age, same), [0, 0])  # noqa: E731
        check("fresh then fresh, same answer (equal early): 1 case, std equal to reference", cell("other", True, "fresh", True) == [1, 1])
        check("fresh not equal, then Age 4 with a different answer: 1 case, std equal to reference", cell("other", False, "4", False) == [1, 1])
        check("fresh equal, then Age 4 with the same answer: 1 case", cell("other", True, "4", True) == [1, 1])
        check("fresh equal, then Age 4 with another volume: different answer, 1 case, bar still equal", cell("other", True, "4", False) == [1, 1])
        check("n differing alone makes a different answer (t9, fresh): 1 case", cell("other", True, "fresh", False) == [1, 1])
        check("fresh not equal, then fresh, different answer: 1 case", cell("other", False, "fresh", False) == [1, 1])
        check("an early row with an Age header (t5) is left out of table 4, and so is a case with no standard row (t6)",
              sum(v[0] for k, v in t4.items() if k[0] == "other") == 6 and sum(v[0] for k, v in t4.items() if k[0] == "all") == 7,
              {k: v for k, v in t4.items()})
        check("BTC apart in table 4: equal, Age 5+, same answer", cell("BTC", True, "5+", True) == [1, 1] and cell("other", True, "5+", True) == [0, 0])
        check("totals, early not equal (other): 2 cases, 1 fresh, 1 with Age, 0 the same answer",
              ex.table4_totals(t4, "other", False) == (2, 1, 1, 0), ex.table4_totals(t4, "other", False))
        check("totals, early equal (other): 4 cases, 2 fresh, 2 with Age, 1 the same answer",
              ex.table4_totals(t4, "other", True) == (4, 2, 2, 1), ex.table4_totals(t4, "other", True))
        check("table 4 'all coins' = other + BTC", ex.table4_totals(t4, "all", True) == (5, 2, 3, 2), ex.table4_totals(t4, "all", True))
        csv4 = [r for r in rows4 if r["table"] == "4" and r["runs"] == "all runs together" and r["group"] == "all coins"]
        check("table 4 rows in explore.csv carry the same counts", any(r["key"] == "early equal|std age 4|same" and r["rows"] == "1" for r in csv4))

        # the files
        with open(os.path.join(out, "explore.md")) as f:
            md = f.read()
        with open(os.path.join(out, "explore.csv")) as f:
            cs = f.read()
        check("explore.md heads with the exploratory line", ex.HEADNOTE in md.splitlines()[2], md.splitlines()[:3])
        check("explore.md closing paragraph: sentence pattern for second 1 (early, other, both runs: 3 of 3)",
              "Of the answers sent in second 1, 2 of 3 were equal to the list 95 s later" in md
              or "Of the answers sent in second 1, 3 of 3 were equal to the list 95 s later" in md, md[-900:])
        check("closing paragraph, second 2: a3 not equal, b2 not equal -> 0 of 2",
              "Of the answers sent in second 2, 0 of 2 were equal to the list 95 s later" in md)
        check("closing paragraph names BTC and the standard pass",
              "For BTC at its early place, of the answers sent (all seconds), 1 of 2" in md and "standard pass as a whole" in md, md[-500:])
        check("shares print as k / n = xx.xx%", "1 / 2 = 50.00%" in md)
        check("no at-sign in the outputs", chr(64) not in md and chr(64) not in cs)
        check("explore.md has the all-runs section and one per run", "## all runs together" in md and "## run runA" in md and "## run runB" in md)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{COUNT[0]} checks, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
