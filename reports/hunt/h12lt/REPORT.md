# H12 (LT): R2-08's wick catcher on Coinbase's long-tail spot coins

Builder h12lt, 2026-11-07, branch hunt/h12lt. Path B.
- **Freeze commit:** 8c728e6 (frozen.json; code 235025e).
- **Verdict: FAILS G1, G2, G3 and G4 (provisional); passes G5.** The sleeve makes money at 2× costs but adds little
  the incumbent doesn't already earn, and it leans on optimistic fill assumptions.

## Mechanism
The incumbent's own: forced and impatient sellers sweep thin books, and a resting, AI-filtered bid 4/6/8σ below fair
value is paid by the snap-back. New here: coins below the wide set's $3M volume floor, where a fund cannot fit but a
$30K sleeve can.

## Data
**Universe** (universe.py; fixed from 2024 data and committed before any simulation):
- Exchange /products lists 496 USD pairs (91 now delisted); 286 traded in 2024.
- **Volume screen:** 2024 median daily USD volume (close × volume over the pair's 2024 trading days) of $0.5–3M,
  excluding the wide 31 and stable, wrapped or pegged assets. 68 pass, 8 of them delisted now.
- **Tick screen:** est_tick (trades_wide.py rule) ≤ 3 bp keeps 36 and drops 32. The 80-coin cap cut none.
- **Universe:** 36 coins. By 2024 volume: 15 at $0.5–1M, 14 at $1–2M, 7 at $2–3M. Median tick 1.3 bp. Two are
  delisted since: EOS (Dec 2025) and VELO (Nov 2026).

**Candles:** Exchange 1-minute candles, 2024-01-01 → 2026-11-05, for the 36 (24.2M traded minutes; 14 Actions
shards). The wide 31 and BTC come from data/minute.

**Scored days:** gates.ERA_DAYS from 2025-01-01, 674 days (DEV 516, HOLD 158). 2024 only trains the model.

## Signal and execution
- **Signal:** R2-08 "C29+A11" exactly as trades_wide.py runs it.
- **Model pool:** the wide 31 plus the 36 (67 coins, 51,731 candidates). It fit in memory, so the 17-coin fallback
  was not needed. The sleeve trades the 36 only.
- **Coin-by-coin driver (pipeline.py):** calls the lab's own LevelSet, wick.panel, labels and simulate one coin at a
  time, and recomputes the two pool-wide features with wick.panel's formula.
  - **Check:** on the wide 31 alone it reproduces trades_wide.parquet's 2,141 DEV trades exactly (largest prediction
    difference 6e-14; identical thresholds and exits).
- **Execution:** sim.py precompute and evaluate with the incumbent's rules (incumbent.py): ladder 4/6/8σ in thirds;
  κ = 0.2% of trailing 30-day median daily volume (spot; none of the 36 has a perp); every AI signal; cash ≤ 100%;
  spot only; instant bound.
  - **Costs:** 6 bp maker, 12.5 bp taker, 2 bp half-spread on market exits, ×2 for the gates. sim.py's square-root
    exit impact stays at 1×.
  - **Check:** the wrapper reproduces incumbent_daily.parquet's selection-era series exactly.

## Trials (5 logged; DEV; sleeve $30K at 2×; alpha t on the incumbent at $70K)
| Variant | Trades | Sleeve Sharpe | Alpha t | DEV book Sharpe | Net bp | Corr |
|---|---|---|---|---|---|---|
| T1 base | 2,241 | 1.20 | 0.52 | 2.43 | 28 | 0.32 |
| T2 2024 volume ≥ $1M | 1,279 | 0.99 | −0.11 | 2.34 | 26 | 0.41 |
| **T3 AI ≥ 70th pct** | **1,701** | **1.88** | **1.74** | **2.62** | **48** | 0.33 |
| T4 no ladder (4σ only) | 2,102 | 0.28 | −0.11 | 2.17 | 10 | 0.10 |
| T5 κ = 0.1% | 2,302 | 1.42 | 0.78 | 2.48 | 35 | 0.34 |

- The incumbent alone on these days: 2.44.
- T3 re-runs R2-08's per-coin book on the stored predictions at or above each quarter's 70th-percentile training
  prediction, with no retraining.

## Frozen variant
T3_ai70, the highest DEV alpha t with ≥ 100 trades. a = 0.7 was chosen on DEV (book Sharpe 2.62, against 2.54 at
a = 0.5).

## Results at 2× (book = 0.7 × incumbent + 0.3 × sleeve; HOLD read once)
| Window | Alpha t | Book Sharpe | Incumbent Sharpe | Gain | Sleeve Sharpe |
|---|---|---|---|---|---|
| DEV | 1.74 | 2.62 | 2.44 | +0.18 | 1.88 |
| HOLD (325 trades) | 0.50 | 3.76 | 3.64 | +0.12 | 1.72 |
| All scored days | 1.61 | 2.75 | 2.60 | +0.15 | 1.75 |

**Gates:**
- **G1** fail: t 1.61.
- **G2** fail: HOLD t 0.50, gain +0.12.
- **G3** fail: gain +0.15.
- **G4** fail, provisional: DSR 0.41 (N = 3,188, within-idea v_z 1.22); about 0 under the pooled and plain rules.
- **G5** pass: book +33.1% (2025), +15.7% (2026 YTD).

**For information** (no case passes any of G1–G4):

| Case | a | Alpha t (all days) | HOLD t | Gain |
|---|---|---|---|---|
| 1× costs | 0.5 | 1.92 | 0.37 | +0.27 |
| 2×, 5 bp half-spread (10 bp at 2×) | 0.7 | 1.40 | 0.43 | +0.12 |
| 2×, θ = 0.25 | 0.7 | 1.39 | 0.35 | +0.14 |
| 2×, minute bound (no same-minute deeper fills) | 0.7 | 0.90 | −0.04 | +0.05 |

**Sleeve ($30K, 2×):**
- +21.0% in 2025 and +8.3% in 2026 YTD: 15.9% a year, Sharpe 1.75 (2.43 at 1×).
- **The Sharpe falls with size:** 1.32 at $50K and 0.52 at $100K, where the HOLD Sharpe is −1.70.
- **Path A** does not apply: the sleeve on $100K has Sharpe 0.52, against the incumbent's 2.60.

## Capacity filled ($30K, 2×, θ = 0.5)
- **Volume:** $1.77M in 2,970 rung fills (mean $596), 84% of the size wanted on rungs whose level traded; 56% exited
  at the take-profit.
- **Cash:** peaks at 100% of capital at $30K and $50K; the cap binds on cascade days.
- **Net bp:**
  - By rung: 4σ 34, 6σ 66, 8σ 121.
  - By 2024 volume: $0.5–1M 67 ($0.26M filled), $1–2M 50 ($0.98M), $2–3M 40 ($0.53M).
  - By year: 42 in 2025 ($1.48M filled), 87 in 2026 ($0.29M).
- **Coins:** all 36 traded on DEV, 35 in HOLD. Worst COMP −220 bp; best IMX +152.
- **Delisted:** EOS and VELO, 126 fills, +$392 (+102 bp).

## Overlap with the incumbent
- **Correlation:** 0.32 (DEV 0.33, HOLD 0.27); beta 0.22.
- **Same days:** 231 of the sleeve's 467 active days are incumbent-active days, and they carry 71% of its P&L.
- **Incumbent's 10 worst days:** incumbent −16.9% in total, sleeve −6.5%; the sleeve was positive on 2 of 10.
- **Concentration:** the top 3 days are 28% of P&L.
- **Drawdown:** −3.6% on daily closes. Marked to market, **−26.8% intraday on Oct 10 2025**, fully invested across
  34 coins (181 fills that day).

## Fill realism (300 random DEV fills of the frozen variant, 34 coins; trade prints via common.TradeFetcher)
- **Confirmed:** 88.6% have a print at or below the level minus one tick in the fill minute (parents 86.6%, deeper
  rungs 92.8%). Every parent's first print was above its level.
- **Unconfirmed:** 11.4% of fills (6.8% of sampled dollars); prints stayed a median 158 bp above the level. They earn
  68 bp net against 19 bp for confirmed fills, and carry 21% of the sample's P&L: optimistic bias in the candle model.
- **Through-volume:** printed volume strictly below the level is only 0.29× the candle estimate, so θ = 0.5 on
  candles is about θ = 0.15 on prints. The modelled fill fits within half the printed through-volume for 68% of
  tranches.
- **Half-spread:** realised median 5.6 bp (75th percentile 15.5 bp), against the model's 2 bp.

## Weaknesses
1. **Same-minute deeper fills drive the result.** The live bot sends the 6σ/8σ bids only after the parent fills.
   Under that minute bound, alpha t falls to 0.90 and the HOLD t to −0.04.
2. **Fills are thinner than the candles say.** Print through-volume is 3.5× smaller, the unconfirmed fills are the
   profitable ones, and realised spreads are about 3× the model's.
3. **Capacity is small.** Sharpe roughly halves from $30K to $50K.
4. **The same cascades as the incumbent.** Most P&L falls on incumbent-active days, it loses on the incumbent's worst
   days, and it has a −27% intraday tail.
5. **Selection lift.** T3 was the best of 5. Base T1 had a DEV alpha t of 0.52, and HOLD (0.50) fell back toward it.
6. **Tick grid.** 2024's grid is coarser than today's quote increments: conservative for fills, and it dropped
   borderline coins such as ENS (3.04 bp).

## Verdict
**FAIL.** Long-tail wicks pay a small resting bid (sleeve Sharpe 1.75 at 2× on $30K), but they are mostly the
incumbent's cascade days. The alpha is not significant (t 1.61; 0.50 in HOLD), the book gains only +0.15 Sharpe, and
the print check contradicts the fill assumptions the result leans on. Keep the incumbent alone.

## Deviations (all fixed before any P&L)
1. **Coin-by-coin driver** instead of trades_wide.py's all-coins-at-once arrays, for memory. Same computations,
   verified identical on the wide 31.
2. **Tick screen applied on H2-2024 minutes first, in the fetcher.** A coin failing est_tick there cannot pass on the
   full file, so it was not fetched further. ENJ had under 10,000 H2 minutes, was fetched in full and failed.
3. **"2024 median daily volume"** = the median over each pair's 2024 trading days, in USD (close × volume).
4. **Stress conventions:** exit impact stays at 1× under 2×; the 5 bp half-spread case doubles to 10 bp.
5. **Bound:** the instant bound (the incumbent's) was fixed as primary before any result; the minute bound is
   reported. No change after reading HOLD.

## Shared code
No bug found in gates.py or common.py. sim.evaluate reads reports/lab/cost_table.csv (absent in sparse worktrees) for
perp costs; sleeve.py stubs it, since this spot-only sleeve prices no perp fill.
