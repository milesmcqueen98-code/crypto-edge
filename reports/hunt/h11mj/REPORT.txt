# H11 (MJ): deep hourly bids on BTC/ETH/SOL/XRP perps. Verdict: FAILS (G1, G2, G3, G4; G5 passes)

Builder h11mj (also built H3), 2026-11-07. Branch hunt/h11mj.
- **Code:** scripts/hunt/h11mj/mj.py, plus dev_log.py and finalize.py.
- **Freeze:** commit dc1a462.
- **Gate series:** prints re-run at 693c9dc.

## Mechanism
- **The bet:** forced selling (liquidations, stops, market dumps) punches through thin books on the majors. A post-only
  bid far below the price buys from it and is paid by the snap-back.
- **Where it came from:** H3's random-depth control arm made money on DEV, at about 7σ and 4.5% deep. H11 tests that
  directly.
- **Bid rule:** every hour, P·exp(−kσ). σ is the trailing 3-day std of 1-hour spot returns; P is the spot close at
  t−1.
- **Venue:** Coinbase perps from the day after launch (BTC/ETH 2025-07-19, SOL/XRP 2025-08-16). Before that,
  spot-priced on the perp tick grid with perp costs.

## Data (fixed rules as SPEC; R3 venue rules applied before any result)
- **Spot:** 1-minute candles. minute_early from 2021-12 and minute from 2024-01; 2024 only trains the AI and is
  never scored.
- **Perps:** cfm 1-minute candles, plus perp prints for every post-launch trade.
- **Decision hours:** BTC 17,407 / ETH 13,773 / SOL 8,782 / XRP 4,030 in 2022–23; about 12,290 each in 2025–26 DEV.
  - ETH, SOL and XRP lose hours in 2022–23 to the contract ≥ $150 rule.
  - XRP's spot data has a gap in 2021–23.
- **Fair Value Limit:** bids are floored at 0.95·P.
  - For k = 9 the floor binds in 22–96% of hours: SOL 79–96%, BTC 22–32%. The frozen bid is mostly "5% below
    spot".
- **Halts and fills:**
  - No activity in the Friday 5–6 pm ET halt.
  - 2-minute halts after ±10% moves.
  - A fill needs a one-tick trade-through. Size ≤ θ·through-volume; whole contracts.
  - Take-profit is post-only at 50% of the way back. Otherwise a market exit at fill + H.
  - Gross ≤ 2×.
- **Costs:** common.py at 2×.

## Trials (12 logged with gates.log_trial, idea "h11mj"; DEV, sleeve $30K at 2×, θ = 0.5; candle fills)
| Variant | Trades | Perp | DEV sleeve Sharpe | DEV alpha t (inc $70K) | Return/yr 2× | 1× |
|---|---|---|---|---|---|---|
| k5 H60 BTC+ETH | 393 | 103 | −1.93 | −4.03 | −30% | −11% |
| k5 H60 all four | 565 | 155 | −0.70 | −1.69 | −12% | +12% |
| k5 H240 BTC+ETH | 381 | 101 | −1.94 | −3.47 | −39% | −21% |
| k5 H240 all four | 531 | 146 | −1.51 | −3.04 | −39% | −17% |
| k7 H60 BTC+ETH | 176 | 42 | −0.68 | −1.95 | −5% | +4% |
| k7 H60 all four (best core) | 318 | 79 | 1.25 | 1.05 | +28% | +41% |
| k7 H240 BTC+ETH | 174 | 42 | −0.39 | −0.97 | −2% | +6% |
| k7 H240 all four | 302 | 75 | 0.57 | 0.51 | +17% | +30% |
| k7 H60 BTC only | 82 | 18 | −0.91 | −2.16 | −1% | +2% |
| **k9 H60 all four (frozen)** | **238** | **48** | **1.78** | **1.93** | **+36%** | **+46%** |
| k7 H60 all + AI (book fills) | 253 | 29 | 1.03 | 0.97 | +23% | +34% |
| k7 H60 all + AI (unit fills) | 246 | 28 | 0.91 | 0.94 | +20% | +31% |

- **Depth decides the sign:** shallow bids (k5) lose to costs. Only the deepest bids on all four coins earn.
  BTC+ETH alone and BTC alone lose.
- **AI:** the walk-forward LightGBM filters from 2022Q3 remove good trades rather than bad ones.
- **Selection rule:** highest DEV alpha t with ≥ 40 trades, giving k9_H60_ALL, frozen and pushed before any HOLD
  computation.

## Gates (Path B, sleeve at 2×; the incumbent at 1×), original vs re-run
| | Original (pre-fix) | Re-run (both fixes) | Bar |
|---|---|---|---|
| a (chosen on DEV) | 0.7 | 0.7 | |
| G1 full alpha t | 1.27 | **1.44** | ≥ 3 → FAIL |
| DEV alpha t (gate series) | 1.23 | 1.38 | |
| G2 HOLD alpha t | 1.24 | **0.83** | ≥ 1.5 → FAIL |
| G2 HOLD book Sharpe gain | +0.38 | **+0.20** | ≥ +0.25 → FAIL |
| G3 full Sharpe gain | −0.07 | **−0.02** | ≥ +0.5 → FAIL |
| G4 DSR (robust v_z 2.51, N 3,137; provisional) | 0.15 | **0.19** | ≥ 0.95 → FAIL |
| G4 DSR, plain-variance v_z (146) | 0.00 | 0.00 | FAIL |
| G5 book years 2022/23/25/26 | +9.5/+11.4/+49.5/+18.1% | **+9.5/+11.4/+50.9/+21.1%** | all > 0 → PASS |
| Sleeve Sharpe full / HOLD | 1.25 / 2.11 | 1.43 / 2.03 | |
| Post-launch rows confirmed by prints | 39 of 68 | 66 of 68 | |

- **Information only, re-run:**
  - At 1×: full alpha t 2.13, HOLD t 1.06, full gain +0.26, HOLD gain +0.30.
  - At θ = 0.25: full t 1.17, HOLD t 0.60.
  - Fee $0.12: full t 1.94; fee $0.30: full t 0.76.
  - Candle fills throughout (no prints): full t 2.15, HOLD t 1.81, full gain +0.22, HOLD gain +0.88.
- **Path A:** not applicable. The sleeve alone has Sharpe 1.43, below the incumbent's 2.47.
- **Sleeve years at 2×:** 2022 +2.2%, 2023 −7.4%, 2025 +80.5%, 2026 +26.3%. At 1×: +15.1%, +2.7%, +87.0%, +29.6%.
- **Where the money is:**
  - 2025 SOL and XRP: +$10.9K and +$9.9K on $30K.
  - ETH lost in 2022–23.
- **HOLD:** 19 trades, +$2.6K on $30K. ETH +$1.5K, XRP +$0.9K, SOL +$0.3K.

## Fill realism (re-run)
- **Prints vs candles:** all 68 post-launch trade rows were re-checked on CDE prints.
  - Print volume in each fill minute equals the candle's contract volume exactly for every trade, with 0 lost
    seconds. The prints are complete.
  - 66 of 68 rows confirmed.
  - Print-supported size is a median 69% of the candle estimate. Candles spread volume evenly over the range, which
    overstates volume below a wick bid.
  - Take-profit share is 0.62 on both; exit prices are identical.
- **Where fills land:** a median 133 bp above the 60-minute cascade low. Only 7% are within 10 bp of it. The bid buys
  mid-cascade, not the end.
- **Capacity:**
  - 80% of trades reach the full $30K. Mean notional $25.8K at θ = 0.5 and $24.9K at θ = 0.25.
  - 256 trades over all scored days: 71 / 56 / 82 / 47 fills in 2022, 2023, 2025 and 2026.
  - 190 are spot-priced (pre-launch) and 66 are on perps. Mean net is 37 bp spot vs 121 bp perp.
- **Overlap with the incumbent:** correlation 0.19. 83% of active days overlap with the incumbent's. On its 10 worst
  days the sleeve lost 1.5% in total (incumbent −19%). Top-3 days carry 26% of P&L.

## Deviations
1. **R3 venue rules** (coordinator, before any result): the 5% Fair Value Limit, halts, and fee sensitivity.
2. **AI** (fixed after a 2024-only smoke test, before the DEV run): a quarter needs ≥ 200 training fills, and a
   constant model keeps every bid. The smoke showed a constant model drops all bids.
3. **Print units (my code; found after the first HOLD read).**
   - CDE print `size` is in contracts. The check treated it as coins, which wrongly rejected every XRP trade and
     overstated BTC/ETH capacity.
   - Fixed: sizes are multiplied by the contract size.
4. **Shared fetcher paging (found by h9mc; fix 9e22019 from the coordinator).** Prints at page-boundary seconds were
   lost.
   - Prints were re-fetched with the fixed fetcher: 0 lost seconds, about 1–2% more prints.
- **Re-run:** fixes 3 and 4 were applied together, and the frozen k9_H60_ALL was re-run once with no other change.
  - The originals are kept as daily_prefix.parquet and gates_prefix.json.
  - The verdict is unchanged.
- **One intermediate mixed fetch:** three coins on the old fetcher and XRP on the new one. It was overwritten and
  never scored.

## Weaknesses
- **Gate series:** pre-launch history (190 of 256 trades) is spot-priced; only post-launch fills are print-verified.
- **Concentration:** profitability is concentrated in 2025 SOL and XRP. 2023 loses at 2×.
- **Clamping:** the 5% clamp makes "k = 9" mostly a fixed-depth bid.
- **H3 informed the grid:** the DEV choice was partly shaped by H3's control arm, as the SPEC disclosed.

## Verdict
FAIL. Deep hourly bids on the majors earn a modest DEV/HOLD sleeve Sharpe (1.4 / 2.0 at 2×). But they do not span
the incumbent: the full alpha t is 1.44, and adding them lowers the book's Sharpe (−0.02). HOLD misses G2 (t 0.83,
+0.20).
