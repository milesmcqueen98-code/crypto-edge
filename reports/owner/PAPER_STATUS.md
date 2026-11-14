# Paper trading status

Report made 2026-11-14 20:30 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-14 17:19 UTC | 3.2 h ago | ok |
| Spot W2 | 2026-11-14 17:19 UTC | 3.2 h ago | ok |
| Spot TB (trades input) | 2026-11-14 17:19 UTC | 3.2 h ago | ok |
| Spot T18 (all coins on trades) | 2026-11-14 20:30 UTC | 0.0 h ago | ok |
| Perp v1 (control) | 2026-11-14 17:46 UTC | 2.7 h ago | ok |
| Perp R2-08 | 2026-11-14 17:46 UTC | 2.7 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-14 17:19 UTC | 186.8 | 142.2 | 76.1% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-14 17:19 UTC | 184.6 | 140.0 | 75.8% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-14 17:19 UTC | 87.5 | 87.4 | 99.9% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-14 20:30 UTC | 70.1 | 70.1 | 100.0% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-14 17:46 UTC | 195.2 | 144.1 | 73.8% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-14 17:46 UTC | 187.0 | 138.3 | 74.0% |

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
| Spot TB (trades input) | 2026-11-13 17:59 UTC | 0.0 |
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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 3.2 h; Spot W2 3.2 h; Spot TB (trades input) 3.2 h; Spot T18 (all coins on trades) 0.0 h; Perp v1 (control) 2.7 h; Perp R2-08 2.7 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 7.8 | $251,603 | +0.64% | 62 | $353,331 | 45.4 bp | 50 / 21 | 29 (22 made money) | 1 |
| Spot W2 | 7.7 | $251,372 | +0.55% | 60 | $296,745 | 46.2 bp | 49 / 21 | 31 (24 made money) | 1 |
| Spot TB (trades input) | 3.6 | $250,559 | +0.22% | 42 | $265,126 | 21.1 bp | 15 / 8 | 11 (8 made money) | 0 |
| Spot T18 (all coins on trades) | 2.9 | $251,397 | +0.56% | 43 | $269,539 | 51.8 bp | 20 / 16 | 22 (18 made money) | 0 |
| Perp v1 (control) | 8.1 | $10,062 | +0.62% | 7 | n/a (not logged) | n/a | 2 / 4 | - | 0 |
| Perp R2-08 | 7.8 | $10,088 | +0.88% | 6 | n/a (not logged) | n/a | 3 / 3 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

| Measure | So far |
|---|---|
| Days (calendar) | 7.8 of 21 |
| Days in real time | 5.9 |
| Rungs | 62 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 7.97 per calendar day; 10.47 per running day |
| Mean net per dollar | 45.4 bp |
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
| 4 | 49 | $267,111 | 59 | $1,087 | 40.7 bp |
| 6 | 12 | $79,624 | 10 | $426.17 | 53.5 bp |
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
| 2026-11-12 | $147.69 | 24.0 |
| 2026-11-13 | $155.68 | 24.0 |
| 2026-11-14 | -$245.25 | 17.3 |

Cash shortfalls: 11. Wanted $115,534 in total (average $10,503) against an average of $1,308 free.

Share of capital held by resting bids (committed over equity, mean of 279 heartbeats): 58.36%.

Largest single-day loss so far: -$245.25 on 2026-11-14.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 7.8 | 7.7 | -0.1 |
| Hours in real time | 142.2 | 140.0 |  |
| Equity | $251,603 | $251,372 | -$230.66 |
| Change | +0.64% | +0.55% | -0.09 pp |
| Rung fills | 62 | 60 | -2 |
| Rung fills per calendar day | 7.97 | 7.80 |  |
| Rung fills per running day | 10.47 | 10.29 |  |
| Dollars bought | $353,331 | $296,745 | -$56,586 |
| Net per dollar | 45.4 bp | 46.2 bp | +0.9 bp |
| Exit events TP / time | 50 / 21 | 49 / 21 |  |
| Ladders closed (made money) | 29 (22) | 31 (24) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): -$230.66.

A few days and a few dozen fills cannot separate the two weightings; a gap this size is within what chance alone produces.

## Data quality

From the heartbeats of each spot book (one every 30 minutes while it runs). Counters are summed per UTC day; a counter that is not listed was 0 or is not reported. Minutes run are the 30 minutes before each heartbeat, less any gap. After a start-up the first heartbeat covers fewer stepped minutes than that, so minutes run can overstate the steps by a few minutes per run; item 1 of the third book's rule is therefore computed from the counters themselves. Data step is the seconds after the minute at which the data step finished: the median of the heartbeat medians, and the largest heartbeat maximum.

### Spot (main)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 261, btc_stale 464, candle_old 889, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 923, btc_stale 1,023, candle_old 2,624, newest_absent 2,439 |
| 2026-11-13 | 1,408 | 47 | 10.1 | 14.9 | btc_candle_old 1,092, btc_stale 1,302, candle_old 2,499, newest_absent 3,287 |
| 2026-11-14 | 1,050 | 35 | 9.3 | 23.2 | btc_candle_old 648, btc_stale 825, candle_old 6,687, newest_absent 2,674 |
| Total | 4,443 | 149 | 9.6 | 23.2 | btc_candle_old 2,924, btc_stale 3,614, candle_old 12,699, newest_absent 9,446 |

130 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot W2

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 411, btc_stale 464, candle_old 1,919, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 893, btc_stale 1,023, candle_old 2,666, newest_absent 2,439 |
| 2026-11-13 | 1,408 | 47 | 10.1 | 14.9 | btc_candle_old 1,122, btc_stale 1,302, candle_old 2,663, newest_absent 3,287 |
| 2026-11-14 | 1,050 | 35 | 9.3 | 28.1 | btc_candle_old 622, btc_stale 825, candle_old 7,127, newest_absent 2,674 |
| Total | 4,443 | 149 | 9.6 | 28.1 | btc_candle_old 3,048, btc_stale 3,614, candle_old 14,375, newest_absent 9,446 |

126 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot TB (trades input)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 1,273 | 43 | 10.2 | 23.9 | btc_candle_old 159, candle_old 182, newest_absent 1,336, rows_open 3, skip_old 96, tb_built 7,428, tb_close_diff 422, tb_insert 741, tb_rebuilt 5 |
| 2026-11-12 | 1,408 | 47 | 10.1 | 17.0 | btc_candle_old 399, candle_old 387, newest_absent 1,662, rows_open 11, skip_old 190, tb_built 8,202, tb_close_diff 440, tb_insert 909, tb_rebuilt 11 |
| 2026-11-13 | 1,379 | 46 | 9.9 | 18.5 | btc_candle_old 571, candle_old 838, newest_absent 1,050, rows_open 1, skip_old 456, tb_built 8,046, tb_close_diff 491, tb_insert 939, tb_rebuilt 15 |
| 2026-11-14 | 1,050 | 35 | 10.4 | 28.4 | btc_candle_old 343, candle_old 155, newest_absent 858, rows_open 1, skip_old 75, tb_built 6,060, tb_close_diff 306, tb_insert 508, tb_rebuilt 5 |
| Total | 5,110 | 171 | 10.2 | 28.4 | btc_candle_old 1,472, candle_old 1,562, newest_absent 4,906, rows_open 16, skip_old 817, tb_built 29,736, tb_close_diff 1,659, tb_insert 3,097, tb_rebuilt 36 |

### Spot T18 (all coins on trades)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 65 | 3 | 13.8 | 17.5 | btc_candle_old 3, candle_old 17, newest_absent 4, tb_built 1,112, tb_close_diff 84, tb_dropped 4, tb_empty 4, tb_insert 13, tb_rebuilt 7, tb_replaced 1,095, tb_replaced_diff 125 |
| 2026-11-12 | 1,410 | 47 | 13.5 | 19.4 | btc_candle_old 58, candle_old 727, newest_absent 553, tb_built 23,888, tb_close_diff 1,133, tb_dropped 815, tb_empty 555, tb_fb_budget 1, tb_insert 1,138, tb_pending 35, tb_rebuilt 52, tb_replaced 23,032, tb_replaced_diff 3,927 |
| 2026-11-13 | 1,410 | 47 | 13.4 | 20.9 | btc_candle_old 438, candle_old 638, newest_absent 280, tb_built 24,304, tb_close_diff 1,049, tb_dropped 521, tb_empty 280, tb_fb_budget 3, tb_fb_unverified 1, tb_insert 1,219, tb_pending 78, tb_rebuilt 40, tb_replaced 23,747, tb_replaced_diff 3,493 |
| 2026-11-14 | 1,230 | 41 | 12.5 | 23.4 | btc_candle_old 157, candle_old 220, newest_absent 371, tb_built 21,076, tb_close_diff 744, tb_dropped 473, tb_empty 369, tb_fb_budget 28, tb_fb_unverified 1, tb_insert 1,178, tb_pending 30, tb_rebuilt 14, tb_replaced 20,555, tb_replaced_diff 2,988 |
| Total | 4,115 | 138 | 13.4 | 23.4 | btc_candle_old 656, candle_old 1,602, newest_absent 1,208, tb_built 70,380, tb_close_diff 3,010, tb_dropped 1,813, tb_empty 1,208, tb_fb_budget 32, tb_fb_unverified 2, tb_insert 3,548, tb_pending 143, tb_rebuilt 113, tb_replaced 68,429, tb_replaced_diff 10,533 |

## Third book against the main book

Period both ran: 2026-11-11 01:47 UTC to 2026-11-14 17:19 UTC (87.5 calendar hours; 75.7 hours with both live).

| Measure | Spot (main) | Spot TB | TB minus main |
|---|---|---|---|
| Rung fills | 41 | 42 | +1 |
| Rung fills per calendar day | 11.24 | 11.52 |  |
| Rung fills per running day | 12.98 | 11.53 |  |
| First-bid fills (rung 4) | 36 | 39 | +3 |
| Deeper rungs placed | 46 | 36 |  |
| Dollars bought | $163,143 | $265,126 | $101,983 |
| Exit P&L | $62.38 | $558.87 | $496.49 |
| Net per dollar bought | 3.8 bp | 21.1 bp | +17.3 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 17 |
| Only in the main book | 19 |
| Only in the third book | 22 |

This comparison is for the record. It is not the pass rule; the rule is below.

## Three-day rule progress for the third book

> Verified inputs (release 2): after the first three full days of real-time running (at least 4,000 minutes), items 1 to 7 below must all hold. The rule is in reports/owner/FORWARD_TESTS.md. Items 1 to 5 are computed here from the heartbeats; the values are provisional until the minutes are reached.

Real-time minutes run so far: 5,246 of 4,000 (131%).

Listed coins for item 1: BTC, ETH, SOL, XRP, LTC, ZEC (read from bot/spot/config.tb.json).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 100.00% (29,736 verified of 29,736 attempted coin-minutes: built 29,736, verified empty 0; fallbacks: unverified 0, error 0, budget 0, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.2 s of 171 heartbeats; maximum 20 s or less in 98.8% (largest 28.4 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.017% (16 of 91,980 coin-minutes, 18 coins) | meets |
| 6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day | from the forward collector; computed at the read by scripts/owner/tb_rule6.py | not computed here |
| 7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both | from the reconciliation (scripts/owner/reconcile); not computed here | not computed here |

## Fourth book against the third book

Period both ran: 2026-11-11 22:25 UTC to 2026-11-14 17:19 UTC (66.9 calendar hours; 66.8 hours with both live).

| Measure | Spot TB | Spot T18 | T18 minus TB |
|---|---|---|---|
| Rung fills | 42 | 43 | +1 |
| Rung fills per calendar day | 15.07 | 15.43 |  |
| Rung fills per running day | 15.08 | 15.43 |  |
| First-bid fills (rung 4) | 39 | 40 | +1 |
| Deeper rungs placed | 36 | 38 |  |
| Dollars bought | $265,126 | $269,539 | $4,413 |
| Exit P&L | $558.87 | $590.65 | $31.78 |
| Net per dollar bought | 21.1 bp | 21.9 bp | +0.8 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 39 |
| Only in the third book | 0 |
| Only in the fourth book | 1 |

This comparison is for the record. The registered read is in reports/owner/bar_source_prereg.md.

## Rule progress for the fourth book

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-14T14:39:45Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: 4,205.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.95% (71,588 verified of 71,622 attempted coin-minutes: built 70,380, verified empty 1,208; fallbacks: unverified 2, error 0, budget 32, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.4 s of 138 heartbeats; maximum 20 s or less in 97.8% (largest 23.4 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 74,070 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 143 of 74,070 coin-minutes

Totals: tb_replaced 68,429, tb_replaced_diff 10,533, tb_dropped 1,813.

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 7 | 0.86 | 1.17 | 54.7 bp | $10,062 | +0.62% | 47,567 |
| Perp R2-08 | 6 | 0.77 | 1.04 | 64.6 bp | $10,088 | +0.88% | 45,358 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
