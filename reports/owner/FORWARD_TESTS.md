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
- **The main book and W2 lost their log twice on Nov 11: 01:47 to 07:37 UTC and 13:28 to 19:18 UTC.** Their job
  and the third book's end in the same second and push to `main` together, and a faulty retry line ended the commit
  step on the first rejected push. Each time both books went on from the state of the run before, so those 11.7
  hours count as gaps. The third book's log is whole. The step is fixed and tested (bot/spot/deploy/paper_commit.sh,
  on `main` since Nov 11 13:42 UTC); the run that began at 19:18 UTC is the first paper run that has it.
- **The fourth book lost its first run's log (Nov 11, 16:15 to 22:05 UTC).** Every push failed with "could not read
  Username": the runner's token was not accepted for more than 76 s. The cause is probably on GitHub's side; that is
  not proven. The commit step now retries over four minutes, limits every remote call to 45 s and keeps a rescue
  branch as the last resort (on `main` since Nov 12 13:44 UTC). Every paper run that began after the Nov 11 fixes
  has pushed its log and started the next run.

**Release 3 is on `main` since Nov 14 2026, 10:12 ET.** The main book and W2 take it at their next run, at about 17:20 UTC on Nov 14. Test A's count starts with that run; the status report shows it once the start time is on file (reports/owner/test_a_start.json).

**What release 3 does to tests A, B and W2 (fixed Nov 13 2026, 08:48 ET, before the third book's read).**
- **Test A starts again at release 3.** Its three weeks and 60 rungs are counted from the main book's first run on
  the new inputs. Until then the book bid from a BTC row one minute late in most minutes (about a third of its bids
  more than 5 bp from the research level) and ran about 70% of the time, so its fills are not the strategy's. The
  record before release 3 stays in the log and is reported apart. That record is favourable so far (35 rungs, 76 bp
  net per dollar by Nov 13), so this sets aside a good number, not a bad one.
- **The W2 comparison goes on unchanged.** W2 and the main book switch together and have had the same inputs in
  every minute, so the comparison stays like for like.
- **Test B, the pilot, compares the live bot with the main book from the pilot's start,** both on release 3 or
  later.
- If the read fails, none of this applies until a later release 3.
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
| Verified inputs (release 2), third paper book `paper_spot_tb` | Whether the new input mode becomes the default for the paper books and the live bot. It is a fidelity fix, so it is not judged on P&L | Once, after its first three full days of real-time running (at least 4,000 minutes) | All of: (1) the listed coins (BTC, ETH, SOL, XRP, LTC, ZEC) got a verified trades bar in at least 99% of coin-minutes; (2) no refusal and no rate-limit stop from the venue; (3) the data step finished at a median of 13 s or less after the minute, and its 30-minute maximum was 20 s or less in at least 95% of heartbeats; (4) no error events from the new code; (5) rows still unconfirmed three to six minutes after their minute are at most 1% of coin-minutes; (6) on the collector's record for the same days, against the final candle (the candle probe's measures 2 and 3): (a) BTC's trades bar is materially off in at most 1% of minutes, over the days together; (b) for every other listed coin, on every day, the trades bar is materially off less often and exactly equal more often than that coin's own first-seen candle. A day is a UTC date with at least 12 hours inside the test period and at least 720 compared minutes for the coin; at least two such days are needed, and item 6 waits for them if the collector has fewer (item 6 was amended on Nov 10; see the note above this table); (7) on the reconciliation of both books over the minutes both were live (reports/owner/paper_reconcile_plan.md, the repeat): the share of new bids more than 5 bp from the research level, and the share of new bids whose research score is on the other side of the threshold, are each lower in the third book than in the main book, or below 5% in both. At least 200 new bids in each book are needed, and item 7 waits for them if there are fewer (item 7 was added on Nov 10; see the second note above this table). On a pass, release 3 switches the main book, W2 and the live bot together. On a fail of items 1 to 5, of 6(a) or of item 7, the fault is fixed and the three days start again. A coin that fails 6(b) is taken off the list at release 3 without restarting the days; it stays on the candle path, which is what the books do today. Fills and P&L of the two books, and the reconciliation's other two measures (bids in common, fills in common), are reported side by side for the record only | **Read on Nov 14 2026: pass, with LTC off the list.** Items 1 to 5 meet on the log cut at the period's end (4,318 minutes; 24,252 of 24,252 trades bars verified; data step median 10.1 s). Item 6: BTC's trades bar materially off in 6 of 2,938 compared minutes (0.20%); ETH, SOL, XRP and ZEC better than their own candles on all three days; LTC not on Nov 13, so it leaves the list. Item 7, on 3,557 common minutes: new bids more than 5 bp from the research level 9 of 550 against 360 of 715 in the main book; bids the research would not have placed 23 of 550 against 153 of 715. Record: reports/owner/reconcile_tb/read/README.md. Release 3 was merged on Nov 14 at 10:12 ET with BTC, ETH, SOL, XRP and ZEC on the list (RELEASES.md). The book runs on unchanged until Part 2 of the bar-source plan is read. Rule fixed Nov 10 2026, before the book's first run; item 6 amended at 02:14 UTC on Nov 11, about half an hour into that run, and item 7 added at 02:29 UTC (notes above this table). Release 2 was merged on Nov 10 at 21:36 UTC. The book's first run began at 01:47 UTC on Nov 11 (run 42906647104) and its first step was at 01:52 UTC, so the three days end at 01:52 UTC on Nov 14. Interim looks at the reconciliation, which decide nothing: reports/owner/reconcile_tb/i1/README.md and i2/README.md. The second (Nov 12, 1,361 common minutes): bids more than 5 bp from the research level 82 of 229 in the main book and 0 of 159 in the third; wrong-side bids 39 of 229 and 5 of 159; item 7 waits for 41 more bids in the third book. Item 6 is read from the collector's trades-bar stream (on `main` since Nov 10; scripts/forward/input_checks.py, then scripts/owner/tb_rule6.py). Item 7's period and commands are in reports/owner/paper_reconcile_plan.md, "How the repeat is run" (it ends with the decision minute 01:52 UTC on Nov 14) | reports/owner/RELEASES.md; this file |
| The newest bar of the twelve coins on the candle path | Which way of filling a coin's rows brings the bot's decisions closest to the research: the candle answer as first seen, or a trades bar for the newest minute that the venue's candle replaces afterwards | Part 1 (offline, every minute): on the collector's record of Nov 11 02:00 to Nov 14 02:00 UTC. Part 2 (a fourth paper book, all 18 coins on the new way, run from a branch): once, after three full days alongside the third book and 300 new bids on the twelve in each | Fixed in reports/owner/bar_source_prereg.md and its deviation log. The new way is proposed for the next release if the fourth book's wrong-side share on the twelve is strictly lower than the third book's, its matched share is not lower, its level share is under 5% and items 1 to 5 hold for it. A single coin stays on candles if Part 1 has its score-miss share higher on the new way over the three days and on two of them | Plan fixed Nov 11 2026, 08:50 ET; amended 09:17 ET on the tool's development run, before any registered minute was read: keeping trades rows for good is dropped, because it puts the bid level off in about 9% of minutes. The engine option is on branch owner/engine-c (commit 58eba8b, pinned in the fourth book's workflow; its item 3 median bar is 15 s, set before its first run). The fourth book's first run (16:15 UTC on Nov 11) lost its log to a failed push, so the book's record begins with its second run: first event at 22:25 UTC and first decisions at 22:30 UTC on Nov 11 (run 43110721127). Its three days beside the third book are 22:30 UTC on Nov 11 to 22:29 UTC on Nov 14, and the read is on Nov 15, once both logs reach that minute (the plan's deviation log, Nov 12). The rule is code since Nov 12, before any read (scripts/owner/bar_source/part2_rule.py). First numbers, which decide nothing: reports/owner/reconcile_tb/i2/README.md. Until the read, the candle clock plan's rule holds: the twelve stay on candles | reports/owner/bar_source_prereg.md |
| Deeper ladders G1 (4/5/7/10 sigma) and G2 (4/5/6/8/10/12) | Whether more depth holds on new data | Once, on Nov 10 2026 - Mar 31 2027 | Positive Sharpe difference, the minute book at or above 0, risk within 1.1x | Registered; data accruing | reports/explore/prospective_prereg.md (branch explore/v1) |
| Alt-perp carry on published funding (hunt 3) | Whether a carry sleeve rivals R2-08 | Once, Feb 1 2027 (Dec 1 - Jan 31) | Its own registered bar, at 1x and 2x costs; published funding within 2 bp a day of the rebuild | Needs published funding logged from Nov 15: the forward collector's `cfm` stream records it | hunt 3's prospective pre-registration (not on GitHub; summarised in the findings doc) |
| Perp wick catcher, paper ($10K, v1 and R2-08) | Whether perp-only wicks are fillable | About 70 trades in the R2-08 book; 60 in each for the comparison | Stop R2-08 if realistic net per trade is below -12 bp after about 70 trades; back to v1 if v1's is higher after 60 in each | Running since Nov 6; two fills each by Nov 10, over 3.9 days (R2-08) and 4.2 days (v1); PAPER_STATUS.md has the current count. Research rates on perp prices are 0.8 fills a day (R2-08) and 1.05 (v1), so the books are a little below the expected count and not unusually so. Owner's watch rule, set Nov 10: review the perp fill model if either book has 6 or fewer fills after 21 days. The books ran about 62% of the time: besides dropped schedules, every scheduled run that waited behind another started from an old copy of the books and lost its log (found and fixed Nov 11; LOG.md), so the 21 days are days of the calendar, with fewer running days behind them. Since Nov 11, 19:39 UTC, each run starts the next, as in the spot workflows | wick v2 lab; bot/README.md; this file |
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
