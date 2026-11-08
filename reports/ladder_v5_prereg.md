# Ladder v5: execution changes to R2-08's spot ladder (pre-registration)

Written 2026-11-07 (UTC) after the diagnosis in step 1 and before any candidate test. The commit that adds this file
is the freeze point: the simulators, the dataset and these rules do not change after it. Deviations go in the log at
the bottom with a reason and a time. Code: scripts/ladder_v5/. Results: reports/ladder_v5/.

## Goal (Miles, Nov 7, ET)
Work like an execution trader: markouts, queue position, adverse selection, expected value. Test whether any change
raises the spot ladder's Sharpe, or its capacity at the same return and Sharpe. "No change" is a valid answer.
Pass for a change: paired t ≥ 2 against the incumbent, consistent across three eras, holding at θ 0.25, at today's
volumes and fee tier, with unverified costs doubled; independent red team; adopted changes re-tested together.

## What has been looked at (honest accounting)
- Every era has shaped some earlier R2-08 choice (wick v2 lab, v3 fresh era, $1M round, wick v4). Relevant earlier
  trials, not repeated here: exits (take-profit share, hold time, stops, a 15-minute passive time exit on the perp
  cost model, B21), thresholds 65–75th percentile and prediction-priority slots (v3), rung weights W1–W4 and a 10σ rung,
  BTC-synchronised re-pricing, 1-second fill detection, 31 coins (v4), the size cap grid ($1M round).
- **Step 1 of this round (diagnosis), before this file:**
  - Oracle bounds and the P&L decomposition on all three eras (aggregate; no rule was fitted):
    reports/ladder_v5/diag_oracles.csv, diag_decomposition.csv.
  - Markouts by fill type on the **selection era only** (Jan 2025 – Mar 2026): reports/ladder_v5/diag_markouts_sel.*.
    The check era (Apr – Nov 2026) and 2022–23 were not split by any of these variables.
  - Two side checks on the selection era only: the 15-minute remainder window (fill-minute sellers only: return
    −1.1 points, Sharpe +0.07, paired t −0.96 at $250K) and the fill-minute selling volume as a brake on the deeper
    rungs (no relation: Spearman +0.10 with the deeper rungs' net). Both are logged as diagnostics, not candidates.
  - The live cash rule (below) on all three eras (research book vs live book, no candidate policy) and on two cascade
    windows against the bot's engine.
  - Trade prints: per-fill statistics for every 2025–26 parent (reports/ladder_v5/prints_parents.csv) and every 2022–23
    parent (prints_parents_early.csv, fetched for C7, same script). Only selection-era fills were compared with
    outcomes (reports/ladder_v5/diag_prints_sel.txt).
- The walk-forward prediction for every minute (data/ladder_v5/panel_*) was rebuilt from the lab pipeline; it equals
  the lab's candidate predictions exactly (max difference 0) and the stored trade lists to 1e-5.

## Frozen simulator, cost model and dataset
- **fsim** (scripts/ladder_v5/fsim.py): scripts/wick1m/sim.py's evaluate with hooks that default to the incumbent.
  Parity with sim.evaluate through scripts/hunt/incumbent.py: maximum daily difference 0.0 (all eras, θ 0.5/0.25,
  $250K/$1M, both latency bounds).
- **hsim** (scripts/ladder_v5/hsim.py): the live bot's cash rule. Coinbase holds cash for every resting spot bid, so
  the bot keeps positions at cost plus all resting bids within equity; each minute the AI-approved coins get 4σ bids in
  prediction order, and deeper rungs only get cash the 4σ bids leave. hsim replays that allocation at minute
  resolution with the walk-forward predictions and passes each tranche's funded size to fsim.
  - Check against the bot's own engine (scripts/ladder_v5/hsim_check.py: engine with the same predictions, paper
    broker, stored candles), results in reports/ladder_v5/hsim_check_*.csv and the table below.
- **Costs:** Coinbase US spot tiers from the book's own 30-day volume (VIP 1 at these sizes: 6 bp maker, 12.5 bp
  taker); 2 bp half-spread and square-root impact (y = 0.7) on market exits. Unverified: the half-spread, the impact
  constant, and anything a candidate adds (perp fees, USDC rewards).
- **Dataset:** reports/ladder_v5/frozen/pre_hunt_{main,early}.pkl (R2-08's out-of-sample trades and ladder
  tranches, sha256 in reports/ladder_v5/frozen/SHA256SUMS), the prediction panel, minute candles in data/.
- **Latency:** the live bot reads fills every second: daily returns = minute bound + s × (instant − minute), with s
  measured in wick v4 per era and θ.
- **Eras:** selection Jan 2025 – Mar 2026, check Apr – Nov 5 2026, fresh 2022–23 (13 coins).
- **Today's volumes:** each coin's size base and fill capacity scaled by today's ADV (paper bot log, Nov 7) / the
  era's median ADV, capped at 1.

## The incumbent
- **Research book** (fsim: positions-only cash, the README's basis), $250K, θ 0.5, 1-second blend: 29.9% / 20.1% /
  14.0% a year (selection / check / 2022–23), the README's returns exactly; Sharpe 2.40 / 2.96 / 2.27 (README 2.28 /
  2.82 / 2.28 came from wick v4's per-tranche 1-second simulation; this round blends daily returns, as the hunt did).
- **Live book** (hsim, the bot's cash rule), base configuration: $250K 22.4% / 17.6% / 13.7%, Sharpe 2.16 / 2.61 /
  2.18; $1M 20.1% / 9.2% / 6.6%, Sharpe 2.43 / 1.56 / 1.20 (reports/ladder_v5/diag_holds.csv).
- **Live book, S\*** (the benchmark for every gate; reports/ladder_v5/cache): θ 0.5: 19.5% / 15.1% / 10.4% a year,
  Sharpe 2.31 / 2.31 / 1.72; θ 0.25: 16.2% / 13.1% / 9.1%, 1.96 / 1.98 / 1.48; at $1M (θ 0.5): 12.1% / 6.9% / 4.7%,
  1.76 / 0.97 / 0.55.
- hsim against the engine (same predictions, stored candles), Oct 10 2025 18:00–06:00 at $250K: parents funded 58 vs
  the engine's 60 of the research's 77; deeper fills 41 vs 37. Jan 31 2026 (a full cascade day): reported in the log
  below when the engine run finishes (an earlier run of the same day: parents 41 vs 39 of 44).

## Leaks and their prizes (step 1)
Oracle replays on the research book (reports/ladder_v5/diag_oracles.csv); Sharpe change at $250K, selection / check /
2022–23, and at $1M:

| Leak | Oracle | $250K | $1M |
|---|---|---|---|
| Exit timing | every rung sells its whole fill at the best minute close within 60 min, as a maker | +3.3 / +3.0 / +1.6 | +2.5 / +3.5 / +1.7 |
| Sizing | losers skipped, winners at twice the size | +2.6 / +2.3 / +1.8 | +2.6 / +3.0 / +2.1 |
| Selection | losers skipped | +2.3 / +2.0 / +1.5 | +1.9 / +2.5 / +1.4 |
| Costs | no fees, half-spread or impact | +1.0 / +1.3 / +0.7 | +1.1 / +1.4 / +0.7 |
| Idle cash | cash not in positions earns T-bills | +0.37 / +0.66 / +0.77 | +0.61 / +1.12 / +1.43 |
| Live cash rule | research book vs live book (base) | +0.24 / +0.34 / +0.09 | +0.08 / +0.04 / 0.00 |
| Queue | all the volume through our bid is ours (θ 1) | +0.10 / +0.16 / +0.13 | +0.19 / +0.32 / +0.16 |
| Latency | every same-minute deeper fill caught | −0.01 / +0.02 / +0.02 | 0.00 / +0.01 / +0.02 |
| Venue | Coinbase US perps as a second venue, 1× costs | −0.01 / +0.25 / 0 | +0.02 / +0.21 / 0 |
| Size cap | no 0.2%-of-ADV cap | −0.49 / −1.37 / −1.04 | −1.75 / −2.09 / −0.97 |

- **Decomposition** ($250K, selection, research book): gross $116K a year; maker fees $17.6K, taker fees $11.6K,
  half-spread $1.9K, impact $5.5K; net $80K (60 bp gross, 41 bp net per $ bought). Half the rung dollars exit at the
  take-profit. Positions average 0.5% of capital; resting bids, not positions, use the cash.
- **The live cash rule.** Most coins are armed most minutes in 2025–26 (80–95% of minutes for 12 of 17 coins; 1–11% in
  2022–23), so at $250K the 4σ bids alone ask for more cash than the account has. The engine gives deeper rungs only
  the cash the 4σ bids leave. In the selection era the live book misses 113 of 1,155 parents and 301 deeper fills;
  return falls 7.5 points (paired t −2.2). At $1M the 0.2% cap keeps bids small relative to cash, and the rule costs
  almost nothing. Per dollar of cash held for a minute, a deeper rung placed after a fill is worth about 100× a 4σ bid
  on another coin (fill odds 45% / 25% within the hour at 46 / 83 bp, against about 1e-4 a minute at 33 bp).
- **Markouts by fill type** (selection era only; reports/ladder_v5/diag_markouts_sel.txt, diag_prints_sel.txt):
  - Who sold to us: fills where the volume through our bid over the next 15 minutes is largest relative to ADV lose
    74 bp net (the top fifth); the rest earn 30–99 bp. A big, persistent seller. But the selling volume of the fill
    minute itself, which the bot knows when it places the deeper rungs, does not predict the outcome (Spearman +0.10).
  - The AI's margin over its threshold: net −4 / 15 / 19 / 52 / 125 bp by fifth, inside every rung. Residual sigma:
    −3 / 6 / 9 / 77 / 125 bp.
  - By rung: 33 / 46 / 83 bp net per $ (4 / 6 / 8σ).
  - Early markouts persist (fills down 166 bp at minute 5 end −69 bp net) but recover 84 bp from minute 5 to 60, so
    stops sell the bottom, as the v2 lab found.
  - BTC's move in the fill minute, sweep depth, the fill minute's volume, cascade breadth and hour: no monotone
    relation worth a hypothesis, except that BTC-up minutes are the best (85 bp), not the worst as wick v4's post-hoc
    lead suggested (a different measure: the whole minute, not minute-start to fill).
  - Who sold to us, from the prints (1,094 parents): the first aggressive order that went through our bid tells a
    forced flush from a grind. When it swept far below our price (top fifth of depth) the parent earned 92 bp net;
    when 227 or more separate aggressive orders hit at or below us in the minute (top fifth), 7 bp; under 10, 68 bp.
    The parent's deeper rungs
    by tercile of that first order's depth: 6σ 15 / 50 / 81 bp, 8σ 17 / 65 / 182 bp. Known within a second of the fill.
  - Who bid beside us: other bids at exactly our price filled before ours in 56% of fills, but a median 0.03× our
    size; printed volume at our exact price is 0.6% of the volume at or below it. We are effectively alone at our
    price, so queue priority there is worth almost nothing; θ (other liquidity arriving below us during the sweep) is
    the competition that matters, and no order-placement rule controls it.
- **The bot's queue.** The paper bot cancels and re-places its 4σ bid almost every minute (391 re-prices in 30 minutes
  across 15 armed coins) and good-til-date bids are renewed every 2.5 minutes, so it never keeps queue priority. Given
  the prints above, that costs little.

## Hypotheses (one per leak; every variant is a logged trial)
Eleven historical trials. Builders implement them on the frozen simulators (reports/ladder_v5/specs/), one gated run
per variant, nothing else first.

| Id | Leak | Rule | Path | Canon / mechanism |
|---|---|---|---|---|
| C1a | Live cash rule | Deeper first: a 6/8σ rung short of cash takes the holds of the lowest-prediction 4σ bids (cancelled); 4σ bids get what is left each minute | return | Value of a resting order per dollar of balance sheet (Moallemi–Yuan's queue value, with cash as the scarce resource) |
| C1b | Live cash rule | 4σ bids may hold at most 50% of equity | return | Same |
| C2a | Selection and sizing | Size × 0.5 / 1.0 / 1.5 by the AI margin's tercile among all earlier parent fills (cutoffs per quarter; × 1 until 60 fills) | return | Meta-labeling: size by the primary model's confidence (López de Prado) |
| C2b | Selection | Same cutoffs; no bid in the bottom tercile | Sharpe | Same |
| C3a | Exit costs | The 60-minute remainder rests 5 minutes as a post-only sell at the previous close + 1 tick, re-pegged, then market | return | Maker vs taker; square-root impact; a passive exit is adversely selected |
| C3b | Exit costs | Same for 15 minutes | return | Same |
| C4 | Idle cash | Cash held as USDC on the alias -USDC books, earning (T-bill − 0.5%) on all USDC, halved in S*; USDC/USD marked to market | return | Seed from the brief; treasury, not trading |
| C5 | Venue | Bids also on the coin's Coinbase US perp; perp fee and half-spread doubled in S*; perp bids hold cash like spot | return | Seed from the brief; no perps before mid-2025, so G2 fails by construction: at most forward-test |
| C6 | Stress | Size × 1.5 when BTC's 60-minute volatility is ≥ 2× its 3-day level (known at t−1) | return | Nagel's evaporating liquidity; Grossman–Miller (weak prior: no monotone stress relation on selection) |
| C7a | Who sold to us | No 6/8σ rungs when the first order through our bid went less far below it than the lower tercile of earlier fills (cutoffs per quarter from earlier parents' prints; × 1 until 60) | return | Grossman–Miller (a forced seller pays for immediacy and reverts) vs Kyle (an informed seller grinds) |
| C7b | Who sold to us | Same cutoffs; 6/8σ rungs × 0.5 / 1.0 / 1.5 by tercile | return | Same; prints for 2022–23 fetched for this test (reports/ladder_v5/windows_early.csv) |

Not tested on history, with reasons: a volume brake on deeper rungs (no relation on selection); dropping the remainder
window (selection: t −0.96); rung weights, BTC-synchronised re-pricing, latency, thresholds, exits' take-profit share and
hold (earlier rounds); queue priority (the prints show no queue at our price; a live check below) and liquidation-feed
sizing (no US-accessible history: a forward log below).

## Gates (scripts/ladder_v5/gates.py)
- Configurations, all at $250K unless stated:
  - **S\***: today's volumes, unverified costs doubled (half-spread 4 bp, impact y 1.4, a candidate's own unverified
    costs doubled or unverified yields halved), fee tier from the book's own volume; θ 0.5 and θ 0.25.
  - **base:** research volumes, 1× costs, θ 0.5.
  - **cap:** S* at $1M (reported; the capacity question).
- **Benchmark:** the live incumbent (hsim, engine policy) in the same configuration.
- **Adopt only if all hold:**
  - G1: pooled paired t ≥ 2 (Newey-West, 5 lags) of daily candidate − incumbent returns, S*, θ 0.5, all three eras.
  - G2: mean difference > 0 in each era, S*, θ 0.5.
  - G3: at θ 0.25, pooled t ≥ 2 and every era > 0.
  - G4: base configuration, pooled mean difference > 0.
  - Then an independent red team re-runs it with its own code, and adopted changes are re-tested together.
- **Paths, declared per candidate before its run:** "return" uses raw daily differences; "Sharpe" uses the
  difference after scaling the candidate to the incumbent's daily volatility (for changes that cut risk more than
  return).
- **Verdicts:** adopt (all gates, red team, joint re-test); forward-test (G1 or the Sharpe path at t ≥ 1 with the
  sign right in every era, or a question history cannot answer); reject (otherwise).

## Live tests where history cannot answer
- **Queue priority (Moallemi–Yuan).** History has no queue. An A/B of sticky vs re-priced bids is not powered: a 10%
  difference in fill rate needs about 1,700 fills per arm. So measure first, in the $10K pilot (no extra risk):
  the live bot already logs the dollars resting at or above our price when it arms (`usd_bids_ahead`). After 50 live
  rungs, compute (a) the share of fills where the minute's low equals our price (touch fills, which need priority) and
  (b) the median dollars ahead at our exact price. Only if (a) ≥ 5% or (b) ≥ our own size, pre-register a sticky-price
  A/B (coin-day randomised, 300 fills, stop at 8 weeks; adopt if fills per armed minute ≥ 1.2× with one-sided p < 0.05
  and markout per $ not worse by > 20 bp).
- **USDC cash (C4), whatever its backtest:** verify before use. With Coinbase One active: preview a post-only bid on
  SOL-USDC with only USDC in the bot's portfolio (must pass), place and cancel a $10 bid far below the market (the hold
  must show on USDC), then after one rewards period compare rewards paid with the expected amount on the average USDC
  balance including holds. Stop: rewards below half the expected amount, any rejected -USDC order, or a rule change
  ending exchange rewards (OCC rule effective Jan 18 2027).
- **Liquidation-feed sizing (seed).** No US-accessible history of per-coin liquidations. Forward shadow log: record a
  US-accessible aggregated liquidation feed (Coinalyze's free API; Hyperliquid's public API as the alternative) at every
  parent fill. After 300 parent fills, test one rule fixed now: size × 1.5 when the coin's long liquidations in the
  prior 5 minutes are at or above their trailing 30-day 90th percentile. Same gates on the shadow P&L.
- **Any change that passes:** a third paper book (paper_spot_v5) runs it beside the incumbent's paper book on the same
  data for ≥ 3 weeks and ≥ 60 rungs before the live bot changes; stop if its mean net per $ is below the incumbent's
  by more than 20 bp after 60 rungs.

## Scorecard (100 points, fixed now)
| Part | Points | Rule |
|---|---|---|
| Evidence | 25 | Pooled paired t at S*, θ 0.5 (on the declared path): ≥ 3 → 25; 2–3 → 18; 1–2 → 8; 0–1 → 3; < 0 → 0 |
| Robustness | 20 | 5 each: all three eras positive at S* θ 0.5 (two → 3); θ 0.25 t ≥ 2 and all eras positive (t ≥ 1 → 3); base positive with t ≥ 1 (positive → 3); the other variant of the same hypothesis (or, if none, the $1M configuration) has the same sign (mixed → 2) |
| Realism | 15 | 5 each: fill model checked on prints (partly → 3); costs published or verified (estimated → 2); the live code path exists and can be parity-tested (needs new venue or infrastructure → 2) |
| Mechanism | 10 | Named mechanism from the canon or market structure 4; the selection-era diagnosis supports it 3; a reason it persists 3 |
| Prize | 15 | Mean Sharpe change across the three eras at S*, θ 0.5: ≥ 0.5 → 15; 0.25–0.5 → 10; 0.1–0.25 → 5; 0–0.1 → 2; ≤ 0 → 0 |
| Implementation and risk | 10 | Keeps every safety check 4; low complexity 3; no new tail risk 3 |
| Capacity | 5 | Sharpe change at $1M (S*): ≥ +0.25 → 5; 0 to +0.25 → 2; < 0 → 0 |

## Deviation log
- 2026-11-07 23:19 UTC (after the freeze, no rule change): the second engine check finished. Jan 31 2026, a full
  cascade day at $250K: parents funded 41 (hsim) vs 39 (engine) of the research's 44; deeper fills 24 vs 24
  (reports/ladder_v5/hsim_check_20260131.csv). With Oct 10 2025 (58 vs 60 of 77; 41 vs 37), hsim tracks the engine.
- 2026-11-07 23:48 UTC (after the freeze; no rule change). fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl, which
  git ignores, so a fresh checkout or Actions runner rebuilds it with sim.precompute instead of reading
  reports/ladder_v5/frozen/. Checked: the rebuilt main and early datasets equal the frozen copies on every column the
  simulators use (only tp_hit's missing-value representation on unfilled rows differs; evaluate never reads it), so the
  C1 run on Actions (no copy step) is unaffected. The builders' runners copy the frozen files into place after checking
  SHA256SUMS.
- 2026-11-07 23:48 UTC. The subagent harness does not let builders write report files; their reports came back as text
  and the coordinator committed them to their branches (reports/ladder_v5/<id>/REPORT.md).
- 2026-11-07 23:48 UTC. Two variants of one hypothesis passed (C3a, C3b). The pre-registration does not say which one
  enters the joint re-test. Decided before the joint run and before the red team reports: C3b, the variant with the
  higher pooled t at S* (+7.71 vs +7.08) and at base (+4.16 vs +3.69); C3a's own trial stands. A reading the
  pre-registration did not spell out: S* doubles the half-spread and impact, which C3 avoids, so for C3 S* is the
  favourable configuration and base the conservative one; its verdict weighs base and the red team's print-based costs.
- 2026-11-07 23:59 UTC. Correction: the four entries above had hand-written times; they now carry their commit
  times (dbcf9cd, 23:19 UTC; fde5f57, 23:48 UTC). From here on the commit time is the record.
- 2026-11-07 23:59 UTC (before any joint trial and before the red-team reports). The joint re-test. Components: the
  candidates that passed G1-G4: C2a, C3b (chosen above) and C4. Logged trials, path "return", the four gate
  configurations, scripts/ladder_v5/cand_joint.py on branch ladder/joint: J_c2a_c3b_c4 and the three sets that leave
  one out (J_c3b_c4, J_c2a_c4, J_c2a_c3b). C4's overlay uses the joint book's own positions (the C2a sizes, plus C3's
  extra minutes while a passive sell rests). The runner first checks that everything off reproduces the incumbent and
  that each component alone reproduces its logged trial, and stops otherwise. Rule: the set put forward is the
  components their red team confirms. It is adopted if (a) it passes G1-G4 against the incumbent and (b) each
  component adds within it: the daily difference between the set and the set without that component, at S* θ 0.5,
  has pooled t ≥ 1 and a positive mean in every era. A component failing (b) is dropped and the smaller set must pass
  (a). Whatever the result, C4 goes live only after the pre-registered USDC verification, and every adopted change
  runs in paper_spot_v5 before the live bot changes.
- 2026-11-08 00:23 UTC (after red team 1, before any re-run of the winners on its replay). Red team 1 found that hsim,
  the frozen simulator of the live cash rule, departs from bot/spot/engine.py in two ways (deeper rungs get cash in
  parent-fill order instead of ladder-creation order; a deeper rung is placed and filled when the market is already at
  or below its level, where the engine defers it). Its engine-faithful replay matches the engine rung by rung on three
  cascade windows and gives a different incumbent: S* θ 0.5 19.9% / 16.4% / 10.2% (hsim 19.5% / 15.1% / 10.4%). The
  gates stay as run (hsim was frozen before any trial). Added check, not a new trial: red team 1 re-runs C2a, C3b, C4,
  J_c3b_c4 and J_c2a_c3b_c4 on its replay against its own incumbent. A winner whose S* θ 0.5 paired t falls below 2
  there, or whose sign flips in any era, is reported as simulator-dependent and drops to forward-test.
- 2026-11-08 00:40 UTC. Verdicts after the red teams, by the rules above (adopt needs all gates, a confirming red team
  and the joint re-test; forward-test needs t >= 1 with every era's sign right, or a question history cannot answer):
  - C3a, C3b: reject. Red team 2 measured the 60-minute market exit on 17.2M Coinbase prints: 3-6 bp per remainder
    dollar at S* (model 16-17); with print costs and print fills C3a/C3b pooled t -0.06 / +0.04, every gate fails, and
    print costs doubled still leave the check era negative. The entry of 23:48 said C3's verdict weighs the red team's
    print-based costs.
  - C2a: forward-test. It reproduces exactly, but red team 2 found out-of-sample t +1.33 (vol-matched +0.02) and, with
    print-measured exit costs, S* t +1.91 (G1 fails) with every era positive. History will not settle it soon (about
    three years of data for t 2 at its effect size), so the forward test is a re-test of the frozen rule on data after
    Nov 5 2026 at the next round, with measured exit costs; adopt only at out-of-sample t >= 2.
  - C4: forward-test. Red team 3 reproduces it to 1e-14 and it does not depend on the exit-cost or cash-rule findings,
    but whether this account is paid (eligibility, holds, alias orders) is a question history cannot answer. The live
    verification (strengthened as red team 3 proposed) decides; the bot gets the option, off by default.
  - C1a: reject (red team 1: +1.40 on an engine-faithful replay). C7b: forward-test by rule only (t +1.51, sign right
    in every era); its prints pattern did not replicate out of sample and it needs a live trades feed: re-test at the
    next round. C1b, C2b, C5, C6, C7a: reject.
  - Joint: the sets passed (a) and (b), but no component is adopted, so nothing is re-tested together and no strategy
    change reaches the live bot or paper_spot_v5.
  - Not candidates, recorded for the incumbent: the frozen exit-cost model overstates the market exit 3-5x, so the
    incumbent is better than the frozen estimate (red team 2, S* theta 0.5 with print costs: 22.5% / 17.7% / 11.4%,
    Sharpe 2.76 / 2.83 / 1.95); hsim's cash rule departs from the engine (red team 1). A safety gap found by red team 1
    (no volume cap for a coin with under 10 days of volume history) is fixed in the bot.

