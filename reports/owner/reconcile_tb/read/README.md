# The third paper book's three-day read (Nov 14 2026)

This is the one registered read of the row "Verified inputs (release 2)" in reports/owner/FORWARD_TESTS.md. The rule
was applied as written, once. Verdict reached at 09:20 ET on Nov 14.

**Result: all seven items pass. One coin, LTC, leaves the trades list by item 6(b). Release 3 follows.**

- **Period:** the book's first three full days. First event 01:47 UTC on Nov 11, last decision minute 01:52 UTC on
  Nov 14 (reports/owner/paper_reconcile_plan.md, step 5). 4,318 real-time minutes against the 4,000 needed.
- **Research for item 7:** job 43602782356, 1,224 answers, nothing refused or dropped, fetched twelve hours after
  the last minute.

## The seven items

| Item | Measured | Verdict |
|---|---|---|
| 1. Verified trades bar in 99% of listed coin-minutes | 24,252 of 24,252 (100%) | pass |
| 2. No refusal, no rate-limit stop | none | pass |
| 3. Data step: median 13 s or less; half-hour maximum 20 s or less in 95% of heartbeats | median 10.1 s; 99.3% of 140 heartbeats (largest 23.9 s) | pass |
| 4. No error events | none | pass |
| 5. Unconfirmed rows at most 1% of coin-minutes | 15 of 75,240 (0.02%) | pass |
| 6(a). BTC's trades bar materially off in at most 1% of minutes | 6 of 2,938 compared minutes (0.20%) | pass |
| 6(b). Each other listed coin better than its own first-seen candle on both measures, every day | ETH, SOL, XRP, ZEC on all three days; LTC not on Nov 13 | pass; LTC leaves the list |
| 7(a). Share of new bids more than 5 bp from the research level, lower than the main book's | 9 of 550 (1.6%) against 360 of 715 (50.3%) | pass |
| 7(b). Share of new bids the research would not have placed, lower than the main book's | 23 of 550 (4.2%) against 153 of 715 (21.4%) | pass |

Items 1 to 5 are computed on the book's log cut at the period's end (items_1_5.md). Item 6 is in item6/item6.md,
item 7 in item7.md.

## Item 6 by coin and day (trades bar against the coin's own first-seen candle)

| Coin | Materially off, Nov 11 / 12 / 13 | Exactly equal, Nov 11 / 12 / 13 |
|---|---|---|
| BTC | 0.08% / 0.00% / 0.66% (candle: 68% / 80% / 95%) | 99.1% / 99.4% / 97.6% |
| ETH | 0.41% / 0.00% / 0.80% (candle: 15.9% / 15.5% / 9.1%) | 98.8% / 98.8% / 96.8% (candle: 63% / 68% / 81%) |
| SOL | 0.30% / 0.15% / 0.77% (candle: 26.5% / 22.5% / 17.8%) | 97.4% / 97.2% / 96.8% (candle: 62% / 64% / 70%) |
| XRP | 0.71% / 0.21% / 0.93% (candle: 13.6% / 12.6% / 8.8%) | 94.6% / 98.0% / 96.7% (candle: 75% / 78% / 82%) |
| ZEC | 1.32% / 1.40% / 2.98% (candle: 11.4% / 10.9% / 8.4%) | 95.6% / 88.3% / 84.6% (candle: 82% / 78% / 82%) |
| LTC | 3.26% / 1.95% / 2.30% (candle: 9.9% / 5.6% / 1.4%) | 84.4% / 87.8% / 87.1% (candle: 81% / 87% / 94%) |

- **LTC fails on Nov 13 on both measures.** The venue's candles for LTC were better that day than before, and LTC's
  trades bar was not. By the rule LTC leaves the list at release 3 and stays on the candle path; the days do not
  start again.
- **ZEC passes on every counted day, by a small margin on the last.** On Nov 14 so far (14 hours, a day the rule
  does not count) ZEC's trades bar was no better than its candle (materially off 3.4% each; exactly equal 80%
  against 83%). It stays on the list as the rule says. It is the weakest coin on it.
- For BTC the collector had a final candle to compare in 1,236, 942 and 760 of each day's 1,440 minutes.

## The two books side by side, on the 3,557 minutes both were live (for the record; only item 7 decides)

| Measure | Main book | Third book |
|---|---|---|
| New bids | 715 | 550 |
| Median distance from the research level | 5.1 bp | 0 |
| Correlation of the level error with BTC's last-minute move | 0.92 | 0.05 |
| The bot's new bids that the research also placed within a minute | 460 of 715 (64%) | 511 of 550 (93%) |
| The research's new bids that the bot also placed within a minute | 458 of 590 (78%) | 511 of 545 (94%) |
| First-bid fills in common with the research | 2 | 3 |
| First-bid fills the research did not have | 6 | 0 |
| Research fills the book missed | 3 | 2 |

- **The main book's six extra fills were bought above the research's level:** XLM 9 bp, SUI 33 bp, AAVE 52 bp, LINK
  57 bp, ETH 62 bp and ENA 73 bp above. The research had no fill there.
- **The third book's three fills are at the research's price to the tick** (ENA, SOL, ETH). It missed two DOGE fills;
  DOGE is on the candle path.
- **The main book got worse as the venue served more old BTC answers:** 57 of 142 new bids more than 5 bp off on
  Nov 11, 71 of 178 on Nov 12, 229 of 377 on Nov 13.
- **Results of the first-bid fills, for the record only:** main book +$139 on the two in common and +$169 on the six
  extra; third book +$253 on its three. Three days and a handful of fills say nothing about profit.

## What is left in the third book
- **By coin group, common minutes.** The five traded coins: 201 new bids, 5 more than 5 bp off, 4 the research
  would not have placed, 196 in common with the research both ways (98%). The twelve candle-path coins: 349 new
  bids, 4 more than 5 bp off, 19 the research would not have placed (5.4%), 315 in common both ways (90% and 91%).
- **All nine level errors fall on Nov 13,** checked against the collector's record:
  - Five are at one minute, 15:43 UTC, on five coins at once (5 to 8 bp, LTC among them). BTC's trades bar for
    15:42 closed 5.1 bp below the venue's candle, and BTC's newest close moves every level. It is one of BTC's six
    materially-off minutes in item 6(a).
  - One is LTC at 08:43 UTC (6.4 bp): the trades-built row an hour back, which the book keeps, closed 6.5 bp from
    the venue's candle. Interim look 2 showed the same for LTC.
  - Three are ZEC (9, 10 and 23 bp). In two of them the row an hour back exists in only one of the two sources. The
    largest is not explained by that row and was not traced further; the offline part of the bar-source plan
    measures ZEC on every minute.
- **Old candle answers:** the third book skipped 752 coin-minutes of the twelve for an old answer in the three days.
- On its own 4,255 minutes the third book has 784 new bids: 10 more than 5 bp off, 37 the research would not have
  placed (4.7%; 4 of 250 on the traded coins, 33 of 534 on the twelve).

## What follows
- **Release 3** switches the main book, W2 and the live bot to these inputs, with BTC, ETH, SOL, XRP and ZEC on the
  trades list (reports/owner/RELEASES.md).
- **The third and fourth books run on unchanged** until Part 2 of the bar-source plan is read. The fourth book's way
  replaces every trades row with the venue's candle afterwards, which is aimed at exactly what is left here: the
  kept rows and the twelve.

## Files
items_1_5.md, item6/ (the daily table and the rule's output), item7.md and item7_bids.csv, side_by_side.csv, main/
and tb/ (each book's tables on its own minutes), research/ (the runner's output, one table for all three books).
