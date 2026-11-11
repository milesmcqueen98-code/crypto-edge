"""Offline tests of the period parameters, the two-book read and item 7, on made-up logs and research tables.
Run: python scripts/owner/reconcile/test_two_books.py (prints ok / FAIL per check, ends with "all passed")."""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np          # noqa: E402
import pandas as pd         # noqa: E402

import common               # noqa: E402
import compare              # noqa: E402
import fetch_and_compute    # noqa: E402
import item7                # noqa: E402
import test_compare as tc   # noqa: E402
import two_books            # noqa: E402

FAILS = []
NAMES = {"A": "SOL", "B": "DOGE"}       # SOL is on the trades list, DOGE on the candle path
m, ev, T0, END = tc.m, tc.ev, tc.T0, tc.END


def check(name, ok, info=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


def renamed():
    E, R, late, ticks, thr = tc.make()
    for e in E:
        if "coin" in e:
            e["coin"] = NAMES[e["coin"]]
        if "ladder" in e:
            e["ladder"] = NAMES[e["ladder"][0]] + e["ladder"][1:]
    R = R.assign(coin=R.coin.map(NAMES))
    late = late.assign(coin=late.coin.map(NAMES))
    return E, R, late, {NAMES[k]: v for k, v in ticks.items()}, thr


def k_of(t):
    return int((pd.Timestamp(t) - T0) / pd.Timedelta(minutes=1))


def rn_set(o):
    return sorted((k_of(t), c) for t, c in zip(o["research_new"].ts, o["research_new"].coin))


def test_period():
    E, R, late, ticks, thr = renamed()
    full = compare.compute(E, R, late, ticks, thr, end=END)
    # an explicit period equal to the default gives the same tables
    same = compare.compute(E, R, late, ticks, thr, end=END, start=m(0))
    check("period = book's first event .. end reproduces the default run",
          full["arms"].equals(same["arms"]) and full["research_new"].equals(same["research_new"])
          and full["fills"].equals(same["fills"]) and full["m3"] == same["m3"] and full["live"] == same["live"])
    # every start: research new bids inside the period are the full run's, restricted (armed state carried over)
    bad = []
    for s in range(1, 60):
        o = compare.compute(E, R, late, ticks, thr, end=END, start=m(s))
        want = [x for x in rn_set(full) if x[0] >= s]
        if rn_set(o) != want:
            bad.append((s, rn_set(o), want))
        dec_full = common.live_minutes(E, END)[0]
        if list(common.live_minutes(E, END, m(s))[0]) != [t for t in dec_full if t >= m(s)]:
            bad.append((s, "decision minutes"))
    check("for every start 1..59: research new bids and decision minutes = the full run's inside the period",
          not bad, bad[:2])
    # start at 10: DOGE is armed at 9 (the previous decision minute) and at 10 -> not new at 10;
    # SOL filled at 7 (before the period) and is busy 8..20 -> not armed at 10..12 although its score is above
    o = compare.compute(E, R, late, ticks, thr, end=END, start=m(10))
    check("carry-over of the research armed state: DOGE not new at the period's first minute",
          (10, "DOGE") not in rn_set(o) and (9, "DOGE") not in rn_set(o), rn_set(o))
    check("carry-over of an open ladder: SOL busy at 10..12 (filled at 7, before the period)",
          not any(c == "SOL" and 10 <= k <= 20 for k, c in rn_set(o)) and rn_set(o)[0] == (30, "SOL"), rn_set(o))
    check("previous decision minute found (9) and the research needs it",
          common.prev_decision_minute(E, END, m(10)) == m(9))
    F = o["fills"]
    check("fills: the ladder that first filled before the period is not counted; DOGE dip at 15 is research only",
          F.group.tolist() == ["research_only"] and F.coin.tolist() == ["DOGE"], F[["group", "coin"]].values.tolist())
    check("bot arms before the period are left out (DOGE at 10 is the only one)",
          o["arms"].coin.tolist() == ["DOGE"] and o["m3"]["bot_new_bids"] == 1)
    # edge effect, stated in compare.py: the research bid at 9 lies outside the period, so DOGE's arm at 10 is unmatched
    check("matching does not look across the period's start (stated edge effect)",
          not bool(o["arms"].research_new_pm1.iloc[0]))
    # without the previous minute in the research table: refuse
    try:
        compare.compute(E, R[R.ts != m(9)], late, ticks, thr, end=END, start=m(10))
        check("missing research row at the previous decision minute raises", False)
    except ValueError:
        check("missing research row at the previous decision minute raises", True)
    # a start right after a logged gap needs no previous minute (the bot cancelled its bids)
    check("no previous minute needed after a logged gap", common.prev_decision_minute(E, END, m(38)) is None)
    # period end before the log ends: arms, fills and cash_short after it are left out; open ladders still known
    o2 = compare.compute(E, R, late, ticks, thr, end=m(30), start=m(6))
    check("period end: decision minutes 6..30, and the research bid at 30 is its last",
          o2["live"]["decision_minutes"] == 25 and rn_set(o2)[-1] == (30, "SOL"), (o2["live"], rn_set(o2)))
    check("busy_intervals uses the period end for a ladder still open",
          common.busy_intervals([ev(3, "fill_entry", coin="X", ladder="X-1", rung=4)], m(30))["X"][0][1] == m(40))


def write_book(d, E, ticks):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "events.jsonl"), "w") as f:
        for e in E:
            f.write(json.dumps({k: v for k, v in e.items() if k != "t"}) + "\n")
    json.dump({"specs": {c: {"tick": t} for c, t in ticks.items()}}, open(os.path.join(d, "state.json"), "w"))


def tb_events(E):
    """The third book: a different gap ((27, 30] instead of (35, 40]), a stale_input at 41, a heartbeat with skip_old,
    and no cash_short."""
    out = [e for e in E if e["kind"] not in ("catch_up", "cash_short", "heartbeat")]
    out += [ev(30, "catch_up", gap_minutes=3, open=[]), ev(41, "stale_input", coin="BTC", age_min=1),
            ev(30, "heartbeat", counts={"skip_old": 4}), ev(60, "heartbeat", counts={"skip_old": 3, "arm": 1})]
    out.sort(key=lambda x: x["t"])
    return out


def test_two_books():
    E, R, late, ticks, thr = renamed()
    Etb = tb_events(E)
    with tempfile.TemporaryDirectory() as tmp:
        write_book(os.path.join(tmp, "paper_spot"), E, ticks)
        write_book(os.path.join(tmp, "paper_spot_tb"), Etb, ticks)
        rd = os.path.join(tmp, "research")
        os.makedirs(rd)
        R.to_csv(os.path.join(rd, "research_minutes.csv.gz"), index=False)
        both = pd.concat([late.assign(book="paper_spot"), late.assign(book="paper_spot_tb")])
        both.to_csv(os.path.join(rd, "late_btc_at_arms.csv"), index=False)
        out = os.path.join(tmp, "out")
        r = two_books.run(rd, os.path.join(tmp, "paper_spot"), os.path.join(tmp, "paper_spot_tb"), m(0), END, out)
        dm = common.live_minutes(E, END)[0]
        dt = common.live_minutes(Etb, END)[0]
        check("the two books have different decision minutes", set(dm) != set(dt))
        check("common minutes = intersection of the two books' decision minutes",
              list(r["common"]) == sorted(set(dm) & set(dt)) and m(28) not in r["common"] and m(38) not in r["common"])
        files = sorted(os.listdir(os.path.join(out, "main")))
        check("main/ and tb/ hold compare.py's file names",
              {"m1_level_error.csv", "m3_bids.csv", "m4_fills.csv", "summary.json"} <= set(files)
              and files == sorted(os.listdir(os.path.join(out, "tb"))), files)
        for f in ("side_by_side.csv", "item7.json", "item7.md", "item7_bids.csv", "common_minutes.csv",
                  "two_books.json"):
            check(f"wrote {f}", os.path.exists(os.path.join(out, f)))
        S = pd.read_csv(os.path.join(out, "side_by_side.csv"))

        def val(measure, stat, group, book):
            x = S[(S.measure == measure) & (S.statistic == stat) & (S.group == group) & (S.book == book)]
            return float(x.value.iloc[0]) if len(x) else np.nan
        # filtering: research new bids of each book (own sequence) in the common minutes
        for b in ("main", "tb"):
            rn = r["results"][b]["research_new"]
            want = int(pd.to_datetime(rn.ts).isin(r["common"]).sum())
            check(f"{b}: research new bids on common minutes = own-sequence rows filtered",
                  val("m3_bids", "research_new_bids", "all", b) == want, (val("m3_bids", "research_new_bids", "all", b), want))
        # main: research SOL new at 41 (after its own gap) and 50; tb: SOL new at 31 (after its gap), 41 (stale)
        rm, rt = rn_set(r["results"]["main"]), rn_set(r["results"]["tb"])
        check("each book's 'new' follows its own gaps", (41, "SOL") in rm and (31, "SOL") in rt and (30, "SOL") in rm,
              (rm, rt))
        # group split
        check("group split: trades list holds SOL only, candle path DOGE only",
              val("m1_level_error", "n", "trades list", "main") == 1 and val("m1_level_error", "n", "candle path", "main") == 1
              and val("m1_level_error", "n", "all", "main") == 2
              and val("m3_bids", "research_new_bids", "trades list", "main")
              + val("m3_bids", "research_new_bids", "candle path", "main") == val("m3_bids", "research_new_bids", "all", "main"))
        check("group split: DOGE's level error (-51 bp) only in the candle path group",
              val("m1_level_error", "share_abs_gt5", "candle path", "main") == 1.0
              and val("m1_level_error", "share_abs_gt5", "trades list", "main") == 0.0)
        # stale_input listing (tb): SOL's research bid at 41 is listed apart and leaves only the share's denominator
        o = r["results"]["tb"]
        rn = o["research_new"].set_index(["ts", "coin"])
        check("stale_input: research new bid at the stale minute is flagged",
              bool(rn.loc[(m(41), "SOL"), "stale_input_t"]) and not bool(rn.loc[(m(31), "SOL"), "stale_input_t"]))
        m3 = o["m3"]
        nb = len(o["research_new"]) - int(o["research_new"].cash_short_pm1.astype(bool).sum()) - m3["research_stale_blocked"]
        check("stale_input: counted apart, kept in research_new_bids, out of share_research_in_bot's denominator",
              m3["research_stale_blocked"] == 1 and m3["research_new_bids"] == len(o["research_new"])
              and m3["research_new_bids_ex_blocked"] == nb
              and abs(m3["share_research_in_bot"] - o["research_new"][~o["research_new"].stale_input_t.astype(bool)]
                      .bot_arm_pm1.mean()) < 1e-12, m3)
        check("stale_input table and skip_old context",
              o["stale_minutes"].ts.tolist() == [m(41)] and o["stale"]["skip_old_total"] == 7
              and r["meta"]["stale"]["main"]["skip_old_total"] == 0, (o["stale"], o["stale_minutes"]))
        check("main book: stale columns present (zero) when run by two_books",
              r["results"]["main"]["m3"]["research_stale_blocked"] == 0)
        # main book alone through compare.compute default: no stale columns (the first reconciliation's shape)
        o0 = compare.compute(E, R, late, ticks, thr, end=END)
        check("no stale_input in the log: compare's default output has no stale columns",
              "stale_input_t" not in o0["research_new"] and "research_stale_blocked" not in o0["m3"] and "stale" not in o0)
        # late file with a book column: each book reads its own rows
        lt = compare.load_late(os.path.join(rd, "late_btc_at_arms.csv"), "paper_spot_tb")
        check("late_btc_at_arms with a book column: one book's rows, old columns", list(lt.columns) == list(late.columns)
              and len(lt) == len(late))
        # item 7 from the folder (item7.py's own path) equals the run's
        j = json.load(open(os.path.join(out, "item7.json")))
        B = pd.read_csv(os.path.join(out, "item7_bids.csv"))
        check("item7_bids.csv holds each book's bids in the common minutes",
              sorted(B.book.value_counts().to_dict().items()) == [("main", 2), ("tb", 2)])
        check("item 7 on the synthetic books waits (fewer than 200 bids)", j["overall"] == "WAIT", j["overall"])
        # a book with no bid at all
        Enone = [e for e in Etb if e["kind"] != "arm" and e["kind"] != "fill_entry"]
        write_book(os.path.join(tmp, "empty_tb"), Enone, ticks)
        r2 = two_books.run(rd, os.path.join(tmp, "paper_spot"), os.path.join(tmp, "empty_tb"), m(0), END,
                           os.path.join(tmp, "out2"))
        check("a book with no bids runs (item 7 waits, n = 0)",
              r2["item7"]["measures"]["a_level_gt5bp"]["tb_n"] == 0 and r2["item7"]["overall"] == "WAIT")


def test_fetch_helpers():
    E, R, late, ticks, thr = renamed()
    Etb = tb_events(E)
    evs = {"paper_spot": E, "paper_spot_tb": Etb}
    L = fetch_and_compute.live_set(evs, m(10), END)
    want = sorted(set(common.live_minutes_brief(E, END, m(10))) | set(common.live_minutes_brief(Etb, END, m(10)))
                  | {m(9)})
    check("research live set = union of the books' brief minutes in the period + previous decision minute",
          list(L) == want and m(9) in L and m(8) not in L)
    L0 = fetch_and_compute.live_set({"paper_spot": E}, None, END)
    check("default live set = the brief's set of the one book", list(L0) == list(common.live_minutes_brief(E, END)))
    ab = fetch_and_compute.arms_in_period(evs, {"SOL", "DOGE"}, m(6), END)
    check("arms in the period, per book", ab == {(m(10), "DOGE"): {"paper_spot", "paper_spot_tb"}}, ab)
    lt = pd.DataFrame([dict(ts=m(10), coin="DOGE", btc_lag=1, level=1.0, score=2.0, valid=True)])
    sp = fetch_and_compute.split_late(lt, {(m(10), "DOGE"): {"paper_spot_tb"}}, ["paper_spot", "paper_spot_tb"])
    check("late rows split per book", sp.book.tolist() == ["paper_spot_tb"] and list(sp.columns)[0] == "book")


def rows(k, n, kind):
    """n per-bid rows of which k count for measure (a) (kind 'a') or (b) (kind 'b')."""
    if kind == "a":
        return pd.DataFrame(dict(err_bp=[6.0] * k + [0.0] * (n - k), res_score=[40.0] * n, res_other_side=[False] * n))
    return pd.DataFrame(dict(err_bp=[0.0] * n, res_score=[20.0] * k + [40.0] * (n - k),
                             res_other_side=[True] * k + [False] * (n - k)))


def test_item7():
    v = item7.verdict
    check("item7: strictly lower passes", v(40, 400, 39, 400) == "PASS")
    check("item7: equal share fails (counts differ, shares equal)", v(40, 400, 20, 200) == "FAIL")
    check("item7: higher fails", v(10, 400, 41, 400) == "FAIL")
    check("item7: both below 5% passes even when the third book is higher", v(10, 400, 19, 400) == "PASS")
    check("item7: one at exactly 5.00% with the other higher fails",
          v(10, 200, 21, 400) == "FAIL" and v(16, 400, 20, 400) == "FAIL" and v(10, 200, 20, 400) == "FAIL")
    check("item7: third book at 5.00% below a higher main book passes (strictly lower)", v(21, 400, 20, 400) == "PASS")
    check("item7: both just below 5% passes", v(19, 400, 19, 400) == "PASS")
    check("item7: fewer than 200 bids waits (either book)", v(0, 199, 0, 400) == "WAIT" and v(0, 400, 0, 199) == "WAIT"
          and v(100, 200, 0, 200) == "PASS")
    check("item7: exact comparison on the counts (shares above 5%)", v(30, 300, 60, 601) == "PASS"
          and v(30, 300, 60, 600) == "FAIL" and v(30, 300, 61, 601) == "FAIL" and v(1000, 3000, 100000, 300001) == "PASS"
          and v(1000, 3000, 100000, 300000) == "FAIL")
    check("item7 overall: FAIL beats WAIT", item7.overall(["WAIT", "FAIL"]) == "FAIL"
          and item7.overall(["WAIT", "PASS"]) == "WAIT" and item7.overall(["PASS", "PASS"]) == "PASS")
    # end to end on per-bid rows: (a) from err_bp (missing level not counted, within a tick is 0), (b) from res_other_side
    main = pd.concat([rows(100, 400, "a"), pd.DataFrame(dict(err_bp=[np.nan] * 5, res_score=[np.nan] * 5,
                                                             res_other_side=[False] * 5))])
    tb = rows(50, 400, "a")
    tb.loc[0, "err_bp"] = 5.0                       # exactly 5 bp is not "more than 5 bp"
    r = item7.evaluate(main, tb)
    a = r["measures"]["a_level_gt5bp"]
    check("item7 evaluate: counts (a) skip missing levels, 5.0 bp is not beyond", (a["main_k"], a["main_n"], a["tb_k"],
                                                                                    a["tb_n"]) == (100, 400, 49, 400), a)
    b = r["measures"]["b_score_other_side"]
    check("item7 evaluate: (b) counts", (b["main_k"], b["main_n"], b["tb_k"], b["tb_n"]) == (0, 400, 0, 400)
          and b["verdict"] == "PASS" and r["overall"] == "PASS", b)
    r2 = item7.evaluate(rows(10, 400, "b"), rows(30, 400, "b"))
    check("item7 evaluate: (b) higher in the third book fails overall",
          r2["measures"]["b_score_other_side"]["verdict"] == "FAIL" and r2["overall"] == "FAIL")
    r3 = item7.evaluate(rows(10, 150, "a"), rows(0, 400, "a"))
    check("item7 evaluate: too few bids waits overall", r3["overall"] == "WAIT")
    md = item7.to_md(dict(r, period=dict(start="s", end="e"), minutes=dict(main=1, tb=2, common=1)))
    check("item7.md shows shares with two decimals", "25.00%" in md and "12.25%" in md and "PASS" in md, md)


def main():
    test_period()
    test_two_books()
    test_fetch_helpers()
    test_item7()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {FAILS}")
        sys.exit(1)
    print("test_two_books: all passed")


if __name__ == "__main__":
    main()
