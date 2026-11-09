# Edge hunt 2: the idea list

The test for every idea: **who is forced (or eager) to trade, and why does a slow liquidity provider or follower get
paid?** Sources: the three desk lenses (HRT microstructure, SIG options/game theory, Renaissance many weak signals);
research memos R1–R4 (reports/hunt2/research/); every earlier round. Rejected mechanisms are not re-proposed unless
the mechanism is new.

## How ideas are scored (prior, 0–12; fixed before any build)
- **Mechanism (M, 0–3):** a named forced or eager counterparty, and a reason it persists.
- **Testable on trade data now (T, 0–3):** free trade-level or event-level history covering DEV and at least one
  HOLD era, with enough events for t ≥ 2 to be reachable.
- **Live from New York (L, 0–2):** every input live-available to a US bot; Coinbase supports the orders.
- **New (N, 0–2):** a new mechanism or new information for the ladder (0 = a re-test of a rejected mechanism).
- **Clears 2× costs (C, 0–2):** the plausible edge per trade exceeds the round trip at 2× (Path A filters pay no new
  costs; perp taker round trips at 2× are ~20 bp BTC, ~26 bp XRP, ~32 bp SOL, ~50 bp ETH).
- **Selection:** the ten highest totals; ties go to Path A (no new costs, a head-to-head test), then to coverage of
  the requested categories.

Status: **BUILD** (one of the ten) · **alt** (next in line) · **merged** (tested inside a build) · **blocked** (no
honest test or trade now) · **dead** (an earlier round killed the mechanism) · **low** (low power or prior) · **oos**
(out of scope for this account).

## A. Microstructure and order flow (HRT lens)
| # | Id | Idea | Who is forced or eager; why we are paid | Data | Path | M T L N C | Score | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | WHO | Who sold into our bid: block share, aggressor share, concentration, frenzy vs drift, 5–15 min before the fill | Liquidations/stops/retail panic arrive as bursts of small and mid-size aggressive orders (paid: Grossman–Miller); informed sellers and metaorders arrive as large, concentrated, persistent orders (adverse) | Coinbase prints, every parent, all eras | A | 3 3 2 1 2 | 11 | **BUILD** |
| 2 | EXH | Is the forced selling spent? Intensity vs its 30-min peak, cumulative selling / ADV, imbalance turn | Forced selling is front-loaded (88% in 30 min, Oct 2025); a fill after the burst meets the last of it, a fill at the peak is early | Same prints | A | 2 3 2 1 2 | 10 | **BUILD** |
| 3 | LIQW | Liquidity withdrawal: EDGE spread, Kyle λ, Amihud vs 7-day medians at the fill | Liquidity providers charge more when others pull out (Nagel 2012); a vacuum refills | Prints + candles | A | 2 2 2 1 2 | 9 | alt (overlaps the AI's volatility-regime features) |
| 4 | HAWK | Self-excitation (Hawkes branching ratio) of sell prints before the fill | Reflexive bursts overshoot; exogenous news arrivals persist | Prints | A | 2 2 2 1 2 | 9 | alt (R3: no reversal evidence) |
| 5 | META | Post-metaorder impact decay: buy after a persistent sell flow ends | Executors pay impact; ~1/3 of peak impact is transient (Bouchaud et al.) | Prints | B | 2 2 2 2 0 | 8 | low (≈10 bp edge < ~24 bp maker round trip at 2×) |
| 6 | TICK | One tick below the best bid on 20–36 bp-tick coins (PEPE, SHIB, BONK) | Impatient sellers cross a huge tick; the queue refills | Prints | B | 2 1 2 2 1 | 8 | low (queue position unobservable without book history) |
| 7 | RND | Retail round-notional orders (app-sized $10–$10K): fade retail imbalance | Coinbase app flow is uninformed | Prints | B | 2 2 2 2 0 | 8 | merged (feature `sell_round_share` in the parent file) |
| 8 | TSIZE | Trade-size mix (small-order share) as a reversal signal | Retail panic sells small | Prints | A | 1 3 2 1 2 | 9 | merged into WHO (R3: size uninformative where tested; WHO keeps the ADV-relative block share) |
| 9 | QI | Queue imbalance at the touch to time take-profits | Large-tick queue dynamics (Cartea–Jaimungal) | Order book | A | 2 0 2 1 2 | 7 | blocked (no book history) |
| 10 | QREF | Book resilience after the sweep for the deeper rungs | Refill speed separates liquidity shocks from information | Order book | A | 2 0 2 1 2 | 7 | blocked |
| 11 | QHR | Quarter-hour bursts (Kim & Hansen 2026) | Scheduled algorithms | Prints | B | 1 3 2 1 0 | 7 | dead (≈0.5 bp) |
| 12 | MM | Two-sided quoting, minute reversal as taker | — | — | — | — | — | dead (maker round, minute round) |

## B. Events and scheduled flows
| # | Id | Idea | Who is forced or eager; why we are paid | Data | Path | M T L N C | Score | Status |
|---|---|---|---|---|---|---|---|---|
| 13 | MAC | Pull the ladder around CPI/NFP/PPI/FOMC | Releases move prices on information; resting bids are hit by informed flow (Glosten–Milgrom); only CPI moves BTC reliably (R2) | BLS/Fed calendars, frozen simulator | A | 2 3 2 2 2 | 11 | **BUILD** |
| 14 | MACB | Deep bids/offers on BTC/ETH/SOL/XRP perps through releases | Stops and liquidations overshoot the news | Calendars, prints | B | 1 3 2 2 1 | 9 | alt (R2: releases are information; no overshoot evidence) |
| 15 | E2 | Alts overshoot their beta at releases; re-arm the ladder 2 min after with a stress beta | Alt makers pull depth before the print | Calendars, candles | A | 2 1 2 2 2 | 9 | alt (needs new parents the frozen simulator cannot create) |
| 16 | SUPPLY | Skip a coin's bids around cliff unlocks ≥ 1% of supply / delisting notices | Insiders and holders forced by a schedule; their selling is persistent | DefiLlama (H7), Binance notices (H5) | A | 2 1 2 2 2 | 9 | low (SUI, ONDO, HBAR, ENA only) |
| 17 | F2 | First perp listing anywhere: short-sale constraint relief (Miller 1977) | New shorts; dips are informed | HL/Binance listing dates | A | 2 1 2 2 2 | 9 | low (few events in the 17 coins) |
| 18 | F3 | Binance delisting / auto-settlement deadlines | Holders forced out by a date | Binance notices | B | 2 1 1 2 1 | 7 | low |
| 19 | DAT | Treasury-company buy programs | Mandated buyers | Filings | B | 1 0 1 2 1 | 5 | dead (OTC, disclosed after; R2) |
| 20 | IDXR | Index rebalances (COIN50, Bitwise 10, Grayscale) | Funds trade on known dates | Few events | B | 2 1 2 1 1 | 7 | low |
| 21 | ETFL | Spot alt-ETF launch seeding (SOL/LTC/HBAR Oct 2025, XRP Nov 2025) | Seed creations | Few events | B | 1 1 2 2 1 | 7 | low |
| 22 | MON | Monday US-open ETF flow after big weekend moves | Advisors trade only in US hours | Candles | B | 1 3 2 1 1 | 8 | low (seasonality-adjacent) |
| 23 | HOLI | US holidays (ETFs closed) | — | Candles | B | 1 1 2 1 1 | 6 | low |
| 24 | RECUR | Recurring buys / paydays | Scheduled retail buys | — | B | 1 1 2 1 0 | 5 | dead (River 2026: 0.08% hour spread) |
| 25 | TAX | Year-end tax-loss selling | Taxable holders | Once a year | B | 1 0 2 1 1 | 5 | low |

## C. Leveraged/ETF flows and settlement windows
| # | Id | Idea | Who is forced or eager; why we are paid | Data | Path | M T L N C | Score | Status |
|---|---|---|---|---|---|---|---|---|
| 26 | LETF | US-close leveraged-ETF rebalancing: momentum into 4 pm, reversal after (taker and maker) | 2x/−2x ETFs must trade 2×AUM×r (≈$30M per 1% BTC, $17M per 1% ETH) into CME's 3:59–4:00 pm settlement; followers take the impact, providers the ~1/3 that reverts | Candles, prints, ETF data, NYSE calendar | B | 3 3 2 2 1 | 11 | **BUILD** |
| 27 | LETFA | LETF close pressure as a ladder rule (pause/let run around 4 pm) | Same flow seen by the ladder | Same | A | 2 2 2 2 2 | 10 | merged (LETF's maker leg is the liquidity-provision form) |
| 28 | NAV | Spot-ETF 3–4 pm fixing flows | Cash creations | — | B | 1 2 2 1 1 | 7 | dead (in-kind since Jul 29 2025; R2) |
| 29 | MSTRL | MSTR leveraged-ETF flows | MSTU/MSTX swaps | — | — | — | — | oos (trade MSTR stock) |
| 30 | CMEW | CME 24/7 (May 29 2026) and the weekend gap | — | — | — | — | — | dead (gap trades rejected; monitor weekend wicks) |

## D. Cross-venue, basis and funding
| # | Id | Idea | Who is forced or eager; why we are paid | Data | Path | M T L N C | Score | Status |
|---|---|---|---|---|---|---|---|---|
| 31 | XV | Local or global? Skip dislocations that Bitstamp shows too | A Coinbase-only dip is a local liquidity shock repaid by slow cross-venue arbitrage; a global one is a new price | Coinbase + Bitstamp 1-min (2024–26) | A | 2 2 2 1 2 | 9 | alt (displaced by IMP, score 12, from memo R1) |
| 32 | CROWD | Funding crowding: skip bids when shorts are crowded | Long-crowded selloffs liquidate longs (forced); short-crowded selloffs are voluntary | Hyperliquid funding (2023-05 ..) | A | 2 2 2 2 2 | 10 | **BUILD** |
| 33 | HLB | Perp-led vs spot-led drop (Hyperliquid basis) | Liquidated longs drag spot via basis arbitrage | HL archive (requester-pays) | A | 3 0 2 2 2 | 9 | blocked (no free history; forward-collect) |
| 34 | HLOI | Hyperliquid OI depletion during the drop | Longs closing = fuel spent | HL archive | A | 3 0 2 2 2 | 9 | blocked |
| 35 | HLW | Hyperliquid wallets: liquidated/backstop vs skilled sellers | Identity of the seller | HL archive (since 2025-03) | A | 3 0 2 2 2 | 9 | blocked |
| 36 | KRL | Kraken Futures liquidation-tagged prints | Direct forced-selling gauge | 7-day REST history | A | 3 0 1 2 2 | 8 | blocked (forward-collect) |
| 37 | CFMB | CFM perp premium at t−1 as a filter | Perp-led liquidations | CFM candles (alts from Dec 2025) | A | 2 1 2 1 2 | 8 | low (short history) |
| 38 | DATED | CFM dated-futures wicks vs perp fair value | Roll and liquidations on thin dated books | CFM prints | B | 2 1 2 1 0 | 6 | low (H1-adjacent; per-contract fees) |
| 39 | COT | CFTC weekly positioning (nano BTC) | Leveraged positioning | Weekly | A | 1 1 2 1 2 | 7 | low |
| 40 | VD | Coinbase vs Bitstamp/perp gap trading | — | — | — | — | — | dead (H6, H10) |
| 41 | CARRY | Funding/basis carry | — | — | — | — | — | dead |

## E. Options, volatility and game theory (SIG lens)
| # | Id | Idea | Who is forced or eager; why we are paid | Data | Path | M T L N C | Score | Status |
|---|---|---|---|---|---|---|---|---|
| 42 | GAMMA | Dealer gamma regime (Deribit inventory from taker flow): skip bids when dealers are short gamma | Short-gamma dealers must sell into falls (forced, procyclical); long-gamma dealers buy dips beside us | Deribit option trades 2021– (history.deribit.com, reachable from runners) | A | 3 3 1 2 2 | 11 | **BUILD** |
| 43 | EXP | Deribit Friday expiry unwind (direction from dealer inventory) | Dealers unwind hedges of expiring options inside the 08:00 UTC TWAP window | Same + Coinbase candles/prints | B | 3 3 1 2 1 | 10 | **BUILD** |
| 44 | PUTW | Bids beyond large dealer short-put strikes | Hedging accelerates through the strike | Deribit | A | 2 2 1 1 2 | 8 | low (close to rejected liquidation-cluster bids) |
| 45 | IBITP | IBIT expiry pin in the 3–4 pm benchmark hour | IBIT dealers | Forward-only OI | A | 2 0 2 2 2 | 8 | blocked |
| 46 | VRP | Implied-minus-realized volatility regime | Insurance demand | DVOL (not live-legal before IBIT IV) | A | 1 2 1 1 2 | 7 | low |
| 47 | HALT | CFM ±10% halt spill-over onto spot | Liquidations and hedges rerouted to spot | CFM gaps | A | 2 1 2 2 2 | 9 | low (5–15 events a year) |
| 48 | FVL | CFM fair-value-limit band edges | Orders beyond ±5% rejected | Few events | B | 1 1 2 2 1 | 7 | low |
| 49 | PRED | Kalshi/Coinbase prediction-market longshot bias | Retail takers (−20% before fees) | Kalshi API | — | 2 2 0 2 2 | — | oos (not on Coinbase Advanced) |
| 50 | GRID | Passive symmetric grid (short gamma) | — | — | — | — | — | dead (maker round; rips don't revert) |
| 51 | TAIL | Far-out 10σ+ rungs | — | — | — | — | — | dead (wick v4) |

## F. Statistical and ML (Renaissance lens)
| # | Id | Idea | Who is forced or eager; why we are paid | Data | Path | M T L N C | Score | Status |
|---|---|---|---|---|---|---|---|---|
| 52 | SHAPE | Air pocket or grind: path efficiency, jump share, worst-minute share, 6-hour drift | Forced sellers empty the book in a minute and it refills; informed sellers grind and the impact lasts | Coinbase 1-min candles, all eras | A | 2 3 2 2 2 | 11 | **BUILD** |
| 53 | BURN | A coin whose last ladder failed is skipped for hours | A failed rebound reveals a persistent seller; the next dip in that coin is likely the same seller | Frozen dataset (own outcomes) | A | 2 3 2 2 2 | 11 | **BUILD** |
| 54 | BRK | SADF/CUSUM explosive-trend filter | Bubble-burst regimes | Candles | A | 1 3 2 1 2 | 9 | merged into SHAPE (DRIFT6h); R3 discards SADF |
| 55 | ONE | Retrain R2-08's LightGBM with every new feature family | Many weak signals, one model | All of the above | A | 2 2 2 1 2 | 9 | alt (the lab found feature additions neutral; run after the filters) |
| 56 | UNIQ | Overlap-aware training: uniqueness weights, episode-blocked CV, threshold by PBO/DSR | Not alpha: robustness of the threshold | Existing | A | 1 2 2 1 2 | 8 | alt |
| 57 | TSC | Minutes since the cascade began | Late fills meet informed sellers | Candles/prints | A | 2 2 2 1 2 | 9 | alt |
| 58 | JUMPV | Signed jump variation over 7 days | Lottery coins drift down | Candles | A | 1 3 2 1 1 | 8 | low |
| 59 | MSIZE | Meta-label sizing | — | — | — | — | — | dead (ladder v6 sizing) |
| 60 | POST | Post-fill model for deeper rungs/exits | — | — | — | — | — | dead (ladder v5 C7, v6 exits) |
| 61 | PGATE | R2-08's gate on CFM perps | — | — | — | — | — | dead (ladder v5 C5) |

## G. Additions from memo R1 (microstructure)
| # | Id | Idea | Who is forced or eager; why we are paid | Data | Path | M T L N C | Score | Status |
|---|---|---|---|---|---|---|---|---|
| 62 | IMP | Was the drop paid for by selling? Residual drop ÷ square-root-law impact of the net aggressive selling | Flow-explained impact of forced selling relaxes; a drop the flow can't explain is quote revision on information (about ⅔ stays) | Parent prints + candles, all eras | A | 3 3 2 2 2 | 12 | **BUILD** |
| 63 | HLF | Hyperliquid forced-flow label: liquidation fills and OI change during the dislocation | Liquidated longs, observed directly | HL node data / paid indexers | A | 3 0 2 2 2 | 9 | blocked (forward-collect) |
| 64 | HLL | Hyperliquid lead gate: HL mark minus Coinbase mid at the fill | Arbitrage still carrying HL liquidations | HL candles (3.5 days) | A | 2 0 2 1 2 | 7 | blocked |
| 65 | ENDO | Endogenous vs exogenous: volatility ramp before the move, Hawkes n̂, single-coin vs broad | Feedback moves relax; news moves persist (Marcaccioli et al. 2022) | Prints, candles | A | 2 2 2 1 2 | 9 | merged (SHAPE's drift, WHO's frenzy ratio, the AI's breadth features); HAWK alt |
| 66 | LPS | Liquidity-provider scarcity: Kyle λ and Roll vs 6-month medians | LPs depleted after cascades charge more | Prints | A | 2 2 2 1 2 | 9 | merged into LIQW (alt) |
| 67 | VTIME | Exits in volume time | Decay runs in volume time | Prints | A | 1 2 2 1 1 | 7 | low (exits closed in ladder v6) |
| 68 | HTWAP | Scheduled sellers: public HL TWAPs, periodic child orders on Coinbase | Announced algorithmic sellers | HL TWAP history (key) | A/B | 2 1 1 2 1 | 7 | low |
| 69 | CXL | Bid-cancellation bursts in the full feed as a rung kill switch | MMs pulling on offshore information | Full feed (no history) | A | 2 0 2 2 2 | 8 | blocked |
| 70 | MIRROR | Post-only ask ladder on CFM alt perps for short squeezes | Liquidated shorts | Spot proxy, CFM prints | B | 2 2 2 0 1 | 7 | dead (wick v2 lab: sell-the-rip mirror 0.32) |
| 71 | WKND | Weekend non-crypto perps faded toward Hyperliquid prices | Weekend hedgers in thin books | CFM index perps from Jun/Aug 2026 | B | 2 0 2 2 1 | 7 | blocked (no DEV history) |
| 72 | XMARG | Cross-margin spill-over wicks in CFM non-crypto perps on cascade days | Liquidated multi-asset accounts | Same | B | 2 0 2 2 1 | 7 | blocked |
| 73 | BRRNY | Liquidity to predicted ETF flow in the 3–4 pm benchmark hour | ETF issuers/APs on BRRNY | Candles, ETF flows | B | 1 2 2 1 1 | 7 | merged (LETF; NAV dead after in-kind) |

## The ten builds
| Build | Path | Category | Score | Builder |
|---|---|---|---|---|
| IMP | A | microstructure (impact) | 12 | builder 3 |
| WHO | A | microstructure (order flow) | 11 | builder 1 |
| EXH | A | microstructure (order flow) | 10 | builder 1 |
| MAC | A | events | 11 | builder 2 |
| BURN | A | statistics / adaptive | 11 | builder 2 |
| SHAPE | A | statistics (path shape) | 11 | builder 3 |
| GAMMA | A | options (dealer gamma) | 11 | builder 4 |
| EXP | B | options / settlement flows | 10 | builder 4 |
| LETF | B | ETF flows | 11 | builder 5 |
| CROWD | A | funding / positioning | 10 | builder 5 |

73 ideas in all: 10 built, 8 next in line (alt), 7 merged into a build, 20 low power or prior, 12 blocked by data, 14 killed by earlier rounds, 2 out of scope for this account. Categories without a build (cross-venue
locality XV, liquidity withdrawal LIQW, macro overshoot MACB) are next in line.
