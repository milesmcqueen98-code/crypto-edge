"""Offline tests of rule C2 and pass C2x18 (build.py) and of c2_rule.py, on made-up records and counts and on a
synthetic copy of Part 1's published table. Run: python scripts/owner/bar_source/test_c2.py (prints ok / FAIL per
check, ends with "test_c2: N checks passed"). The numbers of the synthetic run are a test of the script, not a result."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)

import numpy as np          # noqa: E402
import pandas as pd         # noqa: E402

import build                # noqa: E402
import fetch_and_compute as fac   # noqa: E402
import test_bar_source as tbs     # noqa: E402  (its fixtures: small_record, synth_candles, m)
import c2_rule as c2        # noqa: E402

FAILS = []
COUNT = [0]
MIN = pd.Timedelta(minutes=1)
m = tbs.m
PART1 = os.path.join(ROOT, "reports", "owner", "bar_source")


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


# ------------------------------------------------------------------------------------------------ build.py
def test_passes():
    P = build.passes()
    coins18 = set(["BTC"] + build.TWELVE + build.REPORTED + ["ETH", "SOL", "XRP"])
    check("passes()['C2x18']: 18 coins, each on rule C2", set(P["C2x18"]) == coins18 and len(P["C2x18"]) == 18
          and all(v == "C2" for v in P["C2x18"].values()), P["C2x18"])
    check("canonical_pass(.., 'C2x18') = 'C2x18' for a twelve coin, LTC, ZEC and ETH",
          all(build.canonical_pass(c, "C2x18") == "C2x18" for c in ("DOGE", "LTC", "ZEC", "ETH")))
    check("existing passes untouched: R A B C LA LC C18 and the new one (eight)",
          sorted(P) == sorted(["R", "A", "B", "C", "LA", "LC", "C18", "C2x18"]) and all(v == "C" for v in P["C18"].values()))
    check("canonical_pass unchanged for the old ways", build.canonical_pass("LTC", "B") == "A"
          and build.canonical_pass("LTC", "C") == "LC" and build.canonical_pass("DOGE", "C18") == "C18")


def small_state():
    tb, cd, cf, final = tbs.small_record()
    tbar, first, answers = build.split_record(tb, cd, cf, m(1), m(5))
    dec = pd.date_range(m(1), m(5), freq="min")
    nf = build.newest_frames("DOGE", dec, tbar, first, answers)
    oldB, _ = build.old_b_frame("DOGE", final, m(0), m(4), tbar)
    fac._G["candles"] = {"DOGE": final}
    build._W["frames"] = {"DOGE": dict(oldB=oldB, newA=nf["A"][0], srcA=nf["A"][1], newT=nf["T"][0], srcT=nf["T"][1])}
    build._W["ways"] = {"C": {"DOGE": "C"}, "C2x18": {"DOGE": "C2"}}
    return tbar, dec, nf, answers


def test_table():
    tbar, dec, nf, answers = small_state()
    tab = lambda p, t: build.table_for(p, t)["DOGE"]  # noqa: E731
    opens = lambda p, t: list(tab(p, t).open)  # noqa: E731
    check("C2 at t=m1: t-2 is before the record (final candle 99), row t-1 the trades bar m0",
          opens("C2x18", m(1)) == [98, 99, 200], opens("C2x18", m(1)))
    check("C2 at t=m2: t-2 = m0 trades bar (200, C has the final 100); t-1 = m1 verified empty: no row",
          opens("C2x18", m(2)) == [98, 99, 200] and opens("C", m(2)) == [98, 99, 100], opens("C2x18", m(2)))
    check("C2 at t=m3: t-2 = m1 verified empty: no row; t-1 = m2 the fall-back first-seen candle",
          opens("C2x18", m(3)) == [98, 99, 100, 302], opens("C2x18", m(3)))
    check("C2 at t=m4: t-2 = m2 not verified: the final candle 102; t-1 = m3 no answer: no row",
          opens("C2x18", m(4)) == [98, 99, 100, 101, 102], opens("C2x18", m(4)))
    check("C2 at t=m5: t-2 = m3 absent: the final candle 103; t-1 = m4 the trades bar",
          opens("C2x18", m(5)) == [98, 99, 100, 101, 102, 103, 204], opens("C2x18", m(5)))
    check("C2 at t=m6: t-2 = m4 trades bar; rows through t-3 final; t-1 = m5 has no trades row",
          opens("C2x18", m(6)) == [98, 99, 100, 101, 102, 103, 204], opens("C2x18", m(6)))
    ok = True
    for k in range(1, 7):
        a, c = tab("C2x18", m(k)), tab("C", m(k))
        ok &= (m(k - 1) in a.index) == (m(k - 1) in c.index)
        if m(k - 1) in a.index:
            ok &= a.loc[m(k - 1)].equals(c.loc[m(k - 1)])
        ok &= a.index.is_monotonic_increasing and a.index.is_unique
        fin = fac._G["candles"]["DOGE"]
        ok &= list(a.loc[:m(k - 3)].index) == list(fin.loc[:m(k - 3)].index) \
            and list(a.loc[:m(k - 3)].open) == list(fin.loc[:m(k - 3)].open)       # rows through t-3: the final candles
    check("C2 row t-1 is rule C's at the same decision; rows through t-3 are the final candles; index sorted, unique",
          bool(ok))
    kinds = build.second_row_kinds("DOGE", dec, tbar, m(0))
    check("row t-2 kinds at t=m1..m5: before_record, trades, empty, fallback (not verified), fallback (absent)",
          list(kinds.values) == ["before_record", "trades", "empty", "fallback", "fallback"]
          and list(kinds.index) == [m(k) for k in range(-1, 4)], list(kinds.values))
    src = build.sources_table(dec, ["DOGE"], build._W["frames"], {"C2x18": {"DOGE": "C2"}}, answers)
    check("sources_table gives C2 the source of row t-1 as rules B and C do (srcT)",
          list(src.src) == ["trades", "empty", "fb_first", "fb_no_answer", "trades"] and set(src.way) == {"C2"}
          and list(src.inputs_ok) == [True, True, True, False, True], list(src.src))


def test_engine():
    candles, coins = tbs.synth_candles()
    tmp = tempfile.mkdtemp(prefix="bs_c2_test_")
    build.init_worker(candles, coins, tmp, {}, {"R": {}})
    t = m(8)
    ref = pd.DataFrame(fac.compute_at(t))
    frames = {c: dict(oldB=df, newA=df.loc[m(-5):], newT=df.loc[m(-5):]) for c, df in candles.items()}
    ways = {"R": {}, "C2x18": build.passes()["C2x18"]}
    build.init_worker(candles, coins, tmp, frames, ways)
    got = pd.DataFrame(build.work(("C2x18", t))).drop(columns="pass")
    check("pass C2x18 with trades rows equal to the final candles = pass R (every coin, every column)",
          ref.equals(got) and len(ref) == len(coins), got.compare(ref) if len(got) == len(ref) else len(got))
    check("fac.table_at restored after the pass", fac.table_at is build._TABLE_AT)
    f2 = dict(frames)
    nd = candles["DOGE"].copy()
    nd.loc[t - 2 * MIN, ["close", "low"]] *= 0.9
    f2["DOGE"] = dict(oldB=nd, newA=frames["DOGE"]["newA"], newT=frames["DOGE"]["newT"])
    build.init_worker(candles, coins, tmp, f2, ways)
    got2 = pd.DataFrame(build.work(("C2x18", t))).drop(columns="pass")
    check("a change in DOGE's row t-2 only (rule B's older rows) moves DOGE's output: row t-2 is read from oldB",
          not got2.equals(ref))
    f3 = dict(frames)
    nd = candles["DOGE"].copy()
    nd.loc[t - 3 * MIN, ["close", "low"]] *= 0.9
    f3["DOGE"] = dict(oldB=nd, newA=frames["DOGE"]["newA"], newT=frames["DOGE"]["newT"])
    build.init_worker(candles, coins, tmp, f3, ways)
    got3 = pd.DataFrame(build.work(("C2x18", t))).drop(columns="pass")
    check("a change in oldB at t-3 changes nothing: rows through t-3 are the final candles", got3.equals(ref))


# ------------------------------------------------------------------------------------------------ c2_rule
def cnt(num=0, den=0, miss=0, score_n=0, lv=0, lv_n=0):
    return dict(num=num, den=den, miss=miss, score_n=score_n, level_gt5=lv, level_n=lv_n)


def test_clauses():
    a = cnt(num=10, den=1000, miss=20, score_n=1000)
    c18 = cnt(lv=10, lv_n=1000)
    same = cnt(num=10, den=1000, miss=20, score_n=1000, lv=10, lv_n=1000)
    cl, v = c2.clauses(a, c18, same)
    check("equal shares meet clauses 1 and 2 (and 3), the verdict is true",
          cl["1_arming"]["met"] and cl["2_score"]["met"] and cl["3_level"]["met"] and v is True, cl)
    on = dict(same, level_gt5=15)
    cl, v = c2.clauses(a, c18, on)
    check("clause 3 exactly 0.5 points above C18's share (15 of 1000 against 10 of 1000) is met", cl["3_level"]["met"] and v)
    cl, v = c2.clauses(a, c18, dict(same, level_gt5=16))
    check("clause 3 one minute more above is not met, verdict false", cl["3_level"]["met"] is False and v is False)
    big = dict(same, level_n=2000, level_gt5=30)
    cl, _ = c2.clauses(a, c18, big)
    check("clause 3 is on shares, not counts (30 of 2000 = 1.5% = 10 of 1000 + 0.5 points: met)", cl["3_level"]["met"])
    cl, v = c2.clauses(a, c18, dict(same, num=11))
    check("clause 1 one minute higher on equal denominators is not met; clauses 2 and 3 still met; verdict false",
          not cl["1_arming"]["met"] and cl["2_score"]["met"] and cl["3_level"]["met"] and v is False)
    cl, v = c2.clauses(a, c18, dict(same, miss=21))
    check("clause 2 one miss more is not met; verdict false", not cl["2_score"]["met"] and v is False)
    cl, v = c2.clauses(a, c18, dict(same, num=5, den=1000))
    check("a lower share meets clause 1", cl["1_arming"]["met"])
    for name, a2, c182, new, which in (
            ("new arming den 0", a, c18, dict(same, den=0, num=0), "1_arming"),
            ("pass A arming den 0", dict(a, den=0, num=0), c18, same, "1_arming"),
            ("new score_n 0", a, c18, dict(same, score_n=0, miss=0), "2_score"),
            ("pass A score_n 0", dict(a, score_n=0, miss=0), c18, same, "2_score"),
            ("new level_n 0", a, c18, dict(same, level_n=0, level_gt5=0), "3_level"),
            ("C18 level_n 0", a, dict(c18, level_n=0, level_gt5=0), same, "3_level")):
        cl, v = c2.clauses(a2, c182, new)
        check(f"a zero denominator is not met ({name}); verdict false", cl[which]["met"] is False and v is False)
    cl, v = c2.clauses(cnt(), cnt(), cnt())
    check("all counts zero: no clause met, verdict false", not any(x["met"] for x in cl.values()) and v is False)


def test_pass_rows():
    rows = []
    for p, sc in (("A", 40.0), ("LA", 50.0), ("C18", 60.0)):
        for coin in ("LTC", "DOGE"):
            rows.append(dict(ts=m(0), coin=coin, **{"pass": p}, way="x", score=sc, level=1.0, sig=1.0, valid=True,
                             src="trades", inputs_ok=True, answer_old=False, res_score=40.0, res_level=1.0,
                             res_sig=1.0, res_valid=True))
    rows.append(dict(rows[0], ts=m(1), inputs_ok=False))
    T = pd.DataFrame(rows)
    g = c2.pass_rows(T, ["LTC", "DOGE"], "A")
    check("by-pass rows: all17 under pass A takes LTC's rows from pass A, not LA; inputs_ok False left out",
          len(g) == 2 and set(g["pass"]) == {"A"} and set(g.score) == {40.0}, g)
    r = c2.measures(T, ["LTC", "DOGE"], 30.0, {}, m(0), passes=("A", "LA"))
    pick = lambda coin, p: next(x for x in r if x["coin"] == coin and x["pass"] == p and x["day"] == "all")  # noqa: E731
    check("measures: all17 under pass A counts LTC's pass A rows (2 rows, no miss); under LA the miss count is 2",
          pick("all17", "A")["minutes"] == 2 and pick("all17", "A")["miss"] == 0 and pick("all17", "LA")["miss"] == 2
          and pick("LTC", "A")["minutes"] == 1)


def run_script(d, part1, out):
    return subprocess.run([sys.executable, os.path.join(HERE, "c2_rule.py"), "--dir", d, "--part1", part1,
                           "--out", out], capture_output=True, text=True)


def test_end_to_end():
    tmp = tempfile.mkdtemp(prefix="c2_rule_test_")       # outside the repository
    try:
        T = pd.read_parquet(os.path.join(PART1, "minutes.parquet"))
        cp = T[T["pass"] == "C18"].copy()
        cp["pass"], cp["way"] = "C2x18", "C2"
        d, out = os.path.join(tmp, "run"), os.path.join(tmp, "out")
        os.makedirs(d)
        pd.concat([T, cp]).to_parquet(os.path.join(d, "minutes.parquet"), index=False)
        run = json.load(open(os.path.join(PART1, "run.json")))
        run["second_row_counts"] = {"DOGE": dict(trades=1, empty=2, fallback=3, before_record=4)}
        json.dump(run, open(os.path.join(d, "run.json"), "w"))
        r = run_script(d, PART1, out)
        check("end to end on a synthetic copy: exit code 0", r.returncode == 0, r.stderr[-500:])
        J = json.load(open(os.path.join(out, "c2_counts.json")))
        rc = J["row_check"]
        check("end to end: reproduced true, no differences", J["reproduced"] is True and J["differences"] == [])
        check("end to end: row check over Part 1's six passes, 0 differing rows, none only in one table",
              rc["rows_compared"] == len(T) and rc["rows_differing"] == 0 and rc["rows_only_new"] == 0
              and rc["rows_only_part1"] == 0 and all(v["differ"] == 0 for v in rc["columns"].values()), rc)
        a17 = J["counts"]["all17"]
        check("end to end: with the copy, C2x18's counts equal C18's in every group and day",
              all(J["counts"][g]["C2x18"] == J["counts"][g]["C18"] for g in J["counts"]))
        p1 = json.load(open(os.path.join(PART1, "counts.json")))["counts"]
        coins = run["coins"]
        sums = {k: sum(p1[c]["C18"]["all"][k] for c in coins) for k in ("num", "den", "miss", "score_n", "level_gt5", "level_n")}
        check("all17 under C18 = the sum of Part 1's per-coin counts for way C18 (17 coins)",
              all(a17["C18"]["all"][k] == v for k, v in sums.items()), (sums, a17["C18"]["all"]))
        k3 = J["clauses"]["3_level"]
        check("end to end: clause 3 equal shares met; counts and shares written; verdict equals the three clauses",
              k3["met"] and k3["c2_share"] == k3["bar_share"]
              and J["verdict"] == all(v["met"] for v in J["clauses"].values()) and J["second_row_counts"] == run["second_row_counts"])
        files = sorted(os.listdir(out))
        check("end to end: the three output files", files == ["c2_counts.json", "c2_per_coin.csv", "c2_summary.md"], files)
        md = open(os.path.join(out, "c2_summary.md")).read()
        check("summary has the sections and the verdict sentence",
              "## The 17 traded coins together" in md and "## Per coin, whole period" in md
              and "Under the plan's rule the candle requests move behind the bids: " in md
              and "Where row t-2 came from" in md and r.stdout.strip() == md.strip())
        csv = pd.read_csv(os.path.join(out, "c2_per_coin.csv"))
        check("per_coin.csv: all17 and each of the 17 coins, five passes, days all/1/2/3",
              sorted(csv.coin.unique()) == sorted(["all17"] + coins) and sorted(csv["pass"].unique()) == sorted(c2.PASSES)
              and set(csv.day.astype(str)) == {"all", "1", "2", "3"})

        # one count of Part 1 changed: not reproduced
        p1dir = os.path.join(tmp, "part1_changed")
        os.makedirs(p1dir)
        os.symlink(os.path.join(PART1, "minutes.parquet"), os.path.join(p1dir, "minutes.parquet"))
        j1 = json.load(open(os.path.join(PART1, "counts.json")))
        j1["counts"]["DOGE"]["A"]["all"]["num"] += 1
        json.dump(j1, open(os.path.join(p1dir, "counts.json"), "w"))
        out2 = os.path.join(tmp, "out2")
        r = run_script(d, p1dir, out2)
        J = json.load(open(os.path.join(out2, "c2_counts.json")))
        check("one count changed: exit code 4, line NOT READ printed", r.returncode == 4 and "NOT READ:" in r.stdout, r.returncode)
        check("one count changed: reproduced false, one difference listed, verdict null, no counts or clauses",
              J["reproduced"] is False and J["verdict"] is None and len(J["differences"]) == 1
              and "DOGE" in J["differences"][0] and "counts" not in J and "clauses" not in J, J)
        text = r.stdout + open(os.path.join(out2, "c2_summary.md")).read() + open(os.path.join(out2, "c2_counts.json")).read()
        check("one count changed: nothing of the new pass is printed or written, no per-coin file",
              "C2x18" not in text and "all17" not in text and not os.path.exists(os.path.join(out2, "c2_per_coin.csv")))
        # row check on floats: printed with %.10g
        isA = T["pass"] == "A"
        base = T.copy()
        base.loc[isA, "level"] = 1.5                       # a value far from any rounding boundary of %.10g
        small = base.copy()
        small.loc[isA, "level"] = 1.5 * (1 + 1e-12)
        big = T.copy()
        big.loc[isA, "level"] = big.loc[isA, "level"] * (1 + 1e-6)
        check("row check: a relative change of 1e-12 is below %.10g (0 rows differ)",
              c2.row_check(small, base)["rows_differing"] == 0)
        rcb = c2.row_check(big, T)
        check("row check: a relative change of 1e-6 differs in every A row with a level, largest difference reported",
              rcb["columns"]["level"]["differ"] == int(T.loc[isA, "level"].notna().sum())
              and rcb["columns"]["level"]["max_abs_diff"] > 0, rcb["columns"]["level"])
        T4 = T.copy()
        T4.loc[T4.index[5], "src"] = "zzz"
        T4.loc[T4.index[6], "score"] = np.nan
        rc4 = c2.row_check(T4, T)
        check("row check: a changed text column and a number made NaN are each counted; NaN equals NaN elsewhere",
              rc4["columns"]["src"]["differ"] == 1 and rc4["columns"]["score"]["differ"] >= 1
              and rc4["rows_differing"] >= 2, rc4)
        T5 = T.iloc[1:]
        rc5 = c2.row_check(T5, T)
        check("row check: a row only in Part 1's table is counted", rc5["rows_only_part1"] == 1 and rc5["rows_only_new"] == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_diff_counts():
    d = c2.diff_counts({"a": {"x": 1, "y": 2}, "b": 3}, {"a": {"x": 1, "y": 5}, "c": 1})
    check("diff_counts lists changed and missing keys", sorted(p for p, _, _ in d) == ["/a/y", "/b", "/c"], d)


def main():
    test_passes()
    test_table()
    test_engine()
    test_clauses()
    test_pass_rows()
    test_diff_counts()
    test_end_to_end()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {FAILS}")
        sys.exit(1)
    print(f"test_c2: {COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
