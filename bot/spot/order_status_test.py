#!/usr/bin/env python3
"""Test of what `run.py status` and `run.py live` say about the batch order path (bot/spot/order_status.py).
No network, no keys.

Part 1, summarize() on hand-made lines: the medians of the data mark and of place minus data, their largest values,
the counter sums, the 24-hour cut, the minutes covered, a heartbeat without step_s, a malformed line, the newest
rate_limit and library; no heartbeat at all; the fallback line from fallback_min (and K 0 without the field).
Part 1b, gate() and apply_gate() on temp state folders (every case of the rule, no exception ever).
Part 2, `run.py status` end to end on a temp state folder: a serial config and one without the key print exactly
the lines of today; a batch config prints them, then the block, with no order-check file, a passed one with test
orders, a failed one, a read-only one; an event log with no recent heartbeat.
Part 3, `run.py live` in a temp copy of the package with a stand-in engine: the engine is built with the order path
the gate decides (serial without a passed check with test orders, batch with one), the line is printed, one
order_path event is logged (the stand-in keeps it in its own file, so release_inputs_test's call lists stay as they were), no warning event comes from the gate; a serial config gets no line.
The installed library is a stand-in: a dist-info folder for coinbase-advanced-py 1.8.4 in a temp folder that the
child processes get on PYTHONPATH (the real library need not be installed), so run.py's library_version() gives
"1.8.4" in them; one live case runs without it (version not found).

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
LIB = "1.8.4"                      # the library the child processes find: a stand-in dist-info folder (fake_lib)
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
             hb(NOW - timedelta(minutes=60), 10.0, 12.0, {"reprice": 5, "snap_miss": 1, "other": 9,
                                                          "fallback_min": 1}),
             hb(NOW - timedelta(minutes=50), 11.0, 15.0, {"bbo_miss": 2, "http_429": 1, "fallback_min": 2,
                                                          "cancel_single": 3},
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
                          "cancel_unconfirmed": 4, "fallback_min": 3, "cancel_single": 3}, str(s["counts"]))
    check("summarize: a malformed line skipped and counted; the non-heartbeat event ignored", s["malformed"] == 1)
    check("summarize: the newest rate_limit and library with their times",
          s["rate_limit"]["remaining"] == "20" and s["rate_limit_ts"] == NOW - timedelta(minutes=50)
          and s["library"] == "1.8.4")
    e = S.summarize(["", "garbage", json.dumps(dict(ts=NOW.isoformat(), kind="arm"))], NOW)
    check("summarize: no heartbeat at all", e["heartbeats"] == 0 and e["data"] is None and e["minutes"] == 0)
    b = S.block({"orders_rate": 10, "place_workers": 3}, tempfile.gettempdir() + "/none-here", lines, NOW, "1.8.4")
    want = ["  place minus data: median 2.00 s (the plan's first-day figure is 3 s or less)",
            "  single-request fallbacks: in 3 of 100 minutes, 3.0% (the plan's figure is fewer than 5% of minutes)"]
    check("block: the two closing lines (K = the sum of fallback_min, 1 + 2, of the 100 minutes covered)",
          b[-2:] == want, "\n".join(b))
    check("block: the counters line names cancel_single and fallback_min; no line about not knowing the minutes",
          any(x.startswith("  counters: ") and x.endswith("cancel_single 3, fallback_min 3") for x in b)
          and not any("do not say in how many minutes" in x for x in b), "\n".join(b))
    b0 = S.block({}, tempfile.gettempdir() + "/none-here", [hb(NOW, 9.0, 10.0, {"reprice": 1})], NOW, None)
    check("block: heartbeats with no fallback_min at all -> K is 0",
          b0[-1] == "  single-request fallbacks: in 0 of 30 minutes, 0.0% (the plan's figure is fewer than 5% of "
          "minutes)", b0[-1])


def fake_lib(d, version=LIB):
    """A temp folder with the dist-info of a coinbase-advanced-py of this version, for PYTHONPATH."""
    di = os.path.join(d, f"coinbase_advanced_py-{version}.dist-info")
    os.makedirs(di)
    with open(os.path.join(di, "METADATA"), "w") as f:
        f.write(f"Metadata-Version: 2.1\nName: coinbase-advanced-py\nVersion: {version}\n")
    return d


def put(sd, name, r):
    os.makedirs(sd, exist_ok=True)
    with open(os.path.join(sd, name), "w") as f:
        if isinstance(r, str):
            f.write(r)
        else:
            json.dump(r, f)


def rec(passed=True, placed=True, lib="1.8.4", started="2026-11-15 10:00:00", **kw):
    r = dict(started=started, passed=passed, place_test_orders=placed, reasons=[], **kw)
    if lib is not None:
        r["library"] = lib
    return r


def part1b():
    d = tempfile.mkdtemp(prefix="order_gate_")
    try:
        def g(label, files, lib="1.8.4"):
            sd = os.path.join(d, label.replace(" ", "_").replace(",", ""))
            os.makedirs(sd)
            for n, r in files:
                put(sd, n, r)
            return sd, S.gate(sd, lib)
        A, B, C = "order_check_20261113T100000Z.json", "order_check_20261114T100000Z.json", \
            "order_check_20261115T100000Z.json"
        serial_until = "order path in use: serial, until the order check has passed on this server (wickctl order-check)"
        sd, (u, line) = g("no file", [])
        check("gate: no file -> serial, until the check has passed", u is False and line == serial_until, line)
        sd, (u, line) = g("read-only only", [(A, rec(True, False)), (B, rec(False, False))])
        check("gate: only read-only files (passed and failed) -> serial, until the check has passed",
              u is False and line == serial_until, line)
        sd, (u, line) = g("placed pass same library", [(A, rec())])
        check("gate: a placed pass with the same library -> batch, the line has the start time and the version",
              u is True and line == "order path in use: batch (order check passed 2026-11-15 10:00:00 with "
              "coinbase-advanced-py 1.8.4)", line)
        sd, (u, line) = g("placed pass other library", [(A, rec(lib="1.7.0"))])
        check("gate: a placed pass with another library -> serial, both versions in the line",
              u is False and line == "order path in use: serial: the order check passed with coinbase-advanced-py "
              "1.7.0, the installed version is 1.8.4; run wickctl order-check again", line)
        sd, (u, line) = g("library none", [(A, rec())], lib=None)
        check("gate: library None -> serial, 'not found' in the line", u is False and "the installed version is "
              "not found; run wickctl order-check again" in line and "with coinbase-advanced-py 1.8.4," in line, line)
        sd, (u, line) = g("no library field", [(A, rec(lib=None))])
        check("gate: a placed pass whose file has no library field -> serial", u is False and line.startswith(
            "order path in use: serial: the order check passed with coinbase-advanced-py unknown,"), line)
        sd, (u, line) = g("empty library field and library none", [(A, rec(lib=""))], lib=None)
        check("gate: an empty library field never equals an unknown installed version", u is False, line)
        sd, (u, line) = g("pass then fail", [(A, rec(True)), (B, rec(False))])
        check("gate: an older placed pass, then a newer placed fail -> serial, the failed file named",
              u is False and line == "order path in use: serial: the last order check with test orders failed "
              f"({B}); run wickctl order-check again", line)
        sd, (u, line) = g("fail then pass", [(A, rec(False)), (B, rec(True))])
        check("gate: an older placed fail, then a newer placed pass -> batch", u is True and line.startswith(
            "order path in use: batch ("), line)
        sd, (u, line) = g("pass then read-only fail", [(A, rec(True)), (B, rec(False, False))])
        check("gate: a placed pass, then a newer read-only fail -> batch", u is True, line)
        sd, (u, line) = g("pass then unreadable", [(A, rec(True)), (B, "{not json")])
        check("gate: the newest file unreadable (after an older placed pass) -> serial, the file named",
              u is False and line == f"order path in use: serial: {B} cannot be read; run wickctl order-check again",
              line)
        sd, (u, line) = g("unreadable then pass", [(A, "{not json"), (B, rec(True))])
        check("gate: an older unreadable file does not matter when the newest placed check passed", u is True, line)
        sd, (u, line) = g("not a dict", [(A, [1, 2])])
        check("gate: a file holding a list is not a check that placed orders -> serial, no exception",
              u is False and line == serial_until, line)
        sd, (u, line) = g("passed as a string", [(A, dict(rec(), passed="true"))])
        check("gate: passed must be true itself, not a truthy value", u is False and "failed" in line, line)
        gone = os.path.join(d, "does", "not", "exist")
        try:
            u, line = S.gate(gone, "1.8.4")
            ok = u is False and line == serial_until
        except Exception as err:
            ok, line = False, repr(err)
        check("gate: a state folder that does not exist -> serial, no exception", ok, line)
        try:
            u, line = S.gate(None, "1.8.4")
            ok = u is False and line.startswith("order path in use: serial: the order check could not be read (")
        except Exception as err:
            ok, line = False, repr(err)
        check("gate: any exception inside -> serial with the short repr, never raised", ok, line)
        # apply_gate
        sd = os.path.join(d, "ag")
        os.makedirs(sd)
        for cfg in ({"order_path": "serial", "x": 1}, {"x": 1}, {"order_path": "fast"}):
            before = dict(cfg)
            r = S.apply_gate(cfg, sd, "1.8.4")
            check(f"apply_gate: config {before} is left alone and gives ('serial', None)",
                  cfg == before and r == ("serial", None), str((cfg, r)))
        cfg = {"order_path": "batch", "orders_rate": 10}
        r = S.apply_gate(cfg, sd, "1.8.4")
        check("apply_gate: batch config, no check -> 'serial' set, the gate's line returned, other keys kept",
              r == ("serial", serial_until) and cfg == {"order_path": "serial", "orders_rate": 10}, str((cfg, r)))
        put(sd, A, rec())
        cfg = {"order_path": "batch", "orders_rate": 10}
        r = S.apply_gate(cfg, sd, "1.8.4")
        check("apply_gate: batch config, a placed pass with the same library -> stays batch, ('batch', line)",
              r[0] == "batch" and r[1].startswith("order path in use: batch (") and cfg["order_path"] == "batch",
              str((cfg, r)))
        cfg = {"order_path": "batch"}
        r = S.apply_gate(cfg, sd, "9.9.9")
        check("apply_gate: batch config, another installed library -> 'serial' set",
              r[0] == "serial" and cfg["order_path"] == "serial" and "9.9.9" in r[1], str((cfg, r)))
    finally:
        shutil.rmtree(d, ignore_errors=True)


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


def status(cfgp, sd, libdir=None):
    r = subprocess.run([sys.executable, os.path.join(HERE, "run.py"), "status", "--config", cfgp, "--state-dir", sd],
                       cwd=ROOT, capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=libdir or ""))
    return r.returncode, r.stdout.splitlines(), r.stderr


def part2():
    d = tempfile.mkdtemp(prefix="order_status_")
    libdir = fake_lib(os.path.join(d, "site"))
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        lines = [hb(now - timedelta(minutes=30 * k), 9.0 + k % 3, 11.5 + k % 2,
                    dict({"reprice": 10, "snap_miss": k % 2}, **({"fallback_min": 1} if k % 2 else {})))
                 for k in range(4)][::-1]
        cfg = {"capital": 10000, "newest_bar": "candles"}
        for label, extra in (("no order_path key", {}), ("order_path serial", {"order_path": "serial"})):
            p = os.path.join(d, f"cfg_{len(extra)}.json")
            json.dump(dict(cfg, **extra), open(p, "w"))
            sd = write_state(os.path.join(d, label.replace(" ", "_")), lines)
            rc, out, err = status(p, sd, libdir)
            check(f"status, {label}: exactly today's lines", rc == 0 and out[1:] == old_lines(sd, 10000)
                  and len(out) == 5, str(out) + err[-300:])
        p = os.path.join(d, "cfg_batch.json")
        json.dump(dict(cfg, order_path="batch", orders_rate=10, place_workers=3), open(p, "w"))
        sd = write_state(os.path.join(d, "none"), lines)
        rc, out, err = status(p, sd)                       # no library found here: the "not found" line
        check("status, batch, library not found: the second line is the gate's, the library line says not found",
              rc == 0 and out[6].startswith("  order path in use: serial") and out[7] == "  library: "
              "coinbase-advanced-py not found", str(out[5:8]))
        rc, out, err = status(p, sd, libdir)
        print("  [status, batch, no order-check file]\n    " + "\n    ".join(out), flush=True)
        check("status, batch: today's lines first, then the block", rc == 0 and out[1:5] == old_lines(sd, 10000)
              and out[5] == "order path: batch (10 requests a second, 3 placing threads)"
              and out[6] == "  order path in use: serial, until the order check has passed on this server "
              "(wickctl order-check)"
              and out[7] == "  library: coinbase-advanced-py 1.8.4", str(out) + err[-300:])
        check("status, batch, no order-check file: the line for it",
              "  order check: none on this server yet (wickctl order-check)" in out)
        check("status, batch: 4 heartbeats, 120 minutes, the medians, the counters, the closing lines",
              any(x.startswith("  last 24 h: 4 heartbeats, 120 minutes covered") for x in out)
              and "  data step ended: median 9.50 s after the minute (largest 11.00)" in out
              and any(x.startswith("  counters: reprice 40, arm 0, cancel_unconfirmed 0, snap_miss 2,") for x in out)
              and out[-1] == "  single-request fallbacks: in 2 of 120 minutes, 1.7% (the plan's figure is fewer "
              "than 5% of minutes)", str(out))
        lib = LIB
        newest = "order_check_20261115T100000Z.json"
        on = ("order path in use: batch (order check passed 2026-11-15 10:00:00 with coinbase-advanced-py " + lib + ")")
        for label, r, want, gline in (
                ("passed with test orders", dict(started="2026-11-15 10:00:00", passed=True, place_test_orders=True,
                                                 reasons=[], library=lib), "PASSED, test orders placed", on),
                ("failed", dict(started="2026-11-15 10:00:00", passed=False, place_test_orders=True,
                                reasons=["ETH-USD: placement rejected", "cancel_many did not confirm o1\nsecond line"],
                                library=lib),
                 "FAILED: ETH-USD: placement rejected; cancel_many did not confirm o1 second line, test orders placed",
                 "order path in use: serial: the last order check with test orders failed (" + newest + "); run "
                 "wickctl order-check again"),
                ("read-only", dict(started="2026-11-15 10:00:00", passed=True, place_test_orders=False, reasons=[],
                                   library=lib),
                 "PASSED, read-only", "order path in use: serial, until the order check has passed on this server "
                 "(wickctl order-check)")):
            sd = write_state(os.path.join(d, label.replace(" ", "_")), lines,
                             [("order_check_20261114T100000Z.json", dict(r, passed=False, reasons=["older"])),
                              ("order_check_20261115T100000Z.json", r)])
            rc, out, err = status(p, sd, libdir)
            line = [x for x in out if x.startswith("  order check: ")]
            check(f"status, batch, the newest check {label}: its time, verdict, reasons on one line, mode",
                  line == [f"  order check: 2026-11-15 10:00:00 {want} (order_check_20261115T100000Z.json)"],
                  str(line))
            check(f"status, batch, the newest check {label}: the block's second line is the gate's, before the "
                  "library line", out[6] == "  " + gline and out[7].startswith("  library: coinbase-advanced-py ")
                  and out[5].startswith("order path: batch ("), str(out[5:8]))
        sd = write_state(os.path.join(d, "old"), [hb(now - timedelta(hours=30), 9.0, 11.0)])
        rc, out, err = status(p, sd, libdir)
        check("status, batch, no heartbeat in the last 24 hours: one line saying so",
              rc == 0 and out[-1] == "  last 24 h: no heartbeat", str(out[-3:]))
        sd = write_state(os.path.join(d, "nolog"))
        rc, out, err = status(p, sd, libdir)
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
    lib = LIB
    t = tree()
    libdir = fake_lib(os.path.join(t, "site"))
    try:
        # label, config, check files, the path the engine must be built with, the line that must be printed
        # (None: no line at all), the why of the event (None: "set in the config")
        on = f"order path in use: batch (order check passed 2026-11-15 10:00:00 with coinbase-advanced-py {lib})"
        placed = dict(started="2026-11-15 10:00:00", passed=True, place_test_orders=True, library=lib)
        serial_until = ("order path in use: serial, until the order check has passed on this server "
                        "(wickctl order-check)")
        cases = [
            ("batch, no order-check file", dict(base, order_path="batch"), [], "serial", serial_until),
            ("batch, a failed check and a read-only pass", dict(base, order_path="batch"),
             [("order_check_1.json", dict(passed=False, place_test_orders=True, library=lib)),
              ("order_check_2.json", dict(passed=True, place_test_orders=False, library=lib))],
             "serial", "order path in use: serial: the last order check with test orders failed (order_check_1.json); "
             "run wickctl order-check again"),
            ("batch, a pass with test orders", dict(base, order_path="batch"), [("order_check_1.json", placed)],
             "batch", on),
            ("batch, a pass with test orders of another library", dict(base, order_path="batch"),
             [("order_check_1.json", dict(placed, library="0.0.1"))], "serial",
             f"order path in use: serial: the order check passed with coinbase-advanced-py 0.0.1, the installed "
             f"version is {LIB}; run wickctl order-check again"),
            ("batch, a pass with test orders, the library not found", dict(base, order_path="batch"),
             [("order_check_1.json", placed)], "serial",
             f"order path in use: serial: the order check passed with coinbase-advanced-py {lib}, the installed "
             "version is not found; run wickctl order-check again", True),
            ("serial", base, [], "serial", None),                  # no key at all: the config is passed on as it is
            ("order_path serial, a pass with test orders", dict(base, order_path="serial"),
             [("order_check_1.json", placed)], "serial", None)]
        for case in cases:
            label, cfg, checks, want_path, want_line = case[:5]
            nolib = len(case) > 5
            p = os.path.join(t, "cfg.json")
            json.dump(cfg, open(p, "w"))
            sd = os.path.join(t, "live_" + str(abs(hash(label))))
            os.makedirs(sd)
            for name, r in checks:
                json.dump(r, open(os.path.join(sd, name), "w"))
            r = subprocess.run([sys.executable, "-B", os.path.join(t, "bot", "spot", "run.py"), "live", "--config", p,
                                "--state-dir", sd, "--minutes", "0"], cwd=t, capture_output=True, text=True,
                               env=dict(env, PYTHONPATH="" if nolib else libdir))
            out = r.stdout.splitlines()
            calls = [json.loads(x) for x in open(os.path.join(sd, "calls.jsonl"))]
            lib_i = [i for i, x in enumerate(out) if x.startswith("library: ")]
            gl = [i for i, x in enumerate(out) if x.startswith("order path in use")]
            ev = [json.loads(x) for x in open(os.path.join(sd, "order_path_events.jsonl"))]
            why = want_line or "set in the config"
            check(f"live start, {label}: engine built with {want_path} (no key: as the config has it), the line "
                  + ("next to the library line" if want_line else "absent"),
                  r.returncode == 0 and calls[0]["what"] == "init" and calls[0]["order_path"] == (None if label == "serial" else want_path)
                  and (out[gl[0]] == want_line and gl == [lib_i[0] + 1] if want_line else not gl),
                  str(out) + str(calls[:1]) + r.stderr[-300:])
            check(f"live start, {label}: one order_path event, in_use {want_path}, why as printed; no warning, "
                  "no other event",
                  [c["what"] for c in calls] == ["init", "run"]
                  and ev == [dict(kind="order_path", in_use=want_path, why=why)], str((calls, ev)))
        # paper mode: nothing new printed or logged, its config untouched
        p = os.path.join(t, "cfg.json")
        json.dump(dict(base, order_path="batch"), open(p, "w"))
        sd = os.path.join(t, "paper_state")
        os.makedirs(sd)
        r = subprocess.run([sys.executable, "-B", os.path.join(t, "bot", "spot", "run.py"), "paper", "--config", p,
                            "--state-dir", sd, "--minutes", "0"], cwd=t, capture_output=True, text=True,
                           env=dict(env, PYTHONPATH=libdir))
        calls = [json.loads(x) for x in open(os.path.join(sd, "calls.jsonl"))]
        check("paper start, batch config: no order path line, the engine gets the config as it is, no event",
              r.returncode == 0 and "order path in use" not in r.stdout and calls[0]["order_path"] == "batch"
              and [c["what"] for c in calls] == ["init", "run"]
              and not os.path.exists(os.path.join(sd, "order_path_events.jsonl")), r.stdout[-300:] + r.stderr[-300:])
    finally:
        shutil.rmtree(t, ignore_errors=True)


if __name__ == "__main__":
    part1()
    part1b()
    part2()
    part3()
    print("ORDER STATUS TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
