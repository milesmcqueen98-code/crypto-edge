# Paper trading status

Report made 2026-11-11 22:24 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-11 13:15 UTC | 9.2 h ago | STALE |
| Spot W2 | 2026-11-11 13:15 UTC | 9.2 h ago | STALE |
| Spot TB (trades input) | 2026-11-11 19:18 UTC | 3.1 h ago | ok |
| Perp v1 (control) | 2026-11-11 19:17 UTC | 3.1 h ago | ok |
| Perp R2-08 | 2026-11-11 19:17 UTC | 3.1 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-11 13:15 UTC | 110.8 | 72.0 | 65.0% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-11 13:15 UTC | 108.5 | 69.8 | 64.3% |
| Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-11 19:18 UTC | 17.5 | 17.5 | 99.8% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-11 19:17 UTC | 124.7 | 74.9 | 60.1% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-11 19:17 UTC | 116.5 | 69.2 | 59.3% |

The five longest gaps of each book (a gap is the time the book was not running before a restart):

| Book | Gap start | Hours |
|---|---|---|
| Spot (main) | 2026-11-09 12:55 UTC | 9.7 |
| Spot (main) | 2026-11-10 13:30 UTC | 6.5 |
| Spot (main) | 2026-11-07 06:33 UTC | 6.0 |
| Spot (main) | 2026-11-11 01:47 UTC | 5.8 |
| Spot (main) | 2026-11-08 12:25 UTC | 5.6 |
| Spot W2 | 2026-11-09 12:55 UTC | 9.7 |
| Spot W2 | 2026-11-10 13:30 UTC | 6.5 |
| Spot W2 | 2026-11-07 06:33 UTC | 6.0 |
| Spot W2 | 2026-11-11 01:47 UTC | 5.8 |
| Spot W2 | 2026-11-08 12:25 UTC | 5.6 |
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

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 9.2 h; Spot W2 9.2 h; Spot TB (trades input) 3.1 h; Perp v1 (control) 3.1 h; Perp R2-08 3.1 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 4.6 | $251,540 | +0.62% | 21 | $190,188 | 81.0 bp | 25 / 8 | 13 (12 made money) | 1 |
| Spot W2 | 4.5 | $251,330 | +0.53% | 22 | $164,904 | 80.7 bp | 27 / 8 | 15 (14 made money) | 1 |
| Spot TB (trades input) | 0.7 | $250,000 | +0.00% | 0 | $0.00 | n/a | 0 / 0 | 0 (0 made money) | 0 |
| Perp v1 (control) | 5.2 | $10,011 | +0.11% | 2 | n/a (not logged) | n/a | 1 / 1 | - | 0 |
| Perp R2-08 | 4.9 | $9,988 | -0.12% | 2 | n/a (not logged) | n/a | 1 / 1 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

| Measure | So far |
|---|---|
| Days (calendar) | 4.6 of 21 |
| Days in real time | 3.0 |
| Rungs | 21 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 4.55 per calendar day; 7.00 per running day |
| Mean net per dollar | 81.0 bp |
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
| 4 | 13 | $140,779 | 23 | $958.28 | 68.1 bp |
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
| 2026-11-11 | $0.00 | 7.4 |

Cash shortfalls: 11. Wanted $115,534 in total (average $10,503) against an average of $1,308 free.

Share of capital held by resting bids (committed over equity, mean of 141 heartbeats): 55.15%.

Largest single-day loss so far: -$3.06 on 2026-11-07.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 4.6 | 4.5 | -0.1 |
| Hours in real time | 72.0 | 69.8 |  |
| Equity | $251,540 | $251,330 | -$210.10 |
| Change | +0.62% | +0.53% | -0.08 pp |
| Rung fills | 21 | 22 | +1 |
| Rung fills per calendar day | 4.55 | 4.87 |  |
| Rung fills per running day | 7.00 | 7.57 |  |
| Dollars bought | $190,188 | $164,904 | -$25,283 |
| Net per dollar | 81.0 bp | 80.7 bp | -0.3 bp |
| Exit events TP / time | 25 / 8 | 27 / 8 |  |
| Ladders closed (made money) | 13 (12) | 15 (14) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): -$210.10.

A few days and a few dozen fills cannot separate the two weightings; a gap this size is within what chance alone produces.

## Data quality

From the heartbeats of each spot book (one every 30 minutes while it runs). Counters are summed per UTC day; a counter that is not listed was 0 or is not reported. Minutes run are the 30 minutes before each heartbeat, less any gap. After a start-up the first heartbeat covers fewer stepped minutes than that, so minutes run can overstate the steps by a few minutes per run; item 1 of the third book's rule is therefore computed from the counters themselves. Data step is the seconds after the minute at which the data step finished: the median of the heartbeat medians, and the largest heartbeat maximum.

### Spot (main)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 323 | 11 | 10.3 | 13.1 | btc_candle_old 124, btc_stale 279, candle_old 708, newest_absent 720 |
| Total | 323 | 11 | 10.3 | 13.1 | btc_candle_old 124, btc_stale 279, candle_old 708, newest_absent 720 |

130 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot W2

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 323 | 11 | 10.3 | 13.1 | btc_candle_old 285, btc_stale 279, candle_old 1,760, newest_absent 720 |
| Total | 323 | 11 | 10.3 | 13.1 | btc_candle_old 285, btc_stale 279, candle_old 1,760, newest_absent 720 |

126 earlier heartbeat(s) carry none of these fields and are not counted.

### Spot TB (trades input)

| Day (UTC) | Minutes run | Heartbeats | Data step median (s) | Data step largest max (s) | Counters (sum) |
|---|---|---|---|---|---|
| 2026-11-11 | 1,003 | 34 | 10.4 | 23.9 | btc_candle_old 37, candle_old 110, newest_absent 1,146, skip_old 62, tb_built 5,928, tb_close_diff 350, tb_insert 535 |
| Total | 1,003 | 34 | 10.4 | 23.9 | btc_candle_old 37, candle_old 110, newest_absent 1,146, skip_old 62, tb_built 5,928, tb_close_diff 350, tb_insert 535 |

## Third book against the main book

Period both ran: 2026-11-11 01:47 UTC to 2026-11-11 13:15 UTC (11.5 calendar hours; 5.6 hours with both live).

| Measure | Spot (main) | Spot TB | TB minus main |
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
| Only in the main book | 0 |
| Only in the third book | 0 |

This comparison is for the record. It is not the pass rule; the rule is below.

## Three-day rule progress for the third book

> Verified inputs (release 2): after the first three full days of real-time running (at least 4,000 minutes), items 1 to 7 below must all hold. The rule is in reports/owner/FORWARD_TESTS.md. Items 1 to 5 are computed here from the heartbeats; the values are provisional until the minutes are reached.

Real-time minutes run so far: 1,049 of 4,000 (26%).

Listed coins for item 1: BTC, ETH, SOL, XRP, LTC, ZEC (read from bot/spot/config.tb.json).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 100.00% (5,928 verified of 5,928 attempted coin-minutes: built 5,928, verified empty 0; fallbacks: unverified 0, error 0, budget 0, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.4 s of 34 heartbeats; maximum 20 s or less in 97.1% (largest 23.9 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 18,054 coin-minutes, 18 coins) | meets |
| 6. On the collector's record: BTC's trades bar is materially off in 1% of minutes or less; every other listed coin's trades bar is materially off less often and exactly equal more often than its own first-seen candle, on every day | from the forward collector; computed at the read by scripts/owner/tb_rule6.py | not computed here |
| 7. On the reconciliation of both books over the minutes both were live: the share of new bids more than 5 bp from the research level, and the share whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both | from the reconciliation (scripts/owner/reconcile); not computed here | not computed here |

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 2 | 0.38 | 0.64 | 12.0 bp | $10,011 | +0.11% | 24,851 |
| Perp R2-08 | 2 | 0.41 | 0.69 | -36.7 bp | $9,988 | -0.12% | 22,666 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
