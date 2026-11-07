# H2 (FR): buying the end of forced deleveraging in BTC/ETH/SOL/XRP on Coinbase perps

**Verdict: FAILS.** At 2× costs the frozen variant fails G1–G4 and passes only G5. All 13 DEV trials had a negative
DEV alpha t. After a cascade the price does rebound, but by only about 5–27 bp gross per trade on the best variants.
That is less than 2× perp taker costs, which are about 22–40 bp round trip.

## Mechanism
- **Who is forced:** leveraged longs, liquidated into a cascade until the forced flow is exhausted.
- **What we do:** we take the other side with a perp taker order at the first up-close after the cascade.
- **Why it should pay:** the price overshoots and partly snaps back.

## Data
- **Signals:** Coinbase spot 1-minute candles, 2021-01-01 → 2026-11-05.
  - XRP has a hole from 2021-03 to 2023-07. It is left as NaN, so no events fall in it.
  - DEV builds loaded data only up to 2026-05-31.
- **Execution:** data/cfm perp candles from the first full UTC day of prints: BTC/ETH 2025-07-19, SOL/XRP 2025-08-16.
  - Before those dates, trades are spot-priced with the perp cost model.
  - The $150 contract rule removes some early trades: ETH in 2022Q4 and SOL in 2022Q4–2023Q3.
- **Perp prints:** common.TradeFetcher on Actions (run 42344649166), covering all 63 post-launch trades, with 0 fetch
  errors.
- **Events at W60 k6:** 740 on scored days.

  | Coin | 2022 | 2023 | 2025 | 2026 |
  |---|---|---|---|---|
  | BTC | 42 | 91 | 39 | 33 |
  | ETH | 35 | 82 | 50 | 36 |
  | SOL | 36 | 62 | 40 | 31 |
  | XRP | – | 68 | 59 | 36 |

  - These give 130 portfolio trades (117 DEV, 13 HOLD) after the exhaustion rule, the AI filter and the two-coin cap.

## Trials (13 of 24, all logged)
The sleeve is $30K at 2× costs, θ = 0.5. "t" is the DEV alpha t on the incumbent at $70K. "Book" is the DEV book
Sharpe at a = 0.7; the incumbent's is 2.35.

| Variant | Trades | SR 2× | SR 1× | t | Gross bp | Net 2× bp | Book |
|---|---|---|---|---|---|---|---|
| W15 k4 φ.3 H60 | 2031 | −7.64 | −4.59 | −14.58 | −2.3 | −32.4 | −4.47 |
| W15 k4 φ.5 H240 | 2341 | −6.06 | −3.79 | −11.29 | −6.8 | −38.7 | −4.63 |
| W15 k6 φ.3 H60 | 644 | −3.98 | −2.24 | −7.26 | 0.5 | −32.0 | −0.79 |
| W15 k6 φ.5 H240 | 800 | −3.48 | −2.26 | −6.25 | −9.3 | −43.2 | −1.67 |
| W60 k4 φ.3 H60 | 973 | −5.06 | −3.25 | −9.20 | −6.6 | −37.6 | −2.32 |
| W60 k4 φ.5 H240 | 999 | −3.38 | −2.29 | −6.07 | −12.8 | −45.3 | −2.01 |
| W60 k6 φ.3 H60 | 327 | −2.13 | −1.13 | −4.11 | 3.5 | −28.7 | 0.45 |
| W60 k6 φ.5 H240 (best core) | 365 | −1.74 | −1.04 | −3.51 | −3.1 | −37.0 | 0.00 |
| + immediate entry | 358 | −0.99 | −0.32 | −2.41 | 12.9 | −21.1 | 0.47 |
| + stop at trough − 1σ | 410 | −2.38 | −1.63 | −5.39 | −9.8 | −42.9 | −0.39 |
| + BTC only | 162 | −1.93 | −1.32 | −3.89 | −6.2 | −34.0 | 0.96 |
| AI on the best core | 146 | −0.36 | 0.00 | −1.36 | 22.4 | −4.1 | 1.37 |
| **AI on W60 k6 φ.3 H60 (frozen)** | **117** | **−0.31** | **0.18** | **−0.95** | **27.0** | **+3.8** | **1.82** |

- **AI trials (rule fixed before any result):** the walk-forward LightGBM filter applied to the two best core trials.
  - Huber regression of net bp. Quarters from 2022Q3, trained on trades that exited earlier (2024 included).
  - A trade is taken if its prediction is above the median of the training predictions.
- **Neighbouring settings:** all agree in sign, and all are negative.

## Frozen variant (freeze commit c2c9149; code f05368e)
- **Event:** W = 60 minutes, k = 6σ, volume ≥ 3× its trailing median.
- **Entry:** exhaustion entry at the next minute's open.
- **Exits:** take-profit at trough + 0.3 × drop; time exit at 60 minutes; no stop.
- **AI filter:** on.
- **Size:** 1× sleeve notional per trade, at most 2 coins.

## Gates (Path B, sleeve at 2× costs)
| Gate | Value | Result |
|---|---|---|
| a (chosen on DEV) | 0.7 | |
| **G1** full alpha t | −1.22 | **FAIL** |
| **G2** HOLD alpha t / Sharpe gain | −1.40 / −0.98 (book 2.66 vs incumbent 3.64) | **FAIL** |
| **G3** full Sharpe gain | −0.56 (1.91 vs 2.47) | **FAIL** |
| **G4** DSR | 0.00 with ledger v_z 9.33; 0.26 with the coordinator's robust v_z 1.50; 0.49 at the 1.126 floor | **FAIL** |
| **G5** book years | 2022 +6.6%, 2023 +13.9%, 2025 +29.5%, 2026 +13.4% | PASS |

- **Sleeve Sharpe at 2×:** −0.35 over all days (DEV −0.31, HOLD −0.65).
- **Sleeve years at 2× ($30K):** 2022 −7.4%, 2023 +1.1%, 2025 +9.1%, 2026 +0.4%.
- **At 1× (information only):** G1 t −0.41, full gain −0.39, sleeve Sharpe +0.13.
- **At θ = 0.25:** t −1.24.
- **Fee sensitivity at 2×:** at $0.12/contract, t −0.74 (sleeve Sharpe −0.07); at $0.30, t −1.79.
- **Path A:** not applicable.

## Checks
- **Net bp at 2× by year:**

  | Year | Trades | Net 2× bp |
  |---|---|---|
  | 2022 | 6 | −123 |
  | 2023 | 15 | +7 |
  | 2025 | 79 | +12 |
  | 2026 | 30 | +1 |

  - HOLD: 13 trades, −7.5 bp, 46% hit rate, 27% take-profit fill.
- **Spot- vs perp-priced:**
  - Spot-priced (pre-launch): 77 trades, gross +38 bp, net 2× +14 bp.
  - Perp-priced: 53 trades, gross +9 bp, net 2× −13 bp.
  - Re-pricing the perp trades on spot gives the same result, gross +8 bp and net −14 bp. The edge decays in 2025–26;
    the venue is not the cause.
- **Prints vs candles (63 post-launch trades):**
  - Entry: the first print ≥ 2 s after the decision was 0.0 bp median and −1.4 bp mean (favourable). The 90th
    percentile was 7.2 bp adverse, against a 1.0–3.4 bp spread allowance.
  - Exits: 0.0 bp median.
  - Delay: 3 s median. Two trades waited 37 minutes and 3.8 hours with no print.
  - Take-profit: prints imply a 58% fill share, against 44% in the candle model. The candle model never filled a
    take-profit that the prints did not, so it is conservative.
- **R2-08 overlap:**
  - The incumbent was active on 93% of our trade days (base rate 32%).
  - 34% of our trade days were among its top-10% |P&L| days (base rate 3%).
  - The correlation is only 0.08, but on the incumbent's worst 5% of days the sleeve made −21%. Both buy the same
    cascades, so it does not diversify.
- **Concentration:** the top-3 days make 367% of a total sleeve P&L of only +3.2%.
- **Drawdown:**
  - Daily max drawdown −12.6% at 2×.
  - Worst intratrade adverse excursion −2,062 bp (ETH, 2025-02-03).
- **Capacity:**
  - Notional is 0.99× capital.
  - Entry-minute perp volume is 14× the order at $30K (p10: 3×) and 4× at $100K.
  - The take-profit fill share is 59% at θ = 0.5 and 56% at θ = 0.25.
- **By ET hour:**

  | ET block | Events | Trades | Net 2× bp |
  |---|---|---|---|
  | 00–08 | 146 | 13 | +65 |
  | 08–12 | 179 | 50 | −1 |
  | 12–15:30 | 105 | 22 | −54 |
  | 15:30–16:30 | 20 | 0 | – |
  | 16:30–17 | 22 | 5 | −14 |
  | 17–18 | 61 | 11 | −51 |
  | 18–24 | 207 | 29 | +47 |

  - Over all 632 standalone trades, the 15:30–16:30 block made −58 bp. The 4 pm cutoff shows no rebound effect.

## Deviations
1. **R3 venue rules applied before any result:**
   - the Friday 5–6 pm ET halt;
   - ±10% two-minute halts, emulated before launch;
   - the Fair Value Limit on the take-profit, which delayed 1 trade;
   - the $0.12/$0.30 fee sensitivity and the 4 pm ET table.
2. **Perp launch** is the first full UTC day of prints.
3. **The take-profit is shifted by the perp/spot basis** at the decision minute. It is never placed at or below entry.
4. **A trade is skipped** if the close is already at or above the take-profit at the decision.
5. **HOLD:** no statistic was computed before the freeze push. Only descriptive scripts (prints.py, diag.py) came after
   it.

## Weaknesses and the shared-code note
- **The edge, if any, is about 15–30 bp gross.** That is below the 2× cost of 22–40 bp round trip.
- **The AI filter's DEV gain is selection noise around zero.** It moves t from −4.1 to −0.95.
- **The perp era is short:** 53 trades.
- **Shared code:** with plain variance, large negative trials inflate G4's v_z (h2fr z down to −8.6). The coordinator
  logged this and recomputes G4 centrally with a robust v_z. It does not change this verdict.
