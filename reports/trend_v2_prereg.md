# Trend rule v2: refinements under real costs (pre-registration)

Written 2026-11-06 ~12:50 ET, before any v2 trend variant was run.

## The incumbent (live rule)
- At each UTC daily close, if BTC is above its 100-day simple average, hold 50% BTC / 50% ETH.
- Otherwise hold cash earning T-bills.
- Weights drift while invested; only a flip is a trade.

## What earlier rounds already settled (not re-litigated)
Since 2017, about 2,000 trend setups were tried:
- Ensembles, vol targeting, Carver/Zarattini/Clenow systems, AI timing, long/short and funding overlays.
- None beat the live rule's Sharpe significantly.
- The daily BTC/ETH history is fully mined. A new signal "win" on it is mostly noise unless it is large,
  consistent across sub-periods, and also holds on other markets.

## Two families
**I. Implementation (same signal, real execution).** This is the honest lever: costs and timing, not curve-fitting.
- **Coinbase Advanced spot fees** (schedule after Sep 16, 2026; see the findings doc):
  - Tier by this strategy's own trailing 30-day volume: Intro 0.50% maker / 0.90% taker, Advanced 1 ($10K)
    0.35 / 0.75, Advanced 2 ($50K) 0.15 / 0.30, Advanced 3 ($250K) 0.10 / 0.15.
  - Plus 2 bp of slippage per side for taker orders and 1 bp for maker.
- Variants:
  - I0: old assumption, 0.25% per side at the UTC close (reference only).
  - I1: Coinbase taker, $10k book. I2: Coinbase maker, $10k book.
  - I3: Coinbase taker, $100k book. I4: Coinbase maker, $100k book.
  - I5: spot ETFs (IBIT + ETHA style). Signal from BTC at 3 pm ET, market-on-close order at the 4 pm ET close on
    US trading days. Cost 2 bp per side plus 0.25% a year expense ratio while held. Before the ETFs existed, ETF
    returns are proxied by spot at those times.
  - I6: I5 with 0.15% a year funds (mini trusts).
  - I7: ETFs, signal at the UTC close, executed at the next 4 pm ET close.
  - I8: ETFs, signal at the UTC close, executed at the next 9:30 am ET open.
- Cash earns T-bills in every case.

**S. Signal and allocation refinements**, each run under two implementations (I2 Coinbase maker $10k, and I5 ETF):
- S01–S04: average length 75 / 90 / 110 / 125 days.
- S05: EMA 100.
- S06–S08: hysteresis band ±1 / 2 / 3% around the average.
- S09–S10: 2 / 3 consecutive confirming closes.
- S11: weekly decisions (Sunday UTC; Friday for ETFs).
- S12: each asset on its own 100-day average.
- S13: both must be above their own averages.
- S14: ETH/BTC tilt (75/25 toward the leader by ETH/BTC vs its 50-day average).
- S15: 100% BTC. S16: 100% ETH. S17: 60/40. S18: inverse-vol (30-day) weights.
- S19: monthly rebalance to target while invested.
- S20: vol cap, exposure = min(1, 80% / basket 30-day vol), set at entry and monthly.
- S21: 50/100/150/200-day ensemble.
- S22: crash guard. Exit if the basket falls 20% in 7 days; re-enter after 7 days if the rule is still on.
- S23: 50/200-day golden cross.
- S24: 50-day breakout entry, 25-day low exit.
- S25: add SOL as a third leg from its Coinbase listing.
- S26: 90-day time-series momentum.

Round 2: up to 10 combinations of the best S changes, using the same mechanical rule as the wick lab.

## Evaluation
- **Window:** Jul 2017 – Nov 5, 2026. Daily marks at 00:00 UTC; Sharpe on returns above T-bills.
- **Sub-periods:** 2017-07–2019-12, 2020–2021, 2022–2023, 2024 – Nov 2026.
- **Calendar-year returns:** every year.

**Adopting a signal change requires all of these, under both I2 and I5:**
- Full-window Sharpe at least the incumbent's + 0.10.
- Weekly paired t of excess-return differences > 3.0, roughly Bonferroni for ~30 tries.
- Not worse than the incumbent by more than 0.10 Sharpe in any sub-period.
- **Cross-market check:** the same change, applied single-asset with the same parameters, raises Sharpe on at least
  6 of 9 other markets: SOL, LTC, XRP, LINK, DOGE, ADA, AVAX, SPY, QQQ.

**Implementation:** recommend the cheapest route Miles can legally and compliantly use, unless its paired t versus the
UTC-close timing is below −2.0. Cost savings are certain; timing differences are mostly noise.

The deflated Sharpe is reported but is not a bar for switching: it tests against zero skill, not against the
incumbent (lesson from the wick v2 decision).

## Also reported
A trend + wick portfolio: R2-08 at its efficient $10k against the trend sleeve, by calendar year where both exist.

## Results (2026-11-06 ~13:20 ET; reports/trend_lab/)
- **Signal: no change adopted.**
  - The best paired weekly t was 2.49 (2% band, Coinbase maker), against the 3.0 needed.
  - Cross-market wins were at most 5 of 9 (SMA 110/125, 2% band).
  - All 7 round-2 combinations stayed below t = 3.0. The best (SMA 110 + SOL leg) had t 2.90.
  - Clarification: adding SOL (S25 and the combinations with it) uses hindsight, because SOL is in the universe for having
    become a top coin. It would not have been adopted even with t > 3.
- **Implementation:**
  - Coinbase taker at small-account tiers: 53.7%/yr, Sharpe 1.04. That is paired t −7.6 vs the old 0.25% assumption.
  - Coinbase maker ($10k): 61.3%, Sharpe 1.13.
  - Spot ETFs: 69–77%, Sharpe 1.21–1.31. The timing variants differ only by noise.
  - **Recommended:** spot ETFs with the signal at the UTC close and execution in the next US session, if compliance
    allows ETFs without a minimum hold. With a 30-day minimum hold the ETFs score Sharpe 1.12 / 58.5%, so the fallback is
    Coinbase post-only maker orders.
- **Trend + wick:** daily correlation 0.0.
  - $90k/$10k: 2022 −17% vs −21% for trend alone; 2026 YTD −4% vs −8%.
  - Sharpe 0.85 vs 0.72 over 2022–23 and 2025–26.
