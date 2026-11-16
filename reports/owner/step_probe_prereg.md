# How early is the venue's trades list complete? A probe (plan fixed Nov 14 2026, 10:55 ET, before any data)

## Why
- The live bot's step starts 6 s after each minute, because the venue's candle for the closed minute is not ready
  earlier. A bar built from the venue's trades does not have to wait for the candle.
- The research assumes a bid rests for its whole minute. Every second the step starts earlier is a second more of
  resting. The timing study (reports/owner/timing/README.md) puts a second at about one point of the research's
  same-minute fills.
- Whether the step may start earlier depends on one fact that nobody has measured: how soon after a minute closes
  the public trades list holds that minute completely, as judged by the bot's own check.
- This is a fidelity question (class 1 in the charter). No P&L is read.

## What is measured
- **Symbols:** the 18 of the fourth paper book's list (BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR,
  NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC).
- **The request and the check** are the engine's own: `bot.market.minute_trades_bar`, with its pace of at most
  seven requests a second, one after another. Nothing about the check is changed.
- **For each minute m, which closes at q = m + 60 s:**
  1. **Early pass.** Starts at q + 1.0 s on the runner's clock. BTC first, as in the engine; the other 17 in an
     order that moves on by one place every minute, so every coin is sampled at every place.
  2. **Standard pass.** Starts at q + 6.0 s, or when the early pass ends if that is later. Same order. This is when
     the engine asks today.
  3. **Reference pass.** Starts at q + 35 s, for the minute before m (closed 95 s earlier). Its verified bar is the
     reference for that minute.
- **Recorded for every request:** coin, minute, pass, the second after q at which it was sent, how long it took,
  verified or not and why not, pages, when the venue generated the first page (against q), the number of trades and
  the bar. Raw trades never leave the runner.
- **Load on the venue:** 54 requests a minute, never more than seven in a second.
- **Stop:** a refusal or a rate-limit answer ends the probe at once. Nothing is retried or worked around, and it is
  reported.

## Runs
- Two runs of 300 minutes each on a GitHub runner: one on Nov 14 2026 (a Saturday) and one on Monday Nov 16 from
  13:30 UTC (a US weekday morning, when late prints are most likely). They are read together and shown apart.
- If a run stops early for a fault of the runner or of the script, it is repeated at the same hours of the next
  like day, and that is logged here.

## Measures
By pass and by the second at which the request was sent: early pass [1, 2), [2, 3), [3, 4), [4, 6); standard pass
[6, 10). Requests outside these bins are counted and shown, not ruled on.
- **V, verified share:** of the requests in the bin, the share the engine's check accepts.
- **E, equal share:** of the verified ones whose minute has a verified reference, the share whose open, high, low
  and close all equal the reference bar's. A minute with no trades in both counts as equal. Volume is shown beside
  it.
- **BTC** is shown apart at its own place, the first request of each pass.
- Also shown, with no rule: how long a request takes by coin, and how long each pass takes.

## Rule (fixed now)
- **The step may start at second s (1, 2, 3 or 4)** only if all of these hold over both runs together:
  1. in every bin of the early pass from [s, s + 1) on: V at least 99.0% and E at least 99.5%;
  2. in each of those bins, E is no more than 0.3 points below the standard pass's E;
  3. for BTC, which is sent at second 1.0: V at least 99.5% and E at least 99.5%. If BTC fails at 1.0 s, no second
     earlier than 6 passes on this probe, because the probe has BTC at no other early second.
  4. every bin that is ruled on holds at least 2,000 requests, and BTC at least 500.
- **The earliest second that meets the rule is the candidate.** It becomes a setting only through a release, and a
  paper book runs it first.
- **If no second meets it,** the step stays at 6 s and the result is recorded as a known gap.
- The rule is code before the first run is read (scripts/owner/step_probe/rule.py, with tests).

## What this probe cannot say
- It runs on a GitHub runner. The live bot's server may see the venue a little sooner or later.
- It compares an early bar with the trades list 95 s later, not with the venue's final candle. The paper books
  compare trades bars with candles every minute (the counters in their heartbeats).
- Two runs of five hours are a sample. The paper book that runs the candidate is the longer test.

## Result (read Nov 16 2026, 13:40 ET)
- **No second earlier than 6 meets the rule. The step stays at 6 s.** Recorded as a known gap.
- **The runs.** Run 1: Saturday Nov 14, the minutes that closed from 16:08 to 21:07 UTC. Run 2: Monday Nov 16,
  13:29 to 18:28 UTC. Each: 300 minutes, 5,400 early, 5,400 standard and 5,418 reference requests. No refusal, no
  rate-limit answer, no pass skipped, never more than seven requests in a second.
- **Both runs together:**

| Pass and second sent | Requests | V: the check accepts | E: equal to the list 95 s later |
|---|---|---|---|
| early [1,2) | 2,604 | 66.1% | 87.1% |
| early [2,3) | 3,441 | 84.0% | 95.2% |
| early [3,4) | 3,164 | 92.6% | 97.4% |
| early [4,6) | 1,220 | 100.0% | 97.5% |
| BTC, sent at 1.0 s | 600 | 42.7% | 54.0% |
| standard [6,10), where the engine asks today | 9,544 | 99.99% | 99.99% |
| BTC, sent at 6.0 s | 600 | 99.8% | 100.0% |

- **Against the rule's items:**
  - item 1 (V at least 99.0%, E at least 99.5%) fails in every early bin;
  - item 2 (E no more than 0.3 points under the standard pass's 99.99%) fails in every early bin;
  - item 3 (BTC at 1.0 s, 99.5% on both) fails: 256 of 600 verified, 136 of 252 equal;
  - item 4 (enough requests) holds for [1,2), [2,3), [3,4) and for BTC, and fails for [4,6): 1,220 of the 2,000
    needed.
- **The two runs give the same answer.** Run 1 then run 2: [1,2) V 74.4% and 59.5%, E 83.2% and 91.0%; [2,3) V 90.1% and 75.8%,
  E 93.4% and 98.0%; [3,4) V 96.0% and 87.8%, E 96.8% and 98.3%; BTC at 1.0 s V 42.7% in both, E 50.0% and
  57.9%; standard pass E 5,197 of 5,197 and 4,334 of 4,335.
- **Why early answers fail.**
  - Every unverified early request was turned down for the same reason: its first page was made before the
    minute had closed.
  - Early bars that pass the check still differ, because trades reach the public list a few seconds after they
    happen.
- **What it means.**
  - The list holds the whole minute about five to six seconds after it closes. The step's start at 6 s is close to
    the earliest at which a bar built from requests can be trusted.
  - A step that decides earlier cannot be built on requests. It needs the trade stream, which has to be measured
    from the server with its own plan.
- **Tables:** `reports/owner/step_probe/read/` (`summary.md`, `verdict.md`, `bins.csv`, `durations.csv`), made by
  the scripts on branch owner/step-probe at commit fae2f1e7. The rows of every request are on that branch
  (`reports/owner/step_probe/run1` and `run2`).

## Reported, not ruled on (made after the rule was applied; it decides nothing)
- **By the second a request was sent** (the 17 coins other than BTC, every request whose minute has a reference,
  accepted by the check or not), the bar equals the list 95 s later in:
  - second 1: 1,650 of 2,004 (82%);
  - second 2: 3,017 of 3,441 (88%);
  - second 3: 2,989 of 3,164 (94%);
  - second 4: 856 of 885 (97%);
  - second 5: 333 of 335 (99.4%);
  - from second 6, in the standard pass, all coins: 10,787 of 10,788.
  - BTC at 1.0 s: 151 of 588 (26%).
- **An answer's age is not what makes it incomplete.** The venue's cache hands out copies up to five seconds old.
  - When an early answer came fresh from the venue and was complete, the request five seconds later got the very
    same copy back in 2,838 of 5,727 cases.
  - When the fresh early answer was incomplete, it never did (0 of 239): the copy had been replaced.
  - So the cache appears to renew a copy when the list changes. What decides completeness is when the request is
    sent, not how old the answer says it is.
- Tables: `reports/owner/step_probe/read/explore.md` and `explore.csv` (script `explore.py` on the branch, 52
  offline checks). Anything acted on from these needs its own test.

## Deviation log
- **Nov 16 2026, 13:40 ET (orchestrator), at the read.**
  - **Run 2 began one minute early.** Its first minute closed at 13:29 UTC, not 13:30: the job was started at
    13:27 and the script begins with the next whole minute. No effect on the rule.
  - **The rule script prints "wait: too few requests"; the result is recorded as "none".**
    - The script looks at item 4 first, and every second's bins include [4,6), which holds 1,220 requests against
      2,000. That bin is small by construction: 18 requests at seven a second are all sent by about 3.4 s after
      the minute when no answer is slow, so only slow passes reach second 4.
    - "Wait" is the script's word, not the plan's. The plan asks that all four items hold. Items 1 to 3 fail on
      samples that are large enough: the bins [1,2), [2,3) and [3,4), and BTC's 600 requests against the 500
      needed. The plan also says that if BTC fails at 1.0 s, no second earlier than 6 passes on this probe.
    - More runs would send BTC at the same second and could not change item 3. So no run is added.
    - The script is left as it was written before the read.
