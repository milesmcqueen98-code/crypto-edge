# Candle clock study: where the venue cuts its one-minute candles, against the trade timestamps. Plan (Nov 10 2026, 13:30 ET)

Written by the orchestrator before any data of this study exists. Branch owner/charter; the study runs from branch
owner/candle-clock.

## Why
- **Release 2's runner check** (Nov 10 2026, 17:29 to 17:59 UTC, 18 coins, 30 minutes each) built every minute's bar
  from the venue's public trades and compared it with the venue's final candle.
  - The two were identical in every minute for BTC, ETH, SOL, XRP, LTC and ZEC.
  - For the other twelve coins they were identical in 30% to 90% of minutes.
  - Where they differed, volume had moved between two adjacent minutes and the two-minute total was unchanged: the
    final candle of a minute held trades stamped in the first seconds of the next minute.
- **Signal lab 2 saw the same in history:** in candidate windows, 7.8% of minute boundaries had the first seconds of a
  minute (median 8 s) in the previous candle.
- **The model was trained on final candles.** For such a coin the research's newest candle can hold a few seconds
  that a bar cut at the minute leaves out. Before the trades-built bar is switched on for a coin, the cut has to be
  known for that coin: at the minute, at a steady offset, or unstable.

## Design (fixed now)
- **Coins:** BTC and the 17 traded coins.
- **Data:** the venue's public trades for the most recent six hours of each coin, paged back from the present at no
  more than 7 requests a second, and the final candles of the same minutes, fetched at the end (at least ten minutes
  after the last minute used; an answer counts only if it was generated after that). Raw trades stay on the runner. A
  refusal or a rate-limit answer stops that source and is reported.
- **The cut at each boundary.** For each coin, minutes in order: starting where the previous candle ended, find the
  run of trades (in trade order) whose total size equals the candle's volume and whose open, high, low and close equal
  the candle's. The cut after that run lies between the stamp of its last trade and the stamp of the next trade. That
  gives an interval for the cut at every boundary, measured from the minute mark (positive is after the mark).
- A boundary is **unexplained** if no such run of trades exists.

## Measures (per coin)
1. The bar cut at the minute against the final candle: share of minutes with all five values equal; share "exact" by
   the candle probe's measure 2 (high, low and close equal, volume within 0.5%); share in material error by its
   measure 3 (missing, or the close off by more than half of the coin's one-minute sigma, or the low off by more than
   5 bp).
2. Share of boundaries explained by a cut, and share unexplained.
3. The cut: share of boundaries whose interval holds zero; the spread of the interval bounds for the rest; the largest
   lower bound (how late a candle can end).
4. One offset per coin: the largest share of boundaries that a single offset satisfies, over the six hours and hour
   by hour.
5. Out of sample: the offset fitted on the first three hours, applied to the last three. Share of minutes where the
   bar over [mark + offset, mark + 60 s + offset) equals the final candle (all five values; "exact"; material error).
   The same with offset zero, and with the offset implied by the previous boundary.

## Classes (fixed now)
- **A, cut at the minute:** offset zero satisfies at least 99.5% of boundaries, and the bar cut at the minute has a
  material-error share of at most 1% in the last three hours.
- **B, steady offset:** the offset fitted on the first three hours gives a material-error share of at most 1% in the
  last three hours, and that candle ends no later than 12 s after the mark (the bot's data step runs 6 to 13 s after
  it).
- **C:** neither.

## What a class means for the bot (fixed now)
- **A:** the coin's newest bar may come from trades as release 2 builds it.
- **B:** the trades-built bar needs the coin's offset. That is a further change to release 2, built and tested before
  use; the forward collector then tracks the offset daily.
- **C:** the coin stays on the venue's candle answer. Whether a later look at that answer is good enough is read from
  the candle probe.
- BTC is reported on its own: every coin's bid level reads BTC's newest close.
- A class is a statement about inputs matching. It says nothing about P&L.

## Limits, stated now
- Six hours of one day. A coin's class is confirmed on the collector's daily record before it is relied on for live
  orders.
- A cut is only bounded by the trades around it, so a quiet boundary says little.
- If the candle is cut by a time the public trades do not show, no run of trades explains it. That shows up as
  unexplained boundaries.

## Deviation log
(none yet)
