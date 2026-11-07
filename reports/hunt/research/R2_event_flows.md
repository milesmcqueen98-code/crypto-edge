# R2: Event-driven flows (listings, delistings, unlocks, index/ETF/expiry, depegs)

Wave-2 research memo, Nov 2026. Web research only; no backtests. Time-boxed. The shared web-search budget ran out
near the end, so items marked **(unverified)** need a check before a build relies on them. These fetches were
blocked and not read: the DefiLlama emissions-adapters GitHub page, the MarketVector COIN50 guide PDF, the Coinbase
status-page history index, Upbit's Telegram channel and the Coinbase Advanced fee page.

**Bottom line.** The events in this topic fall into three groups:
- latency races that are over within the announcement minute (listing notices);
- real effects that are rare in the Coinbase-tradable universe (unlock cliffs, delistings, depegs);
- flows too small or too well arbitraged to lean on (index rebalances, ETF fixing, expiries, treasury buys).

The best fits are Coinbase's own new listings, and unlock/delisting calendars used as filters on the wick catcher.

## (a) Candidate ideas
"est." = my estimate, to be counted in the build. CB = Coinbase. Sources [S#] are in (b).

| # | Idea | Who is forced or eager, and why | Why a small trader is paid | Evidence (effect, source) | Backtest data | CB spot / US perp | Events/yr (tradable) | Capacity at $100K | Red flags |
|---|---|---|---|---|---|---|---|---|---|
| E1 | Binance listing or perp-launch notice → follow on CB spot (H5) | Binance users and arbitrage bots buy at once | Only if CB alt books reprice seconds late | Move lands inside the announcement minute: Bithumb n=8, mean peak +13.8%, +8.6% at 10 min (self-reported) [S5]. Binance effect fading [S2]. New-perp median gain-to-max ~1% [S7]. | Binance CMS catalog 48: 2,292 articles, ms stamps, free, reachable from US (wave-1 probe). CB trades, free. | Spot, long only | est. 50–100 | $5–20K per event | Pure latency race (vendors claim µs [S32]); CDN cache ~1 s [S31]; title-parse errors |
| E2 | Upbit/Bithumb KRW listing → follow on CB spot | Korean retail; capital controls slow arbitrage | Same as E1 | CAP +34.5% within 1 min on Bithumb, ~+14% four hours later [S6]. Upbit n=28 on Bybit spot: mean peak +1.2%, +0.1% at 10 min [S5]. Upbit median day-1 +42% fell to +10% after mid-June 2026 [S1]. | Upbit notice feed needs an API key, no history [S8]. Public Telegram channel used by an open-source sniper [S5]. Tardis Upbit trades since 2021 (paid) [S33]. | Spot, long only | est. 30–50 (~100 KRW listings/yr [S1]) | $5–20K | Latency; feed access for a US person (unverified); the big pump is inside Upbit |
| E3 | Robinhood listing → follow on CB | US retail buyers; RH's market makers hedge on US venues | US-hours flow may lag offshore bots | Anecdote only: SHIB +35% the day RH listed it (headline only) [S9] | RH notices (blog/X; vendor feeds cover RH [S32]); CB trades | Spot | est. 10–20 | $10–30K | Tiny n; no study |
| E4 | New CB listing: deep resting bids, days 0–30 (H4) | Airdrop recipients and early holders sell into books with no market-maker inventory | Liquidity to forced sellers; snap-back | Of 42 Binance/CB listings (2024), ~80% rose >10% at some point, but only 12 later held above the listing price; 22 fell >45% [S10]. 88% of 62 airdrops fell, mostly within 15 days [S11]. | CB candles incl. 91 delisted pairs, `new_at` 2023+ (free, wave-1 probe). Status-page phase timestamps [S12]. | Spot, post-only bids | est. 50–100 | $2–10K per listing-day | Persistent downtrend (falling knives); candle fills optimistic |
| E5 | Phase switch: limit-only → full trading | App/market-order buyers arrive only at full trading, 14–24 h after the open | Public timestamp; hold inventory into the switch | **Untested.** SUI: auction→limit-only 13 min, then 24 h to full trading. SPK: 35 min / 21.7 h. BIGTIME: 16 min / 14.6 h [S12]. | Status-page incidents (free; history depth unverified) + CB trades | Spot | as E4 | $2–10K | No prior evidence |
| E6 | Fade listing pumps with US perps | Late FOMO buyers; pumps revert | Shorting thin alts is hard | For >40% Upbit pumps, the day-7 close was 20–65% under the day-1 high (median 45%) [S1]. Premium reverts within ~2 weeks [S2]. 41–71% of new perps peak on day 1 [S7]. | As E1/E2 + CB perp trades | US perp (23 coins) | est. 0–5 | $10–30K | Big perp coins rarely get new listings; squeezes |
| E7 | Unlock pre-drift short on US perps (H7) | Teams and investors sell or pre-hedge before cliffs | Most holders can't short thin alts | Pre-event 1-month median −14.7% vs BTC (p<0.001, n=164). After: −4.85% median vs matched peers (n=221) [S13]. ~90% negative; drift from −30 d; team cliffs ~−25% [S3]. Matters at ≥5% of float, mostly priced in [S14]. | DefiLlama dataset CDN, 373 protocols, free (wave-1 probe). Tokenomist/CryptoRank web views; APIs paid [S34]. | US perp short | est. 3–10 cliffs ≥5% of float | $20–50K | Tiny n; schedule revisions (look-ahead); liquid tokens show no significant effect [S13] |
| E8 | Scheduled treasury release seen on-chain (e.g., LINK quarterly) | Issuer moves ~19M LINK to Binance each quarter | Known seller, visible in real time | Headlines only: $165–262M per release [S15] | Etherscan (free); CB LINK perp | US perp | ~4 | $50K+ | n=4/yr; may sell OTC |
| E9 | Delisting notices: dump, then sometimes a squeeze | Holders forced out before suspension; market makers pull; later, shorts forced to cover | Liquidity provision, or riding the squeeze | Binance Apr 2025 batch: −7% to −28% within minutes [S16]. Sep batch: −7% to −25%, then +62% to +344% a week before delisting [S17]. CB MOVE −20%; book went limit-only at once, suspension ~2 weeks later [S18]. | Binance CMS, CB notices and status page, candles for 91 delisted pairs (free) | Spot bids | est. 10–20 (batched) | $5–15K | Information, not just flow; batches correlate; pump groups |
| E10 | Index rebalances (COIN50 quarterly, Bitwise 10 monthly at 4 pm ET, GDLC quarterly) | Index funds forced to trade at the 4 pm ET reference | Liquidity at the fix | No price-pressure study found. Flows are small: BITW ~$1.3B, HYPE added at ~0.95% [S19, S20]. | 10-K/8-K filings, MarketVector monthlies, Grayscale releases (free) | Spot/perp | ~5–10 add/drops | n/a | Flows ≪ daily volume; pre-announced |
| E11 | ETF 3–4 pm ET fixing flow, conditional on that day's flow sign | APs and issuers trade into the BRRNY window | Only if the flow can be nowcast before 3 pm | That hour was >6.7% of BTC volume in Q1 2024; ~$220M on CB [S21]. In-kind allowed since Jul 29, 2025 [S22]. No return evidence. | Farside daily flows (free, 2024+), CB 1-min (free) | Spot/perp BTC/ETH | ~250 days | Large | Unconditional hour effects already dead; big desks own it; median-based fix |
| E12 | Expiry windows (CME last Friday 4 pm London; Deribit Friday 08:00 UTC) | Rollers, delta hedgers | Pin or settlement pressure | Pre-2021 expiry pattern reversed after BITO [S23]. Pinning: media claims only. | CME calendar (free); Deribit OI (paid) | Perp | 12 / 52 | Large | Calendar effects already dead |
| E13 | Government/estate coin sales (US Marshals, Germany, Mt Gox) | Known sellers move coins on-chain first | Front-run visible transfers | Germany sold ~50k BTC as BTC fell 65k→55.8k, but its largest exchange transfers came after the drop [S24] | Arkham (free web, paid API) | Perp BTC | 2–6 | Large | Few events; everyone watches |
| E14 | Stablecoin depeg ladder (USDT, DAI/USDS, PYUSD, GUSD) (H8) | Panic sellers who can't redeem (KYC, minimums) | Discount at ~zero maker fee | USDT ~$0.95 on 2022-05-12, <$0.99 for ~6 h [S25]. USDC/DAI ~$0.88 on 2023-03-11 [S26]. USDT mild discount through Aug 2023 [S27]. USDe $0.65 on Binance only, Oct 10, 2025 [S28]. | CB 1-min candles (free, 2021+) | Spot | 0–2 deep (>50 bp) | $100K+ | ~3 episodes since 2022; default tail; idle-cash cost |
| E15 | Wrapper discounts (cbETH, cbBTC) | Holders who won't wait for redemption or KYC | Discount accrues back | cbETH ~8% under ETH on 2022-09-09 (stETH ~3%) [S30]. Binance wrappers −80%, Binance only, Oct 10, 2025 [S28]. | CB candles (free) | Spot | ~0–1 | $20–50K | One CB episode in 4 years |

Dropped as dead: corporate treasury (DAT) buys. Strategy's buys averaged ~3.3% of weekly volume, correlated only 0.28
with weekly price change, and are disclosed after execution [S24b].

## (b) Key facts with sources (paraphrased)

**Listing announcements**
- **S1** [4 Pillars](https://research.4pillars.io/en/data/content/the-dying-upbit-listing-pump):
  - Upbit added 58 KRW listings in Jan–Jul 2026.
  - Median first-day gain was 42% through Jun 14, then 10% for the 14 listings after; 8 of those 14 closed day 1
    below the open.
  - Upbit volume was down ~70% YTD.
  - The reference price for "first-day gain" is not stated.
- **S2** [The Tie](https://www.thetie.io/insights/what-does-an-exchange-listing-actually-deliver-in-2026): 1,844
  listings on 7 exchanges, Jan 2023–Jun 2026.
  - Daily, BTC-adjusted VWAP; no announcement-time data.
  - The premium increasingly comes before the listing and reverts within about two weeks.
  - First listings and small caps fade most. Large pre-listing volume spikes predict weak D+7 and D+14.
  - [Companion study](https://www.thetie.io/insights/what-a-binance-listing-delivers-for-already-listed-tokens), 14
    tokens: median drift peaks near +7% around day 9; depth roughly doubles.
- **S4** [RockawayX](https://rockawayx.com/insights/bullish-or-bearish-what-really-happens-when-tokens-list-on-a-cex),
  2024 listings on Binance, Bybit and MEXC: the 7-day difference-in-differences effect is positive but wide; 30- and
  60-day effects are not significant.
- **S5** [exchange-listing-sniper README](https://github.com/sueun-dev/exchange-listing-sniper/blob/main/README.md):
  self-reported; small n; fees not modelled.
  - Ingests Upbit/Bithumb notices from Telegram and buys on Bybit spot.
  - Bithumb n=8: mean peak +13.8%, +8.6% at 10 min; the pump lands inside the announcement minute.
  - Upbit n=28: mean peak +1.2%, +0.1% at 10 min.
- **S6** [BigGo (CAP)](https://finance.biggo.com/news/e5663b55-0efb-49b8-9fd7-1cb7db04d3cd): +34.5% within one minute
  of an Upbit notice; about 15% off the peak four hours later. A buyer one minute late lost money.
- **S7** [BitMEX Q1 2025](https://www.bitmex.com/blog/2025q1-derivatives-report): for new perps, median
  gain-to-maximum is ~1% (Binance) and 0% (OKX), against means of 25–31%; 41–71% peak on day 1.
- **S8** [Upbit changelog](https://docs.upbit.com/kr/changelog/websocket-announcement): an `announcement` stream on
  the private (authenticated) WebSocket since 2026-08-31. Real-time only; no history.
- **S31** [Binance CMS](https://gist.github.com/hungdoansy/b4eb018d5dece90642f632510192e9a4): catalog 48 served via
  CloudFront, with ~1 s cache age observed. The
  [Binance announcements WebSocket](https://developers.binance.com/en/docs/products/announcements/general-info) needs
  a signed Binance API key, which a US person can't hold.
- **S32** [Vendors](https://newlistings.pro/upbit-websocket-listings) (also
  [cryptolisting.ws](https://cryptolisting.ws/best-crypto-listing-alert-services/)):
  - Detection-to-publish of ~190 µs; price moves "can begin within milliseconds".
  - The free tier is delayed 240 ms. Coverage: Binance, Upbit, Bithumb, Robinhood.
- **S33** [Tardis](https://docs.tardis.dev/historical-data-details/upbit): Upbit trades and books since 2021-03-03;
  the first day of each month is free.
- **S35** Older Coinbase studies:
  - [Coin Metrics 2020](https://cointelegraph.com/news/coinmetrics-finds-the-coinbase-effect-is-actually-pretty-lame):
    16 assets, median 10-day return +4%.
  - [The Tie 2020](https://www.thetie.io/insights/exchange-listings): announcement day +24%, listing day +7.5%
    (n=10). Surprise listings: listing day +33% (n=8).
  - Today's roadmap pre-announcements move the pop offshore, before Coinbase trading starts.
- **S9** Headline only: [SHIB +35% on Robinhood listing](https://www.fxempire.com/forecasts/article/shiba-inu-rallies-by-35-as-robinhood-adds-shib-sol-comp-matic-966920).

**Coinbase new listings**
- **S12** Listing mechanics
  ([listings](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/new-asset-listings),
  [auction](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/auction-mode)):
  - Sequence: transfer-only → auction (at least 10 min; limit orders only; post-only and market orders rejected) →
    limit-only or full trading.
  - Unhealthy books go cancel-only.
  - Fills at the opening match pay taker fees on both sides.
- **S12** Status pages give exact timestamps for each phase:
  - [SUI](https://status.exchange.coinbase.com/incidents/zw33064w186l): transfers to auction 24 h; full trading 24 h
    after limit-only.
  - [SPK](https://status.exchange.coinbase.com/incidents/73f6d1p2jmjc): 2.5 h; 21.7 h.
  - [BIGTIME](https://status.exchange.coinbase.com/incidents/vlvb937s28d0): 9 h; 14.6 h.
- **S10** [Blockworks](https://blockworks.co/news/major-exchange-listings-coinbase-binance): about 35% of 2024
  listings went live on their token-launch day.
- **S11** [Keyrock](https://keyrock.com/airdrops-in-the-barren-desert/): high-FDV, low-float launches did worst.
- **S36** [CoinGecko via BeInCrypto](https://beincrypto.com/new-altcoin-listings-price-performance): ~90% of new
  listings on top exchanges are below their debut price after a year.

**Unlocks**
- **S3** [Keyrock](https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/): 16k events, but
  only 40 tokens and mostly linear, so the effective n is small.
  - Price suppression starts ~30 days out; large unlocks settle within ~14 days.
  - Investor unlocks (n=106) show slow, small declines, consistent with OTC, TWAP and options hedging.
  - Ecosystem unlocks average +1.2%.
- **S13** [Streamflow compilation](https://streamflow.finance/blog/token-unlock-report) of a 236-event study (likely
  [Tokenomist's](https://tokenomist.ai/research/do-token-unlocks-crash-prices)):
  - Vs BTC: median −16.3%, mean −8.1%.
  - Thin-float early tokens: about −16% vs peers. Established tokens: not significant.
  - The Tie: the median unlock is 0.20% of daily volume (n=12,350).
- **S14** [Messari via ChainCatcher](https://www.chaincatcher.com/en/article/2162595): 619 events, 41 assets. The
  effect sits within ±7 days, matters for unlocks of 5–10%+ of supply, and shorting on the unlock date is unreliable.
- **S34** Data access:
  - [DefiLlama](https://docs.llama.fi/pro-api): unlocks are in the $300/month API tier, but wave 1 found the dataset
    CDN free.
  - [Tokenomist](https://docs.tokenomist.ai/tier-overviews): the free tier is web-only.
- **S15** Headlines only:
  [LINK quarterly unlock → Binance](https://rallies.ai/news/chainlink-drops-as-165m-quarterly-link-unlock-drives-large-binance-inflows).

**Delistings**
- **S16** [DailyCoin](https://dailycoin.com/binance-to-delist-six-altcoins-sparking-an-immediate-selloff/): FUN −28%,
  MDT and FIO −20%+.
- **S17** [CryptoRank](https://cryptorank.io/news/feed/828da-binance-delisting-sparks-volatile-rallies-in-bakerytoken-hifi-finance-and-self-chain):
  analysts blame short squeezes in thin books; ALPACA quadrupled after its notice, then collapsed.
- **S18** [The Block](https://www.theblock.co/post/352790/coinbase-to-suspend-trading-for-move-by-may-15): suspension
  ~2 p.m. ET about two weeks after the notice.

**Index, ETF, expiry, sellers**
- **S19** [Bitwise 10 10-K](https://www.sec.gov/Archives/edgar/data/1723788/000119312526085428/bitw-20251231.htm):
  - Monthly reconstitution at 4 pm ET on the last business day.
  - Trades target the CF Benchmarks 3–4 pm price; Coinbase acts as agent.
  - A noon check forces a same-day rebalance if holdings in approved components fall below 86%.
- **S20** Other indices:
  - [COIN50](https://www.marketvector.com/insights/mvis-insights/coin50-monthly-march-2026): quarterly (Feb 27, then
    May 29, 2026); 50% weight cap.
  - [BITW Jul 2026](https://en.cryptonomist.ch/2026/07/09/bitwise-crypto-index-etf-rebalance/): +HYPE, +XLM, −DOT,
    −AVAX.
  - [GDLC](https://www.tipranks.com/news/company-announcements/grayscale-completes-quarterly-rebalancing-of-crypto-etf):
    alts ≤5%.
- **S21** [Kaiko](https://www.kaiko.com/resources/btc-etfs-impact-on-spot-market-structure): the weekend share of
  volume hit a record low of 16%.
- **S22** [MoFo](https://www.mofo.com/resources/insights/250801-sec-permits-in-kind-creations-and-redemptions-for-crypto-etps):
  in-kind approval lets APs deliver BTC directly.
  [CME FAQ](https://cmegroup.com/articles/faqs/cme-cf-cryptocurrency-benchmarks-faq.html): the fix is 12 five-minute
  volume-weighted medians, averaged, across seven venues including Coinbase. That design dilutes any single flow.
- **S23** [Quantpedia](https://quantpedia.com/cryptocurrency-market-dynamics-around-bitcoin-futures-expiration-events/):
  small sample; no stable sign.
- **S24** [Gemini](https://www.gemini.com/en-SG/blog/crypto-for-sale-price-impacts-of-germanys-btc-liquidation-mt-gox-and-etf):
  the authors say causality can't be assigned.
  **S24b** [TD Cowen via CoinDesk](https://hotfix.coindesk.com/markets/2025/04/21/strategy-s-bitcoin-buying-spree-has-minimal-impact-on-prices-td-cowen-says).

**Depegs and fees**
- **S29** [Coinbase Exchange fees](https://support.coinbase.com/en/exchange/trading-and-funding/exchange-fees):
  - Stable pairs: maker 0.00%; taker 0.10–0.45 bp by liquidity-program tier.
  - Normal spot starts at 40/60 bp.
  - The pairs aren't listed; the examples given are USDC and WBTC
    ([2022 blog](https://www.coinbase.com/blog/coinbase-exchange-unlocks-stable-pair-trading)).
  - **Unverified:** whether USDT-USD on Advanced is billed as a stable pair.
- **S25** [USDT May 2022](https://www.web3isgoinggreat.com/single/tether-loses-peg-drops-below-095): the venue isn't
  named; the Coinbase low is unverified.
- **S26** [The Block](https://www.theblock.co/post/218993/usdc-and-dai-remain-at-about-0-90-following-circles-disclosure-of-funds-at-svb):
  - Coinbase paused USDC↔USD conversion for the weekend.
  - USDT traded at $1.06 on Kraken.
  - Coinbase has no USDC-USD book, so the tradable leg was DAI.
- **S27** [Kaiko](https://www.kaiko.com/resources/defining-depegs-a-new-metric-for-stablecoin-stability): USDT's
  depeg threshold is ~$0.998. Aug 2023 came after ~$500M of net selling.
- **S28** [Galaxy](https://www.galaxy.com/insights/research/cryptos-flash-crash-liquidation-binance-adl-auto-deleveraging):
  USDe stayed near par off Binance; nothing reported for Coinbase.
- **S30** [Decrypt](https://decrypt.co/109396/coinbase-ethereum-staking-token-trading-discount-why): the cbETH
  discount came from KYC'd redemption and freeze risk.

## (c) Top 3, and which ideas can reach t ≥ 3

**1. E4 + E5: Coinbase's own new listings.**
- **Why:**
  - Coinbase venue and order types.
  - Named forced sellers: airdrop and unlocked holders. About a third of listings launch on token-launch day.
  - Free, survivorship-free candles.
  - Exact phase timestamps on the status page.
  - Events are too small per listing for funds.
- **Risk:** the base rate is a downtrend (S10, S36). So bids must be deep and exits fast; this is not a long-drift
  trade.
- **E5:** a new, testable question. Does inventory bought in the limit-only phase earn a return at the switch to full
  trading?

**2. E1/E3 as a decisive "does Coinbase lag?" test (H5).**
- **Prior:** low. Global moves finish within the minute, vendors dispatch in microseconds, and late buyers can lose
  (S5, S6).
- **Why test it anyway:** 2,292 ms-stamped Binance articles make it cheap, and n is large enough to settle the
  question either way.
- **By-product:** a news-shock flag for the wick catcher.

**3. E7 + E9 as filters on the wick catcher, not standalone books.**
- **E7:** unlock pre-drift is the most consistent published effect in this topic (S13: p<0.001 pre-event). But a
  standalone perp short gets only ~3–10 tradable cliffs a year.
- **Filters:**
  - Skip or shrink alt dip bids in the 30 days before a cliff of ≥5% of float.
  - Exclude coins under a delisting notice: a forced sale there carries information.
- **Payoff:** the filters ride the incumbent's thousands of fills, so they can be measured with real power. They are
  also cheap insurance against the incumbent's worst catches.

**Power.** For per-event Sharpe s, t = s·√n, so t ≥ 3 needs n ≥ 9/s².

| Per-event Sharpe s | Events needed |
|---|---|
| 0.5 | 36 |
| 0.3 | 100 |
| 0.2 | 225 |
| 0.1 | 900 |

- **Can reach t ≥ 3 if the effect is real:** E1, E2, E4, E5 (n in the hundreds over 2022–26) and E11 (~250 days a
  year).
- **Marginal:** E9 (batched: effective n ~10–15 a year) and E7 (≤10 a year in perp coins; spot history only with
  "hypothetical shortability").
- **Cannot reach t ≥ 3:** E6, E8, E10, E12, E13, E14, E15. Judge them by mechanism and stress tests, not t-stats.
  - Depeg ladders are insurance-like: ~3 Coinbase episodes since 2022.
  - If the 0-maker stable-pair fee applies to USDT-USD, the cost of a permanent ladder is idle cash only.

**Status changes vs wave 1 (ideas.md):**
- **UP (#23):** Upbit now has an official notice stream, but it needs an Upbit API key. The public Telegram channel
  could supply minute-stamped history (unverified).
- **ST (#20):** the stable-pair maker fee is 0.00% on Coinbase Exchange. Check whether it applies to USDT-USD on
  Advanced before declaring ST dead.
- **DL (#25):** prices sometimes follow a two-phase path, dump then squeeze. Add the delisting exclusion to the
  incumbent regardless.
