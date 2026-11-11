#!/usr/bin/env python3
"""Tests for paper_status.py on small synthetic logs. Run: python scripts/owner/test_paper_status.py"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paper_status as ps  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
FAILS = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def write(root, folder, lines, raw_tail=None):
    d = os.path.join(root, folder)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "events.jsonl"), "w") as f:
        for o in lines:
            f.write(json.dumps(o) + "\n")
        if raw_tail is not None:
            f.write(raw_tail)


def entry(ts, rung, usd, ladder="A-1"):
    return {"ts": ts, "kind": "fill_entry", "coin": "ETH", "ladder": ladder, "rung": rung, "px": 100.0,
            "size": usd / 100.0, "usd": usd}


def exit_(ts, rung, pnl, how="tp", ladder="A-1"):
    return {"ts": ts, "kind": "fill_exit", "coin": "ETH", "ladder": ladder, "rung": rung, "exit": how,
            "px": 101.0, "entry_px": 100.0, "size": 1.0, "pnl": pnl, "net_bp": pnl, "equity": 250000 + pnl}


def build_root(tmp):
    # spot: 3 entries (rungs 4, 4, 6) = $3,000 + $1,000 + $2,000 bought; exits P&L 30 and -10 and 5
    spot = [
        {"ts": "2026-11-07T00:00:00", "kind": "backfill", "minutes": 10, "coins": 18},
        {"ts": "2026-11-07T01:00:00", "kind": "heartbeat", "equity": 250000, "committed": 100000, "free": 150000},
        {"ts": "2026-11-07T01:30:00", "kind": "heartbeat", "equity": 250000, "committed": 50000, "free": 200000},
        entry("2026-11-07T02:00:00", 4, 3000, "A-1"),
        entry("2026-11-07T02:10:00", 4, 1000, "A-2"),
        entry("2026-11-07T02:20:00", 6, 2000, "A-1"),
        exit_("2026-11-07T03:00:00", 4, 30.0, "tp", "A-1"),
        exit_("2026-11-08T03:00:00", 4, -10.0, "time", "A-2"),
        exit_("2026-11-08T04:00:00", 6, 5.0, "tp", "A-1"),
        {"ts": "2026-11-08T05:00:00", "kind": "ladder_close", "ladder": "A-1", "pnl": 35.0},
        {"ts": "2026-11-08T05:01:00", "kind": "ladder_close", "ladder": "A-2", "pnl": -10.0},
        {"ts": "2026-11-08T06:00:00", "kind": "cash_short", "coin": "SOL", "want": 5000, "free": 1000},
        {"ts": "2026-11-08T06:05:00", "kind": "cash_short", "coin": "SOL", "want": 3000, "free": 1000},
        {"ts": "2026-11-08T07:00:00", "kind": "error", "error": "boom | one at here"},
        {"ts": "2026-11-08T07:05:00", "kind": "error", "error": "boom | one at here"},
        {"ts": "2026-11-08T07:10:00", "kind": "error", "error": "x" * 400},
        {"ts": "2026-11-09T08:00:00", "kind": "brand_new_kind", "x": 1},
    ]
    # truncated last line
    write(tmp, "paper_spot", spot, raw_tail='{"ts": "2026-11-09T09:00:00", "kind": "fill_ent')
    with open(os.path.join(tmp, "paper_spot", "state.json"), "w") as f:
        json.dump({"equity": 250040.0}, f)
    # W2: empty log
    write(tmp, "paper_spot_w2", [])
    # perp v1: exits but no entries, old newest event (stale)
    write(tmp, "paper", [
        {"ts": "2026-11-09T20:00:00", "kind": "heartbeat", "equity": 10000},
        {"ts": "2026-11-09T21:00:00", "kind": "bid", "coin": "ENA"},
        {"ts": "2026-11-09T21:00:01", "kind": "bid", "coin": "ENA"},
        {"ts": "2026-11-09T22:00:00", "kind": "fill_exit", "coin": "BCH", "exit": "tp", "pnl": 20.0, "net_bp": 50.0,
         "equity": 10020.0},
    ])
    # perp v2 folder missing entirely
    return tmp


def T(h, m=0, day=7):
    """ISO time on Nov 'day' 2026, hour h, minute m (may exceed 59 or 23 through timedelta in the caller)."""
    return datetime(2026, 11, day, tzinfo=timezone.utc) + timedelta(hours=h, minutes=m)


def iso(t):
    return t.replace(tzinfo=None).isoformat()


def gap_book(root, folder="paper_spot", with_hb=True):
    """Ten calendar hours from 00:00 to 10:00; catch_up gaps of 120 minutes (ending 04:00) and 60 (ending 08:00)."""
    ev = [{"ts": iso(T(0)), "kind": "backfill"}]
    if with_hb:
        for k in range(1, 21):
            t = T(0, 30 * k)
            if T(2) < t <= T(4) or T(7) < t <= T(8):
                continue
            ev.append({"ts": iso(t), "kind": "heartbeat", "equity": 250000, "committed": 1000, "counts": {"arm": 1}})
    ev += [{"ts": iso(T(4)), "kind": "catch_up", "gap_minutes": 120, "open": []},
           {"ts": iso(T(8)), "kind": "catch_up", "gap_minutes": 60, "open": []},
           {"ts": iso(T(10)), "kind": "arm", "coin": "ETH"}]
    ev.sort(key=lambda e: e["ts"])
    write(root, folder, ev)
    return ev


def running_time_tests():
    with tempfile.TemporaryDirectory() as tmp:
        gap_book(tmp)
        b = ps.load_book(tmp, "paper_spot")
        s = ps.stats(b, 250000.0, True)
        rt = ps.running_time(b["events"], s["first"], s["newest"])
        check("running time: calendar hours", rt["ok"] and abs(rt["cal_h"] - 10.0) < 1e-9, rt)
        check("running time: real-time hours from catch_up gaps", abs(rt["run_h"] - 7.0) < 1e-9, rt["run_h"])
        check("running time: share", abs(rt["share"] - 70.0) < 1e-9, rt["share"])
        check("running time: longest gap first with its start", rt["gaps"][0] == (T(2), 2.0) and rt["gaps"][1] == (T(7), 1.0),
              rt["gaps"])
        check("up_hours inside a gap is zero and across it is cut", ps.up_hours(rt, T(2, 30), T(3, 30)) == 0.0
              and abs(ps.up_hours(rt, T(1), T(5)) - 2.0) < 1e-9)
        text = ps.build_report(tmp, NOW)
        check("report has Running time before Summary", 0 < text.index("## Running time") < text.index("## Summary"))
        check("report running time row", "| 10.0 | 7.0 | 70.0% |" in text, text[text.index("## Running time"):][:900])
        check("report lists gap starts", "2026-11-07 02:00 UTC | 2.0" in text)
        check("rates both ways, labelled, next to the rule text", ps.RULE_A_RATE in text
              and "per calendar day; " in text and "per running day" in text)
        check("both_rates arithmetic", ps.both_rates(7, rt) == "16.80 per calendar day; 24.00 per running day",
              ps.both_rates(7, rt))
    # more than five gaps: only five printed per book
    with tempfile.TemporaryDirectory() as tmp:
        ev = [{"ts": iso(T(0)), "kind": "backfill"}]
        for k in range(1, 7):
            ev.append({"ts": iso(T(2 * k)), "kind": "catch_up", "gap_minutes": 10 * k, "open": []})
        ev.append({"ts": iso(T(14)), "kind": "arm"})
        write(tmp, "paper_spot", ev)
        b = ps.load_book(tmp, "paper_spot")
        s = ps.stats(b, 250000.0, True)
        rt = ps.running_time(b["events"], s["first"], s["newest"])
        text = ps.build_report(tmp, NOW)
        rows = [l for l in text.split("The five longest gaps")[1].split("\n\n")[1].splitlines() if "Spot (main)" in l]
        check("five longest gaps only", len(rt["gaps"]) == 6 and len(rows) == 5 and rows[0].endswith("| 1.0 |"), rows)
    # perp-style log: sub-minute timestamps, catch_up with open_positions
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "paper", [{"ts": "2026-11-07T00:00:05.5", "kind": "backfill"},
                             {"ts": "2026-11-07T05:00:01.25", "kind": "catch_up", "gap_minutes": 180, "open_positions": []},
                             {"ts": "2026-11-07T06:00:00.5", "kind": "heartbeat", "equity": 10000}])
        b = ps.load_book(tmp, "paper")
        s = ps.stats(b, 10000.0, False)
        rt = ps.running_time(b["events"], s["first"], s["newest"])
        check("perp log gap", rt["ok"] and abs(rt["run_h"] - (6 - 3 - 0.0 / 3600)) < 0.01, rt["run_h"])
    # no catch_up: regular heartbeats are enough, a hole in the heartbeats is not
    def hb_only(tmp, times):
        write(tmp, "paper_spot", [{"ts": iso(t), "kind": "heartbeat", "equity": 1, "counts": {}} for t in times])
        b = ps.load_book(tmp, "paper_spot")
        s = ps.stats(b, 250000.0, True)
        return ps.running_time(b["events"], s["first"], s["newest"]), ps.build_report(tmp, NOW)
    with tempfile.TemporaryDirectory() as tmp:
        rt, text = hb_only(tmp, [T(0, 30 * k) for k in range(8)])
        check("no catch_up and regular heartbeats: no gaps", rt["ok"] and abs(rt["share"] - 100.0) < 1e-9)
    with tempfile.TemporaryDirectory() as tmp:
        rt, text = hb_only(tmp, [T(0), T(0, 30), T(4), T(4, 30)])
        check("no catch_up and a hole in the heartbeats: not derivable", not rt["ok"]
              and "not derivable from this log" in text, rt)
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "paper_spot", [{"ts": iso(T(0)), "kind": "arm"}])
        b = ps.load_book(tmp, "paper_spot")
        s = ps.stats(b, 250000.0, True)
        rt = ps.running_time(b["events"], s["first"], s["newest"])
        check("one event: not derivable, no error", not rt["ok"])


def hb(t, counts=None, step=None, **kw):
    o = {"ts": iso(t), "kind": "heartbeat", "equity": 250000, "committed": 1000, "counts": counts if counts is not None else {}}
    if step is not None:
        o["step_s"] = step
    o.update(kw)
    return o


def data_quality_tests():
    with tempfile.TemporaryDirectory() as tmp:
        ev = [{"ts": iso(T(0)), "kind": "backfill"}]
        ev += [hb(T(0, 30), {"arm": 3, "reprice": 9})]                 # old heartbeat: none of the fields
        ev += [hb(T(1), {"newest_absent": 2, "tb_built": 100, "mystery": 5, "tb_brand_new": 4},
                  {"data": [10.0, 18.0], "cancel": [20, 21], "place": [25, 26]}),
               hb(T(1, 30), {"newest_absent": 1, "tb_built": 50, "tb_empty": 3}, {"data": [12.0, 30.0]}, tb_err="BTC: boom"),
               hb(T(2), {}, {"data": [14.0, 19.0]}),                      # reporting with no counter: all zero
               hb(T(2, 30), {"rows_open": "x", "tb_empty": None}, {"data": "bad"}),   # junk values must not break
               hb(T(24, 30), {"obs_error": 2}, {"data": [8.0, 9.0]})]    # next UTC day
        ev.append({"ts": iso(T(25)), "kind": "arm"})
        write(tmp, "paper_spot", ev)
        write(tmp, "paper_spot_w2", [{"ts": iso(T(0)), "kind": "backfill"}, hb(T(0, 30), {"arm": 1}), {"ts": iso(T(1)), "kind": "arm"}])
        b = ps.load_book(tmp, "paper_spot")
        s = ps.stats(b, 250000.0, True)
        rt = ps.running_time(b["events"], s["first"], s["newest"])
        dq = ps.data_quality(b["events"], rt)
        t = dq["total"]
        check("dq: reporting heartbeats counted, old one skipped", t["beats"] == 5 and dq["all_beats"] == 6, (t["beats"], dq["all_beats"]))
        check("dq: listed counters summed", t["counts"]["newest_absent"] == 3 and t["counts"]["tb_built"] == 150
              and t["counts"]["tb_empty"] == 3 and t["counts"]["obs_error"] == 2, dict(t["counts"]))
        check("dq: unknown tb_ counter counted, other unknown key ignored",
              t["counts"].get("tb_brand_new") == 4 and "mystery" not in t["counts"] and "arm" not in t["counts"])
        check("dq: junk counter values ignored", "rows_open" not in t["counts"])
        check("dq: data step median of medians and largest max", t["data_median"] == 11.0 and t["data_max"] == 30.0
              and t["data_n"] == 4, (t["data_median"], t["data_max"], t["data_n"]))
        check("dq: heartbeats within 20 s", t["data_le20"] == 3, t["data_le20"])
        check("dq: minutes run are 30 per heartbeat", abs(t["minutes"] - 150.0) < 1e-9, t["minutes"])
        check("dq: split by UTC day", sorted(d.day for d in dq["days"]) == [7, 8] and dq["days"][T(0).date()]["beats"] == 4)
        check("dq: tb_err kept", len(t["errs"]) == 1 and "boom" in t["errs"][0]["err"])
        text = ps.build_report(tmp, NOW)
        sec = text.split("## Data quality")[1].split("## Perp books")[0]
        check("dq report: old book says not reported", sec.count("not reported by this book's code yet") == 1
              and sec.index("### Spot W2") < sec.index("not reported by this book's code yet"), sec[:900])
        check("dq report: table for the reporting book", "| Total | 150 | 5 | 11.0 | 30.0 |" in sec and "tb_brand_new 4" in sec, sec[:1500])
    # minutes run drop the gap inside a heartbeat's 30 minutes
    with tempfile.TemporaryDirectory() as tmp:
        ev = [{"ts": iso(T(0)), "kind": "backfill"}, hb(T(0, 30), {"tb_built": 1}, {"data": [1, 2]}),
              {"ts": iso(T(3)), "kind": "catch_up", "gap_minutes": 150, "open": []},    # down 00:30 to 03:00
              hb(T(3, 15), {"tb_built": 1}, {"data": [1, 2]})]
        write(tmp, "paper_spot", ev)
        b = ps.load_book(tmp, "paper_spot")
        s = ps.stats(b, 250000.0, True)
        rt = ps.running_time(b["events"], s["first"], s["newest"])
        dq = ps.data_quality(b["events"], rt)
        mins = [r["minutes"] for r in dq["rep"]]
        check("dq: minutes run exclude gap time", abs(mins[0] - 30.0) < 1e-9 and abs(mins[1] - 15.0) < 1e-9, mins)


def tb_books(tmp, counts, step, errors=0, extra=None, n=100):
    """Main book with old heartbeats and a third book with n reporting heartbeats (30 minutes apart, no gaps)."""
    main = [{"ts": iso(T(0)), "kind": "backfill"}] + [hb(T(0, 30 * k)) for k in range(1, n + 1)]
    tb = [{"ts": iso(T(0)), "kind": "backfill"}] + [hb(T(0, 30 * k), dict(counts), dict(step) if step else None) for k in range(1, n + 1)]
    tb += [{"ts": iso(T(0, 40 + k)), "kind": "error", "error": "e"} for k in range(errors)] + list(extra or [])
    write(tmp, "paper_spot", sorted(main, key=lambda e: e["ts"]))
    write(tmp, "paper_spot_tb", sorted(tb, key=lambda e: e["ts"]))


GOOD_COUNTS = {"tb_built": 150, "tb_empty": 30, "rows_open": 5}      # 180 of 6 x 30 = 180 coin-minutes per heartbeat
GOOD_STEP = {"data": [10.0, 15.0], "cancel": [14, 18], "place": [20, 25]}


def verdicts(tmp):
    b = ps.load_book(tmp, "paper_spot_tb")
    s = ps.stats(b, 250000.0, True)
    rt = ps.running_time(b["events"], s["first"], s["newest"])
    dq = ps.data_quality(b["events"], rt)
    run_min, rows = ps.tb_rule_rows(dq, s, b["events"], ps.TB_DEFAULT_COINS, rt)
    return run_min, [r[2] for r in rows], rows


def third_book_tests():
    # absent: no third-book sections, no mention in the report, the four-book report is unchanged in shape
    with tempfile.TemporaryDirectory() as tmp:
        build_root(tmp)
        text = ps.build_report(tmp, NOW)
        check("third book absent: no third-book sections", "Third book" not in text and "Three-day rule" not in text
              and "paper_spot_tb" not in text and "Spot TB" not in text)
    # present, everything good: all five items meet
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, GOOD_STEP)
        run_min, v, rows = verdicts(tmp)
        check("rule: all five items meet on good data", v[:5] == ["meets"] * 5, rows)
        text = ps.build_report(tmp, NOW)
        check("third book present: sections exist", "## Third book against the main book" in text
              and "## Three-day rule progress for the third book" in text and "Spot TB" in text)
        check("rule section: item 6 text and minutes against 4,000", "from the forward collector; computed at the read by scripts/owner/tb_rule6.py" in text
              and "of 4,000" in text, text[text.index("## Three-day"):][:700])
        check("comparison says it is not the pass rule", "for the record" in text and "not the pass rule" in text)
        check("the whole report still has no at-sign", chr(64) not in text)
        check("minutes so far", abs(run_min - 3000.0) < 1e-6, run_min)
    # item 1: 99% of 180 coin-minutes is 178.2
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, {"tb_built": 179, "tb_empty": 1}, GOOD_STEP)
        check("rule item 1 meets at 100%", verdicts(tmp)[1][0] == "meets")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, {"tb_built": 150, "tb_empty": 28}, GOOD_STEP)       # 178 of 180 = 98.9%
        check("rule item 1 fails just below 99%", verdicts(tmp)[1][0] == "does not meet yet")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, {"tb_built": 150, "tb_empty": 29}, GOOD_STEP)       # 179 of 180 = 99.4%
        check("rule item 1 meets just above 99%", verdicts(tmp)[1][0] == "meets")
    # item 2: rate limit counter, refusal text
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, dict(GOOD_COUNTS, tb_fb_limited=1), GOOD_STEP)
        check("rule item 2 fails on tb_fb_limited", verdicts(tmp)[1][1] == "does not meet yet")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, GOOD_STEP, extra=[{"ts": iso(T(1)), "kind": "warning", "msg": "Coinbase refused the request"}])
        check("rule item 2 fails on a refusal in an event", verdicts(tmp)[1][1] == "does not meet yet")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, GOOD_STEP, extra=[{"ts": iso(T(1)), "kind": "arm", "coin": "XLM", "ladder": "XLM-429", "px": 0.429}])
        check("rule item 2 ignores numbers and ladder names", verdicts(tmp)[1][1] == "meets")
    # item 3: median at 13 and just above; share of maxima at 20 s
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, {"data": [13.0, 20.0]})
        check("rule item 3 meets exactly at 13 s and 20 s", verdicts(tmp)[1][2] == "meets")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, {"data": [13.01, 15.0]})
        check("rule item 3 fails on the median", verdicts(tmp)[1][2] == "does not meet yet")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, {"data": [10.0, 20.01]})
        check("rule item 3 fails when every maximum is over 20 s", verdicts(tmp)[1][2] == "does not meet yet")
    # item 3 share of heartbeats: 94 of 100 within 20 s fails, 95 passes
    for slow, want in ((6, "does not meet yet"), (5, "meets")):
        with tempfile.TemporaryDirectory() as tmp:
            tb_books(tmp, GOOD_COUNTS, GOOD_STEP)
            b = ps.load_book(tmp, "paper_spot_tb")
            evs = [o for o in b["events"]]
            seen = 0
            lines = []
            for o in evs:
                o = {k: v for k, v in o.items() if k != "_t"}
                if o["kind"] == "heartbeat" and seen < slow:
                    o["step_s"] = {"data": [10.0, 21.0]}
                    seen += 1
                lines.append(o)
            write(tmp, "paper_spot_tb", lines)
            check(f"rule item 3 with {slow} slow heartbeats of 100", verdicts(tmp)[1][2] == want, verdicts(tmp)[2][2])
    # item 4: error events, obs_error
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, GOOD_STEP, errors=1)
        check("rule item 4 fails on an error event", verdicts(tmp)[1][3] == "does not meet yet")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, dict(GOOD_COUNTS, obs_error=1), GOOD_STEP)
        check("rule item 4 fails on obs_error", verdicts(tmp)[1][3] == "does not meet yet")
    # item 5: 1% of 18 x 30 = 5.4 coin-minutes per heartbeat
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, dict(GOOD_COUNTS, rows_open=5), GOOD_STEP)
        check("rule item 5 meets below 1%", verdicts(tmp)[1][4] == "meets")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, dict(GOOD_COUNTS, rows_open=6), GOOD_STEP)
        check("rule item 5 fails above 1%", verdicts(tmp)[1][4] == "does not meet yet")
    # old-style third book (no new fields): every item says so
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, {"arm": 1}, None)
        write(tmp, "paper_spot_tb", [{"ts": iso(T(0)), "kind": "backfill"}, hb(T(0, 30), {"arm": 1}), hb(T(1), {"arm": 1})])
        v = verdicts(tmp)[1]
        check("rule: no new fields means does not meet yet", v == ["does not meet yet"] * 5, v)
        text = ps.build_report(tmp, NOW)
        check("data quality says not reported for the third book", "not reported by this book's code yet" in text)
    # config list is read
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "bot", "spot"))
        with open(os.path.join(tmp, "bot", "spot", "config.tb.json"), "w") as f:
            json.dump({"trades_coins": ["BTC", "ETH"]}, f)
        check("coin list read from the config", ps.load_tb_coins(tmp)[0] == ["BTC", "ETH"])
        check("coin list defaults to six when no config", ps.load_tb_coins(os.path.join(tmp, "x"))[0] == ps.TB_DEFAULT_COINS)
    # first-bid overlap matching
    def f(t, coin):
        return {"_t": t, "coin": coin}
    a = [f(T(1), "ETH"), f(T(2), "SOL"), f(T(3), "XRP"), f(T(4), "BTC")]
    b = [f(T(1, 2), "ETH"), f(T(2, 3), "SOL"), f(T(3), "LTC"), f(T(4, 1), "BTC"), f(T(5), "BTC")]
    check("overlap: two minutes counts, three minutes and other coins do not",
          ps.match_first_bids(a, b) == (2, 2, 3), ps.match_first_bids(a, b))
    x = [f(T(1), "ETH"), f(T(1, 1), "ETH")]
    y = [f(T(1, 1), "ETH")]
    check("overlap: each fill used once", ps.match_first_bids(x, y) == (1, 1, 0), ps.match_first_bids(x, y))
    # overlap and side-by-side through the report
    with tempfile.TemporaryDirectory() as tmp:
        m = [{"ts": iso(T(0)), "kind": "backfill"}, entry(iso(T(1)), 4, 1000, "A-1"), entry(iso(T(2)), 4, 2000, "A-2"),
             entry(iso(T(3)), 6, 500, "A-1"), exit_(iso(T(4)), 4, 10.0), {"ts": iso(T(9)), "kind": "arm"}]
        tbl = [{"ts": iso(T(0, 30)), "kind": "backfill"}, entry(iso(T(1, 2)), 4, 1000, "A-1"),
               entry(iso(T(2, 5)), 4, 2000, "A-2"), entry(iso(T(6)), 4, 700, "A-3"), exit_(iso(T(7)), 4, 7.0),
               {"ts": iso(T(9)), "kind": "arm"}]
        for e in m + tbl:
            if e["kind"] in ("fill_entry", "fill_exit"):
                e["coin"] = "ETH"
        tbl[2]["coin"] = "SOL"            # the second fill is on another coin, so no match
        write(tmp, "paper_spot", m)
        write(tmp, "paper_spot_tb", tbl)
        text = ps.build_report(tmp, NOW)
        sec = text.split("## Third book against the main book")[1].split("## Three-day")[0]
        check("report: overlap counts", "| First-bid fills in both books | 1 |" in sec and "| Only in the main book | 1 |" in sec
              and "| Only in the third book | 2 |" in sec, sec)
        check("report: side by side", "| Rung fills | 3 | 3 | +0 |" in sec and "| Dollars bought | $3,500 | $3,700 |" in sec
              and "| Exit P&L | $10.00 | $7.00 |" in sec, sec)



def main():
    with tempfile.TemporaryDirectory() as tmp:
        build_root(tmp)
        try:
            text = ps.build_report(tmp, NOW)
        except Exception as exc:  # the whole point: never raises
            check("report builds without raising", False, repr(exc))
            return
        check("report builds without raising", True)

        s = ps.stats(ps.load_book(tmp, "paper_spot"), 250000.0, True)
        check("truncated last line skipped and counted", s["bad"] == 1 and s["n"] == 17, f"bad={s['bad']} n={s['n']}")
        check("rung fills", s["fills"] == 3)
        check("dollars bought", s["bought"] == 6000.0, s["bought"])
        check("exit pnl", abs(s["pnl"] - 25.0) < 1e-9, s["pnl"])
        check("net bp per dollar bought", abs(s["net_bp"] - 1e4 * 25 / 6000) < 1e-9, s["net_bp"])
        check("tp and time split", (s["tp"], s["time"]) == (2, 1))
        check("ladders closed and winners", (s["ladders"], s["ladders_win"]) == (2, 1))
        check("equity from state.json", s["equity"] == 250040.0)
        check("percent change", abs(s["change_pct"] - 100 * 40 / 250000) < 1e-9)
        check("rung table", s["by_rung"][4]["fills"] == 2 and s["by_rung"][6]["fills"] == 1 and s["by_rung"][8]["fills"] == 0)
        check("rung 4 net bp", abs(1e4 * s["by_rung"][4]["pnl"] / s["by_rung"][4]["bought"] - 1e4 * 20 / 4000) < 1e-9)
        check("cash shortfalls", s["shorts"] == 2 and s["want_total"] == 8000 and s["free_avg"] == 1000)
        check("committed share", abs(s["commit_share"] - 100 * (0.4 + 0.2) / 2) < 1e-9, s["commit_share"])
        check("largest loss day", s["worst_day"] is not None and abs(s["worst_day"][1] + 5.0) < 1e-9, s["worst_day"])
        check("unknown kind counted", s["unknown"] == {"brand_new_kind": 1}, s["unknown"])
        check("errors grouped and truncated",
              s["errors"] == 3 and len(s["error_msgs"]) == 2 and max(s["error_msgs"].values()) == 2
              and max(len(m) for m in s["error_msgs"]) == ps.ERR_CHARS, dict(s["error_msgs"]))
        check("rule A is CHECK with errors", ps.rule_a(s) == "CHECK")

        w2 = ps.stats(ps.load_book(tmp, "paper_spot_w2"), 250000.0, True)
        check("empty log status", w2["status"] == "empty" and w2["newest"] is None)
        v2 = ps.stats(ps.load_book(tmp, "paper_v2"), 10000.0, False)
        check("missing folder status", v2["status"] == "missing")
        v1 = ps.stats(ps.load_book(tmp, "paper"), 10000.0, False)
        check("exits without entries: no division error", v1["fills"] == 0 and v1["net_bp"] is None and v1["exits"] == 1)
        check("perp bids counted", v1["bids"] == 2)
        check("perp mean net bp", v1["mean_net_bp"] == 50.0)
        check("perp equity from last exit", v1["equity"] == 10020.0)

        check("report flags stale perp book", "STALE" in text)
        check("report notes missing folder", "folder or events file not found" in text)
        check("report lists unknown kind", "brand_new_kind (1)" in text)
        check("report has rule A text", ps.RULE_A in text)
        check("report ends with the fixed line", text.rstrip().endswith(ps.LAST_LINE))
        check("no at-sign in report", chr(64) not in text)
        check("money format", ps.money(1234.56) == "$1,235" and ps.money(46.034) == "$46.03" and ps.money(-1500) == "-$1,500")
        check("rule A status values",
              ps.rule_a({"days": 3, "fills": 5, "errors": 0, "net_bp": 10.0}) == "NOT YET (too early)"
              and ps.rule_a({"days": 22, "fills": 61, "errors": 0, "net_bp": 10.0}) == "ON TRACK"
              and ps.rule_a({"days": 22, "fills": 61, "errors": 0, "net_bp": 0.0}) == "CHECK")

        # main() writes the file under the root and returns 0
        rc = ps.main([tmp, "--now", "2026-11-10T12:00:00"])
        check("main writes PAPER_STATUS.md", rc == 0 and os.path.exists(os.path.join(tmp, "reports", "owner", "PAPER_STATUS.md")))

    # nothing at all: a root with no folders, and a root that does not exist
    with tempfile.TemporaryDirectory() as tmp:
        try:
            text = ps.build_report(tmp, NOW)
            ok = "NO DATA" in text
        except Exception as exc:
            ok, text = False, repr(exc)
        check("empty root does not raise", ok, text[:200])
    try:
        ps.build_report(os.path.join(tmp, "does", "not", "exist"), NOW)
        check("nonexistent root does not raise", True)
    except Exception as exc:
        check("nonexistent root does not raise", False, repr(exc))

    # garbage lines: non-dict json, missing ts, bad numbers
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "paper_spot")
        os.makedirs(d)
        with open(os.path.join(d, "events.jsonl"), "w") as f:
            f.write("[1,2]\n\n{\"kind\": \"fill_entry\", \"usd\": \"abc\", \"rung\": null}\n{\"ts\": 5}\n"
                    "{\"ts\": \"2026-11-09T01:00:00\", \"kind\": \"fill_exit\", \"pnl\": null, \"exit\": null}\n")
        with open(os.path.join(d, "state.json"), "w") as f:
            f.write("{not json")
        try:
            ps.build_report(tmp, NOW)
            check("garbage values do not raise", True)
        except Exception as exc:
            check("garbage values do not raise", False, repr(exc))

    # explained errors: window, message, book
    msg = "KeyError(\"Cannot get left slice bound for non-monotonic index with a missing label\")"
    entry_ok = {"match": "Cannot get left slice bound", "from": "2026-11-07T21:00:00Z", "to": "2026-11-07T22:00:00Z",
                "books": ["spot"], "explained": "Because of a known bug.", "fix": "A sort is queued."}

    def explained_root(tmp, spot_errors, w2_errors, expl_text):
        for folder, errs in (("paper_spot", spot_errors), ("paper_spot_w2", w2_errors)):
            write(tmp, folder, [{"ts": "2026-11-07T00:00:00", "kind": "backfill"}] +
                  [{"ts": t, "kind": "error", "error": m} for t, m in errs])
        os.makedirs(os.path.join(tmp, "reports", "owner"), exist_ok=True)
        if expl_text is not None:
            with open(os.path.join(tmp, "reports", "owner", "explained_errors.json"), "w") as f:
                f.write(expl_text)

    def unexplained(tmp, key, folder, spot_style=True):
        entries, _ = ps.load_explanations(tmp)
        s = ps.stats(ps.load_book(tmp, folder), 250000.0, spot_style)
        ex, un = ps.classify_errors(key, s["error_events"], entries)
        return len(ex), len(un)

    with tempfile.TemporaryDirectory() as tmp:
        explained_root(tmp, [("2026-11-07T21:19:07", msg)], [("2026-11-07T21:19:07", msg)], json.dumps([entry_ok]))
        check("error inside the window is explained", unexplained(tmp, "spot", "paper_spot") == (1, 0))
        check("wrong book stays unexplained", unexplained(tmp, "w2", "paper_spot_w2") == (0, 1))
        text = ps.build_report(tmp, NOW)
        check("report shows the three error rows", "| Errors (total) | 1 |" in text and "| Explained | 1 |" in text
              and "| Unexplained | 0 |" in text)
        check("report shows explanation and fix", "Because of a known bug." in text and "A sort is queued." in text)
        check("rule A is NOT YET when the only error is explained", "Status: **NOT YET (too early)**" in text)
        check("summary keeps total error count", "| 1 |" in text.split("## Summary")[1].split("##")[0])

    with tempfile.TemporaryDirectory() as tmp:
        explained_root(tmp, [("2026-11-08T21:19:07", msg), ("2026-11-07T20:59:59", msg)], [], json.dumps([entry_ok]))
        check("same message outside the window stays unexplained", unexplained(tmp, "spot", "paper_spot") == (0, 2))
        text = ps.build_report(tmp, NOW)
        check("unexplained errors give CHECK", "Status: **CHECK**" in text and "| Unexplained | 2 |" in text)

    with tempfile.TemporaryDirectory() as tmp:
        explained_root(tmp, [("2026-11-07T21:19:07", msg)], [], "{this is not json")
        try:
            entries, note = ps.load_explanations(tmp)
            text = ps.build_report(tmp, NOW)
            check("malformed explanation file does not raise", entries == [] and note is not None
                  and "| Unexplained | 1 |" in text and "every error counts as unexplained" in text)
        except Exception as exc:
            check("malformed explanation file does not raise", False, repr(exc))
    with tempfile.TemporaryDirectory() as tmp:
        explained_root(tmp, [("2026-11-07T21:19:07", msg)], [], None)
        try:
            ps.build_report(tmp, NOW)
            check("missing explanation file does not raise", True)
        except Exception as exc:
            check("missing explanation file does not raise", False, repr(exc))

    # report fixes: daily table starts at the first event; perp fills per day
    with tempfile.TemporaryDirectory() as tmp:
        build_root(tmp)
        text = ps.build_report(tmp, NOW)
        day_rows = [l for l in text.split("P&L of exits by day")[1].split("\n\n")[1].splitlines() if l.startswith("| 2026")]
        check("daily table starts at the first event", day_rows[0].startswith("| 2026-11-07 ") and len(day_rows) <= 14, day_rows[:2])
        check("perp table has fills per day both ways", "Fills per calendar day" in text and "Fills per running day" in text)
        v1 = ps.stats(ps.load_book(tmp, "paper"), 10000.0, False)
        check("perp days run", v1["days"] is not None and abs(v1["days"] - 2 / 24) < 1e-9, v1["days"])

    running_time_tests()
    data_quality_tests()
    third_book_tests()

    print("\n" + ("all passed" if not FAILS else f"{len(FAILS)} failed: {FAILS}"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
