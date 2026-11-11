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
