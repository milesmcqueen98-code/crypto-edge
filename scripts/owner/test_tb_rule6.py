#!/usr/bin/env python3
"""Tests for tb_rule6.py on small inline tables. Run: python scripts/owner/test_tb_rule6.py"""
import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tb_rule6 as t  # noqa: E402

FAILS = []
HEAD = "coin,day,tbar_compared,tbar_exact,tbar_material,first_compared,first_exact,first_material"
START, END = "2026-11-11T00:00", "2026-11-14T00:00"          # three full UTC dates
DAYS = ["2026-11-11", "2026-11-12", "2026-11-13"]
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tb_rule6.py")


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def row(coin, day, comp=1000, ex=90.0, mat=0.5, fcomp=1000, fex=40.0, fmat=20.0):
    return f"{coin},{day},{comp},{ex},{mat},{fcomp},{fex},{fmat}"


def good(coin):
    return [row(coin, d) for d in DAYS]


def run(lines, start=START, end=END, coins="BTC,ETH,SOL"):
    """Run the whole script on inline text; return (exit code, stdout text)."""
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "daily.csv")
        with open(p, "w") as f:
            f.write("\n".join([HEAD] + lines) + "\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = t.main(["--daily", p, "--start", start, "--end", end, "--coins", coins])
    return code, buf.getvalue()


def verdict(text, prefix):
    for l in text.splitlines():
        if l.startswith(prefix):
            return l
    return ""


def main():
    # 1. clean pass over three full dates
    code, text = run(good("BTC") + good("ETH") + good("SOL"))
    check("clean pass: exit 0 and overall PASS", code == 0 and "Item 6 overall: PASS." in text, text)
    check("clean pass: each part passes", "6(a) BTC: PASS" in text and "6(b) ETH: PASS" in text and "6(b) SOL: PASS" in text)
    check("clean pass: nine counted lines", text.count("| counted |") == 9, text)

    # 2. BTC pooled share: 30 of 3000 is exactly 1.00% and passes; one more minute fails
    btc = [row("BTC", d, comp=1000, mat=1.0) for d in DAYS]
    code, text = run(btc + good("ETH") + good("SOL"))
    check("BTC 1.00% passes", "6(a) BTC: PASS" in text and "1.00%" in text and "30 of 3,000" in text, verdict(text, "6(a)"))
    btc2 = [row("BTC", DAYS[0], mat=1.0), row("BTC", DAYS[1], mat=1.0), row("BTC", DAYS[2], mat=1.1)]
    code, text = run(btc2 + good("ETH") + good("SOL"))
    check("BTC one minute over fails", "6(a) BTC: FAIL" in text and "31 of 3,000" in text and "1.03%" in text, verdict(text, "6(a)"))
    check("BTC fail makes overall FAIL", "Item 6 overall: FAIL." in text)

    # 3. 6(b) failures, ties
    def eth_with(day_idx, **kw):
        r = good("ETH")
        r[day_idx] = row("ETH", DAYS[day_idx], **kw)
        return r
    cases = [
        ("material worse", dict(mat=25.0, fmat=20.0), "material"),
        ("exact worse", dict(ex=30.0, fex=40.0), "exact"),
        ("material tie", dict(mat=20.0, fmat=20.0), "material"),
        ("exact tie", dict(ex=40.0, fex=40.0), "exact"),
    ]
    for name, kw, which in cases:
        code, text = run(good("BTC") + eth_with(1, **kw) + good("SOL"))
        v = verdict(text, "6(b) ETH")
        other = "exact" if which == "material" else "material"
        check(f"6(b) {name}: ETH fails on that date", v.startswith("6(b) ETH: FAIL") and "2026-11-12 (" + which + ")" in v
              and other not in v and "2026-11-11" not in v, v)
        check(f"6(b) {name}: result column says which measure", f"| fail: {which} |" in text)
        check(f"6(b) {name}: SOL still passes", "6(b) SOL: PASS" in text)
    code, text = run(good("BTC") + eth_with(0, mat=25.0, fmat=20.0, ex=30.0, fex=40.0) + good("SOL"))
    check("6(b) both measures named", "2026-11-11 (material and exact)" in text, verdict(text, "6(b) ETH"))

    # 4. date inclusion
    # 11.9 hours inside: period ends 11:54 on the last date
    code, text = run(good("BTC") + good("ETH") + good("SOL"), end="2026-11-13T11:54")
    check("11.9 hours is outside the period", "| 11.9 |" in text and "outside the period" in text
          and text.count("| counted |") == 6, text)
    check("11.9 hours: other dates still counted, two are enough", "Item 6 overall: PASS." in text)
    # exactly 12 hours inside is counted
    code, text = run(good("BTC") + good("ETH") + good("SOL"), end="2026-11-13T12:00")
    check("12.0 hours is counted", text.count("| counted |") == 9 and "| 12.0 |" in text, text)
    # 719 compared minutes is left out
    r = good("BTC")
    r[2] = row("BTC", DAYS[2], comp=719)
    code, text = run(r + good("ETH") + good("SOL"))
    check("719 compared minutes left out", "left out: too few minutes" in text and text.count("| counted |") == 8
          and "6(a) BTC: PASS" in text and "of 2,000" in text, text)
    r = good("BTC")
    r[2] = row("BTC", DAYS[2], comp=720)
    code, text = run(r + good("ETH") + good("SOL"))
    check("720 compared minutes counted", text.count("| counted |") == 9, text)
    # non-BTC: first_compared 719 leaves the date out even with 1,400 tbar minutes
    e = good("ETH")
    e[2] = row("ETH", DAYS[2], comp=1400, fcomp=719)
    code, text = run(good("BTC") + e + good("SOL"))
    check("first_compared 719 leaves a non-BTC date out", "| 1400 | " in text and "left out: too few minutes" in text
          and text.count("| counted |") == 8 and "6(b) ETH: PASS" in text, text)
    # BTC first_compared small does not matter
    b = good("BTC")
    b[2] = row("BTC", DAYS[2], fcomp=100)
    code, text = run(b + good("ETH") + good("SOL"))
    check("BTC ignores first_compared", text.count("| counted |") == 9, text)
    # a date with no row at all
    code, text = run(good("BTC")[:2] + good("ETH") + good("SOL"))
    check("date with no row is left out", "left out: no row" in text, text)

    # 5. fewer than two counted dates
    code, text = run(good("BTC") + good("ETH")[:1] + good("SOL"))
    check("one counted date: coin WAIT and overall WAIT", "6(b) ETH: WAIT" in text and "Item 6 overall: WAIT." in text
          and "6(a) BTC: PASS" in text, text)
    code, text = run(good("BTC")[:1] + good("ETH") + good("SOL"))
    check("BTC with one counted date: WAIT", "6(a) BTC: WAIT" in text and "Item 6 overall: WAIT." in text, text)
    # a failing coin with one date only is still WAIT, not FAIL
    code, text = run(good("BTC") + [row("ETH", DAYS[0], mat=30.0)] + good("SOL"))
    check("one bad date is WAIT not FAIL", "6(b) ETH: WAIT" in text, text)

    # 6. BTC with empty first cells is still counted
    b = [f"BTC,{d},1000,95.0,0.5,,," for d in DAYS]
    code, text = run(b + good("ETH") + good("SOL"))
    check("BTC with empty first cells counted", "6(a) BTC: PASS" in text and text.count("| counted |") == 9
          and "Item 6 overall: PASS." in text, text)

    # 7. a listed coin with no rows
    code, text = run(good("BTC") + good("ETH"))
    check("coin with no rows: WAIT with a note", "6(b) SOL: WAIT. The table has no rows for SOL." in text
          and "Item 6 overall: WAIT." in text, text)

    # 8. malformed rows
    bad = ["ETH,2026-11-12,abc,90,0.5,1000,40,20", "ETH,notadate,1000,90,0.5,1000,40,20", "ETH,2026-11-12",
           ",2026-11-12,1000,90,0.5,1000,40,20", row("ETH", DAYS[0])]
    code, text = run(good("BTC") + good("ETH") + bad + good("SOL"))
    check("malformed rows skipped and reported", code == 0 and "Skipped rows (5):" in text and "line " in text, text)
    check("malformed rows do not change the result", "6(b) ETH: PASS" in text and "Item 6 overall: PASS." in text)
    # a file with the wrong header does not crash
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "x.csv")
        with open(p, "w") as f:
            f.write("a,b\n1,2\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = t.main(["--daily", p, "--start", START, "--end", END])
        check("wrong header: no crash, WAIT", code == 0 and "Item 6 overall: WAIT." in buf.getvalue() and "missing column" in buf.getvalue())

    # 9. 6(a) FAIL wins over a WAIT elsewhere
    code, text = run([row("BTC", d, mat=2.0) for d in DAYS] + good("ETH"))
    check("6(a) FAIL beats a WAIT coin", "6(b) SOL: WAIT" in text and "Item 6 overall: FAIL." in text, text)

    # 10. overall PASS with one coin failing 6(b)
    code, text = run(good("BTC") + eth_with(2, mat=30.0) + good("SOL"))
    check("PASS with a 6(b) fail names the coin as leaving the list",
          "Item 6 overall: PASS." in text and "Failed 6(b): ETH." in text and "leave the list at release 3" in text, text)

    # 11. time zone: same output whatever the machine zone says
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "daily.csv")
        with open(p, "w") as f:
            f.write("\n".join([HEAD] + good("BTC") + good("ETH") + good("SOL")) + "\n")
        outs = []
        for tz in ("UTC", "Pacific/Kiritimati", "America/Los_Angeles"):
            env = dict(os.environ, TZ=tz)
            for a in ("--start 2026-11-11T11:54 --end 2026-11-13T12:00", "--start 2026-11-11T01:50Z --end 2026-11-14T01:50:00Z"):
                r = subprocess.run([sys.executable, SCRIPT, "--daily", p] + a.split(), env=env, capture_output=True, text=True)
                outs.append((a, r.returncode, r.stdout))
        for a in ("--start 2026-11-11T11:54 --end 2026-11-13T12:00", "--start 2026-11-11T01:50Z --end 2026-11-14T01:50:00Z"):
            same = {o[2] for o in outs if o[0] == a}
            check("time zone does not change the output: " + a, len(same) == 1 and all(o[1] == 0 for o in outs), outs)
        check("zone-less and Z times read alike", "2026-11-11 01:50 to 2026-11-14 01:50" in outs[1][2])
        # a non-UTC offset is converted, not read as local
        r = subprocess.run([sys.executable, SCRIPT, "--daily", p, "--start", "2026-11-11T05:00+05:00",
                            "--end", "2026-11-14T00:00Z"], env=dict(os.environ, TZ="Asia/Tokyo"), capture_output=True, text=True)
        check("offset times are converted to UTC", "2026-11-11 00:00 to 2026-11-14 00:00" in r.stdout, r.stdout[:200])

    # 12. a few real rows from the first collector table: about two hours per date, so everything waits
    real = [
        "BTC,2026-11-10,117,96.58,0.85,119,18.49,70.59", "BTC,2026-11-11,102,97.06,0.0,102,27.45,67.65",
        "ETH,2026-11-10,131,96.18,0.0,135,54.81,22.22", "ETH,2026-11-11,111,98.2,0.0,111,68.47,19.82",
        "SOL,2026-11-10,127,96.85,0.0,130,48.46,20.0", "SOL,2026-11-11,112,95.54,0.0,112,66.07,16.07",
        "XRP,2026-11-10,127,96.06,0.0,129,50.39,29.46", "XRP,2026-11-11,111,98.2,0.9,111,65.77,22.52",
        "LTC,2026-11-10,136,91.18,1.47,140,64.29,21.43", "LTC,2026-11-11,116,93.97,1.72,116,73.28,18.1",
        "ZEC,2026-11-10,136,81.62,5.15,140,60.0,24.29", "ZEC,2026-11-11,115,90.43,1.74,115,71.3,22.61",
    ]
    code, text = run(real, start="2026-11-11T01:50", end="2026-11-14T01:50", coins=t.DEFAULT_COINS)
    waits = [l for l in text.splitlines() if l.startswith("6(")]
    check("real rows: every coin WAIT", code == 0 and len(waits) == 6 and all(": WAIT." in l for l in waits)
          and "Item 6 overall: WAIT." in text, text)
    check("real rows: dates shown with hours inside", "| 22.2 |" in text and "| 24.0 |" in text and "| 1.8 |" in text, text)
    check("real rows: partial dates called outside the period", "outside the period" in text and "left out: too few minutes" in text)

    # argument errors give exit code 2; the report has no at-sign
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "d.csv")
        open(p, "w").write(HEAD + "\n")
        for name, args in [("missing file", ["--daily", os.path.join(tmp, "nope.csv"), "--start", START, "--end", END]),
                           ("bad time", ["--daily", p, "--start", "tomorrow", "--end", END]),
                           ("end not after start", ["--daily", p, "--start", END, "--end", START]),
                           ("missing argument", ["--daily", p, "--start", START])]:
            r = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True, text=True)
            check("exit code 2: " + name, r.returncode == 2, (r.returncode, r.stderr))
        out = os.path.join(tmp, "report.md")
        code, text = run(good("BTC") + good("ETH") + good("SOL"))
        r = subprocess.run([sys.executable, SCRIPT, "--daily", p, "--start", START, "--end", END, "--out", out],
                           capture_output=True, text=True)
        check("--out writes the same report that is printed", r.returncode == 0 and open(out).read() == r.stdout)
    check("report has no at-sign", chr(64) not in text)

    print("\n" + ("all passed" if not FAILS else f"{len(FAILS)} failed: {FAILS}"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
