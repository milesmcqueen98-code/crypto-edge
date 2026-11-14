"""Step probe: summary of one or more runs (calls.csv of probe.py).

Run: python scripts/owner/step_probe/summarize.py --runs DIR1 [DIR2 ...] --out DIR
Writes bins.csv (counts, read by rule.py), durations.csv and summary.md.

Definitions (the plan's, reports/owner/step_probe_prereg.md):
- A request is a row of calls.csv. Bins are by the pass and by sent_s, the second after q at which the request was
  sent: early [1, 2) [2, 3) [3, 4) [4, 6); standard [6, 10); anything else of those two passes is bin "other".
- The bins hold ALL requests sent in that second, BTC included. The BTC lines (bin "BTC") are in addition: all of
  BTC's requests of the pass, whatever second they were sent at (BTC is the first request of each pass).
- The reference for (run, coin, minute) is the reference-pass row for it if it is verified; else the minute has none.
- requests, verified (accepted by the engine's check), with_ref (verified rows whose minute has a reference),
  no_ref (verified rows whose minute has none), equal (of with_ref: open, high, low and close exactly equal to the
  reference's, or no trades in both), volume_equal (of equal: volume within 1e-9 relative).
- V = verified / requests; E = equal / with_ref.
"""
import argparse
import csv
import os
import sys

import numpy as np

EARLY_BINS = [(1.0, 2.0, "[1,2)"), (2.0, 3.0, "[2,3)"), (3.0, 4.0, "[3,4)"), (4.0, 6.0, "[4,6)")]
STD_BINS = [(6.0, 10.0, "[6,10)")]
PASSES = ("early", "standard", "reference")
REASONS = ["stale_first_page", "incomplete", "page_cap", "deadline", "malformed", "error", "unspecified", "other_reason"]
COUNTS = ["requests", "verified", "with_ref", "no_ref", "equal", "volume_equal"]
BAR = ("open", "high", "low", "close")
VOL_REL = 1e-9


def bins_for(pname):
    return (EARLY_BINS if pname == "early" else STD_BINS)


def bin_of(pname, sent_s):
    if sent_s is None:
        return "other"
    for lo, hi, name in bins_for(pname):
        if lo <= sent_s < hi:
            return name
    return "other"


def num(x):
    return float(x) if x not in ("", None) else None


def read_calls(d):
    with open(os.path.join(d, "calls.csv"), newline="") as f:
        return list(csv.DictReader(f))


def run_names(dirs):
    names, seen = [], {}
    for d in dirs:
        b = os.path.basename(os.path.normpath(d)) or d
        seen[b] = seen.get(b, 0) + 1
        names.append(b if seen[b] == 1 else f"{b}#{seen[b]}")
    return names


def has_bar(r):
    return r["open"] != ""


def bars_equal(a, b):
    """Open, high, low and close exactly equal, or no trades in both."""
    if not has_bar(a) and not has_bar(b):
        return True
    if has_bar(a) != has_bar(b):
        return False
    return all(float(a[k]) == float(b[k]) for k in BAR)


def volume_equal(a, b):
    if not has_bar(a) and not has_bar(b):
        return True
    x, y = float(a["volume"]), float(b["volume"])
    return abs(x - y) <= VOL_REL * max(abs(x), abs(y))


def reason_of(r):
    s = r["reason"] or ("error" if r["error"] else "unspecified")
    return s if s in REASONS else "other_reason"


def zero():
    d = {k: 0 for k in COUNTS}
    d.update({"r_" + k: 0 for k in REASONS})
    return d


def line_keys(pname):
    return [b[2] for b in bins_for(pname)] + ["other", "BTC"]


def count_run(rows):
    """Counts per (pass, bin) for one run, for early and standard."""
    ref = {}
    for r in rows:
        if r["pass"] == "reference" and r["verified"] == "1":
            ref.setdefault((r["coin"], r["minute"]), r)
    out = {(p, b): zero() for p in ("early", "standard") for b in line_keys(p)}
    for r in rows:
        p = r["pass"]
        if p not in ("early", "standard"):
            continue
        keys = [(p, bin_of(p, num(r["sent_s"])))]
        if r["coin"] == "BTC":
            keys.append((p, "BTC"))
        for k in keys:
            c = out[k]
            c["requests"] += 1
            if r["verified"] == "1":
                c["verified"] += 1
                rf = ref.get((r["coin"], r["minute"]))
                if rf is None:
                    c["no_ref"] += 1
                else:
                    c["with_ref"] += 1
                    if bars_equal(r, rf):
                        c["equal"] += 1
                        if volume_equal(r, rf):
                            c["volume_equal"] += 1
            else:
                c["r_" + reason_of(r)] += 1
    return out


def share(num_, den):
    return None if den == 0 else num_ / den


def bins_table(per_run):
    """Rows for bins.csv: per run and "all" (the sum of the runs)."""
    names = [n for n, _ in per_run]
    total = {k: zero() for k in per_run[0][1]} if per_run else {}
    for _, cnt in per_run:
        for k, c in cnt.items():
            for f, v in c.items():
                total[k][f] += v
    out = []
    for name, cnt in per_run + [("all", total)]:
        for p in ("early", "standard"):
            for b in line_keys(p):
                c = cnt[(p, b)]
                row = {"run": name, "pass": p, "bin": b}
                row.update(c)
                row["V"] = share(c["verified"], c["requests"])
                row["E"] = share(c["equal"], c["with_ref"])
                out.append(row)
    return out, names


BIN_COLUMNS = ["run", "pass", "bin"] + COUNTS + ["r_" + k for k in REASONS] + ["V", "E"]


def write_bins(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=BIN_COLUMNS)
        w.writeheader()
        for r in rows:
            r = dict(r)
            for k in ("V", "E"):
                r[k] = "" if r[k] is None else repr(r[k])
            w.writerow(r)


def pct(x, nd=2):
    return "n/a" if x is None else f"{100 * x:.{nd}f}%"


def pctl(vals, q):
    return float(np.percentile(vals, q))


def duration_rows(runs):
    """durations.csv rows: kind coin (by coin and pass, per run and all) and pass_time (per run and all)."""
    out = []

    def add(kind, run, pname, key, vals):
        if vals:
            out.append({"kind": kind, "run": run, "pass": pname, "key": key, "count": len(vals),
                        "median_s": repr(float(np.median(vals))), "p90_s": repr(pctl(vals, 90))})
    allcoin, alltime = {}, {}
    for name, rows in runs:
        coin, ptime = {}, {}
        for r in rows:
            d = num(r["dur_s"])
            if d is not None:
                coin.setdefault((r["pass"], r["coin"]), []).append(d)
                allcoin.setdefault((r["pass"], r["coin"]), []).append(d)
        groups = {}
        for r in rows:
            s, d = num(r["sent_s"]), num(r["dur_s"])
            if s is not None and d is not None:
                groups.setdefault((r["q"], r["pass"]), []).append((s, d))
        for (q, p), v in groups.items():
            t = max(s + d for s, d in v) - min(s for s, _ in v)
            ptime.setdefault(p, []).append(t)
            alltime.setdefault(p, []).append(t)
        for (p, c), v in sorted(coin.items()):
            add("coin", name, p, c, v)
        for p, v in sorted(ptime.items()):
            add("pass_time", name, p, "pass", v)
    for (p, c), v in sorted(allcoin.items()):
        add("coin", "all", p, c, v)
    for p, v in sorted(alltime.items()):
        add("pass_time", "all", p, "pass", v)
    return out


DUR_COLUMNS = ["kind", "run", "pass", "key", "count", "median_s", "p90_s"]


def md_table(head, rows):
    s = "| " + " | ".join(head) + " |\n|" + "|".join("---" for _ in head) + "|\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


def reasons_text(c):
    parts = [f"{k} {c['r_' + k]}" for k in REASONS if c["r_" + k]]
    return ", ".join(parts) if parts else "none"


def build_md(names, runs, rows, durs):
    by = {(r["run"], r["pass"], r["bin"]): r for r in rows}
    total_calls = {n: len(rr) for n, rr in runs}
    md = ["# Step probe: summary", ""]
    md += ["- Runs read: " + ", ".join(f"{n} ({total_calls[n]} calls)" for n in names) + ".",
           "- A bin holds all requests sent in that second after q, BTC included. The BTC lines are in addition to the bins "
           "and hold all of BTC's requests of the pass (BTC is sent first in each pass).",
           "- V is the share the engine's check accepted. E is the share of verified requests, whose minute has a "
           "verified reference, whose open, high, low and close all equal the reference's (no trades in both counts as equal).",
           "- Reference: the same coin and minute asked again 95 s after the minute closed (reference pass), verified.",
           ""]

    def table(run):
        t = []
        for p in ("early", "standard"):
            for b in line_keys(p):
                r = by[(run, p, b)]
                label = f"{p} {b}"
                t.append([label, r["requests"], pct(r["V"]), pct(r["E"]), r["with_ref"], pct(share(r["volume_equal"], r["equal"]))])
        return t
    head = ["pass and bin", "requests", "V", "E", "with_ref", "volume equal"]
    md += ["## All runs together", "",
           "Bins: all coins, BTC included. Lines named BTC: BTC only. volume equal is the share of the equal bars whose "
           "volume is within 1e-9 relative.", "", md_table(head, table("all"))]
    if len(names) > 1:
        for n in names:
            md += [f"## Run {n}", "", md_table(head, table(n))]
    md += ["## Why requests were not verified (all runs together)", ""]
    for p in ("early", "standard"):
        for b in line_keys(p):
            r = by[("all", p, b)]
            md.append(f"- {p} {b}: {r['requests'] - r['verified']} of {r['requests']} not verified ({reasons_text(r)}); "
                     f"{r['no_ref']} verified without a reference.")
    md.append("")
    md += ["## How long a request takes", "",
           "Median / 90th percentile of dur_s in seconds (linear interpolation), all runs together.", ""]
    dc = {(d["pass"], d["key"]): d for d in durs if d["kind"] == "coin" and d["run"] == "all"}
    coins = sorted({k[1] for k in dc}, key=lambda c: (c != "BTC", c))
    rowsc = []
    for c in coins:
        cell = []
        for p in PASSES:
            d = dc.get((p, c))
            cell.append("n/a" if d is None else f"{float(d['median_s']):.3f} / {float(d['p90_s']):.3f}")
        rowsc.append([c] + cell)
    md += [md_table(["coin", "early", "standard", "reference"], rowsc)]
    md += ["## How long a pass takes", "",
           "First send to last return, per pass (an upper bound: it adds the last call's own pace wait, at most about "
           "0.14 s, because calls.csv records the first send, not the start of the call). Median / 90th percentile in seconds.", ""]
    rowsp = []
    for d in durs:
        if d["kind"] == "pass_time":
            rowsp.append([d["run"], d["pass"], d["count"], f"{float(d['median_s']):.3f}", f"{float(d['p90_s']):.3f}"])
    md += [md_table(["run", "pass", "passes", "median", "90th pct"], rowsp)]
    return "\n".join(md)


def summarize(run_dirs, out_dir):
    names = run_names(run_dirs)
    runs = [(n, read_calls(d)) for n, d in zip(names, run_dirs)]
    per_run = [(n, count_run(rr)) for n, rr in runs]
    rows, names = bins_table(per_run)
    durs = duration_rows(runs)
    os.makedirs(out_dir, exist_ok=True)
    write_bins(os.path.join(out_dir, "bins.csv"), rows)
    with open(os.path.join(out_dir, "durations.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DUR_COLUMNS)
        w.writeheader()
        w.writerows(durs)
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write(build_md(names, runs, rows, durs) + "\n")
    return rows, durs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    summarize(a.runs, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
