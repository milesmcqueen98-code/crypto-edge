# Candle probe: when is the newest minute final, and from which source? Pre-registration (Nov 10 2026, 10:27 ET)

Written by the orchestrator before any probe data exists. Branch owner/charter; the probe runs from branch owner/plant.

## Why
- **The bot decides on a candle that is often not final.** The forward collector's first hour (Nov 10 2026, 753
  coin-minutes) followed the candle the bot reads 6 s after each minute closes:
  - 31.6% changed afterwards: the close in 28%, the volume in 30%, the high in 13%, the low in 12%;
  - 6% were missing at the decision and appeared later;
  - 21% of dollar volume was missing at first sight; 6.5% of candles had the low revised down by 5 bp or more.
- **The research trained and tested the model on final candles.** So live and paper feed the model inputs it was not
  trained on, most of all in fast minutes. Making the live inputs equal the research inputs is a fidelity fix: it
  cannot overfit, because it changes nothing about the model or the rules.
- **This probe decides the engineering path.** It measures when each source is final. It does not measure P&L.

## Design (fixed now)
- **Coins:** ETH, SOL, XRP, DOGE, HYPE, ZEC, PEPE, ONDO (liquid to thin, all in the traded universe).
- **Length:** one run of at least 120 minutes on a GitHub Actions runner, started as soon as the code is ready.
- **Each minute boundary q, each coin, for the minute that just closed (q-1):**
  - Coinbase Exchange candles (the bot's source), requested at about 1, 3, 6, 10, 15, 25 and 40 s after q;
  - Coinbase Advanced public candles, requested at about 6 s;
  - Coinbase Exchange trades, requested at about 1 s and 3 s, paged back to the start of the minute and reduced to
    open, high, low, close and volume;
  - the reference: Exchange candles for the same minute requested 180 s or more after q.
  - The request and response times of every call are stored. Requests are paced inside the venue's public limits; a
    refusal or rate limit stops that source and is reported, never worked around.
- **A coin-minute counts** if the reference candle exists (the minute had a trade).

## Measures (per source and delay)
1. Missing: no row for the minute.
2. Exact: high, low and close equal the reference and volume is within 0.5%.
3. Material error: missing, or the close differs from the reference by more than half of that coin's one-minute sigma
   (the standard deviation of one-minute log returns of the reference closes over the run), or the low differs by
   more than 5 bp.
4. Close error and low error in bp (median, 95th percentile, maximum); volume as a share of the reference.
5. For trades: pages per coin-minute, and the time from the first request to the last response for all eight coins.

## Decision rule (fixed now)
- A source at a delay is **usable** if its material-error share is at most 1% of coin-minutes.
- **Trades usable at 1 s or 3 s, with all coins done within 2 s in at least 99% of minutes:** the bot gets an option
  to build its newest bar from trades and to step earlier. It is built behind a switch (default off, the candle path
  kept as the fallback), tested like every bot change, run as a side-by-side paper book, and only then offered for
  the pilot. It is adopted as a fidelity fix, on the evidence that the inputs match, not on a backtest gain.
- **Otherwise, candles usable at some delay of 25 s or less:** the option is a later step at the smallest usable
  delay. Its timing cost is priced first with the timing study's symmetric valuation.
- **Otherwise:** no change now; a live trade feed is specified as its own project.
- Whatever the outcome, the collector keeps recording the 6 s case every minute, and the registry's 14-day read
  stands.

## Limits, stated now
- Two hours of one weekday. The venue's lag may be worse in fast markets, which is when it matters most.
- The reference is the venue's own final candle. Trade timestamps and candle buckets can disagree at minute
  boundaries (signal lab 2 found this in history), so a bar built from trades may differ from the final candle for
  reasons other than lateness. Measure 3 tolerates small differences for that reason.
- "Usable" says the inputs match. What the mismatch costs in P&L is not measured here.

## Deviation log
- **Nov 10 2026, 10:36 ET, before any probe data (orchestrator).** BTC is added to the coins, nine in all. BTC is not
  traded, but the model's levels and its BTC features read BTC's newest candle every minute, and BTC's candle was among
  the latest to fill in during the collector's first hour (33% of its dollar volume missing at first sight). The rule
  is read on the nine coins together; BTC is also reported on its own.
- **Nov 10 2026, 11:16 ET, before any valid probe data (orchestrator).** The first long run was cancelled after 12 minutes
  and its data discarded: Coinbase serves these public endpoints through a cache keyed by the exact address (candles
  may be reused for 300 s, the trades list for 5 s), and the probe had asked one address per coin-minute at every
  delay, so later delays got the first answer back. Changes for the new run, none of which works around the cache:
  - Every delay other than 6 s, and the reference, uses its own ordinary window, so each is a fresh answer. The cache
    status and age of every response are stored. A reference counts only if it was generated 180 s or more after the
    minute closed.
  - **Trades are also requested at 6 s.** A 1 s or 3 s trades answer can have been generated before the minute closed;
    a 6 s answer cannot. 6 s is when the bot steps today. The decision rule reads trades at 1, 3 and 6 s alike.
  - **One more source: the bot's own steady-state address** (the window from four minutes back to one minute back),
    requested once per coin-minute at about 9.5 s, after the paper bots' own request so the probe cannot fill that
    entry early. It shows how often the bots' own request is answered from a copy someone else made, and how old.
  - Reported in addition: cache-hit shares and ages by source, delay and coin; the measures on fresh answers only; the
    age of the newest row in each answer.
- **Nov 10 2026, 13:48 ET, after the result (orchestrator). The rule's third branch is not followed, for a reason the
  plan did not foresee.**
  - **The result.** Run 42853095116 (125 minutes, nine coins; reports/owner/candle_probe/README.md). No source reaches
    a material-error share of 1% at 25 s or less: the trades bar has 6.8%, 6.4% and 6.0% at 1, 3 and 6 s; the best
    candle answers have 5.2% (Advanced, 6 s) and 5.8% (Exchange, 3 s and 10 s). Trades pass the timing test (all nine
    coins done within 2 s in every minute). By the rule that is the third branch: no change now, and a live trade
    feed as its own project.
  - **Why the branch's remedy is dropped.** The trades are not late. The trades bar has no material error for BTC,
    ETH, SOL, XRP and ZEC. Its errors sit in PEPE, ONDO and DOGE and come from trades near the minute boundary and
    from one-tick differences (one PEPE tick is 19 bp, more than half its one-minute sigma). A live feed carries the
    same trades, so it would not close that gap. The project is not started.
  - **What replaces it.** The candle clock study (candle_clock_prereg.md, written at 13:30 ET before its data)
    classes each coin by where the venue cuts its candle. A coin cut at the minute may take its newest bar from
    trades. The others stay on the venue's candle answer until their cut is known.
  - **A defect the rule does not cover.** The bot's own BTC address returned an old cached copy in every one of the
    125 minutes (ETH in 79%), always without the minute asked for. That is a fault in how the bot reads its inputs,
    not a choice between sources, and the log entry of 11:04 already committed to a guard whatever the probe showed.
    It is fixed in release 2: the bot reads the age of every answer, never lets an older answer replace a newer or
    verified row, rebuilds recent rows of the listed coins from trades, and with the guard on places no new bid on an
    input it knows to be old.
  - **Nothing is switched on by this entry.** Release 2 keeps today's behaviour by default. A third paper book runs
    the new mode, and the rule for making it the default is fixed in FORWARD_TESTS.md before that book's first run.
  - **Limits of the result, as reported.** The counted sample is mostly HYPE, ZEC, ONDO and PEPE (117 to 125 minutes
    each). BTC, ETH, SOL and XRP count 8 minutes each and DOGE none, because their reference answers were themselves
    old copies. A wider reading that keeps those minutes (749 coin-minutes) gives the same outcome. On answers that
    were not copies, the venue's own candle was final by about 25 s (material-error share 4.3% at 10 s, 1.2% at
    15 s, 0.0% at 25 s and 40 s).
