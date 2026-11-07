# Builder spec: who sold to us (C7a, C7b) — branch ladder/sweep

Read BUILDER_GUIDE.md and reports/ladder_v5_prereg.md first. Two pre-registered trials, logged in this order with
`gates.run` under these names: C7a_sweep_skip, C7b_sweep_tilt, path "return".

## Mechanism and evidence
- Grossman-Miller: a seller who needs immediacy for size pays for it; the price reverts. Kyle: an informed seller
  trades in small pieces over time; it does not revert. Which one hit our 4-sigma bid shows in the first aggressive
  order that traded through it.
- Selection era only (reports/ladder_v5/diag_prints_sel.txt and the step-1 cross-tab): by tercile of how far below our
  price that first order went, the 6-sigma rungs of the parent earn 15 / 50 / 81 bp net per $ and the 8-sigma rungs
  17 / 65 / 182 bp. The check era (2025-26 prints exist) and 2022-23 (prints fetched for this test) are untouched.

## Rule
- D, at the parent's fill: in reports/ladder_v5/prints_parents.csv (main) or prints_parents_early.csv (2022-23),
  `first_sweep_depth_bp`: the prints sharing the timestamp of the first print one tick below our bid (one aggressive
  order), at or below our price; D = how far below our price its lowest print was, in bp.
- Cutoffs: the 1/3 and 2/3 quantiles of D over all earlier parent fills with prints in the same era (`ts` before the
  start of the current calendar quarter). Fewer than 60: multiplier 1 (no change). Parents with no D: multiplier 1.
- **C7a:** the parent's 6/8-sigma rungs are not placed when D is below the lower cutoff; otherwise unchanged.
- **C7b:** the parent's 6/8-sigma rungs at 0.5x below the lower cutoff, 1.0x between, 1.5x at or above the upper cutoff.
- Implementation: `hsim.book(..., deep_mult={(parent ts, coin): multiplier})` (the hook scales only that parent's deeper
  rungs; 0 = not placed). In S*, the rule is the same (D is a price measure, not a volume).
- Live: at the parent's fill, the 1-second loop reads the coin's public trades since the minute's start (one request)
  and finds the first order through our bid. State in the report whether the timestamp grouping is reliable as "one
  order" (Coinbase prints one match per maker order; same-time prints at falling prices are one taker order).

## Report
reports/ladder_v5/sweep/REPORT.md: the off-switch check (deep_mult all 1 reproduces the incumbent exactly), coverage
(parents with D by era), the quarterly cutoffs, the share of deeper rungs suppressed or scaled by era, the gate tables,
and the deeper rungs' net per $ by D tercile in the check era and 2022-23 (the out-of-sample view).
