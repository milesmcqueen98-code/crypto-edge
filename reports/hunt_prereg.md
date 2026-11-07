# Edge hunt: new mechanisms for a $100K book (pre-registration)

Written 2026-11-07 (UTC) before any wave-2 build or test. The commit that adds this file is the freeze point; its hash
is recorded in reports/hunt/frozen_prereg.txt. Deviations go in the log at the bottom, with a reason and a time.

## Goal (Miles, Nov 6, ET)
Build the highest-Sharpe, AI-aided crypto book that can run with $100K on Coinbase spot and Coinbase US perps. Hunt
edges too small for big funds: who is forced (or eager) to trade, and why a small liquidity provider is paid.

- **Bar:** beat R2-08 head-to-head, or add at least 0.5 to the combined Sharpe; no losing year.
- **Pass:** paired t ≥ 3, deflated Sharpe counting every trial (~3,000 prior), at 2× costs.
- **Dead without a new mechanism:** two-sided quoting, daily signals, regime/pattern models, stat-arb, seasonality,
  carry, AI direction calls.

## What has been looked at already (honest accounting)
- Every era of Coinbase spot minute data (2021–2026) has shaped some wick-catcher choice. That matters for anything
  that re-uses the wick catcher's trigger. The ideas below use different triggers, venues or universes. None of their
  statistics has been computed on any period before this file was committed.
- Perp-priced replays of R2-08 (wick_futures, lab futures check) were seen for Dec 2025 – Nov 2026. They showed big
  perp-only wicks, 61% of AI futures trades, mostly where spot never reached the level. That observation motivates
  idea H1, so H1's level rule is fixed below from those earlier choices (4σ-style depth, 60% take-profit, 60-minute
  hold). It gets no extra tuning freedom for having been seen.
- Wave 1 looked only at:
  - data-source metadata (reports/hunt/probe.json, probe2.json): which endpoints work and how far back;
  - the perps' trading-hour pattern on DEV days (weekly Friday 5–6 pm ET halt).

  No returns were computed.
- **Research memos (reports/hunt/research/R1–R4)** were still being written when this file was frozen.
  - Facts in them that change a cost or rule before any build result is seen are applied as logged deviations.
  - They do not re-rank the eight builds.

## The incumbent (benchmark)
- **What:** the spot bot as it trades (bot/spot), at $100K.
  - R2-08 signal, with the $1M rules: 4/6/8σ ladder in thirds, each signal capped at 0.2% of ADV, every AI signal,
    cash ≤ 100%.
  - Coinbase spot only: perp volume removed from fill capacity. VIP tiers from its own volume. θ = 0.5.
- **Which bound:** the **instant** bound, which keeps every same-minute deeper fill. It is the stronger of the live
  bot's two bounds, so every comparison is conservative.
- **Data:** daily returns in reports/hunt/incumbent_daily.parquet (scripts/hunt/incumbent.py, regenerated today).
- **Days scored:** 2022-01-01 – 2023-12-31 and 2025-01-01 – 2026-11-05, the days with out-of-sample R2-08
  predictions. 2024 trained the R2-08 model and is never scored.
- **Results (incumbent at $100K):**

| Era | Return/yr | Sharpe |
|---|---|---|
| 2022–23 | 18.3% | 2.51 |
| Jan 2025 – Mar 2026 | 35.3% | 2.60 |
| Apr – Nov 2026 | 22.4% | 3.06 |
| All scored days | — | 2.47 |
| DEV window (before Jun 1 2026) | — | 2.35 |
| HOLD window (Jun 1 – Nov 5 2026) | — | 3.64 |

  - Calendar years: 2022 +15.6%, 2023 +21.0%, 2025 +38.7%, 2026 YTD +18.8%.

## Windows
- **DEV:** every scored day before 2026-06-01. A design, parameter or model choice may use only DEV days. 2024 may
  train models, but is never scored.
- **HOLD:** 2026-06-01 – 2026-11-05. Each idea reads it once, for its single frozen variant, after a commit that
  freezes that variant (reports/hunt/<id>/frozen.json). Data downloads may cover HOLD dates. No statistic, fill
  count or P&L on HOLD days may be computed before the freeze commit.
- **Short histories:** an idea whose data starts later (e.g. US perps from Jul 2025 or Dec 2025) is scored on the
  scored days where it exists. Its book is compared with the incumbent on the same days.

## Cost model (scripts/hunt/common.py)
- **Spot:** VIP 1, 0.06% maker / 0.125% taker. The $100K book reaches that tier in about two weeks. Market orders
  also pay a 2 bp half-spread.
- **Perps:** $0.20 per contract per side, maker or taker (exchange plus FCM estimate). Market orders also pay 1.5× the
  measured median half-spread (reports/cfm_book_summary.csv). Funding: 1 bp per 8 hours, charged either side.
- **2× stress:** every fee, spread and funding term doubled. **All pass tests are computed with the candidate at 2×
  costs**, against the incumbent at 1×. Results at 1× are reported for information only.
- **Perp universe rule:** a contract worth at least $150 at the time of the trade. Below that, per-contract fees
  exceed about 13 bp a side; AVAX and DOT perps fail today.

## Fill and latency rules
- **Resting orders (candles):** fill only if the minute opened beyond the level and then traded through it by at
  least one tick. Size ≤ θ × the volume estimated to trade through the level (each candle's volume spread evenly
  over its range), θ = 0.5, with 0.25 also reported.
- **Resting orders (trades):** where trade prints are used, size ≤ θ × the volume of trades strictly beyond the
  level while the price stays beyond it. Volume at the level itself is ignored (queue position unknown).
- **Latency:** levels and orders use information at least 1 second old (trade-level) or 1 minute old
  (candle-level).
- **Taker entries and market exits:** priced at the first trade at least 2 seconds after the decision, made worse by
  1.5× the half-spread. With candles only: the next minute's open, made worse the same way.
- **Coinbase trade side:** `side` is the maker's side. "BUY" means an aggressive seller hit a resting bid
  (reports/hunt/probe2.json).
- **Live inputs only:** every model input must be obtainable live by a US-based bot. Allowed: Coinbase spot and
  perps, Bitstamp, Kraken, Gemini, Hyperliquid's public info API, and Binance's announcement pages. Binance, Bybit
  and OKX market data are geo-blocked for US clients, so they may inform research but may not be signal inputs.

## How a sleeve is scored (scripts/hunt/gates.py; nobody re-implements a test)
**Path B, add a sleeve:**
- The book is a × incumbent(a × $100K) + (1 − a) × sleeve((1 − a) × $100K). The sleeve is at 2× costs.
- a ∈ {0.7, 0.5} is chosen on DEV by book Sharpe.
- The benchmark is the incumbent with all $100K.

**Path A, replace R2-08:**
- The candidate runs on $100K. It is scaled to the incumbent's DEV volatility for the paired test.

**Gates (all must hold):**
- **G1:** HAC (Newey–West, 5 lags) t ≥ 3 over all scored days.
  - Path B: t of the sleeve's alpha on the incumbent (spanning test).
  - Path A: t of the daily return difference.
- **G2:** HOLD, read once.
  - Path B: t ≥ 1.5, same sign, and book Sharpe gain ≥ +0.25.
  - Path A: t ≥ 1.5, and the candidate's Sharpe is above the incumbent's.
- **G3:** all scored days.
  - Path B: book Sharpe gain ≥ +0.5.
  - Path A: candidate Sharpe above the incumbent's.
- **G4:** deflated Sharpe of the book (or candidate) ≥ 0.95.
  - N = 3,000 prior trials + every trial in reports/hunt/trials.csv.
  - Null dispersion v_z / T, where v_z = max(1.126, variance of z = daily Sharpe × √days across the ledger's
    trials). 1.126 is the wick v2 lab's 139 trials.
  - This puts every trial on the track record's own length.
- **G5:** no losing calendar year for the book on its scored days.
- **G6:** the red team (below) finds no disqualifying error, or the fix is re-run and the gates still hold.

**Trial accounting:**
- Every configuration scored on DEV is a trial and goes into reports/hunt/trials.csv (gates.log_trial).
- What is logged is the DEV book at a = 0.7, the sleeve at 2× costs.
- Budget: at most 24 DEV trials per idea in wave 2.

**Selection inside an idea (fixed):**
- Among DEV trials with at least 40 trades (20 events for event ideas), the variant with the highest DEV alpha t
  (sleeve at 2× costs on the incumbent at $70K).
- Ties go to the simpler variant.
- Then freeze, then read HOLD once.

**AI:**
- Ideas may add a LightGBM filter or sizer. It is walk-forward: trained only on data before each test quarter, with
  at least 6 months of history before the first quarter it scores. Features must be known at decision time.
- The AI variants count as trials.

## Red team (G6)
A separate agent reviews every idea that passes G1–G5, before Wave 3, covering:
- look-ahead, survivorship and fill realism (re-checked on trade prints where available);
- the cost model against published fees, and capacity;
- data snooping and the trial count;
- overlap with the incumbent;
- the gate arithmetic.

Bugs are fixed and the frozen variant is re-run once. Redesign after reading HOLD is not allowed.

## Wave 3 (combination)
- Survivors join the incumbent with capital shares on the grid {0.5, 0.6, 0.7, 0.8} for the incumbent. The rest is
  split across sleeves in proportion to inverse DEV volatility.
- The share is chosen on DEV; the gates are re-applied to the combined book.
- If no idea survives, the final book is the incumbent alone ("none").

## Scorecard (weights fixed now; 100 points)
| Criterion | Points | Full marks |
|---|---|---|
| Out-of-sample (HOLD, read once) | 20 | Path B: HOLD gain ≥ +0.5 and t ≥ 2 (14 if ≥ +0.25 and t ≥ 1.5; 7 if > 0) |
| Statistical strength | 20 | G1 t ≥ 3 (10; 6 if ≥ 2; 3 if ≥ 1) and G4 DSR ≥ 0.95 (10; 6 if ≥ 0.8; 3 if ≥ 0.5) |
| Robustness | 15 | 2× costs positive every year (5); neighbouring settings agree in sign (5); top-3 days < 50% of P&L (5) |
| Fill and cost realism | 15 | Trade-verified fills (6); live-speed latency (3); volume-capped capacity (3); costs checked against published fees (3) |
| Mechanism | 10 | Named forced/eager counterparty (4); evidence it persists (3); capacity-limited, so big funds pass (3) |
| Implementability | 10 | Inputs live-available in the US (4); order types on Coinbase's API (3); low operational complexity (3) |
| Diversification | 5 | Correlation with the incumbent < 0.2 (3); positive on the incumbent's worst days (2) |
| Capacity at $100K | 5 | The sleeve deploys its whole allocation at θ = 0.25 (5; 2–3 if partly) |

The gates decide pass or fail. The score ranks and explains.

## Ideas (wave 1)
All 44 ideas, with who is forced, why we are paid, data and status: reports/hunt/ideas.md. Wave-2 builds (top 8),
each with its own fixed spec in reports/hunt/<id>/SPEC.md before it runs:
| Build | Idea | Who is forced or eager | Venue | Path |
|---|---|---|---|---|
| H1 | Perp-only wicks and rips, fills checked on trade prints | FCM liquidations, stops, short squeezes on thin US-perp books | Coinbase perps | B |
| H2 | End of forced deleveraging in BTC/ETH/SOL/XRP | Leveraged longs liquidated until exhaustion | Coinbase perps (taker) | B |
| H3 | Bids beyond estimated liquidation clusters (live proxy for Hyperliquid levels) | Clustered liquidation prices | Coinbase perps | B |
| H4 | Liquidity for new listings, first 30 days (incl. delisted) | Airdrop and early-holder dumps into empty books | Coinbase spot | B |
| H5 | Binance listing/launch announcements | Eager Binance-driven buyers; is drift left after 2–30 s? | Coinbase spot | B |
| H6 | Coinbase-specific dislocations vs Bitstamp/perp fair value | US-only sellers; slow cross-venue arbitrage | Coinbase spot | B |
| H7 | Short ahead of large token unlocks | Insiders and their hedgers | Coinbase perps | B |
| H8 | Depeg bids under par (stables, wrapped) | Panic and forced de-risking | Coinbase spot | B |

- **Path:** every build is scored on Path B (add a sleeve). Path A (replacing R2-08) applies only if a build's
  sleeve on its own beats the incumbent, and is then reported as well.
- **Specs:** each build's fixed spec is in reports/hunt/<id>/SPEC.md (h1pb, h2fr, h3lm, h4nl, h5an, h6vd, h7ul, h8dp).
  Each is written before its build starts.

## Deviation log
**2026-11-07 03:55 UTC: venue rules from research memo R3, applied to every perp build before any result existed.**
Sent to builders H1, H2, H3, H7 and H8.
- Coinbase Derivatives' Fair Value Limit rejects orders priced more than ±5% from spot fair value. A level beyond 5%
  cannot rest.
- A ±10% move from the hourly reference price triggers a 2-minute halt with no matching.
- 24x7 crypto perps halt only on Fridays, 5–6 pm ET.
- The all-in perp fee is unverified. Gates keep the pre-registered $0.20 per contract per side; $0.12 and $0.30 are
  reported for information.
- Stable pairs other than USDT pay 0% maker and ≤ 0.45 bp taker (third-party source). USDT pays standard fees.
- These are venue facts, not design choices; no trial grid changed.

**2026-11-07 04:00 UTC: wave 2b adds H9 (MC), from research memo R3, before any wave-2 result existed.**
- The mechanism: the 4:00 pm ET step from intraday to overnight margin on Coinbase US perps.
- Spec: reports/hunt/h9mc/SPEC.md. It is committed before its build starts, under the same gates, with ≤ 24 trials.

**2026-11-07 04:05 UTC: wave 2c adds H10 (XQ), from research memo R4, before any wave-2 result existed.**
- The mechanism: secondary-book wicks in Coinbase's BTC-, ETH- and USDT-quoted books, where market makers pull quotes
  first in cascades.
- Spec: reports/hunt/h10xq/SPEC.md. Same gates, ≤ 24 trials.

**2026-11-07 06:00 UTC: how G4's null dispersion is computed. Decided while no idea was in a state where G4 alone
would decide pass or fail; the three ideas finished so far (H2, H5, H7) fail G1–G3 either way.**
- **The problem:** the pre-registered v_z (plain variance of z across the ledger) is dominated by whole strategy
  families with large, truly negative Sharpes. H2's DEV books reach −4.6. With 66 trials logged, the plain variance is
  7.65, which puts the null's expected maximum Sharpe at 5.0 over 3.8 years. That measures how different the families
  are, not sampling noise under the null of no skill.
- **The fix (binding):** v_z = max(1.126, (1.4826 × MAD of z)²), a robust estimate of the same quantity. It is 1.50 on
  the current ledger.
- **Reported alongside:** the pre-registered plain-variance version, in every gate table.
- **When G4 is computed:** once, centrally, at the end, with the final ledger (N = 3,000 + every trial of every
  wave), since N keeps growing while builders run. Builder-time DSR values are provisional.

**2026-11-07 06:20 UTC: loop 2 (wave 2d) adds H11 (MJ), before its build.** H2, H3, H5 and H7 have failed and H4 is
frozen.
- The mechanism is deep, hourly-refreshed bids on the BTC/ETH/SOL/XRP perps. It comes from H3's DEV-only
  observation: random-depth bids made money even though the liquidation estimate added nothing.
- Spec: reports/hunt/h11mj/SPEC.md, ≤ 12 trials, the same gates. Its HOLD has never been computed in any form.

**2026-11-07 06:35 UTC: G4's null dispersion is estimated within each idea. Decided before H1, H8, H10 or H11 had
read its hold-out. Every finished idea (H2–H7, H9) fails G1–G3, so no verdict depends on this choice.**
- **The problem with the 06:00 rule:** ledger trials are DEV books (0.7 × incumbent + 0.3 × sleeve), each over its
  own idea's DEV days. Their z = daily Sharpe × √days carries the incumbent's true Sharpe, which grows with √days.
  - Ideas scored on all 1,246 DEV days sit near z = 3.7; perp-era ideas scored on 318 days sit near z = 2.
  - So the pooled MAD (vz 2.5–3.3 as perp-era ideas joined) measures record length, not selection noise. It would put
    the null's expected maximum at about 3.1 annualized over all days and 5.4 over the perp era.
- **The fix (binding):** subtract each idea's median z, then vz = max(1.126, (1.4826 × MAD)²). On the current ledger
  the within-idea value is about 0.5, so the lab floor of 1.126 binds.
- **Reported alongside:** the pooled robust value (06:00 rule) and the plain variance (pre-registered), in
  reports/hunt/central_gates.csv.
- **Scored days:** the central recompute uses each idea's own scored days (the index of its daily.parquet), as the
  builder guide told builders to do. It reproduced every builder's t, gain and a to within 0.01.

**2026-11-07 06:45 UTC: loop 3 (wave 2e) adds H12 (LT) and H13 (PS), before their builds.** By now H2–H7 and H9 have
failed, H11 is frozen with its HOLD unread, and H1, H8 and H10 are still running.
- **H12 (LT):** R2-08 unchanged on Coinbase's long-tail spot coins (2024 median volume $0.5–3M, tick ≤ 3 bp).
  Spec reports/hunt/h12lt/SPEC.md, ≤ 6 trials.
- **H13 (PS):** the switch from limit-only to full trading on new Coinbase listings. Spec reports/hunt/h13ps/SPEC.md,
  ≤ 10 trials.
- **Alternates not built, with reasons:**
  - SR (stop runs): H3 found structural levels add nothing over random depth, and H11 tests the random-depth version.
  - DL (delisting notices): about 10–20 batched events a year, too few for t ≥ 3.
  - IX/PX (metals and PAXG weekends): about 55 weekends.
  - FU, CM, IR: 50 events or fewer.
  - EF (ETF fixing): in-kind creations since 2025 shrink the flow.
  - TW (TWAP footprints): heavy data, prior 3.
  - Blocked: HL position history, Binance/Bybit live feeds, Upbit.
