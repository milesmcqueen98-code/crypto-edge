# Trades-workers infrastructure: notes for the owner

Plain words. Nothing here changes a trading decision. The plan is `reports/owner/trades_workers_plan.md` (Parts 3 and 4).

## What was added

- `.github/workflows/paper-spot-tw.yml`: the sixth paper book. A copy of the fifth book's workflow. It runs a pinned
  commit of branch `owner/trades-workers` with that commit's own `bot/spot/config.tw.json` (the release build's config
  plus `"trades_workers": 3`). State and log go to `paper_spot_tw` on `main`. Schedule `3 */6 * * *`. Its control is the
  fifth book, unchanged.
- `.github/workflows/step-pairs-tw.yml` and `scripts/owner/step_pairs/run_pair_workers.py`: the same-machine pairs, one
  worker against three, on the sixth book's pinned commit. Four jobs a day at 03:05, 09:05, 15:05 and 21:05 UTC; the
  order is one worker first at 03 and 15, three workers first at 09 and 21. Results land in
  `reports/owner/step_pairs_tw/pair_<UTC start>Z.json`. The fifth book's pair tool (`run_pair.py`) is untouched and keeps
  running; the new tool reads the candidate's longer `tb_smoke.py` output (seven table columns, the trades pass line, the
  peak per second line).
- `.github/workflows/owner-status.yml`: the status report also runs after `paper-spot-tw` and `step-pairs-tw`, and the new
  folders are in its checkout.
- `scripts/owner/paper_status.py`: the sixth book appears in every table (newest event, running time, summary, data
  quality). New sections "Sixth book against the fifth book" and "Rule progress for the sixth book" (the workers pairs,
  items 1 to 5, requests inside a step against the fifth book, stops, and the reported figures). New functions only; the
  fifth book's functions and the fifth book's rule script are as they were.
- `scripts/owner/trades_workers/rule.py`: the rule of Parts 3 and 4 as code, for the one read.
- Tests: `scripts/owner/step_pairs/test_run_pair_workers.py`, `scripts/owner/test_paper_status.py` (new checks added, old
  ones unchanged) and `scripts/owner/trades_workers/test_rule.py`.

## What to set before the merge

One line: `CODE_REF: "PINNED_COMMIT_TO_BE_SET_BY_THE_OWNER"` near the top of `.github/workflows/paper-spot-tw.yml`. Put the
commit of branch `owner/trades-workers` that passed Parts 1 and 2 there. It is written nowhere else: the checkout, the
CODE file and the manual-run input (empty means this commit) all read it, and `step-pairs-tw.yml` takes the commit from
`paper_spot_tw/CODE` once the book has run. Until it is set the sixth book's checkout fails, so set it before the merge. A
different commit restarts the test.

Also: the schedules only run from `main`, and `step-pairs-tw` does nothing until `paper_spot_tw/CODE` exists (the book
must have run once).

## How the read is run, step by step

Period: from the first half-hour mark after the sixth book's first decision minute, 4,320 minutes, extended by six hours
(at most three times) while the sixth or the fifth book has fewer than 300 new bids on the 17 coins on the minutes both
were live. Write START and END as UTC minutes, both included (for example START 2026-11-19T01:30, END 2026-11-22T01:29).

1. Count the bids from the logs alone, before any research is fetched: arm events on the 17 coins at minutes that are
   decision minutes of both books, using `live_minutes` in `scripts/owner/reconcile/common.py` (as in the fifth book's
   read). If either book has fewer than 300, move END six hours later and count again.
2. Make a read branch from `main` once the logs and the pair files are on it. Fetch the research on a runner:
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
5. The rule (it also reads the workers pair files, `--pairs reports/owner/step_pairs_tw` by default):
   `python scripts/owner/trades_workers/rule.py --dir reports/owner/reconcile_tb/tw --start START --end END --sixth paper_spot_tw --fifth paper_spot_r5 --items-1-5 pass`
   (or `fail`). It writes `trades_workers_rule.md` and `trades_workers_rule.json` into the folder and prints the markdown.
   If it prints "PERIOD NOT COMPLETE" it gives no verdict; after the third extension add `--read-as-is`.
   Part 3 may need pairs from after the period: if fewer than 8 pairs count among those that started in the period, the
   script adds the pairs that count after END, oldest first, only until it has 8, and says how many started in the period,
   how many were added and when the last one used started. If fewer than 8 count even then it prints
   "PART 3 NOT COMPLETE: n of 8 pairs count; the pair jobs go on and the read waits" and gives no verdict: wait for the pair
   jobs, then run it again. With `--read-as-is` the clauses that need 8 pairs count as not met.

## Things to know

- The status report on the live log is progress only: it reads the whole log and every pair file so far. The rule script
  reads only heartbeats inside the period and cuts the logs at END first.
- Part 3, measure 3 (the pace) reads every pair file that started in the period, counting or not: a three-worker run with
  more than 8 trades requests in one second, a refusal or a rate limit fails it, and so does a file that cannot be read.
  The plan says one such answer in a three-worker half stops the pairs and the sixth book until the cause is known.
- The refusal and rate-limit tests of the pair tool are text searches taken over unchanged from `run_pair.py`. A printed
  number can set them off: a heartbeat counter equal to 429, a price such as 429.5 in an event line, or a three-decimal
  figure ending in .429 in the heartbeat. Such a pair is written as "limited" and does not count (and, if it is the
  three-worker run, fails the pace clause). If a pair file says so, look at its run's output in the job log before
  believing a rate limit.
- The rule script stops with an error (no verdict) if the folder's books are not the fifth and sixth, if its period differs
  from START and END, if the "all" group is not the 17 traded coins, or if a count from `item7_bids.csv` differs from
  `side_by_side.csv`.
- If the folder `paper_spot_tw` does not exist yet, the status report is written as usual and says nothing about the sixth
  book.
