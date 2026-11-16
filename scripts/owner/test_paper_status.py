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


def restart_gap_tests():
    """No catch_up: a heartbeat pair 46 to 75 minutes apart is accepted only with a backfill after the first and up to the
    second heartbeat (a run handover; the new run's history download can leave one heartbeat out)."""
    def run(times, backfills=(), extra=()):
        ev = [{"ts": iso(t), "kind": "heartbeat", "equity": 1, "counts": {}} for t in times]
        ev += [{"ts": iso(t), "kind": "backfill", "minutes": 5} for t in backfills] + list(extra)
        ev.sort(key=lambda e: e.get("ts", ""))
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "paper_spot", ev)
            b = ps.load_book(tmp, "paper_spot")
            s = ps.stats(b, 250000.0, True)
            return ps.running_time(b["events"], s["first"], s["newest"])

    def never_gapped(rt, cal_h):
        return rt["ok"] and rt["gaps"] == [] and rt["down"] == [] and abs(rt["share"] - 100.0) < 1e-9 \
            and abs(rt["run_h"] - cal_h) < 1e-9
    check("restart: limits are named constants", ps.HEARTBEAT_GAP_MAX_MIN == 45 and ps.HEARTBEAT_RESTART_GAP_MAX_MIN == 75)
    rt = run([T(0, 30 * k) for k in range(6)])
    check("restart: every 30 minutes, derivable and 100%", never_gapped(rt, 2.5), rt)
    rt = run([T(0), T(0, 30), T(1, 30), T(2)], [T(0, 57)])
    check("restart: 60 minutes with a backfill between: derivable, 100%, no gaps", never_gapped(rt, 2.0), rt)
    rt = run([T(0), T(0, 30), T(1, 30), T(2)])
    check("restart: 60 minutes without a backfill: not derivable", not rt["ok"], rt)
    rt = run([T(0), T(0, 30), T(1, 30), T(2)], [T(0, 10), T(3)])
    check("restart: backfills only outside the pair: not derivable", not rt["ok"], rt)
    rt = run([T(0), T(0, 30), T(2), T(2, 30)], [T(1)])
    check("restart: 90 minutes with a backfill: not derivable", not rt["ok"], rt)
    rt = run([T(0), T(0, 30), T(1, 45), T(2, 15)], [T(1)])
    check("restart: exactly 75 minutes with a backfill: derivable", never_gapped(rt, 2.25), rt)
    rt = run([T(0), T(0, 30), T(1, 46), T(2, 16)], [T(1)])
    check("restart: 76 minutes with a backfill: not derivable", not rt["ok"], rt)
    rt = run([T(0), T(0, 30), T(1, 15), T(1, 45)], [T(1)])
    check("restart: exactly 45 minutes needs nothing", never_gapped(rt, 1.75), rt)
    rt = run([T(0), T(0, 30), T(1, 30), T(2)], [T(1, 30)])
    check("restart: a backfill exactly at the second heartbeat counts", never_gapped(rt, 2.0), rt)
    rt = run([T(0), T(0, 30), T(1, 30), T(2)], [T(0, 30)])
    check("restart: a backfill exactly at the first heartbeat does not count", not rt["ok"], rt)
    rt = run([T(0), T(1), T(1, 30), T(2, 30), T(3)], [T(0, 40), T(1, 50)])
    check("restart: two long pairs, both backfilled: derivable", never_gapped(rt, 3.0), rt)
    rt = run([T(0), T(1), T(1, 30), T(2, 30), T(3)], [T(0, 40)])
    check("restart: two long pairs, one without a backfill: not derivable", not rt["ok"], rt)
    rt = run([T(0), T(1), T(1, 30), T(3), T(3, 30)], [T(0, 40), T(2)])
    check("restart: two long pairs, one over 75 minutes: not derivable", not rt["ok"], rt)
    rt = run([T(0), T(0, 30), T(1, 30), T(2)], [T(0, 57)], extra=[{"ts": "bad", "kind": "backfill"}, {"kind": "backfill"}])
    check("restart: backfill events without a usable time are skipped", never_gapped(rt, 2.0), rt)
    # a book with a catch_up event is read as before: the heartbeat spacing does not matter, the gap is the catch_up's
    for bfs in ([T(0, 57)], []):
        rt = run([T(0), T(0, 30), T(1, 30), T(2), T(2, 30), T(3), T(3, 30), T(4)], bfs,
                 [{"ts": iso(T(3)), "kind": "catch_up", "gap_minutes": 60, "open": []}])
        check("restart: with a catch_up the old result, hours down equal the catch_up gap (backfill %d)" % len(bfs),
              rt["ok"] and abs(rt["cal_h"] - 4.0) < 1e-9 and abs(rt["run_h"] - 3.0) < 1e-9 and abs(rt["share"] - 75.0) < 1e-9
              and rt["gaps"] == [(T(2), 1.0)] and rt["down"] == [(T(2), T(3))], rt)
    # the report: a fourth book whose only long pair is accepted shows minutes and no "not derivable" in its lines
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, {"data": [14.0, 15.0]}, n=10)
        counts = {"tb_built": 538, "tb_empty": 2, "rows_open": 5}
        t18 = [{"ts": iso(T(0)), "kind": "backfill"}]
        t18 += [hb(T(0, 30 * k), dict(counts), {"data": [14.0, 15.0]}) for k in (1, 2, 4, 5, 6)]   # 01:00 to 02:00 is one pair
        t18.append({"ts": iso(T(1, 57)), "kind": "backfill"})
        # the pair 01:00 and 02:00 is 60 minutes apart with a backfill at 01:57
        write(tmp, "paper_spot_t18", sorted(t18, key=lambda e: e["ts"]))
        text = ps.build_report(tmp, NOW)
        run = text.split("## Running time")[1].split("\n## ")[0]
        rows = [l for l in run.splitlines() if l.startswith("| Spot T18")]
        sec = text.split("## Rule progress for the fourth book")[1].split("\n## ")[0]
        line = [l for l in sec.splitlines() if l.startswith("Real-time minutes run so far")]
        check("restart: report row for the fourth book has numbers", len(rows) == 1 and "| 3.0 | 3.0 | 100.0% |" in rows[0]
              and "not derivable" not in rows[0], rows)
        check("restart: fourth book's minutes line is a number", line == ["Real-time minutes run so far: 180."], line)
        check("restart: no 'not derivable' in the fourth book's lines", "not derivable" not in sec.split("Real-time minutes")[0]
              and "not derivable" not in line[0] if line else False)


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
        check("rule section: item 7 row and intro", "items 1 to 7" in text
              and "from the reconciliation (scripts/owner/reconcile); not computed here" in text)
        check("comparison says it is not the pass rule", "for the record" in text and "not the pass rule" in text)
        check("the whole report still has no at-sign", chr(64) not in text)
        check("minutes so far", abs(run_min - 3000.0) < 1e-6, run_min)
    # item 1: 99% of 180 coin-minutes is 178.2
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, {"tb_built": 179, "tb_empty": 1}, GOOD_STEP)
        check("rule item 1 meets at 100%", verdicts(tmp)[1][0] == "meets")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, {"tb_built": 150, "tb_empty": 28, "tb_fb_unverified": 2}, GOOD_STEP)       # 178 of 180 attempted = 98.9%
        check("rule item 1 fails just below 99%", verdicts(tmp)[1][0] == "does not meet yet")
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, {"tb_built": 150, "tb_empty": 29, "tb_fb_error": 1}, GOOD_STEP)       # 179 of 180 attempted = 99.4%
        check("rule item 1 meets just above 99%", verdicts(tmp)[1][0] == "meets")
    # item 1 from the counters: the denominator is the attempted coin-minutes, not minutes run
    def item1(counts, minutes=673.0, coins=None):
        from collections import Counter
        dq = {"total": {"counts": Counter(counts), "minutes": minutes, "data_n": 0, "data_median": None,
                        "data_max": None, "data_le20": 0}}
        r = ps.tb_rule_rows(dq, {"errors": 0}, [], coins or list(ps.TB_DEFAULT_COINS), None)[1][0]
        return r[1], r[2]
    v, ver = item1({"tb_built": 3960})
    check("item 1 overcount case: 3,960 built with 673 minutes reads 100.00% and meets",
          v.startswith("100.00% (3,960 verified of 3,960 attempted coin-minutes: built 3,960, verified empty 0; "
                       "fallbacks: unverified 0, error 0, budget 0, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC)")
          and ver == "meets" and "against the rule" not in v and "differs" not in v, (v, ver))
    v, ver = item1({"tb_built": 990, "tb_fb_unverified": 6, "tb_fb_budget": 4})
    check("item 1 fallbacks count: 990 of 1,000 is 99.00% and meets", v.startswith("99.00% (990 verified of 1,000 attempted")
          and "unverified 6, error 0, budget 4, rate limit 0" in v and ver == "meets", (v, ver))
    v, ver = item1({"tb_built": 990, "tb_fb_unverified": 6, "tb_fb_budget": 4, "tb_fb_error": 1})
    check("item 1 one more fallback is below 99% and does not meet", ver == "does not meet yet" and v.startswith("98.90%"), (v, ver))
    v, ver = item1({"tb_built": 5000, "tb_fb_limited": 51})
    check("item 1 boundary is exact", ver == "does not meet yet", (v, ver))
    v, ver = item1({"tb_built": 500, "tb_empty": 490, "tb_fb_error": 10})
    check("item 1 counts tb_empty as verified", v.startswith("99.00% (990 verified of 1,000") and "verified empty 490" in v
          and ver == "meets", (v, ver))
    v, ver = item1({"rows_open": 3})
    check("item 1 with nothing attempted", v == "no trades pass counted yet" and ver == "does not meet yet", (v, ver))
    v, ver = item1({"tb_built": 3960}, coins=["BTC", "ETH"])
    check("item 1 differing list appends the note", v.endswith("listed coins: BTC, ETH); the configured list differs from the rule's six coins")
          and ver == "meets", (v, ver))
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



def t18_tests():
    full = "0123456789abcdef0123456789abcdef01234567"
    counts = {"tb_built": 538, "tb_empty": 2, "rows_open": 5, "tb_pending": 54, "tb_replaced": 3, "tb_replaced_diff": 1,
              "tb_dropped": 2}
    step = {"data": [14.0, 15.0]}
    n = 10
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, step, n=n)                      # third book: median 14.0 s, six coins
        t18 = [{"ts": iso(T(0)), "kind": "backfill"}] + [hb(T(0, 30 * k), dict(counts), dict(step)) for k in range(1, n + 1)]
        fills = [entry(iso(T(1)), 4, 1000), entry(iso(T(1, 1)), 4, 1000)]
        t18 += fills
        write(tmp, "paper_spot_t18", sorted(t18, key=lambda e: e["ts"]))
        with open(os.path.join(tmp, "paper_spot_t18", "CODE"), "w") as f:
            f.write(f"code_ref: refs/heads/x\ncode_commit: {full}\nutc: 2026-11-11T13:00\ncode_branch_hint: owner/t18\n")
        # one first-bid fill in the third book, one minute from the fourth book's
        with open(os.path.join(tmp, "paper_spot_tb", "events.jsonl"), "a") as f:
            f.write(json.dumps(entry(iso(T(1, 1)), 4, 1000)) + "\n")
        text = ps.build_report(tmp, NOW)
        check("t18: in the top table", "| Spot T18 (all coins on trades) |" in text.split("## Running time")[0])
        run = text.split("## Running time")[1].split("##")[0]
        check("t18: in running time", "| Spot T18 (all coins on trades) |" in run)
        check("t18: in the summary", text.count("Spot T18 (all coins on trades)") >= 5, text.count("Spot T18 (all coins on trades)"))
        dqsec = text.split("## Data quality")[1].split("## Fourth book")[0]
        check("t18: own data quality subsection with the new counters", "### Spot T18 (all coins on trades)" in dqsec
              and "tb_pending 540" in dqsec and "tb_replaced 30" in dqsec and "tb_dropped 20" in dqsec, dqsec[-800:])
        check("t18: comparison section ends with the registered sentence", "## Fourth book against the third book" in text
              and "This comparison is for the record. The registered read is in reports/owner/bar_source_prereg.md." in text)
        cmp_ = text.split("## Fourth book against the third book")[1].split("## Rule progress")[0]
        check("t18: comparison table and overlap", "| Measure | Spot TB | Spot T18 | T18 minus TB |" in cmp_
              and "| First-bid fills in both books | 1 |" in cmp_ and "| Only in the fourth book | 1 |" in cmp_, cmp_)
        sec = text.split("## Rule progress for the fourth book")[1].split("## Perp books")[0]
        check("t18: CODE line", f"Engine commit: 0123456 (full hash {full}), recorded 2026-11-11T13:00 UTC." in sec, sec[:300])
        check("t18: minutes run and no items 6 or 7", "Real-time minutes run so far: 300." in sec and "| 6. " not in sec and "| 7. " not in sec, sec)
        check("t18: item 1 names 18 coins", "listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC)" in sec
              and "5,400 verified of 5,400 attempted" in sec and "differs from the rule" not in sec, sec)
        check("t18: item 3 bar is 15 s and 14.0 s meets", "3. Data step median 15 s or less" in sec
              and "| median 14.0 s of 10 heartbeats; maximum 20 s or less in 100.0% (largest 15.0 s) | meets |" in sec, sec)
        tbsec = text.split("## Three-day rule progress for the third book")[1].split("## Fourth book")[0]
        check("t18: the same heartbeats do not meet the third book's 13 s bar",
              "3. Data step median 13 s or less" in tbsec and "| median 14.0 s of 10 heartbeats; maximum 20 s or less in 100.0% (largest 15.0 s) | does not meet yet |" in tbsec, tbsec)
        check("t18: pending line", "Rows still built from trades 3 to 6 minutes on (tb_pending): 540 of 5,400 coin-minutes" in sec, sec)
        check("t18: replaced and dropped line", "Totals: tb_replaced 30, tb_replaced_diff 10, tb_dropped 20." in sec, sec)
        check("t18: item 5 uses the same denominator", "| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.926% (50 of 5,400 coin-minutes, 18 coins)" in sec, sec)
    # the third book's own item 3 and item 1 text did not change
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, GOOD_STEP, n=n)
        text = ps.build_report(tmp, NOW)
        check("t18 absent: no fourth-book heading, label or counter text", "Fourth book" not in text and "T18" not in text
              and "t18" not in text and "tb_pending" not in text and "bar_source_prereg" not in text)
    # CODE file missing, fourth book without a third book
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "paper_spot", [{"ts": iso(T(0)), "kind": "backfill"}])
        write(tmp, "paper_spot_t18", [{"ts": iso(T(0)), "kind": "backfill"}, hb(T(0, 30), {"tb_built": 540}, {"data": [1.0, 2.0]})])
        text = ps.build_report(tmp, NOW)
        check("t18 alone: report still made, no CODE noted", "Engine commit: not recorded" in text
              and "Both logs are needed for this comparison" in text.split("## Fourth book")[1], text[-1500:])


def section(text, title):
    """The text of the '## title' section, up to the next '## ' heading."""
    return text.split("## " + title + "\n", 1)[1].split("\n## ", 1)[0]


RULE_A_TITLE = "Spot book against forward rule A"
START_FILE = os.path.join("reports", "owner", "test_a_start.json")


def put_start(root, content):
    os.makedirs(os.path.join(root, "reports", "owner"), exist_ok=True)
    with open(os.path.join(root, START_FILE), "w") as f:
        f.write(content if isinstance(content, str) else json.dumps(content))


def split_book_root(tmp, start_day=8):
    """Main book with a start at Nov 8 00:00 UTC. Before: A-1/4 $3,000 (exit after the start, +30), A-2/4 $1,000 (exit -10),
    A-1/6 bought in two fills, $500 before and $1,500 after the start (exit +5), one error. After: B-1/4 $2,000 (exit +12),
    B-2/4 $4,000 (open), one error. Newest event Nov 9 12:00."""
    spot = [
        {"ts": "2026-11-07T00:00:00", "kind": "backfill", "minutes": 10, "coins": 18},
        entry("2026-11-07T02:00:00", 4, 3000, "A-1"),
        {"ts": "2026-11-07T07:00:00", "kind": "error", "error": "early failure"},
        entry("2026-11-07T10:00:00", 4, 1000, "A-2"),
        exit_("2026-11-07T12:00:00", 4, -10.0, "time", "A-2"),
        entry("2026-11-07T23:50:00", 6, 500, "A-1"),
        entry("2026-11-08T00:10:00", 6, 1500, "A-1"),
        exit_("2026-11-08T03:00:00", 4, 30.0, "tp", "A-1"),
        exit_("2026-11-08T04:00:00", 6, 5.0, "tp", "A-1"),
        entry("2026-11-08T06:00:00", 4, 2000, "B-1"),
        {"ts": "2026-11-08T07:00:00", "kind": "error", "error": "late failure"},
        exit_("2026-11-08T09:00:00", 4, 12.0, "tp", "B-1"),
        entry("2026-11-08T20:00:00", 4, 4000, "B-2"),
        {"ts": "2026-11-09T12:00:00", "kind": "heartbeat", "equity": 250000, "committed": 1000, "free": 1000},
    ]
    write(tmp, "paper_spot", spot)
    write(tmp, "paper_spot_w2", [{"ts": "2026-11-07T01:00:00", "kind": "backfill"},
                                 entry("2026-11-07T03:00:00", 4, 1000, "W-1"),
                                 exit_("2026-11-07T05:00:00", 4, 3.0, "tp", "W-1"),
                                 {"ts": "2026-11-09T11:00:00", "kind": "heartbeat", "equity": 250003}])
    write(tmp, "paper", [{"ts": "2026-11-09T10:00:00", "kind": "heartbeat", "equity": 10000}])


def test_a_start_tests():
    start = "2026-11-08T00:00:00Z"
    with tempfile.TemporaryDirectory() as tmp:
        split_book_root(tmp)
        plain = ps.build_report(tmp, NOW)
        # no file: the same text as with an empty reports folder, and no trace of the feature
        os.makedirs(os.path.join(tmp, "reports", "owner"))
        check("test A: no file, empty reports folder gives the same text", ps.build_report(tmp, NOW) == plain)
        check("test A: no file, no Counted-from line, no before block, no Summary sentence",
              "Counted from" not in plain and "kept apart" not in plain and "Rule A is counted from" not in plain
              and "could not be read" not in plain)
        # the no-file rule A table, row by row, from the synthetic events (2.5 days, 6 fills, $12,000, P&L 37, 2 errors)
        ra0 = section(plain, RULE_A_TITLE)
        rows0 = [l for l in ra0.split("Unexplained errors:")[0].splitlines() if l.startswith("| ")]
        want_rows = ["| Measure | So far |",
                     "| Days (calendar) | 2.5 of 21 |",
                     "| Days in real time | " + ps.NOT_DERIVABLE + " |",
                     "| Rungs | 6 of 60 |",
                     "| Rung fills a day (rule text: " + ps.RULE_A_RATE + ") | "
                     + f"{6 / (60 / 24):.2f} per calendar day; " + ps.NOT_DERIVABLE + " per running day |",
                     "| Mean net per dollar | " + ps.bp(1e4 * 37 / 12000) + " |",
                     "| Errors (total) | 2 |",
                     "| Explained | 0 |",
                     "| Unexplained | 2 |"]
        check("test A: no file, every row of the rule A table as computed by hand", rows0 == want_rows, rows0)
        check("test A: no file, unexplained errors listed (one each)",
              "| early failure | 1 |" in ra0 and "| late failure | 1 |" in ra0)
        check("test A: no file, status line CHECK (two unexplained errors)", "\nStatus: **CHECK**\n" in ra0)

        # file present
        put_start(tmp, {"start": start, "label": "release 3"})
        text = ps.build_report(tmp, NOW)
        ra = section(text, RULE_A_TITLE)
        check("test A: Counted-from line with label",
              "Counted from 2026-11-08 00:00 UTC (release 3): the main book's inputs changed then. The registered rule is "
              "counted again from that time (reports/owner/FORWARD_TESTS.md)." in ra, ra)
        check("test A: Summary sentence", "Rule A is counted from 2026-11-08 00:00 UTC; see the section below." in text)
        rows = {l.split(" | ")[0].lstrip("| "): l for l in ra.splitlines() if l.startswith("| ")}
        check("test A: rule table counts rungs from the start only (2 fills)", rows["Rungs"] == "| Rungs | 2 of 60 |", rows["Rungs"])
        check("test A: rule table days from the start to the newest event", rows["Days (calendar)"] == "| Days (calendar) | 1.5 of 21 |",
              rows["Days (calendar)"])
        check("test A: net per dollar of the later rungs only: 12 over 6000", rows["Mean net per dollar"] == "| Mean net per dollar | "
              + ps.bp(1e4 * 12 / 6000) + " |", rows["Mean net per dollar"])
        check("test A: later period's errors split", rows["Errors (total)"].endswith("| 1 |") and rows["Unexplained"].endswith("| 1 |")
              and "late failure" in ra and "early failure" not in ra.split("### Before")[0], ra)
        check("test A: status word from the later period (net above 0, one unexplained error)", "Status: **CHECK**" in ra)
        before = ra.split("### Before 2026-11-08 00:00 UTC, kept apart")[1]
        brow = {l.split(" | ")[0].lstrip("| "): l for l in before.splitlines() if l.startswith("| ")}
        check("test A: before block present", "### Before 2026-11-08 00:00 UTC, kept apart" in ra)
        check("test A: before days 1.0", any(k.startswith("Days") and l.split(" | ")[1].strip(" |") == "1.0" for k, l in brow.items()), brow)
        check("test A: before rungs: 4 fills, the two-fill rung counted once as a whole in the earlier period",
              brow["Rungs bought"].endswith("| 4 |"), brow["Rungs bought"])
        check("test A: before dollars 6,000 (3000+1000+500+1500)", brow["Dollars bought"].endswith("| " + ps.money(6000.0) + " |"),
              brow["Dollars bought"])
        nb = [l for k, l in brow.items() if k.startswith("Mean net")][0]
        check("test A: before net includes the exits after the start: (30-10+5) over 6000", nb.endswith("| " + ps.bp(1e4 * 25 / 6000) + " |"), nb)
        check("test A: before errors 1, unexplained 1", brow["Errors"].endswith("| 1 |") and brow["Unexplained"].endswith("| 1 |"))
        check("test A: the exit after the start belongs to the earlier rung, not the rule table (12 not 37)",
              ps.bp(1e4 * 37 / 12000) not in ra and ps.bp(1e4 * 30 / 3000) not in ra)
        whole = ps.stats(ps.load_book(tmp, "paper_spot"), 250000.0, True)
        sb = ps.split_book(ps.load_book(tmp, "paper_spot")["events"], ps.parse_ts(start))
        check("test A: the two periods add up to the whole log (fills, dollars, P&L, errors)",
              sb["before"]["fills"] + sb["after"]["fills"] == whole["fills"] == 6
              and abs(sb["before"]["bought"] + sb["after"]["bought"] - whole["bought"]) < 1e-9
              and abs(sb["before"]["pnl"] + sb["after"]["pnl"] - whole["pnl"]) < 1e-9
              and len(sb["before"]["errors"]) + len(sb["after"]["errors"]) == whole["errors"] and sb["untied"] == 0)
        # every other section equal
        sp_plain = [x for x in plain.split("\n## ")]
        sp_text = [x for x in text.split("\n## ")]
        diff = [i for i, (a, b) in enumerate(zip(sp_plain, sp_text)) if a != b]
        titles = [sp_plain[i].split("\n", 1)[0] for i in diff]
        check("test A: same sections in both reports", len(sp_plain) == len(sp_text), (len(sp_plain), len(sp_text)))
        check("test A: only the Summary and the rule A section differ", titles == ["Summary", RULE_A_TITLE], titles)
        check("test A: W2 section identical", section(text, "W2 against the main spot book") == section(plain, "W2 against the main spot book"))
        sentence = "Rule A is counted from 2026-11-08 00:00 UTC; see the section below."
        summ = section(text, "Summary").replace(sentence, "")
        check("test A: Summary numbers identical (only the sentence added)",
              " ".join(summ.split()) == " ".join(section(plain, "Summary").split()) and sentence in section(text, "Summary"))
        # no label: no parenthesis
        put_start(tmp, {"start": start})
        t2 = section(ps.build_report(tmp, NOW), RULE_A_TITLE)
        check("test A: no label, no parenthesis", "Counted from 2026-11-08 00:00 UTC: the main book's inputs" in t2, t2)
        # start forms: trailing Z, offset, naive
        for form in ("2026-11-08T00:00:00Z", "2026-11-08T02:00:00+02:00", "2026-11-07T19:00:00-05:00", "2026-11-08T00:00:00"):
            put_start(tmp, {"start": form, "label": "release 3"})
            check("test A: start form accepted: " + form, section(ps.build_report(tmp, NOW), RULE_A_TITLE) == ra)
        # a rung first bought before and again after the start is whole in the earlier period; moving start between the fills
        put_start(tmp, {"start": "2026-11-08T00:05:00Z"})
        t3 = section(ps.build_report(tmp, NOW), RULE_A_TITLE)
        check("test A: start between the two fills of A-1/6: both fills stay with the earlier period",
              "| Rungs | 2 of 60 |" in t3 and "| Rungs bought | 4 |" in t3, t3)
        # start later than the newest event
        put_start(tmp, {"start": "2026-11-20T00:00:00Z"})
        t4 = section(ps.build_report(tmp, NOW), RULE_A_TITLE)
        check("test A: start after the newest event: zero rungs, 0.0 days, NOT YET",
              "| Rungs | 0 of 60 |" in t4 and "| Days (calendar) | 0.0 of 21 |" in t4 and "Status: **NOT YET (too early)**" in t4, t4)
        check("test A: start after the newest event: before block holds the whole record (6 fills, $12,000, 2 errors)",
              "| Rungs bought | 6 |" in t4 and "| Dollars bought | " + ps.money(12000.0) + " |" in t4 and "| Errors | 2 |" in t4
              and "| Mean net per dollar (exits after the start included) | " + ps.bp(1e4 * 37 / 12000) + " |" in t4, t4)
        # start earlier than the first event: the whole record is the period, the before block is one line
        put_start(tmp, {"start": "2026-11-01T00:00:00Z"})
        t5 = section(ps.build_report(tmp, NOW), RULE_A_TITLE)
        check("test A: start before the first event: one-line before block",
              "### Before 2026-11-01 00:00 UTC, kept apart\n\nThe book has no events before this time, so there is no earlier record.\n"
              in t5 and "| Measure | Before |" not in t5, t5)
        plain_tab = [l for l in section(plain, RULE_A_TITLE).splitlines() if l.startswith("| ")]
        t5_tab = [l for l in t5.splitlines() if l.startswith("| ")]
        check("test A: start before the first event: the table equals the whole-log table", plain_tab == t5_tab, (plain_tab, t5_tab))
        # unreadable file: same report plus one line at the top of the rule A section
        heading = "## " + RULE_A_TITLE + "\n\n"
        line = "reports/owner/test_a_start.json could not be read; rule A is shown on the whole log.\n\n"
        want = plain.replace(heading, heading + line, 1)
        for name, content in (("bad JSON", "{not json"), ("start missing", '{"label": "x"}'),
                              ("start not a time", '{"start": "later"}'), ("start not text", '{"start": 5}'),
                              ("not an object", "[1, 2]"), ("empty file", "")):
            put_start(tmp, content)
            got = ps.build_report(tmp, NOW)
            check("test A: unreadable file (" + name + "): the no-file report plus one line", got == want)
        check("test A: the added line is the first line of the section",
              section(want, RULE_A_TITLE).lstrip().startswith(line.strip()))
        os.remove(os.path.join(tmp, START_FILE))
        os.mkdir(os.path.join(tmp, START_FILE))
        check("test A: a directory in place of the file counts as unreadable", ps.build_report(tmp, NOW) == want)
        os.rmdir(os.path.join(tmp, START_FILE))
    # an exit that matches no entry is counted in the period of its own time and reported
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "paper_spot", [entry("2026-11-07T02:00:00", 4, 1000, "A-1"),
                                  exit_("2026-11-07T03:00:00", 4, 5.0, "tp", "A-1"),
                                  exit_("2026-11-08T03:00:00", 4, 7.0, "tp", "Z-9"),
                                  exit_("2026-11-07T04:00:00", 4, 1.0, "tp", "Z-8")])
        put_start(tmp, {"start": "2026-11-08T00:00:00Z"})
        ra = section(ps.build_report(tmp, NOW), RULE_A_TITLE)
        check("test A: untied exits counted by their own time and reported",
              "2 exit event(s) match no entry fill" in ra and "| Mean net per dollar (exits after the start included) | "
              + ps.bp(1e4 * 6 / 1000) + " |" in ra, ra)
    # the status word: 21 days and 60 rungs since the start
    with tempfile.TemporaryDirectory() as tmp:
        def long_book(extra_error_after=False):
            ev = [{"ts": "2026-11-01T00:00:00", "kind": "backfill"},
                  {"ts": "2026-11-02T00:00:00", "kind": "error", "error": "old trouble"},
                  entry("2026-11-03T00:00:00", 4, 1000, "OLD-1")]
            for i in range(60):
                t = datetime(2026, 11, 10, 2, tzinfo=timezone.utc) + timedelta(hours=i)
                ev += [entry(iso(t), 4, 1000, f"N-{i}"), exit_(iso(t + timedelta(hours=1)), 4, 2.0, "tp", f"N-{i}")]
            if extra_error_after:
                ev.append({"ts": "2026-11-20T00:00:00", "kind": "error", "error": "new trouble"})
            ev.append({"ts": "2026-12-01T00:00:00", "kind": "heartbeat", "equity": 250100})
            ev.sort(key=lambda e: e["ts"])
            write(tmp, "paper_spot", ev)
        put_start(tmp, {"start": "2026-11-10T00:00:00Z"})
        long_book()
        now2 = datetime(2026, 12, 1, 1, tzinfo=timezone.utc)
        ra = section(ps.build_report(tmp, now2), RULE_A_TITLE)
        check("test A: 21 days, 60 rungs, net above 0, earlier unexplained error: ON TRACK",
              "| Days (calendar) | 21.0 of 21 |" in ra and "| Rungs | 60 of 60 |" in ra and "Status: **ON TRACK**" in ra
              and "| Unexplained | 0 |" in ra, ra)
        os.remove(os.path.join(tmp, START_FILE))
        check("test A: the same book on the whole log is CHECK (the earlier error counts)",
              "Status: **CHECK**" in section(ps.build_report(tmp, now2), RULE_A_TITLE))
        put_start(tmp, {"start": "2026-11-10T00:00:00Z"})
        long_book(extra_error_after=True)
        ra = section(ps.build_report(tmp, now2), RULE_A_TITLE)
        check("test A: an unexplained error after the start: CHECK", "Status: **CHECK**" in ra and "new trouble" in ra, ra)


def ended_book_tests():
    late = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)          # days after the third book's last event
    n = 10
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, GOOD_STEP, n=n)                      # third book newest event Nov 7, 05:00
        write(tmp, "paper_spot_t18", [{"ts": iso(T(0)), "kind": "backfill"}] + [hb(T(0, 30 * k), {"tb_built": 540}, {"data": [14.0, 15.0]}) for k in range(1, n + 1)])
        check("ended: the constant marks the third book", ps.ENDED == {"tb": "2026-11-16"})
        text = ps.build_report(tmp, late)
        top = [l for l in text.split("## Running time")[0].splitlines() if l.startswith("| Spot TB")]
        check("ended: top row says ended with its newest event, no STALE", len(top) == 1 and "| ended |" in top[0]
              and "2026-11-07 05:00 UTC" in top[0] and "STALE" not in top[0], top)
        check("ended: the other books are still flagged STALE", "| Spot (main) | 2026-11-07 05:00 UTC" in text
              and "| STALE |" in text.split("## Running time")[0])
        sinceline = [l for l in text.split("Time since the last event, not counted above:")[1].splitlines()[:1]][0]
        check("ended: left out of the time since the last event", "Spot TB" not in sinceline and "Spot (main)" in sinceline, sinceline)
        line = "The third book ended on 2026-11-16; this section is the final record."
        for title in ("Third book against the main book", "Three-day rule progress for the third book",
                      "Fourth book against the third book"):
            body = section(text, title).strip("\n").splitlines()
            check("ended: section '%s' begins with the line" % title, body[:1] == [line], body[:2])
        check("ended: the fourth book's own sections have no such line", line not in section(text, "Rule progress for the fourth book"))
        check("ended: sections are kept", "| Measure | Spot (main) | Spot TB | TB minus main |" in text and "| 5. " in text)
        # the same log read before the date: not ended, so it is flagged as before
        text0 = ps.build_report(tmp, datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc))
        top0 = [l for l in text0.split("## Running time")[0].splitlines() if l.startswith("| Spot TB")]
        check("ended: before its date the book is read as any other", "STALE" in top0[0] and "ended" not in top0[0]
              and "ended on" not in text0, top0)
        # the date is the owner's to set
        old = dict(ps.ENDED)
        try:
            ps.ENDED["tb"] = "2026-12-01"
            text1 = ps.build_report(tmp, late)
            check("ended: a later date puts the book back to STALE until then", "ended on" not in text1 and "| ended |" not in text1)
        finally:
            ps.ENDED.clear()
            ps.ENDED.update(old)
        # a book with no data keeps its NO DATA row
        write(tmp, "paper_spot_tb", [])
        text2 = ps.build_report(tmp, late)
        check("ended: an empty ended book still says NO DATA", "NO DATA (empty log)" in text2)


def r5_books(tmp, r5, main, t18, r5_counts=None, r5_extra=(), n=10):
    """Fifth, main and fourth book with n heartbeats 30 minutes apart; r5, main and t18 are lists of data-step medians
    (None leaves that heartbeat out), one per heartbeat."""
    def book(meds, counts=None, extra=()):
        ev = [{"ts": iso(T(0)), "kind": "backfill"}]
        for k, m in enumerate(meds, 1):
            if m is not None:
                ev.append(hb(T(0, 30 * k), dict(counts or {}), {"data": [m, m + 1.0]}))
        return sorted(ev + list(extra), key=lambda e: e["ts"])
    write(tmp, "paper_spot", book(main))
    write(tmp, "paper_spot_t18", book(t18))
    write(tmp, "paper_spot_r5", book(r5, r5_counts, r5_extra))


def hrow(k, med, mx=None):
    return {"t": T(0, 30 * k), "data": (med, mx if mx is not None else med + 1.0), "counts": {}, "minutes": 30.0}


def mrow(k, minutes=30.0, **counts):
    return {"t": T(0, 30 * k), "data": None, "counts": counts, "minutes": minutes}


def r5_tests():
    F = ps.Fraction
    # ---- the report with the fifth book's folder missing: written as for any missing folder, nothing about r5
    with tempfile.TemporaryDirectory() as tmp:
        tb_books(tmp, GOOD_COUNTS, GOOD_STEP, n=10)
        write(tmp, "paper_spot_t18", [{"ts": iso(T(0)), "kind": "backfill"}, hb(T(0, 30), {"tb_built": 540}, {"data": [14.0, 15.0]})])
        text = ps.build_report(tmp, NOW)
        check("r5 missing: report written, no fifth-book row, section or label",
              "Spot R5" not in text and "fifth book" not in text.lower() and "paper_spot_r5" not in text
              and "# Paper trading status" in text)
        check("r5 missing: active_books omits it", [b[0] for b in ps.active_books(tmp)] == ["spot", "w2", "tb", "t18", "v1", "r2"])
    # ---- measure 1
    a = [hrow(k, m) for k, m in zip(range(1, 6), (10.0, 10.2, 10.3, 10.4, 10.1))]
    b = [hrow(k, m) for k, m in zip(range(1, 6), (11.0, 10.0, 10.5, 10.5, 12.0))]
    m1 = ps.measure1(a, b)
    check("measure 1: median of the fifth book's heartbeats", m1["median"] == F("10.2") and m1["n"] == 5, m1)
    check("measure 1: paired medians over the same timestamps", m1["pairs"] == 5 and m1["paired_fifth"] == F("10.2")
          and m1["paired_other"] == F("10.5"), m1)
    even = ps.measure1([hrow(1, 10.2), hrow(2, 10.4)], [])
    check("measure 1: even count takes the mean of the middle two, exactly", even["median"] == F("10.3") and even["median"] <= F("10.3"), even)
    # pairing by timestamp: heartbeats present in one book only are left out of the paired medians
    c = [hrow(k, m) for k, m in ((1, 50.0), (2, 10.0), (3, 10.0), (6, 99.0))]
    d = [hrow(k, m) for k, m in ((2, 12.0), (3, 11.0), (4, 1.0), (5, 1.0))]
    m1 = ps.measure1(c, d)
    check("measure 1: a half hour in one book only is left out of the pairs", m1["pairs"] == 2 and m1["paired_fifth"] == F(10)
          and m1["paired_other"] == F("11.5") and m1["median"] == F(30), m1)
    check("measure 1: no pairs", ps.measure1(c, [hrow(7, 1.0)])["pairs"] == 0 and ps.measure1([], [])["median"] is None)
    check("measure 1: heartbeats without a data step are not used", ps.measure1([mrow(1), hrow(2, 9.0)], [])["n"] == 1)
    # report: both halves, pairing, third column for information
    with tempfile.TemporaryDirectory() as tmp:
        r5_books(tmp, r5=[10.0, 10.2, 10.3, 10.4, 10.1, None, 10.0, 10.0, 10.0, 10.0],
                 main=[11.0, 10.0, 10.5, 10.5, 12.0, 1.0, None, 10.1, 10.1, 10.1],
                 t18=[9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0])
        text = ps.build_report(tmp, NOW)
        sec = section(text, "Rule progress for the fifth book")
        rows = {l.split(" | ")[0].lstrip("| "): l for l in sec.splitlines() if l.startswith("| (")}
        ra = [l for k, l in rows.items() if k.startswith("(a)")][0]
        rb = [l for k, l in rows.items() if k.startswith("(b)")][0]
        check("r5 report: (a) is now the pairs: none yet, does not meet", ra.startswith("| (a) Pairs that count") and "0 pairs (8 needed)" in ra
              and ra.endswith("| does not meet yet |") and "No pairs yet." in sec, ra)
        rep10 = [l for l in sec.splitlines() if l.startswith("| Reported, decides nothing")][0]
        check("r5 report: the fifth book's own median against 10.3 s is reported and decides nothing",
              "10.00 s over 9 heartbeats" in rep10 and "10.3 s" in rep10 and rep10.endswith("| reported only |"), rep10)
        check("r5 report: (b) paired over 8 half hours, fifth no higher meets",
              "fifth 10.05 s, main 10.30 s, 8 half hours" in rb and rb.endswith("| meets |"), rb)
        check("r5 report: information line against the fourth book", "For information: against the fourth book" in sec
              and "fifth 10.00 s, fourth 9.00 s, 9 half hours" in sec and "not part of the rule" in sec, sec[:1500])
        check("r5 report: progress-only line names part3_rule.py", "progress only" in sec and "scripts/owner/bar_source/part3_rule.py" in sec)
    with tempfile.TemporaryDirectory() as tmp:
        r5_books(tmp, r5=[10.31] * 10, main=[10.4] * 10, t18=[10.0] * 10)
        sec = section(ps.build_report(tmp, NOW), "Rule progress for the fifth book")
        check("r5 report: 10.31 s no longer fails anything by itself; (b) meets against a higher main median",
              [l for l in sec.splitlines() if l.startswith("| Reported")][0].endswith("| reported only |")
              and [l for l in sec.splitlines() if l.startswith("| (b)")][0].endswith("| meets |"), sec[:900])
    with tempfile.TemporaryDirectory() as tmp:
        r5_books(tmp, r5=[10.0] * 10, main=[9.9] * 10, t18=[10.0] * 10)
        sec = section(ps.build_report(tmp, NOW), "Rule progress for the fifth book")
        check("r5 report: (b) fails when the fifth's paired median is higher",
              [l for l in sec.splitlines() if l.startswith("| (b)")][0].endswith("| does not meet yet |"))
    # ---- measure 1 (a): the pairs
    def pair_file(tmp, name, start, order, r3, bd, counts=True, why=None, steps=31):
        d = os.path.join(tmp, "reports", "owner", "step_pairs")
        os.makedirs(d, exist_ok=True)
        runs = [dict(inputs="release3", data_end_median_text=r3, steps_timed=steps),
                dict(inputs="build", data_end_median_text=bd, steps_timed=steps)]
        if order == "ba":
            runs.reverse()
        with open(os.path.join(d, name), "w") as f:
            json.dump(dict(utc_start=start, order=order, counts=counts, why_not=why, runs=runs), f)
    with tempfile.TemporaryDirectory() as tmp:
        r5_books(tmp, r5=[10.0] * 10, main=[10.0] * 10, t18=[10.0] * 10)
        pair_file(tmp, "pair_20261108T0005Z.json", "2026-11-08T00:05:10Z", "ab", "14.88", "9.70")
        pair_file(tmp, "pair_20261108T0605Z.json", "2026-11-08T06:05:10Z", "ba", "11.37", "11.37")
        pair_file(tmp, "pair_20261108T1205Z.json", "2026-11-08T12:05:10Z", "ab", "10.00", "10.01", counts=False, why="the build run met a refusal")
        pair_file(tmp, "pair_20261111T0005Z.json", "2026-11-11T00:05:10Z", "ab", "10.00", "30.00")     # after the report's time
        open(os.path.join(tmp, "reports", "owner", "step_pairs", "pair_bad.json"), "w").write("{not json")
        sec = section(ps.build_report(tmp, NOW), "Rule progress for the fifth book")
        check("pairs: each pair's start, order, both medians and difference are listed",
              "| 2026-11-08 00:05 UTC | ab | 14.88 s | 9.70 s | -5.18 s | counts |" in sec
              and "| 2026-11-08 06:05 UTC | ba | 11.37 s | 11.37 s | 0.00 s | counts |" in sec, sec[:2500])
        check("pairs: a pair that does not count says why; a bad file does not count",
              "| 2026-11-08 12:05 UTC | ab | 10.00 s | 10.01 s | 0.01 s | does not count: the build run met a refusal |" in sec
              and "does not count: file could not be read" in sec)
        a_row = [l for l in sec.splitlines() if l.startswith("| (a) Pairs that count")][0]
        check("pairs: count and median of the pairs that count, two of eight needed: does not meet",
              "| 2 pairs (8 needed); median -2.59 s; must be at or below 0.00 s | does not meet yet |" in a_row, a_row)
    with tempfile.TemporaryDirectory() as tmp:
        r5_books(tmp, r5=[10.0] * 10, main=[10.0] * 10, t18=[10.0] * 10)
        for i in range(8):
            pair_file(tmp, "pair_%d.json" % i, "2026-11-08T%02d:05:10Z" % i, "ab" if i % 2 == 0 else "ba", "10.00", "10.00" if i < 7 else "9.00")
        a_row = [l for l in section(ps.build_report(tmp, NOW), "Rule progress for the fifth book").splitlines() if l.startswith("| (a) Pairs that count")][0]
        check("pairs: eight pairs with median exactly 0.00 meet", "8 pairs (8 needed); median 0.00 s" in a_row and a_row.endswith("| meets |"), a_row)
        pair_file(tmp, "pair_x.json", "2026-11-09T01:05:10Z", "ab", "10.00", "10.01")
        pair_file(tmp, "pair_y.json", "2026-11-09T02:05:10Z", "ab", "10.00", "10.01")
        pair_file(tmp, "pair_z.json", "2026-11-09T03:05:10Z", "ab", "10.00", "10.01")
        a_row = [l for l in section(ps.build_report(tmp, NOW), "Rule progress for the fifth book").splitlines() if l.startswith("| (a) Pairs that count")][0]
        check("pairs: 11 pairs (one at -1.00, seven at 0.00, three at +0.01): the median is 0.00 and meets", a_row.endswith("| meets |"), a_row)
    ps_pairs = ps.load_pairs(os.path.join(tempfile.gettempdir(), "no_such_folder_for_pairs"))
    check("pairs: a missing folder is no pairs", ps_pairs == [])
    # ---- item 3: only its second half
    with tempfile.TemporaryDirectory() as tmp:
        r5_books(tmp, r5=[16.0] * 10, main=[10.0] * 10, t18=[10.0] * 10, r5_counts={"tb_built": 540})
        sec = section(ps.build_report(tmp, NOW), "Rule progress for the fifth book")
        row = [l for l in sec.splitlines() if l.startswith("| 3. ")][0]
        check("r5 item 3: median 16 s does not fail it (the median is measure 1); 17 s maxima are within 20 s",
              row.startswith("| 3. Data step 30-minute maximum 20 s or less in 95% or more of heartbeats (the median is measure 1")
              and row.endswith("| meets |") and "median 16.0 s of 10 heartbeats" in row, row)
        check("r5 items 1 to 5 use 18 coins and the fourth book's wording for items 1, 2, 4 and 5",
              "listed coins: BTC, ETH" in sec and "| 1. Verified trades bar share" in sec and "| 5. Unconfirmed rows" in sec
              and "5,400 verified of 5,400 attempted" in sec, sec)
    with tempfile.TemporaryDirectory() as tmp:
        ev = [{"ts": iso(T(0)), "kind": "backfill"}] + [hb(T(0, 30 * k), {"tb_built": 540}, {"data": [5.0, 21.0 if k <= 2 else 6.0]}) for k in range(1, 41)]
        write(tmp, "paper_spot_r5", ev)
        sec = section(ps.build_report(tmp, NOW), "Rule progress for the fifth book")
        row = [l for l in sec.splitlines() if l.startswith("| 3. ")][0]
        check("r5 item 3: 38 of 40 heartbeats within 20 s (95.0%) meets, 37 would not",
              "maximum 20 s or less in 95.0% (largest 21.0 s)" in row and row.endswith("| meets |"), row)
        ev[1:3] = [hb(T(0, 30 * k), {"tb_built": 540}, {"data": [5.0, 21.0]}) for k in (1, 2)]
        ev[3] = hb(T(1, 30), {"tb_built": 540}, {"data": [5.0, 21.0]})
        write(tmp, "paper_spot_r5", ev)
        sec = section(ps.build_report(tmp, NOW), "Rule progress for the fifth book")
        row = [l for l in sec.splitlines() if l.startswith("| 3. ")][0]
        check("r5 item 3: 37 of 40 does not meet", "92.5%" in row and row.endswith("| does not meet yet |"), row)
    # the fourth book's item 3 is unchanged (median bar 15 s still applies)
    with tempfile.TemporaryDirectory() as tmp:
        r5_books(tmp, r5=[10.0] * 10, main=[10.0] * 10, t18=[16.0] * 10, r5_counts={"tb_built": 540})
        sec = section(ps.build_report(tmp, NOW), "Rule progress for the fourth book")
        row = [l for l in sec.splitlines() if l.startswith("| 3. ")][0]
        check("r5: the fourth book's item 3 keeps its median half", "Data step median 15 s or less" in row and row.endswith("| does not meet yet |"), row)

    # ---- measure 4
    def m4(rows, starts=()):
        return ps.measure4(rows, list(starts))
    r = m4([mrow(1, pre_fetched=99, pre_error=1)])
    check("measure 4: 1 failed of 100 requests is exactly 1%: meets", r["failed"] == 1 and r["requests"] == 100 and r["failed_ok"], r)
    r = m4([mrow(1, pre_fetched=98, pre_error=1)])
    check("measure 4: 1 failed of 99 requests is just over 1%: fails", not r["failed_ok"], r)
    r = m4([mrow(1, pre_fetched=100, pre_error=0)])
    check("measure 4: no failures meets", r["failed_ok"])
    r = m4([mrow(1, pre_fetched=0, pre_error=0, pre_missing=0)])
    check("measure 4: no requests at all is not met", not r["failed_ok"] and r["requests"] == 0)
    r = m4([mrow(1, minutes=50.0, pre_fetched=1, pre_missing=18)])
    check("measure 4: 18 in-step of 900 coin-minutes (50 minutes) is exactly 2%: meets", r["coin_minutes"] == 900 and r["in_step"] == 18 and r["in_step_ok"], r)
    r = m4([mrow(1, minutes=50.0, pre_fetched=1, pre_missing=10, pre_ondemand=9)])
    check("measure 4: pre_missing plus pre_ondemand 19 of 900 is just over: fails", r["in_step"] == 19 and not r["in_step_ok"], r)
    r = m4([mrow(1, minutes=50.0, pre_fetched=1, pre_missing=18, pre_ondemand=1)])
    check("measure 4: the 2% test uses both counters", not r["in_step_ok"])
    # the first step after each start
    r = m4([mrow(2, pre_fetched=10, pre_missing=25)], [T(0, 45)])
    check("measure 4: one start in the half hour leaves out 18", r["left_out"] == 18 and r["in_step"] == 7, r)
    r = m4([mrow(2, pre_fetched=10, pre_missing=40)], [T(0, 45), T(0, 50)])
    check("measure 4: two starts in the half hour leave out 36", r["left_out"] == 36 and r["in_step"] == 4, r)
    r = m4([mrow(2, pre_fetched=10, pre_missing=5)], [T(0, 45), T(0, 50)])
    check("measure 4: never below zero", r["left_out"] == 5 and r["in_step"] == 0, r)
    r = m4([mrow(2, pre_fetched=10, pre_missing=25, pre_ondemand=3)], [T(0, 45)])
    check("measure 4: only pre_missing is reduced, pre_ondemand counts in full", r["in_step"] == 10, r)
    r = m4([mrow(2, pre_fetched=10, pre_missing=25), mrow(3, pre_fetched=10, pre_missing=25)], [T(0, 45)])
    check("measure 4: a start counts only in its own half hour", r["left_out"] == 18 and r["in_step"] == 32, r)
    r = m4([mrow(2, pre_fetched=10, pre_missing=20), mrow(3, pre_fetched=10, pre_missing=20)], [T(1)])
    check("measure 4: a start exactly at a heartbeat belongs to that heartbeat, not the next",
          r["left_out"] == 18 and r["in_step"] == 22, r)
    r = m4([mrow(2, pre_fetched=10, pre_missing=20)], [T(0, 30)])
    check("measure 4: a start exactly at the previous heartbeat is outside the half hour", r["left_out"] == 0 and r["in_step"] == 20, r)
    # counters absent
    r = m4([mrow(1), mrow(2)])
    check("measure 4: counters absent from every heartbeat", r["present"] == [] and not r["failed_ok"] and not r["in_step_ok"], r)
    r = m4([mrow(1, pre_fetched=5), mrow(2)])
    check("measure 4: a counter in one heartbeat is present, the others count as 0", r["present"] == ["pre_fetched"] and r["requests"] == 5)
    r = m4([])
    check("measure 4: no heartbeats", r["beats"] == 0 and not r["failed_ok"] and not r["in_step_ok"])
    # starts from a log: the first stepped minute after a backfill
    ev = [{"ts": "2026-11-07T01:42:00", "kind": "backfill", "_t": T(1, 42)}, {"ts": "2026-11-07T01:42:30", "kind": "catch_up", "_t": T(1, 42)},
          {"ts": "x", "kind": "arm", "_t": T(1, 47)},
          {"ts": "2026-11-07T05:00:00", "kind": "backfill", "_t": T(5)}, {"ts": "x", "kind": "arm", "_t": T(5, 20)},
          {"ts": "2026-11-07T07:00:00", "kind": "backfill", "_t": T(7)}]
    check("startup_steps: first later event, else backfill plus 6 minutes", ps.startup_steps(ev) == [T(1, 47), T(5, 6), T(7, 6)], ps.startup_steps(ev))
    # report: measure 4 table
    with tempfile.TemporaryDirectory() as tmp:
        counts = {"pre_fetched": 100, "pre_error": 0, "pre_missing": 1, "pre_ondemand": 0, "step_candles": 30}
        r5_books(tmp, r5=[10.0] * 10, main=[10.0] * 10, t18=[10.0] * 10, r5_counts=counts)
        sec = section(ps.build_report(tmp, NOW), "Rule progress for the fifth book")
        t4 = sec.split("### Measure 4")[1]
        check("r5 report: measure 4 counters summed and shares (first step after the start left out)",
              "pre_fetched 1,000, pre_error 0, pre_missing 10, pre_ondemand 0, step_candles 300" in t4
              and "0 of 1,000 = 0.000%" in t4 and "9 of 5,400 = 0.167%" in t4, t4)
        check("r5 report: left out is stated", "1 left out, over 1 starts in the log" in t4, t4)
    with tempfile.TemporaryDirectory() as tmp:
        r5_books(tmp, r5=[10.0] * 10, main=[10.0] * 10, t18=[10.0] * 10)
        sec = section(ps.build_report(tmp, NOW), "Rule progress for the fifth book")
        check("r5 report: counters absent says so", "No heartbeat carries the counters pre_fetched" in sec.split("### Measure 4")[1])
    # fifth log empty (folder exists)
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "paper_spot", [{"ts": iso(T(0)), "kind": "backfill"}])
        write(tmp, "paper_spot_r5", [])
        text = ps.build_report(tmp, NOW)
        check("r5 empty log: report made, section says no log", "No fifth-book log to judge (empty)." in text)

    # ---- the fifth book against the fourth
    with tempfile.TemporaryDirectory() as tmp:
        r5_books(tmp, r5=[10.0] * 10, main=[10.0] * 10, t18=[10.0] * 10, r5_counts={"tb_built": 540})
        with open(os.path.join(tmp, "paper_spot_r5", "events.jsonl"), "a") as f:
            f.write(json.dumps(entry(iso(T(1, 1)), 4, 1000)) + "\n")
        with open(os.path.join(tmp, "paper_spot_t18", "events.jsonl"), "a") as f:
            f.write(json.dumps(entry(iso(T(1)), 4, 1000)) + "\n")
            f.write(json.dumps(entry(iso(T(2)), 4, 1000, "A-2")) + "\n")
        with open(os.path.join(tmp, "paper_spot_r5", "CODE"), "w") as f:
            f.write("code_ref: x\ncode_commit: abcdef0123456789abcdef0123456789abcdef01\nutc: 2026-11-17T01:00\n")
        text = ps.build_report(tmp, NOW)
        cmp_ = section(text, "Fifth book against the fourth book")
        check("r5 vs t18: same columns as the fourth against the third", "| Measure | Spot T18 | Spot R5 | R5 minus T18 |" in cmp_
              and "| Rung fills | 2 | 1 | -1 |" in cmp_ and "| First-bid fills in both books | 1 |" in cmp_
              and "| Only in the fourth book | 1 |" in cmp_ and "| Only in the fifth book | 0 |" in cmp_, cmp_)
        check("r5 vs t18: sits before the fifth book's rule section", text.index("## Fifth book against the fourth book")
              < text.index("## Rule progress for the fifth book"))
        check("r5 vs t18: no ended line, since the fourth book has not ended", "ended on" not in cmp_)
        check("r5: in the top table, running time, summary and data quality",
              "| Spot R5 (release 5 build) |" in text.split("## Running time")[0]
              and "| Spot R5 (release 5 build) |" in text.split("## Running time")[1].split("\n## ")[0]
              and "| Spot R5 (release 5 build) |" in section(text, "Summary")
              and "### Spot R5 (release 5 build)" in section(text, "Data quality"))
        check("r5: engine commit line", "Engine commit: abcdef0 (full hash abcdef0123456789abcdef0123456789abcdef01), recorded 2026-11-17T01:00 UTC." in section(text, "Rule progress for the fifth book"))
        check("r5: no at-sign in the report", chr(64) not in text)
    # the two counters that do not mean the same in the fifth book are left out there, with a note, and kept for the fourth
    with tempfile.TemporaryDirectory() as tmp:
        cnt = {"tb_built": 540, "tb_insert": 538, "tb_close_diff": 0, "tb_replaced": 3}
        r5_books(tmp, r5=[10.0] * 10, main=[10.0] * 10, t18=[10.0] * 10, r5_counts=cnt)
        with open(os.path.join(tmp, "paper_spot_t18", "events.jsonl"), "w") as f:
            for e in [{"ts": iso(T(0)), "kind": "backfill"}] + [hb(T(0, 30 * k), dict(cnt), {"data": [10.0, 11.0]}) for k in range(1, 11)]:
                f.write(json.dumps(e) + "\n")
        text = ps.build_report(tmp, NOW)
        dq = section(text, "Data quality")
        r5dq = dq.split("### Spot R5 (release 5 build)")[1].split("\n### ")[0]
        t18dq = dq.split("### Spot T18 (all coins on trades)")[1].split("\n### ")[0]
        check("r5 counters: tb_insert and tb_close_diff are not printed for the fifth book",
              "tb_insert" not in r5dq.split("Left out for this book")[0] and "tb_close_diff" not in r5dq.split("Left out for this book")[0]
              and "tb_built 5,400" in r5dq and "tb_replaced 30" in r5dq, r5dq)
        check("r5 counters: the fifth book says they are not comparable",
              "Left out for this book: tb_insert, tb_close_diff." in r5dq and "not comparable" in r5dq, r5dq)
        check("r5 counters: the fourth book still shows them", "tb_insert 5,380" in t18dq and "Left out" not in t18dq, t18dq)
        rest = text.replace(r5dq, "")
        check("r5 counters: nowhere else in the fifth book's sections",
              "tb_insert" not in section(text, "Rule progress for the fifth book") and "tb_close_diff" not in section(text, "Rule progress for the fifth book")
              and "tb_insert" not in section(text, "Fifth book against the fourth book"))
    # fifth book present, fourth missing: no comparison section, the rule section still shown
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "paper_spot", [{"ts": iso(T(0)), "kind": "backfill"}])
        write(tmp, "paper_spot_r5", [{"ts": iso(T(0)), "kind": "backfill"}, hb(T(0, 30), {"tb_built": 540}, {"data": [1.0, 2.0]})])
        text = ps.build_report(tmp, NOW)
        check("r5 alone: no comparison section, rule section shown", "Fifth book against the fourth book" not in text
              and "## Rule progress for the fifth book" in text and "against the fourth book, same way" not in text)


def pairs_extend_tests():
    from fractions import Fraction
    t0 = datetime(2026, 11, 20, 0, 30, tzinfo=timezone.utc)
    end = datetime(2026, 11, 23, 0, 29, tzinfo=timezone.utc)

    def pp(diff, start, counts=True, name=None):
        return dict(file=name or "pair_%s_%s.json" % (start.strftime("%d%H%M"), diff), start=start, order="ab", counts=counts,
                    why=None if counts else "x", release3="10.00", build="10.00", diff=Fraction(diff))

    def inside(diffs):
        return [pp(d, t0 + timedelta(hours=i + 1)) for i, d in enumerate(diffs)]

    def after(diffs, first_hours=1, counts=True):
        return [pp(d, end + timedelta(hours=first_hours + i), counts) for i, d in enumerate(diffs)]

    def pm(pairs, **kw):
        return ps.pairs_measure(pairs, t0, end, **kw)
    # 8 or more in the period: nothing added, later pairs ignored
    r = pm(inside(["0"] * 8) + after(["9", "9", "9"]), extend=True)
    check("extend: 8 in the period, nothing added, later pairs ignored", r["n"] == 8 and r["in_period"] == 8 and r["added"] == 0
          and r["complete"] and r["met"] and r["median"] == 0 and r["last_start"] is None, r)
    r = pm(inside(["-1"] * 9) + after(["9"] * 5), extend=True)
    check("extend: 9 in the period are all used (more than 8 is fine)", r["n"] == 9 and r["added"] == 0 and r["met"], r)
    # 7 in the period and 3 after: exactly the oldest later one
    later = after(["1", "5", "5"])
    r = pm(inside(["0"] * 7) + later, extend=True)
    check("extend: 7 in the period and 3 after: one added, the oldest; the median's sign comes from it",
          r["n"] == 8 and r["in_period"] == 7 and r["added"] == 1 and r["complete"] and r["median"] == 0 and r["met"]
          and r["last_start"] == later[0]["start"] and r["used"][-1] is later[0] and later[1] not in r["used"] and later[2] not in r["used"], r)
    base7 = ["-1"] * 3 + ["0"] + ["1"] * 3
    r = pm(inside(base7) + after(["-1", "9", "9", "9"]), extend=True)
    check("extend: the unused later pairs would turn the median positive (1/2 on all ten) but are not read: median -1/2, met",
          r["n"] == 8 and r["added"] == 1 and r["median"] == Fraction(-1, 2) and r["met"]
          and pm(inside(base7) + after(["-1", "9", "9", "9"]), extend=False)["median"] == 0, r)
    r = pm(inside(["0"] * 4 + ["1"] * 3) + after(["1", "-9", "-9"]), extend=True)
    check("extend: 4 at 0, 3 at 1 and the added 1: median 1/2 is above zero, not met",
          r["n"] == 8 and r["median"] == Fraction(1, 2) and not r["met"] and r["complete"], r)
    # 5 in the period and 2 after: 7 used, not complete
    r = pm(inside(["-1"] * 5) + after(["-1", "-1"]), extend=True)
    check("extend: 5 in the period and 2 after: 7 used, not complete, not met", r["n"] == 7 and r["in_period"] == 5 and r["added"] == 2
          and not r["complete"] and not r["enough"] and not r["met"], r)
    # a later pair that does not count is skipped
    bad = after(["-1"], counts=False)
    good = after(["-1", "-1"], first_hours=2)
    r = pm(inside(["-1"] * 7) + bad + good, extend=True)
    check("extend: a later pair that does not count is skipped and the next counting one is taken",
          r["n"] == 8 and r["added"] == 1 and r["used"][-1] is good[0] and bad[0] not in r["used"], r)
    # input order does not matter: oldest first
    r = pm(inside(["-1"] * 6) + list(reversed(after(["-1", "5", "5"]))), extend=True)
    check("extend: later pairs are taken oldest first whatever the input order", r["added"] == 2 and r["median"] == -1
          and r["last_start"] == end + timedelta(hours=2), r)
    # the boundary: end + 1 minute is the first minute after the period
    p_in = pp("0", end + timedelta(seconds=59), name="pair_in.json")
    p_out = pp("0", end + timedelta(minutes=1), name="pair_out.json")
    r = pm(inside(["0"] * 6) + [p_in, p_out], extend=True)
    check("extend: a start in the period's last minute is in the period, one a minute after is added, none in both",
          r["in_period"] == 7 and r["added"] == 1 and p_in in r["used"] and p_out in r["used"] and r["n"] == 8, r)
    r = pm(inside(["0"] * 7) + [p_in, p_out], extend=True)
    check("extend: with the last-minute pair the period has 8: the pair a minute later is not used",
          r["in_period"] == 8 and r["added"] == 0 and p_out not in r["used"], r)
    r = pm(inside(["0"] * 6) + [p_in, p_out], extend=False)
    check("extend=False: the pair a minute after is not used", r["n"] == 7 and p_out not in r["used"] and r["added"] == 0, r)
    # now cuts the added pairs
    later = after(["-1", "-1", "-1"])
    r = pm(inside(["-1"] * 5) + later, now=later[1]["start"], extend=True)
    check("extend: now cuts the added pairs (a pair after now is not used)", r["n"] == 7 and r["added"] == 2 and later[2] not in r["used"]
          and not r["complete"], r)
    r = pm(inside(["-1"] * 7) + later, now=later[0]["start"] - timedelta(minutes=1), extend=True)
    check("extend: now before every later pair adds none", r["n"] == 7 and r["added"] == 0, r)
    # extend=False is today's result on the same inputs
    pairs = inside(["-1"] * 7) + after(["-1", "5", "5"])
    r0, r1 = pm(pairs), pm(pairs, extend=False)
    check("extend=False: today's result (7 used, later pairs left out)", r0["n"] == r1["n"] == 7 and not r1["enough"] and not r1["met"]
          and r1["median"] == -1 and r1["used"] == pairs[:7] and r1["added"] == 0 and r1["in_period"] == 7 and not r1["complete"], r1)
    r = ps.pairs_measure(pairs, t0, None, extend=True)
    check("extend without an end changes nothing", r["n"] == 10 and r["added"] == 0, r)
    r = pm(inside(["-1"] * 7) + after(["-1"]), extend=True, min_pairs=3)
    check("extend: min_pairs is respected (7 in the period, 3 needed: nothing added)", r["n"] == 7 and r["added"] == 0 and r["complete"], r)


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
    restart_gap_tests()
    data_quality_tests()
    third_book_tests()
    t18_tests()
    ended_book_tests()
    r5_tests()
    test_a_start_tests()
    pairs_extend_tests()

    print("\n" + ("all passed" if not FAILS else f"{len(FAILS)} failed: {FAILS}"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
