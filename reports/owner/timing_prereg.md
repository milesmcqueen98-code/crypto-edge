# Live order timing against the research assumption: pre-registration (Nov 10 2026, 09:06 ET)

Written by the orchestrator before any print is fetched for this study. Branch owner/timing.

## Why
- **The research and the paper books assume each minute's bid rests for the whole minute.** A candidate at minute q fills
  at the level L(q) if the minute's low trades through it.
- **The live bot cannot do that** (bot/spot/engine.py). It steps 6 s after each minute closes, fetches candles, computes
  the new levels, cancels every re-priced bid in one pass and places the new bids in a second pass. So in live:
  - the previous minute's bid, at L(q-1), rests for the first seconds of minute q (the stale window);
  - for a few seconds no bid rests at all (the gap between the two passes);
  - the new bid is skipped when the market is already at or below it (`skip_market_below`).
- **Paper cannot see this:** the paper broker fills from whole-minute bars. Only live fills or trade prints can.
- **Why it matters:** this is a difference between the simulation and the bot, not a model change. If it costs or
  earns P&L, the pilot's comparison with paper will show a gap that needs explaining, and re-pricing faster (or
  without a gap) is plain engineering.

## Question
1. How do R2-08's parent fills and P&L change when the 4-sigma bid follows the live bot's timing instead of resting
   for the whole minute?
2. Would re-pricing faster, or without the gap, change them?

## Book and data
- **Book:** the frozen R2-08 research walk-forward (ladder v6's incumbent dataset, tags main and early), parents (the
  4-sigma bid) only. Eras: selection Jan 2025 - Mar 2026, check Apr - Nov 5 2026, 2022-23. All three have been read
  many times; nothing is selected here, so there is no holdout.
- **Minutes studied:** every (coin, q) where a bid could fill under any policy: the coin is approved at q-1 and the
  candle low of q is at or below L(q-1) plus one tick, or approved at q and the low is at or below L(q) plus one tick.
- **Prints:** Coinbase trades for [q, q + 70 s) of those minutes, fetched on GitHub Actions. Raw prints stay on the
  runners; one derived row per (coin, q, policy) is committed.

## Policies (fixed now)
For each minute q, with c = seconds after q when the stale bid is cancelled and p = seconds when the new bid rests:

| Policy | Stale bid at L(q-1) | New bid at L(q) | Meaning |
|---|---|---|---|
| P0 | none | [q, q + 60) | The research assumption |
| P1 | [q, q + 8) | [q + 10, q + 68) | The live bot as built (central case) |
| P1a | [q, q + 6.5) | [q + 7.5, q + 66.5) | The live bot, fast calls |
| P1b | [q, q + 12) | [q + 15, q + 72) | The live bot, slow calls |
| P2 | [q, q + 1) | [q + 1.3, q + 61) | Fast re-pricing (needs live trades instead of polled candles) |
| P3 | [q, q + 8) | [q + 8, q + 68) | As built, but each coin's new bid placed with its cancel (no gap) |

- A stale bid exists only if the coin was approved at q-1 and its ladder was not already open.
- When L(q) and L(q-1) are within half a tick, the engine keeps the old bid: it rests throughout, in every policy.
- The new bid is skipped for that minute when the last print before its placement is at or below L(q).
- **Fill rule:** a resting bid at px fills at px when a print trades at or below px minus one tick (the research's
  trade-through rule). One parent fill per coin until its ladder closes, as in the research.
- Cash, sizes and capture share are not re-simulated: a fill keeps the research's size where the research has that
  parent, and the average parent size of that coin and quarter where it does not.

## What is reported (per era and policy; no gate, this is a measurement)
1. Parents filled; the share of P0's parents filled in the same minute; parents only in the policy; parents only in P0.
2. Entry price against P0 for the shared parents (bp, dollar-weighted), split by whether the fill came from the stale
   bid or the new one, and by seconds after q.
3. The distribution of fill times within the minute for P0's parents (how many fall in the first 8, 10 and 15 s).
4. First-order net P&L against P0, in bp per dollar bought and in percent of P0's P&L:
   - shared parents: the research's ladder result, adjusted for the entry-price difference on the 4-sigma rung (a
     take-profit exit moves with the entry: 0.4 of the difference is kept; a time exit keeps all of it);
   - parents only in the policy: the 4-sigma rung alone, by the lab's exit rule and costs from the candles;
   - parents only in P0: their whole research ladder result removed.
5. The same P&L difference as a change in daily Sharpe at S* (today's volumes, costs doubled), capture 0.5, $250K.
6. P0 itself against the candle-based research fills (how many research parents the prints confirm).

## How it will be read
- **P1 against P0** is what the pilot should expect relative to paper. If it differs by 5% of P&L or more with the
  same sign in at least two eras, the pilot's pass rule (live fills on at least 70% of paper fills, net within 25 bp)
  must be read with that expectation, and the charter records it.
- **P2 or P3 against P1** says whether an engineering change is worth building. If either is better by 5% of P&L or
  more with the same sign in at least two eras, it is built behind a switch and tested in the pilot before any use.
  If neither, the bot's timing stays as it is.
- Anything smaller is reported as no material effect.

## Limits, stated now
- Deeper rungs and exits are not re-simulated; an added or lost parent changes them, and the first-order P&L ignores
  that except through the removed ladders.
- The API timings (8 s and 10 s) are assumptions. The live log does not record wall-clock times of cancels and places;
  P1a and P1b bracket them. The pilot can measure them once the log carries those times.
- Levels come from the repo's candles, whose clock runs ahead of the prints by about 8 s in about 8% of minute
  boundaries (signal lab 2). The bot computes its levels from candles fetched at q + 6 s, which the forward collector
  now records, so this can be checked on new data.
