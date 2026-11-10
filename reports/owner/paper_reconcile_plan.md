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

## Deviation log
(none yet)
