"""Runs every offline spot test on a runner (whole repository checked out, so data/minute and data/cfm are there) and
prints each file's tally: exit code, PASS/ok lines, FAIL lines, the result lines, the time taken. For hunt2.yml, which
runs one script. One test at a time (memory). sandbox_test.py is not run: it needs Coinbase's sandbox (its own
workflow, sandbox-test.yml). trades_bar_check.py and tb_smoke.py are not run: they need the network.

  python scripts/owner/release3/run_spot_tests.py

Reads bot, edge, scripts/owner, scripts/forward (input_checks.py, for test_bar_source.py), reports/cfm_products.csv,
reports/wick1m/spot_ticks_wide.csv, data/minute and data/cfm.
"""
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
WINDOW = ["2025-10-10 20:00", "2025-10-11 02:00"]
DEATH = "--death=2025-10-10 21:10"
PY = [("merge_test.py", []), ("trades_bar_test.py", []), ("usdc_test.py", []), ("newest_bar_test.py", []),
      ("release_inputs_test.py", []), ("replay_test.py", ["2025-10-10", "2025-10-12"]),
      ("live_sim_test.py", WINDOW), ("live_sim_test.py", WINDOW + [DEATH]),
      ("live_sim_inputs_test.py", WINDOW), ("live_sim_inputs_test.py", WINDOW + [DEATH])]
SH = ["paper_next_test.sh", "paper_commit_test.sh", "wickctl_test.sh"]
OTHER = ["bot/spot/deploy/watchdog_test.py",
         "scripts/owner/bar_source/test_bar_source.py"]   # builds an engine from bot/spot/config.json (no stepping)
# the result lines each file prints (shown in full; the rest of the output is in the tail below)
KEY = re.compile(r"^(engine:|PARITY|MISMATCHES|paper settings|\d+ minutes in|entries |bot equity|server dies|back at|"
                 r"switch at|inputs from|trades feed|  first difference|  C, whole log|  [BC]: heartbeats|"
                 r"[A-Z ]+TEST (PASSED|FAILED)|.*: all passed)")


def run(cmd, label):
    t0 = time.time()
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    out = r.stdout + r.stderr
    npass = len(re.findall(r"^(PASS|ok)\b", out, re.M))
    nfail = len(re.findall(r"^FAIL\b", out, re.M))
    print(f"=== {label}: exit {r.returncode}, PASS/ok {npass}, FAIL {nfail}, {time.time() - t0:.0f} s", flush=True)
    for line in out.splitlines():
        if KEY.match(line):
            print("  | " + line, flush=True)
    print(out[-4000:], flush=True)
    return r.returncode != 0 or nfail > 0


def main():
    bad = 0
    for f, args in PY:
        bad += run([sys.executable, os.path.join(ROOT, "bot", "spot", f)] + args, " ".join([f] + args))
    for f in SH:
        bad += run(["bash", os.path.join(ROOT, "bot", "spot", "deploy", f)], f)
    for f in OTHER:
        bad += run([sys.executable, os.path.join(ROOT, f)], f)
    print(f"files with a failure: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
