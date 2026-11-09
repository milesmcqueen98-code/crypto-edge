# Signal lab (Nov 9 2026): what R2-08's model is taught and shown — no change

**Result: no change.** R2-08 keeps its label, features, threshold and training data, and no new paper book opens.
- **Tried:** 41 retrained versions of the model (labels, features, new data, more history, looser thresholds).
- **Read out of sample:** three candidates and one information-only model, once, on the engine-faithful simulator.
- **Best:** features + history, 51.6 / 100. It was above R2-08 in all 12 cells, but by +0.16 and +0.17 Sharpe in the
  holdout eras against a +0.20 bar (p 0.27).

Final report: the "Signal Lab: Report" doc (https://claude.ai/artifact/69u1BHtZsDwEZNXdRwQUUF).

## Setup
- **Goal (Miles):** raise R2-08's out-of-sample Sharpe at $250K by improving what the model knows. Develop on Jan 2025 -
  Mar 2026 (the selection era), read the other eras once, count every trial, score on the engine-faithful simulator,
  beat R2-08 in every era.
- **Plan:** prereg.md, committed at ed5d42d before any candidate ran. Its deviation log has ten entries, each written
  before the runs it covers.
- **Pipeline:** scripts/signal_lab/model.py runs the wick lab's own code with a choice of label, feature set, training
  history and threshold. The incumbent spec reproduces R2-08's trade list and daily series exactly.
- **Development screen:** the frozen simulator at S* (today's volumes, costs doubled, capture 0.5, $250K).
- **Binding test:** ladder v6's engine-faithful replay. Each finalist got its own trade list, tranche dataset,
  every-minute armed panel and deep paths. Both books' market exits are priced by the cost model.

## Development (screen ΔSharpe against R2-08's 2.363; screen.csv, screen_stats.txt)

| Label | Base features | Cascade state (F1) | Position and regime (F2) | All candle sets (F3) | DVOL, VIX, Nasdaq (F4) | Outcome memory (F5) |
|---|---|---|---|---|---|---|
| R: R2-08's (one 4-sigma trade, perp costs) | 0.00 | +0.02 | +0.68 | -0.01 | +0.26 | -0.10 |
| S4: the same trade at spot costs | -0.11 | +0.06 | +0.20 | -0.13 | +0.13 | not run |
| LD: the whole spot ladder | -0.27 | -0.43 | +0.13 | -0.15 | +0.26 | -0.43 |
| LS: the ladder per unit of sigma | -1.89 | -1.75 | -0.74 | -0.49 | -0.99 | not run |

- **With the 2021-23 candidates added to training (H):** RF0H +0.39, S4F0H +0.42, LDF0H +0.01, LSF0H -1.53, RF2H +0.82,
  S4F2H +0.71, RF4H +0.16.
- **Labels, seed-averaged** (five seed triples, frozen simulator, after the read; dose_seeds_main_label.csv,
  dose_seeds_early_label.csv), development / Apr - Nov 2026 / 2022-23:
  - S4 (spot costs): -0.06 / +0.30 / -0.06. Positive in all five triples in Apr - Nov 2026, negative in all five in
    2022-23. Not a consistent gain.
  - LD (the whole ladder): -0.28 / -0.41 / +0.07.
- **Looser thresholds (round 4):** 50th percentile -1.06, 40th -1.66, 30th -2.30, 20th -2.72; predicted net above 0 bp
  -2.82. The signals below R2-08's 60th-percentile threshold lose money, so the holdout was not read for this idea.
- **Multiple testing:** SPA p 0.14 against R2-08; StepM: none significantly better; deflated Sharpe of the improvement
  at most 0.33.

## Binding test (holdout.txt; ΔSharpe against R2-08, S* capture 0.5, $250K)

| Finalist | Development | Apr - Nov 2026 | 2022-23 | Cells above R2-08 (of 12) | Gates passed (of 5) | Score /100 |
|---|---|---|---|---|---|---|
| RF2H: features + history | +0.79 | +0.16 | +0.17 | 12 | 3 | 51.6 |
| RF0H: history only (information) | +0.35 | +0.12 | same book | 7 | 2 | 33.7 |
| RF2: position-and-regime features | +0.63 | -0.59 | +0.17 | 9 | 1 | 32.4 |
| RF4: DVOL, VIX, Nasdaq | +0.34 | -0.46 | -0.44 | 4 | 1 | 19.3 |

- **All fail gate 1** (+0.20 in every era) and gate 5 (pooled holdout p <= 0.05). RF2H's p is 0.27.
- **RF2H runs without the history in 2022-23** (no earlier data exists), so only its four Apr - Nov 2026 cells test the
  added history out of sample.
- **Print-priced exits** (information; favours R2-08): Apr - Nov 2026 gains are +0.06 for RF2H and -0.01 for RF0H.

## Why (post hoc, information only)
- **The models agree on the signals that carry the profit** (posthoc_sets.txt).
  - Signals kept by both models earn 41-55 bp gross per dollar in every era.
  - Signals kept by only one model earn 4-30 bp, about a round trip's costs.
- **Cutting the disputed signals fails** (posthoc_consensus.txt): +0.98 on development, then -0.30 to -0.34 in Apr - Nov
  2026 and -0.02 in 2022-23.
- **How much history** (dose_main.csv, dose_early.csv; frozen simulator, development / Apr - Nov 2026 / 2022-23):
  - only the last 365 days: +0.10 / -1.09 / -0.95;
  - adding 2023: -0.34 / +0.15; adding 2022-23: +0.05 / +0.24; adding 2021-23: +0.39 / -0.02.
  - So a one-year window is too short, and beyond R2-08's growing window there is no dose-response.
- **Seed noise** (dose_seeds_main.csv; five seed triples, frozen simulator):

  | Mean (SD across seed triples) | Development | Apr - Nov 2026 |
  |---|---|---|
  | R2-08 | 2.40 (0.13) | 2.61 (0.15) |
  | History only | 2.77 (0.03) | 2.58 (0.04) |
  | Features + history | 3.17 (0.07) | 2.74 (0.04) |

  - Averaged over seeds, history only gains -0.03 in Apr - Nov 2026 and features + history +0.13 (range -0.09 to +0.33).
  - More history cuts the seed-to-seed spread from 0.15 to 0.04. It steadies the model; it does not raise the mean.
  - **One 15-seed model lands on the seed average** (dose_seeds15_main.csv): R2-08 scores 2.34 / 2.62 against the
    five-triple means of 2.40 / 2.61. With 15 seeds, features + history is +0.10 in Apr - Nov 2026 and history only
    -0.06. A larger ensemble removes the seed lottery without changing the expected Sharpe.
  - **The bot's own five seeds** (7, 11, 23, 42, 101; dose_seeds_main_bot5.csv, dose_seeds_early_bot5.csv) give 2.42 /
    2.63 / 1.60 (development / Apr - Nov 2026 / 2022-23) against the research book's 2.36 / 2.57 / 1.70. The research
    book is representative of the model the bot trains.
  - **2022-23** (dose_seeds_early.csv): the position-and-regime features gain +0.19 on average over five seed triples
    (range -0.03 to +0.29) and +0.32 with 15 seeds, against R2-08 rebuilt by the lab.
  - **The reversals are not seed luck** (dose_seeds_main_feat.csv): averaged over five seed triples, RF2 is +0.62 on
    development and -0.84 in Apr - Nov 2026 (every triple negative); RF4 is +0.21 and -0.72.
  - **History rescues the features:** adding 2021-23 moves RF2's Apr - Nov 2026 result from -0.84 to +0.13.
  - **It is not the regime features in particular** (dose_split_main.csv, dose_split_early.csv; registered seeds).
    Development / Apr - Nov 2026 / 2022-23:
    - the six coin-position features alone: +0.31 / -0.64 / -0.14; with history +0.42 / -0.12;
    - the two BTC-regime features alone: -0.52 / -0.58 / +0.11; with history +0.87 / +0.02.
    - Both halves fail without the history and recover with it, and neither beats R2-08 out of sample.

## Checks
- **Parity:** the incumbent spec gives R2-08's trades and frozen-simulator daily series exactly, on development and on
  Apr - Nov 2026.
- **Datasets:** every-minute predictions equal the candidate-row predictions to about 1e-5; deep paths show 0
  mismatches.
- **2022-23:** R2-08 rebuilt by the lab differs from the frozen book from 2023Q2 (engine-faithful Sharpe 1.645 against
  1.684). Two candidate rows without a label (BCH and XLM, Mar 4 2023) are dropped by the lab and kept by the original
  pipeline, where LightGBM reads them as 0. Comparisons there are against the frozen R2-08, as registered.
- **Independent review** (a separate agent, read-only): no look-ahead found, and nothing that changes a verdict. Its
  notes:
  - The 60th-percentile threshold comes from each model's own training predictions, so feature and history effects
    are mixed with how selective the model is.
  - History rows carry today's per-coin perp fee in the R label.
  - The Nasdaq-futures daily bar may close later than assumed. It affects RF4 only, which failed.

## Next
1. **Method:** average at least five seed triples per arm in every future model comparison.
2. **Next model test:** forced-selling features from Coinbase trade prints for every candidate (edge hunt 2's EXH was
   the closest miss as a filter), with this lab's pipeline, gates and seed averaging. It is pre-registered in
   prospective_prereg.md, written before any print is fetched. It needs a data job (candidate lists:
   candidates_main.csv.gz and candidates_early.csv.gz).
3. **Leave the bot's training as it is.** bot/train_v2.py already uses a growing window from 2024, five seeds, and
   drops unlabelled rows. Never switch to a rolling window. Optional: 15 seeds at the next retrain (same expected
   Sharpe, less seed noise). The research walk-forward (scripts/lab/core.py) should drop unlabelled rows when next
   touched.
4. **Forward data:** open interest and funding logs (hunt 3's hourly logger) for a model test in about six months.
