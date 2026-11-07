# H5 (AN): Binance listing and launch announcements, traded on Coinbase spot

Fixed before any build. Read reports/hunt_prereg.md and reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
When Binance announces a spot listing, perp launch or similar for a token that already trades on Coinbase, Binance
users and arbitrageurs become eager buyers. The token jumps on every venue within seconds.

Professional bots win the first seconds. **The question is what is left, or what reverses, after a polling bot's
delay of 2–30 s on Coinbase spot.** The trade is small per event and latency-bound, so large funds either own the
first second or ignore it.

## Data
- **Events:** Binance's announcement API, catalog 48 ("New Cryptocurrency Listing"). Page every article since
  2022-01-01 on Actions; keep title, code/id and releaseDate (ms).
  - The API answered from a US GitHub runner (probe.json).
  - Classify by title with fixed patterns: (i) spot listing ("Will List"); (ii) futures/perp launch ("Futures Will
    Launch"); (iii) margin/earn/convert additions; (iv) HODLer/Launchpool airdrops; (v) other (dropped).
  - Write the regexes into the code before looking at any price.
- **Tokens:** extract the ticker(s) in parentheses. Keep an event if that ticker had a Coinbase USD spot product with
  trades in the hour before releaseDate.
- **Prices:** Coinbase spot trades from releaseDate − 10 minutes to + 2 hours, per event (common.TradeFetcher on
  Actions; Advanced Trade's window endpoint serves spot history).
- **Scored days:** gates.ERA_DAYS (2022–23, 2025-01-01 → 2026-11-05). 2024 events are used only to train the AI
  variant. DEV ends 2026-05-31.

## Trade (fixed)
- **Entry:** a taker buy at the first Coinbase trade at least Δ seconds after releaseDate. Price = that trade × (1 +
  1.5 × half-spread), plus the taker fee.
  - The half-spread is measured from the prints: the median of |buy-initiated − sell-initiated| / 2 in the 10
    minutes before.
- **Exit:** a market sale at the first trade at least H after entry, worse by the same half-spread, plus the taker
  fee.
- **Size:** min($5K, 1% of the coin's trailing 30-day median daily USD volume on Coinbase).
- **Overlaps:** one position per event. Several events in one article count as several trades.
- **Leak diagnostic (DEV only, descriptive):** price move from −10 minutes to 0. If most of the jump precedes
  releaseDate, say so; the timestamp is then not tradable.

## Trial grid (≤ 24)
- **Core grid:** 18 trials.
  - Δ ∈ {2 s, 10 s, 30 s};
  - H ∈ {5, 30, 120} minutes;
  - event set ∈ {spot listings only, all classes (i)–(iv)}.
- **Fade variant:** for the best Δ, a short via Coinbase perps where one existed at the time. Usually not available
  before Dec 2025; report the count. +1 if at least 20 events.
- **AI variant:**
  - LightGBM on event features at entry: class, market cap rank proxy (Coinbase 30-day volume), the move from −10
    minutes to entry, BTC 60-minute move, hour.
  - Walk-forward by quarter.
  - +2 trials.
- **Selection:** the highest DEV alpha t with at least 20 events.

## Checks to report
- Events by class and year.
- Average path (bp) from −10 minutes to +120 minutes, by class and by Δ (DEV only).
- Share of the move done by Δ.
- Coinbase spread at the event.
- Top-3 events' share of P&L.
- Correlation with the incumbent.
