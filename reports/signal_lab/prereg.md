# Signal lab: what R2-08's model is taught and shown — pre-registration (Nov 9 2026)

Written before any candidate of this lab was run. Branch signal-lab, cut from explore/v1-ef (55f9802).
Code: scripts/signal_lab/. Results: reports/signal_lab/. Time box: ends 5 pm ET, Nov 9.

## Goal
Raise R2-08's out-of-sample Sharpe at $250K by changing what the AI model knows: its label, its features and new
US-accessible data. Nothing else changes:
- the ladder (4 / 6 / 8 sigma in thirds, take-profit 0.6, market exit at 60 minutes, 0.2% ADV cap);
- the model class and settings (LightGBM, quarterly walk-forward, 60th-percentile threshold, 3 seeds).

"No change" is a valid result.

## Why these candidates
- **The label teaches the wrong economics.**
  - R2-08 learns the net of one 4-sigma trade at perp per-contract costs. There, ETH, LTC and BCH cost 7.5-9 bp a side.
  - The bot trades a spot ladder: flat spot fees, and more than half its profit from the 6- and 8-sigma rungs.
- **Features: who is forced to sell.** Cascade state, where the coin sits in its range and trend, and the market's own
  fear gauge (implied volatility).

## Known priors, disclosed
- The extra candle features (F1-F3 below) were about neutral under the perp label in the wick v2 lab.
- The AI's prediction ranks risk along with return (sizing lab; ladder v6 sizing).
- Stricter thresholds failed out of sample (explore v1). Hyperparameter changes were neutral (wick v2).
- **The eras are not fresh.** R2-08 was chosen with the check era in view, and 2022-23 has been read by several rounds.
  So the holdout here is "read once for these candidates", not unseen data.

## Candidates: 4 labels x 5 feature sets = 20 specs (19 trials + the incumbent)

| Label | What the model predicts |
|---|---|
| R | R2-08's: one 4-sigma trade, perp per-contract costs |
| S4 | The same trade at the spot bot's costs: maker 6 bp in; take-profit maker 6 bp, else taker 12.5 bp + 2 bp half-spread |
| LD | The spot ladder's net per dollar of the whole signal: 4 / 6 / 8-sigma rungs in thirds, each with its own take-profit, else sold at minute 60. An unfilled rung earns 0 |
| LS | LD in units of the signal's sigma (a Sharpe-like target) |

| Feature set | Added to R2-08's 23 features |
|---|---|
| F0 | nothing |
| F1 | cascade state: 5-minute sell volume (coin, BTC), close location, other coins filling in the last 5 minutes, minutes since the last fill episode, episodes in 24 hours |
| F2 | position and regime: distance from the 7-day high and 3-day low, place in the 1-day range, 15- and 60-minute returns, BTC from its 1-day high, BTC vs its 100-day average, BTC 30-day return |
| F3 | F1 + F2 + calendar (hour of week, minutes to midnight UTC, US session) |
| F4 | new data: Deribit BTC implied volatility (DVOL) and its 24-hour change, DVOL minus 1-day realized volatility, VIX, Nasdaq-futures 1- and 5-day returns |

- RF0 is the incumbent. It must reproduce R2-08's trade list and frozen-simulator daily series exactly.
- Every feature uses data through minute t-1 only. DVOL bars are usable one hour after they open; daily bars from the
  next UTC day.
- **F4's live source is unverified.** DVOL comes from Deribit's public API; a winner using it needs that check before a
  paper book.

**Not tested, and why:**
- Coinbase perp basis and funding: history starts Jul 2025, so 2022-23 cannot be read.
- Binance funding and open interest: not usable live from the US.
- Liquidations and order books: no history.
- Model settings: neutral in wick v2.

## Development (Jan 2025 - Mar 2026 only)
- The walk-forward stops at 2026Q1, so no holdout prediction exists during development.
- **Screen:** each spec's trade list goes through the frozen simulator (fsim.book) at S*: today's volumes, unverified
  costs doubled, theta 0.5, $250K, 1-second blend. The statistic is Sharpe against the incumbent's.
- Every spec that runs is logged in screen.csv and counts toward N. No other spec runs without a deviation entry made
  first.
- **Overfitting checks (information):**
  - Hansen's SPA and Romano-Wolf StepM against the incumbent, on the vol-matched daily difference (stationary
    bootstrap, mean block 7 days, 2,000 draws);
  - deflated Sharpe of the improvement, with N = 19 and with N = 19 + 9,700 earlier setups.

## Finalists (frozen before any holdout number exists), at most 2
1. **Best:** the highest screen Sharpe of the 19.
2. **Best label-only:** the highest screen Sharpe among S4F0, LDF0 and LSF0, if different. It needs no new live
   feature.

A finalist must beat the incumbent on the screen. If none does, the lab ends with "no change" and the holdout stays
unread.

## Binding test: the engine-faithful simulator, all three eras
- **Simulator:** ladder v6's frozen replay (resting bids hold cash; 1-second blend).
- **Dataset:** each finalist gets its own, built by the code path that built R2-08's: trade list, tranche precompute,
  the every-minute armed panel and deep paths.
- **Exit costs:** print-measured costs exist only for R2-08's own fills.
  - Primary: both books' market exits priced by the model (the same rule for both).
  - Information: the print-priced version, which favours R2-08 (a challenger's new fills fall back to the model).
- **Volumes:** "today's volumes" uses R2-08's per-coin factors for every book.
- **Configurations:** S* theta 0.5 at $250K (primary), theta 0.25, $1M, and research volumes at 1x costs.

## Pass (all required; primary configuration unless stated)
1. ΔSharpe >= +0.20 in each era (selection, check, 2022-23).
2. ΔSharpe >= 0 in each era at theta 0.25, at $1M, and at research volumes.
3. Daily max drawdown and worst day no worse than 1.1x R2-08's in each era.
4. No losing calendar year.
5. Pooled holdout (check + 2022-23) vol-matched daily difference: one-sided stationary-bootstrap p <= 0.05 (mean block 7
   days), Holm-adjusted across the finalists.

**Verdicts:** a winner gets a new paper book (nothing goes live). Everything else is rejected or kept as a forward lead.

## Scorecard (100 points, fixed now; engine-faithful cells, model-priced exits)

| Criterion | Points | Formula |
|---|---|---|
| Sharpe gain | 25 | 25 x clip(mean ΔSharpe over check and 2022-23 / 0.40, 0, 1) |
| Capacity | 10 | 10 x clip(mean $1M ΔSharpe over check and 2022-23 / 0.40, 0, 1) |
| Consistency | 15 | 15 x share of the 12 cells (3 eras x 4 configurations) with ΔSharpe > 0 |
| Evidence | 15 | 15 x clip((0.20 - Holm p) / 0.15, 0, 1) |
| Spread | 10 | 10 x clip((1 - top-5-day share of the pooled holdout gain) / 0.5, 0, 1); 0 if the pooled gain is <= 0 |
| Risk | 10 | 8 x share of the 6 risk checks passed (2 measures x 3 eras) + 2 if no losing year |
| Mechanism | 10 | hand-scored at the freeze |
| Implementation | 5 | hand-scored at the freeze |

## Deviation log
1. **Round 2 and a third finalist rule (Nov 9 2026, 14:42 ET).** Written while round 1 was running, after seeing 8 of
   its 20 results (RF0-RF4, S4F0-S4F2), and before any round-2 spec ran.
   - **F5, outcome memory** (4 features): the mean and count of all coins' candidate-trade outcomes that became known
     in the last 24 hours; the coin's latest known outcome and its age.
     - Mechanism: liquidity providers' capital is slow to return after losses, so the rebound premium is higher after
       failed rebounds. Edge hunt 2 saw this on its development data (the next ladder after a failure earned more).
     - An outcome is used only once it is known: a fill at minute q is used from minute q + 61.
     - Trials: RF5 and LDF5.
   - **H, more history** (main era only): the 2021-23 candidates are added to every training set. The main-era models
     otherwise learn from 2024 on.
     - Mechanism: the binding limit is the number of independent forced-selling episodes, not the feature count.
     - It cannot be judged in 2022-23 (no earlier data), so it cannot pass gate 1. It is a side family: its best spec is
       read on selection and check as information only.
     - Trials: RF0H, S4F0H, LDF0H and LSF0H.
   - **Third finalist, "Main effects":** the label with the highest mean screen Sharpe across F0-F4, with the feature set
     with the highest mean across the four labels (round-1 grid). Added because the single best cell of a noisy grid
     overfits (explore v1). Included if different from finalists 1 and 2.
   - "Best" is now the highest screen Sharpe among all non-H trials of rounds 1-2 (21 trials). N = 25 with the H specs.
   - **Not run:** a Bitstamp-Coinbase premium feature. The Bitstamp history starts in 2024, so 2022-23 could not be read.
2. **Round 3 and the final finalist rules (Nov 9 2026, 14:48 ET).** Written after rounds 1-2 (25 trials, selection era
   only) and before round 3 or any holdout number.
   - **What rounds 1-2 showed** (screen ΔSharpe against the incumbent's 2.363):
     - Labels, base features: S4 -0.11, LD -0.27, LS -1.89. The label mismatch is not a handicap on this era.
     - Feature sets, R label: F1 +0.02, F2 +0.68, F3 -0.01, F4 +0.26, F5 -0.10. F2 is the best set under all four labels.
     - More history (H) helped under every label: R +0.39, S4 +0.54, LD +0.28, LS +0.36 against the same spec without it.
   - **Round 3 (3 trials):** RF2H, S4F2H and RF4H, the two best labels under H with the best feature set, and the
     new-data set with H. N = 28.
   - **How an H spec is judged in 2022-23:** no earlier history exists there, so the spec runs without H in that era.
     A spec that is only H (RF0H, S4F0H) equals its non-H twin there, so it cannot gain in 2022-23.
   - **Finalists (frozen at the next commit, before any holdout number):**
     1. **Best:** the highest screen Sharpe among the non-H trials (unchanged rule).
     2. **Best label-only:** none. No label-only spec beat the incumbent on the screen.
     3. **Main effects:** R with F2, the same spec as Best on the round-1 grid.
     4. **New data:** RF4, the single-change test of the new data (DVOL, VIX, Nasdaq futures). LDF4 scored 0.006 higher
        on the screen; RF4 is chosen because it changes one thing.
     5. **Best with history:** the highest screen Sharpe among all H trials (rounds 2-3). Read in all three eras under
        the rule above.
     6. **History only:** RF0H, the single-change test of more history. Information only; it cannot pass gate 1.
   - Holm runs across the finalists that can pass (1, 4 and 5).
   - **Failed on development, and why:**
     - S4 and LD: R2-08's per-contract costs were not the handicap. The ladder payoff adds heavy-tailed noise to the
       target.
     - LS: dividing by sigma down-weights the high-sigma signals, where the profit is.
     - F5: outcome memory added nothing beyond the existing return and volatility features.
3. **Freeze (Nov 9 2026, 14:51 ET), before any holdout number.** 28 trials ran on the selection era.
   - **Round 3:** RF2H 3.188 (+0.82), S4F2H 3.076 (+0.71), RF4H 2.518 (+0.16).
   - **Finalists** (finalists.json, with hand scores and reasons): RF2, RF4, RF2H; RF0H as information only.
   - **Selection-era statistics** (screen_stats.txt):
     - SPA p 0.14 against the incumbent; StepM: 0 of 28 significantly better.
     - Deflated Sharpe of the improvement: at most 0.33 with N = 28, and about 0 with the 9,700 earlier setups.
     - So nothing is significant in-sample once the trials are counted. The holdout decides. Explore v1 found the
       same sign (SPA p 0.067) and no gain held.
   - **Expectation, recorded before the read:** most or all of the screen gains will not hold. If anything holds, more
     history is the likeliest, because it adds no new degrees of freedom.
   - **Screen vs binding simulator:** the screen used the frozen simulator. The engine-faithful selection-era cells are
     reported with the holdout cells; they do not change the list.
4. **Information runs on the amount of history (Nov 9 2026, 15:30 ET).** Logged while the binding cells were being
   computed. Seen so far: RF2 and RF4 (selection, check), RF2H (selection, check, primary configuration) and RF2
   (2022-23). Not yet seen: any RF0H cell.
   - **Why:** RF2H beat RF2 in the check era by 0.75 Sharpe, and the only difference is the added history. If more
     history helps for the stated reason, Sharpe should rise with the amount of history.
   - **Dose-response** (frozen simulator, S*): R2-08's model with a rolling 365-day window (RF0W365), with 2023 added
     (RF0H23) and with 2022-23 added (RF0H22). RF0 and RF0H are the other two doses.
   - **Replication where R2-08 already uses all the history there is:** RF0W365 in 2022-23.
   - **Seed noise:** RF0, RF2 and RF0H refit with four other seed triples on the selection era.
   - These runs select nothing and cannot become candidates. They read the check era and 2022-23 on the frozen
     simulator for non-candidates, as information. The three new specs count toward N (31).
5. **After the read (Nov 9 2026, 15:44 ET): seed robustness of the history result, and a pipeline difference found.**
   - **The read is done** (holdout.txt). No finalist passed. RF2H was positive in all 12 cells but below +0.20 in both
     holdout eras; RF0H was +0.12 in the check era.
   - **Seed robustness (information):** RF0 and RF0H refit with five seed triples over the whole walk-forward, on the
     frozen simulator, selection and check. Logged before it ran. It asks whether the history gain is larger than the
     noise from the model's random seeds. It selects nothing.
   - **Pipeline difference in 2022-23:** R2-08 rebuilt through this lab's pipeline equals the frozen book through
     2023Q1 and differs slightly from 2023Q2.
     - Cause: two candidate rows (BCH and XLM, Mar 4 2023) have no label. The lab drops them from training; the
       original pipeline kept them.
     - Size: 12 of about 750 trades differ; engine-faithful Sharpe 1.645 against the frozen 1.684.
     - The registered comparison stays against the frozen R2-08. Like for like, RF2's 2022-23 gain is +0.21, not
       +0.17. No verdict depends on it.
6. **Round 4, the arming threshold (Nov 9 2026, 15:48 ET).** Logged before any round-4 spec ran.
   - **Results since deviation 5** (information runs):
     - A rolling 365-day training window lost about 1.0 Sharpe in both holdout eras (-1.09 and -0.95, frozen
       simulator).
     - Adding 2023, 2022-23 or 2021-23 to R2-08's training moved the check era by +0.15, +0.24 and -0.02. There is no
       dose-response, so "more history" is not established.
     - A consensus rule (take only signals two models approve; posthoc_consensus.txt) scored +0.98 on development and
       -0.30 to -0.34 in the check era.
   - **Why the threshold:** every cut of R2-08's marginal signals has failed out of sample today (strictness, sigma
     floor, consensus, and the feature models, which arm less). The marginal signals earn their costs out of sample.
     - R2-08 arms a bid only when the prediction is above the 60th percentile of its training predictions. That rule
       was chosen for a $10K perp book with 6 slots, where capital was scarce.
     - The $250K spot ladder is the opposite: the 0.2% ADV cap binds and cash sits idle. First principles say such a
       book should take every signal with a positive expected net, so the threshold should be lower.
     - Explore v1 only tested stricter thresholds.
   - **Disclosed prior from the holdout eras:** the 50th-percentile variant beat the 60th in the check era in the
     wick v2 lab's diagnostics (a $10K perp book). The lowest predicted-edge tercile above the threshold was profitable
     in both holdout eras (sizing lab). So the check era is not blind to this idea; 2022-23 is nearly so.
   - **Trials (6, N = 37):**
     - RF0Q50, RF0Q40, RF0Q30, RF0Q20: R2-08's model, armed above the 50th / 40th / 30th / 20th percentile.
     - S4F0A0: the spot-cost label, armed when the predicted net is above 0 bp.
     - S4F0Q40: the spot-cost label at the 40th percentile.
   - **Finalist:** the highest screen Sharpe of the six, if above the incumbent's. It gets the same binding test and
     gates. Holm then runs over the four candidates read today (RF2, RF4, RF2H and this one).
   - **Known bias of the screen:** the frozen simulator does not charge resting bids for cash. A looser threshold rests
     more bids, so the engine-faithful result should be lower than the screen's.
7. **Round 4 result and a seed-ensemble information run (Nov 9 2026, 15:52 ET).**
   - **Round 4 failed on development**, so the holdout was not read for it: RF0Q50 -1.06, RF0Q40 -1.66, RF0Q30 -2.30,
     RF0Q20 -2.72, S4F0A0 -2.82, S4F0Q40 -1.54 against the incumbent. The signals below R2-08's threshold lose money
     on the selection era. The threshold stays.
   - **Seed ensemble (information, logged before it ran):** one R2-08 model with 15 seeds, against the five 3-seed
     models, on the frozen simulator in every era. It asks how much of a book's Sharpe is the luck of the seed draw, and
     whether a larger ensemble removes it. It selects nothing: the claim under test is lower variance, not a higher
     mean.
8. **Post-hoc dissection of F2 (Nov 9 2026, 16:13 ET; information only, logged before it ran).**
   - **Seed-averaged results since deviation 7:** the feature reversals hold across seeds (RF2 -0.84 and RF4 -0.72 in
     the check era). Adding the 2021-23 history moves RF2 from -0.84 to +0.13 there.
   - **Question:** is that because F2's two BTC trend-regime features (BTC against its 100-day average, BTC's 30-day
     return) were learned on 2024-25 alone, and the history adds a bear market?
   - **Runs** (frozen simulator, S*, every era): F2a = the six coin-position features only; F2b = the two regime
     features only; each with and without the history (RF2a, RF2b, RF2aH, RF2bH).
   - **Reading it:** if the story is right, RF2b should fail in the check era without the history and recover with it,
     and RF2a should depend on the history much less.
   - These four specs select nothing. They count toward N (41) and shape only the next pre-registered test.
