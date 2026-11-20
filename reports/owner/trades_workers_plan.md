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
  on average. Script: `scripts/owner/step_probe/model_workers.py` on branch owner/step-probe (commit 1bb86d7d);
  its table is `reports/owner/step_probe/read/model_workers.md`.

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
- **Replaced on Nov 16 2026, 18:35 ET, before any Part 3 run: see the deviation log. The lines below are the first
  version, kept for the record.**
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
- **Nov 16 2026, 14:42 ET (orchestrator), before any live run.** The model's script and table are in (a Sonnet
  agent, 27 offline checks). It gives the figures of the table above exactly; the sentence that said the script
  would follow now names it. No rule is touched.
- **Nov 16 2026, 15:21 ET (orchestrator), before any live run and before any pair.** How a pair's rate-limit
  mark is set.
  - **Found in review of the pair tool:** the fifth book's tool marks a half as rate-limited when the bare number
    429 stands anywhere in that half's output outside the step table. A counter that happens to be 429, a price
    of 429.5 or a time of 7.429 s would set it. The agent puts the chance at a few percent a pair, unmeasured.
  - **Here it would do harm:** Part 3's measure 3 fails the test on one such mark in a three-worker half.
  - **So this plan's own pair tool does not use the bare number.** A half is marked rate-limited only by what a
    rate-limit answer really prints: `Limited(`, `HTTP 429`, the words rate limit or too many requests, or the
    heartbeat counter `tb_fb_limited` above zero. The refusal mark is unchanged.
  - Decided before the tool has read any real output. Nothing else in the plan changes.
- **Nov 16 2026, 17:03 ET (orchestrator), before Part 2.** Part 1 holds; the commit is pinned.
  - **The commit:** `4c1717ac3cd711c3383e281ccb3eb2742f993b23` on branch owner/trades-workers (the fifth book's commit 9e6f53b3 plus the option).
  - **The suite on a runner** (job 43945430666): 23 test files, none with a failure, 914 passing checks (the 830 of the fifth book's commit, the new file's 79, five more for the inherited-settings list); the replay equals the research rung for rung.
  - **One existing expectation was changed, and it is not behaviour.** `release_inputs_test.py` checks the list of
    settings the live bot inherits. The option was added to that list, so the list in the test has eight names
    instead of seven. Every other existing check passes as it was written.
  - **Three places where the two paths differ,** each shown by a test (facts in
    `reports/owner/trades_workers_candidate.md` on the branch):
    - after a refusal or a rate limit, the old path keeps the coins before the refused one and the new path
      keeps whatever had arrived;
    - the new path reaches coins the old one would not reach inside the budget;
    - an answer that arrives after the budget is used by the old path and dropped by the new one. That is the
      budget bounding the pass, as this plan says.
  - **A limit of the stop, said plainly:** a request already on its way when another one is refused cannot be
    called back. With three workers that is at most two requests. Nothing is sent once the stop is set.
  - **The bar-source plan's branch** named under "What follows" was corrected there at 15:32, before any read: it
    covers a fail on its measure 4, on item 1 of its measure 3, or on both, and on nothing else.
- **Nov 16 2026, 18:35 ET (orchestrator), after Part 2 and before any Part 3 run.** Part 2 shows no fault. Part 3
  is redesigned, and I say below what that change does to the odds.
  - **Part 2** (job 43966296502, 22:20 to 23:25 UTC, one runner, commit 4c1717ac):

| | One worker, 31 steps | Three workers, 31 steps |
|---|---|---|
| Trades pass, median | 2.65 s | 2.64 s |
| Trades pass, longest | 4.49 s | 3.79 s |
| Data step ends, median | 8.65 s | 8.64 s |
| Budget fallbacks | 0 | 0 |
| Most trades requests in one second | 7 | 7 |
| Compared rows that differ from the venue's candles | 0 of 756 | 0 of 756 |

    - No refusal, no rate-limit answer, no crash. Nothing to fix. Part 2 passes nothing.
  - **What Part 2 showed about Part 3 as written.**
    - Both paths sat at the pace: 18 requests at seven a second cannot take less than 2.43 s. In that hour almost
      no request took longer than the gap between two sends, so there was nothing for workers to gain.
    - The model's 0.6 s came from the probe's runner, where 13 to 16% of requests took longer than that gap. I
      wrote that measure 1 "does not depend on slow minutes". That was wrong: it depends on the machine and the
      hour.
    - So measure 1 as written (a median gain of 0.2 s over half-hour pairs) tests the model's median. It does
      not test what the option is for, which is the slow minutes.
    - The half-hour pairs have a second weakness for slow minutes: slow spells come in runs, so one spell can fall
      into one half of one pair and look like a gain or a loss.
  - **What the change does to the odds, plainly:** as written, Part 3 would most likely fail unless most pairs
    fell into slow hours. The new Part 3 can pass when most minutes are quiet and some are slow. It is easier to
    pass in exactly that case. I make the change anyway because the written measure answers the wrong question,
    and I make it before any Part 3 data exist. To keep it honest, the new measures ask for a shown gain where
    the option claims one, with a floor on how many slow passes must have been seen and a time limit.
  - **Part 3 as it now stands: alternating minutes on one machine.**
    - Four jobs a day at 03:05, 09:05, 15:05 and 21:05 UTC. Each is one paper run of 60 minutes on one runner,
      on the pinned commit, with the sixth book's config. The trades pass uses one worker in one minute and three
      in the next, turn by turn. Which arm takes the even minutes alternates from job to job.
    - Recorded for every step: the arm, the pass's duration by the engine's timer, budget fallbacks, rate-limit
      and error counts, the most trades requests in any one second, and the bars the pass built. Afterwards the
      bars are compared with the venue's candles, fetched at least three minutes later.
    - A job counts if each arm has at least 20 timed steps. At least 8 jobs; with fewer, the jobs go on at the
      same times and the read waits for the eighth.
    - Measures, over all steps of the jobs that count:
      1. **No harm in an ordinary minute.** The median pass with three workers is at most the median with one
         worker plus 0.05 s.
      2. **A gain in slow minutes.** A slow pass is one longer than 6.0 s, three quarters of the budget. The
         one-worker minutes must hold at least 30 slow passes. The share of slow passes among the three-worker
         minutes is at most half the share among the one-worker minutes. Budget fallbacks in the three-worker
         minutes are no more than in the one-worker minutes.
         - If the one-worker minutes hold fewer than 30 slow passes when Part 4's period ends, the jobs go on at
           the same times until they do, for at most 14 days from the first job. If they still do not, the gain
           is not shown and the option stays off until a slow spell can be tested.
      3. **The pace.** In no three-worker minute are more than 8 trades requests sent in one second, and none
         meets a rate-limit answer or a refusal. One such answer in a three-worker minute stops the jobs and the
         sixth book until the cause is known.
      4. **The rows.** The share of built bars that differ from the venue's candle is at most one point higher
         for three workers than for one. (Two equal shares differ by chance, so "no higher" would fail half the
         time. In Part 2's check the rows had already been replaced by the venue's candles, which is why it
         showed none; here the bars are compared as built.)
    - Reported, not ruled on: both arms' median and mean pass and their difference, beside the 0.2 s that the
      first version asked for.
    - **A known lean against the option:** a coin that falls back in a one-worker minute is repaired by the next
      minute's pass, which is a three-worker one. So the three-worker minutes carry some of the one-worker
      minutes' cost.
    - **Why 6.0 s and 30:** on the probe's recorded requests 19.7% of passes on Nov 16 and 2.7% on Nov 14 were
      longer than 6 s, against 1.0% and 0.3% in the model with three workers. With 30 slow passes on the
      one-worker side, an option that did nothing would show 15 or fewer on the other side about once in fifty
      tries (1.8%, slow passes taken as independent). With 20 it would be once in twenty, which is too often.
  - **Part 4 is unchanged.** The sixth book starts now. Parts 3 and 4 are still read once, together; if Part 3
    has to wait for slow minutes, the verdict waits with it.
- **Nov 16 2026, 19:22 ET (orchestrator), after the sixth book's first run.** The period, and the tooling as merged.
  - **The sixth book started** at 23:37 UTC on the pinned commit (`paper_spot_tw/CODE` names 4c1717ac). First
    stepped minute 23:41 UTC. So Part 4's period runs from 00:00 UTC on Nov 17 to 23:59 UTC on Nov 19, before any
    extension.
  - **Interim look at its first heartbeat** (20 steps; it can find a fault and pass nothing): no error, warning or
    halt event, no fallback of any kind, 360 between-step candle requests and none failed, data step at a median
    of 8.66 s, trades pass 2.66 s at the median and 4.69 s at the longest.
  - **Part 3's tooling is on `main`** (squash d95b733e; Sonnet agent, reviewed): the alternating job
    (`scripts/owner/workers_alt/run_alt.py`, workflow `workers-alt`), the rule as code
    (`scripts/owner/trades_workers/rule.py`, 146 offline checks) and the status report's sections. Points the plan
    left open, as the code settles them:
    - the first job is the earliest one that counts, and the 14 days run from its start;
    - if the 14 days pass without 8 jobs and 30 slow one-worker passes, Part 3 is complete with the gain not shown,
      whichever of the two is short;
    - measure 3 (the pace, rate limits, refusals) is read on every job file from the first job to the last one
      used, counting or not; a file that cannot be read fails it;
    - measure 4 (the rows) leaves out a job whose comparison with the venue's candles could not be finished. That
      comparison makes one request a coin, one try, and stops at the first one that gets no answer;
    - a bar and a candle are equal when all five values are equal as numbers, as in the live check's tool; the
      newest three minutes of a job are left out.
  - The first job is the scheduled one at 03:05 UTC on Nov 17. No job is started by hand.
- **Nov 17 2026, 08:20 ET (orchestrator), after the first alternating job.** An interim look, two clauses that
  compared noisy counts, and how the jobs are started.
  - **The first job** (11:41 to 12:48 UTC; it can find a fault and pass nothing): the tooling works on the real
    venue. 30 one-worker and 31 three-worker steps, median pass 2.596 and 2.594 s, no pass over 6 s, no
    fallback, 7 requests in a second at most in every step, no rate limit, no refusal, no engine warning. Bars
    that differ from the venue's candle: 242 of 522 with one worker, 236 of 522 with three.
  - **What that showed about measure 4.** Nearly half of the bars differ from the candle by the equality fixed
    yesterday (all five values equal as numbers), in both arms alike. With a share that large, two equal arms
    differ by more than one point by chance: at 12 jobs about one time in eight. Measure 4 as written would
    then fail an option that builds the same bars.
  - **The same flaw sits in measure 2's last clause** (budget fallbacks with three workers "no more than" with
    one): two small counts with equal rates break "no more than" up to half the time. No alternating job has
    had a fallback yet, so nothing seen bears on it.
  - **Both clauses as they now stand: three workers must not be worse by more than chance allows.**
    - Measure 4: the three-worker share of differing bars is at most the one-worker share plus one point, or, if
      it is more than that, plus two standard errors of the difference (the usual formula for two shares, from
      the pooled share).
    - Measure 2, last clause: counted in passes, not coins. The number of three-worker passes that ran out of
      budget is at most the one-worker number, or, if it is more, more by at most twice the square root of the
      two numbers' sum. (A pass that runs out of budget drops several coins at once, so coins are not
      independent; passes nearly are.)
    - The first job's rows favoured three workers (236 against 242), so this change rescues nothing that was
      seen. It loosens both clauses against chance only. The gain clause (at most half the share of slow
      passes, 30 seen) is untouched.
  - **How jobs are started.** GitHub's clock started one of the first two scheduled jobs (03:05 dropped; 09:05
    started at 11:41). At that rate eight jobs take a week.
    - From now on a job is also started each time a run of the sixth book ends, about every 5 h 50 min, by
      GitHub's event and not its clock. The scheduled times stay; a job they start counts as before.
    - No one chooses when a job runs, so this is not a start by hand. Which arm takes the even minutes still
      follows the UTC hour of the start.
    - Nothing about what a job measures or which jobs count changes.
- **Nov 17 2026, 14:21 ET (orchestrator).** How jobs are started: the starter did not start anything.
  - **What happened:** the sixth book's run ended at 17:52 UTC and the fifth book's at 18:43 UTC. GitHub delivered
    no event for either: the starter workflow has no run at all, and the status report, which waits for the same
    event, did not run after them either. GitHub's own clock is worse than this morning: the status report's
    07:17 UTC job started at 16:54, and none of the pair or alternating jobs scheduled since 12:05 UTC has
    started.
  - **What does work** is a job starting another job directly. That is how each paper book starts its own next
    run, and it has not missed once.
  - **So the start moves into the hand-over.** When a run of the sixth book ends and its hand-over has started the
    next run, the same script also starts an alternating job. Same moment, same cadence, still nobody choosing.
    The separate starter workflow is removed so that a late event cannot start a second job.
  - The sixth book's workflow file, the alternating workflow and its tool stay as they are. Nothing about what a
    job measures or which jobs count changes. No job is started by hand, including the one missed today.
- **Nov 18 2026, 08:26 ET (orchestrator), morning look, before any read.** One change to how often jobs run.
  No measure, floor or period changes.
  - **Part 3 so far:** 5 jobs count. 152 timed steps with one worker and 152 with three; no pass over 6 s in
    either arm (the longest 3.4 s and 3.0 s); no budget fallback; at most 7 requests in a second; nothing
    rate-limited or refused. Slow one-worker passes: 0 of the 30 needed.
  - **Why that is a problem of the design and not yet a result.** A job samples one hour in about six. Slow
    spells have come about once a day for half an hour since Nov 17, and none has fallen into a job. At this
    rate I expect some 4 to 10 slow one-worker passes in the 14 days: the test would end as "the gain is not
    shown" for lack of slow minutes in the sample, whatever the option does.
  - **The change: from now to the end of the 14 days (Dec 1, 11:41 UTC) the jobs run back to back.** When an
    alternating job ends, it starts the next one, the way a paper book starts its next run (the same hand-over
    script, with the same rule that a run under 30 minutes starts nothing). The hand-over of the sixth book
    still starts one too; at most one job runs at a time and at most one waits.
    - What a job does and measures, which jobs count, the floor of 30, the 8 jobs, the four measures and the 14
      days from the first job all stay as written. Which arm takes the even minutes still follows the hour of
      the start.
    - **Why this does not tilt the test:** the two arms sit on alternating minutes inside every job, so more
      jobs add minutes to both arms alike. The read still happens once, when the counts are there, and the
      counts that end the waiting (jobs, slow one-worker passes) do not depend on which arm does better.
    - The alternating workflow gains one job that starts the next run. This replaces the sentence of Nov 17
      that the workflow stays as it is. The tool is unchanged.
  - **Said plainly: I have seen the two books side by side** before deciding this. In the half hour to 21:00 UTC
    on Nov 17 the fourth book had 11 budget fallbacks, the fifth 8 and the sixth, with three workers, none
    (longest pass 2.8 s). That is Part 4's material and one half hour; it decides nothing here, and it is not
    why the jobs run more often: the reason is the arithmetic above.
  - **The trades list stood still from 21:19 to 21:57 UTC on Nov 17** (bar-source plan, deviation log, today).
    The sixth book stopped new bids for those 38 minutes exactly as the fifth did; it is the same build. Part 4
    compares the two, so it does not move this test.
  - **In the half hour to 08:00 UTC on Nov 18** a whole trades pass ran out of its budget in the sixth book and
    in the fifth alike, after a failed candle request between steps (18 and 17 budget fallbacks). Counted by
    Part 4 as it is.
- **Nov 20 2026, 08:34 ET (orchestrator), at the read's start, before any research is fetched.** The period and
  the counts, and one clause of Part 4 restated with what I know.
  - **Period:** 00:00 UTC on Nov 17 to 23:59 UTC on Nov 19 (the sixth book's first event at 23:37 and first stepped
    minute at 23:41 on Nov 16). Counted from the two logs alone (scripts/owner/reconcile/count_bids.py): 725 new
    bids in the sixth book and 725 in the fifth on the 4,174 minutes both decided (decision minutes 4,248 and 4,246
    of 4,320). No extension.
  - **The control:** the fifth book ran commit 9e6f53b3 through the whole period. It changed to the bar-source
    plan's corrected build at 05:08 UTC on Nov 20, after the period.
  - **Part 4, measure 1: the cap is restated before the read, and I know what the old one would say.**
    - As written: bids the research would not have placed at most the fifth book's share plus 2.0 points *and at
      most 5%*. The 5% is the bar-source plan's cap.
    - That cap failed the fifth book on Nov 19: 7.04%, on a period that overlaps this one by 67 of its 72 hours,
      with the fourth book at 6.62% and the main book at 6.94%. The cause was checked and confirmed: the cut of
      the newest row, common to every book, which no input build controls (bar_source_prereg.md, "Result of the
      cause check"). The bar-source plan restated its cap for its second run for that reason.
    - **So I know the sixth book would fail the cap as written.** It reads the same rows as the fifth; I expect
      about 7%. I have not fetched the research for this read and have not seen the sixth book against it.
    - **The clause as it now stands:** at most the fifth book's share plus 2.0 points (unchanged), and at most 5%
      on the five coins whose candles are cut at the minute (ETH, SOL, XRP, LTC, ZEC). The share on all 17 coins
      is reported against 5%, deciding nothing.
    - **What this does to the odds, plainly:** it turns a fail I can foresee into a clause the book will probably
      meet. I make it anyway because the old cap measures a gap that has nothing to do with the number of
      workers, so failing on it would say nothing about the option. What the clause is for, catching a fault, is
      kept twice: against the control, and where the research can be matched.
    - A reader who discounts a rule changed this late can read the old clause in the output.
  - The matched share, the level share, items 1 to 5, the requests inside a step and the stops are unchanged.
    Part 3 is untouched.
  - **The rule script** is changed to this before it is run (Sonnet agent, reviewed), with its tests.
- **Nov 20 2026, 08:51 ET (orchestrator). The read, first pass: Part 4 is read; Part 3 is not complete; no verdict.**
  - **Order kept:** the period, the counts and the restated cap were logged and on `main` at 08:34 (13:34 UTC). The
    research fetch was started after that, at 13:34:37 UTC, and ended at 13:49 (runner job 44745514044; 1,224
    answers, nothing refused). The rule script's change reached `main` at 13:39 UTC (69d18dc6; Sonnet agent,
    reviewed, 177 checks), while the fetch ran and before any of the research was looked at. Then the two books,
    the status report on the cut logs, and the rule. Record: reports/owner/reconcile_tb/tw/README.md.
  - **The rule's line:** "PART 3 NOT COMPLETE: 45 of 8 jobs, 15 of 30 slow one-worker passes; the jobs go on and the
    read waits". No verdict.
  - **Part 4 on its period** (final; the period is over):
    - Measure 1, decisions: bids the research would not have placed 48 of 725 in the sixth book and 48 of 725 in
      the fifth (6.62% each); on the five coins 3 of 179 (1.68%; the cap as restated, 5%); research bids matched
      672 of 720 against 670 of 718; level 2 of 725. Met.
    - **The first version's cap would not be met** (6.62% on all 17 coins against 5%), as foreseen at 08:34.
    - Measure 2, items 1 to 5: all five meet (99.97% of trades bars verified; no rate-limit answer, no refusal;
      half-hour maximum 20 s or less in 99.3% of heartbeats; no error event; no unconfirmed row).
    - Measure 3, requests inside a step: 2 failed of 73,692; 26 inside a step of 77,634 coin-minutes (0.033%), and
      0.034% against the fifth book's 0.078% on the same heartbeat times. Met.
    - Measure 4, stops: no rate-limit stop in either book; request errors in 2 half hours each. Met.
  - **Part 3 so far, which decides nothing until it is complete:** median pass 2.609 s with three workers and
    2.632 s with one; passes over 6 s 6 of 1,360 and 15 of 1,382; passes out of budget 0 and 3; at most 7 requests
    in a second, nothing limited or refused; differing bars 42.89% and 43.26%. Ten of the 15 slow one-worker passes
    came in two jobs this morning (10:37 and 11:45 UTC).
  - **What happens now.** The alternating jobs go on by themselves. The rule is run again, unchanged, when the
    one-worker minutes hold 30 slow passes, or after 11:41 UTC on Dec 1 if they never do. Part 4's folder is not
    recomputed. No job is started by hand.
