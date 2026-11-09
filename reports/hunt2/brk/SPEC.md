# BRK: structural-break (explosive downtrend) filter for the ladder — DRAFT, not frozen

- **Path:** A (the live bot skipping bids while a coin is in an explosive downtrend; frozen simulator).
- **Who is forced or eager, and why we are paid (or not):** the ladder sells insurance to forced sellers: it buys a
  dislocation and is paid when the forcing stops. In an explosive downtrend (a bubble bursting, a protocol failing,
  persistent unwind of a crowded position) the selling does not stop at the 60-minute horizon; the dislocation is the
  first leg of a regime change. López de Prado's structural-break tests (SADF, CUSUM) are built to flag exactly
  these explosive episodes in real time with only past prices, and R2-08's features (drop from the 24-hour high, BTC
  moves, beta, volatility regime) do not measure explosiveness.
- **Prior evidence and what has been seen:** HMM regimes and nearest neighbours failed as DAILY direction models
  (Medallion round). A break test used as a veto on a liquidity-provision signal has not been computed on any era.
- **Data:** Coinbase 1-minute candles (data/minute, data/minute_early).
- **Live inputs and orders:** Coinbase prices; skip the 4σ bid.
- **Rule (frozen grid, 8 trials):** for each coin at t-1, the Chu–Stinchcombe–White CUSUM statistic of 5-minute log
  returns over the last L hours, standardized by the coin's 30-day 5-minute volatility (downward version: the
  cumulative negative drift relative to its own volatility), and the supremum ADF statistic (SADF, López de Prado
  AFML ch. 17) on 15-minute log prices over the last L hours with minimum window 2 hours. Skip the bid when the
  statistic exceeds its DEV q-quantile computed over all approved coin-minutes (not only fills). Grid: statistic in
  {CUSUM, SADF} x L in {6, 24} hours x q in {0.90, 0.97}.
- **Costs:** frozen simulator at X2 (selection, gates), X1 (gate A2), S (reported).
- **Selection statistic:** highest DEV paired HAC t at X2 with 5–40% of DEV parents skipped; ties -> CUSUM, L = 6,
  q = 0.97.
- **Capital:** $250K. **Outputs:** reports/hunt2/brk/.
