# Candle probe: results

Plan: `reports/owner/candle_probe_prereg.md` on branch owner/charter (fixed before any probe data existed).
Code: `scripts/forward/candle_probe.py` on branch owner/plant.

Run used: 42853095116 (hunt2 on a GitHub runner). Boundaries 16:19 to 18:23 UTC on Tue Nov 10 2026, 125
minutes, nine coins. No source was refused or rate limited. One request timed out (an Exchange candle at 1 s).
The derived tables are in this folder: `obs.parquet` (one row per coin, minute, source and delay, with the
planned, request and response times, the cache status, Age, the newest minute returned, and the OHLCV seen;
plus the reference rows), `run.json`, and the CSV tables below. No raw trades were stored.

## The reading under the rule

**Outcome C: no source is usable at a delay of 25 s or less. No change now; a live trade feed is specified as its
own project.**

- **Trades:** they meet the timing test at every delay (all nine coins done within 2 s in 100% of minutes). But
  their material-error share is 6.8% at 1 s, 6.4% at 3 s and 6.0% at 6 s, above the 1% bar.
- **Candles:** no candle source gets to 1% at 25 s or less. The best is Advanced at 6 s (5.2%), then Exchange at
  3 s and 10 s (5.8%).
- **The other reading of the reference gives the same outcome.** It counts cache copies without an Age header
  as valid references (749 coin-minutes instead of 516): trades 6.0 / 5.6 / 5.2%, best candle 4.7%.

## Plan measures (all answers; 516 counted coin-minutes)

A coin-minute counts if its reference exists and that answer was made at least 180 s after the boundary. Columns:
missing, exact and material are % of coin-minutes; errors are in basis points (absolute); "vol p5" is the 5th
percentile of volume as a share of the reference; "sent" is the median request time in seconds after the boundary.

| source | delay | sent | missing | exact | material | close bp med / p95 / max | low bp med / p95 / max | vol p5 |
|---|---|---|---|---|---|---|---|---|
| Exchange candles | 1 | 2.63 | 7.4 | 75.6 | 14.2 | 0 / 15.6 / 38.0 | 0 / 1.1 / 38.0 | 0.44 |
| Exchange candles | 3 | 4.88 | 0.2 | 87.2 | 5.8 | 0 / 9.3 / 38.0 | 0 / 0 / 38.0 | 0.53 |
| Exchange candles | 6 | 7.63 | 5.4 | 83.5 | 10.7 | 0 / 11.5 / 38.0 | 0 / 0 / 38.0 | 0.65 |
| Exchange candles | 10 | 11.13 | 1.6 | 89.1 | 5.8 | 0 / 6.3 / 19.3 | 0 / 0 / 19.4 | 0.76 |
| Exchange candles | 15 | 15.50 | 51.6 | 46.9 | 52.1 | 0 / 0 / 19.1 | 0 / 0 / 18.9 | 1.00 |
| Exchange candles | 25 | 25.50 | 9.5 | 84.1 | 12.2 | 0 / 0.6 / 38.2 | 0 / 0 / 38.2 | 0.37 |
| Exchange candles | 40 | 40.50 | 4.8 | 95.2 | 4.8 | 0 / 0 / 0 | 0 / 0 / 0 | 1.00 |
| Advanced candles | 6 | 6.50 | 0 | 89.0 | 5.2 | 0 / 9.3 / 38.0 | 0 / 0 / 38.0 | 0.67 |
| Exchange trades | 1 | 1.50 | 0 | 65.3 | 6.8 | 0 / 16.5 / 80.1 | 0 / 3.9 / 51.9 | 0.73 |
| Exchange trades | 3 | 3.50 | 0 | 76.0 | 6.4 | 0 / 12.9 / 38.0 | 0 / 1.6 / 38.5 | 0.78 |
| Exchange trades | 6 | 6.50 | 0 | 82.2 | 6.0 | 0 / 9.3 / 38.0 | 0 / 1.0 / 38.5 | 0.79 |
| the bot's own URL (descriptive) | 9.5 | 10.00 | 2.9 | 83.1 | 9.1 | 0 / 14.4 / 39.4 | 0 / 0 / 38.0 | 0.60 |

The candle rows do not fall steadily with delay (15 s is worse than 10 s; 25 s is worse than 3 s). That is the
cache, not the venue: each delay asks a different URL, and some URLs are filled early by other clients (see
"The cache" below).

**Measure 5 (trades):**

| delay | pages per coin-minute (mean / max) | coin-minutes with more than 1 page | first request to last response, all nine coins (median / p99 / max s) | within 2 s |
|---|---|---|---|---|
| 1 s | 1.008 / 3 | 0.7% | 1.04 / 1.29 / 1.30 | 100% |
| 3 s | 1.008 / 3 | 0.7% | 1.02 / 1.27 / 1.30 | 100% |
| 6 s | 1.009 / 3 | 0.8% | 1.02 / 1.29 / 1.45 | 100% |

About 1.0 s of that span is the probe's own pacing (nine requests at 8 a second). BTC took more than one page in
4 to 5% of minutes (at most 3), and finished in 0.29 s at most.

## Where the trades errors come from

The trades bar's material errors are not lateness:
- **Trades agree with Advanced.** The 6 s trades bar and the 6 s Advanced candle agree on 91% of coin-minutes.
- **The errors sit in a few coins.** At 6 s there are 39 of 749 coin-minutes (all coins; the wider reading): PEPE
  21, ONDO 9, DOGE 8, HYPE 1. BTC, ETH, SOL, XRP and ZEC have none.
- **They are mostly one price tick.** One PEPE tick is 19 bp of price, more than half its one-minute sigma
  (14 bp). So a close one tick away from the Exchange candle counts as material.
- **Likely cause.** The trades bar and the venue's own candle differ by a trade near the minute boundary, or by
  one tick. This is the limit the plan named in advance.

## By coin (material-error %, all answers, strict reference)

| coin | counted minutes | Exchange 6 s | Exchange 25 s | Exchange 40 s | Advanced 6 s | trades 1 s | trades 3 s |
|---|---|---|---|---|---|---|---|
| BTC | 8 | 87.5 | 12.5 | 100 | 0 | 0 | 0 |
| ETH | 8 | 87.5 | 12.5 | 100 | 0 | 0 | 0 |
| SOL | 8 | 87.5 | 25.0 | 100 | 0 | 0 | 0 |
| XRP | 8 | 87.5 | 25.0 | 12.5 | 0 | 0 | 0 |
| DOGE | 0 | | | | | | |
| HYPE | 117 | 0.9 | 0 | 0 | 0.9 | 1.7 | 1.7 |
| ZEC | 117 | 0 | 0 | 0 | 0 | 1.7 | 0 |
| ONDO | 125 | 6.4 | 0 | 0 | 6.4 | 7.2 | 7.2 |
| PEPE | 125 | 14.4 | 45.6 | 0 | 14.4 | 17.6 | 17.6 |

The large coins have few counted minutes: their reference URL was usually a copy made too early, or a copy with
no Age (see Limits). The full table, with trades at 6 s, is `by_coin_material.csv`.

## BTC on its own

BTC counts in only 8 minutes under the strict reference (`btc_measures.csv`). In those minutes:
- trades are exact at 6 s in 8 of 8 (0 material at 1, 3 and 6 s);
- Advanced candles are exact in 8 of 8;
- the Exchange candle at 6 s is missing in 7 of 8.

Over all 125 minutes, without a reference (`btc_candle_vs_trades.csv`, `bot_url.csv`):
- **BTC's Exchange candle at 6 s was stale in 60 of 125 minutes.** Its newest minute was older than the one asked
  for, or it was empty.
- **BTC trades were present at 1, 3 and 6 s in every minute,** stale candle or not.
- **The bot's own BTC URL was a cache copy in 125 of 125 minutes.** 82% of those copies were older than 10 s, and
  the asked minute was missing in all 125. The newest minute it returned was 1 to 2 minutes behind.

## The cache

Coinbase answers through Cloudflare, cached by the exact URL. Exchange candles say `max-age=300`, trades
`max-age=5`. `cache.csv` has every source and delay; `cache_by_coin.csv` splits it by coin.

| source | delay | HIT | not fresh | Age > 10 s | answer made before the boundary |
|---|---|---|---|---|---|
| Exchange candles | 1 | 42.6% | 42.6% | 27.4% | 308 |
| Exchange candles | 6 | 47.1% | 32.4% | 13.2% | 148 |
| Exchange candles | 15 | 77.8% | 77.8% | 46.9% | 528 |
| Exchange candles | 25 | 60.6% | 60.1% | 46.0% | 393 |
| Exchange candles | 40 | 34.7% | 34.7% | 22.0% | 246 |
| the bot's own URL | 9.5 | 29.5% | 26.6% | 19.1% | 215 |
| Exchange trades | 1 | 86.1% | 51.4% | 0 | 452 (40%) |
| Exchange trades | 3 | 94.0% | 63.0% | 0 | 173 (15%) |
| Exchange trades | 6 | 90.0% | 59.9% | 0 | 0 |
| Advanced candles | 6 | 22.8% | 0.1% | 0 | 0 |

(1125 answers per row. "Not fresh" = a HIT with Age above 1 s, or a HIT with no Age. "Made before the boundary"
= response time minus Age is before q. Date minus Age gives the same counts.)

- **Trades:** a 1 s answer was made before the minute closed in 40% of minutes, and a 3 s answer in 15%. Those
  copies were made at second 59 of the previous minute. No 6 s answer was ever made before the boundary (Age is
  at most 5 s).
- **The bot's own URL, by coin:**

| coin | copy (HIT) | copy older than 10 s | asked minute missing |
|---|---|---|---|
| BTC | 100% | 81.6% | 100% |
| ETH | 79.2% | 62.4% | 73.6% |
| SOL | 16.8% | 6.4% | 2.4% |
| XRP | 16.0% | 6.4% | 2.4% |
| ZEC | 13.6% | 6.4% | 0 |
| DOGE | 12.8% | 4.0% | 0 |
| HYPE | 12.8% | 4.0% | 0 |
| PEPE | 7.2% | 0.8% | 0 |
| ONDO | 7.2% | 0 | 0 |

**Fresh answers only (descriptive, `measures_fresh_only.csv`).** A fresh answer shows what the venue itself
has, without the cache:

| source | delay | material, fresh answers only | counted |
|---|---|---|---|
| Exchange candles | 1 | 6.4% | 470 |
| Exchange candles | 3 | 5.3% | 507 |
| Exchange candles | 6 | 5.6% | 486 |
| Exchange candles | 10 | 4.3% | 508 |
| Exchange candles | 15 | 1.2% | 250 |
| Exchange candles | 25 | 0.0% | 345 |
| Exchange candles | 40 | 0.0% | 491 |
| the bot's own URL | 9.5 | 5.2% | 479 |

So the venue's own candle is final by about 25 s after the minute closes. Before that, the venue is still filling
it in. After that, only a cached copy can be wrong.

## Why BTC's candles were stale: my best account

- **The mechanism.** Another client asks the same URL before the minute has closed. Cloudflare keeps that answer
  for up to 300 s and serves it to everyone who asks the same URL, the bot included.
- **The copies are old.** The stale BTC answers are HITs whose Age puts their making 50 to 120 s before the
  boundary. On the bot's URL the median copy was made 58 s before the boundary. Copies made before the boundary
  were made at a median of second 13 of a minute (quartiles 4 and 42).
- **They lack the minute asked for.** Their newest minute is the one before. The asked minute did not exist yet
  when the copy was made.
- **The venue itself is current.** At the same moments, BTC's Advanced candles and BTC's trades were current, and
  answers to other window URLs (MISS) had the minute.
- **The copies are not ours.** None of the probe's own requests matches the URL of an old copy made Age seconds
  earlier (0 of 2666).
- **The pattern is by URL and coin.** It hits the most-asked coins (BTC, then ETH, SOL, XRP) and particular
  windows (start 9 minutes back for seven of nine coins). That is what popular windows asked on a fixed schedule
  by other clients would produce.
- **What I cannot verify.** I cannot see who the other clients are or why they ask early. The cache is per
  Cloudflare location, so a paper bot running elsewhere may see a different picture. The probe measured one
  GitHub runner's location.

What this means for the paper bot (descriptive, not a rule outcome):
- **Its BTC request was a stale copy every minute** at this location: for BTC the newest minute was always 1 to
  2 minutes behind.
- **Nothing flags it.** update_spot keeps what it has, and arrays() forward-fills a missing close for up to 30
  minutes without an error. So the bot's BTC features ran 1 to 2 minutes late, silently.
- **ETH was the same in about three quarters of minutes.**

## Consistency check against the collector

Material-error share of the 6 s Exchange candle (the collector's URL) for the nine coins. The collector's
reference is its own later sighting, 186 s after the minute closed, without Age checks:

| data | coin-minutes | material | missing at 6 s |
|---|---|---|---|
| collector, first hour (test branch, 14:17 to 15:13) | 414 | 27.5% | 15.0% |
| production collector, the probe's window (16:19 to 17:55) | 873 | 20.5% | 16.5% |
| production collector, BTC only, same window | 57 | 45.6% | 42.1% |
| probe, Exchange 6 s (sent at about 7.6 s), all answers, wider reading | 749 | 16.2% | 11.8% |
| probe, Exchange 6 s, strict reference | 516 | 10.7% | 5.4% |

The orders of magnitude agree. The probe's 6 s request went about 1.6 s later than the collector's (it queued
behind the trades), so it is somewhat better. For ETH the probe's 6 s answer was a copy in 100% of minutes: the
production collector asks the same URL at 6.0 s and fills the cache first.

## Request times (spread)

Actual request time minus planned, seconds:

| source | delay | min | median | p95 | max |
|---|---|---|---|---|---|
| Exchange candles | 1 | 1.13 | 1.63 | 3.25 | 3.75 |
| Exchange candles | 3 | 1.38 | 1.88 | 2.38 | 2.88 |
| Exchange candles | 6 | 1.13 | 1.63 | 2.13 | 2.38 |
| Exchange candles | 10 | 0.63 | 1.13 | 1.63 | 1.63 |
| Exchange candles | 15, 25, 40 | 0 | 0.50 | 1.00 | 1.00 |
| Exchange trades | 1, 3, 6 | 0 | 0.50 | 1.00 | 1.26 |
| Advanced candles | 6 | 0 | 0.50 | 1.00 | 1.00 |
| the bot's own URL | 9.5 | 0 | 0.50 | 1.00 | 1.00 |
| reference | 230 | 0 | 0.50 | 1.00 | 1.00 |

The 0 to 1 s spread is nine coins at 8 a second. The Exchange candles at 1, 3, 6 and 10 s waited behind the
trades (entry 1), so "1 s" candles were really sent at 2.1 to 4.8 s.

## Limits

- **Two hours of one weekday afternoon, from one Cloudflare location.** Another location, or a fast market, may
  look different.
- **The strict reference leaves few minutes for the large coins.** Their reference URL was usually a copy made
  before 180 s, or one with no Age (233 of 1125 reference answers were HITs without an Age header). So BTC, ETH,
  SOL and XRP count in only 8 minutes each and DOGE in none. The counted sample is mostly HYPE, ZEC, ONDO and
  PEPE. The wider reading (749 coin-minutes) gives the same outcome.
- **The reference is the venue's own final candle.** Trades and that candle can differ near the boundary or by a
  tick (the plan's stated limit). That alone keeps the trades bar above 1% for PEPE, ONDO and DOGE.
- **Age is whole seconds and is missing on some HITs,** so a generation time is accurate to about 1 s, and
  unknown for a HIT with no Age.
- **Several runs before this one were not used** (entries 3 and 4). The production collector's candle answers
  from 16:03 to 16:14 UTC may be copies of the first design's requests (see scripts/forward/README.md).
- **What the mismatch costs in P&L is not measured.**

## Deviation log

Written before the work each entry covers.

Implementation choices. These fill in details the plan leaves open; none changes a measure or the rule.

1. **Pacing order inside a slot.** Exchange requests (candles, trades, reference) share one pace of 8 a second,
   under the venue's public limit of 10 a second (burst 15). The Advanced host has its own pace of 8 a second. Among
   requests already due, trades pages go first, then the first trades page per coin, then candles, then reference
   requests. Reason: the rule's trades test ("all coins done within 2 s") would otherwise measure my pacing, not
   the venue. Cost: the Exchange candles planned at 1 s and 3 s are sent later than planned, by about 1 to 2.5 s
   (the 3-minute dry run, before this ordering was final: 1 s candles sent at 2.1 to 3.4 s, 3 s candles at 4.5 to
   5.9 s). Even so, nine coins at 8 a second spread each source's requests over about 1 s. The actual request times are stored and the spread is reported for each source and delay.
2. **No retries for timed requests.** A timed request that fails (timeout, 5xx, network) is stored as failed and
   counts as missing in measures 1 and 3. A retry would change the delay being measured. Failures are reported
   separately. Reference requests are retried up to three times (their timing does not matter, as long as it is
   at least 180 s).
3. **Reference timing.** The reference for minute q-1 is requested at q + 230 s (second 50 of a later minute,
   when nothing else is due). It is the bot's own request (the 5-minute window ending at q). If the reference
   request fails three times, the coin-minute does not count (the plan counts a coin-minute only if the reference
   exists).
4. **Trades paging.** One page holds up to 1000 trades, newest first. The probe pages back (`after` = the oldest
   trade id) until the oldest trade is before the start of minute q-1, with at most 20 pages. Trades are reduced
   to open, high, low, close and volume on the runner. The raw trades are never stored.
5. **Requests that stop a source.** A refusal (403, 451, a bot check) or a rate limit (429) stops that source for
   the rest of the run, as the plan says. The probe makes no retry with other headers or addresses.
6. **Sigma.** The one-minute sigma per coin is the standard deviation of the log returns between reference closes
   of consecutive minutes (both present), over the run.

Deviations from the plan:

1. **BTC added (the plan's own amendment, commit 30f65ca on owner/charter, before any data).** Nine coins: BTC plus
   the eight. The rule is read on the nine together; BTC is also reported on its own. BTC minutes can take more
   than one page of trades; the probe pages back to the start of the minute (up to 20 pages) and records the pages
   and the time taken. Pacing is unchanged (8 a second per host), so a slot now holds 18 or more Exchange requests.

2. **A descriptive column added (before the 120-minute run).** The dry runs found Exchange BTC-USD candles missing
   at every delay, the reference included, while BTC trades and Advanced candles were present. A runner diagnostic
   at 15:59:38 UTC got BTC's newest candle as 15:57, with the values identical to a call a minute earlier, while
   ETH already had 15:58. The forward collector, on another runner, got BTC on time in the same minutes. The
   requests are the same in every part (BTC-USD, granularity 60, ISO start and end, the window ending at the
   minute just closed). So the probe now also stores `newest`, the newest candle minute in each Exchange and
   Advanced candle response. That tells a stale response from a missing minute. It changes no measure and no part
   of the rule. Nothing about the request was changed to get around it (no headers, no addresses, no
   cache-busting parameters).

3. **The venue answers from a URL-keyed cache: requests made distinct (written before the restarted run).** A
   runner diagnostic (run 42851465479, LTC, a coin outside the probe, 16:09 UTC) showed:
   - Exchange candle responses carry `cache-control: public, max-age=300` and come from Cloudflare (`cf-cache-status`).
   - The identical URL (the bot's 5-minute window) was a MISS at 1.5 s and then a HIT with the 1.5 s body at 4,
     11, 31, 61, 121 and 181 s (Age 2 to 179).
   - A window with a different start was a MISS each time, with fresh values (close 50.169 at 1.5 s, 50.136 at 4 s).
   - Exchange trades (`limit=1000`) carry `max-age=5`: a trades answer can be up to 5 s old.

   The first 125-minute run (42850392993) asked the same URL at every delay and for the reference, so its later
   delays and its reference were copies of the first answer. It was cancelled after about 10 minutes and is not
   used. The stale BTC candles of entry 2 are the same effect: an earlier request for that URL, by someone else,
   was served to the probe.

   Changes for the restarted run (no headers, addresses or cache-busting parameters; each request is an ordinary
   candle window):
   - **The 6 s Exchange request keeps the 5-minute window ending at the minute just closed.** (Correction, entry
     4: this is the collector's URL, not the bot's steady-state URL.)
   - **The other delays use the same end but start further back:** 1 s 6 minutes, 3 s 7, 10 s 8, 15 s 9, 25 s
     10, 40 s 11.
   - **The reference uses a 15-minute window.** It counts only if its response was generated at least 180 s
     after the boundary (response time minus Age); otherwise the coin-minute does not count.
   - **Every response's `cf-cache-status` and `Age` are stored** (for trades, those of the first page).
   - **Descriptive additions, not plan measures:** the share of cached answers per source and delay, the answer's
     age, and the measures restricted to fresh answers.

   Measures 1 to 5 and the decision rule are unchanged. One limit follows: another client can still fill the
   cache for any of these URLs first. The stored Age shows when that happened.

   The second run (42852693023) was cancelled before its first minute boundary, to add entries 4 and 5. It
   collected nothing.

4. **The bot's own URL added as a source (`bot_url`; requested by the orchestrator, written before the run).** In
   steady state the paper bot asks for start = T-4 min and end = T-1 min (bot/spot/engine.py update_spot: start =
   newest stored minute minus 2; the newest stored minute is normally T-2). The probe requests exactly this URL
   once per coin-minute at about 9.5 s after the boundary. That is after the paper bots have made their own
   request, so the probe can never be the one that fills that cache entry early. It stores the cache status, the
   Age, and the newest minute returned. This is a descriptive measure, not part of the rule.
5. **Exchange trades also at 6 s (in the plan's deviation log, by the orchestrator, before the data).** The trades
   URL is shared by every client and cached for 5 s, so a 1 s or 3 s answer may have been generated before the
   minute closed, while a 6 s answer cannot. 6 s is also when the bot steps today. The rule reads trades at 1, 3
   and 6 s the same way (material-error share at most 1%, all coins done within 2 s in at least 99% of minutes).
   Pacing fits all three delays (about 115 Exchange requests a minute; slots of about 20 at 8 a second), so none
   was dropped. Trades keep priority in a slot, so the 6 s candles go out about 1 to 2 s late, and the stored
   times show it. The `Date` header is stored too, so the answer's generation time is also Date minus Age.

6. **Cache copies with no Age header (written after the data; the only such entry).** Some HIT answers carry no
   Age header (233 of 1125 reference answers). The first analysis took a missing Age as 0, so such a copy counted
   as fresh and as a valid reference. That was a bug in my code, not a choice: a HIT with no Age is a copy of
   unknown age. Since entry 3 requires the reference to have been made at least 180 s after the boundary, and
   that cannot be shown for these copies, they are not counted. This leaves 516 coin-minutes instead of 749. Both
   readings are reported, and the outcome is the same (C).
