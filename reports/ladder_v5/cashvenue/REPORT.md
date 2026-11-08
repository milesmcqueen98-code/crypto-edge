# Ladder v5, cash and venue: C4_usdc and C5_perp_venue

Builder's report, returned as text (the subagent harness does not let builders write report files) and committed by
the coordinator. Branch ladder/cashvenue, cut from the freeze commit 7ae53cb. Spec: reports/ladder_v5/specs/cash_venue.md.
Both pre-registered trials were logged by gates.run, in this order, in one Actions job (run 42426015923):
reports/ladder_v5/trials.csv (C4_usdc 23:39:33Z, C5_perp_venue 23:41:15Z, 2026-11-07) and trials/<name>.json. Before
that, the only runs were the off-switch checks below and one code-path test with synthetic perp capacity (1e-9 x spot;
within 1.5e-12 of the incumbent, so it reveals nothing about C5). Code: scripts/ladder_v5/cand_cashvenue.py. USDC
fetch: scripts/ladder_v5/fetch_usdc_ext.py. Post hoc: scripts/ladder_v5/cashvenue_posthoc.py, committed before the
trials ran. Outputs: reports/ladder_v5/cashvenue/.

## Result

| Trial (path "return") | G1: pooled t, S θ0.5 | G2: every era > 0 | G3: θ0.25 | G4: base | Gates |
|---|---|---|---|---|---|
| C4_usdc | +3.06 pass | pass (+0.47 / +0.43 / +0.42 bp a day) | pass (t +3.06) | pass (t +6.07) | pass |
| C5_perp_venue | −1.93 fail | fail (sel −, chk −, 2022-23 zero) | fail (t −1.12) | pass (t +1.94) | fail |

- **C4 passes all four gates.** The gain is a treasury yield, not trading. Under the prereg it goes next to the red team
  and the joint re-test, and whatever the backtest says it must pass the prereg's live verification before use: USDC on
  hold for orders earns rewards, -USDC orders are accepted, and the rules after the OCC's GENIUS Act rule (effective
  Jan 18 2027). The risk it adds is the USDC peg.
- **C5 fails G1-G3.** Its pre-registered ceiling was "forward-test", and it does not meet the forward-test conditions
  on its declared path either (G1 fails, vol-matched t −0.63, S* negative in both eras that have perps): reject. Its
  sign follows the unverified perp costs: negative with them doubled (S*), positive at 1x (base, chk +0.71 points,
  t +2.58). That cost question is answered by verifying fees and spreads, not by a forward test of the strategy.

## Rules as implemented

**C4_usdc.** Trading is the live incumbent, unchanged (hsim.book exactly as gates.py calls it; the -USDC products are
aliases of the -USD books, so fills do not change). Added to the incumbent's daily return:
(r_usdc(t) + m(t)) x (1 − positions_t / C), where
- r_usdc(t) = max(0, T-bill(t) − 0.5%) / 365 (edge.book.rf_daily), × 0.5 wherever cost_mult == 2 (S θ0.5, S θ0.25 and
  cap $1M), × 1 in base. Scenario A: the reward is earned on all USDC, including USDC on hold for resting bids.
- m(t) = Bitstamp usdcusd daily close(t) / close(t−1) − 1: daily candles from the frozen
  data/ladder_v5/usdc_usd_bitstamp.csv (2022-01-01 .. 2024-09-26), then the new data/ladder_v5/usdc_usd_bitstamp_ext.csv
  (2024-09-26 .. 2026-11-05; fetched on Actions, one request, HTTP 200, 771 days, no gaps, plain research User-Agent;
  the day both files share is identical). A day with no candle counts as 1.0 (only 2021-12-31: −0.4 bp on 2022-01-01).
- positions_t = the day's time-average of open positions at cost, from hsim.book's instant-bound Q (each fill's
  take-profit part from the fill minute to its take-profit, the rest to the 60-minute exit).

**C5_perp_venue.** hsim.book with (1) in_perp, tp_perp = in_perp_raw, tp_perp_raw before the era window and the
today's-volume scaling, so fsim.evaluate splits each order across spot and perp by capacity; (2) sim.perp_cost's fee and
1.5x measured half-spread doubled when cost_mult == 2 (patched only around the fsim.evaluate call; fsim's hard-coded
+1 bp perp entry term is not doubled); (3) the live cash rule with perp fills counted as positions (hsim.run's frozen
source with four asserted line edits applied in-process; no file changed; holds unchanged; with no perp capacity it
reproduces hsim.run exactly).

## Off-switch checks
- Local, chk era, S θ0.5, 219 days, in the environment that built the incumbent cache: C4 with rate 0 and no USDC mark
  0.0; C5 with perp capacity 0, 0.0 (offswitch_chk_S_0.5.json).
- In the gated job on Actions (diag.json): C4's trading part equals the cached incumbent to within 1.9e-17 a day in
  all 12 era x configuration cells; C5 in 2022-23 (no perp capacity) within 7.8e-18 — floating-point differences
  between the runtime and the machine that built the cache. C5's 2022-23 per-era t values (−2.40, +2.41, −2.45,
  −2.40) are t-statistics of that noise and mean nothing.

## Gate tables ($250K unless stated; mean difference in bp of capital a day)

**C4_usdc.** Pooled t: S θ0.5 +3.06, S θ0.25 +3.06, base +6.07, cap $1M +3.07. Vol-matched: +0.95 / +1.01 / +4.23 / +0.44.

| Config | Era | Incumbent ret / Sharpe | C4 ret / Sharpe | Δ ret / Δ Sharpe | Mean diff | Era t |
|---|---|---|---|---|---|---|
| S θ0.5 | sel | 19.5% / 2.31 | 21.2% / 2.56 | +1.72 pt / +0.25 | +0.470 | +25.3 |
| S θ0.5 | chk | 15.1% / 2.31 | 16.6% / 2.63 | +1.57 pt / +0.32 | +0.431 | +10.9 |
| S θ0.5 | 2022-23 | 10.4% / 1.72 | 11.9% / 1.72 | +1.55 pt / −0.00 | +0.424 | +1.5 |
| S θ0.25 | sel / chk / 2022-23 | 16.2 / 13.1 / 9.1%; 1.96 / 1.98 / 1.48 | 17.9 / 14.7 / 10.7%; 2.23 / 2.31 / 1.51 | | | +25.3 / +10.9 / +1.5 |
| base | sel / chk / 2022-23 | 22.4 / 17.6 / 13.7%; 2.16 / 2.61 / 2.18 | 25.9 / 20.7 / 16.8%; 2.57 / 3.21 / 2.43 | | | +48.1 / +21.7 / +3.0 |
| cap $1M | sel / chk / 2022-23 | 12.1 / 6.9 / 4.7%; 1.76 / 0.97 / 0.55 | 13.8 / 8.5 / 6.3%; 2.13 / 1.44 / 0.76 | | | +25.3 / +10.9 / +1.5 |

**C5_perp_venue.** Pooled t: S θ0.5 −1.93, S θ0.25 −1.12, base +1.94, cap $1M −1.16. Vol-matched: −0.63 / −0.44 / +1.08 / −0.30.

| Config | Era | Incumbent ret / Sharpe | C5 ret / Sharpe | Δ ret / Δ Sharpe | Mean diff | Era t |
|---|---|---|---|---|---|---|
| S θ0.5 | sel | 19.5% / 2.31 | 18.9% / 2.27 | −0.60 pt / −0.04 | −0.163 | −1.57 |
| S θ0.5 | chk | 15.1% / 2.31 | 14.7% / 2.24 | −0.40 pt / −0.07 | −0.109 | −1.39 |
| S θ0.5 | 2022-23 | 10.4% / 1.72 | 10.4% / 1.72 | 0 | 0 | (noise) |
| S θ0.25 | sel / chk | 16.2 / 13.1%; 1.96 / 1.98 | 15.7 / 13.2%; 1.91 / 1.99 | −0.49 / +0.05 pt | −0.135 / +0.013 | −1.27 / +0.15 |
| base | sel / chk | 22.4 / 17.6%; 2.16 / 2.61 | 22.4 / 18.3%; 2.15 / 2.74 | +0.02 / +0.71 pt | +0.005 / +0.195 | +0.17 / +2.58 |
| cap $1M | sel / chk | 12.1 / 6.9%; 1.76 / 0.97 | 11.9 / 6.7%; 1.74 / 0.93 | −0.15 / −0.21 pt | −0.042 / −0.059 | −1.45 / −0.53 |

## What drives the result

### C4
- **Reward vs mark** (S θ0.5, $250K): the reward adds +1.75 / +1.57 / +1.54 points a year ($4.4K / $3.9K / $3.9K) in
  sel / chk / 2022-23; in base +3.49 / +3.14 / +3.08 points ($8.7K / $7.9K / $7.7K). The USDC mark adds −0.03 / +0.00
  / +0.01 points. Open positions average 0.38% / 0.27% / 0.13% of capital (busiest day 8.9%).
- **The depeg** (Mar 11 2023): usdcusd closed at 0.96853 after 0.99773, a −2.93% mark: −$7,312 at $250K. Mar 10-15:
  −$549, −$7,312, +$5,937, +$1,007, +$645, +$372, net +$100. The daily mark sees only closes; the intraday low was
  0.80526 (07:00 UTC), about −$48K at $250K. Mar 11-12 2023 carry 89% of the variance of C4's daily differences: they
  hold the 2022-23 era t to +1.5 and the pooled t to +3.06, and leave the 2022-23 Sharpe unchanged (1.72), while sel
  and chk gain +0.25 and +0.32. Descriptive aside, not a trial: excluding Mar 10-15 2023 the pooled t would be 10.7.
- **Coinbase One vs the reward:** the tiers cost $49.99 / $299.99 / $2,999.99 a year (Basic / Preferred / Premium), all
  listing 3.5% USDC APY (MEXC News, Feb 20 2026). Scenario A's reward at $250K is $3.9-4.4K a year at S* (halved) and
  $7.7-8.7K in base; at the published 3.5% / 3.75% it would be $8.7K / $9.3K. Basic costs about 1% of the S* reward.
  The subscription is not deducted in the trial.
- **Scenario B** (post hoc, not a trial: rewards only on USDC not on hold for resting bids): 43% / 41% / 3% of capital
  is on hold on average at S θ0.5 (most coins are armed most minutes in 2025-26). The reward falls to $2.4K / $2.3K /
  $3.7K a year; returns 20.4% / 16.0% / 11.9%, Sharpe 2.45 / 2.50 / 1.71, pooled t +2.34 (A: +3.06). In base, 69% /
  49% / 3% on hold, pooled t +3.95 (A: +6.07).

### C5
- Perp share of filled dollars (instant / minute bound), S θ0.5: sel 5.6% / 5.7%, chk 26.3% / 27.3%, 2022-23 0. Perp
  capacity in this data starts Aug-Sep 2025 (ETH, SOL, XRP) and Dec 2025 - Mar 2026 for most other coins.
- Costs (S θ0.5, chk, instant bound, whole era), net −$0.6K: gross +$0.4K; taker fee −$0.3K (perp fee below spot's
  12.5 bp taker); maker fees +$0.8K (perp entry 2x fee + 1 bp vs spot's 6 bp, take-profit 2x fee); half-spread +$0.5K;
  impact +$0.1K. At 1x perp costs (base) the same mechanics net +$0.9K.
- Cascade days (% of capital vs the incumbent): Oct 10 2025 −0.40% (fill moves to the perp, whose take-profit capacity
  is thinner, so more exits at 60 minutes as a taker); Oct 23 2026 +0.07% (ENA and ONDO perp capacity filled rungs spot
  could not).
- Late deeper fills keep the research's perp capacity (hsim.with_live_fills refreshes only spot columns): 0.4-1.6% of
  perp dollars at the instant bound, 6-9% at the minute bound, up to 15% in base. Not enough to change the sign.

## Things that looked wrong or ambiguous
1. fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl (gitignored); the runner copies the frozen pickles there after
   checking frozen/SHA256SUMS.
2. data/ladder_v5/* is frozen, so the fetched history went into a new file (usdc_usd_bitstamp_ext.csv). The frozen CSV
   mixes hourly candles (Mar-Apr 2023) with daily ones; the mark uses only the daily candles.
3. The mark is applied to C minus positions, the same balance as the reward. Coinbase's own 1:1 USD/USDC conversion,
   which it paused over the Mar 11 2023 weekend, is not modelled.
4. C5's cash rule: resolved with the in-process edits above.
5. C5 splits every order by capacity even when spot alone would fill it (the research rule, as specified); a
   cost-aware router would be a new hypothesis and was not tested.
6. Environment noise: hsim on Actions reproduces the locally built cache to about 1e-17; era t values for an era with a
   structurally zero difference (C5 in 2022-23) are noise.

## Scorecard (builder's proposal for the hand-scored rows)

| Part (points) | C4_usdc | C5_perp_venue |
|---|---|---|
| Evidence (25) | 25 | 0 |
| Robustness (20) | 20 | 10 |
| Realism (15) | 7 | 4 |
| Mechanism (10) | 8 | 7 |
| Prize (15) | 5 | 0 |
| Implementation and risk (10) | 7 | 0 |
| Capacity (5) | 5 | 0 |
| **Total** | **77** | **21** |
