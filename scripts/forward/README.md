# Forward data collector

Logs, once a minute, market data that cannot be downloaded later: how much is resting in the order book under
the bids, leverage state on the perp venues, and the candles exactly as the spot bot saw them when it decided.
The bot (bot/spot/) decides 6 seconds after each minute closes; the collector is timed around that moment.
It never trades and nothing in the bot reads it.

## The four streams

Universe: BTC plus the coins in bot/v2/model_meta.json (18 today). All times are UTC.

| stream | source | when in the minute | one row per |
|---|---|---|---|
| `book` | Coinbase Exchange `GET /products/<coin>-USD/book?level=2` (the full aggregated book) | 18 requests, paced 5 a second, timed to finish by second 5 | coin, minute |
| `hl` | Hyperliquid `POST /info {"type":"metaAndAssetCtxs"}` (one request) | second 5 | coin, minute (the universe coins; `--hl-all` for every perp) |
| `candles` | Coinbase Exchange 1-minute candles, the request bot/market.py `spot_candles` makes, last 5 minutes | from second 6, paced 5 a second | revision (see below) |
| `cfm` | Coinbase Advanced public `GET /products?product_type=FUTURE` (one request), perp-style products only | second 12 | US perp product, minute (all 29) |

**book**: `t` (when the response arrived), best bid and ask (price, size), `mid`,
`n_bid`/`n_ask` (levels returned), `bid_usd_<bp>` = USD resting on the bid side at prices within that many basis
points below mid (5, 10, 25, 50, 100, 150, 200, 300, 400, 600, 800), `ask_usd_<bp>` the same above mid (5 to 100),
and `bid_reach_bp`/`ask_reach_bp`, how far from mid the returned book goes. A bucket the returned book does not
reach is missing (NaN), never zero. Why the Exchange endpoint: the Advanced `product_book` used by the bot stops at
1000 levels, which for BTC reaches only about 1.2% below mid (ETH about 6.5%); the Exchange level-2 book is complete
for every coin (about 1 MB a minute for BTC, 3.7 MB for all 18; well within the runner's bandwidth).

**candles**: a revision log. A row is written the first time a (coin, minute) candle is seen and again whenever
any of open, high, low, close, volume changes in a later fetch; `seen` is when the response arrived, `rev` counts
revisions (0 = first).
Each candle is fetched five times (in minutes T+1 to T+5), so the log shows how complete a candle is when the bot
decides and how it settles over the next four minutes. A minute with no trades has no candle (Coinbase omits it).

**hl**: per perp: `name` as Hyperliquid lists it (kPEPE is 1000 PEPE; `px_mult` = 1000 and `coin` = PEPE),
`open_interest` (in coin units of the listing), `mark`, `oracle`, `mid`, `funding` (hourly rate), `premium`,
`impact_bid`/`impact_ask`, `day_ntl_vlm` (USD), `prev_day_px`. Delisted perps are skipped.

**cfm**: per US perp-style product (`*-CDE`): `product_id`, `coin` (the underlying, e.g. BTC, or an index root such
as CDEUS5), `price`, `mid_market`, `index_price`, `settlement_price`, `open_interest` (contracts; times
`contract_size` gives coins), `funding_rate`, `funding_time`, `funding_interval_s`, `volume_24h` (contracts),
`quote_volume_24h` (USD), intraday and overnight margin rates (`im_long`, `im_short`, `om_long`, `om_short`).
The response also has `best_bid`, `best_ask`, `mark_price` columns, but the venue leaves them empty today, so
they are stored as missing. Note: the filter `contract_expiry_type=PERPETUAL` returns the international venue
(`*-PERP-INTX`), not the US one; the US perps call themselves EXPIRING (in 2089) and are recognised by name.

Every stream is independent (its own thread each minute); an error or timeout is retried only within the minute,
counted, and written as a row with `ok = False` and missing values. A stream still hung from the previous minute
is skipped (counted as `busy`), never queued. If a venue refuses the client (403, 451, a bot check), that stream
stops for the rest of the run and the refusal is recorded in status.json. Coinbase requests (both hosts together)
are paced at 5 a second; the client identifies as `crypto-edge-bot/1.0`.

## Files

```
forward/<stream>/<YYYY-MM-DD>/<HH>-<run id>.parquet    one per stream, hour and run; never rewritten
forward/status.json                                    the latest heartbeat
```

Storage is lossless and compact, about 6 MB a day for all four streams (book 2.6, hl 1.3, cfm 1.1,
candles 1.2): zstd level 19, float columns byte-stream-split, no column statistics and no pandas metadata in the
footer. Prices, open interest, funding, candle values and timestamps are float64 / ms; depths, sizes, reach and
the 24h volumes are float32. Request send times (`t_req`) are not stored. Files before this change still carry
`t_req`; the reader reads both.

A file is written when its hour closes (and the partial hour at exit). If a name is taken (a restarted process
in the same run), `-2`, `-3` ... is appended. Two runs overlapping during a hand-over both write the same hour;
the reader removes the overlap: `book`, `hl` by (coin, minute), `cfm` by (product, minute), preferring a
successful sample and then the earlier one; `candles` merge the revision logs of all runs, keeping a row only where
the values differ from the previous sighting of that (coin, minute).

status.json: `heartbeat`, `run`, `started`, `planned_end`, `rows_last_hour` and `bursts_last_hour` per stream,
`errors` (counts since the run started, as `stream:kind`; kinds: net, timeout, http, http429, parse, deadline,
missing, busy, crash, write, refused, truncated, empty), `refused`.

## Two ways to run

**GitHub Actions (git mode)**: `.github/workflows/forward-collector.yml` on `main`. Each run checks out only
`scripts/forward/` and the coin list, makes `fwd/` a worktree of the `forward-data` branch without downloading
any data, and publishes with a plain commit and push: after each hour closes, at least every 30 minutes
(status.json), and at exit. A concurrent push from another run is absorbed by re-applying the new files on the
new tip, so there are no merge conflicts. Hand-over between runs: see the top of the workflow file and
`handover.py`.

```
python scripts/forward/collector.py --out fwd --branch forward-data --minutes 345
```

**A plain Linux server (no GitHub)**: only files, forever:

```
pip install pandas pyarrow requests
python scripts/forward/collector.py --out /srv/forward --no-git --minutes 0
```

Run it under systemd or a supervisor that restarts it. `--run-id` names the files (default `local`). It stops
cleanly on SIGTERM or Ctrl-C, writing the partial hour first. Options: `--hl-all` logs every
Hyperliquid perp (about 179; roughly 15 MB a day instead of 2), `--cfm-universe-only` keeps only the universe
coins' US perps; `--book-source advanced` uses the bot's endpoint instead
(shallower, see above).

## Reading it

Get the data branch without the history: `git clone --depth 1 --branch forward-data --single-branch
https://github.com/milesmcqueen98-code/crypto-edge.git fwd` (or `git pull` in it later). Then:

```
python scripts/forward/read.py status --root fwd            # coverage per stream per day, gaps, failed rows
python scripts/forward/read.py show book --root fwd --start 2026-11-10
```

```python
import sys; sys.path.insert(0, "scripts/forward")
from read import load
book = load("book", "2026-11-10", "2026-11-12", root="fwd")   # minute in [start, end), de-duplicated
revs = load("candles", "2026-11-10", root="fwd")
```

## Checking health

- `forward/status.json` on the branch: `heartbeat` should be under ~35 minutes old (it is pushed at least every
  30 minutes); `rows_last_hour` near 60 x 18 for book, 60 x the perp count for hl and cfm; `refused` empty.
- `read.py status`: minutes per day near 1440 and `longest_gap` 0 to 2 in normal operation.
- The workflow run log prints one line a minute: books ok and the first/last book response second, hl and cfm
  rows, candle coins fetched with the first request and last response second, and total errors.

## Known limits

- Files are written hourly, so a hard kill (no signal, for example a runner lost mid-job) loses up to that hour.
  Ordinary ends, cancellations and SIGTERM write the partial hour first.
- Times are the runner's clock (NTP-synced on GitHub runners); `t` is when the response arrived, not the venue's
  matching-engine time.
- The book is a REST snapshot, not a stream: what changed between snapshots is not seen, and the 18 coins are
  sampled over about 3.5 seconds, not at one instant.
- Candle settlement is observed for four minutes after a candle closes, not beyond.
- Scheduled GitHub runs can be late or skipped at busy times; the hour-long safety net is best effort.
