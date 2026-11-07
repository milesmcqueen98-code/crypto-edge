# H10 (XQ): secondary-book wicks — resting bids in Coinbase's crypto-quoted books (wave 2c)

Fixed before any build. Added after research memo R4, under the same pre-registration (reports/hunt_prereg.md) and
gates. Read reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
In a cascade, market makers pull their quotes from secondary books first: BTC-quoted pairs (ETH-BTC, SOL-BTC,
LTC-BTC …) and USDT-quoted pairs (BTC-USDT, ETH-USDT, SOL-USDT …). They keep the deep USD books. Sellers who hold
those quote assets, or whose stops sit in those books, then sweep near-empty books. The cross price breaks from the
parity implied by the USD books, sometimes by several percent (reported for Oct 10, 2025), and triangular arbitrage
capital takes minutes to return.

A resting bid in the secondary book, a few sigmas under the USD-implied cross, buys from that seller. It exits in the
deep USD book, or in the same book at a take-profit. The incumbent never quotes these books, so this is new capacity
on the same forced-selling days.

## Universe and data
- **Pairs:** every Coinbase spot pair quoted in BTC, ETH or USDT whose base and quote both have USD books, so the
  USD-implied cross exists.
- **Build the list** from the Exchange /products endpoint (online and delisted) and commit it before any price is
  read.
- **Data:**
  - 1-minute candles for each pair: Exchange API (granularity 60, 300 per call, on Actions; history from 2022, or each
    pair's start). Plus the USD legs (data/minute, data/minute_early; fetch any missing).
  - Prints for every candidate fill window: common.TradeFetcher, spot product ids such as "ETH-BTC".
- **Scored days:** gates.ERA_DAYS (2022–23, 2025-01-01 → 2026-11-05). DEV ends 2026-05-31.

## Bids (fixed)
- **Cross residual:** for pair X-Q, c = log(X-Q close) − log(X-USD close / Q-USD close) on minutes where all three
  traded.
- **Fair value:** c̄ = the trailing 24-hour median of c; F = (X-USD / Q-USD at t−1) × exp(c̄).
- **Sigma:** σ_c = the trailing 3-day standard deviation of c, known at t−1.
- **Bid:** in the X-Q book at F × exp(−k σ_c), on the pair's quote_increment.
- **Fill:** trade-through by at least one tick; confirmed on prints wherever they are fetched. Size ≤ θ × through-volume
  (θ = 0.5; 0.25 also reported).
- **Two exits, as variants:**
  - **(a) Same-book take-profit:** post-only at 60% of the way back to F; market exit after H = 60 minutes.
  - **(b) Immediate hedge:** at the first print at least 2 s after the fill, market-sell X on X-USD and market-buy Q on
    Q-USD to restore the quote asset. P&L = the locked-in residual minus both taker legs.

## Quote-asset inventory
- **USDT pairs:** the sleeve holds its capital in USDT (USDT-USD conversion at VIP-1 maker, both ways once a month).
  It is exposed to USDT/USD moves.
- **BTC- and ETH-quoted pairs:** the sleeve holds BTC (or ETH) worth its allocation and shorts the same notional of
  Coinbase's BTC (ETH) perp. The short keeps the inventory neutral; the perp short has costs and funding at 2×.
  - Before the perps' launch (Jul 2025), price the hedge with the perp cost model on spot prices, and flag it.
- **NY access:** whether a New York account can hold USDT on Coinbase is unverified. Report results for USDT pairs
  and for BTC/ETH-quoted pairs separately, so the build plan can drop USDT if needed.

## Sizing
- Per order: min($5K, θ × through-volume).
- One position per pair; at most 6 open.
- Cash in the quote asset, including resting bids at full size, ≤ sleeve capital.

## Trial grid (≤ 24)
- **Core grid:** 12 trials.
  - k ∈ {3, 4, 6};
  - exit ∈ {(a) same-book take-profit, (b) immediate hedge};
  - quote set ∈ {USDT pairs, BTC/ETH-quoted pairs}.
- **Variants on the best:**
  - H = 30 (+1);
  - bids live only while BTC-USD's 15-minute move is below −2σ, i.e. in cascades (+1).
- **Selection:** the highest DEV alpha t with at least 40 trades.

## Checks to report
- Pairs and their volumes.
- Candle-vs-print confirmation rate.
- The largest dislocations, by date.
- Overlap with incumbent fills (same day).
- Top-3 days' share of P&L.
- Correlation with the incumbent.
