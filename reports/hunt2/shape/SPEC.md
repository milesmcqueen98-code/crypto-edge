# SHAPE: air pocket or grind? The drop's shape as a filter on the ladder — DRAFT, not frozen

- **Path:** A (the live bot skipping dislocations that arrive as a steady grind; frozen simulator).
- **Who is forced or eager, and why we are paid (or not):** a forced seller with no price limit (a liquidation engine,
  a stop cascade) empties the book in seconds: the residual drop arrives in one or two minutes, an "air pocket" that
  refills when the forced orders stop (Scaillet, Treccani & Trevisan 2020: bitcoin's negative jumps were more than
  recovered within 30–60 minutes). A large informed seller or a metaorder works the price down steadily: high path
  efficiency, little jump content, and the impact lasts (Donier & Bonart 2015: lasting impact comes from persistent
  related flow). An explosive multi-hour downtrend is the same grind at a longer scale (López de Prado's
  structural-break idea). R2-08's AI sees the residual move at 1, 15 and 60 minutes and the drop from the 1-day high,
  but not how the path was travelled.
- **Prior evidence and what has been seen:** nothing computed on any era. R3 rated drop shape 4/10 (testable on the
  full sample from candles).
- **Data:** Coinbase 1-minute candles (data/minute, data/minute_early) for the 17 coins and BTC; the beta is R2-08's
  (trailing 7-day beta of 1-minute returns on BTC, as of t−1).
- **Live inputs and orders:** Coinbase candles; skip (cancel) the 4σ bid.
- **Features at t−1** on e_k = r_k − β r_BTC,k, the coin's BTC-residual 1-minute log returns, k ∈ [t−60, t−1]:
  1. `PE60` = |Σe_k| / Σ|e_k| (path efficiency): skip when HIGH (a steady grind).
  2. `JS1_60` = the largest single-minute residual drop / the total residual drop (if the total is a drop): skip when
     LOW (no air pocket).
  3. `JR60` = max(0, 1 − BV/RV), RV = Σe_k², BV = (π/2) Σ|e_k||e_{k−1}| (jump share of variance): skip when LOW.
  4. `DRIFT6h` = Σ of the residual returns over [t−360, t−1] divided by (the coin's 30-day residual 1-minute std ×
     √360): skip when LOW (a persistent multi-hour downtrend, the long-scale grind).
- **Rule (frozen grid, 8 trials):** 4 features × removal share ∈ {15%, 30%} of DEV parents (threshold = the DEV
  quantile over DEV parents, then fixed in absolute units).
- **Costs:** frozen simulator at X2 (selection, gates), X1 (gate A2), S (reported).
- **Selection statistic:** highest DEV paired HAC t at X2; ties → 15%.
- **Capital:** $250K. **Outputs:** reports/hunt2/shape/.
