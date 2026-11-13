# Paper trading status

Report made 2026-11-13 00:52 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-13 00:27 UTC | 0.4 h ago | ok |
| Spot W2 | 2026-11-13 00:27 UTC | 0.4 h ago | ok |
| Spot TB (trades input) | 2026-11-13 00:26 UTC | 0.4 h ago | ok |
| Spot T18 (all coins on trades) | 2026-11-12 21:30 UTC | 3.4 h ago | ok |
| Perp v1 (control) | 2026-11-13 00:52 UTC | 0.0 h ago | ok |
| Perp R2-08 | 2026-11-13 00:52 UTC | 0.0 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-13 00:27 UTC | 145.9 | 101.3 | 69.4% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-13 00:27 UTC | 143.7 | 99.1 | 69.0% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-13 00:26 UTC | 46.6 | 46.6 | 99.9% |
| Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-12 21:30 UTC | 23.1 | not derivable from this log | not derivable from this log |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-13 00:52 UTC | 154.3 | 103.7 | 67.2% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-13 00:52 UTC | 146.1 | 98.0 | 67.0% |

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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 0.4 h; Spot W2 0.4 h; Spot TB (trades input) 0.4 h; Spot T18 (all coins on trades) 3.4 h; Perp v1 (control) 0.0 h; Perp R2-08 0.0 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 6.1 | $251,692 | +0.68% | 33 | $216,149 | 78.3 bp | 47 / 10 | 19 (17 made money) | 1 |
| Spot W2 | 6.0 | $251,448 | +0.58% | 33 | $184,618 | 78.5 bp | 47 / 10 | 21 (19 made money) | 1 |
| Spot TB (trades input) | 1.9 | $250,141 | +0.06% | 2 | $20,884 | 67.5 bp | 2 / 0 | 2 (2 made money) | 0 |
| Spot T18 (all coins on trades) | 1.0 | $250,141 | +0.06% | 2 | $20,884 | 67.5 bp | 2 / 0 | 2 (2 made money) | 0 |
| Perp v1 (control) | 6.4 | $10,046 | +0.46% | 3 | n/a (not logged) | n/a | 2 / 1 | - | 0 |
| Perp R2-08 | 6.1 | $10,023 | +0.23% | 3 | n/a (not logged) | n/a | 2 / 1 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

| Measure | So far |
|---|---|
| Days (calendar) | 6.1 of 21 |
| Days in real time | 4.2 |
| Rungs | 33 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 5.43 per calendar day; 7.82 per running day |
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
| 2026-11-12 | $147.69 | 24.0 |
| 2026-11-13 | $0.00 | 0.5 |

Cash shortfalls: 11. Wanted $115,534 in total (average $10,503) against an average of $1,308 free.

Share of capital held by resting bids (committed over equity, mean of 198 heartbeats): 56.97%.

Largest single-day loss so far: -$3.06 on 2026-11-07.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 6.1 | 6.0 | -0.1 |
| Hours in real time | 101.3 | 99.1 |  |
| Equity | $251,692 | $251,448 | -$243.97 |
| Change | +0.68% | +0.58% | -0.10 pp |
| Rung fills | 33 | 33 | +0 |
| Rung fills per calendar day | 5.43 | 5.51 |  |
| Rung fills per running day | 7.82 | 7.99 |  |
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
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 923, btc_stale 1,023, candle_old 2,624, newest_absent 2,439 |
| 2026-11-13 | 30 | 1 | 10.5 | 14.9 | btc_candle_old 13, btc_stale 22, candle_old 85, newest_absent 75 |
| Total | 2,015 | 68 | 9.7 | 14.9 | btc_candle_old 1,197, btc_stale 1,509, candle_old 3,598, newest_absent 3,560 |

130 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot W2

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 575 | 20 | 10.1 | 13.1 | btc_candle_old 411, btc_stale 464, candle_old 1,919, newest_absent 1,046 |
| 2026-11-12 | 1,410 | 47 | 9.7 | 12.6 | btc_candle_old 893, btc_stale 1,023, candle_old 2,666, newest_absent 2,439 |
| 2026-11-13 | 30 | 1 | 10.5 | 14.9 | btc_candle_old 24, btc_stale 22, candle_old 135, newest_absent 75 |
| Total | 2,015 | 68 | 9.7 | 14.9 | btc_candle_old 1,328, btc_stale 1,509, candle_old 4,720, newest_absent 3,560 |

126 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot TB (trades input)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 1,273 | 43 | 10.2 | 23.9 | btc_candle_old 159, candle_old 182, newest_absent 1,336, rows_open 3, skip_old 96, tb_built 7,428, tb_close_diff 422, tb_insert 741, tb_rebuilt 5 |
| 2026-11-12 | 1,408 | 47 | 10.1 | 17.0 | btc_candle_old 399, candle_old 387, newest_absent 1,662, rows_open 11, skip_old 190, tb_built 8,202, tb_close_diff 440, tb_insert 909, tb_rebuilt 11 |
| 2026-11-13 | 30 | 1 | 10.5 | 14.7 | btc_candle_old 1, newest_absent 43, tb_built 180, tb_close_diff 9, tb_insert 19 |
| Total | 2,711 | 91 | 10.2 | 23.9 | btc_candle_old 559, candle_old 569, newest_absent 3,041, rows_open 14, skip_old 286, tb_built 15,810, tb_close_diff 871, tb_insert 1,669, tb_rebuilt 16 |

### Spot T18 (all coins on trades)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 90 | 3 | 13.8 | 17.5 | btc_candle_old 3, candle_old 17, newest_absent 4, tb_built 1,112, tb_close_diff 84, tb_dropped 4, tb_empty 4, tb_insert 13, tb_rebuilt 7, tb_replaced 1,095, tb_replaced_diff 125 |
| 2026-11-12 | 1,290 | 43 | 13.5 | 19.4 | btc_candle_old 51, candle_old 705, newest_absent 494, tb_built 22,183, tb_close_diff 1,054, tb_dropped 749, tb_empty 496, tb_fb_budget 1, tb_insert 1,040, tb_pending 31, tb_rebuilt 40, tb_replaced 21,403, tb_replaced_diff 3,630 |
| Total | 1,380 | 46 | 13.5 | 19.4 | btc_candle_old 54, candle_old 722, newest_absent 498, tb_built 23,295, tb_close_diff 1,138, tb_dropped 753, tb_empty 500, tb_fb_budget 1, tb_insert 1,053, tb_pending 31, tb_rebuilt 47, tb_replaced 22,498, tb_replaced_diff 3,755 |

## Third book against the main book

Period both ran: 2026-11-11 01:47 UTC to 2026-11-13 00:26 UTC (46.6 calendar hours; 34.9 hours with both live).

| Measure | Spot (main) | Spot TB | TB minus main |
|---|---|---|---|
| Rung fills | 12 | 2 | -10 |
| Rung fills per calendar day | 6.17 | 1.03 |  |
| Rung fills per running day | 8.23 | 1.03 |  |
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

Real-time minutes run so far: 2,795 of 4,000 (70%).

Listed coins for item 1: BTC, ETH, SOL, XRP, LTC, ZEC (read from bot/spot/config.tb.json).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 100.00% (15,810 verified of 15,810 attempted coin-minutes: built 15,810, verified empty 0; fallbacks: unverified 0, error 0, budget 0, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.2 s of 91 heartbeats; maximum 20 s or less in 98.9% (largest 23.9 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.029% (14 of 48,798 coin-minutes, 18 coins) | meets |
| 6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day | from the forward collector; computed at the read by scripts/owner/tb_rule6.py | not computed here |
| 7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both | from the reconciliation (scripts/owner/reconcile); not computed here | not computed here |

## Fourth book against the third book

Period both ran: 2026-11-11 22:25 UTC to 2026-11-12 21:30 UTC (23.1 calendar hours; hours with both live: not derivable from this log)

| Measure | Spot TB | Spot T18 | T18 minus TB |
|---|---|---|---|
| Rung fills | 2 | 2 | +0 |
| Rung fills per calendar day | 2.08 | 2.08 |  |
| Rung fills per running day | 2.08 | not derivable from this log |  |
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

Engine commit: 58eba8b (full hash 58eba8bde756e36cfdc51e2541c32b772496ff6f), recorded 2026-11-12T15:57:58Z UTC.

> Items 1 to 5 of the third book's rule are read for this book with 18 listed coins; item 3's median bar is 15 s (the 30-minute maximum stays 20 s or less in 95% or more of heartbeats). The values are provisional. The registered plan is reports/owner/bar_source_prereg.md.

Real-time minutes run so far: not derivable from this log.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 100.00% (23,795 verified of 23,796 attempted coin-minutes: built 23,295, verified empty 500; fallbacks: unverified 0, error 0, budget 1, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.5 s of 46 heartbeats; maximum 20 s or less in 100.0% (largest 19.4 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 24,840 coin-minutes, 18 coins) | meets |

Rows still built from trades 3 to 6 minutes on (tb_pending): 31 of 24,840 coin-minutes

Totals: tb_replaced 22,498, tb_replaced_diff 3,755, tb_dropped 753.

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 3 | 0.47 | 0.69 | 65.7 bp | $10,046 | +0.46% | 34,070 |
| Perp R2-08 | 3 | 0.49 | 0.73 | 33.0 bp | $10,023 | +0.23% | 31,869 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
