# MACB: deep bids and offers through scheduled macro releases on the majors' perps — DRAFT, not frozen

- **Path:** B (a sleeve on Coinbase US perps: BTC, ETH, SOL, XRP).
- **Who is forced or eager, and why we are paid:** a hot or cold US print (CPI, NFP, PPI at 08:30 ET; FOMC at
  14:00 ET) moves crypto within seconds. Market makers pull quotes into the release (Cartea–Jaimungal: liquidity
  providers widen ahead of scheduled news), and the first move triggers stop orders and leveraged liquidations that
  overshoot the information content. A resting order far from the pre-release price, placed just before the release
  and pulled shortly after, is filled only by that overshoot and paid when it partly reverts. Unlike R2-08 (alts vs a
  BTC fair value), this trades the majors' absolute move at a known minute.
- **Prior evidence and what has been seen:** nothing computed on any era. H11 (deep hourly bids on major perps)
  failed: it bought mid-cascade on random hours; this idea bids only in release minutes.
- **Data:** data/hunt2/macro/releases.csv (212 releases 2022-01 .. 2026-11); Coinbase spot 1-minute candles and
  prints in [release - 10 min, release + 75 min] for BTC/ETH/SOL/XRP (spot-priced with perp costs before each perp
  launched; perp prints after); CFM perp candles.
- **Live inputs and orders:** BLS/Fed calendars; post-only GTD limit orders on CFM perps placed at release - 1 min,
  cancelled at release + 5 min; post-only take-profit; market exit.
- **Rule (frozen grid, 16 trials):** at release - 1 min, sigma1 = trailing 60-minute std of 1-minute returns. Rest a
  bid at P x (1 - k x sigma1 x sqrt(5)) (and, in the two-sided variant, an offer symmetrically above) until release
  + 5 min. On a fill, a post-only take-profit at 50% of the way back to P; anything left exits at market at fill +
  H. Grid: k in {3, 5} x side in {bid only, two-sided} x H in {15, 60} min x event set in {CPI+NFP+FOMC,
  CPI+NFP+FOMC+PPI}; assets fixed to BTC, ETH, SOL, XRP.
- **Fills:** a resting order fills only on a print strictly beyond its level; size <= 0.5 x volume beyond the level
  while the price stays beyond it (prints); whole contracts; the Fair Value Limit (orders more than 5% from spot are
  rejected) caps the depth.
- **Size:** each order's notional = 0.5 x sleeve capital / 4 assets x 2 (gross <= 2x).
- **Costs:** scripts/hunt2/costs.py perps at 2x; 1x reported.
- **Selection statistic:** highest DEV alpha t with >= 20 fills; ties -> bid only, then k = 5.
- **Capital:** $25K/$50K/$75K/$125K. **Outputs:** reports/hunt2/macb/.
