"""Offline tests of run_alt.py with a fake engine and a fake market. Run: python scripts/owner/workers_alt/test_run_alt.py
(prints ok / FAIL per check, last line "N checks passed", non-zero exit on any failure)."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_alt as ra        # noqa: E402

FAILS = []
COUNT = [0]


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


BASE = int(datetime(2026, 11, 17, 4, 0, tzinfo=timezone.utc).timestamp())      # minute number even
assert (BASE // 60) % 2 == 0
KEYS = [ra.epoch_key(BASE + 60 * i) for i in range(200)]


def bar(x=1.0):
    return (x, x + 1, x - 1, x + 0.5, 10.0)


class Fake:
    """A fake engine whose run() calls step() n times, one per minute from BASE + start_offset. script[i] describes step i:
    pass_s, inc (counter increases), peak, bars ({coin: tuple or None}), err, skip_pass (no pass), data (mark data), raise_at."""
    def __init__(self, script, coins=("ETH", "SOL"), clock=None, start_offset=0, fail_at=None):
        self.script, self.coins, self.trades_coins, self.clock = script, list(coins), None, clock
        self.counts, self.trades_workers, self._tb_err = {}, 0, None
        self.tm = [0.0]
        self._timer = lambda: self.tm[0]
        self.start_offset, self.fail_at = start_offset, fail_at
        self.workers_at_step, self.rows, self.trusted, self.peak_v, self.i = [], {}, set(), [0], 0
        self.marks = []

    def _mark(self, k, t):
        self.marks.append(k)

    def trades_pass(self, m):
        sp = self.script[self.i]
        self.tm[0] += sp.get("pass_s", 1.0)
        for k, v in sp.get("inc", {}).items():
            self.counts[k] = self.counts.get(k, 0) + v
        self.peak_v[0] = max(self.peak_v[0], sp.get("peak", 0))
        if sp.get("err"):
            self._tb_err = sp["err"]
        for c, b in sp.get("bars", {}).items():
            self.trusted.add((c, m))
            if b is not None:
                self.rows[(c, m)] = b

    def step(self, t=None):
        sp = self.script[self.i]
        self.workers_at_step.append(self.trades_workers)
        if sp.get("data", True):
            self._mark("data", None)
        if not sp.get("skip_pass"):
            self.trades_pass(KEYS[self.start_offset + self.i + 1])
        if sp.get("raise"):
            raise RuntimeError("boom")

    def run(self, minutes):
        for i in range(int(minutes)):
            self.i = i
            self.clock[0] = BASE + 60 * (self.start_offset + i + 2) + 6 + sp_data(self.script[i])
            if self.fail_at == i:
                raise RuntimeError("run failed")
            self.step()


def sp_data(sp):
    return sp.get("data_after", 3)


def make(script, candles=None, candle_err=None, **kw):
    """(factory, fake, clock, sleeps): candles: {coin: {key: tuple}}; candle_err: {coin: exception}."""
    clock = [float(BASE)]
    eng = Fake(script, clock=clock, **kw)
    calls = []

    def peak(reset=False):
        v = eng.peak_v[0]
        if reset:
            eng.peak_v[0] = 0
        return v

    def cand(c, s, e):
        calls.append((c, s, e, clock[0]))
        if candle_err and c in candle_err:
            raise candle_err[c]
        return {k: v for k, v in (candles or {}).get(c, {}).items() if s <= k < e}

    def factory(code_dir, state_dir):
        os.makedirs(state_dir, exist_ok=True)
        with open(os.path.join(state_dir, "events.jsonl"), "w") as f:
            for e in eng.__dict__.get("events", []):
                f.write(json.dumps(e) + "\n")
        return ra.Env(eng, peak, lambda c, m: eng.rows.get((c, m)), lambda c, m: (c, m) in eng.trusted, cand, state_dir)
    return factory, eng, clock, calls


def sleeper(clock):
    return lambda s: clock.__setitem__(0, clock[0] + max(s, 1.0))


def run(script, first="one", **kw):
    cand = kw.pop("candles", None)
    cerr = kw.pop("candle_err", None)
    ev = kw.pop("events", None)
    factory, eng, clock, calls = make(script, cand, cerr, **kw)
    if ev:
        eng.events = ev
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out")
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            res = ra.job("nocode", first, len(script), out, factory, clock=lambda: clock[0], sleep=sleeper(clock))
        files = sorted(os.listdir(out)) if os.path.isdir(out) else []
        disk = json.load(open(os.path.join(out, files[0]))) if files else None
    return res, eng, files, disk, calls, clock


def quiet(n, pass_s=1.0, bars=None):
    return [dict(pass_s=pass_s, bars=bars if bars is not None else {}) for _ in range(n)]


def test_arms():
    res, eng, files, disk, _, _ = run(quiet(24), first="one")
    check("first one: even minutes use 1 worker, odd minutes 3, the attribute is set before each step",
          eng.workers_at_step == [1, 3] * 12, eng.workers_at_step)
    check("steps record the minute (the one the step runs in) and workers", [s["workers"] for s in res["steps"]] == [1, 3] * 12
          and res["steps"][0]["minute"] == KEYS[2] and res["steps"][5]["minute"] == KEYS[7])
    res, eng, *_ = run(quiet(24), first="three")
    check("first three: even minutes use 3 workers, odd minutes 1", eng.workers_at_step == [3, 1] * 12)
    res, eng, *_ = run(quiet(24), first="one", start_offset=1)
    check("the arm follows the clock's minute, not the step count (job starting in an odd minute)", eng.workers_at_step == [3, 1] * 12)
    res, *_ = run(quiet(4), first="two")
    check("a bad --first is a reason, not an exception", not res["counts"] and "one or three" in res["why_not"])


def test_fields():
    script = quiet(24)
    script[2] = dict(pass_s=2.3456, inc=dict(tb_fb_budget=2, tb_fb_unverified=1), peak=7, data_after=4.4)
    script[3] = dict(pass_s=3.0, inc=dict(tb_fb_limited=3), peak=8)
    script[4] = dict(pass_s=1.0, skip_pass=True, data=False)
    script[5] = dict(pass_s=1.0, inc=dict(tb_fb_error=1), err="BTC: Refused('HTTP 403 on x')" + "x" * 300, peak=2)
    script[6] = dict(pass_s=1.0, inc=dict(tb_fb_error=2), err="ETH: ValueError('bad')", peak=1)
    res, eng, files, disk, *_ = run(script)
    s = res["steps"]
    check("pass_s rounded to 3 decimals and its text", s[2]["pass_s"] == 2.346 and s[2]["pass_text"] == "2.346" and s[0]["pass_text"] == "1.000", s[2])
    check("counter increases only in the steps where they happen", s[2]["tb_fb_budget"] == 2 and s[2]["tb_fb_unverified"] == 1 and s[2]["tb_fb_limited"] == 0
          and s[3]["tb_fb_budget"] == 0 and s[3]["tb_fb_limited"] == 3 and s[0]["tb_fb_error"] == 0, (s[2], s[3]))
    check("peak per pass, reset before each pass (a quiet step after a peak of 7 reads 0)", s[2]["peak"] == 7 and s[3]["peak"] == 8 and s[0]["peak"] == 0 and s[1]["peak"] == 0
          and s[7]["peak"] == 0, [x["peak"] for x in s[:8]])
    check("limited when tb_fb_limited rose", s[3]["limited"] and not s[2]["limited"] and not s[3]["refused"])
    check("refused when tb_fb_error rose and the text is a refusal; the text is kept, cut to 200", s[5]["refused"] and s[5]["err"].startswith("BTC: Refused(") and len(s[5]["err"]) == 200, s[5]["err"][:40])
    check("an error that is not a refusal does not set refused (the text is kept)", not s[6]["refused"] and s[6]["tb_fb_error"] == 2 and s[6]["err"].startswith("ETH: ValueError"))
    check("a step without a pass: no pass_s, not timed, data_end null", s[4]["pass_s"] is None and s[4]["data_end_s"] is None and s[4]["peak"] is None)
    check("data_end_s: seconds after the minute at which data was marked", s[0]["data_end_s"] == 9.0 and s[2]["data_end_s"] == 10.4, (s[0]["data_end_s"], s[2]["data_end_s"]))
    check("a stale _tb_err is not reported when the error counter did not rise", s[7]["err"] is None and not s[7]["refused"])
    for code in ("HTTP 401", "HTTP 451"):
        sc = quiet(3)
        sc[1] = dict(inc=dict(tb_fb_error=1), err=f"X: Err('{code} on y')")
        r, *_ = run(sc)
        check(f"{code} is a refusal", r["steps"][1]["refused"])
    sc = quiet(3)
    sc[1] = dict(err="ETH: Refused('x')")                  # text but the error counter did not rise
    check("a refusal text without a rise of tb_fb_error does not count", not run(sc)[0]["steps"][1]["refused"])
    a = res["arms"]
    check("arm sums: limited_steps, refused_steps, fallbacks, peak_max", a["3"]["limited_steps"] == 1 and a["3"]["refused_steps"] == 1 and a["1"]["refused_steps"] == 0
          and a["1"]["fb_budget"] == 2 and a["1"]["fb_unverified"] == 1 and a["3"]["fb_limited"] == 3 and a["3"]["fb_error"] == 1 and a["1"]["fb_error"] == 2
          and a["1"]["peak_max"] == 7 and a["3"]["peak_max"] == 8, a)
    check("the result file equals the returned result", disk == json.loads(json.dumps(res)) and files == [files[0]] and files[0].startswith("alt_") and files[0].endswith("Z.json"))
    check("result fields", all(k in res for k in ("utc_start", "utc_end", "minutes", "code_commit", "first", "steps", "arms", "rows_complete",
                                                  "rows_reason", "events", "counts", "why_not")) and res["first"] == "one")


def test_stats():
    sc = quiet(24)
    for i, v in enumerate((6.000, 6.001, 5.999, 7.0)):
        sc[2 * i] = dict(pass_s=v)                              # one-worker steps (even)
    res, *_ = run(sc)
    a = res["arms"]["1"]
    check("slow_over_6s: 6.000 is not slow, 6.001 is", a["slow_over_6s"] == 2, a)
    check("steps_timed per arm", a["steps_timed"] == 12 and res["arms"]["3"]["steps_timed"] == 12)
    check("pass_longest_s and the mean", a["pass_longest_s"] == 7.0 and abs(a["pass_mean_s"] - (6.0 + 6.001 + 5.999 + 7.0 + 8 * 1.0) / 12) < 1e-9)
    check("median text is exact: even count is the mean of the middle two (1.000 and 1.000 give 1.000; 1.000 and 6.000 give 3.5)", a["pass_median_text"] == "1.000"
          and ra.median_text(["1.000", "6.000"]) == "3.500" and ra.median_text(["0.100", "0.200", "0.300"]) == "0.200" and ra.median_text([]) is None)
    check("the 20-step rule: 20 timed steps in each arm counts", run(quiet(40))[0]["counts"])
    r = run(quiet(39))[0]
    check("the 20-step rule: 19 in one arm does not count, and says so", not r["counts"] and "3-worker arm has 19 timed steps" in r["why_not"], r["why_not"])
    sc = quiet(40)
    for i in range(0, 40, 2):
        sc[i] = dict(skip_pass=True)
    r = run(sc)[0]
    check("steps without a pass are not timed steps", not r["counts"] and r["arms"]["1"]["steps_timed"] == 0)


def test_bars_and_rows():
    # steps 0..11; the pass of step i builds the minute KEYS[i+1]; coins ETH and SOL
    def sc(n=12):
        s = quiet(n)
        return s
    s = sc()
    cand = {"ETH": {}, "SOL": {}}
    for i in range(1, 12):
        s[i]["bars"] = {"ETH": bar(i), "SOL": bar(i + 100)}
        cand["ETH"][KEYS[i + 1]] = bar(i)
        cand["SOL"][KEYS[i + 1]] = bar(i + 100)
    s[0]["bars"] = {}
    res, eng, files, disk, calls, clock = run(s, candles=cand)
    check("bars: built counts per step, none for a fallen-back coin", res["steps"][1]["bars_built"] == 2 and res["steps"][0]["bars_built"] == 0
          and res["steps"][1]["bars_empty"] == 0 and "_bars" not in res["steps"][1], res["steps"][1])
    # recorded minutes are KEYS[1..12] (steps 0..11); newest three left out: KEYS[1..9] kept, steps 1..8 hold bars: 8 minutes x 2 coins
    a = res["arms"]
    check("rows: equal bars, newest three recorded minutes left out, counted by the arm of the building step",
          res["rows_complete"] and res["rows_reason"] is None and a["1"]["rows_compared"] + a["3"]["rows_compared"] == 16
          and a["1"]["rows_differ"] == 0 and a["3"]["rows_differ"] == 0, a)
    # steps with an odd index are three-worker (first one); step i builds minute KEYS[i-1]; steps 1..7 compared: 1,3,5,7 are three
    check("rows: counted by the arm of the step that built the bar (steps 1,3,5,7 are three-worker; 2,4,6,8 one-worker)", a["3"]["rows_compared"] == 8 and a["1"]["rows_compared"] == 8, a)
    check("rows: one candle request per coin, not before three minutes after the last recorded minute", [c[0] for c in calls] == ["ETH", "SOL"]
          and all(c[3] >= ra.key_epoch(KEYS[12]) + 180 for c in calls), [(c[0], c[3] - BASE) for c in calls])
    check("rows: the request covers the compared minutes only", calls[0][1] == KEYS[1] and calls[0][2] == KEYS[10], calls[0])
    # differing: one value off in a three-worker bar (step 3), a missing candle for a one-worker bar (step 2), an off bar in the left-out minutes
    cand2 = json.loads(json.dumps(cand))
    cand2["ETH"][KEYS[4]] = (3.0, 4.0, 2.0, 3.5, 10.5)         # step 3 (three): volume differs
    del cand2["SOL"][KEYS[3]]                                  # step 2 (one): no candle
    cand2["ETH"][KEYS[11]] = (9, 9, 9, 9, 9)                    # minute left out: not counted
    cand2 = {c: {k: tuple(v) for k, v in d.items()} for c, d in cand2.items()}
    res, *_ = run(s, candles=cand2)
    a = res["arms"]
    check("rows: a differing value and a missing candle count as differences by arm; the left-out minutes do not", a["3"]["rows_differ"] == 1 and a["1"]["rows_differ"] == 1
          and a["3"]["rows_compared"] + a["1"]["rows_compared"] == 16, a)
    # all five values must be equal: each column
    for j in range(5):
        c3 = json.loads(json.dumps(cand))
        t = list(bar(1)); t[j] += 1e-9   # step 1 (three)
        c3["ETH"][KEYS[2]] = tuple(t)
        c3 = {c: {k: tuple(v) for k, v in d.items()} for c, d in c3.items()}
        check(f"rows: a difference of 1e-9 in column {ra.COLS[j]} differs (exact float equality)", run(s, candles=c3)[0]["arms"]["3"]["rows_differ"] == 1)
    # empty minutes
    s2 = sc()
    for i in range(1, 12):
        s2[i]["bars"] = {"ETH": None, "SOL": bar(i)}
    c4 = {"ETH": {}, "SOL": {KEYS[i + 1]: bar(i) for i in range(1, 12)}}
    res, *_ = run(s2, candles=c4)
    check("rows: an empty minute is equal when the venue has no candle; empties are counted as built-empty", res["arms"]["1"]["rows_differ"] + res["arms"]["3"]["rows_differ"] == 0
          and res["steps"][1]["bars_empty"] == 1 and res["steps"][1]["bars_built"] == 1)
    c5 = {"ETH": {KEYS[5]: bar(4)}, "SOL": c4["SOL"]}
    res, *_ = run(s2, candles=c5)
    check("rows: an empty minute differs when the venue has a candle (built by step 4: one-worker)", res["arms"]["1"]["rows_differ"] == 1 and res["arms"]["3"]["rows_differ"] == 0, res["arms"])
    # a bar the engine does not hold as trades-built is not recorded (fallen back)
    s3 = sc()
    s3[3]["bars"] = {"SOL": bar(3)}
    res, *_ = run(s3, candles={"SOL": {KEYS[4]: bar(3)}})
    check("a coin that fell back has no entry: only SOL compared in that minute", res["steps"][3]["bars_built"] == 1 and res["arms"]["3"]["rows_compared"] == 1)
    # a refused candle request stops the comparison, nothing counted for later coins, not an arm's refusal
    res, eng, files, disk, calls, _ = run(s, candles=cand, candle_err={"SOL": RuntimeError("Refused('HTTP 403')")})
    a = res["arms"]
    check("a refused candle request stops the comparison: rows_complete false with the reason, the earlier coin is counted, the later none",
          not res["rows_complete"] and "SOL: RuntimeError" in res["rows_reason"] and a["1"]["rows_compared"] + a["3"]["rows_compared"] == 8 and [c[0] for c in calls] == ["ETH", "SOL"], (a, res["rows_reason"]))
    check("the comparison's refusal is not an arm's: no refused or limited steps, the job still counts", a["1"]["refused_steps"] == a["3"]["refused_steps"] == 0 )
    sb = sc()
    sb[2]["bars"] = {"ETH": bar(1)}
    res, *_ = run(sb, candle_err={"ETH": RuntimeError("down")})
    check("a failed first coin: nothing counted, complete false", not res["rows_complete"] and res["arms"]["1"]["rows_compared"] == 0)
    res, *_ = run(sc(), candles={})
    check("no bars recorded: nothing to compare, complete", res["rows_complete"] and res["arms"]["1"]["rows_compared"] == 0)
    res, *_ = run(sc(4), candles={})
    check("fewer than four recorded minutes: all are left out, complete", res["rows_complete"])
    # the job waits for the three minutes
    r, eng, files, disk, calls, clock = run(s, candles=cand)
    check("the wait is by the injected clock (the first request is made at least 3 minutes after the last recorded minute)", calls[0][3] >= ra.key_epoch(KEYS[12]) + 180)


def test_failures():
    res, eng, files, disk, *_ = run(quiet(40), fail_at=30)
    check("an exception inside run still gives a file with counts false", not res["counts"] and "failed: RuntimeError: run failed" in res["why_not"] and len(files) == 1 and disk["counts"] is False)
    res, *_ = run(quiet(40), events=[dict(ts="2026-11-17T04:05:00", kind="error", error="x" * 400), dict(ts="t", kind="warning", msg="w"),
                                       dict(ts="t2", kind="halt", message="h"), dict(ts="t3", kind="heartbeat")])
    check("events: error, warning and halt are kept with the message cut to 200", [e["kind"] for e in res["events"]] == ["error", "warning", "halt"]
          and len(res["events"][0]["message"]) == 200 and res["events"][1]["message"] == "w" and res["events"][2]["message"] == "h")
    # a step that raises: the record is still written, the run fails
    sc = quiet(40)
    sc[5] = dict(raise_=True, **{"raise": True})
    res, *_ = run(sc)
    check("an exception in a step: counts false", not res["counts"])

    def boom(code_dir, state_dir):
        raise ra.NoJob("the engine has no trades_workers attribute")
    with tempfile.TemporaryDirectory() as tmp:
        r = ra.job("nocode", "one", 5, os.path.join(tmp, "o"), boom)
        check("a factory refusing the job: counts false with the reason", not r["counts"] and "trades_workers" in r["why_not"] and len(os.listdir(os.path.join(tmp, "o"))) == 1)
        r = ra.job(os.path.join(tmp, "nocode"), "one", 5, os.path.join(tmp, "o2"))
        check("a missing config.tw.json (the real factory): the job does not run", not r["counts"] and "config.tw.json not found" in r["why_not"])
        r = subprocess.run([sys.executable, os.path.join(HERE, "run_alt.py"), "--code", os.path.join(tmp, "nope"), "--first", "one", "--out", os.path.join(tmp, "o3")],
                           capture_output=True, text=True)
        check("command line: failure still exits 0 and writes the file", r.returncode == 0 and len(os.listdir(os.path.join(tmp, "o3"))) == 1, r.stderr[-300:])
        r = ra.job("nocode", "one", 5, os.path.join(tmp, "x", "y"), boom)
        os.makedirs(os.path.join(tmp, "blocked"))
        open(os.path.join(tmp, "blocked", "f"), "w").write("")
        r = ra.job("nocode", "one", 5, os.path.join(tmp, "blocked", "f", "z"), boom)
        check("an unwritable output folder does not raise", r["counts"] is False)
    check("the tool holds no at-sign and no pandas import at top level", chr(64) not in open(os.path.join(HERE, "run_alt.py")).read()
          and "\nimport pandas" not in open(os.path.join(HERE, "run_alt.py")).read())


def main():
    for t in (test_arms, test_fields, test_stats, test_bars_and_rows, test_failures):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
