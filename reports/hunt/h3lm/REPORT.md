# H3 (LM): bids beyond estimated liquidation clusters. Verdict: FAILS at the mechanism screen (DEV)

Builder h3lm, 2026-11-07. Branch hunt/h3lm. Code: scripts/hunt/h3lm/lm.py (DEV run at commit 407a549, Actions run
42344311377); outputs in reports/hunt/h3lm/.

## Mechanism
- **The idea:** leveraged longs opened at price e are liquidated near e × (1 − 1/L + m).
  - Where many entries cluster, their liquidations should cluster too.
  - A bid one bucket below the densest cluster should buy from the last forced seller.
- **The testable proxy:** the SPEC's live-available estimate.
  - Entries come from Coinbase spot volume-at-price, plus perp volume from launch, over N days, with a 3-day
    half-life.
  - An entry survives while the spot low has not reached its liquidation price, per tier (L = 10/20/50, weights
    0.5/0.3/0.2, m = 0.5%).
  - Density is measured in 0.25% log buckets and recomputed hourly from data to t−1.
- **The screen:** the density bid must beat a depth-matched random bid in the same coin-hour.
  - Paired t of per-event net bp ≥ 2, at 2× costs.

## Data used (DEV only, every day before 2026-06-01)
- **Coins and windows:** BTC, ETH, SOL and XRP; 2022-01-01 to 2023-12-31 and 2025-01-01 to 2026-05-31; 1,246 scored
  days.
- **Spot:**
  - data/minute_early from 2021-12: 1.10M minutes per coin, with N-day warm-up.
  - data/minute from 2024-12: 0.79M minutes.
- **Perps:** data/cfm volume (common.load_perp, in coins) is added to entries from launch:
  - BTC and ETH from 2025-07-18;
  - SOL and XRP from 2025-08-15.
- **Venue:** bids rest on the perp from the day after launch. Before that they are spot-priced on the perp tick grid
  with perp costs.
- **XRP 2021-23:** spot data covers only Jan 2021 and Jul–Dec 2023. Hours without a full N-day history are skipped.
- **Events per config:** about 92,800–93,000 coin-hours with a valid bid, for example BTC 29,671 / ETH 26,020 /
  SOL 21,057 / XRP 16,044.
- **Binance USD-M hourly OI:** used only in the descriptive cross-check.

## Fixed rules applied (incl. coordinator deviation from R3, applied before any result)
- **Fair Value Limit:** the bid sits within 5% of spot at placement in every era. Clusters deeper than 4.88% are not
  eligible, and the bid is floored at 0.95 × spot on the tick grid.
- **Hours and halts:**
  - No bids, fills or exits Friday 5–6 PM ET.
  - A 2-minute halt follows any ±10% move from the hour's first open.
- **Fill rule:** the minute opens above the bid and trades through it by one perp tick.
  - Size ≤ θ × through-volume (≤ 15 min).
  - Whole contracts; contract worth ≥ $150.
- **Exits:**
  - Take-profit is post-only at 50% of the way back to the placement price, with a one-tick trade-through and TP
    volume capped at θ.
  - Otherwise a market exit at the open H minutes after the fill.
  - No stop.
- **Book:** one position per coin, notional 1× sleeve capital, gross ≤ 2×.
- **Costs:** common.py, $0.20 per contract per side, 1.5× half-spread on taker exits, 1 bp per 8 h funding; 2× for all
  tests.
- **Control:** the density bids' depths in σ units (σ = 1-hour spot σ, trailing 3 days) are permuted with a fixed seed
  within blocks of 25 events of adjacent σ rank. They are placed at that bucket inside R, in the same coin-hour.
  - Achieved match, median depth: 6.61σ vs 6.61σ and 453 bp vs 453 bp (R 1.5–5%); 7.15σ vs 7.14σ and 467 bp vs
    466 bp (R 3–10%).
  - Clipping to R: ≤ 1%.
- **Pass rule (written into the code before the DEV run):** both the SPEC's event-level paired t and a
  day-clustered t (Newey–West, 5 lags, on daily sums) must be ≥ 2.
- **Kernel check:** a brute-force recomputation on 2024 data (never scored) matched the vectorised density to 1e-16,
  with 0 fill-kernel mismatches in 1,468 bids (check_density.py).

## Mechanism test (DEV, 2× costs, per-event net bp, density − control)
| Config | Density fills | Control fills | Mean diff (bp/event) | Paired t | Day-clustered t | Net/fill, density | Net/fill, control |
|---|---|---|---|---|---|---|---|
| N7 R1.5–5 H60 | 537 | 425 | +0.01 | 0.15 | 0.18 | 24.6 | 29.7 |
| N7 R1.5–5 H240 | 537 | 430 | −0.02 | −0.40 | −0.38 | 17.5 | 26.7 |
| N7 R3–10 H60 | 337 | 279 | +0.01 | 0.24 | 0.27 | 57.3 | 67.0 |
| N7 R3–10 H240 | 337 | 297 | +0.03 | 0.88 | 1.00 | 51.4 | 48.1 |
| N14 R1.5–5 H60 | 528 | 413 | −0.04 | −0.86 | −0.96 | 24.6 | 39.5 |
| N14 R1.5–5 H240 | 528 | 413 | −0.08 | −1.35 | −1.09 | 17.6 | 39.9 |
| N14 R3–10 H60 | 334 | 281 | +0.03 | 1.31 | 1.35 | 58.0 | 57.6 |
| N14 R3–10 H240 | 334 | 281 | −0.04 | −1.00 | −1.26 | 51.6 | 73.3 |

- **Result: no configuration passes.**
  - The pooled daily difference across all 8 is t = −0.52 (descriptive).
  - At 1× costs the best t is 1.60.
- **Split by era:** no config reaches 2 in either 2022–23 or 2025–26. The only |t| > 2 is negative: N14 R1.5–5 H240,
  2022–23.
- **Why density "fills" more:**
  - It fills about 25% more often than control, because the max-density bucket sits slightly nearer the price.
  - Per fill it earns no more: Welch t of per-fill net from −1.45 to +0.16.
  - It is the same fishing at the same depth.
- **Where clusters sit:** in 27–33% of hours the densest eligible bucket is the deepest one allowed. The 5% Fair Value
  Limit binds, and the bid is then a fixed-depth bid.
- **Where fills land:** a median of 149 bp above the cascade low (control: 154 bp). Only 3% are within 10 bp of the
  low. Density bids do not catch the end of the cascade.
- **Binance OI cross-check** (best config, hours where the price crossed the cluster vs the control bucket, DEV):
  - Median OI change −1.2 bp vs −7.0 bp.
  - After controlling for the hour's price move, the difference is +6.0 bp, t = 0.41.
  - Crossing an estimated cluster does not coincide with extra position closing on Binance. The estimate does not
    locate forced selling.

## Trials logged (16, gates.log_trial, dev_book at a = 0.7, sleeve $30K at 2×)
| Variant | Trades | DEV sleeve Sharpe 2× | DEV alpha t (inc $70K) |
|---|---|---|---|
| dens N7 R1.5–5 H60 | 481 | 0.65 | 0.48 |
| ctrl N7 R1.5–5 H60 | 393 | 0.74 | 0.65 |
| dens N7 R1.5–5 H240 | 440 | 0.10 | −0.26 |
| ctrl N7 R1.5–5 H240 | 372 | 0.38 | −0.11 |
| dens N7 R3–10 H60 | 302 | 1.86 | 2.46 |
| ctrl N7 R3–10 H60 | 249 | 1.90 | 2.75 |
| dens N7 R3–10 H240 | 277 | 0.86 | 1.25 |
| ctrl N7 R3–10 H240 | 246 | 0.91 | 1.24 |
| dens N14 R1.5–5 H60 | 476 | 0.70 | 0.54 |
| ctrl N14 R1.5–5 H60 | 387 | 1.30 | 1.67 |
| dens N14 R1.5–5 H240 | 436 | 0.22 | −0.19 |
| ctrl N14 R1.5–5 H240 | 363 | 0.79 | 1.18 |
| dens N14 R3–10 H60 | 300 | 1.85 | 2.47 |
| ctrl N14 R3–10 H60 | 253 | 1.50 | 1.63 |
| dens N14 R3–10 H240 | 275 | 0.94 | 1.29 |
| ctrl N14 R3–10 H240 | 236 | 1.66 | 2.91 |

- **Control vs density:** the control matches or beats density in 6 of 8 pairs.
- **What the P&L is:** whatever these sleeves earn comes from deep (~4.5%, ~7σ) hourly-refreshed bids on BTC, ETH,
  SOL and XRP, the incumbent's own kind of mechanism. It does not come from the liquidation estimate.

## Frozen variant, HOLD, gates
- **Freeze:** none. frozen.json records "NO FREEZE".
- **Would-be selection, had the screen passed:** dens N14 R3–10 H60.
  - DEV alpha t 2.47; DEV book gain +0.28; DEV-only DSR ≈ 0 (N = 3,066, v_z = 7.65).
  - DEV sleeve years at 2×: 2022 −4.3%, 2023 +12.0%, 2025 +70.2%, 2026 to May +50.2%.
- **HOLD:** not read.
- **G1–G5:** not evaluated. There is no full-window or HOLD series. On DEV alone, the would-be variant misses G1
  (2.47 < 3), G3 (+0.28 < 0.5) and G4 (DSR ≈ 0).
- **daily.parquet:** holds DEV days only for that would-be variant (s30/s50 at 2×/1×). No HOLD day was computed.
- **Fee sensitivity**, DEV, would-be variant: sleeve return per year at 2× is 45.4% at $0.12 and 27.7% at $0.30 (37.6%
  at $0.20).

## Capacity and fill realism
- **Size:** 90% of trades reach full $30K size at θ = 0.5.
- **Counts:** about 300 fills in 3.4 DEV years. 233 are spot-priced (pre-launch) and 67 on perp candles.
- **Fills are candle-based, not trade-verified.** That would matter only if the idea had passed.

## Weaknesses
- The proxy cannot see real leverage, entry or exit, or other venues' positions.
- The 5% Fair Value Limit truncates the deepest clusters.
- 2022–23 is spot-priced with perp costs.

## Verdict
FAIL at the pre-registered mechanism screen. Volume-at-price liquidation clusters add nothing over a random bid at
the same σ-depth. Per the SPEC the idea stops; HOLD was never read.
