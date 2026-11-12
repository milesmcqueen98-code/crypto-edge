# Interim look 2 at the two-book reconciliation (Nov 12 2026)

An interim look under the plan's rule (reports/owner/paper_reconcile_plan.md): it can stop a test for a fault. It
cannot pass a test and it changes no rule.

- **Period:** Nov 11 2026, 01:47 UTC, to Nov 12, 12:30 UTC. Research job 43228703620 (1,080 answers, nothing refused
  or dropped), started 65 minutes after the last minute.
- **Minutes:** the third book has 2,053 decision minutes, the main book 1,364. The main book's log is missing for
  01:47 to 07:37 and 13:28 to 19:18 UTC on Nov 11 (LOG.md, Nov 11). 1,361 minutes are common to both.

## Item 7 on the common minutes

| Measure | Main book | Third book |
|---|---|---|
| (a) New bids more than 5 bp from the research level | 82 of 229 (35.8%) | 0 of 159 (0.0%) |
| (b) New bids whose research score is at or below the threshold | 39 of 229 (17.0%) | 5 of 159 (3.1%) |

Verdict: wait. The third book has 159 of the 200 bids it needs on the common minutes; the main book has its 200.

## The two books side by side, common minutes

| Measure | Main book | Third book |
|---|---|---|
| Median distance from the research level | 3.1 bp | 0 |
| Correlation of the level error with BTC's last-minute move | 0.83 | 0.06 |
| The bot's new bids that the research also placed within a minute | 153 of 229 (67%) | 144 of 159 (91%) |
| The research's new bids that the bot also placed within a minute | 152 of 180 (84%) | 144 of 158 (91%) |
| First-bid fills: both, bot only, research only | 1, 1, 0 | 1, 0, 0 |

By coin group, third book: on ETH, SOL, XRP, LTC and ZEC 45 of 46 bids are also the research's and all 45 of the
research's are the bot's. On the twelve candle-path coins it is 99 of 113 both ways (88%).

## Third book on its own minutes (364 new bids)
- **Bid level:** 358 bids are within one tick of the research level. One is more than 5 bp off.
- **Score:** 19 bids (5.2%) had a research score at or below the threshold: 18 of 275 on the candle-path coins (6.5%)
  and 1 of 89 on the five traded coins.
- **Why the share is higher here than on the common minutes:** 7 of the 19 fall between 18:10 and 19:11 UTC on
  Nov 11, a busy hour for which the main book has no log. Item 7 counts the common minutes, as written.
- **All three level errors above 2 bp are LTC, and each is a kept trades row an hour back.** The bid level rests on
  the coin's close 60 minutes earlier. The third book keeps a trades-built row for good, and LTC's trades bar closed
  away from the venue's candle in exactly those minutes (collector's record):

  | Bid (UTC) | Level error | Row an hour back: trades close against candle close |
  |---|---|---|
  | Nov 11, 19:02 | -8.7 bp | 18:02: -8.8 bp |
  | Nov 12, 00:08 | -3.7 bp | 23:08: -4.8 bp |
  | Nov 12, 12:28 | +5.0 bp | 11:28: +4.9 bp |

  The 12:28 bid is also the one wrong-side bid on a traded coin (logged score 32.0, research 23.5). The fourth
  book's way replaces each trades row with the venue's candle once it is final, which removes this error by
  construction. Whether it does so in practice is what the bar-source plan's two reads measure.

## One fill, three books (Nov 11, 23:20 UTC)
- The main book's ENA bid stood 14 bp above the research level (0.14334 against 0.14314) and filled about $6,000
  (first-rung result +$102). It also filled an XLM bid the research had not placed (+$4).
- The third and fourth books bid ENA at the research level and filled $51 (+$0.86 each).
- One event. It shows how far a late BTC row can move a bid; it says nothing about profit either way.

## Fourth book against the third (folder i2_t18; first numbers, they decide nothing)
- **Period:** Nov 11, 22:25 UTC (where the fourth book's record begins) to Nov 12, 10:00 UTC. 675 common minutes.
- **Labels:** in that folder's tables "main" means the third book and "tb" means the fourth. Item 7's files are left
  out there, because item 7 is not the rule for this pair.
- **All coins:** third book 86 new bids, fourth 99. Neither has a bid more than 5 bp from the research level, and
  neither has a wrong-side bid.
- **The twelve:** third book 59 bids, fourth 70. Bids in common with the research: 55 of 59 both ways in the third
  book, 66 of 70 both ways in the fourth.
- Part 2's rule (reports/owner/bar_source_prereg.md) needs three full days together and 300 bids on the twelve in
  each book.

## Reading
- **The fix holds over a day and a half.** With BTC taken from verified trades, no bid of the third book on the
  common minutes is more than 5 bp from the research level, against one in three for the main book.
- **Two errors remain, both known and both under test.** The twelve candle-path coins give about one wrong-side bid
  in fifteen. LTC's kept trades rows give an occasional level error. The fourth book runs the way meant to remove
  both.
- **No fault that would stop either test.**

## Files
main/ and tb/ hold each book's tables on its own minutes. side_by_side.csv and item7.md are on the common minutes.
research/ is the runner's output, one research table for all three books.
