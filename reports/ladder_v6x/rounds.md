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
