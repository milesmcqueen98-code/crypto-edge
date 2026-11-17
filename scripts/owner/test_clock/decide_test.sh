#!/usr/bin/env bash
# Runs decide.sh on made-up runs. No network.
# Usage: bash scripts/owner/test_clock/decide_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
fail=0
n=0
check() {  # name, NAME, CONCLUSION, EVENT, STARTED, UPDATED, want (the exact line, or a prefix ending in ... )
  local name=$1 out rc
  n=$((n + 1))
  out=$(NAME=$2 CONCLUSION=$3 EVENT=$4 STARTED=$5 UPDATED=$6 bash "$HERE/decide.sh" 2>&1); rc=$?
  if [ "$rc" = 0 ] && { [ "$out" = "$7" ] || { [[ "$7" == *... ]] && [[ "$out" == "${7%...}"* ]]; }; } && [ "$(printf '%s\n' "$out" | wc -l)" = 1 ]; then
    echo "PASS  $name: \"$out\""
  else echo "FAIL  $name: rc $rc, \"$out\" (want \"$7\")"; fail=$((fail + 1)); fi
}
S=2026-11-17T12:00:00Z
check "fifth book, success, dispatch, 5h50m: step-pairs"   paper-spot-r5 success workflow_dispatch $S 2026-11-17T17:50:00Z "start step-pairs.yml"
check "sixth book, success, dispatch, 5h50m: workers-alt"  paper-spot-tw success workflow_dispatch $S 2026-11-17T17:50:00Z "start workers-alt.yml"
check "cancelled run: skip"                                paper-spot-tw cancelled workflow_dispatch $S 2026-11-17T17:50:00Z "skip: the run ended cancelled..."
check "failed run: skip"                                   paper-spot-r5 failure workflow_dispatch $S 2026-11-17T17:50:00Z "skip: the run ended failure..."
check "no conclusion: skip"                                paper-spot-r5 "" workflow_dispatch $S 2026-11-17T17:50:00Z "skip: the run ended with no conclusion..."
check "schedule event: skip"                               paper-spot-r5 success schedule $S 2026-11-17T17:50:00Z "skip: the run came from event schedule..."
check "29 min 59 s: skip (29 min)"                         paper-spot-tw success workflow_dispatch $S 2026-11-17T12:29:59Z "skip: the run lasted 29 min, less than 30"
check "exactly 30 min: start"                              paper-spot-tw success workflow_dispatch $S 2026-11-17T12:30:00Z "start workers-alt.yml"
check "29 min: skip"                                       paper-spot-r5 success workflow_dispatch $S 2026-11-17T12:29:00Z "skip: the run lasted 29 min, less than 30"
check "started time missing: skip"                         paper-spot-r5 success workflow_dispatch "" 2026-11-17T17:50:00Z "skip: a time is missing..."
check "updated time missing: skip"                         paper-spot-tw success workflow_dispatch $S "" "skip: a time is missing..."
check "garbage time: skip"                                 paper-spot-tw success workflow_dispatch not-a-time 2026-11-17T17:50:00Z "skip: unreadable time..."
check "updated before started: skip"                       paper-spot-tw success workflow_dispatch 2026-11-17T17:50:00Z $S "skip: the run lasted..."
check "unknown name: skip"                                 paper-spot success workflow_dispatch $S 2026-11-17T17:50:00Z "skip: workflow paper-spot is not one of the two books"
check "no name: skip"                                      "" success workflow_dispatch $S 2026-11-17T17:50:00Z "skip: workflow none is not one of the two books"
check "the fifth book's t18 twin is not one of them"       paper-spot-t18 success workflow_dispatch $S 2026-11-17T17:50:00Z "skip: workflow paper-spot-t18 is not..."
out=$(MIN_MINUTES=10 NAME=paper-spot-r5 CONCLUSION=success EVENT=workflow_dispatch STARTED=$S UPDATED=2026-11-17T12:10:00Z bash "$HERE/decide.sh")
n=$((n + 1)); if [ "$out" = "start step-pairs.yml" ]; then echo "PASS  MIN_MINUTES=10, 10 min: start"; else echo "FAIL  MIN_MINUTES: \"$out\""; fail=$((fail + 1)); fi
bash -n "$HERE/decide.sh" && { n=$((n + 1)); echo "PASS  bash -n decide.sh"; } || { n=$((n + 1)); echo "FAIL  bash -n"; fail=$((fail + 1)); }
echo "$n checks, $fail failed"
[ $fail = 0 ] && echo "TEST CLOCK TEST PASSED" || { echo "TEST CLOCK TEST FAILED"; exit 1; }
