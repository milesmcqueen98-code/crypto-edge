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
