# H2 (FR): buying the end of forced deleveraging in BTC, ETH, SOL and XRP on Coinbase perps

Fixed before any build. Read reports/hunt_prereg.md and reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
In a long-liquidation cascade, leveraged longs are sold regardless of price until the forced flow is exhausted. Then
the price overshoots and partly snaps back. R2-08 only rests bids on alts' BTC-adjusted dislocations; it never buys
BTC itself, and it never enters after the cascade.

This idea buys the majors right after exhaustion, with a taker order on Coinbase's perps. Taker orders there are
cheap: BTC about 3 bp a side, ETH about 9 bp, SOL/XRP 4–5 bp plus spread at 1×. We are paid for supplying risk
capital when forced sellers have just finished.

## Universe and data
- **Coins:** BTC, ETH, SOL, XRP.
- **Signals:** from Coinbase spot 1-minute candles only. These are live-available.
  - data/minute_early: 2021–2023. XRP from Jul 2023.
  - data/minute: 2024–Nov 2026.
- **Pricing:**
  - Before each perp's launch (BTC/ETH Jul 2025, SOL Aug 2025, XRP Aug 2025): spot-priced with the perp cost model.
    Report this split.
  - After launch: perp-priced from data/cfm. Entries and exits are checked on perp prints for the post-launch events
    (TradeFetcher on Actions).
- **Scored days:** gates.ERA_DAYS (2022–23 and 2025-01-01 → 2026-11-05). 2024 is for training the AI variant only.
  DEV ends 2026-05-31.

## Event (fixed definitions; parameters in the grid)
- **Drop:**
  - D_t = log(close_t / max(close over the last W minutes)).
  - σ_W = the trailing 3-day standard deviation of W-minute log returns, known at t−1.
  - The cascade condition holds when D_t ≤ −k σ_W.
- **Forced-flow confirmation:** volume over the last W minutes ≥ 3× the trailing 3-day median W-minute volume.
- **Exhaustion entry:**
  - the first minute after the cascade condition first holds whose close is above its open and above the previous
    minute's close;
  - within 30 minutes of the condition;
  - entry at the next minute's open (candles), or the first perp print at least 2 s after that minute's close.
- **Re-arming:** one position per coin. A coin re-arms only after the price has been above the pre-drop high minus
  0.5 × drop, or after 6 hours.

## Exits
- **Take-profit:** a post-only limit at trough + φ × (pre-drop high − trough).
- **Time exit:** market exit after H minutes.
- **No stop** in the core grid.

## Sizing
- Notional per trade = 1× sleeve capital, so leverage is at most 1× per coin.
- At most 2 coins at once, so gross is at most 2×.
- Funding is charged for the hold at 2×.

## Trial grid (≤ 24)
- **Core grid:** 8 trials.
  - W ∈ {15, 60} minutes;
  - k ∈ {4, 6};
  - exit ∈ {(φ 0.3, H 60), (φ 0.5, H 240)}.
- **Variants on the best core trial:**
  - immediate entry when the condition first holds (no exhaustion wait): +1;
  - a stop at the trough minus 1σ_W: +1;
  - BTC-only: +1.
- **AI variant:**
  - LightGBM regression of net bp on event features, all known at entry: drop size in σ, speed, volume ratio,
    perp–spot basis at the trough (perp era only, else missing), 1-day and 7-day trend, hour, coin.
  - Walk-forward by quarter, first test quarter 2022Q3 (trained on 2021–22Q2).
  - Take trades with a prediction above the median of the training predictions: +2.
- **Selection:** the highest DEV alpha t with at least 40 trades.

## Checks to report
- Events per year and coin.
- Net bp by year.
- The spot-priced vs perp-priced split.
- Perp-print entry slippage vs the candle open, post-launch.
- How often R2-08 was also filling on the same day.
- Top-3 days' share of P&L.
- Correlation with the incumbent.
