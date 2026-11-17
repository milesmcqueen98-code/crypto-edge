#!/usr/bin/env bash
# Hand-over for .github/workflows/paper-spot.yml and paper-spot-t18.yml (job "next"): start the next run of the
# workflow named by WORKFLOW (default paper-spot.yml) on main, so the paper books do not wait for GitHub's
# often-dropped schedule. It starts one only when:
#   - this run came from the schedule or a manual dispatch (not from anything else), and
#   - this run has lasted at least MIN_MINUTES (default 30), so a run that fails at start cannot loop.
# The cron line stays as the backstop. A run started now waits in the workflow's concurrency group until this one ends.
# Test jobs: once the next run has been started, a run of paper-spot-r5.yml also starts step-pairs.yml (same-machine
# pair; reports/owner/bar_source_prereg.md Part 3) and a run of paper-spot-tw.yml also starts workers-alt.yml
# (alternating job; reports/owner/trades_workers_plan.md Part 3), because GitHub's schedule drops most of their runs.
# A test job that fails to start never fails the hand-over. The cron lines of the two test workflows stay.
# Env: EVENT, RUN_ID, REPO (owner/name), GH_TOKEN for gh; WORKFLOW (optional, the workflow file to start, default
# paper-spot.yml); MIN_MINUTES and NOW (epoch seconds) are for tests.
# Usage: bash bot/spot/deploy/paper_next.sh   (test: bash bot/spot/deploy/paper_next_test.sh)
set -u
min=${MIN_MINUTES:-30}
wf=${WORKFLOW:-paper-spot.yml}
case "${EVENT:-}" in
  schedule|workflow_dispatch) ;;
  *) echo "no hand-over: event ${EVENT:-none}"; exit 0 ;;
esac
started=$(gh api "repos/$REPO/actions/runs/$RUN_ID" --jq .run_started_at) || started=""
if [ -z "$started" ]; then echo "no hand-over: could not read when this run started"; exit 0; fi
s=$(date -u -d "$started" +%s 2>/dev/null) || s=""
if [ -z "$s" ]; then echo "no hand-over: unreadable start time $started"; exit 0; fi
now=${NOW:-$(date -u +%s)}
el=$(( (now - s) / 60 ))
if [ "$el" -lt "$min" ]; then echo "no hand-over: this run lasted $el min, less than $min"; exit 0; fi
if gh workflow run "$wf" --ref main -R "$REPO"; then
  echo "hand-over: next run started after $el min"
else
  echo "hand-over failed: the schedule is the backstop"; exit 1
fi
case "$wf" in
  paper-spot-r5.yml) tj=step-pairs.yml ;;
  paper-spot-tw.yml) tj=workers-alt.yml ;;
  *) tj="" ;;
esac
if [ -n "$tj" ]; then
  if gh workflow run "$tj" --ref main -R "$REPO"; then
    echo "test job started: $tj"
  else
    echo "test job not started: $tj"
  fi
fi
exit 0
