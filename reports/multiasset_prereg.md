# Scale round 2: highest Sharpe that holds at $5M — pre-registration

Committed 2026-11-06 before any multi-asset data was downloaded or any result produced.

## Objective (Miles, Nov 6)

The highest Sharpe that still works at $5M of capital. Returns come from leverage, so Sharpe and capacity are what
count. Earlier rounds: the crypto-only books that scale (C3, live rule) run at Sharpe ~1.2–1.4; the higher-Sharpe
wick catcher tops out near $50K of profit a year.

## Hypotheses (2 trials)

- **H1 (primary).** Adding a trend sleeve built only from non-crypto contracts that Coinbase Derivatives already lists
  (same US account, available in New York) to C3 raises Sharpe without hurting either hold-out.
- **H2 (sensitivity).** Adding Treasury and currency trend, which needs a CME futures account at a retail broker,
  raises it further.

## Instruments (daily total-return closes from yfinance, used as proxies)

| Contract on Coinbase Derivatives | Proxy |
|---|---|
| US500 index perp | SPY |
| Tech100 index perp | QQQ |
| China index perp | FXI |
| Gold futures / PAXG perp | GLD |
| Silver futures | SLV |
| Nano crude oil futures | USO |
| Natural gas futures | UNG |
| Copper futures | CPER (2011+) |
| Platinum futures | PPLT (2010+) |

CME extension (H2): TLT, IEF (Treasuries), UUP (US dollar), FXE (euro), FXY (yen).
AI and Defense index perps are excluded: no long history.
Excess return = proxy total return − T-bill (edge/book.rf_daily). Non-crypto returns are zero on days the US market is
closed; the book runs on calendar days like the crypto sleeves.

## Multi-asset trend sleeve (book defaults, nothing tuned)

- Carver EWMAC on daily closes, speeds 8/32, 16/64, 32/128, 64/256. Forecast scalar = 10 / expanding mean |raw|
  (1-year minimum), cap ±20, combined forecast × 1.15, cap ±20. Long and short.
- Instrument vol: 35-day EWMA of daily returns, annualized (√256), floored at 5%.
- Position = forecast/10 × instrument weight × IDM × 25% / instrument vol. Equal instrument weights. IDM from
  development-period correlations of the instrument sub-systems, capped at 2.5. Buffer 10% of the unit position.
  Gross cap 4x.
- Instruments enter when their history allows (forecast scalars need 1 year).

## Portfolio

- **P1 = C3 + Coinbase multi-asset sleeve**, weights by inverse development-period volatility (the same risk-parity rule
  that built C3). **P2 = C3 + Coinbase + CME sleeve**, same rule.
- C3 exactly as in the C3 upgrade round (netted, realistic nano-perp costs, whole contracts at $10K).

## Costs

- Non-crypto per side: 3 bp for SPY/QQQ/GLD/SLV/USO and the CME extension; 6 bp for UNG, CPER, PPLT, FXI.
- C3: BTC 2.5 bp, ETH 6.5 bp per side. Stress: everything 2×.
- Funding on the index perps is assumed to equal the T-bill carry already removed (unverified).

## Periods and rule

- Development 2019-11-06 – 2023-12-31; hold-outs 2024-01-01 onward and 2017-07-01 – 2019-11-05.
  The multi-asset sleeve alone is also reported from 2010 (long-history check).
- **P1 replaces C3 only if** its dev Sharpe beats C3's and it is not worse than C3 on both hold-outs. P2 is judged
  against P1 the same way.
- Also reported: Memmel z vs C3, deflated Sharpe (N = 484), by-year returns, max drawdown, correlations.

## Leverage and capacity at $5M

- Leverage needed for 50% and 100% a year and the full-period max drawdown at that leverage.
- Capacity: position per contract at the 100%-a-year leverage on $5M vs Coinbase 24-hour volume and open interest
  (reports/cfm_products.csv). Flag any contract above 5% of daily volume or 20% of open interest.
- The wick catcher is reported separately as an overlay (only 2025–26 data; ~$50K a year at capacity).

## Deviation log

(none yet)
