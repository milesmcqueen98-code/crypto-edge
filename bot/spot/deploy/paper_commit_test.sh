#!/usr/bin/env bash
# Runs paper_commit.sh against temporary bare repositories and clones. No network.
# Every case runs twice, once under "bash" and once under "bash -e" (the shell GitHub Actions uses for run steps),
# and the faulty loop the script replaces is run against the same scenarios to show the test detects its fault.
# Usage: bash bot/spot/deploy/paper_commit_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT=$HERE/paper_commit.sh
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export GIT_CONFIG_GLOBAL=$T/gitconfig GIT_CONFIG_NOSYSTEM=1 PAPER_COMMIT_WAIT=0
git config --file "$GIT_CONFIG_GLOBAL" init.defaultBranch main
git config --file "$GIT_CONFIG_GLOBAL" advice.detachedHead false
unset GITHUB_RUN_ID GITHUB_RUN_ATTEMPT GITHUB_JOB PAPER_COMMIT_BRANCH

# THE FAULTY LOOP (the old commit step of paper-spot.yml and owner-status.yml, kept here only to prove the test
# catches its fault): after a clean pull and a rejected push, "git rebase --abort" exits 128 because no rebase is
# in progress, and under "bash -e" that ends the step with no retry.
OLD_LOOP='for i in 1 2 3 4 5; do git pull --rebase -X theirs origin main && git push && break; git rebase --abort 2>/dev/null; sleep $((i*5)); done'

fail=0; n=0
sig=""  # exit codes of the cases in order, compared between the two shell modes (case 10)
pass() { echo "PASS  $1"; sig="$sig ${rc:-}"; }
bad() { echo "FAIL  $1"; fail=1; sig="$sig ${rc:-}"; }

# fresh world: $W/remote.git (bare, main holds paper_spot/log.jsonl = "base"), clones $W/a and $W/b
new_world() {
  n=$((n + 1)); W=$T/w$n; mkdir -p "$W"
  git init -q --bare "$W/remote.git"
  git clone -q "$W/remote.git" "$W/seed" 2>/dev/null
  mkdir -p "$W/seed/paper_spot"; echo base > "$W/seed/paper_spot/log.jsonl"
  git -C "$W/seed" -c user.name=seed -c user.email=seed.local add -A
  git -C "$W/seed" -c user.name=seed -c user.email=seed.local commit -q -m seed
  git -C "$W/seed" push -q origin HEAD:main
  for c in a b; do
    git clone -q "$W/remote.git" "$W/$c"
    git -C "$W/$c" config user.name "crypto-edge-bot"
    git -C "$W/$c" config user.email "bot.users.noreply.local"
  done
}
remote_has() { git --git-dir="$W/remote.git" log --format=%s "${2:-main}" -- 2>/dev/null | grep -qxF "$1"; }
remote_file() { git --git-dir="$W/remote.git" show "main:$1" 2>/dev/null; }
remote_tip() { git --git-dir="$W/remote.git" rev-parse main; }
# run the script in clone $1 under shell mode $2 ("bash" or "bash -e"); sets out and rc
run() {
  local dir=$1 mode=$2; shift 2
  local cmd q
  cmd="$mode $(printf %q "$SCRIPT")"
  while [ $# -gt 0 ]; do q=$(printf %q "$1"); cmd="$cmd $q"; shift; done
  out=$(cd "$dir" && eval "$cmd" 2>&1); rc=$?
}
# hooks in the bare repository
hook_reject_once() {  # rejects the next push to the remote, once
  : > "$W/reject-once"
  cat > "$W/remote.git/hooks/pre-receive" <<H
#!/bin/sh
if [ -f "$W/reject-once" ]; then rm -f "$W/reject-once"; echo "test hook: push rejected once" >&2; exit 1; fi
exit 0
H
  chmod +x "$W/remote.git/hooks/pre-receive"
}
hook_reject_main() {  # rejects every push to main; with "all", rejects every push
  cat > "$W/remote.git/hooks/pre-receive" <<H
#!/bin/sh
while read old new ref; do
  if [ "${1:-main}" = all ] || [ "\$ref" = refs/heads/main ]; then echo "test hook: push to \$ref rejected" >&2; exit 1; fi
done
exit 0
H
  chmod +x "$W/remote.git/hooks/pre-receive"
}
hook_race() {  # during the next push, clone a (the other job) runs the script and pushes first: a real ref race
  : > "$W/race-once"
  cat > "$W/remote.git/hooks/pre-receive" <<H
#!/bin/bash
if [ -f "$W/race-once" ]; then
  rm -f "$W/race-once"
  ( for v in \$(env | sed -n 's/^\(GIT_[A-Z_]*\)=.*/\1/p'); do unset "\$v"; done
    export GIT_CONFIG_GLOBAL="$GIT_CONFIG_GLOBAL" GIT_CONFIG_NOSYSTEM=1
    cd "$W/a" && $1 "$SCRIPT" "job A log" paper_spot_tb > "$W/a.out" 2>&1; echo \$? > "$W/a.rc" ) </dev/null >/dev/null 2>&1
fi
exit 0
H
  chmod +x "$W/remote.git/hooks/pre-receive"
}

for MODE in "bash" "bash -e"; do
  tag="[$MODE]"; sig=""

  # 1. plain success
  new_world
  echo one >> "$W/b/paper_spot/log.jsonl"
  run "$W/b" "$MODE" "log 1" paper_spot
  if [ $rc = 0 ] && remote_has "log 1" && [[ "$out" == *"attempt 1/6: pushed to main"* ]]; then pass "$tag 1 plain success"
  else bad "$tag 1 plain success: rc $rc, \"$out\""; fi

  # 2. the remote moved ahead: another clone pushed a different folder first
  new_world
  mkdir -p "$W/a/paper_spot_tb"; echo tb > "$W/a/paper_spot_tb/log.jsonl"
  git -C "$W/a" add -A; git -C "$W/a" commit -q -m "other job"; git -C "$W/a" push -q origin HEAD:main
  echo two >> "$W/b/paper_spot/log.jsonl"
  run "$W/b" "$MODE" "log 2" paper_spot
  if [ $rc = 0 ] && remote_has "log 2" && remote_has "other job" && [ "$(remote_file paper_spot_tb/log.jsonl)" = tb ]
  then pass "$tag 2 remote ahead: rebased and pushed, both commits on main"
  else bad "$tag 2 remote ahead: rc $rc, \"$out\""; fi

  # 3. THE REGRESSION CASE: pull succeeds, the first push is rejected, the second push succeeds
  new_world; hook_reject_once
  echo three >> "$W/b/paper_spot/log.jsonl"
  run "$W/b" "$MODE" "log 3" paper_spot
  if [ $rc = 0 ] && remote_has "log 3" && [[ "$out" == *"attempt 1/6: git push failed"* ]] && [[ "$out" == *"attempt 2/6: pushed to main"* ]]
  then pass "$tag 3 push rejected once after a clean pull: retried, commit on main"
  else bad "$tag 3 push rejected once: rc $rc, \"$out\""; fi

  # 5. conflict in the same log file: this run's version wins
  new_world
  echo "remote version" > "$W/a/paper_spot/log.jsonl"
  git -C "$W/a" commit -q -am "remote edit"; git -C "$W/a" push -q origin HEAD:main
  echo "this run" > "$W/b/paper_spot/log.jsonl"
  run "$W/b" "$MODE" "log 5" paper_spot
  if [ $rc = 0 ] && remote_has "log 5" && [ "$(remote_file paper_spot/log.jsonl)" = "this run" ]
  then pass "$tag 5 conflict in the log: this run's version pushed"
  else bad "$tag 5 conflict: rc $rc, file \"$(remote_file paper_spot/log.jsonl)\", \"$out\""; fi

  # 6. every push to main rejected: exit 1, ::error::, commit on the rescue branch
  new_world; hook_reject_main
  echo six >> "$W/b/paper_spot/log.jsonl"
  out=$(cd "$W/b" && GITHUB_RUN_ID=77 GITHUB_RUN_ATTEMPT=2 GITHUB_JOB=paper $MODE "$SCRIPT" "log 6" paper_spot 2>&1); rc=$?
  tries=$(printf '%s\n' "$out" | grep -c "git push failed")
  if [ $rc = 1 ] && [ "$tries" = 6 ] && ! remote_has "log 6" && remote_has "log 6" paper-log-rescue/77-2-paper \
     && printf '%s\n' "$out" | grep -q "^::error::.*paper-log-rescue/77-2-paper"
  then pass "$tag 6 every push rejected: 6 attempts, exit 1, ::error::, commit on paper-log-rescue/77-2-paper"
  else bad "$tag 6 every push rejected: rc $rc, tries $tries, \"$out\""; fi

  # 6b. the rescue push fails too: exit 1 and the error line says so
  new_world; hook_reject_main all
  echo six >> "$W/b/paper_spot/log.jsonl"
  run "$W/b" "$MODE" "log 6b" paper_spot
  if [ $rc = 1 ] && printf '%s\n' "$out" | grep -q "^::error::.*paper-log-rescue/local-1-job failed too"
  then pass "$tag 6b rescue push rejected too: exit 1, ::error:: says so"
  else bad "$tag 6b rescue rejected: rc $rc, \"$out\""; fi

  # 6c. two attempts of the same run and job (a re-run) get different rescue branches, and both logs are kept
  new_world; hook_reject_main
  echo six-c1 >> "$W/b/paper_spot/log.jsonl"
  out1=$(cd "$W/b" && GITHUB_RUN_ID=88 GITHUB_RUN_ATTEMPT=1 GITHUB_JOB=paper $MODE "$SCRIPT" "log 6c attempt 1" paper_spot 2>&1); rc1=$?
  echo six-c2 >> "$W/a/paper_spot/log.jsonl"
  out=$(cd "$W/a" && GITHUB_RUN_ID=88 GITHUB_RUN_ATTEMPT=2 GITHUB_JOB=paper $MODE "$SCRIPT" "log 6c attempt 2" paper_spot 2>&1); rc=$?
  if [ $rc1 = 1 ] && [ $rc = 1 ] && remote_has "log 6c attempt 1" paper-log-rescue/88-1-paper \
     && remote_has "log 6c attempt 2" paper-log-rescue/88-2-paper && [[ "$out" != *"failed too"* ]]
  then pass "$tag 6c re-run of the same job: paper-log-rescue/88-1-paper and 88-2-paper, both logs kept"
  else bad "$tag 6c re-run: rc $rc1 and $rc, \"$out1\", \"$out\""; fi

  # 7. nothing to commit: exit 0, remote unchanged
  new_world; before=$(remote_tip)
  run "$W/b" "$MODE" "log 7" paper_spot
  if [ $rc = 0 ] && [ "$(remote_tip)" = "$before" ] && [ "$(git -C "$W/b" rev-list --count HEAD)" = 1 ]
  then pass "$tag 7 nothing to commit: exit 0, remote unchanged"
  else bad "$tag 7 nothing to commit: rc $rc, \"$out\""; fi

  # 8. a missing path is skipped, the existing one committed
  new_world
  echo eight >> "$W/b/paper_spot/log.jsonl"
  run "$W/b" "$MODE" "log 8" paper_spot paper_spot_w2
  if [ $rc = 0 ] && remote_has "log 8" && [ "$(remote_file paper_spot/log.jsonl | tail -n 1)" = eight ] && [[ "$out" == *"paper_spot_w2 does not exist, skipped"* ]]
  then pass "$tag 8 missing path skipped, existing path committed"
  else bad "$tag 8 missing path: rc $rc, \"$out\""; fi

  # 9. two jobs racing: both commit and pull, job A pushes while job B's push is in flight
  new_world; hook_race "$MODE"
  mkdir -p "$W/a/paper_spot_tb"; echo tb > "$W/a/paper_spot_tb/log.jsonl"
  echo nine >> "$W/b/paper_spot/log.jsonl"
  run "$W/b" "$MODE" "job B log" paper_spot
  arc=$(cat "$W/a.rc" 2>/dev/null)
  if [ $rc = 0 ] && [ "$arc" = 0 ] && remote_has "job A log" && remote_has "job B log" \
     && [ "$(remote_file paper_spot_tb/log.jsonl)" = tb ] && [ "$(remote_file paper_spot/log.jsonl | tail -n 1)" = nine ] \
     && [[ "$out" == *"attempt 1/6: git push failed"* ]]
  then pass "$tag 9 two jobs racing: both folders on main, both exit 0 ($(printf '%s\n' "$out" | grep -m1 -o "cannot lock ref[^:]*"))"
  else bad "$tag 9 two jobs racing: B rc $rc, A rc $arc, \"$out\", A: \"$(cat "$W/a.out" 2>/dev/null)\""; fi
  if [ "$MODE" = bash ]; then sig_plain=$sig; else sig_e=$sig; fi
done
# 10. same results under bash -e and plain bash
if [ "$sig_plain" = "$sig_e" ]; then rc=0; pass "10 same exit codes under bash and bash -e:$sig_e"
else rc=1; bad "10 exit codes differ: bash$sig_plain, bash -e$sig_e"; fi

# 4. the faulty loop against the regression scenario of case 3, under bash -e: it must fail
new_world; hook_reject_once
echo four >> "$W/b/paper_spot/log.jsonl"
git -C "$W/b" commit -q -am "log 4"
out=$(cd "$W/b" && bash -e -c "$OLD_LOOP" 2>&1); rc=$?
if [ $rc != 0 ] && ! remote_has "log 4"; then pass "4 faulty loop, push rejected once, bash -e: exits $rc, commit not on main (fault detected)"
else bad "4 faulty loop was expected to fail: rc $rc, \"$out\""; fi

# 4b. the faulty loop against the real ref race of case 9 (the Nov 11 failure), under bash -e: it must fail
new_world; hook_race bash
mkdir -p "$W/a/paper_spot_tb"; echo tb > "$W/a/paper_spot_tb/log.jsonl"
echo four >> "$W/b/paper_spot/log.jsonl"
git -C "$W/b" commit -q -am "log 4b"
out=$(cd "$W/b" && bash -e -c "$OLD_LOOP" 2>&1); rc=$?
if [ $rc != 0 ] && ! remote_has "log 4b" && [[ "$out" == *"cannot lock ref"* ]]
then pass "4b faulty loop, ref race, bash -e: exits $rc, commit not on main ($(printf '%s\n' "$out" | grep -m1 -o "cannot lock ref[^:]*"))"
else bad "4b faulty loop was expected to fail on the ref race: rc $rc, \"$out\""; fi

bash -n "$SCRIPT" && pass "bash -n paper_commit.sh" || bad "bash -n paper_commit.sh"
[ $fail = 0 ] && echo "PAPER COMMIT TEST PASSED" || { echo "PAPER COMMIT TEST FAILED"; exit 1; }
