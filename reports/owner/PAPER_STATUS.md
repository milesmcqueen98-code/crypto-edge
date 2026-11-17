# Paper trading status

Report made 2026-11-17 12:01 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-17 09:36 UTC | 2.4 h ago | ok |
| Spot W2 | 2026-11-17 09:36 UTC | 2.4 h ago | ok |
| Spot TB (trades input) | 2026-11-16 21:30 UTC | 14.5 h ago | ended |
| Spot T18 (all coins on trades) | 2026-11-17 06:30 UTC | 5.5 h ago | ok |
| Spot R5 (release 5 build) | 2026-11-17 07:00 UTC | 5.0 h ago | ok |
| Spot TW (trades side by side) | 2026-11-17 12:00 UTC | 0.0 h ago | ok |
| Perp v1 (control) | 2026-11-17 10:02 UTC | 2.0 h ago | ok |
| Perp R2-08 | 2026-11-17 10:02 UTC | 2.0 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old. A book marked ended (Spot TB (trades input): 2026-11-16) is never flagged STALE.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-17 09:36 UTC | 251.1 | 206.4 | 82.2% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-17 09:36 UTC | 248.9 | 204.2 | 82.1% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-16 21:30 UTC | 139.7 | 139.5 | 99.9% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-17 06:30 UTC | 128.1 | 128.1 | 100.0% |
| Spot R5 (release 5 build) | 2026-11-16 18:39 UTC | 2026-11-17 07:00 UTC | 12.3 | 12.3 | 100.0% |
| Spot TW (trades side by side) | 2026-11-16 23:37 UTC | 2026-11-17 12:00 UTC | 12.4 | 12.4 | 100.0% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-17 10:02 UTC | 259.5 | 207.4 | 80.0% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-17 10:02 UTC | 251.3 | 201.7 | 80.3% |

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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 2.4 h; Spot W2 2.4 h; Spot T18 (all coins on trades) 5.5 h; Spot R5 (release 5 build) 5.0 h; Spot TW (trades side by side) 0.0 h; Perp v1 (control) 2.0 h; Perp R2-08 2.0 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 10.5 | $251,067 | +0.43% | 89 | $631,533 | 16.9 bp | 70 / 46 | 52 (32 made money) | 1 |
| Spot W2 | 10.4 | $251,128 | +0.45% | 86 | $538,306 | 21.0 bp | 64 / 46 | 54 (35 made money) | 1 |
| Spot TB (trades input) | 5.8 | $249,964 | -0.01% | 70 | $537,290 | -0.7 bp | 33 / 35 | 37 (22 made money) | 0 |
| Spot T18 (all coins on trades) | 5.3 | $249,771 | -0.09% | 72 | $539,242 | -4.3 bp | 30 / 35 | 38 (23 made money) | 0 |
| Spot R5 (release 5 build) | 0.5 | $250,000 | +0.00% | 0 | $0.00 | n/a | 0 / 0 | 0 (0 made money) | 0 |
| Spot TW (trades side by side) | 0.5 | $250,000 | +0.00% | 0 | $0.00 | n/a | 0 / 0 | 0 (0 made money) | 0 |
| Perp v1 (control) | 10.8 | $10,144 | +1.44% | 11 | n/a (not logged) | n/a | 4 / 7 | - | 0 |
| Perp R2-08 | 10.5 | $10,130 | +1.30% | 10 | n/a (not logged) | n/a | 4 / 6 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

Rule A is counted from 2026-11-14 17:27 UTC; see the section below.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

Counted from 2026-11-14 17:27 UTC (release 3): the main book's inputs changed then. The registered rule is counted again from that time (reports/owner/FORWARD_TESTS.md).

| Measure | So far |
|---|---|
| Days (calendar) | 2.7 of 21 |
| Days in real time | 2.7 |
| Rungs | 27 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 10.10 per calendar day; 10.11 per running day |
| Mean net per dollar | -40.4 bp |
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
| 4 | 65 | $443,573 | 88 | -$97.39 | -2.2 bp |
| 6 | 21 | $155,382 | 24 | $1,212 | 78.0 bp |
| 8 | 3 | $32,577 | 4 | -$47.71 | -14.6 bp |

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
| 2026-11-14 | -$781.37 | 24.0 |
| 2026-11-15 | $0.00 | 24.0 |
| 2026-11-16 | $0.00 | 24.0 |
| 2026-11-17 | $0.00 | 9.6 |

Cash shortfalls: 31. Wanted $214,854 in total (average $6,931) against an average of $466.74 free.

Share of capital held by resting bids (committed over equity, mean of 406 heartbeats): 59.19%.

Largest single-day loss so far: -$781.37 on 2026-11-14.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 10.5 | 10.4 | -0.1 |
| Hours in real time | 206.4 | 204.2 |  |
| Equity | $251,067 | $251,128 | $61.66 |
| Change | +0.43% | +0.45% | +0.02 pp |
| Rung fills | 89 | 86 | -3 |
| Rung fills per calendar day | 8.51 | 8.29 |  |
| Rung fills per running day | 10.35 | 10.11 |  |
| Dollars bought | $631,533 | $538,306 | -$93,226 |
| Net per dollar | 16.9 bp | 21.0 bp | +4.1 bp |
| Exit events TP / time | 70 / 46 | 64 / 46 |  |
| Ladders closed (made money) | 52 (32) | 54 (35) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): $61.66.

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
| 2026-11-17 | 600 | 20 | 11.0 | 16.0 | btc_candle_old 240, candle_old 725, newest_absent 891, rows_open 6, skip_old 423, tb_built 2,900, tb_close_diff 296, tb_insert 377 |
| Total | 8,253 | 276 | 10.1 | 23.2 | btc_candle_old 4,143, btc_stale 3,614, candle_old 15,406, newest_absent 13,006, rows_open 6, skip_old 1,678, tb_built 18,283, tb_close_diff 1,180, tb_empty 3, tb_fb_budget 19, tb_fb_error 1, tb_fb_unverified 4, tb_insert 2,017, tb_rebuilt 17 |

130 earlier heartbeat(s) carry none of these fields and are not counted.

Heartbeats with a trades error (tb_err): 1. Last: BTC: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

### Spot W2

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 411, btc_stale 464, candle_old 1,919, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 893, btc_stale 1,023, candle_old 2,666, newest_absent 2,439 |
| 2026-11-13 | 1,408 | 47 | 10.1 | 14.9 | btc_candle_old 1,122, btc_stale 1,302, candle_old 2,663, newest_absent 3,287 |
| 2026-11-14 | 1,440 | 48 | 9.5 | 28.1 | btc_candle_old 670, btc_stale 825, candle_old 7,408, newest_absent 2,769, skip_old 193, tb_built 1,740, tb_close_diff 124, tb_fb_budget 12, tb_fb_unverified 3, tb_insert 69, tb_rebuilt 3 |
| 2026-11-15 | 1,440 | 48 | 11.1 | 25.4 | btc_candle_old 473, candle_old 995, newest_absent 1,122, skip_old 644, tb_built 6,901, tb_close_diff 433, tb_empty 3, tb_fb_budget 4, tb_fb_error 1, tb_fb_unverified 1, tb_insert 651, tb_rebuilt 3 |
| 2026-11-16 | 1,380 | 46 | 10.9 | 17.2 | btc_candle_old 556, candle_old 817, newest_absent 1,452, skip_old 461, tb_built 6,745, tb_close_diff 327, tb_insert 920, tb_rebuilt 9 |
| 2026-11-17 | 600 | 20 | 11.0 | 16.0 | btc_candle_old 269, candle_old 774, newest_absent 891, rows_open 6, skip_old 440, tb_built 2,900, tb_close_diff 296, tb_insert 377 |
| Total | 8,253 | 276 | 10.1 | 28.1 | btc_candle_old 4,394, btc_stale 3,614, candle_old 17,242, newest_absent 13,006, rows_open 6, skip_old 1,738, tb_built 18,286, tb_close_diff 1,180, tb_empty 3, tb_fb_budget 16, tb_fb_error 1, tb_fb_unverified 4, tb_insert 2,017, tb_rebuilt 15 |

126 earlier heartbeat(s) carry none of these fields and are not counted.

Heartbeats with a trades error (tb_err): 1. Last: BTC: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

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
| 2026-11-17 | 420 | 14 | 12.2 | 22.7 | btc_candle_old 18, candle_old 98, newest_absent 208, tb_built 7,225, tb_close_diff 235, tb_dropped 281, tb_empty 210, tb_fb_budget 15, tb_fb_error 2, tb_insert 901, tb_pending 27, tb_rebuilt 12, tb_replaced 6,932, tb_replaced_diff 1,428 |
| Total | 7,595 | 254 | 13.5 | 35.6 | btc_candle_old 1,299, btc_stale 2, candle_old 2,626, newest_absent 2,481, skip_old 24, tb_built 128,372, tb_close_diff 5,134, tb_dropped 3,419, tb_empty 2,434, tb_fb_budget 909, tb_fb_error 3, tb_fb_unverified 6, tb_insert 7,583, tb_pending 289, tb_rebuilt 223, tb_replaced 124,710, tb_replaced_diff 19,860 |

Heartbeats with a trades error (tb_err): 2. Last: LTC: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

### Spot R5 (release 5 build)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-16 | 291 | 10 | 8.6 | 16.3 | newest_absent 129, pre_fetched 4,662, pre_ondemand 10, step_candles 10, tb_built 4,550, tb_dropped 135, tb_empty 128, tb_fb_budget 20, tb_pending 230, tb_rebuilt 19, tb_replaced 4,393, tb_replaced_diff 443 |
| 2026-11-17 | 450 | 15 | 8.6 | 16.5 | newest_absent 221, pre_fetched 7,776, pre_ondemand 16, step_candles 16, tb_built 7,557, tb_dropped 305, tb_empty 221, tb_fb_budget 15, tb_fb_error 1, tb_pending 937, tb_rebuilt 21, tb_replaced 7,240, tb_replaced_diff 1,333 |
| Total | 741 | 25 | 8.6 | 16.5 | newest_absent 350, pre_fetched 12,438, pre_ondemand 26, step_candles 26, tb_built 12,107, tb_dropped 440, tb_empty 349, tb_fb_budget 35, tb_fb_error 1, tb_pending 1,167, tb_rebuilt 40, tb_replaced 11,633, tb_replaced_diff 1,776 |

Left out for this book: tb_insert, tb_close_diff. With candle requests between steps (candles_at_s) the step has no candle row for the newest minute of a trades-built coin, so tb_insert counts nearly every trades bar and tb_close_diff is not measured for those coins; the counters are not comparable with the fourth book's and are not shown.

Heartbeats with a trades error (tb_err): 1. Last: SUI: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

### Spot TW (trades side by side)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-17 | 743 | 25 | 8.5 | 14.8 | newest_absent 416, pre_error 1, pre_fetched 12,599, pre_missing 1, pre_ondemand 5, step_candles 6, tb_built 12,230, tb_dropped 550, tb_empty 419, tb_fb_budget 3, tb_fb_error 2, tb_pending 1,119, tb_rebuilt 51, tb_replaced 11,644, tb_replaced_diff 2,282 |
| Total | 743 | 25 | 8.5 | 14.8 | newest_absent 416, pre_error 1, pre_fetched 12,599, pre_missing 1, pre_ondemand 5, step_candles 6, tb_built 12,230, tb_dropped 550, tb_empty 419, tb_fb_budget 3, tb_fb_error 2, tb_pending 1,119, tb_rebuilt 51, tb_replaced 11,644, tb_replaced_diff 2,282 |

Left out for this book: tb_insert, tb_close_diff. With candle requests between steps (candles_at_s) the step has no candle row for the newest minute of a trades-built coin, so tb_insert counts nearly every trades bar and tb_close_diff is not measured for those coins; the counters are not comparable with the fourth book's and are not shown.

Heartbeats with a trades error (tb_err): 1. Last: XLM: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

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

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-17T01:03:57Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: 7,685.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.30% (130,806 verified of 131,724 attempted coin-minutes: built 128,372, verified empty 2,434; fallbacks: unverified 6, error 3, budget 909, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.5 s of 254 heartbeats; maximum 20 s or less in 94.1% (largest 35.6 s) | does not meet yet |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 136,710 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 289 of 136,710 coin-minutes

Totals: tb_replaced 124,710, tb_replaced_diff 19,860, tb_dropped 3,419.

## Fifth book against the fourth book

Period both ran: 2026-11-16 18:39 UTC to 2026-11-17 06:30 UTC (11.8 calendar hours; 11.8 hours with both live).

| Measure | Spot T18 | Spot R5 | R5 minus T18 |
|---|---|---|---|
| Rung fills | 0 | 0 | +0 |
| Rung fills per calendar day | 0.00 | 0.00 |  |
| Rung fills per running day | 0.00 | 0.00 |  |
| First-bid fills (rung 4) | 0 | 0 | +0 |
| Deeper rungs placed | 0 | 0 |  |
| Dollars bought | $0.00 | $0.00 | $0.00 |
| Exit P&L | $0.00 | $0.00 | $0.00 |
| Net per dollar bought | n/a | n/a | n/a |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 0 |
| Only in the fourth book | 0 |
| Only in the fifth book | 0 |

This comparison is for the record. The registered read is Part 3 of reports/owner/bar_source_prereg.md.

## Rule progress for the fifth book

Engine commit: 9e6f53b (full hash 9e6f53b3aca8c15307f22a357f19431bff053e4c), recorded 2026-11-17T01:14:56Z UTC.

> The four measures of Part 3 of reports/owner/bar_source_prereg.md, read here on the whole log so far. This is progress only: the read is made once, on the period the plan defines, by scripts/owner/bar_source/part3_rule.py. Measure 2 (decisions against the research) is not computed here.

### Measure 1, the step

(a) Same-machine pairs: on one runner and the pinned commit, 30 minutes with release 3's inputs and 30 minutes with the build's, one after the other, the order alternating (scripts/owner/step_pairs/run_pair.py, step-pairs.yml). The measure is the median of the build's median data step minus release 3's over the pairs that count: at or below zero, at least 8 pairs. If fewer than 8 count in the period, the read also takes the later pairs, oldest first, up to the one that makes 8.

| Start | Order | Release 3 median | Build median | Build minus release 3 | Counts |
|---|---|---|---|---|---|
| 2026-11-16 19:27 UTC | ba | 11.24 s | 8.55 s | -2.69 s | counts |
| 2026-11-17 06:56 UTC | ba | 9.49 s | 8.46 s | -1.03 s | counts |

| Part | Current value | Verdict |
|---|---|---|
| (a) Pairs that count, and the median of build minus release 3 | 2 pairs (8 needed); median -1.86 s; must be at or below 0.00 s | does not meet yet |

| Part | Current value | Verdict |
|---|---|---|
| (b) Against the main book, over the half hours both have a heartbeat (same heartbeat time) | fifth 8.63 s, main 9.64 s, 24 half hours; the fifth's must be no higher | meets |
| Reported, decides nothing: the fifth book's own median of its half-hour data-step medians | 8.62 s over 25 heartbeats; for comparison 10.3 s (release 3's figure of Nov 11 to 14, which moves with the period and the runner) | reported only |
| For information: against the fourth book, same way | fifth 8.63 s, fourth 13.61 s, 24 half hours | not part of the rule |

The read needs at least 100 heartbeats of the fifth book and at least 100 paired half hours with the main book for (b).

### Items 1 to 5 (measure 3)

Real-time minutes run so far: 741.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.71% (12,456 verified of 12,492 attempted coin-minutes: built 12,107, verified empty 349; fallbacks: unverified 0, error 1, budget 35, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step 30-minute maximum 20 s or less in 95% or more of heartbeats (the median is measure 1, see below) | median 8.6 s of 25 heartbeats; maximum 20 s or less in 100.0% (largest 16.5 s); the median is judged as measure 1 | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 13,338 coin-minutes, 18 coins) | meets |

### Measure 4, the candle requests between steps

| Part | Current value | Verdict |
|---|---|---|
| Counters, summed over the log | pre_fetched 12,438, pre_error 0, pre_missing 0, pre_ondemand 26, step_candles 26 |  |
| Failed requests (pre_error) against requests made (pre_fetched plus pre_error) | 0 of 12,438 = 0.000%; bar 1% or less | meets |
| Requests made inside a step (pre_missing plus pre_ondemand, first step after each start left out) against coin-minutes (18 times the minutes run) | 26 of 13,338 = 0.195%; bar 2% or less | meets |
| Left out: pre_missing of the first step after each start (at most 18 per start) | 0 left out, over 3 starts in the log |  |

## Sixth book against the fifth book

Period both ran: 2026-11-16 23:37 UTC to 2026-11-17 07:00 UTC (7.4 calendar hours; 7.4 hours with both live).

| Measure | Spot R5 | Spot TW | TW minus R5 |
|---|---|---|---|
| Rung fills | 0 | 0 | +0 |
| Rung fills per calendar day | 0.00 | 0.00 |  |
| Rung fills per running day | 0.00 | 0.00 |  |
| First-bid fills (rung 4) | 0 | 0 | +0 |
| Deeper rungs placed | 0 | 0 |  |
| Dollars bought | $0.00 | $0.00 | $0.00 |
| Exit P&L | $0.00 | $0.00 | $0.00 |
| Net per dollar bought | n/a | n/a | n/a |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 0 |
| Only in the fifth book | 0 |
| Only in the sixth book | 0 |

This comparison is for the record. The registered read is Parts 3 and 4 of reports/owner/trades_workers_plan.md.

## Rule progress for the sixth book

Engine commit: 4c1717a (full hash 4c1717ac3cd711c3383e281ccb3eb2742f993b23), recorded 2026-11-17T06:11:43Z UTC.

> Parts 3 and 4 of reports/owner/trades_workers_plan.md, read here on the whole log and all pair files so far. This is progress only: the read is made once, on the period the plan defines, by scripts/owner/trades_workers/rule.py. Measure 1 of Part 4 (decisions against the research) is not computed here.

### Part 3, alternating minutes: one worker against three

One paper run of 60 minutes on one runner and the pinned commit, the trades pass with one worker in one minute and three in the next, the arm of the even minutes alternating from job to job (scripts/owner/workers_alt/run_alt.py, workers-alt.yml). Progress on every job so far that counts; the read (scripts/owner/trades_workers/rule.py) takes the jobs up to the period's end and adds later ones until there are 8 jobs and 30 slow one-worker passes, for at most 14 days from the first job.

No jobs yet.

| Part | Current value | Verdict |
|---|---|---|
| Jobs that count, and the slow one-worker passes | 0 jobs (8 needed); 0 slow one-worker passes (30 needed) | still waiting |
| 1. No harm: the median pass with three at most the median with one plus 0.05 s | three n/a, one n/a, over 0 and 0 steps | does not meet yet |
| 2. A gain in slow minutes: at least 30 slow one-worker passes, the three-worker share of slow passes at most half the one-worker share, fallbacks with three no more | slow passes 0 of 0 with three, 0 of 0 with one; fallbacks 0 with three, 0 with one | does not meet yet |
| 3. The pace: over every file from the first job on, no three-worker step above 8 trades requests in one second, none limited or refused, every file readable | 0 files; most in one second n/a; 0 files above 8; 0 with a limit or refusal; 0 unreadable | meets |
| 4. The rows: share of built bars differing from the venue's candle, three at most one point above one (jobs with a complete comparison) | three 0 of 0 = n/a; one 0 of 0 = n/a; 0 jobs | does not meet yet |
| Reported, decides nothing: median and mean pass, three minus one | median n/a, mean n/a (first version of the plan asked for a 0.2 s gain at the median over half-hour pairs) | reported only |

### Part 4, measure 2: items 1 to 5

Real-time minutes run so far: 743.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.96% (12,649 verified of 12,654 attempted coin-minutes: built 12,230, verified empty 419; fallbacks: unverified 0, error 2, budget 3, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step 30-minute maximum 20 s or less in 95% or more of heartbeats (the median is not judged for this book; the pairs decide the step) | median 8.5 s of 25 heartbeats; maximum 20 s or less in 100.0% (largest 14.8 s); the median is not judged here | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 13,374 coin-minutes, 18 coins) | meets |

### Part 4, measure 3: requests inside a step

| Part | Current value | Verdict |
|---|---|---|
| Failed requests (pre_error) against requests made (pre_fetched plus pre_error) | 1 of 12,600 = 0.008%; bar 1% or less | meets |
| Requests made inside a step (first step after each start left out) against coin-minutes (18 times the minutes run) | 6 of 13,374 = 0.045%; bar 2% or less | meets |

| Part | Current value | Verdict |
|---|---|---|
| In-step share against the fifth book's, over the half hours in which both have a heartbeat (the sixth's must be no higher) | sixth 5 of 7,974 = 0.063%, fifth 16 of 8,100 = 0.198%, 15 half hours | meets |

### Part 4, measure 4: stops

| Part | Current value | Verdict |
|---|---|---|
| Half hours with a rate-limit stop (tb_fb_limited above 0): none in the sixth book unless the fifth has one at the same heartbeat | sixth 0, fifth 0; sixth only: 0 | meets |
| Half hours with a request error (tb_fb_error above 0): the sixth's at most the fifth's plus 2 | sixth 1, fifth 1 | meets |

### Reported, decides nothing

| Part | Current value |
|---|---|
| The sixth book's own heartbeat entry step_s.trades (the trades pass's duration) | median of the half-hour medians 2.52 s, largest maximum 8.01 s, over 25 heartbeats |
| Data-step median over the half hours both books have a heartbeat (the runners differ, so the pairs decide the step) | sixth 8.53 s, fifth 8.63 s, 15 half hours |

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 11 | 1.02 | 1.27 | 62.9 bp | $10,144 | +1.44% | 68,356 |
| Perp R2-08 | 10 | 0.96 | 1.19 | 56.8 bp | $10,130 | +1.30% | 66,035 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

## Data notes

- Spot TB (trades input): event kinds not seen before: stale_input (1).
- Spot T18 (all coins on trades): event kinds not seen before: stale_input (2).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
