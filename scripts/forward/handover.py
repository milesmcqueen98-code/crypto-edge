#!/usr/bin/env python3
"""Hand-over between GitHub Actions runs of the forward collector (.github/workflows/forward-collector.yml).

A run collects for ~5h45m, dispatches its successor 5 minutes before it stops, and keeps collecting until its
planned end, so the two overlap by a few minutes and there is no gap (readers de-duplicate the overlap). An hourly
schedule is the safety net after a crash: a scheduled run that finds a collector already collecting exits at once.

The one rule, applied when a run starts and every few minutes while it collects:
  stop if another run of this workflow is in its "Collect" step, has a lower run id, and is not my predecessor.
So the oldest collector wins any duplicate, a successor never stops because of its predecessor, and a predecessor
never stops because of its successor (higher id).

  handover.py check  --predecessor <id>          exit 0 = collect, 3 = another collector has priority
  handover.py watch  --predecessor <id> --end <epoch> --pid <collector pid> --stop-file <path>
                     dispatches the successor at end - 5 min, and stops the collector if the rule says so
Needs GITHUB_TOKEN (actions: write), GITHUB_REPOSITORY and GITHUB_RUN_ID; uses the REST API only.
"""
import argparse
import os
import signal
import sys
import time

import requests

API = "https://api.github.com"
STEP = "Collect"


def decide(me, collecting, predecessor=None):
    """me: my run id; collecting: ids of runs currently in the Collect step. -> 'collect' or 'exit'."""
    pred = int(predecessor) if predecessor else None
    blockers = [r for r in collecting if r != me and r != pred and r < me]
    return ("exit", min(blockers)) if blockers else ("collect", None)


class GH:
    def __init__(self, repo=None, token=None, workflow=None):
        self.repo = repo or os.environ["GITHUB_REPOSITORY"]
        self.wf = workflow or "forward-collector.yml"
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token or os.environ['GITHUB_TOKEN']}",
                               "Accept": "application/vnd.github+json", "User-Agent": "crypto-edge-bot/1.0"})

    def get(self, path, **params):
        for a in range(4):
            try:
                r = self.s.get(f"{API}/repos/{self.repo}/{path}", params=params, timeout=20)
                r.raise_for_status()
                return r.json()
            except requests.RequestException:
                if a == 3:
                    raise
                time.sleep(3 * (a + 1))

    def collecting(self, step=STEP):
        """Run ids of this workflow whose job is currently in the given step."""
        runs = self.get(f"actions/workflows/{self.wf}/runs", status="in_progress", per_page=50).get("workflow_runs", [])
        out = []
        for run in runs:
            for job in self.get(f"actions/runs/{run['id']}/jobs").get("jobs", []):
                if any(s.get("name") == step and s.get("status") == "in_progress" for s in job.get("steps") or []):
                    out.append(int(run["id"]))
                    break
        return out

    def dispatch(self, ref, inputs):
        r = self.s.post(f"{API}/repos/{self.repo}/actions/workflows/{self.wf}/dispatches",
                        json={"ref": ref, "inputs": inputs}, timeout=20)
        if r.status_code not in (200, 204):
            raise RuntimeError(f"dispatch {r.status_code}: {r.text[:200]}")


def log(msg):
    print(f"[handover {time.strftime('%H:%M:%S', time.gmtime())}Z] {msg}", flush=True)


def cmd_check(a, gh):
    me = int(a.run_id)
    try:
        cols = gh.collecting(a.step)
    except Exception as err:                            # noqa: BLE001 - when in doubt, collect (overlap is de-duplicated)
        log(f"could not list runs ({err}); collecting")
        return 0
    verdict, who = decide(me, cols, a.predecessor)
    log(f"run {me}, predecessor {a.predecessor or '-'}, collecting now {cols}: {verdict}"
        + (f" (run {who} has priority)" if who else ""))
    return 0 if verdict == "collect" else 3


def cmd_watch(a, gh):
    me, dispatched = int(a.run_id), False
    next_check = time.time() + 60
    while time.time() < a.end:
        if not dispatched and time.time() >= a.end - a.lead:
            try:
                gh.dispatch(a.ref, {"predecessor": str(me), "minutes": str(a.minutes)})
                dispatched = True
                log(f"successor dispatched on {a.ref}")
            except Exception as err:                    # noqa: BLE001 - retry; the hourly schedule is the net
                log(f"dispatch failed: {err}")
        if time.time() >= next_check:
            next_check = time.time() + a.every
            try:
                verdict, who = decide(me, gh.collecting(a.step), a.predecessor)
            except Exception as err:                    # noqa: BLE001
                log(f"check failed: {err}")
                verdict, who = "collect", None
            if verdict == "exit":
                log(f"run {who} is an older collector: stopping this one")
                open(a.stop_file, "w").close()
                try:
                    os.kill(int(open(a.pid).read().strip()) if os.path.exists(a.pid) else -1, signal.SIGTERM)
                except (OSError, ValueError):
                    pass
                return 0
        time.sleep(15)
    if not dispatched:
        log("ended without dispatching a successor; the hourly schedule will start one")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "watch"])
    ap.add_argument("--predecessor", default="")
    ap.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "0"))
    ap.add_argument("--workflow", default="forward-collector.yml")
    ap.add_argument("--step", default=STEP)
    ap.add_argument("--ref", default=os.environ.get("GITHUB_REF_NAME", "main"))
    ap.add_argument("--end", type=float, default=0)
    ap.add_argument("--lead", type=float, default=300, help="dispatch the successor this many seconds before the end")
    ap.add_argument("--every", type=float, default=300, help="re-check for duplicates this often (seconds)")
    ap.add_argument("--minutes", default="345")
    ap.add_argument("--pid", default="collector.pid")
    ap.add_argument("--stop-file", default="collector.stop")
    a = ap.parse_args(argv)
    gh = GH(workflow=a.workflow)
    return cmd_check(a, gh) if a.cmd == "check" else cmd_watch(a, gh)


if __name__ == "__main__":
    sys.exit(main())
