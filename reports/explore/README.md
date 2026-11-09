# Explore v1 (Nov 9 2026): 4,691 variants of the R2-08 spot ladder — no winner

**Result: no winner.** The bot keeps its current ladder, and no new paper book opens.
- **In-sample** (Jan 2025 - Mar 2026): the best variant reached a Sharpe of 4.03; the incumbent made 2.40.
- **Out of sample,** read once: that variant made 0.03 (Apr - Nov 5 2026) and 1.70 (2022-23). The incumbent made 2.96
  and 2.27.
- **All 7 finalists failed.** Scores 21-53 /100; every Holm-adjusted p is 1.0.

Final report: the "Explore v1: Search Report" doc (https://claude.ai/artifact/4xNUYDdWCrBEfdh6LJ1Mbz).

## Setup
- **Plan:** prereg.md, committed at f6d5512 before any variant ran. Its deviation log has three entries, all before the
  read.
- **Simulator:** xsim (scripts/explore/xsim.py), a generalized wick_v4 rungs.py.
  - Spot-only capacity, theta 0.5, the simulator's costs.
  - The live-like blend of the minute and instant books.
  - Parity with rungs.py: 2e-17 (parity.txt).
- **Search, on the selection era only:**

  | Round | Variants | What |
  |---|---|---|
  | 1 | 1,060 | One-at-a-time changes and 1,000 random combinations of 12 assumptions |
  | 2 | 444 | Neighbours of round 1's top 20 |
  | 3 | 3,157 | New assumptions (sigma floor, deeper-bid timeout, cancel on recovery, finer holds), a pruned random search and family searches |
  | 3b | 30 | The literature scan's expressible ideas (literature.md) |

- **Freeze:** 0970362. Holdout read: 6044004.

## Selection era (in-sample)
- 68% of variants beat the incumbent; the best reached 4.03.
- **Multiple-testing checks** (analysis.txt, dsr.txt): SPA p 0.067 against the incumbent; StepM 0 significant; deflated
  Sharpe of the improvement 0.02-0.24 (N = 4,691).
- **Within-era resampling was too hopeful:** PBO 0.23, and CSCV retention of 35-57% of the gain
  (select_rules_r123.txt).

## Holdout, read once (holdout.txt)
ΔSharpe against the incumbent, blended at $250K:

| Finalist | Selection | Check | 2022-23 | Score /100 |
|---|---|---|---|---|
| Best geometry (4/5/6/8/10/12 sigma, weights rising with depth) | +0.21 | +0.00 | +0.41 | 53.0 |
| Best single change (sigma floor 55 bp) | +0.97 | -1.31 | -0.60 | 28.3 |
| Best exits | +0.97 | -1.12 | +0.09 | 27.0 |
| Robust | +1.61 | -2.38 | -0.95 | 23.3 |
| Ensemble (top 10) | +1.71 | -2.72 | -0.78 | 22.3 |
| Best | +1.63 | -2.92 | -0.57 | 22.0 |
| Best filters | +1.40 | -1.69 | -0.76 | 21.0 |

- **Cross-checks:** the sigma-floor cells, and ladders with a 10-sigma rung, match the legacy simulator to 1e-17 in all
  three eras (indep_sigma_*.txt, indep_geometry.txt).

## Post hoc (information only)
Files: posthoc_attr.txt, posthoc_panel.txt, posthoc_rotate.txt.
- **Why the finalists failed:**
  - Low-sigma signals lost 10 bp per dollar in-sample but made 28 / 31 bp out of sample.
  - Strictness-cut signals made -0.5 bp, then +25 / +33 bp.
  - Late deeper fills made 26 bp, then 35-71 bp.
- **Every variant on the holdout:**
  - In-sample rank did not carry: Spearman -0.05 (check), +0.20 (2022-23).
  - The incumbent beat 94% / 91% of the variants.
  - Only more depth beat it in all three eras, by at most +0.18. Examples: 4/5/7/10 sigma, 4/5/6/8/10/12 sigma, W2.
- **Rotation:** tuning on two eras and scoring the third still lost to the incumbent in two of three rotations.

## W2 on the engine-faithful simulator (post hoc)
Branch explore/v1-ef (from ladder/v6-exits): scripts/explore_ef/ and reports/explore_ef/.
- **Simulator:** ladder v6's frozen one (resting-bid cash rule, print-priced exits, 1-second blend). Rung weights were
  added in a copy of the replay; with thirds it matches the frozen replay to 1.6e-17.
- **Result:** W2 (rungs 1:1:2, the paper book) beat the incumbent in all 12 cells (4 configurations x 3 eras), by
  +0.01 to +0.30 Sharpe (w_check.txt).
  - Best estimate at $250K: +0.18 / +0.13 / +0.18.
  - Paired t: +0.54 / +0.73 / +1.24.
  - Still ahead without each book's best 5 days (w_paired.txt).
- **Marked-to-market drawdown is no worse** (mtm_check.txt). Oct 10 2025: -15.7% vs -15.3% (minute book), -16.3% vs
  -16.9% (instant).
- **Not fresh evidence:** W2 was picked post hoc in wick v4.

## Next test
prospective_prereg.md, written before its data exists:
- two deeper ladders, read once on Nov 10 2026 - Mar 31 2027 against the incumbent and W2;
- a sign check, not proof (power stated there).
