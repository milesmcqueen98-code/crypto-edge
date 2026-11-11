# Interim look 1 at the two-book reconciliation (Nov 11 2026)

An interim look under the plan's rule (reports/owner/paper_reconcile_plan.md): it can stop the third book's test for a
fault. It cannot pass the test and it changes no rule.

- **Period:** Nov 11 2026, 01:47 to 12:30 UTC. Research job 43030553164 (990 answers, nothing refused or dropped),
  started 65 minutes after the last minute.
- **Minutes:** the third book has 634 decision minutes. The main book has 289: its log for 01:47 to 07:37 UTC was
  lost by a workflow fault (LOG.md, Nov 11). 288 minutes are common to both.

## Third book on its own minutes (102 new bids)
- **Bid level:** all 102 bids are within one tick of the research level. None is more than 5 bp off, and the error
  has no relation left with BTC's last-minute move (correlation -0.09 on the raw error).
- **Score:** 8 of the 102 bids (7.8%) had a research score at or below the threshold. All 8 are on coins of the candle
  path (8 of 87). None of the 15 bids on ETH, SOL, XRP, LTC and ZEC is. Seven of the 8 fall between 02:06 and 07:18
  UTC.
- **Score error by group:** on the trades-list coins, 90% of bids are within 0.05 score points of the research. On
  the candle-path coins, 10% of bids are more than 5.5 points away.
- **Bids in common:** 89% of the bot's bids have a research bid within a minute, and 87% of the research's bids have
  a bot bid.
- **Guard:** no minute was skipped for a stale BTC. 19 coin-minutes got no new bid because the candle answer was old.
- No first-bid fill on either side.

## Main book on its own minutes (36 new bids, 07:43 to 12:30 UTC)
- 5 of 36 bids are more than 5 bp from the research level (13.9%). The error follows BTC's last-minute move
  (correlation 0.61).
- 1 of 36 has a research score on the other side of the threshold.
- Bids in common: 78% of the bot's, 93% of the research's.

## Item 7 on the common minutes

| Measure | Main book | Third book |
|---|---|---|
| (a) New bids more than 5 bp from the research level | 5 of 36 | 0 of 17 |
| (b) New bids whose research score is at or below the threshold | 1 of 36 | 1 of 17 |

Verdict: wait. Each book needs 200 bids.

## Reading
- **The fix does what it was built for.** With BTC taken from verified trades, the bid level equals the research
  level in every bid so far.
- **What remains is the score of the twelve coins on the candle path.** About one of their bids in eleven is one the
  research would not have placed, mostly in quiet hours. Both books read those coins the same way, so release 2 does
  not change it. It is the subject of the planned comparison of bar sources for the twelve (FORWARD_TESTS.md).
- **Item 7(b) may come out close.** It compares two shares that this remaining error feeds in both books, and on a
  quiet day the main book's share is small too (1 of 36 here). The rule is not changed: an interim look changes no
  rule. It is written down so the read is not a surprise.

## Files
main/ and tb/ hold each book's tables on its own minutes. side_by_side.csv and item7.md are on the common minutes.
research/ is the runner's output.
