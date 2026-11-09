# Sizing lab: pre-registration (Nov 9 2026)

Written before any candidate statistic was computed. Branch sizing-lab, cut from main at c8ad3e3. Code:
scripts/sizing_lab/. Results: reports/sizing_lab/.

## Goal
Find a sizing rule for the R2-08 spot ladder that raises Sharpe durably and keeps capacity, for both paper books:
main (rungs 1/3, 1/3, 1/3) and W2 (1/4, 1/4, 1/2). Return is not the objective. "No winner" is a valid result.

## What earlier rounds already showed (these reads are not fully fresh)
- **C2a** (size x0.5 / 1 / 1.5 by the AI margin's tercile, on top of the 0.2% ADV cap) was read on the check era and
  2022-23 in ladder v5: t 2.21 under the frozen gates, 1.33 out of sample, gain on a few days. Family B is its
  relative, so B's holdout read is not fresh.
- **Ladder v6 sizing** (selection era only):
  - The AI's prediction ranks a signal's spread as well as its return.
  - Per-coin volatility points the wrong way.
  - 55% of signal net P&L falls on 20 days, and no rule's gain survived removing its best 5 days.
  - At today's volumes the 0.2% ADV cap leaves room to size up only on ETH, XRP and SOL.
- **The AI's walk-forward models already use** BTC's 60-minute and 4-hour move ("dips while BTC is also falling revert
  more") and a volatility / bid-depth regime ("works when volatility is high"). Time of day matters little to them.
  So C1 and C3 run against the AI's own evidence, and family A starts from a weak prior.
- **Medallion round:** day-of-week and weekend / CME-gap books on BTC failed out of sample (-0.20 / -0.54). Those were
  directional books, not sizing, but they lower the prior for A.
- **Wick v4:**
  - Fills while BTC is flat are the weakest in all three eras (a post-hoc lead).
  - W2 runs as a paper book.
  - Daily realized P&L hides W2's deeper crash drawdowns (-25.1% marked to market in the Oct 10 2025 replay).

## Simulator: scripts/wick_v4/rungs.py, with one optional hook
- **Run:** `rungs.run` calls the wick1m `sim.evaluate` with:
  - kappa 0.002 (each signal at most 0.2% of the coin's ADV) and every R2-08 signal;
  - theta 0.5 (the paper broker's capture) and positions at most 100% of capital;
  - bot-like fills: deeper fills inside the parent's own minute are dropped, as in the minute-stepping paper books;
  - rung weights W0 {4: 1, 6: 1, 8: 1} for the main book, W2 {4: 1, 6: 1, 8: 2} for the W2 book.
- **Realistic capacity:**
  - Entry and take-profit capacity count Coinbase spot only (`in_perp` and `tp_perp` set to 0): the spot bot cannot
    fill on perps (wick v4 correction).
  - The ADV behind the cap is Coinbase spot + perp, as the bot computes it (bot/spot/engine.py `daily_usd`).
- **Realistic costs (the simulator's model):**
  - Maker fees at the simulated 30-day volume tier, on entries and take-profits.
  - Market exits pay the taker fee, a 2 bp half-spread and square-root impact (0.7 x sigma_d x sqrt(size / ADV)).
  - Ladder v5 measured market-exit costs on Coinbase prints at 3-6 bp, against the model's 16-17 bp, so exits are
    priced conservatively. Not changed: the brief fixes rungs.py.
- **Capital:** $250K and $1M.
- **Returns:** daily P&L booked on the exit day, as a share of capital. Sharpe is on returns over T-bills (sim.period_stats),
  annualized with sqrt(365).
- **Sizing hook:** `sim.evaluate(mult=f, mult_cap=True)`.
  - Each row's signal size min(25% x capital, 0.2% x ADV) is multiplied by f(row).
  - With `mult_cap`, the result is capped again at 0.2% of ADV. The cap is a capacity limit, so a multiplier above 1
    acts only where the 25%-of-capital term binds.
  - `mult=None` keeps the old code path. With no multiplier, rungs.csv (W0, W2) and spot_only.csv reproduce exactly:
    largest difference 6e-17 (reproduce.txt).
- **Eras:**
  - Selection: Jan 1 2025 - Mar 31 2026.
  - Check: Apr 1 - Nov 5 2026.
  - 2022-23: Jan 1 2022 - Dec 31 2023.
  - Check and 2022-23 are binding and are read once, after the freeze.

## Units and statistics
- **Signal:** one R2-08 parent (a 4-sigma trade-through) with its 6- and 8-sigma rungs. Its return per dollar of size
  is r_i = signal P&L (all rungs, net of costs) / S_i, where S_i = min(25% x capital, 0.2% x ADV_i). It is taken from
  the flat book with the same rung weights, at $250K, in the selection era.
- **Event cluster:**
  - R2-08 parents (any coin) chain into one cluster when each is within 6 hours of the previous one.
  - A cluster spans from the UTC day of its first parent to the UTC day of its last parent + 2 hours. Overlapping
    spans merge.
  - Every day outside a cluster is a unit of its own.
- **Bucket statistics (selection era):** count, number of clusters, mean, variance, and the cluster-robust standard
  error of the mean.
- **Testable bucket:** at least 30 signals and 10 clusters in the selection era. A candidate whose bucket (or a guard
  whose firing set) is smaller is skipped, and logged as skipped.
- **Shrinkage:**
  - Mean: mu*_b = mu_pool + w_b (mu_b - mu_pool), with w_b = tau^2 / (tau^2 + se_b^2) and
    tau^2 = max(0, variance of the bucket means - average se_b^2) (method of moments).
  - Variance: s*_b^2 = (n_b s_b^2 + 30 s_pool^2) / (n_b + 30).
- **Multiplier, families A and B:**
  - g_b = (mu*_b / s*_b^2) / (mu_pool / s_pool^2).
  - m_i = clip(c x g_b, 0.5, 1.5), then the ADV cap.
- **Multiplier, guards (family C):** m = 0 where the guard fires and c elsewhere (1 <= c <= 1.5), then the ADV cap.
- **Same average capital as flat sizing:**
  - c is found by bisection so that the candidate's selection-era average capital equals the flat book's, for each
    book and capital.
  - Average capital = position dollar-minutes: take-profit parts are held until the take-profit, the rest 60 minutes.
  - If the caps make that unreachable, c takes its largest value and the shortfall is reported.
  - Multipliers and c are frozen. Holdout capital ratios are reported, not re-matched.

## Candidates (at most 3 per family)
**A. Calendar** (the US Eastern clock at the parent's fill)
- A1 Day of week: 7 buckets.
- A2 Sunday 16:00-19:00 ET, against the rest. Mechanism: thin liquidity around CME's weekly reopen (18:00 ET Sunday).
  CME crypto futures went 24/7 on May 29 2026, so the check era partly lacks the mechanism.
- A3 CPI and FOMC days, against the rest.
  - Days: the ET calendar days of CPI releases (8:30 ET) and FOMC statements (14:00 ET), listed in macro_days.csv with
    sources (BLS release archive and lapse notice, Federal Reserve calendar). October 2025 CPI was cancelled.
  - Mechanism: news-driven moves are information, not liquidity overshoots.

**B. R2-08's out-of-sample predicted edge**
- x_i = pred_i / thr_i: the walk-forward prediction over its quarter's 60th-percentile threshold, both from the trade
  list. The ratio is comparable across eras whose thresholds differ (about 35 in 2025, 80 in 2022).
- Bucket by x_i's rank among the R2-08 signals of the previous 90 days. Fewer than 30 such signals means m = 1.
- B1: halves.
- B2: terciles (C2a's buckets, with shrunk mu / sigma^2 sizes, inside the cap).
- B3: quintiles.

**C. Guards** (m = 0 when the guard fires)
- **C1 BTC still falling after the first fill:**
  - A 6- or 8-sigma rung is not bought in a minute that opens just after BTC fell by more than 1 x the standard
    deviation of BTC's 1-minute returns over the previous 24 hours.
  - "Just after" means over the minute before the rung's fill minute. For the first minute after the parent's fill,
    that is the parent's own minute.
  - Approximation: the rung counts as not filled. Minute data cannot say whether it would have filled later.
- **C2 Coins filling at once:** a new parent (and its rungs) is skipped when 3 or more other coins had an R2-08 signal
  in the 30 minutes before its minute. Signals count whether or not the book filled them.
- **C3 Vol regime:** every new parent is skipped while BTC's realized volatility over the previous 24 hours (1-minute
  log returns) is above 2 x the median of its daily values over the previous 365 days.

## Selection (selection era only)
- **Runs:** every candidate on both books and both capitals, ADV-capped.
- **Log:** each run is a row in variants.csv with ΔSharpe vs flat, return, capital ratio, max drawdown, worst day,
  CVaR 5%, ΔSharpe without its best 5 days, the top-5 days' share of the gain, and the leave-one-day-out minimum.
- **Family best:** the testable candidate with the highest mean selection ΔSharpe over the four cells (2 books x 2
  capitals). Ties go to fewer buckets. Each family's best is its finalist.
- **Calendar on top of B:** the A finalist is also built on top of the B finalist. The multipliers are multiplied,
  clipped to 0.5-1.5 and capital-matched again on the selection era.
- Nothing else is tuned.

## Freeze, then one read
- **Freeze commit:** the finalists, with their buckets, multipliers, c for each book and capital, and the
  event-cluster definition.
- **Then, once:** check and 2022-23 for each finalist against flat (both books, both capitals), and for A on top of B
  against B.

## Pass (all required, for each book)
The baseline is flat sizing of the same book; for test 6, it is B.
1. **Sharpe:** ΔSharpe >= +0.20 against the baseline in every era (selection, check, 2022-23) and at both capitals.
2. **Risk no worse than the baseline, in every era and capital:**
   - max drawdown, on daily realized equity and on minute mark-to-market equity;
   - worst day;
   - CVaR 5% (the mean of the worst 5% of days).
3. **Survives leaving out any one day:** in every era and capital, ΔSharpe stays >= +0.20 with any single day removed.
4. **No losing calendar year** (2022, 2023, 2025, 2026 to Nov 5) at either capital.
5. **Significance:**
   - Event-cluster bootstrap of the pooled check + 2022-23 ΔSharpe: 10,000 draws, units resampled within each era until
     the era's length is reached.
   - p = the share of draws <= 0. A rule's p is the larger of its two capitals' p (both must hold).
   - Holm across all holdout tests (finalists x books, plus A on top of B against B, x books), at 0.05.
6. **Calendar:** A against flat passes 1-5, and A on top of B passes 1-5 against B (it adds value beyond B).

**Verdicts:**
- A winner gets a new paper book: a bot/spot config with the rule, parity and fault tests, and deployment by
  `wickctl update`. It is forward-tested beside the incumbent books, and nothing goes live from this round.
- Everything else is rejected, with the next test named.
- No re-tuning after the holdout.

## Scorecard (100 points, fixed now)
Scored on the holdout eras, check and 2022-23 (the "binding cells").

| Criterion | Points | Formula |
|---|---|---|
| Sharpe gain, $250K | 20 | 20 x clip(mean ΔSharpe over binding eras and books at $250K / 0.40, 0, 1) |
| Capacity, $1M | 15 | 10 x clip(the same at $1M / 0.40, 0, 1) + 5 x clip(1 - abs(capital ratio at $1M - 1) / 0.10, 0, 1) |
| Consistency | 10 | 10 x share of the 12 cells (3 eras x 2 capitals x 2 books) with ΔSharpe >= +0.20 |
| Evidence | 15 | 15 x clip((0.20 - Holm-adjusted p) / 0.15, 0, 1), averaged over books |
| Spread | 10 | 5 x share of the 8 binding cells passing leave-one-day-out + 5 x clip((1 - top-5 share of the pooled holdout gain) / 0.5, 0, 1) (0 if the gain is <= 0) |
| Risk | 15 | 12 x share of the 48 risk checks passed (4 measures x 6 era-capital cells x 2 books) + 3 if no losing year in any book or capital |
| Mechanism | 10 | hand-scored, below |
| Implementation | 5 | hand-scored, below |

Hand scores, fixed now:

| Candidate | Mechanism /10 | Why | Implementation /5 | Why |
|---|---|---|---|---|
| A1 day of week | 2 | weak mechanism, 7 buckets | 5 | clock only |
| A2 Sunday 16-19 ET | 4 | CME reopen liquidity; gone since May 29 2026 | 5 | clock only |
| A3 CPI / FOMC days | 5 | information-driven moves | 4 | needs a maintained macro calendar |
| B1-B3 predicted edge | 7 | sizes by the forecast itself; but the forecast also ranks spread | 5 | the bot already has pred and thr |
| C1 BTC still falling | 4 | against the AI's evidence | 4 | per-minute BTC check on resting deeper bids |
| C2 coins at once | 6 | correlated cascades, cash crowding; but cascades carry the P&L | 5 | the bot sees its own signals |
| C3 vol regime | 4 | against the AI's evidence | 4 | 24-hour BTC volatility from 1-minute candles |

A family with no finalist gets no holdout score. Its best candidate is scored on the selection era as an in-sample
upper bound, and marked as such.

## Information only (no decision depends on it)
For finalists, on the holdout:
- uncapped multipliers (the multiplier applied after the ADV cap, as C2a was run);
- theta 0.25.

## Deviation log
(none yet)
