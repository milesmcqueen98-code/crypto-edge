#!/usr/bin/env bash
# Runs paper_next.sh against a stub gh. No network.
# Usage: bash bot/spot/deploy/paper_next_test.sh
set -u
# The old checks below run with one try and no wait: today's behaviour. (The new checks at the end set their own.)
export NEXT_TRIES=1 NEXT_WAIT=0
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"
cat > "$T/bin/gh" <<'S'
#!/usr/bin/env bash
echo "gh $*" >> "$LOG"
CNT=${LOG%/*}   # counters for the retry checks; API_FAIL_N, API_EMPTY_N, RUN_FAIL_N default to 0: never fail
if [ "$1" = "api" ]; then
  n=$(cat "$CNT/cnt_api" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$CNT/cnt_api"
  [ "$n" -le "${API_FAIL_N:-0}" ] && exit 1
  [ "$n" -le $(( ${API_FAIL_N:-0} + ${API_EMPTY_N:-0} )) ] && exit 0
  [ -n "$STARTED" ] && echo "$STARTED"; exit "${API_RC:-0}"
fi
if [ "$1" = "workflow" ]; then
  case "$3" in step-pairs.yml|workers-alt.yml) exit "${TEST_RC:-0}" ;; esac
  n=$(cat "$CNT/cnt_run" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$CNT/cnt_run"
  [ "$n" -le "${RUN_FAIL_N:-0}" ] && exit 1
  exit "${RUN_RC:-0}"
fi
exit 0
S
cat > "$T/bin/sleep" <<'S'
#!/usr/bin/env bash
echo "$*" >> "${LOG%/*}/sleeps"   # never really sleeps; the checks read what was asked for
exit 0
S
chmod +x "$T/bin/gh" "$T/bin/sleep"
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

# Retries. E holds the settings of one check (NEXT_TRIES, NEXT_WAIT, API_FAIL_N, API_EMPTY_N, RUN_FAIL_N); anything
# not in E is unset or "never fail". The stub sleep only records its argument.
G=2026-11-10T12:15:00Z
E=()
ncheck() {  # name workflow event started want_api want_dispatch want_testjob want_sleeps want_rc fragment... ("!x": absent)
  local name=$1 wf=$2 ev=$3 st=$4 wa=$5 wd=$6 wt=$7 ws=$8 wr=$9 out rc a d t s last frag ok=1
  shift 9
  local disp=${wf:-paper-spot.yml} kv
  : > "$T/log"; rm -f "$T/cnt_api" "$T/cnt_run" "$T/sleeps"
  out=$(unset NEXT_TRIES NEXT_WAIT WORKFLOW
        export LOG=$T/log EVENT=$ev STARTED=$st API_RC=0 RUN_RC=0 TEST_RC=0 RUN_ID=42 REPO=o/r NOW=$NOW0
        [ -n "$wf" ] && export WORKFLOW="$wf"
        for kv in ${E[*]}; do export "$kv"; done   # the settings of this check: NAME=value, no spaces in values
        PATH=$T/bin:$PATH bash "$HERE/paper_next.sh" 2>&1); rc=$?
  a=$(grep -c "^gh api " "$T/log")
  d=$(grep -c "gh workflow run $disp --ref main -R o/r" "$T/log")
  t=$(grep -c "gh workflow run \(step-pairs\|workers-alt\).yml --ref main -R o/r" "$T/log")
  s=$(paste -sd' ' "$T/sleeps" 2>/dev/null)
  last=$(grep "gh workflow run" "$T/log" | tail -1)
  { [ "$a" = "$wa" ] && [ "$d" = "$wd" ] && [ "$t" = "$wt" ] && [ "$s" = "$ws" ] && [ "$rc" = "$wr" ]; } || ok=0
  if [ "$wt" != 0 ] && [[ "$last" != *step-pairs.yml* && "$last" != *workers-alt.yml* ]]; then ok=0; fi  # test job comes last
  for frag; do
    case "$frag" in
      "!"*) [[ "$out" == *"${frag#!}"* ]] && ok=0 ;;
      *) [[ "$out" == *"$frag"* ]] || ok=0 ;;
    esac
  done
  if [ $ok = 1 ]; then echo "PASS  $name: api $a, dispatch $d, test job $t, sleeps \"$s\", rc $rc"
  else echo "FAIL  $name: api $a (want $wa), dispatch $d (want $wd), test job $t (want $wt), sleeps \"$s\" (want \"$ws\"), rc $rc (want $wr), \"$out\""; fail=1; fi
}
E=(NEXT_TRIES=3 NEXT_WAIT=0 API_FAIL_N=2)
ncheck "retry api: fails twice, then answers" "" schedule $G 3 1 0 "" 0 "after 345 min" "the start time was read at try 3"
E=(NEXT_TRIES=3 NEXT_WAIT=0 API_EMPTY_N=2)
ncheck "retry api: empty twice, then answers" "" schedule $G 3 1 0 "" 0 "after 345 min" "the start time was read at try 3"
E=(NEXT_TRIES=3 NEXT_WAIT=0 API_FAIL_N=3)
ncheck "retry api: fails 3 of 3: no dispatch" "" schedule $G 3 0 0 "" 0 "could not read" "!the start time was read"
E=(NEXT_TRIES=3 NEXT_WAIT=0 API_FAIL_N=1 RUN_FAIL_N=1)
ncheck "retry both: try 2 each" "" schedule $G 2 2 0 "" 0 "the start time was read at try 2" "the next run was started at try 2"
E=(NEXT_TRIES=3 NEXT_WAIT=0 RUN_FAIL_N=2)
ncheck "retry dispatch: fails twice, then works" "" schedule $G 1 3 0 "" 0 "next run started after 345 min" "the next run was started at try 3" "!the start time was read"
ncheck "retry dispatch r5: test job once, after it" paper-spot-r5.yml schedule $G 1 3 1 "" 0 "next run started" "the next run was started at try 3" "test job started: step-pairs.yml"
E=(NEXT_TRIES=3 NEXT_WAIT=0 RUN_FAIL_N=3)
ncheck "retry dispatch: fails 3 of 3: exit 1" "" schedule $G 1 3 0 "" 1 "backstop" "!next run started"
ncheck "retry dispatch r5: fails 3 of 3: no test job" paper-spot-r5.yml schedule $G 1 3 0 "" 1 "backstop"
# defaults: nothing fails, so one call each and no sleep (the stub sleep cannot hang anyway)
E=()
ncheck "defaults, all works: one api, one dispatch, no sleep" "" schedule $G 1 1 0 "" 0 "after 345 min" "!at try"
for v in abc 0 11 -1 2.5; do
  E=(NEXT_TRIES=$v NEXT_WAIT=0 API_FAIL_N=99)
  ncheck "NEXT_TRIES=$v counts as 5: api always fails" "" schedule $G 5 0 0 "" 0 "could not read"
done
E=(NEXT_WAIT=abc)
ncheck "NEXT_WAIT=abc, nothing fails: works, no sleep" "" schedule $G 1 1 0 "" 0 "after 345 min"
E=(NEXT_TRIES=3 NEXT_WAIT=abc API_FAIL_N=99)
ncheck "NEXT_WAIT=abc counts as 15: 2 sleeps for 3 tries" "" schedule $G 3 0 0 "15 15" 0 "could not read"
E=(NEXT_TRIES=3 NEXT_WAIT=7 RUN_FAIL_N=99)
ncheck "NEXT_WAIT=7: dispatch waits 7 between tries only" "" schedule $G 1 3 0 "7 7" 1 "backstop"
for v in 1 3 abc; do
  E=(NEXT_TRIES=$v NEXT_WAIT=0)
  ncheck "NEXT_TRIES=$v, under 30 min: no dispatch" "" schedule 2026-11-10T17:31:00Z 1 0 0 "" 0 "lasted 29 min"
  ncheck "NEXT_TRIES=$v, push event: no api, no dispatch" "" push $G 0 0 0 "" 0 "event push"
done
[ $fail = 0 ] && echo "PAPER NEXT TEST PASSED" || { echo "PAPER NEXT TEST FAILED"; exit 1; }
