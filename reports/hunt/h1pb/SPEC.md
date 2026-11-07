# H1 (PB): perp-only wicks and rips on Coinbase US perps, fills checked on trade prints

Fixed before any build. Read reports/hunt_prereg.md and reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
On Coinbase's US perp-style futures (alt books since Dec 2025, majors since Jul–Sep 2025), forced flow sweeps thin
books far from the spot-implied price while spot barely moves.
- **Downward wicks:** FCM liquidations of retail longs, stop orders and market sells.
- **Upward rips:** short squeezes and forced buy-ins.

A resting order k basis-sigmas from the spot-implied fair value supplies the missing liquidity. It is paid when the
perp converges back to spot. Earlier perp-priced replays found these wicks big and frequent (Sharpe 5–9 on
candles), but most of the P&L came from minutes when spot never reached the level, and fillability was never
checked. **This build answers whether resting orders would really fill there, at what size, and what is left after
2× costs.**

## Universe and data
- **Universe:** every Coinbase crypto perp in common.PERP, from its first day of trading. Each trade must pass the
  $150 contract rule at that moment. Today AVAX, DOT and SHIB fail.
- **Perp data:** 1-minute candles in /home/claude/crypto-edge/data/cfm (volume in contracts there; common.load_perp
  converts to coins).
- **Spot data:** Coinbase spot 1-minute candles in data/minute.
- **Trades:**
  - Fetch perp trade prints (common.TradeFetcher, on Actions) for every candidate window: from the candidate minute
    to the minute after the exit horizon.
  - For the spot-synchronous variant, also fetch spot trades for the same windows.
  - Candidate windows come from candles: minutes whose perp low (high) crossed the level by at least one tick.
    Pad by one minute each side.
- **Scored days:** gates.ERA_DAYS from the coin's first perp day (in practice Jul 2025 → Nov 5 2026).
  - DEV ends 2026-05-31.
  - HOLD (Jun 1 – Nov 5 2026) is fetched with the rest, but untouched until the freeze.

## Levels (fixed)
- **Basis:** b_t = log(perp close / spot close) on minutes where both traded.
- **Fair value:**
  - b̄ = the trailing 24-hour median of b, known at t−1.
  - F_t = spot close at t−1 × exp(b̄).
- **Residual and its sigma:** e = b − b̄; σ_e = the trailing 3-day standard deviation of e (minutes where both
  traded), known at t−1.
- **Orders:**
  - Long bid at F × exp(−k σ_e).
  - Short offer at F × exp(+k σ_e).
  - Both on the perp tick grid (bid rounded down, offer up).
- **Spot-synchronous variant:**
  - Use the last spot trade at least 1 s before each perp print, instead of the t−1 spot close.
  - The order re-prices with spot, so a market-wide move does not fill it; only a perp-specific dislocation does.

## Trades
- **Entry:** fill when perp prints trade through the level by at least one tick (prints strictly beyond the level).
- **Size:**
  - target $10K notional per order;
  - capped at θ × the summed size of prints strictly beyond the level, counted from the first print beyond it while
    the price stays beyond it;
  - θ = 0.5; 0.25 also reported.
- **Take-profit:** post-only, at 60% of the way from the level back to F at entry. It fills when prints trade
  through it by one tick.
- **Time exit:** market exit after H minutes (H = 60; variant 15). Priced at the first print at least 2 s after the
  deadline, worse by 1.5× half-spread.
- **No stop-loss.**
- **Limits:** one position per coin and side; at most 6 open. Gross notional ≤ 3× sleeve capital.
- **Costs:** common.perp_cost_bp (maker on entries and take-profits, taker on time exits) plus common.perp_funding_bp
  for the hold. 2× for gates.

## Sleeve capital
$30K and $50K (Path B). The $10K order target is the same at both. The gross cap scales with capital.

## Trial grid (≤ 24; log every one)
- **Core grid:** side × depth × latency mode = 18 trials.
  - side ∈ {long, short, both};
  - k ∈ {3, 4, 6};
  - latency mode ∈ {minute (t−1 spot close), spot-synchronous}.
- **H = 15:** +1 trial, for the best of the 18.
- **Maintenance-hour split** (idea #6 merged here): +1 trial for the best variant with no orders 4:55–6:05 pm ET,
  and +1 with orders only in that window. Both are logged.
- **Selection:** the highest DEV alpha t with at least 40 trades.

## Checks to report
- **Match of perp candles to prints:** the share of candle-implied candidate fills that the prints confirm.
- **Realised capacity:** the distribution of fill sizes and the share of the $10K target filled.
- **Spot-confirmed vs perp-only fills:** net bp in each group.
- **Calendar:** P&L by month since each perp listed. Is the edge decaying as books fill in?
- **Concentration:** the top-3 days' share of P&L.
- **Correlation:** with the incumbent.
