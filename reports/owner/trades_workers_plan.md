# The trades pass side by side: plan (fixed Nov 16 2026, 14:40 ET, before the new code has run on live data)

## Why
- Every minute the engine asks the venue's trades list for each listed coin, one after another, at no more than
  seven requests a second. The pass has 8 s. A coin it does not reach falls back to its candle row.
- With 18 coins this fits a quiet day and not a busy one.
  - The fourth book's pass ran out of time for 1 of 23,888 coin-minutes on Nov 12 and 3 of 24,304 on Nov 13.
    Then 1.0% on Nov 14, 1.3% on Nov 15, 1.6% on Nov 16 by 19:00 UTC, and 10.9% in the last half hour of that.
  - The step probe's own 18-coin pass took 4.0 s at the 90th percentile on Nov 14 and 7.1 s on Nov 16.
- The cause is single slow requests, not paging. A slow pass has the same number of pages as a fast one. In the
  probe's 6 s pass, 6.0% of the requests to the smaller coins took more than half a second on Nov 16 and 0.4%
  took three seconds or more (a timeout and its retry); on Nov 14, 0.7% and 0.04%. One slow request holds up
  every coin behind it.
- A late or fallen-back input is a fidelity loss (class 1 in the charter), and busy days are where the strategy
  earns. Nothing about the model or the rules changes. The bars are the same bars.
- **What this is worth, said plainly.** The time gained is small in money: the timing study cannot rank a second
  of step time. The reason to build it is the build under test, which puts all 18 coins on trades. On a busy day
  it cannot keep those inputs without a faster pass, and its paper test may fail on that (bar-source plan, Part
  3, measure 4).

## What is built
- Engine option `trades_workers` (branch owner/trades-workers, from the fifth book's commit 9e6f53b3). Absent or 1:
  today's code path, unchanged. With 3: the pass fetches with three workers and applies the results in today's
  order.
- The pace stays at seven requests a second across all workers.
- A refusal or a rate-limit answer stops every worker at once. Nothing is retried or worked around.
- The 8 s budget bounds the pass in wall time. Today a stalled last request can run past it.
- It ships off. A paper config `config.tw.json` (the build's `config.json` plus `trades_workers: 3`) is what the
  tests below run.

## What a model on the probe's recorded requests expects (an expectation, not a result)
- Model: every call keeps the time the probe recorded for it, less its wait for the pace; the order and the pace
  stay; three workers instead of one. With one worker the model gives the recorded passes back to within 0.1 s
  on average. The script goes onto the probe's branch before this plan's first live run.

| 18-coin pass | Nov 14, recorded | Nov 14, three workers | Nov 16, recorded | Nov 16, three workers |
|---|---|---|---|---|
| Median | 3.1 s | 2.5 s | 3.2 s | 2.5 s |
| Mean | 3.3 s | 2.6 s | 4.1 s | 2.9 s |
| 90th percentile | 4.0 s | 2.6 s | 7.1 s | 4.3 s |
| Longer than the 8 s budget | 1.0% | none | 6.3% | none |

- So the expectation is about 0.6 s earlier in a median minute, 0.8 to 1.2 s on average, and no pass over its
  budget. Two workers give most of it; three hold when two requests are slow at once; a fourth adds nothing.
- Considered and not chosen: a longer budget. It would also end the fallbacks, by letting the slow minutes run
  later. Workers end them without that.

## Parts and rules. Every part must hold.
### Part 1: offline
- The agent's new tests (pace across workers, a stalled request delays only its own coin, the stop, the budget,
  equality of state and counters with the one-worker path on the same scripted data).
- The full offline suite on a runner with no failing file. Every existing test passes with its expectations
  untouched: the one-worker path is today's.
- The commit that passes is pinned and named in this plan's deviation log before Part 2.

### Part 2: one live run, a check for faults (it passes nothing)
- One runner, 30 minutes with one worker and then 30 with three (`tb_smoke.py`), each checked against the
  venue's candles.
- A fault is: a refusal, a rate-limit answer, a crash, more than 8 trades requests in any one second as the tool
  counts them (the pace is 7 and the venue's public limit is 10), or a compared row that differs in the
  three-worker half and not in the other. A fault is fixed and Parts 1 and 2 are run again before anything else.

### Part 3: same-machine pairs, one worker against three
- On one runner and the pinned commit: 30 minutes with `trades_workers` 1 and 30 with 3, one straight after the
  other, both with the build's inputs. The order alternates from job to job. Four jobs a day at 03:05, 09:05,
  15:05 and 21:05 UTC, for the three days of Part 4.
- A pair counts as the fifth book's pairs count: at least 20 timed steps in each half and no refusal or rate
  limit in either. At least 8 pairs; with fewer, the jobs go on at the same times and the read waits for the
  eighth, as fixed for the fifth book's pairs.
- Measures, over the pairs that count:
  1. **The step.** The median of (the three-worker half's median data-step end minus the one-worker half's) is
     at most -0.2 s. The model expects about -0.6 s; a gain under a fifth of a second is not worth threads in
     the input path.
  2. **The slow minutes.** Budget fallbacks as the tool counts them for a half (each half has one start),
     summed over the three-worker halves, are no more than over the one-worker halves. And the median of
     (longest pass with three workers minus longest pass with one) is at most zero.
  3. **The pace.** No three-worker half has more than 8 trades requests in any one second, and none meets a
     rate-limit answer or a refusal. One such answer in a three-worker half stops the pairs and the sixth book
     until the cause is known.
  4. **The rows.** Summed over the pairs, the share of compared rows that differ from the venue's candles is no
     higher in the three-worker halves than in the one-worker halves.
- Reported, not ruled on: the pass's own median duration in each half.

### Part 4: the sixth paper book
- `paper_spot_tw`: the pinned commit with `config.tw.json`, $250,000 of paper money, its own workflow and runner.
  Control: the fifth book (the same inputs with one worker), unchanged.
- Period: from the first half-hour mark after its first decision minute, 4,320 minutes. Extended by six hours, at
  most three times, while it or the fifth book has fewer than 300 new bids on the 17 coins on the minutes both
  were live (counted from the two logs before any research is fetched).
- Measures:
  1. **Decisions,** both books against the research with the tools of the bar-source plan, all 17 coins, the
     minutes both were live: bids the research would not have placed at most the fifth book's share plus 2.0
     points and at most 5%; the research's new bids with a bot bid within a minute at least the fifth's share
     minus 3.0 points; bids more than 5 bp from the research level under 5%. The tolerances are the bar-source
     plan's, for its reason: this catches a fault, it does not rank.
  2. **Items 1 to 5** for the sixth book, as for the fifth (item 3: the half-hour maximum of the data step at or
     below 20 s in at least 95% of heartbeats).
  3. **Requests inside a step.** Failed between-step requests at most 1% of those made; candle requests inside a
     step, leaving out the first step after each start, at most 2% of coin-minutes, and no higher a share than
     the fifth book's over the half hours in which both have a heartbeat.
  4. **Stops.** The sixth book has no half hour with a rate-limit stop (`tb_fb_limited`) unless the fifth book
     has one in the same half hour. Its half hours with a request error (`tb_fb_error`) are at most the fifth
     book's plus 2.
- Reported, not ruled on: both books' data-step medians on the same half hours (the runners differ, so the pairs
  decide the step); the pass's own duration from the new heartbeat entry; fills and P&L.

## One read
- Parts 3 and 4 are read once, together, after the period. Interim looks may stop the test for a fault (a crash, a
  refusal, a rate-limit stop, an error event). They cannot pass it and change no rule.

## What follows
- **All parts hold:** `trades_workers: 3` goes into the release config for the paper books and the live bot,
  with a release note. It is its own release, after release 5 if that has shipped.
- **Any part fails:** the option stays off. The cause is found first; a corrected version starts its parts again.
- **If the bar-source plan's Part 3 fails on its measure 4 alone** (candle requests inside a step), this build is
  the corrected build that plan asks for, because the cause above is the trades pass's time. That case is fixed
  in the bar-source plan's deviation log today, before either book is read.

## What this cannot say
- The runners are not the live server. The live bot's first days with the option are read from its own heartbeat.
- Three days may be quiet. Then the gain in slow minutes cannot show, and measure 2 of Part 3 holds trivially.
  Measure 1 does not depend on slow minutes: the model expects about 0.6 s in a median minute on a quiet day
  too.

## Deviation log
(none yet)
