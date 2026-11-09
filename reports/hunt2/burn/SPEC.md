# BURN: a coin whose last ladder failed to rebound is informed-selling territory (own-outcome filter) — DRAFT, not frozen

- **Path:** A (the live bot skipping new ladders in a coin for a while after its last ladder failed; frozen simulator).
- **Who is forced or eager, and why we are paid (or not):** the ladder is paid when the selling is forced and
  transient. When a ladder's 4σ rung has not rebounded by minute 60 (its take-profit untouched and the price still
  below the fill), the market has told us the selling was not transient: someone with information, or a large
  persistent seller, is working the coin (news diffusion and metaorders last hours; Hong–Stein; Bouchaud et al.'s
  long memory of order flow). The next dislocation in the same coin within hours is more likely the same seller. The
  bot knows its own fills live, so this needs no outside data.
- **Prior evidence and what has been seen:** ladder v6 (exits) found that remainders unsold at minute 60 kept
  falling on average in the selection era (dollar-weighted -71 bp at 60, -117 at 120) and read its hold-past-60 rule
  once on the hold-out (pooled t +0.52 for holding a 6-input subset). The execution round found a 2–5% DAILY loss
  limit lowered Sharpe (bad days usually recovered). No rule that conditions NEW signals on a coin's own failed
  ladder has been computed on any era.
- **Data:** the frozen dataset's research parents and rungs (fill time, take-profit hit, 60-minute mark), Coinbase
  1-minute candles; nothing else.
- **Live inputs and orders:** the bot's own order and fill records; skip (cancel) the coin's 4σ bids.
- **Rule (frozen grid, 12 trials):** a parent "failed" if its take-profit was not hit by fill + 60 min and the coin's
  price at fill + 60 min is below the parent's fill price by at least m x the parent's dislocation (the distance from
  fair value to the 4σ level). After a failure, skip the coin's 4σ bids from fill + 60 min for C hours. Grid:
  m in {0, 0.5} x C in {6, 24, 72} x scope in {that coin only, every coin when >= 2 coins failed within the same
  hour}.
- **HOLD protection:** a parent's failure flag is an OUTCOME (take-profit hit, price at +60). Flags of HOLD-era
  parents are computed only after the freeze commit.
- **Costs:** frozen simulator at X2 (selection, gates), X1 (gate A2), S (reported).
- **Selection statistic:** highest DEV paired HAC t at X2 among variants skipping >= 5% of DEV parents; ties ->
  shorter C, then coin scope.
- **Capital:** $250K. **Outputs:** reports/hunt2/burn/.
