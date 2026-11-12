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
# The rescue push has its own retries: one try more than the waits in PAPER_COMMIT_RESCUE_WAITS (default "15 30").
# Every failure line ends with git's own error line, so the job log names the cause.
# Env: PAPER_COMMIT_BRANCH (default main), PAPER_COMMIT_WAITS and PAPER_COMMIT_RESCUE_WAITS (space-separated
#      seconds, see above), GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT and GITHUB_JOB (name the rescue branch,
#      paper-log-rescue/<run id>-<run attempt>-<job>, defaults local, 1 and job; the attempt keeps a re-run of the
#      same job from colliding with the branch an earlier attempt left).
# Usage: bash bot/spot/deploy/paper_commit.sh "<commit message>" <path> [<path> ...]
#        (test: bash bot/spot/deploy/paper_commit_test.sh)
# The whole body is one { } block: bash parses it fully before running, so a pull that updates this file on disk
# mid-run cannot change what runs.
{
set +e
set -u
if [ $# -lt 2 ]; then echo "::error::usage: paper_commit.sh \"<commit message>\" <path> [<path> ...]"; exit 2; fi
msg=$1; shift
branch=${PAPER_COMMIT_BRANCH:-main}
default_waits="5 10 15 20 25 30 45 60 60 60"
default_rescue_waits="15 30"
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

abort_rebase() {  # only when a rebase is in progress; never fails
  local m a
  m=$(git rev-parse --git-path rebase-merge 2>/dev/null)
  a=$(git rev-parse --git-path rebase-apply 2>/dev/null)
  if { [ -n "$m" ] && [ -d "$m" ]; } || { [ -n "$a" ] && [ -d "$a" ]; }; then
    git rebase --abort >/dev/null 2>&1 || echo "paper_commit: git rebase --abort failed"
  fi
  return 0
}

i=1; rest=$waits
while [ "$i" -le "$attempts" ]; do
  # -X theirs: on a conflict in the paper logs this run's (newer) version wins instead of the push failing
  if out=$(git pull -q --rebase -X theirs origin "$branch" 2>&1); then
    if out=$(git push -q origin "HEAD:refs/heads/$branch" 2>&1); then
      echo "paper_commit: attempt $i/$attempts: pushed to $branch"
      exit 0
    fi
    echo "paper_commit: attempt $i/$attempts: git push failed: $(git_error "$out")"
  else
    echo "paper_commit: attempt $i/$attempts: git pull --rebase failed: $(git_error "$out")"
  fi
  abort_rebase
  read -r w rest <<< "$rest"
  if [ "$i" -lt "$attempts" ]; then sleep "${w:-0}"; fi
  i=$((i + 1))
done

abort_rebase
i=1; rest=$rescue_waits
while [ "$i" -le "$rescue_tries" ]; do
  if out=$(git push -q origin "HEAD:refs/heads/$rescue" 2>&1); then
    echo "::error::paper_commit: could not push to $branch after $attempts attempts; the commit is on branch $rescue"
    exit 1
  fi
  echo "paper_commit: rescue try $i/$rescue_tries: push to $rescue failed: $(git_error "$out")"
  read -r w rest <<< "$rest"
  if [ "$i" -lt "$rescue_tries" ]; then sleep "${w:-0}"; fi
  i=$((i + 1))
done
echo "::error::paper_commit: could not push to $branch after $attempts attempts, and the push to rescue branch $rescue failed too ($rescue_tries tries); the log is only on this runner"
exit 1
}
