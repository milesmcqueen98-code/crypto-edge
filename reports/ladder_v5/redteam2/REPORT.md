# Red team 2 (ladder v5): C2a partly confirmed, C3a/C3b not confirmed

Returned as text by the red team and committed by the coordinator. Branch ladder/redteam2: code in
scripts/ladder_v5/redteam2/, results in reports/ladder_v5/redteam2/ (one-page summary in tables.txt). Own C2a and C3
code from the specs and the pre-registration; the builders' reports read only afterwards. Only the frozen fsim, hsim,
gates and data were used. Nothing logged to trials.csv.

## Claim 1: C2a margin terciles. Partly confirmed.
- **Reproduces exactly.** S* theta 0.5 pooled t +2.21 (vol-matched +1.04); return / Sharpe selection 19.5% / 2.31 ->
  22.4% / 2.65, check 15.1% / 2.31 -> 15.7% / 2.28, 2022-23 10.4% / 1.72 -> 11.6% / 1.84; theta 0.25 +2.06, base +1.63,
  $1M +3.04; G1-G4 pass. With the multiplier fixed at 1 it matches the incumbent exactly.
- **Out-of-sample evidence on its own (check + 2022-23 pooled) is below the bar of 2.** Return-path t / vol-matched t:
  S* theta 0.5 +1.33 / +0.02; S* theta 0.25 +1.55 / +0.71; base +0.53 / -2.36; $1M +1.73 / +0.91. Era t: check +0.38,
  2022-23 +1.30. Sharpe change at S*: -0.03 (check), +0.12 (2022-23); at base -0.19 and -0.32.
- **A few days carry it.** In the check era the gain totals +38 bp of capital; the five best difference days give +185
  bp. Without the five best and five worst days: check -70 bp (t -1.51), 2022-23 +25 bp (t +0.36), selection +275 bp
  (t +2.71).
- **The margin is informative, mainly in the top tercile.** Incumbent net return per dollar by tercile (bottom /
  middle / top): check 20 / 23 / 118 bp; 2022-23 33 / 7 / 143 bp. C2a buys 7-15% fewer dollars than the incumbent.
  Post-hoc placebos (not trials): inverse sizing (1.5 / 1 / 0.5) t -3.55; random buckets with the same shares -3.01;
  C2a minus random +3.37 (out of sample +2.35); C2a minus a constant same-mean size +2.63 (+1.98); top only x1.5 +2.74
  (vol-matched +0.25); bottom only x0.5 -0.44 (out of sample -1.78).
- **New: C2a's gate pass depends on the frozen exit-cost model.** With print-measured exit costs in both books: S*
  theta 0.5 pooled t +1.91 (G1 fails), theta 0.25 +1.76 (G3 fails), base +1.46, $1M +2.75; out of sample +1.16
  (vol-matched -0.39). 98.6-99.9% of C2a's remainder dollars have prints; the rest keep the model cost.

## Claim 2: C3a / C3b passive exit. Not confirmed.
- **Inside the frozen model it replicates.** N = 0 matches the incumbent (difference 3e-16). Own version (exit paths at
  the live fill minute, capacity shared within a coin-minute): C3a S* t +6.88, base +3.61; C3b +7.53 and +4.01 (builder
  +7.08 / +3.69 and +7.71 / +4.16). A cash-hold upper bound (the whole remainder held N more minutes in an in-memory
  copy of hsim) costs the incumbent 0.0-0.2 bp a day; C3 under model costs stays +5.86 / +6.19 at S*.
- **Prints.** 2,143 windows, 17.2M Coinbase prints, all 2,053 remainder exits covered, no failed windows. bp per
  remainder dollar, dollar-weighted, selection / check / 2022-23:

| Item | Model | Prints |
|---|---|---|
| Half-spread | 2 (4 in S*) | 0.95 / 0.83 / 1.81 (event medians 0.57 / 0.64 / 1.48) |
| Impact, S* sizes | 12.4 / 13.1 / 13.3 | 1.3 / 1.7 / 2.6 at that era's depth; 3.6 / 2.2 / 3.8 at today's depth |
| Impact, base sizes | 6.1 / 6.6 / 6.6 | 2.6 / 2.1 / 3.6 |
| Total, S* | 16.4 / 17.1 / 17.3 | 4.5 / 3.0 / 5.7 |
| Total, base | 8.1 / 8.6 / 8.6 | 3.5 / 2.9 / 5.4 |
| Total, $1M | 17.8 / 20.6 / 18.3 | 5.6 / 5.3 / 6.7 |

  - Impact from prints: the slippage below the best bid of the first X dollars of every observed aggressive sell of at
    least X within +/- 5 minutes, X = the remainder's size, i.e. what a market sell of that size paid at those
    instants. Implied impact constant 0.19-0.39 (model 0.7; 1.4 in S*). Measured against the minute-60 close with the
    last print's side, the S* total is 2.5 / 2.5 / 4.9. For about half of remainder dollars an observed aggressive sell
    at least as large took its size within 2 bp of the bid. Sizes larger than any observed order are charged the larger
    of a linear extrapolation and the model's 1x impact (0.8-32% of dollars, mostly 2022-23 and base).
- **The passive fill model is about right, slightly optimistic.** Resting minutes with a one-tick trade-through: candles
  76 / 69 / 66%, prints 78 / 72 / 68%. USD above the peg: 93 / 95 / 88% of the formula (96 / 96 / 95% with the real
  tick). A fill needs a print one tick through the peg, so queue place is irrelevant. Not modelled: in 7-9% of minutes
  the bid was already at or above the peg at the minute's first print (a post-only order would be rejected).
  exit_paths uses the coarser perp tick (ETH 0.5 vs spot 0.01); small in aggregate.
- **C3 with print costs (1x, both books) and print fills (real tick, shared capacity):** C3a pooled t S* theta 0.5
  -0.06 (eras +1.17 / -1.71 / +0.18), theta 0.25 -0.62, base -0.40, $1M +0.72; C3b +0.04, -0.58, -0.23, +0.76. Both
  fail every gate. Per remainder dollar C3a is +1.2 / -4.9 / +0.7 bp against the market exit. Print costs doubled
  (stress): C3a +2.82, C3b +3.10, but the check era is negative (G2, G3 fail). Print costs plus the cash hold: -0.57 /
  -0.53. The cost model drives the result, not the fill model: model costs with print fills give +5.6-6.1; print costs
  with candle fills +1.75 / +1.90.

## Side finding
The frozen exit costs understate the incumbent itself. With print costs the live incumbent at S* theta 0.5 earns
22.5% / 17.7% / 11.4% (Sharpe 2.76 / 2.83 / 1.95), against the frozen 19.5% / 15.1% / 10.4%.

## Claim 3: joint test
C3 does not survive, so there is no C2a + C3 joint to run.

## Commits (ladder/redteam2)
34859a6 print windows and fetch script; b4f475f C2a and placebos, incumbent dump; 824eb57 C3 re-implementation and
print analysis; b6cbff4, b9d05cc cash-hold sensitivity; a937e50 print-derived tables (ladder-prints workflow,
reports/ladder_v5/prints_rt2_*.csv); e4131c5 C3 with print costs and fills; 4721d9d C2a with print costs; 81d3bd7 hold
plus prints and the summary tables. .github/workflows/ladder-fetch.yml is changed on this branch only (do not merge).
Raw prints: Actions artifacts of run 42427293772 (14-day retention).
