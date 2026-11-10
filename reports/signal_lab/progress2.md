# Signal lab 2 progress log (Nov 9 2026, times ET from the shell clock)

Goal (Miles): continue the signal lab by running the pre-registered next test (prospective_prereg.md): forced-selling
features from Coinbase trade prints as inputs to R2-08's model. The main agent orchestrates; Opus agents at max effort
build and run; a separate Opus agent audits for look-ahead before the one holdout read. Five seed triples per arm.
"No change" is acceptable. Deliver a 100-point scorecard, verdict and next test.

Where things live: branch signal-lab (worktree /home/claude/wt/v6x). Plan: reports/signal_lab/prospective_prereg.md
with its deviation log. Data job: branch signal-lab-data (cut from hunt2, which carries the Actions runner and the
print fetcher).

## Log
- 16:44 Task received.
- 16:47 Checks: this session can reach GitHub Actions. The runner workflow is not on branch signal-lab (dispatch
  refused there), so the data job gets its own branch cut from hunt2.
- 16:48 Deviation 1 logged before any fetch or run: how "big" prints are defined from the fetched windows, the
  data-quality gate, the every-minute panel for the binding test (exact at candidate minutes, no-prints twin elsewhere,
  with two sensitivity runs), the order of reads (selection era, audit, one holdout read), a matched-selectivity
  reading, seeds and hand scores.
- 16:50 Two Opus agents started at max effort, in parallel: (1) the print-data job on GitHub Actions, in its own
  worktree and branch (signal-lab-data); (2) the pipeline changes on branch signal-lab, validated on the selection era
  with synthetic features only. The holdout readings are locked behind a file only the orchestrator creates after the
  audit.
- 17:41 Pipeline agent done (c592ae7). Built: the five print features joined to candidate rows, RF6 and RF6H, seed
  sets, the mixed every-minute panel, a separate scorer configuration (reports/signal_lab/test2/), three drivers, and
  a lock on the two holdout drivers. Reviewed: 7 of 7 unit tests pass here; the incumbent's parity line is unchanged
  (trades identical, daily diff 0.0); validation used synthetic features on the selection era only. Accepted its three
  choices: in the all-armed sensitivity run an unarmed minute is raised just above the threshold (funded last); the
  replay's one-ulp threshold read is left as is; history rows with print features go to test2/cand_early.parquet.
- 17:41 Data job: 16 fetch shards running on GitHub Actions since 17:13.
- 18:35 Data agent done (branch signal-lab-data, c175f8a). 16 fetch shards 17:12-18:19, 79.1M prints, 10,042 merged
  windows, one feature row per candidate (17,527 main, 14,563 early). Data-quality gate passes: 100% complete windows
  in both eras; median print USD over candle USD 1.0002 in both. Its look-ahead unit test passes; the side convention
  checks out (falling windows show taker-sell shares above one half).
- 18:37 Review of the QA found a timing risk: prints and the repo's candles disagree in 14-23% of minutes, mostly with
  volume in the neighbouring minute. If a candle for minute q holds trades stamped before q, "prints before q" sees
  part of the fill minute. Sent the data agent back for a boundary-offset diagnostic and for feature tables whose
  windows end 5 s and 60 s before q. No model runs on print features until this is settled.
- 18:37 Independent look-ahead audit started (separate Opus agent at max effort, read-only), on the print-feature
  code, the join, the mixed panel, the drivers' holdout lock and the scorer.
- 18:42 Deviation 2 logged before the diagnostic reported: gate result and the data agent's choices accepted; the rule
  that picks the table (smallest margin among 0 s, 5 s, 60 s with under 0.5% of candidates leaking in each era); the
  information readings on the other margins.
- 18:55 Selection reading on the 0 s table done (run agent; test2_m0/selection.txt; frozen simulator, five seed
  triples, walk-forward stopped at 2026Q1). ΔSharpe against R2-08 with the same seeds, mean (SD), triples positive:
  RF6 +0.06 (0.14), 3 of 5; RF6H +0.43 (0.14), 5 of 5; at R2-08's selectivity RF6M +0.02, 2 of 5; RF6HM +0.39, 5 of 5.
  R2-08's five triples reproduce the first lab's exactly (mean 2.396, SD 0.130). Every candidate found its feature
  row; 24 main and 211 history rows have a missing feature.
  - Against the no-prints twins (first lab's dose_seeds_main.csv): the prints add +0.06 to R2-08 (SD 0.14) and +0.06
    to the history model (RF6H against RF0H: SD 0.03, 5 of 5). Most of RF6H's +0.43 is the added history (+0.37),
    which did not carry out of sample in the first lab.
  - This table's windows end at the candidate minute, so the reading stands only if the boundary diagnostic clears it.
- 18:59 Audit's first report: pass with conditions. No look-ahead in the feature code, ADV, join, walk-forward, mixed
  panel, lock or scorer (all checked directly; candidate timestamps are candle starts). One major finding, the candle
  clock: trades stamped before the candidate minute sit in its candle for 0.1-0.3% of candidates, and 0.6% / 1.6% /
  1.6% (selection / Apr - Nov 2026 / 2022-23) once candidates with a missing previous candle are counted. Deviation 3
  logged: the 0.5% bar per read era, missing previous candles count as leaks under 0 s and 5 s, one margin for every
  row, and a second audit pass on the margin code before the lock is created.
- 19:07 Data agent's follow-up done (signal-lab-data 440314f): boundary diagnostic, per-candidate leak flags, and the
  5 s and 60 s tables. The candles mostly lead the prints by about 8 s (harmless). Leaking candidates under 0 s /
  5 s / 60 s: selection 0.45% / 0.44% / 0.00%; Apr - Nov 2026 1.71% / 1.68% / 0.05%; 2022-23 1.45% / 1.45% / 0.14%.
  Only 60 s is under the 0.5% bar in every read era. Deviation 4 logged: the 60 s table is the primary; the test
  does not use the last minute before the fill.
- 19:15 Audit's second pass: final pass. The margin code keeps every feature before q - 60 s (unit test passes on 42
  cases); its recount of the leak flags matches deviation 4 exactly; even if every missing-candle merge also counted
  at 60 s the shares would be 0.01% / 0.29% / 0.34%; no sign of a lag above 60 s. The 60 s tables match the 0 s
  tables on keys, order, threshold and ADV (sha256 main 583d3de7..., early 9e652994...), and the exported history
  rows carry exactly the 60 s features. One sanity check of mine was too strict (sums 1-2 float units above the 0 s
  table, a rounding artifact); a 1e-12 tolerance was approved. The lock is created once the selection reading on the
  60 s table has finished and is logged.
- 19:19 Selection reading on the 60 s table, the primary (run agent; test2_m60/selection.txt; frozen simulator, five
  seed triples, walk-forward stopped at 2026Q1). ΔSharpe against R2-08 with the same seeds, mean (SD), triples
  positive: RF6 -0.01 (0.05), 2 of 5; RF6H +0.50 (0.15), 5 of 5; at R2-08's selectivity RF6M -0.05, 3 of 5; RF6HM
  +0.42, 5 of 5.
  - What the prints add: to R2-08, -0.01 (0 s table: +0.06); to the history model (RF6H against the first lab's
    RF0H), +0.13 (SD 0.05, 5 of 5; 0 s table: +0.06). History alone is +0.37.
  - So in sample the last minute before the fill adds nothing measurable, and the prints help only beside the
    history. The holdout decides.
- 19:20 Lock opened (test2/AUDIT_PASSED, commit 355ee5b) after the audit's final pass and with the selection reading on
  the 60 s table committed. The run agent starts the one holdout read: the seed-averaged reading (test2.py b), then
  the binding test (test2.py c), on the 60 s table, with nothing decided between them. About two hours.
