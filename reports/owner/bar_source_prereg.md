# Where the twelve candle-path coins should take their newest bar from. Plan (Nov 11 2026, 08:50 ET)

Written by the orchestrator before any decision has been computed with a trades bar for any of the twelve coins.
Branch owner/charter.

## Why
- **The BTC fix works.** In the first interim look at the third paper book (reports/owner/reconcile_tb/i1/README.md)
  all 102 new bids were within a tick of the research level.
- **What remains is the score of the twelve coins read from candles** (DOGE, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE,
  HYPE, ENA, PEPE, ONDO). 8 of their 87 bids were ones the research would not have placed, and 10% of their bids were
  more than 5.5 score points from the research. On the five traded coins that read trades, 90% of bids were within
  0.05 points.
- **Input shares do not settle the source.** On the collector's record for Nov 11, 00:00 to 13:00 UTC, the trades bar
  was materially off the final candle less often than the first-seen candle for seven of the twelve, more often for
  four and level for one, and it was exactly equal less often for all twelve.
- So the sources have to be compared in units of the bot's decisions.

## What has been seen before this plan
- The input shares above, and the same for 4.3 hours of Nov 10.
- The third book's reconciliation for 01:47 to 12:30 UTC on Nov 11: the candle path as the bot runs it, at its bids.
- Nothing at the level of decisions for a trades bar on any of the twelve.

## The three ways to fill a coin's rows
- **A, candles (today):** the newest minute as the candle answer gives it when first seen; older rows as the venue's
  final candles.
- **B, trades kept:** the newest minute from the verified trades bar, cut at the minute; a trades-built row is never
  replaced. The engine does this today for a listed coin.
- **C, trades then candles:** the newest minute from the verified trades bar; every older row as the venue's final
  candle. The engine cannot do this today.
- In all three, BTC and the five listed traded coins are as the third book has them, so only the coin's own rows
  differ.

## Part 1: every minute, offline, on the collector's record
- **Window:** Nov 11 2026 02:00 UTC to Nov 14 2026 02:00 UTC, three full days. The tool is built and proven on the
  collector's record before 02:00 UTC on Nov 11 only.
- **Data:** the collector's trades bars for all 18 coins (built about 10 s after each minute), its first-seen
  candles, and the venue's final candles fetched at least an hour after the last minute, as the reconciliation does.
- **Computation:** for each of the twelve coins (and LTC and ZEC, reported only), each way A, B, C and every minute
  where all inputs exist, the bot's score and bid level from the bot's own table and feature code, against the same on
  final candles (the research).
- **Measures, per coin and way, per day and for the three days:**
  1. Disagreement on arming, the primary measure: among the minutes where the way or the research has a score above
     the threshold, the share where only one of them has. Also split into armed by the way only and by the research
     only.
  2. Score error: the median and the 90th percentile of the absolute difference.
  3. Level error: the share of minutes more than 5 bp from the research level.
- **Checks on the emulation** (it stands in for a bot that does not run):
  - B on ETH, SOL, XRP, LTC and ZEC against the third book's own logged score at its new bids: the share within 0.5
    points. If it is under 90%, Part 1 is reported and not used for any decision.
  - A on the twelve against the third book's logged score at its new bids: the share within 0.5 points, reported. The
    collector asks for candles with a different address than the third book and gets old copies more often, so A may
    look worse here than it is in the book.
- **Limits:** for B, rows before the collector's record began (Nov 10, 21:44 UTC) are final candles, so the long
  look-back inputs are not fully trades-built. One request time (about 10 s after the minute) stands for the bot's.

## Part 2: forward, a fourth paper book
- **The book:** identical to the third book except that its trades list holds all 18 coins. Own folder
  (paper_spot_t18), own workflow file, so the third book's test is not touched. It starts when its workflow is on
  `main`.
- **Read once,** when the third and fourth books have run three full days together and each has at least 300 new
  bids on the twelve coins in the minutes both were live. It waits if there are fewer.
- **Measures, on the minutes both were live, the twelve coins together** (the reconciliation's tools and
  definitions):
  1. Wrong-side share: of the book's new bids with a valid research score, the share whose research score is at or
     below the threshold.
  2. Matched share: of the research's new bids, the share with a bot bid within a minute.
  3. Level: the share of the book's new bids more than 5 bp from the research level.
- Items 1 to 5 of the third book's rule (FORWARD_TESTS.md) are read for the fourth book too, with 18 listed coins.

## Decision rule (fixed now)
- **Trades kept (B) for the twelve is proposed for the next release** if, in Part 2, the fourth book's wrong-side
  share is strictly lower than the third book's, its matched share is not lower, its level share is below 5%, and
  items 1 to 5 hold for it. Shares are compared exactly on the counts.
- **A coin stays on candles in that case** if, in Part 1, its disagreement share under B is higher than under A on
  each of the three days.
- **Trades then candles (C) is built into the engine** only if, in Part 1, its disagreement share for the twelve
  together is at least a fifth lower than both A's and B's on each of the three days. It then gets its own paper test
  before any release.
- **Otherwise the twelve stay on candles** and their remaining score error is recorded as a known gap.
- No P&L test. A list change is a release, with a note to Miles, and comes after release 3 or with it, not before.

## Interim looks
The tools may be run on part of a window to prove they work and to catch a fault. A look cannot pass either part and
changes no rule.

## How the reads are run (added Nov 11 2026, 11:24 ET; tools on `main`)
- **Part 1,** not before 02:59 UTC on Nov 14 (the fetch refuses a newest minute under an hour old). On a branch
  made from `main` for the read, so the runner's tables are reviewed before they reach `main`:
  `gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref BRANCH
  -f script=scripts/owner/bar_source/build.py
  -f args="--start 2026-11-11T02:00 --end 2026-11-14T01:59 --out reports/owner/bar_source"
  -f commit="reports/owner/bar_source" -f tag=bar-source -f sparse="bot edge scripts/owner scripts/forward"`
  About an hour on the runner (seven whole-book passes, about 30,000 engine steps). Then, with the third book's log
  current through 01:59 UTC on Nov 14:
  `python scripts/owner/bar_source/compare.py --dir reports/owner/bar_source --log paper_spot_tb/events.jsonl`
  Without `--log` the emulation checks do not run and the single-coin clause is reported as not applied.
- **Part 2,** not before both books' logs reach 22:29 UTC on Nov 14 (about 02:30 UTC on Nov 15; deviation log,
  Nov 12), and only with 300 new bids on the twelve in each book. The period is the fourth book's first three full
  days of decisions: 2026-11-11T22:30 to 2026-11-14T22:29, both minutes included (4,320 minutes). Steps, fixed on
  Nov 12 at 12:58 ET, before any of the read:
  1. A branch made from `main` once both logs are on it (for example owner/read-part2). Research on a runner:
     `gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref BRANCH
     -f script=scripts/owner/reconcile/fetch_and_compute.py
     -f args="--books paper_spot,paper_spot_tb,paper_spot_t18 --start 2026-11-11T22:25 --end 2026-11-14T22:29
     --out reports/owner/reconcile_tb/part2/research" -f tag=reconcile-part2
     -f sparse="bot edge scripts/owner reports/owner reports/cfm_products.csv paper_spot paper_spot_tb paper_spot_t18"
     -f commit="reports/owner/reconcile_tb/part2/research"`
  2. The two books, with the third as the first book and the fourth as the second:
     `python scripts/owner/reconcile/two_books.py --research reports/owner/reconcile_tb/part2/research
     --main paper_spot_tb --third paper_spot_t18 --start 2026-11-11T22:30 --end 2026-11-14T22:29
     --out reports/owner/reconcile_tb/part2`
  3. The fourth book's items 1 to 5 from the status report run on a copy of its log cut at the period's end (as
     for the third book's read: reports/owner/paper_reconcile_plan.md, step 6), then the rule:
     `python scripts/owner/bar_source/part2_rule.py --dir reports/owner/reconcile_tb/part2 --items-1-5 pass` (or
     `fail`). It reads the twelve coins on the common minutes and writes part2_rule.md. The script is the rule above
     as code (63 checks; on `main` since Nov 12, before any read). In that folder's tables the label "main" means
     the third book and "tb" the fourth.
  4. **If the bids are short** (fixed Nov 13 at 08:46 ET): if either book has fewer than 300 new bids on the twelve
     at 22:29 UTC on Nov 14, the period's end moves later in steps of six hours (04:29, 10:29, 16:29 UTC on Nov 15,
     and so on) until both have 300, and steps 1 to 3 use that end. The bids are counted from the two logs alone:
     arm events on one of the twelve coins at a minute that is a decision minute of both books
     (scripts/owner/reconcile/common.py, live_minutes). No research is fetched for a count.

## Result of Part 1 (read Nov 14 2026, 10:34 ET)
Run as "How the reads are run" says: runner job 43603482156 on branch owner/read-barsrc (4,320 decision minutes,
seven whole-book passes, 30,240 engine steps, 1,224 candle answers, nothing refused), then compare.py with the third
book's log. Tables: reports/owner/bar_source/ (summary.md has every coin and day).

- **The two checks on the emulation, read first.**
  - Way B on ETH, SOL, XRP, LTC and ZEC against the third book's logged score at its new bids: 240 of 249 within
    0.5 points (96.4%). The bar is 90%, so Part 1 may be used for its one decision.
  - Way A on the twelve: 486 of 528 within 0.5 points (92.0%). Reported, as planned.
- **The single-coin clause: no coin stays on candles.** For each of the twelve the score-miss share under C is
  lower than under A over the three days, and for no coin is it higher on two of the three days (it is higher on
  one day for six coins, on none for the other six).
- **The twelve together, three days, 51,840 coin-minutes:**

  | Measure | A, candles | B, trades kept | C, trades then candles | C with all 18 coins |
  |---|---|---|---|---|
  | Disagreement on arming | 240 of 49,272 (0.49%) | 378 of 49,376 (0.77%) | 167 of 49,239 (0.34%) | 163 of 49,237 (0.33%) |
  | Score more than 1.0 point from the research | 1,733 (3.3%) | 3,706 (7.1%) | 1,344 (2.6%) | 1,279 (2.5%) |
  | Level more than 5 bp from the research | 572 (1.1%) | 7,354 (14.2%) | 572 (1.1%) | 497 (1.0%) |

  - C has fewer score misses than A on each day: 393, 439 and 512 against 565, 561 and 607.
  - B is worse than A on every measure. Its level is off in one coin-minute in seven. That is why it was dropped as
    a candidate on Nov 11.
- **By coin, score-miss share under C against A:** DOGE 2.6% against 6.2%, HYPE 1.2% against 2.1%, NEAR 2.1% against
  3.2%, PEPE 5.1% against 6.1%, LINK 1.9% against 2.4%, SUI 1.8% against 2.2%, XLM 1.8% against 2.1%, ENA 3.4%
  against 3.9%, HBAR 3.0% against 3.3%, BCH 3.1% against 3.3%, AAVE 3.7% against 3.8%, ONDO 1.6% against 1.7%. The
  gain is large for DOGE, HYPE and NEAR and small for AAVE, ONDO and BCH.
- **LTC and ZEC, reported only** (score misses under A, B, C; then level more than 5 bp off): LTC 1.1%, 1.2%, 0.8%;
  level 1.2%, 2.8%, 1.2%. ZEC 3.0%, 1.4%, 1.3%; level 1.5%, 4.1%, 1.5%. Keeping trades rows puts the level off more
  often for both; C does not. This agrees with the third book's read, which took LTC off the list and found ZEC's
  level errors.
- **Limits:**
  - **The level column says little about the bot.** The level errors under A and C fall in 54 minutes, and in 50 of
    them at least ten of the twelve coins are off at once, which points to BTC. In 40 of the 54 the collector's own
    BTC bar was a fallback, one minute or an hour back (it could not verify 49 of its 4,575 BTC bars). The third
    book had no fallback in its three days.
  - **The gain is modest in size.** C removes about a fifth of A's score misses and about a third of its
    disagreements on arming. Whether that shows in a running book is Part 2's question.
- **What it decides:** the single-coin clause only. If Part 2 passes, all twelve go to way C and none is held back.

## Deviation log
- **Nov 11 2026, 09:17 ET (orchestrator).** Made after the tool's development run and before any minute of either
  registered window was read for this plan.
  - **What the development window showed** (Nov 10 21:50 to Nov 11 01:59 UTC, 250 minutes; outputs on branch
    owner/bar-source, reports/owner/bar_source_dev):
    - A coin's score reads two inputs built from all the other coins. Each way is therefore computed as a whole book
      that could exist (six passes). This changes no rule.
    - **Way B puts the bid level off.** With trades rows kept, the level of the twelve was more than 5 bp from the
      research in 282 of 3,000 coin-minutes (9.4%; 1.6% to 22% by coin), against 4 under A and under C. The level
      rests on the coin's close an hour back, and a trades bar's close differs from the final candle's wherever the
      candle ran late. ZEC, which the third book keeps on trades, shows 5.2% in the same minutes.
    - Disagreements on arming are few: 5 to 9 in about 2,700 coin-minutes, because the research was armed in about
      90% of them. A rule that asks a margin on each day would turn on a handful of minutes.
    - A's score error is small in this emulation (90th percentile 0.1 point), far below what the third book showed at
      its bids. The check against the book's log decides whether the emulation can be trusted.
  - **Changes:**
    1. **Part 2 tests way C, not B.** The fourth book takes the newest minute of all 18 coins from trades and
       replaces each such row by the venue's candle once a late enough answer holds it. That needs an engine option.
       It is built on a branch, and the fourth book runs the code of that branch, so the engine on `main` is not
       touched while the third book's test runs.
    2. **B is no longer a candidate** for the twelve. It stays in Part 1 as a reported column.
    3. **The decision rule, restated:**
       - Way C for the twelve, with the six listed coins on the same way, is proposed for the next release if, in
         Part 2, the fourth book's wrong-side share on the twelve is strictly lower than the third book's, its
         matched share is not lower, its level share is below 5%, and items 1 to 5 hold for it.
       - The clause that C is built only on a one-fifth margin in Part 1 is dropped. The option is built now, for the
         forward test. A release still needs Part 2.
       - The single-coin clause compares C with A on a measure with enough events, the score-miss share: the share
         of minutes whose score is more than 1.0 point from the research. A coin stays on candles if Part 1 has its
         score-miss share under C strictly higher than under A over the three days and on at least two of the three
         days. The clause applies only if the emulation check on B passes.
    4. **Part 1 gains** the score-miss share, per coin and way, and a pass with all 18 coins on way C, which is what
       the fourth book runs.
  - Nothing else changes: the windows, the data, the two emulation checks, and no P&L test.
- **Nov 11 2026, 11:13 ET (orchestrator).** Made before the fourth book's first run, on the engine option's tests and
  two smoke runs on the real market. No minute of either registered window has been read for this plan.
  - **The option is built** (branch owner/engine-c, commit 58eba8b; key `trades_rows: "candle_after"`): the decision
    for a minute uses its trades bar; a candle answer made at least 85 s after the minute began then replaces the row,
    or drops it where the venue has no bar. With the key absent the engine is identical to `main` (the stored replay
    gives the same 530 events in three modes; all existing tests pass).
  - **Smoke run 43044140767** (45 minutes, all 18 coins): every row the engine held, the newest three minutes left
    out, was identical to a fresh fetch of the venue's candles, for all 18 coins. 666 of 666 trades bars verified.
    540 trades rows were built in the full half hour, 537 were replaced by the candle and 3 dropped; in 48 of the
    replacements the candle's close differed from the trades bar's by more than a tick.
  - **Step time:** the data step finished a median of 13.3 to 13.5 s after the minute (maximum 17.7 s); an earlier
    eight-minute smoke of 18 coins had 11.6 s. Eighteen trade requests take about 3.5 s more than six.
  - **Changes:**
    1. **Item 3 for the fourth book** reads: data step median 15 s or less, and the 30-minute maximum 20 s or less in
       95% of heartbeats. The 13 s bar was set for a book with six coins on trades. The timing study's slower bracket
       placed bids 15 s after the minute and found no cost it could measure. A faster data step is a separate change
       for later, with its own check.
    2. **The engine commit is fixed for the test.** The fourth book runs commit 58eba8b, named in the workflow file
       and written into paper_spot_t18/CODE at every run. A change of that commit starts its three days again.
- **Nov 12 2026, 08:54 ET (orchestrator).** A date moves; no rule changes.
  - **What happened:** the fourth book's first run (43056376442, 16:15 to 22:05 UTC on Nov 11) ended without saving
    its log or its state, because every push failed on the runner's token. The book began again from nothing with
    run 43110721127; its first step was at 22:25 UTC on Nov 11.
  - **Part 2's three days run from 22:25 UTC on Nov 11 to 22:24 UTC on Nov 14.** The read waits until both books'
    logs reach that minute (the fourth book's arrives with the run that ends at about 02:30 UTC on Nov 15) and for
    300 new bids on the twelve in each book.
  - **What had been read when this was written:** one interim look at both books' bids for 22:25 UTC on Nov 11 to
    10:00 UTC on Nov 12 (reports/owner/reconcile_tb/i2/README.md): 59 and 70 new bids on the twelve, no wrong-side
    bid and no level error in either. It changes no rule.
  - Nothing else changes.
- **Nov 12 2026, 12:58 ET (orchestrator).** A five-minute correction and the read's steps; no rule changes.
  - **Correction:** this morning's entry gave 22:25 UTC on Nov 11 as the fourth book's first step. 22:25 is its
    first event, the start of its download. Its first decisions are at 22:30 UTC. Its first three full days of
    decisions are therefore 22:30 UTC on Nov 11 to 22:29 UTC on Nov 14, and that is Part 2's period. None of the
    five minutes concerned had happened when this was written.
  - **The rule is now code** (scripts/owner/bar_source/part2_rule.py; agent, reviewed): the two conditions, the
    three measures on the twelve and the fourth book's items 1 to 5 as an input. Two points the plan left open are
    settled in it: a measure with no bids to count waits instead of failing, and "three full days" is checked as a
    period of at least 4,320 minutes.
  - **The exact commands** are in "How the reads are run". The only look at these books' bids so far is the interim
    one of this morning (59 and 70 bids on the twelve, no wrong-side bid in either).
- **Nov 13 2026, 08:46 ET (orchestrator).** What happens if the bids are short; no rule changes.
  - **Why:** the rule waits for 300 new bids on the twelve in each book but did not say how the period's end is
    then chosen. Left open, the end could be picked after seeing results.
  - **Fixed now:** the end moves later in whole steps of six hours until both books have 300 (step 4 of "How the
    reads are run"). The count uses the logs only.
  - **What was known when this was written:** the counts from the logs through 09:00 UTC on Nov 13: 158 new bids on
    the twelve in the third book and 159 in the fourth, on 2,008 common minutes. At that pace both reach about 330
    by 22:29 UTC on Nov 14. No research has been fetched for these books since the interim look of Nov 12.
- **Nov 14 2026, 10:54 ET (orchestrator), before Part 2 is read.** What a pass leads to; no rule changes.
  - **The rule stands as written:** a pass makes "trades for the newest minute, the venue's candle afterwards" the
    proposal for the next release.
  - **One condition on that release, fixed now:** it must not place its bids later in the minute than release 3
    does. The fourth book's data step ends a median 13.4 s after the minute, against 10.3 s in the third book,
    because it asks for 18 coins' trades one after another. The paper books do not feel that, since they fill on
    whole-minute candles. The live bot would: by the timing study each second costs about one point of same-minute
    fills, and three seconds is more than the new way gains in bids (FORWARD_TESTS.md, the note of this date).
  - **What follows:** the release is built with the candle requests outside the critical seconds and the trades
    requests side by side, and that build runs as a paper book first, on a rule fixed before it starts.
  - **What was known when this was written:** Part 1's result of this morning, the interim look of Nov 12, and the
    books' step times from their heartbeats. No research has been fetched for Part 2's period.
