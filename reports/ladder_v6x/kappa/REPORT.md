# kappa(m): exit cost by minute after the fill (ladder v6 exits)

Returned as text by the measurement agent and committed by the coordinator. Branch ladder/v6x-kappa (final commit
0a70128): code in scripts/ladder_v6x/kappa/, derived numbers in reports/ladder_v6x/kappa/. The workflow edits on that
branch (ladder-fetch.yml, ladder-prints.yml) are for it only and are not merged.

## Method (pre-registered, reports/ladder_v6x_prereg.md)
The 300 selection-era tranches drawn with numpy seed 6 from the S* theta 0.5 instant-bound frame (sample.csv,
stratified by rung 185 / 76 / 39). A sale at minute m is at the close of the candle starting fill_t + m. Red team 2's
measurement, unchanged: half-spread from clean bounces in [T - 5, T + 1) min, first-X slippage of every aggressive
sell order of at least X in [T - 5, T + 5) min, X = the tranche's fill at today's volume, cost as PrintCost.cost
(own data only, no pooled or model fallback). kappa(m) = median over valid pairs of cost(m) / cost(60).

## Result
| m | valid pairs | kappa | median cost(m) bp | median cost(60) bp | dollar-weighted ratio |
|---|---|---|---|---|---|
| 2 | 263 | 1.025 | 2.91 | 2.80 | 1.09 |
| 5 | 262 | 1.147 | 3.55 | 2.80 | 1.31 |
| 10 | 261 | 1.166 | 3.68 | 2.94 | 1.28 |
| 20 | 261 | 1.097 | 3.37 | 2.94 | 1.06 |
| 30 | 257 | 1.015 | 3.49 | 2.81 | 1.16 |
| 45 | 252 | 1.032 | 2.89 | 2.88 | 1.02 |
| 60 | 264 | 1 | 2.80 | 2.80 | 1 |

Every minute has at least 100 valid pairs, so the pre-registered fallback (kappa = 2) never applies. Selling before
minute 60 costs 1-17% more than at 60.

Sensitivity (not used): with windows starting at fill_t + 1 min, kappa(2) = 1.126 (259 pairs, dollar-weighted 1.23);
kappa(5) is unchanged (its windows already start there).

## Coverage and checks
- All 269 merged windows fetched, none failed: 6.48M Coinbase prints; all 300 events have prints; 265-292 events per
  minute have a finite cost (most gaps: fewer than 5 clean bounces for the half-spread).
- The measurement code reproduces red team 2's numbers exactly on synthetic prints, matches their committed minute-60
  rows for the 167 events both samples share, and its costs equal the frozen PrintCost.cost to 1e-14 bp.

## Observations
- Half-spreads are 1.5-1.8x wider for about 10 minutes after the fill; first-X slippage, most of the cost, does not
  widen.
- kappa(2) is below kappa(5) because the minute-2 window still contains the trading burst of the fill minute.
- Three PEPE events have a minute-60 cost of 2e-12 to 2e-9 bp (rounding residue of a zero cost); they inflate the mean
  ratio to about 1e10 and move the median by at most 0.01.
- The four repeated (coin, fill_t) pairs share X and differ only by rung.

Actions runs: fetch 42519311056, analysis 42520539601 (raw prints in that run's artifacts, 14-day retention).
