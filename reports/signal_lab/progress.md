# Signal lab progress log (Nov 9 2026, times ET from the shell clock)

Goal (Miles): raise R2-08's out-of-sample Sharpe at $250K by improving what the model knows (features, labels,
US-accessible data). Develop on Jan 2025 - Mar 2026, read the other eras once, count every trial, score on the
engine-faithful simulator, beat R2-08 head-to-head in every era. "No change" is acceptable. Work until 5 pm.

Where things live: branch signal-lab (worktree /home/claude/wt/v6x). Plan: reports/signal_lab/prereg.md.
Code: scripts/signal_lab/. Trial ledger: reports/signal_lab/screen.csv.

## Log
- 14:28 Task received. Read the hunt 3 log (another session: 66 new models, none beat R2-08).
- 14:36 Pipeline written (scripts/signal_lab/model.py): the lab's own code with a choice of label and feature set, then
  the frozen simulator. Finding while reading the lab: R2-08's label is one 4-sigma trade at perp per-contract costs,
  but the bot trades a spot ladder. That mismatch is the lead candidate.
- 14:37 Parity: the incumbent spec (RF0) through the new pipeline gives R2-08's 1,155 trades through Mar 2026 exactly,
  and the frozen simulator's daily series to 0.0. One spec takes about 14 seconds.
- 14:37 Pre-registration committed (ed5d42d): 4 labels x 5 feature sets (19 trials), finalist rule, engine-faithful binding test,
  gates and scorecard.
- 14:43 Deviation 1 committed before round 2 ran (efb680b): outcome-memory features (F5), more training history (H),
  a main-effects finalist rule. Not run: a Bitstamp premium feature (its history starts in 2024).
- 14:43 Mistake: two lab processes at once ran out of memory and killed the screen at spec 12 of 20. Rerun one at a
  time; the incumbent's parity was re-checked (identical).
- 14:45 Round 1 done (19 trials, selection era). Labels failed: S4 -0.11, LD -0.27, LS -1.89 against the incumbent's
  2.363. Why: the perp costs were not the handicap; the ladder payoff makes the target noisier; dividing by sigma
  down-weights the profitable high-sigma signals. Features: F2 (position and regime) +0.68 and best under every label;
  F4 (DVOL / VIX / Nasdaq) +0.26; F1 and F3 about 0.
- 14:47 Round 2 done (6 trials). Outcome memory failed (RF5 -0.10, LDF5 -0.43): nothing beyond the existing return and
  volatility features. More history helped under every label: +0.28 to +0.54 against the same spec without it.
- 14:50 Deviation 2 committed before round 3 (5a1f1d3). Round 3 (3 trials): RF2H 3.188 (+0.82), S4F2H 3.076, RF4H 2.518.
- 14:51 FREEZE (00a6992): finalists RF2, RF4, RF2H; RF0H as information. Screen statistics: SPA p 0.14, StepM 0 of 28,
  deflated Sharpe of the improvement at most 0.33. Nothing is significant in-sample once trials are counted.
- 15:01 Mistake: the first every-minute panel build ran out of memory (all coins and minutes at once) and cost 10
  minutes. Rewritten to build one quarter at a time, all finalists sharing the features.
- 15:03 Main-era datasets building for RF2, RF2H, RF0H and RF4 (trade lists, tranche precompute, every-minute panels,
  deep paths). About 1 minute per quarter.
- 15:13 Main-era datasets done (594 s). Checks: every-minute predictions equal the candidate-row predictions to 8e-6;
  deep paths 0 mismatches.
- 15:16 First binding cells (engine-faithful, S* theta 0.5, model-priced exits). RF2: selection 3.13 vs R2-08's 2.49
  (the development gain shows on this simulator too), check 1.63 vs 2.22. The feature gain reversed out of sample.
- 15:17 Mistake: the early-era build and the scorer together ran out of memory. Scorer stopped (cells are resumable);
  the early build runs alone, then two scorers in parallel.
- 15:23 Early-era datasets done (371 s), run alone. Two scorers in parallel from 15:24.
- 15:35 Post-hoc signal sets: signals kept by both models earn 41-55 bp gross per dollar; signals only one model keeps
  earn 4-30 bp. A model swap reshuffles break-even signals.
- 15:42 All 60 binding cells done. Chain check: R2-08 rebuilt by the lab in 2022-23 differs from the frozen book from
  2023Q2 (1.645 vs 1.684). Cause found: two candidate rows without a label are dropped by the lab and kept by the
  original pipeline. Main-era parity is exact in both eras.
- 15:43 HOLDOUT READ (d17591d): no finalist passes. RF2 -0.59 and RF4 -0.46 in Apr - Nov 2026. RF2H above R2-08 in all
  12 cells but +0.16 / +0.17 in the holdout eras (51.6 / 100). RF0H +0.12 (information).
- 15:45 Information runs: a rolling 365-day window loses about 1.0 Sharpe in both holdout eras; adding 2023, 2022-23 or
  2021-23 gives +0.15, +0.24, -0.02 in the check era. No dose-response, so "more history" is not established.
- 15:47 Post-hoc consensus rule (only signals two models approve): +0.98 on development, -0.30 to -0.34 in the check
  era. Failed.
- 15:50 Round 4 (looser arming thresholds, registered first): fails on development by 1.1 to 2.8 Sharpe. The signals
  below the threshold lose money. Holdout not read.
- 15:57 Seed noise: R2-08 across five seed triples has SD 0.13 (development) and 0.15 (check). Averaged over seeds,
  history only gains -0.03 in the check era; features + history +0.13. More history cuts the seed spread to 0.04.
- 15:57 Independent review back: no look-ahead, nothing that changes a verdict; six minor notes (README).
- 16:02 Mistake: a queued job waited on itself and never started (10 minutes of idle CPU). Restarted directly: one
  15-seed R2-08 model against the five 3-seed models, all eras.
- 16:06 15-seed models land on the seed averages (R2-08 2.34 / 2.62 against 2.40 / 2.61). A larger ensemble removes
  the seed lottery and leaves the expected Sharpe unchanged.
- 16:09 2022-23, five seed triples: the features gain +0.19 on average (range -0.03 to +0.29).
- 16:12 Seed-averaged check of the reversals: features +0.62 on development and -0.84 in the check era; new data +0.21
  and -0.72. Not seed luck. Adding history moves the features from -0.84 to +0.13 in the check era.
- 16:13 Deliverables: report doc filled (verdict, binding test, development, why, next test, record); README and
  findings section written; everything committed and pushed.
- Verdict: no change. Best scorer: features + history, 51.6 / 100 (above R2-08 in all 12 cells, under the +0.20 bar in
  both holdout eras, p 0.27).
