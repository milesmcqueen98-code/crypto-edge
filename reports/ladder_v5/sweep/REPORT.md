# Ladder v5, C7: who sold to us (C7a_sweep_skip, C7b_sweep_tilt)

Builder's report, returned as text (the subagent harness does not let builders write report files) and committed by
the coordinator. Spec reports/ladder_v5/specs/sweep.md; branch ladder/sweep from the freeze commit 7ae53cb. Both trials
were logged in order, path "return", in one Actions job (run 42425286342, code at 45d6a1e, outputs in 71169e0). Nothing
else was run on outcomes before both were logged.

## Result

| Trial | Pooled t, S*, θ 0.5 (vol-matched) | G1 | G2 | G3 | G4 | Pass |
|---|---|---|---|---|---|---|
| C7a_sweep_skip | −1.37 (−1.04) | fail | fail | fail | fail | no |
| C7b_sweep_tilt | +1.51 (+0.57) | fail | pass | fail | pass | no |

- **C7a: reject.** It loses in both out-of-sample eras. The deeper rungs it skips were profitable there.
- **C7b passes no adoption gate.** It is positive in every era but small. Its vol-matched t is +0.57, so most of the
  gain is extra deeper-rung size, not better selection. By the prereg's verdict rule it still qualifies for a forward
  test: pooled t ≥ 1 with the sign right in every era at S*, θ 0.5. The out-of-sample view below does not support the
  mechanism.

## Rule as implemented (scripts/ladder_v5/cand_sweep.py)

- **D** = `first_sweep_depth_bp`, keyed by (parent ts, coin), from prints_parents.csv (selection and check eras) or
  prints_parents_early.csv (2022-23).
- **Cutoffs, per calendar quarter:** `np.quantile` (linear) at 1/3 and 2/3 of D, over all parent fills in the same
  prints file that have a finite D and a ts before the quarter starts. Fewer than 60 such fills: multiplier 1. A parent
  with no D: multiplier 1.
- **Buckets:** lo is D < lower; mid is lower ≤ D < upper; hi is D ≥ upper.
- **Multipliers:** C7a uses lo 0 (6/8σ rungs not placed) and 1 otherwise. C7b uses lo 0.5, mid 1.0, hi 1.5.
- **Plumbing:** `hsim.book(..., deep_mult={(ts, coin): m})`, the same map in every configuration.
- **"Same era"** is read as the same prints file: main (2025-26) or early (2022-23), as sizing.md uses "era" for the
  trade list ("Main era: 2025Q1 has no earlier fills"). So check-era cutoffs use selection-era parents, as a live bot
  would. Under the stricter reading, 2026Q2 would have no cutoffs and 2026Q3-Q4 would use check-era parents only.
- **The 60-fill minimum** counts earlier parents with a finite D. It binds only in 2025Q1 and 2022Q1, which have no
  earlier fills. 2022Q2 had 76.

## Off-switch check

- **Locally:** check era, S*, θ 0.5, every multiplier 1. Max daily difference against reports/ladder_v5/cache is 0.0,
  with 412/412 parent keys matched.
- **On the runner,** in the same job before the trials, with pandas 3.0.5, numpy 2.5.3 and pyarrow 26.0.1 pinned (the
  versions that built the cache): 0.0 in all three eras, keys matched 1155/1155, 412/412 and 744/744.
- **Hook mechanics** (order sizes only; check era, S*): C7a zeroes every lo-bucket deeper order; C7b's deeper orders are
  exactly 0.5x / 1.0x / 1.5x the off switch's (medians). Cash knock-on effects leave 0.6-2.5% of rungs unfunded.

## Coverage, cutoffs and reach (cutoffs.csv, coverage.csv)

| Era | Parents | With D | none / lo / mid / hi | C7a suppressed (parents / research deeper fills) | C7b scaled |
|---|---|---|---|---|---|
| Selection | 1155 | 1139 | 321 / 191 / 309 / 334 | 16.5% / 18.1% | 45.5% / 43.7% |
| Check | 412 | 403 | 9 / 77 / 190 / 136 | 18.7% / 19.5% | 51.7% / 52.9% |
| 2022-23 | 744 | 728 | 92 / 182 / 186 / 284 | 24.5% / 23.3% | 62.6% / 58.5% |

Every parent is in its prints file. Bucket "none" means no cutoff (2025Q1, 2022Q1) or no D.

Quarterly cutoffs, lower / upper in bp (earlier fills in brackets):

| File | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| main 2025 | none (0) | 1.17 / 3.90 (305) | 1.18 / 3.41 (510) | 1.18 / 3.67 (637) |
| main 2026 | 1.36 / 4.98 (940) | 1.49 / 5.08 (1139) | 1.57 / 5.01 (1277) | 1.63 / 5.29 (1378) |
| early 2022 | none (0) | 1.75 / 4.09 (76) | 2.03 / 4.77 (198) | 2.23 / 4.90 (249) |
| early 2023 | 2.61 / 5.36 (342) | 2.67 / 5.72 (442) | 2.78 / 6.07 (516) | 2.84 / 6.13 (585) |

D drifts up over time, so the walk-forward buckets are not thirds: hi outnumbers lo. C7b therefore adds net
deeper-rung size.

Live book at S*, θ 0.5 (instant bound), incumbent → C7a → C7b:

| | Selection | Check | 2022-23 |
|---|---|---|---|
| Deeper rungs placed | 2105 → 1788 → 2110 | 744 → 631 → 749 | 1484 → 1120 → 1484 |
| Deeper rungs filled | 737 → 624 → 737 | 236 → 199 → 237 | 506 → 387 → 506 |
| Parents funded | 1117 → 1131 → 1124 | 400 → 402 → 399 | 744 → 744 → 744 |

## Gate tables (trials/*.json, sweep/gates_summary.txt)

Return / Sharpe at S*, θ 0.5:

| Era | Incumbent | C7a | C7a era t | C7b | C7b era t |
|---|---|---|---|---|---|
| Selection | 19.5% / 2.31 | 20.3% / 2.40 | +0.75 | 20.8% / 2.47 | +1.46 |
| Check | 15.1% / 2.31 | 13.2% / 2.01 | −1.36 | 15.4% / 2.39 | +0.38 |
| 2022-23 | 10.4% / 1.72 | 8.6% / 1.38 | −1.84 | 10.9% / 1.70 | +0.70 |

Pooled t (vol-matched in brackets) and era t in the other configurations:

| Configuration | C7a pooled t | C7a era t (sel / chk / early) | C7b pooled t | C7b era t (sel / chk / early) |
|---|---|---|---|---|
| S*, θ 0.25 | −1.13 (−0.79) | +0.68 / −1.11 / −1.73 | +1.25 (+0.76) | +1.18 / +0.69 / +0.42 |
| base | −2.08 (−1.29) | +0.17 / −1.54 / −2.27 | +1.48 (−0.64) | +1.43 / +0.65 / +0.45 |
| $1M | −2.11 (−0.64) | −1.50 / −1.89 / −0.74 | +0.86 (+0.45) | +0.82 / −0.09 / +0.65 |

Sharpe at $1M, incumbent → candidate: C7a 1.76 → 1.68, 0.97 → 0.40, 0.55 → 0.37; C7b 1.76 → 1.86, 0.97 → 0.88,
0.55 → 0.63. The incumbent rows equal the prereg's S*, base and $1M figures exactly.

## What drives it (S*, θ 0.5; sweep/drivers.txt; bp of capital a year, blended bounds)

**C7a.** In the check era and 2022-23 the suppressed lo-bucket rungs were profitable (live incumbent net per $, instant
bound: check 8σ +156 bp on 15 fills; 2022-23 6σ +43 on 77 and 8σ +121 on 42). Removing them costs −236 bp a year in the
check era (8σ alone −231) and −173 bp in 2022-23; cash never binds in 2022-23, so there C7a is pure removal. In the
selection era the lo rungs were weak (6σ +3, 8σ +26 bp per $) and the cash they freed funded other rungs (cash-short
minutes 3,863 → 2,788; 14 more parents funded; mid/hi deeper rungs +119 bp, 4σ +16): net +87 bp.

**C7b:**

| | Selection | Check | 2022-23 |
|---|---|---|---|
| 1.5x hi rungs | +122 | +115 | +129 |
| 0.5x lo rungs | −8 | −100 | −81 |
| Net (incl. small knock-on) | +130 | +31 | +48 |

Largest days: 2023-12-11 (C7a −137 bp, C7b −62 bp; 20 parents, 8 lo; C7a removed 10 of 24 deeper fills, which paid);
2025-10-10 (C7a +103 bp; binding cash went to other rungs); 2022-11-09, FTX (C7b +86 bp; 12 of 20 parents in hi);
2022-05-12, LUNA (C7a +85, C7b +47 bp).

## Out-of-sample view: the deeper rungs' net per $ by D tercile (sweep/oos_terciles.txt)

Step 1's method (research book, $250K, θ 0.5, 1x costs, instant bound; terciles of D within the era over parents with a
D and a fill). It reproduces the selection-era evidence exactly. Shallow / middle / deep, bp per $ (fills); last column
deep minus shallow with a bootstrap 90% interval:

| Era | 6σ | 8σ | Deep minus shallow, 6σ / 8σ |
|---|---|---|---|
| Selection (in sample) | 15 / 50 / 81 (128 / 139 / 135) | 17 / 65 / 182 (59 / 61 / 61) | +66 [+19, +111] / +165 [+97, +233] |
| **Check** | 24 / 63 / 40 (52 / 60 / 57) | 123 / 90 / 83 (24 / 31 / 25) | +16 [−32, +67] / −40 [−148, +59] |
| **2022-23** | 68 / 49 / 117 (108 / 115 / 102) | 120 / 117 / 231 (55 / 53 / 50) | +49 [−20, +121] / +112 [−3, +255] |

The selection era's monotone relation does not replicate in the check era (8σ reverses); in 2022-23 only the deepest
tercile stands out. The shallow tercile is not poor in either era, so skipping it (C7a) loses, and C7b's gain comes from
the 1.5x on deep sweeps rather than the 0.5x on shallow ones.

## Is "same timestamp" one order? (scripts/ladder_v5/prints_grouping.py; prints only, on Actions)

Same-timestamp prints always carry consecutive trade ids. The first print group through our bid, 2025-26 / 2022-23:
one seller walking down the book 93.0% / 94.4%; buyers lifting asks only 3.2% / 4.5% (D does not measure a seller);
both sides at one timestamp 2.9% / 0.8%; possible split 7.1% / 3.8%. Verdict: reliable as "one order" for about 93-94%
of parents. Live caveat: one request returns at most 1,000 trades; 38% / 24% / 20% of parents (selection / check /
2022-23) print more than that in the fill minute, so a live reader must page back to the first print through our bid.

## Anything that looked wrong or ambiguous

1. fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl, which git ignores; a fresh checkout rebuilds it with
   sim.precompute. cand_sweep.py copies the frozen pickle into place after checking frozen/SHA256SUMS. (Coordinator's
   check: the rebuild equals the frozen dataset on every column the simulators use.)
2. scripts/hunt/gates.py shadows scripts/ladder_v5/gates.py when fsim is imported before gates; import gates first.
3. "Same era" is ambiguous; resolved as above.
4. C7b adds net size (D rises over time, so hi > lo), part of why its return t (1.51) exceeds its vol-matched t (0.57).
5. Disclosure: before the trials, a coverage step tabulated research deeper-rung fill counts by bucket in every era
   (counts only, no P&L). No P&L or markout was split by D outside the selection era before both trials were logged.

## Scorecard (builder's proposal for the hand-scored rows)

| Part | C7a | C7b |
|---|---|---|
| Evidence (25) | 0 | 8 |
| Robustness (20) | 2 | 15 |
| Realism (15) | 10 | 10 |
| Mechanism (10) | 10 | 10 |
| Prize (15) | 0 | 2 |
| Implementation and risk (10) | 10 | 7 |
| Capacity (5) | 0 | 2 |
| **Total** | **32** | **54** |

## Files

scripts/ladder_v5/cand_sweep.py, scripts/ladder_v5/prints_grouping.py; reports/ladder_v5/trials.csv,
trials/C7a_sweep_skip.json, trials/C7b_sweep_tilt.json; reports/ladder_v5/sweep/ (gates_summary.txt, cutoffs.csv,
coverage.csv, hsim_stats.csv, detail.parquet, daily.parquet, drivers.txt, drivers_rung_bucket.csv, oos_terciles.txt,
oos_terciles.csv); reports/ladder_v5/prints_grouping_{main,early}.csv.
