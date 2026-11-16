# Live order timing, part 3: facts (Nov 16 2026)

Plan: reports/owner/timing_prereg.md on main, "Part 3: the live bot as built and each stage of the rebuild" and
"Part 3, deviation 1". The method is that of parts 1 and 2, unchanged. This file states what was run and what came
out. It contains no reading.

## What was run
- **Paths for fifteen start times.** scripts/owner/timing/rederive_runner.py ran on a runner (job 43876543675,
  workflow hunt2.yml, branch owner/timing-data, outputs in commit 8dae4a48). It read the first fetch's eight print
  artifacts and made no request to the venue.
  - The start times are the six of parts 1 and 2 (0, 1.3, 7.5, 8, 10 and 15 s) and the nine new-bid times of part 3
    (2, 5.2, 10.2, 11.08, 11.7, 12.15, 13.9, 17.25 and 24 s).
  - Rows: reports/owner/timing/data/out3/derived3_0..7.parquet, 31.6 MB. Each row stores one union of the fifteen
    running-minimum paths, from which every start's path is rebuilt exactly, plus the last print before each start.
- **Evaluation.** scripts/owner/timing/part3.py ran on those rows. It covers the six policies of parts 1 and 2 and the
  twelve of part 3 in one pass, through the same code path, and uses:
  - evaluate.py for parents and part 1's first-order P&L;
  - part2.py for the moves and S1;
  - part2_s2.py for S2, with the deep prints of reports/owner/timing/data/out2.

  It took 505 s (evaluate 408 s, S1 22 s, S2 72 s) and peaked at 3.0 GB of memory.
- **"No carried bid" (N1 to N3):**
  - the bid of the minute before never rests into the new minute and is never kept;
  - each approved minute places its new bid at the policy's time, subject to the same skip test;
  - the bid rests to the end of that minute only.

## Checks
- **Cross-check of the paths (runner, decisive).** The six old starts' columns were compared with the rows on file.
  - Every shared column of all 29,686 rows was identical: lists element by element, floats exactly, NaN equal to NaN.
  - 0 rows differ, 0 rows are missing on either side, and status is identical for every row.
  - The rebuild of every start's path from the stored union was exact on every row (0 failures).
  - The runner read 14,081,271 prints in 8 artifact files, covering 6,370 windows.
  - Result: reproduced true. Files: data/out3/rederive_check.csv and rederive_run.json on branch owner/timing-data.
- **Regression of the six policies on file.** Run from the fifteen-start rows, the six policies of parts 1 and 2 come
  out identical, as written, to the files on record in reports/owner/timing. Files compared:
  - rows of the six policies in policies.csv, entry_by_seconds.csv, moves.csv, parents.csv.gz and s2_parents.csv.gz;
  - rows of the parts 1 and 2 pairs in s1.csv and s2.csv;
  - p0_fill_times.csv, p0_vs_research.csv, removed_top_p1.csv, s1_check.csv, s2_check.csv and s2_rowcheck.csv
    whole.

  See [regression_check.csv](regression_check.csv). Before part 3 was added, the evaluation of Nov 10 was rerun on
  the six-start rows and also reproduced every file on record exactly.

## Definitions
- **Same min:** the share of P0's parents that the policy fills in the same coin and minute (moves.csv share_pm0).
- **Within 2 min:** part 2's share_pm2. A P0 parent counts when the policy has a parent in the same coin whose minute
  is at most two minutes away, either side, same minute included. Parents are not paired one to one.
- **Stale and kept:** fills on the bid carried in from the minute before.
  - Stale: a fill before the cancel.
  - Kept: the new level was within half a tick of the resting bid, so it stayed for the whole minute (P0 has these
    too).
  - New: fills on the new bid.
- **P&L percentages:** the policy's P&L minus the reference's, in percent of the reference's P&L.
  - S1: every parent on its 4-sigma rung alone.
  - S2: the whole ladder.
  - Table B: part 1's first-order valuation.
  - Pooled: sums over the three eras.
- **Eras:** sel = selection (Jan 2025 - Mar 2026), chk = check (Apr - Nov 5 2026), early = 2022-23.
- **Order:** policies are in the order of the plan's table, next to P0 and P1. The other policies of parts 1 and 2
  (P1a, P1b, P2, P3) follow for reference.

### Table A: per era and policy (shares, fills, P&L in percent under S1 and S2)

Times: cancel / new bid, seconds after the minute. Same min / within 2 min: share of P0's parents. Stale, kept: fills on the carried bid; new: fills on the new bid. P&L: percent of the reference's P&L.


**sel**

| policy | times (s) | parents | same min | within 2 min | stale | kept | new | S1 vs P0 | S1 vs P1 | S2 vs P0 | S2 vs P1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P0 | 0 / 0 | 1165 | 1.000 | 1.000 | 0 | 37 | 1128 | - | - | - | - |
| P1 | 8 / 10 | 1191 | 0.870 | 0.909 | 145 | 38 | 1008 | +3.7 | - | +1.9 | - |
| B0 | 14.25 / 17.25 | 1229 | 0.814 | 0.873 | 283 | 36 | 910 | +3.6 | -0.1 | -4.1 | -6.0 |
| B0f | 12.4 / 13.9 | 1208 | 0.838 | 0.895 | 215 | 36 | 957 | +0.6 | -3.0 | +1.2 | -0.7 |
| B0s | 18 / 24 | 1227 | 0.751 | 0.822 | 367 | 37 | 823 | +4.7 | +1.0 | -6.8 | -8.6 |
| B1 | 10.8 / 11.7 | 1211 | 0.856 | 0.904 | 189 | 37 | 985 | -1.2 | -4.8 | -0.8 | -2.7 |
| B2 | 9.3 / 10.2 | 1197 | 0.864 | 0.909 | 165 | 38 | 994 | +4.6 | +0.8 | +3.7 | +1.7 |
| B3 | 4.3 / 5.2 | 1184 | 0.916 | 0.943 | 84 | 39 | 1061 | +1.3 | -2.4 | +2.5 | +0.6 |
| B4 | 1.1 / 2 | 1170 | 0.958 | 0.968 | 13 | 37 | 1120 | -2.5 | -6.0 | -1.2 | -3.0 |
| B1r | 10.7 / 12.15 | 1204 | 0.851 | 0.899 | 187 | 37 | 980 | +4.1 | +0.3 | +0.9 | -1.0 |
| B2r | 9.63 / 11.08 | 1201 | 0.861 | 0.910 | 171 | 37 | 993 | +3.3 | -0.4 | +2.6 | +0.6 |
| N1 | 0 / 11.7 (no carry) | 1131 | 0.849 | 0.888 | 0 | 0 | 1131 | -5.0 | -8.4 | -2.7 | -4.5 |
| N2 | 0 / 10.2 (no carry) | 1130 | 0.865 | 0.897 | 0 | 0 | 1130 | -0.7 | -4.3 | +0.2 | -1.7 |
| N3 | 0 / 5.2 (no carry) | 1145 | 0.918 | 0.939 | 0 | 0 | 1145 | -0.3 | -3.9 | +3.7 | +1.8 |
| P1a | 6.5 / 7.5 | 1193 | 0.894 | 0.925 | 122 | 38 | 1033 | +5.9 | +2.1 | +7.8 | +5.8 |
| P1b | 12 / 15 | 1205 | 0.828 | 0.888 | 214 | 36 | 955 | +3.6 | -0.1 | +3.5 | +1.6 |
| P2 | 1 / 1.3 | 1169 | 0.970 | 0.975 | 12 | 37 | 1120 | -6.4 | -9.7 | -1.9 | -3.8 |
| P3 | 8 / 8 | 1212 | 0.900 | 0.934 | 144 | 38 | 1030 | +7.5 | +3.6 | +6.0 | +4.0 |

P0's P&L: S1 $37,291, S2 $90,057.


**chk**

| policy | times (s) | parents | same min | within 2 min | stale | kept | new | S1 vs P0 | S1 vs P1 | S2 vs P0 | S2 vs P1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P0 | 0 / 0 | 418 | 1.000 | 1.000 | 0 | 18 | 400 | - | - | - | - |
| P1 | 8 / 10 | 443 | 0.900 | 0.935 | 85 | 18 | 340 | -16.8 | - | -11.9 | - |
| B0 | 14.25 / 17.25 | 445 | 0.840 | 0.900 | 139 | 17 | 289 | -18.2 | -1.6 | -8.8 | +3.6 |
| B0f | 12.4 / 13.9 | 443 | 0.854 | 0.902 | 120 | 17 | 306 | -12.1 | +5.6 | -10.1 | +2.1 |
| B0s | 18 / 24 | 432 | 0.744 | 0.809 | 173 | 17 | 242 | -10.8 | +7.2 | -9.8 | +2.4 |
| B1 | 10.8 / 11.7 | 437 | 0.871 | 0.902 | 103 | 17 | 317 | -21.2 | -5.3 | -10.8 | +1.2 |
| B2 | 9.3 / 10.2 | 443 | 0.888 | 0.928 | 93 | 17 | 333 | -14.7 | +2.5 | -11.8 | +0.2 |
| B3 | 4.3 / 5.2 | 429 | 0.904 | 0.943 | 38 | 18 | 373 | +2.0 | +22.7 | -1.1 | +12.3 |
| B4 | 1.1 / 2 | 417 | 0.952 | 0.969 | 9 | 18 | 390 | -9.5 | +8.8 | -6.3 | +6.4 |
| B1r | 10.7 / 12.15 | 434 | 0.871 | 0.902 | 101 | 18 | 315 | -23.0 | -7.4 | -10.9 | +1.2 |
| B2r | 9.63 / 11.08 | 437 | 0.876 | 0.919 | 94 | 17 | 326 | -17.2 | -0.4 | -7.5 | +5.1 |
| N1 | 0 / 11.7 (no carry) | 378 | 0.806 | 0.844 | 0 | 0 | 378 | +4.0 | +25.0 | +8.0 | +22.6 |
| N2 | 0 / 10.2 (no carry) | 388 | 0.833 | 0.876 | 0 | 0 | 388 | +4.5 | +25.6 | +0.5 | +14.2 |
| N3 | 0 / 5.2 (no carry) | 399 | 0.880 | 0.914 | 0 | 0 | 399 | +4.2 | +25.3 | -0.7 | +12.8 |
| P1a | 6.5 / 7.5 | 433 | 0.892 | 0.933 | 65 | 18 | 350 | -6.5 | +12.4 | -0.5 | +12.9 |
| P1b | 12 / 15 | 438 | 0.854 | 0.904 | 114 | 17 | 307 | -10.6 | +7.5 | -11.8 | +0.1 |
| P2 | 1 / 1.3 | 420 | 0.959 | 0.974 | 9 | 18 | 393 | -7.8 | +10.9 | -5.7 | +7.1 |
| P3 | 8 / 8 | 440 | 0.900 | 0.938 | 83 | 18 | 339 | -22.3 | -6.5 | -13.8 | -2.1 |

P0's P&L: S1 $12,606, S2 $32,937.


**early**

| policy | times (s) | parents | same min | within 2 min | stale | kept | new | S1 vs P0 | S1 vs P1 | S2 vs P0 | S2 vs P1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P0 | 0 / 0 | 756 | 1.000 | 1.000 | 0 | 27 | 729 | - | - | - | - |
| P1 | 8 / 10 | 768 | 0.827 | 0.882 | 93 | 28 | 647 | -26.0 | - | -11.9 | - |
| B0 | 14.25 / 17.25 | 792 | 0.745 | 0.836 | 170 | 28 | 594 | -24.0 | +2.7 | -13.8 | -2.2 |
| B0f | 12.4 / 13.9 | 791 | 0.788 | 0.865 | 143 | 28 | 620 | -18.4 | +10.2 | -7.9 | +4.5 |
| B0s | 18 / 24 | 788 | 0.690 | 0.792 | 230 | 28 | 530 | -14.6 | +15.4 | -12.6 | -0.9 |
| B1 | 10.8 / 11.7 | 785 | 0.808 | 0.869 | 127 | 29 | 629 | -20.9 | +6.9 | -9.8 | +2.3 |
| B2 | 9.3 / 10.2 | 780 | 0.817 | 0.880 | 110 | 28 | 642 | -21.6 | +5.9 | -8.3 | +4.1 |
| B3 | 4.3 / 5.2 | 764 | 0.876 | 0.931 | 52 | 28 | 684 | -24.2 | +2.4 | -6.9 | +5.7 |
| B4 | 1.1 / 2 | 758 | 0.930 | 0.959 | 23 | 27 | 708 | -8.7 | +23.3 | -2.9 | +10.2 |
| B1r | 10.7 / 12.15 | 783 | 0.807 | 0.869 | 123 | 29 | 631 | -20.7 | +7.1 | -11.2 | +0.8 |
| B2r | 9.63 / 11.08 | 785 | 0.808 | 0.868 | 116 | 29 | 640 | -20.8 | +7.1 | -8.2 | +4.2 |
| N1 | 0 / 11.7 (no carry) | 713 | 0.804 | 0.854 | 0 | 0 | 713 | -16.8 | +12.4 | -11.8 | +0.1 |
| N2 | 0 / 10.2 (no carry) | 716 | 0.810 | 0.858 | 0 | 0 | 716 | -33.3 | -9.9 | -13.6 | -1.9 |
| N3 | 0 / 5.2 (no carry) | 733 | 0.870 | 0.922 | 0 | 0 | 733 | -26.1 | -0.1 | -6.6 | +6.0 |
| P1a | 6.5 / 7.5 | 767 | 0.841 | 0.905 | 77 | 28 | 662 | -19.9 | +8.3 | -8.7 | +3.6 |
| P1b | 12 / 15 | 787 | 0.778 | 0.860 | 135 | 31 | 621 | -20.7 | +7.1 | -11.3 | +0.7 |
| P2 | 1 / 1.3 | 762 | 0.950 | 0.963 | 22 | 27 | 713 | -5.8 | +27.2 | -2.1 | +11.1 |
| P3 | 8 / 8 | 778 | 0.849 | 0.905 | 91 | 28 | 659 | -15.5 | +14.1 | -3.2 | +9.8 |

P0's P&L: S1 $15,818, S2 $59,993.


**pooled (sums over the three eras)**

| policy | times (s) | S1 vs P0 | S1 vs P1 | S2 vs P0 | S2 vs P1 |
|---|---|---|---|---|---|
| P0 | 0 / 0 | - | - | - | - |
| P1 | 8 / 10 | -7.4 | - | -5.1 | - |
| B0 | 14.25 / 17.25 | -7.2 | +0.2 | -8.2 | -3.2 |
| B0f | 12.4 / 13.9 | -6.4 | +1.0 | -3.8 | +1.3 |
| B0s | 18 / 24 | -2.9 | +4.8 | -9.2 | -4.4 |
| B1 | 10.8 / 11.7 | -9.8 | -2.6 | -5.5 | -0.5 |
| B2 | 9.3 / 10.2 | -5.4 | +2.1 | -3.0 | +2.2 |
| B3 | 4.3 / 5.2 | -4.7 | +2.9 | -1.2 | +4.1 |
| B4 | 1.1 / 2 | -5.3 | +2.2 | -2.6 | +2.6 |
| B1r | 10.7 / 12.15 | -7.1 | +0.3 | -5.2 | -0.1 |
| B2r | 9.63 / 11.08 | -6.4 | +1.0 | -2.8 | +2.5 |
| N1 | 0 / 11.7 (no carry) | -6.1 | +1.4 | -3.7 | +1.4 |
| N2 | 0 / 10.2 (no carry) | -7.6 | -0.2 | -4.3 | +0.9 |
| N3 | 0 / 5.2 (no carry) | -5.7 | +1.8 | -0.4 | +4.9 |
| P1a | 6.5 / 7.5 | -2.7 | +5.1 | +0.9 | +6.3 |
| P1b | 12 / 15 | -5.0 | +2.6 | -4.1 | +1.1 |
| P2 | 1 / 1.3 | -6.5 | +0.9 | -2.7 | +2.6 |
| P3 | 8 / 8 | -3.8 | +3.9 | -0.6 | +4.8 |

### Table B: part 1's first-order valuation (the columns of policies.csv)

shared = same coin and minute in both books; entry = dollar-weighted entry difference on shared parents (bp, positive = pays more); P&L % = first-order net P&L difference in percent of the reference's P&L; Sharpe = change in daily Sharpe at S*.


**sel**

| policy | vs | parents | ref | shared | shared share | only policy | only ref | entry bp | P&L bp/$ | P&L % | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | P0 | 1191 | 1165 | 1013 | 0.870 | 178 | 152 | +1.08 | +2.08 | +4.8 | +0.33 |
| B0 | P0 | 1229 | 1165 | 948 | 0.814 | 281 | 217 | +1.82 | +0.47 | +1.1 | +0.16 |
| B0f | P0 | 1208 | 1165 | 976 | 0.838 | 232 | 189 | +1.59 | -0.87 | -2.0 | +0.07 |
| B0s | P0 | 1227 | 1165 | 875 | 0.751 | 352 | 290 | +2.41 | +1.56 | +3.6 | +0.29 |
| B1 | P0 | 1211 | 1165 | 997 | 0.856 | 214 | 168 | +1.57 | +0.76 | +1.7 | +0.27 |
| B2 | P0 | 1197 | 1165 | 1007 | 0.864 | 190 | 158 | +1.24 | +2.25 | +5.2 | +0.28 |
| B3 | P0 | 1184 | 1165 | 1067 | 0.916 | 117 | 98 | +0.51 | +1.54 | +3.5 | +0.15 |
| B4 | P0 | 1170 | 1165 | 1116 | 0.958 | 54 | 49 | +0.00 | -1.33 | -3.1 | -0.10 |
| B1r | P0 | 1204 | 1165 | 991 | 0.851 | 213 | 174 | +1.58 | +1.26 | +2.9 | +0.09 |
| B2r | P0 | 1201 | 1165 | 1003 | 0.861 | 198 | 162 | +1.46 | +2.02 | +4.6 | +0.17 |
| N1 | P0 | 1131 | 1165 | 989 | 0.849 | 142 | 176 | +0.00 | -2.71 | -6.2 | +0.06 |
| N2 | P0 | 1130 | 1165 | 1008 | 0.865 | 122 | 157 | +0.00 | -1.79 | -4.1 | +0.16 |
| N3 | P0 | 1145 | 1165 | 1070 | 0.918 | 75 | 95 | +0.00 | -0.32 | -0.7 | +0.08 |
| P1a | P0 | 1193 | 1165 | 1042 | 0.894 | 151 | 123 | +0.70 | +2.39 | +5.5 | +0.13 |
| P1b | P0 | 1205 | 1165 | 965 | 0.828 | 240 | 200 | +1.62 | -0.05 | -0.1 | +0.20 |
| P2 | P0 | 1169 | 1165 | 1130 | 0.970 | 39 | 35 | +0.00 | -1.16 | -2.7 | -0.09 |
| P3 | P0 | 1212 | 1165 | 1048 | 0.900 | 164 | 117 | +1.04 | +3.35 | +7.7 | +0.23 |
| B0 | P1 | 1229 | 1191 | 1053 | 0.884 | 176 | 138 | +0.86 | -1.61 | -3.5 | -0.17 |
| B0f | P1 | 1208 | 1191 | 1099 | 0.923 | 109 | 92 | +0.61 | -2.95 | -6.5 | -0.27 |
| B0s | P1 | 1227 | 1191 | 965 | 0.810 | 262 | 226 | +1.37 | -0.53 | -1.2 | -0.05 |
| B1 | P1 | 1211 | 1191 | 1143 | 0.960 | 68 | 48 | +0.59 | -1.32 | -2.9 | -0.06 |
| B2 | P1 | 1197 | 1191 | 1178 | 0.989 | 19 | 13 | +0.22 | +0.17 | +0.4 | -0.06 |
| B3 | P1 | 1184 | 1191 | 1081 | 0.908 | 103 | 110 | -0.55 | -0.54 | -1.2 | -0.18 |
| B4 | P1 | 1170 | 1191 | 1034 | 0.868 | 136 | 157 | -1.08 | -3.41 | -7.5 | -0.43 |
| B1r | P1 | 1204 | 1191 | 1134 | 0.952 | 70 | 57 | +0.59 | -0.82 | -1.8 | -0.25 |
| B2r | P1 | 1201 | 1191 | 1161 | 0.975 | 40 | 30 | +0.40 | -0.07 | -0.1 | -0.17 |
| N1 | P1 | 1131 | 1191 | 1034 | 0.868 | 97 | 157 | -0.94 | -4.79 | -10.5 | -0.27 |
| N2 | P1 | 1130 | 1191 | 1070 | 0.898 | 60 | 121 | -0.94 | -3.87 | -8.5 | -0.18 |
| N3 | P1 | 1145 | 1191 | 1018 | 0.855 | 127 | 173 | -1.03 | -2.40 | -5.3 | -0.25 |
| P1a | P1 | 1193 | 1191 | 1124 | 0.944 | 69 | 67 | -0.26 | +0.31 | +0.7 | -0.21 |
| P1b | P1 | 1205 | 1191 | 1085 | 0.911 | 120 | 106 | +0.63 | -2.13 | -4.7 | -0.13 |
| P2 | P1 | 1169 | 1191 | 1032 | 0.866 | 137 | 159 | -1.04 | -3.24 | -7.1 | -0.42 |
| P3 | P1 | 1212 | 1191 | 1147 | 0.963 | 65 | 44 | +0.00 | +1.27 | +2.8 | -0.10 |

**chk**

| policy | vs | parents | ref | shared | shared share | only policy | only ref | entry bp | P&L bp/$ | P&L % | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | P0 | 443 | 418 | 376 | 0.900 | 67 | 42 | +3.24 | -5.51 | -11.3 | -0.27 |
| B0 | P0 | 445 | 418 | 351 | 0.840 | 94 | 67 | +4.32 | -7.07 | -14.5 | -0.34 |
| B0f | P0 | 443 | 418 | 357 | 0.854 | 86 | 61 | +4.18 | -5.33 | -10.9 | -0.24 |
| B0s | P0 | 432 | 418 | 311 | 0.744 | 121 | 107 | +5.41 | -7.39 | -15.1 | -0.12 |
| B1 | P0 | 437 | 418 | 364 | 0.871 | 73 | 54 | +3.88 | -6.92 | -14.2 | -0.37 |
| B2 | P0 | 443 | 418 | 371 | 0.888 | 72 | 47 | +3.72 | -6.14 | -12.6 | -0.42 |
| B3 | P0 | 429 | 418 | 378 | 0.904 | 51 | 40 | +0.98 | +0.61 | +1.2 | +0.06 |
| B4 | P0 | 417 | 418 | 398 | 0.952 | 19 | 20 | +0.69 | -2.82 | -5.8 | -0.19 |
| B1r | P0 | 434 | 418 | 364 | 0.871 | 70 | 54 | +3.93 | -7.14 | -14.6 | -0.38 |
| B2r | P0 | 437 | 418 | 366 | 0.876 | 71 | 52 | +3.83 | -6.54 | -13.4 | -0.31 |
| N1 | P0 | 378 | 418 | 337 | 0.806 | 41 | 81 | -0.00 | -0.67 | -1.4 | +0.16 |
| N2 | P0 | 388 | 418 | 348 | 0.833 | 40 | 70 | -0.00 | -1.53 | -3.1 | +0.01 |
| N3 | P0 | 399 | 418 | 368 | 0.880 | 31 | 50 | -0.00 | +3.04 | +6.2 | +0.31 |
| P1a | P0 | 433 | 418 | 373 | 0.892 | 60 | 45 | +2.29 | -1.99 | -4.1 | -0.13 |
| P1b | P0 | 438 | 418 | 357 | 0.854 | 81 | 61 | +4.14 | -5.82 | -11.9 | -0.22 |
| P2 | P0 | 420 | 418 | 401 | 0.959 | 19 | 17 | +0.68 | -1.80 | -3.7 | -0.12 |
| P3 | P0 | 440 | 418 | 376 | 0.900 | 64 | 42 | +3.20 | -5.46 | -11.2 | -0.24 |
| B0 | P1 | 445 | 443 | 398 | 0.898 | 47 | 45 | +1.11 | -1.56 | -3.6 | -0.07 |
| B0f | P1 | 443 | 443 | 414 | 0.935 | 29 | 29 | +0.70 | +0.18 | +0.4 | +0.03 |
| B0s | P1 | 432 | 443 | 355 | 0.801 | 77 | 88 | +1.79 | -1.88 | -4.3 | +0.15 |
| B1 | P1 | 437 | 443 | 421 | 0.950 | 16 | 22 | +0.48 | -1.41 | -3.2 | -0.09 |
| B2 | P1 | 443 | 443 | 435 | 0.982 | 8 | 8 | +0.39 | -0.63 | -1.4 | -0.15 |
| B3 | P1 | 429 | 443 | 398 | 0.898 | 31 | 45 | -2.21 | +6.12 | +14.1 | +0.33 |
| B4 | P1 | 417 | 443 | 384 | 0.867 | 33 | 59 | -2.45 | +2.69 | +6.2 | +0.08 |
| B1r | P1 | 434 | 443 | 420 | 0.948 | 14 | 23 | +0.48 | -1.63 | -3.8 | -0.11 |
| B2r | P1 | 437 | 443 | 424 | 0.957 | 13 | 19 | +0.42 | -1.03 | -2.4 | -0.03 |
| N1 | P1 | 378 | 443 | 344 | 0.777 | 34 | 99 | -3.01 | +4.84 | +11.2 | +0.43 |
| N2 | P1 | 388 | 443 | 362 | 0.817 | 26 | 81 | -2.91 | +3.98 | +9.2 | +0.28 |
| N3 | P1 | 399 | 443 | 361 | 0.815 | 38 | 82 | -3.10 | +8.55 | +19.7 | +0.58 |
| P1a | P1 | 433 | 443 | 416 | 0.939 | 17 | 27 | -1.04 | +3.52 | +8.1 | +0.15 |
| P1b | P1 | 438 | 443 | 410 | 0.926 | 28 | 33 | +0.63 | -0.31 | -0.7 | +0.05 |
| P2 | P1 | 420 | 443 | 385 | 0.869 | 35 | 58 | -2.40 | +3.71 | +8.6 | +0.15 |
| P3 | P1 | 440 | 443 | 429 | 0.968 | 11 | 14 | +0.00 | +0.05 | +0.1 | +0.04 |

**early**

| policy | vs | parents | ref | shared | shared share | only policy | only ref | entry bp | P&L bp/$ | P&L % | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | P0 | 768 | 756 | 625 | 0.827 | 143 | 131 | +1.53 | -9.67 | -16.6 | -0.49 |
| B0 | P0 | 792 | 756 | 563 | 0.745 | 229 | 193 | +2.81 | -7.24 | -12.4 | -0.23 |
| B0f | P0 | 791 | 756 | 596 | 0.788 | 195 | 160 | +2.02 | -5.36 | -9.2 | -0.16 |
| B0s | P0 | 788 | 756 | 522 | 0.690 | 266 | 234 | +4.47 | -7.05 | -12.1 | -0.33 |
| B1 | P0 | 785 | 756 | 611 | 0.808 | 174 | 145 | +1.90 | -5.46 | -9.4 | -0.17 |
| B2 | P0 | 780 | 756 | 618 | 0.817 | 162 | 138 | +1.80 | -7.18 | -12.3 | -0.34 |
| B3 | P0 | 764 | 756 | 662 | 0.876 | 102 | 94 | +0.74 | -6.03 | -10.3 | -0.24 |
| B4 | P0 | 758 | 756 | 703 | 0.930 | 55 | 53 | +0.17 | -2.98 | -5.1 | -0.11 |
| B1r | P0 | 783 | 756 | 610 | 0.807 | 173 | 146 | +1.89 | -6.09 | -10.4 | -0.20 |
| B2r | P0 | 785 | 756 | 611 | 0.808 | 174 | 145 | +1.84 | -7.90 | -13.5 | -0.36 |
| N1 | P0 | 713 | 756 | 608 | 0.804 | 105 | 148 | +0.00 | -3.78 | -6.5 | -0.10 |
| N2 | P0 | 716 | 756 | 612 | 0.810 | 104 | 144 | +0.00 | -8.75 | -15.0 | -0.35 |
| N3 | P0 | 733 | 756 | 658 | 0.870 | 75 | 98 | -0.00 | -6.71 | -11.5 | -0.31 |
| P1a | P0 | 767 | 756 | 636 | 0.841 | 131 | 120 | +1.15 | -2.40 | -4.1 | -0.02 |
| P1b | P0 | 787 | 756 | 588 | 0.778 | 199 | 168 | +2.01 | -6.90 | -11.8 | -0.21 |
| P2 | P0 | 762 | 756 | 718 | 0.950 | 44 | 38 | +0.16 | -1.14 | -1.9 | -0.06 |
| P3 | P0 | 778 | 756 | 642 | 0.849 | 136 | 114 | +1.47 | -3.32 | -5.7 | -0.11 |
| B0 | P1 | 792 | 768 | 653 | 0.850 | 139 | 115 | +1.04 | +2.43 | +5.0 | +0.26 |
| B0f | P1 | 791 | 768 | 679 | 0.884 | 112 | 89 | +0.37 | +4.32 | +8.9 | +0.33 |
| B0s | P1 | 788 | 768 | 599 | 0.780 | 189 | 169 | +2.58 | +2.63 | +5.4 | +0.16 |
| B1 | P1 | 785 | 768 | 714 | 0.930 | 71 | 54 | +0.30 | +4.21 | +8.7 | +0.32 |
| B2 | P1 | 780 | 768 | 752 | 0.979 | 28 | 16 | +0.23 | +2.49 | +5.1 | +0.15 |
| B3 | P1 | 764 | 768 | 683 | 0.889 | 81 | 85 | -0.52 | +3.65 | +7.5 | +0.25 |
| B4 | P1 | 758 | 768 | 648 | 0.844 | 110 | 120 | -1.12 | +6.69 | +13.8 | +0.38 |
| B1r | P1 | 783 | 768 | 700 | 0.911 | 83 | 68 | +0.31 | +3.58 | +7.4 | +0.29 |
| B2r | P1 | 785 | 768 | 727 | 0.947 | 58 | 41 | +0.24 | +1.77 | +3.6 | +0.13 |
| N1 | P1 | 713 | 768 | 642 | 0.836 | 71 | 126 | -1.21 | +5.89 | +12.1 | +0.38 |
| N2 | P1 | 716 | 768 | 678 | 0.883 | 38 | 90 | -1.22 | +0.93 | +1.9 | +0.14 |
| N3 | P1 | 733 | 768 | 642 | 0.836 | 91 | 126 | -1.27 | +2.96 | +6.1 | +0.18 |
| P1a | P1 | 767 | 768 | 703 | 0.915 | 64 | 65 | -0.18 | +7.27 | +14.9 | +0.47 |
| P1b | P1 | 787 | 768 | 679 | 0.884 | 108 | 89 | +0.32 | +2.78 | +5.7 | +0.28 |
| P2 | P1 | 762 | 768 | 640 | 0.833 | 122 | 128 | -1.16 | +8.54 | +17.5 | +0.43 |
| P3 | P1 | 778 | 768 | 724 | 0.943 | 54 | 44 | +0.00 | +6.35 | +13.1 | +0.38 |

### Table C: same-minute share against the new bid's time, carried-bid policies


**sel** (least-squares slope -0.905 points per second, intercept 96.4, 12 points)

| policy | new bid (s) | cancel (s) | same min |
|---|---|---|---|
| B4 | 2 | 1.1 | 0.958 |
| B3 | 5.2 | 4.3 | 0.916 |
| P1a | 7.5 | 6.5 | 0.894 |
| P1 | 10 | 8 | 0.870 |
| B2 | 10.2 | 9.3 | 0.864 |
| B2r | 11.08 | 9.63 | 0.861 |
| B1 | 11.7 | 10.8 | 0.856 |
| B1r | 12.15 | 10.7 | 0.851 |
| B0f | 13.9 | 12.4 | 0.838 |
| P1b | 15 | 12 | 0.828 |
| B0 | 17.25 | 14.25 | 0.814 |
| B0s | 24 | 18 | 0.751 |

**chk** (least-squares slope -0.839 points per second, intercept 96.8, 12 points)

| policy | new bid (s) | cancel (s) | same min |
|---|---|---|---|
| B4 | 2 | 1.1 | 0.952 |
| B3 | 5.2 | 4.3 | 0.904 |
| P1a | 7.5 | 6.5 | 0.892 |
| P1 | 10 | 8 | 0.900 |
| B2 | 10.2 | 9.3 | 0.888 |
| B2r | 11.08 | 9.63 | 0.876 |
| B1 | 11.7 | 10.8 | 0.871 |
| B1r | 12.15 | 10.7 | 0.871 |
| B0f | 13.9 | 12.4 | 0.854 |
| P1b | 15 | 12 | 0.854 |
| B0 | 17.25 | 14.25 | 0.840 |
| B0s | 24 | 18 | 0.744 |

**early** (least-squares slope -1.048 points per second, intercept 93.2, 12 points)

| policy | new bid (s) | cancel (s) | same min |
|---|---|---|---|
| B4 | 2 | 1.1 | 0.930 |
| B3 | 5.2 | 4.3 | 0.876 |
| P1a | 7.5 | 6.5 | 0.841 |
| P1 | 10 | 8 | 0.827 |
| B2 | 10.2 | 9.3 | 0.817 |
| B2r | 11.08 | 9.63 | 0.808 |
| B1 | 11.7 | 10.8 | 0.808 |
| B1r | 12.15 | 10.7 | 0.807 |
| B0f | 13.9 | 12.4 | 0.788 |
| P1b | 15 | 12 | 0.778 |
| B0 | 17.25 | 14.25 | 0.745 |
| B0s | 24 | 18 | 0.690 |

Table C is descriptive. It shows a least-squares line through the twelve carried-bid policies of each era (P1, P1a,
P1b, B0, B0f, B0s, B1, B2, B3, B4, B1r, B2r): same-minute share in percentage points against the new bid's time in
seconds. The cancel time differs between these policies and is not a separate term in the fit.

| era | slope (points per second) | intercept (points) | points |
|---|---|---|---|
| sel | -0.905 | 96.4 | 12 |
| chk | -0.839 | 96.8 | 12 |
| early | -1.048 | 93.2 | 12 |

## Files
- Tables: [summary.csv](summary.csv) (Table A and C), [policies.csv](policies.csv) (Table B),
  [moves.csv](moves.csv), [s1.csv](s1.csv), [s2.csv](s2.csv),
  [entry_by_seconds.csv](entry_by_seconds.csv), [parents.csv.gz](parents.csv.gz),
  [s2_parents.csv.gz](s2_parents.csv.gz), [minute_flags.csv.gz](minute_flags.csv.gz).
- Unchanged from parts 1 and 2, written again by the same run: p0_fill_times.csv, p0_vs_research.csv,
  removed_top_p1.csv, s1_check.csv, s2_check.csv and s2_rowcheck.csv.
- Code: scripts/owner/timing/part3.py, evaluate.py (POLICIES3), part2.py, part2_s2.py. Tests: test_evaluate.py
  (14 tests), and on branch owner/timing-data test_rederive.py (6 tests).

## Limits (the plan's, restated)
- First order only for added parents in part 1's valuation.
- Levels come from final candles.
- One pair of times stands for all coins of a minute.
- The times of B0 to B4, B1r and B2r are models of code that has not run against the venue. They remain assumptions
  until the pilot's heartbeats record the real ones.
- No significance test was run (the plan has none).
