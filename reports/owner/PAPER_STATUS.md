# Paper trading status

Report made 2026-11-14 14:13 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-14 11:30 UTC | 2.7 h ago | ok |
| Spot W2 | 2026-11-14 11:30 UTC | 2.7 h ago | ok |
| Spot TB (trades input) | 2026-11-14 11:30 UTC | 2.7 h ago | ok |
| Spot T18 (all coins on trades) | 2026-11-14 08:46 UTC | 5.5 h ago | ok |
| Perp v1 (control) | 2026-11-14 11:56 UTC | 2.3 h ago | ok |
| Perp R2-08 | 2026-11-14 11:56 UTC | 2.3 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-14 11:30 UTC | 181.0 | 136.3 | 75.3% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-14 11:30 UTC | 178.8 | 134.1 | 75.0% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-14 11:30 UTC | 81.7 | 81.6 | 99.9% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-14 08:46 UTC | 58.4 | 58.4 | 100.0% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-14 11:56 UTC | 189.4 | 138.3 | 73.0% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-14 11:56 UTC | 181.2 | 132.6 | 73.2% |

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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 2.7 h; Spot W2 2.7 h; Spot TB (trades input) 2.7 h; Spot T18 (all coins on trades) 5.5 h; Perp v1 (control) 2.3 h; Perp R2-08 2.3 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 7.5 | $251,916 | +0.77% | 43 | $262,749 | 72.9 bp | 50 / 14 | 25 (22 made money) | 1 |
| Spot W2 | 7.4 | $251,618 | +0.65% | 41 | $219,712 | 73.7 bp | 49 / 14 | 27 (24 made money) | 1 |
| Spot TB (trades input) | 3.4 | $250,887 | +0.35% | 17 | $120,583 | 73.6 bp | 12 / 5 | 9 (8 made money) | 0 |
| Spot T18 (all coins on trades) | 2.4 | $250,919 | +0.37% | 18 | $124,988 | 73.5 bp | 13 / 5 | 10 (9 made money) | 0 |
| Perp v1 (control) | 7.9 | $10,057 | +0.57% | 4 | n/a (not logged) | n/a | 2 / 2 | - | 0 |
| Perp R2-08 | 7.5 | $10,034 | +0.34% | 4 | n/a (not logged) | n/a | 2 / 2 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

| Measure | So far |
|---|---|
| Days (calendar) | 7.5 of 21 |
| Days in real time | 5.7 |
| Rungs | 43 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 5.70 per calendar day; 7.57 per running day |
| Mean net per dollar | 72.9 bp |
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
| 4 | 35 | $213,340 | 54 | $1,333 | 62.5 bp |
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
| 2026-11-13 | $155.68 | 24.0 |
| 2026-11-14 | $67.54 | 11.5 |

Cash shortfalls: 11. Wanted $115,534 in total (average $10,503) against an average of $1,308 free.

Share of capital held by resting bids (committed over equity, mean of 268 heartbeats): 57.82%.

Largest single-day loss so far: -$3.06 on 2026-11-07.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 7.5 | 7.4 | -0.1 |
| Hours in real time | 136.3 | 134.1 |  |
| Equity | $251,916 | $251,618 | -$297.45 |
| Change | +0.77% | +0.65% | -0.12 pp |
| Rung fills | 43 | 41 | -2 |
| Rung fills per calendar day | 5.70 | 5.50 |  |
| Rung fills per running day | 7.57 | 7.34 |  |
| Dollars bought | $262,749 | $219,712 | -$43,038 |
| Net per dollar | 72.9 bp | 73.7 bp | +0.7 bp |
| Exit events TP / time | 50 / 14 | 49 / 14 |  |
| Ladders closed (made money) | 25 (22) | 27 (24) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): -$297.45.

A few days and a few dozen fills cannot separate the two weightings; a gap this size is within what chance alone produces.

## Data quality

From the heartbeats of each spot book (one every 30 minutes while it runs). Counters are summed per UTC day; a counter that is not listed was 0 or is not reported. Minutes run are the 30 minutes before each heartbeat, less any gap. After a start-up the first heartbeat covers fewer stepped minutes than that, so minutes run can overstate the steps by a few minutes per run; item 1 of the third book's rule is therefore computed from the counters themselves. Data step is the seconds after the minute at which the data step finished: the median of the heartbeat medians, and the largest heartbeat maximum.

### Spot (main)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 261, btc_stale 464, candle_old 889, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 923, btc_stale 1,023, candle_old 2,624, newest_absent 2,439 |
| 2026-11-13 | 1,408 | 47 | 10.1 | 14.9 | btc_candle_old 1,092, btc_stale 1,302, candle_old 2,499, newest_absent 3,287 |
| 2026-11-14 | 720 | 24 | 9.5 | 23.2 | btc_candle_old 404, btc_stale 501, candle_old 2,848, newest_absent 1,688 |
| Total | 4,113 | 138 | 9.7 | 23.2 | btc_candle_old 2,680, btc_stale 3,290, candle_old 8,860, newest_absent 8,460 |

130 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot W2

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 411, btc_stale 464, candle_old 1,919, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 893, btc_stale 1,023, candle_old 2,666, newest_absent 2,439 |
| 2026-11-13 | 1,408 | 47 | 10.1 | 14.9 | btc_candle_old 1,122, btc_stale 1,302, candle_old 2,663, newest_absent 3,287 |
| 2026-11-14 | 720 | 24 | 9.5 | 28.1 | btc_candle_old 452, btc_stale 501, candle_old 4,089, newest_absent 1,688 |
| Total | 4,113 | 138 | 9.7 | 28.1 | btc_candle_old 2,878, btc_stale 3,290, candle_old 11,337, newest_absent 8,460 |

126 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot TB (trades input)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 1,273 | 43 | 10.2 | 23.9 | btc_candle_old 159, candle_old 182, newest_absent 1,336, rows_open 3, skip_old 96, tb_built 7,428, tb_close_diff 422, tb_insert 741, tb_rebuilt 5 |
| 2026-11-12 | 1,408 | 47 | 10.1 | 17.0 | btc_candle_old 399, candle_old 387, newest_absent 1,662, rows_open 11, skip_old 190, tb_built 8,202, tb_close_diff 440, tb_insert 909, tb_rebuilt 11 |
| 2026-11-13 | 1,379 | 46 | 9.9 | 18.5 | btc_candle_old 571, candle_old 838, newest_absent 1,050, rows_open 1, skip_old 456, tb_built 8,046, tb_close_diff 491, tb_insert 939, tb_rebuilt 15 |
| 2026-11-14 | 720 | 24 | 10.9 | 28.4 | btc_candle_old 170, candle_old 89, newest_absent 680, skip_old 58, tb_built 4,092, tb_close_diff 220, tb_insert 256 |
| Total | 4,780 | 160 | 10.3 | 28.4 | btc_candle_old 1,299, candle_old 1,496, newest_absent 4,728, rows_open 15, skip_old 800, tb_built 27,768, tb_close_diff 1,573, tb_insert 2,845, tb_rebuilt 31 |

### Spot T18 (all coins on trades)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 65 | 3 | 13.8 | 17.5 | btc_candle_old 3, candle_old 17, newest_absent 4, tb_built 1,112, tb_close_diff 84, tb_dropped 4, tb_empty 4, tb_insert 13, tb_rebuilt 7, tb_replaced 1,095, tb_replaced_diff 125 |
| 2026-11-12 | 1,410 | 47 | 13.5 | 19.4 | btc_candle_old 58, candle_old 727, newest_absent 553, tb_built 23,888, tb_close_diff 1,133, tb_dropped 815, tb_empty 555, tb_fb_budget 1, tb_insert 1,138, tb_pending 35, tb_rebuilt 52, tb_replaced 23,032, tb_replaced_diff 3,927 |
| 2026-11-13 | 1,410 | 47 | 13.4 | 20.9 | btc_candle_old 438, candle_old 638, newest_absent 280, tb_built 24,304, tb_close_diff 1,049, tb_dropped 521, tb_empty 280, tb_fb_budget 3, tb_fb_unverified 1, tb_insert 1,219, tb_pending 78, tb_rebuilt 40, tb_replaced 23,747, tb_replaced_diff 3,493 |
| 2026-11-14 | 510 | 17 | 12.3 | 18.9 | btc_candle_old 78, candle_old 90, newest_absent 170, tb_built 8,957, tb_close_diff 267, tb_dropped 232, tb_empty 168, tb_fb_budget 19, tb_insert 555, tb_pending 13, tb_rebuilt 5, tb_replaced 8,709, tb_replaced_diff 1,397 |
| Total | 3,395 | 114 | 13.5 | 20.9 | btc_candle_old 577, candle_old 1,472, newest_absent 1,007, tb_built 58,261, tb_close_diff 2,533, tb_dropped 1,572, tb_empty 1,007, tb_fb_budget 23, tb_fb_unverified 1, tb_insert 2,925, tb_pending 126, tb_rebuilt 104, tb_replaced 56,583, tb_replaced_diff 8,942 |

## Third book against the main book

Period both ran: 2026-11-11 01:47 UTC to 2026-11-14 11:30 UTC (81.7 calendar hours; 69.9 hours with both live).

| Measure | Spot (main) | Spot TB | TB minus main |
|---|---|---|---|
| Rung fills | 22 | 17 | -5 |
| Rung fills per calendar day | 6.46 | 4.99 |  |
| Rung fills per running day | 7.54 | 5.00 |  |
| First-bid fills (rung 4) | 22 | 15 | -7 |
| Deeper rungs placed | 24 | 18 |  |
| Dollars bought | $72,561 | $120,583 | $48,022 |
| Exit P&L | $375.17 | $887.02 | $511.85 |
| Net per dollar bought | 51.7 bp | 73.6 bp | +21.9 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 7 |
| Only in the main book | 15 |
| Only in the third book | 8 |

This comparison is for the record. It is not the pass rule; the rule is below.

## Three-day rule progress for the third book

> Verified inputs (release 2): after the first three full days of real-time running (at least 4,000 minutes), items 1 to 7 below must all hold. The rule is in reports/owner/FORWARD_TESTS.md. Items 1 to 5 are computed here from the heartbeats; the values are provisional until the minutes are reached.

Real-time minutes run so far: 4,897 of 4,000 (122%).

Listed coins for item 1: BTC, ETH, SOL, XRP, LTC, ZEC (read from bot/spot/config.tb.json).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 100.00% (27,768 verified of 27,768 attempted coin-minutes: built 27,768, verified empty 0; fallbacks: unverified 0, error 0, budget 0, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.3 s of 160 heartbeats; maximum 20 s or less in 98.8% (largest 28.4 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.017% (15 of 86,040 coin-minutes, 18 coins) | meets |
| 6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day | from the forward collector; computed at the read by scripts/owner/tb_rule6.py | not computed here |
| 7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both | from the reconciliation (scripts/owner/reconcile); not computed here | not computed here |

## Fourth book against the third book

Period both ran: 2026-11-11 22:25 UTC to 2026-11-14 08:46 UTC (58.4 calendar hours; 58.3 hours with both live).

| Measure | Spot TB | Spot T18 | T18 minus TB |
|---|---|---|---|
| Rung fills | 17 | 18 | +1 |
| Rung fills per calendar day | 6.99 | 7.40 |  |
| Rung fills per running day | 7.00 | 7.40 |  |
| First-bid fills (rung 4) | 15 | 16 | +1 |
| Deeper rungs placed | 18 | 20 |  |
| Dollars bought | $120,583 | $124,988 | $4,405 |
| Exit P&L | $887.02 | $918.69 | $31.67 |
| Net per dollar bought | 73.6 bp | 73.5 bp | -0.1 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 15 |
| Only in the third book | 0 |
| Only in the fourth book | 1 |

This comparison is for the record. The registered read is in reports/owner/bar_source_prereg.md.

## Rule progress for the fourth book

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-14T02:59:49Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: 3,501.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.96% (59,268 verified of 59,292 attempted coin-minutes: built 58,261, verified empty 1,007; fallbacks: unverified 1, error 0, budget 23, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.5 s of 114 heartbeats; maximum 20 s or less in 98.2% (largest 20.9 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 61,110 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 126 of 61,110 coin-minutes

Totals: tb_replaced 56,583, tb_replaced_diff 8,942, tb_dropped 1,572.

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 4 | 0.51 | 0.69 | 63.6 bp | $10,057 | +0.57% | 45,723 |
| Perp R2-08 | 4 | 0.53 | 0.72 | 39.1 bp | $10,034 | +0.34% | 43,462 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
