# H11 (MJ): deep hourly bids on BTC, ETH, SOL and XRP perps (wave 2d, loop 2)

Fixed before any build of this idea. Same pre-registration (reports/hunt_prereg.md) and gates. Read
reports/hunt/BUILDER_GUIDE.md first.

## Why this idea now (honest accounting)
- **Where it comes from:** H3's mechanism test failed. Bids at estimated liquidation clusters did no better than
  random bids at the same depth. But both arms made money on DEV.
  - The control arm reached a DEV alpha t of 1.6–2.9 for depths of about 7σ, roughly 4.5% below price.
  - So the money came from **deep, hourly-refreshed bids on the majors** — the incumbent's kind of mechanism, forced
    selling into empty books — not from the liquidation estimate.
- **What R2-08 already does:** it trades alts' BTC-adjusted dislocations only and never bids in BTC. This idea puts
  bids in the four majors' perps in raw price terms.
- **What has been seen:** DEV results for nearby settings were seen through H3. So this idea's DEV choice is informed,
  and its grid is kept small.
- **HOLD (Jun 1 – Nov 5 2026) has never been computed for any version of it.** It is read once after the freeze.

## Universe, data, venue
- **Coins:** BTC, ETH, SOL, XRP.
- **Venue:**
  - Coinbase perps from the day after each launch (BTC/ETH 2025-07-19, SOL/XRP 2025-08-16).
  - Before that, spot-priced on the perp tick grid with the perp cost model. Report this split.
- **Data:**
  - Spot 1-minute: /home/claude/crypto-edge/data/minute_early (2021–23) and data/minute (2024–26).
  - Perp 1-minute: data/cfm.
  - Perp prints (common.TradeFetcher on Actions) for every post-launch fill window, to confirm fills.
- **Scored days:** gates.ERA_DAYS. DEV ends 2026-05-31.

## Bids (fixed)
- **When:** at the top of every hour, using data to t−1.
- **Sigma:** σ = the trailing 3-day standard deviation of 1-hour spot log returns.
- **Bid:** one post-only bid per coin at P × exp(−k σ), where P is the spot close of the previous minute. It sits on
  the perp tick grid and **within 5% of spot** (Fair Value Limit).
- **Replacement:** replace the bid every hour.
- **Halts:** none during Friday 5–6 pm ET; none for 2 minutes after a ±10% move from the hour's first open (R3 rules,
  all eras).
- **Fill:** the minute opens above the bid and trades through it by one perp tick (candles); prints where fetched.
  Size ≤ θ × through-volume (≤ 15 min), θ = 0.5; 0.25 also reported. Whole contracts; contract ≥ $150.
- **Take-profit:** post-only, 50% of the way back to the placement price, filled by a one-tick trade-through
  (TP volume ≤ θ).
- **Time exit:** market exit at the open H minutes after the fill.
- **No stop.**
- **Book:** one position per coin, notional 1× sleeve capital, gross ≤ 2×.
- **Costs:** common.py; 2× for gates.
- **Reuse:** you may reuse the H3 builder's fill and cost code from branch hunt/h3lm (scripts/hunt/h3lm/lm.py). Copy it
  into scripts/hunt/h11mj/ rather than importing it across branches.

## Trial grid (≤ 12, all logged)
- **Core grid:** 8 trials.
  - k ∈ {5, 7};
  - H ∈ {60, 240} minutes;
  - universe ∈ {BTC+ETH, all four}.
- **Variants on the best core trial:** +2.
  - k = 9;
  - BTC only.
- **AI filter on the best core trial:** +2.
  - Walk-forward LightGBM by quarter from 2022Q3, trained only on fills before each quarter.
  - Features known at placement: σ, the 24-hour and 7-day moves, the BTC 4-hour move, hour, coin.
  - Rule: keep a bid if its predicted net bp is above the median of the training predictions.
- **Selection:** the highest DEV alpha t with at least 40 trades.

## Checks to report
- Fills per year and coin.
- Net bp by year and coin.
- Spot-priced vs perp-priced.
- Candle-vs-print confirmation on post-launch fills.
- Where fills land relative to the cascade low.
- Same-day overlap with the incumbent and the result on its 10 worst days.
- Top-3 days' share of P&L.
- Correlation with the incumbent.
