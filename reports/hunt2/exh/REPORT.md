# EXH: is the forced selling spent? REPORT (builder flow, Path A)

**Verdict: FAIL (A1).** The HOLD paired t is 1.51 < 2 at X2. A2, A3 and A4 pass: +0.21 bp/day at X2 and +0.10 at X1, positive in both HOLD eras and in every year. But the gain is concentrated (the top-5 HOLD days are 125% of it), and the threshold's bite drifts across eras.

## Mechanism
Forced selling is front-loaded, and liquidation engines sell until their queue is empty. A bid filled after a large flush meets the last of the forced flow and is paid by the rebound. A bid filled at peak selling intensity is early, and a drop that arrives with little aggressive selling is makers repricing (information), not a flush. The live bot can read aggressor-exact intensity and cumulative selling in Coinbase's market_trades feed and cancel the 4σ bid while the rule fires.

## Data
The same parents and prints as WHO: DEV 1,155 parents (2025-01-01..2026-03-31; 189 days, 16 coins), HOLD 412 chk + 744 early. Coinbase prints run from 30 minutes before to 2 minutes after every fill minute, and all 2,311 windows are covered. Features come from prints ≥ 1 s before the first trade-through (scripts/hunt2/parent_features.py) and are all order-free. HOLD features were derived after both freezes (commit d3fb237), and the same run regenerated the DEV file byte-identically.
- ex_peak: the EWMA (60 s half-life) of aggressive-sell dollars now ÷ its 30-minute maximum (skip HIGH). The grid's last second is always empty, so the maximum is 0.5^(1/60) = 0.9885. 162 DEV parents sit at that value, but the 15% cut (0.9852) lies below the cluster and removes exactly 174.
- csv_15, csv_30: aggressive-sell dollars over 15 / 30 minutes ÷ the coin's 30-day ADV (skip LOW).
- turn: the imbalance over the last minute minus the imbalance over 15 minutes (skip LOW; 2 DEV parents missing, kept).

## Rule and threshold
As in WHO: the threshold is the numpy quantile of the DEV parents' values at the level that removes 15% or 30% of all 1,155 DEV parents (174 or 347 removed in every variant), fixed in absolute units. Missing values are kept, and a skip is frozen_sim.SKIP on the parent's (fill minute, coin) cell.

## DEV trials (sel, X2, $250K; paired HAC t vs the incumbent, whose DEV Sharpe is 1.62)
| Variant | Skip when | Thr | Events | t | bp/day | ΔSharpe |
|---|---|---|---|---|---|---|
| expeak_15 | ex_peak high | 0.98523 | 174 | +0.44 | +0.23 | +0.20 |
| expeak_30 | same | 0.86979 | 347 | −0.60 | −0.42 | −0.06 |
| csv15_15 | csv_15 low | 0.010506 | 174 | +0.46 | +0.20 | +0.28 |
| csv15_30 | same | 0.015241 | 347 | +0.94 | +0.66 | +0.57 |
| **csv30_15** | csv_30 low | 0.016907 | 174 | **+1.03** | +0.56 | +0.44 |
| csv30_30 | same | 0.025237 | 347 | +0.57 | +0.47 | +0.46 |
| turn_15 | turn low | −0.41259 | 174 | +0.00 | +0.00 | +0.13 |
| turn_30 | same | −0.26992 | 347 | −1.08 | −0.66 | −0.20 |

The cumulative-selling family is positive in all four neighbours (t +0.46 to +1.03); intensity-vs-peak and the imbalance turn are not.

## Frozen variant
csv30_15: skip when the aggressive selling of the last 30 minutes is below 1.691% of the coin's 30-day ADV (csv_30 < 0.0169069). It was selected by the SPEC's rule; frozen.json is at 8c68eff (code e1f6538). DEV: t +1.03, +0.56 bp/day, ΔSharpe +0.44, though the top-5 DEV days carry 165% of the gain.

## HOLD (read once) and gates
| | DEV | chk | early | HOLD |
|---|---|---|---|---|
| Skipped / parents | 174/1,155 (15.1%) | 97/412 (23.5%) | 33/744 (4.4%; 8 kept, ADV unknown) | 130/1,156 |
| Mean diff X2, bp/day (t) | +0.56 (1.03) | +0.67 (1.22) | +0.08 (0.99) | +0.21 (1.51) |
| Mean diff X1, bp/day (t) | — | +0.25 (0.58) | +0.05 (0.67) | +0.10 (0.84) |
| Sharpe X2, cand / inc | 2.06 / 1.62 | 2.11 / 1.61 | 1.20 / 1.13 | 1.45 / 1.26 |

- **A1 FAIL** (HOLD t 1.51 < 2). **A2 pass** (X1 +0.10 bp/day). **A3 pass** (chk +0.67, early +0.08). **A4 pass.**
- Years at X2, candidate (incumbent): 2022 7.2% (6.8%), 2023 9.0% (8.9%), 2025 18.4% (15.6%), 2026 10.3% (9.2%). The difference is positive in every year.
- All three eras together: t 1.62, +0.32 bp/day. Deflated Sharpe 0.25 (N = 4,598). The HOLD top-5 days are 125% of the net gain (+201 bp), four of the five fall in October 2026 (Oct 8, 12, 14, 29), and without the top five the HOLD difference is −49 bp.
- θ 0.25 at S (reported): HOLD +0.11 bp/day (t 1.02); chk +0.29, early +0.06; DEV +0.24 (t 0.52).
- On the incumbent's ten worst DEV days the candidate loses 2.8 points less at X2 (2.4 at S).

## Capacity
EXH is a filter only. Per-fill sizing is unchanged, so there is no loss of the incumbent's capacity. At 2026's rate it would skip about a fifth of the ladders.

## Fill-realism checks
- The aggressor side is exact from prints, features are measured 1 s before the first trade-through, and every skip cell is asserted to hit a simulator parent.
- **Threshold drift.** An absolute cut on "selling ÷ 30-day ADV" bites very differently by year: 2022 4.9%, 2023 4.0%, 2025 14.8%, 2026 Q1 16.3%, chk 23.5%. In 2022–23, 4σ dips came with more selling relative to ADV, so the rule was nearly idle in early (33 skips), and A3's early pass rests on +0.08 bp/day.
- **Not modelled: re-placement.** In quiet markets csv_30 sits below the cut, so live the bid is off by default and must be placed as selling accumulates. The simulation assumes the bid is resting whenever csv_30 ≥ the cut one second before the trade-through, so a crossing in the last second or two of a fast drop would be a missed fill live. Measuring this needs csv_30 timing in a forward log.
- Costs, fills and latency are the frozen simulator's.

## Weaknesses
- t 1.51 is below the bar, a single HOLD month (October 2026) supplies more than the whole gain, and the DSR is 0.25.
- This builder ran 24 trials on related print features (8 here), and EXH is one of eight Path A filters read on the same HOLD.
- Overlap with R2-08's AI (volume and volatility state) is untested.
- It uses Coinbase spot prints only.

## Verdict
**FAIL (A1).** The direction is consistent: DEV, chk, early, X1, θ 0.25 and every year are all positive. But the evidence is weak (HOLD t 1.51, DSR 0.25), concentrated in one month, and the absolute threshold's bite is unstable across regimes. It is not deployable under the protocol. If pursued, it needs a new pre-registered test on forward data: log csv_30 continuously, including when the cut is crossed before each fill. A regime-stable normalisation would be a new idea, not a re-test.
