# What a late BTC input costs (replay of reports/owner/late_btc_prereg.md)

(Results go here once the runs are read. Until then this file holds only the deviation log, written before the work it
covers.)

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
