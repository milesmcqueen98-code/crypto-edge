#!/usr/bin/env python3
"""Test of the live bot's input settings taken from the release (bot/spot/release_inputs.py, bot/spot/run.py).
No network, no keys.

Part 1, the pure functions:
  - apply: keys absent from the live config come from the base; a differing value is replaced and noted; a key the
    base lacks is dropped and noted; keys outside INPUT_KEYS are never touched; "inputs_local": true keeps everything
    and gives one note; false or absent does not; neither argument is changed; applying twice equals applying once;
  - applies: true only for the base name config.live.json;
  - describe: trades mode with and without a list, candle mode, guard on and off, trades_rows;
  - preflight_file: the file as read plus coins_disabled and bid_ttl_s, nothing taken from the release;
  - release_inputs.py and run.py parse as Python 3.8, and importing release_inputs loads no pandas or numpy.
Part 2, run.py status end to end (a subprocess, temp folder, no network):
  - a live file as a VM set up before release 3 has it (config.json without the input keys, capital changed): the
    inputs line of bot/spot/config.json with the "(from bot/spot/config.json)" marker, then every line status printed
    before;
  - a live file made as setup_vm.sh makes it now (a copy of config.json, capital 0) with a different trades_coins
    list: the release's list is used and a note names both;
  - "inputs_local": true with "newest_bar": "candles": the candle line and the note, no marker;
  - --config bot/spot/config.tb.json: its own line, no marker;
  - the live files are byte for byte as written after every run.
Part 3, a temp copy of the package (run.py, release_inputs.py, a stand-in engine; the real config.json untouched):
  - config.json missing or with bad JSON: status prints the note and the live file's own inputs, the kill switch
    (stop, resume) completes, and live starts on the file's own inputs with the warning;
  - live warns (a printed line and one warning event through the engine's log, before run) exactly when the inputs
    are not trades with the stale guard; the key and live-switch checks still stop before the engine is built;
  - the real engine's log("warning", msg=...) writes one warning event.

Usage: python bot/spot/release_inputs_test.py
"""
import ast
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot.spot import release_inputs as R  # noqa: E402

FAILS = []
BASE = json.load(open(os.path.join(HERE, "config.json")))
MARK = " (from bot/spot/config.json)"


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""), flush=True)
    if not ok:
        FAILS.append(name)


def expected_line(cfg):
    """The inputs line written out here independently of describe()."""
    if cfg.get("newest_bar", "candles") == "trades":
        tc = cfg.get("trades_coins")
        src = ("newest minute from trades for BTC and every coin" if tc is None else
               "newest minute from trades for " + ", ".join(tc) + "; candles for the other coins")
    else:
        src = "candles for every coin"
    return "inputs: " + src + "; stale guard " + ("on" if cfg.get("stale_guard") else "off")


# ------------------------------------------------------------------------------------------------ part 1
def part1():
    base = {"capital": 250000, "newest_bar": "trades", "trades_coins": ["BTC", "ETH", "SOL"], "stale_guard": True,
            "rung_weights": {"4": 1, "6": 1, "8": 1}}
    live = {"capital": 12000.0, "coins_disabled": ["HYPE", "ZEC"], "bid_ttl_s": 600, "quote": "USDC",
            "daily_loss_limit": 0.05, "max_drawdown": 0.2, "rung_weights": {"4": 1, "6": 1, "8": 2},
            "fee_bp_maker": 4.0}
    base0, live0 = copy.deepcopy(base), copy.deepcopy(live)
    new, notes = R.apply(live, base)
    check("absent keys are taken from the base", new["newest_bar"] == "trades" and new["stale_guard"] is True
          and new["trades_coins"] == ["BTC", "ETH", "SOL"], str(new))
    check("absent keys give no note", notes == [], str(notes))
    outside = [k for k in set(live) | set(new) if k not in R.INPUT_KEYS]
    check("keys outside INPUT_KEYS are exactly as the live config has them (capital, coins_disabled, bid_ttl_s, quote, "
          "risk limits, rung weights, fees)", all(new.get(k) == live.get(k) and (k in new) == (k in live)
                                                  for k in outside), str(outside))
    check("neither argument is changed", base == base0 and live == live0)
    new["trades_coins"].append("XRP")
    check("the result shares no list with the base", base["trades_coins"] == ["BTC", "ETH", "SOL"])
    new2, notes2 = R.apply(live, base)

    # a differing value is replaced and noted, naming the key and both values
    live_d = dict(live, newest_bar="candles", trades_coins=["BTC", "ETH"], stale_guard=True)
    new_d, notes_d = R.apply(live_d, base)
    check("a differing value is replaced", new_d["newest_bar"] == "trades" and new_d["trades_coins"] == base[
        "trades_coins"], str(new_d))
    check("each differing value is noted with the key and both values (equal values give no note)",
          len(notes_d) == 2 and "newest_bar" in notes_d[0] and "'candles'" in notes_d[0] and "'trades'" in notes_d[0]
          and "trades_coins" in notes_d[1] and "['BTC', 'ETH']" in notes_d[1]
          and "['BTC', 'ETH', 'SOL']" in notes_d[1], str(notes_d))

    # a key the base lacks is dropped and noted
    live_x = dict(live, confirm_s=40, trades_budget_s=5)
    new_x, notes_x = R.apply(live_x, base)
    check("a key the base lacks is dropped from the result",
          "confirm_s" not in new_x and "trades_budget_s" not in new_x, str(new_x))
    check("a dropped key is noted", len(notes_x) == 2 and all(any(k in n for n in notes_x)
                                                              for k in ("confirm_s", "trades_budget_s")), str(notes_x))
    new_c, notes_c = R.apply(dict(live, newest_bar="trades", stale_guard=True), {"capital": 1})
    check("a base without input keys drops every input key of the live config (code defaults apply)",
          not any(k in new_c for k in R.INPUT_KEYS) and new_c["capital"] == live["capital"] and len(notes_c) == 2,
          str(notes_c))

    # inputs_local
    live_l = dict(live, inputs_local=True, newest_bar="candles", confirm_s=40)
    new_l, notes_l = R.apply(live_l, base)
    check("inputs_local true: the live config is kept as it is", new_l == live_l, str(new_l))
    check("inputs_local true: one note that the file's own inputs are used", len(notes_l) == 1
          and "inputs_local" in notes_l[0] and "own input settings" in notes_l[0], str(notes_l))
    for v in (False, "true", 1, None):
        new_f, notes_f = R.apply(dict(live, inputs_local=v, newest_bar="candles"), base)
        check(f"inputs_local {v!r}: release inputs applied", new_f["newest_bar"] == "trades"
              and not any("inputs_local" in n for n in notes_f) and new_f["inputs_local"] == v, str(notes_f))

    # idempotent
    once, _ = R.apply(live_d, base)
    twice, notes_t = R.apply(once, base)
    check("applying twice equals applying once (and the second gives no note)", once == twice and notes_t == [])
    check("applying the same inputs again gives the same result", new2 == R.apply(live, base)[0])

    # applies
    yes = ["config.live.json", "/home/wick/crypto-edge/bot/spot/config.live.json", "bot/spot/config.live.json",
           "./config.live.json", "../spot/config.live.json"]
    no = ["config.live.json.bak", "config.json", "config.tb.json", "config.w2.json", "bot/spot/config.json",
          "/home/wick/crypto-edge/bot/spot/config.tb.json", "my.config.live.json", "config.live.json/", "",
          "config.live.jsonx", "old_config.live.json"]
    check("applies: true for every path whose base name is config.live.json", all(R.applies(p) for p in yes),
          str([p for p in yes if not R.applies(p)]))
    check("applies: false for every other name", not any(R.applies(p) for p in no),
          str([p for p in no if R.applies(p)]))

    # describe
    d1 = R.describe({"newest_bar": "trades", "trades_coins": ["BTC", "ETH", "SOL", "XRP", "LTC", "ZEC"],
                     "stale_guard": True})
    check("describe: trades with a list, guard on", d1 == "inputs: newest minute from trades for BTC, ETH, SOL, XRP, "
          "LTC, ZEC; candles for the other coins; stale guard on", d1)
    d2 = R.describe({"newest_bar": "trades", "stale_guard": False})
    check("describe: trades without a list, guard off",
          d2 == "inputs: newest minute from trades for BTC and every coin; stale guard off", d2)
    d3 = R.describe({"capital": 1})
    check("describe: candle mode (no keys)", d3 == "inputs: candles for every coin; stale guard off", d3)
    d4 = R.describe({"newest_bar": "candles", "trades_coins": ["BTC"], "stale_guard": True})
    check("describe: candle mode with the guard on (a list is not mentioned in candle mode)",
          d4 == "inputs: candles for every coin; stale guard on", d4)
    d5 = R.describe({"newest_bar": "trades", "trades_coins": ["BTC", "ETH"], "stale_guard": True,
                     "trades_rows": "candle_after"})
    check("describe: trades_rows mentioned when set", d5.endswith("; stale guard on; trades_rows candle_after")
          and "BTC, ETH;" in d5, d5)
    check("describe: trades_rows not mentioned when absent", "trades_rows" not in d1 + d2 + d3 + d4)
    check("describe matches the line written out independently for config.json and config.tb.json",
          all(R.describe(c) == expected_line(c) for c in
              (BASE, json.load(open(os.path.join(HERE, "config.tb.json"))))))

    # preflight write-back
    raw = {"capital": 12000.0, "coins_disabled": [], "bid_ttl_s": 300, "quote": "USD"}
    raw0 = copy.deepcopy(raw)
    eff, _ = R.apply(raw, base)
    out = R.preflight_file(raw, ["HYPE", "ZEC"], 600)
    check("preflight_file: the file as read plus coins_disabled and bid_ttl_s",
          out == dict(raw0, coins_disabled=["HYPE", "ZEC"], bid_ttl_s=600) and raw == raw0, str(out))
    check("preflight_file: nothing taken from the release is written", not any(k in out for k in R.INPUT_KEYS)
          and any(k in eff for k in R.INPUT_KEYS))
    out2 = R.preflight_file(raw, [], None)
    check("preflight_file: no bid lifetime found keeps the file's bid_ttl_s", out2 == dict(raw0, coins_disabled=[]),
          str(out2))
    raw_l = dict(raw, inputs_local=True, newest_bar="candles")
    check("preflight_file: a file with its own inputs keeps them",
          R.preflight_file(raw_l, ["ZEC"], 600) == dict(raw_l, coins_disabled=["ZEC"], bid_ttl_s=600))

    # Python 3.8 grammar, and a light import
    for f in ("release_inputs.py", "run.py"):
        try:
            ast.parse(open(os.path.join(HERE, f)).read(), feature_version=(3, 8))
            ok = True
        except SyntaxError as err:
            ok, f = False, f"{f}: {err}"
        check(f"{f} parses as Python 3.8", ok)
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); "
                        "from bot.spot import release_inputs; "
                        "print(sorted(m for m in ('pandas', 'numpy', 'lightgbm') if m in sys.modules))", ROOT],
                       capture_output=True, text=True)
    check("importing release_inputs loads no pandas, numpy or lightgbm", r.stdout.strip() == "[]",
          r.stdout.strip() + r.stderr[-300:])


# ------------------------------------------------------------------------------------------------ part 2
STATE = {"last_minute": "2026-11-13T12:00:00", "equity": 10234.5, "peak": 10400.0, "day_start_equity": 10100.0,
         "dd_halt": False, "halted_day": None, "day": "2026-11-13",
         "ladders": {"ETH-1": {"id": "ETH-1", "status": "open",
                               "tranches": {"4": {"size": 0.5, "cost": 1500.0, "tp_px": 3050.0,
                                                  "exit_due": "2026-11-13T12:30:00"}},
                               "orders": {"o1": {"side": "SELL", "size": 0.5, "filled": 0.0, "px": 3050.0}}}}}


def old_lines(sd, capital):
    """Every line `run.py status` printed before release 3, for STATE (no STOP file in the repository root)."""
    return [f"state {sd}: last minute 2026-11-13T12:00:00",
            f"equity $10,234.50 (config capital ${capital:,.0f}); marked peak $10,400.00; day start $10,100.00",
            "halts: none",
            "  ETH-1      open  rungs {'4': '0.5 @ 3000 (tp 3050.0, exit 12:30)'} orders {'o1': 'SELL 0.5 @ 3050.0'}"]


def status(config, sd):
    r = subprocess.run([sys.executable, os.path.join(HERE, "run.py"), "status", "--config", config, "--state-dir", sd],
                       cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return r.returncode, r.stdout.splitlines(), r.stderr


def write_live(d, cfg):
    p = os.path.join(d, "config.live.json")
    with open(p, "w") as f:
        json.dump(cfg, f, indent=2)
    return p, open(p, "rb").read()


def part2():
    if os.path.exists(os.path.join(ROOT, "STOP")):
        check("part 2 needs no STOP file in the repository root", False)
        return
    tmp = tempfile.mkdtemp(prefix="relin_")
    sd = os.path.join(tmp, "live_spot")
    os.makedirs(sd)
    with open(os.path.join(sd, "state.json"), "w") as f:
        json.dump(STATE, f)
    eff = {k: BASE[k] for k in R.INPUT_KEYS if k in BASE}
    want = expected_line(BASE) + MARK
    print(f"  config.json inputs: {eff}", flush=True)
    try:
        # 1. a VM set up before release 3: config.json of that time (no input keys), capital changed
        old = {k: v for k, v in BASE.items() if k not in R.INPUT_KEYS}
        old["capital"] = 10000.0
        p, b = write_live(tmp, old)
        rc, out, err = status(p, sd)
        print("  [pre-release-3 live file]\n    " + "\n    ".join(out), flush=True)
        check("old live file: exit 0", rc == 0, err[-500:])
        check("old live file: the inputs line of config.json with the marker, first", out[:1] == [want], str(out[:1]))
        check("old live file: no note (the file had no input keys)", len(out) == 5, str(out))
        check("old live file: every line status printed before, unchanged and in order",
              out[1:] == old_lines(sd, 10000), str(out[1:]))
        if BASE.get("newest_bar") == "trades":
            check("old live file: trades mode for config.json's list, stale guard on",
                  "newest minute from trades for " + ", ".join(BASE.get("trades_coins") or []) in out[0]
                  and out[0].endswith("stale guard on" + MARK) and bool(BASE.get("stale_guard")), out[0])
        check("old live file: unchanged byte for byte", open(p, "rb").read() == b)

        # 2. made as setup_vm.sh makes it after release 3, then edited: the three keys with a different list
        new = dict(BASE, capital=0)
        new.update(newest_bar="trades", stale_guard=True, trades_coins=["BTC", "ETH"])
        p, b = write_live(tmp, new)
        rc, out, err = status(p, sd)
        print("  [live file with its own list]\n    " + "\n    ".join(out), flush=True)
        notes = [x for x in out[1:] if x.startswith("  ") and "live config had" in x]
        check("own list: exit 0, the release's line with the marker", rc == 0 and out[:1] == [want], str(out[:1]) + err)
        want_notes = sum(1 for k in ("newest_bar", "trades_coins", "stale_guard") if new.get(k) != BASE.get(k)
                         or (k in new) != (k in BASE))
        check("own list: one note per differing key, naming both lists",
              len(notes) == want_notes and any("trades_coins" in x and "['BTC', 'ETH']" in x for x in notes),
              str(notes))
        check("own list: then every line status printed before", out[1 + len(notes):] == old_lines(sd, 0),
              str(out[1 + len(notes):]))
        check("own list: unchanged byte for byte", open(p, "rb").read() == b)

        # 3. inputs_local
        loc = dict(old, inputs_local=True, newest_bar="candles")
        p, b = write_live(tmp, loc)
        rc, out, err = status(p, sd)
        print("  [inputs_local]\n    " + "\n    ".join(out), flush=True)
        check("inputs_local: the candle line, no marker, then the note", rc == 0 and out[:2] == [
            "inputs: candles for every coin; stale guard off",
            '  "inputs_local": true in the live config: its own input settings are used and do not follow releases'],
            str(out[:2]) + err)
        check("inputs_local: then every line status printed before", out[2:] == old_lines(sd, 10000), str(out[2:]))
        check("inputs_local: unchanged byte for byte", open(p, "rb").read() == b)

        # 4. a paper config runs what its own file says
        tb = os.path.join(HERE, "config.tb.json")
        tbb = open(tb, "rb").read()
        rc, out, err = status(tb, sd)
        print("  [config.tb.json]\n    " + "\n    ".join(out), flush=True)
        check("config.tb.json: its own line, no marker, no note",
              rc == 0 and out[:1] == [expected_line(json.loads(tbb))]
              and out[1:] == old_lines(sd, json.loads(tbb)["capital"]), str(out) + err)
        check("config.tb.json: unchanged", open(tb, "rb").read() == tbb)
    finally:
        shutil.rmtree(tmp)


# ------------------------------------------------------------------------------------------------ part 3
FAKE_ENGINE = '''"""Stand-in for bot/spot/engine.py in the temp tree: records what run.py does with the engine."""
import json
import os


class Engine:
    def __init__(self, mode, cfg, state_dir):
        self.sd = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self._w("init", mode=mode, newest_bar=cfg.get("newest_bar"), stale_guard=cfg.get("stale_guard"),
                trades_coins=cfg.get("trades_coins"))

    def _w(self, what, **kw):
        with open(os.path.join(self.sd, "calls.jsonl"), "a") as f:
            f.write(json.dumps(dict(what=what, **kw)) + "\\n")

    def log(self, kind, t=None, **kw):
        self._w("log", kind=kind, **kw)

    def run(self, minutes):
        self._w("run", minutes=minutes)
'''
NOTE = "inputs: bot/spot/config.json could not be read ("
TRADES = {"newest_bar": "trades", "trades_coins": ["BTC", "ETH"], "stale_guard": True}


def tree(base_cfg):
    """A temp copy of the package with run.py, release_inputs.py, a stand-in engine and the given config.json
    (dict, a string written as is, or None for no file). The real bot/spot/config.json is never touched."""
    t = tempfile.mkdtemp(prefix="relin_tree_")
    sp = os.path.join(t, "bot", "spot")
    os.makedirs(sp)
    for f in ("bot/__init__.py", "bot/spot/__init__.py", "bot/spot/run.py", "bot/spot/release_inputs.py"):
        shutil.copy(os.path.join(ROOT, f), os.path.join(t, f))
    with open(os.path.join(sp, "engine.py"), "w") as f:
        f.write(FAKE_ENGINE)
    if base_cfg is not None:
        with open(os.path.join(sp, "config.json"), "w") as f:
            f.write(base_cfg if isinstance(base_cfg, str) else json.dumps(base_cfg, indent=2))
    return t


def run_in(t, args, env=None):
    r = subprocess.run([sys.executable, "-B", os.path.join(t, "bot", "spot", "run.py")] + args, cwd=t,
                       capture_output=True, text=True, env=dict(os.environ, **(env or {})))
    return r.returncode, r.stdout.splitlines(), r.stderr


def calls(sd):
    p = os.path.join(sd, "calls.jsonl")
    return [json.loads(x) for x in open(p)] if os.path.exists(p) else []


def part3():
    live_env = {"COINBASE_API_KEY": "test-key", "COINBASE_API_SECRET": "test-secret",
                "I_UNDERSTAND_LIVE_TRADING": "yes"}
    old = {k: v for k, v in BASE.items() if k not in R.INPUT_KEYS}
    old["capital"] = 10000.0
    for label, base_cfg in (("config.json missing", None), ("config.json with bad JSON", '{"capital": 250000,')):
        t = tree(base_cfg)
        try:
            sd = os.path.join(t, "live_spot")
            os.makedirs(sd)
            with open(os.path.join(sd, "state.json"), "w") as f:
                json.dump(STATE, f)
            p, b = write_live(t, old)
            rc, out, err = run_in(t, ["status", "--config", p, "--state-dir", sd])
            print(f"  [{label}: status]\n    " + "\n    ".join(out), flush=True)
            check(f"{label}: status exits 0 with the note, the file's own line (no marker) and every old line",
                  rc == 0 and len(out) == 6 and out[0].startswith(NOTE) and out[0].endswith(
                      "; this file's own input settings are used")
                  and out[1] == "inputs: candles for every coin; stale guard off" and out[2:] == old_lines(sd, 10000),
                  str(out) + err[-300:])
            rc, out, err = run_in(t, ["stop", "--config", p])
            ok_stop = rc == 0 and os.path.exists(os.path.join(t, "STOP")) and out[:1] and out[0].startswith(NOTE)
            rc2, out2, err2 = run_in(t, ["resume", "--config", p])
            check(f"{label}: the kill switch stop and resume complete (STOP file written, then removed)",
                  ok_stop and rc2 == 0 and not os.path.exists(os.path.join(t, "STOP")), str(out + out2) + err + err2)
            lsd = os.path.join(t, "live_run")
            rc, out, err = run_in(t, ["live", "--config", p, "--state-dir", lsd, "--minutes", "0"], live_env)
            cl = calls(lsd)
            print(f"  [{label}: live with a stand-in engine]\n    " + "\n    ".join(out), flush=True)
            check(f"{label}: live starts on the file's own inputs, warns, logs the warning event, then runs",
                  rc == 0 and [c["what"] for c in cl] == ["init", "log", "run"] and cl[1]["kind"] == "warning"
                  and "without the release 3 inputs" in cl[1]["msg"] and cl[0]["newest_bar"] is None
                  and any(x.startswith("WARNING: ") for x in out) and out[0].startswith(NOTE), str(cl) + err[-300:])
            check(f"{label}: the live file is unchanged", open(p, "rb").read() == b)
        finally:
            shutil.rmtree(t)

    # live warning: present on candle inputs, absent on trades with the guard
    for label, base_cfg, warn in (("release on candles", {"capital": 1}, True), ("release on trades", TRADES, False),
                                  ("release on trades, guard off", dict(TRADES, stale_guard=False), True)):
        t = tree(base_cfg)
        try:
            p, _ = write_live(t, old)
            lsd = os.path.join(t, "live_run")
            rc, out, err = run_in(t, ["live", "--config", p, "--state-dir", lsd, "--minutes", "0"], live_env)
            cl = calls(lsd)
            w = [x for x in out if x.startswith("WARNING")]
            want = ["init", "log", "run"] if warn else ["init", "run"]
            check(f"live, {label}: warning line and warning event {'present' if warn else 'absent'}",
                  rc == 0 and [c["what"] for c in cl] == want and len(w) == (1 if warn else 0)
                  and (not warn or (cl[1]["kind"] == "warning" and w[0] == "WARNING: " + cl[1]["msg"]
                                    and cl[1]["msg"].endswith(R.describe(R.apply(old, base_cfg)[0])))),
                  str(out) + str(cl) + err[-300:])
            check(f"live, {label}: the engine got the release's inputs",
                  cl and cl[0]["newest_bar"] == base_cfg.get("newest_bar")
                  and cl[0]["stale_guard"] == base_cfg.get("stale_guard"), str(cl[:1]))
        finally:
            shutil.rmtree(t)
    t = tree(dict(TRADES, capital=1000))
    try:
        lsd = os.path.join(t, "live_run")
        rc, out, err = run_in(t, ["live", "--config", os.path.join(t, "bot", "spot", "config.json"), "--state-dir", lsd,
                                  "--minutes", "0"], {"COINBASE_API_KEY": "", "I_UNDERSTAND_LIVE_TRADING": "yes"})
        check("live: the key check still stops before the engine is built", rc != 0 and not calls(lsd)
              and "COINBASE_API_KEY" in err, err[-200:])
        rc, out, err = run_in(t, ["live", "--config", os.path.join(t, "bot", "spot", "config.json"), "--state-dir", lsd,
                                  "--minutes", "0"], dict(live_env, I_UNDERSTAND_LIVE_TRADING="no"))
        check("live: the live switch check still stops before the engine is built", rc != 0 and not calls(lsd)
              and "I_UNDERSTAND_LIVE_TRADING" in err, err[-200:])
    finally:
        shutil.rmtree(t)

    # the real engine's log writes a warning event (the call run.py makes; offline, paper mode)
    from bot.spot.engine import Engine
    d = tempfile.mkdtemp(prefix="relin_eng_")
    try:
        eng = Engine(mode="paper", cfg=dict(BASE), state_dir=d, echo=False)
        eng.log("warning", msg="test line")
        ev = [json.loads(x) for x in open(os.path.join(d, "events.jsonl"))]
        check("the real engine's log(\"warning\", msg=...) writes one warning event",
              len(ev) == 1 and ev[0]["kind"] == "warning" and ev[0]["msg"] == "test line", str(ev))
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    part1()
    part2()
    part3()
    print("RELEASE INPUTS TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
