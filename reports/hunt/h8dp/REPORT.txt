# H8 (h8dp): depeg bids under par for stablecoins and cbETH on Coinbase. Verdict: FAILS (G1-G4)

## Mechanism
In a scare, holders sell stablecoins below par: funds de-risk, and some holders cannot wait for redemption. Resting
bids at par x (1 - d) buy that flow and sell at par - 5 bp after recovery. The risk is a true default. Per SPEC,
cbETH's "par" = trailing 30-day median cbETH/ETH ratio x ETH's previous-minute close.

## Data used (fetched on Actions, branch hunt/h8dp)
- **1-minute Exchange candles from each pair's start:**
  - USDT 2021-05 to 2026-11;
  - DAI 2021-01 to 2026-05-04 (delisted);
  - PYUSD 2023-08 to 2025-04 (delisted);
  - GUSD 2022-06 to 2025-05 (delisted);
  - USDS 2025-07 on;
  - cbETH 2022-08 on, plus the repo's ETH minutes.
  - UST, BUSD, MUSD, PAX and USD1 were fetched for context only.
- **cbBTC:** no Coinbase spot book. It is absent from Exchange /products (846) and Advanced Trade (929) on
  2026-11-07. EURC is excluded per SPEC.
- **Prints for every candidate fill window** (at least one tick below par - 10 bp):
  - TradeFetcher for USDT (1,601 DEV windows), DAI (1,700) and cbETH (58,673);
  - full Exchange history for PYUSD (528K prints), GUSD (85K) and USDS.
  - Coverage is 100% of candidate minutes in scored years.
- **Fees** (reports/hunt/research/R3_plumbing.md, Nov 6 2026, citing a third-party table from Aug 2026; unverified,
  since the official page needs a sign-in):
  - fx_stablecoin pairs (DAI, PYUSD, GUSD, USDS): 0% maker, 0.45 bp taker;
  - USDT and cbETH: VIP 1 (6 bp maker / 12.5 bp taker).
- **high_bid_limit_percentage** = 0.03 caps limit buys above the market, so it does not bind bids under par
  (inferred; the docs page was unreachable).
- **USDS** is limit-only today, which is compatible with post-only orders.

## Depeg episodes
Episodes are lows at least 50 bp under par, merged across gaps of under 24 h. Recovery is the first close at or
above par - 5 bp. The full list is in episodes_all.csv.

| Pair | Start | Depth | Minutes ≥50 bp under | Minutes ≥200 bp under | Recovery |
|---|---|---|---|---|---|
| USDT | 2022-05-11 (LUNA) | 590 bp | 1,111 | 117 | 41 h |
| USDT | 2022-11-09 (FTX) | 288 bp | 269 | 18 | 56 h |
| USDT | 2025-10-06 | 191 bp | 6 | 0 | 0.4 h |
| USDT | 2026-06-08 (HOLD) | 170 bp | 9 | 0 | 2.6 h |
| DAI | 2023-03-10 (SVB) | 1,418 bp | 2,456 | 1,801 | 97 h |
| GUSD | 2022-07-10 | 880 bp | 37 | 4 | 197 h |
| GUSD | 2023-03-11 (SVB) | 400 bp | 131 | 45 | 100 h |
| UST | 2022-05-07 | 9,795 bp | 26,788 | 25,448 | never |

- Episodes of at least 50 bp: USDT 42, DAI 68, GUSD 51, PYUSD 29, USDS 18, cbETH 364.
- Most are 1-10 minute wicks. There are about three independent stress events (LUNA, FTX, SVB) in 5.5 years.
- USDT has sat 10-15 bp under par since mid-2026.

## Trials
Eight DEV trials, all logged. Basis: sleeve $30K at 2x costs, theta 0.5. A fill is a rung round trip.

| Variant | DEV sleeve Sharpe | DEV alpha t | Fills | Lots | DEV P&L |
|---|---|---|---|---|---|
| usdt, shallow, tp | -9.30 | -12.62 | 401 | 928 | -$5,568 |
| usdt, shallow, tp7 | -9.35 | -12.75 | 404 | 928 | -$5,752 |
| usdt, deep, tp | -2.78 | -4.88 | 38 | 74 | +$1,310 |
| usdt, deep, tp7 | -2.78 | -4.88 | 38 | 74 | +$1,308 |
| all, shallow, tp | -8.12 | -9.90 | 9,746 | 108,144 | -$82,635 |
| all, shallow, tp7 | -8.13 | -9.92 | 9,787 | 107,964 | -$82,793 |
| **all, deep, tp** | **0.70** | **1.90** | **3,325** | **19,555** | **+$7,674** |
| all, deep, tp7 | 0.70 | 1.89 | 3,334 | 19,040 | +$7,658 |

- **Shallow rungs lose:** USDT and cbETH pay 24 bp a round trip at 2x, against 5-40 bp captured.
- **cbETH's 10 bp rung** fills on every one-minute ETH drop against a stale par.

## Frozen variant
- **Variant:** all, deep, tp.
  - Bids 50/100/200 bp under par on USDT, DAI, PYUSD, GUSD, USDS and cbETH.
  - Cash is split equally across the pairs listed that day and across the rungs.
  - Exit: post-only sale at par - 5 bp only.
- **Selection rule:** the highest DEV alpha t with at least 20 fills.
- **Freeze commit:** 0b70ec7 (code 0b8bb8f). HOLD was read once afterwards.

## Gates (Path B, 2x costs; a = 0.7 chosen on DEV; fixed prints)
| Gate | Value | Result |
|---|---|---|
| G1: full-period alpha t | 1.55 (DEV 1.90) | FAIL |
| G2: HOLD alpha t | -3.09 | FAIL |
| G2: HOLD book gain | -0.51 (3.13 vs 3.64) | FAIL |
| G3: full-period book gain | -0.02 (2.446 vs 2.466) | FAIL |
| G4: DSR | 0.00 | FAIL, provisional |
| G5: book by year | 2022 +11.0%, 2023 +23.4%, 2025 +23.1%, 2026 +11.8% | PASS |

- **G4:** the ledger's v_z is 146, inflated by another idea. With the floor v_z the DSR is 0.86. The coordinator
  recomputes it.
- **1x costs (information):**
  - a = 0.5;
  - full alpha t 2.89, DEV 3.18, HOLD -2.53;
  - full book gain +0.39, HOLD book gain -0.93.
- **theta = 0.25:** full alpha t 1.19, HOLD -3.11.
- **Path A:** not applicable. The sleeve's Sharpe is 0.44 against the incumbent's 2.47.

## Years
Sleeve return on $30K at 2x:

| Year | Total | Stablecoins | cbETH |
|---|---|---|---|
| 2022 | +7.1% | +$481 | +$1,648 |
| 2023 | +32.7% | +$561 | +$9,247 |
| 2025 | -12.2% | +$412 | -$4,057 |
| 2026 | -4.8% | +$214 | -$1,643 |

- At 1x: +10.9%, +43.8%, -5.8%, -1.9%.
- HOLD: -2.8% (-$828; USDT +$130, cbETH -$957; 132 fills).
- All scored days: 3,461 fills, 19,945 lots.
- **Stablecoins earn about $345 a year (1.1% of the sleeve), below T-bills (3.7%).**
- **The DEV edge was cbETH discounts in 2022-23** (FTX, SVB, pre-Shapella illiquidity). It turned negative in
  2025-26.
- Top-3 days are 44% of P&L. Correlation with the incumbent is -0.18. On the incumbent's 10 worst days the sleeve
  lost 2.5%.

## Capacity actually filled
- Time-weighted deployment is 3.1%: the ladder is idle about 97% of the time.
- Stablecoin rungs fill completely in USDT and DAI events ($5K-$25K per episode).
- At theta = 0.25, total bought falls from $8.82M to $7.36M.

## Fill-realism checks
- **Entries:** fills only on prints at least one tick through the bid; size ≤ theta x through-volume.
  - Rungs share sellers by the wick1m rule.
- **Exits:** prints at least one tick above the ask, with no same-minute round trips.
- **Latency:** levels use information at least 1 minute old.
- **Trade side:** the Exchange `side` is the maker side (tick test). The fetcher's initial taker assumption was fixed
  before use.
- **Delistings:** DAI, GUSD and PYUSD are liquidated at their last close at market costs.

## Power calculation
- **Frozen variant:** over 1,404 days (daily standard deviation 0.27%), t = 3 needs an 11.5% a year sleeve return.
  It made 6.0%.
- **Stablecoins only (usdt, deep):** it needs 5.2% a year, i.e. about 36 active days a year against 6.4 observed.
- **Structural ceiling:** about 3 independent events cap t near √3 ≈ 1.7, even with identical payoffs and no
  T-bill hurdle.
- **Conclusion:** a stablecoin depeg sleeve cannot reach G1 on Coinbase's history.

## Worst case: no recovery (UST stress; described, not traded)
- **UST did trade on Coinbase** (UST-USD, 2021-08-12 to 2022-05-27), contrary to the SPEC.
- **Deep ladder at $10K a rung:** every rung fills on May 7-9, 2022 (at least $0.4M an hour of selling).
  - Take-profit-only exit: -96.7% of the sleeve.
  - 7-day exit: -85.9%.
  - The candle-rule simulation shows -31% / -26%, understated because gapped minutes don't fill.
- **Survivorship:** the universe is survivors chosen in 2026. One default erases about 85 years of the stablecoin
  premium.

## Weaknesses
1. The edge is cbETH relative value, not depegs. It decayed and lost on HOLD.
2. The strategy is short the default tail, and the universe has survivorship bias.
3. Stable-pair fees are unverified. VIP 1 on USDT kills shallow rungs.
4. Idle cash earns nothing while the gates subtract T-bills.
5. The marked-to-market maximum drawdown is -11.1% of the sleeve.
6. cbETH needs a re-quote every minute, and its stale-par fills are adversely selected.

## Scorecard: 38/100
| Criterion | Points |
|---|---|
| Out-of-sample | 0/20 |
| Statistical strength | 3/20 |
| Robustness | 5/15 |
| Fill and cost realism | 13/15 |
| Mechanism | 4/10 |
| Implementability | 9/10 |
| Diversification | 3/5 |
| Capacity | 1/5 |

## Deviations (before the freeze unless noted)
- cbBTC is omitted.
- Stable-pair fees follow R3; USDT and cbETH use VIP 1.
- GUSD's market half-spread is 5 bp (half its tick).
- Engineering choices:
  - the wick1m seller sharing;
  - candle exits without the open condition (outside print windows only);
  - full Exchange history for PYUSD, GUSD and USDS.
- A fill is a rung round trip.
- The UST stress was computed analytically.
- Post-freeze: episodes_all.csv, the checks, and the fetcher fix below. The variant is unchanged.

## Fetcher paging fix (post-freeze; frozen variant re-run once)
- **The bug:** shared TradeFetcher lost prints when a page boundary split a second (fixed in 06b7052).
- **Windows hit:** 431 USDT DEV windows (58K ids), 107 USDT HOLD windows (2.7K), 13 DAI and 115 cbETH windows.
  These are exactly the windows my trade-id gap check had flagged.
- **Fix:** they were re-fetched, recovering 97% of the missing USDT ids and all of DAI's.
- **Before → after (2x):**

| Measure | Before | After |
|---|---|---|
| Full alpha t | 1.549 | 1.546 |
| DEV alpha t | 1.900 | 1.899 |
| HOLD alpha t | -3.087 | -3.087 |
| Full book gain | -0.020 | -0.020 |
| HOLD book gain | -0.514 | -0.514 |
| Fills | 3,457 | 3,461 |
| DEV P&L | $7,674 | $7,690 |
| HOLD P&L | -$828 | -$828 |

- Every gate verdict is unchanged. Files: fetchfix_compare.csv and *_prefix.
- The DEV grid was not re-run. Selection used the pre-fix data, where tp led tp7 by 0.012 in t.

## Verdict
**FAILS (G1, G2, G3, G4).**
- Depeg bidding on Coinbase is crisis-liquidity insurance with a short default tail, not alpha. It sees about three
  real events in 5.5 years, earns below T-bills, and survivorship hides the UST loss.
- The only positive DEV signal (cbETH discounts) was a 2022-23 artifact that reversed out of sample.
- Do not carry it to wave 3.
