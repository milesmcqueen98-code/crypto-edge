# EXH: is the forced selling spent? (sell-flow exhaustion filter for the ladder) — DRAFT, not frozen

- **Path:** A (the live bot skipping fills that arrive while the selling is still accelerating; frozen simulator).
- **Who is forced or eager, and why we are paid (or not):** forced selling is front-loaded: in the Oct 10 2025 cascade
  88% of it came in the first 30 minutes (Garcia Seuma 2026, memo R3), and liquidation engines sell until their queue
  is empty. A bid filled once the burst is decaying meets the last of the forced flow and is paid by the rebound; a
  bid filled while aggressive selling is still at its peak is early — the cascade, or an informed seller still
  working, carries the price well past it inside the 60-minute holding window. Coinbase prints carry the exact
  aggressor side, so intensity and imbalance are measured, not inferred (no bulk-volume classification).
- **Prior evidence and what has been seen:** ladder v5 read fill-minute features on the selection era (the number of
  aggressive orders at or below our price in the fill minute related negatively to net, Spearman −0.12) and built
  deeper-rung filters (C7a/C7b) on the first sweep. This idea uses PRE-fill intensity, cumulative selling and
  imbalance, never computed on any era. R3 rated it 4/10.
- **Data:** the shared parent prints (every research parent, 30 minutes before to 2 minutes after the fill minute,
  all eras), features on the runner (scripts/hunt2/parent_features.py): DEV in reports/hunt2/parents/features_dev.csv,
  HOLD committed only after the freeze.
- **Live inputs and orders:** Coinbase's market_trades WebSocket (aggressor side exact); cancel the 4σ bid while the
  rule fires.
- **Features** (prints ≥ 1 s before the fill; aggressor-sell = maker side "BUY"):
  1. `ex_peak`: EWMA (60 s half-life) of aggressive-sell dollars at the fill, divided by its maximum over the 30
     minutes before. Skip when HIGH (selling at its peak, not spent).
  2. `csv_15`, `csv_30`: aggressive-sell dollars over the last 15 / 30 minutes, divided by the coin's 30-day ADV.
     Skip when LOW (little forced volume has traded: the drop is a repricing, not a flush).
  3. `turn`: imbalance (buy − sell)/(buy + sell) over the last minute minus over the last 15 minutes. Skip when LOW
     (sellers still gaining ground).
- **Rule (frozen grid, 8 trials):** {ex_peak high, csv_15 low, csv_30 low, turn low} × removal share ∈ {15%, 30%} of
  DEV parents (threshold = the DEV quantile, then fixed in absolute units).
- **Costs:** frozen simulator at X2 (selection, gates), X1 (gate A2), S (reported).
- **Selection statistic:** highest DEV paired HAC t at X2; ties → 15%.
- **Capital:** $250K. **Outputs:** reports/hunt2/exh/.
