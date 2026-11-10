#!/usr/bin/env bash
# Hand-over for .github/workflows/paper-spot.yml (job "next"): start the next run of the workflow on main, so the
# paper books do not wait for GitHub's often-dropped schedule. It starts one only when:
#   - this run came from the schedule or a manual dispatch (not from anything else), and
#   - this run has lasted at least MIN_MINUTES (default 30), so a run that fails at start cannot loop.
# The cron line stays as the backstop. A run started now waits in the workflow's concurrency group until this one ends.
# Env: EVENT, RUN_ID, REPO (owner/name), GH_TOKEN for gh; MIN_MINUTES and NOW (epoch seconds) are for tests.
# Usage: bash bot/spot/deploy/paper_next.sh   (test: bash bot/spot/deploy/paper_next_test.sh)
set -u
min=${MIN_MINUTES:-30}
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
if gh workflow run paper-spot.yml --ref main -R "$REPO"; then
  echo "hand-over: next run started after $el min"
else
  echo "hand-over failed: the schedule is the backstop"; exit 1
fi
