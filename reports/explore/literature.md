# R2-08 spot ladder: next ideas to test (literature + practitioner scan)

Scope: ideas that could raise the Sharpe of the R2-08 Coinbase-spot wick-catcher. Each idea is mechanism-led and says how it differs from what has already been tested.
Ranking (per coordinator): first by **how directly the idea maps to knobs the simulator has today**, then by expected Sharpe gain. The knobs are:
- rung depths (4-12 sigma) and weights;
- take-profit fraction of each rung's dislocation (0.3-1.0), per rung or as a scale-out ladder;
- hold time (up to 60 min);
- when deeper bids are cancelled (parent recovery fraction, or a timeout in minutes);
- per-signal filters on the AI pred/thr ratio, sigma in bp, coin ADV, coin daily vol and signal time.

Ideas that need simulator changes (but no new data) are in section B. Ideas that need new data are in section C.
Expected sign: + (should raise Sharpe), - (should lower it), ± (theory is split; test it).
"Practitioner claim" marks forum, blog and vendor material that is not peer reviewed.

---------------------------------------------------------------------------------------------------

## A. Ideas the simulator can express today (ranked)

### A1. Take-profit fraction that rises with rung depth  (expected sign: + on the 8 sigma rung, ~0 on the 4 sigma rung)
- **Mechanism.** The deeper rungs are filled by larger, mostly uninformed forced-selling shocks. Their impact reverts more fully and more slowly, so a fixed 60% take-profit sells the best fills early.
  - Lipton and López de Prado solve for the Sharpe-optimal take-profit and stop under a mean-reverting (OU) model with a time stop. With strong mispricing it is "not optimal to stop the trade early": hold to the horizon. With weaker mispricing a take-profit can help.
  - Duffie: "the size of the immediate price reaction and the half-life of its reversal are decreasing in the mean rate at which investors locate suitable counterparties". Deeper shocks go with slower recovery.
  - Gomes and Waelbroeck, as summarised in the market-impact review: residual impact is about 2/3 for informed metaorders and about 0 for uninformed ones (measured after 10 days).
  - This fits your markouts, which still rise at 60 minutes (+51 bp).
- **Citations.** Lipton & López de Prado, "A closed-form solution for optimal mean-reverting trading strategies" (arXiv 2003.10502); Duffie (2010) AFA Presidential Address; "Market Impact: Empirical Evidence, Theory and Practice" (arXiv 2205.07385, Sec. 11.4, Table 4).
- **Knobs.**
  - Per-rung TP fractions (4 sigma / 6 sigma / 8 sigma): {0.5, 0.7, 0.9}, {0.5, 0.8, 1.0}, {0.6, 0.8, 1.0}, {0.4, 0.6, 1.0}.
  - Control: the {0.6, 0.6, 0.6} baseline.
  - Keep the fractions monotone in depth. Do not search them freely.
  - Hold stays at 60 minutes.
- **What to watch.** The share of exits that reach the 60-minute market sale (taker 12.5 bp) rises with the TP fraction, so report gains net of that cost. Most of the effect will come from a handful of cascade days, so run the concentration checks in section D.

### A2. Cost floor on the dislocation in bp: per-signal filter on sigma_bp  (expected sign: +)
- **Mechanism.** This is fee arithmetic, not a forecast.
  - At 4 sigma, a 60% take-profit captures 2.4 x sigma_bp before fees.
  - The round trip costs about 12 bp maker/maker, or 18.5 bp maker/taker if the 60-minute exit fires.
  - When sigma_bp is small, fees take most of the edge while the risk is the same, so these trades lower Sharpe even if their net mean is slightly positive.
  - In Avellaneda-Lee-style stat-arb, entry and exit thresholds are set in units of the residual's equilibrium sigma, with costs handled separately. A cost floor is the standard companion rule.
- **Citations.** Avellaneda & Lee, "Statistical arbitrage in the US equities market" (s-score: open at s < -1.25, close at s > -0.50). That close is 60% of the entry dislocation, the same as your TP. Rest is your own fee schedule.
- **Knobs.**
  - Require 4 x sigma_bp >= {25, 35, 50, 75} bp. Equivalently, sigma_bp >= {6, 9, 12.5, 19} bp.
  - Alternative: drop the lowest tercile of coin daily vol.
  - Report trade count, net bp per trade and Sharpe at each floor.
- **What to watch.** The filter also changes which coins and regimes trade, and low-sigma periods may be when cascades start. Run a placebo: a random filter that removes the same number of trades.

### A3. Trigger-only or light parent: 4 sigma acts mostly as a trigger, and capital goes to deeper rungs  (expected sign: ±; + if cash binds on cascade days)
- **How it differs from tested work.** You tested deeper-weighted rungs and a 10 sigma rung with the 4 sigma rung still funded. This sets the parent's weight to zero (or about 10%), so the 4 sigma touch only arms the 6 and 8 sigma bids. That frees cash on cascade days, when the 100%-of-cash cap binds.
- **Mechanism.** Net edge per dollar is 33 bp at 4 sigma, 46 at 6 and 83 at 8. Deep fills happen on co-movement cascades, when HFT market makers stop supplying liquidity, so the deep book is thin and the rebound is large.
  - Brogaard et al.: HFT liquidity provision "is limited to EPMs in single stocks". In simultaneous EPMs, HFT liquidity demand outweighs their supply.
  - Handa & Schwartz: a paucity of limit orders "can result in accentuated short-term price fluctuations that compensate a limit order trader".
- **Citations.** Brogaard, Carrion, Moyaert, Riordan, Shkilko, Sokolov, "High frequency trading and extreme price movements" (JFE 2018; thesis copy on core.ac.uk); Handa & Schwartz, "Limit Order Trading" (JF 1996).
- **Practitioner claim.** Hummingbot's "liquidation sniper" defaults to a deeper-weighted maker ladder: offsets 1/2/3/5% with 10/20/30/40% of capital, TP 1%, stop 3%, 30-minute time limit.
- **Knobs.**
  - Weights (4 / 6 / 8 sigma): {0, 0.5, 0.5}, {0, 0.4, 0.6}, {0.1, 0.4, 0.5}.
  - Rungs at 4 (trigger) / 6 / 8 / 10 sigma with weights {0, 0.3, 0.4, 0.3}.
  - Keep the per-signal size cap, so the deeper rungs get the parent's notional.
- **What to watch.** Fewer fills means a noisier Sharpe. Compare on paired daily P&L differences (section D), not on separate Sharpe levels.

### A4. Scale-out take-profit ladders  (expected sign: small +, mainly through lower variance)
- **Mechanism.** In the Guéant-Lehalle-Fernandez-Tapia liquidation-with-limit-orders model, the optimal ask is monotone in remaining inventory: "a larger inventory gives a lower ask". As inventory is sold, the remaining units are offered higher.
  - In practice: sell the first tranche close, the last tranche far.
  - This turns a binary "TP hit / time stop" outcome into a smoother payoff, and the far tranche keeps exposure to the reversion that is still rising at 60 minutes.
- **Citation.** Guéant, Lehalle, Fernandez-Tapia, "Optimal Portfolio Liquidation with Limit Orders" (arXiv 1106.3279; verification theorem and asymptotic quote formula).
- **Knobs.**
  - Each rung split into thirds with TPs {0.4, 0.7, 1.0}, {0.3, 0.6, 0.9} or {0.5, 0.75, 1.0}.
  - Halves at {0.5, 1.0}.
  - Combine with A1: deeper rungs get the higher ladder, e.g. 4 sigma {0.4, 0.6, 0.8} and 8 sigma {0.6, 0.8, 1.0}.
- **What to watch.** More passive orders each pay the 6 bp maker fee on a smaller size, so fees per dollar are unchanged. The risk is that the far tranche often ends at the taker time stop. Report the time-stop share.

### A5. When to cancel the deeper bids: parent recovery fraction or timeout  (expected sign: ±)
- **Mechanism (two-sided).**
  - Forced selling is front-loaded. In the October 2025 cascade, about 88% of post-onset forced selling occurred within 30 minutes, and Hyperliquid liquidated about $2.1B in 12 minutes. A deep bid still resting after the episode is more likely to be hit by a new, informed move, and it ties up cash. That argues for cancelling on parent recovery or after about 20-30 minutes.
  - Against that, extreme moves cluster and decay like aftershocks (Omori law; self-exciting Hawkes dynamics), which argues for longer timeouts.
- **Citations.** Garcia Seuma, "Measuring the engine of a liquidation cascade" (arXiv 2608.03616); Sepper, "Slippage-at-Risk" (arXiv 2603.09164); Lillo & Mantegna, "Omori law after a financial market crash" (cond-mat/0111257); Bacry, Mastromatteo, Muzy, "Hawkes processes in finance" (arXiv 1502.04592).
- **Knobs.**
  - Cancel the deeper bids when the parent has recovered {25%, 50%, 75%} of its dislocation.
  - Timeouts of {10, 20, 30, 60} minutes.
  - One combined arm: cancel at 50% recovery OR 30 minutes.
- **What to watch.** The answer depends on a few large cascades, so use leave-one-cascade-out (section D).

### A6. Finer grid and a smeared ensemble of neighbouring ladders (parameter averaging)  (expected sign: small + to Sharpe, large reduction in overfitting risk)
- **Mechanism.**
  - A single 8 sigma rung is fill-or-miss on where one candle's low lands. Spreading the same notional over nearby levels averages out that threshold noise.
  - Averaging nearby settings also avoids the out-of-sample decay of a picked optimum:
    - In Newfound's ensemble of more than 500 momentum specifications, the averaged strategy's Sharpe "fell in the top quartile of specifications" with bottom-quartile drawdown. Changing only the rebalance day moved Sharpe from about 0.6 to 0.9.
    - The forecast-combination literature finds simple averages beat estimated optimal weights, largely because of weight-estimation error.
- **Citations.** Newfound Research, "Ensemble Multi-Asset Momentum" (blog, practitioner); Qian, Rolling, Cheng, Yang, "On the Forecast Combination Puzzle" (arXiv 1505.00475).
- **Knobs.**
  - (a) Rungs {4, 5, 6, 7, 8, 10} sigma with weights proportional to net bp per dollar from your table, interpolated. Or equal weights.
  - (b) Nine sub-ladders, each with 1/9 of the signal size:
    - depth multipliers {0.9, 1.0, 1.1} applied to (4, 6, 8) sigma, crossed with TP {0.5, 0.6, 0.7};
    - equivalently, rungs at {3.6, 4, 4.4}, {5.4, 6, 6.6} and {7.2, 8, 8.8} sigma. 3.6 sigma is below your 4 sigma minimum; drop it or use {4, 4.4, 4.8}.
  - Report the ensemble against the median and the best member.
- **What to watch.** Small fills raise the minimum-size and rounding problems on Coinbase, so check the minimum order size for low-ADV coins.

### A7. AI-conditioned depth instead of AI-conditioned size; a deep-only ladder below threshold  (expected sign: ±; + if your lesson "filters remove the best fills" also applies to the AI gate)
- **How it differs from tested work.** You tested thresholds from the 40th to 75th percentile, and sizing by predicted edge. Here the pred/thr ratio chooses where the ladder sits, not how big it is or whether it exists.
- **Mechanism.** The model "ranks risk along with return". For low-confidence signals, demand a larger margin of safety (a deeper first rung) rather than skipping them.
  - At extreme dislocations the payoff is dominated by uninformed forced-selling reversion (Gomes-Waelbroeck, via the impact review), which the gate may be filtering out.
  - Handa & Schwartz report that a standalone "network of buy and sell limit orders" is profitable.
- **Citations.** Handa & Schwartz (1996); "Market Impact: Empirical Evidence, Theory and Practice" (arXiv 2205.07385).
- **Knobs.**
  - Ladder L1: pred/thr >= 1.5 gives rungs 4/6/8.
  - Ladder L2: 1.0 <= pred/thr < 1.5 gives rungs 5/7/9.
  - Ladder L3 (new coverage): 0.6 <= pred/thr < 1.0 gives a deep-only ladder of 8/10/12 sigma, with weights {0.3, 0.4, 0.3} and TP 0.8-1.0.
  - Test L3 alone first.
- **What to watch.** L3 adds the fills most exposed to genuine news crashes: hacks, delistings, and venue failures such as the October 2025 Binance zero prints (ATOM, IOTX, ENJ), which on other venues fell 53%, 46% and 64.5%. Inspect L3's worst 10 trades one by one.

### A8. Hold time by rung depth: shorter for 4 sigma, 60 minutes for deeper  (expected sign: ±; small)
- **Mechanism.**
  - Under the fair-pricing view, the time for price to return to the metaorder's average execution price is roughly the metaorder's duration.
  - Duffie: deeper shocks recover more slowly.
  - So the 4 sigma rung (shallow, short episodes) can be released earlier to recycle cash, while the deep rungs keep the full 60 minutes.
- **Citations.** "Market Impact: Empirical Evidence, Theory and Practice" (arXiv 2205.07385, Sec. 11.3: fair-pricing time about equal to metaorder duration); Farmer, Gerig, Lillo, Waelbroeck, "How efficiency shapes market impact" (arXiv 1102.5457); Duffie (2010).
- **Knobs.** 4 sigma hold {20, 30, 45} min with 6 and 8 sigma at 60. Pair with A3 or A6, which change how much cash the 4 sigma rung uses.
- **What to watch.** You already found 30-minute holds worse overall. This only helps if cash recycling on cascade days is worth more than the lost 4 sigma markout. Check the cascade-day subset.

---------------------------------------------------------------------------------------------------

## B. Ideas that need a simulator change but no new data (short)

- **B1. Exit anchored to fair value, not a fixed price (expected sign: +).** Exit when the residual has recovered a fraction f of the entry dislocation, instead of when price reaches entry + f x dislocation.
  - Once the idiosyncratic gap has closed, what remains is mostly BTC-beta exposure. That carries risk with little expected edge, unless BTC's own post-cascade rebound is part of your edge, which the test will show.
  - Test residual-TP, price-TP, and whichever triggers first, at f in {0.5, 0.6, 0.8}.
  - Evidence: Avellaneda-Lee close their trades on the residual s-score (s > -0.50), not on price.
- **B2. Take-profit that decays over time (expected sign: +).** TP(t) = f0 - (f0 - f1)(t/60)^p, with f0 in {0.8, 1.0}, f1 in {0.2, 0.4} and p in {0.5, 1, 2}.
  - In GLFT the quote "is lowered as the deadline approaches". A falling passive TP should catch more exits as maker (6 bp) instead of taker (12.5 bp) at minute 60.
- **B3. Take-profit at the VWAP of the forced-selling episode (expected sign: ±).**
  - The fair-pricing condition: "the average transaction price of the metaorder is equal to the price after trading is completed" (Farmer et al.). Permanent impact is about 2/3 of peak impact.
  - Compute the episode VWAP from 1-minute typical price x volume, from the first minute the residual drops below -1 sigma until the fill, and set the TP there or at the VWAP minus a buffer.
- **B4. Cash reserved for deep rungs, and priority by depth, when cash binds (expected sign: +).**
  - Cap total 4 sigma exposure at {30, 50}% of cash, so 6 and 8 sigma fills are always fundable.
  - Optionally let an 8 sigma fill bump the shallowest open 4 sigma position (sell it at the bid) when its expected remaining edge is below 83 bp plus 12.5 bp.
  - Evidence: returns to liquidity provision rise when liquidity supply is withdrawn (Nagel, "Evaporating Liquidity"), and shocks "must be absorbed on short notice by a limited set of investors" (Duffie).
  - This rule decides which rungs get funded when cash runs out, not how big a signal is; still treat it with the same suspicion as your sizing rules.
- **B5. Jump-robust sigma (expected sign: ±).**
  - Replace the 3-day residual standard deviation with MedRV or bipower variation, so cascades do not inflate the yardstick for days afterwards. MedRV = pi/(6-4*sqrt(3)+pi) * n/(n-2) * sum med(|r_{i-1}|, |r_i|, |r_{i+1}|)^2.
  - Optionally blend horizons HAR-style (Corsi): sigma^2 = a*RV_1d + b*RV_3d + c*RV_7d.
  - Sanity anchor: the Lee-Mykland 1-minute jump threshold. With C_n and S_n from the cited constants and alpha = 1%, it is about 4.6 sigma over n = 1,440 one-minute observations (one day) and about 5.0 sigma over n = 10,080 (one week). Our calculation converts these to true-sigma units. This is close to your 4 sigma parent.
- **B6. Fair-value beta (expected sign: ±; + on BTC-led cascade days).**
  - (a) Correct for lead-lag and the Epps effect: Dimson sum of betas at lags 0-3 minutes, or beta from 5-15 minute returns. BTC led ADA by about 57 seconds on average (range 16-118 s) at tick level, and correlations shrink at short horizons (Epps).
  - (b) Downside or crash beta in BTC-led drops. Correlations rise in bear markets (Longin-Solnik), and inter-asset coupling jumps to a "near-fully-ordered phase" at cascade onset (Garcia Seuma).
  - A higher crash beta lowers fair value in BTC-led cascades, so bids fill deeper, which is where your best fills are.
- **B7. Fair value averaged over several horizons (expected sign: small +).** Average the standardised residual over 15, 60 and 240-minute windows, or arm on the most negative. This is parameter averaging for the 60-minute window choice; same evidence as A6.
- **B8. Re-arming for aftershocks (expected sign: ±).** After a filled ladder closes, keep the coin armed for H in {2, 6} hours whatever the AI says. Event rates decay like Omori's law after crashes (Lillo-Mantegna; Petersen et al. at 1-minute resolution). Your tested cool-down after a failed ladder is the opposite case.
- **B9. Snapping rungs to round numbers and queue position (expected sign: small +).**
  - Stop-loss sells cluster just below round numbers and take-profits at them. Rates trend faster after crossing round numbers and reverse more often at take-profit clusters: 59.3% vs 54.8% for USD/DEM (Osler).
  - Over 10% of Bitcoin prices end in .00 (Urquhart).
  - Rule: a rung within 0.5 sigma below a round level moves to 1 tick above it, which puts the bid at the front of the queue at a level with higher reversal odds. Mirror it for TPs: place them 1 tick below the round level.
- **B10. Deeper-rung spacing that adapts to sell intensity (expected sign: ±).** After an influential sell, the model market maker "cancels her existing limit orders and reposts" with a wider bid half-spread, and fill probability at a fixed depth falls (Cartea-Jaimungal-Ricci).
  - Rule: if the move from -1 sigma to 4 sigma took 2 minutes or less, place the deeper rungs at 7 and 10 sigma; otherwise at 6 and 8.
  - This changes geometry, not whether to trade, which is how it differs from the tested drop-shape filter.

## C. Ideas that need new or short-history data (short)

- **C1. Venue-local vs global dislocation (needs other venues' 1-minute candles).**
  - BitMEX describes "scamwicks" as wicks contained to one exchange that revert in about 1 minute because other venues and derivative mark prices do not follow (practitioner claim).
  - Derivatives lead spot in price discovery (Alexander, Choi, Park, Sohn, JFM 2020, BitMEX data).
  - Rule: fills where Coinbase trades well below other venues get a fast, tight exit; global dislocations get A1's wide exit.
- **C2. Perp-spot basis at fill (Coinbase perps since mid-2025; short history).** A deep perp discount means the forced selling is in leveraged perps and spot is following through arbitrage. Use it as an exit conditioner, not an entry filter.
- **C3. Liquidation-feed triggers and liquidation-cluster levels (needs liquidation and open-interest history, mostly unavailable).**
  - Practitioner claims: Hummingbot triggers on more than $10M of Binance liquidations within 15 seconds. CoinMarketMan places orders 0.3-1% beyond estimated 10x/25x liquidation bands. No backtests are shown in either source.
- **C4. Queue-aware fill model (needs order-book history or more trade prints).** See D-0.
- **C5. Yield on idle cash (operational).** Coinbase USDC rewards are now limited to Coinbase One members, at 4% per Decrypt.
  - This raises raw return but not Sharpe measured over the risk-free rate.
  - Not verified: whether resting bids can be funded from USDC without losing the rewards.

---------------------------------------------------------------------------------------------------

## D. Methods: searching 1,000+ variants without fooling ourselves

**D-0. Before any search.**
- **(i) Fill realism.**
  - Require a trade-through by at least 1 tick, or volume printed at or below the bid of at least our size plus an assumed queue. Calibrate with the Coinbase trade prints.
  - Lo, MacKinlay and Zhang find that executions inferred from first-passage times or transaction data are "very poor proxies for actual limit-order executions".
  - Practitioners note that passive fills cluster when the market moves against you (r/algotrading thread).
  - Re-run the "deepest fills are best" finding under the stricter fill model first.
- **(ii) Look-ahead check.** The "quarter's 60th percentile" arming threshold must be computed from past predictions only (trailing or expanding window), never from the current quarter's own distribution.
- **(iii) Holdout.** Lock the most recent 6 months, and select parameters inside the walk-forward loop.

**D-1. Test differences, not levels.** For variant k, use the paired daily series d_kt = r_kt - r_base,t. Highly correlated variants have low-variance differences, so this has far more power than comparing two Sharpe ratios.
- Bootstrap by day blocks (stationary bootstrap with mean block about 5-10 days) or by cascade episode.

**D-2. Sharpe significance with non-normal returns.** Use per-period (daily) SR, skewness g3 and kurtosis g4 (not excess).
- sigma(SR) = sqrt[(1 - g3*SR + (g4-1)/4*SR^2) / (T-1)]
- PSR(SR*) = Phi[(SR - SR*) * sqrt(T-1) / sqrt(1 - g3*SR + (g4-1)/4*SR^2)]
- MinTRL = 1 + (1 - g3*SR + (g4-1)/4*SR^2) * (z_alpha / (SR - SR*))^2
- Caution: with daily skew about 5, the -g3*SR term shrinks sigma(SR) (in our example from 0.50 to 0.39 annualised). Do not trust that gain when the best 5 days are a third of P&L.
  - Always also report P&L and Sharpe with the top-k days removed (k = 1, 3, 5, 10), and leave-one-cascade-out results.

**D-3. Deflated Sharpe (Bailey & López de Prado 2014).**
- SR0 = sqrt(V[SR_n]) * [(1 - gamma) * Phi^-1(1 - 1/N) + gamma * Phi^-1(1 - 1/(N*e))], where gamma = 0.5772 and V[SR_n] is the cross-sectional variance of the trials' Sharpe ratios.
- DSR = PSR(SR0).
- E[max of N standard normals]: N=10: 1.58; N=45: 2.24; N=100: 2.53; N=1000: 3.26.
- Worked example: SR 2.5 annualised over 4 years, cross-trial sd of SR 0.5 annualised, normal returns.
  - N_eff = 50 gives SR0 = 1.14 annualised and DSR = 0.997.
  - N_eff = 1000 gives SR0 = 1.63 and DSR = 0.959.

**D-4. Minimum backtest length (Bailey, Borwein, López de Prado, Zhu 2014).**
- MinBTL (years) is about [((1 - gamma) * Z^-1(1 - 1/N) + gamma * Z^-1(1 - 1/(N*e))) / E[max SR_annual]]^2, which is less than 2 ln N / E[max]^2.
- Their example: with 5 years, no more than about 45 independent configurations, or the expected in-sample max annual SR is 1 with 0 out of sample.
- At N = 1000 independent trials: 10.6 years for an in-sample max SR of 1, or 2.65 years for 2.

**D-5. PBO via CSCV (Bailey, Borwein, López de Prado, Zhu).**
- Build M = T x N (daily P&L by variant). Split rows into S = 16 blocks, giving C(16, 8) = 12,870 splits.
- For each split: n* = best in-sample variant; w = its out-of-sample rank / (N + 1); lambda = ln(w / (1 - w)).
- PBO = share of splits with lambda <= 0 (reject a variant if PBO > 0.05).
- Also report the regression of out-of-sample on in-sample performance (slope usually negative) and P[out-of-sample loss].

**D-6. White's Reality Check, Hansen's SPA and Romano-Wolf StepM on d_kt.**
- RC: V = max_k sqrt(n) * dbar_k. Bootstrap V*_b = max_k sqrt(n) * (dbar*_kb - dbar_k). p = mean(V*_b >= V).
- SPA: T = max(0, max_k sqrt(n) * dbar_k / omega_k), with omega_k from the bootstrap or Newey-West.
  - Bootstrap with consistent recentring: Z*_kb = dbar*_kb - dbar_k * 1{sqrt(n) * dbar_k / omega_k >= -sqrt(2 ln ln n)}.
  - T*_b = max(0, max_k sqrt(n) * Z*_kb / omega_k). p = mean(T*_b > T).
  - Clearly inferior variants are not recentred, so they cannot inflate the critical value.
- StepM (studentized):
  1. Order variants by z_k = w_k / sigma_k.
  2. Reject every H_k with w_k - sigma_k * d_j > 0, where d_j is the (1 - alpha) bootstrap quantile of max over the not-yet-rejected k of (w*_k - w_k) / sigma*_k.
  3. Repeat on the remaining variants until no new rejections.
  - It controls the family-wise error rate strongly, and rejects at least as many hypotheses as the Reality Check.
  - Use J >= 1,000 bootstrap draws. The authors found the studentized version controls family-wise error in time series and the basic one does not.
- Heavy tails: these tests assume finite variance. With skew about 5, also run a subsampling version (Frederiksen, Matsui, Pedersen 2026).

**D-7. Harvey-Liu haircut.**
- t = SR_annual * sqrt(years); p = 2 * (1 - Phi(t)).
- Adjust p for M tests:
  - Bonferroni: min(M * p, 1).
  - Holm: min over the ordered p of max_{j <= i} (M - j + 1) * p_(j), capped at 1.
  - BHY: p_(M) unchanged; for i < M, min[(M * c(M) / i) * p_(i), p_BHY(i+1)], with c(M) = sum_{j=1..M} 1/j.
- Convert back: t_adj = Phi^-1(1 - p_adj / 2); HSR = t_adj / sqrt(years); haircut = 1 - HSR/SR. The authors advocate BHY.
- Bonferroni examples (our calculation):
  - SR 2.5 over 4 years: M = 50 gives HSR 2.09 (16% haircut); M = 1000 gives HSR 1.72 (31%).
  - SR 2.0 over 3 years: M = 1000 gives HSR 0.36 (82%).

**D-8. Effective number of trials (use as N in D-3 and M in D-7).** Take the eigenvalues lambda_i of the k x k correlation matrix of daily P&L across variants.
- Nyholt: M_eff = 1 + (k - 1) * (1 - Var(lambda) / k).
- Li-Ji: M_eff = sum f(|lambda_i|), where f(x) = 1{x >= 1} + (x - floor(x)).
- Galwey: M_eff = (sum sqrt(lambda_i+))^2 / sum lambda_i+, where lambda_i+ = max(0, lambda_i).
- Gao: the smallest m whose eigenvalues explain 99.5% of the variance.
- Or cluster the variants (ONC or hierarchical clustering on angular distance), take one inverse-variance portfolio per cluster, set N = number of clusters and V[SR] = variance of the cluster Sharpe ratios.
- Report N_eff together with the total number of variants tried, logged before the search (López de Prado's recommendation).

---------------------------------------------------------------------------------------------------

## E. Sources actually opened (title, URL)

**Optimal limit orders, exits and market impact**
- Handa & Schwartz, Limit Order Trading (JF 1996), IDEAS: https://ideas.repec.org/a/bla/jfinan/v51y1996i5p1835-61.html
- Guéant, Lehalle, Fernandez-Tapia, Optimal Portfolio Liquidation with Limit Orders: https://arxiv.org/abs/1106.3279 and https://arxiv.org/pdf/1106.3279
- Lipton & López de Prado, A closed-form solution for optimal mean-reverting trading strategies: https://arxiv.org/pdf/2003.10502.pdf
- Market Impact: Empirical Evidence, Theory and Practice: https://arxiv.org/pdf/2205.07385
- Farmer, Gerig, Lillo, Waelbroeck, How efficiency shapes market impact: https://arxiv.org/pdf/1102.5457
- Cartea, Jaimungal, Ricci, Buy Low Sell High (preprint): https://c.mql5.com/forextsd/forum/169/a_high_frequency_trading_perspective.pdf
- Lo, MacKinlay, Zhang, Econometric Models of Limit-Order Executions: https://web.mit.edu/Alo/www/Papers/limit10.html
- Avellaneda & Lee, Statistical arbitrage in the US equities market (slides): https://math.nyu.edu/inmemoriam/avellaneda/StatArb13030.pdf

**Liquidity provision, cascades and flash crashes**
- Duffie, Asset Price Dynamics with Slow-Moving Capital: https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1237-1267.html and https://www.darrellduffie.com/uploads/1/4/8/0/148007615/duffieafapresidentialaddress2010.pdf
- Nagel, Evaporating Liquidity: https://nber.org/papers/w17653
- Brogaard et al., HFT and extreme price movements (thesis copy): https://core.ac.uk/download/143688303.pdf
- Osler, Stop-loss orders and price cascades in currency markets: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.html
- Urquhart, Price clustering in Bitcoin: https://ideas.repec.org/a/eee/ecolet/v159y2017icp145-148.html
- Garcia Seuma, Early-warning signals ... seven crypto-perpetual liquidation cascades: https://arxiv.org/abs/2607.27070
- Garcia Seuma, Measuring the engine of a liquidation cascade: https://ideas.repec.org/p/arx/papers/2608.03616.html
- Sepper, Slippage-at-Risk: https://arxiv.org/html/2603.09164v1
- Borgards & Czudaj, Features of overreactions in the cryptocurrency market: https://econpapers.repec.org/RePEc:eee:quaeco:v:80:y:2021:i:c:p:31-48

**Hawkes processes and aftershocks**
- Bacry, Mastromatteo, Muzy, Hawkes processes in finance: https://arxiv.org/abs/1502.04592
- Lillo & Mantegna, Omori law after a financial market crash: https://arxiv.org/abs/cond-mat/0111257
- Petersen, Wang, Havlin, Stanley, Omori/productivity/Bath laws: https://ideas.repec.org/p/arx/papers/1006.1882.html

**Volatility, jumps and beta estimation**
- Andersen, Dobrev, Schaumburg, MedRV/MinRV: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr465.html
- High-Frequency Jump Tests (Lee-Mykland description): https://arxiv.org/pdf/1708.09520
- The Arrival of News and Return Jumps (Lee-Mykland constants): https://arxiv.org/pdf/1901.02691
- Corsi, HAR-RV: https://econpapers.repec.org/RePEc:oup:jfinec:v:7:y:2009:i:2:p:174-196
- OHLC volatility estimators: https://bookdown.org/jarneric/financial_econometrics/5.1-ohlc-measures.html
- Busca & Thomir, Epps effect: https://ideas.repec.org/p/arx/papers/2309.06711.html
- Anderson, Bitcoin vs Cardano lead-lag: https://businessperspectives.org/index.php/publishing-policies2/a-tick-by-tick-level-measurement-of-the-lead-lag-duration-between-cryptocurrencies-the-case-of-bitcoin-versus-cardano
- Non-synchronous trading betas (Scholes-Williams/Dimson): https://sites.google.com/view/defining-risk/equilibrium/evidence/market-sampling
- Price Discovery in Cryptocurrency Markets: https://arxiv.org/pdf/2506.08718
- Alexander, Choi, Park, Sohn, BitMEX derivatives price discovery: https://econpapers.repec.org/RePEc:wly:jfutmk:v:40:y:2020:i:1:p:23-43
- Longin & Solnik, Extreme correlation: https://econpapers.repec.org/RePEc:bla:jfinan:v:56:y:2001:i:2:p:649-676

**Overfitting and multiple-testing methods**
- Deflated Sharpe ratio (Wikipedia): https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio
- Probability of backtest overfitting: https://carmamaths.org/jon/backtest2.pdf
- Pseudo-mathematics and financial charlatanism (MinBTL): https://carmamaths.org/jon/backtest.pdf
- Harvey & Liu, Backtesting: https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF
- Reality Check / SPA: https://metricgate.com/docs/reality-check-superior-predictive-ability/
- SPA implementation: https://rdrr.io/cran/forecastdom/man/spa_test.html
- Frederiksen, Matsui, Pedersen, Heavy Tails and Predictive Ability Testing: https://arxiv.org/pdf/2605.16866
- Romano & Wolf, Stepwise multiple testing (working paper): https://econ-papers.upf.edu/papers/712.pdf
- Effective number of tests (poolr meff): https://search.r-project.org/CRAN/refmans/poolr/html/meff.html
- López de Prado, A Data Science Solution to the Multiple-Testing Crisis: https://www.aqr.com/insights/research/journal-article/a-data-science-solution-to-the-multiple-testing-crisis-in-financial-research
- Newfound, Ensemble Multi-Asset Momentum: https://blog.thinknewfound.com/2019/07/ensemble-multi-asset-momentum/
- Qian et al., On the Forecast Combination Puzzle: https://arxiv.org/pdf/1505.00475

**Practitioner sources (claims only, not peer reviewed)**
- BitMEX blog, Scamwicks and Stop Cascades: https://www.bitmex.com/blog/scamwicks-and-stop-cascades
- Hummingbot liquidation sniper: https://hummingbot.org/blog/coding-a-liquidation-sniper-v2-strategy-controller/
- CoinMarketMan, liquidation clusters: https://coinmarketman.com/blog/stop-loss-placement-using-liquidation-clusters-on-hyperliquid--en/
- TradingView "Stink Bids" script: https://in.tradingview.com/script/e515deFp-Stink-Bids
- TradingView "impossible limit orders": https://il.tradingview.com/chart/ETHUSD/lwZfDRUY-Ethereum-Dip-Lesson-Quick-Post-About-Impossible-Limit-Orders
- Elite Trader, Flash Crash Trading: https://elitetrader.com/et/threads/flash-crash-trading.210244/
- QuantConnect forum, realistic backtesting: https://www.quantconnect.com/forum/discussion/4564/realistic-backtesting-question/
- QuantConnect equity fill model docs (truncated): https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/supported-models/equity-model
- r/algotrading mirror, midpoint and passive fill realism: https://reddit.sentinel-team.org/posts/1tnl249/snapshots/2026-05-27T16%3A55%3A25.196064Z
- Gainium WickHunter (vendor page, no parameters): https://gainium.io/bots/wickhunter
- passivbot README: https://github.com/enarjord/passivbot
- Cointelegraph, Oct 10 2025 Binance zero prints: https://cointelegraph.com/markets/why-did-some-altcoins-on-binance-crash-to-zero
- Decrypt, Coinbase USDC rewards change: https://decrypt.co/351946/coinbase-ending-usdc-rewards-free-users-only-paid-members?amp=1

**Blocked or failed (not used)**
- Kaiko "How $3.21B vanished in 60 seconds" (permission timeout): https://www.kaiko.com/resources/how-3-21b-vanished-in-60-seconds-october-2025-crypto-crash-explained-through-7-charts
- TradingView "The Wick Catcher" (permission timeout): https://www.tradingview.com/chart/FUNUSDT/R3xgCJpG-The-Wick-Catcher/
- Coinbase help, USDC rewards (site error): https://help.coinbase.com/coinbase/getting-started/crypto-education/usd-coin-rewards-faq
