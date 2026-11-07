# Ladder v5 builder guide (read first)

You test pre-registered candidates against R2-08's live spot ladder. The rules are in reports/ladder_v5_prereg.md
(frozen); your candidate's exact rule is in its spec in this folder. Do not change any frozen file:
scripts/ladder_v5/{fsim,hsim,gates}.py, reports/ladder_v5/frozen/*, data/ladder_v5/*, reports/ladder_v5/exit_paths_*.pkl,
reports/ladder_v5/cache/*.

## Setup
- Work in your own git worktree on your own branch, created from origin/ladder/v5 at the freeze commit:
  `git -C /home/claude/crypto-edge fetch origin ladder/v5 && git -C /home/claude/crypto-edge worktree add /home/claude/wt/<id> -b ladder/<id> origin/ladder/v5`
  Never write into /home/claude/crypto-edge itself.
- The worktree needs the large untracked-in-git inputs? No: everything is committed on ladder/v5 (panel data, frozen
  pickles, exit paths, incumbent cache). Minute candles are in data/minute and data/minute_early (committed).
- Candidate code goes in scripts/ladder_v5/cand_<id>.py. Results go in reports/ladder_v5/<id>/.

## How to test
- One call of `gates.run(name, book_fn, path=...)` per pre-registered variant, nothing else first. It scores the
  candidate against the live incumbent in every configuration (S* at θ 0.5 and 0.25, base, $1M), applies gates G1-G4,
  and logs the trial to reports/ladder_v5/trials.csv and reports/ladder_v5/trials/<name>.json.
- `book_fn(P, era, pan=, adv_=, theta=, C=, today=, cost_mult=)` must return the daily returns on capital (index = the
  era's days), built with hsim/fsim exactly as the incumbent is, changing only your candidate's rule. Start from
  `hsim.book(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, pan=pan, adv=adv_)`, which is the incumbent.
- Before the gated run, check your book_fn with the candidate switched off reproduces the incumbent exactly (max daily
  difference 0) in at least one era and configuration. Report that check.
- Compute: the local machine has 2 cores shared by several agents. Heavy runs go to GitHub Actions:
  `gh workflow run hunt.yml --ref ladder/<id> -f script=scripts/ladder_v5/cand_<id>.py -f args="..." -f commit="reports/ladder_v5" -f tag=<id>`
  The runner commits outputs back to your branch; `git pull` to read them. One gated run takes roughly 10-25 minutes.
- Do not run extra variants, thresholds or configurations before every pre-registered variant is logged. Anything
  after that is labelled post hoc in your report and is not a trial for adoption.

## Report (reports/ladder_v5/<id>/REPORT.md, committed and pushed to your branch)
- The rule as implemented, the off-switch reproduction check, and the gate table per variant (pooled t on the
  declared path, per-era return/Sharpe of incumbent and candidate, G1-G4).
- What drives the result (by era, by rung, a few cascade days), and anything that looked wrong.
- Keep it short and factual. Commit messages end with:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01AEZT6kPaLhVZQWa1uXmv5Y
