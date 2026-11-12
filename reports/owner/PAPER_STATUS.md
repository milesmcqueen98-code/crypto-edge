# Paper trading status

Report made 2026-11-12 12:49 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-12 12:49 UTC | 0.0 h ago | ok |
| Spot W2 | 2026-11-12 12:49 UTC | 0.0 h ago | ok |
| Spot TB (trades input) | 2026-11-12 12:46 UTC | 0.1 h ago | ok |
| Spot T18 (all coins on trades) | 2026-11-12 10:00 UTC | 2.8 h ago | ok |
| Perp v1 (control) | 2026-11-12 07:21 UTC | 5.5 h ago | ok |
| Perp R2-08 | 2026-11-12 07:21 UTC | 5.5 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-12 12:49 UTC | 134.3 | 89.7 | 66.8% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-12 12:49 UTC | 132.1 | 87.5 | 66.2% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-12 12:46 UTC | 35.0 | 35.0 | 99.9% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-12 10:00 UTC | 11.6 | 11.6 | 100.0% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-12 07:21 UTC | 136.8 | 86.4 | 63.2% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-12 07:21 UTC | 128.6 | 80.7 | 62.7% |

The five longest gaps of each book (a gap is the time the book was not running before a restart):

| Book | Gap start | Hours |
|---|---|---|
| Spot (main) | 2026-11-09 12:55 UTC | 9.7 |
| Spot (main) | 2026-11-10 13:30 UTC | 6.5 |
| Spot (main) | 2026-11-07 06:33 UTC | 6.0 |
| Spot (main) | 2026-11-11 01:47 UTC | 5.8 |
| Spot (main) | 2026-11-11 13:28 UTC | 5.8 |
| Spot W2 | 2026-11-09 12:55 UTC | 9.7 |
| Spot W2 | 2026-11-10 13:30 UTC | 6.5 |
| Spot W2 | 2026-11-07 06:33 UTC | 6.0 |
| Spot W2 | 2026-11-11 01:47 UTC | 5.8 |
| Spot W2 | 2026-11-11 13:28 UTC | 5.8 |
| Spot TB (trades input) | 2026-11-11 13:26 UTC | 0.0 |
| Perp v1 (control) | 2026-11-11 04:34 UTC | 8.9 |
| Perp v1 (control) | 2026-11-07 04:30 UTC | 7.9 |
| Perp v1 (control) | 2026-11-10 06:55 UTC | 7.3 |
| Perp v1 (control) | 2026-11-09 10:03 UTC | 5.0 |
| Perp v1 (control) | 2026-11-09 20:47 UTC | 4.4 |
| Perp R2-08 | 2026-11-11 04:34 UTC | 8.9 |
| Perp R2-08 | 2026-11-07 04:30 UTC | 7.9 |
| Perp R2-08 | 2026-11-10 06:55 UTC | 7.3 |
| Perp R2-08 | 2026-11-09 10:03 UTC | 5.0 |
| Perp R2-08 | 2026-11-09 20:47 UTC | 4.4 |

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 0.0 h; Spot W2 0.0 h; Spot TB (trades input) 0.1 h; Spot T18 (all coins on trades) 2.8 h; Perp v1 (control) 5.5 h; Perp R2-08 5.5 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 5.6 | $251,647 | +0.66% | 28 | $196,682 | 83.8 bp | 41 / 8 | 15 (14 made money) | 1 |
| Spot W2 | 5.5 | $251,411 | +0.56% | 28 | $169,892 | 83.1 bp | 41 / 8 | 17 (16 made money) | 1 |
| Spot TB (trades input) | 1.5 | $250,001 | +0.00% | 1 | $50.65 | 169.8 bp | 1 / 0 | 1 (1 made money) | 0 |
| Spot T18 (all coins on trades) | 0.5 | $250,001 | +0.00% | 1 | $50.65 | 169.8 bp | 1 / 0 | 1 (1 made money) | 0 |
| Perp v1 (control) | 5.7 | $10,011 | +0.11% | 2 | n/a (not logged) | n/a | 1 / 1 | - | 0 |
| Perp R2-08 | 5.4 | $9,988 | -0.12% | 2 | n/a (not logged) | n/a | 1 / 1 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

| Measure | So far |
|---|---|
| Days (calendar) | 5.6 of 21 |
| Days in real time | 3.7 |
| Rungs | 28 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 5.00 per calendar day; 7.49 per running day |
| Mean net per dollar | 83.8 bp |
| Errors (total) | 1 |
| Explained | 1 |
| Unexplained | 0 |

Explained errors:

| Time (UTC) | Error (first 160 characters) | Explanation | Queued fix |
|---|---|---|---|
| 2026-11-07 21:19 UTC | KeyError("Cannot get left slice bound for non-monotonic index with a missing label Timestamp('2026-10-27 21:19:00'). Either sort the index or specify an existin | The spot engine re-fetches the last three minutes of candles each minute, and when a re-fetch left out a minute that an earlier fetch had returned, the table was left out of order and the next time slice failed, so that one minute placed no new bids and the next minute's fetch repaired it. | Fixed in release 1 (Nov 10 2026): the candle table is sorted after the merge in update_spot (bot/spot/engine.py). |

Status: **NOT YET (too early)**

CHECK means unexplained errors are present or net is at or below 0. NOT YET means the 3 weeks and 60 rungs are not reached. ON TRACK means both are reached with no unexplained errors and net above 0. The owner declares any pass.

## Spot book detail

Fills and net per dollar by rung:

| Rung | Fills | Dollars bought | Exit events | Exit P&L | Net per dollar |
|---|---|---|---|---|---|
| 4 | 20 | $147,273 | 39 | $1,065 | 72.3 bp |
| 6 | 7 | $42,813 | 8 | $492.83 | 115.1 bp |
| 8 | 1 | $6,596 | 2 | $89.39 | 135.5 bp |

P&L of exits by day, last 14 days:

| Day (UTC) | Exit P&L | Hours running |
|---|---|---|
| 2026-11-06 | $0.00 | 1.5 |
| 2026-11-07 | -$3.06 | 18.0 |
| 2026-11-08 | $1,305 | 17.8 |
| 2026-11-09 | $238.52 | 12.9 |
| 2026-11-10 | $0.00 | 14.4 |
| 2026-11-11 | $4.26 | 12.3 |
| 2026-11-12 | $102.49 | 12.8 |

Cash shortfalls: 11. Wanted $115,534 in total (average $10,503) against an average of $1,308 free.

Share of capital held by resting bids (committed over equity, mean of 175 heartbeats): 56.35%.

Largest single-day loss so far: -$3.06 on 2026-11-07.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 5.6 | 5.5 | -0.1 |
| Hours in real time | 89.7 | 87.5 |  |
| Equity | $251,647 | $251,411 | -$235.72 |
| Change | +0.66% | +0.56% | -0.09 pp |
| Rung fills | 28 | 28 | +0 |
| Rung fills per calendar day | 5.00 | 5.09 |  |
| Rung fills per running day | 7.49 | 7.68 |  |
| Dollars bought | $196,682 | $169,892 | -$26,791 |
| Net per dollar | 83.8 bp | 83.1 bp | -0.7 bp |
| Exit events TP / time | 41 / 8 | 41 / 8 |  |
| Ladders closed (made money) | 15 (14) | 17 (16) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): -$235.72.

A few days and a few dozen fills cannot separate the two weightings; a gap this size is within what chance alone produces.

## Data quality

From the heartbeats of each spot book (one every 30 minutes while it runs). Counters are summed per UTC day; a counter that is not listed was 0 or is not reported. Minutes run are the 30 minutes before each heartbeat, less any gap. After a start-up the first heartbeat covers fewer stepped minutes than that, so minutes run can overstate the steps by a few minutes per run; item 1 of the third book's rule is therefore computed from the counters themselves. Data step is the seconds after the minute at which the data step finished: the median of the heartbeat medians, and the largest heartbeat maximum.

### Spot (main)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 261, btc_stale 464, candle_old 889, newest_absent 1,046 |
| 2026-11-12 | 750 | 25 | 9.7 | 12.6 | btc_candle_old 433, btc_stale 543, candle_old 1,880, newest_absent 1,701 |
| Total | 1,325 | 45 | 9.7 | 13.1 | btc_candle_old 694, btc_stale 1,007, candle_old 2,769, newest_absent 2,747 |

130 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot W2

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 411, btc_stale 464, candle_old 1,919, newest_absent 1,046 |
| 2026-11-12 | 750 | 25 | 9.7 | 12.6 | btc_candle_old 365, btc_stale 543, candle_old 1,683, newest_absent 1,701 |
| Total | 1,325 | 45 | 9.7 | 13.1 | btc_candle_old 776, btc_stale 1,007, candle_old 3,602, newest_absent 2,747 |

126 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot TB (trades input)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 1,273 | 43 | 10.2 | 23.9 | btc_candle_old 159, candle_old 182, newest_absent 1,336, rows_open 3, skip_old 96, tb_built 7,428, tb_close_diff 422, tb_insert 741, tb_rebuilt 5 |
| 2026-11-12 | 750 | 25 | 9.9 | 14.9 | btc_candle_old 220, candle_old 233, newest_absent 1,164, rows_open 6, skip_old 138, tb_built 4,434, tb_close_diff 235, tb_insert 336, tb_rebuilt 6 |
| Total | 2,023 | 68 | 10.0 | 23.9 | btc_candle_old 379, candle_old 415, newest_absent 2,500, rows_open 9, skip_old 234, tb_built 11,862, tb_close_diff 657, tb_insert 1,077, tb_rebuilt 11 |

### Spot T18 (all coins on trades)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 65 | 3 | 13.8 | 17.5 | btc_candle_old 3, candle_old 17, newest_absent 4, tb_built 1,112, tb_close_diff 84, tb_dropped 4, tb_empty 4, tb_insert 13, tb_rebuilt 7, tb_replaced 1,095, tb_replaced_diff 125 |
| 2026-11-12 | 630 | 21 | 13.5 | 19.4 | btc_candle_old 16, candle_old 244, newest_absent 341, tb_built 10,656, tb_close_diff 455, tb_dropped 485, tb_empty 341, tb_fb_budget 1, tb_insert 646, tb_pending 19, tb_rebuilt 14, tb_replaced 10,159, tb_replaced_diff 2,049 |
| Total | 695 | 24 | 13.6 | 19.4 | btc_candle_old 19, candle_old 261, newest_absent 345, tb_built 11,768, tb_close_diff 539, tb_dropped 489, tb_empty 345, tb_fb_budget 1, tb_insert 659, tb_pending 19, tb_rebuilt 21, tb_replaced 11,254, tb_replaced_diff 2,174 |

## Third book against the main book

Period both ran: 2026-11-11 01:47 UTC to 2026-11-12 12:46 UTC (35.0 calendar hours; 23.3 hours with both live).

| Measure | Spot (main) | Spot TB | TB minus main |
|---|---|---|---|
| Rung fills | 7 | 1 | -6 |
| Rung fills per calendar day | 4.80 | 0.69 |  |
| Rung fills per running day | 7.21 | 0.69 |  |
| First-bid fills (rung 4) | 7 | 1 | -6 |
| Deeper rungs placed | 4 | 2 |  |
| Dollars bought | $6,495 | $50.65 | -$6,444 |
| Exit P&L | $106.75 | $0.86 | -$105.89 |
| Net per dollar bought | 164.4 bp | 169.8 bp | +5.4 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 1 |
| Only in the main book | 6 |
| Only in the third book | 0 |

This comparison is for the record. It is not the pass rule; the rule is below.

## Three-day rule progress for the third book

> Verified inputs (release 2): after the first three full days of real-time running (at least 4,000 minutes), items 1 to 7 below must all hold. The rule is in reports/owner/FORWARD_TESTS.md. Items 1 to 5 are computed here from the heartbeats; the values are provisional until the minutes are reached.

Real-time minutes run so far: 2,097 of 4,000 (52%).

Listed coins for item 1: BTC, ETH, SOL, XRP, LTC, ZEC (read from bot/spot/config.tb.json).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 100.00% (11,862 verified of 11,862 attempted coin-minutes: built 11,862, verified empty 0; fallbacks: unverified 0, error 0, budget 0, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.0 s of 68 heartbeats; maximum 20 s or less in 98.5% (largest 23.9 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.025% (9 of 36,414 coin-minutes, 18 coins) | meets |
| 6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day | from the forward collector; computed at the read by scripts/owner/tb_rule6.py | not computed here |
| 7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both | from the reconciliation (scripts/owner/reconcile); not computed here | not computed here |

## Fourth book against the third book

Period both ran: 2026-11-11 22:25 UTC to 2026-11-12 10:00 UTC (11.6 calendar hours; 11.6 hours with both live).

| Measure | Spot TB | Spot T18 | T18 minus TB |
|---|---|---|---|
| Rung fills | 1 | 1 | +0 |
| Rung fills per calendar day | 2.07 | 2.07 |  |
| Rung fills per running day | 2.07 | 2.07 |  |
| First-bid fills (rung 4) | 1 | 1 | +0 |
| Deeper rungs placed | 2 | 2 |  |
| Dollars bought | $50.65 | $50.65 | $0.00 |
| Exit P&L | $0.86 | $0.86 | $0.00 |
| Net per dollar bought | 169.8 bp | 169.8 bp | +0.0 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 1 |
| Only in the third book | 0 |
| Only in the fourth book | 0 |

This comparison is for the record. The registered read is in reports/owner/bar_source_prereg.md.

## Rule progress for the fourth book

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-12T04:15:51Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: 695.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.99% (12,113 verified of 12,114 attempted coin-minutes: built 11,768, verified empty 345; fallbacks: unverified 0, error 0, budget 1, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.6 s of 24 heartbeats; maximum 20 s or less in 100.0% (largest 19.4 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 12,510 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 19 of 12,510 coin-minutes

Totals: tb_replaced 11,254, tb_replaced_diff 2,174, tb_dropped 489.

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 2 | 0.35 | 0.56 | 12.0 bp | $10,011 | +0.11% | 28,485 |
| Perp R2-08 | 2 | 0.37 | 0.59 | -36.7 bp | $9,988 | -0.12% | 26,286 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
