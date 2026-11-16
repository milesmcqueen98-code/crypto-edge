# Part 3 infrastructure: notes for the owner

Plain words. Nothing here changes a trading decision. The plan is Part 3 of `reports/owner/bar_source_prereg.md`.

## What was added

- `.github/workflows/paper-spot-r5.yml`: the fifth paper book. A copy of the fourth book's workflow. It runs a pinned
  commit of branch `owner/release-5` with that commit's own `bot/spot/config.json`. State and log go to `paper_spot_r5`
  on `main`. Schedule `18 */6 * * *`.
- `.github/workflows/paper-spot.yml`: the job for the third book (`paper_tb`) is removed and the hand-over job now waits
  for `paper` only. The `paper` job (main book and W2) is unchanged. The third book's folder stays as the record.
- `.github/workflows/owner-status.yml`: the status report also runs after `paper-spot-r5`, and the fifth book's folder is
  in its checkout.
- `scripts/owner/paper_status.py`: the fifth book appears in every table. The third book can be marked ended. A new
  section "Rule progress for the fifth book" (measures 1, 3 and 4 as progress) and "Fifth book against the fourth book".
- `scripts/owner/bar_source/part3_rule.py`: the rule of Part 3 as code, for the one read.
- `.github/workflows/step-pairs.yml` and `scripts/owner/step_pairs/run_pair.py`: the same-machine step pairs (below).
- Tests: `scripts/owner/test_paper_status.py`, `scripts/owner/bar_source/test_part3_rule.py` and
  `scripts/owner/step_pairs/test_run_pair.py`.

In the fifth book's data quality table, two counters are left out, `tb_insert` and `tb_close_diff`. With candle requests
between steps they do not mean what they mean in the fourth book, so they cannot be compared. A note in the report says so.

## Measure 1 (a): the same-machine pairs (change of Nov 16, 12:04 ET)

Measure 1 no longer compares the fifth book with a fixed 10.3 s. Part (a) is now a median over same-machine pairs, and
part (b) (the fifth book against the main book over the same half hours) is as before. The fifth book's own median
against 10.3 s is still printed, marked as reported only.

- What runs: `.github/workflows/step-pairs.yml`, four times a day at 00:05, 06:05, 12:05 and 18:05 UTC. Each job runs, on
  one runner and on the fifth book's pinned commit, 30 minutes of paper steps with release 3's inputs and 30 minutes with
  the build's, one straight after the other. No orders, public data only, about 40 requests a minute for about an hour.
- Why :05: the step tool waits until the clock is at minute 20 or 50 of the hour. Set-up takes two to four minutes, so a
  job that starts at :05 idles about ten minutes at most, and a start up to about ten minutes late still catches :20. A
  later one waits for :50 and the 150-minute limit still holds.
- The pinned commit: read only from `paper_spot_r5/CODE` (the line `code_commit`). If that file does not exist yet, the
  job says the fifth book has not run and ends without a pair.
- The order alternates: `ab` (release 3 first) when the UTC hour of the job's start is 00 to 05 or 12 to 17, `ba`
  otherwise. So the four scheduled jobs of a day run ab, ba, ab, ba.
- Which settings are swapped: the input settings of the pinned code (`INPUT_KEYS` of `bot/spot/release_inputs.py`, without
  the order-path keys). Both runs use the build's own `bot/spot/config.json` as the base, so everything else is equal.
  Release 3's values are those of `bot/spot/config.json` on `main`. If the two files differ in any other key the pair
  does not run and its file says why.
- Where results land: `reports/owner/step_pairs/pair_<UTC start>Z.json`, committed to `main` by the job. A pair counts if
  both halves have at least 20 timed steps and neither met a refusal or a rate limit; otherwise the file says
  `"counts": false` and why.
- How the read uses them: `part3_rule.py` takes the pairs that count and start inside the period (`--pairs`, default
  `reports/owner/step_pairs`), computes the median of the build's median data step minus release 3's exactly from the
  printed medians, and needs at least 8 pairs and a median at or below zero (pairs from after the period are
  added only if fewer than 8 count inside it; see step 5 of the read). The status report lists every pair so far
  and the same count and median.
- To start a pair by hand: run the workflow `step-pairs` (Run workflow on `main`); the input `order` (ab or ba) is
  optional and empty means automatic from the hour; `minutes` stays 30.
- The result files must be on `main` (or on the read branch) when the read is run; copy `reports/owner/step_pairs` in
  with the logs.

## What you must set before the merge

1. The pinned commit: one line, `CODE_REF: "PINNED_COMMIT_TO_BE_SET_BY_THE_OWNER"` near the top of
   `.github/workflows/paper-spot-r5.yml`. It is written nowhere else. The checkout, the CODE file and the manual-run
   input (empty means this commit) all read it. Replace the text with the full 40-character commit hash. A different
   commit restarts the three days.
2. The date the third book ended: `ENDED = {"tb": "2026-11-16"}` in `scripts/owner/paper_status.py`. Set the real date.
   A book counts as ended from the start of that day (UTC). Before then the report treats it like any other book.

## How the read is run, step by step

Period: from the first half-hour mark after the fifth book's first decision minute, 4,320 minutes, extended by six hours
(at most three times) while the fifth or the fourth book has fewer than 300 new bids. Write START and END as UTC minutes,
both included (for example START 2026-11-19T01:30 and END 2026-11-22T01:29).

1. Count the bids from the logs alone (no research fetched): arm events on the 17 coins at minutes that are decision
   minutes of both the fifth and the fourth book, using `live_minutes` in `scripts/owner/reconcile/common.py`, as in
   "How the reads are run", step 4 of the plan. If either has fewer than 300, move END six hours later and count again.
2. Make a read branch from `main` once the logs are on it. Fetch the research on a runner:
   `gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref BRANCH -f script=scripts/owner/reconcile/fetch_and_compute.py -f args="--books paper_spot,paper_spot_t18,paper_spot_r5 --start START_MINUS_5_MIN --end END --out reports/owner/reconcile_tb/part3/research" -f tag=reconcile-part3 -f sparse="bot edge scripts/owner reports/owner reports/cfm_products.csv paper_spot paper_spot_t18 paper_spot_r5" -f commit="reports/owner/reconcile_tb/part3/research"`
   (START_MINUS_5_MIN is five minutes before START, as in Part 2's command.)
3. The two books, the fourth as the first book and the fifth as the second:
   `python scripts/owner/reconcile/two_books.py --research reports/owner/reconcile_tb/part3/research --main paper_spot_t18 --third paper_spot_r5 --start START --end END --out reports/owner/reconcile_tb/part3`
   In that folder's tables "main" means the fourth book and "tb" the fifth.
4. Items 1 to 5 of the fifth book: copy the fifth book's log cut at END into a scratch folder (keep `paper_spot_r5/` and
   its CODE file; the other folders may be copied whole) and run
   `python scripts/owner/paper_status.py SCRATCH_ROOT --now END_PLUS_ONE_MINUTE`, then read the section "Rule progress for
   the fifth book", items 1 to 5. Item 3 there is only its second half; its median is measure 1. Say pass if all five
   items meet, else fail.
5. The rule (it also reads the pair files, `--pairs reports/owner/step_pairs` by default):
   `python scripts/owner/bar_source/part3_rule.py --dir reports/owner/reconcile_tb/part3 --start START --end END --fifth paper_spot_r5 --fourth paper_spot_t18 --main paper_spot --items-1-5 pass`
   (or `fail`). It writes `part3_rule.md` and `part3_rule.json` into the folder and prints the markdown. If it prints
   "PERIOD NOT COMPLETE" it gives no verdict. After the third extension, add `--read-as-is`.
   Part (a) may need pairs from after the period: if fewer than 8 pairs count among those that started in the period,
   the script adds the pairs that count after END, oldest first, only until it has 8, and says in the markdown and the
   JSON how many started in the period, how many were added and when the last one used started. If fewer than 8 count
   even then it prints "PART (a) NOT COMPLETE" and gives no verdict: wait for the pair jobs to go on, then run it again.
   Part (b) and measures 2 to 4 are still read on the period. (`--read-as-is` makes part (a) not met instead.)

## Things to know

- The status report on the live log is progress only. It reads the whole log, not the period. The rule script reads
  only heartbeats inside the period and cuts the logs at END first.
- Measure 4's "first step after each start": for each heartbeat the script takes off at most 18 in-step requests
  (`pre_missing`) for every start whose first stepped minute falls in that heartbeat's half hour. A start's first stepped
  minute is found as in `common.py`: the first later event that is not a catch-up or backfill, else the backfill minute
  plus 6 minutes.
- The rule script stops with an error (no verdict) if the folder's books are not the fourth and fifth, if its period
  differs from START and END, if the "all" group is not the 17 traded coins, or if a count from `item7_bids.csv`
  differs from `side_by_side.csv`.
- If the folder `paper_spot_r5` does not exist yet, the status report is written as usual and says nothing about the
  fifth book.
