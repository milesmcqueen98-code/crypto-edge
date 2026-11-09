# EXP: the Deribit Friday expiry unwind (Path B sleeve), REPORT

**Verdict: FAIL.** HOLD book Sharpe gain −0.04 (B1 needs ≥ +0.5), alpha t −10.2 (B2), both HOLD eras negative (B3); B4 passes only because the book is 90% incumbent. The frozen variant lost money before costs on HOLD.

## Mechanism
Deribit options settle at 08:00 UTC to a 07:30–08:00 TWAP of its index, so the expiring options' deltas leave dealers' books linearly across the window. Dealers who hedged them must unwind a size and direction known in advance. If dealers are net long delta in the expiring options (D > 0), they hold short hedges and must buy them back (F = +D). A follower trades with that flow inside the window; a liquidity provider fades its impact after 08:00.

## Data
- Deribit (history.deribit.com, 20 Actions fetch runs, all succeeded, every month 2021-01..2026-11 present): 22,980,230 BTC and 16,036,874 ETH option trades; totals reconcile exactly with the derive. Dealer inventory per option = −cumulative signed taker contracts since listing. Options listed before 2021-01-01 (432 BTC, 450 ETH, by Deribit's creation_timestamp; every traded instrument was found in Deribit's list) are excluded; none is live after 2021.
- D = Σ inventory × Black–Scholes delta (last traded IV, index at 07:29, T = 31 min) of the options expiring that Friday, from trades before 07:29:00 (scripts/hunt2/gamma/derive_deribit.py, run 42545078490). 65 DEV Fridays per coin; HOLD 135 (early 104, chk 31). DEV inputs: BTC D median +74 coins (IQR −815..+1,575), ~72 expiring options per Friday.
- Coinbase 1-minute candles: spot BTC/ETH 2021–2026; CFM perps from 2025-07-18.

## Construction (fixed in scripts/hunt2/exp/exp.py's docstring, commit 5ca2d24, before the first trial)
- F = D / (trailing 30-day mean 30-minute Coinbase spot volume; BTC median 173 coins). Fire when |F| ≥ the DEV median of |F| for that coin and event set (all Fridays: BTC 5.75, ETH 3.54; last Friday of the month, "mq": BTC 20.43, ETH 7.37).
- Window fade: |log r(07:30→08:00)| ≥ the trailing 30-day σ of 30-minute returns; enter −sign(r) at 08:01.
- Taker at the named minute's open. Before 2025-07-25: spot candles (first candle within 5 minutes). After: CFM candles when both legs' exact minutes have one, else spot. Perp costs from costs.py at 2× (BTC ≈ 9–10 bp per side, ETH ≈ 21–25), funding, contract ≥ $150. Notional 1.0 × capital split equally over the variant's assets, whole contracts, P&L on the Friday.

## Trials (12, all in the ledger; $50K sleeve at 2×)
| variant | events | DEV alpha t | DEV sleeve 2× | 1× |
|---|---|---|---|---|
| with / all / BTC | 33 | −4.79 | −7.77% | −4.75% |
| with / all / BTC+ETH | 46 | −5.81 | −9.89% | −4.86% |
| **with / mq / BTC** | 8 | **−4.02** | −0.77% | −0.03% |
| with / mq / BTC+ETH | 11 | −4.66 | −1.86% | −0.63% |
| fade / all / BTC | 33 | −4.98 | −8.36% | −5.31% |
| fade / all / BTC+ETH | 46 | −5.82 | −9.67% | −4.62% |
| fade / mq / BTC | 8 | −4.78 | −0.20% | +0.55% |
| fade / mq / BTC+ETH | 11 | −6.42 | −1.11% | +0.13% |
| wfade / all / BTC | 20 | −4.76 | −5.85% | −4.00% |
| wfade / all / BTC+ETH | 24 | −4.28 | −4.98% | −2.73% |
| wfade / mq / BTC | 8 | −4.89 | −1.95% | −1.21% |
| wfade / mq / BTC+ETH | 8 | −4.55 | −0.56% | +0.11% |

All 12 met the minimum events. Every alpha t is dominated by the T-bill charge: the gates take excess returns on the full sleeve capital every calendar day, and this sleeve is idle on 98–99% of days. For the frozen variant the raw DEV sleeve mean has t = −0.55; its alpha t is −4.02.

## Frozen variant (freeze commit 31278d2)
with / mq / BTC: on the last Friday of each month, if |F| ≥ 20.43, enter sign(F) at 07:30 and exit at 08:00, BTC only. DEV: 8 trades, gross +9.1 bp per trade (5 of 8 winners), net −9.7 bp at 2×.

## HOLD (read once; a = 0.9 picked on DEV by book Sharpe)
| gate (2×) | result | |
|---|---|---|
| B1 HOLD book Sharpe gain ≥ +0.5 | −0.038 (chk −0.108, early −0.009) | FAIL |
| B2 HOLD alpha t ≥ 2 | −10.17 | FAIL |
| B3 every gated era positive | both negative | FAIL (h2gates) |
| B4 no losing book year | 2022 +9.9%, 2023 +11.1%, 2025 +22.9%, 2026 +13.4% | PASS (the incumbent's years) |
- Prereg reading of B3: no HOLD era reaches 10 events (early 3, chk 4), so none is gated. The pass is false either way.
- 1×: gain −0.031, alpha t −11.6. Deflated Sharpe of the book 0.82 (N = 4,598).
- The trades tell it plainly. Seven HOLD trades, gross mean −4.3 bp (early, 1 of 3 winners) and −15.5 bp (chk, 2 of 4), net −33 / −35 bp at 2×. The $50K sleeve made −2.38% over HOLD at 2× (−1.56% at 1×). By year: 2022 0 (no event fired), 2023 −0.99%, 2025 +0.06%, 2026 −2.22%. The DEV gross edge (+9.1 bp) was below 2× costs (19.5 bp round trip) and did not repeat on HOLD.
- Structural hurdle: at about 3.9 events a year, each event must net about 95 bp of notional just to cover the T-bill charge (3.7% a year), plus 19.5 bp of costs. That is a ~115 bp gross move in 30 minutes, about 3.3σ (σ₃₀ₘ ≈ 35 bp). B2 was out of reach for an event this rare, whatever the signal.

## Fill realism and capacity
- Prints (scripts/hunt2/exp/verify_fills.py; 30 orders of the frozen variant, DEV and HOLD): the first Coinbase print ≥ 2 s after the order on the venue it was priced on is 0.45 bp worse than the candle open on average (median 0.0), before the cost model's 1.5× half-spread, so the candle prices are fair. The CFM perp is thin at these times: median 4.5 s to the first print, up to 56 s, and two exits had no print within 30 s.
- Capacity: a $50K order (median 0.62 BTC) is about half the median CFM 1-minute volume at 07:30/08:00 (1.2 BTC; minimum 0.2). The book (~$2.5M bid within 5 bp, reports/cfm_book_summary.csv) absorbs it, but $125K would exceed a typical minute's prints. Contracts stay ≥ $150 throughout.
- Correlation with the incumbent: DEV 0.005, HOLD −0.04. The sleeve has no P&L on the incumbent's 10 worst DEV days.

## Weaknesses
- Few events: 8 DEV and 7 HOLD for the frozen variant. Normalising F by Coinbase spot volume made the DEV threshold era-dependent (higher coin volume in 2022–23 gave only 3 early events).
- The inventory proxy assumes every taker is a customer and every maker a dealer (block trades, RFQs, market maker vs market maker). Delta is plain Black–Scholes (no inverse-option premium adjustment). Dealers hedge mostly on Deribit, Binance and CME, so Coinbase sees part of the unwind at most.
- Events before Jul 2025 are spot-priced (perp basis ignored). Deribit data is read-only from the US.

## Deviations and shared-code notes
- The pre-freeze derive run's artifact upload failed: hunt2.yml passes the space-separated `artifact` input to upload-artifact@v4 as one path. HOLD files were regenerated after both freezes by re-running the unchanged derive code (bebe87d) on the same raw artifacts. The DEV outputs reproduced byte-for-byte (sha256 checked).
- scripts/hunt2/prints.py cannot save a windows file that mixes spot and perp products (integer vs string trade_id in one parquet column). verify_fills.py calls it once per product type.
- B3 in h2gates counts every era with scored days; the prereg's 10-event rule is reported alongside.

## Verdict
FAIL. The predicted dealer unwind does not show up as a tradable 30-minute BTC move on Coinbase. HOLD gross returns were negative before costs, and at monthly frequency the sleeve could not clear the T-bill charge on its capital even with a real edge.
