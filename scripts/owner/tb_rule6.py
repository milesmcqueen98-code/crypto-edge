#!/usr/bin/env python3
"""Apply item 6 of the third paper book's rule to the collector's daily table.

Run: python scripts/owner/tb_rule6.py --daily input_checks_daily.csv --start 2026-11-11T01:50 --end 2026-11-14T01:50

The rule text, verbatim:

  "(6) on the collector's record for the same days, against the final candle (the candle probe's
  measures 2 and 3): (a) BTC's trades bar is materially off in at most 1% of minutes, over the days
  together; (b) for every other listed coin, on every day, the trades bar is materially off less
  often and exactly equal more often than that coin's own first-seen candle. A day is a UTC date
  with at least 12 hours inside the test period and at least 720 compared minutes for the coin; at
  least two such days are needed, and item 6 waits for them if the collector has fewer. [...] On a
  fail of items 1 to 5 or of 6(a), the fault is fixed and the three days start again. A coin that
  fails 6(b) is taken off the list at release 3 without restarting the days; it stays on the candle
  path, which is what the books do today."

Input: input_checks_daily.csv, one row per coin and UTC date. Columns used: coin, day,
tbar_compared, tbar_exact, tbar_material, first_compared, first_exact, first_material. The tbar
columns describe the trades bar against the final candle; the first columns describe the candle as
first seen against the same final candle. Compared is a count of minutes; exact and material are
percentages of the compared minutes. Other columns are ignored.

Semantics, in brief:
  1. Hours inside: overlap of [D 00:00 UTC, D+1 00:00 UTC) with the period [start, end).
     All times are UTC (timezone-aware); the machine's local time zone is never used.
  2. A date is counted for a coin when hours inside >= 12 and the coin has a row with
     tbar_compared >= 720 and, for every coin except BTC, first_compared >= 720 as well.
     BTC needs only tbar_compared, so empty first_* cells do not stop a BTC date.
  3. A date with >= 12 hours inside that fails the minutes test is "left out", with its counts.
     A date with fewer than 12 hours inside is "outside the period".
  4. A coin needs at least two counted dates; with fewer its verdict is WAIT.
  5. 6(a), BTC: material minutes per counted date = round(tbar_material / 100 * tbar_compared) to
     the nearest integer (halves go up). Pooled share = sum of material / sum of tbar_compared.
     PASS when material_total * 100 <= compared_total (integers), else FAIL.
  6. 6(b), every other listed coin: a counted date passes when tbar_material < first_material and
     tbar_exact > first_exact, both strict. PASS when every counted date passes, else FAIL; a FAIL
     names the failing dates and the measure that failed.
  7. A listed coin with no rows at all is WAIT, with a note.
  8. Overall: FAIL if 6(a) is FAIL. Otherwise WAIT if 6(a) is WAIT or any listed coin is WAIT.
     Otherwise PASS; if some coins failed 6(b), they leave the list at release 3 and the rest stay.
  9. Rows that cannot be parsed are skipped and listed. Exit code 0 for any readable run; exit code
     2 only for unusable arguments (missing file, bad timestamps, end not after start).

Notes on choices the rule leaves open (kept minimal): a second row for the same coin and date is
skipped and listed; a date that passes the minutes test but lacks a value the rule needs is shown as
"left out: missing values"; if BTC is not in --coins, 6(a) is shown as not applicable and does not
affect the overall verdict.
"""
import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DEFAULT_COINS = "BTC,ETH,SOL,XRP,LTC,ZEC"
MIN_HOURS = timedelta(hours=12)
MIN_MINUTES = 720
MIN_DAYS = 2
UTC = timezone.utc
FIELDS = ["tbar_compared", "tbar_exact", "tbar_material", "first_compared", "first_exact", "first_material"]


def parse_utc(text):
    """Parse a timestamp as UTC. No zone means UTC; another zone is converted to UTC."""
    t = text.strip()
    if t.endswith(("Z", "z")):
        t = t[:-1] + "+00:00"
    d = datetime.fromisoformat(t)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(UTC)


def hours_inside(day, start, end):
    """Overlap of the UTC date `day` (a date) with [start, end), as a timedelta."""
    d0 = datetime(day.year, day.month, day.day, tzinfo=UTC)
    lo, hi = max(d0, start), min(d0 + timedelta(days=1), end)
    return max(hi - lo, timedelta(0))


def num(text):
    """Decimal from a cell; None for an empty cell; ValueError for anything else."""
    if text is None or text.strip() == "":
        return None
    try:
        v = Decimal(text.strip())
    except InvalidOperation:
        raise ValueError(f"not a number: {text.strip()!r}")
    if not v.is_finite():
        raise ValueError(f"not a number: {text.strip()!r}")
    return v


def read_rows(path):
    """Return (rows, skipped). rows maps (COIN, date) to a dict of Decimal-or-None values."""
    rows, skipped = {}, []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in ["coin", "day"] + FIELDS if c not in header]
        reader.fieldnames = header
        for rec in reader:
            line = reader.line_num
            try:
                if missing:
                    raise ValueError("missing column(s): " + ", ".join(missing))
                coin = (rec.get("coin") or "").strip().upper()
                if not coin:
                    raise ValueError("no coin")
                day = datetime.strptime((rec.get("day") or "").strip(), "%Y-%m-%d").date()
                vals = {k: num(rec.get(k)) for k in FIELDS}
                if vals["tbar_compared"] is None:
                    raise ValueError("tbar_compared is empty")
                if (coin, day) in rows:
                    raise ValueError("second row for the same coin and date")
            except (ValueError, TypeError) as e:
                skipped.append((line, str(e)))
                continue
            rows[(coin, day)] = vals
    return rows, skipped


def material_minutes(pct, compared):
    return int((pct / 100 * compared).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def evaluate(rows, coins, start, end):
    """Apply item 6. Returns a dict with per-date lines, per-coin verdicts and the overall verdict."""
    days = []
    d = start.date()
    while datetime(d.year, d.month, d.day, tzinfo=UTC) < end:
        days.append(d)
        d += timedelta(days=1)
    lines, coin_res = [], {}
    for coin in coins:
        is_btc = coin == "BTC"
        have_rows = any(c == coin for (c, _d) in rows)
        counted = []
        for day in days:
            hin = hours_inside(day, start, end)
            row = rows.get((coin, day))
            line = {"coin": coin, "day": day, "hours": hin.total_seconds() / 3600.0, "row": row,
                    "status": "", "result": "n.a."}
            if hin <= timedelta(0):
                continue
            if hin < MIN_HOURS:
                line["status"] = "outside the period"
            elif row is None:
                line["status"] = "left out: no row"
            else:
                need = ["tbar_compared"] if is_btc else ["tbar_compared", "first_compared"]
                small = [k for k in need if row[k] is None or row[k] < MIN_MINUTES]
                if small:
                    line["status"] = "left out: too few minutes"
                else:
                    needed = ["tbar_material"] if is_btc else ["tbar_material", "tbar_exact", "first_material", "first_exact"]
                    if any(row[k] is None for k in needed):
                        line["status"] = "left out: missing values"
                    else:
                        line["status"] = "counted"
                        counted.append(line)
            lines.append(line)
        res = {"coin": coin, "counted": len(counted), "have_rows": have_rows}
        if is_btc:
            comp = sum(int(l["row"]["tbar_compared"]) for l in counted)
            mat = sum(material_minutes(l["row"]["tbar_material"], l["row"]["tbar_compared"]) for l in counted)
            res.update(compared=comp, material=mat)
            if len(counted) < MIN_DAYS:
                res["verdict"] = "WAIT"
            else:
                res["verdict"] = "PASS" if mat * 100 <= comp else "FAIL"
        else:
            fails = []
            for l in counted:
                r = l["row"]
                bad = []
                if not r["tbar_material"] < r["first_material"]:
                    bad.append("material")
                if not r["tbar_exact"] > r["first_exact"]:
                    bad.append("exact")
                if bad:
                    l["result"] = "fail: " + " and ".join(bad)
                    fails.append((l["day"], bad))
                else:
                    l["result"] = "pass"
            res["fails"] = fails
            if len(counted) < MIN_DAYS:
                res["verdict"] = "WAIT"
            else:
                res["verdict"] = "FAIL" if fails else "PASS"
        coin_res[coin] = res
    a = coin_res.get("BTC")
    others = [c for c in coins if c != "BTC"]
    b_failed = [c for c in others if coin_res[c]["verdict"] == "FAIL"]
    waiting = [c for c in coins if coin_res[c]["verdict"] == "WAIT"]
    if a is not None and a["verdict"] == "FAIL":
        overall = "FAIL"
    elif waiting:
        overall = "WAIT"
    else:
        overall = "PASS"
    return {"lines": lines, "coins": coin_res, "overall": overall, "b_failed": b_failed, "waiting": waiting}


def cell(v):
    return "-" if v is None else format(v, "f")


def render(result, coins, start, end, skipped):
    fmt = "%Y-%m-%d %H:%M"
    out = [f"# Item 6 of the third paper book's rule",
           "",
           f"Period (UTC): {start.strftime(fmt)} to {end.strftime(fmt)}. Listed coins: {', '.join(coins)}.",
           "",
           "| Coin | Date (UTC) | Hours inside | Tbar compared | Tbar material % | First-seen material % "
           "| Tbar exact % | First-seen exact % | Status | Result |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for l in result["lines"]:
        r = l["row"] or {}
        out.append("| " + " | ".join([
            l["coin"], l["day"].isoformat(), f"{l['hours']:.1f}", cell(r.get("tbar_compared")),
            cell(r.get("tbar_material")), cell(r.get("first_material")), cell(r.get("tbar_exact")),
            cell(r.get("first_exact")), l["status"], l["result"]]) + " |")
    out += ["", "For BTC the result is n.a. on each date because 6(a) pools the dates.", ""]
    cr = result["coins"]
    if "BTC" in cr:
        a = cr["BTC"]
        if not a["have_rows"]:
            out.append("6(a) BTC: WAIT. The table has no rows for BTC.")
        elif a["verdict"] == "WAIT":
            out.append(f"6(a) BTC: WAIT. {a['counted']} counted date(s); at least {MIN_DAYS} are needed.")
        else:
            share = Decimal(a["material"]) * 100 / Decimal(a["compared"])
            out.append(f"6(a) BTC: {a['verdict']}. Materially off in {share:.2f}% of minutes over the counted days "
                       f"({a['material']:,} of {a['compared']:,} minutes); the limit is 1%.")
    else:
        out.append("6(a): not applicable, BTC is not in the listed coins.")
    for c in coins:
        if c == "BTC":
            continue
        r = cr[c]
        if not r["have_rows"]:
            out.append(f"6(b) {c}: WAIT. The table has no rows for {c}.")
        elif r["verdict"] == "WAIT":
            out.append(f"6(b) {c}: WAIT. {r['counted']} counted date(s); at least {MIN_DAYS} are needed.")
        elif r["verdict"] == "PASS":
            out.append(f"6(b) {c}: PASS. Better on both measures on all {r['counted']} counted dates.")
        else:
            det = "; ".join(f"{d.isoformat()} ({' and '.join(m)})" for d, m in r["fails"])
            out.append(f"6(b) {c}: FAIL. Not better than its first-seen candle on: {det}.")
    out += ["", f"Item 6 overall: {result['overall']}."]
    if result["overall"] == "PASS" and result["b_failed"]:
        out.append(f"Failed 6(b): {', '.join(result['b_failed'])}. These coins leave the list at release 3 "
                   "and stay on the candle path; the days do not restart. The other coins stay.")
    if result["overall"] == "WAIT":
        out.append("Waiting on: " + ", ".join(
            (["BTC (6(a))"] if "BTC" in cr and cr["BTC"]["verdict"] == "WAIT" else [])
            + [c for c in result["waiting"] if c != "BTC"]) + ".")
    if skipped:
        out += ["", f"Skipped rows ({len(skipped)}):"]
        out += [f"- line {n}: {why}" for n, why in skipped[:10]]
        if len(skipped) > 10:
            out.append(f"- and {len(skipped) - 10} more")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Apply item 6 of the third paper book's rule to the daily table.")
    ap.add_argument("--daily", required=True, help="input_checks_daily.csv")
    ap.add_argument("--start", required=True, help="test period start, UTC, e.g. 2026-11-11T01:50")
    ap.add_argument("--end", required=True, help="test period end (exclusive), UTC")
    ap.add_argument("--coins", default=DEFAULT_COINS, help="listed coins, comma separated")
    ap.add_argument("--out", help="also write the markdown report here")
    args = ap.parse_args(argv)

    def bad(msg):
        print("error: " + msg, file=sys.stderr)
        return 2

    try:
        start, end = parse_utc(args.start), parse_utc(args.end)
    except ValueError as e:
        return bad(f"cannot read the start or end time: {e}")
    if end <= start:
        return bad("end must be after start")
    coins = []
    for c in args.coins.split(","):
        c = c.strip().upper()
        if c and c not in coins:
            coins.append(c)
    if not coins:
        return bad("no coins listed")
    if not os.path.isfile(args.daily):
        return bad(f"no such file: {args.daily}")
    try:
        rows, skipped = read_rows(args.daily)
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        return bad(f"cannot read {args.daily}: {e}")
    text = render(evaluate(rows, coins, start, end), coins, start, end, skipped)
    sys.stdout.write(text)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            return bad(f"cannot write {args.out}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
