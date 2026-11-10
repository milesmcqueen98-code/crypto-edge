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
  - A study of the cut was planned before its data (candle_clock_prereg.md, 13:30) and run.
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
  - **The trades are not late.** No material error for BTC, ETH, SOL, XRP or ZEC. The errors sit in PEPE, ONDO and
    DOGE: trades near the minute boundary and one-tick differences.
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
  - **No coin has a steady offset.** BTC, ETH, SOL, XRP, LTC and ZEC are cut at the minute: the trades bar's
    material-error share against the final candle was 0 to 0.6% in the last three hours.
  - **The other twelve run late in 8% to 41% of boundaries,** by a median of 7 to 11 s, mostly after quiet minutes
    (about 54% after a minute with 5 trades or fewer, about 2% after more than 50). No offset fixes that.
  - **About 5% of minutes, the same ones for nearly every coin, have a final candle that leaves out trades** listed in
    the public trades (BTC 14:05 UTC: about 3.4 in the candle, 13.4 in the trades). The trades list has no gaps.
  - Joined with the collector for 16:06 to 17:52 UTC: for the six, the trades bar matched the final candle in 97% or
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
