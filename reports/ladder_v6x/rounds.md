# Ladder v6 exits: rounds (selection era only)

Times are the commit times of each entry (git log); hand-typed times in earlier commits were corrected to them.

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

### Round 1 read, first part (2026-11-08 20:19 UTC)
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

### Round 1 read, completed (2026-11-08 20:21 UTC)
- Best in-sample rule of the family (63 input subsets x 3 hurdles, all logged): X1 t -0.60 at kappa 1 (-1.03 at
  kappa 2); X12 +1.30 (rec + m, h 0) at kappa 1 (+1.12 at kappa 2). Both below 1.4, so both are dropped unless the
  measured kappa(m) is below 1 (then their bound is re-run at the measured kappa). X2 goes on alone.
- X2 in-sample (6 inputs, h 10) on the instant frame: 466 of 907 remainders extended (52% of remainder dollars), 37.5
  minutes on average, 196 to 120. Gain $20.9K = take-profit fills after 60 $10.9K + drift on the part sold at market
  $9.9K + cost change $0.1K (print costs barely move between 60 and 75). By the recovered share at 60, holding every
  remainder to 120 gains +77 bp per dollar when still >= 0.6 k sigma below the entry, +16 between -0.6 and -0.3, about
  0 to +5 above. By quarter: +43 (2025Q1), +31, +7, -7, +7.5 (2026Q1).

## Round 2: X2 walk-forward (written 2026-11-08 20:21 UTC, before running)
Hypothesis: X2's in-sample edge is mostly "a remainder still deep under water at 60 keeps recovering for another
hour", which is one input (the recovered share), so a parsimonious fit should survive walk-forward better than the
6-input fit. 2025Q1, the quarter where holding paid most, only trains, so expect walk-forward t of +0.5 to +1.5.
Variants (OLS, refit quarterly on earlier quarters, 2025Q1 runs the incumbent, pessimistic cash): inputs {all 6},
{rec}, {rec, m}, each at h 0 / 5 / 10. Reference, not a candidate: every remainder held to 120 (a plain hold time,
already tried in wick v2), to separate the state-dependence from the extension itself.

### Round 2 read (2026-11-08 20:24 UTC)
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

## Round 3: the cascade is not over (written 2026-11-08 20:24 UTC, before running)
Hypothesis: a remainder should be held past 60 while the cascade is still spreading (other coins' parent fills in the
last 30 minutes), because the dislocation, and its rebound, is still under way; once the market has been quiet for 30
minutes, sell. Breadth plus at most the markout should then carry what the 6-input fit had, with less noise.
Prediction: walk-forward t around +1 with optimistic cash and near 0 under the pessimistic bound, because the
extension happens exactly when cash is scarce (a cascade). Variants (OLS walk-forward, pessimistic cash): inputs
{breadth}, {breadth, mark}, {breadth, rec}, each at h 0 / 5 / 10.

### Round 3 read (2026-11-08 20:24 UTC)
| Variant (walk-forward, pessimistic cash) | t (h 0 / 5 / 10) | for information: optimistic cash, best h |
|---|---|---|
| breadth | -1.15 / -1.15 / -1.15 | +0.39 |
| breadth + mark | -0.67 / -0.40 / -0.14 | +0.87 (h 10) |
| breadth + rec | -1.51 / -1.07 / -1.00 | +0.79 (h 10) |
- Wrong again: breadth's coefficient was stable but its walk-forward gain is not (-3, +7, +5, -1 bp per remainder
  dollar by quarter for breadth alone). As predicted, the pessimistic cash bound sinks it: extensions cluster in
  cascades, exactly when cash is short.
- Best so far on the gate's terms: round 2's 6-input fit at h 10, t +0.62.

## Round 4: fit the objective (written 2026-11-08 20:24 UTC, before running)
Hypothesis: the unweighted fit lets small tranches set the coefficients while P&L is dollar-weighted; weighting the
fit by remainder dollars (WLS) should improve the walk-forward result of the 6-input fit, by at most a few tenths of t.
Variants: 6 inputs, WLS by remainder USD, h 0 / 5 / 10; and the three inputs whose sign never changed across the
round-2 refits (mark, rec, breadth), OLS and WLS, h 0 / 5 / 10. Walk-forward, pessimistic cash.

### Round 4 read (2026-11-08 20:25 UTC)
| Variant (walk-forward, pessimistic cash) | t (h 0 / 5 / 10) |
|---|---|
| 6 inputs, WLS | +0.18 / +0.56 / +0.31 |
| mark + rec + breadth, OLS | -0.56 / -0.72 / -0.21 |
| mark + rec + breadth, WLS | +0.13 / +0.16 / +0.14 |
- No gain from weighting or from keeping only the sign-stable inputs. Every X2 variant on the gate's cash terms sits
  between t -1.5 and +0.6, and every one lowers the selection Sharpe (dSharpe -0.03 to -0.20).
- Decision: no round 5 for X2. Nothing in rounds 2-4 points to a refinement that is not a fishing trip, and the best
  variant (round 2: 6 inputs, OLS, h 10; t +0.62, dret +0.5 pp, dSharpe -0.03, vol-matched t -0.44) is far below what
  the out-of-sample gate needs (selection t of about 1.4 at equal effect). It is frozen as the round's one candidate
  so the out-of-sample eras give it a single honest read. X1 and X12 stay dropped unless the measured kappa(m) is
  below 1 (X12's family bound was +1.30 at kappa 1); round 5 is kept for that case only.

### Round 1, final: kappa(m) measured (see the freeze commit for the time)
kappa(m), the median ratio of a market sale's print-measured cost at minute m to minute 60 on the 300 pre-drawn
selection tranches (252-264 valid pairs per minute; branch ladder/v6x-kappa): 1.02 (2 min), 1.15 (5), 1.17 (10),
1.10 (20), 1.01 (30), 1.03 (45). Selling early costs 1-17% more than at minute 60 (median minute-60 cost 2.8 bp), so
nothing reopens X1 or X12. Family bounds at the measured kappa: X1 -0.72, X12 +1.32 (rec + m, h 0). Both dropped.

## Freeze
The round's one candidate, round 2's "X2 wf mark+rec+k+btc+breadth+m h10", is frozen in
reports/ladder_v6x/frozen_rule.json with its hand scores (reports/ladder_v6x/scorecard_manual.json) before any
out-of-sample number is computed. Selection era (walk-forward, pessimistic cash): S* theta 0.5 t +0.62, dret +0.50 pp,
dSharpe -0.03 (vol-matched t -0.44); theta 0.25 +0.45; base -0.88; $1M +1.05.
