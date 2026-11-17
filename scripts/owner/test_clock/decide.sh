#!/usr/bin/env bash
# Decision for .github/workflows/test-clock.yml: after a run of the fifth book (paper-spot-r5) or the sixth book
# (paper-spot-tw) has completed, which test job, if any, to start. Prints exactly one line, and exits 0 always:
#   start <workflow file>     the job to start (step-pairs.yml for paper-spot-r5, workers-alt.yml for paper-spot-tw)
#   skip: <reason>            nothing to start
# It starts one only when the completed run
#   - is one of the two books named above,
#   - ended with the conclusion success,
#   - was started by workflow_dispatch (the real paper runs are all started by dispatch; the scheduled backstop runs end
#     cancelled), and
#   - lasted at least MIN_MINUTES (default 30), from STARTED to UPDATED, so a run that fails at start cannot start a job.
# If either time is missing or unreadable, nothing is started. No network.
# Env: NAME (the completed workflow's name), CONCLUSION, EVENT, STARTED (run_started_at), UPDATED (updated_at), both
# ISO 8601 UTC times from the workflow_run payload; MIN_MINUTES is for tests.
# Usage: bash scripts/owner/test_clock/decide.sh   (test: bash scripts/owner/test_clock/decide_test.sh)
set -u
min=${MIN_MINUTES:-30}
case "${NAME:-}" in
  paper-spot-r5) wf=step-pairs.yml ;;
  paper-spot-tw) wf=workers-alt.yml ;;
  *) echo "skip: workflow ${NAME:-none} is not one of the two books"; exit 0 ;;
esac
if [ "${CONCLUSION:-}" != "success" ]; then echo "skip: the run ended ${CONCLUSION:-with no conclusion}, not success"; exit 0; fi
if [ "${EVENT:-}" != "workflow_dispatch" ]; then echo "skip: the run came from event ${EVENT:-none}, not workflow_dispatch"; exit 0; fi
if [ -z "${STARTED:-}" ] || [ -z "${UPDATED:-}" ]; then echo "skip: a time is missing (started '${STARTED:-}', updated '${UPDATED:-}')"; exit 0; fi
s=$(date -u -d "$STARTED" +%s 2>/dev/null) || s=""
u=$(date -u -d "$UPDATED" +%s 2>/dev/null) || u=""
if [ -z "$s" ] || [ -z "$u" ]; then echo "skip: unreadable time (started '$STARTED', updated '$UPDATED')"; exit 0; fi
el=$(( (u - s) / 60 ))
if [ "$el" -lt "$min" ]; then echo "skip: the run lasted $el min, less than $min"; exit 0; fi
echo "start $wf"
exit 0
