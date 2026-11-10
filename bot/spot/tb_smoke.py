#!/usr/bin/env python3
"""Paper smoke run of the trades book on live public data, for the generic runner (hunt2.yml takes a script, not a
command). Waits until the run will cover a heartbeat minute (:00 or :30), then runs
  python bot/spot/run.py paper --minutes <minutes> --config bot/spot/config.tb.json --state-dir <state_dir>
and prints the tail of its event log and every heartbeat. No keys, no orders.

Usage: python bot/spot/tb_smoke.py [--minutes 10] [--state-dir /tmp/tb_smoke]
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

p = argparse.ArgumentParser()
p.add_argument("--minutes", type=float, default=10)
p.add_argument("--state-dir", default="/tmp/tb_smoke")
a = p.parse_args()

# start at minute 20 or 50 of the hour: the backfill takes a few minutes and the steps then cross :30 or :00
while int(time.time() // 60) % 30 != 20:
    time.sleep(5)
cmd = [sys.executable, os.path.join(HERE, "run.py"), "paper", "--minutes", str(a.minutes), "--config",
       os.path.join(HERE, "config.tb.json"), "--state-dir", a.state_dir]
print("running:", " ".join(cmd), flush=True)
rc = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
print("exit code", rc.returncode)
if rc.stderr:
    print("stderr tail:\n" + rc.stderr[-3000:])
ev = [json.loads(x) for x in open(os.path.join(a.state_dir, "events.jsonl"))]
kinds = {}
for e in ev:
    kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
print("event kinds:", kinds)
print("\nlast 25 events (adv lines shortened):")
for e in ev[-25:]:
    s = json.dumps(e)
    print(s if len(s) < 600 else s[:600] + " ...")
print("\nheartbeats:")
for e in ev:
    if e["kind"] == "heartbeat":
        print(json.dumps(e))
sys.exit(rc.returncode)
