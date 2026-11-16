# Paper trading status

Report made 2026-11-16 04:49 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-16 04:00 UTC | 0.8 h ago | ok |
| Spot W2 | 2026-11-16 04:00 UTC | 0.8 h ago | ok |
| Spot TB (trades input) | 2026-11-16 04:00 UTC | 0.8 h ago | ok |
| Spot T18 (all coins on trades) | 2026-11-16 01:35 UTC | 3.2 h ago | ok |
| Perp v1 (control) | 2026-11-16 04:49 UTC | 0.0 h ago | ok |
| Perp R2-08 | 2026-11-16 04:49 UTC | 0.0 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-16 04:00 UTC | 221.5 | 176.8 | 79.8% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-16 04:00 UTC | 219.3 | 174.6 | 79.6% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-16 04:00 UTC | 122.2 | 122.0 | 99.9% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-16 01:35 UTC | 99.2 | 99.2 | 100.0% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-16 04:49 UTC | 230.2 | 178.7 | 77.6% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-16 04:49 UTC | 222.1 | 172.9 | 77.9% |

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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 0.8 h; Spot W2 0.8 h; Spot TB (trades input) 0.8 h; Spot T18 (all coins on trades) 3.2 h; Perp v1 (control) 0.0 h; Perp R2-08 0.0 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 9.2 | $251,067 | +0.43% | 89 | $631,533 | 16.9 bp | 70 / 46 | 52 (32 made money) | 1 |
| Spot W2 | 9.1 | $251,128 | +0.45% | 86 | $538,306 | 21.0 bp | 64 / 46 | 54 (35 made money) | 1 |
| Spot TB (trades input) | 5.1 | $249,964 | -0.01% | 70 | $537,290 | -0.7 bp | 33 / 35 | 37 (22 made money) | 0 |
| Spot T18 (all coins on trades) | 4.1 | $249,771 | -0.09% | 72 | $539,242 | -4.3 bp | 30 / 35 | 38 (23 made money) | 0 |
| Perp v1 (control) | 9.6 | $10,144 | +1.44% | 11 | n/a (not logged) | n/a | 4 / 7 | - | 0 |
| Perp R2-08 | 9.3 | $10,130 | +1.30% | 10 | n/a (not logged) | n/a | 4 / 6 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

Rule A is counted from 2026-11-14 17:27 UTC; see the section below.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

Counted from 2026-11-14 17:27 UTC (release 3): the main book's inputs changed then. The registered rule is counted again from that time (reports/owner/FORWARD_TESTS.md).

| Measure | So far |
|---|---|
| Days (calendar) | 1.4 of 21 |
| Days in real time | 1.4 |
| Rungs | 27 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 18.76 per calendar day; 18.76 per running day |
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
| 2026-11-16 | $0.00 | 4.0 |

Cash shortfalls: 31. Wanted $214,854 in total (average $6,931) against an average of $466.74 free.

Share of capital held by resting bids (committed over equity, mean of 349 heartbeats): 58.94%.

Largest single-day loss so far: -$781.37 on 2026-11-14.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 9.2 | 9.1 | -0.1 |
| Hours in real time | 176.8 | 174.6 |  |
| Equity | $251,067 | $251,128 | $61.66 |
| Change | +0.43% | +0.45% | +0.02 pp |
| Rung fills | 89 | 86 | -3 |
| Rung fills per calendar day | 9.64 | 9.41 |  |
| Rung fills per running day | 12.08 | 11.82 |  |
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
| 2026-11-16 | 270 | 9 | 10.2 | 17.3 | btc_candle_old 101, candle_old 49, newest_absent 213, skip_old 15, tb_built 1,350, tb_close_diff 67, tb_insert 308 |
| Total | 6,543 | 219 | 10.1 | 23.2 | btc_candle_old 3,527, btc_stale 3,614, candle_old 13,991, newest_absent 10,876, skip_old 837, tb_built 9,988, tb_close_diff 624, tb_empty 3, tb_fb_budget 19, tb_fb_error 1, tb_fb_unverified 4, tb_insert 1,028, tb_rebuilt 10 |

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
| 2026-11-16 | 270 | 9 | 10.2 | 17.2 | btc_candle_old 190, candle_old 89, newest_absent 213, skip_old 24, tb_built 1,350, tb_close_diff 67, tb_insert 308 |
| Total | 6,543 | 219 | 10.1 | 28.1 | btc_candle_old 3,759, btc_stale 3,614, candle_old 15,740, newest_absent 10,876, skip_old 861, tb_built 9,991, tb_close_diff 624, tb_empty 3, tb_fb_budget 16, tb_fb_error 1, tb_fb_unverified 4, tb_insert 1,028, tb_rebuilt 6 |

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
| 2026-11-16 | 270 | 9 | 12.1 | 20.9 | btc_candle_old 24, candle_old 328, newest_absent 219, skip_old 224, tb_built 1,620, tb_close_diff 137, tb_insert 15 |
| Total | 7,206 | 241 | 10.5 | 28.4 | btc_candle_old 1,878, btc_stale 1, candle_old 2,485, newest_absent 6,289, rows_open 16, skip_old 1,412, tb_built 41,720, tb_close_diff 2,277, tb_empty 3, tb_fb_budget 27, tb_fb_unverified 4, tb_insert 4,232, tb_rebuilt 42 |

### Spot T18 (all coins on trades)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 65 | 3 | 13.8 | 17.5 | btc_candle_old 3, candle_old 17, newest_absent 4, tb_built 1,112, tb_close_diff 84, tb_dropped 4, tb_empty 4, tb_insert 13, tb_rebuilt 7, tb_replaced 1,095, tb_replaced_diff 125 |
| 2026-11-12 | 1,410 | 47 | 13.5 | 19.4 | btc_candle_old 58, candle_old 727, newest_absent 553, tb_built 23,888, tb_close_diff 1,133, tb_dropped 815, tb_empty 555, tb_fb_budget 1, tb_insert 1,138, tb_pending 35, tb_rebuilt 52, tb_replaced 23,032, tb_replaced_diff 3,927 |
| 2026-11-13 | 1,410 | 47 | 13.4 | 20.9 | btc_candle_old 438, candle_old 638, newest_absent 280, tb_built 24,304, tb_close_diff 1,049, tb_dropped 521, tb_empty 280, tb_fb_budget 3, tb_fb_unverified 1, tb_insert 1,219, tb_pending 78, tb_rebuilt 40, tb_replaced 23,747, tb_replaced_diff 3,493 |
| 2026-11-14 | 1,410 | 47 | 13.3 | 23.4 | btc_candle_old 159, candle_old 275, newest_absent 378, skip_old 4, tb_built 24,017, tb_close_diff 915, tb_dropped 482, tb_empty 375, tb_fb_budget 247, tb_fb_unverified 3, tb_insert 1,203, tb_pending 31, tb_rebuilt 16, tb_replaced 23,471, tb_replaced_diff 3,098 |
| 2026-11-15 | 1,440 | 48 | 13.5 | 24.6 | btc_candle_old 289, btc_stale 2, candle_old 207, newest_absent 412, skip_old 1, tb_built 23,943, tb_close_diff 979, tb_dropped 601, tb_empty 390, tb_fb_budget 324, tb_fb_error 1, tb_fb_unverified 2, tb_insert 1,343, tb_pending 50, tb_rebuilt 48, tb_replaced 23,301, tb_replaced_diff 3,693 |
| 2026-11-16 | 120 | 4 | 14.9 | 19.6 | btc_candle_old 62, candle_old 27, newest_absent 37, skip_old 2, tb_built 2,077, tb_close_diff 45, tb_dropped 40, tb_empty 31, tb_fb_budget 52, tb_insert 176, tb_pending 3, tb_rebuilt 4, tb_replaced 2,042, tb_replaced_diff 324 |
| Total | 5,855 | 196 | 13.5 | 24.6 | btc_candle_old 1,009, btc_stale 2, candle_old 1,891, newest_absent 1,664, skip_old 7, tb_built 99,341, tb_close_diff 4,205, tb_dropped 2,463, tb_empty 1,635, tb_fb_budget 627, tb_fb_error 1, tb_fb_unverified 6, tb_insert 5,092, tb_pending 197, tb_rebuilt 167, tb_replaced 96,688, tb_replaced_diff 14,660 |

Heartbeats with a trades error (tb_err): 1. Last: BTC: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=3)"))

## Third book against the main book

Period both ran: 2026-11-11 01:47 UTC to 2026-11-16 04:00 UTC (122.2 calendar hours; 110.3 hours with both live).

| Measure | Spot (main) | Spot TB | TB minus main |
|---|---|---|---|
| Rung fills | 68 | 70 | +2 |
| Rung fills per calendar day | 13.35 | 13.75 |  |
| Rung fills per running day | 14.77 | 13.76 |  |
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

> Verified inputs (release 2): after the first three full days of real-time running (at least 4,000 minutes), items 1 to 7 below must all hold. The rule is in reports/owner/FORWARD_TESTS.md. Items 1 to 5 are computed here from the heartbeats; the values are provisional until the minutes are reached.

Real-time minutes run so far: 7,323 of 4,000 (183%).

Listed coins for item 1: BTC, ETH, SOL, XRP, LTC, ZEC (read from bot/spot/config.tb.json).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.93% (41,723 verified of 41,754 attempted coin-minutes: built 41,720, verified empty 3; fallbacks: unverified 4, error 0, budget 27, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.5 s of 241 heartbeats; maximum 20 s or less in 98.8% (largest 28.4 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.012% (16 of 129,708 coin-minutes, 18 coins) | meets |
| 6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day | from the forward collector; computed at the read by scripts/owner/tb_rule6.py | not computed here |
| 7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both | from the reconciliation (scripts/owner/reconcile); not computed here | not computed here |

## Fourth book against the third book

Period both ran: 2026-11-11 22:25 UTC to 2026-11-16 01:35 UTC (99.2 calendar hours; 99.0 hours with both live).

| Measure | Spot TB | Spot T18 | T18 minus TB |
|---|---|---|---|
| Rung fills | 70 | 72 | +2 |
| Rung fills per calendar day | 16.94 | 17.43 |  |
| Rung fills per running day | 16.96 | 17.43 |  |
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

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-15T19:53:57Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: 5,950.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.38% (100,976 verified of 101,610 attempted coin-minutes: built 99,341, verified empty 1,635; fallbacks: unverified 6, error 1, budget 627, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.5 s of 196 heartbeats; maximum 20 s or less in 96.4% (largest 24.6 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 105,390 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 197 of 105,390 coin-minutes

Totals: tb_replaced 96,688, tb_replaced_diff 14,660, tb_dropped 2,463.

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 11 | 1.15 | 1.48 | 62.9 bp | $10,144 | +1.44% | 58,723 |
| Perp R2-08 | 10 | 1.08 | 1.39 | 56.8 bp | $10,130 | +1.30% | 56,429 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

## Data notes

- Spot TB (trades input): event kinds not seen before: stale_input (1).
- Spot T18 (all coins on trades): event kinds not seen before: stale_input (2).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
