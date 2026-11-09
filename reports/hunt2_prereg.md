# Edge hunt 2: a desk-style round against R2-08 (pre-registration)

Frozen 2026-11-09 (UTC), before any hunt-2 build or test. The freeze point is the commit that changed this line
from DRAFT to frozen; its hash is recorded in reports/hunt2/frozen_prereg.txt. Drafts committed before it bound
nothing. Deviations after the freeze go in the log at the bottom, with a reason and a time.

## Goal (Miles, Nov 8 2026, ET)
Think like researchers from HRT (microstructure), SIG (options, game theory) and Renaissance (many weak signals, one
model), limited to one New York retail Coinbase Advanced account: spot plus Coinbase Financial Markets (CFM) US perps,
REST/WebSocket, 30 requests/s, no colocation or rebates, about $250K. Beat R2-08, the AI-filtered 4/6/8σ dip ladder.
Mine Harris; Bouchaud et al.'s *Trades, Quotes and Prices*; Cartea–Jaimungal; López de Prado; Isichenko; Carver;
SSRN and arXiv q-fin; Quantpedia; Kaiko; Quant StackExchange and Wilmott. Generate 50+ ideas spanning microstructure,
events, cross-venue, basis/funding, volatility, flow and ML, each naming who is forced to trade and why we are paid.
Build the best 10 on trade data. Pre-register, freeze, read the hold-out once. Pass only at 2x costs: paired t >= 2
vs R2-08 or +0.5 book Sharpe, no losing year. Rank on a 100-point scorecard.

## What has been looked at already (honest accounting)
- **The incumbent** was selected with the Apr–Nov 2026 check era read (wick v2 lab) and confirmed on 2022–23 (wick
  v3). Ladder v5 and v6 read both eras for the incumbent and for their frozen candidates (C2a, C3, C4, X2 exits).
  The incumbent's performance in every era is known; that is fine, it is the benchmark.
- **The first edge hunt's HOLD (Jun 1 – Nov 5 2026) lies inside this round's check era.** Its 13 mechanisms were
  read there. Hunt-2 ideas are new mechanisms, or new information for the ladder, so their statistics are unread.
- **Seen before this file, and named where it motivates an idea:** ladder v5's fill-minute print diagnostics on the
  selection era (sweeps, taker-sell share, first-sweep depth); ladder v6's selection-era markouts of unsold
  remainders (−71 bp at minute 60, −117 at 120) and its hold-past-60 rule read once out of sample; the execution
  round's daily-loss-limit result; the wick v4 post-hoc lead that fills with BTC flat are the weakest (seen in every
  era, so it is NOT used as an idea here). Input data downloaded for this round (prints around parent fills,
  Deribit option trades, ETF prices, calendars) has had no statistic computed on it except coverage counts and, for
  the DEV era only, the quartiles of the parent print features (no outcomes). The incumbent's ten worst and best DEV
  days were looked at (its own DEV series).

## The incumbent (benchmark)
- **What:** the live spot bot (bot/spot): R2-08's signal, the 4/6/8σ ladder in thirds, each signal capped at 0.2% of
  ADV, every AI signal, cash ≤ 100%, 1-second detection of deeper fills, at $250K.
- **Simulator:** ladder v6's frozen one (scripts/ladder_v6x/lsim.py): the engine-faithful cash rule, print-measured
  exit costs, the 1-second blend of the two latency bounds, today's volumes. Wrapped, unchanged, by
  scripts/hunt2/frozen_sim.py; reproduced exactly (difference 0.0) in every era.
- **Cost settings:** **S** = the incumbent's best estimate (ladder v5/v6: unverified model costs ×2, published fees
  ×1, print-measured exit costs ×1); **X1** = every cost term at its realistic value; **X2** = every cost term doubled
  (fee tiers ×2, model half-spread and impact ×2, print-measured exit costs ×2).
- **Series:** reports/hunt2/incumbent_daily.parquet (scripts/hunt2/incumbent.py), at $250K for S, X1, X2 and θ 0.25,
  and at $225K, $200K, $175K and $125K for S (the Path B books).

| $250K, θ 0.5 | sel (DEV) | chk (HOLD) | early (HOLD) |
|---|---|---|---|
| S | 22.79% / 2.94 | 19.05% / 2.66 | 11.14% / 1.91 |
| X1 | 22.83% / 2.94 | 19.07% / 2.66 | 11.14% / 1.91 |
| X2 | 13.82% / 1.62 | 12.60% / 1.61 | 7.83% / 1.13 |

Calendar years at X2: 2022 +6.8%, 2023 +8.9%, 2025 +15.6%, 2026 YTD +9.2%.

## Windows
- **DEV** = the selection era, 2025-01-01 .. 2026-03-31 (455 days). Every design, parameter, threshold and model
  choice uses DEV only.
- **HOLD** = the check era 2026-04-01 .. 2026-11-05 (219 days) and the early era 2022-01-01 .. 2023-12-31 (730
  days): 949 days, read once per idea, after a commit that freezes that idea's variant (reports/hunt2/<id>/frozen.json).
- 2021 and 2024 may train models; they are never scored.
- Downloads may cover HOLD dates. Before an idea's freeze, no statistic, fill count, P&L, trade list, feature
  distribution or feature–outcome relation on HOLD days may be computed, printed or committed.
- **Ideas whose inputs start later** are scored on the days where they exist. An era counts for the per-era gates
  (A3, B3) only if the idea has at least 60 scored days and 10 events in it; otherwise it is reported, not gated.

## Cost model
- **Path A** (modifications of the live bot): only through the frozen simulator, at X2 for selection and gates, X1 for
  gate A2, S reported.
- **Path B** (sleeves): scripts/hunt2/costs.py. Spot (unchanged from the first hunt): VIP 1, 0.06% maker / 0.125%
  taker (the shared account reaches it), plus a 2 bp half-spread on market orders. Perps, from the documented fee
  structure (research memo R4): a flat **$0.15 per contract per side** (exchange $0.10 + NFA $0.01 + clearing) **plus
  Coinbase's commission, taken as 2 bp per side for maker and taker alike**, plus 1.5× the measured median
  half-spread on market orders; funding 1 bp per 8 h either side; contracts worth ≥ $150 only. **2× = every term
  doubled; every gate is at 2×.** 1× is reported.
  - Per side at Nov 8 prices, taker 1× / 2×: BTC 5.0 / 10.0 bp, ETH 12.4 / 24.9, SOL 8.0 / 15.9, XRP 6.6 / 13.2.
  - Against the first hunt's $0.20 per contract this is dearer for BTC, SOL and XRP and about equal for ETH. Coinbase's
    retail commission tier is still unverified; one order preview settles it.

## Fill and latency rules
- **Resting orders:** fill only on a print (or candle) strictly beyond the level by at least one tick; size ≤ θ × the
  volume beyond the level while the price stays beyond it (prints where available; candles spread volume evenly over
  each minute's range); θ = 0.5, 0.25 reported.
- **Taker orders:** the first print ≥ 2 s after the decision (candles: the next minute's open), worse by 1.5× the
  half-spread, plus the fee.
- **Latency:** decisions use information ≥ 1 s old (prints) or ≥ 1 minute old (candles).
- **Live inputs only:** Coinbase (spot, perps), Bitstamp, Kraken, Gemini, Hyperliquid's info API, Binance announcement
  pages, official calendars (BLS, Federal Reserve, exchange expiry rules), US ETF prices and volumes. Binance, Bybit
  and OKX market data are research context only.
- **Coinbase trade side** is the maker's side ("BUY" = an aggressive seller hit a bid).

## Gates (scripts/hunt2/h2gates.py; nobody re-implements a test)
**Path A, beat R2-08 head-to-head** (a modification of the live bot at $250K on the frozen simulator):
- **A1:** HOLD paired Newey–West (5 lags) t ≥ 2 of the daily difference, candidate − incumbent, both at X2.
- **A2:** the HOLD mean difference is also > 0 at X1 (the gain is not an artefact of doubled costs).
- **A3:** the difference is positive in every HOLD era the idea is gated in (chk, early).
- **A4:** no losing calendar year for the candidate at X2 (2022, 2023, 2025, 2026).

**Path B, add a sleeve:** book = a × incumbent(a × $250K, S) + (1 − a) × sleeve((1 − a) × $250K, 2×), with a ∈ {0.9,
0.8, 0.7, 0.5} chosen on DEV by book Sharpe; the benchmark is the incumbent with all $250K at S.
- **B1:** HOLD book Sharpe gain ≥ +0.5.
- **B2:** HOLD Newey–West t ≥ 2 of the sleeve's alpha on the incumbent (so the gain is not noise).
- **B3:** the book gain is positive in every HOLD era the idea is gated in.
- **B4:** no losing calendar year for the book.

**Reported, scored, not gated** (Miles' bar, Nov 8): the deflated Sharpe (Bailey–López de Prado) with N = 4,500
prior trials + every hunt-2 trial and the first hunt's null-dispersion rule; the 1× results; θ 0.25.

**Red team:** a separate agent reviews any idea that passes A1–A4 or B1–B4 (look-ahead, fills on prints, costs
against published fees, capacity, trial count, overlap with the incumbent, gate arithmetic). A bug is fixed and the
frozen variant re-run once; no redesign after reading HOLD.

## Trial accounting and selection
- Every DEV configuration scored is a trial, logged in reports/hunt2/trials.csv (h2gates.log_trial): Path A logs the
  candidate's DEV series at X2 and its DEV paired t; Path B logs the a = 0.8 DEV book and the DEV alpha t.
- Budget: each idea's SPEC grid, never more than 16 trials; at most 160 in the round.
- Selection inside an idea (fixed): the highest DEV statistic among variants with the SPEC's minimum events; ties go
  to the simpler variant. Then the freeze commit, then HOLD once.
- AI variants (LightGBM) are walk-forward: trained only on data before each test quarter, with at least 6 months of
  history before the first scored quarter; they count as trials.

## Multiple testing and combinations
- Eight Path A filters are read on the same HOLD. Under the null each has about a 2.3% chance of t ≥ 2, so about
  0.2 false passes are expected across the eight; a single pass just above t = 2 is weak evidence on its own. The
  deflated Sharpe (N = 4,500 + every hunt-2 trial) and the scorecard report this; the red team checks any pass.
- No post-hoc combination is a pass. If two or more Path A builds pass every gate, their union (skip when any of
  them fires) is computed once and reported as descriptive, because which filters to combine was chosen on HOLD; a
  combined candidate needs its own pre-registered test on new data.

## Scorecard (weights fixed now; 100 points; scripts/hunt2/scorecard.py)
| Criterion | Points | Full marks |
|---|---|---|
| Out-of-sample (HOLD, read once) | 25 | A: HOLD t ≥ 2 (15 if ≥ 1; 7 if > 0). B: gain ≥ +0.5 and t ≥ 2 (15 if ≥ +0.25 and t ≥ 1; 7 if > 0) |
| Statistical strength | 15 | DEV statistic ≥ 3 (5; 3 if ≥ 2; 1 if ≥ 1); deflated Sharpe ≥ 0.95 (5; 3 if ≥ 0.8; 1 if ≥ 0.5); every gated HOLD era positive (5) |
| Robustness | 15 | Every year positive at 2× (5); neighbouring settings agree in sign (5); HOLD top-5 days < 50% of the gain (5) |
| Fill and cost realism | 15 | Trade-verified fills or features (6); live-speed latency (3); volume-capped capacity (3); costs vs published fees (3) |
| Mechanism | 10 | Named forced/eager counterparty (4); evidence it persists (3); capacity-limited, so big funds pass (3) |
| Implementability | 10 | Inputs live in the US (4); Coinbase order types (3); low operational complexity (3) |
| Diversification / fit | 5 | A: helps the incumbent's 10 worst DEV days (5). B: correlation with the incumbent < 0.2 (3) and positive on its 10 worst days (2) |
| Capacity at $250K | 5 | A: no loss of the incumbent's capacity (5). B: deploys its allocation at θ 0.25 (5; 2–3 if partly) |

The gates decide pass or fail; the score ranks and explains. Hand-scored parts go in reports/hunt2/scorecard_manual.json
with a reason for each.

## Ideas
The full list (73 ideas), its scoring rubric (prior 0–12: mechanism, testable on trade data, live from New York, new, clears 2×
costs) and every score are in reports/hunt2/ideas.md, fixed with this file. Research memos: reports/hunt2/research/
(R1 microstructure, R2 options/events/flows, R3 ML/statistics, R4 venue facts).

**The ten builds** (the ten highest scores; ties to Path A, then to category coverage). Each SPEC
(reports/hunt2/<id>/SPEC.md) is fixed with this file and binds its build:

| Build | Path | Mechanism in one line | Data (trade-level part) | Trials |
|---|---|---|---|---|
| WHO | A | Skip fills whose pre-fill selling looks informed: blocks, low aggressor share, concentration, slow drift | Coinbase prints, 30 min before every parent fill, all eras | 16 |
| EXH | A | Skip fills that arrive while aggressive selling is still at its peak, or before much forced volume has traded | Same prints | 8 |
| MAC | A | Pull the ladder around CPI/NFP/PPI/FOMC releases (information, not forced flow) | Official calendars; parent prints for fill times | 6 |
| BURN | A | After a coin's ladder fails to rebound, skip that coin (or the market) for hours | The frozen dataset's own outcomes | 12 |
| SHAPE | A | Skip dislocations that arrive as a grind (high path efficiency, no air pocket, multi-hour drift) | Coinbase 1-minute candles, all eras | 8 |
| IMP | A | Skip fills whose residual drop is larger than the square-root-law impact of the net aggressive selling (quote revision on information, not forced flow) | Same prints + candles | 8 |
| CROWD | A | Skip bids when perp funding says shorts, not longs, are crowded (no forced long liquidation) | Hyperliquid daily funding, 2023-05 .. | 8 |
| GAMMA | A | Skip bids while option dealers are net short gamma (they sell into falls) | Every Deribit BTC option trade from 2021 (dealer inventory) | 8 |
| LETF | B | Trade the leveraged-ETF rebalancing flow into CME's 4 pm settlement, and provide liquidity to it | Coinbase candles and prints 15:44–17:01 ET, ETF data, CFM perps | 12 |
| EXP | B | Trade the dealers' predicted hedge unwind in Deribit's Friday 08:00 UTC settlement window, or fade it after | Deribit option trades, Coinbase candles and prints, CFM perps | 12 |

Total budget: 98 DEV trials. Next in line if a build is blocked (score 9, Path A first, buildable on this
simulator): XV, LIQW, HAWK, TSC, ONE, then MACB.

## Deviation log
- **2026-11-08 20:15 ET, shared feature file, before any IMP trial (found by the IMP builder on DEV, no outcomes
  used).** scripts/hunt2/parent_features.py computes `ret_bp_W` and `dist_lvl_bp_W` on prints stored newest-first (the
  Exchange-API fetcher walks backward), so `ln(1 + ret_bp_W/1e4)` is exactly minus the window's log return and
  `dist_lvl_bp_W` uses the window's oldest print, not its latest. Every other feature is order-free (orders are
  re-sorted; `t_fill` is a minimum; sums, min/max, the 1-second EWMA grid, and Roll's lag-1 autocovariance are
  unchanged by reversal). The shared code is left as it is, so the DEV and HOLD files keep one convention; IMP uses
  `r_W = -ln(1 + ret_bp_W/1e4)`, which is exact. No other build uses either feature. To be fixed in the code after
  the round, with the files regenerated.
- **2026-11-08 21:40 ET, scorecard only, after every HOLD read (no gate is affected).** For Path B the scorecard's
  deflated Sharpe and "every year positive" are read on the sleeve itself (at the capital the gate chose), not on the
  book: the book is at least half incumbent, so its deflated Sharpe (EXP 0.82) and its calendar years scored the
  incumbent, not the idea. This lowers EXP from 39 to 31 and LETF from 39 to 34; no other score moves.
- **Operations, all builders (Nov 8 evening).** The shared machine's memory limit (6.26 GB for every builder) killed
  eight HOLD-read processes (SHAPE 1, BURN 2, CROWD 2, GAMMA 1, WHO 1, EXH 1). None had written or shown a gate, series or P&L except WHO's, which had already written its
  outputs when it was killed; each idea's single read is the one committed, and its DEV slice reproduces the logged
  DEV trial exactly (reports/hunt2/central_checks.json). The instructed HOLD-feature dispatch could not commit
  (parent_features.py rewrites tracked files, so the workflow's pull --rebase refused and the step still ended
  green); flow and shape re-ran the unchanged script into a fresh folder, and both runners regenerated the committed
  DEV file byte for byte. The options builder's pre-freeze derive uploaded no artifact (the workflow passes a
  space-separated artifact list as one path); its HOLD files were rebuilt after both freezes from the same raw trades,
  with the DEV outputs identical by SHA-256.
- **Shared-code notes for later rounds.** (1) A skipped parent still keeps its coin busy until its take-profit or
  fill + 61 minutes, so a later same-coin parent that live trading could take is lost; at most 2.3% (DEV), 0.5% (chk)
  and 2.4% (early) of parents follow a still-busy same-coin parent, and only those whose predecessor a filter skipped
  are affected. (2) h2gates.path_b's B3 counts every era with a scored day; the 60-day / 10-event rule above was
  applied by the builders and changes no verdict. (3) Gate B2 books idle sleeve capital at 0%, which dominates the alpha
  t of a sleeve that trades a few days a year (EXP -10.2; -2.1 with idle cash at T-bills). (4) pathA.mult_for drops
  cells it cannot place without an error; every build asserted its cells, and every filter changed the result in every
  era. (5) prints.py cannot save a file that mixes spot and perp trade ids. (6) ex_peak tops out at 0.9885, not 1.
