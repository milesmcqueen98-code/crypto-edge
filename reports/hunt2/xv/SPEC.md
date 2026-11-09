# XV: is the selling local or global? (cross-venue confirmation filter for the ladder) — DRAFT, not frozen

- **Path:** A (the live bot skipping dislocations that are not Coinbase-local; frozen simulator).
- **Who is forced or eager, and why we are paid:** a Coinbase dip below the BTC-adjusted fair value can come from a
  Coinbase-local seller (US liquidation of spot margin, a US fund or app user dumping, a local book thinning) or from a
  global repricing of the coin that every venue shows at once (coin news, offshore liquidations already arbitraged
  everywhere). A local dislocation is paid back by cross-venue arbitrage once inventory moves (slow, because US venues
  are fragmented and capital-constrained: Harris's arbitrageurs are limited); a global one is a new price. Bitstamp
  (NY-licensed, public data) shows which: at t-1, compare the coin's Coinbase and Bitstamp moves over the last 15
  minutes.
- **Prior evidence and what has been seen:** H6 (first hunt) traded Coinbase–Bitstamp/perp gaps directly and failed:
  Coinbase leads, so the other venue's price is a stale fair value at the second scale. This idea does not trade the
  gap; it uses whether the gap exists at the minute scale to classify the ladder's own signals. Nothing computed on
  any era.
- **Data:** Coinbase and Bitstamp 1-minute candles (data/minute, data/bitstamp; Bitstamp from 2024-01, so the early
  hold-out era is not covered and is not scored for this idea).
- **Live inputs and orders:** Bitstamp's public market data (allowed); skip the 4σ bid.
- **Rule (frozen grid, 8 trials):** at t-1, local = (Coinbase 15-minute log return - Bitstamp 15-minute log return)
  for the coin, in units of the coin's 15-minute residual sigma. Skip the bid when the dislocation is global:
  local > -c (Coinbase has not fallen more than Bitstamp by c sigma), c in {0.5, 1.0}; window in {15, 60} minutes;
  Bitstamp missing (no trade in the window) -> keep the bid, or skip it ({keep, skip}).
- **HOLD protection:** the feature's values on HOLD days (and any threshold or distribution from them) are computed or
  read only after the freeze commit.
- **Costs:** frozen simulator at X2 (selection, gates), X1 (gate A2), S (reported).
- **Selection statistic:** highest DEV paired HAC t at X2 with 5–50% of DEV parents skipped; ties -> c = 0.5, 15 min,
  keep.
- **Scored days:** sel and chk (Bitstamp history starts 2024). **Capital:** $250K. **Outputs:** reports/hunt2/xv/.
