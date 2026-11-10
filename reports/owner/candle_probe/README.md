# Candle probe: results

Plan: `reports/owner/candle_probe_prereg.md` on branch owner/charter (fixed before any probe data existed).
Code: `scripts/forward/candle_probe.py` on branch owner/plant.

Results are added below after the run.

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
