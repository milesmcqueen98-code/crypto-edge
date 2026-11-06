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

**Implementation notes (fixed before any lever was evaluated).**
1. Trade lists come from the wick lab's own pipeline (scripts/wick1m/trades.py imports scripts/lab unchanged): 1,568
   AI-approved R2-08 trades in 2025–26, of which the bot's portfolio rule keeps 1,264 (identical to
   reports/lab/futures_trades.parquet). Bids all day (no quiet window), as in the scale round. Fresh era: 744 / 691.
2. Deeper tranches: levels from the fair value and sigma at the first fill, fixed while they rest (60 minutes); a
   tranche fills in the first minute whose spot low trades through it by a tick, at its level; it then has its own
   take-profit and 60-minute window.
3. Take-profit orders rest for 60 minutes; capacity = θ × USD volume above the take-profit price on all venues in the
   60 minutes after the fill minute.
4. Participation exits pay the taker fee, half-spread and square-root impact on the amount they sell; anything left
   after 240 minutes is sold at market with impact.
5. Bitstamp fees: 2 bp maker / 5 bp taker once the book trades ≥ $10M a month (published range 0.00–0.30% maker,
   0.03–0.40% taker); below that, Coinbase's schedule as a proxy.
6. Uncapped list: each tranche's fill counts against the 300% gross cap for 60 minutes (plus 240 for participation
   exits); a trade is skipped when less than 10% of its size fits.
7. Fee tier, gross cap and statistics are computed inside each period separately. P&L is booked on the fill day.
8. Check-period statistics are computed only with WICK1M_CHECK=1.

**Deviation 1 (before the check period): gross ≤ 100% of capital.** The registered grid allowed 300% gross for the
uncapped list. But 97% of the entry capacity is Coinbase spot volume, and US spot accounts have no margin, so spot
positions need cash. The first grid peaked at 264% gross (Oct 10 2025 crash). The grid was re-run with gross ≤ 100%
for both trade lists. Under that limit the participation exits rank below the market exit, because they hold capital
for up to 5 hours.

**Deviation 2 (before the check period): two more size caps.** The best cap was the largest in the grid (10 bp of
daily volume, i.e. 0.1%), so 20 bp and 40 bp were added, with the same ladder / exit / list options.

**Phase 1 selection (selection period only, $1M, θ = 0.5, gross ≤ 100%).** Best by Sharpe: size cap 20 bp of the
coin's daily volume, ladder at 4/6/8σ, market exit at 60 minutes, every AI-approved signal. Selection period: 21.6% a
year, Sharpe 2.75, max drawdown −3.8%, $216K a year; at θ = 0.25: 18.5%, Sharpe 2.41. Baseline (current rules):
−7.7%, Sharpe −0.83. This rule is now fixed for Phase 2 and the check period. Grid files:
reports/wick1m/grid_main_1000k_g1.csv (the 300%-gross first pass: grid_main_1000k.csv).

**Deviation 3 (Phase 2, before it ran): spot details.**
- The AI's cost label uses the tier the $1M book actually reaches in Phase 1: Coinbase VIP 1, 6 bp maker and 12.5 bp
  taker, plus a 2 bp half-spread on market exits, no funding. The registered 0% maker / 3.5 bp taker assumed a tier
  ($50M a month) the book doesn't reach.
- Every coin uses its spot tick for fills and level rounding, estimated from its minute prices (the smallest step in
  H2 2024). The $1M book trades spot, so the lab's coarser perp ticks no longer apply.
- Phase 2 runs on GitHub Actions (scripts/wick1m/trades_wide.py, .github/workflows/wick1m.yml), because it needs
  about 10 GB of memory.

**Check period opened once (2026-11-06, after commit 4b0d8d2).** Results: reports/wick1m/report.csv, curve.csv,
monthly.csv. At $1M, θ = 0.5, check period Apr – Nov 2026:

| Book | Return/yr | Sharpe | Max DD | $/yr | θ = 0.25 |
|---|---|---|---|---|---|
| Current rules, 17 coins | −18.1% | −2.32 | −11.0% | −$181K | −19.2% |
| $1M rule, 17 coins | 12.4% | 2.28 | −0.7% | $124K | 10.6% |
| + Bitstamp | 13.9% | 2.46 | −0.7% | $139K | 12.0% |
| + wider universe (35 coins) + Bitstamp | 16.3% | 2.89 | −0.7% | $163K | 14.3% |

Verdict against the bar: Sharpe ≥ 2.0 passes (2.89), drawdown passes, θ = 0.25 stays profitable, but the return
fails: 16.3% vs 25%. **Not "works" by the registered bar.** The 2022–23 fresh era (spot only, 13 coins): 7.5% a year,
Sharpe 1.38 (current rules −8.2%). Dollar profit stops growing near $1M: in the check period $163K at $1M, $187K at
$2M, $191K at $5M. Returns are 23–26% a year at $100K–$500K. Correlation with C3: 0.06.
