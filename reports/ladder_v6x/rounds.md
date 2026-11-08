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
