# H6 (VD): Coinbase-specific dislocation bids against an outside fair value

Fixed before any build. Read reports/hunt_prereg.md and reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
Some selling hits Coinbase alone. Examples: US retail market sells from the Coinbase app, US-hours news, and
Coinbase-specific stop orders or liquidity gaps. Other venues don't move, and cross-venue arbitrage needs inventory
on both sides, so it is slow. A bid on Coinbase anchored to an outside fair value catches these dislocations and is
paid when arbitrage closes the gap.

R2-08's level is anchored to BTC on Coinbase itself. This idea's trigger is the venue gap, so it can fire on dips
R2-08 ignores (Coinbase-only, under 4σ vs BTC) and stays out of market-wide cascades.

## Universe and data
- **Universe:** coins in both data/minute (Coinbase spot) and data/bitstamp: 34 alts, 2024-01 → 2026-11. BTC is
  the market reference, not traded.
- **Fair-value references (live-available in the US):**
  - (a) Bitstamp 1-minute close.
  - (b) Coinbase's own perp (data/cfm), from each perp's launch.
- **Trades:** spot trades for a 25% sample of candidate fills (TradeFetcher on Actions), to confirm fills and measure
  through-volume.
- **Scored days:**
  - 2025-01-01 → 2026-11-05 (Bitstamp data starts 2024; 2024 is warm-up and AI training only).
  - The perp-reference variant scores from each perp's launch.
  - DEV ends 2026-05-31.

## Bids (fixed)
- **Gap:** g_t = log(Coinbase close / reference close) on minutes where both traded.
- **Median:** ḡ = the trailing 24-hour median of g, known at t−1.
- **Residual and sigma:** e = g − ḡ; σ_e = the trailing 3-day standard deviation of e, known at t−1.
- **Freshness guard:** the reference must have traded in minute t−1, or no bid.
- **Bid:** on Coinbase spot at reference_close(t−1) × exp(ḡ − k σ_e), on the spot tick.
- **Fill:** trade-through by at least one tick on Coinbase candles. Size ≤ θ × through-volume, θ = 0.5 (0.25 also
  reported).
- **Take-profit:** post-only, 60% of the way back to fair value.
- **Time exit:** market exit after H minutes (H = 60; variant 30), at the next minute's open, worse by the half-spread.
- **Costs:** spot maker on entries and take-profits, taker on time exits (common.spot_cost_bp). 2× for gates.

## Sizing
- Per order: min($5K, θ × through-volume).
- One position per coin; at most 6 open.
- Cash, including resting bids at full size, ≤ sleeve capital.

## Trial grid (≤ 24)
- **Core grid:** 12 trials.
  - k ∈ {3, 4, 6};
  - reference ∈ {Bitstamp, Coinbase perp};
  - H ∈ {30, 60}.
- **Market-quiet filter:** +1 for the best: no bid while BTC's 15-minute move is beyond ±2σ, to keep it out of
  market-wide cascades.
- **AI filter:**
  - LightGBM on features at t−1: gap z, coin 15/60-minute residual vs BTC, BTC moves, volume ratios, hour,
    weekend, coin.
  - Walk-forward by quarter from 2025Q2.
  - +2 trials.
- **Selection:** the highest DEV alpha t with at least 40 trades.

## Checks to report
- Overlap with R2-08: the share of fills in the same coin-minute as an incumbent fill (reports/wick1m/trades_main
  for parents).
- Net bp by k.
- Bitstamp-led vs Coinbase-led gaps: did Coinbase or Bitstamp move first?
- Top-3 days' share of P&L.
- Correlation with the incumbent.
