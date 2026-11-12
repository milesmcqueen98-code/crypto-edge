# Paper trading status

Report made 2026-11-12 19:02 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-12 18:30 UTC | 0.5 h ago | ok |
| Spot W2 | 2026-11-12 18:30 UTC | 0.5 h ago | ok |
| Spot TB (trades input) | 2026-11-12 18:30 UTC | 0.5 h ago | ok |
| Spot T18 (all coins on trades) | 2026-11-12 15:30 UTC | 3.5 h ago | ok |
| Perp v1 (control) | 2026-11-12 19:02 UTC | 0.0 h ago | ok |
| Perp R2-08 | 2026-11-12 19:02 UTC | 0.0 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-12 18:30 UTC | 140.0 | 95.4 | 68.1% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-12 18:30 UTC | 137.8 | 93.2 | 67.6% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-12 18:30 UTC | 40.7 | 40.6 | 99.8% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-12 15:30 UTC | 17.1 | 17.1 | 100.0% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-12 19:02 UTC | 148.5 | 98.0 | 66.0% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-12 19:02 UTC | 140.3 | 92.2 | 65.7% |

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
| Spot TB (trades input) | 2026-11-12 12:47 UTC | 0.0 |
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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 0.5 h; Spot W2 0.5 h; Spot TB (trades input) 0.5 h; Spot T18 (all coins on trades) 3.5 h; Perp v1 (control) 0.0 h; Perp R2-08 0.0 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 5.8 | $251,692 | +0.68% | 33 | $216,149 | 78.3 bp | 47 / 10 | 19 (17 made money) | 1 |
| Spot W2 | 5.7 | $251,448 | +0.58% | 33 | $184,618 | 78.5 bp | 47 / 10 | 21 (19 made money) | 1 |
| Spot TB (trades input) | 1.7 | $250,141 | +0.06% | 2 | $20,884 | 67.5 bp | 2 / 0 | 2 (2 made money) | 0 |
| Spot T18 (all coins on trades) | 0.7 | $250,141 | +0.06% | 2 | $20,884 | 67.5 bp | 2 / 0 | 2 (2 made money) | 0 |
| Perp v1 (control) | 6.2 | $10,046 | +0.46% | 3 | n/a (not logged) | n/a | 2 / 1 | - | 0 |
| Perp R2-08 | 5.8 | $10,023 | +0.23% | 3 | n/a (not logged) | n/a | 2 / 1 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

| Measure | So far |
|---|---|
| Days (calendar) | 5.8 of 21 |
| Days in real time | 4.0 |
| Rungs | 33 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 5.66 per calendar day; 8.30 per running day |
| Mean net per dollar | 78.3 bp |
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
| 4 | 25 | $166,739 | 47 | $1,110 | 66.6 bp |
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
| 2026-11-12 | $147.69 | 18.5 |

Cash shortfalls: 11. Wanted $115,534 in total (average $10,503) against an average of $1,308 free.

Share of capital held by resting bids (committed over equity, mean of 187 heartbeats): 56.71%.

Largest single-day loss so far: -$3.06 on 2026-11-07.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 5.8 | 5.7 | -0.1 |
| Hours in real time | 95.4 | 93.2 |  |
| Equity | $251,692 | $251,448 | -$243.97 |
| Change | +0.68% | +0.58% | -0.10 pp |
| Rung fills | 33 | 33 | +0 |
| Rung fills per calendar day | 5.66 | 5.75 |  |
| Rung fills per running day | 8.30 | 8.50 |  |
| Dollars bought | $216,149 | $184,618 | -$31,531 |
| Net per dollar | 78.3 bp | 78.5 bp | +0.2 bp |
| Exit events TP / time | 47 / 10 | 47 / 10 |  |
| Ladders closed (made money) | 19 (17) | 21 (19) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): -$243.97.

A few days and a few dozen fills cannot separate the two weightings; a gap this size is within what chance alone produces.

## Data quality

From the heartbeats of each spot book (one every 30 minutes while it runs). Counters are summed per UTC day; a counter that is not listed was 0 or is not reported. Minutes run are the 30 minutes before each heartbeat, less any gap. After a start-up the first heartbeat covers fewer stepped minutes than that, so minutes run can overstate the steps by a few minutes per run; item 1 of the third book's rule is therefore computed from the counters themselves. Data step is the seconds after the minute at which the data step finished: the median of the heartbeat medians, and the largest heartbeat maximum.

### Spot (main)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 261, btc_stale 464, candle_old 889, newest_absent 1,046 |
| 2026-11-12 | 1,110 | 37 | 9.6 | 12.6 | btc_candle_old 766, btc_stale 867, candle_old 2,213, newest_absent 2,019 |
| Total | 1,685 | 57 | 9.6 | 13.1 | btc_candle_old 1,027, btc_stale 1,331, candle_old 3,102, newest_absent 3,065 |

130 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot W2

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 411, btc_stale 464, candle_old 1,919, newest_absent 1,046 |
| 2026-11-12 | 1,110 | 37 | 9.6 | 12.6 | btc_candle_old 695, btc_stale 867, candle_old 2,044, newest_absent 2,019 |
| Total | 1,685 | 57 | 9.6 | 13.1 | btc_candle_old 1,106, btc_stale 1,331, candle_old 3,963, newest_absent 3,065 |

126 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot TB (trades input)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 1,273 | 43 | 10.2 | 23.9 | btc_candle_old 159, candle_old 182, newest_absent 1,336, rows_open 3, skip_old 96, tb_built 7,428, tb_close_diff 422, tb_insert 741, tb_rebuilt 5 |
| 2026-11-12 | 1,108 | 37 | 9.9 | 17.0 | btc_candle_old 391, candle_old 387, newest_absent 1,317, rows_open 11, skip_old 190, tb_built 6,468, tb_close_diff 356, tb_insert 620, tb_rebuilt 11 |
| Total | 2,381 | 80 | 10.0 | 23.9 | btc_candle_old 550, candle_old 569, newest_absent 2,653, rows_open 14, skip_old 286, tb_built 13,896, tb_close_diff 778, tb_insert 1,361, tb_rebuilt 16 |

### Spot T18 (all coins on trades)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 65 | 3 | 13.8 | 17.5 | btc_candle_old 3, candle_old 17, newest_absent 4, tb_built 1,112, tb_close_diff 84, tb_dropped 4, tb_empty 4, tb_insert 13, tb_rebuilt 7, tb_replaced 1,095, tb_replaced_diff 125 |
| 2026-11-12 | 960 | 32 | 13.5 | 19.4 | btc_candle_old 23, candle_old 329, newest_absent 434, tb_built 16,321, tb_close_diff 747, tb_dropped 623, tb_empty 436, tb_fb_budget 1, tb_insert 856, tb_pending 31, tb_rebuilt 39, tb_replaced 15,684, tb_replaced_diff 2,792 |
| Total | 1,025 | 35 | 13.5 | 19.4 | btc_candle_old 26, candle_old 346, newest_absent 438, tb_built 17,433, tb_close_diff 831, tb_dropped 627, tb_empty 440, tb_fb_budget 1, tb_insert 869, tb_pending 31, tb_rebuilt 46, tb_replaced 16,779, tb_replaced_diff 2,917 |

## Third book against the main book

Period both ran: 2026-11-11 01:47 UTC to 2026-11-12 18:30 UTC (40.7 calendar hours; 29.0 hours with both live).

| Measure | Spot (main) | Spot TB | TB minus main |
|---|---|---|---|
| Rung fills | 12 | 2 | -10 |
| Rung fills per calendar day | 7.07 | 1.18 |  |
| Rung fills per running day | 9.91 | 1.18 |  |
| First-bid fills (rung 4) | 12 | 2 | -10 |
| Deeper rungs placed | 12 | 4 |  |
| Dollars bought | $25,961 | $20,884 | -$5,077 |
| Exit P&L | $151.95 | $141.06 | -$10.89 |
| Net per dollar bought | 58.5 bp | 67.5 bp | +9.0 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 1 |
| Only in the main book | 11 |
| Only in the third book | 1 |

This comparison is for the record. It is not the pass rule; the rule is below.

## Three-day rule progress for the third book

> Verified inputs (release 2): after the first three full days of real-time running (at least 4,000 minutes), items 1 to 7 below must all hold. The rule is in reports/owner/FORWARD_TESTS.md. Items 1 to 5 are computed here from the heartbeats; the values are provisional until the minutes are reached.

Real-time minutes run so far: 2,439 of 4,000 (61%).

Listed coins for item 1: BTC, ETH, SOL, XRP, LTC, ZEC (read from bot/spot/config.tb.json).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 100.00% (13,896 verified of 13,896 attempted coin-minutes: built 13,896, verified empty 0; fallbacks: unverified 0, error 0, budget 0, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.0 s of 80 heartbeats; maximum 20 s or less in 98.8% (largest 23.9 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.033% (14 of 42,858 coin-minutes, 18 coins) | meets |
| 6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day | from the forward collector; computed at the read by scripts/owner/tb_rule6.py | not computed here |
| 7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both | from the reconciliation (scripts/owner/reconcile); not computed here | not computed here |

## Fourth book against the third book

Period both ran: 2026-11-11 22:25 UTC to 2026-11-12 15:30 UTC (17.1 calendar hours; 17.0 hours with both live).

| Measure | Spot TB | Spot T18 | T18 minus TB |
|---|---|---|---|
| Rung fills | 2 | 2 | +0 |
| Rung fills per calendar day | 2.81 | 2.81 |  |
| Rung fills per running day | 2.82 | 2.81 |  |
| First-bid fills (rung 4) | 2 | 2 | +0 |
| Deeper rungs placed | 4 | 4 |  |
| Dollars bought | $20,884 | $20,884 | $0.00 |
| Exit P&L | $141.06 | $141.06 | $0.00 |
| Net per dollar bought | 67.5 bp | 67.5 bp | +0.0 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 2 |
| Only in the third book | 0 |
| Only in the fourth book | 0 |

This comparison is for the record. The registered read is in reports/owner/bar_source_prereg.md.

## Rule progress for the fourth book

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-12T10:07:06Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: 1,025.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.99% (17,873 verified of 17,874 attempted coin-minutes: built 17,433, verified empty 440; fallbacks: unverified 0, error 0, budget 1, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.5 s of 35 heartbeats; maximum 20 s or less in 100.0% (largest 19.4 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 18,450 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 31 of 18,450 coin-minutes

Totals: tb_replaced 16,779, tb_replaced_diff 2,917, tb_dropped 627.

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 3 | 0.48 | 0.73 | 65.7 bp | $10,046 | +0.46% | 32,477 |
| Perp R2-08 | 3 | 0.51 | 0.78 | 33.0 bp | $10,023 | +0.23% | 30,256 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
