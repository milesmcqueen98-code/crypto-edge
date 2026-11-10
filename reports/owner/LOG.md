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
- **Perp paper books: one fill each in about 3.5 days is not a signal yet.** The research rate on perp prices is 0.8
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
    whole ladder, an added one counts its first rung only; about eleven ladders decide 2022-23). Nothing is built on
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
- **Collector storage:** 9.8 MB a day measured. The VM's clone is shallow, sparse and single-branch, so the data
  branch does not reach it. Lossless trims first, target about 6 MB a day.
- **10:40. Timing study closed: the bot's timing stays as built.**
  - Like-for-like valuation (whole ladder for every first bid, 4.8M deep prints): the live timing is +1.9% / -11.9% /
    -11.9% against the research assumption (pooled -5.1%); fast re-pricing is -3.8% / +7.1% / +11.1% against the live
    timing (pooled +2.6%).
  - **Deviation 4:** the two-era condition is met for fast re-pricing, and nothing is built on it. The live bot with
    calls 1.5 to 2.5 s faster (P1a) beats the central case by more than fast re-pricing does (pooled +6.3%), and the
    slower-call case is also slightly ahead. The order by P&L is not the order of speed, so the measure cannot rank
    timings: two seconds move 10-17% of first bids to other minutes and a few dozen ladders decide each era.
  - What holds: every realistic timing is within a few percent of the research assumption (pooled +0.9% to -5.1%);
    match rates of 83-90% in the same minute and 88-94% within two minutes; fills are spread evenly in the minute.
  - **Rule B's reading fixed before the pilot:** a paper fill counts as matched when the live bot fills the same coin
    within two minutes either side. The 70% bar stays.
  - Queued for the next engine release: the heartbeat records when cancels and new bids finish each minute.
- **10:36. Probe deviation, before data:** BTC added. The bid level of every coin is the coin's price 60 minutes ago
  moved by beta times BTC's return to the newest close, less four sigma (edge/wick.py `levels`). So BTC's newest
  candle is the input whose lateness moves every level.
