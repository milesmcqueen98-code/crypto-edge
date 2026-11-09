# LETF: leveraged-ETF rebalancing flow into the US close (Path B)

**Verdict: FAIL.** All 12 DEV trials had a negative alpha t (−8.19 to −1.26). The frozen variant (reversal after 16:00, k = 2, four coins) lost on HOLD: book gain −0.40, sleeve alpha t −2.62. B1–B3 fail; B4 passes.

## Mechanism
2x and −2x crypto ETFs must trade AUM × L(L−1) × r in the direction of the day's return into their 4 pm ET NAV (CME settles 15:59–16:00). A fast follower would be paid by the impact (momentum into the close); a liquidity provider after 16:00 would be paid by the part that reverts.

## Data
- **Candles:** Coinbase spot 1-minute candles drive every signal, and fills before the perps existed. CFM perp 1-minute candles are used for fills from 2025-07-21 (BTC, ETH) and 2025-08-18 (SOL, XRP).
- **ETF volume:** Yahoo close × volume for the SPEC's 13 tickers. NYSE days and early closes come from pandas_market_calendars.
- **DEV:** 311 NYSE days (3 early closes), 455 scored calendar days. The gate was open every day for BTC and ETH, 51% of days for SOL and 32% for XRP.
- **chk:** 152 NYSE days, 219 scored days. SOL's gate was open on 3% of days; XRP's never opened.
- **Early:** 501 NYSE days, none gated (the BTC complex's 20-day mean peaked at $24.9M in 2023), so the era is not scored.

## Definitions fixed before any trial (letf.py docstring, commit b5b0172)
- **Prices:** P(x) is the close of the candle labelled x. Every time is anchored on the NYSE close, so early closes shift the whole schedule.
- **Volatility:** σ is the standard deviation of the last 30 NYSE-day close-to-close log returns, ending at the previous close.
- **Gate:** the complex's 20-NYSE-day mean dollar volume to d−1 must be at least $50M.
- **Sizing:** the contract count and the $150 contract rule both use P(15:44).
- **Taker fills:** the next minute's open. An entry needs a candle within 5 minutes, or there is no trade. An exit takes the first candle within 30 minutes, or else the last close before it; in practice that is CFM's Friday 17:00–18:00 ET maintenance.
- **Maker orders:** placed 10 bp beyond the fill venue's 15:54 close, on the perp tick. They fill only on a tick through the level, at θ × the volume beyond it, and a post-only order that would cross is rejected.
- **Trades:** asset-days filled on the $50K sleeve at 2×.

## DEV trials (12; sleeve $50K at 2×, alpha t on the incumbent at $200K)
| Variant | Trades | Alpha t | Gross bp | Net 2× | Net 1× |
|---|---|---|---|---|---|
| mom k1 BTC | 103 | −8.19 | +2.0 | −16.4 | −7.2 |
| mom k2 BTC | 16† | −7.47 | +5.0 | −13.7 | −4.3 |
| mom k1 all | 282 | −7.43 | +3.4 | −24.7 | −10.7 |
| mom k2 all | 41 | −3.52 | +13.3 | −17.2 | −1.9 |
| rev k1 BTC | 103 | −2.70 | +5.7 | −12.9 | −3.6 |
| rev k2 BTC | 16† | −2.70 | −0.7 | −19.6 | −10.2 |
| rev k1 all | 282 | −2.52 | +1.6 | −26.7 | −12.6 |
| **rev k2 all** | **41** | **−1.26** | −10.9 | −41.6 | −26.2 |
| mkr k1 BTC | 59 | −5.05 | −0.2 | −14.7 | −7.4 |
| mkr k2 BTC | 12† | −4.66 | −6.1 | −21.4 | −13.8 |
| mkr k1 all | 169 | −6.33 | −1.3 | −20.7 | −11.0 |
| mkr k2 all | 28† | −5.12 | +3.4 | −19.2 | −7.9 |

† Fewer than 40 trades, so ineligible. The maker leg with k = 1 on all four coins filled 169 of its 282 signals (110 unfilled, 3 post-only rejections); the taker legs filled every signal.

- **Costs:** a taker side costs about 9 bp on BTC at 2×, 21 bp on ETH, 13 on SOL and 10 on XRP. The best gross edge (momentum, k = 2, four coins: +13 bp) is smaller than one round trip.
- **The maker leg cannot win at 2×.** Its take-profit at the 15:54 close caps the gross near 10 bp, below a maker round trip (14 bp on BTC, 28 bp on ETH). None of its trades made money at 2×.

## Frozen variant
**rev_k2_all** (freeze commit 94ac933).
- **Rule:** when |r(15:44)| ≥ 2σ, take the side against the day's move in the BTC, ETH, SOL and XRP perps at 16:01 ET, and exit at 17:00 ET. The capital is split equally among the coins that signal.
- **Why it was chosen:** it had the highest DEV alpha t among the eight eligible variants. With every t negative, the least active eligible variant wins. The runner-up was rev_k1_all (t −2.52).

## HOLD (read once) and gates
At 2× costs, with 1× in brackets. a = 0.9 was chosen on DEV; 674 scored days (sel and chk).

| Gate | Value | Result |
|---|---|---|
| B1: HOLD book gain ≥ +0.5 | −0.40 (−0.32) | FAIL |
| B2: HOLD alpha t ≥ 2 | −2.62 (−2.40) | FAIL |
| B3: gain > 0 in every gated era | chk −0.40 | FAIL |
| B4: no losing book year | 2025 +22.2%, 2026 +12.3% | PASS |

- **HOLD book:** Sharpe 2.26 against the incumbent's 2.66; the sleeve's own Sharpe was −3.17. Correlation with the incumbent was +0.14 on HOLD and −0.26 on DEV.
- **chk trades:** 23 (12 BTC, 11 ETH). Gross −22.9 bp, net −58.3 bp at 2× (−40.6 bp at 1×), 17% winners. One ETH trade on 2026-08-19 lost 554 bp gross.
- **Full window:** alpha t −3.03; deflated Sharpe 0.36 (N = 4,598).
- **Sleeve years** ($50K, 2×): 2025 −7.6%, 2026 −12.9%.
- **Early-era placebo** (gate off, descriptive only): 80 trades, gross −28.8 bp, net −70 bp. The sign was the same before the LETFs existed.

## Capacity and fill realism
- **Capacity:** the mean notional was $31K on DEV and $35K on chk, out of the $50K sleeve (whole contracts, split among the coins that signal). Taker fills are 100%; θ 0.25 does not apply.
- **DEV print check:** 82 legs and 160,467 Coinbase prints, fetched on Actions with scripts/hunt2/prints.py and derived with letf/prints_check.py.
  - Price: the first print on our side at least 2 s after the decision was a median +0.25 bp (perp) and −0.4/0.0 bp (spot entry/exit) away from the candle open. The model charges 1.5× the measured perp half-spread (1.0–3.4 bp) on top of that.
  - Size: walking through our-side prints until our size is filled costs +1.5 bp at entry and +3.3 bp at exit.
  - Delay: the median wait for the first print is 2–3 s, but 14 s at the 17:00 perp exit.
  - Gross per trade: −8.0 bp on prints against −10.9 bp on candles, so the candles are not biased against the idea.
- **Friday exits:** these fall in CFM's maintenance hour, so they use the last price before it (5 of 41 DEV trades, 6 of 23 chk trades).

## Weaknesses
- Fills use candles, checked against prints on DEV only. Decisions carry 1 minute of latency.
- From January to July 2025, before the perps launched, fills are spot prices charged at perp costs.
- The gate depends on Yahoo's volumes. The SOL and XRP complexes fell below $50M in chk, so HOLD is effectively BTC and ETH only.
- σ mixes 1-day and 3-day returns, so Monday's r is larger.
- The samples are small: 41 DEV trades and 23 HOLD trades.

## Deviations and shared code
- No change to the rule or the variant after the freeze.
- prints.py cannot write a shard that mixes spot and perp windows (trade_id types clash), so the windows were split by venue (commit 8a5752b).

## Verdict
**FAIL** on B1–B3. The rebalancing flow may exist, but its footprint on Coinbase after 15:44 is a few basis points at best, against round trips of 18–42 bp at 2×. The reversal after 16:00 had a negative gross on DEV, on HOLD and in the pre-LETF placebo.

**Scorecard inputs (suggested):**
- Realism 12/15: prints check 5, latency 3, capacity 1, fees 3.
- Mechanism 5/10.
- Implementability 10/10.
- Diversification 3/5: HOLD correlation 0.14 scores 3; the sleeve did not trade on the incumbent's 10 worst HOLD days.
- Capacity 5/5.

**Reproduce:** scripts/hunt2/letf/: dev.py sel, freeze.py, windows.py sel, prints_check.py (Actions), hold.py.
