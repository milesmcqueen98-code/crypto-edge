"""Offline test of rule.py on hand-made bins.csv files. Run: python scripts/owner/step_probe/test_rule.py
(one line per check, last line "N checks, F failed", non-zero exit on a failure)."""
import csv
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rule             # noqa: E402

COLS = ["run", "pass", "bin", "requests", "verified", "with_ref", "no_ref", "equal", "volume_equal"]
EARLY = ["[1,2)", "[2,3)", "[3,4)", "[4,6)"]
FAILS = []
COUNT = [0]


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


def lines(**over):
    """Everything passes by default: each early bin 3000 requests all verified and all equal, the standard bin 5000,
    BTC 800. over maps a key to a dict of count changes: e1..e4 (early bins), std, btc."""
    base = {"e1": (3000, 3000, 3000, 3000), "e2": (3000, 3000, 3000, 3000), "e3": (3000, 3000, 3000, 3000),
            "e4": (3000, 3000, 3000, 3000), "std": (5000, 5000, 5000, 5000), "btc": (800, 800, 800, 800)}
    for k, v in over.items():
        cur = dict(zip(("requests", "verified", "with_ref", "equal"), base[k]))
        cur.update(v)
        base[k] = (cur["requests"], cur["verified"], cur["with_ref"], cur["equal"])
    rows = []
    for name, (p, b) in zip(("e1", "e2", "e3", "e4", "std", "btc"),
                            [("early", x) for x in EARLY] + [("standard", "[6,10)"), ("early", "BTC")]):
        r, v, w, e = base[name]
        rows.append({"run": "all", "pass": p, "bin": b, "requests": r, "verified": v, "with_ref": w, "no_ref": 0,
                     "equal": e, "volume_equal": e})
    return rows


def write_bins(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def verdict(tmp, rows, tag):
    d = os.path.join(tmp, tag)
    os.makedirs(d)
    write_bins(os.path.join(d, "bins.csv"), rows)
    rule.main(["--bins", os.path.join(d, "bins.csv"), "--out", d])
    with open(os.path.join(d, "verdict.json")) as f:
        return json.load(f), d


def case(tmp, tag, name, expect_cand, expect_text, **over):
    v, d = verdict(tmp, lines(**over), tag)
    check(name, v["candidate"] == expect_cand and v["verdict"].startswith(expect_text), (v["candidate"], v["verdict"]))
    return v, d


def main():
    tmp = tempfile.mkdtemp()
    try:
        v, d = case(tmp, "a", "everything passes: candidate 1", 1, "candidate: the step may start at second 1")
        check("all four s pass when everything passes", all(v["per_s"][s]["status"] == "pass" for s in "1234"))
        md = open(os.path.join(d, "verdict.md")).read()
        check("verdict.md lists every s and every item with numbers",
              all(f"## s = {s}: pass" in md for s in "1234") and "Item 1" in md and "Item 2" in md and "Item 3" in md
              and "Item 4" in md and "V = 3000 / 3000 = 100.000%" in md and "BTC" in md)

        # item 1, V
        case(tmp, "b", "bin [1,2) fails V (2969 of 3000): candidate 2", 2, "candidate: the step may start at second 2", e1=dict(verified=2969))
        case(tmp, "c", "V exactly 99.0% (2970 of 3000) holds: candidate 1", 1, "candidate", e1=dict(verified=2970))
        v, _ = case(tmp, "c2", "V fails in [4,6) only: s = 1..4 all fail: none", None, "none: the step stays at 6 s", e4=dict(verified=2969))
        check("none verdict names the 6 s gap", v["verdict"] == "none: the step stays at 6 s")
        # item 1, E (the standard pass is set to 99.5% so that item 2 does not bind: 4975 of 5000)
        std995 = dict(equal=4975)
        case(tmp, "d", "E exactly 99.5% (2985 of 3000) in [2,3) holds: candidate 1", 1, "candidate", e2=dict(equal=2985), std=std995)
        case(tmp, "e", "E just below 99.5% (2984 of 3000) in [2,3): s 1 and 2 fail, candidate 3", 3, "candidate: the step may start at second 3",
             e2=dict(equal=2984), std=std995)
        # with_ref not equal to requests: E is on with_ref
        case(tmp, "e2", "E counts on with_ref (1990 of 2000 is 99.5%; 1989 fails)", 1, "candidate",
             e1=dict(with_ref=2000, equal=1990), std=std995)
        case(tmp, "e3", "E just below with a short with_ref (1989 of 2000): candidate 2", 2, "candidate: the step may start at second 2",
             e1=dict(with_ref=2000, equal=1989), std=std995)

        # item 2 alone: the standard pass E is 100%, a bin at 99.6% passes item 1 but not item 2
        v, _ = case(tmp, "f", "item 2 fails alone in [3,4) (2990 of 3000 against 100%): candidate 4", 4,
                    "candidate: the step may start at second 4", e3=dict(equal=2990))
        s3 = v["per_s"]["3"]
        check("... with items 1, 3 and 4 holding and item 2 failing at s = 3",
              s3["items_ok"] == dict(item1=True, item2=False, item3=True, item4=True) and s3["status"] == "fail", s3["items_ok"])
        case(tmp, "g", "item 2 exactly 0.3 points below (2991 of 3000 against 100%) holds: candidate 1", 1, "candidate", e3=dict(equal=2991))
        case(tmp, "g2", "item 2 against a standard pass of 99.0% (4950 of 5000): a bin at 99.5% holds",
             1, "candidate", e1=dict(equal=2985), std=dict(equal=4950))
        # the exact boundary with unequal denominators (counts, not floats): 1991/2000 = 99.55; std 4985/5000 = 99.7 -> 99.55 >= 99.4
        case(tmp, "g3", "item 2 on unequal denominators: 99.55% against 99.7% holds", 1, "candidate",
             e1=dict(with_ref=2000, equal=1991), std=dict(equal=4985))
        case(tmp, "g4", "item 2 on unequal denominators: 99.5% against 99.85% fails by 0.35 points in [1,2): candidate 2", 2,
             "candidate: the step may start at second 2", e1=dict(with_ref=2000, equal=1990), std=dict(equal=4993, with_ref=5000))
        case(tmp, "g5", "item 2 undefined (standard pass has no references): nothing passes", None, "none",
             std=dict(with_ref=0, equal=0))

        # item 3, BTC
        case(tmp, "h", "BTC V 99.0% (792 of 800) fails: no s passes", None, "none", btc=dict(verified=792))
        case(tmp, "h2", "BTC V exactly 99.5% (796 of 800) holds", 1, "candidate", btc=dict(verified=796))
        case(tmp, "h3", "BTC V just below (795 of 800) fails", None, "none", btc=dict(verified=795))
        case(tmp, "h4", "BTC E exactly 99.5% (796 of 800) holds against a standard pass at 99.5%", 1, "candidate",
             btc=dict(equal=796), std=std995)
        v, _ = case(tmp, "h5", "BTC E just below (795 of 800) fails every s", None, "none", btc=dict(equal=795), std=std995)
        check("BTC fails item 3 for every s", all(not v["per_s"][s]["items_ok"]["item3"] for s in "1234"))

        # item 4, too few requests
        v, _ = case(tmp, "i", "[4,6) with 1999 requests: every s waits", None, "wait: too few requests", e4=dict(requests=1999))
        check("... and each s is wait, not fail", all(v["per_s"][s]["status"] == "wait" for s in "1234"))
        case(tmp, "i2", "[4,6) with exactly 2000 requests is enough", 1, "candidate", e4=dict(requests=2000))
        case(tmp, "i3", "BTC with 499 requests: wait", None, "wait: too few requests", btc=dict(requests=499))
        case(tmp, "i4", "BTC with exactly 500 requests is enough", 1, "candidate", btc=dict(requests=500))
        v, d = case(tmp, "i5", "[1,2) with 1500 requests: s = 1 waits, s = 2 passes, candidate 2", 2, "candidate: the step may start at second 2",
                    e1=dict(requests=1500, verified=1500, with_ref=1500, equal=1500))
        check("... the note names s = 1 as waiting", v["per_s"]["1"]["status"] == "wait"
              and "s = 1 is waiting" in open(os.path.join(d, "verdict.md")).read())
        v, _ = case(tmp, "i6", "too few requests wins over a failing share: [1,2) 1500 requests and V 50% is wait for s = 1", 2, "candidate",
                    e1=dict(requests=1500, verified=750, with_ref=750, equal=750))
        check("... s = 1 is wait", v["per_s"]["1"]["status"] == "wait")

        # lines of single runs are ignored; a file without all-runs lines is an error
        rows = lines(e1=dict(verified=2000)) + [dict(r, run="runA") for r in lines()]
        for r in rows:
            if r["run"] == "runA":
                r["verified"] = 0
        v, _ = verdict(tmp, rows, "j")
        check("only the lines of 'all' are used (run lines with V 0 are ignored)", v["candidate"] == 2, v["candidate"])
        try:
            verdict(tmp, [dict(r, run="runA") for r in lines()], "k")
            ok = False
        except ValueError:
            ok = True
        check("bins.csv without 'all' lines is an error", ok)
        rows = [r for r in lines() if r["bin"] != "[4,6)"]
        v, _ = verdict(tmp, rows, "l")
        check("a bin missing from the file counts as zero requests (wait)", v["verdict"] == "wait: too few requests")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{COUNT[0]} checks, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
