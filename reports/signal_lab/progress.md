# Signal lab progress log (Nov 9 2026, times ET from the shell clock)

Goal (Miles): raise R2-08's out-of-sample Sharpe at $250K by improving what the model knows (features, labels,
US-accessible data). Develop on Jan 2025 - Mar 2026, read the other eras once, count every trial, score on the
engine-faithful simulator, beat R2-08 head-to-head in every era. "No change" is acceptable. Work until 5 pm.

Where things live: branch signal-lab (worktree /home/claude/wt/v6x). Plan: reports/signal_lab/prereg.md.
Code: scripts/signal_lab/. Trial ledger: reports/signal_lab/screen.csv.

## Log
- 14:28 Task received. Read the hunt 3 log (another session: 66 new models, none beat R2-08).
- 14:36 Pipeline written (scripts/signal_lab/model.py): the lab's own code with a choice of label and feature set, then
  the frozen simulator. Finding while reading the lab: R2-08's label is one 4-sigma trade at perp per-contract costs,
  but the bot trades a spot ladder. That mismatch is the lead candidate.
- 14:37 Parity: the incumbent spec (RF0) through the new pipeline gives R2-08's 1,155 trades through Mar 2026 exactly,
  and the frozen simulator's daily series to 0.0. One spec takes about 14 seconds.
- 14:38 Pre-registration committed: 4 labels x 5 feature sets (19 trials), finalist rule, engine-faithful binding test,
  gates and scorecard.
