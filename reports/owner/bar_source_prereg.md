# Where the twelve candle-path coins should take their newest bar from. Plan (Nov 11 2026, 08:50 ET)

Written by the orchestrator before any decision has been computed with a trades bar for any of the twelve coins.
Branch owner/charter.

## Why
- **The BTC fix works.** In the first interim look at the third paper book (reports/owner/reconcile_tb/i1/README.md)
  all 102 new bids were within a tick of the research level.
- **What remains is the score of the twelve coins read from candles** (DOGE, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE,
  HYPE, ENA, PEPE, ONDO). 8 of their 87 bids were ones the research would not have placed, and 10% of their bids were
  more than 5.5 score points from the research. On the five traded coins that read trades, 90% of bids were within
  0.05 points.
- **Input shares do not settle the source.** On the collector's record for Nov 11, 00:00 to 13:00 UTC, the trades bar
  was materially off the final candle less often than the first-seen candle for seven of the twelve, more often for
  four and level for one, and it was exactly equal less often for all twelve.
- So the sources have to be compared in units of the bot's decisions.

## What has been seen before this plan
- The input shares above, and the same for 4.3 hours of Nov 10.
- The third book's reconciliation for 01:47 to 12:30 UTC on Nov 11: the candle path as the bot runs it, at its bids.
- Nothing at the level of decisions for a trades bar on any of the twelve.

## The three ways to fill a coin's rows
- **A, candles (today):** the newest minute as the candle answer gives it when first seen; older rows as the venue's
  final candles.
- **B, trades kept:** the newest minute from the verified trades bar, cut at the minute; a trades-built row is never
  replaced. The engine does this today for a listed coin.
- **C, trades then candles:** the newest minute from the verified trades bar; every older row as the venue's final
  candle. The engine cannot do this today.
- In all three, BTC and the five listed traded coins are as the third book has them, so only the coin's own rows
  differ.

## Part 1: every minute, offline, on the collector's record
- **Window:** Nov 11 2026 02:00 UTC to Nov 14 2026 02:00 UTC, three full days. The tool is built and proven on the
  collector's record before 02:00 UTC on Nov 11 only.
- **Data:** the collector's trades bars for all 18 coins (built about 10 s after each minute), its first-seen
  candles, and the venue's final candles fetched at least an hour after the last minute, as the reconciliation does.
- **Computation:** for each of the twelve coins (and LTC and ZEC, reported only), each way A, B, C and every minute
  where all inputs exist, the bot's score and bid level from the bot's own table and feature code, against the same on
  final candles (the research).
- **Measures, per coin and way, per day and for the three days:**
  1. Disagreement on arming, the primary measure: among the minutes where the way or the research has a score above
     the threshold, the share where only one of them has. Also split into armed by the way only and by the research
     only.
  2. Score error: the median and the 90th percentile of the absolute difference.
  3. Level error: the share of minutes more than 5 bp from the research level.
- **Checks on the emulation** (it stands in for a bot that does not run):
  - B on ETH, SOL, XRP, LTC and ZEC against the third book's own logged score at its new bids: the share within 0.5
    points. If it is under 90%, Part 1 is reported and not used for any decision.
  - A on the twelve against the third book's logged score at its new bids: the share within 0.5 points, reported. The
    collector asks for candles with a different address than the third book and gets old copies more often, so A may
    look worse here than it is in the book.
- **Limits:** for B, rows before the collector's record began (Nov 10, 21:44 UTC) are final candles, so the long
  look-back inputs are not fully trades-built. One request time (about 10 s after the minute) stands for the bot's.

## Part 2: forward, a fourth paper book
- **The book:** identical to the third book except that its trades list holds all 18 coins. Own folder
  (paper_spot_t18), own workflow file, so the third book's test is not touched. It starts when its workflow is on
  `main`.
- **Read once,** when the third and fourth books have run three full days together and each has at least 300 new
  bids on the twelve coins in the minutes both were live. It waits if there are fewer.
- **Measures, on the minutes both were live, the twelve coins together** (the reconciliation's tools and
  definitions):
  1. Wrong-side share: of the book's new bids with a valid research score, the share whose research score is at or
     below the threshold.
  2. Matched share: of the research's new bids, the share with a bot bid within a minute.
  3. Level: the share of the book's new bids more than 5 bp from the research level.
- Items 1 to 5 of the third book's rule (FORWARD_TESTS.md) are read for the fourth book too, with 18 listed coins.

## Decision rule (fixed now)
- **Trades kept (B) for the twelve is proposed for the next release** if, in Part 2, the fourth book's wrong-side
  share is strictly lower than the third book's, its matched share is not lower, its level share is below 5%, and
  items 1 to 5 hold for it. Shares are compared exactly on the counts.
- **A coin stays on candles in that case** if, in Part 1, its disagreement share under B is higher than under A on
  each of the three days.
- **Trades then candles (C) is built into the engine** only if, in Part 1, its disagreement share for the twelve
  together is at least a fifth lower than both A's and B's on each of the three days. It then gets its own paper test
  before any release.
- **Otherwise the twelve stay on candles** and their remaining score error is recorded as a known gap.
- No P&L test. A list change is a release, with a note to Miles, and comes after release 3 or with it, not before.

## Interim looks
The tools may be run on part of a window to prove they work and to catch a fault. A look cannot pass either part and
changes no rule.

## How the reads are run (added Nov 11 2026, 11:24 ET; tools on `main`)
- **Part 1,** not before 02:59 UTC on Nov 14 (the fetch refuses a newest minute under an hour old). On a branch
  made from `main` for the read, so the runner's tables are reviewed before they reach `main`:
  `gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref BRANCH
  -f script=scripts/owner/bar_source/build.py
  -f args="--start 2026-11-11T02:00 --end 2026-11-14T01:59 --out reports/owner/bar_source"
  -f commit="reports/owner/bar_source" -f tag=bar-source -f sparse="bot edge scripts/owner scripts/forward"`
  About an hour on the runner (seven whole-book passes, about 30,000 engine steps). Then, with the third book's log
  current through 01:59 UTC on Nov 14:
  `python scripts/owner/bar_source/compare.py --dir reports/owner/bar_source --log paper_spot_tb/events.jsonl`
  Without `--log` the emulation checks do not run and the single-coin clause is reported as not applied.
- **Part 2,** not before both books' logs reach 22:29 UTC on Nov 14 (about 02:30 UTC on Nov 15; deviation log,
  Nov 12), and only with 300 new bids on the twelve in each book. The period is the fourth book's first three full
  days of decisions: 2026-11-11T22:30 to 2026-11-14T22:29, both minutes included (4,320 minutes). Steps, fixed on
  Nov 12 at 12:58 ET, before any of the read:
  1. A branch made from `main` once both logs are on it (for example owner/read-part2). Research on a runner:
     `gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref BRANCH
     -f script=scripts/owner/reconcile/fetch_and_compute.py
     -f args="--books paper_spot,paper_spot_tb,paper_spot_t18 --start 2026-11-11T22:25 --end 2026-11-14T22:29
     --out reports/owner/reconcile_tb/part2/research" -f tag=reconcile-part2
     -f sparse="bot edge scripts/owner reports/owner reports/cfm_products.csv paper_spot paper_spot_tb paper_spot_t18"
     -f commit="reports/owner/reconcile_tb/part2/research"`
  2. The two books, with the third as the first book and the fourth as the second:
     `python scripts/owner/reconcile/two_books.py --research reports/owner/reconcile_tb/part2/research
     --main paper_spot_tb --third paper_spot_t18 --start 2026-11-11T22:30 --end 2026-11-14T22:29
     --out reports/owner/reconcile_tb/part2`
  3. The fourth book's items 1 to 5 from the status report run on a copy of its log cut at the period's end (as
     for the third book's read: reports/owner/paper_reconcile_plan.md, step 6), then the rule:
     `python scripts/owner/bar_source/part2_rule.py --dir reports/owner/reconcile_tb/part2 --items-1-5 pass` (or
     `fail`). It reads the twelve coins on the common minutes and writes part2_rule.md. The script is the rule above
     as code (63 checks; on `main` since Nov 12, before any read). In that folder's tables the label "main" means
     the third book and "tb" the fourth.
  4. **If the bids are short** (fixed Nov 13 at 08:46 ET): if either book has fewer than 300 new bids on the twelve
     at 22:29 UTC on Nov 14, the period's end moves later in steps of six hours (04:29, 10:29, 16:29 UTC on Nov 15,
     and so on) until both have 300, and steps 1 to 3 use that end. The bids are counted from the two logs alone:
     arm events on one of the twelve coins at a minute that is a decision minute of both books
     (scripts/owner/reconcile/common.py, live_minutes). No research is fetched for a count.

## Result of Part 1 (read Nov 14 2026, 10:34 ET)
Run as "How the reads are run" says: runner job 43603482156 on branch owner/read-barsrc (4,320 decision minutes,
seven whole-book passes, 30,240 engine steps, 1,224 candle answers, nothing refused), then compare.py with the third
book's log. Tables: reports/owner/bar_source/ (summary.md has every coin and day).

- **The two checks on the emulation, read first.**
  - Way B on ETH, SOL, XRP, LTC and ZEC against the third book's logged score at its new bids: 240 of 249 within
    0.5 points (96.4%). The bar is 90%, so Part 1 may be used for its one decision.
  - Way A on the twelve: 486 of 528 within 0.5 points (92.0%). Reported, as planned.
- **The single-coin clause: no coin stays on candles.** For each of the twelve the score-miss share under C is
  lower than under A over the three days, and for no coin is it higher on two of the three days (it is higher on
  one day for six coins, on none for the other six).
- **The twelve together, three days, 51,840 coin-minutes:**

  | Measure | A, candles | B, trades kept | C, trades then candles | C with all 18 coins |
  |---|---|---|---|---|
  | Disagreement on arming | 240 of 49,272 (0.49%) | 378 of 49,376 (0.77%) | 167 of 49,239 (0.34%) | 163 of 49,237 (0.33%) |
  | Score more than 1.0 point from the research | 1,733 (3.3%) | 3,706 (7.1%) | 1,344 (2.6%) | 1,279 (2.5%) |
  | Level more than 5 bp from the research | 572 (1.1%) | 7,354 (14.2%) | 572 (1.1%) | 497 (1.0%) |

  - C has fewer score misses than A on each day: 393, 439 and 512 against 565, 561 and 607.
  - B is worse than A on every measure. Its level is off in one coin-minute in seven. That is why it was dropped as
    a candidate on Nov 11.
- **By coin, score-miss share under C against A:** DOGE 2.6% against 6.2%, HYPE 1.2% against 2.1%, NEAR 2.1% against
  3.2%, PEPE 5.1% against 6.1%, LINK 1.9% against 2.4%, SUI 1.8% against 2.2%, XLM 1.8% against 2.1%, ENA 3.4%
  against 3.9%, HBAR 3.0% against 3.3%, BCH 3.1% against 3.3%, AAVE 3.7% against 3.8%, ONDO 1.6% against 1.7%. The
  gain is large for DOGE, HYPE and NEAR and small for AAVE, ONDO and BCH.
- **LTC and ZEC, reported only** (score misses under A, B, C; then level more than 5 bp off): LTC 1.1%, 1.2%, 0.8%;
  level 1.2%, 2.8%, 1.2%. ZEC 3.0%, 1.4%, 1.3%; level 1.5%, 4.1%, 1.5%. Keeping trades rows puts the level off more
  often for both; C does not. This agrees with the third book's read, which took LTC off the list and found ZEC's
  level errors.
- **Limits:**
  - **The level column says little about the bot.** The level errors under A and C fall in 54 minutes, and in 50 of
    them at least ten of the twelve coins are off at once, which points to BTC. In 40 of the 54 the collector's own
    BTC bar was a fallback, one minute or an hour back (it could not verify 49 of its 4,575 BTC bars). The third
    book had no fallback in its three days.
  - **The gain is modest in size.** C removes about a fifth of A's score misses and about a third of its
    disagreements on arming. Whether that shows in a running book is Part 2's question.
- **What it decides:** the single-coin clause only. If Part 2 passes, all twelve go to way C and none is held back.

## Result of Part 2 (read Nov 15 2026, 02:37 ET)
Run as "How the reads are run" says, steps 1 to 4. The record is reports/owner/reconcile_tb/part2/README.md.

- **The count came first, from the two logs alone:** at 22:29 UTC on Nov 14 the third book had 452 new bids on the
  twelve and the fourth 435, on 4,187 common decision minutes. Both are over 300, so the period is the planned one
  (22:30 UTC on Nov 11 to 22:29 UTC on Nov 14) and was not extended.
- **Research:** runner job 43689324147 on branch owner/read-part2, 1,224 answers, nothing refused or dropped.
- **The fourth book's items 1 to 5,** on its log cut at the period's end: all five meet. 73,068 of 73,170 trades
  bars verified (99.86%); no refusal and no rate-limit stop; data step median 13.5 s (bar 15 s), half-hour maximum
  20 s or less in 97.2% of 141 heartbeats; no error event; no unconfirmed row. Engine commit 58eba8b throughout.
- **The rule, on the twelve:**

  | Measure | Third book | Fourth book | Verdict |
  |---|---|---|---|
  | New bids the research would not have placed | 20 of 452 (4.42%) | 18 of 435 (4.14%) | pass (strictly lower) |
  | Research's new bids with a bot bid within a minute | 414 of 448 (92.41%) | 404 of 434 (93.09%) | pass (not lower) |
  | New bids more than 5 bp from the research level | 4 of 452 (0.88%) | 4 of 435 (0.92%) | pass (under 5%) |

- **Part 2: pass.** Trades for the newest minute with the venue's candle afterwards, for all 18 coins, is the
  proposal for the next input release. By Part 1's single-coin clause no coin is held back.
- **How strong it is.**
  - On the twelve the two books are nearly the same: the first measure passes by two bids, the wrong-side bids
    fall on the same coins in both books, and the four level errors are the same four bids (one minute, 15:43 UTC
    on Nov 13). Three days of bids cannot tell the two ways apart on these coins. Part 1 is the measure of the
    difference: about 30% fewer disagreements on arming and about a fifth fewer score misses.
  - The clear gains are outside the rule. On ETH, SOL, XRP, LTC and ZEC, which the third book keeps on trades
    rows: wrong-side bids 5 of 292 against 1 of 281, level errors 7 against 2 (ZEC 5 against 1). And minutes with
    no new bid because an answer was old: 763 coin-minutes in the third book, 4 in the fourth.
- **What it does not settle:** the step. The fourth book's data step ended a median 13.5 s after the minute. The
  release is built so that its bids rest no later than release 3's, and runs as a paper book first (deviation log,
  Nov 14 and Nov 15).
- **The third and fourth books have done their work.** They keep running unchanged for now; the plan for the
  paper test of the build will name its control.

## Addition: candles after the bids (plan fixed Nov 15 2026, 02:07 ET, before any evaluation)
- **Why.**
  - The fourth book's way asks for 18 candles and then 18 coins' trades before it decides. Its data step ends a
    median 13.4 s after the minute, against 10.3 s for release 3's way. The live bot's bids would rest three seconds
    later (FORWARD_TESTS.md, the note of Nov 14).
  - A build that moves the candle requests to second 45 of the minute exists (branch owner/release-4). Its builder
    found the flaw in that design: the request at second 45 has the same address as the request every other client
    of this engine makes at the start of the minute, and the venue's cache hands out a copy for a minute or more
    (collector's record of Nov 14: BTC's candle answer was a cached copy in 96% of minutes with a median age of
    65 s; copies up to 184 s old). A copy made at second 8 cannot confirm the minute that just closed, by the
    engine's own rule. So the pass would often leave the row behind the newest one unconfirmed, and whether it does
    would depend on who else is asking.
  - The robust alternative: ask for the candles after the bids are placed. The decision then reads trades bars for
    its two newest rows and the venue's candles from the third row on, every minute, whoever else is asking.
- **The question.** What does the second trades row cost in decisions?
- **Method: Part 1's tool, period and record, with one more rule.**
  - **C2:** rows t-1 and t-2 as in B (the verified trades bar; a minute without one takes the candle path's row);
    every older row the final candle. Way C has only row t-1 from trades.
  - One more pass, **C2x18:** all 18 coins on C2. It is the book the build would run.
  - Period 2026-11-11 02:00 to 2026-11-14 01:59 UTC, as Part 1. The earlier passes must reproduce Part 1's
    published counts exactly; if they do not, nothing is read until the difference is explained.
- **Measures,** as in Part 1, for the 17 traded coins together and by coin and day: the share of coin-minutes that
  disagree with the research on arming, the share with a score more than 1.0 point off, the share with a level more
  than 5 bp off.
- **Rule (fixed now).** The candle requests move behind the bids if, over the three days and the 17 coins together:
  1. C2x18's disagreement on arming is no higher than the third book's inputs give (pass A: the twelve on first-seen
     candles, the listed coins on kept trades rows);
  2. C2x18's share of scores more than 1.0 point off is no higher than pass A's;
  3. C2x18's share of levels more than 5 bp off is no more than 0.5 points above C18's.
  - **Why pass A is the bar:** the build is faster than release 3's way by about a second. If its decisions are no
    worse than release 3's as well, it is the better of the two on both counts. Against the fourth book's way it
    gives up some agreement to gain about four seconds; C2 against C18 is reported so that this price is on record.
  - **If it fails:** the candle requests stay ahead of the decision, the data step is not shortened this way, and a
    release with all 18 coins from trades waits for another way to meet the step-time condition.
- **Limits:** those of Part 1 (the collector's record; its BTC fallbacks; one period of three days). The paper book
  that runs the build is the forward test, on a rule fixed before it starts.

## Result of the addition (read Nov 16 2026, 08:33 ET)
The run finished at 08:58 UTC on Nov 15 (job 43689717933, branch owner/read-c2). Nothing was read before Nov 16.

- **Part 1's counts are reproduced exactly:** every count of every pass, coin and day equal; 440,640 rows compared
  with Part 1's table, none differs.
- **The 17 traded coins together, three days:**

  | Pass | Disagree on arming | Scores more than 1.0 off | Levels more than 5 bp off |
  |---|---|---|---|
  | A: the third book's inputs | 278 of 63,371 (0.44%) | 1,933 of 73,440 (2.63%) | 1,029 of 73,440 (1.40%) |
  | C18: one trades row (the fourth book) | 188 of 63,326 (0.30%) | 1,434 of 73,440 (1.95%) | 730 of 73,440 (0.99%) |
  | C2x18: two trades rows | 193 of 63,330 (0.30%) | 1,473 of 73,440 (2.01%) | 730 of 73,440 (0.99%) |

- **The rule:** clause 1 met (193 of 63,330 against 278 of 63,371), clause 2 met (1,473 against 1,933), clause 3
  met (730 against 730). **Pass.**
- **What the second trades row costs:** five more disagreements on arming and 39 more score misses in three days
  over 17 coins; the levels do not change. No coin is worse than under pass A on arming or on scores.
- **Where the second row came from:** a verified trades bar in 76,250 of 77,760 coin-minutes, a verified empty
  minute in 1,461, the final candle (no verified bar) in 49.
- **What follows,** as fixed on Nov 15 before the output: two trades rows are acceptable, so the candle requests
  leave the step. The build with the request at second 45 goes to its paper test as it is. Its floor is this
  pass; with fresh answers it is the fourth book's way.
- **Tables:** reports/owner/bar_source_c2/ (c2_summary.md, c2_counts.json, c2_per_coin.csv, the run's table).

## Part 3: the build as a paper book (plan fixed Nov 16 2026, 08:38 ET, before the book exists)
- **Why.** Parts 1 and 2 and the addition settle which rows the decision should read. They do not show that the
  build which reads them keeps the step early, or that its candle requests between steps work against the real
  venue. Both were made conditions of the release on Nov 14, to be met by a paper book on a rule fixed first.
- **The fifth book** (`paper_spot_r5`): the build on branch owner/release-5, which is `main` with the input build
  merged in, at one pinned commit. It runs that commit's own `bot/spot/config.json`, the file the release would
  ship: all 18 coins take the newest minute from trades, the venue's candle replaces it afterwards, and the candle
  requests for those coins are made at second 45, between steps. $250,000 of paper money, its own workflow and
  runner, like the fourth book.
  - The commit is named in the deviation log before the book's first run, after the full offline suite has passed
    on it on a runner. A different commit restarts the three days.
- **Controls, unchanged while the test runs:** the fourth book (engine commit 58eba8b: the same rows with the
  candle requests inside the step) and the main book (release 4 on `main`, release 3's inputs).
- **The third book ends when the fifth starts.** Its question was answered by release 3, and the main book runs
  nearly its inputs. Its folder and log stay as the record.
- **Period.** From the first half-hour mark after the fifth book's first decision minute, 4,320 minutes. It is
  extended by six hours, at most three times, while the fifth or the fourth book has fewer than 300 new bids on the
  17 coins on the minutes both were live (counted from the two logs before any research is fetched). After the
  third extension the read is made on what there is.
- **Measures. All four must hold.**
  1. **The step** (the condition of Nov 14: no later than release 3). From the half-hour heartbeats inside the
     period, each book's median of the data step's end (`step_s`, `data`, the first number):
     - the median of the fifth book's values is at or below 10.3 s (release 3's way measured over the third
       book's three days: 10.26 s);
     - and, over the half hours in which both the fifth and the main book have a heartbeat, the median of the
       fifth book's values is no higher than the median of the main book's.
  2. **Decisions,** both books against the research with Part 2's tools, all 17 coins, the minutes both the fifth
     and the fourth book were live:
     - bids the research would not have placed: the fifth book's share is at most the fourth's plus 2.0 points,
       and at most 5%;
     - the research's new bids with a bot bid within a minute: the fifth book's share is at least the fourth's
       minus 3.0 points;
     - bids more than 5 bp from the research level: under 5% of the fifth book's bids.
     - **Why tolerances and not "no worse":** the two books read the same rows except where a candle answer was a
       copy, and the emulation puts that difference at 5 disagreements in 63,000. With about 700 bids a book in
       three days, a share near 3% moves by 0.6 points and a share near 93% by 1 point from chance alone. The
       tolerances are a little over two such steps of the difference. This measure is there to catch a fault, not
       to rank the two ways; Part 1 and the addition did that.
  3. **Items 1 to 5** for the fifth book with all 18 coins listed, as for the fourth book, with one change: item
     3's median is measure 1. Its other half stays: the data step's half-hour maximum at or below 20 s in at least
     95% of heartbeats.
  4. **The candle requests between steps,** from the heartbeat counters over the period:
     - failed requests (`pre_error`) are at most 1% of the requests made (`pre_fetched` plus `pre_error`);
     - candle requests that had to be made inside a step for a trades-built coin (`pre_missing` plus
       `pre_ondemand`), leaving out the first step after each start, are at most 2% of coin-minutes.
- **Reported, not part of the rule:** each book's bids and fills side by side; how often a coin had two or more
  trades rows at a decision, as far as the counters show it; the measures for the twelve and the five apart; P&L.
- **One read.** Interim looks may stop the test for a fault (a crash, a refusal, a rate-limit stop, an error
  event). They cannot pass it and change no rule.
- **A pass** makes the build's configuration release 5 for the main book, W2 and the live bot, with a release
  note. Test A does not restart (FORWARD_TESTS.md, note of Nov 14).
- **A fail:**
  - on measure 1: the build is not released; the twelve stay on candles until a step fed another way (a trade
    stream) exists and has its own test;
  - on measure 2 or 3: no release; the cause is found first, and a corrected build starts a new three days;
  - on measure 4 alone: the same, since requests inside the step are what the build exists to avoid.

## Result of Part 3 (read Nov 19 2026, 19:14 ET)
Run as fixed: the bid count from the two logs first (deviation log, Nov 19), then the research on a runner, the
status report on the logs cut at the period's end, the two books against the research, and the rule script. One
read, rule as written. The record is reports/owner/reconcile_tb/part3/README.md.

- **Part 3: fail, on one clause of measure 2. No release 5.** The cap on bids the research would not have placed
  is not met: 49 of 696 (7.04%) against 5%. Every other clause of measure 2 and measures 1, 3 and 4 are met.
- **Period:** 2026-11-16 19:00 to 2026-11-19 18:59 UTC, 4,320 minutes; both books decided in 4,168 of them. New
  bids on the 17 coins in those minutes: fifth book 696, fourth book 695.
- **Research:** runner job 44637871745 on branch owner/read-part3, 1,224 answers, nothing refused or dropped,
  fetched about four and a half hours after the last minute.
- **The rule** (scripts/owner/bar_source/part3_rule.py; part3_rule.md is its own output):

  | Measure | Value | Rule | Result |
  |---|---|---|---|
  | 1 (a) Same-machine pairs, build minus release 3 | median -1.485 s over 14 pairs | at or below zero, at least 8 pairs | met |
  | 1 (b) Fifth book against main book, same half hours | 8.61 s against 11.05 s, 140 half hours | fifth no higher | met |
  | 2 Bids the research would not have placed, against the fourth book | 49 of 696 (7.04%) against 46 of 695 (6.62%) | at most the fourth's share plus 2.0 points | met |
  | 2 The same, cap | 49 of 696 (7.04%) | at most 5% | **not met** |
  | 2 Research's new bids with a bot bid within a minute | 641 of 688 (93.17%) against 645 of 692 (93.21%) | at least the fourth's share minus 3.0 points | met |
  | 2 Bids more than 5 bp from the research level | 2 of 696 (0.29%) | under 5% | met |
  | 3 Items 1 to 5, fifth book | 72,965 of 73,044 trades bars verified (99.89%); no refusal, no rate-limit stop; half-hour maximum 20 s or less in 99.3% of 142 heartbeats; no error event; no unconfirmed row | all five | met |
  | 4 Failed candle requests between steps | 1 of 72,792 (0.001%) | at most 1% | met |
  | 4 Candle requests inside a step | 70 of 76,518 coin-minutes (0.09%) | at most 2% | met |

- **What the fail is.**
  - **The build is not worse than its control.** The fourth book's 46 wrong-side bids are all among the fifth
    book's 49; 686 of the bids are the same bid in both books. The clause that compares the two is met with
    room.
  - **The cap is an absolute bound, and the control misses it as well.** So does the main book, on release 3's
    inputs: 47 of 677 (6.94%) over the same period (run after the verdict; it decides nothing).
  - **By the rule as written it is a fail.** The plan's branch for measure 2: no release; the cause is found
    first, and a corrected build starts a new three days.
- **Reported, not part of the rule.**
  - **The twelve and the five apart** (fifth book, then fourth):
    - bids the research would not have placed: the twelve 46 of 530 (8.68%) and 43 of 534 (8.05%); the five
      (ETH, SOL, XRP, LTC, ZEC) 3 of 166 (1.81%) and 3 of 161 (1.86%);
    - research bids matched: the twelve 481 of 525 (91.62%) and 487 of 531 (91.71%); the five 160 of 163
      (98.16%) and 158 of 161 (98.14%);
    - level more than 5 bp off: one bid on the twelve and one on the five in each book.
  - **Fills and P&L.** Both books had the same two first-bid fills (NEAR at 15:44 UTC on Nov 18, BCH at 01:34 on
    Nov 19), and the research had both. The research had a third, PEPE at 15:51 on Nov 19, that neither book
    had. Exit P&L -$81.73 (fifth) and -$81.63 (fourth) on $23,095 and $23,076 bought.
  - **Trades rows at a decision,** as far as the counters show it: 3,545 times a row three to six minutes old
    was still built from trades, of about 306,000 such rows looked at (1.2%).
  - **The standstill window of Nov 17** (21:19 to 21:57 UTC). The research placed 8 new bids. The fourth book
    placed the same 8: none on the wrong side, none off the level, seven of the eight scores within 0.1 point.
    The fifth book placed none (38 stopped minutes). **The veto rule of Nov 18 is not triggered** (0 of 8 wrong;
    five were needed), so the fallback to candles inside the step stays in the corrected build.
  - **The pairs.** 14 count. The build's data step ended earlier in every one, by 1.03 to 2.80 s. Four pairs
    ran release 3 first (differences -1.07, -2.44, -2.56, -1.14 s) and ten the build first.

## After Part 3: the cause (written Nov 19 2026, 19:14 ET, before the check below was run)
- **Looked at after the verdict.** All of it is exploratory and changes nothing above.
  - **The books agree with one another; the difference is against the research.** At the 64 bids that the main
    and the fourth book share and whose score is more than 2 points from the research, the two books logged the
    same score within 0.1 point in all 64. Their newest rows come by different ways (a candle as first seen, a
    trades bar), so what they share is what a bot can see at the minute, not a fault of one way.
  - **The differences are large and the level is right.** At a wrong-side bid the book's score is a median 11.6
    points from the research's; the bid level is on the same tick. The level is anchored on the coin's close an
    hour back and on BTC (edge/wick.py), so a different newest close of the coin moves the score and not the
    level.
  - **It is not new and it is not the build's.** The fourth book has run one commit since Nov 11. On the twelve
    it had 18 wrong-side bids of 435 in Part 2 (4.1%) and has 43 of 534 now (8.1%). A score more than 2 points
    from the research: 8.7% of its bids on the twelve then, 12.4% now; on the five 0.4% then, 1.8% now.
  - **Mostly a minute apart.** At 29 of the fourth book's 46 wrong-side bids the research has a new bid of its
    own on that coin within a minute.
  - **A first guess was checked and dropped:** that coarse price ticks make these coins' scores jump. The share
    of large differences by coin does not follow tick size (rank correlation 0.07 to 0.15 over the 17 coins).
- **The leading explanation is on record since Nov 10** (candle clock study, candle_clock_prereg.md, "Result").
  - For the twelve coins the venue's final candle of a quiet minute holds trades from the first seconds of the
    next minute: in 8% to 41% of boundaries, by a median of 7 to 11 s. The research decides on that candle. A bar
    cut at the minute cannot equal it, whichever way the bot gets it.
  - For BTC and the five the candle is cut at the minute or nearly so, and there the books agree with the
    research (wrong side under 2% in both parts).
  - This is the gap left open on Nov 10 and the row "What the candle's late cut gives the research on thin
    coins" in FORWARD_TESTS.md.
- **The cap was badly set, and that was my error.** I wrote 5% on Part 2's level for all 17 coins (2.7% to
  3.4%). The gap moves with how quiet the market is and with the share of bids that fall on the twelve (61% of
  the fourth book's bids in Part 2, 77% now), and the cap left no room for either. The verdict stands as read.
- **The check, fixed now, before it is run.** It decides nothing about Part 3.
  - **Run:** Part 1's tool on Part 3's period (scripts/owner/bar_source/build.py on a runner: the collector's
    record and the venue's final candles). Its pass C18 is the fourth book's inputs emulated: row t-1 from the
    collector's trades bar, cut at the minute, every older row the final candle. Pass A is the main book's.
  - **(i) The emulation stands for the book** if pass C18's score is within 0.5 points of the fourth book's
    logged score at 90% or more of its new bids in the period. This is Part 1's own bar.
  - **(ii) The explanation is confirmed** if, at the fourth book's bids whose logged score is more than 2 points
    from the research, pass C18 is within 0.5 points of the book's score at 80% or more. C18 differs from the
    research in one thing only, the cut of row t-1, so the difference then comes from that row, the coin's own
    or another coin's. Under 50%: not explained by the newest row, and every input at those bids is compared
    next. In between: explained in part, and reported as that.
  - **Reported with it:** the same for the main book against pass A; C18's disagreement on arming and its share
    of scores more than 1.0 point off for this period next to Part 1's (0.30% and 1.95%); the twelve and the
    five apart.
- **What follows if it is confirmed.**
  - The gap is common to every input path, the live bot's included. No input build removes it, and it is not
    the fifth book's fault.
  - **The corrected build** is the tested build plus the fallback for a trades list that stands still, the one
    weakness this test did find: commit 815ea390 on branch owner/standstill (it also carries the balance look;
    full offline suite passed on a runner, job 44533821743). It starts a new three days, as the fail branch
    asks, on a rule written into this plan before its first run.
  - **What the late cut gives the research on the twelve** moves to the top of the research list. If the
    research's result on those coins leans on seeing a few seconds into the minute it bids in, the live bot's
    return on them is lower than the research's, and no input fix will show it. Its plan is written before any
    trade print is fetched.

## Result of the cause check (read Nov 19 2026, 20:22 ET)
Run as fixed in the section above: runner job 44644238137 on branch owner/read-part3 (4,320 decision minutes, 30,240
engine steps, 1,224 candle answers, nothing refused), then scripts/owner/bar_source/book_check.py. The record is
reports/owner/bar_source_p3/README.md.

- **(i) The emulation stands for the book:** pass C18 is within 0.5 point of the fourth book's logged score at 671
  of its 709 new bids (94.6%; 90% needed).
- **(ii) Confirmed:** of the 70 bids whose logged score is more than 2 points from the research, pass C18 gives the
  book's score at 67 (95.7%; 80% needed). The other three are minutes in which the collector's trades bar was empty.
  All 46 wrong-side bids are on the book's side in the emulation.
- **Reported with it.**
  - The fifth book against the same pass: 665 of 702 within (94.7%); 66 of its 71 far bids (93.0%); 47 of its 49
    wrong-side bids on the book's side.
  - The twelve and the five apart, fourth book: (i) 519 of 542 and 152 of 167; (ii) 64 of 67 and 3 of 3.
  - On every minute, pass C18 against the research, this period and Part 1's: disagreement on arming 275 of 60,757
    (0.45%) against 0.30%; scores more than 1.0 point off 1,390 of 73,437 (1.89%) against 1.95%; levels more than
    5 bp off 2.01% against 0.99%.
  - **The main book against pass A cannot be read.** In that pass BTC keeps its trades rows and a minute without
    trades has no row; in the 38 minutes of Nov 17 in which the trades list stood still that leaves BTC flat for
    good, where the real book took candles. The main book's bids are within 0.5 point of pass A at 80 of 92 before
    the standstill and at 328 of 546 after it. Nothing is concluded from it.
- **What is established.** Put a trades bar cut at the minute in place of the newest row, leave everything else as
  the research has it, and the book's score comes out at the bids where book and research disagree. The cause of
  the wrong-side bids is the cut of the newest row. It is common to every book, and no input build controls it.
- **What is not established here:** why the bar cut at the minute differs from the venue's final candle. The Nov 10
  study says the final candle of the twelve runs into the next minute, and the split agrees (67 of the 70 far bids
  are on the twelve). The late-cut replay (late_cut_prereg.md) sets prints against candles at the minutes that
  matter, and prices the difference.
- **On every minute nothing got worse.** The share of scores off is what it was in Part 1's period. The share at
  new bids doubled because a new bid is placed where the score crosses the line.

## Part 3, second run: the corrected build (plan fixed Nov 19 2026, 20:22 ET, before the book has run the new commit)
- **Why.** The first run failed on measure 2, and the branch for that is: the cause first, then a corrected build
  and a new three days. The cause is found (above).
- **The corrected build** is commit 815ea3900e9e74c59a451ea0c2365e49fa631cd2 on branch owner/standstill: the build of the first run plus two things.
  - *The fallback for a trades list that stands still* (`standstill_candles`): when BTC's trades answer is verified
    and holds no trade in the closed minute, the step asks for BTC's candle; if that has a traded row the list is
    behind, and every coin's newest row is taken from a candle asked inside the step, as release 3 does. This is
    the weakness the first run found; the window of Nov 17 did not veto it.
  - *The balance look* for the live bot (two looks before a balance warning). A paper book places no real order,
    so it does nothing here.
  - The full offline suite passed on this commit on a runner (job 44533821743; 24 file runs, no failure).
- **The book.** The fifth book (`paper_spot_r5`) goes on with its paper money, state and log. Only the commit its
  workflow pins changes, and with it the file it runs: that commit's own bot/spot/config.json, the first run's
  settings plus `standstill_candles`. The change takes effect at the book's next hand-over. Controls, unchanged:
  the fourth book (58eba8b) and the main book.
- **Period.** From the first half-hour mark after the first decision minute of the first run on the new commit
  (named in the deviation log from paper_spot_r5/CODE once it has started), 4,320 minutes. Extended as in the
  first run: by six hours, at most three times, while the fifth or the fourth book has fewer than 300 new bids on
  the 17 coins on the minutes both decided.
- **Measures. All four must hold.**
  1. **The step,** as in the first run after its revision of Nov 16: (a) same-machine pairs on the new commit (the
     pair file names the commit it ran), the median of the build's data step minus release 3's at or below zero
     over at least 8 pairs; (b) over the half hours in which both the fifth and the main book have a heartbeat,
     the fifth book's median no higher than the main book's.
  2. **Decisions against the research** (Part 2's tools):
     - against the fourth book, all 17 coins, the minutes both decided: the fifth book's wrong-side share at most
       the fourth's plus 2.0 points; its matched share at least the fourth's minus 3.0 points; its bids more than
       5 bp from the research level under 5%. As in the first run.
     - **against the main book,** all 17 coins, the minutes the fifth and the main book both decided: the fifth
       book's wrong-side share at most the main book's plus 2.0 points. New.
     - **the cap, restated:** on the five coins whose candles are cut at the minute (ETH, SOL, XRP, LTC, ZEC), the
       fifth book's wrong-side share at most 5% (the minutes it shares with the fourth book).
  3. **Items 1 to 5** for the fifth book with all 18 coins listed, on its log from the first event of the first
     run on the new commit to the period's end; item 3's median is measure 1.
  4. **The candle requests between steps,** as in the first run: failed requests at most 1% of requests made;
     requests inside a step at most 2% of coin-minutes, the first step after each start left out. A step in which
     the fallback acts asks for candles inside the step by design; those requests count like any other.
- **What changed in the rule against the first run, and why.** Said plainly, because a rule changed after a fail is
  weaker evidence than a rule that held.
  - The first run capped the wrong-side share at 5% on all 17 coins. It failed at 7.0% with the control at 6.6%
    and the main book at 6.9%, on a gap no build controls. A cap is there to catch a fault the controls share. It
    is now set where the research can be matched: on the five, where the fifth book had 1.8% in the first run and
    the fourth 0.4% in Part 2.
  - A second control on a different input path is added: the main book reads the twelve from candles. A fault of
    the trades path shared by the fourth and fifth books would pass the first comparison and not this one.
  - What limits the weakness: the rule is fixed before the new commit has run a minute; both controls must be
    passed; and the first run's clause is still computed and reported next to the result (the all-17 share against
    5%), deciding nothing.
- **Reported, not part of the rule:** the all-17 wrong-side share against the first run's 5%; the twelve and the
  five apart; bids, fills and P&L side by side; the steps in which the fallback acted (`tb_frozen`) and what the
  book did in them; the pairs' order split.
- **One read.** Interim looks may stop the test for a fault (a crash, a refusal, a rate-limit stop, an error
  event). They cannot pass it and change no rule.
- **A pass** makes this commit's configuration release 5 for the main book, W2 and the live bot, with a release
  note that says what the fallback and the balance look do. **A fail:** the first run's branches.
- **The rule as code** (a second rule script next to part3_rule.py, which stays as the first run's record) is on
  `main` before the read.

## Deviation log
- **Nov 11 2026, 09:17 ET (orchestrator).** Made after the tool's development run and before any minute of either
  registered window was read for this plan.
  - **What the development window showed** (Nov 10 21:50 to Nov 11 01:59 UTC, 250 minutes; outputs on branch
    owner/bar-source, reports/owner/bar_source_dev):
    - A coin's score reads two inputs built from all the other coins. Each way is therefore computed as a whole book
      that could exist (six passes). This changes no rule.
    - **Way B puts the bid level off.** With trades rows kept, the level of the twelve was more than 5 bp from the
      research in 282 of 3,000 coin-minutes (9.4%; 1.6% to 22% by coin), against 4 under A and under C. The level
      rests on the coin's close an hour back, and a trades bar's close differs from the final candle's wherever the
      candle ran late. ZEC, which the third book keeps on trades, shows 5.2% in the same minutes.
    - Disagreements on arming are few: 5 to 9 in about 2,700 coin-minutes, because the research was armed in about
      90% of them. A rule that asks a margin on each day would turn on a handful of minutes.
    - A's score error is small in this emulation (90th percentile 0.1 point), far below what the third book showed at
      its bids. The check against the book's log decides whether the emulation can be trusted.
  - **Changes:**
    1. **Part 2 tests way C, not B.** The fourth book takes the newest minute of all 18 coins from trades and
       replaces each such row by the venue's candle once a late enough answer holds it. That needs an engine option.
       It is built on a branch, and the fourth book runs the code of that branch, so the engine on `main` is not
       touched while the third book's test runs.
    2. **B is no longer a candidate** for the twelve. It stays in Part 1 as a reported column.
    3. **The decision rule, restated:**
       - Way C for the twelve, with the six listed coins on the same way, is proposed for the next release if, in
         Part 2, the fourth book's wrong-side share on the twelve is strictly lower than the third book's, its
         matched share is not lower, its level share is below 5%, and items 1 to 5 hold for it.
       - The clause that C is built only on a one-fifth margin in Part 1 is dropped. The option is built now, for the
         forward test. A release still needs Part 2.
       - The single-coin clause compares C with A on a measure with enough events, the score-miss share: the share
         of minutes whose score is more than 1.0 point from the research. A coin stays on candles if Part 1 has its
         score-miss share under C strictly higher than under A over the three days and on at least two of the three
         days. The clause applies only if the emulation check on B passes.
    4. **Part 1 gains** the score-miss share, per coin and way, and a pass with all 18 coins on way C, which is what
       the fourth book runs.
  - Nothing else changes: the windows, the data, the two emulation checks, and no P&L test.
- **Nov 11 2026, 11:13 ET (orchestrator).** Made before the fourth book's first run, on the engine option's tests and
  two smoke runs on the real market. No minute of either registered window has been read for this plan.
  - **The option is built** (branch owner/engine-c, commit 58eba8b; key `trades_rows: "candle_after"`): the decision
    for a minute uses its trades bar; a candle answer made at least 85 s after the minute began then replaces the row,
    or drops it where the venue has no bar. With the key absent the engine is identical to `main` (the stored replay
    gives the same 530 events in three modes; all existing tests pass).
  - **Smoke run 43044140767** (45 minutes, all 18 coins): every row the engine held, the newest three minutes left
    out, was identical to a fresh fetch of the venue's candles, for all 18 coins. 666 of 666 trades bars verified.
    540 trades rows were built in the full half hour, 537 were replaced by the candle and 3 dropped; in 48 of the
    replacements the candle's close differed from the trades bar's by more than a tick.
  - **Step time:** the data step finished a median of 13.3 to 13.5 s after the minute (maximum 17.7 s); an earlier
    eight-minute smoke of 18 coins had 11.6 s. Eighteen trade requests take about 3.5 s more than six.
  - **Changes:**
    1. **Item 3 for the fourth book** reads: data step median 15 s or less, and the 30-minute maximum 20 s or less in
       95% of heartbeats. The 13 s bar was set for a book with six coins on trades. The timing study's slower bracket
       placed bids 15 s after the minute and found no cost it could measure. A faster data step is a separate change
       for later, with its own check.
    2. **The engine commit is fixed for the test.** The fourth book runs commit 58eba8b, named in the workflow file
       and written into paper_spot_t18/CODE at every run. A change of that commit starts its three days again.
- **Nov 12 2026, 08:54 ET (orchestrator).** A date moves; no rule changes.
  - **What happened:** the fourth book's first run (43056376442, 16:15 to 22:05 UTC on Nov 11) ended without saving
    its log or its state, because every push failed on the runner's token. The book began again from nothing with
    run 43110721127; its first step was at 22:25 UTC on Nov 11.
  - **Part 2's three days run from 22:25 UTC on Nov 11 to 22:24 UTC on Nov 14.** The read waits until both books'
    logs reach that minute (the fourth book's arrives with the run that ends at about 02:30 UTC on Nov 15) and for
    300 new bids on the twelve in each book.
  - **What had been read when this was written:** one interim look at both books' bids for 22:25 UTC on Nov 11 to
    10:00 UTC on Nov 12 (reports/owner/reconcile_tb/i2/README.md): 59 and 70 new bids on the twelve, no wrong-side
    bid and no level error in either. It changes no rule.
  - Nothing else changes.
- **Nov 12 2026, 12:58 ET (orchestrator).** A five-minute correction and the read's steps; no rule changes.
  - **Correction:** this morning's entry gave 22:25 UTC on Nov 11 as the fourth book's first step. 22:25 is its
    first event, the start of its download. Its first decisions are at 22:30 UTC. Its first three full days of
    decisions are therefore 22:30 UTC on Nov 11 to 22:29 UTC on Nov 14, and that is Part 2's period. None of the
    five minutes concerned had happened when this was written.
  - **The rule is now code** (scripts/owner/bar_source/part2_rule.py; agent, reviewed): the two conditions, the
    three measures on the twelve and the fourth book's items 1 to 5 as an input. Two points the plan left open are
    settled in it: a measure with no bids to count waits instead of failing, and "three full days" is checked as a
    period of at least 4,320 minutes.
  - **The exact commands** are in "How the reads are run". The only look at these books' bids so far is the interim
    one of this morning (59 and 70 bids on the twelve, no wrong-side bid in either).
- **Nov 13 2026, 08:46 ET (orchestrator).** What happens if the bids are short; no rule changes.
  - **Why:** the rule waits for 300 new bids on the twelve in each book but did not say how the period's end is
    then chosen. Left open, the end could be picked after seeing results.
  - **Fixed now:** the end moves later in whole steps of six hours until both books have 300 (step 4 of "How the
    reads are run"). The count uses the logs only.
  - **What was known when this was written:** the counts from the logs through 09:00 UTC on Nov 13: 158 new bids on
    the twelve in the third book and 159 in the fourth, on 2,008 common minutes. At that pace both reach about 330
    by 22:29 UTC on Nov 14. No research has been fetched for these books since the interim look of Nov 12.
- **Nov 14 2026, 10:54 ET (orchestrator), before Part 2 is read.** What a pass leads to; no rule changes.
  - **The rule stands as written:** a pass makes "trades for the newest minute, the venue's candle afterwards" the
    proposal for the next release.
  - **One condition on that release, fixed now:** it must not place its bids later in the minute than release 3
    does. The fourth book's data step ends a median 13.4 s after the minute, against 10.3 s in the third book,
    because it asks for 18 coins' trades one after another. The paper books do not feel that, since they fill on
    whole-minute candles. The live bot would: by the timing study each second costs about one point of same-minute
    fills, and three seconds is more than the new way gains in bids (FORWARD_TESTS.md, the note of this date).
  - **What follows:** the release is built with the candle requests outside the critical seconds and the trades
    requests side by side, and that build runs as a paper book first, on a rule fixed before it starts.
  - **What was known when this was written:** Part 1's result of this morning, the interim look of Nov 12, and the
    books' step times from their heartbeats. No research has been fetched for Part 2's period.
- **Nov 15 2026, 02:26 ET (orchestrator), while the run for the addition is on the runner and before any of its
  output is read.** What a pass of the addition's rule leads to; the rule and its measures do not change.
  - **A point missed when the addition was written.** It compared a candle request right after the bids with the
    request at second 45 that is already built, and called the second fragile. Counted out, the later request is
    never worse for the next decision. A row is confirmed by an answer made 85 s or more after its minute began.
    - Request at second 45: an answer under 20 s old leaves one trades row at the next decision (way C); an
      answer 20 to 80 s old leaves two (C2); older, three.
    - Request right after the bids, at about second 15: an answer under 50 s old leaves two rows; older, three.
      It never leaves one.
  - **So the addition measures the floor of the built design, not a design of its own.** C2x18 is what the build
    at second 45 gives when every answer is a copy made at the start of the minute, and what a request right after
    the bids gives at best.
  - **What a pass leads to, restated:** two trades rows are acceptable, so the candle requests leave the step. The
    build with the request at second 45 goes to its paper test as it is (branch owner/release-4); the request
    right after the bids is not built.
  - **What a fail leads to, as written:** the candle requests stay ahead of the decision unless a paper book shows
    that the answers at second 45 are fresh often enough, on a rule fixed before that book starts.
  - **Runs:** the tool with the added pass is on branch owner/read-c2 (commit 891c38b8; 50 new offline checks,
    the 53 and 63 existing ones unchanged); runner job 43689717933, started 07:23 UTC.
  - **Also on record, from the engine's request and the collector's Nov 14 answers:** the venue's cache answers
    BTC's candle request with a copy in 96% of minutes, a median 65 s old, so BTC keeps two or three trades rows
    under any of these designs, the fourth book's included. BTC's trades bar equalled the final candle in 97.6% to
    99.4% of minutes in the third book's read, so this costs little.
- **Nov 16 2026, 12:04 ET (orchestrator), before the fifth book exists.** Part 3, measure 1: the fixed bar of
  10.3 s is replaced by a comparison on the same machine. Measures 2 to 4 are untouched.
  - **What was found today, before any run of the fifth book.**
    - The step's time moves with the period and with the runner by more than the difference being measured.
      Release 3's way ended its data step at a median of 10.26 s in the third book over Nov 11 to 14; since noon
      UTC on Nov 15 the same way is at 11.5 s in the main book and 11.1 s in the third (56 heartbeats each).
    - The build itself, 30 minutes each on two runners two hours apart today: 9.70 s and 11.37 s. On the same two
      runners the fourth book's way took 14.88 s and 15.35 s (jobs 43880261551 and 43898466756).
  - **Why the bar as written is wrong.** Taken from another period, 10.3 s would today fail release 3's own way.
    The condition of Nov 14 is "no later than release 3", and that can only be read with both on the same machine
    in the same hour.
  - **Measure 1 as it now stands. Both parts must hold.**
    - **(a) Same-machine pairs.** Every six hours of the period a runner job runs, on one machine and on the
      fifth book's pinned commit, 30 minutes of paper steps with release 3's inputs (`bot/spot/config.json` of
      `main`) and 30 minutes with the build's inputs, one straight after the other. The order alternates from job
      to job. A pair counts if both halves have at least 20 timed steps and neither met a refusal or a rate
      limit. The measure is the median, over the pairs that count, of the build's median data-step end minus
      release 3's. It must be at or below zero, with at least 8 pairs.
    - **(b) As written:** over the half hours in which both the fifth and the main book have a heartbeat, the
      median of the fifth book's values is no higher than the median of the main book's (at least 100 such half
      hours, and at least 100 heartbeats of the fifth book).
    - The fifth book's own median and the 10.3 s figure are reported, and decide nothing.
  - **Is this easier to pass?** It drops a bar that release 3 itself would not meet this week, and adds a direct
    test of the condition that the plan did not have. A build that is slower than release 3 on the same machine
    fails (a) whatever the week is like.
  - **Cost:** the pairs' paper steps place no orders and add about 40 public requests a minute from their own
    runner for an hour, four times a day.
- **Nov 16 2026, 13:36 ET (orchestrator), before the fifth book's first run.** Part 3: the pinned commit, two
  changes to the build made before it, and the points the plan left open, as the rule's code settles them.
  - **The commit:** `9e6f53b3aca8c15307f22a357f19431bff053e4c` on branch owner/release-5 (`main` at release 4
    with the input build merged in). The merged engine equals both sides' changes line for line.
  - **Two changes after the merge, both before the pin:**
    - the candle requests between steps make one try with a 4 s limit, and a request that gets no answer leaves
      the coin to the step. Before, a hanging request could hold the live bot's fast polls and the next step for
      about 83 s. The first form of this change also failed every answer without rows; the suite caught it (job
      43880224505: one coin of the simulation has no data in its window, so its valid empty answer was sent to the
      step every minute) and it was corrected before the pin: an empty answer is an answer;
    - a `candles_at_s` key outside trades mode is ignored with one warning at start. Before, the engine refused to
      start, which would have stopped a server switched back to candles by the emergency switch.
  - **Tests on that commit:**
    - the full offline suite, runner job 43898459890: 22 test files, none with a failure, 830 passing checks; the
      replay equals the research rung for rung;
    - on real market data, one runner, 30 minutes without the between-step requests and then 30 with them, each
      checked against the venue's candles (job 43898466756): the data step ended at a median of 15.35 s without
      them and 11.37 s with them; 540 requests between steps, none failed; 8 candle requests were made inside a
      step; none of 1,512 compared rows differs.
  - **The rule as code** (`scripts/owner/bar_source/part3_rule.py`, `scripts/owner/paper_status.py`,
    `scripts/owner/step_pairs/run_pair.py`; 110, 283 and 57 offline checks), with the points the plan left open:
    - the shares of measure 2 are taken as Part 2 took them: wrong-side bids over the bids that have a research
      score, level errors over the bids that have a research level, matched bids over the research's new bids that
      were not blocked. The 300-bid condition counts all new bids on the 17 coins;
    - measure 4's leaving out of the first step after a start: at most 18 in-step requests are left out for each
      start, from the half hour in which its first step falls;
    - the same-machine pairs of measure 1(a) run at 00:05, 06:05, 12:05 and 18:05 UTC (workflow `step-pairs`),
      on the commit the fifth book's own `CODE` file names. Both halves use the build's config file with only the
      input settings swapped (`trades_coins`, `trades_rows`, `candles_at_s`). A pair belongs to the period by the
      time its job started. Its medians are read to the hundredth of a second, as the tool prints them.
  - **Two points on the pairs, fixed before any pair exists:**
    - today's 18:05 pair could not run on schedule: at that time neither the workflow nor the book's `CODE` file
      existed. It is started by hand once the file exists, with the order that job would have had (the build
      first). No other pair is started by hand;
    - GitHub starts scheduled jobs late and sometimes drops them. If fewer than 8 pairs count among the jobs
      started in the period, the jobs go on at the same times after it, and part (a) is read on all pairs that
      count from the period's start up to the one that brings the count to 8. Part (b) and measures 2 to 4 are
      read on the period itself, and Part 3's verdict waits for part (a). This can delay the read; it cannot
      choose pairs. The rule script does exactly this and gives no verdict until 8 count.
  - **The first run is a short one** (40 minutes), so the counters can be looked at for a fault within the hour;
    the hand-over then starts the normal runs. Such a look can stop the test, cannot pass it, and changes no rule.
  - **The third book** is taken out of the main paper workflow in the same change; its last run ends by itself.
- **Nov 16 2026, 14:40 ET (orchestrator), after the fifth book's first heartbeat and before any read.** Part 3:
  what the corrected build would be if measure 4 fails alone, fixed now.
  - **Seen in an interim look** (LOG.md, 14:28): the venue's trades list is slow. In the fifth book's first 17
    steps a trades pass ran out of its 8 s budget often enough to send 10 of 306 coin-minutes (3.3%) to a candle
    request inside the step. The fourth book shows the same since Nov 14 (1.0%, 1.3%, 1.6% of coin-minutes a day,
    10.9% in the half hour to 19:00 UTC today). Measure 4 allows 2%.
  - **No rule changes.** This is not a fault in the plan's sense. The fifth book runs on and is read once, by
    the measures as written.
  - **What is fixed now is only the fail branch "on measure 4 alone".** That branch asks for a corrected build
    and a new three days. The cause is already visible without the fifth book's read: a trades pass that asks
    18 coins one after another. So the corrected build is being made now: the same build with the trades pass
    asked side by side (reports/owner/trades_workers_plan.md, fixed today before that code has run on live
    data). Its paper book, the sixth, starts as soon as its offline parts are clean, which may be before this
    plan's read.
  - **If Part 3 here fails on measure 4 alone and the sixth book's plan passes,** the sixth book's three days are
    the corrected build's three days. It is then read by this plan's measures 2 to 4 as written, computed for the
    sixth book (decisions against the fourth book's, items 1 to 5, the requests between steps). Measure 1 counts
    as met if the fifth book met it and the sixth book's pairs show three workers no later than one.
  - **In every other case nothing here applies:** a pass releases the build as it is; a fail on measure 1, 2 or 3
    follows the branches as written.
  - **Why this is not a second chance taken after the fact:** it is written before either book is read, it adds
    no measure and loosens none, and the sixth book has to pass its own plan as well.
- **Nov 16 2026, 15:21 ET (orchestrator), before the first pair has ended.** Part 3, the pairs: a weakness of the
  pair tool, and why the tool stays as it is.
  - The tool marks a half as rate-limited when the bare number 429 stands anywhere in that half's output outside
    the step table. A counter that happens to be 429 or a price of 429.5 would set the mark without any
    rate-limit answer.
  - Such a false mark can only take a pair out of the count. It cannot let one in and cannot move a median.
  - **The tool is not changed while the test runs. A pair it marks stays out,** also when the job's log shows
    that the mark is false. Each such case is logged with the line that set it. The rule of 13:36 (the pairs go
    on until 8 count) covers the loss.
- **Nov 16 2026, 15:32 ET (orchestrator), before any read; nothing new has been looked at since the first
  heartbeat.** Two corrections to my entry of 14:40.
  - **The figure.** I wrote that 10 of 306 coin-minutes (3.3%) needed a candle request inside a step. That divides
    by the 17 minutes the book had stepped. The rule divides by 18 coins times 30 minutes for each heartbeat, as
    fixed in the code before the book ran, so by the rule the first heartbeat reads 10 of 540 (1.9%). The two
    agree from the second heartbeat on. The rule's arithmetic stands.
  - **The branch.** I fixed the corrected build for a fail "on measure 4 alone". I had missed that item 1 of
    measure 3 (verified trades bars in at least 99% of coin-minutes) counts the same budget fallbacks: at the
    first heartbeat it reads 304 of 324 (93.8%). A slow trades pass therefore fails item 1 as well, and what I
    wrote at 14:40 would not have applied in the very case it was written for.
  - **The branch as it now stands:** if Part 3 fails on measure 4, on item 1 of measure 3, or on both, and on
    nothing else, the corrected build is the side-by-side build and the sixth book's three days count for it, on
    the terms written at 14:40 (it must pass its own plan, and it is read by this plan's measures 2 to 4 as
    written). A fail on anything else follows the branches as they were.
  - No measure is added, loosened or re-read. This only settles, before either read, which three days a
    corrected build may use.
- **Nov 17 2026, 08:20 ET (orchestrator).** Part 3, the pairs: how they are started.
  - **GitHub's clock is not keeping the schedule.** Of the three scheduled jobs so far, 00:05 UTC never started,
    06:05 started at 06:56, and 12:05 had not started at 13:18. Two pairs count: the one started by hand on Nov
    16 as logged, and the 06:56 one.
  - At that rate the eight pairs of measure 1(a) take about a week, and the release waits on a scheduler.
  - **From now on a pair is also started each time a run of the fifth book ends,** about every 5 h 50 min, by
    GitHub's event and not its clock. The scheduled times stay; a pair they start counts as before.
  - No one chooses when a pair runs, so this is not a start by hand, and the entry of Nov 16 13:36 ("no other
    pair is started by hand") stands. The order of the halves still follows the UTC hour of the start.
  - Nothing about what a pair measures or which pairs count changes. A pair still belongs to the period by the
    time its job started.
  - The pair tool, its test and the pair workflow stay byte for byte as they are. The starter is a separate
    small workflow.
- **Nov 17 2026, 14:21 ET (orchestrator).** Part 3, the pairs: the starter did not start anything.
  - **What happened:** the sixth book's run ended at 17:52 UTC and the fifth book's at 18:43 UTC. GitHub delivered
    no event for either: the starter workflow has no run at all, and the status report, which waits for the same
    event, did not run after them either. GitHub's own clock is worse than this morning: the status report's
    07:17 UTC job started at 16:54, and none of the pair or alternating jobs scheduled since 12:05 UTC has
    started.
  - **What does work** is a job starting another job directly. That is how each paper book starts its own next
    run, and it has not missed once.
  - **So the start moves into the hand-over.** When a run of the fifth book ends and its hand-over has started the
    next run, the same script also starts a pair. Same moment, same cadence (about every 5 h 50 min), still nobody
    choosing. The separate starter workflow is removed so that a late event cannot start a second pair.
  - The fifth book's workflow file, the pair workflow and the pair tool stay byte for byte as they are. The one
    file that changes is the hand-over script all paper books share; the addition runs only after the next run
    has been started and cannot change whether it is.
  - Nothing about what a pair measures or which pairs count changes. No pair is started by hand, including the
    two that were missed today.
- **Nov 18 2026, 08:26 ET (orchestrator), morning look, before the read. No rule changed.**
  - **Seen: the venue's trades list stood still for 38 minutes.** From 21:19 to 21:57 UTC on Nov 17 it showed no
    new trade for almost any coin. In the half hour to 22:00 the three books that read all 18 coins from trades
    each built 54 bars and found 486 minutes empty. The venue's candles kept coming.
  - **What the books did.**
    - The fifth book (and the sixth, the same build) had no row for the newest minute of any coin. The stale
      guard saw BTC without one and stopped new bids: 38 minutes, no new bid.
    - The fourth book and the main book ask for the candle inside the step, so they had rows and carried on:
      8 new bids each in the window, on the same coins in the same minutes, and two stopped minutes each
      (21:26 and 21:39).
  - **This is the build doing what it was built to do, and it is a weakness this plan did not foresee.**
    Release 3's way falls back on the candle by itself. The build asks for candles between steps only, so when
    the trades list stands still it has nothing for the newest minute.
  - **It is not a fault in the sense of "One read"** (no crash, refusal, rate-limit stop or error event). The test
    goes on and is read once, by its four measures, as written.
    - Item 1 does not see it: a minute found empty counts as verified.
    - Measure 2 does: the research's bids in those minutes have no bid of the fifth book next to them. Eight
      bids are 3.2% of the fourth book's 252 so far; the tolerance is 3.0 points on the whole period.
  - **The read will give the window by itself, next to the result and deciding nothing:** each book's new bids,
    the research's, and the fourth book's eight bids against the research.
  - **What follows, fixed now.** The repair is a fallback: when BTC has no trade in the newest minute, ask for
    BTC's candle inside the step; if it has a row for that minute, the trades list is behind, and the step takes
    every coin's newest row from candles asked inside the step, as release 3 does.
    - It is built unless the window speaks against it: if five or more of the fourth book's eight bids in the
      window are bids the research would not have placed, or are more than 5 bp from the research level, the
      candles were no better than nothing there and the stop stays as it is.
    - A fallback is a new commit. It gets its own offline test and its own paper days before any release.
  - **A pass of Part 3 still makes the tested configuration release 5, as written.** The release note will say
    what the build does when the trades list stands still.
  - **Also seen, counted by measures 3 and 4 as they are:** in the half hour to 08:00 UTC on Nov 18 a candle
    request between steps failed and the trades pass of the fifth and of the sixth book ran out of its budget
    for a whole pass (17 and 18 coin-minutes). Both asked for the candles inside the step; the data step
    ended at 22 s and 21 s that time.
  - **The third pair's release 3 half** (about 21:20 to 21:57 UTC) lay inside the standstill. The pair counts by
    the tool's rule and stays in. Its release 3 median, 9.78 s, is in line with the other pairs (9.49 to 9.74 s).
  - **Pairs so far: 6 of 8** (differences 2.69, 1.03, 1.18, 1.07, 1.27 and 1.20 s in the build's favour; five ran
    the build first, one release 3 first). Every ended run of the fifth book has started its pair since the
    hand-over does it.
- **Nov 19 2026, 18:27 ET (orchestrator), at the read, before any research is fetched.**
  - **The period:** 2026-11-16 19:00 to 2026-11-19 18:59 UTC, 4,320 minutes. The fifth book's first decision
    minute was 18:44 UTC on Nov 16, so the first half-hour mark after it is 19:00.
  - **New bids on the 17 coins, from the two logs alone,** on the 4,168 minutes in which both books decided: the
    fifth book 696, the fourth book 695. Both are over 300, so the period is not extended.
  - **Decision minutes in the period:** the fifth book 4,246, the fourth book 4,242.
  - **Pairs on `main` at this moment:** 15 result files; the rule script says which count.
  - **The read was planned for 15:40 ET and began at 18:27 ET.** A paper book puts its log on `main` only when a
    run ends, and the runs that cover the period's end ended at 23:10 and 23:18 UTC. Nothing was read in between.
- **Nov 19 2026, 20:33 ET (orchestrator). Part 3, second run: set in motion, before the corrected build has run.**
  - **The pin.** The fifth book's workflow names commit 815ea390 since 01:23 UTC on Nov 20 (`main` 99673d0d). The
    book's run on the old commit (44636491089) began at 23:18 UTC on Nov 19 and ends about 05:05 UTC; its
    hand-over starts the first run on the new commit.
  - **The rule as code** is on `main` since 01:40 UTC (65b2c584; scripts/owner/bar_source/part3b_rule.py, 99 checks;
    Sonnet agent, reviewed). part3_rule.py is unchanged. The read's first step is a tool as well now
    (scripts/owner/reconcile/count_bids.py, 21 checks); on the first run's period it gives the counts logged on
    Nov 19 (696 and 695 on 4,168 minutes).
  - **Run once on the first run's data, to prove the script:** it prints pass. Against the main book the fifth
    book has 48 wrong-side bids of 685 and the main book 47 of 669, on the 4,175 minutes both decided; on the five
    coins 3 of 166. This is no evidence for the build. The rule was written knowing that data; only the second
    run's days count.
  - **Pairs.** The pair that starts at the hand-over into the first run on the new commit still reads the old
    commit from the fifth book's record and is set aside by the rule. The first pair on the new commit starts at
    the hand-over after that, about 11:00 UTC on Nov 20.
  - **The read's steps** are in reports/owner/part3_infra_notes.md, "The second run's read".
