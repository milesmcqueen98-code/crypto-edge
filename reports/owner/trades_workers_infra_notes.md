# Trades-workers infrastructure: notes for the owner

Plain words. Nothing here changes a trading decision. The plan is `reports/owner/trades_workers_plan.md` (Parts 3 and 4).

## What was added

- `.github/workflows/paper-spot-tw.yml`: the sixth paper book. A copy of the fifth book's workflow. It runs a pinned
  commit of branch `owner/trades-workers` with that commit's own `bot/spot/config.tw.json` (the release build's config
  plus `"trades_workers": 3`). State and log go to `paper_spot_tw` on `main`. Schedule `3 */6 * * *`. Its control is the
  fifth book, unchanged.
- `.github/workflows/workers-alt.yml` and `scripts/owner/workers_alt/run_alt.py`: Part 3 as alternating minutes, one worker
  against three, inside one run on one runner and on the sixth book's pinned commit. The half-hour pair design is gone: its
  tool (`run_pair_workers.py`), its test and its fixtures are removed, and so is `step-pairs-tw.yml`. One run is 60 minutes of
  paper steps with the sixth book's config (no orders, public data only); the trades pass uses one worker in one UTC minute
  and three in the next, turn by turn, and the arm of the first minute is the job's first arm. Four jobs a day at 03:05,
  09:05, 15:05 and 21:05 UTC; one worker first at 03 and 15, three workers first at 09 and 21 (the UTC hour decides: 00 to
  05 and 12 to 17 start with one). Results land in `reports/owner/workers_alt/alt_<UTC start>Z.json`: every step with its
  arm, its pass time, its peak of trades requests in one second, and whether it was limited or refused; then, after the run,
  the rows the trades pass built are compared with the venue's candles (the newest three minutes are left out). A row
  counts as the same only when all five values, open, high, low, close and volume, are equal as floats (`==`, no tolerance),
  as in `tb_smoke.py`. If a candle request fails, the comparison stops and the file says so (`rows_complete` false); the
  run's steps still count. The fifth book's pair tool (`run_pair.py`) is untouched and keeps running.
- `.github/workflows/owner-status.yml`: the status report also runs after `paper-spot-tw` and `workers-alt`, and the new
  folder is in its checkout.
- `scripts/owner/paper_status.py`: the sixth book appears in every table (newest event, running time, summary, data
  quality). New sections "Sixth book against the fifth book" and "Rule progress for the sixth book" (the alternating runs,
  items 1 to 5, requests inside a step against the fifth book, stops, and the reported figures). The alternating runs
  are shown one line per job (start, first arm, steps, medians, slow passes, fallbacks, peak, rows, and whether it counts)
  with progress on the four clauses of Part 3. New functions only; the fifth book's functions and the fifth book's rule
  script are as they were.
- `scripts/owner/trades_workers/rule.py`: the rule of Parts 3 and 4 as code, for the one read.
- Tests: `scripts/owner/workers_alt/test_run_alt.py`, `scripts/owner/test_paper_status.py` (new checks added, old
  ones unchanged) and `scripts/owner/trades_workers/test_rule.py`.

- Back to back (decided Nov 18, plan deviation log): from Nov 18 until the end of the test's 14 days, Dec 1 2026 11:41 UTC,
  the alternating jobs run one after the other. The job `next` in `.github/workflows/workers-alt.yml` starts the following
  job through `bot/spot/deploy/paper_next.sh` (a run under 30 minutes starts nothing). The sixth book's hand-over and the cron
  lines still start jobs too; at most one waits behind the running one. After 2026-12-01T11:41:00Z the job `next` starts
  nothing and can be removed.

## What was set before the merge

One line: `CODE_REF: "4c1717ac3cd711c3383e281ccb3eb2742f993b23"` near the top of `.github/workflows/paper-spot-tw.yml`:
the commit of branch `owner/trades-workers` named in the plan's deviation log. It is written nowhere else: the
checkout, the CODE file and the manual-run input (empty means this commit) all read it, and `workers-alt.yml` takes
the commit from `paper_spot_tw/CODE` once the book has run. A different commit restarts the test.

Also: the schedules only run from `main`, and `workers-alt` does nothing until `paper_spot_tw/CODE` exists (the book
must have run once).

## How the read is run, step by step

Period: from the first half-hour mark after the sixth book's first decision minute, 4,320 minutes, extended by six hours
(at most three times) while the sixth or the fifth book has fewer than 300 new bids on the 17 coins on the minutes both
were live. Write START and END as UTC minutes, both included (for example START 2026-11-19T01:30, END 2026-11-22T01:29).

1. Count the bids from the logs alone, before any research is fetched: arm events on the 17 coins at minutes that are
   decision minutes of both books, using `live_minutes` in `scripts/owner/reconcile/common.py` (as in the fifth book's
   read). If either book has fewer than 300, move END six hours later and count again.
2. Make a read branch from `main` once the logs and the alt files are on it. Fetch the research on a runner:
   `gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref BRANCH -f script=scripts/owner/reconcile/fetch_and_compute.py -f args="--books paper_spot_r5,paper_spot_tw --start START_MINUS_5_MIN --end END --out reports/owner/reconcile_tb/tw/research" -f tag=reconcile-tw -f sparse="bot edge scripts/owner reports/owner reports/cfm_products.csv paper_spot_r5 paper_spot_tw" -f commit="reports/owner/reconcile_tb/tw/research"`
   (START_MINUS_5_MIN is five minutes before START.)
3. The two books, the fifth as the first book and the sixth as the second:
   `python scripts/owner/reconcile/two_books.py --research reports/owner/reconcile_tb/tw/research --main paper_spot_r5 --third paper_spot_tw --start START --end END --out reports/owner/reconcile_tb/tw`
   In that folder's tables "main" means the fifth book and "tb" the sixth.
4. Items 1 to 5 of the sixth book: copy the sixth and the fifth book's logs cut at END into a scratch folder (keep
   `paper_spot_tw/` with its CODE file; the other folders may be copied whole) and run
   `python scripts/owner/paper_status.py SCRATCH_ROOT --now END_PLUS_ONE_MINUTE`, then read the section "Rule progress for
   the sixth book", "Part 4, measure 2: items 1 to 5". Item 3 there is its second half only. Say pass if all five items
   meet, else fail.
5. The rule (it also reads the alternating-run files, `--alt reports/owner/workers_alt` by default, and the time of the read,
   `--now`, which is the clock unless given):
   `python scripts/owner/trades_workers/rule.py --dir reports/owner/reconcile_tb/tw --start START --end END --sixth paper_spot_tw --fifth paper_spot_r5 --items-1-5 pass`
   (or `fail`). It writes `trades_workers_rule.md` and `trades_workers_rule.json` into the folder and prints the markdown.
   If it prints "PERIOD NOT COMPLETE" it gives no verdict; after the third extension add `--read-as-is`.
   Part 3 takes the jobs that count (`alt_*.json` with `counts` true) that started from the first one up to END, and may need
   jobs from after the period: while there are fewer than 8 jobs, or the one-worker steps of those jobs hold fewer than 30
   slow passes (above 6.0 s), the next job that counts is added, oldest first, if it started within 14 days of the first
   job's start; adding stops when both hold, and the script says how many jobs started in the period, how many were added and
   when the last one used started. If they do not hold and the 14 days have not passed at `--now`, it prints
   "PART 3 NOT COMPLETE: n of 8 jobs, m of 30 slow one-worker passes; the jobs go on and the read waits" and gives no verdict:
   wait for the jobs, then run it again. With `--read-as-is` clauses 1, 2 and 4 count as not met. If they do not hold and the
   14 days have passed, Part 3 is complete, clause 2 is not met and the output says "the gain is not shown".

## Things to know

- The status report on the live log is progress only: it reads the whole log and every alt file so far. The rule script
  reads only heartbeats inside the period and cuts the logs at END first.
- Part 3 has four clauses, over all steps of the jobs used: (1) no harm, the median pass with three at most the median
  with one plus 0.05 s; (2) a gain in slow minutes, at least 30 slow one-worker passes, the share of slow passes with three
  at most half of one's, and budget fallbacks not worse with three than chance allows; (3) the pace, over every alt file
  from the first job to the last one used, counting or not: no three-worker step with more than 8 trades requests in one
  second, none limited or refused, and a file that cannot be read is listed and fails it; (4) the rows, the share of built
  bars that differ from the venue's candle, not worse with three than chance allows (jobs with a complete comparison
  only; no rows on either side means not met). "Not worse than chance allows" is exact arithmetic with squares, no
  square roots. Fallbacks are counted in passes, not coins (a step with `tb_fb_budget` above zero is one pass, however many
  coins fell back): s1 one-worker passes, s3 three-worker ones; met if s3 <= s1, or if (s3 - s1) squared <= 4 * (s1 + s3).
  Rows: d = three's share minus one's, p = the pooled share; met if d <= 1/100, or if d squared <= 4 * p * (1 - p) *
  (1 / compared1 + 1 / compared3). The tools print which branch decided: "no more", "more, but within chance (two standard
  deviations of the difference)" or "more than chance allows". The coin sums of fallbacks are still shown, as information.
  The median and mean pass of both arms and their difference are reported, deciding nothing, with the line that the first
  version of the plan asked for a 0.2 s gain at the median over half-hour pairs. The plan says one such answer in a
  three-worker step stops the runs and the sixth book until the cause is known.
- A step is marked refused only when the engine's error text has `Refused(`, `HTTP 401`, `HTTP 403` or `HTTP 451`, and limited
  only when the counter `tb_fb_limited` rose in that step; the bare number 429 marks nothing. A job whose run ended with an
  exception, or with fewer than 20 timed steps in an arm, does not count; the file's `why_not` and the job log say why.
- The rule script stops with an error (no verdict) if the folder's books are not the fifth and sixth, if its period differs
  from START and END, if the "all" group is not the 17 traded coins, or if a count from `item7_bids.csv` differs from
  `side_by_side.csv`.
- If the folder `paper_spot_tw` does not exist yet, the status report is written as usual and says nothing about the sixth
  book.
