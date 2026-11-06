# Medallion round: every Renaissance strategy, crypto version — pre-registration

Committed 2026-11-06 before any of the new data (data/alt/) was opened. Rules here are fixed; deviations go in the
log at the bottom with a reason.

## Goal (Miles, Nov 6)

Trade crypto the way Medallion did; try every strategy family the book describes Renaissance trying; get new data
where needed; must be implementable by a retail investor in New York; priority is high Sharpe at $5M (returns via
leverage).

## What the book says Renaissance tried → crypto test here

| Book (who) | Crypto test (family) |
|---|---|
| Sunspots, lunar phases (Simons, Baum, Straus) — failed | F0 placebo: lunar phase. Must fail; checks our false-positive rate |
| Weather → coffee (Straus); sentiment and futures traders' holdings — few patterns | F1 positioning and sentiment: fear & greed, funding, open interest, top-trader and taker ratios |
| Markov-chain / hidden Markov models (Ax, Baum; Brown & Mercer's background) | F2 HMM regime book |
| "Find past periods like now and see what prices did" — Carmona's kernel regression | F3 nearest-neighbour (kernel) pattern book |
| Trend-following (Axcom) | Already tested: C3 is the base |
| Reversion; "24-hour effect": yesterday predicts today; cross-period correlations (Berlekamp, Laufer) | F4 daily return-sequence signals |
| Day-of-week (Monday follows Friday; Tuesday reverts), best day and time, week split into sessions (Laufer) | F5 calendar and session seasonality, incl. weekend / CME-gap and funding-hour effects |
| Pairs and relative value | F6 cointegration pairs on Coinbase-perp coins |
| Factor models → statistical arbitrage, predictions relative to peers (Frey, Brown, Mercer) | F7 cross-sectional factor book (residual reversal, momentum, funding carry, open interest) |
| "Hundreds of metrics", alternative data | F8 alternative data: Coinbase premium, CME basis, stablecoin supply, ETF flows, implied vol, on-chain, macro |
| Humans most predictable under stress; option buyers overpay | F9 short volatility (variance risk premium) |
| One model for everything; online learner searching for signals (Laufer, Brown & Mercer) | F10 one combined model (ridge and LightGBM) |
| Cost model "The Devil"; leverage via basket options | Realistic Coinbase costs everywhere; leverage via perps |

## Data (all free and public; offshore-exchange data used only as research signals)

Coinbase hourly/daily prices (existing); Binance USD-M archive (funding since 2019-09, 1h perp klines, 5-minute
open-interest and taker/top-trader metrics since 2021-12 for BTC/ETH/SOL/XRP/DOGE); Binance spot 1h (Coinbase
premium); Deribit DVOL (2021-03+); alternative.me fear & greed (2018-02+); DefiLlama stablecoin supply; Coin Metrics
community on-chain; blockchain.com hash rate/transactions; Farside ETF flows (2024+); yfinance CME BTC/ETH futures,
VIX, dollar index, 10y yield, S&P and Nasdaq futures, gold.

## Timing and periods

- Daily bars close at 00:00 UTC (Coinbase). A signal for day t uses only data published by the end of day t (US
  market data from the prior US close, one-day lag for on-chain and ETF flows); it predicts day t+1 (or t+1..t+7).
- Development: 2020-01-01 – 2023-12-31 (from first data where later). Hold-out: 2024-01-01 – 2026-11-05, opened once.
- Hourly families: development 2017-07-01 – 2023-12-31, hold-out 2024+.

## Signal screen (F0, F1, F4, F8; time-series, BTC and ETH, 1-day and 7-day forward returns)

Each signal is a rolling z-score (365-day window, 90-day minimum) of the raw quantity:
- F0: cosine of lunar phase.
- F1: fear & greed level and 7-day change; funding (daily mean) level and 7-day change; open interest 1-day and 7-day
  change; top-trader long/short ratio (accounts and positions); taker buy/sell volume ratio.
- F4: returns over 1, 2, 3, 5, 20 days; 5/30-day realized-vol ratio; volume z-score; distance from 20-day high.
- F8: Coinbase premium level and 7-day change; CME basis (annualized, front month); stablecoin supply growth 7d and
  30d; DVOL level, DVOL − 30-day realized vol, DVOL 7-day change; on-chain growth (active addresses, transactions,
  fees, hash rate) 30d, MVRV and NVT levels; prior-day VIX change, dollar index, 10y yield, S&P and Nasdaq futures
  and gold returns. ETF flows start in 2024, inside the hold-out, so they are described but cannot pass.
- Statistic: Spearman IC between signal and forward return; t-stat with Newey-West lags = horizon.
- **Pass:** development |t| ≥ 3, then the hold-out has the same sign and |t| ≥ 2.

## Books (one fixed specification each; no tuning)

- **F2 HMM:** 2-state Gaussian HMM on daily log returns (BTC; ETH), refit monthly on all prior data (min 2 years);
  long when the filtered probability of the higher-mean state > 0.5, else flat; and a long/short version.
- **F3 nearest-neighbour:** features = last 1, 2, 3, 5, 10, 20-day returns and 20-day vol (z-scored); predict
  next-day return as the mean of the 50 nearest past days (Euclidean, all prior data, ≥ 1 year); position =
  sign(prediction), long/short, vol-targeted.
- **F5 seasonality:** (a) hour-of-week book: trailing 52-week mean return per hour-of-week per coin (9 coins); hold
  the hour when |mean| > 2 × one-way cost; (b) day-of-week book: trailing 104-week mean by weekday, daily
  long/short; (c) weekend/CME-gap: the Friday 21:00 → Sunday 23:00 UTC move, faded from Sunday 23:00 to Monday
  21:00 UTC; (d) funding-hour book: the hour into 00/08/16 UTC vs the hour after.
- **F6 pairs:** monthly, pairs among the Coinbase-perp coins with Engle-Granger p < 0.05 on the trailing year; enter
  at |z| > 2 of the spread, exit at |z| < 0.5 or after 20 days; equal risk per pair.
- **F7 factor book:** daily, Coinbase-perp coins with Binance perp history; z-scored signals of 1-day residual reversal
  vs BTC, 7- and 30-day momentum, funding carry (short high funding), 7-day open-interest change; combined with
  signs and equal weights from development ICs; dollar- and beta-neutral; plus funding carry alone.
- **F9 short volatility:** each day sell one day of BTC (and ETH) variance at DVOL²/365 and pay the realized squared
  return (delta-hedged short straddle proxy), minus 1 vol point of option spread per 30 days; scaled to 20% vol.
- **F10 one model:** all F0/F1/F4/F8 signals, ridge (alpha fixed at 10 on standardized features) and LightGBM (book
  defaults, 200 trees, depth 3), retrained monthly on prior data from 2021; predicts next-day BTC and ETH returns;
  position = prediction / its trailing 1-year std, capped ±1, vol-targeted.
- Costs: Coinbase perps BTC 2.5 bp, ETH 6.5 bp, alts measured half-spread + $0.20/contract (reports/lab/cost_table.csv
  where available, else 15 bp) per side; F9 as stated. All Sharpe ratios above T-bills, daily.

## Pass bars and combination

- **A book passes** if development Sharpe ≥ 1.0 and hold-out Sharpe ≥ 0.5 with the same sign.
- **Portfolio:** passing books are added to C3 by inverse development volatility. The portfolio replaces C3 only if
  its development Sharpe is higher and neither hold-out is worse (same rule as the earlier rounds).
- Report: deflated Sharpe (N = 484 earlier trials + this round's books), capacity at $5M against Coinbase volume and
  open interest, leverage for 50% and 100% a year with the drawdown.
- Trial count this round: 17 books (F2 4 = BTC/ETH × long-flat/long-short; F3 2; F5 4; F6 1; F7 2; F9 2; F10 2).
  The signal screen is ~150 tests, handled by the t ≥ 3 + hold-out rule, not by deflated Sharpe.

## Deviation log

**Implementation notes (2026-11-06, committed with scripts/medallion/ before any statistic on data/alt was computed).**
The specification above left these details open; they are fixed here. Development-period runs of F2, F3, F5 and F6
(Coinbase prices only) were made while debugging the code; nothing in the specification was changed after them.
1. Funding paid in every new book: Binance USD-M (sum of the day's prints) where available, else Hyperliquid
   (data/funding), else 8% a year. (Earlier rounds used Hyperliquid or 8%; C3 itself is unchanged.)
2. Taker ratio: daily log(taker buy / taker sell quote volume) from Binance 1h perp klines (longer history than the
   5-minute metrics files). Top-trader ratios: daily mean of hourly values. Open interest: last value of the day, in
   coins.
3. Coinbase premium: daily mean of hourly (Coinbase close / Binance spot USDT close − 1).
4. CME basis: yfinance continuous front-month close vs the Coinbase close at the matching Chicago time (the hour is
   chosen by the smallest variance of daily basis changes, a measurement check that uses no forward returns);
   annualized with days to the last Friday of the month, floored at 7.
   *Update after the data arrived (measurement checks only, no forward returns):* 15:00 CT matches best (s.d. of daily
   basis changes 0.70% vs 1.3–1.7% at 13, 14, 16, 17 CT; Yahoo's close is the settlement). Yahoo rolls the series a
   few days before expiry and prints the final settlement on expiry day, which makes jumps of 3–6%; days within 5 of
   expiry are therefore left out (no signal), replacing the floor of 7.
5. On-chain growth: 7-day mean, then 30-day log change, lagged one day. NVT: NVTAdj, else market cap / adjusted
   transfer value. Macro: change from the previous US close on the US date; missing on days without a US close.
6. F2: hmmlearn GaussianHMM (diagonal, 200 iterations, seed 0) on 100 × log returns; positions of one unit.
7. F3: features standardized with the mean and std of all rows up to the current day; 25% vol target, cap 2x.
8. F5: development 2017-07-01 – 2023-12-31 for all four books; weight 1 / (coins trading). (c) BTC and ETH, ±0.5
   each. (d) uses the sign of the last settled Binance print: short the hour into settlement and long the hour
   after when funding is positive, the reverse when negative.
9. F6: the alphabetically first coin is the dependent variable; positions close at month end; each pair sized to 10%
   annualized spread vol; gross capped at 4.
10. F7: universe = coins with a Coinbase price 30 days back, a 90-day beta to BTC and Binance funding; weights
    neutral to [1, beta] by projection, gross 1; open-interest signal 0 for coins without metrics.
11. F9: constant scale giving 20% development vol; sold implied vol = DVOL − 1 point.
12. F10: one pooled BTC+ETH model; missing features 0 for ridge, native for LightGBM; 12.5% vol target per coin.
13. Hold-out lock: hold-out numbers are computed only when MEDALLION_HOLDOUT=1.
14. Coin Metrics' community API withholds FeeTotUSD, NVTAdj and TxTfrValAdjUSD. BTC fees and NVT come from
    blockchain.com instead (transaction-fees-usd; market cap / estimated-transaction-volume-usd, both 7-day means),
    lagged one day. ETH has no free source for them, so its fee and NVT signals are dropped (4 fewer tests).
15. Data coverage as delivered: Binance funding and perp klines start 2020-01 (not 2019-09); DVOL 2021-03-24;
    Farside ETF pages show only recent weeks (19–21 rows), so ETF flows are not tested at all.
