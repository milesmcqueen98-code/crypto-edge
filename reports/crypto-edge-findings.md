# Crypto edge: findings and live rules (updated Nov 6, 2026, scale round)

Repo: github.com/milesmcqueen98-code/crypto-edge (data, research code, nightly signals, paper-trading bot)

## Status at a glance
- **Live (real money):** BTC+ETH trend filter (below). Unchanged.
- **Paper trading since Nov 6, 2026:** "wick catcher" — AI-filtered resting dip bids on Coinbase US perps (Execution round
  below). Out-of-sample Sharpe 2.95 (t = 4.0) on spot-priced simulation, Jan 2025 – Nov 2026, 2.25 with high costs.
  Replayed on the perps' own prices it shows 5–9, but mostly from perp-only wicks whose fills are unverified (1.6–2.6
  counting only spot-confirmed fills). Not traded with money until the paper test and a 1-contract pilot pass, and
  compliance clears futures.
- **Wick v2 lab (Nov 6):** 130 variations tested with realistic Coinbase costs (section below).
  - **R2-08 is now the strategy of record:** realistic-cost AI label, 60th-percentile threshold, 7-day beta.
  - Its realistic-cost Sharpe is 3.79 / 3.06 / 2.36 (selection / check / perp-priced), vs 2.24 / 1.22 / 1.21 for v1.
  - Head-to-head paired t of the daily differences is 2.1 in the check period and 1.7 on perp prices.
  - It missed the deflated-Sharpe bar (0.77 vs 0.95), but v1 scores 0.06 on the same bar.
  - v1 keeps paper trading as the control.
  - Rules: stop R2-08 if its realistic net per trade is below −12 bp after about 70 paper trades. Go back to v1 if
    v1's realistic net per trade is higher after 60 trades in each book.
- **Scale round (Nov 6):** the wick catcher is already largely market neutral (daily beta 0.03) and reaches ~100%/yr only at
  small size (2x the paper size, up to roughly $25–50K). Its profit tops out near $50K a year; it cannot carry $5M
  (section below).
- **Maker round (Nov 6): rejected.** Two-sided quoting at the touch loses 0.7–0.9 bp per dollar before fees in all 36 setups.
- **C3 upgrade round (Nov 6):** turnover cuts tie on Sharpe; C3 unchanged, still a paper-trade candidate.

## Wick v2 lab (Nov 6): 130 variations of the dip-bid strategy, realistic costs first
Goal set by Miles: a higher-Sharpe version, Renaissance-style. That meant:
- Many small variations of the one idea that works.
- One model across all coins.
- Costs modeled first, strict out-of-sample selection.
- Something he can run himself.

Rules were pre-registered before any result (reports/wick_v2_prereg.md); code is in scripts/lab/.

**Reality rules:**
- **Realistic costs (used for selection):**
  - $0.20 per contract per side on every fill. Coinbase Derivatives' exchange fee is per contract per side (CFTC
    filing, effective Aug 17, 2026); the rest is our estimate for Coinbase's own charges.
  - 1.5x the measured perp half-spread on market exits.
  - 1 bp funding per trade.
  - Whole contracts only.
- **Fills:** a one-tick trade-through on spot 1-minute candles. The AI is walk-forward, retrained quarterly with a
  1-day embargo.
- **Periods:** selection Jan 2025 – Mar 2026. Check period (holdout) Apr – Nov 2026, read once after the shortlist was
  fixed.
- **Adoption needs all five:**
  - Selection Sharpe at least base + 0.25.
  - Check-period Sharpe at least base + 0.25.
  - Perp-candle check (spot-confirmed fills) at least base.
  - Deflated Sharpe at least 0.95, with N = 130 lab trials + ~2,000 earlier setups.
  - Probability of backtest overfitting (PBO) at most 0.3.

**What we tested:**
- 110 single changes in six families:
  - Entry level: depth, lookback, sigma/beta windows, reference, ladder, BTC hedge, hour-of-day sigma.
  - Exits: take-profit, hold time, two-stage, fair-value tracking, stops, passive exits.
  - AI: threshold, label, parameters, retraining, features, ensembles.
  - Sizing and slots.
  - Universe and fees.
  - Rhyming books: rips, 15/240-minute, joint horizons.
- 20 combinations, built by a fixed rule from the best changes.

**What the selection period said (realistic costs, base 2.24):**
- **Being pickier is the robust gain.** With per-contract fees, marginal trades lose money:
  - Threshold 40th / 50th / 60th / 75th percentile gave 1.25 / 2.24 / 2.93 / 3.38.
  - Realistic-cost label + 60th percentile (C29): 3.41.
  - No bid while a contract is worth under $667 (E07): 3.46.
  - These also held in the check period: 2.36 / 4.68 / 2.57 / 2.93 vs 1.22 for v1 (diagnostic, read after the
    shortlist).
- **Neutral (within noise):** model tweaks (leaves, rounds, features, retraining, decay, seeds) and passive exits:
  2.0–2.4.
- **Hurt:**
  - BTC-perp hedge: 0.57. Hedge fees eat the edge.
  - Early stops: 0.5–0.8. They sell the bottom of the wick.
  - 15-minute book: −0.46.
  - Sell-the-rip mirror: 0.32. Rips don't revert like forced selling.
  - Basket reference: 0.20.
  - Hour-of-day sigma: 1.16.
  - No AI: 0.24.
- **Noise warning:** neighbouring settings can differ by more than 1 Sharpe (L=60 gave 2.24, L=75 gave 0.94).
  Across all 130 variants, the selection-period and check-period rankings correlate 0.53 (Spearman).

**Shortlist (top 5 by selection Sharpe) after opening the check period:**

| Variant | Changes | Selection | Check period | Perp-priced (spot-confirmed) | Deflated Sharpe (lab / all trials) |
|---|---|---|---|---|---|
| v1 base | — | 2.24 | 1.22 | 1.21 | 0.30 / 0.06 |
| R2-20 | E07+C29+B08+A11+D02+F08 | 4.23 | 1.89 | 1.43 | 0.97 / 0.74 |
| R2-03 | E07+B13 (fee floor, hold 120) | 3.84 | 1.62 | 1.37 | 0.94 / 0.57 |
| R2-19 | E07+C03+B13+A11+D02+F08 | 3.80 | 2.09 | 1.36 | 0.85 / 0.51 |
| **R2-08** | **C29+A11** (realistic label, 60th pct, 7-day beta) | **3.79** | **3.06** | **2.36** | **0.975 / 0.77** |
| R2-07 | C29+B13 (… + hold 120) | 3.76 | 2.28 | 1.87 | 0.97 / 0.68 |

- **Overall statistics:**
  - PBO 0.27 (pass).
  - Walk-forward variant selection: 2.50 vs 2.03 for v1. In the check-period quarters it scored 1.89 vs 1.22.
- **R2-08, perp-priced from Jul 2025** (coins join as their perps list): 394 trades, 20.8 bp net per trade vs 9.6 for
  v1. With strict fills it scored 2.16 vs 0.98.
- **R2-08 as the bot trades** (no bids 16:55–18:05 ET, spot-priced, Jan 2025 – Nov 2026):
  - Sharpe 3.58 vs 1.97. With the advertised 0%/0.03% fees: 3.97 vs 2.82.
  - Max drawdown −7% vs −14%.
- **Decision.** The pre-registered verdict was "none adopted": all five passed bars 1, 2, 3 and 5, and all failed
  bar 4 (deflated Sharpe 0.51–0.77 counting the ~2,000 earlier setups).
- **Revised the same day** (logged in the pre-registration). Bar 4 tests against zero skill, and v1 scores 0.06 on it.
  The decision that matters is head-to-head:

  | R2-08 vs v1, realistic costs, same days | Paired t | Bootstrap P(R2-08 Sharpe higher) |
  |---|---|---|
  | Selection period | 3.27 | 1.00 |
  | Check period | 2.11 | 0.995 |
  | Perp-priced, spot-confirmed | 1.68 | 0.993 |
  | As the bot trades | 3.89 | 1.00 |

  - The head-to-head also wins under advertised and base fees (paired t 2.8 and 2.7).
  - Picking R2-08 after seeing the check period weakens the 2.11 to about p = 0.09 on its own. But every finalist
    beat v1 there, as did its core single change C29 (2.57 vs 1.22).
  - The two are about 0.87 correlated, so the downside of switching is small.
- **R2-08 is the strategy of record** (bot/v2/, logged to paper_v2/). v1 keeps paper trading as the control
  (paper/).
- **Forward rules:**
  - Stop R2-08 if its realistic net per trade is below −12 bp after about 70 paper trades.
  - Go back to v1 if v1's realistic net per trade is higher after 60 trades in each book.

**Costs, at today's prices:**
- Realistic round trip:
  - 3–19 bp with a take-profit exit.
  - 10–22 bp with a time exit.
  - ETH, LTC and BCH are the dearest: a contract is only ~$220–270, so 7.5–9 bp of fees per side.
- Advertised schedule: about 1 bp (take-profit) and 6–12 bp (time exit).
- Per-coin table: reports/lab/cost_table.csv.
- Check your real futures fee in Coinbase before going live. The strategy is fee-sensitive, and the AI threshold is
  what keeps it profitable after costs.

## Live strategy: BTC+ETH trend filter
- BTC daily close (UTC) above its 100-day simple moving average → hold 50% BTC / 50% ETH.
- Close below → hold cash (USD/USDC). Checked every daily close; only a flip is a trade.
- Backtest on Coinbase data, 0.25% per-trade costs:
  - Jul 2021 – Nov 2026: 21–22%/yr vs 16.5% for BTC buy & hold. Max drawdown −39% vs −77%.
  - Nov 2019 – Nov 2026 (7 years): 58.9%/yr; $1,000 → $25,562 vs $8,112 for BTC hold; Sharpe 1.24 vs 0.80.
  - Stress case at 0.5% costs, 7 years: 53.6%/yr.
- Jul 2017 – Nov 2026, Sharpe on returns above T-bills: 1.17, 64%/yr. Max drawdown −61%, from the 2018 bear-market whipsaws.
- Losing years: 2018 (−38%), 2022 (−18%), 2026 YTD (−8%).
- The 7-year figure is front-loaded. Of 47 round trips, 34% won; average win +52%, average loss −4%.
  - The top 3 trades (one of them +458% in 2020–21) produced about 89% of the gain.
  - By start date: Nov 2021 start 16%/yr vs 4% BTC; Nov 2022 start 30% vs 38% BTC (lags in steady bull markets).
- Robustness:
  - 50/100/150-day averages all returned 51–66%/yr; 200-day returned 43%.
  - Trading one day late: 66%/yr.
- The edge is drawdown control. The return difference vs buy & hold is not statistically significant.
- Signal as of 2026-11-05: risk off (BTC $75,969, 1.3% below its 100-day average $76,942). Starting position: cash.

## Execution round (Nov 6): making the short-horizon reversal tradable — "wick catcher"
Goal set by Miles: find a way to actually execute the minute-level reversal (gross Sharpe 4–5) with $10K.

**Why market orders can't work:** the edge per trade of the cross-sectional reversal is ~0.2 bp; a taker pays a
2 bp fee plus a 0.3–5 bp half-spread per side. An event study of large residual moves vs BTC (|z| ≥ 2–5, 640 setups,
reports/event_grid.csv) confirmed it: big drops revert 9–33 bp, big jumps don't, and the best taker setting chosen on
2024 earned a test Sharpe of only 0.4.

**What works: be the liquidity, not the taker.**
- Keep a post-only buy order resting 4 residual standard deviations below each coin's BTC-adjusted fair value
  (60-minute residual vs BTC, 3-day beta and sigma). It fills only during forced selling (liquidation cascades, stop
  runs), which snaps back.
- A post-only take-profit at 60% of the dislocation sells into the rebound; anything left is sold at market after 60
  minutes. No stop-loss (stops at 1x the dislocation turned it negative).
- Simulated fills: an order fills only if the minute opened above it and then traded *through* it by at least one
  futures tick; the fill price is the limit. Base costs: 2 bp per side on every fill (maker and taker) plus one futures
  tick of spread on market exits.
- Design period 2024; test Jan 2025 – Nov 5 2026, never used for any choice.
- Family chosen on 2024 by median design Sharpe across a 1,120-setup grid (reports/wick_grid_base.csv): 60-minute
  residual dips. Design/test rank correlation across setups 0.85. The sell-the-rip side fails.
- **AI filter (LightGBM, walk-forward quarterly, first model trained on 2024 only):** each minute it predicts the trade's
  net edge from 23 features known at t−1. The bid stays live only if the prediction beats the median of its own training
  predictions; that rule was fixed before the run. The bot averages 5 seeds. Code: scripts/wick_ai.py,
  scripts/wick_final.py, edge/wick.py.
- Universe rule, fixed before looking at results (implementability only): a Coinbase US perp exists, tick ≤ 3 bp,
  contract ≥ $150, perp volume ≥ $1M/day. That gives 17 coins: ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR,
  NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC. AVAX, DOT, SHIB and ADA fail on tick size.

**Out-of-sample results, Jan 2025 – Nov 2026** ($2,500 notional per trade on $10K; numbers after the audit fixes below):

| Version | Sharpe | t | Return/yr | Max DD | Worst day | Trades/day | Net/trade |
|---|---|---|---|---|---|---|---|
| Market orders after the move (best 2024 setting) | 0.39 | — | 16% | — | — | 2.6 | 3.3 bp |
| Resting bids, no AI, 6 core coins | 1.17 | 1.6 | 17% | −19% | −8% | 2.8 | 6.8 bp |
| Resting bids + AI, 6 core coins | 2.85 | 3.9 | 32% | −9% | −4% | 1.4 | 25.7 bp |
| Resting bids, no AI, 17 coins | 2.04 | 2.8 | 64% | −36% | −21% | 5.7 | 12.3 bp |
| Resting bids + AI, 17 coins, no position cap | 3.56 | 4.8 | 93% | −14% | −11% | 3.0 | 33.7 bp |
| **Resting bids + AI, 17 coins, max 6 open (paper trading)** | **2.95** | **4.0** | **57%** | **−12%** | **−10%** | **2.4** | **25.7 bp** |
| Same, high costs ($0.20/contract/side + measured perp spreads) | 2.25 | 3.1 | 43% | −14% | −10% | 2.4 | 19.4 bp |

- By year (paper-trading version): 2025 Sharpe 3.94, 2026 1.99. High-cost case: 3.09 and 1.40.
- **Model noise:** 5 LightGBM seeds give 2.85–3.10 at the cap and 3.46–3.71 uncapped. Row order alone moved the 6-coin
  result by ~0.3 (3.13 vs 2.85).
- **Stress tests** (6-coin test, AI version):

| Change | AI Sharpe |
|---|---|
| Fills need 3 ticks | 3.06 |
| $0.20/contract fees | 2.70 |
| Both | 2.66 |
| 0 bp maker fee | 3.37 |
| Primary depth k=3 / k=5 | 2.75 / 2.82 |
| Take-profit 0.3 / 1.0 of the move | 2.96 / 2.51 |
| No take-profit | 1.67 |
| Hold 30 / 120 min | 2.25 / 2.71 |
| Lookback 30 / 120 min | 1.98 / 2.00 |

  - The AI filter raised Sharpe in all 14 variants.
  - 17 coins with exits paying 3 ticks: 2.79.
- **Lumpy:** the best 5 days are 36% of P&L and the best 10 days 55% (the Oct 10 2025 crash, Feb 5–6 2026). Without the
  best 10 days the 16-coin Sharpe is still 2.8.
  - Worst day: Jan 19 2026 (−9.4%), an overnight alt selloff that kept going.
- **Daily loss limit:** a 2–5% limit lowered Sharpe, because bad days usually recovered. The bot's 8% limit is only a
  safety switch.

**What the AI uses** (mean |SHAP| of the walk-forward models; net bp per trade in the lowest vs highest fifth, test period):

| Signal | Lowest fifth | Highest fifth | Reading |
|---|---|---|---|
| Coin's move from its 24-hour high | +35 bp | −17 bp | Dips after a big down day revert most |
| Bid depth / volatility regime | −10 bp | +33 bp | Works when volatility is high |
| Size of the 60-minute drop vs BTC | — | — | Matters |
| BTC's own 60-minute and 4-hour move | — | — | Dips while BTC is also falling revert more |
| Beta | — | — | Matters |

Volume spikes, time of day and the last minute's move matter little.

**How long to hold:** the pre-cost markout after a fill (k=5) builds to ~26–32 bp at 30–60 minutes in 2025–26, then
fades to ~4 bp by 4 hours; in 2024 it kept rising. A take-profit at 0.6× the move plus a 60-minute cap sits on the plateau.

**Venue for New York: Coinbase Financial Markets perp-style futures (all 50 states).**
- Ticks and contract sizes come from the public listing (reports/cfm_products.csv):
  - BIP 0.01 BTC, tick $5.
  - ETP 0.1 ETH, tick $0.50 (2.2 bp).
  - SLP 5 SOL; XPP 500 XRP.
  - Alt perps (DOP, LCP, LNP, BCP, SUP, XLP, HEP, …) listed Dec 12 2025 or Feb 28 2026.
- Measured perp spreads from a 15-minute book sample (reports/cfm_book_summary.csv): BTC 1.3 bp, ETH 4.5, SOL 3.3,
  XRP 2.5, alt perps 5.5–10.8 bp.
- Fees: "from 0.02%" advertised. The CFTC filing shows $0.10/contract/side retail before Coinbase's charges, hence the
  $0.20/contract high-cost case.

**Futures validation** (scripts/wick_futures.py): the same spot-computed levels times the futures/spot price ratio, with
fills and exits on the perps' own 1-minute candles since each listed. Market exits pay the measured perp half-spread and
sell at the lower of the last futures trade and the spot-implied price.

| Futures-priced, max 6 open | Window | Sharpe | t | Net/trade |
|---|---|---|---|---|
| AI, fill needs 1 tick | 17 perps, Dec 13 2025 – Nov 5 2026 | 8.80 | 8.3 | 50.5 bp |
| AI, strict: 3 ticks + 3x our size traded that minute | same | 9.28 | 8.8 | 53.1 bp |
| AI, only fills where spot also reached its level (audit) | same | 1.58 | 1.5 | 14.8 bp |
| Same AI rule on spot prices | same | 2.56 | 2.4 | 23.5 bp |
| AI, fill needs 1 tick, ETH/SOL/XRP | Aug 16 2025 – Nov 5 2026 | 5.34 | 5.9 | 48.2 bp |
| Same, only spot-confirmed fills (audit) | same | 2.60 | 2.9 | 29.2 bp |
| Same AI rule on spot prices, ETH/SOL/XRP | same | 3.78 | 4.2 | 39.6 bp |

- **Independent audit** (separate agent, audit/ folder): no look-ahead and no off-by-one errors. Both headlines were
  reproduced exactly with independent code, and 6 futures trades were rebuilt by hand. But the futures result does not
  validate the spot strategy.
  - 61% of AI futures trades (84% of the P&L) filled in minutes when spot never reached its level. These were wicks on the
    new perps' thin books: the futures low was a median 172 bp below the spot-implied price, and the take-profit hit
    after a median 2 minutes.
  - The wicks cluster in 5–6 pm ET, the daily maintenance hour plus the weekly Friday halt: 13% of AI trades, 19% of P&L.
  - In the same minute on both venues, futures net 9–13 bp less per trade than spot.
  - Fees, 1x–3x volume rules, a clean or fresh basis, and 1-minute latency all leave the futures result at 6–9. What candles
    can't show is whether our order would really be filled in those thin-book wicks: queue position, partial fills, and
    competition from Coinbase's market makers.
- **Audit fixes applied:**
  - PEPE's spot tick is 1e-8 (26 bp), not 1e-9: the cap-6 Sharpe fell 3.22 → 2.98.
  - A position now holds its slot through its exit minute: 2.98 → 2.95.
- **Audit sensitivities** (pre-fix base 3.22):
  - Everything one minute older: 2.37.
  - AI features one minute older: 2.56.
  - AVAX and ADA added back: 2.75.
  - ZEC dropped: 2.93.
  - Tie-order shuffles: 2.98–3.27.
- **Realistic expectation:** Sharpe ~2–3 on spot-confirmed dislocations. 5+ only if the perp-only wicks prove fillable at
  our size, which the paper test measures.

**Implementation (bot/):**
- Python bot, paper mode by default (no keys). Live mode uses the official Coinbase Advanced SDK: post-only GTC limits
  and market exits.
- 5-seed model, max 6 positions, $2,500 per trade.
- Safety: 8% daily stop, STOP-file kill switch, no new bids 4:55–6:05 pm ET (maintenance hour and Friday halt), a basis
  sanity check (3%), and position reconciliation in live mode.
- Parity test (bot/replay_test.py): the live engine replayed over history traded the same minutes at the same prices as
  the research code (14/14 in the Feb 2026 crash window, 1/1 in Oct 2026).
- Forward paper test: GitHub Actions every 6 hours from Nov 6 2026 (.github/workflows/paper.yml, results in paper/). It
  logs the dollars of bids ahead of ours and the volume traded in each fill minute.
- Pilot plan: paper 4–8 weeks → live at 1 contract per order for 2–4 weeks → scale. Compliance pre-clearance is needed
  (futures).

**Caveats:**
- Fills are simulated from 1-minute candles.
- The 17-coin universe has survivorship and end-of-sample selection bias; the 6 core coins less so.
- About 2,000 setups were looked at in this round, but the deployable design was fixed on 2024 data or by rule before its
  test.
- The futures windows are 11–15 months long.

## Exchange costs (checked Nov 6, 2026)
- **Coinbase Advanced spot, US (maker / taker by trailing 30-day volume, after the Sep 16, 2026 change):**

| Tier | 30-day volume | Maker | Taker |
|---|---|---|---|
| Intro | $0+ | 0.50% | 0.90% |
| Advanced 1 | $10K | 0.35% | 0.75% |
| Advanced 2 | $50K | 0.15% | 0.30% |
| Advanced 3 | $250K | 0.10% | 0.15% |
| VIP 1 | $500K | 0.06% | 0.125% |
| VIP 5 | $20M | 0.01% | 0.05% |
| VIP 6 | $50M | 0.000% | 0.035% |
| VIP 8 | $250M | 0.000% | 0.020% |

  - VIP 2–4 and VIP 7 not found; models charge the next-lower listed tier. Tiers update hourly.
  - No maker rebate at any tier: 0.00% is the floor.
  - Spot or derivatives volume qualifies, or USDC balances ($500K for Advanced 1 up to $15M for VIP 2).
- **Coinbase US perpetual-style futures** (nano BTC = 0.01 BTC; nano ETH = 0.1 ETH):
  - Fees "from 0.02%", up to 10x leverage, available in all 50 states.
  - Funding accrues hourly and is settled twice daily.
  - Exchange fee (CFTC filing): $0.10 per contract per side for retail on BIP/ETP ($0.07 for signed market makers), before
    Coinbase's own charges: 1.3 bp on nano BTC, 4.5 bp on nano ETH at today's prices. Makers pay it too.
  - Full product list, ticks and contract sizes: reports/cfm_products.csv (29 perp-style products incl. 17 crypto alts).
- **Kraken Derivatives US perps (Bitnomial):**
  - 16 contracts, including BTC, ETH, SOL, XRP, ADA, AVAX, LINK, DOGE, LTC.
  - Contract sizes 0.01 BTC, 0.5 ETH, 5 SOL.
  - Fees all-in per contract per side: Kraken's page says $0.0113 (≈0.1–0.15 bp); another source says $0.15 (≈2 bp).
  - Not available in New York or Maine.
- **Kraken Futures (global, non-US):** maker rebate −0.5 to −1 bp at $250M–$1B+ per month; taker 1.25–5 bp.
- **Kalshi perps:** 5 bp maker / 12 bp taker at the base tier; 0.6 / 2.6 bp above $3B volume.
- Our perps model: 0.04% per side, plus funding (Hyperliquid data 2023+, 8%/yr assumed before). Realistic nano-perp model
  (C3 upgrade round): BTC 2.5 bp, ETH 6.5 bp per side, whole contracts.
- Coinbase Advanced REST API limit: 30 requests per second.

## Benchmarks: SPY and elite funds (Nov 6)
Same rules on SPY, Nov 2019 – Nov 2026 (Sharpe above T-bills):

| Strategy | Sharpe | Return/yr | Max DD |
|---|---|---|---|
| SPY buy & hold | 0.66 | 14.9% | −34% |
| SPY 200-day rule | 0.73 | 11.8% | −18% |
| SPY 100-day rule | 0.85 | 13.2% | −17% |

- Citadel Wellington: about 19%/yr net since 1990, and −55% in 2008.
  - Recent press-reported years imply a Sharpe of roughly 2–2.5 at ~9% vol (my estimate; Citadel publishes no volatility).
- Renaissance Medallion: about 66%/yr gross 1988–2018, with no losing year.

## Round 1: tested and rejected (out of sample, tradable universe, Jul 2021+)
| Strategy | Return | Max DD | Status |
|---|---|---|---|
| AI LightGBM coin ranker, top 10 + trend | 5.2%/yr | −56% | Shadow-tracked only |
| Low-volatility top 10 + trend | 17.3%/yr | −54% | Shadow-tracked only |
| Momentum top 10 + trend | −12.2%/yr | — | Rejected |
| Equal-weight top 50 | −28.7%/yr | −93% | Rejected |
| AI market-timing classifier for BTC/ETH | — | — | Rejected: hit rate 52.6%, equal to always guessing up |

- The AI ranker has real ranking skill (rank IC +0.12, t≈10; the leakage test with shuffled labels gives about 0). It won on Coin Metrics data for 2020–2026.
- Since 2021, though, any long-only altcoin basket lost to BTC, so the ranking skill didn't turn into returns.
- The ranker's signal is mostly a low-volatility / liquidity tilt.

## Round 2 (Nov 6): challengers vs the live rule
Pass bar, fixed before running: beat the live rule's Sharpe AND weekly-difference t > 2.5. All failed.

| Challenger | 7 years | Jul 2021+ | 2024+ |
|---|---|---|---|
| Live rule (reference) | 58.9%, Sharpe 1.24 | 22.2%, 0.71 | 20.5%, 0.67 |
| Ensemble of 50/100/150/200-day trend | 56.6%, 1.25 | 19.7%, 0.68 | 20.2%, 0.68 |
| Volatility-targeted trend | 48.8%, 1.17 | 19.3%, 0.66 | 18.4%, 0.63 |
| AI picks top 2 of the 5 most liquid coins | — | 13.0%, 0.50 | 20.0%, 0.65 |
| Funding-crowding overlay (halve when crowded) | — | — | 16.3%, 0.60 |

Code: scripts/round2.py.

## Long/short (Nov 6): shorting BTC when below the 100-day average
- Shorting lowers Sharpe in every window and for every average length (50–200 days).
- 7 years: BTC long/short 20.2%/yr, Sharpe 0.60, max DD −60%. BTC long/cash: 39.2%, Sharpe 1.00, max DD −40%.
- The short leg lost 64% in total over 7 years. Bear-market rallies whipsaw it; it helped only in 2022 (+16% vs −22%).
- Short carry barely matters. Hyperliquid BTC funding paid shorts about +6%/yr during below-average periods (2023+). Carry scenarios from −5% to +6%/yr move Sharpe only 0.58–0.63.
- US venues for shorting exist, but the venue doesn't change the result:
  - Kraken Derivatives US perps (Bitnomial).
  - Coinbase Financial Markets perps.
  - CME futures.
  - Inverse BTC ETFs.
- Code: scripts/long_short.py.

## Long/short search (Nov 6): 154 candidates, development / hold-out split
Protocol:
- Pick each round's best candidate on development data (Nov 2019 – Dec 2023).
- It must also beat the long-only rule on hold-outs: Jan 2024 – Nov 2026, and Jul 2016 – Nov 2019 where data allows.
- Engine: daily target weights. Costs 0.25% per trade. Short carry from Hyperliquid funding; alt shorts pay an extra 5%/yr.
- Code: scripts/ls_search.py, scripts/ls_validate.py. Every candidate is in reports/ls_search.csv.

Round results:
- **Round A, trend long/short (72 candidates):** adding a BTC short lowered Sharpe for 10 of 12 signals in every period; the other two were near-ties. No winner.
- **Round B, asymmetric shorts, ETH/BTC pairs, rotation (33):** no winner. The ETH/BTC 50-day pair overlay did well on both hold-outs (Sharpe 0.84 recent, 1.97 early) but lost on development (1.44 vs 1.53).
- **Round C, market-neutral baskets (24):** found the only candidate that passed.

**The winner on paper:** live rule + 0.5x a market-neutral low-vol book.
- The book goes long the 3 lowest-volatility and short the 3 highest-volatility of the 30 most liquid coins, refreshed weekly, 25% gross on each side.

| Sharpe | Development | Recent hold-out | 7 years |
|---|---|---|---|
| Live rule | 1.53 | 0.66 | 1.22 |
| Best long-only (50-day) | 1.67 | 0.78 | 1.35 |
| Candidate | 1.67 | 0.99 | 1.43 |

- 7 years: 77%/yr, max DD −42%.
- Wins on all 7 rebalance weekdays.
- Survives 0.5% costs plus a 15%/yr short fee (7-year Sharpe 1.26).

Why it is not adopted:
1. **Not significant.** Improvement t = 1.5 (dev), 1.2 (recent), 1.9 (7 years). The deflated-Sharpe probability after 154 tries is 0.74, below the 0.95 bar.
2. **Not tradable from the US.** 99% of its shorts are memecoins and small caps (BONK, FARTCOIN, ZEC, MOODENG, etc.) with no US-listed perps.
   - Limiting shorts to US-perp coins (SOL, XRP, ADA, LINK, DOGE, LTC, AVAX) gives a 7-year Sharpe of 1.26 vs 1.22, a tie (t ≈ 0).
3. **The short leg lost money** (−14% over 7 years). The gain came from the long low-vol leg (+105%), with the shorts acting as a hedge.

Status: candidate for paper tracking only.

## Practitioner round (Nov 6): 28 strategies from 12 authors, book-default parameters
- Sources: published papers, blogs and documented rules, not the full books.
  - Carver: EWMAC with 6 speeds, forecast scalars, FDM, vol targeting, buffering.
  - Zarattini, Pagani & Barbon (2025): 9-lookback Donchian ensemble, 25% vol target.
  - AQR (Hurst / Ooi / Pedersen): 1/3/12-month TSMOM.
  - Clenow: EMA50/100 filter, 50-day breakout, 3-ATR stop.
  - Antonacci: dual momentum.
  - Kaufman: KAMA 10/2/30.
  - Moreira & Muir: volatility-managed buy & hold.
  - López de Prado: triple-barrier meta-labeling with purged walk-forward, uniqueness weights and AFML bet sizing.
  - Chan: Kalman / Bollinger ETH-BTC pairs.
  - Connors: RSI(2).
  - Liu & Tsyvinski: weekly TSMOM.
  - He, Manela, Ross & von Wachter: cash-and-carry funding arbitrage.
- Engine upgrades:
  - Sharpe measured above T-bills (approximate monthly 3-month rates).
  - Idle cash earns T-bills; leverage pays T-bills + 2%.
- Implementation check: our Zarattini BTC-only replication gave Sharpe 1.63 to Mar 2025 vs 1.56 in the paper. Max DD −19% in both.
- Code: scripts/book_strategies.py, scripts/book_analysis.py, edge/book.py. Results: reports/book_results.csv.

Results (Sharpe above T-bills; full period Jul 2017 – Nov 2026):

| Strategy | Dev | 2024+ | Full | Return/yr | Max DD |
|---|---|---|---|---|---|
| Cash & carry BTC+ETH (May 2023+ only) | 4.28* | 1.64 | 2.15 | 7.7% | −3% |
| Live rule (benchmark) | 1.51 | 0.59 | 1.17 | 64% | −61% |
| Trend ensemble (Carver + Zarattini + Clenow, equal weight) | 1.30 | 0.46 | 1.16 | 21% | −14% |
| Carver EWMAC long-only | 1.36 | 0.48 | 1.14 | 25% | −21% |
| Zarattini Donchian ensemble BTC+ETH | 1.32 | 0.41 | 1.13 | 17% | −13% |
| López de Prado meta-label, AFML sizing | 1.22 | 0.78 | 1.07 | 15% | −11% |
| Clenow long-only | 1.08 | 0.39 | 1.04 | 20% | −15% |
| BTC buy & hold | 0.86 | 0.58 | 0.84 | 44% | −84% |

\*Carry's "dev" covers May–Dec 2023 only.

Long/short versions were worse for Carver, AQR, Clenow, Connors and Liu-Tsyvinski. Chan's pairs, Connors RSI(2) and Moreira-Muir all came in below the benchmark.

Checks:
- **Sharpe-difference tests vs the live rule (Memmel–Jobson–Korkie):** the trend ensemble, Carver and Zarattini are ties (p 0.86–0.98). No strategy beats the live rule's Sharpe significantly.
- **PBO (CSCV, 16 blocks, 23 directional strategies): 15%.** Low overfitting risk in this set; the in-sample winners are usually the live rule or the trend ensemble.
- **Deflated Sharpe after about 220 trials:** carry 0.81, trend ensemble 0.29, live rule 0.19. None passes 0.95.
- **Risk at equal Sharpe:**
  - Trend ensemble: vol 15%, max DD −14%, Calmar 1.49. Live rule: vol 51%, DD −61%, Calmar 1.04.
  - Scaled 3.4x to the live rule's vol, the ensemble returned 63%/yr with DD −46% (needs futures/margin).
- **Carry is fragile and has faded:**
  - By year: +7.5% (part of 2023), +15.4% (2024), +4.5% (2025), −0.2% (2026 YTD).
  - Sharpe since Jan 2025: −1.36, below T-bills.
  - Halving funding (US venues may pay less than Hyperliquid's ~14%/yr, which includes an ~11% baseline) → Sharpe −0.61.
  - 0.5% per leg costs → Sharpe −0.52.
- **Trend + carry mixes:** Sharpe rises with the carry weight, but only because carry is the high-Sharpe, low-vol piece. Not robust.

Conclusion: the highest Sharpe on paper is the carry trade, but it has trailed T-bills since 2025 and breaks under retail costs. Among directional strategies, the live rule is tied for best. The book trend systems match its Sharpe with about a quarter of its drawdown, but earn less unless levered.

## Creative round (Nov 6): hourly data, AI risk models, Coinbase perps
- Goal set by Miles: similar upside to the live rule, Sharpe at least 2x, no losses in down years, tradable on Coinbase, AI in the decision loop.
- Data: 10 years of hourly Coinbase candles for 9 coins (data/hourly).
- Code: edge/intraday.py, scripts/intraday_search.py, intraday_search2.py, validate_c3.py.

Pre-registered tests, all on perps costs (7-year Sharpe above T-bills unless noted):
- **Intraday anomalies failed:**
  - BTC 22–24h UTC seasonality (Padyšák & Vojtko): gross Sharpe 1.63 in 2017–19, but ~0.1 after 2019, so the effect decayed. After costs: −1.59.
  - Shen–Urquhart–Wang intraday momentum/reversal: never worked on Coinbase hourly data, even gross.
- **The AI hourly direction model (LightGBM) failed:** 7-year Sharpe −0.25, and 2024+ −1.12.
- **AI risk overlays did not help:**
  - LightGBM volatility forecasts were worse than the simple HAR model (log-vol RMSE 0.357 vs 0.335; naive 30-day 0.386).
  - Vol sizing and the AI crash guard left Sharpe flat or lower in 2024+.
  - The AI allocator between books hit 55.5% but had a 2024+ Sharpe of 0.09.
- **Live rule checked hourly:** 1.19 vs 1.11. A small gain, no change in losing years.
- **Hourly EWMAC long/short on BTC/ETH (Carver speeds 4/16–128/512 h) is the key finding.**
  - 7-year Sharpe 0.85 on its own, but it made money in bear years: 2018 +86%, 2022 +17%, 2026 +15%; it lost 13% in 2025.
  - Correlation with the live rule is only 0.27.

**Best combination found: C3 = risk parity of the live rule (41%) and the hourly EWMAC long/short (59%), both on Coinbase perps.**
- Weights come from development-period volatility only.
- Unlevered:

| Measure | C3 | Live rule (perps) |
|---|---|---|
| 7-year Sharpe | 1.23 | 1.11 |
| Jul 2017+ Sharpe | 1.42 | 1.14 |
| 7-year return | 42%/yr | 53%/yr |
| Max DD | −21% | −40% |

- **No losing year 2017–2026:**

| Year | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 YTD |
|---|---|---|---|---|---|---|---|---|---|---|
| C3 | +124% | +26% | +64% | +166% | +87% | +3% | +47% | +41% | +2% | +6% |

- **1.5x leverage (similar upside):** 63%/yr, max DD −32%. Down years: 2018 +37%, 2022 +2%, 2025 −2%, 2026 +6%.

Caveats:
- **Not significant:** Sharpe difference vs the live rule p = 0.16–0.86; deflated Sharpe 0.21 after about 250 trials.
- **Cost-sensitive:** the hourly book turns over 100–220x capital per year.
  - At 0.08%/side: Sharpe 1.08, and the down years turn slightly negative.
  - At 0.12%/side: 0.93.
- **Robust to EWMAC speed choice:** dropping any one speed gives 1.19–1.26.
- **Capital and compliance:**
  - A nano BTC contract is ~$760, so the strategy needs roughly $10k+ to size the hourly book properly.
  - Futures need employer compliance clearance.

**Verdict: no strategy reached 2x Sharpe.** C3 meets the "no losing years" and "similar upside" goals (the latter levered 1.5x), with Sharpe up about 10–25%, but it is unproven and fee-sensitive. Status: candidate for paper tracking.

## Renaissance/Citadel-style round (Nov 6): signal library, market-neutral books
- Universe: the 9 coins with US-listed perps (Kraken Derivatives US list): BTC, ETH, SOL, XRP, DOGE, LTC, ADA, AVAX, LINK. Hourly Coinbase data.
- Signal library: 47 signals × 4 horizons (1/4/12/24 h) = 179 rank-IC tests on development 2021-07 – 2023-12. Families:
  - momentum and reversal at 1–720 h, with skip versions;
  - residual vs BTC; BTC-leads-alts lag;
  - volatility, max return, skew; Donchian position;
  - abnormal volume and return × volume;
  - same-hour seasonality.
- Stale-price guard: a coin-hour counts only if volume > 0.
- Code: scripts/xs_search.py. Results: reports/xs_ic.csv, xs_books.csv, xs_search_log.txt.

Results:
- 81 tests passed |t| ≥ 3 on development data. 79 kept the same sign on the 2024–26 hold-out; 71 had hold-out |t| ≥ 2.
  - The signals are real but are all versions of one effect: **short-term cross-sectional reversal** (coins that just rose relative to the others fall back).
  - The strongest is the last 1–2 hours of return: IC −0.06, t −21 dev / −16 hold-out.
  - The effect decays quickly with horizon.
- Composite dollar- and beta-neutral books after perps costs (0.04%/side):

| Rebalance every | Turnover/yr | Gross Sharpe (dev / 2024+) | Net Sharpe (dev / 2024+) |
|---|---|---|---|
| 1 h | 5,594x | 1.80 / 0.57 | −7.2 / −11.4 |
| 4 h | 1,760x | — | −3.4 / −4.1 |
| 12 h | 782x | — | −1.3 / −2.4 |
| 24 h | 231x | — | −0.4 / −1.4 |

  - The 4–24 h books were negative even gross.
- **Pure 1-hour reversal book (the Renaissance-type edge):**
  - Gross Sharpe 4.34 dev, 2.52 on the 2024–26 hold-out. Gross return 117%/yr dev, 48%/yr hold-out.
  - Turnover 10,708x capital per year, so break-even cost is 1.09 bp (dev) / 0.45 bp (hold-out) per side.
  - With a 1-hour execution delay it collapses: gross Sharpe 0.55 / 0.10. The edge lives in the minutes after each move (liquidity provision and bid-ask bounce).
  - Retail perps cost ~2–4 bp per side, which is 4–9x the break-even.
- Conclusion: Sharpe > 2 exists in this data, but only at market-making speed and cost. It can't be captured with a basic retail plan. No neutral pod survived costs, so the multi-pod portfolio reduces to C3.

## Minute-level test of the reversal (Nov 6)
- Data: 1-minute Coinbase candles, Jan 2024 – Nov 2026 (data/minute, 1.5M minutes × 9 coins). This period was never used for selection.
- Code: scripts/minute_reversal.py. Results: reports/minute_reversal.csv, roll_spreads_bp.csv.
- Method: long the losers, short the winners over the last L minutes, dollar-neutral, held L minutes, entered d minutes late. All Sharpe ratios below are gross, before any costs.

| L (min) | Delay 0 | 1 min | 5 min | 10 min | Break-even/side at 5–10 min delay |
|---|---|---|---|---|---|
| 5 | 18.9 | 7.1 | 2.7 | 2.5 | 0.04 bp |
| 15 | 9.1 | 5.7 | 4.0 | 4.1 | 0.19–0.20 bp |
| 30 | 4.4 | 2.2 | 1.7 | 1.3 | 0.12–0.16 bp |
| 60 | 1.9 | 1.2 | 1.2 | 1.1 | 0.21–0.23 bp |

- Turnover: 143,298x / 47,589x / 23,687x / 11,838x capital per year for L = 5 / 15 / 30 / 60.
- **The 15-minute reversal is real, not bounce.**
  - It survives a 10-minute delay, on liquid coins only (BTC, ETH, SOL, XRP, DOGE: gross 3.1–3.2), and in every year (2024: 3.2, 2025: 5.3, 2026: 4.5).
  - But the edge per trade is only ~0.2 bp.
- **Spreads beat the edge.** Roll effective spreads (round trip, bp): BTC 1.4, ETH 2.6, SOL 1.8, DOGE 0.9, LTC 3.1, ADA 1.6, AVAX 2.0, LINK 1.1.
  - That is a half-spread of ~0.4–1.5 bp per side, already above the 0.2 bp edge before any fee.
  - So taker execution loses at any fee level, even zero.
- **Capacity is small.** Median 15-minute Coinbase volume vs. a 15-minute-rebalanced book:
  - At $100K capital, trades are 0–19% of volume per coin (AVAX 19%, LTC 16%).
  - At $1M, 60–194% for DOGE, LTC, ADA, AVAX and LINK. Impossible.
- **Meaningful capital:** at ~48,000x turnover, about $63K of capital already trades $250M a month (Coinbase VIP 8: 0% maker / 0.02% taker). Volume tiers come quickly, but they don't fix the spread, and capacity caps the strategy around $100K.
- **Conclusion:** the continuous reversal can only be harvested as a maker. A two-sided spot market-making test (other session, reports/maker_prereg.md) was rejected. The tradable version is the one-sided, event-driven "wick catcher" in the Execution round above.

## Maker round (Nov 6): quoting the reversal passively on Coinbase tick data — rejected
- Question: can the 1–15 minute reversal (edge ~0.2–0.3 bp, smaller than the spread) be harvested as a maker — post-only quotes at the touch, skewed by signal and inventory?
- Pre-registered before any test: reports/maker_prereg.md (commit 01c84b4). Dev selection frozen before the hold-out ran (commit f92b83b). One logged deviation: the robustness re-run below.
- Data: Tardis.dev free first-of-month Coinbase files (top of book with sizes + trades), BTC, ETH, SOL, XRP, DOGE.
  - 35 days: development Jan 2024 – Jun 2025 (18), hold-out Jul 2025 – Nov 2026 (17).
  - Checks: no trade ever printed inside the prior quote; each book update follows its trade by ~5 ms (median).
  - Quoted spreads on 1 Jan 2024: BTC 0.67 bp, ETH 0.82, SOL 1.96, XRP 1.62, DOGE 2.22 (median).
- Simulator (edge/maker.py, 14 hand-checked tests): queue position at our price, fills from queue depletion, trades through our price and crossings, post-only rejects, latency, inventory caps.
  - Latency: 3 ms (co-located; out of reach at retail), 60 ms (cloud VM, REST orders), 120 ms (2×).
  - Queue: risk-averse (only trades move us up) and proportional (cancels spread through the queue).
  - Book: $1,000 quotes, $2,000 per-coin inventory cap ($10K); ×10 for $100K.
- Strategies: S0 symmetric, S1 skewed toward the signal's target inventory, S2 passive tracker of the reversal portfolio.
- Signal, fit on dev only: 3.4% of a coin's 15-minute move vs the others reverses in the next 15 minutes (t = 4.1). Typical expected edge 0.34 bp; 80th percentile 0.76 bp.
- Code: scripts/maker_day.py (runs on GitHub Actions; raw ticks never committed), scripts/maker_analyze.py. Results: reports/maker/.

Results: P&L per dollar traded before fees, measured as the realized spread against the mid 60 s after each fill.

| Setups ($10K book) | Dev | Hold-out |
|---|---|---|
| All 18 (3 strategies × 3 latencies × 2 queue models) | −0.70 to −0.86 bp | −0.66 to −0.82 bp |
| Selected S0, 60 ms, risk-averse | −0.85 bp | −0.73 bp (per-day t = −28) |
| 3 ms latency only | −0.70 to −0.81 bp | −0.75 to −0.82 bp |
| By coin (S0, 60 ms) | BTC −0.61, ETH −0.74, SOL −1.02, XRP −0.82, DOGE −1.23 | BTC −0.58, ETH −0.66, SOL −0.88, XRP −0.71, DOGE −1.03 |

- Every setup loses before fees, in both periods, on every coin. S0 was positive on 0 of 35 days.
- Hold-out S0, $10K: −$11.3K per day on $153M traded. It lost the whole $10K within the day on 19 of 35 days. S2, the lowest-volume version, lost $2.9K per day.
- Why it loses: adverse selection, not inventory drift. Most of the loss lands within a second of the fill (S0 dev: −0.41 bp at the fill, −0.77 bp at 1 s, −0.85 bp at 60 s, flat to 15 min).
  - A newcomer at the back of the queue gets filled mainly when the price runs through its resting quote (69–72% of fills at 60 ms, 53–54% even at 3 ms) or by trades big enough to clear the whole queue. That flow is informed.
  - Being faster cut the loss in dollars (fewer stale fills) but not per dollar traded. Profitable quoting needs queue priority, i.e. being first at new price levels: HFT infrastructure.
- The signal helps, but by a tenth of the gap: the signal-driven versions lose 0.04–0.11 bp less per dollar than symmetric quoting (S2 vs S0: dev −0.74 vs −0.85 bp, hold-out −0.67 vs −0.73 bp).
- Fees can't fix it: break-even is a −0.74 bp maker fee, i.e. a rebate. Coinbase's best maker fee at any tier is 0.00%. Climbing to 0% (VIP 6, $50M a month) costs up to ~$15K in fees on the way at the listed rates, more than the capital.
- Realism limits, both of which flatter the strategy: S0 needs ~31 API requests/s on average (peaks ~200/s) vs Coinbase's 30/s; and simulated fills exceed what thin books could supply (about 40% of DOGE's Coinbase volume at $10K; more than the whole market for four coins at $100K). So the $100K figures overstate capacity; neither changes the sign.
- All 7 pre-registered bars fail (t, deflated Sharpe, Sharpe ≥ 2.4, no losing year, $100K capacity, 2× stress). **Verdict: reject.**
- Independent review (separate agent, read-only): no bug that flips the sign. It flagged two rules that bias against the strategy (chasing every move of the touch; crossings filling our full size). A logged re-run fixing both (crossings capped at the displayed size; quotes that keep queue place within 0.5 or 2 bp of the touch) changed nothing: −0.72 to −0.97 bp per dollar, 0 positive days in any variant, and even pure queue fills lost 0.42–0.63 bp per dollar. Sticky quoting cut API load to 2–25 requests/s but lost more per dollar. Results: reports/maker/sens_summary.csv.
- US perps (judged by arithmetic, no order-book history exists): the Coinbase Derivatives fee is $0.10 per contract per side for makers too = 1.3 bp on nano BTC, 4.5 bp on nano ETH, before clearing/FCM charges. The best case for a maker before adverse selection is ~0.7–1.1 bp (half a $5 tick + the signal). Rejected.
- Not tested: posting inside the spread (price improvement). Historical data can't show competitors re-pricing around us, so any result would be optimistic.

## C3 upgrade round (Nov 6): turnover cuts and realistic nano-perp costs
- Pre-registered with the maker round. Book run as one netted account.
- Realistic costs: BTC 2.5 bp, ETH 6.5 bp per side (exchange fee + clearing/FCM + half a tick), positions rounded to whole contracts (0.01 BTC, 0.1 ETH) at $10K. 2× stress doubles both.
- Code: scripts/c3_improve.py. Results: reports/c3_improve.csv.

| Book (Sharpe above T-bills) | Turnover/yr | Dev | 2024+ | Jul 2017 – Nov 2019 | 7 years | 7 years at 2× cost |
|---|---|---|---|---|---|---|
| C3 | 104x | 1.61 | 0.53 | 1.92 | 1.21 | 1.05 |
| C3-B: buffer 0.25 | 76x | 1.60 | 0.55 | 1.89 | 1.21 | 1.09 |
| C3-F: drop 4/16 h speed | 69x | 1.59 | 0.57 | 1.90 | 1.21 | 1.11 |
| C3-BF: both | 54x | 1.60 | 0.56 | 1.84 | 1.22 | 1.13 |

- Realistic costs barely move C3 (7-year Sharpe 1.22 → 1.21): buffering already made it cost-efficient.
- No variant passes the pre-registered replacement rule (every dev Sharpe ≤ C3's; all differences |z| < 1.4). **C3 stays as is.**
- C3-BF halves turnover at the same Sharpe and holds up better at 2× costs. It is the pre-declared fallback if measured costs run ≥ 2× the model.
- C3 risk at realistic costs (Jul 2017 – Nov 2026): vol 31%, max DD −22.5% at 1x and −32.5% at 1.5x, longest time under water 430 days, worst 30 days −16% at 1x.
  - 2024+: 16%/yr, max DD −21% at 1x.
  - Years at 1x: 2022 +2.7%, 2025 +0.1% (no losing year, barely). At 1.5x, 2025 is −4.1%.
- Deflated Sharpe 0.10 after 476 trials. **Verdict: paper-trade C3; nothing reaches the 2.4 Sharpe target.**

### C3 kill switches (paper and live)
1. Drawdown: stop and review at −30% from peak at 1x (backtest worst −22.5%); −42% at 1.5x.
2. 30-day loss worse than −11% at 1x (backtest 1st percentile): halve size until a new equity high.
3. Rolling 6-month Sharpe below −1.6 (backtest 1st percentile): stop and re-test.
4. Costs: measured all-in cost per side above 2× model (BTC > 5 bp, ETH > 13 bp) for two weeks: switch to C3-BF.
5. Funding: Coinbase funding paid above the model by more than 10 points a year over 30 days: re-run the backtest on live funding before continuing.
6. Tracking: live P&L differs from the paper model by more than 0.5% of capital on 3 of 10 days: stop and reconcile.
7. Operations: a missed hourly signal 2 hours running, or a position more than 1 contract off target for 15 minutes: alert. Stale for 3 hours: flatten the hourly sleeve.
8. Leverage: gross ≤ 1.5× equity; margin used ≤ 50% of available.

### C3 30-day build plan (from Nov 9)
- Week 1:
  - Sculptor compliance pre-clearance for personal crypto futures trading (blocking for anything live).
  - Open the Coinbase Financial Markets futures account; create a read-only API key.
  - Hourly signal job: C3 target contracts for nano BTC/ETH perps, contract rounding, kill-switch checks; writes signals/c3_latest.json and a paper ledger.
- Week 2:
  - Paper fills at the live Coinbase Derivatives touch plus per-contract fees, from public market data.
  - Record actual spreads, depth and funding to replace the 2.5 / 6.5 bp and Hyperliquid-funding assumptions.
  - Daily paper-vs-backtest report.
- Week 3:
  - Execution module in dry-run: post-only at the touch, marketable after 60 s; hourly position reconciliation; kill switches in code; alerts through GitHub issues (email + app) as today.
  - After compliance approval only: a one-contract live test of order and position plumbing.
- Week 4: go / no-go.
  - Go live at 1x on $10K only if tracking error, measured cost per side, funding and uptime are within tolerance.
  - 1.5x only after 3 months without a kill-switch trigger.
- AI in the loop: none for decisions; every AI decision component tested so far failed (direction, volatility, crash guard, allocator). Use AI to review the daily reconciliation report.

## Scale round (Nov 6): Simons lessons vs. 100% a year at $5M
- Target set by Miles: 100%+ a year on average, working up to $5M, retail tools, AI where useful, largely market neutral.
- Lessons from *The Man Who Solved the Market* (Zuckerman), as they apply here:
  1. **Many small edges, many bets.** Medallion was right only about 50.75% of the time, over a huge number of trades. Here: the wick catcher (R2-08) wins 70% of 1,264 trades at ~38 bp net each.
  2. **Overreaction and snap-back.** Prices overshoot and revert; the trick is being there when they do. Here: resting bids under forced selling work; quoting at the touch for everyone doesn't (maker round).
  3. **Costs first.** Per-contract fees and adverse selection decided every round here.
  4. **One model over many weak signals.** Here the LightGBM filter is the edge (Sharpe 0.24 without it, ~3 with it); AI direction calls and overlays failed.
  5. **Leverage only on short-horizon, high-Sharpe books.** Medallion ran roughly 12x on a low-volatility book.
  6. **Capacity rules everything.** Medallion was capped around $10B and returned outside money. Renaissance's scalable funds earned ordinary returns: in 2020 Medallion made about +76% while RIEF lost 22.6% and RIDA 33.6%.
  7. **No overrides; rules set before results.**
- Math: return ≈ Sharpe × volatility. At the wick catcher's Sharpe ~3, 100% a year needs ~33% volatility, twice the paper-trade size. At $5M, 100% means $5M of profit a year.
- Capacity test (scripts/wick_capacity.py; reports/wick_capacity.csv, wick_capacity_trades.parquet):
  - A resting bid can buy at most the volume that traded below its level while the price stayed there; those sellers had already cleared every bid at our price. Each 1-minute candle's volume is spread evenly over its range; Coinbase spot and perp books both count.
  - Take-profits are capped by the volume above the exit price; the rest sells at the 60-minute mark with square-root impact (0.7 × daily vol × √(size / daily volume)).
  - Fees: the cheaper of the lab's realistic perp costs and Coinbase spot fees at the tier the book itself reaches.
  - Entry capacity per trade: median $280K across both books (p25 $55K, p10 $9K); ETH/SOL/XRP $1–3M; ENA/NEAR ~$40K.

| Capital (we capture half the through-volume) | 25% of capital per trade (paper size) | 50% per trade (2x) |
|---|---|---|
| $10K | 58%/yr, Sharpe 3.1, max DD −10% | 110%/yr, Sharpe 3.1, max DD −18% |
| $50K | 46% | 75% |
| $100K | 38% | 52% |
| $250K | 22% | 11% |
| $500K | 6% | −14% |
| $1M | −7% | −26% |
| $5M | −20% | −40% |

  - Exits bind before entries: at size, the take-profit can't all sell into the rebound and market exits pay impact.
  - Capping the size per trade instead: profit peaks near $50K a year (range $30–80K across capture assumptions), at about $50K per trade. At $5M that is ~1% a year.
- Market neutrality: daily P&L beta to BTC 0.03 (correlation 0.07); a trade on 42% of days, ~35-minute holds. Already largely market neutral; a BTC hedge hurt (lab: 0.57).
- **Verdict: no edge found meets 100%+, $5M and market neutral together.**
  - 100% + market neutral: the wick catcher at 2x, only up to roughly $25–50K of capital.
  - $5M + market neutral: carry and basis trades, single-digit to low-teens returns.
  - $5M + high return: directional (C3 at 1.5x: ~60% a year in backtest, −33% drawdown).
- Untested ways to raise capacity: more books for the same dips (the Coinbase spot long tail, since dip bids don't need perps, and other NY-licensed spot venues such as Gemini and Bitstamp); perp-vs-spot basis wicks (market neutral by construction); exits worked over several minutes.

## Method notes
- Point-in-time top-50 universe by 30-day median dollar volume.
- Walk-forward retraining every quarter, with an 8-day purge between training data and the test period.
- Hyperparameters frozen before seeing any results.
- Weekly-only trend checks were fragile: 7%–26% CAGR depending on the weekday. Fixed with daily checks and averaging across all 7 weekday phases.
- About 482 variants in the earlier rounds (incl. the maker and C3 upgrade rounds), about 2,000 setups in the execution round and
  130 in the wick v2 lab, so an improvement needs t ≈ 3 to be believable.
- Tick-data rounds: pre-register, freeze the dev choice in a commit, then run the hold-out once. Raw tick files stay on the
  CI runner.

## Known gaps
- Coins delisted from Coinbase are missing (survivorship bias favors the alt strategies).
- Taxes are excluded.
- T-bill rates are approximate monthly levels.
- Hyperliquid funding and perp history only goes back to May 2023. Coinbase's own perp funding history isn't available.
- News and event (unlock, hack, depeg) screening hasn't been backtested.
- The live rule was chosen after seeing most of this data.
- Retail fills on hourly rebalances may cost more than 0.04%/side.
- Maker fills are simulated from 1-minute candles (trade-through rule). Queue position inside the minute and partial fills
  aren't observable there; the paper test logs order-book depth ahead of each bid to measure them.
- Tick data (maker round) covers only the first day of each month (35 days, Tardis free tier). Coinbase Derivatives order-book
  history isn't available.
- Wick-catcher capacity is estimated from 1-minute candles (volume spread evenly over each candle's range); real depth
  during wicks is unobserved until the paper test logs it.
