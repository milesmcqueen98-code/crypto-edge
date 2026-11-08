# Ladder v6 exits: rounds (selection era only)

Each round's hypothesis is written here before the round runs. Every variant run is a row of variants.csv
(selection-era statistics only, S* theta 0.5 unless noted). Levers and rule family: reports/ladder_v6x_prereg.md.

## Round 1: headroom (written 2026-11-08 20:16 UTC, before running)
Hypothesis: hindsight exits are worth a lot (ladder v5 put perfect exits at +3.3 Sharpe), but what is knowable at the
minute is worth little. Prediction: the in-sample fitted rule (6 inputs fitted on the whole selection era, best of
h in {0, 5, 10}) clears the drop bar (selection t >= 1.4) for none of the levers at kappa = 2; at kappa = 1 at most X1
or X12. X2 should fail outright: under print costs a remainder held past 60 swaps a cheap market sale (12.5 + ~4 bp) for
a take-profit fill (6 bp), worth ~11 bp a dollar instead of ~23 under the model, and the price drift after 60 is small.
Runs: oracle (hindsight best exit minute per tranche) for X1 (0-60), X2 (60-120), X12 (0-120) at kappa 1 and 2, X2/X12
with the pessimistic cash bound and, for information, without; in-sample fitted rules per lever, h and kappa bracket.
Drop decisions: X2 now (its costs do not use kappa); X1 and X12 once kappa(m) is measured.

### Round 1 read, first part (2026-11-08 20:25 UTC)
| Lever | Oracle t / dSharpe (kappa 1) | In-sample, all 6 inputs, best h: t (kappa 1 / 2) |
|---|---|---|
| X1 early exit | +4.02 / +1.43 | -1.77 / -2.13 |
| X2 hold to 120, pessimistic cash | +4.35 / +1.82 | +1.79 (h 10; kappa-free) |
| X12 both | +4.78 / +1.93 | +0.54 / +0.32 |
- X2 clears the drop bar (1.4) and goes on. The prediction that X2 fails outright was wrong.
- Diagnostic (selection, S* theta 0.5 instant frame, dollar-weighted gain from holding in bp per remainder dollar):
  holding to 60 pays +80 bp while the price is still below the entry and is strongly negative once the close is above
  the take-profit with part of the remainder unfilled (recovered share > 0.6: -14 to -256 bp). A linear fit cannot
  carve that out, which is why the 6-input fit loses. That region exists because the frozen model fills only
  theta = 0.5 of the volume traded above the take-profit; a live resting order the price trades through would mostly
  be filled, so an exit rule built on it may only re-earn what the model's capacity haircut takes away.
- The drop rule reads "the best rule of its family": before deciding X1 and X12, the in-sample bound is completed over
  every subset of the 6 inputs (63) x h in {0, 5, 10} at kappa 1 and 2 (all logged).

### Round 1 read, completed (2026-11-08 20:33 UTC)
- Best in-sample rule of the family (63 input subsets x 3 hurdles, all logged): X1 t -0.60 at kappa 1 (-1.03 at
  kappa 2); X12 +1.30 (rec + m, h 0) at kappa 1 (+1.12 at kappa 2). Both below 1.4, so both are dropped unless the
  measured kappa(m) is below 1 (then their bound is re-run at the measured kappa). X2 goes on alone.
- X2 in-sample (6 inputs, h 10) on the instant frame: 466 of 907 remainders extended (52% of remainder dollars), 37.5
  minutes on average, 196 to 120. Gain $20.9K = take-profit fills after 60 $10.9K + drift on the part sold at market
  $9.9K + cost change $0.1K (print costs barely move between 60 and 75). By the recovered share at 60, holding every
  remainder to 120 gains +77 bp per dollar when still >= 0.6 k sigma below the entry, +16 between -0.6 and -0.3, about
  0 to +5 above. By quarter: +43 (2025Q1), +31, +7, -7, +7.5 (2026Q1).

## Round 2: X2 walk-forward (written 2026-11-08 20:33 UTC, before running)
Hypothesis: X2's in-sample edge is mostly "a remainder still deep under water at 60 keeps recovering for another
hour", which is one input (the recovered share), so a parsimonious fit should survive walk-forward better than the
6-input fit. 2025Q1, the quarter where holding paid most, only trains, so expect walk-forward t of +0.5 to +1.5.
Variants (OLS, refit quarterly on earlier quarters, 2025Q1 runs the incumbent, pessimistic cash): inputs {all 6},
{rec}, {rec, m}, each at h 0 / 5 / 10. Reference, not a candidate: every remainder held to 120 (a plain hold time,
already tried in wick v2), to separate the state-dependence from the extension itself.

### Round 2 read (2026-11-08 20:41 UTC)
| Variant (walk-forward, pessimistic cash) | t | dSharpe | dret |
|---|---|---|---|
| 6 inputs, h 0 / 5 / 10 | +0.24 / +0.34 / +0.62 | -0.06 / -0.06 / -0.03 | +0.2 / +0.3 / +0.5 pp |
| rec, h 0 / 5 / 10 | -0.51 / -0.61 / -0.99 | -0.16 / -0.15 / -0.13 | -0.5 / -0.5 / -0.8 pp |
| rec + m, h 0 / 5 / 10 | -0.59 / -0.48 / -0.76 | -0.20 / -0.12 / -0.18 | -0.7 / -0.5 / -0.8 pp |
| reference: every remainder held to 120 | +1.07 | +0.36 | +3.85 pp |
- The hypothesis was wrong: the parsimonious fits lose. The "deep under water at 60, keep holding" effect was a
  2025Q1 effect (+164 bp per dollar for recovered share <= -0.6), then -3, -46, -47, +35 in the next four quarters.
- The pessimistic cash bound alone (incumbent's exit, every remainder held 60 more minutes in the cash rule) costs
  -3.5 pp a year (t -1.42): a selective extension must earn that back before it shows a gain. Without it (for
  information only) the 6-input rule reads t +1.04 / +1.22 at h 0 / 10.
- Walk-forward coefficients: breadth is the one stable input (+19.4, +17.5, +18.9, +15.6 bp per coin across the four
  refits); k, BTC and minutes change sign or size; mark and rec move together (collinear).

## Round 3: the cascade is not over (written 2026-11-08 20:41 UTC, before running)
Hypothesis: a remainder should be held past 60 while the cascade is still spreading (other coins' parent fills in the
last 30 minutes), because the dislocation, and its rebound, is still under way; once the market has been quiet for 30
minutes, sell. Breadth plus at most the markout should then carry what the 6-input fit had, with less noise.
Prediction: walk-forward t around +1 with optimistic cash and near 0 under the pessimistic bound, because the
extension happens exactly when cash is scarce (a cascade). Variants (OLS walk-forward, pessimistic cash): inputs
{breadth}, {breadth, mark}, {breadth, rec}, each at h 0 / 5 / 10.
