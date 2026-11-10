#!/usr/bin/env python3
"""Tests for paper_status.py on small synthetic logs. Run: python scripts/owner/test_paper_status.py"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

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
        check("perp table has fills per day", "Fills per day" in text)
        v1 = ps.stats(ps.load_book(tmp, "paper"), 10000.0, False)
        check("perp days run", v1["days"] is not None and abs(v1["days"] - 2 / 24) < 1e-9, v1["days"])

    print("\n" + ("all passed" if not FAILS else f"{len(FAILS)} failed: {FAILS}"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
