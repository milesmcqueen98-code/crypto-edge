# Wick catcher v4: rung weights, sub-minute execution, capacity, venue (pre-registration)

Written 2026-11-06 ~19:00 ET (commit 2b5d046), before any of the tests below were run. Deviations go in the log at the bottom.

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
1. The trade-by-trade analysis ran on GitHub Actions (`subminute-analysis` workflow) instead of locally. This
   environment can't download workflow artifacts (they're served from blocked storage). Only derived per-event results
   were committed (reports/wick_v4/subminute_*.csv, subminute_log.txt), plus the per-event research inputs it needed
   (events_research.csv). Logged before results.
2. U1 used the corrected 31-coin precompute (pre_wide.pkl, simulator v2) with Bitstamp switched off. The older
   pre_wide_nobs.pkl predates the simulator review.
3. Added after the results, as a forward test only (not an adoption): W2 runs as a second paper book (paper_spot_w2).
   It failed the rule below but looked better post hoc, so forward data will decide it.

## Results (2026-11-07 ~00:30 UTC)
**Rung weights: none adopted.** $250K, θ 0.5, bot-like; Sharpe in selection / check / 2022–23 (reports/wick_v4/rungs.csv):

| Candidate | Selection | Check | 2022–23 | Paired t vs W0 (sel / check / 22–23) |
|---|---|---|---|---|
| W0 thirds | 2.37 | 3.10 | 2.02 | — |
| W1 ∝ depth | 2.45 | 3.21 | 2.21 | −0.4 / −0.9 / +0.9 |
| W2 ¼ ¼ ½ | 2.49 | 3.19 | 2.22 | +0.1 / −0.1 / +1.0 |
| W3 + 10σ equal | 2.60 | 3.01 | 2.28 | +0.2 / +0.4 / +0.1 |
| W4 + 10σ ∝ depth | 2.62 | 2.89 | 2.28 | −0.1 / −0.1 / −0.0 |

The selection pick was W4. It fails rule 2: its 2022–23 return equals W0's (paired t −0.005). Every difference is
within noise.

**S2, BTC-synchronised level: not adopted** (fails step 1).
- Correlation of BTC's move in the fill minute with the parent fill's gross outcome: +0.06 / +0.02 / −0.01 in the
  three eras.
- Fills during the biggest BTC drops did as well as typical fills (50 / 37 / 51 bp gross).
- Post-hoc lead, not a rule: in all three eras the worst fills came when BTC was flat during the fill minute (26 / 5
  / 22 bp). The trade data agrees: by BTC's move up to our fill, the flat quintile made 37 bp against 52–63 for the
  others. Coin-specific selling reverts less. It is a forward-test candidate only.

**S1, latency (4.3M trades, 2,618 windows).**
- The trade data shows a trade-through for 98.4% of the simulator's parent fills.
- Of the 236 same-minute deeper fills, the share still caught when reacting L seconds after the 4σ trade-through:

| Reaction time | 0.5 s | 1 s | 2 s | 5 s | 15 s | 30 s | 60 s |
|---|---|---|---|---|---|---|---|
| Rest (post-only) | 89% | 87% | 84% | 74% | 42% | 17% | 0% |
| Cross if passed (taker) | 90% | 89% | 89% | 86% | 65% | 37% | 0% |

- The median time from the 4σ trade-through to the deeper one is 9.1 s (interquartile 3.4–19.2 s).
- Value at $250K, θ 0.5 (reports/wick_v4/latency_value.csv). Return / Sharpe:

| Detection | Selection | Check | 2022–23 |
|---|---|---|---|
| Once a minute (paper) | 27.6% / 2.37 | 19.6% / 3.10 | 12.2% / 2.02 |
| 5-second poll | 29.2% / 2.27 | 20.2% / 2.90 | 13.7% / 2.22 |
| 1-second detection | 29.8% / 2.27 | 21.5% / 3.06 | 14.0% / 2.28 |
| Instant (simulator ceiling) | 31.8% / 2.38 | 22.7% / 3.23 | 14.2% / 2.29 |

- 1-second detection gains about 2 points a year of return. Sharpe is about flat: −0.10 / −0.04 / +0.26 (paired
  daily t of returns 1.1 / 1.2 / 3.4).
- **Implemented:** the live bot finds 4σ fills from the account's fill list every second (one request), and retries
  deferred deeper rungs every second.
- At θ 0.25 with 1-second detection: 2.15 / 2.82 / 2.02.

**S3, fast take-profit: not worth it.** The take-profit trades within the fill minute for 4.5% of parent fills, and
almost all of those also hit it in the simulator. The gain is under 1 bp per fill.

**U1, 31 coins: not adopted** (reports/wick_v4/universe.csv). It is worse in the check period at every size (Sharpe at
$500K 2.19 vs 2.67; at $1M 1.32 vs 1.73), and better in selection only at $1M and $2M.

**Venue: Coinbase stays.**
- Gemini (New York licensed) has the same fee schedule tier for tier, 0.06% / 0.125% at $500K, but far less volume in
  these alts.
- Bitstamp was tested in wick1m: it adds 0–23% of Coinbase's volume per coin, and its fees at the book's volume eat the
  edge.
- Kraken and Crypto.com don't serve New York.
- Robinhood routes orders rather than running a public order book.
- Wick capacity is volume through our price, and Coinbase has the most US spot volume. The signal was also fitted on
  Coinbase's own candles.
