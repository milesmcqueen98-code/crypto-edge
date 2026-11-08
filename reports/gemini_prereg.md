# Gemini venue test: pre-registration (Nov 8, 2026)

Question (Miles): is Gemini, a thinner New York-licensed spot venue, a better or additional place for the R2-08
spot ladder than Coinbase? Measure (1) ≥4σ dislocations that happen on Gemini only, (2) the dollars that trade
through the bids, (3) the rebound, with the frozen R2-08 ladder and a Coinbase-synchronous fair value.
Written before any Gemini data was downloaded. Nothing here was tuned; every rule is the incumbent's or is fixed
below. "No change" is a valid answer.

## Data
- **Why a sample of days.** Gemini's public API keeps only seven days of trades. The free history with prints on
  both venues is Tardis.dev's first-day-of-month CSVs.
- **Sample.** The first UTC day of every month, 2024-01-01 to 2026-11-01: 35 days.
  - AI-filtered results use the R2-08 out-of-sample days only, 2025-01-01 to 2026-11-01 (23 days).
  - 2024 days count unfiltered dislocations only (2024 trains the first model).
- **Gemini.** Every trade (price, size, taker side, exchange timestamp) and top of book reduced to the last bid/ask of
  each second, for the 17 R2-08 coins that Tardis lists as Gemini USD pairs that day.
- **Coinbase.** Every trade of the same coins, reduced to per-second bars (last, low, high, USD volume, taker-sell and
  taker-buy USD).
- **Ticks.** Gemini's current quote increments (symbol details); history may have had other ticks.
- Fetch: scripts/gemini/fetch_tardis.py on Actions (hunt.yml); raw data stays in artifacts.

## Frozen rules (the incumbent's, mapped to Gemini)
- **Levels.** R2-08 (scripts/lab, variant R2-08: L 60, 3-day σ of the BTC-residual, 7-day β), rungs at 4, 6 and
  8σ below the BTC-adjusted fair value, computed from Coinbase 1-minute data known at t−1 and fixed through
  minute t.
- **AI.** R2-08's walk-forward LightGBM (label net_real, threshold at the 60th percentile of training predictions,
  seeds 7/11/23, quarterly retraining, trained on Coinbase candidates only), scored at every minute of the
  out-of-sample sample days with the same features. A coin is armed in minute t when pred > thr.
  - Parity check before use: the reproduced predictions must match the stored R2-08 trades (reports/wick1m/
    trades_main.parquet, pred and thr) on the bot's trades.
- **Coinbase-synchronous mapping.** Gemini bid = Coinbase-model level × r, floored to Gemini's tick, where r is the
  median Gemini/Coinbase price ratio of Gemini prints in the 240 minutes before t (each print against Coinbase's
  last price at or before its second); at least 3 prints, else r = 1.
- **Parent fill (4σ).** The first Gemini print in minute t at or below the Gemini bid minus one tick while the coin is
  armed (unfiltered counts: armed or not). One ladder per coin at a time; a new ladder only after the 4σ rung closes.
- **Deeper rungs (6σ, 8σ).** Placed 1 second after the parent fill (the live bot's 1-second fill check) at the
  parent minute's levels; they rest until the parent's take-profit trades or 60 minutes pass, and fill on the first
  print at or below their bid minus one tick.
- **Through-volume (the size we could get).** USD of Gemini taker-sell prints at or below the bid minus one tick, from
  the fill print until a print at or above the bid, at most 15 minutes; rungs of one parent share the parent's
  sellers. All-prints volume reported as an upper bound. We get θ = 0.5 of it (0.25 sensitivity).
- **Exits.** Take-profit at 60% of each rung's dislocation (bid × e^{0.6kσ}), filled on the first print one tick
  through it within 60 minutes, capacity = taker-buy USD through it (shared within the parent); the rest sold at
  Gemini's best bid at minute 60 (half-spread included), taker fee.
- **Size.** $250K book: each signal min(25% of capital, 0.2% of the coin's Gemini USD volume that day) split in thirds,
  then capped by θ × through-volume. (The day's own volume is a proxy for the 30-day median; noted as a bias.)
- **Fees.** Gemini ActiveTrader schedule (Sep 1 2026 page), tier from the sleeve's own 30-day volume:
  $0 60/120 bp, $10K 40/80, $25K 25/50, $75K 12.5/25, $250K 7.5/15, $500K 6/12.5, $1M 5/10 (maker/taker).
  Also reported at Coinbase's VIP 1 (6/12.5 bp) as if the book's combined volume set the tier.

## Measurements
1. **Gemini-only vs shared.** A Gemini 4σ parent fill at time τ is *shared* if Coinbase traded at or below its own
   4σ level (minus one Coinbase tick) within τ ± 60 s; otherwise *Gemini-only*.
2. **Pure synchronous dislocations (no AI, no level).** Gemini prints at or below r × Coinbase's last price at that
   second × e^{−kσ}, k = 4, 6, 8; prints within 60 s merged into one episode.
3. **Dollars.** Through-volume per fill, per day and per year (× 365 / sample days), at θ 0.5.
4. **Rebound.** For each rung fill, markouts against the Coinbase-synchronous fair value and Gemini's mid at +1 s,
   +10 s, +1 min, +5 min, +60 min; take-profit hit rate; realized gross and net per dollar.
5. **Comparison.** The incumbent's Coinbase fills on the same sample days from the frozen ladder dataset
   (scripts/ladder_v5/fsim.py), same $250K book: fills, dollars, gross and net per dollar.
- Uncertainty: 90% intervals by resampling days.

## Verdict bar
Gemini is worth adding as a second venue only if the AI-filtered Gemini ladder (shared and Gemini-only together)
earns at least **+$5,000 a year net at $250K** at Gemini's own fee tier, with positive mean net per dollar and a
day-bootstrap 90% lower bound above zero. "More profitable than Coinbase" means a higher net per dollar *and* more
dollars a year than the incumbent's Coinbase fills on the same days.

## Known limits (stated before the data)
- 23 out-of-sample days are about 7% of the period. Crash days (Oct 10 2025, Feb 3 2025) are not in the sample, so
  shared-cascade capacity is understated; ordinary-day, Gemini-only events are what the sample measures well.
- Queue position on Gemini is unknown; θ covers it as in the research.
