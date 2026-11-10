# Paper against research, Nov 6 to Nov 10 2026

Plan: reports/owner/paper_reconcile_plan.md (fixed before any number here existed). Branch owner/reconcile.

(Results follow once the runs are done. The deviations below were written on Nov 10 2026 at about 19:16 UTC, before
the comparison was run.)

## Deviations from the plan, and additions

- **D1. Start-up minutes are not decision minutes.** The plan's period leaves out the gaps the log records
  (catch_up events). The log also shows that each paper job makes its first decision only 4 to 6 minutes after it
  starts: it first downloads 11 days of candles (the first job's first step is exactly known: its adv event is at
  22:36, six minutes after its backfill at 22:30). When one job follows the next without a gap, no catch_up is logged,
  so these minutes are in the plan's period but the bot decided nothing in them. Counting them would add research
  bids that the bot could not have. So the comparison leaves out, for each job start, the minutes from its backfill
  minute up to its first step (the first event only a step writes, if it is at most 6 minutes later; otherwise 6
  minutes, the longest start-up seen). Both figures are reported: the plan's live hours and the decision hours.
- **D2. One failed step.** The step of Nov 7 21:19 raised an error before the model ran. That minute is left out too.
- **D3. Bot armed state across a start-up.** After a logged gap the bot cancels every armed bid, so its next bids are
  new. After a start-up with no logged gap it keeps them. The research rule follows the same logic: a research bid
  is new when it was not armed at the previous decision minute, or when a logged gap lies in between.
- **Addition A1 (not a plan measure).** At every minute with a bot first bid, the engine's code is also run with
  BTC's newest one and two minutes missing from its table (what a late BTC answer gives the bot). This shows directly
  whether the bot's price equals the price a late BTC gives. The plan's own test (beta times BTC's late return) is
  reported as written.
- **Computation.** The research side is computed minute by minute with the engine's own functions (no vectorised
  panel), so no vectorisation check is needed.
