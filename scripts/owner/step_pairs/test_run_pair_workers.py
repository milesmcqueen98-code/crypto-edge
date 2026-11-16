"""Offline tests of run_pair_workers.py with a stand-in for tb_smoke.py that prints canned output. Run:
python scripts/owner/step_pairs/test_run_pair_workers.py (prints ok / FAIL per check, last line "N checks passed", non-zero
exit on any failure).

The fixtures fixtures/synthetic_tw_*.txt are built from the print statements of the candidate's bot/spot/tb_smoke.py
(branch owner/trades-workers: the step table with its trades_s and fb_budget columns, the median line, the trades pass
line, the trades requests line, the parity table, the closing lines); they are not taken from a real run. A NaN cell is
in the first row of every table, as the real table has when a step has no data end.

Notes on the patterns: the refusal pattern is run_pair.py's own (imported). The rate-limit pattern is this tool's own and
has no bare 429: a heartbeat counter of 429, a price of 429.5 or a time ending in .429 must not mark a run limited, while
Limited(, HTTP 429, rate limit, too many requests and a tb_fb_limited counter of 1 or more do. The step table rows are
left out of the search, as in run_pair.py."""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_pair as rp               # noqa: E402
import run_pair_workers as rw       # noqa: E402

FIX = os.path.join(HERE, "fixtures")
FAILS = []
COUNT = [0]

RELEASE_INPUTS = '''ORDER_KEYS = ("order_path", "orders_rate", "place_workers")
INPUT_KEYS = ("newest_bar", "trades_coins", "stale_guard", "trades_rows", "trades_budget_s", "confirm_s",
              "candles_at_s", "trades_workers") + ORDER_KEYS
'''
RELEASE_INPUTS_OLD = RELEASE_INPUTS.replace(", \"trades_workers\"", "")

STAND_IN = '''import json, os, sys
open(os.environ["ARGV_OUT"], "w").write(json.dumps(sys.argv[1:]))
sys.stdout.write(open(os.environ["CANNED"]).read())
sys.exit(int(os.environ.get("EXIT", "0")))
'''


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


def fixture(name):
    return open(os.path.join(FIX, name)).read()


def code_dir(tmp, canned, exit_code=0, with_smoke=True, with_config=True, inputs=RELEASE_INPUTS):
    d = os.path.join(tmp, "code")
    os.makedirs(os.path.join(d, "bot", "spot"))
    if inputs is not None:
        open(os.path.join(d, "bot", "spot", "release_inputs.py"), "w").write(inputs)
    if with_config:
        json.dump({"newest_bar": "trades", "trades_workers": 3}, open(os.path.join(d, "bot", "spot", "config.tw.json"), "w"))
    if with_smoke:
        open(os.path.join(d, "bot", "spot", "tb_smoke.py"), "w").write(STAND_IN)
    cpath = os.path.join(tmp, "canned.txt")
    open(cpath, "w").write(canned)
    os.environ.update(CANNED=cpath, ARGV_OUT=os.path.join(tmp, "argv.json"), EXIT=str(exit_code))
    return d


def go(tmp, order, canned, exit_code=0, **kw):
    d = code_dir(tmp, canned, exit_code, **kw)
    out = os.path.join(tmp, "out")
    with contextlib.redirect_stdout(io.StringIO()):
        res = rw.pair(d, order, 30, out)
    files = sorted(os.listdir(out)) if os.path.isdir(out) else []
    return res, files, out


def argv_of(tmp):
    return json.load(open(os.path.join(tmp, "argv.json")))


def drop_rows(text, keep):
    """The text with each step table cut to its first `keep` rows (the first row is the NaN row)."""
    out, n = [], 0
    for l in text.splitlines():
        if rw.ROW_RX.match(l):
            n += 1
            if n > keep:
                continue
        else:
            n = 0 if not l.strip() else n
        out.append(l)
    return "\n".join(out) + "\n"


def by_label(res):
    return {r["label"]: r for r in res["runs"]}


# ---------------------------------------------------------------- tests
def test_argv():
    with tempfile.TemporaryDirectory() as tmp:
        res, files, out = go(tmp, "ab", fixture("synthetic_tw_ab.txt"))
        a = argv_of(tmp)
        check("ab: tb_smoke is called with --parity, the length and the candidate's config.tw.json",
              a[:6] == ["--parity", "--minutes", "30", "--config", os.path.join("bot", "spot", "config.tw.json"), "--state-dir"], a[:7])
        check("ab: --set trades_workers=1 then --then trades_workers=3, nothing else",
              a[7:] == ["--set", "trades_workers=1", "--then", "trades_workers=3"], a)
        check("ab: first run is one, second three", [(r["workers"], r["label"]) for r in res["runs"]] == [(1, "one"), (3, "three")])
        check("one result file named after the UTC start, mode workers", len(files) == 1 and re.fullmatch(r"pair_\d{8}T\d{4}Z\.json", files[0])
              and res["mode"] == "workers" and json.load(open(os.path.join(out, files[0])))["mode"] == "workers", files)
    with tempfile.TemporaryDirectory() as tmp:
        res, files, out = go(tmp, "ba", fixture("synthetic_tw_ba.txt"))
        a = argv_of(tmp)
        check("ba: --set trades_workers=3 then --then trades_workers=1", a[7:] == ["--set", "trades_workers=3", "--then", "trades_workers=1"], a)
        check("ba: first run is three, second one", [(r["workers"], r["label"]) for r in res["runs"]] == [(3, "three"), (1, "one")])
        check("argv is recorded in the result", res["argv"][:2] == [os.path.join("bot", "spot", "tb_smoke.py"), "--parity"] and "--then" in res["argv"])
    check("smoke_argv builds the exact list", rw.smoke_argv(30, "/s", ["a=1"], ["b=3"])[1:]
          == [os.path.join("bot", "spot", "tb_smoke.py"), "--parity", "--minutes", "30", "--config",
              os.path.join("bot", "spot", "config.tw.json"), "--state-dir", "/s", "--set", "a=1", "--then", "b=3"])
    pl = rw.plan("ab")
    check("plan ab / ba", pl["set"] == ["trades_workers=1"] and pl["then"] == ["trades_workers=3"]
          and rw.plan("ba")["runs"] == ((3, "three"), (1, "one")))
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "xy", fixture("synthetic_tw_ab.txt"))
        check("a bad order is a reason, not an exception", not res["counts"] and "ab or ba" in res["why_not"])


def test_fields():
    for order, name, first in (("ab", "synthetic_tw_ab.txt", "one"), ("ba", "synthetic_tw_ba.txt", "three")):
        with tempfile.TemporaryDirectory() as tmp:
            res, files, out = go(tmp, order, fixture(name))
            on_disk = json.load(open(os.path.join(out, files[0])))
            r = by_label(on_disk)
            o, t = r["one"], r["three"]
            check(f"{order}: pair counts, no reason", res["counts"] is True and res["why_not"] is None, res["why_not"])
            check(f"{order}: first run in the file is {first}", on_disk["runs"][0]["label"] == first)
            check(f"{order}: data step medians as printed (text and float) and maxima",
                  o["data_end_median_text"] == "9.93" and o["data_end_median_s"] == 9.93 and o["data_end_max_s"] == 10.86
                  and t["data_end_median_text"] == "9.33" and t["data_end_median_s"] == 9.33 and t["data_end_max_s"] == 10.26, (o, t))
            check(f"{order}: timed steps leave out the row with a NaN data end", o["steps_timed"] == 30 and t["steps_timed"] == 30)
            check(f"{order}: trades pass median and longest (text and float), budget fallbacks as ints",
                  o["trades_pass_median_text"] == "5.80" and o["trades_pass_median_s"] == 5.8 and o["trades_pass_longest_text"] == "6.60"
                  and o["trades_pass_longest_s"] == 6.6 and o["fb_budget"] == 2
                  and t["trades_pass_median_text"] == "3.40" and t["trades_pass_longest_text"] == "4.20" and t["fb_budget"] == 0
                  and isinstance(o["fb_budget"], int), (o, t))
            check(f"{order}: peak per second", o["peak_per_second"] == 7 and t["peak_per_second"] == 8
                  and isinstance(t["peak_per_second"], int))
            check(f"{order}: parity rows summed over the coins (the answer_gen cell with a space does not shift columns)",
                  (o["rows_compared"], o["rows_differ"]) == (126, 1) and (t["rows_compared"], t["rows_differ"]) == (126, 0), (o, t))
            check(f"{order}: not refused, not limited (the heartbeat has tb_fb_limited 0)",
                  not o["refused"] and not o["limited"] and not t["refused"] and not t["limited"])
            check(f"{order}: three minus one for the data step (float and exact text), and for the longest pass",
                  on_disk["three_minus_one_text"] == "-0.60" and on_disk["three_minus_one_s"] == -0.6
                  and on_disk["longest_three_minus_one_text"] == "-2.40" and on_disk["longest_three_minus_one_s"] == -2.4,
                  (on_disk["three_minus_one_text"], on_disk["longest_three_minus_one_text"]))
            check(f"{order}: result fields", all(k in on_disk for k in (
                "mode", "utc_start", "utc_end", "order", "minutes", "code_commit", "argv", "runs", "three_minus_one_s",
                "three_minus_one_text", "longest_three_minus_one_text", "counts", "why_not"))
                  and on_disk["order"] == order and on_disk["minutes"] == 30 and on_disk["utc_start"].endswith("Z"))
            check(f"{order}: run entries have the listed fields", set(o) >= {
                "workers", "label", "data_end_median_text", "data_end_median_s", "data_end_max_s", "steps_timed",
                "trades_pass_median_text", "trades_pass_median_s", "trades_pass_longest_text", "trades_pass_longest_s",
                "fb_budget", "peak_per_second", "rows_compared", "rows_differ", "refused", "limited"})
    text = fixture("synthetic_tw_ab.txt")
    check("the fixtures hold a NaN cell in the step table and no at-sign", "NaN" in text and all(
        chr(64) not in open(os.path.join(FIX, f)).read() for f in os.listdir(FIX)))
    check("the seven-column rows are not read by run_pair.py's five-column pattern",
          not any(rp.ROW_RX.match(l) for l in text.splitlines()) and sum(1 for l in text.splitlines() if rw.ROW_RX.match(l)) == 62)
    runs = rp.split_runs(text)
    check("split_runs finds two runs", len(runs) == 2)
    # a None cell instead of NaN reads the same
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ab", text.replace("NaN", "None"))
        check("None cells read like NaN", res["counts"] and by_label(res)["one"]["steps_timed"] == 30, res["why_not"])


def test_decimals():
    base = fixture("synthetic_tw_ab.txt")
    with tempfile.TemporaryDirectory() as tmp:
        t = base.replace("data step end 9.93 s", "data step end 10.10 s").replace("data step end 9.33 s", "data step end 9.90 s")
        res, _, _ = go(tmp, "ab", t)
        check("exact decimal: 9.90 minus 10.10 is -0.20 (no float noise)", res["three_minus_one_text"] == "-0.20"
              and res["three_minus_one_s"] == -0.2, res["three_minus_one_text"])
    with tempfile.TemporaryDirectory() as tmp:
        t = base.replace("data step end 9.93 s", "data step end 0.30 s").replace("data step end 9.33 s", "data step end 0.10 s")
        res, _, _ = go(tmp, "ab", t)
        check("exact decimal: 0.10 minus 0.30", res["three_minus_one_text"] == "-0.20")
    with tempfile.TemporaryDirectory() as tmp:
        t = base.replace("data step end 9.33 s", "data step end 9.93 s")
        res, _, _ = go(tmp, "ab", t)
        check("equal medians give 0.00 and still count", res["counts"] and res["three_minus_one_text"] == "0.00")
    with tempfile.TemporaryDirectory() as tmp:
        t = base.replace("data step end 9.33 s", "data step end 10.53 s")
        res, _, _ = go(tmp, "ab", t)
        check("three slower than one is positive (+0.60)", res["three_minus_one_text"] == "0.60" and res["three_minus_one_s"] == 0.6)
    with tempfile.TemporaryDirectory() as tmp:
        t = base.replace("longest 6.60 s", "longest 0.30 s").replace("longest 4.20 s", "longest 0.10 s")
        res, _, _ = go(tmp, "ab", t)
        check("exact decimal for the longest pass: 0.10 minus 0.30", res["longest_three_minus_one_text"] == "-0.20"
              and res["longest_three_minus_one_s"] == -0.2)
    with tempfile.TemporaryDirectory() as tmp:         # in order ba the labels, not the position, decide the sign
        t = fixture("synthetic_tw_ba.txt")
        res, _, _ = go(tmp, "ba", t)
        check("ba: three's median (first run) minus one's (second run)", res["three_minus_one_text"] == "-0.60")


def test_not_counted():
    ab = fixture("synthetic_tw_ab.txt")

    def bad(order, canned, why, name, exit_code=0, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            res, files, out = go(tmp, order, canned, exit_code, **kw)
            check(name, res["counts"] is False and why in (res["why_not"] or "") and len(files) == 1, (res["why_not"], files))
            return res
    res = bad("ab", fixture("synthetic_tw_no_pass.txt"), "not read for the three run: trades_pass_median_text",
              "a missing trades-pass line: not counted, the figures are null")
    t = by_label(res)["three"]
    check("missing trades-pass line: its fields and the longest difference are null, the data step is still read",
          t["trades_pass_median_text"] is None and t["trades_pass_longest_s"] is None and t["fb_budget"] is None
          and t["data_end_median_text"] == "9.33" and res["longest_three_minus_one_text"] is None
          and res["three_minus_one_text"] == "-0.60" and t["peak_per_second"] == 8)
    bad("ab", re.sub(r"  trades requests \(.*\n", "", ab, count=1), "not read for the one run: peak_per_second", "a missing peak line: not counted")
    bad("ab", re.sub(r"\ncoin  minutes.*?\n\n", "\n", ab, count=1, flags=re.S), "not read for the one run: rows_compared", "a missing parity table: not counted")
    res = bad("ab", fixture("synthetic_tw_refused.txt"), "three run met a refusal", "a refusal in the second run: not counted")
    check("a refusal sets refused and not limited", by_label(res)["three"]["refused"] and not by_label(res)["three"]["limited"])
    res = bad("ab", fixture("synthetic_tw_limited.txt"), "three run met a refusal", "a rate limit on the parity fetch: not counted")
    check("a 429 on the parity fetch sets both flags", by_label(res)["three"]["refused"] and by_label(res)["three"]["limited"])
    bad("ba", fixture("synthetic_tw_refused.txt"), "one run met a refusal", "order ba: the second run is one")
    bad("ab", ab.replace('"tb_fb_limited": 0', '"tb_fb_limited": 3', 1), "one run met a rate limit", "tb_fb_limited above 0 in a heartbeat: not counted")
    bad("ab", ab.replace("errors and warnings:\n", 'errors and warnings:\n{"kind": "warning", "message": "rate limit reached"}\n', 1),
        "one run met a rate limit", "an engine warning about a rate limit: not counted")
    bad("ab", fixture("synthetic_tw_short.txt"), "one run has 19 timed steps, 20 needed", "19 timed steps: not counted")
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ab", drop_rows(ab, 21))
        check("exactly 20 timed steps in each run counts", res["counts"] and by_label(res)["one"]["steps_timed"] == 20, (res["why_not"], res["runs"][0]["steps_timed"]))
    bad("ab", drop_rows(ab, 20), "one run has 19 timed steps", "19 timed steps by cutting the table: not counted")
    bad("ba", drop_rows(ab, 20), "three run has 19", "order ba: the first run is three")
    bad("ab", ab, "exited with code 1", "a non-zero exit code: not counted", exit_code=1)
    bad("ab", ab, "exited with code 3", "exit code 3 says refusal or rate limit", exit_code=3)
    bad("ab", "this is not tb_smoke output\nat all\n", "expected 2 runs", "garbage output: not counted")
    bad("ab", "", "expected 2 runs", "empty output: not counted")
    bad("ab", ab.replace("data step end 9.93 s", "data step end nan s"), "no median line", "an unreadable median: not counted")
    bad("ab", ab.replace("budget fallbacks (tb_fb_budget) 2", "budget fallbacks (tb_fb_budget) many"), "fb_budget", "an unreadable fallback count: not counted")
    bad("ab", ab, "tb_smoke.py not found", "tb_smoke missing: not counted", with_smoke=False)
    # the candidate's files
    with tempfile.TemporaryDirectory() as tmp:
        res, files, out = go(tmp, "ab", ab, with_config=False)
        check("config.tw.json missing: pair does not run, reason written", res["counts"] is False and "config.tw.json not found" in res["why_not"]
              and not os.path.exists(os.path.join(tmp, "argv.json")) and len(files) == 1 and res["runs"] == [], res["why_not"])
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ab", ab, inputs=RELEASE_INPUTS_OLD)
        check("trades_workers not in INPUT_KEYS: pair does not run", res["counts"] is False and "trades_workers is not in INPUT_KEYS" in res["why_not"]
              and not os.path.exists(os.path.join(tmp, "argv.json")), res["why_not"])
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ab", ab, inputs=None)
        check("release_inputs.py missing: pair does not run", not res["counts"] and "release_inputs.py not found" in res["why_not"])
    # never raises
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            r1 = rw.pair(os.path.join(tmp, "nope"), "ab", 30, os.path.join(tmp, "o"))
            d = code_dir(tmp, ab)
            r3 = rw.pair(d, "ab", 30, os.path.join(tmp, "main.json", "x"))
        check("never raises: missing code folder, unwritable output folder", not r1["counts"] and "release_inputs.py not found" in r1["why_not"]
              and os.path.isfile(os.path.join(tmp, "o", os.listdir(os.path.join(tmp, "o"))[0])) and r3["counts"] is True)
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, os.path.join(HERE, "run_pair_workers.py"), "--code", os.path.join(tmp, "nope"),
                            "--order", "ab", "--out", os.path.join(tmp, "o")], capture_output=True, text=True)
        check("command line: failure still exits 0 and writes the file", r.returncode == 0 and len(os.listdir(os.path.join(tmp, "o"))) == 1, r.stderr[-300:])
        r = subprocess.run([sys.executable, os.path.join(HERE, "run_pair_workers.py"), "--code", "x", "--order", "ba", "--dry-run"],
                           capture_output=True, text=True)
        d = json.loads(r.stdout)
        check("command line: --dry-run prints the plan", r.returncode == 0 and d["set"] == ["trades_workers=3"] and d["then"] == ["trades_workers=1"], r.stdout[-200:])


def test_patterns():
    """The tool's own rate-limit pattern (no bare 429) and the imported refusal pattern."""
    check("refusal pattern is run_pair.py's own object, the limited pattern is the tool's own", rw.rp.REFUSED_RX is rp.REFUSED_RX
          and rw.LIMITED_RX is not rp.LIMITED_RX and rw.rp.MEDIAN_RX is rp.MEDIAN_RX)
    ab = fixture("synthetic_tw_ab.txt")

    def flags(text):
        with tempfile.TemporaryDirectory() as tmp:
            res, _, _ = go(tmp, "ab", text)
            return by_label(res)["one"]["limited"], by_label(res)["one"]["refused"]
    check("the clean fixture is neither limited nor refused", flags(ab) == (False, False))
    not_marked = {
        "a heartbeat counter of 429": ab.replace('"tb_built": 125', '"tb_built": 429', 1),
        "a price of 429.5 in an event line": ab.replace("event kinds:", 'event kinds: {"price": 429.5}', 1),
        "a step_s value of 7.429": ab.replace('"trades": [5.125, 7.5]', '"trades": [5.125, 7.429]', 1),
        "a summary median of 2.429": ab.replace("trades pass, first run: median 5.8 s", "trades pass, first run: median 2.429 s", 1),
        "the text 'at most 7 sent'": ab.replace("errors and warnings:\n", "errors and warnings:\nat most 7 sent\n", 1),
        "tb_fb_limited 0": ab,
        "4290 and 1429": ab.replace('"tb_built": 125', '"tb_built": 4290, "x": 1429', 1),
        "a .429 in a step table row": ab.replace("14:26      6.0        9.31             0           18             0       5.4        0.0",
                                                  "14:26      6.0        9.31             0           18             0     7.429        0.0", 1),
        "the new lines with a 4.29 s pass and 29 fallbacks": ab.replace(
            "median 5.80 s, longest 6.60 s; budget fallbacks (tb_fb_budget) 2", "median 4.29 s, longest 6.42 s; budget fallbacks (tb_fb_budget) 29", 1)}
    for name, text in not_marked.items():
        check(f"does NOT mark a run limited: {name}", ("429" in text or "tb_fb_limited" in text) and flags(text) == (False, False), flags(text))
    marked = {
        "Limited('HTTP 429 on https://x')": "Limited('HTTP 429 on https://x')", "HTTP 429": "got HTTP 429 back", "rate limit": "rate limit reached",
        "rate-limit": "a rate-limit answer", "Too Many Requests": "Too Many Requests", '"tb_fb_limited": 1': '{"counts": {"tb_fb_limited": 1}}',
        '"tb_fb_limited": 12': '{"counts": {"tb_fb_limited": 12}}'}
    for name, line in marked.items():
        text = ab.replace("errors and warnings:\n", "errors and warnings:\n" + line + "\n", 1)
        check(f"marks a run limited: {name}", flags(text)[0] is True and flags(text)[1] is False, flags(text))
    text = ab.replace("errors and warnings:\n", "errors and warnings:\nREFUSED (parity fetch stopped): BTC: Limited('HTTP 429 ...')\n", 1)
    check("REFUSED (parity fetch stopped): Limited('HTTP 429 ...') sets both flags", flags(text) == (True, True))
    check("the word refus does not appear in the new lines", not rp.REFUSED_RX.search(
        "\n".join(l for l in ab.splitlines() if "trades pass" in l or "trades requests" in l)))


def main():
    for t in (test_argv, test_fields, test_decimals, test_not_counted, test_patterns):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
