"""Offline tests of run_pair.py with a stand-in for tb_smoke.py that prints canned output. Run:
python scripts/owner/step_pairs/test_run_pair.py (prints ok / FAIL per check, last line "N checks passed", non-zero exit
on any failure)."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_pair as rp       # noqa: E402

FIX = os.path.join(HERE, "fixtures")
FAILS = []
COUNT = [0]

RELEASE_INPUTS = '''ORDER_KEYS = ("order_path", "orders_rate", "place_workers")
INPUT_KEYS = ("newest_bar", "trades_coins", "stale_guard", "trades_rows", "trades_budget_s", "confirm_s",
              "candles_at_s") + ORDER_KEYS
'''

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


def output(m1, m2, n1=31, n2=31, extra1="", extra2="", hb1="", hb2=""):
    """Canned tb_smoke output: two runs with n timed steps each and the medians as printed on the median line."""
    def run(label, m, n, extra, hb):
        L = [f"===== {label}: running in process: Engine(mode=paper, config=bot/spot/config.json).run(30.0)",
             "event kinds: {'backfill': 1, 'heartbeat': 1}", "", "heartbeats:",
             hb or '{"ts": "2026-11-16T14:30:00", "kind": "heartbeat", "counts": {"tb_built": 125, "tb_fb_budget": 16}}',
             "", "errors and warnings:"]
        if extra:
            L.append(extra)
        L += ["", f"step timing ({label}; seconds after the minute, wall clock):",
              "minute  start_s  data_end_s  step_candles  step_trades  pass_candles"]
        for i in range(n):
            L.append(f" 14:{25 + i % 30:02d}      6.0       {m}            18           18             0")
        L.append(f"  median: step start 6.00 s, data step end {m} s (max 18.64 s); per step 18 candle and 18 trades "
                 "requests; 0 candle requests between steps")
        L += ["", "parity: venue candles ...", "coin  minutes  identical", " BTC       42         42", ""]
        return L
    return "\n".join(run("first", m1, n1, extra1, hb1) + run("second", m2, n2, extra2, hb2)
                     + ["", "data step end, median seconds after the minute: first run 1.0, second run 2.0"]) + "\n"


def code_dir(tmp, build_cfg, canned, exit_code=0, with_smoke=True):
    d = os.path.join(tmp, "code")
    os.makedirs(os.path.join(d, "bot", "spot"))
    open(os.path.join(d, "bot", "spot", "release_inputs.py"), "w").write(RELEASE_INPUTS)
    json.dump(build_cfg, open(os.path.join(d, "bot", "spot", "config.json"), "w"))
    if with_smoke:
        open(os.path.join(d, "bot", "spot", "tb_smoke.py"), "w").write(STAND_IN)
    cpath = os.path.join(tmp, "canned.txt")
    open(cpath, "w").write(canned)
    os.environ.update(CANNED=cpath, ARGV_OUT=os.path.join(tmp, "argv.json"), EXIT=str(exit_code))
    return d


BUILD = {"newest_bar": "trades", "trades_coins": ["BTC", "ETH", "DOGE"], "stale_guard": True, "trades_rows": "candle_after",
         "candles_at_s": 45, "order_path": "batch", "coins_disabled": ["X"], "capital": 250000}
MAIN = {"newest_bar": "trades", "trades_coins": ["BTC", "ETH"], "stale_guard": True, "order_path": "single",
        "coins_disabled": ["X"], "capital": 250000}


def go(tmp, order, canned, exit_code=0, build=BUILD, main=MAIN, with_smoke=True):
    d = code_dir(tmp, build, canned, exit_code, with_smoke)
    mp = os.path.join(tmp, "main.json")
    json.dump(main, open(mp, "w"))
    out = os.path.join(tmp, "out")
    with contextlib.redirect_stdout(io.StringIO()):
        res = rp.pair(d, mp, order, 30, out)
    files = sorted(os.listdir(out)) if os.path.isdir(out) else []
    return res, files, out


def argv_of(tmp):
    return json.load(open(os.path.join(tmp, "argv.json")))


def test_argv():
    with tempfile.TemporaryDirectory() as tmp:
        res, files, out = go(tmp, "ab", output("14.88", "9.70"))
        a = argv_of(tmp)
        check("ab: tb_smoke is called with --parity, the length and the build's config file",
              a[:6] == ["--parity", "--minutes", "30", "--config", os.path.join("bot", "spot", "config.json"), "--state-dir"], a[:7])
        sets = [a[i + 1] for i, x in enumerate(a) if x == "--set"]
        thens = [a[i + 1] for i, x in enumerate(a) if x == "--then"]
        check("ab: --set items are release 3's values (a removed key is null, a list is JSON)",
              sets == ['trades_coins=["BTC","ETH"]', "trades_rows=null", "candles_at_s=null"], sets)
        check("ab: --then items are the build's values",
              thens == ['trades_coins=["BTC","ETH","DOGE"]', 'trades_rows="candle_after"', "candles_at_s=45"], thens)
        check("ab: order keys are not swapped and equal keys are not passed",
              not any(x.startswith(("order_path", "newest_bar", "stale_guard")) for x in sets + thens))
        check("ab: --set items come before --then items", a.index("--set") < a.index("--then"))
        check("ab: first run is release 3, second the build", [r["inputs"] for r in res["runs"]] == ["release3", "build"])
        check("ab: one result file named after the UTC start", len(files) == 1 and files[0].startswith("pair_")
              and files[0].endswith("Z.json") and len(files[0]) == len("pair_20261116T1407Z.json"), files)
    with tempfile.TemporaryDirectory() as tmp:
        res, files, out = go(tmp, "ba", output("9.70", "14.88"))
        a = argv_of(tmp)
        check("ba: no --set, --then items are release 3's values",
              "--set" not in a and [a[i + 1] for i, x in enumerate(a) if x == "--then"]
              == ['trades_coins=["BTC","ETH"]', "trades_rows=null", "candles_at_s=null"], a)
        check("ba: first run is the build, second release 3", [r["inputs"] for r in res["runs"]] == ["build", "release3"])
    # a key the build lacks and release 3 has: removed in the build's run
    with tempfile.TemporaryDirectory() as tmp:
        build = dict(BUILD)
        build.pop("candles_at_s")
        main = dict(MAIN, candles_at_s=30, confirm_s=2.5)
        res, files, out = go(tmp, "ab", output("1.00", "2.00"), build=build, main=main)
        a = argv_of(tmp)
        check("a key only release 3 has: --set gives its value, --then removes it",
              "candles_at_s=30" in a and "candles_at_s=null" in a and a.index("candles_at_s=30") < a.index("candles_at_s=null")
              and "confirm_s=2.5" in a and "confirm_s=null" in a)
        keys = {k["key"]: k for k in res["keys"]}
        check("keys: both values recorded, differs flag", keys["candles_at_s"]["release3"] == 30 and keys["candles_at_s"]["build"] is None
              and keys["candles_at_s"]["differs"] and not keys["stale_guard"]["differs"]
              and [k["key"] for k in res["keys"]] == ["newest_bar", "trades_coins", "stale_guard", "trades_rows", "trades_budget_s",
                                                      "confirm_s", "candles_at_s"], keys)
    # plan() directly: argv without running anything
    pl = rp.plan(BUILD, MAIN, ("trades_coins", "trades_rows"), ("trades_coins", "trades_rows", "order_path", "candles_at_s", "newest_bar", "stale_guard"), "ba")
    check("plan: ba", pl["set"] == [] and pl["then"] == ['trades_coins=["BTC","ETH"]', "trades_rows=null"]
          and pl["runs"] == ("build", "release3"))
    check("smoke_argv builds the exact list", rp.smoke_argv(30, "/s", ["a=1"], ["b=null"])[1:]
          == [os.path.join("bot", "spot", "tb_smoke.py"), "--parity", "--minutes", "30", "--config",
              os.path.join("bot", "spot", "config.json"), "--state-dir", "/s", "--set", "a=1", "--then", "b=null"])


def test_real_outputs():
    for name, a, b, diff, exact, n2 in (("real_1.txt", "14.88", "9.70", -5.18, "-5.18", 30), ("real_2.txt", "15.35", "11.37", -3.98, "-3.98", 31)):
        text = open(os.path.join(FIX, name)).read()
        runs = rp.split_runs(text)
        check(f"{name}: two runs found", len(runs) == 2, len(runs))
        r1, r2 = rp.parse_run(runs[0], "release3"), rp.parse_run(runs[1], "build")
        check(f"{name}: medians as printed on the median lines", r1["data_end_median_text"] == a and r2["data_end_median_text"] == b
              and r1["data_end_median_s"] == float(a) and r2["data_end_median_s"] == float(b), (r1, r2))
        check(f"{name}: timed steps (rows of the table), step medians", r1["steps_timed"] == 31 and r2["steps_timed"] == n2
              and r1["step_candles_median"] == 18.0 and r1["step_trades_median"] == 18.0 and r1["pass_candles_median"] == 0.0
              and r2["step_candles_median"] == 0.0 and r2["pass_candles_median"] == 18.0, (r1, r2))
        check(f"{name}: not refused, not limited (the real heartbeat has tb_fb_budget and tb_close_diff)",
              not r1["refused"] and not r1["limited"] and not r2["refused"] and not r2["limited"])
        check(f"{name}: counts, and the difference is the build's minus release 3's, exactly",
              rp.judge([r1, r2], 0) == (True, None) and rp.difference([r1, r2]) == (diff, exact), rp.difference([r1, r2]))
        # the fixture through the whole wrapper, order ab: first run is release 3
        with tempfile.TemporaryDirectory() as tmp:
            res, files, out = go(tmp, "ab", text)
            on_disk = json.load(open(os.path.join(out, files[0])))
            check(f"{name}: wrapper result counts with build minus release 3 {exact}", res["counts"] and res["why_not"] is None
                  and on_disk["build_minus_release3_text"] == exact and on_disk["build_minus_release3_s"] == diff
                  and on_disk["runs"][0]["data_end_median_text"] == a, on_disk["why_not"])
    r = rp.parse_run(rp.split_runs(open(os.path.join(FIX, "real_1.txt")).read())[0], "x")
    check("max of the data step end is read", r["data_end_max_s"] == 18.64, r)


def test_signs():
    with tempfile.TemporaryDirectory() as tmp:        # the build is slower: positive in both orders
        res, _, _ = go(tmp, "ab", output("10.00", "10.50"))
        check("ab: second run (build) 10.50 against first (release 3) 10.00: +0.50", res["build_minus_release3_text"] == "0.50"
              and res["build_minus_release3_s"] == 0.5, res["build_minus_release3_text"])
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ba", output("10.50", "10.00"))
        check("ba: first run (build) 10.50 against second (release 3) 10.00: +0.50", res["build_minus_release3_text"] == "0.50")
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ba", output("9.70", "14.88"))
        check("ba: build faster is negative", res["build_minus_release3_text"] == "-5.18")
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ab", output("10.00", "10.00"))
        check("equal medians give 0.00 and still count", res["counts"] and res["build_minus_release3_text"] == "0.00")


def test_not_counted():
    def bad(order, canned, why, name, exit_code=0, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            res, files, out = go(tmp, order, canned, exit_code, **kw)
            check(name, res["counts"] is False and why in (res["why_not"] or "") and len(files) == 1, (res["why_not"], files))
            return res
    bad("ab", output("10.00", "10.00", n1=19), "release3 run has 19 timed steps", "19 timed steps in the first run: not counted")
    bad("ab", output("10.00", "10.00", n2=19), "build run has 19 timed steps", "19 timed steps in the second run: not counted")
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ab", output("10.00", "10.00", n1=20, n2=20))
        check("exactly 20 timed steps in each run counts", res["counts"])
    bad("ba", output("10.00", "10.00", n1=19), "build run has 19", "order ba: the build's run is the first one")
    bad("ab", output("10.00", "10.00", extra2="REFUSED (parity fetch stopped): BTC: Refused('HTTP 403 on https://x')"),
        "build run met a refusal", "a refusal in the second run: not counted")
    res = bad("ab", output("10.00", "10.00", extra1="REFUSED (parity fetch stopped): BTC: Limited('HTTP 429 on https://x')"),
              "release3 run met a refusal", "a rate limit on the parity fetch: not counted")
    check("a 429 sets both flags", res["runs"][0]["refused"] and res["runs"][0]["limited"])
    bad("ab", output("10.00", "10.00", extra1='{"ts": "x", "kind": "warning", "message": "rate limit reached"}'),
        "met a", "an engine warning about a rate limit: not counted")
    bad("ab", output("10.00", "10.00", hb2='{"kind": "heartbeat", "counts": {"tb_fb_limited": 3}}'),
        "build run met a rate limit", "tb_fb_limited above 0 in a heartbeat: not counted")
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ab", output("10.00", "10.00", hb2='{"kind": "heartbeat", "counts": {"tb_fb_limited": 0}}'))
        check("tb_fb_limited 0 is not a rate limit", res["counts"])
    bad("ab", output("10.00", "10.00"), "exited with code 1", "a non-zero exit code: not counted", exit_code=1)
    bad("ab", output("10.00", "10.00"), "exited with code 3", "exit code 3 says refusal or rate limit", exit_code=3)
    bad("ab", "this is not tb_smoke output\nat all\n", "expected 2 runs", "garbage output: not counted")
    bad("ab", "", "expected 2 runs", "empty output: not counted")
    bad("ab", output("10.00", "10.00").replace("data step end 10.00 s", "data step end nan s"), "no median line", "an unreadable median: not counted")
    bad("ab", output("10.00", "10.00", n1=0), "0 timed steps", "no steps: not counted")
    bad("ab", output("10.00", "10.00"), "tb_smoke.py not found", "tb_smoke missing: not counted", with_smoke=False)
    # configs differing outside INPUT_KEYS: no run at all
    with tempfile.TemporaryDirectory() as tmp:
        res, files, out = go(tmp, "ab", output("10.00", "10.00"), main=dict(MAIN, capital=100000))
        check("configs differ outside INPUT_KEYS: pair does not run, reason written", res["counts"] is False
              and "differ outside INPUT_KEYS: capital" in res["why_not"] and not os.path.exists(os.path.join(tmp, "argv.json"))
              and len(files) == 1 and res["runs"] == [], res["why_not"])
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ab", output("10.00", "10.00"), main=dict(MAIN, extra_key=1))
        check("a key only one file has, outside INPUT_KEYS, also stops it", not res["counts"] and "extra_key" in res["why_not"])
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "ab", output("10.00", "10.00"), main=dict(MAIN, order_path="batch", orders_rate=5))
        check("order keys may differ: they are inside INPUT_KEYS and not swapped", res["counts"])
    with tempfile.TemporaryDirectory() as tmp:
        res, _, _ = go(tmp, "xy", output("10.00", "10.00"))
        check("a bad order is a reason, not an exception", not res["counts"] and "ab or ba" in res["why_not"])
    # never raises: a missing main config, a missing code dir, an unwritable output folder
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            r1 = rp.pair(os.path.join(tmp, "nope"), os.path.join(tmp, "nomain.json"), "ab", 30, os.path.join(tmp, "o"))
            d = code_dir(tmp, BUILD, output("1.0", "1.0"))
            r2 = rp.pair(d, os.path.join(tmp, "nomain.json"), "ab", 30, os.path.join(tmp, "o2"))
            r3 = rp.pair(d, os.path.join(tmp, "nomain.json"), "ab", 30, os.path.join(tmp, "main.json", "x"))
        check("never raises: missing code folder and missing main config", not r1["counts"] and "release_inputs.py not found" in r1["why_not"]
              and not r2["counts"] and "main config" in r2["why_not"] and r3["counts"] is False)
    # the command line exits 0 on failure
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, os.path.join(HERE, "run_pair.py"), "--code", os.path.join(tmp, "nope"), "--main-config", "x",
                            "--order", "ab", "--out", os.path.join(tmp, "o")], capture_output=True, text=True)
        check("command line: failure still exits 0 and writes the file", r.returncode == 0 and len(os.listdir(os.path.join(tmp, "o"))) == 1, r.stderr[-300:])


def test_misc():
    with tempfile.TemporaryDirectory() as tmp:
        res, _, out = go(tmp, "ab", output("10.00", "10.00"))
        check("result fields", all(k in res for k in ("utc_start", "utc_end", "order", "minutes", "code_commit", "keys", "runs",
                                                      "build_minus_release3_s", "counts", "why_not")) and res["code_commit"] is None
              and res["utc_start"].endswith("Z") and res["order"] == "ab" and res["minutes"] == 30)
        check("run entries have the listed fields", set(res["runs"][0]) >= {"inputs", "data_end_median_s", "data_end_median_text",
                                                                           "data_end_max_s", "steps_timed", "step_candles_median",
                                                                           "step_trades_median", "pass_candles_median", "refused", "limited"})
    # the commit of a real git folder
    with tempfile.TemporaryDirectory() as tmp:
        d = code_dir(tmp, BUILD, output("1.0", "1.0"))
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t.example", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t.example")
        subprocess.run(["git", "init", "-q", d], check=True, env=env)
        subprocess.run(["git", "-C", d, "add", "-A"], check=True, env=env)
        subprocess.run(["git", "-C", d, "commit", "-q", "-m", "x"], check=True, env=env)
        c = rp.git_commit(d)
        check("code_commit is the 40-character hash", c is not None and len(c) == 40 and c == subprocess.run(
            ["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip())
    check("the fixtures hold no at-sign", all(chr(64) not in open(os.path.join(FIX, f)).read() for f in os.listdir(FIX)))


def main():
    for t in (test_argv, test_real_outputs, test_signs, test_not_counted, test_misc):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
