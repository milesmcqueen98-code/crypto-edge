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
