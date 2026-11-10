# R2-08: how this algorithm is run (owner's charter, Nov 10 2026)

Miles handed the algorithm to Claude on Nov 10 2026: how it is built and structured is the owner's call, and the
goal is the best algorithm a Coinbase Advanced account can run. This file is the standing plan. The research record
is reports/crypto-edge-findings.md; every forward test is in FORWARD_TESTS.md beside this file.

## Objective
- **Maximise the Sharpe the account actually realises, out of sample,** at the size it runs, without giving up the
  kill switches. Research Sharpe matters only as a predictor of that.
- **Do not overfit.** A change that cannot be told from noise is not adopted on a backtest.

## What is frozen
- **The model:** R2-08's label (net of realistic costs), its 23 features, the 60th-percentile threshold, a growing
  training window from 2024, quarterly retrains.
- **The ladder:** bids 4, 6 and 8 sigma under fair value in thirds, take-profit at 0.6 of the dislocation, market
  exit at 60 minutes, 25% of capital per signal, each rung capped at 0.2% of the coin's daily volume, positions and
  resting bids within cash.
- **Every safety check in bot/spot:** the STOP file, the 8% daily loss limit, the 25% drawdown stop, good-til-date
  bids, the reconcile sweep.

## Why the search on history is closed
- Three rounds varied everything testable on the three eras: 4,691 ladder variants, 41 retrained models, and trade
  prints. The best candidates landed at +0.03 to +0.17 Sharpe out of sample.
- The pooled holdout difference has a standard error of about 0.16 Sharpe. A real gain of +0.1 to +0.2 cannot be
  told from luck there, and each further search on the same eras mostly finds luck.
- Both holdout eras have been read by thousands of trials. They are closed for choosing a model or a rule.

## Where realised Sharpe can still rise (ranked by size and certainty)

| Lever | Size | What it needs |
|---|---|---|
| Yield on idle cash (USDC rewards) | At the 3.50% on Coinbase's own page: about +1.5 points a year if only free cash earns, about +3.4 if cash held by resting bids earns too. Roughly +0.2 to +0.45 Sharpe at $250K. | Account eligibility (Miles), then the bot's USDC mode |
| Capture share on live fills | 0.19 to 0.26 Sharpe between a share of 0.5 and 0.25 | The $10K pilot, then the $250K step |
| Live order timing | Unknown until measured (timing study, Nov 10) | Trade prints now; the pilot later |
| New information: open interest, funding, book depth | Unknown; none exists historically | The forward collector, then about a year of data |
| 15 seeds at each retrain | No change in expected Sharpe. Cuts the luck of one retrain's seeds from about 0.10 to about 0.06 Sharpe (scaled from the 0.13-0.15 measured for three seeds) | Next retrain |

## How a change gets in
Three classes, by what the change touches:

1. **Accounting (no prediction):** idle-cash yield, fees, ensemble size.
   - Adopt when the mechanism is verified on the live account and a no-harm check passes.
2. **Execution (how orders are placed, not which signals):** re-pricing speed, order sequencing, fill detection.
   - Measure first on prints or live fills, pre-registered. Build it only if it is worth 5% of P&L or more with the
     same sign in at least two eras. Then run it behind a switch in the pilot before any wider use.
3. **Model and strategy (what to trade):** features, labels, thresholds, rungs, exits, universe.
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
