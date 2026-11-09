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
- 18:27 Data agent done (branch signal-lab-data, c175f8a). 16 fetch shards 17:12-18:19, 79.1M prints, 10,042 merged
  windows, one feature row per candidate (17,527 main, 14,563 early). Data-quality gate passes: 100% complete windows
  in both eras; median print USD over candle USD 1.0002 in both. Its look-ahead unit test passes; the side convention
  checks out (falling windows show taker-sell shares above one half).
- 18:33 Review of the QA found a timing risk: prints and the repo's candles disagree in 14-23% of minutes, mostly with
  volume in the neighbouring minute. If a candle for minute q holds trades stamped before q, "prints before q" sees
  part of the fill minute. Sent the data agent back for a boundary-offset diagnostic and for feature tables whose
  windows end 5 s and 60 s before q. No model runs on print features until this is settled.
- 18:35 Independent look-ahead audit started (separate Opus agent at max effort, read-only), on the print-feature
  code, the join, the mixed panel, the drivers' holdout lock and the scorer.
- 18:47 Deviation 2 logged before the diagnostic reported: gate result and the data agent's choices accepted; the rule
  that picks the table (smallest margin among 0 s, 5 s, 60 s with under 0.5% of candidates leaking in each era); the
  information readings on the other margins.
