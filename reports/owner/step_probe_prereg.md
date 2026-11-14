# How early is the venue's trades list complete? A probe (plan fixed Nov 14 2026, 10:55 ET, before any data)

## Why
- The live bot's step starts 6 s after each minute, because the venue's candle for the closed minute is not ready
  earlier. A bar built from the venue's trades does not have to wait for the candle.
- The research assumes a bid rests for its whole minute. Every second the step starts earlier is a second more of
  resting. The timing study (reports/owner/timing/README.md) puts a second at about one point of the research's
  same-minute fills.
- Whether the step may start earlier depends on one fact that nobody has measured: how soon after a minute closes
  the public trades list holds that minute completely, as judged by the bot's own check.
- This is a fidelity question (class 1 in the charter). No P&L is read.

## What is measured
- **Symbols:** the 18 of the fourth paper book's list (BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR,
  NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC).
- **The request and the check** are the engine's own: `bot.market.minute_trades_bar`, with its pace of at most
  seven requests a second, one after another. Nothing about the check is changed.
- **For each minute m, which closes at q = m + 60 s:**
  1. **Early pass.** Starts at q + 1.0 s on the runner's clock. BTC first, as in the engine; the other 17 in an
     order that moves on by one place every minute, so every coin is sampled at every place.
  2. **Standard pass.** Starts at q + 6.0 s, or when the early pass ends if that is later. Same order. This is when
     the engine asks today.
  3. **Reference pass.** Starts at q + 35 s, for the minute before m (closed 95 s earlier). Its verified bar is the
     reference for that minute.
- **Recorded for every request:** coin, minute, pass, the second after q at which it was sent, how long it took,
  verified or not and why not, pages, when the venue generated the first page (against q), the number of trades and
  the bar. Raw trades never leave the runner.
- **Load on the venue:** 54 requests a minute, never more than seven in a second.
- **Stop:** a refusal or a rate-limit answer ends the probe at once. Nothing is retried or worked around, and it is
  reported.

## Runs
- Two runs of 300 minutes each on a GitHub runner: one on Nov 14 2026 (a Saturday) and one on Monday Nov 16 from
  13:30 UTC (a US weekday morning, when late prints are most likely). They are read together and shown apart.
- If a run stops early for a fault of the runner or of the script, it is repeated at the same hours of the next
  like day, and that is logged here.

## Measures
By pass and by the second at which the request was sent: early pass [1, 2), [2, 3), [3, 4), [4, 6); standard pass
[6, 10). Requests outside these bins are counted and shown, not ruled on.
- **V, verified share:** of the requests in the bin, the share the engine's check accepts.
- **E, equal share:** of the verified ones whose minute has a verified reference, the share whose open, high, low
  and close all equal the reference bar's. A minute with no trades in both counts as equal. Volume is shown beside
  it.
- **BTC** is shown apart at its own place, the first request of each pass.
- Also shown, with no rule: how long a request takes by coin, and how long each pass takes.

## Rule (fixed now)
- **The step may start at second s (1, 2, 3 or 4)** only if all of these hold over both runs together:
  1. in every bin of the early pass from [s, s + 1) on: V at least 99.0% and E at least 99.5%;
  2. in each of those bins, E is no more than 0.3 points below the standard pass's E;
  3. for BTC, which is sent at second 1.0: V at least 99.5% and E at least 99.5%. If BTC fails at 1.0 s, no second
     earlier than 6 passes on this probe, because the probe has BTC at no other early second.
  4. every bin that is ruled on holds at least 2,000 requests, and BTC at least 500.
- **The earliest second that meets the rule is the candidate.** It becomes a setting only through a release, and a
  paper book runs it first.
- **If no second meets it,** the step stays at 6 s and the result is recorded as a known gap.
- The rule is code before the first run is read (scripts/owner/step_probe/rule.py, with tests).

## What this probe cannot say
- It runs on a GitHub runner. The live bot's server may see the venue a little sooner or later.
- It compares an early bar with the trades list 95 s later, not with the venue's final candle. The paper books
  compare trades bars with candles every minute (the counters in their heartbeats).
- Two runs of five hours are a sample. The paper book that runs the candidate is the longer test.

## Deviation log
(none yet)
