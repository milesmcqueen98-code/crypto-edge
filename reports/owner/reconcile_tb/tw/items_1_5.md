# Trades-workers read: the sixth book's items 1 to 5, requests and stops on its log cut at the period's end

Copied from the status report (scripts/owner/paper_status.py) run on copies of the books' logs, the sixth and
the fifth book's cut at 23:59 UTC on Nov 19 2026, with `--now 2026-11-20T00:00`. The rule script computes the
requests and the stops itself from the period's heartbeats; they are here for comparison. Part 3's table in the
status report is progress only and is not copied: the rule's own table is in trades_workers_rule.md.

### Part 4, measure 2: items 1 to 5

Real-time minutes run so far: 4,315.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.97% (73,920 verified of 73,944 attempted coin-minutes: built 71,147, verified empty 2,773; fallbacks: unverified 0, error 3, budget 21, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step 30-minute maximum 20 s or less in 95% or more of heartbeats (the median is not judged for this book; the pairs decide the step) | median 8.6 s of 144 heartbeats; maximum 20 s or less in 99.3% (largest 21.2 s); the median is not judged here | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 77,634 coin-minutes, 18 coins) | meets |

### Part 4, measure 3: requests inside a step

| Part | Current value | Verdict |
|---|---|---|
| Failed requests (pre_error) against requests made (pre_fetched plus pre_error) | 2 of 73,692 = 0.003%; bar 1% or less | meets |
| Requests made inside a step (first step after each start left out) against coin-minutes (18 times the minutes run) | 26 of 77,634 = 0.033%; bar 2% or less | meets |

| Part | Current value | Verdict |
|---|---|---|
| In-step share against the fifth book's, over the half hours in which both have a heartbeat (the sixth's must be no higher) | sixth 26 of 76,554 = 0.034%, fifth 60 of 76,680 = 0.078%, 142 half hours | meets |

### Part 4, measure 4: stops

| Part | Current value | Verdict |
|---|---|---|
| Half hours with a rate-limit stop (tb_fb_limited above 0): none in the sixth book unless the fifth has one at the same heartbeat | sixth 0, fifth 0; sixth only: 0 | meets |
| Half hours with a request error (tb_fb_error above 0): the sixth's at most the fifth's plus 2 | sixth 2, fifth 2 | meets |

## Sixth book against the fifth book

Period both ran: 2026-11-16 23:37 UTC to 2026-11-19 23:32 UTC (71.9 calendar hours; 71.9 hours with both live).

| Measure | Spot R5 | Spot TW | TW minus R5 |
|---|---|---|---|
| Rung fills | 2 | 2 | +0 |
| Rung fills per calendar day | 0.67 | 0.67 |  |
| Rung fills per running day | 0.67 | 0.67 |  |
| First-bid fills (rung 4) | 2 | 2 | +0 |
| Deeper rungs placed | 4 | 4 |  |
| Dollars bought | $23,095 | $23,095 | $0.00 |
| Exit P&L | -$81.73 | -$81.73 | $0.00 |
| Net per dollar bought | -35.4 bp | -35.4 bp | +0.0 bp |

How the first bids overlap (a first bid is a rung 4 fill; the same coin within two minutes either side counts as the same fill, each fill used once):

| Group | Fills |
|---|---|
| First-bid fills in both books | 2 |
| Only in the fifth book | 0 |
| Only in the sixth book | 0 |

This comparison is for the record. The registered read is Parts 3 and 4 of reports/owner/trades_workers_plan.md.
