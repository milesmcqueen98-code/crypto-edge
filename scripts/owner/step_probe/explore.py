"""Step probe, exploratory tables: when is the venue's trades list complete, by when the answer was sent and made.

Run: python scripts/owner/step_probe/explore.py --runs DIR1 [DIR2 ...] --out DIR
Writes explore.md and explore.csv into DIR. Exploratory: made after the probe's rule was applied; it decides nothing.

Definitions (summarize.py's, reused exactly, re-implemented here only to stay free of numpy):
- Rows used: the early and standard passes whose (run, coin, minute) has a reference.
- The reference for (run, coin, minute) is the first reference-pass row for it that is verified; else none.
- "equal": open, high, low, close compared as NUMBERS (float), as summarize.bars_equal does; a row with no bar and a
  reference with no bar count as equal, a bar against no bar does not. Equality is counted among ALL rows (verified or
  not) and among the verified rows.
- Whole second of sent_s and gen_s: floor. gen_s below zero: "before the minute's end"; 8 and later: "8+"; empty:
  "unknown". sent_s 12 and later: "12+"; empty or negative sent_s: "unknown" / "below 0" (printed only when present).
- Age header: empty = "fresh"; 0..4; 5 and more = "5+".
- Table 4 ("same answer"): the standard row's open, high, low, close, volume and n are all the same TEXT as the early row's.
- Coin groups: "BTC" and "other" (the other 17 coins). Table 4 also gives "all coins".
"""
import argparse
import csv
import math
import os
import sys

PASSES = ("early", "standard")
BAR = ("open", "high", "low", "close")
SAME = ("open", "high", "low", "close", "volume", "n")
GROUPS = ("other", "BTC")
HEADNOTE = ("Exploratory: this table was made after the probe's rule was applied, it decides nothing, and anything "
            "acted on needs its own test.")


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
    """Same as summarize.bars_equal: open, high, low, close equal as numbers, or no bar in both."""
    if not has_bar(a) and not has_bar(b):
        return True
    if has_bar(a) != has_bar(b):
        return False
    return all(float(a[k]) == float(b[k]) for k in BAR)


def group_of(coin):
    return "BTC" if coin == "BTC" else "other"


def sent_label(x):
    """Whole second (floor) of sent_s: "0".."11", "12+", "below 0", "unknown"."""
    if x in ("", None):
        return "unknown"
    s = math.floor(float(x))
    if s < 0:
        return "below 0"
    return "12+" if s >= 12 else str(s)


def gen_label(x):
    """Whole second (floor) of gen_s: "before the minute's end", "0".."7", "8+", "unknown"."""
    if x in ("", None):
        return "unknown"
    s = math.floor(float(x))
    if s < 0:
        return "before the minute's end"
    return "8+" if s >= 8 else str(s)


def age_label(x):
    """The Age header: "fresh" when empty, "0".."4", "5+"."""
    if x in ("", None):
        return "fresh"
    a = int(float(x))
    return "5+" if a >= 5 else str(max(a, 0))


SENT_ORDER = ["below 0"] + [str(i) for i in range(12)] + ["12+", "unknown"]
GEN_ORDER = ["before the minute's end"] + [str(i) for i in range(8)] + ["8+", "unknown"]
AGE_ORDER = ["fresh", "0", "1", "2", "3", "4", "5+"]


def used_rows(name, rows):
    """Early and standard rows with a reference, each as (run, row, reference); also the table 4 index."""
    ref = {}
    for r in rows:
        if r["pass"] == "reference" and r["verified"] == "1":
            ref.setdefault((r["coin"], r["minute"]), r)
    out = []
    for r in rows:
        if r["pass"] in PASSES:
            rf = ref.get((r["coin"], r["minute"]))
            if rf is not None:
                out.append((name, r, rf))
    return out


def zero4():
    return {"rows": 0, "verified": 0, "equal_all": 0, "equal_verified": 0}


def add4(c, r, eq):
    c["rows"] += 1
    if r["verified"] == "1":
        c["verified"] += 1
        if eq:
            c["equal_verified"] += 1
    if eq:
        c["equal_all"] += 1


def tally(used, labeler, col):
    """{(pass, group, label): counts} for the rows used."""
    out = {}
    for _, r, rf in used:
        k = (r["pass"], group_of(r["coin"]), labeler(r[col]))
        add4(out.setdefault(k, zero4()), r, bars_equal(r, rf))
    return out


def tally_age(used):
    out = {}
    for _, r, _rf in used:
        k = (r["pass"], group_of(r["coin"]), age_label(r["age"]))
        out[k] = out.get(k, 0) + 1
    return out


def tally_after_fresh(used):
    """Table 4. Keys (group, early_equal, std_age, same_answer) -> [count, std_equal_to_reference]; group "all" too."""
    early, std = {}, {}
    for name, r, rf in used:
        k = (name, r["coin"], r["minute"])
        if r["pass"] == "early":
            early.setdefault(k, (r, rf))
        else:
            std.setdefault(k, (r, rf))
    out = {}
    for k, (e, rf) in early.items():
        if e["age"] != "" or k not in std:
            continue
        s, _ = std[k]
        e_eq = bars_equal(e, rf)
        same = all(e[f] == s[f] for f in SAME)
        for g in (group_of(e["coin"]), "all"):
            c = out.setdefault((g, e_eq, age_label(s["age"]), same), [0, 0])
            c[0] += 1
            if bars_equal(s, rf):
                c[1] += 1
    return out


def table4_totals(t4, group, e_eq):
    """(cases, std fresh, std with Age header, of those the same answer as the early one)."""
    n = fresh = aged = aged_same = 0
    for (g, eq, age, same), (c, _) in t4.items():
        if g != group or eq != e_eq:
            continue
        n += c
        if age == "fresh":
            fresh += c
        else:
            aged += c
            if same:
                aged_same += c
    return n, fresh, aged, aged_same


def kn(k, n):
    return f"{k} / {n} = {100 * k / n:.2f}%" if n else f"{k} / {n} = n/a"


def md_table(head, rows):
    s = "| " + " | ".join(head) + " |\n|" + "|".join("---" for _ in head) + "|\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


def fmt_counts(c):
    return [c["rows"], kn(c["verified"], c["rows"]), kn(c["equal_all"], c["rows"]), kn(c["equal_verified"], c["verified"])]


def sent_second_text(tab, p, g, s):
    c = tab.get((p, g, s))
    return (c["equal_all"], c["rows"]) if c else (0, 0)


def explore(run_dirs, out_dir):
    names = run_names(run_dirs)
    per = [(n, used_rows(n, read_calls(d))) for n, d in zip(names, run_dirs)]
    sets = [("all runs together", [u for _, us in per for u in us])]
    if len(per) > 1:
        sets += [(f"run {n}", us) for n, us in per]
    csv_rows = []
    md = ["# Step probe: exploratory table, when is the trades list complete", "", HEADNOTE, "",
          "Rows used: early and standard passes whose (run, coin, minute) has a verified reference-pass row (asked again "
          "95 s after the minute closed). Equal: open, high, low and close equal as numbers, or no bar in both. "
          "Equal among all rows counts unverified rows too (their bar, if any, against the reference). "
          "BTC and the other 17 coins are shown apart. Shares are k / n = percent.", ""]
    closing = None
    for sname, used in sets:
        md += [f"## {sname}", ""]
        sent = tally(used, sent_label, "sent_s")
        gen = tally(used, gen_label, "gen_s")
        ages = tally_age(used)
        t4 = tally_after_fresh(used)
        head = ["pass", "coins", "{}", "rows", "verified", "equal among all rows", "equal among the verified"]
        for tno, title, tab, order, col in (
                (1, "By the second the request was sent (sent_s, floor)", sent, SENT_ORDER, "sent_s"),
                (2, "By the second the answer was made (gen_s, floor)", gen, GEN_ORDER, "gen_s")):
            md += [f"### Table {tno}. {title}", ""]
            rows = []
            for p in PASSES:
                for g in GROUPS:
                    for lab in order:
                        c = tab.get((p, g, lab))
                        if c is None:
                            if lab in ("below 0", "before the minute's end", "unknown"):
                                continue
                            c = zero4()
                        rows.append([p, g, lab] + fmt_counts(c))
                        csv_rows.append({"runs": sname, "table": tno, "pass": p, "group": g, "key": lab, **c})
            md += [md_table([head[0], head[1], col] + head[3:], rows)]
        md += ["### Table 3. The Age header", ""]
        rows = []
        for p in PASSES:
            for g in GROUPS:
                tot = sum(ages.get((p, g, a), 0) for a in AGE_ORDER)
                rows.append([p, g, tot] + [ages.get((p, g, a), 0) for a in AGE_ORDER])
                csv_rows.append({"runs": sname, "table": 3, "pass": p, "group": g, "key": "age",
                                 **{"age_" + a: ages.get((p, g, a), 0) for a in AGE_ORDER}, "rows": tot})
        md += [md_table(["pass", "coins", "rows", "none (fresh)", "Age 0", "Age 1", "Age 2", "Age 3", "Age 4", "Age 5 and more"], rows)]
        md += ["### Table 4. What the standard pass saw after a fresh early answer", "",
               "Cases: (run, coin, minute) with an early row without an Age header, a standard row and a reference. "
               "Same answer: open, high, low, close, volume and n all the same text as the early row's. "
               "Last column: standard rows of the cell equal to the reference.", ""]
        for g in GROUPS + ("all",):
            gname = "all coins" if g == "all" else g
            rows = []
            for e_eq in (False, True):
                for age in AGE_ORDER:
                    for same in (True, False):
                        c = t4.get((g, e_eq, age, same), [0, 0])
                        rows.append(["equal" if e_eq else "not equal", age, "same answer" if same else "different answer",
                                     c[0], kn(c[1], c[0])])
                        csv_rows.append({"runs": sname, "table": 4, "pass": "standard", "group": gname,
                                         "key": f"early {'equal' if e_eq else 'not equal'}|std age {age}|"
                                                f"{'same' if same else 'different'}",
                                         "rows": c[0], "equal_all": c[1]})
            md += [f"Coins: {gname}", "", md_table(["early bar vs reference", "standard row's Age", "standard answer",
                                                    "cases", "standard rows equal to the reference"], rows)]
            lines = []
            for e_eq in (False, True):
                n, fresh, aged, aged_same = table4_totals(t4, g, e_eq)
                lines.append(f"- After a fresh early answer that was {'equal' if e_eq else 'NOT equal'} to the reference: "
                             f"{n} cases; the standard row was fresh in {fresh}, came with an Age header in {aged}, "
                             f"and of those {aged_same} were the same answer as the early one.")
                csv_rows.append({"runs": sname, "table": 4, "pass": "standard", "group": gname,
                                 "key": f"total early {'equal' if e_eq else 'not equal'}|cases|std fresh|std with Age|"
                                        f"of those same answer", "rows": n, "verified": fresh, "equal_all": aged,
                                 "equal_verified": aged_same})
            md += lines + [""]
        if sname == "all runs together":
            closing = (sent, used)
    sent, used = closing
    es = [sent_second_text(sent, "early", "other", str(s)) for s in range(1, 8)]
    btc = tally(used, lambda x: "all", "sent_s").get(("early", "BTC", "all"), zero4())
    std_all = zero4()
    for _, r, rf in used:
        if r["pass"] == "standard":
            add4(std_all, r, bars_equal(r, rf))
    md += ["## What the tables show", ""]
    parts = [f"Of the answers sent in second {s}, {k} of {n} were equal to the list 95 s later" for s, (k, n) in
             zip(range(1, 8), es)]
    txt = ("Early pass, other coins, both runs together: " + "; ".join(parts) + ". "
           f"For BTC at its early place, of the answers sent (all seconds), {btc['equal_all']} of {btc['rows']} were equal "
           f"to the list 95 s later. For the standard pass as a whole (all coins), of the answers sent, "
           f"{std_all['equal_all']} of {std_all['rows']} were equal to the list 95 s later.")
    md += [txt, ""]
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "explore.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    cols = ["runs", "table", "pass", "group", "key", "rows", "verified", "equal_all", "equal_verified"] + \
           ["age_" + a for a in AGE_ORDER]
    with open(os.path.join(out_dir, "explore.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(csv_rows)
    return csv_rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    explore(a.runs, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
