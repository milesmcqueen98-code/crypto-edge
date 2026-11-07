# H3 (LM): bids beyond estimated liquidation clusters, the testable proxy for "public liquidation levels"

Fixed before any build. Read reports/hunt_prereg.md and reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
Leveraged longs opened at a price e are liquidated near e × (1 − 1/L + m), where L is leverage and m the maintenance
margin. When many positions opened in the same price band, their liquidation prices cluster. A cascade that reaches
the cluster feeds on itself until the cluster is spent, then stops. A bid just beyond the densest cluster buys from
the last forced seller.

**Why this is a proxy:** Hyperliquid publishes live positions and liquidation prices, but no history exists (probes),
and Binance/Bybit open interest isn't available live to a US bot. So the history-testable version estimates entries
from Coinbase's own volume-at-price, which is live-available. Binance open interest may be used **only** as a
research cross-check of the estimate (not as an input).

## Universe and data
- **Coins:** BTC, ETH, SOL, XRP. Traded on Coinbase perps from launch; spot-priced with perp costs before.
- **Data:**
  - Spot 1-minute candles: data/minute_early 2021–23, data/minute 2024–26.
  - Perp 1-minute candles (data/cfm), added to volume-at-price from their launch.
  - Optional cross-check: Binance 5-minute open interest in data/alt/binance/metrics_*.
- **Scored days:** gates.ERA_DAYS; DEV ends 2026-05-31.

## The estimate (fixed)
Done hourly, at the top of each hour, using data to t−1.

1. **Volume-at-price:** over the trailing N days, in 0.25% log-price buckets, from 1-minute (typical price,
   volume). Each minute's volume is a candidate leveraged-long entry, decayed with a 3-day half-life.
2. **Survival:** a bucket's entries survive only while the price has not traded below its liquidation price since
   entry (computed per leverage tier).
3. **Leverage tiers:** L ∈ {10, 20, 50} with weights {0.5, 0.3, 0.2}, maintenance m = 0.5%.
4. **Density:** liquidation density D(p) = Σ surviving entries × weight, mapped to their liquidation bucket.
5. **The bid:** inside the depth range R below the current price, find the bucket with maximum D. Place the bid one
   bucket (0.25%) below it, on the tick grid.
6. **Cancel:** replace the bid every hour. Cancel if the cluster is consumed (the price traded through it without
   filling us).

## Trades
- **Fill:** trade-through by at least one tick (candles; perp prints for post-launch fills). Size ≤ θ ×
  through-volume, θ = 0.5.
- **Take-profit:** post-only, 50% of the way from the fill back to the price at placement.
- **Time exit:** market exit after H minutes.
- **No stop.**
- **Sizing:** one position per coin, notional = 1× sleeve capital; gross ≤ 2×.

## Mechanism test inside DEV (decides whether the idea continues)
- **Control:** same coins, same hours, same fill rules. The bid is placed at the **same depth below the price (in
  σ units)** as the density bid, but at a random bucket within R, with a fixed seed.
- **Rule:** if the density bids do not beat the control on DEV (paired t of per-event net bp ≥ 2), stop. The idea
  fails at the screen, and HOLD is not read. The control runs are logged as trials too.

## Trial grid (≤ 24, including controls)
- **Core grid:** 8 density trials plus their 8 controls = 16 logged trials.
  - N ∈ {7, 14} days;
  - R ∈ {[−1.5%, −5%], [−3%, −10%]};
  - H ∈ {60, 240} minutes.
- **Binance check:** for the best trial only, a research check that estimated cluster locations line up with
  Binance open-interest drops (descriptive, not a trial).
- **Selection:** the highest DEV alpha t with at least 40 trades, provided the mechanism test passed.

## Checks to report
- Where fills land relative to the cascade low.
- Net bp, density vs control.
- Fills per year.
- Top-3 days' share of P&L.
- Correlation with the incumbent.
