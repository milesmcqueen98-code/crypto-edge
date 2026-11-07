# R3: Exchange docs and data plumbing (checked Nov 6, 2026)

**Scope:**
- Coinbase Advanced Trade, Coinbase Exchange, and Coinbase Derivatives (CDE) retail perps through Coinbase Financial
  Markets (CFM).
- Free research data.
- Docs research only. Several help.coinbase.com pages could not be reached, and the web-search budget ran out (see §3).

**Last column of the table:**
- **D**: verified in the cited doc or filing this session.
- **P**: verified from repo probes or data (reports/hunt/probe2.json, data/cfm/, reports/cfm_products.json, Nov 6–7).
- **I**: inferred.
- **U**: unverified (third-party only, or the source was unreachable).

## 0. Builders: read first
1. **Perp all-in fee: UNVERIFIED.**
   - Exchange fee is about $0.10 per contract per side for non-professional electronic trades. Source: the CFTC fee
     schedule; the column mapping is uncertain.
   - No reachable official page gives Coinbase's FCM charge or the NFA fee.
   - Keep the repo's $0.20 per contract per side as the base case, and run sensitivities at $0.12 and $0.30.
   - Definitive check: one authenticated order preview (`POST /api/v3/brokerage/orders/preview`) for 1 BIP contract,
     maker and taker. Its commission field should give the all-in fee (I).
2. **Hours for 24x7 crypto perps:**
   - Trading is continuous except Friday 5:00–6:00 PM ET, plus a quarterly weekend maintenance of about 3–4 h that is
     announced ahead.
   - There is no daily halt.
   - The help page's "daily 5–6 PM ET break, Saturday closed" describes 23x5 products. The 5 index perps are not 24x7.
3. **Margin cutoff:**
   - Intraday margin is opt-in and runs weekdays 8 AM–4 PM ET. Positions held past 4 PM ET need overnight margin.
   - Nov 6 rates:

     | Product | Intraday | Overnight long | Overnight short |
     |---|---|---|---|
     | BIP | 10% | 21.0% | 25.7% |
     | ETP | 10% | 24.1% | 30.4% |
     | SLP, XPP | 20% | ~37% | ~56% |
     | DOP | 25% | 52% | 92% |

   - CDE's daily settlement price is the VWAP of the 60 seconds to 4:00 PM ET, the same minute.
4. **Perp order types:**
   - Limit GTC and GTD both accept `post_only`. GTD needs `end_time`.
   - The documented request has no `reduce_only` or self-trade-prevention field.
   - The exchange rejects orders priced more than ±5% from spot fair value.
5. **Spot stable pairs:**
   - 0% maker; 0.10–0.45 bp taker, by liquidity-program tier.
   - USDT-USD and USDT-USDC pay standard fees.
   - Source is third-party (Aug 2026); the official fee page needs a sign-in (U).

## 1. Fact table

### Coinbase Advanced Trade: public market data (spot and CDE perps)
| Item | Answer | Source | V/I |
|---|---|---|---|
| Public market trades | `GET api.coinbase.com/api/v3/brokerage/market/products/{id}/ticker`. `limit` is required; `start` and `end` are UNIX seconds. No auth. Returns trade_id, price, size, time, `side` (maker side), best bid/ask. | [docs](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-market-trades) | D |
| Trades: depth and cap | Docs give neither. Windowed calls return CDE perp prints back to launch: BIP and ETP from Aug 2025, SLP from Sep 2025, DOP and SUP from Dec 2025. `limit=1000` returned 1,000, so page by narrowing windows; more than 1,000 per call is untested. | probe2.json | P |
| Side convention | `side` is the maker side. In an ETP sample, BUY prints were mostly down-ticks (162 vs 30) and SELL prints mostly up-ticks (202 vs 84). So BUY means a resting bid was hit by a seller. | [asyncapi](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/advanced-trade-asyncapi.json), probe2 | D+P |
| Public candles | `GET .../market/products/{id}/candles`. `start`, `end` and `granularity` are required: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d. Maximum and default 350 per call. Depth not stated; the repo has perp 1m candles from launch (BTC 2025-07-18, DOGE 2025-12-12). | [docs](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-candles), data/cfm | D+P |
| Caching | Public responses are cached for 1 s. | [REST overview](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/rest-api) | D |
| Public REST rate limit | About 10 req/s per IP; private about 30/s. From a third-party crate citing Coinbase docs; the official page was unreachable. | [crate](https://docs.rs/crate/coinbase-advanced/latest/source/src/rate_limit.rs) | U |
| WebSocket | `wss://advanced-trade-ws.coinbase.com`, no auth.<br>Channels:<br>- `level2`: snapshot plus updates, absolute size per level<br>- `market_trades`: batched every 250 ms<br>- `ticker`, `candles` (5-min), `status`, `heartbeats`<br>Covers "spot crypto and US futures". Limits: 8 connections/s and 8 unauthenticated messages/s per IP. Channels close after 60–90 s idle without heartbeats. | [channels](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-channels), [limits](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-rate-limits) | D (perps covered: I) |
| Perp metadata | List Public Products with `product_type=FUTURE` gives:<br>- funding rate, time and interval<br>- open interest<br>- intraday and overnight margin rates<br>- 24x7 flag and session times<br>- status flags (`cancel_only`, `limit_only`, `post_only`, `auction_mode`)<br>- `new_at` | [docs](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/list-public-products) | D |

### Coinbase Exchange API (spot)
| Item | Answer | Source | V/I |
|---|---|---|---|
| Trades pagination | `GET api.exchange.coinbase.com/products/{id}/trades`. Trade-id cursor: `after` gives older trades, `before` newer, via the CB-AFTER and CB-BEFORE headers. `limit` default and maximum are 1,000. Depth is not stated; full history by walking CB-AFTER is likely. | [pagination](https://docs.cdp.coinbase.com/exchange/rest-api/pagination), [trades](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades) | D (depth I) |
| Candles | Granularity 60, 300, 900, 3600, 21600 or 86400 s. The doc caps a call at 300, but the probe got 350 daily candles in one call. No candle is published for an interval with no trades. | [docs](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles), probe2 | D+P |
| Rate limit | Public 10 req/s per IP, burst 15; 429 when exceeded. | [docs](https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits) | D |
| Delisted products | `/products` lists 91 delisted USD pairs, and their candles are still served. Delisted trades are untested. | probe2 | P (trades U) |
| Self-trade prevention | Exchange default is decrement-and-cancel; options are co, cn and cb. Advanced Trade orders have no STP field. | [matching engine](https://docs.cdp.coinbase.com/exchange/concepts/matching-engine) | D (Advanced: I) |

### Coinbase Derivatives / CFM retail perps
| Item | Answer | Source | V/I |
|---|---|---|---|
| Specs | Contract sizes and ticks:<br>- BIP 0.01 BTC, tick $5 ($0.05 per contract)<br>- ETP 0.1 ETH, tick $0.50<br>- SLP 5 SOL<br>- XPP 500 XRP<br>- DOP 5,000 DOGE<br>29 perp products: 24 are 24x7; the 5 index perps (US5, TEK, AIP, DEF, CHN) are not. Cash-settled, cleared by Nodal Clear.<br>IDs keep "20DEC30", but the API expiry reads 2089-12-30 after expiries were removed under CFTC no-action letters 26-19 and 26-29. | [CFTC BIP cert](https://www.cftc.gov/sites/default/files/filings/ptc/25/06/ptc06262524818.pdf), cfm_products.csv, [filing 2026-67](https://www.cftc.gov/filings/orgrules/rules10192634774.pdf) | D+P |
| Hours (24x7) | Weekly maintenance Friday 5:00–6:00 PM ET (4–5 PM CT): pre-open from 5:50, no cancels from 5:59:30, open at 6:00. Moves to Thursday if Friday is a holiday. Quarterly weekend maintenance of about 3–4 h, announced ahead. Trade date rolls at 5 PM ET, Mon–Fri. | [market hours](https://docs.cdp.coinbase.com/derivatives/introduction/market-hours), [24/7 page](https://coinbase.com/learn/futures/24-7-trading) | D |
| Hours seen in data | 1m perp candles, Aug–Nov 2026:<br>- Zero minutes on Friday 5–6 PM ET; Saturday trades.<br>- Mon–Thu 5–6 PM ET trades but thins: BTC has prints in ~85% of minutes (vs ~97% at 3 PM), DOGE ~18% (vs ~37%). | data/cfm/*.parquet | P |
| Funding formula | Hourly, set by the clearing house:<br>- premium = mean of twenty 3-min samples of (futures mark − spot mark) / spot mark, divided by 24<br>- rate = 0.75 × premium + 0.25 × previous rate<br>- payment = −rate × qty × multiplier × mark<br>No cap is stated. | [CFTC BIP cert](https://www.cftc.gov/sites/default/files/filings/ptc/25/06/ptc06262524818.pdf) | D |
| Funding timing | Accrues each UTC hour (interval 3600 s). Settled twice daily at the mid-day and end-of-day margin runs; their ET times are not published. | same, [Perps 101](https://www-marketing.coinbase.com/learn/futures/us-perpetual-style-futures-101), cfm_products.json | D (times U) |
| Daily settlement | 3:00 PM CT (4:00 PM ET): VWAP of trades in the prior 60 s, with fallbacks. | CFTC BIP cert | D |
| Price controls | A ±10% move from the hourly reference price triggers a 2-min halt (orders accepted, no matching). Fair Value Limit: orders outside ±5% of spot mid are rejected. | CFTC BIP cert, CDE instruments API | D |
| Position limits | Exchange: BIP 6.5M contracts, reportable at 25. CFM retail: tiered by income and net worth, per instrument, open orders included. | CFTC BIP cert, [futures intro](https://help.coinbase.com/coinbase/trading-and-funding/derivatives/futures-intro) | D |
| Exchange fee | Per side per contract, by class: market maker, non-professional or professional; electronic or block. The BIT/BIP/ET/ETP row extracts as $0.07/$0.05/$0.01 and $0.10/$0.05/$0.01. Best read: retail electronic $0.10, market maker $0.07. Effective Aug 17, 2026. | [CFTC #2026-46](https://www.cftc.gov/filings/orgrules/rules08032613651.pdf) | D (mapping I) |
| All-in retail fee | **Unverified.** The fee help pages were unreachable. Marketing says "from 0.02%"; an old API guide says futures use the Advanced fee table. Repo model: $0.20 per contract per side. | [futures guide](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/futures) | U |
| Margin windows | Intraday margin is opt-in, weekdays 8 AM–4 PM ET, excluding holidays. Past 4 PM ET the overnight requirement applies; CFM can disable intraday margin without notice. `GET /api/v3/brokerage/cfm/intraday/current_margin_window` (auth) returns INTRADAY, OVERNIGHT, WEEKEND or TRANSITION, with an end time. | [futures intro](https://help.coinbase.com/coinbase/trading-and-funding/derivatives/futures-intro), [margin window](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/futures/get-current-margin-window.md), [setting](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/futures/set-intraday-margin-settings.md) | D (WEEKEND and TRANSITION start times U) |
| Margin rates | See §0 (Nov 6 snapshot). Index perps: US5 5% intraday, 6.4–6.9% overnight. | cfm_products.json | P |
| Liquidation | Buffer = (available − threshold) / (initial − threshold); warnings at 100% and 20%.<br>At 0%: open spot and futures orders are cancelled, then CFM futures are liquidated, then spot crypto may be sold. Execution method is not disclosed. Cash sweeps automatically from spot to CFM to meet margin. | [buffer](https://help.coinbase.com/en/coinbase/trading-and-funding/derivatives/futures-liquidation-buffer), futures guide | D |
| API order types | Limit GTC and GTD (`post_only` on both; GTD needs `end_time` in RFC3339). Also limit FOK, IOC, market IOC, market FOK (perps only), stop-limit, bracket, attached TP/SL, TWAP and scaled. `leverage` and `margin_type` fields. No `reduce_only` or STP field; only REDUCE_ONLY_* and FUTURES_AFTER_HOUR_INVALID_ORDER_TYPE error codes exist. | [create order](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/create-order), [orders guide](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/orders) | D |

### Coinbase spot
| Item | Answer | Source | V/I |
|---|---|---|---|
| US Advanced fee tiers | Mechanics: tiers are recomputed hourly on trailing 30-day volume, and the tier at order time applies. The official table needs a sign-in. Repo table (Nov 6, after the Sep 16 change), maker/taker %:<br>- Intro 0.50/0.90<br>- $10K 0.35/0.75<br>- $50K 0.15/0.30<br>- $250K 0.10/0.15<br>- VIP1 $500K 0.06/0.125<br>- VIP8 0/0.02<br>A third-party Aug 2026 table differs (0.40/0.60 at the bottom tier). | [help](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/advanced-trade-fees), crypto-edge-findings.md, [datawallet](https://www.datawallet.com/crypto/coinbase-fees) | D (mechanics), U (numbers) |
| Stable pairs | Fees as in §0. Stable volume doesn't count toward tiers. API: `fx_stablecoin` flag; `high_bid_limit_percentage` caps limit-buy prices. | datawallet, [products](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-all-known-trading-pairs) | U (fees), D (flags) |
| Market statuses | Full, limit-only (no market orders), post-only (maker only, no matching), cancel-only, trading-disabled and view-only. API flags (at most one true), plus status online/offline/internal/delisted and `auction_mode`. | [help](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/market-availability), products API | D |
| New listings | Each book moves independently through: transfer-only, then auction (at least 10 min; limit only, post-only rejected; crossing orders match at the indicative open), then limit-only, then full trading. A thin book can go cancel-only instead. Phases are timestamped on status.exchange.coinbase.com. Example, BARD: auction 15:06 PDT Sep 18 2025, limit-only 15:17, full trading next day 10:50. | [listings](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/new-asset-listings), [auction](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/auction-mode), [BARD](https://status.exchange.coinbase.com/incidents/dkqym3wm9d4n) | D |
| Listing times | `new_at` is set on all 409 USD pairs. Pre-2023 listings carry a placeholder of 2023-01-01. | probe2 | P |

### Free research data
| Item | Answer | Source | V/I |
|---|---|---|---|
| data.binance.vision | Spot, USD-M and COIN-M: aggTrades, trades, klines (1s–1mo), daily and monthly. Futures also have bookTicker, bookDepth (±1–5% depth; at least 2023-01 to 2025-10), metrics (OI and long/short ratios), premium/mark/index klines and fundingRate.<br>Coverage ends:<br>- liquidationSnapshot, USD-M: 2024-03-31<br>- liquidationSnapshot, COIN-M: continues (at least 2024-10)<br>- USD-M bookTicker: about 2024-03<br>Reachable from runners. | [repo](https://github.com/binance/binance-public-data), [issue 337](https://github.com/binance/binance-public-data/issues/337), [nekojiru](https://pypi.org/project/nekojiru-binance/), probe2 | D/P/U |
| Tardis free | The first day of each month is free without a key, at `datasets.tardis.dev/v1/{ex}/{type}/{Y}/{M}/{D}/{SYM}.csv.gz`. Data types: trades, incremental L2, book snapshots (5/25), quotes, book ticker, derivative ticker, liquidations.<br>Coverage:<br>- Coinbase: from 2019-03-30<br>- Binance futures: from 2019-11-17; liquidations from 2020-01-07, but only the latest per symbol per second<br>- Hyperliquid: from 2024-10-29; trades carry buyer and seller from 2024-12<br>- Coinbase International: 2024-10-31 to 2026-10-01<br>- Coinbase Derivatives: from 2026-10-14, with no liquidations type; first free day 2026-11-01 (Feb 2026 returned 400)<br>Coinbase-derived data can't be redistributed, even aggregated. | [overview](https://docs.tardis.dev/downloadable-csv-files/overview), [coinbase](https://docs.tardis.dev/historical-data-details/coinbase), [binance-futures](https://docs.tardis.dev/historical-data-details/binance-futures), [hyperliquid](https://docs.tardis.dev/historical-data-details/hyperliquid), [FAQ](https://docs.tardis.dev/faq/general), probe2 | D+P |
| Hyperliquid info API | Limits:<br>- candleSnapshot: only the latest 5,000 candles (1m is about 3.5 days)<br>- userFills: at most 2,000<br>- userFillsByTime: 2,000 per call, latest 10,000 only<br>- fundingHistory: by time range (third party: about 500 per call)<br>- weight: about 1,200/min per IP (third party)<br>Liquidations are flagged only in user fills (`liquidation`: liquidated user, mark price, method) and userEvents. Public trades carry [buyer, seller] but no flag. | [info](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint.md), [subscriptions](https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/websocket/subscriptions) | D (third-party items U) |
| Hyperliquid S3 | Buckets:<br>- `hyperliquid-archive`: hourly L2 snapshots and daily asset contexts<br>- `hl-mainnet-node-data`: node_fills_by_block, node_fills (API format) and misc events<br>**Requester pays**, so an AWS account is needed. Uploaded about monthly; gaps possible. Node fills likely carry the liquidation object. | [historical data](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data.md) | D (liquidation object I) |
| CoinDesk / CryptoCompare | A key is now required (probe: 401). The free plan has a lifetime call cap (about 250K) and reportedly about 1 h of minute history, so it is not usable. Delisted-coin coverage is unverified. | probe2, [CoinGecko](https://www.coingecko.com/learn/coindesk-api-alternatives), [apis.io](https://apis.io/plans/cryptocompare/cryptocompare-plans-pricing/) | P/U |
| Coinalyze | Free but needs a sign-up key; 40 calls/min. Liquidation, OI and funding history at 1 min to daily.<br>Intraday intervals keep only 1,500–2,000 points: 1m is about 1–1.4 days, 1h about 2–3 months. Daily data is kept for good. Exchange list via `/exchanges`. | [docs](https://api.coinalyze.net/v1/doc) | D |
| CoinGlass | No free API. Hobbyist $29/mo (30 req/min, 4h+ intervals). 1-min data needs Standard ($299/mo), with about 6 days of depth. | [review, May 2026](https://dev.to/great-time-flies/coinglass-api-review-2026-is-it-worth-it-for-crypto-quant-traders-2bcf) | U |
| Free CDE history | Trades: the Advanced public trades endpoint and 1m candles since launch (the only free full history found). Book: none before 2026-10-14; Tardis from then, free on the 1st of each month.<br>CDE's own APIs (FIX, SBE, UDP multicast, REST) serve members, and the changelog lists no public history product. | probe2, [CDE intro](https://docs.cdp.coinbase.com/derivatives/introduction/welcome.md), [changelog](https://docs.cdp.coinbase.com/derivatives/changes/changelog.md) | P/D/I |
| Global Derivatives (Deribit stack) | `public/get_last_trades_by_instrument` on drb.coinbase.com is public. Up to 1,000 per call, by time or sequence range. The trade field `liquidation` = M, T or MT gives a free liquidation-flagged tape for BTC-PERPETUAL etc. (offshore, not CDE). History depth is undocumented. | [docs](https://docs.cdp.coinbase.com/api-reference/market-data/public-get_last_trades_by_instrument.md) | D (depth U) |

## 2. What this enables or blocks

**(i) Fillability of perp-only wicks: ENABLED with a conservative fill rule.**
- *Method:*
  - Pull every CDE print in a ±10-minute window around each candidate wick. That is a few calls per event at 8 req/s.
  - Count our bid at P as filled only if prints trade strictly below P, or if seller-initiated volume at or below P
    exceeds an assumed queue ahead. (Seller-initiated prints are `side=BUY`.)
- *Blocked:*
  - The real queue ahead of us. No free CDE book history exists before 2026-10-14. Calibrate queue depth from Tardis
    free days (2026-11-01 onward, one per month) and the paper bot's "dollars ahead" log.
- *Rules the simulator must encode:*
  - Bids more than 5% below spot fair value are rejected at entry (Fair Value Limit). This also caps how deep a perp-only
    wick can print.
  - ±10% moves trigger 2-minute halts.
  - No fills Friday 5–6 PM ET.

**(ii) Historical liquidation-flow signal: largely BLOCKED for the CDE era (Jul 2025 on).**
- CDE prints carry no liquidation flag; CFM liquidations probably look like ordinary orders (I).
- Binance USD-M liquidation snapshots stop at 2024-03-31. They are good for studying the cascade mechanism in
  2020–2024 on Binance prices.
- Tardis liquidations are free only 12 days a year and throttled to one per second per symbol.
- Coinalyze minute data is about 1 day deep, and CoinGlass is paid.
- Options, cheapest first:
  - (a) Test the depth of the Deribit-stack liquidation-flagged tape: one call.
  - (b) Hyperliquid node_fills from requester-pays S3 (AWS account and egress cost).
  - (c) A free proxy: Binance metrics, 5-minute open-interest drops together with price drops.
  - (d) Start forward collection now: a daily Coinalyze 1-minute pull per symbol (needs a free key) and a Hyperliquid WS
    logger.

**(iii) New-listings study: ENABLED and survivorship-free.**
- *Inputs:*
  - `new_at` for 2023+ listings.
  - Delisted pairs still listed, with their candles served.
  - Exchange trades paginate by trade id. Verify the first-trade depth on one 2023 listing.
  - Phase timestamps scraped from status.exchange.coinbase.com incidents.
- *Mechanics:*
  - No market orders are accepted in auction or limit-only, so the first market-order dump comes at full trading.
  - The open prints at the auction's indicative price.
- *Blocked:*
  - Book depth around listings.
  - Exact pre-2023 listing times: infer from the first trade.

**(iv) Schedule-driven forced flows: ENABLED, testable on prints and candles since Jul 2025** (about 330 weekdays and
about 68 Fridays).
- *Clocks to test:*
  - **4:00 PM ET weekdays.** Intraday margin ends; the overnight requirement is 2.1–2.6× higher (BTC/ETH) and up to
    3.7× (DOGE shorts). The settlement VWAP falls in the same minute. Test 3:45–4:15 PM ET flow and wick rates against
    other hours.
  - **5:00 PM ET, Mon–Thu.** The trade date rolls and books thin.
  - **Friday 5:00–6:00 PM ET.** The weekly halt: pre-open at 5:50, no cancels from 5:59:30, reopen at 6:00. The WEEKEND
    margin window also applies.
  - **Hourly funding** on the UTC hour.
  - **2-minute price-limit halts.**
- *Blocked:*
  - Start times of the TRANSITION and WEEKEND windows.
  - Whether CFM liquidates at 4:00 PM sharp.
  - Capture both live: log the public margin rates from List Products each minute (no key), and poll
    `current_margin_window` (auth).
- *Caveat:* intraday margin is opt-in and CFM can switch it off without notice, so the effect may be small or unstable.

## 3. Sources not reachable (gaps)
- **help.coinbase.com:** US-derivatives hours; leverage and margin; perps fees; Prime US derivatives fees; contract
  specifications; Global Derivatives funding. All returned client errors.
- **Coinbase fee table page.**
- **Advanced Trade REST rate-limits page.**
- **api.tardis.dev exchange listing:** used probe2 instead.
- **Web search budget exhausted:** Deribit-stack history depth and the official CFM fee page remain open. Both can be
  settled with one probe call and one authenticated order preview.
