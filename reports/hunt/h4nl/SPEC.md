# H4 (NL): liquidity for new Coinbase listings in their first 30 days

Fixed before any build. Read reports/hunt_prereg.md and reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
A new Coinbase spot listing opens with thin books and no market-maker inventory. Meanwhile airdrop recipients, early
investors and unlocked holders want out. Their market sells sweep the book, and the price snaps back as buyers and
market makers arrive. A resting bid several sigmas under a short-horizon fair value supplies that liquidity.

These coins are never in R2-08's universe. Capacity is tiny per event, which is exactly why large funds ignore it.

## Universe and data (survivorship-free)
- **Universe:** every Coinbase USD spot product whose first trade was 2022-01-01 or later, **including delisted
  products** (Coinbase still serves their candles; reports/hunt/probe2.json).
  - Excluded: stablecoins, fiat-backed and wrapped assets (USDT, DAI, PYUSD, USDS, GUSD, EURC, cbBTC, cbETH, wBTC,
    etc.), and coins listed on Coinbase before 2022 and relisted.
- **Listing time t0:** the first 1-minute candle with volume. Cross-check against Advanced Trade's `new_at` where it
  exists.
- **Data:** 1-minute candles for days 0–30 after t0, fetched on Actions (Exchange API candles, 300 per request).
  BTC 1-minute is in data/minute(_early) for context.
- **Trades:** fetch spot trades (TradeFetcher works for spot) for a random 25% sample of candidate fill minutes.
  Report how often prints confirm the candle-based fill, and the realised through-volume.
- **Scored days:** gates.ERA_DAYS. Listings from 2024 are used only to train the AI variant. DEV ends 2026-05-31.

## Bids (fixed)
- **Warm-up:** start 2 hours after t0. Never trade the opening auction or the first two hours.
- **Fair value:** F_t = the VWAP of the last 60 minutes, known at t−1.
- **Sigma:** σ_t = the standard deviation of 1-minute log returns over the trailing min(1,440, minutes since t0)
  minutes, × √60, known at t−1.
- **Bid:** at F × exp(−k σ), on the product's tick (quote_increment from the Exchange product list).
- **Fill:** trade-through by at least one tick on candles. Size ≤ θ × through-volume (candle volume spread over its
  range), θ = 0.5 (0.25 also reported).
- **Take-profit:** post-only, 60% of the way back to F.
- **Time exit:** market sale after H minutes (H = 60; variant 30), at the next minute's open, worse by the half-spread.
- **Costs:** spot maker on entries and take-profits, taker plus half-spread on time exits. 2× for gates.
  - Use a 2× half-spread of 10 bp, not 2 bp: new listings are wide. Measure the actual spread on the trade sample
    and report it.

## Sizing
- Per order: min($3K, θ × through-volume).
- One position per coin; at most 6 coins at once.
- Cash used (open positions) ≤ sleeve capital.
- Resting bids also hold cash on Coinbase: count resting bids at full size against capital. If capital is short,
  the most recent listings come first.

## Trial grid (≤ 24)
- **Core grid:** 12 trials.
  - k ∈ {3, 4, 6};
  - window ∈ {days 0–7, days 0–30};
  - liquidity filter ∈ {none, listing's day-1 volume ≥ $1M}.
- **H = 30:** +1, for the best.
- **AI variant:**
  - LightGBM on listing features known at t−1: days since listing, drawdown from the first-day VWAP, volume vs
    day 1, BTC 60-minute move, σ, k-depth in bp.
  - Walk-forward by quarter, first test quarter 2022Q3 (trained on listings before it).
  - +2 trials.
- **Selection:** the highest DEV alpha t with at least 40 trades.

## Checks to report
- Listings per year, and how many were delisted later.
- Net bp by days since listing.
- Survivorship: the result with and without products that are now delisted.
- Spread and depth from the trade sample.
- Top-3 days' and top-3 listings' share of P&L.
- Correlation with the incumbent.
