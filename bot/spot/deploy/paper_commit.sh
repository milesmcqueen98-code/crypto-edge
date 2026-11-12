#!/usr/bin/env bash
# Commit step for the paper-log workflows (.github/workflows/paper-spot.yml, owner-status.yml): stage the given
# paths, commit, then pull --rebase and push with retries. Two jobs often finish within seconds of each other, so a
# push can be rejected after a clean pull (Nov 11: "cannot lock ref 'refs/heads/main'"); every failure is retried,
# and if all attempts fail the commit goes to a rescue branch so the log is not lost.
# The caller sets git user.name and user.email. Behaves the same under "bash -e" and plain bash: every command's
# result is checked explicitly and errexit is switched off below.
# Retries: one attempt (pull --rebase, then push) more than there are waits; after a failed attempt the script waits
# the next value of PAPER_COMMIT_WAITS, none after the last. Default "5 10 15 20 25 30 45 60 60 60": 11 attempts over
# 330 s of waiting. It is long because on Nov 11 a six-hour log was lost to a token problem ("could not read Username")
# that outlasted 76 seconds of retries. The paper jobs have about 8.5 minutes between the end of the paper run and
# their time limit; keep the total within that (paper_commit_test.sh checks it is 330).
# The rescue push has its own retries: one try more than the waits in PAPER_COMMIT_RESCUE_WAITS (default "10 20").
# Every git call to the remote runs under a time limit of PAPER_COMMIT_CALL_LIMIT seconds (default 45; a call cut off
# counts as a failed attempt, "no answer within N s"), and the main attempts stop at PAPER_COMMIT_DEADLINE seconds
# after the script's start (default 240; no attempt or wait starts past it, and a call near it gets only the time
# left), then the script goes to the rescue push. Every other failure line ends with git's own error line.
# The deadline ends the main attempts before the schedule is used up: with quick failures, after about 9 of the 11.
# Worst case with the defaults: about 244 s of main attempts (240 s and a capped last call), about 11 s for the last
# abort, then up to three rescue tries of at most 46 s (45 s and 1 s of kill grace) with 10 s and 20 s between them,
# about 168 s: about 425 s in all, against about 510 s between the end of the paper run (minute ~349.5) and the
# 358-minute job limit. The paper jobs reach the limit only if the script starts after about minute 350.9; if it did, GitHub would kill the job at 358 minutes, the commit would never leave the runner and no ::error:: line
# would be printed, so the log would be lost.
# Env: PAPER_COMMIT_BRANCH (default main), PAPER_COMMIT_WAITS and PAPER_COMMIT_RESCUE_WAITS (space-separated
#      seconds, see above), PAPER_COMMIT_CALL_LIMIT and PAPER_COMMIT_DEADLINE (seconds, see above), GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT and GITHUB_JOB (name the rescue branch,
#      paper-log-rescue/<run id>-<run attempt>-<job>, defaults local, 1 and job; the attempt keeps a re-run of the
#      same job from colliding with the branch an earlier attempt left).
# Usage: bash bot/spot/deploy/paper_commit.sh "<commit message>" <path> [<path> ...]
#        (test: bash bot/spot/deploy/paper_commit_test.sh)
# The whole body is one { } block: bash parses it fully before running, so a pull that updates this file on disk
# mid-run cannot change what runs.
{
set +e
set -u
t0=$SECONDS
export GIT_TERMINAL_PROMPT=0   # never wait for a password prompt
if [ $# -lt 2 ]; then echo "::error::usage: paper_commit.sh \"<commit message>\" <path> [<path> ...]"; exit 2; fi
msg=$1; shift
branch=${PAPER_COMMIT_BRANCH:-main}
default_waits="5 10 15 20 25 30 45 60 60 60"
default_rescue_waits="10 20"
waits=${PAPER_COMMIT_WAITS:-$default_waits}
rescue_waits=${PAPER_COMMIT_RESCUE_WAITS:-$default_rescue_waits}
count_waits() {  # prints the number of waits in $1, or nothing when one of them is not a whole number of seconds
  local n=0 rest=$1 w
  while read -r w rest <<< "$rest" && [ -n "$w" ]; do
    case "$w" in *[!0-9]*) return 0 ;; esac
    n=$((n + 1))
  done
  echo "$n"
}
n=$(count_waits "$waits")
if [ -z "$n" ]; then echo "::warning::paper_commit: PAPER_COMMIT_WAITS \"$waits\" unreadable, using the default"; waits=$default_waits; n=$(count_waits "$waits"); fi
attempts=$((n + 1))
n=$(count_waits "$rescue_waits")
if [ -z "$n" ]; then echo "::warning::paper_commit: PAPER_COMMIT_RESCUE_WAITS \"$rescue_waits\" unreadable, using the default"; rescue_waits=$default_rescue_waits; n=$(count_waits "$rescue_waits"); fi
rescue_tries=$((n + 1))
default_call_limit=45
default_deadline=240
call_limit=${PAPER_COMMIT_CALL_LIMIT:-$default_call_limit}
deadline=${PAPER_COMMIT_DEADLINE:-$default_deadline}
case "$call_limit" in ''|*[!0-9]*|0) echo "::warning::paper_commit: PAPER_COMMIT_CALL_LIMIT \"$call_limit\" unreadable, using the default"; call_limit=$default_call_limit ;; esac
case "$deadline" in ''|*[!0-9]*) echo "::warning::paper_commit: PAPER_COMMIT_DEADLINE \"$deadline\" unreadable, using the default"; deadline=$default_deadline ;; esac
rescue="paper-log-rescue/${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}-${GITHUB_JOB:-job}"

while [ $# -gt 0 ]; do
  if [ -e "$1" ]; then
    git add -- "$1" || echo "::warning::paper_commit: git add $1 failed"
  else
    echo "paper_commit: $1 does not exist, skipped"
  fi
  shift
done
if git diff --cached --quiet; then echo "paper_commit: nothing to commit"; exit 0; fi
if ! git commit -q -m "$msg"; then echo "::error::paper_commit: git commit failed"; exit 1; fi

git_error() {  # git's own error line from the output in $1: a ref rejection, else the first fatal:, else the first
  local l   # error:, else the last non-empty line that is not a hint
  l=$(printf '%s\n' "$1" | grep -m1 -E '^ *! \[') \
    || l=$(printf '%s\n' "$1" | grep -m1 '^fatal:') \
    || l=$(printf '%s\n' "$1" | grep -m1 '^error:') \
    || l=$(printf '%s\n' "$1" | grep -v -e '^hint:' -e '^[[:space:]]*$' | tail -n 1)
  l=$(printf '%s' "$l" | sed 's/^[[:space:]]*//')
  echo "${l:-no output}"
}

left() { echo $((deadline - (SECONDS - t0))); }   # seconds until the deadline of the main attempts
limit_now() {  # the call limit, cut to the time left before the deadline (at least 1 s)
  local l; l=$(left)
  if [ "$l" -lt "$call_limit" ]; then [ "$l" -lt 1 ] && l=1; echo "$l"; else echo "$call_limit"; fi
}
why() {  # why a remote call failed: rc $1, output $2, limit $3
  if [ "$1" = 124 ] || [ "$1" = 137 ]; then echo "no answer within $3 s"; else git_error "$2"; fi
}
clear_locks() {  # after a call was cut off: remove the lock files a killed git can leave (no other git runs here)
  local f r
  r=$(git symbolic-ref -q HEAD)
  for f in index.lock HEAD.lock ORIG_HEAD.lock packed-refs.lock ${r:+$r.lock}; do
    rm -f "$(git rev-parse --git-path "$f" 2>/dev/null)"
  done
  return 0
}
in_rebase() {
  local m a
  m=$(git rev-parse --git-path rebase-merge 2>/dev/null)
  a=$(git rev-parse --git-path rebase-apply 2>/dev/null)
  { [ -n "$m" ] && [ -d "$m" ]; } || { [ -n "$a" ] && [ -d "$a" ]; }
}
mine=$(git rev-parse HEAD)            # this run's commit
head_ref=$(git symbolic-ref -q HEAD)  # the branch it is on (empty when detached)
abort_rebase() {  # only when a rebase is in progress; never fails. A rebase whose state a cut-off pull left broken
  in_rebase || return 0                # is dropped and the branch put back on this run's commit.
  timeout -k 1 10 git rebase --abort >/dev/null 2>&1
  in_rebase || return 0
  clear_locks
  git rebase --quit >/dev/null 2>&1
  [ -n "$head_ref" ] && git symbolic-ref HEAD "$head_ref"
  if ! in_rebase && git reset -q --hard "$mine"; then
    echo "paper_commit: git rebase --abort failed; dropped the rebase and put $head_ref back on this run's commit"
  else
    echo "paper_commit: git rebase --abort failed and the rebase could not be dropped"
  fi
  return 0
}

i=1; made=0; rest=$waits
while [ "$i" -le "$attempts" ]; do
  if [ "$(left)" -le 0 ]; then
    echo "paper_commit: deadline of $deadline s reached after $made attempts; going to the rescue push"; break
  fi
  made=$i
  # -X theirs: on a conflict in the paper logs this run's (newer) version wins instead of the push failing
  lim=$(limit_now); out=$(timeout -k 1 "$lim" git pull -q --rebase -X theirs origin "$branch" 2>&1); rc=$?
  if [ $rc = 0 ]; then
    lim=$(limit_now); out=$(timeout -k 1 "$lim" git push -q origin "HEAD:refs/heads/$branch" 2>&1); rc=$?
    if [ $rc = 0 ]; then
      echo "paper_commit: attempt $i/$attempts: pushed to $branch"
      exit 0
    fi
    echo "paper_commit: attempt $i/$attempts: git push failed: $(why $rc "$out" "$lim")"
  else
    echo "paper_commit: attempt $i/$attempts: git pull --rebase failed: $(why $rc "$out" "$lim")"
  fi
  if [ $rc = 124 ] || [ $rc = 137 ]; then clear_locks; fi
  abort_rebase
  if [ "$i" -lt "$attempts" ]; then
    read -r w rest <<< "$rest"; w=${w:-0}
    if [ $(( $(left) - w )) -le 0 ]; then
      echo "paper_commit: deadline of $deadline s reached after $made attempts (next wait $w s); going to the rescue push"
      break
    fi
    sleep "$w"
  fi
  i=$((i + 1))
done

abort_rebase
i=1; rest=$rescue_waits
while [ "$i" -le "$rescue_tries" ]; do
  out=$(timeout -k 1 "$call_limit" git push -q origin "HEAD:refs/heads/$rescue" 2>&1); rc=$?
  if [ $rc = 0 ]; then
    echo "::error::paper_commit: could not push to $branch after $made attempts; the commit is on branch $rescue"
    exit 1
  fi
  echo "paper_commit: rescue try $i/$rescue_tries: push to $rescue failed: $(why $rc "$out" "$call_limit")"
  if [ $rc = 124 ] || [ $rc = 137 ]; then clear_locks; fi
  read -r w rest <<< "$rest"
  if [ "$i" -lt "$rescue_tries" ]; then sleep "${w:-0}"; fi
  i=$((i + 1))
done
echo "::error::paper_commit: could not push to $branch after $made attempts, and the push to rescue branch $rescue failed too ($rescue_tries tries); the log is only on this runner"
exit 1
}
