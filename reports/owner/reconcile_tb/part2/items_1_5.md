# Items 1 to 5 for the fourth paper book, on the test period alone

Made on Nov 15 2026 as reports/owner/bar_source_prereg.md, "How the reads are run", step 3, says: the status report
(scripts/owner/paper_status.py on `main`, commit 1456de4a) run on a copy of the fourth book's log cut at the
period's end. The copy holds the 1,138 events up to 22:29 UTC on Nov 14 (first 22:25 UTC on Nov 11, last 22:29 UTC
on Nov 14); the report was run with `--now 2026-11-14T22:29:00+00:00`. The book ran engine commit 58eba8b throughout
(paper_spot_t18/CODE).

- **Running time** (first event, last event, calendar hours, hours in real time, share):
  | Spot T18 (all coins on trades) | 2026-11-11 22:25 UTC | 2026-11-14 22:29 UTC | 72.1 | 72.1 | 100.0% |
- **Real-time minutes run: 4,324.**

| Item | Measured | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.86% (73,068 verified of 73,170 attempted coin-minutes: built 71,860, verified empty 1,208; fallbacks: unverified 4, error 0, budget 98, rate limit 0; all 18 coins listed) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 15 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 13.5 s of 141 heartbeats; maximum 20 s or less in 97.2% (largest 23.4 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 75,690 coin-minutes, 18 coins) | meets |

Item 3's median bar for this book is 15 s (plan, deviation log, Nov 11). By day the median was 13.8, 13.5, 13.4 and
13.1 s. Of the 98 budget fallbacks (the step ran out of time for a coin's trades and used its candle), 94 fell on
Nov 14, 66 of them between 21:00 and 22:00 UTC, when the other two books' steps were slow as well; in those two
half hours this book's median was 16.8 s.

Other counters over the period: 69,890 trades rows replaced by the venue's candle, 10,571 of them with a close more
than a tick from the trades bar; 1,815 dropped (the venue had no bar); 143 rows still built from trades three to six
minutes on; 4 coin-minutes skipped for an old answer.
