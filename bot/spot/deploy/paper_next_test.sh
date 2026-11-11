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
if [ "$1" = "workflow" ]; then exit "${RUN_RC:-0}"; fi
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
bash -n "$HERE/paper_next.sh" && echo "PASS  bash -n paper_next.sh" || { echo "FAIL  bash -n"; fail=1; }
[ $fail = 0 ] && echo "PAPER NEXT TEST PASSED" || { echo "PAPER NEXT TEST FAILED"; exit 1; }
