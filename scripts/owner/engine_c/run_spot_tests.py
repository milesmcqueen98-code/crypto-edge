"""Runs the spot engine's offline test files on a runner (whole repository checked out, so data/minute is there) and
prints each file's tally: exit code, PASS/ok lines, FAIL lines. For hunt2.yml, which runs one script.
sandbox_test.py is not run: it needs Coinbase sandbox keys (its own workflow, sandbox-test.yml).

  python scripts/owner/engine_c/run_spot_tests.py
"""
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TESTS = [("merge_test.py", []), ("trades_bar_test.py", []), ("usdc_test.py", []), ("newest_bar_test.py", []),
         ("candle_after_test.py", []), ("replay_test.py", ["2025-10-10", "2025-10-12"]),
         ("live_sim_test.py", ["2025-10-10 20:00", "2025-10-11 02:00", "--death=2025-10-10 21:10"])]


def main():
    bad = 0
    for f, args in TESTS:
        t0 = time.time()
        r = subprocess.run([sys.executable, os.path.join(ROOT, "bot", "spot", f)] + args, cwd=ROOT,
                           capture_output=True, text=True)
        out = r.stdout + r.stderr
        npass = len(re.findall(r"^(PASS|ok)\b", out, re.M))
        nfail = len(re.findall(r"^FAIL\b", out, re.M))
        print(f"=== {f} {' '.join(args)}: exit {r.returncode}, PASS/ok {npass}, FAIL {nfail}, {time.time() - t0:.0f} s",
              flush=True)
        print(out[-6000:], flush=True)
        bad += r.returncode != 0 or nfail > 0
    print(f"files with a failure: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
