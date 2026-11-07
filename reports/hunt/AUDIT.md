EDGE HUNT (Nov 7 2026) - INDEPENDENT AUDIT OF GATES, PROCESS AND SCORECARD
==========================================================================
Auditor: independent agent, 2026-11-07, finished 09:25 UTC.
Snapshot audited: main clone at 3652fba (2026-11-07 08:54 UTC, "full 13-idea scorecard and central gates");
reports/hunt/trials.csv = 188 rows (last row 08:43:59Z); central_gates.csv/.json, scorecard.csv and
scorecard_manual.json as of 3652fba (copies in /home/claude/audit/snap/). Worktrees at their branch HEADs:
h1pb 9dbd289, h2fr 78ec565, h3lm def12be, h4nl f14fd79, h5an 5db7e24, h6vd e036d96, h7ul 99d208c, h8dp efc7ac3,
h9mc 90c24d1, h10xq f6b1544, h11mj e181f18, h12lt 3e18ee1, h13ps b875d6e (all clean).
Nothing under /home/claude/wt or /home/claude/crypto-edge was modified; gates.log_trial was never called.
Auditor code and outputs: /home/claude/audit/work/ (mygates.py = independent gate code; compare.py; check45.py;
check6.py; check3_select.py; scan_prefreeze.py; scan_pnl_cols.py; runs_vs_freeze.py; sens.py; idle_rf.py;
idle_rf2.py; h5an_paging.py; tables.py; results in my_gates.csv, compare_diffs.csv, check4.csv, sens.csv, tables.txt,
scan_*.txt, runs_*.json).

Severity scale used below
- VERDICT-CHANGING: would flip an idea's overall pass/fail.
- MATERIAL: changes a single gate's outcome or a reported gate number by more than 0.02, or breaches the hold-out
  rule, but leaves the overall verdict unchanged.
- MINOR: cosmetic, convention-level or bounded far below any gate margin.

0. BOTTOM LINE
--------------
- No idea's pass/fail verdict changes. All 12 gated ideas fail Path B at 2x costs, exactly as central_gates.csv
  says. h3lm was correctly stopped at its pre-registered DEV screen. Wave 3 therefore stays "none".
- My own implementation (it does not import gates.py) reproduces central_gates.csv on every number, including
  years and all three DSR variants, to within 7e-12. It reproduces every builder's gates.json to within 5e-5,
  except the builder-time DSR values. The deviation log already calls those provisional.
- Counts: VERDICT-CHANGING 0, MATERIAL 4, MINOR 12 (section 9).
- Hold-out discipline is clean for 11 of the 12 ideas that read HOLD. The exception is h12lt: an Actions run
  computed and committed HOLD trade lists with per-trade net P&L 34 s before the freeze commit (MATERIAL; it
  changes no verdict).
- The biggest structural lever on the near-misses is not a bug. It is the pre-registered convention that idle
  sleeve cash earns nothing while T-bills are subtracted. Under that convention G1 fails for h5an, h1pb and h4nl.
  If idle cash earned T-bills, all three would clear G1, but none would clear G1-G3 together (section 8).

1. METHOD (auditor's own code, /home/claude/audit/work/mygates.py)
-----------------------------------------------------------------
- Risk-free rate: the same source gates.py uses, edge/book.py `_TB`. These are hard-coded approximate monthly
  3-month T-bill yields (% p.a.) for 2016-2026, anchored on the 15th of each month. rf_daily unions the anchors with
  the scored index, fills the gaps with pandas' default linear interpolation, then ffill/bfill and divides by
  100/365. That default interpolation is positional, so a day's rf depends on which dates are in the series being
  scored. I parsed the table with ast, not by import, re-implemented it with np.interp and also built a
  calendar-time variant.
- Excess return = daily return - rf. Sharpe = mean / std(ddof 1) x sqrt(365).
- Path B:
  - book = a x incumbent(a x $100K) + (1 - a) x sleeve((1 - a) x $100K);
  - a = 0.7 pairs s30_2x with the incumbent at $70K; a = 0.5 pairs s50_2x with the incumbent at $50K;
  - a = argmax of the DEV book Sharpe (ties go to 0.7, as in gates.py);
  - DEV = scored days before 2026-06-01; HOLD = 2026-06-01 .. 2026-11-05;
  - scored days = the daily.parquet index intersected with ERA (2022-01-01..2023-12-31 and 2025-01-01..2026-11-05);
  - incumbent = the early/sel/chk "|cap|0.5|instant" columns. I asserted that the eras do not overlap.
- Alpha t: OLS of sleeve excess on incumbent excess (the incumbent at a x $100K), Newey-West Bartlett with 5 lags,
  no small-sample factor. A statsmodels cross-check (HAC, maxlags 5, use_correction=False) gives the same t on all
  12 ideas.
- Gains = book Sharpe - incumbent($100K) Sharpe, over all days and over HOLD. Years = simple sums of the daily book
  returns.
- DSR: Bailey & Lopez de Prado (2014), my own code, with N = 3000 + ledger rows and vz from the ledger under each
  rule (section 3).

2. RECOMPUTED GATES (check 1) - TABLE 1, WITH TABLE 2 (G4) BELOW IT
--------------------------------------------------------------------
TABLE 1. Path B gates at 2x costs, auditor's independent code (A) vs central_gates.csv (C).
  a chosen on DEV book Sharpe; t = Newey-West(5) t of the sleeve's alpha on the incumbent at a x $100K;
  gain = book Sharpe - incumbent($100K) Sharpe on the idea's own scored days; DSR = binding within-idea rule.
idea    days first         a A/C full t A full t C DEV t A  HOLD t A  HOLD t C  gain A  gain C Hgain A Hgain C bookSR incSR  slvSR  DSR A  DSR C G1 G2 G3 G4 G5 pass maxdiff
h1pb     475 2025-07-19 0.5/0.5    2.070    2.070   2.424    -0.158    -0.158  +0.427  +0.427  -0.174  -0.174   3.23  2.80   0.86  0.385  0.385 n  n  n  n  Y  fail 1.9e-13
h2fr    1404 2022-01-01 0.7/0.7   -1.218   -1.218  -0.946    -1.404    -1.404  -0.555  -0.555  -0.984  -0.984   1.91  2.47  -0.35  0.421  0.421 n  n  n  n  Y  fail 1.8e-13
h3lm   -- stopped at its pre-registered DEV mechanism screen; daily.parquet holds 1,246 DEV days only (ends 2026-05-31); no HOLD statistic exists; not gated (central: evaluated=False).
h4nl    1404 2022-01-01 0.7/0.7    1.526    1.526   1.211     1.277     1.277  -0.073  -0.073  +0.360  +0.360   2.39  2.47   0.73  0.811  0.811 n  n  n  n  Y  fail 1.4e-13
h5an    1404 2022-01-01 0.7/0.7    2.867    2.867   2.863     0.312     0.312  +0.216  +0.216  +0.079  +0.079   2.68  2.47   1.42  0.935  0.935 n  n  n  n  Y  fail 6.5e-14
h6vd     475 2025-07-19 0.7/0.7   -8.015   -8.015  -7.782    -5.032    -5.032 -10.234 -10.234  -5.680  -5.680  -7.44  2.80 -11.68  0.000  0.000 n  n  n  n  n  fail 5.3e-15
h7ul    1404 2022-01-01 0.7/0.7    1.899    1.899   1.941 -1062.003 -1062.003  -0.187  -0.187  -0.160  -0.160   2.28  2.47   0.82  0.710  0.710 n  n  n  n  Y  fail 6.8e-12
h8dp    1404 2022-01-01 0.7/0.7    1.546    1.546   1.899    -3.087    -3.087  -0.020  -0.020  -0.514  -0.514   2.45  2.47   0.44  0.823  0.823 n  n  n  n  Y  fail 1.2e-13
h9mc     476 2025-07-18 0.7/0.7   -2.183   -2.183  -1.066    -2.083    -2.083  -0.271  -0.271  -0.642  -0.642   2.53  2.80  -1.97  0.101  0.101 n  n  n  n  Y  fail 9.5e-14
h10xq   1404 2022-01-01 0.7/0.7  -10.873  -10.873 -10.901    -9.311    -9.311 -11.493 -11.493  -7.669  -7.669  -9.03  2.47  -9.95  0.000  0.000 n  n  n  n  n  fail 2.0e-14
h11mj   1404 2022-01-01 0.7/0.7    1.442    1.442   1.378     0.829     0.829  -0.017  -0.017  +0.201  +0.201   2.45  2.47   1.43  0.819  0.819 n  n  n  n  Y  fail 1.2e-13
h12lt    674 2025-01-01 0.7/0.7    1.611    1.611   1.740     0.503     0.503  +0.153  +0.153  +0.120  +0.120   2.75  2.60   1.75  0.412  0.412 n  n  n  n  Y  fail 1.9e-13
h13ps   1404 2022-01-01 0.7/0.7   -0.198   -0.198  -0.041    -1.241    -1.241  -0.538  -0.538  -0.624  -0.624   1.93  2.47  -0.14  0.426  0.426 n  n  n  n  Y  fail 2.1e-13

  Book calendar years (simple sum of daily book returns; G5), auditor = central to 4 dp:
    h1pb   2025: +0.1207, 2026: +0.1398
    h2fr   2022: +0.0664, 2023: +0.1394, 2025: +0.2948, 2026: +0.1337
    h4nl   2022: +0.1103, 2023: +0.1400, 2025: +0.2953, 2026: +0.1454
    h5an   2022: +0.1067, 2023: +0.1928, 2025: +0.3280, 2026: +0.1693
    h6vd   2025: -0.3747, 2026: -0.3711
    h7ul   2022: +0.2030, 2023: +0.1455, 2025: +0.3156, 2026: +0.1759
    h8dp   2022: +0.1097, 2023: +0.2342, 2025: +0.2310, 2026: +0.1181
    h9mc   2025: +0.1615, 2026: +0.1264
    h10xq  2022: -2.6334, 2023: -0.7970, 2025: -1.6078, 2026: -0.4830
    h11mj  2022: +0.0952, 2023: +0.1139, 2025: +0.5089, 2026: +0.2112
    h12lt  2025: +0.3305, 2026: +0.1573
    h13ps  2022: +0.0881, 2023: +0.1436, 2025: +0.2385, 2026: +0.1788

TABLE 2. G4 (deflated Sharpe of the book, Bailey & Lopez de Prado 2014) under each null-dispersion rule.
  N = 3000 + 188 ledger rows = 3188. vz: within-idea robust (binding) = 1.2178; pooled robust = 5.5487; plain variance (pre-registered) = 159.9111; floor alone = 1.1257.
  idea       T bookSR | SR0 within DSR within | SR0 pooled DSR pooled | SR0 plain DSR plain | SR0 floor DSR floor | G4 w/p/p/floor
  h1pb     475   3.23 |     3.455     0.3848 |     7.375     0.0000 |   39.589    0.0000 |    3.322    0.4521 | f/f/f/f
  h2fr    1404   1.91 |     2.010     0.4208 |     4.289     0.0000 |   23.027    0.0000 |    1.932    0.4836 | f/f/f/f
  h4nl    1404   2.39 |     2.010     0.8115 |     4.289     0.0000 |   23.027    0.0000 |    1.932    0.8558 | f/f/f/f
  h5an    1404   2.68 |     2.010     0.9353 |     4.289     0.0002 |   23.027    0.0000 |    1.932    0.9545 | f/f/f/P
  h6vd     475  -7.44 |     3.455     0.0000 |     7.375     0.0000 |   39.589    0.0000 |    3.322    0.0000 | f/f/f/f
  h7ul    1404   2.28 |     2.010     0.7101 |     4.289     0.0000 |   23.027    0.0000 |    1.932    0.7618 | f/f/f/f
  h8dp    1404   2.45 |     2.010     0.8231 |     4.289     0.0000 |   23.027    0.0000 |    1.932    0.8625 | f/f/f/f
  h9mc     476   2.53 |     3.451     0.1014 |     7.367     0.0000 |   39.548    0.0000 |    3.318    0.1380 | f/f/f/f
  h10xq   1404  -9.03 |     2.010     0.0000 |     4.289     0.0000 |   23.027    0.0000 |    1.932    0.0000 | f/f/f/f
  h11mj   1404   2.45 |     2.010     0.8190 |     4.289     0.0001 |   23.027    0.0000 |    1.932    0.8581 | f/f/f/f
  h12lt    674   2.75 |     2.900     0.4115 |     6.191     0.0000 |   33.235    0.0000 |    2.788    0.4786 | f/f/f/f
  h13ps   1404   1.93 |     2.010     0.4261 |     4.289     0.0000 |   23.027    0.0000 |    1.932    0.4970 | f/f/f/f

Check 1 - differences above 0.02
- Versus central_gates.csv: none. The largest |difference| on any number (a, the three t's, the gains, the
  book/incumbent/sleeve Sharpes, all three DSRs, every year) is 6.8e-12.
- Versus the builders' gates.json (2x block):
  - a, the t's, the gains, the Sharpes, the years and the G1, G2, G3 and G5 flags all agree within 4.8e-5.
  - The differences above 0.02 are all builder-time DSR (and its sr0_ann / n_trials):

    | Idea | Builder DSR | Binding DSR | Note |
    |---|---|---|---|
    | h1pb | 0.000 | 0.385 | |
    | h2fr | 0.000 | 0.421 | |
    | h4nl | 0.000 | 0.811 | |
    | h5an | 0.956 | 0.935 | builder G4 = PASS, binding G4 = FAIL |
    | h7ul | 1e-11 | 0.710 | |
    | h8dp | 0.000 | 0.823 | |
    | h9mc | 0.000 | 0.101 | |
    | h11mj | 0.186 | 0.819 | |
    | h13ps | 0.498 | 0.426 | |

  - Cause: 10 of the 13 worktrees still carry the pre-deviation scripts/hunt/gates.py (md5 b5f55e8e), whose
    n_trials uses the plain variance. h11mj carries the 06:00-UTC pooled version (0778d5a5); h12lt and h13ps carry
    the final one. The ledger was also smaller when each builder ran.
- Sensitivities (all immaterial):
  - Calendar-time instead of positional rf interpolation moves no gate number by more than 1e-4.
  - DSR with ddof-1 Sharpe and population moments moves DSR by at most 0.002.

3. G4 - DEFLATED SHARPE (TABLE 2 above)
--------------------------------------
- gates.deflated_sharpe against Bailey & Lopez de Prado (2014): correct.
  - SR0 = sqrt(V) x [(1 - g) Phi^-1(1 - 1/N) + g Phi^-1(1 - 1/(N e))], with g the Euler-Mascheroni constant.
  - DSR = Phi[(SR - SR0) sqrt(T - 1) / sqrt(1 - skew x SR + (kurt - 1)/4 x SR^2)].
  - SR is the non-annualised daily Sharpe and kurt is non-excess kurtosis (pandas kurt + 3).
  - V = vz / T puts every trial's dispersion on this record's length. That is a sound mapping of BLdP's
    V[{SR_n}] when trials ran on different lengths.
  - Small departures: SR uses ddof 0, and skew/kurtosis are pandas' bias-corrected versions. Both are immaterial
    (at most 0.002).
- gates.n_trials matches the deviation-log rule:
  - z = daily_sr x sqrt(n_days), minus the idea's median z;
  - vz = max(1.1257, (1.4826 x median|zw|)^2);
  - N = 3000 + all 188 rows.
  - Ledger checks: no NaN z, no duplicate idea/variant rows. The 2 "descriptive" wave3 rows and h9mc's 2 step-1
    rows are counted.
  - The code takes the MAD around 0, not re-centred on the median of zw. A textbook re-centred MAD gives the same
    1.2178.
- Final values: within-idea 1.2178 (binding; above the floor), pooled 5.5487, plain 159.9111. Every idea fails G4
  under all three rules.
- No verdict depends on the vz choice, because no idea passes G1-G3.
- The only knife-edge is h5an: 0.9353 under the binding value, but 0.9545 (a PASS) if the floor alone bound.
  - The DSR crosses 0.95 near vz = 1.15.
  - The final within-idea vz sits above the floor only because of h1pb's 21 trials. Leaving out one idea at a time
    gives 0.57 without h1pb, 0.70 without h2fr, h6vd or h10xq, and 1.97 to 2.00 without h4nl, h5an or h9mc.
  - The within value was 0.29 at h5an's freeze and 0.50 at 06:35 UTC, which is why the log then said the floor
    binds.
  - So one idea's G4 depends on another idea's trial grid. h1pb's grid mixes minute and sync modes with DEV book
    Sharpes from -27 to +3.2. The within-idea MAD is meant to remove exactly this kind of family heterogeneity, and
    here it carries it in (MATERIAL item M3).
- Structural, not an error: SR0 is 2.01 on 1,404 days but 3.45 on 475 days. Because the book contains the
  incumbent, a perp-era book needs a Sharpe of about 5 to reach DSR 0.95. That is correct BLdP scaling for short
  records.

4. HOLD-OUT DISCIPLINE PER IDEA (check 3)
-----------------------------------------
How I checked:
- I scanned every commit before the commit that adds frozen.json, reading the blobs with `git show`. In every
  parquet, csv, pkl and json under reports/hunt/<id> and data/hunt/<id>, I looked for rows dated on or after
  2026-06-01 and for P&L-like columns (scan_prefreeze.py, scan_pnl_cols.py).
- I compared the mtimes of daily.parquet and gates.json with the freeze commit time.
- I read the GitHub Actions run metadata through `gh run list` (read-only): when each run was created, its head SHA,
  and whether that SHA descends from the freeze commit (runs_vs_freeze.py).
- I re-applied the selection rule to the ledger rows (check3_select.py).

Results:
- Every frozen variant equals the ledger argmax of DEV alpha t (incumbent at $70K) above the SPEC's trade/event
  floor.
- No ledger row was logged after any freeze.
- Every gates.json and daily.parquet was first written after its idea's freeze commit.

All times are UTC. "Freeze" = the commit that adds frozen.json; "HOLD" = where the HOLD-dependent outputs first
appear.

| Idea | Freeze | HOLD | Frozen = argmax? (runner-up) | Finding |
|---|---|---|---|---|
| h1pb | 649038b 08:37:34 | Actions runs created 08:38:31-36 on post-freeze code 03cd8a4; shards 08:43; gates 49c1c77 08:46:24 | yes, t 2.885 (sync_k6_long_H60 -0.81) | clean |
| h2fr | c2c9149 05:50:53 | daily.parquet written locally +89 s; 7b64eb8 05:53:37 | yes, t -0.946 (-1.357) | clean |
| h3lm | no freeze (8a649af 06:03:45 records NO FREEZE) | HOLD never computed | n/a (would-be pick dens_N14_R30-10_H60 = argmax) | clean |
| h4nl | c912018 06:13:08 | +18 s; 213eb2f 06:21:54 | yes, t 1.211 (1.090) | clean |
| h5an | 1c05af4 05:27:04 | +35 s; a85ec70 05:29:21 | yes, t 2.863 (2.428) | clean; one gray-zone data reduction (MINOR) |
| h6vd | 1bf0d58 06:27:16 | Actions run created 06:27:19 at the freeze SHA; bf49cc7 06:28:46 | yes, t -7.78 (-9.44) | clean |
| h7ul | 5d3eeff 05:55:18 | +9 s; 01966aa 05:56:18 | yes, t 1.941 (1.839) | clean; HOLD test vacuous (MINOR) |
| h8dp | 0b70ec7 06:37:12 | c8b0942 06:41:17; re-run 1c31b3f 06:56:19 | yes, t 1.900 (tp7 1.888) | clean |
| h9mc | 7c378c0 06:27:44 | Actions run 06:28:04 on post-freeze code; 0eb6e8e 06:33:11 | yes, t -1.066 (-1.555) | clean |
| h10xq | b4711ad 07:21:03 | +47 s; 3dbbfa0 07:22:02 | yes, t -10.90 (-11.04) | clean |
| h11mj | dc1a462 06:33:58 | Actions run created 06:34:06 at the freeze SHA; 381b3f6 06:34:42; re-run e36ce60 06:43:26 | yes, t 1.927 (1.054) | clean |
| h12lt | 8c728e6 08:44:09 | Actions run 42356387221 (pre-freeze code 5086a14) committed 235025e at 08:43:35 | yes, t 1.740 (0.784) | BREACH (MATERIAL M1) |
| h13ps | d0d8277 08:06:34 | +25 s; c4f4d45 08:09:18 | yes, t -0.041 (-0.211) | clean |

Details by idea:
- h1pb
  - The DEV entries in dev/ (26 shards) and dev2/ (10 shards) contain no fill or close on or after 2026-06-01.
  - The frozen time-of-day variant is on the SPEC grid ("+1 with orders only in that window"). It is the best of 21
    trials, its parent has t -0.81 and its complement -2.61, and its HOLD t is -0.16, a typical selection fall-back.
  - The level-inputs v2 fix came before any DEV P&L and is a logged deviation.
- h3lm: the paired-t >= 2 stop rule is in the SPEC; daily.parquet holds DEV days only; gates.json records no gate.
- h4nl: the pre-freeze HOLD-dated files are raw minute candles only, which are allowed.
- h5an (MINOR gray zone)
  - data/hunt/h5an/px_*.parquet (Actions, 05:03-05:06, before the freeze) holds first-print entry and exit prices
    for 11 HOLD events, a reduction ready to turn into P&L.
  - That is allowed as a data download, and the fetcher logs no prices or returns.
  - All reports/ files before the freeze are DEV-only.
- h6vd: the HOLD run started 3 s after the freeze, on the freeze SHA itself.
- h7ul (MINOR)
  - A schedule-only scan before the freeze showed zero qualifying HOLD unlocks. This is disclosed in frozen.json.
  - So the HOLD read was vacuous: the sleeve is all zeros, and the printed HOLD t of -1062 is an artefact of an
    excess return equal to -rf.
- h8dp
  - One post-HOLD re-run for the shared paging bug, logged with the prefix files kept.
  - Every gate number moved by less than 0.01 (full t 1.549 to 1.546).
- h10xq: three print-check runs dispatched before the freeze (07:16:55-58) finished after it. Their inputs are DEV
  fills only.
- h11mj
  - One post-HOLD re-run for its own print-unit bug plus the shared paging fix, logged with the originals kept.
  - Full t moved 1.27 to 1.44; HOLD t moved 1.24 to 0.83; HOLD gain moved +0.38 to +0.20.
  - So the fix lowered HOLD; it did not tune to pass.
  - The gate series' DEV t (1.38) is below the selection t (1.93) because post-launch fills were re-priced on
    prints. This is documented.
- h12lt (MATERIAL M1)
  - Actions run 42356387221 was created at 08:39:11 on the pre-freeze code 5086a14.
  - Its commit 235025e (08:43:35) wrote trades_ai70.parquet and trades_base.parquet. They hold 325 and 491 HOLD
    trades with per-trade gross and net P&L.
  - The same commit wrote pre_ai70.pkl and pre_base.pkl, with HOLD-day signal outcomes (975 and 1,473 HOLD rows).
  - The 5 DEV trials were logged at 08:43:58-59 from that same run. The freeze commit followed at 08:44:09, and its
    message says "HOLD not yet read".

5. DAILY.PARQUET SANITY (check 4; check4.csv)
--------------------------------------------
- Index integrity: all 13 files have no dates outside the scored calendar, no duplicate dates, no NaN, and no
  missing scored day inside their span.
- Spans:
  - 1,404 days from 2022-01-01 for most ideas;
  - 475 days from 2025-07-19 for h1pb and h6vd;
  - 476 days from 2025-07-18 for h9mc;
  - 674 days from 2025-01-01 for h12lt (its SPEC starts the scored days in 2025);
  - h3lm: 1,246 DEV days, ending 2026-05-31.
- Costs:
  - 2x never beats 1x, on average or on any single day.
  - Annual 1x cost drag on the $30K sleeve: h1pb 20.0%, h6vd 124%, h10xq 258%, h3lm 11.0%, h11mj 8.5%, h8dp 6.3%,
    h12lt 5.0%, h2fr 4.0%, h9mc 3.6%, h13ps 3.5%, h5an 3.3%, h7ul 2.6%, h4nl 0.4%.
- HOLD rows:
  - All 12 ideas that read HOLD have 158 HOLD rows. They are non-zero wherever the idea traded.
  - h1pb: 504 HOLD trades on 115 days equals 115 non-zero days, and $750.4 of P&L from the trade list equals the
    daily series.
  - h13ps: 21 trades on 16 days equals 16. h7ul: 0 events equals 0.
- $50K versus $30K:
  - Fixed-ticket sleeves (h1pb, h5an, h6vd, h13ps, and h4nl at 1.0002) make identical dollar P&L at both capitals,
    so their per-dollar returns are exactly 0.6x at $50K. That is plausible.
  - Capital-proportional sleeves scale sub-linearly or about linearly (dollar ratio at 1x): h2fr 1.47, h3lm 1.51,
    h7ul 1.68, h8dp 1.45, h11mj 1.47, h10xq 1.19, h12lt 1.11.
  - h9mc earns 3.5% fewer dollars at $50K than at $30K (0.965). That is mildly odd but harmless, since the idea
    fails at t -2.18 (MINOR).

6. INCUMBENT (check 5)
---------------------
- incumbent_daily.parquet reproduces incumbent_summary.csv exactly (difference < 1e-5) for ret_yr (sum / years)
  and Sharpe (above T-bills), in every era x capital cell for the "instant" bound at theta 0.5:

  | Era | $50K | $70K | $100K |
  |---|---|---|---|
  | 2022-23 | 16.57% / 2.017 | 16.06% / 2.024 | 18.34% / 2.509 |
  | Jan 2025 - Mar 2026 | 35.44% / 2.608 | 34.69% / 2.588 | 35.32% / 2.603 |
  | Apr - Nov 2026 | 23.50% / 3.079 | 23.19% / 3.062 | 22.40% / 3.064 |

- The pre-registration table is reproduced:
  - $100K Sharpe: all scored days 2.47, DEV 2.35, HOLD 3.64;
  - calendar years +15.6%, +21.0%, +38.7%, +18.8% YTD.
- The gates use the same series. All 13 worktrees carry a byte-identical incumbent_daily.parquet (md5
  10cc0c9e0148, committed once in c9eb72e, before the pre-registration). Builder and central t's agree to 5e-5.
- Structural note, not an error: in 2022-23 the incumbent's Sharpe is 2.02 at $50K/$70K but 2.51 at $100K.
  - The gap is concentrated on crash days. On 2022-11-08 the $70K book lost 2.68% against 1.63% at $100K; on
    2022-05-11, 2.89% against 2.52%.
  - Over all days that is 2.30 at $70K against 2.47 at $100K.
  - So for the full-period ideas, the book's incumbent leg starts about 0.17 Sharpe behind the benchmark. This is
    pre-registered (the benchmark is the incumbent with all $100K), but it raises the effective G3 hurdle.

7. SCORECARD (check 6)
---------------------
- The automatic parts reproduce scorecard.csv exactly for all 13 ideas, and every total equals the sum of its 10
  parts. The automatic parts are out-of-sample, statistical strength, 2x years, top-3 concentration and
  diversification; they are computed from the central gate values and s30_2x on the scored days.
- They follow the rubric, with one exception: the code gives 1.5 for 0.2 <= correlation < 0.4, which the rubric
  ("< 0.2 (3)") does not allow.
  - That adds 1.5 to h11mj (correlation 0.210) and h12lt (0.332).
  - Under the strict rubric h1pb (53) ranks 4th, ahead of h11mj and h12lt (52 each), not 6th.
- Hand scores whose own rule or reason contradicts them:
  - h5an rob_neigh = 4. The stated rule allows only 5 or 2-3. The reason lists the one-step neighbours (delta 10 s
    t 0.31, H30 2.43, spot-only 2.26), all positive, so the rule gives 5. The "30 s turns negative" variant is two
    steps away.
  - h11mj capacity = 4 ("80% of trades at the full $30K") and h10xq capacity = 4 ("60% of fills at the full $5K").
    Both are partial deployment, which the rules score 1-3 (the pre-registration says 2-3). Neither is stated at
    theta 0.25.
  - h4nl and h8dp capacity = 1. That is inside the coordinator's 1-3 band but below the pre-registration's 2-3.
  - All other hand-score arithmetic matches its reason.
- None of these changes the top of the ranking: h5an stays first.

8. BIAS AGAINST NEAR-MISSES (check 7: h5an, h1pb, h7ul, h12lt, h8dp, h4nl)
--------------------------------------------------------------------------
Verified correct, so nothing here pushes a result down:
- Capital mapping in gates.path_b: a = 0.7 pairs $30K with inc($70K); a = 0.5 pairs $50K with inc($50K); the
  benchmark is inc($100K).
- The a grid is {0.7, 0.5}, picked on DEV book Sharpe. h1pb picked 0.5 (3.181 against 3.151); everyone else 0.7.
- Each sleeve is scored on its own scored days, against the incumbent on the same days.
- Idle days are 0, and P&L is booked on the exit day (checked in h1pb book.py, h5an sim.py, h7ul sim.py and h12lt
  sleeve.py, and in the HOLD trade-list reconciliations).
- Costs are applied exactly once at 2x. I read each cost function:
  - h1pb: maker fee in and out, plus taker fee and 1.5 x half-spread on time exits, plus funding, all x mult. Gross
    P&L uses raw exit prints, so the spread is not double counted.
  - h5an: half-spread charge and taker fee x mult, on raw prints.
  - h4nl: 6 bp maker, 17.5 bp taker including the SPEC's 5 bp half-spread, x mult.
  - h7ul: side cost = mult x (fee + 1.5 x half-spread). The 10%/yr carry on hypothetical shorts comes from its SPEC.
  - h8dp: maker, taker and half-spread x mult once.
  - h12lt: tiers and SPOT_HS_BP x mult. Square-root impact stays at 1x, which is lenient rather than harsh.
- The incumbent series is identical everywhere.
- h12lt's AI filter covers the HOLD quarters, with 16-111 trades a month in Jun-Nov 2026 (November partial).

Shared-code drift, bounded (MINOR):
- h5an's gate series uses prints fetched at 05:03 UTC by the pre-fix common.TradeFetcher. That version loses the
  older prints of the second at each 1,000-print page boundary.
- From its 10-second bars (median 2.8 and p90 35 prints/s at entry), the expected number of DEV entries affected
  is about 1.05 of 184, and of exits about 0.18. Each shift is less than one second.
- G1 needs +0.13 in t, about +11 bp per trade on average, so the paging loss cannot supply it.
- Empirically, h8dp's real re-fetch moved its full t by -0.003.
- Six other worktrees (h2fr, h3lm, h4nl, h6vd, h7ul, h9mc) also carry the pre-fix common.py. None of them is near a
  gate.

Structural conventions that decide gates for the near-misses (not errors; pre-registered and applied consistently):

S1. Idle sleeve cash earns nothing, but T-bills are subtracted (BUILDER_GUIDE: "a sleeve that holds cash is not
    credited with interest").
- The spanning regression therefore charges about rf (3.7%/yr) on the sleeve's whole notional capital.

  Full-period alpha t at 2x, prereg convention vs idle cash credited with T-bills (y = raw sleeve returns,
  x = raw incumbent returns), at the chosen a:

  | Idea | Prereg | Credited | HOLD t prereg | HOLD t credited |
  |---|---|---|---|---|
  | h5an | 2.87 | 3.80 | 0.31 | 0.79 |
  | h1pb | 2.07 | 3.46 | -0.16 | 0.64 |
  | h4nl | 1.53 | 3.97 | 1.28 | 2.04 |
  | h8dp | 1.55 | 2.98 | -3.09 | -1.85 |
  | h12lt | 1.61 | 2.37 | 0.50 | 1.54 |
  | h7ul | 1.90 | 2.35 | n/a | n/a |

- This convention alone decides G1 for h5an, h1pb and h4nl.
- Even on an all-cash-credited upper bound (raw-return Sharpes), no idea clears G1-G3 together:
  - h4nl: G1 and G2 pass (HOLD t 2.04, HOLD gain +0.56), but the full gain is +0.11, so G3 fails;
  - h1pb: G1 passes and the full gain is +0.81, but G2 fails (HOLD t 0.64, HOLD gain +0.23);
  - h5an: only G1 passes (full gain +0.36, HOLD gain +0.25 with t 0.79).
- So the "none passes" verdict survives the alternative convention.

S2. Fixed-ticket sleeves at a = 0.5 carry extra idle capital. h1pb's t is 2.60 at a = 0.7 but 2.07 at the chosen
    a = 0.5, with an identical dollar series. That is S1 again. The book gain barely moves (0.457 against 0.427).

S3. The incumbent capital effect (section 6) costs the full-period books about 0.17 Sharpe against the benchmark
    before the sleeve adds anything.

S4. 2x costs are decisive for h1pb.
- At 1x (information only) it passes G1 (t 5.59), G2 (HOLD t 2.57, HOLD gain +1.44), G3 (+1.55) and G5. It fails
  only G4, at 0.878.
- At 2x it fails G1 through G4.
- On the 1,414 frozen-variant trades, gross P&L averages $1.06 per contract, against $0.83 of costs at 2x
  ($0.42 at 1x). ETH grosses $0.46 per contract against $0.81 of costs.
- The per-contract fee is unverified, as the deviation log says. The rule is the pre-registered 2x.

Other near-misses at 1x, for information: h5an fails G2 and G3; h8dp fails G1 (2.89) and G2; h4nl, h7ul, h12lt and
h11mj fail G1. No idea passes all five gates at 1x either.

Result of check 7: I found no error in the shared code or in the gate inputs that pushes any near-miss's gate
down. The gates that the near-misses miss are decided by the pre-registered conventions S1-S4 and by HOLD.

9. DISCREPANCIES, RANKED
------------------------
VERDICT-CHANGING
- None. No correction in this audit, alone or combined, turns any idea into a pass.

MATERIAL
M1. h12lt computed and committed HOLD P&L before its freeze.
    - What: run 42356387221 (pre-freeze code 5086a14) committed 235025e at 08:43:35Z. It contains
      reports/hunt/h12lt/trades_ai70.parquet (325 HOLD trades with net_real, net_base and net_adv),
      trades_base.parquet (491) and pre_*.pkl (HOLD signal outcomes).
    - Timing: the DEV trials were logged at 08:43:58Z from the same run, and the freeze 8c728e6 followed at
      08:44:09Z. This breaches "No statistic, fill count or P&L on HOLD days may be computed before the freeze
      commit".
    - Disclosure: none. The REPORT and the freeze message ("HOLD not yet read") do not mention it.
    - Mitigation: the frozen T3_ai70 is the mechanical argmax of the 5 SPEC trials (t 1.740 against 0.784). The
      pipeline printed only DEV counts. HOLD fell back to t 0.50 and gain +0.12.
    - Verdict: unchanged (G1 1.61, G2 0.50/+0.12, G3 +0.15).
M2. h5an's own gates.json and commit a85ec70 report G4 PASS (DSR 0.956, with N = 3020 and vz at the floor). The
    binding central value is 0.935, a FAIL.
    - The same staleness affects 8 other builder DSRs (section 2). 10 of 13 worktrees still carry the plain-variance
      gates.py.
    - central_gates.csv is right; anyone reading the builder files would see a different G4.
    - Verdict: unchanged (h5an fails G1, G2 and G3).
M3. G4's binding within-idea vz is unstable. It is above the floor only because of h1pb's 21 trials (leave-one-out
    range 0.57 to 2.00).
    - h5an's G4 flips between PASS (0.9545 at the floor) and FAIL (0.9353 at 1.2178) depending on another idea's
      trial grid.
    - Verdict: unchanged (h5an fails G1-G3).
M4. Convention, not an error: the T-bill charge on idle sleeve capital (S1) decides G1 for h5an, h1pb and h4nl, and
    G2's t for h4nl.
    - It is pre-registered in the builder guide and consistent across the book and the benchmark.
    - With idle cash credited, those G1s would pass. Still, no idea would clear G1-G3 (section 8).
    - Verdict: unchanged.

MINOR
m1. Shared-code drift. 10 worktrees carry the old gates.py: builder DSRs are provisional and superseded centrally. 6
    worktrees, and h5an's fetch run, used the pre-paging-fix common.py: the h5an effect is bounded at about 1 entry
    of 184, and h8dp's real re-fetch moved its t by -0.003.
m2. h5an's px_*.parquet, committed before the freeze, holds entry/exit print prices for 11 HOLD events. That is an
    allowed data download, but it is a P&L-ready reduction.
m3. h7ul knew before its freeze that HOLD has zero qualifying events (disclosed). Its G2 was untestable, and the
    reported HOLD t (-1062) and HOLD sleeve Sharpe (-3680) are artefacts that should read n/a.
m4. Scorecard diversification gives 1.5 for 0.2 <= correlation < 0.4, which is not in the rubric (h11mj, h12lt +1.5).
    Under the rubric h1pb moves from 6th to 4th.
m5. Hand scores outside their own rule: h5an rob_neigh 4 (should be 5); h11mj and h10xq capacity 4 (partial, so
    1-3); h4nl and h8dp capacity 1 (below the pre-registration's 2-3 partial band).
m6. edge.book.rf_daily interpolates positionally, so a day's rf depends on the scored index. Effect under 1e-4 on
    every gate number.
m7. gates.n_trials takes the MAD around 0, not around the median of the demeaned z. No effect (1.2178 either way).
m8. gates.deflated_sharpe uses a ddof-0 Sharpe with bias-corrected skew/kurtosis. Effect at most 0.002.
m9. gates.dev_screen defaults to the incumbent at $100K, while the selection rule uses $70K. Builders used $70K,
    except h3lm's ledger t (at $100K). No selection is affected.
m10. h9mc makes 3.5% fewer dollars at $50K than at $30K (1x). Not a gate issue.
m11. h12lt's SPEC selection floor is at least 100 trades, against the pre-registration's 40. No effect (every trial
     has at least 1,279).
m12. h1pb's frozen variant is a time-of-day subset (orders only 4:55-6:05 pm ET), legitimately on its SPEC grid.
     Its parent and complement are negative (-0.81, -2.61), and its HOLD t is -0.16. The scorecard already notes the
     selection risk.
