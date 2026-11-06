# Wick catcher v3: refinements tested on fresh data (pre-registration)

Written 2026-11-06 ~12:45 ET. The 2021–2023 minute data was being fetched while this was written; none of it
had been loaded. No wick research has ever used data before 2024-01-01.

## Why a fresh era
- Every 2024–2026 minute has now shaped a choice: v1's design (2024), lab selection (2025 – Mar 2026), and the
  check period (Apr – Nov 2026), opened once. Any further tuning on that data is curve-fitting.
- 2021–2023 is untouched, and it contains the regimes this strategy should love or fear: the May 2021 crash,
  the Luna collapse (May 2022), FTX (Nov 2022) and the 2023 recovery.

## Fresh-era set-up (identical code: scripts/lab, era "early")
- **Data:** Coinbase spot 1-minute candles 2021-01-01 → 2023-12-31 for BTC, ETH and the 17-coin universe
  members that traded then: SOL, DOGE, LTC, LINK, BCH, XLM, AAVE, ZEC, NEAR, HBAR, XRP (from Jul 2023), SUI
  (from May 2023). HYPE, ENA, PEPE and ONDO did not exist.
- **Walk-forward:** the first model is trained on 2021 only. Test quarters run 2022Q1 → 2023Q4 with quarterly
  retraining and a 1-day embargo, as in the lab.
- **Costs ("realistic at today's prices"):**
  - Each coin's fee per side is held at today's $0.20-per-contract level in bp (reports/lab/cost_table.csv).
    Old prices with today's contract sizes would turn the fee into an artifact.
  - 1.5x today's measured half-spread on market exits.
  - 1 bp funding per trade.
  - The same cost model labels the AI.
- **Perps:** none existed, so fills are spot-priced only. Expect results to read high, as in 2025–26
  (perp-priced was about two-thirds of spot-priced there).

## Variants (fixed now, 14)
- Incumbents: V000 v1, R2-08 (current strategy of record).
- Earlier finalists: R2-07, R2-20, R2-03.
- Round-3 refinements of R2-08, motivated by the robust round-1/2 finding (pickier wins once costs are real) and by
  how the bot actually trades:
  - R3-01 threshold 65th percentile
  - R3-02 threshold 70th percentile
  - R3-03 threshold 75th percentile
  - R3-04 60th percentile and predicted net > 0 bp
  - R3-05 prediction-priority slots (the live bot already does this)
  - R3-06 8 slots of $1,875 (same gross)
  - R3-07 trend-regime features: BTC's distance from its 100-day average, and its 30-day return
  - R3-08 size by perp liquidity (sqrt rule, clipped 0.5–1.5x)
  - R3-09 10 LightGBM seeds instead of 3

## Scoring and adoption
- Primary score: fresh-era (2022–2023) realistic Sharpe and the paired t of daily differences against R2-08.
- Also reported for each variant: its 2025–2026 realistic Sharpe (seen data) and each calendar year 2022 and 2023.
- **v1 vs R2-08 re-check:** if v1 beats R2-08 in the fresh era (paired t > 1), the switch is reversed.
- **A round-3 refinement replaces R2-08 only if all of these hold:**
  - Fresh-era paired t vs R2-08 ≥ 2.0.
  - It beats R2-08 in both 2022 and 2023.
  - It is not worse than R2-08 on 2025–2026 (paired t > −1).
  - The bot can do it with changes already in train_v2 / engine, or with a small parity-tested change.
- Nothing else is tried on the fresh era. Its results are reported whatever they show.
