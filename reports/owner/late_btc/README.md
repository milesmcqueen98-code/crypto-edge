# What a late BTC input costs (replay of reports/owner/late_btc_prereg.md)

Run Nov 10 2026, read 15:05 ET. Plan: reports/owner/late_btc_prereg.md (fixed before any result). Descriptive: nothing
is chosen with it.

## The answer
- **A late BTC costs R2-08 about half a Sharpe point in two of three eras, and nothing visible in the third.**
- Headline, S3 (each minute one or two minutes late, the probe's 70 / 30 mix; mean of five seeds, range in brackets):
  - Jan 2025 - Mar 2026 (selection): Sharpe 2.94 to 2.41 (2.34 to 2.52), about -0.5; yearly return 22.8% to 19.7%.
  - Apr - Nov 2026 (check): 2.66 to 2.86 (2.69 to 3.23), about +0.2; return 19.1% to 19.4%. No cost seen.
  - 2022-23: 1.91 to 1.21 (1.06 to 1.34), about -0.7; return 11.1% to 9.3%.
- Bracket: S1 (always one minute late) costs about -0.4 / +0.2 / -1.0; S4 (S3 plus 30% of older BTC minutes wrong)
  about -0.9 / +0.3 / -1.0.
- In return terms: about 2 to 3 points a year in selection and 2022-23, about 0 in the check era.
- **The paired daily test is weak.** Most 90% intervals include zero. Only S2 in selection and S1 in 2022-23 exclude
  it. So the cost is likely but its size is uncertain: think "between nothing and about one Sharpe point".
- **The loss sits on crash days.** Late BTC means bids set as if BTC had not yet fallen. In 2022-23 the five worst days
  of S1 against S0 carry about 70% of its loss (Nov 8 2022 alone, the FTX day, about -1.8%). In selection, Oct 10
  2025 is the largest single day (about -1.5%).
- Fixing the input (release 2) matters. The fix is cheap and the downside is concentrated in exactly the days that
  decide a year.

## Table (Sharpe / yearly return, $250K, best-estimate configuration; difference from S0; paired daily difference)

| Era | S0 (true BTC) | S1 (1 min late) | S2 (2 min late) | S3 (mix, 5 seeds) | S4 (mix + old rows, 5 seeds) |
|---|---|---|---|---|---|
| Selection | 2.94 / 22.8% | 2.50 / 19.8% (-0.44) | 1.81 / 16.6% (-1.12) | 2.41 / 19.7% (-0.53; -0.60 to -0.41) | 2.02 / 18.8% (-0.92; -1.36 to -0.58) |
| paired, bp a day (90%) | | -0.8 (-1.7 to +0.1) | -1.7 (-3.1 to -0.4) | -0.8 (-1.8 to +0.1) | -1.1 (-2.8 to +0.6) |
| Check | 2.66 / 19.1% | 2.91 / 19.4% (+0.24) | 3.09 / 21.5% (+0.43) | 2.86 / 19.4% (+0.20; +0.03 to +0.57) | 2.98 / 18.4% (+0.32; -0.18 to +0.83) |
| paired, bp a day (90%) | | +0.1 (-0.7 to +1.0) | +0.7 (-0.5 to +1.9) | +0.1 (-0.6 to +0.9) | -0.2 (-1.3 to +0.9) |
| 2022-23 | 1.91 / 11.1% | 0.87 / 7.8% (-1.04) | 1.48 / 10.3% (-0.43) | 1.21 / 9.3% (-0.71; -0.85 to -0.58) | 0.94 / 8.6% (-0.97; -1.23 to -0.59) |
| paired, bp a day (90%) | | -0.9 (-1.5 to -0.3) | -0.2 (-0.8 to +0.3) | -0.5 (-1.0 to +0.0) | -0.7 (-1.6 to +0.2) |

- Sharpe as the repo measures it (fsim.stats). "bp a day" = mean daily return difference in basis points of capital.
- S3 and S4 show the mean over seeds, then the range of the five seeds' differences.
- Fills, net per dollar and worst days: table.csv. Every seed: results.csv. Each seed's own paired interval: paired.csv.
- Two minutes late is not always worse than one (2022-23). The fills reshuffle; one-path noise is about as large as the
  effect.

## How the decisions moved
- **Arming barely changes.** About 99% of S0's armed coin-minutes stay armed in S1 to S3 (93-96% in 2022-23, 92-95%
  in S4). Under 1% (2-3% in 2022-23) of the scenario's armed minutes are new.
- **The level moves a few bp.** Median absolute difference about 2-4 bp (S1, S3), about 3-5 bp (S2); 95th percentile
  about 14-34 bp. S4 is larger: median about 14-19 bp, 95th percentile about 50-75 bp.
- **So the fills change a lot.** A few bp decide whether a dip touches the bid. Only about 38-62% of S0's first-bid
  fills happen at the same coin and minute in S1 to S3 (27-37% in S4), and about 41-63% of the scenario's first-bid
  fills are new (61-73% in S4). Counts stay similar (for example selection S3 about 1,250 first-bid fills against 1,120).
- **Net per dollar bought falls** where Sharpe falls: selection 44 bp to about 34 bp (S3); 2022-23 58 bp to about 46 bp.

## Checks
- **Gate (passed).** S0 through this code reproduces R2-08 exactly: the same 1,568 (main) and 744 (2022-23) trades at
  the same prices, the every-minute panel with 0 armed-state differences over 30 million coin-minutes, and the best
  estimate 2.935 / 2.661 / 1.913 Sharpe, 22.79% / 19.05% / 11.14% a year. Largest daily difference from R2-08's
  committed cells: 1e-17.
- **Exactness (passed).** 200 random decision minutes per era (600 in all). At each, the bot's own arrays were built
  (11 days, close filled forward, volume 0 when missing, BTC's last one or two minutes dropped) and the unmodified
  edge.wick.panel was run on them. Level, sigma and all 23 features agreed with the vectorised values. Largest
  relative difference on a BTC-dependent value about 5e-12; largest anywhere 6e-8 (one float32 step of a coin-only
  feature, from the bot's 11-day window). Also passed for S4 seed 1 (150 minutes, largest relative 3e-12).
- **Offline test** of the transform: scripts/owner/late_btc/test_late.py (made-up closes; the transform equals a
  brute-force forward fill, and the vectorised values equal wick.panel on the brute-force arrays to 1e-14).

## Limits (from the prereg)
- The 70 / 30 mix comes from one runner location over two hours. The paper books' own counters (release 2) will show
  the real share. Until then the mix is an assumption.
- A row that stayed wrong in the bot's table was often a partial candle, not a missing one. S4 models it as missing,
  which is a rough stand-in.
- ETH and the other coins also had late or unfinished candles. Not modelled here.
- The simulator's fills come from candles, as in the research.
- Added here: each era is one price path, and a few-bp level change reshuffles which dips fill. The seed ranges show
  that noise; the paired intervals show it too.

## Deviations and clarifications (each written before the work it covers)
1. **Nov 10 2026, 14:11 ET. Branch setup.** The brief's `git merge origin/main` into owner/late-btc (cut from
   owner/timing) conflicted in reports/crypto-edge-findings.md and reports/owner/timing/README.md. The merge was
   aborted, not forced. Only the two files this replay needs were taken from origin/main: the prereg
   (reports/owner/late_btc_prereg.md, unedited) and the runner workflow .github/workflows/hunt2.yml (not on
   owner/timing). Nothing else on the branch changed.
2. **Nov 10 2026, 14:11 ET. A missing BTC minute also has volume 0.** The prereg speaks of BTC's closes. The bot
   (bot/spot/engine.py `arrays`) fills a missing minute's close forward and sets its volume to 0. This replay copies
   the bot, so a missing BTC minute changes one more feature, btc_volume_ratio_15m (BTC's last 15 minutes of volume
   against its 3-day average), as well as the close-based ones. Coins' own candles stay true.
3. **Nov 10 2026, 14:11 ET. The models are fitted by the wick lab's own walk-forward.** The prereg names the signal
   lab's pipeline. Its model step (model.py `wf`) drops two training rows that have no label (BCH and XLM, Mar 4
   2023), which the original R2-08 kept, so in 2022-23 it differs from the frozen book from 2023Q2 (documented in
   reports/signal_lab/README.md, "Checks"). The gate asks for the frozen book. So the models here are fitted exactly as
   scripts/lab/core.py `walk_forward` fits R2-08 (the same code path, kept models), and everything else is the signal
   lab's pipeline (levels, candidates, features, threshold, every-minute panel, deep paths) and the frozen
   engine-faithful simulator. The gate checks that this reproduces the frozen R2-08.
4. **Nov 10 2026, 14:11 ET. Definitions the prereg leaves open** (fixed before any run):
   - Seeds: S3 seed s draws each decision minute's lag (1 with probability 0.7, else 2) from
     numpy default_rng(100 + s); S4 seed s uses the same lags and drops each older BTC minute with probability 0.3
     from default_rng(200 + s), once over the whole era. s = 1 .. 5. The exactness check draws its minutes from
     default_rng(7).
   - A dropped older minute (S4) is filled as the bot fills: forward from the last candle it has, volume 0.
   - Counts of first-bid fills and rungs (measure 2) are from the replay's minute bound (the slower of its two latency
     bounds); P&L, Sharpe and returns are the replay's usual blend of the two bounds. Mean net per dollar bought =
     blended P&L / blended dollars filled. Worst day = the lowest blended daily return.
   - Measure 3 is read on the decisions: an "armed" minute is a coin and minute where the model approves a 4-sigma
     bid (prediction above the quarter's threshold). Shares are over all coin-minutes of the era. The level difference
     is |scenario level / S0 level - 1| in bp at the scenario's armed minutes, both levels as posted (tick-rounded).
     The same shares are also given for first-bid fills of the replay (information).
   - Measure 4: daily return difference against S0 (blended, print-priced exits); stationary bootstrap, mean block 7
     days, 5,000 draws, default_rng(11), 90% interval of the mean. For S3 and S4 the series is the mean of the five
     seeds' daily returns; each seed's own interval is in the CSV.
   - Primary pricing is the best estimate's: engine-faithful cash rule plus print-measured exit costs, S*, theta 0.5,
     $250K. The model-priced exits are kept in the CSVs as information.
5. **Nov 10 2026, 14:20 ET. Trade-list parity to rounding.** A shakedown run (2022-23, S0 only) reproduced R2-08's
   744 trades, prices, every-minute panel (0 of 13.7 million armed states differ) and best estimate (1.913, 11.14% a
   year; largest daily difference from R2-08's cell 2e-15). The script's own trade check had asked for predictions
   equal to the last bit and saw 9e-14 bp (LightGBM summing the same trees over a different batch of rows), so it
   stopped. The check now allows 1e-9 bp. No scenario other than S0 had been computed.

## How to reproduce
- Runs: `python scripts/owner/late_btc/replay.py <main|early> --exact 200 --exact4 50 --job full` on the hunt2 runner
  (workflow_dispatch on branch owner/late-btc, commit = reports/owner/late_btc/runs). Each job builds R2-08, fits the
  models, runs S0 and the gate, the exactness check, then S1, S2, S3s1-5, S4s1-5. It stops if a check fails.
  Run ids: 42884373432 (main: selection and check), 42884378600 (2022-23); about 40 and 16 minutes.
- Tables: `python scripts/owner/late_btc/summarize.py reports/owner/late_btc/runs/main_full
  reports/owner/late_btc/runs/early_full` writes table.csv, results.csv, paired.csv.
- Test: `python scripts/owner/late_btc/test_late.py`.
- Committed outputs are derived tables only (daily returns, counts, checks). No trade prints.
