# Paper trading status

Report made 2026-11-10 19:07 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-10 13:30 UTC | 5.6 h ago | ok |
| Spot W2 | 2026-11-10 13:30 UTC | 5.6 h ago | ok |
| Perp v1 (control) | 2026-11-10 06:55 UTC | 12.2 h ago | STALE |
| Perp R2-08 | 2026-11-10 06:55 UTC | 12.2 h ago | STALE |

A book is flagged STALE when its newest event is more than 8 hours old.

## Running time

GitHub drops scheduled runs. While a book is not running it places no new bids; when it starts again it only settles what was already open. So the books were live in real time for only part of the calendar time, and every rate per calendar day below understates the rate while running. Rates are given both ways.

| Book | First event | Last event | Calendar hours | Hours in real time | Share |
|---|---|---|---|---|---|
| Spot (main) | 2026-11-06 22:30 UTC | 2026-11-10 13:30 UTC | 87.0 | 60.5 | 69.5% |
| Spot W2 | 2026-11-07 00:44 UTC | 2026-11-10 13:30 UTC | 84.8 | 58.3 | 68.8% |
| Perp v1 (control) | 2026-11-06 14:34 UTC | 2026-11-10 06:55 UTC | 88.3 | 57.6 | 65.2% |
| Perp R2-08 | 2026-11-06 22:45 UTC | 2026-11-10 06:55 UTC | 80.2 | 51.9 | 64.7% |

The five longest gaps of each book (a gap is the time the book was not running before a restart):

| Book | Gap start | Hours |
|---|---|---|
| Spot (main) | 2026-11-09 12:55 UTC | 9.7 |
| Spot (main) | 2026-11-07 06:33 UTC | 6.0 |
| Spot (main) | 2026-11-08 12:25 UTC | 5.6 |
| Spot (main) | 2026-11-10 04:29 UTC | 3.2 |
| Spot (main) | 2026-11-09 05:42 UTC | 1.4 |
| Spot W2 | 2026-11-09 12:55 UTC | 9.7 |
| Spot W2 | 2026-11-07 06:33 UTC | 6.0 |
| Spot W2 | 2026-11-08 12:25 UTC | 5.6 |
| Spot W2 | 2026-11-10 04:29 UTC | 3.2 |
| Spot W2 | 2026-11-09 05:42 UTC | 1.4 |
| Perp v1 (control) | 2026-11-07 04:30 UTC | 7.9 |
| Perp v1 (control) | 2026-11-09 10:03 UTC | 5.0 |
| Perp v1 (control) | 2026-11-09 20:47 UTC | 4.4 |
| Perp v1 (control) | 2026-11-07 18:08 UTC | 3.3 |
| Perp v1 (control) | 2026-11-08 18:29 UTC | 3.2 |
| Perp R2-08 | 2026-11-07 04:30 UTC | 7.9 |
| Perp R2-08 | 2026-11-09 10:03 UTC | 5.0 |
| Perp R2-08 | 2026-11-09 20:47 UTC | 4.4 |
| Perp R2-08 | 2026-11-07 18:08 UTC | 3.3 |
| Perp R2-08 | 2026-11-08 18:29 UTC | 3.2 |

Hours in real time are calendar hours (first event to last event) minus the gaps the log itself records (each restart logs a catch_up event with the minutes the book was not running). A run whose log was never saved would show as a gap, so the share can read too low. Time since the last event, not counted above: Spot (main) 5.6 h; Spot W2 5.6 h; Perp v1 (control) 12.2 h; Perp R2-08 12.2 h.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 3.6 | $251,540 | +0.62% | 21 | $190,188 | 81.0 bp | 25 / 8 | 13 (12 made money) | 1 |
| Spot W2 | 3.5 | $251,330 | +0.53% | 22 | $164,904 | 80.7 bp | 27 / 8 | 15 (14 made money) | 1 |
| Perp v1 (control) | 3.7 | $10,046 | +0.46% | 1 | n/a (not logged) | n/a | 1 / 0 | - | 0 |
| Perp R2-08 | 3.3 | $10,024 | +0.24% | 1 | n/a (not logged) | n/a | 1 / 0 | - | 0 |

Days are calendar days, from the first to the newest event (hours in real time are under Running time). Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

| Measure | So far |
|---|---|
| Days (calendar) | 3.6 of 21 |
| Days in real time | 2.5 |
| Rungs | 21 of 60 |
| Rung fills a day (rule text: 1-6 rung fills a day) | 5.79 per calendar day; 8.33 per running day |
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
| 2026-11-10 | $0.00 | 10.3 |

Cash shortfalls: 11. Wanted $115,534 in total (average $10,503) against an average of $1,308 free.

Share of capital held by resting bids (committed over equity, mean of 119 heartbeats): 54.50%.

Largest single-day loss so far: -$3.06 on 2026-11-07.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days (calendar) | 3.6 | 3.5 | -0.1 |
| Hours in real time | 60.5 | 58.3 |  |
| Equity | $251,540 | $251,330 | -$210.10 |
| Change | +0.62% | +0.53% | -0.08 pp |
| Rung fills | 21 | 22 | +1 |
| Rung fills per calendar day | 5.79 | 6.23 |  |
| Rung fills per running day | 8.33 | 9.06 |  |
| Dollars bought | $190,188 | $164,904 | -$25,283 |
| Net per dollar | 81.0 bp | 80.7 bp | -0.3 bp |
| Exit events TP / time | 25 / 8 | 27 / 8 |  |
| Ladders closed (made money) | 13 (12) | 15 (14) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): -$210.10.

A few days and a few dozen fills cannot separate the two weightings; a gap this size is within what chance alone produces.

## Data quality

From the heartbeats of each spot book (one every 30 minutes while it runs). Counters are summed per UTC day; a counter that is not listed was 0 or is not reported. Minutes run are the 30 minutes before each heartbeat, less any gap. Data step is the seconds after the minute at which the data step finished: the median of the heartbeat medians, and the largest heartbeat maximum.

### Spot (main)

not reported by this book's code yet.

### Spot W2

not reported by this book's code yet.

## Perp books

| Book | Fills | Fills per calendar day | Fills per running day | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|---|---|
| Perp v1 (control) | 1 | 0.27 | 0.42 | 192.5 bp | $10,046 | +0.46% | 18,979 |
| Perp R2-08 | 1 | 0.30 | 0.46 | 97.0 bp | $10,024 | +0.24% | 16,833 |

Net per trade is the mean of the net bp of each exit. Fills per calendar day is fills divided by calendar days from the first to the newest event; fills per running day divides by the days the book was live (see Running time).

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
