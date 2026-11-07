# H7 (UL): token unlocks — short the perp ahead of large cliff unlocks

Fixed before any build. Read reports/hunt_prereg.md and reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
Ahead of a large scheduled unlock, recipients (team, investors) and those who expect them to sell hedge or sell
early, often by shorting perps. This produces negative drift into the unlock. Afterwards the overhang is resolved and
the selling pressure fades.

The short is only possible on Coinbase through its perps, so the tradable universe is coins with a Coinbase US perp.

## Data
- **Unlock schedules:** DefiLlama's free dataset CDN, https://defillama-datasets.llama.fi/emissions/<protocol>.
  - The protocol list is at …/emissionsProtocolsList; categories and timestamps are in the JSON.
  - Map protocols to tickers by hand. Write the mapping table into the repo before looking at any price.
- **Unlock event:**
  - a day whose scheduled increase in unlocked supply is at least X% of the circulating supply 30 days before;
  - circulating supply from DefiLlama's series where available, else Coinbase/CoinGecko supply (state which);
  - linear vesting below the threshold is not an event.
- **Prices:**
  - Coinbase spot 1-minute/daily (data/minute, minute_early, prices) for coins that now have a Coinbase perp.
  - Perp-priced from each perp's launch (data/cfm).
  - Before launch, spot-priced with the perp cost model and an extra 10%/yr carry charge. Flag this as
    **hypothetical shortability** in the report; the scorecard penalises it.
- **Scored days:** gates.ERA_DAYS; DEV ends 2026-05-31.

## Trade (fixed)
- **Short:** short the perp d1 days before the unlock at the 16:00 UTC daily close (taker at 2×).
- **Cover:** cover d2 days after the unlock.
- **Hedge variant:** long BTC perp × trailing 30-day beta.
- **Size:** equal notional per event = 50% of sleeve capital; gross ≤ 2× capital (oldest positions first).

## Trial grid (≤ 24)
- **Core grid:** 16 trials.
  - d1 ∈ {7, 14} days;
  - d2 ∈ {0, 3} days;
  - threshold X ∈ {1%, 2.5%} of supply;
  - hedge ∈ {none, BTC beta}.
- **Category split:** for the best, team/investor unlocks only vs all: +1.
- **Selection:** the highest DEV alpha t with at least 20 events.

## Checks to report
- Events by coin and year.
- Mean cumulative abnormal return (vs BTC beta) from −30 to +10 days.
- Hypothetical-shortability vs perp-priced split.
- Top-3 events' share of P&L.
- Correlation with the incumbent.
- An honest power calculation: with this event count, what Sharpe would be needed for t ≥ 3?
