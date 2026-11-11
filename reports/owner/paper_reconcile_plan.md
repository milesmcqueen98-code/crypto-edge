# Paper against research, Nov 6 to Nov 10: reconciliation plan

Written by the orchestrator on Nov 10 2026, 14:08 ET, before any of its numbers exist. Branch owner/charter; the work runs from
branch owner/reconcile.

## Why
- The paper book's BTC input was late (candle probe, Nov 10), and its rung fills per running day are above forward
  rule A's band (8.3 a day against 1 to 6).
- The paper log records every new first bid: coin, minute, price and the model's score. Final candles for the same
  minutes exist now. So what the bot did can be set against what the research would have decided on final candles,
  minute by minute, on real forward data.
- This is a description. Nothing is chosen with it. It feeds the scorecard's block "the live bot matches the
  research", and it is repeated for the third paper book once that book has run for some days.

## Design (fixed now)
- **Period:** every minute the main spot paper book was live, from its first event to Nov 10 2026 13:30 UTC (the gaps
  its log records are left out).
- **Research side:** final one-minute candles of BTC and the 17 coins, fetched at least an hour after the last
  minute; the deployed model (bot/v2); the bot's own code for the table and the features (the engine's `arrays` and
  edge/wick.py `panel`). This gives the bid level and the model's score for every coin and live minute, as the bot
  would have computed them had its inputs been final.
- **Bot side:** the `arm` events (new first bids) and the rung-4 `fill_entry` events in paper_spot/events.jsonl, and
  the `cash_short` events.

## Measures (fixed now)
1. **Level error at the bot's new bids:** bot price against the research level for the same coin and minute, in bp:
   median, 5th and 95th percentiles, share beyond 5 bp and beyond 20 bp. And whether the error is what a late BTC
   predicts: beta times BTC's return over the last one and two minutes (correlation and slope).
2. **Score error:** the bot's score against the research score at the same coin and minute: median absolute
   difference, and the share that falls on the other side of the model's threshold.
3. **Bids:** of the bot's new first bids, the share the research also has at that minute or one minute either side;
   of the research's new first bids in live minutes, the share the bot has. Bids the log shows as blocked for cash
   are listed apart.
4. **First-bid fills:** bot fills the research would also have had (research armed, final low at or below the
   research level); fills only the bot had; fills only the research had. P&L of the bot's fills in each group, from
   the log.

## Limits, stated now
- The research side is the bot's own table and feature code on final candles, not the full backtest. Exits, deeper
  rungs and fill sizes are not compared.
- About 60 live hours of one book. W2 has the same inputs and is not repeated.
- Final candles themselves leave out trades in some minutes (candle clock study).

## Repeat for the third book's test (plan fixed Nov 10 2026, 21:29 ET)
Written before either book's log for these days has been read.
- **Period:** from the third paper book's first step (Nov 11 2026, about 01:50 UTC) to the end of its three-day
  test. Side-by-side numbers use the minutes in which both books were live. Each book's own live minutes are reported
  as well.
- **Research side:** unchanged, and one record serves both books: final candles fetched at least an hour after the
  last minute, the deployed model, the bot's own table and feature code.
- **Bot side:** the same events, from each book's own log (paper_spot and paper_spot_tb). The third book's bids
  skipped for a stale input are counted apart, as bids blocked for cash are.
- **Measures:** the same four, for each book. Each is also split into two groups of coins: ETH, SOL, XRP, LTC and
  ZEC, whose newest bar comes from trades in the third book, and the twelve on the candle path.
- **What a working fix should show** (written now, so the read cannot be bent to the result):
  - third book: bids more than 5 bp from the research level in a few percent of cases (main book, Nov 6 to 10: 40%),
    and no relation left between the level error and BTC's last-minute move (main book: correlation 0.94);
  - third book: fewer scores on the other side of the threshold (main book: 19%) and more bids in common (main book:
    67% and 77%);
  - main book: about what it showed on Nov 6 to 10, since its inputs are unchanged.
- **Use:** item 7 of the third book's rule reads the first two measures (FORWARD_TESTS.md). The rest is description.
  For the twelve coins, the third book's score error is the first measure of what their own newest candle costs once
  BTC is right. It decides whether the comparison of bar sources for them is worth running.
- **Limits:** three days of one market. Fills will be few and are not judged.
- **Interim looks** (added Nov 10 2026, 21:34 ET, before any look): the pipeline may be run on part of the period, to
  prove it works and to catch a fault early. An interim look can stop the test for a fault to be fixed (the three
  days then start again). It cannot pass the test, and it changes no rule.

### How the repeat is run (added Nov 10 2026, 22:02 ET; tools on `main` in scripts/owner/reconcile)
1. **A branch for the look,** made from `main` once both books' logs are on it (for example owner/read-tb-i1 for the
   first interim look, owner/read-tb for the read). The runner writes its tables to that branch; they go onto `main`
   after review.
2. **Research for both books, on a runner** (about 15 minutes). START is the third book's first event minute, END
   the last minute wanted, both UTC and written like 2026-11-11T01:50. The script refuses to fetch until END is an
   hour old.
   `gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref BRANCH
   -f script=scripts/owner/reconcile/fetch_and_compute.py
   -f args="--books paper_spot,paper_spot_tb --start START --end END --out reports/owner/reconcile_tb/NAME/research"
   -f tag=reconcile-tb-NAME
   -f sparse="bot edge scripts/owner reports/owner reports/cfm_products.csv paper_spot paper_spot_tb"
   -f commit="reports/owner/reconcile_tb/NAME/research"`
3. **The two-book comparison and item 7, offline:**
   `python scripts/owner/reconcile/two_books.py --research reports/owner/reconcile_tb/NAME/research --start START
   --end END --out reports/owner/reconcile_tb/NAME`
   It writes each book's tables, side_by_side.csv and item7.md. Item 7 alone:
   `python scripts/owner/reconcile/item7.py --dir reports/owner/reconcile_tb/NAME`.
4. **Edges, as built:** the measures are computed on each book's own minutes and then limited to the minutes both
   were live. Research bids at a minute where the third book logged a stale BTC are listed apart and leave the
   share's denominator, as bids blocked for cash do. Item 7 uses only each bid's level and score, so the
   one-minute edge effects at the period's ends do not touch it.

## Deviation log
(none yet)
