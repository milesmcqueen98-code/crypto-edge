# Paper against research, Nov 6 to Nov 10 2026

Plan: reports/owner/paper_reconcile_plan.md (fixed before any number here existed). Branch owner/reconcile.
This is a description. Nothing is chosen with it.

## The answer

- **Bid levels.** At the bot's 787 new first bids, its price was within one tick of the research price in about
  26% of cases and within 5 bp in about 60%. The median error is 0 bp. The 5th and 95th percentiles are about -23 bp and +13 bp. About 40% of bids
  are more than 5 bp off, about 10% more than 20 bp off.
- **The level error is a late BTC.** The plan's test: the bot's error against beta times BTC's return over minute
  t-1 (sign flipped, the error a one-minute-late BTC gives). Correlation about 0.94, slope about 0.98, R-squared
  about 0.88. With the two-minute return: correlation about 0.78, slope about 0.69. Replaying the engine's own code
  with BTC's newest minute removed: the bot's price equals the 1-minute-late price for about 37% of bids, the final
  price for about 26% (mostly minutes where BTC barely moved, so both are the same), the 2-minute-late price for about
  18%, and none of the three for about 19%.
- **Scores.** The median absolute gap between the bot's score and the research score is about 0.26 (the log rounds
  to 0.1). Against the 1-minute-late replay it is about 0.045. But the tail is wide: 90th percentile about 11 points.
  For 153 of 787 bids (about 19%) the research score is at or below the threshold, so the research would not have
  bid. In about 74% of those, the 1- or 2-minute-late replay puts the score above the threshold.
- **Bids in common.** About 67% of the bot's new first bids have a research new first bid on the same coin within one
  minute (about 81% have the research holding a bid at that minute). About 77% of the research's new first bids have
  a bot new first bid within one minute.
- **First-bid fills.** 11 bot fills the research also has (bot P&L of the 4-sigma rung about +$717; whole ladders
  about +$1,130). 2 fills only the bot has (about +$241; ladders about +$410). 5 fills only the research has, all in
  the Nov 8 21:55 drop; in 3 of them the bot logged a cash_short for that coin within 3 minutes, and 2 of them (DOGE,
  SOL) opened below the research price, so the paper fill rule (the minute must open above an unfilled bid) would
  not have filled them either.
- **Live time.** The plan's live period is 3,630 minutes (60.50 hours). The decision minutes compared here are
  3,564 (59.40 hours); see deviations D1 and D2.

## Terms

- **Research side:** what the bot's own code (engine `arrays`, `edge/wick.py` `panel`, the five bot/v2 models) gives
  at minute t when its table holds the final Coinbase one-minute candles of the 11 days before t. Computed minute by
  minute on a GitHub runner, one engine step per minute, no vectorisation.
- **Level / price:** the 4-sigma bid level; the price is the level floored to the coin's tick, as the engine does.
- **Error, bp:** bot price over research price minus 1, times 10,000. Zero when the two are within one tick. The
  "raw" error is against the unrounded research level.
- **Tick:** the engine's `spec(c).tick`, from paper_spot/state.json. For PEPE one tick is about 20 bp of its price,
  so its errors below that are hidden; for the other coins a tick is 0.05 to 1.5 bp.
- **New first bid (bot):** an `arm` event. **(research):** at minute t the inputs are valid, the score is above the
  threshold (about 30.39) and the coin has no open 4-sigma rung in the bot's log; and at the previous decision
  minute it was not so, or a logged gap lies in between (the bot cancels every armed bid after a gap). Cash and slot
  limits are not modelled; the bot's cash_short cases are listed apart.
- **Busy coin:** from the minute after a rung-4 fill to its take-profit fill (inclusive of that minute) or to just
  before its time exit, as the engine allocates.
- **First-bid fill (research):** research armed at minute m and the final low of m at or below the research price.
  One dip counts once: after such a fill the research coin is treated as busy until its take-profit price trades or
  for 60 minutes. Only minutes the bot settled count.
- **Both / bot only / research only:** a bot rung-4 fill is "both" when the research is armed at that minute with
  the final low at or below its price (the plan's rule). A research fill is "research only" when the bot has no rung-4
  fill on that coin from one minute before it until the research rung would have closed.

## Tables

Level error at the bot's new first bids (reports/owner/reconcile/m1_level_error.csv)

| n | median | 5th pct | 95th pct | median abs | share beyond 5 bp | share beyond 20 bp |
|---|---|---|---|---|---|---|
| 787 | 0.0 | -23.4 | +12.9 | 3.6 | 40% | 10% |

Is the error a late BTC? (m1_explained_by_late_btc.csv; y = raw error)

| explanatory variable | corr | slope | R-squared |
|---|---|---|---|
| beta times BTC 1-minute return to t-1, sign flipped | 0.94 | 0.98 | 0.88 |
| beta times BTC 2-minute return to t-1, sign flipped | 0.78 | 0.69 | 0.61 |
| replayed error, BTC 1 minute late (engine code) | 0.94 | 0.98 | 0.88 |
| replayed error, BTC 2 minutes late (engine code) | 0.78 | 0.69 | 0.61 |

Which input the bot's price equals within a tick (m1_closest_input.csv; checked in this order)

| final candles | BTC 1 min late | BTC 2 min late | none of these |
|---|---|---|---|
| 206 (26%) | 289 (37%) | 143 (18%) | 149 (19%) |

By size of BTC's last-minute move (terciles of the absolute 1-minute return; m1_by_btc_move.csv)

| tercile | abs return, bp | n | median | 5th pct | 95th pct | beyond 5 bp | beyond 20 bp |
|---|---|---|---|---|---|---|---|
| low | 0 to 1.4 | 263 | 0.0 | -7.1 | +4.7 | 11% | 2% |
| mid | 1.4 to 4.8 | 262 | 0.0 | -7.1 | +6.9 | 26% | 0.4% |
| high | 4.8 to 145 | 262 | -6.2 | -44.6 | +28.4 | 83% | 27% |

By coin: m1_by_coin.csv (every coin's median is within about 2.5 bp of zero; the share beyond 20 bp runs from 0%
for ENA to about 19% for SUI; ETH has only 3 bids, 1 of them beyond 20 bp).

Score error (m2_score_error.csv)

| n | median abs gap | 90th pct abs gap | research at or below threshold | median abs gap to 1-min-late replay |
|---|---|---|---|---|
| 787 | 0.26 | 11.3 | 153 (19%) | 0.045 |

Bids in common (m3_bids.csv; matching window: same coin, one minute either side)

| bot new first bids | also in research | research new first bids (less 2 cash-blocked) | also in bot |
|---|---|---|---|
| 787 | 524 (67%) | 674 | 519 (77%) |

- Cash: 11 cash_short events, all on Nov 8 21:56 to 22:00 (m3_cash_short.csv). 2 research new first bids fall on a
  coin and minute the bot logged as cash-short; they are left out above. 8 bot new first bids come within 3 minutes
  after a cash_short on that coin (a disarm and re-arm the research does not have).

First-bid fills (m4_summary.csv, m4_fills.csv)

| group | n | bot P&L, 4-sigma rung | bot P&L, whole ladder |
|---|---|---|---|
| both | 11 | +$717 | +$1,130 |
| bot only | 2 | +$241 | +$410 |
| research only | 5 | none (no bot fill) | none |

- 3 of the 11 "both" fills came 3 to 4 minutes after the research's own fill of the same dip (XRP, LINK, SUI on
  Nov 8: research at 21:55, bot at 21:58 and 21:59). The bot's bids moved one minute behind the drop.
- Not counted: 6 research dips in the final minute (Nov 10 13:30), which the bot never settled
  (m4_unsettled_minutes.csv).

## Deviations from the plan, and additions

Written on Nov 10 2026 at about 19:16 UTC, before the comparison was run.

- **D1. Start-up minutes are not decision minutes.** The plan's period leaves out the gaps the log records
  (catch_up events). The log also shows that each paper job makes its first decision only 4 to 6 minutes after it
  starts: it first downloads 11 days of candles (the first job's first step is exactly known: its adv event is at
  22:36, six minutes after its backfill at 22:30). When one job follows the next without a gap, no catch_up is logged,
  so these minutes are in the plan's period but the bot decided nothing in them. Counting them would add research
  bids that the bot could not have. So the comparison leaves out, for each job start, the minutes from its backfill
  minute up to its first step (the first event only a step writes, if it is at most 6 minutes later; otherwise 6
  minutes, the longest start-up seen; two of 13 starts were assumed). Both figures are reported.
- **D2. One failed step.** The step of Nov 7 21:19 raised an error before the model ran. That minute is left out too.
- **D3. Bot armed state across a start-up.** After a logged gap the bot cancels every armed bid, so its next bids are
  new. After a start-up with no logged gap it keeps them. The research rule follows the same logic.
- **Addition A1 (not a plan measure).** At every minute with a bot first bid, the engine's code is also run with
  BTC's newest one and two minutes missing from its table (what a late BTC answer gives the bot).
- **Computation.** Minute by minute with the engine's own functions, so no vectorisation check was needed.
- **Added during the work (after the first look at measure 4, Nov 10 about 19:30 UTC).** Two refinements of the
  fill rule, both written into compare.py's header: only minutes the bot settled count (step m+1 settles minute m),
  and a research fill is "research only" only when no bot rung-4 fill on that coin falls in the research rung's open
  window. Without them the final minute added 6 research-only fills the bot could not have seen, and the Nov 8 drop
  was counted on both sides (11 both, 2 bot only, 14 research only).
- **Sensitivity, plan's live set without D1 to D3:** 54% of bot bids in research, 61% of research bids in bot (the
  research then bids at each job's first minute while the bot is still downloading). Fills unchanged.

## Limits

- One book, about 60 live hours, 13 first-bid fills. The fill groups are small.
- The research side is the bot's own table and feature code on final candles, not the full backtest. Exits, deeper
  rungs and fill sizes are not compared. The research fill rule ignores the paper rules of a one-tick trade-through,
  the open-above rule and the volume cap.
- The bot's disarms are not logged one by one, so a research new bid while the bot was already holding a bid on that
  coin counts as not in common.
- About 19% of bot prices match none of final, 1-minute-late or 2-minute-late BTC; their cause (BTC later still, or
  the coin's own late candles, or older BTC minutes missing) is not tested here.
- Final candles leave out trades in some minutes (candle clock study); some coins miss many minutes (DOGE about 13%,
  AAVE about 24% of the window), as they do for the bot.
- Candle answers: 1,278, none dropped, no refusal. 106 were cache hits for windows that ended about 3.8 days or more before
  the fetch; most answers had no Age header, so their making time is taken from Date and cannot be checked further.

## How to reproduce

1. Research side (needs the exchange API; runs on a runner, about 16 minutes):
   `gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref owner/reconcile
   -f script=scripts/owner/reconcile/fetch_and_compute.py -f args="" -f tag=reconcile
   -f sparse="bot edge scripts/owner reports/owner reports/cfm_products.csv paper_spot" -f commit="reports/owner/reconcile"`
   It writes research_minutes.csv.gz (61,710 coin-minutes), late_btc_at_arms.csv, fetch_answers.csv, fetch_run.json.
2. Comparison (offline, light): `python scripts/owner/reconcile/compare.py`; writes the m1 to m4 CSVs and summary.json.
3. Test of the matching logic: `python scripts/owner/reconcile/test_compare.py`.
