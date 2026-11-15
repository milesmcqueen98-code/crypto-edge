#!/usr/bin/env python3
"""Test of what `run.py status` and `run.py live` say about the batch order path (bot/spot/order_status.py).
No network, no keys.

Part 1, summarize() on hand-made lines: the medians of the data mark and of place minus data, their largest values,
the counter sums, the 24-hour cut, the minutes covered, a heartbeat without step_s, a malformed line, the newest
rate_limit and library; no heartbeat at all.
Part 2, `run.py status` end to end on a temp state folder: a serial config and one without the key print exactly
the lines of today; a batch config prints them, then the block, with no order-check file, a passed one with test
orders, a failed one, a read-only one; an event log with no recent heartbeat.
Part 3, `run.py live` in a temp copy of the package with a stand-in engine: the start-up line is printed on the batch
path without a passed check with test orders, and not printed with one, nor on the serial path; no event is logged.

Usage: python bot/spot/order_status_test.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot.spot import order_status as S  # noqa: E402
from bot.spot.release_inputs_test import FAKE_ENGINE, STATE, old_lines  # noqa: E402

FAILS = []
NOW = datetime(2026, 11, 15, 12, 0)


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""), flush=True)
    if not ok:
        FAILS.append(name)


def hb(t, data=None, place=None, counts=None, **kw):
    e = dict(ts=t.isoformat(), kind="heartbeat", equity=1.0, counts=counts or {})
    if data is not None:
        e["step_s"] = {"data": [data, data + 1], "cancel": [data + 0.5, data + 1], "place": [place, place + 1]}
    e.update(kw)
    return json.dumps(e)


def part1():
    lines = [hb(NOW - timedelta(hours=25), 9.0, 30.0, {"reprice": 100}),          # outside the 24 hours
             hb(NOW - timedelta(minutes=90), None, None, {"arm": 2}, library="1.8.4"),   # no step_s
             "{not json",
             json.dumps(dict(ts=(NOW - timedelta(minutes=70)).isoformat(), kind="fill_entry", coin="ETH")),
             hb(NOW - timedelta(minutes=60), 10.0, 12.0, {"reprice": 5, "snap_miss": 1, "other": 9}),
             hb(NOW - timedelta(minutes=50), 11.0, 15.0, {"bbo_miss": 2, "http_429": 1},
                rate_limit={"limit": "30", "remaining": "20", "reset": "1"}),     # 10 minutes after the one before
             hb(NOW, 12.0, 13.0, {"reprice": 3, "batch_fallback": 1, "cancel_unconfirmed": 4})]
    s = S.summarize(lines, NOW)
    check("summarize: heartbeats of the last 24 hours only (the one 25 hours back cut)", s["heartbeats"] == 4, str(s))
    check("summarize: minutes covered (30, 30, 10 since the one before, 30)", s["minutes"] == 100, str(s["minutes"]))
    check("summarize: median of the data mark's median over heartbeats with step_s, and its largest",
          s["data"] == 11.0 and s["data_max"] == 12.0, str((s["data"], s["data_max"])))
    check("summarize: median of place minus data (2, 4, 1) and its largest", s["gap"] == 2.0 and s["gap_max"] == 4.0,
          str((s["gap"], s["gap_max"])))
    check("summarize: counter sums, only the listed counters, the cut one left out",
          s["counts"] == {"arm": 2, "reprice": 8, "snap_miss": 1, "bbo_miss": 2, "http_429": 1, "batch_fallback": 1,
                          "cancel_unconfirmed": 4}, str(s["counts"]))
    check("summarize: a malformed line skipped and counted; the non-heartbeat event ignored", s["malformed"] == 1)
    check("summarize: the newest rate_limit and library with their times",
          s["rate_limit"]["remaining"] == "20" and s["rate_limit_ts"] == NOW - timedelta(minutes=50)
          and s["library"] == "1.8.4")
    e = S.summarize(["", "garbage", json.dumps(dict(ts=NOW.isoformat(), kind="arm"))], NOW)
    check("summarize: no heartbeat at all", e["heartbeats"] == 0 and e["data"] is None and e["minutes"] == 0)
    b = S.block({"orders_rate": 10, "place_workers": 3}, tempfile.gettempdir() + "/none-here", lines, NOW, "1.8.4")
    want = ["  place minus data: median 2.00 s (the plan's first-day figure is 3 s or less)",
            "  single-request fallbacks: 4 in 100 minutes (the plan's figure is fewer than 5% of minutes)"]
    check("block: the two closing lines (N = snap_miss + bbo_miss + batch_fallback = 1 + 2 + 1)",
          all(w in b for w in want), "\n".join(b))


def write_state(d, lines=None, checks=()):
    sd = os.path.join(d, "live_spot")
    os.makedirs(sd, exist_ok=True)
    with open(os.path.join(sd, "state.json"), "w") as f:
        json.dump(STATE, f)
    if lines is not None:
        with open(os.path.join(sd, "events.jsonl"), "w") as f:
            f.write("\n".join(lines) + "\n")
    for name, r in checks:
        with open(os.path.join(sd, name), "w") as f:
            json.dump(r, f)
    return sd


def status(cfgp, sd):
    r = subprocess.run([sys.executable, os.path.join(HERE, "run.py"), "status", "--config", cfgp, "--state-dir", sd],
                       cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return r.returncode, r.stdout.splitlines(), r.stderr


def part2():
    d = tempfile.mkdtemp(prefix="order_status_")
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        lines = [hb(now - timedelta(minutes=30 * k), 9.0 + k % 3, 11.5 + k % 2, {"reprice": 10, "snap_miss": k % 2})
                 for k in range(4)][::-1]
        cfg = {"capital": 10000, "newest_bar": "candles"}
        for label, extra in (("no order_path key", {}), ("order_path serial", {"order_path": "serial"})):
            p = os.path.join(d, f"cfg_{len(extra)}.json")
            json.dump(dict(cfg, **extra), open(p, "w"))
            sd = write_state(os.path.join(d, label.replace(" ", "_")), lines)
            rc, out, err = status(p, sd)
            check(f"status, {label}: exactly today's lines", rc == 0 and out[1:] == old_lines(sd, 10000)
                  and len(out) == 5, str(out) + err[-300:])
        p = os.path.join(d, "cfg_batch.json")
        json.dump(dict(cfg, order_path="batch", orders_rate=10, place_workers=3), open(p, "w"))
        sd = write_state(os.path.join(d, "none"), lines)
        rc, out, err = status(p, sd)
        print("  [status, batch, no order-check file]\n    " + "\n    ".join(out), flush=True)
        check("status, batch: today's lines first, then the block", rc == 0 and out[1:5] == old_lines(sd, 10000)
              and out[5] == "order path: batch (10 requests a second, 3 placing threads)"
              and out[6].startswith("  library: coinbase-advanced-py "), str(out) + err[-300:])
        check("status, batch, no order-check file: the line for it",
              "  order check: none on this server yet (wickctl order-check)" in out)
        check("status, batch: 4 heartbeats, 120 minutes, the medians, the counters, the closing lines",
              any(x.startswith("  last 24 h: 4 heartbeats, 120 minutes covered") for x in out)
              and "  data step ended: median 9.50 s after the minute (largest 11.00)" in out
              and any(x.startswith("  counters: reprice 40, arm 0, cancel_unconfirmed 0, snap_miss 2,") for x in out)
              and any(x.startswith("  single-request fallbacks: 2 in 120 minutes") for x in out), str(out))
        for label, r, want in (
                ("passed with test orders", dict(started="2026-11-15 10:00:00", passed=True, place_test_orders=True,
                                                 reasons=[]), "PASSED, test orders placed"),
                ("failed", dict(started="2026-11-15 10:00:00", passed=False, place_test_orders=True,
                                reasons=["ETH-USD: placement rejected", "cancel_many did not confirm o1\nsecond line"]),
                 "FAILED: ETH-USD: placement rejected; cancel_many did not confirm o1 second line, test orders placed"),
                ("read-only", dict(started="2026-11-15 10:00:00", passed=True, place_test_orders=False, reasons=[]),
                 "PASSED, read-only")):
            sd = write_state(os.path.join(d, label.replace(" ", "_")), lines,
                             [("order_check_20261114T100000Z.json", dict(r, passed=False, reasons=["older"])),
                              ("order_check_20261115T100000Z.json", r)])
            rc, out, err = status(p, sd)
            line = [x for x in out if x.startswith("  order check: ")]
            check(f"status, batch, the newest check {label}: its time, verdict, reasons on one line, mode",
                  line == [f"  order check: 2026-11-15 10:00:00 {want} (order_check_20261115T100000Z.json)"],
                  str(line))
        sd = write_state(os.path.join(d, "old"), [hb(now - timedelta(hours=30), 9.0, 11.0)])
        rc, out, err = status(p, sd)
        check("status, batch, no heartbeat in the last 24 hours: one line saying so",
              rc == 0 and out[-1] == "  last 24 h: no heartbeat", str(out[-3:]))
        sd = write_state(os.path.join(d, "nolog"))
        rc, out, err = status(p, sd)
        check("status, batch, no event log at all: no heartbeat, no error", rc == 0 and out[-1] == "  last 24 h: no "
              "heartbeat", str(out[-3:]) + err[-200:])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def tree():
    t = tempfile.mkdtemp(prefix="order_status_tree_")
    sp = os.path.join(t, "bot", "spot")
    os.makedirs(sp)
    for f in ("bot/__init__.py", "bot/spot/__init__.py", "bot/spot/run.py", "bot/spot/release_inputs.py",
              "bot/spot/order_status.py"):
        shutil.copy(os.path.join(ROOT, f), os.path.join(t, f))
    with open(os.path.join(sp, "engine.py"), "w") as f:
        f.write(FAKE_ENGINE)
    return t


def part3():
    env = dict(os.environ, COINBASE_API_KEY="k", COINBASE_API_SECRET="s", I_UNDERSTAND_LIVE_TRADING="yes")
    base = {"capital": 1000, "newest_bar": "trades", "stale_guard": True}
    t = tree()
    try:
        for label, cfg, checks, want in (
                ("batch, no order-check file", dict(base, order_path="batch"), [], True),
                ("batch, a failed check and a read-only pass", dict(base, order_path="batch"),
                 [("order_check_1.json", dict(passed=False, place_test_orders=True)),
                  ("order_check_2.json", dict(passed=True, place_test_orders=False))], True),
                ("batch, a pass with test orders", dict(base, order_path="batch"),
                 [("order_check_1.json", dict(passed=True, place_test_orders=True))], False),
                ("serial", base, [], False)):
            p = os.path.join(t, "cfg.json")
            json.dump(cfg, open(p, "w"))
            sd = os.path.join(t, "live_" + str(abs(hash(label))))
            os.makedirs(sd)
            for name, r in checks:
                json.dump(r, open(os.path.join(sd, name), "w"))
            r = subprocess.run([sys.executable, "-B", os.path.join(t, "bot", "spot", "run.py"), "live", "--config", p,
                                "--state-dir", sd, "--minutes", "0"], cwd=t, capture_output=True, text=True, env=env)
            out = r.stdout.splitlines()
            calls = [json.loads(x) for x in open(os.path.join(sd, "calls.jsonl"))]
            lib = [i for i, x in enumerate(out) if x.startswith("library: ")]
            has = S.NOT_PASSED in out
            what = "printed next to the library line" if want else "absent"
            check(f"live start, {label}: the order-check line {what}, no event logged",
                  r.returncode == 0 and has == want and lib and (not want or out.index(S.NOT_PASSED) == lib[0] + 1)
                  and [c["what"] for c in calls] == ["init", "run"], str(out) + r.stderr[-300:])
    finally:
        shutil.rmtree(t, ignore_errors=True)


if __name__ == "__main__":
    part1()
    part2()
    part3()
    print("ORDER STATUS TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
