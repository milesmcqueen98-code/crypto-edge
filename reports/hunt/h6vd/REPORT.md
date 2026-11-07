# H6 (VD): Coinbase dislocation bids against Bitstamp / perp fair value: REPORT

**Verdict: FAILS.** All 15 DEV trials lose money, even before fees. The frozen variant fails every gate (G1 to G5)
in DEV, HOLD and over all days, at 2x costs and also at 1x. The bids are adversely selected: at a 1-minute horizon
Coinbase leads Bitstamp and the Coinbase perps, so most "gaps" are a stale reference, not a Coinbase-only seller who
gets reversed.

## Mechanism (SPEC, unchanged)
- **Bid:** on Coinbase spot at ref_close(t-1) * exp(gbar - k * sigma_e).
  - gbar: the trailing 24h median of g = log(CB close / ref close).
  - sigma_e: the trailing 3-day std of g - gbar.
  - Both use information through t-1. The reference must have traded in t-1.
- **Fill:** the minute opens above the bid and trades at least 1 tick through it.
  - Size: min($5K, theta * through-volume), theta = 0.5.
  - Through-volume: candle volume spread over the range, scanned up to 15 minutes while the price stays below.
- **Exits:** a post-only take-profit 60% of the way back to fair value. Otherwise a market exit at the next open after
  H minutes.
- **Costs:** common.spot_cost_bp (maker 6 bp; taker 12.5 bp + 2 bp half-spread); 2x for the gates.
- **Book:** one position per coin, at most 6 open; resting bids count against cash at full size.

## Data used
- **Coinbase spot:** 1-minute candles, 2024-01-01 to 2026-11-05, for 34 alts plus BTC (quiet filter only). 2024 is
  warm-up.
- **Bitstamp:** 1-minute candles.
  - 30 alts usable in DEV. AERO, APT, JTO and ZEC had fewer than 2,000 traded minutes before June 2026.
  - Share of minutes Bitstamp traded: 94-96% for ETH, SOL and XRP; 1-3% for ICP, INJ, SEI, GRT and LDO.
- **Coinbase perps:** 19 alts, each from its launch (ETH 2025-07-18 to HYPE 2026-06-05).
  - Share of minutes traded: 2-12% for alts; ETH 86%, SOL 64%, XRP 60%.
- **Scored days:**
  - Bitstamp variants: 2025-01-01 to 2026-05-31 (516 DEV days).
  - Perp variants: from 2025-07-19 (317 DEV days).
  - Frozen variant: 475 days, 158 of them HOLD.
- **Candidate fill-minutes in DEV:**
  - Bitstamp: 861K (k=3), 533K (k=4), 226K (k=6).
  - Perp: 97K, 49K, 15K.
- **Trade prints:** 1,768 fills, a 25% sample (seed 0) of the frozen variant's 7,073 fills. Fetched on Actions with
  common.TradeFetcher: 4,118 requests, 0 errors.

## Trials (DEV; sleeve $30K at 2x; all 15 logged in reports/hunt/trials.csv)
| Variant | Trades | Fills $M | Sleeve Sharpe | Alpha t ($70K) | Gross bp | Net bp 1x | Net bp 2x |
|---|---|---|---|---|---|---|---|
| bi_k3_H30 | 198,498 | 878 | -53.3 | -45.9 | -6.3 | -20.2 | -34.1 |
| bi_k3_H60 | 155,695 | 689 | -54.4 | -47.8 | -6.5 | -19.8 | -33.2 |
| bi_k4_H30 | 141,681 | 641 | -41.4 | -35.2 | -5.8 | -19.7 | -33.6 |
| bi_k4_H60 | 115,015 | 519 | -42.5 | -37.2 | -5.8 | -19.2 | -32.7 |
| bi_k6_H30 | 70,555 | 329 | -28.3 | -23.6 | -4.8 | -18.7 | -32.7 |
| bi_k6_H60 | 60,184 | 280 | -29.2 | -24.7 | -4.8 | -18.2 | -31.7 |
| pe_k3_H30 | 41,087 | 196 | -29.7 | -17.3 | -3.9 | -17.8 | -31.7 |
| pe_k3_H60 | 34,282 | 163 | -29.6 | -17.8 | -4.2 | -17.7 | -31.1 |
| pe_k4_H30 | 23,729 | 114 | -24.3 | -14.5 | -3.4 | -17.4 | -31.4 |
| pe_k4_H60 | 20,302 | 98 | -24.4 | -15.2 | -3.5 | -17.0 | -30.5 |
| pe_k6_H30 | 8,501 | 42 | -17.0 | -10.9 | -3.0 | -17.2 | -31.4 |
| pe_k6_H60 | 7,554 | 37 | -16.9 | -11.5 | -3.3 | -17.0 | -30.7 |
| pe_k6_H30_quiet | 7,013 | 34 | -16.3 | -10.7 | -2.9 | -17.1 | -31.3 |
| pe_k6_H30_quiet_aipos | 5,987 | 29 | -13.5 | -7.8 | -2.7 | -16.8 | -30.9 |
| pe_k6_H30_quiet_aiq50 | 6,491 | 32 | -15.0 | -9.4 | -2.9 | -17.1 | -31.3 |

How the grid ran:
- **Core:** k in {3, 4, 6} x reference in {Bitstamp, perp} x H in {30, 60}.
- **Quiet filter:** added to the best core variant (no bid while BTC's 15-minute move is beyond 2 sigma).
- **AI:** two variants on the better of those two.
  - LightGBM on the SPEC's features, walk-forward by quarter.
  - A model needs at least 6 months of history, so the first perp model is 2026Q2.
  - Bids allowed when pred > 0 ("pos") or pred is at least the training median ("q50").
- **Net bp:** flat across k (-30 to -34 at 2x); a deeper bid only trades less.

## Frozen variant
- **Variant:** pe_k6_H30_quiet_aipos: perp reference, k = 6, H = 30, quiet filter, AI pred > 0.
- **Why:** the highest DEV alpha t (-7.78) among trials with at least 40 trades.
- **Freeze commit:** 1bf0d58 (code 2004966).
- **Reproduced:** the final run gives the DEV numbers exactly (5,987 trades, -30.87 bp).

## Gates (Path B; sleeve at 2x, incumbent at 1x; a = 0.7 chosen on DEV)
| Gate | Value | Bar | Result |
|---|---|---|---|
| G1 all-day alpha t | -8.02 | >= 3 | FAIL |
| G2 HOLD alpha t / book Sharpe gain | -5.03 / -5.68 | >= 1.5 / >= +0.25 | FAIL |
| G3 all-day book Sharpe gain | -10.23 (book -7.44 vs incumbent 2.80) | >= +0.5 | FAIL |
| G4 deflated Sharpe (provisional; recomputed centrally) | 0.00 (N = 3,117) | >= 0.95 | FAIL |
| G5 no losing year (book) | 2025 -37.5%, 2026 -37.1% | all > 0 | FAIL |

- **Sleeve Sharpe at 2x:** DEV -13.5, HOLD -9.0, all days -11.7.
- **At 1x (information):** alpha t -6.96 over all days and -3.70 in HOLD; book gain -6.23; sleeve Sharpe -9.1.
- **Theta 0.25:** essentially the same (alpha t -8.09).
- **Path A:** not applicable.

## Years, capacity, P&L anatomy
- **By year:**
  - 2025 (from Jul 19): 3,486 fills, $17.2M, -31.4 bp at 2x.
  - 2026: 3,587 fills, $17.0M, -29.6 bp.
  - In simple sums, the $30K sleeve loses 179% and 168% of its capital at 2x, so a live sleeve would be wiped out.
- **HOLD:** 1,086 fills, $4.8M, -28.3 bp at 2x and -13.8 bp at 1x.
- **Capacity:**
  - Orders deploy nearly in full: 7,073 fills, $34.2M, average $4,829, 93.7% at the full $5K.
  - Theta 0.25: 89.9% at full size.
  - 201 fills went unplaced for lack of a slot.
  - Capacity is not the constraint.
- **Anatomy:**
  - Take-profit exits are 75% of the dollars and add +17.1 bp.
  - Time-exit remainders cost -19.3 bp (mean -75 bp, median -50 bp each; 5th-percentile excursion -186 bp).
  - Gross is -2.2 bp, before fees of 14.1 bp (1x) or 28.3 bp (2x).
  - Why fees win: the median bid sits 32.6 bp under fair value and the take-profit earns 19.8 bp, too thin for 12 bp
    of round-trip maker fees (24 bp at 2x).
- **Coins:** ETH, SOL and XRP are 82% of the dollars. 18 of the 19 coins lose at 2x; AAVE (8 fills) made +$7.

## SPEC checks
- **Overlap with R2-08** (parent fills, reports/wick1m/trades_main):
  - Same coin and minute: 0.49% of fills. Within 5 minutes: 1.33%.
  - DEV 0.42% / 1.05%; HOLD 0.92% / 2.85%.
  - The trigger is disjoint from R2-08.
- **Net bp by k** (2x):
  - Bitstamp: -33.2 to -34.1 (k=3), -32.7 to -33.6 (k=4), -31.7 to -32.7 (k=6).
  - Perp: -31.1 to -31.7, -30.5 to -31.4, -30.7 to -31.4.
  - Per candidate, without the book: -28.5 to -32.2.
- **Which venue moved first** (6 minutes before the fill: Coinbase falling vs the reference rising):
  - Coinbase-led share: 46-65% with Bitstamp (k=3 to 6), 52-79% with the perp.
  - Frozen variant: 78% Coinbase-led (-30.6 bp), 19% reference-led (-28.8 bp), 2% unclear (-41.0 bp).
  - Both kinds lose.
- **Lead-lag** (1-minute returns, DEV):
  - Coinbase leads every reference: corr(CB_t, ref_t+1) = 0.06 to 0.28.
  - The reverse is -0.03 to +0.05 (ARB 0.16 is the exception).
  - The reference does most of the gap-closing in 45% of frozen fills.
- **Top-3 days:** not meaningful with negative P&L. The three best days offset 0.35% of the loss; 305 losing days
  vs 46 winning days.
- **Correlation with the incumbent** (daily, $100K): -0.36. On the incumbent's 20 worst days, the sleeve lost 37% of
  its capital.

## Fill realism (trade prints, 1,768 sampled fills; prints_summary.json)
- **Fills:** 99.4% of fills (99.6% of dollars) had a print at least 1 tick below the bid, at least 1 s into the
  minute.
  - The first live print was above the bid in 99.7%.
  - 67% of the prints below the bid were sellers hitting bids (maker side BUY).
- **Through-volume:**
  - All prints below the bid in the fill minute: a median 95% of the candle estimate.
  - The first unbroken run only, the strict pre-registered rule: 17%.
  - The strict rule plus the candle estimate for later minutes supports 91% of the simulated dollars.
- **Take-profits:** 99.7% of 1,354 confirmed.
- **Time exits:** the first print at least 2 s after the open is +0.26 bp from the candle open (median 0).
- **Print-adjusted sample P&L:** -32.0 bp at 2x vs -29.7 bp simulated. The loss is not a candle artefact.
- **Other modelling notes:**
  - 0.07% of bids sat at or above the last trade, so a post-only order could have been rejected.
  - Market exits pay common.py's 2 bp half-spread, where the pre-registration text says 1.5x the half-spread. The
    difference is under 0.3 bp per trade.

## Weaknesses and choices
- **Choices fixed before any result:**
  - Bid slots go each minute to the free eligible coins with the most negative gap z at t-1 ($5K bids on $30K allow
    at most 6 bids plus positions).
  - Spot ticks are inferred per coin and month (APT and SEI changed in 2025Q4).
  - The median needs 30 observations and sigma needs 100.
  - The slot is held until the take-profit has fully sold.
  - Take-profit P&L is booked on its own day.
- **AI:** only 2026Q2 had a model in DEV. It allowed 3.4% of the candidates it scored. Rank IC was 0.16, but the
  allowed bids still averaged -22 bp at 2x.
- **Latency:** candle-level only (1-minute latency). A faster bot was not tested.
- **After the freeze:** no redesign and no bug fixes.

## Verdict
**FAIL.**
- Gross P&L is about zero to negative for every k, reference and hold, and 1x costs (14 bp) make it deeply negative.
- Timing is disjoint from R2-08, but the sleeve loses about 30 bp on every dollar.
- Drop H6.
- The useful finding is that Coinbase leads Bitstamp and its own perps at 1 minute. Neither is a sound live
  fair-value anchor for Coinbase spot bids.
