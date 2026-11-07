# R1: Forced flows (liquidations, margin schedules, halts)

Research memo, written 2026-11-07 UTC. This is web research only: no backtests, and no return statistics were computed.

Tags:
- **[V]** checked in the cited source.
- **[V-repo]** checked in this repo's files. These are candle counts and figures from reports/crypto-edge-findings.md, not new tests.
- **[2nd]** second-hand: one source reporting another.
- **[I]** my inference.
- **[U]** not verified.

Source keys S1–S16 are listed in section (b).

## (a) Candidate ideas

| # | Idea | Who is forced or eager, and why | Why a small trader is paid | Evidence: effect size and source | Data to backtest | Spot / US perps | Capacity at $100K | Overlap with R2-08 | Red flags |
|---|---|---|---|---|---|---|---|---|---|
| F1 | **4 PM ET margin step-up** | CFM retail on intraday margin (up to 10x) must meet overnight margin (e.g. 10% → 20%) at 4:00 PM ET on weekdays; ramp from 3:30; a short account enters liquidation at once [V S1]. Others de-lever early [I]. Crowd side ≈ CFM premium/funding sign. | Clock-known, price-insensitive flow in books too small for funds: BTC perp OI ≈ $160M, alts $1–20M [V-repo] | Rule [V]; no effect size published | data/cfm 1-min (local, free): BTC/ETH since Jul 2025 (≈330 weekdays), alts since Dec 2025/Feb 2026; Coinbase trades for prints; placebo = holidays and weekends | Perps (spot if it spills over [I]) | ~$10–30K per event on BTC/ETH | Low | CFM may internalise (S2). Window start documented two ways. Calendar-style test: placebo essential. |
| F2 | **Friday halt reopen** | All CDE products halt Fri 5:00–5:50 PM ET. Pre-open runs from 5:50, cancels stop at 5:59:30, and trading resumes at 6:00 [V S4]. Spot keeps trading [V-repo]. At the open: accounts pushed under margin get liquidated, and stops and queued orders hit [I]. Hourly ±10% limit halts (2 min) work the same way [V S5]. | A one-sided open in a thin book. The perp must re-converge to spot (±5% fair-value band) [V S5]. | Oct 10 2025's peak liquidation minute (21:15 UTC = 5:15 PM EDT, a Friday) fell inside the halt [V, timing only]. No study found. | data/cfm plus spot minute candles (local); ~68 Fridays since Jul 2025; Coinbase trades for the opening prints. | Perps | Small, weekly | None. The quiet window (4:55–6:05 PM ET) blanks it. | Small N (maybe 5–10 big-move Fridays). Whether post-only orders are accepted in pre-open is undocumented [U]. |
| F3 | **Mon–Thu 5–6 PM ET thin hour** | 24x7 perps have no daily halt [V S4], but this hour is thin [V-repo]. BTC perp trades in ~50 of 60 minutes at 5–6 PM ET vs ~58 at 2–3 PM; SOL 32 vs 50. Stops and liquidations meet few makers [I]. | Being one of the few resting bids | The in-repo audit found futures-only wicks cluster at 5–6 PM ET: 13% of AI trades, 19% of P&L [V-repo]. | Local, free | Perps | Small | Same mechanism, different hours | Fillability is the open H1 question. The bot's "daily maintenance hour" premise is true only on Fridays. |
| F4 | **Hyperliquid liquidation label** | HL liquidates with market orders on its book. Positions over $100K go in 20% chunks, 30 s apart; then a backstop vault; then ADL [V S8]. Arbitrage carries the moves to Coinbase [I]. | Separates forced dips (which revert) from informed dips (which continue), giving a better R2-08 filter. | Forced selling is 88% done within 30 min of onset, and 63% is absorbed off-book [V S9]. Liquidation fills pay ~20x the voluntary half-spread and see ~10x larger adverse post-trade moves, i.e. short-run continuation, so bid deeper [V S10]. | HL S3 node_fills (2025-05-25 → 07-27) and node_fills_by_block (2025-07-27 →), which carry a liquidation object [V S7]. About $2–3 per month of data [2nd]. | Filter on both venues | n/a | High (a feature) | Live use needs our own non-validating node or a vendor stream; the prereg allows only HL's public info API [I]. HL is ~16% of global OI [V S8]. |
| F5 | **HL liquidation-cluster proximity** | Liquidation prices are deterministic and public [V S8]. Dense bands are queued forced orders. | Bid just beyond a band, or size up near one. | No quantified support. Hyperdash says bands don't predict direction; Glassnode's evidence is visual only; a vendor's claim has no statistics [V S8]. No scalar pre-cascade measure grades severity [V S9]. | Vendors expose only current snapshots. History must be rebuilt from fills plus state. ABCI state checkpoints start 2026-04-14, so ~7 months [2nd S7]. | Filter | n/a | High | Weak evidence, heavy build, short history |
| F6 | **Expiry settlement hour** | Dated futures settle to a Coinbase-built benchmark over 3–4 PM London on expiry Fridays (20 three-minute volume-weighted medians) [V S5 for BIP; other contracts U]. Basis traders and hedgers trade the average, a TWAP-like spot flow [I]. | LP to a scheduled flow, with relief after 4 PM London [I]. | None found for crypto. | Coinbase spot minute candles 2021–26 (local), ~60 monthly expiries. BIT Nov-26 OI ≈ $76M [V-repo]. | Spot + perps | Moderate on BTC/ETH | None | Calendar-like. Check whether the dead seasonality tests covered expiry hours. Hedgers roll early. Small N. |
| F7 | **Stop clusters at round numbers and prior lows** | Stop-sells cluster just past round numbers and prior lows. | Market-order overshoot past the cluster | FX (Osler 2003, from memory [U]): stops past round numbers accelerate moves, take-profits at them reverse. BTC: >10% of prices end in .00, but no return effect [V S14]. Round-cent clustering in a US crypto order book [V S14]. Stocks: 24.6 bp/day above vs below round numbers, t 32.5 [V S14]. No crypto stop-run effect size found. | Local spot minute candles, free | Spot (+perps) | As incumbent | High (a placement tweak) | The pattern family is dead, so run this as a ladder-placement variant inside the trial budget. |
| F8 | **CFM → spot spillover** | Short CFM accounts may have their spot crypto sold [V S3] | Forced alt spot sells | Mechanism only | None public | Spot | n/a | Full | Rationale only: also test F1 on spot |
| F9 | **Coinbase/Morpho loan liquidations** | On-chain liquidation at 86% LTV (BTC/ETH), 62.5% (XRP/DOGE/ADA/LTC) [V S15] | Selling at known prices | >$1.9B originated; impact unknown | Base events via Dune/RPC [U]; from Jan 2025 | Spot | Small | High | Hits DEX pools first |
| F10 | **Cross-venue cascade lead** | Offshore longs liquidate first (Oct 10: HL $10.3B, Bybit $4.6B, Binance $2.4B) [2nd S12] | Re-centre fair value on HL mark (allowed live input) in cascades | Kraken–Coinbase BTC gap ~9% at worst point, single source [V S12] | HL S3 l2Book (Sep 2023+) | Both | n/a | High | Speed race vs market makers |
| F11 | **Forced-flow-aware exit** | (as F4) | Exit once forced flow stops | 88% done within 30 min [V S9]; R2-08 markout peaks at 30–60 min [V-repo] | HL fills + local | Both | n/a | Full | Trial budget only |

## (b) Key facts with sources

### Coinbase US derivatives (CFM is the FCM; CDE is the exchange; Nodal Clear clears)

**S1 Margin schedule.** Source: [German mirror of the help article](https://help.coinbase.com/de/coinbase/derivatives/us-derivatives-leverage-margin). All English mirrors returned errors.
- Intraday margin is opt-in and lower than overnight margin.
- From 3:30 PM ET, rates rise gradually toward overnight levels. At-risk accounts get an email or SMS at 3:30.
- Overnight rates apply in full at 4:00 PM ET. If equity is short at that point, the account enters liquidation immediately.
- The page's worked example: 3:55 PM ET margin ratio 82%; 4:02 PM ET 106.8% (the requirement rose 18.7%) with no price move, which means liquidation.
- Overnight margin can be about twice intraday (10% → 20%).
- Weekends and holidays use overnight rates.
- Coinbase can switch intraday margin off without notice.
- Ratio of 100% or more is the liquidation zone.
- **Window start conflicts:**
  - The German page gives 6:00 PM ET → 4:00 PM ET the next day.
  - The [English intro](https://help.coinbase.com/coinbase/trading-and-funding/derivatives/futures-intro) and the [API docs](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/futures/set-intraday-margin-settings.md) give 8 AM–4 PM ET.
  - Every source agrees on the **4:00 PM ET end**.
- The API reports the current margin window: INTRADAY, OVERNIGHT, WEEKEND or TRANSITION, with an end time and kill-switch flags ([get-current-margin-window](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/futures/get-current-margin-window.md)). The bot can read the schedule live.

**S2 Who liquidates, and how** ([futures account agreement](https://www.coinbase.com/legal/futures-account-agreement)):
- "CFM generally will not issue margin calls to meet intraday or overnight margin deficiencies."
- CFM may liquidate without notice. It chooses which positions to close, in what sequence, when and how.
- It may use any market or dealer, including off-exchange, and CFM or its affiliates may take the other side.
- The order type is not disclosed [U].
- [I] Most likely these are market or IOC orders on the CDE book at a time CFM picks. Because internalisation is allowed, a public footprint isn't guaranteed. Test it by comparing aggressive-sell volume from 16:00:00 to 16:02 ET with the same minutes on placebo days.

**S3 Liquidation buffer** ([help page](https://help.coinbase.com/en/coinbase/trading-and-funding/derivatives/futures-liquidation-buffer)):
- Alerts go out at 100% and 20%. At 0%, Coinbase may liquidate.
- It first cancels the customer's open spot and futures orders, then closes some or all futures positions.
- If funds are still short, it may sell crypto in the customer's Coinbase spot account. Losses can exceed margin.

**S4 Hours** ([CDE market hours](https://docs.cdp.coinbase.com/derivatives/introduction/market-hours), [24/7 explainer](https://coinbase.com/learn/futures/24-7-trading)):
- 24x7 crypto futures trade from Friday 6 PM ET to Friday 5 PM ET with no daily break.
- **Every product halts Fri 5:00–5:50 PM ET.** Pre-open starts at 5:50, cancels are blocked from 5:59:30, and trading resumes at 6:00. The source gives these times in CT.
- There are quarterly 3–4 hour weekend maintenance windows, announced in advance.
- Products that are not 24x7 break daily 5–6 PM ET.
- Weekend trades carry Monday's trade date.
- Repo check [V-repo]: BTC perp has candles in ≈50 of 60 minutes at 5–6 PM ET Mon–Thu (≈58 at 2–3 PM) and ≈1.5 on Fridays (halt). Coinbase spot has 60 of 60 every day.

**S5 Perp rules** ([BIP CFTC self-certification, Jun 2025](https://www.cftc.gov/sites/default/files/filings/ptc/25/06/ptc06262524818.pdf); [Coinbase explainer](https://www-marketing.coinbase.com/learn/futures/us-perpetual-style-futures-101); [Oct 2026 filing](https://www.cftc.gov/filings/orgrules/rules10192634774.pdf)):
- **Funding:**
  - Computed hourly. The premium (perp mark minus spot, over spot) is sampled every 3 minutes, averaged over the hour, and divided by 24.
  - The rate is 0.75 × premium + 0.25 × the previous rate. No cap is stated.
  - Hourly amounts are aggregated at "mid-day" and "end-of-day" margin runs and settled in cash twice a day.
  - The clock times are not published [U]. The explainer's example uses a 2:00 PM ET period.
- **Daily settlement:** VWAP of the 60 seconds before 3:00 PM CT, i.e. 4:00 PM ET, the same moment as the margin step-up.
- **Fair-value limit:** orders more than 5% through the spot mid are rejected.
- **Hourly limit:** ±10% around an hourly reference price, then a 2-minute halt with no matching.
- **Final settlement:** the MarketVector Coinbase benchmark at 4 PM London.
- Alt perps are assumed to follow the same rules [U].
- [I] For H1: a perp-only wick can't trade more than ~5% below spot, so ladder rungs deeper than that are useless on perps.

**S6 Spot reopen** ([auction mode](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/auction-mode), [May 2026 outage reopen](https://www.theblock.co/post/400536/coinbase-resumes-trading-after-aws-linked-disruption)):
- Paused books go cancel-only, then into an auction of at least 10 minutes. Indicative prices are shown, and post-only orders are rejected.
- Crossed orders match at the uncross price, and both sides pay taker fees. Then full trading resumes.
- No study of returns after a reopen was found.

**Also:** CME crypto futures went 24/7 on May 29 2026, with a weekend maintenance window of at least 2 hours ([report](https://www.crowdfundinsider.com/?p=263656)).

### Liquidation data

**S7 Hyperliquid, official data** ([docs](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data)). The S3 buckets are requester-pays.
- `hyperliquid-archive`: L2 snapshots and daily asset contexts from about Sep 2023, uploaded roughly monthly, with gaps possible.
- `hl-mainnet-node-data`: fills, trades and events. Liquidation coverage by period ([Dwellir](https://www.dwellir.com/docs/hyperliquid/data-catalog/node-feeds/fills.md), consistent with [Allium](https://docs.allium.so/historical-data/supported-blockchains/hyperliquid/data-guide)):

  | File set | Period | Liquidation info |
  |---|---|---|
  | `node_fills_by_block` | 2025-07-27 → now | Liquidation object: liquidated user, mark price, market/backstop method |
  | `node_fills` | 2025-05-25 → 2025-07-27 | Same object |
  | `node_trades` | 2025-03-22 → 2025-05-25 | Only a LiquidatedMarket flag |

- Cost is ≈ $0.09/GB after 100 GB free; fills run ≈ 0.8–1 GiB/day [2nd, [Dwellir blog](https://www.dwellir.com/blog/hyperliquid-historical-data-for-backtesting)].
- The public API gives liquidations per address only, 10,000 fills per account and 5,000 candles per interval [2nd].

**S8 Hyperliquid third parties and mechanics**
- [HyperTracker](https://docs.coinmarketman.com/endpoints/liquidation-data):
  - Has historical liquidation fills, queried in windows of up to 3 months.
  - Its heatmap and risk endpoints show only the current state. Free tier: 100 requests/day.
- [Hyperdash](https://hyperdash.com/learn/how-to-read-a-liquidation-heatmap):
  - Builds levels from actual positions and has a historical view (retention unstated).
  - Says outright that bands don't predict direction.
- [Glassnode](https://research.glassnode.com/liquidation-heatmaps/): HL is ~16% of global OI. Clusters line up with liquidation spikes, but only visually; there is no test.
- [CoinMarketMan](https://coinmarketman.com/blog/hyperliquid-liquidations-explained--en/), mechanics: market close first; positions over $100K in 20% chunks with 30 s cooldowns; backstop vault if the book is thin.
- CoinMarketMan's [cascade post](https://coinmarketman.com/blog/when-one-liquidation-triggers-a-thousand-hyperliquids-cascade-effect--en/) claims cohort signals precede cascades, with no statistics.
- [I] No history of past liquidation *levels* is published. It would have to be rebuilt from fills plus account state.

**S16 Other liquidation data**

| Source | What you get free | History | Status |
|---|---|---|---|
| [Binance liquidationSnapshot](https://github.com/binance/binance-public-data/issues/337) | Daily files | USDT-M files stop 2024-03-31; COIN-M apparently continues. Start date unknown (S3 listing fetch blocked). | V / U |
| [Tardis](https://docs.tardis.dev/historical-data-details/binance-futures) | First-of-month CSVs need no API key ([policy](https://docs.tardis.dev/downloadable-csv-files/api)); unclear whether that includes liquidations | Binance forceOrder since 2020-01-07. Binance publishes only the latest liquidation per symbol per second. | V / U |
| [Coinalyze](https://api.coinalyze.net/v1/doc) | Free with API key, 40 calls/min, bars from 1 min to daily | Keeps 1,500–2,000 points per intraday interval (≈1 day of 1-min, ≈2–3 months of hourly); daily kept forever. A minute history needs a nightly collector started now. Exchange list not checked. | V |
| [CoinGlass](https://coinglass.com/pricing) | No free API | $29: bars of 4h and up. $299: 1-min for 6 days. $699: 1-min for 12 days. | V |
| [Coin Metrics](https://docs.coinmetrics.io/market-data/market-data-overview/liquidations/futures-liquidations) community API | Last 24 h only | Binance gap 2021-04-27 to 08-31; no Coinbase coverage | V |

[I] Coinbase publishes no CFM liquidation feed that I could find.

### Cascade evidence

**S9 Branching and timing** (Garcia Seuma, [2608.03616](https://ideas.repec.org/p/arx/papers/2608.03616.html) and [2607.27070](https://econpapers.repec.org/RePEc:arx:papers:2607.27070)), covering seven cascades in 2022–25:
- Oct 2025 was subcritical (branching ratio ~0.1–0.2).
- 88% of forced selling after onset happened within 30 min, and 63% was absorbed off-book.
- OI fell 25–70%.
- No pre-cascade measure graded severity, and early warnings differed from event to event.

**S10 HL microstructure, Mar 2025 – Jun 2026** ([Jia, Moallemi et al.](https://drops.dagstuhl.de/storage/00lipics/lipics-vol395-aft2026/LIPIcs.AFT.2026.36/LIPIcs.AFT.2026.36.pdf)):
- Liquidations pay ~20x the voluntary half-spread, with ~10x larger adverse moves after the trade.
- Loss-realizing closes revert.

**S11 BitMEX hourly moves above 5%** ([Gornall, Rinaldi & Xiao](https://ftp.aeaweb.org/conference/2026/program/paper/ByyFEfr4)):
- Perps mean-revert quickly while quarterly futures overshoot.
- In stress, quarterly spreads widen 161–249%, vs ~34% for perps.
- Liquidations are 1.9–3.0% of perp volume on Kraken and 0.4–0.8% on Deribit.

**S12 Oct 10 2025** ([Datawallet, citing CoinGlass, Amberdata and Kaiko](https://www.datawallet.com/crypto/october-10-crypto-crash-explained)):
- ~$19.3B liquidated (87% longs). 20:50–21:30 UTC carried $6.93B; the peak minute, 21:15 UTC, $3.21B. BTC perp spread 0.02 → 26.4 bp. Forced selling tapered ~14 h after onset.
- The [Binance USDe book](https://cointelegraph.com/research/exclusively-obtained-orderbook-data-reveals-details-about-usde-crash) lost 74% of its depth in 15 minutes. BTC depth within 1% went ~$8M → ~$3M, still ~$6M months later ([Kaiko](https://whale-alert.io/stories/b3a4016c6bb5b0/Kaiko-Liquidity-for-BTC-ETH-XRP-and-SOL-still-impaired-six-months-after-Oct-10-flash-crash-XRP-liquidity-has-not-recovered-to-pre-crash-levels)).
- Kraken BTC ~9% above Coinbase at the worst point ([Insights4VC](https://insights4vc.substack.com/p/inside-the-19b-flash-crash), single source).

**S13 Hyperliquid ADL** ([Chitra](https://arxiv.org/abs/2512.01112), [Sepper](https://arxiv.org/html/2603.09164v1)):
- ~$2.1B of positions were closed in ~12 minutes: 34,983 ADL fills across 19,337 wallets and 162 markets.
- Deficits were $304.5M. Liquidations were ≈15% of the affected tokens' open interest.
- The excess-haircut estimates differ between versions of the paper.

**In-repo** [V-repo]: R2-08's markout is +26–32 bp at 30–60 minutes and ~4 bp by 4 hours.

**S14 Round numbers**
- [Urquhart 2017](https://ideas.repec.org/a/eee/ecolet/v159y2017icp145-148.html): BTC prices cluster at round numbers, with no return effect after them.
- [Han 2024](https://ideas.repec.org/a/eee/beexfi/v41y2024ics221463502400008x.html): round-cent clustering in a US crypto order book.
- [Zhang 2024](https://afajof.org/management/viewp.php?n=131712), stocks: 24.6 bp/day above vs below round numbers; ETFs show only 2 bp.

**S15 Coinbase/Morpho loans** ([The Block](https://www.theblock.co/post/390403/coinbase-xrp-dogecoin-cardano-litecoin-loans-morpho)): liquidation LTVs of 86% and 62.5%, and more than $1.9B originated.

**Not found:** a crypto stop-run effect size; any study of reopen returns; a quantified test that HL clusters predict anything; CFM's funding settlement clock times and liquidation order type. **Blocked fetches:** English Coinbase margin and hours pages, NinjaTrader spec PDF, data.binance.vision S3 listing, Binance forceOrder docs. The search budget ran out before Osler (2003) and the full Jia et al. paper.

## (c) Top 3

1. **F1, the 4 PM ET margin step-up.**
   - Why: it is the only verified, schedule-driven forced flow on the venue we actually trade. The time is known to the second, the data is local and free, and holidays and weekends give a clean placebo. It doesn't overlap R2-08.
   - Kill test, run first: does aggressive-sell volume or the perp–spot basis show a footprint from 15:58 to 16:03 ET on weekdays, compared with placebo days? If there's none, CFM is internalising and the idea is dead.
   - Then: resting perp bids k residual σ below the spot-implied price for 15:58–16:05, with direction set by the pre-window premium.
2. **F2 + F3, the incumbent's blind spot (Friday reopen and the Mon–Thu thin hour).**
   - Why: R2-08's own audit already puts 19% of its futures P&L at 5–6 PM ET. The documents show 24x7 perps have no daily halt, so the 4:55–6:05 PM ET quiet window throws away tradable hours on Mon–Thu. Oct 10's peak minute fell inside the Friday halt.
   - Test: replay the 1-minute data, check fills against perp trade prints, and get queue evidence from the paper bot's log of bids ahead of ours.
   - Risk: fillability, the same unresolved question as H1.
3. **F4, an HL liquidation-flow feature for R2-08's AI filter.**
   - Why: it is the only labelled, verifiable "forced" signal, with history from May 2025 at a few dollars a month. The AI filter is where R2-08's Sharpe gains came from.
   - Risk: running it live needs our own HL node (or a prereg amendment to allow a vendor stream).

F6, the expiry settlement hour, is the cheapest independent check to run as an extra.
