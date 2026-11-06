# Research results (2021-07-11 to 2026-11-05)

Universe: point-in-time top 50 USD-tradable coins by 30-day volume (682 coins in data). Costs: 0.25% per side.

| Strategy | CAGR | Vol | Sharpe | Max DD | CAGR @0.5% cost |
|---|---|---|---|---|---|
| BTC buy & hold | 16.5% | 52% | 0.55 | -77% | 16.4% |
| Equal-weight top 50 | -28.4% | 77% | -0.04 | -93% | -29.8% |
| BTC trend filter | 19.8% | 36% | 0.68 | -37% | 18.1% |
| Momentum top 10 + trend | -11.3% | 62% | 0.12 | -80% | -15.3% |
| Low-vol top 10 + trend | 17.3% | 48% | 0.57 | -58% | 14.9% |
| AI model top 10 + trend | 8.2% | 46% | 0.40 | -64% | 3.4% |
| AI model top 10 (no filter) | -8.6% | 64% | 0.18 | -81% | -14.8% |
| AI model top 3 + trend (aggressive) | 12.6% | 45% | 0.49 | -54% | 7.1% |

Weekly IC (Spearman, non-overlapping): ai_model +0.121 (t +9.8), momentum_28d -0.032 (t -2.4), low_vol +0.120 (t +8.1)

Head-to-head (weekly return difference):
- AI model top 10 + trend vs Low-vol top 10 + trend: -0.171%/wk, t -1.14
- AI model top 10 + trend vs BTC trend filter: -0.086%/wk, t -0.32
- Low-vol top 10 + trend vs BTC trend filter: +0.085%/wk, t +0.32
- AI model top 10 + trend vs Momentum top 10 + trend: +0.250%/wk, t +0.95
