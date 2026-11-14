# Items 1 to 5 of the third paper book's rule, on the test period alone

Made on Nov 14 2026 as reports/owner/paper_reconcile_plan.md, step 6, says: the status report
(scripts/owner/paper_status.py on `main`, commit 7fdaa622) run on a copy of the third book's log cut at the
period's end. The copy holds the 962 events up to 01:52 UTC on Nov 14 (first 01:47 UTC on Nov 11, last 01:51 UTC
on Nov 14); the report was run with `--now 2026-11-14T01:52:00+00:00`.

- **Running time** (first event, last event, calendar hours, hours in real time, share):
  | Spot TB (trades input) | 2026-11-11 01:47 UTC | 2026-11-14 01:51 UTC | 72.1 | 72.0 | 99.9% |
- **Real-time minutes run so far: 4,318 of 4,000 (108%).**

| Item | Measured | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 100.00% (24,252 verified of 24,252 attempted coin-minutes: built 24,252, verified empty 0; fallbacks: unverified 0, error 0, budget 0, rate limit 0; listed coins: BTC, ETH, SOL, XRP, LTC, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step median 13 s or less; 30-minute maximum 20 s or less in 95% or more of heartbeats | median 10.1 s of 140 heartbeats; maximum 20 s or less in 99.3% (largest 23.9 s) | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.020% (15 of 75,240 coin-minutes, 18 coins) | meets |

Items 6 and 7 are in item6/item6.md and item7.md.
