"""Offline test of summarize.py on two hand-made calls.csv files whose bins were computed by hand (see the comment
above each run). Run: python scripts/owner/step_probe/test_summarize.py (one line per check, last line
"N checks, F failed", non-zero exit on a failure)."""
import csv
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import summarize as sm  # noqa: E402

COLS = ["q", "minute", "pass", "place", "coin", "sent_s", "dur_s", "verified", "reason", "pages", "gen_s", "age", "n",
        "open", "high", "low", "close", "volume", "error"]
FAILS = []
COUNT = [0]
M1, M2, M3 = "2026-11-14T10:00:00Z", "2026-11-14T10:01:00Z", "2026-11-14T10:02:00Z"


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


def row(p, coin, minute, sent, ver=1, reason="", bar=None, dur="0.2", error="", q="Q1"):
    r = {c: "" for c in COLS}
    r.update(q=q, minute=minute, coin=coin, dur_s=dur, verified=str(ver), reason=reason, error=error)
    r["pass"] = p
    r["sent_s"] = sent
    if ver:
        r["n"] = "0" if bar is None else "3"
    if bar is not None:
        r["open"], r["high"], r["low"], r["close"], r["volume"] = (repr(float(x)) for x in bar)
    return r


def write(d, rows):
    os.makedirs(d)
    with open(os.path.join(d, "calls.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


BTC1 = (100, 101, 99, 100.5, 2.0)
ETH1 = (10, 12, 9, 11, 5.0)
ETH2 = (20, 22, 19, 21, 7.0)
BTC2 = (200, 201, 199, 200.5, 3.0)

# Run A. References (verified unless noted): BTC M1, ETH M1, SOL M1 (no trades), ETH M2, BTC M2; DOGE M1 is NOT
# verified, so DOGE M1 has no reference; XRP, LINK, BCH, BTC M3 have no reference row at all.
RUN_A = [
    row("reference", "BTC", M1, "35.0", bar=BTC1), row("reference", "ETH", M1, "35.2", bar=ETH1),
    row("reference", "SOL", M1, "35.4"), row("reference", "DOGE", M1, "35.6", ver=0, reason="stale_first_page"),
    row("reference", "ETH", M2, "35.8", bar=ETH2), row("reference", "BTC", M2, "36.0", bar=BTC2),
    # early
    row("early", "BTC", M1, "1.000", bar=BTC1),                                    # [1,2) equal, volume equal
    row("early", "ETH", M1, "1.143", bar=(10, 12, 9, 11, 5.0000000001), dur="0.1"),  # [1,2) equal, volume within 1e-9
    row("early", "SOL", M1, "1.286"),                                              # [1,2) no trades in both: equal
    row("early", "DOGE", M1, "1.429", bar=(1, 1, 1, 1, 1.0)),                      # [1,2) verified, reference unverified: no_ref
    row("early", "BTC", M2, "1.000", bar=(200, 201, 199, 200.5, 3.5)),             # [1,2) OHLC equal, volume differs
    row("early", "ETH", M2, "2.100", bar=(20, 22, 19, 21.5, 7.0), dur="0.3"),      # [2,3) close differs: not equal
    row("early", "LTC", M1, "2.500", ver=0, reason="stale_first_page"),            # [2,3) unverified
    row("early", "XRP", M1, "3.900", bar=(5, 6, 4, 5, 1.0)),                       # [3,4) verified, no reference: no_ref
    row("early", "ETH", M1, "4.000", dur="0.9"),                                   # [4,6) bar missing, reference has one
    row("early", "SOL", M2, "5.999", ver=0, reason="incomplete"),                  # [4,6) unverified
    row("early", "LINK", M1, "6.000", bar=(3, 3, 3, 3, 1.0)),                      # other (6.0 is not in an early bin)
    row("early", "BCH", M1, "0.500", bar=(3, 3, 3, 3, 1.0)),                       # other
    row("early", "BTC", M3, "0.999", bar=(300, 301, 299, 300, 1.0)),               # other bin, but in the BTC line; no reference
    row("early", "SUI", M1, "", ver=0, reason="error", error="boom"),              # other (no send time), error
    # standard
    row("standard", "BTC", M1, "6.000", bar=BTC1),                                 # [6,10) equal
    row("standard", "ETH", M1, "6.200", bar=ETH1),                                 # [6,10) equal
    row("standard", "ETH", M2, "7.500", bar=ETH2),                                 # [6,10) equal
    row("standard", "SOL", M1, "9.999", ver=0, reason="malformed"),                # [6,10) unverified
    row("standard", "BTC", M2, "10.000", bar=BTC2),                                # other (10.0 is out); BTC line; equal
    row("standard", "DOGE", M1, "12.000", bar=(1, 1, 1, 1, 1.0)),                  # other; no reference
]
# Run B: reference for ETH M1 only.
RUN_B = [
    row("reference", "ETH", M1, "35.0", bar=ETH1),
    row("early", "ETH", M1, "1.200", bar=ETH1, dur="0.5"),                         # [1,2) equal
    row("early", "BTC", M1, "1.000", bar=BTC1),                                    # [1,2) BTC; no reference in B
    row("early", "ETH", M1, "3.000", ver=0, reason="deadline", dur="0.7"),         # [3,4) unverified
    row("standard", "ETH", M1, "6.500", bar=(10, 12, 9, 11.5, 5.0)),               # [6,10) not equal
]

# expected: (pass, bin) -> (requests, verified, with_ref, no_ref, equal, volume_equal, reasons)
EXP_A = {
    ("early", "[1,2)"): (5, 5, 4, 1, 4, 3, {}),
    ("early", "[2,3)"): (2, 1, 1, 0, 0, 0, {"stale_first_page": 1}),
    ("early", "[3,4)"): (1, 1, 0, 1, 0, 0, {}),
    ("early", "[4,6)"): (2, 1, 1, 0, 0, 0, {"incomplete": 1}),
    ("early", "other"): (4, 3, 0, 3, 0, 0, {"error": 1}),
    ("early", "BTC"): (3, 3, 2, 1, 2, 1, {}),
    ("standard", "[6,10)"): (4, 3, 3, 0, 3, 3, {"malformed": 1}),
    ("standard", "other"): (2, 2, 1, 1, 1, 1, {}),
    ("standard", "BTC"): (2, 2, 2, 0, 2, 2, {}),
}
EXP_B = {
    ("early", "[1,2)"): (2, 2, 1, 1, 1, 1, {}),
    ("early", "[2,3)"): (0, 0, 0, 0, 0, 0, {}),
    ("early", "[3,4)"): (1, 0, 0, 0, 0, 0, {"deadline": 1}),
    ("early", "[4,6)"): (0, 0, 0, 0, 0, 0, {}),
    ("early", "other"): (0, 0, 0, 0, 0, 0, {}),
    ("early", "BTC"): (1, 1, 0, 1, 0, 0, {}),
    ("standard", "[6,10)"): (1, 1, 1, 0, 0, 0, {}),
    ("standard", "other"): (0, 0, 0, 0, 0, 0, {}),
    ("standard", "BTC"): (0, 0, 0, 0, 0, 0, {}),
}
EXP_ALL = {
    ("early", "[1,2)"): (7, 7, 5, 2, 5, 4, {}),
    ("early", "[2,3)"): (2, 1, 1, 0, 0, 0, {"stale_first_page": 1}),
    ("early", "[3,4)"): (2, 1, 0, 1, 0, 0, {"deadline": 1}),
    ("early", "[4,6)"): (2, 1, 1, 0, 0, 0, {"incomplete": 1}),
    ("early", "other"): (4, 3, 0, 3, 0, 0, {"error": 1}),
    ("early", "BTC"): (4, 4, 2, 2, 2, 1, {}),
    ("standard", "[6,10)"): (5, 4, 4, 0, 3, 3, {"malformed": 1}),
    ("standard", "other"): (2, 2, 1, 1, 1, 1, {}),
    ("standard", "BTC"): (2, 2, 2, 0, 2, 2, {}),
}


def got(rows, run):
    out = {}
    for r in rows:
        if r["run"] == run:
            reasons = {k[2:]: int(r[k]) for k in r if k.startswith("r_") and int(r[k])}
            out[(r["pass"], r["bin"])] = (int(r["requests"]), int(r["verified"]), int(r["with_ref"]), int(r["no_ref"]),
                                          int(r["equal"]), int(r["volume_equal"]), reasons)
    return out


def main():
    tmp = tempfile.mkdtemp()
    try:
        a, b, out = (os.path.join(tmp, x) for x in ("runA", "runB", "out"))
        write(a, RUN_A)
        write(b, RUN_B)
        check("hand-made runs: 31 rows in all (26 of A, 5 of B)", (len(RUN_A), len(RUN_B)) == (26, 5), (len(RUN_A), len(RUN_B)))
        sm.main(["--runs", a, b, "--out", out])
        with open(os.path.join(out, "bins.csv"), newline="") as f:
            rows = list(csv.DictReader(f))
        for name, exp in (("runA", EXP_A), ("runB", EXP_B), ("all", EXP_ALL)):
            g = got(rows, name)
            bad = [(k, g.get(k), v) for k, v in exp.items() if g.get(k) != v]
            check(f"bins.csv counts for {name} match the hand computation", not bad, bad[:2])
        check("every run has 9 lines (early 4 bins + other + BTC, standard bin + other + BTC)",
              all(sum(1 for r in rows if r["run"] == n) == 9 for n in ("runA", "runB", "all")))
        ra = {(r["pass"], r["bin"]): r for r in rows if r["run"] == "runA"}
        check("V and E are written as shares (early [1,2) of run A: 1.0 and 1.0)", ra[("early", "[1,2)")]["V"] == "1.0"
              and ra[("early", "[1,2)")]["E"] == "1.0")
        check("E is empty when no verified request has a reference ([3,4) of run A)", ra[("early", "[3,4)")]["E"] == "")
        check("V of early [2,3) of run A is 0.5", ra[("early", "[2,3)")]["V"] == "0.5")
        check("BTC line takes BTC's requests whatever the second (0.999 s is in the BTC line, in bin other)",
              ra[("early", "BTC")]["requests"] == "3" and ra[("early", "other")]["requests"] == "4")
        check("a row with no send time goes to bin other", ra[("early", "other")]["r_error"] == "1")
        check("0.001 under a bin edge and the edge: 5.999 is [4,6), 6.0 early is other, 4.0 is [4,6), 10.0 standard is other",
              ra[("early", "[4,6)")]["requests"] == "2" and ra[("standard", "other")]["requests"] == "2")
        check("reference rows are not counted: 24 early and standard requests in all, BTC lines apart",
              sum(int(r["requests"]) for r in rows if r["run"] == "all" and r["bin"] != "BTC") == 24)

        with open(os.path.join(out, "durations.csv"), newline="") as f:
            dur = list(csv.DictReader(f))
        d = {(r["kind"], r["run"], r["pass"], r["key"]): r for r in dur}
        e = d[("coin", "all", "early", "ETH")]
        check("ETH early: count 5, median 0.5, 90th percentile 0.82 (0.1 0.3 0.9 0.5 0.7)",
              e["count"] == "5" and abs(float(e["median_s"]) - 0.5) < 1e-12 and abs(float(e["p90_s"]) - 0.82) < 1e-12, e)
        pa = d[("pass_time", "runA", "early", "pass")]
        pb = d[("pass_time", "runB", "early", "pass")]
        pall = d[("pass_time", "all", "early", "pass")]
        check("pass time run A early: 6.2 - 0.5 = 5.7; run B early: 3.7 - 1.0 = 2.7; both: median 4.2",
              abs(float(pa["median_s"]) - 5.7) < 1e-9 and abs(float(pb["median_s"]) - 2.7) < 1e-9
              and abs(float(pall["median_s"]) - 4.2) < 1e-9 and pall["count"] == "2", (pa, pb, pall))
        check("durations.csv has coin lines per run and for all, and pass_time lines for reference too",
              ("coin", "runB", "early", "BTC") in d and ("pass_time", "all", "reference", "pass") in d)

        with open(os.path.join(out, "summary.md")) as f:
            md = f.read()
        check("summary.md says bins include BTC and BTC lines are in addition", "BTC included" in md and "in addition" in md)
        heads = [ln for i, ln in enumerate(md.splitlines()[:-1]) if ln.startswith("|") and md.splitlines()[i + 1].startswith("|---")]
        check("summary.md tables have at most six columns", heads and all(h.count("|") - 1 <= 6 for h in heads), heads)
        check("summary.md has the all-runs table and one per run", "## All runs together" in md and "## Run runA" in md and "## Run runB" in md)
        check("summary.md reports the not-verified reasons", "stale_first_page 1" in md and "deadline 1" in md and "error 1" in md)
        check("summary.md: early [1,2) of all runs: 7 requests, V 100.00%, E 100.00%",
              "| early [1,2) | 7 | 100.00% | 100.00% | 5 | 80.00% |" in md, [l for l in md.splitlines() if "early [1,2)" in l][:1])
        check("no at-sign in the output", chr(64) not in md)

        # a single run, and the same folder name twice
        out2 = os.path.join(tmp, "out2")
        sm.main(["--runs", a, "--out", out2])
        with open(os.path.join(out2, "bins.csv"), newline="") as f:
            r2 = list(csv.DictReader(f))
        check("single run: all lines equal run A's", got(r2, "all") == got(r2, "runA") == EXP_A)
        names = sm.run_names(["x/run1", "y/run1/", "z"])
        check("duplicate folder names are told apart", names == ["run1", "run1#2", "z"], names)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{COUNT[0]} checks, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
