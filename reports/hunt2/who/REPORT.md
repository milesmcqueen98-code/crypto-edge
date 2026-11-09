# WHO: who sold into our bid? REPORT (builder flow, Path A)

**Verdict: FAIL.** A1 (HOLD t 0.59), A2 (X1 −0.02 bp/day) and A3 (chk −0.12 bp/day) fail; A4 passes. All 16 DEV variants were below the incumbent, and the frozen one is the least bad.

## Mechanism
The ladder is paid by forced, uninformed sellers (liquidations, stops, panic: bursts of many small aggressive orders into a thinning book) and loses to informed sellers (news, metaorders: large, concentrated, persistent aggression, or makers repricing without aggressive selling). WHO reads the composition of the aggressive selling before our fill in Coinbase's public trade feed and cancels the 4σ bid, and with it the ladder's deeper rungs, when the selling looks informed.

## Data
- Research parents (R2-08's AI-approved 4σ fills on the frozen dataset), joined 1:1 on (fill minute, coin): DEV 1,155 (2025-01-01..2026-03-31; 189 days, 16 coins); HOLD 412 chk + 744 early.
- Coinbase spot prints from 30 minutes before to 2 minutes after each fill minute (runs in reports/hunt2/parents/RUNS.txt). All 2,311 windows have prints (DEV median 7,396). t_fill is the first print strictly through the level (DEV 1,154 of 1,155); the 1 DEV and 15 HOLD parents without one use the minute + 30 s. Features use prints ≥ 1 s before t_fill (scripts/hunt2/parent_features.py).
- Features (none missing): sell_bigadv_share_W (share of aggressive-sell dollars in orders ≥ 5 bp of 30-day ADV), sell_hhi_W, sell_share_W (aggressor-sell share of all dollars), rate_ratio_1/5 (print rate vs the 30-minute average). All are order-free; the print-order deviation (d0eb624) touches only ret_bp/dist_lvl, which are unused.
- HOLD features were derived after both freezes (run 42545423910, commit d3fb237). The same run regenerated the DEV file byte-identically, so the DEV thresholds and the HOLD values come from one pipeline.

## Rule and threshold
Skip a parent when its feature lies in the SPEC's tail. The threshold is the numpy quantile of the DEV parents' values at the level that removes that share of all 1,155 DEV parents (missing features kept), then fixed in absolute units. Every variant removed exactly 174 (15%) or 347 (30%) DEV parents. A skip sets frozen_sim.SKIP on the parent's (fill minute, coin) cell: the bid and deeper rungs carry about $0, freed cash follows the engine-faithful cash rule, and the coin stays occupied for the ladder's window (the shared semantics, i.e. "skip this ladder").

## DEV trials (sel, X2, $250K; paired HAC t vs the incumbent, whose DEV Sharpe is 1.62; events = parents skipped)
| Variant | Skip when | Thr | Events | t | bp/day | ΔSharpe |
|---|---|---|---|---|---|---|
| bigadv5_15 | sell_bigadv_share_5 high | 0.4991 | 174 | −2.62 | −0.93 | −0.47 |
| bigadv5_30 | same | 0.3590 | 347 | −1.25 | −0.94 | −0.51 |
| bigadv15_15 | sell_bigadv_share_15 high | 0.4829 | 174 | −1.00 | −0.35 | −0.12 |
| bigadv15_30 | same | 0.3553 | 347 | −2.46 | −1.31 | −0.64 |
| hhi5_15 | sell_hhi_5 high | 0.1001 | 174 | −1.40 | −0.43 | −0.18 |
| hhi5_30 | same | 0.0546 | 347 | −0.91 | −0.57 | −0.19 |
| hhi15_15 | sell_hhi_15 high | 0.0516 | 174 | −0.85 | −0.25 | −0.02 |
| hhi15_30 | same | 0.0314 | 347 | −0.30 | −0.15 | +0.15 |
| sshare5_15 | sell_share_5 low | 0.4704 | 174 | −0.61 | −0.35 | +0.05 |
| sshare5_30 | same | 0.5594 | 347 | −0.84 | −0.63 | +0.10 |
| sshare15_15 | sell_share_15 low | 0.4905 | 174 | −1.90 | −0.95 | −0.48 |
| sshare15_30 | same | 0.5541 | 347 | −1.16 | −0.95 | −0.46 |
| rate1_15 | rate_ratio_1 low | 0.7410 | 174 | −1.00 | −0.44 | −0.07 |
| rate1_30 | same | 1.1056 | 347 | −0.21 | −0.25 | −0.11 |
| **rate5_15** | rate_ratio_5 low | 0.8127 | 174 | **−0.18** | −0.11 | +0.17 |
| rate5_30 | same | 1.0688 | 347 | −1.17 | −0.89 | −0.30 |

The mechanism's sign is contradicted exactly where it is sharpest. The "informed-looking" tails (blocks, low aggressor share) were the better parents: skipping them cost up to 1.3 bp/day (t −2.6, −2.5, −1.9). The frozen variant's neighbours agree in sign: all four rate-ratio variants are negative.

## Frozen variant
rate5_15: skip when rate_ratio_5 < 0.812699, i.e. prints in the last 5 minutes run below 0.81× the 30-minute rate, a slow drift into the level. It was selected by the SPEC's rule (highest DEV t). frozen.json is at fadf819 (code e1f6538): DEV t −0.18, −0.11 bp/day, ΔSharpe +0.17.

## HOLD (read once) and gates
| | DEV | chk | early | HOLD |
|---|---|---|---|---|
| Skipped / parents | 174/1,155 | 53/412 (12.9%) | 111/744 (14.9%) | 164/1,156 |
| Mean diff X2, bp/day (t) | −0.11 (−0.18) | −0.12 (−0.36) | +0.18 (0.83) | +0.11 (0.59) |
| Mean diff X1, bp/day (t) | — | −0.36 (−1.00) | +0.08 (0.39) | −0.02 (−0.11) |
| Sharpe X2, cand / inc | 1.79 / 1.62 | 1.74 / 1.61 | 1.33 / 1.13 | 1.44 / 1.26 |

- **A1 FAIL** (HOLD t 0.59 < 2). **A2 FAIL** (X1 −0.02 bp/day). **A3 FAIL** (chk −0.12). **A4 pass.**
- Years at X2, candidate (incumbent): 2022 8.4% (6.8%), 2023 8.6% (8.9%), 2025 14.0% (15.6%), 2026 10.0% (9.2%).
- All three eras together: t 0.16, +0.04 bp/day. Deflated Sharpe 0.19 (N = 4,598, vz 1.126). The HOLD top-5 days are 264% of the net gain: one day (2022-01-22, +147 bp) exceeds the HOLD total (+106 bp), and without the top five the difference is −174 bp.
- θ 0.25 at S (reported): HOLD −0.02 bp/day (t −0.13); chk −0.36, early +0.08; DEV −0.62 (t −1.15).
- On the incumbent's ten worst DEV days (−11.5% summed at X2) the candidate loses 2.7 points less (2.3 at S).

## Capacity
WHO is a filter only. Per-fill size (0.2% of ADV, θ × the volume beyond the level) is unchanged, and freed cash can fund other signals, so there is no loss of the incumbent's capacity; it trades about 15% fewer ladders.

## Fill-realism checks
- Features are measured 1 s before the first trade-through print, from the exact aggressor side (maker side "BUY" = aggressive sell), with no bulk classification.
- Every skip cell is asserted to land on a simulator parent in every era. The HOLD skip share (12.9–14.9%) matches DEV (15.1%) because the rate ratio is self-normalised; by year it is 2022 13.0%, 2023 16.6%, 2025 15.0%, 2026 Q1 15.3%.
- Costs, fills and latency are the frozen simulator's (published fee tiers ×2 at X2, print-measured exits); nothing is re-modelled.
- Not modelled: live, the rule must run continuously on the market_trades feed and cancel the resting post-only bid before the trade-through. A state change in the last second cannot be acted on.

## Weaknesses
- No mean edge on DEV in any of the 16 variants; the frozen one is a selection among negatives.
- The HOLD sign flips between eras and between cost settings, and the HOLD total rests on one day.
- The consistent ΔSharpe gain (+0.13 to +0.20 at X2 in every era, with the incumbent's worst days helped) suggests the slow-drift tail adds variance at about zero mean. The pre-registered paired test does not measure that, and it is not claimed here.
- Coinbase spot prints see only part of the selling (perp venues lead cascades).

## Verdict
**FAIL.** The composition of the pre-fill aggressive selling (blocks, concentration, aggressor share, frenzy vs drift) did not separate good from bad R2-08 fills on DEV, and the least-bad variant fails A1–A3 on HOLD. Do not deploy; as a mean filter it is not worth a forward test.
