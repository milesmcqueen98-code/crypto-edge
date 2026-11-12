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
- **Part 2,** not before both books' logs reach 22:24 UTC on Nov 14 (about 02:30 UTC on Nov 15; deviation log,
  Nov 12), and only with 300 new bids on the twelve in each book: the two-book
  reconciliation of scripts/owner/reconcile with the third book as the first book and the fourth as the second
  (paper_spot_tb and paper_spot_t18), over the minutes both were live, read for the twelve coins together. The
  fourth book's items 1 to 5 are in PAPER_STATUS.md.

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
