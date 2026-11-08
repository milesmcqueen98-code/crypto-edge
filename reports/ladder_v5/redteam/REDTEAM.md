# Ladder v5 red team: the live cash rule (Claim 1) and C1a "deeper first"

Independent re-derivation, 2026-11-08 (UTC). Scope (coordinator): Claim 1 and the C1a near miss only. Branch
ladder/redteam, from origin/ladder/v5 at the freeze (7ae53cb + 38066ba). Code: scripts/ladder_v5/redteam/. Outputs:
reports/ladder_v5/redteam/.

## Verdicts
- **Claim 1 (live cash rule): partly confirmed.** The direction holds: at $250K the engine's cash rule costs a lot in
  the selection era, less in the check era, little in 2022-23, and almost nothing at $1M. The claimed sizes do not:
  my engine-faithful live book earns **24.1% / 18.8% / 13.2%** a year (selection / check / 2022-23; claim 22.4 / 17.6
  / 13.7), paired t against the research book **-1.68 / -0.61 / -1.99** (claim -2.23 / -1.88 / -1.44). At $1M:
  21.8% / 9.1% / 6.5% (claim 20.1 / 9.2 / 6.6), t +1.04 / +0.53 / -0.51. The claim's numbers come from two hsim
  modelling choices that differ from bot/spot/engine.py (deeper-rung priority by parent fill time instead of ladder
  creation order; deeper rungs placed and filled when the market is already at or below their level). An emulation of
  hsim's choices in my replay reproduces the claim within 0.1 point in every era at base (0.2 at S* and $1M). Three
  engine runs on cascade
  windows match my replay rung by rung (100% of deeper-fill counts on common parents on two of the three days) and do
  not match hsim's choices.
- **C1a: partly confirmed.** The claimed result is reproduced under hsim's choices (pooled t +1.98 vs claimed +1.94;
  selection 19.3% -> 21.7%, check 15.0% -> 15.7%, 2022-23 10.35% -> 10.26%). Against the engine-faithful incumbent
  the pooled t is **+1.40** (selection 19.9% -> 22.4%, check 16.4% -> 17.3%, 2022-23 10.16% -> 10.14%), and +1.40
  to +1.77 across my robustness variants. In every world G1 (t >= 2) and G2 (2022-23 > 0) fail; G3 fails in every
  engine-faithful world (passes only under hsim's choices, t +2.04); G4 passes. Not adoptable; further from the bar
  than reported.

## Method
- **My replay** (rt_live.py, numba): every minute of each era, written from bot/spot/engine.py. I did not import or
  copy scripts/ladder_v5/hsim.py or gates.py; I read hsim.py only after my replay and engine harness were built, to
  find the causes of the disagreements below. Engine rules replayed:
  - step t: settle minute t-1 (parent and deeper fills; take-profit fills release cash; a partly filled bid rests
    while the price stays below it, <= 15 minutes, holding its cash), then `_manage` ladder by ladder in creation
    (dict insertion = arming) order: window close (parent take-profit traded, or t >= parent + 60) cancels deeper bids,
    time exits at fill + 61, then pending deeper rungs are placed if the last close is above the level and free cash =
    equity - positions at cost - all resting holds (including the 4-sigma bids placed at t-1) covers them (>= 50%:
    partial; else retried next minute); then `_allocate`: approved, fresh, non-busy coins in prediction order from
    equity - positions - non-4-sigma holds (full, partial if >= 50%, else nothing).
  - busy: no 4-sigma bid while the parent rung is open (until its take-profit fills completely or the 60-minute exit)
    or its remainder rests.
  - live 1-second poll (instant bound): the deeper rungs of a parent filling in minute t go out at the fill from the
    cash the 4-sigma allocation left (new ladders first, then every pending rung, creation order); a rung that waited
    fills on the first trade-through of its level after it starts resting (deep paths), with that minute's quantities.
  - holds = notional x (1 + 6 bp); fixed equity = capital (as the research book); ADV from my own table
    (sim.daily_stats; equal to the frozen dataset's adv on all 4,701 + 2,208 rows); a coin with unknown ADV gets no bid
    (its research trades have size 0).
- **P&L:** fsim.evaluate on the frozen tranches with each tranche's funded size (`mult`) and late deeper fills taking
  the deep-path quantities; 1-second blend minute + s x (instant - minute) with fsim's s. Frozen pickles copied into
  reports/wick1m/ after a SHA256SUMS check.
- **Checks:** the research policy of my replay (unlimited cash, research timing) reproduces fsim.book to 1e-15 per
  day in all three eras; under the engine policy my fill sizes equal fsim's to 4e-12 (so the gross cap never binds).
- **Engine check** (rt_engine.py): bot/spot/engine.py itself (paper broker, capture 0.5, stored candles), its AI
  replaced by the panel prediction and quarterly threshold (the harness pattern of hsim_check.py, engine side only),
  against my replay restricted to the same window, minute bound (the paper engine has no 1-second poll, so my
  instant-bound emulation of `fast_poll` is checked against the code only, not against an engine run).
- **C1a** (rt_c1a.py): policy preempt in my replay (a 6/8-sigma rung short of cash cancels the lowest-prediction
  4-sigma bids and takes their holds, at the minute step and at the 1-second placement; parents filling in the same
  minute are not preempted, which favours C1a), gates computed by my own code as pre-registered.

## Claim 1: my numbers next to the claim
Base: $250K, theta 0.5, 1x costs, research volumes, 1-second blend. t = Newey-West (5 lags) paired t vs the research
book. "Unlimited cash" = my replay with the engine's timing and busy rule but no cash limit.

| | Selection | Check | 2022-23 |
|---|---|---|---|
| Research book (fsim) | 29.9% / 2.40 | 20.1% / 2.95 | 14.0% / 2.27 |
| Live book, claim (hsim) | 22.4% / 2.16, t -2.23 | 17.6% / 2.61, t -1.88 | 13.7% / 2.18, t -1.44 |
| **Live book, my engine-faithful replay** | **24.1% / 2.48, t -1.68** | **18.8% / 2.48, t -0.61** | **13.2% / 2.14, t -1.99** |
| Engine timing, unlimited cash | 31.7% / 2.42, t +1.52 | 20.9% / 2.76, t +0.64 | 14.0% / 2.26, t -0.04 |
| Cash rule alone (live vs unlimited cash) | -7.6 pts, t -1.91 | -2.1 pts, t -1.46 | -0.9 pts, t -2.02 |
| My emulation of hsim's choices | 22.4% / 2.17, t -2.22 | 17.6% / 2.62, t -1.80 | 13.7% / 2.17, t -1.45 |
| $1M research | 20.5% / 2.51 | 8.9% / 1.60 | 6.6% / 1.20 |
| $1M live, claim | 20.1% / 2.43, t -0.60 | 9.2% / 1.56, t +0.53 | 6.6% / 1.20, t +1.15 |
| **$1M live, mine** | **21.8% / 2.78, t +1.04** | **9.1% / 1.57, t +0.53** | **6.5% / 1.18, t -0.51** |
| $1M hsim emulation | 19.9% / 2.41, t -0.85 | 9.2% / 1.56, t +0.53 | 6.6% / 1.20, t +1.15 |

Counts, selection, $250K (minute bound): parents unfunded 112 (102 cash, 10 busy; claim 113), partial 17 (claim 18).
S* incumbent (today's volumes, 2x unverified costs, theta 0.5): mine 19.9% / 16.4% / 10.2%, Sharpe 2.49 / 2.22 /
1.68; claim 19.5% / 15.1% / 10.4%, 2.31 / 2.31 / 1.72; my hsim emulation 19.3% / 15.0% / 10.35%.

Two things the claim's single comparison mixes: (1) the research book's minute bound drops every deeper rung whose
first trade-through is in the parent's own minute, while the engine places it a minute later and it can fill on a
later trade-through; with unlimited cash that timing alone is worth +1.7 / +0.8 / 0.0 points; (2) the cash rule
itself, -7.6 / -2.1 / -0.9 points. The cash cost is a cascade-day phenomenon: in the selection era Oct 10 2025 and
Feb 3 2025 carry 69% of it and five days 93%.

## Every disagreement and its cause
My emulation of hsim (switches in rt_live.py, all on together, priority by fill time) reproduces the claim in every
era and configuration within 0.2 point (table above; S* and $1M too). The choices, each switched on alone in my
engine-faithful replay (base, return change in points, selection / check / 2022-23):

| hsim choice | Engine (bot/spot/engine.py) | Effect alone |
|---|---|---|
| Pending deeper rungs get cash in parent fill order | `_manage` iterates `state["ladders"]` in insertion order: ladders in arming order | -3.0 / -1.4 / +0.4 |
| A deeper rung is placed even when the market is at or below its level, and fills on that minute's trade-through at the level (above the market) | `_place_pending` defers while last close (paper) / best bid (live) <= level; post-only could not rest above the market | -2.2 / -0.2 / +0.3 |
| Coin free at the parent's take-profit touch + 1 even if the take-profit filled only partly | busy while "4" is in tranches (until fully sold or the 60-minute exit) or "e4" rests | -1.0 / +0.1 / +0.1 |
| Unfilled remainder of a partly filled bid released at the fill | remainder rests (holds cash) while the price stays below, <= 15 min | -0.8 / 0.0 / 0.0 |
| Take-profit, exit and closed-window cash released at the take-profit minute / fill + 60 | released at the next step (settle / `_manage`) | +0.5 / 0.0 / 0.0 |
| Bids on coins with no candles or unknown ADV at 25% x C / 3 (panel predictions exist for pre-listing ENA, HYPE, XRP, SUI, HBAR, NEAR) | no bid without a candle in the last 10 minutes | 0.0 / 0.0 / 0.0 |
| Older pending rungs retried only at minute steps | `fast_poll` retries every pending rung each second | -0.2 / 0.0 / 0.0 |
| All releases before any placement | releases and placements interleaved ladder by ladder | 0.0 / -0.4 / 0.0 |

The effects are not additive and not even sign-stable (at S* the priority switch is +1.2 / -0.7 / 0.0): which
deeper rungs win the scarce cash on two to four cascade days decides several points of a year's return. Both orders
deploy the same deeper dollars in the selection era ($6.28M) but earn 39 vs 23 bp per dollar (base, minute bound). Only an exact
replay of the engine's order gives the incumbent's level; the engine checks below say mine is that replay.

**Engine checks** ($250K, minute bound; agreement with the engine on the research parents, on the deeper-fill count
of parents both funded, and on the minute each deeper rung was placed):

| Window | Research parents | Engine parents (replacement) | Deeper fills engine / mine / hsim-like | Mine: parents, deeper, placement | Fill-order priority | hsim-like |
|---|---|---|---|---|---|---|
| Oct 10 2025 18:00 - Oct 11 06:00 | 77 | 60 (6) | 37 / 35 / 41 | 68/77, 50/54, 86/108 | 66/77, 48/54, 77/108 | 61/77, 44/54, 53/108 |
| Jan 31 2026 (full day) | 44 | 39 (0) | 24 / 24 / 24 | 44/44, 39/39, 73/78 | 44/44, 30/39, 53/78 | 42/44, 31/39, 47/78 |
| Feb 2 12:00 - Feb 3 12:00 2025 | 81 | 60 (7) | 30 / 29 / 35 | 79/81, 53/53, 96/106 | 71/81, 44/53, 60/106 | 74/81, 42/53, 53/106 |

The engine's 4-sigma allocation equals mine in every minute before the first fill (172, 864 and 3 minutes). hsim-like
reproduces the prereg's reported hsim totals (58 parents and 41 deeper on Oct 10; 41 parents on Jan 31), which looked
close to the engine in aggregate but sit on different parents. The paper engine deferred deeper rungs for the market
343 / 171 / 640 times and for cash 231 / 387 / 1,628 times in these windows. My remaining Oct 10 mismatches are the
engine's **replacement parents**: after missing a parent for cash, the engine fills the same coin minutes later at a
re-priced level that the research list does not have (it was busy there), which then blocks later research parents
(6 of 60 engine parents on Oct 10, 7 of 60 on Feb 2-3, 0 on Jan 31). Neither hsim nor my replay can price them; their
sign is unknown.

## Artifact checks asked for
- **Timing order (allocation vs deeper placement):** both hsim and my replay use the engine's order (deeper rungs in
  `_manage`, before `_allocate`). Allocating first instead: -0.9 / -0.8 / 0.0 points (base). Not an artifact.
- **Cash release at take-profit vs 60 minutes:** both release the take-profit part at the take-profit. Releasing
  everything at 60 minutes would cost -6.7 / -2.4 / -3.0 points (base), so the claim is not inflated by that.
- **Busy coins:** the engine's busy rule blocks 10 / 2 / 7 research parents at $250K (14 / 2 / 7 at $1M) that hsim
  funds; dropping the busy rule altogether is worse (-3.4 / -2.6 / -0.2: busy coins would keep bidding). Replacement
  parents: see above.
- **Partial bids:** the 50% partial rule is the same in all books; remainder holds change base returns by -0.8 /
  0.0 / 0.0 when removed (sign is noise-like: S* +0.7).
- **1-second blend:** the live book is below research in both bounds (selection: minute -4.6, instant -7.0 points;
  check -0.5 / -1.7; 2022-23 -0.3 / -0.9), so the blend is not driving the sign. A rung placed late that cannot fill
  on a later trade-through would cost -2.0 / -1.6 / -0.1 (both hsim and I allow late fills, as the engine does).
- Fixed equity on both sides (no compounding); daily loss and drawdown halts never bind (worst research day -2.7%).

## C1a "deeper first"
Pooled paired t (Newey-West 5, daily candidate - incumbent over all three eras' days), per-era inc -> cand return
(era t):

| World | S* theta 0.5 | S* theta 0.25 | base | $1M |
|---|---|---|---|---|
| Claim (hsim) | +1.94: 19.5 -> 21.7, 15.1 -> 15.7, 10.4 -> 10.3 | +2.04 | +1.74 | (no change) |
| My hsim emulation | **+1.98**: 19.3 -> 21.7 (+1.89), 15.0 -> 15.7 (+1.34), 10.35 -> 10.26 (-0.92) | +2.04 | +1.79 | -1.00 (no change) |
| **Engine-faithful** | **+1.40**: 19.9 -> 22.4 (+1.22), 16.4 -> 17.3 (+1.93), 10.16 -> 10.14 (-0.72) | +1.37 | +1.89 | -1.00 (no change) |
| Faithful, fill-order priority | +1.77 | +1.80 | +1.84 | -1.00 |
| Faithful, no market check | +1.54 | +1.34 | +1.62 | -1.00 |
| Faithful, new-coin bids (below) | +1.40 | +1.37 | +1.88 | -1.00 |

Gates (engine-faithful): G1 no (+1.40), G2 no (2022-23 -0.02 pts), G3 no (+1.37), G4 yes. Base: 24.1% -> 30.2%,
18.8% -> 20.0%, 13.2% -> 13.4%. The C1a gain is the cash-rule cost on cascade days recovered; it is large where the
incumbent loses most (selection) and absent in 2022-23 at S*. Same-minute preemption was given to C1a for free (a
parent filling in the same minute is never cancelled); charging it would lower C1a further.

## Other findings
- **Engine edge case (live risk, small):** `signal_usd` applies the 0.2%-of-ADV cap only when the ADV is known; a coin
  with fewer than 10 days of volume history bids 25% x equity / 3 ($20.8K at $250K) with no ADV cap. The research
  never priced those trades (size 0 in the dataset). Holding those bids changes nothing measurable here (C1a +1.40).
- hsim gives full-size bids to approved coins whose ADV is unknown and checks no freshness; the panel has predictions
  for every minute, including before a coin traded on Coinbase (ENA until 2025-06-05, HYPE until 2026-02-05, XRP until
  2023-07, SUI until 2023-05): 14K approved minutes with unknown ADV in the selection era, 57K in 2022-23. Effect on
  returns about zero.
- The prereg's statement that hsim "tracks the engine" rested on aggregate counts; per parent it does not (table).

## Files
- scripts/ladder_v5/redteam/rt_live.py (replay), rt_check.py (off switch), rt_adv.py (ADV table), rt_diag.py
  (counts), rt_matrix.py (configurations x switches), rt_engine.py (engine check), rt_c1a.py (C1a), rt_tables.py.
- reports/ladder_v5/redteam/: matrix_{base,S_0.5,base_1M}.csv and daily_*.parquet; rt_diag_base.csv;
  engine_check_{20251010,20260131,20250202}.{csv,json} and engine_events_*.csv.gz; c1a_*.json and c1a_daily_*.parquet.
