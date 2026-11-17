#!/usr/bin/env bash
# Runs paper_next.sh against a stub gh. No network.
# Usage: bash bot/spot/deploy/paper_next_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"
cat > "$T/bin/gh" <<'S'
#!/usr/bin/env bash
echo "gh $*" >> "$LOG"
if [ "$1" = "api" ]; then [ -n "$STARTED" ] && echo "$STARTED"; exit "${API_RC:-0}"; fi
if [ "$1" = "workflow" ]; then
  case "$3" in step-pairs.yml|workers-alt.yml) exit "${TEST_RC:-0}" ;; esac
  exit "${RUN_RC:-0}"
fi
exit 0
S
chmod +x "$T/bin/gh"
NOW0=$(date -u -d "2026-11-10T18:00:00Z" +%s)
fail=0
unset WORKFLOW   # the checks below run with WORKFLOW unset, as paper-spot.yml does
check() {  # name event started api_rc run_rc want_dispatch want_rc fragment [workflow file wanted, default paper-spot.yml]
  local name=$1 out rc n want_wf=${9:-paper-spot.yml}
  export LOG=$T/log EVENT=$2 STARTED=$3 API_RC=$4 RUN_RC=$5 RUN_ID=42 REPO=o/r NOW=$NOW0; : > "$LOG"
  out=$(PATH=$T/bin:$PATH bash "$HERE/paper_next.sh" 2>&1); rc=$?
  n=$(grep -c "gh workflow run $want_wf --ref main -R o/r" "$LOG")
  if [ "$n" = "$6" ] && [ "$rc" = "$7" ] && [[ "$out" == *"$8"* ]]; then echo "PASS  $name: \"$out\""
  else echo "FAIL  $name: dispatches $n (want $6), rc $rc (want $7), \"$out\""; fail=1; fi
}
check "schedule, ran 5h45m: dispatch"          schedule          2026-11-10T12:15:00Z 0 0 1 0 "after 345 min"
check "manual, ran exactly 30 min: dispatch"   workflow_dispatch 2026-11-10T17:30:00Z 0 0 1 0 "after 30 min"
check "schedule, ran 29 min: no dispatch"      schedule          2026-11-10T17:31:00Z 0 0 0 0 "lasted 29 min"
check "push event: no dispatch"                push              2026-11-10T12:15:00Z 0 0 0 0 "event push"
check "start time unreadable: no dispatch"     schedule          ""                   1 0 0 0 "could not read"
check "start time garbage: no dispatch"        schedule          not-a-time           0 0 0 0 "unreadable"
check "dispatch refused: exit 1"               schedule          2026-11-10T12:15:00Z 0 1 1 1 "backstop"
# WORKFLOW: unset starts paper-spot.yml (checks above, and this one); set, it starts the file it names and only that
unset WORKFLOW
check "WORKFLOW unset: dispatches paper-spot.yml"  schedule 2026-11-10T12:15:00Z 0 0 1 0 "after 345 min" paper-spot.yml
export WORKFLOW=paper-spot-t18.yml
check "WORKFLOW=paper-spot-t18.yml: dispatches it" schedule 2026-11-10T12:15:00Z 0 0 1 0 "after 345 min" paper-spot-t18.yml
check "WORKFLOW=paper-spot-t18.yml: not paper-spot.yml" schedule 2026-11-10T12:15:00Z 0 0 0 0 "after 345 min" paper-spot.yml
unset WORKFLOW
# Test jobs: after a good hand-over, r5 also starts step-pairs.yml and tw also starts workers-alt.yml, in that order
tjcheck() {  # name workflow event started run_rc test_rc want_rc want_main want_tj want_text order_ok
  local name=$1 out rc m t first
  export LOG=$T/log WORKFLOW=$2 EVENT=$3 STARTED=$4 API_RC=0 RUN_RC=$5 TEST_RC=$6 RUN_ID=42 REPO=o/r NOW=$NOW0; : > "$LOG"
  out=$(PATH=$T/bin:$PATH bash "$HERE/paper_next.sh" 2>&1); rc=$?
  m=$(grep -c "gh workflow run $2 --ref main -R o/r" "$LOG")
  t=$(grep -c "gh workflow run \(step-pairs\|workers-alt\).yml --ref main -R o/r" "$LOG")
  first=$(grep "gh workflow run" "$LOG" | head -1)
  if [ "$m" = "$8" ] && [ "$t" = "$9" ] && [ "$rc" = "$7" ] && [[ "$out" == *"${10}"* ]] \
     && { [ "$9" = 0 ] || [ "$first" = "gh workflow run $2 --ref main -R o/r" ]; }; then echo "PASS  $name: \"$out\""
  else echo "FAIL  $name: main $m (want $8), test job $t (want $9), rc $rc (want $7), \"$out\""; fail=1; fi
  unset WORKFLOW TEST_RC
}
G=2026-11-10T12:15:00Z
tjcheck "r5: next run then step-pairs"        paper-spot-r5.yml schedule $G 0 0 0 1 1 "test job started: step-pairs.yml"
tjcheck "r5: both lines printed"              paper-spot-r5.yml schedule $G 0 0 0 1 1 "hand-over: next run started after 345 min"
tjcheck "tw: next run then workers-alt"       paper-spot-tw.yml workflow_dispatch $G 0 0 0 1 1 "test job started: workers-alt.yml"
tjcheck "tw: both lines printed"              paper-spot-tw.yml schedule $G 0 0 0 1 1 "hand-over: next run started after 345 min"
tjcheck "paper-spot.yml: no test job"         paper-spot.yml schedule $G 0 0 0 1 0 "after 345 min"
tjcheck "paper-spot-t18.yml: no test job"     paper-spot-t18.yml schedule $G 0 0 0 1 0 "after 345 min"
tjcheck "r5: test job refused: exit 0"        paper-spot-r5.yml schedule $G 0 1 0 1 1 "test job not started: step-pairs.yml"
tjcheck "tw: test job refused: exit 0"        paper-spot-tw.yml schedule $G 0 1 0 1 1 "test job not started: workers-alt.yml"
tjcheck "r5: next run refused: exit 1, no test job" paper-spot-r5.yml schedule $G 1 0 1 1 0 "backstop"
tjcheck "tw: next run refused: exit 1, no test job" paper-spot-tw.yml schedule $G 1 0 1 1 0 "backstop"
tjcheck "r5: under 30 min: nothing"           paper-spot-r5.yml schedule 2026-11-10T17:31:00Z 0 0 0 0 0 "lasted 29 min"
tjcheck "tw: under 30 min: nothing"           paper-spot-tw.yml schedule 2026-11-10T17:31:00Z 0 0 0 0 0 "lasted 29 min"
tjcheck "r5: push event: nothing"             paper-spot-r5.yml push $G 0 0 0 0 0 "event push"
tjcheck "tw: push event: nothing"             paper-spot-tw.yml push $G 0 0 0 0 0 "event push"
tjcheck "r5: start time garbage: nothing"     paper-spot-r5.yml schedule not-a-time 0 0 0 0 0 "unreadable"
tjcheck "tw: start time unreadable: nothing"  paper-spot-tw.yml schedule "" 0 0 0 0 0 "could not read"
unset WORKFLOW
bash -n "$HERE/paper_next.sh" && echo "PASS  bash -n paper_next.sh" || { echo "FAIL  bash -n"; fail=1; }
[ $fail = 0 ] && echo "PAPER NEXT TEST PASSED" || { echo "PAPER NEXT TEST FAILED"; exit 1; }
