# Owner's log

Dated decisions and results, newest last. Times are US Eastern. The plan is CHARTER.md; open tests are in
FORWARD_TESTS.md.

## Nov 10 2026

- **08:51. Handover.** Miles: the algorithm is the owner's to build and improve; goal is the best algorithm a Coinbase
  Advanced account can run, with a higher out-of-sample Sharpe and no overfitting.
- **Decision: no further search on history.** Three rounds found nothing above the noise (standard error about 0.16
  Sharpe on the pooled holdout), and both holdout eras are used up. Work moves to what can still be measured or
  earned: live order timing, new forward data, idle-cash yield and fees, and monitoring.
- **09:06. Live order timing study pre-registered** (reports/owner/timing_prereg.md, branch owner/timing).
  - Why: the bot re-prices 6 seconds after each minute closes, in two passes. The paper book's last heartbeat (Nov 10
    13:30 UTC) counts 334 re-priced bids in 30 minutes with 12 coins armed, about 93% of bid-minutes. In live that
    means an old bid for the first seconds of almost every minute, then a short gap with no bid. Paper fills cannot
    see it.
  - One deviation logged by the implementer before any data was fetched (where the last print before the minute comes
    from).
- **09:09. Charter and forward-test registry written** (this folder).
- **09:14. Paper status report live on main** (scripts/owner/paper_status.py, PAPER_STATUS.md, refreshed after every
  paper run and daily).
  - 09:16: errors can be marked as explained in explained_errors.json, by message, time window and book. Rule A counts
    unexplained errors only.
- **The Nov 7 paper error is explained.** A candle re-fetch that leaves out a minute an earlier fetch returned leaves
  the table out of order, and the next time slice fails. One minute with no new bids; the next minute repairs it. A
  one-line sort is being prepared and tested as release 1 (branch owner/release-1).
- **Perp paper books: one fill each in 3.3 and 3.7 days is not a signal yet.** The research rate on perp prices is 0.8
  fills a day for R2-08 and 1.05 for v1 (bot/README.md). With those rates, one fill or fewer has a chance of about
  0.26 and 0.10 if fills were independent, and wicks cluster, so the true chances are higher. A watch rule is in the
  registry.
- **Coinbase facts for the idle-cash and fee levers** (web research, Nov 10; nothing confirmed for New York):
  - USDC rewards need Coinbase One since Dec 15 2025 (reported). Coinbase's own pages show 3.50% (Coinbase One page)
    and 4.10% (USDC page), undated.
  - Coinbase One Preferred ($29.99 a month) returns 25% of Advanced spot fees in USDC, up to 100 USDC a month; Premium
    ($299.99) has no cap (Coinbase One page, undated). Not known: whether API orders in the bot's portfolio count.
  - The OCC's final rule on stablecoin rewards takes effect Jan 18 2027 and reviews programs case by case (reported).
    Rewards may stop or change then.
- **10:11. The machine's disk filled up** (several full checkouts of the repo, 1.8 GB each). Finished, fully pushed
  worktrees were removed; nothing was lost. One agent's tests were interrupted and are being re-run.
- **10:26. Timing study, first reading** (reports/owner/timing/README.md on branch owner/timing; 14.1M prints, 29,686
  studied minutes).
  - By the plan's rule: the live timing (P1) is 11.3% and 16.6% of P&L below the research assumption (P0) in the check
    era and 2022-23, and 4.8% above in selection. Fast re-pricing (P2) beats P1 by 8.6% and 17.5% and loses 7.1% in
    selection. Removing only the gap (P3) has no material effect.
  - **Deviation 2, logged before the follow-up:** the plan's valuation decides the reading (a missed parent loses its
    whole ladder, an added one counts its first rung only; a two-second change in timing moves the 2022-23 total by $10,231). Nothing is built on
    it alone. A like-for-like valuation (S1: first rung only; S2: whole ladder re-simulated) is running, with the same
    5% rule.
  - Not in doubt: P1 fills 87% / 90% / 83% of P0's parents in the same minute; 14-20% of P0's fills come in the first
    10 s of a minute; prints confirm 93-96.5% of the candle research's parents.
- **10:27. The collector's first hour shows the bot decides on unfinished candles.** Of 753 newest candles read 6 s
  after the minute closed, 31.6% changed later (close 28%, volume 30%, low 12%) and 6% were missing.
  - The research used final candles. This is a gap between research and the live or paper bot, not a model change.
  - **Candle probe pre-registered** (candle_probe_prereg.md): when is each source final (Exchange candles at 1 to
    40 s, Advanced candles, a bar built from trades at 1 and 3 s), with the decision rule fixed before any data.
  - **Charter: a fourth class of change, fidelity.** A fix that brings the live bot closer to what the research
    assumed is adopted on verification and tests, behind a switch, without needing a backtest gain.
  - **Storage:** 9.8 MB a day measured. The VM's clone is shallow, sparse and single-branch, so the data branch does
    not reach it. Lossless trims first, target about 6 MB a day.
- **10:36. Probe deviation, before data:** BTC added. The bid level of every coin is the coin's price 60 minutes ago
  moved by beta times BTC's return to the newest close, less four sigma (edge/wick.py `levels`). So BTC's newest
  candle is the input whose lateness moves every level.
- **10:39. Timing study closed: the bot's timing stays as built.**
  - Like-for-like valuation (whole ladder for every first bid, 4.8M deep prints): the live timing is +1.9% / -11.9% /
    -11.9% against the research assumption (pooled -5.1%); fast re-pricing is -3.8% / +7.1% / +11.1% against the live
    timing (pooled +2.6%).
  - **Deviation 4:** the two-era condition is met for fast re-pricing, and nothing is built on it. The live bot with
    calls 1.5 to 2.5 s faster (P1a) beats the central case by more than fast re-pricing does (pooled +6.3%), and the
    slower-call case is also slightly ahead. The order by P&L is not the order of speed, so the measure cannot rank
    timings: a shift of about two seconds changes 6-9% of first bids, and a few dozen ladders decide each era.
  - What holds: every realistic timing is within a few percent of the research assumption (pooled +0.9% to -5.1%);
    match rates of 83-90% in the same minute and 88-94% within two minutes; fills are spread roughly evenly in the minute.
  - **Rule B's reading fixed before the pilot:** a paper fill counts as matched when the live bot fills the same coin
    within two minutes either side. The 70% bar stays.
  - Queued for the next engine release: the heartbeat records when cancels and new bids finish each minute.
- **10:45. Release 1 ready** (RELEASES.md): the candle merge fix, and `wickctl update` no longer starts a stopped bot.
  - The fix passed the parity replay, the live-path simulation, the USDC test and the Coinbase sandbox test with
    identical results before and after.
  - Found in review: `wickctl update` always ended by starting the service, which runs live mode. An update on a VM
    with the bot set up but not started would have begun live trading. Changed and tested (7 of 7). The first update
    on the VM still runs the old copy, so the release note gives two manual commands for a bot that is not running.
- **Scorecard added to the charter:** 50 of 100 (39 before today). The largest open blocks are fills proven with real
  orders (17 points, the pilot) and the live bot matching the research (11 points, the candle probe and what follows).
- **11:03. Forward collector in production** (main d221c59; first run 42850829239). Storage about 6.2 MB a day,
  lossless. Each run collects for 5 h 45 min and starts its successor five minutes before it ends; an hourly schedule
  restarts collection after a crash.
- **11:04. Seen while setting up the probe: a runner was served stale BTC candles.** The same request that the collector
  answered on time on another runner returned BTC's newest minute two to four or more minutes old, with identical
  values a minute apart, while ETH was current. Not a refusal. The bot forward-fills a missing close for up to 30
  minutes, so a stale BTC table would move every level without any error. The probe now records the age of the newest
  row by source, delay and coin. A stale-input guard is on the list for the next engine release whatever the probe
  shows.
- **11:12. Corrections after an independent fact-check** (a separate agent checked about 125 claims in the owner's
  documents against their sources).
  - A shift of about two seconds changes 6-9% of first bids. The 10-17% written earlier is the live timing against
    the research assumption.
  - "About eleven ladders decide 2022-23" was not established; the entries now give the dollar change only.
  - The pilot's expected match with perfect capture is about 77-86% in the same minute and 82-90% within two minutes
    (the first version took the top of two ranges from different eras).
  - Charter: the 0.2% of daily volume cap is on the whole signal, which is then split in thirds; the best candidates
    were ahead by +0.03 to +0.18 Sharpe in the holdout eras; the fee rebate's Premium case is a range from both paper
    books.
  - Entries are back in time order.
- **11:18. Cause of the stale candles: a public cache.** Coinbase serves its public candle and trade endpoints through a
  cache keyed by the exact address. A candle answer may be reused for 300 s, the trades list for 5 s.
  - The probe's first long run asked one address at every delay, so later delays got the first answer back. It was
    cancelled after 12 minutes and its data discarded. The new run is logged in the plan: its own window for each
    delay, cache status and age stored, trades also at 6 s, and the bot's own address read at 9.5 s.
  - The bot's request can therefore be answered with a copy that another client made up to five minutes earlier. For
    BTC that moves every level, with no error.
  - The collector and the probe do not share addresses with the bots in the normal case: the bot's window starts four
    minutes back, the collector's five.
- **11:18. Decision: release 2 is being built now, behind switches, without waiting for the probe** (branch
  owner/release-2).
  - The newest minute's bar built from the trades list, with proof that it is complete and the candle as the fallback.
    The trades list is reusable for 5 s at most, so an answer read 6 s after the minute closes was made after it closed.
  - A guard that places no new bids in a minute when BTC's newest candle is missing.
  - Heartbeat counters for all of this, and the times at which the data, the cancels and the new bids finish.
  - A third paper book runs it side by side. Defaults stay as today, so nothing changes until it is switched on, and
    the probe's rule decides that.
- **13:09. Release 2, first build reviewed; sent back for a second pass** (branch owner/release-2).
  - With the switches at their defaults every log line except the heartbeat is identical to `main` (parity replay 156
    rungs and 88 parents; live-path simulation 540 minutes, 111 entries, $11,723.34). The heartbeat gains counters.
  - Its new tests pass in the owner's own run.
  - Asked for before the merge: monitoring code that cannot stop a step; a rate-limit answer stops the trades pass
    for that minute; a per-coin list; the third paper book in its own job; a hand-over between paper runs.
- **13:10. Seen in release 2's runner check: the venue cuts many candles after the minute** (run 42865444628, 18 coins,
  30 minutes each, 17:29 to 17:59 UTC).
  - A bar built from the public trades matched the final candle in every minute for BTC, ETH, SOL, XRP, LTC and ZEC,
    and in 30% to 90% of minutes for the other twelve (77% of all 540 coin-minutes).
  - Where they differed, volume had moved between two adjacent minutes with the total unchanged: the final candle of
    a minute held trades stamped in the first seconds of the next. Signal lab 2 saw the same in history.
  - The candle the bot would have read about 6 s after the minute matched the final candle in 42% of coin-minutes and
    was absent in 8%. BTC's was absent in 27% and matched in none.
- **13:30. Candle clock study planned before its data and started** (candle_clock_prereg.md).
- **13:35. The paper books have run in real time only part of the time.** GitHub drops scheduled runs. From the first
  run to Nov 10 18:30 UTC the spot books ran 66.4 of 92.0 hours (72%); since Nov 8 12:25 UTC, 29.2 of 54.1 hours
  (54%). In a gap the bot places no new bids, and at the next start it only settles what was open.
  - Fills and fees per calendar day therefore understate the rate while the bot runs.
  - **Correction to the fee pace in the charter.** The $1,900 to $2,200 a month was measured over 3.6 calendar days
    in which the books ran about 76% of the time. At a full-time pace it is about $2,500 to $2,900 a month, which
    puts the Premium tier at about +$340 to +$420 a month net instead of +$190 to +$250. Still a few days of data.
  - Release 2 adds a hand-over, so each paper run starts the next.
- **13:36. Candle probe result** (run 42853095116, 125 minutes, nine coins; reports/owner/candle_probe/README.md).
  - **By the rule: no source is usable at 25 s or less.** Trades bar 6.8%, 6.4% and 6.0% material error at 1, 3 and
    6 s; best candles 5.2% (Advanced, 6 s) and 5.8% (Exchange, 3 s and 10 s). The bar was 1%.
  - **The trades are not late.** At 6 s the trades bar had no material error for BTC, ETH, SOL, XRP or ZEC (few
    counted minutes for the first four). The errors sit in PEPE, ONDO and DOGE, with one HYPE minute: trades near
    the minute boundary and one-tick differences.
  - **The bot's own BTC address returned an old cached copy in 125 of 125 minutes,** always without the minute asked
    for and one to two minutes behind. ETH: a copy in 79% of minutes. The other seven coins: the minute missing in at
    most 2.4%. Some copies hold a minute still in progress, which none of our own requests ask for, so other clients
    made them. Who they are is not known.
  - **On answers that were not copies, the venue's candle is final by about 25 s** (material error 4.3% at 10 s, 1.2%
    at 15 s, 0.0% at 25 s and 40 s).
  - **What that means for the bot as it runs today.** Its last look at a minute is 126 s after the minute closes. If
    that answer is a copy older than about 100 s, the row stays partial or missing, and a missing close is filled
    forward for up to 30 minutes. So BTC's table, which every bid level reads, can be wrong well beyond the newest row.
    What this has cost is not measured.
- **13:48. Deviation logged in the probe's plan.** The rule's third branch (specify a live trade feed) is not followed:
  a live feed carries the same trades, so it would not close the gap the probe found. The stale-copy fault is outside
  the rule and is fixed in release 2, as the 11:04 entry committed.
- **13:50. Candle clock result** (six hours, 18 coins; reports/owner/candle_clock/README.md).
  - **No coin has a steady offset.** BTC, ETH, SOL and XRP are cut at the minute, and LTC and ZEC nearly so (a late
    boundary in about 5% of minutes): for all six the trades bar's material-error share against the final candle
    was 0 to 0.6% in the last three hours.
  - **The other twelve run late in 8% to 41% of boundaries,** by a median of 7 to 11 s, mostly after quiet minutes
    (about 54% after a minute with 5 trades or fewer, about 2% to 3% after more than 50). No offset fixes that.
  - **About 5% of minutes, the same ones for nearly every coin, have a final candle that leaves out trades** listed in
    the public trades (BTC 14:05 UTC: about 3.4 in the candle, 13.4 in the trades). The trades list has no gaps.
  - The study's per-minute match flags joined with the collector's first-seen candles, 16:06 to 17:52 UTC: for the six, the trades bar matched the final candle in 97% or
    more of minutes at every level of activity, and the first-seen candle in about 70% of busy minutes. For the
    twelve, the first-seen candle matched the final candle exactly a little more often than the trades bar (82%
    against 74% of minutes), and the two were about even on material errors.
- **13:52. Decisions.**
  - **Release 2's new mode ("verified inputs"):** the six coins take their newest bar from trades, and a trades row is
    never replaced by a candle row. The twelve stay on candles, read with the answer's age checked; an older answer
    never replaces a newer row; recent rows are looked at again for six minutes instead of three. With the guard on,
    no new bid is placed on an input the bot knows to be old.
  - **Defaults do not change.** A third paper book runs the new mode. The rule for making it the default (three clean
    days, six conditions, no P&L test) is in FORWARD_TESTS.md, fixed before that book's first run.
  - **Scorecard re-scored: 47 of 100.** The block "the live bot matches the research" goes from 9 back to 6: timing is
    verified, inputs are verified faulty, and the fix is not on yet.
  - **Advice to Miles: hold the pilot until the new mode is the default.** A pilot now would trade on the late BTC
    input.
- **13:57. Late-BTC replay planned and started** (late_btc_prereg.md, branch owner/late-btc). It replays the research
  with BTC one and two minutes late at every decision, models not retrained, fills on true prices. It prices the
  fault; nothing is chosen with it.
- **13:58. Collector: a trades-bar stream and a daily input check ordered.** They give the collector's own daily record
  of the trades bar against the final candle, which the three-day rule (item 6) and the candle clock plan require.
- **Known and not fixed in release 2: the perp paper bots.** They fetch each spot minute once and never look again
  (bot/engine.py), so their inputs are first-seen candles, BTC included. Their forward test is lower priority; the
  spot bot's data handling can be carried over later.
- **14:08. Correction to the 13:35 entry, from the paper logs themselves.** The status report now derives running time
  from each book's own log. The main spot book was live 60.5 of the 87.0 hours to its last event (69.5%), not the
  66.4 hours of the GitHub run history: the run of Nov 7 06:33 to 12:22 UTC finished but its log never reached
  `main`, so its events are missing.
  - The fee pace follows the log. At a full-time pace it is about $2,800 to $3,200 a month at $250K, and the Premium
    tier about +$400 to +$490 a month net (the 13:35 entry said $2,500 to $2,900 and +$340 to +$420).
  - **Rung fills per running day are above rule A's band:** 21 rungs in 60.5 live hours is 8.3 a day against 1 to 6.
    Either the market was active or the late BTC input added fills. The replay and the third paper book will tell.
- **14:08. Paper status report extended** (main 7c76d7a): running time per book, every rate per calendar day and per
  running day, the new data counters, and the third book's progress on its three-day rule.
- **14:08. Paper book against the research: reconciliation planned and started** (paper_reconcile_plan.md, branch
  owner/reconcile). For every minute the main paper book was live, the bid level and score it would have computed
  from final candles are set against the bids and fills in its log. It shows how far the late inputs moved the
  bot's decisions on real forward data, and whether they explain the extra fills.
- **14:31. Collector: trades-bar stream and daily input check on `main`** (e81a9b1). Every minute, for all 18 coins,
  the bar of the minute that just closed is built from the public trades list with the bot's proof of completeness.
  A 25-minute test run gave 450 rows, all verified. The production collector picks it up at its next hand-over
  (about 21:44 UTC). Storage rises to about 7.5 MB a day for all streams.
- **14:41. Reconciliation result: the paper book against the research on final candles** (main 7fd3195;
  reports/owner/reconcile/README.md). 59.4 live hours, 787 new first bids, 13 first-bid fills.
  - **The bot's bid levels carry a late BTC.** Median error 0 bp; 5th and 95th percentiles about -23 and +13 bp; 40%
    of bids more than 5 bp off and 10% more than 20 bp. Beta times BTC's last-minute return explains it (correlation
    0.94, slope 0.98). The bot's price equals the one-minute-late price for 37% of bids, the two-minute-late price
    for 18%, the final price for 26%, and none of these for 19%.
  - **When BTC moves, the error is large.** In the third of bids with the largest last-minute BTC move, 83% are
    more than 5 bp off and 27% more than 20 bp.
  - **Scores.** For 19% of the bot's bids the research score is at or below the threshold; a late BTC accounts for
    three quarters of those.
  - **Bids in common:** 67% of the bot's new bids have a research bid within a minute; 77% the other way.
  - **Fills:** 11 in common, 2 only in the bot, 5 only in the research (all in the Nov 8 21:55 UTC drop; three of
    them blocked for cash in the bot).
  - **What it cost in the one market-wide drop.** At 21:55 on Nov 8 the bot's seven fills in common were bought 36 to
    59 bp above the research price (47 bp on $62,191, about $290). Those rungs earned $443; the book has made about
    $1,540 in all. Three more fills came three to four minutes late.
  - **The high fill count was the market.** The research would have had 16 first-bid fills in the same minutes.
  - Limits: one book, 60 hours, 13 fills; the research side is the bot's own code on final candles, not the full
    backtest.
- **15:06. Late-BTC replay result** (main 1dc5617; reports/owner/late_btc/README.md). The research replayed with
  BTC late at every decision, models not retrained, fills on true prices.
  - The true-BTC run reproduces R2-08's best estimate exactly (2.94 / 2.66 / 1.91, the same trades at the same
    prices), and 600 decision minutes agree with the bot's own computation.
  - **With BTC late as the probe saw it** (one minute in 70% of minutes, two in 30%; five seeds): Sharpe 2.41 / 2.86 /
    1.21 for selection / check / 2022-23. About -0.5, +0.2 and -0.7. Yearly return 19.7% / 19.4% / 9.3% against
    22.8% / 19.1% / 11.1%.
  - Always one minute late: -0.44 / +0.24 / -1.04. The mix plus wrong older rows: -0.92 / +0.32 / -0.97.
  - **The loss sits on crash days:** in 2022-23 five days carry about 70% of it (Nov 8 2022 alone about -1.8%); in
    selection Oct 10 2025 is the largest. The worst day in 2022-23 goes from -2.1% to about -4.0% when BTC is one
    minute late.
  - **The paired daily test is weak:** most 90% intervals include zero. Read the cost as likely, and between nothing
    and about one Sharpe point.
  - **Reading.** This is larger than anything the three search rounds found (+0.03 to +0.18 Sharpe). The largest
    lever on realised Sharpe so far is making the live inputs equal the research inputs. It agrees with the paper
    book's own log (the Nov 8 drop).
- **16:36. Release 2 on `main`** (4471a4f; reports/owner/RELEASES.md). Review of the finished build found three things,
  fixed before the merge: the repair of a missed minute was wired only to the test market, not the live one; the
  rule that an older answer never replaces a newer row covered only the six coins on trades and now covers all 18;
  one decorator.
  - Checked by the owner on the final code: the unit tests, the live-path simulation (540 minutes, 111 entries,
    $11,723.34) and the parity replay (156 rungs, 88 parents, every rung identical).
  - On a GitHub runner the new mode had its data ready at a median of 9.8 s after the minute (12.0 s at the latest),
    with 48 of 48 bars built from trades and no fallback.
  - The main and W2 paper books had resumed at 19:57 UTC on GitHub's late schedule. The next paper run is queued
    behind that one; it starts all three books with the hand-over at about 01:50 UTC on Nov 11.
  - Nothing changes for the main book, W2 or a live bot until release 3.
- **16:49. Corrections after an independent fact-check of the afternoon's documents** (about 140 claims checked
  against their sources: none wrong, ten imprecise; fixed in place, listed here).
  - The probe's "no material error for BTC, ETH, SOL, XRP or ZEC" holds for the trades bar at 6 s. At 1 s ZEC had
    1.7%, and HYPE had one such minute too.
  - LTC and ZEC are not cut at the minute every time: about 5% of their boundaries run late. They are on the trades
    list because their material-error share is 1% or less.
  - The late-cut shares by activity (54% and 2%) were computed over 14 coins; for the twelve alone the second figure
    is about 3%.
  - Fee rebate arithmetic: at $1,900 to $2,200 a month in fees the Premium tier nets about +$175 to +$250, and at
    $2,800 to $3,200 about +$400 to +$500 (the entries above say +$190 to +$250 and +$400 to +$490).
  - Idle cash: with the paper book's mean free cash (45.5%), 3.50% on free cash only is about +1.6 points a year,
    not +1.5.
  - "About 99% of armed coin-minutes stay armed" in the replay holds for the selection and check eras; in 2022-23 it
    is 93% to 96%.
  - The 13:10 entry had held the 13:30 plan; it is now its own entry. The perp books have two fills each by now, not
    one.
  - "Other clients made the old copies" is the probe's best account, not a proven fact; the documents now say so.
- **16:50. Collector: first hand-over worked.** The first run ended cleanly at its planned time (21:49 UTC; no errors
  and nothing refused in the four status files read during its 5 h 45 min) and had started its successor at 21:44
  UTC. The successor runs the code now on
  `main`, with the age of each candle answer and the trades-bar stream. None of the hourly schedule runs fired during
  the first run, so the hand-over chain is what keeps collection going; the schedule is a weak backstop.
- **16:51. Owner's checks scheduled:** Nov 10 21:10 ET (first run of the third book and of the two new workflow
  jobs), Nov 11 08:30 ET (the hand-over chain, the data counters of all three books, the collector's new streams),
  Nov 14 09:00 ET (the three-day read of the third book, if it has its 4,000 minutes).
- **17:02. Hand-over verified on the data** (the 16:56 check). The status file names the successor (run 42907961929,
  planned end 03:29 UTC), with no errors and nothing refused. Book, candles, Hyperliquid and the perp list have no
  gap from 16:05 to 21:59 UTC across the two runs. The new streams are writing: the trades bar from 21:44 (288 rows
  in 16 minutes, all verified, one page each) and the age of candle answers from 21:45. In those first 15 minutes
  BTC's candle answer was a cached copy in 87% of minutes (median age about a minute) and lacked the minute just
  closed in 60%. One scheduled run did fire at 21:50 and stood down correctly because a collector was running.
- **21:14. The 21:10 check: the third paper book is running.** The paper run that started at 01:47 UTC (Nov 11) has
  both jobs in progress, the two registered books in one and the third book in its own; no step failed at start-up.
  Its log is committed when the run ends (about 07:35 UTC), so its counters are read in the morning check.
  - **Collector, second run:** healthy (one timeout on a book request, nothing refused). The trades-bar stream has
    every minute since 21:44 UTC, 18 rows each, all verified.
  - **First daily table from the collector** (4.3 quiet evening hours, 21:44 to 02:00 UTC; trades bar against final
    candle, material-error share): BTC 0% to 0.9%, ETH 0%, SOL 0%, XRP 0% to 0.9%, LTC 1.5% to 1.7%, ZEC 1.7% to
    5.2%. Their first-seen candles: BTC about 70%, ETH, SOL and XRP 16% to 29%, LTC and ZEC 18% to 24%. For each of
    the twelve coins on the candle path the trades bar was also lower than the first-seen candle (4% to 42% against
    19% to 47%).
  - **Item 6 of the third book's rule amended** (FORWARD_TESTS.md, note below the table): BTC keeps the 1% bar; every
    other listed coin must beat its own first-seen candle on every day. As first written it would have sent LTC and
    ZEC back to a worse source. Logged as a change made after 4.3 hours of the collector's record were seen.
  - **Two things registered for later:** a rule for moving any of the twelve onto the trades list after the three-day
    read, and a planned replay of what the candle's late cut gives the research on thin coins.
- **21:23. Corrections to the 21:14 entry, after re-reading the table and the candle clock plan.**
  - The entry was written at 21:14, not 21:15. The record seen was 4.3 hours, of which about ten minutes fall inside
    the third book's days. LTC's share is 1.5% to 1.7%.
  - **Item 6, second part, now asks both of the probe's measures.** For every listed coin other than BTC the trades
    bar must be materially off less often and exactly equal more often than the coin's own first-seen candle, on every
    day. On the 4.3 hours seen all five meet both (exactly equal: 82% to 98% against 48% to 73%).
  - **A day is now defined:** a UTC date with at least 12 hours inside the test period and at least 720 compared
    minutes for the coin. At least two such days are needed.
  - **Deviation entered in the candle clock plan.** That plan asks class B's 1% on the collector's daily record. LTC
    and ZEC miss it on this record and stay on the trades list, because their candle answer is the worse source on
    both measures.
  - **The 21:14 rule for moving the twelve onto the trades list is withdrawn.** It decided on the material-error
    share alone, against the candle clock plan's rule that class C coins stay on the candle answer. The same table
    shows the two measures disagree for them: the trades bar is materially off less often for all twelve and exactly
    equal to the final candle less often for nine. In its place: the twelve stay on candles unless a comparison of
    the bot's own decisions under each source says otherwise, under a plan written before the record is read for it.
  - The status report's line for item 6 still shows the first wording. The fix goes to an agent, with a small
    script that applies item 6 to the collector's daily table exactly as written.
- **21:29. The third book's rule gets a seventh item, and item 6 is now code.**
  - **Item 7 (added; FORWARD_TESTS.md, second note):** on the reconciliation of both books over the same minutes, the
    third book's new bids must be closer to the research than the main book's on level error (share beyond 5 bp) and
    on score (share on the other side of the threshold), or both books below 5%. The rule had tested inputs only;
    this tests decisions. Added about 40 minutes into the run, before either book's log for these days was read. It
    can only make the rule harder to pass.
  - **The repeat of the reconciliation is planned** (paper_reconcile_plan.md): both books, the minutes both were
    live, the same four measures, split into the five traded coins on the trades list and the twelve on candles,
    with what a working fix should show written down first. The scripts still read only the main book and the first
    period; generalising them is the next agent job, due before the read.
  - **Item 6 as a script** (scripts/owner/tb_rule6.py, built by an agent on branch owner/rule6, reviewed here): it
    applies item 6 to the collector's daily table exactly as written, with integer arithmetic for BTC's 1%. 50 checks
    pass, and five of my own cases gave the expected verdicts. On tonight's table every coin is "wait", as it should
    be with two hours a day. It goes onto `main` together with the status report's lines for items 6 and 7.
- **21:34. Item 6 script and status lines on `main`; the two-book reconciliation is being built.**
  - **Merged at 21:31:** scripts/owner/tb_rule6.py with its 50 checks, and the status report's lines for items 6 and
    7 (107 checks). No trading code is touched.
  - **An agent is generalising the reconciliation** to any book and period, with the two-book read and item 7 as
    code (branch owner/reconcile-2). Its gate: with default arguments the comparison must reproduce the first
    reconciliation's files byte for byte. Its two runner jobs use only minutes before the test period.
  - **Interim looks** (written into the plan before any look): the pipeline may be run on part of the test period, to
    prove it works and to catch a fault early. A look can stop the test for a fault. It cannot pass the test and it
    changes no rule.
- **22:02. The reconciliation works for any book and period, and item 7 is code.**
  - **Built by an agent, reviewed, merged at 22:01** (scripts/owner/reconcile). With default arguments it reproduces
    all 14 files of the first reconciliation byte for byte; that is now a test. Item 7 run on the first
    reconciliation's bids returns its published figures: 316 of 787 beyond 5 bp, 153 of 787 on the other side of the
    threshold. The research fetch now refuses to run until its newest minute is an hour old, as the plan asks.
  - **Runner job A (42947679530): the research side for Nov 6 to 10, fetched and computed again** about seven hours
    after the first time. All 61,710 rows are identical. Whatever the venue's final candles left out on those days,
    they did not change in seven hours.
  - **Runner job B (42949193615), a development run on minutes before the test:** the main book from Nov 10 19:58 to
    Nov 11 01:40 UTC, 338 decision minutes, 54 new bids, no fills.
    - Beyond 5 bp from the research level: 18.5% (40% on Nov 6 to 10). Score on the other side: 11.1% (19%). Bids in
      common: 80% of the bot's, 98% of the research's.
    - It was a quiet evening, so a late BTC moved the level less. The relation is still there (correlation 0.70).
    - 19 of the 54 prices match none of final, one-minute-late or two-minute-late BTC (35%; it was 19%). The errors
      are small. Their cause is not tested.
  - **Bids come at about 10 to 13 an hour,** so item 7's 200 bids in each book need about a day of both books.
  - **How a look or the read is run** is now in paper_reconcile_plan.md. The first interim look is due after the
    third book's first log is on `main` (its first run ends at about 07:35 UTC).

## Nov 11 2026 (times ET; UTC is five hours later)

- **08:45. Morning check after the first night of release 2.**
  - **Hand-over: works.** The run that began at 01:47 UTC ended at 07:37 and its hand-over job started the next one
    at once; that one ended at 13:28 and started the third. The collector's chain also held (three runs, no gap).
  - **Fault: the main book and W2 lost their log for 01:47 to 07:37 UTC.**
    - Cause, from the run's log: the two paper jobs ended two seconds apart and pushed to `main` in the same second.
      The main job's push was rejected. The retry line then ran `git rebase --abort` with no rebase in progress,
      which fails, and under `bash -e` that ended the step on the first try. The runner was discarded with the log.
    - Effect: both books went on at 07:37 from the 01:47 state (a 350-minute gap). The third book's log is whole.
    - Fix (agent, reviewed, on `main` at 13:42 UTC): bot/spot/deploy/paper_commit.sh replaces the inline loop in
      paper-spot.yml (both jobs), owner-status.yml and paper.yml. Six attempts, every failure retried, and a rescue
      branch if all fail. Its test reproduces last night's git error and shows the old line failing on it (24
      checks). No trading code is touched.
    - The run in progress (began 13:28 UTC, ends about 19:18) still has the old step. When both jobs end in the
      same minute the same loss can happen once more. I tried to cancel it and start a fresh run on the fixed step;
      the session's permission check refused the cancel, so it runs on. Reported to Miles.
    - An agent's audit of the other workflows: the daily data jobs have no retry but fail visibly and can be
      fetched again; several research jobs pass silently if every push fails. None is changed today.
  - **What the books' new counters say (PAPER_STATUS.md):**
    - Main book, 07:43 to 13:00 UTC: no BTC row for the minute just closed in 279 of about 320 minutes, nearly
      nine in ten. The late BTC input is the normal state on the paper runners, as the probe found on its own
      runner.
    - Third book, 01:52 to 13:00 UTC: BTC never stale; 3,960 trades bars built in 660 steps, six every step, no
      fallback of any kind; 19 coin-minutes skipped for an old candle answer; no error event; data step median
      10.2 s, one half hour with a maximum above 20 s (23.9 s).
  - **The status report understated item 1 (98.07%).** It divided verified bars by minutes run times six, and
    minutes run counts about 13 minutes around the two start-ups that had no step. The engine counts every attempted
    coin-minute in exactly one of six counters, so the share is now verified over attempted: 3,960 of 3,960. This
    corrects the measurement, not the rule, and it was made after the 98.07% was seen; the evidence is that every
    full half hour shows 180 bars for 30 steps. Fixed by an agent, reviewed, on `main` at 13:42 UTC (114 checks).
  - **A subagent's first command was refused by the session's permission check** (it tried to create a branch that
    already existed). It stopped and asked me to do it or approve it. I did neither; the step was not needed, and it
    went on with edits only.
  - **Collector's table for Nov 11, 00:00 to 13:00 UTC** (trades bar against final candle; materially off / exactly
    equal; first-seen candle in brackets):
    - BTC 0.0% / 99.4% (62% / 26%); ETH 0.4% / 98.7% (13% / 67%); SOL 0.7% / 96.9% (28% / 66%); XRP 1.5% / 92.9%
      (11% / 80%); ZEC 1.8% / 94.4% (12% / 82%).
    - LTC 5.5% / 78.9% (9.7% / 81.3%): its trades bar is exactly equal less often than its candle, so on this
      partial day it fails item 6(b) on that measure. If the full days say the same, LTC leaves the list at
      release 3, as the rule provides.
    - The twelve: the trades bar is materially off more often than the candle for AAVE, BCH, ENA and PEPE, level
      for HBAR, and less often for the other seven. The candle is exactly equal more often for all twelve. Last
      night's 4.3 hours had the trades bar ahead on the first measure for all twelve; the rule written on that and
      withdrawn would have moved them wrongly.
  - **Interim look 1 at the reconciliation** (01:47 to 12:30 UTC; reports/owner/reconcile_tb/i1/README.md):
    - Third book, 102 new bids: every one within a tick of the research level. Main book, 36 bids: 5 more than
      5 bp off, following BTC's last-minute move.
    - Third book's research score on the other side of the threshold: 8 of 102, all on candle-path coins, 7 of
      them between 02:06 and 07:18 UTC. None on the five traded coins of the trades list.
    - Item 7 on the 288 common minutes: (a) 5 of 36 against 0 of 17; (b) 1 of 36 against 1 of 17. It waits for 200
      bids in each book.
    - No fault found, so the test runs on. Item 7(b) may come out close on quiet days, because the remaining score
      error sits in coins both books read the same way. The rule is not changed.
- **08:50. Plan for the twelve candle-path coins fixed (bar_source_prereg.md).**
  - **Why now:** the interim look shows what is left after the BTC fix. It is the score of the twelve coins read from
    candles (8 of 87 bids on the wrong side), and input shares cannot say which source would do better.
  - **Three ways compared:** candles as today; a trades bar that is kept; a trades bar replaced by the final candle
    afterwards (the engine cannot do the third yet).
  - **Part 1, offline:** the bot's own score and level under each way at every minute of Nov 11 02:00 to Nov 14 02:00
    UTC, against the research, from the collector's record. The tool is built on earlier minutes only.
  - **Part 2, forward:** a fourth paper book with all 18 coins on trades, in its own workflow, read against the third
    book after three full days and 300 bids on the twelve in each.
  - **Rule:** in FORWARD_TESTS.md. Nothing at decision level had been computed with a trades bar for the twelve when
    it was written.
  - Two agents get the work: one the offline tool, one the fourth book's configuration and workflow.
- **08:56. The perp paper books lost a log too, by a different fault; fixed.**
  - **What happened:** the perp run of 04:35 to 10:23 UTC (Nov 11) never reached `main`, and its step reported
    success. It was a scheduled run that had waited behind the previous one. Its checkout took the commit of its
    trigger time, older than the log the previous run committed at 04:34, so it ran six hours from stale state. At
    the end the rebase hit conflicts on its own four files, the old loop left them in place, every retry failed, and
    the step passed. The status report showed both perp books stale for 9 hours.
  - **Why it mattered today:** the commit script merged at 13:42 resolves such a conflict in favour of the run that
    is pushing. For a stale run that would have replaced the previous run's events and state on `main`.
  - **Fix (agent, reviewed, on `main` at 13:56 UTC):** paper.yml checks out the tip of `main`, as paper-spot.yml
    has since Nov 7. It was merged before that workflow's next scheduled start (nominally 18:03 UTC), because a
    queued run uses the workflow file of its trigger time.
  - **The new commit step ran on a real runner** for the first time (status refresh, 13:53 UTC): pushed on the first
    attempt.
  - **Left open:** the commit script can still drop another commit's lines if something else writes a book's folder
    during a run (a hand edit, or a rescue branch merged meanwhile). An agent suggests sending such a case to the
    rescue branch instead. Not built. data.yml also waits in a group without taking the tip; its data can be
    fetched again.
  - **The perp books' running time (about 62%) is partly this fault,** not only dropped schedules: every scheduled
    run that waited behind another lost its log. They also have no hand-over yet.
- **09:17. The offline tool is built; its development run changes the plan for the twelve.**
  - **Tool** (agent, reviewed; scripts/owner/bar_source): it drives the bot's own code under each way of filling a
    coin's rows. 46 checks pass, and its research pass is identical to the reconciliation's on 3,927 shared rows.
    Runner job 43034926403 covered 250 minutes before the registered window.
  - **Finding 1: keeping trades rows puts the bid level off.** For the twelve, 9.4% of coin-minutes were more than
    5 bp from the research level (4 of 3,000 under the other two ways). The level rests on the close an hour back;
    a trades bar's close is not the final candle's wherever the candle ran late. ZEC, kept on trades in the third
    book, shows 5.2%.
  - **Finding 2: a coin's score reads the other coins.** Two model inputs are built across all coins, so every way
    has to be computed as a whole book.
  - **Finding 3: the emulation of today's candle path shows almost no score error** (90th percentile 0.1 point),
    while the third book showed large ones at its bids. The registered check against the book's own log will say
    which is right.
  - **Plan amended** (bar_source_prereg.md, deviation log), before any registered minute was read: the fourth book
    will run "trades for the newest minute, the venue's candle afterwards" for all 18 coins, from a branch that
    carries the engine option. Keeping trades rows is dropped as a candidate. The one-fifth margin for building the
    option is dropped, since it is built now for the forward test. The single-coin clause moves to a measure with
    enough events.
  - **What this says about release 2's own rule:** a candle row never replaces a trades-built row. For matching the
    research that is the wrong way round for a coin whose candles run late. It costs little for BTC, ETH, SOL and
    XRP. The third book's test is read as registered; the new way is the candidate for the release after it.
- **11:13. The engine option for the fourth book is built and proven on the real market; not on `main`.**
  - **What it does** (branch owner/engine-c, commit 58eba8b, key `trades_rows: "candle_after"`): the decision for a
    minute uses its trades bar. One step later the venue's candle replaces that row, or the row is dropped where the
    venue has no bar. So the older rows are the venue's candles, as in the research.
  - **Default untouched:** 36 lines in the engine. With the key absent the stored replay gives the same 530 events in
    three modes, and every existing spot test passes on a runner (21, 37, 11, 73 and the replay and live-path tests),
    plus 30 new checks. I read the diff and reran the tests that need no data.
  - **Smoke on the real market (45 minutes, 18 coins):** every row the engine held was identical to a fresh fetch of
    the venue's candles, for all 18 coins. All 666 trades bars verified. In 48 of 537 replacements the candle's close
    differed from the trades bar's, which is the late cut showing in the newest minute only.
  - **Step time is the cost:** data step median 13.3 to 13.5 s after the minute, against 10.2 s for the third book.
    Eighteen trade requests in a row take about 3.5 s. Item 3's median bar for the fourth book is set at 15 s before
    its first run, with the reason, in bar_source_prereg.md. A faster data step is a later, separate change.
  - **The fourth book's workflow** (agent, branch owner/paper-t18) runs the code of that branch in a second checkout
    and keeps the book's state and log on `main`. It gets one more change, pinning the engine commit, and is then
    merged and started.
- **11:18. The fourth paper book is running.**
  - Its workflow (paper-spot-t18.yml; agent, reviewed) is on `main` since 16:14 UTC. It checks out engine commit
    58eba8b into a second folder, keeps the book's state and log on `main` in paper_spot_t18, and writes the engine
    commit into paper_spot_t18/CODE at every run. The engine on `main` is unchanged.
  - First run 43056376442 began at 16:15 UTC; both checkouts and the start succeeded, and the paper step is running.
    Its log reaches `main` when the run ends, at about 22:05 UTC.
  - Its read (bar_source_prereg.md, Part 2) is not before Nov 14, 16:20 UTC: three full days beside the third book
    and 300 new bids on the twelve in each.
  - Still to do before the Nov 14 reads: the offline tool's seventh pass and score-miss measure (with an agent), and
    the fourth book in the status report.
- **11:24. Tools for the Nov 14 reads are complete on `main`.**
  - **Offline tool, follow-up** (agent, reviewed): a seventh pass with all 18 coins on the new way, which is what
    the fourth book runs; the score-miss share; the restated single-coin clause, applied only if the emulation check
    passes. The earlier passes are identical row for row. 53 checks pass.
  - **Development window again (decides nothing):** score more than 1.0 point from the research in 51 of 3,000
    coin-minutes for the twelve on candles and 36 on the new way. With all 18 coins on the new way the five listed
    traded coins sit on the research (0 misses in 1,250), and the level is off in 2 of 3,000 for the twelve.
  - **Status report** (agent, reviewed): the fourth book appears once its folder is on `main`, with its comparison
    with the third book and its items 1 to 5 (18 coins, 15 s median bar). Without the folder the report is
    byte-identical. 130 checks pass.
  - **How both reads are run** is written into bar_source_prereg.md.
- **14:37. Afternoon check: the same race cost the main book and W2 a second log.**
  - **What happened:** the paper run that began at 13:28 UTC still had the old commit step. Its two jobs ended one
    second apart at 19:18 UTC, the main job's push was rejected ("cannot lock ref"), and the faulty line ended the
    step. The main book and W2 lost 13:28 to 19:18 UTC. Together with the morning that is 11.7 of today's hours.
    The third book's log is whole both times.
  - **My estimate was wrong.** I gave Miles "roughly one in four" for this run. The two jobs start together and run
    the same number of minutes, so they end in the same second nearly every time. It has now happened in two of three
    runs. I could not cancel the run this morning (the session's permission check refused it).
  - **From here on the fixed step is in place:** the run that began at 19:18 UTC (43085951611) has it. It has
    already pushed on the first attempt three times on real runners (the status refreshes at 13:53, 19:17 and 19:37
    UTC).
  - **Perp books:** the run that ended at 19:17 UTC pushed its log. The next scheduled run will be the first on the
    fixed workflow (it now starts from the tip of `main`).
  - **Third book** (17.5 hours, 99.8% of the time, 1,049 of its 4,000 minutes): all five items the report computes
    hold. 5,928 of 5,928 trades bars verified; no refusal; data step median 10.4 s, one half hour of 34 above 20 s;
    no error; no unconfirmed rows. 62 coin-minutes skipped for an old candle answer.
  - **Item 7 gets its minutes later than planned:** the two books have only 07:43 to 13:26 UTC in common so far,
    about 47 bids in the main book. At about 8 bids an hour the 200 bids need another day, well before the read.
  - **Fourth book:** running since 16:15 UTC on engine commit 58eba8b; its first log is due at about 22:05 UTC.
- **14:40. The perp paper workflow hands over too.**
  - An agent added the same hand-over job the spot workflows have (reviewed, on `main` at 19:39 UTC). The schedule
    stays as the backstop.
  - No perp run was under way, so I started one (43089287826, 19:39 UTC) rather than wait for the schedule. It is
    the first perp run that starts from the tip of `main`, commits through the new step and starts its successor.
  - With that, all four paper workflows chain their runs and none can lose a log to a rejected push or to an old
    starting point without failing visibly.

## Nov 12 2026 (times ET; UTC is five hours later)

- **08:54. Morning check.**
  - **Overnight runs:** every paper run that began after yesterday's fixes pushed its log and started its successor:
    spot at 01:07, 06:58 and 12:49 UTC, perp at 01:30, 07:21 and 13:11 UTC, the fourth book at 04:15 and 10:06 UTC.
    The collector has a trades bar for all 1,440 minutes of Nov 11 for every coin.
  - **The fourth book's first run lost its log, for a new reason.** Run 43056376442 (16:15 to 22:05 UTC on Nov 11)
    ran to its end. Then every push failed with "could not read Username": the runner's token was not accepted for
    more than 76 s, on all six attempts and on the rescue push. The cause is probably on GitHub's side; that is not
    proven. The book began again from nothing with run 43110721127, first step at 22:25 UTC, so its record and its
    three days beside the third book start there.
  - **Commit step hardened** (agent, reviewed; on `main` since 13:44 UTC): retries spread over four minutes, a 45 s
    limit on every remote call, a deadline that leaves time for the rescue branch, and no credential prompt. 38
    checks pass. The runs under way started before it; the first runs with it begin at about 15:57 UTC (fourth
    book), 18:40 UTC (spot) and 19:00 UTC (perp).
  - **Third book at 12:49 UTC** (35.0 hours, 99.9% of the time, 2,097 of its 4,000 minutes): items 1 to 5 hold.
    11,862 of 11,862 trades bars verified; no refusal; data step median 10.0 s, half-hour maximum at most 20 s in
    98.5% of 68 half hours; no error; 9 of 36,414 rows unconfirmed. 234 coin-minutes skipped for an old candle answer.
  - **Fourth book at 12:49 UTC** (695 minutes): 12,113 of 12,114 trades bars verified, one fell back on the request
    budget; data step median 13.6 s, largest 19.4 s; no error. 11,254 trades rows were replaced by the venue's
    candle (2,174 with a different close), 489 dropped where the venue has no bar, 19 of 12,510 still waiting.
  - **Collector, first full day (item 6, provisional):** BTC's trades bar was materially off in 1 of 1,236 compared
    minutes on Nov 11 (0.08%). ETH, SOL, XRP, LTC and ZEC each pass both measures on Nov 11 and on Nov 12 so far.
    LTC is the closest: exactly equal in 84.4% of minutes against 80.8% for its first-seen candle, materially off in
    3.3% against 9.9%. The rule's tool says wait: Nov 12 is not a counted day yet.
  - **Interim look 2 at the two books** (reports/owner/reconcile_tb/i2/README.md; Nov 11 01:47 to Nov 12 12:30
    UTC, 1,361 common minutes). It decides nothing.
    - Bids more than 5 bp from the research level: main book 82 of 229 (35.8%), third book 0 of 159.
    - Bids the research would not have placed: main book 39 of 229 (17.0%), third book 5 of 159 (3.1%).
    - Item 7 waits: the third book has 159 of the 200 bids it needs on the common minutes.
    - On its own minutes the third book has 19 wrong-side bids in 364 (5.2%): 18 of 275 on the twelve candle-path
      coins, 1 of 89 on the five traded coins. Seven fall in one busy hour for which the main book has no log.
  - **New finding: LTC's three level errors are kept trades rows.** The third book keeps a trades-built row for
    good. Its three bids more than 2 bp from the research level are all LTC, and each lines up with the gap between
    LTC's trades close and the venue's candle close 60 minutes earlier (-8.7, -3.7 and +5.0 bp against -8.8, -4.8
    and +4.9 bp on the collector's record). One of them is the only wrong-side bid on a traded coin. This is the
    weakness the development run showed for keeping trades rows, now seen in a live book. The fourth book's way
    replaces the row with the candle. No rule changes: LTC's place on the list is item 6(b)'s to decide, and the
    way of filling rows is the bar-source plan's.
  - **One fill in all three books (Nov 11, 23:20 UTC).** The main book's ENA bid stood 14 bp above the research
    level and filled about $6,000 (+$102); the third and fourth books bid at the research level and filled $51
    (+$0.86 each). The main book also filled an XLM bid the research had not placed (+$4). One event; it shows how
    far the late BTC row moves a bid and nothing about profit.
  - **Fourth book against the third, first numbers** (Nov 11 22:25 to Nov 12 10:00 UTC, 675 common minutes): 59
    and 70 new bids on the twelve; no wrong-side bid and no level error in either; bids in common with the research
    55 of 59 and 66 of 70. Part 2 needs 300 bids on the twelve in each.
  - **Part 2's date moves** (bar_source_prereg.md, deviation log): its three days end at 22:25 UTC on Nov 14, and
    the fourth book's log reaches that minute at about 02:30 UTC on Nov 15. The read is set for the morning of
    Nov 15. The rule is unchanged.
- **12:58. Part 2's rule is code, the reads' periods are fixed, and a five-minute correction.**
  - **Rule as code** (agent, reviewed; `main` 45813d8): scripts/owner/bar_source/part2_rule.py applies Part 2's
    rule to the two-book tables of the third and fourth books. 63 checks pass. On this morning's interim tables it
    says wait, as it must (59 and 70 bids on the twelve, 696 minutes).
  - **Correction to this morning's entry:** the fourth book's first step was at 22:30 UTC on Nov 11, not 22:25,
    which is the start of its download. Part 2's three days are 22:30 UTC on Nov 11 to 22:29 UTC on Nov 14. The
    plan's deviation log has it.
  - **Third book's read, period fixed now:** it ends with the decision minute 01:52 UTC on Nov 14, three full
    days after the book's first decisions (paper_reconcile_plan.md, step 5). My scheduled note for that read names 01:51 as the last
    minute; the plan file governs.
  - **Status at 16:00 UTC:** the fourth book's run that began at 10:06 UTC pushed its log, and the next run is the
    first with the hardened commit step. Fourth book: 1,025 minutes, 17,873 of 17,874 trades bars verified, data
    step median 13.5 s, no half hour above 20 s, no unconfirmed row. The third book's next log is due at about
    18:40 UTC.
  - **Schedule:** third book's read Nov 14, 09:00 ET; Part 1 after it; Part 2 moved to Nov 15, 08:40 ET; a morning
    check on Nov 13.

## Nov 13 2026 (times ET; UTC is five hours later)

- **08:46. Morning check.**
  - **Runs:** every paper run since 12:49 UTC on Nov 12 ended in success, pushed its log and started its
    successor: spot at 18:38, 00:29, 06:19 and 12:10 UTC, perp at 19:02, 00:52, 06:44 and 12:34 UTC, the fourth
    book at 15:57, 21:48, 03:39 and 09:28 UTC. The runs that began after 13:44 UTC on Nov 12 used the hardened
    commit step; no rescue branch exists. The collector's record is current and nothing was refused.
  - **Third book at 12:10 UTC:** 3,489 of its 4,000 minutes (58.1 of 58.2 hours). Items 1 to 5 hold: 19,806 of
    19,806 trades bars verified; no refusal; data step median 10.2 s, at or under 20 s in 99.1% of 114 half hours;
    no error; 14 of 61,218 rows unconfirmed.
  - **The venue serves more old candle answers today.** The third book skipped 316 coin-minutes of the twelve for
    an old answer in the first 12 hours of Nov 13, against 190 in all of Nov 12. The main book had no BTC row for
    the minute just closed in 637 of 720 minutes (88%). The fourth book reads no newest bar from candles and skips
    nothing for this.
  - **Fourth book at 09:00 UTC:** 2,075 minutes without a gap. 35,621 of 35,622 trades bars verified; data step
    median 13.5 s (12.1 s today), at or under 20 s in 98.6% of 69 half hours (largest 20.2 s); no error; no
    unconfirmed row. 33,932 trades rows replaced by the venue's candle (5,368 with a different close), 988 dropped,
    61 of 36,810 still waiting. Its code record names commit 58eba8b.
  - **A fault in the status report, fixed** (agent, reviewed; `main` 96d1834). The report said the fourth book's
    running time could not be derived. Cause: a hand-over whose start-up ran over a half-hour mark leaves one
    heartbeat out, and the report treated two heartbeats an hour apart as a possible gap for a book with no
    logged gap. It now accepts such a pair when a start lies between them. The book itself had no fault. 20 new
    checks; the other books' numbers are unchanged.
  - **Item 6, provisional, two counted days** (Nov 11 and 12): BTC's trades bar materially off in 1 of 2,178
    compared minutes (0.05%). ETH, SOL, XRP, LTC and ZEC pass both measures on both days. LTC is the closest: on
    Nov 12 exactly equal in 87.7% of minutes against 87.0% for its first-seen candle, materially off in 1.95%
    against 5.58%. For BTC the collector has a final candle to compare in 1,236 and 942 of 1,440 minutes.
  - **Bid counts, from the logs alone.** Item 7's pair through 12:00 UTC: 418 new bids in the main book and 315
    in the third on 2,746 common minutes, so item 7 has the 200 it needs. Part 2's pair through 09:00 UTC: 158 and
    159 new bids on the twelve on 2,008 common minutes, against 300 needed by 22:29 UTC on Nov 14. That is close,
    so the plan now says what happens if they are short: the period's end moves in six-hour steps
    (bar_source_prereg.md, deviation log).
  - **No reconciliation was run** and no outcome was read. The reads stay as scheduled: third book Nov 14, 09:00
    ET; Part 1 after it; Part 2 Nov 15, 08:40 ET.
- **08:48. Test A's count at release 3, fixed before the read.** If release 3 ships, test A's three weeks and 60
  rungs start again with the main book's first run on the new inputs; the record made on the late BTC input is kept
  and reported apart. It is a favourable record (35 rungs, 76 bp net per dollar), so the choice is not made to hide
  a bad one. The W2 comparison continues, since both books switch together. Registry: FORWARD_TESTS.md, the note
  under the first table.
- **12:49. Release 3 is built as a candidate on a branch. Nothing is merged; it ships only if tomorrow's read
  passes, with the coin list the read decides.**
  - **A fault found before it could bite: the live bot would not have received the new inputs.** The VM runs from
    `bot/spot/config.live.json`, a copy of `config.json` made when the VM was set up (setup_vm.sh). A release that
    changes `config.json` never reaches it, so `wickctl update` alone would have left the pilot on the late BTC
    input.
  - **Design (mine; built by an agent on branch owner/release-3, commit ec6f19a):**
    - The live file takes its six input settings from `config.json` at every start. Capital, coins, fees and risk
      limits stay as the live file has them, and the file is not rewritten. `wickctl status` prints which inputs
      are in use. `"inputs_local": true` in the live file is an emergency switch back to its own inputs.
    - A `config.json` that cannot be read never stops a command, the kill-switch commands included.
    - A live start without the release's inputs prints a warning and writes a `warning` event, which the watchdog
      sends to the phone.
    - The watchdog sends one alert when the stale guard skipped new bids in three or more minutes within one of
      its five-minute runs, at most every 30 minutes. Before, a failing trades feed would have idled the bot with
      no alert.
    - The main book's and W2's configs get the third book's three keys, as a commit of its own. The list is
      provisional.
    - Replays of history state their own inputs (final candles), so the config change cannot alter them.
  - **Tests run here by the agent, before and after the change:** parity replay 156 rungs and 88 parents on both
    sides; live-path simulation 540 minutes, 111 entries, P&L $11,723.34 (109 entries and $8,421.28 with the
    server death); every event log identical line for line. New: the live-path simulation on the new inputs, with
    a trades feed made from the same candles, equals the candle run line for line (1,487 lines, 2,892 bars from
    trades, no fallback); a switch of modes on a running book kept its 15 open ladders and every entry and exit;
    66 checks on the inputs rule and 31 on the watchdog. I re-ran the light tests and the two new ones: pass.
  - **On GitHub runners, started 17:45 UTC:** the full offline suite (run 43475841318) and a ten-minute paper run
    of the new main-book config on live data (run 43475847326).
  - **A permission refusal, not worked around.** The automatic permission check refused the agent's first commit.
    That commit had changed the attribution line from the one I had instructed. The agent asked me to commit its
    files for it; I declined. It redid the same commit as instructed, once, and that went through.
  - **Found, not changed (engine behaviour; queued for after the Part 2 read, because the third book's code must
    not change before it):**
    - At a start the engine compares balances before it books the fills of the minute before, so a restart during
      fills raises "coin balance differs" warnings (seven in the simulation). Each is a phone alert on the VM.
    - In a minute skipped by the stale guard, first bids already resting stay until they expire (at most 300 s)
      or the next good minute replaces them.
  - **Item 6, a look at an incomplete day:** on Nov 13 so far (13 hours) LTC and ZEC are behind their own
    first-seen candles on both measures (LTC exactly equal 86.2% against 91.9%, materially off 2.45% against
    1.81%; ZEC 87.5% against 92.8%, 2.32% against 2.06%). The candles are better today than on Nov 11 and 12. It
    decides nothing. If the day ends so, the rule takes both off the list at release 3 and the list is BTC, ETH,
    SOL and XRP.
  - **Open for the release note:** the pilot's live log stays on the VM, and I need it to read test B. Two ways
    to put to Miles: a private repository the VM pushes to, or an export he attaches.
  - **Status report:** rule A can be counted from a start time (`main` 1456de4). The start file is added at
    release 3; until then the report is unchanged.
- **14:01. The release 3 candidate passed on GitHub runners.**
  - **Full offline suite** (run 43475841318, 75 minutes, on commit fec476a): no file with a failure. Parity replay
    156 rungs and 88 parents on both sides; live-path simulation 111 entries and $11,723.34, and 109 entries and
    $8,421.28 with the server death; on the new inputs the same numbers, 2,892 bars built from trades, no fallback,
    15 ladders kept across the switch. The watchdog's test joined the list one commit later (ec6f19a); I ran it
    here: 31 checks pass.
  - **Paper run of the new main-book config on live data** (run 43475847326, 17:50 to 18:00 UTC): no error. 54
    bars built from trades in nine minutes (six coins a minute), no fallback, data ready at a median of 9.7 s and
    12.2 s at the latest, 17 new bids. Six coin-minutes on the candle path were skipped for an old answer.
  - **A four-coin variant is being tested as well** (branch owner/release-3-four: BTC, ETH, SOL, XRP), in case
    the read takes LTC and ZEC off the list. Suite run 43488258360, paper run 43488263182.
- **14:44. The four-coin variant passed too.** Branch owner/release-3-four (commit e622b78: BTC, ETH, SOL, XRP).
  - **Full offline suite** (run 43488258360): no file with a failure, the same replay and live-path numbers, 1,928
    bars built from trades on the new inputs, 15 ladders kept across the switch. This run also covers the
    watchdog's test on a runner (31 checks).
  - **Paper run on live data** (run 43488263182, to 19:30 UTC): no error, 28 bars built from trades in seven
    minutes (four coins a minute), no fallback, data ready at a median of 11.4 s and 16.5 s at the latest.
  - **So both lists the read can plausibly give are tested:** six coins (owner/release-3, ec6f19a) and four. A
    list of five lies between them on the same code. Nothing is merged.

## Nov 14 2026 (times ET; UTC is five hours later)

- **09:21. The third paper book's three-day read: all seven items pass. LTC leaves the trades list.** Applied
  once, as written (FORWARD_TESTS.md; record in reports/owner/reconcile_tb/read/README.md).
  - **Runs overnight:** every paper and collector run succeeded, saved its log and started its successor.
  - **Period:** first event 01:47 UTC on Nov 11, last decision minute 01:52 UTC on Nov 14. 4,318 real-time
    minutes against 4,000.
  - **Items 1 to 5,** on the log cut at the period's end: 24,252 of 24,252 trades bars verified; no refusal; data
    step median 10.1 s, at or under 20 s in 99.3% of 140 half hours; no error; 15 of 75,240 rows unconfirmed.
  - **Item 6,** collector's record, three counted days: BTC's trades bar materially off in 6 of 2,938 compared
    minutes (0.20%, limit 1%). ETH, SOL, XRP and ZEC beat their own first-seen candles on both measures on every
    day. LTC did not on Nov 13 (materially off 2.30% against 1.39%; exactly equal 87.1% against 93.6%), so by the
    rule it leaves the list at release 3 and the days do not start again.
  - **ZEC stays, as the rule says, and is the weakest coin on the list.** It passed Nov 13 by a small margin.
    Yesterday's look at the incomplete day had it behind; the full day put it ahead. On Nov 14 so far, a day the
    rule does not count, it is no better than its candle.
  - **Item 7,** research job 43602782356, 3,557 minutes both books were live: new bids more than 5 bp from the
    research level 9 of 550 (1.6%) in the third book against 360 of 715 (50.3%) in the main book; bids the
    research would not have placed 23 of 550 (4.2%) against 153 of 715 (21.4%).
  - **For the record:** bids in common with the research 93% and 94% in the third book against 64% and 78% in the
    main book. The main book had six first-bid fills the research did not have, bought 9 to 73 bp above the
    research's level; the third book had none, and its three fills are at the research's price to the tick. The
    main book's fault grew with the venue's old BTC answers: 229 of its 377 new bids on Nov 13 were more than 5 bp
    off.
  - **What is left in the third book:** 19 of 349 new bids on the twelve candle-path coins the research would not
    have placed (5.4%), 752 coin-minutes skipped for an old candle answer, and nine level errors, all on Nov 13:
    five at one minute from one BTC bar 5.1 bp off, one from a kept LTC trades row, three on ZEC (up to 23 bp).
  - **Release 3 follows** with BTC, ETH, SOL, XRP and ZEC on the list. That five-coin version of the candidate is
    under test on runners now (suite 43602816403, paper run 43602818937); yesterday's runs covered six coins and
    four. Nothing is merged until those pass.
  - **Part 1 of the bar-source plan:** its runner job was started at 14:10 UTC on branch owner/read-barsrc (run
    43603482156, about an hour). It is read after this.
- **10:12. Release 3 is on `main`.** The main book, W2 and the live bot go to the third book's inputs, with BTC,
  ETH, SOL, XRP and ZEC on the trades list (RELEASES.md).
  - **Runner tests on this exact list:** The full offline suite on commit 0fb7f12c (run 43602816403): no file with a failure, the same replay and live-path numbers, 2,410 bars built from trades on the new inputs, 15 ladders kept across the switch. A paper run of the new main-book config on live data (run 43602818937, to 14:30 UTC): no error, 40 bars built from trades in eight minutes (five coins a minute), no fallback, data ready at a median of 11.1 s and 14.0 s at the latest.
  - **Paper books:** the main book and W2 take it at their next run, at about 17:20 UTC on Nov 14. The third and fourth books are
    unchanged.
  - **Live bot:** nothing changes until Miles runs `wickctl update`. The note tells him what to check, and that
    one more input release may follow the Nov 15 read.
  - **Scorecard: 47 to 53.** "The live bot matches the research" from 6 to 11; "Controls and monitoring" from 8 to
    9. The other blocks are unchanged.
  - **Still to do for test A:** put the main book's first start on the new inputs on file
    (reports/owner/test_a_start.json) once that run's log is on `main`.
- **10:34. Part 1 of the bar-source plan is read: the emulation holds, and no coin is held back on candles.** Run
  as planned (job 43603482156; tables in reports/owner/bar_source; result in bar_source_prereg.md).
  - **Checks on the emulation:** way B on the five traded coins agrees with the third book's logged score at 240
    of 249 bids (bar 90%); way A on the twelve at 486 of 528.
  - **Single-coin clause:** for every one of the twelve, way C has fewer score misses than way A over the three
    days. None stays on candles.
  - **The twelve together:** score more than 1.0 point from the research in 2.6% of coin-minutes under C against
    3.3% under A and 7.1% with trades rows kept; disagreement on arming 0.34% against 0.49% and 0.77%.
  - **Reading:** C is better than today's candles on every coin, by a modest amount: about a fifth fewer score
    misses. Keeping trades rows is the worst of the three, which fits what the third book showed for LTC and ZEC.
    Part 1 decides nothing else; the release question rests on Part 2, tomorrow.
- **10:54. The time of the step is a fidelity gap of its own, and the larger one.** Found while preparing the
  release that may follow Part 2. Nothing on `main` changes today.
  - **The data step.** Heartbeats since Nov 11 22:30 UTC: the main book's data step ends a median 9.6 s after the
    minute, the third book's at 10.3 s and the fourth book's at 13.4 s. The fourth book's way is three seconds
    slower because it fetches 18 coins' trades one after another, after the candles.
  - **Why it matters only live.** The paper books fill on the whole minute's candle. The live bot's bid rests from
    the second it is placed. The timing study has the slope: about one point of the research's same-minute fills
    for every second.
  - **Fixed before Part 2's read:** the release that carries the new bar source must be no slower than release 3,
    and test A does not start again at later releases (FORWARD_TESTS.md; the plan's deviation log).
  - **The order path, read from the code (bot/spot/engine.py), is slower than the study assumed.** Each minute the
    live bot asks the venue for the status of every resting order, then cancels each old bid and polls until the
    venue confirms it, then asks for each coin's best bid, and only after all of that places the new bids. For 15
    bids that is about 75 calls in a row. At 0.1 s a call the new bids rest from about 17 to 18 s after the minute.
    The study's central case was 10 s and its slow case 15 s. This is an estimate: no live run exists, so nothing
    is measured.
  - **Decisions.** (1) Rebuild the order path so that it takes a handful of calls: one batch cancel, one read of
    the open orders and of the fills, one price request for all coins, then the bids. (2) Take the candle requests
    out of the critical seconds and fetch trades side by side. (3) Measure how early after the minute the venue's
    trades list is complete, and move the step earlier only if it is. Each is a fidelity change with its own tests
    and release note. Rule B's count starts at the release with the new order path.
  - **Agents:** the release candidate with the new bar source is being built on branch owner/release-4 (Opus).
    The order path and the data step go to Opus agents on their own branches; the venue's interface facts are
    checked from its documentation first.
- **11:19. Step probe: script reviewed, run 1 started; order path: the venue's facts and the plan.**
  - **Step probe.** Plan fixed at 10:55 (reports/owner/step_probe_prereg.md). A Sonnet agent built the probe, the
    summary and the rule with offline tests (61, 23 and 36 checks). Reviewed: the probe uses the engine's own
    request and check at the engine's own pace, stops at once on a refusal or a rate-limit answer, and writes one
    row per request. One addition asked for and made: an error that escapes the loop no longer loses the rows.
    Run 1 started at 16:07 UTC on a runner (run 43613801204, 300 minutes, 54 requests a minute, at most 7 in a
    second). Run 2 is set for Monday from 13:30 UTC. The rule reads both together.
  - **The venue's interface facts.** The research agent read the venue's Python library (version 1.8.4) but could
    not open the documentation: its page requests needed an approval that was not answered in time, and it
    stopped, as told. It asked for those requests to be allowed. No setting was changed. The pages were then read
    from this session through its own search results, which the tool allows without that approval. One page was
    not read: the overview that the venue's retired rate-limit page forwards to needs Miles's approval to open, so
    the order endpoints' request limit stays unconfirmed and the bot will read it from the venue's own headers.
  - **What the documentation settles:** several orders can be cancelled in one request, but success only means the
    cancel was submitted; several orders can be read in one request, with fills and status; the best bid of
    several products comes in one request; editing a bid in place is not documented for good-till-date orders, so
    it is not used. Public market data is limited to 10 requests a second per IP (the bot's pace is 7).
  - **Order path plan** (reports/owner/order_path_plan.md, fixed at 11:16, before any live order): setting
    `order_path`, today's code untouched as the default, the batch path beside it with today's single requests as
    the fallback for every piece, the tests before release, and what the first live day must show. An Opus agent
    is building it on branch owner/order-path.
- **12:50. The main book's first run on release 3 is under way.** Run 43620656443 started at 17:21 UTC from a
  commit that holds release 3 (bot/spot/config.json: newest bar from trades, guard on, list BTC, ETH, SOL, XRP,
  ZEC). Both of its jobs, the main book with W2 and the third book, are still running after 29 minutes, so there
  was no start-up fault. Its log reaches `main` when the run ends, at about 23:12 UTC. Tomorrow's read confirms
  the heartbeat counters and puts test A's start on file.
- **16:26. Step probe, run 1: complete with no fault. An interim look.**
  - **The run** (43613801204): 300 minutes, 16:08 to 21:07 UTC, 16,218 calls in 21,211 requests, never more than 7
    in a second. No refusal, no rate-limit answer, no pass skipped, no crash file.
  - **Interim look.** It can find a fault and pass nothing; the rule is read on both runs after Monday's.
    - **At 6 s and later,** when the engine asks today: 5,201 of 5,202 requests verified, and all 5,197 that have a
      reference equal it.
    - **Earlier:** sent in second 1, 74% verified and 83% of those equal the reference; second 2, 90% and 93%;
      second 3, 96% and 97%; seconds 4 and 5 (383 requests), 100% and 96%. BTC, always sent at 1.0 s: 43%
      verified, and half of those equal.
    - **Why:** every unverified early request got a first page that the venue had made before the minute ended.
      Early bars that pass the check still miss prints that reach the list a few seconds late.
  - **What it points to (not a verdict):** the public trades list is complete only about 6 s after the minute. If
    Monday's run agrees, the step cannot start earlier while it asks for trades by request. Only a stream of
    trades could, and that would need its own probe.
  - **How long requests take on this runner:** 0.11 to 0.17 s for most coins, 0.5 to 0.6 s for BTC, whose minute
    spans several pages. The 18-coin pass takes a median 3.2 s, which is what a pace of 7 a second allows for
    its 22 or so requests. Sending them side by side would not shorten it.
  - **Decision for the data-step build:** it drops the side-by-side setting and the step-time setting. One thing
    remains: the candle requests move out of the critical seconds. With all 18 coins from trades that puts the end
    of the data step at about 9.2 s after the minute on a runner, against 10.3 s for release 3's way and 13.4 s
    for the fourth book's.
- **17:46. Order path build reviewed; seven changes asked for. Scorecard re-scored: 51 of 100.**
  - **What came back** (branch owner/order-path): the batch methods on the live broker, the engine's batch path
    beside today's code, a stand-in for the venue's library so that the real broker class runs in the live-path
    simulation for the first time, 70 unit checks, and a three-way run in which the test exchange, the real broker
    on today's path and the real broker on the batch path agree on every entry, exit and dollar. Today's functions
    keep their text: four lines changed, 559 added.
  - **The model of the clock** (0.1 s a request; a model, not a measurement): from the end of the data step to the
    last new bid, a median 7.8 s on today's path and 2.0 s on the batch path; 50 requests a minute against 19.
  - **Reviewed line by line.** The batch path reproduces today's decisions coin by coin. Seven changes before it is
    a candidate: (1) one unreadable placement answer must not lose the bookkeeping of the others; (2) a failed
    batch cancel falls back to single cancels at once, and late reads are checked against the single read; (3) an
    order with a recent fill is always read singly; (4) a running check of the batch read against the single
    read, which switches the batch read off after two mismatches; (5) an older library on the server must not
    stop the bot; (6) a command the account owner runs once, `order-check`, which places three tiny bids at half
    the market price, reads and cancels them through the batch requests and reports what the venue really does;
    (7) documents. The agent is on them.
  - **Scorecard:** "the live bot matches the research" from 11 to 9, total 51. The order path's gap was there
    before today; the score now says so.
  - **Still running:** the release candidate with the new bar source (tests are slow on two cores). The data-step
    build waits for it. Part 3 of the timing study waits for a free core.
- **21:45. Evening: order path second review, sandbox run, the bar-source candidate reviewed, the data-step build
  started.**
  - **Order path, second review.** The seven changes are in as asked (94 unit checks, 14 for the new check command;
    the three-way run still agrees to the dollar; modelled median from the data step's end to the last new bid 2.3 s
    with the added safety reads, against 7.8 s on today's path). Four smaller changes went back: the running check
    flags only contradictions, the check command prices its test bids from the public book and sweeps for a lost
    test order, and `wickctl order-check` refuses while the bot runs.
  - **Sandbox run** (run 43667375643, the venue's library 1.8.4): 26 of 28 checks pass. The two that fail are limits
    of the sandbox: it does not serve the best-bid request (404) and sends no rate-limit headers. The batch read,
    the batch cancel and placing on three threads answer in the expected shapes. Canned answers only: shapes, not
    behaviour.
  - **Bar-source candidate** (branch owner/release-4, built by an Opus agent over the day): the engine option is
    carried over from owner/engine-c unchanged (checked here: the two diffs are the same and three files are the
    same to the byte), the main book's and W2's configs carry the fourth book's four input settings, every test
    equal to the baseline with the option absent, and the live-path simulation on the new inputs gives the same
    entries, exits and P&L as candle mode (8,153 of 8,187 trades rows replaced by their candle, none differing in
    the made-up feed). One fact from the fourth book's own counters: 10,533 of 68,429 replaced rows (15.4%) had a
    candle close more than a tick from the trades bar that the decision used. Not merged: it waits for Part 2's
    read, the step-time condition and its own paper book.
  - **Data-step build started** on the same branch (Opus): one setting, `candles_at_s`, moves the candle requests
    of trades-built coins into a pass between steps. It also corrects the inputs line where it said "candles for
    the other coins" with no other coin left.
  - **Tomorrow, 08:40 ET:** Part 2's read. Its period ended at 22:29 UTC today.

## Nov 15 2026 (times ET; UTC is five hours later)
- **02:37. Night: Part 2 read (pass), a gate on the new order path, the data-step build's floor under measurement,
  timing Part 3 started.**
  - **Part 2 of the bar-source plan, read as planned** (plan, "Result of Part 2"; record in
    reports/owner/reconcile_tb/part2/). The logs reached the period's end hours ago, so the read did not wait for
    the 08:40 check. Count first: 452 and 435 new bids on the twelve, no extension. Research job 43689324147.
    Verdict: **pass**. Wrong-side bids on the twelve 18 of 435 against 20 of 452, matched 404 of 434 against 414
    of 448, level errors 4 and 4, items 1 to 5 all met. On the twelve the books are nearly the same; the clear
    gains are on the five coins the third book keeps on trades rows and in minutes skipped for an old answer (4
    against 763).
  - **Order path.** The full offline suite passed on the reviewed commit (d21317af, run 43673559075: 20 test
    files, none with a failure, replay 156 rungs identical, the three-way simulation equal in both windows). Then
    one more change, logged in the plan before the work: **a gate**. The live bot uses the batch path only after
    `wickctl order-check` has passed on that server with the installed library; until then it runs release 3's
    path. Reason: the batch requests have never reached the real venue, and a server updated and started without
    the check would have traded on them. Built by a Sonnet agent (decision in `run.py`, engine untouched; 62
    status and gate checks, 20 for the check command), reviewed, pushed as e3bd62d1. The suite is running on that
    commit (run 43690044333). Release 4 follows if it is clean.
  - **Data step.** The builder of the request-at-second-45 design found that its answers can be copies made at
    the start of the minute by other clients of the same address, which leaves two trades rows instead of one.
    The collector's record agrees (BTC's candle answer is a copy in 96% of minutes, a median 65 s old). An
    addition to the bar-source plan was fixed at 02:07, before any output: an emulation pass with two trades rows
    for all 18 coins, to pass if it is no worse than release 3's inputs on arming and on scores. At 02:26, still
    before any output, a correction: the later request is never worse than one right after the bids, so the pass
    measures the built design's floor. Tool extended by a Sonnet agent (50 new offline checks), reviewed; runner
    job 43689717933.
  - **Timing study, Part 3.** Two policies added and the way the new paths are derived logged at 02:29, before
    any evaluation. An Opus agent is on phase 1 (regression of the six policies on file, a runner script that
    re-derives the paths from the first fetch's print artifacts, the evaluator for twelve policies). The
    artifacts expire on Dec 1.
  - **Test A's start is on file:** the main book's first decision minute on release 3 was 17:27 UTC on Nov 14.
    Its heartbeats carry the trades counters (150 bars per half hour, five coins); 15 fallbacks in about 3,400
    coin-minutes so far. Its data step ended a median of about 10 to 12 s after the minute, by runner; between
    21:00 and 23:00 UTC on Nov 14 all three books were slow (13 to 17 s).

## Nov 16 2026 (times ET; UTC is five hours later)
- **08:33. Release 4 (order path), the two-row floor read (pass), probe run 2 started, timing Part 3 on the runner.**
  - **No work was done between 02:45 on Nov 15 and 08:26 today.** The jobs started before then finished on their
    own; the 08:40 check of Nov 15 found Part 2 already read.
  - **Release 4 is on `main`** (RELEASES.md). The live bot's order requests in batches, used only after
    `wickctl order-check` has passed on the server with the installed library; until then release 3's path. Added
    since the last entry: a hand switch (`wickctl order-path serial|batch`, a marker file the gate reads first), so
    the way back touches no config. Final commit 513ab722: full suite (job 43691154265) 20 files, none with a
    failure; sandbox (job 43876402271) 26 of 28, the two sandbox limits. Paper books unaffected. Rule B counts from
    the first live minute on the new path.
  - **The addition to the bar-source plan, read: pass** (plan, "Result of the addition"). Part 1's counts
    reproduced exactly. Two trades rows for all 18 coins: 193 disagreements on arming of 63,330 against 188 with
    one row and 278 with the third book's inputs; score misses 1,473 against 1,434 and 1,933; levels the same as
    with one row. So the build that asks for candles at second 45 goes to its paper test as it is.
  - **Step probe, run 2:** dispatched at 08:27 (job 43875928226; its Run step began 13:27:57 UTC). Read set for
    13:50.
  - **Timing study, Part 3, phase 1 reviewed.** The six policies on file reproduce byte for byte (15 files), before
    and after the agent's changes. The runner script re-derives the paths for fifteen start times from the stored
    prints, checks the six old ones against the rows on file, and stores one union path per row, verified on every
    row. Job 43876543675 dispatched at 08:31. Phase 2 (the twelve policies) follows its output.
  - **Test A since release 3 (the status report shows CHECK):** 27 rungs, $278K bought, net -40 bp per dollar.
    It is one market-wide minute: at 20:54 UTC on Nov 14 the first bid of 14 coins filled within the minute, the
    book ran short of cash, and most of those rungs left by time an hour later at lower prices. The third and
    fourth books show the same (exits since then -$604 and -$895 against -$536 here). No fault and no error
    event; no new fill since 22:10 UTC on Nov 14. The rule reads at three weeks and 60 rungs.
- **08:48. Timing study, Part 3 read; the input build merged onto main and hardened; the fifth book's test fixed.**
  - **Part 3 of the timing study** (timing_prereg.md, "Result of Part 3"; facts in reports/owner/timing/). Paths
    re-derived from the stored prints equal the rows on file (29,686 rows); the six policies on file reproduce
    exactly. Same-minute share of the research's first-bid fills by era: as built (new bid from 17.25 s) 81 / 84 /
    75%, release 4 (12.15 s) 85 / 87 / 81%, with the data step 86 / 88 / 81%, a stream-fed step deciding at the minute 93 to 96%. About
    0.8 to 1.0 points a second. In money no order: pooled against the research's zero-delay fills, whole ladder,
    -8.2% as built, -5.2% release 4, -2.8% with the data step, -1.2% to -2.6% by stream; the first-rung valuation
    gives no such order and the eras change sign. No steady gain without a carried bid. Rule B's expected capture
    restated (81 to 87% within two minutes).
  - **The input build is on today's `main`,** branch owner/release-5 (Opus agent). The merged engine equals both
    sides' changes line for line (160 changed lines from the input build, 746 from the order path); 14 light test
    files pass (inputs 90 checks). Two hardening changes sent back before the commit is pinned: the candle
    requests between steps fail fast (one try, 4 s; a hanging request could block the fast polls and the step for
    about 83 s), and a `candles_at_s` key outside trades mode is ignored with a warning instead of stopping the
    bot at start.
  - **Part 3 of the bar-source plan fixed at 08:38, before the book exists:** the fifth paper book runs the
    build's own release config at a pinned commit for three days. Four measures: the data step's end at or below
    10.3 s and no later than the main book's; decisions against the research within fixed tolerances of the fourth
    book's; items 1 to 5; the candle requests between steps. The third book ends when the fifth starts. A Sonnet
    agent is building the workflow, the status report's sections and the rule script (branch owner/r5-infra).
  - **A short live paper run of the new `main`** (job 43878173310) was started to see release 4's code on live
    data before the books pick it up.
- **13:36. The fifth paper book starts: the input build at a pinned commit.**
  - **Commit** `9e6f53b3` of owner/release-5 (plan, deviation log).
    - Full offline suite on it (job 43898459890): 22 test files, none with a failure, 830 passing checks; the
      replay equals the research rung for rung.
    - Live A/B of the data step on one runner (job 43898466756): a median of 15.35 s without the between-step
      requests and 11.37 s with them; 540 requests between steps, none failed; 8 candle requests were made inside
      a step; none of 1,512 compared rows differs.
  - **What the first suite run caught** (job 43880224505, commit 7ae96c9e): my fail-fast change for the candle
    requests between steps treated any answer without rows as a failure. HYPE has no data in the simulation's
    October 2025 window, so its valid empty answer went to the step in every minute (465 of 465 steps) and one test
    failed. Corrected by the agent (only a request with no answer fails), confirmed by running that test, then
    the whole suite again. The first live A/B, on the superseded commit (job 43880261551): data step 14.88 s with
    the candle requests in the step, 9.70 s with them between steps, 540 requests between steps and none failed,
    no row different from the venue's candles.
  - **The suite took two hours this time** (66 minutes on the first run): the runner was about 1.8 times slower in
    every file. Not knowing that, I started the same suite again on the same commit at 18:16 UTC (job
    43927028467) so that a hang could be told from a slow machine. It is still running and decides nothing now.
  - **Release 4's code on live data:** a short paper run of the new `main` (job 43878173310) ended clean: 16 new
    bids, one heartbeat with the trades counters, no error and no warning event.
  - **Measure 1 was changed before the book existed** (plan, deviation log, 12:04): the second live A/B showed
    the build at 11.37 s on a slower runner, and the books show release 3's own way at 11.5 s since yesterday
    noon UTC against 10.26 s last week. A fixed 10.3 s bar measures the week, not the build. It is replaced by
    same-machine pairs against release 3's inputs, four times a day; the comparison with the main book stays.
  - **Infrastructure merged to `main`** (branch owner/r5-infra, Sonnet agent, reviewed): the fifth book's workflow
    with the commit in one place, the pairs' workflow and runner script, the third book out of the main paper
    workflow (the main book's job is byte-identical), the status report (the third book shown as ended, the fifth
    book's sections, 283 checks) and the rule script (110 checks).
  - **Two points on the pairs, logged in the plan before any pair exists:** today's 18:05 pair is started by hand
    once the book has written its `CODE` file (at 18:05 neither the workflow nor the file existed); and if fewer than 8 pairs count in
    the period, the pairs go on and the reading of part (a) waits for the eighth. It can delay the read, not choose
    pairs. The rule script does this (Sonnet agent, branch owner/r5-pairs-ext, reviewed; 110 checks).
  - **First run:** 40 minutes, for an early look at the counters; then the normal hand-over.
- **13:40. Step probe read: no second earlier than 6 passes. The step stays at 6 s.**
  - **Run 2** (job 43875928226): Monday, the minutes closing 13:29 to 18:28 UTC, 300 minutes, 16,218 calls, no
    refusal, no rate-limit answer, never more than seven requests in a second. It began one minute before the
    planned 13:30 (plan, deviation log).
  - **Both runs together** (plan, "Result"; tables in reports/owner/step_probe/read/):
    - sent in second 1: the engine's check accepts 66% of requests, and 87% of the accepted bars equal the list
      95 s later; second 2: 84% and 95%; second 3: 93% and 97%; seconds 4 and 5: 100% and 97.5%;
    - BTC, always sent at 1.0 s: 43% and 54%;
    - from 6 s, where the engine asks today: 9,543 of 9,544 accepted, 9,531 of 9,532 equal.
  - **The rule:** items 1 to 3 fail in every early bin and for BTC, on samples that are large enough. The script
    prints "wait" because the bin [4,6) holds 1,220 requests against 2,000; I record "none" by the plan's own
    words and add no run, since BTC is sent at the same second in every run (plan, deviation log).
  - **Looked at afterwards, deciding nothing** (reports/owner/step_probe/read/explore.md): by the second a request
    was sent, the bars of the 17 other coins equal the later list in 82%, 88%, 94%, 97% and 99.4% of cases for
    seconds 1 to 5, and in 10,787 of 10,788 from second 6 (all coins). An answer's age does not explain it: the
    venue's cache never gave an incomplete early answer back five seconds later (0 of 239), and gave a complete
    one back about half the time. Trades reach the public list up to about five seconds after they happen.
  - **What follows.** A step that decides earlier than 6 s cannot be built on requests. The trade stream is the
    only way to it, and it has to be measured from the server with its own plan. The timing study puts a stream-fed
    step at 93 to 96% same-minute fills by era against 81 to 87% for release 4, so the lever stays on the list.
- **14:28. The fifth book's first run: no fault. An interim look, and one thing to watch.**
  - **The run** (43930915168, 18:39 to 19:24 UTC): the pinned commit checked out (`paper_spot_r5/CODE` names
    9e6f53b3), first stepped minute 18:44 UTC, 18 new bids, one heartbeat, no error, warning or halt event. The
    hand-over started the next run (43938993420), a normal one of 345 minutes.
  - **The period** of Part 3 therefore begins at 19:00 UTC on Nov 16 and its 4,320 minutes end at 18:59 UTC on
    Nov 19, before any extension.
  - **The first pair** was started by hand at 19:26 UTC, the build first (job 43939421658), as the plan's entry of
    13:36 says. From 00:05 UTC the schedule runs them.
  - **Interim look at the 19:00 heartbeat** (17 steps). It can find a fault and pass nothing.
    - Between-step candle requests: 306 made, none failed. Data step: median 11.06 s, longest 16.32 s.
    - Candle requests inside a step: 10 of 306 coin-minutes (3.3%). All ten followed a trades pass that ran out
      of its 8 s budget before it reached every coin. The counter shows 20 budget fallbacks; the other 10 had no
      such request after them, so by the code they belong to the start's own pass, which rebuilds five minutes
      at once (not checked further).
  - **To watch: the venue's trades list has been slow since Nov 14, and slower this afternoon.**
    - The fourth book's trades pass ran out of its budget for 1 of 23,888 coin-minutes on Nov 12 and 3 of 24,304
      on Nov 13. Then 1.0% on Nov 14, 1.3% on Nov 15, 1.6% today so far, and 58 of 531 (10.9%) in the half hour to
      19:00 UTC. Its data step went from a median of 11.5 s this morning to 15 to 17 s this afternoon.
    - The probe saw the same from its own runner: an 18-coin pass took 4.0 s at the 90th percentile on Saturday
      and 7.5 s today.
    - Measure 4 allows candle requests inside a step in 2% of coin-minutes. If the venue stays this slow, the
      fifth book will not meet it, and the cause will be the trades pass's time, not the requests between steps.
      The rule stays as written: this is not a fault in the plan's sense, so the test runs on and is read once.
    - It matters beyond the test. Eighteen coins asked one after another fit the budget on a quiet day and not on
      a busy one, and busy days are where the strategy earns. If Part 3 fails here, the corrected build has to
      make the trades pass faster (requests side by side under the same pace, or less paging), and that build
      gets its own three days.
- **14:40. Why the trades pass is slow, and a plan for asking side by side.**
  - **The cause** (read from the probe's recorded requests): single slow requests, not paging. A slow 18-coin
    pass has the same number of pages as a fast one. On Nov 16, 6.0% of the requests to the smaller coins took
    more than half a second and 0.4% three seconds or more; on Nov 14, 0.7% and 0.04%. Asked one after another,
    one slow request holds up every coin behind it.
  - **A model on those requests** (each call keeps its recorded time less its pace wait; with one worker it gives
    the recorded passes back to within 0.1 s): three workers at the same pace bring the pass from a median of
    3.1 to 3.2 s down to 2.5 s, from a mean of 3.3 and 4.1 s to 2.6 and 2.9 s, and leave none over the 8 s budget
    (1.0% and 6.3% as recorded).
    - My first model run counted each call's pace wait as network time and put the gain at 0.9 s at the median.
      Checked against the gaps between sends before the plan was committed; the corrected figure is 0.6 s.
  - **In money this is small.** The timing study cannot rank a second. The reason to build it is the build under
    test: 18 coins on trades cannot keep their inputs on a busy day with this pass.
  - **Plan fixed** (reports/owner/trades_workers_plan.md) before the code has run on live data: offline parts,
    one live run for faults, same-machine pairs of one worker against three, and a sixth paper book against the
    fifth. An Opus agent is building the option on branch owner/trades-workers, off by default.
  - **Bar-source plan, deviation log:** if Part 3 fails on measure 4 alone, this is the corrected build and the
    sixth book's three days count for it, read by Part 3's own measures. Written before either book is read; no
    measure is added or loosened.
- **14:41. The repeat of the suite on the pinned commit ended clean** (job 43927028467, 85 minutes): the same 22
  files, none with a failure, the same 830 passing checks. Two clean runs on 9e6f53b3 on two runners.
- **15:05. The side-by-side trades pass is built and reviewed; the suite is running on it.**
  - **The build** (Opus agent, branch owner/trades-workers, commit 4c1717ac; facts in
    reports/owner/trades_workers_candidate.md on that branch): option `trades_workers`, off unless set.
    - One function in `bot/market.py` owns the threads, the pace, the stop and the deadline. Workers fetch data
      only. The engine works out every coin's plan first and applies the results afterwards, in today's order,
      with the same code the one-after-another loop uses.
    - With 1 or absent the old path runs. The loop body was split into three functions; I compared them with the
      old lines one by one.
  - **Reviewed, and what the review settles:**
    - the pace: each send reserves a slot at least 1/7 s after the one before and is then checked against the
      last send that actually went out, under one lock for all workers and the old path;
    - a refusal or a rate limit: the stop and every send are recorded under one lock, so nothing is sent once the
      stop is set, not a retry and not the next page of a coin in the middle of paging;
    - the budget: no job starts and no request is sent after the deadline, the pass returns by it, and a late
      answer is thrown away.
  - **What it cannot do, said plainly:** a request that is already on its way when another one is refused cannot
    be called back. With three workers that is at most two requests. The old path has none.
  - **Where the two paths differ** (each shown by a test): after a stop the old path keeps the coins before the
    refused one and the new path keeps whatever had arrived; the new path reaches coins the old one would not
    reach in time; an answer that arrives after the deadline is used by the old path and dropped by the new one.
  - **Tests here:** the new file 79 checks (run again by me, passed), 16 light files without a failure. The five
    long files run in the full suite on a runner (job 43945430666, started 20:01 UTC).
  - **Infrastructure for the sixth book** is being built by a Sonnet agent (branch owner/tw-infra). The fifth
    book's pair tool and workflows stay untouched; the new pairs get their own tool.
- **15:21. A weakness in the pair tool's rate-limit mark, handled before any pair has ended.**
  - Found by the Sonnet agent while building the sixth book's infrastructure: the fifth book's pair tool takes
    the bare number 429 anywhere in a half's output as a rate limit.
  - **Fifth book's pairs:** a false mark can only remove a pair. The tool stays frozen and a marked pair stays
    out (bar-source plan, deviation log).
  - **Sixth book's pairs:** there a false mark in a three-worker half would fail the test, so that plan's own
    tool marks a rate limit only by what one really prints (trades-workers plan, deviation log). The agent is
    making that change.
- **15:32. Sixth book's infrastructure reviewed; two corrections to my 14:40 entry in the bar-source plan.**
  - **Infrastructure** (Sonnet agent, branch owner/tw-infra, head 538a0871): the sixth book's workflow, the
    workers pairs with their own tool, the status report's sections, the rule script (135 checks), notes.
    - The fifth book's workflows, its pair tool with test and fixtures, and both older rule scripts are identical
      to `main` (empty diff). Five existing lines of the status script changed; on today's logs the new script
      writes the same report as the one on `main`, byte for byte.
    - Tests run by me: 90, 57, 135, 110, 63 checks and the status report's suite, all passing.
    - It merges when the commit is pinned (after the suite and the live check).
  - **Corrections** (bar-source plan, deviation log):
    - the in-step share at the first heartbeat is 1.9% by the rule's own arithmetic (10 of 540), not the 3.3% I
      wrote (10 of the 306 coin-minutes actually stepped);
    - item 1 of measure 3 counts the same budget fallbacks (304 of 324 verified, 93.8% against 99%), so the
      branch for the corrected build now covers a fail on measure 4, on item 1, or on both. Seen in the status
      report's first rendering of the same first heartbeat; nothing new was read.
- **17:03. The side-by-side build: Part 1 holds, the commit is pinned, the live check starts.**
  - **Suite on a runner** (job 43945430666, commit `4c1717ac`): 23 test files, none with a failure, 914 passing
    checks (the 830 of the fifth book's commit, the new file's 79, five more for the inherited-settings list);
    the replay equals the research rung for rung.
  - One existing expectation changed, the list of inherited settings in `release_inputs_test.py` (eight names
    instead of seven). Logged in the plan with the three places where the two paths differ.
  - **The first same-machine pair of the fifth book counts** (started by hand at 19:27 UTC, the build first): 31
    timed steps in each half, no refusal, no rate limit. One pair is progress, not a result.
  - **Part 2** of the trades-workers plan follows now: one runner, 30 minutes with one worker and 30 with three,
    each checked against the venue's candles. It can find a fault and pass nothing.
- **17:04. Evening look, faults only.**
  - **The main book's first run on release 4's code** (16:08 to 21:57 UTC): 12 heartbeats, 37 new bids, no error,
    warning or halt event. W2 the same. Its next run started by the hand-over, now without the third book's job.
  - **The third book has ended:** its last run closed at 21:57 UTC. Its folder and log stay as the record.
  - **The venue's speed, by book, this afternoon** (half hours 16:30 to 21:30 UTC):
    - main book, five coins on trades: data step at a median of 9.6 to 9.9 s, no budget fallback;
    - third book, six coins: 10.2 to 10.7 s, none;
    - fourth book, 18 coins: 14.6 to 17.2 s and 7 to 58 budget fallbacks a half hour (log to 19:00 UTC).
    - So the slow trades list costs the 18-coin pass and not the short ones. The main book and the live bot's
      present inputs are not affected.
  - **The fifth book:** second run in progress, nothing new on `main` until it ends at about 01:10 UTC; no fault
    in what is there.
  - **Live check of the side-by-side build** (trades-workers plan, Part 2): job 43966296502 started 22:03 UTC,
    30 minutes with one worker and then 30 with three.
- **18:35. Live check of the side-by-side build: no fault. Part 3 of its plan redesigned before any Part 3 run.**
  - **Part 2** (job 43966296502, 22:20 to 23:25 UTC): one worker 2.65 s at the median and 4.49 s at the longest;
    three workers 2.64 s and 3.79 s. No budget fallback, at most 7 requests in a second, none of 756 compared
    rows differs in either half. No refusal, no rate limit, no crash.
  - **What it showed:** the venue was fast again and both paths sat at the pace (2.43 s is the floor for 18
    requests). My plan's measure 1 asked for a 0.2 s gain at the median, taken from a model fitted to another
    runner. I had written that it does not depend on slow minutes. It does.
  - **The change** (plan, deviation log, with what it does to the odds): Part 3 becomes runs that alternate one
    worker and three minute by minute on one machine. No harm at the median (0.05 s); at most half the share of
    passes over 6 s, with at least 30 such passes seen on the one-worker side and up to 14 days to see them; the
    pace and the rows as before, the rows with a one-point tolerance.
    - It is easier to pass than the first version when most minutes are quiet and some are slow. That is the
      case the option is for. It is logged before any Part 3 data exist.
    - If no slow spell comes in 14 days, the gain is not shown and the option stays off.
  - **Part 4 unchanged:** the sixth book starts now. The alternating tool is the next piece of work for the
    agent; the half-hour pair tool it built for this plan is not used.
- **19:22. The sixth paper book is running; Part 3's alternating jobs start at 03:05 UTC.**
  - **Sixth book** (`paper_spot_tw`, pinned 4c1717ac, three workers): first run 23:37 to 00:21 UTC, first stepped
    minute 23:41, 16 new bids, no error, warning or halt event, no fallback. Data step 8.66 s at the median,
    trades pass 2.66 s. The hand-over started its normal runs. Period: 00:00 UTC Nov 17 to 23:59 UTC Nov 19.
  - **Infrastructure on `main`** in two merges: the book's workflow alone first (4cd23be0), so that the half-hour
    pair tool of the first design never reached `main`; then the alternating job, the rule script and the status
    report's sections (d95b733e). The fifth book's workflows, pair tool and rule scripts are untouched, and on logs
    without the sixth book the new status script writes the same report as before, byte for byte.
  - **Reviewed by me:** the alternating tool line by line (arm by the minute's parity, counters by step, bars as
    built, comparison by arm). One fix sent back: the comparison's candle requests retried a rate limit five
    times and would have read "no answer" as "every bar differs". Now one try, and no answer stops the comparison.
  - **Tests run by me on the merged branch:** 58, 146, 57, 110, 63 checks and the status report's suite, passing.

## Nov 17 2026 (times ET; UTC is five hours later)
- **08:20. Morning look, faults only. No fault in any book. Two changes follow, both logged in the plans.**
  - **Books since 19:00 UTC on Nov 16:** no error, warning or halt event in the main, fourth, fifth or sixth
    book. All four hand over. Nothing from Miles on release 4's server steps.
  - **The venue was calm overnight,** with one slow spell around 03:30 to 04:00 UTC. In that half hour the trades
    pass ran out of budget for 12 coin-minutes in the fourth book, 14 in the fifth and 3 in the sixth (three
    workers), whose longest pass was 8.01 s. Different runners, so this is not a comparison.
  - **Fifth book, progress only** (36 heartbeats): data step at a median of 8.5 s (main book 9.6 to 11.2 s by
    runner, fourth book 12 to 15 s); 35 budget fallbacks of 18,306 coin-minutes, 20 of them from its first half
    hour; 26 candle requests inside a step of 19,440 coin-minutes (0.13%); no failed request between steps.
  - **Sixth book, progress only** (25 heartbeats): data step 8.5 s, trades pass about 2.5 s, 3 budget fallbacks,
    6 candle requests inside a step, one failed request between steps of 12,600.
  - **Fifth book's pairs:** two count. Nov 16 19:27 UTC: the build 8.55 s, release 3's inputs 11.24 s. Nov 17
    06:56 UTC: 8.46 s and 9.49 s. Both with the build first.
  - **GitHub's clock** dropped the 00:05 pair, started the 06:05 one at 06:56 and had not started the 12:05 one
    by 13:18. For the alternating jobs it dropped 03:05 and started 09:05 at 11:41.
    - **Change:** a pair is also started when a run of the fifth book ends, and an alternating job when a run of
      the sixth book ends. Event-driven, about every 5 h 50 min, nobody chooses the time (both plans, deviation
      logs). A separate small workflow; the pair tool and its workflow are not touched.
  - **First alternating job** (11:41 UTC): the tooling works on the real venue. 30 and 31 steps, both arms at
    2.59 s, nothing slow, 7 requests a second at most. 242 and 236 of 522 bars differ from the candle.
    - **Change:** with nearly half the bars differing in both arms, "at most one point more" would fail by
      chance about one time in eight. Measure 4 and the budget-fallback clause of measure 2 now fail only when
      three workers are worse by more than chance allows (trades-workers plan, deviation log). The first job
      favoured three workers, so nothing seen is rescued.
  - The side-by-side build asked for in last night's note to myself is already built and under test.
- **08:26. Both changes are on `main`** (cd2fa16b; Sonnet agent, reviewed).
  - **The starter** (`.github/workflows/test-clock.yml`): when a run of the fifth book ends it starts a pair, when
    a run of the sixth book ends it starts an alternating job. Only after a run that ended well, was started by
    the hand-over and lasted at least 30 minutes. Its decision is a small script with 18 offline checks. First
    starts expected at about 17:51 UTC (sixth book) and 18:44 UTC (fifth book).
  - **The two clauses** live in one function that the status report and the rule script share. Tests run by me:
    157, 58, 110, 57 and 63 checks and the status report's suite, all passing. On today's logs the new status
    script differs from the old one in those two lines only.
  - The pair tool, its workflow, the alternating tool and its workflow are byte for byte as they were.
- **14:21. The starter did not fire. The start moves into the paper books' hand-over.**
  - GitHub delivered no event when the sixth book's run ended (17:52 UTC) or the fifth book's (18:43 UTC): the
    starter has no run, and the status report did not run after them either. The scheduler is also worse: the
    status report's 07:17 UTC job started at 16:54, and no pair or alternating job has started since 12:05 UTC.
    GitHub's status page shows no incident today.
  - A job starting another job directly has never missed here (each book's hand-over). So the hand-over script
    will also start a pair after a fifth-book run and an alternating job after a sixth-book run, once it has
    started the book's own next run. The starter workflow goes. Logged in both plans before the change.
  - The change is to the one script all paper books share, so it gets its own test run and a look right after
    the first two hand-overs tonight (about 23:42 and 00:33 UTC). If a hand-over fails, I start that book's next
    run at once: a book's continuity comes before a test job.
  - The two starts missed today are not made up by hand.
- **14:28. The hand-over change is on `main`** (c1f1a489; Sonnet agent, reviewed and tested by me).
  - **What it does** (`bot/spot/deploy/paper_next.sh`): once it has started a book's next run, it starts a pair
    after a fifth-book run and an alternating job after a sixth-book run. For the main and fourth books it does
    nothing more. A test job that fails to start prints a line and never fails the hand-over.
  - **Checks:** 27 in the script's test, the 10 old ones unchanged; the commit script's test passes. The starter
    workflow and its script are deleted, so a late event cannot start a second job.
  - **First uses tonight (UTC):** main book about 21:18 (no test job, but the first run of the changed script),
    sixth book about 23:42 (alternating job), fourth book about 00:23 (no test job), fifth book about 00:33
    (pair). I look after each one.
  - Nothing that changes a trading decision went to `main`.
- **14:38. The two engine items queued on Nov 13: one is being built, one is left as it is.**
  - **False balance warnings after a restart during fills** (Opus agent, branch owner/balance-look, from the
    release 5 candidate 9e6f53b3). At a start the bot compares balances before it books the fills of the time it
    was down, so each such fill is a phone alert (seven in the simulation with a server death). The 15-minute
    check has the same weakness for a fill in the seconds before it.
    - **The rule:** a difference is warned only when it is still there at a second look and the bot has booked
      fills between the two looks. A first look that differs is logged as an event that does not alert. A
      difference that stays is still warned about every 15 minutes, one step later than today.
    - It changes no order, cancel or fill, and paper mode never runs it. It is the sweep's alert made
      believable, not removed. It ships in a later release with a note; the full suite runs on a runner first.
  - **Bids that rest through a minute the stale guard skips: no change.** Since Nov 11 the four books' logs hold
    two such minutes, both in the fourth book on Nov 15. Too rare to be worth a change to the order path.
- **14:57. The balance warning: first result, a correction, and one addition to the rule.**
  - **The agent stopped as told** when the simulations did not match my brief. With the rule in place, entries,
    exits, P&L and final balances are identical to before (111 entries and $11,723.34; with the server death 109
    and $8,421.28).
  - **Correction to the 14:38 entry.** Of the seven warnings in the run with the death, six come from the restart
    and one from a 15-minute look. The run without a death has two warnings, not none. My brief had both wrong.
  - **What the rule did:** the six restart warnings are gone (a first look, then cleared by the look after the
    gap's fills were booked), and one of the other three as well.
  - **A second harmless cause, found by the simulation:** a market sell whose outcome the bot cannot read yet. The
    coins have left the venue, and the bot keeps the rung until it can read the sell (two to three minutes in
    the simulation). Booking fills does not resolve that, so those warnings only moved by a minute.
  - **Addition to the rule, decided now, before the build goes on:** while a coin has a market sell with an
    unknown outcome, a shortfall no larger than those sells is not warned for up to 10 minutes after its first
    look. A surplus, a larger shortfall, or one that is 10 minutes old is warned as before. Each such sell
    already alerts on its own, when it is sent and when it is resolved.
  - **The simulation gets a check of its own:** from now on a run with any balance warning fails.
- **16:26. The changed hand-over script: first real use, the main book.** Its run ended at 21:19 UTC after 350
  minutes and the script started the next one (44178580796) in the same second; no test job, as intended for
  this book. A scheduled run that GitHub had queued four minutes earlier was cancelled by it, as on other days.
  Next: the sixth book at about 23:43 UTC, with the first alternating job started this way.
- **16:27. The balance warning build is reviewed; the full suite is running on a runner.**
  - **The build** (branch owner/balance-look at 46e1ee84, six commits on the release 5 candidate): 62 changed
    lines in the engine, a new test with 26 checks, and the live-path simulation now fails on any balance
    warning. Facts in `reports/owner/balance_look_candidate.md` on the branch.
  - **Simulations before and after** (run by the agent): entries, exits, P&L and final balances identical.
    Balance warnings fell from 2 to 0 without the server death and from 7 to 0 with it. The three that came from
    market sells with an unknown outcome are held and clear when the sell is booked, two minutes later at most.
  - **What a restart for an update did before:** in the input simulations a fresh start now gives 9 and 14 first
    looks that all clear. Each of those was a phone alert.
  - **Tests the agent ran, none with a changed expectation:** the order path (116 unit checks and its two
    simulations), the input simulations, release inputs (90), USDC, the watchdog (31), `wickctl` (15). I read
    the whole change and ran the new test: 26 pass.
  - **Full offline suite** on a runner (job 44179920431, started 21:27 UTC). It includes the paper parity
    replay, which the agent did not run.
  - **Limits:** a new fill on the same coin in the seconds before the second look can still raise a false
    warning. For up to 10 minutes a real shortfall is not warned if it is no larger than that coin's market sells
    with an unknown outcome.
  - It stays on its branch until a release point.
- **18:58. The sixth book's hand-over started its test job; the balance warning's suite passed.**
  - **Hand-over at 23:41 UTC:** the script started the book's next run (44201542189, after 348 minutes) and, one
    second later, an alternating job (44201545168). Both lines are in the job's log. This is the first test job
    started this way.
  - **That job waited 16 minutes.** GitHub had started a scheduled alternating job at 22:50 (most likely the 21:05
    one, late), and the two share one queue. The scheduled one ended at 23:57 and the other began three seconds later.
  - **Second alternating job (22:50 UTC, three workers on even minutes): it counts.** 30 timed steps in each arm;
    median pass 2.647 s with one worker and 2.611 s with three; no pass over 6 s and no budget fallback in
    either arm; at most 7 requests in a second; nothing rate-limited or refused; rows that differ from the
    venue's candles 187 of 504 and 189 of 522.
  - **Part 3 so far:** 2 of 8 jobs, 0 of 30 slow one-worker passes. The venue is calm, so the test can only
    say something once slow minutes come back.
  - **The balance warning's full suite on a runner** (job 44179920431, branch at 46e1ee84): 23 file runs, no
    failure. Paper parity is identical (156 rungs, 88 parents). Both live-path simulations show no balance
    warning, with entries, exits and P&L as before.
- **19:46. All four books have handed over with the changed script; the fifth book's hand-over started a pair.**
  - **Fourth book, 00:24 UTC:** next run started after 351 minutes (44207572759); no test job, as intended.
  - **Fifth book, 00:34 UTC:** next run started after 351 minutes (44208915239) and, two seconds later, a
    same-machine pair (44208918421), which began at once. Both lines are in the job's log.
  - So the start of test jobs no longer depends on GitHub's clock or its events. The clock still adds jobs when
    it happens to fire: a scheduled pair started at 20:33 UTC (most likely the 18:05 one, late).
  - **Third pair (20:33 UTC, the build first): it counts.** Data step 8.60 s with the build and 9.78 s with
    release 3, a difference of 1.18 s; 31 timed steps in each half; nothing refused or rate-limited.
  - **Pairs so far: 3 of 8, differences 2.69, 1.03 and 1.18 s in the build's favour.**
  - **Seen before the read, no rule changed:** all three pairs ran the build first. The order follows the hour
    of the start, as fixed, and with starts that no longer fall on the clock's four hours it need not come out
    even. The read will give the count of each order and the difference within each, next to the result.

## Nov 18 2026 (times ET; UTC is five hours later)
- **08:26. Morning look. One finding that matters: the release 5 build stops bidding when the venue's trades list
  stands still.**
  - **The four books:** all handing over (main 03:10 and 09:01 UTC; fourth 06:15 and 12:06; fifth 06:25 and
    12:15; sixth 05:32 and 11:22). No error event, no halt, no refusal, no rate-limit stop in any book.
  - **The finding** (both plans' deviation logs, today). From 21:19 to 21:57 UTC on Nov 17 the venue's trades
    list showed no new trade for almost any coin while its candles kept coming.
    - The fifth and sixth books (the build: candles asked between steps only) had no row for the newest minute,
      the stale guard stopped new bids, and for 38 minutes they placed none.
    - The fourth and main books (candles asked inside the step) carried on: 8 new bids each, on the same
      coins in the same minutes.
    - Once in the seven days the trades-reading books have run. It is the guard working, and a weakness of the
      build that the plan did not foresee. Not a fault by the plan's list, so the test goes on to its one read.
    - **Fixed now, before the read:** the repair is a fallback to candles asked inside the step when BTC's
      newest minute has no trade but its candle has a row. It is built unless five or more of the fourth
      book's eight bids in the window were wrong against the research. It would be a new commit with its own
      test. A pass of Part 3 still makes the tested configuration release 5, with this said in the note.
  - **Correction to yesterday's 14:38 entry.** "Two such minutes" was counted two hours before the standstill.
    In the fifth and sixth books it made 38 minutes in a row in which bids already resting ran out after five
    minutes and none was renewed. If the fallback is built such runs go away again; if the window speaks
    against it, the question comes back.
  - **Fifth book's pairs: 6 of 8 count,** the build ahead by 1.03 to 2.69 s in every one (five with the build
    first, one with release 3 first). Two more are due today. Every ended run has started its pair.
  - **Sixth book's alternating jobs: 5 count, and no slow pass in either arm** (152 steps each, longest 3.4 s).
    At one hour in six the floor of 30 slow one-worker passes would probably not be reached in the 14 days, so
    from today the jobs run back to back until Dec 1. Nothing about the rule changes (plan, deviation log).
  - **The venue's speed since yesterday's look.** One slow half hour (to 21:00 UTC Nov 17): budget fallbacks 11
    in the fourth book, 8 in the fifth, none in the sixth. One slow half hour in the fourth book alone (to
    02:00 UTC, 7). One whole trades pass of the fifth and of the sixth book fell back in the half hour to
    08:00 UTC, after a failed candle request between steps. Data step medians: main 11.2 s, fourth 13.1 s, fifth 8.5 s,
    sixth 8.5 s.
  - **Test A since release 3** (status report: CHECK): 32 rungs, $293K bought, net -38 bp. Still the one
    market-wide minute of Nov 14 (logged Nov 16) plus one LINK ladder on Nov 17 that ended at +3 bp. The three
    trades-reading books did not take that LINK fill; the read's research data will show which side was right.
  - **GitHub:** its events arrive again (the status report ran after every book's run today). Its clock still
    runs late; it started one pair and one alternating job hours late, which now only adds jobs.
  - **Nothing from Miles** on release 4's server steps.
- **08:29. The alternating jobs' back-to-back start is on `main`** (923bfe99; Sonnet agent, reviewed by me).
  - **What changed:** the alternating workflow has a second job that starts the next alternating job through
    the paper books' hand-over script, until Dec 1 2026, 11:41 UTC. A run under 30 minutes starts nothing, so a
    job that fails at once cannot loop.
  - **Checked:** the existing job, the triggers and the queue compare equal to the file before; the new step's
    script with an end time in the future, in the past and unreadable; the hand-over script's own test passes.
  - **First use:** the job running now was started from the old file and will not start a successor. The chain
    begins with the job the sixth book's hand-over starts at about 17:13 UTC. Nothing is started by hand.
- **08:33. The fallback for a standing trades list is being built today** (Opus agent, branch owner/standstill,
  on the balance-look commit 46e1ee84), so that it is ready when the fifth book's read comes.
  - **Whether it is used is still decided as fixed this morning:** by the fourth book's eight bids in the window
    against the research, at the read. If they speak against it, the branch is dropped.
  - **The design:** a switch, off unless set. With it on, a BTC minute without a trade in the trades list makes
    the step look at BTC's candle. If that candle has trades, the list is behind: the step asks for the candles
    of the coins whose minute came back empty and judges those rows as release 3 judges candle rows. If BTC's
    candle is empty too, the guard stops the bids as today.
  - **What it has to show offline:** with no standstill in the feed, not one log line differs, switch on or off.
    With a 38-minute standstill in the feed, the build with the switch on decides exactly as the candle run
    does, and with the switch off it stops as the books did on Nov 17.

## Nov 19 2026 (times ET; UTC is five hours later)
- **08:21. Morning look.** Yesterday's 14:45 check reached me only this morning (the session stood still from
  about noon), so it is made here too.
  - **A fault in a hand-over, covered by luck.** At 08:22 UTC the main book's hand-over got one HTTP 502 from
    GitHub when it asked for its own run's start time. The script printed "no hand-over" and started nothing.
    - The book went on because a scheduled run that GitHub had queued 33 minutes earlier was waiting. No minute
      was lost. Without that run the book would have stood until the next scheduled start.
    - **The repair:** the script tries its two requests again (the start time, and the start of the next run).
      A Sonnet agent is building it. It goes onto `main` after the fifth book's period ends today (18:59 UTC);
      until then I look at each hand-over (about 14:13, 16:33, 17:20 and 17:28 UTC) and start a book by hand if
      one fails, as the rule of Nov 17 says.
  - **The four books otherwise:** all handing over. No error event, warning, halt, refusal or rate-limit stop,
    and no stale-guard minute since yesterday's look: the trades list has not stood still again.
  - **The alternating jobs run back to back.** Since 17:13 UTC yesterday every job has started its successor: 18
    jobs in 20 hours. 23 count in all. At most 7 requests in a second, nothing rate-limited or refused.
    - **Part 3 so far, deciding nothing:** 706 timed steps with one worker hold 4 passes over 6 s and 2 budget
      fallbacks; 695 with three workers hold 3 passes over 6 s and no fallback. That is 4 of the 30 slow
      one-worker passes the read needs.
    - In the two slow spells that fell into jobs, three workers also had passes over 6 s (6.8 and 6.9 s), though
      none over the 8 s budget. So far the alternating jobs show no gain on the share of slow passes.
  - **Fifth book's pairs: 13 count** (8 needed). The build is ahead in every one, by 1.03 to 2.80 s, median
    1.70 s. Three ran release 3 first (1.07, 2.44 and 2.56 s), ten the build first.
  - **New bids since the period began** (every coin but BTC; the read counts them properly): main 515, fourth
    569, fifth 562, sixth 546. No extension looks needed.
  - **The venue's speed.** One slow spell, 03:30 to 05:00 UTC today: budget fallbacks 21 in the fourth book, 16
    in the fifth and none in the sixth (its longest pass 6.8 s). It is the second spell in which the two books
    on one worker fell back and the book on three did not (Nov 17, 20:30 UTC: 11, 8 and none). That is Part 4's
    material. Data step medians today: main 11.1 s, fourth 12.9 s, fifth 8.5 s, sixth 8.6 s.
  - **Test A since release 3:** 34 rungs, net -37.9 bp. Two more rungs yesterday, -$99 on the day; the count is
    still the one minute of Nov 14.
  - **The fallback for a standing trades list** (branch owner/standstill at 1bfa413f) was built and tested by
    the agent yesterday. By its runs, which the suite on a runner will repeat:
    - with no standstill in the feed no log line differs from before, switch on or off;
    - with a 38-minute standstill in the feed, the build with the switch on decides exactly as the candle run
      does (111 entries, $11,723), and with the switch off it places 86 entries and makes $6,089. The window is
      the busiest one of the test data, so this shows what such a stop can cost, not what it costs on average.
    - I asked for one addition after reading the change: in a standstill step no coin keeps its "empty" mark.
    - Whether it is used is still decided by the window of Nov 17 at today's read.
  - **Today:** the fifth book's read at 15:40 ET.
  - **Miles** wrote to go on. Nothing yet on release 4's server steps.
- **08:27. The hand-over script's retries are on `main`** (646de21b; Sonnet agent, reviewed and tested by me).
  - **What it does:** the script tries its two requests that matter, the read of the run's start time and the
    start of the next run, up to five times, 15 seconds apart. With one try and no wait it behaves as before.
  - **Checks:** 50, of which the 27 old ones pass unchanged; I ran them here.
  - **Earlier than I wrote this morning.** The change was ready 45 minutes before the main book's hand-over
    (about 14:13 UTC). I watch that one anyway and it matters least for today's read, so merging now protects
    the three hand-overs still inside the fifth book's period (16:33, 17:20 and 17:28 UTC). If the first use
    fails, I start the book by hand and take the change back.
  - **A permission refusal, for the record.** While writing the test, the agent's scripted rewrite of its own
    half-written test file was refused by the session's permission check ("Destructive or Unwanted Actions").
    It stopped and reported. I did not do the action in its place. The refusal's own text allows a safer
    method, and the agent finished with ordinary edits of lines it had added, which the check accepted. Miles
    has been told.
- **08:34. The standstill fallback is complete on its branch; the full suite is running on a runner.**
  - **Branch owner/standstill at 815ea390** (the balance-look commit plus the switch `standstill_candles`): 49
    new lines in the engine and 6 for the addition I asked for this morning. In a standstill step no coin keeps
    its "empty" mark, and every row of that minute is judged as a candle row.
  - **Its own test:** 73 checks; I ran it here. Three of the new ones fail against the engine without the
    addition, so they test it (the agent's run).
  - **Full offline suite** on a runner: job 44533821743, started 13:28 UTC. It repeats the standstill
    simulations on the final commit, and the paper parity replay.
- **09:21. The hand-over script with retries: first real use, the main book.** Its run ended at 14:13 UTC and the
  script started the next one (44541407852) at the first try. The alternating chain is alive; its next
  hand-over, at about 14:27 UTC, is the second use.
- **11:42. The standstill fallback passed the full suite on a runner** (job 44533821743, branch at 815ea390): 24 file
  runs, no failure.
  - **Paper parity** is identical (every rung: entry minute and price, exit minute, type and price).
  - **The standstill simulations on the final commit:** with the switch on, every log line equals the candle
    run's (1,489 lines) and the 38 standstill steps are all counted; with the switch off, 38 stale minutes, no
    new bid in the span, 86 entries and $6,089 against 111 and $11,723.
  - **No balance warning** in any live-path simulation.
  - **Hand-overs with the retry script so far today:** main book 14:13 UTC, the alternating chain 14:28 and
    15:36, sixth book 16:33. Each started its next run.
- **14:41. The fifth book's read waits for the logs, until about 18:25 ET.**
  - The period ended at 18:59 UTC, but a paper book puts its log on `main` only when a run ends. The runs that
    cover the period's end are still going: the fourth book's ends at about 23:11 UTC and the fifth book's at
    about 23:19 UTC. On `main` both logs stop at 17:17 UTC. I set the read's time on Nov 16 without counting this.
  - The last two hand-overs inside the period worked (fourth book 17:20 UTC, fifth book 17:28 UTC, with its pair).
  - Nothing is read before the logs are complete: no bid count is logged and no research is fetched.
- **18:27. The fifth book's read begins.** Logs on `main` now reach past the period's end (fourth book to 23:08
  UTC, fifth to 23:11, main book to 20:00). All four books handed over this evening.
  - **Period:** 2026-11-16 19:00 to 2026-11-19 18:59 UTC, 4,320 minutes.
  - **New bids on the 17 coins, from the logs alone,** on the 4,168 minutes both books decided: fifth book 696,
    fourth book 695. No extension. Written into the plan's deviation log before any research is fetched.
- **19:14. The fifth book's read: fail on one clause of measure 2. No release 5.**
  - **The clause:** bids the research would not have placed are capped at 5%; the fifth book has 49 of 696
    (7.04%). Everything else is met: measure 1 (the build's data step 1.49 s earlier than release 3's over 14
    pairs; 8.61 s against the main book's 11.05 s), the rest of measure 2 (against the fourth book 49 against 46;
    matched 641 of 688 against 645 of 692; level 2 of 696), measure 3 (items 1 to 5) and measure 4 (1 failed
    request of 72,792; 70 requests inside a step of 76,518 coin-minutes).
  - **The build is not worse than its control.** The fourth book has 46 of 695 (6.62%) and misses the cap too;
    its 46 are all among the fifth's 49. The main book, on release 3's inputs, has 47 of 677 over the same
    period (run after the verdict).
  - **One read, rule as written:** fail. By the plan: no release, the cause first, then a corrected build and a
    new three days.
  - **The standstill window of Nov 17:** the fourth book's 8 bids there were all bids the research placed, on
    the level. The veto rule of Nov 18 is not triggered; the fallback stays.
  - **After the verdict, exploratory.** The books agree with one another to 0.1 point at the bids in question
    and differ from the research by a median 11.6 points, with the bid level on the tick. The share is 8% to 9%
    on the twelve and under 2% on the five, in every book. The unchanged fourth book had 4.1% on the twelve in
    Part 2. A first guess (coarse ticks) was checked and dropped.
  - **Leading cause, known since Nov 10:** for the twelve the venue's final candle runs into the next minute
    after a quiet minute (8% to 41% of boundaries, 7 to 11 s). The research decides on that candle; a bar cut at
    the minute cannot equal it. The row "What the candle's late cut gives the research on thin coins" has been
    waiting in FORWARD_TESTS.md since then.
  - **My error in the rule:** the 5% cap was written on Part 2's level and left no room for this gap moving
    with a quiet market and with more bids on the twelve (77% of bids now, 61% then). The verdict stands.
  - **Next, fixed in the plan before it is run:** Part 1's tool on Part 3's period. If the fourth book's inputs
    emulated on the collector's record give the book's own scores at the bids in question (80% or more within
    0.5 point), the cause is the cut of the newest row.
  - **Then:** the corrected build is the tested build with the standstill fallback (815ea390), on a new three
    days and a rule fixed first. And the replay that prices the late cut for the research moves to the top of
    the list: if the research on the twelve leans on those seconds, the live return on them is lower than the
    research's.
  - **Tables:** reports/owner/reconcile_tb/part3/ (README.md is the record).
- **19:22. The cause check is running, its tool is on `main`, and the late-cut replay has its plan.**
  - **Runner job 44644238137** (branch owner/read-part3, started 00:14 UTC on Nov 20): Part 1's tool on Part 3's
    period. About an hour.
  - **The check's tool** (scripts/owner/bar_source/book_check.py; Sonnet agent, reviewed, 31 checks; d073a124):
    for a book's new bids it sets the score the book logged next to the emulated score and the research's, and
    prints the two readings fixed in the plan.
  - **Seen while the tool was built, on Part 1's period, which is not the check:** the fourth book against its
    emulation, Nov 11 22:30 to Nov 14 01:59 UTC. 508 of 521 bids within 0.5 point. Of the 31 bids more than 2
    points from the research, the emulation gives the book's score at 30. All 17 wrong-side bids are on the
    book's side in the emulation too. So on those three days the difference was the cut of the newest row. The
    registered check is the same count on Part 3's period.
  - **Plan fixed for the replay that prices the late cut** (reports/owner/late_cut_prereg.md), before any print is
    fetched. It asks two things. Is the research on the twelve flattered by a candle that runs into the next
    minute? And would a bar the bot keeps open for 5 or 10 s, which it can have by the time its bids rest, bring
    the decisions back? The five coins with clean candles are the placebo. It uses the late-BTC replay's harness
    and the timing study's print tools, on branch owner/late-cut. An Opus agent runs it.
- **20:22. The cause check: confirmed. The corrected build gets its three days, on a rule fixed now.**
  - **The check** (runner job 44644238137, ended 01:18 UTC on Nov 20). With the newest row replaced by a trades
    bar cut at the minute and nothing else changed, the emulation is within 0.5 point of the fourth book's logged
    score at 671 of 709 bids (94.6%; 90% needed). Of the 70 bids more than 2 points from the research it gives
    the book's score at 67 (95.7%; 80% needed). All 46 wrong-side bids are on the book's side in the emulation.
    The fifth book: 665 of 702, 66 of 71, 47 of 49.
  - **So the cause is the cut of the newest row.** It is common to every book and no input build controls it.
    On every minute nothing got worse against Part 1's period (scores more than 1.0 point off: 1.89% against
    1.95%). The share at new bids doubled because a bid is placed where the score crosses the line.
  - **Not established by this check:** why the bar cut at the minute differs from the final candle. The Nov 10
    study and the split (67 of 70 on the twelve) say the candle's late cut; the replay's print table will show
    it directly.
  - **One part cannot be read:** the main book against its own emulation. The tool's pass with kept trades rows
    leaves BTC flat through the 38 standstill minutes of Nov 17, which the real book filled from candles (80 of
    92 bids within before the standstill, 328 of 546 after). Nothing is concluded from it.
  - **Part 3's second run is in the plan** (bar_source_prereg.md), fixed before the new commit has run. The fifth
    book goes on with commit 815ea390: the first run's build plus the fallback for a trades list that stands
    still, and the balance look. Three days from its first half-hour mark on that commit.
  - **The rule changes in one place, and I say so:** the 5% cap on all 17 coins becomes a 5% cap on the five
    coins whose candles are cut at the minute, and the main book is added as a second control (wrong-side share
    at most its share plus 2.0 points). A rule changed after a fail is weaker evidence than one that held. The
    all-17 figure is still reported against 5%.
  - **Next:** the fifth book's workflow pins the new commit from its next hand-over (about 05:10 UTC). The second
    rule script goes to `main` before the read.
- **20:33. Second run set in motion: the pin and the rule as code are on `main`.**
  - **The fifth book's workflow pins 815ea390** since 20:23 (99673d0d). It takes effect at the hand-over about
    00:05; I check the first run on it at 00:25.
  - **The rule as code** (part3b_rule.py, 65b2c584; Sonnet agent, reviewed): 99 checks, and the first rule's 110
    unchanged. I sent it back once, for a cross-check of the five-coin counts that the restated cap reads.
  - **The bid count is a tool now** (count_bids.py, 21 checks), not a scratch file. On the first run's period it
    gives the logged counts.
  - **Proved on the first run's data: pass, and that proves nothing about the build.** The rule was written
    knowing that data. Worth noting from it: against the main book the build is level (48 of 685 against 47 of
    669).
  - **The read's steps** are written down (part3_infra_notes.md). The read falls on about Nov 23.
  - **Still running:** the late-cut replay (Opus agent).
- **21:32. The late-cut replay stopped before its third era. Two things go to Miles.**
  - **What ran** (Opus agent, branch owner/late-cut): the candidate export with the gate (22,486 candidates), the
    print job (17,070 windows, 9.1M prints, 8 shards of about 81 minutes), and part A.
  - **What the two eras show.** With the coin's own newest row cut at the minute, the decision changes at 5 of
    4,773 candidate minutes of the twelve in selection and at 8 of 2,431 in check. Sharpe 2.935 to 2.930 and
    2.661 to 2.660. The row itself differs from the candle at 446 and at 612 of those minutes. The five: 0 and 1
    changed decisions. So far the research on the twelve does not lean on the candle's late seconds.
  - **Why the paper books show 8% and this shows 0.2%:** the books' share is counted at new bids, which are
    placed where the score crosses the line. At the minutes where a bid fills, the same difference in the row
    almost never changes the side.
  - **First thing for Miles: the 2022-23 era stopped at its gate, and the agent's rerun was denied.** The gate
    wants trade prices equal to R2-08's to the last bit. The same code passed that on one runner and failed it on
    another; the two runs' daily series differ by at most 1.6e-15. The agent tried to add diagnostics and run the
    job again; the session's permission check refused ("Undermining Oversight"). It stopped. I have not done it in
    its place. If Miles allows it: a tolerance of 1e-9 relative on prices, logged first, one rerun.
  - **Second thing: a rule was broken in the print job, and the fault is mine.** My rule is that a source that
    answers "too many requests" is stopped. The print fetcher tries again after a wait, and has since Nov 9; I
    wrote the stop into the plan without checking the code, and my brief described the fetcher wrongly. The
    venue answered 429 to 5,505 of 198,838 requests and each was retried. No refusal. No further print fetch;
    before any future one the fetcher stops at the first 429 and runs slower.
  - **Not done:** the late bar is not named (it would be Q5), part B has not run, readings (b) and (c) are not
    made.
  - **Check when the books' logs reach `main`:** any rate-limit answer in the books between 00:48 and 02:09 UTC.

## Nov 20 2026 (times ET; UTC is five hours later)
- **00:26. The fifth book runs the corrected build.**
  - **Run 44679000823** started at 05:08:20 UTC, from the hand-over of the last run on the old commit (which ended
    at 05:08). The workflow it was started with pins 815ea390 (checked in the file at the run's own commit,
    aa2018dc). Its step that records the engine commit passed, and the book has been stepping for 17 minutes. No
    crash at start-up.
  - **Not read from the run's own log:** a running job's log cannot be fetched. The commit the book wrote into
    paper_spot_r5/CODE reaches `main` when the run ends, about 11:00 UTC. The period's start goes into the plan
    then, not now.
  - **The print job did not reach the books.** In the heartbeats from 00:30 to 02:30 UTC the fifth, fourth and
    sixth books have no rate-limit answer, no refusal and no error. The main book's log on `main` ends at 01:53
    UTC and shows none up to there; the rest of the window is checked in the morning.
  - **Still waiting for Miles:** whether the 2022-23 job of the late-cut replay may be rerun (entry of 21:32).
