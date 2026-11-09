# SHAPE: air pocket or grind? (Path A, builder `shape`)

**Verdict: FAIL.** The frozen filter skips the 4σ parent when JS1_60 ≤ 0.2615: no single minute carried more than 26% of the last hour's residual drop. It loses to R2-08 on HOLD: paired t −1.12 at X2, −0.71 bp/day at X1, and negative in both HOLD eras. Only A4 (no losing year) passes. Its DEV edge (t 0.61 at X2) did not survive realistic costs even on DEV (−0.20 bp/day at X1).

## Mechanism
A forced seller with no price limit (liquidations, stop cascades) empties the book in a minute or two. That is an air pocket, and it refills when the forced flow stops. An informed seller or a worked metaorder grinds the price down instead: high path efficiency, little jump content, and the impact lasts. A multi-hour downtrend is the same grind at a longer scale. R2-08's AI sees how far the residual price moved, not how it got there. SHAPE cancels the 4σ bid when the last hour, or the last six hours, looks like a grind.

## Formulas (committed before any trial: c344da2, 9539368)
For a research parent (coin c, fill minute t; `pathA.parents(era)`), using Coinbase 1-minute candles known at t−1:
- r_k = Δ log cf_c, where cf is the close forward-filled up to 30 minutes on R2-08's grid; rb_k is the same for BTC.
- β = R2-08's 10,080-minute beta through t−1 (`scripts/lab/core.py` rbeta, clipped to [0, 3]). Recomputing every DEV parent's 4σ level with this β matches the frozen `lvl` exactly: relative difference 0, and PEPE within its 1e-8 tick.
- e_k = r_k − β rb_k.
- PE60 = |Σe| / Σ|e| over k ∈ [t−60, t−1]. Skip when HIGH.
- JS1_60 = max_k(−e_k) / (−Σe) if Σe < 0, else +∞ (no drop yet at t−1, never skipped). Skip when LOW.
- JR60 = max(0, 1 − BV/RV), with RV = Σe² and BV = (π/2) Σ|e_k||e_{k−1}| over 59 pairs. Skip when LOW (see the deviation).
- DRIFT6h = Σe over [t−360, t−1] / (sd of e over [t−43,200, t−1] × √360). Skip when LOW.

**Threshold rule** (`shp_rules.py`):
- n_skip = floor(s × 1,155 + 0.5) = 173 (15%) or 347 (30%).
- The threshold is the n_skip-th most extreme DEV value. Skip x ≥ thr for HIGH features, x ≤ thr for LOW ones.
- A missing feature is never skipped; ties at the threshold are all skipped.
- HOLD uses the same absolute threshold.
- A skip sets the (fill minute, coin) cell to `frozen_sim.SKIP`, which cancels the bid. Every skip cell is asserted to be a parent in the simulator's arrays.

## Deviation (before any trial, from the DEV feature distribution only)
JR60 is exactly 0 for 406 of 1,155 DEV parents (35%, where BV ≥ RV). Its lowest 15% and 30% therefore tie, and both trials would skip the same 35%. The JR60 variants instead rank the untruncated RJ60 = 1 − BV/RV. It equals JR60 wherever JR60 > 0, and more negative means a smoother path. Realised shares were 15.0% and 30.0%.

## Data
- **DEV:** 1,155 parents (2025-01-07 .. 2026-03-31, 16 coins).
- **HOLD:** chk 412 parents, early 744.
- **Candles:** `data/minute` (2024-01 .. 2026-11-05) and `data/minute_early` (2021–23), 17 coins plus BTC.
- Every feature is present for every parent in every era.

## Trials (DEV, X2, $250K; all 8 logged)
| Variant | Threshold | Skipped | DEV t | Δ bp/day | ΔSharpe |
|---|---|---|---|---|---|
| PE60_15 | ≥ 0.3367 | 173 | −0.43 | −0.22 | −0.02 |
| PE60_30 | ≥ 0.2796 | 347 | +0.46 | +0.45 | +0.77 |
| JS1_60_15 | ≤ 0.1997 | 173 | −0.06 | −0.03 | +0.12 |
| **JS1_60_30** | ≤ 0.2615 | 347 | **+0.61** | +0.48 | +0.86 |
| JR60_15 (RJ60) | ≤ −0.0756 | 173 | −1.27 | −0.37 | −0.11 |
| JR60_30 (RJ60) | ≤ −0.0180 | 347 | −2.35 | −1.32 | −0.64 |
| DRIFT6h_15 | ≤ −2.291 | 173 | +0.21 | +0.13 | +0.19 |
| DRIFT6h_30 | ≤ −1.572 | 347 | −2.04 | −1.62 | −0.87 |

The incumbent's DEV Sharpe at X2 is 1.62. No variant reached DEV t = 1. Skipping the smoothest or most persistent dislocations (JR60 and DRIFT6h at 30%) hurt, with t ≤ −2: those were good fills.

## Frozen variant (freeze commit 2e6b6ef)
JS1_60_30: skip when JS1_60 ≤ 0.2615111544208388. On DEV it gained +0.48 bp/day at X2 (t 0.61) but lost −0.20 bp/day at X1. The DEV gain was saved costs at doubled costs, not better fill selection.

## HOLD (read once) and gates
| | X2 Δ bp/day (t) | X1 Δ bp/day | Candidate / incumbent Sharpe X2 | Skipped |
|---|---|---|---|---|
| chk | −0.35 (−0.85) | −0.80 | 1.50 / 1.61 | 98 / 412 |
| early | −0.46 (−0.94) | −0.69 | 0.79 / 1.13 | 158 / 744 |
| HOLD | −0.43 (−1.12) | −0.71 (t −1.81) | 0.99 / 1.26 | 256 / 1,156 |

- **A1** (HOLD t ≥ 2 at X2): **fail**, −1.12.
- **A2** (HOLD mean > 0 at X1): **fail**, −0.71 bp/day.
- **A3** (positive in chk and early): **fail**, both negative.
- **A4** (no losing year at X2): **pass**. 2022 +5.8%, 2023 +6.5%, 2025 +17.0%, 2026 +9.2%; the incumbent made 6.8 / 8.9 / 15.6 / 9.2%.
- Deflated Sharpe 0.16 (N = 4,598, SR0 1.98).
- The HOLD top-5-day share is undefined because the total gain is negative.
- At S (reported only), HOLD −0.71 bp/day (t −1.80).

## Robustness and diagnostics (descriptive, after the read)
- **Neighbouring setting:** disagrees in sign on DEV (JS1_60_15, t −0.06).
- **θ 0.25 at S**, against the incumbent's S/0.25 series: DEV −0.10, chk −0.63 (t −1.60), early −0.54 bp/day (t −1.29).
- **Skipped vs kept parents**, by the frozen dataset's research gross return per trade:

  | Era | Skipped | Kept | Hit rate skipped / kept |
  |---|---|---|---|
  | DEV | 35 bp | 67 bp | 63% / 75% |
  | chk | 47 bp | 45 bp | — |
  | early | 42 bp | 55 bp | — |

  On DEV the filter picked weaker fills, but they were still profitable before costs. In chk it did not discriminate at all.
- **Incumbent's 10 worst DEV days:** the filter added +673 bp of $250K (8 of 10 days helped). This is not confirmed on HOLD.

## Capacity and fill realism
- A skip only cancels the 4σ bid, so no new fills or volume are assumed and the incumbent's capacity is untouched. The engine-faithful cash rule reallocates any freed cash.
- Features use only candles closed by t−1, available live from Coinbase. Costs are the frozen simulator's X2, X1 and S.
- A cancelled bid that would have been re-placed and filled later is not simulated, because the dataset holds no such fills. Every Path A filter shares this bias.

## Weaknesses
- One-minute candles see the shape only at minute resolution, and the true air pocket often happens inside the fill minute itself. 83 DEV parents had no residual drop at all by t−1.
- JS1_60 is a noisy ratio, and its 15% and 30% cuts disagree in sign on DEV.
- Each parent uses a single 7-day β, so residual moves of high-β coins carry BTC noise.

## Verdict
**Fail.** The drop's shape, measured from candles at t−1, does not separate forced from informed selling well enough to beat R2-08 after costs. No DEV variant reached t = 1, and the frozen one lost in both HOLD eras at X2 and at X1. Not recommended for the live bot.

## Reproduce
In worktree `h2/shape`:
- `python scripts/hunt2/shape/shape.py features sel`, then `dev`, then `freeze`, then `hold <tmp>`
- `python scripts/hunt2/shape/diag.py all <tmp>`

Commits: trial code 9539368, freeze 2e6b6ef, read ba5a265, diagnostics be671fd.
