# Paper trading status

Report made 2026-11-20 22:40 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-20 19:18 UTC | 3.4 h ago | ok |
| Spot W2 | 2026-11-20 19:18 UTC | 3.4 h ago | ok |
| Spot TB (trades input) | 2026-11-16 21:30 UTC | 97.2 h ago | ended |
| Spot T18 (all coins on trades) | 2026-11-20 22:30 UTC | 0.2 h ago | ok |
| Spot R5 (release 5 build) | 2026-11-20 22:30 UTC | 0.2 h ago | ok |
| Spot TW (trades side by side) | 2026-11-20 21:41 UTC | 1.0 h ago | ok |
| Perp v1 (control) | 2026-11-20 19:49 UTC | 2.9 h ago | ok |
| Perp R2-08 | 2026-11-20 19:49 UTC | 2.9 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old. A book marked ended (Spot TB (trades input): 2026-11-16) is never flagged STALE.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-20 19:18 UTC | 332.8 | 288.1 | 86.6% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-20 19:18 UTC | 330.6 | 285.9 | 86.5% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-16 21:30 UTC | 139.7 | 139.5 | 99.9% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-20 22:30 UTC | 216.1 | 216.1 | 100.0% |
| Spot R5 (release 5 build) | 2026-11-16 18:39 UTC | 2026-11-20 22:30 UTC | 99.8 | 99.8 | 100.0% |
| Spot TW (trades side by side) | 2026-11-16 23:37 UTC | 2026-11-20 21:41 UTC | 94.1 | 94.1 | 100.0% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-20 19:49 UTC | 341.2 | 288.1 | 84.4% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-20 19:49 UTC | 333.1 | 282.3 | 84.8% |

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
| Spot TB (trades input) | 2026-11-14 17:19 UTC | 0.0 |
| Spot TB (trades input) | 2026-11-15 22:33 UTC | 0.0 |
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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 3.4 h; Spot W2 3.4 h; Spot T18 (all coins on trades) 0.2 h; Spot R5 (release 5 build) 0.2 h; Spot TW (trades side by side) 1.0 h; Perp v1 (control) 2.9 h; Perp R2-08 2.9 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 13.9 | $249,737 | -0.11% | 119 | $841,207 | -3.1 bp | 85 / 62 | 64 (39 made money) | 1 |
| Spot W2 | 13.8 | $249,980 | -0.01% | 117 | $726,890 | -0.3 bp | 77 / 62 | 66 (42 made money) | 1 |
| Spot TB (trades input) | 5.8 | $249,964 | -0.01% | 70 | $537,290 | -0.7 bp | 33 / 35 | 37 (22 made money) | 0 |
| Spot T18 (all coins on trades) | 9.0 | $249,040 | -0.38% | 124 | $877,835 | -10.9 bp | 49 / 58 | 56 (35 made money) | 0 |
| Spot R5 (release 5 build) | 4.2 | $249,271 | -0.29% | 52 | $338,973 | -21.5 bp | 19 / 23 | 18 (12 made money) | 0 |
| Spot TW (trades side by side) | 3.9 | $249,269 | -0.29% | 52 | $338,975 | -21.6 bp | 19 / 23 | 18 (12 made money) | 0 |
| Perp v1 (control) | 14.2 | $10,176 | +1.76% | 14 | n/a (not logged) | n/a | 5 / 9 | - | 0 |
| Perp R2-08 | 13.9 | $10,117 | +1.17% | 12 | n/a (not logged) | n/a | 4 / 8 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

Rule A is counted from 2026-11-14 17:27 UTC; see the section below.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

Counted from 2026-11-14 17:27 UTC (release 3): the main book's inputs changed then. The registered rule is counted again from that time (reports/owner/FORWARD_TESTS.md).

| Measure | So far |
|---|---|
| Days (calendar) | 6.1 of 21 |
| Days in real time | 6.1 |
| Rungs | 57 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 9.38 per calendar day; 9.38 per running day |
| Mean net per dollar | -50.3 bp |
| Errors (total) | 0 |
| Explained | 0 |
| Unexplained | 0 |

Status: **CHECK**

CHECK means unexplained errors are present or net is at or below 0. NOT YET means the 3 weeks and 60 rungs are not reached. ON TRACK means both are reached with no unexplained errors and net above 0. The owner declares any pass.

### Before 2026-11-14 17:27 UTC, kept apart

| Measure | Before |
|---|---|
| Days (calendar, first event to start) | 7.8 |
| Rungs bought | 62 |
| Dollars bought | $353,331 |
| Mean net per dollar (exits after the start included) | 62.0 bp |
| Errors | 1 |
| Unexplained | 0 |

## Spot book detail

Fills and net per dollar by rung:

| Rung | Fills | Dollars bought | Exit events | Exit P&L | Net per dollar |
|---|---|---|---|---|---|
| 4 | 82 | $577,552 | 108 | -$706.09 | -12.2 bp |
| 6 | 28 | $195,755 | 31 | $704.73 | 36.0 bp |
| 8 | 9 | $67,900 | 8 | -$261.49 | -38.5 bp |

P&L of exits by day, last 14 days:

| Day (UTC) | Exit P&L | Hours running |
|---|---|---|
| 2026-11-07 | -$3.06 | 18.0 |
| 2026-11-08 | $1,305 | 17.8 |
| 2026-11-09 | $238.52 | 12.9 |
| 2026-11-10 | $0.00 | 14.4 |
| 2026-11-11 | $4.26 | 12.3 |
| 2026-11-12 | $147.69 | 24.0 |
| 2026-11-13 | $155.68 | 24.0 |
| 2026-11-14 | -$781.37 | 24.0 |
| 2026-11-15 | $0.00 | 24.0 |
| 2026-11-16 | $0.00 | 24.0 |
| 2026-11-17 | $4.53 | 24.0 |
| 2026-11-18 | -$98.77 | 24.0 |
| 2026-11-19 | $16.59 | 24.0 |
| 2026-11-20 | -$1,252 | 19.3 |

Cash shortfalls: 31. Wanted $214,854 in total (average $6,931) against an average of $466.74 free.

Share of capital held by resting bids (committed over equity, mean of 568 heartbeats): 58.32%.

Largest single-day loss so far: -$1,252 on 2026-11-20.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 13.9 | 13.8 | -0.1 |
| Hours in real time | 288.1 | 285.9 |  |
| Equity | $249,737 | $249,980 | $242.52 |
| Change | -0.11% | -0.01% | +0.10 pp |
| Rung fills | 119 | 117 | -2 |
| Rung fills per calendar day | 8.58 | 8.49 |  |
| Rung fills per running day | 9.91 | 9.82 |  |
| Dollars bought | $841,207 | $726,890 | -$114,317 |
| Net per dollar | -3.1 bp | -0.3 bp | +2.8 bp |
| Exit events TP / time | 85 / 62 | 77 / 62 |  |
| Ladders closed (made money) | 64 (39) | 66 (42) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): $242.52.

A few days and a few dozen fills cannot separate the two weightings; a gap this size is within what chance alone produces.

## Data quality

From the heartbeats of each spot book (one every 30 minutes while it runs). Counters are summed per UTC day; a counter that is not listed was 0 or is not reported. Minutes run are the 30 minutes before each heartbeat, less any gap. After a start-up the first heartbeat covers fewer stepped minutes than that, so minutes run can overstate the steps by a few minutes per run; item 1 of the third book's rule is therefore computed from the counters themselves. Data step is the seconds after the minute at which the data step finished: the median of the heartbeat medians, and the largest heartbeat maximum.

### Spot (main)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 261, btc_stale 464, candle_old 889, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 923, btc_stale 1,023, candle_old 2,624, newest_absent 2,439 |
| 2026-11-13 | 1,408 | 47 | 10.1 | 14.9 | btc_candle_old 1,092, btc_stale 1,302, candle_old 2,499, newest_absent 3,287 |
| 2026-11-14 | 1,440 | 48 | 9.5 | 23.2 | btc_candle_old 695, btc_stale 825, candle_old 6,943, newest_absent 2,769, skip_old 178, tb_built 1,740, tb_close_diff 124, tb_fb_budget 12, tb_fb_unverified 3, tb_insert 69, tb_rebuilt 5 |
| 2026-11-15 | 1,440 | 48 | 11.1 | 22.0 | btc_candle_old 455, candle_old 987, newest_absent 1,122, skip_old 644, tb_built 6,898, tb_close_diff 433, tb_empty 3, tb_fb_budget 7, tb_fb_error 1, tb_fb_unverified 1, tb_insert 651, tb_rebuilt 5 |
| 2026-11-16 | 1,380 | 46 | 10.9 | 20.8 | btc_candle_old 477, candle_old 739, newest_absent 1,452, skip_old 433, tb_built 6,745, tb_close_diff 327, tb_insert 920, tb_rebuilt 7 |
| 2026-11-17 | 1,410 | 47 | 11.2 | 18.6 | btc_candle_old 370, btc_stale 2, candle_old 2,008, newest_absent 1,644, rows_open 7, skip_old 1,292, tb_built 6,603, tb_close_diff 784, tb_empty 165, tb_fb_error 2, tb_insert 549, tb_rebuilt 4 |
| 2026-11-18 | 1,440 | 48 | 11.1 | 14.8 | btc_candle_old 516, candle_old 1,488, newest_absent 2,069, rows_open 14, skip_old 1,026, tb_built 6,924, tb_close_diff 707, tb_fb_unverified 1, tb_insert 650, tb_rebuilt 9 |
| 2026-11-19 | 1,440 | 48 | 11.0 | 15.7 | btc_candle_old 507, candle_old 1,409, newest_absent 1,819, rows_open 8, skip_old 833, tb_built 6,938, tb_close_diff 744, tb_empty 2, tb_insert 841, tb_rebuilt 13 |
| 2026-11-20 | 1,170 | 39 | 9.7 | 15.2 | btc_candle_old 804, candle_old 790, newest_absent 1,082, rows_open 37, skip_old 339, tb_built 5,639, tb_close_diff 193, tb_fb_unverified 1, tb_insert 1,422, tb_rebuilt 9 |
| Total | 13,113 | 438 | 10.3 | 23.2 | btc_candle_old 6,100, btc_stale 3,616, candle_old 20,376, newest_absent 18,729, rows_open 66, skip_old 4,745, tb_built 41,487, tb_close_diff 3,312, tb_empty 170, tb_fb_budget 19, tb_fb_error 3, tb_fb_unverified 6, tb_insert 5,102, tb_rebuilt 52 |

130 earlier heartbeat(s) carry none of these fields and are not counted.

Heartbeats with a trades error (tb_err): 2. Last: BTC: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

### Spot W2

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 411, btc_stale 464, candle_old 1,919, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 893, btc_stale 1,023, candle_old 2,666, newest_absent 2,439 |
| 2026-11-13 | 1,408 | 47 | 10.1 | 14.9 | btc_candle_old 1,122, btc_stale 1,302, candle_old 2,663, newest_absent 3,287 |
| 2026-11-14 | 1,440 | 48 | 9.5 | 28.1 | btc_candle_old 670, btc_stale 825, candle_old 7,408, newest_absent 2,769, skip_old 193, tb_built 1,740, tb_close_diff 124, tb_fb_budget 12, tb_fb_unverified 3, tb_insert 69, tb_rebuilt 3 |
| 2026-11-15 | 1,440 | 48 | 11.1 | 25.4 | btc_candle_old 473, candle_old 995, newest_absent 1,122, skip_old 644, tb_built 6,901, tb_close_diff 433, tb_empty 3, tb_fb_budget 4, tb_fb_error 1, tb_fb_unverified 1, tb_insert 651, tb_rebuilt 3 |
| 2026-11-16 | 1,380 | 46 | 10.9 | 17.2 | btc_candle_old 556, candle_old 817, newest_absent 1,452, skip_old 461, tb_built 6,745, tb_close_diff 327, tb_insert 920, tb_rebuilt 9 |
| 2026-11-17 | 1,410 | 47 | 11.1 | 18.6 | btc_candle_old 420, btc_stale 2, candle_old 2,125, newest_absent 1,644, rows_open 6, skip_old 1,349, tb_built 6,603, tb_close_diff 784, tb_empty 165, tb_fb_error 2, tb_insert 549, tb_rebuilt 4 |
| 2026-11-18 | 1,440 | 48 | 11.1 | 14.8 | btc_candle_old 491, candle_old 1,460, newest_absent 2,069, rows_open 12, skip_old 994, tb_built 6,924, tb_close_diff 707, tb_fb_unverified 1, tb_insert 650, tb_rebuilt 11 |
| 2026-11-19 | 1,440 | 48 | 11.0 | 15.7 | btc_candle_old 559, candle_old 1,365, newest_absent 1,819, rows_open 8, skip_old 791, tb_built 6,938, tb_close_diff 744, tb_empty 2, tb_insert 841, tb_rebuilt 11 |
| 2026-11-20 | 1,170 | 39 | 9.7 | 15.2 | btc_candle_old 795, candle_old 831, newest_absent 1,082, rows_open 36, skip_old 342, tb_built 5,639, tb_close_diff 193, tb_fb_unverified 1, tb_insert 1,422, tb_rebuilt 11 |
| Total | 13,113 | 438 | 10.3 | 28.1 | btc_candle_old 6,390, btc_stale 3,616, candle_old 22,249, newest_absent 18,729, rows_open 62, skip_old 4,774, tb_built 41,490, tb_close_diff 3,312, tb_empty 170, tb_fb_budget 16, tb_fb_error 3, tb_fb_unverified 6, tb_insert 5,102, tb_rebuilt 52 |

126 earlier heartbeat(s) carry none of these fields and are not counted.

Heartbeats with a trades error (tb_err): 2. Last: BTC: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

### Spot TB (trades input)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 1,273 | 43 | 10.2 | 23.9 | btc_candle_old 159, candle_old 182, newest_absent 1,336, rows_open 3, skip_old 96, tb_built 7,428, tb_close_diff 422, tb_insert 741, tb_rebuilt 5 |
| 2026-11-12 | 1,408 | 47 | 10.1 | 17.0 | btc_candle_old 399, candle_old 387, newest_absent 1,662, rows_open 11, skip_old 190, tb_built 8,202, tb_close_diff 440, tb_insert 909, tb_rebuilt 11 |
| 2026-11-13 | 1,379 | 46 | 9.9 | 18.5 | btc_candle_old 571, candle_old 838, newest_absent 1,050, rows_open 1, skip_old 456, tb_built 8,046, tb_close_diff 491, tb_insert 939, tb_rebuilt 15 |
| 2026-11-14 | 1,438 | 48 | 11.2 | 28.4 | btc_candle_old 352, candle_old 203, newest_absent 949, rows_open 1, skip_old 105, tb_built 8,141, tb_close_diff 455, tb_fb_budget 16, tb_fb_unverified 3, tb_insert 575, tb_rebuilt 5 |
| 2026-11-15 | 1,438 | 48 | 11.0 | 18.3 | btc_candle_old 373, btc_stale 1, candle_old 547, newest_absent 1,073, skip_old 341, tb_built 8,283, tb_close_diff 332, tb_empty 3, tb_fb_budget 11, tb_fb_unverified 1, tb_insert 1,053, tb_rebuilt 6 |
| 2026-11-16 | 1,288 | 43 | 10.7 | 20.9 | btc_candle_old 75, candle_old 625, newest_absent 1,339, skip_old 387, tb_built 7,560, tb_close_diff 313, tb_insert 861, tb_rebuilt 4 |
| Total | 8,224 | 275 | 10.5 | 28.4 | btc_candle_old 1,929, btc_stale 1, candle_old 2,782, newest_absent 7,409, rows_open 16, skip_old 1,575, tb_built 47,660, tb_close_diff 2,453, tb_empty 3, tb_fb_budget 27, tb_fb_unverified 4, tb_insert 5,078, tb_rebuilt 46 |

### Spot T18 (all coins on trades)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 65 | 3 | 13.8 | 17.5 | btc_candle_old 3, candle_old 17, newest_absent 4, tb_built 1,112, tb_close_diff 84, tb_dropped 4, tb_empty 4, tb_insert 13, tb_rebuilt 7, tb_replaced 1,095, tb_replaced_diff 125 |
| 2026-11-12 | 1,410 | 47 | 13.5 | 19.4 | btc_candle_old 58, candle_old 727, newest_absent 553, tb_built 23,888, tb_close_diff 1,133, tb_dropped 815, tb_empty 555, tb_fb_budget 1, tb_insert 1,138, tb_pending 35, tb_rebuilt 52, tb_replaced 23,032, tb_replaced_diff 3,927 |
| 2026-11-13 | 1,410 | 47 | 13.4 | 20.9 | btc_candle_old 438, candle_old 638, newest_absent 280, tb_built 24,304, tb_close_diff 1,049, tb_dropped 521, tb_empty 280, tb_fb_budget 3, tb_fb_unverified 1, tb_insert 1,219, tb_pending 78, tb_rebuilt 40, tb_replaced 23,747, tb_replaced_diff 3,493 |
| 2026-11-14 | 1,410 | 47 | 13.3 | 23.4 | btc_candle_old 159, candle_old 275, newest_absent 378, skip_old 4, tb_built 24,017, tb_close_diff 915, tb_dropped 482, tb_empty 375, tb_fb_budget 247, tb_fb_unverified 3, tb_insert 1,203, tb_pending 31, tb_rebuilt 16, tb_replaced 23,471, tb_replaced_diff 3,098 |
| 2026-11-15 | 1,440 | 48 | 13.5 | 24.6 | btc_candle_old 289, btc_stale 2, candle_old 207, newest_absent 412, skip_old 1, tb_built 23,943, tb_close_diff 979, tb_dropped 601, tb_empty 390, tb_fb_budget 324, tb_fb_error 1, tb_fb_unverified 2, tb_insert 1,343, tb_pending 50, tb_rebuilt 48, tb_replaced 23,301, tb_replaced_diff 3,693 |
| 2026-11-16 | 1,440 | 48 | 14.0 | 35.6 | btc_candle_old 334, candle_old 664, newest_absent 646, skip_old 19, tb_built 23,883, tb_close_diff 739, tb_dropped 715, tb_empty 620, tb_fb_budget 319, tb_insert 1,766, tb_pending 68, tb_rebuilt 48, tb_replaced 23,132, tb_replaced_diff 4,096 |
| 2026-11-17 | 1,440 | 48 | 12.9 | 22.7 | btc_candle_old 250, btc_stale 2, candle_old 465, newest_absent 571, tb_built 23,626, tb_close_diff 1,096, tb_dropped 784, tb_empty 1,237, tb_fb_budget 27, tb_fb_error 4, tb_insert 2,127, tb_pending 70, tb_rebuilt 40, tb_replaced 23,453, tb_replaced_diff 4,119 |
| 2026-11-18 | 1,410 | 47 | 13.2 | 19.9 | btc_candle_old 46, candle_old 450, newest_absent 807, tb_built 23,517, tb_close_diff 1,991, tb_dropped 897, tb_empty 808, tb_fb_budget 10, tb_fb_error 1, tb_insert 1,346, tb_pending 86, tb_rebuilt 47, tb_replaced 22,575, tb_replaced_diff 4,124 |
| 2026-11-19 | 1,410 | 47 | 12.8 | 19.7 | btc_candle_old 187, candle_old 1,023, newest_absent 668, tb_built 23,360, tb_close_diff 1,238, tb_dropped 769, tb_empty 667, tb_fb_budget 21, tb_insert 2,111, tb_pending 63, tb_rebuilt 46, tb_replaced 22,521, tb_replaced_diff 3,947 |
| 2026-11-20 | 1,380 | 46 | 12.4 | 18.1 | btc_candle_old 601, candle_old 1,033, newest_absent 455, tb_built 23,621, tb_close_diff 1,111, tb_dropped 486, tb_empty 457, tb_fb_budget 6, tb_insert 1,806, tb_pending 333, tb_rebuilt 32, tb_replaced 23,105, tb_replaced_diff 2,960 |
| Total | 12,815 | 428 | 13.2 | 35.6 | btc_candle_old 2,365, btc_stale 4, candle_old 5,499, newest_absent 4,774, skip_old 24, tb_built 215,271, tb_close_diff 10,335, tb_dropped 6,074, tb_empty 5,393, tb_fb_budget 958, tb_fb_error 6, tb_fb_unverified 6, tb_insert 14,072, tb_pending 814, tb_rebuilt 376, tb_replaced 209,432, tb_replaced_diff 33,582 |

Heartbeats with a trades error (tb_err): 4. Last: ETH: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

### Spot R5 (release 5 build)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-16 | 291 | 10 | 8.6 | 16.3 | newest_absent 129, pre_fetched 4,662, pre_ondemand 10, step_candles 10, tb_built 4,550, tb_dropped 135, tb_empty 128, tb_fb_budget 20, tb_pending 230, tb_rebuilt 19, tb_replaced 4,393, tb_replaced_diff 443 |
| 2026-11-17 | 1,440 | 48 | 8.6 | 16.5 | btc_candle_old 1, btc_stale 38, candle_old 1, newest_absent 1,199, pre_fetched 24,624, pre_ondemand 26, skip_old 1, step_candles 26, tb_built 23,434, tb_dropped 790, tb_empty 1,236, tb_fb_budget 23, tb_fb_error 3, tb_pending 1,528, tb_rebuilt 96, tb_replaced 22,623, tb_replaced_diff 3,169 |
| 2026-11-18 | 1,440 | 48 | 8.6 | 22.4 | newest_absent 812, pre_error 1, pre_fetched 24,713, pre_missing 1, pre_ondemand 17, step_candles 18, tb_built 23,958, tb_dropped 898, tb_empty 811, tb_fb_budget 17, tb_pending 709, tb_rebuilt 88, tb_replaced 23,026, tb_replaced_diff 3,037 |
| 2026-11-19 | 1,380 | 46 | 8.6 | 15.6 | newest_absent 695, pre_fetched 23,796, pre_ondemand 16, step_candles 16, tb_built 23,173, tb_dropped 775, tb_empty 697, tb_fb_budget 16, tb_pending 1,137, tb_rebuilt 79, tb_replaced 22,317, tb_replaced_diff 3,368 |
| 2026-11-20 | 1,350 | 45 | 8.7 | 17.3 | newest_absent 442, pre_error 2, pre_fetched 23,560, pre_missing 2, pre_ondemand 23, step_candles 25, tb_built 23,148, tb_dropped 470, tb_empty 442, tb_fb_budget 25, tb_fb_error 1, tb_pending 1,033, tb_rebuilt 46, tb_replaced 22,638, tb_replaced_diff 2,302 |
| Total | 5,901 | 197 | 8.6 | 22.4 | btc_candle_old 1, btc_stale 38, candle_old 1, newest_absent 3,277, pre_error 3, pre_fetched 101,355, pre_missing 3, pre_ondemand 92, skip_old 1, step_candles 95, tb_built 98,263, tb_dropped 3,068, tb_empty 3,314, tb_fb_budget 101, tb_fb_error 4, tb_pending 4,637, tb_rebuilt 328, tb_replaced 94,997, tb_replaced_diff 12,319 |

Left out for this book: tb_insert, tb_close_diff. With candle requests between steps (candles_at_s) the step has no candle row for the newest minute of a trades-built coin, so tb_insert counts nearly every trades bar and tb_close_diff is not measured for those coins; the counters are not comparable with the fourth book's and are not shown.

Heartbeats with a trades error (tb_err): 3. Last: ETH: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

### Spot TW (trades side by side)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-17 | 1,433 | 48 | 8.5 | 14.8 | btc_stale 38, newest_absent 1,209, pre_error 1, pre_fetched 24,461, pre_missing 1, pre_ondemand 5, step_candles 6, tb_built 23,297, tb_dropped 795, tb_empty 1,250, tb_fb_budget 3, tb_fb_error 2, tb_pending 1,555, tb_rebuilt 81, tb_replaced 22,444, tb_replaced_diff 3,531 |
| 2026-11-18 | 1,440 | 48 | 8.5 | 21.2 | btc_stale 1, newest_absent 821, pre_error 1, pre_fetched 24,641, pre_missing 1, pre_ondemand 18, step_candles 19, tb_built 23,893, tb_dropped 913, tb_empty 821, tb_fb_budget 18, tb_pending 1,197, tb_rebuilt 112, tb_replaced 22,919, tb_replaced_diff 3,508 |
| 2026-11-19 | 1,440 | 48 | 8.6 | 13.6 | newest_absent 701, pre_fetched 24,588, pre_ondemand 1, step_candles 1, tb_built 23,957, tb_dropped 771, tb_empty 702, tb_fb_error 1, tb_pending 1,295, tb_rebuilt 102, tb_replaced 23,187, tb_replaced_diff 2,800 |
| 2026-11-20 | 1,320 | 44 | 8.6 | 13.3 | newest_absent 448, pre_fetched 22,914, pre_ondemand 1, step_candles 1, tb_built 22,518, tb_dropped 472, tb_empty 448, tb_fb_error 1, tb_fb_unverified 1, tb_pending 1,605, tb_rebuilt 64, tb_replaced 21,984, tb_replaced_diff 3,227 |
| Total | 5,633 | 188 | 8.6 | 21.2 | btc_stale 39, newest_absent 3,179, pre_error 2, pre_fetched 96,604, pre_missing 2, pre_ondemand 25, step_candles 27, tb_built 93,665, tb_dropped 2,951, tb_empty 3,221, tb_fb_budget 21, tb_fb_error 4, tb_fb_unverified 1, tb_pending 5,652, tb_rebuilt 359, tb_replaced 90,534, tb_replaced_diff 13,066 |

Left out for this book: tb_insert, tb_close_diff. With candle requests between steps (candles_at_s) the step has no candle row for the newest minute of a trades-built coin, so tb_insert counts nearly every trades bar and tb_close_diff is not measured for those coins; the counters are not comparable with the fourth book's and are not shown.

Heartbeats with a trades error (tb_err): 3. Last: SOL: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

## Third book against the main book

The third book ended on 2026-11-16; this section is the final record.

Period both ran: 2026-11-11 01:47 UTC to 2026-11-16 21:30 UTC (139.7 calendar hours; 127.8 hours with both live).

| Measure | Spot (main) | Spot TB | TB minus main |
|---|---|---|---|
| Rung fills | 68 | 70 | +2 |
| Rung fills per calendar day | 11.68 | 12.02 |  |
| Rung fills per running day | 12.75 | 12.04 |  |
| First-bid fills (rung 4) | 52 | 55 | +3 |
| Deeper rungs placed | 59 | 56 |  |
| Dollars bought | $441,345 | $537,290 | $95,945 |
| Exit P&L | -$473.74 | -$35.65 | $438.09 |
| Net per dollar bought | -10.7 bp | -0.7 bp | +10.1 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 33 |
| Only in the main book | 19 |
| Only in the third book | 22 |

This comparison is for the record. It is not the pass rule; the rule is below.

## Three-day rule progress for the third book

The third book ended on 2026-11-16; this section is the final record.

> Verified inputs (release 2): after the first three full days of real-time running (at least 4,000 minutes), items 1 to 7 below must all hold. The rule is in reports/owner/FORWARD_TESTS.md. Items 1 to 5 are computed here from the heartbeats; the values are provisional until the minutes are reached.

Real-time minutes run so far: 8,371 of 4,000 (209%).

Listed coins for item 1: BTC, ETH, SOL, XRP, LTC, ZEC (read from bot/spot/config.tb.json).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.94% (47,663 verified of 47,694 attempted coin-minutes: built 47,660, verified empty 3; fallbacks: unverified 4, error 0, budget 27, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.5 s of 275 heartbeats; maximum 20 s or less in 98.9% (largest 28.4 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.011% (16 of 148,032 coin-minutes, 18 coins) | meets |
| 6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day | from the forward collector; computed at the read by scripts/owner/tb_rule6.py | not computed here |
| 7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both | from the reconciliation (scripts/owner/reconcile); not computed here | not computed here |

## Fourth book against the third book

The third book ended on 2026-11-16; this section is the final record.

Period both ran: 2026-11-11 22:25 UTC to 2026-11-16 21:30 UTC (119.1 calendar hours; 118.9 hours with both live).

| Measure | Spot TB | Spot T18 | T18 minus TB |
|---|---|---|---|
| Rung fills | 70 | 72 | +2 |
| Rung fills per calendar day | 14.11 | 14.51 |  |
| Rung fills per running day | 14.13 | 14.51 |  |
| First-bid fills (rung 4) | 55 | 58 | +3 |
| Deeper rungs placed | 56 | 56 |  |
| Dollars bought | $537,290 | $539,242 | $1,953 |
| Exit P&L | -$35.65 | -$229.50 | -$193.85 |
| Net per dollar bought | -0.7 bp | -4.3 bp | -3.6 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 55 |
| Only in the third book | 0 |
| Only in the fourth book | 3 |

This comparison is for the record. The registered read is in reports/owner/bar_source_prereg.md.

## Rule progress for the fourth book

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-20T16:41:50Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: 12,965.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.56% (220,664 verified of 221,634 attempted coin-minutes: built 215,271, verified empty 5,393; fallbacks: unverified 6, error 6, budget 958, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.2 s of 428 heartbeats; maximum 20 s or less in 96.5% (largest 35.6 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 230,670 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 814 of 230,670 coin-minutes

Totals: tb_replaced 209,432, tb_replaced_diff 33,582, tb_dropped 6,074.

## Fifth book against the fourth book

Period both ran: 2026-11-16 18:39 UTC to 2026-11-20 22:30 UTC (99.8 calendar hours; 99.8 hours with both live).

| Measure | Spot T18 | Spot R5 | R5 minus T18 |
|---|---|---|---|
| Rung fills | 52 | 52 | +0 |
| Rung fills per calendar day | 12.50 | 12.50 |  |
| Rung fills per running day | 12.50 | 12.50 |  |
| First-bid fills (rung 4) | 31 | 31 | +0 |
| Deeper rungs placed | 35 | 35 |  |
| Dollars bought | $338,593 | $338,973 | $380.48 |
| Exit P&L | -$730.50 | -$729.39 | $1.11 |
| Net per dollar bought | -21.6 bp | -21.5 bp | +0.1 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 31 |
| Only in the fourth book | 0 |
| Only in the fifth book | 0 |

This comparison is for the record. The registered read is Part 3 of reports/owner/bar_source_prereg.md.

## Rule progress for the fifth book

Engine commit: 815ea39 (full hash 815ea3900e9e74c59a451ea0c2365e49fa631cd2), recorded 2026-11-20T16:50:44Z UTC.

> The four measures of Part 3 of reports/owner/bar_source_prereg.md, read here on the whole log so far. This is progress only: the read is made once, on the period the plan defines, by scripts/owner/bar_source/part3_rule.py. Measure 2 (decisions against the research) is not computed here.

### Measure 1, the step

(a) Same-machine pairs: on one runner and the pinned commit, 30 minutes with release 3's inputs and 30 minutes with the build's, one after the other, the order alternating (scripts/owner/step_pairs/run_pair.py, step-pairs.yml). The measure is the median of the build's median data step minus release 3's over the pairs that count: at or below zero, at least 8 pairs. If fewer than 8 count in the period, the read also takes the later pairs, oldest first, up to the one that makes 8.

| Start | Order | Release 3 median | Build median | Build minus release 3 | Counts |
|---|---|---|---|---|---|
| 2026-11-16 19:27 UTC | ba | 11.24 s | 8.55 s | -2.69 s | counts |
| 2026-11-17 06:56 UTC | ba | 9.49 s | 8.46 s | -1.03 s | counts |
| 2026-11-17 20:33 UTC | ba | 9.78 s | 8.60 s | -1.18 s | counts |
| 2026-11-18 00:34 UTC | ab | 9.54 s | 8.47 s | -1.07 s | counts |
| 2026-11-18 06:18 UTC | ba | 9.74 s | 8.47 s | -1.27 s | counts |
| 2026-11-18 07:27 UTC | ba | 9.69 s | 8.49 s | -1.20 s | counts |
| 2026-11-18 12:15 UTC | ab | 11.04 s | 8.60 s | -2.44 s | counts |
| 2026-11-18 18:05 UTC | ba | 11.45 s | 8.65 s | -2.80 s | counts |
| 2026-11-18 20:05 UTC | ba | 9.84 s | 8.60 s | -1.24 s | counts |
| 2026-11-18 23:56 UTC | ba | 11.36 s | 8.61 s | -2.75 s | counts |
| 2026-11-19 05:47 UTC | ab | 11.18 s | 8.62 s | -2.56 s | counts |
| 2026-11-19 07:00 UTC | ba | 10.20 s | 8.50 s | -1.70 s | counts |
| 2026-11-19 11:37 UTC | ba | 10.88 s | 8.63 s | -2.25 s | counts |
| 2026-11-19 17:28 UTC | ab | 9.74 s | 8.60 s | -1.14 s | counts |
| 2026-11-19 20:04 UTC | ba | 9.78 s | 8.78 s | -1.00 s | counts |
| 2026-11-19 23:18 UTC | ba | 11.18 s | 8.60 s | -2.58 s | counts |
| 2026-11-20 05:08 UTC | ab | 11.28 s | 8.63 s | -2.65 s | counts |
| 2026-11-20 06:30 UTC | ba | 9.62 s | 8.46 s | -1.16 s | counts |
| 2026-11-20 10:59 UTC | ba | 9.79 s | 9.13 s | -0.66 s | counts |
| 2026-11-20 15:18 UTC | ab | 10.73 s | 9.03 s | -1.70 s | counts |
| 2026-11-20 16:50 UTC | ab | 11.69 s | 8.80 s | -2.89 s | counts |

| Part | Current value | Verdict |
|---|---|---|
| (a) Pairs that count, and the median of build minus release 3 | 21 pairs (8 needed); median -1.70 s; must be at or below 0.00 s | meets |

| Part | Current value | Verdict |
|---|---|---|
| (b) Against the main book, over the half hours both have a heartbeat (same heartbeat time) | fifth 8.63 s, main 10.98 s, 188 half hours; the fifth's must be no higher | meets |
| Reported, decides nothing: the fifth book's own median of its half-hour data-step medians | 8.63 s over 197 heartbeats; for comparison 10.3 s (release 3's figure of Nov 11 to 14, which moves with the period and the runner) | reported only |
| For information: against the fourth book, same way | fifth 8.63 s, fourth 13.07 s, 195 half hours | not part of the rule |

The read needs at least 100 heartbeats of the fifth book and at least 100 paired half hours with the main book for (b).

### Items 1 to 5 (measure 3)

Real-time minutes run so far: 5,991.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.90% (101,577 verified of 101,682 attempted coin-minutes: built 98,263, verified empty 3,314; fallbacks: unverified 0, error 4, budget 101, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step 30-minute maximum 20 s or less in 95% or more of heartbeats (the median is measure 1, see below) | median 8.6 s of 197 heartbeats; maximum 20 s or less in 99.5% (largest 22.4 s); the median is judged as measure 1 | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 106,218 coin-minutes, 18 coins) | meets |

### Measure 4, the candle requests between steps

| Part | Current value | Verdict |
|---|---|---|
| Counters, summed over the log | pre_fetched 101,355, pre_error 3, pre_missing 3, pre_ondemand 92, step_candles 95 |  |
| Failed requests (pre_error) against requests made (pre_fetched plus pre_error) | 3 of 101,358 = 0.003%; bar 1% or less | meets |
| Requests made inside a step (pre_missing plus pre_ondemand, first step after each start left out) against coin-minutes (18 times the minutes run) | 95 of 106,218 = 0.089%; bar 2% or less | meets |
| Left out: pre_missing of the first step after each start (at most 18 per start) | 0 left out, over 18 starts in the log |  |

## Sixth book against the fifth book

Period both ran: 2026-11-16 23:37 UTC to 2026-11-20 21:41 UTC (94.1 calendar hours; 94.1 hours with both live).

| Measure | Spot R5 | Spot TW | TW minus R5 |
|---|---|---|---|
| Rung fills | 52 | 52 | +0 |
| Rung fills per calendar day | 13.27 | 13.27 |  |
| Rung fills per running day | 13.27 | 13.27 |  |
| First-bid fills (rung 4) | 31 | 31 | +0 |
| Deeper rungs placed | 35 | 35 |  |
| Dollars bought | $338,973 | $338,975 | $1.73 |
| Exit P&L | -$729.39 | -$731.07 | -$1.68 |
| Net per dollar bought | -21.5 bp | -21.6 bp | -0.0 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 31 |
| Only in the fifth book | 0 |
| Only in the sixth book | 0 |

This comparison is for the record. The registered read is Parts 3 and 4 of reports/owner/trades_workers_plan.md.

## Rule progress for the sixth book

Engine commit: 4c1717a (full hash 4c1717ac3cd711c3383e281ccb3eb2742f993b23), recorded 2026-11-20T15:51:51Z UTC.

> Parts 3 and 4 of reports/owner/trades_workers_plan.md, read here on the whole log and all pair files so far. This is progress only: the read is made once, on the period the plan defines, by scripts/owner/trades_workers/rule.py. Measure 1 of Part 4 (decisions against the research) is not computed here.

### Part 3, alternating minutes: one worker against three

One paper run of 60 minutes on one runner and the pinned commit, the trades pass with one worker in one minute and three in the next, the arm of the even minutes alternating from job to job (scripts/owner/workers_alt/run_alt.py, workers-alt.yml). Progress on every job so far that counts; the read (scripts/owner/trades_workers/rule.py) takes the jobs up to the period's end and adds later ones until there are 8 jobs and 30 slow one-worker passes, for at most 14 days from the first job.

| Start | First arm | Timed steps one / three | Median pass one / three | Slow passes one / three | Budget fallbacks one / three | Largest peak | Rows differing one / three | Counts |
|---|---|---|---|---|---|---|---|---|
| 2026-11-17 11:41 UTC | three | 30 / 31 | 2.60 s / 2.59 s | 0 / 0 | 0 / 0 | 7 | 242 of 522 / 236 of 522 | counts |
| 2026-11-17 22:50 UTC | three | 30 / 30 | 2.65 s / 2.61 s | 0 / 0 | 0 / 0 | 7 | 187 of 504 / 189 of 522 | counts |
| 2026-11-17 23:57 UTC | three | 31 / 30 | 2.50 s / 2.48 s | 0 / 0 | 0 / 0 | 7 | 252 of 522 / 245 of 522 | counts |
| 2026-11-18 05:32 UTC | one | 31 / 30 | 2.56 s / 2.50 s | 0 / 0 | 0 / 0 | 7 | 286 of 522 / 277 of 522 | counts |
| 2026-11-18 11:22 UTC | three | 30 / 31 | 2.46 s / 2.47 s | 0 / 0 | 0 / 0 | 7 | 280 of 522 / 257 of 522 | counts |
| 2026-11-18 12:28 UTC | one | 31 / 30 | 2.60 s / 2.48 s | 0 / 0 | 0 / 0 | 7 | 260 of 522 / 250 of 522 | counts |
| 2026-11-18 17:13 UTC | one | 30 / 31 | 2.95 s / 2.88 s | 1 / 0 | 0 / 0 | 7 | 224 of 522 / 220 of 522 | counts |
| 2026-11-18 18:22 UTC | three | 31 / 30 | 2.88 s / 2.65 s | 0 / 0 | 0 / 0 | 7 | 225 of 522 / 219 of 522 | counts |
| 2026-11-18 19:29 UTC | three | 31 / 30 | 2.76 s / 2.70 s | 0 / 0 | 0 / 0 | 7 | 203 of 522 / 210 of 522 | counts |
| 2026-11-18 20:37 UTC | three | 31 / 30 | 2.59 s / 2.60 s | 0 / 0 | 0 / 0 | 7 | 222 of 522 / 207 of 522 | counts |
| 2026-11-18 21:43 UTC | three | 31 / 30 | 2.60 s / 2.61 s | 0 / 0 | 0 / 0 | 7 | 230 of 522 / 239 of 522 | counts |
| 2026-11-18 22:51 UTC | three | 30 / 30 | 2.60 s / 2.61 s | 0 / 0 | 0 / 0 | 7 | 202 of 504 / 212 of 522 | counts |
| 2026-11-18 23:57 UTC | three | 31 / 30 | 2.60 s / 2.61 s | 0 / 0 | 0 / 0 | 7 | 213 of 522 / 213 of 522 | counts |
| 2026-11-19 01:03 UTC | one | 31 / 30 | 2.65 s / 2.66 s | 0 / 0 | 0 / 0 | 7 | 251 of 522 / 245 of 522 | counts |
| 2026-11-19 02:10 UTC | one | 31 / 30 | 2.60 s / 2.61 s | 0 / 0 | 0 / 0 | 7 | 214 of 522 / 224 of 522 | counts |
| 2026-11-19 03:16 UTC | one | 31 / 30 | 2.86 s / 2.61 s | 2 / 2 | 0 / 0 | 7 | 220 of 522 / 224 of 522 | counts |
| 2026-11-19 04:22 UTC | one | 31 / 30 | 2.89 s / 2.47 s | 0 / 0 | 0 / 0 | 7 | 227 of 522 / 230 of 522 | counts |
| 2026-11-19 05:28 UTC | one | 31 / 30 | 2.55 s / 2.48 s | 0 / 0 | 0 / 0 | 7 | 253 of 522 / 259 of 522 | counts |
| 2026-11-19 06:36 UTC | three | 30 / 31 | 2.60 s / 2.51 s | 0 / 0 | 0 / 0 | 7 | 268 of 522 / 265 of 522 | counts |
| 2026-11-19 07:44 UTC | three | 30 / 31 | 2.54 s / 2.47 s | 1 / 1 | 2 / 0 | 7 | 284 of 520 / 279 of 522 | counts |
| 2026-11-19 08:52 UTC | three | 31 / 30 | 2.50 s / 2.50 s | 0 / 0 | 0 / 0 | 7 | 289 of 522 / 294 of 522 | counts |
| 2026-11-19 09:59 UTC | three | 31 / 30 | 2.45 s / 2.46 s | 0 / 0 | 0 / 0 | 7 | 299 of 522 / 295 of 522 | counts |
| 2026-11-19 11:05 UTC | three | 31 / 30 | 2.62 s / 2.47 s | 0 / 0 | 0 / 0 | 7 | 257 of 522 / 237 of 522 | counts |
| 2026-11-19 12:13 UTC | one | 30 / 31 | 2.56 s / 2.56 s | 0 / 0 | 0 / 0 | 7 | 238 of 522 / 241 of 522 | counts |
| 2026-11-19 13:21 UTC | one | 31 / 30 | 2.50 s / 2.51 s | 0 / 0 | 0 / 0 | 7 | 263 of 522 / 246 of 522 | counts |
| 2026-11-19 14:28 UTC | one | 31 / 30 | 3.02 s / 2.92 s | 0 / 0 | 0 / 0 | 7 | 180 of 522 / 173 of 522 | counts |
| 2026-11-19 15:36 UTC | one | 30 / 30 | 2.78 s / 2.78 s | 0 / 0 | 0 / 0 | 7 | 157 of 504 / 175 of 522 | counts |
| 2026-11-19 16:42 UTC | one | 31 / 30 | 3.08 s / 2.92 s | 0 / 0 | 0 / 0 | 7 | 131 of 522 / 129 of 522 | counts |
| 2026-11-19 17:50 UTC | one | 31 / 30 | 2.64 s / 2.65 s | 0 / 0 | 0 / 0 | 7 | 204 of 522 / 205 of 522 | counts |
| 2026-11-19 18:56 UTC | three | 30 / 31 | 2.80 s / 2.65 s | 0 / 0 | 0 / 0 | 7 | 229 of 522 / 224 of 522 | counts |
| 2026-11-19 20:04 UTC | three | 30 / 31 | 2.94 s / 2.77 s | 0 / 0 | 0 / 0 | 7 | 157 of 522 / 151 of 522 | counts |
| 2026-11-19 21:13 UTC | three | 31 / 30 | 3.04 s / 2.81 s | 1 / 0 | 0 / 0 | 7 | 188 of 522 / 194 of 522 | counts |
| 2026-11-19 22:21 UTC | three | 31 / 30 | 2.60 s / 2.61 s | 0 / 0 | 0 / 0 | 7 | 235 of 522 / 213 of 522 | counts |
| 2026-11-19 23:27 UTC | three | 30 / 31 | 2.61 s / 2.65 s | 0 / 0 | 0 / 0 | 7 | 219 of 522 / 226 of 522 | counts |
| 2026-11-20 00:34 UTC | one | 31 / 30 | 2.69 s / 2.62 s | 0 / 0 | 0 / 0 | 7 | 207 of 522 / 221 of 522 | counts |
| 2026-11-20 01:42 UTC | one | 31 / 30 | 2.73 s / 2.75 s | 0 / 0 | 0 / 0 | 7 | 126 of 522 / 143 of 522 | counts |
| 2026-11-20 02:48 UTC | one | 31 / 30 | 2.60 s / 2.60 s | 0 / 0 | 0 / 0 | 7 | 195 of 522 / 180 of 522 | counts |
| 2026-11-20 03:54 UTC | one | 31 / 30 | 2.63 s / 2.62 s | 0 / 0 | 0 / 0 | 7 | 191 of 522 / 208 of 522 | counts |
| 2026-11-20 05:02 UTC | one | 31 / 30 | 2.59 s / 2.60 s | 0 / 0 | 0 / 0 | 7 | 205 of 522 / 218 of 522 | counts |
| 2026-11-20 06:08 UTC | three | 30 / 31 | 2.53 s / 2.60 s | 0 / 0 | 0 / 0 | 7 | 259 of 522 / 256 of 522 | counts |
| 2026-11-20 07:16 UTC | three | 31 / 30 | 2.64 s / 2.51 s | 0 / 0 | 0 / 0 | 7 | 263 of 522 / 244 of 522 | counts |
| 2026-11-20 08:23 UTC | three | 31 / 30 | 2.46 s / 2.47 s | 0 / 0 | 0 / 0 | 7 | 246 of 522 / 244 of 522 | counts |
| 2026-11-20 09:29 UTC | three | 31 / 30 | 2.89 s / 2.48 s | 0 / 0 | 0 / 0 | 7 | 227 of 522 / 239 of 522 | counts |
| 2026-11-20 10:37 UTC | three | 31 / 30 | 4.25 s / 2.87 s | 4 / 2 | 9 / 0 | 7 | 231 of 513 / 242 of 522 | counts |
| 2026-11-20 11:45 UTC | three | 31 / 30 | 3.31 s / 2.62 s | 6 / 1 | 1 / 0 | 7 | 194 of 521 / 177 of 522 | counts |
| 2026-11-20 12:53 UTC | one | 31 / 30 | 2.67 s / 2.65 s | 0 / 0 | 0 / 0 | 7 | 167 of 522 / 158 of 522 | counts |
| 2026-11-20 14:00 UTC | one | 31 / 30 | 2.92 s / 2.94 s | 0 / 0 | 0 / 0 | 7 | 161 of 522 / 177 of 522 | counts |
| 2026-11-20 15:06 UTC | one | 31 / 30 | 3.71 s / 3.46 s | 0 / 0 | 0 / 0 | 7 | 53 of 522 / 59 of 522 | counts |
| 2026-11-20 16:14 UTC | one | 31 / 30 | 2.75 s / 2.76 s | 0 / 0 | 0 / 0 | 7 | 98 of 522 / 111 of 522 | counts |
| 2026-11-20 17:20 UTC | one | 31 / 30 | 2.60 s / 2.62 s | 0 / 0 | 0 / 0 | 7 | 134 of 522 / 145 of 522 | counts |
| 2026-11-20 18:26 UTC | three | 31 / 30 | 2.80 s / 2.80 s | 0 / 0 | 0 / 0 | 7 | 116 of 522 / 104 of 522 | counts |
| 2026-11-20 19:33 UTC | three | 31 / 30 | 2.77 s / 2.77 s | 0 / 0 | 0 / 0 | 7 | 108 of 522 / 113 of 522 | counts |
| 2026-11-20 20:41 UTC | three | 31 / 30 | 2.77 s / 2.69 s | 0 / 0 | 0 / 0 | 7 | 135 of 522 / 125 of 522 | counts |

| Part | Current value | Verdict |
|---|---|---|
| Jobs that count, and the slow one-worker passes | 53 jobs (8 needed); 15 slow one-worker passes (30 needed) | still waiting |
| 1. No harm: the median pass with three at most the median with one plus 0.05 s | three 2.62 s, one 2.64 s, over 1600 and 1630 steps | meets |
| 2. A gain in slow minutes: at least 30 slow one-worker passes, the three-worker share of slow passes at most half the one-worker share, fallbacks (in passes) not more with three than chance allows | slow passes 6 of 1600 with three, 15 of 1630 with one; fallback passes 0 with three, 3 with one (no more; coins 0 and 12) | does not meet yet |
| 3. The pace: over every file from the first job on, no three-worker step above 8 trades requests in one second, none limited or refused, every file readable | 53 files; most in one second 7; 0 files above 8; 0 with a limit or refusal; 0 unreadable | meets |
| 4. The rows: share of built bars differing from the venue's candle, three at most one point above one, or more only within chance (jobs with a complete comparison) | three 11067 of 27666 = 40.002%; one 11105 of 27600 = 40.236%; 53 jobs; no more | meets |
| Reported, decides nothing: median and mean pass, three minus one | median -0.03 s, mean -0.13 s (first version of the plan asked for a 0.2 s gain at the median over half-hour pairs) | reported only |

### Part 4, measure 2: items 1 to 5

Real-time minutes run so far: 5,644.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.97% (96,886 verified of 96,912 attempted coin-minutes: built 93,665, verified empty 3,221; fallbacks: unverified 1, error 4, budget 21, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step 30-minute maximum 20 s or less in 95% or more of heartbeats (the median is not judged for this book; the pairs decide the step) | median 8.6 s of 188 heartbeats; maximum 20 s or less in 99.5% (largest 21.2 s); the median is not judged here | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 101,394 coin-minutes, 18 coins) | meets |

### Part 4, measure 3: requests inside a step

| Part | Current value | Verdict |
|---|---|---|
| Failed requests (pre_error) against requests made (pre_fetched plus pre_error) | 2 of 96,606 = 0.002%; bar 1% or less | meets |
| Requests made inside a step (first step after each start left out) against coin-minutes (18 times the minutes run) | 27 of 101,394 = 0.027%; bar 2% or less | meets |

| Part | Current value | Verdict |
|---|---|---|
| In-step share against the fifth book's, over the half hours in which both have a heartbeat (the sixth's must be no higher) | sixth 27 of 99,774 = 0.027%, fifth 85 of 99,900 = 0.085%, 185 half hours | meets |

### Part 4, measure 4: stops

| Part | Current value | Verdict |
|---|---|---|
| Half hours with a rate-limit stop (tb_fb_limited above 0): none in the sixth book unless the fifth has one at the same heartbeat | sixth 0, fifth 0; sixth only: 0 | meets |
| Half hours with a request error (tb_fb_error above 0): the sixth's at most the fifth's plus 2 | sixth 3, fifth 3 | meets |

### Reported, decides nothing

| Part | Current value |
|---|---|
| The sixth book's own heartbeat entry step_s.trades (the trades pass's duration) | median of the half-hour medians 2.60 s, largest maximum 8.01 s, over 188 heartbeats |
| Data-step median over the half hours both books have a heartbeat (the runners differ, so the pairs decide the step) | sixth 8.61 s, fifth 8.64 s, 185 half hours |

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 14 | 0.98 | 1.17 | 57.5 bp | $10,176 | +1.76% | 95,192 |
| Perp R2-08 | 12 | 0.86 | 1.02 | 41.2 bp | $10,117 | +1.17% | 92,734 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

## Data notes

- Spot (main): event kinds not seen before: stale_input (3).
- Spot W2: event kinds not seen before: stale_input (3).
- Spot TB (trades input): event kinds not seen before: stale_input (1).
- Spot T18 (all coins on trades): event kinds not seen before: stale_input (4).
- Spot R5 (release 5 build): event kinds not seen before: stale_input (39).
- Spot TW (trades side by side): event kinds not seen before: stale_input (39).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
