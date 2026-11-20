# What the candle's late cut gives the research on the twelve coins: replay plan (Nov 19 2026, 19:22 ET)

Written by the orchestrator before any trade print is fetched for it and before any result exists. Branch
owner/charter; the work runs from branch owner/late-cut (cut from owner/late-btc, which carries the replay harness).

## Why
- **Twelve of the 17 traded coins have candles that are not cut at the minute** (DOGE, LINK, BCH, SUI, XLM, HBAR,
  NEAR, AAVE, HYPE, ENA, PEPE, ONDO). After a quiet minute the venue's final candle often holds trades stamped in the
  first seconds of the next minute: in 8% to 41% of boundaries by coin in a six-hour live study, by a median of 7
  to 11 s (candle_clock_prereg.md, "Result"); in history, 7.8% of minute boundaries in candidate windows, median
  8 s (signal lab 2).
- **The research and the model's training rows are built on those candles.** Row t is meant to hold what is known
  at the end of minute t-1. For these coins it sometimes holds the first seconds of minute t as well.
- **A bot does not have that candle when it decides.** Release 3 gives the twelve the candle as first seen; the
  build tested in Part 3 of the bar-source plan gives them a trades bar cut at the minute. Either way about 8% of
  the paper books' new bids on the twelve are bids the research would not have placed, with scores a median 11
  points apart, against under 2% on the five coins whose candles are cut at the minute (bar_source_prereg.md,
  "Result of Part 3").
- **What it is worth is not known.** The paper reads compare decisions, not P&L, and three days hold two or three
  fills.
- **Two things could be true, and they call for different answers.**
  1. *The research is flattered.* Part of its result on the twelve comes from deciding with seconds that a bot
     acting on a bar cut at the minute does not use. Then the honest expectation for the live bot is lower than the
     research's.
  2. *The bot throws information away.* By the time it places its bids (8 to 12 s into the minute) the trades of
     those first seconds have happened and are in the trades list it has just read. It cuts them off on purpose. A
     bar that keeps them would be closer to what the model was trained on, and can be built.

## What has been seen before this plan
- The candle clock study and signal lab 2's clock figures (above).
- The paper reads, decisions only: the wrong-side shares above; fills side by side (Part 2: 37 fills in both the
  research and the fourth book, one in the book only, a ladder that lost $406, one in the research only; Part 3:
  two, none and one).
- The late-BTC replay, which priced a different input fault at about half a Sharpe point in two eras
  (reports/owner/late_btc/README.md). Its harness is used here.
- Nothing at the level of P&L for this gap, and no print fetched for it.

## Design (fixed now)
- **Harness:** the late-BTC replay's. The signal lab's pipeline (candles to features to R2-08's walk-forward models
  and candidates) and the frozen engine-faithful simulator at the best estimate's configuration, $250K. Eras:
  selection (Jan 2025 to Mar 2026), check (Apr to Nov 2026), 2022-23.
- **Gate:** scenario S0 below reproduces R2-08 exactly (Sharpe 2.94 / 2.66 / 1.91, the same trades at the same
  prices). If it does not, the replay stops and the difference is reported.
- **The models are not retrained.** Fills, exits, costs and prices are the research's (candles). One thing changes:
  at a candidate minute t of coin c, the newest row (minute t-1) of coin c that the decision reads. Its close and its
  volume come from trade prints, cut as the scenario says. Every other row, coin and minute is the research's.
- **Candidate minutes:** as the harness finds them (the first bid's level touched by the minute's low). All of
  them, for all 17 coins, in the three eras. A decision moves P&L only there.
- **Trade prints:** the venue's public trades for coin c stamped from the start of minute t-1 to 15 s after the
  start of minute t, fetched on runners with the timing study's tools (windows merged, the same pacing). A refusal
  or a rate-limit answer stops all fetching: no retry and no way around it. Raw prints are never committed; one
  derived row per candidate is.
- **Scenarios** (row t-1 of coin c at its candidate minutes):
  - **S0:** the venue's candle. This is the research.
  - **M0:** the prints stamped inside minute t-1. Close: the last print's price. Volume: the sum of their sizes.
    No print: no row, so the close is carried forward and the volume is 0, as the engine does. This is the build
    of Part 3 and, nearly, release 3.
  - **M5, M10:** the prints stamped from the start of minute t-1 to 5 s and to 10 s after its end. A bot whose bids
    rest from 8 to 12 s into the minute can have these.
  - **Q5, Q10:** as M5 and M10 when minute t-1 holds five prints or fewer, and as M0 otherwise. The venue's late
    cut follows quiet minutes; these stand for a bar that is late only then.
- **Placebo:** the five coins (ETH, SOL, XRP, LTC, ZEC), whose candles are cut at the minute or nearly so. M0 should
  leave their decisions almost untouched.
- **Exactness check:** for at least 200 randomly drawn candidates per era, the changed level, sigma and features
  equal the unmodified edge.wick.panel run on the bot's own arrays with that one row replaced, to floating-point
  tolerance, before any scenario is read.

## Measures (per scenario and era; the twelve and the five apart and together)
1. **Decisions at candidate minutes:** armed in S0, armed in the scenario, in both, in S0 only (fills the scenario
   drops), in the scenario only (fills it adds); the median and the 90th percentile of the absolute score
   difference.
   Also how often the replaced row differs from the candle at all: the close, and the volume by more
   than 1%.
2. **What the moved fills were worth:** mean net per dollar bought of the fills dropped, added and kept.
3. **The book:** Sharpe as the repo measures it, yearly return, first-bid fills, worst day; the difference from S0.
4. **Paired by day:** the scenario minus S0, and M5, M10, Q5, Q10 minus M0: mean daily difference in bp of capital
   with a bootstrap 90% interval, per era and pooled.
5. **The venue's cut, descriptive:** for each candidate boundary of the twelve with a print in the first 15 s of
   minute t, whether the venue's candle of minute t-1 holds it (the candle's close and volume against the print
   bars cut at each second from 0 to 15), by the number of prints in minute t-1. It is the table a rule for the
   venue's cut could be learned from. Nothing is fitted to it here.

## Reading (fixed now)
- **Order:** gate, exactness, placebo, then the rest. For (c) the selection era is read first and the choice is
  written into the deviation log before the other two eras' numbers for those scenarios are looked at.
- **(a) Placebo.** If on the five M0 changes arming at more than 3% of their candidates in any era, the tool or
  the premise is wrong: the result is reported and nothing below is concluded.
- **(b) Is the research flattered?**
  - *Yes* if S0 minus M0 is at least 0.20 Sharpe, the same sign, in at least two of the three eras, or the pooled
    paired daily difference of M0 against S0 has a 90% interval wholly below zero.
  - *No* if S0 minus M0 is under 0.10 Sharpe in size in every era and the pooled interval includes zero.
  - Otherwise *not settled*.
- **(c) Does a late bar help?** Of M5, M10, Q5 and Q10, the one with the fewest changed decisions against S0 in
  the selection era (S0 only plus scenario only, on the twelve) is named. It helps if, in each of the other two
  eras, its changed decisions are at most half of M0's, and the pooled paired daily difference against M0 over
  those two eras is not wholly below zero at 90%.
- **What follows.**
  - *Flattered, and a late bar helps:* the bar is built into the engine as an option for the twelve, with its own
    offline tests and a paper test on a rule fixed first. Forward expectations for the twelve are quoted from that
    scenario.
  - *Flattered, and no late bar helps:* forward expectations are quoted from M0, and the Jan 1 2027 retrain is
    planned on bars cut at the minute for the twelve (its own plan; it needs the trade tape for the training
    window).
  - *Not flattered:* the gap is a known difference in decisions with no price. The row in FORWARD_TESTS.md is
    closed, and if a late bar helps by (c) it may still be built for agreement's sake, at low priority.
  - *Not settled:* reported as that. The paper books' fills against the research stay the forward measure and the
    row stays open.
- No model, threshold or parameter is chosen with this replay.

## Limits, stated now
- **One row only.** In a real book the other thin coins' newest rows are cut the same way and move the two
  cross-coin inputs (alts_mean_z60, alts_below_2sd). Not modelled: the paper books measure the whole, this replay
  the coin's own row.
- **Candidate minutes only.** Elsewhere the every-minute panel is the research's.
- **Fills come from candles,** as in the research. For the twelve the candle's low can hold the first seconds of
  the next minute too. The timing study priced when a bid rests; this replay does not.
- **Each era is one price path,** and a changed decision reshuffles which dips fill. The paired intervals show
  that noise; a difference under about 0.2 Sharpe in one era means little.
- **The prints and the candles keep slightly different records** (signal lab 2: 0.9% to 1.7% of minutes have prints
  and no candle; about 5% of minutes have a candle that leaves trades out). Where that makes M0 differ from S0 on
  the five, the placebo shows it.
- **A late bar's volume can count some prints twice:** the first seconds of minute t-1, when the venue put them
  into the candle of minute t-2. The close is not touched by this.
- **Five scenarios besides S0.** No significance is claimed for a single one; the rules above are the reading.

## Deviation log
(Each entry is written before the work it covers.)
- **Nov 19 2026, 19:26 ET (orchestrator), before any print is fetched and before the agent starts.**
  - **Who does what.** An Opus agent runs the whole replay on branch owner/late-cut from a written brief. It logs
    its own readings of open details below, on that branch, each before the work it covers; I bring them to `main`
    with the result.
  - **A tie in (c)** goes to the shorter bar, then to the Q form.
  - **Part B is not computed early.** M5, M10, Q5 and Q10 for the check era and for 2022-23 are run only after the
    commit that names the late bar from the selection era is pushed. Until then those numbers do not exist.
- **Nov 19 2026, 19:33 ET (agent), before any code of this replay is run and before any print is fetched.**
  Readings of details the plan leaves open. Code: scripts/owner/late_cut/; outputs: reports/owner/late_cut/.
  - **Harness.** scripts/owner/late_btc/replay.py's Research, gate, simulator configuration (S_0.5, $250K), eras and
    summary measures, copied into scripts/owner/late_cut/replay.py (late_btc's files are not changed). R2-08's models
    are fitted as there (core.walk_forward's code path, boosters kept).
  - **Candidate minutes.** S0's candidates as the harness finds them: the level set's candidate minutes in the test
    period (open above the posted level, low at or below the level minus one tick, row above 1500), all 17 coins.
    The era of a candidate is the era whose dates hold its minute t.
  - **What the scenario changes at a candidate (c, t).** Coin c's row t-1 gets the bar's close and volume. From it
    the level, sigma, 7-day beta and the 23 features of coin c at t are rebuilt; the model scores them (mean of the
    quarter's three boosters); the trade, if any, carries the scenario's level and sigma (the take-profit target and
    the rungs follow sigma), as the late-BTC harness passes them. The every-minute armed panel takes the scenario's
    prediction at these minutes and S0's everywhere else. Other coins' rows and decisions are S0's.
  - **A candidate whose changed level is no longer touched.** The harness's fill rule is applied again with the
    scenario's posted (tick-rounded) level against the true open and low. If it fails, the minute is not a candidate
    in the scenario: no first bid fills there. Minutes that are not S0 candidates are never added (their rows are not
    rebuilt). In measure 1 a scenario decision is "armed" only if the minute is still a candidate and the prediction
    is above the quarter's threshold; S0's "armed" is the prediction above the threshold (core.simulate's keep, float64).
    The counts of candidates no longer touched, and of arming by the prediction alone, are reported beside it.
    Readings (a) and (c) count changed decisions with this "armed".
  - **Score difference.** |scenario prediction - S0 prediction| in the model's own units (predicted net, bp), over all
    candidates of the group.
  - **The print cut.** A print's time is the venue's stamp (UTC, microseconds). Minute t-1 is [start of t-1, start of
    t): start included, end excluded. The bar of second s (0 to 15) holds the prints with start of t-1 <= time <
    start of t + s seconds. The window fetched is [start of t-1, start of t + 15 s), the fetcher keeping start <= time
    < end. M0 is s = 0, M5 is s = 5, M10 is s = 10.
  - **The close when prints share the last stamp.** Prints are de-duplicated by trade id and ordered by (time, trade
    id); the close is the price of the last one (the highest trade id among those with the latest stamp).
  - **Volume unit.** The candle's volume and a print's size are both in the coin's base units; the bar's volume is the
    sum of sizes, compared with the candle's volume without conversion.
  - **No print in the bar.** No row: the close is the research's close of minute t-1 as the bot would fill it, that is
    the research's close of t-2 carried forward (NaN if that carry would pass the 30-minute fill limit), and the
    volume is 0.
  - **Q5, Q10.** "Minute t-1 holds five prints or fewer" = at most 5 prints in [start of t-1, start of t), zero
    included; then the bar of s = 5 (Q5) or s = 10 (Q10), else the bar of s = 0.
  - **A candidate whose window is not complete** (status other than complete: capped, history_start, failed,
    not_run) keeps S0's row in every scenario. Their number is reported by coin and era.
  - **Measure 1, "differs from the candle".** Close: the bar's close not equal to the candle's close of t-1 as the
    research holds it (cf). Volume: |bar volume / candle volume - 1| > 1%, and any bar volume above 0 where the candle
    volume is 0.
  - **Measure 2.** Fills = first-bid fills (k = 4, filled) of the replay's minute bound, keyed (minute, coin): dropped =
    S0 only, added = scenario only, kept = both. Net per dollar = blended print-priced P&L of the parent's tranches
    (first bid and its rungs) over blended dollars filled, both bounds blended as fsim.lat_share; dropped priced in
    S0's book, added in the scenario's, kept in both.
  - **Measure 3** as the late-BTC replay: fsim.stats Sharpe and yearly return of the blended print-priced daily
    series, first-bid fills of the minute bound, worst day.
  - **Measure 4, bootstrap.** The late-BTC replay's: daily difference of the blended print-priced returns; stationary
    bootstrap of the mean, mean block 7 days, 5,000 draws, numpy default_rng(11), 90% interval.
  - **Measure 4, pooled.** The mean over all days of the eras pooled (each day weighted once). Each bootstrap draw
    resamples each era's series on its own (stationary, mean block 7, eras in the order sel, chk, early from the one
    default_rng(11) stream) and takes the mean of all drawn days; 5,000 draws; 90% interval. For (c) the same over
    chk and early only.
  - **Measure 5.** For each candidate of the twelve with at least one print in [start of t, start of t + 15 s): for
    s = 0 to 15, whether the candle of t-1 equals the bar of s (close equal, volume within 1e-6 relative). Tabled by
    the number of prints in minute t-1 (0, 1, 2-5, 6-20, over 20) and era: the share equal at each s, and the share
    equal at no s.
  - **Each scenario-era is built on its own.** A scenario changes only the candidates of one era and is priced in that
    era only (so the selection-era build of M5, M10, Q5, Q10 holds no number of the other eras). S0 is one build per
    base, as in the harness.
  - **Exactness check.** For each era and each bar s = 0, 5, 10 that a job prices: 200 candidates drawn without
    replacement (numpy default_rng(7)) among the era's candidates whose bar differs from the candle's row (close or
    volume not equal). At each, late-BTC's bot_arrays (11 days, close filled forward with limit 30, volume 0 when
    missing) with coin c's row t-1 replaced by the bar (volume 0 = no row, filled forward), and the unmodified
    edge.wick.panel (wbeta 7 days, as late-BTC's check). Compared: level (before tick rounding), sigma and the 23
    features of coin c at t. Fail as late-BTC: a NaN mismatch, or absolute difference above 1e-9 and relative above
    1e-6. Q5 and Q10 take the same per-bar values (selection tested offline). A failure stops the job before any
    scenario other than S0 is priced.
  - **The fetcher and the venue.** scripts/owner/timing/prints_runner.py's strict_get and fetch are imported and used
    unchanged (pacing 7 per second; HTTP 401, 403, 451 or a non-JSON reply raise at once; a 429 is retried by the
    fetcher's own rule and 10 of them in a row raise; a raise stops the shard). Every 429 answer is also counted
    (bookkeeping only, through the session, no change of behaviour) and reported. If any shard reports a refusal
    or a 429, no further fetch is started.
  - **Windows and shards.** One window per candidate, [start of t-1, start of t + 15 s), merged per product as
    windows.py merges (overlapping or touching); 8 shards balanced on windows.py's cost model with estimated prints =
    (candle dollars of minute t-1 + a quarter of minute t's) / 874.
  - **Reading (b), "the same sign".** Yes needs S0 - M0 >= +0.20 Sharpe in at least two eras (the research ahead),
    or the pooled interval of M0 - S0 wholly below zero. Sharpe unrounded.
