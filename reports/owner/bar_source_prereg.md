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

## Deviation log
(none yet)
