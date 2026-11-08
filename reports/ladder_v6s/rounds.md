# Ladder v6 sizing: rounds (selection era only)

Each round's hypothesis is written here before the round runs; times are the commit times of each entry. Every run is
a row of variants.csv (selection-era statistics, S* θ 0.5 unless noted, both the ADV-capped and uncapped versions,
with the best-5-days-removed figures). Plan: reports/ladder_v6s_prereg.md.

## Round 1: headroom (written before running)
Hypothesis:
- The AI's prediction μ̂ ranks per-dollar outcomes: C2a's top tercile earned far more per dollar. The coin's daily
  volatility σ̂ ranks their dispersion.
- So Kelly, f = μ̂ / σ̂², should rank risk-adjusted outcomes better than μ̂ alone.

Predictions:
- The hindsight oracle (×2 / ×0.5, ADV-capped) gives a selection Sharpe-path t above 5.
- Z1 Kelly and Z3 edge clear the drop bar (t 1.4) at some λ. Z2 inverse variance ignores edge, and Z4 breadth
  shrinks the most profitable cascades, so neither does.
- Under the ADV cap at S*, upsizing is possible only in ETH, SOL, XRP, NEAR and ZEC, so capped results are weaker
  than uncapped.
- The edge family's t falls the most when the best 5 days are removed, because C2a's gain sat on a few days.

Runs:
- Diagnostics (quintiles of μ̂, σ̂, f and breadth against realized net per dollar of the incumbent's signals).
- The oracle, capped and uncapped.
- Each family at λ 0.25 / 0.5 / 1, capped and uncapped (24 runs).
