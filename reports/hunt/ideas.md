# Edge hunt, wave 1: 48 mechanism-first ideas (research memos R1–R4 folded in)

The test for every idea: **who is forced (or eager) to trade, and why does a small liquidity provider or fast follower
get paid?** Research memos: reports/hunt/research/R1–R4. Data probes: reports/hunt/probe.json and probe2.json.

## How the ideas are ranked (prior score, 0–10)
- **Mechanism, 0–3:** a named forced or eager counterparty, and a reason it persists.
- **Testable now, 0–3:** trade-level or event-level history exists and is free.
- **Live-implementable, 0–2:** every input is available to a US bot, and Coinbase supports the orders.
- **New vs R2-08, 0–2:** a different trigger, universe or venue, so it can add Sharpe rather than duplicate it.

## Facts that shaped the ranking (probes, Nov 7)
- **Coinbase perp trades:** Coinbase's public market-trades endpoint serves trade-by-trade history for its US perps by
  time window.
  - BTC and ETH perps from Aug 2025, SOL from Sep 2025, alt perps from Dec 2025.
  - So perp-only wicks can be checked against real prints, not candles.
- **Delisted spot products:** Coinbase still serves candles for delisted spot products (91 delisted USD pairs).
  Advanced Trade's product list carries a listing time (`new_at`) for listings from 2023 on. So a new-listings study
  can be survivorship-free.
- **Binance:**
  - Binance's announcement API (2,292 listing articles, ms timestamps) answers from a US runner.
  - Binance market data (bulk files) is downloadable for research, but its live API is geo-blocked for US clients.
  - Binance's bulk files have no liquidation history.
- **Liquidations:** Tardis' free tier has Binance liquidations only on the first day of each month.
- **Hyperliquid:**
  - Its public API serves funding history and current state only.
  - 1-minute candles go back about 3.5 days.
  - There is no history of positions or liquidation levels.
- **Unlocks:** DefiLlama's dataset CDN serves token-unlock schedules for 373 protocols free (its API version is paid).
- **Upbit:** Upbit's Korean announcement feed refuses plain clients. We don't work around that.

## The 44 ideas
Status key: **W2** = built in wave 2 · **alt** = next in line · **merged** = tested inside another idea ·
**blocked** = can't be tested or traded honestly now · **dead** = an earlier round killed the mechanism.

### A. Forced sellers and buyers: liquidations, stops, margin
| # | Idea | Who is forced or eager; why we're paid | Data / live inputs | Prior | Status |
|---|---|---|---|---|---|
| 1 | **PB: perp-only wicks, long** | FCM liquidations and market sells hit empty US-perp books. Resting bids supply the missing liquidity and are paid by the snap-back to the spot-implied price. | Perp trades since launch, spot candles / Coinbase | 9 | W2 (H1) |
| 2 | PB-R: perp-only rips, short | Short squeezes and forced buy-ins lift thin perp offers. The short side is tradable only on perps. | Same | 7 | merged (H1) |
| 3 | **FR: cascade exhaustion on BTC/ETH/SOL/XRP perps** | Forced deleveraging overshoots; the buyer after exhaustion is paid by the rebound. Perps make taker entry cheap (BTC ~3 bp a side). R2-08 never trades BTC. | Spot 1m 2021–26, perp trades / Coinbase | 7 | W2 (H2) |
| 4 | **LM: liquidation-density bids** | Leveraged longs opened at high-volume prices get liquidated at entry × (1 − 1/leverage). Bids beyond dense zones catch the end of the cascade. This is the testable proxy for Hyperliquid's public levels. | Coinbase spot+perp volume-at-price (live); Binance OI as research check | 5 | W2 (H3) |
| 5 | HL: Hyperliquid public liquidation map | Live positions show where forced selling sits. | No history of positions or levels | 6 | blocked: forward-collect |
| 6 | SC: reopen after the perp maintenance halt | Stale stops and thin books at the daily/weekly reopen. | Perp trades / Coinbase | 6 | merged (H1, time split) |
| 7 | **MC: intraday-to-overnight margin step-up at 4 pm ET** | Opt-in intraday margin ends at 4 pm ET on weekdays. The overnight requirement is 2–4× higher (R3). Under-margined retail must cut at a known minute; the provider is paid by the reversion. | Perp trades / Coinbase | 8 | W2b (H9) |
| 8 | SR: stop-run reversals at prior lows and round numbers | Clustered retail stops fire together; the sweep reverts. | Spot 1m / Coinbase | 5 | alt |
| 9 | RN: front-run round-number bid walls | Retail limit orders cluster at round prices. | Spot 1m | 3 | merged (SR) |
| 10 | CW: cross-venue liquidation feed as a live trigger | Binance/Bybit liquidations lead US prices. | Live feed geo-blocked in the US | 5 | blocked |
| 11 | WE: weekend thin-book wicks in BTC | Thin weekend books. | Spot 1m | 3 | dead (seasonality) |
| 12 | LT: long-tail Coinbase spot wick catcher (beyond 31 coins) | Same forced sellers, thinner books. | Spot 1m to fetch | 4 | W2e (H12) |
| 13 | FU: monthly perp-futures expiry convergence | Forced rollers at the 11 am ET settlement window. | Perp trades / Coinbase | 3 | low power (~50 events) |

### B. Venue and basis dislocations
| # | Idea | Who is forced or eager; why we're paid | Data / live inputs | Prior | Status |
|---|---|---|---|---|---|
| 14 | **VD: Coinbase-specific dislocation bids** | US-specific sellers (app market sells, US news) push Coinbase spot below other venues; slow cross-venue inventory pays the provider. Fair value: Bitstamp, Coinbase perp. | Spot 1m both venues 2024–26 / Coinbase+Bitstamp | 6 | W2 (H6) |
| 15 | BS: slow basis-spike convergence (long spot, short perp) | Retail leverage demand lifts perp premia for hours. | Perp+spot 1m | 4 | merged (H1 rip side); carry dead |
| 16 | NP: launch days of new US perps | Empty books at launch. | Perp trades | 4 | merged (H1) |
| 17 | CP: Coinbase-vs-Binance premium spikes | US flow vs offshore flow. | Binance live data blocked | 3 | blocked |
| 18 | IX: 24/7 index and commodity perps vs the reopen of the underlying | Weekend retail flow in US500/Tech100/gold perps with no hedge until Globex reopens. | Perp candles to fetch; ~50 weekends | 4 | alt |
| 19 | PX: PAXG spot vs PAXG perp vs gold futures on Coinbase | Three Coinbase instruments on one asset. | Small | 3 | alt |
| 20 | ST: stablecoin-pair oscillation (USDT-USD etc.) at low fees | Tether mint/redeem flow. Stable pairs pay 0% maker (R2/R3), but USDT-USD likely pays standard fees. | Two-sided quoting dead | 2 | dead (two-sided quoting) |
| 45 | **XQ: secondary-book wicks (BTC/ETH/USDT-quoted pairs)** | Makers pull secondary books first in cascades; sellers sweep near-empty books; slow triangular arbitrage pays the bidder (R4). | Candles and prints for every pair / Coinbase | 6 | W2c (H10) |
| 46 | PS: new-listing phase switch (limit-only → full trading) | App and market-order buyers can only arrive at full trading, 14–24 h after the open, at a public timestamp (R2, E5). | Status-page phase times (history depth unverified) + prints | 5 | W2e (H13) |
| 48 | **MJ: deep hourly bids on BTC/ETH/SOL/XRP perps** | Forced selling into empty books on the majors; R2-08 never bids in BTC. From H3's control arm (DEV only). | Spot 1m 2021–26, perp candles and prints / Coinbase | 6 | W2d (H11) |
| 47 | UF: unlock and delisting filters on the incumbent | Skip alt dip bids within 30 days of a cliff ≥5% of float, or under a delisting notice: forced sales there carry information (R2). | DefiLlama CDN + Binance delist notices | 4 | build-plan risk filter (refinement, not a new book) |

### C. Events: listings, delistings, unlocks, airdrops
| # | Idea | Who is forced or eager; why we're paid | Data / live inputs | Prior | Status |
|---|---|---|---|---|---|
| 21 | **NL: new Coinbase listings, first 30 days** | Airdrop recipients and early holders dump into books with no market-maker inventory. The provider is paid by the snap-back. Different coins from R2-08. | Candles/trades incl. delisted / Coinbase | 7 | W2 (H4) |
| 22 | **AN: Binance listing/launch announcements → Coinbase spot** | Binance users and arbitrageurs are eager buyers. Is any drift left after 2–15 s for a polling bot? | Binance announcement API (US-accessible) + Coinbase trades | 6 | W2 (H5) |
| 23 | UP: Upbit KRW listing announcements | Korean retail demand shock. | Feed refuses plain clients | 6 | blocked |
| 24 | CL: Coinbase roadmap/listing announcements | Eager buyers on other venues. | Untradable on Coinbase before listing | 2 | dead |
| 25 | DL: delisting announcements → deep bids | Holders forced out before the delist date. | Binance announcements + Coinbase | 4 | alt |
| 26 | **UL: token unlocks** | Insiders sell and pre-hedge around cliff unlocks: short the perp before, bid after. | DefiLlama unlock data (free CDN) + spot/perp | 5 | W2 (H7) |
| 27 | TG: TGE/airdrop first-day dumps | Airdrop farmers sell at once. | As 21 | 5 | merged (H4) |
| 28 | LP: Launchpool/HODLer airdrop farming flows | Borrow-and-sell farming. | Offshore | 2 | blocked |

### D. Index, fixing, ETF and treasury flows
| # | Idea | Who is forced or eager; why we're paid | Data / live inputs | Prior | Status |
|---|---|---|---|---|---|
| 29 | EF: spot-ETF 4 pm ET NAV fixing flows | APs' hedges into the CF Benchmarks window. In-kind creations since 2025 shrink it; big funds trade it. | Farside daily flows + spot 1m | 3 | alt |
| 30 | IR: index rebalances (COIN50, Bitwise 10, Grayscale) | Index funds trade on known dates. | Few events | 3 | low power |
| 31 | CM: CME expiry/roll windows | Settlement on the BRR window. | 12/yr | 2 | low power |
| 32 | DX: Deribit Friday expiry pin | Dealer hedging. | Open-interest history is paid | 3 | blocked |
| 33 | GV: government/estate coin sales | Known sellers move coins on-chain first. | Paid on-chain labels; few events | 3 | blocked |
| 34 | DT: corporate treasury buy programs | Buys announced after execution. | — | 1 | dead |

### E. Depegs and insurance
| # | Idea | Who is forced or eager; why we're paid | Data / live inputs | Prior | Status |
|---|---|---|---|---|---|
| 35 | **DP: stablecoin and wrapped-asset depeg bids (USDT, PYUSD, DAI, USDS, EURC, GUSD, cbBTC/cbETH)** | Panic redemptions and forced de-risking push stables below par; redemption at par pays the patient bidder. | Spot 1m to fetch / Coinbase | 5 | W2 (H8) |
| 36 | WR: wrapped-asset discounts | Same. | Same | 3 | merged (H8) |

### F. Microstructure and lead-lag
| # | Idea | Who is forced or eager; why we're paid | Data / live inputs | Prior | Status |
|---|---|---|---|---|---|
| 37 | LL: perp-leads-spot lead-lag | Perps reprice first. | — | 2 | dead (BTC-synchronised bid rejected) |
| 38 | TW: TWAP/iceberg footprints on Coinbase prints | A detectable parent order keeps pushing. | Heavy trade data | 3 | alt |
| 39 | OB: order-book imbalance/queue | — | — | 1 | dead (maker round) |
| 40 | RV: continuous minute reversal | Gross Sharpe 4+, but 0.2 bp edge < spread. | — | 1 | dead |

### G. Volatility and premia
| # | Idea | Who is forced or eager; why we're paid | Data / live inputs | Prior | Status |
|---|---|---|---|---|---|
| 41 | SV: short BTC vol via IBIT options | Insurance buyers. | Outside Coinbase | 3 | out of scope (near miss earlier) |
| 42 | FV: funding-spike fades | — | — | 1 | dead (carry) |

### H. AI
| # | Idea | Who is forced or eager; why we're paid | Data / live inputs | Prior | Status |
|---|---|---|---|---|---|
| 43 | AIx: forced-vs-informed selloff classifier | Filter that skips news-driven falls. | Timestamped news history lacking | 3 | R2-08 refinement, not a book |
| 44 | PM: Coinbase-listed prediction markets vs the perp-implied distribution | Retail longshot bias. | Outside the stated venues | 3 | out of scope (flag) |

## Wave-2 selection
- **Picked:** the eight W2 builds. They are the highest prior scores among testable, live-implementable ideas. All
  five of Miles' seeds are among them in their testable form:
  - perp-only wicks (H1);
  - liquidation levels (H3, via the live-available proxy);
  - unlocks (H7);
  - new listings (H4, H5);
  - depegs (H8).
- **Expected to struggle:** the two depeg/unlock ideas are expected to struggle to reach t ≥ 3 on event counts alone.
  They are built anyway, because a seed deserves a real test rather than a guess.
- **Next in line if wave 2 finds nothing:** the "alt" ideas: SR, LT, IX/PX, DL, EF, TW.
