# H8 (DP): depeg liquidity — patient bids under par for stablecoins and wrapped assets on Coinbase

Fixed before any build. Read reports/hunt_prereg.md and reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
In a scare, holders of a stablecoin or wrapped asset sell at a discount. The forced or panicked sellers are funds
de-risking, liquidations, and holders who can't wait for redemption. Anyone who can wait for par (redemption or
recovery) is paid the discount. On Coinbase the bid is a resting order; the risk is a true default.

## Universe and data
- **Coinbase USD pairs:** USDT, DAI, PYUSD, GUSD, USDS. EURC is excluded (FX, not a peg).
- **Wrapped / liquid-staking:** cbBTC vs BTC-USD and cbETH vs ETH-USD where both trade.
  - The "par" for cbETH is its trailing 30-day median ratio to ETH (staking accrual).
- **Data:** 1-minute candles since each pair's start (2021+), fetched on Actions (Exchange API). Trades for every
  candidate fill window (TradeFetcher).
- **Costs:** Coinbase's fee for stablecoin pairs. Use the published schedule if it differs from VIP 1 (record the
  source and date). 2× for gates.
- **Scored days:** gates.ERA_DAYS; DEV ends 2026-05-31.

## Trade (fixed)
- **Ladder:** resting bids at par × (1 − d) for each d in the ladder. Cash split equally across rungs.
- **Exit:** sell at par − 5 bp (post-only), or by a market sale after T days.
- **Capital:** the whole sleeve capital sits in the ladder. Coinbase holds cash for resting bids, so the sleeve's idle
  return is 0, and the gates subtract T-bills.

## Trial grid (≤ 24)
- **Grid:** 8 trials.
  - ladder ∈ {shallow: 10/25/50 bp, deep: 50/100/200 bp};
  - exit ∈ {take-profit only, take-profit or 7 days};
  - universe ∈ {USDT only, all pairs}.
- **Selection:** the highest DEV alpha t with at least 20 fills.

## Checks to report
- Every depeg episode: pair, depth, duration, recovery.
- Fills per year.
- P&L per episode.
- Worst case if a coin had not recovered (e.g., UST 2022 as a stress case, described, not traded: not on Coinbase).
- An honest power calculation.
