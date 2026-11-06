# Wick catcher at $1M — pre-registration

Committed 2026-11-06 before any of the tests below were run. Deviations go in the log at the bottom.

## Goal (Miles, Nov 6)

Get the wick catcher (strategy of record R2-08: AI-filtered post-only dip bids 4 residual sigmas below fair value,
take-profit at 60% of the dislocation, 60-minute time exit) to work with $1M of capital, on venues open to a New York
resident.

**Bar ("works"):** in the check period, at $1M with capture θ = 0.5: Sharpe ≥ 2.0, net return ≥ 25% a year,
max drawdown no worse than −20%; and still profitable at θ = 0.25.

## Starting point (scale round, reports/wick_capacity.csv)

- At $1M the current rules lose 7–10% a year; capping each trade near $50K caps profit near $50K a year.
- Diagnosis (descriptive, from reports/wick_capacity_trades.parquet): the trades with the most volume traded through
  our level are the losers. By quintile of through-volume, mean gross is +77, +84, +44, +42 and −5 bp. At size the book
  fills fully in sustained selloffs and only partly in quick wicks: adverse selection by size.

## Periods

- Selection: 2025-01-01 – 2026-03-31. Check: 2026-04-01 – 2026-11-05, opened once at the end (the wick lab's split).
- Secondary, reported only: the 2022–2023 fresh era (spot only, 13 coins), R2-08 rerun with LAB_ERA=early.

## Capacity model (scripts/wick_capacity.py; unchanged unless listed)

- Entry: a bid can buy θ × the volume that traded below its level while the price stayed there (≤ 15 minutes), each
  1-minute candle's volume spread evenly over its range; Coinbase spot and perp books both count.
- Take-profit: fills up to θ × the volume above the exit price before the exit.
- Market sales pay half-spread + 0.7 × daily vol × √(size / daily volume).
- Fees: the cheaper of the lab's realistic perp cost and Coinbase spot at the volume tier the book itself reaches.
- θ ∈ {0.25, 0.5}; capital $1M (curve also reported for $100K – $2M).

## Phase 1 levers (existing data: 17 coins)

- **A. Size cap per trade:** κ × the coin's trailing 30-day median daily volume (spot + perp, known at the time),
  κ ∈ {none, 0.10%, 0.05%, 0.025%}; the base size stays 25% of capital.
- **B. Depth ladder:** none, or the trade's size split in thirds at 4σ (the R2-08 level), 6σ and 8σ below fair value.
  Deeper bids rest while the first tranche is open. Each tranche has its own take-profit (60% of its own dislocation)
  and its own 60-minute time exit.
- **C. Exits:** E0 = market at 60 minutes (current). E1 / E2 = take-profit as now; any remainder is sold at 10% / 25%
  of each minute's combined spot + perp volume at the minute's typical price (high + low + close)/3 minus half-spread,
  for up to 240 minutes; anything left is sold at market with impact.
- **D. Trade list:** as the bot trades (6 slots × 25% of capital), or every AI-approved signal (no slot cap; gross
  capped at 300% of capital; each trade sized by A).
- Grid 4 × 2 × 3 × 2 = 48. Pick the best by selection-period Sharpe at $1M, θ = 0.5 (ties: higher dollars a year).

## Phase 2 levers (new data, fetched by GitHub Actions)

- **E. Universe:** add the Coinbase spot coins with a 2024 median daily Coinbase volume ≥ $3M (chosen on 2024 data
  only) and a spot tick ≤ 3 bp: ADA, AVAX and 19 not yet downloaded (BONK, SHIB, FET, JASMY, INJ, SEI, TIA, ICP, STX,
  AERO, OP, DOT, ARB, JTO, UNI, LDO, APT, FIL, GRT). At $1M the book trades on spot, where it reaches Coinbase's
  0%-maker tier, so a perp is no longer needed. R2-08's pipeline (levels, features, walk-forward AI with R2-08's
  settings) is re-run on the wider universe, with the AI's cost label set to the $1M spot tier (0% maker, 3.5 bp
  taker, plus the measured half-spread on market exits) for every coin.
- **F. Venue:** Bitstamp (New York BitLicense since 2019) 1-minute volume added to entry and exit capacity for the
  coins it lists.
- The Phase 1 execution rule is applied unchanged to the Phase 2 trade list (no re-selection).

## Reporting

For the chosen rule, Phase 1 and Phase 1 + 2: return, Sharpe, max drawdown and dollars a year at $1M (θ = 0.5 and
0.25), the capacity curve $100K – $2M, the check period, the 2022–23 fresh era, and correlation with C3.

## Deviation log

(none yet)
