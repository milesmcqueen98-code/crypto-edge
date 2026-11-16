"""One same-machine pair for Part 3 of reports/owner/trades_workers_plan.md: 30 minutes of paper steps with
trades_workers 1 ("one") and 30 minutes with trades_workers 3 ("three"), one straight after the other on one machine and on
the pinned code, the order given. Standard library only. No orders, public data only (what bot/spot/tb_smoke.py does).
This is the second tool beside run_pair.py (release 3 against the build, the fifth book's test), which stays as it is;
the functions of run_pair.py that fit unchanged are imported (the split into runs, the number reader, the refusal and
rate-limit patterns, the median-line pattern, the run of tb_smoke).

Usage: python scripts/owner/step_pairs/run_pair_workers.py --code CODE_DIR --order ab|ba --minutes 30
           --out reports/owner/step_pairs_tw

What it drives: CODE_DIR/bot/spot/tb_smoke.py, with the working directory at CODE_DIR:
  python bot/spot/tb_smoke.py --parity --minutes M --config bot/spot/config.tw.json --state-dir DIR
         --set trades_workers=A --then trades_workers=B
Both runs use the candidate's bot/spot/config.tw.json as the base (the release build's config plus trades_workers 3).
  order ab: first run trades_workers=1 (--set), second trades_workers=3 (--then).
  order ba: first run trades_workers=3 (--set), second trades_workers=1 (--then).
If config.tw.json is missing in the code folder, or "trades_workers" is not in CODE_DIR/bot/spot/release_inputs.py
INPUT_KEYS, the pair does not run: the result file says counts false and why.

What it reads from the output (split into runs at the lines that start with "=====", one per run; the formats are
those printed by the candidate's tb_smoke.py):
  step table under "step timing (...)": minute, start_s, data_end_s, step_candles, step_trades, pass_candles, trades_s,
    fb_budget (seven columns after the minute; a cell may be NaN or None). A row with a numeric data_end_s is a timed
    step; steps_timed is their number. (run_pair.py's row pattern takes five columns and would read none of these.)
  "  median: step start X s, data step end Y s (max Z s); per step A candle and B trades requests; C candle requests
    between steps": Y is the run's median data step end (kept as printed, and as a float), Z its maximum.
  "  trades pass (<label>; engine timer): median X s, longest Y s; budget fallbacks (tb_fb_budget) N": the trades pass's
    median and longest duration (as printed, and as floats) and the budget fallbacks of the run. When the run has no
    such line (newest_bar not trades: "trades pass (<label>): none in the steps") these are null.
  "  trades requests (<label>): at most P sent in any one second (start-up pass included)": peak_per_second.
  the parity table (header "coin minutes identical differ ..."): rows_compared is the sum of its minutes column, rows_differ
    the sum of its differ column, over the coins listed.
  refused and limited: run_pair.py's own patterns (REFUSED_RX, LIMITED_RX, imported, not changed), searched over the
    run's text leaving out its "=====" header and the step table, as run_pair.py does. See that file for the patterns.
    Known to fire on numbers (see the notes of the test file): a heartbeat counter equal to 429, or a price such as
    429.5 in an event line, reads as an HTTP 429. The patterns are not loosened here.
  tb_smoke exits 3 when a run was refused; any non-zero exit code makes counts false.

Result: <out>/pair_<UTC start YYYYMMDDTHHMM>Z.json with mode "workers", utc_start, utc_end, order, minutes, code_commit
(git rev-parse HEAD in CODE_DIR, or null), argv (the command run), runs (two entries, in the order run: workers 1 or 3,
label "one" or "three", data_end_median_text and data_end_median_s, data_end_max_s, steps_timed, trades_pass_median_text
and _s, trades_pass_longest_text and _s, fb_budget, peak_per_second, rows_compared, rows_differ, refused, limited; a
figure that cannot be read is null), three_minus_one_s and three_minus_one_text (the data step medians, three's minus
one's, exact decimal from the printed texts), longest_three_minus_one_s and longest_three_minus_one_text (the trades
pass's longest, three minus one, exact decimal), counts (true only if both runs have at least 20 timed steps and every
figure above was read, neither run met a refusal or a rate limit, and the exit code was 0) and why_not (null or a short
reason). It never raises: any failure gives a result file with counts false and the reason, and the exit code is 0.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_pair as rp       # noqa: E402

MIN_STEPS = rp.MIN_STEPS
SMOKE = rp.SMOKE
CONFIG = os.path.join("bot", "spot", "config.tw.json")
KEY = "trades_workers"
ROW_RX = re.compile(r"^\s*\d\d:\d\d\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$")
PASS_RX = re.compile(r"trades pass \(.*; engine timer\): median (\S+) s, longest (\S+) s; budget fallbacks "
                     r"\(tb_fb_budget\) (\S+)")
PEAK_RX = re.compile(r"trades requests \(.*\): at most (\S+) sent in any one second")
PARITY_HEAD_RX = re.compile(r"^\s*coin\s+minutes\s+identical\s+differ\b")


def plan(order):
    """The overrides and the two runs (workers, label) in the order run. Raises NoPair for a bad order."""
    if order == "ab":
        return dict(set=[f"{KEY}=1"], then=[f"{KEY}=3"], runs=((1, "one"), (3, "three")))
    if order == "ba":
        return dict(set=[f"{KEY}=3"], then=[f"{KEY}=1"], runs=((3, "three"), (1, "one")))
    raise rp.NoPair(f"order must be ab or ba, not {order!r}")


def smoke_argv(minutes, state_dir, sets, thens):
    argv = [sys.executable, SMOKE, "--parity", "--minutes", f"{minutes:g}", "--config", CONFIG, "--state-dir", state_dir]
    for x in sets:
        argv += ["--set", x]
    for x in thens:
        argv += ["--then", x]
    return argv


# ---------------------------------------------------------------- parsing
def to_int(s):
    return int(s) if isinstance(s, str) and re.fullmatch(r"\d+", s) else None


def parity_sums(body):
    """(rows compared, rows that differ) summed over the parity table's coins, or (None, None)."""
    for i, l in enumerate(body):
        if not PARITY_HEAD_RX.match(l):
            continue
        head = l.split()
        im, idf = head.index("minutes"), head.index("differ")
        tot_m = tot_d = n = 0
        for r in body[i + 1:]:
            if not r.strip():
                break
            t = r.split()
            m, d = (to_int(t[im]) if len(t) > im else None), (to_int(t[idf]) if len(t) > idf else None)
            if m is None or d is None:
                return None, None
            tot_m, tot_d, n = tot_m + m, tot_d + d, n + 1
        return (tot_m, tot_d) if n else (None, None)
    return None, None


def parse_run(lines, workers, label):
    """One run's figures from its lines (the first is the "=====" header)."""
    body = list(lines[1:])
    rows = [m for m in (ROW_RX.match(l) for l in body) if m]
    timed = sum(1 for m in rows if rp.num(m.group(2)) is not None)
    med = pas = peak = None
    for l in body:
        m = rp.MEDIAN_RX.search(l)
        if m:
            med = m
        m = PASS_RX.search(l)
        if m:
            pas = m
        m = PEAK_RX.search(l)
        if m:
            peak = m
    text = "\n".join(l for l in body if not ROW_RX.match(l))
    out = dict(workers=workers, label=label, data_end_median_text=None, data_end_median_s=None, data_end_max_s=None,
               steps_timed=timed, trades_pass_median_text=None, trades_pass_median_s=None,
               trades_pass_longest_text=None, trades_pass_longest_s=None, fb_budget=None, peak_per_second=None,
               rows_compared=None, rows_differ=None, refused=bool(rp.REFUSED_RX.search(text)),
               limited=bool(rp.LIMITED_RX.search(text)))
    if med:
        d = rp.num(med.group(2))
        if d is not None:
            out["data_end_median_text"] = med.group(2)
            out["data_end_median_s"] = float(d)
        v = rp.num(med.group(3))
        out["data_end_max_s"] = None if v is None else float(v)
    if pas:
        for k, g in (("median", 1), ("longest", 2)):
            d = rp.num(pas.group(g))
            if d is not None:
                out[f"trades_pass_{k}_text"] = pas.group(g)
                out[f"trades_pass_{k}_s"] = float(d)
        out["fb_budget"] = to_int(pas.group(3))
    if peak:
        out["peak_per_second"] = to_int(peak.group(1))
    out["rows_compared"], out["rows_differ"] = parity_sums(body)
    return out


FIGURES = ("data_end_median_text", "data_end_max_s", "trades_pass_median_text", "trades_pass_longest_text", "fb_budget",
           "peak_per_second", "rows_compared", "rows_differ")


def judge(runs, rc):
    """(counts, why_not) for the two parsed runs and tb_smoke's exit code."""
    if rc is not None and rc != 0:
        return False, f"tb_smoke exited with code {rc}" + (" (a run met a refusal or a rate limit)" if rc == 3 else "")
    if len(runs) != 2:
        return False, f"expected 2 runs in the output, found {len(runs)}"
    for r in runs:
        if r["refused"]:
            return False, f"the {r['label']} run met a refusal"
        if r["limited"]:
            return False, f"the {r['label']} run met a rate limit"
        if r["data_end_median_text"] is None:
            return False, f"no median line could be read for the {r['label']} run"
        if r["steps_timed"] < MIN_STEPS:
            return False, f"the {r['label']} run has {r['steps_timed']} timed steps, {MIN_STEPS} needed"
        missing = [k for k in FIGURES if r[k] is None]
        if missing:
            return False, f"not read for the {r['label']} run: " + ", ".join(missing)
    return True, None


def diff_texts(runs, key):
    """(float, exact decimal text) of three's printed figure minus one's, or (None, None)."""
    by = {r["label"]: r for r in runs}
    try:
        d = Decimal(by["three"][key]) - Decimal(by["one"][key])
    except (KeyError, InvalidOperation, TypeError):
        return None, None
    return float(d), format(d, "f")


# ---------------------------------------------------------------- running
def pair(code_dir, order, minutes, out, start=None):
    """Run one pair and write its result file; returns the result dict. Never raises."""
    start = start or rp.now_utc()
    res = dict(mode="workers", utc_start=rp.iso(start), utc_end=None, order=order, minutes=minutes, code_commit=None,
               argv=None, runs=[], three_minus_one_s=None, three_minus_one_text=None, longest_three_minus_one_s=None,
               longest_three_minus_one_text=None, counts=False, why_not=None)
    try:
        res["code_commit"] = rp.git_commit(code_dir)
        pl = plan(order)
        _, allk = rp.load_input_keys(code_dir)
        if not os.path.isfile(os.path.join(code_dir, CONFIG)):
            raise rp.NoPair(f"{CONFIG} not found in {code_dir}")
        if KEY not in allk:
            raise rp.NoPair(f"{KEY} is not in INPUT_KEYS of {rp.INPUTS} in {code_dir}")
        if not os.path.isfile(os.path.join(code_dir, SMOKE)):
            raise rp.NoPair(f"{SMOKE} not found in {code_dir}")
        state = os.path.join(tempfile.mkdtemp(prefix="step_pair_tw_"), "s")
        argv = smoke_argv(minutes, state, pl["set"], pl["then"])
        res["argv"] = argv[1:]
        text, rc, timed_out = rp.run_smoke(code_dir, argv, (2 * minutes + 45) * 60)
        found = rp.split_runs(text)
        runs = [parse_run(r, w, lab) for r, (w, lab) in zip(found, pl["runs"])]
        res["runs"] = runs
        res["three_minus_one_s"], res["three_minus_one_text"] = diff_texts(runs, "data_end_median_text")
        res["longest_three_minus_one_s"], res["longest_three_minus_one_text"] = diff_texts(runs, "trades_pass_longest_text")
        if timed_out:
            res["why_not"] = f"tb_smoke was stopped after {2 * minutes + 45} minutes"
        elif len(found) != 2:
            res["why_not"] = f"expected 2 runs in the output, found {len(found)}"
        else:
            res["counts"], res["why_not"] = judge(runs, rc)
    except rp.NoPair as exc:
        res["why_not"] = str(exc)
    except Exception as exc:
        res["why_not"] = f"failed: {type(exc).__name__}: {exc}"[:300]
    res["counts"] = bool(res["counts"]) and res["why_not"] is None
    res["utc_end"] = rp.iso(rp.now_utc())
    try:
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, "pair_" + start.strftime("%Y%m%dT%H%M") + "Z.json")
        with open(path, "w") as f:
            json.dump(res, f, indent=1)
            f.write("\n")
        print(f"pair result: {path}: counts {res['counts']}"
              + (f", three minus one {res['three_minus_one_text']} s" if res["counts"] else f", {res['why_not']}"))
    except Exception as exc:
        print("could not write the result file:", repr(exc))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--order", required=True)
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--out", default=os.path.join("reports", "owner", "step_pairs_tw"))
    ap.add_argument("--dry-run", action="store_true", help="print the command it would run and stop (no tb_smoke)")
    a = ap.parse_args(argv)
    if a.dry_run:
        pl = plan(a.order)
        print(json.dumps(dict(order=a.order, runs=pl["runs"], set=pl["set"], then=pl["then"],
                              argv=smoke_argv(a.minutes, "STATE_DIR", pl["set"], pl["then"])[1:]), indent=1))
        return 0
    try:
        pair(a.code, a.order, a.minutes, a.out)
    except Exception as exc:                       # never fails the job
        print("run_pair_workers failed:", repr(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
