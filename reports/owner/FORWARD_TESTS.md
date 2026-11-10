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
- **They ran in real time about 72% of the time** from their first run to Nov 10 18:30 UTC (66.4 of 92.0 hours), and
  about 54% since Nov 8 12:25 UTC. GitHub drops scheduled runs. In a gap the bot places no new bids; when it
  restarts it only settles what was already open. Fills per calendar day therefore understate the rate while the bot
  is running. Release 2 adds a hand-over so each run starts the next.
- **Their BTC input is known to be late.** In a two-hour probe the bot's own BTC candle request returned an old
  cached copy every minute (reports/owner/candle_probe/README.md). The main book and W2 keep that behaviour until
  the "verified inputs" test below is read, so their results so far and until then carry that fault.

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
| Verified inputs (release 2), third paper book `paper_spot_tb` | Whether the new input mode becomes the default for the paper books and the live bot. It is a fidelity fix, so it is not judged on P&L | Once, after its first three full days of real-time running (at least 4,000 minutes) | All of: (1) the listed coins (BTC, ETH, SOL, XRP, LTC, ZEC) got a verified trades bar in at least 99% of coin-minutes; (2) no refusal and no rate-limit stop from the venue; (3) the data step finished at a median of 13 s or less after the minute, and its 30-minute maximum was 20 s or less in at least 95% of heartbeats; (4) no error events from the new code; (5) rows still unconfirmed three to six minutes after their minute are at most 1% of coin-minutes; (6) on the collector's record for the same days, each listed coin's trades bar has a material-error share of at most 1% against the final candle (the candle probe's measure 3). On a pass, release 3 switches the main book, W2 and the live bot together. On a fail, the fault is fixed and the three days start again. Fills and P&L of the two books are reported side by side for the record only | Rule fixed Nov 10 2026, before the book's first run. Starts when release 2 is merged. Item 6 needs a trades-bar stream in the collector, not built yet | reports/owner/RELEASES.md; this file |
| Deeper ladders G1 (4/5/7/10 sigma) and G2 (4/5/6/8/10/12) | Whether more depth holds on new data | Once, on Nov 10 2026 - Mar 31 2027 | Positive Sharpe difference, the minute book at or above 0, risk within 1.1x | Registered; data accruing | reports/explore/prospective_prereg.md (branch explore/v1) |
| Alt-perp carry on published funding (hunt 3) | Whether a carry sleeve rivals R2-08 | Once, Feb 1 2027 (Dec 1 - Jan 31) | Its own registered bar, at 1x and 2x costs; published funding within 2 bp a day of the rebuild | Needs published funding logged from Nov 15: the forward collector's `cfm` stream records it | hunt 3's prospective pre-registration (not on GitHub; summarised in the findings doc) |
| Perp wick catcher, paper ($10K, v1 and R2-08) | Whether perp-only wicks are fillable | About 70 trades in the R2-08 book; 60 in each for the comparison | Stop R2-08 if realistic net per trade is below -12 bp after about 70 trades; back to v1 if v1's is higher after 60 in each | Running since Nov 6; one fill each in 3.3 days (R2-08) and 3.7 days (v1). Research rates on perp prices are 0.8 fills a day (R2-08) and 1.05 (v1), so this is not unusual yet (chance about 0.26 and 0.10 over those days if fills were independent). Owner's watch rule, set Nov 10: review the perp fill model if either book has 6 or fewer fills after 21 days | wick v2 lab; bot/README.md; this file |
| H1 perp-only wicks at 5-6 pm ET | Whether the edge survives the real fee | After one authenticated order preview | Forward-test for 3 months only if the all-in fee is at or below $0.13 a contract | Needs the fee preview | edge hunt |
| Sizing by the model's margin (C2a) and sweep depth (C7b) | Whether either survives on new data | A re-test on data after Nov 5 2026 | Ladder v5's gates | Not scheduled; low priority after the sizing lab | ladder v5 |

## Waiting for data that is only now being collected

| Test | What it decides | Read when | Status |
|---|---|---|---|
| Open interest and funding as model inputs | Whether leverage state adds information the candles lack | Pre-register when about a year of the collector's `hl` and `cfm` streams exists. Possible shortcut: Hyperliquid publishes history (asset contexts and book snapshots, from 2023) in an S3 bucket where the reader pays for transfer, updated about monthly (hyperliquid.gitbook.io/hyperliquid-docs/historical-data). With AWS keys as repository secrets the test could be registered on that history and read forward. The files' fields and time step are not checked yet | Collector started Nov 10 2026. The shortcut needs Miles's AWS keys; cost is cents |
| Order-book depth as a model input and as a capture-share estimate | Whether a thin book under the bid predicts the rebound, and how much of the volume is ours to take | Pre-register when about a year of the `book` stream exists; the capture-share use can be read with test C | Collector started Nov 10 2026 |
| Candles as the bot sees them | Whether the bot decides on finished candles | Once, after 14 full days of the `candles` stream. Rule fixed Nov 10, before any data: count the coin-minutes where, at the first fetch after the minute closes, the candle is missing or its close differs from the final close by more than half of that coin's one-minute sigma. Above 2% of coin-minutes, a study of the cost is pre-registered (the timing study's method, with the levels as the bot saw them). At or below 2%, the step time stays | Collector started Nov 10 2026. Its first two hours are far above 2% (about 15% of coin-minutes; BTC missing at first sight in about half), and the probe found the cause for BTC and ETH (old cached copies). The read stands as registered. The cost study is not waiting for it: a replay of the research with BTC held one and two minutes late is planned once release 2 is merged |
| History-trained model at R2-08's selectivity | Whether 2021-23 history helps ranking forward | Optional shadow log at the next retrain | Not built |

## Closed
- Candle probe (Nov 10 2026): by its rule no source is usable at 25 s or less (reports/owner/candle_probe_prereg.md,
  with the logged deviation). Followed by the candle clock study (candle_clock_prereg.md) and release 2.
- Candle clock study (Nov 10 2026): no coin has a steady offset. Six coins are cut at the minute and take their
  newest bar from trades in release 2's new mode; twelve stay on the candle answer (candle_clock_prereg.md, "Result").
- Live order timing (Nov 10 2026): the bot's timing stays as built. Every realistic timing is within a few percent of
  the research assumption in pooled P&L, and the study cannot rank them (reports/owner/timing_prereg.md, "Final
  reading").
- The model on historical data: three rounds, no change (findings doc).
- Trade-print features: no change (signal lab 2). A live shadow log of them is not worth building.
