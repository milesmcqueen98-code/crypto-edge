# What a late BTC input costs: replay plan (Nov 10 2026, 14:00 ET)

Written by the orchestrator before any result of this replay exists. Branch owner/charter; the replay runs from branch
owner/late-btc.

## Why
- **The fault.** In a two-hour probe on Nov 10 2026 the bot's own request for BTC's newest candle returned an old
  cached copy in 125 of 125 minutes. The newest BTC minute in the answer was one minute behind in 70% of minutes and
  two or more behind in 30% (reports/owner/candle_probe/README.md). The bot fills a missing close forward and carries
  on, so every bid level and every BTC feature was computed from a late BTC.
- **The research used BTC's true close at every decision.** So the paper books, and any live bot, have run on an
  input the research never had. Release 2 fixes it. This replay prices it.
- **Nothing is chosen with this replay.** It changes no model, rule or parameter. It tells the owner and Miles how
  much of the research result the fault could have taken, and how urgent the fix is.

## Design (fixed now)
- **Harness:** the signal lab's pipeline (candles to features to R2-08's walk-forward models to candidates) and the
  frozen engine-faithful simulator that reproduces R2-08's best estimate at $250K (Sharpe 2.94 / 2.66 / 1.91 for
  selection / check / 2022-23).
- **Gate:** scenario S0 below must reproduce those three numbers before any other scenario is read. If it does not,
  the replay stops and the difference is reported.
- **The models are not retrained.** They stay as trained on true candles, as in the live bot. Only what the bot sees at
  decision time changes: BTC's closes as they enter the levels and the features. Fills, exits and P&L are computed on
  true prices.
- **Scenarios** (BTC only; every coin's own candles stay true):
  - S0: true BTC (the research).
  - S1: BTC's newest minute missing at every decision and filled forward, as the bot does (one minute late).
  - S2: the newest two minutes missing and filled forward (two minutes late).
  - S3: each decision minute draws S1 with probability 0.7 and S2 with probability 0.3, independently (the probe's
    mix); five seeds.
  - S4: S3, and in addition 30% of BTC's older minutes are missing and filled forward from the minute before, drawn
    once per seed (rows that stayed wrong after the bot's last look); five seeds.
- **Exactness check.** The vectorised late-BTC features are compared with the bot's own computation (the panel built
  on an array whose tail is filled forward) on at least 200 randomly drawn decision minutes per era. They must agree
  to floating-point tolerance before any scenario is read.

## Measures (per scenario and era, at $250K)
1. Sharpe as the repo measures it, yearly return, and the difference from S0.
2. Number of first-bid fills and rungs, mean net per dollar bought, worst day.
3. How the decisions moved: share of S0's first bids that are also armed in the scenario, share of the scenario's
   first bids that S0 did not have, and the median and 95th percentile of the absolute difference in bid level (bp).
4. A paired comparison by day against S0: mean daily difference and a bootstrap 90% interval.

## Reading (fixed now)
- The replay is descriptive. No pass or fail.
- The headline is S3 (the probe's mix), with S1 and S4 as the bracket.
- Reported to Miles as a range, with the limits below.

## Limits, stated now
- The probe measured one runner location for two hours. The paper books' own counters (release 2) will show how often
  their BTC answer is old; until then the mix is an assumption.
- A row that stayed wrong in the bot's table was often a partial candle, not a missing one. S4 models it as missing,
  which is a rough stand-in.
- ETH and the other coins also had late or unfinished candles of their own. That is not modelled here.
- The simulator's fills come from candles, as in the research.

## Deviation log
(none yet)
