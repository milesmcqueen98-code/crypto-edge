# IMP: was the drop paid for by selling? (Path A, builder `shape`)

**Verdict: FAIL.** The frozen filter skips the 4σ parent when the 30-minute residual drop is at least 9.2× the square-root-law impact of the net aggressive selling, or when the coin dropped with no net taker selling. It loses on HOLD: paired t −1.50 at X2, −0.79 bp/day at X1. It helped in chk (+0.26 bp/day, t 0.36) and hurt in early (−0.82, t −1.86). Only A4 passes.

## Mechanism
Impact that the signed flow explains (I ≈ Y σ_D √(Q/V_D)) is mechanical. For forced, uninformed flow it relaxes once the flow stops, which is what the ladder's take-profit collects. A drop much larger than the net selling explains was made by market makers revising quotes on information, and about two-thirds of informed impact stays. IMP cancels the 4σ bid when the residual drop per unit of square-root impact is extreme, or when the selling rate looks like a slow drift.

## Formulas (committed before any trial: c344da2, 9539368; `scripts/hunt2/imp/imp.py`)
For each parent (coin c, fill minute t, first trade-through t_fill) and W ∈ {5, 15, 30}:
- **Inputs:** usd_W, sell_share_W and ret_bp_W from prints in [t_fill − W − 1 s, t_fill − 1 s) (`reports/hunt2/parents/features_*.csv`); σ_D = vol_d and V_D = adv from `windows.csv`.
- Q_W = usd_W (2 sell_share_W − 1).
- r_W = −ln(1 + ret_bp_W/1e4) (the sign is deviation 1).
- rb_W = lf_BTC[t−1] − lf_BTC[t−1−W]: BTC's 1-minute closes, forward-filled up to 30 minutes, over the W minutes before the fill minute.
- β = R2-08's beta through t−1 (SHAPE's verified helper).
- D_W = −(r_W − β rb_W); I_W = σ_D √(max(Q_W, 0)/V_D).
- f_W = D_W / I_W if Q_W > 0; +∞ if Q_W ≤ 0 and D_W > 0; missing (kept) if Q_W ≤ 0 and D_W ≤ 0. Skip when HIGH.
- rate_15 = (Q_15/15) / (V_D/1440). Skip when LOW.
- **Threshold rule:** as in SHAPE (`shp_rules.py`). 173 or 347 of the 1,155 DEV parents, the n_skip-th most extreme DEV value, ties skipped, missing values kept, the same absolute threshold on HOLD.

## Deviations
1. **Print order (shared-code bug; prereg deviation log d0eb624; found on DEV before any IMP trial).**
   - Prints are stored newest-first, because the Exchange-API fetcher walks backward. `parent_features.py` takes px[−1]/px[0] − 1 on that order, so ln(1 + ret_bp_W/1e4) is exactly minus the window's log return.
   - On DEV it correlates −0.84 / −0.95 / −0.96 (W = 5/15/30) with the candle return over the same minutes.
   - After the freeze, the corrected HOLD values correlate +0.93 (chk) and +0.96 (early) at W = 30.
   - The shared code is unchanged; r_W is negated identically on DEV and HOLD. `dist_lvl_bp_W`, also affected, is not used.
2. **HOLD feature run.**
   - The instructed dispatch (run 42545412684) computed `features_hold.csv` but could not commit it. `parent_features.py` rewrites tracked files, so the workflow's pull --rebase refused, and the step still ended green.
   - Run 42545852738 used `scripts/hunt2/imp/hold_features.py` instead: `parent_features.py` unchanged into a scratch folder, then only `features_hold.csv` copied.
   - The runner reproduced all 94 committed DEV columns exactly (`reports/hunt2/imp/runner_dev_check.txt`).
3. **HOLD read one era per subprocess** (memory), combined exactly as `pathA.hold_read` does. The sel column reproduces the DEV trial exactly.

## Data
- **DEV:** 1,155 parents (1,154 with a trade-through in the fill minute, 1 fallback).
- **HOLD:** 1,156 parents (chk 412, early 744; 15 fallbacks).
- Median DEV D_15 is +122 bp against I_15 of 38 bp, so f ≈ 3 with Y omitted.
- On DEV, f_W is +∞ for 162 / 137 / 136 parents (W = 5/15/30) and missing (kept) for 59 / 58 / 30.

## Trials (DEV, X2, $250K; all 8 logged)
| Variant | Threshold | Skipped (of which +∞) | DEV t | Δ bp/day | ΔSharpe |
|---|---|---|---|---|---|
| f_5_15 | ≥ 19.91 | 173 (162) | +0.05 | +0.02 | +0.26 |
| f_5_30 | ≥ 5.192 | 347 (162) | +0.42 | +0.34 | +0.81 |
| f_15_15 | ≥ 9.782 | 173 (137) | −0.36 | −0.16 | +0.04 |
| f_15_30 | ≥ 4.809 | 347 (137) | −0.81 | −0.53 | −0.00 |
| **f_30_15** | ≥ 9.213 | 173 (136) | **+0.423** | +0.18 | +0.32 |
| f_30_30 | ≥ 4.750 | 347 (136) | +0.30 | +0.22 | +0.53 |
| rate_15_15 | ≤ −0.0432 | 173 | −2.16 | −1.11 | −0.59 |
| rate_15_30 | ≤ 0.290 | 347 | −0.54 | −0.50 | +0.03 |

The rule picked f_30_15 (t 0.4230) narrowly over f_5_30 (0.4203); that is not a tie. Skipping net-buying windows (rate_15_15) hurt with t −2.16: on DEV, drops with no net selling were good fills.

## Frozen variant (freeze commit d8ec6c0)
f_30_15: skip when f_30 ≥ 9.212555495931506, including +∞. On DEV it gained +0.18 bp/day at X2 (t 0.42) but lost −0.14 bp/day at X1.

## HOLD (read once) and gates
| | X2 Δ bp/day (t) | X1 Δ bp/day | Candidate / incumbent Sharpe X2 | Skipped |
|---|---|---|---|---|
| chk | +0.26 (+0.36) | +0.02 | 1.94 / 1.61 | 51 / 412 |
| early | −0.82 (−1.86) | −1.03 | 0.38 / 1.13 | 199 / 744 |
| HOLD | −0.57 (−1.50) | −0.79 (t −1.95) | 0.85 / 1.26 | 250 / 1,156 |

- **A1:** **fail**, t −1.50.
- **A2:** **fail**, −0.79 bp/day.
- **A3:** **fail**, early negative.
- **A4:** **pass**. 2022 +2.2%, 2023 +7.5%, 2025 +15.0%, 2026 +11.2%.
- Deflated Sharpe 0.08 (N = 4,598).
- The HOLD top-5-day share is undefined because the total is negative.
- At S, HOLD −0.79 bp/day (t −1.95).

## Robustness and diagnostics (descriptive, after the read)
- **Neighbours on DEV:** f_30 at 30% agrees in sign (+0.30); f_15 at 15% does not (−0.36).
- **The skip share drifted:** 15% on DEV, 12% in chk, 27% in early.
- **θ 0.25 at S:** DEV −0.26, chk +0.06 (t 0.08), early −0.81 bp/day (t −2.13).
- **Skipped vs kept parents**, by research gross return per trade:

  | Era | Skipped | Kept | Hit rate skipped / kept |
  |---|---|---|---|
  | DEV | 52 bp | 58 bp | — |
  | chk | 5 bp | 51 bp | 61% / 77% |
  | early | 49 bp | 54 bp | — |

  In chk the filter found genuinely bad fills. On DEV and in early it barely discriminated, and the skipped fills were profitable.
- **Incumbent's 10 worst DEV days:** +203 bp (6 of 10 days helped).

## Capacity and fill realism
- Skips only cancel bids, so no new capacity is used.
- Features use Coinbase prints at least 1 s before the trade-through (the aggressor side is exact), plus BTC candles closed by the start of the fill minute.
- Live, the rule must run on a trade stream and cancel the bid within the last second before a trade-through. That is far more latency-sensitive than the bot's 1-second fill poll. The backtest evaluates it once, 1 s before the fill, which flatters it.

## Weaknesses
- Most of the 15% skip set (136 of 173 on DEV) is the +∞ case: a drop with no net taker selling, not the large-ratio case the mechanism targets.
- σ_D and V_D are daily figures, and BTC's window is candle-aligned, up to a minute off the print window.
- Y and the impact-decay timescale are not estimated, and the thresholds are pooled across 16 coins.

## Verdict
**Fail.** The square-root-impact residual did not reliably separate informed from forced drops: DEV t 0.42 at X2 (and negative at X1), HOLD t −1.50 at X2, mixed by era. Not recommended for the live bot.

## Reproduce
In worktree `h2/shape`:
- `python scripts/hunt2/imp/imp.py features sel`, then `dev`, then `freeze`
- HOLD print features: run 42545852738 (`scripts/hunt2/imp/hold_features.py art`)
- `imp.py features chk`, `imp.py features early`, then `imp.py hold <tmp>`
- `python scripts/hunt2/shape/diag.py all <tmp>`

Commits: trial code 9539368, freeze d8ec6c0, read b2aecb7.
