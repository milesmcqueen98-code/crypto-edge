#!/usr/bin/env python3
"""Test of bot/spot/deploy/watchdog.py. No network, no keys: NTFY_TOPIC is removed, so the script only prints.

Each case builds a temp state folder (state.json, events.jsonl), runs the script as a subprocess, and checks the
printed alerts and the saved watchdog.json. Checks the stale_input rule (three or more in one run's batch, at most one
alert every 30 minutes), that the other event kinds, the heartbeat alerts, the daily line and the missing-state path
are as before, and that bad lines in events.jsonl do not stop it.

Usage: python bot/spot/deploy/watchdog_test.py
"""
import calendar
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "watchdog.py")
TITLE = "wickbot stale input"
FAILS = []


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""))
    if not ok:
        FAILS.append(name)


def stale_text(n):
    return (f"[{TITLE}] no new bids in {n} of the last minutes: BTC's newest price row was missing or old (stale "
            "guard). Exits still run. If it lasts, look at live_spot/stdout.log.")


def ev(kind, **kw):
    d = {"kind": kind}
    d.update(kw)
    return json.dumps(d) + "\n"


def make(tmp, name, events=None, state=True, mark=None, age=0.0):
    """A state folder under tmp; events is the text of events.jsonl (None: no file)."""
    d = os.path.join(tmp, name)
    os.makedirs(d)
    if state:
        p = os.path.join(d, "state.json")
        json.dump({"equity": 12345.6, "day_start_equity": 12000.0, "ladders": {"a": 1, "b": 2}}, open(p, "w"))
        t = time.time() - age
        os.utime(p, (t, t))
    if events is not None:
        open(os.path.join(d, "events.jsonl"), "w").write(events)
    if mark is not None:
        json.dump(mark, open(os.path.join(d, "watchdog.json"), "w"))
    return d


def append(d, text):
    with open(os.path.join(d, "events.jsonl"), "a") as fh:
        fh.write(text)


def run(d, script=SCRIPT, wrapper=None):
    env = {k: v for k, v in os.environ.items() if k != "NTFY_TOPIC"}
    cmd = [sys.executable, script, d] if wrapper is None else [sys.executable, wrapper, script, d]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
    return r.returncode, r.stdout.splitlines(), r.stderr


def mark_of(d):
    p = os.path.join(d, "watchdog.json")
    return json.load(open(p)) if os.path.exists(p) else None


def stale_lines(lines):
    return [x for x in lines if x.startswith(f"[{TITLE}]")]


def main():
    tmp = tempfile.mkdtemp(prefix="watchdog_test_")
    try:
        cases(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("WATCHDOG TEST FAILED" if FAILS else "WATCHDOG TEST PASSED")
    sys.exit(1 if FAILS else 0)


def cases(tmp):
    # 1. two stale_input events: nothing
    d = make(tmp, "two", ev("stale_input", t=1) * 2)
    rc, out, err = run(d)
    m = mark_of(d)
    check("two stale_input: exit 0, no output", rc == 0 and out == [], f"rc={rc} out={out} err={err[-200:]}")
    check("two stale_input: no stale_input_alert saved, offset moved",
          "stale_input_alert" not in m and m["offset"] == os.path.getsize(os.path.join(d, "events.jsonl")), str(m))

    # 2. three in the batch: one alert; 3. a second run with three more right after: none
    d = make(tmp, "three", ev("stale_input", t=1) * 3)
    t0 = time.time()
    rc, out, err = run(d)
    m = mark_of(d)
    check("three stale_input: exactly one alert, with the count", out == [stale_text(3)], str(out))
    check("three stale_input: stale_input_alert saved", t0 - 1 <= m.get("stale_input_alert", 0) <= time.time() + 1,
          str(m))
    size1 = os.path.getsize(os.path.join(d, "events.jsonl"))
    check("three stale_input: offset at end of file", m["offset"] == size1, str(m))
    first_alert = m["stale_input_alert"]
    append(d, ev("stale_input", t=2) * 3)
    rc, out, err = run(d)
    m = mark_of(d)
    check("second run, three more right after: no alert (quiet period)", out == [], str(out))
    check("second run: offset moved on, stale_input_alert unchanged",
          m["offset"] == os.path.getsize(os.path.join(d, "events.jsonl")) > size1
          and m["stale_input_alert"] == first_alert, str(m))

    # 4. quiet period edges: 1,801 s old alerts, 1,799 s does not
    for age, want in ((1801, True), (1799, False)):
        d = make(tmp, f"quiet{age}", ev("stale_input", t=1) * 3)
        run(d)
        mk = mark_of(d)
        mk["stale_input_alert"] = time.time() - age
        json.dump(mk, open(os.path.join(d, "watchdog.json"), "w"))
        append(d, ev("stale_input", t=2) * 3)
        rc, out, err = run(d)
        m = mark_of(d)
        if want:
            check(f"saved alert {age} s old: one alert again", out == [stale_text(3)], str(out))
            check(f"saved alert {age} s old: stale_input_alert renewed", time.time() - m["stale_input_alert"] < 60)
        else:
            check(f"saved alert {age} s old: no alert", out == [], str(out))
            check(f"saved alert {age} s old: stale_input_alert kept",
                  abs(time.time() - age - m["stale_input_alert"]) < 60)

    # more than three: the count in the text
    d = make(tmp, "five", ev("stale_input", t=1) * 5)
    rc, out, err = run(d)
    check("five stale_input: one alert saying 5", out == [stale_text(5)], str(out))

    # 5. old-style watchdog.json
    d = make(tmp, "old", ev("stale_input", t=1) * 3, mark={"offset": 0, "day": None, "stale": False})
    rc, out, err = run(d)
    m = mark_of(d)
    check("old-style watchdog.json: works and alerts on three", rc == 0 and out == [stale_text(3)],
          f"{out} {err[-200:]}")
    check("old-style watchdog.json: other fields kept, new one added",
          m["day"] is None and m["stale"] is False and "stale_input_alert" in m, str(m))
    d = make(tmp, "old2", ev("stale_input", t=1) * 2, mark={"offset": 0, "day": None, "stale": False})
    rc, out, err = run(d)
    check("old-style watchdog.json: two events, nothing", rc == 0 and out == [], str(out))

    # 6. the four kinds mixed with stale_input
    body = (ev("stale_input", t=1) + ev("halt", why="dd") + ev("stale_input", t=2) + ev("error", msg="boom")
            + ev("stale_input", t=3) + ev("warning", msg="w") + ev("reject", id="x") + ev("stale_input", t=4))
    d = make(tmp, "mixed", body)
    rc, out, err = run(d)
    want = ['[wickbot halt] {"why": "dd"}', '[wickbot error] {"msg": "boom"}', '[wickbot warning] {"msg": "w"}',
            '[wickbot reject] {"id": "x"}', stale_text(4)]
    check("mixed: four own alerts in order plus one summary", out == want, str(out))
    d = make(tmp, "mixed2", ev("halt", why="dd") + ev("stale_input", t=1) + ev("reject", id="x")
             + ev("stale_input", t=2))
    rc, out, err = run(d)
    check("mixed, two stale_input: own alerts only", out == ['[wickbot halt] {"why": "dd"}',
                                                            '[wickbot reject] {"id": "x"}'], str(out))
    # priorities: the push function is not reachable without a topic, so check them through the source
    src = open(SCRIPT).read()
    check("priority rule line unchanged",
          'prio = "urgent" if e["kind"] == "halt" else "high" if e["kind"] in ("error", "warning") else "default"'
          in src)
    check("stale alert pushed with priority high", '"high")\n            mark["stale_input_alert"]' in src)

    # 7. no stale_input events: exact expected output and mark (hand-written)
    d = make(tmp, "plain", ev("halt", why="dd") + ev("info", n=1) + ev("error", msg="e"))
    rc, out, err = run(d)
    m = mark_of(d)
    check("no stale_input: output as before", out == ['[wickbot halt] {"why": "dd"}', '[wickbot error] {"msg": "e"}'],
          str(out))
    check("no stale_input: watchdog.json has exactly offset, day, stale",
          sorted(m) == ["day", "offset", "stale"] and m["day"] is None and m["stale"] is False, str(m))

    # 8. truncated last line and a non-JSON line
    body = "not json at all\n" + ev("stale_input", t=1) * 3 + ev("halt", why="dd") + '{"kind": "error", "msg": "cut'
    d = make(tmp, "bad", body)
    rc, out, err = run(d)
    m = mark_of(d)
    check("bad lines: no crash, alerts for the good ones", rc == 0 and out == ['[wickbot halt] {"why": "dd"}',
                                                                              stale_text(3)] or
          rc == 0 and out == [stale_text(3), '[wickbot halt] {"why": "dd"}'], f"rc={rc} {out} {err[-200:]}")
    check("bad lines: offset at end of file", m["offset"] == len(body.encode()), str(m))

    # 9. no state file yet
    d = make(tmp, "nostate", ev("halt", why="dd"), state=False)
    rc, out, err = run(d)
    check("no state file: prints the one line, saves nothing", rc == 0 and out == ["[wickbot] no state file yet"]
          and mark_of(d) is None, str(out))

    # 10. DOWN and back
    d = make(tmp, "down", None, age=900)
    rc, out, err = run(d)
    check("old state.json: DOWN alert",
          len(out) == 1 and out[0].startswith("[wickbot DOWN] no minute completed for 15 min")
          and mark_of(d)["stale"] is True, str(out))
    rc, out, err = run(d)
    check("still down: no second alert", out == [], str(out))
    os.utime(os.path.join(d, "state.json"), None)
    rc, out, err = run(d)
    check("fresh again: back alert", out == ["[wickbot back] minute loop running again"]
          and mark_of(d)["stale"] is False, str(out))

    # 11. daily line, with the clock of the subprocess set to 00:10 UTC (and 12:00 for the negative)
    wrapper = os.path.join(tmp, "clock.py")
    open(wrapper, "w").write(
        "import calendar, runpy, sys, time\n"
        "real = time.gmtime\n"
        "fixed = real(int(sys.argv[1]))\n"
        "time.gmtime = lambda *a: real(*a) if a else fixed\n"
        "sys.argv = [sys.argv[2], sys.argv[3]]\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n")

    def run_at(d, ts):
        env = {k: v for k, v in os.environ.items() if k != "NTFY_TOPIC"}
        r = subprocess.run([sys.executable, wrapper, str(ts), SCRIPT, d], capture_output=True, text=True, env=env,
                           timeout=60)
        return r.returncode, r.stdout.splitlines(), r.stderr

    t_daily = calendar.timegm((2027, 1, 15, 0, 10, 0))
    d = make(tmp, "daily", None)
    rc, out, err = run_at(d, t_daily)
    check("daily line after 00:05 UTC", out == ["[wickbot daily] equity $12,346; open ladders 2; drawdown stop off"]
          and mark_of(d)["day"] == "2027-01-15", f"{out} {err[-200:]}")
    rc, out, err = run_at(d, t_daily + 60)
    check("daily line only once a day", out == [], str(out))
    d = make(tmp, "daily2", None)
    rc, out, err = run_at(d, calendar.timegm((2027, 1, 15, 12, 0, 0)))
    check("no daily line at noon", out == [] and mark_of(d)["day"] is None, str(out))
    d = make(tmp, "daily3", ev("stale_input", t=1) * 3)
    rc, out, err = run_at(d, t_daily)
    check("daily line and stale alert together", len(out) == 2 and out[0] == stale_text(3)
          and out[1].startswith("[wickbot daily]"), str(out))


if __name__ == "__main__":
    main()
