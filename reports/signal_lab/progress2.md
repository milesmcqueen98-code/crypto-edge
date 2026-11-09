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
