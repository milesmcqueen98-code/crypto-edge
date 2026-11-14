# Paper trading status

Report made 2026-11-14 00:15 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-13 23:36 UTC | 0.7 h ago | ok |
| Spot W2 | 2026-11-13 23:36 UTC | 0.7 h ago | ok |
| Spot TB (trades input) | 2026-11-13 23:35 UTC | 0.7 h ago | ok |
| Spot T18 (all coins on trades) | 2026-11-13 21:07 UTC | 3.1 h ago | ok |
| Perp v1 (control) | 2026-11-14 00:15 UTC | 0.0 h ago | ok |
| Perp R2-08 | 2026-11-14 00:15 UTC | 0.0 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-13 23:36 UTC | 169.1 | 124.4 | 73.6% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-13 23:36 UTC | 166.9 | 122.2 | 73.3% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-13 23:35 UTC | 69.8 | 69.7 | 99.9% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-13 21:07 UTC | 46.7 | 46.7 | 100.0% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-14 00:15 UTC | 177.7 | 126.8 | 71.4% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-14 00:15 UTC | 169.5 | 121.0 | 71.4% |

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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 0.7 h; Spot W2 0.7 h; Spot TB (trades input) 0.7 h; Spot T18 (all coins on trades) 3.1 h; Perp v1 (control) 0.0 h; Perp R2-08 0.0 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 7.0 | $251,848 | +0.74% | 35 | $242,092 | 76.3 bp | 50 / 10 | 21 (19 made money) | 1 |
| Spot W2 | 7.0 | $251,565 | +0.63% | 35 | $204,060 | 76.7 bp | 49 / 10 | 23 (21 made money) | 1 |
| Spot TB (trades input) | 2.9 | $250,433 | +0.17% | 4 | $62,574 | 69.3 bp | 4 / 0 | 3 (3 made money) | 0 |
| Spot T18 (all coins on trades) | 1.9 | $250,465 | +0.19% | 5 | $66,979 | 69.4 bp | 5 / 0 | 4 (4 made money) | 0 |
| Perp v1 (control) | 7.4 | $10,046 | +0.46% | 3 | n/a (not logged) | n/a | 2 / 1 | - | 0 |
| Perp R2-08 | 7.1 | $10,023 | +0.23% | 3 | n/a (not logged) | n/a | 2 / 1 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

| Measure | So far |
|---|---|
| Days (calendar) | 7.0 of 21 |
| Days in real time | 5.2 |
| Rungs | 35 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 4.97 per calendar day; 6.75 per running day |
| Mean net per dollar | 76.3 bp |
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
| 4 | 27 | $192,683 | 50 | $1,266 | 65.7 bp |
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
| 2026-11-12 | $147.69 | 24.0 |
| 2026-11-13 | $155.68 | 23.6 |

Cash shortfalls: 11. Wanted $115,534 in total (average $10,503) against an average of $1,308 free.

Share of capital held by resting bids (committed over equity, mean of 244 heartbeats): 57.44%.

Largest single-day loss so far: -$3.06 on 2026-11-07.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 7.0 | 7.0 | -0.1 |
| Hours in real time | 124.4 | 122.2 |  |
| Equity | $251,848 | $251,565 | -$282.98 |
| Change | +0.74% | +0.63% | -0.11 pp |
| Rung fills | 35 | 35 | +0 |
| Rung fills per calendar day | 4.97 | 5.03 |  |
| Rung fills per running day | 6.75 | 6.87 |  |
| Dollars bought | $242,092 | $204,060 | -$38,032 |
| Net per dollar | 76.3 bp | 76.7 bp | +0.4 bp |
| Exit events TP / time | 50 / 10 | 49 / 10 |  |
| Ladders closed (made money) | 21 (19) | 23 (21) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): -$282.98.

A few days and a few dozen fills cannot separate the two weightings; a gap this size is within what chance alone produces.

## Data quality

From the heartbeats of each spot book (one every 30 minutes while it runs). Counters are summed per UTC day; a counter that is not listed was 0 or is not reported. Minutes run are the 30 minutes before each heartbeat, less any gap. After a start-up the first heartbeat covers fewer stepped minutes than that, so minutes run can overstate the steps by a few minutes per run; item 1 of the third book's rule is therefore computed from the counters themselves. Data step is the seconds after the minute at which the data step finished: the median of the heartbeat medians, and the largest heartbeat maximum.

### Spot (main)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 261, btc_stale 464, candle_old 889, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 923, btc_stale 1,023, candle_old 2,624, newest_absent 2,439 |
| 2026-11-13 | 1,408 | 47 | 10.1 | 14.9 | btc_candle_old 1,092, btc_stale 1,302, candle_old 2,499, newest_absent 3,287 |
| Total | 3,393 | 114 | 9.7 | 14.9 | btc_candle_old 2,276, btc_stale 2,789, candle_old 6,012, newest_absent 6,772 |

130 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot W2

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 411, btc_stale 464, candle_old 1,919, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 893, btc_stale 1,023, candle_old 2,666, newest_absent 2,439 |
| 2026-11-13 | 1,408 | 47 | 10.1 | 14.9 | btc_candle_old 1,122, btc_stale 1,302, candle_old 2,663, newest_absent 3,287 |
| Total | 3,393 | 114 | 9.7 | 14.9 | btc_candle_old 2,426, btc_stale 2,789, candle_old 7,248, newest_absent 6,772 |

126 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot TB (trades input)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 1,273 | 43 | 10.2 | 23.9 | btc_candle_old 159, candle_old 182, newest_absent 1,336, rows_open 3, skip_old 96, tb_built 7,428, tb_close_diff 422, tb_insert 741, tb_rebuilt 5 |
| 2026-11-12 | 1,408 | 47 | 10.1 | 17.0 | btc_candle_old 399, candle_old 387, newest_absent 1,662, rows_open 11, skip_old 190, tb_built 8,202, tb_close_diff 440, tb_insert 909, tb_rebuilt 11 |
| 2026-11-13 | 1,379 | 46 | 9.9 | 18.5 | btc_candle_old 571, candle_old 838, newest_absent 1,050, rows_open 1, skip_old 456, tb_built 8,046, tb_close_diff 491, tb_insert 939, tb_rebuilt 15 |
| Total | 4,060 | 136 | 10.0 | 23.9 | btc_candle_old 1,129, candle_old 1,407, newest_absent 4,048, rows_open 15, skip_old 742, tb_built 23,676, tb_close_diff 1,353, tb_insert 2,589, tb_rebuilt 31 |

### Spot T18 (all coins on trades)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 65 | 3 | 13.8 | 17.5 | btc_candle_old 3, candle_old 17, newest_absent 4, tb_built 1,112, tb_close_diff 84, tb_dropped 4, tb_empty 4, tb_insert 13, tb_rebuilt 7, tb_replaced 1,095, tb_replaced_diff 125 |
| 2026-11-12 | 1,410 | 47 | 13.5 | 19.4 | btc_candle_old 58, candle_old 727, newest_absent 553, tb_built 23,888, tb_close_diff 1,133, tb_dropped 815, tb_empty 555, tb_fb_budget 1, tb_insert 1,138, tb_pending 35, tb_rebuilt 52, tb_replaced 23,032, tb_replaced_diff 3,927 |
| 2026-11-13 | 1,260 | 42 | 12.4 | 20.9 | btc_candle_old 435, candle_old 603, newest_absent 245, tb_built 21,855, tb_close_diff 887, tb_dropped 470, tb_empty 245, tb_fb_budget 3, tb_fb_unverified 1, tb_insert 1,158, tb_pending 74, tb_rebuilt 37, tb_replaced 21,365, tb_replaced_diff 3,181 |
| Total | 2,735 | 92 | 13.5 | 20.9 | btc_candle_old 496, candle_old 1,347, newest_absent 802, tb_built 46,855, tb_close_diff 2,104, tb_dropped 1,289, tb_empty 804, tb_fb_budget 4, tb_fb_unverified 1, tb_insert 2,309, tb_pending 109, tb_rebuilt 96, tb_replaced 45,492, tb_replaced_diff 7,233 |

## Third book against the main book

Period both ran: 2026-11-11 01:47 UTC to 2026-11-13 23:35 UTC (69.8 calendar hours; 58.0 hours with both live).

| Measure | Spot (main) | Spot TB | TB minus main |
|---|---|---|---|
| Rung fills | 14 | 4 | -10 |
| Rung fills per calendar day | 4.81 | 1.38 |  |
| Rung fills per running day | 5.78 | 1.38 |  |
| First-bid fills (rung 4) | 14 | 3 | -11 |
| Deeper rungs placed | 16 | 6 |  |
| Dollars bought | $51,904 | $62,574 | $10,670 |
| Exit P&L | $307.63 | $433.46 | $125.83 |
| Net per dollar bought | 59.3 bp | 69.3 bp | +10.0 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 1 |
| Only in the main book | 13 |
| Only in the third book | 2 |

This comparison is for the record. It is not the pass rule; the rule is below.

## Three-day rule progress for the third book

> Verified inputs (release 2): after the first three full days of real-time running (at least 4,000 minutes), items 1 to 7 below must all hold. The rule is in reports/owner/FORWARD_TESTS.md. Items 1 to 5 are computed here from the heartbeats; the values are provisional until the minutes are reached.

Real-time minutes run so far: 4,182 of 4,000 (105%).

Listed coins for item 1: BTC, ETH, SOL, XRP, LTC, ZEC (read from bot/spot/config.tb.json).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 100.00% (23,676 verified of 23,676 attempted coin-minutes: built 23,676, verified empty 0; fallbacks: unverified 0, error 0, budget 0, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.0 s of 136 heartbeats; maximum 20 s or less in 99.3% (largest 23.9 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.021% (15 of 73,080 coin-minutes, 18 coins) | meets |
| 6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day | from the forward collector; computed at the read by scripts/owner/tb_rule6.py | not computed here |
| 7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both | from the reconciliation (scripts/owner/reconcile); not computed here | not computed here |

## Fourth book against the third book

Period both ran: 2026-11-11 22:25 UTC to 2026-11-13 21:07 UTC (46.7 calendar hours; 46.6 hours with both live).

| Measure | Spot TB | Spot T18 | T18 minus TB |
|---|---|---|---|
| Rung fills | 4 | 5 | +1 |
| Rung fills per calendar day | 2.06 | 2.57 |  |
| Rung fills per running day | 2.06 | 2.57 |  |
| First-bid fills (rung 4) | 3 | 4 | +1 |
| Deeper rungs placed | 6 | 8 |  |
| Dollars bought | $62,574 | $66,979 | $4,405 |
| Exit P&L | $433.46 | $465.13 | $31.67 |
| Net per dollar bought | 69.3 bp | 69.4 bp | +0.2 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 3 |
| Only in the third book | 0 |
| Only in the fourth book | 1 |

This comparison is for the record. The registered read is in reports/owner/bar_source_prereg.md.

## Rule progress for the fourth book

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-13T15:17:52Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: 2,802.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.99% (47,659 verified of 47,664 attempted coin-minutes: built 46,855, verified empty 804; fallbacks: unverified 1, error 0, budget 4, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.5 s of 92 heartbeats; maximum 20 s or less in 97.8% (largest 20.9 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 49,230 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 109 of 49,230 coin-minutes

Totals: tb_replaced 45,492, tb_replaced_diff 7,233, tb_dropped 1,289.

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 3 | 0.41 | 0.57 | 65.7 bp | $10,046 | +0.46% | 41,761 |
| Perp R2-08 | 3 | 0.42 | 0.59 | 33.0 bp | $10,023 | +0.23% | 39,528 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
