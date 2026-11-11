#!/usr/bin/env bash
# Commit step for the paper-log workflows (.github/workflows/paper-spot.yml, owner-status.yml): stage the given
# paths, commit, then pull --rebase and push with retries. Two jobs often finish within seconds of each other, so a
# push can be rejected after a clean pull (Nov 11: "cannot lock ref 'refs/heads/main'"); every failure is retried,
# and if all attempts fail the commit goes to a rescue branch so the log is not lost.
# The caller sets git user.name and user.email. Behaves the same under "bash -e" and plain bash: every command's
# result is checked explicitly and errexit is switched off below.
# Env: PAPER_COMMIT_BRANCH (default main), PAPER_COMMIT_WAIT (base wait in seconds, default 5; attempt n waits
#      n times that), GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT and GITHUB_JOB (name the rescue branch,
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
wait_base=${PAPER_COMMIT_WAIT:-5}
attempts=6
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

abort_rebase() {  # only when a rebase is in progress; never fails
  local m a
  m=$(git rev-parse --git-path rebase-merge 2>/dev/null)
  a=$(git rev-parse --git-path rebase-apply 2>/dev/null)
  if { [ -n "$m" ] && [ -d "$m" ]; } || { [ -n "$a" ] && [ -d "$a" ]; }; then
    git rebase --abort >/dev/null 2>&1 || echo "paper_commit: git rebase --abort failed"
  fi
  return 0
}

i=1
while [ "$i" -le "$attempts" ]; do
  # -X theirs: on a conflict in the paper logs this run's (newer) version wins instead of the push failing
  if git pull -q --rebase -X theirs origin "$branch"; then
    if git push -q origin "HEAD:refs/heads/$branch"; then
      echo "paper_commit: attempt $i/$attempts: pushed to $branch"
      exit 0
    fi
    echo "paper_commit: attempt $i/$attempts: git push failed"
  else
    echo "paper_commit: attempt $i/$attempts: git pull --rebase failed"
  fi
  abort_rebase
  if [ "$i" -lt "$attempts" ]; then sleep $((i * wait_base)); fi
  i=$((i + 1))
done

abort_rebase
if git push -q origin "HEAD:refs/heads/$rescue"; then
  echo "::error::paper_commit: could not push to $branch after $attempts attempts; the commit is on branch $rescue"
else
  echo "::error::paper_commit: could not push to $branch after $attempts attempts, and the push to rescue branch $rescue failed too; the log is only on this runner"
fi
exit 1
}
