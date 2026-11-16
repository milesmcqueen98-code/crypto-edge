"""One same-machine pair for measure 1(a) of Part 3 (reports/owner/bar_source_prereg.md, deviation log of Nov 16 2026,
12:04 ET): 30 minutes of paper steps with release 3's input settings and 30 minutes with the build's, one straight
after the other on one machine and on the pinned code, the order given. Standard library only. No orders, public
data only (what bot/spot/tb_smoke.py does).

Usage: python scripts/owner/step_pairs/run_pair.py --code CODE_DIR --main-config PATH --order ab|ba --minutes 30
           --out reports/owner/step_pairs

What it drives: CODE_DIR/bot/spot/tb_smoke.py, with the working directory at CODE_DIR:
  python bot/spot/tb_smoke.py --parity --minutes M --config bot/spot/config.json --state-dir DIR
         [--set KEY=JSON ...] --then KEY=JSON ...
The first run uses the config plus the --set overrides, the second the same config plus the --set and then the --then
overrides, in a fresh state dir. tb_smoke waits until the clock is at minute 20 or 50 of the hour before it starts.

Which settings are swapped: both runs use the BUILD's config file (CODE_DIR/bot/spot/config.json) as the base, so every
setting that is not an input is equal. The swapped settings are the keys of CODE_DIR/bot/spot/release_inputs.py
INPUT_KEYS without its ORDER_KEYS (the module is loaded from CODE_DIR by path). Release 3's value of a key is the one
--main-config has; a key it does not have is removed (JSON null). Only keys whose two values differ are passed.
  order ab: first run = release 3's inputs (--set), second = the build's inputs (--then).
  order ba: first run = the build's (no --set), second = release 3's (--then).
If the two config files differ in any key outside INPUT_KEYS (a key in one file only counts as a difference), the pair
does not run: the result file says counts false and why.

What it reads from the output (the output is split into runs at the lines that start with "=====", one per run):
  per-step table: the rows under "step timing (...)": minute, start_s, data_end_s, step_candles, step_trades,
    pass_candles. A row with a numeric data_end_s is a timed step; steps_timed is their number.
  the line "  median: step start X s, data step end Y s (max Z s); per step A candle and B trades requests; C candle
    requests between steps": Y is the run's median data step end (kept as printed, e.g. "9.70", and as a float), Z
    its maximum, A and B the per-step medians of candle and trades requests, C the median of candle requests between
    steps. These are the values as printed on that line (two decimals), not those of the last line of the output.
  refused: the run's text (leaving out its "=====" header and the table) matches, case-insensitively, REFUSED, Refused(
    or refus. This is what tb_smoke prints when the parity fetch is refused ("REFUSED (parity fetch stopped): ...") and
    what an engine error or warning event says of a refusal.
  limited: the run's text matches Limited(, 429, rate limit, rate-limit, too many requests, or a heartbeat counter
    "tb_fb_limited" above 0. A 429 on the parity fetch prints "REFUSED ... Limited('HTTP 429 ...')", so it sets both.
  tb_smoke exits 3 when a run was refused; any non-zero exit code makes counts false.

Result: <out>/pair_<UTC start YYYYMMDDTHHMM>Z.json with utc_start, utc_end, order, minutes, code_commit (git rev-parse
HEAD in CODE_DIR, or null), keys (each swapped key with its release 3 and build values and whether they differ), argv
(the command run), runs (two entries: inputs "release3" or "build", data_end_median_s, data_end_median_text,
data_end_max_s, steps_timed, step_candles_median, step_trades_median, pass_candles_median, refused, limited),
build_minus_release3_s (float) and build_minus_release3_text (exact decimal, from the printed medians), counts (true
only if both runs have at least 20 timed steps and a parsed median and neither refused nor limited, and the exit code
was 0) and why_not (null or a short reason). It never raises: any failure gives a result file with counts false and the
reason, and the exit code is 0.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

MIN_STEPS = 20
SMOKE = os.path.join("bot", "spot", "tb_smoke.py")
BUILD_CONFIG = os.path.join("bot", "spot", "config.json")
INPUTS = os.path.join("bot", "spot", "release_inputs.py")
REFUSED_RX = re.compile(r"REFUSED|Refused\(|refus", re.I)
LIMITED_RX = re.compile(r"Limited\(|\b429\b|rate.?limit|too many requests|\"tb_fb_limited\": [1-9]", re.I)
MEDIAN_RX = re.compile(r"median: step start (\S+) s, data step end (\S+) s \(max (\S+) s\); per step (\S+) candle and "
                       r"(\S+) trades requests; (\S+) candle requests between steps")
ROW_RX = re.compile(r"^\s*\d\d:\d\d\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$")


class NoPair(Exception):
    """The pair cannot be run or read; the message is the reason written to the result file."""


def now_utc():
    return datetime.now(timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_input_keys(code_dir):
    path = os.path.join(code_dir, INPUTS)
    if not os.path.isfile(path):
        raise NoPair(f"{INPUTS} not found in {code_dir}")
    spec = importlib.util.spec_from_file_location("pinned_release_inputs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    order = tuple(mod.ORDER_KEYS)
    return tuple(k for k in mod.INPUT_KEYS if k not in order), tuple(mod.INPUT_KEYS)


def jdump(v):
    return json.dumps(v, separators=(",", ":"))


def plan(build_cfg, main_cfg, swap_keys, all_input_keys, order):
    """The swapped keys and the overrides of both runs. Raises NoPair when the configs differ outside INPUT_KEYS."""
    if order not in ("ab", "ba"):
        raise NoPair(f"order must be ab or ba, not {order!r}")
    outside = sorted(k for k in set(build_cfg) | set(main_cfg) if k not in all_input_keys
                     and ((k in build_cfg) != (k in main_cfg) or build_cfg.get(k) != main_cfg.get(k)))
    if outside:
        raise NoPair("the two config files differ outside INPUT_KEYS: " + ", ".join(outside))
    keys = [dict(key=k, release3=main_cfg.get(k), build=build_cfg.get(k), differs=main_cfg.get(k) != build_cfg.get(k)
                 or (k in main_cfg) != (k in build_cfg)) for k in swap_keys]
    r3 = [f"{x['key']}={jdump(x['release3'])}" for x in keys if x["differs"]]
    bd = [f"{x['key']}={jdump(x['build'])}" for x in keys if x["differs"]]
    if order == "ab":
        sets, thens, runs = r3, bd, ("release3", "build")
    else:
        sets, thens, runs = [], r3, ("build", "release3")
    return dict(keys=keys, set=sets, then=thens, runs=runs)


def smoke_argv(minutes, state_dir, sets, thens):
    argv = [sys.executable, SMOKE, "--parity", "--minutes", f"{minutes:g}", "--config", BUILD_CONFIG, "--state-dir",
            state_dir]
    for x in sets:
        argv += ["--set", x]
    for x in thens:
        argv += ["--then", x]
    return argv


# ---------------------------------------------------------------- parsing
def split_runs(text):
    runs, cur = [], None
    for line in text.splitlines():
        if line.startswith("====="):
            cur = [line]
            runs.append(cur)
        elif cur is not None:
            cur.append(line)
    return runs


def num(s):
    try:
        d = Decimal(s)
        return d if d.is_finite() else None
    except (InvalidOperation, TypeError):
        return None


def parse_run(lines, label):
    """One run's figures from its lines (the first is the "=====" header)."""
    body = [l for l in lines[1:]]
    rows = [m for m in (ROW_RX.match(l) for l in body) if m]
    timed = sum(1 for m in rows if num(m.group(2)) is not None)
    med = None
    for l in body:
        m = MEDIAN_RX.search(l)
        if m:
            med = m
    text = "\n".join(l for l in body if not ROW_RX.match(l))
    out = dict(inputs=label, steps_timed=timed, data_end_median_s=None, data_end_median_text=None, data_end_max_s=None,
               step_candles_median=None, step_trades_median=None, pass_candles_median=None,
               refused=bool(REFUSED_RX.search(text)), limited=bool(LIMITED_RX.search(text)))
    if med:
        d = num(med.group(2))
        if d is not None:
            out["data_end_median_text"] = med.group(2)
            out["data_end_median_s"] = float(d)
        for k, g in (("data_end_max_s", 3), ("step_candles_median", 4), ("step_trades_median", 5),
                     ("pass_candles_median", 6)):
            v = num(med.group(g))
            out[k] = None if v is None else float(v)
    return out


def judge(runs, rc):
    """(counts, why_not) for the two parsed runs and tb_smoke's exit code."""
    if rc is not None and rc != 0:
        return False, f"tb_smoke exited with code {rc}" + (" (a run met a refusal or a rate limit)" if rc == 3 else "")
    if len(runs) != 2:
        return False, f"expected 2 runs in the output, found {len(runs)}"
    for r in runs:
        if r["refused"]:
            return False, f"the {r['inputs']} run met a refusal"
        if r["limited"]:
            return False, f"the {r['inputs']} run met a rate limit"
        if r["data_end_median_text"] is None:
            return False, f"no median line could be read for the {r['inputs']} run"
        if r["steps_timed"] < MIN_STEPS:
            return False, f"the {r['inputs']} run has {r['steps_timed']} timed steps, {MIN_STEPS} needed"
    return True, None


def difference(runs):
    """(float, exact decimal text) of the build's median minus release 3's, from the printed medians, or (None, None)."""
    by = {r["inputs"]: r for r in runs}
    try:
        b, a = Decimal(by["build"]["data_end_median_text"]), Decimal(by["release3"]["data_end_median_text"])
    except (KeyError, InvalidOperation, TypeError):
        return None, None
    d = b - a
    return float(d), format(d, "f")


# ---------------------------------------------------------------- running
def git_commit(code_dir):
    try:
        r = subprocess.run(["git", "-C", code_dir, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)
        c = r.stdout.strip()
        return c if r.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", c) else None
    except Exception:
        return None


def run_smoke(code_dir, argv, timeout_s):
    """(output, exit code or None, timed out). The output is echoed as it comes."""
    p = subprocess.Popen(argv, cwd=code_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         errors="replace")
    hit = []

    def kill():
        hit.append(1)
        p.kill()
    timer = threading.Timer(timeout_s, kill)
    timer.start()
    lines = []
    try:
        for line in p.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            lines.append(line)
        p.wait()
    finally:
        timer.cancel()
    return "".join(lines), p.returncode, bool(hit)


def pair(code_dir, main_config, order, minutes, out, start=None):
    """Run one pair and write its result file; returns the result dict. Never raises."""
    start = start or now_utc()
    res = dict(utc_start=iso(start), utc_end=None, order=order, minutes=minutes, code_commit=None, keys=[], argv=None,
               runs=[], build_minus_release3_s=None, build_minus_release3_text=None, counts=False, why_not=None)
    try:
        res["code_commit"] = git_commit(code_dir)
        swap, allk = load_input_keys(code_dir)
        bpath = os.path.join(code_dir, BUILD_CONFIG)
        if not os.path.isfile(bpath):
            raise NoPair(f"{BUILD_CONFIG} not found in {code_dir}")
        if not os.path.isfile(main_config):
            raise NoPair(f"main config {main_config} not found")
        pl = plan(json.load(open(bpath)), json.load(open(main_config)), swap, allk, order)
        res["keys"] = pl["keys"]
        if not os.path.isfile(os.path.join(code_dir, SMOKE)):
            raise NoPair(f"{SMOKE} not found in {code_dir}")
        state = os.path.join(tempfile.mkdtemp(prefix="step_pair_"), "s")
        argv = smoke_argv(minutes, state, pl["set"], pl["then"])
        res["argv"] = argv[1:]
        text, rc, timed_out = run_smoke(code_dir, argv, (2 * minutes + 45) * 60)
        runs = [parse_run(r, lab) for r, lab in zip(split_runs(text), pl["runs"])]
        n_found = len(split_runs(text))
        res["runs"] = runs
        res["build_minus_release3_s"], res["build_minus_release3_text"] = difference(runs)
        if timed_out:
            res["why_not"] = f"tb_smoke was stopped after {2 * minutes + 45} minutes"
        elif n_found != 2:
            res["why_not"] = f"expected 2 runs in the output, found {n_found}"
        else:
            res["counts"], res["why_not"] = judge(runs, rc)
    except NoPair as exc:
        res["why_not"] = str(exc)
    except Exception as exc:
        res["why_not"] = f"failed: {type(exc).__name__}: {exc}"[:300]
    res["counts"] = bool(res["counts"]) and res["why_not"] is None
    res["utc_end"] = iso(now_utc())
    try:
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, "pair_" + start.strftime("%Y%m%dT%H%M") + "Z.json")
        with open(path, "w") as f:
            json.dump(res, f, indent=1)
            f.write("\n")
        print(f"pair result: {path}: counts {res['counts']}"
              + (f", build minus release 3 {res['build_minus_release3_text']} s" if res["counts"] else f", {res['why_not']}"))
    except Exception as exc:
        print("could not write the result file:", repr(exc))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--main-config", required=True)
    ap.add_argument("--order", required=True)
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--out", default=os.path.join("reports", "owner", "step_pairs"))
    ap.add_argument("--dry-run", action="store_true", help="print the command it would run and stop (no tb_smoke)")
    a = ap.parse_args(argv)
    if a.dry_run:
        swap, allk = load_input_keys(a.code)
        pl = plan(json.load(open(os.path.join(a.code, BUILD_CONFIG))), json.load(open(a.main_config)), swap, allk, a.order)
        print(json.dumps(dict(order=a.order, runs=pl["runs"], keys=pl["keys"], set=pl["set"], then=pl["then"],
                              argv=smoke_argv(a.minutes, "STATE_DIR", pl["set"], pl["then"])[1:]), indent=1))
        return 0
    try:
        pair(a.code, a.main_config, a.order, a.minutes, a.out)
    except Exception as exc:                       # never fails the job
        print("run_pair failed:", repr(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
