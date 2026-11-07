# H1 (PB): perp-only wicks and rips on Coinbase US perps, fills checked on trade prints

**Verdict: FAIL at 2× costs (Path B).** G1 t 2.07; G2 HOLD t −0.16, gain −0.17; G3 gain +0.43; G4 DSR 0.00
(provisional); G5 pass. Perp-only wicks are real and fill on prints, but after 2× fees they are a thin, fee- and
capacity-sensitive edge confined to 4:55–6:05 pm ET, not the Sharpe 5–9 of the candle replays.

## Mechanism
Forced flow (FCM liquidations, stops, market orders) sweeps thin CDE perp books away from the spot-implied price. A
resting order kσ_e beyond fair value F (spot × trailing-24 h median basis) supplies liquidity and is paid when the perp
converges back to spot.

## Data and fill model
- **Prints:**
  - 33.5M CDE perp prints (20 perps), fetched in candidate windows: the k = 3 superset from 1-minute candles, both
    sides and modes.
  - 298M spot prints (minutes t−1..t of each candidate minute), for the spot-synchronous variant.
  - 478K requests over 44 Actions runs.
  - Print contracts / candle contracts: 0.997 DEV, 1.000 HOLD. Perps lost 0 seconds to the 1,000-print page cap;
    spot lost at most 201.
- **Dates:**
  - BTC/ETH from Jul 19 2025; SOL/XRP from Aug 16; Dec 12 alts from about Dec 15; Feb 28 alts from about Mar 3;
    HYPE from June 2026 (HOLD only).
  - Scored days Jul 19 2025 – Nov 5 2026: 475 (DEV 317, HOLD 158).
- **Fills:**
  - A bid at L fills at L when a print is ≥ 1 tick through L and the previous print is at or above L (the post-only
    order could rest).
  - Size = min($10K target, ⌊θ × contracts of the consecutive prints beyond L⌋), θ = 0.5.
  - The take-profit (60% back to F) is placed 1 s after the fill and fills ⌊θ × through-volume⌋ on runs beyond it.
  - Time exit: the first print ≥ 2 s after fill + 60 min, plus the taker fee and 1.5× the half-spread.
- **R3 venue rules:** orders more than 5% from spot are skipped; halts (including Friday 5–6 pm ET) have no prints,
  so no fills.
- **Costs and slots:** common.py costs ($0.20/contract/side); 1 slot per coin and side, 6 open, gross ≤ 3× capital.

## Candle-vs-print confirmation (headline; DEV, minute-mode candle fills at this SPEC's levels)
| Set | Candle fills | Price confirmed | ≥ 1 contract | Full $10K | Filled share, prints / candle model |
|---|---|---|---|---|---|
| All | 318,644 | 99.8% | 94.7% | 62.9% | 0.75 / 0.83 |
| Alts | 19,769 | 99.4% | 92.5% | 36.9% | 0.56 / 0.42 |
| Majors | 298,875 | 99.9% | 94.9% | 64.6% | 0.76 / 0.86 |
| Alts, 4:55–6:05 pm ET | 1,556 | 98.5% | 89.3% | 28.2% | 0.48 |

The price is essentially always confirmed. Size is the constraint: alts fill the full $10K a third of the time.
Measured on prints, alts carry more volume beyond the level than the candle model assumes (median 1.3–1.9×); majors
carry less (0.73–0.99×).

## Trials (DEV; sleeve $30K at 2×; alpha t on incumbent $70K; all 21 logged)
| Variant | Trades (long / short / both) | Sleeve Sharpe | α t |
|---|---|---|---|
| minute k3 | 34,761 / 34,139 / 59,984 | −23.7 / −23.6 / −27.3 | −13.8 / −14.2 / −15.7 |
| minute k4 | 22,453 / 21,885 / 39,926 | −19.8 / −19.2 / −22.8 | −12.1 / −12.6 / −13.5 |
| minute k6 | 10,231 / 10,106 / 19,020 | −13.4 / −13.3 / −16.9 | −9.3 / −10.2 / −11.0 |
| sync k3 | 12,189 / 10,795 / 22,041 | −16.6 / −15.7 / −19.2 | −10.6 / −10.6 / −11.5 |
| sync k4 | 6,459 / 5,542 / 11,595 | −11.0 / −11.6 / −14.1 | −8.0 / −9.0 / −9.4 |
| sync k6 | 2,948 / 2,272 / 5,080 | −0.80 / −3.53 / −2.09 | −0.81 / −3.47 / −1.94 |
| sync k6 long H15 | 3,097 | −0.93 | −1.25 |
| sync k6 long, no orders 4:55–6:05 pm ET | 2,091 | −1.59 | −2.61 |
| **sync k6 long, orders only 4:55–6:05 pm ET** | **910** | **1.63** | **2.89** |

Minute mode, which uses the t−1 spot close, is run over by market-wide moves (−16 to −22 bp a trade). The rip side
loses everywhere.

## Frozen variant
Spot-synchronous, k = 6, long, H = 60, θ = 0.5, orders only 4:55–6:05 pm ET. Freeze commit 649038b (code 369d3eb).

## Gates (Path B, a = 0.5 chosen on DEV)
| | 2× (gates) | 1× (information) |
|---|---|---|
| G1 full α t ≥ 3 | 2.07 ✗ | 5.59 ✓ |
| G2 HOLD α t ≥ 1.5, gain ≥ 0.25 | −0.16, −0.17 ✗ | 2.57, +1.44 ✓ |
| G3 full gain ≥ 0.5 | +0.43 ✗ | +1.55 ✓ |
| G4 DSR ≥ 0.95 (provisional; recomputed centrally) | 0.00 ✗ | 0.00 ✗ |
| G5 book years (2025 / 2026) | +12.1% / +14.0% ✓ | ✓ |

- **Book Sharpe vs incumbent:** full 3.23 vs 2.80; HOLD 3.47 vs 3.64.
- **Sleeve ($30K, 2×):**
  - DEV Sharpe 1.63 (+$3,461, 910 trades); HOLD 0.52 (+$750, 504 trades); full 1.33 (+$4,212, 10.8%/yr).
  - Max drawdown −3.6% (Oct 10 2025). Years: 2025 +0.1%, 2026 +13.9%.
  - At $50K (a = 0.5) the same dollars barely clear T-bills (HOLD sleeve Sharpe −0.07).

## Capacity actually filled
- Mean filled share of the $10K target 66% (median 97%, 10th percentile 9%); 50% of trades filled it fully; median
  notional $8.9K.
- At θ = 0.25 the sleeve Sharpe is −0.30 (DEV 0.27, HOLD −2.12): take-profits need half the through-volume.

## Other checks (frozen, all days, 2×)
- **Spot-confirmed vs perp-only:** perp-only fills: 1,213 trades, +12.3 bp net (+30.2 gross), +$6,761. Spot-confirmed:
  201 trades, −15.0 bp, −$2,550.
- **By coin:**
  - Alts +$5.7K: XLM +$1,477, ZEC +$900, NEAR +$724, DOGE +$694.
  - Majors −$1.5K. ETH −$2,267 (−14.5 bp; the fee on a 0.1-ETH contract at 2×); BTC +1.0 bp; SOL +2.7; XRP +5.6.
- **Decay:** alt P&L ran +$530–1,140 a month in Jan–Jun 2026, then +$16–280 a month in Jul–Oct. The majors were
  negative most months.
- **Concentration:** top-3 days are 23.5% of P&L.
- **Correlation with the incumbent:** −0.39 (DEV −0.48, HOLD +0.05). +$16 a day on the incumbent's worst 5% of days.
- **ET hour (R3):**
  - Frozen variant: 5–6 pm, 1,197 fills, +$4,627; 4:55–5:00 pm, −$389; 6:00–6:05 pm, −$26.
  - Parent (all hours, DEV): 5 pm ET +$4,154; all other hours −$5,835.
  - 3:45–4:15 pm (margin cutoff): 66 fills, −$89. No effect.
- **Fees (descriptive; gates keep $0.20):**
  - $0.12/contract at 2×: sleeve Sharpe 4.10 (HOLD 4.20).
  - $0.30 at 2×: −2.22 (HOLD −4.23).
  - At 1×: $0.12 → 6.05; $0.30 → 3.26.

## Fill-realism checks
1. Print contracts vs candle volume, per chunk.
2. Kernel unit tests on hand-built tapes.
3. An independent plain-Python recomputation of 70 frozen trades (36 DEV, 34 HOLD, plus the 5 biggest wins and
   losses) from freshly re-fetched prints with the shared fetcher. **70/70 match exactly.**

## Weaknesses
- **Fees decide the sign** ($0.12 strong, $0.30 negative). The all-in CFM fee is unverified.
- **Capacity:** queue position and competition are proxied only by θ, and θ = 0.25 fails.
- **Selection:** the 5–6 pm window was already flagged by earlier perp replays. HOLD shows no incremental alpha.
- **Decay** after June 2026.
- **Short sample:** 475 days.
- **No book history:** the rest condition is proxied by the previous print. Friday no-cancel seconds are not
  modelled.

## Deviations
1. **R3 venue facts:** ±5% Fair Value Limit, no fills in halts, ET-hour table, fee sensitivity.
2. **Fetcher:** fills came from fetch.Fetcher, a common.TradeFetcher subclass with the same boundary-second fix the
   coordinator later shipped. No fill used the buggy fetcher.
3. **Level inputs v2.** Found after seeing DEV trigger and confirmation counts, before any DEV P&L.
   - v1 forward-filled stale b̄/σ_e over windows too thin to estimate them.
   - Its 720-minute floor blanked 12–52% of thin-alt time, against "from its first day".
   - v2 floors are 20 (24 h median) and 100 (3-day std) both-traded minutes.
   - Alts rerun in full; majors rerun on their 3.6–5.7K changed rows (first days after listing), with 0 level flips
     elsewhere.
4. **HOLD fetch** restricted to the frozen variant's own candidate superset (exact). DEV/HOLD spliced at
   2026-05-31 10:00 UTC.
5. **Choices:**
   - Minute-mode order live from t + 1 s to t + 61 s.
   - Take-profit rounded toward L.
   - P&L booked on the final close day.
   - Shards 14 and 15 split into sub-runs.

## Shared-code problems
1. TradeFetcher dropped prints at page boundaries (coordinator fix bf70666; I measured BTC perps 2–5% short, spot
   about 10%).
2. ISO-8601 parsing failed under pandas 3 (39aca18).
3. The SHIB tick in common.PERP is 1e-9; the listing implies 1e-8 (no data, so no effect).
4. gates.py's plain v_z is inflated by extreme trials, including my 18 losing grid trials.

## Verdict
**FAIL.** The candle replays' Sharpe 5–9 is not reproduced on prints. Fills are real (99.8% of candle fills confirmed
at the price; 70/70 audited trades match). The only profitable piece is perp-only dislocations at 5–6 pm ET on alt
perps, and at the pre-registered 2× costs it adds +0.43 Sharpe to the book (HOLD −0.17).

Re-test only as a new pre-registered idea, and only if an order preview shows an all-in fee of at most about
$0.12/contract. That test should exclude contracts whose fee exceeds about 5 bp (ETH).
