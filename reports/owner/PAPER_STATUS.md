# Paper trading status

Report made 2026-11-10 14:15 UTC.

| Book | Newest event | Age | Flag |
|---|---|---|---|
| Spot (main) | 2026-11-10 13:30 UTC | 0.8 h ago | ok |
| Spot W2 | 2026-11-10 13:30 UTC | 0.8 h ago | ok |
| Perp v1 (control) | 2026-11-10 06:55 UTC | 7.3 h ago | ok |
| Perp R2-08 | 2026-11-10 06:55 UTC | 7.3 h ago | ok |

A book is flagged STALE when its newest event is more than 8 hours old.

## Summary

| Book | Days | Equity | Change | Rung fills | Dollars bought | Net per dollar | Exit events TP / time | Ladders closed | Errors |
|---|---|---|---|---|---|---|---|---|---|
| Spot (main) | 3.6 | $251,540 | +0.62% | 21 | $190,188 | 81.0 bp | 25 / 8 | 13 (12 made money) | 1 |
| Spot W2 | 3.5 | $251,330 | +0.53% | 22 | $164,904 | 80.7 bp | 27 / 8 | 15 (14 made money) | 1 |
| Perp v1 (control) | 3.7 | $10,046 | +0.46% | 1 | n/a (not logged) | n/a | 1 / 0 | - | 0 |
| Perp R2-08 | 3.3 | $10,024 | +0.24% | 1 | n/a (not logged) | n/a | 1 / 0 | - | 0 |

Days run from the first to the newest event. Change is against starting capital ($250,000 spot, $10,000 perp). Net per dollar is total P&L of exits over total dollars bought, so rungs still open count as bought with no P&L yet. A rung can exit in several pieces, so exit events can outnumber fills. The perp logs do not record contract size, so their dollars bought are not available.

## Spot book against forward rule A

> Paper for at least 3 weeks and at least 60 rungs; pass if there are no unexplained errors and mean net per dollar is above 0.

| Measure | So far |
|---|---|
| Days | 3.6 of 21 |
| Rungs | 21 of 60 |
| Mean net per dollar | 81.0 bp |
| Errors | 1 |

| Error message (first 160 characters) | Count |
|---|---|
| KeyError("Cannot get left slice bound for non-monotonic index with a missing label Timestamp('2026-10-27 21:19:00'). Either sort the index or specify an existin | 1 |

Status: **CHECK**

CHECK means errors are present or net is at or below 0. NOT YET means the 3 weeks and 60 rungs are not reached. ON TRACK means both are reached with no errors and net above 0. The owner declares any pass.

## Spot book detail

Fills and net per dollar by rung:

| Rung | Fills | Dollars bought | Exit events | Exit P&L | Net per dollar |
|---|---|---|---|---|---|
| 4 | 13 | $140,779 | 23 | $958.28 | 68.1 bp |
| 6 | 7 | $42,813 | 8 | $492.83 | 115.1 bp |
| 8 | 1 | $6,596 | 2 | $89.39 | 135.5 bp |

P&L of exits by day, last 14 days:

| Day (UTC) | Exit P&L |
|---|---|
| 2026-10-28 | $0.00 |
| 2026-10-29 | $0.00 |
| 2026-10-30 | $0.00 |
| 2026-10-31 | $0.00 |
| 2026-11-01 | $0.00 |
| 2026-11-02 | $0.00 |
| 2026-11-03 | $0.00 |
| 2026-11-04 | $0.00 |
| 2026-11-05 | $0.00 |
| 2026-11-06 | $0.00 |
| 2026-11-07 | -$3.06 |
| 2026-11-08 | $1,305 |
| 2026-11-09 | $238.52 |
| 2026-11-10 | $0.00 |

Cash shortfalls: 11. Wanted $115,534 in total (average $10,503) against an average of $1,308 free.

Share of capital held by resting bids (committed over equity, mean of 119 heartbeats): 54.50%.

Largest single-day loss so far: -$3.06 on 2026-11-07.

## W2 against the main spot book

| Measure | Spot (main) | W2 | W2 minus main |
|---|---|---|---|
| Days | 3.6 | 3.5 | -0.1 |
| Equity | $251,540 | $251,330 | -$210.10 |
| Change | +0.62% | +0.53% | -0.08 pp |
| Rung fills | 21 | 22 | +1 |
| Dollars bought | $190,188 | $164,904 | -$25,283 |
| Net per dollar | 81.0 bp | 80.7 bp | -0.3 bp |
| Exit events TP / time | 25 / 8 | 27 / 8 |  |
| Ladders closed (made money) | 13 (12) | 15 (14) |  |
| Errors | 1 | 1 | +0 |

W2 started 2.2 hours after the main book, so the windows are not identical.

Difference in equity (W2 minus main): -$210.10.

A few days and a few dozen fills cannot separate the two weightings; a gap this size is within what chance alone produces.

## Perp books

| Book | Fills | Net per trade | Equity | Change | Bids placed |
|---|---|---|---|---|---|
| Perp v1 (control) | 1 | 192.5 bp | $10,046 | +0.46% | 18,979 |
| Perp R2-08 | 1 | 97.0 bp | $10,024 | +0.24% | 16,833 |

Net per trade is the mean of the net bp of each exit.

Paper fills assume the research's capture share; they check the machinery and the fill frequency, not whether real orders fill.
