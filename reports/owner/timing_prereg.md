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

## Deviation log
- **Nov 10 2026, before any print is fetched (implementer).** The last print before P0's placement time (q + 0) is
  stamped before q, outside the fetched window [q, q + 70 s). It is taken from the last page the fetcher already reads
  to prove the window complete (no extra request): the newest print stamped before the merged window's start, or the
  last print before q inside a merged window. Where it is unknown, P0's skip test falls back to no skip and the row is
  flagged. Nothing else about the window changes.

## First reading (Nov 10 2026, 10:26 ET, orchestrator)
- **By the plan's rule, read once:**
  - P1 against P0 is -11.3% (check) and -16.6% (2022-23) of P&L, and +4.8% in selection. That is material in two eras
    with the same sign.
  - P2 against P1 is +8.6% (check) and +17.5% (2022-23), and -7.1% in selection. By the letter, P2 qualifies to be
    built behind a switch.
  - P3 against P1 is +2.8% / +0.1% / +13.1%: no material effect.
- **What does not depend on how a changed parent is valued:**
  - P1 fills 87% / 90% / 83% of P0's parents in the same minute (selection / check / 2022-23). P2 fills 97% / 96% / 95%.
  - 14% / 18% / 20% of P0's fills come in the first 10 s of the minute.
  - The prints confirm 96.5% / 95.9% / 93.0% of the candle research's parents.

## Deviation 2 (Nov 10 2026, 10:26 ET, orchestrator; logged before the work it covers)
- **What was found.** Most of every P&L difference comes from the plan's valuation and not from fill prices. A P0
  parent that a policy misses loses its whole research ladder; a parent only the policy finds adds back its 4-sigma
  rung alone. A parent that merely moves by a minute is booked as the loss of its deeper rungs.
  - In 2022-23 the ladders removed from P1 sum to -$13,072 (131 parents). For P1a, which differs by 1.5 to 2.5 s, they
    sum to -$2,841 (120 parents). About eleven ladders decide the reading.
  - The selection era has the opposite sign in both readings.
  - Pooled over the three eras in dollars, P1 is 5.8% below P0 and P2 is 3.4% above P1.
  - The plan named this limit but not its size.
- **Decision.** No engineering is commissioned on the first reading alone. A symmetric valuation is run on the same
  prints, and the plan's 5% rule is applied to it. Fixed now, before any of it is computed:
  - **S1** (from the committed derived data): every parent of every policy valued on its 4-sigma rung alone, by the
    lab's exit rule and costs, in percent of P0's 4-sigma P&L.
  - **S2:** the whole ladder re-simulated for every parent of every policy. Deeper rungs fill on prints from one
    second after the parent's fill inside the fetched window, and on candles afterwards; exits follow the lab's rule.
    The same method values P0, so the comparison is like for like. If the committed data cannot support S2, the missing
    derived fields are fetched again for the same windows.
  - **Reading.** S2 decides where it exists, otherwise S1. P2 or P3 is built behind a switch on timing grounds only if
    it beats P1 by 5% of P&L or more with the same sign in at least two eras under the symmetric valuation as well.
    If it does not, the first reading is recorded as an effect of the valuation.
  - **Also reported, with no rule:** the share of P0's parents that each policy fills within one minute either side,
    and how many of the added and lost parents are such moves.
- **Question 1 (the pilot).** The expectation for the pilot is taken from the match rates above, which do not depend
  on the valuation.

## Deviation 3 (Nov 10 2026, implementer; logged before S2 is computed, after S1 and the moves were specified)
- **The committed derived data cannot support S2 exactly.** It keeps the record lows from the six start times only.
  A deeper rung rests from one second after the parent's fill. When a print already trades through the rung inside
  that second (5 to 21 rung cases per era and policy), whether a later print fills it is not determined.
- **No new fetch.** The prints of the first fetch are still in the eight shard artifacts of the runner jobs (kept 21
  days). One runner job downloads them and keeps, for each studied minute, every print in [q, q + 70 s) at or below
  max(L6(q-1), L6(q)) + one tick (L6 = L x exp(-2 sigma), the 6-sigma level of that minute). These are the same
  prints that gave the parent fill times, so the rungs and the parents cannot disagree. Raw prints stay on the
  runners; only the cut prints are committed (branch owner/timing-data). This replaces "re-run the same windows with
  the same fetcher": the prints are identical and no request is made.
- **S2 as implemented:**
  - deeper rungs at L x exp(-2 sigma) and L x exp(-4 sigma) of the parent's own level (L(q-1) and sigma(q-1) for a
    stale-bid fill);
  - they fill on a print at or below the rung minus one tick in [fill + 1 s, q + 70 s) (fill minute q, or q + 1 from
    60 s), then on candle lows (low <= rung x (1 - tick / rung)) from minute q + 1 up to the minute before the
    parent's take-profit minute (else q + 59), as the research's precompute;
  - capacity (USD volume below the rung), take-profit capacity, take-profit minute and the 60-minute close: the
    research's precompute rules on candles, from each rung's own fill minute;
  - sizes, sellers shared within a parent, take-profit capacity and costs: the research's evaluator
    (scripts/ladder_v5/fsim.py evaluate) at S* (today's volumes, costs x2, theta 0.5, $250K), the cash cap off, the
    fee tier fixed to the research book's; remainder exits priced from prints as the research book
    (lsim.rem_daily's costs);
  - one timing, the print timing (rungs from 1 s after the fill), in place of the research's blend of its two latency
    bounds.
- **S2 validation, before any policy difference is read:** P0 under S2 against the research ladder on the shared
  parents, per era. The same evaluator on the research's own candle rows (cash off, blended bounds) splits the gap
  into the cash rule and bounds against the print timing.

## Final reading (Nov 10 2026, 10:39 ET, orchestrator)
- **Under the rule, on S2 (whole ladder, like for like):**
  - P1 against P0: +1.9% / -11.9% / -11.9% (selection / check / 2022-23), pooled -5.1%. Material in two eras.
  - P2 against P1: -3.8% / +7.1% / +11.1%, pooled +2.6%. The two-era condition is met.
  - P3 against P1: +4.0% / -2.1% / +9.8%, pooled +4.8%. One era only: not met.
- **Deviation 4 (logged with the decision): the condition is met for P2, and nothing is built on timing grounds.**
  The plan's own bracket shows that this measure cannot rank timing policies:
  - P1a is the live bot with its calls 1.5 to 2.5 s faster. Under S2 it beats P1 by 5.8% and 12.9% in two eras
    (pooled +6.3%), which is more than P2 does, and it sits 0.9% above P0. The rule would qualify it too.
  - P1b, the live bot with slower calls, is also slightly above P1 in all three eras.
  - The order by pooled P&L is P1a, P3, P2, P1b, P1. That is not the order of speed. A shift of two seconds moves
    10-17% of the first bids to other minutes, and a few dozen ladders per era decide the sign.
- **What the study does establish:**
  1. Every realistic timing is within a few percent of the research's zero-delay assumption in pooled P&L (P1a +0.9%,
     P3 -0.6%, P2 -2.7%, P1b -4.1%, P1 -5.1%). The research overstates P&L by a few percent at most on this count. The
     study cannot say which timing is best.
  2. The match rates are stable. The live timing fills 83-90% of the research's first bids in the same minute and
     88-94% within two minutes. Fast re-pricing fills 95-97% in the same minute.
  3. Fills are spread evenly inside the minute: 14-20% of them fall in the first 10 s.
  4. Removing the gap between the cancel and the new bid has no reliable effect.
- **Decisions:**
  - The bot's timing stays as built.
  - If the candle probe leads to a bar built from trades (decided on its own rule), the step time becomes a setting.
    An earlier step would then be chosen for its match with the research (class 1 in the charter), not for a P&L gain.
  - The pilot's rule B is read with these match rates (reports/owner/FORWARD_TESTS.md).
  - The heartbeat should record when the cancels and the new bids actually finish each minute, so the pilot shows
    where the live bot sits between P1a and P1b. Queued for the next release that touches the engine.
