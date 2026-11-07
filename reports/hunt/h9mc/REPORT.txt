# H9 (MC): the 4 pm ET margin step-up on Coinbase US perps

**Verdict: FAIL.** Step 1 passes both tests: the forced flow is real on DEV. But it moves the basis only 2–3 bp, against round trips of 9–40 bp at 2× costs. All 19 trading trials had a negative DEV alpha t, and the frozen variant lost on HOLD. G1–G4 fail; G5 passes.

## Mechanism
- **The rule:** CFM's opt-in intraday margin (weekdays 8 am–4 pm ET) ends at 4:00 pm. Overnight margin is 2–4× higher; rates ramp from 3:30, and a short account liquidates at 4:00. CDE settles on the 15:59–16:00 VWAP.
- **Who is forced, who is paid:** retail longs on intraday margin must sell into thin books. A liquidity provider, or a buyer after the step, should earn the reversion.
- **Kill test:** CFM may internalise liquidations (memo R1), leaving no public footprint.

## Data
- **Prints:** 7.33M CDE perp prints in 12,244 windows: 19 perps, every day from launch to 2026-11-05, in two ET windows (13:30–14:30 control; 15:30–17:30). 17,130 requests, no errors.
- **Completeness:** on DEV trading days (4,236 windows, 4.69M prints), print volume matches 1-minute candle volume within 0.005%.
- **Basis residual:** H1's definition, from the perp and spot candles.
- **Calendar:** ET with daylight saving; weekdays minus US holidays (listed in hcommon.py). 217 DEV trading days (2025-07-21 – 2026-05-29); 99 weekend/holiday days as a placebo.
- **Universe:**
  - BTC/ETH from Jul 2025; SOL/XRP from Aug 2025.
  - 8 alts from Dec 2025; 6 more from Mar 2026.
  - HYPE in HOLD only.
- **Excluded:** AVAX fails the $150 contract rule every day; BNB, DOT and SHIB have no candles.

## Step 1 (DEV; 4 pm window vs the same window two hours earlier)
| Measure | 4 pm | Control | Paired t (NW) | Placebo t |
|---|---|---|---|---|
| Aggressive-sell share (USD-pooled) | 53.2% | 50.5% | **4.59** (3.67) | 1.04 |
| Basis residual 15:55–16:05 (volume-weighted) | −2.79 bp | −0.17 bp | **−7.79** (−4.52) | −0.72 |
| Perp − spot return 15:45–16:05 (information) | −0.71 bp gap | | −2.04 | |

- **Information:** equal-weighted selling +5.8 pp (t 9.7); R1's 16:00–16:02 check +4.1 pp (t 2.2); volume 1.6× the control.
- **By coin:** extra selling in 18 of 18 coins (t ≥ 2 in 14); negative residual in 17 of 18.
- **Minute profile:** the residual sinks from −2 bp at 15:40 to about −3.4 bp at 16:01–16:05, and is still −2.2 bp at 16:15 (BTC/ETH).
- **Friday:** same as Mon–Thu (Welch t 0.38 and −0.45).
- **Decay:**

  | Period | Extra selling | Basis residual |
  |---|---|---|
  | Jul–Oct 2025 | +5.9 pp (t 5.3) | −5.8 bp |
  | Nov 2025 – May 2026 | +1.1 pp (t 1.7) | −0.95 bp |

  By month, the selling t was ≥ 3.7 in Aug–Oct 2025 and ≤ 1.5 afterwards: CFM's terms, or retail, changed.
- **Result:** both tests pass, so Step 2 was built.

## DEV trials (21 logged)
- **Step 1:** two trials, logged as the idle-sleeve DEV book.
- **Step 2:** 19 trials in the table below, sleeve $30K at 2× costs (1× in brackets). Alpha t is on the incumbent at $70K; gross and net are bp per trade.

| Variant | Trades | Sleeve Sharpe | Alpha t | Gross | Net 2× |
|---|---|---|---|---|---|
| vbid k1.5 BTC+ETH | 422 | −12.0 (−7.9) | −11.31 | −0.5 | −19.5 |
| vbid k1.5 all | 1089 | −10.9 (−7.3) | −9.45 | −2.2 | −19.6 |
| vbid k2 BTC+ETH | 406 | −11.2 (−7.1) | −9.63 | −0.5 | −19.3 |
| vbid k2 all | 948 | −10.5 (−6.9) | −9.00 | −1.8 | −18.4 |
| vbid k3 BTC+ETH | 359 | −9.7 (−5.4) | −9.23 | +3.0 | −15.3 |
| vbid k3 all | 743 | −8.1 (−4.8) | −8.01 | +1.0 | −14.6 |
| vafter z1 16:30 BTC+ETH | 151 | −5.2 (−1.9) | −4.61 | +10.6 | −15.3 |
| vafter z1 16:30 all | 281 | −4.9 (−1.7) | −4.89 | +4.7 | −23.5 |
| vafter z1 17:00 BTC+ETH | 151 | −4.2 (−2.1) | −3.14 | +5.7 | −20.4 |
| vafter z1 17:00 all | 281 | −3.5 (−1.9) | −2.67 | −0.7 | −29.1 |
| vafter z2 16:30 BTC+ETH | 36 | −2.5 (−1.3) | −2.33 | +19.2 | −0.4 |
| vafter z2 16:30 all | 59 | −3.0 (−1.4) | −2.49 | +12.1 | −12.1 |
| vafter z2 17:00 BTC+ETH | 36 | −1.4 (−0.3) | −1.22 | +25.3 | +5.4 |
| vafter z2 17:00 all | 59 | −2.1 (−1.1) | −1.56 | +10.9 | −13.5 |
| vflow x1 BTC+ETH | 59 | −2.5 (−1.0) | −2.61 | +15.5 | −10.5 |
| vflow x1 all | 209 | −2.1 (−0.4) | −2.03 | +19.2 | −13.6 |
| vflow x2 BTC+ETH | 17 | −1.9 (−1.2) | −1.83 | +30.7 | +6.2 |
| **vflow x2 all** | 54 | −1.1 (−0.3) | **−1.07** | +42.5 | +10.8 |
| vflow x2 all, short mirror | 68 | −2.6 (−1.7) | −1.79 | +21.8 | −12.1 |

Positive net bp can still give a negative Sharpe: the sleeve is idle about 90% of days, and the gates charge T-bills on idle capital.

## Frozen variant
**vflow_x2_all**, freeze commit 7c378c0. It had the highest DEV alpha t among trials with at least 40 trades; the runner-up was −1.56.
- **Signal:** at 16:01 ET, buy the perp of any coin whose 15:30–16:00 return is below −2× its trailing 20-day standard deviation.
- **Entry:** taker, at the first print at or after 16:01:02, worse by 1.5× the half-spread.
- **Exit:** at market, at the first print at or after 16:45:02.
- **Size:** min($15K, 2% of the trailing 20-day median 15:30–16:30 volume).

## Gates
Path B at 2× costs, a = 0.7 chosen on DEV, 476 scored days.

| Gate | Value | Result |
|---|---|---|
| G1: full-window alpha t ≥ 3 | −2.18 | FAIL |
| G2: HOLD t ≥ 1.5 and gain ≥ +0.25 | t −2.08, gain −0.64 | FAIL |
| G3: full-window gain ≥ +0.5 | −0.27 (book Sharpe 2.53 vs 2.80) | FAIL |
| G4: deflated Sharpe ≥ 0.95 | 0.00, provisional (0.14 at the v_z floor) | FAIL |
| G5: no losing book year | 2025 +16.2%, 2026 +12.6% | PASS |

- **HOLD:**
  - Book Sharpe 3.00 vs the incumbent's 3.64; sleeve Sharpe −3.46.
  - 73 trades at −33.6 bp at 2× (−13.7 bp at 1×), against +10.8 bp on DEV.
- **At 1×:** full-window alpha t −0.88, HOLD −1.03. θ = 0.25 changes nothing (a taker variant).
- **Fee sensitivity, at 2×:**
  - $0.12 per contract: HOLD −25.7 bp, full-window alpha t −1.67.
  - $0.30 per contract: HOLD −43.6 bp.
- **Sleeve years at 2×:** 2025 −0.8%, 2026 −2.0%.
- **Concentration:** P&L DEV +$167, HOLD −$1,007; three HOLD days account for −$957 (top-3 share undefined: total negative).
- **HOLD by month (net bp at 2×, trades):** Jun −64 (11), Jul −66 (19), Aug +19 (13), Sep −28 (26), Oct none, Nov −8 (4).
- **Overlap:** correlation with the incumbent 0.002; +0.03% on its worst 5% of days. H1: no daily.parquet on hunt/h1pb at finish.

## Capacity and fill realism
- **Capacity:** mean notional $7.5K, 50% of the target. Majors fill about $14.5K; alts $0.3–4.5K, where the volume cap binds. Active on 38 of 476 days.
- **Prices:** every entry and exit is priced on actual prints. The median entry is 4.3 s after 16:01:00 (p90 42 s). Each leg pays 1.5× the half-spread plus the fee.
- **V-bid fills:**
  - Rules: prints strictly through the level, size ≤ θ × through-volume, live from t + 1 s, post-only and ±5% Fair Value Limit checks.
  - 85% of fills hit the take-profit. The rest lost about 57 bp: the bids filled when spot itself was falling (adverse selection).

## Why it fails
- **Size of the footprint:** the selling is visible, but the majors' dislocation is only about 2–3 bp, and it reverts slowly.
- **Cost of a round trip at 2×:** about 9 bp on BTC as maker; about 28 bp on ETH, where $0.40 is paid per 0.1-ETH contract; 12–40 bp as taker.
- **The gross edges that exist are too small or too rare:**
  - V-after (z ≤ −1, BTC+ETH): +10.6 bp, trade-level t 3.2.
  - V-flow (x = 2): +42 bp, but on only 54 trades.
- **Post hoc, not a trial:** BTC-only V-after netted +1.8 bp; ETH's fee is the drag.

## Weaknesses
- The mechanism faded about 6× after Oct 2025; its HOLD state is unknown (Step 1 is DEV-only).
- Taker fills use the next print, not the book. The fee is unverified. Spot closes are 1-minute.

## Scorecard (pre-registered weights)
| Criterion | Score | Note |
|---|---|---|
| Out-of-sample | 0/20 | |
| Statistical strength | 0/20 | |
| Robustness | 0/15 | Neighbouring settings agree only in being negative |
| Fill and cost realism | 12/15 | Fees unverified |
| Mechanism | 8/10 | |
| Implementability | 10/10 | |
| Diversification | 5/5 | |
| Capacity | 2/5 | |
| **Total** | **37/100** | |

## Deviations (none after HOLD)
1. **Print fetcher:** a subclass of the shared fetcher fixes its paging (below). common.py is unchanged.
2. **Fetch windows:** 15:30–17:30 ET instead of 15:30–16:45, to cover the 17:00 exits; plus the 13:30–14:30 control. Weekend/holiday aggregates are a placebo, not a trial.
3. **Step-1 choices:** the volume weights and window bounds were committed before step1.py ran.
4. **Step-1 trials:** logged as the idle-sleeve DEV book, with their t-stats in `extra`.
5. **Taker sizing:** the volume measure is the 15:30–16:30 USD perp volume over the trailing 20 trading days.
6. **Exits:** with no print within 30 minutes, a trade exits at the next candle's open. This was fixed before any Step-2 number existed.
7. **PEPE prices** (quoted per 1,000 PEPE) are converted before costs and the $150 rule.

## Shared-code problems
1. **TradeFetcher.window drops prints at page boundaries.**
   - It ends each next page at int(oldest print), and `end` is exclusive, so earlier prints in that second are lost.
   - ETH lost 4,865 of the 5,709 contracts in the 16:00 ET minute of 2026-03-11.
   - The losses fall in bursts, exactly where the 4 pm and wick studies look (H1 especially).
   - Fix: hcommon.Fetcher.
2. **PEPE units:**
   - common.PERP is in PEPE units, but the candles and prints quote per 1,000 PEPE.
   - Passing a raw price makes perp_cost_bp understate PEPE fees 1,000×.
   - SHIB's tick also disagrees with the product metadata; untested.
3. **The gates' v_z is inflated**, so G4 is provisional, as the coordinator noted.

## Reproduce
scripts/hunt/h9mc/: fetch.py, step1.py, step2.py (Actions); log_dev.py, freeze.py, gates_run.py (local).
