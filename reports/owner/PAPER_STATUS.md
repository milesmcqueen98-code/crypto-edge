# Paper trading status

Report made 2026-11-18 21:26 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-18 20:41 UTC | 0.8 h ago | ok |
| Spot W2 | 2026-11-18 20:41 UTC | 0.8 h ago | ok |
| Spot TB (trades input) | 2026-11-16 21:30 UTC | 47.9 h ago | ended |
| Spot T18 (all coins on trades) | 2026-11-18 17:50 UTC | 3.6 h ago | ok |
| Spot R5 (release 5 build) | 2026-11-18 18:04 UTC | 3.4 h ago | ok |
| Spot TW (trades side by side) | 2026-11-18 17:12 UTC | 4.2 h ago | ok |
| Perp v1 (control) | 2026-11-18 21:06 UTC | 0.3 h ago | ok |
| Perp R2-08 | 2026-11-18 21:06 UTC | 0.3 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old. A book marked ended (Spot TB (trades input): 2026-11-16) is never flagged STALE.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-18 20:41 UTC | 286.2 | 241.5 | 84.4% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-18 20:41 UTC | 283.9 | 239.3 | 84.3% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-16 21:30 UTC | 139.7 | 139.5 | 99.9% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-18 17:50 UTC | 163.4 | 163.4 | 100.0% |
| Spot R5 (release 5 build) | 2026-11-16 18:39 UTC | 2026-11-18 18:04 UTC | 47.4 | 47.4 | 100.0% |
| Spot TW (trades side by side) | 2026-11-16 23:37 UTC | 2026-11-18 17:12 UTC | 41.6 | 41.6 | 100.0% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-18 21:06 UTC | 294.5 | 242.0 | 82.2% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-18 21:06 UTC | 286.4 | 236.3 | 82.5% |

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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 0.8 h; Spot W2 0.8 h; Spot T18 (all coins on trades) 3.6 h; Spot R5 (release 5 build) 3.4 h; Spot TW (trades side by side) 4.2 h; Perp v1 (control) 0.3 h; Perp R2-08 0.3 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 11.9 | $250,972 | +0.39% | 95 | $667,579 | 14.6 bp | 70 / 50 | 54 (33 made money) | 1 |
| Spot W2 | 11.8 | $251,082 | +0.43% | 92 | $570,618 | 19.0 bp | 64 / 50 | 56 (36 made money) | 1 |
| Spot TB (trades input) | 5.8 | $249,964 | -0.01% | 70 | $537,290 | -0.7 bp | 33 / 35 | 37 (22 made money) | 0 |
| Spot T18 (all coins on trades) | 6.8 | $249,672 | -0.13% | 73 | $560,057 | -5.9 bp | 30 / 36 | 39 (23 made money) | 0 |
| Spot R5 (release 5 build) | 2.0 | $249,902 | -0.04% | 1 | $20,833 | -47.2 bp | 0 / 1 | 1 (0 made money) | 0 |
| Spot TW (trades side by side) | 1.7 | $249,902 | -0.04% | 1 | $20,833 | -47.2 bp | 0 / 1 | 1 (0 made money) | 0 |
| Perp v1 (control) | 12.3 | $10,144 | +1.44% | 11 | n/a (not logged) | n/a | 4 / 7 | - | 0 |
| Perp R2-08 | 11.9 | $10,130 | +1.30% | 10 | n/a (not logged) | n/a | 4 / 6 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

Rule A is counted from 2026-11-14 17:27 UTC; see the section below.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

Counted from 2026-11-14 17:27 UTC (release 3): the main book's inputs changed then. The registered rule is counted again from that time (reports/owner/FORWARD_TESTS.md).

| Measure | So far |
|---|---|
| Days (calendar) | 4.1 of 21 |
| Days in real time | 4.1 |
| Rungs | 33 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 7.98 per calendar day; 7.98 per running day |
| Mean net per dollar | -38.7 bp |
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
| 4 | 68 | $467,691 | 90 | -$222.81 | -4.8 bp |
| 6 | 22 | $161,347 | 25 | $1,202 | 74.5 bp |
| 8 | 5 | $38,541 | 5 | -$6.63 | -1.7 bp |

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
| 2026-11-17 | $4.53 | 24.0 |
| 2026-11-18 | -$98.77 | 20.7 |

Cash shortfalls: 31. Wanted $214,854 in total (average $6,931) against an average of $466.74 free.

Share of capital held by resting bids (committed over equity, mean of 475 heartbeats): 59.19%.

Largest single-day loss so far: -$781.37 on 2026-11-14.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 11.9 | 11.8 | -0.1 |
| Hours in real time | 241.5 | 239.3 |  |
| Equity | $250,972 | $251,082 | $109.94 |
| Change | +0.39% | +0.43% | +0.04 pp |
| Rung fills | 95 | 92 | -3 |
| Rung fills per calendar day | 7.97 | 7.78 |  |
| Rung fills per running day | 9.44 | 9.23 |  |
| Dollars bought | $667,579 | $570,618 | -$96,961 |
| Net per dollar | 14.6 bp | 19.0 bp | +4.4 bp |
| Exit events TP / time | 70 / 50 | 64 / 50 |  |
| Ladders closed (made money) | 54 (33) | 56 (36) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): $109.94.

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
| 2026-11-18 | 1,260 | 42 | 11.2 | 14.8 | btc_candle_old 431, candle_old 1,434, newest_absent 1,906, rows_open 9, skip_old 1,008, tb_built 6,094, tb_close_diff 682, tb_fb_unverified 1, tb_insert 440, tb_rebuilt 8 |
| Total | 10,323 | 345 | 10.3 | 23.2 | btc_candle_old 4,704, btc_stale 3,616, candle_old 18,123, newest_absent 15,665, rows_open 16, skip_old 3,555, tb_built 28,080, tb_close_diff 2,350, tb_empty 168, tb_fb_budget 19, tb_fb_error 3, tb_fb_unverified 5, tb_insert 2,629, tb_rebuilt 29 |

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
| 2026-11-18 | 1,260 | 42 | 11.2 | 14.8 | btc_candle_old 411, candle_old 1,423, newest_absent 1,906, rows_open 10, skip_old 985, tb_built 6,094, tb_close_diff 682, tb_fb_unverified 1, tb_insert 440, tb_rebuilt 9 |
| Total | 10,323 | 345 | 10.3 | 28.1 | btc_candle_old 4,956, btc_stale 3,616, candle_old 20,016, newest_absent 15,665, rows_open 16, skip_old 3,632, tb_built 28,083, tb_close_diff 2,350, tb_empty 168, tb_fb_budget 16, tb_fb_error 3, tb_fb_unverified 5, tb_insert 2,629, tb_rebuilt 28 |

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
| 2026-11-18 | 1,080 | 36 | 13.1 | 18.6 | btc_candle_old 46, candle_old 447, newest_absent 686, tb_built 17,719, tb_close_diff 1,440, tb_dropped 737, tb_empty 687, tb_fb_budget 7, tb_fb_error 1, tb_insert 1,053, tb_pending 72, tb_rebuilt 41, tb_replaced 16,953, tb_replaced_diff 3,213 |
| Total | 9,695 | 324 | 13.4 | 35.6 | btc_candle_old 1,577, btc_stale 4, candle_old 3,440, newest_absent 3,530, skip_old 24, tb_built 162,492, tb_close_diff 7,435, tb_dropped 4,659, tb_empty 4,148, tb_fb_budget 928, tb_fb_error 6, tb_fb_unverified 6, tb_insert 9,862, tb_pending 404, tb_rebuilt 292, tb_replaced 158,184, tb_replaced_diff 25,764 |

Heartbeats with a trades error (tb_err): 4. Last: ETH: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

### Spot R5 (release 5 build)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-16 | 291 | 10 | 8.6 | 16.3 | newest_absent 129, pre_fetched 4,662, pre_ondemand 10, step_candles 10, tb_built 4,550, tb_dropped 135, tb_empty 128, tb_fb_budget 20, tb_pending 230, tb_rebuilt 19, tb_replaced 4,393, tb_replaced_diff 443 |
| 2026-11-17 | 1,440 | 48 | 8.6 | 16.5 | btc_candle_old 1, btc_stale 38, candle_old 1, newest_absent 1,199, pre_fetched 24,624, pre_ondemand 26, skip_old 1, step_candles 26, tb_built 23,434, tb_dropped 790, tb_empty 1,236, tb_fb_budget 23, tb_fb_error 3, tb_pending 1,528, tb_rebuilt 96, tb_replaced 22,623, tb_replaced_diff 3,169 |
| 2026-11-18 | 1,110 | 37 | 8.5 | 22.4 | newest_absent 691, pre_error 1, pre_fetched 18,953, pre_missing 1, pre_ondemand 17, step_candles 18, tb_built 18,301, tb_dropped 740, tb_empty 690, tb_fb_budget 17, tb_pending 626, tb_rebuilt 65, tb_replaced 17,535, tb_replaced_diff 2,338 |
| Total | 2,841 | 95 | 8.6 | 22.4 | btc_candle_old 1, btc_stale 38, candle_old 1, newest_absent 2,019, pre_error 1, pre_fetched 48,239, pre_missing 1, pre_ondemand 53, skip_old 1, step_candles 54, tb_built 46,285, tb_dropped 1,665, tb_empty 2,054, tb_fb_budget 60, tb_fb_error 3, tb_pending 2,384, tb_rebuilt 180, tb_replaced 44,551, tb_replaced_diff 5,950 |

Left out for this book: tb_insert, tb_close_diff. With candle requests between steps (candles_at_s) the step has no candle row for the newest minute of a trades-built coin, so tb_insert counts nearly every trades bar and tb_close_diff is not measured for those coins; the counters are not comparable with the fourth book's and are not shown.

Heartbeats with a trades error (tb_err): 2. Last: BTC: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

### Spot TW (trades side by side)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-17 | 1,433 | 48 | 8.5 | 14.8 | btc_stale 38, newest_absent 1,209, pre_error 1, pre_fetched 24,461, pre_missing 1, pre_ondemand 5, step_candles 6, tb_built 23,297, tb_dropped 795, tb_empty 1,250, tb_fb_budget 3, tb_fb_error 2, tb_pending 1,555, tb_rebuilt 81, tb_replaced 22,444, tb_replaced_diff 3,531 |
| 2026-11-18 | 1,050 | 35 | 8.5 | 21.2 | btc_stale 1, newest_absent 692, pre_error 1, pre_fetched 18,017, pre_missing 1, pre_ondemand 18, step_candles 19, tb_built 17,363, tb_dropped 738, tb_empty 691, tb_fb_budget 18, tb_pending 638, tb_rebuilt 72, tb_replaced 16,585, tb_replaced_diff 2,597 |
| Total | 2,483 | 83 | 8.5 | 21.2 | btc_stale 39, newest_absent 1,901, pre_error 2, pre_fetched 42,478, pre_missing 2, pre_ondemand 23, step_candles 25, tb_built 40,660, tb_dropped 1,533, tb_empty 1,941, tb_fb_budget 21, tb_fb_error 2, tb_pending 2,193, tb_rebuilt 153, tb_replaced 39,029, tb_replaced_diff 6,128 |

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

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-18T12:07:06Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: 9,805.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.44% (166,640 verified of 167,580 attempted coin-minutes: built 162,492, verified empty 4,148; fallbacks: unverified 6, error 6, budget 928, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.4 s of 324 heartbeats; maximum 20 s or less in 95.4% (largest 35.6 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 174,510 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 404 of 174,510 coin-minutes

Totals: tb_replaced 158,184, tb_replaced_diff 25,764, tb_dropped 4,659.

## Fifth book against the fourth book

Period both ran: 2026-11-16 18:39 UTC to 2026-11-18 17:50 UTC (47.2 calendar hours; 47.2 hours with both live).

| Measure | Spot T18 | Spot R5 | R5 minus T18 |
|---|---|---|---|
| Rung fills | 1 | 1 | +0 |
| Rung fills per calendar day | 0.51 | 0.51 |  |
| Rung fills per running day | 0.51 | 0.51 |  |
| First-bid fills (rung 4) | 1 | 1 | +0 |
| Deeper rungs placed | 2 | 2 |  |
| Dollars bought | $20,814 | $20,833 | $19.13 |
| Exit P&L | -$98.22 | -$98.32 | -$0.10 |
| Net per dollar bought | -47.2 bp | -47.2 bp | -0.0 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 1 |
| Only in the fourth book | 0 |
| Only in the fifth book | 0 |

This comparison is for the record. The registered read is Part 3 of reports/owner/bar_source_prereg.md.

## Rule progress for the fifth book

Engine commit: 9e6f53b (full hash 9e6f53b3aca8c15307f22a357f19431bff053e4c), recorded 2026-11-18T12:15:45Z UTC.

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

| Part | Current value | Verdict |
|---|---|---|
| (a) Pairs that count, and the median of build minus release 3 | 9 pairs (8 needed); median -1.24 s; must be at or below 0.00 s | meets |

| Part | Current value | Verdict |
|---|---|---|
| (b) Against the main book, over the half hours both have a heartbeat (same heartbeat time) | fifth 8.59 s, main 11.13 s, 93 half hours; the fifth's must be no higher | meets |
| Reported, decides nothing: the fifth book's own median of its half-hour data-step medians | 8.59 s over 95 heartbeats; for comparison 10.3 s (release 3's figure of Nov 11 to 14, which moves with the period and the runner) | reported only |
| For information: against the fourth book, same way | fifth 8.58 s, fourth 13.11 s, 94 half hours | not part of the rule |

The read needs at least 100 heartbeats of the fifth book and at least 100 paired half hours with the main book for (b).

### Items 1 to 5 (measure 3)

Real-time minutes run so far: 2,845.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.87% (48,339 verified of 48,402 attempted coin-minutes: built 46,285, verified empty 2,054; fallbacks: unverified 0, error 3, budget 60, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step 30-minute maximum 20 s or less in 95% or more of heartbeats (the median is measure 1, see below) | median 8.6 s of 95 heartbeats; maximum 20 s or less in 98.9% (largest 22.4 s); the median is judged as measure 1 | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 51,138 coin-minutes, 18 coins) | meets |

### Measure 4, the candle requests between steps

| Part | Current value | Verdict |
|---|---|---|
| Counters, summed over the log | pre_fetched 48,239, pre_error 1, pre_missing 1, pre_ondemand 53, step_candles 54 |  |
| Failed requests (pre_error) against requests made (pre_fetched plus pre_error) | 1 of 48,240 = 0.002%; bar 1% or less | meets |
| Requests made inside a step (pre_missing plus pre_ondemand, first step after each start left out) against coin-minutes (18 times the minutes run) | 54 of 51,138 = 0.106%; bar 2% or less | meets |
| Left out: pre_missing of the first step after each start (at most 18 per start) | 0 left out, over 9 starts in the log |  |

## Sixth book against the fifth book

Period both ran: 2026-11-16 23:37 UTC to 2026-11-18 17:12 UTC (41.6 calendar hours; 41.6 hours with both live).

| Measure | Spot R5 | Spot TW | TW minus R5 |
|---|---|---|---|
| Rung fills | 1 | 1 | +0 |
| Rung fills per calendar day | 0.58 | 0.58 |  |
| Rung fills per running day | 0.58 | 0.58 |  |
| First-bid fills (rung 4) | 1 | 1 | +0 |
| Deeper rungs placed | 2 | 2 |  |
| Dollars bought | $20,833 | $20,833 | $0.00 |
| Exit P&L | -$98.32 | -$98.32 | $0.00 |
| Net per dollar bought | -47.2 bp | -47.2 bp | +0.0 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 1 |
| Only in the fifth book | 0 |
| Only in the sixth book | 0 |

This comparison is for the record. The registered read is Parts 3 and 4 of reports/owner/trades_workers_plan.md.

## Rule progress for the sixth book

Engine commit: 4c1717a (full hash 4c1717ac3cd711c3383e281ccb3eb2742f993b23), recorded 2026-11-18T11:22:46Z UTC.

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

| Part | Current value | Verdict |
|---|---|---|
| Jobs that count, and the slow one-worker passes | 9 jobs (8 needed); 1 slow one-worker passes (30 needed) | still waiting |
| 1. No harm: the median pass with three at most the median with one plus 0.05 s | three 2.60 s, one 2.62 s, over 273 and 275 steps | meets |
| 2. A gain in slow minutes: at least 30 slow one-worker passes, the three-worker share of slow passes at most half the one-worker share, fallbacks (in passes) not more with three than chance allows | slow passes 0 of 273 with three, 1 of 275 with one; fallback passes 0 with three, 0 with one (no more; coins 0 and 0) | does not meet yet |
| 3. The pace: over every file from the first job on, no three-worker step above 8 trades requests in one second, none limited or refused, every file readable | 9 files; most in one second 7; 0 files above 8; 0 with a limit or refusal; 0 unreadable | meets |
| 4. The rows: share of built bars differing from the venue's candle, three at most one point above one, or more only within chance (jobs with a complete comparison) | three 2103 of 4698 = 44.764%; one 2159 of 4680 = 46.132%; 9 jobs; no more | meets |
| Reported, decides nothing: median and mean pass, three minus one | median -0.01 s, mean -0.10 s (first version of the plan asked for a 0.2 s gain at the median over half-hour pairs) | reported only |

### Part 4, measure 2: items 1 to 5

Real-time minutes run so far: 2,495.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.95% (42,601 verified of 42,624 attempted coin-minutes: built 40,660, verified empty 1,941; fallbacks: unverified 0, error 2, budget 21, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step 30-minute maximum 20 s or less in 95% or more of heartbeats (the median is not judged for this book; the pairs decide the step) | median 8.5 s of 83 heartbeats; maximum 20 s or less in 98.8% (largest 21.2 s); the median is not judged here | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 44,694 coin-minutes, 18 coins) | meets |

### Part 4, measure 3: requests inside a step

| Part | Current value | Verdict |
|---|---|---|
| Failed requests (pre_error) against requests made (pre_fetched plus pre_error) | 2 of 42,480 = 0.005%; bar 1% or less | meets |
| Requests made inside a step (first step after each start left out) against coin-minutes (18 times the minutes run) | 25 of 44,694 = 0.056%; bar 2% or less | meets |

| Part | Current value | Verdict |
|---|---|---|
| In-step share against the fifth book's, over the half hours in which both have a heartbeat (the sixth's must be no higher) | sixth 25 of 44,694 = 0.056%, fifth 44 of 44,820 = 0.098%, 83 half hours | meets |

### Part 4, measure 4: stops

| Part | Current value | Verdict |
|---|---|---|
| Half hours with a rate-limit stop (tb_fb_limited above 0): none in the sixth book unless the fifth has one at the same heartbeat | sixth 0, fifth 0; sixth only: 0 | meets |
| Half hours with a request error (tb_fb_error above 0): the sixth's at most the fifth's plus 2 | sixth 1, fifth 2 | meets |

### Reported, decides nothing

| Part | Current value |
|---|---|
| The sixth book's own heartbeat entry step_s.trades (the trades pass's duration) | median of the half-hour medians 2.52 s, largest maximum 8.01 s, over 83 heartbeats |
| Data-step median over the half hours both books have a heartbeat (the runners differ, so the pairs decide the step) | sixth 8.52 s, fifth 8.59 s, 83 half hours |

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 11 | 0.90 | 1.09 | 62.9 bp | $10,144 | +1.44% | 80,016 |
| Perp R2-08 | 10 | 0.84 | 1.02 | 56.8 bp | $10,130 | +1.30% | 77,662 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

## Data notes

- Spot (main): event kinds not seen before: stale_input (3).
- Spot W2: event kinds not seen before: stale_input (3).
- Spot TB (trades input): event kinds not seen before: stale_input (1).
- Spot T18 (all coins on trades): event kinds not seen before: stale_input (4).
- Spot R5 (release 5 build): event kinds not seen before: stale_input (39).
- Spot TW (trades side by side): event kinds not seen before: stale_input (39).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
