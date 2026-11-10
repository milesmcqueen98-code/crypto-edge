# Signal lab (Nov 9 2026): what R2-08's model is taught and shown — no change

**Result: no change.** R2-08 keeps its label, features, threshold and training data, and no new paper book opens.
- **Tried:** 41 retrained versions of the model (labels, features, new data, more history, looser thresholds).
- **Read out of sample:** three candidates and one information-only model, once, on the engine-faithful simulator.
- **Best:** features + history, 51.6 / 100. It was above R2-08 in all 12 cells, but by +0.16 and +0.17 Sharpe in the
  holdout eras against a +0.20 bar (p 0.27).

Final report: the "Signal Lab: Report" doc (https://claude.ai/artifact/69u1BHtZsDwEZNXdRwQUUF).

**Signal lab 2 (the next test below, run the same day): no change either.** Trade-print features scored 38.6 and
39.3 / 100. See the last section.

## Setup
- **Goal (Miles):** raise R2-08's out-of-sample Sharpe at $250K by improving what the model knows. Develop on Jan 2025 -
  Mar 2026 (the selection era), read the other eras once, count every trial, score on the engine-faithful simulator,
  beat R2-08 in every era.
- **Plan:** prereg.md, committed at ed5d42d before any candidate ran. Its deviation log has eleven entries, each written
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
- **Selectivity, not ranking** (dose_match_main.csv, dose_match_early.csv; frozen simulator, registered seeds). Each
  model's threshold is the 60th percentile of its own training predictions, and the challengers arm fewer signals
  than R2-08. With each quarter's threshold reset so a model keeps R2-08's share of candidates (a diagnostic, not a
  tradable rule), development / Apr - Nov 2026 / 2022-23:
  - RF2: +0.49 / -0.21 / +0.03 (unmatched: +0.68 / -0.80);
  - RF4: +0.25 / -0.28 / -0.27 (unmatched: +0.26 / -0.73);
  - RF2H: +0.53 / +0.09 (unmatched: +0.82 / +0.20);
  - RF0H: +0.54 / +0.25 (unmatched: +0.39 / -0.02).
  - Most of the challengers' check-era loss came from arming fewer signals. What is left is within the noise.
  - Averaged over five seed triples (dose_seeds_main_match.csv), development / Apr - Nov 2026: RF0H +0.38 / +0.15
    (positive in 5 and 4 of 5 triples); RF2H +0.39 / +0.13. So the added features rank no better than R2-08's, and
    more history may rank slightly better.
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
1. **Method:** average at least five seed triples per arm in every future model comparison, and read each challenger
   at R2-08's selectivity as well as at its own.
2. **Next model test (done, see "Signal lab 2" below: no change):** forced-selling features from Coinbase trade prints for every candidate (edge hunt 2's EXH was
   the closest miss as a filter), with this lab's pipeline, gates and seed averaging. It is pre-registered in
   prospective_prereg.md, written before any print is fetched. It needs a data job (candidate lists:
   candidates_main.csv.gz and candidates_early.csv.gz).
3. **Leave the bot's training as it is.** bot/train_v2.py already uses a growing window from 2024, five seeds, and
   drops unlabelled rows. Never switch to a rolling window. Optional: 15 seeds at the next retrain (same expected
   Sharpe, less seed noise). The research walk-forward (scripts/lab/core.py) should drop unlabelled rows when next
   touched.
4. **Optional forward check on history:** train R2-08 with the 2021-23 history, set its threshold from the 2024-on
   rows so it arms about as often as R2-08, and log its decisions beside the paper book. No trading change.
5. **Forward data:** open interest and funding logs (hunt 3's hourly logger) for a model test in about six months.

## Signal lab 2 (Nov 9 2026): forced-selling features from trade prints - no change

**Result: no change.** RF6H 38.6 / 100 and RF6 39.3 / 100. Both fail gates 1, 2, 3 and 5. R2-08 keeps its model and
no new paper book opens. Final report: the "Signal Lab 2: Report" doc (https://claude.ai/artifact/R4kib7NPnS2BaG1LkarYaB).

**How it was run (set by Miles):** the main agent orchestrated and kept the protocol. Opus agents at max effort did all
implementation (the print-data job, the pipeline, the model runs). A separate Opus agent audited for look-ahead before
the holdout was read. Five seed triples per arm; one holdout read.
- **Plan:** prospective_prereg.md, written before any print was fetched. Five deviations, each logged before the work
  it covers. Log: progress2.md.
- **Order of reads:** selection era, the audit (two passes), the lock (test2/AUDIT_PASSED, 19:19 ET), then the
  seed-averaged reading and the binding test with nothing decided between them.
- **One interruption:** a machine restart stopped the binding test after its chains and 11 of the incumbent's 12
  cells. No candidate cell existed yet; the remaining steps ran unchanged (deviation 5).

**What was tested:**
- **Five features** from Coinbase trade prints before each candidate fill minute: taker-sell USD over daily volume
  (30 and 5 minutes), taker-sell share, the share of it in large prints, and the largest one-second sweep.
- **RF6:** R2-08's label and 23 features plus the five. **RF6H (primary):** the same with the 2021-23 candidates added
  to training. Nothing tuned.
- **Incumbent:** R2-08 rebuilt by the lab's pipeline as one 15-seed model.

**Data and timing:**
- **Data job:** 79.1M prints, 10,042 merged windows, one feature row for each of 32,090 candidates. Gate passed: every
  window complete; print USD over candle USD has a median of 1.0002 in both eras.
- **The repo's candles and the prints keep slightly different clocks.** They disagree in 14-23% of minutes. Most of it
  is harmless: the candles run ahead of the prints by about 8 s.
- **The leak:** trades stamped before a candidate minute sit in its candle, or its previous candle is missing, for
  0.45% / 1.71% / 1.45% of candidates (selection / Apr - Nov 2026 / 2022-23).
- **Rule, logged before the diagnostic reported:** the smallest of 0 s, 5 s and 60 s with under 0.5% of candidates
  leaking in every read era. Only 60 s qualifies (0.00% / 0.05% / 0.14%). So every feature window ends 60 s before
  the candidate minute, and the test does not use the last minute before the fill.
- **Audit:** no look-ahead in the feature code, the ADV, the join, the walk-forward, the every-minute panel, the lock
  or the scorer. Its own recount of the leak flags matched.

**Results** (ΔSharpe against R2-08; selection / Apr - Nov 2026 / 2022-23; in 2022-23 RF6H runs as RF6):

| Reading | RF6H | RF6 |
|---|---|---|
| Seed-averaged, frozen simulator (five seed triples) | +0.50 / +0.07 / as RF6 | -0.01 / -0.01 / +0.02 |
| The same at R2-08's selectivity | +0.42 / +0.18 / as RF6 | -0.05 / +0.04 / -0.06 |
| Binding test: 15 seeds, engine-faithful, $250K, θ 0.5 | +0.26 / +0.04 / +0.15 | +0.05 / +0.03 / +0.15 |
| Binding test at θ 0.25 | +0.33 / +0.12 / +0.15 | +0.10 / +0.03 / +0.15 |
| Binding test at $1M | +0.59 / +0.17 / +0.24 | +0.04 / +0.06 / +0.24 |
| Binding test at research volumes, 1x costs | -0.12 / +0.14 / +0.14 | -0.01 / -0.06 / +0.14 |
| Frozen simulator, 15 seeds (no cash rule) | +0.51 / +0.03 / +0.14 | +0.02 / -0.08 / +0.14 |
| Every other minute armed, both books | +0.39 / +0.01 / +0.15 | +0.11 / +0.04 / +0.15 |

- **Gates:** both fail gate 1 (+0.20 in each era), gate 2 (research volumes), gate 3 (drawdown within 1.1x) and
  gate 5 (pooled holdout p 0.22 and 0.21; Holm 0.41). Both pass gate 4 (no losing year).
- **Scorecard (RF6H / RF6):** Sharpe gain 5.8 / 5.4 of 25; capacity 5.1 / 3.7 of 10; consistency 13.8 / 12.5 of 15
  (11 and 10 of 12 cells positive); evidence 0 / 0 of 15; spread 0 / 0 of 10; risk 6.0 / 8.7 of 10; mechanism 6 / 6 of
  10; implementation 2 / 3 of 5.
- **The gain sits on a few days:** the five best days carry more than the whole pooled holdout gain (2.3x and 1.7x).
- **Checks:** every chain's built-in checks passed (0 armed-state mismatches, 0 deep-path mismatches). The gates and
  scorecard were recomputed from the daily series with separate code and match to 1e-15. R2-08's seed-triple rows are
  bit-identical to the first lab's.

**Why:**
- **The prints tell the model little that the candles do not.** Averaged over seeds they move R2-08 by -0.01 / -0.01 /
  +0.02. Taker-sell share follows the price path (rank correlation -0.34 to -0.38 with the window's return).
- **RF6H's selection gain is the history again.** History alone was +0.37 in selection and -0.03 in Apr - Nov 2026.
- **Beside the history the prints change selectivity, not ranking:** +0.13 / +0.11 at the model's own threshold
  (5 of 5 seed triples both times), +0.03 / +0.03 at R2-08's selectivity (3 of 5).
- **The last minute adds nothing in sample.** The 0 s table, which includes it and the leak, did no better on the
  selection era: RF6 +0.06 against -0.01, RF6H +0.43 against +0.50.
- **The 2022-23 gain depends on the seed set:** +0.15 for the 15-seed model, +0.02 on average for the five 3-seed
  triples (range -0.09 to +0.07).
- **Every gain found so far is under the noise floor.** The pooled holdout difference has a standard error of 0.16
  Sharpe over 2.6 years. A true +0.12 would need about 13 years of forward data to reach one-sided 5%.

**Next:**
1. **Start the hourly open-interest and funding log.** The next model test needs it and it cannot be backfilled. As
   of Nov 9 the logger written in hunt 3 is not on GitHub (no workflow, script or branch). Hunt 3's forward test
   needs it running from the default branch by Nov 15.
2. **Next model test, once about a year of that log exists:** open-interest and funding features in R2-08's model,
   with this lab's pipeline, gates, 60 s rule and seed averaging.
3. **The forward rules already fixed decide R2-08's real Sharpe:** paper, the $10K pilot, then capture share at $250K.
   Capture share alone is worth 0.19-0.26 Sharpe (θ 0.5 against 0.25 in R2-08's cells: 2.48 / 2.31 / 1.52 against
   2.29 / 2.05 / 1.26).
4. **At the next retrain:** 15 seeds instead of 5 (first lab: same expected Sharpe, less seed noise).
5. **Not built:** a live shadow log of the print features. It needs a new live data path for an effect that cannot be
   confirmed in under a decade.

**Files:** test2_m60/ (selection.txt, seeded.txt, holdout.txt, sensitivity.csv, cells/), test2_m0/ (the 0 s table,
selection era only), prints/ (QA.md, leak_flags.parquet), prints_m60/ (the tables the test read, with sha256),
test2/AUDIT_PASSED. Data job: branch signal-lab-data (scripts/signal_lab/prints_*.py); raw prints are not stored.
