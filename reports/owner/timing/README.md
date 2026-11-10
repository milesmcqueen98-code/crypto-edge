# Live order timing against the research assumption: results (Nov 10 2026)

**Where the rest is:** this page and the plan are copied to `main` for the record. The code, tests and data tables are on branch `owner/timing` (scripts/owner/timing/, reports/owner/timing/), so the file links below work there.

Plan: [reports/owner/timing_prereg.md](../timing_prereg.md) (fixed before any print was fetched; deviations logged there).

**Owner's verdict (Nov 10 2026): the bot's timing stays as built.** The whole-ladder valuation in part 2 meets the
plan's two-era condition for fast re-pricing, but the bracket of the live bot's own timings (P1a, P1, P1b) spreads
wider than any difference between policies, so the measure cannot rank them. Every realistic timing is within a
few percent of the research assumption. The full reading and the reasons are in the plan's "Final reading".
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

# Part 2: symmetric valuation

**Planned after the first reading was seen** (plan: "First reading", "Deviation 2", "Deviation 3"). The parents and
fill prices are the same as in part 1; only the valuation changes. Code: scripts/owner/timing/part2.py (moves, S1)
and part2_s2.py (S2).

## The reading under the rule (S2 decides)
- **P1 against P0: 5% or more worse in two eras under S2** (+1.9% / -11.9% / -11.9%) and under S1 (+3.7% / -16.8% /
  -26.0%). The first reading's direction holds once a changed parent is valued on both sides. Pooled in dollars: -5.1%
  (S2), -7.4% (S1).
- **P2 against P1: 5% or more better in two eras under S2** (-3.8% / +7.1% / +11.1%; selection is below 5% in the
  other direction) and under S1 (-9.7% / +10.9% / +27.2%). By the plan's rule, P2 still qualifies to be built behind a
  switch and tested in the pilot. Pooled it is only +2.6% (S2) and +0.9% (S1). The selection era goes the other way
  every time.
- **P3 against P1: no material effect** (S2 +4.0% / -2.1% / +9.8%; S1 +3.6% / -6.5% / +14.1%).
- Each difference comes from roughly 35 to 240 changed parents per era. No significance test was run (the plan has
  none).

## Moves (descriptive, no rule)
Share of P0's parents the policy fills in the same coin at the same minute / within 1 minute / within 2 minutes:

| era | P1 | P1a | P1b | P2 | P3 |
|---|---|---|---|---|---|
| sel | 0.870 / 0.893 / 0.909 | 0.894 / 0.913 / 0.925 | 0.828 / 0.863 / 0.888 | 0.970 / 0.974 / 0.975 | 0.900 / 0.921 / 0.934 |
| chk | 0.900 / 0.926 / 0.935 | 0.892 / 0.923 / 0.933 | 0.854 / 0.890 / 0.904 | 0.959 / 0.971 / 0.974 | 0.900 / 0.931 / 0.938 |
| early | 0.827 / 0.865 / 0.882 | 0.841 / 0.885 / 0.905 | 0.778 / 0.829 / 0.860 | 0.950 / 0.959 / 0.963 | 0.849 / 0.888 / 0.905 |

- Of the parents only in the policy and only in P0, few pair up one to one as moves. For P1, 27 / 11 / 29 pairs fall
  within 1 minute and 46 / 15 / 40 within 2 minutes, out of 152 / 42 / 131 lost parents. Most lost parents have no
  policy parent in that coin nearby.
- Paired moves enter at -0.7 / -16.4 / -13.5 bp against P0 (P1, within 1 minute, dollar-weighted). The medians are
  -8.0 / -5.2 / +0.3 bp, on few pairs.
- All policies: [moves.csv](moves.csv). The ten largest ladders removed from P1 per era, and whether P1 has a parent
  in that coin within 2 minutes: [removed_top_p1.csv](removed_top_p1.csv).
- In the selection era the four largest removed ladders are losers (-$3,223 HBAR, -$2,606 SOL, -$1,816 XRP, -$1,660
  SUI). That is why selection goes the other way in part 1.

## S1: every parent on its 4-sigma rung alone
The lab's exit rule on candles, costs x2, at each parent's own price and minute. Sizes are those of part 1.

| era | P0 4-sigma P&L | P1 vs P0 | P1a vs P0 | P1b vs P0 | P2 vs P0 | P3 vs P0 | P2 vs P1 | P3 vs P1 |
|---|---|---|---|---|---|---|---|---|
| sel | $37,291 | +3.7% (+0.08) | +5.9% (+0.03) | +3.6% (+0.11) | -6.4% (-0.10) | +7.5% (+0.09) | **-9.7%** (-0.18) | +3.6% (0.00) |
| chk | $12,605 | **-16.8%** (-0.16) | -6.5% (-0.10) | -10.6% (-0.06) | -7.8% (-0.12) | -22.3% (-0.21) | **+10.9%** (+0.04) | -6.5% (-0.05) |
| early | $15,818 | **-26.0%** (-0.23) | -19.9% (-0.15) | -20.7% (-0.14) | -5.8% (-0.06) | -15.5% (-0.12) | **+27.2%** (+0.18) | +14.1% (+0.12) |
| pooled | $65,714 | -7.4% | -2.7% | -5.0% | -6.5% | -3.8% | +0.9% | +3.9% |

In brackets: the change in daily Sharpe at S*. The difference is added to the incumbent's daily series, as in part 1.

- **Coverage:** in the research book the 4-sigma rung is 52.8% (sel), 50.6% (chk) and 29.9% (early) of the ladder
  P&L, so S1 covers about half of the book, and under a third in 2022-23.
- **Check against the research's own 4-sigma result** (the parents P0 shares with the research): $36,574 vs $37,411
  (-2.2%), $12,638 vs $14,326 (-11.8%), $16,147 vs $16,522 (-2.3%).
  - S1 uses model costs and a full take-profit fill.
  - The research uses print-measured remainder costs and capacity-limited take-profits.
  - The check-era gap is not split further.
- Files: [s1.csv](s1.csv), [s1_check.csv](s1_check.csv).

## S2: the whole ladder, like for like
Every parent of every policy, P0 included. The method is deviation 3:
- The 6 and 8 sigma rungs rest from 1 s after the parent's fill and fill on prints inside [q, q + 70 s); after that,
  candle lows until the parent's take-profit.
- Sizes, capacity, shared sellers and take-profit capacity come from the research's evaluator, with the cash cap off.
- The fee tier is the research book's, and remainder exits are priced from prints.
- Deep prints: the first fetch's runner artifacts re-read, with no new request. They hold 4.79M prints at or below
  the 6-sigma level plus a tick, on branch owner/timing-data, reports/owner/timing/data/out2.

**Validation, read before any policy difference** (the parents P0 shares with the research; USD):

| era | shared | A research ladder | B evaluator on frozen rows, no cash | C rows rebuilt here (candles), no cash | D P0 under S2 | D vs A | B vs A | D vs C |
|---|---|---|---|---|---|---|---|---|
| sel | 1115 | 69,524 | 86,035 | 86,041 | 88,427 | +27.2% | +23.7% | +2.8% |
| chk | 395 | 28,361 | 31,409 | 31,408 | 33,224 | +17.1% | +10.7% | +5.8% |
| early | 692 | 55,401 | 60,058 | 60,054 | 60,046 | +8.4% | +8.4% | -0.0% |

- **The row builder reproduces the research's frozen rows.**
  - Filled flags and fill minutes match on every rung, and take-profit minutes match on 99.8 to 100% of rungs.
  - B and C agree to within $6 per era.
  - Capacity differs by up to 20% on single rungs, and the 60-minute close by up to 2.6 bp. These come from the
    current candle files against the frozen ones. They are not traced further.
- **The gap between S2 and the research is the cash rule (B vs A: +24% / +11% / +8%).** S2 turns the cash cap off, as
  the plan set. The print timing adds +2.8% / +5.8% / 0.0% (D vs C). So S2's levels are above the research. Only the
  differences between policies are read, and every policy is valued the same way.

| era | P0 ladder P&L | P1 vs P0 | P1a vs P0 | P1b vs P0 | P2 vs P0 | P3 vs P0 | P2 vs P1 | P3 vs P1 |
|---|---|---|---|---|---|---|---|---|
| sel | $90,057 | +1.9% (+0.12) | +7.8% (-0.04) | +3.5% (+0.23) | -1.9% (-0.08) | +6.0% (+0.12) | -3.8% (-0.20) | +4.0% (0.00) |
| chk | $32,937 | **-11.9%** (-0.32) | -0.5% (-0.09) | -11.8% (-0.23) | -5.7% (-0.26) | -13.8% (-0.40) | **+7.1%** (+0.06) | -2.1% (-0.08) |
| early | $59,993 | **-11.9%** (-0.43) | -8.7% (-0.28) | -11.3% (-0.29) | -2.1% (-0.07) | -3.2% (-0.12) | **+11.1%** (+0.36) | **+9.8%** (+0.31) |
| pooled | $182,987 | -5.1% | +0.9% | -4.1% | -2.7% | -0.6% | +2.6% | +4.8% |

Files: [s2.csv](s2.csv), [s2_check.csv](s2_check.csv), [s2_rowcheck.csv](s2_rowcheck.csv), per-parent results
[s2_parents.csv.gz](s2_parents.csv.gz), and the readings [s1_rule.csv](s1_rule.csv) and [s2_rule.csv](s2_rule.csv).

## Part 2 limits
- The cash rule is off in S2. With it on, the research's ladder P&L is 8 to 24% lower. How much of each policy
  difference would survive the cash rule is not measured.
- S2 values every rung on the research's capacity and take-profit rules from candles; only the deeper fills use
  prints.
- The parents and their sizes are part 1's.
