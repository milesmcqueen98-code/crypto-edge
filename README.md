# forward-data

Forward-collected market data for crypto-edge, written by scripts/forward/collector.py on the main branch
(see scripts/forward/README.md there). Nothing from main lives on this branch.

- `forward/<stream>/<YYYY-MM-DD>/<HH>-<run id>.parquet`: one immutable file per stream, hour and collector run
  (UTC). Streams: `book` (Coinbase spot depth), `candles` (revision log of the bot's candle view), `hl`
  (Hyperliquid perps), `cfm` (Coinbase US perp-style futures).
- `forward/status.json`: the latest collector heartbeat, rows per stream in the last hour, error counts.

Read it with `python scripts/forward/read.py status --root <checkout of this branch>`; files are never rewritten,
so overlapping runs are de-duplicated by the reader.
