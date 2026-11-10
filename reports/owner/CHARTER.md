# R2-08: how this algorithm is run (owner's charter, Nov 10 2026)

Miles handed the algorithm to Claude on Nov 10 2026: how it is built and structured is the owner's call, and the
goal is the best algorithm a Coinbase Advanced account can run. This file is the standing plan. The research record
is reports/crypto-edge-findings.md; every forward test is in FORWARD_TESTS.md beside this file.

## Objective
- **Maximise the Sharpe the account actually realises, out of sample,** at the size it runs, without giving up the
  kill switches. Research Sharpe matters only as a predictor of that.
- **Do not overfit.** A change that cannot be told from noise is not adopted on a backtest.

## Where the algorithm stands (re-scored at every review)
Scores are the owner's judgment of what has been verified, not a forecast. The open points say where the work is.

| Block | Weight | Before Nov 10 | Nov 10 2026 | What holds it back |
|---|---|---|---|---|
| Research evidence: out-of-sample Sharpe that held on unseen 2022-23 data | 25 | 17 | 17 | Best estimate at $250K is Sharpe 2.94 / 2.66 / 1.91 (selection / check / 2022-23, unverified costs doubled). It missed the deflated-Sharpe bar (0.77 against 0.95). Only time and live data add points |
| The live bot matches the research: inputs, timing, fills | 20 | 6 | 9 | Timing is measured and within a few percent. The newest candle is not final in about a third of decisions, and paper books its fills on that candle too. Probe running |
| Fills proven with real orders (capture share) | 20 | 3 | 3 | No live fill yet. Trade prints support the fill rule and the capacity. The pilot is the test |
| Costs and idle cash | 10 | 4 | 4 | Fees are assumed; idle cash earns nothing until the USDC check; the fee rebate is unverified |
| Controls and monitoring | 10 | 6 | 8 | Stops and the reconcile sweep were in place. Added: automatic paper status, an explained-error list, an update command that cannot start the bot |
| Forward data for new information | 10 | 0 | 5 | The collector is built and tested; it has to run for months before anything can be read |
| Process: plans before data, releases, records | 5 | 3 | 4 | Charter, registry, release notes and log exist. Two plans needed logged deviations on the first day |
| **Total** | **100** | **39** | **50** | |

## What is frozen
- **The model:** R2-08's label (net of realistic costs), its 23 features, the 60th-percentile threshold, a growing
  training window from 2024, quarterly retrains.
- **The ladder:** bids 4, 6 and 8 sigma under fair value in thirds, take-profit at 0.6 of the dislocation, market
  exit at 60 minutes, each signal sized at the smaller of 25% of capital and 0.2% of the coin's daily volume and split in thirds across
  the rungs, positions and
  resting bids within cash.
- **Every safety check in bot/spot:** the STOP file, the 8% daily loss limit, the 25% drawdown stop, good-til-date
  bids, the reconcile sweep.

## Why the search on history is closed
- Three rounds varied everything testable on the three eras: 4,691 ladder variants, 41 retrained models, and trade
  prints. In the two holdout eras the best candidates were ahead by +0.03 to +0.18 Sharpe.
- The pooled holdout difference has a standard error of about 0.16 Sharpe. A real gain of +0.1 to +0.2 cannot be
  told from luck there, and each further search on the same eras mostly finds luck.
- Both holdout eras have been read by thousands of trials. They are closed for choosing a model or a rule.

## Where realised Sharpe can still rise (ranked by size and certainty)

| Lever | Size | What it needs |
|---|---|---|
| Yield on idle cash (USDC rewards) | At the 3.50% on Coinbase's Coinbase One page (its USDC page shows 4.10%; the lower is used): about +1.5 points a year if only free cash earns, about +3.4 if cash held by resting bids earns too. Roughly +0.2 to +0.45 Sharpe at $250K, measured as the repo measures Sharpe (against zero). Against Treasury bills it removes a drag instead of adding an edge. The program may change on Jan 18 2027, when the OCC's rule on stablecoin rewards is reported to take effect. | Account eligibility (Miles), then the bot's USDC mode |
| Coinbase One fee rebate | Preferred ($29.99 a month) returns 25% of Advanced spot fees up to 100 USDC a month: about +$70 a month net, +0.3 points a year. Premium ($299.99) has no cap: at the two paper books' pace over their first 3.6 days (about $1,900 to $2,200 a month in fees at $250K) about +$190 to +$250 a month net, +0.9 to +1.2 points a year. Premium beats Preferred only above about $1,480 a month in fees. | Confirm on the account that API orders in the bot's portfolio earn the rebate (one month on Preferred shows it) |
| Capture share on live fills | 0.19 to 0.26 Sharpe between a share of 0.5 and 0.25 | The $10K pilot, then the $250K step |
| Live inputs: the newest candle is often not final when the bot decides | P&L effect unknown. In the collector's first hour 32% of newest candles changed after the decision and 6% were missing. The model was trained on final candles | Candle probe (reports/owner/candle_probe_prereg.md); if it passes, the newest bar built from trades, behind a switch |
| Live order timing | Measured on 14.1M trade prints (Nov 10). Every realistic timing is within a few percent of the research's zero-delay assumption in pooled P&L (+0.9% to -5.1%), and the study cannot rank them. The live timing fills 83-90% of the research's first bids in the same minute | Closed: timing stays as built. The pilot's rule B is read with these match rates |
| New information: open interest, funding, book depth | Unknown; none exists historically | The forward collector, then about a year of data |
| 15 seeds at each retrain | No change in expected Sharpe. Cuts the luck of one retrain's seeds from about 0.10 to about 0.06 Sharpe (scaled from the 0.13-0.15 measured for three seeds) | Next retrain |

## How a change gets in
Four classes, by what the change touches:

1. **Fidelity (the live bot differs from what the research assumed):** inputs the model was not trained on, bids that
   do not rest when the research assumed they did, bugs.
   - Adopt when the fix is verified to bring the live bot closer to the research assumption and the bot's regression
     tests pass. Measure the size when that is cheap. No backtest gain is required, because nothing about the model or
     the rules changes.
   - Anything that touches live orders or inputs still ships behind a switch, runs as a side-by-side paper book first,
     and goes out as a release.
   - This class never covers a change to the research assumption itself. That is class 3 or 4.
2. **Accounting (no prediction):** idle-cash yield, fees, ensemble size.
   - Adopt when the mechanism is verified on the live account and a no-harm check passes.
3. **Execution (a deliberate change in how orders are placed, beyond matching the research):** order sequencing,
   passive exits, queue tactics.
   - Measure first on prints or live fills, pre-registered. Build it only if it is worth 5% of P&L or more with the
     same sign in at least two eras, under a valuation that treats added and lost fills alike. Then run it behind a
     switch in the pilot before any wider use.
4. **Model and strategy (what to trade):** features, labels, thresholds, rungs, exits, universe.
   - Only with new information, or as a forward test registered before its data exists (FORWARD_TESTS.md).
   - Seed-average at least five seed triples per arm, read each challenger at R2-08's selectivity as well as its
     own, and have a separate agent audit for look-ahead before any holdout read.

For every class: the plan is written first, deviations are logged before the work they cover, and the result is
reported with a 100-point scorecard.

## Releases
- **`main` is production.** The paper books run from it, and the live bot takes it at the next `wickctl update`.
- **Nothing that changes a trading decision reaches `main` between release points.** Paper and live must run the
  same code, or the pilot's comparison means nothing. A release is a commit with a note to Miles saying what changed
  and why; he runs the update.
- **Data collection, monitoring and research code can reach `main` at any time.** They do not touch decisions.

## Retrains
- **Quarterly, at the start of each quarter,** on all candidates from 2024 to the last full day, with the same recipe
  (bot/train_v2.py). Next: Jan 1 2027.
- **From the next retrain: 15 seeds instead of 5.** The first signal lab showed the same expected Sharpe with less
  seed noise. It is a release, so it ships with a note.
- Never a rolling window: a one-year window cost about 1.0 Sharpe out of sample.

## Monitoring
- **reports/owner/PAPER_STATUS.md:** refreshed after every paper run. Fills, net per dollar, errors, and progress
  against forward rule A.
- **The forward collector** (scripts/forward, data on branch forward-data): minute-level book depth, the candles as
  the bot sees them at decision time, open interest and funding.
- **FORWARD_TESTS.md:** every open test, its read date and its pass rule.

## Stops (unchanged)
- STOP file; daily realised loss of 8%; marked drawdown of 25% from the peak.
- Standing rule: stop and review if the mean net per dollar bought is below 0 after 150 rungs.

## Who does what
- **Owner (Claude, orchestrating):** the plan, reviews, merges, releases, and every decision in this file.
- **Subagents (Opus or Sonnet by difficulty):** all building and running.
- **Miles:** actions only the account holder can take: eligibility checks, the pilot, `wickctl update`, capital.
