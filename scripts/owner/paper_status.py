#!/usr/bin/env python3
"""Status report for the four paper-trading logs.

Usage: python scripts/owner/paper_status.py [REPO_ROOT] [--now ISO_TIME]

Reads paper_spot/, paper_spot_w2/, paper/ and paper_v2/ (events.jsonl and state.json) under REPO_ROOT (default: the
repo this file lives in) and writes reports/owner/PAPER_STATUS.md. Standard library only, no network. A missing
folder, an empty log, a truncated last line or an event kind it has not seen never stops the report.
"""
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

STALE_HOURS = 8.0
RULE_A = ("Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors "
          "and mean net per dollar is above 0.")
LAST_LINE = ("Paper fills assume the research's capture share; they check the machinery and the fill frequency, "
             "not whether real orders fill.")
ERR_CHARS = 160

# key, folder, label, starting capital, spot-style book (rungs, ladders) or perp book
BOOKS = [
    ("spot", "paper_spot", "Spot (main)", 250000.0, True),
    ("w2", "paper_spot_w2", "Spot W2", 250000.0, True),
    ("v1", "paper", "Perp v1 (control)", 10000.0, False),
    ("r2", "paper_v2", "Perp R2-08", 10000.0, False),
]

KNOWN_KINDS = {
    "backfill", "arm", "heartbeat", "fill_entry", "fill_exit", "ladder_close", "cash_short", "error", "catch_up",
    "bid", "cancel", "rung", "adv", "halt", "warning", "reject", "skip", "cancel_all", "fee_tier",
}


# ---------------------------------------------------------------- small helpers
def num(x):
    """A finite float, or None."""
    try:
        if isinstance(x, bool) or x is None:
            return None
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def parse_ts(s):
    """A timezone-aware UTC datetime from an ISO string (naive means UTC), or None."""
    if not isinstance(s, str) or not s:
        return None
    try:
        t = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def clean(s):
    """Text safe for a table cell: one line, no pipes, no at-sign."""
    s = " ".join(str(s).split())
    return s.replace("|", "/").replace(chr(64), " at ")


def money(x):
    if x is None:
        return "n/a"
    sign = "-" if x < 0 else ""
    a = abs(x)
    return f"{sign}${a:,.0f}" if a >= 1000 else f"{sign}${a:,.2f}"


def bp(x):
    return "n/a" if x is None else f"{x:,.1f} bp"


def pct(x, signed=True):
    if x is None:
        return "n/a"
    return f"{x:+.2f}%" if signed else f"{x:.2f}%"


def fmt_t(t):
    return "none" if t is None else t.strftime("%Y-%m-%d %H:%M UTC")


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(clean(c) for c in r) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------- loading
def load_book(root, folder):
    """Returns dict: status (ok, missing, empty), events (dicts with _t), bad (unreadable lines), state."""
    d = os.path.join(root, folder)
    res = {"status": "ok", "events": [], "bad": 0, "state": None, "note": None}
    if not os.path.isdir(d):
        res["status"] = "missing"
        return res
    path = os.path.join(d, "events.jsonl")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    res["bad"] += 1
                    continue
                if not isinstance(o, dict):
                    res["bad"] += 1
                    continue
                o["_t"] = parse_ts(o.get("ts"))
                res["events"].append(o)
    except OSError:
        res["status"] = "missing"
        return res
    if not res["events"]:
        res["status"] = "empty"
    try:
        with open(os.path.join(d, "state.json"), encoding="utf-8", errors="replace") as f:
            st = json.load(f)
        if isinstance(st, dict):
            res["state"] = st
    except (OSError, ValueError):
        pass
    return res


# ---------------------------------------------------------------- statistics
def stats(book, capital, spot_style):
    ev = book["events"]
    s = {"status": book["status"], "bad": book["bad"], "capital": capital, "n": len(ev)}
    times = [e["_t"] for e in ev if e["_t"] is not None]
    s["first"] = min(times) if times else None
    s["newest"] = max(times) if times else None
    s["days"] = (s["newest"] - s["first"]).total_seconds() / 86400 if times else None
    s["kinds"] = Counter(str(e.get("kind")) for e in ev)
    s["unknown"] = {k: n for k, n in s["kinds"].items() if k not in KNOWN_KINDS}

    entries = [e for e in ev if e.get("kind") == "fill_entry"]
    exits = [e for e in ev if e.get("kind") == "fill_exit"]
    closes = [e for e in ev if e.get("kind") == "ladder_close"]
    errors = [e for e in ev if e.get("kind") == "error"]
    beats = [e for e in ev if e.get("kind") == "heartbeat"]
    shorts = [e for e in ev if e.get("kind") == "cash_short"]

    s["fills"] = len(entries)
    usds = [num(e.get("usd")) for e in entries]
    known = [u for u in usds if u is not None]
    s["bought"] = sum(known) if (known or not entries) else None
    pnls = [num(e.get("pnl")) or 0.0 for e in exits]
    s["pnl"] = sum(pnls)
    s["net_bp"] = 1e4 * s["pnl"] / s["bought"] if s["bought"] else None
    s["exits"] = len(exits)
    s["tp"] = sum(1 for e in exits if e.get("exit") == "tp")
    s["time"] = sum(1 for e in exits if e.get("exit") == "time")
    s["other_exit"] = s["exits"] - s["tp"] - s["time"]
    nb = [num(e.get("net_bp")) for e in exits]
    nb = [v for v in nb if v is not None]
    s["mean_net_bp"] = sum(nb) / len(nb) if nb else None
    s["ladders"] = len(closes)
    s["ladders_win"] = sum(1 for e in closes if (num(e.get("pnl")) or 0.0) > 0)
    s["errors"] = len(errors)
    msgs = Counter()
    for e in errors:
        m = clean(e.get("error", e.get("message", "(no message)")))
        msgs[m[:ERR_CHARS]] += 1
    s["error_msgs"] = msgs
    s["bids"] = s["kinds"].get("bid", 0)
    s["cancels"] = s["kinds"].get("cancel", 0)
    s["halts"] = s["kinds"].get("halt", 0)
    s["warnings"] = s["kinds"].get("warning", 0)

    # equity: the book's own state when it has one, else the latest event that carries one
    eq = num((book["state"] or {}).get("equity"))
    if eq is None:
        for e in reversed(ev):
            v = num(e.get("equity"))
            if v is not None and e.get("kind") in ("heartbeat", "fill_exit"):
                eq = v
                break
    s["equity"] = eq
    s["change_pct"] = 100.0 * (eq / capital - 1.0) if eq is not None and capital else None

    if spot_style:
        by_rung = defaultdict(lambda: {"fills": 0, "bought": 0.0, "exits": 0, "pnl": 0.0})
        for rung in (4, 6, 8):
            by_rung[rung]
        for e in entries:
            r = num(e.get("rung"))
            r = int(r) if r is not None else -1
            by_rung[r]["fills"] += 1
            by_rung[r]["bought"] += num(e.get("usd")) or 0.0
        for e in exits:
            r = num(e.get("rung"))
            r = int(r) if r is not None else -1
            by_rung[r]["exits"] += 1
            by_rung[r]["pnl"] += num(e.get("pnl")) or 0.0
        s["by_rung"] = dict(sorted(by_rung.items()))

        daily = defaultdict(float)
        for e in exits:
            if e["_t"] is not None:
                daily[e["_t"].date()] += num(e.get("pnl")) or 0.0
        s["daily"] = dict(daily)
        losses = {d: v for d, v in daily.items() if v < 0}
        s["worst_day"] = min(losses.items(), key=lambda kv: kv[1]) if losses else None

        s["shorts"] = len(shorts)
        want = [num(e.get("want")) for e in shorts]
        free = [num(e.get("free")) for e in shorts]
        want = [v for v in want if v is not None]
        free = [v for v in free if v is not None]
        s["want_total"] = sum(want)
        s["want_avg"] = sum(want) / len(want) if want else None
        s["free_avg"] = sum(free) / len(free) if free else None

        shares = []
        for e in beats:
            c, q = num(e.get("committed")), num(e.get("equity"))
            if c is not None and q:
                shares.append(c / q)
        s["commit_share"] = 100.0 * sum(shares) / len(shares) if shares else None
        s["commit_n"] = len(shares)
    return s


def rule_a(s):
    days, rungs = s["days"] or 0.0, s["fills"]
    net = s["net_bp"]
    if s["errors"] > 0 or (net is not None and net <= 0):
        return "CHECK"
    if days >= 21 and rungs >= 60 and net is not None:
        return "ON TRACK"
    return "NOT YET (too early)"


# ---------------------------------------------------------------- report
def na(s, v):
    return "no data" if s["status"] != "ok" else v


def summary_row(label, s, spot_style):
    if s["status"] != "ok":
        return [label, s["status"] + " log"] + ["-"] * 8
    exits = f"{s['tp']} / {s['time']}" + (f" (+{s['other_exit']} other)" if s["other_exit"] else "")
    lad = f"{s['ladders']} ({s['ladders_win']} made money)" if spot_style else "-"
    return [label, f"{s['days']:.1f}" if s["days"] is not None else "n/a", money(s["equity"]), pct(s["change_pct"]),
            str(s["fills"]), money(s["bought"]) if s["bought"] is not None else "n/a (not logged)", bp(s["net_bp"]),
            exits, lad, str(s["errors"])]


def build_report(root, now):
    loaded, st = {}, {}
    notes = []
    for key, folder, label, cap, spot_style in BOOKS:
        try:
            loaded[key] = load_book(root, folder)
            st[key] = stats(loaded[key], cap, spot_style)
        except Exception as exc:  # never fail on odd data
            loaded[key] = {"status": "empty", "events": [], "bad": 0, "state": None}
            st[key] = stats(loaded[key], cap, spot_style)
            notes.append(f"{label}: could not be fully read ({clean(type(exc).__name__)}); shown as empty.")
    labels = {k: lab for k, _, lab, _, _ in BOOKS}
    kinds_spot = {k: spot for k, _, _, _, spot in BOOKS}

    L = ["# Paper trading status", "", f"Report made {fmt_t(now)}.", ""]
    rows = []
    for key, folder, label, _, _ in BOOKS:
        s = st[key]
        if s["newest"] is None:
            rows.append([label, "none", "-", "NO DATA (" + ("folder missing" if s["status"] == "missing" else "empty log") + ")"])
            continue
        age = (now - s["newest"]).total_seconds() / 3600
        flag = "STALE" if age > STALE_HOURS else "ok"
        rows.append([label, fmt_t(s["newest"]), f"{age:.1f} h ago", flag])
    L += [table(["Book", "Newest event", "Age", "Flag"], rows), "",
          f"A book is flagged STALE when its newest event is more than {STALE_HOURS:g} hours old.", ""]

    # summary
    L += ["## Summary", ""]
    hdr = ["Book", "Days", "Equity", "Change", "Rung fills", "Dollars bought", "Net per dollar", "Exit events TP / time",
           "Ladders closed", "Errors"]
    L += [table(hdr, [summary_row(labels[k], st[k], kinds_spot[k]) for k in st]), "",
          "Days run from the first to the newest event. Change is against starting capital ($250,000 spot, $10,000 perp). "
          "Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought "
          "with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.", ""]

    # rule A
    sp = st["spot"]
    L += ["## Spot book against forward rule A", "", f"> {RULE_A}", ""]
    if sp["status"] != "ok":
        L += [f"No spot log to judge ({sp['status']}). Status: NOT YET (too early).", ""]
    else:
        L += [table(["Measure", "So far"], [
            ["Days", f"{sp['days']:.1f} of 21"],
            ["Rungs", f"{sp['fills']} of 60"],
            ["Mean net per dollar", bp(sp["net_bp"])],
            ["Errors", str(sp["errors"])]]), ""]
        if sp["error_msgs"]:
            L += [table(["Error message (first 160 characters)", "Count"],
                        [[m, str(n)] for m, n in sp["error_msgs"].most_common()]), ""]
        L += [f"Status: **{rule_a(sp)}**", "",
              "CHECK means errors are present or net is at or below 0. NOT YET means the 3 weeks and 60 rungs are not "
              "reached. ON TRACK means both are reached with no errors and net above 0. The owner declares any pass.", ""]

    # spot detail
    L += ["## Spot book detail", ""]
    if sp["status"] != "ok":
        L += ["No spot log.", ""]
    else:
        rr = []
        for r, v in sp["by_rung"].items():
            net = 1e4 * v["pnl"] / v["bought"] if v["bought"] else None
            rr.append(["unknown" if r < 0 else str(r), str(v["fills"]), money(v["bought"]), str(v["exits"]),
                       money(v["pnl"]), bp(net)])
        L += ["Fills and net per dollar by rung:", "",
              table(["Rung", "Fills", "Dollars bought", "Exit events", "Exit P&L", "Net per dollar"], rr), ""]
        end = (sp["newest"] or now).date()
        days = [end - timedelta(days=i) for i in range(13, -1, -1)]
        L += ["P&L of exits by day, last 14 days:", "",
              table(["Day (UTC)", "Exit P&L"], [[d.isoformat(), money(sp["daily"].get(d, 0.0))] for d in days]), ""]
        if sp["shorts"]:
            L += [f"Cash shortfalls: {sp['shorts']}. Wanted {money(sp['want_total'])} in total "
                  f"(average {money(sp['want_avg'])}) against an average of {money(sp['free_avg'])} free.", ""]
        else:
            L += ["Cash shortfalls: 0.", ""]
        L += [("Share of capital held by resting bids (committed over equity, mean of "
               f"{sp['commit_n']} heartbeats): {pct(sp['commit_share'], False)}." if sp["commit_share"] is not None
               else "Share of capital held by resting bids: n/a (no heartbeats)."), ""]
        if sp["worst_day"]:
            d, v = sp["worst_day"]
            L += [f"Largest single-day loss so far: {money(v)} on {d.isoformat()}.", ""]
        else:
            L += ["Largest single-day loss so far: none (no losing day yet).", ""]

    # W2
    w2 = st["w2"]
    L += ["## W2 against the main spot book", ""]
    if sp["status"] != "ok" or w2["status"] != "ok":
        L += ["Both spot logs are needed for this comparison; one is missing or empty.", ""]
    else:
        def diff(a, b, f):
            return "n/a" if a is None or b is None else f(b - a)
        cmp_rows = [
            ["Days", f"{sp['days']:.1f}", f"{w2['days']:.1f}", f"{w2['days'] - sp['days']:+.1f}"],
            ["Equity", money(sp["equity"]), money(w2["equity"]), diff(sp["equity"], w2["equity"], money)],
            ["Change", pct(sp["change_pct"]), pct(w2["change_pct"]),
             diff(sp["change_pct"], w2["change_pct"], lambda v: f"{v:+.2f} pp")],
            ["Rung fills", str(sp["fills"]), str(w2["fills"]), f"{w2['fills'] - sp['fills']:+d}"],
            ["Dollars bought", money(sp["bought"]), money(w2["bought"]), diff(sp["bought"], w2["bought"], money)],
            ["Net per dollar", bp(sp["net_bp"]), bp(w2["net_bp"]),
             diff(sp["net_bp"], w2["net_bp"], lambda v: f"{v:+.1f} bp")],
            ["Exit events TP / time", f"{sp['tp']} / {sp['time']}", f"{w2['tp']} / {w2['time']}", ""],
            ["Ladders closed (made money)", f"{sp['ladders']} ({sp['ladders_win']})",
             f"{w2['ladders']} ({w2['ladders_win']})", ""],
            ["Errors", str(sp["errors"]), str(w2["errors"]), f"{w2['errors'] - sp['errors']:+d}"],
        ]
        L += [table(["Measure", "Spot (main)", "W2", "W2 minus main"], cmp_rows), ""]
        if sp["first"] and w2["first"] and sp["first"] != w2["first"]:
            gap = abs((w2["first"] - sp["first"]).total_seconds()) / 3600
            L += [f"W2 started {gap:.1f} hours {'after' if w2['first'] > sp['first'] else 'before'} the main book, "
                  "so the windows are not identical.", ""]
        eqd = diff(sp["equity"], w2["equity"], money)
        L += [f"Difference in equity (W2 minus main): {eqd}.", "",
              "A few days and a few dozen fills cannot separate the two weightings; a gap this size is within "
              "what chance alone produces.", ""]

    # perps
    L += ["## Perp books", ""]
    prow = []
    for key in ("v1", "r2"):
        s = st[key]
        if s["status"] != "ok":
            prow.append([labels[key], s["status"] + " log", "-", "-", "-", "-"])
        else:
            prow.append([labels[key], str(s["fills"]), bp(s["mean_net_bp"]), money(s["equity"]),
                         pct(s["change_pct"]), f"{s['bids']:,}"])
    L += [table(["Book", "Fills", "Net per trade", "Equity", "Change", "Bids placed"], prow), "",
          "Net per trade is the mean of the net bp of each exit.", ""]

    # data notes
    for key, _, label, _, _ in BOOKS:
        s = st[key]
        if s["status"] == "missing":
            notes.append(f"{label}: folder or events file not found.")
        elif s["status"] == "empty":
            notes.append(f"{label}: events log is empty.")
        if s["bad"]:
            notes.append(f"{label}: {s['bad']} unreadable line(s) skipped (a truncated last line is normal if the log was being written).")
        if s["unknown"]:
            notes.append(f"{label}: event kinds not seen before: " + ", ".join(f"{clean(k)} ({n})" for k, n in sorted(s["unknown"].items())) + ".")
        if s["halts"] or s["warnings"]:
            notes.append(f"{label}: {s['halts']} halt and {s['warnings']} warning events in the log.")
    if notes:
        L += ["## Data notes", ""] + [f"- {n}" for n in notes] + [""]

    L += [LAST_LINE, ""]
    return "\n".join(L)


def main(argv):
    args = list(argv)
    now = datetime.now(timezone.utc)
    if "--now" in args:
        i = args.index("--now")
        t = parse_ts(args[i + 1]) if i + 1 < len(args) else None
        if t is not None:
            now = t
        del args[i:i + 2]
    root = args[0] if args else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    text = build_report(root, now)
    out = os.path.join(root, "reports", "owner", "PAPER_STATUS.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
