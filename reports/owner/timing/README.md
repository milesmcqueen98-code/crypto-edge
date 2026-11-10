# Live order timing against the research assumption: results (Nov 10 2026)

Plan: [reports/owner/timing_prereg.md](../timing_prereg.md) (fixed before any print was fetched; one deviation-log entry).
This is a measurement of simulation accuracy. Nothing was tuned and there is no pass or fail.

## The result
- **Q1: the live bot's timing (P1) costs P&L against the whole-minute assumption (P0) in two of three eras.**
  P1 is 11.3% below P0 in the check era and 16.6% below in 2022-23. In the selection era it is 4.8% above, which is
  under the 5% bar. That is the plan's "5% or more, same sign, in at least two eras", so the pilot should expect live
  P&L below paper and read its pass rule with that in mind.
- **Q2: fast re-pricing (P2) beats P1 by 5% or more in two eras: +8.6% (check) and +17.5% (2022-23).** It loses 7.1%
  in the selection era. By the plan's rule it qualifies to be built behind a switch and tested in the pilot.
  Removing only the gap (P3) beats P1 by 13.1% in 2022-23 but by just 2.8% and 0.1% in the other two eras, so it has
  **no material effect**.
- **What drives it:** about 10 to 17% of parents change. They move to a different minute, appear, or disappear. The
  per-fill price effect is small. A stale-bid fill pays 21 to 27 bp more than P0's fill in the same minute, but such
  fills are only 6 to 11% of P1's shared parents, so the dollar-weighted entry gap is +1.1 / +3.2 / +1.5 bp. Most of
  each P&L difference comes from P0 parents that P1 misses. Under the plan, their whole research ladder result is
  removed, while a parent found only by P1 adds back only its 4-sigma rung.

## Policies against P0 and against P1
"shared" = the same coin and minute in both books. entry = the dollar-weighted entry difference on shared parents
(bp; positive means the policy pays more). P&L % = first-order net P&L difference as a percent of the reference's
P&L. Sharpe = the change in daily Sharpe at S* (today's volumes, costs x2, capture 0.5, $250K) when the difference is
added to the incumbent's daily series.

| era | policy | vs | parents | ref | shared | shared share | only policy | only ref | entry bp | P&L bp/$ | P&L % | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sel | P1 | P0 | 1191 | 1165 | 1013 | 0.870 | 178 | 152 | +1.08 | +2.08 | **+4.8** | +0.33 |
| sel | P1a | P0 | 1193 | 1165 | 1042 | 0.894 | 151 | 123 | +0.70 | +2.39 | +5.5 | +0.13 |
| sel | P1b | P0 | 1205 | 1165 | 965 | 0.828 | 240 | 200 | +1.62 | -0.05 | -0.1 | +0.20 |
| sel | P2 | P0 | 1169 | 1165 | 1130 | 0.970 | 39 | 35 | 0.00 | -1.16 | -2.7 | -0.09 |
| sel | P3 | P0 | 1212 | 1165 | 1048 | 0.900 | 164 | 117 | +1.04 | +3.35 | +7.7 | +0.23 |
| sel | P2 | P1 | 1169 | 1191 | 1032 | 0.866 | 137 | 159 | -1.04 | -3.24 | **-7.1** | -0.42 |
| sel | P3 | P1 | 1212 | 1191 | 1147 | 0.963 | 65 | 44 | 0.00 | +1.27 | **+2.8** | -0.10 |
| chk | P1 | P0 | 443 | 418 | 376 | 0.900 | 67 | 42 | +3.24 | -5.51 | **-11.3** | -0.27 |
| chk | P1a | P0 | 433 | 418 | 373 | 0.892 | 60 | 45 | +2.29 | -1.99 | -4.1 | -0.13 |
| chk | P1b | P0 | 438 | 418 | 357 | 0.854 | 81 | 61 | +4.14 | -5.82 | -11.9 | -0.22 |
| chk | P2 | P0 | 420 | 418 | 401 | 0.959 | 19 | 17 | +0.68 | -1.80 | -3.7 | -0.12 |
| chk | P3 | P0 | 440 | 418 | 376 | 0.900 | 64 | 42 | +3.20 | -5.46 | -11.2 | -0.24 |
| chk | P2 | P1 | 420 | 443 | 385 | 0.869 | 35 | 58 | -2.40 | +3.71 | **+8.6** | +0.15 |
| chk | P3 | P1 | 440 | 443 | 429 | 0.968 | 11 | 14 | 0.00 | +0.05 | **+0.1** | +0.04 |
| early | P1 | P0 | 768 | 756 | 625 | 0.827 | 143 | 131 | +1.53 | -9.67 | **-16.6** | -0.49 |
| early | P1a | P0 | 767 | 756 | 636 | 0.841 | 131 | 120 | +1.15 | -2.40 | -4.1 | -0.02 |
| early | P1b | P0 | 787 | 756 | 588 | 0.778 | 199 | 168 | +2.01 | -6.90 | -11.8 | -0.21 |
| early | P2 | P0 | 762 | 756 | 718 | 0.950 | 44 | 38 | +0.16 | -1.14 | -1.9 | -0.06 |
| early | P3 | P0 | 778 | 756 | 642 | 0.849 | 136 | 114 | +1.47 | -3.32 | -5.7 | -0.11 |
| early | P2 | P1 | 762 | 768 | 640 | 0.833 | 122 | 128 | -1.16 | +8.54 | **+17.5** | +0.43 |
| early | P3 | P1 | 778 | 768 | 724 | 0.943 | 54 | 44 | 0.00 | +6.35 | **+13.1** | +0.38 |

- P0's first-order P&L: $70,301 (sel), $28,329 (chk), $55,072 (early), on $16.2M, $5.8M and $9.4M bought.
- P1a and P1b, the fast-call and slow-call variants of P1, bracket P1 without changing the picture. P1a is closer to
  P0 in the check era and in 2022-23 (-4.1% in both).
- Every column, including the dollar parts (entry adjustment, parents added, ladders removed), is in
  [policies.csv](policies.csv).

## Where fills happen in the minute
- **P0's parents (the research assumption), share filled in the first 8 / 10 / 15 s:** sel 11.2% / 14.2% / 22.3%,
  chk 17.2% / 18.4% / 27.0%, early 17.3% / 19.7% / 27.2%. Median fill at 29 to 33 s.
- **P1's shared parents by source:**

| era | stale-bid fills (0-8 s) | their entry vs P0 | new-bid fills | kept-bid fills |
|---|---|---|---|---|
| sel | 61 | +21.5 bp | 915 | 37 |
| chk | 43 | +25.1 bp | 315 | 18 |
| early | 36 | +27.4 bp | 563 | 26 |

  New-bid and kept-bid fills are at P0's price. Splits by second are in
  [entry_by_seconds.csv](entry_by_seconds.csv).
- "Kept" means the next level was within half a tick of the resting bid, so the bid stayed for the whole minute.

## P0 against the candle-based research (prereg item 6)

| era | research parents | P0 parents | confirmed by prints | research only | P0 only |
|---|---|---|---|---|---|
| sel | 1155 | 1165 | 1115 (96.5%) | 40 | 50 |
| chk | 412 | 418 | 395 (95.9%) | 17 | 23 |
| early | 744 | 756 | 692 (93.0%) | 52 | 64 |

## Data and checks
- **Studied minutes:** 18,755 (main: 14,110 sel and 4,645 chk) and 10,931 (early), 29,686 in all. They are merged into
  6,370 windows of [q, q + 70 s) and fetched on 8 GitHub Actions shards: 14.08M prints in 94,858 requests, with no
  refusal.
- **Completeness:** all 6,370 windows are complete (a page reached a print before the window start). Every studied
  minute has prints, and the last print before q is known for all of them.
- **Prints against candles:** the lowest print of the minute matches the candle low to within 0.5 bp in 98.4% (sel),
  97.8% (chk) and 96.1% (early) of studied minutes.
- **Level check:** the per-minute levels (scripts/lab LevelSet, R2-08) equal the levels on all 2,311 parent rows of
  the frozen dataset exactly (largest relative difference 0). Every research parent is approved in the panel.
  See data/levelcheck_*.txt.
- **Tests:** scripts/owner/timing/test_evaluate.py covers a fill only in the stale window, a fill only after
  placement, a dip inside the gap (no fill), the market already through at placement (skip), levels within half a
  tick (the bid stays), the one-tick trade-through boundary, approval lost at q, and the busy rule.
  scripts/owner/timing/test_derive.py checks the print reduction against brute force; it also ran on every runner
  before the fetch.

## How it was computed
- [export.py](../../../scripts/owner/timing/export.py) produces the studied minutes and levels.
  [windows.py](../../../scripts/owner/timing/windows.py) merges them into windows and shards.
- [prints_runner.py](../../../scripts/owner/timing/prints_runner.py) and prints_derive.py do the fetch and reduction
  on runners. They use signal lab 2's fetcher, unchanged in pacing and retries.
- [evaluate.py](../../../scripts/owner/timing/evaluate.py) evaluates the policies and P&L. Its core, `step` and
  `run_coin`, is pure.
- Each minute's timeline is evaluated once:
  - the bid carried in from q-1 rests [q, q + c);
  - the new bid rests [q + p, q + 60);
  - the tail of the new bid, [q + 60, q + 60 + c), is the next minute's stale bid.
  This is the prereg's [q + p, q + 60 + c) without double counting.
- A carried bid exists only if the coin was approved at q-1, its ladder was closed, and the bid was placed (not
  skipped) and not filled.
- Sizes and the research ladder results come from the incumbent's engine-faithful S* book (scripts/ladder_v6x
  lsim, the poll1s blend). A parent the research does not have gets the mean research parent fill for its coin and
  quarter.
- Data:
  - data/derived/derived_all.parquet has one row per studied minute. Its print paths are cut to the prices that can
    matter, and it evaluates identically to the runners' full rows; those are on branch owner/timing-data,
    reports/owner/timing/data/out.
  - parents.csv.gz lists every parent of every policy.

## Limits (as stated in the plan, plus what this run adds)
- First order only. Deeper rungs and exits are not re-simulated for parents that a policy adds.
- The removed-ladder versus added-rung asymmetry drives most of every P&L difference here. The differences come from
  roughly 35 to 240 changed parents per era. The plan has no significance test, and none was run.
- The selection era goes the other way from the other two in both readings (P1 vs P0, and P2 vs P1).
- The API timings (8 s and 10 s) are assumptions. P1a and P1b bracket them.
- The levels come from the repo's candles. The bot's levels come from candles fetched at q + 6 s, which this study
  does not check.
