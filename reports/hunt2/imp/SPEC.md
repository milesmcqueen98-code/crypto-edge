# IMP: was the drop paid for by selling? (square-root-law impact residual as a filter on the ladder)

- **Path:** A (the live bot skipping fills whose drop is larger than the selling explains; frozen simulator).
- **Who is forced or eager, and why we are paid (or not):** a seller's price impact follows the square-root law,
  I ≈ Y σ_D √(Q / V_D) (Donier & Bonart 2015 on bitcoin, Y ≈ 0.9; Bouchaud et al., *Trades, Quotes and Prices*). Impact
  that the signed flow explains is mechanical; for uninformed, forced flow it relaxes almost completely once the
  flow stops (latent-order-book model; Gomes & Waelbroeck 2015), which is what the ladder's take-profit collects. A
  drop much LARGER than the net aggressive selling can explain was made by market makers revising their quotes on
  information they hold; about two-thirds of informed impact stays (Farmer et al. 2013). The ratio of the residual
  drop to the flow-implied impact separates the two. R2-08's AI sees the drop's size and the coin's volume, never the
  drop per unit of signed flow.
- **Prior evidence and what has been seen:** nothing computed on any era. Memo R1 rated it 6/10 (its best Path A
  idea). Ladder v5's fill-minute taker-sell share (selection era) is a crude cousin, measured at, not before, the fill.
- **Data:** the shared parent prints (30 minutes before to 2 minutes after every research parent's fill minute, all
  eras) → per parent and window W: net aggressive selling Q_W (dollars; `usd_W × (2 × sell_share_W − 1)`) and the
  coin's log return over the window from prints (`ret_bp_W`), in reports/hunt2/parents/features_*.csv; BTC's return
  over the same window and the trailing 7-day beta from Coinbase 1-minute candles; σ_D (`vol_d`) and V_D (`adv`) from
  the frozen dataset (reports/hunt2/parents/windows.csv).
- **Live inputs and orders:** Coinbase market_trades (aggressor side exact) and candles; cancel the 4σ bid while the
  rule fires.
- **Features** at the fill, prints ≥ 1 s old, W ∈ {5, 15, 30} minutes:
  - residual drop D_W = −(r_coin,W − β r_BTC,W) (positive for a drop);
  - flow-implied impact I_W = σ_D √(max(Q_W, 0) / V_D) (Y omitted: thresholds are quantiles);
  - `f_W` = D_W / I_W, set to +∞ when Q_W ≤ 0 and D_W > 0 (a drop with no net selling). Skip when HIGH.
  - `rate_15` = (Q_15 / 15) / (V_D / 1440), the selling rate vs an average minute's volume. Skip when LOW (a slow
    drift: a worked order, not a flush).
- **Rule (frozen grid, 8 trials):** {f_5, f_15, f_30, rate_15} × removal share ∈ {15%, 30%} of DEV parents (threshold
  = the DEV quantile, then fixed in absolute units).
- **HOLD protection:** the features' values on HOLD days are computed or read only after the freeze commit (the HOLD
  feature file is committed by a post-freeze run).
- **Costs:** frozen simulator at X2 (selection, gates), X1 (gate A2), S (reported).
- **Selection statistic:** highest DEV paired HAC t at X2; ties → 15%, then W = 15.
- **Capital:** $250K. **Outputs:** reports/hunt2/imp/.
