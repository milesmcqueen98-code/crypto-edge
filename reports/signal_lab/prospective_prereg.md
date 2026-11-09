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
