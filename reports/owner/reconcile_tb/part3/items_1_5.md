# Part 3: the fifth book's measures 1, 3 and 4 on its log cut at the period's end

Copied from the status report (scripts/owner/paper_status.py) run on copies of the three books' logs, the
fifth book's cut at 18:59 UTC on Nov 19 2026. Measure 2 is in part3_rule.md.

## Rule progress for the fifth book

Engine commit: 9e6f53b (full hash 9e6f53b3aca8c15307f22a357f19431bff053e4c), recorded 2026-11-19T17:28:48Z UTC.

> The four measures of Part 3 of reports/owner/bar_source_prereg.md, read here on the whole log so far. This is progress only: the read is made once, on the period the plan defines, by scripts/owner/bar_source/part3_rule.py. Measure 2 (decisions against the research) is not computed here.

### Measure 1, the step

(a) Same-machine pairs: on one runner and the pinned commit, 30 minutes with release 3's inputs and 30 minutes with the build's, one after the other, the order alternating (scripts/owner/step_pairs/run_pair.py, step-pairs.yml). The measure is the median of the build's median data step minus release 3's over the pairs that count: at or below zero, at least 8 pairs. If fewer than 8 count in the period, the read also takes the later pairs, oldest first, up to the one that makes 8.

| Start | Order | Release 3 median | Build median | Build minus release 3 | Counts |
|---|---|---|---|---|---|
| 2026-11-16 19:27 UTC | ba | 11.24 s | 8.55 s | -2.69 s | counts |
| 2026-11-17 06:56 UTC | ba | 9.49 s | 8.46 s | -1.03 s | counts |
| 2026-11-17 20:33 UTC | ba | 9.78 s | 8.60 s | -1.18 s | counts |
| 2026-11-18 00:34 UTC | ab | 9.54 s | 8.47 s | -1.07 s | counts |
| 2026-11-18 06:18 UTC | ba | 9.74 s | 8.47 s | -1.27 s | counts |
| 2026-11-18 07:27 UTC | ba | 9.69 s | 8.49 s | -1.20 s | counts |
| 2026-11-18 12:15 UTC | ab | 11.04 s | 8.60 s | -2.44 s | counts |
| 2026-11-18 18:05 UTC | ba | 11.45 s | 8.65 s | -2.80 s | counts |
| 2026-11-18 20:05 UTC | ba | 9.84 s | 8.60 s | -1.24 s | counts |
| 2026-11-18 23:56 UTC | ba | 11.36 s | 8.61 s | -2.75 s | counts |
| 2026-11-19 05:47 UTC | ab | 11.18 s | 8.62 s | -2.56 s | counts |
| 2026-11-19 07:00 UTC | ba | 10.20 s | 8.50 s | -1.70 s | counts |
| 2026-11-19 11:37 UTC | ba | 10.88 s | 8.63 s | -2.25 s | counts |
| 2026-11-19 17:28 UTC | ab | 9.74 s | 8.60 s | -1.14 s | counts |
| 2026-11-19 20:04 UTC | ba | 9.78 s | 8.78 s | -1.00 s | counts |

| Part | Current value | Verdict |
|---|---|---|
| (a) Pairs that count, and the median of build minus release 3 | 14 pairs (8 needed); median -1.49 s; must be at or below 0.00 s | meets |

| Part | Current value | Verdict |
|---|---|---|
| (b) Against the main book, over the half hours both have a heartbeat (same heartbeat time) | fifth 8.61 s, main 11.05 s, 140 half hours; the fifth's must be no higher | meets |
| Reported, decides nothing: the fifth book's own median of its half-hour data-step medians | 8.61 s over 142 heartbeats; for comparison 10.3 s (release 3's figure of Nov 11 to 14, which moves with the period and the runner) | reported only |
| For information: against the fourth book, same way | fifth 8.61 s, fourth 13.11 s, 140 half hours | not part of the rule |

The read needs at least 100 heartbeats of the fifth book and at least 100 paired half hours with the main book for (b).

### Items 1 to 5 (measure 3)

Real-time minutes run so far: 4,320.

Listed coins for item 1: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC (fixed list for this book).

| Item | Current value | Verdict |
|---|---|---|
| 1. Verified trades bar share of listed coin-minutes (99% or more) | 99.89% (72,965 verified of 73,044 attempted coin-minutes: built 70,195, verified empty 2,770; fallbacks: unverified 0, error 3, budget 76, rate limit 0; listed coins: BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC) | meets |
| 2. No rate-limit fallback (tb_fb_limited 0) and no refusal in any event | tb_fb_limited 0; events mentioning a refusal or rate limit 0 | meets |
| 3. Data step 30-minute maximum 20 s or less in 95% or more of heartbeats (the median is measure 1, see below) | median 8.6 s of 142 heartbeats; maximum 20 s or less in 99.3% (largest 22.4 s); the median is judged as measure 1 | meets |
| 4. No error events and obs_error 0 | error events 0; obs_error 0 | meets |
| 5. Unconfirmed rows (rows_open) 1% or less of coin-minutes | 0.000% (0 of 76,518 coin-minutes, 18 coins) | meets |

### Measure 4, the candle requests between steps

| Part | Current value | Verdict |
|---|---|---|
| Counters, summed over the log | pre_fetched 72,791, pre_error 1, pre_missing 1, pre_ondemand 69, step_candles 70 |  |
| Failed requests (pre_error) against requests made (pre_fetched plus pre_error) | 1 of 72,792 = 0.001%; bar 1% or less | meets |
| Requests made inside a step (pre_missing plus pre_ondemand, first step after each start left out) against coin-minutes (18 times the minutes run) | 70 of 76,518 = 0.091%; bar 2% or less | meets |
| Left out: pre_missing of the first step after each start (at most 18 per start) | 0 left out, over 14 starts in the log |  |
