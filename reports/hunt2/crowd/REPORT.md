# CROWD: perp-funding crowding as a filter on the ladder (Path A)

**Verdict: FAIL.** On DEV the hypothesis came out the other way round: skipping coin-days with low or negative funding cost the ladder money (t from −1.97 to −1.82). The frozen variant (skip when BTC's funding is low) was neutral on DEV and lost on HOLD: paired t −1.83. A1–A3 fail; A4 passes.

## Mechanism
When funding is positive, leveraged longs are crowded. A selloff then liquidates them, and the ladder is paid for absorbing that forced selling. When funding is negative, the sellers are voluntary and more often informed, so skipping bids on those days should remove the ladder's worst fills.

## Data
- **Funding:** Hyperliquid daily funding (data/funding), with day d using the value for d−1 (known at 00:00 UTC). Funding was read only for the window each era needs.
- **Coverage:** all 16 coins with DEV parents have their own file except PEPE (no kPEPE file), which uses BTC. ZEC uses BTC before 2025-10-02.
- **Simulator:** the frozen one, at X2, X1 and S, on $250K. There are 1,155 research parents on DEV, 412 on chk and 257 in early from 2023-05-13.
- **Scored days:** all of sel (455) and chk (219), and early from 2023-05-13 (233): 907 days.

## Definitions fixed before any trial (crowd.py docstring, commit b5b0172)
- **Coin series:** the coin's own funding where it exists, otherwise BTC's.
- **m7:** the mean of the values that exist from d−7 to d−1.
- **q25:** the linear 25th percentile over the unique coin-days of DEV parents.
- **Skip:** when the statistic is strictly below the threshold, every minute of the coin's day d is skipped (frozen_sim.SKIP), and only inside the era's own days.

## DEV trials (8; X2, $250K; incumbent DEV Sharpe 1.62)
| Variant | Threshold | Parents skipped | Paired t | Mean diff bp/day | Sharpe |
|---|---|---|---|---|---|
| coin prev 0 | 0 | 245 (21.2%) | −1.85 | −1.23 | 0.98 |
| coin prev q25 | 4.67e−5 | 287 (24.8%) | −1.82 | −1.26 | 1.01 |
| coin m7 0 | 0 | 237 (20.5%) | −1.86 | −1.58 | 0.77 |
| coin m7 q25 | 5.55e−5 | 296 (25.6%) | −1.97 | −1.84 | 0.63 |
| btc prev 0 | 0 | 14 (1.2%)† | +0.14 | +0.00 | 1.63 |
| **btc prev q25** | **2.31e−4** | **280 (24.2%)** | **−0.04** | −0.03 | 1.82 |
| btc m7 0 | 0 | 4 (0.3%)† | −1.29 | −0.02 | 1.61 |
| btc m7 q25 | 1.86e−4 | 308 (26.7%) | −1.33 | −0.86 | 1.20 |

† Below the 10% minimum, so ineligible.

- **Coin-level funding:** every coin-level variant lost 1.2–1.8 bp/day. The ladder earned more on coin-days whose shorts were crowded, which is the opposite of the mechanism.
- **BTC funding:** BTC's previous-day funding was below zero for only 14 parents (1.2%).

## Frozen variant
**btc_prev_q25** (freeze commit 498cb02).
- **Rule:** skip every coin's 4σ bids on UTC day d when BTC's Hyperliquid funding for d−1 is below 0.0002307 per day (about 8.4% a year). That threshold is DEV's 25th percentile and is never recomputed.
- **DEV effect:** it skipped 177 of 455 days and 24% of parents. The paired t was −0.04 and the Sharpe rose from 1.62 to 1.82, because the skip removed variance and return in about equal measure.
- **Runner-up:** btc_m7_q25 (t −1.33).

## HOLD (read once) and gates
X2, with X1 in brackets.

| Gate | Value | Result |
|---|---|---|
| A1: HOLD paired t ≥ 2 | −1.83 (−2.38) | FAIL |
| A2: HOLD mean difference > 0 at X1 | −1.44 bp/day | FAIL |
| A3: positive in every gated era | chk −1.36, early −0.64 bp/day | FAIL |
| A4: no losing candidate year | 2023 +6.3%, 2025 +16.3%, 2026 +5.4% | PASS |

- **Sharpe:** the HOLD candidate scored 1.11 against the incumbent's 1.72 (chk 0.87 against 1.61; early 1.49 against 2.00). Full window: t −1.13, deflated Sharpe 0.04 (N = 4,598).
- **Parents skipped:** chk 182 of 412 (44%). BTC funding was below the DEV threshold on 121 of 219 days, so the fixed level bit about twice as often as on DEV. Early: 60 of 257 (23%).
- **Cumulative difference:** sel −0.14%, chk −2.97%, early −1.49% of $250K. Worst day: 2026-06-05 (−200 bp, a large winning fill that was skipped). The difference sum is negative, so the top-5 share is undefined.
- **The sel run reproduces the DEV trial exactly** (t −0.043).

## Fill realism, capacity, diversification
- **Fills:** the frozen simulator's own (print-measured exits). The filter only removes bids, so the incumbent's capacity per signal is unchanged. The funding input is public and available at 00:00 UTC.
- **Incumbent's 10 worst DEV days:** the frozen variant added +341 bp over them (it helped on 3 of the 10).
- θ 0.25 was not run (not gated; the shared machine's memory was the constraint).

## Weaknesses
- One daily value per coin, compared with a fixed level in a non-stationary series: the HOLD skip rate rose to 44%.
- The funding source is Hyperliquid, not Coinbase, and it starts only in May 2023.
- The selection was by t among variants that were all at or below zero on DEV.

## Deviations
- Two HOLD-read processes were killed by the shared machine's out-of-memory killer (exit 137) before pathA.hold_read wrote or printed anything.
- The third run used the same hold_read with each era's arrays built on demand, the other eras' and tag's caches released, and a wait for free memory (as BURN's hold_lowmem.py). Both incidents and the change were committed before that run (38789d2, ba02dee). Nothing in the rule, the variant or the threshold changed.

## Verdict
**FAIL.** The forced-liquidation story has the wrong sign on DEV for coin funding. Its BTC version is neutral on DEV and costs money on HOLD in both eras.

**Scorecard inputs (suggested):**
- Realism 13/15: public daily input 4, latency 3, capacity 3, costs 3.
- Mechanism 5/10: the forced counterparty is named, but DEV contradicts it.
- Implementability 10/10.
- Diversification 3/5: positive on the incumbent's worst DEV days but helped on only 3 of 10.
- Capacity 5/5.

**Reproduce:** scripts/hunt2/crowd/: dev.py sel, freeze.py, hold.py.
