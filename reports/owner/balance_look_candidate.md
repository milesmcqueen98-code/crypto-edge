# Balance look candidate (branch owner/balance-look, from 9e6f53b3)

Monitoring only: no order the bot places, cancels or books changes. Only when the balance warning is raised changes.

## The rule
- A coin's balance at the venue is compared with the bot's open rungs as before (same tolerance key
  `reconcile_tol_usd`, 25 dollars; same price; a coin without a finite price is skipped).
- A **first look** that differs writes a `balance_look` event (`look` "first", `coin`, `exchange`, `bot`) and counts
  `bal_first`. The watchdog does not alert on it.
- A **second look**, after `_settle` has run to its end (fills booked), at which the difference is still there,
  writes the `warning` "coin balance differs from the bot's open rungs: check before trading" with the same fields as
  before plus `since` (the first look's time), and counts `bal_warned`. This alerts, as before.
- A look at which a recorded difference is gone writes `balance_look` with `look` "cleared" and counts `bal_cleared`.
- **Hold** (added after the first run of step 3): at a second look that would warn, a shortfall (bot's sum above the
  venue's balance) that is no larger than the coin's tranches with a market sell of unknown outcome plus the tolerance
  is not warned while the first look is under `BAL_HOLD_MIN` (10) minutes old: no event, the suspect is kept, counts
  `bal_held`. A surplus at the venue, a larger shortfall, or a first look 10 minutes old or more is warned as before.
- The suspects live in memory only (not in `state.json`); a new process starts with none.

## Where a look runs
- Wherever `reconcile` ran before (start; the 15-minute minute 7, 22, 37, 52; after a failed `place_many`): unchanged.
- In `start()`, right after `catch_up`: one more look if a suspect has seen `_settle` (a gap over one minute).
- In a normal `step()`, at the place of the 15-minute call, when it is not the 15-minute minute and a suspect has seen
  `_settle`: the balance look alone (no orphan sweep, no fee tier line). Not in `_orders_only`, not in a minute the
  stale guard skips.
- A look outside `reconcile` that fails logs an `error` "balance look failed: ..." and keeps the suspects.
- Paper mode runs none of this.

## Correction to the brief's expectations
In the step-1 runs, six of the seven "coin balance differs" warnings of the death run come from the restart at 21:30
(XRP, LTC, NEAR, ENA, PEPE, ZEC). The seventh (LINK at 22:22), and the two of the run without a death (LINK at 22:22
and 00:07), come from 15-minute looks. All three LINK cases are a market sell sent with an outcome that cannot be
read yet (the fake exchange's injected fault). The coins have left the venue, but the tranche stays in the bot's sum
until the sell is resolved. With the two looks alone the 22:22 case was still warned, one minute later (22:23). The
hold removes it.

## Live-path simulations ("2025-10-10 20:00" to "2025-10-11 02:00"), step 1 against step 3
| | no death, before | no death, after | death, before | death, after |
|---|---|---|---|---|
| result | PASSED | PASSED | PASSED | PASSED |
| entries | 111 ($1,093,780) | 111 ($1,093,780) | 109 ($1,077,890) | 109 ($1,077,890) |
| exits | 134 | 134 | 135 | 135 |
| P&L | $11,723.34 | $11,723.34 | $8,421.28 | $8,421.28 |
| bot equity / exchange USD | 261,723.3507 / 261,723.3505 | same | 258,421.2907 / 258,421.2905 | same |
| "coin balance differs" warnings | 2 | 0 | 7 | 0 |
| warning events (all kinds of message) | 194 | 192 | 205 | 198 |
| balance_look first / cleared / held | - | 2 / 2 / 1 | - | 7 / 7 / 1 |

- The exchange's counter line is identical in each pair. No death: cancel_unconfirmed 178, partial_sell 8,
  post_only_reject 9, funds_reject 0, fills 195, expired 0, duration_reject 1, sell_unknown 3, tp_error 12. Death:
  187, 3, 7, 0, 204, 0, 1, 4, 11. It does not count balance requests. The extra balance requests are one per look
  outside `reconcile`: 3 in the run without a death (22:23, 22:24, 00:08), 3 with it (21:30 after catch_up, 22:23,
  22:24).
- Event logs compared line by line (order ids masked). The only differences are the removed warnings (2, and 7), the
  added `balance_look` events (4, and 14) and the new counters in heartbeat `counts`.
- LINK timeline, run without a death: market sell of LINK-80 rung 4 sent at 22:21, outcome unknown; first look at
  22:22 (venue about 0, bot 567.93); held at 22:23; sell resolved and booked at 22:24 (567.93 sold), cleared at
  22:24. Second case: the time exit of LINK-105 rung 8 is a market sell sent at 00:05, outcome unknown; first look at
  00:07 (venue about 0, bot 1113.38); resolved and booked at 00:08 (1113.38 sold), cleared at 00:08. That is a
  pending sell resolved within a minute, not a fill that was not booked yet.
- LINK timeline, death run: market sell of LINK-77 rung 4 sent at 22:21, outcome unknown, half filled by the fake
  exchange; first look at 22:22 (venue 567.93, bot 1135.86); held at 22:23; resolved at 22:24 (567.93 sold),
  cleared at 22:24.
- The restart at 21:30 (death run): first looks for XRP, LTC, NEAR, ENA, PEPE and ZEC at `start()`'s reconcile;
  all six cleared by the look after `catch_up`, before the first step.

`bot/spot/live_sim_test.py` now prints a line "balance looks: N 'coin balance differs' warnings; first, cleared,
held" (held: the heartbeats' `bal_held` counts plus the last engine's counts since its last heartbeat; a process
that dies loses the counts since its last heartbeat). A run with any such warning now FAILS.

## Tests
Run here one at a time (offline), each with its result line; none of their expectations changed.
- `bot/spot/balance_look_test.py` (new): BALANCE LOOK TEST PASSED, 26 passed, 0 failed. The brief's cases and the
  hold's six cases. Engine stand-ins: the step's data and decision parts are no-ops; a fill is booked by a hook at the
  start of `_settle`; the failed `place_many` case uses an `_allocate` stand-in that calls `reconcile` as the failure
  branch does. The watchdog case runs `bot/spot/deploy/watchdog.py` itself on a small events file.
- `bot/spot/live_sim_test.py`, without and with the death: LIVE-PATH TEST PASSED (table above).
- `bot/spot/order_path_unit_test.py`: ORDER PATH UNIT TEST PASSED (116 PASS lines).
- `bot/spot/order_path_test.py`, without the death: ORDER PATH TEST PASSED (23 PASS lines); with the death: ORDER PATH
  TEST PASSED (23 PASS lines). Its requests per minute are reported, not checked: get_accounts median 1, max 2,
  total 522 without the death and 500 with it.
- `bot/spot/live_sim_inputs_test.py`, without the death (A, B, C1, C2, E, F0, F1, D): LIVE-PATH INPUTS TEST PASSED
  (37 PASS lines); with the death (A, B, C1, C2, E): LIVE-PATH INPUTS TEST PASSED (22 PASS lines). Every live-path
  run in it shows 0 "coin balance differs" warnings. The switch runs (C1, C2) add first and cleared looks at the
  switch's fresh start: 9 / 9 without the death, 14 / 14 with it.
- `bot/spot/release_inputs_test.py`: RELEASE INPUTS TEST PASSED (90 PASS lines).
- `bot/spot/usdc_test.py`: USDC QUOTE TEST PASSED (11 ok lines).
- `bot/spot/deploy/watchdog_test.py`: WATCHDOG TEST PASSED (31 PASS lines).
- `bash bot/spot/deploy/wickctl_test.sh`: WICKCTL TEST PASSED (15 PASS lines).

Not run here: `bot/spot/replay_test.py` (paper parity) and the rest of the full suite
(`scripts/owner/input_release/run_spot_tests.py`, which now lists `balance_look_test.py`); they run on a runner.

## Limits
- A new fill on the same coin in the seconds before the second look can still raise a false warning (the second look
  then sees a fresh difference that `_settle` has not booked).
- A second look that falls in a minute skipped by the stale guard, or handled by `_orders_only`, waits for the next
  normal step.
- For up to 10 minutes a real shortfall on a coin is not warned if it is no larger than that coin's market sells with
  an unknown outcome (plus the tolerance).
- A real difference is warned one step after the look that first saw it (at a start with a gap over one minute: at
  the start, right after `catch_up`, so still before the first bid).
