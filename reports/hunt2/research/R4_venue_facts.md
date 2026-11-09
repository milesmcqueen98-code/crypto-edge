# R4: venue facts, Coinbase spot and CFM perps (research agent memo, Nov 8 2026)

Full memo delivered by the R4 research agent; key facts used by the pre-registration are summarised here with the
sources it cited (URLs as given by the agent; checked by it on Nov 8 2026).

## CFM perp costs
- Coinbase (CFM) commission: volume-based, maker "as low as 0.005%", launch coverage "from 0.02%" (taker), beta 0.05%.
  https://www-marketing.coinbase.com/derivatives-trading/us-derivatives ; CoinGape / ForkLog Jul 21–22 2025.
- Plus a flat **$0.15 per contract** "to cover exchange, NFA and clearing fees" (same page, footnote 3).
- Exchange fee $0.10 per side for nano and small perps (both Non-Professional and Professional; $0.07 market makers),
  CFTC filings Nov 26 2025 (eff. Dec 15 2025) and Aug 3 2026 (eff. Aug 17 2026); NFA $0.01 (IBKR pass-through table);
  clearing ≈ $0.04 (inferred).
- A bot is "Professional" under the Non-Professional definition; nano exchange fees are the same either way.
- $0.15 in bp per side at Nov 8 2026 prices: BTC 2.0, ETH 7.1, SOL 3.5, XRP 2.7, HYPE 2.0, LINK 2.9, AAVE 2.4,
  BNB 2.2, ZEC 1.2, NEAR 0.8, BCH 6.3, LTC 6.0, AVAX 18.9, PAXG 0.4, US500 0.5.
- Unverified: Coinbase's own commission by tier (estimate 2–3 bp taker, 0–1 bp maker at retail volume); whether the
  $0.15 is per side (assume yes).

## CFM products (public API, Nov 8 2026)
- Perps: BTC, ETH (Jul 21 2025); SOL, XRP (Aug 15 2025); BCH, LTC, AVAX, LINK, DOT, 1kSHIB, XLM, HBAR, ADA, SUI, DOGE
  (Dec 12–15 2025); ZEC, PAXG, AAVE, NEAR, ONDO, ENA, 1kPEPE (Feb 28 2026); BNB, HYPE (Jun 5 2026); AI10, China10,
  Defense10, Tech100 index perps (Jun 15 2026, equity hours); US500 (Aug 17 2026, equity hours).
- Crypto perps trade 24/7 except the Friday 5–6 pm ET maintenance and occasional weekend maintenance (up to ~9 h).
- Gold/silver dated futures 24/7 since May 4 2026; single-stock perps and gold/silver perps are not for US persons.

## CFM rules
- ±10% move from an hourly reference price → 2-minute halt (orders accepted, no matching).
- Fair Value Limit: orders more than ±5% from the spot mid are rejected.
- Funding: hourly premium (1-hour TWAP of (mark − spot)/spot / 24, sampled every 3 min), smoothed 0.75/0.25, no cap;
  settled at the mid-day and end-of-day margin runs (2:00 pm ET named as one).
- Intraday leverage (opt-in) weekdays 8 am–4 pm ET; liquidation at 0% buffer, orders cancelled first.

## Coinbase spot
- From Sep 16 2026 tiers start at $10K; entry 0.50% maker / 0.90% taker; VIP 8 0 / 2 bp; tier = best of spot volume,
  derivatives volume or USDC balance. Stable pairs 0% maker (USDT pairs excluded).
- Order types: limit GTC/GTD with post_only, market IOC/FOK, smart limit IOC, stop-limit, TWAP, scaled, brackets.
- Rate limits: 30/s private, 10/s public (SDK-sourced); WebSocket market_trades batched every 250 ms; level2 gives
  absolute sizes.

## ETFs and CME
- In-kind creations approved Jul 29 2025; generic listing standards Sep 17 2025; spot SOL/LTC/HBAR ETFs Oct 28 2025,
  XRP Nov 13 2025.
- Leveraged ETF AUM (latest found): BITX $989M (Nov 6 2026), BITU $462M, ETHU $852M (Oct 30 2026), ETHT $211M, SOLT
  $136M, XXRP $142M; BITX holds CME futures; XXRP swaps + CME. A 2x fund's daily rebalance = 2 × AUM × the day's
  return.
- CME 24/7 crypto futures and options from May 29 2026; CME SOL futures Mar 17 2025, XRP futures May 19 2025.

## Liquidity (Kaiko via press)
- ~47% of BTC volume trades in the US weekday session since the ETFs; the 3–4 pm ET benchmark window carried 6.6% of
  weekday volume (2024). Weekend share ~16%.
- Coinbase BTC ±1% depth ~$16–20M (Binance ~$30M). Oct 10 2025: books near mid emptied; depth impaired for 6+ months.

## Historical data
- Coinbase spot prints by trade-id cursor back to 2020; CFM perp prints by time window from launch.
- Tardis free first-of-month: Coinbase spot since 2019 (L2, trades, quotes); Coinbase Derivatives only since
  2026-10-14; Deribit options chain and DVOL.
- Deribit DVOL hourly via the public API (no open-interest history).
