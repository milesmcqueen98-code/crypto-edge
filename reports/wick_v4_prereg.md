# Wick catcher v4: rung weights, sub-minute execution, capacity, venue (pre-registration)

Written 2026-11-06 ~19:30 ET, before any of the tests below were run. Deviations go in the log at the bottom.

## Goal (Miles, Nov 6)
A better Sharpe than the current spot bot (bot/spot: R2-08 signal, $1M rules: 0.2% ADV cap, 4/6/8σ ladder in equal
thirds, every AI signal, cash ≤ 100%), able to take more capital, without overfitting. Also answer three questions:
- Is Coinbase the best venue?
- Does acting on the second (or every 5 seconds) improve results?
- Is that testable?

## What has been looked at already (honest accounting)
- Every era has shaped a choice:
  - 2024: v1 design.
  - Jan 2025 – Mar 2026: selection.
  - Apr – Nov 2026: the check period, opened in the v2 lab and in wick1m.
  - 2022–2023: fresh era, opened in v3 and wick1m.
- Per-rung results by period were already seen for selection and check: 33/34/73 bp and 33/35/113 bp net per $ at
  4/6/8σ. They motivate candidate W1–W4 below, so selection and check are **not** independent evidence for rung
  weights.
- The per-rung split of the 2022–23 fresh era (pre_early) has **not** been looked at. It is the confirmation set for
  rung weights.
- The production models are already trained through Nov 5, 2026, so retraining is not a candidate.

## Candidates (fixed now)
**Rung weights** (mechanism: per-dollar edge rises with the depth of the dislocation; a smaller 4σ rung also holds less
cash in resting bids, so more coins can be armed at once):
- W0 (incumbent): 4/6/8σ at 1/3 each.
- W1: weights ∝ depth, 4/6/8σ at 2/9, 3/9, 4/9.
- W2: 4/6/8σ at 1/4, 1/4, 1/2.
- W3: add a 10σ rung, 4/6/8/10σ at 1/4 each.
- W4: W3 weighted ∝ depth: 4/6/8/10σ at 4/28, 6/28, 8/28, 10/28.
- The total per signal stays S = min(25% of equity, 0.2% of ADV). The 10σ rung uses the same frozen fair value and
  the same cancel rule as the 6/8σ rungs.

**Sub-minute execution** (testable only with trade-by-trade data; fetched from Coinbase's public trades endpoint by
GitHub Actions; raw trades go to a workflow artifact, never committed):
- S1, latency: what share of the simulator's same-minute deeper fills happen at least 1 / 5 / 15 / 60 seconds after
  the 4σ fill? This decides how many the live bot's 5-second poll recovers. It is a measurement, not a parameter
  choice.
- S2, BTC-synchronised level: re-price the 4σ bid every 5 seconds using BTC's live price instead of the last
  minute's close, so systematic (BTC-driven) moves don't fill it.
  - The mechanism cuts both ways: BTC-driven cascades also revert.
  - Step 1 (minute-candle proxy, all eras): net per $ of parent fills by BTC's same-minute move.
  - Step 2 (trades, a sample of parent fills): re-simulate each fill minute with the 5-second level.

**Capacity:**
- U1: the wide universe (31 coins) at $250K, $500K and $1M.
- Already known: at $1M it was worse than 17 coins in the check period (9.2% vs 10.0%). It stays a candidate only if
  it is better at $500K in both selection and check.

**Venue:** web research on venues open to a New York resident:
- fees at the book's volume;
- coverage of the 17 coins;
- volume (wick capacity);
- API order types (post-only, good-til-date).

Bitstamp was already tested (no help at the book's fee tier).

## Simulator and settings
- scripts/wick1m/sim.py (v2 after the review), bot-like: deeper fills in the parent's own minute dropped, unless S1
  shows the 5-second poll recovers them.
- θ = 0.5 (also reported at 0.25), VIP-1 fees, gross ≤ 100%.
- Capital $250K (primary), $500K and $1M (capacity).

## Adoption rules
Rung weights: pick the best of W1–W4 by selection-period Sharpe at $250K, θ = 0.5. It replaces W0 only if all hold:
1. Selection Sharpe ≥ W0 + 0.15.
2. Fresh era 2022–23 (unseen per-rung data): Sharpe ≥ W0, and paired daily t vs W0 > 0.
3. Check period: paired daily t vs W0 > −1. It may not be worse in a meaningful way.
4. At $1M it is not worse than W0 in selection or check (dollars a year).
5. Stability: the neighbouring weights (the other W's) mostly agree in sign vs W0 in the fresh era. This guards against
   a lone spike.

S2: adopt only if the trade-data sample shows a higher mean net per $ than the incumbent rule on the same events
(paired t ≥ 2) and the minute proxy points the same way in all three eras.

S1: no adoption decision; it sets the expected value of the 5-second poll and decides whether the bot-like numbers are
too pessimistic.

U1: adopt only if better at $500K in both selection and check (Sharpe and dollars).

## Scorecard (asked for: score the final model out of 20)
| Criterion | Points | Full marks means |
|---|---|---|
| Out-of-sample edge | 4 | Sharpe ≥ 2 after costs in every era tested (2022–23, 2025–26 selection, 2026 check), all positive |
| Robustness / no overfitting | 4 | Few trials, mechanism-first; plateaus not spikes; consistent across eras; deflated Sharpe ≥ 0.95 |
| Realism of the simulation | 4 | Fills, capacity, fees and latency validated against data finer than 1-minute candles or against live fills |
| Capacity | 2 | Sharpe ≥ 2 at $1M in every era |
| Implementation and risk | 3 | Parity-tested bot, fault-tolerant live path, kill switches, monitoring |
| Live validation | 3 | A forward paper and live record consistent with the backtest |

## Deviation log
(empty)
