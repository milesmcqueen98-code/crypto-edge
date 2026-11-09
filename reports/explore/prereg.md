# Explore v1: a 1,000+-variant search for a higher-Sharpe R2-08 spot ladder — pre-registration (Nov 9 2026)

Written before any variant of this search was run. Branch explore/v1, cut from sizing-lab (eca0555).
Code: scripts/explore/. Results: reports/explore/.

## Goal
Raise the Sharpe of the R2-08 spot ladder by changing any execution assumption, without giving up capacity:
- ladder geometry, rung weights and trigger-only parents;
- take-profit level, take-profit by depth and scale-out ladders;
- hold time and the deeper-bid cancel rule;
- AI strictness, a liquidity floor and concurrency;
- size, size cap and cash cap.

The AI signal itself is not retrained here. Its predictions enter only through stricter thresholds. "No change" is a
valid result.

## What this search can and cannot show
- **The eras are not fresh.** Every era has shaped earlier choices: R2-08 was the best of 130 variants, and about
  5,000 setups have touched these data.
- **So the protocol is:**
  - search on the selection era only;
  - freeze a short list;
  - read check and 2022-23 once;
  - judge with statistics that count every variant tried;
  - forward-test any winner on paper before a live change.
- **Known results that shape the priors**, disclosed here:
  - Rung weights: up to +0.25 in selection, paired t <= 1.2 (wick v4). W2 runs as a paper book.
  - Take-profit 0.3 and 1.0, and hold times of 30 and 120 minutes, were worse in the v2 lab.
  - Stricter thresholds (65-75th percentile) had higher Sharpe but lower return in 2022-23 (wick v3).
  - The 0.2% ADV cap was chosen from 72 combinations (wick1m).
  - No exit-timing rule beat "take-profit, else sell at minute 60" (ladder v6).
  - No sizing rule or pre-fill filter held out of sample (sizing lab, edge hunt 2).
  - Sizing lab, post hoc: deeper rungs bought right after a BTC drop were the best fills in the check era.

## Simulator
- **xsim** (scripts/explore/xsim.py): the rungs.py rules (wick1m simulator) with spot-only capacity, generalized to the
  dimensions below.
  - At its defaults it reproduces rungs.run, W0 and W2, in both fill modes, on all eras and capitals, to 2e-17
    (parity.txt).
- **Precompute** (scripts/explore/precompute_x.py):
  - rungs at 4, 5, 6, 7, 8, 9, 10 and 12 sigma;
  - take-profits at 0.3-1.0 of each rung's dislocation;
  - each deeper rung's first touch over the parent's 60 minutes;
  - the 61-minute close path.
- **Fill timing:**
  - Minute mode is the paper books: no deeper fill in the parent's own minute.
  - Instant mode keeps those fills.
  - The live 1-second bot is minute + s x (instant - minute), with s measured in wick v4 (theta 0.5): selection
    0.52 / 0.66, check 0.62 / 0.82, 2022-23 0.91 / 0.93 at $250K / $1M.
- **Costs:** the simulator's model (tiered fees, 2 bp half-spread, square-root impact on market exits), with theta 0.5.
- **Limits:**
  - No resting-bid cash rule (ladder v5's engine-faithful replay is too slow for a search). Finalists that it can
    express are re-checked there.
  - Model exit costs, which are conservative against prints.
  - Take-profit capacity is counted over 60 minutes even for shorter holds.
  - Take-profit sub-tranches share one take-profit-buyer counter per parent (conservative).

## Objective
- **Primary:** Sharpe of daily returns over T-bills (sqrt 365) of the blended, live-like book at $250K.
- **Secondary:** minute-mode Sharpe at $250K (the paper books), and blended Sharpe at $1M (capacity).
- **Incumbent:** rungs 4 / 6 / 8 sigma in thirds, take-profit 0.6, hold 60 minutes, deeper bids cancelled when the
  parent's take-profit trades, every AI signal, ADV cap 0.2%, 25% of capital per signal, positions <= 100% of cash.

## Search space

| Dimension | Levels (first = incumbent) |
|---|---|
| Rung set (sigma) | 4-6-8; 4-5-6-7-8; 4-6-8-10; 4-6-8-12; 4-5-7-10; 4-7-10; 4-6-9-12; 4-8; 4-6-10; 4-5-6-8-10-12; 4-6; 4-8-12 |
| Depth weighting alpha (w_k ~ (k/4)^alpha) | 0, -1, 0.5, 1, 1.5, 2, 3 |
| Parent weight multiplier | 1, 0.5, 0 (trigger-only: deeper bids go out when the 4-sigma level trades) |
| Take-profit | 0.6 for every rung; one fraction 0.3 / 0.4 / 0.5 / 0.7 / 0.8 / 1.0; by depth (parent 0.4 / 0.6 / 0.8, deeper 0.4 / 0.6 / 0.8 / 1.0); scale-out ladders (0.4 / 0.6 / 0.8 in thirds; 0.5 / 0.8 in halves; 0.3 / 0.6 / 1.0 as 1:2:1; 0.4 / 0.7 in halves) |
| Hold (minutes) | 60, 30, 45 |
| Deeper-bid cancel | at the parent's take-profit; never (rest the whole hold) |
| AI strictness (pred / thr >=) | 1.0, 1.05, 1.1, 1.2, 1.3, 1.5 |
| Liquidity floor (ADV) | 0, $3M, $10M |
| Concurrent parents | no limit, 4, 6, 8 |
| ADV cap | 0.2%, 0.15%, 0.3%, 0.4% |
| Size per signal | 25%, 15%, 20%, 33% of capital |
| Cash cap | 100%, 80% |

**Round 1** (reports/explore/round1_variants.json, 1,060 variants):
- the incumbent, the W2 book, and 58 one-factor-at-a-time variants;
- 1,000 random combinations drawn uniformly over the grid (seed 20261109), de-duplicated.

**Rounds 2-3** (selection era only):
- Round 2: refinement around the top region of round 1 (one level either side, on each dimension, of the top 20),
  plus mechanism-led variants from a literature scan that xsim can express.
- Round 3: at most one more refinement.
- Each round's list is committed before it runs. Every variant is logged in reports/explore/variants.csv and counts
  toward N.

## Overfitting diagnostics (selection era)
- **PBO by CSCV:** 16 contiguous blocks and all 12,870 half-splits. PBO is the share of splits in which the in-sample
  best variant ranks below the median out of sample.
- **Hansen's SPA test** of "some variant beats the incumbent":
  - The statistic is the vol-matched daily difference d_t = r_v,t / sd_v - r_0,t / sd_0, so its mean tracks the
    Sharpe difference.
  - Stationary bootstrap, mean block 7 days, 2,000 draws.
  - Romano-Wolf StepM lists the variants that survive.
- **Deflated Sharpe** of each finalist, with:
  - N = all variants of this search, and N = this search plus about 5,000 earlier setups;
  - also with the effective N from the variants' return correlations.

## Short list (frozen before the holdout read), at most 6
"No harm" means minute-mode Sharpe at $250K >= the incumbent's, and blended Sharpe at $1M >= the incumbent's - 0.05,
both on the selection era.
1. **Best:** the highest primary Sharpe among no-harm variants.
2. **Robust:** the highest lower bound (primary Sharpe - 1 block-bootstrap standard error, 7-day blocks) among no-harm
   variants.
3. **Ensemble:** the average of the 10 best no-harm variants' daily returns (each run at full capital; an
   approximation of splitting the capital across 10 sub-ladders).
4-6. The best no-harm variant of each family not already listed:
   - geometry (rungs, weights, parent);
   - exits (take-profit, hold, cancel);
   - filters and capacity (strictness, floor, slots, cap, size, cash).

## Holdout read (once)
- Check (Apr - Nov 5 2026) and 2022-23, for the finalists and the incumbent.
- Both fill modes, $250K and $1M, plus theta 0.25 at $250K.
- Finalists that the engine-faithful simulator can express are re-run there (information).

## Pass (all required)
1. Blended ΔSharpe >= +0.20 at $250K in each era (selection, check, 2022-23).
2. Blended ΔSharpe >= 0 at $1M in each era.
3. Minute-mode ΔSharpe >= 0 at $250K in each era.
4. Theta 0.25: blended ΔSharpe >= 0 at $250K in each era.
5. Risk at $250K, blended, in each era: daily max drawdown, marked-to-market max drawdown and worst day no worse than
   1.1x the incumbent's.
6. No losing calendar year (blended, $250K).
7. Significance: event-cluster bootstrap (as in the sizing lab) of the pooled check + 2022-23 mean vol-matched daily
   difference at $250K, blended. p <= 0.05 after Holm across the finalists.

**Verdicts:**
- A winner gets a new paper book: a bot/spot config with engine support where needed, parity and fault tests, and
  deployment by `wickctl update`. Nothing goes live from this round.
- Everything else is rejected, or kept as a forward-test lead.
- Deflated Sharpe, PBO and SPA are reported and shape the verdict's wording. The gates above decide.

## Scorecard (100 points, fixed now)
Scored on check and 2022-23, the "binding cells".

| Criterion | Points | Formula |
|---|---|---|
| Sharpe gain | 20 | 20 x clip(mean blended ΔSharpe at $250K over the binding eras / 0.40, 0, 1) |
| Capacity | 15 | 10 x clip(mean blended ΔSharpe at $1M over the binding eras / 0.40, 0, 1) + 5 x share of the 3 eras with $1M ΔSharpe >= 0 |
| Consistency | 10 | 10 x share of the 12 cells (3 eras x 2 capitals x 2 modes) with ΔSharpe > 0 |
| Evidence | 15 | 15 x clip((0.20 - Holm-adjusted p) / 0.15, 0, 1) |
| Spread | 10 | 5 x share of the 2 binding eras whose ΔSharpe stays >= +0.20 with any single day removed (blended, $250K) + 5 x clip((1 - top-5-day share of the pooled holdout gain) / 0.5, 0, 1) |
| Risk | 15 | 12 x share of the 9 risk checks passed (3 measures x 3 eras) + 3 if no losing year |
| Mechanism | 10 | hand-scored at the freeze, before the read |
| Implementation | 5 | hand-scored at the freeze, before the read |

## Deviation log
1. **Before round 3 ran (Nov 9 2026, 09:20 ET).** Recorded before any round-3 variant was run.
   - **New dimensions:** xsim gains three dimensions, all off in rounds 1-2, plus finer hold times. Parity at the
     defaults is unchanged (parity.txt).
     - sig_min: skip signals whose sigma is below 40 / 50 / 55 / 60 / 70 bp;
     - bid_to: deeper bids rest at most 2 / 5 / 10 / 20 minutes after the signal;
     - cancel_f: cancel deeper bids when the parent recovers 0.3 / 0.4 / 0.5 / 0.8 / 1.0 of its dislocation;
     - hold times of 40, 50 and 55 minutes.
   - **Why:** a selection-era attribution of the incumbent's fills.
     - Signals with sigma below the median (57.6 bp) made about 0 bp per dollar; those above made about 85 bp. This
       held in all five quarters and all three ADV terciles.
     - Deeper fills in the first 2 minutes made 72-122 bp; later ones made -5 to 66 bp (noisy).
   - **Wider than "one more refinement":** round 3 has 3,157 variants (scripts/explore/variants_r3.py).
     - 1,500 random variants over a pruned grid. Levels with a round 1-2 OLS effect of -0.19 or worse and |t| >= 3
       are dropped.
     - Family searches with everything else at the incumbent: geometry (all 240 new combinations), exits (600) and
       filters (600). These supply the family-best finalists, which rounds 1-2 could only fill from one-factor
       variants.
     - The new dimensions one at a time around the incumbent and the 10 best no-harm variants.
   - **Information only:** a selection-rule tournament by CSCV (select_rules.py) estimates each short-list rule's
     out-of-sample gain inside the selection era. The short-list rules above do not change.
   - **Disclosed prior:** the sizing lab's holdout showed that the AI's lowest predicted-edge tercile was profitable
     out of sample. That bears on strictness (r_min) finalists. It is used only in the hand-scored mechanism points,
     not in selection.
   - All round-3 variants count toward N.
