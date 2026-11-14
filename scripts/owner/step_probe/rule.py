"""Step probe: the plan's decision rule (reports/owner/step_probe_prereg.md, section Rule), applied to the lines of
all runs together in bins.csv (written by summarize.py).

Run: python scripts/owner/step_probe/rule.py --bins DIR/bins.csv --out DIR
Writes verdict.json and verdict.md.

The step may start at second s (1, 2, 3 or 4) only if all four items hold; the bins of the early pass from [s, s + 1)
on are meant: s = 1: [1,2) [2,3) [3,4) [4,6); s = 2: [2,3) [3,4) [4,6); s = 3: [3,4) [4,6); s = 4: [4,6).
  1. in each of those bins: V >= 0.990 and E >= 0.995
  2. in each of those bins: E >= (the standard pass's E, bin [6,10)) - 0.003
  3. BTC's early line: V >= 0.995 and E >= 0.995 (the same for every s)
  4. each of those bins holds at least 2000 requests, and BTC's early line at least 500
Every share is compared on the integer counts, never on a rounded float: V >= 0.990 is 1000 * verified >= 990 *
requests. The bins hold all requests of the second, BTC included (the plan's reading), as summarize.py writes them.
The candidate is the smallest s where all four hold. If any bin ruled on for an s has too few requests, that s is
"wait", not "fail" (item 4 is looked at first). Where no s passes and some s waits, the verdict is "wait".
"""
import argparse
import csv
import json
import os
import sys

EARLY_BINS = ["[1,2)", "[2,3)", "[3,4)", "[4,6)"]
STD_BIN = "[6,10)"
V_BIN, E_BIN, V_BTC, E_BTC = (990, 1000), (995, 1000), (995, 1000), (995, 1000)
GAP = (3, 1000)                 # item 2: E may be at most 0.003 below the standard pass's E
MIN_BIN, MIN_BTC = 2000, 500
NONE_TEXT = "none: the step stays at 6 s"
WAIT_TEXT = "wait: too few requests"


def ge_share(k, n, bar):
    """k / n >= bar[0] / bar[1], on integers. False when n is 0."""
    return n > 0 and k * bar[1] >= bar[0] * n


def ge_gap(eq_b, w_b, eq_s, w_s):
    """eq_b / w_b >= eq_s / w_s - 3 / 1000, on integers. False when either denominator is 0."""
    if w_b <= 0 or w_s <= 0:
        return False
    return 1000 * eq_b * w_s >= 1000 * eq_s * w_b - GAP[0] * w_b * w_s


def pct(k, n):
    return "n/a" if n == 0 else f"{100.0 * k / n:.3f}%"


def load(path):
    """Counts of the all-runs lines: {(pass, bin): {requests, verified, with_ref, equal}}."""
    out = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if r["run"] == "all":
                out[(r["pass"], r["bin"])] = {k: int(r[k]) for k in ("requests", "verified", "with_ref", "equal")}
    if not out:
        raise ValueError(f"{path} has no lines for run 'all'")
    return out


def line(lines, p, b):
    return lines.get((p, b), {"requests": 0, "verified": 0, "with_ref": 0, "equal": 0})


def judge_s(lines, s):
    bins = EARLY_BINS[s - 1:]
    std = line(lines, "standard", STD_BIN)
    btc = line(lines, "early", "BTC")
    item1, item2, item4 = [], [], []
    for b in bins:
        c = line(lines, "early", b)
        v_ok = ge_share(c["verified"], c["requests"], V_BIN)
        e_ok = ge_share(c["equal"], c["with_ref"], E_BIN)
        item1.append(dict(bin=b, requests=c["requests"], verified=c["verified"], with_ref=c["with_ref"], equal=c["equal"],
                          V_ok=v_ok, E_ok=e_ok, ok=v_ok and e_ok))
        g_ok = ge_gap(c["equal"], c["with_ref"], std["equal"], std["with_ref"])
        item2.append(dict(bin=b, equal=c["equal"], with_ref=c["with_ref"], std_equal=std["equal"], std_with_ref=std["with_ref"],
                          ok=g_ok))
        item4.append(dict(bin=b, requests=c["requests"], need=MIN_BIN, ok=c["requests"] >= MIN_BIN))
    b_v = ge_share(btc["verified"], btc["requests"], V_BTC)
    b_e = ge_share(btc["equal"], btc["with_ref"], E_BTC)
    item3 = dict(requests=btc["requests"], verified=btc["verified"], with_ref=btc["with_ref"], equal=btc["equal"],
                 V_ok=b_v, E_ok=b_e, ok=b_v and b_e)
    item4.append(dict(bin="BTC early", requests=btc["requests"], need=MIN_BTC, ok=btc["requests"] >= MIN_BTC))
    ok1, ok2, ok3, ok4 = (all(x["ok"] for x in item1), all(x["ok"] for x in item2), item3["ok"], all(x["ok"] for x in item4))
    if not ok4:
        status = "wait"
    elif ok1 and ok2 and ok3:
        status = "pass"
    else:
        status = "fail"
    return dict(s=s, bins=bins, status=status, item1=item1, item2=item2, item3=item3, item4=item4,
                items_ok=dict(item1=ok1, item2=ok2, item3=ok3, item4=ok4))


def decide(lines):
    per_s = [judge_s(lines, s) for s in (1, 2, 3, 4)]
    cand = next((p["s"] for p in per_s if p["status"] == "pass"), None)
    waits = [p["s"] for p in per_s if p["status"] == "wait"]
    if cand is not None:
        overall = f"candidate: the step may start at second {cand}"
    elif waits:
        overall = WAIT_TEXT
    else:
        overall = NONE_TEXT
    std = line(lines, "standard", STD_BIN)
    return dict(candidate=cand, verdict=overall, waiting_s=waits, standard_line=std,
                per_s={str(p["s"]): p for p in per_s})


def mark(ok):
    return "holds" if ok else "FAILS"


def to_md(d):
    std = d["standard_line"]
    md = ["# Step probe: rule applied", "", f"**Verdict: {d['verdict']}**", ""]
    if d["candidate"] is not None and d["waiting_s"] and min(d["waiting_s"]) < d["candidate"]:
        md += [f"- Note: s = {', '.join(str(x) for x in d['waiting_s'] if x < d['candidate'])} is waiting for more "
               "requests; the candidate is the smallest s for which all four items hold.", ""]
    md += [f"- Standard pass, bin [6,10): E = {std['equal']} / {std['with_ref']} = {pct(std['equal'], std['with_ref'])} "
           f"({std['requests']} requests).",
           "- Shares are compared on the counts, not on the rounded percentages shown here.", ""]
    for s in ("1", "2", "3", "4"):
        p = d["per_s"][s]
        md += [f"## s = {s}: {p['status']}" + (" (" + WAIT_TEXT + ")" if p["status"] == "wait" else ""), "",
               "Bins: " + " ".join(p["bins"]), ""]
        md.append(f"- Item 1 (V at least 99.0% and E at least 99.5% in each bin): {mark(p['items_ok']['item1'])}")
        for x in p["item1"]:
            md.append(f"  - {x['bin']}: V = {x['verified']} / {x['requests']} = {pct(x['verified'], x['requests'])} "
                      f"({mark(x['V_ok'])}); E = {x['equal']} / {x['with_ref']} = {pct(x['equal'], x['with_ref'])} ({mark(x['E_ok'])})")
        md.append(f"- Item 2 (E no more than 0.3 points below the standard pass's E): {mark(p['items_ok']['item2'])}")
        for x in p["item2"]:
            md.append(f"  - {x['bin']}: E = {pct(x['equal'], x['with_ref'])} against {pct(x['std_equal'], x['std_with_ref'])} "
                      f"minus 0.3 points ({mark(x['ok'])})")
        x = p["item3"]
        md.append(f"- Item 3 (BTC at its first place: V at least 99.5% and E at least 99.5%): {mark(p['items_ok']['item3'])}")
        md.append(f"  - V = {x['verified']} / {x['requests']} = {pct(x['verified'], x['requests'])} ({mark(x['V_ok'])}); "
                  f"E = {x['equal']} / {x['with_ref']} = {pct(x['equal'], x['with_ref'])} ({mark(x['E_ok'])})")
        md.append(f"- Item 4 (at least 2,000 requests in each bin, 500 for BTC): {mark(p['items_ok']['item4'])}")
        for x in p["item4"]:
            md.append(f"  - {x['bin']}: {x['requests']} requests, needs {x['need']} ({mark(x['ok'])})")
        md.append("")
    return "\n".join(md)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bins", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    d = decide(load(a.bins))
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "verdict.json"), "w") as f:
        json.dump(d, f, indent=1)
        f.write("\n")
    with open(os.path.join(a.out, "verdict.md"), "w") as f:
        f.write(to_md(d) + "\n")
    print(d["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
