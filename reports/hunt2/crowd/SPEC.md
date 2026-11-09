# CROWD: leverage crowding (perp funding) as a filter on the ladder

- **Path:** A (the live bot, bids skipped when crowding says a selloff is unlikely to be forced; frozen simulator).
- **Who is forced or eager, and why we are paid:** perpetual funding prices net leverage demand. When funding is
  positive, leveraged longs are crowded; a selloff then liquidates them (exchange liquidation engines sell at market),
  which is the forced flow the ladder is paid to absorb, and it reverts when the liquidations stop. When funding is
  negative, shorts are crowded and a selloff liquidates nobody: the sellers are voluntary, more often informed, and
  the move is less likely to revert. Skipping bids in short-crowded states should remove the ladder's worst fills.
- **Prior evidence and what has been seen:** the Medallion round tested funding and positioning as DAILY direction
  signals for BTC/ETH (nothing passed); no round has used funding to condition the ladder. Nothing computed on any era.
- **Data:** Hyperliquid daily funding per coin (data/funding/<COIN>.csv, 2023-05-12 ..; coin-level, and BTC as the
  market-wide measure). PEPE uses kPEPE if present, else BTC. The early hold-out era is covered from 2023-05-12 only;
  days before have no signal (the filter is off there and those days are not scored for this idea).
- **Live inputs and orders:** Hyperliquid's public info API (funding history), allowed as a live input by the
  hunt rules; cancel or skip the 4σ bid.
- **Rule (frozen grid, 8 trials):** skip a coin's 4σ bids on day d when its funding statistic for day d − 1 is
  below a threshold: source ∈ {coin, BTC} × statistic ∈ {previous day, trailing 7-day mean} × threshold ∈ {0,
  the DEV 25th percentile of the statistic over the coin-days on which a research parent filled}.
- **HOLD protection:** the feature's values on HOLD days (and any threshold or distribution from them) are computed or
  read only after the freeze commit.
- **Costs:** frozen simulator at X2 (selection, gates), X1 (gate A2), S (reported).
- **Selection statistic:** highest DEV paired HAC t at X2; minimum 10% of DEV parents skipped and at most 50%;
  ties → previous-day, then threshold 0.
- **Scored days:** sel, chk, and early from 2023-05-12. **Capital:** $250K. **Outputs:** reports/hunt2/crowd/.
