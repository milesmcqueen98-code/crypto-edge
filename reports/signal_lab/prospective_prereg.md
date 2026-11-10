# Signal lab 2: forced-selling features from trade prints — pre-registration (Nov 9 2026)

Written after the signal lab's read and before any trade print is fetched for this test. Branch signal-lab.

## Why
- **The model cannot see who is selling.** Candles carry price and volume, not the aggressor side.
- **Edge hunt 2's closest miss was a prints variable.** EXH skipped fills that came before much aggressive selling.
  As a filter it was positive in every era and at 1x costs (hold-out t 1.51), and it could only drop fills.
- **As a model feature for every candidate it can also add signals.**
- **What the signal lab showed** (reports/signal_lab/README.md):
  - candle and macro features do not hold out of sample;
  - any model with added features needs the 2021-23 history;
  - R2-08's seed noise is 0.13-0.15 Sharpe, so arms must be seed-averaged;
  - the profit sits in signals every model already takes, so expect a small effect.

## Data (one job, before anything is run)
- **Source:** Coinbase's public trade prints (the same feed the bot can read live).
- **Windows:** the 30 minutes before each candidate fill minute q, for every candidate of both eras
  (reports/signal_lab/candidates_main.csv.gz and candidates_early.csv.gz; about 32,000 candidates, many windows
  overlapping).
- **Kept:** one feature row per candidate. Raw prints stay on the runner.
- **Timing rule:** only prints stamped before minute q. A feature on row q is known at the end of minute q-1.
- **How to run it:** the generic Actions runner .github/workflows/hunt2.yml (on main) runs a script and commits its
  derived rows. Edge hunt 2's scripts/hunt2/prints.py and scripts/hunt2/who/flowfilt.py (branch hunt2) already compute
  `csv_30` for R2-08's fills; extend them to every candidate and the five features below.

## Features (F6; fixed now)
For coin c and candidate minute q, with ADV = the coin's trailing 30-day median daily USD volume as of the day before:
1. `csv_30`: taker-sell USD in [q-30 min, q) / ADV. This is EXH's variable.
2. `csv_5`: the same over [q-5 min, q).
3. `sell_share_30`: taker-sell USD / all USD in [q-30 min, q).
4. `big_sell_share_30`: the share of that taker-sell USD in prints at or above the coin's trailing 30-day
   99th-percentile print size.
5. `sweep_max_30`: the largest one-second taker-sell USD in [q-30 min, q) / ADV.

A candidate with no prints in its window gets missing values (LightGBM handles them).

## Candidates (2; no development search)
- **RF6H (primary):** R2-08's label and 23 features + F6, trained with the 2021-23 history in the main era. In
  2022-23 it runs without it (no earlier data).
- **RF6 (single change):** the same without the added history.
- Nothing is tuned. No other spec runs without a logged deviation made first.

## Test
1. **Seed-averaged reading (frozen simulator, S*):** each arm with five seed triples, every era, against R2-08 with the
   same five triples.
2. **Binding test (engine-faithful simulator):** each candidate and R2-08 as 15-seed models, built by
   scripts/signal_lab/model.py chain and scored by score.py with this lab's configurations.
3. **Pass (all required):** this lab's gates 1-5 (prereg.md), with Holm across the two candidates.
4. **Scorecard:** this lab's, unchanged.

## Verdicts
- A winner gets a new paper book, with the print features computed live. Nothing goes live from this test.
- Otherwise the prints lead closes for the model, and model-side tests wait for forward data (open interest and
  funding logs).

## Power, stated before the read
- One era's Sharpe difference between two correlated books has a standard error of roughly 0.5.
- So +0.20 in each of three eras is a demanding bar, and a real gain of +0.2 will often miss it.
- A miss with a consistent positive sign would be a lead for a paper-shadow log, not a change.

## Deviation log
1. **Before any print was fetched or any model run (Nov 9 2026, 16:48 ET).** Decisions the plan left open, fixed now.
   - **Roles:** the session's main agent keeps the protocol and decides. Opus agents build the data job, the feature
     code and the model runs. A separate Opus agent audits for look-ahead before the holdout read.
   - **"Big" prints (feature 4).** A trailing 30-day percentile over all prints would need every print the coin
     traded. The job fetches only the candidate windows, so the threshold is taken from those:
     - the 99th percentile of print size in USD over the coin's fetched prints stamped in the 30 days before the
       candidate's own window starts;
     - if that holds fewer than 2,000 prints, the most recent 2,000 fetched prints before the window;
     - if fewer than 2,000 exist at all, the feature is missing.
   - **Taker sells:** prints whose maker side is BUY (a resting bid was hit).
   - **ADV:** the trailing 30-day median daily USD volume on Coinbase spot candles, as of the day before, with the
     10-day minimum the simulator uses.
   - **Data-quality gate, before any model run:**
     - at least 97% of candidates in each era have a completely fetched window;
     - print USD against candle USD over the same windows has a median ratio of 0.98-1.02 in each era.
     - If either fails, the test stops and the gap is reported.
   - **Every-minute panel for the binding test.** The engine-faithful replay needs a prediction for every minute, and
     print features for every minute would need every Coinbase print for five years. So:
     - at candidate minutes (the only minutes a bid can fill) the candidate's own prediction is used, which is exact;
     - at other minutes its no-prints twin's prediction is used (RF0 for RF6, RF0H for RF6H), shifted so the twin's
       own armed state is kept. This only affects how much cash resting bids hold.
     - Sensitivity, reported with the result: the same replay with every non-candidate minute armed, and the frozen
       simulator, which has no cash rule.
   - **Order of reads:**
     1. the selection era alone, with the walk-forward stopped at 2026Q1 so no holdout prediction exists;
     2. the independent look-ahead audit;
     3. one holdout read of the check era and 2022-23: the seed-averaged reading and the binding test together.
   - **Added reading (information):** each candidate at R2-08's selectivity (thresholds reset to R2-08's share of each
     quarter's candidates), five seed triples. The signal lab showed selectivity alone moves results.
   - **Seeds:** the five triples of the signal lab, (7, 11, 23), (1, 2, 3), (4, 5, 6), (8, 9, 10) and (12, 13, 14).
     The 15-seed model is their union.
   - **Hand scores, assigned now** (mechanism /10, implementation /5): RF6H 6 and 2; RF6 6 and 3.
     - Mechanism 6: aggressive selling before the fill measures forced selling directly, which candles cannot. EXH was
       positive in every era as a filter. Against: edge hunt 2's other print screens ran backwards, EXH's gain sat on a
       few days, and the profit sits in signals every model already takes.
     - Implementation 2-3: the bot must aggregate the live trade feed per coin every minute, a new data path. RF6H
       also retrains on 2021-23 and needs print features for those years.
   - **Comparison in the binding test:** against R2-08 rebuilt by the lab's pipeline as a 15-seed model (like for
     like), with model-priced exits for every book.
2. **After the data job, before any model has seen a print feature (Nov 9 2026, 18:42 ET).** Written before the
   boundary diagnostic below has reported.
   - **Data-quality gate: passed** (reports/signal_lab/prints/QA.md). Every candidate's window is complete in both
     eras, and print USD over candle USD has a median of 1.0002 in both.
   - **Choices made by the data agent, accepted** (no outcome, label or prediction was read):
     - ADV is one continuous daily series per coin across the era boundary, so January 2024 uses December 2023;
     - the big-print pool is the coin's fetched prints of both eras stamped before the candidate's window starts;
     - the 99th percentile is numpy's linear interpolation; the sweep uses calendar seconds;
     - missing values: ADV for 10 main and 190 early rows, the big-print threshold for 24 and 73. LightGBM takes
       them as missing.
     - The Actions runner's own commits on branch signal-lab-data carry its fixed message without trailer lines.
   - **A timing risk found in the QA.** Prints and the repo's candles disagree in 14-23% of minutes, mostly with
     volume sitting in the neighbouring minute. The simulator decides fills from candles. If the candle of minute q
     holds trades stamped before q, a feature built from "prints before q" sees part of the fill minute. The plan's
     timing rule ("known at the end of minute q-1") is then broken by the candle clock, not by the code.
   - **Boundary diagnostic and margin tables (data agent, no outcomes).** For each candidate's own boundary it
     measures whether trades stamped before q sit in the candle of q, and by how many seconds. It also builds the
     same five features with the windows ending at q - 5 s and at q - 60 s.
   - **Rule for the table the test uses, fixed now:**
     - A candidate counts as leaking under margin M if trades stamped before q - M sit in the candle of q or later.
     - A disagreement that no boundary move up to 60 s explains counts as leaking under 0 s and 5 s when both signs
       fit a move into q (the prints of q-1 exceed its candle and the candle of q exceeds its prints).
     - The primary table is the smallest margin among 0 s (as registered), 5 s and 60 s under which fewer than
       0.5% of candidates leak in each era.
     - 60 s is the floor: a lag of more than a minute cannot be measured by this diagnostic. That limit is stated
       with the result.
   - **Information readings, declared now:**
     - the 60 s table in the selection reading and in the seed-averaged holdout reading (if it is not the primary);
     - the 0 s table on the selection era only (if it is not the primary), to measure what the boundary adds.
     - The binding test runs the primary table only. Gates and scorecard use the primary table only.
   - **Unchanged:** candidates, seeds, gates, scorecard, hand scores and the order of reads.
3. **After the audit's first report (Nov 9 2026, 18:59 ET).** Written before the boundary diagnostic has reported and
   before any holdout number exists.
   - **Audit: pass with conditions.** No look-ahead found in the feature code, the ADV, the join, the walk-forward,
     the mixed panel, the holdout lock or the scorer. One major finding, the candle clock of deviation 2.
   - **Its estimates at the candidate's own boundary** (share of candidates with trades stamped before q in the
     candle of q): 0.08-0.14% in the selection era, 0.20-0.32% in Apr - Nov 2026, under 0.05% in 2022-23. With
     candidates whose previous candle is missing: 0.6%, 1.6% and 1.6%.
   - **Conditions adopted. They tighten deviation 2's rule:**
     - The 0.5% bar applies in each read era (selection, Apr - Nov 2026, 2022-23), not in each data era.
     - A candidate whose candle of q-1 is missing while prints exist in that minute leaks under 0 s and 5 s. The
       bid's reference price is then stale, so the real crossing may sit in the missing minute, which those windows
       include. Under 60 s the same holds when the candles of q-1 and q-2 are both missing with prints in q-2.
     - One margin for every row. No row is masked: a mask built from the candle of q would itself leak.
     - Every step reads the chosen table from its own folder, and the table's sha256 is logged.
     - The frozen-simulator and all-armed sensitivities are reported beside the binding result (as declared).
     - Nobody computes statistics of the print features against labels on holdout rows before the read.
     - RF6H's result is read beside RF6's and the first lab's history-only model: against R2-08 it also carries the
       2021-23 history.
   - **Before the lock file is created,** the auditor checks the margin code and the leak counts.
   - **Selection reading on the 0 s table** (run under deviation 2; test2_m0/): information unless the rule picks
     0 s.
4. **The rule's outcome: the 60 s table is the primary (Nov 9 2026, 19:07 ET).** Before any holdout number.
   - **Diagnostic** (data agent; prints and candles only; branch signal-lab-data 440314f, reports/signal_lab/prints/
     QA.md and leak_flags.parquet). The repo's candles mostly lead the prints: trades stamped in the first seconds of
     a minute sit in the previous candle (median 8 s), which cannot leak. The leak direction is rare and is mostly a
     missing candle whose minute sits in the next one. Every measured offset in the leak direction is under 60 s.
   - **Candidates leaking under each margin** (deviations 2 and 3):

     | Read era | Candidates | 0 s | 5 s | 60 s |
     |---|---|---|---|---|
     | Selection (Jan 2025 - Mar 2026) | 7,788 | 0.45% | 0.44% | 0.00% |
     | Check (Apr - Nov 5 2026) | 4,095 | 1.71% | 1.68% | 0.05% |
     | 2022-23 | 10,603 | 1.45% | 1.45% | 0.14% |

     Training-only years: 2021 0.18% / 0.18% / 0.00%; 2024 0.34% / 0.34% / 0.07%.
   - **Upper bounds for 0 s and 5 s** (the last candidate of each merged window, whose own minute was not fetched,
     cannot be decided): 1.8%, 5.3% and 5.1%.
   - **So the test uses the 60 s table:** every feature's window ends at q - 60 s, i.e. [q - 30 min, q - 60 s) and
     [q - 5 min, q - 60 s). The big-print threshold and the ADV do not move. Tables: f6_main_m60.parquet and
     f6_early_m60.parquet, copied to reports/signal_lab/prints_m60/ under the names the pipeline reads.
   - **Limits, stated now:** the test does not use the last minute before the fill, which may be the most informative
     one. A candle lag above 60 s cannot be measured by this diagnostic.
   - **Readings:** selection, seed-averaged holdout and binding test on the 60 s table, in reports/signal_lab/
     test2_m60/. The 0 s table stays information on the selection era only (test2_m0/). The 5 s table is not used.
5. **The read was interrupted by a container restart and is resumed unchanged (Nov 9 2026, 20:08 ET).**
   - **What happened:** the machine restarted at about 20:06 ET during the binding test's third step (the
     incumbent's cells). Every process stopped. The files survived.
   - **State on disk, checked before anything was rerun:**
     - both chains had finished with clean checks (every-minute values within 2e-5 of the candidate predictions; 0
       armed-state mismatches; 0 deep-path mismatches);
     - 11 of the incumbent's 12 cells were written and are complete;
     - no candidate cell had been computed, so no binding number for RF6 or RF6H exists or was seen.
   - **Resumption:** the remaining steps of the same driver, as `test2.py c --dry` prints them from step 3 on, in the
     same order, one process at a time. The cell step keeps cells already written (they are deterministic) and
     computes the missing one. Nothing else changes: same table, datasets, configurations, gates and scorecard.
   - It remains one holdout read.
