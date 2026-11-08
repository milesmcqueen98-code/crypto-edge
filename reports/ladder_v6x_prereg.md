# Ladder v6, exits: pre-registration

Written before any exit variant was run. Branch ladder/v6-exits (cut from ladder/v5 at 52ec854).

## Goal
Test whether a different exit raises the spot ladder's Sharpe, or its capacity at the same return and Sharpe, now that
the 60-minute market sell is known to cost 3-6 bp on prints instead of the model's 16-17. "No change" is a valid result.
The prize motivating it: perfect exits are worth +3.3 Sharpe (ladder v5 oracle O2, hindsight), and mid markouts keep
rising for an hour after our fills (+14 / +28 / +51 bp at 1 / 5 / 60 min). Already tried and not to be re-run as such:
stops (hurt), passive limit exits (a cost-model artifact, ladder v5 C3), take-profit levels and hold times (noise or
failed out of sample, wick v2).

## Frozen simulator (ladder v5's named simulator for the next round)
- scripts/ladder_v6x/lsim.py: red team 1's engine-faithful cash-rule replay (frozen/rt_live.py, unchanged from
  origin/ladder/redteam 75ecbd3) feeding scripts/ladder_v5/fsim.py; red team 2's print-measured exit costs
  (frozen/c3.py PrintCost on reports/ladder_v5/prints_rt2_{exit,coin}.csv, unchanged from origin/ladder/redteam2)
  applied as red team 1's rt_prints.rem_daily; the ladder v5 frozen dataset (SHA256SUMS).
- Reproduced before anything else (reports/ladder_v6x/reproduce.txt): S* θ 0.5, $250K: 22.79% / 19.05% / 11.14% a
  year, Sharpe 2.935 / 2.661 / 1.913 (selection / check / 2022-23), max daily difference to red team 1's committed
  series 1e-17. The incumbent's tranche frames are cached in reports/ladder_v6x/books/.
- Configurations as in ladder v5: S* (today's volumes, unverified costs doubled) at θ 0.5 and 0.25, base (research
  volumes, 1x), cap ($1M, S*).

## Exit costs at any minute (fixed now)
A market sell of a remainder X USD at minute m after its fill pays the taker fee plus:
- m = 60, 65, 75: the frozen print-measured cost of that tranche (PrintCost offsets 0, 5, 15), as the incumbent.
- other m: the tranche's own minute-60 print cost scaled by kappa(m), the ratio of print-measured cost at minute m to
  minute 60 measured on a selection-era sample (below); for m > 75, kappa = 1 relative to the minute-75 cost.
- no event prints for the tranche (e.g. its take-profit filled in full, so ladder v5 measured no minute-60 exit): the
  coin-era pooled print cost (PrintCost's pooled half-spread and first-X slippage for that coin and era) x kappa(m);
  with no pool either, the frozen model (2 bp half-spread + 0.7 x daily vol x sqrt(X / volume)) x cost_mult, as the
  incumbent's fallback. The exit layer must reproduce the incumbent's book exactly when its rule is "take-profit,
  else market at 60" (check before any variant).
- Measured costs count as verified (1x in every configuration). Until kappa(m) is measured, oracle headroom is shown
  at kappa = 1 and kappa = 2; no rule is iterated before kappa is fixed.
- kappa(m) sample, fixed now: 300 selection-era tranches drawn with numpy seed 6 from the S* θ 0.5 instant-bound frame
  (filled, stratified by rung in proportion), event minutes 2, 5, 10, 20, 30, 45 after the fill plus 60 as reference;
  half-spread and first-X slippage measured from Coinbase prints as red team 2 did (event median; X = the tranche's
  fill at today's volume, as S* sizes it). kappa(m) = median over the sample of cost(m) / cost(60), by minute; with fewer than 100 valid pairs at a
  minute, kappa = 2 there.

## Levers (families fixed now)
- X1, early exit: sell the unsold part at market before minute 60 when a rule says the remaining rebound is not worth
  waiting for; the take-profit keeps resting until then.
- X2, extended hold: keep the unsold part beyond minute 60, take-profit still resting, up to minute 120 at most, then
  market.
- X12: both, as one minute-by-minute hold-or-sell rule.
- The rule family: at each minute m an open remainder is sold at market if the predicted gain from holding (the
  realised value of continuing to the family's horizon, minus selling now, in bp net of costs) is below a hurdle h.
  The prediction is a linear regression with at most 6 inputs, all known at minute m: markout so far, the share of the
  dislocation recovered (markout / (k sigma)), rung depth k, BTC's move since the fill, cascade breadth (coins with a
  research parent fill in the last 30 minutes), minutes since the fill. Refit walk-forward each quarter on all earlier
  quarters' tranche-minutes (the first quarter of an era runs the incumbent's exit); h in {0, 5, 10} bp.
- Cash: an early exit frees cash sooner (ignored: conservative). An extended hold ties it up longer: any X2 or X12 rule
  is also scored with every remainder held its maximum extension in the cash rule (rt_live rem_extra), and that
  pessimistic bound is the one the gates use.

## Iteration on the selection era only (Jan 2025 - Mar 2026)
- At most 5 rounds of hypothesis -> test -> read -> refine. Each round's hypothesis is written in
  reports/ladder_v6x/rounds.md before it runs; every variant run is logged in reports/ladder_v6x/variants.csv
  (selection-era statistics only).
- Round 1 is oracle headroom per lever. A lever is dropped when its in-sample bound cannot clear the gates: the best
  rule of its family fitted on the selection era itself (not walk-forward) scores a selection-era paired t below 1.4
  at S* θ 0.5 (1.4 x sqrt(950 / 455 days) ~ 2, the gate on the out-of-sample eras at equal effect).
- No statistic of any variant on the check era (Apr - Nov 5 2026) or 2022-23 is computed before the freeze commit.

## Freeze, then one read of the out-of-sample eras
- The chosen rule (or none) is frozen in a commit, then read once on the check era and 2022-23.
- Gates (ladder v5's, on the out-of-sample eras): G1 pooled paired Newey-West t >= 2 over check + 2022-23, S* θ 0.5,
  declared path (return unless the rule is declared on the Sharpe path); G2 mean daily difference > 0 in the check era
  and in 2022-23; G3 the same at θ 0.25 (pooled t >= 2, both eras positive); G4 base pooled mean > 0. The selection era
  is reported and carries no weight.
- A rule that passes: an independent red team re-runs it with its own code (including print-measured costs at the
  rule's own exit minutes), then a forward test on data after Nov 5 2026: a paper book running the rule beside the
  incumbent's on the same data, sample size and stop rule fixed before it starts. Adopt only after both.
- Verdicts: adopt (gates, red team, forward test set up); forward-test (G1 at t >= 1 with both out-of-sample eras
  positive, or a question history cannot answer); reject.
- Scorecard: ladder v5's 100-point rubric, with Evidence, Robustness and Prize on the out-of-sample eras.
- A patch to bot/spot only for an adopted change, with parity and fault tests, every safety check kept.

## Deviation log
- 2026-11-08 20:16 UTC (before any exit variant ran; implementation choices the plan left open, scripts/ladder_v6x/exits.py):
  - Exit costs between measured points: kappa(m) linear between measured minutes, kappa(2) for minutes 0-1; between
    60, 65 and 75 the tranche's own frozen costs are interpolated linearly in m (same size).
  - A tranche without event prints whose minute-60 exit the incumbent priced with the frozen model keeps the model
    x kappa(m) at every minute (deviation: the plan said pooled prints, which would break the required parity at 60;
    the model is dearer than prints, so this is conservative). 45 of 3,571 S* theta 0.5 selection tranche-frames.
  - Take-profit fills in the exit layer: an early exit keeps only the take-profit fill that had traded (the incumbent's
    fill, accrued with the USD traded above the take-profit from the touch on); after 60 the order keeps resting and
    gets theta x the later USD above it (x today's-volume factor in S*), shared pro rata among a parent's open tranches.
    Exit at 60 everywhere reproduces the incumbent (max daily difference 5e-20); the exit dataset reproduces the
    frames' take-profit touches and capacities exactly.
  - Decisions run from the close of the fill minute (m = 0) to the horizon minus one.
  - Training rows: open tranche-minutes of the S* theta 0.5 instant-bound incumbent frame; the fitted coefficients
    apply to every configuration and bound. OLS, unweighted.
  - Cash for X2 / X12 under walk-forward: quarters that run the incumbent's exit use the incumbent's frames; fitted
    quarters use the rem_extra = 60 frames (pessimistic), spliced at quarter boundaries.
  - Walk-forward on the out-of-sample eras (deviation, fixed now): each quarter's coefficients are fitted on the
    selection era plus the same era's earlier quarters (no quarter runs the incumbent's exit there). The plan's "first
    quarter of an era runs the incumbent's exit" would have zeroed 3 of the check era's 7 months; within the selection
    era the first quarter (2025Q1) still runs the incumbent's exit.
- Freeze (this entry's commit time is the freeze time). kappa(m) measured (ladder/v6x-kappa): 1.02 / 1.15 / 1.17 /
  1.10 / 1.01 / 1.03 at minutes 2 / 5 / 10 / 20 / 30 / 45; X1 and X12 dropped at round 1 (family bounds at the
  measured kappa -0.72 and +1.32). Rounds run: 4 of 5 (round 5 not needed). Frozen candidate: X2_wf6_h10
  (reports/ladder_v6x/frozen_rule.json), hand scores fixed before the read (scorecard_manual.json). Times in
  rounds.md were hand-typed in earlier commits and are corrected to the commit times.
- 2026-11-08 20:37 UTC (commit 5d7174b, after the freeze 94209a0 at 20:33 UTC): the one out-of-sample read. X2_wf6_h10
  fails G1 (pooled t +0.52 at S* theta 0.5), G2 (check era -0.04 bp a day), G3 (theta 0.25 pooled t +0.60); G4 passes
  (base +0.28 bp a day). Sharpe at S* theta 0.5: check 2.66 -> 2.37, 2022-23 1.91 -> 1.90. Verdict: reject. Nothing
  passed, so no red team and no forward test (the forward-test verdict needs pooled t >= 1 with both eras positive).
  For information after the freeze, the dropped levers' best in-sample specs run walk-forward on the selection era:
  X12 t +0.46 (dSharpe -0.32), X1 +0.16 (-0.27). Scorecard (scorecard.csv): X12 46 and X1 18 on their in-sample
  upper bounds, X2 33 out of sample. No change to the bot, so no patch.
