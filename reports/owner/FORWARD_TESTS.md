# Forward tests: every open question that only new data can answer (Nov 10 2026)

One row per test. A test is read once, on the date and by the rule fixed before its data existed. Nothing here is
decided on a backtest. The rules were written in the documents named in the last column; this file only collects
them.

## The incumbent, live

| Test | What it decides | Read when | Pass rule | Status | Source |
|---|---|---|---|---|---|
| A. Spot paper book, $250K | Whether the machinery and the fill frequency match the research | At least 3 weeks and 60 rungs: no earlier than Nov 27 2026 | No unexplained errors; every rung closes by its rule; 1-6 rung fills a day; mean net per dollar above 0 | Running since Nov 6. See PAPER_STATUS.md and the two notes below the table | bot/spot/README.md |
| B. Live pilot, $10K | Whether real orders fill like paper | At least 3 weeks and 50 rungs | Live fills on at least 70% of the paper bot's fills; mean live result before fees within 25 bp of paper; no balance warnings. Owner's reading of "same fill", fixed Nov 10 before the pilot: the same coin within two minutes either side (see the note below) | Miles's to start | bot/spot/README.md; this file |
| C. Live, $100K (up to $250K) | Capture share, the largest unmeasured number | 6-8 weeks | Capture share at least 0.25; mean net above 0 after 150 rungs | After B | bot/spot/README.md |
| Standing stop | Whether to stop | Any time after 150 rungs | Stop and review if mean net per dollar bought is below 0 | Standing | bot/spot/README.md |
| Idle cash as USDC (ladder v5, C4) | Whether Coinbase pays rewards on this account's USDC, and on cash held by resting bids | One weekly or monthly payout after switching | Rewards at least half of expectation B (free cash only); stop on any rejected -USDC order, a program change, or USDC below 0.997 for 15 minutes | Needs the account's eligibility and `usdc-check` | reports/ladder_v5_prereg.md, bot/spot/run.py |

**Two notes on the paper books (Nov 10 2026).**
- **They ran in real time about 70% of the time.** GitHub's run history shows runs for 66.4 of the 92.0 hours
  from the first run to Nov 10 18:30 UTC (72%), and for about 54% since Nov 8 12:25 UTC. The main book's own log
  holds less: 60.5 of the 87.0 hours to its last event (69.5%), because one run on Nov 7 never saved its log.
  GitHub drops scheduled runs. In a gap the bot places no new bids; when it restarts it only settles what was
  already open. Fills per calendar day therefore understate the rate while the bot is running (PAPER_STATUS.md
  shows both). Release 2 adds a hand-over so each run starts the next. The hand-over worked on its first two real
  runs (Nov 11, 07:37 and 13:28 UTC).
- **The main book and W2 lost their log for Nov 11, 01:47 to 07:37 UTC.** Their job and the third book's pushed to
  `main` in the same second, and a faulty retry line ended the commit step on the first rejected push. Both books
  went on at 07:37 from the 01:47 state, so those hours count as a gap. The third book's log is whole. The step is
  fixed and tested (bot/spot/deploy/paper_commit.sh, on `main` since Nov 11 13:42 UTC). The run that began at 13:28
  UTC still has the old step.
- **Rung fills are above rule A's band when counted per running day:** 21 rungs in 60.5 live hours is 8.3 a day,
  against 1 to 6 (5.8 per calendar day). The reconciliation (reports/owner/reconcile/README.md) shows it was the
  market, not the fault: on final candles the research would have had 16 first-bid fills in the same live minutes,
  against the bot's 13. Net per dollar so far is 81 bp.
- **Their BTC input is known to be late.** In a two-hour probe the bot's own BTC candle request returned an old
  cached copy every minute (reports/owner/candle_probe/README.md). The books now count it themselves: on Nov 11,
  07:43 to 13:00 UTC, the main book had no BTC row for the minute just closed in 279 of about 320 minutes. The main book and W2 keep that behaviour until
  the "verified inputs" test below is read, so their results so far and until then carry that fault.

**Note on item 6 of the "verified inputs" rule (amended Nov 10 2026, 21:14 ET; its second part tightened at 21:23 ET on the same data).**
- As first written, item 6 asked a material-error share of at most 1% of all six listed coins.
- The collector's first 4.3 hours (21:44 to 02:00 UTC, a quiet US evening) show, for the trades bar: BTC, ETH, SOL and
  XRP materially off in 0% to 0.9% of minutes, LTC in 1.5% to 1.7%, ZEC in 1.7% to 5.2%. Their first-seen candles
  were materially off far more often: BTC about 70%, ETH, SOL and XRP 16% to 29%, LTC and ZEC 18% to 24%.
- The trades bar was also exactly equal to the final candle more often: 82% to 98% of minutes for the five coins
  other than BTC, against 48% to 73% for their first-seen candles.
- Held to 1%, LTC and ZEC would fail and go back to a source that is worse on both measures. The question the item
  should answer is which source is closer to the final candle, so for every listed coin but BTC it now compares the
  two, on both measures. BTC keeps the 1% bar, because every bid level reads it.
- The amendment was made about half an hour after the third book's first run began. The collector's record seen by
  then was those 4.3 hours, of which about ten minutes fall inside the book's days. None of the book's own data had
  been read.
- It is also a deviation from the candle clock plan, which asks class B's 1% on the collector's daily record before
  a coin's trades bar is relied on. It is entered in that plan's deviation log.

**Note on item 7 of the "verified inputs" rule (added Nov 10 2026, 21:29 ET).**
- As first written, the rule tested the bot's inputs (items 1 to 6) and reported the reconciliation for the record.
  Nothing in it tested the bot's decisions, which are what the release is meant to bring closer to the research.
- Item 7 asks that the third book's bids be closer to the research than the main book's on the two measures where the
  first reconciliation found the fault: on Nov 6 to 10, 40% of the main book's new bids were more than 5 bp from the
  research level, and 19% had a research score on the other side of the threshold. If the fix works, both shares
  should fall to a few percent in the third book.
- "Or below 5% in both" covers the case where the main book's own inputs happen to be good on those days, so that
  there is no fault to compare against.
- It was added about 40 minutes after the third book's first run began, before either book's log for these days had
  been read. It can only make the rule harder to pass.

**Note on rule B (fixed Nov 10 2026, before any pilot data).**
- The timing study (reports/owner/timing/, 14.1M trade prints) shows that the live bot's order timing alone fills 83-90%
  of the research's first bids in the same minute and 88-94% within two minutes. Trade prints confirm 93-96.5% of the
  candle-based fills.
- With a same-minute match, a pilot with perfect capture would be expected at about 77-86%, too close to the 70% bar to
  say anything about capture. With a two-minute window it would be expected at about 82-90%. The 70% bar stays.
- The same-minute rate is reported as well at the read.

## Challengers running or registered

| Test | What it decides | Read when | Pass rule | Status | Source |
|---|---|---|---|---|---|
| W2 rung weights (1:1:2), paper | Whether weighting the 8-sigma rung earns more per dollar without deeper drawdowns | With test A, then at each later read | No fixed rule was registered. Owner's rule, set Nov 10 with three days of data seen: adopt only if, after at least six months, its net P&L is at or above the main book's and its worst marked drawdown is within 1.1x. It is judged on return per dollar, because a Sharpe gain of this size cannot be confirmed in under several years | Running since Nov 7 | wick v4; this file |
| Verified inputs (release 2), third paper book `paper_spot_tb` | Whether the new input mode becomes the default for the paper books and the live bot. It is a fidelity fix, so it is not judged on P&L | Once, after its first three full days of real-time running (at least 4,000 minutes) | All of: (1) the listed coins (BTC, ETH, SOL, XRP, LTC, ZEC) got a verified trades bar in at least 99% of coin-minutes; (2) no refusal and no rate-limit stop from the venue; (3) the data step finished at a median of 13 s or less after the minute, and its 30-minute maximum was 20 s or less in at least 95% of heartbeats; (4) no error events from the new code; (5) rows still unconfirmed three to six minutes after their minute are at most 1% of coin-minutes; (6) on the collector's record for the same days, against the final candle (the candle probe's measures 2 and 3): (a) BTC's trades bar is materially off in at most 1% of minutes, over the days together; (b) for every other listed coin, on every day, the trades bar is materially off less often and exactly equal more often than that coin's own first-seen candle. A day is a UTC date with at least 12 hours inside the test period and at least 720 compared minutes for the coin; at least two such days are needed, and item 6 waits for them if the collector has fewer (item 6 was amended on Nov 10; see the note above this table); (7) on the reconciliation of both books over the minutes both were live (reports/owner/paper_reconcile_plan.md, the repeat): the share of new bids more than 5 bp from the research level, and the share of new bids whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both. At least 200 new bids in each book are needed, and item 7 waits for them if there are fewer (item 7 was added on Nov 10; see the second note above this table). On a pass, release 3 switches the main book, W2 and the live bot together. On a fail of items 1 to 5, of 6(a) or of item 7, the fault is fixed and the three days start again. A coin that fails 6(b) is taken off the list at release 3 without restarting the days; it stays on the candle path, which is what the books do today. Fills and P&L of the two books, and the reconciliation's other two measures (bids in common, fills in common), are reported side by side for the record only | Rule fixed Nov 10 2026, before the book's first run; item 6 amended at 02:14 UTC on Nov 11, about half an hour into that run, and item 7 added at 02:29 UTC (notes above this table). Release 2 was merged on Nov 10 at 21:36 UTC. The book's first run began at 01:47 UTC on Nov 11 (run 42906647104) and its first step was at 01:52 UTC, so the three days end at 01:52 UTC on Nov 14. First interim look at the reconciliation: reports/owner/reconcile_tb/i1/README.md. Item 6 is read from the collector's trades-bar stream (on `main` since Nov 10; scripts/forward/input_checks.py) | reports/owner/RELEASES.md; this file |
| The newest bar of the twelve coins on the candle path | Which source brings the bot's decisions closest to the research: the candle answer as first seen, or a bar built from trades | Not before the three-day read above | No rule yet. The candle clock plan's rule holds: the twelve stay on the candle answer. A coin changes source only by a comparison in units of the bot's decisions (armed or not, and the bid level, with each source as the newest bar, against the same on final candles), under a plan written before the collector's record is read for it | Registered Nov 10 2026, 21:23 ET. In the collector's first 4.3 hours the trades bar was materially off less often than the first-seen candle for all twelve (4% to 42% against 19% to 47%) and exactly equal to the final candle less often for nine of them, so the two error shares do not settle it. A rule written at 21:14 ET on the material-error share alone was withdrawn at 21:23 ET (LOG.md) | reports/owner/candle_clock_prereg.md; this file |
| Deeper ladders G1 (4/5/7/10 sigma) and G2 (4/5/6/8/10/12) | Whether more depth holds on new data | Once, on Nov 10 2026 - Mar 31 2027 | Positive Sharpe difference, the minute book at or above 0, risk within 1.1x | Registered; data accruing | reports/explore/prospective_prereg.md (branch explore/v1) |
| Alt-perp carry on published funding (hunt 3) | Whether a carry sleeve rivals R2-08 | Once, Feb 1 2027 (Dec 1 - Jan 31) | Its own registered bar, at 1x and 2x costs; published funding within 2 bp a day of the rebuild | Needs published funding logged from Nov 15: the forward collector's `cfm` stream records it | hunt 3's prospective pre-registration (not on GitHub; summarised in the findings doc) |
| Perp wick catcher, paper ($10K, v1 and R2-08) | Whether perp-only wicks are fillable | About 70 trades in the R2-08 book; 60 in each for the comparison | Stop R2-08 if realistic net per trade is below -12 bp after about 70 trades; back to v1 if v1's is higher after 60 in each | Running since Nov 6; two fills each by Nov 10, over 3.9 days (R2-08) and 4.2 days (v1); PAPER_STATUS.md has the current count. Research rates on perp prices are 0.8 fills a day (R2-08) and 1.05 (v1), so the books are a little below the expected count and not unusually so. Owner's watch rule, set Nov 10: review the perp fill model if either book has 6 or fewer fills after 21 days | wick v2 lab; bot/README.md; this file |
| H1 perp-only wicks at 5-6 pm ET | Whether the edge survives the real fee | After one authenticated order preview | Forward-test for 3 months only if the all-in fee is at or below $0.13 a contract | Needs the fee preview | edge hunt |
| Sizing by the model's margin (C2a) and sweep depth (C7b) | Whether either survives on new data | A re-test on data after Nov 5 2026 | Ladder v5's gates | Not scheduled; low priority after the sizing lab | ladder v5 |

## Waiting for data that is only now being collected

| Test | What it decides | Read when | Status |
|---|---|---|---|
| Open interest and funding as model inputs | Whether leverage state adds information the candles lack | Pre-register when about a year of the collector's `hl` and `cfm` streams exists. Possible shortcut: Hyperliquid publishes history (asset contexts and book snapshots, from 2023) in an S3 bucket where the reader pays for transfer, updated about monthly (hyperliquid.gitbook.io/hyperliquid-docs/historical-data). With AWS keys as repository secrets the test could be registered on that history and read forward. The files' fields and time step are not checked yet | Collector started Nov 10 2026. The shortcut needs Miles's AWS keys; cost is cents |
| Order-book depth as a model input and as a capture-share estimate | Whether a thin book under the bid predicts the rebound, and how much of the volume is ours to take | Pre-register when about a year of the `book` stream exists; the capture-share use can be read with test C | Collector started Nov 10 2026 |
| Candles as the bot sees them | Whether the bot decides on finished candles | Once, after 14 full days of the `candles` stream. Rule fixed Nov 10, before any data: count the coin-minutes where, at the first fetch after the minute closes, the candle is missing or its close differs from the final close by more than half of that coin's one-minute sigma. Above 2% of coin-minutes, a study of the cost is pre-registered (the timing study's method, with the levels as the bot saw them). At or below 2%, the step time stays | Collector started Nov 10 2026. Its first two hours are far above 2% (about 15% of coin-minutes; BTC missing at first sight in about half), and the probe found the cause for BTC and ETH (old cached copies). The read stands as registered. The cost was not left to wait for it: a replay of the research with BTC one and two minutes late put it at about -0.5 / +0.2 / -0.7 Sharpe by era (reports/owner/late_btc/README.md) |
| What the candle's late cut gives the research on thin coins | For the twelve coins, the final candle of a quiet minute often holds trades from the first seconds of the next (candle clock study). The research decides on that candle, so it can see a few seconds further than a live bot. How much of the research result on those coins rests on that is not known | Planned: a replay on the trade prints of signal lab 2, with each decision's newest bar cut at the minute, pre-registered before it runs | Not started |
| History-trained model at R2-08's selectivity | Whether 2021-23 history helps ranking forward | Optional shadow log at the next retrain | Not built |

## Closed
- Candle probe (Nov 10 2026): by its rule no source is usable at 25 s or less (reports/owner/candle_probe_prereg.md,
  with the logged deviation). Followed by the candle clock study (candle_clock_prereg.md) and release 2.
- Candle clock study (Nov 10 2026): no coin has a steady offset. Six coins are cut at the minute or nearly so (a
  material-error share of 1% or less) and take their newest bar from trades in release 2's new mode; twelve stay on the candle answer (candle_clock_prereg.md, "Result").
- Live order timing (Nov 10 2026): the bot's timing stays as built. Every realistic timing is within a few percent of
  the research assumption in pooled P&L, and the study cannot rank them (reports/owner/timing_prereg.md, "Final
  reading").
- The model on historical data: three rounds, no change (findings doc).
- Trade-print features: no change (signal lab 2). A live shadow log of them is not worth building.
